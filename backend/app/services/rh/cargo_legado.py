# Criado por José Eduardo Santana Martins
# Este arquivo serve para interpretar o texto livre de cargo dos cadastros antigos ("FCESP 2.16 - Assessor Especial IV") em tipo, grupo, nível e denominação.
"""Interpretação do cargo escrito à mão (função pura, sem banco).

O cadastro antigo guardava o cargo como texto livre. O padrão do quadro da SPI (LC 1.395/2023 e Decreto 69.377/2025) é `TIPO G.NN - Denominação` (ou a denominação primeiro, como está nos cadastros):
tipo CCESP (cargo em comissão) ou FCESP (função de confiança), grupo 1 (direção e chefia) ou 2 (assessoria) e nível (1 a 17), ex.: "FCESP 2.16 - Assessor
Especial IV" ou "CCESP 1.15 – Diretor". O que não segue o padrão vira cargo do tipo OUTRO, sem nível, com o texto inteiro como denominação.
"""

import re
from dataclasses import dataclass

# Dois formatos reais nos cadastros: tipo primeiro ("FCESP 2.16 - Assessor Especial IV") e tipo por último ("Assessor II - CCESP 2.10", "Chefe de Gabinete - CCESP 1.16",
# "Assistente Técnico III CCESP 2.07", "Secretário Executivo - CCESP 1.18 (NES)"). O grupo/nível pode vir como "2.16", "2 16" ou "2-16"; sufixo entre parênteses é ignorado.
_TIPO_ANTES = re.compile(
    r"^(?P<tipo>CCESP|FCESP|CC|FC)\s*(?P<grupo>[12])\s*[.\- ]\s*(?P<nivel>\d{1,2})\s*(?:[-–—:]\s*|\s+)(?P<denominacao>.+?)\s*$", re.IGNORECASE)
_TIPO_DEPOIS = re.compile(
    r"^(?P<denominacao>.+?)\s*[-–—:]?\s*(?P<tipo>CCESP|FCESP)\s*(?P<grupo>[12])\s*[.\- ]\s*(?P<nivel>\d{1,2})\s*(?:\([^)]*\))?\s*$", re.IGNORECASE)
_TIPOS = {"CCESP": "CCESP", "CC": "CCESP", "FCESP": "FCESP", "FC": "FCESP"}


@dataclass(frozen=True)
class CargoInterpretado:
    tipo: str            # CCESP, FCESP ou OUTRO
    grupo: int | None
    nivel: int | None
    denominacao: str
    interpretado: bool   # True quando seguia o padrão do quadro


def interpretar(texto: str | None) -> CargoInterpretado | None:
    """Cargo do texto livre; `None` se o texto estiver vazio."""
    limpo = re.sub(r"\s+", " ", (texto or "")).strip()
    if not limpo:
        return None
    for padrao in (_TIPO_ANTES, _TIPO_DEPOIS):
        m = padrao.match(limpo)
        if m and 1 <= int(m.group("nivel")) <= 18 and m.group("denominacao").strip(" -–—:"):
            return CargoInterpretado(_TIPOS[m.group("tipo").upper()], int(m.group("grupo")), int(m.group("nivel")), m.group("denominacao").strip(" -–—:")[:200], True)
    return CargoInterpretado("OUTRO", None, None, limpo[:200], False)
