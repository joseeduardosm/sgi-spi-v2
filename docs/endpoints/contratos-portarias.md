# Contratos: portaria de designação (`/api/contratos/{contrato_id}/portarias` e `/api/portarias/autoridades`)

Tag no OpenAPI: **Contratos: portaria**. Implementação:
- rotas: `backend/app/api/routes/contratos/portarias.py`; schemas: `backend/app/schemas/contratos/portaria.py`;
- regras: `backend/app/services/contratos/servico_portaria.py`; texto e exportação: `backend/app/services/contratos/portaria_documento.py` (modelo institucional em `backend/app/recursos/portarias/portaria.docx`);
- modelos: `backend/app/models/contratos/portaria.py` (`portarias_autoridades`, `contratos_portarias`; migração `d6f1a3c5e7b9`).

## Finalidade

Gera a portaria que designa gestor e fiscais do contrato a partir da equipe vigente e dos dados do contrato. O número é **reservado no Protocolo** (tipo "Portaria", faixa do ano corrente) e vinculado ao contrato. Na tela, é a aba **Portarias**, depois de "Execução".

## Fluxo

`aguardando_aceite` → `aceita` → `publicada`; a autoridade pode **devolver** (`devolvida`, o solicitante ajusta e **reenvia**); `cancelada` libera o número no Protocolo. **Uma portaria em andamento por contrato** (`409`).

1. **Solicitar** escolhendo a autoridade (cargo, setor e nome vêm do cadastro). Reserva o próximo número, congela o texto e avisa o usuário vinculado à autoridade.
2. **Aceite** pela própria autoridade (usuário vinculado) ou SuperRoot. O texto é refeito com a equipe e o RS atuais; sem **RS** (lido do RH, nunca exposto), processo SEI de gestão ou objeto, responde `400` listando o que falta.
3. **Minuta** em Word ou PDF com a marca d'água "MINUTA", antes e depois do aceite, para postar no SEI e no DOE.
4. **Publicação**: o PDF publicado é enviado com a portaria aceita; fica anexado ao número do Protocolo (que passa a `utilizado`) e em **Documentos Importantes** (tipo 16).

**Texto**: vem da **máscara** ativa cadastrada em Contratos → Modelos (veja abaixo), preenchida na solicitação, no reenvio e no aceite, e congelada na portaria (`dados.texto_html`). Se o contrato tem portaria anterior (aceita/publicada pelo sistema ou, na falta, um número de "Portaria" do Protocolo vinculado ao contrato), usa-se a máscara **com portaria anterior**; senão, a **sem portaria anterior**. Sem máscara ativa da variante, a solicitação responde `400`.

## Máscaras

Modelos globais do tipo `portaria` (`POST/PUT/DELETE /api/contratos/modelos`), com `variante` (`com_anterior` ou `sem_anterior`), `html` do editor rico e `ativo`. Quem edita: **SuperRoot ou controle total em Contratos**. Regras ao salvar:
- só placeholders da lista (`GET /api/contratos/modelos/portaria/placeholders`); qualquer outro `#...`, inclusive `#` solto ou `#015#`, responde `400` listando os inválidos; a máscara sem portaria anterior não aceita os placeholders da anterior;
- uma máscara ativa por variante (`409` ao ativar outra);
- parágrafo cujo placeholder de pessoa (nome ou RS) fica vazio é omitido e os incisos em romano ("I –", "II –") são renumerados; os valores são sempre escapados.

Placeholders: `#numeroportaria`, `#anoportaria`, `#numerodocontrato`, `#contratada`, `#cnpjcontratada`, `#objetodocontrato`, `#nroprocessosei`, `#nomeautoridade`, `#nomegestor`/`#rsgestor`, `#nomegestorsuplente`/`#rsgestorsuplente`, `#nomefiscal`/`#rsfiscal` (fiscal técnico ou, na falta, o administrativo), `#nomefiscaladministrativo`/`#rs…`, `#nomefiscaladministrativosuplente`/`#rs…`, `#nomefiscaltecnico`/`#rs…`, `#nomefiscaltecnicosuplente`/`#rs…` e, só com portaria anterior, `#nomedocumento` (sigla), `#numeroportariaanterior`, `#diaportariaanterior`, `#mesportariaanterior` (por extenso) e `#anoportariaanterior`. As duas máscaras iniciais vêm da migração `e7a2b4d6f8c1`.

## Permissões (recurso ACL `contratos`)

| Operação | Quem |
|---|---|
| `GET /portarias`, minuta | LEITURA |
| Solicitar, reenviar, cancelar, publicar | pode editar o contrato (ACL ≥ MODIFICACAO e ser SuperRoot, criador ou da equipe); `403 acesso_negado` sem vínculo |
| Aceitar, devolver | Usuário vinculado à autoridade da portaria ou SuperRoot (`403 acesso_negado` para os demais) |
| Autoridades: criar, alterar, excluir | CONTROLE_TOTAL |
| Máscaras (Modelos) | SuperRoot ou CONTROLE_TOTAL |

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /contratos/{contrato_id}/portarias` | `PainelPortarias`: `portarias` (com título, status, portaria anterior citada, equipe sem RS, `pendencias`, `pode_decidir`, `pode_alterar`), `autoridades` ativas e `em_andamento` |
| `POST /contratos/{contrato_id}/portarias` | `{ autoridade_id }` → `201 PainelPortarias`. `400` sem gestor ou sem faixa de "Portaria" do ano no Protocolo; `409` se já há portaria em andamento ou sem números livres |
| `POST …/{portaria_id}/reenviar` | Refaz o texto e volta para o aceite (portaria devolvida ou aguardando) |
| `POST …/{portaria_id}/aceite` | Aceite da autoridade; `400` com as pendências; `409` se não aguarda aceite |
| `POST …/{portaria_id}/devolucao` | `{ motivo }` |
| `POST …/{portaria_id}/cancelamento` | `{ motivo }`: libera o número no Protocolo (quem reservou ou administração do Protocolo) |
| `GET …/{portaria_id}/minuta?formato=docx\|pdf` | Arquivo com marca d'água "MINUTA" |
| `POST …/{portaria_id}/publicacao` | `multipart` com `arquivo` (PDF publicado); só com a portaria aceita (`409`); `400` se não for PDF |
| `GET /portarias/autoridades` | Todas as autoridades (ativas e desativadas) |
| `POST /portarias/autoridades`, `PUT /portarias/autoridades/{id}`, `DELETE /portarias/autoridades/{id}` | `{ sigla, nome, cargo, setor, usuario_id?, ativa }`; devolvem a lista atualizada. Excluir autoridade que já assinou: `409` (desative-a) |

Todas as escritas devolvem o painel atualizado.
