# Notificações (`/api/notificacoes`)

Tag no OpenAPI: **Notificações**. Implementação:
- rotas: `backend/app/api/routes/notificacoes.py` (caixa e envio), `notificacoes_preferencias.py` (preferências, navegador, testar, silenciar, obrigatórias e painel) e `notificacoes_cliente_windows.py` (compatibilidade com o SGI Alertas);
- regras: `backend/app/services/notificacoes/` (`caixa`, `catalogo`, `preferencias`, `despacho`, `navegador`, `layout_email`);
- avisos dos contratos: `backend/app/services/contratos/avisos.py`;
- tarefas agendadas: `backend/app/tarefas/notificacoes.py`;
- modelos: `backend/app/models/notificacao.py` (`notificacoes` e `notificacoes_entregas`) e `notificacao_preferencias.py` (`notificacoes_preferencias`, `notificacoes_config_usuario`, `notificacoes_inscricoes_navegador`, `notificacoes_silenciados` e `notificacoes_obrigatorias`).

É a caixa de notificações de cada usuário. Reúne comunicados escritos por usuários (**avulsas**) e avisos gerados pelo sistema (**automáticas**).

**Nenhuma mensagem bloqueia a navegação.** Avisos de pendência se encerram sozinhos quando a ação é feita no sistema.

## Conceitos

- **Mensagem e entrega:**
  - a mensagem é o conteúdo publicado;
  - cada destinatário recebe uma **entrega** com a fotografia do assunto e do texto.
  - Os `id` das rotas de caixa (`/{entrega_id}`) são de **entregas**. Entregas de outro usuário respondem `404`.
- **Estados da entrega (`estado`):**
  - `nao_visualizada`;
  - `visualizada`: a mensagem foi aberta;
  - `ciente`: o usuário clicou em "Li e estou ciente";
  - `encerrada`: pendência resolvida pela própria ação no sistema.
  - `pendente` = sem ciência e sem encerramento.
- **Prioridade:** `baixa`, `normal`, `alta` ou `critica`.
- **Categoria:** `comunicado`, `prazo`, `pendencia`, `revisao`, `atribuicao`, `indisponibilidade` ou `normativo`.
- **Expiração (`expira_em`):** depois dela, a mensagem some das caixas.
- **Link (`link`):** sempre um caminho interno (`/…`).
- **Janela (`abrir_em_janela`):** o aviso abre um modal na próxima vez que o usuário usa o sistema.
  - Ao aparecer, conta como lido e não abre de novo. Continua pendente até a ciência.

## Canais e preferências

- **A caixa (o sino) recebe sempre.** Os canais **e-mail**, **navegador** (Web Push) e **desktop** (cliente Windows SGI SPI Alertas) são opcionais e **começam desmarcados**. Exceção: a migração `f1a7c3e9b4d6` ligou o **navegador** (em todos os eventos que o aceitam) para os usuários que já existiam em 13/10/2026; quem foi criado depois começa desmarcado e cada pessoa pode desmarcar.
- Cada pessoa liga o que quiser **por evento** (matriz evento × canal, agrupada por módulo, em `/notificacoes` › aba **Preferências**). Existir a linha em `notificacoes_preferencias` = ligado; sem linha = desligado.
- Cada notificação automática nasce de um **evento do catálogo** (`backend/app/services/notificacoes/catalogo.py`, chave `modulo.evento`, ver a lista abaixo). `notificar(..., evento=...)` é obrigatório e confere a chave; o parâmetro `email=` não existe mais.
- Na entrega, o sistema calcula os canais do destinatário: `(preferência ∪ obrigatórias) − silenciados`, limitados aos `canais_disponiveis` do evento (as novidades do sistema só saem por e-mail), e grava uma **fotografia** em `canal_email`, `canal_navegador` e `canal_desktop` da entrega.
- **E-mail:** frequência `imediato` (um e-mail por notificação, layout oficial), `diario` (resumo às 7h) ou `semanal` (resumo na segunda-feira, às 7h). O resumo agrupa por módulo, traz um link para cada notificação e não é enviado se não houver nada.
- **Não perturbe:** horário (São Paulo, aceita faixa que atravessa a meia-noite, ex.: 19:00 às 07:00) e/ou fins de semana. Vale para **navegador e desktop**: dentro do período a notificação fica só na caixa e **não vai para a fila depois**. O e-mail não é afetado.
- **Silenciar:** a partir de uma notificação ligada a contrato (`contrato_id`) ou tarefa (`tarefa_id`), a pessoa corta os canais externos daquele contrato/tarefa; a caixa continua recebendo. "Voltar a avisar" desfaz.
- **Obrigatórias:** a administração define evento + canal para um setor ou usuário; para a pessoa aparece marcado e travado ("definida pela administração") e o `PUT /preferencias` não o remove. Nenhuma vem de fábrica.

### Despacho (depois do commit)

1. `notificar()` grava a notificação, as entregas e os canais, e guarda o id (gerado no Python) em `sessao.info`.
2. No **commit** da sessão, um listener dispara o despacho: `NOTIFICACOES_DESPACHO=thread` (padrão, em segundo plano), `sincrono` (na hora) ou `desligado` (só o timer; é o que os testes usam). No **rollback**, nada sai.
3. O timer `despachar` (a cada 2 minutos) é a rede de segurança: envia o que ficou pendente nos últimos 2 dias.
4. Cada envio é **reivindicado** com `UPDATE … WHERE x_enviado_em IS NULL` e conferência do `rowcount`: a thread e o timer nunca mandam em dobro.

### Notificações do navegador (Web Push)

- **Pedido de permissão no acesso:** o layout autenticado (`app-aviso-notificacoes-navegador`) lê `GET /api/notificacoes/preferencias`; se o canal navegador está disponível e ligado em algum evento e este navegador ainda não está inscrito, mostra o aviso "Receber avisos neste navegador?". O botão **Ativar notificações** dispara o pedido nativo do navegador (exige um clique) e inscreve via `POST /api/notificacoes/navegador/inscricoes`. Se a permissão já estava concedida, inscreve sem perguntar. "Agora não" some só naquela visita; no próximo acesso o aviso volta. Sem chaves VAPID no servidor, nada aparece.

- Biblioteca `pywebpush`; chaves **VAPID** no `backend/.env`: `CHAVE_PUBLICA_VAPID`, `CHAVE_PRIVADA_VAPID` (segredo) e `CONTATO_VAPID` (`mailto:`). Gere o par com `backend/.venv/bin/python scripts/gerar-chaves-vapid.py`. Sem as três, o canal aparece **indisponível** na tela, com a explicação. Trocar o par invalida as inscrições (cada pessoa ativa de novo).
- Cada navegador inscrito é uma linha em `notificacoes_inscricoes_navegador`. Resposta `404`/`410` do serviço de push apaga a inscrição; outras falhas somam em `falhas_seguidas`. A limpeza diária (timer de lembretes) apaga as com 10+ falhas seguidas ou sem uso há 90 dias.
- **Payload** (JSON, ao service worker `/sw-notificacoes.js`, escopo `/`): `titulo`, `texto` (≤ 200 caracteres, sem quebras), `url` (o link da notificação ou `/notificacoes/{entrega}`), `tag` (id da entrega: um pop-up por entrega), `entrega_id` e `token_ciencia`.
- **Botão "Ciente" do pop-up:** o service worker não tem a sessão do usuário, então o payload leva `token_ciencia`, um JWT de **7 dias** com `fin = ciencia_push` e o id da entrega; vale só para `POST /api/notificacoes/ciencia-por-token`. Se a entrega já tem ciência, a chamada não faz nada (`registrada = false`). Token inválido, expirado ou de outra finalidade: `401 token_invalido`.
- O servidor precisa alcançar `fcm.googleapis.com` e `*.notify.windows.com` na porta 443. No iPhone/iPad (iOS 16.4+), só com o SGI instalado na tela inicial (o `manifest.webmanifest` é do SGI inteiro, `display: standalone`).

## Autorização

| Ação | Quem |
|---|---|
| Caixa, abrir, ciência, enviar para usuários, acompanhar as próprias enviadas | Qualquer usuário autenticado com perfil em dia |
| Enviar para **setores** | SuperRoot ou ACL `notificacoes-setores` = CONTROLE_TOTAL. Sem isso: `403 acl_negado` |
| Acompanhar enviada de outra pessoa | Só o SuperRoot (demais: `404`) |
| Preferências, navegador, testar, silenciar | Qualquer usuário autenticado, só da própria conta |
| Notificações **obrigatórias** (`/obrigatorias`) | SuperRoot ou ACL `notificacoes-obrigatorias` = CONTROLE_TOTAL (recurso criado **fechado** pela migração `e5f9b2d7a3c1`: só a conta root, até a administração liberar mais alguém). Sem isso: `403 acl_negado` |
| Painel de entregas (`/painel-entregas`) | Só a conta root (`403 acesso_negado`) |
| `ciencia-por-token` | Sem sessão: vale o token do pop-up |

O recurso `notificacoes-setores` é criado pela migração `0c11fdac4f46` **fechado**: só a conta administrativa principal recebe CONTROLE_TOTAL. Os demais são liberados em **Controle de acesso** (`/admin/acl`).

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /api/notificacoes/resumo` | `ResumoCaixa`: `pendentes`, `nao_lidas` e `janela` (próxima entrega a abrir em modal, ou nula) |
| `GET /api/notificacoes/cliente-windows` | Baixa o instalador `SgiSpiAlertas-<versão>.msi` mais recente (pasta `client/` do servidor). Qualquer usuário autenticado; `404` se não houver instalador publicado. A tela `/notificacoes` tem o atalho **⬇ Baixar o SGI Alertas** |
| `GET /api/notificacoes?estado=&busca=&pagina=&tamanho_pagina=` | Caixa de entrada (ver abaixo) |
| `GET /api/notificacoes/{entrega_id}` | `EntregaDetalhe`, com o texto; registra a primeira visualização |
| `POST /api/notificacoes/{entrega_id}/ciencia` | Registra a ciência (também marca como visualizada; repetir não muda a data) |
| `POST /api/notificacoes/previa` | `{ "assunto", "corpo", "link"?, "autor_nome"? }` → `{ "html" }`. Devolve o e-mail da mensagem no **mesmo layout do e-mail do changelog** (brasão embutido como `data:`, cabeçalho institucional, botão e rodapé). O texto aceita `## título`, `- item` (2 espaços por subnível) e `**negrito**`; qualquer HTML digitado é escapado. A caixa de notificações mostra a mensagem recebida e a enviada nesse layout (em `<iframe srcdoc>`) e a janela Nova mensagem tem o botão "Ver prévia". O e-mail enviado ao destinatário usa o mesmo HTML |
| `POST /api/notificacoes/lote` | `{ "ids": [...], "acao": "lida" \| "nao_lida" \| "ciente" }` (1 a 500 ids) → `{ "atualizadas": n }`. Marca várias mensagens da própria caixa de uma vez: `lida` visualiza, `nao_lida` remove a visualização (a ciência já registrada não muda) e `ciente` registra a ciência (audita `mensagem.ciencia`). Ids de outras pessoas são ignorados. A tela traz caixas de seleção, "selecionar todas" (da página ou de todo o filtro) e os três botões |
| `POST /api/notificacoes` | Envia mensagem avulsa → `201` `{ "notificacao_id", "destinatarios" }` |
| `GET /api/notificacoes/destinatarios` | `usuarios[]` ativos (`id`, `nome`, `detalhe` = login · departamento), `setores[]` (só para quem pode) e `pode_enviar_setores` |
| `GET /api/notificacoes/enviadas?pagina=` | Mensagens avulsas do usuário com `destinatarios`, `visualizadas` e `cientes` |
| `GET /api/notificacoes/enviadas/{notificacao_id}` | `EnviadaDetalhe`: texto e `situacao[]` por destinatário (lida, ciência, encerrada, e-mail) |
| `GET /api/notificacoes/preferencias` | Catálogo agrupado por módulo com `canais[canal] = {disponivel, ligado, obrigatorio}`, `configuracao` (`frequencia_email`, `silencio_inicio`, `silencio_fim`, `silencio_fins_de_semana`), `navegador` (`disponivel`, `chave_publica_vapid`, `inscricoes`, `aparelhos[]`, `explicacao`) e `silenciados[]` |
| `PUT /api/notificacoes/preferencias` | `{ "canais": {"evento": ["email", "navegador"]}, "configuracao": {...} }`: **substitui tudo**. `422` para evento desconhecido, canal fora de `canais_disponiveis` do evento, frequência ou horário inválidos. Obrigatórias não saem |
| `POST /api/notificacoes/navegador/inscricoes` | `{ endpoint, p256dh, auth, rotulo }` → `201` `SituacaoNavegador` (cria ou atualiza pelo `endpoint`). `409 navegador_indisponivel` sem VAPID |
| `POST /api/notificacoes/navegador/inscricoes/remover` | `{ endpoint }` → `SituacaoNavegador` (só do próprio usuário) |
| `POST /api/notificacoes/testar` | `{ "canal": "email" \| "navegador" \| "desktop" }` → `{ enviado, detalhe }`. Desktop cria uma entrega de teste com `canal_desktop` que expira sozinha em 3 minutos |
| `POST /api/notificacoes/silenciar` | `{ "entrega_id", "tipo"? }` → `201` `{ id, tipo, alvo_id, rotulo }`. Idempotente. `400` se a notificação não tem contrato nem tarefa; `404` se a entrega não é sua |
| `DELETE /api/notificacoes/silenciados/{id}` | "Voltar a avisar" → `204` (`404` se não é seu) |
| `POST /api/notificacoes/ciencia-por-token` | `{ "token" }` → `{ "registrada": bool }` (botão "Ciente" do pop-up; `401` token inválido) |
| `GET/POST /api/notificacoes/obrigatorias`, `DELETE /api/notificacoes/obrigatorias/{id}` | Lista, cria (`{evento, canal, setor_id` ou `usuario_id}`: um só alvo; `422` se evento sem o canal) e remove as notificações obrigatórias. Repetir a mesma regra devolve a existente |
| `GET /api/notificacoes/painel-entregas?dias=` | Conta root. `por_canal` (enviadas e falhas de e-mail e navegador no período), `ultimas_falhas`, `inscricoes_total` e `inscricoes_com_falhas` |
| `GET /api/mensagens/resumo` e `GET /api/mensagens` | **Compatibilidade permanente** com o SGI Alertas já instalado (mesmo formato antigo), devolvendo **só as entregas com `canal_desktop`**. Ver [cliente-windows.md](../cliente-windows.md) |
| `POST /api/notificacoes/enviadas/{notificacao_id}/lembrar` | E-mail de lembrete ("Lembrete: …") a quem ainda não deu ciência → `{ "lembrados" }`; `400` se todos já deram ciência |

### Caixa de entrada

- **`estado`:** `pendentes` (padrão), `cientes` (com ciência ou encerradas) ou `todas`.
- **`busca`:** procura no assunto, no texto e no remetente, **sem diferenciar acentos** ("medicao" encontra "Medição").
- **Ordem:** da mais recente para a mais antiga. Expiradas não aparecem.
- **Resposta:** `{ itens: EntregaResumo[], total, pagina, tamanho_pagina }`.
- **`EntregaResumo`:** `id`, `assunto`, `prioridade`, `categoria`, `autor_nome` ("Sistema" nas automáticas), `origem`, `link`, `entregue_em`, `visualizada_em`, `ciente_em`, `encerrada_em`, `estado` e `pendente`.
- `EntregaResumo` traz também `evento`, `alertar_desktop` (a pessoa ligou o desktop para o evento), `contrato_id` e `tarefa_id`.
- **`EntregaDetalhe`** acrescenta `corpo` e `abrir_em_janela`.
- Cientes ou encerradas há mais de `NOTIFICACOES_MESES_NA_CAIXA` (padrão 6) meses **saem da caixa e da busca**, mas continuam no banco (auditoria) e em "Enviadas por mim" do remetente.

### Envio (`POST /api/notificacoes`)

```json
{
  "assunto": "Reunião de alinhamento",
  "corpo": "Reunião na sexta, às 10h.",
  "prioridade": "alta",
  "categoria": "comunicado",
  "usuarios_ids": [12, 15],
  "setores_ids": [3],
  "expira_em": "2026-10-31T23:59:59-03:00",
  "link": "/contratos/painel"
}
```

- **Destinatários:**
  - setores viram a lista de membros, e ninguém recebe duas vezes;
  - só usuários **ativos** recebem;
  - sem nenhum destinatário, a resposta é `400`.
- **Validações:**
  - `assunto` até 300 caracteres e `corpo` até 12.000, ambos obrigatórios;
  - `link` precisa começar com `/` (`422`);
  - `expira_em` precisa estar no futuro (`400`).
- **Canais:** não há mais "também enviar por e-mail" no envio. Cada destinatário recebe na caixa e pelos canais que ligou para o evento `comunicados.mensagem`.
  - O resultado do e-mail fica na entrega (`email_ok`, `email_erro`) e aparece em "Enviadas".
  - Destinatário sem e-mail ou sem servidor ativo: `email_ok = false`, com a explicação.

## Layout dos e-mails

Todos os e-mails do sistema (notificações, avisos dos contratos, lembretes e teste do servidor SMTP) usam o layout oficial de `backend/app/services/modelo_email.py`:
- **cabeçalho:** brasão do Estado, "GOVERNO DO ESTADO DE SÃO PAULO", "Secretaria de Parcerias em Investimentos" e o filete vermelho institucional;
- **corpo:** título, texto e botão "Abrir no SGI SPI";
- **rodapé:** "SGI SPI – Sistema de Gestão Integrada" e a nota de mensagem automática.

O logo do cabeçalho (`apoio/2-horizontal-slogan-para-emails.png`: Secretaria de Parcerias em Investimentos + Governo do Estado de São Paulo) vai **embutido e centralizado** no e-mail (imagem `Content-ID: <logo-sp>`, arquivo `backend/app/recursos/logo-sp-email.png`, 1168 px exibido a 584 px). Para trocar o logo, substitua esse arquivo. Por isso ele aparece sem acesso à rede interna e sem o bloqueio de imagens externas do Outlook. `servico_smtp.enviar_email` anexa o brasão sempre que o HTML o referencia.

## Catálogo de eventos

Cada linha é um evento que a pessoa pode ligar por e-mail, navegador e desktop (`canais_disponiveis`). A chave é estável.

| Módulo | Chave | Evento | Quem recebe e quando |
|---|---|---|---|
| Comunicados | `comunicados.mensagem` | Comunicado de colega ou setor | Você recebe quando alguém envia uma notificação a você ou ao seu setor. |
| Comunicados | `comunicados.lembrete_ciencia` | Lembrete de ciência pendente | Você recebe quando um comunicado importante continua sem a sua ciência (lembrete do remetente ou automático, no 3º dia). |
| Sistema | `sistema.novidades` | Novidades do SGI SPI (só e-mail) | Você recebe o e-mail de novidades (changelog) enviado pela administração. |
| Contratos | `contratos.equipe_incluido` | Incluído na equipe de um contrato | Você recebe quando alguém cadastra você como gestor, fiscal ou outro papel de um contrato. |
| Contratos | `contratos.ocorrencia_diario` | Ocorrência no diário do contrato | A equipe do contrato recebe quando uma ocorrência é registrada no diário. |
| Contratos | `contratos.medicao_concluida` | Medição concluída | A equipe do contrato recebe quando uma medição mensal é concluída. |
| Contratos | `contratos.medicao_adicional` | Medição adicional incluída | A equipe do contrato recebe quando uma medição adicional é incluída. |
| Contratos | `contratos.conferir_retencao` | Conferir retenção de tributos | O Financeiro recebe quando a nota fiscal é juntada e a retenção precisa ser conferida. |
| Contratos | `contratos.nota_recusada` | Nota fiscal recusada | A equipe do contrato recebe quando a nota fiscal é recusada e precisa ser reenviada. |
| Contratos | `contratos.retencao_conferida` | Retenção conferida | A equipe do contrato recebe quando a retenção de tributos é conferida e a etapa seguinte pode seguir. |
| Contratos | `contratos.alteracao_concluida` | Prorrogação, reajuste ou alteração concluídos | A equipe do contrato recebe quando uma prorrogação, um reajuste ou uma alteração é concluída. |
| Contratos | `contratos.vencimento_contrato` | Vencimento do contrato (90, 60 e 30 dias) | A equipe do contrato recebe quando faltam 90, 60 e 30 dias para o fim da vigência. |
| Contratos | `contratos.medicao_atrasada` | Medição atrasada | A equipe do contrato recebe quando a medição de uma competência está atrasada. |
| Contratos | `contratos.correcao_itens` | Correção de itens do contrato | A equipe do contrato recebe quando uma correção de itens é proposta, aplicada ou recusada. |
| Contratos | `contratos.portaria` | Portaria de designação | Você recebe quando uma portaria de designação precisa do seu aceite ou muda de situação. |
| Contratos | `contratos.portaria_nomeacao` | Nomeação em portaria (ciência) | Você recebe quando é indicado em uma portaria de designação e precisa dar ciência. |
| Contratos | `contratos.portaria_dados_rh` | Dados do RH pendentes para uma nomeação | O RH (CGP) recebe quando alguém indicado em uma portaria está com RS/PV, RG/CIN ou cargo em branco. |
| Tarefas | `tarefas.atribuida` | Tarefa atribuída a você | Você recebe quando uma tarefa é criada para você, quando entra como responsável ou quando ela é transferida a você. |
| Tarefas | `tarefas.prazo_alterado` | Prazo alterado | Os envolvidos recebem quando o prazo de uma tarefa muda. |
| Tarefas | `tarefas.aguardando_validacao` | Aguardando sua validação | Quem valida recebe quando uma entrega aguarda validação, e de novo quando ela fica parada. |
| Tarefas | `tarefas.entrega_validada` | Entrega validada | Os responsáveis recebem quando a entrega é validada. |
| Tarefas | `tarefas.entrega_devolvida` | Entrega devolvida | Os responsáveis recebem quando a entrega é devolvida para ajustes. |
| Tarefas | `tarefas.reaberta` | Tarefa reaberta | Os responsáveis recebem quando uma tarefa é reaberta. |
| Tarefas | `tarefas.concluida` | Tarefa concluída | Os responsáveis e a liderança recebem quando a tarefa é concluída. |
| Tarefas | `tarefas.mencao` | Menção a você | Você recebe quando alguém menciona você em uma tarefa. |
| Tarefas | `tarefas.comentario` | Comentário em tarefa | Os envolvidos recebem quando alguém comenta em uma tarefa. |
| Tarefas | `tarefas.vence_amanha` | Tarefa vence amanhã | Os envolvidos recebem na véspera do prazo. |
| Tarefas | `tarefas.atrasada` | Tarefa atrasada | Os envolvidos recebem quando o prazo passa sem a tarefa estar concluída. |
| Tarefas | `tarefas.escalonada` | Tarefas atrasadas das suas equipes | A liderança recebe, uma vez por dia, a tabela das tarefas atrasadas das suas equipes. |
| Tarefas | `tarefas.marco_atingido` | Marco atingido | A liderança e os membros recebem quando todas as tarefas de um marco são concluídas. |
| Tarefas | `tarefas.status_equipe` | Status da equipe | A liderança e os membros recebem quando o status da equipe é atualizado. |
| Tarefas | `tarefas.lembrete_status` | Lembrete para atualizar o status | A liderança recebe quando a equipe está há uma semana sem atualização de status. |
| Tarefas | `tarefas.recorrencia_pausada` | Recorrência pausada | O criador recebe quando uma tarefa recorrente é pausada por erro. |
| Tarefas | `tarefas.atividade_agendada` | Atividade agendada para você | Você recebe quando uma atividade é agendada para você. |
| Tarefas | `tarefas.atividade_concluida` | Atividade concluída | O criador recebe quando a atividade que ele agendou é concluída. |
| Tarefas | `tarefas.atividade_lembrete` | Atividade para hoje ou atrasada | Você recebe quando uma atividade vence hoje ou está atrasada. |
| RH | `rh.afastamento_aprovacao` | Afastamento aguardando aprovação | Os aprovadores recebem quando um servidor agenda férias ou outro afastamento. |
| RH | `rh.afastamento_ciencia` | Afastamento aguardando seu ciente e de acordo | O superior imediato recebe quando o servidor agenda um afastamento. |
| RH | `rh.afastamento_situacao` | Situação do seu afastamento | Você recebe quando o seu pedido de afastamento é aprovado, recusado ou alterado. |
| RH | `rh.afastamento_cancelado` | Afastamento cancelado | Os envolvidos recebem quando um afastamento é cancelado. |
| RH | `rh.boas_vindas` | Boas-vindas no retorno | Você recebe quando volta de um afastamento. |
| RH | `rh.afastamento_lembrete` | Pedido de afastamento parado | Os aprovadores recebem quando um pedido fica parado há 3 dias. |
| RH | `rh.cadastro_validacao` | Alteração de cadastro aguardando validação | A CGP recebe quando um servidor altera o cadastro. |
| RH | `rh.cadastro_recusado` | Alteração do seu cadastro recusada | Você recebe quando a CGP recusa uma alteração do seu cadastro. |
| RH | `rh.folha_ponto_bloqueada` | Folha de ponto bloqueada | A CGP recebe quando um servidor tenta baixar a folha de ponto, mas tem cadastro pendente ou incompleto. |
| RH | `rh.periodo_ferias` | Novo período de férias | Você recebe quando começa um novo período aquisitivo. |
| RH | `rh.prazo_ferias` | Prazo para usar as férias | Você e quem aprova recebem quando o saldo de férias está perto de expirar. |
| Reserva de espaços | `reserva_espacos.nova_solicitacao` | Nova solicitação de reserva | Os fiscais do espaço recebem quando uma reserva é solicitada. |
| Reserva de espaços | `reserva_espacos.registrada_em_seu_nome` | Reserva registrada em seu nome | Você recebe quando alguém registra uma reserva em seu nome. |
| Reserva de espaços | `reserva_espacos.resposta` | Reserva deferida ou indeferida | Quem solicitou e o responsável recebem a decisão do fiscal. |
| Reserva de espaços | `reserva_espacos.cancelada` | Reserva cancelada | Os fiscais, o solicitante e o responsável recebem quando uma reserva é cancelada. |
| Reserva de espaços | `reserva_espacos.lembrete_vespera` | Lembrete da véspera da reserva | Quem solicitou e o responsável recebem na véspera da reserva. |
| Contratações | `contratacoes.revisao_nova` | Nova proposta ou comentário em documento | O criador e os envolvidos recebem quando alguém registra uma proposta de alteração ou um comentário. |
| Contratações | `contratacoes.proposta_aplicada` | Proposta de alteração aplicada | O autor da proposta recebe quando ela é aplicada ao documento. |
| Contratações | `contratacoes.revisao_parada` | Revisão parada | O criador do documento recebe quando uma revisão fica sem resposta. |
| Notícias | `noticias.aguardando_aprovacao` | Notícia aguardando aprovação | Os aprovadores recebem quando uma notícia é enviada para aprovação. |
| Notícias | `noticias.aprovada` | Notícia aprovada | O autor recebe quando a notícia é aprovada. |
| Notícias | `noticias.devolvida` | Notícia devolvida para ajustes | O autor recebe quando a notícia é devolvida. |
| Notícias | `noticias.publicada` | Notícia ou comunicado publicado | Os destinatários escolhidos recebem quando a notícia ou o comunicado é publicado. |
| Melhorias | `melhorias.nova_sugestao` | Nova sugestão de melhoria | Quem faz a triagem recebe quando alguém envia uma sugestão. |
| Melhorias | `melhorias.andamento` | Andamento da sua sugestão | O autor recebe quando a sugestão muda de situação. |
| Protocolo | `protocolo.documento_pendente` | Documento pendente no Protocolo | Quem reservou um número recebe quando o documento continua sem anexo. |
| Patrimônio | `patrimonio.movimentacao_pendente` | Movimentação aguardando autorização | Quem administra o Patrimônio recebe quando uma movimentação é solicitada. |
| Patrimônio | `patrimonio.movimentacao_decidida` | Movimentação autorizada, recusada ou concluída | Quem solicitou recebe a decisão e a conclusão da movimentação. |
| Patrimônio | `patrimonio.classificacao_pendente` | Classificação aguardando aprovação | Quem administra o Patrimônio recebe quando uma lista de inservíveis ou extraviados é enviada. |
| Patrimônio | `patrimonio.classificacao_decidida` | Classificação decidida | Quem enviou a lista (e quem colaborou nela) recebe a decisão. |
| Patrimônio | `patrimonio.classificacao_compartilhada` | Lista compartilhada com você | Você recebe quando alguém compartilha uma lista de inservíveis ou extraviados para você ajudar a montar. |
| Patrimônio | `patrimonio.baixa_pendente` | Baixa aguardando aprovação | Quem administra o Patrimônio recebe quando uma baixa é enviada. |
| Patrimônio | `patrimonio.baixa_decidida` | Baixa decidida | Quem enviou a baixa recebe a decisão. |
| Diretório | `diretorio.recado_aniversario` | Recado de aniversário | Você recebe quando um colega deixa um recado no seu aniversário. |
| Diretório | `diretorio.feliz_aniversario` | Feliz aniversário | Você recebe a mensagem automática no dia do seu aniversário. |

## Avisos automáticos

Gerados na mesma transação do evento, com uma **chave** que impede repetir o aviso para a mesma pessoa. O autor da ação não recebe o próprio aviso, exceto nas janelas.

| Evento | Quem recebe | Chave | Observações |
|---|---|---|---|
| Pessoa incluída na equipe de um contrato (cadastro ou edição) | A pessoa designada | `equipe:{contrato}:{papel}:{usuario}:{momento}` | **Janela**: "Você foi cadastrado como <papel> no contrato <número>"; categoria `atribuicao`, prioridade alta, **e-mail** |
| Ocorrência no diário de bordo | Equipe vigente | `diario:{ocorrencia}` | Prioridade alta se houver glosa |
| Medição concluída | Equipe vigente | `medicao:{competencia}:{momento}` | Encerra o aviso de atraso da competência |
| Nota fiscal juntada | Financeiro (ACL `financeiro`, Modificação ou mais) | `retencao:{competencia}` | Pendência, **encerrada** ao salvar a retenção |
| Retenção conferida | Equipe vigente | `finais:{competencia}` | Pendência (CADIN/checklist/consolidado), **encerrada** ao gerar o consolidado |
| Prorrogação registrada, reajuste concluído, aditamento/supressão concluídos | Equipe vigente | `prorrogacao:{id}`, `reajuste:{id}`, `alteracao:{id}` | Informativos; a prorrogação encerra os avisos de vencimento |

Excluir um contrato apaga todos os avisos dele (`mensagens.contrato_id` com `ON DELETE CASCADE`).

## Tarefas agendadas (systemd)

`backend/.venv/bin/python -m app.tarefas.notificacoes <comando>`, instaladas por `scripts/instalar.sh`:

| Timer | Comando | Quando | O que faz |
|---|---|---|---|
| `sgi-spi-notificacoes-despachar.timer` | `despachar` | A cada 2 minutos | Rede de segurança: envia (e-mail imediato e navegador) o que ficou pendente nos últimos 2 dias e gera os avisos das notícias agendadas. As unidades antigas `sgi-spi-mensageria-*` são removidas pelo `scripts/instalar.sh`; até lá o módulo `app.tarefas.mensageria` repassa para este |
| `sgi-spi-notificacoes-lembretes.timer` | `lembretes` | Todo dia às 07:00 (America/Sao_Paulo) | Ver abaixo |

**Lembretes diários** (idempotentes: rodar de novo no mesmo dia não repete):
- **Vencimento do contrato:** quando faltam 90, 60 e 30 dias para o fim da vigência atual, só para contratos ativos ou a vencer.
  - Aviso `prazo` à equipe, com e-mail. Chave `vencimento:{contrato}:{AAAAMMDD do fim}:{marco}`.
  - Uma prorrogação muda a data de fim, e os marcos voltam a valer.
- **Medição atrasada:** competência regular com período encerrado há mais de 30 dias e medição não concluída. **Só competências de 09/2026 em diante**: as anteriores foram "limpas" e não geram aviso (os avisos pendentes delas foram encerrados em 06/10/2026).
  - Pendência à equipe, com e-mail. Chave `atraso:{competencia}`, encerrada ao concluir a medição.
- **Ciência pendente:** notificações de prioridade alta ou crítica sem ciência no 3º dia geram um e-mail "Lembrete: …" **só para quem ligou o e-mail** do evento `comunicados.lembrete_ciencia`.
- **Resumos por e-mail:** o resumo diário sai todo dia e o semanal na segunda-feira (às 7h), um e-mail por pessoa agrupado por módulo.
- **Limpeza do navegador:** apaga as inscrições com 10+ falhas seguidas ou 90 dias sem uso.
- **Sem resumo diário:** o e-mail diário "N mensagem(ns) aguardando sua ciência" foi retirado (05/10/2026); as pendências continuam na caixa de notificações e nos lembretes de ciência pendente.

## Consumo no Angular

- **Sino** na barra superior (`shared/layout/layout-autenticado`):
  - mostra o total de `pendentes` (`GET /resumo` ao abrir, a cada navegação e a cada 60 s);
  - o clique abre `/notificacoes`.
  - Não aparece com o perfil pendente.
- **Janela** (`features/notificacoes/janela-notificacao.component.ts`): mostra `resumo.janela` com os botões **Abrir** (link) e **Ciente**.
  - Fechar (×, Esc ou fundo) só esconde; a notificação continua na caixa.
- **Tela `/notificacoes`** (item "Notificações" na barra lateral; `/mensagens` redireciona para ela; `/notificacoes/:entregaId` abre aquela notificação, é o link do pop-up):
  - aba **Recebidas**: filtro de situação, busca, detalhe com "Li e estou ciente", "Abrir" e **"Silenciar este contrato/tarefa"**;
  - **Nova notificação**: usuários com busca e setores (se `pode_enviar_setores`), prioridade, categoria, expiração e link;
  - aba **Enviadas por mim**: % de ciência, situação por destinatário e botão "Lembrar pendentes por e-mail";
  - aba **Preferências** (`preferencias-notificacoes.component.ts`): matriz evento × canal por módulo (com "marcar o módulo inteiro" e "marcar a coluna inteira"), botões **Testar** por canal, ativação do navegador (permissão, service worker e inscrição), frequência do e-mail, "não perturbe" e a lista de silenciados com "Voltar a avisar".
- **Ativação do navegador** (`core/notificacoes/push-notificacoes.service.ts`): ao marcar a primeira caixa de "Navegador" (ou em "Ativar neste navegador"), pede `Notification.requestPermission()`, registra `/sw-notificacoes.js` (escopo `/`, `src/sw-notificacoes.js`, publicado na raiz pelo `angular.json`; o nginx o serve sem cache longo e com `Service-Worker-Allowed: /`) e faz `pushManager.subscribe` com a chave VAPID. Estados: ativado neste navegador, bloqueado (com a instrução para liberar nas configurações do site), não suportado e "iPhone sem o app instalado".
- **Service worker** (`src/sw-notificacoes.js`): mostra o pop-up com as ações **Abrir** e **Ciente** e trata o clique (foca uma aba aberta ou abre a URL). Convive com o `ngsw-worker.js` do Patrimônio (escopo `/patrimonio/`).
- **Administração › Notificações do sistema** (`/admin/notificacoes-sistema`, só a conta root): e-mail de changelog (com a contagem de quem receberá), notificações **obrigatórias** e o **painel de entregas**.
- **Serviços:** `core/notificacoes/notificacoes-api.service.ts` e `core/notificacoes/caixa-notificacoes.service.ts` (estado do sino e da janela).
