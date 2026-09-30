# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Módulo Notícias: permissões, fluxo de aprovação, avisos, capa 2:1, sanitização e o portal público.
"""Módulo Notícias (`/api/noticias`, `/api/portal`)."""

import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.mensagem import EntregaMensagem, Mensagem
from app.services.noticias import servico_noticias
from app.services.noticias.sanitizacao import limpar_html
from tests.apoio_rh import simular_smtp
from tests.conftest import cabecalho, criar_usuario

URL = "/api/noticias"


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    simular_smtp(monkeypatch)


@pytest.fixture
def redacao(cliente, admin):
    """Rita redatora (MODIFICACAO), Ari aprovador (CONTROLE_TOTAL), Leo só leitura, e o setor CGP com a Cida."""
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br") for login, nome in (
        ("rita", "Rita Redatora"), ("ari", "Ari Aprovador"), ("leo", "Leo Leitor"), ("cida", "Cida da CGP"))}
    r = cliente.post("/api/acl/recursos", json={"nome": "Notícias", "slug": "noticias"}, headers=admin)
    assert r.status_code == 201, r.text
    for login, nivel in (("rita", "MODIFICACAO"), ("ari", "CONTROLE_TOTAL"), ("leo", "LEITURA")):
        corpo = {"recurso_id": r.json()["id"], "nivel": nivel, "usuarios_ids": [ids[login]], "setores_ids": []}
        assert cliente.post("/api/acl/regras", json=corpo, headers=admin).status_code == 201
    setor = cliente.post("/api/setores", json={"nome": "Coordenadoria de Gestão de Pessoas", "membros_ids": [ids["cida"]]}, headers=admin).json()["id"]
    return ids, {k: cabecalho(cliente, k) for k in ids}, setor


def _imagem(largura=1200, altura=900, formato="PNG") -> bytes:
    saida = BytesIO()
    Image.new("RGB", (largura, altura), (200, 30, 50)).save(saida, formato)
    return saida.getvalue()


def _nova(cliente, h, **extra) -> dict:
    corpo = {"titulo": "Campanha do Agasalho 2026", "linha_fina": "Doe roupas até sexta", "corpo_html": "<p>Participe!</p>", "capa_alt": "Cartaz"} | extra
    r = cliente.post(URL, json=corpo, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _com_capa(cliente, h, noticia_id, modo="recortar", recorte=None) -> dict:
    dados = {"modo": modo, "recorte": json.dumps(recorte) if recorte else ""}
    r = cliente.post(f"{URL}/{noticia_id}/capa", data=dados, files={"arquivo": ("capa.png", _imagem(), "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _avisos(prefixo: str) -> list[tuple[int, str]]:
    with FabricaSessao() as s:
        linhas = s.execute(select(EntregaMensagem.destinatario_id, Mensagem.assunto).join(Mensagem).where(Mensagem.chave.startswith(prefixo)))
        return sorted((a, b) for a, b in linhas)


def test_sanitizacao_remove_scripts_e_eventos():
    html = limpar_html('<p onclick="x()">Oi <script>alert(1)</script><a href="javascript:1">l</a> <a href="https://sp.gov.br">ok</a></p><iframe src=x></iframe>')
    assert "script" not in html and "onclick" not in html and "iframe" not in html and "javascript" not in html
    assert 'href="https://sp.gov.br"' in html and 'rel="noopener noreferrer"' in html


def test_permissoes_por_nivel(cliente, redacao):
    ids, h, _ = redacao
    assert cliente.post(URL, json={"titulo": "X"}, headers=h["leo"]).status_code == 403
    n = _nova(cliente, h["rita"])
    assert n["situacao"] == "rascunho" and n["slug"] == "campanha-do-agasalho-2026" and "enviar_revisao" in n["acoes"] and "aprovar" not in n["acoes"]
    # Leitor não vê a gestão; o aprovador vê tudo; o slug repetido ganha sufixo
    assert cliente.get(URL, headers=h["leo"]).status_code == 403
    assert _nova(cliente, h["ari"])["slug"] == "campanha-do-agasalho-2026-2"
    assert len(cliente.get(URL, headers=h["ari"]).json()) == 2
    assert len(cliente.get(URL, headers=h["rita"]).json()) == 1
    # Redatora não aprova nem edita a notícia do aprovador
    assert cliente.post(f"{URL}/{n['id']}/aprovar", json={}, headers=h["rita"]).status_code == 403
    papel = cliente.get(f"{URL}/papel", headers=h["rita"]).json()
    assert (papel["redator"], papel["aprovador"]) == (True, False)


def test_sem_regras_so_superroot_escreve(cliente, admin):
    criar_usuario("zeca")
    assert cliente.post(URL, json={"titulo": "X"}, headers=cabecalho(cliente, "zeca")).status_code == 403
    assert cliente.post(URL, json={"titulo": "X"}, headers=admin).status_code == 201


def test_fluxo_de_aprovacao_com_avisos(cliente, redacao):
    ids, h, _ = redacao
    n = _nova(cliente, h["rita"])
    # Sem capa não envia
    r = cliente.post(f"{URL}/{n['id']}/enviar-revisao", headers=h["rita"])
    assert r.status_code == 400 and "capa" in r.json()["detalhe"]
    _com_capa(cliente, h["rita"], n["id"])
    r = cliente.post(f"{URL}/{n['id']}/enviar-revisao", headers=h["rita"])
    assert r.status_code == 200 and r.json()["situacao"] == "em_revisao"
    # Aprovadores (Ari e o SuperRoot) recebem a pendência; a redatora não edita mais
    assert ids["ari"] in {d for d, _ in _avisos(f"noticia-aprovacao:{n['id']}")}
    assert cliente.put(f"{URL}/{n['id']}", json={"titulo": "Outro"}, headers=h["rita"]).status_code == 403
    # Devolução exige motivo e avisa a autora
    assert cliente.post(f"{URL}/{n['id']}/devolver", json={"motivo": " "}, headers=h["ari"]).status_code == 400
    r = cliente.post(f"{URL}/{n['id']}/devolver", json={"motivo": "Corrigir a data"}, headers=h["ari"])
    assert r.json()["situacao"] == "devolvida" and r.json()["motivo_devolucao"] == "Corrigir a data"
    assert _avisos(f"noticia-devolvida:{n['id']}")[0][0] == ids["rita"]
    # Corrige, reenvia e é aprovada: aparece no portal e a autora é avisada
    cliente.put(f"{URL}/{n['id']}", json={"titulo": "Campanha do Agasalho 2026", "corpo_html": "<p>Até sexta!</p>", "capa_alt": "Cartaz"}, headers=h["rita"])
    cliente.post(f"{URL}/{n['id']}/enviar-revisao", headers=h["rita"])
    r = cliente.post(f"{URL}/{n['id']}/aprovar", json={}, headers=h["ari"])
    assert r.status_code == 200 and r.json()["situacao"] == "aprovada" and r.json()["visivel"] is True
    assert _avisos(f"noticia-aprovada:{n['id']}")[0][0] == ids["rita"]
    with FabricaSessao() as s:
        pendentes = s.scalars(select(EntregaMensagem).join(Mensagem).where(Mensagem.chave.startswith(f"noticia-aprovacao:{n['id']}"),
                                                                              EntregaMensagem.encerrada_em.is_(None))).all()
        assert pendentes == []
    historico = cliente.get(f"{URL}/{n['id']}/revisoes", headers=h["ari"]).json()
    assert [x["descricao"] for x in historico][:2] == ["Aprovada", "Enviada para aprovação"]


def test_agendada_so_aparece_na_hora_e_avisa_o_publico(cliente, redacao):
    ids, h, setor = redacao
    futuro = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    n = _nova(cliente, h["rita"], publicar_em=futuro, exige_ciencia=True, setores_aviso=[setor], usuarios_aviso=[ids["leo"]])
    _com_capa(cliente, h["rita"], n["id"])
    cliente.post(f"{URL}/{n['id']}/enviar-revisao", headers=h["rita"])
    r = cliente.post(f"{URL}/{n['id']}/aprovar", json={}, headers=h["ari"]).json()
    assert r["situacao"] == "aprovada" and r["visivel"] is False
    # Antes da hora: fora do portal e das rotas públicas; nenhum aviso
    assert cliente.get("/api/portal").json()["slides"] == []
    assert cliente.get(f"{URL}/publicas/{n['slug']}").status_code == 404
    with FabricaSessao() as s:
        assert servico_noticias.processar_publicacoes(s) == 0
        # Depois da hora: aparece e a rotina manda o aviso (setor + usuário), com ciência
        depois = datetime.now(timezone.utc) + timedelta(hours=3)
        assert servico_noticias.processar_publicacoes(s, depois) == 1
        assert servico_noticias.processar_publicacoes(s, depois) == 0
    destinatarios = {d for d, _ in _avisos(f"noticia-aviso:{n['id']}")}
    assert destinatarios == {ids["cida"], ids["leo"]}
    assert _avisos(f"noticia-aviso:{n['id']}")[0][1].startswith("Comunicado:")
    assert cliente.get(f"{URL}/{n['id']}/ciencias", headers=h["ari"]).json()["total"] == 2


def test_capa_2x1_recorte_e_imagem_inteira(cliente, redacao):
    ids, h, _ = redacao
    n = _nova(cliente, h["rita"])
    r = _com_capa(cliente, h["rita"], n["id"], recorte={"x": 100, "y": 50, "largura": 900, "altura": 900})
    # O recorte vira 2:1 (900 × 450) e há três versões WebP
    assert r["capa_recorte"] == {"x": 100, "y": 50, "largura": 900, "altura": 450}
    assert sorted(r["capa"]) == ["1600", "400", "800"]
    imagem = cliente.get(r["capa"]["800"], headers=h["rita"])
    assert imagem.status_code == 200 and imagem.headers["content-type"] == "image/webp"
    assert Image.open(BytesIO(imagem.content)).size == (800, 400)
    # Só muda o modo (sem novo arquivo): arte inteira sobre fundo desfocado, ainda 2:1
    r = cliente.post(f"{URL}/{n['id']}/capa", data={"modo": "inteira"}, headers=h["rita"]).json()
    assert r["capa_modo"] == "inteira"
    assert Image.open(BytesIO(cliente.get(r["capa"]["1600"], headers=h["rita"]).content)).size == (1600, 800)
    # Arquivo que não é imagem é recusado
    ruim = cliente.post(f"{URL}/{n['id']}/capa", data={"modo": "recortar"}, files={"arquivo": ("x.png", b"nao-e-imagem", "image/png")}, headers=h["rita"])
    assert ruim.status_code == 400


def test_portal_publico_slider_cartoes_e_arquivo(cliente, redacao, admin):
    ids, h, _ = redacao
    agora = datetime.now(timezone.utc)
    criadas = []
    for i in range(5):
        n = _nova(cliente, h["ari"], titulo=f"Notícia {i}", publicar_em=(agora - timedelta(hours=10 - i)).isoformat(), fixada=(i == 0))
        _com_capa(cliente, h["ari"], n["id"])
        assert cliente.post(f"{URL}/{n['id']}/aprovar", json={}, headers=h["ari"]).status_code == 200
        criadas.append(n)
    # Sem token: fixada primeiro, depois as mais recentes; cartões sem repetir
    cliente.put("/api/portal/configuracao", json={"titulo": "Notícias", "subtitulo": "", "quantidade_slides": 2, "segundos_por_slide": 6,
                                                 "passagem_automatica": True, "criterio_slider": "automatico", "titulo_sobreposto": True,
                                                 "quantidade_cartoes": 2, "exibir_atalhos": True, "exibir_todas": True}, headers=h["ari"])
    portal = cliente.get("/api/portal").json()
    assert [s["titulo"] for s in portal["slides"]] == ["Notícia 0", "Notícia 4"]
    assert [c["titulo"] for c in portal["cartoes"]] == ["Notícia 3", "Notícia 2"]
    # Curadoria manual
    r = cliente.put("/api/portal/configuracao", json=portal["configuracao"] | {"criterio_slider": "curadoria", "curadoria": [criadas[2]["id"], criadas[1]["id"]]},
                    headers=h["ari"])
    assert [c["titulo"] for c in r.json()["curadoria"]] == ["Notícia 2", "Notícia 1"]
    assert [s["titulo"] for s in cliente.get("/api/portal").json()["slides"]] == ["Notícia 2", "Notícia 1"]
    # Redator não configura o portal
    assert cliente.put("/api/portal/configuracao", json=portal["configuracao"], headers=h["rita"]).status_code == 403
    # Arquivo público com busca e detalhe com visualização e "leia também"
    pagina = cliente.get(f"{URL}/publicas", params={"busca": "notícia 3"}).json()
    assert pagina["total"] == 1
    detalhe = cliente.get(f"{URL}/publicas/{criadas[3]['slug']}").json()
    assert detalhe["titulo"] == "Notícia 3" and len(detalhe["leia_tambem"]) == 3
    assert cliente.get(detalhe["capa"]["400"]).status_code == 200
    # Arquivada sai do portal
    cliente.post(f"{URL}/{criadas[3]['id']}/arquivar", headers=h["ari"])
    assert cliente.get(f"{URL}/publicas/{criadas[3]['slug']}").status_code == 404


def test_atalhos_e_anexos(cliente, redacao):
    ids, h, _ = redacao
    r = cliente.post("/api/portal/atalhos", data={"titulo": "Outlook", "url": "https://outlook.office.com", "ativo": "true", "nova_aba": "true"},
                     files={"imagem": ("o.png", _imagem(600, 600), "image/png")}, headers=h["ari"])
    assert r.status_code == 201, r.text
    assert cliente.get(r.json()["imagem"]).status_code == 200
    assert cliente.post("/api/portal/atalhos", data={"titulo": "X", "url": "https://x"}, headers=h["rita"]).status_code == 403
    assert [a["titulo"] for a in cliente.get("/api/portal").json()["atalhos"]] == ["Outlook"]
    n = _nova(cliente, h["rita"])
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    r = cliente.post(f"{URL}/{n['id']}/anexos", files={"arquivo": ("edital.pdf", pdf, "application/pdf")}, headers=h["rita"])
    assert r.status_code == 200 and r.json()["anexos"][0]["nome"] == "edital.pdf"
    ruim = cliente.post(f"{URL}/{n['id']}/anexos", files={"arquivo": ("pagina.html", b"<script>", "text/html")}, headers=h["rita"])
    assert ruim.status_code == 400
