# Endpoints de orçamento do contrato (`/api/contratos/{contrato_id}/previsao` e `/notas-empenho`)

Tag no OpenAPI: **Contratos: orçamento**. Implementação: `backend/app/api/routes/contratos/orcamento.py` e `backend/app/services/contratos/servico_orcamento.py`.

## Finalidade

Previsão orçamentária mensal por vigência e controle das Notas de Empenho (NE) com extrato.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `contratos` ≥ `LEITURA`.
  - **Gravação:** poder editar o contrato (ACL ≥ `MODIFICACAO` e ser SuperRoot, criador ou integrante vigente da equipe).
- **Previsão mensal** (sempre por mês civil, em todas as vigências):
  - itens **contínuos** entram em todos os meses: quantidade mensal × preço × fator;
  - o **fator** usa a convenção comercial 30/360 (o último dia do mês vale 30; 15/01 a 31/01 = 16/30). Itens "sempre integral" usam fator 1;
  - itens **sob demanda** entram só nos meses com apontamento;
  - o preço e a quantidade de cada mês consideram os reajustes e os aditamentos/supressões **concluídos**.
- **Apontamentos sob demanda:** a grade de cada vigência não pode deixar saldo negativo (saldo = limite da vigência − soma dos apontamentos).
  - O limite da vigência 1 é a quantidade total do item. Nas prorrogações, é o limite definido na tela de prorrogação.
  - Salvar **sela** a previsão da vigência: depois disso, só o SuperRoot altera (a gravação fica auditada como `contrato.previsao.editar_selada`).
- **Nota de Empenho:**
  - número único no contrato, sem diferenciar maiúsculas;
  - valor original > 0;
  - saldo = valor original − débitos do extrato (pagamentos − estornos);
  - **comprometido** = valor a pagar das competências com medição concluída e ainda sem OB que apontam a NE, distribuído na ordem de consumo; **saldo livre** = saldo − comprometido. Medição e NF são validadas contra o saldo livre;
  - faixa de consumo: `verde` até 50%, `amarelo` até 75%, `vermelho` acima;
  - o valor não pode ficar abaixo do consumido;
  - só pode ser excluída se não estiver ligada a nenhuma competência nem tiver débitos.
- **Auditoria:** `contrato.previsao.salvar`, `contrato.previsao.editar_selada`, `contrato.nota_empenho.criar`, `.alterar` e `.excluir`.

---

## `GET /api/contratos/{contrato_id}/previsao`

Resposta `Previsao`:
- `total_previsto`;
- `vigencias[]`: `sequencia`, `inicio`, `fim`, `meses` (dia 1 de cada mês), `possui_sob_demanda`, `salva`, `salva_em`, `salva_por_nome`, `pode_editar`, `total_previsto` e `itens_sob_demanda[]` (`item_id`, `ordem`, `descricao`, `limite`, `apontamentos` `{AAAA-MM-01: qtd}`, `saldo`);
- `meses[]`: `competencia`, `sequencia_vigencia`, `inicio`, `fim`, `fator`, `base_mensal` (contínuos em mês cheio), `valor`, `acumulado` (dentro da vigência) e `itens[]` (`item_id`, `descricao`, `tipo`, `quantidade`, `valor_unitario`, `fator`, `subtotal`).

## `PUT /api/contratos/{contrato_id}/previsao/{sequencia_vigencia}`

Substitui a grade da vigência e a sela. Resposta: `Previsao`.

```json
{ "apontamentos": [ { "item_id": "…", "competencia": "2026-01-01", "quantidade": "10" } ] }
```

Erros:
- `400 invalido`: saldo negativo, mês fora da vigência, item que não é sob demanda, ou previsão selada (usuário comum);
- `403`;
- `404`: contrato ou vigência.

## `GET /api/contratos/{contrato_id}/previsao/{sequencia_vigencia}/xlsx`

Planilha com as abas "Previsão mensal" e "Itens por competência".

## `GET /api/contratos/{contrato_id}/notas-empenho`

`LeituraNotaEmpenho[]`: `id`, `numero`, `valor_original`, `consumido`, `saldo`, `comprometido`, `saldo_livre`, `percentual_consumido`, `faixa`, `vinculada`, `criado_em` e `movimentos[]` (`data`, `tipo` — `pagamento` ou `estorno`, `competencia`, `competencia_id`, `competencia_rotulo`, `debito` — negativo no estorno, `saldo_apos`, `justificativa` — motivo da reabertura no estorno, `autor`).

O estorno surge quando uma competência paga é reaberta (ver [contratos-execucao.md](contratos-execucao.md)); o pagamento original continua no extrato.

## `POST /api/contratos/{contrato_id}/notas-empenho`

```json
{ "numero": "2026NE00012", "valor_original": "150000.00" }
```

Resposta **`201`**: a lista atualizada. Erros: `409` (número repetido), `422` (valor ≤ 0 ou número com mais de 30 caracteres), `403`.

## `PUT /api/contratos/{contrato_id}/notas-empenho/{nota_id}`

Mesmo corpo. Resposta `200`: a lista. Erros: `400` (valor abaixo do consumido), `409`, `404`.

## `DELETE /api/contratos/{contrato_id}/notas-empenho/{nota_id}`

Resposta **`204`**. Erros: `400` (NE ligada a competência ou com débitos), `404`.

## Consumo no Angular

`ContratosApiService` (`frontend/src/app/features/contratos/compartilhado/contratos-api.service.ts`), nas abas **Previsão orçamentária** e **Notas de Empenho** do detalhe do contrato.
