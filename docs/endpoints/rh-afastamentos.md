# Módulo RH: férias e licença-prêmio (`/api/rh/afastamentos`, `/api/rh/parametros`)

Tag no OpenAPI: **Módulo RH**. Implementação:
- rotas: `backend/app/api/routes/rh.py`;
- regras: `backend/app/services/rh/servico_afastamentos.py` e `servico_periodos.py` (períodos aquisitivos);
- modelos: `backend/app/models/rh.py` (`rh_afastamentos`, `rh_afastamentos_eventos`, `rh_periodos_aquisitivos`, `rh_parametros`).

Férias (`ferias`) e licença-prêmio (`licenca_premio`) são administradas juntas: mesma tela, mesmo calendário e mesmo painel. Os papéis (CGP, autorizador, substituto) estão descritos em [rh-cadastro.md](rh-cadastro.md).

## Regras (parametrizáveis pela CGP em `rh_parametros`)

| Regra | Parâmetro | Valor inicial |
|---|---|---|
| Mínimo de dias consecutivos por período | `minimo_dias_ferias`, `minimo_dias_lp` | 5 e 5 |
| Dias da semana em que o período não pode começar (0 = segunda … 6 = domingo) | `inicio_vedado_ferias`, `inicio_vedado_lp` | `[0]` (segunda) e `[0]` |
| Antecedência mínima para agendar | `antecedencia_minima_dias` | 30 |
| Cancelar ou alterar até N dias antes do início (a CGP pode sempre) | `prazo_cancelamento_dias` | 5 |
| Permite emendar férias e licença-prêmio em sequência | `permite_emenda` | sim |
| Alerta com pelo menos N pessoas do mesmo setor afastadas ao mesmo tempo (0 desliga) | `limite_alerta_setor` | 3 |
| Dias de férias creditados a cada período aquisitivo (12 meses) | `dias_ferias_por_periodo` | 30 |
| Folga do 1º aviso de expiração (dias) | `folga_aviso_ferias_dias` | 15 |
| Enviar os avisos de férias a vencer | `aviso_ferias_ativo` | sim |
| Períodos não podem começar em feriado ou ponto facultativo cadastrado | `inicio_vedado_feriado` | não |
| Data em que abre o agendamento das férias do ano seguinte (vazio = sem a regra) | `abertura_agendamento_ferias` | vazio |

A leitura dos parâmetros traz também `membros_cgp` (só leitura): a quantidade de pessoas no setor da CGP. Com `0`, a tela Parâmetros alerta que os avisos destinados à CGP não chegam a ninguém.

## Feriados e pontos facultativos (`/api/rh/feriados`)

Cadastro manual da CGP (tabela `rh_feriados`, migração `9c5e7a1b3d4f`; serviço `servico_feriados.py`): uma data só pode ter um registro. Aparecem no calendário de férias, no eixo mensal do painel e na folha de ponto; com `inicio_vedado_feriado` ligado, férias e licença-prêmio não podem começar nessas datas (`400` "O período não pode começar em feriado ou ponto facultativo (03/11/2026: Descrição).").

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/rh/feriados?ano=` | Todos | `FeriadoLeitura[]` do ano, por data |
| `POST /api/rh/feriados` | CGP | `GravacaoFeriado` → `201 FeriadoLeitura`; `409 conflito` se a data já tem cadastro |
| `PUT /api/rh/feriados/{feriado_id}` | CGP | Altera → `FeriadoLeitura`; `409` se a nova data já tem cadastro; `404` se não existe |
| `DELETE /api/rh/feriados/{feriado_id}` | CGP | `204`; `404` se não existe |

- **`GravacaoFeriado`:** `data` (`AAAA-MM-DD`), `descricao` (1–200, sem só espaços), `tipo` (`feriado` \| `ponto_facultativo`), `abrangencia` (`nacional` \| `estadual` \| `municipal`, padrão `nacional`). Fora disso → `422`.
- **`FeriadoLeitura`:** os mesmos campos + `id`, `atualizado_por_nome`, `atualizado_em`.
- Os demais recebem `403 sem_permissao` nas gravações. Auditoria: `rh.feriados.criar`, `.alterar`, `.excluir`.
- `GET /afastamentos/meus` traz `feriados[]` do exercício, e o painel traz `feriados[]` da janela exibida.

**Sempre valem:**
- **Férias por período aquisitivo** (detalhes abaixo): o saldo é o do período em que as férias **começam**, vigente ou o próximo.
- **Licença-prêmio por exercício** (ano civil): o período precisa começar e terminar no mesmo ano; saldo = `saldo_lp_dias` (definido pela CGP) − dias dos pedidos pendentes, aprovados e gozados do exercício.
- Os saldos são independentes: um tipo não consome o outro.
- **Sem sobreposição** com outro afastamento ativo, de qualquer tipo.
- As mensagens de erro são claras: "Saldo de férias do período aquisitivo 15/03/2026 a 14/03/2027 insuficiente: 12 dia(s) disponível(is), pedido de 20", "O período de férias não pode começar numa segunda-feira" etc.

## Exercício e agendamento do próximo exercício

**Exercício = janela de gozo de 12 meses.** Quando o período aquisitivo do servidor vira (ex.: 31/12/2026), os 30 dias podem ser **agendados e usufruídos nos 12 meses seguintes** (01/01/2027 a 31/12/2027). Cada linha de `rh_periodos_aquisitivos` é essa janela: os dias entram no início dela, as férias debitam a janela em que **começam** e o saldo que sobra expira no fim. O `exercicio` é o ano em que cai a maior parte da janela (`servico_periodos.exercicio_do_periodo`: 31/12/2026 a 30/12/2027 = 2027; 15/03/2027 a 14/03/2028 = 2027) e vem em `PeriodoAtual`, `ProximoPeriodo` e `PeriodoLeitura`.

**Data de abertura** (`abertura_agendamento_ferias`, migração `c1f2a8d94e57`; só CGP/SuperRoot em Parâmetros). Vale quando a data cai na janela vigente do servidor (ex.: 15/10/2026, janela virando em 31/12/2026) e governa o **próximo exercício**:

- **Antes da data:** férias que começam no próximo exercício não podem ser agendadas (`400` "O agendamento das férias do exercício 2027 abre em 15/10/2026."). A CGP é isenta.
- **Depois da data:** qualquer servidor agenda até o crédito previsto (`dias_ferias_por_periodo`, 30) para o próximo exercício, **mesmo antes de o saldo ser implantado**. O pedido usa o saldo normal da janela (`creditados − usado`), então já **abate** quando o exercício começa; passar de 30 → `400` "Saldo de férias do período aquisitivo … insuficiente".
- **Com a janela nova em curso** a regra deixa de valer (`agendamento_antecipado = null`).
- **Sem o início do período aquisitivo informado** (`fallback`): vale o ano civil seguinte ao da data, com limite de 30 dias por ano e sem vínculo com período.
- `GET /afastamentos/meus` traz `agendamento_antecipado`: `exercicio`, `inicio`, `fim` (nulos no fallback), `abertura`, `aberto`, `limite_dias`, `agendados`.

## Período aquisitivo de férias (janela do exercício)

- A CGP informa, nos dados funcionais, o **início do período aquisitivo** só como dia e mês (`"DD/MM"`, ex.: `"15/03"`); ele se repete todo ano. Ver [rh-cadastro.md](rh-cadastro.md).
- Cada período dura **12 meses**: começa no dd/mm e termina na véspera do mesmo dd/mm do ano seguinte. 29/02 vira 28/02 nos anos comuns.
- No início de cada período entram `dias_ferias_por_periodo` dias (padrão 30) e o saldo não usado do período anterior **expira** (fica em `dias_expirados`).
- **Saldo do período** = dias creditados − dias das férias pendentes, aprovadas e gozadas que começam nele. Pedidos no **próximo** período usam o crédito previsto.
- Sem início informado, o pedido de férias é recusado: "A CGP ainda não informou o início do seu período aquisitivo…" (`400`).
- A CGP pode ajustar os dias creditados do período vigente (ex.: férias gozadas antes do sistema): `PUT /api/rh/cadastro/usuarios/{id}/periodo-vigente`.
- Tabela `rh_periodos_aquisitivos` (um registro por pessoa e período; `origem` = `automatico` ou `ajuste_cgp`); cada férias guarda o período em `rh_afastamentos.periodo_aquisitivo_id`.

**Aviso de férias a vencer** (e-mail oficial com brasão à pessoa, ao autorizador ou substituto e à CGP, enquanto houver saldo não agendado; tarefa diária das 07:00):
- **data-limite para começar** = fim do período − saldo não agendado + 1 (para caber todo o saldo);
- **data-limite para pedir** = data-limite para começar − `antecedencia_minima_dias`;
- **1º aviso** = data-limite para pedir − `folga_aviso_ferias_dias`, ou seja, cerca de saldo + antecedência + folga dias antes do fim do período;
- **lembrete** 7 dias antes da data-limite para pedir e **último aviso** na própria data-limite.
- Exemplo: período até 14/03/2027, 20 dias sem agendar, antecedência 30 e folga 15 → data-limite para começar 23/02/2027, para pedir 24/01/2027; 1º aviso em 09/01/2027 (64 dias antes do fim, contando o último dia do período como o 1º), lembrete em 17/01 e último aviso em 24/01.
- Cada aviso sai uma vez por período (chave `ferias-periodo:{usuario}:{inicio}:{marco}`); se a tarefa pular dias, sai só o marco mais recente.
- **Novo período:** a pessoa recebe "Novo período aquisitivo: N dias de férias disponíveis" (até 7 dias depois do início).

## Fluxo em duas etapas (ciente do superior e aprovação)

1. **Etapa 1: ciente e de acordo do superior imediato** (`gestor_id` do solicitante). Ao agendar ou alterar, só o superior recebe a mensagem e o e-mail "[Nome] agendou [férias/licença-prêmio]: ciente e de acordo". O pedido fica `pendente` com `aguarda_ciencia = true`.
   - **Ciente e de acordo** (`POST /afastamentos/{id}/ciencia`) **não aprova**: registra a ciência (`ciencia_por_nome`, `ciencia_em`, evento "Ciente e de acordo do superior imediato"), envia e-mail ao solicitante e libera o pedido.
   - O superior também pode **recusar** com justificativa (`/recusar`): o pedido encerra como `recusado`.
   - Só o superior imediato dá o ciente (nem o autorizador, a não ser que seja o superior, nem a CGP). Ninguém dá ciente ao próprio pedido (`403`).
2. **Etapa 2: aprovação.** Só depois do ciente o autorizador (ou substituto) e a CGP recebem o e-mail para aprovar ou recusar.
   - Aprovar antes do ciente devolve `409 aguarda_ciencia`. A CGP continua podendo decidir a qualquer momento.
   - **Etapa 1 dispensada:** o pedido vai direto à etapa 2 quando o solicitante não tem superior, o superior está inativo ou o superior já é o aprovador (autorizador ou substituto em exercício).
   - Alterar um pedido pendente reinicia o fluxo (novo ciente para as novas datas); alterar um aprovado cria um novo pedido que também começa pela etapa 1.
   - Lembrete de 3 dias: na etapa 1 vai só ao superior; na etapa 2, aos aprovadores e à CGP.

## Status

`pendente` (etapa 1, ciente do superior, e etapa 2, aprovação) → `aprovado` | `recusado`; `aprovado` → `cancelado` | `gozado`. O `gozado` é automático, pela tarefa diária das 07:00, depois do fim do período.

- **Alterar um pendente:** muda o próprio pedido.
- **Alterar um aprovado:** cria um novo pedido `pendente` com `substitui_id`. Ao ser aprovado, o anterior vira `cancelado`; se for recusado, o anterior continua aprovado.
- **Quem decide:**
  - o autorizador;
  - o **substituto**, se o autorizador tiver afastamento aprovado cobrindo hoje;
  - a CGP.
  - Ninguém decide o próprio pedido, exceto a CGP. A recusa exige justificativa.
- **Histórico:** cada mudança fica em `rh_afastamentos_eventos` (de → para, quem, quando, justificativa).
- **E-mails** (caixa de mensagens + fila de e-mail):
  - **ao agendar ou alterar:** autorizador (ou substituto) e CGP recebem "[Nome] agendou [férias/licença-prêmio] e aguarda aprovação". O aviso se encerra na decisão;
  - **a cada mudança de status** (aprovado, recusado com a justificativa, cancelado, gozado): o usuário recebe e-mail;
  - **ao cancelar** (`POST /afastamentos/{id}/cancelar`): além do dono do pedido, a **CGP** e o **superior imediato** recebem "Cancelamento: [Nome] cancelou [férias/licença-prêmio]" (mensagem e e-mail, com quem cancelou, o período e a justificativa); o **autorizador (ou substituto)** também, mas só se o pedido estava na etapa de aprovação (não na do ciente do superior nem já aprovado). Quem cancelou não recebe o aviso duplicado; os avisos de pedido pendente continuam sendo encerrados;
  - **pedido pendente há 3 dias:** lembrete aos aprovadores (tarefa diária).

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/rh/afastamentos/meus?exercicio=` | Todos | `MeusAfastamentos`: `periodo_vigente` (`PeriodoAtual`, nulo sem início informado), `proximo_periodo` (`ProximoPeriodo`), `saldos.licenca_premio` (`saldo`, `usado`, `disponivel`), `afastamentos[]` (com `eventos`) e `parametros` |
| `POST /api/rh/afastamentos/lancamento` | CGP | `LancamentoAfastamento` → `201 AfastamentoLeitura`: lança em nome do servidor (detalhes abaixo) |
| `GET /api/rh/relatorios/saldos?formato=xlsx\|pdf` | CGP | Relatório de saldos de todos os servidores (detalhes abaixo) |
| `POST /api/rh/afastamentos` | Todos | `{ "tipo", "inicio", "fim" }` → `201 AfastamentoLeitura`; `400` com a regra violada |
| `PUT /api/rh/afastamentos/{id}` | Dono (no prazo) ou CGP | Alteração (ver acima) |
| `POST /api/rh/afastamentos/{id}/cancelar` | Dono (no prazo) ou CGP | `{ "justificativa" }` opcional |
| `POST /api/rh/afastamentos/{id}/ciencia` | Superior imediato do solicitante | Etapa 1: ciente e de acordo (não aprova); `400` se o pedido não aguarda ciência; `403` para os demais |
| `POST /api/rh/afastamentos/{id}/aprovar` | Autorizador, substituto ou CGP | Aprova (`409 aguarda_ciencia` antes do ciente, exceto CGP) |
| `POST /api/rh/afastamentos/{id}/recusar` | Autorizador, substituto ou CGP; na etapa 1, também o superior imediato | `{ "justificativa" }` obrigatória (`400` sem ela) |
| `GET /api/rh/afastamentos/aprovacoes` | Todos | Pendentes que o usuário pode decidir ou aos quais pode dar o ciente (`pode_dar_ciencia`); CGP: todos |
| `GET /api/rh/afastamentos/painel` | Todos (escopo abaixo) | `visao=mensal\|anual`, `ano`, `mes`, `pessoa_id`, `setor_id`, `tipo` |
| `GET /api/rh/afastamentos/painel/exportar` | Todos (escopo abaixo) | Mesmos filtros + `formato=pdf\|xlsx` |
| `GET /api/rh/parametros` | Todos | Regras em vigor |
| `PUT /api/rh/parametros` | CGP | Grava as regras (`GravacaoParametros`); auditado como `rh.parametros` |

**`PeriodoAtual`:** `inicio`, `fim`, `dias_creditados`, `usado`, `disponivel`, `expira_em_dias`, `data_limite_inicio`, `data_limite_pedido` (nulas sem saldo) e `alerta_expiracao` (já na janela de aviso).

**`ProximoPeriodo`:** `inicio`, `fim`, `dias_creditados_previstos`, `usado` (férias já agendadas nele).

**`AfastamentoLeitura`:**
- identificação: `id`, `usuario_id`, `nome`, `setor` (o Departamento em vigor);
- período: `tipo`, `inicio`, `fim`, `dias`, `exercicio`;
- situação: `status`, `solicitado_em`, `decidido_por_nome`, `decidido_em`, `justificativa`, `substitui_id`;
- etapa 1: `aguarda_ciencia`, `ciencia_por_nome`, `ciencia_em`, `pode_dar_ciencia`;
- permissões: `pode_decidir`, `pode_alterar` (dono, pendente/aprovado, no prazo);
- `eventos[]`.

### Lançamento pela CGP

Para férias ou licença-prêmio já combinadas ou gozadas fora do sistema, inclusive retroativas.
- **`LancamentoAfastamento`:** `usuario_id`, `tipo`, `inicio`, `fim`, `situacao` (`aprovado` ou `gozado`), `justificativa` (3 a 2000) e `ignorar_saldo` (padrão `false`).
- **Não se aplicam:** antecedência mínima, dia vedado, mínimo de dias e início em feriado.
- **Continuam valendo:** a sobreposição com outro afastamento ativo e o saldo. As férias debitam o período aquisitivo que contém o início, mesmo anterior. `ignorar_saldo` lança mesmo sem saldo, por exemplo em períodos anteriores ao sistema.
- `gozado` só para períodos já encerrados (`400` caso contrário).
- O afastamento nasce decidido pela CGP. O histórico registra "Lançado pela CGP: [motivo]", o servidor recebe e-mail e a auditoria é `rh.afastamento.lancar`.
- Sem início do período aquisitivo (férias): `400`.

### Relatório de saldos (CGP)

Uma linha por servidor ativo, menos a conta root:
- servidor, login, setor e autorizador;
- período aquisitivo vigente: creditados, agendados, disponíveis, expira em e "pedir até";
- licença-prêmio do ano: saldo, usado e disponível.

Quem ainda não tem o início do período aquisitivo aparece como "não informado". Formatos XLSX (com observações) e PDF (paisagem). Serve para conferir a carga inicial e acompanhar os saldos.

### Painel

- **Escopo:**
  - CGP vê todos;
  - o autorizador vê os autorizados, mais os autorizados do titular que ele substitui enquanto o titular estiver afastado, e a si mesmo;
  - os demais, só a si.
- **Períodos exibidos:** pendentes, aprovados e gozados que cruzam a janela (o mês, ou o ano inteiro). Recusados e cancelados não aparecem, mas ficam no histórico.
- **Filtro de setor:** inclui os **setores filhos**, com os membros e quem tem um deles como Departamento.
- **`alertas[]`:** `{ setor, inicio, fim, pessoas }`, faixas de dias em que pelo menos `limite_alerta_setor` pessoas do mesmo setor estão afastadas.
- **`ferias_a_vencer[]`** (CGP e autorizadores, no escopo): `usuario_id`, `nome`, `setor`, `periodo_inicio`, `periodo_fim`, `disponivel`, `data_limite_pedido`. Quem tem saldo não agendado e período terminando em até 90 dias, pela data-limite para pedir.
- **Opções dos filtros:** `pessoas[]` (do escopo) e `setores[]` (hierarquia de Setores).
- **Exportação:**
  - **XLSX:** aba "Períodos" (nome, setor, tipo, início, fim, dias, status) e aba "Calendário" (grade por dia com F/LP; "?" = aguardando);
  - **PDF:** paisagem, com os períodos e os alertas de setor.

## Consumo no Angular (`features/rh/`, item "RH" em Módulos)

- **`/rh/ferias` (todos):**
  - cartões: férias disponíveis no período aquisitivo vigente (com a expiração), o próximo período e a licença-prêmio do exercício;
  - aviso amarelo "Peça até dd/mm/aaaa para não perder dias" quando `alerta_expiracao`;
  - calendário mês a mês do exercício: clicar no primeiro e no último dia abre "Deseja agendar férias ou licença-prêmio?", com o saldo de cada tipo (férias: o do período em que a seleção começa);
  - dias com afastamento em amarelo (aguardando) ou verde (aprovado), com a etiqueta F/LP;
  - lista dos pedidos com Alterar e Cancelar.
- **`/rh/painel-afastamentos` (CGP e autorizadores):**
  - fila "Aguardando sua aprovação" (Aprovar; Recusar com justificativa);
  - filtros e alertas de setor;
  - uma linha por período, "[F]/[LP] Nome – Setor", com faixa amarela (pendente) ou verde (aprovado), em visão mensal ou anual. **Cada faixa é clicável** e abre o detalhe (setor, período, situação, decisão, justificativa); se o usuário pode decidir o pedido, a janela traz **Aprovar** (verde) e **Recusar** (abre a justificativa);
  - na fila "Aguardando sua aprovação", o botão Aprovar é verde e o Recusar, vermelho claro;
  - bloco "Férias a vencer";
  - para a CGP: "Lançar afastamento" (`lancamento-afastamento.component.ts`) e "Relatório de saldos (Excel/PDF)";
  - exportação em PDF e Excel.
- **`/rh/parametros` (CGP):** edição das regras, com a fórmula do aviso explicada na tela e a caixa "Períodos não podem começar em feriado ou ponto facultativo".
- **`/rh/feriados` (todos; atalho "Feriados"):** lista do ano com dia da semana, tipo e abrangência; a CGP cadastra, edita e exclui em janela.
- **Destaques:** no calendário de férias, os feriados e pontos facultativos têm fundo azulado (descrição no título) e entram na legenda; no painel mensal, o dia fica marcado no eixo.

## Dados fictícios para demonstração

`scripts/dados-ficticios-rh.py` (na pasta `backend/`: `--criar`, `--remover`, ou sem opção para ver a situação) cria:
- 12 pessoas fictícias (login `ficticio.*`, nome "[FICTÍCIO] …", sem e-mail e sem senha) em setores reais;
- dados funcionais e pedidos aguardando aprovação, aprovados e gozados, com sobreposição num setor e férias a vencer.

A remoção apaga as pessoas fictícias e, em cascata, tudo o que é delas. Nenhum servidor real é tocado e nenhum e-mail é enviado.
