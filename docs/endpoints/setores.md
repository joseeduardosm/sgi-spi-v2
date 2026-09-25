# Endpoints de setores (`/api/setores`)

Tag no OpenAPI: **Setores**. Implementação: `backend/app/api/routes/setores.py` e `backend/app/services/servico_setores.py`.

## Finalidade

Os setores representam a estrutura institucional (hierarquia com setor pai e líder) e os grupos sistêmicos. Eles funcionam como **grupos de acesso** na ACL: uma regra concedida a um setor vale para todos os seus membros.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `setores` ≥ `LEITURA`.
  - **Escrita:** papel **SuperRoot**.
- **Nome** único, sem diferenciar maiúsculas.
- **Hierarquia:** o setor pai não pode ser o próprio setor nem um subordinado dele (sem ciclos).
- **Exclusão:** só é permitida para setores **sem membros e sem subordinados**.
- **Setor inativo:** deixa de conceder acesso herdado na ACL.
- **Auditoria:** `setor.criar`, `setor.alterar` e `setor.excluir`.

## Schemas

### `GravacaoSetor` (requisição)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `nome` | string | sim | 1 a 150 |
| `setor_pai_id` | integer \| null | não | Setor pai. Nulo = raiz |
| `lider_id` | integer \| null | não | Usuário líder |
| `sistemico` | boolean | não (`false`) | Grupo sistêmico, não institucional (ex.: "Auditores") |
| `ativo` | boolean | não (`true`) | |
| `membros_ids` | integer[] | não (`[]`) | **Substitui** a lista de membros |

### `LeituraSetor` (resposta)

`id`, `nome`, `setor_pai_id`, `setor_pai_nome`, `lider_id`, `lider_nome`, `sistemico`, `ativo`, `total_membros`, `total_subordinados`, `criado_em`, `atualizado_em`.

`DetalheSetor` = `LeituraSetor` + `membros` (`OpcaoUsuario[]`).

---

## `GET /api/setores`

`LeituraSetor[]` em ordem alfabética. Parâmetro opcional `busca`, que filtra pelo nome.

## `GET /api/setores/{setor_id}`

`DetalheSetor`, com a lista de membros. `404 nao_encontrado`.

## `POST /api/setores`

Resposta **`201`**: `DetalheSetor`.

```json
{ "nome": "Coordenadoria de Contratos", "setor_pai_id": 3, "lider_id": 42, "sistemico": false, "ativo": true, "membros_ids": [42, 57, 61] }
```

Erros:
- `409 conflito`: nome duplicado;
- `400 invalido`: pai inválido ou ciclo, líder ou membros inexistentes;
- `422`.

## `PUT /api/setores/{setor_id}`

Mesmo corpo do `POST`. Resposta `200`: `DetalheSetor`. Erros: `404`, `409`, `400`, `422`.

## `DELETE /api/setores/{setor_id}`

Resposta **`204`**. Erros:
- `404`;
- `400 invalido`: `Não é possível excluir um setor que possui membros.` ou `... que possui setores subordinados.`

## Consumo no Angular

- Serviço: `SetoresApiService` (`frontend/src/app/features/setores/setores-api.service.ts`).
- Tela: `/setores` (`SetoresComponent`), protegida por `guardaAcl` (`setores`). Criação, edição e exclusão aparecem só para o SuperRoot.
