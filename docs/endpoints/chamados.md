# Módulo Chamados (`/api/chamados`)

Tag no OpenAPI: **Chamados**. Implementação:
- rotas: `backend/app/api/routes/chamados.py`; schemas: `backend/app/schemas/chamados.py`;
- regras: `backend/app/services/chamados/` (`acesso.py` papéis e visibilidade, `motor_sla.py` horas úteis, `parametros.py` Parâmetros, `servico.py` atendimento);
- modelos: `backend/app/models/chamados.py` (`chamados_parametros`, `chamados_setores_atendimento`, `chamados_expedientes`, `chamados_expediente_faixas`,
  `chamados_slas`, `chamados_categorias`, `chamados`, `chamados_acompanhamentos`, `chamados_solucoes`, `chamados_anexos`; migração `d4f6a8c0e2b5`;
  marco 2: `chamados_campos`, `chamados_valores`, `chamados_atores`, `chamados_tarefas`, `chamados_validacoes`, migração `e7a9c1d3f5b8`;
  marco 3: `chamados_status_apresentacao`, `chamados_substatus`, `chamados_recorrentes`, `chamados_execucoes` e as colunas `chamados.substatus_id`,
  `recorrente_id`, `gerado_para`, migração `f8b0d2e4a6c9`).
- tarefas automáticas: `backend/app/tarefas/chamados.py` (`minuto`, `vigia`) e `backend/app/services/chamados/tarefas_agendadas.py`; timers
  `systemd/sgi-spi-chamados-minuto.timer` (a cada minuto) e `sgi-spi-chamados-vigia.timer` (a cada 5 minutos), instalados pelo `scripts/instalar.sh`.
- ações do marco 2: `backend/app/services/chamados/acoes.py`; campos adicionais: `backend/app/services/chamados/campos.py`.

O módulo substitui a Assistência do GLPI (planejamento em `replica/architecture.md`). Este documento cobre os **marcos 1, 2 e 3** (ver as seções "Marco 2" e "Marco 3"). O marco 1: abrir um chamado,
ver na fila, assumir, responder e resolver, e os Parâmetros mínimos (expedientes, SLAs e categorias). Até a virada, a abertura de chamado
no GLPI continua em [chamados-glpi.md](chamados-glpi.md) (`/api/chamados-glpi`).

> **Canais dos avisos:** todo aviso chega na caixa de [notificações](notificacoes.md). Quando um **setor** é responsável ou solicitante,
> **todos os membros ativos** recebem também **por e-mail**, mesmo que tenham desmarcado o e-mail nas preferências. Os demais avisos seguem a preferência de cada pessoa.

---

## Papéis e acesso

Recurso ACL `chamados` (níveis hierárquicos):

| Nível | Papel | O que pode |
|---|---|---|
| `LEITURA` | Abrir chamados | Abre chamados e acompanha os seus (como solicitante ou pelo setor em nome do qual pediu); responde em público e anexa arquivos. Não vê a fila |
| `MODIFICACAO` | Atender chamados | Além de abrir, vê a fila dos seus setores (e dos setores abaixo, se for líder), assume, responde (inclusive em privado) e resolve |
| `CONTROLE_TOTAL` | Administrar os Chamados | Faz tudo, vê os chamados de todos os setores e cuida dos Parâmetros |
| SuperRoot | | Tudo |

- **Fechado até a virada:** diferente dos outros módulos, o recurso **sem nenhuma regra nem perfil** libera **só o SuperRoot** (o GLPI continua em uso).
  Sem papel, as rotas respondem `403 acl_negado` (exceto `GET /contexto`, que responde com os papéis em `false`). A migração `d4f6a8c0e2b5` cadastra o recurso sem regras.
- **Papéis no chamado** (nomes do SGI): **solicitante** (quem pediu e, opcionalmente, o **setor solicitante**), **em cópia** (marco seguinte) e
  **responsável**: o **setor responsável** (qualquer setor ativo do SGI, oficial ou sistêmico) e o **responsável pelo atendimento** (a pessoa).
- **Quem vê um chamado:** o solicitante, os membros do setor solicitante, o responsável pelo atendimento, quem atende e é membro do setor responsável
  (ou líder de um setor acima dele), quem atende e é membro de um setor com "ver todos" (`chamados_setores_atendimento.ve_todos`) e quem administra.
  Para os demais, o chamado **não existe** (`404`).
- **Categoria sigilosa** (própria ou de um ancestral): quem não atende vê o título "Chamado restrito", sem descrição nem linha do tempo.
- **Mensagem privada:** só quem atende escreve e vê (inclusive os anexos dela).

## Regras

- **Status-base** (fixos no código): `novo` → `em_atendimento` → `pendente` / `em_aprovacao` (marcos seguintes) → `solucionado`. **Resolvido é o fim**: não existe
  "fechado", e o chamado resolvido (ou importado do GLPI) é somente leitura (`409 chamado_encerrado`).
- **Setor responsável obrigatório:** o chamado nasce com o setor da categoria (próprio ou herdado da categoria-mãe) e guarda o nome do setor (`setor_nome`)
  para o histórico. Se a categoria tem responsável padrão (pessoa), o chamado já nasce `em_atendimento` com ela.
- **Tipo** (incidente ou requisição): **não é perguntado** a quem abre. Vem da categoria: `incidente`, a menos que a categoria só aceite requisição.
- **Prioridade:** a da categoria (padrão `normal`). Se o solicitante responder que o problema **está impedindo o trabalho**, ela sobe um nível
  (`prioridade_origem = solicitante`).
- **Prazos em horas úteis:** o SLA de atendimento (`tto`, cumprido na primeira ação de quem atende: assumir ou responder) e o de solução (`ttr`, cumprido
  ao resolver) só contam dentro do **expediente** e fora dos **feriados do RH** (`rh_feriados`). O ponto facultativo **não** é dia útil, a menos que o
  parâmetro `sla_ponto_facultativo_util` seja `sim`. Ex.: expediente seg–sex 8h–18h, aberto na sexta 17h com 4 horas → vence na segunda 11h.
- **Número:** sequencial (`chamados_parametros.proximo_numero`, reservado com trava de linha). Os importados do GLPI manterão o número de lá.
- **Assumir** é atômico (trava otimista por `versao`): se outra pessoa assumiu ou alterou antes, `409 chamado_alterado` e a tela recarrega.
- **Responder também assume:** quem é **membro do setor responsável** e responde (público ou privado) um chamado **sem responsável** passa a ser o
  responsável (novo → em atendimento), com a nota automática "assumiu o chamado ao responder"; o evento ao vivo sai como `assumido` (o painel
  fala). A resposta do solicitante nunca muda o responsável.
- **Ao resolver:** o relógio para e começa a janela do "Não resolveu" (`reabrir_ate`: fim do dia, `dias_reabrir` dias úteis depois; padrão 5). A ação de reabrir vem no marco seguinte.
- **Texto rico:** HTML sanitizado no servidor. **Imagens coladas em base64 viram anexos** e saem do texto (evita o erro do GLPI 11.0.8 que travava os e-mails).
- **Anexos:** até 10 por envio, nos formatos gerais do SGI (PDF, Office/LibreOffice, PNG, JPG, TXT, CSV), no limite `ANEXOS_TAMANHO_MAXIMO_MB`.

### Avisos (eventos do catálogo de notificações)

| Evento | Quem recebe | E-mail |
|---|---|---|
| `chamados.novo` | Membros do setor responsável (e o responsável padrão da categoria) na abertura | sempre |
| `chamados.setor_solicitante` | Membros do setor solicitante, na abertura e na solução | sempre |
| `chamados.assumido` | Solicitante, quando alguém assume | preferência |
| `chamados.acompanhamento` | Solicitante, quando a equipe responde em público; responsável (ou, sem responsável, o setor) quando o solicitante responde; quem está em cópia, em toda resposta pública; o solicitante quando o chamado fica pendente | preferência |
| `chamados.solucionado` | Solicitante (e quem está em cópia), quando o chamado é resolvido | preferência |
| `chamados.reaberto` | Responsável (sem responsável: os membros do setor, também por e-mail) quando o solicitante diz que não resolveu | preferência / sempre |
| `chamados.validacao_pedida` | Quem aprova (a pessoa ou os membros do setor aprovador) | sempre |
| `chamados.sla_estourado` | Setor responsável, quando ninguém agiu no prazo de atendimento (preferência); responsável (ou o setor), quando o prazo de solução estoura e o chamado vira Urgente (sempre) | preferência / sempre |
| `chamados.saude` | Quem administra os Chamados (Controle total e SuperRoot), quando as tarefas automáticas param ou o e-mail deixa de sair. Só pelo sino (no máximo um aviso por problema por dia) | preferência |

Quem fez a ação não recebe o próprio aviso.

---

## `GET /api/chamados/contexto`

Papéis da pessoa no módulo e setores de que ela é membro (para abrir em nome de um setor).

- **Autorização:** usuário autenticado. **Responde `200` mesmo sem papel** (tudo `false`, sem setores): o menu usa esta rota para decidir se mostra o módulo.

### Resposta `200 OK`: `ContextoChamados`

| Campo | Tipo | Descrição |
|---|---|---|
| `papeis` | `{abrir, atender, administrar}` | O que a pessoa pode fazer |
| `setores_do_usuario` | `SetorResumo[]` | `{id, nome, caminho}` dos setores ativos de que é membro |
| `inicio_atendimento` | date \| null | "A partir de": data em que o SGI passa a receber os chamados de todos (Parâmetros > Geral) |
| `atendimento_aberto` | boolean | A data já chegou. O "Abrir chamado" do sistema vai para o SGI quando a pessoa tem papel de abrir **e** (não há data marcada, ou a data chegou, ou ela administra); senão, abre o formulário do GLPI |

## `GET /api/chamados/catalogo`

Categorias que podem ser escolhidas na abertura: ativas (com todos os ancestrais ativos), com setor responsável e, para quem só abre, visíveis ao solicitante.

- **Autorização:** qualquer papel.

### Resposta `200 OK`: `CategoriaCatalogo[]`

| Campo | Tipo | Descrição |
|---|---|---|
| `id`, `pai_id` | uuid | Categoria e categoria-mãe |
| `nome`, `caminho`, `nivel` | string, string, integer | Ex.: `Informática > Impressoras`, nível 2 |
| `permite_incidente`, `permite_requisicao` | boolean | Tipos aceitos |
| `perguntar_impedindo` | boolean | Mostrar a pergunta "Isso está impedindo você de trabalhar?" |
| `setor_nome` | string | Setor que vai atender (próprio ou herdado) |

## `POST /api/chamados`

Abre um chamado. `multipart/form-data` com o campo `dados` (JSON de `AberturaChamado`) e até 10 `arquivos`. Antes da data "a partir de"
(Parâmetros > Geral), só quem tem Controle total abre: os demais recebem `409 antes_do_inicio`.

- **Autorização:** papel de abrir (Leitura ou acima).

### Requisição: `AberturaChamado` (no campo `dados`)

| Campo | Tipo | Obrigatório | Regras | Descrição |
|---|---|---|---|---|
| `titulo` | string | sim | 3 a 250 caracteres | Assunto |
| `descricao` | string | sim | HTML do editor | Imagens coladas viram anexo |
| `categoria_id` | uuid | sim | do catálogo | Define o setor responsável, a prioridade e os SLAs |
| `tipo` | string | não | `incidente` (padrão) ou `requisicao` | Precisa ser aceito pela categoria. A tela de abertura não pergunta: manda o tipo que a categoria aceita |
| `impedindo_trabalho` | boolean | não | | Sim sobe a prioridade um nível |
| `setor_solicitante_id` | integer | não | setor de que a pessoa é membro | Todos os membros recebem os avisos, inclusive por e-mail |

### Resposta `201 Created`: `ChamadoDetalhe` (ver `GET /api/chamados/{numero}`)

Erros: `400 invalido` / `categoria_invalida` (categoria fora do catálogo ou tipo não aceito), `403 acesso_negado` (sem papel ou setor solicitante de que não é membro),
`409 categoria_sem_setor` (setor responsável inativo), `422 validacao`.

## `GET /api/chamados/meus`

Chamados em que a pessoa é solicitante ou que foram abertos em nome de um setor dela, do mais recente para o mais antigo.

- **Parâmetros:** `filtro` = `abertos` (padrão) · `aguardando` (pendentes) · `resolvidos` · `todos`; `busca` (número, título ou nome do solicitante); `pagina`, `tamanho` (até 100).
- **Ordenação pela coluna clicada:** `ordem` = `numero` · `titulo` · `solicitante` · `setor` · `situacao` (na ordem do andamento) · `prioridade` (baixa → urgente) · `prazo` (prazo de solução; sem prazo sempre no fim) · `aberto_em`, e `direcao` = `asc` (padrão) ou `desc`. O número desempata. Sem `ordem`, vale a ordem padrão de cada lista.
- **Resposta `200 OK`:** `ListaChamados` = `{ total, itens: ChamadoResumo[] }`.

## `GET /api/chamados`

Fila de quem atende, limitada ao que a pessoa enxerga.

- **Autorização:** papel de atender (Modificação ou acima); senão `403 acesso_negado`.
- **Parâmetros:** `filtro` = `abertos` (padrão) · `meus` (eu sou o responsável) · `setor` · `novos` · `sem_responsavel` · `solucionados` · `todos`; `busca`
  (`1530`, `#1530`, título ou nome do solicitante); `setor_id`; `pagina`, `tamanho` (até 200); `ordem` e `direcao` (como em `GET /meus`).
- **Ordem:** prioridade (urgente primeiro), prazo de solução mais próximo, abertura mais antiga. Em `solucionados`, a solução mais recente primeiro.

### `ChamadoResumo`

| Campo | Tipo | Descrição |
|---|---|---|
| `id`, `numero` | uuid, integer | Identificação (as telas e as rotas usam o número) |
| `titulo` | string | "Chamado restrito" se a categoria for sigilosa e a pessoa não atender |
| `tipo`, `status_base`, `prioridade`, `prioridade_origem` | string | Ver Regras |
| `categoria_id`, `categoria_caminho` | uuid, string | Categoria e o caminho completo dela |
| `setor_id`, `setor_nome` | integer, string | Setor responsável |
| `responsavel_id`, `responsavel_nome` | integer \| null, string | Responsável pelo atendimento |
| `solicitante_id`, `solicitante_nome` | integer \| null, string | Solicitante |
| `aberto_em`, `solucionado_em` | date-time | |
| `atendimento`, `solucao` | `PrazoSla` | `{vence_em, cumprido_em, estourado, percentual}`; `percentual` = parte do prazo já consumida em horas úteis (pode passar de 100), nulo sem SLA |
| `importado` | boolean | Chamado vindo do GLPI (somente leitura) |

## `GET /api/chamados/{numero}`

O chamado, a linha do tempo e as ações que a pessoa pode fazer nele. `404` se não existir **ou** se a pessoa não o enxergar.

### Resposta `200 OK`: `ChamadoDetalhe` (= `ChamadoResumo` mais)

| Campo | Tipo | Descrição |
|---|---|---|
| `descricao` | string | HTML sanitizado (vazio para quem vê um chamado sigiloso sem atender) |
| `impedindo_trabalho` | boolean \| null | Resposta da abertura |
| `setor_solicitante_id`, `setor_solicitante_nome` | integer \| null, string | Setor em nome do qual foi aberto |
| `versao` | integer | Para `POST /assumir` (trava otimista) |
| `reabrir_ate` | date-time \| null | Fim da janela do "Não resolveu" |
| `anexos` | `AnexoLeitura[]` | Anexos da abertura: `{id, nome, tamanho, tipo_conteudo, privado}` |
| `linha_do_tempo` | `ItemLinhaTempo[]` | Em ordem: `{id, tipo (acompanhamento \| solucao), autor_id, autor_nome, texto, privado, automatico, criado_em, anexos}`; sem os privados para quem não atende |
| `acoes` | `{responder, responder_privado, assumir, solucionar}` | O que a tela pode oferecer |

## `POST /api/chamados/{numero}/assumir`

A pessoa vira a responsável pelo atendimento: status `em_atendimento`, prazo de atendimento cumprido, registro automático na linha do tempo e aviso ao solicitante.

- **Autorização:** quem atende o setor responsável. **Corpo:** `{ "versao": <versão mostrada> }`.
- **Erros:** `403`, `404`, `409 chamado_alterado` (outra pessoa assumiu ou alterou antes) ou `chamado_encerrado`.

## `POST /api/chamados/{numero}/acompanhamentos`

Resposta na linha do tempo. `multipart/form-data`: `dados` = `{ "texto", "privado" }` e até 10 `arquivos`.

- **Autorização:** quem vê o chamado; `privado: true` só para quem atende (`403` para os demais).
- A primeira resposta de quem atende cumpre o prazo de atendimento. Avisa o outro lado (ver Avisos).
- **Resposta `201 Created`:** `ChamadoDetalhe`. **Erros:** `400`, `403`, `404`, `409 chamado_encerrado`.

## `POST /api/chamados/{numero}/solucao`

Resolve o chamado (o fim). `multipart/form-data`: `dados` = `{ "texto" }` e até 10 `arquivos`. Sem responsável, quem resolve vira o responsável.

- **Autorização:** quem atende o setor responsável. **Resposta `201 Created`:** `ChamadoDetalhe`. **Erros:** `400`, `403`, `404`, `409 chamado_encerrado`.

## `GET /api/chamados/{numero}/anexos/{anexo_id}`

Baixa um anexo do chamado (o `id` vem de `AnexoLeitura`). Anexo de mensagem privada só para quem atende; para os demais, `404`.

---

## Parâmetros (Controle total)

Todas as rotas abaixo exigem o papel de administrar (`403 acesso_negado` para os demais).

| Método e caminho | Descrição |
|---|---|
| `GET /api/chamados/parametros/setores` | Setores ativos (oficiais e sistêmicos) com o caminho na hierarquia: todo setor ativo pode ser responsável |
| `GET` · `POST /api/chamados/parametros/expedientes` | Lista e cria. Corpo `GravacaoExpediente`: `{ nome, ativo, faixas: [{ dia_semana (0 = segunda … 6 = domingo), inicio, fim }] }`, com pelo menos uma faixa e sem sobreposição no mesmo dia. Nome único (`409`) |
| `PUT /api/chamados/parametros/expedientes/{expediente_id}` | Altera (vale para os próximos chamados) |
| `DELETE /api/chamados/parametros/expedientes/{expediente_id}` | Exclui (`204`) o expediente que nenhum SLA usa. Em uso: `409 em_uso` com os nomes dos SLAs (troque o expediente deles ou desative este) |
| `GET` · `POST /api/chamados/parametros/slas` | Lista e cria. Corpo `GravacaoSla`: `{ nome, tipo (tto \| ttr), tempo (> 0), unidade (minuto \| hora \| dia), expediente_id (obrigatório), ativo }`. Em `dia`, vence no fim do expediente do N-ésimo dia útil seguinte |
| `PUT /api/chamados/parametros/slas/{sla_id}` | Altera (os prazos já calculados não mudam) |
| `DELETE /api/chamados/parametros/slas/{sla_id}` | Exclui (`204`) o SLA que nenhuma categoria nem nenhum chamado usa. Em uso: `409 em_uso` dizendo onde (troque o SLA das categorias ou desative-o; o chamado guarda o SLA no histórico) |
| `GET` · `POST /api/chamados/parametros/categorias` | Lista (com `caminho`, `nivel`, `setor_efetivo_id`, `setor_efetivo_nome`, `herda_setor`) e cria. Corpo `GravacaoCategoria`: `{ nome, pai_id, ativa, visivel_solicitante, permite_incidente, permite_requisicao, setor_id, responsavel_id, sla_tto_id, sla_ttr_id, prioridade_padrao, perguntar_impedindo, sigilosa, ordem }`. Campos vazios herdam da categoria-mãe |
| `PUT /api/chamados/parametros/categorias/{categoria_id}` | Altera, renomeia ou move (recalcula o caminho da subárvore). Desativar não apaga e exige as subcategorias já inativas (`409`) |
| `DELETE /api/chamados/parametros/categorias/{categoria_id}` | Exclui (`204`) a categoria sem subcategorias e sem chamados. Com subcategorias ou já usada em chamados: `409 em_uso` (desative-a; o histórico aponta para ela) |

Regras que impedem configuração errada: `400 categoria_sem_setor` para categoria ativa sem setor responsável (próprio ou herdado), inclusive quando tirar o setor de uma
mãe deixaria uma filha ativa sem setor; `409 conflito` para nome repetido no mesmo nível; SLA sem expediente é recusado na validação (`422`); a categoria não pode ficar
dentro de si mesma (`400`); o SLA escolhido precisa ser do tipo certo.

## Integração com Setores

`servico_setores.substituir_estrutura` (recarga do organograma oficial) **não apaga setor citado pelo módulo Chamados** (responsável ou solicitante de chamado,
responsável de categoria, ajustes de atendimento): se o nome continua na estrutura nova, o setor é reaproveitado com o mesmo id; se não continua, fica inativo.
O resumo da recarga ganhou `setores_reaproveitados` e `setores_inativados_em_uso`. Ver [setores.md](setores.md).

Erros no formato `{"detalhe", "codigo"}`. Telas: `/chamados` (abrir), `/chamados/meus`, `/chamados/fila`, `/chamados/{numero}`, `/chamados/parametros`.

---

## Marco 2: atendimento completo

### Regras
- **Pendente** (`POST /{numero}/pendente`, `motivo` opcional): pausa o prazo de solução. Ao retomar (`POST /{numero}/retomar`), ou quando o
  **solicitante responde**, o tempo útil parado (`espera_minutos_uteis`) é somado e empurra o prazo de solução pelo mesmo tanto. Enquanto pendente,
  o percentual do prazo fica congelado (`PrazoSla.pausado = true`). Resolver um chamado pendente fecha a pausa.
- **"Não resolveu"** (`POST /{numero}/nao-resolveu`, `motivo` com 5+ caracteres): o solicitante (ou alguém do setor solicitante) reabre o mesmo chamado
  até `reabrir_ate` (fim do dia, `dias_reabrir` dias úteis depois da solução; padrão 5). A solução anterior fica `substituida`, `reaberturas` soma 1 e o
  prazo de solução recomeça da reabertura. Depois do prazo: `409 prazo_reabertura` (abra um chamado novo, relacionado a este).
- **Chamado relacionado** (`relacionado_id` na abertura): só um chamado do próprio solicitante (`400 relacionado_invalido` para o de outra pessoa).
- **Local** (`localizacao_id` na abertura): uma sala ativa do Patrimônio (`400 local_invalido`). A sala sugerida vem de `GET /abertura/contexto`:
  a sala de que a pessoa é responsável; senão, a sala com mais bens sob a responsabilidade dela; senão, a única sala do setor dela.
- **Campos adicionais** (`campos` na abertura, `{campo_id: valor}`): os da categoria e os herdados das categorias acima. Obrigatório vazio:
  `400 campo_obrigatorio`. Campo com `condicao` só aparece (e só é exigido) quando o outro campo tem o valor indicado. Tipos: `texto` (até 300),
  `texto_longo`, `numero`, `data` (AAAA-MM-DD), `lista` (uma das opções) e `sim_nao`. **Dado pessoal**: vem **mascarado para todos**
  (`RespostaCampo.mascarado = true`); quem atende (`pode_revelar = true`) pede o valor completo em `GET /{numero}/dados-pessoais/{campo_id}`, e cada
  consulta registra `chamados.dado_pessoal` na auditoria.
- **Em cópia** (`POST /{numero}/em-copia` com `usuario_id` **ou** `setor_id`; `DELETE /{numero}/em-copia/{ator_id}`): quem atende ou quem pediu inclui;
  quem atende, quem pediu ou a própria pessoa tira. Quem está em cópia vê o chamado, recebe os avisos pelo canal que escolheu e o chamado aparece
  em `GET /meus`.
- **Tarefas** (`POST /{numero}/tarefas`, `PATCH /{numero}/tarefas/{tarefa_id}` com `{feita}`): só quem atende; privadas por padrão (o solicitante não vê).
- **Aprovação** (`POST /{numero}/aprovacoes` com `alvo_usuario_id` **ou** `alvo_setor_id` e o `pedido`): o chamado fica `em_aprovacao` e quem aprova
  passa a ver o chamado. `GET /aprovacoes/minhas` lista o que aguarda a pessoa (ou um setor dela); `POST /aprovacoes/{validacao_id}/responder`
  com `{aprovar, resposta}` (não aprovar exige motivo; já respondida: `409 ja_respondida`). Sem outra aprovação aguardando, o chamado volta ao atendimento.
- **Alterar** (`PATCH /{numero}`, só os campos enviados, com `versao`): `responsavel_id` (pessoa ativa do setor responsável, senão
  `400 responsavel_invalido`; `null` tira), `setor_id` (o responsável que não é do setor novo sai; os membros do setor novo recebem o aviso, com e-mail),
  `categoria_id` (reaplica setor, SLAs e prioridade da categoria nova, mantendo o tempo pendente descontado) e `prioridade` (exige
  `motivo_prioridade`, senão `400 motivo_obrigatorio`; `prioridade_origem` vira `responsavel`). Responde `null` se a pessoa deixar de ver o chamado.

### Endpoints novos

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/chamados/abertura/contexto` | Qualquer papel | `{ local_sugerido: {id, rotulo} \| null, relacionaveis: [{id, numero, titulo, status_base, aberto_em}] }` |
| `GET /api/chamados/locais?busca=&limite=` | Qualquer papel | Salas ativas do Patrimônio (código, nome ou setor), até `limite` (padrão 20, máximo 2000): `[{id, rotulo, codigo, andar}]`. A abertura pede todas para o campo **"Onde podemos te encontrar?"** (logo abaixo do título, já com a sala da pessoa pelo Patrimônio), agrupadas por andar |
| `GET /api/chamados/pessoas?busca` | Qualquer papel | Até 20 usuários ativos `{id, nome, login, cargo}` (em cópia, aprovação, tarefas). Na tela, toda escolha de pessoa usa o seletor de usuários do sistema (o mesmo da Equipe do contrato) |
| `GET /api/chamados/setores` | Qualquer papel | Setores ativos com o caminho |
| `GET /api/chamados/aprovacoes/minhas` | Qualquer papel | Aprovações aguardando a pessoa ou um setor dela |
| `POST /api/chamados/aprovacoes/{validacao_id}/responder` | Aprovador | `{aprovar, resposta}` → `ChamadoDetalhe` |
| `PATCH /api/chamados/{numero}` | Quem atende | Alterar (ver Regras) → `ChamadoDetalhe \| null` |
| `GET /api/chamados/{numero}/responsaveis` | Quem atende | Membros ativos do setor responsável |
| `POST /api/chamados/{numero}/pendente` · `/retomar` | Quem atende | Pausa e retoma o prazo |
| `POST /api/chamados/{numero}/nao-resolveu` | Solicitante | Reabre (ver Regras) |
| `POST /api/chamados/{numero}/em-copia` · `DELETE …/em-copia/{ator_id}` | Ver Regras | Em cópia |
| `POST /api/chamados/{numero}/tarefas` · `PATCH …/tarefas/{tarefa_id}` | Quem atende | Tarefas |
| `POST /api/chamados/{numero}/aprovacoes` | Quem atende | Pedir aprovação |
| `GET /api/chamados/{numero}/dados-pessoais/{campo_id}` | Quem atende | `{valor}` completo, auditado |
| `GET` · `POST /api/chamados/parametros/categorias/{categoria_id}/campos` | Controle total | Campos da categoria (sem os herdados) e criar (`GravacaoCampo`: `rotulo, tipo, obrigatorio, dado_pessoal, ajuda, opcoes, condicao {campo_id, igual}, ordem, ativo`) |
| `PUT` · `DELETE /api/chamados/parametros/categorias/{categoria_id}/campos/{campo_id}` | Controle total | Alterar; excluir só o que nenhum chamado respondeu (`409 em_uso`) |

`ChamadoDetalhe` ganhou: `local`, `relacionado`, `campos` (`RespostaCampo`: `campo_id, rotulo, valor, dado_pessoal, mascarado, pode_revelar`), `em_copia`
(`{id, usuario_id, setor_id, nome}`), `tarefas` (as privadas só para quem atende), `validacoes` (com `posso_responder`), `reaberturas`, `pendente_desde`
e as ações `pendente, retomar, nao_resolveu, alterar, tarefas, pedir_aprovacao, incluir_em_copia`. `CategoriaCatalogo` ganhou `campos`
(`CampoAdicional`). `AberturaChamado` ganhou `relacionado_id`, `localizacao_id` e `campos`. O tipo (`incidente`/`requisicao`) **não** é perguntado
na tela: vem da categoria.

---

## Marco 3: Parâmetros completos e tarefas automáticas

### Tarefas automáticas
- **`minuto`** (timer a cada minuto):
  - prazo de **atendimento** vencido sem nenhuma ação de quem atende → `tto_estourado_em` e aviso ao setor responsável;
  - prazo de **solução** vencido (fora do pendente) → `ttr_estourado_em`, **prioridade Urgente** (`prioridade_origem = sla`), registro automático
    na linha do tempo e aviso ao responsável (ou ao setor), também por e-mail. Reabrir ("Não resolveu") zera a marca;
  - **recorrentes** devidos: abre o chamado em nome do solicitante do recorrente, `antecedencia_min` minutos antes da ocorrência. A dupla
    `(recorrente_id, gerado_para)` é única no banco (rodar duas vezes não duplica). Depois de uma parada longa, gera só a ocorrência devida mais
    recente e segue para a próxima futura. Passado o `fim_em`, o recorrente se desativa.
  - **resumo do líder** (`chamados.resumo_lider`): no começo de cada dia útil (a partir das 7h de São Paulo, parâmetro `resumo_lider_hora`;
    fim de semana e feriado do RH, não), o líder de cada setor recebe por e-mail a lista dos chamados em aberto em que o setor é o responsável.
    Uma vez por dia; setor sem chamado aberto não gera e-mail.
- **`vigia`** (timer a cada 5 minutos): encerra rodadas "rodando" há mais de 15 minutos e, se `GET /saude` tiver problemas, avisa pelo sino quem
  administra os Chamados.
- Cada rodada fica em `chamados_execucoes` (mantidas 30 dias).

### Regras dos Parâmetros
- **Geral** (`GET`/`PUT /parametros/geral`): `dias_reabrir` (1–30), `ponto_facultativo_util`, e os limites de cor do prazo `limite_alerta` <
  `limite_atencao` < `limite_perigo` ≤ 100 (padrão 50/75/90). `PrazoSla.nivel` (`sem`, `ok`, `alerta`, `atencao`, `perigo`, `cumprido`) já vem
  calculado com esses limites.
- **Atendimento no SGI "a partir de"** (`inicio_atendimento`, Geral): a virada sem migração. Com a data marcada e ainda no futuro, só quem tem
  **Controle total** abre chamado no SGI (testes e treinamento); os demais recebem `409 antes_do_inicio` em `POST /api/chamados`, a tela de abertura
  avisa e oferece o formulário do GLPI, e o "Abrir chamado" do sistema continua indo para o GLPI. A partir da data (horário de São Paulo), todos
  abrem no SGI; as equipes terminam os pendentes no próprio GLPI. Sem data marcada, vale só o papel da ACL (como antes). Os chamados do RH seguem a
  chave própria (Parâmetros > RH > destino). A migração pelo botão fica desativada (os chamados que ela trouxe foram excluídos).
- **Status**: os 5 status-base são fixos; `PUT /parametros/status/{status}` muda só o **nome exibido** e a **cor** (token: `info`, `alerta`,
  `atencao`, `perigo`, `sucesso`, `neutro`). **Sub-status** (`/parametros/substatus`) ficam dentro de um status-base; quem atende escolhe pelo
  `PATCH /{numero}` (`substatus_id`; de outro status-base: `400 substatus_invalido`). `ChamadoResumo` ganhou `status_nome` (ex.: "Em atendimento ›
  Aguardando peça"), `status_cor` e `substatus_id`. O sub-status só vale enquanto o chamado está no status-base dele.
- **Setores de atendimento** (`/parametros/setores-atendimento`): todo setor ativo atende; o ajuste `ve_todos` faz os membros que atendem verem os
  chamados de todos os setores.
- **Recorrentes** (`/parametros/recorrentes`): `nome, categoria_id, titulo, descricao, periodicidade_quantidade, periodicidade_unidade (dia | semana |
  mes), antecedencia_min (0–10080), so_dias_uteis (pula fim de semana e feriado do RH mantendo o horário), proxima_em, fim_em, ativo,
  solicitante_id`. Excluir mantém os chamados já gerados.

### Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET` · `PUT /api/chamados/parametros/geral` | Controle total | Parâmetros gerais (ver Regras) |
| `GET /api/chamados/parametros/status` · `PUT …/status/{status}` | Controle total | Nome e cor dos status-base |
| `GET /api/chamados/substatus` | Qualquer papel | Sub-status (para escolher no chamado) |
| `POST /api/chamados/parametros/substatus` · `PUT` · `DELETE …/{substatus_id}` | Controle total | Sub-status (excluir deixa os chamados só no status-base) |
| `GET /api/chamados/parametros/setores-atendimento` · `PUT …/{setor_id}` | Controle total | Ajuste `ve_todos` por setor |
| `GET` · `POST /api/chamados/parametros/recorrentes` · `PUT` · `DELETE …/{recorrente_id}` | Controle total | Chamados recorrentes |
| `GET /api/chamados/saude` | Controle total | `{ tarefas: [{tarefa, ultima_em, ultimo_estado, ultima_ok_em, ultimo_erro, ultimo_resumo}], email_parados, email_falhas_24h, email_mais_antigo, ultimo_erro_email, problemas[] }` |

## Marco 4: tempo real, painel e RH

### Tempo real (SSE)
- Cada chamado **aberto ou alterado** (inclusive por resposta, solução, tarefa, aprovação ou cópia) gera um evento **depois do commit**; nada sai
  de uma transação desfeita. No PostgreSQL o evento vai pelo canal `sgi_chamados` (`pg_notify`/`LISTEN`), então chega aos dois workers da API e
  também sai das tarefas automáticas (prazo estourado aparece ao vivo).
- O evento só leva `{"tipo": "novo" | "alterado", "numero", "acao"}`. A tela busca o resto pela rota normal, que confere a visibilidade.
  `acao` diz o que aconteceu de marcante, para o painel falar: `assumido` (ganhou ou trocou de responsável), `resolvido`, `reaberto`,
  `transferido` (mudou de setor responsável) ou vazio (resposta, tarefa, prioridade...). Na transferência, quem atende o **setor de antes**
  também recebe o evento (o chamado sai do painel dele na hora).
- Formato: `text/event-stream`, com `event: chamado` + `data: {...}`, um comentário `: ping` a cada 20 s e `retry: 5000`. Cada conexão dura até
  30 min; a tela reconecta sozinha e a autorização é conferida de novo. Cabeçalho `X-Accel-Buffering: no` (o Nginx não segura o fluxo).
- Quem recebe, em `GET /eventos`: solicitante, setor solicitante, responsável pelo atendimento, quem atende o setor do chamado e, para quem
  atende, os setores do seu painel. *Quem está só em cópia não recebe ao vivo* (vê a mudança ao abrir o chamado).

### Painel (sempre com login)
- **Quem aparece:** os chamados em que o **setor responsável** é um setor de que a pessoa é membro, ou um setor abaixo dele. Nada fica fixo
  no código: cada pessoa vê o painel do seu setor (quem só abre chamados também tem o seu, normalmente vazio). `setor_id` escolhe um desses
  setores; quem administra escolhe qualquer um ou, sem `setor_id`, vê todos.
- A TV da sala fica **logada com a conta de alguém do setor**, em tela cheia. A TV pareada sem login (marco 4) foi retirada a pedido do usuário
  (migração `d7f9b1c3e5a8` apaga `chamados_paineis`).
- Linhas: **só os abertos** (o resolvido não aparece; conta só em "resolvidos hoje"). O importado do GLPI não entra.
- `nivel` da linha = o pior entre os prazos de atendimento e de solução, pelos limites da aba Geral (50/75/90).
- **Ordem sempre pela cor:** todos os vermelhos, depois os laranjas, os amarelos e os brancos (no prazo ou sem prazo); dentro da mesma cor,
  quem gastou mais do prazo e, empatando, o mais antigo.
- Navegável: a tela troca de página sozinha, mas também pelos botões ou pelas setas do teclado (a troca automática pausa um minuto), e cada
  linha abre o chamado.
- Indicadores: `abertos`, `sem_responsavel`, `estourados` e `resolvidos_hoje` (desde 0h de São Paulo).
- Título de categoria sigilosa sempre oculto; solicitante e responsável só com os **dois primeiros nomes**.
- **Exibição** (`config`, Parâmetros > Painel): `linhas_por_pagina` (0 = automático, quantas couberem), `tamanho` (`compacto`, `normal`,
  `grande`), `segundos_pagina` (5–300), `voz`, `cor_linha` (cor na linha inteira ou só no selo) e `colunas` (abaixo).
- **Voz** (com `voz` ligada): "Novo chamado de Maria Aparecida", "Chamado 123 assumido por João Silva", "Chamado 123 resolvido",
  "Chamado 123 reaberto" e "Chamado 123 transferido para este painel"; a linha que mudou ganha destaque por 8 s. Ao abrir ou recarregar o
  painel nada é falado; o chamado transferido para outro setor só sai da lista.
- Colunas possíveis: (`abertura`, `titulo`, `usuario`, `local`, `espera`, `situacao`, `responsavel`; o título é obrigatório).

### Chamados do RH (Nomeação e Exoneração)
- `rh_destino`: `glpi` (padrão, como hoje), `chamados` ou `na_data`. Com `na_data`, o RH segue a data "Atendimento no SGI a partir de"
  (Parâmetros > Geral): antes dela envia ao GLPI e, no dia, passa a abrir aqui, sozinho. Exige a data marcada (400) e fila em todo serviço (409).
  O `GET` devolve também `destino_atual` (`glpi` ou `chamados`): para onde o RH envia agora. O RH (admissão e exoneração) sempre lê esse destino atual.
- Cada serviço (9 da Nomeação e 9 da Exoneração) tem, nos Parâmetros > RH, a sua **fila** (`setor_id`: o setor que atende), a **prioridade**
  (`baixa`, `normal`, `alta`, `urgente`) e os **prazos** (`sla_tto_id`, prazo de atendimento, e `sla_ttr_id`, prazo de solução; vazio = sem prazo).
  O chamado já nasce nessa fila, com essa prioridade e esses prazos, sem passar pelas regras do assunto. Para ligar `chamados`, todos os serviços
  dos dois fluxos precisam de fila ativa (`409 servico_sem_fila`); setor inexistente ou inativo e SLA do tipo errado: 400.
- Os chamados do RH entram nos assuntos fixos **"Nomeação (RH)"** e **"Exoneração (RH)"**, criados sozinhos pelo SGI, inativos e invisíveis
  para quem abre chamado. Eles só existem porque todo chamado precisa de um assunto, e servem para agrupar esses chamados nos relatórios e filtros.
- Com `chamados`, `POST /api/rh/admissoes/{id}/chamado` abre um chamado por serviço marcado (título "Serviço: Nome"), com `admissao_id` e
  `servico_rh`. CPF, RG, RS e e-mail pessoal ficam numa **nota privada**. A admissão mostra o status de cada chamado ao vivo
  (ver [rh-admissao.md](rh-admissao.md)).
- **Exoneração** (só com o destino `chamados`): o inverso da Nomeação, um chamado por serviço marcado ("Desativar usuário de rede",
  "Recolher crachá"...), com `rh_ocupacao_id` e `servico_rh`. A tela sugere o que foi pedido na nomeação da pessoa (ver [rh-cargos.md](rh-cargos.md)).
  `PUT /parametros/rh` recebe também `servicos_exoneracao`, e `GET` devolve `servicos_exoneracao`; para ligar `chamados`, os dois fluxos precisam de fila.

### Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/chamados/eventos` | Qualquer papel | Fluxo SSE (ver Tempo real). O `EventSource` não manda `Authorization`: o frontend lê com `fetch` |
| `GET /api/chamados/painel?setor_id=` | Qualquer papel | `{ area, gerado_em, config, limites{alerta,atencao,perigo}, indicadores{abertos,sem_responsavel,estourados,resolvidos_hoje}, itens[{numero, titulo, solicitante, responsavel, local, setor_nome, aberto_em, solucionado_em, status_base, status_nome, prioridade, nivel, percentual, estourado, pausado}] }`; `setor_id` fora do alcance: 403; Controle total sem `setor_id`: todos |
| `GET` · `PUT /api/chamados/parametros/painel` | Controle total | `ConfigPainel` (ver Painel); sem o título nas colunas: 400 |
| `GET` · `PUT /api/chamados/parametros/rh` | Controle total | `{destino, destino_atual, servicos[{servico, rotulo, setor_id, setor_nome, prioridade, sla_tto_id, sla_ttr_id}], servicos_exoneracao[...]}` / grava `{destino, servicos{servico: {setor_id, prioridade, sla_tto_id, sla_ttr_id}}, servicos_exoneracao{...}}`; sem fila com destino `chamados` ou `na_data`: 409 `servico_sem_fila`; `na_data` sem a data "a partir de": 400 |

## Marco 5: histórico do GLPI

Sem endpoint novo: a importação é feita por script, a partir de um dump (guia completo e roteiro da virada em
[importacao-glpi-chamados.md](../importacao-glpi-chamados.md)). O que muda na API:
- chamado importado: `importado = true`, número do GLPI, **somente leitura** (`409 chamado_encerrado` em qualquer ação) e prazos do GLPI
  (o SLA não é recalculado nem estoura);
- a fila (`GET /fila`) **não mostra o importado** nos filtros de trabalho (`abertos`, `meus`, `setor`, `novos`, `sem_responsavel`); ele
  aparece em `solucionados` e `todos`, e pela busca em "Meus chamados". O painel de TV também não mostra.

## Marco 6: satisfação, respostas prontas, motivos de pendência e relatórios

### Regras
- **Satisfação:** resolver o chamado cria a pesquisa (resolver de novo, depois do "Não resolveu", pede outra vez). O solicitante ou alguém do
  setor solicitante dá a nota com um clique: 1 Péssimo, 2 Ruim, 3 Regular, 4 Bom, 5 Ótimo, e pode comentar. Pode mudar a nota enquanto o chamado
  estiver resolvido. `ChamadoDetalhe.satisfacao = {nota, rotulo, comentario, respondida_em, pode_avaliar}` (nula antes de resolver). O aviso de
  "resolvido" convida a dar a nota. A importação do GLPI traz as notas antigas (escala de 5).
- **Respostas prontas:** sem setor, valem para todos os que atendem; com setor, só para quem atende aquele setor. O texto é HTML saneado.
- **Motivos de pendência:** lista para escolher no "Pendente" (o texto escolhido vai no campo `motivo`; quem atende ainda pode escrever outro).
- **Relatórios:** período padrão de 30 dias (até 1 ano), inclui o histórico importado. **Quem escolhe setor** (`pode_escolher_setor`):
  Controle total (qualquer setor; sem `setor_id`, todos) ou **líder de um setor que tem setores abaixo** (o dele e os de baixo; `setores_opcoes`).
  Só essas pessoas veem `por_setor` e `por_prioridade` (para as demais vêm vazios). **Os demais** veem só o próprio setor, sem escolha
  (`setor_id` de outro setor: 403). A exportação segue o mesmo escopo.
  **Equipe** (`equipe`, até 12 pessoas, as que mais resolveram nos últimos 30 dias): `resolvidos_*` = soluções registradas pela pessoa;
  `assumidos_*` = chamados que estão com ela e foram assumidos na janela; janelas `7d` e `30d` (terminando no fim do período) e `semana`
  (média por semana no período). Entram os membros dos setores do relatório, mesmo zerados. Cada semana traz também `em_aberto_fim` (fila
  no fim da semana, sem o importado), `reabertos`, `horas_mediana_solucao` e `atendimento_no_prazo_pct`, para as minisséries dos cartões. "No prazo de solução" compara a
  solução com o prazo gravado (o pendente já empurra o prazo); a mediana de solução é em horas corridas. O botão **Exportar** abre um modal com
  data de início e fim, setor, "Sem solução" / "Com solução" e o formato (PDF ou XLSX).

### Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `POST /api/chamados/{numero}/satisfacao` | Solicitante / setor solicitante | `{nota: 1..5, comentario?}` → `ChamadoDetalhe`. Antes de resolver: `409 chamado_aberto`; de outra pessoa: 403 |
| `GET /api/chamados/respostas-prontas` | Modificação | `[{id, titulo, texto, setor_id, setor_nome, ativo, ordem}]` (só as que valem para a pessoa) |
| `GET /api/chamados/motivos-pendencia` | Modificação | `[{id, nome, ativo, ordem}]` (ativos) |
| `GET /api/chamados/relatorios?inicio=&fim=&setor_id=` | Modificação | `{area, inicio, fim, pode_escolher_setor, setores_opcoes[{id, nome}], equipe[{usuario_id, nome, resolvidos_7d, assumidos_7d, resolvidos_30d, assumidos_30d, resolvidos_semana, assumidos_semana}], resumo{abertos_no_periodo, resolvidos_no_periodo, em_aberto_agora, atendimento_no_prazo(_pct), atendimento_com_prazo, solucao_no_prazo(_pct), solucao_com_prazo, horas_mediana_solucao, reabertos, satisfacao_media, satisfacao_respostas, satisfacao_pedidas}, semanas[{inicio, abertos, resolvidos, em_aberto_fim, reabertos, horas_mediana_solucao, atendimento_no_prazo_pct}], por_categoria[{nome, abertos, resolvidos, no_prazo_pct}], por_setor[...], por_prioridade{}, notas[5]}`. Período invertido ou maior que 1 ano: 400 |
| `GET /api/chamados/relatorios/exportar?inicio=&fim=&setor_id=&com_solucao=&formato=` | Modificação | Arquivo (`pdf` em A4 paisagem com a identidade do sistema, ou `xlsx`) com os chamados **abertos** no período, no mesmo escopo do relatório: Nº, título, descrição (texto sem formatação; no PDF até 1.500 caracteres), solicitante, setor responsável, responsável e status (nome dos Parâmetros); `com_solucao=true` acrescenta a solução vigente. Título "Chamados {setor} - {início} a {fim}" (sem setor: "Meus setores" ou "Todos os setores"). `inicio` e `fim` obrigatórios; período invertido ou maior que 1 ano: 400; formato inválido: 422. Notas privadas nunca entram |
| `GET` · `POST /api/chamados/parametros/respostas-prontas` · `PUT` · `DELETE …/{resposta_id}` | Controle total | `{titulo, texto, setor_id, ativo, ordem}` |
| `GET` · `POST /api/chamados/parametros/motivos-pendencia` · `PUT` · `DELETE …/{motivo_id}` | Controle total | `{nome, ativo, ordem}`; nome repetido: 409 `duplicado` |

## Marco 7: porta e ponto de rede no chamado

`POST /api/chamados` aceita `rede_porta_id` e `rede_ponto_id` (opcionais; inexistente: `400 porta_invalida` / `ponto_invalido`). A porta
mostra os chamados dela e do ponto no plano de face ([rede.md](rede.md)).

## Categoria ITIL (classificação técnica)

- **Separada do assunto.** A **categoria** (assunto) é o que quem abre escolhe (Impressoras, Crachás...). A **categoria ITIL** é a classificação
  técnica (Infraestrutura › Servidores, Redes › Wi-Fi, Acessos › Liberação de acesso), numa árvore própria nos Parâmetros (aba "Categorias ITIL").
  As categorias do GLPI entram nessa árvore na migração, e não nos assuntos.
- **Quem pode escolher o assunto** (`setores_permitidos` na categoria): vazio = vale `visivel_solicitante` (qualquer pessoa ou, desmarcado, só quem
  atende); com setores = **só os membros deles e dos setores abaixo** veem e abrem (ex.: "CGP > Nomeação" só para a CGP; quem atende de outro setor
  também não vê). Vale para a categoria e para cada ancestral. Controle total vê todos; a troca de assunto feita por quem atende não é restrita.
  Setor inexistente ou inativo: 400. Migração `c8e0a2b4d6f7` (`chamados_categorias_setores`).
- **Padrão no assunto:** cada assunto pode ter `categoria_itil_id` (vazio = herda da mãe; sem nenhuma, o chamado nasce **pendente**). Trocar o
  assunto de um chamado ainda pendente aplica a ITIL do assunto novo; a que o técnico já escolheu não muda.
- **Quem vê e classifica:** só quem atende o chamado (`acoes.classificar`), também depois de resolvido. O solicitante não recebe
  `categoria_itil_id`/`categoria_itil` e não vê a nota da classificação (vai para a linha do tempo como **nota privada**). Filtro `sem_itil` na fila.

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET` · `POST /api/chamados/parametros/categorias-itil` · `PUT` · `DELETE …/{itil_id}` | Controle total | `{nome, pai_id, ativa, ordem}` (+ `caminho`, `nivel`, `chamados` na leitura). Nome único no nível (`409 conflito`), sem ">"; mover para dentro de si: 400; desativar com filha ativa: 409; excluir com filhas ou com chamados: `409 em_uso` |
| `GET /api/chamados/categorias-itil` | Modificação | As ativas `[{id, caminho}]`, para classificar |
| `PUT /api/chamados/{numero}/categoria-itil` | Quem atende | `{versao, categoria_itil_id}` (`null` = pendente) → `ChamadoDetalhe`. Versão antiga: `409 chamado_alterado` |

## Migração do GLPI pelo botão (Parâmetros, Controle total)

Aba "Migração do GLPI" nos Parâmetros. Lê o banco MariaDB do GLPI com um usuário **só de leitura** (nada é gravado lá; a sessão também é
`READ ONLY`) e traz os chamados em **segundo plano**, com um modal de andamento (etapas, barra e "X de Y chamados do GLPI conferidos").

- **Trazer novidades** (`novidades`): os chamados novos e os que **mudaram no GLPI** desde a última migração (data de alteração do chamado ou de um
  acompanhamento, solução, tarefa, aprovação ou pesquisa). O que mudou é regravado: campos e filhos vindos do GLPI; os ids de acompanhamentos e
  soluções se mantêm. Na primeira vez, traz tudo.
- **Refazer do zero** (`refazer`): apaga **todos** os chamados, os importados **e os abertos no próprio SGI** (com acompanhamentos, soluções,
  tarefas, aprovações, satisfação e cópias; os arquivos anexos têm exclusão lógica e ficam em disco), e traz o GLPI de novo. Serve para
  demonstração e treinamento; a tela pede confirmação com espera. Categorias, assuntos, SLAs e demais Parâmetros ficam.
- **Só os não solucionados** (padrão, `so_abertos`): chamado **novo** já resolvido ou excluído no GLPI não vem (`resumo.resolvidos_nao_migrados`).
  O que já veio continua sendo atualizado: resolvido depois no GLPI fica resolvido aqui também (se ninguém mexeu nele no SGI). Desmarcado,
  traz também o histórico.
- **Abertos × resolvidos:** o chamado **resolvido** no GLPI entra como histórico **somente leitura**; o **ainda aberto** entra como chamado
  **normal** do SGI (painel, fila, assumir, responder, resolver). Depois de trabalhado aqui (a versão subiu: assumido, respondido, alterado),
  "Trazer novidades" **não o sobrescreve** mais (`resumo.trabalhados_sgi`).
- **Casamento automático:** pessoa pelo login (ou e-mail), grupo pelo nome do setor, etiqueta pelo nome de uma única pessoa (as mesmas sugestões
  do script). **Categorias do GLPI viram categorias ITIL** (atualizadas pelo id de origem); o assunto dos importados é "Importados do GLPI" (inativo).
  Setor do chamado: o grupo atribuído, senão o grupo da categoria no GLPI, senão o **setor padrão**. Anexos ficam no GLPI.
- **Tudo ou nada:** a execução roda numa transação só; erro no meio não grava nada. Uma por vez (o andamento fica num arquivo que os dois
  workers leem, como o Backup geral). Fica na auditoria (`chamados.migracao_glpi`).
- **Desligável:** `ativa = false` esconde os botões e as rotas de teste e execução respondem `409 desativada` (a configuração fica guardada).

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/chamados/parametros/migracao-glpi` | Controle total | `{ativa, host, porta, banco, usuario, setor_padrao_id, so_abertos, senha_cadastrada, ultima_sincronizacao, andamento{modo, situacao, etapa, mensagem, percentual, chamados_migrados, chamados_total, resumo{novos, atualizados, sem_mudanca, trabalhados_sgi, resolvidos_nao_migrados, categorias_itil, acompanhamentos, solucoes, avisos[], total_avisos}, iniciado_em, atualizado_em, autor}}`. A senha nunca volta |
| `PUT /api/chamados/parametros/migracao-glpi` | Controle total | `{ativa, host, porta, banco, usuario, senha?, setor_padrao_id, so_abertos}`; senha vazia mantém a cadastrada (guardada cifrada) |
| `POST /api/chamados/parametros/migracao-glpi/testar` | Controle total | Conecta e devolve `{versao, chamados}`; sem conexão: `400 sem_conexao`; desativada: `409` |
| `POST /api/chamados/parametros/migracao-glpi/executar` | Controle total | `{modo: novidades \| refazer}` → `202` e começa em segundo plano (`refazer` apaga **todos** os chamados antes). `409 em_andamento`, `409 desativada`, `400 sem_configuracao` |

**Usuário só de leitura no GLPI** (criado pela equipe do GLPI, não pelo SGI), por exemplo:
`CREATE USER 'sgi_leitura'@'<ip do SGI>' IDENTIFIED BY '…'; GRANT SELECT ON helpdesk.* TO 'sgi_leitura'@'<ip do SGI>';`
e a porta 3306 liberada só para o servidor do SGI.

