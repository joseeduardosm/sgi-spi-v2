# Manual: atualização de outubro/2026 (portaria de designação, Pagamentos, diário em PDF, Patrimônio, perfis de acesso)

Páginas do livro "SGI SPI" (https://instrucoes.spi.sp.gov.br) atualizadas ou criadas em 19/10/2026:

- **Contratos:** *Contratos: visão geral*, *Cadastro do contrato*, *Trilha de execução*, *Diário de bordo* (atualizadas) e *Equipe e portaria de designação* (nova).
- **Protocolo:** *Reservar um número e anexar o documento* (número de portaria e D.O.E.).
- **Patrimônio:** *Inservíveis e extraviados* e *Baixa de bens*.
- **Tarefas:** *Subtarefas e dependências*.
- **Controle de acesso (administração):** capítulo novo com *Perfis de acesso*.

`imagens/` e `legendas.json` têm os prints com setas numeradas (cada número é explicado numa lista abaixo da imagem). Todos os dados dos prints são fictícios (contrato 900/2026 – EXEMPLO).

## Como os prints foram gerados
`laboratorio/` cria uma cópia isolada do sistema (SQLite + build do Angular, nunca a produção): `reset.sh` recria o banco e sobe a API (8100) e o site (8200); `rodar*.py` percorrem as telas com o Playwright e desenham as setas (`cap.py`). Precisa do Chromium do Playwright e, se faltarem bibliotecas do sistema, de `LD_LIBRARY_PATH` apontando para os .deb extraídos (ver a memória do projeto).

## Como publicar
`publicar_final.py` (com `cabecalho_pub.py` e `textos_novos.py`) edita as páginas pela API do BookStack. Precisa de um token de API **temporário** em `token.txt` (`ID:SEGREDO`), que deve ser **revogado e apagado** depois. Não grave senhas nem tokens aqui. O script não é idempotente: rodar de novo duplica os trechos inseridos.
