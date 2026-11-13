"""
===============================================================================
ARQUIVO: dependencias.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Fornece às rotas a sessão do banco, o usuário autenticado e as checagens de
papel e de ACL (dependências compartilhadas por toda a API).

RESUMO TÉCNICO:
No FastAPI, uma "dependência" é uma função que roda antes da rota e entrega um
valor a ela (Depends(...)). As dependências daqui encadeiam as verificações de
acesso: token válido, usuário ativo, perfil em dia e, por fim, papel exigido ou
nível de ACL exigido. Se qualquer etapa falhar, a rota nem é executada e o
usuário recebe 401 ou 403 no formato {"detalhe", "codigo"}.

Principais funções: obter_usuario_autenticado (token, personificação e
renovação deslizante do token), obter_usuario_atual (perfil em dia),
exigir_papeis, exigir_conta_root, exigir_gestao, exigir_rh e exigir_acl
(fábricas que devolvem a dependência já configurada).

FINALIDADE DE NEGÓCIO:
Garante que só quem tem permissão use cada módulo do SGI, que o cadastro
institucional fique atualizado e que a sessão de quem está trabalhando não caia
no meio do expediente. Na personificação, o SuperRoot vê o sistema como outro
usuário, mas a auditoria registra quem realmente agiu.

CONTEXTO NO SISTEMA:
Usa app/core/seguranca.py (JWT), app/core/banco.py (sessão),
app/services/servico_acl.py, servico_perfil.py e services/rh/papeis.py.
Importado por praticamente todos os arquivos de app/api/routes.

===============================================================================
"""

from collections.abc import Callable

import jwt
from fastapi import Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.core.seguranca import decodificar_token_acesso, renovar_token
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.services import servico_acl, servico_perfil

# Lê o cabeçalho "Authorization: Bearer <token>". Com `auto_error=False`, a ausência do token não
# gera o erro padrão do FastAPI (em inglês): quem trata é `obter_usuario_autenticado`, em português.
esquema_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="TokenBearer",
    description="JWT obtido em `POST /api/autenticacao/login`.",
)


def _nao_autenticado(detalhe: str) -> ErroApi:
    """Erro 401 padrão (o frontend encerra a sessão e volta para o login)."""
    return ErroApi(status.HTTP_401_UNAUTHORIZED, detalhe, "nao_autenticado")


# Cabeçalhos de resposta com o token renovado (renovação deslizante); o frontend os guarda e passa a usar o novo token
CABECALHO_TOKEN_RENOVADO = "X-Token-Renovado"
CABECALHO_TOKEN_EXPIRA_EM = "X-Token-Expira-Em"


def obter_usuario_autenticado(
    resposta: Response,
    credenciais: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    sessao: Session = Depends(obter_sessao),
) -> Usuario:
    """Usuário do token, sem verificar o perfil institucional.

    Parâmetros (injetados pelo FastAPI via `Depends`): a resposta HTTP (para
    gravar cabeçalhos), as credenciais Bearer e a `Session` do SQLAlchemy (a
    conexão com o banco aberta para esta requisição).

    Retorna o `Usuario` dono do token. Efeitos: na personificação marca
    `usuario.personificado_por` e `sessao.info`; perto do vencimento grava nos
    cabeçalhos da resposta um token renovado. Erros: 401 em qualquer falha.

    Use apenas nos endpoints que devem funcionar durante a atualização obrigatória do perfil
    (sessão e próprio perfil). Os demais usam `obter_usuario_atual`.
    """
    # Sem cabeçalho Authorization
    if credenciais is None:
        raise _nao_autenticado("Não autenticado.")
    # Confere assinatura e validade do token
    try:
        conteudo = decodificar_token_acesso(credenciais.credentials)
    except jwt.ExpiredSignatureError:
        raise _nao_autenticado("Sessão expirada.")
    except jwt.InvalidTokenError:
        raise _nao_autenticado("Token inválido.")

    # O campo `sub` do token guarda o id do usuário
    try:
        usuario = sessao.get(Usuario, int(conteudo["sub"]))
    except (TypeError, ValueError):
        raise _nao_autenticado("Token inválido.")
    # Usuário excluído ou desativado depois da emissão do token perde o acesso imediatamente
    if usuario is None or not usuario.ativo:
        raise _nao_autenticado("Usuário inválido ou inativo.")
    # Personificação: `sub` é o usuário personificado e `imp`, o SuperRoot real. O SuperRoot precisa continuar ativo e SuperRoot, senão a sessão cai.
    if conteudo.get("imp") is not None:
        real = sessao.get(Usuario, int(conteudo["imp"]))
        if real is None or not real.ativo or not real.superusuario:
            raise _nao_autenticado("Personificação inválida.")
        usuario.personificado_por = real
        # `auditar` lê isto para gravar quem realmente agiu (sem mexer nas chamadas de auditoria)
        sessao.info["personificado_por"] = (real.id, real.login)
    # Quem está usando o sistema não cai: perto do vencimento, a resposta traz um token novo (só para usuário ativo)
    renovado = renovar_token(conteudo)
    if renovado:
        resposta.headers[CABECALHO_TOKEN_RENOVADO], resposta.headers[CABECALHO_TOKEN_EXPIRA_EM] = renovado[0], renovado[1].isoformat()
    return usuario


def obter_declaracoes(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)) -> dict:
    """Declarações (claims) do token da requisição: `sub`, `ini`, `imp` (SuperRoot real, na personificação).

    Só decodifica o token (sem ir ao banco); usada por rotas que precisam ler as
    declarações cruas, como o fim da personificação. Erro 401 se faltar ou for
    inválido/expirado.
    """
    if credenciais is None:
        raise _nao_autenticado("Não autenticado.")
    try:
        return decodificar_token_acesso(credenciais.credentials)
    except jwt.ExpiredSignatureError:
        raise _nao_autenticado("Sessão expirada.")
    except jwt.InvalidTokenError:
        raise _nao_autenticado("Token inválido.")


def obter_usuario_atual(usuario: Usuario = Depends(obter_usuario_autenticado)) -> Usuario:
    """Usuário autenticado com perfil institucional em dia (só a conta root não passa por essa restrição).

    É a dependência padrão das rotas. O perfil institucional precisa ser revisado
    periodicamente; enquanto estiver pendente, devolve 403 com o código
    `revisao_perfil_obrigatoria` e a lista `campos_pendentes`.
    """
    if servico_perfil.perfil_restrito(usuario):
        # O frontend reconhece este código e leva o usuário para a tela de perfil
        raise ErroApi(
            status.HTTP_403_FORBIDDEN,
            "Atualize seu cadastro para continuar usando o sistema.",
            "revisao_perfil_obrigatoria",
            campos_pendentes=servico_perfil.campos_pendentes(usuario),
        )
    return usuario


def exigir_papeis(*papeis: str) -> Callable[..., Usuario]:
    """Exige que o usuário autenticado possua ao menos um dos papéis informados.

    Uso: `usuario: Usuario = Depends(exigir_papeis(Papel.SUPER_ROOT))`.

    Devolve uma função (a dependência de fato); por isso pode ser configurada com os papéis
    desejados em cada rota.
    """

    # Função interna ("closure"): enxerga a tupla `papeis` recebida acima
    def verificar(usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
        if not any(usuario.possui_papel(p) for p in papeis):
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Acesso negado.", "acesso_negado")
        return usuario

    return verificar


def exigir_conta_root(usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
    """Exige a conta administrativa principal (login `LOGIN_ADMIN`, padrão "root"). Ex.: a tela Notificações do sistema."""
    if not servico_perfil.dispensado(usuario):
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Somente a conta root tem acesso a este recurso.", "acesso_negado")
    return usuario


def exigir_gestao(recurso: str) -> Callable[..., Usuario]:
    """Gravação em recursos administrativos (ex.: `usuarios`, `setores`): SuperRoot ou CONTROLE_TOTAL na ACL.

    Diferente de `exigir_acl`, um recurso **sem regras não libera a gravação**: se as regras forem apagadas,
    só o SuperRoot continua podendo alterar (nunca "todos"). As restrições do que o não SuperRoot pode fazer
    (papel SuperRoot, senhas, grupos sistêmicos) ficam nas próprias rotas.
    """

    def verificar(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> Usuario:
        # SuperRoot (papel administrativo máximo) sempre passa
        if usuario.superusuario:
            return usuario
        # Recurso sem regras nega; com regras, exige a ação de CONTROLE_TOTAL
        if not servico_acl.possui_regras(sessao, recurso) or not servico_acl.pode_porta(sessao, usuario, recurso, NivelAcl.CONTROLE_TOTAL):
            raise ErroApi(status.HTTP_403_FORBIDDEN, f"Esta operação exige CONTROLE_TOTAL em '{recurso}'.", "acl_negado",
                          recurso=recurso, nivel_exigido=NivelAcl.CONTROLE_TOTAL)
        return usuario

    return verificar


def exigir_rh(nivel_minimo: str = NivelAcl.MODIFICACAO) -> Callable[..., Usuario]:
    """Exige pelo menos `nivel_minimo` no módulo RH (ACL `rh`; SuperRoot sempre).

    Estrito como `exigir_gestao`: nunca "aberto a todos". Enquanto o recurso `rh` não tem regras, vale o setor `setor_cgp` (veja `services/rh/papeis.py`)."""
    # Import dentro da função (e não no topo) para evitar importação circular com os serviços do RH
    from app.services.rh import papeis

    def verificar(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> Usuario:
        if not papeis.tem_nivel_rh(sessao, usuario, nivel_minimo):
            raise ErroApi(status.HTTP_403_FORBIDDEN, f"Esta operação exige {nivel_minimo} no módulo RH (Controle de acesso > RH).", "acl_negado",
                          recurso="rh", nivel_exigido=nivel_minimo)
        return usuario

    return verificar


def exigir_acl(recurso: str, nivel_minimo: str = NivelAcl.LEITURA) -> Callable[..., Usuario]:
    """Exige nível de ACL mínimo no recurso (slug) antes de executar o endpoint.

    Uso: `usuario: Usuario = Depends(exigir_acl("usuarios", NivelAcl.MODIFICACAO))`.
    Sem nível suficiente → 403 com `codigo = acl_negado`, recurso, nível exigido e efetivo.
    """

    def verificar(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> Usuario:
        # Regras de setor/diretas valem por nível (LEITURA < MODIFICACAO < CONTROLE_TOTAL); o perfil vale pela ação exata da porta
        if not servico_acl.pode_porta(sessao, usuario, recurso, nivel_minimo):
            efetivo = servico_acl.resolver_acesso(sessao, usuario, recurso)
            raise ErroApi(
                status.HTTP_403_FORBIDDEN,
                f"Você não possui o nível de acesso necessário para este recurso. "
                f"Esta operação exige {nivel_minimo} em '{recurso}'; seu acesso efetivo é {efetivo or 'nenhum'}.",
                "acl_negado",
                recurso=recurso,
                nivel_exigido=nivel_minimo,
                nivel_efetivo=efetivo,
            )
        return usuario

    return verificar
