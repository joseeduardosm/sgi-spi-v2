# Endpoints da execução do contrato (`/api/contratos/{contrato_id}/…`)

Tag no OpenAPI: **Contratos: execução**. Implementação:
- rotas: `backend/app/api/routes/contratos/execucao.py`;
- serviços: `servico_configuracao_execucao.py` (checklists e formulários), `servico_competencias.py` (competências e etapas) e `documentos_execucao.py` (PDFs), em `backend/app/services/contratos/`.

## Finalidade

Configurar a execução (checklist de documentos mensais e formulário de avaliação), gerar as competências e levar cada uma da medição até a Ordem Bancária.

## Regras gerais

- **Autorização:**
  - **Leitura:** ACL `contratos` ≥ `LEITURA`.
  - **Gravação:** poder editar o contrato. Os seis papéis da equipe têm os mesmos poderes.
  - **Ciências:** só integrantes **vigentes** da equipe (o SuperRoot fora da equipe não registra ciência).
  - **Reabrir etapa (e estornar pagamento):** o SuperRoot ou o **gestor vigente** do contrato (papel `gestor`, com ACL ≥ MODIFICACAO).
- **Versões de checklist e de formulário:** nascem inativas. Uma versão ativa não é editada nem excluída; para mudar, duplica-se.
  - Ativar o **checklist** aplica a nova versão às competências que ainda não passaram do checklist (documentos já anexados com o mesmo nome são mantidos).
  - Ativar o **formulário** aplica a nova versão às competências ainda na medição.
- **Formulário:**
  - escala de notas em ordem crescente e sem repetição;
  - faixas de liberação (mínimo ≤ máximo; máximo nulo = sem teto; % do pagamento; `notas_zero` opcional, ver Avaliação);
  - grupos com itens cujos pesos somam 100%.
- **Geração das competências** (idempotente; "Atualizar" cria só as que faltam):
  - uma competência a cada `periodicidade_meses` meses **civis**, a partir do início de cada vigência, recortada pelas datas da vigência;
  - cada competência fotografa os itens (preço vigente no mês; prevista contínua com pró-rata 30/360 quando o item calcula pró-rata; prevista sob demanda = apontamentos da previsão), o checklist ativo e, se houver, o formulário ativo;
  - depois da geração, itens e ordem só mudam pelo SuperRoot;
  - um período que se **sobrepõe** a uma competência existente não é gerado. É o caso das competências migradas do SGI, que seguem o aniversário do contrato (ex.: 15/01 a 14/02; ver [../migracao-sgi.md](../migracao-sgi.md));
  - **mês dividido:** quando uma vigência termina no meio do mês, o mês gera **duas competências** (uma por vigência, cada uma com o seu preço e as suas NEs), identificadas como 1ª e 2ª parte.
- **Pré-requisitos** para gerar:
  - ao menos 1 item e 1 integrante da equipe;
  - previsão salva em cada vigência, se houver item sob demanda;
  - checklist ativo;
  - ao menos 1 NE com saldo.
- **Identificação e tipos:**
  - `identificador` (chave da rota da tela): `AAAA-MM`; `AAAA-MM-1`/`AAAA-MM-2` nas partes de um mês dividido; `AAAA-MM-dif` na diferença de reajuste. Em um mês dividido, `AAAA-MM` abre a 1ª parte;
  - `rotulo` para exibição: `01/2027`, `01/2027 · 1ª parte`, `Diferença de reajuste 01/2026 a 04/2026`;
  - `tipo`: `regular` ou `diferenca_reajuste` — competência **complementar** criada ao concluir um reajuste cujo mês de referência alcança competências já medidas. Ela traz, por item, a quantidade já medida desde a referência × (preço reajustado − preço pago). As quantidades não podem ser alteradas; o fluxo é o normal (NEs e ciências, NF, CADIN, checklist, consolidado e OB), sem avaliação, e ela não conta como execução do item.
- **Situação** (não gravada): `pendente` (o período ainda não terminou), `disponivel`, `em_andamento` (medição salva ou etapa posterior) e `concluida`.
- **Etapas:** 1 `medicao` → 2 `avaliacao` (só com formulário) → 3 `nota_fiscal` → 4 `cadin` → 5 `checklist` → 6 `consolidado` → 7 `ordem_bancaria` → `concluida`.
  - Cada ação exige a competência na sua etapa (senão `400`).
  - A medição só é liberada depois do fim do período.
- **Medição:**
  - informa a quantidade medida de todos os itens (até 10 casas) e as NEs em **ordem de consumo**; o **saldo livre** somado dessas NEs deve cobrir o valor a pagar (saldo livre = saldo − o **comprometido** por outras competências com medição concluída e ainda não pagas);
  - **item sob demanda:** a medição não pode passar do saldo disponível do item na vigência (limite − já executado). Ao salvar, o detalhe traz o aviso em `avisos`; a conclusão é recusada até corrigir a medição ou registrar um aditamento;
  - qualquer alteração apaga as ciências;
  - a conclusão exige **ao menos 2 ciências de pessoas diferentes** e gera a memória de cálculo em PDF (nova versão só se os dados mudaram);
  - concluir soma o medido na quantidade executada dos itens.
- **Avaliação:**
  - nota da escala abaixo da máxima exige justificativa (inicial) ou complemento (gestor);
  - nota final = **soma** das notas dos grupos, e em cada grupo Σ nota × peso / 100 (vale a nota do gestor, se houver) — igual à planilha oficial ("Somatório das notas totais dos grupos");
  - % liberado: pela nota, a faixa com mínimo ≤ nota ≤ máximo (entre várias, a de maior mínimo). Faixas com `notas_zero = N` também se aplicam quando algum grupo tem **ao menos N notas mínimas** da escala (a "nota 0" da planilha). Entre as faixas aplicáveis, vale a de **menor** percentual; nenhuma = 0%. Ex. da planilha: ≥ 6,75 → 100%; 5 a 6,74 ou 1 nota 0 num grupo → 90%; < 5 ou 2+ notas 0 num grupo → 75%;
  - fluxo: assinaturas do ateste (integrantes da equipe) → ciência de cada indicado → PDF → via assinada pela contratada (conclui a etapa);
  - reconsideração: uma vez, antes da nota fiscal, reabre a avaliação.
- **Nota fiscal:**
  - origem `medicao`: bruto = total medido × % autorizado; origem `manual`: `valor_bruto`;
  - retenções não negativas e com soma ≤ bruto;
  - vencimento = data de recebimento + prazo (dias corridos);
  - nota adicional opcional (`possui_adicional=true` e campos `adicional_*`);
  - as duas notas são pagas pelas **mesmas NEs** apontadas na medição: o saldo livre delas precisa cobrir NF + NF adicional (brutos), senão `400`.
- **CADIN:** com pendência, exige descrição e e-mail de comunicação, e a etapa continua aberta; sem pendência, conclui.
- **Checklist:**
  - um PDF por documento;
  - cada documento é **obrigatório** ou **opcional** (`obrigatorio`, padrão `true`; os documentos anteriores a esta opção são obrigatórios);
  - a etapa conclui sozinha quando todos os documentos estão anexados;
  - com os obrigatórios anexados, `POST …/checklist/concluir` conclui a etapa mesmo com opcionais sem anexo.
- **Consolidado:** resumo executivo + memória, avaliação assinada, NFs, CADIN e checklist em um PDF. Pode ser gerado de novo até a OB.
- **Ordem Bancária:** debita nas NEs apontadas, na ordem escolhida, o **valor a pagar** = NF principal + NF adicional (valores brutos), e conclui a competência. O lançamento (`pagamento`) registra o autor.
- **Reabrir (SuperRoot ou gestor):** volta para uma etapa anterior com justificativa e desfaz as conclusões posteriores. Se a competência estava paga, cada débito ganha um lançamento de **`estorno`** (valor negativo, com autor e justificativa) no extrato da NE; o pagamento original **permanece** no extrato. Anexos e histórico ficam guardados.
- **Auditoria:** `contrato.checklist.*`, `contrato.formulario.*`, `contrato.execucao.gerar`, `contrato.execucao.medicao.*`, `contrato.execucao.avaliacao.*`, `contrato.execucao.nota_fiscal.concluir`, `contrato.execucao.cadin`, `contrato.execucao.checklist.enviar`, `contrato.execucao.consolidado`, `contrato.execucao.ordem_bancaria` e `contrato.execucao.reabrir`.

---

## Checklists

| Método e caminho | Descrição |
|---|---|
| `GET /checklists` | Versões (mais recente primeiro), sem as excluídas |
| `POST /checklists` | Cria versão inativa: `{ "nome", "itens": [{ "nome", "observacao", "obrigatorio" }] }` (`obrigatorio` padrão `true`) |
| `PUT /checklists/{checklist_id}` | Edita versão inativa |
| `POST /checklists/{checklist_id}/duplicar` | Nova versão inativa com o mesmo conteúdo |
| `POST /checklists/{checklist_id}/ativar` | Ativa e aplica às competências abertas |
| `DELETE /checklists/{checklist_id}` | Exclusão lógica de versão inativa |

Todas devolvem `LeituraChecklist[]` (`id`, `versao`, `nome`, `ativo`, `itens[]` com `obrigatorio`, `criado_por_nome`, `criado_em`, `ativado_em`).

## Formulários de avaliação

| Método e caminho | Descrição |
|---|---|
| `GET /formularios` | Versões |
| `POST /formularios` | `{ "nome", "definicao": { "escala": [{ "valor", "legenda" }], "faixas": [{ "minimo", "maximo", "percentual" }], "grupos": [{ "nome", "itens": [{ "nome", "descricao", "peso" }] }] } }` |
| `PUT /formularios/{formulario_id}` | Edita versão inativa |
| `POST /formularios/{formulario_id}/duplicar` | Nova versão inativa |
| `POST /formularios/{formulario_id}/ativar` | Ativa e aplica às competências na medição |

A API gera `id` para grupos e itens. As respostas da avaliação referenciam o `id` do item.

## Competências

| Método e caminho | Descrição |
|---|---|
| `GET /execucao` | `PainelExecucao`: `requisitos` (`prontos`, `pendencias[]`), `geradas` e `grupos[]` por vigência com `ResumoCompetencia` (`id`, `competencia`, `tipo`, `parte`, `identificador`, `rotulo`, `periodo_inicio`, `periodo_fim`, `situacao`, `etapa_atual`, `valor_medicao`, `possui_avaliacao`) |
| `POST /execucao/gerar` | Gera/atualiza as competências. Pré-requisito faltando → `400` com os motivos |
| `GET /competencias/identificador/{identificador}` | `DetalheCompetencia` pelo `identificador` (`AAAA-MM`, `AAAA-MM-1`, `AAAA-MM-2`, `AAAA-MM-dif`). Outro formato → `404` |
| `GET /competencias/{competencia_id}` | `DetalheCompetencia` |
| `GET /competencias/{competencia_id}/arquivos/{anexo_id}` | Download de qualquer PDF da competência |
| `PUT /competencias/{id}/medicao` | `{ "itens": [{ "id", "quantidade_medida" }], "notas_empenho_ids": [...] }` |
| `POST /competencias/{id}/medicao/ciencia` | Minha ciência (uma por pessoa) |
| `POST /competencias/{id}/medicao/concluir` | `{ "notas_empenho_ids": [...] }` (igual à seleção salva) |
| `PUT /competencias/{id}/avaliacao/inicial` | `{ "respostas": [{ "item_id", "nota", "justificativa" }] }` |
| `PUT /competencias/{id}/avaliacao/gestor` | `{ "respostas": [...], "complemento": "…" }` |
| `PUT /competencias/{id}/avaliacao/assinaturas` | `{ "assinaturas": [{ "papel": "gestor" \| "fiscal_administrativo" \| "fiscal_tecnico", "usuario_id" }] }` |
| `POST /competencias/{id}/avaliacao/ciencia` | Ciência de quem foi indicado no ateste |
| `POST /competencias/{id}/avaliacao/pdf` | Gera o PDF (exige todas as ciências do ateste) |
| `POST /competencias/{id}/avaliacao/assinada` | `multipart` `arquivo`: via assinada pela contratada; conclui a etapa |
| `POST /competencias/{id}/avaliacao/reconsideracao` | `multipart` `arquivo`: justificativa da contratada; reabre a avaliação (uma vez) |
| `POST /competencias/{id}/nota-fiscal` | `multipart`: `arquivo`, `numero`, `recebida_em`, `prazo_pagamento_dias`, `origem_valor`, `valor_bruto`, `retencao_ir`, `retencao_inss`, `retencao_iss`, `retencao_pis`, `retencao_cofins`; adicional: `possui_adicional`, `arquivo_adicional`, `adicional_numero`, `adicional_valor_bruto` e as `adicional_retencao_*` |
| `POST /competencias/{id}/cadin` | `multipart`: `possui_pendencia`, `certidao`; com pendência: `pendencia`, `texto_notificacao` e `email` |
| `POST /competencias/{id}/checklist/{documento_id}` | `multipart` `arquivo` |
| `POST /competencias/{id}/checklist/concluir` | Conclui a etapa com os obrigatórios anexados. Falta de obrigatório → `400` com os nomes |
| `POST /competencias/{id}/consolidado` | Gera o documento consolidado |
| `POST /competencias/{id}/ordem-bancaria` | `multipart` `arquivo`: debita as NEs e conclui |
| `POST /competencias/{id}/reabrir` | `{ "etapa": "…", "justificativa": "…" }` (SuperRoot ou gestor vigente; demais → `403`) |

O `DetalheCompetencia` traz o `ResumoCompetencia` e mais:
- **Contrato e etapas:** `contrato_numero`, `etapas` (as etapas desta competência), `pode_editar`, `integra_equipe`, `liberada`.
- **Medição:**
  - `itens[]` (preço, fator, prevista, medida e subtotal), `total_previsto`, `total_medido`;
  - NEs: `notas_selecionadas`, `notas_disponiveis` (só as com saldo livre), cada uma com `saldo` e `saldo_livre`;
  - `avisos[]` (ex.: item sob demanda acima do saldo da vigência);
  - ciências: `ciencias`, `ciencias_minimas`;
  - `memorias[]` e `medicao_concluida_em`.
- **Avaliação e pagamento:**
  - `avaliacao`: definição, respostas, `nota_final`, `percentual_liberado`, assinaturas, PDFs e reconsideração;
  - `percentual_autorizado`, `valor_autorizado` (medido × %; sugestão do valor da NF) e `valor_a_pagar` (o que a OB debita: NF + NF adicional; antes da NF, o valor autorizado);
  - `reaberturas_permitidas` (o usuário pode reabrir etapas).
- **Nota fiscal:** `nota_fiscal` e `nota_fiscal_adicional` (número, arquivo, bruto, retenções, líquido), `nf_recebida_em`, `prazo_pagamento_dias`, `vencimento_pagamento`, `origem_valor_nf`, `nf_concluida_em`.
- **Demais etapas:** `consultas_cadin[]`, `documentos[]` (checklist mensal, com `obrigatorio`), `consolidado`, `ordem_bancaria`, `concluida_em`.

Os arquivos vêm no formato `{anexo_id, nome, tamanho, enviado_em}`.

Erros comuns: `400 invalido` (etapa errada, período não encerrado, ciências insuficientes, saldo de NE insuficiente, retenções inválidas, arquivo recusado), `403` e `404`.

## Consumo no Angular

`ExecucaoApiService` (`frontend/src/app/features/contratos/compartilhado/execucao-api.service.ts`):
- abas **Checklists**, **Formulários de avaliação** e **Execução** do detalhe;
- tela **`/contratos/:id/execucao/:identificador`** (etapas 1 a 7). A lista da aba Execução navega pelo `identificador` e exibe o `rotulo`.
