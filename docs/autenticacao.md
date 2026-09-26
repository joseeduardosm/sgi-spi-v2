# Autenticação e autorização

## Visão geral

A API usa **JWT (JSON Web Token)** do tipo Bearer, assinado com HS256.

1. O cliente envia login e senha para `POST /api/autenticacao/login`.
2. A API valida as credenciais: primeiro no diretório LDAP ativo, depois na conta local (ver [Fluxo de login](#fluxo-de-login)).
3. A API devolve um `token_acesso` com validade definida (padrão: 60 minutos).
4. O cliente envia o token em cada chamada protegida: `Authorization: Bearer <token_acesso>`.
5. Quando o token expira, a API responde `401` e o cliente precisa autenticar de novo.

Não há sessão no servidor nem token de renovação nesta etapa.

## Contas de usuário

Os usuários ficam na tabela `usuarios` do PostgreSQL. A coluna `origem` indica a origem da conta:

| `origem` | Descrição | Senha local |
|---|---|---|
| `local` | Conta criada no portal | Hash bcrypt em `hash_senha` |
| `ldap` | Conta de representação criada pelo LDAP (login ou sincronização) | Nenhuma: só autentica pelo diretório |
| `local_ldap` | Conta local que também autenticou pelo LDAP, ou conta LDAP que recebeu senha local do SuperRoot | Hash bcrypt, usado como contingência |

### Conta administrativa principal

A conta definida no `backend/.env` (login `root` no desenvolvimento) é criada ou atualizada **a cada inicialização da API**:

| Variável | Descrição |
|---|---|
| `LOGIN_ADMIN` | Login da conta (desenvolvimento: `root`) |
| `HASH_SENHA_ADMIN` | **Hash bcrypt** da senha. A senha em texto puro não é gravada em nenhum arquivo |
| `NOME_ADMIN` | Nome de exibição (aplicado só se a conta ainda não tiver nome) |

Ela é local, ativa e superusuária (papel `SuperRoot`). Ela não pode ser excluída, desativada nem perder o papel SuperRoot, e nenhuma identidade LDAP homônima consegue assumi-la. Por isso é o acesso administrativo de contingência quando o diretório está fora do ar.

Para trocar a senha:

```bash
backend/.venv/bin/python scripts/gerar-hash-senha.py
# edite backend/.env: HASH_SENHA_ADMIN='<hash>'   (aspas simples: o hash contém "$")
sudo systemctl restart contratos-spi-api
```

## Fluxo de login

O LDAP é **prioritário, mas não exclusivo**:

```text
POST /api/autenticacao/login
   │
   ├─ Há diretório LDAP ativo?
   │     sim → conta técnica localiza a pessoa (sAMAccountName ou userPrincipalName)
   │           → bind com a identidade encontrada + senha informada
   │           → sucesso: cria/atualiza a conta de representação e autentica
   │           → senha recusada, pessoa não encontrada, conta desativada no AD
   │             ou diretório indisponível: segue para a conta local
   │
   └─ Conta local: usuário ativo com hash_senha e senha correta → autentica
                   caso contrário → 401 "Usuário ou senha inválidos."
```

Detalhes do login LDAP:

- **Login aceito:** `sAMAccountName` (ex.: `maria`) ou `userPrincipalName` (ex.: `maria@spi.sp.gov.br`).
- **Identidades testadas no bind:** DN completo, `userPrincipalName`, `login@dominio` e `DOMINIO\login`. O domínio é derivado da Base DN.
- **Conta desativada no AD** (`userAccountControl` com o bit `ACCOUNTDISABLE`): recusada mesmo antes da próxima sincronização.
- **Conta de representação:** na primeira autenticação é criada com `origem = ldap`. Nas seguintes, são atualizados login, nome, e-mail, identificador externo (`objectGUID`), DN e situação. Os demais dados internos, como o perfil institucional, são preservados.
- **Conta local homônima** que autentica pelo LDAP é vinculada ao diretório e passa a `origem = local_ldap`. A senha local continua valendo.
- **Superusuários nunca são vinculados** a uma identidade LDAP.
- Usuário inexistente, senha errada e conta inativa retornam a **mesma** resposta (`401`), com tempo de resposta equivalente.

## Conteúdo do token

| Declaração | Descrição |
|---|---|
| `sub` | **ID** do usuário (`usuarios.id`), como texto. O login pode mudar numa sincronização LDAP; o ID não muda |
| `login` | Login no momento da emissão (informativo) |
| `papeis` | Papéis no momento da emissão (informativo) |
| `iat` / `exp` | Emissão / expiração (epoch, segundos) |
| `tipo` | Sempre `acesso` |

O conteúdo do token é legível por qualquer pessoa (é apenas assinado, não criptografado). A cada requisição, o backend recarrega o usuário pelo `sub` e usa a situação, os papéis e o perfil **atuais**. Um usuário desativado perde o acesso imediatamente, mesmo com token válido.

No Swagger (`/api/documentacao`), clique em **Authorize** e cole apenas o `token_acesso`.

## Regras de autenticação

| Situação | Resposta |
|---|---|
| Token ausente | `401 Não autenticado.` |
| Assinatura inválida ou token malformado | `401 Token inválido.` |
| Token expirado | `401 Sessão expirada.` |
| Usuário do token não existe mais ou está inativo | `401 Usuário inválido ou inativo.` |

Todas as respostas `401` têm `codigo = nao_autenticado` e o cabeçalho `WWW-Authenticate: Bearer`.

## Perfil institucional obrigatório

Todo usuário comum precisa manter o perfil institucional **completo** e **revalidá-lo a cada 30 dias**.

- **Campos obrigatórios:** `nome_completo`, `email`, `ramal`, `cargo`, `departamento`, `andar` e `predio`.
- **Campos opcionais:** `celular`, `data_nascimento` e `gestor_id`.
- **Revalidação:** feita em `PUT /api/autenticacao/perfil`, que grava `perfil_revisado_em`.
- **Restrição:** enquanto houver campo obrigatório vazio ou a revalidação estiver vencida (ou nunca feita), o **backend** recusa todos os endpoints com `403` e `codigo = revisao_perfil_obrigatoria`. Continuam liberados: `/api/autenticacao/login`, `/sessao`, `/perfil`, `/perfil/opcoes-gestor` e `/perfil/opcoes-departamento`.
- **Sessão:** `GET /api/autenticacao/sessao` informa `perfil_restrito`, `campos_pendentes` e `revisao_obrigatoria`.
- **SuperRoot:** não passa por essa restrição.

Contas criadas pelo LDAP começam com perfil incompleto (só nome e e-mail vêm do diretório). No primeiro acesso, a pessoa completa e confirma o cadastro.

## Autorização

### Papéis

| Papel | Quem tem | Acesso |
|---|---|---|
| `SuperRoot` | Usuários com `superusuario = true` (inclui a conta administrativa principal) | Administração: usuários, setores, ACL e diretórios LDAP. Sempre CONTROLE_TOTAL na ACL |

Endpoint restrito a papel usa a dependência `exigir_papeis`. Sem o papel → `403` com `codigo = acesso_negado`.

### ACL por recurso

Cada **recurso** representa um módulo do portal. Ele é identificado por um `slug` técnico, por exemplo `usuarios`, `setores` ou `contratos`. As **regras** associam o recurso a um **nível** e a usuários e/ou setores.

| Nível | Permite |
|---|---|
| `LEITURA` | Consultar o recurso |
| `MODIFICACAO` | Operações que alteram dados |
| `CONTROLE_TOTAL` | Nível máximo |

Cálculo do nível efetivo:

1. SuperRoot → `CONTROLE_TOTAL`.
2. Recurso não cadastrado, inativo ou **sem regras** → `CONTROLE_TOTAL` para qualquer usuário autenticado (política aberta).
3. A partir da **primeira regra**, o recurso vira **lista positiva**: só usuários ou setores contemplados têm acesso.
4. Se houver regra **direta** para o usuário, vale a de maior nível entre as diretas. As regras dos setores são ignoradas.
5. Senão, vale o maior nível entre as regras dos **setores ativos** dos quais o usuário é membro.
6. Nenhuma regra aplicável → sem acesso.

No backend, o endpoint declara o nível mínimo com `exigir_acl`, que é verificado antes da execução:

```python
from fastapi import Depends
from app.api.dependencias import exigir_acl
from app.models.acl import NivelAcl
from app.models.usuario import Usuario

@roteador.put("/{contrato_id}")
def alterar_contrato(usuario: Usuario = Depends(exigir_acl("contratos", NivelAcl.MODIFICACAO))): ...
```

Nível insuficiente → `403` com `codigo = acl_negado`, `recurso`, `nivel_exigido` e `nivel_efetivo`.

O frontend consulta `GET /api/acl/meus-acessos` para ocultar módulos, mas a proteção efetiva é sempre a do backend.

Novos papéis devem ser incluídos em `Papel` (`backend/app/models/usuario.py`), no tipo `Papel` do Angular (`frontend/src/app/core/modelos/usuario.model.ts`) e nesta documentação.

## Configuração (`backend/.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `CHAVE_SECRETA_JWT` | (obrigatória) | Chave de assinatura, mínimo 32 caracteres. Trocar a chave invalida todos os tokens emitidos |
| `ALGORITMO_JWT` | `HS256` | Algoritmo de assinatura |
| `MINUTOS_EXPIRACAO_TOKEN` | `60` | Validade do token |
| `CHAVE_CIFRA_LDAP` | (obrigatória) | Chave Fernet que cifra a senha de bind dos diretórios |
| `INTERVALO_SINCRONIZACAO_LDAP_MINUTOS` | `15` | Intervalo da sincronização automática (`0` desativa) |
| `TEMPO_LIMITE_LDAP_SEGUNDOS` | `5` | Tempo limite de conexão com o diretório |

## Integração com o frontend Angular

Arquivos em `frontend/src/app/core/autenticacao/` e `frontend/src/app/core/acesso/`:

| Arquivo | Responsabilidade |
|---|---|
| `autenticacao/autenticacao.service.ts` | `AutenticacaoService`: `entrar()`, `sair()`, `validarSessao()`, `definirUsuario()`, `possuiPapel()`, sinais `usuario` e `autenticado`, propriedade `token` |
| `autenticacao/autenticacao.interceptor.ts` | `interceptadorAutenticacao`: anexa `Authorization: Bearer` às chamadas para `/api` (exceto o login). Em `401`, encerra a sessão; em `403 revisao_perfil_obrigatoria`, leva a `/perfil` |
| `autenticacao/autenticacao.guards.ts` | `guardaAutenticacao` (rotas autenticadas), `guardaVisitante` (impede usuário logado de ver `/login`), `guardaPapel` (papéis em `route.data.papeis`) |
| `acesso/acesso.service.ts` | `AcessoService`: carrega `GET /api/acl/meus-acessos` e responde `pode(slug, nivel)` |
| `acesso/acesso.guards.ts` | `guardaPerfil` (perfil pendente → só `/perfil`), `guardaAcl` (nível em `route.data.acl`) |

Comportamento:

- **Armazenamento:** a sessão (`tokenAcesso`, `expiraEm`, `usuario`) fica em `localStorage`, na chave `contratos-spi.sessao`.
- **Expiração:** o logout automático é agendado para `expira_em`. Ao expirar, redireciona para `/login?sessao=expirada`.
- **Inicialização:** com sessão salva, `validarSessao()` chama `GET /api/autenticacao/sessao`. Se o token não for mais aceito, a sessão é encerrada.
- **Logout:** descarta o token localmente e redireciona para `/login`. O JWT é stateless, então não há chamada ao backend.
- **Rotas:** toda rota autenticada é filha da rota `''` (layout `LayoutAutenticadoComponent`) em `app.routes.ts`, com `guardaAutenticacao` e `guardaPerfil`. Módulos usam `guardaAcl`; telas administrativas usam `guardaPapel` com `data: { papeis: ['SuperRoot'] }`.
