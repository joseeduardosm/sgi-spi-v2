# Menu lateral configurável (`/api/menu`)

Tag no OpenAPI: **Menu**. Implementação:
- `backend/app/api/routes/menu.py`, `backend/app/schemas/menu.py` e `backend/app/models/menu.py` (tabela `menu_configuracao`, linha única; migração `b2d6f0a4c8e1`);
- frontend: `core/navegacao/menu-config.service.ts` e `menu-config.ts` (aplicam a configuração ao menu do código), tela `features/administracao/menu` (rota `/admin/menu`).

O administrador define a **ordem, os grupos, os nomes e os itens ocultos** do menu lateral e cria **grupos e links** (os antigos atalhos fixos). O menu é montado no cliente: o código tem o menu padrão (`core/navegacao/navegacao.ts`) e a configuração é aplicada **por cima, depois** do filtro de papel e de ACL. Ocultar um item o tira do menu **e da busca global/paleta de comandos**, mas **não muda o acesso**: a rota e a ACL continuam valendo.

A configuração vale para a seção "Navegação" do menu; a seção "Administração" é fixa.

## Acesso

- Leitura (`GET /api/menu`): qualquer usuário autenticado.
- Gravar e restaurar o padrão: ACL `atalhos` ≥ MODIFICACAO (o mesmo recurso que já gerenciava os atalhos; fechado: só quem o SuperRoot liberou).

## Nó do menu

| Campo | Descrição |
|---|---|
| `id` | Identificador estável (`^[a-z0-9][a-z0-9_-]*$`, até 60). Módulos usam o `id` do item do código (`contratos`, `rh`…); grupos e links criados usam `g-…` e `l-…` |
| `tipo` | `modulo` (só posição, nome e visibilidade de um item do código), `grupo` ou `link` |
| `rotulo` | Nome exibido (até 80). Obrigatório em grupos e links; em módulos, vazio mantém o padrão |
| `pai_id` | `id` do grupo que contém o nó; vazio = primeiro nível. No máximo dois níveis |
| `oculto` | Oculta do menu e da busca |
| `url` | Só em links: rota interna (`/ramais?q=a`) ou `http(s)://` |
| `nova_aba` | Só em links; padrão: externos sim, internos não |

Itens do código **ausentes** da configuração aparecem no fim, no grupo padrão deles (um módulo novo nunca some). Ids desconhecidos são ignorados.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/menu` | `200`: `{itens, padrao, atualizado_por_nome, atualizado_em}`. `padrao = true` e `itens = []` quando nada foi configurado |
| `PUT` | `/api/menu` | Substitui a configuração inteira. Corpo: `{"itens": [nó, …]}` (até 200). `200` com a configuração; `403` sem a ACL; `422` para ids repetidos, grupo inexistente, mais de dois níveis, link dentro de link, grupo ou link sem nome, endereço inválido (`javascript:`, `//…`) |
| `DELETE` | `/api/menu` | Apaga a configuração e volta ao menu padrão. `204`; `403` |

Cada gravação e restauração é auditada (`menu.gravar`, `menu.restaurar`).

## Migração dos atalhos fixos

A migração `b2d6f0a4c8e1` leva as categorias e os atalhos **ativos** para a configuração (categoria → grupo; atalho → link). As tabelas `atalhos_*` e `/api/atalhos` continuam existindo, mas o menu não as lê mais.
