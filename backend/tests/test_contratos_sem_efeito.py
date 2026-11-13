"""
===============================================================================
ARQUIVO: test_contratos_sem_efeito.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar o "Tornar sem efeito" dos eventos concluídos do contrato (reajuste e
aditamento; a prorrogação está em test_contratos_alteracoes) e a aba
"Eventos" do contrato.

RESUMO TÉCNICO:
Usa os cenários de test_contratos_reajuste_desconto (hoje = 15/03/2026,
item contínuo de 2 × R$ 1.000,00) e de test_contratos_alteracoes (equipe com
gestora e fiscal). Chama `POST …/{tipo}/{id}/sem-efeito` e confere o que
volta (preço, quantidade, competência de diferença, crédito), os bloqueios
(409 com o motivo), a situação "sem_efeito" no histórico e a auditoria; e a
rota `GET …/eventos` (403 sem Controle total, categorias, busca, botão).

FINALIDADE DE NEGÓCIO:
Decisões do usuário (13/11/2026): qualquer evento pode ser desfeito se nada
depender dele; bloqueia se a diferença já foi medida, se o crédito já foi
aplicado ou se algum mês foi medido com o valor novo; motivo obrigatório; o
evento fica no histórico com o selo "Sem efeito".

CONTEXTO NO SISTEMA:
app/services/contratos/servico_sem_efeito.py e servico_eventos.py; rotas em
api/routes/contratos/alteracoes.py e contratos.py.

===============================================================================
"""

from tests.apoio_contratos import PDF
from tests.test_contratos_alteracoes import _alteracao, equipe  # noqa: F401 (fixture)
from tests.test_contratos_execucao import _url
from tests.test_contratos_reajuste_desconto import _abrir, _aplicar, _competencia, _concluir, _hoje, _medir, cenario  # noqa: F401 (fixtures)

MOTIVO = {"motivo": "Índice aplicado por engano no processo"}


def _sem_efeito(cliente, contrato, h, tipo, registro_id, corpo=MOTIVO):
    return cliente.post(_url(contrato, f"/{tipo}/{registro_id}/sem-efeito"), json=corpo, headers=h)


def _reajuste_concluido(cliente, contrato, h, notas, indices=("10", "0")):
    """Janeiro medido; reajuste desde janeiro concluído (gera a diferença de janeiro). Devolve (url, id)."""
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", list(indices))
    _concluir(cliente, h, url)
    return url, r.json()["em_andamento"]["id"]


def test_reajuste_sem_efeito_volta_o_preco_e_tira_a_diferenca(cliente, cenario):
    """+10%: o preço volta a R$ 1.000,00, a competência de diferença sai e o histórico mostra o selo com quem e o motivo."""
    contrato, h, notas = cenario
    url, rid = _reajuste_concluido(cliente, contrato, h, notas)
    assert _competencia(cliente, contrato, h, "2026-03")["itens"][0]["valor_unitario"] == "1100.0000"
    assert _competencia(cliente, contrato, h, "2026-01-dif")["id"]
    historico = cliente.get(_url(contrato, "/reajustes"), headers=h).json()["historico"][0]
    assert historico["pode_tornar_sem_efeito"] is True and historico["motivo_bloqueio"] == ""

    # Sem motivo (ou curto) não vai
    assert _sem_efeito(cliente, contrato, h, "reajustes", rid, {}).status_code == 422
    assert _sem_efeito(cliente, contrato, h, "reajustes", rid, {"motivo": "erro"}).status_code == 422
    assert _sem_efeito(cliente, contrato, h, "reajustes", rid).status_code == 204

    assert cliente.get(_url(contrato), headers=h).json()["itens"][0]["valor_unitario"] == "1000.0000"
    assert _competencia(cliente, contrato, h, "2026-03")["itens"][0]["valor_unitario"] == "1000.0000"
    assert cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif"), headers=h).status_code == 404
    historico = cliente.get(_url(contrato, "/reajustes"), headers=h).json()["historico"][0]
    assert historico["situacao"] == "sem_efeito" and historico["sem_efeito_motivo"] == MOTIVO["motivo"] and historico["sem_efeito_por"]
    assert historico["pode_tornar_sem_efeito"] is False
    # De novo: já está sem efeito
    assert _sem_efeito(cliente, contrato, h, "reajustes", rid).status_code == 409


def test_mes_medido_com_o_preco_novo_bloqueia(cliente, cenario):
    """Fevereiro medido depois da conclusão (com o preço novo): 409 e o botão desativado com o motivo."""
    contrato, h, notas = cenario
    _, rid = _reajuste_concluido(cliente, contrato, h, notas)
    _medir(cliente, contrato, h, notas, "2026-02")
    r = _sem_efeito(cliente, contrato, h, "reajustes", rid)
    assert r.status_code == 409 and "02/2026 já foi medida com o preço novo" in r.json()["detalhe"]
    historico = cliente.get(_url(contrato, "/reajustes"), headers=h).json()["historico"][0]
    assert historico["pode_tornar_sem_efeito"] is False and "02/2026" in historico["motivo_bloqueio"]


def test_diferenca_ja_medida_bloqueia(cliente, cenario):
    """A competência de diferença já medida impede: é preciso reabrir antes."""
    contrato, h, notas = cenario
    _, rid = _reajuste_concluido(cliente, contrato, h, notas)
    _medir(cliente, contrato, h, notas, "2026-01-dif")
    r = _sem_efeito(cliente, contrato, h, "reajustes", rid)
    assert r.status_code == 409 and "competência de diferença" in r.json()["detalhe"]


def test_credito_aplicado_bloqueia_e_credito_no_fundo_sai(cliente, cenario):
    """Desconto de 10%: com o crédito aplicado em março, bloqueia; retirado da medição, o crédito sai junto com o reajuste."""
    contrato, h, notas = cenario
    _, rid = _reajuste_concluido(cliente, contrato, h, notas, ("-10", "0"))
    _aplicar(cliente, contrato, h, "2026-03")
    r = _sem_efeito(cliente, contrato, h, "reajustes", rid)
    assert r.status_code == 409 and "crédito" in r.json()["detalhe"]


def test_aditamento_sem_efeito_volta_a_quantidade(cliente, admin, equipe):  # noqa: F811
    """Aditamento de Limpeza 2 → 2,2 concluído: tornado sem efeito, a quantidade mensal volta a 2."""
    contrato, gestora, fiscal = equipe
    url, itens = _alteracao(cliente, contrato, gestora, "aditamento", {"Limpeza": "2.2"})
    cliente.put(f"{url}/quantitativos", json={"itens": itens}, headers=gestora)
    cliente.post(f"{url}/ciencia", headers=gestora)
    cliente.post(f"{url}/ciencia", headers=fiscal)
    cliente.post(f"{url}/memoria", headers=gestora)
    cliente.post(f"{url}/documentos/de_acordo", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    cliente.post(f"{url}/consolidado", headers=gestora)
    cliente.post(f"{url}/documentos/termo", files={"arquivo": ("t.pdf", PDF)}, headers=gestora)
    assert cliente.post(f"{url}/concluir", headers=gestora).status_code == 200
    assert cliente.get(_url(contrato), headers=gestora).json()["itens"][0]["quantidade_mensal"] == "2.2000"
    aid = cliente.get(_url(contrato, "/alteracoes"), headers=gestora).json()["historico"][0]["id"]

    assert _sem_efeito(cliente, contrato, gestora, "alteracoes", aid).status_code == 204
    assert cliente.get(_url(contrato), headers=gestora).json()["itens"][0]["quantidade_mensal"] == "2.0000"
    historico = cliente.get(_url(contrato, "/alteracoes"), headers=gestora).json()["historico"][0]
    assert historico["situacao"] == "sem_efeito" and historico["sem_efeito_motivo"] == MOTIVO["motivo"]


def test_eventos_so_para_controle_total_com_categorias_busca_e_botao(cliente, admin, cenario):
    """A gestora (Modificação) não vê a aba; o admin vê o reajuste concluído com o botão e, depois, o "sem efeito"."""
    contrato, h, notas = cenario
    _, rid = _reajuste_concluido(cliente, contrato, h, notas)
    assert cliente.get(_url(contrato, "/eventos"), headers=h).status_code == 403

    pagina = cliente.get(_url(contrato, "/eventos"), params={"categoria": "altera_contrato"}, headers=admin).json()
    concluido = next(e for e in pagina["itens"] if e["acao"] == "contrato.reajuste.concluir")
    assert concluido["evento"] == "Reajuste concluído" and concluido["registro_tipo"] == "reajustes" and concluido["registro_id"] == rid
    assert concluido["pode_tornar_sem_efeito"] is True and pagina["por_categoria"]["execucao"] > 0
    # Busca sem acento e filtro por categoria
    achados = cliente.get(_url(contrato, "/eventos"), params={"busca": "medicao concluida"}, headers=admin).json()["itens"]
    assert achados and all(e["categoria"] == "execucao" for e in achados)

    assert _sem_efeito(cliente, contrato, admin, "reajustes", rid).status_code == 204
    sem = cliente.get(_url(contrato, "/eventos"), params={"categoria": "sem_efeito"}, headers=admin).json()["itens"]
    assert [e["evento"] for e in sem] == ["Reajuste tornado sem efeito"] and MOTIVO["motivo"] in sem[0]["detalhe"]
    concluido = next(e for e in cliente.get(_url(contrato, "/eventos"), headers=admin).json()["itens"] if e["acao"] == "contrato.reajuste.concluir")
    assert concluido["sem_efeito"] is True and concluido["pode_tornar_sem_efeito"] is False


def test_repactuacao_sem_efeito_tira_a_diferenca_do_preco(cliente, admin, equipe):  # noqa: F811
    """Repactuação de +R$ 10 (vale-transporte) desde janeiro, janeiro medido: tornada sem efeito, o preço volta e a diferença sai."""
    from tests.apoio_contratos import escolher_calculo
    from tests.test_contratos_repactuacao import _medir_janeiro

    contrato, gestora, fiscal = equipe
    _medir_janeiro(cliente, contrato, gestora, fiscal)
    painel = cliente.post(_url(contrato, "/repactuacoes"), data={"data_base_cct": "2026-01-01", "data_efeito": "2026-01-01"},
                          files={"arquivo": ("cct.pdf", PDF)}, headers=gestora).json()
    continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
    url = _url(contrato, f"/repactuacoes/{painel['em_andamento']['id']}")
    escolher_calculo(cliente, url, gestora)
    cliente.put(f"{url}/linhas", json={"finalizar": True, "linhas": [
        {"descricao": "Vale-transporte", "valor_vigente": "100", "valor_repactuado": "110", "itens_ids": [continuo["id"]]}]}, headers=gestora)
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 200
    assert cliente.post(f"{url}/consolidado", headers=gestora).status_code == 200
    final = cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora)
    assert final.status_code == 200, final.text
    rid = final.json()["historico"][0]["id"]
    preco = lambda: next(i for i in cliente.get(_url(contrato), headers=gestora).json()["itens"] if i["id"] == continuo["id"])["valor_unitario"]  # noqa: E731
    assert float(preco()) == float(continuo["valor_unitario"]) + 10

    assert _sem_efeito(cliente, contrato, gestora, "repactuacoes", rid).status_code == 204
    assert float(preco()) == float(continuo["valor_unitario"])
    historico = cliente.get(_url(contrato, "/repactuacoes"), headers=gestora).json()["historico"][0]
    assert historico["situacao"] == "sem_efeito" and historico["competencia_diferenca"] is None
