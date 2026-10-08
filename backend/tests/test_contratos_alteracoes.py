# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar prorrogação, reajuste, aditamento/supressão e o painel.
"""MVPs 5 a 7: prorrogação, reajuste e aditamento/supressão."""

from datetime import date
from decimal import Decimal

import pytest

from tests.apoio_contratos import PDF, conferir_retencao, criar_contrato, criar_empresa, item, juntar_nf, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url

# Data "de hoje" fixa nos testes
HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    """Congela a data de hoje nos serviços."""
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


@pytest.fixture
def equipe(cliente, admin):
    """Contrato (vigência máxima de 24 meses) com gestora e fiscal, e os cabeçalhos de cada um."""
    gestora, fiscal = criar_usuario("gestora"), criar_usuario("fiscal")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal}, vigencia_maxima_meses=24)
    return contrato, cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")


# --- MVP 5: prorrogação ---------------------------------------------------------------------------

def test_prorrogar_so_com_prazo_e_termo_nao_gera_parecer(cliente, admin, equipe):
    """Prorrogação sem parecer: prazo além do máximo recusado, termo vira documento 024, e o desfazer."""
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
    """Parecer gera PDF; editar o parecer apaga as ciências já registradas."""
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
    """Na prorrogação, o limite do sob demanda não passa do original; o plano vira a previsão da nova vigência."""
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
    """Reajuste de 5%: competências já medidas mantêm o preço; as demais e o cadastro recebem o novo."""
    # Mede e conclui janeiro antes de abrir o reajuste
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
    assert [i["valor_unitario_reajustado"] for i in reajuste["itens"]] == ["1050.0000", "11.0250"]  # 10,50 × 1,05 com 4 casas (antes arredondava para 11,03)
    # Os novos preços valem desde a referência, inclusive nos meses já medidos (a diferença vira competência complementar)
    assert reajuste["base_reajustada"] == "2100.00" and reajuste["valor_global_reajustado"] == "26302.50"  # sob demanda a 11,025 (4 casas)
    assert cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).status_code == 400
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=gestora)
    memorias = cliente.post(f"{url}/memoria/arquivos", headers=gestora).json()["em_andamento"]["memorias"]
    assert len(memorias) == 1 and len(cliente.post(f"{url}/memoria/arquivos", headers=gestora).json()["em_andamento"]["memorias"]) == 1
    xlsx = cliente.get(f"{url}/arquivos/{memorias[0]['xlsx']['anexo_id']}", headers=gestora)
    assert xlsx.content[:2] == b"PK"
    painel = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).json()
    assert painel["em_andamento"] is None and painel["vigencias_disponiveis"] == []

    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    assert detalhe["itens"][0]["valor_unitario"] == "1050.0000" and detalhe["valor_global"] == "26302.50"
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()["itens"][0]["valor_unitario"] == "1000.0000"
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()["itens"][0]["valor_unitario"] == "1050.0000"
    previsao = cliente.get(_url(contrato, "/previsao"), headers=gestora).json()
    assert previsao["meses"][1]["itens"][0]["valor_unitario"] == "1050.0000"


# --- MVP 7: aditamento e supressão ------------------------------------------------------------------

def _alteracao(cliente, contrato, h, tipo, novas):
    """Abre uma alteração, tenta salvar sem justificativa (400), anexa a justificativa e devolve (url, itens)."""
    # Nova quantidade: a informada para o item (pela descrição) ou a atual
    painel = cliente.post(_url(contrato, "/alteracoes"), json={"tipo": tipo, "sequencia_vigencia": 1, "mes_efeito": "2026-01-01"}, headers=h).json()
    alteracao = painel["em_andamento"]
    url = _url(contrato, f"/alteracoes/{alteracao['id']}")
    itens = [{"item_id": i["item_id"], "quantidade_nova": novas.get(i["descricao"], i["quantidade_original"])} for i in alteracao["itens"]]
    assert cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=h).status_code == 400  # sem justificativa
    cliente.post(f"{url}/documentos/justificativa", files={"arquivo": ("j.pdf", PDF)}, headers=h)
    return url, itens


def test_acrescimo_de_30_por_cento_exige_autorizacao(cliente, admin, equipe):
    """Aditamento de 28,74% (acima de 25%) só conclui com a autorização do Ordenador de Despesa."""
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
    """Supressão abaixo do já executado é recusada; o cancelamento encerra a alteração."""
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
    # Antes de gerar as competências: a pendência é completar a base; o risco é o vencimento próximo
    painel = cliente.get("/api/contratos/painel", headers=gestora).json()
    assert painel["minhas_pendencias"][0]["tipo"] == "base_execucao"
    riscos = [r["tipo"] for g in painel["alertas"] for r in g["riscos"]]
    assert riscos == ["a_vencer_sem_prorrogacao"] and len(painel["alertas"]) == 1
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    # Depois de gerar: pendências de medição e um risco de atraso agregado por contrato
    painel = cliente.get("/api/contratos/painel", params={"exercicio": 2026}, headers=gestora).json()
    # Competências de antes de 09/2026 foram "limpas" e não aparecem mais; a partir de 09/2026 seguem sendo cobradas
    medicoes = [p["descricao"] for p in painel["minhas_pendencias"] if p["tipo"] == "medicao"]
    assert medicoes and not any(f"0{mes}/2026" in d for d in medicoes for mes in range(1, 9))
    assert any("09/2026" in d for d in medicoes)
    atrasos = [r for g in painel["alertas"] for r in g["riscos"] if r["tipo"] == "competencias_atrasadas"]
    assert len(atrasos) == 1  # um risco agregado por contrato, não um por competência
    # Competências de antes de 09/2026 não geram alerta: a mais antiga em atraso é a de 09/2026
    assert "1 competência(s)" in atrasos[0]["descricao"] and "09/2026" in atrasos[0]["descricao"]
    assert painel["execucao"]["total_previsto"] == "24105.00" and painel["execucao"]["empenhado"] == "51000.00"
    assert painel["numeros"]["contratos_a_vencer"] == 1
    # O criador também recebe as pendências; filtro por empresa inexistente zera os números
    assert cliente.get("/api/contratos/painel", headers=admin).json()["minhas_pendencias"]
    vazio = cliente.get("/api/contratos/painel", params={"empresa_id": str(contrato["id"])}, headers=admin).json()
    assert vazio["numeros"]["contratos_ativos"] == 0 and vazio["alertas"] == []


def test_painel_de_vigencias_ordena_vigentes_pelo_vencimento(cliente, admin, equipe, monkeypatch):
    """Painel de vigências: só vigentes, do que vence primeiro ao último, com as vigências e o filtro de empresa."""
    monkeypatch.setattr("app.services.contratos.servico_painel.hoje", lambda: HOJE)
    contrato, gestora, _ = equipe
    # Contrato da equipe (01/2026 a 12/2026, máximo 24 meses) prorrogado por 12 meses: vai a 31/12/2027
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "repetir_inicial"}, headers=gestora)
    r = cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10", "numero_termo": "01/2026"},
                     files={"termo": ("ta.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200, r.text
    outra = criar_empresa(cliente, admin, base="44555666", razao="Outra Ltda")
    a_vencer = criar_contrato(cliente, admin, numero="002/2025", empresa_id=outra["id"], apelido="", data_inicio="2025-06-01")
    criar_contrato(cliente, admin, numero="003/2024", empresa_id=outra["id"], data_inicio="2024-01-01")  # encerrado
    quinze = criar_contrato(cliente, admin, numero="004/2026", empresa_id=outra["id"], data_inicio="2026-02-01", vigencia_inicial_meses=15)

    r = cliente.get("/api/contratos/painel/vigencias", headers=admin)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["hoje"] == "2026-03-15"
    assert [c["numero"] for c in p["contratos"]] == ["002/2025", "004/2026", "001/2026"]
    primeiro = p["contratos"][0]
    assert primeiro["contrato_id"] == a_vencer["id"] and primeiro["situacao"] == "a_vencer" and primeiro["rotulo"] == "Outra Ltda"
    assert (primeiro["data_fim"], primeiro["dias_restantes"], primeiro["meses_prorrogaveis"]) == ("2026-05-31", 77, 48)
    assert p["contratos"][1]["contrato_id"] == quinze["id"] and p["contratos"][1]["data_fim"] == "2027-04-30"
    prorrogado = p["contratos"][2]
    assert [(v["sequencia"], v["inicio"], v["fim"]) for v in prorrogado["vigencias"]] == [
        (1, "2026-01-01", "2026-12-31"), (2, "2027-01-01", "2027-12-31")]
    assert prorrogado["meses_prorrogaveis"] == 0 and prorrogado["data_limite_maxima"] == "2027-12-31"
    # Filtro por empresa (as opções do filtro continuam todas)
    filtrado = cliente.get("/api/contratos/painel/vigencias", params={"empresa_id": outra["id"]}, headers=admin).json()
    assert [c["numero"] for c in filtrado["contratos"]] == ["002/2025", "004/2026"] and len(filtrado["empresas"]) == 2
    # Sem ACL de leitura em contratos: 403
    criar_usuario("sem_acesso")
    assert cliente.get("/api/contratos/painel/vigencias", headers=cabecalho(cliente, "sem_acesso")).status_code == 403


def test_previsao_consolidada_com_cenarios(cliente, admin, equipe):
    """Exportação consolidada com o cenário de prorrogação; só o SuperRoot exporta."""
    contrato, gestora, _ = equipe
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12}, headers=gestora)
    parametros = {"exercicio": 2027, "formato": "xlsx", "cenario_prorrogacoes": "true"}
    assert cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params=parametros, headers=gestora).status_code == 403
    r = cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params=parametros, headers=admin)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    from io import BytesIO

    from openpyxl import load_workbook

    # C4 = previsão 2027 (0: o contrato acaba em 2026), D4 = cenário de prorrogação, E4 = total
    folha = load_workbook(BytesIO(r.content))["Resumo anual"]
    assert folha["C4"].value == 0 and folha["D4"].value == 24000 and folha["E4"].value == 24000
    pdf = cliente.get("/api/contratos/relatorios/previsao-orcamentaria", params={**parametros, "formato": "pdf"}, headers=admin)
    assert pdf.content[:5] == b"%PDF-"


def test_aditamento_apos_reajuste_soma_ao_valor_global_e_contrato_completo_pode_ser_excluido(cliente, admin, equipe):
    """Aditamento após reajuste soma o impacto ao valor global; contrato completo pode ser excluído."""
    # Janeiro inteiro, da medição à OB
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
    assert juntar_nf(cliente, base, gestora, "2105.00", recebida_em="2026-02-01").status_code == 200
    assert conferir_retencao(cliente, base, gestora).status_code == 200
    assert cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora).status_code == 200
    for documento in cliente.get(base, headers=gestora).json()["documentos"]:
        cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    cliente.post(f"{base}/consolidado", headers=gestora)
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=gestora).json()["situacao"] == "concluida"

    # Reajuste de 10% a partir de fevereiro
    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-02-01"}, headers=gestora).json()["em_andamento"]
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    cliente.put(f"{url}/memoria", json={"itens": [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]}, headers=gestora)
    cliente.post(f"{url}/evidencia", files={"arquivo": ("e.pdf", PDF)}, headers=gestora)
    cliente.post(f"{url}/memoria/arquivos", headers=gestora)
    cliente.post(f"{url}/concluir", files={"arquivo": ("a.pdf", PDF)}, headers=gestora)
    antes = cliente.get(_url(contrato), headers=gestora).json()["valor_global"]

    # Aditamento depois do reajuste
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


# --- Mês da virada: reajuste a partir de uma data e uma medição só --------------------------------------

def test_reajuste_a_partir_de_20_do_mes_gera_uma_competencia_com_dois_trechos(cliente, admin):
    """Prorrogação e reajuste em 20/01/2027: janeiro é UMA competência, cada item com uma linha por trecho, pagos pelos dias."""
    import uuid

    from app.core.banco import FabricaSessao
    from app.models.contratos import Contrato

    gestora = criar_usuario("gestora")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora}, data_inicio="2026-01-20", vigencia_maxima_meses=24)
    h = cabecalho(cliente, "gestora")
    _preparar_execucao(cliente, contrato, h)
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "repetir_inicial"}, headers=h)
    r = cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10"}, files={"termo": ("ta.pdf", PDF)}, headers=h)
    assert r.status_code == 200, r.text
    assert cliente.get(_url(contrato), headers=h).json()["vigencias"][1]["inicio"] == "2027-01-20"

    # Reajuste de 10% a partir de 20/01/2027 (início da 2ª vigência); data fora da vigência é recusada
    assert cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 2, "data_efeito": "2027-01-19"}, headers=h).status_code == 400
    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 2, "data_efeito": "2027-01-20"}, headers=h).json()["em_andamento"]
    assert reajuste["data_efeito"] == "2027-01-20" and reajuste["mes_referencia"] == "2027-01-01"
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    itens = [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]
    assert cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h).status_code == 200
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    cliente.post(f"{url}/memoria/arquivos", headers=h)
    assert cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h).status_code == 200

    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    with FabricaSessao() as sessao:
        sessao.get(Contrato, uuid.UUID(contrato["id"])).liberar_todas_competencias = True
        sessao.commit()
    # Uma competência só em janeiro/2027, sem "1ª/2ª parte"
    lista = cliente.get(_url(contrato, "/execucao"), headers=h).json()
    janeiros = [c for g in lista["grupos"] for c in g["competencias"] if c["competencia"] == "2027-01-01"]
    assert len(janeiros) == 1 and janeiros[0]["identificador"] == "2027-01"
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2027-01"), headers=h).json()
    continuos = [i for i in janeiro["itens"] if i["tipo"] == "continuo"]
    assert [(i["segmento"], i["valor_unitario"], i["periodo_rotulo"]) for i in continuos] == [
        (1, "1000.0000", "01/01 a 19/01/2027 · preço anterior"), (2, "1100.0000", "20/01 a 31/01/2027 · preço reajustado"),
    ]
    # Pelos dias (19/30 e 11/30 do mês): 2 postos × fator
    assert [i["quantidade_prevista"] for i in continuos] == ["1.2667", "0.7333"]
    # Total previsto do item contínuo = 1,2667 × 1000 + 0,7333 × 1100
    assert abs(sum(float(i["quantidade_prevista"]) * float(i["valor_unitario"]) for i in continuos) - 2073.3) < 0.1
    # Medição única com os dois trechos: o total é a soma dos trechos
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=h).json()]
    base = _url(contrato, f"/competencias/{janeiro['id']}")
    corpo = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in janeiro["itens"]], "notas_empenho_ids": notas}
    assert cliente.put(f"{base}/medicao", json=corpo, headers=h).status_code == 200
    medida = cliente.get(base, headers=h).json()
    assert Decimal(medida["total_medido"]) == sum((Decimal(i["subtotal"]) for i in medida["itens"]), Decimal(0))


def test_trimestral_prorrogado_tem_uma_competencia_so_atravessando_as_vigencias(cliente, admin):
    """Contrato trimestral prorrogado em 20/01/2027: a competência jan–mar/2027 é uma só, atravessa as vigências e leva dois trechos."""
    import uuid

    from app.core.banco import FabricaSessao
    from app.models.contratos import Contrato

    gestora = criar_usuario("gestora")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora}, data_inicio="2026-01-20", vigencia_maxima_meses=24, periodicidade_meses=3)
    h = cabecalho(cliente, "gestora")
    _preparar_execucao(cliente, contrato, h)
    cliente.put(_url(contrato, "/prorrogacao"), json={"meses": 12, "regra_sob_demanda": "repetir_inicial"}, headers=h)
    r = cliente.post(_url(contrato, "/prorrogacao/registrar"), data={"assinada_em": "2026-12-10"}, files={"termo": ("ta.pdf", PDF)}, headers=h)
    assert r.status_code == 200, r.text
    assert cliente.get(_url(contrato), headers=h).json()["vigencias"][1]["inicio"] == "2027-01-20"

    # Reajuste de 10% a partir de 20/01/2027 (início da 2ª vigência); data fora da vigência é recusada
    assert cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 2, "data_efeito": "2027-01-19"}, headers=h).status_code == 400
    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 2, "data_efeito": "2027-01-20"}, headers=h).json()["em_andamento"]
    assert reajuste["data_efeito"] == "2027-01-20" and reajuste["mes_referencia"] == "2027-01-01"
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    itens = [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]
    assert cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h).status_code == 200
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    cliente.post(f"{url}/memoria/arquivos", headers=h)
    assert cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h).status_code == 200

    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    with FabricaSessao() as sessao:
        sessao.get(Contrato, uuid.UUID(contrato["id"])).liberar_todas_competencias = True
        sessao.commit()
    # Uma competência só para jan–mar/2027 (identificador do 1º mês), sem corte na virada da vigência
    lista = cliente.get(_url(contrato, "/execucao"), headers=h).json()
    trimestres = [c for g in lista["grupos"] for c in g["competencias"] if c["competencia"] == "2027-01-01"]
    assert len(trimestres) == 1 and trimestres[0]["identificador"] == "2027-01"
    assert (trimestres[0]["periodo_inicio"], trimestres[0]["periodo_fim"]) == ("2027-01-01", "2027-03-31")
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2027-01"), headers=h).json()
    continuos = [i for i in competencia["itens"] if i["tipo"] == "continuo"]
    assert [(i["segmento"], i["valor_unitario"], i["periodo_rotulo"]) for i in continuos] == [
        (1, "1000.0000", "01/01 a 19/01/2027 · preço anterior"), (2, "1100.0000", "20/01 a 31/03/2027 · preço reajustado"),
    ]
    # 2 postos: 19/30 do mês de janeiro no 1º trecho; 11/30 de janeiro + fevereiro e março inteiros no 2º
    assert [i["quantidade_prevista"] for i in continuos] == ["1.2667", "4.7333"]


def test_alertas_a_partir_de_do_contrato_empurra_o_corte_para_depois(cliente, admin, equipe, monkeypatch):
    """"Desconsiderar alertas a partir de": vale a maior entre a data do contrato e o corte global; sem a data, só o global."""
    import uuid
    from datetime import date as data

    from app.core.banco import FabricaSessao
    from app.models.contratos import Contrato

    for modulo in ("servico_painel", "servico_contratos", "servico_competencias"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: data(2026, 11, 1))
    contrato, gestora, _ = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)

    def tipos():
        painel = cliente.get("/api/contratos/painel", headers=gestora).json()
        return {r["tipo"] for g in painel["alertas"] for r in g["riscos"]}, [p["descricao"] for p in painel["minhas_pendencias"] if p["tipo"] == "medicao"]

    riscos, medicoes = tipos()
    assert "competencias_atrasadas" in riscos and any("09/2026" in d for d in medicoes)  # só o corte global (09/2026)
    with FabricaSessao() as sessao:
        sessao.get(Contrato, uuid.UUID(contrato["id"])).alertas_a_partir_de = data(2026, 11, 1)
        sessao.commit()
    riscos, medicoes = tipos()
    assert "competencias_atrasadas" not in riscos and not any("09/2026" in d or "10/2026" in d for d in medicoes)
    # Data anterior ao corte global não "devolve" os alertas antigos: continua valendo o global
    with FabricaSessao() as sessao:
        sessao.get(Contrato, uuid.UUID(contrato["id"])).alertas_a_partir_de = data(2025, 1, 1)
        sessao.commit()
    assert not any(f"0{m}/2026" in d for d in tipos()[1] for m in range(1, 9))
