# Rascunhos de formulários (frontend)

Formulários longos guardam um **rascunho no navegador** enquanto a pessoa digita, para não perder o trabalho se a sessão vencer, a aba fechar ou ela precisar sair no meio (melhoria #22). Além disso, o botão **Salvar rascunho** guarda o rascunho **no servidor**, para a equipe ver e continuar (ver [contratos-rascunhos.md](endpoints/contratos-rascunhos.md)); os dois convivem: o automático protege quem digita, o do servidor compartilha.

- **Onde vale:** Diário de bordo (nova ocorrência), Avaliação dos serviços (notas, justificativas e complemento do gestor) e Medição do serviço (quantidades, acertos, despesas variáveis e NEs escolhidas).
- **Como funciona:** `RascunhoService` (`core/rascunho`) grava no `localStorage` a cada alteração (comparação a cada 2 s), na chave `sgi-spi.rascunho.<id do usuário>.<tela>:<contrato ou competência>`. O rascunho é **por usuário** (outra pessoa no mesmo computador não o vê), vale por **7 dias** e some ao salvar de verdade, ao esvaziar o formulário ou ao clicar em **Descartar rascunho**.
- **Ao voltar:** a tela restaura os campos e mostra "Rascunho restaurado (salvo em …)" com o botão **Descartar rascunho**. No Diário o formulário reabre sozinho.
- **Medição e Avaliação:** o rascunho só é restaurado se a medição ou avaliação **gravada no servidor continua a mesma** da época; se mudou (outra pessoa salvou), o rascunho velho é descartado.
- **Limites:** só campos de texto e números. **Arquivos anexados não são guardados** (no Diário, a pessoa anexa de novo). Não vale entre computadores nem navegadores.
- **Rascunho da equipe (botão):** aparece "Rascunho salvo por fulano em …" com **Carregar no formulário** e **Excluir rascunho**; quem só lê Contratos vê o aviso sem as ações. Salvar por cima de um rascunho que outra pessoa atualizou depois é recusado até a pessoa ver o novo.
