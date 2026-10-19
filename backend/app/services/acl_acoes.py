# Criado por José Eduardo Santana Martins
# Este arquivo serve para dizer quais ações (permissões independentes) cada módulo oferece nos perfis de acesso.
"""Ações de cada módulo da ACL, para os perfis.

No perfil, cada módulo tem **ações independentes** (como as colunas do GLPI): marcar uma não marca as outras. Uma ação é
identificada pelo **nível da porta** que ela abre nas rotas do módulo (`LEITURA`, `MODIFICACAO` ou `CONTROLE_TOTAL`, os valores de
`NivelAcl`), mas o perfil guarda **cada ação separadamente**, sem herança: quem tem só `CONTROLE_TOTAL` administra e nada mais.

O catálogo sai de `acl_niveis.py` (rótulos e frases de cada módulo): níveis que o módulo declara "Igual a …" ou "Sem efeito"
não viram ação. Por isso cada módulo tem de 1 a 3 ações, com os nomes próprios dele. Para dar mais granularidade a um módulo,
basta acrescentar ações aqui e usar `exigir_acl(slug, ação)` na rota correspondente.
"""

from typing import TypedDict

from app.models.acl import NivelAcl
from app.services.acl_niveis import textos_do_recurso


class AcaoModulo(TypedDict):
    codigo: str
    rotulo: str
    descricao: str


# Ações próprias de um módulo, que **não** correspondem a um nível (LEITURA/MODIFICACAO/CONTROLE_TOTAL): valem só pelo perfil e só na rota que as confere.
# Ex.: quem tem apenas "Lançar ordem bancária" anexa a OB das competências, mas não altera mais nada nos contratos.
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
    """Ações oferecidas pelo módulo, da mais simples à mais ampla."""
    textos = textos_do_recurso(slug)
    do_nivel: list[AcaoModulo] = [
        {"codigo": nivel, "rotulo": textos[nivel]["rotulo"], "descricao": textos[nivel]["descricao"]}
        for nivel in NivelAcl.TODOS
        if _eh_acao_real(textos[nivel]["rotulo"], textos[nivel]["descricao"])
    ]
    return do_nivel + ACOES_EXTRAS.get(slug, [])


def codigos_do_recurso(slug: str) -> list[str]:
    return [a["codigo"] for a in acoes_do_recurso(slug)]


def acao_da_porta(slug: str, nivel: str) -> str | None:
    """Ação que abre a porta de nível `nivel` no módulo: a de menor nível que serve (`>= nivel`); None se o módulo não tem."""
    return next((c for c in codigos_do_recurso(slug) if c in NivelAcl.TODOS and NivelAcl.posicao(c) >= NivelAcl.posicao(nivel)), None)
