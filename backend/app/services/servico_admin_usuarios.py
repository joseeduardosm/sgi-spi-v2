"""Administração de usuários e manutenção do próprio perfil."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.core.seguranca import gerar_hash_senha
from app.models.diretorio_ldap import DiretorioLdap
from app.models.setor import MembroSetor, Setor
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.usuarios import AlteracaoUsuario, CriacaoUsuario, DadosPerfil, DetalheUsuario, OpcaoUsuario, PerfilLeitura
from app.services import servico_perfil
from app.services.servico_auditoria import auditar
from app.services.servico_usuarios import buscar_por_login

CAMPOS_PERFIL = ("nome_completo", "email", "ramal", "celular", "cargo", "departamento", "andar", "predio", "data_nascimento", "gestor_id")
CAMPOS_BUSCA = ("login", "nome_completo", "email", "ramal", "celular", "cargo", "departamento", "predio")


class UsuarioNaoEncontrado(Exception):
    pass


class ErroRegraUsuario(Exception):
    """Violação de regra de negócio (mensagem pronta para o usuário)."""

    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


def eh_admin_principal(usuario: Usuario) -> bool:
    return usuario.login.lower() == obter_configuracao().login_admin.lower()


def _aplicar_busca(consulta: Select, busca: str | None) -> Select:
    if busca and busca.strip():
        termo = f"%{busca.strip().lower()}%"
        consulta = consulta.where(or_(*[func.lower(getattr(Usuario, c)).like(termo) for c in CAMPOS_BUSCA]))
    return consulta


def listar_usuarios(
    sessao: Session, busca: str | None, situacao: str, origem: str | None, pagina: int, tamanho_pagina: int
) -> tuple[list[DetalheUsuario], int]:
    consulta = _aplicar_busca(select(Usuario), busca)
    if situacao == "ativos":
        consulta = consulta.where(Usuario.ativo.is_(True))
    elif situacao == "inativos":
        consulta = consulta.where(Usuario.ativo.is_(False))
    if origem:
        consulta = consulta.where(Usuario.origem == origem)
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    usuarios = list(
        sessao.scalars(
            consulta.order_by(func.lower(func.coalesce(func.nullif(Usuario.nome_completo, ""), Usuario.login)))
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        )
    )
    return para_detalhes(sessao, usuarios), total


def opcoes(sessao: Session, busca: str | None, limite: int = 20, incluir_inativos: bool = False) -> list[OpcaoUsuario]:
    consulta = _aplicar_busca(select(Usuario), busca)
    if not incluir_inativos:
        consulta = consulta.where(Usuario.ativo.is_(True))
    usuarios = sessao.scalars(consulta.order_by(func.lower(Usuario.nome_completo), Usuario.login).limit(limite))
    return [para_opcao(u) for u in usuarios]


def para_opcao(u: Usuario) -> OpcaoUsuario:
    return OpcaoUsuario(id=u.id, login=u.login, nome_completo=u.nome_completo or u.login, cargo=u.cargo, ativo=u.ativo)


def obter_usuario(sessao: Session, usuario_id: int) -> Usuario:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNaoEncontrado()
    return usuario


def para_detalhes(sessao: Session, usuarios: list[Usuario]) -> list[DetalheUsuario]:
    if not usuarios:
        return []
    ids = [u.id for u in usuarios]
    ids_gestores = {u.gestor_id for u in usuarios if u.gestor_id}
    gestores = (
        {g.id: g.nome_completo or g.login for g in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids_gestores)))}
        if ids_gestores
        else {}
    )
    ids_diretorios = {u.diretorio_id for u in usuarios if u.diretorio_id}
    diretorios = (
        {d.id: d.nome for d in sessao.scalars(select(DiretorioLdap).where(DiretorioLdap.id.in_(ids_diretorios)))}
        if ids_diretorios
        else {}
    )
    setores: dict[int, list[str]] = {}
    for usuario_id, nome in sessao.execute(
        select(MembroSetor.usuario_id, Setor.nome)
        .join(Setor, Setor.id == MembroSetor.setor_id)
        .where(MembroSetor.usuario_id.in_(ids))
        .order_by(Setor.nome)
    ):
        setores.setdefault(usuario_id, []).append(nome)
    return [
        DetalheUsuario(
            id=u.id,
            login=u.login,
            ativo=u.ativo,
            superusuario=u.superusuario,
            origem=u.origem,
            possui_senha_local=bool(u.hash_senha),
            diretorio_nome=diretorios.get(u.diretorio_id) if u.diretorio_id else None,
            id_externo=u.id_externo,
            perfil=PerfilLeitura(
                **{c: getattr(u, c) for c in CAMPOS_PERFIL},
                gestor_nome=gestores.get(u.gestor_id) if u.gestor_id else None,
                perfil_revisado_em=u.perfil_revisado_em,
            ),
            perfil_completo=not servico_perfil.campos_pendentes(u),
            revisao_obrigatoria=servico_perfil.revisao_vencida(u),
            setores=setores.get(u.id, []),
            ultimo_acesso_em=u.ultimo_acesso_em,
            criado_em=u.criado_em,
            atualizado_em=u.atualizado_em,
        )
        for u in usuarios
    ]


def para_detalhe(sessao: Session, usuario: Usuario) -> DetalheUsuario:
    return para_detalhes(sessao, [usuario])[0]


def _aplicar_perfil(sessao: Session, usuario: Usuario, perfil: DadosPerfil) -> None:
    if perfil.gestor_id is not None:
        if perfil.gestor_id == usuario.id:
            raise ErroRegraUsuario("O usuário não pode ser gestor de si mesmo.")
        if sessao.get(Usuario, perfil.gestor_id) is None:
            raise ErroRegraUsuario("Gestor imediato inválido.")
    for campo in CAMPOS_PERFIL:
        setattr(usuario, campo, getattr(perfil, campo))


def criar_conta_local(sessao: Session, dados: CriacaoUsuario, autor: str) -> Usuario:
    if buscar_por_login(sessao, dados.login) is not None:
        raise ErroRegraUsuario("Este login já está cadastrado.", conflito=True)
    usuario = Usuario(
        login=dados.login.strip(),
        hash_senha=gerar_hash_senha(dados.senha),
        origem=OrigemUsuario.LOCAL,
        ativo=dados.ativo,
        superusuario=dados.superusuario,
    )
    sessao.add(usuario)
    sessao.flush()
    _aplicar_perfil(sessao, usuario, dados.perfil)
    auditar(sessao, autor, "usuario.criar", usuario.login, f"id={usuario.id} superusuario={usuario.superusuario}")
    sessao.commit()
    return usuario


def alterar_usuario(sessao: Session, usuario_id: int, dados: AlteracaoUsuario, autor: Usuario) -> Usuario:
    usuario = obter_usuario(sessao, usuario_id)
    if eh_admin_principal(usuario) and (not dados.ativo or not dados.superusuario):
        raise ErroRegraUsuario("A conta administrativa principal não pode ser desativada nem perder o papel SuperRoot.")
    if usuario.id == autor.id and (not dados.ativo or not dados.superusuario):
        raise ErroRegraUsuario("Você não pode desativar a própria conta nem remover o próprio papel SuperRoot.")
    alteracoes = []
    if usuario.ativo != dados.ativo:
        alteracoes.append(f"ativo={dados.ativo}")
    if usuario.superusuario != dados.superusuario:
        alteracoes.append(f"superusuario={dados.superusuario}")
    usuario.ativo = dados.ativo
    usuario.superusuario = dados.superusuario
    _aplicar_perfil(sessao, usuario, dados.perfil)
    if dados.senha:
        if eh_admin_principal(usuario):
            raise ErroRegraUsuario("A senha da conta administrativa principal é definida no .env (HASH_SENHA_ADMIN).")
        usuario.hash_senha = gerar_hash_senha(dados.senha)
        if usuario.origem == OrigemUsuario.LDAP:
            usuario.origem = OrigemUsuario.LOCAL_LDAP  # conta corporativa ganha senha local de contingência
        alteracoes.append("senha")
    auditar(sessao, autor.login, "usuario.alterar", usuario.login, ", ".join(alteracoes) or None)
    sessao.commit()
    return usuario


def excluir_usuario(sessao: Session, usuario_id: int, autor: Usuario) -> None:
    usuario = obter_usuario(sessao, usuario_id)
    if eh_admin_principal(usuario):
        raise ErroRegraUsuario("A conta administrativa principal não pode ser excluída.")
    if usuario.id == autor.id:
        raise ErroRegraUsuario("Você não pode excluir a própria conta.")
    auditar(sessao, autor.login, "usuario.excluir", usuario.login, f"id={usuario.id} origem={usuario.origem}")
    sessao.delete(usuario)
    sessao.commit()


def revisar_proprio_perfil(sessao: Session, usuario: Usuario, perfil: DadosPerfil) -> Usuario:
    """Atualiza e confirma o próprio perfil, reiniciando o prazo de 30 dias."""
    _aplicar_perfil(sessao, usuario, perfil)
    usuario.perfil_revisado_em = agora_utc()
    auditar(sessao, usuario.login, "usuario.revisar-perfil", usuario.login)
    sessao.commit()
    return usuario
