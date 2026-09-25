# Endpoints do contrato (`/api/contratos`)

Tag no OpenAPI: **Contratos**. Implementação: `backend/app/api/routes/contratos/contratos.py`, `backend/app/services/contratos/servico_contratos.py` e os cálculos em `backend/app/services/contratos/calculos.py`.

## Finalidade

Carteira de contratos, cadastro e edição (dados, processos SEI, equipe e itens financeiros), detalhe com vigências e saldos, documentos importantes e histórico de alterações por campo.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `contratos` ≥ `LEITURA`.
  - **Cadastro:** ACL `contratos` ≥ `MODIFICACAO`. Quem cadastra vira o **criador**.
  - **Alteração e anexos (pode editar):** ACL ≥ `MODIFICACAO` **e** ser SuperRoot, o criador ou integrante **vigente** da equipe. Sem esse vínculo: `403 acesso_negado`. Os seis papéis da equipe têm os mesmos poderes.
  - **Exclusão:** ACL `contratos` = `CONTROLE_TOTAL`.
- **Número:** `NNN/AAAA`, único. `GET /proximo-numero` sugere o maior sequencial do ano + 1.
- **Datas:** `data_fim` = `data_inicio` + vigência inicial − 1 dia (ex.: 01/01/2026 + 12 meses = 31/12/2026). Depois de uma prorrogação, a data inicial e a vigência inicial ficam bloqueadas.
- **Vigência máxima** ≥ vigência inicial e ≥ soma das vigências já registradas.
- **Situação** (calculada, não gravada): `encerrado` depois do fim da vigência atual; `a_vencer` a até 90 dias do fim; senão `ativo`. `situacao_forcada` (ex.: `suspenso`) prevalece.
- **Valores** (calculados, não gravados):
  - `subtotal_mensal` do item = quantidade mensal × valor unitário;
  - `base_mensal` = soma dos subtotais dos itens **contínuos**;
  - `valor_global` = valor da **vigência atual**, somado **mês a mês**: contínuos = quantidade do mês × preço do mês × fator 30/360 (quando o item calcula pró-rata); sob demanda = apontamentos × preço do mês + limite ainda não apontado × preço do último mês. Assim, reajustes e aditamentos/supressões só alteram os meses a partir do seu efeito.
- **Itens:**
  - contínuo exige `quantidade_mensal > 0`; sob demanda exige `quantidade_total > 0`;
  - os quatro códigos orçamentários (classe, ND, SIAFÍSICO e CATMAT/CATSER) são obrigatórios;
  - um item salvo **não muda** `descricao`, `tipo` nem `calcula_pro_rata` (exclua e crie outro);
  - item com quantidade executada não pode ser excluído;
  - a ordem da lista enviada é a ordem dos itens;
  - depois de geradas as competências de execução, só o SuperRoot altera itens e ordem.
- **Equipe:** um usuário ativo por papel (`gestor`, `gestor_suplente`, `fiscal_administrativo`, `fiscal_administrativo_suplente`, `fiscal_tecnico`, `fiscal_tecnico_suplente`). Trocar o designado encerra a designação anterior, que fica no histórico.
- **Concorrência:** o `PUT` exige a `versao` lida no detalhe. Se outra pessoa salvou antes: `409 conflito`.
- **Valores decimais** são enviados e recebidos como **texto** (`"1234.50"`): dinheiro com 2 casas e quantidades com 4.
- **Auditoria:** `contrato.criar`, `contrato.alterar` (campos "de → para"), `contrato.equipe.alterar`, `contrato.itens.alterar`, `contrato.documento.enviar` e `contrato.excluir`, com `alvo_tipo = contrato`.

## Schemas

### `GravacaoContrato` (requisição)

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `numero` | string | sim | `NNN/AAAA` (aceita `1/2026`); único |
| `empresa_id` | uuid | sim | Empresa ativa (um contrato existente pode manter uma empresa já inativada) |
| `apelido` | string | não | Até 200 |
| `objeto` | string | sim | 1 a 4000 |
| `data_inicio` | date | sim | |
| `vigencia_inicial_meses` | integer | sim | 1 a 600 |
| `vigencia_maxima_meses` | integer | sim | ≥ vigência inicial |
| `periodicidade_meses` | integer | sim | 1, 2, 3, 6 ou 12 |
| `mes_reajuste` | integer | sim | 1 a 12 |
| `sei_gestao_numero`, `sei_execucao_numero` | string | sim | Até 100 |
| `sei_gestao_link`, `sei_execucao_link` | string | sim | `http(s)://…`, até 1000 |
| `situacao_forcada` | string \| null | não | `ativo`, `a_vencer`, `encerrado`, `suspenso` |
| `equipe` | `GravacaoEquipe` | não | Um id de usuário (ou nulo) por papel |
| `itens` | `GravacaoItem[]` | não | Lista completa, na ordem de exibição |
| `versao` | integer | no `PUT` | Versão lida no detalhe |

`GravacaoItem`: `id` (nulo = novo), `descricao` (1 a 1000), `tipo` (`continuo`/`sob_demanda`), `calcula_pro_rata` (`true` = com pró-rata, `false` = sempre integral), `codigo_classe`, `codigo_natureza_despesa`, `codigo_siafisico`, `codigo_catmat_catser` (obrigatórios, até 80), `quantidade_mensal`, `quantidade_total` (até 4 casas), `valor_unitario` (2 casas).

### Respostas

- `ResumoContrato`: `id`, `numero`, `apelido`, `empresa_razao_social`, `objeto`, `data_inicio`, `data_fim`, `situacao`, `base_mensal`, `valor_global`.
- `PaginaContratos`: `itens`, `total`, `pagina`, `tamanho_pagina`.
- `DetalheContrato` = `ResumoContrato` +
  - `sequencial`, `ano` e `empresa` (`OpcaoEmpresa`);
  - `data_fim_prazo_inicial`, `data_limite_maxima`, `vigencia_inicial_meses`, `vigencia_maxima_meses`, `periodicidade_meses`, `mes_reajuste`;
  - os quatro campos SEI e `situacao_forcada`;
  - `vigencias` (`[{sequencia, inicio, fim, meses}]`);
  - `itens` (`LeituraItem`: dados do item + `quantidade_total` da vigência atual, `quantidade_original` (teto inicial do item sob demanda), `quantidade_executada`, `quantidade_disponivel`, `subtotal_mensal`, `vigencia_meses`);
  - `equipe` (`[{papel, usuario_id, nome, login, desde}]`, só as designações vigentes);
  - `criador_nome`, `permissoes` (`{pode_editar, pode_excluir}`), `versao`, `criado_em`, `atualizado_em`.
- `LeituraDocumento`: `codigo`, `numero` (`"012"`), `titulo`, `anexado`, `nome_arquivo`, `tamanho`, `enviado_em`, `enviado_por_nome`.
- `AlteracaoCampo`: `campo`, `de`, `para`, `autor`, `ocorrido_em`.

---

## `GET /api/contratos`

`PaginaContratos`, com os mais recentes primeiro. Parâmetros: `busca` (número `012/2026`, empresa, apelido ou objeto), `pagina` e `tamanho_pagina` (padrão 25, máximo 100).

## `GET /api/contratos/proximo-numero?ano=2026`

```json
{ "numero": "013/2026", "sequencial": 13, "ano": 2026 }
```

## `GET /api/contratos/opcoes-usuarios`

`OpcaoUsuario[]` com os usuários ativos do portal, para os papéis da equipe. Parâmetros `busca` e `limite` (padrão 20). Exige ACL `contratos` ≥ `MODIFICACAO`. Não exige acesso ao módulo Usuários.

## `GET /api/contratos/{contrato_id}`

`DetalheContrato`. `404 nao_encontrado`.

## `POST /api/contratos`

Resposta **`201`**: `DetalheContrato`.

```json
{
  "numero": "013/2026",
  "empresa_id": "5d1c…",
  "apelido": "Limpeza sede",
  "objeto": "Serviços contínuos de limpeza predial",
  "data_inicio": "2026-01-01",
  "vigencia_inicial_meses": 12,
  "vigencia_maxima_meses": 60,
  "periodicidade_meses": 1,
  "mes_reajuste": 1,
  "sei_gestao_numero": "SPI-PRC-2026/00001",
  "sei_gestao_link": "https://sei.sp.gov.br/…",
  "sei_execucao_numero": "SPI-PRC-2026/00002",
  "sei_execucao_link": "https://sei.sp.gov.br/…",
  "equipe": { "gestor": 12, "fiscal_tecnico": 31 },
  "itens": [
    { "descricao": "Posto de limpeza", "tipo": "continuo", "calcula_pro_rata": true, "codigo_classe": "01",
      "codigo_natureza_despesa": "339039", "codigo_siafisico": "123", "codigo_catmat_catser": "456",
      "quantidade_mensal": "2", "valor_unitario": "1000.00" }
  ]
}
```

Erros: `409 conflito` (número já usado); `400 invalido` (empresa inativa ou inexistente, usuário da equipe inexistente ou inativo); `422` (formato, vigências, quantidades do item).

## `PUT /api/contratos/{contrato_id}`

Mesmo corpo, com `versao` e o `id` de cada item existente. Resposta `200`: `DetalheContrato` com a nova `versao`. Erros:
- `404`;
- `403 acesso_negado`: sem vínculo com o contrato;
- `409 conflito`: número já usado, ou `O contrato foi alterado por outra pessoa depois que você o abriu…`;
- `400 invalido`: item mudou nome, tipo ou faturamento; item com execução excluído; datas bloqueadas pela prorrogação; itens bloqueados pela execução;
- `422`.

## `DELETE /api/contratos/{contrato_id}`

Resposta **`204`**. Remove o contrato e seus dependentes; **todos** os PDFs e arquivos gerados ligados ao contrato (documentos, execução, reajuste, prorrogação, alterações) passam a excluídos (exclusão lógica). Erro: `404`.

## `GET /api/contratos/{contrato_id}/historico`

`AlteracaoCampo[]`, do mais recente para o mais antigo. A tela filtra por `campo` para montar o ícone de histórico de cada campo. Os campos de equipe aparecem como `equipe.<papel>`, com os nomes.

## `GET /api/contratos/{contrato_id}/documentos`

`LeituraDocumento[]`: os 23 tipos do catálogo (001 DFD … 023 Termos de Recebimento), anexados ou não, e os termos aditivos de prorrogação (024 em diante). A aba é só um repositório: nenhuma etapa depende dela.

## `POST /api/contratos/{contrato_id}/documentos/{codigo}`

`multipart/form-data` com o PDF no campo `arquivo`. Aceita os códigos 1 a 23 e substitui o anexo anterior. Resposta `200`: `LeituraDocumento[]` atualizada. Erros:
- `400 invalido`: arquivo recusado (não é PDF, vazio, acima do limite) ou código fora do catálogo;
- `403`;
- `404`.

## `GET /api/contratos/{contrato_id}/documentos/{codigo}/arquivo`

O PDF, com o nome `PREFIXO_SPI_NNN_AAAA.pdf` (ex.: `CONTRATO_ASSINADO_SPI_012_2026.pdf`). `404` se não houver anexo.

## Consumo no Angular

- Serviço: `ContratosApiService` (`frontend/src/app/features/contratos/compartilhado/contratos-api.service.ts`).
- Telas: `/contratos` (carteira), `/contratos/novo` e `/contratos/:id/editar` (cadastro), e `/contratos/:id` (detalhe com abas).
