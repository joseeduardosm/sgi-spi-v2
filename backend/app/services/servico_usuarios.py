"""Consulta de usuários, conta administrativa principal e conta de representação LDAP."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.diretorio_ldap import DiretorioLdap
from app.models.usuario import OrigemUsuario, Usuario
from app.services.cliente_ldap import IdentidadeLdap


def buscar_por_login(sessao: Session, login: str) -> Usuario | None:
    return sessao.scalar(select(Usuario).where(func.lower(Usuario.login) == login.lower()))


def garantir_conta_admin(sessao: Session) -> Usuario:
    """Cria ou atualiza a conta administrativa principal a partir do .env.

    O .env é a fonte da senha dessa conta: trocar HASH_SENHA_ADMIN e reiniciar a API troca a senha.
    """
    config = obter_configuracao()
    usuario = buscar_por_login(sessao, config.login_admin)
    if usuario is None:
        usuario = Usuario(login=config.login_admin, origem=OrigemUsuario.LOCAL, nome_completo=config.nome_admin)
        sessao.add(usuario)
    usuario.hash_senha = config.hash_senha_admin.get_secret_value()
    usuario.superusuario = True
    usuario.ativo = True
    if not usuario.nome_completo:
        usuario.nome_completo = config.nome_admin
    sessao.commit()
    return usuario


def buscar_vinculado(sessao: Session, diretorio: DiretorioLdap, identidade: IdentidadeLdap) -> Usuario | None:
    """Localiza a conta vinculada ao diretório pelo identificador externo ou, na falta dele, pelo login."""
    if identidade.id_externo:
        usuario = sessao.scalar(
            select(Usuario).where(Usuario.diretorio_id == diretorio.id, Usuario.id_externo == identidade.id_externo)
        )
        if usuario:
            return usuario
    return sessao.scalar(
        select(Usuario).where(Usuario.diretorio_id == diretorio.id, func.lower(Usuario.login) == identidade.login.lower())
    )


def aplicar_identidade(usuario: Usuario, identidade: IdentidadeLdap) -> None:
    """Sincroniza os dados corporativos, preservando o que o diretório não informa."""
    usuario.login = identidade.login
    usuario.id_externo = identidade.id_externo or usuario.id_externo
    usuario.dn = identidade.dn or usuario.dn
    if identidade.nome_completo:
        usuario.nome_completo = identidade.nome_completo
    if identidade.email:
        usuario.email = identidade.email


def registrar_login_ldap(sessao: Session, diretorio: DiretorioLdap, identidade: IdentidadeLdap) -> Usuario | None:
    """Cria ou atualiza a conta local de representação após autenticação LDAP bem-sucedida.

    Retorna None quando a identidade não pode assumir a conta local homônima (superusuário),
    caso em que o login segue para a autenticação local.
    """
    usuario = buscar_vinculado(sessao, diretorio, identidade)
    if usuario is None:
        homonimo = buscar_por_login(sessao, identidade.login)
        if homonimo is not None:
            if homonimo.superusuario:
                return None  # nunca vincular uma identidade corporativa a um superusuário
            homonimo.diretorio_id = diretorio.id
            homonimo.origem = OrigemUsuario.LOCAL_LDAP if homonimo.hash_senha else OrigemUsuario.LDAP
            usuario = homonimo
        else:
            usuario = Usuario(login=identidade.login, origem=OrigemUsuario.LDAP, diretorio_id=diretorio.id)
            sessao.add(usuario)
    aplicar_identidade(usuario, identidade)
    usuario.ativo = identidade.ativo
    usuario.ultimo_acesso_em = agora_utc()
    sessao.commit()
    return usuario
