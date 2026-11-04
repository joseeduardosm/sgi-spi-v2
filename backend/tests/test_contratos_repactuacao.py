# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a repactuação pela CCT: linhas e vínculos, memória, retroativo, checklist, consolidado e finalização.
"""Repactuação: a diferença de cada componente de custo soma no preço dos itens vinculados, a partir da data de vigência da CCT."""
from datetime import date
from decimal import Decimal

import pytest

from tests.apoio_contratos import PDF, corpo_conclusao
from tests.test_contratos_alteracoes import equipe  # noqa: F401 (fixture)
from tests.test_contratos_execucao import _preparar_execucao, _url

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


def _medir_janeiro(cliente, contrato, gestora, fiscal):
    """Mede e conclui a medição de janeiro (a competência que o retroativo alcança)."""
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{janeiro['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in janeiro["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    assert cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(base, notas), headers=gestora).status_code == 200


def _abrir(cliente, contrato, h, efeito="2026-01-16", base_cct="2026-01-01"):
    return cliente.post(_url(contrato, "/repactuacoes"), data={"data_base_cct": base_cct, "data_efeito": efeito}, files={"arquivo": ("cct.pdf", PDF)}, headers=h)


def test_repactuacao_completa(cliente, admin, equipe):  # noqa: F811
    """Linhas com vínculos 1..N, nova base, mês quebrado, checklist, consolidado e finalização com competência de diferença."""
    contrato, gestora, fiscal = equipe
    _medir_janeiro(cliente, contrato, gestora, fiscal)
    assert cliente.post("/api/contratos/modelos", json={"tipo": "checklist_repactuacao", "nome": "Padrão", "itens": [
        {"nome": "Pedido da contratada", "observacao": "", "obrigatorio": True}]}, headers=admin).status_code == 201

    r = _abrir(cliente, contrato, gestora)
    assert r.status_code == 201, r.text
    painel = r.json()
    rep = painel["em_andamento"]
    assert rep["data_base_cct"] == "2026-01-01" and len(rep["checklist"]) == 1 and rep["obrigatorios_pendentes"] == 1
    assert _abrir(cliente, contrato, gestora).status_code == 409
    # A CCT entra nos Documentos importantes
    documentos = cliente.get(_url(contrato, "/documentos"), headers=gestora).json()
    assert any(d["titulo"] == "CCT 01/2026" for d in (documentos if isinstance(documentos, list) else documentos.get("documentos", [])))

    itens = {i["descricao"]: i for i in painel["itens_contrato"]}
    continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
    todos = [i["id"] for i in itens.values()]
    url = _url(contrato, f"/repactuacoes/{rep['id']}")
    linhas = {"linhas": [
        {"descricao": "Vale-transporte", "valor_vigente": "198", "valor_repactuado": "220", "itens_ids": [continuo["id"]]},
        {"descricao": "Uniforme", "valor_vigente": "10", "valor_repactuado": "15", "itens_ids": todos},
    ]}
    rep = cliente.put(f"{url}/linhas", json=linhas, headers=gestora).json()["em_andamento"]
    novos = {i["item_id"]: Decimal(i["valor_unitario_repactuado"]) - Decimal(i["valor_unitario_atual"]) for i in rep["itens"]}
    assert novos[continuo["id"]] == Decimal("27")  # 22 + 5: o item vinculado às duas linhas soma as duas diferenças
    assert [l["diferenca_percentual"] for l in rep["linhas"]] == ["11.1111", "50.0000"]
    impacto = sum((Decimal(i["impacto_mensal"]) for i in rep["itens"]), Decimal(0))
    assert Decimal(rep["base_repactuada"]) - Decimal(rep["base_atual"]) == impacto == Decimal(rep["total_diferencas"]) > 0
    # A memória só depois de finalizar o cadastro; janeiro medido e quebrado em 16/01 pede a escolha do cálculo
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 400
    rep = cliente.put(f"{url}/linhas", json={**linhas, "finalizar": True}, headers=gestora).json()["em_andamento"]
    janeiro = next(c for c in rep["competencias"] if c["competencia"] == "01/2026")
    assert janeiro["medida"] and janeiro["quebrada"] and not janeiro["paga"]
    assert any(not c["medida"] and c["situacao"] == "Aguardando medição" for c in rep["competencias"])
    opcoes = {o["calculo"]: Decimal(o["total_diferenca"]) for o in rep["opcoes_mes_quebrado"]}
    assert opcoes["integral"] > opcoes["pro_rata"] > 0 and abs(opcoes["integral"] / 2 - opcoes["pro_rata"]) <= Decimal("0.01")  # 16 a 30/01 = metade (30/360)
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 400
    cliente.put(f"{url}/mes-quebrado", json={"calculo": "integral"}, headers=gestora)
    rep = cliente.post(f"{url}/memoria", headers=gestora).json()["em_andamento"]
    assert rep["memoria_atualizada"] and Decimal(rep["total_retroativo"]) == opcoes["integral"]
    xlsx = cliente.get(f"{url}/arquivos/{rep['memorias'][0]['xlsx']['anexo_id']}", headers=gestora)
    assert xlsx.content[:2] == b"PK"

    # Finalizar exige o checklist e o consolidado
    assert cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).status_code == 400
    cliente.post(f"{url}/checklist/{rep['checklist'][0]['id']}", files={"arquivo": ("p.pdf", PDF)}, headers=gestora)
    rep = cliente.post(f"{url}/consolidado", headers=gestora).json()["em_andamento"]
    assert rep["consolidado"] is not None and rep["consolidado_atualizado"]
    painel = cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).json()
    assert painel["em_andamento"] is None and painel["historico"][0]["situacao"] == "concluido"
    final = painel["historico"][0]
    assert final["competencia_diferenca"] == "2026-01-dif-repactuacao" and Decimal(final["diferenca_retroativa"]) == opcoes["integral"]

    # Preço do cadastro e das competências não medidas com a diferença; janeiro (medido) fica como estava
    detalhe = cliente.get(_url(contrato), headers=gestora).json()
    preco = next(i for i in detalhe["itens"] if i["id"] == continuo["id"])["valor_unitario"]
    assert Decimal(preco) == Decimal(continuo["valor_unitario"]) + 27
    fevereiro = cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()
    assert Decimal(next(i for i in fevereiro["itens"] if i["ordem"] == continuo["ordem"])["valor_unitario"]) == Decimal(preco)
    janeiro = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    assert Decimal(next(i for i in janeiro["itens"] if i["ordem"] == continuo["ordem"])["valor_unitario"]) == Decimal(continuo["valor_unitario"])
    lista = [c["identificador"] for g in cliente.get(_url(contrato, "/execucao"), headers=gestora).json()["grupos"] for c in g["competencias"]]
    assert "2026-01-dif-repactuacao" in lista, lista
    dif = cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif-repactuacao"), headers=gestora).json()
    assert dif.get("tipo") == "diferenca_repactuacao" and "Diferença de repactuação" in dif["rotulo"], dif
    # Nada pode valer antes desta repactuação agora
    assert _abrir(cliente, contrato, gestora, efeito="2026-01-10").status_code == 409


def test_repactuacao_com_desconto_vira_credito(cliente, admin, equipe):  # noqa: F811
    """Componente que diminui: a diferença negativa das medidas vira crédito abatido na próxima medição."""
    contrato, gestora, fiscal = equipe
    _medir_janeiro(cliente, contrato, gestora, fiscal)
    painel = _abrir(cliente, contrato, gestora, efeito="2026-01-01").json()
    continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
    url = _url(contrato, f"/repactuacoes/{painel['em_andamento']['id']}")
    rep = cliente.put(f"{url}/linhas", json={"finalizar": True, "linhas": [
        {"descricao": "Plano de saúde", "valor_vigente": "100", "valor_repactuado": "90", "itens_ids": [continuo["id"]]}]}, headers=gestora).json()["em_andamento"]
    assert rep["opcoes_mes_quebrado"] == [] and Decimal(rep["total_retroativo"]) < 0
    cliente.post(f"{url}/memoria", headers=gestora)
    cliente.post(f"{url}/consolidado", headers=gestora)
    final = cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).json()["historico"][0]
    assert final["competencia_diferenca"] is None and Decimal(final["diferenca_retroativa"]) < 0
    fevereiro = cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()
    assert Decimal(fevereiro["desconto_reajuste"]) == -Decimal(final["diferenca_retroativa"])
    assert fevereiro["descontos_reajuste"][0]["repactuacao_id"] == final["id"]


def test_cada_repactuacao_gera_a_sua_competencia_de_diferenca(cliente, admin, equipe):  # noqa: F811
    """Duas repactuações retroativas a janeiro: cada uma paga só os próprios componentes, numa competência de diferença própria."""
    contrato, gestora, fiscal = equipe
    _medir_janeiro(cliente, contrato, gestora, fiscal)

    def repactuar(descricao, vigente, repactuado):
        painel = _abrir(cliente, contrato, gestora, efeito="2026-01-01").json()
        continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
        url = _url(contrato, f"/repactuacoes/{painel['em_andamento']['id']}")
        cliente.put(f"{url}/linhas", json={"finalizar": True, "linhas": [
            {"descricao": descricao, "valor_vigente": vigente, "valor_repactuado": repactuado, "itens_ids": [continuo["id"]]}]}, headers=gestora)
        cliente.post(f"{url}/memoria", headers=gestora)
        cliente.post(f"{url}/consolidado", headers=gestora)
        return continuo, cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora).json()["historico"][0]

    continuo, primeira = repactuar("Vale-transporte", "198", "220")  # +22
    _, segunda = repactuar("Vale-alimentação", "500", "510")  # +10, depois da primeira
    postos = Decimal(primeira["itens"][0]["quantidade_mensal"])
    assert Decimal(primeira["diferenca_retroativa"]) == 22 * postos
    assert Decimal(segunda["diferenca_retroativa"]) == 10 * postos  # não cobra de novo os 22 da primeira
    assert (primeira["competencia_diferenca"], segunda["competencia_diferenca"]) == ("2026-01-dif-repactuacao", "2026-01-dif-repactuacao-2")
    dif2 = cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif-repactuacao-2"), headers=gestora).json()
    assert dif2["tipo"] == "diferenca_repactuacao" and "(2ª)" in dif2["rotulo"]
    preco = next(i for i in cliente.get(_url(contrato), headers=gestora).json()["itens"] if i["id"] == continuo["id"])["valor_unitario"]
    assert Decimal(preco) == Decimal(continuo["valor_unitario"]) + 22 + 10  # R$ 1.000 + 22 (1ª) + 10 (2ª) = R$ 1.032
