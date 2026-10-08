# Reserva de Espaços (`/api/reserva-espacos`)

Tag no OpenAPI: **Reserva de Espaços**. Implementação:
- rotas: `backend/app/api/routes/reserva_espacos.py`; schemas: `backend/app/schemas/reserva_espacos.py`;
- regras: `backend/app/services/servico_reserva_espacos.py`; modelos: `backend/app/models/reserva_espacos.py` (`reserva_espacos_espacos`, `_reservas`, `_eventos`, `_fiscais`, `_configuracao`; migração `c7d1e5a9b3f4`);
- avisos: mensageria (nova solicitação, deferimento, indeferimento, cancelamento, predefinida) e lembrete **um dia antes** na tarefa diária (`app/tarefas/mensageria.py`).

Migrado da Reserva de Espaços do 10.23.1.243 (Django). Carga dos dados: `scripts/extrair-reserva-espacos-243.py` (somente leitura; grava o pacote em `dados/`) e `scripts/migrar-reserva-espacos-243.py` (ensaio por padrão; `--gravar`; `--substituir`; idempotente pelo id de origem). Dados migrados: 4 espaços, 91 reservas (54 deferidas, 36 canceladas, 1 aguardando), 218 eventos e 4 fiscais. A reserva de teste com data `0020-06-22` teve o ano corrigido para 2026.

## Papéis

Recurso ACL `reserva-espacos` (sem regras = aberto a todo usuário autenticado). Dentro dele:

| Papel | O que pode |
|---|---|
| Solicitante (qualquer usuário) | Ver a agenda, solicitar (com recorrência), ver, alterar (só aguardando aprovação) e cancelar o que criou ou em que é responsável |
| Fiscal (tabela `reserva_espacos_fiscais`) ou SuperRoot | Tudo do solicitante, mais: fila, deferir/indeferir, reserva predefinida, ver todas as reservas, cadastrar espaços, painel e exportação |
| SuperRoot | Também grava a configuração e a lista de fiscais |

Operação de fiscal sem o papel → `403 acesso_negado`.

## Regras

- Status: `AGUARDANDO_APROVACAO` → `DEFERIDA` | `INDEFERIDA` (justificativa obrigatória) | `CANCELADA` (motivo obrigatório).
- **Conflito**: só reservas `DEFERIDAS` do mesmo espaço e data com horários sobrepostos bloqueiam (`409 conflito`); horário colado (fim = início da outra) é permitido. Pendentes geram só `avisos` na solicitação.
- **Recorrência** (`diaria`, `semanal`, `quinzenal`, `mensal`, até `recorrencia_ate`, no máximo 120 ocorrências) só na criação; todas compartilham o `serie_id`. Mensal preserva o dia, ajustando ao fim de meses curtos. Deferir/indeferir valem para a série pendente inteira (em bloco: um conflito impede todas).
- **Cancelamento** com `escopo`: `ocorrencia`, `serie` ou `periodo` (`de`/`ate`).
- Configuração: horário de funcionamento, antecedência mínima e duração máxima (não valem para o fiscal) e capacidade do espaço (aviso).
- Solicitante só solicita data futura; fiscal pode registrar retroativamente.

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /contexto` | Autenticado | `{ eh_fiscal, espacos }` (inativos só para fiscal) |
| `GET /agenda?inicio&fim&espaco_id` | Autenticado | Reservas do período (até 62 dias): deferidas para todos; aguardando também para fiscal e dono. `400` se o período for inválido |
| `GET /disponibilidade?data&hora_inicio&hora_fim` | Autenticado | Espaços ativos livres no horário |
| `GET /minhas?status` | Autenticado | Reservas do usuário (solicitante ou responsável) |
| `GET /reservas` | Fiscal | Lista paginada (`status`, `espaco_id`, `inicio`, `fim`, `busca`, `pagina`, `tamanho`) → `ListaReservas` |
| `GET /exportar` | Fiscal | Planilha XLSX com os mesmos filtros |
| `GET /fila` | Fiscal | Solicitações aguardando análise |
| `GET /reservas/{id}` | Fiscal, solicitante ou responsável | `ReservaDetalhe` com linha do tempo e demais ocorrências da série (`403` para os demais, `404`) |
| `POST /reservas` | Autenticado | `201 { reservas, avisos }`; `400` regra de horário/recorrência, `409` conflito com deferida |
| `POST /reservas/predefinida` | Fiscal | Já nasce `DEFERIDA`, em nome de `responsavel_id` ou `responsavel_nome` |
| `PUT /reservas/{id}` | Dono ou fiscal | Altera data, horário, espaço, título, observações e participantes; só aguardando (`409` caso contrário) |
| `POST /reservas/{id}/analise` | Fiscal | `{ decisao: deferir|indeferir, justificativa }` → reservas atualizadas da série |
| `POST /reservas/{id}/cancelamento` | Dono ou fiscal | `{ escopo, motivo, de?, ate? }` → reservas canceladas |
| `GET /usuarios?busca` | Fiscal | Até 20 usuários ativos, para escolher o responsável |
| `POST /espacos`, `PUT /espacos/{id}` | Fiscal | Cadastra e altera (nome único: `409`) |
| `DELETE /espacos/{id}` | Fiscal | Exclui; se já teve reservas, apenas inativa → `{ "resultado": "excluido" | "inativado" }` |
| `GET /painel?ano&mes` | Fiscal | Indicadores do mês, deferidas por mês, ocupação por espaço e ranking de pessoas |
| `GET /configuracao` | Fiscal | Horários, antecedência, duração máxima e fiscais |
| `PUT /configuracao` | SuperRoot | Grava as regras e a lista de fiscais (`fiscais_ids`) |

Erros no formato `{"detalhe", "codigo"}`. Telas: `/reserva-espacos` (agenda mensal), `/nova`, `/minhas`, `/reservas`, `/reservas/:id`, `/fila`, `/espacos`, `/painel`, `/configuracao`.
