# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar CNPJ e CPF pelos dígitos verificadores.
"""Validação de documentos brasileiros (CNPJ e CPF) com dígitos verificadores.

Os dois últimos dígitos de um CNPJ ou CPF são calculados a partir dos anteriores (módulo 11).
Recalculá-los aqui evita cadastrar números digitados errado.
"""

import re


def somente_digitos(valor: str) -> str:
    """Remove tudo o que não for dígito (pontos, barras, traços e espaços)."""
    return re.sub(r"\D", "", valor or "")


def _digito(numeros: str, pesos: list[int]) -> str:
    """Calcula um dígito verificador pelo módulo 11.

    Multiplica cada número pelo peso da mesma posição, soma e pega o resto da divisão por 11:
    resto 0 ou 1 → dígito 0; senão, 11 − resto.
    """
    resto = sum(int(n) * p for n, p in zip(numeros, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj: str) -> bool:
    """Confere os dois dígitos verificadores de um CNPJ só com números."""
    # Recusa tamanho errado e sequências repetidas (ex.: 00000000000000), que "passariam" na conta
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    # O 1º dígito usa os 12 primeiros números; o 2º usa os 12 + o 1º dígito, com um peso a mais no início
    primeiro = _digito(cnpj[:12], pesos)
    segundo = _digito(cnpj[:12] + primeiro, [6, *pesos])
    return cnpj[12:] == primeiro + segundo


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores de um CPF só com números."""
    if len(cpf) != 11 or not cpf.isdigit() or len(set(cpf)) == 1:
        return False
    # Pesos decrescentes: 10..2 para o 1º dígito e 11..2 para o 2º
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
    """Aceita com ou sem máscara; devolve só os 11 dígitos ou levanta ValueError (mensagem pt-BR)."""
    cpf = somente_digitos(valor)
    if not cpf_valido(cpf):
        raise ValueError("CPF inválido")
    return cpf
