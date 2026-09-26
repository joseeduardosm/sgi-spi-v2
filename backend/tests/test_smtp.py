# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a administração dos servidores SMTP e o envio de e-mail.
"""Testes dos servidores SMTP: cadastro, validações, teste de conexão, envio de teste e permissões.

Usam um servidor SMTP simulado (substitui `smtplib.SMTP`/`SMTP_SSL`), sem rede.
"""

import smtplib
import uuid

import pytest

from app.core.banco import FabricaSessao
from app.models import RegistroAuditoria, ServidorSmtp
from app.services import servico_smtp
from app.services.cliente_smtp import Mensagem
from tests.conftest import cabecalho, criar_usuario

URL = "/api/smtp/servidores"
SENHA = "S3nha-Smtp-9x"


class SmtpSimulado:
    """Servidor SMTP falso: anuncia STARTTLS e AUTH, confere a senha e guarda as mensagens aceitas."""

    enviadas: list = []
    conexoes: list = []
    recusar_remetente = False

    def __init__(self, servidor, porta, timeout=None, context=None):
        if servidor == "inexistente.invalid":
            raise __import__("socket").gaierror("nome não resolvido")
        SmtpSimulado.conexoes.append((type(self).__name__, servidor, porta))
        self.tls = False

    def ehlo(self):
        return 250, b"ok"

    def has_extn(self, nome):
        return nome in ("starttls", "auth")

    def starttls(self, context=None):
        self.tls = True

    def login(self, usuario, senha):
        if senha != SENHA:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.3 Authentication unsuccessful")

    def noop(self):
        return 250, b"ok"

    def send_message(self, mensagem, from_addr=None, to_addrs=None):
        if SmtpSimulado.recusar_remetente:
            raise smtplib.SMTPSenderRefused(554, b"5.2.252 SendAsDenied", from_addr)
        SmtpSimulado.enviadas.append((mensagem, from_addr, to_addrs, self.tls))

    def quit(self):
        pass

    def close(self):
        pass


class SmtpSslSimulado(SmtpSimulado):
    """Variante SSL direto (porta 465)."""


@pytest.fixture(autouse=True)
def smtp_simulado(monkeypatch):
    """Troca o smtplib pelo servidor simulado e zera o registro entre os testes."""
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)
    return SmtpSimulado


def dados_servidor(**alteracoes) -> dict:
    """Configuração válida no molde do Microsoft 365; os argumentos sobrescrevem campos."""
    dados = {
        "nome": "Microsoft 365", "servidor": "smtp.office365.com", "porta": 587, "seguranca": "starttls",
        "usuario": "chamados.spi@sp.gov.br", "senha": SENHA, "remetente_email": "chamados.spi@sp.gov.br",
        "remetente_nome": "Chamados SPI", "responder_para": "", "tempo_limite_segundos": 20, "ativo": True,
    }
    dados.update(alteracoes)
    return dados


def _criar(cliente, admin, **alteracoes) -> dict:
    """Cadastra um servidor pela API e devolve o JSON."""
    r = cliente.post(URL, json=dados_servidor(**alteracoes), headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


# --- Cadastro e validações ------------------------------------------------------------------------

def test_cadastro_cifra_senha_e_nao_a_devolve(cliente, admin):
    """A senha é gravada cifrada e nunca aparece na resposta (só `possui_senha`)."""
    corpo = _criar(cliente, admin)
    assert "senha" not in corpo and "senha_cifrada" not in corpo and corpo["possui_senha"] is True
    with FabricaSessao() as sessao:
        servidor = sessao.get(ServidorSmtp, uuid.UUID(corpo["id"]))
        assert servidor.senha_cifrada and SENHA not in servidor.senha_cifrada


@pytest.mark.parametrize(
    "alteracao, trecho",
    [
        ({"remetente_email": "sem-arroba"}, "e-mail inválido"),
        ({"responder_para": "x@"}, "e-mail inválido"),
        ({"seguranca": "ssl", "porta": 587}, "587 usa STARTTLS"),
        ({"seguranca": "starttls", "porta": 465}, "465 usa SSL"),
        ({"servidor": "smtp://smtp.office365.com"}, "só o nome ou IP"),
        ({"servidor": "smtp.office365.com:587"}, "só o nome ou IP"),
        ({"senha": None}, "informe a senha"),
        ({"seguranca": "tls"}, "starttls"),
    ],
)
def test_validacoes_do_cadastro(cliente, admin, alteracao, trecho):
    """Combinações inválidas são recusadas com mensagem que diz o que corrigir."""
    r = cliente.post(URL, json=dados_servidor(**alteracao), headers=admin)
    assert r.status_code == 422 and trecho in r.text


def test_sem_usuario_nao_exige_senha(cliente, admin):
    """Relay interno sem autenticação: usuário e senha vazios."""
    corpo = _criar(cliente, admin, usuario="", senha=None, porta=25, seguranca="nenhuma")
    assert corpo["possui_senha"] is False


def test_apenas_um_servidor_ativo(cliente, admin):
    """Ativar um servidor desativa o outro."""
    a = _criar(cliente, admin, nome="A")
    _criar(cliente, admin, nome="B")
    assert {s["nome"]: s["ativo"] for s in cliente.get(URL, headers=admin).json()} == {"A": False, "B": True}
    cliente.put(f"{URL}/{a['id']}", json=dados_servidor(nome="A", senha=""), headers=admin)
    assert {s["nome"]: s["ativo"] for s in cliente.get(URL, headers=admin).json()} == {"A": True, "B": False}


def test_edicao_sem_senha_preserva_a_atual(cliente, admin, smtp_simulado):
    """Alterar sem mandar senha mantém a gravada (o teste continua autenticando)."""
    s = _criar(cliente, admin)
    r = cliente.put(f"{URL}/{s['id']}", json=dados_servidor(nome="Renomeado", senha=None), headers=admin)
    assert r.status_code == 200 and r.json()["nome"] == "Renomeado"
    assert cliente.post(f"{URL}/{s['id']}/testar", headers=admin).json()["sucesso"] is True


def test_edicao_sem_usuario_descarta_senha(cliente, admin):
    """Tirar o usuário descarta a senha gravada."""
    s = _criar(cliente, admin)
    r = cliente.put(f"{URL}/{s['id']}", json=dados_servidor(usuario="", senha=None, porta=25, seguranca="nenhuma"), headers=admin)
    assert r.json()["possui_senha"] is False


def test_excluir(cliente, admin):
    """Exclusão remove o servidor e registra auditoria."""
    s = _criar(cliente, admin)
    assert cliente.delete(f"{URL}/{s['id']}", headers=admin).status_code == 204
    assert cliente.get(f"{URL}/{s['id']}", headers=admin).status_code == 404
    with FabricaSessao() as sessao:
        acoes = [r.acao for r in sessao.query(RegistroAuditoria).filter(RegistroAuditoria.acao.like("smtp.%"))]
    assert acoes == ["smtp.criar", "smtp.excluir"]


# --- Teste de conexão -----------------------------------------------------------------------------

def test_testar_sem_salvar_usa_starttls_e_autentica(cliente, admin, smtp_simulado):
    """O teste sem salvar conecta, sobe para TLS e autentica, sem gravar nada."""
    r = cliente.post(f"{URL}/testar", json=dados_servidor(), headers=admin).json()
    assert r["sucesso"] is True and "STARTTLS" in r["mensagem"] and "chamados.spi@sp.gov.br" in r["mensagem"]
    assert cliente.get(URL, headers=admin).json() == []


def test_testar_ssl_direto(cliente, admin, smtp_simulado):
    """Segurança `ssl` abre a conexão já cifrada (SMTP_SSL)."""
    r = cliente.post(f"{URL}/testar", json=dados_servidor(porta=465, seguranca="ssl"), headers=admin).json()
    assert r["sucesso"] is True and smtp_simulado.conexoes[-1][0] == "SmtpSslSimulado"


def test_senha_errada_e_servidor_inexistente(cliente, admin):
    """Falhas voltam com `sucesso=false` e mensagem em português."""
    r = cliente.post(f"{URL}/testar", json=dados_servidor(senha="errada"), headers=admin).json()
    assert r["sucesso"] is False and "Usuário ou senha recusados" in r["mensagem"]
    r = cliente.post(f"{URL}/testar", json=dados_servidor(servidor="inexistente.invalid"), headers=admin).json()
    assert r["sucesso"] is False and "não encontrado (DNS)" in r["mensagem"]


def test_teste_do_servidor_salvo_registra_resultado(cliente, admin):
    """O teste do servidor salvo grava data, resultado e erro; a senha temporária não é gravada."""
    s = _criar(cliente, admin)
    r = cliente.post(f"{URL}/{s['id']}/testar", json={"senha": "errada"}, headers=admin).json()
    assert r["sucesso"] is False
    salvo = cliente.get(f"{URL}/{s['id']}", headers=admin).json()
    assert salvo["ultimo_teste_ok"] is False and "recusados" in salvo["ultimo_erro"]
    assert cliente.post(f"{URL}/{s['id']}/testar", headers=admin).json()["sucesso"] is True
    salvo = cliente.get(f"{URL}/{s['id']}", headers=admin).json()
    assert salvo["ultimo_teste_ok"] is True and salvo["ultimo_erro"] is None


# --- Envio -----------------------------------------------------------------------------------------

def test_envio_de_teste(cliente, admin, smtp_simulado):
    """O e-mail de teste sai com remetente, nome e destinatário certos, pela conexão TLS."""
    s = _criar(cliente, admin, responder_para="suporte@sp.gov.br")
    r = cliente.post(f"{URL}/{s['id']}/enviar-teste", json={"destinatario": "fulano@sp.gov.br"}, headers=admin).json()
    assert r["sucesso"] is True and r["id_mensagem"]
    mensagem, remetente, destinatarios, tls = smtp_simulado.enviadas[0]
    assert remetente == "chamados.spi@sp.gov.br" and destinatarios == ["fulano@sp.gov.br"] and tls
    assert mensagem["From"] == "Chamados SPI <chamados.spi@sp.gov.br>" and mensagem["Reply-To"] == "suporte@sp.gov.br"
    assert "Teste de envio" in mensagem["Subject"]
    salvo = cliente.get(f"{URL}/{s['id']}", headers=admin).json()
    assert salvo["ultimo_envio_ok"] is True and salvo["ultimo_envio_para"] == "fulano@sp.gov.br"


def test_envio_com_remetente_recusado_explica_permissao(cliente, admin, smtp_simulado):
    """Remetente sem permissão (ex.: Microsoft 365 sem "Enviar como") volta com a explicação."""
    smtp_simulado.recusar_remetente = True
    s = _criar(cliente, admin)
    r = cliente.post(f"{URL}/{s['id']}/enviar-teste", json={"destinatario": "fulano@sp.gov.br"}, headers=admin).json()
    assert r["sucesso"] is False and "Enviar como" in r["mensagem"]
    assert cliente.post(f"{URL}/{s['id']}/enviar-teste", json={"destinatario": "invalido"}, headers=admin).status_code == 422


def test_enviar_email_usa_o_servidor_ativo(cliente, admin, smtp_simulado):
    """A função usada pelos módulos envia pelo servidor ativo; sem ativo, avisa."""
    with FabricaSessao() as sessao:
        with pytest.raises(servico_smtp.SemServidorAtivo):
            servico_smtp.enviar_email(sessao, Mensagem(para=["a@sp.gov.br"], assunto="Oi", texto="Olá"))
    _criar(cliente, admin, nome="Inativo", ativo=False, remetente_email="outro@sp.gov.br")
    _criar(cliente, admin, nome="Ativo")
    with FabricaSessao() as sessao:
        r = servico_smtp.enviar_email(sessao, Mensagem(para=["a@sp.gov.br"], cc=["b@sp.gov.br"], assunto="Oi", texto="Olá", html="<p>Olá</p>"))
    assert r.sucesso
    mensagem, remetente, destinatarios, _ = smtp_simulado.enviadas[0]
    assert remetente == "chamados.spi@sp.gov.br" and destinatarios == ["a@sp.gov.br", "b@sp.gov.br"] and mensagem.is_multipart()


# --- Permissões ------------------------------------------------------------------------------------

def test_somente_superroot(cliente, admin):
    """Usuário comum recebe 403 em todas as rotas."""
    s = _criar(cliente, admin)
    criar_usuario("comum")
    comum = cabecalho(cliente, "comum")
    assert cliente.get(URL, headers=comum).status_code == 403
    assert cliente.post(URL, json=dados_servidor(), headers=comum).status_code == 403
    assert cliente.post(f"{URL}/testar", json=dados_servidor(), headers=comum).status_code == 403
    assert cliente.post(f"{URL}/{s['id']}/enviar-teste", json={"destinatario": "a@sp.gov.br"}, headers=comum).status_code == 403
