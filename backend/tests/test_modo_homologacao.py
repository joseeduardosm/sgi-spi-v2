# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o modo homologação: nada sai do servidor e os envios ficam registrados como simulados.
"""Modo homologação (`MODO_HOMOLOGACAO=true`): e-mail simulado sem conectar ao SMTP, SIGEO parado e a faixa na tela."""

import pytest

from app.core.configuracao import obter_configuracao
from app.services import cliente_smtp
from app.tarefas import sigeo


@pytest.fixture
def homologacao(monkeypatch):
    monkeypatch.setattr(obter_configuracao(), "modo_homologacao", True)


def test_email_e_simulado_sem_conectar(homologacao, monkeypatch):
    def nao_pode_conectar(_):
        raise AssertionError("em homologação o cliente SMTP não pode conectar")

    monkeypatch.setattr(cliente_smtp, "_conectar", nao_pode_conectar)
    parametros = cliente_smtp.ParametrosSmtp("smtp.invalido", 25, "nenhuma", "", "", "sgi@sp.gov.br")
    r = cliente_smtp.enviar(parametros, cliente_smtp.Mensagem(para=["pessoa@sp.gov.br"], assunto="Teste", texto="Oi"))
    assert r.sucesso is True and r.simulado is True and r.mensagem.startswith(cliente_smtp.SIMULADO)


def test_sigeo_nao_roda(homologacao, monkeypatch):
    monkeypatch.setattr(sigeo.servico_ob_sigeo, "executar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não pode consultar o SIGEO")))
    assert sigeo.main(["agora"]) == 0


def test_saude_avisa_a_homologacao(cliente, homologacao):
    assert cliente.get("/api/saude").json()["homologacao"] is True


def test_fora_da_homologacao_nada_muda(cliente):
    assert cliente.get("/api/saude").json()["homologacao"] is False
