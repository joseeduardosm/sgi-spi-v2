# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o checklist do Parecer Referencial: conferências automáticas, respostas, aviso jurídico, planilha e fotografia no registro.
"""Prorrogação: enquadramento no Parecer Referencial NLC nº 1/2026 (37 itens)."""

import io
from datetime import date

from openpyxl import load_workbook

from app.services.contratos.catalogo_parecer_referencial import ITENS
from tests.apoio_contratos import criar_contrato, criar_empresa, dados_contrato, definir_parametros, preparar_registro_prorrogacao

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _itens(leitura: dict) -> dict[int, dict]:
    return {i["numero"]: i for g in leitura["grupos"] for i in g["itens"]}


def test_catalogo_tem_37_itens_em_nove_grupos_com_linhas_unicas():
    assert len(ITENS) == 37 and len({i.numero for i in ITENS}) == 37 and len({i.linha for i in ITENS}) == 37
    assert len({i.grupo for i in ITENS}) == 9


def test_conferencias_automaticas_com_a_conta(cliente, admin):
    ano = date.today().year
    contrato = criar_contrato(cliente, admin, data_inicio=date(ano, 1, 1).isoformat(), vigencia_inicial_meses=12, vigencia_maxima_meses=120)
    base = f"/api/contratos/{contrato['id']}/prorrogacao"
    leitura = cliente.get(f"{base}/enquadramento", headers=admin).json()
    assert leitura["total"] == 37 and len(leitura["grupos"]) == 9
    itens = _itens(leitura)
    # Sem prazo escolhido, prazo e 10 anos ficam pendentes; vigência em curso e parecer válido conferem sozinhos
    assert itens[5]["automatica"] is None and itens[14]["efetivo"] == ""
    assert itens[3]["efetivo"] == "sim" and itens[8]["efetivo"] == "sim"
    # Garantia não exigida e contrato sem modalidade: garantia "não se aplica", dispensa pendente
    assert itens[27]["efetivo"] == "na" and itens[29]["efetivo"] == ""

    cliente.put(base, json={"meses": 24}, headers=admin)
    itens = _itens(cliente.get(f"{base}/enquadramento", headers=admin).json())
    assert itens[5]["efetivo"] == "nao" and "24 mês" in itens[5]["automatica"]["explicacao"]
    assert itens[14]["efetivo"] == "sim" and "= 36 mês" in itens[14]["automatica"]["explicacao"]
    cliente.put(base, json={"meses": 12}, headers=admin)
    assert _itens(cliente.get(f"{base}/enquadramento", headers=admin).json())[5]["efetivo"] == "sim"


def test_dez_anos_vigencia_expirada_e_validade_do_parecer(cliente, admin):
    contrato = criar_contrato(cliente, admin, data_inicio="2020-01-01", vigencia_inicial_meses=60, vigencia_maxima_meses=120)
    base = f"/api/contratos/{contrato['id']}/prorrogacao"
    cliente.put(base, json={"meses": 60}, headers=admin)
    leitura = cliente.get(f"{base}/enquadramento", headers=admin).json()
    itens = _itens(leitura)
    assert itens[14]["efetivo"] == "sim"           # 60 + 60 = 120
    assert itens[3]["efetivo"] == "nao"             # vigência de 2020 a 2024 já terminou
    assert leitura["precisa_analise_juridica"] and any(m.startswith("Item 3:") for m in leitura["motivos"])
    definir_parametros(parecer_referencial_vigencia_ate=date(2020, 1, 1))
    assert _itens(cliente.get(f"{base}/enquadramento", headers=admin).json())[8]["efetivo"] == "nao"


def test_respostas_da_equipe_valem_mais_e_marcam_contestacao(cliente, admin):
    contrato = criar_contrato(cliente, admin, data_inicio="2020-01-01", vigencia_inicial_meses=60)
    base = f"/api/contratos/{contrato['id']}/prorrogacao"
    r = cliente.put(f"{base}/enquadramento", json={"respostas": {"3": {"resposta": "sim", "doc": "doc. nº 99, p. 2", "obs": "assinado antes"}, "10": {"resposta": "sim"}}}, headers=admin)
    assert r.status_code == 200, r.text
    itens = _itens(r.json())
    assert itens[3]["efetivo"] == "sim" and itens[3]["contestado"] is True and itens[3]["doc"] == "doc. nº 99, p. 2"
    assert itens[10]["efetivo"] == "sim" and itens[10]["contestado"] is False
    assert r.json()["atendidos"] >= 2 and r.json()["pendentes"] + r.json()["atendidos"] + r.json()["nao_atendidos"] == 37
    # Item "não" liga o aviso jurídico; item desconhecido é recusado
    r = cliente.put(f"{base}/enquadramento", json={"respostas": {"12": {"resposta": "nao"}}}, headers=admin)
    assert r.json()["precisa_analise_juridica"] is True
    assert cliente.put(f"{base}/enquadramento", json={"respostas": {"38": {"resposta": "sim"}}}, headers=admin).status_code == 400
    assert cliente.put(f"{base}/enquadramento", json={"respostas": {"1": {"resposta": "talvez"}}}, headers=admin).status_code == 422


def test_planilha_no_formato_do_modelo_6(cliente, admin):
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}/prorrogacao"
    cliente.put(f"{base}/enquadramento", json={"respostas": {"1": {"resposta": "sim", "doc": "doc. nº 5"}, "12": {"resposta": "nao", "obs": "sem interesse escrito"}}}, headers=admin)
    r = cliente.get(f"{base}/enquadramento/planilha", headers=admin)
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"] and "checklist-parecer-referencial" in r.headers["content-disposition"]
    folha = load_workbook(io.BytesIO(r.content)).active
    assert folha["C8"].value == "Sim" and folha["D8"].value == "doc. nº 5"
    assert folha["C39"].value == "Não" and "sem interesse escrito" in folha["D39"].value
    assert "análise da Consultoria Jurídica" in folha["B1"].value


def test_registro_guarda_a_fotografia_e_o_aviso_no_historico(cliente, admin):
    empresa = criar_empresa(cliente, admin)
    contrato = criar_contrato(cliente, admin, empresa_id=empresa["id"], data_inicio=date(date.today().year, 1, 1).isoformat())
    base = f"/api/contratos/{contrato['id']}/prorrogacao"
    cliente.put(f"{base}/enquadramento", json={"respostas": {"12": {"resposta": "nao"}}}, headers=admin)
    cliente.put(base, json={"meses": 12}, headers=admin)
    preparar_registro_prorrogacao(cliente, f"/api/contratos/{contrato['id']}", admin)
    r = cliente.post(f"{base}/registrar", data={"assinada_em": date.today().isoformat()}, files={"termo": ("ta.pdf", PDF)}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()[0]["precisa_analise_juridica"] is True
    assert cliente.get(f"/api/contratos/{contrato['id']}/prorrogacoes", headers=admin).json()[0]["precisa_analise_juridica"] is True
