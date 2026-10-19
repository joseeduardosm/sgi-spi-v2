# Criado por José Eduardo Santana Martins
# Este arquivo serve para administrar os perfis de acesso: cadastro, matriz de direitos e usuários de cada perfil (SuperRoot).
"""Administração dos perfis de acesso (SuperRoot).

Um perfil é um conjunto de direitos (módulo × nível) atribuível a vários usuários. O cálculo do acesso efetivo fica em `servico_acl`;
aqui ficam só o cadastro e as validações. Toda gravação é auditada (`acl.perfil.*`).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl, PerfilAcl, PerfilDireito, PerfilSetor, RecursoAcl, UsuarioPerfil
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.acl import (
    AcaoModulo, DetalhePerfil, SetorDoPerfil, DireitoPerfilModulo, GravacaoPerfil, GravacaoPerfisDoUsuario, LeituraPerfil, PerfilDoUsuario, UsuarioDoPerfil,
)
from app.services.acl_acoes import acoes_do_recurso, codigos_do_recurso
from app.services.servico_admin_acl import AclNaoEncontrado, ErroRegraAcl
from app.services.servico_auditoria import auditar


def obter_perfil(sessao: Session, perfil_id: int) -> PerfilAcl:
    perfil = sessao.get(PerfilAcl, perfil_id)
    if perfil is None:
        raise AclNaoEncontrado()
    return perfil


def leitura(perfil: PerfilAcl) -> LeituraPerfil:
    return LeituraPerfil(id=perfil.id, nome=perfil.nome, descricao=perfil.descricao, ativo=perfil.ativo, total_usuarios=len(perfil.vinculos), total_setores=len(perfil.setores_vinculados),
                         total_direitos=len({d.recurso_id for d in perfil.direitos}), criado_em=perfil.criado_em, atualizado_em=perfil.atualizado_em)


def listar(sessao: Session) -> list[LeituraPerfil]:
    return [leitura(p) for p in sessao.scalars(select(PerfilAcl).order_by(func.lower(PerfilAcl.nome))).unique()]


def _direitos_por_modulo(perfil: PerfilAcl) -> list[DireitoPerfilModulo]:
    """Uma linha por módulo adicionado ao perfil, com as ações marcadas (na ordem das ações do módulo)."""
    por_recurso: dict[int, list[PerfilDireito]] = {}
    for d in perfil.direitos:
        por_recurso.setdefault(d.recurso_id, []).append(d)
    linhas = []
    for linha in por_recurso.values():
        recurso = linha[0].recurso
        marcadas = {d.nivel for d in linha}
        disponiveis = acoes_do_recurso(recurso.slug)
        linhas.append(DireitoPerfilModulo(
            recurso_id=recurso.id, recurso_nome=recurso.nome, recurso_slug=recurso.slug,
            acoes=[a["codigo"] for a in disponiveis if a["codigo"] in marcadas],
            acoes_disponiveis=[AcaoModulo(**a) for a in disponiveis]))
    return sorted(linhas, key=lambda x: x.recurso_nome.lower())


def detalhar(sessao: Session, perfil_id: int) -> DetalhePerfil:
    perfil = obter_perfil(sessao, perfil_id)
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([v.usuario_id for v in perfil.vinculos])))} if perfil.vinculos else {}
    return DetalhePerfil(
        **leitura(perfil).model_dump(),
        direitos=_direitos_por_modulo(perfil),
        setores=sorted((SetorDoPerfil(id=v.setor.id, nome=v.setor.nome, sistemico=v.setor.sistemico, setor_pai_id=v.setor.setor_pai_id) for v in perfil.setores_vinculados), key=lambda x: x.nome.lower()),
        usuarios=sorted(
            (UsuarioDoPerfil(id=u.id, login=u.login, nome_completo=u.nome_completo or u.login, cargo=u.cargo, ativo=u.ativo, padrao=v.padrao)
             for v in perfil.vinculos if (u := usuarios.get(v.usuario_id))),
            key=lambda x: x.nome_completo.lower()),
    )


def gravar(sessao: Session, dados: GravacaoPerfil, autor: Usuario, perfil_id: int | None = None) -> PerfilAcl:
    """Cria (sem `perfil_id`) ou altera o perfil, com nome único."""
    if not dados.nome:
        raise ErroRegraAcl("O nome do perfil é obrigatório.")
    if sessao.scalar(select(PerfilAcl.id).where(func.lower(PerfilAcl.nome) == dados.nome.lower(), PerfilAcl.id != (perfil_id or 0))) is not None:
        raise ErroRegraAcl("Já existe um perfil com este nome.", conflito=True)
    perfil = obter_perfil(sessao, perfil_id) if perfil_id else PerfilAcl()
    perfil.nome, perfil.descricao, perfil.ativo = dados.nome, dados.descricao, dados.ativo
    if perfil_id is None:
        sessao.add(perfil)
    sessao.flush()
    auditar(sessao, autor.login, "acl.perfil.alterar" if perfil_id else "acl.perfil.criar", perfil.nome, f"ativo={perfil.ativo}", autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id)
    sessao.commit()
    return perfil


def excluir(sessao: Session, perfil_id: int, autor: Usuario) -> None:
    """Exclui o perfil só se ninguém o usa; com usuários, é preciso tirá-los (ou desativar o perfil)."""
    perfil = obter_perfil(sessao, perfil_id)
    if perfil.vinculos:
        raise ErroRegraAcl(f"O perfil tem {len(perfil.vinculos)} usuário(s): retire-os antes de excluir (ou desative o perfil).", conflito=True)
    auditar(sessao, autor.login, "acl.perfil.excluir", perfil.nome, autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id)
    sessao.delete(perfil)
    sessao.commit()


def definir_acoes_do_modulo(sessao: Session, perfil_id: int, recurso_id: int, acoes: list[str], autor: Usuario) -> PerfilAcl:
    """Adiciona o módulo ao perfil (ou troca as ações dele). As ações são independentes e precisam ser do módulo."""
    perfil = obter_perfil(sessao, perfil_id)
    recurso = sessao.get(RecursoAcl, recurso_id)
    if recurso is None:
        raise ErroRegraAcl("Módulo não encontrado.")
    validas = set(codigos_do_recurso(recurso.slug))
    escolhidas = list(dict.fromkeys(acoes))
    if not escolhidas:
        raise ErroRegraAcl("Marque ao menos uma ação do módulo.")
    if not set(escolhidas) <= validas:
        raise ErroRegraAcl("Há ação que este módulo não oferece.")
    antes = sorted(d.nivel for d in perfil.direitos if d.recurso_id == recurso_id)
    for d in [d for d in perfil.direitos if d.recurso_id == recurso_id]:
        perfil.direitos.remove(d)
    sessao.flush()
    perfil.direitos.extend(PerfilDireito(perfil_id=perfil.id, recurso_id=recurso_id, nivel=a) for a in escolhidas)
    perfil.atualizado_em = func.now()
    auditar(sessao, autor.login, "acl.perfil.modulo", f"{perfil.nome}: {recurso.slug}", autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id,
            dados={"modulo": recurso.slug, "antes": antes, "depois": sorted(escolhidas)})
    sessao.commit()
    sessao.refresh(perfil)
    return perfil


def remover_modulo(sessao: Session, perfil_id: int, recurso_id: int, autor: Usuario) -> PerfilAcl:
    """Tira o módulo do perfil (todas as ações dele)."""
    perfil = obter_perfil(sessao, perfil_id)
    existentes = [d for d in perfil.direitos if d.recurso_id == recurso_id]
    if not existentes:
        raise AclNaoEncontrado()
    slug = existentes[0].recurso.slug
    for d in existentes:
        perfil.direitos.remove(d)
    perfil.atualizado_em = func.now()
    auditar(sessao, autor.login, "acl.perfil.modulo.remover", f"{perfil.nome}: {slug}", autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id,
            dados={"modulo": slug, "antes": sorted(d.nivel for d in existentes)})
    sessao.commit()
    sessao.refresh(perfil)
    return perfil


def _garantir_padrao(sessao: Session, usuario_id: int, preferido: int | None = None) -> None:
    """O usuário com perfis fica com exatamente um padrão (o preferido, o que já era ou o primeiro por nome)."""
    vinculos = list(sessao.scalars(select(UsuarioPerfil).where(UsuarioPerfil.usuario_id == usuario_id)))
    if not vinculos:
        return
    nomes = {p.id: p.nome.lower() for p in sessao.scalars(select(PerfilAcl).where(PerfilAcl.id.in_([v.perfil_id for v in vinculos])))}
    escolhido = next((v for v in vinculos if v.perfil_id == preferido), None) or next((v for v in vinculos if v.padrao), None) or min(vinculos, key=lambda v: nomes.get(v.perfil_id, ""))
    for v in vinculos:
        v.padrao = v is escolhido


def definir_setores(sessao: Session, perfil_id: int, setores_ids: list[int], autor: Usuario) -> PerfilAcl:
    """Substitui os setores e grupos sistêmicos que recebem o perfil: quem é membro deles passa a ter o perfil (além dos usuários diretos).

    A API guarda exatamente os ids enviados: a tela marca os filhos junto com o pai, mas cada setor continua independente (dá para tirar um filho).
    """
    perfil = obter_perfil(sessao, perfil_id)
    novos = set(setores_ids)
    if novos and set(sessao.scalars(select(Setor.id).where(Setor.id.in_(novos)))) != novos:
        raise ErroRegraAcl("Setor ou grupo não encontrado.")
    atuais = {v.setor_id: v for v in perfil.setores_vinculados}
    for setor_id, vinculo in list(atuais.items()):
        if setor_id not in novos:
            perfil.setores_vinculados.remove(vinculo)
    for setor_id in novos - set(atuais):
        perfil.setores_vinculados.append(PerfilSetor(perfil_id=perfil.id, setor_id=setor_id))
    perfil.atualizado_em = func.now()
    nomes = sorted(n for n in sessao.scalars(select(Setor.nome).where(Setor.id.in_(novos)))) if novos else []
    auditar(sessao, autor.login, "acl.perfil.setores", perfil.nome, f"{len(novos)} setor(es)/grupo(s)", autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id,
            dados={"setores_ids": sorted(novos), "setores": nomes})
    sessao.commit()
    sessao.refresh(perfil)
    return perfil


def definir_usuarios(sessao: Session, perfil_id: int, usuarios_ids: list[int], autor: Usuario) -> PerfilAcl:
    """Substitui os usuários do perfil. Quem não tinha outro perfil passa a ter este como padrão."""
    perfil = obter_perfil(sessao, perfil_id)
    novos = set(usuarios_ids)
    if novos and set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(novos)))) != novos:
        raise ErroRegraAcl("Usuário não encontrado.")
    atuais = {v.usuario_id: v for v in perfil.vinculos}
    for usuario_id, vinculo in list(atuais.items()):
        if usuario_id not in novos:
            perfil.vinculos.remove(vinculo)
    sessao.flush()
    for usuario_id in novos - set(atuais):
        perfil.vinculos.append(UsuarioPerfil(usuario_id=usuario_id, perfil_id=perfil.id, padrao=False))
    sessao.flush()
    for usuario_id in novos | set(atuais):
        _garantir_padrao(sessao, usuario_id)
    auditar(sessao, autor.login, "acl.perfil.usuarios", perfil.nome, f"{len(novos)} usuário(s)", autor_id=autor.id, alvo_tipo="perfil", alvo_id=perfil.id,
            dados={"usuarios_ids": sorted(novos)})
    sessao.commit()
    sessao.refresh(perfil)
    return perfil


def perfis_do_usuario(sessao: Session, usuario_id: int) -> list[PerfilDoUsuario]:
    """Perfis do usuário: os atribuídos a ele (alteráveis) e os que recebe pelos setores/grupos (só leitura, com a origem)."""
    from app.services import servico_acl

    if sessao.get(Usuario, usuario_id) is None:
        raise AclNaoEncontrado()
    diretos = {p.id: padrao for p, padrao in sessao.execute(
        select(PerfilAcl, UsuarioPerfil.padrao).join(UsuarioPerfil, UsuarioPerfil.perfil_id == PerfilAcl.id).where(UsuarioPerfil.usuario_id == usuario_id)
    ).unique().all()}
    por_setor = servico_acl.perfis_por_setor(sessao, usuario_id)
    nomes = {p.id: p for p in sessao.scalars(select(PerfilAcl).where(PerfilAcl.id.in_(set(diretos) | set(por_setor))))} if diretos or por_setor else {}
    linhas = [PerfilDoUsuario(perfil_id=i, nome=nomes[i].nome, ativo=nomes[i].ativo, padrao=diretos.get(i, False), via_setores=por_setor.get(i, []), direto=i in diretos) for i in nomes]
    return sorted(linhas, key=lambda x: x.nome.lower())


def definir_perfis_do_usuario(sessao: Session, usuario_id: int, dados: GravacaoPerfisDoUsuario, autor: Usuario) -> list[PerfilDoUsuario]:
    """Substitui os perfis do usuário e define o padrão."""
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise AclNaoEncontrado()
    novos = list(dict.fromkeys(dados.perfis_ids))
    if novos and set(sessao.scalars(select(PerfilAcl.id).where(PerfilAcl.id.in_(novos)))) != set(novos):
        raise ErroRegraAcl("Perfil não encontrado.")
    if dados.padrao_id is not None and dados.padrao_id not in novos:
        raise ErroRegraAcl("O perfil padrão precisa estar entre os perfis do usuário.")
    atuais = {v.perfil_id: v for v in sessao.scalars(select(UsuarioPerfil).where(UsuarioPerfil.usuario_id == usuario_id))}
    for perfil_id, vinculo in atuais.items():
        if perfil_id not in novos:
            sessao.delete(vinculo)
    for perfil_id in novos:
        if perfil_id not in atuais:
            sessao.add(UsuarioPerfil(usuario_id=usuario_id, perfil_id=perfil_id, padrao=False))
    sessao.flush()
    _garantir_padrao(sessao, usuario_id, dados.padrao_id)
    auditar(sessao, autor.login, "acl.usuario.perfis", usuario.login, f"{len(novos)} perfil(is)", autor_id=autor.id, alvo_tipo="usuario", alvo_id=usuario.id,
            dados={"perfis_ids": novos, "padrao_id": dados.padrao_id})
    sessao.commit()
    return perfis_do_usuario(sessao, usuario_id)
