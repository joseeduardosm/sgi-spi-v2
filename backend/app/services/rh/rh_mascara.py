# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher as máscaras (modelos) dos textos do RH com os placeholders permitidos.
"""Máscara dos textos do RH: HTML do editor rico com placeholders `#nome` de uma **lista fechada**.

- **Validar:** qualquer `#` que não seja um placeholder da lista barra o salvamento.
- **Preencher:** troca cada placeholder pelo valor (sempre escapado). Placeholder sem valor vira um traço longo (`—`), para o texto nunca sair com "#nome".
"""

import re
from html import escape

# Placeholder → o que é (mostrado na tela de modelos)
PLACEHOLDERS: dict[str, str] = {
    "nome": "Nome completo da pessoa",
    "login": "Login (usuário de rede)",
    "cpf": "CPF, com máscara (000.000.000-00)",
    "rg": "RG (ou CIN, se não houver RG)",
    "rs": "RS/PV (matrícula)",
    "cargo": "Cargo completo (ex.: FCESP 2.16 – Assessor Especial IV)",
    "denominacao": "Denominação do cargo (ex.: Assessor Especial IV)",
    "classificacao": "Classificação do cargo (ex.: FCESP 2.16)",
    "nivel": "Grupo.nível do cargo (ex.: 2.16)",
    "setor": "Unidade (setor) do cargo",
    "siglasetor": "Sigla da unidade",
    "datainicio": "Data prevista de início (dd/mm/aaaa)",
    "dataposse": "Data da posse (dd/mm/aaaa)",
    "numeroresolucao": "Número da resolução reservado no Protocolo (3 dígitos)",
    "anoresolucao": "Ano da resolução",
    "datapublicacao": "Data da publicação no D.O.E. (dd/mm/aaaa)",
    "hoje": "Data de hoje, por extenso",
    "linksistema": "Endereço do SGI SPI",
}

_TOKEN = re.compile(r"(?<!&)#([A-Za-z]*)")


def usados(html: str) -> set[str]:
    return {m.group(1).lower() for m in _TOKEN.finditer(html or "")}


def invalidos(html: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos."""
    ruins = [m.group(0) or "#" for m in _TOKEN.finditer(html or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher(html: str, valores: dict[str, str]) -> str:
    """Troca os placeholders pelos valores (escapados). Sem valor, entra `—`."""
    def trocar(m: re.Match) -> str:
        nome = m.group(1).lower()
        if nome not in PLACEHOLDERS:
            return m.group(0)
        return escape(valores.get(nome) or "—")

    return _TOKEN.sub(trocar, html or "")
