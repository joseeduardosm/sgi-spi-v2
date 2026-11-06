#!/usr/bin/env bash
# Instalação do SGI SPI numa máquina Ubuntu nova ou já instalada (idempotente: pode rodar de novo para atualizar).
# Provisiona tudo o que o sistema precisa: pacotes do sistema, Node 22, PostgreSQL (usuário e banco), backend/.env,
# pasta dos anexos, sudoers do restart, certificado (autoassinado se não houver), build, serviços e Nginx.
#
# Executar com sudo, a partir do usuário que vai rodar o sistema (dono do diretório do projeto).
#
# Máquina nova (sem o projeto): baixe só este script; ele instala o git, clona o repositório do GitHub em
# ~/projeto (ou --diretorio) e continua a partir da cópia clonada:
#   curl -fsSL https://raw.githubusercontent.com/joseeduardosm/sgi-spi-v2/estado-atual-servidor/scripts/instalar.sh -o instalar.sh
#   sudo bash instalar.sh --dominio homologacao.spi.sp.gov.br --homologacao --sem-testes
# (não use "curl … | sudo bash": a senha do SuperRoot é pedida no terminal)
#
# Máquina com o projeto (atualizar ou reaplicar Nginx/systemd):
#   sudo scripts/instalar.sh --dominio portal.spi.sp.gov.br               # usa o código como está na pasta
#   sudo scripts/instalar.sh --dominio portal.spi.sp.gov.br --atualizar   # antes, puxa a versão nova do GitHub
#
# --diretorio DIR        onde clonar numa máquina nova (padrão: pasta "projeto" na home do usuário)
# --ramo NOME            ramo do GitHub a clonar (padrão estado-atual-servidor)
# --atualizar            com o projeto já na máquina: "git pull" do ramo atual antes de instalar (recusa se houver
#                        alteração local não commitada, para não perder nada)
#
# --dominio NOME|IP      nome do site no HTTPS (padrão portal.spi.sp.gov.br, que é PRODUÇÃO). Sem DNS (ex.: homologação
#                        em casa), informe o IP da máquina: o site fica em https://IP e o certificado autoassinado sai para o IP. Certificado esperado em
#                        /etc/ssl/certs/NOME.fullchain.crt e chave em /etc/ssl/private/NOME.key; sem eles, gera um
#                        autoassinado (o navegador vai avisar até trocar pelo certificado oficial)
# --homologacao          ambiente de testes: e-mails e pop-ups do navegador são simulados (nada sai do servidor),
#                        SIGEO, sincronização com o AD e parabéns de aniversário não rodam, e a tela mostra a faixa
#                        "HOMOLOGAÇÃO". Exige --dominio diferente do de produção
# --sem-testes           não roda os testes do backend e do frontend no build (mais rápido na primeira instalação)
# --porta N              porta HTTP do Nginx (padrão 80); o HTTPS fica na 443
# --substituir-default   torna o sgi-spi o site padrão da porta e desativa os demais sites com default_server nessa porta
# --sem-pacotes          não instala pacotes do sistema (máquina já preparada ou sem acesso à internet)
set -euo pipefail

# Repositório público do sistema (clonado por HTTPS, sem senha)
REPOSITORIO=https://github.com/joseeduardosm/sgi-spi-v2.git
RAMO=estado-atual-servidor
DIRETORIO=""
ATUALIZAR=0
# Guarda as opções originais para repassar à cópia clonada
OPCOES=("$@")
PORTA=80
DOMINIO=portal.spi.sp.gov.br
DOMINIO_PRODUCAO=portal.spi.sp.gov.br
SUBSTITUIR=0
HOMOLOGACAO=0
SEM_TESTES=0
PACOTES=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --dominio) DOMINIO="$2"; shift 2 ;;
    --substituir-default) SUBSTITUIR=1; shift ;;
    --homologacao) HOMOLOGACAO=1; shift ;;
    --sem-testes) SEM_TESTES=1; shift ;;
    --sem-pacotes) PACOTES=0; shift ;;
    --diretorio) DIRETORIO="$2"; shift 2 ;;
    --ramo) RAMO="$2"; shift 2 ;;
    --atualizar) ATUALIZAR=1; shift ;;
    *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "Execute com sudo." >&2; exit 1; }
USUARIO="${SUDO_USER:?Execute via sudo a partir do usuário do projeto}"
como_usuario() { sudo -u "$USUARIO" -H "$@"; }
# Homologação apontando para o domínio de produção redirecionaria tudo para produção
if (( HOMOLOGACAO )) && [[ "$DOMINIO" == "$DOMINIO_PRODUCAO" ]]; then
  echo "ERRO: em homologação informe --dominio com o endereço da homologação (o padrão é o de produção)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------------------------
# 0. Código do sistema: clona do GitHub numa máquina nova, ou usa (e, com --atualizar, atualiza) o que já está aqui
# ---------------------------------------------------------------------------------------------
AQUI="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
if [[ -d "$AQUI/.git" && -f "$AQUI/backend/requirements-dev.txt" ]]; then
  PROJETO="$AQUI"
  if (( ATUALIZAR )); then
    echo "==> Atualizando o código do GitHub ($(como_usuario git -C "$PROJETO" rev-parse --abbrev-ref HEAD))"
    if [[ -n "$(como_usuario git -C "$PROJETO" status --porcelain --untracked-files=no)" ]]; then
      echo "ERRO: há alterações locais não commitadas em $PROJETO. Faça o commit (ou descarte) antes de --atualizar." >&2
      exit 1
    fi
    como_usuario git -C "$PROJETO" pull --ff-only
    # Segue com a versão nova deste script (sem --atualizar, para não puxar de novo)
    SEGUIR=()
    for opcao in "${OPCOES[@]}"; do [[ "$opcao" == --atualizar ]] || SEGUIR+=("$opcao"); done
    exec bash "$PROJETO/scripts/instalar.sh" "${SEGUIR[@]}"
  fi
else
  # Script baixado sozinho: traz o repositório e continua a partir da cópia clonada
  PROJETO="${DIRETORIO:-$(getent passwd "$USUARIO" | cut -d: -f6)/projeto}"
  if ! command -v git >/dev/null; then
    echo "==> Instalando o git"
    DEBIAN_FRONTEND=noninteractive apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q git ca-certificates
  fi
  if [[ -d "$PROJETO/.git" ]]; then
    echo "==> Projeto já clonado em $PROJETO (use --atualizar para puxar a versão nova)"
  elif [[ -e "$PROJETO" && -n "$(ls -A "$PROJETO" 2>/dev/null)" ]]; then
    echo "ERRO: $PROJETO já existe e não está vazio. Escolha outra pasta com --diretorio." >&2
    exit 1
  else
    echo "==> Clonando $REPOSITORIO (ramo $RAMO) em $PROJETO"
    install -d -o "$USUARIO" -g "$USUARIO" "$PROJETO"
    como_usuario git clone --branch "$RAMO" "$REPOSITORIO" "$PROJETO"
  fi
  exec bash "$PROJETO/scripts/instalar.sh" "${OPCOES[@]}"
fi
ENV="$PROJETO/backend/.env"

echo "==> Projeto em $PROJETO (usuário $USUARIO, domínio $DOMINIO$( (( HOMOLOGACAO )) && echo ', HOMOLOGAÇÃO'))"

# ---------------------------------------------------------------------------------------------
# 1. Pacotes do sistema e Node 22
# ---------------------------------------------------------------------------------------------
if (( PACOTES )); then
  echo "==> Pacotes do sistema"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q git python3 python3-venv python3-pip nginx postgresql postgresql-contrib curl ca-certificates gnupg openssl openssh-server
  # O Angular do projeto exige Node 22 (o build falha em versões antigas)
  if ! command -v node >/dev/null || [[ "$(node -v | sed 's/^v//; s/\..*//')" -lt 22 ]]; then
    echo "==> Node 22 (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y -q nodejs
  fi
fi
for comando in python3 node npm psql nginx openssl; do
  command -v "$comando" >/dev/null || { echo "ERRO: falta '$comando' (rode sem --sem-pacotes ou instale à mão)." >&2; exit 1; }
done
# O sistema trabalha no horário de São Paulo (a API ajusta o próprio processo; o servidor fica igual, para os logs baterem)
timedatectl set-timezone America/Sao_Paulo 2>/dev/null || true

# ---------------------------------------------------------------------------------------------
# 2. Ambiente Python (antes do .env: o hash da senha do admin usa o bcrypt do projeto)
# ---------------------------------------------------------------------------------------------
echo "==> Ambiente Python do backend"
[[ -d "$PROJETO/backend/.venv" ]] || como_usuario python3 -m venv "$PROJETO/backend/.venv"
como_usuario "$PROJETO/backend/.venv/bin/pip" install -q --upgrade pip
como_usuario "$PROJETO/backend/.venv/bin/pip" install -q -r "$PROJETO/backend/requirements-dev.txt"

# ---------------------------------------------------------------------------------------------
# 3. PostgreSQL e backend/.env (o .env existente nunca é sobrescrito)
# ---------------------------------------------------------------------------------------------
if [[ ! -f "$ENV" ]]; then
  echo "==> Banco de dados e backend/.env (primeira instalação)"
  systemctl enable --now postgresql
  BANCO=sgi_spi
  SENHA_BANCO="$(openssl rand -hex 24)"
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$BANCO'" | grep -q 1; then
    sudo -u postgres psql -qc "ALTER ROLE $BANCO WITH LOGIN PASSWORD '$SENHA_BANCO'"
  else
    sudo -u postgres psql -qc "CREATE ROLE $BANCO WITH LOGIN PASSWORD '$SENHA_BANCO'"
  fi
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$BANCO'" | grep -q 1 || sudo -u postgres createdb -O "$BANCO" "$BANCO"

  # Senha do SuperRoot (login root): pedida aqui, só o hash bcrypt vai para o .env
  while true; do
    read -rsp "Senha do SuperRoot (login root): " SENHA_ADMIN; echo
    read -rsp "Confirme a senha: " CONFIRMA; echo
    [[ -n "$SENHA_ADMIN" && "$SENHA_ADMIN" == "$CONFIRMA" ]] && break
    echo "As senhas não conferem ou estão vazias. Tente de novo."
  done
  HASH_ADMIN="$(SENHA="$SENHA_ADMIN" "$PROJETO/backend/.venv/bin/python" -c 'import bcrypt, os; print(bcrypt.hashpw(os.environ["SENHA"].encode(), bcrypt.gensalt()).decode())')"
  unset SENHA_ADMIN CONFIRMA
  CHAVE_JWT="$(openssl rand -base64 48 | tr -d '\n=+/')"
  CHAVE_LDAP="$("$PROJETO/backend/.venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  VAPID="$("$PROJETO/backend/.venv/bin/python" "$PROJETO/scripts/gerar-chaves-vapid.py" | grep -E '^(CHAVE_PUBLICA_VAPID|CHAVE_PRIVADA_VAPID|CONTATO_VAPID)=')"
  cat > "$ENV" <<EOF
# Gerado por scripts/instalar.sh em $(date '+%d/%m/%Y %H:%M'). Não versionar. Referência: backend/.env.example
AMBIENTE=$( (( HOMOLOGACAO )) && echo homologacao || echo producao )
CHAVE_SECRETA_JWT=$CHAVE_JWT
URL_BANCO_DADOS=postgresql+psycopg://$BANCO:$SENHA_BANCO@localhost:5432/$BANCO
# Cifra a senha de bind do LDAP e dos servidores SMTP. Para restaurar um backup de outro servidor, use a MESMA chave dele.
CHAVE_CIFRA_LDAP=$CHAVE_LDAP
LOGIN_ADMIN=root
HASH_SENHA_ADMIN='$HASH_ADMIN'
NOME_ADMIN=Administrador
URL_PUBLICA=https://$DOMINIO
$VAPID
EOF
  chown "$USUARIO:$USUARIO" "$ENV"
fi
chmod 600 "$ENV"
# Liga ou desliga o modo homologação no .env (também num .env que já existia)
if (( HOMOLOGACAO )); then
  grep -q '^MODO_HOMOLOGACAO=' "$ENV" && sed -i 's/^MODO_HOMOLOGACAO=.*/MODO_HOMOLOGACAO=true/' "$ENV" || echo 'MODO_HOMOLOGACAO=true' >> "$ENV"
else
  sed -i 's/^MODO_HOMOLOGACAO=.*/MODO_HOMOLOGACAO=false/' "$ENV"
fi

# ---------------------------------------------------------------------------------------------
# 4. Pastas, permissões e sudoers
# ---------------------------------------------------------------------------------------------
echo "==> Pastas e permissões"
ANEXOS="$(grep -E '^ANEXOS_DIRETORIO=' "$ENV" | cut -d= -f2- || true)"
ANEXOS="${ANEXOS:-$PROJETO/dados/anexos}"
install -d -o "$USUARIO" -g "$USUARIO" -m 750 "$ANEXOS" "$PROJETO/dados/backups" "$PROJETO/dados/atualizacao"
# O Nginx (www-data) precisa atravessar os diretórios até o build do Angular.
# o+x permite apenas a travessia: outros usuários não conseguem listar o conteúdo.
d="$PROJETO"
while [[ "$d" != "/" ]]; do chmod o+x "$d"; d="$(dirname "$d")"; done
# O deploy e o sistema reiniciam a API sem senha, e a tela Administração › Versões liga a atualização (só estes comandos)
SYSTEMCTL="$(command -v systemctl)"
cat > /etc/sudoers.d/sgi-spi-restart <<EOF
$USUARIO ALL=(root) NOPASSWD: $SYSTEMCTL restart sgi-spi-api.service, $SYSTEMCTL restart sgi-spi-api, $SYSTEMCTL start --no-block sgi-spi-atualizar.service
EOF
chmod 440 /etc/sudoers.d/sgi-spi-restart
visudo -cf /etc/sudoers.d/sgi-spi-restart >/dev/null

# ---------------------------------------------------------------------------------------------
# 5. Build (testes, migrações e frontend)
# ---------------------------------------------------------------------------------------------
echo "==> Build$( (( SEM_TESTES )) && echo ' (sem testes)' || echo ' e testes') (como $USUARIO)"
if (( SEM_TESTES )); then como_usuario env SGI_SEM_RESTART=1 bash "$PROJETO/scripts/deploy.sh" --sem-testes
else como_usuario env SGI_SEM_RESTART=1 bash "$PROJETO/scripts/deploy.sh"; fi

echo "==> Encerrando processos manuais nas portas 8000/4200 (substituídos pelo systemd e pelo Nginx)"
# O uvicorn manual pode ter sido iniciado com caminho relativo (.venv/bin/uvicorn): casa pelo módulo
pkill -u "$USUARIO" -f "uvicorn app.main:app" || true
pkill -u "$USUARIO" -f "ng serve .*--port 4200" || true
sleep 1

# ---------------------------------------------------------------------------------------------
# 6. Serviços (API e tarefas agendadas)
# ---------------------------------------------------------------------------------------------
echo "==> systemd: sgi-spi-api"
sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" \
    "$PROJETO/systemd/sgi-spi-api.service" > /etc/systemd/system/sgi-spi-api.service
systemctl daemon-reload
systemctl enable sgi-spi-api
systemctl restart sgi-spi-api

echo "==> systemd: sgi-spi-atualizar (atualização pela tela Administração › Versões; só roda quando pedida)"
HOME_USUARIO="$(getent passwd "$USUARIO" | cut -d: -f6)"
sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" -e "s|__HOME__|$HOME_USUARIO|g" \
    "$PROJETO/systemd/sgi-spi-atualizar.service" > /etc/systemd/system/sgi-spi-atualizar.service
systemctl daemon-reload

echo "==> systemd: timers das notificações (despacho a cada 2 min; lembretes às 07:00), da conferência de OBs no SIGEO e dos Chamados (prazos e recorrentes a cada minuto; vigia a cada 5 min) e do ping da Rede (a cada minuto)"
# Em homologação os timers rodam igual: os envios saem simulados e a conferência do SIGEO não consulta nada
# Unidades antigas (antes se chamavam "mensageria"): desativa e remove, para não rodarem em dobro
for antiga in sgi-spi-mensageria-emails sgi-spi-mensageria-lembretes; do
  systemctl disable --now "$antiga.timer" 2>/dev/null || true
  systemctl stop "$antiga.service" 2>/dev/null || true
  rm -f "/etc/systemd/system/$antiga.timer" "/etc/systemd/system/$antiga.service"
done
for unidade in sgi-spi-notificacoes-despachar sgi-spi-notificacoes-lembretes sgi-spi-sigeo-ob sgi-spi-chamados-minuto sgi-spi-chamados-vigia sgi-spi-rede-ping; do
  for tipo in service timer; do
    sed -e "s/__USUARIO__/$USUARIO/g" -e "s|__PROJETO__|$PROJETO|g" \
        "$PROJETO/systemd/$unidade.$tipo" > "/etc/systemd/system/$unidade.$tipo"
  done
done
systemctl daemon-reload
systemctl enable --now sgi-spi-notificacoes-despachar.timer sgi-spi-notificacoes-lembretes.timer sgi-spi-sigeo-ob.timer sgi-spi-chamados-minuto.timer sgi-spi-chamados-vigia.timer sgi-spi-rede-ping.timer

# ---------------------------------------------------------------------------------------------
# 7. Certificado e Nginx
# ---------------------------------------------------------------------------------------------
echo "==> Nginx (porta $PORTA)"
DEFAULT=""
CONFLITOS=$(grep -lE "listen[^;]*\b$PORTA\b[^;]*default_server" /etc/nginx/sites-enabled/* 2>/dev/null | grep -v '/sgi-spi$' || true)
if [[ -n "$CONFLITOS" ]] && (( ! SUBSTITUIR )); then
  # Instalação nova do Ubuntu: o único conflito é o site "default" do pacote, que pode sair sem perguntar
  if [[ "$CONFLITOS" == "/etc/nginx/sites-enabled/default" ]]; then
    echo "    desativando o site default do Nginx (continua em sites-available)"
    rm -f /etc/nginx/sites-enabled/default
    CONFLITOS=""
  else
    echo "ERRO: a porta $PORTA já tem um site padrão ($CONFLITOS)." >&2
    echo "      Acessos por IP iriam para ele. Use --substituir-default ou --porta <outra>." >&2
    exit 1
  fi
fi
[[ -z "$CONFLITOS" ]] && DEFAULT="default_server"
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
CERT="/etc/ssl/certs/$DOMINIO.fullchain.crt"
CHAVE="/etc/ssl/private/$DOMINIO.key"
if [[ ! -f "$CERT" || ! -f "$CHAVE" ]]; then
  echo "    sem certificado para $DOMINIO: gerando um autoassinado (troque pelo oficial nos mesmos caminhos e recarregue o Nginx)"
  # Acesso pelo IP (sem DNS): o certificado precisa declarar o IP, não um nome
  if [[ "$DOMINIO" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then NOME_CERT="IP:$DOMINIO"; else NOME_CERT="DNS:$DOMINIO"; fi
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 -subj "/CN=$DOMINIO" -addext "subjectAltName=$NOME_CERT" \
    -keyout "$CHAVE" -out "$CERT" >/dev/null 2>&1
  chmod 600 "$CHAVE"
fi
sed -e "s/__PORTA__/$PORTA/g" -e "s/ __DEFAULT__/${DEFAULT:+ $DEFAULT}/g" -e "s|__PROJETO__|$PROJETO|g" -e "s/__DOMINIO__/$DOMINIO/g" \
    "$PROJETO/nginx/sgi-spi.conf" > /etc/nginx/sites-available/sgi-spi
ln -sfn /etc/nginx/sites-available/sgi-spi /etc/nginx/sites-enabled/sgi-spi
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# ---------------------------------------------------------------------------------------------
# 8. Verificação
# ---------------------------------------------------------------------------------------------
echo "==> Verificação"
sleep 2
curl -fsS "http://127.0.0.1:$PORTA/api/saude" && echo
curl -fsS -o /dev/null "http://127.0.0.1:$PORTA/" && echo "frontend OK"
curl -fsS -o /dev/null --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/api/saude" --cacert "$CERT" && echo "HTTPS OK" \
  || echo "AVISO: a conferência do HTTPS falhou (veja o certificado em $CERT)."
echo "Aplicação: https://$DOMINIO/ (os demais endereços redirecionam para ele). Login: root com a senha informada na instalação."
(( HOMOLOGACAO )) && echo "HOMOLOGAÇÃO: e-mails e pop-ups são simulados; SIGEO, AD e aniversários não rodam."
if (( HOMOLOGACAO )); then
  cat <<AVISO
APROVAR VERSÕES (Administração › Versões): a homologação envia a tag da versão aprovada ao GitHub e precisa de uma chave com escrita:
  1. como $USUARIO: ssh-keygen -t ed25519 -f ~/.ssh/sgi-spi-deploy -N ""   (e mostre a pública: cat ~/.ssh/sgi-spi-deploy.pub)
  2. no GitHub: repositório sgi-spi-v2 › Settings › Deploy keys › Add deploy key, cole a chave e marque "Allow write access"
  3. em ~/.ssh/config:  Host github.com  /  IdentityFile ~/.ssh/sgi-spi-deploy
  4. git -C $PROJETO remote set-url --push origin git@github.com:joseeduardosm/sgi-spi-v2.git && git -C $PROJETO push --dry-run origin HEAD
A produção só baixa (HTTPS público), não precisa de chave.
AVISO
fi
exit 0
