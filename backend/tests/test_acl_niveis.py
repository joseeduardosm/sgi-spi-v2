# Criado por José Eduardo Santana Martins
# Este arquivo serve para garantir que todo recurso da ACL diga, em texto claro, o que cada nível libera.
"""Cada recurso da ACL precisa de `NIVEIS_POR_RECURSO` com os três níveis escritos (ver `services/acl_niveis.py`)."""

import re
from pathlib import Path

from app.models.acl import NivelAcl
from app.services.acl_niveis import NIVEIS_POR_RECURSO, textos_do_recurso

RAIZ = Path(__file__).resolve().parent.parent
FONTES = list((RAIZ / "app").rglob("*.py"))
MIGRACOES = list((RAIZ / "alembic" / "versions").glob("*.py"))


def _slugs_no_codigo() -> set[str]:
    """Slugs usados em `exigir_acl("x", …)`, `exigir_gestao("x")` e constantes `RECURSO… = "x"`."""
    achados: set[str] = set()
    for arquivo in FONTES:
        texto = arquivo.read_text(encoding="utf-8")
        achados.update(re.findall(r"""exigir_(?:acl|gestao)\(\s*["']([a-z0-9_-]+)["']""", texto))
        achados.update(re.findall(r"""^RECURSOS?(?:_[A-Z]+)?\s*=\s*["']([a-z0-9_-]+)["']""", texto, re.M))
    return achados


def _slugs_nas_migracoes() -> set[str]:
    """Slugs de recursos semeados pelas migrações (`"slug": "x"` ao lado de `description`/`descricao`)."""
    achados: set[str] = set()
    for arquivo in MIGRACOES:
        texto = arquivo.read_text(encoding="utf-8")
        if "acl_recursos" in texto or "resources" in texto:
            achados.update(re.findall(r"""["']slug["']\s*:\s*["']([a-z0-9_-]+)["']""", texto))
    return achados


def test_todo_recurso_tem_os_tres_niveis_escritos():
    for slug, niveis in NIVEIS_POR_RECURSO.items():
        assert set(niveis) == set(NivelAcl.TODOS), slug
        for nivel, texto in niveis.items():
            assert texto["rotulo"].strip() and texto["descricao"].strip(), f"{slug}/{nivel} sem texto"


def test_recursos_do_codigo_e_das_migracoes_estao_cadastrados_em_acl_niveis():
    usados = _slugs_no_codigo() | _slugs_nas_migracoes()
    # ruído de migrações antigas (slugs de outras tabelas): só interessam os que o código protege ou que a migração semeou como recurso
    assert {"protocolo", "contratos", "manuais", "reserva-espacos"} <= usados, "a busca de slugs deixou de achar módulos conhecidos"
    faltando = sorted(s for s in usados if s not in NIVEIS_POR_RECURSO)
    assert not faltando, (
        f"Recurso(s) da ACL sem texto dos níveis: {faltando}. Acrescente a entrada em app/services/acl_niveis.py "
        "dizendo o que Leitura, Modificação e Controle total liberam em cada módulo."
    )


def test_slug_desconhecido_cai_nos_nomes_genericos():
    assert textos_do_recurso("modulo-que-nao-existe")["MODIFICACAO"]["rotulo"] == "Modificação"
