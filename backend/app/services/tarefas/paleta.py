# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a paleta de 12 cores dos marcadores das tarefas (a mesma do Odoo) e achar a mais próxima de uma cor.
"""Paleta dos marcadores: (borda, fundo suave, texto) de cada índice de 0 a 11. O índice 0 é o cinza neutro.

A mesma tabela existe no frontend (`marcadores.paleta.ts`); o backend a usa para converter as cores antigas (hexadecimal) e sortear a cor
de um marcador criado sem escolha.
"""

PALETA: tuple[tuple[str, str, str], ...] = (
    ("#8f8f8f", "#d7d7d7", "#3d3d3d"),
    ("#d76a58", "#fedbd5", "#6b1f15"),
    ("#cc7724", "#fedec5", "#5c3003"),
    ("#c09910", "#f4dc9d", "#4c3b04"),
    ("#179dc5", "#c2ecfe", "#044457"),
    ("#b271c6", "#ebcaf6", "#542662"),
    ("#af8563", "#f2e1d4", "#4d3827"),
    ("#17a49d", "#aef4ee", "#034744"),
    ("#5d8ee4", "#c3d9fe", "#193a76"),
    ("#d06792", "#fec5d9", "#671d3f"),
    ("#4ca65a", "#bae5bd", "#044b18"),
    ("#8f7ede", "#e4e1fe", "#3e2f72"),
)


def _rgb(cor: str) -> tuple[int, int, int]:
    cor = cor.lstrip("#")
    return int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16)


def indice_mais_proximo(cor_hex: str) -> int:
    """Índice da cor da paleta (comparando com a borda) mais parecida com a cor hexadecimal informada."""
    alvo = _rgb(cor_hex)
    return min(range(len(PALETA)), key=lambda i: sum((a - b) ** 2 for a, b in zip(alvo, _rgb(PALETA[i][0]), strict=True)))


def borda(indice: int) -> str:
    """Cor hexadecimal da borda do índice (guardada em `MarcadorTarefa.cor` por compatibilidade)."""
    return PALETA[indice][0]
