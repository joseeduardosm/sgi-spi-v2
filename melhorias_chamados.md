# Melhorias do módulo Chamados (Fase 2)

Data: 2026-11-01. Base: recon da Fase 1 (`replica/recon.md`), relatos públicos sobre o GLPI (`replica/reviews.csv`,
`replica/feedback.md`) e o contexto do SGI (setor público, LGPD, módulos que já existem).

**Princípio desta lista:** o que o recon achou no GLPI da SPI não é tratado como "limitação do GLPI", e sim como um **erro de
configuração ou de processo que o módulo novo deve impedir por design**. Se dá para configurar errado, alguém vai configurar errado:
a SPI tem SLA sem calendário, 121 chamados sem categoria, etiquetas no lugar de atribuição e um e-mail que parou de sair
sem ninguém perceber. Cada item diz como o módulo torna isso impossível (ou visível na hora).

Legenda: esforço **P** (até 2 dias) · **M** (até 1 semana) · **G** (mais de 1 semana). Prioridade **1** = MVP de virada ·
**2** = logo depois da virada · **3** = quando der.

## Sobre as evidências externas

- **Amostra: 35 relatos de 2 fontes**: 28 issues do repositório oficial do GLPI no GitHub (texto exato, lido pela API pública)
  e 7 trechos do fórum oficial do GLPI. Nenhum relato tem nota em estrelas.
- **G2, Capterra, Software Advice e Reddit bloquearam a leitura** (HTTP 403). Por isso não há avaliação de loja aqui.
  Pelos resumos do buscador, as notas são 4,5 no Capterra (41 avaliações) e 4,5 no G2 (42 avaliações), com críticas a configuração
  complexa e relatórios fracos. Não consegui conferir o texto exato, então isso não entra como evidência.
- Os temas com uma única fonte estão marcados como **finos**. Issue de GitHub mostra onde o produto falha, não quanto isso irrita
  os usuários. A força da evidência aqui vem de **casar o relato externo com o que o banco da SPI mostra**.
- As citações estão no idioma original, palavra por palavra, com link.

---

## A. O que o módulo impede por design (achados do recon)

### A1. Chamado sem grupo responsável · prioridade 1 · esforço M
- **Problema.** No GLPI, a categoria pode ficar sem grupo (só 11 de 126 têm), o chamado nasce sem ninguém, 121 chamados ficaram
  sem categoria e a equipe passou a usar **etiquetas com nome de técnico** para saber de quem é cada chamado (513 vínculos).
  Lá fora, o mesmo: o grupo pré-definido no modelo não entra no chamado aberto pela interface simplificada
  ("the resulting ticket does not include the technician group": [#20832](https://github.com/glpi-project/glpi/issues/20832)),
  e trocar a categoria soma grupos em vez de trocar
  ("the new actor is added and I have 2 groups in the Watcher field": [#17739](https://github.com/glpi-project/glpi/issues/17739)).
- **Proposta.**
  - Categoria é obrigatória na abertura e **não salva sem grupo responsável** (herdado da categoria-mãe, se não tiver um próprio).
  - O chamado **sempre nasce atribuído a um grupo**, derivado da categoria.
  - Trocar a categoria **troca** o grupo (e não soma). Se já houver técnico, o sistema pergunta se mantém.
  - A fila tem "sem técnico" e "por técnico". As etiquetas continuam, mas **não podem ter nome de usuário nem de grupo**
    (o cadastro recusa) e não servem de fila.
  - Nos Parâmetros, um alerta "categorias sem grupo: 0" deixa o erro à vista.

### A2. SLA sem calendário · prioridade 1 · esforço G
- **Problema.** Os 5 SLAs da SPI correm 24 horas por dia, 7 dias por semana. Não há feriado cadastrado e 23% dos chamados
  estouram o prazo de solução, inclusive à noite e no fim de semana. O cálculo do GLPI também tem histórico de erros:
  - "Pending should be work only during working hours defined in calendar." ([fórum](https://forum.glpi-project.org/viewtopic.php?id=158161))
  - "the time spent in "pending" is added tot the field TTR" ([#17186](https://github.com/glpi-project/glpi/issues/17186))
  - "despite being on pending, the OLA time to resolve has been violated" ([#24481](https://github.com/glpi-project/glpi/issues/24481))
  - "waiting time is not added to the Time to resolve after SLA changed" ([#6902](https://github.com/glpi-project/glpi/issues/6902))
  - "OLA is assigned and the time passes before the Ticket is taken, although the technician is assigned" ([#14026](https://github.com/glpi-project/glpi/issues/14026))
- **Proposta.**
  - **Não existe SLA sem expediente.** O expediente é obrigatório no cadastro e os feriados vêm do RH (`rh_feriados`, com
    `calendario_util`). Fica um parâmetro para decidir se ponto facultativo conta como dia útil.
  - Uma regra só para a pausa: o relógio para em Pendente e em Solucionado (fim) e só anda dentro do expediente.
  - Trocar o SLA no meio do chamado recalcula o prazo com a espera já acumulada.
  - Uma **suíte de testes com os cenários dessas issues** (sexta → segunda, pendente no fim de semana, troca de SLA, atribuição na
    abertura), mais o ponto facultativo do RH.
  - Na tela do chamado, o prazo aparece como "vence em 3h20 úteis (quarta, 10:40)", e não como uma data solta.

### A3. E-mail que para de sair sem ninguém saber · prioridade 1 · esforço M
- **Problema.** A fila do GLPI da SPI tem **9.207 avisos parados, só 41 com tentativa de envio**. Ninguém percebeu porque o alerta
  do GLPI sai pela mesma fila que travou. Isso é descrito exatamente aqui:
  "This puts the alert in the same notification queue that the stuck task is supposed to send, so the alert is never delivered."
  ([#26004](https://github.com/glpi-project/glpi/issues/26004), reproduzido no 11.0.8, a versão da SPI). Outros relatos:
  - "Large Base64 image in ticket follow-up breaks email notifications" ([#25265](https://github.com/glpi-project/glpi/issues/25265), 11.0.8)
  - "the notification queue gets stuck for hours on end" ([fórum](https://forum.glpi-project.org/viewtopic.php?id=291882))
  - "Mailgate task stuck" ([#14662](https://github.com/glpi-project/glpi/issues/14662))
- **Proposta.**
  - Fila de envio com estado por mensagem (aguardando, enviada, falhou), número de tentativas e o erro do servidor SMTP.
  - **Alerta por um canal diferente do e-mail** (o sino do SGI e um selo vermelho no painel da equipe) quando houver falha
    seguida ou a fila passar de N mensagens ou de X minutos.
  - **Painel de saúde do módulo**: última execução de cada tarefa agendada, fila, erros. Tarefa travada é detectada e liberada sozinha.
  - **Imagem colada vira anexo** (nunca base64 no corpo) e o e-mail leva só um resumo com o link.
  - Teste de envio no cadastro do SMTP (o SGI já tem os servidores SMTP).

### A4. Prioridade que ninguém usa · prioridade 1 · esforço P
- **Problema.** 1.601 de 1.607 chamados ficaram em urgência, impacto e prioridade "média". A matriz 5 × 5 existe, mas é ruído.
- **Proposta.**
  - A **prioridade é derivada da categoria** (ex.: "Rede > Falha de conexão" = alta, "Sala de reunião" = normal).
  - O requerente responde **uma pergunta só**, e opcional: "Isso está impedindo você de trabalhar?" (sim/não). Se a resposta for sim,
    a prioridade sobe um nível.
  - O técnico pode mudar a prioridade, **com motivo** registrado no histórico.
  - A matriz urgência × impacto fica disponível nos Parâmetros para quem quiser, mas **desligada por padrão**, com 3 níveis, não 5.

### A5. Satisfação que não volta · prioridade 2 · esforço M
- **Problema.** 30 respostas em 1.408 pesquisas (2%). A pesquisa abre só dentro do GLPI, vale 1 dia e vem depois do fechamento.
  Lá fora, o mesmo:
  - "the rating field is defaulted to 3 stars. Many of our users leave this field to 3 stars" ([#14919](https://github.com/glpi-project/glpi/issues/14919))
  - "the Satisfaction survey block displays all tickets that had no survey anwers" ([#7028](https://github.com/glpi-project/glpi/issues/7028))
  - "enquêtes de satisfaction non répondues et expirées reste affiché" ([fórum](https://forum.glpi-project.org/viewtopic.php?id=148480))
- **Proposta.**
  - **1 clique** no aviso de solução, no sino e no e-mail: 5 botões (de 😞 a 😀) num link assinado, **sem login**. O comentário é opcional,
    na página seguinte.
  - Sem valor padrão. Vale por 7 dias (parâmetro) e, depois disso, some sem deixar resto na tela.
  - Nota baixa (1 ou 2) avisa o gestor do grupo e mostra o botão "Não resolveu" (ver A6).
  - A taxa de resposta aparece no painel. A meta é passar de 2% para mais de 30%.

### A6. Solucionado é o fim: reabrir sem bagunça · prioridade 1 · esforço M
- **Problema.** Você decidiu que "Solucionado" encerra o chamado. Falta decidir o que acontece quando não resolveu de verdade
  (hoje são 31 soluções recusadas). O GLPI tem erros nessa área:
  - "Editing an existing ticket task reopens a solved ticket" ([#25663](https://github.com/glpi-project/glpi/issues/25663))
  - "It is possible to edit several things even on Closed ITIL Objects" ([#13910](https://github.com/glpi-project/glpi/issues/13910))
  - "GLPI creates a new ticket from the reply" ([#24760](https://github.com/glpi-project/glpi/issues/24760))
- **Proposta (para você aprovar).**
  - Chamado solucionado fica **somente leitura**. Nenhuma edição o reabre por acidente.
  - O requerente tem um botão **"Não resolveu"** por N dias úteis (parâmetro, sugestão: 5), no aviso de solução, no sino e no e-mail.
    É obrigatório dizer o porquê.
  - "Não resolveu" **reabre o mesmo chamado**: volta a "Em atendimento", com o mesmo grupo e técnico e um novo prazo de SLA.
    O contador "reaberto N vezes" entra no painel.
  - Passado o prazo, "Não resolveu" vira "Abrir novo chamado ligado a este" (pré-preenchido).
  - A resposta por e-mail a um chamado solucionado vira acompanhamento e mostra a opção de reabrir. Nunca cria chamado duplicado.

### A7. Modelo e campos que não seguem a categoria · prioridade 1 · esforço P
- **Problema.**
  - "Changing a ticket category don't change the ticket template" ([#22316](https://github.com/glpi-project/glpi/issues/22316))
  - "If I use the service catalog [...] The description field is empty when I choose the category" ([#24384](https://github.com/glpi-project/glpi/issues/24384))
- **Proposta.** Campos adicionais, modelo, grupo, SLA e prioridade vêm **sempre da categoria atual**. Trocar a categoria reaplica
  tudo e mostra o que mudou. O mesmo motor serve para a abertura pelo requerente, pelo técnico, pelo RH e pelos recorrentes:
  um caminho só, sem diferenças entre "interfaces".

### A8. Requerente vê botões que não fazem nada · prioridade 1 · esforço P
- **Problema.**
  - "he can modify category and urgency but there is no "save" button so it doesn't change anything" ([#25290](https://github.com/glpi-project/glpi/issues/25290))
  - "A red ! icon [...] "Some actions are unavailable due to missing required fields" [...] very confusing and vague" ([#20558](https://github.com/glpi-project/glpi/issues/20558))
- **Proposta.** A tela do requerente só mostra o que ele pode fazer: responder, anexar, "Não resolveu", avaliar.
  O status aparece em linguagem simples ("Com a equipe de Redes", "Aguardando você", "Resolvido") e com o prazo previsto.

### A9. Categorias que crescem sem controle · prioridade 2 · esforço P
- **Problema.** 126 categorias, umas 45 nunca usadas e uma duplicada ("Internos > Processos").
- **Proposta.**
  - O nome é único dentro da mesma categoria-mãe.
  - Selo "sem uso há 90 dias" na árvore, com a ação "desativar" (o histórico fica).
  - A busca da categoria na abertura usa sinônimos (ex.: "senha" acha "Reset de senha").

### A10. Tarefas agendadas sem vigia · prioridade 1 · esforço P
- **Problema.** Recorrentes, SLA, fila de e-mail e coletor dependem de tarefas agendadas. No GLPI, uma tarefa travada
  em "Running" para tudo ([#26004](https://github.com/glpi-project/glpi/issues/26004), [#14662](https://github.com/glpi-project/glpi/issues/14662)).
- **Proposta.** Cada tarefa tem um tempo máximo e é liberada sozinha quando passa dele. A última execução e os erros ficam no painel
  de saúde (A3). Se uma tarefa falhar, o recorrente é gerado no próximo ciclo, sem duplicar (a chave é o recorrente mais o dia).

### A11. Um pedido que gera vários chamados · prioridade 1 · esforço M
- **Problema.** A Nomeação gera até 9 chamados soltos. O RH só guarda os links e não vê o andamento. Lá fora já pedem isso há anos:
  "Rule will create a linked ticket "Setup Computer" for Support team" ([#290](https://github.com/glpi-project/glpi/issues/290)).
- **Proposta.**
  - **Chamado-pai com chamados-filhos** (um por serviço marcado), cada filho no grupo certo.
  - A Admissão mostra o andamento: "6 de 9 serviços prontos", com o nome de cada um.
  - O pai fecha sozinho quando todos os filhos estiverem solucionados.
  - O mesmo vale para a Exoneração e para os recorrentes de verificação.

---

## B. Setor público e LGPD

### B1. Dados pessoais nos chamados · prioridade 1 · esforço M
- **Problema.** Nomeação, Exoneração, Crachá e Carro branco pedem CPF, RG, foto, cargo e itinerário. Hoje isso fica no texto do
  chamado e aparece em e-mail, busca e exportação.
- **Proposta.**
  - Campo adicional marcado como **"dado pessoal"**: aparece mascarado na fila, na busca, no painel de TV e no e-mail (`***.456.789-**`).
  - O valor completo só aparece para quem atende o chamado, e cada visualização fica registrada na auditoria.
  - **Retenção**: os dados pessoais são anonimizados depois de N anos do fim do chamado (parâmetro, alinhado à tabela de temporalidade
    do órgão). O chamado e as estatísticas ficam.
  - A foto vai para os anexos do SGI com acesso restrito, nunca dentro do texto.

### B2. Painel de TV sem expor ninguém · prioridade 1 · esforço P
- **Proposta.**
  - O painel mostra os **dois primeiros nomes** ("Maria Aparecida"), na tela e na voz (decisão do usuário).
  - Categorias marcadas como **sigilosas** (ex.: acessos de exoneração, crachá) aparecem como "Chamado restrito" e não mostram o título.
  - Token por dispositivo, revogável, e lista de IPs permitidos (já previsto).

### B3. Transparência sem dado pessoal · prioridade 3 · esforço P
- **Proposta.** Relatório mensal de atendimento (volume, prazo cumprido, satisfação por área) exportável em CSV/PDF, sem nenhum dado
  pessoal, pronto para prestação de contas e para os indicadores do Painel Executivo.

### B4. Acessibilidade · prioridade 2 · esforço P
- **Proposta.** Abrir e acompanhar chamado inteiramente pelo teclado, com contraste AA (o DESIGN.md já cobre) e leitor de tela
  na linha do tempo. O painel de TV tem fonte grande, mas a cor nunca é o único sinal: a linha também leva um selo com texto
  ("75% do prazo").

---

## C. Integração com o resto do SGI

| # | Melhoria | Problema hoje | Proposta | Esforço | Prioridade |
| --- | --- | --- | --- | --- | --- |
| C1 | **RH: Nomeação e Exoneração** | o form do GLPI é enviado pela tela web, com login guardado; a Exoneração é aberta à mão | formulário em código no RH, chamado-pai/filhos (A11), andamento na Admissão; quando o RH registrar um desligamento, oferecer "abrir Exoneração" | G | 1 |
| C2 | **RH: técnico de férias ou afastado** | o chamado é atribuído a quem está ausente | a atribuição automática pula quem está em afastamento ou férias no RH (`servico_afastamentos`) e avisa o grupo | P | 2 |
| C3 | **RH: feriados** | — | o SLA usa `rh_feriados` (decisão já tomada) | P | 1 |
| C4 | **Patrimônio: bem no chamado** | 51 vínculos com ativos do GLPI, sem ligação com a chapa do Patrimônio | campo "bem" com busca por chapa ou série; a ficha do bem mostra os chamados dele | M | 2 |
| C5 | **Patrimônio: movimentação** | o form 19 tem 61 respostas e há 128 chamados de "Movimentação" sem efeito no Patrimônio | o chamado de movimentação gera o rascunho da Movimentação no Patrimônio, com origem, destino e responsáveis | M | 2 |
| C6 | **Localização do usuário** | 710 chamados com local preenchido à mão | o local vem preenchido com a sala do requerente (Setores/Diretório/Patrimônio) e pode ser trocado | P | 1 |
| C7 | **Reserva de Espaços** | 38 chamados "Sala de Reunião > Preparação de Sala" abertos à mão | uma reserva com equipamento (TV, vídeo) gera o chamado de preparação para o grupo responsável, com a data da reserva como prazo | M | 2 |
| C8 | **Protocolo** | pedidos que viram processo (compras, mobiliário) perdem o vínculo | botão "gerar protocolo" no chamado; o número fica ligado nos dois lados | M | 3 |
| C9 | **Contratos (DGA)** | limpeza e manutenção predial são serviços terceirizados | o chamado de categoria terceirizada aponta o contrato. O relatório de prazo por contrato serve de insumo para a fiscalização e a medição | M | 3 |
| C10 | **Plano de face** | rede sem cadastro de ponto ↔ patch panel ↔ porta | abrir chamado a partir da porta ou do ponto; o chamado mostra a configuração da porta | M | 2 |
| C11 | **Sino, Notificações e preferências** | o e-mail do GLPI está quebrado | todo aviso vai para o sino do SGI e o e-mail é opcional por pessoa (as preferências de notificação já existem) | P | 1 |
| C12 | **Busca global e paleta de comandos** | — | `#1234` abre o chamado, e "novo chamado" na paleta abre o formulário | P | 2 |
| C13 | **Painel Executivo** | — | indicadores de Chamados (volume, prazo cumprido, satisfação) no painel que já existe | P | 2 |
| C14 | **Tarefas** | — | a tarefa de chamado aparece na agenda da pessoa no módulo Tarefas (só leitura) | M | 3 |

---

## D. Outras melhorias propostas

| # | Melhoria | Por quê | Esforço | Prioridade |
| --- | --- | --- | --- | --- |
| D1 | **"Já existe um chamado parecido"** na abertura (mesma categoria, mesmo local, nas últimas 24 h) | evita duplicatas em quedas de rede, impressora ou sala | M | 2 |
| D2 | **Incidente em massa**: um chamado-mãe com "eu também" | queda de Wi-Fi gera dezenas de chamados; um aviso único na tela de abertura | M | 3 |
| D3 | **Fila ao vivo** (SSE) com "3 chamados novos" sem recarregar | o mesmo canal do painel de TV | P | 2 |
| D4 | **Respostas prontas com variáveis** (`{nome}`, `{prazo}`) | acelera o atendimento repetitivo (ex.: reset de senha, desbloqueio) | P | 2 |
| D5 | **Atalhos de teclado** na fila e no chamado (assumir, responder, solucionar) | ações frequentes, sem animação (regra de movimento do SGI) | P | 3 |
| D6 | **Motivo de pendência obrigatório** com lembrete ao requerente | 62 chamados pendentes sem motivo; o requerente nem sabe que esperam por ele | P | 2 |
| D7 | **Tempo de atendimento real** (início e fim de cada tarefa) | os relatórios do GLPI medem só datas; a gestão quer horas por tipo de serviço | M | 3 |
| D8 | **Exportar o chamado em PDF** com a linha do tempo | o plugin pdf está ativo hoje; útil para processos e auditoria | P | 3 |

---

## Plano: o que vale mais por esforço

Ordem sugerida, com a evidência (o banco da SPI e o relato externo) multiplicada pelo custo de fazer:

| ordem | item | esforço | evidência |
| --- | --- | --- | --- |
| 1 | A1 grupo obrigatório derivado da categoria | M | 121 sem categoria, 513 etiquetas de pessoa, #20832, #17739 |
| 2 | A2 SLA sempre com expediente e feriados do RH | G | 5 SLAs 24×7, 23% estourados, 5 issues e 1 fórum (tema com 2 fontes) |
| 3 | A3 + A10 saúde do e-mail e das tarefas agendadas | M | 9.207 avisos parados, #26004, #25265, 2 fóruns (tema com 2 fontes) |
| 4 | A6 Solucionado é fim + "Não resolveu" | M | decisão do usuário, 31 recusas, #25663, #13910, #24760 |
| 5 | B1 + B2 dados pessoais e painel de TV | M | CPF, RG e foto em 4 formulários |
| 6 | A11 + C1 pai/filhos para Nomeação e Exoneração | G | 51 respostas, 18 destinos, #290 |
| 7 | A4 prioridade derivada da categoria | P | 1.601 de 1.607 em "média" |
| 8 | A5 satisfação de 1 clique | M | 2% de resposta, #14919, #7028, fórum (tema com 2 fontes) |

## Posicionamento (para quando o módulo for para outros órgãos)

1. **"Não deixa configurar errado."** Para órgãos que instalaram um helpdesk e descobriram meses depois que o SLA contava a madrugada
   e o e-mail não saía, o Chamados do SGI exige grupo, expediente e feriados e avisa na hora quando algo para.
   Evidência: os temas SLA e notificações, 20 relatos em 2 fontes, mais o próprio banco da SPI.
2. **"Integrado à gestão do órgão."** Para quem mantém o RH, o patrimônio e o helpdesk separados, aqui a nomeação abre os chamados
   sozinha, o bem mostra os chamados dele e o feriado do RH vale para o prazo.
   Evidência: o recon (Nomeação com 9 destinos, 128 movimentações, 38 preparações de sala). Os relatos externos são finos (#290).
3. **"Pronto para a LGPD."** Dado pessoal mascarado, acesso auditado, retenção e painel de TV sem expor ninguém.
   Evidência: o recon. Não há relato externo: é diferencial nosso, não dor declarada.

**Recomendo a opção 1**, com a 2 como prova. É a que tem mais evidência e é a que um órgão pode conferir no próprio GLPI que já usa.

---

## Decisões do usuário (2026-11-01)

1. **Reabertura (A6): aprovada.** "Não resolveu" por 5 dias úteis reabre o mesmo chamado. Depois do prazo, abre-se um chamado novo.
   **No fim do formulário de abertura há um campo "Chamado relacionado"** (combobox com busca) que **lista só os chamados do
   próprio requerente**. Não dá para relacionar chamado de outra pessoa (o backend também valida).
2. **Prioridade (A4): aprovada**, com um acréscimo: **chamado que estoura o SLA vira "Urgente" automaticamente**. A mudança fica
   registrada no histórico como automática e aparece no selo da fila e do painel de TV.
3. **Ponto facultativo:** é um parâmetro, e o padrão é **não** contar como dia útil.
4. **Entram no MVP de virada:**
   - A3/A10: aviso de falha de e-mail e de tarefas agendadas travadas.
   - A8: tela do requerente só com ações reais.
   - B1: mascaramento de dados pessoais.
   - B2: o painel de TV mostra **os dois primeiros nomes** (ex.: "Maria Aparecida", na tela e na voz).
   - C6: o local do chamado vem preenchido **a partir do Patrimônio** (a localização ligada ao requerente).
   - C11: todo aviso vai também para o sino do SGI.
