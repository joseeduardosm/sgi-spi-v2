# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher a máscara (modelo) do despacho de pagamento do documento consolidado.
"""Máscara do despacho: HTML do editor rico com placeholders de uma **lista fechada**.

Aceita as formas `#nome`, `#nome#` e `##nome##` (a pessoa escreve como preferir; o `#` em volta é consumido na troca). Qualquer `#` que não seja
um placeholder da lista barra o salvamento. Os valores são sempre escapados. **Parágrafo com placeholder de pessoa vazio é omitido** (função
sem designado, autoridade não cadastrada): assim o bloco de assinatura inteiro some quando não há quem assine.
"""

import re
from html import escape

from lxml import html as lxml_html

# Funções do contrato: sufixo do placeholder → rótulo mostrado na tela (e escrito pelo placeholder `funcao…`)
FUNCOES: dict[str, tuple[str, str]] = {
    "gestor": ("gestor", "Gestor do Contrato"),
    "gestorsuplente": ("gestor_suplente", "Gestor suplente do Contrato"),
    "fiscaladministrativo": ("fiscal_administrativo", "Fiscal Administrativo do Contrato"),
    "fiscaladministrativosuplente": ("fiscal_administrativo_suplente", "Fiscal Administrativo suplente do Contrato"),
    "fiscaltecnico": ("fiscal_tecnico", "Fiscal Técnico do Contrato"),
    "fiscaltecnicosuplente": ("fiscal_tecnico_suplente", "Fiscal Técnico suplente do Contrato"),
}

# Placeholder → o que é (mostrado na tela de modelos)
PLACEHOLDERS: dict[str, str] = {
    "nrocontrato": "Número do contrato (ex.: 018/2024)",
    "razaosocialempresa": "Razão social da contratada",
    "cnpjempresa": "CNPJ da contratada",
    "objetodocontrato": "Objeto do contrato",
    "processogestao": "Número do processo SEI de gestão do contrato",
    "iniciocompetencia": "Primeiro dia do período da competência (dd/mm/aaaa)",
    "fimcompetencia": "Último dia do período da competência (dd/mm/aaaa)",
    "mescompetencia": "Mês e ano da competência (ex.: Agosto/2026)",
    "vencimentodanotafiscal": "Vencimento da nota fiscal (recebimento + prazo de pagamento, dd/mm/aaaa)",
}
for _sufixo, (_papel, _rotulo) in FUNCOES.items():
    _quem = _rotulo.replace(" do Contrato", "").lower()
    PLACEHOLDERS[f"nome{_sufixo}"] = f"Nome do {_quem} (ponha em negrito no editor)"
    PLACEHOLDERS[f"cargo{_sufixo}"] = f"Cargo do {_quem}, do cadastro do usuário"
    PLACEHOLDERS[f"funcao{_sufixo}"] = f"Função no contrato (\"{_rotulo}\")"
    PLACEHOLDERS[f"setor{_sufixo}"] = f"Setor do {_quem}, do cadastro do usuário"
PLACEHOLDERS |= {
    "nomeautoridade": "Nome da autoridade do despacho (escolhida no contrato; ponha em negrito no editor)",
    "cargoautoridade": "Cargo da autoridade, do cadastro do usuário",
    "setorautoridade": "Setor da autoridade, do cadastro do usuário",
}
# Placeholders de pessoa: parágrafo com um deles vazio é omitido
DE_PESSOA = {n for n in PLACEHOLDERS if n.startswith(("nome", "cargo", "funcao", "setor")) and n not in ("nrocontrato",)}

# `##nome##`, `#nome#` ou `#nome` (letras só); o `(?<!&)` evita entidades HTML como `&#233;`
_TOKEN = re.compile(r"(?<!&)#{1,2}([A-Za-z]*)#{0,2}")


def usados(html: str) -> set[str]:
    """Placeholders (minúsculos) presentes no HTML."""
    return {m.group(1).lower() for m in _TOKEN.finditer(html or "") if m.group(1)}


def invalidos(html: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos (inclui `#` solto)."""
    ruins = [m.group(0) or "#" for m in _TOKEN.finditer(html or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher(html: str, valores: dict[str, str]) -> str:
    """HTML da máscara com os placeholders trocados (escapados); omite parágrafos de pessoa sem valor; o que não tem valor fica como escrito."""
    raiz = lxml_html.fragment_fromstring(html or "", create_parent="div")
    for el in list(raiz):
        texto = lxml_html.tostring(el, encoding="unicode")
        if any(n in DE_PESSOA and not valores.get(n) for n in usados(texto)):
            raiz.remove(el)
    corpo = "".join(lxml_html.tostring(el, encoding="unicode") for el in raiz)
    return _TOKEN.sub(lambda m: escape(valores[m.group(1).lower()]) if m.group(1).lower() in valores else m.group(0), corpo)
