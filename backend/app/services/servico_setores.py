# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de hierarquia, membros e exclusão de setores.
"""Setores: hierarquia institucional, grupos sistêmicos e membros.

As funções levantam `SetorNaoEncontrado` (vira 404) ou `ErroRegraSetor` (vira 400/409) e
deixam a tradução para HTTP com as rotas.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, aliased

from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.schemas.setores import DetalheSetor, GravacaoSetor, LeituraSetor
from app.services.servico_admin_usuarios import para_opcao
from app.services.servico_auditoria import auditar


class SetorNaoEncontrado(Exception):
    """O setor pedido não existe."""
    pass


class ErroRegraSetor(Exception):
    """Regra violada; `conflito=True` indica duplicidade (responde 409 em vez de 400)."""
    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


def obter_setor(sessao: Session, setor_id: int) -> Setor:
    """Setor pelo id, ou `SetorNaoEncontrado`."""
    setor = sessao.get(Setor, setor_id)
    if setor is None:
        raise SetorNaoEncontrado()
    return setor


def listar_setores(sessao: Session, busca: str | None = None) -> list[LeituraSetor]:
    """Lista os setores com nome do pai, nome do líder e contagens, em uma única consulta."""
    # `aliased` permite usar a tabela de setores duas vezes (o setor e o seu pai / os seus filhos)
    pai = aliased(Setor)
    filho = aliased(Setor)
    # Subconsultas que contam membros e subordinados de cada setor da linha
    total_membros = select(func.count()).where(MembroSetor.setor_id == Setor.id).scalar_subquery()
    total_subordinados = select(func.count()).select_from(filho).where(filho.setor_pai_id == Setor.id).scalar_subquery()
    # outerjoin: setores sem pai ou sem líder também aparecem
    consulta = (
        select(Setor, pai.nome, Usuario.nome_completo, Usuario.login, total_membros, total_subordinados)
        .outerjoin(pai, pai.id == Setor.setor_pai_id)
        .outerjoin(Usuario, Usuario.id == Setor.lider_id)
        .order_by(func.lower(Setor.nome))
    )
    # Filtro opcional pelo nome, sem diferenciar maiúsculas/minúsculas
    if busca and busca.strip():
        consulta = consulta.where(func.lower(Setor.nome).like(f"%{busca.strip().lower()}%"))
    return [
        LeituraSetor(
            id=s.id,
            nome=s.nome,
            setor_pai_id=s.setor_pai_id,
            setor_pai_nome=nome_pai,
            lider_id=s.lider_id,
            lider_nome=(nome_lider or login_lider) if s.lider_id else None,
            sistemico=s.sistemico,
            ativo=s.ativo,
            total_membros=membros,
            total_subordinados=subordinados,
            criado_em=s.criado_em,
            atualizado_em=s.atualizado_em,
        )
        for s, nome_pai, nome_lider, login_lider, membros, subordinados in sessao.execute(consulta)
    ]


def detalhar_setor(sessao: Session, setor_id: int) -> DetalheSetor:
    """Detalhe do setor: a linha da listagem mais a lista de membros."""
    obter_setor(sessao, setor_id)
    base = next(s for s in listar_setores(sessao) if s.id == setor_id)
    membros = sessao.scalars(
        select(Usuario)
        .join(MembroSetor, MembroSetor.usuario_id == Usuario.id)
        .where(MembroSetor.setor_id == setor_id)
        .order_by(func.lower(Usuario.nome_completo))
    )
    return DetalheSetor(**base.model_dump(), membros=[para_opcao(u) for u in membros])


def _validar(sessao: Session, dados: GravacaoSetor, setor_id: int | None) -> None:
    """Confere nome único, ausência de ciclos na hierarquia e existência do líder e dos membros."""
    duplicado = sessao.scalar(select(Setor.id).where(func.lower(Setor.nome) == dados.nome.lower()))
    if duplicado is not None and duplicado != setor_id:
        raise ErroRegraSetor("Já existe um setor com este nome.", conflito=True)
    # Sobe pela cadeia de pais a partir do pai escolhido; se passar pelo próprio setor, seria um ciclo
    if dados.setor_pai_id is not None:
        # Impede ciclos: o pai não pode ser o próprio setor nem um descendente dele
        atual: int | None = dados.setor_pai_id
        while atual is not None:
            if atual == setor_id:
                raise ErroRegraSetor("O setor pai não pode ser o próprio setor nem um setor subordinado a ele.")
            no = sessao.get(Setor, atual)
            if no is None:
                raise ErroRegraSetor("Setor pai inválido.")
            atual = no.setor_pai_id
    # Todos os ids informados (membros e líder) precisam existir
    ids_usuarios = set(dados.membros_ids) | ({dados.lider_id} if dados.lider_id else set())
    if ids_usuarios:
        encontrados = set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(ids_usuarios))))
        if encontrados != ids_usuarios:
            raise ErroRegraSetor("Líder ou membros inválidos.")


def _definir_membros(sessao: Session, setor_id: int, membros_ids: list[int]) -> None:
    """Substitui a lista de membros: apaga os atuais e insere os informados (sem repetição)."""
    sessao.execute(delete(MembroSetor).where(MembroSetor.setor_id == setor_id))
    for usuario_id in sorted(set(membros_ids)):
        sessao.add(MembroSetor(setor_id=setor_id, usuario_id=usuario_id))


def criar_setor(sessao: Session, dados: GravacaoSetor, autor: str) -> Setor:
    """Cria o setor, define os membros e registra na auditoria."""
    _validar(sessao, dados, None)
    setor = Setor(nome=dados.nome, setor_pai_id=dados.setor_pai_id, lider_id=dados.lider_id, sistemico=dados.sistemico, ativo=dados.ativo)
    sessao.add(setor)
    # flush envia o INSERT para obter o id do setor antes de inserir os membros
    sessao.flush()
    _definir_membros(sessao, setor.id, dados.membros_ids)
    auditar(sessao, autor, "setor.criar", setor.nome, f"id={setor.id} membros={len(set(dados.membros_ids))}")
    sessao.commit()
    return setor


def alterar_setor(sessao: Session, setor_id: int, dados: GravacaoSetor, autor: str) -> Setor:
    """Altera os dados do setor e substitui os membros."""
    setor = obter_setor(sessao, setor_id)
    _validar(sessao, dados, setor_id)
    for campo in ("nome", "setor_pai_id", "lider_id", "sistemico", "ativo"):
        setattr(setor, campo, getattr(dados, campo))
    _definir_membros(sessao, setor.id, dados.membros_ids)
    auditar(sessao, autor, "setor.alterar", setor.nome, f"id={setor.id} membros={len(set(dados.membros_ids))}")
    sessao.commit()
    return setor


def excluir_setor(sessao: Session, setor_id: int, autor: str) -> None:
    """Exclui o setor, desde que não tenha subordinados nem membros."""
    setor = obter_setor(sessao, setor_id)
    if sessao.scalar(select(func.count()).where(Setor.setor_pai_id == setor_id)):
        raise ErroRegraSetor("Não é possível excluir um setor que possui setores subordinados.")
    if sessao.scalar(select(func.count()).where(MembroSetor.setor_id == setor_id)):
        raise ErroRegraSetor("Não é possível excluir um setor que possui membros.")
    auditar(sessao, autor, "setor.excluir", setor.nome, f"id={setor.id}")
    sessao.delete(setor)
    sessao.commit()
