# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o download em XLSX do contrato, do checklist e do formulário de avaliação.
"""Exportação para XLSX: planilha preenchida, reimportável, e acesso por ACL."""

from io import BytesIO

from openpyxl import load_workbook

from tests.apoio_contratos import criar_contrato
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_importacao_modelos_xlsx import enviar, modelo


def baixar(cliente, h, url: str):
    r = cliente.get(url, headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats") and "attachment" in r.headers["content-disposition"]
    return r.content


def test_checklist_exportado_volta_pela_importacao(cliente, admin):
    """O checklist baixado traz os documentos preenchidos e pode ser importado em outro contrato."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/checklists"
    enviar(cliente, admin, f"{base}/importacao-xlsx", modelo(cliente, admin, f"{base}/importacao-xlsx/modelo"))
    versao = cliente.get(base, headers=admin).json()[0]
    planilha = baixar(cliente, admin, f"{base}/{versao['id']}/xlsx")
    folha = load_workbook(BytesIO(planilha))["Checklist"]
    assert folha["B4"].value == versao["nome"] and folha["A7"].value == "Certidão negativa de débitos" and folha["C9"].value == "Não"
    previa = enviar(cliente, admin, f"{base}/importacao-xlsx/previa", planilha).json()
    assert previa["pode_importar"] and [d["nome"] for d in previa["documentos"]] == [i["nome"] for i in versao["itens"]]


def test_formulario_exportado_volta_pela_importacao(cliente, admin):
    """O formulário baixado mantém escala, faixas e grupos, e passa na prévia da importação."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/formularios"
    enviar(cliente, admin, f"{base}/importacao-xlsx", modelo(cliente, admin, f"{base}/importacao-xlsx/modelo"))
    versao = cliente.get(base, headers=admin).json()[0]
    planilha = baixar(cliente, admin, f"{base}/{versao['id']}/xlsx")
    livro = load_workbook(BytesIO(planilha))
    assert livro["Formulário"]["B4"].value == versao["nome"] and livro["Itens"]["A4"].value == "Pessoal" and livro["Itens"]["A5"].value is None
    previa = enviar(cliente, admin, f"{base}/importacao-xlsx/previa", planilha).json()
    assert previa["pode_importar"] and [g["nome"] for g in previa["grupos"]] == ["Pessoal", "Materiais"]
    assert [f["percentual"] for f in previa["faixas"]] == ["70", "90", "100"]


def test_contrato_exportado_traz_dados_e_itens(cliente, admin):
    """A planilha do contrato sai com cabeçalho e itens preenchidos, sem as linhas de legenda do modelo."""
    contrato = criar_contrato(cliente, admin)
    planilha = baixar(cliente, admin, f"/api/contratos/{contrato['id']}/exportacao-xlsx")
    folha = load_workbook(BytesIO(planilha)).worksheets[0]
    assert folha["C2"].value == contrato["numero"] and folha["C11"].value == contrato["apelido"]
    assert folha["C12"].value.date().isoformat() == contrato["data_inicio"]
    assert folha["C15"].value in ("Mensal", "Bimestral", "Trimestral", "Semestral", "Anual")
    assert folha["A30"].value == contrato["itens"][0]["descricao"] and folha["B30"].value in ("Contínuo", "Sob demanda")
    assert folha["A30"].value and folha.max_row >= 30 and folha["C30"].value in ("Pró-rata", "Sempre Integral")


def test_exportacao_inexistente_e_acl(cliente, admin):
    """Id desconhecido dá 404 e quem não tem ACL de leitura em contratos não baixa nada."""
    contrato = criar_contrato(cliente, admin)
    zero = "00000000-0000-0000-0000-000000000000"
    for url in (f"/api/contratos/{zero}/exportacao-xlsx", f"/api/contratos/{contrato['id']}/checklists/{zero}/xlsx",
                f"/api/contratos/{contrato['id']}/formularios/{zero}/xlsx"):
        assert cliente.get(url, headers=admin).status_code == 404
    assert cliente.get(f"/api/contratos/{contrato['id']}/exportacao-xlsx").status_code == 401
