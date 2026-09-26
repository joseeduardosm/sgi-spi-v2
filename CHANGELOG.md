# Changelog

Todas as mudanças relevantes do contratos-spi ficam registradas aqui, da mais recente para a mais antiga.
Toda alteração é registrada aqui assim que é feita; commit e push só quando o usuário pedir (ver `AGENTS.md`, seção "Changelog e commits").

Formato de cada entrada: data, e as seções **Adicionado**, **Alterado**, **Corrigido** e **Removido**, conforme o caso.
Informe também migrações do banco e endpoints novos ou alterados.

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
