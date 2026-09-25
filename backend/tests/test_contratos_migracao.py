"""Importação do SGI pela tela: só o SuperRoot, senhas conferidas antes, uma execução por vez."""

import os

import pytest

from app.services.contratos import servico_migracao_sgi as servico
from tests.conftest import cabecalho, criar_usuario

URL = "/api/contratos/migracao-sgi"
SENHAS = {"senha_origem": "S3nh@-Orig-7f2", "senha_destino": "S3nh@-Dest-9k1"}


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    monkeypatch.setattr(servico, "_diretorio", lambda: tmp_path)
    iniciados = []

    class ProcessoFalso:
        pid = os.getpid()  # processo vivo: o estado continua "executando"

        def __init__(self, comando, **opcoes):
            iniciados.append((comando, opcoes["env"]))

    monkeypatch.setattr(servico.subprocess, "Popen", ProcessoFalso)
    return iniciados


def test_somente_superroot(cliente, admin):
    criar_usuario("comum")
    comum = cabecalho(cliente, "comum")
    assert cliente.get(URL, headers=comum).status_code == 403
    assert cliente.post(URL, json=SENHAS, headers=comum).status_code == 403
    estado = cliente.get(URL, headers=admin).json()
    assert estado["situacao"] == "ociosa" and estado["origem"].endswith("10.23.1.220")


def test_senha_incorreta_nao_inicia(cliente, admin, monkeypatch, _isolar):
    def recusar(*_):
        raise servico.ErroMigracao("Senha incorreta para administrador@10.23.1.220 (origem).", "senha_invalida")

    monkeypatch.setattr(servico, "validar_senhas", recusar)
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 400 and r.json()["codigo"] == "senha_invalida"
    assert not _isolar and cliente.get(URL, headers=admin).json()["situacao"] == "ociosa"


def test_inicia_em_segundo_plano_e_bloqueia_outra(cliente, admin, monkeypatch, _isolar):
    monkeypatch.setattr(servico, "validar_senhas", lambda *_: None)
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 202 and r.json()["situacao"] == "executando"
    comando, ambiente = _isolar[0]
    assert comando[-2:] == ["1", "root"] and ambiente["SGI_SENHA"] == "S3nh@-Orig-7f2"
    # A senha não fica no estado nem no registro
    gravado = servico._arquivo_estado().read_text() + servico._arquivo_log().read_text()
    assert "S3nh@" not in gravado
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "conflito"


def test_execucao_interrompida_vira_erro(cliente, admin):
    servico._gravar_estado(situacao="executando", etapa="extraindo", pid=999999999)
    estado = cliente.get(URL, headers=admin).json()
    assert estado["situacao"] == "erro" and "interrompida" in estado["mensagem"]
