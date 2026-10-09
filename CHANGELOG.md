# Changelog

Todas as mudanças relevantes do SGI SPI (antigo contratos-spi) ficam registradas aqui, da mais recente para a mais antiga.
Toda alteração é registrada aqui assim que é feita; commit e push só quando o usuário pedir (ver `AGENTS.md`, seção "Changelog e commits").

Formato de cada entrada: data, e as seções **Adicionado**, **Alterado**, **Corrigido** e **Removido**, conforme o caso.
Informe também migrações do banco e endpoints novos ou alterados.

## 2026-10-09

### Adicionado
- **Contratos: portarias de designação de gestão e fiscalização.** Nova aba **Portarias** no contrato (depois de Execução). Quem edita o contrato solicita a portaria escolhendo a autoridade signatária; o número é **reservado no Protocolo** (tipo "Portaria", faixa do ano) e vinculado ao contrato. A autoridade (o usuário vinculado a ela) dá o **aceite** ou devolve; o solicitante reenvia ou cancela (o número volta a ficar livre). Word e PDF saem com a marca d'água **MINUTA**, antes e depois do aceite, para postar no SEI e no DOE; o **PDF publicado** volta pela própria aba e fica anexado ao número do Protocolo e em Documentos Importantes (tipo 16). O aceite é bloqueado se faltar o RS (lido do RH, sem aparecer na tela), o processo SEI ou o objeto. O cadastro das **autoridades** fica na mesma aba (controle total em Contratos). Migração `d6f1a3c5e7b9`; endpoints `/api/contratos/{id}/portarias*` e `/api/portarias/autoridades*` (`docs/endpoints/contratos-portarias.md`).
- **Contratos: máscaras de portaria em Contratos → Modelos.** O texto da portaria vem de **duas máscaras** (com e sem portaria anterior, escolhida sozinha), editadas em página própria com editor de texto formatado e a lista de placeholders ao lado (clique insere). Aceita **somente os placeholders da lista** (`#nomegestor`, `#rsgestor`, `#numerodocontrato`, `#objetodocontrato`…); qualquer outro `#` impede salvar. Parágrafos de pessoa sem valor somem e os incisos são renumerados. Editável por SuperRoot ou por quem tem controle total em Contratos. Migração `e7a2b4d6f8c1` (tipo `portaria` em `contratos_modelos` e as duas máscaras iniciais); `GET /api/contratos/modelos/portaria/placeholders`.
- **Contratos: carteira com marcadores da competência atual.** Nova coluna **Competência** com chips: a competência em aberto mais antiga, a(s) etapa(s) aberta(s) (Medição pendente/disponível, Avaliação, Nota fiscal, Retenção, CADIN, Checklist…), **Atrasada**, **Sem competências** ou **Em dia**. Clicar abre a execução da competência. `ResumoContrato` ganha `competencia_atual`, `sem_competencias` e `criador_id`.
- **Tarefas: dias em aberto.** O cartão do quadro (ex.: "12d"), o detalhe da tarefa e o memorial das tarefas atrasadas mostram há quantos dias a tarefa está aberta (`dias_em_aberto`).
- **Tarefas: relatório memorial da tarefa (PDF e XLSX).** No detalhe da tarefa, botões que emitem o memorial com os dados da tarefa e **todos os acontecimentos** da linha do tempo, do mais antigo ao mais recente. `GET /api/tarefas/{numero}/memorial?formato=pdf|xlsx`.
- **Tarefas: quadro próprio das subtarefas.** O detalhe da tarefa-mãe tem o atalho **Abrir quadro de subtarefas** (`/tarefas/{numero}/subtarefas`, título "Equipe X - Tarefa Título - Subtarefas"), com visões Quadro e Lista e andamento independente. `GET /api/tarefas?escopo=subtarefas&tarefa=N`.
- **Tarefas: colunas da Lista ordenáveis.** Clicar no título de Tarefa, Pessoas, Prazo, Prioridade ou Checklist ordena (crescente, decrescente e ordem manual); a escolha fica na URL.

### Alterado
- **Tarefas: subtarefas fora do quadro principal.** Quadro, lista, calendário, contadores, "Minhas tarefas", agenda, carga das pessoas, busca global, painel executivo e contagem das equipes mostram só tarefas-mãe. A tarefa-mãe **não é mais bloqueada** por subtarefa em aberto (acabou o erro "Conclua antes as subtarefas em aberto"): ao mover a mãe (situação ou estágio), cada subtarefa só recebe um registro no histórico, sem mudar de posição.
- **Tarefas: cartões do quadro com altura fixa** (título em até 2 linhas) e novo nível de densidade **compacto** entre o normal e o reduzido, para os cartões não encolherem à toa quando há espaço.
- **Contratos: ACL.** **Controle total** passa a fazer tudo em qualquer contrato (editar, itens com execução gerada, previsão selada, desfazer prorrogação, reabrir competência, correção de itens e **dar ciência**, com o papel "administrador"); o nível agora se chama "Administrar contratos e empresas". **Modificação** passa a poder **excluir os contratos que ele mesmo criou**. `permissoes` do contrato ganha `pode_administrar`.
- **Contratos → Modelos** ganha a coluna **Portarias**; a tela é acessível também a quem tem controle total em Contratos (só vê as portarias).
- **Protocolo:** `anexar` aceita anexar o documento de um número reservado por outro módulo (usado pela publicação da portaria).

## 2026-10-08

### Adicionado
- **Contratos: despesas variáveis na medição.** A medição ganhou a coluna **Despesas Variáveis**: marque os itens que são despesa variável. No fim da medição aparecem **Subtotal - Medição**, **Subtotal - Despesas Variáveis** e o **Total** (a soma dos dois). Na etapa da **nota fiscal**, quando há item marcado, passa a ser obrigatório juntar **ao menos uma nota fiscal e ao menos uma nota de débito, recibo ou outro documento** da despesa; a soma desses documentos precisa ser igual ao Subtotal - Despesas Variáveis. Só a nota fiscal vai para a validação do DOF; a nota de débito, o recibo e os outros documentos ficam apenas juntados e seguem para o documento consolidado. A memória de cálculo sai em dois PDFs e o e-mail da medição concluída pede também esses documentos à empresa. O consolidado fica na ordem: medição (itens que não são despesas variáveis) → NF → medição das despesas variáveis → nota de débito/recibo/outros → demais etapas.
- **Contratos: checklist reaproveita documentos entre contratos da mesma empresa mesmo sem validade.** Se o item está marcado "Vale para outros contratos" e o documento foi juntado na mesma competência (mês) em outro contrato da empresa, o sistema oferece usá-lo. Os checklists da Prodesp foram padronizados (nomes iguais para CEEP, CEIS e e-Sanções e marca "Vale para outros contratos" nas certidões e consultas: CND Estadual, Federal e Municipal de Origem, CNDT, CRF-FGTS, CEEP, CEIS, CNEP, e-Sanções, TCE-SP, CNCIAI, SICAF e CADIN Estadual).
- **Tarefas: equipe "Contratos".** Todas as tarefas geradas pelo módulo Contratos ficam na equipe **Contratos**, da qual passam a ser membros todos os integrantes das equipes dos contratos e o Financeiro. Essas tarefas saem da fila pessoal ("Minhas tarefas") e são acompanhadas pela equipe.
- **Tarefas: repetição automática.** Ao criar uma tarefa, o bloco **Repetir** permite que ela se renove sozinha (todo dia, toda semana, todo mês ou todo ano), com intervalo, dias da semana, opção de só dias úteis e fim por data ou por quantidade de repetições. A próxima tarefa é criada alguns dias antes do prazo, e todos os responsáveis são avisados. Se algo impedir a criação (por exemplo, responsável desligado), a repetição é pausada e quem a criou recebe um aviso. A tela **Recorrências** lista as séries e permite pausar, retomar e encerrar.
- **Tarefas: tela Desempenho para a liderança.** Quatro gráficos mostram como a equipe está indo: **Burndown** (quantas tarefas faltam e se o ritmo basta para zerar), **Vazão semanal** (quanto entra e quanto é entregue por semana), **Tempo de ciclo e lead time** (quantos dias uma tarefa leva para ficar pronta) e **Fluxo acumulado** (onde as tarefas estão se acumulando). Há também o total por pessoa e filtros de período e de marcador. Cada gráfico tem um botão **?** que explica, em linguagem simples, como ler.
- **Tarefas: marcadores como no Odoo.** Os marcadores aparecem como etiquetas coloridas (12 cores). Ao clicar no campo, aparecem os mais usados; ao digitar, a lista filtra; se o marcador não existe, dá para criá-lo na hora. Para tirar, é só clicar no ×. A liderança pode trocar a cor, renomear ou excluir. O campo agora fica acima das subtarefas, na janela da tarefa.
- **Tarefas: subtarefas e dependências.** Uma tarefa grande pode ser dividida em subtarefas, com barra de progresso na tarefa principal. Também é possível dizer que uma tarefa só pode começar depois de outra. A tarefa principal não vai para validação nem conclui enquanto houver subtarefa aberta, e uma tarefa bloqueada não inicia até a que a bloqueia terminar; o sistema avisa quais estão pendentes.
- **Tarefas: etapas próprias para cada equipe.** A equipe pode criar as colunas do quadro com os nomes que usa (como "Análise" ou "Aguardando fornecedor"). Cada etapa continua pertencendo a uma das quatro fases de sempre (a fazer, em andamento, em validação e concluída), então validações, avisos e relatórios seguem funcionando.
- **Tarefas: atividades, seguidores e menções.** Dentro da tarefa dá para **agendar atividades** (um compromisso curto, com data e responsável) e concluí-las; o responsável é lembrado no dia e quando atrasa. Quem quer só acompanhar uma tarefa pode **segui-la** e recebe os avisos de comentários, prazos e validação. Escrevendo **@login** num comentário, a pessoa citada é avisada.
- **Tarefas: marcos e status da equipe.** A liderança pode criar **marcos** (entregas importantes com data-alvo) e ligar tarefas a eles. O marco fica **atingido** quando todas as tarefas terminam, e é mostrado como **no prazo**, **em risco** (há tarefa atrasada ou com prazo depois da data-alvo) ou **atrasado**. A liderança também publica **atualizações de status** da equipe e recebe, toda segunda-feira, um lembrete quando passam 7 dias sem atualização.
- **Contratos: calendário de vencimentos.** Nova tela com os vencimentos dos contratos (fim de vigência, reajuste, pagamento da nota, prazo de 48 h da nota, validade de documentos, medição atrasada, empenho insuficiente e tarefas do contrato), em visão de mês e de semana, com filtros por contrato, empresa e "meus contratos". `GET /api/contratos/calendario`.
- **SLA de prazos (Tarefas e Melhorias).** Metas de resposta e resolução em **dias úteis** (com os feriados do RH), editáveis em Administração › SLA (recurso ACL `sla`). Tarefas e sugestões mostram a situação (no prazo, em risco, estourado, cumprido) e o Desempenho mostra o % de cumprimento. Migração `b4d7f1a9c2e6`.
- **Paleta de comandos (Ctrl+K).** Ações rápidas, telas e resultados de busca em uma janela só, respeitando o acesso de cada pessoa.
- **Contratos: autenticação dos PDFs.** Avaliação, memória de cálculo e consolidado ganham hash SHA-256 e código de verificação; a **folha de autenticação** vem antes do resumo executivo do consolidado. Há tela para **verificar um PDF** (`POST /api/contratos/verificar-documento`). Não é assinatura digital. Migração `c5e8a2b6d9f1`.
- **Tarefas: responder a um comentário** e aba **Histórico** (antes "Atividade"); botão **Anexar** sempre visível ao comentar.
- **Protocolo: manual no BookStack.** Capítulo "Módulo Protocolo" (5 páginas, 30 imagens) no livro SGI SPI; fontes em `docs/manuais/protocolo/` (`publicar.py` publica e atualiza).
- **ACL: o que cada nível libera, por módulo.** Cada recurso diz com clareza o que Leitura, Modificação e Controle total liberam nele (ex.: Protocolo — "Reservar números de documentos", "Administrar o Protocolo"). Os textos aparecem na lista de regras, no formulário, no acesso efetivo e na aba Recursos. Todo recurso novo precisa ter os textos (teste `test_acl_niveis.py`).

### Alterado
- **Contratos: e-mail da nota fiscal ao DOF é obrigatório.** Ao juntar a nota fiscal, o e-mail é sempre enviado a **todo o DOF** (com cópia à equipe); não há mais caixa para marcar nem escolha de destinatários. O reenvio continua disponível.
- **Contratos: retenção de tributos.** A confirmação passou a dizer "Conferi que as retenções de tributos estão de acordo com o valor da nota fiscal apresentada."
- **Tarefas de contratos:** o título traz o **apelido e o número do contrato** (ex.: "Medição — Limpeza - 001/2026 — 09/2026") e a criação ou conclusão dessas tarefas **não gera e-mail** (o módulo Contratos já avisa).
- **Tarefas: quadro.** As colunas abertas ficam sempre em **ordem crescente de prazo**.
- **Contratos: checklist.** Mais espaço visual na caixa "Disponível do contrato…".
- **Tarefas: "participantes" agora são "responsáveis".** Os participantes já cadastrados foram convertidos automaticamente, sem perder ninguém.
- **Mural de parabéns** passa a ocupar 80% da largura da tela.
- **Contratos: gerar o consolidado novamente** passa a ser permitido a todos que podem editar o contrato.
- **Ramais:** cards com identidade visual nova (Férias em vermelho, demais em verde) e tema escuro ajustado.
- **ACL:** `GET /api/acl/recursos`, `/regras`, `/meus-acessos` e `/efetivo/{id}` devolvem `niveis` (rótulo e descrição de cada nível no recurso); valores gravados e permissões não mudaram.

### Corrigido
- Erro ao salvar uma equipe de tarefas.
- Formatação do valor da nota fiscal em tela.

### Para a equipe técnica
- Migração `a3c6e9b1d4f7` (despesas variáveis: coluna no item da medição, PDF das despesas na memória e tabela dos documentos). Script `scripts/padronizar-checklists-prodesp.py` (idempotente, com ensaio) já executado. Endpoints alterados em `docs/endpoints/contratos-execucao.md` (`PUT …/medicao`, `POST …/nota-fiscal`, detalhe da competência) e `docs/endpoints/tarefas.md`.
- Migrações do banco: `a2b5c9d3e7f8`, `b3c6d0e4f8a9`, `c4d7e1f5a9b0`, `d5e8f2a6b1c3`, `e6f9a3b7c2d4` e `e9f3a7c1b5d6`, mais `f1a4b8d2c6e7` (cores dos marcadores). Os endpoints novos e alterados estão em `docs/endpoints/tarefas.md`. O limite do bundle inicial do Angular passou de 750 kB para 800 kB (`angular.json`). É preciso reiniciar a `sgi-spi-api` para as rotas novas funcionarem.
- Migrações novas: `b4d7f1a9c2e6` (SLA + recurso ACL `sla`) e `c5e8a2b6d9f1` (documentos autenticados). Endpoints: `/api/sla/*`, `/api/contratos/calendario`, `/api/contratos/verificar-documento`; ver `docs/endpoints/sla.md`, `contratos-painel.md`, `contratos-execucao.md`, `tarefas.md` e `acl.md`. Textos dos níveis da ACL em `backend/app/services/acl_niveis.py`. A API precisa ser reiniciada para valer.

## 2026-10-06

### Corrigido
- **Fuso horário de São Paulo em todo o sistema.** Alguns textos saíam no horário do servidor (UTC, 3 horas adiantado): o PDF do Painel Executivo ("gerado em"), o relatório de tarefas, o histórico de versões das contratações, a data de "hoje" do Protocolo e do Diretório (virava o dia às 21h), o agendador de parabéns e os metadados dos PDFs (como o documento consolidado). Novos utilitários `em_sao_paulo` e `hoje_sao_paulo` (`app/core/banco.py`) e o processo da API agora roda com `TZ=America/Sao_Paulo`; as datas com hora continuam gravadas em UTC.
- **Campos de formulário fora do padrão** (ex.: o seletor de Prioridade na janela da tarefa aparecia no visual nativo do navegador). Causa: o estilo dos campos só existia por contexto (`.grade-formulario select` etc.). Agora há um **estilo base global** para `select`, `textarea` e `input` de texto/número/data em `styles.scss`, com especificidade baixa (os estilos de contexto e a classe `.form-control` continuam mandando), de modo que todo campo novo já nasce no padrão; regra registrada no `CLAUDE.md`.
- **Busca global:** passa a pesquisar também as **empresas contratadas** (razão social, nome fantasia, CNPJ, endereço e nome dos prepostos), com o mesmo acesso dos contratos; o resultado abre a ficha da empresa.

### Adicionado
- **Manuais do BookStack dentro do portal.** Novo módulo **Manuais** (barra lateral): estantes e livros do BookStack (https://instrucoes.spi.sp.gov.br) lidos pelo portal, no layout do SGI, com sumário lateral, página anterior/próxima, busca e link "Abrir no BookStack". Os manuais continuam sendo escritos no BookStack. O portal lê pela API com uma **conta de serviço somente leitura** (token cifrado), então o usuário não precisa de conta lá; o acesso é pela ACL `manuais`, que nasce **sem regras (todos os usuários logados)**.
  - O HTML das páginas é **sanitizado** no servidor (sem scripts, iframes, estilos ou eventos); imagens passam por `/api/manuais/imagem` (só `/uploads/` da instância) e links entre páginas viram links do portal. Cache de 5 minutos para listas, sumários e páginas.
  - **Somente o livro "SGI SPI"**: nova configuração `livros_permitidos` (Administração › Integração BookStack, migração `e8b2d6f0a4c3`) limita o que o portal mostra; hoje só o livro 147. Com um único livro, **Manuais** abre direto nele; os demais livros não aparecem (nem na busca) e respondem 404. A regra **falha fechada**: lista vazia = nenhum livro (nunca todos).
  - Endpoints novos: `GET /api/manuais`, `/livros/{id}`, `/paginas/{id}`, `/busca`, `/imagem`; `GET`/`PUT /api/integracao-bookstack` e `POST …/testar` (SuperRoot), com a tela **Administração › Integração BookStack**. Migração `d7a1c5e9b3f2` (tabela `integracao_bookstack` e recurso de ACL `manuais`). Docs em `docs/endpoints/manuais.md`.
- **Documentação da API protegida por ACL.** `/api/documentacao` (Swagger), `/api/redoc` e `/api/openapi.json` deixam de ser públicos: só usuário logado com o recurso `documentacao-api` ≥ LEITURA (SuperRoot sempre). O recurso nasce **fechado** (só a conta administrativa) e o SuperRoot libera quem quiser em Controle de acesso; as páginas usam a sessão do SGI (basta estar logado no portal). O item "Documentação da API" saiu da seção só-SuperRoot e aparece a quem tem o recurso. Migração `c6e0a4b8d2f1`; docs em `docs/endpoints/documentacao-api.md`.
- **Atalhos fixos na barra lateral (módulo/CRUD).** Novo grupo dobrável **Atalhos** na barra lateral, igual para todos os usuários (internos e externos), com os links divididos em **categorias** (cada uma também dobrável); atalhos internos abrem a rota do SGI e externos (`http/https`) abrem em nova aba. Tela **Gerenciar atalhos** (`/admin/atalhos`) para criar, editar, ordenar, ativar/inativar e excluir categorias e atalhos, restrita ao recurso de ACL `atalhos` (nasce fechado: só o administrador até o SuperRoot liberar).
  - Endpoints novos: `GET /api/atalhos`, `GET /api/atalhos/gestao`, `POST|PUT|DELETE /api/atalhos/categorias[/{id}]` e `POST|PUT|DELETE /api/atalhos/itens[/{id}]` (docs em `docs/endpoints/atalhos.md`). Migração `b5d9f3a7c1e2` (tabelas `atalhos_categorias` e `atalhos_fixos` e recurso de ACL `atalhos`).
- **Recusa da nota fiscal pelo Financeiro (DOF) na retenção de tributos.** O Financeiro pode **recusar a nota com justificativa** (mínimo de 10 caracteres): a etapa da **nota fiscal volta a ficar aberta**, com novo campo para subir a nota (PDF; **XML opcional**), e o ciclo **se repete sem limite** até o Financeiro conferir a retenção. **CADIN e checklist já feitos são mantidos.**
  - A recusa gera um **PDF** (baixável na etapa, para juntar a um processo) e um **e-mail obrigatório à equipe do contrato e a todos os prepostos da empresa**, com a justificativa e o PDF anexado (reenvio disponível). A equipe recebe também uma pendência na caixa de mensagens.
  - O **documento consolidado** mostra a trilha: nota recusada → recusa nº N → outra nota → … → nota aprovada → retenção, e o resumo executivo ganha a tabela "Trilha da nota fiscal".
  - Endpoints novos: `POST /api/contratos/{id}/competencias/{id}/retencao/recusar` e `POST …/recusas/{recusa_id}/reenviar-email`; o detalhe da competência traz `recusas[]` e `pode_recusar`. Migração `a4c8e2f6b0d1` (tabela `contratos_competencias_recusas`). Docs em `docs/endpoints/contratos-execucao.md`.

## 2026-10-05

### Adicionado
- **Escalonamento de tarefas atrasadas (SLA, parte 1), em memorial diário:** no job das 07:00, a tarefa atrasada há 1+ dia é escalonada à liderança direta da equipe (pessoal: o criador) e, há 3+ dias, à liderança das equipes acima. Cada líder recebe **um aviso por dia** (caixa e e-mail) com a **tabela das tarefas atrasadas** dele (Nº, Título, Responsável, Atraso e Link), em vez de um e-mail por tarefa; cada nível registra o evento "escalonada" na linha do tempo, uma vez por prazo. O corpo dos e-mails da mensageria aceita tabela simples. Migração `f3b7d1e9a5c4`; sem endpoint novo (ver `docs/endpoints/tarefas.md`).
- **Abrir Chamado pelo SGI (integração com o GLPI).** Novo item **Abrir Chamado** na barra lateral, para todos os usuários, abre um modal com **Assunto** e **Descrição do problema**; nome, setor, superior imediato, e-mail, telefone, celular (se preenchido) e andar - lado vêm do cadastro, e o chamado termina com "Aberto pelo SGI". O chamado é criado no GLPI pela API REST, em nome do usuário (sem categoria: a TI classifica), com limite de 5 por hora por usuário.
  - Endpoints novos: `GET /api/chamados/solicitante`, `POST /api/chamados`, `GET /api/chamados`, `GET`/`PUT /api/integracao-glpi` e `POST /api/integracao-glpi/testar` (docs em `docs/endpoints/chamados.md`). Tela **Administração › Integração GLPI** (URL, tokens cifrados, liga/desliga, testar conexão). Migração `d1f4b8a2e6c9` (tabelas `integracao_glpi` e `chamados_glpi` e recurso de ACL `abrir-chamado`, sem regras = aberto a todos). Dependência nova: `httpx`.
  - **No GLPI** (alterações feitas por SSH): API ligada, cliente de API "SGI SPI" liberado só para o IP do servidor do SGI e conta de serviço `sgi.integracao`; como desfazer está em `docs/endpoints/chamados.md`. Integração **ativa** e testada contra o GLPI real (conexão, busca de usuário e um chamado de teste, apagado em seguida).
  - **Igual ao formulário "Informática" (id 3) do GLPI:** título `Informática | assunto`, conteúdo `1) Assunto … 2) Descrição de Problema … 3) Local do Problema …` (mais os dados do solicitante e "Aberto pelo SGI"), **Local do problema sempre o andar e lado do cadastro** (sem campo no modal; vira a localização equivalente no GLPI), requerente = o usuário, **grupo SUPORTE atribuído** (o chamado nasce "Em atendimento (atribuído)"), SLAs de atendimento e solução, incidente, sem categoria. Grupo, SLAs, modelo e prefixo ficam configuráveis na tela Integração GLPI. O modal mostra só "Seus dados". Migração `e2a6c4d8b0f3`. No GLPI foi criado o perfil **SGI INTEGRAÇÃO** (cópia do TECNOLOGIA + leitura de Localizações) para a conta de serviço.
  - **Anexos:** o modal aceita até 5 arquivos (imagem colada com Ctrl+V ou escolhida, PDF, .docx, .xlsx, CSV; 5 MB cada), enviados ao chamado na criação (`POST /api/chamados` agora é `multipart/form-data`). Testado no GLPI real (chamado e documento de teste apagados).
  - **Dados temporários:** enquanto a CGP não valida o cadastro, o chamado leva os dados que o usuário informou (marcados "temporário"); o primeiro cadastro já abre chamado completo. Removida do modal a frase sobre "Aberto pelo SGI" (a assinatura continua no texto do chamado).
- **Navegação inspirada no GLPI (fase 1):** **busca global** no topo (Ctrl+K ou `/`) em contratos, contratações, tarefas, pessoas, setores e telas do menu, respeitando o ACL; **favoritos** do menu salvos na conta e **recentes** no navegador; **anterior/próximo** no detalhe do contrato (‹ 3 de 34 ›) respeitando a busca, o filtro e a ordenação da carteira.
  - O breadcrumb (trilha) passa a existir também em Mensagens e Assinatura de e-mail, e a tela de Ramais aceita `?q=` (a busca global leva direto à pessoa).
  - Endpoints novos: `GET /api/busca`, `GET`/`PUT /api/favoritos` e `GET /api/contratos/{id}/vizinhos` (docs em `docs/endpoints/navegacao.md`). Migração `c9e3a7f1b5d8` (tabela `usuarios_favoritos`).

- **Reaproveitamento de documentos do checklist entre contratos da mesma empresa** ("documento da empresa"). O item do checklist ganha a opção **Documento da empresa** (com validade), nas abas Checklists, nos modelos globais e na importação XLSX (coluna **Vale para outros contratos**). Na etapa do checklist, o documento sem anexo mostra "Disponível do contrato X (competência mm/aaaa) · válido até …" quando outro contrato da mesma empresa tem o de **mesmo nome**, também marcado, anexado e com validade até o fim do período; **nada é copiado sozinho**: **Usar este documento** ou **Trazer os documentos válidos de outros contratos**. O reaproveitado mostra "Reaproveitado do contrato X (competência mm/aaaa) · válido até …" (só na tela; o consolidado não mostra).
  - Endpoints novos: `POST /api/contratos/{id}/competencias/{id}/checklist/{documento_id}/reaproveitar` e `POST …/checklist/reaproveitar-todos`; campos novos `vale_outros_contratos`, `reaproveitado_contrato` e `sugestao_outro_contrato` (ver `docs/endpoints/contratos-execucao.md`). Migração `b8d2f6a4c1e7`.
- **Links clicáveis em todo o portal:** endereços `http://` e `https://` digitados em campos de texto livre (observação do checklist, descrição e comentários de tarefas, mensagens, sugestões de melhoria, justificativas, diário de bordo, recados do mural, comentários das contratações etc.) viram links que abrem em outra aba (pipe `linkificar`, com o texto escapado). Só frontend.

### Alterado
- **Carteira de contratos (`/contratos`):** todas as colunas (número, empresa/objeto, datas, situação, base mensal e valor global) passam a ser **ordenáveis** (clicar no título ordena; clicar de novo inverte) e o **apelido** abaixo do número aparece em **caixa alta**. O número do contrato também é um link (Ctrl+clique ou botão do meio abre em nova aba) e o menu de ações ganhou "Abrir em nova aba". `GET /api/contratos` ganha os parâmetros `ordenar_por` e `direcao` (docs em `contratos-cadastro.md`); sem migração.
- **Consolidado:** documento opcional do checklist que não foi anexado deixa de aparecer como "Não anexado" no resumo executivo; só é citado quando anexado (já não tinha página nem índice).

### Corrigido
- **Recentes do menu lateral:** a lista era do navegador (duas pessoas no mesmo computador viam as telas uma da outra) e crescia até 8. Agora é **por usuário**, guarda **só as últimas 5 telas** e some da tela ao sair ou trocar de usuário; os favoritos também ficam por usuário no navegador. As chaves antigas são apagadas.

### Removido
- **E-mail resumo diário de mensagens pendentes** ("SGI SPI: N mensagem(ns) aguardando sua ciência"): o job das 07:00 deixa de enviá-lo. As pendências seguem na caixa de mensagens e nos lembretes de ciência pendente.
- **Cartão "Helpdesk"** da página inicial do portal (o chamado agora se abre pelo item "Abrir Chamado" da barra lateral).

## 2026-10-04

### Adicionado
- **Importação de checklists e formulários de avaliação por planilha XLSX**, no mesmo fluxo da importação de contratos (modelo, prévia com erros por linha e campo, confirmação). Documentação em `docs/endpoints/contratos-importacao-modelos-xlsx.md`.
  - No contrato (abas Checklists e Formulários): cria uma versão **inativa**. `GET`/`POST /api/contratos/{contrato_id}/{checklists|formularios}/importacao-xlsx/{modelo|previa}`, `POST /api/contratos/{contrato_id}/checklists/importacao-xlsx` e `POST /api/contratos/{contrato_id}/formularios/importacao-xlsx`.
  - Nos modelos globais (SuperRoot): `GET`/`POST /api/contratos/modelos/importacao-xlsx/{checklist|formulario}[/modelo|/previa]`.
  - O modelo da planilha é gerado pela API, com exemplo preenchido. As regras são as do cadastro manual (escala crescente, pesos de cada grupo somando 100).
  - Migração `e5a8c3d7f2b1`: recurso de ACL `importacao-modelos`, que nasce fechado (só a conta administrativa); o SuperRoot libera os demais.

- **Tema escuro opcional.** No menu do usuário (canto superior direito) há o seletor **Tema: Claro / Escuro / Auto** (Auto segue o tema do sistema operacional; é o padrão).
  - A escolha vale na hora e fica gravada no navegador (`localStorage`, `sgi-spi.tema`, aplicada antes do Angular carregar, sem piscar, inclusive na tela de login) **e na conta**, para acompanhar o usuário em outros aparelhos; depois do login, o tema da conta prevalece.
  - Endpoint novo `PUT /api/autenticacao/tema` e campo `tema` em `UsuarioSessao` (documentação em `docs/endpoints/autenticacao.md`). Migração `f6b9d4e8a3c2` (coluna `usuarios.tema`, padrão `auto`).
  - As cores neutras fixas dos estilos passaram a variáveis `--cor-<hex>` (definidas em `frontend/src/styles/_tema.scss`); no tema claro as cores são exatamente as de antes. Impressão e PDF saem sempre no tema claro. Gráficos e telas com cores fixas em código TypeScript podem precisar de ajuste fino no tema escuro.

### Alterado
- **Documento consolidado da execução:** o **índice passa a ser a primeira página**, e o título e as páginas de cada documento são **hiperlinks** que levam direto ao documento dentro do PDF (nos enviados, à contracapa). Os documentos também aparecem nos marcadores do leitor de PDF. A numeração "Página X de N" e a composição do resumo contam o índice. Ver `docs/endpoints/contratos-execucao.md`. Não há endpoint nem migração novos.

- **Ramais:** a página usa toda a largura da janela (antes limitada a 1280 px), com mais colunas em telas largas (cartões a partir de 270 px) e 60 contatos por página (antes 24). O limite de 1840 px do layout com barra lateral também deixa de valer nessa página.

### Corrigido
- **Departamento validado agora faz o usuário virar membro do setor.** Antes, o Departamento do perfil era só texto e a ACL (que consulta a participação no setor) não enxergava o vínculo: quem estava na "Subsecretaria de Gestão Corporativa" no perfil, mas fora de `membros_setor`, ficava sem os acessos liberados ao setor (caso do jesmartins na importação de XLSX).
  - Quando o Departamento passa a valer (validação da CGP, recusa com correção, alteração direta de CGP/SuperRoot ou edição pelo administrador), o usuário entra no setor de mesmo nome e sai do setor do Departamento anterior; participações em outros setores não são tocadas. Ver `docs/endpoints/setores.md`.
  - Renomear um setor atualiza o Departamento dos usuários que apontavam para o nome antigo.
  - Migração `a7c1e5b9d3f4`: inclui como membros os usuários que já tinham um Departamento válido e nenhum vínculo.

## 2026-10-02

### Adicionado
- **Módulo Contratações (ETP e TR)**, trazido do 10.23.1.220 e ampliado. Endpoints `/api/contratacoes/...` (documentação em `docs/endpoints/contratacoes.md`); migração `e5b8c3d7a921`.
  - Árvore de seções e itens (item, subitem, inciso, alínea, subseção) com editor de texto formatado (TipTap), entrada em lote com prévia, tabela do item 1.1 do TR, duplicar e mover.
  - **Acesso por documento:** criador, editores e revisores (o revisor só comenta e propõe). No 1.220 todos viam todos os documentos; aqui só o criador e a administração, e o criador compartilha.
  - **Versões no estilo BookStack:** cada versão guarda o documento inteiro e mostra o que foi incluído, retirado, alterado (diferença por palavra) e movido; dá para visualizar e restaurar. Existe também o **histórico de cada item**, com restauração só do item. Antes da primeira edição de uma sessão grava-se uma versão automática.
  - Revisões (comentário ou proposta, aplicar, resolver), com aviso ao criador e aos editores e lembrete diário de revisão parada.
  - Conferência antes de concluir, vínculo com contrato (aba na ficha do contrato), exportação em Word (sobre os modelos originais) e PDF, importação de Word com prévia.
  - Dados migrados do 1.220: 10 documentos, 122 seções, 1.547 itens, 2 linhas da tabela do TR e 30 revisões (3 aplicadas), cada documento com a versão "Migrado do SGI". Recurso ACL `contratacoes` criado com uma regra para os 5 autores.
  - Scripts `extrair-contratacoes-sgi.py` e `migrar-contratacoes-sgi.py`. Dependências novas: `python-docx`, `lxml` e `@tiptap/*`.
- **`scripts/conferir-sgi.py`:** conferência somente leitura entre o 1.220 e o sistema novo (ids por tabela, contratos por número, usuários por login), para o dia do desligamento do 1.220.
- **Módulo Protocolo** (numeração institucional por tipo e exercício), migrado do 1.220 com melhorias (próximo número, linha do tempo, sigilo, vínculo com contrato, painel, exportação). Migração `d4a7b2c6e815`; ver `docs/endpoints/protocolo.md`.
- Assinatura de e-mail (`/api/assinatura-email`), com `docs/endpoints/assinatura-email.md`.
- Migrações pendentes do repositório incluídas nesta entrega: `3f23277d8a5a`, `78fca44765aa`, `a7d3c91e5b20`, `b8e41f6a2c93`, `c1f2a8d94e57`.

### Alterado
- **Notícias:** a janela de prévia abre bem mais larga.

### Corrigido
- **Notícias:** editar uma notícia já aprovada com o campo "publicar em" vazio apagava a data de publicação e a notícia sumia do portal e do slider. Agora a data é mantida. A notícia "Outubro Rosa" foi restaurada.
- **Protocolo:** margens internas zeradas nas telas e campo "Contrato (opcional)" quebrado.

## 2026-10-01

### Alterado
- **Contratos: o valor unitário dos itens aceita até 4 casas decimais** (ex.: R$ 0,075 por página). Antes, o banco arredondava para 2 casas (0,075 virava 0,08).
  - Vale para o cadastro e a edição do contrato, a importação por XLSX, a medição, o reajuste (o novo preço passa a ter 4 casas, e o teto também aceita 4) e o aditamento/supressão.
  - Telas, PDFs e planilhas mostram o preço unitário com 2 a 4 casas (R$ 0,075; R$ 171,22). Subtotais, base mensal, valor global e medição continuam em centavos.
  - Migração `3f23277d8a5a`: `valor_unitario` de `contratos_itens`, `contratos_competencias_itens` e `contratos_alteracoes_itens`, e `valor_unitario_atual`, `valor_unitario_reajustado` e `valor_referencial` de `contratos_reajustes_itens`, de 2 para 4 casas. Nenhum valor existente muda.
  - Valores já gravados arredondados (ex.: 0,08) precisam ser corrigidos editando o contrato.

## 2026-09-30

### Alterado
- **Contratos › "Importar do SGI" volta, só para a conta root, com outro fluxo:**
  - a janela pede o número do contrato e a senha do SGI;
  - o contrato é lido no SGI, somente leitura;
  - abre "Novo contrato" já preenchido, **sem salvar** (cabeçalho, itens e equipe convertida para os usuários daqui); o usuário revisa e salva;
  - se a empresa não existir aqui, a tela oferece cadastrá-la com os dados e os prepostos do SGI;
  - avisos na tela: itens sem UF, pessoas sem conta aqui, prorrogações, e competências e NEs que não vêm.
  - Novo endpoint `POST /api/contratos/migracao-sgi/rascunho`. A importação completa com substituição saiu da tela, mas continua na API.
- `scripts/migrar-contratos-sgi.py`:
  - nova opção `--contrato NNN/AAAA`, que importa um contrato só do SGI (10.23.1.220) sem apagar nada daqui e reaproveita a empresa se ela já existir;
  - o script passa a gravar o campo `numero` do contrato.
  - Com essa opção, o **contrato 010/2024** (Suporte e infraestrutura - PD24008, PRODESP) foi importado.
- **HTTPS em `portal.spi.sp.gov.br`**, com o certificado emitido pela SPI-AD01-CA.
  - Com o DNS já apontando para o 10.23.0.254, todo acesso por HTTP, pelo IP ou por outro nome redireciona para `https://portal.spi.sp.gov.br`, com o mesmo caminho (favoritos e e-mails antigos com o IP continuam funcionando).
  - `nginx/sgi-spi.conf` e `scripts/instalar.sh` ganharam o HTTPS e a opção `--dominio`, com a conferência dos arquivos do certificado.
- `URL_PUBLICA` passa a ser `https://portal.spi.sp.gov.br`: os links dos e-mails usam o novo endereço.

### Adicionado
- **Módulo Melhorias**, trazido do "Banco de melhorias" do 10.23.1.220 e ampliado.
  - **Envio:** o botão flutuante **"Sugerir melhoria"** aparece em todas as telas autenticadas.
    - Pode ser **arrastado** para não cobrir o que importa.
    - O **"×"** esconde o botão só na aba atual; uma aba nova traz o botão de volta ao canto inferior direito.
    - O envio leva o texto, a tela de origem e até 3 prints (arquivo ou Ctrl+V).
  - **Minhas sugestões** (`/melhorias`, item em Módulos): o autor acompanha a situação e a resposta da equipe e recebe aviso na caixa de Mensagens, com e-mail, quando elas mudam.
  - **Triagem** (`/melhorias/triagem`), para o SuperRoot ou quem tem CONTROLE_TOTAL no novo recurso `melhorias` da ACL:
    - filtros por situação, módulo, período e busca;
    - resposta ao autor e observação interna (o autor não vê);
    - histórico;
    - **converter em tarefa** no Módulo Tarefas;
    - **exportar planilha** e **relatório em PDF** com os prints.
  - Quem faz a triagem recebe aviso a cada sugestão nova.
  - Migração `11d8a496ccab`: tabelas `melhorias_sugestoes`, `melhorias_anexos` e `melhorias_eventos`, e o recurso `melhorias` na ACL, sem regras.
  - Endpoints `/api/melhorias/…` (ver `docs/endpoints/melhorias.md`).
- **Contratos › Diário de bordo: anexos.** Até 5 arquivos por ocorrência, com o formato conferido pelo conteúdo. Os arquivos vão anexados ao e-mail da ocorrência (acima de 15 MB no total, o e-mail só lista os nomes) e aparecem no PDF do diário e na conversa, com download.
- **Contratos › Diário de bordo: a ocorrência pode impactar a avaliação da qualidade.** A pergunta "Esta ocorrência impacta a avaliação da qualidade?" vincula a ocorrência a itens do formulário de avaliação ativo. Na avaliação da competência do período:
  - os itens mostram as ocorrências;
  - **nota máxima nesses itens exige justificativa** (avaliação inicial e do gestor);
  - o PDF ganha a seção "Ocorrências do diário de bordo consideradas";
  - uma ocorrência registrada depois de salva a avaliação gera aviso para revisar as notas.
- **Contratos › Avaliação dos serviços: envio à contratada por e-mail.** Ao gerar o PDF, o relatório vai aos prepostos, com cópia para a equipe, pedindo a devolução assinada. A tela mostra o resultado e tem "Reenviar e-mail".
- Migração `57c0f7e1349f`:
  - tabelas `contratos_diario_anexos` e `contratos_diario_itens_avaliacao`;
  - coluna `impacta_avaliacao` na ocorrência;
  - colunas `email_enviado_em`, `email_ok`, `email_destinatarios` e `email_erro` na avaliação da competência.
- Migração `b3d91e7a0c24`: avaliações com PDF gerado antes desta versão ficam com o e-mail "não enviado", com a explicação, e podem ser reenviadas.
- Endpoints:
  - `GET /api/contratos/{id}/diario/{ocorrencia_id}/anexos/{anexo_id}`;
  - `POST /api/contratos/{id}/competencias/{cid}/reenviar-email-avaliacao`.

### Alterado
- `POST /api/contratos/{id}/diario` passa a receber `multipart/form-data`: o campo `dados` leva o JSON da ocorrência, agora com `impacta_avaliacao` e `itens_avaliacao`, e o campo `arquivos` leva os anexos.
- `DiarioContrato` ganha `itens_avaliacao`. `LeituraOcorrencia` ganha `anexos`, `impacta_avaliacao` e `itens_avaliacao`. `LeituraAvaliacao` ganha `ocorrencias` e `email`.
- A tela da competência consulta de novo, em instantes, enquanto o e-mail da medição ou o da avaliação ainda está sendo enviado.

### Corrigido
- Notícias › Configurar portal: a caixa "Incluir notícia publicada" da curadoria volta para "Escolha…" depois de incluir.
- Notícias: na janela "Aprovar e publicar", deixar a data vazia não publicava na hora quando o redator tinha pedido publicação agendada; agora data vazia publica imediatamente.

### Alterado
- Contratos: o e-mail da medição concluída pede à contratada a nota fiscal **em PDF e em XML** (o XML é lido automaticamente na etapa Nota fiscal).

### Removido
- Tela "Início" com a saudação: a página inicial agora é o portal de notícias.

### Adicionado
- **Módulo Notícias (Fases 2 a 4: telas, portal como página inicial e migração do 10.23.1.243).**
  - **A página inicial do sistema (`/`) passa a ser o portal de notícias:**
    - pública para visitantes, com "Entrar no SGI SPI";
    - para quem está logado, aparece com a barra lateral;
    - traz slider (passagem automática, setas, pontos, toque e teclado), cartões sem repetir os slides e atalhos.
  - `/noticias` (arquivo com busca, categoria e mês) e `/noticias/:slug` (notícia com PDF incorporado e "Leia também").
  - **Gestão** em Módulos › Notícias:
    - lista por situação, com o total aguardando aprovação;
    - editor com texto formatado, **recorte 2:1 da capa no próprio editor** (arrastar e zoom, ou "imagem inteira" sem cortes) e aviso de baixa resolução;
    - publicação imediata ou agendada, aviso a setores e pessoas, comunicado com ciência, anexos e prévia;
    - Aprovar em verde, Devolver com motivo e histórico de versões.
  - **Configurar portal** (aprovadores): quantidade de slides, tempo, passagem automática, curadoria manual, título sobreposto, cartões, atalhos e categorias, com prévia.
  - Rotas `GET /api/noticias/opcoes-setores` e `/opcoes-usuarios` para o público do aviso.
  - **Migração do 10.23.1.243** (`scripts/extrair-noticias-243.py`, somente leitura, e `scripts/migrar-noticias-243.py`): 23 notícias, 3 anexos e 4 atalhos, com categorias sugeridas e capas adequadas sem cortar as artes.
- **Módulo Notícias (Fase 1: backend)**, que traz para o SGI SPI o portal de notícias do 10.23.1.243, com melhorias.
  - **Portal público** (sem login): `GET /api/portal` (slider configurável, cartões sem repetir os slides, atalhos) e arquivo/detalhe em `/api/noticias/publicas`, com busca, categoria e mês.
  - **Fluxo de aprovação pela ACL `noticias`:** redator (MODIFICACAO) escreve e pede publicação imediata ou agendada; aprovadores (CONTROLE_TOTAL) recebem caixa + e-mail de aprovação pendente, aprovam ou devolvem com motivo. Sem regras no recurso, só o SuperRoot publica.
  - **Agendamento sem cron:** a visibilidade é calculada pela data; a rotina de e-mails (2 min) só dispara os avisos das notícias que acabaram de aparecer.
  - **Aviso ao público** (usuários e setores, com os setores abaixo) e **comunicado com ciência**, pela mensageria.
  - **Capa 2:1 sem ajuste manual:** recorte enviado pelo editor ou modo "imagem inteira" (fundo desfocado); versões WebP 1600/800/400.
  - Corpo em HTML **sanitizado** (`nh3`), histórico de versões, anexos conferidos pelo conteúdo, categorias, atalhos e configuração do slider.
  - Migração `aef1af3a69ff`: tabelas `noticias*` e `portal_*`, categorias iniciais, configuração e recurso `noticias` na ACL. Dependências `pillow` e `nh3` fixadas em `requirements.txt`. Ver `docs/endpoints/noticias.md`.

### Corrigido
- Contratos › Minhas pendências e Alertas de risco: a busca e os seletores de filtro apareciam sem o estilo do site.

### Adicionado
- **Módulo Tarefas: releitura da interface, estilo Trello (com lista estilo Asana como alternativa).**
  - **Navegação lateral do módulo:**
    - traz Nova tarefa, Minhas tarefas, "Para validar" (liderança, com o total) e a árvore de equipes com as contagens;
    - é recolhível;
    - a barra lateral do sistema continua com um só item.
  - **Quadro como tela principal:**
    - colunas do pipeline com cartões compactos: etiquetas coloridas, título, chip de prazo colorido, checklist, comentários, anexos e avatares;
    - arrastar entre colunas ou usar o menu "⋯";
    - coluna Concluída recolhível, com as 10 mais recentes;
    - **criação rápida** "+ Adicionar tarefa" (só o título; você como responsável, prazo em 7 dias às 18:00);
    - **raias por pessoa**.
  - **Cabeçalho do quadro:**
    - visões Quadro, Lista, Calendário e Pessoas;
    - **avatares que filtram por pessoa** (Shift+clique soma);
    - busca e filtros num popover;
    - linha de resumo clicável no lugar dos seis cartões de indicadores.
  - **Lista estilo Asana:** seções recolhíveis por situação, com ordem manual por arraste.
  - **Calendário** (mês ou semana): tarefas no dia do prazo; arrastar para outro dia abre "Alterar prazo" com a justificativa.
  - **Janela da tarefa sobre o quadro** (`?tarefa=123`) no lugar da página separada:
    - título e propriedades editáveis no lugar;
    - ações do pipeline na coluna direita;
    - atividade com comentários e linha do tempo;
    - o link `/tarefas/123` dos e-mails continua funcionando.
  - **Agenda da pessoa ao atribuir** (Nova tarefa, participantes e transferência): carga e tarefas da pessoa em lista ou **linha do tempo estilo Gantt** (4 semanas). Novo endpoint `GET /api/tarefas/pessoas/{usuario_id}/agenda`, aberto a quem atribui e **com os títulos de todas as tarefas da pessoa**, por decisão do usuário.
  - `TarefaResumo` ganhou `envolvidos`, `comentarios`, `anexos`, `criado_em`, `iniciada_em` e `concluida_em`, com contagens agregadas e sem consulta por tarefa. Sem migração.
- **Módulo Tarefas (Fase 4: migração do 10.23.1.220).** `scripts/extrair-tarefas-sgi.py` (somente leitura) e `scripts/migrar-tarefas-sgi.py` (ensaio por padrão, `--gravar`, `--substituir`, conferência que impede gravar com divergência). Carga feita: 159 tarefas, 971 eventos, 66 anexos (SHA-256 conferido), 5 equipes e 20 marcadores, com números, autores e datas preservados. Mapeamento em `docs/endpoints/tarefas.md`.
  - Migração `9639d1d834db`: `tarefas_marcadores.nome` passa de 60 para 120 caracteres.

### Alterado
- Linha de etapas: "Em validação" pulada (tarefa pessoal, ou concluída pela liderança) não aparece mais como alcançada.

### Removido
- Dados do teste automatizado do Módulo Tarefas (tarefas "(E2E)", equipe de teste e anexos). A tarefa #11, criada por um usuário, foi mantida.

- **Módulo Tarefas (Fase 3: equipes, liderança e relatórios).**
  - `/tarefas/equipes`: cartões por equipe (em aberto, atrasadas, em validação, concluídas, carga), subequipes abaixo da equipe pai, atalhos "Ver tarefas", "Pessoas", "Validar entregas" e "Configurar".
  - Configuração separada do acompanhamento (`/tarefas/equipes/:id/configurar`, só dono ou SuperRoot): nome, equipe pai (sem ciclos), líderes, membros, marcadores com cor e desativação.
  - **Visão da liderança** (`?visao=pessoas`): cartões por pessoa, da maior para a menor carga, com barras empilhadas por situação nesta equipe e link para as tarefas da pessoa.
  - **Relatório** XLSX (abas Tarefas e Por pessoa) ou PDF por escopo, período e marcador: `GET /api/tarefas/relatorio`.
  - `PessoaCarga.na_equipe`: contagens da pessoa só nas tarefas da equipe (com `equipe_id`).

### Alterado
- Título da lista de uma equipe não repete "Equipe" quando o nome já começa assim.

- **Módulo Tarefas (Fase 2: telas)**, item "Tarefas" em Módulos na barra lateral.
  - `/tarefas` (minhas), `/tarefas/equipes/:id`, `/tarefas/pessoas/:login`: indicadores clicáveis (em aberto, atrasadas, vencem hoje, críticas, em validação, carga), chips de situação e de filtros ativos, busca com atraso, ordenação; **tudo guardado na URL** (recarregar mantém o estado).
  - **Tabela** com prazo relativo ("Atrasada há 1 dia"), selo "prazo alterado N×" e ordem manual por arrastar (ou setas pelo teclado).
  - **Kanban** de 4 colunas: arrastar segue o pipeline (movimento proibido explica o caminho; recusa da API desfaz o movimento) e botões no cartão como alternativa.
  - `/tarefas/nova`: na equipe, o responsável é escolhido numa lista com a carga de cada pessoa e alerta de sobrecarga.
  - `/tarefas/:numero`: linha de etapas com data e autor, só as ações permitidas (validar em verde, devolver em vermelho claro), janelas de prazo, transferência, entrega e devolução/reabertura com motivo, edição, checklist com progresso, comentários com anexos e **linha do tempo agrupada por dia**, com ícone e cor por tipo, de/para em selos, prazo antigo riscado, justificativas destacadas, filtros em chips e "Carregar mais". SuperRoot remove itens com motivo.

### Alterado
- `TarefaResumo.participantes` passa a contar só os participantes além do responsável.

- **Módulo Tarefas (Fase 1: backend)**, reconstrução do app de tarefas do 10.23.1.220 com melhorias.
  - **Pipeline com validação:** A fazer → Em andamento → **Em validação** (o executor entrega) → Concluída (a liderança valida) ou volta com motivo. Tarefa sem equipe conclui na entrega.
  - **Prazo** só com justificativa, guardando o prazo original e o número de prorrogações.
  - **Transferência** dentro da equipe (a liderança, para qualquer pessoa), com justificativa.
  - **Linha do tempo** só cresce, com de/para, filtros por tipo e "carregar mais"; comentários com até 5 anexos de formatos conferidos pelo conteúdo.
  - **Avisos** com e-mail oficial: atribuição, prazo, transferência, entrega para validação, validação, devolução, comentário, vencimento, atraso e validação parada há 2 dias (janela que não bloqueia).
  - **Equipes** com dono, líderes, membros e hierarquia; marcadores por equipe; checklist; carga de trabalho com faixas.
  - Migração `2320f1538b36`: tabelas `tarefas*`. Endpoints `/api/tarefas/*` (ver `docs/endpoints/tarefas.md`). `servico_anexos.guardar_arquivo` aceita formatos além de PDF.

## 2026-09-29

### Alterado
- **Um só "Salvar usuário"** na página do usuário: grava conta, perfil, dados funcionais do RH e o ajuste do período (o bloco do RH perdeu os botões "Salvar dados funcionais" e "Ajustar" ali; em Validações eles continuam).

### Corrigido
- O botão "Salvar usuário" da nova página não gravava (o formulário usava `ngSubmit` sem o módulo que emite esse evento).

### Alterado
- **Edição de usuário em página própria** (`/usuarios/novo` e `/usuarios/:id`), no lugar da janela: cartões Conta e Perfil institucional, dados funcionais do RH ao lado e barra de ações fixa no rodapé; funciona no celular.
- **A CGP administra usuários e setores pela ACL.**
  - As gravações passaram a aceitar CONTROLE_TOTAL nas ACLs `usuarios` e `setores` (antes, só SuperRoot); recurso sem regras não libera gravação.
  - A migração `b2e4f6a8c0d1` cria as regras para o setor "Coordenadoria de Gestão de Pessoas" (membros). Com isso, só CGP e SuperRoot veem Usuários e Setores.
  - Sem escalada de privilégio: quem não é SuperRoot não concede o papel SuperRoot, não altera nem exclui contas SuperRoot, não define senha de outra pessoa e não mexe em grupos sistêmicos.
  - Negação sem CONTROLE_TOTAL passa a responder `403 acl_negado` (antes `acesso_negado`).
- **Painel de afastamentos:**
  - cada período do gráfico abre uma janela com os detalhes e, para quem pode decidir, Aprovar e Recusar;
  - botão Aprovar em verde (Recusar mantém o vermelho claro);
- **Padrão de cores das decisões:** aprovar e validar em verde; recusar mantém o vermelho claro. Aplicado também em RH › Validações (Validar, Validar selecionadas e Validar todas deste usuário). Classes `acao-aprovar` (linha de tabela) e `acao-positiva` (botão principal).
  - a justificativa da recusa (painel e Validações) ganhou o estilo dos campos do site;
  - os botões no rodapé das janelas não encostam mais na borda.
- **Validação do cadastro com data e hora:** em Meu perfil (e no histórico de Validações) o campo mostra "Validado por [nome] em dd/mm/aaaa hh:mm:ss" (antes, só a data).
- **Folha de ponto** some do menu da conta root, que não tem vínculo funcional.
- **Folha de ponto só sai com o cadastro em dia.**
  - Com alteração de cadastro aguardando validação, ou sem os dados funcionais (jornada, horário de trabalho, intervalo, RG/CIN, RS/PV), o usuário vê o aviso "Folha de ponto indisponível".
  - A CGP recebe mensagem e e-mail: "[Nome] quer baixar a folha de ponto, mas…", no máximo um por motivo e por dia. O aviso se encerra quando os dados são preenchidos ou as alterações são analisadas.
  - Endpoint `GET /api/rh/folha-ponto` passa a responder `409` (`folha_cadastro_pendente` ou `folha_dados_incompletos`).
  - Downloads mostram a mensagem de erro da API (antes, o corpo em `Blob` se perdia).
- **E-mail de changelog: marcar um setor pai marca os filhos**; a lista separa "Estrutura organizacional" e "Grupos sistêmicos".
- **E-mail de changelog também para usuários e setores escolhidos**, além de "todos os usuários ativos" e do teste.
  - Um ou mais usuários pelo seletor e/ou setores sistêmicos ou institucionais. O setor inclui os membros, quem o tem como Departamento e os setores filhos.
  - O histórico mostra quem foi escolhido.
  - Migração `a1d3f5b7c9e2`: destino `selecionados` e coluna `destino_descricao` em `mensageria_envios_changelog`.
  - Endpoints: `POST /api/mensageria/changelog/envios` aceita `destino = selecionados`, `usuarios_ids` e `setores_ids`; o rascunho traz `setores[]`.
- **Folha de ponto fiel ao modelo de frequência da SPI**, conservando a estrutura do documento.
  - **Frente:** cabeçalho em caixa com o brasão, identificação em duas colunas, a tabela do mês inteira com as marcas em vermelho ("---------" na hora; SÁBADO, DOMINGO, FERIADO, PONTO FACULTATIVO, FÉRIAS na assinatura), as informações financeiras e as assinaturas.
  - **Verso:** só as anotações ("CONSOLIDAÇÃO" com as linhas pautadas, data e assinatura do superior ou do responsável).
  - Sem mudança de API.

### Adicionado
- **Preparação para o lançamento do Módulo RH (MVP)**, a partir de uma análise de prontidão do banco de produção.
  - **Carga em lote dos dados funcionais por planilha** (RH › Validações › Importar planilha):
    - o modelo já traz todos os servidores ativos e os valores atuais; a CGP completa e envia;
    - a prévia mostra, por linha, o que muda e os erros; só grava sem nenhum erro;
    - célula vazia mantém o valor; "Dias disponíveis no período vigente" corrige o saldo de quem já gozou parte do período.
  - **Lançamento de afastamento pela CGP em nome do servidor** (Painel › Lançar afastamento), para férias e licença-prêmio já combinadas ou gozadas fora do sistema, inclusive retroativas, com motivo e opção de ignorar o saldo. O servidor recebe e-mail.
  - **Validação em lote** em RH › Validações: filtro por campo, seleção de vários usuários e "Validar todas deste usuário". Pensado para os ~210 setores que serão preenchidos no primeiro acesso.
  - **Relatório de saldos** (Painel, Excel e PDF), com período vigente, disponíveis, "pedir até" e licença-prêmio de cada servidor.
  - **Alerta em Parâmetros** quando o setor da CGP não tem ninguém (os avisos da CGP não chegariam a ninguém).
  - **Dados fictícios para demonstração:** `scripts/dados-ficticios-rh.py --criar` / `--remover` (pessoas "[FICTÍCIO]", sem e-mail, removidas em cascata).
  - Endpoints `POST /api/rh/afastamentos/lancamento`, `GET /api/rh/relatorios/saldos`, `POST /api/rh/cadastro/alteracoes/validar-lote` e `GET`/`POST /api/rh/cadastro/funcionais/importacao[/modelo|/previa]`; os parâmetros trazem `membros_cgp`. Sem migração.
- **Mensageria com e-mail de changelog** (Administração › Mensageria, só para a conta root).
  - O botão "Preparar e-mail de changelog" abre uma janela com um rascunho das novidades do CHANGELOG ainda não enviadas, em linguagem de usuário.
  - Assunto e texto editáveis, com prévia ao lado no layout oficial com brasão.
  - Envio de teste para um e-mail ou para todos os usuários ativos (um e-mail por pessoa, com confirmação), e histórico com o resultado de cada envio.
  - Migração `7a3c5e9f1b2d`: tabela `mensageria_envios_changelog`.
  - Endpoints `GET /api/mensageria/changelog/rascunho`, `POST /api/mensageria/changelog/previa`, `GET`/`POST /api/mensageria/changelog/envios` (ver `docs/endpoints/mensageria.md`); `GET /api/autenticacao/sessao` ganhou `conta_root`.
- **Férias por período aquisitivo** (Módulo RH).
  - A CGP informa o **início do período aquisitivo** de cada pessoa só como dia e mês (dd/mm). A cada 12 meses entram 30 dias de férias (parametrizável) e o saldo não usado **expira**.
  - Férias debitam o saldo do período em que começam; dá para agendar no período vigente ou no próximo.
  - **Aviso oficial de férias a vencer** por e-mail à pessoa, ao autorizador (ou substituto) e à CGP: 1º aviso com antecedência de saldo + antecedência mínima + folga (15 dias, parametrizável), lembrete 7 dias antes da data-limite para pedir e último aviso nessa data. No início de cada período, e-mail com os novos dias.
  - Tela de férias com o período vigente, o próximo e o alerta "Peça até…"; painel com "Férias a vencer"; parâmetros com os dias por período, a folga e a opção de desligar os avisos.
  - A CGP pode ajustar os dias do período vigente (ex.: férias gozadas antes do sistema) e vê o histórico dos períodos.
  - A licença-prêmio continua por exercício (ano civil), com saldo manual.
  - Migração `5de0447b97ad`: tabela `rh_periodos_aquisitivos`, colunas `inicio_aquisitivo_dia`/`_mes` em `rh_dados_funcionais`, `periodo_aquisitivo_id` em `rh_afastamentos` e parâmetros `dias_ferias_por_periodo`, `folga_aviso_ferias_dias` e `aviso_ferias_ativo`.
  - Endpoints: `PUT /api/rh/cadastro/usuarios/{id}/periodo-vigente` (novo); dados funcionais com `inicio_periodo_aquisitivo` e `periodos[]` (sem `saldo_ferias_dias`); `GET /api/rh/afastamentos/meus` com `periodo_vigente` e `proximo_periodo`; painel com `ferias_a_vencer`.
- **Folha de ponto em PDF** (menu do usuário, abaixo de "Meu perfil").
  - O usuário escolhe a competência (do mês atual, 12 meses para trás e 2 para frente) e baixa a folha no modelo de frequência da SPI.
  - Vem com o setor, a identificação (nome, RG/CIN, RS/PV, função, jornada, plantão, horários, estudante, intervalo), uma linha por dia com sábados, domingos, feriados, pontos facultativos e férias ou licença-prêmio aprovadas, as informações financeiras e as assinaturas na frente, e a consolidação no verso.
  - Endpoints `GET /api/rh/folha-ponto?competencia=AAAA-MM` e `GET /api/rh/folha-ponto/competencias` (ver `docs/endpoints/rh-folha-ponto.md`).
- **Feriados e pontos facultativos** (RH › Feriados): todos consultam; a CGP cadastra, edita e exclui.
  - Aparecem destacados no calendário de férias, no painel e na folha de ponto.
  - Novo parâmetro da CGP: "Períodos não podem começar em feriado ou ponto facultativo" (desligado por padrão).
  - Migração `9c5e7a1b3d4f`: tabela `rh_feriados` e parâmetro `inicio_vedado_feriado`.
  - Endpoints `GET`/`POST /api/rh/feriados` e `PUT`/`DELETE /api/rh/feriados/{feriado_id}`; `feriados[]` em `GET /api/rh/afastamentos/meus` e no painel.
- **Jornada, horários e documentos nos dados funcionais** (visíveis só para a CGP e o SuperRoot): jornada semanal, regime de plantão, horário de trabalho, horário de estudante, intervalo de almoço e descanso, RG/CIN nº e RS/PV nº. Alimentam a folha de ponto.
  - Migração `8b4d6f0a2c3e`: colunas novas em `rh_dados_funcionais`.
- **Trilha de navegação clicável em todo o site** ("Início / RH / Parâmetros"): Início leva à página inicial, o módulo à entrada do módulo e o nome da página à própria página. No módulo Contratos, o número do contrato leva ao contrato.
- **Dados funcionais do RH na tela de Usuários:** a janela de edição mostra, só para a CGP e o SuperRoot, o bloco de autorizador, substituto, topo da hierarquia, exercício e saldos, com gravação própria. É o mesmo componente da tela de Validações.
- **Módulo RH** (item "RH" em Módulos), com os papéis CGP (Coordenadoria de Gestão de Pessoas, pelo setor `SETOR_CGP` e filhos), autorizador (com substituto) e usuário.
  - **Atualização cadastral mensal:**
    - modal bloqueante "Confirme ou atualize seus dados" uma vez por **mês civil**, no lugar da regra de 30 dias;
    - **superior imediato obrigatório**, sem ser o próprio usuário e sem ciclos na hierarquia;
    - cada campo alterado fica **pendente de validação da CGP** (valem os dados anteriores), e a CGP recebe e-mail;
    - a CGP **valida** ("Validado por … em …") ou **recusa com justificativa e correção** (o usuário recebe e-mail);
    - histórico completo;
    - dados funcionais exclusivos da CGP: autorizador (sugestão: o superior), substituto, topo da hierarquia e saldos.
    - Tela `/rh/validacoes`.
  - **Férias e licença-prêmio:**
    - calendário do exercício (ano civil) com seleção de intervalo e "férias ou licença-prêmio?", com saldos visíveis;
    - regras parametrizáveis pela CGP (mínimo de dias, início vedado, antecedência, prazo de cancelamento, emenda, alerta de setor), além de saldo por tipo e sem sobreposição;
    - aprovação pelo autorizador, pelo substituto (com o autorizador afastado) ou pela CGP; recusa com justificativa;
    - alteração exige nova aprovação;
    - e-mails a cada status; `gozado` automático e lembrete de pedidos parados há 3 dias, no timer das 07:00;
    - **painel** mensal/anual (amarelo = aguardando, verde = aprovado; "[F]/[LP] Nome – Setor"), com filtros por pessoa, setor (com filhos) e tipo, alertas de setor e exportação em PDF e Excel.
    - Telas `/rh/ferias`, `/rh/painel-afastamentos` e `/rh/parametros`.
  - Endpoints `/api/rh/*` (ver `docs/endpoints/rh-cadastro.md` e `rh-afastamentos.md`); `GET /api/autenticacao/perfil` ganhou `situacao_campos` e `superior_obrigatorio`.
  - Migração `6be74b4141cb`: tabelas `rh_alteracoes_cadastrais`, `rh_dados_funcionais`, `rh_afastamentos`, `rh_afastamentos_eventos` e `rh_parametros`.
  - Nova variável `SETOR_CGP`.

### Alterado
- **Confirmação mensal do cadastro obrigatória também para os SuperRoot.** Só a conta `root` fica dispensada (e também de informar o superior imediato).
- **Janela de edição de usuário mais larga:** conta e perfil institucional à esquerda, em três colunas, e os dados funcionais do RH à direita; cabeçalho e botões fixos, rolagem só no meio; uma coluna no celular.

- **O projeto passa a se chamar SGI SPI – Sistema de Gestão Integrada** (antes: Contratos SPI / contratos-spi).
  - **Nome visível:** abas do navegador ("… | SGI SPI"), tela de login, e-mails, PDFs, OpenAPI ("API SGI SPI – Sistema de Gestão Integrada") e documentação. O módulo Contratos continua com o mesmo nome.
  - **Identificadores técnicos:**
    - serviço `sgi-spi-api` e timers `sgi-spi-mensageria-*` (no lugar de `contratos-spi-*`);
    - site do Nginx `sgi-spi`;
    - build em `frontend/dist/sgi-spi`;
    - pacote `sgi-spi-frontend`;
    - chaves do navegador `sgi-spi.*`: a sessão salva com o nome antigo é migrada, sem deslogar ninguém;
    - logs `sgi_spi.*`;
    - variável `SGI_SEM_RESTART` nos scripts.
  - Unidades e site reinstalados no servidor; as antigas foram removidas.
- **E-mails com layout oficial:** brasão do Estado embutido, cabeçalho "Governo do Estado de São Paulo · Secretaria de Parcerias em Investimentos", filete vermelho, botão de acesso e rodapé "SGI SPI – Sistema de Gestão Integrada". Vale para a mensageria, os avisos dos contratos, os lembretes e o teste do servidor SMTP (`app/services/modelo_email.py`; `ImagemEmbutida` em `cliente_smtp`).

- **Setores reorganizados pela estrutura oficial da SPI** (decreto de organização).
  - Raiz: "Secretaria de Parcerias em Investimentos".
  - Abaixo dela, os 6 órgãos vinculados ao Secretário e as 2 Subsecretarias, com as Diretorias e as Coordenadorias: 28 setores, em `app/services/estrutura_setores.py`.
  - Os setores institucionais antigos e os membros deles foram apagados. Os grupos sistêmicos (Administradores, Operadores de Contratos, Auditores) foram mantidos.
  - O **Departamento de todos os usuários foi limpo**: no próximo login, cada usuário comum é levado a "Meu perfil" para escolher o novo setor.
  - Novo script `scripts/reorganizar-setores.py` (ensaio por padrão; `--gravar` aplica) e a função `servico_setores.substituir_estrutura`. Sem migração de esquema e sem mudança de API.

## 2026-09-28

### Adicionado
- **Mensageria (caixa de mensagens)**, inspirada no sistema de referência e sem bloquear a navegação:
  - **sino** na barra superior com o total de pendentes e tela **`/mensagens`** (item "Mensagens" na barra lateral), com as abas **Recebidas** e **Enviadas por mim**;
  - **mensagem avulsa** para usuários e setores (setores exigem SuperRoot ou ACL `mensageria-setores` = CONTROLE_TOTAL):
    - prioridade, categoria, expiração e link interno;
    - "também enviar por e-mail", pelo servidor SMTP ativo;
  - estados **lida**, **ciente** ("Li e estou ciente") e **resolvida** (pendência encerrada pela ação no sistema). A busca não diferencia acentos;
  - **acompanhamento** de quem enviou: situação por destinatário, % de ciência e botão "Lembrar pendentes por e-mail".
- **Janela ao entrar na equipe de um contrato:** quem é cadastrado (ou trocado) como gestor, fiscal ou suplente recebe o modal "Você foi cadastrado como <papel> no contrato <número>…", também por e-mail.
- **Avisos automáticos dos contratos na caixa:**
  - ocorrência do diário;
  - medição concluída;
  - NF juntada: pendência do Financeiro, resolvida ao salvar a retenção;
  - retenção conferida: pendência da equipe, resolvida ao gerar o consolidado;
  - prorrogação, reajuste e aditamento/supressão concluídos.
  - Avisos de contrato excluído somem junto.
- **Tarefas agendadas** (systemd, instaladas por `scripts/instalar.sh`):
  - `contratos-spi-mensageria-emails.timer`, a cada 2 min: fila de e-mails dos avisos automáticos;
  - `contratos-spi-mensageria-lembretes.timer`, às 07:00 (America/Sao_Paulo):
    - vencimento do contrato a 90, 60 e 30 dias;
    - medição atrasada há mais de 30 dias;
    - lembrete de ciência de mensagens alta/crítica no 3º dia;
    - resumo diário por e-mail das pendências.
- Endpoints `/api/mensagens` (`resumo`, caixa, abrir, `ciencia`, envio, `destinatarios`, `enviadas`, `lembrar`). Migração `0c11fdac4f46`: tabelas `mensagens` e `mensagens_entregas` e recurso de ACL `mensageria-setores` (fechado).

### Alterado
- **Número do contrato em formato livre** (ex.: `012/2026`, `CT-45/2025`, `20214514`), até 60 caracteres, no cadastro, na edição e na importação XLSX.
  - Continua único, sem diferenciar maiúsculas. `1/2026` e `001/2026` seguem sendo o mesmo número.
  - `sequencial`/`ano` passam a ser opcionais: preenchidos só no padrão NNN/AAAA, para ordenar a carteira e sugerir o próximo número. Números livres vêm depois na ordenação.
  - A busca da carteira e das empresas encontra qualquer trecho do número.
  - Nomes de arquivo usam o número saneado (`CT-45/2025` → `CT_45_2025`).
  - A planilha XLSX mantém o número como digitado (`7/2026` não vira mais `007/2026`).
  - Na tela de cadastro, trocar a data inicial não sobrescreve mais um número digitado.
  - Migração `46921c091299`: coluna `contratos.numero`, preenchida com os números existentes, índice único em `lower(numero)`, `sequencial`/`ano` anuláveis.
- **Vigências:** removida a frase explicativa abaixo do título do quadro.

### Removido (temporariamente)
- **Botão "Importar do SGI"** oculto na carteira (`importacaoSgiHabilitada = false` em `carteira.component.ts`). O endpoint `/api/contratos/migracao-sgi` continua disponível ao SuperRoot.

### Adicionado
- **Relatório PDF da aba Itens** (`/contratos/:id?aba=itens`), com o botão "Relatório PDF".
  - Traz a identificação do contrato, os totais da vigência atual e a tabela dos itens (UF, tipo, códigos, quantidades total, mensal, executada e disponível, valor unitário, subtotal mensal).
  - Novo endpoint `GET /api/contratos/{contrato_id}/itens/pdf` (ACL `contratos` ≥ LEITURA).
- **Aba "Vigências"** (`/contratos/vigencias`), ao lado de "Painel" no cabeçalho do módulo de contratos.
  - Uma linha do tempo por contrato vigente, do que vence primeiro ao último.
  - Os trilhos têm a mesma largura, cada um na escala do próprio contrato (início → fim da vigência atual). O preenchimento é o tempo decorrido.
  - Mostra blocos das prorrogações e marcas de reajuste. A cor segue a proximidade do vencimento: até 90 dias, até 180 dias e acima disso.
  - Também mostra dias restantes, data de vencimento e meses ainda prorrogáveis, com filtro de empresa.
  - Novo endpoint `GET /api/contratos/painel/vigencias` (ACL `contratos` ≥ LEITURA).

### Alterado
- **Ícone do site (favicon)** com o brasão do Estado de São Paulo, no lugar do ícone padrão do Angular.
  - `favicon.ico` em 16 a 256 px, recortado de `assets/imagens/brasao.png` com fundo transparente.
  - Também `icone-192.png` e `apple-touch-icon` (180 px), referenciados em `index.html`.

### Alterado
- **Reajuste com reajustes e descontos por item** (tela `/contratos/:id/reajuste`):
  - cada item tem o seu percentual: positivo reajusta, negativo dá desconto, zero mantém o preço. Aceita de −100 (exclusive) a 1000; `indice_percentual` passou de `ge=-100` para `gt=-100`;
  - novo campo "Aplicar a todos os itens", que preenche o mesmo percentual em todos (depois ajustável item a item);
  - a evidência continua sendo um único PDF por reajuste;
  - no topo: mês de referência, mês de reajuste do contrato, vigência e competências recalculadas;
  - o novo preço e a variação de cada item são calculados enquanto se digita, com aviso de alterações não salvas. A memória (PDF/XLSX) ganhou a coluna "Variação" e o destino da diferença das competências já medidas.
- **Diferença retroativa líquida:** positiva continua gerando a competência `-dif` (itens com desconto entram com preço negativo). **Negativa vira crédito da SPI**, abatido no valor autorizado da próxima medição:
  - o que não couber passa para a seguinte, e a reabertura da medição devolve a sobra;
  - sem competência a medir, fica pendente até a próxima ser gerada.
- **Execução:**
  - `valor_autorizado` = medido × % liberado − desconto de reajuste;
  - novos campos `desconto_reajuste` e `descontos_reajuste` no detalhe da competência;
  - o desconto aparece no rodapé da medição, na etapa da NF, na memória de medição, no PDF da retenção e no resumo do consolidado.
- `LeituraReajuste` ganhou `diferenca_retroativa`, `competencia_credito`, `abatimentos` e `credito_pendente`.
- Migração `0ecc10bd1805`: tabela `contratos_abatimentos_reajuste` e coluna `contratos_reajustes.diferenca_retroativa`.

### Corrigido
- **Importação XLSX, quantidades grandes e dízimas:** números vindos de célula numérica do Excel passam a ser arredondados para as casas aceitas (4 nas quantidades, 2 no valor unitário). Antes, valores de fórmulas (ex.: 1/3) ou muito grandes, que o Excel guarda em ponto flutuante, eram recusados com "deve ter no máximo 4 casa(s) decimal(is)". Quantidades de até 99 trilhões (4 casas) continuam aceitas; número digitado como texto com casas a mais continua sendo erro.

## 2026-09-26

### Adicionado
- **Importação de contrato por planilha XLSX:** botão "Importar XLSX" na carteira de contratos.
  - Lê a planilha "Checklist de Alimentação do Sistema de Contratos" e mostra uma prévia com erros (com a linha da planilha) e avisos.
  - Depois da confirmação, cadastra numa transação só a empresa (se nova), o preposto (se novo) e o contrato com os itens.
  - Empresa e preposto já cadastrados são reaproveitados sem alteração, e as divergências viram avisos. A equipe não é importada.
  - Endpoints `POST /api/contratos/importacao-xlsx/previa`, `POST /api/contratos/importacao-xlsx` e `GET /api/contratos/importacao-xlsx/modelo`.
  - Novo recurso de ACL `importacao-contratos`, que nasce fechado (só a conta root) e é liberado por usuário ou setor na tela de ACL. Migração `d4f7b2c9e1a3`.

- **Unidade de Fornecimento (UF) nos itens do contrato:**
  - campo obrigatório na janela do item, logo depois do nome;
  - coluna "UF" nas tabelas de itens do cadastro e do detalhe;
  - coluna opcional "UF" (K) na planilha de importação.
  - Campo `unidade_fornecimento` em `GravacaoItem` e `LeituraItem`. Migração `e5a8c3d1f2b4`.

- **Limpar documento importante:** botão "Limpar" ao lado de "Substituir" na aba Documentos Importantes. O PDF sai do contrato e o documento volta a "Não anexado"; o arquivo fica guardado para auditoria. Endpoint `DELETE /api/contratos/{contrato_id}/documentos/{codigo}` (códigos 1 a 23).

### Alterado
- **Uma ciência já basta para avançar** em todas as etapas que pedem ciência da equipe:
  - **medição:** a conclusão exige uma ciência, e não mais duas de pessoas diferentes;
  - **aditamento/supressão:** uma ciência libera a memória e a formalização;
  - **ateste da avaliação:** deixou de ter assinantes indicados por papel e virou **ciência da equipe, como na medição**. Qualquer integrante vigente registra a sua, uma já libera o PDF, e mudar as notas apaga as ciências. Removido o endpoint `PUT .../avaliacao/assinaturas`; `avaliacao.assinaturas` e `assinaturas_definidas_em` deram lugar a `avaliacao.ciencias` (sem migração: a coluna JSON é a mesma);
  - **painel:** as pendências "registrar sua ciência" somem para todos depois da primeira ciência e voltam a apontar a etapa;
  - a prorrogação não muda, porque a ciência no parecer já era opcional.
  - Endpoints com regra alterada: `POST .../medicao/concluir`, `POST .../avaliacao/pdf`, `POST .../alteracoes/{id}/memoria`, anexos `de_acordo`/`termo` e conclusão da alteração. `ciencias_minimas` passa a valer 1.
- **Avaliação do gestor só quando necessária:** a seção só é habilitada quando alguma nota inicial fica abaixo da máxima. Com todas na máxima, vale a nota inicial, e a ciência no ateste vem logo depois. Novo campo `avaliacao.precisa_avaliacao_gestor`; `PUT .../avaliacao/gestor` responde 400 quando não é necessária.
- **Painel de contratos:** "Minhas pendências" e "Alertas de risco" viraram resumos clicáveis, só com título e total. A lista das primeiras ocorrências saiu, e o clique abre a tela correspondente em cartões.
- **Documento consolidado da competência:**
  - segue a ordem de execução: medição → avaliação (quando houver) → NF → retenção → CADIN → checklist → resumo executivo (agora por último, com a composição do documento e as páginas de cada parte);
  - cada documento enviado ganha uma contracapa na identidade visual do sistema, dizendo que documento é aquele, quando e por quem foi enviado (nome completo);
  - as páginas são numeradas em sequência ("Página X de N"), e os documentos enviados mantêm o layout e a orientação originais.
  - **Gerar novamente** passou a ser do gestor do contrato ou do SuperRoot, inclusive depois da OB; os demais recebem 403. Novo campo `pode_gerar_consolidado_novamente` no detalhe da competência.
- **Todos os PDFs gerados pelo sistema em A4 paisagem:** avaliação, retenção e parecer de prorrogação, que estavam em retrato, passaram para paisagem.
- **Módulos → Contratos abre no painel** (`/contratos/painel`), e não mais na carteira. A carteira continua acessível pelos atalhos do módulo, e o item da barra lateral fica destacado em todas as telas de contratos.
- **Painel, execução orçamentária:** o valor pago agora entra na barra do mês da competência paga, e não no mês em que a OB foi lançada. Assim, a liquidação de 08/2026 paga em setembro aparece em agosto.
- **Regra do projeto:** toda alteração entra no CHANGELOG na hora, e commit/push só acontecem quando o usuário pedir (`AGENTS.md` e `CLAUDE.md`).
- **Diário de bordo mais compacto:**
  - cabeçalho do balão numa linha, com selos de data e competência;
  - glosas em chips e balões mais largos;
  - área do chat acompanhando a altura da janela;
  - pergunta "Esta ocorrência implicará glosa?" com seletor Não | Sim, no lugar dos rádios desproporcionais.
- **Janela "Criar/Editar checklist" reorganizada:**
  - nome e modelo global no topo;
  - tabela dos documentos, com tipo Obrigatório | Opcional e ações ↑ ↓ remover (agora dá para reordenar);
  - faixa única para adicionar documento;
  - resumo de documentos e obrigatórios no rodapé.
- **Seletor de exercício** do painel e dos alertas com lista fixa (do contrato mais antigo, ou 8 anos atrás, até 2 anos à frente), rolável, que não muda ao escolher.
- **Prorrogação:** o parecer (opcional) passa a ser a última seção da tela, depois da formalização.
- **Tela de cadastro/edição do contrato reorganizada** em três grupos:
  - Identificação: empresa, número, apelido e objeto;
  - Vigência: data inicial, vigência, data final calculada, e vigência máxima com a data-limite;
  - Execução e reajuste: periodicidade, mês de reajuste e situação.
- Mensagens de validação de números decimais traduzidas para o português ("deve ser um número", "no máximo N casas decimais").

### Corrigido
- **Quantidade total dos itens contínuos:** no cadastro/edição do contrato, a quantidade aparecia como "—". Agora mostra qtd. mensal × meses da vigência, também na janela do item.

## 2026-09-25

### Adicionado
- **Servidores SMTP** (SuperRoot, `/admin/smtp`). Cadastro no mesmo molde dos diretórios LDAP: senha cifrada, um servidor ativo, teste de conexão e envio de e-mail de teste.
  - Endpoints `/api/smtp/servidores`, `/testar`, `/{id}`, `/{id}/testar` e `/{id}/enviar-teste`.
  - Migração `3486e80ca434` (tabela `servidores_smtp`).
- **Diário de bordo do contrato**, na aba "Diário de bordo" do detalhe.
  - A equipe registra ocorrências com data, opcionalmente com glosa (item e quantidade).
  - Cada ocorrência gera e-mail à equipe e aos prepostos ativos, e há PDF do diário.
  - Na medição aparecem as colunas "Saldo", "Glosas" e "Saldo líquido", e não é possível medir acima do saldo líquido.
  - Ao concluir a medição, um e-mail com a memória de cálculo e o diário em PDF pede a nota fiscal em até 48 h.
  - Endpoints `/api/contratos/{id}/diario`, `/diario/pdf`, `/diario/{ocorrencia_id}/reenviar` e `/competencias/{id}/reenviar-email-medicao`.
  - Migração `7566f71dd5a5`.
- **Etapa "Retenção de tributos"** na execução.
  - A NF-e/NFS-e é enviada com o XML, e os valores lidos do XML aparecem na etapa (incluindo a CSLL).
  - O setor DOF confere a retenção, o sistema gera o PDF e envia os e-mails da NF e da retenção.
  - Endpoints `/competencias/{id}/retencao`, `/reenviar-email-nf` e `/reenviar-email-retencao`.
  - Migração `508822e8dedd`.
- **Setores importados do SGI SPI:** os 28 setores foram trazidos do 10.23.1.220, em leitura apenas.
- **Departamento do perfil como combobox**, alimentado pelos setores (endpoint `/api/autenticacao/perfil/opcoes-departamento`).

### Alterado
- **Etapas paralelas:** depois da nota fiscal, retenção, CADIN e checklist ficam abertos ao mesmo tempo. O documento consolidado só é liberado com os três concluídos. Migração `c3e9a1f4b7d2`.

## 2026-09-24 a 2026-09-25

### Alterado
- Cabeçalho padrão ("Criado por José Eduardo Santana Martins" + finalidade do arquivo) e comentários explicativos em todos os `.py` do backend e `.ts` do frontend. O teste de cabeçalho cobre os dois.

## 2026-09-24

### Adicionado
- Versão inicial do contratos-spi:
  - autenticação local e LDAP, perfil institucional, usuários, setores, ACL e diretórios LDAP;
  - módulo de contratos: carteira, cadastro, empresas e prepostos, documentos importantes, previsão orçamentária, Notas de Empenho, checklists e formulários de avaliação, execução mensal, prorrogação, reajuste, aditamento/supressão, painel, relatórios e modelos globais;
  - importação dos contratos do SGI SPI.
