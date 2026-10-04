# Módulo Tarefas (`/api/tarefas`)

Tag no OpenAPI: **Módulo Tarefas**. Implementação:
- rotas: `backend/app/api/routes/tarefas.py`;
- regras: `backend/app/services/tarefas/servico_tarefas.py`;
- modelos: `backend/app/models/tarefas.py` (migração `2320f1538b36`).

Reconstrução, no SGI SPI, do app de tarefas do 10.23.1.220, com pipeline de validação, linha do tempo detalhada e avisos pela mensageria. Todas as rotas exigem login (perfil em dia); as permissões por tarefa e por equipe são conferidas no servidor.

## Papéis

| Papel | Quem |
|---|---|
| **Envolvidos** | Responsável e participantes. Executam a tarefa; a carga conta para cada um |
| **Liderança** | Dono e líderes da equipe da tarefa **e das equipes acima dela** (equipe pai), além do SuperRoot. Numa tarefa sem equipe, quem a criou |
| **Criador** | Quem cadastrou |
| **Membros da equipe** | Veem as tarefas da equipe |

Quem não tem relação com a tarefa recebe **404** (o sistema não revela que ela existe).

## Pipeline

`a_fazer` → `em_andamento` → `em_validacao` → `concluida` (`POST /{numero}/mover`, campo `acao`):

| Ação | De → Para | Quem | Observação |
|---|---|---|---|
| `iniciar` | a_fazer → em_andamento | envolvidos, liderança | |
| `pausar` | em_andamento → a_fazer | envolvidos, liderança | |
| `entregar` | em_andamento → em_validacao | envolvidos, liderança | comentário opcional em `texto`; **sem equipe, vai direto a concluída** |
| `validar` | em_validacao → concluida | liderança | |
| `devolver` | em_validacao → em_andamento | liderança | **`texto` (motivo) obrigatório** |
| `concluir` | a_fazer/em_andamento → concluida | liderança | |
| `reabrir` | concluida → em_andamento | liderança | **`texto` (motivo) obrigatório** |

- O detalhe traz `acoes`: as ações permitidas ao usuário agora. A tela mostra só essas. Fora delas: `403 sem_permissao`.
- `versao`, opcional em todas as gravações, evita sobrescrever alteração de outra pessoa (`409 conflito`).
- O tempo em andamento é acumulado (`segundos_em_andamento`).

## Regras

- **Prazo:** só por `POST /{numero}/prazo`, com **justificativa obrigatória**. O `prazo_original` fica guardado, e `prorrogacoes` conta as mudanças.
- **Atribuição:** numa equipe, responsável e participantes são membros ou liderança da equipe. A liderança pode incluir qualquer usuário ativo.
- **Transferência:** para membro da equipe (a liderança, para qualquer usuário ativo), com justificativa e novo prazo opcional. O responsável anterior deixa de ser envolvido.
- **Comentários e anexos:** até 5 arquivos por vez, conferidos pelo conteúdo (PDF, DOCX/XLSX/PPTX, ODT/ODS/ODP, DOC/XLS/PPT, TXT, CSV, PNG, JPG), no limite `ANEXOS_TAMANHO_MAXIMO_MB`. Permitidos também em tarefa concluída.
- **Linha do tempo:** só cresce. Remoção lógica apenas pelo SuperRoot, com motivo registrado (`removido`).
- **Carga:** peso da prioridade (baixa 1, normal 3, alta 5, crítica 8) × urgência do prazo (atrasada 4; menos de 3 dias 3; até 7 dias 2; até 15 dias 1,5; mais 1). Só contam `a_fazer` e `em_andamento`.
  - Faixas: até 20 baixa ocupação; até 40 moderada; até 60 alta; acima, sobrecarga crítica.
- **Exclusão:** quem criou ou a liderança.

## Avisos (caixa de mensagens + e-mail oficial)

| Quando | Para | Chave |
|---|---|---|
| Tarefa criada | envolvidos (menos o autor) | `tarefa-criada:{id}` |
| Participante incluído | quem entrou | `tarefa-participante:{id}:{versao}` |
| Prazo alterado | envolvidos | `tarefa-prazo:{id}:{versao}` |
| Transferida | novo responsável | `tarefa-transferida:{id}:{versao}` |
| **Entregue para validação** | liderança (pendência, encerrada ao validar ou devolver) | `tarefa-validacao:{id}:{versao}` |
| Validada / devolvida (com motivo) / reaberta | envolvidos | `tarefa-validada:…`, `tarefa-devolvida:…`, `tarefa-reaberta:…` |
| Concluída pela liderança | envolvidos e liderança | `tarefa-concluida:{id}:{versao}` |
| Comentário | envolvidos e criador (menos o autor) | `tarefa-comentario:{evento}` |
| Vence amanhã / atrasada (timer das 07:00) | envolvidos | `tarefa-prazo-aviso:{id}:…` |
| Validação parada há 2+ dias (timer) | liderança, **em janela modal que não bloqueia** | `tarefa-validacao-parada:{id}:{versao}` |

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /api/tarefas` | `ListaTarefas`. `escopo`: `minhas` (padrão), `equipe` (`equipe_id`) ou `pessoa` (`login`). Filtros: `status` (repetível), `prioridade`, `marcador_id`, `responsavel_id`, `busca` (título, descrição ou número). Os indicadores são do escopo inteiro |
| `POST /api/tarefas` | `NovaTarefa` → `201 TarefaDetalhe` |
| `POST /api/tarefas/com-anexos` | `multipart/form-data`: `dados` (JSON de `NovaTarefa`, como texto) e até 5 `arquivos` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG) → `201 TarefaDetalhe`. Os arquivos ficam anexados ao evento "Tarefa criada" da linha do tempo e o aviso aos envolvidos informa a quantidade. Arquivo recusado (tipo, tamanho ou vazio) ou mais de 5 → `400` e **nenhuma tarefa é criada**; `dados` inválido → `422`. Mesmas regras de permissão do `POST /api/tarefas` |
| `GET /api/tarefas/{numero}` | `TarefaDetalhe` |
| `PUT /api/tarefas/{numero}` | `EdicaoTarefa`: título, descrição, prioridade, participantes, marcadores |
| `POST /api/tarefas/{numero}/prazo` | `{prazo, justificativa, versao?}` |
| `POST /api/tarefas/{numero}/mover` | `{acao, texto?, versao?}` |
| `POST /api/tarefas/{numero}/transferir` | `{para_id, justificativa, novo_prazo?, versao?}` |
| `POST /api/tarefas/{numero}/comentarios` | `multipart/form-data`: `texto` e/ou `arquivos` → `201 EventoLeitura` |
| `GET /api/tarefas/{numero}/linha-do-tempo` | `LinhaDoTempo {total, itens, tem_mais}`. `filtro`: comentarios, anexos, status, prazos, atribuicoes; `antes_de` + `limite` (padrão 30) para "carregar mais" |
| `GET /api/tarefas/{numero}/anexos/{anexo_id}` | Download (confere a permissão na tarefa) |
| `POST /api/tarefas/{numero}/eventos/{evento_id}/remover` | SuperRoot: `{motivo}` |
| `POST /api/tarefas/{numero}/checklist` | `{acao: incluir\|marcar\|remover, texto?, item_id?}` |
| `DELETE /api/tarefas/{numero}` | `204` |
| `POST /api/tarefas/ordem` | `{numeros: [...]}`: ordem manual (arrastar); ignora o que o usuário não pode editar |
| `GET /api/tarefas/pessoas` | `PessoaCarga[]`: carga, faixa, a fazer, em andamento e atrasadas de **todas** as tarefas da pessoa. Com `equipe_id`, os membros e a liderança da equipe, mais `na_equipe` (`a_fazer`, `em_andamento`, `em_validacao`, `concluidas`, `atrasadas` só das tarefas da equipe); sem, busca (`busca`, até 20) e `na_equipe` nulo |
| `GET /api/tarefas/pessoas/{usuario_id}/agenda` | `AgendaPessoa`: painel que aparece ao escolher responsável ou participantes. Traz `pessoa` (como em `PessoaCarga`), `de`, `ate` e `itens[]` (`ItemAgenda`: `numero`, `titulo`, `status`, `prioridade`, `inicio` = 1ª vez em andamento ou criação, `prazo`, `concluida_em`, `atrasada`, `equipe`, `papel` = `responsavel`/`participante`, `abrivel`). Entram **todas** as tarefas abertas da pessoa e as concluídas no período `de`–`ate` (padrão: 30 dias antes a 60 dias depois de hoje). **Aberto a qualquer usuário logado, com os títulos**: por decisão do usuário, quem atribui vê a agenda completa de quem recebe. `abrivel` diz se quem consulta pode abrir a tarefa. `400` se `de` > `ate`; `404` se a pessoa não existe |
| `GET /api/tarefas/relatorio` | Arquivo XLSX (abas **Tarefas** e **Por pessoa**) ou PDF (resumo, pessoas, lista). `formato` (`xlsx` padrão ou `pdf`), `escopo`/`equipe_id`/`login` (mesmas permissões da lista), `marcador_id`, `de` e `ate` (aaaa-mm-dd). Entram as tarefas ativas no período: criadas até `ate` e abertas ou concluídas a partir de `de`. `400` se `de` > `ate` |
| `GET /api/tarefas/equipes` | `EquipeLeitura[]` visíveis (membro ou liderança; SuperRoot: todas), com indicadores, `lider` e `pode_configurar` |
| `POST /api/tarefas/equipes` | `GravacaoEquipe` → `201`: quem cria é o dono |
| `PUT /api/tarefas/equipes/{equipe_id}` | Dono ou SuperRoot |
| `DELETE /api/tarefas/equipes/{equipe_id}` | Desativa (dono ou SuperRoot); `400` com tarefas em aberto |
| `GET` / `POST /api/tarefas/equipes/{equipe_id}/marcadores` | Marcadores da equipe e globais; criar: liderança (`409` se o nome repetir) |
| `DELETE /api/tarefas/marcadores/{marcador_id}` | Liderança da equipe do marcador |

**`TarefaResumo`:**
- identificação: `numero`, `titulo`, `status`, `prioridade`, `equipe`, `responsavel`, `participantes` (quantos, além do responsável), `marcadores`;
- prazo: `prazo`, `prazo_original`, `prorrogacoes`, `atrasada`;
- pessoas: `envolvidos` (responsável primeiro e depois os participantes, para os avatares);
- andamento: `checklist_feitos`/`checklist_total`, `comentarios` e `anexos` (sem os removidos), `carga`, `ordem`;
- datas: `criado_em`, `iniciada_em` (1ª vez em andamento), `concluida_em` e `atualizado_em`.

**`TarefaDetalhe`** acrescenta:
- `descricao`, `criado_por`, `pessoas`, `checklist[]`;
- **`etapas[]`**: para cada etapa do pipeline, `rotulo`, `em` (quando chegou), `por`, `atual` e `alcancada`;
- `segundos_em_andamento`, `versao` e `acoes`.

**`EventoLeitura`:** `tipo`, `titulo`, `texto`, `dados`, `autor`, `criado_em`, `anexos[]` e `removido`/`motivo_remocao`.
- Tipos: `criada`, `editada`, `status`, `entregue`, `validada`, `devolvida`, `reaberta`, `prazo`, `transferida`, `comentario`, `checklist`, `removido`.
- `dados` traz `de`/`para` (status ou nomes), `para` do prazo e `campos` da edição.

## Migração do 10.23.1.220

Scripts em `scripts/` (o 10.23.1.220 só é lido, numa transação read only):

```bash
SGI_SENHA=... backend/.venv/bin/python scripts/extrair-tarefas-sgi.py <pacote>      # CSVs, anexos (SHA-256) e usuarios.csv sem senhas
cd backend && .venv/bin/python ../scripts/migrar-tarefas-sgi.py <pacote>           # ensaio: carrega, confere e desfaz
cd backend && .venv/bin/python ../scripts/migrar-tarefas-sgi.py <pacote> --gravar  # grava (--substituir recarrega o mesmo pacote)
```

| SGI (10.23.1.220) | Aqui |
|---|---|
| `Pending` / `InProgress` / `Completed` (eventos antigos: `AwaitingApproval`, 0–3) | `a_fazer` / `em_andamento` / `concluida` (`em_validacao`) |
| `Low` / `Normal` / `High` / `Critical` | `baixa` / `normal` / `alta` / `critica` |
| `Number` | `numero` (preservado; tarefa criada aqui com o mesmo número recebe o próximo livre) |
| participante único | `responsavel_id` e participante |
| `Created`, `Edited`, `DeadlineChanged`, `StatusChanged`, `Reopened`, `Transferred`, `CommentAdded`, `ContentRemoved` | `criada`, `editada`, `prazo`, `status`, `reaberta`, `transferida`, `comentario`, `removido` (autor com o nome da época) |
| primeiro "anterior" de mudança de prazo | `prazo_original` |
| marcadores (globais) | marcadores globais (`equipe_id` nulo) |
| usuário sem conta aqui | criado inativo, sem senha |

- Na edição, o SGI só gravava os valores novos: o "de" vem da edição anterior (na primeira, a linha do tempo mostra só o valor novo).
- Nenhum aviso ou e-mail é disparado pela carga. A conferência compara as contagens por tabela, a situação e o número de cada tarefa; divergência impede gravar.
- Carga de 29/09/2026: 159 tarefas (35 a fazer, 15 em andamento, 109 concluídas), 971 eventos, 66 anexos, 5 equipes (2 desativadas), 20 marcadores.

## Consumo no Angular

Código em `frontend/src/app/features/tarefas/`: rotas em `tarefas.routes.ts`, chamadas em `tarefas-api.service.ts`, tipos e funções das visões em `tarefas.models.ts`.

Todas as telas ficam dentro da **casca do módulo** (`modulo-tarefas.component.ts`). Ela tem uma navegação lateral própria, no estilo dos espaços do Trello/ClickUp:
- "+ Nova tarefa";
- Minhas tarefas;
- **Para validar** (liderança), com o total de entregas pendentes;
- a árvore de **equipes** (subequipes recuadas), com as tarefas em aberto e as entregas a validar;
- "+ Nova equipe".

Ela é recolhível, e a preferência fica no navegador. A barra lateral do sistema continua com um só item "Tarefas".

| Tela | Rota | Endpoints |
|---|---|---|
| Espaço: Minhas tarefas / equipe / pessoa | `/tarefas`, `/tarefas/equipes/:equipeId`, `/tarefas/pessoas/:login` | `GET /api/tarefas` (uma carga; filtros aplicados na tela), `POST /api/tarefas` (criação rápida), `POST /ordem`, `POST /{numero}/mover`, `POST /{numero}/prazo`, `GET /pessoas?equipe_id=` (visão Pessoas e raias) |
| Janela da tarefa | `?tarefa=<número>` sobre qualquer visão | `GET /{numero}`, `PUT`, `DELETE`, `/prazo`, `/mover`, `/transferir`, `/comentarios`, `/linha-do-tempo`, `/anexos/{id}`, `/eventos/{id}/remover`, `/checklist`, `GET /equipes/{id}/marcadores` |
| Link antigo | `/tarefas/:numero` (e-mails e avisos) | Redireciona para `/tarefas?tarefa=<número>` |
| Nova tarefa | `/tarefas/nova` (`?equipe=<id>` já escolhe a equipe) | `GET /equipes`, `GET /pessoas?equipe_id=`, `GET /pessoas?busca=`, `GET /pessoas/{id}/agenda`, `GET /equipes/{id}/marcadores`, `POST /api/tarefas` |
| Equipes (visão geral) | `/tarefas/equipes` | `GET /equipes` |
| Configurar equipe | `/tarefas/equipes/nova/configurar`, `/tarefas/equipes/:equipeId/configurar` | `POST`/`PUT`/`DELETE /equipes`, `GET`/`POST /equipes/{id}/marcadores`, `DELETE /marcadores/{id}` |
| Relatório (janela no espaço) | qualquer espaço | `GET /relatorio` |

**Espaço** (`espaco-tarefas.component.*`). Estado na URL:
- `visao`: vazio = **Quadro** (padrão), `lista`, `calendario` ou `pessoas` (liderança da equipe);
- filtros: `pessoas` (ids separados por vírgula, escolhidos nos avatares: clique filtra, Shift+clique soma), `busca`, `prioridade`, `marcador` e `recorte` (`atrasadas`, `hoje`, `semana`, `validacao` ou `criticas`, também escolhido na linha de resumo);
- `raias=pessoa`: quadro agrupado por responsável;
- `ordem` (`prazo` ou `prioridade`; vazio = manual), na lista;
- `tarefa`: a tarefa aberta na janela. Abrir empilha no histórico: o "voltar" do navegador fecha a janela.

**Visões:**
- **Quadro** (`quadro-tarefas.component.ts`, `cartao-tarefa.component.ts`):
  - colunas A fazer, Em andamento, Em validação e Concluída;
  - a Concluída mostra as 10 mais recentes, com "ver todas", e pode ser recolhida;
  - o cartão traz as etiquetas (marcadores), o título, o chip do prazo (vermelho se atrasado, âmbar se vence hoje ou amanhã), o checklist, os comentários, os anexos, o número e os avatares de `envolvidos`, com a borda da prioridade;
  - arrastar entre colunas ou usar o menu "⋯" vira a `acao` do pipeline (Em validação → Em andamento = `devolver`, que pede o motivo). O servidor decide e, em `403`, o cartão volta;
  - **"+ Adicionar tarefa"** na coluna A fazer (fora da tela de outra pessoa) cria só com o título. Padrões: responsável = quem cria, prioridade normal, prazo em 7 dias às 18:00, equipe do quadro (em Minhas tarefas, pessoal);
  - em raias, cada responsável ganha uma linha com a carga.
- **Lista** (`lista-tarefas.component.ts`): seções recolhíveis por situação, estilo Asana (a Concluída começa fechada), com a ordem manual por arraste dentro da seção.
- **Calendário** (`calendario-tarefas.component.ts`): mês ou semana, com as tarefas no dia do prazo. Arrastar para outro dia abre "Alterar prazo" já com o novo dia, e a justificativa continua obrigatória.
- **Pessoas:** cartões com a carga e as barras por situação na equipe.

**Janela da tarefa** (`janela-detalhe-tarefa.component.*`):
- à esquerda: título editável no lugar, descrição, checklist e atividade (comentário com anexos e linha do tempo com filtros);
- à direita: situação e ações (só as de `acoes`), responsável (Transferir), participantes, prazo (Alterar), prioridade, marcadores, carga e dados;
- cada propriedade é gravada sozinha pelo `PUT`, com `versao`.

**Agenda da pessoa** (`agenda-pessoa.component.ts`, `GET /pessoas/{id}/agenda`):
- aparece ao escolher o responsável ou os participantes na Nova tarefa, ao editar participantes na janela e na transferência;
- mostra a carga e as tarefas da pessoa em **Lista** (por situação) ou **Linha do tempo** (Gantt de 4 semanas, com a marca de hoje);
- a aba escolhida fica guardada no navegador.

## Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Regra violada: justificativa ou motivo vazio, pessoa fora da equipe, formato de arquivo, equipe com tarefas abertas |
| `403` | `sem_permissao` | Ação fora do papel ou da etapa |
| `403` | `tarefa_concluida` | Alterar prazo, editar ou transferir uma tarefa já concluída (a mensagem orienta a liderança a reabri-la). A tela se atualiza sozinha ao receber `403`/`409` e ao voltar para a aba |
| `404` | `nao_encontrado` | Tarefa, equipe ou anexo inexistente, ou sem permissão para ver |
| `409` | `conflito` | `versao` desatualizada ou marcador repetido |
| `422` | `validacao` | Campos fora do formato |
