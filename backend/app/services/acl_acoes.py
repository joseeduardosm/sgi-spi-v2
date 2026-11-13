"""
===============================================================================
ARQUIVO: acl_acoes.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Dizer quais ações (permissões independentes) cada módulo oferece nos perfis
de acesso da ACL (lista de controle de acesso do SGI).

RESUMO TÉCNICO:
No perfil, cada módulo tem ações independentes (como as colunas do GLPI):
marcar uma não marca as outras. Uma ação é identificada pelo nível da porta
que ela abre nas rotas (`LEITURA`, `MODIFICACAO` ou `CONTROLE_TOTAL`, os
valores de `NivelAcl`), mas o perfil guarda cada ação separadamente, sem
herança: quem tem só `CONTROLE_TOTAL` administra e nada mais. O catálogo sai
de `acl_niveis.py`: níveis "Igual a ..." ou "Sem ..." não viram ação, então
cada módulo tem de 1 a 3 ações, mais as ACOES_EXTRAS (ex.: LANCAR_OB).

FINALIDADE DE NEGÓCIO:
Permite montar perfis finos, como dar a alguém só o direito de "Lançar ordem
bancária" nos contratos sem poder editar mais nada, ou só aprovar reservas
sem poder solicitá-las.

CONTEXTO NO SISTEMA:
Usado pela tela e pelo serviço de perfis da ACL e pela verificação de acesso
(`exigir_acl(slug, ação)` nas rotas). Para dar mais granularidade a um
módulo, basta acrescentar ações aqui e conferi-las na rota correspondente.

===============================================================================
"""

from typing import TypedDict

from app.models.acl import NivelAcl
from app.services.acl_niveis import textos_do_recurso


class AcaoModulo(TypedDict):
    """Uma ação marcável no perfil: código gravado, rótulo curto e descrição."""
    codigo: str
    rotulo: str
    descricao: str


# Ações próprias de um módulo, que **não** correspondem a um nível (LEITURA/MODIFICACAO/CONTROLE_TOTAL): valem só pelo perfil e só na rota que as confere.
# Ex.: quem tem apenas "Lançar ordem bancária" anexa a OB das competências, mas não altera mais nada nos contratos.
# OB = ordem bancária (o pagamento efetivo); NE = nota de empenho (a reserva do
# orçamento que a OB "debita"). Competência = o mês de execução do contrato.
ACAO_LANCAR_OB = "LANCAR_OB"
ACOES_EXTRAS: dict[str, list[AcaoModulo]] = {
    "contratos": [{
        "codigo": ACAO_LANCAR_OB,
        "rotulo": "Lançar ordem bancária",
        "descricao": "Anexa a OB de uma competência pronta para pagamento (debita as NEs e conclui), em qualquer contrato, sem poder alterar mais nada. "
                     "Para a integração achar o contrato e a competência, combine com \"Consultar contratos\".",
    }],
}


def _eh_acao_real(rotulo: str, descricao: str) -> bool:
    """Nível que o módulo realmente diferencia (não é "Igual a …", "Sem efeito" nem "Sem acesso útil")."""
    return not descricao.startswith("Igual a ") and not rotulo.startswith("Sem ")


def acoes_do_recurso(slug: str) -> list[AcaoModulo]:
    """Ações oferecidas pelo módulo, da mais simples à mais ampla.

    Percorre os três níveis em ordem (NivelAcl.TODOS), descarta os que o
    módulo não diferencia e acrescenta no fim as ações extras do módulo.
    """
    textos = textos_do_recurso(slug)
    do_nivel: list[AcaoModulo] = [
        {"codigo": nivel, "rotulo": textos[nivel]["rotulo"], "descricao": textos[nivel]["descricao"]}
        for nivel in NivelAcl.TODOS
        if _eh_acao_real(textos[nivel]["rotulo"], textos[nivel]["descricao"])
    ]
    return do_nivel + ACOES_EXTRAS.get(slug, [])


def codigos_do_recurso(slug: str) -> list[str]:
    """Só os códigos das ações do módulo (ex.: ["LEITURA", "MODIFICACAO"])."""
    return [a["codigo"] for a in acoes_do_recurso(slug)]


def acao_da_porta(slug: str, nivel: str) -> str | None:
    """Ação que abre a porta de nível `nivel` no módulo: a de menor nível que serve (`>= nivel`); None se o módulo não tem.

    Exemplo: num módulo cujas ações são só LEITURA e CONTROLE_TOTAL, uma rota
    que exige MODIFICACAO é aberta pela ação CONTROLE_TOTAL. As ações extras
    (que não são níveis) são ignoradas aqui. `next(..., None)` devolve o
    primeiro item que atende ou None se nenhum atende.
    """
    return next((c for c in codigos_do_recurso(slug) if c in NivelAcl.TODOS and NivelAcl.posicao(c) >= NivelAcl.posicao(nivel)), None)
