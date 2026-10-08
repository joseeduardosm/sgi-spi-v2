#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para padronizar os checklists da Prodesp: nomes iguais para o mesmo documento e a marca "Vale para outros contratos".
"""Padroniza os checklists dos contratos da Prodesp para o reaproveitamento de documentos entre contratos.

- Junta variantes do mesmo documento sob um nome padrão (ex.: "CEEP" → "CEEP – Cadastro Estadual de Empresas Punidas");
- marca `vale_outros_contratos` nas certidões e consultas da empresa (não mexe em `com_validade`);
- vale para os itens dos checklists **ativos** e para os documentos das competências (nome e marca; anexos, validades e histórico ficam como estão).
Versões antigas de checklist e os modelos globais não são tocados. É idempotente.

Uso (na pasta backend):
    .venv/bin/python ../scripts/padronizar-checklists-prodesp.py            # ensaio: mostra o que mudaria e desfaz
    .venv/bin/python ../scripts/padronizar-checklists-prodesp.py --gravar   # grava
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402

CNPJ_PRODESP = "62577929000135"
NOME_CEEP = "CEEP – Cadastro Estadual de Empresas Punidas"
NOME_CEIS = "CEIS – Cadastro Nacional de Empresas Inidôneas e Suspensas"
NOME_ESANCOES = "e-Sanções – Sistema Eletrônico de Aplicação e Registro de Sanções Administrativas"


def _chave(nome: str) -> str:
    """Texto sem acento, em minúsculas e com um espaço entre palavras (pontuação vira espaço)."""
    sem_acento = unicodedata.normalize("NFD", nome).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).split())


def regra(nome: str) -> tuple[str, bool] | None:
    """(nome padrão, vale para outros contratos) do documento da empresa, ou `None` quando o item é específico do contrato."""
    c = _chave(nome)
    if c.startswith("ceep"):
        return NOME_CEEP, True
    if "ceis" in c.split():
        return NOME_CEIS, True
    if "sancoes" in c and ("e sancoes" in c or c.startswith("sistema eletronico de aplicacao e registro de sancoes")):
        return NOME_ESANCOES, True
    if c.startswith(("cnep", "cnciai", "cadastro nacional de condenacoes civeis", "tce sp relacao de apenados", "crf fgts", "cndt",
                     "cnd estadual", "cnd federal", "cnd municipal de origem", "sicaf ", "cadin estadual")):
        return " ".join(nome.split()), True
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gravar", action="store_true", help="Grava (sem isso, é só um ensaio).")
    gravar = parser.parse_args().gravar
    with FabricaSessao() as sessao:
        filtro_contrato = """c.empresa_id in (select id from contratos_empresas where regexp_replace(cnpj, '\\D', '', 'g') = :cnpj)"""
        itens = sessao.execute(text(f"""
            select i.id, i.nome, i.vale_outros_contratos, c.numero from contratos_checklists_itens i
            join contratos_checklists k on k.id = i.checklist_id and k.ativo and k.excluido_em is null
            join contratos c on c.id = k.contrato_id where {filtro_contrato}"""), {"cnpj": CNPJ_PRODESP}).all()
        documentos = sessao.execute(text(f"""
            select d.id, d.nome, d.vale_outros_contratos, c.numero from contratos_competencias_documentos d
            join contratos_competencias co on co.id = d.competencia_id join contratos c on c.id = co.contrato_id
            where {filtro_contrato}"""), {"cnpj": CNPJ_PRODESP}).all()
        resumo: Counter = Counter()
        for tabela, linhas in (("contratos_checklists_itens", itens), ("contratos_competencias_documentos", documentos)):
            for id_, nome, marcado, numero in linhas:
                alvo = regra(nome)
                if alvo is None:
                    continue
                novo_nome, marcar = alvo
                if " ".join(nome.split()) == novo_nome and marcado == marcar:
                    continue
                sessao.execute(text(f"update {tabela} set nome = :nome, vale_outros_contratos = :marca where id = :id"),
                               {"nome": novo_nome, "marca": marcar, "id": id_})
                resumo[(tabela.split("_", 1)[1], numero, " ".join(nome.split())[:70], novo_nome[:70] if novo_nome != " ".join(nome.split()) else "(só a marca)")] += 1
        for (tabela, numero, antes, depois), qtd in sorted(resumo.items()):
            print(f"{tabela:28} {numero:9} {qtd:3}x  {antes}  →  {depois}")
        print(f"\n{sum(resumo.values())} registro(s) {'alterado(s)' if gravar else 'seriam alterados (ensaio)'}.")
        if gravar:
            sessao.commit()
        else:
            sessao.rollback()


if __name__ == "__main__":
    main()
