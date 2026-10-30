# Integração com o SIGEO (`/api/integracao-sigeo`)

Tag no OpenAPI: **Integração SIGEO**. Implementação:
- `backend/app/api/routes/integracao_sigeo.py`, `backend/app/services/servico_integracao_sigeo.py` e `backend/app/models/integracao_sigeo.py` (tabela `integracao_sigeo`, linha única; migração `e5a9c3f7b1d4`);
- cliente SOAP do OBIEE: `backend/app/services/sigeo/cliente_obiee.py` (`httpx` + `lxml`);
- conferência: `backend/app/services/contratos/servico_ob_sigeo.py`; rotina: `python -m app.tarefas.sigeo conferir` pelo timer `systemd/sgi-spi-sigeo-ob.timer`, que passa **de hora em hora** e só confere **uma vez por dia, a partir da hora configurada** (`hora_conferencia`, 0–23, horário de Brasília, padrão 8; migração `f6b0d4a8c2e5`). `python -m app.tarefas.sigeo agora` confere na hora;
- tela: Administração › Integração SIGEO (`/admin/sigeo`, só SuperRoot).

O SGI lê no SIGEO (Oracle BI/OBIEE da Fazenda) a análise salva com as ordens bancárias pagas (colunas `COD_PROCESSO`, `COD_DOCUMENTO`, `DATA_LANCAMENTO`, `DESCRICAO_DOCUMENTO`, `VALOR_DOCUMENTO`, `CGC_CPF`…) pelo web service SOAP: `nQSessionService.logon` → `xmlViewService.executeXMLQuery` (caminho da análise) → `logoff`. Só lê.

## Acesso

Todas as rotas: **SuperRoot**. A senha fica cifrada (`CHAVE_CIFRA_LDAP`) e nunca volta pela API; senha vazia no `PUT` preserva a gravada.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/integracao-sigeo` | `ativo`, `url_base`, `caminho_analise`, `caminho_analise_empenhado`, `usuario`, `possui_senha`, `hora_conferencia`, `configurada`, `ultima_execucao_em`, `ultimo_resultado`, `atualizado_em`, `atualizado_por` |
| `PUT` | `/api/integracao-sigeo` | Corpo: `ativo`, `url_base`, `caminho_analise`, `caminho_analise_empenhado` (opcional), `usuario`, `senha` (opcional), `hora_conferencia` (0–23). `422` se faltar campo |
| `POST` | `/api/integracao-sigeo/testar` | Entra no SIGEO, executa a análise e diz quantas OBs vieram (`sucesso`, `mensagem`, `linhas`, `latencia_ms`); sempre `200` |
| `POST` | `/api/integracao-sigeo/conferir?ensaio=true` | Faz o que a rotina das 08:00 faz. Com `ensaio=true` (padrão) só relata. Resposta: `verificadas`, `aguardando`, `concluidas[]` (`competencia`, `contrato_id`, `ob`, `valor`), `pendencias[]` (`competencia`, `contrato_id`, `motivo`), `sugestoes_processo[]` (contratos esperando OB sem processo financeiro, com os processos que o SIGEO usa para o CNPJ da contratada) e `erros[]` |

## Cadastro automático de NEs e cancelamentos

Contratos com **Processo Financeiro** preenchido e **sem nenhuma NE cadastrada** recebem, sozinhos, as Notas de Empenho do(s) processo(s) e os cancelamentos, lidos da análise de empenhos (`caminho_analise_empenhado`, padrão `…/EMPENHADO - Execução`; migração `b8d2f6a0c4e7`). Roda junto da conferência diária das OBs e sob demanda em `POST /api/integracao-sigeo/empenhos?ensaio=true` (SuperRoot; `ensaio=false` grava). Resposta: `contratos` (NEs e cancelamentos), `nes_cadastradas`, `cancelamentos`, `pendencias` e `sem_empenho_no_sigeo`.

- **NE:** linha com valor positivo; cadastrada com o número curto `AAAANEnnnnn` (fim do `COD_DOCUMENTO`) e o valor como valor original.
- **Cancelamento:** linha com valor **negativo** (eventos 400093 e 400096); `COD_DOCUMENTO_ORIGEM` é a NE cancelada. Vira um cancelamento dessa NE, com o texto do SIGEO e a data de lançamento na justificativa.
- **Nunca altera** contrato que já tem NE. Cancelamento sem a NE na análise, soma de cancelamentos acima do valor da NE e números repetidos viram **pendência** e não gravam aquele item. Auditoria `contrato.nota_empenho.sigeo`.
- **Limite:** a análise hoje só traz NEs de 2025; contratos cujo empenho é de outro exercício aparecem em `sem_empenho_no_sigeo` até a análise ser ampliada no SIGEO.
- As NEs nascem **sem os pagamentos anteriores ao SGI abatidos**.

## Regra da conferência

Para cada competência na etapa **ordem bancária** (sem OB juntada) de um contrato com **Processo Financeiro** preenchido (campo opcional do contrato, ver [contratos-cadastro.md](contratos-cadastro.md)):

1. OBs do SIGEO do(s) mesmo(s) processo(s) (só dígitos). O contrato pode ter **mais de um processo financeiro** (ex.: um por exercício), separados por vírgula, ponto e vírgula ou espaço no campo, lançadas a partir do início do período e ainda não usadas por outra competência.
2. **Competência lida no texto livre** `DESCRICAO_DOCUMENTO`: nome do mês com ano opcional (`REF NOV/25`, `JUL26`, `SETEMBRO DE 2026`, `REF-MAI/26`) ou número depois de REF/COMP (`REF. 09/2026`). Ano ausente ou fora de propósito (ex.: `AGO/16` lançado em 2026) vira a última ocorrência daquele mês até o lançamento. Mês colado num dia (`10SET26`) é a data da nota e é ignorado. Dois meses diferentes = ambíguo.
3. A soma das OBs do mês (o pagamento pode vir em partes) é comparada ao **líquido**: valor a pagar (notas brutas + despesas variáveis) − retenções conferidas. A OB paga o líquido; os tributos retidos saem em outros documentos.

Igual ao centavo → **conclui**: gera o PDF "Comprovante de pagamento (SIGEO)" no lugar do PDF da OB, debita as NEs pelo valor a pagar (como no lançamento manual), grava `ob_origem = sigeo`, `ob_numero`, `ob_data`, `ob_valor`, audita (`contrato.execucao.ordem_bancaria.sigeo`), sincroniza as tarefas e envia o e-mail de pagamento. Sem OB do processo ainda → `aguardando` (normal). Qualquer dúvida (texto sem mês, soma parcial ou acima, duas competências do mesmo mês esperando OB) → **não conclui** e grava o motivo em `ob_sigeo_pendencia`, que aparece na etapa da OB; a equipe junta a OB manualmente. Sem mês legível nunca conclui: os contratos de valor fixo repetem o mesmo valor todo mês. Idempotente.


## Execução retroativa e e-mail de pagamento

A conferência conclui competências anteriores à data "Desconsiderar alertas a partir de" do contrato (ou ao corte global de 01/09/2026) normalmente, mas **não envia o e-mail de pagamento** a elas: o motivo fica em `email_ob_erro` da competência (o reenvio manual continua possível).
