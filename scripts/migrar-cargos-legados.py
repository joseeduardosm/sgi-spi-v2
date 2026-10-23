#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para transformar o cargo e o departamento em texto livre dos usuários em cargos cadastrados no RH, com a pessoa alocada neles.
"""Migra os cargos legados (texto livre) para o cadastro de cargos do RH.

Para cada usuário ativo com cargo em texto e sem ocupação vigente: interpreta o texto ("FCESP 2.16 - Assessor Especial IV" vira tipo FCESP, grupo 2, nível 16,
denominação "Assessor Especial IV"), acha o setor pelo departamento, cria o cargo nesse setor (ou aproveita uma vaga igual) e aloca a pessoa. Texto que não segue o
padrão vira cargo do tipo OUTRO sem nível. Quem tem departamento que não corresponde a um setor cadastrado **não é migrado** e continua na lista "A reconciliar".
Idempotente: quem já ocupa um cargo é ignorado. Cada alocação vai para o histórico (ato "Vínculo do cadastro anterior").

Uso (da raiz do projeto):
  backend/.venv/bin/python scripts/migrar-cargos-legados.py             # simulação: só mostra os números e o que ficaria de fora
  backend/.venv/bin/python scripts/migrar-cargos-legados.py --aplicar   # grava no banco (faça o backup antes: pg_dump)
"""
import sys
from collections import Counter
from pathlib import Path

# Permite importar o pacote `app` do backend ao rodar o script da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.rh import servico_cargos  # noqa: E402

APLICAR = "--aplicar" in sys.argv


def main() -> None:
    resumo: Counter = Counter()
    fora: list[str] = []
    with FabricaSessao() as sessao:
        for p in servico_cargos.reconciliar(sessao):
            if p.setor_id is None:
                resumo["sem setor correspondente (fica em 'A reconciliar')"] += 1
                fora.append(f"{p.login}: cargo «{p.cargo_texto}» / departamento «{p.departamento_texto}»")
                continue
            resumo["padrão do quadro (CCESP/FCESP)" if p.interpretado else "outro cargo (tipo OUTRO)"] += 1
            if APLICAR:
                servico_cargos.vincular_legado(sessao, p.usuario_id, None, setor_id=p.setor_id)
        if APLICAR:
            sessao.commit()
        else:
            sessao.rollback()
    print(("GRAVADO" if APLICAR else "SIMULAÇÃO (nada foi gravado; use --aplicar)") + f": {dict(resumo)}")
    if fora:
        print(f"\n{len(fora)} pessoa(s) não migrada(s) (departamento sem setor cadastrado); o RH resolve em RH > Cargos > A reconciliar:")
        print("\n".join("  - " + linha for linha in fora[:40]) + ("\n  ..." if len(fora) > 40 else ""))


if __name__ == "__main__":
    main()
