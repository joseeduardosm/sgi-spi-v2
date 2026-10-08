# Endpoints de controle de acesso (`/api/acl`)

Tag no OpenAPI: **Controle de acesso (ACL)**. Implementação: `backend/app/api/routes/acl.py`. Cálculo em `backend/app/services/servico_acl.py`; administração em `servico_admin_acl.py`.

## Finalidade

Define quem acessa cada módulo do portal. A política e o cálculo do nível efetivo estão descritos em [autenticacao.md](../autenticacao.md#acl-por-recurso).

**Nomes dos níveis:** os valores gravados continuam `LEITURA`, `MODIFICACAO` e `CONTROLE_TOTAL` (hierárquicos). Cada recurso diz o que cada nível libera nele: `GET /acl/recursos`, `GET /acl/regras`, `GET /acl/meus-acessos` e `GET /acl/efetivo/{usuario_id}` trazem `niveis` (`{LEITURA|MODIFICACAO|CONTROLE_TOTAL: {rotulo, descricao}}`), definido em `backend/app/services/acl_niveis.py`. A tela de ACL mostra esses textos (ex.: Protocolo, Modificação = "Reservar números de documentos"). **Todo recurso novo precisa de entrada nesse arquivo** (o teste `test_acl_niveis.py` falha se faltar).

## Regras gerais

- **Autorização:**
  - `GET /api/acl/meus-acessos`: qualquer usuário autenticado com perfil em dia.
  - Demais endpoints: papel **SuperRoot**.
- **Níveis:** `LEITURA` < `MODIFICACAO` < `CONTROLE_TOTAL`.
- **Auditoria:**
  - recursos: `acl.recurso.criar`, `acl.recurso.alterar` e `acl.recurso.excluir`;
  - regras: `acl.regra.criar`, `acl.regra.alterar` e `acl.regra.excluir`.
- **Recursos iniciais** (criados pela migração): `usuarios`, `setores`, `contratos` e `relatorios`.
- **Recursos criados abertos a todos** (sem regras): `abrir-chamado`, item "Abrir Chamado" da barra lateral (migração `d1f4b8a2e6c9`; ver [chamados.md](chamados.md)). O SuperRoot pode restringir criando regras.
- **Recursos criados fechados** (só a conta administrativa principal tem CONTROLE_TOTAL; o SuperRoot libera os demais):
  - `importacao-contratos`: botão "Importar XLSX" (migração `d4f7b2c9e1a3`);
  - `atalhos`: gestão dos atalhos fixos da barra lateral, nasce fechado (migração `b5d9f3a7c1e2`; ver [atalhos.md](atalhos.md));
  - `documentacao-api`: Swagger, ReDoc e OpenAPI; nasce fechado (migração `c6e0a4b8d2f1`; ver [documentacao-api.md](documentacao-api.md));
  - `manuais`: módulo Manuais (BookStack); nasce **sem regras**, aberto a todo usuário autenticado (migração `d7a1c5e9b3f2`; ver [manuais.md](manuais.md));
  - `importacao-modelos`: botão "Importar XLSX" de checklists e formulários de avaliação (migração `e5a8c3d7f2b1`; ver [contratos-importacao-modelos-xlsx.md](contratos-importacao-modelos-xlsx.md));
  - `mensageria-setores`: envio de mensagens para setores inteiros, que exige CONTROLE_TOTAL (migração `0c11fdac4f46`; ver [mensagens.md](mensagens.md)).

---

## `GET /api/acl/meus-acessos`

Recursos **ativos** aos quais o usuário autenticado tem acesso, com o nível efetivo. Recursos sem acesso não aparecem.

Resposta `200`, `AcessoEfetivo[]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `recurso_id` | integer | |
| `nome` | string | Nome do recurso |
| `slug` | string | Identificador técnico |
| `url_base` | string | Rota base no portal |
| `nivel` | string \| null | Nível efetivo (nulo = sem acesso; só em `/efetivo`) |

```json
[{ "recurso_id": 1, "nome": "Usuários", "slug": "usuarios", "url_base": "/usuarios", "nivel": "CONTROLE_TOTAL" }]
```

## `GET /api/acl/efetivo/{usuario_id}`

Nível efetivo de um usuário em **todos** os recursos ativos (`nivel` nulo = sem acesso). Serve para auditar permissões. `404` se o usuário não existir.

---

## Recursos

### `LeituraRecurso`

`id`, `nome`, `slug`, `descricao`, `url_base`, `ativo`, `total_regras` (zero = recurso aberto), `criado_em`, `atualizado_em`.

### `GravacaoRecurso`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `nome` | string | sim | 1 a 100, único sem diferenciar maiúsculas |
| `slug` | string | sim | 1 a 60, único. Normalizado: minúsculas, caracteres fora de `a-z0-9_-` viram `-` |
| `descricao` | string | não | até 2000 |
| `url_base` | string | não | Ex.: `/contratos` |
| `ativo` | boolean | não (`true`) | Inativo = acesso aberto |

| Método e caminho | Resposta | Erros |
|---|---|---|
| `GET /api/acl/recursos` | `200 LeituraRecurso[]` | |
| `POST /api/acl/recursos` | **`201`** `LeituraRecurso` | `409 conflito`, `400`, `422` |
| `PUT /api/acl/recursos/{recurso_id}` | `200` `LeituraRecurso` | `404`, `409`, `400`, `422` |
| `DELETE /api/acl/recursos/{recurso_id}` | **`204`** | `404` |

Excluir um recurso remove também as regras dele, e o módulo volta a ficar aberto. O slug é usado pelo código (`exigir_acl("slug")`): alterá-lo desvincula as proteções existentes.

---

## Regras

### `GravacaoRegra`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `recurso_id` | integer | sim | Recurso existente |
| `nivel` | `LEITURA` \| `MODIFICACAO` \| `CONTROLE_TOTAL` | sim | |
| `usuarios_ids` | integer[] | * | Usuários contemplados |
| `setores_ids` | integer[] | * | Setores contemplados |

\* Pelo menos um usuário ou setor.

### `LeituraRegra`

`id`, `recurso_id`, `recurso_nome`, `recurso_slug`, `nivel`, `usuarios` (`OpcaoUsuario[]`), `setores` (`{id, nome, sistemico}[]`), `criado_em`, `atualizado_em`.

| Método e caminho | Resposta | Erros |
|---|---|---|
| `GET /api/acl/regras?recurso_id=` | `200 LeituraRegra[]` (filtro opcional) | |
| `POST /api/acl/regras` | **`201`** `LeituraRegra` | `400 invalido`: recurso inválido, sem alvos, alvos inexistentes. `422`: nível inválido |
| `PUT /api/acl/regras/{regra_id}` | `200` `LeituraRegra` | `404`, `400`, `422` |
| `DELETE /api/acl/regras/{regra_id}` | **`204`** | `404` |

```json
{ "recurso_id": 3, "nivel": "MODIFICACAO", "usuarios_ids": [42], "setores_ids": [5] }
```

**Atenção:** a primeira regra de um recurso o transforma em lista positiva. A partir dela, quem não estiver contemplado perde o acesso.

## Consumo no Angular

- `AcessoService` (`frontend/src/app/core/acesso/acesso.service.ts`) carrega `meus-acessos` após o login. A barra lateral oculta os itens cujo `acl` não aparece, e o `guardaAcl` protege as rotas.
- Tela de administração: `/admin/acl` (`AclComponent`), com abas **Regras**, **Recursos** e **Acesso efetivo**. Restrita ao SuperRoot. Serviço: `AclApiService`.
