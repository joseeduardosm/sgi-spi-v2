# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter funcionando as unidades systemd antigas (sgi-spi-mensageria-*) até o scripts/instalar.sh trocá-las.
"""Compatibilidade: `python -m app.tarefas.mensageria emails|lembretes` (nome antigo) repassa para `app.tarefas.notificacoes`.

As unidades `sgi-spi-mensageria-emails` e `sgi-spi-mensageria-lembretes` ainda instaladas no servidor chamam este módulo. Depois que o
`scripts/instalar.sh` instalar as unidades novas (`sgi-spi-notificacoes-despachar` e `sgi-spi-notificacoes-lembretes`) e remover as antigas,
este arquivo pode ser apagado.
"""

import sys

from app.tarefas import notificacoes

# Comando antigo -> comando novo
COMANDOS = {"emails": "despachar", "lembretes": "lembretes"}


def main(argumentos: list[str]) -> int:
    comando = COMANDOS.get(argumentos[0], argumentos[0]) if argumentos else ""
    return notificacoes.main([comando])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
