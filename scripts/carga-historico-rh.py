#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para preencher o histórico funcional do RH com o que já existia (períodos de férias, férias e licença-prêmio gozadas, alterações cadastrais).
"""Carga retroativa do histórico funcional (`rh_historico`).

Lê os períodos aquisitivos, os afastamentos gozados e as alterações cadastrais validadas e acrescenta os fatos ao histórico, com quem decidiu e quando.
Idempotente: cada fato guarda a origem e não se duplica. As ocupações de cargo entram pelo próprio script `migrar-cargos-legados.py`.

Uso (da raiz do projeto):
  backend/.venv/bin/python scripts/carga-historico-rh.py             # simulação: só conta
  backend/.venv/bin/python scripts/carga-historico-rh.py --aplicar   # grava
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.rh import servico_historico  # noqa: E402

APLICAR = "--aplicar" in sys.argv

with FabricaSessao() as sessao:
    contagem = servico_historico.carga_retroativa(sessao, aplicar=APLICAR)
    if APLICAR:
        sessao.commit()
    else:
        sessao.rollback()
print(("GRAVADO" if APLICAR else "SIMULAÇÃO (nada foi gravado; use --aplicar)") + f": {contagem}")
