#!/bin/sh
# Recomeça o laboratório do manual do zero: para a API e o servidor web, apaga o banco e os anexos, sobe tudo e povoa de novo.
cd "$(dirname "$0")"
for porta in 8301 8302; do
  pid=$(ss -ltnp | grep ":$porta " | grep -o "pid=[0-9]*" | cut -d= -f2)
  [ -n "$pid" ] && kill "$pid"
done
sleep 1
rm -rf lab.db anexos
nohup /home/administrador/projeto/backend/.venv/bin/python api.py > api.log 2>&1 &
nohup python3 web.py > web.log 2>&1 &
for i in $(seq 1 40); do curl -s -o /dev/null http://127.0.0.1:8301/api/saude && break; sleep 1; done
/home/administrador/projeto/backend/.venv/bin/python semear.py
