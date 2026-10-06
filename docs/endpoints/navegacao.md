# Navegação: busca global e favoritos do menu (`/api/busca`, `/api/favoritos`)

Tags no OpenAPI: **Busca global** e **Favoritos do menu**. Implementação:
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

## No Angular

- Busca: caixa no topo do layout autenticado (`shared/componentes/busca-global`), com atalho Ctrl+K ou `/`, setas, Enter e Esc.
- Favoritos: estrela ao lado do título da página e seção "Favoritos" na barra lateral. A lista fica também no navegador (`localStorage`, por usuário), para aparecer na hora; depois do login, a da conta prevalece.
- Recentes: **sempre as últimas 5 telas** abertas (a sexta empurra a mais antiga; a repetida sobe), só no navegador e **por usuário** (`sgi-spi.recentes.<id>`): outra pessoa no mesmo computador não vê as suas, e sair da conta esvazia a lista na tela. Os favoritos também ficam por usuário (`sgi-spi.favoritos.<id>`). As chaves antigas (`sgi-spi.recentes` e `sgi-spi.favoritos`) são apagadas.
- Anterior/próximo: a carteira guarda a busca, o filtro "Meus contratos" e a ordenação em `sessionStorage`; o detalhe do contrato mostra ‹ 3 de 34 › com o `GET /vizinhos`.
