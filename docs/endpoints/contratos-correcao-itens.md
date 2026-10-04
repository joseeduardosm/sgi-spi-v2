# Contratos: correção de itens depois de geradas as competências (`/api/contratos/{id}/itens/…`)

Tag no OpenAPI: **Contratos: correção de itens**. Implementação:
- rotas: `backend/app/api/routes/contratos/correcoes.py`; schemas: `backend/app/schemas/contratos/correcoes.py`;
- regras: `backend/app/services/contratos/servico_correcao_itens.py` e, em `servico_competencias.py`, `sincronizar_competencia`, `sincronizar_abertas` e `sincronizar_se_defasada`;
- modelos: `backend/app/models/contratos/correcoes.py` (`contratos_correcoes_itens`, `contratos_itens_historico`), `Contrato.versao_cadastro` e `Competencia.versao_cadastro_sincronizada` (migrações `dd7999d97284` e `5bf9f2139d6e`).

## Princípio

Os itens do contrato são **independentes das execuções**: as competências **abertas** (medição ainda não concluída) **acompanham o cadastro** dos itens; ao **concluir a medição** a competência congela e vira histórico (nunca mais muda). Por isso corrigir um preço ou uma quantidade no cadastro atualiza só as competências abertas, **preservando a quantidade medida** já digitada. Competências migradas do SGI que não seguem o calendário atual não são sincronizadas.

`Contrato.versao_cadastro` sobe a cada mudança de item; cada competência aberta guarda a versão com que foi calculada e, antes de qualquer escrita nela (salvar medição, ciência, concluir), alinha-se ao cadastro se estiver para trás. Se a sincronização mudar valores, a **ciência** não é registrada na hora (`400`: recarregue e confira) e a conclusão exige ciências novas.

## Quem pode

| Ação | Quem |
|---|---|
| Propor, pré-visualizar | Gestor titular vigente ou SuperRoot |
| Confirmar ou recusar | **Outra pessoa** (nunca o autor) com permissão de edição no contrato, ou o SuperRoot |
| Cancelar | O autor (ou o SuperRoot), enquanto pendente |
| Ler (lista e histórico) | ACL `contratos` ≥ LEITURA |

**Dois olhos:** toda correção só vale depois de confirmada por quem não a propôs. A alteração direta de itens pelo SuperRoot no cadastro do contrato também sobe a versão, grava o histórico e sincroniza as abertas.

## Endpoints

| Método e caminho | Descrição |
|---|---|
| `GET /correcoes` | `ListaCorrecoes`: `pode_propor` e as propostas (`pode_decidir`, `pode_cancelar` por proposta) |
| `GET /historico` | Cada mudança de item: quem, quando, motivo, `campos` (de → para) e `versao_cadastro` |
| `POST /correcoes/previa` | `{ justificativa, itens: [{ id, valor_unitario?, quantidade_mensal?, quantidade_total?, unidade_fornecimento?, codigo_* ? }] }` → `Previa`: competências abertas afetadas, variação do valor previsto, quantas congeladas não mudam e avisos. **Não grava** |
| `POST /correcoes` | Mesmo corpo → `201 LeituraCorrecao` pendente; avisa a equipe (mensagem e e-mail). Justificativa com ao menos 20 caracteres (`422`); nada mudou (`400`) |
| `POST /correcoes/{id}/confirmar` | Grava o cadastro, sobe `versao_cadastro`, registra o histórico, sincroniza as abertas, invalida as ciências das que mudaram e avisa. `403` para o autor; `409` se o cadastro mudou depois da proposta ou se já foi decidida |
| `POST /correcoes/{id}/recusar` | `{ motivo }`; mesmas regras de quem confirma |
| `POST /correcoes/{id}/cancelar` | Só o autor ou o SuperRoot |

## Regras de validação
- **Preço de item já reajustado** é recusado (`400`): o preço vem do reajuste; use o reajuste ou a repactuação.
- **Quantidade de item já aditado ou suprimido** é recusada: use um novo aditamento ou supressão.
- Descrição, tipo e faturamento (pró-rata) continuam imutáveis. Contínuo exige quantidade mensal > 0; sob demanda, quantidade total > 0; a quantidade total de item contínuo é calculada.

## Competências concluídas
Nunca mudam. Para corrigir preço ou quantidade medida de competência já medida, reabra a medição (antes da Ordem Bancária) ou use os instrumentos de diferença (reajuste/repactuação e ajuste de competência concluída, previstos nas próximas fases).

**Auditoria:** `contrato.itens.correcao.propor|confirmar|recusar|cancelar`.
