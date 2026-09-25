# Endpoints de diretórios LDAP (`/api/ldap/diretorios`)

Tag no OpenAPI: **Diretórios LDAP**. Implementação: `backend/app/api/routes/ldap.py`. Regras em `backend/app/services/servico_ldap.py`; acesso ao diretório em `cliente_ldap.py`; rotina automática em `agendador_ldap.py`.

## Finalidade

Integra o portal ao Active Directory, ou a outro diretório compatível, para:
- autenticar com credenciais corporativas (ver [autenticacao.md](../autenticacao.md#fluxo-de-login));
- importar e sincronizar usuários;
- acompanhar a saúde da conexão.

O módulo **não atribui permissões**. Ele fornece a identidade e a situação dos usuários. A autorização é definida pela [ACL](acl.md).

## Regras gerais

- **Autorização:** todos os endpoints exigem o papel **SuperRoot** (`403 acesso_negado` para os demais; `401` sem token).
- **Um diretório ativo por vez:** ativar um (`ativo: true`) desativa os demais. O banco também garante isso, com um índice único parcial.
- **Senha de bind:** cifrada com Fernet (`CHAVE_CIFRA_LDAP`) antes de ser gravada e **nunca devolvida** pela API. Se a chave for trocada, será preciso informar a senha de novo.
- **Auditoria:** `ldap.criar`, `ldap.alterar`, `ldap.excluir` e `ldap.sincronizar`. A rotina automática registra com o autor `sistema:sincronizacao-ldap`.
- **Sincronização automática:** o diretório ativo é sincronizado a cada `INTERVALO_SINCRONIZACAO_LDAP_MINUTOS` (padrão 15; `0` desativa). Com vários workers, um advisory lock do PostgreSQL garante uma execução por vez.
- **Ao salvar como ativo:** o diretório é sincronizado logo após o cadastro ou a edição. Se estiver indisponível, o cadastro é mantido e a rotina tenta de novo.

## Schemas

### `LeituraDiretorio` (resposta)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | uuid | Identificador |
| `nome` | string | Nome de identificação (ex.: `AD01`) |
| `servidor` | string | Servidor (nome ou IP) |
| `porta` | integer | 389 LDAP, 636 LDAPS |
| `usar_ssl` | boolean | LDAPS (SSL/TLS) |
| `base_dn` | string | Base DN das buscas |
| `bind_dn` | string | Conta técnica (DN, `usuario@dominio` ou `DOMINIO\usuario`) |
| `ativo` | boolean | Usado no login e na sincronização automática |
| `ultimo_teste_em` | datetime \| null | Data do último teste |
| `ultimo_teste_ok` | boolean \| null | Resultado do último teste |
| `ultima_latencia_ms` | integer \| null | Tempo de resposta do último teste |
| `ultimo_erro` | string \| null | Erro do último teste com falha |
| `ultima_sincronizacao_em` | datetime \| null | Data da última sincronização |
| `ultima_sincronizacao_ok` | boolean \| null | Resultado |
| `ultima_sincronizacao_mensagem` | string \| null | Resumo (`encontrados=…, criados=…`) ou erro |
| `criado_em`, `atualizado_em` | datetime | |

### `CriacaoDiretorio` / `AlteracaoDiretorio` / `TesteDiretorioNaoSalvo` (requisição)

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `nome` | string | sim | 1 a 100 |
| `servidor` | string | sim | 1 a 255 |
| `porta` | integer | não (389) | 1 a 65535 |
| `usar_ssl` | boolean | não (`false`) | |
| `base_dn` | string | sim | até 500 |
| `bind_dn` | string | sim | até 500 |
| `senha_bind` | string | **cadastro e teste sem salvar: sim**; alteração: não | Na alteração, vazia ou nula **preserva** a senha atual |
| `ativo` | boolean | não (`false`) | `true` desativa os demais |

### `ResultadoTeste`

| Campo | Tipo | Descrição |
|---|---|---|
| `sucesso` | boolean | Conexão, bind da conta técnica e Base DN válidos |
| `latencia_ms` | integer | Tempo de conexão + bind + validação da Base DN |
| `mensagem` | string | Resultado legível |

Mensagens de falha:
- `Não foi possível conectar a <servidor>:<porta>.`
- `A conta técnica (Bind DN/senha) foi recusada pelo diretório.`
- `Base DN não encontrada no diretório.`
- `Falha na negociação SSL/TLS com o diretório.`
- `O diretório recusou a operação: <descrição>.`

### `ResultadoSincronizacao`

| Campo | Tipo | Descrição |
|---|---|---|
| `encontrados` | integer | Identidades encontradas |
| `criados` | integer | Contas corporativas criadas |
| `atualizados` | integer | Contas existentes atualizadas |
| `desativados` | integer | Contas exclusivamente LDAP desativadas por não constarem mais no diretório |
| `ignorados` | integer | Identidades ignoradas por existir conta local homônima sem vínculo |
| `sincronizado_em` | datetime | |

---

## `GET /api/ldap/diretorios`

`200`: `LeituraDiretorio[]` em ordem alfabética.

## `POST /api/ldap/diretorios`

**`201`**: `LeituraDiretorio`.

```json
{
  "nome": "AD01",
  "servidor": "10.23.1.20",
  "porta": 389,
  "usar_ssl": false,
  "base_dn": "DC=spi,DC=sp,DC=gov,DC=br",
  "bind_dn": "spi\\aplicacoesspi",
  "senha_bind": "<senha da conta técnica>",
  "ativo": true
}
```

## `GET /api/ldap/diretorios/{diretorio_id}`

`200`: `LeituraDiretorio`. `404 nao_encontrado`.

## `PUT /api/ldap/diretorios/{diretorio_id}`

Altera todos os campos. `senha_bind` vazia ou nula mantém a atual. `200`: `LeituraDiretorio`. Erros: `404`, `422`.

## `DELETE /api/ldap/diretorios/{diretorio_id}`

**`204`**. Os usuários importados continuam cadastrados, sem vínculo com o diretório (`diretorio_id = null`). Erro: `404`.

## `POST /api/ldap/diretorios/testar`

Testa uma configuração **ainda não salva**. Corpo: `TesteDiretorioNaoSalvo`, com `senha_bind` obrigatória. `200`: `ResultadoTeste`. Não grava nada.

## `POST /api/ldap/diretorios/{diretorio_id}/testar`

Testa a configuração salva e **registra** `ultimo_teste_em`, `ultimo_teste_ok`, `ultima_latencia_ms` e `ultimo_erro`. Corpo opcional, para testar com outra senha sem alterá-la:

```json
{ "senha_bind": "<senha>" }
```

`200`: `ResultadoTeste`. A falha de conexão também volta como `200`, com `sucesso: false`. Erro: `404`.

## `POST /api/ldap/diretorios/{diretorio_id}/sincronizar`

Sincronização completa e manual. Pode ser usada em diretório inativo.

1. Lê todas as pessoas: `(&(objectCategory=person)(objectClass=user)(sAMAccountName=*))`, com busca paginada.
2. **Cria** contas com `origem = ldap`, sem senha local, para identidades novas.
3. **Atualiza** contas vinculadas ao diretório, localizadas por `objectGUID` ou pelo login. São atualizados login, nome, e-mail, identificador externo, DN e situação (conta desativada no AD → inativa).
4. **Desativa** contas `ldap` vinculadas que não aparecem mais.
5. **Preserva** contas `local`, `local_ldap` e superusuários, que nunca são desativadas. Uma identidade com login igual ao de uma conta local sem vínculo é ignorada (`ignorados`).
6. Se a leitura falhar, **nada é alterado**.

`200`: `ResultadoSincronizacao`.

```json
{ "encontrados": 578, "criados": 0, "atualizados": 578, "desativados": 0, "ignorados": 0, "sincronizado_em": "2026-09-23T20:28:55Z" }
```

Erros: `404`; `503 servico_indisponivel` (`Não foi possível ler o diretório: <motivo> Nenhum usuário foi alterado.`).

## `GET /api/ldap/diretorios/{diretorio_id}/diagnosticar?login=<login>`

Procura um login usando **apenas a conta técnica**. Nunca testa a senha da pessoa.

| Parâmetro (query) | Obrigatório | Descrição |
|---|---|---|
| `login` | sim | `sAMAccountName` ou `userPrincipalName` (1 a 150) |

`200`:

```json
{
  "encontrado": true,
  "entradas": 1,
  "mensagem": "Usuário localizado com sucesso.",
  "login": "maria",
  "nome_principal": "maria@spi.sp.gov.br",
  "dn": "CN=Maria Silva,OU=Pessoas,DC=spi,DC=sp,DC=gov,DC=br"
}
```

## Consumo no Angular

- Serviço: `LdapApiService` (`frontend/src/app/features/administracao/ldap/ldap-api.service.ts`). Tipos em `ldap.models.ts`.
- Tela: `/admin/ldap` (`DiretoriosLdapComponent`), protegida por `guardaPapel` (`SuperRoot`).
- Na edição, o formulário envia `senha_bind: null` quando a senha fica vazia.
- "Testar sem salvar" usa `POST /testar` quando há senha no formulário. Na edição sem senha nova, usa `POST /{id}/testar`.
