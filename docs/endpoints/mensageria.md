# Mensageria: e-mail de changelog (`/api/mensageria`)

Tag no OpenAPI: **Mensageria**. Implementação:
- rotas: `backend/app/api/routes/mensageria.py`;
- regras: `backend/app/services/servico_changelog.py`;
- modelo: `backend/app/models/envio_changelog.py` (`mensageria_envios_changelog`, migrações `7a3c5e9f1b2d` e `a1d3f5b7c9e2`).

Tela **Administração › Mensageria** (`/admin/mensageria`), exclusiva da **conta root** (login `LOGIN_ADMIN`, padrão `root`). Os SuperRoot e os demais usuários recebem `403 acesso_negado` e não veem o item na barra lateral. A caixa de mensagens de cada usuário continua em [mensagens.md](mensagens.md).

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
   - `selecionados`: 1 ou mais usuários (`usuarios_ids`) e/ou setores sistêmicos ou institucionais (`setores_ids`). Um setor inclui os membros, quem o tem como Departamento e os **setores filhos**;
   - `todos`: usuários **ativos** com e-mail.
   - Só usuários ativos com e-mail recebem. Sai **um e-mail por destinatário**, em segundo plano, pelo servidor SMTP ativo. Só os envios a todos avançam a data do próximo rascunho (`ate_data`).
5. **Histórico** (`GET /changelog/envios`): os 30 últimos, com `enviados`, `falhas`, `erros` e `concluido_em` (nulo enquanto envia).

## Endpoints

Todos exigem `Authorization: Bearer <token>` da conta root.

| Método e caminho | Corpo | Resposta |
|---|---|---|
| `GET /api/mensageria/changelog/rascunho` | — | `200 RascunhoChangelog` |
| `POST /api/mensageria/changelog/previa` | `ConteudoChangelog` | `200 PreviaChangelog` |
| `POST /api/mensageria/changelog/envios` | `PedidoEnvioChangelog` | `202 EnvioChangelogLeitura` |
| `GET /api/mensageria/changelog/envios` | — | `200 EnvioChangelogLeitura[]` |

**`RascunhoChangelog`:** `assunto` (ex.: `"SGI SPI – Novidades de 29/09/2026"`), `corpo`, `desde` (última data enviada a todos, ou `null`), `ate` (data mais recente incluída; `null` se não há novidade), `datas[]`, `total_destinatarios` e `setores[]` (`OpcaoSetorChangelog`: `id`, `nome`, `sistemico`, `nivel`; institucionais na ordem da hierarquia, depois os sistêmicos).

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

O envio é auditado como `mensageria.changelog` (destino e total).

## Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `401` | `nao_autenticado` | Sem token ou token inválido |
| `400` | `invalido` | `selecionados` sem nenhum usuário ativo com e-mail na seleção |
| `403` | `acesso_negado` | Não é a conta root ("Somente a conta root tem acesso a este recurso.") |
| `422` | `validacao` | Assunto ou texto vazio, `destino` inválido, `email_teste` ausente ou inválido no teste, `selecionados` sem usuário nem setor |

Sem servidor SMTP ativo, o envio é registrado com todas as mensagens em `falhas` e o motivo em `erros`.

## Consumo no Angular (`features/administracao/mensageria/`)

- **Acesso:** item "Mensageria" em Administração (`somenteRoot: true`) e rota `/admin/mensageria` com `guardaContaRoot`, ambos pelo `conta_root` de `GET /api/autenticacao/sessao`.
- **Tela:** botão "Preparar e-mail de changelog" e histórico (Enviando…/enviados/falhas; "Reabrir texto" carrega um envio anterior na janela).
- **Janela:** assunto e texto à esquerda, prévia à direita (atualizada 600 ms depois da digitação); rodapé com "Somente teste para [e-mail]" (padrão), "Usuários e setores escolhidos" (seletor de usuários com busca e lista de setores com busca, sistêmicos marcados) ou "Todos os usuários ativos (N)". Os envios a escolhidos e a todos pedem confirmação; o teste mantém a janela aberta para ajustes. O histórico mostra quem foi escolhido.
- **Serviço:** `mensageria-api.service.ts`.
