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
| `revisao_obrigatoria` | boolean | Revalidação vencida (mais de 30 dias) ou nunca feita |

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
    "revisao_obrigatoria": true
  }
}
```

O SuperRoot pode ter campos pendentes sem ficar restrito.

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
- **Resposta `200`:** `UsuarioSessao`, ver acima.
- **Erros:** `401` (`nao_autenticado`), com `detalhe` `Não autenticado.`, `Token inválido.`, `Sessão expirada.` ou `Usuário inválido ou inativo.`

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
| `cargo` | string | Cargo |
| `departamento` | string | Departamento |
| `andar` | string | Andar |
| `predio` | string | Prédio |
| `data_nascimento` | string (date) \| null | `AAAA-MM-DD` |
| `gestor_id` | integer \| null | Gestor imediato |
| `gestor_nome` | string \| null | Nome do gestor |
| `perfil_revisado_em` | datetime \| null | Última revalidação |

---

## `PUT /api/autenticacao/perfil`

Grava o próprio perfil e **registra a revalidação**, reiniciando o prazo de 30 dias. Operação auditada como `usuario.revisar-perfil`.

- **Autorização:** Bearer.
- **Requisição: `RevisaoPerfil`**. Mesmos campos de `PerfilLeitura`, sem `gestor_nome` e `perfil_revisado_em`.
  - **Obrigatórios, não podem ser vazios:** `nome_completo`, `email` (formato válido), `ramal`, `cargo`, `departamento`, `andar`, `predio`.
  - **Opcionais:** `celular`, `data_nascimento`, `gestor_id`.

```json
{
  "nome_completo": "Maria Silva",
  "email": "maria@spi.sp.gov.br",
  "ramal": "4321",
  "celular": "",
  "cargo": "Analista",
  "departamento": "Coordenadoria de Contratos",
  "andar": "5",
  "predio": "Sede",
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
