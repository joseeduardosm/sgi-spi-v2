# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de login, sessão e perfil do próprio usuário.
"""Rotas de autenticação (`/api/autenticacao`).

- `POST /login`: troca login e senha por um token JWT;
- `GET /sessao`: quem é o dono do token;
- `GET/PUT /perfil`: o próprio perfil institucional.

As rotas de sessão e perfil usam `obter_usuario_autenticado` (e não `obter_usuario_atual`) porque
precisam funcionar mesmo quando o perfil está pendente: é por elas que o usuário regulariza o cadastro.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from datetime import UTC, datetime

from app.api.dependencias import obter_declaracoes, obter_usuario_autenticado
from app.api.respostas import INVALIDO, VALIDACAO, erro_regra
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.schemas.autenticacao import PedidoPerfilAtivo, PedidoPersonificar, PreferenciaTema, RequisicaoLogin, RespostaToken, UsuarioSessao
from app.schemas.comum import RespostaErro
from app.schemas.usuarios import OpcaoUsuario, PerfilLeitura, RevisaoPerfil
from app.schemas.setores import OpcaoDepartamento
from app.services import servico_acl, servico_admin_usuarios, servico_auditoria, servico_setores
from app.services.servico_admin_usuarios import ErroRegraUsuario
from app.services.servico_autenticacao import ServicoAutenticacao, para_usuario_sessao

roteador = APIRouter(prefix="/autenticacao", tags=["Autenticação"], responses=VALIDACAO)

# Descrição do 401 para a documentação das rotas que exigem token
NAO_AUTENTICADO = {status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Token ausente, inválido ou expirado."}}


@roteador.post(
    "/login",
    response_model=RespostaToken,
    summary="Autenticar usuário",
    description=(
        "Valida login e senha e emite um token JWT de acesso. Com um diretório LDAP ativo, tenta primeiro a "
        "autenticação corporativa; se ela falhar ou o diretório estiver indisponível, tenta a conta local."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"model": RespostaErro, "description": "Usuário ou senha inválidos."}},
)
def entrar(dados: RequisicaoLogin, sessao: Session = Depends(obter_sessao)) -> RespostaToken:
    """Autentica e devolve o token. A mensagem de erro é a mesma para login e senha errados (não revela qual)."""
    servico = ServicoAutenticacao(sessao)
    usuario = servico.autenticar(dados.login, dados.senha)
    if usuario is None:
        raise ErroApi(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha inválidos.", "nao_autenticado")
    return servico.emitir_token(usuario)


@roteador.get(
    "/sessao",
    response_model=UsuarioSessao,
    summary="Usuário autenticado",
    description=(
        "Retorna os dados do usuário dono do token, incluindo a situação do perfil institucional "
        "(`perfil_restrito`). Funciona mesmo com o perfil pendente."
    ),
    responses=NAO_AUTENTICADO,
)
def obter_sessao_atual(usuario: Usuario = Depends(obter_usuario_autenticado)) -> UsuarioSessao:
    """Dados do usuário logado; o frontend chama ao abrir para confirmar que o token ainda vale."""
    return para_usuario_sessao(usuario)


def _inicio_da_sessao(declaracoes: dict) -> datetime:
    """Quando a sessão começou (o novo token preserva, para o limite de duração da sessão continuar valendo)."""
    return datetime.fromtimestamp(declaracoes.get("ini", declaracoes["iat"]), UTC)


@roteador.post(
    "/perfil-ativo",
    response_model=RespostaToken,
    summary="Trocar o perfil ativo",
    description=(
        "Troca o perfil de acesso que vale nesta sessão e devolve um **token novo** (claim `pa`); o frontend guarda o token e recarrega o aplicativo. "
        "O perfil precisa ser **ativo** e do próprio usuário (`403 acesso_negado` caso contrário). Na personificação, vale para o usuário personificado."
    ),
    responses=NAO_AUTENTICADO,
)
def trocar_perfil_ativo(
    dados: PedidoPerfilAtivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado),
    declaracoes: dict = Depends(obter_declaracoes),
) -> RespostaToken:
    """Valida que o perfil é do usuário e emite o token com o perfil escolhido."""
    perfil = next((p for p in servico_acl.perfis_do_usuario(sessao, usuario.id) if p.id == dados.perfil_id), None)
    if perfil is None:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Este perfil não é seu (ou está inativo).", "acesso_negado")
    servico_auditoria.auditar(sessao, usuario.login, "autenticacao.perfil_ativo", f"Perfil {perfil.nome}", autor_id=usuario.id, alvo_tipo="perfil", alvo_id=str(perfil.id))
    sessao.commit()
    return ServicoAutenticacao(sessao).emitir_token(
        usuario, perfil_ativo_id=perfil.id, personificado_por_id=declaracoes.get("imp"), inicio_sessao=_inicio_da_sessao(declaracoes))


@roteador.post(
    "/personificar",
    response_model=RespostaToken,
    summary="Personificar um usuário (SuperRoot)",
    description=(
        "O SuperRoot entra como outro usuário **ativo** para testar o acesso e as permissões: o token novo tem `sub` = o usuário personificado e a "
        "declaração `imp` = o SuperRoot real. O perfil ativo passa a ser o padrão do personificado. Tudo o que for gravado fica auditado com "
        "o autor real (`personificado_por_id`; o autor aparece como \"login (por root)\"). Já personificando, trocar de alvo é permitido (o SuperRoot "
        "original é mantido). `403 acesso_negado` para quem não é SuperRoot; `422` se o alvo for o próprio SuperRoot ou estiver inativo."
    ),
    responses=NAO_AUTENTICADO,
)
def personificar(
    dados: PedidoPersonificar, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado),
    declaracoes: dict = Depends(obter_declaracoes),
) -> RespostaToken:
    """Só o SuperRoot **real** (o do claim `imp` quando já está personificando) personifica."""
    real = getattr(usuario, "personificado_por", None) or usuario
    if not real.superusuario:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Somente o SuperRoot pode personificar outro usuário.", "acesso_negado")
    alvo = sessao.get(Usuario, dados.usuario_id)
    if alvo is None or not alvo.ativo:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Escolha um usuário ativo.", "validacao")
    if alvo.id == real.id:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Você não pode personificar a si mesmo.", "validacao")
    servico_auditoria.auditar(sessao, real.login, "autenticacao.personificar", f"Personificou {alvo.login}", autor_id=real.id, alvo_tipo="usuario", alvo_id=str(alvo.id))
    sessao.commit()
    return ServicoAutenticacao(sessao).emitir_token(alvo, personificado_por_id=real.id, inicio_sessao=_inicio_da_sessao(declaracoes))


@roteador.post(
    "/personificar/parar",
    response_model=RespostaToken,
    summary="Parar de personificar",
    description="Encerra a personificação e devolve o token do SuperRoot real (decidido pela declaração `imp`). `422` se a sessão não está personificando.",
    responses=NAO_AUTENTICADO,
)
def parar_de_personificar(
    sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado), declaracoes: dict = Depends(obter_declaracoes),
) -> RespostaToken:
    """Volta ao SuperRoot original (a identidade real vem do token, não do usuário personificado)."""
    real = getattr(usuario, "personificado_por", None)
    if real is None:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Esta sessão não está personificando ninguém.", "validacao")
    servico_auditoria.auditar(sessao, real.login, "autenticacao.personificar.parar", f"Parou de personificar {usuario.login}", autor_id=real.id, alvo_tipo="usuario", alvo_id=str(usuario.id))
    sessao.commit()
    return ServicoAutenticacao(sessao).emitir_token(real, inicio_sessao=_inicio_da_sessao(declaracoes))


@roteador.put(
    "/tema",
    response_model=UsuarioSessao,
    summary="Salvar meu tema da interface",
    description=(
        "Grava a escolha de tema do próprio usuário (`claro`, `escuro` ou `auto`) para que ela o acompanhe em qualquer "
        "navegador ou aparelho. Funciona mesmo com o perfil pendente e não passa pela validação da CGP. Retorna a sessão atualizada."
    ),
    responses={**NAO_AUTENTICADO, **VALIDACAO},
)
def salvar_meu_tema(
    dados: PreferenciaTema, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)
) -> UsuarioSessao:
    """Atualiza só a coluna `tema` do usuário logado."""
    usuario.tema = dados.tema
    sessao.commit()
    return para_usuario_sessao(usuario)


@roteador.get(
    "/perfil",
    response_model=PerfilLeitura,
    summary="Meu perfil institucional",
    description="Perfil do usuário autenticado. Funciona mesmo com o perfil pendente.",
    responses=NAO_AUTENTICADO,
)
def obter_meu_perfil(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)) -> PerfilLeitura:
    """Perfil institucional do próprio usuário, com a situação de cada campo no fluxo de validação da CGP."""
    from app.services.rh import servico_cadastro

    perfil = servico_admin_usuarios.para_detalhe(sessao, usuario).perfil
    perfil.situacao_campos = servico_cadastro.situacao_campos(sessao, usuario)
    perfil.superior_obrigatorio = servico_cadastro.superior_obrigatorio(sessao, usuario)
    return perfil


@roteador.put(
    "/perfil",
    response_model=UsuarioSessao,
    summary="Atualizar e revalidar meu perfil",
    description=(
        "Confirma o perfil no mês civil. Usuário comum: cada campo alterado fica **pendente de validação da CGP** "
        "(o valor em vigor continua o anterior) e a CGP recebe um e-mail; os valores pendentes já contam como preenchidos. "
        "CGP e SuperRoot: vale na hora. Exige nome completo, e-mail, ramal, cargo, departamento, andar (Subsolo a 13), lado (A ou B) e "
        "superior imediato (sem ser o próprio usuário nem formar ciclo na hierarquia). "
        "Retorna a sessão atualizada, com `perfil_restrito` recalculado."
    ),
    responses={**NAO_AUTENTICADO, **INVALIDO},
)
def revisar_meu_perfil(
    dados: RevisaoPerfil, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)
) -> UsuarioSessao:
    """Grava o perfil; em caso de regra violada, desfaz a transação e responde 400/409."""
    try:
        return para_usuario_sessao(servico_admin_usuarios.revisar_proprio_perfil(sessao, usuario, dados))
    except ErroRegraUsuario as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)


@roteador.get(
    "/perfil/opcoes-departamento",
    response_model=list[OpcaoDepartamento],
    summary="Opções de departamento",
    description=(
        "Setores ativos e institucionais (sem os grupos sistêmicos), em ordem hierárquica, para o combobox "
        "\"Departamento\" do perfil. Funciona mesmo com o perfil pendente e sem acesso ao módulo Setores."
    ),
    responses=NAO_AUTENTICADO,
)
def listar_opcoes_departamento(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_autenticado)) -> list[OpcaoDepartamento]:
    """Departamentos = setores cadastrados em "Setores"."""
    return servico_setores.opcoes_departamento(sessao)


@roteador.get(
    "/perfil/opcoes-gestor",
    response_model=list[OpcaoUsuario],
    summary="Opções de gestor imediato",
    description="Usuários ativos para o seletor de gestor do próprio perfil. Funciona mesmo com o perfil pendente.",
    responses=NAO_AUTENTICADO,
)
def listar_opcoes_gestor(
    busca: str | None = Query(None, max_length=100),
    limite: int = Query(20, ge=1, le=50),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(obter_usuario_autenticado),
) -> list[OpcaoUsuario]:
    """Busca de usuários para escolher o gestor imediato, sem exigir acesso ao módulo Usuários."""
    return servico_admin_usuarios.opcoes(sessao, busca, limite)
