# Criado por José Eduardo Santana Martins
# Este arquivo serve para dizer o que cada pessoa pode fazer no módulo Chamados e quais chamados ela enxerga.
"""Papéis e visibilidade dos Chamados.

Recurso da ACL `chamados`, em três níveis:
- **Leitura** (abrir): abre chamados e acompanha os seus (como solicitante, pelo setor solicitante ou em cópia).
- **Modificação** (atender): além disso, vê a fila dos seus setores, assume, responde e soluciona.
- **Controle total** (administrar): vê todos os chamados e cuida dos Parâmetros.

**Módulo fechado até a virada:** diferente dos outros recursos, sem nenhuma regra nem perfil na ACL **só o SuperRoot** entra
(o GLPI continua em uso até lá). Ao criar a primeira regra ou perfil, vale o que a ACL disser.

Quem vê um chamado:
- o solicitante, os membros do setor solicitante e o responsável pelo atendimento;
- quem está **em cópia** (a pessoa, ou membro de um setor em cópia);
- quem precisa **aprovar** (a pessoa, ou membro do setor aprovador);
- quem atende e é membro do setor responsável (ou líder de um setor acima dele);
- quem atende e é membro de um setor com "ver todos" nos ajustes de atendimento;
- quem administra (Controle total) e o SuperRoot.
"""

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl
from app.models.chamados import AtorChamado, Chamado, SetorAtendimentoChamados, ValidacaoChamado
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import servico_acl

RECURSO_ACL = "chamados"


@dataclass(frozen=True)
class Papeis:
    """O que a pessoa pode fazer no módulo."""
    abrir: bool
    atender: bool
    administrar: bool

    @property
    def algum(self) -> bool:
        return self.abrir or self.atender or self.administrar


def papeis(sessao: Session, usuario: Usuario) -> Papeis:
    """Papéis pela ACL. As colunas do perfil são independentes, mas aqui quem atende também abre e quem administra faz tudo."""
    if usuario.superusuario:
        return Papeis(True, True, True)
    if not servico_acl.possui_regras(sessao, RECURSO_ACL):
        # Fechado até a virada: sem regras, ninguém além do SuperRoot
        return Papeis(False, False, False)
    administrar = servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.CONTROLE_TOTAL)
    atender = administrar or servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.MODIFICACAO)
    abrir = atender or servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.LEITURA)
    return Papeis(abrir, atender, administrar)


def setores_do_usuario(sessao: Session, usuario: Usuario) -> set[int]:
    """Setores de que a pessoa é membro (ativos)."""
    return set(sessao.scalars(
        select(MembroSetor.setor_id).join(Setor, Setor.id == MembroSetor.setor_id).where(MembroSetor.usuario_id == usuario.id, Setor.ativo.is_(True))
    ))


def _descendentes(sessao: Session, raizes: set[int]) -> set[int]:
    """Setores abaixo das `raizes` (inclusive), percorrendo a hierarquia."""
    resultado, fronteira = set(raizes), set(raizes)
    while fronteira:
        filhos = set(sessao.scalars(select(Setor.id).where(Setor.setor_pai_id.in_(fronteira)))) - resultado
        resultado |= filhos
        fronteira = filhos
    return resultado


@dataclass(frozen=True)
class Alcance:
    """Quais chamados a pessoa enxerga: `todos` ou os dos setores em `setores_atendidos`, mais os em que ela é parte."""
    usuario_id: int
    todos: bool
    setores_membro: frozenset[int]
    setores_atendidos: frozenset[int]


def alcance(sessao: Session, usuario: Usuario, p: Papeis | None = None) -> Alcance:
    """Calcula uma vez por requisição o que a pessoa enxerga."""
    p = p or papeis(sessao, usuario)
    membro = setores_do_usuario(sessao, usuario)
    if p.administrar:
        return Alcance(usuario.id, True, frozenset(membro), frozenset())
    if not p.atender:
        return Alcance(usuario.id, False, frozenset(membro), frozenset())
    ve_todos = bool(membro) and sessao.scalar(
        select(SetorAtendimentoChamados.setor_id).where(SetorAtendimentoChamados.setor_id.in_(membro), SetorAtendimentoChamados.ve_todos.is_(True)).limit(1)
    ) is not None
    # O líder enxerga também os setores abaixo do dele
    liderados = set(sessao.scalars(select(Setor.id).where(Setor.lider_id == usuario.id, Setor.ativo.is_(True))))
    atendidos = membro | _descendentes(sessao, liderados) if liderados else membro
    return Alcance(usuario.id, ve_todos, frozenset(membro), frozenset(atendidos))


def filtro_visibilidade(a: Alcance):
    """Condição SQL dos chamados que a pessoa enxerga (para listas)."""
    if a.todos:
        return Chamado.id.is_not(None)
    condicoes = [Chamado.solicitante_id == a.usuario_id, Chamado.responsavel_id == a.usuario_id, Chamado.id.in_(em_copia(a)), Chamado.id.in_(aprovador(a))]
    if a.setores_membro:
        condicoes.append(Chamado.setor_solicitante_id.in_(a.setores_membro))
    if a.setores_atendidos:
        condicoes.append(Chamado.setor_id.in_(a.setores_atendidos))
    return or_(*condicoes)


def em_copia(a: Alcance):
    """Subconsulta: chamados em que a pessoa (ou um setor dela) está em cópia."""
    alvo = AtorChamado.usuario_id == a.usuario_id
    if a.setores_membro:
        alvo = or_(alvo, AtorChamado.setor_id.in_(a.setores_membro))
    return select(AtorChamado.chamado_id).where(alvo)


def aprovador(a: Alcance):
    """Subconsulta: chamados em que a pessoa (ou um setor dela) foi chamada a aprovar."""
    alvo = ValidacaoChamado.alvo_usuario_id == a.usuario_id
    if a.setores_membro:
        alvo = or_(alvo, ValidacaoChamado.alvo_setor_id.in_(a.setores_membro))
    return select(ValidacaoChamado.chamado_id).where(alvo)


def e_aprovador(a: Alcance, chamado: Chamado) -> bool:
    return any(v.alvo_usuario_id == a.usuario_id or (v.alvo_setor_id is not None and v.alvo_setor_id in a.setores_membro) for v in chamado.validacoes)


def esta_em_copia(a: Alcance, chamado: Chamado) -> bool:
    return any(x.usuario_id == a.usuario_id or (x.setor_id is not None and x.setor_id in a.setores_membro) for x in chamado.atores)


def ve(a: Alcance, chamado: Chamado) -> bool:
    """A pessoa enxerga este chamado?"""
    return (
        a.todos
        or a.usuario_id in (chamado.solicitante_id, chamado.responsavel_id)
        or (chamado.setor_solicitante_id is not None and chamado.setor_solicitante_id in a.setores_membro)
        or chamado.setor_id in a.setores_atendidos
        or esta_em_copia(a, chamado)
        or e_aprovador(a, chamado)
    )


def atende(a: Alcance, p: Papeis, chamado: Chamado) -> bool:
    """A pessoa atende este chamado (vê o privado, responde como responsável, assume e soluciona)?"""
    if not p.atender:
        return False
    return a.todos or chamado.setor_id in a.setores_atendidos or chamado.responsavel_id == a.usuario_id
