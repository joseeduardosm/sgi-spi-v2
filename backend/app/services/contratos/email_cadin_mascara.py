# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher a máscara (modelo) do e-mail de pendência no CADIN enviado aos prepostos da contratada.
"""Máscara do e-mail de CADIN: assunto e corpo (HTML do editor rico) com placeholders de uma **lista fechada**.

Mesma regra do despacho (`despacho_mascara`): `#nome`, `#nome#` ou `##nome##`; qualquer `#` que não seja da lista barra o salvamento; os valores
são sempre escapados; parágrafo com placeholder de pessoa vazio é omitido. Aqui a lista é a do despacho (contrato, empresa, competência e
equipe) **mais** os dados da consulta ao CADIN (`pendencia`, `dataconsulta`, `horaconsulta`, `usuarioconsulta`).
"""

import re
from html import escape

from app.services.contratos import despacho_mascara

# Placeholders do despacho que não fazem sentido no e-mail (autoridade do despacho e vencimento da nota fiscal)
_FORA = {"nomeautoridade", "cargoautoridade", "setorautoridade", "vencimentodanotafiscal"}

PLACEHOLDERS: dict[str, str] = {n: d for n, d in despacho_mascara.PLACEHOLDERS.items() if n not in _FORA} | {
    "pendencia": "Descrição da pendência encontrada no CADIN, escrita por quem registrou a consulta",
    "dataconsulta": "Data da consulta ao CADIN (dd/mm/aaaa)",
    "horaconsulta": "Hora da consulta ao CADIN (hh:mm)",
    "usuarioconsulta": "Nome de quem registrou a consulta no sistema",
}
DE_PESSOA = despacho_mascara.DE_PESSOA & set(PLACEHOLDERS)

_TOKEN = despacho_mascara._TOKEN  # noqa: SLF001 - mesma sintaxe do despacho


def usados(texto: str) -> set[str]:
    return {m.group(1).lower() for m in _TOKEN.finditer(texto or "") if m.group(1)}


def invalidos(*textos: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos, no assunto e no corpo."""
    ruins: list[str] = []
    for texto in textos:
        ruins += [m.group(0) or "#" for m in _TOKEN.finditer(texto or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher_html(html: str, valores: dict[str, str]) -> str:
    """Corpo preenchido (valores escapados; parágrafo de pessoa sem valor é omitido; placeholder sem valor fica como escrito)."""
    return despacho_mascara.preencher(html, valores)


def preencher_assunto(assunto: str, valores: dict[str, str]) -> str:
    """Assunto em texto simples, sem quebras de linha."""
    texto = _TOKEN.sub(lambda m: valores[m.group(1).lower()] if m.group(1).lower() in valores else m.group(0), assunto or "")
    return re.sub(r"\s+", " ", texto).strip()


def valores_da_consulta(valores_despacho: dict[str, str], consulta, fuso) -> dict[str, str]:
    """Valores do despacho + os da consulta (data e hora no horário de São Paulo)."""
    quando = consulta.criado_em.astimezone(fuso) if consulta.criado_em.tzinfo else consulta.criado_em
    return {**{k: v for k, v in valores_despacho.items() if k in PLACEHOLDERS}, "pendencia": consulta.pendencia, "dataconsulta": f"{quando:%d/%m/%Y}",
            "horaconsulta": f"{quando:%H:%M}", "usuarioconsulta": consulta.criado_por_nome}


# Texto inicial do modelo que a migração semeia (a administração edita em Contratos › Modelos)
ASSUNTO_PADRAO = "Contrato #nrocontrato - #mescompetencia - Pendência no CADIN"
HTML_PADRAO = (
    "<p>Prezados,</p>"
    "<p>Na consulta ao CADIN realizada em <b>#dataconsulta</b>, às <b>#horaconsulta</b>, foi encontrada pendência em nome de "
    "<b>#razaosocialempresa</b> (CNPJ #cnpjempresa), relacionada ao contrato <b>#nrocontrato</b>, competência <b>#mescompetencia</b>.</p>"
    "<p><b>Pendência:</b> #pendencia</p>"
    "<p>Solicitamos a regularização e o envio de comprovante para que o processo de pagamento possa prosseguir.</p>"
    "<p>Atenciosamente,<br/>#usuarioconsulta</p>"
)
