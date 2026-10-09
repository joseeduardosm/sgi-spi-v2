# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a portaria de designação do contrato: solicitação, aceite, devolução, minuta, publicação e Art. 5º.
"""Portarias contratuais (`/api/contratos/{id}/portarias`): fluxo completo com reserva no Protocolo."""

import io
import zipfile

import pytest

from app.core.banco import FabricaSessao
from app.models.rh import DadosFuncionais
from tests.apoio_contratos import PDF, criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario

PROTOCOLO = "/api/protocolo"
MASCARA = (
    '<p style="text-align: center"><strong>Portaria SPI SSGC nº #numeroportaria, de #anoportaria</strong></p>'
    "<p>Contrato #numerodocontrato, #contratada, CNPJ #cnpjcontratada, objeto #objetodocontrato, SEI #nroprocessosei.</p>"
    "<p>I – #nomegestor – RS: #rsgestor – Gestor</p><p>II – #nomegestorsuplente – RS: #rsgestorsuplente – Suplente</p>"
    "<p>III – #nomefiscal – RS: #rsfiscal – Fiscal</p>"
)
REVOGACAO = "<p>Fica revogada a Portaria #nomedocumento nº #numeroportariaanterior, de #diaportariaanterior de #mesportariaanterior de #anoportariaanterior.</p>"
ASSINATURA = '<p style="text-align: center">#nomeautoridade</p>'


def _modelo(cliente, h, variante, html, **extras):
    return cliente.post("/api/contratos/modelos", json={"tipo": "portaria", "nome": f"Portaria {variante}", "variante": variante, "html": html, **extras}, headers=h)


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com gestor e fiscal técnico (RS cadastrado só do gestor), faixa de Portaria e uma autoridade que aceita."""
    gestor = criar_usuario("gestora", nome_completo="Gabriela Gestora")
    fiscal = criar_usuario("fiscal", nome_completo="Fábio Fiscal")
    chefe = criar_usuario("chefe", nome_completo="Carlos Chefe")
    with FabricaSessao() as sessao:
        sessao.add(DadosFuncionais(usuario_id=gestor, rs_pv="12345"))
        sessao.commit()
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestor, "fiscal_tecnico": fiscal})
    tipo = cliente.post(f"{PROTOCOLO}/tipos", json={"nome": "Portaria"}, headers=admin).json()
    assert cliente.post(f"{PROTOCOLO}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 9}, headers=admin).status_code == 201
    assert _modelo(cliente, admin, "sem_anterior", MASCARA + ASSINATURA).status_code == 201
    assert _modelo(cliente, admin, "com_anterior", MASCARA + REVOGACAO + ASSINATURA).status_code == 201
    autoridade = cliente.post("/api/portarias/autoridades", json={
        "sigla": "SPI SSGC", "nome": "Carlos Chefe", "cargo": "Subsecretário de Gestão", "setor": "Subsecretaria de Gestão e Controle", "usuario_id": chefe,
    }, headers=admin)
    assert autoridade.status_code == 201, autoridade.text
    return {"contrato": contrato, "autoridade": autoridade.json()[0], "fiscal": fiscal, "chefe_id": chefe, "chefe": cabecalho(cliente, "chefe")}


def _url(cenario, *partes):
    return "/".join([f"/api/contratos/{cenario['contrato']['id']}/portarias", *partes])


def _solicitar(cliente, admin, cenario):
    r = cliente.post(_url(cenario), json={"autoridade_id": cenario["autoridade"]["id"]}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["portarias"][0]


def test_solicitar_reserva_numero_no_protocolo_e_bloqueia_segunda(cliente, admin, cenario):
    portaria = _solicitar(cliente, admin, cenario)
    assert portaria["titulo"] == "Portaria SPI SSGC nº 001, de 2026" and portaria["status"] == "aguardando_aceite"
    assert [p["papel"] for p in portaria["equipe"]] == ["gestor", "fiscal_tecnico"]
    assert portaria["anterior"] is None
    # O RS do fiscal falta: aparece como pendência (sem expor o RS)
    assert any("Fábio Fiscal" in p for p in portaria["pendencias"])
    numeros = cliente.get(f"{PROTOCOLO}/contratos/{cenario['contrato']['id']}", headers=admin).json()
    assert len(numeros) == 1
    segunda = cliente.post(_url(cenario), json={"autoridade_id": cenario["autoridade"]["id"]}, headers=admin)
    assert segunda.status_code == 409


def test_aceite_so_da_autoridade_e_exige_rs(cliente, admin, cenario):
    portaria = _solicitar(cliente, admin, cenario)
    # Sem RS do fiscal: nem a autoridade aceita
    r = cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cenario["chefe"])
    assert r.status_code == 400 and "Fábio Fiscal" in r.json()["detalhe"]
    with FabricaSessao() as sessao:
        sessao.add(DadosFuncionais(usuario_id=cenario["fiscal"], rs_pv="67890"))
        sessao.commit()
    # Quem não é a autoridade não aceita
    outro = criar_usuario("outro", nome_completo="Outro Servidor")
    restringir_contratos(cliente, admin, {outro: "MODIFICACAO", cenario["chefe_id"]: "LEITURA"})
    h_outro = cabecalho(cliente, "outro")
    assert cliente.post(_url(cenario, portaria["id"], "aceite"), headers=h_outro).status_code == 403
    r = cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cenario["chefe"])
    assert r.status_code == 200, r.text
    aceita = r.json()["portarias"][0]
    assert aceita["status"] == "aceita" and aceita["aceita_por_nome"] == "Carlos Chefe" and outro


def test_devolver_e_reenviar(cliente, admin, cenario):
    portaria = _solicitar(cliente, admin, cenario)
    assert cliente.post(_url(cenario, portaria["id"], "devolucao"), json={"motivo": "Ajustar fiscal"}, headers=cenario["chefe"]).json()["portarias"][0]["status"] == "devolvida"
    r = cliente.post(_url(cenario, portaria["id"], "reenviar"), headers=admin)
    assert r.json()["portarias"][0]["status"] == "aguardando_aceite"


def test_minuta_word_e_pdf_com_marca_dagua(cliente, admin, cenario):
    portaria = _solicitar(cliente, admin, cenario)
    word = cliente.get(_url(cenario, portaria["id"], "minuta") + "?formato=docx", headers=admin)
    assert word.status_code == 200 and "MINUTA_PORTARIA_001_2026" in word.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(word.content)) as z:
        assert "MINUTA" in z.read("word/header1.xml").decode()
        corpo = z.read("word/document.xml").decode()
    assert "Portaria SPI SSGC nº 001, de 2026" in corpo and "Gabriela Gestora" in corpo and "RS: 12345" in corpo and "Serviços contínuos de limpeza predial" in corpo and "#" not in corpo
    pdf = cliente.get(_url(cenario, portaria["id"], "minuta") + "?formato=pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_publicar_anexa_no_protocolo_e_no_documento_16_e_proxima_cita_anterior(cliente, admin, cenario):
    with FabricaSessao() as sessao:
        sessao.add(DadosFuncionais(usuario_id=cenario["fiscal"], rs_pv="67890"))
        sessao.commit()
    portaria = _solicitar(cliente, admin, cenario)
    # Ainda não aceita: não publica
    assert cliente.post(_url(cenario, portaria["id"], "publicacao"), files={"arquivo": ("p.pdf", PDF, "application/pdf")}, headers=admin).status_code == 409
    assert cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cenario["chefe"]).status_code == 200
    r = cliente.post(_url(cenario, portaria["id"], "publicacao"), files={"arquivo": ("p.pdf", PDF, "application/pdf")}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["portarias"][0]["status"] == "publicada"
    numeros = cliente.get(f"{PROTOCOLO}/contratos/{cenario['contrato']['id']}", headers=admin).json()
    assert numeros[0]["estado"] == "utilizado"
    documentos = cliente.get(f"/api/contratos/{cenario['contrato']['id']}/documentos", headers=admin).json()
    assert next(d for d in documentos if d["codigo"] == 16)["anexado"] is True
    # Nova portaria: o Art. 5º cita a anterior
    nova = _solicitar(cliente, admin, cenario)
    assert nova["numero"] == 2 and nova["anterior"].startswith("Portaria SPI SSGC nº 001, de ")
    docx = cliente.get(_url(cenario, nova["id"], "minuta") + "?formato=docx", headers=admin).content
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        assert "Fica revogada a Portaria SPI SSGC nº 001, de" in z.read("word/document.xml").decode()


def test_cancelar_libera_o_numero(cliente, admin, cenario):
    portaria = _solicitar(cliente, admin, cenario)
    r = cliente.post(_url(cenario, portaria["id"], "cancelamento"), json={"motivo": "Pedido errado"}, headers=admin)
    assert r.status_code == 200 and r.json()["portarias"][0]["status"] == "cancelada" and r.json()["em_andamento"] is False
    assert _solicitar(cliente, admin, cenario)["numero"] == 1


def test_sem_faixa_do_ano_ou_sem_gestor(cliente, admin):
    contrato = criar_contrato(cliente, admin)
    autoridade = cliente.post("/api/portarias/autoridades", json={"sigla": "X", "nome": "A", "cargo": "C", "setor": "S"}, headers=admin).json()[0]
    r = cliente.post(f"/api/contratos/{contrato['id']}/portarias", json={"autoridade_id": autoridade["id"]}, headers=admin)
    assert r.status_code == 400 and "faixa" in r.json()["detalhe"]


def test_autoridades_so_com_controle_total(cliente, admin):
    restringir_contratos(cliente, admin, {criar_usuario("leitor", nome_completo="Leitor"): "MODIFICACAO"})
    h = cabecalho(cliente, "leitor")
    assert cliente.post("/api/portarias/autoridades", json={"sigla": "X", "nome": "A", "cargo": "C", "setor": "S"}, headers=h).status_code == 403


def test_mascara_rejeita_placeholder_fora_da_lista(cliente, admin):
    for html in ("<p>Nº #015#</p>", "<p>#naoexiste</p>", "<p>Valor # solto</p>"):
        r = _modelo(cliente, admin, "sem_anterior", html)
        assert r.status_code == 400 and "Placeholders não permitidos" in r.json()["detalhe"]
    # A máscara sem portaria anterior não aceita os placeholders da anterior
    assert _modelo(cliente, admin, "sem_anterior", REVOGACAO).status_code == 400
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO).status_code == 201
    # Só uma máscara ativa por variante
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO).status_code == 409
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO, ativo=False).status_code == 201


def test_mascara_permissao_controle_total_so_para_portaria(cliente, admin):
    chefe = criar_usuario("admincontratos", nome_completo="Admin Contratos")
    restringir_contratos(cliente, admin, {chefe: "CONTROLE_TOTAL"})
    h = cabecalho(cliente, "admincontratos")
    assert _modelo(cliente, h, "sem_anterior", MASCARA).status_code == 201
    checklist = {"tipo": "checklist", "nome": "X", "itens": [{"nome": "Doc"}]}
    assert cliente.post("/api/contratos/modelos", json=checklist, headers=h).status_code == 403
    assert cliente.post("/api/contratos/modelos", json=checklist, headers=admin).status_code == 201


def test_solicitar_sem_mascara_ativa(cliente, admin):
    contrato = criar_contrato(cliente, admin, equipe={"gestor": criar_usuario("g2", nome_completo="G Dois")})
    tipo = cliente.post(f"{PROTOCOLO}/tipos", json={"nome": "Portaria"}, headers=admin).json()
    cliente.post(f"{PROTOCOLO}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 9}, headers=admin)
    aut = cliente.post("/api/portarias/autoridades", json={"sigla": "X", "nome": "A", "cargo": "C", "setor": "S"}, headers=admin).json()[0]
    r = cliente.post(f"/api/contratos/{contrato['id']}/portarias", json={"autoridade_id": aut["id"]}, headers=admin)
    assert r.status_code == 400 and "máscara" in r.json()["detalhe"]


def test_linha_de_pessoa_vazia_some_e_incisos_sao_renumerados():
    from app.services.contratos import portaria_mascara as m
    html = "<p>I – #nomegestor – RS: #rsgestor</p><p>II – #nomegestorsuplente – RS: #rsgestorsuplente</p><p>III – #nomefiscal – RS: #rsfiscal</p>"
    saida = m.preencher(html, {"nomegestor": "Ana", "rsgestor": "1", "nomegestorsuplente": "", "rsgestorsuplente": "", "nomefiscal": "Beto & Cia", "rsfiscal": "3"})
    assert "Suplente" not in saida and "II – Beto &amp; Cia" in saida and "III" not in saida
