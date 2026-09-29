# Changelog

Todas as mudanças relevantes do SGI SPI (antigo contratos-spi) ficam registradas aqui, da mais recente para a mais antiga.
Toda alteração é registrada aqui assim que é feita; commit e push só quando o usuário pedir (ver `AGENTS.md`, seção "Changelog e commits").

Formato de cada entrada: data, e as seções **Adicionado**, **Alterado**, **Corrigido** e **Removido**, conforme o caso.
Informe também migrações do banco e endpoints novos ou alterados.

## 2026-09-29

### Alterado
- **Folha de ponto fiel ao modelo de frequência da SPI**, conservando a estrutura do documento.
  - **Frente:** cabeçalho em caixa com o brasão, identificação em duas colunas, a tabela do mês inteira com as marcas em vermelho ("---------" na hora; SÁBADO, DOMINGO, FERIADO, PONTO FACULTATIVO, FÉRIAS na assinatura), as informações financeiras e as assinaturas.
  - **Verso:** só as anotações ("CONSOLIDAÇÃO" com as linhas pautadas, data e assinatura do superior ou do responsável).
  - Sem mudança de API.

### Adicionado
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
