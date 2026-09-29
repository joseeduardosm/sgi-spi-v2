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
| `GET /api/tarefas/pessoas` | `PessoaCarga[]` (carga, faixa, a fazer, em andamento, atrasadas). Com `equipe_id`, a equipe; sem, busca (`busca`, até 20) |
| `GET /api/tarefas/equipes` | `EquipeLeitura[]` visíveis (membro ou liderança; SuperRoot: todas), com indicadores, `lider` e `pode_configurar` |
| `POST /api/tarefas/equipes` | `GravacaoEquipe` → `201`: quem cria é o dono |
| `PUT /api/tarefas/equipes/{equipe_id}` | Dono ou SuperRoot |
| `DELETE /api/tarefas/equipes/{equipe_id}` | Desativa (dono ou SuperRoot); `400` com tarefas em aberto |
| `GET` / `POST /api/tarefas/equipes/{equipe_id}/marcadores` | Marcadores da equipe e globais; criar: liderança (`409` se o nome repetir) |
| `DELETE /api/tarefas/marcadores/{marcador_id}` | Liderança da equipe do marcador |

**`TarefaResumo`:**
- identificação: `numero`, `titulo`, `status`, `prioridade`, `equipe`, `responsavel`, `participantes` (quantos, além do responsável), `marcadores`;
- prazo: `prazo`, `prazo_original`, `prorrogacoes`, `atrasada`;
- andamento: `checklist_feitos`/`checklist_total`, `carga`, `ordem`, `atualizado_em`.

**`TarefaDetalhe`** acrescenta:
- `descricao`, `criado_por`, `criado_em`, `pessoas`, `checklist[]`;
- **`etapas[]`**: para cada etapa do pipeline, `rotulo`, `em` (quando chegou), `por`, `atual` e `alcancada`;
- `segundos_em_andamento`, `versao` e `acoes`.

**`EventoLeitura`:** `tipo`, `titulo`, `texto`, `dados`, `autor`, `criado_em`, `anexos[]` e `removido`/`motivo_remocao`.
- Tipos: `criada`, `editada`, `status`, `entregue`, `validada`, `devolvida`, `reaberta`, `prazo`, `transferida`, `comentario`, `checklist`, `removido`.
- `dados` traz `de`/`para` (status ou nomes), `para` do prazo e `campos` da edição.

## Consumo no Angular

Código em `frontend/src/app/features/tarefas/` (rotas em `tarefas.routes.ts`, chamadas em `tarefas-api.service.ts`, tipos em `tarefas.models.ts`):

| Tela | Rota | Endpoints |
|---|---|---|
| Minhas tarefas / equipe / pessoa | `/tarefas`, `/tarefas/equipes/:equipeId`, `/tarefas/pessoas/:login` | `GET /api/tarefas` (uma carga, filtros aplicados na tela), `POST /ordem`, `POST /{numero}/mover` (Kanban) |
| Nova tarefa | `/tarefas/nova` (`?equipe=<id>` já escolhe a equipe) | `GET /equipes`, `GET /pessoas?equipe_id=`, `GET /equipes/{id}/marcadores`, `POST /api/tarefas` |
| Detalhe | `/tarefas/:numero` | `GET /{numero}`, `PUT`, `DELETE`, `/prazo`, `/mover`, `/transferir`, `/comentarios`, `/linha-do-tempo`, `/anexos/{id}`, `/eventos/{id}/remover`, `/checklist` |

- Estado da lista na URL: `visao=kanban`, `status` (lista separada por vírgula ou `todas`; vazio = em aberto e em validação), `prioridade`, `marcador`, `responsavel`, `busca`, `recorte` (`atrasadas` ou `hoje`) e `ordem` (`prazo` ou `prioridade`; vazio = manual).
- Kanban: a tela converte o movimento entre colunas na `acao` do pipeline (ex.: Em validação → Em andamento = `devolver`, que abre a janela do motivo). O servidor decide; em `403` o cartão volta.
- Botões do detalhe: só os de `acoes`. Envie `versao` nas gravações para receber `409` em caso de alteração concorrente.
- Seletor de pessoas: `GET /pessoas?busca=` (a faixa de carga aparece junto ao nome).

## Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Regra violada: justificativa ou motivo vazio, pessoa fora da equipe, formato de arquivo, equipe com tarefas abertas |
| `403` | `sem_permissao` | Ação fora do papel ou da etapa |
| `404` | `nao_encontrado` | Tarefa, equipe ou anexo inexistente, ou sem permissão para ver |
| `409` | `conflito` | `versao` desatualizada ou marcador repetido |
| `422` | `validacao` | Campos fora do formato |
