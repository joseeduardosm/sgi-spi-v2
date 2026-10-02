# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar e conferir hashes de senha (bcrypt) e emitir e validar tokens JWT.
"""Hash de senhas (bcrypt) e emissão/validação de tokens JWT.

- Senhas locais nunca são gravadas em texto: guarda-se só o hash bcrypt, que não pode ser
  revertido. Para conferir o login, calcula-se de novo e compara-se.
- Depois do login, o usuário recebe um JWT (token assinado) que acompanha cada requisição no
  cabeçalho `Authorization: Bearer <token>`. A API não guarda sessão: a assinatura prova que o
  token foi emitido por ela.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.configuracao import obter_configuracao


def gerar_hash_senha(senha: str) -> str:
    """Gera o hash bcrypt da senha (com um "sal" aleatório, então o mesmo texto gera hashes diferentes)."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, hash_senha: str) -> bool:
    """Confere se a senha digitada corresponde ao hash gravado."""
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_senha.encode("utf-8"))
    except ValueError:
        # Hash malformado: trata como credencial inválida em vez de erro 500
        return False


def criar_token_acesso(sujeito: str, declaracoes_extras: dict[str, Any] | None = None, inicio_sessao: datetime | None = None) -> tuple[str, datetime]:
    """Gera um JWT assinado e retorna o token e a data de expiração (UTC).

    `sujeito` é o id do usuário (vai no campo padrão `sub`). As `declaracoes_extras` permitem
    acrescentar informações ao token sem mudar esta função.
    """
    config = obter_configuracao()
    agora = datetime.now(UTC)
    expira_em = agora + timedelta(minutes=config.minutos_expiracao_token)
    conteudo: dict[str, Any] = {
        "sub": sujeito,  # quem é o usuário
        "iat": agora,  # quando o token foi emitido
        "ini": int((inicio_sessao or agora).timestamp()),  # quando a sessão começou (o login); a renovação preserva este instante
        "exp": expira_em,  # até quando vale
        "tipo": "acesso",  # distingue de outros tipos de token que venham a existir
        **(declaracoes_extras or {}),
    }
    token = jwt.encode(conteudo, config.chave_secreta_jwt.get_secret_value(), algorithm=config.algoritmo_jwt)
    return token, expira_em


def renovar_token(conteudo: dict[str, Any], agora: datetime | None = None) -> tuple[str, datetime] | None:
    """Token novo para quem está usando o sistema; None se ainda não é hora ou a sessão atingiu o limite.

    Renova quando faltam menos de `minutos_renovacao_token` para o vencimento. O token novo mantém quem é o usuário, o login
    (`ini`) e as demais declarações; só a validade recomeça. Com `horas_sessao_maxima` > 0, a sessão não passa desse total
    desde o login (tokens antigos, sem `ini`, contam a partir de `iat`).
    """
    config = obter_configuracao()
    agora = agora or datetime.now(UTC)
    expira = datetime.fromtimestamp(conteudo["exp"], UTC)
    if expira - agora > timedelta(minutes=config.minutos_renovacao_token):
        return None
    inicio = datetime.fromtimestamp(conteudo.get("ini", conteudo["iat"]), UTC)
    if config.horas_sessao_maxima and agora - inicio >= timedelta(hours=config.horas_sessao_maxima):
        return None
    extras = {k: v for k, v in conteudo.items() if k not in {"sub", "iat", "exp", "ini", "tipo"}}
    return criar_token_acesso(conteudo["sub"], extras, inicio_sessao=inicio)


def decodificar_token_acesso(token: str) -> dict[str, Any]:
    """Valida assinatura e expiração. Lança jwt.InvalidTokenError se o token for inválido."""
    config = obter_configuracao()
    conteudo = jwt.decode(
        token,
        config.chave_secreta_jwt.get_secret_value(),
        # Aceita somente o algoritmo configurado (impede tokens "sem assinatura" ou com outro algoritmo)
        algorithms=[config.algoritmo_jwt],
        # Recusa tokens sem os campos essenciais
        options={"require": ["sub", "exp", "iat"]},
    )
    if conteudo.get("tipo") != "acesso":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return conteudo
