# Navegação: busca global, favoritos do menu e colunas das listagens (`/api/busca`, `/api/favoritos`, `/api/preferencias/colunas`)

Tags no OpenAPI: **Busca global**, **Favoritos do menu** e **Preferências de colunas**. Implementação:
- `backend/app/api/routes/busca.py` e `backend/app/services/servico_busca.py`;
- `backend/app/api/routes/favoritos.py`, `backend/app/models/favorito_menu.py` (tabela `usuarios_favoritos`, migração `c9e3a7f1b5d8`);
- o anterior/próximo do contrato fica em `GET /api/contratos/{contrato_id}/vizinhos` (ver [contratos-cadastro.md](contratos-cadastro.md)).

Inspirado na navegação do GLPI: caixa de busca no topo (atalho **Ctrl+K** ou **/**), favoritos e recentes no menu lateral e navegação ‹ › entre contratos da lista.

## `GET /api/busca`

Procura em vários módulos ao mesmo tempo.

- **Autorização:** Bearer (qualquer usuário logado). Cada módulo só aparece se o usuário tem ao menos LEITURA no recurso de ACL dele.
- **Parâmetro:** `q` (até 100 caracteres). Com menos de 2 caracteres, devolve lista vazia.
- **Resposta `200`:** `{"itens": [ResultadoBusca]}`, com até 5 resultados por módulo, agrupáveis por `tipo`.

| Campo | Descrição |
|---|---|
| `tipo` | `contrato`, `empresa`, `contratacao`, `tarefa`, `pessoa` ou `setor` |
| `id` | Identificador do registro (texto) |
| `titulo`, `subtitulo` | Texto da linha (ex.: "Contrato 012/2026 · LIMPEZA SEDE" e a razão social) |
| `rota` | Rota do Angular que abre o registro (pessoas: `/ramais?q=<nome>`) |

| Tipo | Onde procura | Quem vê |
|---|---|---|
| `contrato` | número, apelido, empresa e objeto (mesma busca da carteira) | ACL `contratos` ≥ LEITURA |
| `empresa` | razão social, nome fantasia, CNPJ, endereço e nome dos prepostos | ACL `contratos` ≥ LEITURA |
| `contratacao` | nome e processo | ACL `contratacoes` ≥ LEITURA, e só os documentos que a pessoa enxerga (criador, membro ou administração) |
| `tarefa` | título e número | só as tarefas em que o usuário é criador, responsável ou participante |
| `pessoa` | diretório de ramais (nome, cargo, setor, ramal, e-mail…) | todo usuário logado |
| `setor` | nome | ACL `setores` ≥ LEITURA |

Cada módulo é independente: se um falhar, os outros continuam (a falha vai para o log `sgi_spi.busca`). As telas do menu também entram na busca, mas isso é feito no próprio Angular, a partir do menu que o usuário já enxerga.

## `GET /api/favoritos`

Telas que o usuário fixou, na ordem de exibição: `{"itens": [{"rota", "rotulo"}]}`. Cada usuário vê só os próprios. **Autorização:** Bearer.

## `PUT /api/favoritos`

Substitui a lista inteira, na ordem enviada.

- **Corpo:** `{"itens": [{"rota": "/contratos", "rotulo": "Contratos"}]}`. Máximo de **20** itens. `rota` precisa ser interna (começar por `/`, não por `//` nem conter `://`); `rotulo` até 120 caracteres. Rotas repetidas contam uma vez.
- **Resposta `200`:** a lista gravada. **Erros:** `401`; `422` (`validacao`) para rota externa, rótulo vazio ou mais de 20.

## `GET /api/preferencias/colunas/{tela}`

Colunas que o usuário escolheu mostrar na listagem da tela (como as preferências de exibição do GLPI). `tela` é o identificador escolhido pelo módulo (minúsculas, números, `_`, `.` e `-`; até 60), por exemplo `patrimonio.bens`.

- **Autorização:** Bearer. Cada usuário lê e grava só as próprias. Implementação: `backend/app/api/routes/preferencias.py`, `backend/app/models/preferencia_colunas.py` (tabela `usuarios_preferencias_colunas`, migrações `554e409aefd2` e `c3badbe90657`, esta com a visão global: `usuario_id` nulo).
- **Resposta `200`:** `{"tela": "patrimonio.bens", "colunas": ["chapa", "numero_serie", ...], "padrao_global": [...]}`. `colunas` (visão pessoal) **nulo** = a pessoa nunca escolheu; `padrao_global` é a **visão global** da tela, usada por quem não tem visão pessoal (nulo = vale o padrão da própria tela). A tela mostra: pessoal, senão global, senão o padrão.

## `PUT /api/preferencias/colunas/{tela}`

Substitui a lista inteira, na ordem de exibição.

- **Parâmetro:** `visao` = `pessoal` (padrão) ou `global`; gravar a global exige **SuperRoot** (`403 acesso_negado` para os demais).
- **Corpo:** `{"colunas": ["chapa", "numero_serie", "descricao"]}`: de 1 a 80 ids (minúsculas, números e `_`, até 60 caracteres), sem repetir (a repetição conta uma vez). O servidor não confere se a tela conhece o id: a tela ignora o que não existir mais.
- **Resposta `200`:** a lista gravada. **Erros:** `401`; `422` (`validacao`) para lista vazia, mais de 80 ids ou id inválido.

## `DELETE /api/preferencias/colunas/{tela}`

Apaga a visão pessoal (padrão) ou, com `visao=global`, a global (só SuperRoot): volta a valer a seguinte (global, depois o padrão da tela). **Resposta `204`**, inclusive quando não havia escolha. **Erros:** `401`; `403` na global sem ser SuperRoot.

## No Angular

- Busca: caixa no topo do layout autenticado (`shared/componentes/busca-global`), com atalho `/`, setas, Enter e Esc.
- **Paleta de comandos** (`shared/componentes/paleta-comandos`): **Ctrl/Cmd+K** abre (e fecha) um modal central. Vazio, mostra as **Ações**, os **Favoritos** e os **Recentes**; digitando, as ações que combinam, as telas do menu (já filtradas por papel e ACL) e os resultados de `GET /api/busca`. Setas escolhem, Enter executa, Esc fecha só a paleta. Os comandos ficam em `paleta-comandos.registro.ts` (rótulo, palavras, ACL e rota ou ação): nova tarefa, minhas tarefas e atividades, reservar espaço, novo contrato e nova empresa (MODIFICACAO em `contratos`), abrir chamado, sugerir melhoria, nova mensagem (`/mensagens?nova=1`) e alternar tema. Só frontend, sem endpoint novo.
- Favoritos: estrela ao lado do título da página e seção "Favoritos" na barra lateral. A lista fica também no navegador (`localStorage`, por usuário), para aparecer na hora; depois do login, a da conta prevalece.
- Recentes: **sempre as últimas 5 telas** abertas (a sexta empurra a mais antiga; a repetida sobe), só no navegador e **por usuário** (`sgi-spi.recentes.<id>`): outra pessoa no mesmo computador não vê as suas, e sair da conta esvazia a lista na tela. Os favoritos também ficam por usuário (`sgi-spi.favoritos.<id>`). As chaves antigas (`sgi-spi.recentes` e `sgi-spi.favoritos`) são apagadas.
- Anterior/próximo: a carteira guarda a busca, o filtro "Meus contratos" e a ordenação em `sessionStorage`; o detalhe do contrato mostra ‹ 3 de 34 › com o `GET /vizinhos`.
