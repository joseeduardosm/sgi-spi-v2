"""
===============================================================================
ARQUIVO: test_tarefas_estagios.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar os estágios (colunas do quadro) configuráveis de cada equipe de
tarefas e a movimentação das tarefas entre eles.

RESUMO TÉCNICO:
Usa `GET/PUT /api/tarefas/equipes/{id}/estagios` para ler e regravar a
lista de estágios, `POST /{numero}/estagio` para trocar de coluna e o campo
`estagio_id` de `POST /{numero}/mover`. Confere as regras de gravação
(ordem do pipeline, uma categoria de validação, nomes únicos, mínimo de 4
estágios) e os códigos 400, 403, 404, 409 e 422.

FINALIDADE DE NEGÓCIO:
Garante que cada equipe pode adaptar o quadro ao seu jeito de trabalhar
(ex.: coluna "Aguardando terceiros") sem quebrar o fluxo oficial A fazer,
Em andamento, Em validação e Concluída, que só a liderança muda a
configuração e que um estágio com tarefas não some.

CONTEXTO NO SISTEMA:
Reaproveita `URL`, `_nova` e a fixture `equipe` de `tests/test_tarefas.py`;
exercita as rotas de `app/api/routes/tarefas.py` e o serviço de estágios em
`app/services/tarefas/`.

===============================================================================
"""

from tests.test_tarefas import URL, _nova, equipe  # noqa: F401  (fixture da equipe)


def _gravar(cliente, h, equipe_id, estagios):
    """Regrava a lista completa de estágios da equipe (o PUT substitui a configuração inteira)."""
    return cliente.put(f"{URL}/equipes/{equipe_id}/estagios", json={"estagios": estagios}, headers=h)


def _estagio(nome, categoria, cor=0, id=None):
    """Monta um estágio no formato do corpo da API; `id=None` significa estágio novo."""
    return {"id": id, "nome": nome, "categoria": categoria, "cor_indice": cor}


def test_padrao_e_configuracao_com_regras(cliente, equipe):
    """A equipe nasce com os 4 estágios padrão; só a liderança reconfigura, respeitando as regras."""
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/estagios"
    padrao = cliente.get(base, headers=h["ana"]).json()
    assert [(e["nome"], e["categoria"]) for e in padrao] == [("A fazer", "a_fazer"), ("Em andamento", "em_andamento"), ("Em validação", "em_validacao"), ("Concluída", "concluida")]
    assert cliente.get(base, headers=h["caio"]).status_code == 404  # fora da equipe
    a, b, v, c = [e["id"] for e in padrao]
    novo = [_estagio("A fazer", "a_fazer", id=a), _estagio("Triagem", "em_andamento", 4), _estagio("Em andamento", "em_andamento", 4, b),
            _estagio("Em validação", "em_validacao", 5, v), _estagio("Concluída", "concluida", 10, c)]
    assert _gravar(cliente, h["ana"], equipe_id, novo).status_code == 403  # só a liderança
    r = _gravar(cliente, h["lia"], equipe_id, novo)
    assert r.status_code == 200 and [e["nome"] for e in r.json()] == ["A fazer", "Triagem", "Em andamento", "Em validação", "Concluída"]
    # Regras: ordem do pipeline, categorias únicas, nome repetido
    assert _gravar(cliente, h["lia"], equipe_id, [novo[1], novo[0], *novo[2:]]).status_code == 400
    assert _gravar(cliente, h["lia"], equipe_id, [*novo, _estagio("Outra validação", "em_validacao")]).status_code == 400
    assert _gravar(cliente, h["lia"], equipe_id, [novo[0], _estagio("a fazer", "em_andamento"), *novo[3:], novo[2]]).status_code == 400
    assert _gravar(cliente, h["lia"], equipe_id, [novo[0], _estagio("Triagem", "a_fazer"), *novo[3:]]).status_code == 400  # sem "Em andamento"
    assert _gravar(cliente, h["lia"], equipe_id, novo[:1] + novo[3:]).status_code == 422  # menos de 4 estágios


def test_mover_entre_estagios_e_categorias(cliente, equipe):
    """Troca de coluna livre dentro da mesma categoria; mudar de categoria segue o fluxo (iniciar, pausar...)."""
    ids, h, equipe_id = equipe
    base = f"{URL}/equipes/{equipe_id}/estagios"
    a, b, v, c = [e["id"] for e in cliente.get(base, headers=h["lia"]).json()]
    novo = [_estagio("A fazer", "a_fazer", id=a), _estagio("Em andamento", "em_andamento", 4, b), _estagio("Aguardando terceiros", "em_andamento", 3),
            _estagio("Em validação", "em_validacao", 5, v), _estagio("Concluída", "concluida", 10, c)]
    espera = next(e["id"] for e in _gravar(cliente, h["lia"], equipe_id, novo).json() if e["nome"] == "Aguardando terceiros")
    t = _nova(cliente, h["lia"], equipe_id, responsavel_id=ids["ana"])
    assert t["estagio_id"] == a
    # Iniciar leva ao primeiro estágio de "em andamento"; trocar de coluna na mesma categoria
    assert cliente.post(f"{URL}/{t['numero']}/mover", json={"acao": "iniciar"}, headers=h["ana"]).json()["estagio_id"] == b
    r = cliente.post(f"{URL}/{t['numero']}/estagio", json={"estagio_id": espera}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["estagio_id"] == espera and r.json()["status"] == "em_andamento"
    # Outra categoria exige o pipeline; quem não é da tarefa não mexe
    assert cliente.post(f"{URL}/{t['numero']}/estagio", json={"estagio_id": c}, headers=h["ana"]).status_code == 400
    assert cliente.post(f"{URL}/{t['numero']}/estagio", json={"estagio_id": b}, headers=h["caio"]).status_code in (403, 404)
    # Voltar para "A fazer" e iniciar de novo escolhendo a coluna de destino
    assert cliente.post(f"{URL}/{t['numero']}/mover", json={"acao": "pausar"}, headers=h["ana"]).json()["estagio_id"] == a
    r = cliente.post(f"{URL}/{t['numero']}/mover", json={"acao": "iniciar", "estagio_id": espera}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["estagio_id"] == espera
    assert cliente.post(f"{URL}/{t['numero']}/mover", json={"acao": "pausar", "estagio_id": b}, headers=h["ana"]).status_code == 400  # estágio de outra categoria
    # A lista também traz o estágio; estágio com tarefa não é excluído
    lista = cliente.get(URL, params={"escopo": "equipe", "equipe_id": equipe_id}, headers=h["lia"]).json()["itens"]
    assert lista[0]["estagio_id"] in (a, espera)
    # Tentar remover "Aguardando terceiros" com a tarefa dentro falha; depois de tirá-la de lá, a remoção passa
    sem_espera = [e for e in novo if e["nome"] != "Aguardando terceiros"]
    r = _gravar(cliente, h["lia"], equipe_id, sem_espera)
    assert r.status_code in (400, 409)
    cliente.post(f"{URL}/{t['numero']}/estagio", json={"estagio_id": b}, headers=h["ana"])
    assert _gravar(cliente, h["lia"], equipe_id, sem_espera).status_code == 200
