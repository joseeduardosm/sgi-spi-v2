#!/usr/bin/env bash
# Atualiza dependências, roda os testes, compila o frontend e reinicia a API.
# Uso (como usuário do projeto, não root): scripts/deploy.sh [--sem-testes]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TESTES=1
[[ "${1:-}" == "--sem-testes" ]] && TESTES=0

echo "==> Backend: ambiente virtual e dependências"
cd "$ROOT/backend"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-dev.txt
[[ -f .env ]] || { echo "ERRO: backend/.env não existe. Copie de backend/.env.example e preencha." >&2; exit 1; }
# Testes do backend em paralelo (8 processos, pytest-xdist), como manda o CLAUDE.md
if (( TESTES )); then .venv/bin/pytest -q -n 8; fi
echo "==> Banco de dados: aplicando migrações (alembic upgrade head)"
.venv/bin/alembic upgrade head

echo "==> Frontend: dependências e build de produção"
cd "$ROOT/frontend"
npm ci --no-audit --no-fund
if (( TESTES )); then npx ng test --watch=false; fi
npx ng build --configuration production

# SGI_SEM_RESTART=1 é usado pelo instalar.sh, que reinicia o serviço por conta própria
if [[ -z "${SGI_SEM_RESTART:-}" ]] && systemctl list-unit-files sgi-spi-api.service >/dev/null 2>&1; then
  echo "==> Reiniciando sgi-spi-api"
  sudo systemctl restart sgi-spi-api
  # A API leva alguns segundos para subir (dois workers): espera até 60 s pela saúde antes de dar o deploy por concluído
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:8000/api/saude 2>/dev/null && echo && break
    sleep 2
  done || true
  curl -fsS -o /dev/null http://127.0.0.1:8000/api/saude || { echo "!! A API não respondeu em 60 s: veja journalctl -u sgi-spi-api"; exit 1; }
fi
echo "==> Concluído"
