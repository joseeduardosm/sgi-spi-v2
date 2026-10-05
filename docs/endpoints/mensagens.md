# Mensageria (`/api/mensagens`)

Tag no OpenAPI: **Mensageria**. Implementação:
- rotas: `backend/app/api/routes/mensagens.py`;
- regras: `backend/app/services/servico_mensagens.py`;
- avisos dos contratos: `backend/app/services/contratos/avisos.py`;
- tarefas agendadas: `backend/app/tarefas/mensageria.py`;
- modelos: `backend/app/models/mensagem.py` (tabelas `mensagens` e `mensagens_entregas`).

É a caixa de mensagens de cada usuário. Reúne comunicados escritos por usuários (**avulsas**) e avisos gerados pelo sistema (**automáticas**).

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

## Autorização

| Ação | Quem |
|---|---|
| Caixa, abrir, ciência, enviar para usuários, acompanhar as próprias enviadas | Qualquer usuário autenticado com perfil em dia |
| Enviar para **setores** | SuperRoot ou ACL `mensageria-setores` = CONTROLE_TOTAL. Sem isso: `403 acl_negado` |
| Acompanhar enviada de outra pessoa | Só o SuperRoot (demais: `404`) |

O recurso `mensageria-setores` é criado pela migração `0c11fdac4f46` **fechado**: só a conta administrativa principal recebe CONTROLE_TOTAL. Os demais são liberados em **Controle de acesso** (`/admin/acl`).

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /api/mensagens/resumo` | `ResumoCaixa`: `pendentes`, `nao_lidas` e `janela` (próxima entrega a abrir em modal, ou nula) |
| `GET /api/mensagens?estado=&busca=&pagina=&tamanho_pagina=` | Caixa de entrada (ver abaixo) |
| `GET /api/mensagens/{entrega_id}` | `EntregaDetalhe`, com o texto; registra a primeira visualização |
| `POST /api/mensagens/{entrega_id}/ciencia` | Registra a ciência (também marca como visualizada; repetir não muda a data) |
| `POST /api/mensagens/previa` | `{ "assunto", "corpo", "link"?, "autor_nome"? }` → `{ "html" }`. Devolve o e-mail da mensagem no **mesmo layout do e-mail do changelog** (brasão embutido como `data:`, cabeçalho institucional, botão e rodapé). O texto aceita `## título`, `- item` (2 espaços por subnível) e `**negrito**`; qualquer HTML digitado é escapado. A caixa de mensagens mostra a mensagem recebida e a enviada nesse layout (em `<iframe srcdoc>`) e a janela Nova mensagem tem o botão "Ver prévia". O e-mail enviado ao destinatário usa o mesmo HTML |
| `POST /api/mensagens/lote` | `{ "ids": [...], "acao": "lida" \| "nao_lida" \| "ciente" }` (1 a 500 ids) → `{ "atualizadas": n }`. Marca várias mensagens da própria caixa de uma vez: `lida` visualiza, `nao_lida` remove a visualização (a ciência já registrada não muda) e `ciente` registra a ciência (audita `mensagem.ciencia`). Ids de outras pessoas são ignorados. A tela traz caixas de seleção, "selecionar todas" (da página ou de todo o filtro) e os três botões |
| `POST /api/mensagens` | Envia mensagem avulsa → `201` `{ "mensagem_id", "destinatarios" }` |
| `GET /api/mensagens/destinatarios` | `usuarios[]` ativos (`id`, `nome`, `detalhe` = login · departamento), `setores[]` (só para quem pode) e `pode_enviar_setores` |
| `GET /api/mensagens/enviadas?pagina=` | Mensagens avulsas do usuário com `destinatarios`, `visualizadas` e `cientes` |
| `GET /api/mensagens/enviadas/{mensagem_id}` | `EnviadaDetalhe`: texto e `situacao[]` por destinatário (lida, ciência, encerrada, e-mail) |
| `POST /api/mensagens/enviadas/{mensagem_id}/lembrar` | E-mail de lembrete ("Lembrete: …") a quem ainda não deu ciência → `{ "lembrados" }`; `400` se todos já deram ciência |

### Caixa de entrada

- **`estado`:** `pendentes` (padrão), `cientes` (com ciência ou encerradas) ou `todas`.
- **`busca`:** procura no assunto, no texto e no remetente, **sem diferenciar acentos** ("medicao" encontra "Medição").
- **Ordem:** da mais recente para a mais antiga. Expiradas não aparecem.
- **Resposta:** `{ itens: EntregaResumo[], total, pagina, tamanho_pagina }`.
- **`EntregaResumo`:** `id`, `assunto`, `prioridade`, `categoria`, `autor_nome` ("Sistema" nas automáticas), `origem`, `link`, `entregue_em`, `visualizada_em`, `ciente_em`, `encerrada_em`, `estado` e `pendente`.
- **`EntregaDetalhe`** acrescenta `corpo`, `contrato_id` e `abrir_em_janela`.

### Envio (`POST /api/mensagens`)

```json
{
  "assunto": "Reunião de alinhamento",
  "corpo": "Reunião na sexta, às 10h.",
  "prioridade": "alta",
  "categoria": "comunicado",
  "usuarios_ids": [12, 15],
  "setores_ids": [3],
  "expira_em": "2026-10-31T23:59:59-03:00",
  "link": "/contratos/painel",
  "enviar_email": true
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
- **E-mail (`enviar_email`):** sai na hora, em segundo plano, pelo servidor SMTP ativo, para o e-mail do perfil de cada destinatário.
  - O resultado fica na entrega (`email_ok`, `email_erro`) e aparece em "Enviadas".
  - Destinatário sem e-mail ou sem servidor ativo: `email_ok = false`, com a explicação.

## Layout dos e-mails

Todos os e-mails do sistema (mensageria, avisos dos contratos, lembretes e teste do servidor SMTP) usam o layout oficial de `backend/app/services/modelo_email.py`:
- **cabeçalho:** brasão do Estado, "GOVERNO DO ESTADO DE SÃO PAULO", "Secretaria de Parcerias em Investimentos" e o filete vermelho institucional;
- **corpo:** título, texto e botão "Abrir no SGI SPI";
- **rodapé:** "SGI SPI – Sistema de Gestão Integrada" e a nota de mensagem automática.

O brasão vai **embutido** no e-mail (imagem `Content-ID: <brasao-spi>`, arquivo `backend/app/recursos/brasao-email.png`). Por isso ele aparece sem acesso à rede interna e sem o bloqueio de imagens externas do Outlook. `servico_smtp.enviar_email` anexa o brasão sempre que o HTML o referencia.

## Avisos automáticos

Gerados na mesma transação do evento, com uma **chave** que impede repetir o aviso para a mesma pessoa. O autor da ação não recebe o próprio aviso, exceto nas janelas.

| Evento | Quem recebe | Chave | Observações |
|---|---|---|---|
| Pessoa incluída na equipe de um contrato (cadastro ou edição) | A pessoa designada | `equipe:{contrato}:{papel}:{usuario}:{momento}` | **Janela**: "Você foi cadastrado como <papel> no contrato <número>"; categoria `atribuicao`, prioridade alta, **e-mail** |
| Ocorrência no diário de bordo | Equipe vigente | `diario:{ocorrencia}` | Prioridade alta se houver glosa |
| Medição concluída | Equipe vigente | `medicao:{competencia}:{momento}` | Encerra o aviso de atraso da competência |
| Nota fiscal juntada | Financeiro (setor `SETOR_FINANCEIRO`) | `retencao:{competencia}` | Pendência, **encerrada** ao salvar a retenção |
| Retenção conferida | Equipe vigente | `finais:{competencia}` | Pendência (CADIN/checklist/consolidado), **encerrada** ao gerar o consolidado |
| Prorrogação registrada, reajuste concluído, aditamento/supressão concluídos | Equipe vigente | `prorrogacao:{id}`, `reajuste:{id}`, `alteracao:{id}` | Informativos; a prorrogação encerra os avisos de vencimento |

Excluir um contrato apaga todos os avisos dele (`mensagens.contrato_id` com `ON DELETE CASCADE`).

## Tarefas agendadas (systemd)

`backend/.venv/bin/python -m app.tarefas.mensageria <comando>`, instaladas por `scripts/instalar.sh`:

| Timer | Comando | Quando | O que faz |
|---|---|---|---|
| `sgi-spi-mensageria-emails.timer` | `emails` | A cada 2 minutos | Envia por e-mail os avisos automáticos marcados para e-mail, entregues nos últimos 2 dias e ainda não enviados |
| `sgi-spi-mensageria-lembretes.timer` | `lembretes` | Todo dia às 07:00 (America/Sao_Paulo) | Ver abaixo |

**Lembretes diários** (idempotentes: rodar de novo no mesmo dia não repete):
- **Vencimento do contrato:** quando faltam 90, 60 e 30 dias para o fim da vigência atual, só para contratos ativos ou a vencer.
  - Aviso `prazo` à equipe, com e-mail. Chave `vencimento:{contrato}:{AAAAMMDD do fim}:{marco}`.
  - Uma prorrogação muda a data de fim, e os marcos voltam a valer.
- **Medição atrasada:** competência regular com período encerrado há mais de 30 dias e medição não concluída.
  - Pendência à equipe, com e-mail. Chave `atraso:{competencia}`, encerrada ao concluir a medição.
- **Ciência pendente:** mensagens de prioridade alta ou crítica sem ciência no 3º dia recebem um e-mail "Lembrete: …".
- **Sem resumo diário:** o e-mail diário "N mensagem(ns) aguardando sua ciência" foi retirado (05/10/2026); as pendências continuam na caixa de mensagens e nos lembretes de ciência pendente.

## Consumo no Angular

- **Sino** na barra superior (`shared/layout/layout-autenticado`):
  - mostra o total de `pendentes` (`GET /resumo` ao abrir, a cada navegação e a cada 60 s);
  - o clique abre `/mensagens`.
  - Não aparece com o perfil pendente.
- **Janela** (`features/mensagens/janela-mensagem.component.ts`): mostra `resumo.janela` com os botões **Abrir** (link) e **Ciente**.
  - Fechar (×, Esc ou fundo) só esconde; a mensagem continua na caixa.
- **Tela `/mensagens`** (item "Mensagens" na barra lateral):
  - aba **Recebidas**: filtro de situação, busca, detalhe com "Li e estou ciente" e link "Abrir";
  - **Nova mensagem**: usuários com busca e setores (se `pode_enviar_setores`), prioridade, categoria, expiração, link e "Também enviar por e-mail";
  - aba **Enviadas por mim**: % de ciência, situação por destinatário e botão "Lembrar pendentes por e-mail".
- **Serviços:** `core/mensagens/mensagens-api.service.ts` e `core/mensagens/caixa-mensagens.service.ts` (estado do sino e da janela).
