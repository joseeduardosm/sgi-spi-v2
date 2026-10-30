# Backup geral (`/api/admin/backups`)

Tag no OpenAPI: **Backup geral**. Implementação:
- `backend/app/api/routes/backup.py`, `backend/app/services/servico_backup.py` e `backend/app/schemas/backup.py`;
- tela: Administração › Backup geral (`/admin/backup`, só SuperRoot);
- pasta dos backups: `BACKUPS_DIRETORIO` (padrão `dados/backups`, criada pelo `scripts/instalar.sh`).

Um `.zip` com **o banco inteiro e todos os anexos**, para levar o sistema de um servidor a outro (ex.: produção → homologação) ou guardar um ponto de restauração:
- `manifesto.json`: `sistema` ("SGI SPI"), `gerado_em`, `servidor`, `ambiente`, `homologacao`, `versao`, `revisao_banco` (Alembic), `gerado_por`, `motivo`, `anexos`, `bytes_anexos`;
- `banco.dump`: `pg_dump --format=custom --no-owner --no-acl` (configurações, ACLs, servidores SMTP e LDAP, integrações, contratos, RH… tudo o que está no banco);
- `anexos/…`: os arquivos de `ANEXOS_DIRETORIO`, com o mesmo caminho (guardados sem recomprimir).

Gerar e importar demoram mais que uma requisição: as duas operações rodam **em segundo plano** e gravam o andamento em `dados/backups/andamento.json`; a tela consulta `GET /api/admin/backups` a cada 3 s e mostra um **modal de andamento** (trilha de etapas, barra com `percentual` e a `mensagem` do que está sendo feito). Uma operação por vez.

Etapas (`andamento.etapa`):
- gerar: `banco` (cópia e compactação do banco, 0–30%), `anexos` (um a um, pelo tamanho, 30–95%; a mensagem diz "N de M (x MB de y GB)"), `finalizar`;
- importar: `guardar` (backup do estado atual, 0–35%), `banco` (35–60%), `anexos` (60–90%), `migracoes`, `reiniciar`.

No erro, `etapa` fica na etapa em que parou. O andamento é atualizado no máximo uma vez por segundo.

## Acesso

Todas as rotas: **SuperRoot** (`403` para os demais). Auditoria: `sistema.backup.gerar` e `sistema.backup.importar` (esta gravada no banco já restaurado, com o nome do backup automático do estado anterior).

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/admin/backups` | `PainelBackup`: `backups[]` (`nome`, `tamanho`, `criado_em`, `antes_da_importacao`) e `andamento` (`operacao` = `gerar`/`importar`, `situacao` = `em_andamento`/`concluido`/`erro`/`reiniciando`, `mensagem`, `arquivo`, `etapa`, `percentual` de 0 a 100, `atualizado_em`) |
| `POST` | `/api/admin/backups` | `202`: começa a gerar o backup. `400` se já houver operação em andamento |
| `GET` | `/api/admin/backups/arquivo/{nome}` | Download do `.zip` (`application/zip`) com o token no cabeçalho. `404` para nome inexistente ou fora da pasta |
| `POST` | `/api/admin/backups/arquivo/{nome}/link` | `LinkDownloadBackup`: `url` (`/api/admin/backups/arquivo/{nome}/baixar?chave=…`) e `expira_em`. A chave é um JWT de tipo `download_backup`, vale **5 minutos** e só para este arquivo (não serve como token de acesso). `404` para nome inexistente |
| `GET` | `/api/admin/backups/arquivo/{nome}/baixar?chave=…` | Download **sem cabeçalho de autenticação**, para o navegador abrir direto: o arquivo aparece na barra de downloads do navegador, com o progresso dele, sem passar pela memória da página. Exige que quem pediu o link continue SuperRoot e ativo. `404` com chave inválida, vencida ou de outro arquivo |
| `POST` | `/api/admin/backups/importar` | `multipart`: `arquivo` (.zip) e `confirmacao` = `SUBSTITUIR`. `202` com o manifesto do arquivo. `400`: sem a confirmação, arquivo que não é um backup do SGI SPI, caminhos inválidos, **backup de versão mais nova** que o sistema, ou operação em andamento |

## Importação (substitui tudo)

Depois de conferir o arquivo, em segundo plano:
1. gera um **backup automático do estado atual** (`…-antes-da-importacao.zip`, aparece na lista);
2. encerra as outras conexões ao banco e roda `pg_restore --clean --if-exists --single-transaction --exit-on-error`: **se falhar, o banco fica como estava**;
3. troca a pasta de anexos pelos do arquivo (extrai ao lado e troca no fim);
4. aplica as migrações (`alembic upgrade head`): um backup de versão anterior sobe para a atual;
5. reinicia a API (`sudo -n systemctl restart sgi-spi-api.service`, liberado pelo sudoers do instalador); `andamento.situacao = reiniciando`. A tela espera `GET /api/saude` voltar e recarrega (é preciso entrar de novo).

As senhas do LDAP e dos servidores SMTP vão **cifradas com `CHAVE_CIFRA_LDAP`**: no servidor de destino, use no `.env` a mesma chave do servidor de origem. Em homologação (`MODO_HOMOLOGACAO=true`), os e-mails continuam simulados mesmo com os servidores SMTP de produção.

## Nginx

`nginx/sgi-spi.conf` libera arquivo grande só em `/api/admin/backups/importar` (`client_max_body_size 10g`, sem buffer no Nginx, 900 s) e serve o download sem buffer. Num servidor já instalado, rode `sudo scripts/instalar.sh --dominio …` de novo para aplicar (sem isso, o envio continua limitado a 30 MB).
