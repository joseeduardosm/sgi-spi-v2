# Endpoints da admissão, modelos, boas-vindas e bio do RH (`/api/rh`)

Tags no OpenAPI: **Módulo RH: admissão** e **Módulo RH: minha vida funcional**. Implementação: `api/routes/rh_admissao.py`, `api/routes/rh_pessoal.py`, `services/rh/servico_admissao.py`, `servico_modelos.py`, `servico_checklists.py` e `servico_boas_vindas.py`.

Tudo de admissão, modelos e checklists exige **Controle total** no RH (dados pessoais sensíveis). As rotas "minha…" e "boas-vindas" valem para qualquer usuário autenticado, só sobre si mesmo.

## Trilha de admissão

Uma admissão por ficha de pré-cadastro. As etapas se abrem na ordem (a que está à frente devolve `409`):

| # | Etapa (`etapa`) | O que acontece |
|---|---|---|
| 1 | `chamado` | **Preenche e envia o formulário "CGP - Nomeações" (id 8) do GLPI** com os dados da ficha e os serviços marcados (rede, e-mail, SEI, Compras SP, equipamento, estação, crachá, telefone, mobiliário); o próprio formulário abre os chamados e dispara os e-mails dos seus destinos. Nenhum chamado à parte é criado. As perguntas são achadas pelo **título** (os ids não são fixos). O login proposto e o e-mail pessoal vão nas observações; `usuario_espelho` é opcional. Os links dos itens criados ficam em `chamado_links`. A **foto** da pessoa (opcional, `PUT /foto`) sobe à área temporária do GLPI (`/ajax/fileupload.php`) e vai junto no envio (pergunta "Foto") |
| 2 | `documentos` | Checklist da classificação do cargo (grupo + nível, ex.: 1.15). O envio ao **Portal de Indicações** (sistema externo) é só **registrado** aqui: data, observação e comprovante opcional. Conclui com todos os obrigatórios registrados |
| 3 | `resolucao` | Texto da resolução a partir do modelo (editável); guarda os placeholders, que entram na hora do PDF. PDF com marca d'água **MINUTA** até a publicação |
| 4 | `protocolo` | Reserva o próximo número no tipo de Resolução do Protocolo definido nos **Parâmetros do RH** (`tipo_resolucao_protocolo_id`; nome começa com "Resolu"), na faixa do ano. **Sem tipo nos Parâmetros a resolução é sem número** (veja abaixo) |
| 5 | `publicacao` | PDF do D.O.E. anexado ao número do Protocolo (pelo RH aqui, ou pelo próprio Protocolo: a publicação fica registrada nos dois casos) e data da publicação. **O e-mail "Sua nomeação foi publicada" sai sozinho** nesse momento, para o e-mail pessoal da ficha, a partir do modelo, com o PDF em anexo. Falha de e-mail nunca desfaz a publicação: o motivo fica em `email_erro` e o RH reenvia |
| 6 | `posse` | Data da posse (não anterior à publicação) e termo de posse em PDF, a partir do modelo |
| 7 | `concluida` | Exige a conta da pessoa já ligada à ficha (a TI cria o login no AD). A pessoa assume o cargo na data da posse, o ato é "Resolução SPI nº X/AAAA" e o histórico funcional registra a admissão |

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/rh/admissoes?status=&busca=` | Lista (andamento, concluida, cancelada) |
| `GET` | `/api/rh/admissoes/solicitacoes` | Serviços que o chamado pode pedir (chave → rótulo) |
| `GET` | `/api/rh/admissoes/tipos-protocolo` | Tipos de Resolução do Protocolo e se têm faixa no ano (só o tipo dos Parâmetros, se definido; `?todos=true` lista todos, para a tela de Parâmetros) |
| `POST` | `/api/rh/admissoes` | Inicia a admissão de uma ficha (`ficha_id`): exige login proposto e cargo pretendido vago (201) |
| `GET` | `/api/rh/admissoes/{id}` | Trilha completa: etapas (`feita`/`atual`/`pendente`), documentos, número, datas |
| `POST` | `/api/rh/admissoes/{id}/cancelar` | Cancela; número sem documento volta para a fila |
| `PUT` `DELETE` `GET` | `/api/rh/admissoes/{id}/foto` | Foto da pessoa (opcional): `multipart` com `arquivo` (PNG ou JPG, até 5 MB; 400 se não for imagem válida). Vai no formulário do GLPI (se ainda não enviado) e, **quando a conta da pessoa existir** (ligação da ficha com a conta, ou conclusão da admissão), vira a **foto do Diretório (intranet)**. Trocar depois do envio atualiza a intranet, mas não reenvia ao GLPI. `tem_foto` na leitura |
| `POST` | `/api/rh/admissoes/{id}/chamado` | Envia o formulário de nomeação ao GLPI (`solicitacoes`, `observacoes`, `usuario_espelho`). 502 se o GLPI estiver fora ou recusar; 503 sem integração ativa ou sem login web (ver [chamados.md](chamados.md#formulário-de-nomeações-do-rh-envio-pela-tela-web)) |
| `POST` | `/api/rh/admissoes/{id}/documentos/{doc_id}` | Registra o envio (`multipart`: `enviado_em`, `observacao`, `comprovante`) |
| `DELETE` | `/api/rh/admissoes/{id}/documentos/{doc_id}` | Desfaz o registro (até concluir a etapa) |
| `GET` | `/api/rh/admissoes/{id}/documentos/{doc_id}/comprovante` | Baixa o comprovante |
| `POST` | `/api/rh/admissoes/{id}/documentos/concluir` | Conclui a etapa de documentos |
| `POST` | `/api/rh/admissoes/{id}/documentos/incluir` | Inclui documento fora do checklist do cargo (`multipart`: `nome`, `descricao`, `arquivo` PDF). Nunca obrigatório; `409` com a etapa fechada, `400` sem nome |
| `DELETE` | `/api/rh/admissoes/{id}/documentos/{doc_id}/incluido` | Exclui um documento incluído (só eles; `400` nos do checklist; `409` com a etapa concluída) |
| `GET` | `/api/rh/admissoes/{id}/documentos/{doc_id}/arquivo` | Baixa o arquivo do documento incluído |
| `POST` `PUT` | `/api/rh/admissoes/{id}/resolucao` | Gera o texto do modelo / grava o texto editado (`html`) |
| `GET` | `/api/rh/admissoes/{id}/resolucao.pdf` | PDF (MINUTA até a publicação) |
| `GET` | `/api/rh/admissoes/{id}/resolucao/copia` | Texto da resolução com os placeholders já trocados, em `html` (formatado) e `texto` (simples), para colar no SEI |
| `POST` | `/api/rh/admissoes/{id}/protocolo` | Reserva o número do tipo dos Parâmetros (`tipo_protocolo_id` só vale se os Parâmetros não definirem um); `409` se a admissão é de resolução sem número |
| `POST` | `/api/rh/admissoes/{id}/protocolo/liberar` | `{ motivo }` (obrigatório): devolve o número ao Protocolo **mesmo com o PDF da publicação já subido** (o PDF é excluído logicamente, a publicação deixa de estar registrada e a trilha volta à etapa do número). Quem reservou o número, o Serviço de Apoio Administrativo (parâmetro do RH) e o SuperRoot; `403 sem_permissao` nos demais; `409` sem número ou depois da posse. O e-mail de nomeação já enviado não é desfeito |
| `POST` `PUT` | `/api/rh/admissoes/{id}/publicacao` | Anexa o PDF do D.O.E. (`multipart`: `arquivo`, `publicado_em`) / ajusta a data |
| `GET` | `/api/rh/admissoes/{id}/publicacao.pdf` | Baixa o PDF da publicação |
| `POST` | `/api/rh/admissoes/{id}/email` | **Reenvia** o e-mail de nomeação quando o envio automático falhou (`email_erro`); 400 se falhar de novo, 409 se já foi enviado |
| `POST` | `/api/rh/admissoes/{id}/posse` | Registra a posse (`posse_em`) |
| `PUT` | `/api/rh/admissoes/{id}/termo` | Edita o texto do termo |
| `GET` | `/api/rh/admissoes/{id}/termo.pdf` | PDF do termo de posse |
| `POST` | `/api/rh/admissoes/{id}/concluir` | Conclui e dá posse no cargo |

Erros no formato `{"detalhe", "codigo"}`: 400 `invalido`, 404 `nao_encontrado`, 409 `conflito`.

## Modelos (RH > Modelos)

Quatro textos editáveis, cada um com texto padrão criado na primeira consulta: `resolucao_nomeacao`, `email_nomeacao_publicada` (com assunto), `termo_posse` e `boas_vindas`.

Os textos são HTML do editor rico com **placeholders de lista fechada** (`GET /api/rh/modelos/placeholders`): `#nome`, `#login`, `#cpf`, `#rg`, `#rs`, `#cargo`, `#denominacao`, `#classificacao`, `#nivel` (grupo.nível do cargo, ex.: `2.16`), `#setor`, `#siglasetor`, `#datainicio`, `#dataposse`, `#numeroresolucao`, `#anoresolucao`, `#datapublicacao`, `#hoje`, `#linksistema`. Qualquer outro `#` barra o salvamento (400). Valor ausente sai como `—`; os valores são escapados.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/rh/modelos` | Lista os modelos |
| `PUT` | `/api/rh/modelos/{tipo}` | Salva (`assunto`, `html`) |
| `POST` | `/api/rh/modelos/{tipo}/restaurar` | Volta ao texto padrão |

## Checklists de documentos

Cada checklist vale para uma ou várias **classificações de cargo**: grupo (1 ou 2) + nível (1 a 18), por exemplo 1.15, 1.16 e 1.17 (`classificacoes: [{grupo, nivel}]`). `aplica_a_outros = true` faz o checklist valer também para os cargos sem classificação (tipo OUTRO). É preciso marcar ao menos uma classificação ou "outros" (400 caso contrário); grupo fora de 1 e 2 ou nível fora de 1 a 18 dão 422.

Ao iniciar a admissão, os itens dos checklists ativos que valem para a classificação do cargo são **copiados** para ela, sem repetir descrição (excluir ou alterar o checklist depois não muda admissões em andamento).

| Método | Rota | Descrição |
|---|---|---|
| `GET` `POST` | `/api/rh/checklists` | Lista / cria (201) |
| `PUT` `DELETE` | `/api/rh/checklists/{id}` | Altera / exclui (204) |


**Checklist "a partir de…":** o checklist do cargo é o ponto de partida da admissão. Com a etapa de documentos aberta, o RH inclui documentos que não estavam nele (nome, descrição e PDF): o incluído vale só para aquela admissão (`incluido_no_processo`, `detalhe`, `tem_arquivo`, `incluido_por_nome`, `incluido_em` em `documentos[]`), **nunca é obrigatório**, pode ser excluído até a etapa ser concluída e não muda o checklist. O arquivo dele é separado do comprovante de envio ao Portal de Indicações (que continua sendo registrado pelo botão de envio). Auditoria `rh.admissao.documento.incluir` e `.excluir`. Migração `b8d2f4a6c9e1`.

## Boas-vindas, bio e ficha da própria pessoa

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/rh/boas-vindas` | `pendente = true` só no primeiro acesso de contas do AD (quem já usava o sistema antes foi marcado como "já viu"). Traz o texto do modelo preenchido; na primeira consulta envia o mesmo texto por e-mail, uma única vez. **Não exige o perfil em dia** |
| `POST` | `/api/rh/boas-vindas/confirmar` | Marca como vistas (204). A tela segue para o cadastro (perfil) |
| `GET` `PUT` | `/api/rh/minha-bio` | Bio opcional (até 3000 caracteres). `bio_visivel = true` libera a bio na busca de usuários e no cartão de contato (`bio` em `GET /api/diretorio/ramais/{id}`); sem texto, fica oculta |
| `GET` `PUT` | `/api/rh/minha-ficha` | Ficha cadastral da própria pessoa (legados). Cada envio zera a validação |
| `POST` | `/api/rh/pre-cadastros/{id}/validar` | O RH confere e valida a ficha enviada (409 se não foi enviada). `GET /api/rh/pre-cadastros?pendentes_de_validacao=true` lista as pendentes |

A busca de usuários (`GET /api/usuarios?busca=`) passa a procurar também na bio liberada, para todos.


## Resolução sem número (Parâmetros do RH)

`GET`/`PUT /api/rh/parametros` trazem `tipo_resolucao_protocolo_id` (migração `e8f4a0b6c2d5`): o tipo de documento do Protocolo que a resolução de nomeação consome (só tipos "Resolu…"; `400` para outro). **Em branco, a resolução é sem número.**

- A escolha é gravada na admissão ao iniciá-la (`sem_numero` em `LeituraAdmissao`); mudar o parâmetro vale só para as admissões iniciadas depois. As já em andamento seguem como estavam.
- Sem número: ao gerar o texto da resolução, a etapa `protocolo` é dada como feita sozinha e a trilha vai direto à `publicacao`; `numero_protocolo` fica nulo e os placeholders `#numeroresolucao`/`#anoresolucao` saem vazios; `POST /admissoes/{id}/protocolo` responde `409`.
- A publicação (`POST /admissoes/{id}/publicacao`, só PDF) guarda o PDF do D.O.E. na própria admissão (`publicacao_anexo_id`), registra a publicação e envia o e-mail de nomeação com o PDF; `GET /publicacao.pdf` baixa esse arquivo.
