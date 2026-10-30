#!/bin/sh
# Criado por José Eduardo Santana Martins
# Este arquivo serve para rodar um passo da carga histórica do contrato 010/2024 no banco de ensaio (padrão) ou em produção.
# Uso: ./rodar.sh ensaio|producao <passo.py> [argumentos]   (ensaio usa o banco appdb_ensaio_carga e uma pasta de anexos temporária)
ALVO="$1"; shift
cd "$(dirname "$0")/../.." || exit 1
BASE_URL=$(.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from app.core.configuracao import obter_configuracao
print(obter_configuracao().url_banco_dados)")
if [ "$ALVO" = "ensaio" ]; then
  export URL_BANCO_DADOS="${BASE_URL%/*}/appdb_ensaio_carga"
  export ANEXOS_DIRETORIO=/home/administrador/backups-carga/anexos_ensaio
  mkdir -p "$ANEXOS_DIRETORIO"
elif [ "$ALVO" != "producao" ]; then echo "alvo: ensaio ou producao"; exit 1; fi
export CARGA_ALVO="$ALVO"
PASSO="$1"; shift
PYTHONPATH=. exec .venv/bin/python "scripts_manutencao/carga_010_2024/$PASSO" "$@"
