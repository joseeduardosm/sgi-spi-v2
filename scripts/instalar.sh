#!/usr/bin/env bash
# Instalação no servidor (idempotente). O projeto roda no próprio diretório (/home/administrador/projeto).
# Executar com sudo:
#   sudo scripts/instalar.sh [--porta 80] [--substituir-default]
#
# --porta N              porta do Nginx (padrão 80)
# --substituir-default   torna o contratos-spi o site padrão da porta e desativa os demais
#                        sites em sites-enabled que usam default_server nessa porta
#                        (sem esta opção, a instalação é interrompida se houver conflito)
set -euo pipefail

PORTA=80
SUBSTITUIR=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --substituir-default) SUBSTITUIR=1; shift ;;
    *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "Execute com sudo." >&2; exit 1; }
USUARIO="${SUDO_USER:?Execute via sudo a partir do usuário do projeto}"
PROJETO="$(cd "$(dirname "$0")/.." && pwd)"

DEFAULT=""
CONFLITOS=$(grep -lE "listen[^;]*\b$PORTA\b[^;]*default_server" /etc/nginx/sites-enabled/* 2>/dev/null | grep -v '/contratos-spi$' || true)
if [[ -n "$CONFLITOS" ]] && (( ! SUBSTITUIR )); then
  echo "ERRO: a porta $PORTA já tem um site padrão ($CONFLITOS)." >&2
  echo "      Acessos por IP iriam para ele. Use --substituir-default ou --porta <outra>." >&2
  exit 1
fi
[[ -z "$CONFLITOS" ]] && DEFAULT="default_server"

echo "==> Projeto em $PROJETO (usuário $USUARIO)"
chmod 600 "$PROJETO/backend/.env" 2>/dev/null || true
# O Nginx (www-data) precisa atravessar os diretórios até o build do Angular.
# o+x permite apenas a travessia: outros usuários não conseguem listar o conteúdo.
d="$PROJETO"
while [[ "$d" != "/" ]]; do chmod o+x "$d"; d="$(dirname "$d")"; done

echo "==> Build e testes (como $USUARIO)"
sudo -u "$USUARIO" -H env CONTRATOS_SEM_RESTART=1 bash "$PROJETO/scripts/deploy.sh"

echo "==> Encerrando processos manuais nas portas 8000/4200 (substituídos pelo systemd e pelo Nginx)"
# O uvicorn manual pode ter sido iniciado com caminho relativo (.venv/bin/uvicorn): casa pelo módulo
pkill -u "$USUARIO" -f "uvicorn app.main:app" || true
pkill -u "$USUARIO" -f "ng serve .*--port 4200" || true
sleep 1

echo "==> systemd: contratos-spi-api"
sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" \
    "$PROJETO/systemd/contratos-spi-api.service" > /etc/systemd/system/contratos-spi-api.service
systemctl daemon-reload
systemctl enable contratos-spi-api
systemctl restart contratos-spi-api

echo "==> Nginx (porta $PORTA)"
if (( SUBSTITUIR )); then
  DEFAULT="default_server"
  for site in /etc/nginx/sites-enabled/*; do
    [[ "$(basename "$site")" == contratos-spi ]] && continue
    if grep -qE "listen[^;]*\b$PORTA\b[^;]*default_server" "$site"; then
      echo "    desativando site $(basename "$site") (continua em sites-available)"
      rm -f "$site"
    fi
  done
fi
sed -e "s/__PORTA__/$PORTA/g" -e "s/ __DEFAULT__/${DEFAULT:+ $DEFAULT}/g" -e "s|__PROJETO__|$PROJETO|g" \
    "$PROJETO/nginx/contratos-spi.conf" > /etc/nginx/sites-available/contratos-spi
ln -sfn /etc/nginx/sites-available/contratos-spi /etc/nginx/sites-enabled/contratos-spi
nginx -t
systemctl reload nginx

echo "==> Verificação"
sleep 2
curl -fsS "http://127.0.0.1:$PORTA/api/saude" && echo
curl -fsS -o /dev/null "http://127.0.0.1:$PORTA/" && echo "frontend OK"
echo "Aplicação: http://$(hostname -I | awk '{print $1}'):$PORTA/"
