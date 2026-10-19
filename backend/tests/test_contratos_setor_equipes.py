# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o setor sistêmico "Equipes de contratos", mantido sozinho conforme a equipe dos contratos.
"""O setor sistêmico "Equipes de contratos" entra e sai de gente sozinho: ao designar, ao trocar a designação e ao excluir o contrato."""

from tests.apoio_contratos import criar_contrato, trocar_equipe_pela_portaria
from tests.conftest import criar_usuario


def _membros(cliente, admin) -> set[str]:
    setores = cliente.get("/api/setores", headers=admin).json()
    setor = next(s for s in setores if s["nome"] == "Equipes de contratos")
    assert setor["sistemico"] is True
    detalhe = cliente.get(f"/api/setores/{setor['id']}", headers=admin).json()
    return {m["login"] for m in detalhe["membros"]}


def _trocar_equipe(cliente, admin, contrato, equipe) -> None:
    """A equipe só muda por portaria: aplica o efeito da publicação."""
    trocar_equipe_pela_portaria(contrato["id"], equipe)


def test_quem_entra_na_equipe_entra_no_setor_e_quem_sai_de_todas_sai(cliente, admin):
    a, b = criar_usuario("fiscal-a"), criar_usuario("fiscal-b")
    contrato = criar_contrato(cliente, admin, equipe={"fiscal_tecnico": a})
    assert _membros(cliente, admin) == {"fiscal-a"}
    # Trocar o fiscal: o antigo sai (não está em nenhum outro contrato) e o novo entra
    _trocar_equipe(cliente, admin, contrato, {"fiscal_tecnico": b})
    assert _membros(cliente, admin) == {"fiscal-b"}


def test_quem_continua_em_outro_contrato_permanece(cliente, admin):
    a = criar_usuario("fiscal-a")
    primeiro = criar_contrato(cliente, admin, equipe={"fiscal_tecnico": a})
    criar_contrato(cliente, admin, empresa_id=primeiro["empresa"]["id"], numero="002/2026", equipe={"fiscal_tecnico": a})
    _trocar_equipe(cliente, admin, primeiro, {})
    assert _membros(cliente, admin) == {"fiscal-a"}


def test_excluir_o_contrato_tira_a_equipe_do_setor(cliente, admin):
    a = criar_usuario("fiscal-a")
    contrato = criar_contrato(cliente, admin, equipe={"fiscal_tecnico": a})
    assert _membros(cliente, admin) == {"fiscal-a"}
    assert cliente.delete(f"/api/contratos/{contrato['id']}", headers=admin).status_code == 204
    assert _membros(cliente, admin) == set()


def test_contrato_criado_sem_equipe_e_equipe_atribuida_depois_entra_no_setor(cliente, admin):
    """Caso da importação por planilha: o contrato nasce sem equipe; ao atribuir a equipe editando o contrato, as pessoas entram no grupo."""
    a = criar_usuario("fiscal-a")
    contrato = criar_contrato(cliente, admin)  # sem equipe, como o contrato importado
    assert _membros(cliente, admin) == set()
    _trocar_equipe(cliente, admin, contrato, {"fiscal_tecnico": a})
    assert _membros(cliente, admin) == {"fiscal-a"}
