import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.diretorio_ldap import DiretorioLdap
from app.models.usuario import Papel, Usuario
from app.schemas.comum import RespostaErro
from app.schemas.ldap import (
    AlteracaoDiretorio,
    CriacaoDiretorio,
    DiagnosticoLogin,
    LeituraDiretorio,
    ResultadoSincronizacao,
    ResultadoTeste,
    SenhaBindTemporaria,
    TesteDiretorioNaoSalvo,
)
from app.services import cliente_ldap, servico_ldap
from app.services.cliente_ldap import ErroLdapIndisponivel, ParametrosDiretorio
from app.services.servico_ldap import DiretorioNaoEncontrado

roteador = APIRouter(prefix="/ldap/diretorios", tags=["Diretórios LDAP"], responses=RESPOSTAS_AUTENTICADAS)

super_root = exigir_papeis(Papel.SUPER_ROOT)
NAO_ENCONTRADO = resposta_nao_encontrado("Diretório")


def _obter(sessao: Session, diretorio_id: uuid.UUID) -> DiretorioLdap:
    try:
        return servico_ldap.obter_diretorio(sessao, diretorio_id)
    except DiretorioNaoEncontrado:
        raise nao_encontrado("Diretório")


def _sincronizar_se_ativo(sessao: Session, diretorio: DiretorioLdap, autor: str) -> None:
    # Diretório ativo já popula os usuários ao ser salvo. Se o AD estiver indisponível,
    # o cadastro permanece válido e a rotina periódica tentará de novo.
    if diretorio.ativo:
        try:
            servico_ldap.sincronizar(sessao, diretorio.id, autor)
        except ErroLdapIndisponivel:
            pass


@roteador.get("", response_model=list[LeituraDiretorio], summary="Listar diretórios")
def listar_diretorios(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> list[DiretorioLdap]:
    return servico_ldap.listar_diretorios(sessao)


@roteador.post(
    "",
    response_model=LeituraDiretorio,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar diretório",
    description="Cifra a senha de bind antes de gravar. Se `ativo` for verdadeiro, desativa os demais e sincroniza os usuários.",
)
def criar_diretorio(dados: CriacaoDiretorio, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> DiretorioLdap:
    diretorio = servico_ldap.criar_diretorio(sessao, dados, autor.login)
    _sincronizar_se_ativo(sessao, diretorio, autor.login)
    return diretorio


@roteador.post(
    "/testar",
    response_model=ResultadoTeste,
    summary="Testar configuração sem salvar",
    description="Valida servidor, porta, SSL, credenciais técnicas e Base DN de uma configuração ainda não gravada.",
)
def testar_sem_salvar(dados: TesteDiretorioNaoSalvo, _: Usuario = Depends(super_root)) -> ResultadoTeste:
    parametros = ParametrosDiretorio(dados.servidor, dados.porta, dados.usar_ssl, dados.base_dn, dados.bind_dn, dados.senha_bind)
    return ResultadoTeste(**servico_ldap.testar_parametros(parametros).__dict__)


@roteador.get("/{diretorio_id}", response_model=LeituraDiretorio, summary="Consultar diretório", responses=NAO_ENCONTRADO)
def consultar_diretorio(diretorio_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> DiretorioLdap:
    return _obter(sessao, diretorio_id)


@roteador.put(
    "/{diretorio_id}",
    response_model=LeituraDiretorio,
    summary="Alterar diretório",
    description="`senha_bind` vazia ou ausente preserva a senha atual. Ativar um diretório desativa os demais.",
    responses=NAO_ENCONTRADO,
)
def alterar_diretorio(
    diretorio_id: uuid.UUID, dados: AlteracaoDiretorio, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)
) -> DiretorioLdap:
    _obter(sessao, diretorio_id)
    diretorio = servico_ldap.alterar_diretorio(sessao, diretorio_id, dados, autor.login)
    _sincronizar_se_ativo(sessao, diretorio, autor.login)
    return diretorio


@roteador.delete(
    "/{diretorio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir diretório",
    description="Os usuários vinculados permanecem cadastrados, sem vínculo com o diretório.",
    responses=NAO_ENCONTRADO,
)
def excluir_diretorio(diretorio_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    _obter(sessao, diretorio_id)
    servico_ldap.excluir_diretorio(sessao, diretorio_id, autor.login)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post(
    "/{diretorio_id}/testar",
    response_model=ResultadoTeste,
    summary="Testar conectividade",
    description="Testa a configuração salva e registra data, resultado, tempo de resposta e mensagem de erro.",
    responses=NAO_ENCONTRADO,
)
def testar_diretorio(
    diretorio_id: uuid.UUID,
    dados: SenhaBindTemporaria | None = None,
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(super_root),
) -> ResultadoTeste:
    _obter(sessao, diretorio_id)
    resultado = servico_ldap.testar_diretorio(sessao, diretorio_id, dados.senha_bind if dados else None)
    return ResultadoTeste(**resultado.__dict__)


@roteador.post(
    "/{diretorio_id}/sincronizar",
    response_model=ResultadoSincronizacao,
    summary="Sincronizar usuários",
    description=(
        "Lê todas as identidades do diretório: cria contas corporativas novas, atualiza nome, e-mail, login, "
        "identificador externo e situação, e desativa contas exclusivamente LDAP ausentes. "
        "Contas locais e superusuários são preservados."
    ),
    responses={
        **NAO_ENCONTRADO,
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": RespostaErro, "description": "Diretório inacessível. Nenhum usuário foi alterado."},
    },
)
def sincronizar_diretorio(
    diretorio_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)
) -> ResultadoSincronizacao:
    _obter(sessao, diretorio_id)
    try:
        resumo = servico_ldap.sincronizar(sessao, diretorio_id, autor.login)
    except ErroLdapIndisponivel as erro:
        raise ErroApi(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Não foi possível ler o diretório: {erro} Nenhum usuário foi alterado.",
            "servico_indisponivel",
        )
    return ResultadoSincronizacao(**resumo.__dict__)


@roteador.get(
    "/{diretorio_id}/diagnosticar",
    response_model=DiagnosticoLogin,
    summary="Diagnosticar login",
    description="Procura um login no diretório usando apenas a conta técnica. Não testa a senha da pessoa.",
    responses=NAO_ENCONTRADO,
)
def diagnosticar_login(
    diretorio_id: uuid.UUID,
    login: str = Query(..., min_length=1, max_length=150, description="Login (`sAMAccountName`) ou `userPrincipalName`."),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(super_root),
) -> DiagnosticoLogin:
    diretorio = _obter(sessao, diretorio_id)
    try:
        parametros = ParametrosDiretorio.do_modelo(diretorio)
    except ErroLdapIndisponivel as erro:
        return DiagnosticoLogin(encontrado=False, entradas=0, mensagem=str(erro))
    return DiagnosticoLogin(**cliente_ldap.diagnosticar_login(parametros, login).__dict__)
