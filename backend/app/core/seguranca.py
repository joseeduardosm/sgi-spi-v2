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


def criar_token_acesso(sujeito: str, declaracoes_extras: dict[str, Any] | None = None) -> tuple[str, datetime]:
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
        "exp": expira_em,  # até quando vale
        "tipo": "acesso",  # distingue de outros tipos de token que venham a existir
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
        # Aceita somente o algoritmo configurado (impede tokens "sem assinatura" ou com outro algoritmo)
        algorithms=[config.algoritmo_jwt],
        # Recusa tokens sem os campos essenciais
        options={"require": ["sub", "exp", "iat"]},
    )
    if conteudo.get("tipo") != "acesso":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return conteudo
