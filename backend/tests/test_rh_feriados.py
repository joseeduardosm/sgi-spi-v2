# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o cadastro de feriados e pontos facultativos do Módulo RH.
"""Feriados e pontos facultativos: permissões, data única, regra de início vedado e exibição no calendário e no painel."""

from tests.test_rh_afastamentos import _ambiente, _pedir, equipe  # noqa: F401  (fixtures reaproveitadas)

URL = "/api/rh/feriados"


def _feriado(cliente, h, data="2026-11-20", descricao="Dia da Consciência Negra", tipo="feriado", abrangencia="nacional"):
    return cliente.post(URL, json={"data": data, "descricao": descricao, "tipo": tipo, "abrangencia": abrangencia}, headers=h)


def test_cgp_mantem_e_todos_leem(cliente, equipe):  # noqa: F811
    _, h, _ = equipe
    assert _feriado(cliente, h["ana"]).status_code == 403
    r = _feriado(cliente, h["rh"], descricao="  Dia da Consciência Negra ")
    assert r.status_code == 201, r.text
    feriado = r.json()
    assert feriado["descricao"] == "Dia da Consciência Negra" and feriado["atualizado_por_nome"] == "Rita RH"
    # Uma data só pode ter um cadastro
    r = _feriado(cliente, h["rh"], descricao="Outro", tipo="ponto_facultativo")
    assert r.status_code == 409 and "Já existe feriado em 20/11/2026" in r.json()["detalhe"]
    assert _feriado(cliente, h["rh"], data="2026-10-28", descricao="Dia do Servidor Público", tipo="ponto_facultativo").status_code == 201
    lista = cliente.get(URL, params={"ano": 2026}, headers=h["ana"]).json()
    assert [f["data"] for f in lista] == ["2026-10-28", "2026-11-20"]
    assert cliente.get(URL, params={"ano": 2027}, headers=h["ana"]).json() == []
    # Alterar e excluir: só a CGP
    corpo = {"data": "2026-11-20", "descricao": "Consciência Negra", "tipo": "feriado", "abrangencia": "estadual"}
    assert cliente.put(f"{URL}/{feriado['id']}", json=corpo, headers=h["ana"]).status_code == 403
    assert cliente.put(f"{URL}/{feriado['id']}", json=corpo, headers=h["rh"]).json()["abrangencia"] == "estadual"
    assert cliente.put(f"{URL}/{feriado['id']}", json={**corpo, "data": "2026-10-28"}, headers=h["rh"]).status_code == 409
    assert cliente.delete(f"{URL}/{feriado['id']}", headers=h["ana"]).status_code == 403
    assert cliente.delete(f"{URL}/{feriado['id']}", headers=h["rh"]).status_code == 204
    assert cliente.delete(f"{URL}/{feriado['id']}", headers=h["rh"]).status_code == 404
    # Validação: descrição vazia e tipo desconhecido
    assert _feriado(cliente, h["rh"], data="2026-12-25", descricao="   ").status_code == 422
    assert _feriado(cliente, h["rh"], data="2026-12-25", tipo="recesso").status_code == 422


def test_parametro_veda_inicio_em_feriado(cliente, equipe):  # noqa: F811
    _, h, _ = equipe
    assert _feriado(cliente, h["rh"], data="2026-11-03", descricao="Recesso de teste", tipo="ponto_facultativo").status_code == 201
    parametros = cliente.get("/api/rh/parametros", headers=h["ana"]).json()
    assert parametros["inicio_vedado_feriado"] is False
    # Desligado (padrão): pode começar no ponto facultativo
    r = _pedir(cliente, h["ana"], "2026-11-03", "2026-11-09")
    assert r.status_code == 201, r.text
    parametros = {k: v for k, v in parametros.items() if k not in ("atualizado_por_nome", "atualizado_em")}
    assert cliente.put("/api/rh/parametros", json={**parametros, "inicio_vedado_feriado": True}, headers=h["rh"]).status_code == 200
    for tipo in ("ferias", "licenca_premio"):
        r = _pedir(cliente, h["bia"], "2026-11-03", "2026-11-09", tipo)
        assert r.status_code == 400 and r.json()["detalhe"] == "O período não pode começar em feriado ou ponto facultativo (03/11/2026: Recesso de teste)."
    # Calendário e painel trazem os feriados
    meus = cliente.get("/api/rh/afastamentos/meus", params={"exercicio": 2026}, headers=h["ana"]).json()
    assert [f["descricao"] for f in meus["feriados"]] == ["Recesso de teste"]
    painel = cliente.get("/api/rh/afastamentos/painel", params={"visao": "mensal", "ano": 2026, "mes": 11}, headers=h["rh"]).json()
    assert [f["data"] for f in painel["feriados"]] == ["2026-11-03"]
    painel = cliente.get("/api/rh/afastamentos/painel", params={"visao": "mensal", "ano": 2026, "mes": 12}, headers=h["rh"]).json()
    assert painel["feriados"] == []
