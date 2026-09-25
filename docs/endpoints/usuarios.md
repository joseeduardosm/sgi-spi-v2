# Endpoints de usuários (`/api/usuarios`)

Tag no OpenAPI: **Usuários**. Implementação: `backend/app/api/routes/usuarios.py` e `backend/app/services/servico_admin_usuarios.py`.

## Finalidade

Gerencia a identidade dos usuários e seus dados funcionais: login, situação, origem, papel SuperRoot, vínculo LDAP e perfil institucional.

## Regras gerais

- **Autorização:**
  - **Leitura** (`GET`): ACL `usuarios` ≥ `LEITURA`, com perfil em dia.
  - **Escrita** (`POST`, `PUT`, `DELETE`): papel **SuperRoot**.
- **Contas locais** têm senha armazenada como hash bcrypt. **Contas LDAP** não têm senha local utilizável. Se o SuperRoot definir uma senha numa conta `ldap`, ela passa a `local_ldap` (contingência).
- **Conta administrativa principal** (`LOGIN_ADMIN` do `.env`):
  - não pode ser excluída, desativada nem perder o papel SuperRoot;
  - a senha dela é definida só pelo `.env`.
- Ninguém pode excluir nem desativar a própria conta, nem remover o próprio papel SuperRoot.
- **Auditoria:** `usuario.criar`, `usuario.alterar` (lista as mudanças de situação, papel e senha) e `usuario.excluir`.

## Schemas

### `DadosPerfil`

Perfil institucional usado na criação e na alteração. Os textos são aparados e podem ficar vazios nesses endpoints. A obrigatoriedade só vale na [revalidação feita pelo próprio usuário](autenticacao.md#put-apiautenticacaoperfil).

| Campo | Tipo | Regras |
|---|---|---|
| `nome_completo` | string | até 200 |
| `email` | string | até 254, formato de e-mail quando preenchido |
| `ramal` | string | até 20 |
| `celular` | string | até 30 |
| `cargo` | string | até 150 |
| `departamento` | string | até 150 |
| `andar` | string | até 30 |
| `predio` | string | até 100 |
| `data_nascimento` | date \| null | `AAAA-MM-DD` |
| `gestor_id` | integer \| null | Usuário existente e diferente do próprio |

### `DetalheUsuario` (resposta)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | integer | Identificador |
| `login` | string | Login |
| `ativo` | boolean | Situação da conta |
| `superusuario` | boolean | Papel SuperRoot |
| `origem` | string | `local`, `ldap` ou `local_ldap` |
| `possui_senha_local` | boolean | Tem senha local utilizável |
| `diretorio_nome` | string \| null | Diretório LDAP vinculado |
| `id_externo` | string \| null | `objectGUID` no diretório |
| `perfil` | `PerfilLeitura` | `DadosPerfil` + `gestor_nome` e `perfil_revisado_em` |
| `perfil_completo` | boolean | Campos obrigatórios preenchidos |
| `revisao_obrigatoria` | boolean | Revalidação vencida ou nunca feita |
| `setores` | string[] | Nomes dos setores dos quais é membro |
| `ultimo_acesso_em` | datetime \| null | Último login |
| `criado_em`, `atualizado_em` | datetime | |

### `OpcaoUsuario`

Forma reduzida para seletores: `id`, `login`, `nome_completo`, `cargo`, `ativo`.

---

## `GET /api/usuarios`

Lista paginada com pesquisa.

| Parâmetro (query) | Tipo | Padrão | Descrição |
|---|---|---|---|
| `busca` | string | — | Pesquisa em login, nome, e-mail, ramal, celular, cargo, departamento e prédio |
| `situacao` | `ativos` \| `inativos` \| `todos` | `ativos` | Filtro de situação |
| `origem` | `local` \| `ldap` \| `local_ldap` | — | Filtro de origem |
| `pagina` | integer ≥ 1 | 1 | |
| `tamanho_pagina` | integer 1–200 | 50 | |

Resposta `200`, `PaginaUsuarios`, ordenada por nome:

```json
{ "itens": [ { "id": 7, "login": "maria", "ativo": true, "...": "..." } ], "total": 578, "pagina": 1, "tamanho_pagina": 50 }
```

## `GET /api/usuarios/opcoes`

`OpcaoUsuario[]` para seletores: gestor, líder, membros e regras de ACL.

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `busca` | — | Mesmo critério da listagem |
| `limite` | 20 | 1 a 100 |
| `incluir_inativos` | `false` | Inclui contas inativas |

## `GET /api/usuarios/{usuario_id}`

Resposta `200`: `DetalheUsuario`. `404 nao_encontrado`.

## `POST /api/usuarios`

Cria **conta local**. Resposta **`201`**: `DetalheUsuario`.

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `login` | string | sim | 1 a 150; letras, números, `.`, `_`, `-`, `@`; único sem diferenciar maiúsculas |
| `senha` | string | sim | 8 a 128 |
| `ativo` | boolean | não (`true`) | |
| `superusuario` | boolean | não (`false`) | Concede o papel SuperRoot |
| `perfil` | `DadosPerfil` | não | |

```json
{ "login": "ana.souza", "senha": "********", "ativo": true, "superusuario": false, "perfil": { "nome_completo": "Ana Souza" } }
```

Erros: `409 conflito` (`Este login já está cadastrado.`), `422 validacao`, `400 invalido` (gestor inválido).

## `PUT /api/usuarios/{usuario_id}`

Altera situação, papel, perfil e, opcionalmente, a senha local.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `senha` | string \| null | não | Nova senha (mín. 8). Vazia/nula mantém a atual |
| `ativo` | boolean | sim | |
| `superusuario` | boolean | sim | |
| `perfil` | `DadosPerfil` | sim | Substitui o perfil inteiro |

Resposta `200`: `DetalheUsuario`. Erros:
- `404`;
- `400 invalido`: conta principal, a própria conta, senha do root ou gestor inválido;
- `422`.

A alteração pelo SuperRoot **não** conta como revalidação do perfil; só o próprio usuário revalida.

## `DELETE /api/usuarios/{usuario_id}`

Resposta **`204`**. Erros:
- `404`;
- `400 invalido`: conta principal ou a própria conta.

A exclusão remove também os vínculos com setores e regras de ACL. Os setores liderados e os subordinados ficam sem líder e sem gestor.

## Consumo no Angular

- Serviço: `UsuariosApiService` (`frontend/src/app/features/usuarios/usuarios-api.service.ts`). Tipos em `usuarios.models.ts`.
- Tela: `/usuarios` (`UsuariosComponent`), protegida por `guardaAcl` (`usuarios`). Ações de escrita aparecem só para o SuperRoot.
- O formulário de perfil (`CamposPerfilComponent`) é compartilhado com a página "Meu perfil".
