#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para a carga inicial do plano de face da rede a partir do dump do GLPI.
"""Carga inicial do plano de face (regras em `app/services/rede/importacao_glpi.py`).

Usa o mesmo dump da importação dos chamados (`mysqldump` com dados, feito pela equipe do GLPI). Nunca fala com o GLPI em produção.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-rede-glpi.py glpi.sql             # ENSAIO: carrega, mostra o relatório e desfaz
    .venv/bin/python ../scripts/migrar-rede-glpi.py glpi.sql --gravar    # grava (pode rodar de novo: o que já veio é pulado)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.chamados.importacao_glpi import ErroImportacao, ler_dump  # noqa: E402
from app.services.rede import importacao_glpi  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga inicial do plano de face pelo dump do GLPI.")
    parser.add_argument("dump", type=Path)
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é ensaio).")
    args = parser.parse_args()
    try:
        dados = ler_dump(args.dump, importacao_glpi.TABELAS_REDE)
    except (OSError, ErroImportacao) as erro:
        print(f"ERRO: {erro}")
        return 1
    with FabricaSessao() as sessao:
        relatorio = importacao_glpi.carregar(sessao, dados)
        if args.gravar:
            sessao.commit()
        else:
            sessao.rollback()
    print(relatorio.texto())
    print("\nGRAVADO." if args.gravar else "\nENSAIO: nada foi gravado. Rode de novo com --gravar para valer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
