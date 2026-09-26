# Importação de contrato por planilha XLSX (`/api/contratos/importacao-xlsx`)

Tag no OpenAPI: **Contratos: importação por XLSX**. Implementação:
- `backend/app/api/routes/contratos/importacao.py`;
- `backend/app/services/contratos/servico_importacao_xlsx.py`.

Cadastra um contrato (e, se preciso, a empresa e o preposto) a partir da planilha "Checklist de Alimentação do Sistema de Contratos". Na tela, o botão **Importar XLSX** fica na carteira (`/contratos`). O fluxo é:
1. baixar o modelo;
2. preencher;
3. enviar para a **prévia**;
4. conferir erros e avisos;
5. **confirmar**. O mesmo arquivo é enviado de novo e só então é gravado.

**Autorização (todos os endpoints desta página):**
- ACL `importacao-contratos` ≥ MODIFICACAO **e** ACL `contratos` ≥ MODIFICACAO. Sem uma delas: `403 acl_negado`.
- O recurso `importacao-contratos` é criado pela migração `d4f7b2c9e1a3` **fechado**: uma única regra, com CONTROLE_TOTAL para a conta administrativa principal.
- O SuperRoot libera os demais usuários e setores em **Controle de acesso** (`/admin/acl`) e sempre tem acesso.

---

## Formato da planilha

Modelo: `backend/app/recursos/modelo-importacao-contrato.xlsx`, disponível em `GET /modelo`. Só a primeira aba é lida.

**Cabeçalho do contrato.**
- Um campo por linha: o rótulo fica nas colunas A/B e o valor na coluna **C**.
- Nos blocos agrupados, o rótulo do grupo fica em A (célula mesclada) e o do campo em B.
- Os campos são achados **pelo rótulo** (sem acento e sem diferenciar maiúsculas). Linhas a mais ou fora de ordem não atrapalham.

| Rótulo (linha no modelo) | Campo | Conversão / regra |
|---|---|---|
| Nro do Contrato (2) | `numero` | `12/2026` ou `012/2026` → `012/2026`. Obrigatório e único |
| Empresa · CNPJ (3) | CNPJ | Com ou sem máscara; dígitos verificadores conferidos. Obrigatório |
| Empresa · Razão Social / Nome Fantasia / Endereço (4–6) | empresa | Razão social obrigatória quando a empresa é nova |
| Empresa - Preposto · Nome / CPF / E-mail / Telefone (7–10) | preposto | Opcional: bloco em branco = sem preposto. Se preenchido, nome e CPF são obrigatórios |
| Apelido (11) | `apelido` | Opcional |
| Data Inicial (12) | `data_inicio` | Célula de data ou `dd/mm/aaaa` |
| Vigência (13) / Vigência Máxima (14) | meses | Número ou texto com número (`12 meses`). A máxima não pode ser menor que a inicial |
| Periodicidade de Execução (15) | `periodicidade_meses` | Mensal, Bimestral, Trimestral, Semestral, Anual ou 1/2/3/6/12 |
| Mês de Reajuste (16) | `mes_reajuste` | Nome do mês (Março, mar) ou 1 a 12 |
| Objeto (17) | `objeto` | Obrigatório |
| Processo Gestão / Execução · Número e Link (18–21) | processos SEI | Número obrigatório; link começando com `http://` ou `https://` |
| Gestor, Fiscais e suplentes (22–27) | — | **Não importados.** Se preenchidos, geram aviso: a equipe é cadastrada depois, editando o contrato |

**Itens.**
- A tabela começa na linha com **Descrição** na coluna A. As colunas são achadas pelo título: Descrição, Tipo, Faturamento, Classe, ND, SIAFISICO (BEC), CATMAT/CATSER, QTD MENSAL, QTD NA VIGÊNCIA e VALOR UNITÁRIO.
- Entram só as linhas com descrição. As linhas de legenda do modelo (Contínuo/Sob demanda, Pró-rata/Sempre Integral) são ignoradas.

| Coluna | Regra |
|---|---|
| Tipo | `Contínuo` ou `Sob demanda` |
| Faturamento | `Pró-rata` (proporcional em mês parcial) ou `Sempre Integral` |
| Classe, ND, SIAFISICO, CATMAT/CATSER | Obrigatórios (números digitados no Excel viram texto sem `.0`) |
| QTD MENSAL | Contínuo: maior que zero. Sob demanda: estimativa (pode ficar vazia) |
| QTD NA VIGÊNCIA | Sob demanda: teto da vigência inicial, maior que zero. Contínuo: ignorada (calculada) |
| VALOR UNITÁRIO | Número do Excel ou formato brasileiro (`1.234,56`, `R$ 10,50`) |

**Empresa e preposto existentes.**
- CNPJ já cadastrado: a empresa é **reaproveitada sem alteração**. Dados diferentes na planilha viram **avisos**.
- Empresa inativa: é um **erro**; reative-a antes de importar.
- CPF já cadastrado na empresa: o preposto é reaproveitado, com aviso se o nome for diferente. Senão, é cadastrado.

---

## `POST /api/contratos/importacao-xlsx/previa`

Lê e valida a planilha **sem gravar nada**.

- **Requisição:** `multipart/form-data` com a planilha em `arquivo` (extensão `.xlsx`, até 5 MB).

### Resposta `200 OK`: `PreviaImportacao`

| Campo | Tipo | Descrição |
|---|---|---|
| `contrato` | `ContratoPrevia` | Campos lidos (`numero`, `apelido`, `objeto`, `data_inicio`, `data_fim` calculada, `vigencia_inicial_meses`, `vigencia_maxima_meses`, `periodicidade_meses`, `mes_reajuste`, `sei_*`); nulos quando vazios ou inválidos |
| `empresa` | `EmpresaPrevia` \| null | `existente`, `id` (se existente), `cnpj`, `razao_social`, `nome_fantasia`, `endereco`. Na existente, os dados são os **cadastrados** |
| `preposto` | `PrepostoPrevia` \| null | `existente`, `cpf`, `nome`, `email`, `telefone`; nulo se o bloco estiver vazio |
| `itens` | `ItemPrevia[]` | `linha`, `descricao`, `tipo`, `calcula_pro_rata`, códigos, `quantidade_mensal`, `quantidade_total` (só sob demanda), `valor_unitario` |
| `valor_global_estimado` | string decimal \| null | Contínuos: mensal × preço × vigência inicial; sob demanda: teto × preço |
| `erros` | `ErroImportacao[]` | `linha` (nula para erros do arquivo), `campo` (rótulo da planilha, ex.: `Item 2 · Classe`) e `mensagem`, em ordem de linha |
| `avisos` | string[] | Informações que não impedem a importação |
| `pode_importar` | boolean | Verdadeiro quando `erros` está vazio |

```json
{
  "contrato": { "numero": "007/2026", "data_inicio": "2026-03-01", "data_fim": "2027-02-28", "vigencia_inicial_meses": 12, "...": "..." },
  "empresa": { "existente": false, "id": null, "cnpj": "44555666000199", "razao_social": "Limpa Tudo Serviços Ltda", "nome_fantasia": "Limpa Tudo", "endereco": "Rua B, 20" },
  "preposto": { "existente": false, "cpf": "98765432100", "nome": "João Preposto", "email": "joao@limpatudo.com", "telefone": "(11) 99999-0000" },
  "itens": [ { "linha": 32, "descricao": "Limpeza diária", "tipo": "continuo", "calcula_pro_rata": true, "valor_unitario": "1000.00", "...": "..." } ],
  "valor_global_estimado": "25050.00",
  "erros": [],
  "avisos": ["A equipe de gestão e fiscalização não é importada: cadastre-a editando o contrato depois da importação."],
  "pode_importar": true
}
```

### Erros

| Código HTTP | `codigo` | Quando |
|---|---|---|
| `400` | `invalido` | Extensão diferente de `.xlsx`, arquivo vazio, acima de 5 MB ou que não é uma planilha legível |
| `401` / `403` | `nao_autenticado` / `acl_negado` | Sem token ou sem as duas liberações de ACL |

---

## `POST /api/contratos/importacao-xlsx`

Valida de novo a mesma planilha e, sem erros, grava **numa única transação**:
1. a empresa, se for nova;
2. o preposto, se for novo;
3. o contrato com os itens, **sem equipe**.

O usuário vira o criador do contrato. A auditoria registra a ação `contrato.importar_xlsx`, com o nome do arquivo.

- **Requisição:** `multipart/form-data` com a planilha em `arquivo`.
- **Resposta `201 Created`:** `DetalheContrato`, o mesmo de `GET /api/contratos/{contrato_id}` (ver [contratos-cadastro.md](contratos-cadastro.md)).

### Erros

| Código HTTP | `codigo` | Quando |
|---|---|---|
| `400` | `invalido` | Arquivo recusado (como na prévia) ou **planilha com erros**. Neste caso, o corpo traz também `erros` (mesmo formato da prévia) e nada é gravado |
| `401` / `403` | `nao_autenticado` / `acl_negado` | Sem token ou sem as duas liberações de ACL |

```json
{
  "detalhe": "A planilha tem 1 erro(s). Corrija-os e envie de novo.",
  "codigo": "invalido",
  "erros": [{ "linha": 2, "campo": "Nro do Contrato", "mensagem": "Já existe um contrato com o número 007/2026." }]
}
```

---

## `GET /api/contratos/importacao-xlsx/modelo`

Baixa a planilha modelo em branco (`modelo-importacao-contrato.xlsx`).

- **Resposta `200 OK`:** arquivo `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
