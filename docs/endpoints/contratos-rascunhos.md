# Endpoints de rascunhos compartilhados do contrato (`/api/contratos/{contrato_id}/rascunhos`)

Tag no OpenAPI: **Contratos: rascunhos**. Implementação: `backend/app/api/routes/contratos/rascunhos.py` e `services/contratos/servico_rascunhos.py`.

Botão **Salvar rascunho** do Diário de bordo, da Avaliação e da Medição. O rascunho fica **no servidor**, visível à equipe, e é **adicional** ao rascunho automático que o navegador guarda sozinho (ver [rascunhos.md](../rascunhos.md)).

- **Um rascunho por tela e contrato:** `tipo` = `diario`, `avaliacao` ou `medicao`; nas duas últimas, `chave` = id da competência (no diário, vazio).
- **Quem vê:** qualquer pessoa com acesso a Contratos (ACL ≥ LEITURA). **Quem salva, carrega por cima e apaga:** quem pode editar o contrato (equipe vigente, criador ou SuperRoot, com ACL ≥ MODIFICACAO); os demais veem só o aviso "Rascunho salvo por fulano em …".
- **Versão:** cada gravação sobe `versao`. Quem grava informa a que viu; se outra pessoa salvou depois (ou a pessoa nunca viu o rascunho existente), `409` e a tela mostra o rascunho novo antes de qualquer sobrescrita.
- **Conteúdo:** só campos de texto e números (até 300 000 caracteres em JSON); **arquivos não entram**. O relato do diário (`descricao`) é sanitizado como o da ocorrência registrada.
- **Ciclo de vida:** a tela apaga o rascunho do servidor depois de registrar a ocorrência, salvar a avaliação (inicial ou do gestor) ou salvar a medição; também pode ser excluído à mão ("Excluir rascunho").
- **Auditoria:** `contrato.rascunho.salvar` e `contrato.rascunho.excluir`.
- **Migração:** `c9e5a1b7d3f8` (tabela `contratos_rascunhos`).

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/{tipo}?chave=` | Rascunho salvo (`LeituraRascunho`: `tipo`, `chave`, `dados`, `versao`, `atualizado_em`, `atualizado_por_id`, `atualizado_por_nome`) ou `null` |
| `PUT` | `/{tipo}?chave=` | Cria ou grava por cima. Corpo: `{"dados": {...}, "versao": 2}` (`versao` = a que a pessoa viu; `null` se não havia). `409` se mudou; `400` se grande demais; `404` para competência que não é do contrato; `403` sem permissão de editar |
| `DELETE` | `/{tipo}?chave=` | Apaga (`204`); `404` se não há rascunho; `403` sem permissão de editar |

`tipo` fora de `diario`, `avaliacao` e `medicao` responde `422`.
