# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a tela Administração › Versões: homologação acompanha o ramo e aprova (tag no GitHub), produção instala.
"""Testes da atualização do SGI pelo GitHub, com repositórios Git temporários (um "GitHub" local e um clone fazendo o papel do servidor)."""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.core.configuracao import obter_configuracao
from app.services import servico_backup, servico_versoes
from tests.conftest import cabecalho, criar_usuario

BASE = "/api/admin/versoes"
RAMO = "estado-atual-servidor"


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(pasta), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(trabalho: Path, linha: str) -> str:
    """Novo commit no "computador de desenvolvimento", com uma linha no CHANGELOG, enviado ao GitHub."""
    changelog = trabalho / "CHANGELOG.md"
    changelog.write_text(changelog.read_text() + linha + "\n")
    _git(trabalho, "commit", "-qam", linha)
    _git(trabalho, "push", "-q", "origin", RAMO)
    return _git(trabalho, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """GitHub (bare), o computador de desenvolvimento e o servidor (clone em que a API roda)."""
    for var, valor in (("GIT_AUTHOR_NAME", "Dev"), ("GIT_AUTHOR_EMAIL", "dev@x"), ("GIT_COMMITTER_NAME", "Dev"), ("GIT_COMMITTER_EMAIL", "dev@x")):
        monkeypatch.setenv(var, valor)
    github, trabalho, servidor = tmp_path / "github.git", tmp_path / "trabalho", tmp_path / "servidor"
    subprocess.run(["git", "init", "-q", "--bare", "-b", RAMO, str(github)], check=True)
    subprocess.run(["git", "init", "-q", "-b", RAMO, str(trabalho)], check=True)
    (trabalho / "CHANGELOG.md").write_text("# Changelog\n")
    _git(trabalho, "add", ".")
    _git(trabalho, "commit", "-qm", "inicio")
    _git(trabalho, "remote", "add", "origin", str(github))
    _git(trabalho, "push", "-q", "origin", RAMO)
    subprocess.run(["git", "clone", "-q", "-b", RAMO, str(github), str(servidor)], check=True)
    config = obter_configuracao()
    monkeypatch.setattr(servico_versoes, "raiz", lambda: servidor)
    monkeypatch.setattr(config, "atualizacao_diretorio", tmp_path / "atualizacao")
    monkeypatch.setattr(config, "backups_diretorio", tmp_path / "backups")
    monkeypatch.setattr(config, "modo_homologacao", False)
    disparos: list = []
    monkeypatch.setattr(servico_versoes, "disparar_unidade", lambda: disparos.append(True))
    return {"github": github, "trabalho": trabalho, "servidor": servidor, "disparos": disparos, "config": config}


def test_so_superroot(cliente, repos):
    criar_usuario("comum")
    assert cliente.get(BASE, headers=cabecalho(cliente, "comum")).status_code == 403


def test_homologacao_acompanha_o_ramo_e_pede_a_atualizacao(cliente, admin, repos, monkeypatch):
    monkeypatch.setattr(repos["config"], "modo_homologacao", True)
    _commit(repos["trabalho"], "- Nova tela de Rede")
    painel = cliente.post(f"{BASE}/buscar", headers=admin).json()
    assert painel["homologacao"] and painel["arvore_limpa"] and [c["titulo"] for c in painel["commits_novos"]] == ["- Nova tela de Rede"]
    # Confirmação e alvo errados; na homologação o alvo é o ramo
    assert cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "sim"}, headers=admin).status_code == 400
    assert cliente.post(f"{BASE}/atualizar", json={"alvo": "v2026.01.01", "confirmacao": "ATUALIZAR"}, headers=admin).status_code == 400
    r = cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin)
    assert r.status_code == 202, r.text
    assert repos["disparos"] == [True] and r.json()["andamento"]["situacao"] == "em_andamento" and r.json()["andamento"]["para"] == RAMO
    pedido = json.loads((repos["config"].atualizacao_diretorio / "pedido.json").read_text())
    assert pedido["ref"] == _git(repos["trabalho"], "rev-parse", "HEAD") and pedido["de_commit"] == _git(repos["servidor"], "rev-parse", "HEAD")
    # Uma operação por vez
    r = cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin)
    assert r.status_code == 400 and "andamento" in r.json()["detalhe"]


def test_aprovar_cria_a_tag_no_github_so_na_homologacao(cliente, admin, repos, monkeypatch):
    assert cliente.post(f"{BASE}/aprovar", headers=admin).status_code == 400  # produção não aprova
    monkeypatch.setattr(repos["config"], "modo_homologacao", True)
    r = cliente.post(f"{BASE}/aprovar", headers=admin)
    assert r.status_code == 201, r.text
    tag = r.json()["tag"]
    assert tag == f"v{datetime.now().astimezone():%Y.%m.%d}"
    assert tag in _git(repos["github"], "tag", "-l")
    assert "Aprovada em homologação por" in _git(repos["github"], "tag", "-l", "--format=%(contents)", tag)
    assert cliente.get(BASE, headers=admin).json()["aprovada"] == tag
    # Já aprovada; alteração local também bloqueia
    assert "já foi aprovada" in cliente.post(f"{BASE}/aprovar", headers=admin).json()["detalhe"]
    (repos["servidor"] / "CHANGELOG.md").write_text("mexido\n")
    assert cliente.get(BASE, headers=admin).json()["arvore_limpa"] is False


def test_producao_so_ve_e_instala_versoes_aprovadas_mais_novas(cliente, admin, repos):
    # Versão aprovada na homologação: uma tag no GitHub (feita aqui pelo computador de desenvolvimento)
    _commit(repos["trabalho"], "- Cores nas VLANs")
    _git(repos["trabalho"], "tag", "-a", "v2026.11.06", "-m", "Aprovada em homologação por Fulano em 06/11/2026 10:00")
    _git(repos["trabalho"], "push", "-q", "origin", "v2026.11.06")
    # Um commit sem aprovação não aparece para a produção
    _commit(repos["trabalho"], "- Ainda em teste")
    painel = cliente.post(f"{BASE}/buscar", headers=admin).json()
    assert [v["alvo"] for v in painel["versoes"]] == ["v2026.11.06"]
    versao = painel["versoes"][0]
    assert versao["novidades"] == "- Cores nas VLANs" and versao["aprovada_por"] == "Dev" and [c["titulo"] for c in versao["commits"]] == ["- Cores nas VLANs"]
    # Só uma versão aprovada da lista; o ramo não serve na produção
    assert cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin).status_code == 400
    r = cliente.post(f"{BASE}/atualizar", json={"alvo": "v2026.11.06", "confirmacao": "ATUALIZAR"}, headers=admin)
    assert r.status_code == 202, r.text
    # Depois de instalada (servidor na tag), ela deixa de aparecer
    _git(repos["servidor"], "checkout", "-q", "--detach", "v2026.11.06")
    (repos["config"].atualizacao_diretorio / "andamento.json").unlink()
    assert cliente.get(BASE, headers=admin).json()["versoes"] == []


def test_alteracao_local_ou_backup_em_andamento_bloqueiam(cliente, admin, repos, monkeypatch):
    monkeypatch.setattr(repos["config"], "modo_homologacao", True)
    _commit(repos["trabalho"], "- Algo")
    monkeypatch.setattr(servico_backup, "ocupado", lambda: True)
    r = cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin)
    assert r.status_code == 400 and "andamento" in r.json()["detalhe"]
    monkeypatch.setattr(servico_backup, "ocupado", lambda: False)
    (repos["servidor"] / "CHANGELOG.md").write_text("mexido\n")
    r = cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin)
    assert r.status_code == 400 and "não commitadas" in r.json()["detalhe"] and repos["disparos"] == []


def test_script_em_ensaio_troca_o_codigo_e_volta(cliente, admin, repos, monkeypatch):
    """O orquestrador (scripts/atualizar-versao.py --ensaio) confere, faz o checkout da versão pedida e volta ao commit anterior."""
    monkeypatch.setattr(repos["config"], "modo_homologacao", True)
    novo = _commit(repos["trabalho"], "- Algo novo")
    assert cliente.post(f"{BASE}/atualizar", json={"alvo": RAMO, "confirmacao": "ATUALIZAR"}, headers=admin).status_code == 202
    antes = _git(repos["servidor"], "rev-parse", "HEAD")
    caminho = Path(__file__).resolve().parents[2] / "scripts" / "atualizar-versao.py"
    especificacao = importlib.util.spec_from_file_location("atualizar_versao", caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    monkeypatch.setattr(sys, "argv", ["atualizar-versao.py", "--ensaio"])
    assert modulo.main() == 1  # o ensaio termina "com erro" de propósito, depois de voltar
    andamento = servico_versoes.andamento()
    assert andamento["situacao"] == "erro" and andamento["voltou"] is True and "ensaio" in andamento["mensagem"]
    assert _git(repos["servidor"], "rev-parse", "HEAD") == antes != novo
