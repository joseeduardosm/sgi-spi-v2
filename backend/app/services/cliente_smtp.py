# Criado por José Eduardo Santana Martins
# Este arquivo serve para conversar com o servidor SMTP: conectar, autenticar e enviar mensagens.
"""Cliente SMTP de baixo nível (biblioteca padrão `smtplib`).

Concentra a conversa com o servidor: conexão (sem cifra, STARTTLS ou SSL direto), autenticação e
envio. Os erros do servidor viram mensagens em português que dizem o que conferir, inclusive os
casos comuns do Microsoft 365 (SMTP autenticado desativado, remetente sem permissão).
"""

import smtplib
import socket
import ssl
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.core.criptografia import ErroDecifrarSegredo, decifrar_segredo
from app.models.servidor_smtp import ServidorSmtp


class ErroSmtp(Exception):
    """Falha de conexão, segurança, autenticação ou envio, com mensagem pronta para a tela."""


@dataclass(frozen=True)
class ParametrosSmtp:
    """Dados de conexão desacoplados do modelo, para testar configurações ainda não salvas."""

    servidor: str
    porta: int
    seguranca: str
    usuario: str
    senha: str
    remetente_email: str
    remetente_nome: str = ""
    responder_para: str = ""
    tempo_limite_segundos: int = 20

    @classmethod
    def do_modelo(cls, servidor: ServidorSmtp, senha: str | None = None) -> "ParametrosSmtp":
        """Monta os parâmetros a partir do servidor salvo, decifrando a senha (ou usando a informada)."""
        if senha is None:
            try:
                senha = decifrar_segredo(servidor.senha_cifrada) if servidor.senha_cifrada else ""
            except ErroDecifrarSegredo as erro:
                raise ErroSmtp(f"{erro} Informe a senha de novo e salve o servidor.") from erro
        return cls(
            servidor.servidor, servidor.porta, servidor.seguranca, servidor.usuario, senha, servidor.remetente_email,
            servidor.remetente_nome, servidor.responder_para, servidor.tempo_limite_segundos,
        )


@dataclass(frozen=True)
class ResultadoSmtp:
    """Resultado de um teste de conexão ou de um envio."""
    sucesso: bool
    latencia_ms: int
    mensagem: str
    id_mensagem: str | None = None


@dataclass(frozen=True)
class AnexoEmail:
    """Arquivo anexado ao e-mail."""
    nome: str
    conteudo: bytes
    tipo: str = "application/pdf"


@dataclass(frozen=True)
class Mensagem:
    """E-mail a enviar. `html` é opcional (o texto simples sempre vai junto, para leitores sem HTML).

    `responder_para`, quando informado, substitui o "Responder para" do servidor nesta mensagem
    (ex.: respostas do diário de bordo vão para a equipe do contrato, não para a caixa de envio).
    """
    para: list[str]
    assunto: str
    texto: str
    html: str | None = None
    cc: list[str] = field(default_factory=list)
    cco: list[str] = field(default_factory=list)
    responder_para: list[str] = field(default_factory=list)
    anexos: list[AnexoEmail] = field(default_factory=list)


def _traduzir(erro: Exception, parametros: ParametrosSmtp) -> str:
    """Converte a exceção do smtplib/rede numa mensagem que diz o que conferir."""
    endereco = f"{parametros.servidor}:{parametros.porta}"
    if isinstance(erro, socket.gaierror):
        return f"Servidor {parametros.servidor} não encontrado (DNS). Confira o endereço."
    if isinstance(erro, ConnectionRefusedError):
        return f"Conexão recusada em {endereco}. Confira a porta e se o servidor aceita conexões deste endereço."
    if isinstance(erro, (TimeoutError, socket.timeout)):
        return f"Tempo esgotado ao falar com {endereco} ({parametros.tempo_limite_segundos}s). Confira porta, firewall e segurança."
    if isinstance(erro, ssl.SSLError):
        return (f"Falha na negociação TLS/SSL com {endereco}: {erro.reason or erro}. "
                "Confira a segurança: a porta 465 usa SSL direto; 587 e 25 usam STARTTLS.")
    if isinstance(erro, smtplib.SMTPAuthenticationError):
        texto = _texto_servidor(erro.smtp_error)
        if "5.7.139" in texto or "SmtpClientAuthentication is disabled" in texto:
            return ("O Microsoft 365 recusou a autenticação: o SMTP autenticado está desativado para esta conta. "
                    "O administrador do Microsoft 365 precisa habilitá-lo na caixa de correio (\"SMTP autenticado\"). "
                    f"Resposta do servidor: {erro.smtp_code} {texto}")
        return f"Usuário ou senha recusados pelo servidor ({erro.smtp_code} {texto})."
    if isinstance(erro, smtplib.SMTPSenderRefused):
        return (f"Remetente {erro.sender} recusado ({erro.smtp_code} {_texto_servidor(erro.smtp_error)}). "
                "No Microsoft 365, o remetente precisa ser a própria conta autenticada ou ter permissão \"Enviar como\".")
    if isinstance(erro, smtplib.SMTPRecipientsRefused):
        recusados = ", ".join(f"{d} ({c} {_texto_servidor(m)})" for d, (c, m) in erro.recipients.items())
        return f"Destinatário(s) recusado(s): {recusados}."
    if isinstance(erro, smtplib.SMTPNotSupportedError):
        return f"O servidor não oferece o recurso pedido: {erro}. Confira a segurança (STARTTLS) e a autenticação."
    if isinstance(erro, smtplib.SMTPServerDisconnected):
        return f"O servidor {endereco} encerrou a conexão. Confira a segurança (SSL na 465, STARTTLS na 587)."
    if isinstance(erro, smtplib.SMTPResponseException):
        return f"O servidor respondeu com erro: {erro.smtp_code} {_texto_servidor(erro.smtp_error)}"
    if isinstance(erro, OSError):
        return f"Não foi possível conectar a {endereco}: {erro.strerror or erro}."
    return f"Falha no SMTP: {erro}"


def _texto_servidor(valor: bytes | str) -> str:
    """Resposta do servidor em texto, numa linha só."""
    texto = valor.decode("utf-8", "replace") if isinstance(valor, bytes) else str(valor)
    return " ".join(texto.split())


def _conectar(parametros: ParametrosSmtp) -> smtplib.SMTP:
    """Abre a conexão com a segurança escolhida e autentica (se houver usuário)."""
    contexto = ssl.create_default_context()
    if parametros.seguranca == "ssl":
        conexao: smtplib.SMTP = smtplib.SMTP_SSL(parametros.servidor, parametros.porta, timeout=parametros.tempo_limite_segundos, context=contexto)
    else:
        conexao = smtplib.SMTP(parametros.servidor, parametros.porta, timeout=parametros.tempo_limite_segundos)
    try:
        conexao.ehlo()
        if parametros.seguranca == "starttls":
            if not conexao.has_extn("starttls"):
                raise smtplib.SMTPNotSupportedError("STARTTLS não anunciado pelo servidor")
            conexao.starttls(context=contexto)
            conexao.ehlo()
        if parametros.usuario:
            if not conexao.has_extn("auth"):
                raise smtplib.SMTPNotSupportedError("autenticação (AUTH) não anunciada nesta conexão")
            conexao.login(parametros.usuario, parametros.senha)
    except BaseException:
        conexao.close()
        raise
    return conexao


def testar_conexao(parametros: ParametrosSmtp) -> ResultadoSmtp:
    """Valida endereço, porta, segurança e credenciais (sem enviar mensagem)."""
    inicio = time.perf_counter()
    try:
        conexao = _conectar(parametros)
        try:
            conexao.noop()
        finally:
            _encerrar(conexao)
    except Exception as erro:  # noqa: BLE001 - toda falha vira mensagem para a tela
        return ResultadoSmtp(False, _ms(inicio), _traduzir(erro, parametros))
    autenticacao = f"autenticado como {parametros.usuario}" if parametros.usuario else "sem autenticação"
    seguranca = {"starttls": "STARTTLS", "ssl": "SSL", "nenhuma": "sem cifra"}[parametros.seguranca]
    return ResultadoSmtp(True, _ms(inicio), f"Conexão com {parametros.servidor}:{parametros.porta} ({seguranca}), {autenticacao}.")


def montar_mensagem(parametros: ParametrosSmtp, mensagem: Mensagem) -> EmailMessage:
    """Monta o e-mail com remetente, destinatários, assunto, data e identificador."""
    email = EmailMessage()
    email["From"] = formataddr((parametros.remetente_nome, parametros.remetente_email)) if parametros.remetente_nome else parametros.remetente_email
    email["To"] = ", ".join(mensagem.para)
    if mensagem.cc:
        email["Cc"] = ", ".join(mensagem.cc)
    if mensagem.responder_para:
        email["Reply-To"] = ", ".join(mensagem.responder_para)
    elif parametros.responder_para:
        email["Reply-To"] = parametros.responder_para
    email["Subject"] = mensagem.assunto
    email["Date"] = formatdate(localtime=True)
    email["Message-ID"] = make_msgid(domain=parametros.remetente_email.rsplit("@", 1)[-1])
    email.set_content(mensagem.texto)
    if mensagem.html:
        email.add_alternative(mensagem.html, subtype="html")
    for anexo in mensagem.anexos:
        principal, _, secundario = anexo.tipo.partition("/")
        email.add_attachment(anexo.conteudo, maintype=principal, subtype=secundario or "octet-stream", filename=anexo.nome)
    return email


def enviar(parametros: ParametrosSmtp, mensagem: Mensagem) -> ResultadoSmtp:
    """Envia a mensagem. Falha não lança exceção: volta `sucesso=False` com a mensagem traduzida."""
    inicio = time.perf_counter()
    email = montar_mensagem(parametros, mensagem)
    destinatarios = [*mensagem.para, *mensagem.cc, *mensagem.cco]
    try:
        conexao = _conectar(parametros)
        try:
            conexao.send_message(email, from_addr=parametros.remetente_email, to_addrs=destinatarios)
        finally:
            _encerrar(conexao)
    except Exception as erro:  # noqa: BLE001 - toda falha vira mensagem para a tela
        return ResultadoSmtp(False, _ms(inicio), _traduzir(erro, parametros))
    return ResultadoSmtp(True, _ms(inicio), f"Mensagem aceita pelo servidor para {len(destinatarios)} destinatário(s).", email["Message-ID"])


def _encerrar(conexao: smtplib.SMTP) -> None:
    """Encerra a sessão; se o servidor já tiver fechado a conexão, só libera o socket."""
    try:
        conexao.quit()
    except (smtplib.SMTPException, OSError):
        conexao.close()


def _ms(inicio: float) -> int:
    """Milissegundos desde `inicio`."""
    return int((time.perf_counter() - inicio) * 1000)
