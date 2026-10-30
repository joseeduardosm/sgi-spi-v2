# Parâmetros de Contratos (`/api/contratos/parametros`)

Tag no OpenAPI: **Contratos: parâmetros**. Implementação:
- rotas: `backend/app/api/routes/contratos/parametros.py`; schemas: `backend/app/schemas/contratos/parametros.py`;
- serviço: `backend/app/services/contratos/servico_parametros.py` (`parametros`, `leitura`, `salvar` e `valor(nome)`, que o resto do código usa);
- modelo: `backend/app/models/contratos/parametros.py` (tabela `contratos_parametros`, linha única `id = 1`; `PADROES` guarda os valores de fábrica); migração `c9e3a7f1b5d2`;
- tela: Contratos › Parâmetros (`/contratos/parametros`), visível só para quem tem controle total em Contratos.

Reúne os números que antes estavam fixos no código (cortes de alertas, prazos, regras e limites). Os valores iniciais são os de antes, então **nada muda de comportamento até alguém editar**. Se o banco falhar na leitura, o código cai nos valores de fábrica (um parâmetro nunca derruba uma tela). Os valores lidos ficam até 30 segundos em memória; quem salva já vê o novo valor na hora.

## Acesso

| Rota | Quem |
|---|---|
| `GET /api/contratos/parametros` | ACL `contratos` ≥ LEITURA (as telas leem estes números em vez de repetir valores fixos) |
| `PUT /api/contratos/parametros` | **Controle total** em Contratos ou SuperRoot; os demais recebem `403` |

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/contratos/parametros` | Todos os parâmetros, `atualizado_por_nome`, `atualizado_em` e `padroes` (valores de fábrica, para "Restaurar padrão"). Na primeira leitura de um banco novo a linha é criada com os padrões |
| `PUT` | `/api/contratos/parametros` | Substitui o conjunto (envie todos os campos). `200` com a leitura nova; `422` para valor fora do limite ou incoerente; `403` sem controle total. Audita `contratos.parametros` com `{campo: {de, para}}` só do que mudou |

## Parâmetros

**Alertas e cortes**

| Campo | Padrão | Faixa | Efeito |
|---|---|---|---|
| `corte_alertas_a_partir_de` | 01/09/2026 | data | Competências que terminam antes dela não geram pendências, alertas, avisos de atraso nem o e-mail de pagamento. Vale o maior entre este corte e o "Desconsiderar alertas a partir de" do contrato |
| `corte_marcadores_a_partir_de` | 01/08/2026 | data | Competências que começam antes dela não aparecem como marcadores na carteira |
| `dias_pagamento_vencendo` | 5 | 0–365 | Pagamento que vence em até N dias vira risco médio |
| `dias_atraso` | 30 | 1–365 | Medição atrasada há mais de N dias: risco médio; mais de 2×N: alto; também dispara o aviso de atraso |
| `dias_vigencia_a_vencer` | 90 | 1–730 | Contrato com fim de vigência em até N dias fica "a vencer" |
| `dias_vigencia_atencao` | 180 | 1–1460 | Faixa de atenção da linha do tempo de vigências (maior que a de "a vencer") |
| `dias_sem_prorrogacao_alto` | 60 | 1–730 | "A vencer sem prorrogação": alto com até N dias, médio acima |
| `dias_documento_alto` / `dias_documento_medio` | 15 / 30 | 0–730 | Severidade do documento com validade a vencer (médio ≥ alto) |
| `dias_fim_vigencia_alto` / `dias_fim_vigencia_medio` | 30 / 60 | 0–730 | Severidade do fim de vigência no calendário (médio ≥ alto) |

**Regras do contrato**

| Campo | Padrão | Faixa | Efeito |
|---|---|---|---|
| `vigencia_maxima_padrao_meses` | 60 | 1–600 | Vigência máxima que o formulário de novo contrato já traz |
| `maximo_meses_vigencia_retroativa` | 120 | 1–600 | Prazo máximo, em meses, de uma vigência retroativa (`POST …/vigencias-retroativas`, `400` acima disso) |
| `limite_aditamento_sem_autorizacao` | 25 | 0–1000 (%) | Acréscimo acumulado acima do qual o aditamento exige a autorização anexada |
| `limite_acerto_centavos` | 1,00 | 0–1000 (R$) | Maior acerto por item na medição |
| `maximo_notas_fiscais` | 20 | 1–200 | Notas fiscais (e documentos de despesa variável) por competência |
| `prazo_pagamento_padrao_dias` | 30 | 0–365 | Prazo de pagamento sugerido na etapa de nota fiscal e usado nas tarefas quando a NF ainda não entrou |
| `prazo_nota_fiscal_horas` | 48 | 1–720 | Prazo da NF depois da medição, nas competências sem prazo de contestação |

**Prorrogação** (migração `e2a6c0d4f8b1`)

| Campo | Padrão | Efeito |
|---|---|---|
| `ssgc_nome` / `ssgc_cpf` | Laercio Paulino Simões / 822.684.878-49 | Subsecretário(a) de Gestão Corporativa: assina o termo aditivo e as declarações |
| `secretario_nome` / `secretario_cpf` | Rafael Antonio Cren Benini / 223.011.918-42 | Autoridade máxima no Termo de Ciência e Notificação (TCE) |
| `autoridade_competente_nome` / `_cargo` | Laercio Paulino Simões / Subsecretário de Gestão Corporativa | Quem assina o despacho de autorização |
| `pncp_dias_uteis_licitacao` | 20 | Prazo (dias úteis a partir da assinatura) para divulgar no PNCP o termo de licitação |
| `pncp_dias_uteis_direta` | 10 | O mesmo, para dispensa e inexigibilidade |
| `aviso_pncp_dias_uteis` | 5 | Lembrete, em dias úteis antes do prazo |
| `parecer_referencial_validade_dias` | 365 | Validade do Parecer Referencial da PGE (NLC nº 1/2026), desde a emissão |
| `parecer_referencial_vigencia_ate` | 09/02/2027 | Data limite do parecer vigente |

**Arquivos e limites**

| Campo | Padrão | Faixa | Efeito |
|---|---|---|---|
| `xml_tamanho_maximo_mb` | 5 | 1–100 | XML de nota fiscal |
| `planilha_tamanho_maximo_mb` | 5 | 1–100 | Planilhas de importação (cadastro do contrato e modelos) |
| `maximo_anexos_ocorrencia` | 5 | 1–50 | Anexos por ocorrência do diário |
| `anexos_email_maximo_mb` | 15 | 1–100 | Soma máxima dos anexos de uma ocorrência enviados por e-mail |

O tamanho máximo de um anexo PDF comum continua sendo o do servidor (`ANEXOS_TAMANHO_MAXIMO_MB`, vale para todos os módulos).

## Observações

- Antecipar `corte_alertas_a_partir_de` reabre pendências e alertas de competências antigas.
- Competências anteriores ao corte seguem o **caminho curto** (medição, avaliação se houver, nota fiscal e OB), sem e-mails nem avisos: ver [contratos-execucao.md](contratos-execucao.md#competência-retroativa-anterior-ao-corte-de-alertas).
- A base de cálculo (30/360, casas decimais), a lista de tributos, as etapas e o catálogo de documentos **não** são parâmetros.
