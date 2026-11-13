#!/bin/sh
# Roda um roteiro de prints (ex.: ./rodar.sh rodar_4_diferenca_manual.py) com o Playwright do ambiente temporário e as bibliotecas do Chromium.
cd "$(dirname "$0")"
LD_LIBRARY_PATH=/tmp/claude-1000/-home-administrador-projeto/394947b1-66eb-494c-a248-14ce9096f589/scratchpad/libs/root/usr/lib/x86_64-linux-gnu \
  /tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad/pw/bin/python "$@"
