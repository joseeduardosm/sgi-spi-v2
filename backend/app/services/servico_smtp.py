# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de cadastro, teste e envio dos servidores SMTP.
"""Regras de negócio dos servidores SMTP: cadastro, ativação, teste de conexão e envio.

A conversa com o servidor fica em `cliente_smtp`; aqui ficam as decisões: qual servidor está
ativo, o que é gravado depois de um teste e a função `enviar_email`, usada pelos módulos que
mandam e-mail (ex.: mensageria) por meio do servidor ativo.
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.criptografia import cifrar_segredo
from app.models.servidor_smtp import ServidorSmtp
from app.schemas.smtp import AlteracaoServidorSmtp, CriacaoServidorSmtp
from app.services import cliente_smtp
from app.services.cliente_smtp import ErroSmtp, Mensagem, ParametrosSmtp, ResultadoSmtp
from app.services.servico_auditoria import auditar

CAMPOS = ("nome", "servidor", "porta", "seguranca", "usuario", "remetente_email", "remetente_nome", "responder_para",
          "tempo_limite_segundos", "ativo")


class ServidorNaoEncontrado(Exception):
    """O servidor pedido não existe (vira 404)."""


class SemServidorAtivo(Exception):
    """Nenhum servidor SMTP ativo: o sistema não tem como enviar e-mail."""


def listar_servidores(sessao: Session) -> list[ServidorSmtp]:
    """Servidores em ordem alfabética."""
    return list(sessao.scalars(select(ServidorSmtp).order_by(func.lower(ServidorSmtp.nome))))


def obter_servidor(sessao: Session, servidor_id: uuid.UUID) -> ServidorSmtp:
    """Servidor pelo id, ou `ServidorNaoEncontrado`."""
    servidor = sessao.get(ServidorSmtp, servidor_id)
    if servidor is None:
        raise ServidorNaoEncontrado()
    return servidor


def obter_servidor_ativo(sessao: Session) -> ServidorSmtp | None:
    """O servidor ativo (no máximo um), ou None se o envio de e-mail estiver desligado."""
    return sessao.scalar(select(ServidorSmtp).where(ServidorSmtp.ativo.is_(True)))


def _desativar_demais(sessao: Session, manter_id: uuid.UUID | None) -> None:
    """Desativa os servidores ativos, exceto `manter_id` (garante que só um fique ativo)."""
    comando = update(ServidorSmtp).where(ServidorSmtp.ativo.is_(True))
    if manter_id is not None:
        comando = comando.where(ServidorSmtp.id != manter_id)
    sessao.execute(comando.values(ativo=False))
    sessao.flush()


def criar_servidor(sessao: Session, dados: CriacaoServidorSmtp, autor: str) -> ServidorSmtp:
    """Cadastra o servidor, com a senha cifrada."""
    if dados.ativo:
        _desativar_demais(sessao, None)
    servidor = ServidorSmtp(**{campo: getattr(dados, campo) for campo in CAMPOS})
    servidor.senha_cifrada = cifrar_segredo(dados.senha) if dados.senha else None
    sessao.add(servidor)
    sessao.flush()
    auditar(sessao, autor, "smtp.criar", servidor.nome, f"id={servidor.id} ativo={servidor.ativo}")
    sessao.commit()
    return servidor


def alterar_servidor(sessao: Session, servidor_id: uuid.UUID, dados: AlteracaoServidorSmtp, autor: str) -> ServidorSmtp:
    """Altera o servidor; senha em branco mantém a atual. Sem usuário, a senha gravada é descartada."""
    servidor = obter_servidor(sessao, servidor_id)
    if dados.ativo:
        _desativar_demais(sessao, servidor.id)
    for campo in CAMPOS:
        setattr(servidor, campo, getattr(dados, campo))
    if not dados.usuario:
        servidor.senha_cifrada = None
    elif dados.senha:
        servidor.senha_cifrada = cifrar_segredo(dados.senha)
    elif not servidor.senha_cifrada:
        raise ErroSmtp("Informe a senha da conta de autenticação.")
    auditar(sessao, autor, "smtp.alterar", servidor.nome, f"id={servidor.id} ativo={servidor.ativo}")
    sessao.commit()
    return servidor


def excluir_servidor(sessao: Session, servidor_id: uuid.UUID, autor: str) -> None:
    """Exclui o servidor."""
    servidor = obter_servidor(sessao, servidor_id)
    auditar(sessao, autor, "smtp.excluir", servidor.nome, f"id={servidor.id}")
    sessao.delete(servidor)
    sessao.commit()


def parametros_do_formulario(dados: CriacaoServidorSmtp) -> ParametrosSmtp:
    """Parâmetros de conexão a partir de dados ainda não salvos."""
    return ParametrosSmtp(dados.servidor, dados.porta, dados.seguranca, dados.usuario, dados.senha or "", dados.remetente_email,
                          dados.remetente_nome, dados.responder_para, dados.tempo_limite_segundos)


def testar_parametros(dados: CriacaoServidorSmtp) -> ResultadoSmtp:
    """Testa uma configuração ainda não salva (nada é gravado)."""
    return cliente_smtp.testar_conexao(parametros_do_formulario(dados))


def testar_servidor(sessao: Session, servidor_id: uuid.UUID, senha: str | None) -> ResultadoSmtp:
    """Testa a configuração salva e registra data, resultado, tempo de resposta e erro."""
    servidor = obter_servidor(sessao, servidor_id)
    try:
        resultado = cliente_smtp.testar_conexao(ParametrosSmtp.do_modelo(servidor, senha or None))
    except ErroSmtp as erro:
        # Falha antes da conexão (ex.: senha gravada não pode ser decifrada) conta como teste sem sucesso
        resultado = ResultadoSmtp(False, 0, str(erro))
    servidor.ultimo_teste_em = agora_utc()
    servidor.ultimo_teste_ok = resultado.sucesso
    servidor.ultima_latencia_ms = resultado.latencia_ms
    servidor.ultimo_erro = None if resultado.sucesso else resultado.mensagem
    sessao.commit()
    return resultado


def enviar_teste(sessao: Session, servidor_id: uuid.UUID, destinatario: str, autor: str) -> ResultadoSmtp:
    """Envia um e-mail de teste pelo servidor salvo e registra o resultado (prova de ponta a ponta)."""
    servidor = obter_servidor(sessao, servidor_id)
    agora = agora_utc()
    mensagem = Mensagem(
        para=[destinatario],
        assunto=f"Teste de envio — {servidor.nome}",
        texto=(
            "Esta é uma mensagem de teste do portal Contratos SPI.\n\n"
            f"Servidor: {servidor.servidor}:{servidor.porta} ({servidor.seguranca})\n"
            f"Remetente: {servidor.remetente_email}\n"
            f"Enviada por: {autor}\n"
            f"Data: {agora:%d/%m/%Y %H:%M} (UTC)\n\n"
            "Se você recebeu este e-mail, o envio pelo portal está funcionando."
        ),
    )
    try:
        resultado = cliente_smtp.enviar(ParametrosSmtp.do_modelo(servidor), mensagem)
    except ErroSmtp as erro:
        resultado = ResultadoSmtp(False, 0, str(erro))
    servidor.ultimo_envio_em = agora
    servidor.ultimo_envio_ok = resultado.sucesso
    servidor.ultimo_envio_para = destinatario
    servidor.ultimo_envio_mensagem = resultado.mensagem
    auditar(sessao, autor, "smtp.enviar_teste", servidor.nome, f"para={destinatario} sucesso={resultado.sucesso}")
    sessao.commit()
    return resultado


def enviar_email(sessao: Session, mensagem: Mensagem) -> ResultadoSmtp:
    """Envia pelo servidor ativo. Usado pelos módulos que mandam e-mail. Lança `SemServidorAtivo`."""
    servidor = obter_servidor_ativo(sessao)
    if servidor is None:
        raise SemServidorAtivo("Nenhum servidor SMTP ativo. Cadastre e ative um em Administração > Servidores SMTP.")
    try:
        return cliente_smtp.enviar(ParametrosSmtp.do_modelo(servidor), mensagem)
    except ErroSmtp as erro:
        return ResultadoSmtp(False, 0, str(erro))
