# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a troca dos setores institucionais pela estrutura oficial da SPI.
"""Reorganização dos setores (`servico_setores.substituir_estrutura`)."""

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import servico_perfil
from app.services.estrutura_setores import ESTRUTURA_SPI, contar
from app.services.servico_setores import opcoes_departamento, substituir_estrutura
from tests.conftest import cabecalho, criar_usuario


def _cenario() -> tuple[int, int]:
    """Estrutura antiga: raiz + filho institucionais (com membro) e um grupo sistêmico (com membro)."""
    comum = criar_usuario("comum", departamento="Diretoria Antiga")
    raiz = criar_usuario("raiz", superusuario=True, departamento="Diretoria Antiga")
    with FabricaSessao() as sessao:
        antiga = Setor(nome="Diretoria Antiga")
        sessao.add(antiga)
        sessao.flush()
        filho = Setor(nome="Secretaria Executiva", setor_pai_id=antiga.id)
        grupo = Setor(nome="Auditores", sistemico=True)
        sessao.add_all([filho, grupo])
        sessao.flush()
        sessao.add_all([MembroSetor(setor_id=filho.id, usuario_id=comum), MembroSetor(setor_id=grupo.id, usuario_id=comum)])
        sessao.commit()
    return comum, raiz


def test_substitui_institucionais_mantem_sistemicos_e_limpa_departamentos(cliente):
    comum, raiz = _cenario()
    with FabricaSessao() as sessao:
        resumo = substituir_estrutura(sessao, ESTRUTURA_SPI, "teste")
        sessao.commit()
    assert resumo["setores_removidos"] == ["Diretoria Antiga", "Secretaria Executiva"]
    assert resumo["membros_removidos"] == 1 and resumo["departamentos_limpos"] == 2
    assert len(resumo["setores_criados"]) == contar(ESTRUTURA_SPI) == 28

    with FabricaSessao() as sessao:
        setores = {s.nome: s for s in sessao.scalars(select(Setor))}
        # O grupo sistêmico e o membro dele ficam
        assert setores["Auditores"].sistemico
        assert [(m.setor_id, m.usuario_id) for m in sessao.scalars(select(MembroSetor))] == [(setores["Auditores"].id, comum)]
        # Hierarquia nova
        raiz_spi = setores["Secretaria de Parcerias em Investimentos"]
        assert raiz_spi.setor_pai_id is None and setores["Ouvidoria"].setor_pai_id == raiz_spi.id
        assert setores["Coordenadoria de Finanças"].setor_pai_id == setores["Diretoria de Orçamento e Finanças"].id
        assert setores["Diretoria de Orçamento e Finanças"].setor_pai_id == setores["Subsecretaria de Gestão Corporativa"].id
        assert "Diretoria Antiga" not in setores
        # Departamentos limpos: todos precisam escolher o setor, inclusive o SuperRoot (só a conta root é dispensada)
        usuario, admin = sessao.get(Usuario, comum), sessao.get(Usuario, raiz)
        assert usuario.departamento == "" and admin.departamento == ""
        assert servico_perfil.perfil_restrito(usuario) and "departamento" in servico_perfil.campos_pendentes(usuario)
        assert servico_perfil.perfil_restrito(admin)
        # A combobox do perfil lista a hierarquia nova (sem o grupo sistêmico)
        opcoes = opcoes_departamento(sessao)
        assert opcoes[0].nome == "Secretaria de Parcerias em Investimentos" and opcoes[0].nivel == 0
        assert len(opcoes) == 28 and "Auditores" not in {o.nome for o in opcoes}
    # Na API, o usuário comum é mandado revisar o perfil
    r = cliente.get("/api/mensagens/resumo", headers=cabecalho(cliente, "comum"))
    assert r.status_code == 403 and r.json()["codigo"] == "revisao_perfil_obrigatoria"


def test_rodar_de_novo_recria_a_mesma_estrutura(cliente):
    with FabricaSessao() as sessao:
        substituir_estrutura(sessao, ESTRUTURA_SPI, "teste")
        sessao.commit()
        segundo = substituir_estrutura(sessao, ESTRUTURA_SPI, "teste")
        sessao.commit()
        assert len(segundo["setores_removidos"]) == 28 and len(segundo["setores_criados"]) == 28
        assert sessao.query(Setor).count() == 28
