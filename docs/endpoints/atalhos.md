# Atalhos fixos da barra lateral (`/api/atalhos`)

Tag no OpenAPI: **Atalhos fixos**. Implementação:
- `backend/app/api/routes/atalhos.py` e `backend/app/schemas/atalhos.py`;
- `backend/app/models/atalho_fixo.py` (tabelas `atalhos_categorias` e `atalhos_fixos`, migração `b5d9f3a7c1e2`);
- frontend: `core/navegacao/atalhos-fixos.service.ts`, grupo "Atalhos" em `shared/layout/barra-lateral` e tela `features/administracao/atalhos` (rota `/admin/atalhos`).

Links fixos, iguais para todos os usuários (internos e externos), organizados em **categorias**. Na barra lateral aparece o grupo dobrável **Atalhos**; dentro dele, cada categoria também é dobrável. Atalho **interno** é uma rota do SGI (`/ramais`, `/contratos?...`); **externo** é um endereço `http://` ou `https://`.

## Acesso

- Leitura (`GET /api/atalhos`): qualquer usuário autenticado.
- Gestão (`/gestao` e todas as gravações): ACL `atalhos` ≥ MODIFICACAO. O recurso nasce **fechado** (migração cria uma regra CONTROLE_TOTAL só para a conta administrativa/SuperRoot); o SuperRoot libera usuários e setores em Controle de acesso.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/atalhos` | Categorias **ativas** com ao menos um atalho **ativo**, ordenadas por `ordem` e id. Resposta `200`: `{"categorias": [{id, nome, ordem, ativo, atalhos: [{id, categoria_id, titulo, url, externo, nova_aba, ordem, ativo}]}]}` |
| `GET` | `/api/atalhos/gestao` | Mesma estrutura, incluindo inativos e categorias vazias. `403` sem a ACL |
| `POST` | `/api/atalhos/categorias` | Cria categoria. Corpo: `nome` (1–80), `ordem` (0–9999), `ativo`. `201`; `409` (`conflito`) se o nome já existe (sem diferenciar maiúsculas) |
| `PUT` | `/api/atalhos/categorias/{categoria_id}` | Altera categoria. `404`; `409` |
| `DELETE` | `/api/atalhos/categorias/{categoria_id}` | Exclui a categoria **e os atalhos dela**. `204`; `404` |
| `POST` | `/api/atalhos/itens` | Cria atalho. Corpo: `categoria_id`, `titulo` (1–80), `url`, `nova_aba` (opcional), `ordem`, `ativo`. `201`; `404` (categoria); `422` (destino inválido) |
| `PUT` | `/api/atalhos/itens/{atalho_id}` | Altera atalho. `404`; `422` |
| `DELETE` | `/api/atalhos/itens/{atalho_id}` | Exclui o atalho. `204`; `404` |

### Regras

- `url`: interna começa com `/` (não `//`, sem `://`); externa é `http://` ou `https://` sem espaços. Outro formato (ex.: `javascript:`) → `422`.
- `nova_aba` em branco: externos abrem em nova aba; internos, na mesma.
- Todas as gravações são auditadas (`atalho.*`). Erros no formato `{"detalhe", "codigo"}`.
