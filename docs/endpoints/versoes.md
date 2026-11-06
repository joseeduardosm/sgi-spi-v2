# Versões do sistema (`/api/admin/versoes`)

Tag no OpenAPI: **Versões do sistema**. Implementação:
- `backend/app/api/routes/versoes.py`, `backend/app/services/servico_versoes.py` e `backend/app/schemas/versoes.py`;
- execução: `scripts/atualizar-versao.py`, rodado pela unidade `systemd/sgi-spi-atualizar.service` (fora da API);
- tela: Administração › Versões do sistema (`/admin/versoes`, só SuperRoot);
- pasta: `ATUALIZACAO_DIRETORIO` (padrão `dados/atualizacao`): `pedido.json`, `andamento.json` e `ultima-atualizacao.log`.

## Como funciona (decisões do usuário)

1. Desenvolvimento faz push no ramo acompanhado (`ATUALIZACAO_RAMO`, padrão `estado-atual-servidor`).
2. **Homologação** (`MODO_HOMOLOGACAO=true`): "Atualizar a homologação" leva o servidor ao último commit desse ramo. Depois de testar, "Aprovar esta
   versão" cria a **tag anotada** `vAAAA.MM.DD` (`.2`, `.3`… se já houver no dia) no commit em execução, com quem aprovou, quando e as novidades do
   `CHANGELOG.md`, e a envia ao GitHub. Exige a chave de deploy **com escrita** na homologação (o `instalar.sh --homologacao` explica como).
3. **Produção**: lista só as tags aprovadas **mais novas** que a versão em execução, com as novidades do CHANGELOG, e instala a escolhida.

A versão em execução vem do Git (`git describe --tags --always`, lido na subida da API) e aparece em `GET /api/saude` (`versao`).

## Atualização (fora da API)

A API confere o pedido, grava `pedido.json` e liga a unidade (`sudo -n systemctl start --no-block sgi-spi-atualizar.service`, liberado no sudoers do
instalador). A unidade roda `scripts/atualizar-versao.py`, que grava o andamento (`etapa`, `percentual`, `mensagem`) a cada passo:

| Etapa | O que faz |
|---|---|
| `conferir` | Sem alteração local; o código não mudou desde o pedido; a versão existe |
| `backup` | Backup geral completo (`…-antes-da-atualizacao.zip`, aparece em Backup geral) |
| `codigo` | `git checkout --detach <versão>` |
| `dependencias` | `pip install -r requirements.txt` e `npm ci` |
| `migracoes` | `alembic upgrade head` |
| `build` | `ng build` numa pasta ao lado, trocada de uma vez com `frontend/dist/sgi-spi` (o site continua no ar enquanto compila) |
| `reiniciar` | Reinicia a API (`situacao = reiniciando`) e espera `GET /api/saude` responder com a versão nova (até 90 s) |

**Volta automática** (falha a partir de `codigo`): código anterior, dependências, banco restaurado do backup da etapa `backup` (só se as migrações já
tinham rodado; os anexos não mudam numa atualização), build e reinício. Termina com `situacao = erro`, `voltou = true` e a mensagem da falha. Se a
própria volta falhar, `voltou = false` e a mensagem indica o backup a restaurar em Backup geral. A saída dos comandos fica no log, mostrado na tela.

Uma operação por vez: atualização, backup e importação de backup se bloqueiam. Alteração local não commitada em arquivo versionado bloqueia
atualizar e aprovar (a atualização passaria por cima dela).

## Acesso e auditoria

Todas as rotas: **SuperRoot** (`403` para os demais). Auditoria: `sistema.versao.pedir` (pedido), `sistema.versao.atualizar` (resultado, gravado pelo
script: `concluido`, `erro`, `erro_com_volta`, `erro_sem_volta`) e `sistema.versao.aprovar` (a tag criada).

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/admin/versoes` | `PainelVersoes`: `homologacao`, `versao` (em execução), `versao_no_disco`, `commit`, `arvore_limpa`, `ramo`, `aprovada` (homologação: a tag da versão em execução, se aprovada), `commits_novos[]` (homologação: `commit`, `titulo`, `autor`, `data`), `versoes[]` (produção: `alvo`, `aprovada_por`, `aprovada_em`, `mensagem`, `novidades`, `commits[]`), `andamento` (`operacao`, `situacao`, `mensagem`, `etapa`, `percentual`, `de`, `para`, `voltou`, `atualizado_em`) e `log` (final do log, quando deu erro). Não vai ao GitHub |
| `POST` | `/api/admin/versoes/buscar` | `git fetch --tags` e devolve o painel. `400` se o GitHub não responder |
| `POST` | `/api/admin/versoes/atualizar` | `{alvo, confirmacao: "ATUALIZAR"}` → `202` com o painel. Produção: `alvo` = tag aprovada mais nova; homologação: `alvo` = o ramo acompanhado. `400`: sem a confirmação, alvo inválido, já no último commit, alteração local, outra operação em andamento ou unidade/sudoers não instalados (rode o `scripts/instalar.sh` uma vez) |
| `POST` | `/api/admin/versoes/aprovar` | `201` com `{tag}`. Só na homologação, sem alteração local, com o commit já no GitHub e ainda não aprovado. `400` nos demais casos ou se o push da tag for recusado (chave sem escrita) |

## Instalação

O `scripts/instalar.sh` instala a unidade `sgi-spi-atualizar.service`, acrescenta ao sudoers `systemctl start --no-block sgi-spi-atualizar.service` e cria
`dados/atualizacao`. Num servidor já instalado, rode-o de novo uma vez para ganhar a atualização pela tela.
