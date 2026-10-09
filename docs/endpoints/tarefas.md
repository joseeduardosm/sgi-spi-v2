# Módulo Tarefas (`/api/tarefas`)

Tag no OpenAPI: **Módulo Tarefas**. Implementação:
- rotas: `backend/app/api/routes/tarefas.py`;
- regras: `backend/app/services/tarefas/servico_tarefas.py`;
- modelos: `backend/app/models/tarefas.py` (migração `2320f1538b36`).

Reconstrução, no SGI SPI, do app de tarefas do 10.23.1.220, com pipeline de validação, linha do tempo detalhada e avisos pela mensageria. Todas as rotas exigem login (perfil em dia); as permissões por tarefa e por equipe são conferidas no servidor.

## Papéis

| Papel | Quem |
|---|---|
| **Responsáveis** | Um ou mais, com os mesmos poderes: executam a tarefa e a carga conta para cada um. O primeiro (`responsavel`) é o principal, usado nas raias e nos relatórios; o antigo conceito de "participante" foi incorporado aqui (migração `e9f3a7c1b5d6`: a tabela `tarefas_participantes` virou `tarefas_responsaveis`, e o responsável principal de cada tarefa passou a constar nela) |
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
- **Atribuição:** numa equipe, os responsáveis são membros ou liderança da equipe. A liderança pode incluir qualquer usuário ativo.
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
| Responsável incluído | quem entrou | `tarefa-responsavel:{id}:{versao}` |
| Prazo alterado | envolvidos | `tarefa-prazo:{id}:{versao}` |
| Transferida | novo responsável | `tarefa-transferida:{id}:{versao}` |
| **Entregue para validação** | liderança (pendência, encerrada ao validar ou devolver) | `tarefa-validacao:{id}:{versao}` |
| Validada / devolvida (com motivo) / reaberta | envolvidos | `tarefa-validada:…`, `tarefa-devolvida:…`, `tarefa-reaberta:…` |
| Concluída pela liderança | envolvidos e liderança | `tarefa-concluida:{id}:{versao}` |
| Comentário | envolvidos e criador (menos o autor) | `tarefa-comentario:{evento}` |
| Vence amanhã / atrasada (timer das 07:00) | envolvidos | `tarefa-prazo-aviso:{id}:…` |
| **Escalonamento por atraso** (memorial diário) | cada líder: um aviso por dia com a tabela das tarefas atrasadas escalonadas a ele | `tarefa-escalonada:{usuário}:{dia}` |

**Escalonamento por atraso (memorial diário).** No mesmo timer das 07:00, a tarefa operacional (a fazer ou em andamento) atrasada é escalonada em dois níveis: há **1+ dia**, à liderança direta da equipe (tarefa pessoal: o criador); há **3+ dias**, também a quem lidera as equipes acima. Em vez de um e-mail por tarefa, cada líder recebe **um aviso por dia** (caixa do SGI e e-mail, prioridade alta) com **uma tabela** das tarefas atrasadas escalonadas a ele: **Nº, Título, Responsável, Atraso (dias) e Link**, da mais atrasada para a menos. O memorial repete a cada dia enquanto houver tarefa atrasada (concluir ou renegociar o prazo tira a tarefa da lista); quem não tem tarefa escalonada não recebe nada. Na linha do tempo da tarefa entra o evento `escalonada` ("Escalonada (nível N): atrasada há X dia(s)"), **uma vez por nível e prazo**. Constantes: `DIAS_ESCALONAR_LIDERANCA = 1` e `DIAS_ESCALONAR_ACIMA = 3` em `servico_tarefas.py`. Migração `f3b7d1e9a5c4`. Sem endpoint novo. O corpo dos e-mails da mensageria passou a aceitar tabela simples (linhas `| a | b |`).
| Validação parada há 2+ dias (timer) | liderança, **em janela modal que não bloqueia** | `tarefa-validacao-parada:{id}:{versao}` |

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /api/tarefas` | `ListaTarefas`. `escopo`: `minhas` (padrão), `equipe` (`equipe_id`), `pessoa` (`login`) ou `subtarefas` (`tarefa` = número da mãe: o quadro das subtarefas, `contexto.titulo` = "Equipe X - Tarefa Título - Subtarefas", `contexto.equipe_id`, `tarefa_numero` e `tarefa_titulo`; `400` sem `tarefa`, `404` se o usuário não vê a mãe). Só **tarefas-mãe** entram em `minhas`, `equipe` e `pessoa`. Filtros: `status` (repetível), `prioridade`, `marcador_id`, `responsavel_id`, `busca` (título, descrição ou número). Os indicadores são do escopo inteiro |
| `POST /api/tarefas` | `NovaTarefa` (`titulo`, `descricao`, `prazo`, `prioridade`, `equipe_id`, `responsaveis_ids` — um ou mais, o primeiro é o principal, vazio = quem cadastra —, `marcadores_ids`) → `201 TarefaDetalhe` |
| `POST /api/tarefas/com-anexos` | `multipart/form-data`: `dados` (JSON de `NovaTarefa`, como texto) e até 5 `arquivos` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG) → `201 TarefaDetalhe`. Os arquivos ficam anexados ao evento "Tarefa criada" da linha do tempo e o aviso aos envolvidos informa a quantidade. Arquivo recusado (tipo, tamanho ou vazio) ou mais de 5 → `400` e **nenhuma tarefa é criada**; `dados` inválido → `422`. Mesmas regras de permissão do `POST /api/tarefas` |
| `GET /api/tarefas/{numero}` | `TarefaDetalhe` |
| `PUT /api/tarefas/{numero}` | `EdicaoTarefa`: título, descrição, prioridade, `responsaveis_ids` (ao menos um; o principal continua o mesmo se estiver na lista, senão passa a ser o primeiro), marcadores |
| `POST /api/tarefas/{numero}/prazo` | `{prazo, justificativa, versao?}` |
| `POST /api/tarefas/{numero}/mover` | `{acao, texto?, versao?}` |
| `POST /api/tarefas/{numero}/transferir` | `{para_id, justificativa, novo_prazo?, versao?}` |
| `POST /api/tarefas/{numero}/comentarios` | `multipart/form-data`: `texto` e/ou `arquivos` e, opcionalmente, `em_resposta_a` (id de um comentário **desta** tarefa, ainda não removido; `404` caso contrário) → `201 EventoLeitura`. A resposta guarda em `dados` `resposta_a`, `resposta_autor` e `resposta_texto` (trecho de até 240 caracteres, que continua legível se o original for removido) e entra no topo da linha do tempo como qualquer comentário novo. No Angular: botão "Responder" em cada comentário do **Histórico** (antes "Atividade"), citação acima do campo e, na resposta, citação clicável que rola até o original |
| `GET /api/tarefas/{numero}/linha-do-tempo` | `LinhaDoTempo {total, itens, tem_mais}`. `filtro`: comentarios, anexos, status, prazos, atribuicoes; `antes_de` + `limite` (padrão 30) para "carregar mais" |
| `GET /api/tarefas/{numero}/anexos/{anexo_id}` | Download (confere a permissão na tarefa) |
| `POST /api/tarefas/{numero}/eventos/{evento_id}/remover` | SuperRoot: `{motivo}` |
| `POST /api/tarefas/{numero}/checklist` | `{acao: incluir\|marcar\|remover, texto?, item_id?}` |
| `DELETE /api/tarefas/{numero}` | `204` |
| `POST /api/tarefas/ordem` | `{numeros: [...]}`: ordem manual (arrastar); ignora o que o usuário não pode editar |
| `GET /api/tarefas/pessoas` | `PessoaCarga[]`: carga, faixa, a fazer, em andamento e atrasadas de **todas** as tarefas da pessoa. Com `equipe_id`, os membros e a liderança da equipe, mais `na_equipe` (`a_fazer`, `em_andamento`, `em_validacao`, `concluidas`, `atrasadas` só das tarefas da equipe); sem, busca (`busca`, até 20) e `na_equipe` nulo |
| `GET /api/tarefas/pessoas/{usuario_id}/agenda` | `AgendaPessoa`: painel que aparece ao escolher os responsáveis. Traz `pessoa` (como em `PessoaCarga`), `de`, `ate` e `itens[]` (`ItemAgenda`: `numero`, `titulo`, `status`, `prioridade`, `inicio` = 1ª vez em andamento ou criação, `prazo`, `concluida_em`, `atrasada`, `equipe`, `abrivel`). Entram **todas** as tarefas abertas da pessoa e as concluídas no período `de`–`ate` (padrão: 30 dias antes a 60 dias depois de hoje). **Aberto a qualquer usuário logado, com os títulos**: por decisão do usuário, quem atribui vê a agenda completa de quem recebe. `abrivel` diz se quem consulta pode abrir a tarefa. `400` se `de` > `ate`; `404` se a pessoa não existe |
| `GET /api/tarefas/relatorio` | Arquivo XLSX (abas **Tarefas** e **Por pessoa**) ou PDF (resumo, pessoas, lista). `formato` (`xlsx` padrão ou `pdf`), `escopo`/`equipe_id`/`login` (mesmas permissões da lista), `marcador_id`, `de` e `ate` (aaaa-mm-dd). Entram as tarefas ativas no período: criadas até `ate` e abertas ou concluídas a partir de `de`. `400` se `de` > `ate` |
| `GET /api/tarefas/{numero}/memorial?formato=pdf\|xlsx` | **Relatório memorial** da tarefa: dados (equipe, situação, responsáveis, prazos, **dias em aberto** ou dias até a conclusão) e **todos** os acontecimentos da linha do tempo (comentários, situação, prazos, atribuições, anexos, checklist, escalonamentos, atividades), do mais antigo ao mais recente; itens removidos aparecem identificados, sem conteúdo. PDF paisagem ou XLSX (abas **Resumo** e **Acontecimentos**). Quem vê a tarefa emite; `404` caso contrário. No detalhe da tarefa, botões PDF e XLSX |
| `GET /api/tarefas/equipes` | `EquipeLeitura[]` visíveis (membro ou liderança; SuperRoot: todas), com indicadores, `lider` e `pode_configurar` |
| `POST /api/tarefas/equipes` | `GravacaoEquipe` → `201`: quem cria é o dono |
| `PUT /api/tarefas/equipes/{equipe_id}` | Dono ou SuperRoot |
| `DELETE /api/tarefas/equipes/{equipe_id}` | Desativa (dono ou SuperRoot); `400` com tarefas em aberto |
| `GET /api/tarefas/equipes/{equipe_id}/marcadores` | Marcadores da equipe e globais, **os mais usados primeiro** (uso nas últimas 1000 tarefas da equipe, campo `usos`) e depois por nome. `busca` filtra por trecho do nome (sem maiúsculas nem acentos); `limite` (padrão 100, até 500). Alimenta o campo de marcadores |
| `POST /api/tarefas/equipes/{equipe_id}/marcadores` | `{ nome, cor_indice? }` → `201`. **Membros e liderança** criam na hora ("Criar 'texto'"); nome repetido (sem diferenciar maiúsculas) devolve o marcador existente; sem `cor_indice` sorteia de 1 a 11. Não membro: `403`. `cor` (hexadecimal legado) vira a cor da paleta mais próxima |
| `PUT /api/tarefas/equipes/{equipe_id}/marcadores/{marcador_id}` | `{ nome, cor_indice }`: renomear e trocar a cor, só a liderança (`403`); nome repetido `409`; `cor_indice` fora de 0–11 `422` |
| `DELETE /api/tarefas/marcadores/{marcador_id}` | Liderança da equipe do marcador |
| `GET` / `POST /api/tarefas/equipes/{equipe_id}/marcos` | Marcos (milestones) com `total`, `concluidas`, `atrasadas` e `situacao` (`no_prazo`, `em_risco`, `atrasado`, `atingido`), por data-alvo. `GET`: membros e liderança; `POST` `{ nome, descricao, data_alvo }`: só a liderança (`403`), nome único (`409`) |
| `PUT` / `DELETE /api/tarefas/marcos/{id}` | Alterar e excluir (as tarefas ficam, sem marco): só a liderança |
| `POST /api/tarefas/marcos/{id}/atingir` e `/reabrir` | Decisão manual da liderança; o estado fica fixo (a conclusão das tarefas não o muda mais) |
| `PUT /api/tarefas/{numero}/marco` | `{ marco_id? }`: liga a tarefa a um marco da mesma equipe ou tira (vazio); quem edita a tarefa |
| `GET` / `POST /api/tarefas/equipes/{equipe_id}/status` | Atualizações de status da equipe (últimas 30, a primeira é a atual) e publicar `{ situacao, texto }` (`no_prazo`, `em_risco`, `atrasado`, `em_espera`, `concluido`): só a liderança; membros avisados (e-mail só em risco/atrasado) |
| `GET /api/tarefas/atividades?concluidas=` | Minhas atividades: abertas por data (`situacao` atrasada, hoje ou futura) ou, com `concluidas=true`, as 50 últimas concluídas |
| `GET` / `POST /api/tarefas/{numero}/atividades` | Lista (abertas primeiro) e agenda: `{ resumo, tipo, nota, prazo, responsavel_id }`; tipos `fazer`, `ligar`, `email`, `reuniao`, `revisar`, `enviar_documento`; padrões: prazo hoje, responsável quem agenda; numa equipe o responsável precisa ser da equipe (membro) — a liderança pode escolher qualquer usuário (`400`) |
| `PUT` / `DELETE /api/tarefas/atividades/{id}` | Alterar (`409` se concluída) e excluir: quem agendou, quem faz ou quem edita a tarefa (`403`) |
| `POST /api/tarefas/atividades/{id}/concluir` | `{ feedback? }`: registra na linha do tempo e avisa quem agendou (se for outra pessoa); concluída de novo `409` |
| `POST` / `DELETE /api/tarefas/{numero}/seguir` | Seguir ou deixar de seguir; `TarefaDetalhe.seguindo` e `seguidores` |
| `GET` / `PUT /api/tarefas/equipes/{equipe_id}/estagios` | Estágios (colunas do quadro) da equipe. `GET`: membros, liderança e SuperRoot; uma equipe sem estágios ganha os 4 padrão. `PUT`: lista completa e ordenada (4 a 20), só a liderança (`403`); regras de ordem e unicidade `400`; excluir estágio com tarefas `409` |
| `POST /api/tarefas/{numero}/estagio` | `{ estagio_id, versao? }`: troca a coluna dentro da **mesma categoria**; outra categoria `400` (use `mover` com `estagio_id`) |
| `POST /api/tarefas/{numero}/subtarefas` | `NovaSubtarefa` (`titulo`, `descricao`, `prazo`, `prioridade`, `responsaveis_ids`) → `201 TarefaDetalhe` da subtarefa. Quem edita a mãe cria; um só nível (`400` para subtarefa de subtarefa); herda equipe e marcadores; padrões: prazo, prioridade e responsáveis da mãe; o prazo não passa do da mãe (`400`) |
| `PUT /api/tarefas/{numero}/dependencias` | `{ numeros: [..] }` substitui a lista de tarefas que **bloqueiam** esta. `400` para a própria tarefa, mãe/subtarefa, outra equipe, tarefa inexistente ou ciclo |
| `GET /api/tarefas/equipes/{equipe_id}/desempenho?de&ate&marcador_id` | `DesempenhoEquipe` — só dono, líderes (inclusive de equipes acima) e SuperRoot (`403`). Padrão: últimos 30 dias; `400` se `de` > `ate` ou período > 366 dias; `404` equipe inexistente. Traz `resumo`, `burndown`, `vazao`, `ciclo`, `fluxo` e `pessoas` |
| `GET /api/tarefas/pessoas/{usuario_id}/desempenho?de&ate&marcador_id` | O mesmo `DesempenhoEquipe`, para **uma pessoa** (`escopo = pessoa`, `equipe_id` vazio, `equipe_nome` = nome da pessoa): todas as tarefas em que ela é **responsável**, de qualquer equipe **e as pessoais** (sem equipe), sem subtarefas. A própria pessoa e o SuperRoot veem tudo; a liderança vê só as tarefas das equipes que lidera (as pessoais de outra pessoa ficam de fora). `403` para os demais; `404` pessoa inexistente; `400` período inválido |
| `POST /api/tarefas/contratos/sincronizar?ensaio=true` | SuperRoot (`403`). Cria e atualiza as tarefas das competências de contratos (ver **Tarefas das competências de contratos**). `ensaio=true` (padrão) não grava: devolve `{ensaio, competencias, criadas, atualizadas, removidas, erros[]}`. Idempotente; roda sozinha às 07:00 |
| `POST /api/tarefas/recorrencias/previa` | `{ prazo, regra }` → `{ resumo, proximas[] }`: texto da regra e as próximas datas de prazo (depois da primeira), com o mesmo cálculo da geração (dias úteis e feriados cadastrados). Regra inválida `400`; `dias_semana` fora de 0–6 `422` |
| `GET /api/tarefas/recorrencias?equipe_id=` | Séries da equipe (membros e liderança) ou, sem `equipe_id`, as pessoais do usuário → `RecorrenciaLeitura[]` (modelo, regra, `resumo`, `proxima_data`, `proximas`, `geradas`, `ultimo_erro`, `pode_gerir`) |
| `GET` / `PUT` / `DELETE /api/tarefas/recorrencias/{id}` | Ler (`404` fora da equipe), alterar (modelo e regra; vale só para as próximas ocorrências) e excluir (as tarefas já criadas continuam, sem vínculo). Alterar e excluir: quem criou a série, a liderança da equipe ou o SuperRoot (`403`) |
| `POST /api/tarefas/recorrencias/{id}/pausar` e `/retomar` | Pausa a geração; retomar volta pela próxima data da regra (as vencidas durante a pausa não são criadas) |

**Tarefas recorrentes.** `NovaTarefa.recorrencia` (`frequencia` diaria/semanal/mensal/anual, `intervalo`, `dias_semana` 0=segunda…6, `somente_dias_uteis`, `antecedencia_dias`, `fim`, `max_ocorrencias`) cria a série junto com a tarefa, que é a **primeira ocorrência** (o prazo dela define a data inicial e o horário de todas). As demais nascem **pelo calendário** na rotina das 07:00 (`python -m app.tarefas.mensageria lembretes`), `antecedencia_dias` antes do prazo, mesmo com a anterior ainda aberta; mensal preserva o dia (último dia nos meses curtos) e, com `somente_dias_uteis`, fim de semana e feriado (`rh_feriados`) vão para o próximo dia útil. Depois de uma parada do sistema só a ocorrência mais recente vencida é criada (as anteriores são puladas, mas contam no limite). A geração é idempotente (unicidade `(recorrencia_id, ocorrencia_em)`) e avisa todos os responsáveis, com e-mail. Se a geração falha (ex.: responsável inativo), a série é **pausada** com `ultimo_erro` e quem a criou é avisado. `TarefaDetalhe.recorrencia` traz o resumo da série. Migração `a2b5c9d3e7f8` (`tarefas_recorrencias`, `_responsaveis`, `_marcadores` e `tarefas.recorrencia_id`/`ocorrencia_em`).

**Desempenho da equipe.** O histórico **não tem tabela própria**: é reconstruído de `criado_em` e dos eventos de status da linha do tempo (`dados.de/para`); tarefas migradas, cujos eventos não têm `de/para`, usam `iniciada_em`, `entregue_em` e `concluida_em`. Entram a equipe e as sub-equipes (tarefas excluídas não existem mais). Definições: **burndown** (contagem de tarefas) = abertas ao fim de cada dia, com a linha **ideal** (do total aberto no início do período até zero no último dia) e a linha de **escopo** (tudo o que existia no escopo até o dia: mostra o que entrou no meio do período; tarefas concluídas antes do período ficam de fora); dias futuros vêm sem valor (`null`). **Vazão** = por semana (segunda a domingo), criadas e concluídas e a média móvel de 4 semanas das concluídas. **Ciclo** = primeira vez em andamento → conclusão; **lead time** = criação → conclusão, ambos em dias, por semana de conclusão (mediana e percentil 85). **Fluxo acumulado** = tarefas em cada situação por dia. **Pessoas** = concluídas no período e lead time médio por responsável. **Conclusão desfeita não conta:** tarefa concluída e depois reaberta sai da vazão, do ciclo, do lead time e do total por pessoa; reaberta e concluída de novo conta uma vez, na data da última conclusão (só a conclusão vigente vale; o burndown e o fluxo continuam mostrando a situação de cada dia). Na tela é a visão **Desempenho** (`?visao=desempenho`): da equipe, só para `contexto.lider`; individual (`contexto.pessoa_id`), em **Minhas tarefas** (o próprio usuário) e na tela de uma pessoa.

**Dias em aberto.** `TarefaResumo.dias_em_aberto` = dias corridos (calendário de São Paulo) desde a criação, enquanto a tarefa não está concluída (`null` se concluída). Aparece no cartão do quadro ("12d"), no detalhe ("Em aberto há 12 dias"), no memorial da tarefa e na coluna **Em aberto** do memorial de tarefas atrasadas enviado às lideranças.

**Subtarefas e dependências.** A subtarefa é uma tarefa completa (pipeline, responsáveis e prazo próprios) ligada à mãe por `tarefa_pai_id` (migração `b3c6d0e4f8a9`); o resumo traz `tarefa_pai_numero`, `subtarefas_total`, `subtarefas_concluidas` e `bloqueada`, e o detalhe traz `tarefa_pai`, `subtarefas`, `bloqueada_por`, `bloqueia` e `pode_criar_subtarefa`. **Subtarefas têm quadro próprio** e não aparecem no quadro, na lista, no calendário, nos contadores, em "Minhas tarefas", na agenda e carga das pessoas, na busca global, no painel executivo nem na contagem das equipes (os lembretes das 07:00 continuam avisando quem recebeu uma subtarefa); o detalhe da mãe tem o atalho "Abrir quadro de subtarefas" (`/tarefas/{numero}/subtarefas`). A mãe **se move livremente** (entregar, validar, concluir) mesmo com subtarefa aberta: a subtarefa **não muda de situação, estágio, ordem nem versão**, só ganha um evento `editada` ("Tarefa mãe #N movida: A → B", também ao mudar o estágio da mãe) na linha do tempo. Regra de `POST /{numero}/mover`: uma tarefa **bloqueada não inicia** enquanto alguma bloqueadora não estiver concluída (`400`). Excluir a mãe leva as subtarefas (cascata). O desempenho da equipe conta só as tarefas-mãe.

**Estágios por equipe.** Cada estágio (`tarefas_estagios`, migração `c4d7e1f5a9b0`) pertence a uma **categoria** (`a_fazer`, `em_andamento`, `em_validacao`, `concluida`): validação, permissões, avisos, burndown e relatórios continuam seguindo a categoria. Regras: categorias na ordem do pipeline; ao menos um "a fazer" e um "em andamento"; exatamente um "em validação" e um "concluída"; nomes únicos. `TarefaResumo.estagio_id` é a coluna atual (vazio em tarefa pessoal; tarefa sem estágio próprio aparece no primeiro da categoria). `POST /{numero}/mover` aceita `estagio_id` (da categoria de destino); sem ele, vai para o primeiro estágio da categoria.

**Atividades, seguidores e menções.** Atividade (`tarefas_atividades`, migração `d5e8f2a6b1c3`) é um compromisso curto da tarefa com tipo, resumo, nota, data e responsável. Agendar e concluir entram na linha do tempo (evento `atividade`). A rotina das 07:00 avisa o responsável das atividades **de hoje** e das **atrasadas** (e quem agendou, quando é outra pessoa, nas atrasadas), uma vez por dia. **Seguidores** (`tarefas_seguidores`) recebem os avisos informativos (comentários, prazos e validação), não as pendências nem as atribuições. Em comentários, `@login` avisa a pessoa citada (se ela vê a tarefa), que não recebe também o aviso genérico do comentário.

**Marcos e status da equipe.** Marco (`tarefas_marcos`, migração `e6f9a3b7c2d4`) = nome, descrição e data-alvo; `TarefaResumo.marco_id` liga a tarefa. Fica **atingido** quando todas as suas tarefas concluem (reavaliado a cada mudança de situação; reabrir uma tarefa tira o atingimento) ou por decisão da liderança. Situação derivada: `atingido`; `atrasado` (data-alvo passou); `em_risco` (há tarefa atrasada ou com prazo depois da data-alvo); `no_prazo`. A equipe é avisada quando um marco é atingido. As **atualizações de status** (`tarefas_atualizacoes_status`) trazem a situação publicada pela liderança; toda **segunda-feira**, às 07:00, a liderança das equipes com tarefas abertas e sem atualização há 7 dias ou mais é lembrada. `DesempenhoEquipe` inclui `marcos` e `status_atual`.

**Marcadores (estilo Odoo).** Cada marcador tem `cor_indice` (0–11) numa paleta de 12 cores (borda, fundo suave e texto escuro; a mesma do Odoo; `cor` guarda o hexadecimal da borda por compatibilidade; migração `f1a4b8d2c6e7` converteu as cores antigas para a mais próxima). No frontend o campo `app-seletor-marcadores` mostra pílulas com ×, lista os mais usados ao focar, filtra ao digitar, oferece `Criar "texto"`, e a liderança clica na pílula para trocar a cor, renomear ou excluir. Atribuir e tirar grava na hora (`PUT /api/tarefas/{numero}` com `marcadores_ids`; a linha do tempo registra "Marcadores: de → para"). `TarefaDetalhe.usuario_lidera` indica se o usuário lidera a equipe (libera a gestão dos marcadores).

**`TarefaResumo`:**
- identificação: `numero`, `titulo`, `status`, `prioridade`, `equipe`, `responsavel` (principal), `marcadores`;
- prazo: `prazo`, `prazo_original`, `prorrogacoes`, `atrasada`;
- pessoas: `responsaveis` (todos os responsáveis, o principal primeiro e depois os demais por nome, para os avatares);
- andamento: `checklist_feitos`/`checklist_total`, `comentarios` e `anexos` (sem os removidos), `carga`, `ordem`;
- datas: `criado_em`, `iniciada_em` (1ª vez em andamento), `concluida_em` e `atualizado_em`.

**`TarefaDetalhe`** acrescenta:
- `descricao`, `criado_por`, `checklist[]`;
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
| participante único | `responsavel_id` e responsável (`tarefas_responsaveis`) |
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
  - dentro de cada coluna aberta, os cartões ficam sempre em ordem crescente de prazo (desempate pelo número); a ordem manual por arraste vale só na Lista;
  - **Tela cheia** (botão "⛶ Tela cheia", tecla `F`; `Esc` sai): o espaço (Minhas tarefas, equipe e pessoa, em todas as visões) cobre o portal e pede o fullscreen do navegador; a preferência fica no navegador (`tarefas.espaco.tela-cheia`). O quadro ocupa a altura toda, sem rolagem da página.
  - **Densidade automática por coluna** (na tela cheia e no modo normal): o quadro mede cada coluna e escolhe o menor nível em que os cartões cabem sem rolagem: 1 cartão normal; 2 duas subcolunas (só em coluna com ao menos 330px; cartões por linha, mantendo a ordem de prazo); 3 duas subcolunas com cartão reduzido (`#número · prazo · criticidade (B/N/A/C) · marcadores como faixas coloridas`), com dica ao passar o mouse ou focar (título, prazo e hora, prioridade, responsáveis, marcadores, contadores). Se nem o nível 3 couber, a coluna rola. Lógica em `densidade-quadro.ts`. Apenas frontend (sem mudança de API).
  - a Concluída mostra as 10 mais recentes, com "ver todas", e pode ser recolhida;
  - o cartão traz as etiquetas (marcadores), o título, o chip do prazo (vermelho se atrasado, âmbar se vence hoje ou amanhã), o checklist, os comentários, os anexos, o número e os avatares de `responsaveis`, com a borda da prioridade;
  - arrastar entre colunas ou usar o menu "⋯" vira a `acao` do pipeline (Em validação → Em andamento = `devolver`, que pede o motivo). O servidor decide e, em `403`, o cartão volta;
  - **"+ Adicionar tarefa"** na coluna A fazer (fora da tela de outra pessoa) cria só com o título. Padrões: responsável = quem cria, prioridade normal, prazo em 7 dias às 18:00, equipe do quadro (em Minhas tarefas, pessoal);
  - em raias, cada responsável ganha uma linha com a carga.
- **Lista** (`lista-tarefas.component.ts`): seções recolhíveis por situação, estilo Asana (a Concluída começa fechada), com a ordem manual por arraste dentro da seção.
- **Calendário** (`calendario-tarefas.component.ts`): mês ou semana, com as tarefas no dia do prazo. Arrastar para outro dia abre "Alterar prazo" já com o novo dia, e a justificativa continua obrigatória.
- **Pessoas:** cartões com a carga e as barras por situação na equipe.

**Janela da tarefa** (`janela-detalhe-tarefa.component.*`):
- à esquerda: título editável no lugar, descrição, checklist e atividade (comentário com anexos e linha do tempo com filtros);
- à direita: situação e ações (só as de `acoes`), responsáveis (Editar e Transferir), prazo (Alterar), prioridade, marcadores, carga e dados;
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


## Tarefas das competências de contratos

Para **medir** o trabalho da execução mensal, cada competência regular de contrato ganha, na equipe **Contratos**, uma tarefa por etapa. O motor é `services/contratos/servico_tarefas_contratos.py` (`sincronizar_competencia`): idempotente, compara o estado real da competência com as tarefas e corrige o que diverge. Ele roda (1) depois de cada ação de escrita em `servico_competencias` (`_auditar`; falha vira log e nunca derruba a ação), (2) na rotina das 07:00 (`gerar_lembretes`) e (3) por `POST /api/tarefas/contratos/sincronizar`.

- **Quem entra:** competência `regular`, já liberada (`hoje` > fim do período), dentro do corte de cobrança (`anterior_ao_corte`) e de contrato **sem** "Liberar todas as competências" e não suspenso. Na primeira execução as etapas já feitas nascem **concluídas**, com as datas e os autores reais.
- **SLA de prazos:** `TarefaResumo.sla` (resposta e resolução em dias úteis pela prioridade; vazio nas tarefas controladas por outro módulo), selo "SLA" no cartão quando a resolução está em risco ou estourada, `sla` e `pessoas[].sla_percentual` no Desempenho e coluna "SLA (resolução)" no relatório XLSX. Política e cálculo em [sla.md](sla.md).
- **Título:** `{etapa} — {apelido} - {número do contrato} — {competência}` (sem apelido, só o número); as tarefas existentes são renomeadas na próxima sincronização.
- **Equipe e fila pessoal:** a equipe **Contratos** recebe como membros todos da equipe vigente de qualquer contrato e o Financeiro (`sincronizar_membros`, a cada sincronização; só acrescenta). As pessoas continuam responsáveis, mas as tarefas com `origem_tipo` preenchido **não entram em `escopo=minhas` nem em `escopo=pessoa`**: ficam só no escopo `equipe` da equipe Contratos.
- **Colunas novas em `tarefas`** (migração `a7c3e9b5d1f2`): `origem_tipo` (`contrato_competencia`), `origem_id` (id da competência), `origem_chave` (etapa), `controlada_externamente` e a unicidade `(origem_tipo, origem_id, origem_chave)`; novo tipo de evento `contrato` na linha do tempo. `TarefaResumo` traz `origem_tipo` e `controlada_externamente`; `TarefaDetalhe` traz `origem_link` e `origem_rotulo`; `GET /api/tarefas` aceita `origem=contratos|manual`; `Contexto.pessoa_id` identifica a pessoa do escopo.
- **Prazos** em dias úteis (fim de semana e `rh_feriados` não contam), às 18:00, contados de `n` = dia seguinte ao fim do período: medição n+2; avaliação preencher n+3 e via assinada n+4; nota fiscal n+4; retenção n+5 (ou nota juntada + 1 dia útil, o que for maior); CADIN, checklist e consolidado n+6; **Subir no SEI** e **Despachar** n+7 (**manuais**, sem controle de Contratos e sem o rodapé); juntar a OB = data da NF + prazo de pagamento (n+30 dias corridos até a NF entrar).
- **Estado:** a fazer → em andamento (primeira ação na etapa) → concluída (etapa concluída em Contratos). Etapas de ato único passam por em andamento e concluem no mesmo instante. Reabrir/zerar em Contratos devolve a tarefa (evento `reaberta`). **Nota fiscal e retenção em rodadas**: uma retenção por nota; a recusa do Financeiro fecha a rodada (motivo no histórico, evento `contrato` com `recusa`) e abre "Subir a nota fiscal (2ª rodada)" e a nova retenção.
- **Controle:** tarefa `controlada_externamente` só aceita comentar, anexar e seguir; a liderança ajusta responsáveis, prazo e transferência. Mover, estágio, subtarefas, dependências, excluir e editar título/descrição → `403` com código `controlada_externamente`. **Não entra na carga** da pessoa (continua no quadro, nos filtros e no Desempenho).
- **Avisos:** nenhum e-mail ou aviso ao criar ou concluir essas tarefas (o módulo Contratos já avisa). Lembretes e escalonamento por atraso valem para essas tarefas.
- **Descrição:** as tarefas controladas terminam com o rodapé "Tarefa criada pelo módulo Contratos somente para dimensionamento e monitoramento do trabalho. Por favor, trate esta tarefa no módulo Contratos".
- **Responsáveis:** equipe vigente do contrato (gestor primeiro); retenção = Financeiro + gestor; SEI/despachar = gestor + fiscal administrativo. Marcadores automáticos: um por contrato e um por etapa.
