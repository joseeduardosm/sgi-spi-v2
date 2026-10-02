# Protocolo: numeração institucional (`/api/protocolo`)

Tag no OpenAPI: **Protocolo**. Implementação:
- rotas: `backend/app/api/routes/protocolo.py`; schemas: `backend/app/schemas/protocolo.py`;
- regras: `backend/app/services/servico_protocolo.py`; modelos: `backend/app/models/protocolo.py` (`protocolo_tipos`, `protocolo_sequencias`, `protocolo_numeros`, `protocolo_eventos`; migração `d4a7b2c6e815`);
- avisos: `app/tarefas/mensageria.py lembretes` (tarefa diária das 07:00).

Migrado do Protocolo do SGI SPI antigo (10.23.1.220) com melhorias. A carga dos dados está em [migracao-sgi.md](../migracao-sgi.md) (`scripts/extrair-protocolo-sgi.py` e `scripts/migrar-protocolo-sgi.py`).

## Finalidade

Controla a numeração de documentos (Ofício, Portaria, Resolução…). Cada **tipo** tem uma **sequência por exercício** (a numeração reinicia a cada ano: `005/2026`). A pessoa reserva o **próximo número**, informa a finalidade e, depois, anexa o documento, o que torna o número **utilizado**.

## Permissões (recurso ACL `protocolo`)

Atenção: um recurso ACL **sem nenhuma regra fica aberto a todos**; por isso o recurso `protocolo` deve ter ao menos uma regra (a migração cria uma para quem já usava o Protocolo).

| Nível | O que pode |
|---|---|
| `LEITURA` | Ver tipos, a grade, o painel e a **linha do tempo**, e exportar |
| `MODIFICACAO` | Reservar o **próximo** número, anexar o documento do que reservou, liberar a própria reserva, marcar sigilo e vincular a um contrato |
| `CONTROLE_TOTAL` (ou SuperRoot) | Cadastrar tipos, criar sequências, **ampliar a faixa** para trás e para frente, **lançar um número específico**, anular e atuar em qualquer reserva |

## Estados do número

`livre` → `reservado` (finalidade, responsável, data) → `utilizado` (tem documento). `anulado` prevalece sobre os demais. **Liberar** uma reserva sem documento devolve o número a `livre`; a **linha do tempo** (reservou, lançou, anexou, liberou, anulou, sigilo, vinculou) permanece.

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /tipos` | LEITURA | `ListaTipos`: tipos com as sequências de cada exercício e `pode_administrar` |
| `POST /tipos`, `PUT /tipos/{id}`, `DELETE /tipos/{id}` | CONTROLE_TOTAL | Cria, renomeia (nome único sem diferenciar maiúsculas: `409`) e exclui (só sem números reservados, utilizados ou anulados: `409`) |
| `POST /tipos/{id}/sequencias` | CONTROLE_TOTAL | `{ exercicio, inicio, fim }`: cria a sequência do exercício (até 10.000 números; uma por tipo e exercício: `409`) |
| `PUT /sequencias/{id}/faixa` | CONTROLE_TOTAL | `{ inicio, fim }`: `inicio` menor amplia **para trás** e `fim` maior amplia **para frente**, criando só os números novos. Encolher só vale para pontas livres e sem histórico (`409`) |
| `GET /sequencias/{id}/numeros` | LEITURA | `ListaNumeros`: a grade, `livres` e o que o usuário pode fazer em cada número |
| `POST /sequencias/{id}/proximo` | MODIFICACAO | `{ finalidade, contrato_id? }` → `201 NumeroLeitura`: reserva o **menor livre**, de forma atômica. `409 sequencia_esgotada` sem livres |
| `POST /numeros/{id}/reservar` | CONTROLE_TOTAL | `{ finalidade, contrato_id? }`: lança um número específico (`409` se já reservado ou anulado) |
| `GET /numeros/{id}` | LEITURA | Detalhe com a **linha do tempo** (visível mesmo com documento sigiloso) |
| `POST /numeros/{id}/liberar` | Dono ou administração (MODIFICACAO+) | `{ motivo }`: só reservado e sem documento; volta a livre |
| `POST /numeros/{id}/anular` | CONTROLE_TOTAL | `{ motivo }`: tira o número de uso para sempre (o documento anexado fica guardado) |
| `POST /numeros/{id}/anexo` | Dono ou administração | `multipart` `arquivo` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG); o número vira `utilizado`; um documento por número (`409`) |
| `GET /numeros/{id}/anexo` | LEITURA | Baixa o documento. **Sigiloso: só o dono e o SuperRoot** (`403 documento_sigiloso`) |
| `PUT /numeros/{id}/sigilo` | Dono ou SuperRoot | `{ sigiloso }`: marca ou desmarca o sigilo |
| `PUT /numeros/{id}/contrato` | Dono ou administração | `{ contrato_id \| null }`: vínculo opcional com um contrato (exige acesso ao Módulo de Contratos) |
| `GET /contratos/{contrato_id}` | LEITURA | Números vinculados ao contrato (para a ficha do contrato) |
| `GET /painel?tipo_id=&ano=` | LEITURA | Reservas e utilizações por mês, top 10 pessoas e reservados sem documento |
| `GET /exportar?formato=xlsx\|pdf&tipo_id=&exercicio=` | LEITURA | Controle dos números com movimento (sem o conteúdo dos documentos) |

**`NumeroLeitura`:** `id`, `tipo_nome`, `exercicio`, `numero`, `numero_formatado` (`005/2026`), `estado`, `finalidade`, `reservado_por_nome`, `reservado_em`, `usado_em`, `contrato_id`/`contrato_numero`, `sigiloso`, `anulado_em`, `motivo_anulacao`, `arquivo` (`id`, `nome`, `tamanho`, `pode_baixar`), `pode_anexar`, `pode_liberar`, `pode_alterar_sigilo` e `eventos[]`.

### Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Finalidade ou motivo vazios, faixa inválida, arquivo recusado |
| `403` | `acl_negado` / `sem_permissao` / `documento_sigiloso` | Sem o nível exigido, não é o dono, ou documento sigiloso |
| `404` | `nao_encontrado` | Tipo, sequência, número ou documento inexistente |
| `409` | `conflito` / `sequencia_esgotada` | Número já reservado, estado incompatível, nome duplicado, faixa que excluiria números usados |

## Avisos e auditoria

- **Aviso de reserva esquecida:** a tarefa diária avisa o responsável (mensagem e e-mail) quando o número está reservado sem documento há `PROTOCOLO_DIAS_AVISO` dias (padrão 5) e de novo ao dobro; o aviso é encerrado ao anexar, liberar ou anular.
- **Auditoria:** `protocolo.tipo.criar|alterar|excluir`, `protocolo.sequencia.criar|alterar`, `protocolo.reservar`, `protocolo.liberar`, `protocolo.anular`, `protocolo.anexar`, `protocolo.sigilo`, `protocolo.vincular`.

## Consumo no Angular

Rota `/protocolo` (item "Protocolo" na barra lateral; `guardaAcl` com `acl: 'protocolo'`): seleção de tipo e exercício, grade de números (com cadeado nos sigilosos), "Reservar próximo número", janela do número com linha do tempo, anexo, sigilo, vínculo, liberar e anular, painel e exportação; administração (tipos, exercícios e faixas) só com CONTROLE_TOTAL.
