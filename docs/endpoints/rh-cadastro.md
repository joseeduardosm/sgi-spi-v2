# Módulo RH: atualização cadastral validada pela CGP (`/api/rh/cadastro`, `/api/rh/papeis`)

Tag no OpenAPI: **Módulo RH**. Implementação:
- rotas: `backend/app/api/routes/rh.py`;
- regras: `backend/app/services/rh/servico_cadastro.py`;
- papéis: `backend/app/services/rh/papeis.py`;
- modelos: `backend/app/models/rh.py` (`rh_alteracoes_cadastrais`, `rh_dados_funcionais`).

## Papéis

| Papel | Quem |
|---|---|
| **CGP** (Coordenadoria de Gestão de Pessoas) | SuperRoot; membro do setor `SETOR_CGP` (padrão "Coordenadoria de Gestão de Pessoas") ou de um setor filho; ou com um deles como Departamento **em vigor** (validado). Acesso total ao RH |
| **Autorizador** | Quem a CGP definiu em `rh_dados_funcionais.autorizador_id` de alguém (ou é substituto de um autorizador) |
| **Usuário** | Todo usuário autenticado: atualiza o próprio cadastro e agenda os próprios afastamentos |

`GET /api/rh/papeis` → `{ "cgp": bool, "autorizador": bool }`. O Angular usa esse retorno para mostrar os atalhos do módulo.

## Fluxo

1. **Confirmação mensal:** uma vez por mês civil, o usuário confirma ou atualiza o perfil (`PUT /api/autenticacao/perfil`; ver [autenticacao.md](autenticacao.md)). Até confirmar, só "Meu perfil" funciona (`403 revisao_perfil_obrigatoria`). Não há e-mail de cobrança.
2. **Alteração pendente:**
   - cada campo alterado vira uma `AlteracaoCadastral` com status `pendente`, e os valores em vigor continuam os anteriores;
   - uma nova proposta para o mesmo campo substitui a pendente (`substituida`).
   - Todos da CGP recebem na caixa de mensagens, com e-mail: "[Nome] alterou seu cadastro e aguarda validação da CGP".
3. **Análise da CGP:**
   - **validar:** o valor proposto passa a valer, e o campo exibe "Validado por [nome] em [data]";
   - **recusar:** a CGP informa a **justificativa** e a **correção**. A correção passa a valer, e o usuário recebe um e-mail com a justificativa e a correção.
4. **Histórico:** todas as alterações ficam em `rh_alteracoes_cadastrais`, com quem alterou, o quê, quando, e quem validou ou corrigiu.

**Superior imediato (`gestor_id`):**
- obrigatório, exceto para a conta root (login `LOGIN_ADMIN`) e para quem a CGP marcar como **topo da hierarquia** (`sem_superior`);
- não pode ser o próprio usuário nem formar ciclo (A superior de B e B superior de A, direta ou indiretamente).
- A regra vale também na validação, na correção da CGP e na edição pela tela de Usuários.

**Valores no histórico:** texto. O superior imediato é guardado pelo `id` do usuário e as datas em `AAAA-MM-DD`. Os campos `*_rotulo` trazem o valor para exibir (nome do superior, data em dd/mm/aaaa).

## Endpoints (só CGP; os demais recebem `403 sem_permissao`)

| Método e caminho | Descrição |
|---|---|
| `GET /api/rh/cadastro/pendencias` | `UsuarioPendente[]`: `usuario_id`, `nome`, `login`, `departamento`, `alteracoes[]` pendentes |
| `GET /api/rh/cadastro/usuarios/{usuario_id}` | `CadastroRh`: `perfil` (valores em vigor para exibir), `pendentes[]`, `historico[]`, `funcionais` |
| `POST /api/rh/cadastro/alteracoes/{alteracao_id}/validar` | Valida → `CadastroRh`. `400` se já analisada; `404` se não existe |
| `POST /api/rh/cadastro/alteracoes/{alteracao_id}/recusar` | `{ "justificativa": "…", "valor_corrigido": "…" }` → `CadastroRh`. Justificativa obrigatória (`422`); correção conferida (e-mail válido, data `AAAA-MM-DD`, superior sem ciclo) |
| `POST /api/rh/cadastro/alteracoes/validar-lote` | `{ "ids": [...] }` (1 a 1000) → `ResultadoValidacaoLote` `{ validadas, erros: [{ id, detalhe }] }`. Cada alteração é validada à parte: a que não puder (já analisada, superior em ciclo) volta em `erros` sem impedir as demais |
| `PUT /api/rh/cadastro/usuarios/{usuario_id}/funcionais` | Dados funcionais (abaixo) → `CadastroRh` |
| `GET /api/rh/cadastro/funcionais/importacao/modelo` | Planilha XLSX com todos os servidores ativos (menos a conta root) e os valores atuais, mais a aba "Instruções" |
| `POST /api/rh/cadastro/funcionais/importacao/previa` | `multipart/form-data` (`arquivo` .xlsx) → `ResultadoImportacaoRh`, sem gravar |
| `POST /api/rh/cadastro/funcionais/importacao` | Mesma planilha → grava tudo numa transação **só se não houver nenhum erro** (senão `400`, nada gravado) |
| `PUT /api/rh/cadastro/usuarios/{usuario_id}/periodo-vigente` | `{ "dias_creditados": 0..365 }` → `CadastroRh`. Ajusta os dias do período aquisitivo vigente (origem `ajuste_cgp`); `400` sem início informado. Auditado como `rh.ferias.ajuste_periodo` |

**`AlteracaoLeitura`:**
- `id`, `campo`, `rotulo`;
- `valor_anterior`/`_rotulo`, `valor_proposto`/`_rotulo`;
- `status` (`pendente`, `validada`, `recusada` ou `substituida`);
- `solicitada_em`, `solicitada_por_nome`;
- `analisada_por_nome`, `analisada_em`, `justificativa`, `valor_corrigido`/`_rotulo`.

### Dados funcionais (exclusivos da CGP, invisíveis ao usuário)

`GravacaoDadosFuncionais`:

| Campo | Descrição |
|---|---|
| `autorizador_id` | Autorizador de férias e licença-prêmio. A leitura traz `autorizador_sugerido_id` = superior imediato em vigor |
| `substituto_id` | Aprova no lugar **deste** usuário (como autorizador) quando ele estiver afastado. Sem substituto, só a CGP |
| `sem_superior` | Topo da hierarquia: dispensa o superior imediato |
| `inicio_periodo_aquisitivo` | Início do período aquisitivo de férias, `"DD/MM"` (ex.: `"15/03"`; 29/02 aceito; `null` = não informado). Data inválida → `422`. Ver [rh-afastamentos.md](rh-afastamentos.md) |
| `exercicio` | Ano a que o saldo de licença-prêmio se refere (ano civil) |
| `saldo_lp_dias` | Saldo de licença-prêmio (0 a 365) |
| `jornada_semanal_horas` | Jornada de trabalho em horas semanais (1 a 80; ex.: `40`) |
| `regime_plantao` | Regime de plantão (`true`/`false`) |
| `horario_trabalho_inicio`, `horario_trabalho_fim` | Horário de trabalho, `"HH:MM"` (ex.: `"09:00"` e `"18:00"`). Os dois ou nenhum; o fim pode ser menor que o início (plantão noturno), mas não igual |
| `horario_estudante` | Horário de estudante (`true`/`false`) |
| `intervalo_inicio`, `intervalo_fim` | Intervalo de almoço e descanso, `"HH:MM"`. Os dois ou nenhum; o fim depois do início |
| `rg_cin` | Nº do RG ou da CIN (até 30; dígitos, letras, ponto, hífen, barra e espaço; ex.: `"12.345.678-9"`) |
| `rs_pv` | Nº do RS/PV (mesmas regras; ex.: `"1.234.567/8"`) |

Jornada, horários e documentos alimentam o cabeçalho da folha de ponto ([rh-folha-ponto.md](rh-folha-ponto.md)). Sem jornada, horário de trabalho, intervalo, RG/CIN ou RS/PV, o usuário não consegue gerar a folha e a CGP é avisada; gravar os dados completos encerra esse aviso. Violações das regras acima → `422 validacao`. A leitura devolve os horários como `"HH:MM"`.

A leitura (`funcionais` em `CadastroRh`) traz também `periodos[]` (`PeriodoLeitura`: `inicio`, `fim`, `dias_creditados`, `usado`, `disponivel`, `dias_expirados`, `origem`, `vigente`), do mais recente ao mais antigo. O antigo `saldo_ferias_dias` deixou de existir: as férias seguem o período aquisitivo.

- O autorizador e o substituto não podem ser o próprio usuário e precisam estar ativos (`400`).
- Operação auditada como `rh.cadastro.funcionais`.

### Carga em lote dos dados funcionais (planilha)

- **Colunas:** Login (obrigatório; identifica a linha), Nome e Setor (informativos), Autorizador (login), Substituto (login), Topo da hierarquia (Sim/Não), Início do período aquisitivo (dd/mm), Dias disponíveis no período vigente, Exercício da LP, Dias de LP, Jornada (horas/semana), Regime de plantão (Sim/Não), Horário de trabalho ("9:00 às 18:00"), Horário de estudante (Sim/Não), Intervalo de almoço e descanso ("12:00 às 13:00"), RG/CIN nº e RS/PV nº.
- **Célula vazia mantém o valor atual**: a planilha nunca apaga dados. Reenviar o modelo sem mexer não altera ninguém.
- **Dias disponíveis no período vigente:** ajusta os dias creditados do período para que sobrem exatamente esses dias, descontando o que já está agendado no sistema (origem `ajuste_cgp`). Só conta como alteração se diferir do saldo atual ou se o início do período mudar.
- **Validações:** as mesmas da tela (logins existentes e ativos, ninguém autorizador de si mesmo, dd/mm válido, horários em pares, jornada de 1 a 80, documentos). Os erros vêm por linha na prévia.
- **`ResultadoImportacaoRh`:** `total`, `com_mudanca`, `com_erro`, `gravado` e `linhas[]` (`linha`, `login`, `nome`, `mudancas[]`, `erros[]`).
- **Auditoria:** `rh.cadastro.funcionais` por servidor, `rh.ferias.ajuste_periodo` quando há dias disponíveis e `rh.cadastro.funcionais_lote` do lote.

## Consumo no Angular

- **Meu perfil** (`/perfil`):
  - modal bloqueante "Confirme ou atualize seus dados" no mês pendente, com os botões "Meus dados estão corretos" e "Revisar e atualizar";
  - "Superior imediato" obrigatório;
  - selo por campo: "Pendente de validação da CGP: …" ou "Validado/Corrigido por … em …";
  - os campos pendentes aparecem com o valor proposto, de modo que confirmar de novo mantém a proposta.
- **Validações** (`/rh/validacoes`, só CGP):
  - botão "Importar planilha de dados funcionais" (`importacao-funcionais.component.ts`): baixar o modelo, escolher a planilha (a prévia sai na hora) e importar, só sem erros;
  - validação em lote: filtro por campo (ex.: só "Departamento", com a quantidade), caixas por usuário, "Marcar todos" e "Validar selecionadas (N)"; no cadastro aberto, "Validar todas deste usuário";
  - lista de pendências e busca de qualquer usuário;
  - comparação em vigor × proposto com Validar e Recusar (justificativa + correção);
  - dados funcionais (o autorizador vem pré-selecionado com o superior imediato);
  - histórico.
- **Usuários** (página `/usuarios/:id`, com a conta e o perfil à esquerda e o RH à direita; o "Salvar usuário" grava também os dados funcionais e o ajuste do período, sem botões próprios no bloco): o mesmo bloco de dados funcionais (com o início do período aquisitivo em dd/mm, o período vigente, o ajuste e o histórico) (`features/rh/dados-funcionais.component.ts`), visível só para a CGP e o SuperRoot (a API responde `403` aos demais e o bloco não aparece), com gravação própria e o link para as pendências do usuário.
- **Serviço:** `features/rh/rh-api.service.ts`.
