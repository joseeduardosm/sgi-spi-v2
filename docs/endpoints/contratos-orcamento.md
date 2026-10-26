# Endpoints de orçamento do contrato (`/api/contratos/{contrato_id}/previsao` e `/notas-empenho`)

Tag no OpenAPI: **Contratos: orçamento**. Implementação: `backend/app/api/routes/contratos/orcamento.py` e `backend/app/services/contratos/servico_orcamento.py`.

## Finalidade

Previsão orçamentária mensal por vigência e controle das Notas de Empenho (NE) com extrato.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `contratos` ≥ `LEITURA`.
  - **Gravação:** poder editar o contrato (ACL ≥ `MODIFICACAO` e ser SuperRoot, ter controle total, ser criador ou integrante vigente da equipe).
- **Previsão mensal** (sempre por mês civil, em todas as vigências):
  - itens **contínuos** entram em todos os meses: quantidade mensal × preço × fator;
  - o **fator** usa a convenção comercial 30/360 (o último dia do mês vale 30; 15/01 a 31/01 = 16/30). Itens "sempre integral" usam fator 1;
  - itens **sob demanda** entram só nos meses com apontamento;
  - o preço e a quantidade de cada mês consideram os reajustes e os aditamentos/supressões **concluídos**.
- **Apontamentos sob demanda:** a grade de cada vigência não pode deixar saldo negativo (saldo = limite da vigência − soma dos apontamentos).
  - O limite da vigência 1 é a quantidade total do item. Nas prorrogações, é o limite definido na tela de prorrogação.
  - Salvar **sela** a previsão da vigência: depois disso, quem edita o contrato (equipe, criador, controle total ou SuperRoot) pode alterar (a gravação fica auditada como `contrato.previsao.editar_selada`).
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

## `GET /api/contratos/{contrato_id}/orcamento-executivo?exercicio=AAAA`

Exige ACL `contratos` ≥ `LEITURA` (`exercicio` padrão: ano corrente). Respostas executivas do exercício, mostradas no cartão "Orçamento do exercício" do detalhe do contrato (substitui o antigo cartão "Empenho de AAAA"):

- **Saldo remanescente** (`remanescente`): previsto − **valor bruto das notas fiscais** dos meses cuja competência regular concluiu todas as etapas (`meses_concluidos[]`, `previsto_concluido`, `pago_concluido`). Meses em aberto ou ainda não pagos ficam de fora; negativo = pago acima do previsto.
- **Empenho:** `empenhado` (NEs do exercício: ano do número da NE, ou do cadastro) e `livre` (empenhado − consumido − cancelado − comprometido por medições ainda não pagas).
- **Necessidade:** `necessidade` = previsto dos meses do exercício ainda sem medição concluída, a partir do corte de pendências (09/2026, ou o "Desconsiderar alertas a partir de" do contrato); `meses_restantes`.
- **Cobertura:** o saldo livre cobre esses meses em ordem: `meses_cobertos`, `coberto_ate`, `primeiro_descoberto` e `pedir_reforco_ate` (fim do período do primeiro mês descoberto: a medição dele precisa de empenho).
- **Decisão:** `reforco` = quanto falta empenhar (zero se sobra) e `disponivel_cancelar` = quanto do saldo livre pode ser cancelado ou transferido sem faltar para os meses restantes.

## `GET /api/contratos/{contrato_id}/notas-empenho`

`LeituraNotaEmpenho[]`: `id`, `numero`, `valor_original`, `consumido`, `cancelado`, `saldo`, `comprometido`, `saldo_livre`, `percentual_consumido`, `faixa`, `vinculada`, `criado_em` e `movimentos[]` (`data`, `tipo` — `pagamento` ou `estorno`, `competencia`, `competencia_id`, `competencia_rotulo`, `debito` — negativo no estorno, `saldo_apos`, `justificativa` — motivo da reabertura no estorno, `autor`).

`cancelamentos[]` traz as NEs de cancelamento aplicadas (`id`, `numero`, `valor`, `justificativa`, `autor`, `criado_em`). Saldo = valor original − débitos − cancelamentos.

O estorno surge quando uma competência paga é reaberta (ver [contratos-execucao.md](contratos-execucao.md)); o pagamento original continua no extrato.

## `POST /api/contratos/{contrato_id}/notas-empenho`

```json
{ "numero": "2026NE00012", "valor_original": "150000.00" }
```

Resposta **`201`**: a lista atualizada. Erros: `409` (número repetido), `422` (valor ≤ 0 ou número com mais de 30 caracteres), `403`.

## `PUT /api/contratos/{contrato_id}/notas-empenho/{nota_id}`

Mesmo corpo. Resposta `200`: a lista. Erros: `400` (valor abaixo do consumido), `409`, `404`.

## `POST /api/contratos/{contrato_id}/notas-empenho/{nota_id}/cancelamentos`

Registra a **NE de cancelamento**: abate `valor` do saldo da NE original (parcial ou total).

```json
{ "numero": "2026NE00099", "valor": "50000.00", "justificativa": "Redução do escopo" }
```

Regras: o `numero` (até 30) é único no contrato entre NEs e cancelamentos (sem diferenciar maiúsculas); `valor` > 0 e até o saldo atual da NE, mesmo que parte esteja reservada por medições. Se, depois do cancelamento, nenhuma NE do contrato tiver saldo, **salvar e concluir a medição** são recusados (`400`, "As NEs de cancelamento consumiram todo o saldo…"); as demais etapas não mudam. NE com cancelamento não pode ser excluída nem ter o valor abaixo de consumido + cancelado. Resposta **`201`**: a lista de NEs. Erros: `400` (valor acima do saldo), `404`, `409` (número repetido), `422`, `403`.

## `DELETE /api/contratos/{contrato_id}/notas-empenho/{nota_id}`

Resposta **`204`**. Erros: `400` (NE ligada a competência, com débitos ou com cancelamentos), `404`.

## Consumo no Angular

`ContratosApiService` (`frontend/src/app/features/contratos/compartilhado/contratos-api.service.ts`), nas abas **Previsão orçamentária** e **Notas de Empenho** do detalhe do contrato.
