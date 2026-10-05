# Changelog

Todas as mudanças relevantes do SGI SPI (antigo contratos-spi) ficam registradas aqui, da mais recente para a mais antiga.
Toda alteração é registrada aqui assim que é feita; commit e push só quando o usuário pedir (ver `AGENTS.md`, seção "Changelog e commits").

Formato de cada entrada: data, e as seções **Adicionado**, **Alterado**, **Corrigido** e **Removido**, conforme o caso.
Informe também migrações do banco e endpoints novos ou alterados.

## 2026-10-05

### Adicionado
- **Escalonamento de tarefas atrasadas (SLA, parte 1), em memorial diário:** no job das 07:00, a tarefa atrasada há 1+ dia é escalonada à liderança direta da equipe (pessoal: o criador) e, há 3+ dias, à liderança das equipes acima. Cada líder recebe **um aviso por dia** (caixa e e-mail) com a **tabela das tarefas atrasadas** dele (Nº, Título, Responsável, Atraso e Link), em vez de um e-mail por tarefa; cada nível registra o evento "escalonada" na linha do tempo, uma vez por prazo. O corpo dos e-mails da mensageria aceita tabela simples. Migração `f3b7d1e9a5c4`; sem endpoint novo (ver `docs/endpoints/tarefas.md`).
- **Abrir Chamado pelo SGI (integração com o GLPI).** Novo item **Abrir Chamado** na barra lateral, para todos os usuários, abre um modal com **Assunto** e **Descrição do problema**; nome, setor, superior imediato, e-mail, telefone, celular (se preenchido) e andar - lado vêm do cadastro, e o chamado termina com "Aberto pelo SGI". O chamado é criado no GLPI pela API REST, em nome do usuário (sem categoria: a TI classifica), com limite de 5 por hora por usuário.
  - Endpoints novos: `GET /api/chamados/solicitante`, `POST /api/chamados`, `GET /api/chamados`, `GET`/`PUT /api/integracao-glpi` e `POST /api/integracao-glpi/testar` (docs em `docs/endpoints/chamados.md`). Tela **Administração › Integração GLPI** (URL, tokens cifrados, liga/desliga, testar conexão). Migração `d1f4b8a2e6c9` (tabelas `integracao_glpi` e `chamados_glpi` e recurso de ACL `abrir-chamado`, sem regras = aberto a todos). Dependência nova: `httpx`.
  - **No GLPI** (alterações feitas por SSH): API ligada, cliente de API "SGI SPI" liberado só para o IP do servidor do SGI e conta de serviço `sgi.integracao`; como desfazer está em `docs/endpoints/chamados.md`. Integração **ativa** e testada contra o GLPI real (conexão, busca de usuário e um chamado de teste, apagado em seguida).
  - **Igual ao formulário "Informática" (id 3) do GLPI:** título `Informática | assunto`, conteúdo `1) Assunto … 2) Descrição de Problema … 3) Local do Problema …` (mais os dados do solicitante e "Aberto pelo SGI"), **Local do problema obrigatório** (lista das localizações do GLPI, sugerida pelo andar e lado do cadastro), requerente = o usuário, **grupo SUPORTE atribuído** (o chamado nasce "Em atendimento (atribuído)"), SLAs de atendimento e solução, incidente, sem categoria. Grupo, SLAs, modelo e prefixo ficam configuráveis na tela Integração GLPI. Endpoint novo `GET /api/chamados/locais`; `POST /api/chamados` agora exige `local_id`. Migração `e2a6c4d8b0f3`. No GLPI foi criado o perfil **SGI INTEGRAÇÃO** (cópia do TECNOLOGIA + leitura de Localizações) para a conta de serviço.
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
