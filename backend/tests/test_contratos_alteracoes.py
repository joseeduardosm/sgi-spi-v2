"""MVPs 5 a 7: prorrogação, reajuste e aditamento/supressão."""

from datetime import date

import pytest

from tests.apoio_contratos import PDF, criar_contrato, item, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


@pytest.fixture
def equipe(cliente, admin):
    gestora, fiscal = criar_usuario("gestora"), criar_usuario("fiscal")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal}, vigencia_maxima_meses=24)
    return contrato, cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")


# --- MVP 5: prorrogação ---------------------------------------------------------------------------

def test_prorrogar_so_com_prazo_e_termo_nao_gera_parecer(cliente, admin, equipe):
    contrato, gestora, _ = equipe
    rascunho = cliente.get(_url(contrato, "/prorrogacao"), headers=gestora).json()
    assert rascunho["meses_disponiveis"] == 12 and rascunho["nova_vigencia_inicio"] == "2027-01-01"
    assert cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 13}, headers=gestora).status_code == 400
    r = cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "repetir_inicial"}, headers=gestora)
    assert r.json()["nova_vigencia_fim"] == "2027-12-31" and r.json()["itens_sob_demanda"][0]["limite"] == "100.0000"
    assert cliente.post(_url(contrato, "/prorrogacao/parecer"), headers=gestora).status_code == 400

    r = cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10", "numero_termo": "01/2026"},
                     files={"termo": ("ta.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200, r.text
    prorrogacao = r.json()[0]
    assert prorrogacao["relatorio"] is None and prorrogacao["codigo_documento"] == 24 and prorrogacao["pode_desfazer"]
    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    assert detalhe["data_fim"] == "2027-12-31" and [v["sequencia"] for v in detalhe["vigencias"]] == [1, 2]
    assert any(m["tipo"] == "termo_aditivo" and m["rotulo"].startswith("TA nº 01/2026") for m in detalhe["marcos"])
    documentos = cliente.get(_url(contrato, "/documentos"), headers=gestora).json()
    assert documentos[-1]["codigo"] == 24 and documentos[-1]["anexado"] and documentos[-1]["nome_arquivo"] == "TERMO_ADITIVO_024_SPI_001_2026.pdf"

    # Data inicial bloqueada e vigência máxima esgotada
    assert cliente.get(_url(contrato, "/prorrogacao"), headers=gestora).json()["meses_disponiveis"] == 0

    # Desfazer
    r = cliente.delete(_url(contrato, f"/prorrogacoes/{prorrogacao['id']}"), headers=gestora)
    assert r.status_code == 200 and r.json() == []
    assert cliente.get(_url(contrato), headers=gestora).json()["data_fim"] == "2026-12-31"


def test_parecer_emite_pdf_e_edicao_apaga_ciencias(cliente, admin, equipe):
    contrato, gestora, fiscal = equipe
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 6, "parecer": "Favorável"}, headers=gestora)
    assert len(cliente.post(_url(contrato, "/prorrogacao/ciencia"), headers=fiscal).json()["ciencias"]) == 1
    r = cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 6, "parecer": "Favorável com ressalvas"}, headers=gestora)
    assert r.json()["ciencias"] == []
    cliente.post(_url(contrato, "/prorrogacao/ciencia"), headers=fiscal)
    assert cliente.post(_url(contrato, "/prorrogacao/parecer"), headers=gestora).json()["relatorio"] is not None
    r = cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10"}, files={"termo": ("ta.pdf", PDF)}, headers=gestora)
    relatorio = r.json()[0]["relatorio"]
    assert relatorio is not None
    assert cliente.get(_url(contrato, f"/prorrogacoes/arquivos/{relatorio['anexo_id']}"), headers=gestora).content[:5] == b"%PDF-"


def test_prorrogacao_limita_itens_sob_demanda_ao_original(cliente, admin, equipe):
    contrato, gestora, _ = equipe
    item_id = contrato["itens"][1]["id"]
    plano = [{"item_id": item_id, "limite": "150", "apontamentos": {}}]
    r = cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "manual", "plano_sob_demanda": plano}, headers=gestora)
    assert r.status_code == 400 and "aditamento" in r.json()["detalhe"]
    plano = [{"item_id": item_id, "limite": "40", "apontamentos": {"2027-01-01": "10"}}]
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "manual", "plano_sob_demanda": plano}, headers=gestora)
    cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10"}, files={"termo": ("ta.pdf", PDF)}, headers=gestora)
    previsao = cliente.get(_url(contrato, "/previsao"), headers=gestora).json()
    segunda = previsao["vigencias"][1]
    assert segunda["salva"] and segunda["itens_sob_demanda"][0]["limite"] == "40.0000" and segunda["itens_sob_demanda"][0]["saldo"] == "30.0000"
    # Valor global da vigência atual: contínuo 2 × 1000 × 12 + sob demanda 40 × 10,50
    assert cliente.get(_url(contrato), headers=gestora).json()["valor_global"] == "24420.00"


# --- MVP 6: reajuste ------------------------------------------------------------------------------

def test_reajuste_de_5_por_cento_mantem_competencias_medidas(cliente, admin, equipe):
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{janeiro['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in janeiro["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)

    painel = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-01-01"}, headers=gestora).json()
    reajuste = painel["em_andamento"]
    assert reajuste["competencias_recalculadas"] == 11
    assert cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-01-01"}, headers=gestora).status_code == 409
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    itens = [{"item_id": i["item_id"], "indice_percentual": "5"} for i in reajuste["itens"]]
    reajuste = cliente.put(f"{url}/memoria", json={"itens": itens}, headers=gestora).json()["em_andamento"]
    assert [i["valor_unitario_reajustado"] for i in reajuste["itens"]] == ["1050.00", "11.03"]
    # Os novos preços valem desde a referência, inclusive nos meses já medidos (a diferença vira competência complementar)
    assert reajuste["base_reajustada"] == "2100.00" and reajuste["valor_global_reajustado"] == "26303.00"
    assert cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).status_code == 400
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=gestora)
    memorias = cliente.post(f"{url}/memoria/arquivos", headers=gestora).json()["em_andamento"]["memorias"]
    assert len(memorias) == 1 and len(cliente.post(f"{url}/memoria/arquivos", headers=gestora).json()["em_andamento"]["memorias"]) == 1
    xlsx = cliente.get(f"{url}/arquivos/{memorias[0]['xlsx']['anexo_id']}", headers=gestora)
    assert xlsx.content[:2] == b"PK"
    painel = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).json()
    assert painel["em_andamento"] is None and painel["vigencias_disponiveis"] == []

    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    assert detalhe["itens"][0]["valor_unitario"] == "1050.00" and detalhe["valor_global"] == "26303.00"
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()["itens"][0]["valor_unitario"] == "1000.00"
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()["itens"][0]["valor_unitario"] == "1050.00"
    previsao = cliente.get(_url(contrato, "/previsao"), headers=gestora).json()
    assert previsao["meses"][1]["itens"][0]["valor_unitario"] == "1050.00"


# --- MVP 7: aditamento e supressão ------------------------------------------------------------------

def _alteracao(cliente, contrato, h, tipo, novas):
    painel = cliente.post(_url(contrato, "/alteracoes"), json={"tipo": tipo, "sequencia_vigencia": 1, "mes_efeito": "2026-01-01"}, headers=h).json()
    alteracao = painel["em_andamento"]
    url = _url(contrato, f"/alteracoes/{alteracao['id']}")
    itens = [{"item_id": i["item_id"], "quantidade_nova": novas.get(i["descricao"], i["quantidade_original"])} for i in alteracao["itens"]]
    assert cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=h).status_code == 400  # sem justificativa
    cliente.post(f"{url}/documentos/justificativa", files={"arquivo": ("j.pdf", PDF)}, headers=h)
    return url, itens


def test_acrescimo_de_30_por_cento_exige_autorizacao(cliente, admin, equipe):
    contrato, gestora, fiscal = equipe
    url, itens = _alteracao(cliente, contrato, gestora, "aditamento", {"Limpeza": "2.6"})
    r = cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=gestora).json()["em_andamento"]
    assert r["impacto_valor"] == "7200.00" and r["impacto_percentual"] == "28.74" and r["exige_autorizacao"]
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 400
    cliente.post(f"{url}/ciencia", headers=gestora)
    cliente.post(f"{url}/ciencia", headers=fiscal)
    assert cliente.post(f"{url}/memoria", headers=gestora).json()["em_andamento"]["memoria_pdf"] is not None
    cliente.post(f"{url}/documentos/de_acordo", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    assert cliente.post(f"{url}/consolidado", headers=gestora).json()["em_andamento"]["consolidado"] is not None
    cliente.post(f"{url}/documentos/termo", files={"arquivo": ("t.pdf", PDF)}, headers=gestora)
    r = cliente.post(f"{url}/concluir", headers=gestora)
    assert r.status_code == 400 and "Ordenador" in r.json()["detalhe"]
    cliente.post(f"{url}/documentos/autorizacao", files={"arquivo": ("a.pdf", PDF)}, headers=gestora)
    assert cliente.post(f"{url}/concluir", headers=gestora).status_code == 200
    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    assert detalhe["itens"][0]["quantidade_mensal"] == "2.6000" and detalhe["aditamento_acumulado_percentual"] == "28.74"


def test_supressao_abaixo_do_executado_e_bloqueada(cliente, admin, equipe):
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{janeiro['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in janeiro["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)

    url, itens = _alteracao(cliente, contrato, gestora, "supressao", {"Material": "5"})
    r = cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=gestora)
    assert r.status_code == 400 and "abaixo do já executado" in r.json()["detalhe"]
    itens[1]["quantidade_nova"] = "80"
    r = cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=gestora).json()["em_andamento"]
    assert r["impacto_valor"] == "-210.00" and not r["exige_autorizacao"]
    cliente.post(f"{url}/cancelar", headers=gestora)
    assert cliente.get(_url(contrato, "/alteracoes"), headers=gestora).json()["em_andamento"] is None


def test_contrato_com_um_item(cliente, admin):
    """Regressão: contrato só com item contínuo também calcula previsão e execução."""
    contrato = criar_contrato(cliente, admin, itens=[item()])
    assert cliente.get(_url(contrato, "/previsao"), headers=admin).json()["vigencias"][0]["possui_sob_demanda"] is False


# --- MVP 8: painel e relatórios --------------------------------------------------------------------

def test_painel_com_pendencias_alertas_e_execucao(cliente, admin, equipe, monkeypatch):
    monkeypatch.setattr("app.services.contratos.servico_painel.hoje", lambda: date(2026, 11, 1))
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: date(2026, 11, 1))
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: date(2026, 11, 1))
    contrato, gestora, fiscal = equipe
    painel = cliente.get("/api/contratos/painel", headers=gestora).json()
    assert painel["minhas_pendencias"][0]["tipo"] == "base_execucao"
    riscos = [r["tipo"] for g in painel["alertas"] for r in g["riscos"]]
    assert riscos == ["a_vencer_sem_prorrogacao"] and len(painel["alertas"]) == 1
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    painel = cliente.get("/api/contratos/painel", params={"exercicio": 2026}, headers=gestora).json()
    assert any(p["tipo"] == "medicao" and "01/2026" in p["descricao"] for p in painel["minhas_pendencias"])
    atrasos = [r for g in painel["alertas"] for r in g["riscos"] if r["tipo"] == "competencias_atrasadas"]
    assert len(atrasos) == 1  # um risco agregado por contrato, não um por competência
    assert painel["execucao"]["total_previsto"] == "24105.00" and painel["execucao"]["empenhado"] == "51000.00"
    assert painel["numeros"]["contratos_a_vencer"] == 1
    # O criador também recebe as pendências; filtro por empresa inexistente zera os números
    assert cliente.get("/api/contratos/painel", headers=admin).json()["minhas_pendencias"]
    vazio = cliente.get("/api/contratos/painel", params={"empresa_id": str(contrato["id"])}, headers=admin).json()
    assert vazio["numeros"]["contratos_ativos"] == 0 and vazio["alertas"] == []


def test_previsao_consolidada_com_cenarios(cliente, admin, equipe):
    contrato, gestora, _ = equipe
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12}, headers=gestora)
    parametros = {"exercicio": 2027, "formato": "xlsx", "cenario_prorrogacoes": "true"}
    assert cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params=parametros, headers=gestora).status_code == 403
    r = cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params=parametros, headers=admin)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    from io import BytesIO

    from openpyxl import load_workbook

    folha = load_workbook(BytesIO(r.content))["Resumo anual"]
    assert folha["C4"].value == 0 and folha["D4"].value == 24000 and folha["E4"].value == 24000
    pdf = cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params={**parametros, "formato": "pdf"}, headers=admin)
    assert pdf.content[:5] == b"%PDF-"


def test_aditamento_apos_reajuste_soma_ao_valor_global_e_contrato_completo_pode_ser_excluido(cliente, admin, equipe):
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{janeiro['id']}")
    cliente.put(f"{base}/medicao", json={"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in janeiro["itens"]],
                                         "notas_empenho_ids": notas}, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    for etapa, dados, arquivos in (
        ("nota-fiscal", {"numero": "1", "recebida_em": "2026-02-01", "prazo_pagamento_dias": "30", "origem_valor": "medicao"}, {"arquivo": ("n.pdf", PDF)}),
        ("cadin", {"possui_pendencia": "false"}, {"certidao": ("c.pdf", PDF)}),
    ):
        assert cliente.post(f"{base}/{etapa}", data=dados, files=arquivos, headers=gestora).status_code == 200
    for documento in cliente.get(base, headers=gestora).json()["documentos"]:
        cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    cliente.post(f"{base}/consolidado", headers=gestora)
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=gestora).json()["situacao"] == "concluida"

    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-02-01"}, headers=gestora).json()["em_andamento"]
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    cliente.put(f"{url}/memoria", json={"itens": [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]}, headers=gestora)
    cliente.post(f"{url}/evidencia", files={"arquivo": ("e.pdf", PDF)}, headers=gestora)
    cliente.post(f"{url}/memoria/arquivos", headers=gestora)
    cliente.post(f"{url}/concluir", files={"arquivo": ("a.pdf", PDF)}, headers=gestora)
    antes = cliente.get(_url(contrato), headers=gestora).json()["valor_global"]

    url, itens = _alteracao(cliente, contrato, gestora, "aditamento", {"Limpeza": "2.2"})
    impacto = cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=gestora).json()["em_andamento"]["impacto_valor"]
    cliente.post(f"{url}/ciencia", headers=gestora)
    cliente.post(f"{url}/ciencia", headers=fiscal)
    cliente.post(f"{url}/documentos/de_acordo", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    cliente.post(f"{url}/documentos/termo", files={"arquivo": ("t.pdf", PDF)}, headers=gestora)
    assert cliente.post(f"{url}/concluir", headers=gestora).status_code == 200
    depois = cliente.get(_url(contrato), headers=gestora).json()["valor_global"]
    assert float(depois) == round(float(antes) + float(impacto), 2)

    # Exclusão do contrato com execução, reajuste e aditamento (chaves estrangeiras verificadas)
    assert cliente.delete(_url(contrato), headers=admin).status_code == 204
    assert cliente.delete(f"/api/contratos/empresas/{contrato['empresa']['id']}", headers=admin).status_code == 204
