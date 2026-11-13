# Tornar sem efeito (`/api/contratos/{contrato_id}/{tipo}/{registro_id}/sem-efeito`)

Tag no OpenAPI: **Contratos: tornar sem efeito**. Implementação: `backend/app/api/routes/contratos/alteracoes.py` e `backend/app/services/contratos/servico_sem_efeito.py`.

Desfaz o que um evento **já concluído** aplicou ao contrato e grava a situação `sem_efeito`, com quem fez, quando e o motivo. Decisões do usuário (13/11/2026):
- qualquer evento pode ser desfeito, **desde que nenhum outro dependa dele**;
- **bloqueia** se a competência de diferença já tem medição ou nota fiscal, se o crédito do desconto já foi aplicado numa medição ou se algum mês já foi **medido com o preço (ou a quantidade) novo**: é preciso reabrir antes;
- quem pode é a **equipe do contrato** (quem edita: equipe vigente, criador, Controle total ou SuperRoot), sempre com **motivo**;
- o evento continua no histórico com o selo **"Sem efeito"**; os documentos ficam guardados.

---

## `POST /api/contratos/{contrato_id}/{tipo}/{registro_id}/sem-efeito`

- **Autorização:** ACL `contratos` ≥ MODIFICACAO e poder editar o contrato.
- **`tipo`:** `reajustes`, `repactuacoes`, `alteracoes` (aditamento/supressão), `prorrogacoes` ou `vigencias-retroativas`.

### Requisição: `GravacaoSemEfeito`

| Campo | Tipo | Obrigatório | Regras | Descrição |
|---|---|---|---|---|
| `motivo` | string | sim | 10 a 4000 caracteres | Por que o evento perde o efeito (vai para o histórico e para a auditoria) |

```json
{ "motivo": "Índice aplicado por engano no processo" }
```

### Resposta `204 No Content`

A tela recarrega o painel do evento e o contrato.

### O que é desfeito

| Evento | O que volta |
|---|---|
| Reajuste | Preço do cadastro volta ao de antes (se o reajuste era da vigência atual); competências regulares ainda não medidas são realinhadas; a competência de diferença (automática e a complementar da diferença manual) é excluída; o crédito no fundo é excluído; os meses da diferença manual destravam; meses marcados como "diferença acertada por este reajuste" deixam de estar; o valor global reajustado é refeito pela linha do tempo (ou fica vazio se não sobrar reajuste/repactuação valendo na vigência atual) |
| Repactuação | A diferença somada no preço de cada item sai; o resto como no reajuste. A CCT continua nos Documentos importantes |
| Aditamento / supressão | Quantidade mensal (contínuo, vigência atual) e limite da previsão (sob demanda) voltam às originais; as quantidades previstas das competências não medidas são refeitas; o impacto sai do valor global reajustado |
| Prorrogação | O mesmo "desfazer" de sempre (só a última; apaga a vigência criada e devolve o fim anterior). O processo da prorrogação fica com a situação `sem_efeito` e o motivo |
| Vigência retroativa | O mesmo "desfazer" de sempre (só a mais antiga). O motivo fica na auditoria |

Auditoria: `contrato.<tipo>.sem_efeito` (`reajuste`, `repactuacao`, `aditamento`, `supressao`) com `registro_id`, `motivo` e o de/para (`precos`, `quantidades`, `competencias_excluidas`, `campos.valor_global_reajustado`); na prorrogação e na vigência retroativa, `contrato.prorrogacao.desfazer` e `contrato.vigencia_retroativa.desfazer` com `motivo`. O aviso "concluído" da equipe sai da caixa de notificações.

### Bloqueios (`409`, motivo em `detalhe`)

- Há reajuste ou repactuação **concluído depois** deste (partiu do preço dele); no aditamento/supressão, outro aditamento/supressão concluído depois na mesma vigência ou um reajuste/repactuação concluído depois.
- Há **prorrogação registrada depois** do evento, ou **correção de itens aplicada depois**.
- A competência de diferença já tem medição iniciada, medição concluída ou nota fiscal, ou saiu da etapa de medição.
- O crédito do desconto retroativo já foi aplicado numa medição.
- Alguma competência a partir do efeito foi **medida depois da conclusão** (com o preço ou a quantidade nova).
- O evento não está concluído (rascunho, cancelado ou já sem efeito).

Prorrogação e vigência retroativa seguem as regras do desfazer delas e respondem `400` quando não podem.

### Outras respostas

- `400`: regra violada (prorrogação/vigência retroativa); `403`: sem permissão; `404`: contrato, tipo ou registro inexistente; `422`: motivo ausente ou curto.

### Nos painéis de cada evento

`LeituraReajuste`, `LeituraRepactuacao` e `LeituraAlteracao` ganham a situação `sem_efeito` e os campos `sem_efeito_em`, `sem_efeito_por`, `sem_efeito_motivo`, `pode_tornar_sem_efeito` (botão ativo) e `motivo_bloqueio` (por que não pode). `LeituraProrrogacao` ganha `motivo_bloqueio` (só na última).
