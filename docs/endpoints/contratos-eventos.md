# Eventos do contrato (`/api/contratos/{contrato_id}/eventos`)

Tag no OpenAPI: **Contratos**. Implementação: `backend/app/api/routes/contratos/contratos.py`, `backend/app/services/contratos/servico_eventos.py` e `eventos_catalogo.py`.

A aba **Eventos** do contrato mostra tudo o que a auditoria registrou sobre ele (`auditoria.alvo_tipo = 'contrato'`), com nome em linguagem de usuário, categoria e, nas conclusões que podem ser desfeitas, o botão "Tornar sem efeito". Decisão do usuário (13/11/2026): só para quem tem **Controle total** em Contratos.

---

## `GET /api/contratos/{contrato_id}/eventos`

- **Autorização:** ACL `contratos` = CONTROLE_TOTAL (ou SuperRoot). Sem ela, `403`.

### Parâmetros (query)

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `categoria` | `altera_contrato` \| `execucao` \| `documentos` \| `equipe_cadastro` \| `sem_efeito` | nenhum (todas) | Chip escolhido |
| `busca` | string (até 200) | `""` | Procura sem acento e sem diferença de maiúsculas no nome do evento, no autor, no detalhe e no conteúdo gravado |
| `ordem` | `ocorrido_em` \| `evento` \| `autor` \| `detalhe` | `ocorrido_em` | Coluna da ordenação |
| `sentido` | `asc` \| `desc` | `desc` | Mais recentes primeiro, por padrão |
| `pagina` | integer ≥ 1 | 1 | Página |
| `por_pagina` | 1 a 200 | 50 | Tamanho da página |

### Resposta `200 OK`: `PaginaEventosContrato`

| Campo | Tipo | Descrição |
|---|---|---|
| `itens` | `EventoContrato[]` | A página |
| `total` | integer | Total com o filtro e a busca |
| `pagina`, `por_pagina` | integer | Página atual e tamanho |
| `por_categoria` | objeto | Quantos eventos há em cada categoria com a busca atual (números dos chips) |

`EventoContrato`:

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | integer | Número do registro de auditoria |
| `ocorrido_em` | date-time | Quando |
| `acao` | string | Ação técnica (ex.: `contrato.reajuste.concluir`) |
| `evento` | string | Nome em linguagem de usuário (ex.: "Reajuste concluído") |
| `categoria` | string | Uma das categorias acima |
| `autor` | string | Nome completo de quem fez (ou o login) |
| `detalhe` | string | Motivo, campos de → para, justificativa ou a descrição gravada |
| `registro_tipo`, `registro_id` | string \| null | Nas conclusões de reajuste, repactuação, aditamento/supressão, prorrogação e vigência retroativa: o registro para `POST …/{registro_tipo}/{registro_id}/sem-efeito` |
| `sem_efeito` | boolean | O registro desta conclusão já foi tornado sem efeito |
| `pode_tornar_sem_efeito` | boolean | O botão fica ativo |
| `motivo_bloqueio` | string | Por que o botão fica desativado |

### Categorias

- **Alteram o contrato** (`altera_contrato`): cadastro e alteração do contrato e dos itens, importação, prorrogação, vigência retroativa, reajuste, repactuação, aditamento, supressão, correção de itens, portaria e o que não se encaixa nas demais.
- **Execução** (`execucao`): geração das competências, medição, ciências, avaliação, nota fiscal, retenção, CADIN, checklist, consolidado, OB, reabrir, zerar, créditos e medição adicional.
- **Documentos** (`documentos`): documentos importantes, checklists, formulários e diário de bordo.
- **Equipe e cadastro** (`equipe_cadastro`): equipe, empresa, preposto, notas de empenho, previsão orçamentária, processo financeiro e rascunhos.
- **Sem efeito** (`sem_efeito`): `*.sem_efeito`, `contrato.prorrogacao.desfazer` e `contrato.vigencia_retroativa.desfazer`.

As conclusões gravam `registro_id` na auditoria a partir desta versão; nos registros antigos, o registro é achado pela data da conclusão (gravada na mesma transação, tolerância de 10 segundos).

### Outras respostas

`403` sem Controle total; `404` contrato inexistente; `422` parâmetro inválido.
