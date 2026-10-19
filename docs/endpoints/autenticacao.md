# Endpoints de autenticação (`/api/autenticacao`)

Tag no OpenAPI: **Autenticação**. Implementação: `backend/app/api/routes/autenticacao.py`.

Todos os endpoints desta página funcionam **mesmo com o perfil institucional pendente**.

---

## `POST /api/autenticacao/login`

Valida login e senha e emite um token JWT de acesso. Com um diretório LDAP ativo, tenta primeiro a autenticação corporativa. Se ela falhar ou o diretório estiver indisponível, tenta a conta local. Ver [autenticacao.md](../autenticacao.md#fluxo-de-login).

- **Autorização:** pública.

### Requisição: `RequisicaoLogin`

| Campo | Tipo | Obrigatório | Regras | Descrição |
|---|---|---|---|---|
| `login` | string | sim | 1 a 150 caracteres | Login local, `sAMAccountName` ou `userPrincipalName` |
| `senha` | string | sim | 1 a 128 caracteres | Senha |

```json
{ "login": "root", "senha": "<senha>" }
```

### Resposta `200 OK`: `RespostaToken`

| Campo | Tipo | Descrição |
|---|---|---|
| `token_acesso` | string | JWT para o cabeçalho `Authorization: Bearer <token>` |
| `tipo_token` | string | Sempre `bearer` |
| `expira_em_segundos` | integer | Validade em segundos a partir da emissão |
| `expira_em` | string (date-time, UTC) | Instante de expiração |

**Renovação:** nas rotas autenticadas, perto do vencimento a resposta traz os cabeçalhos `X-Token-Renovado` (token novo) e `X-Token-Expira-Em` (ISO 8601, UTC); o frontend os guarda. Ver [../autenticacao.md](../autenticacao.md).
| `usuario` | `UsuarioSessao` | Usuário autenticado |

`UsuarioSessao`:

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | integer | Identificador do usuário |
| `login` | string | Login |
| `nome_completo` | string | Nome de exibição |
| `papeis` | string[] | Papéis (ex.: `SuperRoot`). Vazio para contas comuns |
| `origem` | string | `local`, `ldap` ou `local_ldap` |
| `perfil_restrito` | boolean | Perfil incompleto ou revalidação vencida: acesso restrito ao próprio perfil |
| `campos_pendentes` | string[] | Campos obrigatórios não preenchidos (ex.: `["ramal", "andar"]`) |
| `revisao_obrigatoria` | boolean | Perfil ainda não confirmado no mês civil atual (ou nunca confirmado) |
| `conta_root` | boolean | Conta administrativa principal (login `LOGIN_ADMIN`): dispensada da confirmação do perfil e única com acesso à Notificações |
| `tema` | string | Tema da interface escolhido pelo usuário: `claro`, `escuro` ou `auto` (segue o sistema operacional; padrão) |

```json
{
  "token_acesso": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "tipo_token": "bearer",
  "expira_em_segundos": 3600,
  "expira_em": "2026-09-23T20:30:00Z",
  "usuario": {
    "id": 1,
    "login": "root",
    "nome_completo": "Administrador",
    "papeis": ["SuperRoot"],
    "origem": "local",
    "perfil_restrito": false,
    "campos_pendentes": ["ramal", "cargo", "departamento", "andar", "predio"],
    "revisao_obrigatoria": true,
    "conta_root": false
  }
}
```

Só a conta root (login `LOGIN_ADMIN`, padrão `root`) e as **contas de integração** (`conta_integracao`) podem ter campos pendentes sem ficar restritas; os SuperRoot também confirmam o perfil todo mês. A conta de integração **não** é `conta_root`. `conta_root = true` identifica essa conta: o Angular mostra as Notificações (ver [notificações.md](notificacoes-changelog.md)).

### Erros

| HTTP | `codigo` | `detalhe` | Causa |
|---|---|---|---|
| `401` | `nao_autenticado` | `Usuário ou senha inválidos.` | Recusado pelo LDAP e pela conta local |
| `422` | `validacao` | lista em `erros` | Campo ausente, vazio ou fora do tamanho |

### Consumo no Angular

```typescript
this.autenticacao.entrar({ login, senha }).subscribe({
  next: (usuario) => this.roteador.navigateByUrl(usuario.perfil_restrito ? '/perfil' : '/'),
  error: (erro: HttpErrorResponse) => { /* 401 → credenciais inválidas */ },
});
```

Use sempre `AutenticacaoService.entrar()`, que grava a sessão e agenda a expiração.

---

## `GET /api/autenticacao/sessao`

Retorna o `UsuarioSessao` do dono do token, com a situação do perfil recalculada. O frontend usa este endpoint para validar a sessão restaurada do navegador.

- **Autorização:** Bearer.
- **Resposta `200`:** `UsuarioSessao`, ver acima. Traz também `perfis` (`[{id, nome}]`, perfis ativos do usuário), `perfil_ativo` (`{id, nome}` ou nulo) e `personificado_por` (`{id, login, nome_completo}` ou nulo; preenchido quando um SuperRoot está personificando).
- **Erros:** `401` (`nao_autenticado`), com `detalhe` `Não autenticado.`, `Token inválido.`, `Sessão expirada.` ou `Usuário inválido ou inativo.`

---

## `POST /api/autenticacao/perfil-ativo`

Troca o **perfil de acesso ativo** do usuário (só ele vale no cálculo do acesso; ver [acl.md](acl.md#perfis-de-acesso)). Devolve um token novo com o claim `pa`; o Angular guarda a sessão e **recarrega a aplicação em `/`** (zera acessos, atalhos e notificações).

- **Autorização:** Bearer.
- **Corpo:** `{"perfil_id": 3}`.
- **Resposta `200`:** `RespostaToken` (como o login), com o `usuario` já no novo perfil.
- **Erros:** `401` (`nao_autenticado`); `403` (`acesso_negado`) se o perfil não é do usuário ou está inativo.
- **Auditoria:** `autenticacao.perfil_ativo`.

---

## Personificação de usuário

O **SuperRoot real** pode navegar como outro usuário para testar a atribuição de permissões (como no GLPI). O token passa a ter `sub` = usuário personificado e o claim `imp` = id do SuperRoot; o claim é mantido na renovação do token. O usuário personificado é o que vale para ACL, notificações e dados; o **autor real fica registrado na auditoria** (`personificado_por_id` e o autor gravado como `alvo (por root)`). O front mostra a faixa "Você está personificando…" com o botão **Parar de personificar** e recarrega em `/` ao iniciar e ao parar.

### `POST /api/autenticacao/personificar`

- **Autorização:** SuperRoot real (também aceito com a personificação em curso, para trocar de alvo).
- **Corpo:** `{"usuario_id": 7}`.
- **Resposta `200`:** `RespostaToken`; `usuario.personificado_por` identifica o SuperRoot.
- **Erros:** `403` (`acesso_negado`) para quem não é SuperRoot; `404` se o alvo não existe; `422` (`validacao`) se o alvo está inativo ou é o próprio SuperRoot.
- **Auditoria:** `autenticacao.personificar`.

### `POST /api/autenticacao/personificar/parar`

Devolve a sessão do SuperRoot.

- **Autorização:** Bearer com personificação em curso.
- **Resposta `200`:** `RespostaToken` do SuperRoot.
- **Erros:** `422` (`validacao`) se não há personificação em curso.
- **Auditoria:** `autenticacao.personificar.parar`.

---

## `PUT /api/autenticacao/tema`

Grava o tema da interface do próprio usuário, para que a escolha o acompanhe em qualquer navegador ou aparelho. O Angular também guarda a escolha no `localStorage` (chave `sgi-spi.tema`), para aplicá-la antes do login e sem piscar; depois do login, o valor da conta prevalece.

- **Autorização:** Bearer. Funciona mesmo com o perfil pendente; não passa pela validação da CGP.
- **Corpo:** `{"tema": "claro" | "escuro" | "auto"}`.
- **Resposta `200`:** `UsuarioSessao` atualizado (campo `tema`).
- **Erros:** `401` (`nao_autenticado`); `422` (`validacao`) para valor fora das três opções.

---

## `GET /api/autenticacao/perfil`

Perfil institucional do usuário autenticado.

- **Autorização:** Bearer.
- **Resposta `200`: `PerfilLeitura`**

| Campo | Tipo | Descrição |
|---|---|---|
| `nome_completo` | string | Nome completo |
| `email` | string | E-mail institucional |
| `ramal` | string | Ramal |
| `celular` | string | Celular |
| `linkedin` | string | Link do perfil no LinkedIn (opcional, até 200). Domínio diferente de `linkedin.com` → `422`. **Vale na hora**: não passa pela validação da CGP |
| `cargo` | string | Cargo |
| `departamento` | string | Departamento |
| `andar` | string | Andar: `Subsolo` ou `1` a `13` (lista fixa na tela) |
| `predio` | string | Lado do andar: `A` ou `B` (na tela, "Lado"; o nome do campo continua `predio`) |
| `data_nascimento` | string (date) \| null | `AAAA-MM-DD` |
| `gestor_id` | integer \| null | Superior imediato (em vigor) |
| `gestor_nome` | string \| null | Nome do gestor |
| `perfil_revisado_em` | datetime \| null | Última confirmação |
| `situacao_campos` | objeto | Por campo: `pendente`, `valor_proposto`, `valor_proposto_rotulo`, `validado_por`, `validado_em`, `corrigido` (validação da CGP; só no `GET` do próprio perfil) |
| `superior_obrigatorio` | boolean | O superior imediato é obrigatório para este usuário |

---

## `PUT /api/autenticacao/perfil`

Confirma o próprio perfil no mês civil (grava `perfil_revisado_em`). Operação auditada como `usuario.revisar-perfil`.

- **Usuário comum:** cada campo diferente do valor em vigor vira uma **alteração pendente** de validação da CGP (o valor em vigor não muda), e a CGP recebe e-mail. Voltar ao valor em vigor descarta a pendência do campo. **CGP e SuperRoot:** a alteração vale na hora (histórico como validada).
- **Superior imediato:** obrigatório (`400` "Informe o superior imediato."), exceto para a conta root e o topo da hierarquia; `400` se for o próprio usuário ou formar ciclo.

- **Autorização:** Bearer.
- **Requisição: `RevisaoPerfil`**. Mesmos campos de `PerfilLeitura`, sem `gestor_nome` e `perfil_revisado_em`.
  - **Obrigatórios, não podem ser vazios:** `nome_completo`, `email` (formato válido), `ramal`, `cargo`, `departamento`, `andar`, `predio`.
  - `andar` aceita só `Subsolo` ou `1` a `13`, e `predio` (lado) só `A` ou `B`; outro valor devolve `400` (`Andar inválido…`/`Lado inválido…`). Valores antigos de texto livre continuam aceitos enquanto não forem alterados.
  - **Opcionais:** `celular`, `data_nascimento`; `gestor_id` (ver acima).

```json
{
  "nome_completo": "Maria Silva",
  "email": "maria@spi.sp.gov.br",
  "ramal": "4321",
  "celular": "",
  "cargo": "Analista",
  "departamento": "Coordenadoria de Contratos",
  "andar": "5",
  "predio": "A",
  "data_nascimento": null,
  "gestor_id": 42
}
```

- **Resposta `200`:** `UsuarioSessao` atualizado. Com `perfil_restrito = false`, a navegação é liberada.
- **Erros:**

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | `Gestor imediato inválido.` ou gestor igual ao próprio usuário |
| `422` | `validacao` | Campo obrigatório vazio (`Preencha os campos obrigatórios: ramal, andar.`) ou e-mail inválido |

---

## `GET /api/autenticacao/perfil/opcoes-departamento`

Setores para o combobox **Departamento** do perfil (em "Meu perfil" e no cadastro de usuários). Fica liberado durante a restrição de perfil e não exige acesso ao módulo Setores.

- Traz os setores **ativos e institucionais** (os grupos sistêmicos, como "Auditores", ficam de fora), em ordem hierárquica: cada pai antes dos filhos, irmãos em ordem alfabética. Setor cujo pai não entra na lista aparece como raiz.
- **Resposta `200`:** `OpcaoDepartamento[]`, com `id`, `nome` (o valor gravado em `perfil.departamento`) e `nivel` (0 = raiz; usado para recuar a opção).
- O perfil continua guardando o departamento como texto: valores que já existiam, inclusive os que vêm do AD na sincronização LDAP, são preservados. A tela mostra o valor atual mesmo quando ele não está em Setores.

## `GET /api/autenticacao/perfil/opcoes-gestor`

Usuários ativos para o seletor de gestor imediato. Fica liberado durante a restrição de perfil, diferentemente de `/api/usuarios/opcoes`.

| Parâmetro (query) | Tipo | Padrão | Descrição |
|---|---|---|---|
| `busca` | string | — | Texto pesquisado em login, nome, e-mail, ramal, celular, cargo, departamento e prédio |
| `limite` | integer | 20 | 1 a 50 |

- **Resposta `200`:** `OpcaoUsuario[]`, ver [usuarios.md](usuarios.md#opcaousuario).
