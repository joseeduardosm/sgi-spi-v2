# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar previsão, Notas de Empenho, checklists e as etapas da execução.
"""MVPs 2 a 4: previsão, Notas de Empenho, checklists, competências (etapas 1 a 7), avaliação e reabertura."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.contratos import calculos
from tests.apoio_contratos import PDF, conferir_retencao, criar_contrato, juntar_nf, restringir_contratos
from tests.conftest import cabecalho, criar_usuario

# Data "de hoje" fixa nos testes: janeiro e fevereiro de 2026 já acabaram; março está em curso
HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    """Congela a data de hoje nos serviços (os resultados não dependem do dia em que o teste roda)."""
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


@pytest.fixture
def equipe(cliente, admin):
    """Contrato com gestora e fiscal (ACL MODIFICACAO) e os cabeçalhos de cada um."""
    gestora, fiscal = criar_usuario("gestora"), criar_usuario("fiscal")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    return contrato, cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")


def _url(contrato: dict, caminho: str = "") -> str:
    """URL da API do contrato, com um caminho opcional no fim."""
    return f"/api/contratos/{contrato['id']}{caminho}"


def _preparar_execucao(cliente, contrato, h, apontamentos=None):
    """Cumpre os pré-requisitos da execução: previsão salva, duas NEs e checklist ativo."""
    sob_demanda = contrato["itens"][1]["id"]
    grade = apontamentos if apontamentos is not None else [{"item_id": sob_demanda, "competencia": "2026-01-01", "quantidade": "10"}]
    assert cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": grade}, headers=h).status_code == 200
    for numero, valor in (("2026NE00001", "1000.00"), ("2026NE00002", "50000.00")):
        assert cliente.post(_url(contrato, "/notas-empenho"), json={"numero": numero, "valor_original": valor}, headers=h).status_code == 201
    r = cliente.post(_url(contrato, "/checklists"), json={"nome": "Mensal", "itens": [{"nome": "Folha de pagamento"}, {"nome": "FGTS"}]}, headers=h)
    checklist_id = r.json()[0]["id"]
    assert cliente.post(_url(contrato, f"/checklists/{checklist_id}/ativar"), headers=h).status_code == 200


# --- Cálculos ------------------------------------------------------------------------------------

def test_pro_rata_30_360_e_periodos_por_mes_civil():
    """30/360 (15/01 a 31/01 = 16 dias), meses parciais e períodos bimestrais por mês civil."""
    assert calculos.dias_comerciais(date(2026, 1, 15), date(2026, 1, 31)) == 16
    assert calculos.dias_comerciais(date(2026, 2, 1), date(2026, 2, 28)) == 30
    vigencia = calculos.Vigencia(1, date(2026, 1, 15), date(2027, 1, 14))
    meses = calculos.meses_da_vigencia(vigencia)
    assert len(meses) == 13 and meses[0].fator == Decimal("0.53333333") and meses[-1].fator == Decimal("0.46666667")
    bimestral = calculos.periodos_de_execucao([vigencia], 2)
    assert [(p.inicio, p.fim) for p in bimestral[:2]] == [(date(2026, 1, 15), date(2026, 2, 28)), (date(2026, 3, 1), date(2026, 4, 30))]
    quantidade, fator = calculos.quantidade_prevista_continua(Decimal(2), True, bimestral[0].meses)
    assert fator == Decimal("1.53333333") and quantidade == Decimal("3.0667")
    assert calculos.quantidade_prevista_continua(Decimal(2), False, bimestral[0].meses)[0] == Decimal(4)


# --- MVP 2: previsão e NEs -------------------------------------------------------------------

def test_previsao_sob_demanda_com_saldo_e_selo(cliente, admin, equipe):
    """Previsão sob demanda: saldo negativo recusado, selo após salvar e só o SuperRoot altera depois."""
    contrato, gestora, _ = equipe
    sob_demanda = contrato["itens"][1]["id"]
    previsao = cliente.get(_url(contrato, "/previsao"), headers=gestora).json()
    assert len(previsao["meses"]) == 12 and previsao["total_previsto"] == "24000.00"
    assert previsao["vigencias"][0]["itens_sob_demanda"][0]["saldo"] == "100.0000"

    excesso = [{"item_id": sob_demanda, "competencia": "2026-01-01", "quantidade": "60"}, {"item_id": sob_demanda, "competencia": "2026-02-20", "quantidade": "41"}]
    r = cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": excesso}, headers=gestora)
    assert r.status_code == 400 and "saldo negativo" in r.json()["detalhe"]

    grade = [{"item_id": sob_demanda, "competencia": "2026-01-01", "quantidade": "10"}, {"item_id": sob_demanda, "competencia": "2026-02-01", "quantidade": "5"}]
    salva = cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": grade}, headers=gestora).json()
    vigencia = salva["vigencias"][0]
    assert vigencia["salva"] and vigencia["itens_sob_demanda"][0]["saldo"] == "85.0000" and not vigencia["pode_editar"]
    assert salva["meses"][0]["valor"] == "2105.00" and salva["total_previsto"] == "24157.50"

    # Selada: usuário comum não altera; SuperRoot pode reduzir
    assert cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": grade[:1]}, headers=gestora).status_code == 400
    assert cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": grade[:1]}, headers=admin).status_code == 200
    planilha = cliente.get(_url(contrato, "/previsao/1/xlsx"), headers=gestora)
    assert planilha.status_code == 200 and planilha.content[:2] == b"PK"


def test_notas_de_empenho(cliente, admin, equipe):
    """NEs: número único (sem diferenciar maiúsculas), valor > 0, alteração, exclusão e relatório do SuperRoot."""
    contrato, gestora, _ = equipe
    r = cliente.post(_url(contrato, "/notas-empenho"), json={"numero": "2026NE1", "valor_original": "100.00"}, headers=gestora)
    assert r.status_code == 201 and r.json()[0]["saldo"] == "100.00" and r.json()[0]["faixa"] == "verde"
    assert cliente.post(_url(contrato, "/notas-empenho"), json={"numero": "2026ne1", "valor_original": "5"}, headers=gestora).status_code == 409
    assert cliente.post(_url(contrato, "/notas-empenho"), json={"numero": "X", "valor_original": "0"}, headers=gestora).status_code == 422
    nota_id = r.json()[0]["id"]
    assert cliente.put(_url(contrato, f"/notas-empenho/{nota_id}"), json={"numero": "2026NE1", "valor_original": "200"}, headers=gestora).status_code == 200
    assert cliente.delete(_url(contrato, f"/notas-empenho/{nota_id}"), headers=gestora).status_code == 204
    relatorio = cliente.get("/api/contratos/relatorios/notas-empenho", params={"formato": "pdf"}, headers=admin)
    assert relatorio.status_code == 200 and relatorio.content[:5] == b"%PDF-"
    assert cliente.get("/api/contratos/relatorios/notas-empenho", headers=gestora).status_code == 403


# --- MVP 3: execução ponta a ponta -------------------------------------------------------------

def test_requisitos_e_geracao_das_competencias(cliente, admin, equipe):
    """Pré-requisitos, geração idempotente das competências e bloqueio dos itens depois da geração."""
    # Sem previsão, NEs e checklist, faltam três pré-requisitos
    contrato, gestora, _ = equipe
    painel = cliente.get(_url(contrato, "/execucao"), headers=gestora).json()
    assert not painel["requisitos"]["prontos"] and len(painel["requisitos"]["pendencias"]) == 3
    r = cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    assert r.status_code == 400 and "Complete a base do contrato" in r.json()["detalhe"]

    _preparar_execucao(cliente, contrato, gestora)
    painel = cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora).json()
    competencias = painel["grupos"][0]["competencias"]
    assert len(competencias) == 12
    assert [c["situacao"] for c in competencias[:4]] == ["disponivel", "disponivel", "pendente", "pendente"]
    # Idempotente
    assert len(cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora).json()["grupos"][0]["competencias"]) == 12

    # Itens bloqueados para quem não é SuperRoot
    # Tenta alterar o preço de um item depois da geração: só o SuperRoot pode
    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    dados = {k: detalhe[k] for k in ("apelido", "objeto", "data_inicio", "vigencia_inicial_meses", "vigencia_maxima_meses", "periodicidade_meses",
                                     "mes_reajuste", "sei_gestao_numero", "sei_gestao_link", "sei_execucao_numero", "sei_execucao_link", "versao")}
    dados |= {"numero": detalhe["numero"], "empresa_id": detalhe["empresa"]["id"], "equipe": {"gestor": detalhe["equipe"][0]["usuario_id"],
              "fiscal_tecnico": detalhe["equipe"][1]["usuario_id"]}}
    dados["itens"] = [{k: i[k] for k in ("id", "descricao", "tipo", "calcula_pro_rata", "codigo_classe", "codigo_natureza_despesa", "codigo_siafisico",
                                         "codigo_catmat_catser", "quantidade_mensal", "valor_unitario")} for i in detalhe["itens"]]
    dados["itens"][1]["quantidade_total"] = "100"
    dados["itens"][0]["valor_unitario"] = "999.00"
    r = cliente.put(_url(contrato), json=dados, headers=gestora)
    assert r.status_code == 400 and "SuperRoot" in r.json()["detalhe"]


def test_competencia_da_medicao_ate_a_ordem_bancaria(cliente, admin, equipe):
    """Fluxo completo de uma competência (etapas 1, 3, 4, 5, 6 e 7) e a reabertura com estorno."""
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = {n["numero"]: n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    ordem_notas = [notas["2026NE00001"], notas["2026NE00002"]]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    assert competencia["etapas"] == ["medicao", "nota_fiscal", "retencao", "cadin", "checklist", "consolidado", "ordem_bancaria", "concluida"]
    assert [i["quantidade_prevista"] for i in competencia["itens"]] == ["2.0000", "10.0000"]

    # 1 Medição
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]], "notas_empenho_ids": ordem_notas}
    r = cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    assert r.status_code == 200 and r.json()["total_medido"] == "2105.00" and r.json()["situacao"] == "em_andamento"
    assert cliente.post(f"{base}/medicao/ciencia", headers=gestora).status_code == 200
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": ordem_notas}, headers=gestora)
    assert r.status_code == 400 and "2 ciências" in r.json()["detalhe"]
    assert cliente.post(f"{base}/medicao/ciencia", headers=admin).status_code == 400  # SuperRoot fora da equipe
    assert len(cliente.post(f"{base}/medicao/ciencia", headers=fiscal).json()["ciencias"]) == 2
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": ordem_notas}, headers=fiscal)
    assert r.status_code == 200, r.text
    detalhe = r.json()
    assert detalhe["etapa_atual"] == "nota_fiscal" and detalhe["memorias"][0]["versao"] == 1
    memoria = cliente.get(f"{base}/arquivos/{detalhe['memorias'][0]['arquivo']['anexo_id']}", headers=gestora)
    assert memoria.content[:5] == b"%PDF-"
    assert cliente.get(_url(contrato), headers=gestora).json()["itens"][1]["quantidade_executada"] == "10.0000"

    # 3 Nota fiscal: PDF + XML; número e valor vêm do XML
    sem_xml = cliente.post(f"{base}/nota-fiscal", data={"recebida_em": "2026-02-05", "prazo_pagamento_dias": "30"},
                           files={"arquivo": ("nf.pdf", PDF, "application/pdf")}, headers=gestora)
    assert sem_xml.status_code == 400 and "XML" in sem_xml.json()["detalhe"]
    r = juntar_nf(cliente, base, gestora, "2105.00", "123")
    assert r.status_code == 200, r.text
    detalhe = r.json()
    assert detalhe["nota_fiscal"]["numero"] == "123" and detalhe["nota_fiscal"]["valor_bruto"] == "2105.00"
    assert detalhe["vencimento_pagamento"] == "2026-03-07" and detalhe["etapa_atual"] == "retencao"

    # 4 Retenção de tributos: soma acima do bruto e discriminação não conferida são recusadas
    assert conferir_retencao(cliente, base, gestora, {"ir": "3000"}).status_code == 400
    assert conferir_retencao(cliente, base, gestora, {"ir": "31.58"}, discriminacao=False).status_code == 400
    r = conferir_retencao(cliente, base, gestora, {"ir": "31.58"})
    assert r.status_code == 200, r.text
    detalhe = r.json()
    assert detalhe["nota_fiscal"]["valor_liquido"] == "2073.42" and detalhe["etapa_atual"] == "cadin"
    assert detalhe["retencao"]["por_nome"] and detalhe["retencao"]["pdf"]

    # 4 CADIN: com pendência continua aberta; sem pendência conclui
    r = cliente.post(f"{base}/cadin", data={"possui_pendencia": "true"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora)
    assert r.status_code == 400
    r = cliente.post(f"{base}/cadin", data={"possui_pendencia": "true", "pendencia": "Débito", "texto_notificacao": "Prezados"},
                     files={"certidao": ("c.pdf", PDF), "email": ("e.pdf", PDF)}, headers=gestora)
    assert r.json()["etapa_atual"] == "cadin"
    r = cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c2.pdf", PDF)}, headers=gestora)
    assert r.json()["etapa_atual"] == "checklist" and len(r.json()["consultas_cadin"]) == 2

    # 5 Checklist
    for documento in r.json()["documentos"]:
        r = cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    assert r.json()["etapa_atual"] == "consolidado"

    # 6 Consolidado e 7 OB
    r = cliente.post(f"{base}/consolidado", headers=gestora)
    assert r.status_code == 200, r.text
    assert r.json()["etapa_atual"] == "ordem_bancaria"
    consolidado = cliente.get(f"{base}/arquivos/{r.json()['consolidado']['anexo_id']}", headers=gestora)
    assert consolidado.content[:5] == b"%PDF-"
    r = cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200 and r.json()["situacao"] == "concluida"
    saldos = {n["numero"]: (n["saldo"], len(n["movimentos"])) for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    assert saldos == {"2026NE00001": ("0.00", 1), "2026NE00002": ("48895.00", 1)}

    # Reabertura (SuperRoot ou gestor): o fiscal não pode; a gestora reabre e o débito vira estorno no extrato
    r = cliente.post(f"{base}/reabrir", json={"etapa": "consolidado", "justificativa": "OB errada"}, headers=fiscal)
    assert r.status_code == 403
    r = cliente.post(f"{base}/reabrir", json={"etapa": "consolidado", "justificativa": "OB errada"}, headers=gestora)
    assert r.status_code == 200 and r.json()["etapa_atual"] == "consolidado"
    notas_depois = cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()
    assert all(n["saldo"] == n["valor_original"] for n in notas_depois)
    extrato = [m["tipo"] for n in notas_depois for m in n["movimentos"]]
    assert extrato.count("pagamento") == 2 and extrato.count("estorno") == 2


def test_nota_de_empenho_sem_saldo_nao_serve_para_a_medicao(cliente, admin, equipe):
    """NE sem saldo suficiente é recusada na medição; competência futura fica pendente."""
    contrato, gestora, _ = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = {n["numero"]: n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]],
               "notas_empenho_ids": [notas["2026NE00001"]]}
    r = cliente.put(_url(contrato, f"/competencias/{competencia['id']}/medicao"), json=medicao, headers=gestora)
    assert r.status_code == 400 and "saldo suficiente" in r.json()["detalhe"]
    futura = cliente.get(_url(contrato, "/competencias/identificador/2026-04"), headers=gestora).json()
    assert futura["situacao"] == "pendente" and not futura["liberada"]


# --- MVP 4: avaliação ---------------------------------------------------------------------------

# Formulário de avaliação usado nos testes: escala 0/5/10 e três faixas de liberação
FORMULARIO = {
    "nome": "Qualidade",
    "definicao": {
        "escala": [{"valor": "0", "legenda": "Ruim"}, {"valor": "5", "legenda": "Regular"}, {"valor": "10", "legenda": "Ótimo"}],
        "faixas": [{"minimo": "0", "maximo": "6.99", "percentual": "70"}, {"minimo": "7", "maximo": "9.99", "percentual": "90"},
                   {"minimo": "10", "percentual": "100"}],
        "grupos": [{"nome": "Execução", "itens": [{"nome": "Pontualidade", "peso": "50"}, {"nome": "Limpeza", "peso": "50"}]}],
    },
}


def test_avaliacao_libera_pagamento_pela_faixa(cliente, admin, equipe):
    """Etapa 2: justificativas, nota final, % liberado, ateste, PDF e uma única reconsideração."""
    # Formulário com pesos que não somam 100% é recusado
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    ruim = {**FORMULARIO, "definicao": {**FORMULARIO["definicao"], "grupos": [{"nome": "G", "itens": [{"nome": "A", "peso": "60"}]}]}}
    assert cliente.post(_url(contrato, "/formularios"), json=ruim, headers=gestora).status_code == 422
    formularios = cliente.post(_url(contrato, "/formularios"), json=FORMULARIO, headers=gestora).json()
    cliente.post(_url(contrato, f"/formularios/{formularios[0]['id']}/ativar"), headers=gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    assert "avaliacao" in competencia["etapas"]
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    assert cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora).json()["etapa_atual"] == "avaliacao"

    itens = [i["id"] for g in competencia["avaliacao"]["definicao"]["grupos"] for i in g["itens"]]
    sem_justificativa = {"respostas": [{"item_id": itens[0], "nota": "5"}, {"item_id": itens[1], "nota": "10"}]}
    assert cliente.put(f"{base}/avaliacao/inicial", json=sem_justificativa, headers=fiscal).status_code == 400
    inicial = {"respostas": [{"item_id": itens[0], "nota": "5", "justificativa": "Atrasos"}, {"item_id": itens[1], "nota": "10"}]}
    assert cliente.put(f"{base}/avaliacao/inicial", json=inicial, headers=fiscal).status_code == 200
    gestor = {"respostas": [{"item_id": itens[0], "nota": "5", "justificativa": "Confirmo"}, {"item_id": itens[1], "nota": "10"}], "complemento": "Ok"}
    r = cliente.put(f"{base}/avaliacao/gestor", json=gestor, headers=gestora).json()
    assert r["avaliacao"]["nota_final"] == "7.50" and r["percentual_autorizado"] == "90.00" and r["valor_autorizado"] == "1894.50"

    ids = {m["login"]: m["usuario_id"] for m in cliente.get(_url(contrato), headers=gestora).json()["equipe"]}
    assinaturas = {"assinaturas": [{"papel": "gestor", "usuario_id": ids["gestora"]}, {"papel": "fiscal_tecnico", "usuario_id": ids["fiscal"]}]}
    assert cliente.put(f"{base}/avaliacao/assinaturas", json=assinaturas, headers=gestora).status_code == 200
    assert cliente.post(f"{base}/avaliacao/pdf", headers=gestora).status_code == 400
    cliente.post(f"{base}/avaliacao/ciencia", headers=gestora)
    cliente.post(f"{base}/avaliacao/ciencia", headers=fiscal)
    assert cliente.post(f"{base}/avaliacao/pdf", headers=gestora).json()["avaliacao"]["pdf_gerado"] is not None
    r = cliente.post(f"{base}/avaliacao/assinada", files={"arquivo": ("assinada.pdf", PDF)}, headers=gestora)
    assert r.json()["etapa_atual"] == "nota_fiscal"

    # Reconsideração: uma única vez
    r = cliente.post(f"{base}/avaliacao/reconsideracao", files={"arquivo": ("j.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200 and r.json()["etapa_atual"] == "avaliacao"
    cliente.post(f"{base}/avaliacao/ciencia", headers=gestora)
    cliente.post(f"{base}/avaliacao/ciencia", headers=fiscal)
    cliente.post(f"{base}/avaliacao/pdf", headers=gestora)
    cliente.post(f"{base}/avaliacao/assinada", files={"arquivo": ("assinada.pdf", PDF)}, headers=gestora)
    r = cliente.post(f"{base}/avaliacao/reconsideracao", files={"arquivo": ("j.pdf", PDF)}, headers=gestora)
    assert r.status_code == 400 and "já foi utilizada" in r.json()["detalhe"]


def test_modelos_globais(cliente, admin, equipe):
    """Só o SuperRoot cria modelos globais; qualquer um com leitura os lista."""
    _, gestora, _ = equipe
    modelo = {"tipo": "checklist", "nome": "Padrão SPI", "itens": [{"nome": "Folha"}, {"nome": "FGTS", "observacao": "Guia"}]}
    assert cliente.post("/api/contratos/modelos", json=modelo, headers=gestora).status_code == 403
    r = cliente.post("/api/contratos/modelos", json=modelo, headers=admin)
    assert r.status_code == 201 and r.json()["conteudo"]["itens"][1]["observacao"] == "Guia"
    assert cliente.post("/api/contratos/modelos", json={**FORMULARIO, "tipo": "formulario"}, headers=admin).status_code == 201
    assert [m["tipo"] for m in cliente.get("/api/contratos/modelos", headers=gestora).json()] == ["checklist", "formulario"]


def test_checklist_com_documentos_obrigatorios_e_opcionais(cliente, admin, equipe):
    """Documentos obrigatórios bloqueiam a conclusão do checklist; os opcionais não."""
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    itens = [{"nome": "Folha de pagamento", "obrigatorio": True}, {"nome": "Relatório fotográfico", "obrigatorio": False}]
    checklists = cliente.post(_url(contrato, "/checklists"), json={"nome": "Com opcionais", "itens": itens}, headers=gestora).json()
    novo = next(c for c in checklists if c["nome"] == "Com opcionais")
    assert [i["obrigatorio"] for i in novo["itens"]] == [True, False]
    # Versões antigas (sem a opção) continuam com todos os documentos obrigatórios
    assert all(i["obrigatorio"] for c in checklists if c["nome"] == "Mensal" for i in c["itens"])
    duplicado = cliente.post(_url(contrato, f"/checklists/{novo['id']}/duplicar"), headers=gestora).json()[0]
    assert [i["obrigatorio"] for i in duplicado["itens"]] == [True, False]
    cliente.post(_url(contrato, f"/checklists/{novo['id']}/ativar"), headers=gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)

    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    assert juntar_nf(cliente, base, gestora, "2105.00").status_code == 200
    assert conferir_retencao(cliente, base, gestora).status_code == 200
    detalhe = cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora).json()
    assert detalhe["etapa_atual"] == "checklist"
    assert [(d["nome"], d["obrigatorio"]) for d in detalhe["documentos"]] == [("Folha de pagamento", True), ("Relatório fotográfico", False)]

    r = cliente.post(f"{base}/checklist/concluir", headers=gestora)
    assert r.status_code == 400 and "Folha de pagamento" in r.json()["detalhe"]
    obrigatorio = detalhe["documentos"][0]["id"]
    detalhe = cliente.post(f"{base}/checklist/{obrigatorio}", files={"arquivo": ("f.pdf", PDF)}, headers=gestora).json()
    # O opcional ainda está sem anexo: a etapa espera a conclusão manual
    assert detalhe["etapa_atual"] == "checklist"
    r = cliente.post(f"{base}/checklist/concluir", headers=gestora)
    assert r.status_code == 200 and r.json()["etapa_atual"] == "consolidado"
    assert cliente.post(f"{base}/consolidado", headers=gestora).status_code == 200
