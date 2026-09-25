# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as regras decididas na revisão do módulo de contratos.
"""Regras decididas na revisão do módulo de contratos (24/09/2026).

- 30/360 com início no último dia do mês;
- nota da avaliação = soma dos grupos (planilha oficial) e faixas por quantidade de notas zero;
- competência dividida em duas partes na virada da vigência;
- OB debita NF + NF adicional nas NEs apontadas; saldo comprometido por medições ainda não pagas;
- item sob demanda não pode ser medido acima do saldo da vigência;
- reajuste retroativo gera competência complementar de diferença.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.contratos import Competencia, Contrato
from app.services.contratos import calculos
from app.services.contratos.servico_competencias import maximo_de_notas_minimas_por_grupo, nota_final, percentual_da_nota
from tests.apoio_contratos import PDF
from tests.test_contratos_execucao import _hoje, _preparar_execucao, _url, equipe  # noqa: F401 (fixtures)

# --- 30/360 -----------------------------------------------------------------------------------------


def test_30_360_com_inicio_no_ultimo_dia_do_mes():
    assert calculos.dias_comerciais(date(2027, 2, 28), date(2027, 2, 28)) == 1
    assert calculos.dias_comerciais(date(2028, 2, 29), date(2028, 2, 29)) == 1
    assert calculos.dias_comerciais(date(2026, 1, 31), date(2026, 1, 31)) == 1
    assert calculos.dias_comerciais(date(2026, 2, 1), date(2026, 2, 28)) == 30


# --- Avaliação: planilha oficial ---------------------------------------------------------------------

PLANILHA = {
    "escala": [{"valor": 0, "legenda": "Péssimo"}, {"valor": 1, "legenda": "Regular"}, {"valor": 3, "legenda": "Bom"}],
    "faixas": [
        {"minimo": 6.75, "maximo": None, "percentual": 100},
        {"minimo": 5, "maximo": 6.74, "percentual": 90, "notas_zero": 1},
        {"minimo": 0, "maximo": 4.99, "percentual": 75, "notas_zero": 2},
    ],
    "grupos": [
        {"id": "g1", "nome": "Desempenho Profissional",
         "itens": [{"id": "a", "peso": 50}, {"id": "b", "peso": 30}, {"id": "c", "peso": 20}]},
        {"id": "g2", "nome": "Desempenho das Atividades",
         "itens": [{"id": "d", "peso": 40}, {"id": "e", "peso": 30}, {"id": "f", "peso": 30}]},
        {"id": "g3", "nome": "Gerenciamento",
         "itens": [{"id": "g", "peso": 20}, {"id": "h", "peso": 30}, {"id": "i", "peso": 25}, {"id": "j", "peso": 25}]},
    ],
}


def _avaliacao(notas: dict[str, int]):
    return SimpleNamespace(
        definicao=PLANILHA,
        respostas_iniciais=[{"item_id": k, "nota": str(v)} for k, v in notas.items()],
        respostas_gestor=[],
    )


def _liberacao(notas: dict[str, int]) -> tuple[Decimal, Decimal]:
    avaliacao = _avaliacao(notas)
    nota = nota_final(avaliacao)
    return nota, percentual_da_nota(PLANILHA, nota, maximo_de_notas_minimas_por_grupo(avaliacao))


def test_nota_final_e_a_soma_dos_grupos():
    todas_bom = {k: 3 for k in "abcdefghij"}
    assert _liberacao(todas_bom) == (Decimal("9.00"), Decimal(100))


def test_faixa_pela_nota():
    # g1 = 3, g2 = 3, g3 = 1 → 7,00 (≥ 6,75: libera tudo)
    assert _liberacao({**{k: 3 for k in "abcdef"}, **{k: 1 for k in "ghij"}}) == (Decimal("7.00"), Decimal(100))
    # g1 = 3, g2 = 1, g3 = 1 → 5,00 (90%)
    assert _liberacao({**{k: 3 for k in "abc"}, **{k: 1 for k in "defghij"}}) == (Decimal("5.00"), Decimal(90))
    # todas regulares → 3,00 (75%)
    assert _liberacao({k: 1 for k in "abcdefghij"}) == (Decimal("3.00"), Decimal(75))


def test_notas_zero_limitam_a_liberacao_mesmo_com_nota_alta():
    # Uma nota 0 num grupo: nota 8,40 (faixa de 100%), mas a regra da nota zero limita a 90%
    nota, percentual = _liberacao({**{k: 3 for k in "abcdefghij"}, "c": 0})
    assert nota == Decimal("8.40") and percentual == Decimal(90)
    # Duas notas 0 no mesmo grupo: 75%
    assert _liberacao({**{k: 3 for k in "abcdefghij"}, "b": 0, "c": 0})[1] == Decimal(75)
    # Uma nota 0 em cada um de dois grupos (máximo 1 por grupo): 90%
    assert _liberacao({**{k: 3 for k in "abcdefghij"}, "c": 0, "g": 0})[1] == Decimal(90)


# --- Competência dividida na virada da vigência -----------------------------------------------------


def test_mes_dividido_entre_vigencias_vira_duas_partes():
    vigencias = calculos.montar_vigencias(date(2026, 1, 15), date(2027, 1, 14), 12, [(date(2027, 1, 15), date(2028, 1, 14))])
    janeiro = [p for p in calculos.periodos_de_execucao(vigencias, 1) if p.competencia == date(2027, 1, 1)]
    assert [(p.inicio, p.fim, p.sequencia_vigencia) for p in janeiro] == [
        (date(2027, 1, 1), date(2027, 1, 14), 1), (date(2027, 1, 15), date(2027, 1, 31), 2),
    ]
    contrato = Contrato()
    unica = Competencia(tipo="regular", competencia=date(2026, 12, 1), periodo_inicio=date(2026, 12, 1), periodo_fim=date(2026, 12, 31))
    partes = [
        Competencia(tipo="regular", competencia=p.competencia, periodo_inicio=p.inicio, periodo_fim=p.fim, sequencia_vigencia=p.sequencia_vigencia)
        for p in janeiro
    ]
    diferenca = Competencia(tipo="diferenca_reajuste", competencia=date(2026, 1, 1), periodo_inicio=date(2026, 1, 15), periodo_fim=date(2026, 4, 30))
    contrato.competencias.extend([unica, *reversed(partes), diferenca])
    assert (unica.parte, unica.identificador, unica.numero_competencia) == (None, "2026-12", "12/2026")
    assert [(c.parte, c.identificador, c.numero_competencia) for c in partes] == [
        (1, "2027-01-1", "01/2027 · 1ª parte"), (2, "2027-01-2", "01/2027 · 2ª parte"),
    ]
    assert diferenca.identificador == "2026-01-dif" and diferenca.numero_competencia == "Diferença de reajuste 01/2026 a 04/2026"


# --- Pagamento: NF + NF adicional, saldo comprometido -----------------------------------------------


def _medir_e_concluir(cliente, contrato, gestora, fiscal, identificador, notas, quantidades=None):
    competencia = cliente.get(_url(contrato, f"/competencias/identificador/{identificador}"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": (quantidades or {}).get(i["descricao"], i["quantidade_prevista"])} for i in competencia["itens"]]
    r = cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 200, r.text
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    return base, cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)


def test_ob_debita_nf_e_nf_adicional_e_saldo_fica_comprometido(cliente, admin, equipe):  # noqa: F811
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = {n["numero"]: n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    ordem = [notas["2026NE00001"], notas["2026NE00002"]]

    base, r = _medir_e_concluir(cliente, contrato, gestora, fiscal, "2026-01", ordem)
    assert r.status_code == 200 and r.json()["valor_a_pagar"] == "2105.00"

    # Janeiro medido e não pago: reserva 1.000 na NE1 e 1.105 na NE2
    lidas = {n["numero"]: n for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    assert (lidas["2026NE00001"]["comprometido"], lidas["2026NE00001"]["saldo_livre"]) == ("1000.00", "0.00")
    assert (lidas["2026NE00002"]["comprometido"], lidas["2026NE00002"]["saldo_livre"]) == ("1105.00", "48895.00")

    # Fevereiro não pode contar só com a NE1: o saldo dela está comprometido com janeiro
    fevereiro = cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()
    itens = [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in fevereiro["itens"]]
    r = cliente.put(_url(contrato, f"/competencias/{fevereiro['id']}/medicao"), json={"itens": itens, "notas_empenho_ids": [notas["2026NE00001"]]}, headers=gestora)
    assert r.status_code == 400 and "saldo livre" in r.json()["detalhe"]

    # NF principal (valor da medição) + NF adicional de 500: a OB debita 2.605 nas mesmas NEs, em ordem
    nf = {"numero": "10", "recebida_em": "2026-02-05", "prazo_pagamento_dias": "30", "origem_valor": "medicao",
          "possui_adicional": "true", "adicional_numero": "11", "adicional_valor_bruto": "500.00"}
    r = cliente.post(f"{base}/nota-fiscal", data=nf, files={"arquivo": ("nf.pdf", PDF), "arquivo_adicional": ("nf2.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200, r.text
    assert r.json()["valor_a_pagar"] == "2605.00"
    cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora)
    for documento in cliente.get(base, headers=gestora).json()["documentos"]:
        cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    cliente.post(f"{base}/consolidado", headers=gestora)
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=gestora).json()["situacao"] == "concluida"
    lidas = {n["numero"]: n for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    assert lidas["2026NE00001"]["saldo"] == "0.00" and lidas["2026NE00002"]["saldo"] == "48395.00"
    assert lidas["2026NE00002"]["comprometido"] == "0.00"


def test_nf_que_passa_do_saldo_livre_das_nes_e_recusada(cliente, admin, equipe):  # noqa: F811
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = {n["numero"]: n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    base, r = _medir_e_concluir(cliente, contrato, gestora, fiscal, "2026-01", [notas["2026NE00002"]])
    assert r.status_code == 200
    nf = {"numero": "10", "recebida_em": "2026-02-05", "prazo_pagamento_dias": "30", "origem_valor": "manual", "valor_bruto": "60000.00"}
    r = cliente.post(f"{base}/nota-fiscal", data=nf, files={"arquivo": ("nf.pdf", PDF)}, headers=gestora)
    assert r.status_code == 400 and "saldo" in r.json()["detalhe"]


# --- Sob demanda acima do saldo da vigência ----------------------------------------------------------


def test_medicao_sob_demanda_acima_do_limite_avisa_e_bloqueia_conclusao(cliente, admin, equipe):  # noqa: F811
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    base, r = _medir_e_concluir(cliente, contrato, gestora, fiscal, "2026-01", notas, {"Material": "150"})
    assert r.status_code == 400 and "saldo disponível" in r.json()["detalhe"]
    avisos = cliente.get(base, headers=gestora).json()["avisos"]
    assert len(avisos) == 1 and "Material" in avisos[0]


# --- Reajuste retroativo ------------------------------------------------------------------------------


def test_reajuste_retroativo_gera_competencia_de_diferenca(cliente, admin, equipe):  # noqa: F811
    contrato, gestora, fiscal = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    _, r = _medir_e_concluir(cliente, contrato, gestora, fiscal, "2026-01", notas)
    assert r.status_code == 200

    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-01-01"}, headers=gestora).json()["em_andamento"]
    assert reajuste["competencias_com_diferenca"] == 1
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    cliente.put(f"{url}/memoria", json={"itens": [{"item_id": i["item_id"], "indice_percentual": "10"} for i in reajuste["itens"]]}, headers=gestora)
    cliente.post(f"{url}/evidencia", files={"arquivo": ("e.pdf", PDF)}, headers=gestora)
    cliente.post(f"{url}/memoria/arquivos", headers=gestora)
    assert cliente.post(f"{url}/concluir", files={"arquivo": ("a.pdf", PDF)}, headers=gestora).status_code == 200

    diferenca = cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif"), headers=gestora).json()
    assert diferenca["tipo"] == "diferenca_reajuste" and diferenca["rotulo"] == "Diferença de reajuste 01/2026 a 01/2026"
    # 2 × (1.100 − 1.000) + 10 × (11,55 − 10,50) = 210,50
    assert diferenca["total_medido"] == "210.50" and diferenca["etapa_atual"] == "medicao"
    # As quantidades são as já medidas: não podem ser alteradas
    base = _url(contrato, f"/competencias/{diferenca['id']}")
    alteradas = [{"id": i["id"], "quantidade_medida": "1"} for i in diferenca["itens"]]
    r = cliente.put(f"{base}/medicao", json={"itens": alteradas, "notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 400
    # A diferença não conta como execução do item sob demanda
    assert cliente.get(_url(contrato), headers=gestora).json()["itens"][1]["quantidade_executada"] == "10.0000"
    # Lista da execução mostra a complementar junto das demais
    rotulos = [c["rotulo"] for g in cliente.get(_url(contrato, "/execucao"), headers=gestora).json()["grupos"] for c in g["competencias"]]
    assert "Diferença de reajuste 01/2026 a 01/2026" in rotulos


# --- Competências migradas do SGI (períodos pelo aniversário) ------------------------------------


def test_geracao_nao_sobrepoe_competencias_migradas(cliente, admin, equipe):  # noqa: F811
    """Uma competência de 15/01 a 14/02 (aniversário) impede gerar a de fevereiro civil, que se sobrepõe a ela."""
    from app.core.banco import FabricaSessao
    import uuid

    from app.models.contratos import Competencia as ModeloCompetencia

    contrato, gestora, _ = equipe
    _preparar_execucao(cliente, contrato, gestora)
    with FabricaSessao() as sessao:
        sessao.add(ModeloCompetencia(contrato_id=uuid.UUID(contrato["id"]), competencia=date(2026, 1, 1), periodo_inicio=date(2026, 1, 15),
                                     periodo_fim=date(2026, 2, 14), etapa_atual="medicao"))
        sessao.commit()
    painel = cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora).json()
    periodos = sorted((c["periodo_inicio"], c["periodo_fim"]) for g in painel["grupos"] for c in g["competencias"])
    assert ("2026-01-15", "2026-02-14") in periodos
    assert not any(inicio in ("2026-01-01", "2026-02-01") for inicio, _ in periodos)
    assert ("2026-03-01", "2026-03-31") in periodos
