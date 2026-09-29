# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a tela Mensageria: e-mail de changelog exclusivo da conta root.
"""Mensageria (`/api/mensageria`): rascunho a partir do CHANGELOG, prévia, envio e acesso só da conta root."""

from datetime import date

import smtplib

import pytest

from app.services import servico_changelog
from tests.conftest import cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor

URL = "/api/mensageria/changelog"

CHANGELOG = """# Changelog

Texto de apresentação.

## 2026-09-29

### Adicionado
- **Trilha clicável** em todas as telas.
  - Migração `abc123`: tabela nova.
  - Endpoints `/api/x`.
- Mensageria com `e-mail` de changelog.

### Corrigido
- Janela de usuário mais larga.

## 2026-09-28

### Alterado
- Painel de vigências ordenado.

## 2026-09-24 a 2026-09-25

### Adicionado
- Módulo antigo.
"""


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, tmp_path):
    """SMTP simulado e um CHANGELOG próprio do teste."""
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)
    arquivo = tmp_path / "CHANGELOG.md"
    arquivo.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(servico_changelog, "ARQUIVO_CHANGELOG", arquivo)
    return arquivo


def test_ler_entradas_usa_a_ultima_data_do_titulo():
    entradas = servico_changelog.ler_entradas(CHANGELOG)
    assert [e.data for e in entradas] == [date(2026, 9, 29), date(2026, 9, 28), date(2026, 9, 25)]


def test_so_a_conta_root_acessa(cliente, admin):
    criar_usuario("chefe", superusuario=True)
    criar_usuario("comum")
    for login in ("chefe", "comum"):
        r = cliente.get(f"{URL}/rascunho", headers=cabecalho(cliente, login))
        assert r.status_code == 403 and r.json()["codigo"] == "acesso_negado"
    assert cliente.get(f"{URL}/rascunho", headers=admin).status_code == 200
    # A sessão informa ao frontend quem é a conta root
    assert cliente.get("/api/autenticacao/sessao", headers=admin).json()["conta_root"] is True
    assert cliente.get("/api/autenticacao/sessao", headers=cabecalho(cliente, "chefe")).json()["conta_root"] is False


def test_rascunho_sem_detalhes_tecnicos_e_so_a_entrada_mais_recente(cliente, admin):
    criar_usuario("ana", email="ana@sp.gov.br")
    r = cliente.get(f"{URL}/rascunho", headers=admin).json()
    assert r["assunto"] == "SGI SPI – Novidades de 29/09/2026"
    assert r["ate"] == "2026-09-29" and r["desde"] is None and r["datas"] == ["2026-09-29"]
    corpo = r["corpo"]
    assert "## Novidades" in corpo and "## Correções" in corpo and "**Trilha clicável**" in corpo
    assert "Migração" not in corpo and "Endpoints" not in corpo and "`" not in corpo
    assert "Painel de vigências" not in corpo
    assert r["total_destinatarios"] >= 1


def test_previa_no_layout_oficial_com_brasao_embutido(cliente, admin):
    r = cliente.post(f"{URL}/previa", json={"assunto": "Novidades", "corpo": "Olá!\n\n## Novidades\n- **Um**\n  - dois\n- três <b>"}, headers=admin)
    assert r.status_code == 200
    html = r.json()["html"]
    assert "data:image/png;base64," in html and "cid:brasao-spi" not in html
    assert "<strong>Um</strong>" in html and html.count("<ul") == 2 and "&lt;b&gt;" in html
    assert "SGI SPI – Sistema de Gestão Integrada" in html


def test_envio_de_teste_nao_avanca_o_rascunho(cliente, admin):
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    r = cliente.post(f"{URL}/envios", json={"assunto": "Teste", "corpo": "Olá", "destino": "teste", "email_teste": "eu@sp.gov.br", "ate_data": "2026-09-29"},
                     headers=admin)
    assert r.status_code == 202, r.text
    assert len(SmtpSimulado.enviadas) == 1 and SmtpSimulado.enviadas[0][2] == ["eu@sp.gov.br"]
    historico = cliente.get(f"{URL}/envios", headers=admin).json()
    assert historico[0]["enviados"] == 1 and historico[0]["concluido_em"] and historico[0]["ate_data"] is None
    assert cliente.get(f"{URL}/rascunho", headers=admin).json()["ate"] == "2026-09-29"
    # Teste sem e-mail é recusado
    r = cliente.post(f"{URL}/envios", json={"assunto": "Teste", "corpo": "Olá", "destino": "teste"}, headers=admin)
    assert r.status_code == 422


def test_envio_a_todos_um_email_por_pessoa_e_proximo_rascunho(cliente, admin, _ambiente):
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    criar_usuario("ana", email="ana@sp.gov.br")
    criar_usuario("bia", email="ANA@sp.gov.br")  # repetido: recebe uma vez só
    criar_usuario("caio", email="caio@sp.gov.br", ativo=False)
    rascunho = cliente.get(f"{URL}/rascunho", headers=admin).json()
    r = cliente.post(f"{URL}/envios", json={"assunto": rascunho["assunto"], "corpo": rascunho["corpo"], "destino": "todos", "ate_data": rascunho["ate"]},
                     headers=admin)
    assert r.status_code == 202, r.text
    destinos = [d for _, _, dests, _ in SmtpSimulado.enviadas for d in dests]
    assert "ana@sp.gov.br" in destinos and "caio@sp.gov.br" not in destinos
    assert len(destinos) == len({d.lower() for d in destinos})
    assert all(len(dests) == 1 for _, _, dests, _ in SmtpSimulado.enviadas)
    assert SmtpSimulado.enviadas[0][0]["Subject"] == "SGI SPI – Novidades de 29/09/2026"
    # Nada novo depois do envio; uma entrada nova no CHANGELOG entra no próximo rascunho
    assert cliente.get(f"{URL}/rascunho", headers=admin).json()["ate"] is None
    _ambiente.write_text(CHANGELOG.replace("## 2026-09-29", "## 2026-10-01\n\n### Adicionado\n- Nova tela.\n\n## 2026-09-29"), encoding="utf-8")
    novo = cliente.get(f"{URL}/rascunho", headers=admin).json()
    assert novo["datas"] == ["2026-10-01"] and "Nova tela" in novo["corpo"] and "Trilha" not in novo["corpo"]
