# Endpoints de servidores SMTP (`/api/smtp/servidores`)

Tag no OpenAPI: **Servidores SMTP**. Implementação: `backend/app/api/routes/smtp.py`. Regras em
`backend/app/services/servico_smtp.py`; conversa com o servidor em `cliente_smtp.py`.

## Finalidade

Configura por onde o portal **envia e-mail**, no mesmo molde dos [diretórios LDAP](ldap.md):
- cadastrar o servidor, a segurança da conexão, a conta de autenticação e o remetente;
- testar a conexão (conectar, negociar TLS e autenticar) com ou sem salvar;
- enviar um e-mail de teste de ponta a ponta;
- deixar um servidor **ativo**, usado pelos módulos que mandam e-mail (ex.: [diário de bordo e medição](contratos-diario.md))
  por meio de `servico_smtp.enviar_email(sessao, Mensagem(...))`. A `Mensagem` aceita texto, HTML, Cc, Cco,
  `responder_para` (substitui o "Responder para" do servidor naquela mensagem) e `anexos`
  (`AnexoEmail(nome, conteudo, tipo)`).

## Regras gerais

- **Autorização:** todos os endpoints exigem o papel **SuperRoot** (`403 acesso_negado` para os demais; `401` sem token).
- **Um servidor ativo por vez:** ativar um (`ativo: true`) desativa os demais. O banco também garante isso, com um índice único parcial.
- **Senha:** cifrada com Fernet (`CHAVE_CIFRA_LDAP`, a mesma chave dos segredos do LDAP) antes de ser gravada e **nunca devolvida** pela API; a resposta mostra só `possui_senha`. Se a chave for trocada, será preciso informar a senha de novo.
- **Sem autenticação:** `usuario` vazio conecta sem `AUTH` (relay interno); a senha gravada é descartada.
- **Segurança:** `starttls` (portas 587/25; sobe para TLS antes de autenticar), `ssl` (porta 465; conexão já cifrada) ou `nenhuma` (só em rede interna). O certificado do servidor é validado.
- **Auditoria:** `smtp.criar`, `smtp.alterar`, `smtp.excluir` e `smtp.enviar_teste`.

### Validações do cadastro

| Regra | Resposta |
|---|---|
| `nome`, `servidor` e `remetente_email` obrigatórios | `422` |
| `servidor` só com nome ou IP (sem `smtp://` e sem `:porta`) | `422` "informe só o nome ou IP do servidor" |
| `remetente_email` e `responder_para` com formato de e-mail | `422` "e-mail inválido" |
| `seguranca = ssl` na porta 587, ou `starttls` na 465 | `422` (combinações que nunca funcionam) |
| `usuario` preenchido sem senha (cadastro; na alteração, sem senha gravada) | `422` no cadastro, `400 invalido` na alteração |
| `tempo_limite_segundos` entre 3 e 120 | `422` |

### Mensagens de erro do teste e do envio

As falhas voltam com `sucesso: false` e uma `mensagem` em português que diz o que conferir: servidor
não encontrado (DNS), conexão recusada, tempo esgotado, falha de TLS/SSL (porta × segurança), usuário ou
senha recusados, remetente recusado, destinatário recusado. Dois casos do Microsoft 365 têm explicação
própria:
- **`5.7.139` / "SmtpClientAuthentication is disabled":** o SMTP autenticado está desligado para a caixa;
  o administrador do Microsoft 365 precisa habilitá-lo;
- **remetente recusado (`SendAsDenied`):** o remetente precisa ser a própria conta autenticada ou ter
  permissão "Enviar como".

## Schemas

### `LeituraServidorSmtp` (resposta)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | uuid | Identificador |
| `nome` | string | Nome de identificação (ex.: `Microsoft 365 — chamados`) |
| `servidor` | string | Endereço (ex.: `smtp.office365.com`) |
| `porta` | integer | 587, 465 ou 25 |
| `seguranca` | `starttls` \| `ssl` \| `nenhuma` | Segurança da conexão |
| `usuario` | string | Conta de autenticação (vazia = sem autenticação) |
| `possui_senha` | boolean | Se há senha gravada (o valor nunca é devolvido) |
| `remetente_email` | string | E-mail do remetente ("De") |
| `remetente_nome` | string | Nome exibido do remetente |
| `responder_para` | string | Endereço de resposta (Reply-To); vazio = o remetente |
| `tempo_limite_segundos` | integer | Espera máxima por resposta do servidor |
| `ativo` | boolean | Servidor usado pelo sistema para enviar e-mail |
| `ultimo_teste_em` / `ultimo_teste_ok` / `ultima_latencia_ms` / `ultimo_erro` | | Resultado do último teste de conexão |
| `ultimo_envio_em` / `ultimo_envio_ok` / `ultimo_envio_para` / `ultimo_envio_mensagem` | | Resultado do último e-mail de teste |
| `criado_em` / `atualizado_em` | datetime | Datas de registro |

### `CriacaoServidorSmtp` / `AlteracaoServidorSmtp` (requisição)

Os campos editáveis de `LeituraServidorSmtp` (`nome`, `servidor`, `porta`, `seguranca`, `usuario`,
`remetente_email`, `remetente_nome`, `responder_para`, `tempo_limite_segundos`, `ativo`) mais `senha`
(obrigatória no cadastro quando há `usuario`; na alteração, vazia ou ausente preserva a atual).

### `ResultadoSmtp` (resposta do teste e do envio)

| Campo | Tipo | Descrição |
|---|---|---|
| `sucesso` | boolean | Operação concluída |
| `latencia_ms` | integer | Tempo total, em ms |
| `mensagem` | string | Resumo ou erro traduzido |
| `id_mensagem` | string \| null | `Message-ID` do e-mail enviado (só no envio) |

## Endpoints

| Método e caminho | Descrição | Respostas |
|---|---|---|
| `GET /api/smtp/servidores` | Lista os servidores (ordem alfabética) | `200` `LeituraServidorSmtp[]` |
| `POST /api/smtp/servidores` | Cadastra (cifra a senha; ativo desativa os demais) | `201`, `422` |
| `POST /api/smtp/servidores/testar` | Testa uma configuração **não salva** (mesmo corpo do cadastro). Nada é gravado e nenhum e-mail é enviado | `200` `ResultadoSmtp` |
| `GET /api/smtp/servidores/{servidor_id}` | Consulta | `200`, `404` |
| `PUT /api/smtp/servidores/{servidor_id}` | Altera | `200`, `400 invalido`, `404`, `422` |
| `DELETE /api/smtp/servidores/{servidor_id}` | Exclui | `204`, `404` |
| `POST /api/smtp/servidores/{servidor_id}/testar` | Testa a configuração salva e grava o resultado. Corpo opcional `{"senha": "…"}` usa essa senha só no teste | `200` `ResultadoSmtp`, `404` |
| `POST /api/smtp/servidores/{servidor_id}/enviar-teste` | Envia um e-mail de teste. Corpo `{"destinatario": "fulano@sp.gov.br"}` | `200` `ResultadoSmtp`, `404`, `422` |

Exemplo de cadastro (Microsoft 365):

```json
{
  "nome": "Microsoft 365 — chamados",
  "servidor": "smtp.office365.com",
  "porta": 587,
  "seguranca": "starttls",
  "usuario": "chamados.spi@sp.gov.br",
  "senha": "…",
  "remetente_email": "chamados.spi@sp.gov.br",
  "remetente_nome": "Chamados SPI",
  "responder_para": "",
  "tempo_limite_segundos": 20,
  "ativo": true
}
```

## Consumo no Angular

- Tela **Administração > Servidores SMTP** (`/admin/smtp`), só para SuperRoot (`guardaPapel`), com item na barra lateral.
- Lista com situação, último teste e último envio; ações **Testar**, **Enviar teste** (pede o destinatário), **Editar** e **Excluir**.
- Formulário com **Testar sem salvar**; na edição, senha vazia preserva a atual.
