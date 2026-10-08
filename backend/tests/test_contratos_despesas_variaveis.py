# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as despesas variáveis da medição: marca por item, subtotais, documentos na nota fiscal e PDFs.
"""Despesas variáveis: item marcado na medição, Subtotal - Medição / Despesas Variáveis / Total, documentos obrigatórios na etapa da nota fiscal."""

from decimal import Decimal

import pytest

from tests.apoio_contratos import criar_contrato, juntar_nf
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url
from tests.test_contratos_retencao import _ambiente  # noqa: F401 — fixture (data fixa e SMTP simulado)


@pytest.fixture
def medido(cliente, admin):
    """Competência 01/2026 com a medição concluída e o 2º item marcado como despesa variável; devolve (base, detalhe, headers)."""
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva", email="gestora@sp.gov.br")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza", email="fiscal@sp.gov.br")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    g, f = cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")
    _preparar_execucao(cliente, contrato, g)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=g)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=g).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=g).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"], "despesa_variavel": n == 1} for n, i in enumerate(competencia["itens"])]
    assert cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=g).status_code == 200
    cliente.post(f"{base}/medicao/ciencia", headers=g)
    cliente.post(f"{base}/medicao/ciencia", headers=f)
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=g)
    assert r.status_code == 200, r.text
    return base, r.json(), g


def test_subtotais_separam_a_medicao_das_despesas_variaveis(medido):
    _, detalhe, _ = medido
    marcados = [i for i in detalhe["itens"] if i["despesa_variavel"]]
    assert len(marcados) == 1 and detalhe["tem_despesas_variaveis"] is True
    assert Decimal(detalhe["subtotal_despesas_variaveis"]) == Decimal(marcados[0]["subtotal"]) > 0
    assert Decimal(detalhe["subtotal_medicao"]) + Decimal(detalhe["subtotal_despesas_variaveis"]) == Decimal(detalhe["total_medido"])
    # A medição das despesas variáveis sai em PDF à parte
    assert detalhe["memorias"][-1]["arquivo_despesas"]["nome"].startswith("medicao-despesas-variaveis-")


def test_nota_fiscal_exige_nota_e_documento_de_despesa_com_a_soma_certa(cliente, medido):
    base, detalhe, g = medido
    esperado = detalhe["subtotal_despesas_variaveis"]
    # Sem documento de despesa: recusado
    r = juntar_nf(cliente, base, g, "2105.00", "123")
    assert r.status_code == 400 and "despesas variáveis" in r.json()["detalhe"]
    # Soma diferente do Subtotal - Despesas Variáveis: recusado
    r = juntar_nf(cliente, base, g, "2105.00", "123", despesas=(("recibo", "1.00"),))
    assert r.status_code == 400 and "precisa ser igual" in r.json()["detalhe"]
    # Vários documentos somando o subtotal: aceito; só a NF vai para a retenção
    metade = (Decimal(esperado) / 2).quantize(Decimal("0.01"))
    r = juntar_nf(cliente, base, g, "2105.00", "123", despesas=(("nota_debito", str(metade)), ("recibo", str(Decimal(esperado) - metade))))
    assert r.status_code == 200, r.text
    novo = r.json()
    assert novo["etapa_atual"] == "retencao" and len(novo["notas_fiscais"]) == 1
    assert [d["tipo"] for d in novo["despesas_variaveis"]] == ["nota_debito", "recibo"] and novo["despesas_variaveis"][0]["arquivo"]["nome"] == "despesa1.pdf"
    # O débito nas NEs cobre a nota fiscal mais os documentos de despesa
    assert Decimal(novo["valor_a_pagar"]) == Decimal("2105.00") + Decimal(esperado)


def test_sem_item_marcado_nao_aceita_documentos_de_despesa(cliente, admin):
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva", email="gestora@sp.gov.br")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza", email="fiscal@sp.gov.br")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    g, f = cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")
    _preparar_execucao(cliente, contrato, g)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=g)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=g).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=g).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]]
    cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=g)
    cliente.post(f"{base}/medicao/ciencia", headers=g)
    cliente.post(f"{base}/medicao/ciencia", headers=f)
    assert cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=g).status_code == 200
    assert juntar_nf(cliente, base, g, "2105.00", "123", despesas=(("recibo", "10.00"),)).status_code == 400
    r = juntar_nf(cliente, base, g, "2105.00", "123")
    assert r.status_code == 200 and r.json()["tem_despesas_variaveis"] is False and r.json()["despesas_variaveis"] == []


def test_consolidado_traz_a_medicao_das_despesas_variaveis_e_os_documentos_depois_da_nota_fiscal(cliente, medido):
    from io import BytesIO

    from pypdf import PdfReader

    from tests.apoio_contratos import PDF, conferir_retencao

    base, detalhe, g = medido
    assert juntar_nf(cliente, base, g, "2105.00", "123", despesas=(("recibo", detalhe["subtotal_despesas_variaveis"]),)).status_code == 200
    assert conferir_retencao(cliente, base, g).status_code == 200
    assert cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=g).status_code == 200
    for doc in cliente.get(base, headers=g).json()["documentos"]:
        assert cliente.post(f"{base}/checklist/{doc['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=g).status_code == 200
    r = cliente.post(f"{base}/consolidado", headers=g)
    assert r.status_code == 200, r.text
    consolidado = r.json()["consolidado"]
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(cliente.get(f"{base}/arquivos/{consolidado['anexo_id']}", headers=g).content)).pages[:1])
    ordem = [texto.index(t) for t in ("Memória de cálculo da medição", "Nota fiscal 123", "Medição dos itens de despesas variáveis", "Recibo 1", "Retenção de tributos")]
    assert ordem == sorted(ordem)
