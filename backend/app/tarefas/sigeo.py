# Criado por José Eduardo Santana Martins
# Este arquivo serve para executar a conferência diária das ordens bancárias no SIGEO (timer do systemd às 08:00).
"""Conferência diária das OBs no SIGEO.

Uso (pelo timer `sgi-spi-sigeo-ob`, de hora em hora, ou à mão para testar):
    backend/.venv/bin/python -m app.tarefas.sigeo conferir          # confere se já é a hora configurada e ainda não conferiu hoje
    backend/.venv/bin/python -m app.tarefas.sigeo agora             # confere já (ignora a hora)
    backend/.venv/bin/python -m app.tarefas.sigeo ensaio            # só relata

Não faz nada se a integração estiver desligada (Administração > Integração SIGEO). A hora vem da tela (padrão 08:00). Idempotente.
"""

import json
import logging
import sys

from app.core.banco import FabricaSessao
from app.services import servico_integracao_sigeo
from app.services.contratos import servico_ob_sigeo

log = logging.getLogger("sgi_spi.sigeo")


def main(argumentos: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    comando = argumentos[0] if argumentos else ""
    if comando not in ("conferir", "agora", "ensaio"):
        print(__doc__)
        return 2
    with FabricaSessao() as sessao:
        config = servico_integracao_sigeo.obter(sessao)
        if comando in ("conferir", "agora") and not config.ativo:
            log.info("Integração SIGEO desligada: nada a fazer.")
            return 0
        if comando == "conferir" and not servico_integracao_sigeo.hora_de_conferir(config):
            log.info("Ainda não é a hora da conferência (%02d:00) ou já conferiu hoje.", config.hora_conferencia)
            return 0
        resultado = servico_ob_sigeo.executar(sessao, ensaio=comando == "ensaio").como_dict()
    log.info("Conferência SIGEO: %s", json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in resultado.items()}, ensure_ascii=False))
    return 1 if resultado["erros"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
