"""
===============================================================================
ARQUIVO: test_departamento_setor.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar que o Departamento validado no perfil do usuário define de qual
setor ele é membro (Departamento <-> setor).

RESUMO TÉCNICO:
Cria setores, uma servidora (Ana), uma chefe e uma analista da CGP. A Ana
altera o Departamento no perfil (/api/autenticacao/perfil); a CGP valida
ou recusa com correção (/api/rh/cadastro/alteracoes). O teste lê a tabela
MembroSetor direto no banco para conferir entradas e saídas. Também cobre
alteração direta (CGP e administrador), Departamento sem setor
correspondente e renomeação do setor.

FINALIDADE DE NEGÓCIO:
A participação no setor é usada pela ACL (controle de acesso por setor).
Ela só deve mudar quando o Departamento passa a valer (após validação da
CGP, a Coordenadoria de Gestão de Pessoas), sem mexer em setores
sistêmicos montados à mão.

CONTEXTO NO SISTEMA:
Perfil institucional (autenticação), cadastro do RH (pendências e
validação), modelos Usuario e MembroSetor, rotas de setores e usuários.
Apoios em tests/apoio_rh.py e tests/conftest.py; e-mails pelo SMTP simulado.

===============================================================================
"""

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.setor import MembroSetor
from app.models.usuario import Usuario
from tests.apoio_rh import criar_cgp, simular_smtp
from tests.conftest import PERFIL_COMPLETO, cabecalho, criar_usuario
from tests.test_smtp import dados_servidor

PERFIL = "/api/autenticacao/perfil"
# Id da chefe criado na fixture cenario; o perfil exige o superior imediato (gestor_id).
CHEFE = 0


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    """Troca o envio de e-mail por um SMTP simulado em todos os testes do arquivo (autouse)."""
    simular_smtp(monkeypatch)


@pytest.fixture
def cenario(cliente, admin):
    """Dois setores, uma servidora (Ana) e uma analista da CGP."""
    chefe = criar_usuario("chefe", nome_completo="Chefe Silva", email="chefe@sp.gov.br")
    ana = criar_usuario("ana", nome_completo="Ana Souza", email="ana@sp.gov.br")
    rh = criar_usuario("rh", nome_completo="Rita RH", email="rh@sp.gov.br")
    criar_cgp(rh)
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    setores = {n: cliente.post("/api/setores", json={"nome": n}, headers=admin).json()["id"] for n in ("Setor A", "Setor B")}
    global CHEFE
    CHEFE = chefe  # o superior imediato é obrigatório no perfil
    return ana, setores, {"ana": cabecalho(cliente, "ana"), "rh": cabecalho(cliente, "rh")}


def _perfil(**extras):
    """Perfil atual da Ana com as alterações informadas."""
    return {**PERFIL_COMPLETO, "nome_completo": "Ana Souza", "email": "ana@sp.gov.br", "gestor_id": CHEFE, **extras}


def _setores_de(usuario_id: int) -> set[int]:
    """Ids dos setores dos quais o usuário é membro, lidos direto da tabela MembroSetor.

    FabricaSessao abre uma sessão do SQLAlchemy (conexão com o banco) que fecha
    sozinha no fim do bloco with.
    """
    with FabricaSessao() as sessao:
        return set(sessao.scalars(select(MembroSetor.setor_id).where(MembroSetor.usuario_id == usuario_id)))


def _validar(cliente, h, campo="departamento"):
    """A CGP valida a alteração pendente do campo indicado (padrão: departamento); devolve a resposta HTTP."""
    pendentes = {a["campo"]: a["id"] for a in cliente.get("/api/rh/cadastro/pendencias", headers=h["rh"]).json()[0]["alteracoes"]}
    return cliente.post(f"/api/rh/cadastro/alteracoes/{pendentes[campo]}/validar", headers=h["rh"])


def test_validacao_da_cgp_inclui_o_usuario_no_setor_e_tira_do_anterior(cliente, cenario):
    """Enquanto pendente, nada muda; validado, entra no setor; ao trocar de Departamento, sai do anterior."""
    ana, setores, h = cenario
    cliente.put(PERFIL, json=_perfil(departamento="Setor A"), headers=h["ana"])
    # Pendente: o Departamento em vigor não mudou, então ainda não é membro
    assert _setores_de(ana) == set()
    assert _validar(cliente, h).status_code == 200
    assert _setores_de(ana) == {setores["Setor A"]}
    # Trocar de setor: entra no novo e sai do anterior
    cliente.put(PERFIL, json=_perfil(departamento="setor b"), headers=h["ana"])
    assert _validar(cliente, h).status_code == 200
    assert _setores_de(ana) == {setores["Setor B"]}


def test_recusa_com_correcao_tambem_ajusta_o_setor(cliente, cenario):
    """Recusa com valor corrigido pela CGP também atualiza o setor (vale o valor corrigido)."""
    ana, setores, h = cenario
    cliente.put(PERFIL, json=_perfil(departamento="Setor A"), headers=h["ana"])
    pendentes = {a["campo"]: a["id"] for a in cliente.get("/api/rh/cadastro/pendencias", headers=h["rh"]).json()[0]["alteracoes"]}
    r = cliente.post(f"/api/rh/cadastro/alteracoes/{pendentes['departamento']}/recusar",
                     json={"justificativa": "Você atua no Setor B.", "valor_corrigido": "Setor B"}, headers=h["rh"])
    assert r.status_code == 200
    assert _setores_de(ana) == {setores["Setor B"]}


def test_alteracao_direta_da_cgp_e_do_administrador(cliente, admin, cenario):
    """A CGP no próprio perfil e o administrador no perfil de outra pessoa alteram o setor na hora."""
    ana, setores, h = cenario
    # CGP altera o próprio perfil: vale na hora
    with FabricaSessao() as sessao:
        rh_id = sessao.scalar(select(Usuario.id).where(Usuario.login == "rh"))
    r = cliente.put(PERFIL, json={**PERFIL_COMPLETO, "nome_completo": "Rita RH", "email": "rh@sp.gov.br", "gestor_id": CHEFE, "departamento": "Setor A"}, headers=h["rh"])
    assert r.status_code == 200
    # A analista da CGP já pertence ao setor da CGP (criado por criar_cgp); o novo vínculo se soma a ele
    assert setores["Setor A"] in _setores_de(rh_id)
    # Administrador edita o perfil de outra pessoa
    alteracao = {"ativo": True, "superusuario": False, "perfil": _perfil(departamento="Setor B")}
    assert cliente.put(f"/api/usuarios/{ana}", json=alteracao, headers=admin).status_code == 200
    assert _setores_de(ana) == {setores["Setor B"]}


def test_departamento_sem_setor_correspondente_nao_cria_nem_remove_nada(cliente, admin, cenario):
    """Departamento sem setor de mesmo nome tira do setor anterior, mas não cria setor nem mexe em setor sistêmico."""
    ana, setores, h = cenario
    # Participação manual em um setor sistêmico não é tocada pela sincronização
    sistemico = cliente.post("/api/setores", json={"nome": "Auditores", "sistemico": True, "membros_ids": [ana]}, headers=admin).json()["id"]
    cliente.put(PERFIL, json=_perfil(departamento="Setor A"), headers=h["ana"])
    _validar(cliente, h)
    cliente.put(PERFIL, json=_perfil(departamento="Texto que não é setor"), headers=h["ana"])
    assert _validar(cliente, h).status_code == 200
    assert _setores_de(ana) == {sistemico}


def test_renomear_o_setor_acompanha_o_departamento_dos_usuarios(cliente, admin, cenario):
    """Renomear o setor atualiza o Departamento dos membros e mantém a participação."""
    ana, setores, h = cenario
    cliente.put(PERFIL, json=_perfil(departamento="Setor A"), headers=h["ana"])
    _validar(cliente, h)
    r = cliente.put(f"/api/setores/{setores['Setor A']}", json={"nome": "Setor Alfa", "membros_ids": [ana]}, headers=admin)
    assert r.status_code == 200
    assert cliente.get(PERFIL, headers=h["ana"]).json()["departamento"] == "Setor Alfa"
    assert _setores_de(ana) == {setores["Setor A"]}
