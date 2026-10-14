# Criado por José Eduardo Santana Martins
# Este arquivo serve para tratar a descrição das tarefas: HTML do editor rico (sanitizado) ou texto simples antigo.
"""Descrição de tarefa.

A tela grava HTML do editor rico (o mesmo das Contratações); descrições antigas continuam como texto simples e são exibidas com quebras
de linha e links. O HTML é sanitizado (`nh3`): só formatação, listas, tabelas e links http(s)/mailto passam.
"""

import re

from app.services.contratacoes.conteudo import ErroConteudo, sanitizar, texto_do_html

# Há alguma tag HTML (e não só um "<" solto do texto)?
_TEM_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


def sanitizar_descricao(valor: str) -> str:
    """HTML sanitizado; texto simples (sem tags) fica como está; editor vazio (`<p></p>`) vira vazio."""
    if not valor or not _TEM_TAG.search(valor):
        return valor or ""
    try:
        limpo = sanitizar(valor)
    except ErroConteudo as erro:
        raise ValueError(str(erro)) from erro
    return limpo if texto_do_html(limpo) or "<table" in limpo.lower() else ""


def texto_da_descricao(valor: str) -> str:
    """Texto puro da descrição (para a busca): remove as tags do HTML e mantém o texto simples antigo."""
    return texto_do_html(valor) if _TEM_TAG.search(valor or "") else (valor or "")
