# contratos-spi

Sistema de gestão de contratos da **Secretaria de Parcerias em Investimentos (SPI)**, Governo do Estado de São Paulo.

- **Backend:** Python 3.12 + FastAPI (`backend/`)
- **Frontend:** Angular 22 + Bootstrap 5.3 (`frontend/`)
- **Servidor web:** Nginx serve o build do Angular e encaminha `/api/*` para o FastAPI
- **Serviço:** FastAPI/uvicorn gerenciado pelo systemd (`contratos-spi-api`)

Etapa atual: estrutura do projeto, identidade visual e autenticação. Os módulos de negócio ainda não foram implementados.

```text
Usuário → Nginx ─┬─ /       → Angular (frontend/dist/contratos-spi/browser)
                 └─ /api/*  → FastAPI (127.0.0.1:8000, systemd contratos-spi-api)
```

## Estrutura

O projeto roda no próprio diretório **`/home/administrador/projeto`**. Não existe cópia em `/var/www`.

```text
/home/administrador/projeto/
├── backend/            FastAPI
│   ├── app/{api,core,models,schemas,services}/  main.py
│   ├── alembic/        migrações do banco
│   ├── tests/          pytest
│   ├── requirements.txt / requirements-dev.txt
│   ├── .env            configuração local (não versionar)
│   └── .env.example    modelo do .env
├── frontend/           Angular
│   └── src/app/{core,shared,features}/  app.routes.ts
├── nginx/contratos-spi.conf        modelo do site Nginx
├── systemd/contratos-spi-api.service  modelo da unidade systemd
├── scripts/            instalar.sh, deploy.sh, gerar-hash-senha.py
├── docs/               documentação da API (obrigatória, ver docs/README.md)
├── dados/anexos/       PDFs enviados e gerados (ANEXOS_DIRETORIO; incluir no backup, não versionar)
└── logs/               saída dos processos provisórios (não versionar)
```

## Requisitos

Ubuntu 24.04 com:
- Python 3.12 + `python3-venv`;
- Node.js 22 + npm;
- PostgreSQL 16 (banco e usuário próprios, informados em `URL_BANCO_DADOS`);
- Nginx;
- sudo.

## Instalação no servidor

1. Configure o backend:

   ```bash
   cp backend/.env.example backend/.env
   chmod 600 backend/.env
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # → CHAVE_SECRETA_JWT
   python3 -m venv backend/.venv && backend/.venv/bin/pip install bcrypt cryptography
   backend/.venv/bin/python scripts/gerar-hash-senha.py           # → HASH_SENHA_ADMIN (entre aspas simples)
   backend/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # → CHAVE_CIFRA_LDAP
   # URL_BANCO_DADOS=postgresql+psycopg://usuario:senha@localhost:5432/banco
   ```

2. Execute a instalação (idempotente):

   ```bash
   sudo scripts/instalar.sh                        # porta 80 (interrompe se já houver site padrão nela)
   sudo scripts/instalar.sh --substituir-default   # porta 80, desativa o site padrão atual (fica em sites-available)
   sudo scripts/instalar.sh --porta 8081           # outra porta
   ```

   O script:
   - libera apenas a travessia (`chmod o+x`) de `/home/administrador` e `projeto`, para o Nginx ler o build do Angular;
   - cria o virtualenv, instala as dependências, roda os testes, aplica as migrações do banco e compila o Angular (`scripts/deploy.sh`);
   - encerra processos manuais (uvicorn na 8000, `ng serve` na 4200), instala e inicia `contratos-spi-api.service`;
   - gera `/etc/nginx/sites-available/contratos-spi` a partir de `nginx/contratos-spi.conf`, ativa o site, valida (`nginx -t`) e recarrega o Nginx;
   - verifica `GET /api/saude` pelo Nginx.

3. Acesse `http://<servidor>/` e entre com o administrador configurado.

## Atualização (deploy)

Depois de alterar o código:

```bash
scripts/deploy.sh                # dependências + testes + migrações + build do Angular + restart da API
scripts/deploy.sh --sem-testes
```

Alterações em `nginx/contratos-spi.conf` ou `systemd/*.service` exigem rodar `sudo scripts/instalar.sh` novamente.

## Desenvolvimento

Os testes do backend usam SQLite temporário e um Active Directory simulado (ldap3 `MOCK_SYNC`). Não dependem do PostgreSQL nem do AD real.

Backend com recarga automática (porta de desenvolvimento diferente da 8000 do serviço, se ele estiver ativo):

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
.venv/bin/pytest -q
```

Frontend com recarga automática (`proxy.conf.json` encaminha `/api` para `127.0.0.1:8000`):

```bash
cd frontend
npx ng serve --host 127.0.0.1 --port 4201
npx ng test --watch=false
npx ng build              # produção → dist/contratos-spi/browser (servido pelo Nginx)
```

## Configuração (`backend/.env`)

| Variável | Descrição |
|---|---|
| `CHAVE_SECRETA_JWT` | Chave de assinatura dos tokens (mín. 32 caracteres). Trocar invalida todas as sessões |
| `ALGORITMO_JWT` | Padrão `HS256` |
| `MINUTOS_EXPIRACAO_TOKEN` | Validade do token. Padrão 60 |
| `URL_BANCO_DADOS` | Conexão PostgreSQL (`postgresql+psycopg://usuario:senha@host:5432/banco`) |
| `CHAVE_CIFRA_LDAP` | Chave Fernet que cifra a senha de bind LDAP. Trocar exige informar as senhas de novo |
| `INTERVALO_SINCRONIZACAO_LDAP_MINUTOS` | Sincronização automática do diretório ativo. Padrão 15; `0` desativa |
| `TEMPO_LIMITE_LDAP_SEGUNDOS` | Tempo limite de conexão LDAP. Padrão 5 |
| `LOGIN_ADMIN` | Conta administrativa principal, SuperRoot local (`root` no desenvolvimento) |
| `HASH_SENHA_ADMIN` | Hash bcrypt da senha, reaplicado à conta a cada inicialização. Nunca grave a senha em texto puro |
| `NOME_ADMIN` | Nome exibido, aplicado se a conta ainda não tiver nome |
| `ORIGENS_CORS` | Lista JSON. Só é necessária se o frontend for servido por outra origem |
| `ANEXOS_DIRETORIO` | Onde os PDFs são gravados. Padrão `/home/administrador/projeto/dados/anexos`. O usuário do serviço precisa de permissão de escrita |
| `ANEXOS_TAMANHO_MAXIMO_MB` | Tamanho máximo de cada PDF. Padrão 20. Mantenha o `client_max_body_size` do Nginx um pouco acima deste valor |

## Manutenção

| Tarefa | Comando |
|---|---|
| Status da API | `systemctl status contratos-spi-api` |
| Logs da API | `journalctl -u contratos-spi-api -f` |
| Reiniciar a API | `sudo systemctl restart contratos-spi-api` |
| Saúde | `curl http://127.0.0.1/api/saude` |
| Validar/recarregar o Nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| Logs do Nginx | `/var/log/nginx/access.log`, `/var/log/nginx/error.log` |
| Trocar a senha do root | `scripts/gerar-hash-senha.py` → `.env` → restart da API |
| Aplicar migrações do banco | `cd backend && .venv/bin/alembic upgrade head` |
| Criar migração após alterar modelos | `cd backend && .venv/bin/alembic revision --autogenerate -m "descrição"` (revise o arquivo gerado) |
| Consultar auditoria | `psql … -c "select ocorrido_em, autor, acao, alvo, detalhes from auditoria order by ocorrido_em desc limit 50"` |
| Backup dos anexos | Copie `dados/anexos/` junto com o dump do banco: a tabela `anexos` guarda só os metadados e o SHA-256 de cada arquivo |

## Documentação da API

- Textual: [docs/](docs/README.md)
- Automática: `/api/documentacao` (Swagger), `/api/redoc`, `/api/openapi.json`

**Regra:** nenhuma alteração de API está concluída sem a documentação em `docs/` atualizada na mesma implementação. Ver [docs/README.md](docs/README.md).

## Barra lateral e novos módulos

As páginas autenticadas usam o layout `LayoutAutenticadoComponent` (`frontend/src/app/shared/layout/`), com barra lateral no padrão do SGI SPI:
- recolhida em ícones, expande ao passar o mouse;
- botão de fixar, com a preferência salva no navegador;
- grupos com submenu;
- gaveta com botão hambúrguer no celular.

Os itens vêm de `frontend/src/app/core/navegacao/navegacao.ts`. Para publicar um módulo:

1. Crie a feature em `frontend/src/app/features/<modulo>/` e a rota como filha de `''` em `app.routes.ts`, com `title: '<Nome> | Contratos SPI'`. O título aparece na topbar.
2. Acrescente o item em `NAVIGATION`, normalmente como filho do grupo `modulos`:
   `{ id: 'contratos', rotulo: 'Contratos', rota: '/contratos', acl: 'contratos' }`.
   `acl` esconde o item de quem não tem acesso ao recurso; `papeis` (ex.: `['SuperRoot']`) restringe por papel. A API continua validando as permissões.
3. Se o módulo tiver endpoints, documente-os em `docs/` (regra obrigatória).

## Identidade visual

Reproduz o portal hospedado em `10.23.3.190`: Bootstrap 5.3, Arial, fundo `#f6f7f8`, vermelho institucional `#c82331`, cabeçalho com brasão e filete `#ee2c35`. Os tokens e componentes reutilizáveis (`.portal-card`, `.eyebrow`, `.section-mark`, `.action-button`, etc.) estão em `frontend/src/styles.scss`. Use-os nas novas telas.
