# Endpoints de prorrogação, reajuste e aditamento/supressão (`/api/contratos/{contrato_id}/…`)

Tags no OpenAPI: **Contratos: prorrogação**, **Contratos: reajuste** e **Contratos: aditamento e supressão**.

Implementação:
- rotas: `backend/app/api/routes/contratos/alteracoes.py`;
- serviços: `servico_prorrogacao.py`, `servico_vigencia_retroativa.py`, `servico_reajuste.py` e `servico_alteracao.py`, em `backend/app/services/contratos/`.

## Regras gerais

- **Autorização:** leitura com ACL `contratos` ≥ `LEITURA`; gravação exige poder editar o contrato; ciências de integrantes vigentes da equipe e, para efeito de teste, do SuperRoot (papel `administrador`).
- Cada processo é um **rascunho** até a conclusão. Só a conclusão altera o contrato.
- **Auditoria:** `contrato.prorrogacao.*`, `contrato.vigencia_retroativa.*`, `contrato.reajuste.*`, `contrato.aditamento.*` e `contrato.supressao.*`.

---

## Vigência retroativa

> **Na tela**, antes de gravar, o botão "Cadastrar vigência retroativa" abre duas confirmações em sequência: uma de **10 segundos** que explica todos os impactos (início do contrato recua, vigências renumeradas, competências de época, empenhos, checklists e reajustes da época, termo nos documentos importantes, prazos que não mudam e o que o desfazer exige) e, depois de lida, outra de **3 segundos** ("Tem certeza que deseja continuar?"). Só então a API é chamada.

Vigência **anterior ao início do contrato**, cadastrada com o seu termo para poder voltar no tempo (reajuste retroativo). Tag: **Contratos: prorrogação**.

- **Cadastro:**
  - `multipart`: `meses` (1 a 120), `assinada_em`, `numero_termo` (opcional) e `termo` (PDF);
  - a nova vigência **termina na véspera do início atual** do contrato e começa `meses` antes; as retroativas formam uma cadeia contínua;
  - `contratos.data_inicio` **recua** para o início da retroativa mais antiga; as datas iniciais do contrato ficam travadas, como depois de uma prorrogação;
  - as vigências são **renumeradas** em ordem de início (a retroativa mais antiga é a 1ª; a original e as prorrogações sobem). A renumeração atualiza competências, linhas de medição, reajustes, aditamentos/supressões e previsões;
  - o termo vira documento importante (024, 025…);
  - com competências já geradas, exige checklist ativo.
- **O que a vigência retroativa é:** uma vigência completa. Gera competências (medição, checklist, NEs, avaliação da qualidade) como qualquer outra, mas **não conta** no prazo máximo nem nas prorrogações (o prazo inicial e a vigência máxima continuam contados a partir da vigência original), não tem itens sob demanda planejados (a previsão dela não é exigida para gerar a execução) e **não tem parecer**.
- **Desfazer:** só a retroativa mais antiga e somente sem medição registrada e sem reajuste ou aditamento/supressão (não cancelados) nela. Apaga as competências e a previsão da vigência, devolve o início anterior ao contrato e renumera as demais.

| Método e caminho | Descrição |
|---|---|
| `GET /vigencias-retroativas` | `LeituraVigenciaRetroativa[]`: `id`, `sequencia`, `meses`, `assinada_em`, `numero_termo`, `data_inicio`, `data_fim`, `codigo_documento`, `termo`, `reajustada`, `pode_desfazer`, `motivo_bloqueio` |
| `POST /vigencias-retroativas` | `multipart`; devolve a lista atualizada. `400` para prazo inválido ou sem checklist ativo (com competências) |
| `DELETE /vigencias-retroativas/{vigencia_id}` | Desfaz a mais antiga; devolve a lista (`400` se houver medição, reajuste ou aditamento) |
| `GET /prorrogacoes/arquivos/{anexo_id}` | Também baixa o termo de uma vigência retroativa |

---

## Prorrogação

> **Fluxo da tela (para frente):** 1 Meses → 2 Meses quebrados (só se houver) → 3 Itens sob demanda (só se houver) → 4 Memória de cálculo → 5 Checklist → 6 Termo e registro; depois, o pós-assinatura. **Minutas, enquadramento (Parecer Referencial) e parecer saíram da tela**; as rotas e os dados deles continuam (as prorrogações antigas guardam enquadramento e parecer). Migração `c3e5a7b9d2f4`.

- **Meses quebrados:** mês em que a nova vigência começa ou termina no meio (ex.: início em 15/01 ou fim em 14/01). `GET /prorrogacao` traz em `memoria.meses_quebrados[]` cada um (`competencia`, `inicio`, `fim`, `dias` 30/360) com o valor dos itens contínuos nas duas opções (`pro_rata` e `integral`), e `memoria.total_pro_rata`/`total_integral` da nova vigência inteira. A escolha é **uma só** e vai em `calculo_mes_quebrado` no `PUT /prorrogacao` (`pro_rata`: só os dias da nova vigência; `integral`: o mês inteiro; nulo mantém). Vale para todos os itens contínuos e **só para a memória e o valor da prorrogação**: a execução continua seguindo o faturamento de cada item. Sem escolha, `memoria.precisa_escolher = true`.
- **Memória de cálculo** (`services/contratos/memoria_prorrogacao.py`): a nova vigência ainda não existe no contrato, então a conta é feita mês a mês sobre os meses que ela vai cobrir — contínuos: quantidade mensal × preço vigente no início do mês × fator (1 nos meses cheios; nos quebrados, pela escolha); sob demanda: quantidade planejada do mês (`plano_sob_demanda`) × preço. `memoria` traz `meses[]` (`competencia`, `inicio`, `fim`, `quebrado`, `continuos`, `sob_demanda`, `total`), `totais_por_ano[]` e `total`. `POST /prorrogacao/memoria/arquivos` gera o **PDF** (capa "Prorrogação de dd/mm/aaaa a dd/mm/aaaa", meses quebrados, tabela executiva mês a mês, "Total para AAAA" e "Total da nova vigência") e o **XLSX** (abas "Memória" e "Por ano"); versão nova só quando os dados mudam (hash); `400` sem prazo ou com mês quebrado sem escolha. `memorias[]` lista as versões e `memoria_atualizada` diz se a última corresponde aos dados de agora. A mesma conta alimenta `valorprorrogacao` e `valoresporexercicio` das minutas (antes o rascunho calculava R$ 0, porque procurava a vigência ainda não registrada).
- **Checklist da prorrogação:** modelo global do tipo **`checklist_prorrogacao`** (Contratos → Modelos → **Checklist Prorrogação**; `itens` com `nome`, `observacao`, `obrigatorio`; **um ativo por vez**, `409` para o segundo; SuperRoot ou controle total em Contratos). Ao criar o rascunho, os itens do modelo ativo são copiados para `checklist[]` (sem modelo ativo, começa vazio). É um **ponto de partida**: `POST /prorrogacao/checklist/incluir` (`multipart`: `nome`, `descricao`, `arquivo` PDF) inclui documento fora do modelo, **sempre opcional**; `DELETE /prorrogacao/checklist/{id}` exclui só os incluídos (`400` nos do modelo); `POST /prorrogacao/checklist/{id}` (`multipart` `arquivo`) anexa ou substitui o PDF. `obrigatorios_pendentes` conta os obrigatórios sem PDF. Os arquivos (checklist e memória) baixam por `GET /prorrogacoes/arquivos/{anexo_id}`.
- **Registro** passa a exigir, além do que já exigia: escolha dos meses quebrados (se houver), **memória gerada com os dados atuais** e **obrigatórios do checklist anexados** (`400` dizendo o que falta). A tela gera a memória sozinha antes de registrar se ela estiver desatualizada.
- **Parecer no `PUT /prorrogacao`:** os seis campos do parecer passaram a ser opcionais; campo não enviado mantém o gravado (a tela nova não os envia).

- **Prazo:**
  - obrigatório;
  - a soma das vigências não passa da vigência máxima (`meses_disponiveis`);
  - a nova vigência começa no dia seguinte ao fim da atual.
- **Itens sob demanda (opcional):**
  - regras de limite: `saldo_remanescente` (limite atual − executado na vigência), `repetir_inicial` (quantidade original) ou `manual`;
  - nenhum limite passa da quantidade original (para ampliar o objeto, registre aditamento);
  - a grade mensal da nova vigência não passa do limite.
- **Parecer (opcional):**
  - seis campos: `avaliacao_geral`, `resumo_qualidade`, `historico_ocorrencias`, `reclamacoes`, `atendimento_chamados` e `parecer`;
  - o **PDF só é emitido se algum campo estiver preenchido**;
  - as ciências são opcionais e aparecem no PDF;
  - **editar o parecer apaga as ciências** (a tela confirma antes).
- **Registro:**
  - `multipart`: `assinada_em`, `numero_termo` (opcional) e `termo` (PDF);
  - cria a nova vigência e anexa o termo aos documentos importantes (024, 025…);
  - grava a previsão sob demanda da nova vigência, já selada;
  - zera o valor global reajustado (a nova vigência usa os preços atuais).
- Com competências já geradas, prorrogar exige checklist ativo.
- **Desfazer:**
  - só a última prorrogação;
  - depois de gerada a execução da nova vigência, quem edita o contrato (equipe, criador, controle total ou SuperRoot) pode desfazer, e somente sem medição registrada e sem reajuste ou aditamento na vigência.

| Método e caminho | Descrição |
|---|---|
| `GET /prorrogacao` | `LeituraProcessoProrrogacao`: rascunho (ou valores iniciais), nova vigência calculada, `meses_disponiveis`, itens sob demanda com `saldo_remanescente`, parecer, ciências e `relatorio` |
| `PUT /prorrogacao` | `{ "meses", "regra_sob_demanda", "plano_sob_demanda": [{ "item_id", "limite", "apontamentos": { "2027-01-01": "10" } }], …campos do parecer }` |
| `DELETE /prorrogacao` | Descarta o rascunho |
| `POST /prorrogacao/ciencia` | Minha ciência no parecer |
| `POST /prorrogacao/parecer` | Emite o PDF do parecer (`400` se nenhum campo estiver preenchido) |
| `GET /prorrogacao/minutas` | `LeituraMinutas`: os documentos do processo (`documentos`: `variante`, `titulo`, `modelo_ativo`, `lacunas`) e os dados que os completam (`campos`: `nome`, `rotulo`, `descricao`, `digitado`, `multilinha`, `valor`, `calculado`). Exige leitura em Contratos |
| `GET /prorrogacao/minutas/{variante}` | `LeituraMinuta`: `html` preenchido (pronto para copiar para o SEI) e `lacunas`. `404` se a variante não existe ou não há modelo ativo da variante |
| `PUT /prorrogacao/dados-minuta` | `{ "dados": { "testemunhaanome": "…", "dotacao": "…" } }`: substitui o conjunto de dados digitados (texto vazio apaga). Cria o rascunho se ainda não existir. `400` para nome desconhecido ou condicional. Exige modificação |
| `GET /prorrogacao/enquadramento` | `LeituraEnquadramento`: os 37 itens do checklist do Parecer Referencial em 9 grupos (`numero`, `texto`, `referencia`, `automatica`, `resposta`, `doc`, `obs`, `efetivo`, `contestado`), `total`, `atendidos`, `nao_atendidos`, `pendentes`, `precisa_analise_juridica` e `motivos` |
| `PUT /prorrogacao/enquadramento` | `{ "respostas": { "3": { "resposta": "sim", "doc": "doc. nº 99, p. 2", "obs": "" } } }` (`resposta`: `sim`, `nao`, `na` ou vazio): substitui as respostas; cria o rascunho se não existir. `400` para item fora de 1–37 |
| `GET /prorrogacao/enquadramento/planilha` | XLSX no formato do Modelo 6 da SPI, com respostas, documentos e observações |
| `POST /prorrogacao/registrar` | Registra; devolve `LeituraProrrogacao[]` (com `precisa_analise_juridica`) |
| `GET /prorrogacoes/arquivos/{anexo_id}` | Download do termo ou do parecer (de prorrogação registrada ou do rascunho) |
| `GET /prorrogacoes` | Histórico: `id`, `meses`, `assinada_em`, `numero_termo`, `fim_anterior`, `data_inicio`, `data_fim`, `codigo_documento`, `termo`, `relatorio`, `pode_desfazer` |
| `PUT /prorrogacoes/{prorrogacao_id}/pos-assinatura` | `{ "pncp_publicado_em", "pncp_numero", "doe_publicado_em", "garantia_comprovada_em", "garantia_enviada_dof_em", "contratos_gov_atualizado_em", "dados_garantia": { "responsavel_nome": "…" } }`: substitui o que havia e devolve `LeituraProrrogacao[]`. `400` para data anterior à assinatura ou chave desconhecida em `dados_garantia`. Exige modificação |
| `GET /prorrogacoes/{prorrogacao_id}/garantia/planilha` | XLSX de dados de garantia para a DOF (Modelo 9: caução em dinheiro; Modelo 10: demais modalidades). `400` se o contrato não tem garantia cadastrada |
| `DELETE /prorrogacoes/{prorrogacao_id}` | Desfaz a última |

### Minutas e despachos da prorrogação

O SGI escreve os documentos do processo da prorrogação (**texto formatado para colar no SEI**, com o botão "Copiar o texto formatado", como a portaria e o despacho de pagamento). Os textos vêm dos **modelos** do tipo `prorrogacao` (**Contratos → Modelos → Prorrogação**; SuperRoot ou controle total em Contratos; **uma máscara ativa por variante**, a segunda responde `409`). A migração `a4c8e2f6b0d3` semeia os sete modelos padrão, tirados de `apoio/Prorrogações` já corrigidos.

| Variante | Documento |
|---|---|
| `minuta_aditivo` | Minuta do Termo de Aditamento (Anexo I do Parecer Referencial) |
| `termo_ciencia` | Termo de Ciência e de Notificação (TCE-SP) |
| `declaracao_atendimento_licitacao` | Declaração de Atendimento, Anexo II (contrato de licitação) |
| `declaracao_atendimento_direta` | Declaração de Atendimento, Anexo III (dispensa ou inexigibilidade) |
| `declaracao_tce` | Declaração de documentos à disposição do TCE-SP |
| `despacho_instrucao` | Despacho CCC/DGA → SSGC |
| `despacho_autorizacao` | Despacho de autorização da autoridade competente |

- **Declaração certa:** vem da `modalidade_contratacao` do contrato (licitação → Anexo II; dispensa ou inexigibilidade → Anexo III). Sem modalidade cadastrada, as duas aparecem.
- **Placeholders** (`GET /api/contratos/modelos/prorrogacao/placeholders`, lista fechada, `#nome`, `#nome#` ou `##nome##`; qualquer outro `#...` responde `400`):
  - **do SGI:** contrato, empresa, endereço, representante legal (preposto marcado), processo de gestão, vigência inicial, `nrotermo` (próximo da sequência), nova vigência (`mesesprorrogacao`, `inicioprorrogacao`, `fimprorrogacao`), valor da prorrogação (`valorprorrogacao`, extenso e `valoresporexercicio`, calculados pelos preços vigentes), modalidade, `prazopncp` (20 ou 10 dias úteis, dos Parâmetros de Contratos), gestor e as autoridades dos Parâmetros (SSGC, Secretário, autoridade competente);
  - **digitados** (testemunhas, base da representação, dotação, nota de empenho e de reserva, períodos de repactuação, nº dos documentos do SEI…): guardados em `contratos_prorrogacoes_processos.dados_minuta` (JSON);
  - **condicionais** (`#secustosnaorenovaveis`, `#sedemandavariavel`, `#serepactuacao`): o parágrafo com o marcador só aparece se a condição valer (custos não renováveis: há data de efeito digitada; demanda variável: há item sob demanda; repactuação: há períodos digitados).
- **Precedência:** o que foi digitado vale mais do que o calculado, para qualquer placeholder (assim um valor calculado errado se corrige na tela sem mexer no cadastro).
- **Lacunas:** placeholder sem valor **não some**: vira `[rótulo]` no texto e entra em `lacunas`. Os valores são escapados.
- **Auditoria:** `contrato.prorrogacao.minutas` (quais dados foram gravados).

### Enquadramento no Parecer Referencial

Checklist de 37 itens (Modelo 6 da SPI, `services/contratos/catalogo_parecer_referencial.py`; planilha-modelo em `backend/app/recursos/prorrogacao/`). Respostas no rascunho (`contratos_prorrogacoes_processos.enquadramento`) e, no registro, uma **fotografia** em `contratos_prorrogacoes.enquadramento` (respostas, o que valia em cada item, `precisa_juridico`, `motivos`); migração `b5d9f3a7c1e4`.

- **O que vale em cada item:** a resposta da equipe; sem ela, a **conferência automática** (com a conta em `automatica.explicacao`); sem nenhuma, pendente. `contestado` = a equipe respondeu o contrário do SGI.
- **Conferências automáticas:** item 1 (contrato anterior a 01/04/2021 → `nao`); 3 (vigência ainda em curso; vigência expirada → `nao`); 5 (prazo ≤ vigência inicial); 8 (Parecer dentro da validade, parâmetro `parecer_referencial_vigencia_ate`); 14 (vigência total ≤ 120 meses, art. 107); 27 e 28 (`na` se o contrato não exige garantia); 29 a 31 (`na` se veio de licitação). Os demais itens são declarados pela CCC.
- **Aviso:** qualquer item que vale `nao` liga `precisa_analise_juridica` ("o caso sai do Parecer Referencial e precisa de análise da Consultoria Jurídica"). **Não bloqueia** o registro; fica na prorrogação registrada (`LeituraProrrogacao.precisa_analise_juridica`) e na auditoria `contrato.prorrogacao.registrar`.
- **Auditoria:** `contrato.prorrogacao.enquadramento` (contagem de atendidos, não atendidos e pendentes).

### Pós-assinatura: PNCP, DOE e garantia

Depois do registro, a tela da prorrogação acompanha o que falta para o aditivo produzir efeitos (migração `c6e0a4b8d2f5`; serviço `servico_pos_assinatura.py`).

- **Prazo do PNCP:** a divulgação é **condição de eficácia**. `pncp_prazo_ate` = data de assinatura + **20 dias úteis** (licitação) ou **10** (dispensa e inexigibilidade), nos Parâmetros de Contratos (`pncp_dias_uteis_licitacao`, `pncp_dias_uteis_direta`), contados com os feriados do RH. Fica **vazio** se o contrato não tem modalidade cadastrada (`situacao_pncp = sem_prazo`).
- **Situação (`situacao_pncp`):** `publicado` (há `pncp_publicado_em`), `no_prazo` (com `dias_uteis_pncp` restantes), `vencido` ou `sem_prazo`.
- **Garantia:** `garantia_pendente` = o contrato exige garantia e `garantia_comprovada_em` está vazio. O texto-modelo do contrato trata a garantia **depois** da assinatura; o Parecer (§61) pede **antes**: o SGI só registra a data, a CCC decide.
- **Planilhas de garantia:** preenchidas com contrato, empresa, valor da vigência original e da prorrogação (pelos preços vigentes), garantia cadastrada e os dados digitados em `dados_garantia` (`responsavel_nome`, `responsavel_email`, `responsavel_fone`, `ultima_nl`, `forma_prestacao`, `meio_prestacao`, `dare`, `valor_complemento`, `data_pagamento`, `endosso_numero`, `endosso_valor`, `endosso_vigencia`). Modelos originais em `backend/app/recursos/prorrogacao/`.
- **Lembretes** (job diário `lembretes`, uma vez cada, para a equipe): quando faltam `aviso_pncp_dias_uteis` (5) dias úteis ou menos para o PNCP; quando o prazo vence; e quando passaram 5 dias úteis da assinatura sem a garantia comprovada. Eventos `contratos.pncp_prazo` e `contratos.garantia_pendente` (Preferências de notificação). O aviso some quando a publicação é registrada (o job só avisa o que está pendente).
- **Auditoria:** `contrato.prorrogacao.pos_assinatura` (campos alterados).
- Prorrogações registradas **antes** desta entrega não têm prazo calculado (`sem_prazo`); as datas podem ser preenchidas à mão.

## Reajuste

- **Memória de cálculo mês a mês:** (o PDF começa cada parte em página nova: identificação, itens, cada mês medido e a memória executiva) além da folha de itens (novo preço do objeto), o PDF e o XLSX de cada versão trazem **uma seção (no XLSX, uma aba) por mês medido**, com a OB paga ou aguardando (o título indica qual), da vigência reajustada a partir do mês da data de efeito (mês anterior ao efeito não entra: foi faturado antes de o reajuste valer): `item | descrição | tipo · SIAFÍSICO · CATMAT/CATSER | qtd | valor unit. (pago) | valor unit. reajustado | diferença +/− | valor pago | valor reajustado | em haver`, com o subtotal do mês; mês que atravessa a data de efeito mostra a quantidade já multiplicada pela fração dos dias com o novo preço (30/360). **Mês pago = competência com a OB concluída; o mês medido que aguarda a OB também entra, identificado como tal.** No fim, a **memória de cálculo executiva**: uma linha por mês medido (`mês | OB | valor pago | valor reajustado | em haver`) e o **Total em haver**, igual à diferença retroativa. No reajuste retroativo não há meses pagos: só o resumo "nada em haver". A versão nova nasce quando muda qualquer item, quantidade, preço pago ou OB concluída (hash de origem). Em elaboração, `GET …/reajustes` traz `resumo_meses` (`meses[]` com `paga`, `valor_pago`, `valor_reajustado`, `em_haver`; `total_em_haver`; `meses_quebrados[]`, `diferenca_pro_rata`, `diferenca_integral`, `calculo_mes_quebrado`, `precisa_escolher`); `total_em_haver = diferenca_retroativa`. A tela mostra a tabela "Meses medidos (em haver)", com a situação da OB de cada mês.
- **Meses quebrados (pro rata × integral):** mês medido que contém a data de efeito entra em `resumo_meses.meses_quebrados[]` (`competencia` `AAAA-MM`, `rotulo`, `periodo_inicio`, `periodo_fim`) com as **duas opções já calculadas** em `opcoes.pro_rata` e `opcoes.integral`: cada uma traz, por item, os `trechos[]` (`inicio`, `fim`, `dias` 30/360, `reajustado`, `quantidade`, `valor_unitario`, `valor`), o `valor_pago`, o `devido` e o `em_haver`, e os totais do mês. **Pro rata:** os dias antes do efeito com o valor sem reajuste e os dias a partir dele com o reajustado (ex.: efeito 15/11 → 01 a 14/11 e 15 a 30/11). **Integral:** o mês inteiro com o valor reajustado. `diferenca_pro_rata` e `diferenca_integral` dão a diferença retroativa inteira em cada opção. A escolha é **uma só** para todos os meses quebrados e todos os itens do reajuste (inclusive os de faturamento sempre integral) e vai em `calculo_mes_quebrado` (`pro_rata` ou `integral`) no corpo da memória; enquanto não houver escolha, o cálculo usa pro rata, `precisa_escolher` é `true` e `POST …/memoria/arquivos` responde `400`. O mês do **fim da vigência** já vem medido só até o último dia dela, então as duas opções param ali; numa prorrogação, os dias seguintes são da vigência nova e entram no reajuste dela. Na **virada de vigência** não há escolha: cada reajuste cobre só o trecho da sua vigência. O PDF e o XLSX trazem a seção/aba **Meses quebrados** com a opção escolhida e a memória período a período.
- Um reajuste em elaboração por vez (`409`). Cada vigência é reajustada **uma vez** (o reajuste comum e o retroativo contam à parte). **Todas as vigências, inclusive as retroativas, podem receber o reajuste comum** (preço novo a partir de uma data de efeito dentro da vigência; as competências já medidas a partir dela geram a diferença e a memória mês a mês); o reajuste retroativo continua à parte, só para vigência retroativa, na ordem da mais recente para a mais antiga.
- **Abertura:** vigência + **data de efeito** (`data_efeito`: a partir de que dia os novos preços valem, qualquer dia da vigência; o `mes_referencia`, dia 1 do mês dessa data, é derivado e continua aceito no corpo como forma antiga). Os itens são fotografados com o preço vigente naquele dia.
- **Mês da virada (reajuste ou prorrogação no meio do mês):** o mês continua sendo **uma competência e uma medição só**; cada item aparece **uma vez por trecho do mês**, com o preço do trecho e a quantidade pelos **dias** de cada um (fator 30/360, todos os itens, inclusive os "sempre integral"). Ex.: reajuste a partir de 20/09 → "01/09 a 19/09 · preço anterior" (19/30) e "20/09 a 30/09 · preço reajustado" (11/30). Uma só memória de cálculo, com os dois trechos.  Vale para **qualquer periodicidade**: uma prorrogação nunca corta a competência (ex.: num contrato trimestral prorrogado em 20/01, a competência jan–mar é uma só, com um trecho até 19/01 e outro de 20/01 a 31/03).
- **Memória:**
  - por item, um `indice_percentual` **independente**, em pontos percentuais:
    - **positivo** reajusta (`2` = +2%);
    - **negativo** dá desconto (`-3` = −3%);
    - `0` mantém o preço.
  - Aceita de −100 (exclusive, o preço não pode zerar) a 1000, com até 8 casas. Fora disso: `422`.
  - A tela tem "Aplicar a todos", que preenche o mesmo percentual em todos os itens antes de salvar. Na API, basta enviar o mesmo valor em cada item.
  - `valor_referencial` é opcional e funciona como teto do novo preço (útil no reajuste positivo);
  - novo preço = preço × (1 + índice/100), com **4 casas** (como o preço unitário); o valor referencial (teto) também aceita até 4 casas;
  - totais: base atual × nova base; valor global atual × novo valor global, ambos somados mês a mês (ver [contratos-cadastro.md](contratos-cadastro.md)), com os preços reajustados a partir do mês de referência — inclusive nos meses já medidos, que serão pagos pela competência de diferença.
- **Evidência:** um único PDF para o reajuste, mesmo com percentuais diferentes por item.
- **Arquivos da memória:** PDF + XLSX versionados; nova versão só se os dados mudaram.
  - Mostram o percentual com sinal e a variação (novo − atual) de cada item.
  - Os totais trazem o destino da diferença das competências já medidas.
- **Conclusão:**
  - exige a evidência do índice, a memória gerada e o apostilamento assinado;
  - atualiza o preço dos itens e **refaz as linhas** das competências ainda não medidas a partir do mês de referência (com a divisão em trechos, se a data cair no meio do mês), e grava o novo valor global;
  - as competências já medidas mantêm os preços antigos (fotografia);
  - **competências já medidas da vigência:** calcula-se a **diferença retroativa líquida** = Σ quantidade medida × (preço novo − preço pago), gravada em `diferenca_retroativa`. Entram **todos os meses medidos da vigência**, inclusive os anteriores ao mês de referência (eles foram faturados no preço antigo e nenhum outro reajuste os alcança), desde que ainda não cobertos por um reajuste anterior (`diferenca_coberta_por_reajuste_id`). Meses de outras vigências ficam de fora.
    - **Mês cortado em trechos** (virada de vigência ou data de efeito): item **sempre integral** não se divide e entra inteiro, somando todos os trechos; item **pró-rata** entra só pelos trechos da **vigência deste reajuste** — o trecho da vigência anterior é regido pelo reajuste dela. Quando o mês inteiro antecede a data de efeito, o corte veio da virada de vigência e o trecho foi faturado no preço antigo, então a diferença cobre o trecho todo; quando o mês contém a data de efeito, só valem os trechos a partir dela.
    - **Positiva:** é gerada uma competência `diferenca_reajuste` (identificador `AAAA-MM-dif`) com a medição já preenchida e o checklist copiado.
      - Por item, entra a quantidade medida e o preço unitário da diferença; num reajuste misto, os itens com desconto entram com preço negativo, e o total é o líquido.
      - Ela segue o fluxo normal da execução (NEs, NF, OB), sem avaliação.
    - **Negativa (desconto):** não há competência de diferença. O valor vira um **crédito da SPI**, abatido no valor autorizado da **próxima competência regular com a medição aberta** (tabela `contratos_abatimentos_reajuste`).
      - Se o crédito passar do valor da medição (medido × % da avaliação), abate o que cabe, e o restante segue para a competência seguinte. O ajuste é feito ao concluir a medição e de novo ao concluir a avaliação.
      - Reabrir a medição devolve as sobras ainda não usadas.
      - Sem competência a medir, o crédito fica **pendente** e é vinculado à primeira competência criada depois (por exemplo, ao gerar a execução de uma prorrogação).
      - Na execução, o desconto aparece em `desconto_reajuste` / `descontos_reajuste` (ver [contratos-execucao.md](contratos-execucao.md)).
    - **Zero:** nada é gerado.

### Reajuste retroativo

Volta no tempo: define os preços de uma **vigência retroativa** a partir dos da vigência seguinte. Abre-se com `"retroativo": true` e a vigência retroativa em `sequencia_vigencia` (`data_efeito` não é informada: é o **início da vigência seguinte**).

- **Ordem:** da vigência retroativa mais recente para a mais antiga, uma por vez (`vigencias_retroativas_disponiveis` traz a próxima). Cada vigência tem um reajuste retroativo.
- **Cálculo:** `valor_unitario_atual` é o preço vigente no início da vigência seguinte; o preço da retroativa é **deflacionado**: `atual ÷ (1 + índice/100)`, com 4 casas. O `valor_referencial`, quando informado, é o **piso** (no reajuste comum é o teto). O índice precisa ser maior que −100%.
- **Efeito:** valores só mudam na vigência retroativa (até a véspera da data de efeito); o preço do cadastro e o valor global do contrato não mudam. O mesmo cálculo mês a mês dos totais simula os preços novos na vigência retroativa.
- **Sem diferença retroativa:** só é permitido enquanto a vigência retroativa **não tem competência com medição concluída** (`400` ao abrir ou concluir). Competências abertas dela são refeitas com os preços novos na conclusão.
- A evidência do índice, a memória de cálculo e o apostilamento seguem as mesmas exigências do reajuste comum.

| Método e caminho | Descrição |
|---|---|
| `GET /reajustes` | `PainelReajuste`: `em_andamento`, `vigencias_disponiveis` (sem as retroativas), `vigencias_retroativas_disponiveis`, `historico`, `pode_editar` |
| `POST /reajustes` | `{ "sequencia_vigencia": 1, "data_efeito": "2026-05-20" }` → `201` (ou, na forma antiga, `"mes_referencia": "2026-05-01"`; data fora da vigência → `400`). Retroativo: `{ "sequencia_vigencia": 1, "retroativo": true }` |
| `POST /reajustes/{id}/evidencia` | `multipart` `arquivo` |
| `PUT /reajustes/{id}/memoria` | `{ "itens": [{ "item_id", "indice_percentual", "valor_referencial" }], "calculo_mes_quebrado": "pro_rata" }` (`calculo_mes_quebrado` opcional: nulo mantém a escolha; `400` se não há mês quebrado) |
| `POST /reajustes/{id}/memoria/previa` | Calculadora ao vivo: mesmo corpo do `PUT …/memoria`, mas **não grava**; devolve o reajuste como ficaria (novos preços, base, valor global, `diferenca_retroativa`, `resumo_meses`). A tela chama enquanto a pessoa digita o índice (o botão Salvar memória só é preciso para gravar e gerar os arquivos). `400` se o reajuste não está em elaboração, o item não pertence a ele ou `calculo_mes_quebrado` veio sem haver mês quebrado |
| `POST /reajustes/{id}/memoria/arquivos` | Gera PDF e XLSX. `400` (`invalido`) se há mês quebrado e `calculo_mes_quebrado` ainda não foi escolhido |

Os arquivos só criam **versão nova** quando muda algo da memória (itens, índices, meses pagos) ou o **formato** do arquivo (`FORMATO_MEMORIA`): mudou o layout, a próxima geração sai com o layout novo.
| `POST /reajustes/{id}/concluir` | `multipart` `arquivo` (apostilamento) |
| `POST /reajustes/{id}/cancelar` | Cancela |
| `GET /reajustes/{id}/arquivos/{anexo_id}` | Download |

`LeituraReajuste` traz:
- **Identificação:** `situacao`, `retroativo`, a vigência, a `data_efeito` e o `mes_referencia`;
- **Efeito:**
  - `competencias_recalculadas`;
  - `competencias_com_diferenca` (competências medidas que entram na diferença);
  - `competencia_diferenca` (`identificador` `AAAA-MM-dif` da competência gerada, após a conclusão);
- **Diferença retroativa:**
  - `diferenca_retroativa` (string decimal com sinal: prévia no rascunho, valor gravado depois de concluído);
  - `competencia_credito` (rascunho com desconto: rótulo `MM/AAAA` da competência que receberá o crédito, ou nulo);
  - `abatimentos[]` (`competencia`, `identificador`, `medida`, `valor`: onde o crédito foi ou será abatido);
  - `credito_pendente` (parte ainda sem competência);
- **Itens:** `itens[]` (atual, índice, referencial, reajustado, subtotal);
- **Totais:** `base_atual`, `base_reajustada`, `valor_global_atual`, `valor_global_reajustado`;
- **Arquivos:** `evidencia`, `apostilamento` e `memorias[]` (`versao`, `pdf`, `xlsx`).

## Aditamento / supressão

- Uma alteração em andamento por vez (`409`). Abertura: `tipo` (`aditamento`/`supressao`), vigência e mês de efeito.
- **Aba 1:** a justificativa técnica em PDF libera os quantitativos.
- **Aba 2:** nova quantidade por item.
  - Contínuo: nova quantidade mensal.
  - Sob demanda: novo limite da vigência.
  - Aditamento: não diminui. Supressão: não aumenta e não fica abaixo do executado.
  - Impacto em R$: contínuo = Σ, mês a mês a partir do mês de efeito, Δ × preço do mês × fator 30/360 (se o item calcula pró-rata); sob demanda = Δ × preço.
  - Impacto em % sobre o valor da vigência.
  - Acumulado do mesmo tipo na vigência **acima de 25%** exige a autorização do Ordenador de Despesa.
  - Salvar envia para ciência e apaga as ciências anteriores.
- **Aba 3:** ciências (**uma ciência de integrante da equipe já basta**); depois dela, a memória em PDF e XLSX e a formalização são liberadas.
- **Aba 4:**
  - De Acordo da contratada, que libera o documento consolidado;
  - Termo Aditivo assinado;
  - conclusão, que aplica as quantidades (contínuo: quantidade mensal; sob demanda: limite da vigência) e recalcula a prevista das competências ainda não medidas.

| Método e caminho | Descrição |
|---|---|
| `GET /alteracoes` | `PainelAlteracao`: `em_andamento`, `vigencias`, `historico`, `pode_editar`, `integra_equipe` |
| `POST /alteracoes` | `{ "tipo", "sequencia_vigencia", "mes_efeito" }` → `201` |
| `POST /alteracoes/{id}/documentos/{tipo}` | `tipo`: `justificativa`, `autorizacao`, `de_acordo`, `termo` (`multipart` `arquivo`) |
| `PUT /alteracoes/{id}/quantitativos` | `{ "itens": [{ "item_id", "quantidade_nova" }] }` |
| `POST /alteracoes/{id}/ciencia` | Minha ciência |
| `POST /alteracoes/{id}/memoria` | Gera PDF e XLSX (exige ao menos uma ciência) |
| `POST /alteracoes/{id}/consolidado` | Justificativa + autorização + memória + De Acordo |
| `POST /alteracoes/{id}/concluir` | Aplica a alteração |
| `POST /alteracoes/{id}/cancelar` | Cancela |
| `GET /alteracoes/{id}/arquivos/{anexo_id}` | Download |

`LeituraAlteracao` traz:
- **Identificação:** `tipo`, `situacao`, a vigência, `mes_efeito` e `meses_restantes`;
- **Itens:** `itens[]` (original, executado, nova, impacto, `abaixo_do_executado`);
- **Valores:** `valor_global_original`, `impacto_valor`, `impacto_percentual`, `acumulado_percentual`, `exige_autorizacao`;
- **Documentos:** os anexos;
- **Ciências:** `ciencias` e `ciencias_minimas` (hoje 1: uma ciência já libera a memória e a formalização).

## Consumo no Angular

`AlteracoesApiService` (`frontend/src/app/features/contratos/compartilhado/alteracoes-api.service.ts`). Telas:
- `/contratos/:id/prorrogacao`;
- `/contratos/:id/reajuste`;
- `/contratos/:id/aditamento` e `/contratos/:id/supressao`.
