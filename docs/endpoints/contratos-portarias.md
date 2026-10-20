# Contratos: portaria de designação (`/api/contratos/{contrato_id}/portarias` e `/api/portarias/autoridades`)

Tag no OpenAPI: **Contratos: portaria**. Implementação:
- rotas: `backend/app/api/routes/contratos/portarias.py`; schemas: `backend/app/schemas/contratos/portaria.py`;
- regras: `backend/app/services/contratos/servico_portaria.py`; texto e PDF de evidência: `backend/app/services/contratos/portaria_documento.py`;
- modelos: `backend/app/models/contratos/portaria.py` (`portarias_autoridades`, `contratos_portarias`, `contratos_portarias_nomeacoes`; migrações `d6f1a3c5e7b9` e `e9b3c5a7d1f2`).

## Finalidade

A portaria é o **único caminho para mudar a equipe** de gestão e fiscalização de um contrato (nem o SuperRoot a troca direto). A tela de edição do contrato não mostra mais a equipe e a API recusa (`400`, "A equipe do contrato só muda por portaria…") qualquer equipe diferente da vigente; só no **cadastro** do contrato a equipe inicial pode ser informada. Na tela, o fluxo fica na aba **Equipe** do contrato (a antiga aba "Portarias" deixou de existir; links `?aba=portaria` abrem a Equipe).

## Fluxo

`nomeacao` → `aguardando_ciencia` → `aguardando_autoridade` → `aguardando_aceite` → `aceita` → `publicada`; `cancelada` em qualquer etapa antes da publicação. **Uma portaria em andamento por contrato** (`409`).

1. **Nomeações** (`POST /portarias`): de 1 a 6 funções (gestor obrigatório; gestor suplente, fiscal técnico e seu suplente, fiscal administrativo e seu suplente), cada uma com um usuário. **A portaria define a equipe inteira**: funções sem nomeado ficam sem responsável quando ela é publicada (ela revoga a anterior). A tela já parte da equipe vigente. Cada nomeado precisa ter **RS/PV e RG/CIN** (dados do RH, restritos à CGP) e **cargo** (perfil) preenchidos; a nomeação que não tem fica com `dados_pendentes` (marcador "Dados pendentes no RH") e o **RH (CGP) é avisado** ("RH precisa atualizar os dados de X para que ele seja nomeado como [função] no contrato [nº – apelido]", evento `contratos.portaria_dados_rh`). Quando o RH salva os dados (ou o cargo é validado), a portaria avança sozinha.
2. **Ciência**: com todos os dados completos, a portaria vira `aguardando_ciencia` e cada nomeado vê o modal "Você está sendo nomeado por [quem criou] como [função] do contrato [nº – apelido]. Você está ciente?" assim que entra no sistema (`GET /portarias/ciencias`; qualquer usuário autenticado, mesmo sem acesso ao módulo). "Sim, estou ciente" (`POST /portarias/{id}/ciencia`) registra a data e a hora; "Ainda não" só adia (a nomeação continua pendente, com o marcador "Aguardando ciência do usuário"). O aviso `contratos.portaria_nomeacao` sai **também por e-mail**, mesmo para quem desligou o e-mail nas preferências (com o botão "Abrir no SGI SPI" que leva à ciência), e fica **no sino** até a ciência e seu link (`/contratos/{id}?aba=equipe&ciencia={portaria_id}`) reabre o pedido adiado. Alterar as nomeações (`PUT …/nomeacoes`) zera a ciência de quem mudou (quem continua na mesma função mantém a sua). Na tabela de nomeações da aba Equipe (colunas ordenáveis Função | Nome | Situação), a situação mostra o marcador do cadastro ("Dados completos" ou "Dados pendentes no RH: …") e o da ciência ("Ciência pendente" ou "Ciência ok · data").
3. **Autoridade** (`POST …/autoridade`): só quando **todas as nomeações estão com o cadastro completo e com a ciência de cada nomeado** (`aguardando_autoridade`; antes disso a tela nem mostra o seletor e a API responde `409`), escolhe-se a autoridade competente. **Só aqui** o texto é gerado (HTML da máscara, para **copiar**, como o despacho da última etapa da execução; não há mais minuta em Word/PDF) e o número é **reservado no Protocolo** (tipo "Portaria SPI SSGC", faixa do ano, vinculado ao contrato), ainda pendente. A tela mostra: "A portaria xx/20xx foi reservada. Os novos usuários ganharão acesso ao contrato neste sistema quando o Protocolo subir o PDF do D.O.E. no módulo do Protocolo, comprovando a sua publicação." (`aviso_reserva`).
4. **Aceite** (`POST …/aceite`) pela própria autoridade (usuário vinculado) ou SuperRoot; sem **RS**, processo SEI de gestão ou objeto, responde `400` listando o que falta. A autoridade pode **devolver** (`POST …/devolucao`): o número volta ao Protocolo, o texto some e a portaria volta a `aguardando_autoridade` (as ciências ficam; quem criou ajusta e escolhe a autoridade de novo). Ao aceitar sai o **PDF de evidência** (`GET …/evidencia`): função, nomeado e data/hora da ciência de cada um, a autoridade e a data/hora do aceite, com o rodapé "Este documento deverá ser juntado ao processo SEI como evidência…", para juntar ao SEI antes da publicação.
5. **Publicação pelo Protocolo**: quando o Protocolo **anexa o PDF do D.O.E. ao número reservado** (`POST /api/protocolo/numeros/{id}/anexo`), a portaria vira `publicada` e **a nova equipe passa a valer** (encerra as designações anteriores, abre as novas, atualiza o setor sistêmico "Equipes de contratos" e avisa os designados); o PDF entra em **Documentos Importantes** (tipo 16, a última portaria; o histórico completo fica na aba Equipe). Antes do aceite o Protocolo não anexa a esse número (`409`), e só se aceita PDF (`409`).

**Texto**: vem da **máscara** ativa cadastrada em Contratos → Modelos (veja abaixo), preenchida na escolha da autoridade e no aceite, e congelada na portaria (`dados.texto_html`). Se o contrato tem portaria anterior (publicada pelo sistema ou, na falta, um número de "Portaria" do Protocolo vinculado ao contrato), usa-se a máscara **com portaria anterior**; senão, a **sem portaria anterior**. Sem máscara ativa da variante, a escolha da autoridade responde `400`.

## Máscaras

Modelos globais do tipo `portaria` (`POST/PUT/DELETE /api/contratos/modelos`), com `variante` (`com_anterior` ou `sem_anterior`), `html` do editor rico e `ativo`. Quem edita: **SuperRoot ou controle total em Contratos**. Regras ao salvar:
- só placeholders da lista (`GET /api/contratos/modelos/portaria/placeholders`); qualquer outro `#...`, inclusive `#` solto ou `#015#`, responde `400` listando os inválidos; a máscara sem portaria anterior não aceita os placeholders da anterior;
- uma máscara ativa por variante (`409` ao ativar outra);
- parágrafo cujo placeholder de pessoa (nome ou RS) fica vazio é omitido e os incisos em romano ("I –", "II –") são renumerados; os valores são sempre escapados.

Placeholders: `#numeroportaria`, `#anoportaria`, `#numerodocontrato`, `#contratada`, `#cnpjcontratada`, `#objetodocontrato`, `#nroprocessosei`, `#nomeautoridade`, `#nomegestor`/`#rsgestor`, `#nomegestorsuplente`/`#rsgestorsuplente`, `#nomefiscal`/`#rsfiscal` (fiscal técnico ou, na falta, o administrativo), `#nomefiscaladministrativo`/`#rs…`, `#nomefiscaladministrativosuplente`/`#rs…`, `#nomefiscaltecnico`/`#rs…`, `#nomefiscaltecnicosuplente`/`#rs…` e, só com portaria anterior, `#nomedocumento` (sigla), `#numeroportariaanterior`, `#diaportariaanterior`, `#mesportariaanterior` (por extenso) e `#anoportariaanterior`. As duas máscaras iniciais vêm da migração `e7a2b4d6f8c1`.

## Permissões (recurso ACL `contratos`)

| Operação | Quem |
|---|---|
| `GET /portarias`, evidência | LEITURA |
| Criar, alterar nomeações, escolher a autoridade, cancelar | **Equipe vigente do contrato**, o **cadastrante** (quem criou o contrato) ou quem tem **CONTROLE_TOTAL** em Contratos (perfil "Administrador de Contratos") ou SuperRoot; `403 acesso_negado` para os demais. `pode_criar` no painel diz se os botões aparecem |
| Aceitar, devolver | Usuário vinculado à autoridade da portaria ou SuperRoot (`403 acesso_negado` para os demais) |
| Ciência | Só o próprio nomeado (`403` para quem não foi nomeado), sem exigir ACL |
| Publicação | Quem anexa o PDF no número do Protocolo (administração do Protocolo ou quem reservou) |
| Autoridades: criar, alterar, excluir e buscar usuários | SuperRoot, CONTROLE_TOTAL ou **gestor/gestor suplente vigente** de algum contrato (`403 acesso_negado` para os demais). `permissoes.pode_gerir_autoridades` do contrato diz se a seção aparece na aba |
| Máscaras (Modelos) | SuperRoot ou CONTROLE_TOTAL |

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /contratos/{contrato_id}/portarias` | `PainelPortarias`: `portarias` (título, `status`, `nomeacoes` com `dados_pendentes` e `ciente_em`, `texto_html`, `aviso_reserva`, `tem_evidencia`, `pendencias`, `pode_decidir`, `pode_alterar`), `autoridades` ativas, `em_andamento`, `pode_criar` e `equipe_vigente`. Também avança as portarias que esperavam dados do RH |
| `POST /contratos/{contrato_id}/portarias` | `{ nomeacoes: [{ papel, usuario_id }] }` → `201 PainelPortarias`. `400` sem gestor, função repetida ou usuário inativo; `409` se já há portaria em andamento |
| `PUT …/{portaria_id}/nomeacoes` | Troca as nomeações enquanto não há autoridade (`409` depois) |
| `POST …/{portaria_id}/autoridade` | `{ autoridade_id }`: gera o texto e reserva o número. `409` se faltar ciência; `400` sem máscara, sem faixa de "Portaria" do ano, sem processo SEI ou objeto |
| `POST …/{portaria_id}/aceite` | Aceite da autoridade; `400` com as pendências; `409` se não aguarda aceite |
| `POST …/{portaria_id}/devolucao` | `{ motivo }`: libera o número |
| `POST …/{portaria_id}/cancelamento` | `{ motivo }`: libera o número no Protocolo |
| `GET …/{portaria_id}/evidencia` | PDF de evidência (ciências e aceite); `400` antes do aceite |
| `GET /portarias/ciencias` | Nomeações do usuário logado aguardando ciência (`LeituraCienciaPendente`) |
| `POST /portarias/{portaria_id}/ciencia` | O nomeado dá ciência; devolve as que ainda restam |
| `GET /portarias/autoridades` | Todas as autoridades (ativas e desativadas) |
| `GET /portarias/autoridades/usuarios?busca=` | Usuários ativos (até 20, por nome ou login) com `cargo` e `departamento` do cadastro, para o combobox do formulário. SuperRoot, controle total ou gestor/suplente de contrato |
| `POST /portarias/autoridades`, `PUT /portarias/autoridades/{id}`, `DELETE /portarias/autoridades/{id}` | `{ sigla, usuario_id, ativa, nome?, cargo?, setor? }`: a **autoridade é um usuário do sistema** (`usuario_id` obrigatório; `422` sem ele, `400` se não existe) e é ele mesmo quem dá o aceite. `nome`, `cargo` e `setor` em branco vêm do cadastro do usuário (cargo e departamento); devolvem a lista atualizada. Excluir autoridade que já assinou: `409` (desative-a) |

Todas as escritas do contrato devolvem o painel atualizado. As portarias que estavam em andamento no fluxo antigo (aguardando aceite, devolvidas ou aceitas) foram **canceladas** pela migração `e9b3c5a7d1f2` (sem ciências); o número reservado delas, se houver, é liberado no Protocolo.
