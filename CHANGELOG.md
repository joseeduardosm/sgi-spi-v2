# Changelog

Todas as mudanças relevantes do contratos-spi ficam registradas aqui, da mais recente para a mais antiga.
Cada commit atualiza este arquivo na mesma alteração (ver `AGENTS.md`, seção "Commits e changelog").

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
