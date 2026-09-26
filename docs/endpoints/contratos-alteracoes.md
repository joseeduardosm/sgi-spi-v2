# Endpoints de prorrogação, reajuste e aditamento/supressão (`/api/contratos/{contrato_id}/…`)

Tags no OpenAPI: **Contratos: prorrogação**, **Contratos: reajuste** e **Contratos: aditamento e supressão**.

Implementação:
- rotas: `backend/app/api/routes/contratos/alteracoes.py`;
- serviços: `servico_prorrogacao.py`, `servico_reajuste.py` e `servico_alteracao.py`, em `backend/app/services/contratos/`.

## Regras gerais

- **Autorização:** leitura com ACL `contratos` ≥ `LEITURA`; gravação exige poder editar o contrato; ciências só de integrantes vigentes da equipe.
- Cada processo é um **rascunho** até a conclusão. Só a conclusão altera o contrato.
- **Auditoria:** `contrato.prorrogacao.*`, `contrato.reajuste.*`, `contrato.aditamento.*` e `contrato.supressao.*`.

---

## Prorrogação

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
  - depois de gerada a execução da nova vigência, só o SuperRoot pode desfazer, e somente sem medição registrada e sem reajuste ou aditamento na vigência.

| Método e caminho | Descrição |
|---|---|
| `GET /prorrogacao` | `LeituraProcessoProrrogacao`: rascunho (ou valores iniciais), nova vigência calculada, `meses_disponiveis`, itens sob demanda com `saldo_remanescente`, parecer, ciências e `relatorio` |
| `PUT /prorrogacao` | `{ "meses", "regra_sob_demanda", "plano_sob_demanda": [{ "item_id", "limite", "apontamentos": { "2027-01-01": "10" } }], …campos do parecer }` |
| `DELETE /prorrogacao` | Descarta o rascunho |
| `POST /prorrogacao/ciencia` | Minha ciência no parecer |
| `POST /prorrogacao/parecer` | Emite o PDF do parecer (`400` se nenhum campo estiver preenchido) |
| `POST /prorrogacao/registrar` | Registra; devolve `LeituraProrrogacao[]` |
| `GET /prorrogacoes/arquivos/{anexo_id}` | Download do termo ou do parecer (de prorrogação registrada ou do rascunho) |
| `GET /prorrogacoes` | Histórico: `id`, `meses`, `assinada_em`, `numero_termo`, `fim_anterior`, `data_inicio`, `data_fim`, `codigo_documento`, `termo`, `relatorio`, `pode_desfazer` |
| `DELETE /prorrogacoes/{prorrogacao_id}` | Desfaz a última |

## Reajuste

- Um reajuste em elaboração por vez (`409`). Cada vigência é reajustada **uma vez**.
- **Abertura:** vigência + mês de referência (primeiro mês com os novos preços). Os itens são fotografados com o preço vigente naquele mês.
- **Memória:**
  - por item, `indice_percentual` (2 = 2%) e `valor_referencial` opcional, que funciona como teto;
  - preço reajustado = preço × (1 + índice/100), com 2 casas;
  - totais: base atual × nova base; valor global atual × novo valor global, ambos somados mês a mês (ver [contratos-cadastro.md](contratos-cadastro.md)), com os preços reajustados a partir do mês de referência — inclusive nos meses já medidos, que serão pagos pela competência de diferença.
- **Arquivos da memória:** PDF + XLSX versionados; nova versão só se os dados mudaram.
- **Conclusão:**
  - exige a evidência do índice, a memória gerada e o apostilamento assinado;
  - atualiza o preço dos itens e as competências ainda não medidas a partir do mês de referência, e grava o novo valor global;
  - as competências já medidas mantêm os preços antigos (fotografia);
  - **reajuste retroativo:** se houver competências medidas a partir do mês de referência, é gerada uma competência `diferenca_reajuste` (identificador `AAAA-MM-dif`) com, por item, a quantidade medida × (preço novo − preço pago), a medição já preenchida e o checklist copiado. Ela segue o fluxo normal da execução (NEs, NF, OB), sem avaliação.

| Método e caminho | Descrição |
|---|---|
| `GET /reajustes` | `PainelReajuste`: `em_andamento`, `vigencias_disponiveis`, `historico`, `pode_editar` |
| `POST /reajustes` | `{ "sequencia_vigencia": 1, "mes_referencia": "2026-05-01" }` → `201` |
| `POST /reajustes/{id}/evidencia` | `multipart` `arquivo` |
| `PUT /reajustes/{id}/memoria` | `{ "itens": [{ "item_id", "indice_percentual", "valor_referencial" }] }` |
| `POST /reajustes/{id}/memoria/arquivos` | Gera PDF e XLSX |
| `POST /reajustes/{id}/concluir` | `multipart` `arquivo` (apostilamento) |
| `POST /reajustes/{id}/cancelar` | Cancela |
| `GET /reajustes/{id}/arquivos/{anexo_id}` | Download |

`LeituraReajuste` traz:
- **Identificação:** `situacao`, a vigência e o `mes_referencia`;
- **Efeito:** `competencias_recalculadas`, `competencias_com_diferenca` (competências medidas que entram na diferença) e `competencia_diferenca` (`identificador` `AAAA-MM-dif` da competência gerada, após a conclusão);
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
