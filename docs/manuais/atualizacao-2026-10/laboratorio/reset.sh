#!/bin/sh
# Recria o laboratório do zero (API na 8100, web na 8200)
cd "$(dirname "$0")"; LAB=$PWD
fuser -k 8100/tcp 8200/tcp >/dev/null 2>&1; sleep 1
rm -rf lab.db anexos imgs/_*.png
R=/home/administrador/projeto/backend
PYTHONPATH=$LAB:$R $R/.venv/bin/python $LAB/lab_seed.py > $LAB/seed.log 2>&1
(PYTHONPATH=$PWD:$R nohup $R/.venv/bin/python -c "
import lab_env, uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8100, log_level='warning')
" > api.log 2>&1 &)
(nohup python3 lab_web.py > web.log 2>&1 &)
sleep 7
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
from api import *
for l in ("marina","carlos","paulo","ana","roberto","protocolo"): limpar_janelas(l)
print("lab pronto")
PY
