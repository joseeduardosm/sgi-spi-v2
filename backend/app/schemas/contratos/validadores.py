# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar CNPJ e CPF pelos dígitos verificadores.
"""Validação de documentos brasileiros (CNPJ e CPF) com dígitos verificadores."""

import re


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digito(numeros: str, pesos: list[int]) -> str:
    resto = sum(int(n) * p for n, p in zip(numeros, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    primeiro = _digito(cnpj[:12], pesos)
    segundo = _digito(cnpj[:12] + primeiro, [6, *pesos])
    return cnpj[12:] == primeiro + segundo


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or len(set(cpf)) == 1:
        return False
    primeiro = _digito(cpf[:9], list(range(10, 1, -1)))
    segundo = _digito(cpf[:9] + primeiro, list(range(11, 1, -1)))
    return cpf[9:] == primeiro + segundo


def normalizar_cnpj(valor: str) -> str:
    """Aceita com ou sem máscara; devolve só os 14 dígitos ou levanta ValueError (mensagem pt-BR)."""
    cnpj = somente_digitos(valor)
    if not cnpj_valido(cnpj):
        raise ValueError("CNPJ inválido")
    return cnpj


def normalizar_cpf(valor: str) -> str:
    cpf = somente_digitos(valor)
    if not cpf_valido(cpf):
        raise ValueError("CPF inválido")
    return cpf
