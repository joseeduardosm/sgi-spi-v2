"""
===============================================================================
ARQUIVO: email_cadin_mascara.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Validar e preencher a máscara (modelo) do e-mail de pendência no CADIN que o
sistema envia aos prepostos da empresa contratada.

RESUMO TÉCNICO:
O assunto e o corpo (HTML do editor rico) usam placeholders de uma lista
fechada (`PLACEHOLDERS`), com a mesma sintaxe do despacho: `#nome`, `#nome#`
ou `##nome##`. `invalidos` barra qualquer `#` fora da lista, `preencher_html`
e `preencher_assunto` trocam os placeholders pelos valores (sempre escapados)
e `valores_da_consulta` junta os dados do despacho com os da consulta.

FINALIDADE DE NEGÓCIO:
O CADIN (Cadastro Informativo de créditos não quitados do setor público) é
consultado antes do pagamento. Havendo pendência, a equipe avisa a empresa
por e-mail com texto padronizado, pedindo regularização para seguir com o
pagamento da competência (mês de execução do contrato).

CONTEXTO NO SISTEMA:
Reaproveita `despacho_mascara` (lista de placeholders, regex e preenchimento).
O modelo padrão (`ASSUNTO_PADRAO`/`HTML_PADRAO`) é semeado por migração e
editado em Contratos > Modelos; o envio fica no serviço de notificações.

===============================================================================
"""

import re
from html import escape

from app.services.contratos import despacho_mascara

# Placeholders do despacho que não fazem sentido no e-mail (autoridade do despacho e vencimento da nota fiscal)
# A lista final é: os do despacho, menos os de `_FORA`, mais os da consulta ao CADIN.
# O operador `|` entre dicionários junta os dois (o da direita prevalece em chave repetida).
_FORA = {"nomeautoridade", "cargoautoridade", "setorautoridade", "vencimentodanotafiscal"}

PLACEHOLDERS: dict[str, str] = {n: d for n, d in despacho_mascara.PLACEHOLDERS.items() if n not in _FORA} | {
    "pendencia": "Descrição da pendência encontrada no CADIN, escrita por quem registrou a consulta",
    "dataconsulta": "Data da consulta ao CADIN (dd/mm/aaaa)",
    "horaconsulta": "Hora da consulta ao CADIN (hh:mm)",
    "usuarioconsulta": "Nome de quem registrou a consulta no sistema",
}
# Placeholders que representam uma pessoa (ex.: gestor, fiscal). Se o valor vier vazio,
# o parágrafo inteiro que os contém é omitido do e-mail. O `&` é a interseção de conjuntos.
DE_PESSOA = despacho_mascara.DE_PESSOA & set(PLACEHOLDERS)

_TOKEN = despacho_mascara._TOKEN  # noqa: SLF001 - mesma sintaxe do despacho


def usados(texto: str) -> set[str]:
    """Nomes de placeholders (em minúsculas) que aparecem no texto, válidos ou não.

    Recebe o assunto ou o corpo; texto vazio/None devolve conjunto vazio.
    """
    return {m.group(1).lower() for m in _TOKEN.finditer(texto or "") if m.group(1)}


def invalidos(*textos: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos, no assunto e no corpo.

    Recebe quantos textos quiser (assunto, corpo) e devolve a lista, sem repetições
    e na ordem em que apareceram, para a tela mostrar o que precisa ser corrigido.
    Lista vazia significa que o modelo pode ser salvo.
    """
    ruins: list[str] = []
    # Percorre cada `#...` encontrado pela regex e guarda os que não estão na lista fechada
    for texto in textos:
        ruins += [m.group(0) or "#" for m in _TOKEN.finditer(texto or "") if m.group(1).lower() not in PLACEHOLDERS]
    # `dict.fromkeys` remove repetidos mantendo a ordem original
    return list(dict.fromkeys(ruins))


def preencher_html(html: str, valores: dict[str, str]) -> str:
    """Corpo preenchido (valores escapados; parágrafo de pessoa sem valor é omitido; placeholder sem valor fica como escrito)."""
    return despacho_mascara.preencher(html, valores)


def preencher_assunto(assunto: str, valores: dict[str, str]) -> str:
    """Assunto em texto simples, sem quebras de linha.

    Troca cada placeholder conhecido pelo seu valor; o que não tem valor fica
    como foi escrito. No fim, espaços e quebras de linha repetidos viram um só
    espaço, porque o assunto de e-mail precisa ser uma linha única.
    """
    texto = _TOKEN.sub(lambda m: valores[m.group(1).lower()] if m.group(1).lower() in valores else m.group(0), assunto or "")
    return re.sub(r"\s+", " ", texto).strip()


def valores_da_consulta(valores_despacho: dict[str, str], consulta, fuso) -> dict[str, str]:
    """Valores do despacho + os da consulta (data e hora no horário de São Paulo).

    Parâmetros: `valores_despacho` (já calculados para o contrato/competência),
    `consulta` (registro da consulta ao CADIN, com `criado_em`, `pendencia` e
    `criado_por_nome`) e `fuso` (fuso horário de São Paulo). Só devolve chaves
    que existem em `PLACEHOLDERS`.
    """
    # Data com fuso é convertida para São Paulo; data "ingênua" (sem fuso) é usada como está
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
