# Criado por José Eduardo Santana Martins
# Este arquivo serve para cifrar e decifrar segredos recuperáveis, como a senha de bind LDAP.
"""Cifra simétrica (Fernet/AES) para segredos que precisam ser recuperados, como a senha de bind LDAP.

Diferença em relação às senhas dos usuários: estas são guardadas como hash (não voltam ao texto
original). A senha de bind do LDAP, ao contrário, precisa ser usada de novo para conectar ao
diretório, por isso é cifrada com uma chave (CHAVE_CIFRA_LDAP) que permite decifrá-la depois.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.configuracao import obter_configuracao


class ErroDecifrarSegredo(Exception):
    """O segredo não pôde ser decifrado (chave trocada ou dado corrompido)."""


def _fernet() -> Fernet:
    """Objeto de cifra montado com a chave CHAVE_CIFRA_LDAP da configuração."""
    return Fernet(obter_configuracao().chave_cifra_ldap.get_secret_value().encode())


def cifrar_segredo(valor: str) -> str:
    """Cifra o texto e devolve o resultado em ASCII, pronto para gravar no banco."""
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def decifrar_segredo(token: str) -> str:
    """Volta ao texto original um valor cifrado por `cifrar_segredo`.

    Se a chave foi trocada depois da gravação, o Fernet recusa o dado (`InvalidToken`); a exceção
    é convertida em `ErroDecifrarSegredo`, com mensagem em português para a tela.
    """
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as erro:
        raise ErroDecifrarSegredo("Não foi possível decifrar a senha armazenada.") from erro
