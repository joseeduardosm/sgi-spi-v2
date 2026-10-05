# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a ordenação por coluna da carteira de contratos.
"""Carteira: ordem padrão (número, mais recentes primeiro) e ordenação por qualquer coluna, nos dois sentidos, com paginação."""

from tests.apoio_contratos import criar_contrato, criar_empresa

URL = "/api/contratos"


def _carteira(cliente, admin, **params) -> list[str]:
    r = cliente.get(URL, params=params, headers=admin)
    assert r.status_code == 200, r.text
    return [c["numero"] for c in r.json()["itens"]]


def test_ordenacao_por_coluna(cliente, admin):
    zeta = criar_empresa(cliente, admin, base="11111111", razao="Zeta Serviços")["id"]
    alfa = criar_empresa(cliente, admin, base="22222222", razao="alfa Limpeza")["id"]
    criar_contrato(cliente, admin, empresa_id=zeta, numero="001/2026", data_inicio="2026-03-01")
    criar_contrato(cliente, admin, empresa_id=alfa, numero="002/2026", data_inicio="2026-01-01")
    criar_contrato(cliente, admin, empresa_id=zeta, numero="003/2025", data_inicio="2025-06-01")
    # Padrão: número do mais recente ao mais antigo (ano, depois sequencial)
    assert _carteira(cliente, admin) == ["002/2026", "001/2026", "003/2025"]
    assert _carteira(cliente, admin, ordenar_por="numero", direcao="asc") == ["003/2025", "001/2026", "002/2026"]
    # Empresa sem diferenciar maiúsculas; empates seguem a ordem padrão
    assert _carteira(cliente, admin, ordenar_por="empresa", direcao="asc") == ["002/2026", "001/2026", "003/2025"]
    assert _carteira(cliente, admin, ordenar_por="empresa", direcao="desc") == ["001/2026", "003/2025", "002/2026"]
    assert _carteira(cliente, admin, ordenar_por="data_inicio", direcao="asc") == ["003/2025", "002/2026", "001/2026"]
    assert _carteira(cliente, admin, ordenar_por="data_fim", direcao="desc") == ["001/2026", "002/2026", "003/2025"]
    # Valores calculados (todos com os mesmos itens: empate, mantém a ordem padrão) e paginação depois de ordenar
    assert _carteira(cliente, admin, ordenar_por="valor_global", direcao="asc") == ["002/2026", "001/2026", "003/2025"]
    assert _carteira(cliente, admin, ordenar_por="situacao", direcao="asc", tamanho_pagina=2, pagina=2) == ["003/2025"]
    assert cliente.get(URL, params={"ordenar_por": "inventada"}, headers=admin).status_code == 422
