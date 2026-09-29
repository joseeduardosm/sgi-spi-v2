#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para trocar os setores institucionais pela estrutura oficial da SPI.
"""Reorganiza os setores: apaga os institucionais e cadastra a estrutura oficial da SPI.

O que faz (numa transação só, ver `servico_setores.substituir_estrutura`):
- mantém os setores sistêmicos (grupos do sistema) e os membros deles;
- apaga os setores institucionais e os membros deles;
- limpa o Departamento de todos os usuários (no próximo login, o usuário comum escolhe o novo setor);
- cadastra a árvore de `app/services/estrutura_setores.py`.

Uso (como o usuário do projeto, na pasta backend/):
    .venv/bin/python ../scripts/reorganizar-setores.py            # ensaio: mostra o resultado e desfaz
    .venv/bin/python ../scripts/reorganizar-setores.py --gravar   # grava de verdade
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.estrutura_setores import ESTRUTURA_SPI  # noqa: E402
from app.services.servico_setores import substituir_estrutura  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é só um ensaio).")
    args = parser.parse_args()
    with FabricaSessao() as sessao:
        resumo = substituir_estrutura(sessao, ESTRUTURA_SPI, "script:reorganizar-setores")
        print(f"Setores removidos ({len(resumo['setores_removidos'])}): {', '.join(resumo['setores_removidos']) or '—'}")
        print(f"Membros removidos: {resumo['membros_removidos']}")
        print(f"Departamentos limpos: {resumo['departamentos_limpos']}")
        print(f"Setores criados: {len(resumo['setores_criados'])}")
        if args.gravar:
            sessao.commit()
            print("Gravado.")
        else:
            sessao.rollback()
            print("Ensaio: nada foi gravado. Use --gravar para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
