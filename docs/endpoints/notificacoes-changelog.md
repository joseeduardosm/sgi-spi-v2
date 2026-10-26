# Notificações: e-mail de changelog (`/api/notificacoes/changelog`)

Tag no OpenAPI: **Notificações**. Implementação:
- rotas: `backend/app/api/routes/notificacoes_changelog.py`;
- regras: `backend/app/services/servico_changelog.py`;
- modelo: `backend/app/models/envio_changelog.py` (`notificacoes_envios_changelog`, migrações `7a3c5e9f1b2d` e `a1d3f5b7c9e2`).

Tela **Administração › Notificações** (`/admin/notificacoes-sistema`), exclusiva da **conta root** (login `LOGIN_ADMIN`, padrão `root`). Os SuperRoot e os demais usuários recebem `403 acesso_negado` e não veem o item na barra lateral. A caixa de notificações de cada usuário continua em [notificacoes.md](notificacoes.md).

## Finalidade

Avisar todos os usuários, por e-mail oficial (brasão, cabeçalho institucional, botão "Acessar o SGI SPI" e rodapé), das novidades do sistema registradas no `CHANGELOG.md` da raiz do projeto, sempre que a conta root quiser.

## Fluxo

1. **Rascunho** (`GET /changelog/rascunho`): junta as entradas do CHANGELOG (`## AAAA-MM-DD`; num título "A a B" vale a última data) **posteriores à última data já enviada a todos**. No primeiro envio, só a entrada mais recente.
   - As seções viram linguagem de usuário: Adicionado → "Novidades", Alterado → "Melhorias", Corrigido → "Correções".
   - Saem os detalhes técnicos: linhas de migração, endpoints e variáveis novas, e as crases.
   - Com mais de uma data, cada uma ganha o subtítulo "Atualização de dd/mm/aaaa".
2. **Edição:** assunto e texto são livres. O formato do texto:
   - `## Título` → subtítulo em vermelho;
   - `- item` → lista; dois espaços antes do hífen por nível de subitem;
   - `**negrito**`;
   - as demais linhas viram parágrafos (o HTML digitado é exibido como texto, nunca interpretado).
3. **Prévia** (`POST /changelog/previa`): o HTML do e-mail com o brasão embutido.
4. **Envio** (`POST /changelog/envios`), sem repetir endereço:
   - `teste`: só `email_teste`;
   - `selecionados`: 1 ou mais usuários (`usuarios_ids`) e/ou setores sistêmicos ou institucionais (`setores_ids`). Um setor inclui os membros, quem o tem como Departamento e os **setores filhos**. **Quem a administração escolhe recebe sempre** (ativo e com e-mail cadastrado), sem depender da preferência "Novidades do SGI SPI"; sem nenhum destinatário assim, `400`;
   - `todos`: usuários **ativos** com e-mail **que ligaram o e-mail de "Novidades do SGI SPI"** (evento `sistema.novidades`) nas Preferências. Ninguém começa com ele ligado: sem opt-in, não há destinatários (`400`).
   - Só usuários ativos e com e-mail recebem; a preferência de novidades só filtra o envio a `todos` (o `teste` continua indo para o endereço digitado). Sai **um e-mail por destinatário**, em segundo plano, pelo servidor SMTP ativo. Só os envios a todos avançam a data do próximo rascunho (`ate_data`).
   - **Agendar:** com `agendar_para` (data e hora com fuso, de 1 minuto a 1 ano à frente; não vale para `teste`) o envio fica `agendado` e **não avança** o próximo rascunho. A rotina `despachar` (a cada 2 minutos) envia o que venceu, **montando a lista de destinatários naquele momento** (`total` no registro é só uma estimativa); cada agendamento é reservado antes de sair e nunca sai duas vezes. Sem destinatários na hora, o envio termina sem nada enviado e o motivo vai em `erros`. Colunas novas (migração `d4f8b2a6c0e3`): `agendado_para`, `iniciado_em`, `cancelado_em`, `selecao`.
   - **Cancelar:** `DELETE /changelog/envios/{id}` enquanto estiver `agendado` (`204`; `404`; `409` se já saiu ou foi cancelado).
5. **Histórico** (`GET /changelog/envios`): os 30 últimos, com `situacao` (`agendado`, `enviando`, `concluido` ou `cancelado`), `agendado_para`, `enviados`, `falhas`, `erros` e `concluido_em` (nulo enquanto envia).

## Endpoints

Todos exigem `Authorization: Bearer <token>` da conta root.

| Método e caminho | Corpo | Resposta |
|---|---|---|
| `GET /api/notificacoes/changelog/rascunho` | — | `200 RascunhoChangelog` |
| `POST /api/notificacoes/changelog/previa` | `ConteudoChangelog` | `200 PreviaChangelog` |
| `POST /api/notificacoes/changelog/envios` | `PedidoEnvioChangelog` | `202 EnvioChangelogLeitura` |
| `GET /api/notificacoes/changelog/envios` | — | `200 EnvioChangelogLeitura[]` |
| `DELETE /api/notificacoes/changelog/envios/{envio_id}` | — | `204`; `404`; `409` |

**`RascunhoChangelog`:** `assunto` (ex.: `"SGI SPI – Novidades de 29/09/2026"`), `corpo`, `desde` (última data enviada a todos, ou `null`), `ate` (data mais recente incluída; `null` se não há novidade), `datas[]`, `total_destinatarios` (`total_destinatarios` = quem ligou o e-mail de novidades) e `setores[]` (`OpcaoSetorChangelog`: `id`, `nome`, `sistemico`, `nivel`; institucionais na ordem da hierarquia, depois os sistêmicos).

**`ConteudoChangelog`:** `assunto` (1–300) e `corpo` (1–50.000), sem aceitar só espaços.

**`PreviaChangelog`:** `html` (documento completo; o brasão vem como `data:image/png;base64,…` para exibir num `iframe`).

**`PedidoEnvioChangelog`:** `ConteudoChangelog` + `destino` (`"todos"`, `"selecionados"` ou `"teste"`), `email_teste` (obrigatório e válido em `teste`), `usuarios_ids` e `setores_ids` (em `selecionados`, ao menos um dos dois) e `ate_data` (o `ate` do rascunho; só vale em `todos`).

```json
{
  "assunto": "SGI SPI – Novidades de 29/09/2026",
  "corpo": "Olá!\n\n## Novidades\n- **Trilha clicável** em todas as telas.",
  "destino": "teste",
  "email_teste": "fulano@sp.gov.br",
  "ate_data": "2026-09-29"
}
```

**`EnvioChangelogLeitura`:** `id`, `assunto`, `corpo`, `destino`, `destino_descricao` (em `selecionados`: "usuários: …; setores: …"), `ate_data`, `total`, `enviados`, `falhas`, `erros` (um endereço por linha, com o motivo), `enviado_por_nome`, `criado_em`, `concluido_em`.

O envio é auditado como `notificacoes.changelog` (destino e total).

## Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `401` | `nao_autenticado` | Sem token ou token inválido |
| `400` | `invalido` | `selecionados` sem nenhum usuário ativo com e-mail na seleção |
| `403` | `acesso_negado` | Não é a conta root ("Somente a conta root tem acesso a este recurso.") |
| `422` | `validacao` | Assunto ou texto vazio, `destino` inválido, `email_teste` ausente ou inválido no teste, `selecionados` sem usuário nem setor |

Sem servidor SMTP ativo, o envio é registrado com todas as mensagens em `falhas` e o motivo em `erros`.

## Consumo no Angular (`features/administracao/notificacoes-sistema/`)

- **Acesso:** item "Notificações" em Administração (`somenteRoot: true`) e rota `/admin/notificacoes-sistema` com `guardaContaRoot`, ambos pelo `conta_root` de `GET /api/autenticacao/sessao`.
- **Tela:** botão "Preparar e-mail de changelog" e histórico (Enviando…/enviados/falhas; "Reabrir texto" carrega um envio anterior na janela).
- **Janela:** assunto e texto à esquerda, prévia à direita (atualizada 600 ms depois da digitação); rodapé com "Somente teste para [e-mail]" (padrão), "Usuários e setores escolhidos" (seletor de usuários com busca e lista de setores com busca, em duas seções: "Estrutura organizacional", em árvore, e "Grupos sistêmicos"; marcar ou desmarcar um setor pai vale para todos os filhos) ou "Quem ligou o e-mail de novidades (N usuários)". Em "escolhidos", a janela mostra quantos da seleção receberão (`POST /changelog/contagem`). Os envios a escolhidos e a todos pedem confirmação; o teste mantém a janela aberta para ajustes. O histórico mostra quem foi escolhido.
- **Serviço:** `notificacoes-sistema-api.service.ts`.
