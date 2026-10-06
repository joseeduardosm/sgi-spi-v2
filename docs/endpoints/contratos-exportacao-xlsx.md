# Download de contrato, checklist e formulário de avaliação em XLSX

Tag no OpenAPI: **Contratos: exportação para XLSX**. Implementação:
- `backend/app/api/routes/contratos/exportacao.py`;
- `backend/app/services/contratos/servico_exportacao_xlsx.py` (contrato);
- `backend/app/services/contratos/servico_importacao_modelos_xlsx.py` (`exportar_checklist` e `exportar_formulario`).

É o caminho de volta da importação: a planilha sai **já preenchida**, no mesmo formato das importações
([contrato](contratos-importacao-xlsx.md) e [checklist/formulário](contratos-importacao-modelos-xlsx.md)),
então o arquivo baixado pode ser importado de novo (por exemplo, para copiar um checklist para outro contrato).

**Autorização:** ACL `contratos` ≥ LEITURA (quem vê o contrato pode baixá-lo). Sem token: `401`; sem a ACL: `403 acl_negado`.

No Angular, o botão **Baixar XLSX** fica no cabeçalho do detalhe do contrato e em cada versão das abas Checklists e Formulários.

## `GET /api/contratos/{contrato_id}/exportacao-xlsx`

Planilha do contrato (arquivo `contrato-<número>.xlsx`, com o número sem barras):
- cabeçalho: número, empresa (CNPJ, razão social, nome fantasia, endereço), apelido, data inicial, vigência, vigência máxima, periodicidade, mês de reajuste, objeto e processos SEI de gestão e execução;
- **preposto**: o primeiro ativo da empresa (o contrato não guarda um preposto próprio);
- **equipe** (gestor, fiscais e suplentes): nomes vigentes, separados por vírgula quando há mais de um; a importação ignora essas linhas;
- **itens financeiros**: descrição, tipo, faturamento, classe, ND, SIAFISICO, CATMAT/CATSER, quantidades, valor unitário e UF.

Respostas: `200` (`.xlsx`), `404 nao_encontrado` (contrato).

## `GET /api/contratos/{contrato_id}/checklists/{checklist_id}/xlsx`

Uma versão do checklist (arquivo `checklist-v<versão>-<nome>.xlsx`): aba `Checklist` com o nome e os documentos na ordem
(Obrigatório, Com validade e Vale para outros contratos em `Sim`/`Não`).

Respostas: `200` (`.xlsx`), `404 nao_encontrado` (contrato, checklist de outro contrato ou excluído).

## `GET /api/contratos/{contrato_id}/formularios/{formulario_id}/xlsx`

Uma versão do formulário de avaliação (arquivo `formulario-v<versão>-<nome>.xlsx`): abas `Formulário` (nome), `Escala`,
`Faixas` e `Itens` (o nome do grupo aparece só na primeira linha de cada grupo, como no modelo de importação).

Respostas: `200` (`.xlsx`), `404 nao_encontrado` (contrato, formulário de outro contrato ou excluído).
