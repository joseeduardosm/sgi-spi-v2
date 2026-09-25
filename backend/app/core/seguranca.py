"""Hash de senhas (bcrypt) e emissão/validação de tokens JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.configuracao import obter_configuracao


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, hash_senha: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_senha.encode("utf-8"))
    except ValueError:
        # Hash malformado: trata como credencial inválida em vez de erro 500
        return False


def criar_token_acesso(sujeito: str, declaracoes_extras: dict[str, Any] | None = None) -> tuple[str, datetime]:
    """Gera um JWT assinado e retorna o token e a data de expiração (UTC)."""
    config = obter_configuracao()
    agora = datetime.now(UTC)
    expira_em = agora + timedelta(minutes=config.minutos_expiracao_token)
    conteudo: dict[str, Any] = {
        "sub": sujeito,
        "iat": agora,
        "exp": expira_em,
        "tipo": "acesso",
        **(declaracoes_extras or {}),
    }
    token = jwt.encode(conteudo, config.chave_secreta_jwt.get_secret_value(), algorithm=config.algoritmo_jwt)
    return token, expira_em


def decodificar_token_acesso(token: str) -> dict[str, Any]:
    """Valida assinatura e expiração. Lança jwt.InvalidTokenError se o token for inválido."""
    config = obter_configuracao()
    conteudo = jwt.decode(
        token,
        config.chave_secreta_jwt.get_secret_value(),
        algorithms=[config.algoritmo_jwt],
        options={"require": ["sub", "exp", "iat"]},
    )
    if conteudo.get("tipo") != "acesso":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return conteudo
