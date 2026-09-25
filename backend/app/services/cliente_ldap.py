# Criado por José Eduardo Santana Martins
# Este arquivo serve para conectar e consultar diretórios LDAP/Active Directory.
"""Acesso a diretórios LDAP/Active Directory (biblioteca ldap3).

Fluxo de autenticação:
1. conecta com a conta técnica (bind DN) e localiza a pessoa pelo login;
2. tenta um novo bind com a identidade encontrada e a senha informada.
A busca sozinha não autentica ninguém: só o segundo bind prova a senha.
"""

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from ldap3 import BASE, NONE, SIMPLE, SUBTREE, Connection, Server
from ldap3.core import exceptions as excecoes_ldap
from ldap3.utils.conv import escape_filter_chars

from app.core.configuracao import obter_configuracao
from app.core.criptografia import ErroDecifrarSegredo, decifrar_segredo
from app.models.diretorio_ldap import DiretorioLdap

registro_log = logging.getLogger(__name__)

ATRIBUTOS_USUARIO = [
    "distinguishedName",
    "givenName",
    "sn",
    "displayName",
    "mail",
    "sAMAccountName",
    "userPrincipalName",
    "objectGUID",
    "userAccountControl",
]
FILTRO_PESSOAS = "(&(objectCategory=person)(objectClass=user)(sAMAccountName=*))"
CONTA_DESATIVADA = 0x2  # bit ACCOUNTDISABLE do userAccountControl


@dataclass(frozen=True)
class IdentidadeLdap:
    login: str
    nome_completo: str
    email: str
    dn: str
    id_externo: str | None
    ativo: bool = True


@dataclass(frozen=True)
class ResultadoTesteLdap:
    sucesso: bool
    latencia_ms: int
    mensagem: str


@dataclass(frozen=True)
class DiagnosticoLdap:
    encontrado: bool
    entradas: int
    mensagem: str
    login: str | None = None
    nome_principal: str | None = None
    dn: str | None = None


class ErroLdapIndisponivel(Exception):
    """Diretório inacessível ou conta técnica recusada: o login deve seguir para a conta local."""


@dataclass(frozen=True)
class ParametrosDiretorio:
    """Dados de conexão desacoplados do modelo, para testar configurações ainda não salvas."""

    servidor: str
    porta: int
    usar_ssl: bool
    base_dn: str
    bind_dn: str
    senha_bind: str

    @classmethod
    def do_modelo(cls, diretorio: DiretorioLdap, senha_bind: str | None = None) -> "ParametrosDiretorio":
        if senha_bind is None:
            try:
                senha_bind = decifrar_segredo(diretorio.senha_bind_cifrada)
            except ErroDecifrarSegredo as erro:
                raise ErroLdapIndisponivel(str(erro)) from erro
        return cls(diretorio.servidor, diretorio.porta, diretorio.usar_ssl, diretorio.base_dn, diretorio.bind_dn, senha_bind)


def _conexao_padrao(parametros: ParametrosDiretorio, usuario: str, senha: str) -> Connection:
    limite = obter_configuracao().tempo_limite_ldap_segundos
    servidor = Server(parametros.servidor, port=parametros.porta, use_ssl=parametros.usar_ssl, get_info=NONE, connect_timeout=limite)
    return Connection(
        servidor,
        user=usuario,
        password=senha,
        authentication=SIMPLE,
        auto_referrals=False,
        read_only=True,
        receive_timeout=limite * 2,
        raise_exceptions=False,
    )


# Substituível nos testes (ldap3 MOCK_SYNC)
fabrica_conexao: Callable[[ParametrosDiretorio, str, str], Connection] = _conexao_padrao


def _conectar(parametros: ParametrosDiretorio, usuario: str, senha: str) -> Connection:
    """Abre a conexão e faz o bind. Lança exceção do ldap3 se a conexão ou o bind falharem."""
    conexao = fabrica_conexao(parametros, usuario, senha)
    if not conexao.bind():
        resultado = conexao.result or {}
        conexao.unbind()
        if resultado.get("result") == 49:
            raise excecoes_ldap.LDAPInvalidCredentialsResult(result=49, description=resultado.get("description"))
        raise excecoes_ldap.LDAPBindError(resultado.get("description") or "bind recusado")
    return conexao


def _conexao_tecnica(parametros: ParametrosDiretorio) -> Connection:
    try:
        return _conectar(parametros, parametros.bind_dn, parametros.senha_bind)
    except excecoes_ldap.LDAPException as erro:
        raise ErroLdapIndisponivel(descrever_erro(erro, parametros)) from erro


def descrever_erro(erro: Exception, parametros: ParametrosDiretorio) -> str:
    """Mensagem legível e sem detalhes sensíveis para o administrador."""
    if isinstance(erro, excecoes_ldap.LDAPSocketOpenError | excecoes_ldap.LDAPSocketReceiveError | excecoes_ldap.LDAPSessionTerminatedByServerError):
        return f"Não foi possível conectar a {parametros.servidor}:{parametros.porta}{' (LDAPS)' if parametros.usar_ssl else ''}."
    if isinstance(erro, excecoes_ldap.LDAPInvalidCredentialsResult | excecoes_ldap.LDAPBindError):
        return "A conta técnica (Bind DN/senha) foi recusada pelo diretório."
    if isinstance(erro, excecoes_ldap.LDAPNoSuchObjectResult):
        return "Base DN não encontrada no diretório."
    if isinstance(erro, excecoes_ldap.LDAPSSLConfigurationError | excecoes_ldap.LDAPStartTLSError):
        return "Falha na negociação SSL/TLS com o diretório."
    if isinstance(erro, excecoes_ldap.LDAPOperationResult):
        return f"O diretório recusou a operação: {erro.description or erro.result}."
    return f"Falha LDAP ({type(erro).__name__})."


def _atributo(entrada: dict, nome: str) -> str | None:
    valor = entrada.get("attributes", {}).get(nome)
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    if valor in (None, ""):
        return None
    return str(valor)


def _guid(entrada: dict) -> str | None:
    bruto = entrada.get("raw_attributes", {}).get("objectGUID")
    if bruto and isinstance(bruto[0], bytes) and len(bruto[0]) == 16:
        return str(uuid.UUID(bytes_le=bruto[0]))  # mesmo formato do System.Guid do .NET
    valor = _atributo(entrada, "objectGUID")
    return valor.strip("{}").lower() if valor else None


def _esta_ativa(entrada: dict) -> bool:
    sinalizadores = _atributo(entrada, "userAccountControl")
    try:
        return not (int(sinalizadores) & CONTA_DESATIVADA) if sinalizadores is not None else True
    except ValueError:
        return True


def _identidade(entrada: dict, login: str) -> IdentidadeLdap:
    nome, sobrenome = _atributo(entrada, "givenName") or "", _atributo(entrada, "sn") or ""
    return IdentidadeLdap(
        login=login,
        nome_completo=_atributo(entrada, "displayName") or f"{nome} {sobrenome}".strip(),
        email=_atributo(entrada, "mail") or "",
        dn=entrada.get("dn", ""),
        id_externo=_guid(entrada),
        ativo=_esta_ativa(entrada),
    )


def _dominio(base_dn: str) -> str:
    """'DC=spi,DC=sp,DC=gov,DC=br' -> 'spi.sp.gov.br'"""
    partes = [p.strip() for p in base_dn.split(",")]
    return ".".join(p[3:] for p in partes if p.upper().startswith("DC="))


def _buscar_login(conexao: Connection, base_dn: str, login: str) -> list[dict]:
    escapado = escape_filter_chars(login)
    filtro = f"(userPrincipalName={escapado})" if "@" in login else f"(sAMAccountName={escapado})"
    conexao.search(base_dn, filtro, SUBTREE, attributes=ATRIBUTOS_USUARIO, size_limit=2)
    return [e for e in conexao.response or [] if e.get("type") == "searchResEntry"]


def testar_conexao(parametros: ParametrosDiretorio) -> ResultadoTesteLdap:
    """Valida servidor, porta, SSL, credenciais técnicas e Base DN."""
    inicio = time.perf_counter()
    try:
        conexao = _conectar(parametros, parametros.bind_dn, parametros.senha_bind)
        try:
            if not conexao.search(parametros.base_dn, "(objectClass=*)", BASE, attributes=[]):
                codigo = conexao.result.get("result")
                if codigo == 32:
                    raise excecoes_ldap.LDAPNoSuchObjectResult()
                raise excecoes_ldap.LDAPOperationResult(result=codigo, description=conexao.result.get("description"))
        finally:
            conexao.unbind()
        return ResultadoTesteLdap(True, _ms(inicio), "Conexão, bind da conta técnica e Base DN validados.")
    except excecoes_ldap.LDAPException as erro:
        return ResultadoTesteLdap(False, _ms(inicio), descrever_erro(erro, parametros))


def autenticar(parametros: ParametrosDiretorio, login: str, senha: str) -> IdentidadeLdap | None:
    """Retorna a identidade se login/senha forem válidos no diretório; None se recusados.

    Lança ErroLdapIndisponivel quando o diretório não pode ser consultado.
    """
    if not senha:
        return None  # bind com senha vazia é "anônimo" em muitos servidores
    conexao = _conexao_tecnica(parametros)
    try:
        entradas = _buscar_login(conexao, parametros.base_dn, login)
    except excecoes_ldap.LDAPException as erro:
        raise ErroLdapIndisponivel(descrever_erro(erro, parametros)) from erro
    finally:
        conexao.unbind()
    if not entradas:
        return None
    entrada = entradas[0]
    if not _esta_ativa(entrada):
        return None
    login_encontrado = _atributo(entrada, "sAMAccountName") or login.split("@")[0]
    dominio = _dominio(parametros.base_dn)
    candidatos = [entrada.get("dn"), _atributo(entrada, "userPrincipalName")]
    if dominio:
        candidatos += [f"{login_encontrado}@{dominio}", f"{dominio.split('.')[0].upper()}\\{login_encontrado}"]
    ja_testados: set[str] = set()
    for identidade in candidatos:
        if not identidade or identidade.lower() in ja_testados:
            continue
        ja_testados.add(identidade.lower())
        if _tentar_bind(parametros, identidade, senha):
            return _identidade(entrada, login_encontrado)
    return None


def listar_usuarios(parametros: ParametrosDiretorio) -> list[IdentidadeLdap]:
    """Lista as contas de pessoas do diretório (busca paginada). Lança ErroLdapIndisponivel."""
    conexao = _conexao_tecnica(parametros)
    try:
        identidades: list[IdentidadeLdap] = []
        for entrada in conexao.extend.standard.paged_search(
            parametros.base_dn, FILTRO_PESSOAS, SUBTREE, attributes=ATRIBUTOS_USUARIO, paged_size=500, generator=True
        ):
            if entrada.get("type") != "searchResEntry":
                continue  # referrals apontam para fora da Base DN configurada
            login = _atributo(entrada, "sAMAccountName")
            if login:
                identidades.append(_identidade(entrada, login))
        if conexao.result and conexao.result.get("result") not in (0, None):
            raise excecoes_ldap.LDAPOperationResult(result=conexao.result["result"], description=conexao.result.get("description"))
        return identidades
    except excecoes_ldap.LDAPException as erro:
        raise ErroLdapIndisponivel(descrever_erro(erro, parametros)) from erro
    finally:
        conexao.unbind()


def diagnosticar_login(parametros: ParametrosDiretorio, login: str) -> DiagnosticoLdap:
    """Procura um login usando só a conta técnica (nunca testa a senha pessoal)."""
    try:
        conexao = _conexao_tecnica(parametros)
        try:
            entradas = _buscar_login(conexao, parametros.base_dn, login)
        finally:
            conexao.unbind()
    except ErroLdapIndisponivel as erro:
        return DiagnosticoLdap(False, 0, str(erro))
    except excecoes_ldap.LDAPException as erro:
        return DiagnosticoLdap(False, 0, descrever_erro(erro, parametros))
    if not entradas:
        return DiagnosticoLdap(False, 0, "Usuário não encontrado na Base DN configurada.")
    entrada = entradas[0]
    mensagem = "Mais de uma entrada encontrada; a primeira será usada." if len(entradas) > 1 else "Usuário localizado com sucesso."
    return DiagnosticoLdap(
        True, len(entradas), mensagem, _atributo(entrada, "sAMAccountName"), _atributo(entrada, "userPrincipalName"), entrada.get("dn")
    )


def _tentar_bind(parametros: ParametrosDiretorio, identidade: str, senha: str) -> bool:
    try:
        conexao = _conectar(parametros, identidade, senha)
    except excecoes_ldap.LDAPException:
        return False
    autenticado = bool(conexao.bound)
    conexao.unbind()
    return autenticado


def _ms(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)
