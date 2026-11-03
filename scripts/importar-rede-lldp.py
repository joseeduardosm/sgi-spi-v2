#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para carregar no plano de face da rede o inventário levantado por LLDP nos switches (regras em app/services/rede/importacao_lldp.py).
"""Carga da Rede pelo inventário LLDP.

O inventário é um JSON fora do Git (ex.: `dados/rede/inventario-lldp-2026-11-03.json`), montado só com comandos de leitura
(`display lldp neighbor`, `display interface brief`) nos switches. Este script não fala com os switches.

Uso (na pasta backend):
    .venv/bin/python ../scripts/importar-rede-lldp.py ../dados/rede/inventario-lldp-2026-11-03.json            # ENSAIO: mostra o relatório e desfaz
    .venv/bin/python ../scripts/importar-rede-lldp.py ../dados/rede/inventario-lldp-2026-11-03.json --gravar   # grava (pode rodar de novo)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.rede import importacao_lldp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga da Rede pelo inventário LLDP.")
    parser.add_argument("inventario", type=Path)
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é ensaio).")
    args = parser.parse_args()
    try:
        inventario = json.loads(args.inventario.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        print(f"ERRO: não consegui ler o inventário: {erro}")
        return 1
    with FabricaSessao() as sessao:
        relatorio = importacao_lldp.carregar(sessao, inventario)
        if args.gravar:
            sessao.commit()
        else:
            sessao.rollback()
    print(relatorio.texto())
    print("\nGRAVADO." if args.gravar else "\nENSAIO: nada foi gravado. Rode de novo com --gravar para valer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
