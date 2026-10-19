# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular o nível de acesso efetivo de um usuário em cada recurso (perfil ativo, setores e regras diretas).
"""Cálculo do nível de acesso efetivo (ACL).

Política:
- SuperRoot sempre tem CONTROLE_TOTAL.
- Recurso não cadastrado ou inativo, ou **sem nenhuma regra e sem nenhum perfil com direito nele**: aberto (CONTROLE_TOTAL para autenticados).
- Com ao menos uma regra ou um direito de perfil, o recurso vira lista positiva: só acessa quem estiver contemplado.
- O nível é a **soma das origens: vale o maior** entre (1) o **perfil ativo** do usuário, (2) as regras dos **setores** ativos de que ele é membro
  e (3) as regras **diretas** ao usuário. (Antes dos perfis, a regra direta prevalecia sobre a de setor; agora as três se somam.)
- O usuário pode ter vários perfis, mas só **um é o ativo**: o padrão ou o escolhido no menu do usuário (claim `pa` do token).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl, PerfilAcl, PerfilDireito, PerfilSetor, RecursoAcl, RegraAcl, UsuarioPerfil, acl_regras_setores, acl_regras_usuarios
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services.acl_acoes import acao_da_porta

ORIGEM_PERFIL, ORIGEM_SETOR, ORIGEM_DIRETA = "perfil", "setor", "direta"


def _nivel_continuo(slug: str, acoes: set[str]) -> str | None:
    """Maior nível cujas portas (e as dos níveis abaixo) o perfil abre com as `acoes` marcadas.

    Os perfis têm ações independentes, mas os pontos do código que comparam um nível (`resolver_acesso`) precisam de um só valor:
    aqui vale o lado seguro, só sobe quando **todas** as portas até ele estão abertas. A checagem exata de uma porta é `pode_porta`.
    """
    nivel = None
    for candidato in NivelAcl.TODOS:
        acao = acao_da_porta(slug, candidato)
        if acao is None or acao not in acoes:
            break
        nivel = candidato
    return nivel


def _maior_nivel(niveis: list[str]) -> str | None:
    """Maior nível da lista (LEITURA < MODIFICACAO < CONTROLE_TOTAL), ou None se a lista estiver vazia."""
    return max(niveis, key=NivelAcl.posicao) if niveis else None


# --- Perfil ativo -------------------------------------------------------------------------------

def perfis_do_usuario(sessao: Session, usuario_id: int) -> list[PerfilAcl]:
    """Perfis **ativos** do usuário (os atribuídos a ele e os que recebe pelos setores/grupos de que é membro), em ordem de nome."""
    diretos = select(UsuarioPerfil.perfil_id).where(UsuarioPerfil.usuario_id == usuario_id)
    por_setor = (
        select(PerfilSetor.perfil_id).join(MembroSetor, MembroSetor.setor_id == PerfilSetor.setor_id).join(Setor, Setor.id == MembroSetor.setor_id)
        .where(MembroSetor.usuario_id == usuario_id, Setor.ativo.is_(True))
    )
    return list(sessao.scalars(
        select(PerfilAcl).where(PerfilAcl.ativo.is_(True), PerfilAcl.id.in_(diretos.union(por_setor))).order_by(func.lower(PerfilAcl.nome))
    ))


def perfis_por_setor(sessao: Session, usuario_id: int) -> dict[int, list[str]]:
    """Perfis que o usuário recebe pelos setores/grupos: `{perfil_id: [nomes dos setores]}` (para mostrar de onde vem)."""
    resultado: dict[int, list[str]] = {}
    for perfil_id, nome in sessao.execute(
        select(PerfilSetor.perfil_id, Setor.nome).join(MembroSetor, MembroSetor.setor_id == PerfilSetor.setor_id).join(Setor, Setor.id == MembroSetor.setor_id)
        .where(MembroSetor.usuario_id == usuario_id, Setor.ativo.is_(True)).order_by(Setor.nome)
    ):
        resultado.setdefault(perfil_id, []).append(nome)
    return resultado


def perfil_padrao_id(sessao: Session, usuario_id: int) -> int | None:
    """Perfil padrão do usuário (o marcado como padrão; senão o primeiro por nome), entre os ativos."""
    perfis = perfis_do_usuario(sessao, usuario_id)
    if not perfis:
        return None
    padrao = set(sessao.scalars(select(UsuarioPerfil.perfil_id).where(UsuarioPerfil.usuario_id == usuario_id, UsuarioPerfil.padrao.is_(True))))
    return next((p.id for p in perfis if p.id in padrao), perfis[0].id)


def perfil_ativo_id(sessao: Session, usuario: Usuario) -> int | None:
    """Perfil ativo do usuário: o escolhido na sessão (`usuario.perfil_ativo_id`, validado ao autenticar) ou o padrão."""
    escolhido = getattr(usuario, "perfil_ativo_id", None)
    if escolhido is not None:
        return escolhido
    return perfil_padrao_id(sessao, usuario.id)


# --- Cálculo ------------------------------------------------------------------------------------

def acoes_do_perfil(sessao: Session, perfil_id: int, recursos_ids: list[int] | None = None) -> dict[int, set[str]]:
    """Ações que o perfil (se ativo) concede em cada recurso: `{recurso_id: {ações}}`."""
    consulta = (
        select(PerfilDireito.recurso_id, PerfilDireito.nivel).join(PerfilAcl, PerfilAcl.id == PerfilDireito.perfil_id)
        .where(PerfilDireito.perfil_id == perfil_id, PerfilAcl.ativo.is_(True))
    )
    if recursos_ids is not None:
        consulta = consulta.where(PerfilDireito.recurso_id.in_(recursos_ids))
    resultado: dict[int, set[str]] = {}
    for recurso_id, acao in sessao.execute(consulta):
        resultado.setdefault(recurso_id, set()).add(acao)
    return resultado


def pode_porta(sessao: Session, usuario: Usuario, slug: str, nivel: str) -> bool:
    """O usuário passa pela porta `nivel` do módulo? É a checagem das rotas (`exigir_acl`).

    Passa se: é SuperRoot; o módulo está aberto; as regras de setor/diretas dão nível >= `nivel` (hierárquicas, como sempre);
    ou o perfil ativo tem **exatamente a ação** que abre essa porta (ações de perfil são independentes).
    """
    if usuario.superusuario:
        return True
    recurso = sessao.scalar(select(RecursoAcl).where(func.lower(RecursoAcl.slug) == slug.lower(), RecursoAcl.ativo.is_(True)))
    if recurso is None:
        return True
    perfil_id = perfil_ativo_id(sessao, usuario)
    _, origens = _calcular(sessao, usuario.id, None, [recurso.id])[recurso.id]
    if not origens and _aberto(sessao, recurso.id):
        return True
    if any(NivelAcl.posicao(n) >= NivelAcl.posicao(nivel) for n in origens.values()):
        return True
    acao = acao_da_porta(slug, nivel)
    return bool(perfil_id is not None and acao and acao in acoes_do_perfil(sessao, perfil_id, [recurso.id]).get(recurso.id, set()))


def tem_acao_no_perfil(sessao: Session, usuario: Usuario, slug: str, acao: str) -> bool:
    """O perfil ativo do usuário tem esta ação própria do módulo (ex.: `LANCAR_OB`)? Vale só pelo perfil; SuperRoot sempre tem."""
    if usuario.superusuario:
        return True
    perfil_id = perfil_ativo_id(sessao, usuario)
    recurso = sessao.scalar(select(RecursoAcl).where(func.lower(RecursoAcl.slug) == slug.lower(), RecursoAcl.ativo.is_(True)))
    if perfil_id is None or recurso is None:
        return False
    return acao in acoes_do_perfil(sessao, perfil_id, [recurso.id]).get(recurso.id, set())


def _aberto(sessao: Session, recurso_id: int) -> bool:
    """Recurso sem nenhuma regra e sem direito de perfil ativo."""
    if sessao.scalar(select(func.count(RegraAcl.id)).where(RegraAcl.recurso_id == recurso_id)):
        return False
    return not sessao.scalar(
        select(func.count()).select_from(PerfilDireito).join(PerfilAcl, PerfilAcl.id == PerfilDireito.perfil_id)
        .where(PerfilDireito.recurso_id == recurso_id, PerfilAcl.ativo.is_(True)))


def possui_regras(sessao: Session, slug: str) -> bool:
    """O recurso (ativo) tem ao menos uma regra ou um direito de perfil (é lista positiva)?"""
    regras = sessao.scalar(
        select(func.count(RegraAcl.id)).join(RecursoAcl, RecursoAcl.id == RegraAcl.recurso_id)
        .where(RecursoAcl.slug == slug, RecursoAcl.ativo.is_(True))
    )
    if regras:
        return True
    return bool(sessao.scalar(
        select(func.count()).select_from(PerfilDireito).join(RecursoAcl, RecursoAcl.id == PerfilDireito.recurso_id)
        .join(PerfilAcl, PerfilAcl.id == PerfilDireito.perfil_id)
        .where(RecursoAcl.slug == slug, RecursoAcl.ativo.is_(True), PerfilAcl.ativo.is_(True))
    ))


def resolver_acesso(sessao: Session, usuario: Usuario, slug: str) -> str | None:
    """Nível do usuário no recurso identificado pelo `slug` (None = sem acesso)."""
    if usuario.superusuario:
        return NivelAcl.CONTROLE_TOTAL
    # Procura o recurso ativo pelo slug, sem diferenciar maiúsculas/minúsculas
    recurso = sessao.scalar(
        select(RecursoAcl).where(func.lower(RecursoAcl.slug) == slug.lower(), RecursoAcl.ativo.is_(True))
    )
    # Recurso não cadastrado ou inativo não restringe nada
    if recurso is None:
        return NivelAcl.CONTROLE_TOTAL
    nivel, _ = _calcular(sessao, usuario.id, perfil_ativo_id(sessao, usuario), [recurso.id])[recurso.id]
    return nivel


def _calcular(sessao: Session, usuario_id: int, perfil_id: int | None, recursos_ids: list[int]) -> dict[int, tuple[str | None, dict[str, str]]]:
    """Nível e origens (`{origem: nível}`) do usuário em cada recurso, carregando tudo de uma vez.

    Recurso sem regra e sem direito de perfil → aberto (CONTROLE_TOTAL, sem origens).
    """
    if not recursos_ids:
        return {}
    com_regra = set(sessao.scalars(select(RegraAcl.recurso_id).where(RegraAcl.recurso_id.in_(recursos_ids))))
    com_direito = set(sessao.scalars(
        select(PerfilDireito.recurso_id).join(PerfilAcl, PerfilAcl.id == PerfilDireito.perfil_id)
        .where(PerfilDireito.recurso_id.in_(recursos_ids), PerfilAcl.ativo.is_(True))
    ))
    diretos: dict[int, list[str]] = {}
    for recurso_id, nivel in sessao.execute(
        select(RegraAcl.recurso_id, RegraAcl.nivel).join(acl_regras_usuarios, acl_regras_usuarios.c.regra_id == RegraAcl.id)
        .where(RegraAcl.recurso_id.in_(recursos_ids), acl_regras_usuarios.c.usuario_id == usuario_id)
    ):
        diretos.setdefault(recurso_id, []).append(nivel)
    por_setor: dict[int, list[str]] = {}
    for recurso_id, nivel in sessao.execute(
        select(RegraAcl.recurso_id, RegraAcl.nivel).join(acl_regras_setores, acl_regras_setores.c.regra_id == RegraAcl.id)
        .join(MembroSetor, MembroSetor.setor_id == acl_regras_setores.c.setor_id).join(Setor, Setor.id == MembroSetor.setor_id)
        .where(RegraAcl.recurso_id.in_(recursos_ids), MembroSetor.usuario_id == usuario_id, Setor.ativo.is_(True))
    ):
        por_setor.setdefault(recurso_id, []).append(nivel)
    do_perfil: dict[int, str] = {}
    if perfil_id is not None:
        slugs = dict(sessao.execute(select(RecursoAcl.id, RecursoAcl.slug).where(RecursoAcl.id.in_(recursos_ids))).all())
        for recurso_id, acoes in acoes_do_perfil(sessao, perfil_id, recursos_ids).items():
            nivel = _nivel_continuo(slugs[recurso_id], acoes)
            if nivel is not None:
                do_perfil[recurso_id] = nivel
    resultado: dict[int, tuple[str | None, dict[str, str]]] = {}
    for recurso_id in recursos_ids:
        if recurso_id not in com_regra and recurso_id not in com_direito:
            resultado[recurso_id] = (NivelAcl.CONTROLE_TOTAL, {})
            continue
        origens: dict[str, str] = {}
        if recurso_id in do_perfil:
            origens[ORIGEM_PERFIL] = do_perfil[recurso_id]
        if por_setor.get(recurso_id):
            origens[ORIGEM_SETOR] = _maior_nivel(por_setor[recurso_id])
        if diretos.get(recurso_id):
            origens[ORIGEM_DIRETA] = _maior_nivel(diretos[recurso_id])
        resultado[recurso_id] = (_maior_nivel(list(origens.values())), origens)
    return resultado


def acessos_detalhados(sessao: Session, usuario: Usuario, perfil_id: int | None = None) -> list[tuple[RecursoAcl, str | None, dict[str, str]]]:
    """Nível efetivo e origem do usuário em cada recurso ativo. `perfil_id` simula outro perfil ativo (padrão: o ativo do usuário)."""
    recursos = list(sessao.scalars(select(RecursoAcl).where(RecursoAcl.ativo.is_(True)).order_by(func.lower(RecursoAcl.nome))))
    if usuario.superusuario:
        return [(r, NivelAcl.CONTROLE_TOTAL, {}) for r in recursos]
    ativo = perfil_id if perfil_id is not None else perfil_ativo_id(sessao, usuario)
    calculo = _calcular(sessao, usuario.id, ativo, [r.id for r in recursos])
    return [(r, calculo[r.id][0], calculo[r.id][1]) for r in recursos]


def acessos_efetivos(sessao: Session, usuario: Usuario) -> list[tuple[RecursoAcl, str | None]]:
    """Nível efetivo do usuário em cada recurso ativo (None = sem acesso)."""
    return [(r, nivel) for r, nivel, _ in acessos_detalhados(sessao, usuario)]
