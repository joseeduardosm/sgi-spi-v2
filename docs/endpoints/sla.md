# SLA de prazos

Prazos de **resposta** (primeiro atendimento) e de **resolução**, em **dias úteis** (segunda a sexta, sem os feriados cadastrados em `rh_feriados`), contados a partir do **dia da criação**. Vale para **Tarefas** (por prioridade) e **Melhorias** (regra única). Abrir Chamado fica de fora por ora.

## Política

Tabela `sla_politicas` (migração `b4d7f1a9c2e6`, com os padrões abaixo e o recurso de ACL `sla`, que nasce fechado: só a conta administrativa). Linha ausente ou `ativo=false` usa o padrão.

| Módulo | Prioridade | Resposta | Resolução |
|---|---|---|---|
| Tarefas | crítica | 1 | 3 |
| Tarefas | alta | 2 | 5 |
| Tarefas | normal | 3 | 10 |
| Tarefas | baixa | 5 | 20 |
| Melhorias | (única) | 3 | 15 |

### `GET /api/sla/politicas`
ACL `sla` ≥ LEITURA. Devolve `[ { modulo, prioridade, dias_uteis_resposta, dias_uteis_resolucao, ativo } ]` (5 linhas; as não gravadas vêm com o padrão).

### `PUT /api/sla/politicas`
ACL `sla` ≥ MODIFICACAO (`403`). Corpo `{ politicas: [ ... ] }` com as linhas a gravar. `400` se a resolução for menor que a resposta ou a combinação módulo/prioridade não existir. Registra auditoria (`sla.politicas.gravar`). Devolve a lista atualizada.

## Como o SLA é calculado (`SlaItem`)

`meta_resposta_dias`, `meta_resolucao_dias`, `prazo_resposta` e `prazo_resolucao` (último dia, inclusive), `respondido_em`, `resolvido_em`, `situacao_resposta` e `situacao_resolucao`:

- `cumprido`: feito até o último dia do prazo; `cumprido_fora`: feito depois.
- Ainda aberto: `estourado` (passou do último dia), `em_risco` (80% ou mais do prazo em dias úteis já consumido) ou `no_prazo`.
- Quem resolveu sem registrar o primeiro atendimento respondeu, no mínimo, ao resolver.

## Onde aparece

- **Tarefas:** `TarefaResumo.sla` (e no detalhe). Resposta = `iniciada_em − criado_em`; resolução = `concluida_em − criado_em`; prioridade atual da tarefa. Fica **vazio nas tarefas controladas por outro módulo** (Contratos). Cartão do quadro mostra o selo "SLA" quando a resolução está em risco ou estourada; a janela da tarefa mostra os dois prazos. No **Desempenho** (`GET …/desempenho`): `sla` (`resolucoes_no_prazo`, `resolucoes_fora`, `percentual_resolucao`, `respostas_*`, `percentual_resposta`, `abertas_estouradas`, `abertas_em_risco`) e `pessoas[].sla_percentual` (resoluções no prazo entre as concluídas no período). O relatório de tarefas (XLSX) ganhou a coluna "SLA (resolução)".
- **Melhorias:** `SugestaoTriagem.sla` (só triagem; o autor não vê). Resposta = primeira mudança de situação; resolução = conclusão **ou recusa**. Aparece na fila de triagem, no detalhe e na planilha (colunas "SLA resposta" e "SLA resolução").
- **Angular:** tela `/admin/sla` (Administração › SLA de prazos).
