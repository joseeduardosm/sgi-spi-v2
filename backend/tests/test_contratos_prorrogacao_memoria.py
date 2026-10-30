# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o fluxo novo da prorrogação: meses quebrados (pro rata × integral), memória de cálculo e checklist.
"""Prorrogação: memória de cálculo da nova vigência, escolha dos meses quebrados e checklist "a partir de…".

Cenário: contrato de 15/01/2026 por 12 meses (fim 14/01/2027), prorrogado por 12 meses: nova vigência de 15/01/2027
a 14/01/2028. Um item contínuo (2 postos a R$ 1.000,00) e um sob demanda (R$ 10,50). Janeiro/2027 (15 a 31: 16 dias
comerciais) e janeiro/2028 (1 a 14: 14 dias) são os meses quebrados.
"""

import io
from datetime import date
from decimal import Decimal

from pypdf import PdfReader

from tests.apoio_contratos import PDF, criar_contrato, criar_empresa

ITENS_MODELO = [{"nome": "Certidão de regularidade"}, {"nome": "Parecer técnico", "obrigatorio": False}]


def _contrato(cliente, admin) -> tuple[dict, str]:
    contrato = criar_contrato(cliente, admin, empresa_id=criar_empresa(cliente, admin)["id"], data_inicio=date(2026, 1, 15).isoformat())
    return contrato, f"/api/contratos/{contrato['id']}"


def _salvar(cliente, base, h, **extras):
    corpo = {"meses": 12, "regra_sob_demanda": "repetir_inicial", **extras}
    r = cliente.put(f"{base}/prorrogacao", json=corpo, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_memoria_com_meses_quebrados_totais_por_ano_e_sob_demanda(cliente, admin):
    contrato, base = _contrato(cliente, admin)
    material = contrato["itens"][1]["id"]
    plano = [{"item_id": material, "limite": "100", "apontamentos": {"2027-03-01": "4"}}]
    p = _salvar(cliente, base, admin, plano_sob_demanda=plano)
    m = p["memoria"]

    # Dois meses quebrados, sem escolha ainda: a memória não sai e o registro também não
    assert [q["competencia"] for q in m["meses_quebrados"]] == ["01/2027", "01/2028"] and m["precisa_escolher"] is True
    assert [q["dias"] for q in m["meses_quebrados"]] == [16, 14]
    assert Decimal(m["meses_quebrados"][0]["pro_rata"]) == Decimal("1066.67") and Decimal(m["meses_quebrados"][0]["integral"]) == Decimal("2000.00")
    assert Decimal(m["total_pro_rata"]) == Decimal("24042.00") and Decimal(m["total_integral"]) == Decimal("26042.00")
    assert cliente.post(f"{base}/prorrogacao/memoria/arquivos", headers=admin).status_code == 400

    # Pro rata: totais por ano e da vigência; o sob demanda planejado entra em março/2027
    p = _salvar(cliente, base, admin, plano_sob_demanda=plano, calculo_mes_quebrado="pro_rata")
    m = p["memoria"]
    marco = next(x for x in m["meses"] if x["competencia"] == "03/2027")
    assert Decimal(marco["sob_demanda"]) == Decimal("42.00") and Decimal(marco["total"]) == Decimal("2042.00")
    assert [(a["ano"], Decimal(a["total"])) for a in m["totais_por_ano"]] == [(2027, Decimal("23108.67")), (2028, Decimal("933.33"))]
    assert Decimal(m["total"]) == Decimal("24042.00") and m["precisa_escolher"] is False

    # Gera a memória (PDF com capa e totais); sem mudança, não gera outra versão
    r = cliente.post(f"{base}/prorrogacao/memoria/arquivos", headers=admin)
    assert r.status_code == 200, r.text
    versoes = r.json()["memorias"]
    assert len(versoes) == 1 and r.json()["memoria_atualizada"] is True
    texto = " ".join(pg.extract_text() for pg in PdfReader(io.BytesIO(cliente.get(f"{base}/prorrogacoes/arquivos/{versoes[0]['pdf']['anexo_id']}", headers=admin).content)).pages)
    assert "Prorrogação de 15/01/2027 a 14/01/2028" in texto and "Total para 2027" in texto and "Total da nova vigência" in texto
    assert len(cliente.post(f"{base}/prorrogacao/memoria/arquivos", headers=admin).json()["memorias"]) == 1

    # Integral muda o total; a memória gerada fica desatualizada até gerar de novo
    p = _salvar(cliente, base, admin, plano_sob_demanda=plano, calculo_mes_quebrado="integral")
    assert Decimal(p["memoria"]["total"]) == Decimal("26042.00") and p["memoria_atualizada"] is False


def test_valor_da_prorrogacao_nas_minutas_nao_e_zero(cliente, admin):
    """Regressão: no rascunho a nova vigência não existe no contrato e o valor saía zerado."""
    _, base = _contrato(cliente, admin)
    _salvar(cliente, base, admin, calculo_mes_quebrado="pro_rata")
    campos = {c["nome"]: c for c in cliente.get(f"{base}/prorrogacao/minutas", headers=admin).json()["campos"]}
    assert campos["valorprorrogacao"]["calculado"] == "R$ 24.000,00"
    assert "para o exercício de 2027" in campos["valoresporexercicio"]["calculado"] and "para o exercício de 2028" in campos["valoresporexercicio"]["calculado"]


def test_checklist_padrao_trava_o_registro_e_aceita_documentos_incluidos(cliente, admin):
    r = cliente.post("/api/contratos/modelos", json={"tipo": "checklist_prorrogacao", "nome": "Padrão", "itens": ITENS_MODELO}, headers=admin)
    assert r.status_code == 201, r.text
    # Um só ativo por vez
    assert cliente.post("/api/contratos/modelos", json={"tipo": "checklist_prorrogacao", "nome": "Outro", "itens": ITENS_MODELO}, headers=admin).status_code == 409

    _, base = _contrato(cliente, admin)
    p = _salvar(cliente, base, admin, calculo_mes_quebrado="integral")
    assert [(d["nome"], d["obrigatorio"]) for d in p["checklist"]] == [("Certidão de regularidade", True), ("Parecer técnico", False)]
    assert p["obrigatorios_pendentes"] == 1

    # Inclui um documento fora do modelo (sempre opcional) e exclui; o do modelo não sai
    r = cliente.post(f"{base}/prorrogacao/checklist/incluir", data={"nome": "Ofício da área", "descricao": "Pedido de prorrogação"}, files={"arquivo": ("of.pdf", PDF)}, headers=admin)
    assert r.status_code == 200, r.text
    oficio = r.json()["checklist"][-1]
    assert oficio["incluido_no_processo"] is True and oficio["obrigatorio"] is False and oficio["arquivo"] is not None
    certidao = r.json()["checklist"][0]
    assert cliente.delete(f"{base}/prorrogacao/checklist/{certidao['id']}", headers=admin).status_code == 400
    assert cliente.delete(f"{base}/prorrogacao/checklist/{oficio['id']}", headers=admin).status_code == 200

    # Registrar exige a memória gerada e o obrigatório anexado
    registrar = lambda: cliente.post(f"{base}/prorrogacao/registrar", data={"assinada_em": "2026-12-10"}, files={"termo": ("ta.pdf", PDF)}, headers=admin)  # noqa: E731
    assert "memória de cálculo" in registrar().json()["detalhe"]
    assert cliente.post(f"{base}/prorrogacao/memoria/arquivos", headers=admin).status_code == 200
    assert "Certidão de regularidade" in registrar().json()["detalhe"]
    assert cliente.post(f"{base}/prorrogacao/checklist/{certidao['id']}", files={"arquivo": ("cert.pdf", PDF)}, headers=admin).status_code == 200
    r = registrar()
    assert r.status_code == 200, r.text
    assert r.json()[0]["data_inicio"] == "2027-01-15" and r.json()[0]["data_fim"] == "2028-01-14"
