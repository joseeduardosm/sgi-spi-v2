# Contratações: ETP e TR com versionamento (`/api/contratacoes`)

Tag no OpenAPI: **Contratações**. Implementação:
- rotas: `backend/app/api/routes/contratacoes.py`; schemas: `backend/app/schemas/contratacoes.py`;
- regras: `backend/app/services/contratacoes/` (`acesso`, `arvore`, `conteudo`, `versoes`, `diferencas`, `revisoes`, `conferencia`, `docx_exportacao`, `docx_importacao`, `html_blocos`);
- modelos: `backend/app/models/contratacoes.py` (`contratacoes_documentos`, `_secoes`, `_itens`, `_tabela_tr`, `_revisoes`, `_comentarios_importados`, `_membros`, `_versoes`, `_historico_itens`; migração `e5b8c3d7a921`);
- modelos de exportação: `backend/app/recursos/contratacoes/etp.docx` e `tr.docx` (os mesmos do SGI SPI antigo, 10.23.1.220);
- avisos: `app/tarefas/mensageria.py` (revisão parada há `CONTRATACOES_DIAS_AVISO` dias, no timer diário).

Migrado do módulo Contratações do SGI SPI antigo, com as melhorias abaixo. A carga dos dados está em [migracao-sgi.md](../migracao-sgi.md).

## Finalidade

Elaborar o **ETP** (Estudo Técnico Preliminar) e o **TR** (Termo de Referência): seções com itens em árvore (item, subitem, inciso, alínea, subseção) de conteúdo rico (HTML sanitizado). O marcador jurídico (`1.1.`, `1.1.1.`, `I -`, `a)`) é calculado, nunca digitado.

## Permissões

Recurso ACL `contratacoes` (atenção: recurso sem nenhuma regra fica aberto a todos; a migração cria uma regra).

| Nível / papel | O que pode |
|---|---|
| `LEITURA` | Ver os documentos em que é **criador ou membro** |
| `MODIFICACAO` | Também criar, duplicar e importar documentos |
| `CONTROLE_TOTAL` (ou SuperRoot) | Ver e administrar **todos** os documentos |
| **criador** / administração | Tudo no documento, inclusive compartilhar, vincular contrato e excluir |
| **editor** (membro) | Editar, aplicar propostas, mudar situação, restaurar versões |
| **revisor** (membro) | Ver, comentar e propor alterações (não edita nem aplica) |

Documento sem acesso responde `404` (não revela que existe); papel insuficiente, `403 sem_permissao`.

## Endpoints

| Método e caminho | Papel | Descrição |
|---|---|---|
| `GET /opcoes-usuarios?busca=` | MODIFICACAO | Usuários ativos (até 20) para escolher com quem compartilhar |
| `GET /painel` | LEITURA | Totais por situação e tipo, revisões abertas e concluídos sem vínculo com contrato |
| `GET /documentos?tipo=&situacao=&busca=&contrato_id=` | LEITURA | `ListaDocumentos` (`pode_criar`, `itens[]`) dos documentos visíveis |
| `GET /por-contrato/{contrato_id}` | LEITURA | Documentos vinculados ao contrato (aba da ficha do contrato) |
| `POST /documentos` | MODIFICACAO | `{ tipo: etp\|tr, nome, processo, link_sei }` → `201 DocumentoLeitura`; nasce a versão 1 |
| `GET /documentos/{id}` | qualquer | `DocumentoLeitura`: seções, itens em lista plana (hierarquia por `pai_id`, `marcador`), revisões, comentários importados, linhas da tabela do TR, membros e permissões |
| `PUT /documentos/{id}` | editor | Nome, processo e link |
| `DELETE /documentos/{id}` | criador | Apaga também versões e histórico (`204`) |
| `PUT /documentos/{id}/situacao` | editor | `{ situacao, confirmar }`. Concluir roda a **conferência**: bloqueio (proposta não aplicada) → `409 conferencia`; alertas exigem `confirmar = true`. Gera versão |
| `GET /documentos/{id}/conferencia` | qualquer | `{ pode_concluir, bloqueios[], alertas[] }` |
| `POST /documentos/{id}/duplicar` | MODIFICACAO | Cópia em rascunho (sem revisões, membros nem vínculo) |
| `PUT /documentos/{id}/contrato` | criador | `{ contrato_id \| null }` |
| `PUT`/`DELETE /documentos/{id}/membros/{usuario_id}` | criador | `{ papel: editor\|revisor }`; devolve os membros |
| `POST`/`PUT`/`DELETE /documentos/{id}/secoes[/{sid}]`, `PUT …/secoes/{sid}/ordem` | editor | Cria, renomeia, exclui (com os itens) e move seções |
| `POST /documentos/{id}/itens` | editor | `{ secao_id, pai_id?, tipo, conteudo?, conteudo_html?, posicao? }` (até 8 níveis; HTML sanitizado) |
| `PUT`/`DELETE /documentos/{id}/itens/{iid}` | editor | Edita (grava antes e depois no histórico) / exclui com os filhos |
| `POST …/itens/{iid}/mover`, `…/duplicar`, `…/limpar-filhos` | editor | Move com a subárvore, duplica com a subárvore, apaga só os filhos (`400` se mover para dentro de si mesmo) |
| `POST /documentos/{id}/lote/previa`, `POST …/lote` | editor | Entrada em lote (`#`..`######`, `@` subseção, `**` inciso, `$$` alínea): a **prévia** não grava; gravar cria os itens marcados "precisa de revisão" |
| `POST …/itens/{iid}/linhas-tr`, `DELETE …/linhas-tr/{lid}` | editor | Tabela estruturada do **item 1.1 do TR** (`400` fora dele) |
| `POST …/itens/{iid}/revisoes` | revisor ou mais | `{ comentario, conteudo_proposto?, conteudo_proposto_html? }`: comentário ou **proposta**; avisa o criador e os editores |
| `POST …/revisoes/{rid}/aplicar` | editor | Copia a proposta para o item e gera versão (`409` se já aplicada) |
| `POST …/revisoes/{rid}/resolver` | editor | `{ resolvida }` marca ou reabre |
| `GET /documentos/{id}/versoes` | qualquer | Lista (mais recente primeiro): número, tipo, rótulo, resumo, autor, data |
| `POST /documentos/{id}/versoes` | editor | `{ resumo }`: salva a foto atual (como o "descreva as alterações" do BookStack) |
| `GET …/versoes/{n}` | qualquer | **Visualizar**: a foto completa da versão |
| `GET …/versoes/{n}/alteracoes?contra=` | qualquer | **O que mudou** em relação à anterior (ou a `contra`): itens `incluido`, `removido`, `alterado` (diferença por palavra com `<ins>`/`<del>`) e `movido`; seções e metadados |
| `POST …/versoes/{n}/restaurar` | editor | Recria a árvore como estava (guarda antes o estado atual) e gera a versão "Restaurou a versão N" |
| `GET …/itens/{iid}/historico` | qualquer | Edições do item, com antes, depois e diferença; sobrevive à exclusão do item |
| `POST …/historico/{hid}/restaurar` | editor | `{ estado: antes\|depois }`: volta só o conteúdo daquele item (`409` se o item não existe mais) |
| `GET …/exportar/word`, `GET …/exportar/pdf` | qualquer | `.docx` sobre o modelo original e PDF |
| `POST /importar-word` | MODIFICACAO | `multipart`: `arquivo` (.docx, até 10 MB), `tipo`, `nome?`, `processo?`, `confirmar` (padrão `false`). Sem confirmar devolve só a **prévia**; com `confirmar = true` cria o documento (`documento_id`). Erros: `400 docx_invalido`/`docx_vazio`, `413 arquivo_grande` |

## Versionamento (estilo BookStack, por item)

- **Versão:** foto completa da árvore em um marco: criação, importação, mudança de situação, proposta aplicada, restauração, migração, versão salva a pedido (com resumo) e o **estado antes da primeira edição de uma sessão** (sem edição há `CONTRATACOES_SESSAO_MINUTOS`, padrão 30), de modo que o que for retirado nunca se perde. Limite `CONTRATACOES_LIMITE_VERSOES` (padrão 100): as mais antigas saem, nunca as de situação.
- **Histórico do item:** uma linha por edição (antes e depois), automática.
- **Importação do Word:** estilos `Nível 01..04` e a numeração do texto formam a hierarquia; ambiguidade vira item "precisa de revisão"; comentários do Word entram como somente leitura; arquivos com mais de 50 MB expandidos, caminhos inválidos ou macros são recusados.
