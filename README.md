# SGI SPI – Sistema de Gestão Integrada

Sistema de Gestão Integrada da **Secretaria de Parcerias em Investimentos (SPI)**, Governo do Estado de São Paulo (antes chamado contratos-spi): contratos, RH, notificações e administração.

- **Backend:** Python 3.12 + FastAPI (`backend/`)
- **Frontend:** Angular 22 + Bootstrap 5.3 (`frontend/`)
- **Servidor web:** Nginx serve o build do Angular e encaminha `/api/*` para o FastAPI
- **Serviço:** FastAPI/uvicorn gerenciado pelo systemd (`sgi-spi-api`)

Etapa atual: estrutura do projeto, identidade visual e autenticação. Os módulos de negócio ainda não foram implementados.

```text
Usuário → Nginx ─┬─ /       → Angular (frontend/dist/sgi-spi/browser)
                 └─ /api/*  → FastAPI (127.0.0.1:8000, systemd sgi-spi-api)
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
├── nginx/sgi-spi.conf        modelo do site Nginx
├── systemd/sgi-spi-api.service  modelo da unidade systemd
├── scripts/            instalar.sh, deploy.sh, gerar-hash-senha.py
├── docs/               documentação da API (obrigatória, ver docs/README.md)
├── dados/anexos/       PDFs enviados e gerados (ANEXOS_DIRETORIO; incluir no backup, não versionar)
└── logs/               saída dos processos provisórios (não versionar)
```

## Requisitos

Ubuntu 24.04 com acesso à internet (pacotes do sistema, NodeSource, PyPI e npm) e sudo. **O resto o `scripts/instalar.sh` instala**: Python 3 + venv, Node.js 22, PostgreSQL, Nginx, curl, OpenSSL e OpenSSH. Numa máquina sem internet, prepare esses pacotes à mão e use `--sem-pacotes`.

## Instalação no servidor (do zero ou para atualizar)

1. Copie o projeto para a pasta do usuário que vai rodar o sistema (ex.: `/home/administrador/projeto`).
2. (Opcional) Instale o certificado HTTPS do domínio. Sem ele, o script gera um **autoassinado** (o navegador avisa até trocar pelo oficial nos mesmos caminhos):
   - **Chave privada:** `/etc/ssl/private/DOMINIO.key`, só para o root (`chmod 600`), gerada no próprio servidor com o pedido (`openssl req -new … -keyout`); o `.csr` vai à equipe de servidores (SPI-AD01-CA).
   - **Certificado com a cadeia:** `/etc/ssl/certs/DOMINIO.fullchain.crt`, o do site seguido do da CA, com fim de linha Unix:

     ```bash
     { tr -d '\r' < DOMINIO.crt; echo; tr -d '\r' < SPI-AD01-CA.crt; } | sed '/^$/d' | sudo tee /etc/ssl/certs/DOMINIO.fullchain.crt >/dev/null
     ```

3. Rode a instalação (idempotente) a partir do usuário do projeto:

   ```bash
   sudo scripts/instalar.sh --dominio portal.spi.sp.gov.br                                  # produção
   sudo scripts/instalar.sh --dominio homologacao.spi.sp.gov.br --homologacao --sem-testes  # homologação
   ```

   Opções: `--homologacao` (envios simulados, ver abaixo), `--sem-testes` (build sem rodar os testes), `--sem-pacotes`, `--porta N` (HTTP; o HTTPS fica na 443) e `--substituir-default` (desativa outro site padrão do Nginx na porta; o `default` do Ubuntu sai sozinho).

   O script:
   - instala os pacotes do sistema e o Node 22, e põe o servidor no fuso de São Paulo;
   - cria o virtualenv e instala as dependências do backend;
   - **na primeira vez** (sem `backend/.env`): cria o usuário e o banco `sgi_spi` no PostgreSQL com senha aleatória, **pede a senha do SuperRoot** (login `root`; só o hash bcrypt é gravado) e gera o `backend/.env` com a chave do JWT, a chave de cifra do LDAP/SMTP, as chaves VAPID e `URL_PUBLICA=https://DOMINIO`. Um `.env` que já existe nunca é sobrescrito;
   - cria a pasta dos anexos (`dados/anexos`) e a dos backups (`dados/backups`), libera só a travessia (`chmod o+x`) dos diretórios até o projeto para o Nginx e grava `/etc/sudoers.d/sgi-spi-restart` (o usuário reinicia a API sem senha, só esse comando);
   - roda `scripts/deploy.sh` (testes, `alembic upgrade head` e build do Angular);
   - instala e inicia `sgi-spi-api.service` e os timers das notificações e do SIGEO (remove as unidades antigas "mensageria");
   - gera o site do Nginx a partir de `nginx/sgi-spi.conf` (HTTPS em DOMINIO; os demais acessos redirecionam para ele) e confere `GET /api/saude` em HTTP e HTTPS.

4. Acesse `https://DOMINIO/` e entre com `root` e a senha informada.

### Homologação (`--homologacao`)

Grava `MODO_HOMOLOGACAO=true` no `.env` (e exige um `--dominio` diferente do de produção):
- **e-mails e pop-ups do navegador são simulados**: nada sai do servidor, mas o envio fica registrado como feito, com a nota "Simulado (homologação)";
- a conferência do SIGEO, a sincronização com o AD e o parabéns de aniversário não rodam;
- a tela mostra a faixa **HOMOLOGAÇÃO** no topo.

Ao restaurar lá um backup de produção, use no `.env` a mesma `CHAVE_CIFRA_LDAP` de produção (senão as senhas do LDAP e do SMTP não abrem). Abrir chamado no GLPI e publicar no BookStack **não** são simulados: confira essas integrações antes de testar.

## Atualização (deploy)

Depois de alterar o código:

```bash
scripts/deploy.sh                # dependências + testes + migrações + build do Angular + restart da API
scripts/deploy.sh --sem-testes
```

Alterações em `nginx/sgi-spi.conf` ou `systemd/*.service` exigem rodar `sudo scripts/instalar.sh` novamente.

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
npx ng build              # produção → dist/sgi-spi/browser (servido pelo Nginx)
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
| `HORA_PARABENS_ANIVERSARIO` | Hora (0 a 23) do parabéns automático de aniversário. Padrão 8; `-1` desativa |
| `TEMPO_LIMITE_LDAP_SEGUNDOS` | Tempo limite de conexão LDAP. Padrão 5 |
| `LOGIN_ADMIN` | Conta administrativa principal, SuperRoot local (`root` no desenvolvimento) |
| `HASH_SENHA_ADMIN` | Hash bcrypt da senha, reaplicado à conta a cada inicialização. Nunca grave a senha em texto puro |
| `NOME_ADMIN` | Nome exibido, aplicado se a conta ainda não tiver nome |
| `ORIGENS_CORS` | Lista JSON. Só é necessária se o frontend for servido por outra origem |
| `ANEXOS_DIRETORIO` | Onde os PDFs são gravados. Padrão `/home/administrador/projeto/dados/anexos`. O usuário do serviço precisa de permissão de escrita |
| `URL_PUBLICA` | Endereço usado nos links dos e-mails (ex.: link direto para a etapa da competência). Produção: `https://portal.spi.sp.gov.br` |
| `CHAVE_PUBLICA_VAPID`, `CHAVE_PRIVADA_VAPID`, `CONTATO_VAPID` | Notificações do navegador (Web Push). Gere o par com `backend/.venv/bin/python scripts/gerar-chaves-vapid.py` e cole as três linhas; a chave privada é segredo. Sem elas, o canal Navegador fica indisponível na tela de Preferências |
| `NOTIFICACOES_MESES_NA_CAIXA` | Notificações cientes ou encerradas há mais de N meses (padrão 6) saem da caixa e da busca; continuam no banco |
| `NOTIFICACOES_DESPACHO` | `thread` (padrão), `sincrono` ou `desligado`: como as notificações saem depois do commit (os testes usam `desligado`) |
| `ANEXOS_TAMANHO_MAXIMO_MB` | Tamanho máximo de cada PDF. Padrão 20. Mantenha o `client_max_body_size` do Nginx um pouco acima deste valor |

## Manutenção

| Tarefa | Comando |
|---|---|
| Status da API | `systemctl status sgi-spi-api` |
| Logs da API | `journalctl -u sgi-spi-api -f` |
| Reiniciar a API | `sudo systemctl restart sgi-spi-api` |
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

1. Crie a feature em `frontend/src/app/features/<modulo>/` e a rota como filha de `''` em `app.routes.ts`, com `title: '<Nome> | SGI SPI'`. O título aparece na topbar.
2. Acrescente o item em `NAVIGATION`, normalmente como filho do grupo `modulos`:
   `{ id: 'contratos', rotulo: 'Contratos', rota: '/contratos', acl: 'contratos' }`.
   `acl` esconde o item de quem não tem acesso ao recurso; `papeis` (ex.: `['SuperRoot']`) restringe por papel. A API continua validando as permissões.
3. Se o módulo tiver endpoints, documente-os em `docs/` (regra obrigatória).

## Identidade visual

Reproduz o portal hospedado em `10.23.3.190`: Bootstrap 5.3, Arial, fundo `#f6f7f8`, vermelho institucional `#c82331`, cabeçalho com brasão e filete `#ee2c35`. Os tokens e componentes reutilizáveis (`.portal-card`, `.eyebrow`, `.section-mark`, `.action-button`, etc.) estão em `frontend/src/styles.scss`. Use-os nas novas telas.
