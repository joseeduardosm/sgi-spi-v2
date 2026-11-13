#!/usr/bin/env python3
"""
===============================================================================
ARQUIVO: migrar-rede-glpi.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Fazer a carga inicial do plano de face da rede (equipamentos, portas e
ligações) a partir do dump do GLPI.

RESUMO TÉCNICO:
Lê o dump `mysqldump` (com dados, feito pela equipe do GLPI) com
`ler_dump` do importador dos Chamados, filtrando as tabelas de
`importacao_glpi.TABELAS_REDE`, e entrega os dados a
`app/services/rede/importacao_glpi.carregar`, onde ficam as regras.
Sem --gravar é ensaio (rollback); com --gravar faz commit. Pode rodar de
novo: o que já veio é pulado. Nunca fala com o GLPI em produção.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-rede-glpi.py glpi.sql           # ENSAIO
    .venv/bin/python ../scripts/migrar-rede-glpi.py glpi.sql --gravar  # grava

FINALIDADE DE NEGÓCIO:
Evita que a equipe de infraestrutura da SPI redigite no Módulo Rede o plano
de face que já estava documentado no GLPI.

CONTEXTO NO SISTEMA:
Usa app.services.chamados.importacao_glpi (leitura do dump),
app.services.rede.importacao_glpi (carga e relatório) e FabricaSessao.
Roda uma vez, fora da API, a partir da pasta backend.

===============================================================================
"""

import argparse
import sys
from pathlib import Path

# Coloca a pasta backend/ no caminho de importação para usar os serviços do sistema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.chamados.importacao_glpi import ErroImportacao, ler_dump  # noqa: E402
from app.services.rede import importacao_glpi  # noqa: E402


def main() -> int:
    """Lê os argumentos, carrega o dump, grava ou desfaz e imprime o relatório; devolve o código de saída."""
    parser = argparse.ArgumentParser(description="Carga inicial do plano de face pelo dump do GLPI.")
    parser.add_argument("dump", type=Path)
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é ensaio).")
    args = parser.parse_args()
    # Lê só as tabelas da rede do dump; arquivo ausente ou dump inválido encerra com código 1.
    try:
        dados = ler_dump(args.dump, importacao_glpi.TABELAS_REDE)
    except (OSError, ErroImportacao) as erro:
        print(f"ERRO: {erro}")
        return 1
    with FabricaSessao() as sessao:
        relatorio = importacao_glpi.carregar(sessao, dados)
        # Ensaio por padrão: tudo o que a carga fez na sessão é desfeito com rollback.
        if args.gravar:
            sessao.commit()
        else:
            sessao.rollback()
    print(relatorio.texto())
    print("\nGRAVADO." if args.gravar else "\nENSAIO: nada foi gravado. Rode de novo com --gravar para valer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
