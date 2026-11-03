# Criado por José Eduardo Santana Martins
# Este arquivo serve para executar o teste de ping dos equipamentos de rede, chamado pelo timer do systemd a cada minuto (a rodada respeita o intervalo dos parâmetros).
"""Tarefas automáticas da Rede.

Uso (pelo timer do systemd, ou à mão para testar):
    backend/.venv/bin/python -m app.tarefas.rede ping   # chamado a cada minuto; testa no intervalo dos parâmetros da Rede

Detalhes em `app/services/rede/ping.py`.
"""

import logging
import sys

from app.core.banco import FabricaSessao
from app.services.rede import ping

log = logging.getLogger("sgi_spi.rede")


def main(argumentos: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if (argumentos[0] if argumentos else "") != "ping":
        print(__doc__)
        return 2
    try:
        with FabricaSessao() as sessao:
            if not ping.hora_da_rodada(sessao):
                return 0
            contagem = ping.testar_todos(sessao)
            sessao.commit()
    except Exception:  # noqa: BLE001 - a rodada falhou inteira: registra e devolve erro ao systemd
        log.exception("Rede ping: falhou")
        return 1
    log.info("Rede ping: %(testados)s testados, %(no_ar)s no ar, %(fora)s fora do ar, %(mudaram)s mudaram", contagem)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
