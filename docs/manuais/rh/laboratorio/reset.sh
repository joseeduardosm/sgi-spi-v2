#!/bin/sh
# Recria o laboratório do RH do zero (API na 8100, web na 8200). Base isolada (SQLite); nunca toca na produção.
cd "$(dirname "$0")"; LAB=$PWD
fuser -k 8100/tcp 8200/tcp >/dev/null 2>&1; sleep 1
rm -rf lab.db anexos
R=/home/administrador/projeto/backend
PYTHONPATH=$LAB:$R $R/.venv/bin/python $LAB/lab_seed_rh.py > $LAB/seed.log 2>&1 || { tail -20 $LAB/seed.log; exit 1; }
(PYTHONPATH=$LAB:$R nohup $R/.venv/bin/python -c "
import lab_env, lab_patches, uvicorn
lab_patches.aplicar()
uvicorn.run('app.main:app', host='127.0.0.1', port=8100, log_level='warning')
" > api.log 2>&1 &)
(nohup python3 lab_web.py > web.log 2>&1 &)
sleep 8
echo "lab do RH pronto"
