# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os estágios (colunas) configuráveis das equipes de tarefas.
"""Estágios da equipe (`/api/tarefas/equipes/{id}/estagios`, `/{numero}/estagio` e `estagio_id` em `mover`)."""

from tests.test_tarefas import URL, _nova, equipe  # noqa: F401  (fixture da equipe)


def _gravar(cliente, h, equipe_id, estagios):
    return cliente.put(f"{URL}/equipes/{equipe_id}/estagios", json={"estagios": estagios}, headers=h)


def _estagio(nome, categoria, cor=0, id=None):
    return {"id": id, "nome": nome, "categoria": categoria, "cor_indice": cor}


def test_padrao_e_configuracao_com_regras(cliente, equipe):
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
    sem_espera = [e for e in novo if e["nome"] != "Aguardando terceiros"]
    r = _gravar(cliente, h["lia"], equipe_id, sem_espera)
    assert r.status_code in (400, 409)
    cliente.post(f"{URL}/{t['numero']}/estagio", json={"estagio_id": b}, headers=h["ana"])
    assert _gravar(cliente, h["lia"], equipe_id, sem_espera).status_code == 200
