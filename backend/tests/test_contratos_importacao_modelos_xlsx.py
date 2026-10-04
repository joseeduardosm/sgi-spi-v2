# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a importação de checklists e formulários de avaliação por planilha XLSX.
"""Importação de checklist e formulário por XLSX: modelo, prévia, gravação (contrato e modelo global), erros e ACL."""

from io import BytesIO

from openpyxl import load_workbook

from tests.apoio_contratos import criar_contrato
from tests.conftest import cabecalho, criar_usuario

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GLOBAL = "/api/contratos/modelos/importacao-xlsx"


def preencher(conteudo: bytes, alteracoes: dict[str, dict[str, object]]) -> bytes:
    """Sobrescreve células do modelo gerado (`{"Aba": {"B4": valor}}`)."""
    livro = load_workbook(BytesIO(conteudo))
    for aba, celulas in alteracoes.items():
        for celula, valor in celulas.items():
            livro[aba][celula] = valor
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


def enviar(cliente, h, url: str, conteudo: bytes, nome: str = "planilha.xlsx"):
    """Envia a planilha como multipart (campo `arquivo`)."""
    return cliente.post(url, files={"arquivo": (nome, conteudo, XLSX)}, headers=h)


def modelo(cliente, h, url: str) -> bytes:
    """Baixa o modelo da planilha."""
    r = cliente.get(url, headers=h)
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"
    return r.content


def test_checklist_modelo_previa_e_importacao_no_contrato(cliente, admin):
    """O modelo baixado já é importável: a prévia não grava e a importação cria uma versão inativa."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/checklists/importacao-xlsx"
    planilha = modelo(cliente, admin, f"{base}/modelo")
    p = enviar(cliente, admin, f"{base}/previa", planilha).json()
    assert p["pode_importar"] and p["nome"] == "Checklist mensal padrão" and len(p["documentos"]) == 3
    assert p["documentos"][0]["com_validade"] is True and p["documentos"][2]["obrigatorio"] is False
    assert cliente.get(f"/api/contratos/{contrato['id']}/checklists", headers=admin).json() == []
    r = enviar(cliente, admin, base, planilha)
    assert r.status_code == 201, r.text
    versoes = r.json()
    assert len(versoes) == 1 and versoes[0]["ativo"] is False and [i["nome"] for i in versoes[0]["itens"]][0] == "Certidão negativa de débitos"


def test_formulario_modelo_previa_e_importacao_no_contrato(cliente, admin):
    """O formulário do modelo (3 notas, 3 faixas, 2 grupos) vira uma versão inativa com ids gerados."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/formularios/importacao-xlsx"
    planilha = modelo(cliente, admin, f"{base}/modelo")
    p = enviar(cliente, admin, f"{base}/previa", planilha).json()
    assert p["pode_importar"] and [g["nome"] for g in p["grupos"]] == ["Pessoal", "Materiais"]
    assert len(p["grupos"][0]["itens"]) == 2  # grupo em branco repete o de cima
    r = enviar(cliente, admin, base, planilha)
    assert r.status_code == 201, r.text
    definicao = r.json()[0]["definicao"]
    assert r.json()[0]["ativo"] is False and len(definicao["escala"]) == 3 and definicao["faixas"][2]["maximo"] is None
    assert all(i["id"] for g in definicao["grupos"] for i in g["itens"])


def test_modelos_globais_por_planilha(cliente, admin):
    """SuperRoot cria modelo global de checklist e de formulário pela planilha."""
    for tipo in ("checklist", "formulario"):
        planilha = modelo(cliente, admin, f"{GLOBAL}/{tipo}/modelo")
        assert enviar(cliente, admin, f"{GLOBAL}/{tipo}/previa", planilha).json()["pode_importar"]
        r = enviar(cliente, admin, f"{GLOBAL}/{tipo}", planilha)
        assert r.status_code == 201 and r.json()["tipo"] == tipo
    assert {m["tipo"] for m in cliente.get("/api/contratos/modelos", headers=admin).json()} == {"checklist", "formulario"}


def test_erros_do_checklist_apontam_linha_e_campo(cliente, admin):
    """Documento sem nome e Sim/Não inválido: erros por linha e nada é gravado."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/checklists/importacao-xlsx"
    ruim = preencher(modelo(cliente, admin, f"{base}/modelo"), {"Checklist": {"A7": None, "B7": "Obs", "C8": "talvez"}})
    erros = enviar(cliente, admin, f"{base}/previa", ruim).json()["erros"]
    assert {(e["linha"], e["campo"]) for e in erros} == {(7, "Documento"), (8, "Obrigatório")}
    r = enviar(cliente, admin, base, ruim)
    assert r.status_code == 400 and len(r.json()["erros"]) == 2
    assert cliente.get(f"/api/contratos/{contrato['id']}/checklists", headers=admin).json() == []


def test_erros_do_formulario(cliente, admin):
    """Pesos que não somam 100, escala repetida e peso inválido são apontados com a linha."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/formularios/importacao-xlsx"
    original = modelo(cliente, admin, f"{base}/modelo")
    pesos = enviar(cliente, admin, f"{base}/previa", preencher(original, {"Itens": {"D4": 40}})).json()
    assert not pesos["pode_importar"] and pesos["erros"][0]["linha"] == 4 and "100" in pesos["erros"][0]["mensagem"]
    escala = enviar(cliente, admin, f"{base}/previa", preencher(original, {"Escala": {"A5": 0}})).json()
    assert not escala["pode_importar"] and "crescente" in escala["erros"][0]["mensagem"]
    peso = enviar(cliente, admin, f"{base}/previa", preencher(original, {"Itens": {"D5": "abc"}})).json()
    assert [(e["linha"], e["campo"]) for e in peso["erros"]] == [(5, "Peso")]
    assert enviar(cliente, admin, base, preencher(original, {"Itens": {"D4": 40}})).status_code == 400
    assert cliente.get(f"/api/contratos/{contrato['id']}/formularios", headers=admin).json() == []


def test_aba_ausente_e_arquivo_invalido(cliente, admin):
    """Planilha sem a aba esperada gera erro; arquivo que não é .xlsx é recusado com 400."""
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/formularios/importacao-xlsx"
    checklist = modelo(cliente, admin, f"/api/contratos/{contrato['id']}/checklists/importacao-xlsx/modelo")
    assert not enviar(cliente, admin, f"{base}/previa", checklist).json()["pode_importar"]
    assert enviar(cliente, admin, f"{base}/previa", b"a;b", nome="x.csv").status_code == 400
    assert enviar(cliente, admin, f"{base}/previa", b"isto nao e planilha").status_code == 400


def test_acl_e_papel_da_importacao_de_modelos(cliente, admin):
    """Sem liberação em `importacao-modelos` o usuário recebe 403; modelos globais exigem SuperRoot."""
    contrato = criar_contrato(cliente, admin)
    criar_usuario("comum")
    liberado = criar_usuario("liberado")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Importação", "slug": "importacao-modelos"}, headers=admin).json()
    corpo = {"recurso_id": recurso["id"], "nivel": "MODIFICACAO", "usuarios_ids": [liberado], "setores_ids": []}
    assert cliente.post("/api/acl/regras", json=corpo, headers=admin).status_code == 201
    url = f"/api/contratos/{contrato['id']}/checklists/importacao-xlsx/modelo"
    r = cliente.get(url, headers=cabecalho(cliente, "comum"))
    assert r.status_code == 403 and r.json()["recurso"] == "importacao-modelos"
    # Liberado na ACL, mas sem papel SuperRoot: o modelo global continua negado
    assert cliente.get(f"{GLOBAL}/checklist/modelo", headers=cabecalho(cliente, "liberado")).status_code == 403
