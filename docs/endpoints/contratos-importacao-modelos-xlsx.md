# Importação de checklists e formulários de avaliação por XLSX

Tag no OpenAPI: **Contratos: importação de modelos por XLSX**. Implementação:
- `backend/app/api/routes/contratos/importacao_modelos.py`;
- `backend/app/services/contratos/servico_importacao_modelos_xlsx.py`.

Cria checklists e formulários de avaliação da qualidade a partir de planilhas, em dois destinos:
- **no contrato** (abas Checklists e Formulários do detalhe do contrato): cria uma **versão inativa**; é preciso ativá-la depois, como no cadastro manual;
- **modelos globais** (tela `/contratos/modelos`): cria um modelo global.

Fluxo, igual ao da [importação de contratos](contratos-importacao-xlsx.md):
1. baixar o modelo;
2. preencher;
3. enviar para a **prévia** (nada é gravado);
4. conferir erros e avisos;
5. **confirmar**: o mesmo arquivo é enviado de novo, validado outra vez e só então gravado.

**Autorização:**
- ACL `importacao-modelos` ≥ MODIFICACAO **e** ACL `contratos` ≥ MODIFICACAO. Sem uma delas: `403 acl_negado`.
- No contrato, vale também o vínculo exigido para editá-lo (criador, equipe de gestão e fiscalização ou SuperRoot): `403 acesso_negado`.
- Nos modelos globais, só o SuperRoot (`403 acesso_negado`).
- O recurso `importacao-modelos` é criado pela migração `e5a8c3d7f2b1` **fechado** (CONTROLE_TOTAL só para a conta administrativa principal); o SuperRoot libera os demais em `/admin/acl`.

---

## Formato das planilhas

O modelo é gerado pela API, com um exemplo preenchido. Abas e colunas são achadas pelo título (sem acento e sem diferenciar maiúsculas), então linhas a mais ou colunas fora de ordem não atrapalham.

### Checklist (aba `Checklist`)

- O nome fica na célula à direita de **Nome do checklist**.
- A tabela começa na linha com o título **Documento**.

| Coluna | Regra |
|---|---|
| Documento | Obrigatório, até 500 caracteres |
| Observação | Opcional, até 1000 caracteres |
| Obrigatório | `Sim` ou `Não`; em branco = Sim |
| Com validade | `Sim` ou `Não`; em branco = Não |

Pelo menos um documento. A ordem das linhas é a ordem do checklist.

### Formulário de avaliação (abas `Formulário`, `Escala`, `Faixas` e `Itens`)

- **Formulário:** o nome fica à direita de **Nome do formulário**.
- **Escala:** colunas `Nota` (número) e `Legenda`. Mínimo de duas notas, em ordem crescente e sem repetição.
- **Faixas:** colunas `Mínimo`, `Máximo` (em branco = sem teto), `Percentual liberado` (0 a 100) e `Notas zero` (opcional, inteiro).
- **Itens:** colunas `Grupo`, `Item`, `Descrição` (opcional) e `Peso`. Grupo em branco repete o da linha de cima. Os pesos de cada grupo somam exatamente 100.

Números aceitam o formato brasileiro (`7,5`, `1.234,56`); células numéricas do Excel são arredondadas para 2 casas. As regras de negócio são as mesmas do cadastro manual (`POST /api/contratos/{contrato_id}/checklists` e `/formularios`).

---

## Endpoints

Erros comuns: `400 invalido` para arquivo vazio, acima de 5 MB ou que não é `.xlsx`; `401`; `403`.

### No contrato — `recurso` é `checklists` ou `formularios`

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/api/contratos/{contrato_id}/{recurso}/importacao-xlsx/modelo` | Planilha modelo (`modelo-importacao-checklist.xlsx` ou `…-formulario.xlsx`) |
| `POST` | `/api/contratos/{contrato_id}/{recurso}/importacao-xlsx/previa` | Prévia (`multipart/form-data`, campo `arquivo`); `404` se o contrato não existir |
| `POST` | `/api/contratos/{contrato_id}/checklists/importacao-xlsx` | Cria a versão inativa do checklist; `201` com a lista de versões (`LeituraChecklist[]`) |
| `POST` | `/api/contratos/{contrato_id}/formularios/importacao-xlsx` | Cria a versão inativa do formulário; `201` com `LeituraFormulario[]` |

### Modelos globais — `tipo` é `checklist` ou `formulario` (SuperRoot)

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/api/contratos/modelos/importacao-xlsx/{tipo}/modelo` | Planilha modelo |
| `POST` | `/api/contratos/modelos/importacao-xlsx/{tipo}/previa` | Prévia |
| `POST` | `/api/contratos/modelos/importacao-xlsx/{tipo}` | Cria o modelo global; `201` com `LeituraModelo` |

### Prévia (`PreviaImportacaoModelo`)

| Campo | Descrição |
|---|---|
| `tipo`, `nome` | Tipo e nome lidos |
| `documentos[]` | Checklist: `linha`, `nome`, `observacao`, `obrigatorio`, `com_validade` |
| `escala[]`, `faixas[]`, `grupos[]` | Formulário: o que foi lido, com a `linha` de cada nota, faixa e item |
| `erros[]` | `linha` (nulo para erro do arquivo), `campo` e `mensagem`; impedem a importação |
| `avisos[]` | Só informam |
| `pode_importar` | Verdadeiro quando não há erros |

Na importação com erros na planilha, a resposta é `400 invalido` com o mesmo `erros[]` no corpo, e nada é gravado.

**Auditoria:** `contrato.checklist.importar_xlsx`, `contrato.formulario.importar_xlsx` e `contrato.modelo.importar_xlsx`, além do registro normal de criação.
