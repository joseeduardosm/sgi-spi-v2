"""Regras de negócio dos diretórios LDAP: cadastro, ativação, teste e sincronização."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.criptografia import cifrar_segredo
from app.models.diretorio_ldap import DiretorioLdap
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.ldap import AlteracaoDiretorio, CriacaoDiretorio
from app.services import cliente_ldap
from app.services.cliente_ldap import IdentidadeLdap, ParametrosDiretorio, ResultadoTesteLdap
from app.services.servico_auditoria import auditar
from app.services.servico_usuarios import aplicar_identidade, buscar_por_login


class DiretorioNaoEncontrado(Exception):
    pass


@dataclass(frozen=True)
class ResumoSincronizacao:
    encontrados: int
    criados: int
    atualizados: int
    desativados: int
    ignorados: int
    sincronizado_em: datetime


def listar_diretorios(sessao: Session) -> list[DiretorioLdap]:
    return list(sessao.scalars(select(DiretorioLdap).order_by(func.lower(DiretorioLdap.nome))))


def obter_diretorio(sessao: Session, diretorio_id: uuid.UUID) -> DiretorioLdap:
    diretorio = sessao.get(DiretorioLdap, diretorio_id)
    if diretorio is None:
        raise DiretorioNaoEncontrado()
    return diretorio


def obter_diretorio_ativo(sessao: Session) -> DiretorioLdap | None:
    return sessao.scalar(select(DiretorioLdap).where(DiretorioLdap.ativo.is_(True)))


def _desativar_demais(sessao: Session, manter_id: uuid.UUID | None) -> None:
    comando = update(DiretorioLdap).where(DiretorioLdap.ativo.is_(True))
    if manter_id is not None:
        comando = comando.where(DiretorioLdap.id != manter_id)
    sessao.execute(comando.values(ativo=False))
    sessao.flush()


def criar_diretorio(sessao: Session, dados: CriacaoDiretorio, autor: str) -> DiretorioLdap:
    if dados.ativo:
        _desativar_demais(sessao, None)
    diretorio = DiretorioLdap(
        nome=dados.nome,
        servidor=dados.servidor,
        porta=dados.porta,
        usar_ssl=dados.usar_ssl,
        base_dn=dados.base_dn,
        bind_dn=dados.bind_dn,
        senha_bind_cifrada=cifrar_segredo(dados.senha_bind),
        ativo=dados.ativo,
    )
    sessao.add(diretorio)
    sessao.flush()
    auditar(sessao, autor, "ldap.criar", diretorio.nome, f"id={diretorio.id} ativo={diretorio.ativo}")
    sessao.commit()
    return diretorio


def alterar_diretorio(sessao: Session, diretorio_id: uuid.UUID, dados: AlteracaoDiretorio, autor: str) -> DiretorioLdap:
    diretorio = obter_diretorio(sessao, diretorio_id)
    if dados.ativo:
        _desativar_demais(sessao, diretorio.id)
    for campo in ("nome", "servidor", "porta", "usar_ssl", "base_dn", "bind_dn", "ativo"):
        setattr(diretorio, campo, getattr(dados, campo))
    if dados.senha_bind:  # vazia preserva a senha já cifrada
        diretorio.senha_bind_cifrada = cifrar_segredo(dados.senha_bind)
    auditar(sessao, autor, "ldap.alterar", diretorio.nome, f"id={diretorio.id} ativo={diretorio.ativo}")
    sessao.commit()
    return diretorio


def excluir_diretorio(sessao: Session, diretorio_id: uuid.UUID, autor: str) -> None:
    diretorio = obter_diretorio(sessao, diretorio_id)
    auditar(sessao, autor, "ldap.excluir", diretorio.nome, f"id={diretorio.id}")
    sessao.delete(diretorio)
    sessao.commit()


def testar_parametros(parametros: ParametrosDiretorio) -> ResultadoTesteLdap:
    return cliente_ldap.testar_conexao(parametros)


def testar_diretorio(sessao: Session, diretorio_id: uuid.UUID, senha_bind: str | None) -> ResultadoTesteLdap:
    """Testa a configuração salva e registra data, resultado, tempo de resposta e erro."""
    diretorio = obter_diretorio(sessao, diretorio_id)
    try:
        resultado = cliente_ldap.testar_conexao(ParametrosDiretorio.do_modelo(diretorio, senha_bind or None))
    except cliente_ldap.ErroLdapIndisponivel as erro:
        resultado = ResultadoTesteLdap(False, 0, str(erro))
    diretorio.ultimo_teste_em = agora_utc()
    diretorio.ultimo_teste_ok = resultado.sucesso
    diretorio.ultima_latencia_ms = resultado.latencia_ms
    diretorio.ultimo_erro = None if resultado.sucesso else resultado.mensagem
    sessao.commit()
    return resultado


def sincronizar(sessao: Session, diretorio_id: uuid.UUID, autor: str) -> ResumoSincronizacao:
    """Lê todas as identidades do diretório e aplica a fotografia. Lança ErroLdapIndisponivel.

    Uma leitura com falha não altera nenhum usuário.
    """
    diretorio = obter_diretorio(sessao, diretorio_id)
    try:
        identidades = cliente_ldap.listar_usuarios(ParametrosDiretorio.do_modelo(diretorio))
    except cliente_ldap.ErroLdapIndisponivel as erro:
        diretorio.ultima_sincronizacao_em = agora_utc()
        diretorio.ultima_sincronizacao_ok = False
        diretorio.ultima_sincronizacao_mensagem = str(erro)
        sessao.commit()
        raise
    resumo = aplicar_fotografia(sessao, diretorio, identidades)
    diretorio.ultima_sincronizacao_em = resumo.sincronizado_em
    diretorio.ultima_sincronizacao_ok = True
    diretorio.ultima_sincronizacao_mensagem = (
        f"encontrados={resumo.encontrados}, criados={resumo.criados}, atualizados={resumo.atualizados}, "
        f"desativados={resumo.desativados}, ignorados={resumo.ignorados}"
    )
    auditar(sessao, autor, "ldap.sincronizar", diretorio.nome, diretorio.ultima_sincronizacao_mensagem)
    sessao.commit()
    return resumo


def aplicar_fotografia(sessao: Session, diretorio: DiretorioLdap, identidades: list[IdentidadeLdap]) -> ResumoSincronizacao:
    agora = agora_utc()
    criados = atualizados = desativados = ignorados = 0
    ids_vistos = {i.id_externo.lower() for i in identidades if i.id_externo}
    logins_vistos = {i.login.lower() for i in identidades}

    vinculados = list(sessao.scalars(select(Usuario).where(Usuario.diretorio_id == diretorio.id)))
    por_id_externo = {u.id_externo.lower(): u for u in vinculados if u.id_externo}
    por_login = {u.login.lower(): u for u in vinculados}

    for identidade in identidades:
        usuario = (por_id_externo.get(identidade.id_externo.lower()) if identidade.id_externo else None) or por_login.get(
            identidade.login.lower()
        )
        if usuario is None:
            if buscar_por_login(sessao, identidade.login) is not None:
                # Conta local homônima é preservada: não muda origem nem privilégios numa importação
                ignorados += 1
                continue
            usuario = Usuario(login=identidade.login, origem=OrigemUsuario.LDAP, diretorio_id=diretorio.id)
            sessao.add(usuario)
            aplicar_identidade(usuario, identidade)
            usuario.ativo = identidade.ativo
            sessao.flush()
            por_login[usuario.login.lower()] = usuario
            criados += 1
        else:
            aplicar_identidade(usuario, identidade)
            if usuario.origem == OrigemUsuario.LDAP and not usuario.superusuario:
                usuario.ativo = identidade.ativo
            atualizados += 1

    # Contas exclusivamente LDAP que sumiram do diretório são desativadas
    for usuario in vinculados:
        if usuario.origem != OrigemUsuario.LDAP or usuario.superusuario or not usuario.ativo:
            continue
        presente = (usuario.id_externo and usuario.id_externo.lower() in ids_vistos) or usuario.login.lower() in logins_vistos
        if not presente:
            usuario.ativo = False
            desativados += 1

    sessao.flush()
    return ResumoSincronizacao(len(identidades), criados, atualizados, desativados, ignorados, agora)
