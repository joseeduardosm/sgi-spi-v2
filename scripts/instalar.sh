#!/usr/bin/env bash
# Instalação no servidor (idempotente). O projeto roda no próprio diretório (/home/administrador/projeto).
# Executar com sudo:
#   sudo scripts/instalar.sh [--porta 80] [--dominio portal.spi.sp.gov.br] [--substituir-default]
#
# --porta N              porta HTTP do Nginx (padrão 80); o HTTPS fica na 443
# --dominio NOME         nome do site no HTTPS (padrão portal.spi.sp.gov.br). Exige o certificado com a cadeia em
#                        /etc/ssl/certs/NOME.fullchain.crt e a chave em /etc/ssl/private/NOME.key
# --substituir-default   torna o sgi-spi o site padrão da porta e desativa os demais
#                        sites em sites-enabled que usam default_server nessa porta
#                        (sem esta opção, a instalação é interrompida se houver conflito)
set -euo pipefail

PORTA=80
DOMINIO=portal.spi.sp.gov.br
SUBSTITUIR=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --dominio) DOMINIO="$2"; shift 2 ;;
    --substituir-default) SUBSTITUIR=1; shift ;;
    *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "Execute com sudo." >&2; exit 1; }
USUARIO="${SUDO_USER:?Execute via sudo a partir do usuário do projeto}"
PROJETO="$(cd "$(dirname "$0")/.." && pwd)"

DEFAULT=""
CONFLITOS=$(grep -lE "listen[^;]*\b$PORTA\b[^;]*default_server" /etc/nginx/sites-enabled/* 2>/dev/null | grep -v '/sgi-spi$' || true)
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
sudo -u "$USUARIO" -H env SGI_SEM_RESTART=1 bash "$PROJETO/scripts/deploy.sh"

echo "==> Encerrando processos manuais nas portas 8000/4200 (substituídos pelo systemd e pelo Nginx)"
# O uvicorn manual pode ter sido iniciado com caminho relativo (.venv/bin/uvicorn): casa pelo módulo
pkill -u "$USUARIO" -f "uvicorn app.main:app" || true
pkill -u "$USUARIO" -f "ng serve .*--port 4200" || true
sleep 1

echo "==> systemd: sgi-spi-api"
sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" \
    "$PROJETO/systemd/sgi-spi-api.service" > /etc/systemd/system/sgi-spi-api.service
systemctl daemon-reload
systemctl enable sgi-spi-api
systemctl restart sgi-spi-api

echo "==> systemd: timers da mensageria (fila de e-mails a cada 2 min; lembretes às 07:00)"
for unidade in sgi-spi-mensageria-emails sgi-spi-mensageria-lembretes; do
  for tipo in service timer; do
    sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" \
        "$PROJETO/systemd/$unidade.$tipo" > "/etc/systemd/system/$unidade.$tipo"
  done
done
systemctl daemon-reload
systemctl enable --now sgi-spi-mensageria-emails.timer sgi-spi-mensageria-lembretes.timer

echo "==> Nginx (porta $PORTA)"
if (( SUBSTITUIR )); then
  DEFAULT="default_server"
  for site in /etc/nginx/sites-enabled/*; do
    [[ "$(basename "$site")" == sgi-spi ]] && continue
    if grep -qE "listen[^;]*\b$PORTA\b[^;]*default_server" "$site"; then
      echo "    desativando site $(basename "$site") (continua em sites-available)"
      rm -f "$site"
    fi
  done
fi
for arquivo in "/etc/ssl/certs/$DOMINIO.fullchain.crt" "/etc/ssl/private/$DOMINIO.key"; do
  [[ -f "$arquivo" ]] || { echo "ERRO: falta $arquivo (certificado de $DOMINIO; ver docs/README.md, seção HTTPS)." >&2; exit 1; }
done
sed -e "s/__PORTA__/$PORTA/g" -e "s/ __DEFAULT__/${DEFAULT:+ $DEFAULT}/g" -e "s|__PROJETO__|$PROJETO|g" -e "s/__DOMINIO__/$DOMINIO/g" \
    "$PROJETO/nginx/sgi-spi.conf" > /etc/nginx/sites-available/sgi-spi
ln -sfn /etc/nginx/sites-available/sgi-spi /etc/nginx/sites-enabled/sgi-spi
nginx -t
systemctl reload nginx

echo "==> Verificação"
sleep 2
curl -fsS "http://127.0.0.1:$PORTA/api/saude" && echo
curl -fsS -o /dev/null "http://127.0.0.1:$PORTA/" && echo "frontend OK"
curl -fsS -o /dev/null --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/api/saude" --cacert "/etc/ssl/certs/$DOMINIO.fullchain.crt" && echo "HTTPS OK"
echo "Aplicação: https://$DOMINIO/ (os demais endereços redirecionam para ele)"
