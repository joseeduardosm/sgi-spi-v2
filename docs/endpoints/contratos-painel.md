# Painel, relatórios e modelos globais (`/api/contratos/painel`, `/relatorios`, `/modelos`)

Tags no OpenAPI: **Contratos: painel**, **Contratos: relatórios** e **Contratos: modelos globais**.

Implementação:
- rotas: `backend/app/api/routes/contratos/relatorios.py` e `modelos.py`;
- serviços: `servico_painel.py`, `servico_relatorios.py` e `servico_configuracao_execucao.py`.

## `GET /api/contratos/painel`

Exige ACL `contratos` ≥ `LEITURA`. Parâmetros opcionais: `exercicio` (padrão: ano corrente), `empresa_id` e `contrato_id`. Os filtros valem para alertas, execução e números, **não** para as pendências.

Resposta `Painel`:
- `hoje`.
- `minhas_pendencias[]`: o que o usuário precisa fazer nos contratos em que é **criador ou integrante vigente da equipe**.
  - Campos: `tipo`, `contrato_numero`, `contrato_apelido`, `descricao`, `rota` (tela do Angular) e `desde` (para ordenar por urgência).
  - Tipos:
    - competências liberadas e não concluídas: a etapa atual, `ciencia_medicao` ou `ciencia_ateste` (para os integrantes da equipe, só enquanto ninguém deu ciência; no ateste, depois das notas fechadas. Após a primeira ciência, a pendência volta a ser a etapa);
    - `base_execucao`: competências ainda não geradas;
    - processos em elaboração: `prorrogacao`, `reajuste`, `alteracao` e `ciencia_alteracao` (só enquanto a alteração não tem nenhuma ciência).
- `alertas[]` da carteira, **agrupados por contrato** (`AlertasContrato`: `contrato_id`, `contrato_numero`, `contrato_apelido`, `empresa`, `gravidade` — a maior do contrato, `riscos[]`). Só entram **riscos**; tarefas ficam em `minhas_pendencias`. Cada `Risco`: `tipo`, `gravidade` (`alta`/`media`), `descricao`, `rota`, `data`, `valor`. Contratos com risco alto vêm primeiro. Tipos:
  - `a_vencer_sem_prorrogacao`: a até 90 dias do fim e sem rascunho de prorrogação;
  - `vigencia_maxima`: a vencer e sem meses disponíveis (planejar nova contratação);
  - `reajuste_pendente`: mês de reajuste passado, com o contrato já com 12 meses, sem reajuste aberto;
  - `empenho_insuficiente`: o **saldo livre** das NEs não cobre a próxima competência;
  - `pagamento_vencido` / `pagamento_vencendo` (até 5 dias): recebimento da NF + prazo;
  - `competencias_atrasadas`: **um** risco por contrato somando as competências com período encerrado há mais de 30 dias sem medição concluída (`alta` acima de 60 dias). Na competência de diferença de reajuste, o prazo conta da sua criação (conclusão do reajuste).
- `execucao`: exercício, 12 `meses` com `previsto`, `medido` e `pago` (débitos das OBs, somados no **mês da competência paga**, e não na data do pagamento: a OB de 08/2026 lançada em setembro entra em agosto; estornos entram como negativos), totais, e `empenhado`, `consumido` e `saldo_empenho`.
- `numeros`: `contratos_ativos`, `contratos_a_vencer`, `contratos_encerrados`, `valor_global_ativos`, `base_mensal_ativos`.
- `empresas[]` e `contratos[]`: opções dos filtros (`id`, `rotulo`).

## `GET /api/contratos/relatorios/notas-empenho?formato=xlsx|pdf`

Relatório Executivo de Notas de Empenho: todas as NEs de todos os contratos, com valor inicial, consumido e saldo. **SuperRoot.**

## `GET /api/contratos/relatorios/previsao-orcamentaria`

Exportar Previsão Orçamentária consolidada. **SuperRoot.**

Parâmetros:
- `exercicio`;
- `formato` (`xlsx`/`pdf`);
- seções: `resumo_anual`, `detalhamento_mensal`;
- cenários em elaboração somados à previsão: `cenario_reajustes`, `cenario_aditamentos`, `cenario_supressoes`, `cenario_prorrogacoes`.

O resumo anual traz uma linha por contrato: previsto, uma coluna por cenário e o total. O detalhamento traz os 12 meses.

## Modelos globais (`/api/contratos/modelos`)

Checklists e formulários reutilizáveis, que a tela copia para o contrato como uma nova versão inativa. As cópias não mudam quando o modelo muda.

| Método e caminho | Autorização | Descrição |
|---|---|---|
| `GET /api/contratos/modelos?tipo=&somente_ativos=true` | ACL `contratos` ≥ LEITURA | `LeituraModelo[]` (`id`, `tipo`, `nome`, `conteudo`, `ativo`, `atualizado_em`) |
| `POST /api/contratos/modelos` | SuperRoot | `{ "tipo": "checklist", "nome", "itens": [{ "nome", "observacao", "obrigatorio" }] }` ou `{ "tipo": "formulario", "nome", "definicao": {…} }` → `201` |
| `PUT /api/contratos/modelos/{modelo_id}` | SuperRoot | Altera (o tipo não muda) |
| `DELETE /api/contratos/modelos/{modelo_id}` | SuperRoot | `204` |

`conteudo` do checklist: `{ "itens": [...] }`. Do formulário: a mesma `definicao` do formulário do contrato.

## Consumo no Angular

- `/contratos/painel`: tela do painel e **tela inicial do módulo**. O item Módulos → Contratos da barra lateral abre aqui e continua destacado em todas as telas sob `/contratos`. **Minhas pendências** e **Alertas de risco** aparecem como resumos clicáveis (título e total de `minhas_pendencias` / `alertas`). O clique abre `/contratos/minhas-pendencias` e `/contratos/alertas-de-risco`, com uma ocorrência por cartão.
- `/contratos`: botões **Exportar Previsão Orçamentária** e **Relatório Executivo de Notas de Empenho**, só para o SuperRoot.
- `/contratos/modelos`: modelos globais, só para o SuperRoot.
