#!/usr/bin/env python3
"""Padroniza os checklists dos contratos da Prodesp para o reaproveitamento de documentos entre contratos.
===============================================================================
ARQUIVO: padronizar-checklists-prodesp.py
AUTOR: José Eduardo Santana Martins

(A 1ª linha acima precisa continuar sendo a frase-resumo: o argparse usa a
primeira linha desta docstring como descrição do --help.)

FINALIDADE:
Padronizar os checklists da Prodesp: nomes iguais para o mesmo documento e a
marca "Vale para outros contratos".

RESUMO TÉCNICO:
- Junta variantes do mesmo documento sob um nome padrão (ex.: "CEEP" vira
  "CEEP – Cadastro Estadual de Empresas Punidas");
- marca `vale_outros_contratos` nas certidões e consultas da empresa (não
  mexe em `com_validade`);
- vale para os itens dos checklists ATIVOS e para os documentos das
  competências (nome e marca; anexos, validades e histórico ficam como
  estão).
Versões antigas de checklist e os modelos globais não são tocados. É
idempotente. Usa SQL direto (text) filtrando os contratos pelo CNPJ da
Prodesp; a função `regra` decide o nome padrão de cada item.

Uso (na pasta backend):
    .venv/bin/python ../scripts/padronizar-checklists-prodesp.py           # ensaio
    .venv/bin/python ../scripts/padronizar-checklists-prodesp.py --gravar  # grava

FINALIDADE DE NEGÓCIO:
Com o mesmo nome e a marca, uma certidão da empresa (CND, CRF do FGTS,
CNDT, CADIN estadual etc.) enviada em um contrato pode ser reaproveitada nos
outros contratos da mesma empresa, sem o gestor pedir o documento de novo.

CONTEXTO NO SISTEMA:
Altera as tabelas contratos_checklists_itens e
contratos_competencias_documentos (Módulo Contratos). Competência é o mês
de execução do contrato que será medido e pago. Roda fora da API.

===============================================================================
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# Coloca a pasta backend/ no caminho de importação para usar a sessão do sistema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402

# CNPJ da Prodesp (só dígitos) e os nomes padrão dos cadastros de sanções.
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
    # Cadastros de empresas punidas/inidôneas: cada variante ganha o nome padrão.
    if c.startswith("ceep"):
        return NOME_CEEP, True
    if "ceis" in c.split():
        return NOME_CEIS, True
    if "sancoes" in c and ("e sancoes" in c or c.startswith("sistema eletronico de aplicacao e registro de sancoes")):
        return NOME_ESANCOES, True
    # Demais certidões e consultas da empresa: mantém o nome (só normaliza espaços) e marca.
    if c.startswith(("cnep", "cnciai", "cadastro nacional de condenacoes civeis", "tce sp relacao de apenados", "crf fgts", "cndt",
                     "cnd estadual", "cnd federal", "cnd municipal de origem", "sicaf ", "cadin estadual")):
        return " ".join(nome.split()), True
    return None


def main() -> None:
    """Varre itens e documentos da Prodesp, aplica `regra`, imprime o resumo e grava ou desfaz."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gravar", action="store_true", help="Grava (sem isso, é só um ensaio).")
    gravar = parser.parse_args().gravar
    with FabricaSessao() as sessao:
        # Filtro SQL reaproveitado: só contratos de empresas com o CNPJ da Prodesp
        # (a comparação tira a pontuação do CNPJ gravado).
        filtro_contrato = """c.empresa_id in (select id from contratos_empresas where regexp_replace(cnpj, '\\D', '', 'g') = :cnpj)"""
        # Itens dos checklists ativos (não excluídos) dos contratos da Prodesp.
        itens = sessao.execute(text(f"""
            select i.id, i.nome, i.vale_outros_contratos, c.numero from contratos_checklists_itens i
            join contratos_checklists k on k.id = i.checklist_id and k.ativo and k.excluido_em is null
            join contratos c on c.id = k.contrato_id where {filtro_contrato}"""), {"cnpj": CNPJ_PRODESP}).all()
        # Documentos já lançados nas competências desses contratos.
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
                # Pula o que já está padronizado (idempotência: rodar de novo não altera nada).
                if " ".join(nome.split()) == novo_nome and marcado == marcar:
                    continue
                sessao.execute(text(f"update {tabela} set nome = :nome, vale_outros_contratos = :marca where id = :id"),
                               {"nome": novo_nome, "marca": marcar, "id": id_})
                # Agrupa as alterações por tabela, contrato, nome antigo e nome novo para o resumo.
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
