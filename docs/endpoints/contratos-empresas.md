# Endpoints de empresas contratadas (`/api/contratos/empresas`)

Tag no OpenAPI: **Contratos: empresas**. Implementação: `backend/app/api/routes/contratos/empresas.py` e `backend/app/services/contratos/servico_empresas.py`.

## Finalidade

Cadastro das empresas contratadas e de seus **prepostos**. O preposto é um contato da empresa, **não** um usuário do portal. Só empresas ativas podem ser escolhidas em contratos novos.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `contratos` ≥ `LEITURA`.
  - **Cadastro, alteração e prepostos:** ACL `contratos` ≥ `MODIFICACAO`.
  - **Exclusão da empresa:** ACL `contratos` = `CONTROLE_TOTAL`.
- **CNPJ:** aceito com ou sem máscara, gravado com os 14 dígitos, validado pelos dígitos verificadores e **único**.
- **CPF do preposto:** mesmas regras (11 dígitos), único **dentro da empresa**.
- **Exclusão:** só para empresas **sem contratos**. As demais podem ser inativadas.
- **Auditoria:** `contrato.empresa.criar`, `contrato.empresa.alterar`, `contrato.empresa.excluir`, `contrato.preposto.salvar` e `contrato.preposto.excluir`. As alterações guardam o "de → para" de cada campo (`alvo_tipo = empresa`).

## Schemas

### `GravacaoEmpresa` (requisição)

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `cnpj` | string | sim | Com ou sem máscara; dígitos verificadores válidos; único |
| `razao_social` | string | sim | 1 a 250 |
| `nome_fantasia` | string | não (`""`) | Até 250 |
| `endereco` | string | não (`""`) | Até 500 |
| `ativa` | boolean | não (`true`) | |

### `GravacaoPreposto` (requisição)

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `cpf` | string | sim | Com ou sem máscara; válido; único na empresa |
| `nome` | string | sim | 1 a 200 |
| `telefone` | string | não | Até 30 |
| `email` | string | não | Até 250; formato de e-mail |
| `cargo` | string | não | Até 150 |
| `ativo` | boolean | não (`true`) | |

### Respostas

- `ResumoEmpresa`: `id`, `cnpj` (14 dígitos), `razao_social`, `nome_fantasia`, `endereco`, `ativa`, `prepostos` (nomes), `contratos` (`[{id, numero}]`).
- `PaginaEmpresas`: `itens` (`ResumoEmpresa[]`), `total`, `pagina`, `tamanho_pagina`.
- `DetalheEmpresa`: dados da empresa + `prepostos` (`LeituraPreposto[]`: `id`, `cpf`, `nome`, `telefone`, `email`, `cargo`, `ativo`) + `contratos` + `criado_em`, `atualizado_em`.
- `OpcaoEmpresa`: `id`, `cnpj`, `razao_social`, `nome_fantasia`, `ativa`.

---

## `GET /api/contratos/empresas`

`PaginaEmpresas`. Parâmetros:

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `busca` | — | Pesquisa em razão social, nome fantasia, endereço, CNPJ, nome/CPF/e-mail dos prepostos e número, apelido e objeto dos contratos |
| `ordenar` | `razao_social` | `cnpj`, `razao_social`, `nome_fantasia` ou `endereco` |
| `direcao` | `asc` | `asc` ou `desc` |
| `pagina` / `tamanho_pagina` | 1 / 25 | Máximo de 100 por página |

## `GET /api/contratos/empresas/opcoes`

`OpcaoEmpresa[]` em ordem alfabética. Somente ativas, salvo `incluir_inativas=true`.

## `GET /api/contratos/empresas/{empresa_id}`

`DetalheEmpresa`. `404 nao_encontrado`.

## `POST /api/contratos/empresas`

Resposta **`201`**: `DetalheEmpresa`.

```json
{ "cnpj": "11.222.333/0001-81", "razao_social": "ACME Serviços Ltda", "nome_fantasia": "ACME", "endereco": "Rua A, 1", "ativa": true }
```

Erros: `409 conflito` (CNPJ já cadastrado); `422` (CNPJ inválido e demais campos).

## `PUT /api/contratos/empresas/{empresa_id}`

Mesmo corpo. Resposta `200`: `DetalheEmpresa`. Erros: `404`, `409`, `422`.

## `DELETE /api/contratos/empresas/{empresa_id}`

Resposta **`204`**. Erros: `404`; `409 conflito`: `A empresa possui contratos e não pode ser excluída. Inative-a.`

## `POST /api/contratos/empresas/{empresa_id}/prepostos`

Corpo `GravacaoPreposto`. Resposta **`201`**: `DetalheEmpresa` atualizada. Erros: `404`, `409` (CPF repetido na empresa), `422`.

## `PUT /api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}`

Corpo `GravacaoPreposto`. Resposta `200`: `DetalheEmpresa`. Erros: `404` (empresa ou preposto), `409`, `422`.

## `DELETE /api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}`

Resposta **`204`**. Erro: `404`.

## Consumo no Angular

- Serviço: `EmpresasApiService` (`frontend/src/app/features/contratos/compartilhado/empresas-api.service.ts`).
- Telas: `/contratos/empresas` (lista) e `/contratos/empresas/:id` / `/contratos/empresas/nova` (cadastro com prepostos), protegidas por `guardaAcl` (`contratos`).
