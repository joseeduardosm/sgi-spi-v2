# Criado por José Eduardo Santana Martins
# Este arquivo serve para executar as tarefas automáticas dos Chamados (prazos, recorrentes e o vigia), chamadas pelos timers do systemd.
"""Tarefas automáticas dos Chamados.

Uso (pelos timers do systemd, ou à mão para testar):
    backend/.venv/bin/python -m app.tarefas.chamados minuto   # a cada minuto: prazos estourados e chamados recorrentes
    backend/.venv/bin/python -m app.tarefas.chamados vigia    # a cada 5 minutos: confere se as tarefas e o e-mail estão andando

Cada rodada fica em `chamados_execucoes` (o painel de saúde e o vigia leem de lá). Detalhes em `app/services/chamados/tarefas_agendadas.py`.
"""

import logging
import sys

from app.core.banco import FabricaSessao
from app.services.chamados import tarefas_agendadas

log = logging.getLogger("sgi_spi.chamados")


def main(argumentos: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    comando = argumentos[0] if argumentos else ""
    funcoes = {"minuto": tarefas_agendadas.rodar_minuto, "vigia": tarefas_agendadas.vigiar}
    if comando not in funcoes:
        print(__doc__)
        return 2
    ok = tarefas_agendadas.executar(FabricaSessao, comando, funcoes[comando])
    log.info("Chamados %s: %s", comando, "ok" if ok else "falhou (ver chamados_execucoes)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
