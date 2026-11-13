#!/usr/bin/env python3
"""
===============================================================================
ARQUIVO: reorganizar-setores.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Trocar os setores institucionais pela estrutura oficial da SPI: apaga os
institucionais e cadastra a árvore oficial.

RESUMO TÉCNICO:
Chama `servico_setores.substituir_estrutura` numa transação só, que:
- mantém os setores sistêmicos (grupos do sistema) e os membros deles;
- apaga os setores institucionais e os membros deles;
- limpa o Departamento de todos os usuários (no próximo login, o usuário
  comum escolhe o novo setor);
- cadastra a árvore de `app/services/estrutura_setores.py`.
Imprime o resumo e só faz commit com --gravar (sem ele, rollback).

Uso (como o usuário do projeto, na pasta backend/):
    .venv/bin/python ../scripts/reorganizar-setores.py            # ensaio
    .venv/bin/python ../scripts/reorganizar-setores.py --gravar   # grava

FINALIDADE DE NEGÓCIO:
Alinha o cadastro de setores do sistema ao organograma oficial da SPI, base
para a lotação das pessoas e para os módulos que filtram por setor.

CONTEXTO NO SISTEMA:
Usa app.services.servico_setores e app.services.estrutura_setores
(ESTRUTURA_SPI). Esta docstring inteira aparece no --help (o argparse a usa
como descrição). Roda fora da API, a partir da pasta backend.

===============================================================================
"""

import argparse
import sys
from pathlib import Path

# Coloca a pasta backend/ no caminho de importação para usar os serviços do sistema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.estrutura_setores import ESTRUTURA_SPI  # noqa: E402
from app.services.servico_setores import substituir_estrutura  # noqa: E402


def main() -> int:
    """Executa a troca da estrutura, imprime o resumo e grava ou desfaz; devolve o código de saída."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é só um ensaio).")
    args = parser.parse_args()
    with FabricaSessao() as sessao:
        resumo = substituir_estrutura(sessao, ESTRUTURA_SPI, "script:reorganizar-setores")
        print(f"Setores removidos ({len(resumo['setores_removidos'])}): {', '.join(resumo['setores_removidos']) or '—'}")
        print(f"Membros removidos: {resumo['membros_removidos']}")
        print(f"Departamentos limpos: {resumo['departamentos_limpos']}")
        print(f"Setores criados: {len(resumo['setores_criados'])}")
        # Ensaio por padrão: rollback desfaz a troca; só --gravar confirma (commit).
        if args.gravar:
            sessao.commit()
            print("Gravado.")
        else:
            sessao.rollback()
            print("Ensaio: nada foi gravado. Use --gravar para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
