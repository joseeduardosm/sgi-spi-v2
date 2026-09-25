"""Setores: hierarquia institucional, grupos sistêmicos e membros."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, aliased

from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.schemas.setores import DetalheSetor, GravacaoSetor, LeituraSetor
from app.services.servico_admin_usuarios import para_opcao
from app.services.servico_auditoria import auditar


class SetorNaoEncontrado(Exception):
    pass


class ErroRegraSetor(Exception):
    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


def obter_setor(sessao: Session, setor_id: int) -> Setor:
    setor = sessao.get(Setor, setor_id)
    if setor is None:
        raise SetorNaoEncontrado()
    return setor


def listar_setores(sessao: Session, busca: str | None = None) -> list[LeituraSetor]:
    pai = aliased(Setor)
    filho = aliased(Setor)
    total_membros = select(func.count()).where(MembroSetor.setor_id == Setor.id).scalar_subquery()
    total_subordinados = select(func.count()).select_from(filho).where(filho.setor_pai_id == Setor.id).scalar_subquery()
    consulta = (
        select(Setor, pai.nome, Usuario.nome_completo, Usuario.login, total_membros, total_subordinados)
        .outerjoin(pai, pai.id == Setor.setor_pai_id)
        .outerjoin(Usuario, Usuario.id == Setor.lider_id)
        .order_by(func.lower(Setor.nome))
    )
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
    duplicado = sessao.scalar(select(Setor.id).where(func.lower(Setor.nome) == dados.nome.lower()))
    if duplicado is not None and duplicado != setor_id:
        raise ErroRegraSetor("Já existe um setor com este nome.", conflito=True)
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
    ids_usuarios = set(dados.membros_ids) | ({dados.lider_id} if dados.lider_id else set())
    if ids_usuarios:
        encontrados = set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(ids_usuarios))))
        if encontrados != ids_usuarios:
            raise ErroRegraSetor("Líder ou membros inválidos.")


def _definir_membros(sessao: Session, setor_id: int, membros_ids: list[int]) -> None:
    sessao.execute(delete(MembroSetor).where(MembroSetor.setor_id == setor_id))
    for usuario_id in sorted(set(membros_ids)):
        sessao.add(MembroSetor(setor_id=setor_id, usuario_id=usuario_id))


def criar_setor(sessao: Session, dados: GravacaoSetor, autor: str) -> Setor:
    _validar(sessao, dados, None)
    setor = Setor(nome=dados.nome, setor_pai_id=dados.setor_pai_id, lider_id=dados.lider_id, sistemico=dados.sistemico, ativo=dados.ativo)
    sessao.add(setor)
    sessao.flush()
    _definir_membros(sessao, setor.id, dados.membros_ids)
    auditar(sessao, autor, "setor.criar", setor.nome, f"id={setor.id} membros={len(set(dados.membros_ids))}")
    sessao.commit()
    return setor


def alterar_setor(sessao: Session, setor_id: int, dados: GravacaoSetor, autor: str) -> Setor:
    setor = obter_setor(sessao, setor_id)
    _validar(sessao, dados, setor_id)
    for campo in ("nome", "setor_pai_id", "lider_id", "sistemico", "ativo"):
        setattr(setor, campo, getattr(dados, campo))
    _definir_membros(sessao, setor.id, dados.membros_ids)
    auditar(sessao, autor, "setor.alterar", setor.nome, f"id={setor.id} membros={len(set(dados.membros_ids))}")
    sessao.commit()
    return setor


def excluir_setor(sessao: Session, setor_id: int, autor: str) -> None:
    setor = obter_setor(sessao, setor_id)
    if sessao.scalar(select(func.count()).where(Setor.setor_pai_id == setor_id)):
        raise ErroRegraSetor("Não é possível excluir um setor que possui setores subordinados.")
    if sessao.scalar(select(func.count()).where(MembroSetor.setor_id == setor_id)):
        raise ErroRegraSetor("Não é possível excluir um setor que possui membros.")
    auditar(sessao, autor, "setor.excluir", setor.nome, f"id={setor.id}")
    sessao.delete(setor)
    sessao.commit()
