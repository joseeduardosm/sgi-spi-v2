# Painel, relatórios e modelos globais (`/api/contratos/painel`, `/relatorios`, `/modelos`)

Tags no OpenAPI: **Contratos: painel**, **Contratos: relatórios** e **Contratos: modelos globais**.

Implementação:
- rotas: `backend/app/api/routes/contratos/relatorios.py` e `modelos.py`;
- serviços: `servico_painel.py`, `servico_relatorios.py` e `servico_configuracao_execucao.py`.

## `GET /api/contratos/painel`

Exige ACL `contratos` ≥ `LEITURA`. Parâmetros opcionais: `exercicio` (padrão: ano corrente), `empresa_id` e `contrato_id`. Os filtros valem para alertas, execução e números, **não** para as pendências.

Resposta `Painel`:
- `hoje`.
- `minhas_pendencias[]`: o que o usuário precisa fazer nos contratos em que é **criador ou integrante vigente da equipe**. **Competências de antes de 09/2026 não geram mais pendência** (medição, ciências, nota fiscal, retenção, CADIN etc.; vale o fim do período, ou a criação, na diferença de reajuste). O corte é a constante `PENDENCIAS_A_PARTIR_DE` em `servico_painel.py`; prorrogação, reajuste, aditamento/supressão e a geração da execução não mudam.
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

## `GET /api/contratos/painel/vigencias`

Painel de vigências, que alimenta a aba **Vigências**. Traz uma linha do tempo de vigência por contrato vigente.

- **Autorização:** ACL `contratos` ≥ LEITURA (senão `403 acl_negado`).
- **Parâmetro opcional:** `empresa_id` (UUID), que filtra os contratos. As opções de `empresas` continuam todas.
- **Contratos que entram:** só os vigentes, isto é, `ativo` e `a_vencer`. Encerrados e suspensos ficam de fora.
- **Ordem:** do que vence primeiro ao último (`data_fim`, depois `numero`).

### Resposta `200 OK`: `PainelVigencias`

| Campo | Tipo | Descrição |
|---|---|---|
| `hoje` | date | Data de referência dos cálculos |
| `contratos` | `VigenciaContratoPainel[]` | Uma linha por contrato vigente |
| `empresas` | `OpcaoFiltro[]` | Empresas com contrato vigente (filtro) |

`VigenciaContratoPainel`:

| Campo | Descrição |
|---|---|
| `contrato_id`, `numero` | Identificação |
| `rotulo`, `empresa` | Apelido (ou razão social, se não houver apelido) e razão social |
| `situacao` | `ativo` ou `a_vencer` (termina em até 90 dias) |
| `data_inicio`, `data_fim` | Início do contrato e fim da vigência atual: os extremos da linha do tempo |
| `dias_restantes` | Dias corridos de hoje até `data_fim` (0 = vence hoje) |
| `data_limite_maxima`, `meses_prorrogaveis` | Limite pela vigência máxima e quantos meses ainda cabem (0 = no limite) |
| `vigencias[]` | `sequencia`, `inicio` e `fim` da vigência inicial e de cada prorrogação |
| `reajustes[]` | Meses de referência dos reajustes concluídos |

```json
{
  "hoje": "2026-09-28",
  "contratos": [{
    "contrato_id": "…", "numero": "022/2024", "rotulo": "Gerador", "empresa": "Manutesp Ltda.", "situacao": "a_vencer",
    "data_inicio": "2026-03-26", "data_fim": "2026-11-25", "dias_restantes": 58,
    "data_limite_maxima": "2036-03-25", "meses_prorrogaveis": 112,
    "vigencias": [{ "sequencia": 1, "inicio": "2026-03-26", "fim": "2026-11-25" }], "reajustes": []
  }],
  "empresas": [{ "id": "…", "rotulo": "Manutesp Ltda." }]
}
```

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
- `/contratos/vigencias`: aba **Vigências**, ao lado de "Painel" no cabeçalho do módulo.
  - Uma linha por contrato, com um trilho de **mesma largura em todas as linhas**, em escala própria (de `data_inicio` a `data_fim`).
  - Os blocos de vigência (inicial e prorrogações) ficam separados por filete. O preenchimento vai até hoje, e marcas verdes indicam os reajustes.
  - A cor segue `dias_restantes`: vermelho até 90 dias, âmbar até 180 e azul acima disso.
  - Filtro de empresa.
- `/contratos`: botões **Exportar Previsão Orçamentária** e **Relatório Executivo de Notas de Empenho**, só para o SuperRoot.
- `/contratos/modelos`: modelos globais, só para o SuperRoot.
