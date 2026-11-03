#!/bin/sh
# Roda um roteiro de prints (ex.: ./rodar.sh prints_1_abrir.py) com o Playwright e as bibliotecas do Chromium do ambiente local.
cd "$(dirname "$0")"
LD_LIBRARY_PATH=/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/libs/usr/lib/x86_64-linux-gnu \
PYTHONPATH=/home/administrador/projeto/backend/.venv/lib/python3.12/site-packages \
  /home/administrador/diagnostico-dhcp/.venv/bin/python "$@"
