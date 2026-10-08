# Criado por José Eduardo Santana Martins
# Este arquivo serve para o erro de regra do SLA (vira 400 na API).
"""Erro de regra do SLA."""


class ErroSla(Exception):
    """Política inválida (combinação desconhecida ou resolução menor que a resposta)."""
