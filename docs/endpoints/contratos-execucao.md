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
  - **Retenção de tributos:** além de quem edita o contrato e do SuperRoot, o **Financeiro**: usuários do setor configurado em `SETOR_FINANCEIRO` (padrão "Diretoria de Orçamento e Finanças") e dos setores filhos — por serem **membros** do setor (em Setores) **ou** por terem um deles como **Departamento** no perfil. Precisam de ACL `contratos` ≥ `LEITURA`.
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
- **Etapas:** 1 `medicao` → 2 `avaliacao` (só com formulário) → 3 `nota_fiscal` → 4 `retencao` (retenção de tributos) → 5 `cadin` → 6 `checklist` → 7 `consolidado` → 8 `ordem_bancaria` → `concluida`. Competências que já tinham passado da nota fiscal antes da etapa de retenção existir ficaram com a retenção dada como conferida.
- **Etapas em paralelo:** depois da nota fiscal, **retenção, CADIN e checklist ficam abertos ao mesmo tempo** e podem ser concluídos em qualquer ordem (o Financeiro confere a retenção enquanto a equipe faz o CADIN e o checklist). O **documento consolidado só é liberado com as três concluídas**; antes disso, `400` com "Falta concluir: …". `etapa_atual` fica na primeira etapa paralela ainda aberta; use `etapas_abertas` e `etapas_concluidas` para saber o estado de cada uma.
  - Cada ação exige a competência na sua etapa (senão `400`).
  - A medição só é liberada depois do fim do período.
- **Medição:**
  - informa a quantidade medida de todos os itens (até 10 casas) e as NEs em **ordem de consumo**; o **saldo livre** somado dessas NEs deve cobrir o valor a pagar (saldo livre = saldo − o **comprometido** por outras competências com medição concluída e ainda não pagas);
  - nenhum item pode ser medido acima do **saldo líquido** (ver abaixo): `400` ao salvar e de novo ao concluir, porque uma glosa pode ser registrada depois de salva a medição;
  - qualquer alteração apaga as ciências;
  - a conclusão exige **ao menos uma ciência de integrante da equipe** (as demais são opcionais) e gera a memória de cálculo em PDF (nova versão só se os dados mudaram);
  - concluir soma o medido na quantidade executada dos itens;
  - **e-mail da medição concluída** (em segundo plano, pelo [servidor SMTP](smtp.md) ativo): vai à equipe vigente e aos prepostos ativos da contratada, com a memória de cálculo e o [diário de bordo](contratos-diario.md) do período em PDF, pedindo a emissão da nota fiscal com base na medição **em até 48 horas** (a data e a hora limite vão no texto). "Responder para" = equipe vigente (as respostas não voltam à caixa de envio). O resultado fica em `email_medicao`; `POST /competencias/{id}/reenviar-email-medicao` reenvia.

### Medição: saldo, glosas e saldo líquido

Cada item da medição traz:

| Coluna | Cálculo |
|---|---|
| **Saldo** | Contínuo: a quantidade **prevista** da competência (com pró-rata). Sob demanda: o que resta do item na vigência (limite − executado nas outras competências). Diferença de reajuste: a quantidade já medida (fixa) |
| **Glosas** | Soma das glosas do [diário de bordo](contratos-diario.md) com **data dentro do período** da competência (diferença de reajuste: nenhuma) |
| **Saldo líquido** | Saldo − glosas (mínimo 0): o **máximo que pode ser medido** |

A memória de cálculo em PDF mostra as mesmas colunas e, havendo glosas, a seção "Glosas do período".
- **Avaliação:**
  - nota da escala abaixo da máxima exige justificativa (inicial) ou complemento (gestor);
  - **avaliação do gestor só quando alguma nota inicial ficou abaixo da máxima** (`precisa_avaliacao_gestor`). Com todas na máxima, vale a nota inicial, e o `PUT /avaliacao/gestor` responde `400`. Salvar a avaliação inicial toda na máxima descarta uma avaliação do gestor feita antes;
  - nota final = **soma** das notas dos grupos, e em cada grupo Σ nota × peso / 100 (vale a nota do gestor, se houver) — igual à planilha oficial ("Somatório das notas totais dos grupos");
  - % liberado: pela nota, a faixa com mínimo ≤ nota ≤ máximo (entre várias, a de maior mínimo). Faixas com `notas_zero = N` também se aplicam quando algum grupo tem **ao menos N notas mínimas** da escala (a "nota 0" da planilha). Entre as faixas aplicáveis, vale a de **menor** percentual; nenhuma = 0%. Ex. da planilha: ≥ 6,75 → 100%; 5 a 6,74 ou 1 nota 0 num grupo → 90%; < 5 ou 2+ notas 0 num grupo → 75%;
  - fluxo: notas fechadas (inicial e, se preciso, a do gestor) → **ciências da equipe no ateste**, como na medição: qualquer integrante vigente, uma por pessoa, e **uma já libera o PDF** → PDF → via assinada pela contratada (conclui a etapa). Não há indicação de assinantes por papel. Mudar as notas apaga as ciências e o PDF gerado;
  - reconsideração: uma vez, antes da nota fiscal, reabre a avaliação.
- **Nota fiscal** (equipe): só os arquivos e as datas.
  - **PDF e XML obrigatórios** (principal e, se houver, adicional). O XML é lido automaticamente (NF-e modelo 55, NFS-e Padrão Nacional ou NFS-e da Prefeitura de São Paulo; ver [Leitura do XML](#leitura-do-xml)): **número, chave e valor bruto vêm do XML**, e as retenções informadas nele ficam como sugestão para a etapa seguinte;
  - data de recebimento e prazo de pagamento: vencimento = recebimento + prazo (dias corridos);
  - a mesma nota (chave) não pode ser juntada em outra competência (`400`); a adicional não pode ser a mesma da principal;
  - as duas notas são pagas pelas **mesmas NEs** apontadas na medição: o saldo livre delas precisa cobrir NF + NF adicional (brutos), senão `400`;
  - ao concluir, **e-mail ao Financeiro com cópia para a equipe** (Reply-To: equipe): assunto `Contrato NNN/AAAA - MM/AAAA - Nota fiscal anexada no sistema`; corpo "Foi juntada a nota fiscal para conferência de tributação pelo setor competente:" com o link direto para a etapa (`{URL_PUBLICA}/contratos/{id}/execucao/{identificador}?etapa=retencao`). Resultado em `email_nf`; `POST …/reenviar-email-nf` reenvia.
- **Retenção de tributos** (Financeiro, equipe ou SuperRoot):
  - a tela mostra a nota **renderizada a partir do XML** (emitente, tomador, número/série, emissão, competência, código do serviço, itens ou discriminação, totais) e as **conferências automáticas** (`ok` / `alerta` / `info`): emitente = empresa do contrato; tomador = SPI (`TOMADOR_CNPJ`, 96.480.850/0001-03); nota autorizada; valor da NF × valor autorizado da medição; competência da NFS-e × competência da execução; código do serviço (guia de ISS);
  - retenções IR, INSS, ISS, PIS, COFINS e **CSLL**, já preenchidas com os valores do XML: não negativas e com soma ≤ bruto; **líquido = bruto − retenções**;
  - é obrigatório confirmar que a **discriminação dos serviços é compatível** com o objeto;
  - ao salvar: gera o **PDF da retenção** (nota do XML + conferências + retenções + líquido + "conferido por … em …"), conclui a etapa e envia **e-mail à equipe** (assunto `Contrato NNN/AAAA - MM/AAAA - Retenções tributárias conferidas`, com o link da próxima etapa). Resultado em `email_retencao`; `POST …/reenviar-email-retencao` reenvia;
  - reabrir a nota fiscal (ou a retenção) desfaz a conferência; uma NF nova exige nova conferência.
  - o **Financeiro** vê as retenções a conferir em "Minhas pendências" do painel.
- **CADIN:** com pendência, exige descrição e e-mail de comunicação, e a etapa continua aberta; sem pendência, conclui.
- **Checklist:**
  - um PDF por documento;
  - cada documento é **obrigatório** ou **opcional** (`obrigatorio`, padrão `true`; os documentos anteriores a esta opção são obrigatórios);
  - a etapa conclui sozinha quando todos os documentos estão anexados;
  - com os obrigatórios anexados, `POST …/checklist/concluir` conclui a etapa mesmo com opcionais sem anexo.
- **Consolidado:** um PDF só.
  - **Quem gera:** a primeira geração é de quem pode editar o contrato. **Gerar novamente** (substituir o consolidado existente) é só do **gestor do contrato** (titular vigente) ou do **SuperRoot**, inclusive depois da OB, para refazer consolidados antigos. Os demais recebem `403`. `pode_gerar_consolidado_novamente` diz se o usuário vê o botão.
  - **Ordem de execução:** 1 medição (última memória de cálculo) → 2 avaliação (via assinada; sem ela, o relatório gerado), quando houver → 3 nota fiscal e NF adicional → 4 retenção de tributos (PDF gerado) → 5 CADIN (certidão e, se houver, e-mail de notificação, por consulta) → 6 documentos do checklist → 7 **resumo executivo, por último**, com a tabela "Composição deste documento" (nº, etapa, documento e páginas).
  - **Contracapa:** cada documento **enviado** (avaliação assinada, NFs, CADIN e checklist) vem precedido de uma página na identidade visual do sistema: "Documento N de M · etapa", nome do documento, arquivo, data de envio com o nome completo de quem enviou e dados da etapa. Um arquivo ausente ou ilegível fica só com a contracapa, que avisa que ele não foi incluído.
  - **Paginação sequencial:** todas as páginas levam "Página X de N". Nas páginas geradas pelo sistema, o número substitui o do rodapé original. Nos documentos enviados, entra num selo pequeno no canto inferior direito, e **o layout e a orientação do arquivo enviado são preservados**.
- **PDFs gerados pelo sistema:** todos em **A4 paisagem** (memórias, avaliação, retenção, parecer de prorrogação, relatórios, contracapas e resumo).
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
| `POST /competencias/{id}/medicao/concluir` | `{ "notas_empenho_ids": [...] }` (igual à seleção salva). Em segundo plano, envia o e-mail da medição |
| `POST /competencias/{id}/reenviar-email-medicao` | Reenvia o e-mail da medição concluída (quem pode editar o contrato) |
| `PUT /competencias/{id}/avaliacao/inicial` | `{ "respostas": [{ "item_id", "nota", "justificativa" }] }` |
| `PUT /competencias/{id}/avaliacao/gestor` | `{ "respostas": [...], "complemento": "…" }`. Só com nota inicial abaixo da máxima |
| `POST /competencias/{id}/avaliacao/ciencia` | Minha ciência no ateste (integrante vigente da equipe, uma por pessoa, depois das notas fechadas) |
| `POST /competencias/{id}/avaliacao/pdf` | Gera o PDF (exige ao menos uma ciência no ateste) |
| `POST /competencias/{id}/avaliacao/assinada` | `multipart` `arquivo`: via assinada pela contratada; conclui a etapa |
| `POST /competencias/{id}/avaliacao/reconsideracao` | `multipart` `arquivo`: justificativa da contratada; reabre a avaliação (uma vez) |
| `POST /competencias/{id}/nota-fiscal` | `multipart`: `arquivo` (PDF), `xml`, `recebida_em`, `prazo_pagamento_dias`; adicional: `possui_adicional`, `arquivo_adicional`, `xml_adicional`. Arquivos já enviados podem ser mantidos numa correção depois de reabrir |
| `POST /competencias/{id}/reenviar-email-nf` | Reenvia o e-mail da NF ao Financeiro (quem edita o contrato) |
| `PUT /competencias/{id}/retencao` | `{ "principal": {"ir","inss","iss","pis","cofins","csll"}, "adicional": {…} \| null, "discriminacao_conferida": true }` (Financeiro, equipe ou SuperRoot). Outro usuário → `403` |
| `POST /competencias/{id}/reenviar-email-retencao` | Reenvia o e-mail da retenção à equipe |
| `POST /competencias/{id}/cadin` | `multipart`: `possui_pendencia`, `certidao`; com pendência: `pendencia`, `texto_notificacao` e `email` |
| `POST /competencias/{id}/checklist/{documento_id}` | `multipart` `arquivo` |
| `POST /competencias/{id}/checklist/concluir` | Conclui a etapa com os obrigatórios anexados. Falta de obrigatório → `400` com os nomes |
| `POST /competencias/{id}/consolidado` | Gera o documento consolidado. Gerar novamente: só gestor do contrato ou SuperRoot (`403`), também após a OB |
| `POST /competencias/{id}/ordem-bancaria` | `multipart` `arquivo`: debita as NEs e conclui |
| `POST /competencias/{id}/reabrir` | `{ "etapa": "…", "justificativa": "…" }` (SuperRoot ou gestor vigente; demais → `403`) |

O `DetalheCompetencia` traz o `ResumoCompetencia` e mais:
- **Contrato e etapas:** `contrato_numero`, `etapas` (as etapas desta competência), `pode_editar`, `integra_equipe`, `pode_gerar_consolidado_novamente`, `liberada`.
- **Medição:**
  - `itens[]` (preço, fator, prevista, medida, subtotal, `saldo`, `glosas`, `saldo_liquido`), `total_previsto`, `total_medido`;
  - `glosas_periodo[]` (`ocorrencia_id`, `data_ocorrencia`, `descricao_ocorrencia`, `registrada_por_nome`, `item_id`, `descricao_item`, `quantidade`);
  - `email_medicao` (`enviado_em`, `ok`, `destinatarios[]`, `erro`);
  - NEs: `notas_selecionadas`, `notas_disponiveis` (só as com saldo livre), cada uma com `saldo` e `saldo_livre`;
  - `avisos[]` (ex.: item medido acima do saldo líquido por causa de uma glosa registrada depois);
  - ciências: `ciencias`, `ciencias_minimas` (hoje 1);
  - `memorias[]` e `medicao_concluida_em`.
- **Avaliação e pagamento:**
  - `avaliacao`: definição, respostas, `nota_final`, `percentual_liberado`, `precisa_avaliacao_gestor`, `ciencias` (mesmo formato das ciências da medição: `usuario_id`, `nome`, `papel`, `registrada_em`), PDFs e reconsideração;
  - `percentual_autorizado`, `valor_autorizado` (medido × %; sugestão do valor da NF) e `valor_a_pagar` (o que a OB debita: NF + NF adicional; antes da NF, o valor autorizado);
  - `reaberturas_permitidas` (o usuário pode reabrir etapas).
- **Nota fiscal:** `nota_fiscal` e `nota_fiscal_adicional` (número, `arquivo`, `xml`, `dados_xml`, `conferencias[]` com `descricao`/`situacao`/`detalhe`, bruto, retenções — `retencao_ir`, `_inss`, `_iss`, `_pis`, `_cofins`, `_csll` —, líquido), `nf_recebida_em`, `prazo_pagamento_dias`, `vencimento_pagamento`, `nf_concluida_em`, `email_nf`.
- **Retenção:** `retencao` (`concluida_em`, `por_nome`, `discriminacao_conferida`, `pdf`) ou `null`, `pode_conferir_retencao`, `email_retencao`.
- **Etapas:** `etapas_abertas` (aceitam gravação agora; depois da NF, até três ao mesmo tempo) e `etapas_concluidas`.
- **Demais etapas:** `consultas_cadin[]`, `documentos[]` (checklist mensal, com `obrigatorio`), `consolidado`, `ordem_bancaria`, `concluida_em`.

Os arquivos vêm no formato `{anexo_id, nome, tamanho, enviado_em}`.

Erros comuns: `400 invalido` (etapa errada, período não encerrado, ciências insuficientes, saldo de NE insuficiente, retenções inválidas, arquivo recusado), `403` e `404`.

## Consumo no Angular

`ExecucaoApiService` (`frontend/src/app/features/contratos/compartilhado/execucao-api.service.ts`):
- abas **Checklists**, **Formulários de avaliação** e **Execução** do detalhe;
- tela **`/contratos/:id/execucao/:identificador`** (etapas 1 a 8); `?etapa=retencao` (ou outra) abre direto na etapa — é o link dos e-mails. A lista da aba Execução navega pelo `identificador` e exibe o `rotulo`.

## Leitura do XML

`backend/app/services/contratos/leitor_nota_xml.py` detecta o formato e devolve os mesmos campos para todos
(`dados_xml`): `modelo` (`nfe`, `nfse_nacional`, `nfse_sp`), `modelo_rotulo`, `numero`, `serie`, `chave`,
`emissao`, `competencia`, `autorizada`, `situacao`, `emitente` e `tomador` (`cnpj`, `razao_social`,
`inscricao_municipal`), `valor_bruto`, `valor_liquido`, `codigo_servico`, `discriminacao`, `itens[]`
(`descricao`, `quantidade`, `valor_unitario`, `valor_total`), `retencoes` (`ir`, `inss`, `iss`, `pis`, `cofins`,
`csll`) e `informacoes_complementares`. Campo que o formato não tem vem `null` ("não informado na nota").

| Formato | Origem dos principais campos |
|---|---|
| NF-e (modelo 55, `http://www.portalfiscal.inf.br/nfe`) | `ide/nNF`, `serie`, `dhEmi`; `emit`/`dest`; `ICMSTot/vNF`; itens `det/prod`; retenções `retTrib` (vIRRF, vRetPrev, vRetPIS, vRetCOFINS, vRetCSLL) e `ISSQNtot/vISSRet`; autorização `protNFe/infProt` (cStat 100). Não tem competência; código de serviço só com grupo ISSQN |
| NFS-e Padrão Nacional (`http://www.sped.fazenda.gov.br/nfse`) | `nNFSe`, `DPS/infDPS` (`dhEmi`, `dCompet`, `toma`, `serv/cServ` — `cTribNac`, `xDescServ` —, `vServ`), `tribFed` (IRRF, CP, CSLL, PIS/COFINS retidos) e ISS retido (`tpRetISSQN` 2 ou 3), `vLiq` |
| NFS-e Prefeitura de São Paulo (`http://www.prefeitura.sp.gov.br/nfe`) | `ChaveNFe/NumeroNFe`, `DataEmissaoNFe`, `DataFatoGeradorNFe`, prestador/tomador, `ValorServicos`, `CodigoServico`, `Discriminacao`, `ValorIR/INSS/PIS/COFINS/CSLL`, `ValorISS` quando `ISSRetido` |

Segurança: XML com `DOCTYPE`/entidades é recusado e o limite é 5 MB. XML ilegível ou de outro tipo → `400`.
Configurações: `URL_PUBLICA` (links dos e-mails), `TOMADOR_CNPJ` e `SETOR_FINANCEIRO`.
