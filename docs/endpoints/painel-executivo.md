# Painel Executivo (`/api/painel-executivo`)

Tag no OpenAPI: **Painel Executivo**. Implementação:
- rotas: `backend/app/api/routes/painel_executivo.py`;
- dados dos slides: `backend/app/services/painel_executivo/slides.py` (reaproveita `servico_painel` de contratos, `servico_afastamentos`/`servico_periodos` do RH e `servico_tarefas`);
- PDF: `backend/app/services/painel_executivo/pdf.py` (reportlab);
- acesso: `backend/app/services/painel_executivo/acesso.py`; cache: `cache.py`;
- recurso ACL criado pela migração `9a4d2e6f1b38`.

Visão da **organização inteira** para a Diretoria, em slides: contratos, RH e tarefas.

## Quem acessa

Recurso ACL **`painel-executivo`**. Diferente dos demais recursos, **sem nenhuma regra só o SuperRoot acessa** (a migração cria o recurso vazio). Para liberar a Diretoria, o administrador cria uma regra com nível LEITURA (ou maior) para os usuários ou setores em *Administração › ACL*. Quem não tem acesso recebe `403 acl_negado`.

## Rotas

| Método | Rota | Descrição | Respostas |
|---|---|---|---|
| `GET` | `/api/painel-executivo/acesso` | `{ "pode": true/false }`; nunca devolve 403. Usado pela home e pela barra lateral | 200, 401 |
| `GET` | `/api/painel-executivo/contratos?exercicio=` | `SlideContratos` | 200, 403, 422 |
| `GET` | `/api/painel-executivo/rh?ano=` | `SlideRh` | 200, 403, 422 |
| `GET` | `/api/painel-executivo/tarefas` | `SlideTarefas` | 200, 403 |
| `GET` | `/api/painel-executivo/{slide}/pdf` | PDF paisagem do slide (`contratos`, `rh` ou `tarefas`) | 200, 403, 422 |

Erros no formato `{"detalhe", "codigo"}`. Os dados têm **cache de 60 segundos** por processo.

## Conteúdo dos slides

- **Contratos:** `numeros` (ativos, a vencer, encerrados, valor global), `execucao` do exercício (previsto × medido × pago por mês, empenhado, consumido, saldo), `acumulado` (mesma série acumulada mês a mês), `vencimentos` (contratos vigentes que vencem em 30, 60 e 90 dias), `alertas_altos`/`alertas_medios` (contratos com risco) e `maiores_riscos` (até 5, mais graves primeiro). Padrão: ano corrente.
- **RH:** `afastados_hoje` (férias ou licença-prêmio aprovadas/gozadas que cobrem hoje), `por_mes` (pessoas distintas afastadas em cada mês), `por_setor` (dias no ano, até 8), `ferias_a_vencer` (saldo não agendado, período terminando em até 90 dias) e `alertas_setor` (setores acima do limite de afastados). Visão global, sem o escopo por papel do painel do RH.
- **Tarefas:** `abertas`, `atrasadas`, `vencem_hoje`, `criticas`, `em_validacao`, `concluidas_30_dias`, `equipes` (até 10, atrasadas primeiro, com carga e faixa) e `semanas` (criadas × concluídas nas últimas 12 semanas, a partir da segunda-feira).

Valores monetários seguem o padrão de contratos (texto com 2 casas).
