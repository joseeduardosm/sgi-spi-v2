"""Cifra simétrica (Fernet/AES) para segredos que precisam ser recuperados, como a senha de bind LDAP."""

from cryptography.fernet import Fernet, InvalidToken

from app.core.configuracao import obter_configuracao


class ErroDecifrarSegredo(Exception):
    """O segredo não pôde ser decifrado (chave trocada ou dado corrompido)."""


def _fernet() -> Fernet:
    return Fernet(obter_configuracao().chave_cifra_ldap.get_secret_value().encode())


def cifrar_segredo(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def decifrar_segredo(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as erro:
        raise ErroDecifrarSegredo("Não foi possível decifrar a senha armazenada.") from erro
