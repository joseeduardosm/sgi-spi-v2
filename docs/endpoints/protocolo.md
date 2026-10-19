# Protocolo: numeração institucional (`/api/protocolo`)

> **Canais dos avisos:** todo aviso deste módulo chega **sempre** na caixa de [notificações](notificacoes.md). O e-mail, o pop-up do navegador e o alerta do desktop só saem para quem ligou o evento correspondente em `/notificacoes` › Preferências (tudo começa desmarcado). Onde este documento fala em "e-mail" dos avisos, leia "para quem ligou o e-mail".

Tag no OpenAPI: **Protocolo**. Implementação:
- rotas: `backend/app/api/routes/protocolo.py`; schemas: `backend/app/schemas/protocolo.py`;
- regras: `backend/app/services/servico_protocolo.py`; modelos: `backend/app/models/protocolo.py` (`protocolo_tipos`, `protocolo_sequencias`, `protocolo_numeros`, `protocolo_eventos`; migração `d4a7b2c6e815`);
- avisos: `app/tarefas/notificacoes.py lembretes` (tarefa diária das 07:00).

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

## Faixa reservada ao SAA ("Liberar a partir de")

Cada sequência pode ter `liberar_a_partir_de` (entre `inicio` e `fim + 1`; nulo ou igual a `inicio` = nada reservado; migração `f8b3c5d7e9a1`). Os números do início da faixa até o anterior a esse ponto, **enquanto livres**, têm o estado derivado **`reservado_saa`** ("Reservado SAA"): só quem é do **Serviço de Apoio Administrativo** dá andamento neles (reservar e subir o documento). O SuperRoot e quem administra o Protocolo (CONTROLE_TOTAL) também usam a faixa. Os demais usuários reservam a partir do ponto de liberação.
- **SAA** = membro do setor (ou com ele como Departamento) cujo nome está em `setor_apoio_administrativo` (padrão "Serviço de Apoio Administrativo", inclui os setores filhos). Se o setor não existir, só SuperRoot e administração usam a faixa.
- `POST /sequencias/{id}/proximo`: só o SAA começa pela faixa reservada; os demais, **inclusive a administração**, recebem a partir do ponto de liberação (a administração ainda escolhe à mão qualquer número, inclusive os `reservado_saa`). `POST /numeros/{id}/reservar` agora aceita o SAA **só nos `reservado_saa`** (`403 sem_permissao` nos outros casos); a administração continua escolhendo qualquer número.
- Reservado e depois **liberado**, o número volta a `reservado_saa` (o estado é derivado).
- Elevar `liberar_a_partir_de` (`PUT /sequencias/{id}/faixa`) só vale se nenhum número que passa a ser do SAA estiver reservado (`409`).
- `ListaNumeros` traz `reservados_saa` e `pode_usar_reserva_saa`; cada número traz `pode_reservar`; `SequenciaLeitura` traz `liberar_a_partir_de`.
- **Tela dedicada** de novo tipo (`/protocolo/administracao/tipos/novo`) e de novo exercício (`/protocolo/administracao/tipos/{tipoId}/exercicio`): nome, exercício, início, fim e "Liberar a partir de", com prévia da faixa. `POST /tipos` aceita `sequencia` opcional e cria tipo e faixa **na mesma transação**.
- O módulo **Contratos** usa o tipo **"Portaria SPI SSGC"** e reserva sempre **fora da faixa do SAA** (`proximo(..., fora_da_reserva=True)`).

## Estados do número

`livre` (ou `reservado_saa`, dentro da faixa do SAA) → `reservado` (finalidade, responsável, data) → `utilizado` (tem documento). `anulado` prevalece sobre os demais. **Liberar** uma reserva sem documento devolve o número a `livre`; a **linha do tempo** (reservou, lançou, anexou, liberou, anulou, sigilo, vinculou) permanece.

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /tipos` | LEITURA | `ListaTipos`: tipos com as sequências de cada exercício e `pode_administrar` |
| `DELETE /sequencias/{id}` | CONTROLE_TOTAL | Exclui o exercício (faixa e números) de um tipo; só se nenhum número foi reservado, utilizado ou anulado (`409`); `204` sem corpo; `404` se não existir |
| `POST /tipos`, `PUT /tipos/{id}`, `DELETE /tipos/{id}` | CONTROLE_TOTAL | Cria, renomeia (nome único sem diferenciar maiúsculas: `409`) e exclui (só sem números reservados, utilizados ou anulados: `409`) |
| `POST /tipos/{id}/sequencias` | CONTROLE_TOTAL | `{ exercicio, inicio, fim }`: cria a sequência do exercício (até 10.000 números; uma por tipo e exercício: `409`) |
| `PUT /sequencias/{id}/faixa` | CONTROLE_TOTAL | `{ inicio, fim }`: `inicio` menor amplia **para trás** e `fim` maior amplia **para frente**, criando só os números novos. Encolher só vale para pontas livres e sem histórico (`409`) |
| `GET /sequencias/{id}/numeros` | LEITURA | `ListaNumeros`: a grade, `livres` e o que o usuário pode fazer em cada número |
| `POST /sequencias/{id}/proximo` | MODIFICACAO | `{ finalidade, contrato_id? }` → `201 NumeroLeitura`: reserva o **menor livre**, de forma atômica. `409 sequencia_esgotada` sem livres |
| `POST /numeros/{id}/reservar` | CONTROLE_TOTAL | `{ finalidade, contrato_id? }`: lança um número específico (`409` se já reservado ou anulado) |
| `GET /numeros/{id}` | LEITURA | Detalhe com a **linha do tempo** (visível mesmo com documento sigiloso) |
| `POST /numeros/{id}/liberar` | Dono ou administração (MODIFICACAO+) | `{ motivo }`: só reservado e sem documento; volta a livre |
| `POST /numeros/{id}/anular` | CONTROLE_TOTAL | `{ motivo }`: tira o número de uso para sempre (o documento anexado fica guardado) |
| `POST /numeros/{id}/anexo` | Dono ou administração | `multipart` `arquivo` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG); o número vira `utilizado`; um documento por número (`409`). **Número de portaria de designação de contrato**: só depois do aceite da autoridade e só PDF (`409`); o anexo é o D.O.E. e **publica a portaria**, aplicando a nova equipe do contrato (ver [contratos-portarias.md](contratos-portarias.md)) |
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
