# Endpoints de controle de acesso (`/api/acl`)

Tag no OpenAPI: **Controle de acesso (ACL)**. Implementação: `backend/app/api/routes/acl.py`. Cálculo em `backend/app/services/servico_acl.py`; administração em `servico_admin_acl.py`.

## Finalidade

Define quem acessa cada módulo do portal. A política e o cálculo do nível efetivo estão descritos em [autenticacao.md](../autenticacao.md#acl-por-recurso).

**Nomes dos níveis:** os valores gravados continuam `LEITURA`, `MODIFICACAO` e `CONTROLE_TOTAL` (hierárquicos). Cada recurso diz o que cada nível libera nele: `GET /acl/recursos`, `GET /acl/regras`, `GET /acl/meus-acessos` e `GET /acl/efetivo/{usuario_id}` trazem `niveis` (`{LEITURA|MODIFICACAO|CONTROLE_TOTAL: {rotulo, descricao}}`), definido em `backend/app/services/acl_niveis.py`. A tela de ACL mostra esses textos (ex.: Protocolo, Modificação = "Reservar números de documentos"). **Todo recurso novo precisa de entrada nesse arquivo** (o teste `test_acl_niveis.py` falha se faltar).

## Regras gerais

- **Autorização:**
  - `GET /api/acl/meus-acessos`: qualquer usuário autenticado com perfil em dia.
  - Demais endpoints: papel **SuperRoot**.
- **Níveis:** `LEITURA` < `MODIFICACAO` < `CONTROLE_TOTAL`.
- **Auditoria:**
  - recursos: `acl.recurso.criar`, `acl.recurso.alterar` e `acl.recurso.excluir`;
  - regras: `acl.regra.criar`, `acl.regra.alterar` e `acl.regra.excluir`;
  - perfis: `acl.perfil.*` e `acl.usuario.perfis` (ver [perfis de acesso](#perfis-de-acesso)).
- **Importações por planilha XLSX** (contratos, checklists e formulários de avaliação) não têm recurso próprio: são parte de "Editar contratos e conduzir a execução" (`contratos` ≥ MODIFICACAO). A migração `d7a2f5c8b1e4` removeu os antigos recursos `importacao-contratos` e `importacao-modelos` (e suas regras e direitos de perfil).
- **Recursos iniciais** (criados pela migração): `usuarios`, `setores`, `contratos` e `relatorios`.
- **Recursos criados abertos a todos** (sem regras): `abrir-chamado`, item "Abrir Chamado" da barra lateral (migração `d1f4b8a2e6c9`; ver [chamados.md](chamados.md)). O SuperRoot pode restringir criando regras.
- **Recursos criados fechados** (só a conta administrativa principal tem CONTROLE_TOTAL; o SuperRoot libera os demais):
  - `atalhos`: gestão dos atalhos fixos da barra lateral, nasce fechado (migração `b5d9f3a7c1e2`; ver [atalhos.md](atalhos.md));
  - `documentacao-api`: Swagger, ReDoc e OpenAPI; nasce fechado (migração `c6e0a4b8d2f1`; ver [documentacao-api.md](documentacao-api.md));
  - `manuais`: módulo Manuais (BookStack); nasce **sem regras**, aberto a todo usuário autenticado (migração `d7a1c5e9b3f2`; ver [manuais.md](manuais.md));
  - `notificacoes-setores`: envio de notificações para setores inteiros, que exige CONTROLE_TOTAL (migração `0c11fdac4f46`, renomeado de `mensageria-setores` pela `d4e8a1c6b2f7`; ver [notificacoes.md](notificacoes.md));
  - `notificacoes-obrigatorias`: define os eventos e canais de notificação obrigatórios para um setor ou usuário, que exige CONTROLE_TOTAL (migração `e5f9b2d7a3c1`, criado **fechado**: só a conta root, até a administração liberar mais alguém).

---

## `GET /api/acl/meus-acessos`

Recursos **ativos** aos quais o usuário autenticado tem acesso, com o nível efetivo. Recursos sem acesso não aparecem.

Resposta `200`, `AcessoEfetivo[]`:

| Campo | Tipo | Descrição |
|---|---|---|
| `recurso_id` | integer | |
| `nome` | string | Nome do recurso |
| `slug` | string | Identificador técnico |
| `url_base` | string | Rota base no portal |
| `nivel` | string \| null | Nível efetivo (nulo = sem acesso; só em `/efetivo`) |
| `origens` | objeto | De onde vem o nível: `perfil` (perfil ativo), `setor` e `direta`, cada um com o seu nível; o efetivo é o maior. Vazio em módulo aberto ou SuperRoot |

```json
[{ "recurso_id": 1, "nome": "Usuários", "slug": "usuarios", "url_base": "/usuarios", "nivel": "CONTROLE_TOTAL" }]
```

## `GET /api/acl/efetivo/{usuario_id}`

Nível efetivo de um usuário em **todos** os recursos ativos (`nivel` nulo = sem acesso), com a `origens` de cada nível. Serve para auditar permissões. Query opcional `perfil_id`: simula aquele perfil como o ativo (padrão: o perfil padrão do usuário). `404` se o usuário não existir.

---

## Recursos

### `LeituraRecurso`

`id`, `nome`, `slug`, `descricao`, `url_base`, `ativo`, `total_regras` (zero = recurso aberto), `criado_em`, `atualizado_em`.

### `GravacaoRecurso`

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `nome` | string | sim | 1 a 100, único sem diferenciar maiúsculas |
| `slug` | string | sim | 1 a 60, único. Normalizado: minúsculas, caracteres fora de `a-z0-9_-` viram `-` |
| `descricao` | string | não | até 2000 |
| `url_base` | string | não | Ex.: `/contratos` |
| `ativo` | boolean | não (`true`) | Inativo = acesso aberto |

| Método e caminho | Resposta | Erros |
|---|---|---|
| `GET /api/acl/recursos` | `200 LeituraRecurso[]` | |
| `POST /api/acl/recursos` | **`201`** `LeituraRecurso` | `409 conflito`, `400`, `422` |
| `PUT /api/acl/recursos/{recurso_id}` | `200` `LeituraRecurso` | `404`, `409`, `400`, `422` |
| `DELETE /api/acl/recursos/{recurso_id}` | **`204`** | `404` |

Excluir um recurso remove também as regras dele, e o módulo volta a ficar aberto. O slug é usado pelo código (`exigir_acl("slug")`): alterá-lo desvincula as proteções existentes.

---

## Regras

### `GravacaoRegra`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `recurso_id` | integer | sim | Recurso existente |
| `nivel` | `LEITURA` \| `MODIFICACAO` \| `CONTROLE_TOTAL` | sim | |
| `usuarios_ids` | integer[] | * | Usuários contemplados |
| `setores_ids` | integer[] | * | Setores contemplados |

\* Pelo menos um usuário ou setor.

### `LeituraRegra`

`id`, `recurso_id`, `recurso_nome`, `recurso_slug`, `nivel`, `usuarios` (`OpcaoUsuario[]`), `setores` (`{id, nome, sistemico}[]`), `criado_em`, `atualizado_em`.

| Método e caminho | Resposta | Erros |
|---|---|---|
| `GET /api/acl/regras?recurso_id=` | `200 LeituraRegra[]` (filtro opcional) | |
| `POST /api/acl/regras` | **`201`** `LeituraRegra` | `400 invalido`: recurso inválido, sem alvos, alvos inexistentes. `422`: nível inválido |
| `PUT /api/acl/regras/{regra_id}` | `200` `LeituraRegra` | `404`, `400`, `422` |
| `DELETE /api/acl/regras/{regra_id}` | **`204`** | `404` |

```json
{ "recurso_id": 3, "nivel": "MODIFICACAO", "usuarios_ids": [42], "setores_ids": [5] }
```

**Atenção:** a primeira regra de um recurso o transforma em lista positiva. A partir dela, quem não estiver contemplado perde o acesso.

## Perfis de acesso

Um **perfil** é um conjunto de direitos atribuível a vários usuários, como no GLPI. O acesso passa a poder ser liberado **por perfil, por setor e por usuário**.

- **Ações independentes:** no perfil, cada módulo tem **ações próprias** (de 1 a 3, com os nomes do módulo, ex.: Patrimônio: *Consultar o patrimônio*, *Cadastrar bens e solicitar*, *Administrar o patrimônio*). Marcar uma ação **não marca as outras**: quem tem só *Cadastrar* cadastra, mas não consulta. O catálogo vem de `backend/app/services/acl_acoes.py` (derivado de `acl_niveis.py`: níveis "Igual a…" ou "Sem efeito" não viram ação) e aparece em `acoes` de `GET /acl/recursos`. O código da ação é a porta que ela abre nas rotas (`LEITURA`, `MODIFICACAO` ou `CONTROLE_TOTAL`); cada rota (`exigir_acl`) confere a ação **exata**.
- **Ações próprias de um módulo:** além das ações que correspondem aos níveis, um módulo pode ter ações **próprias**, que só existem no perfil e só valem na rota que as confere (catálogo `ACOES_EXTRAS` em `acl_acoes.py`; vêm em `acoes` de `GET /acl/recursos` com o código em `codigo`). Hoje: **Contratos → "Lançar ordem bancária" (`LANCAR_OB`)**, que permite só anexar a OB das competências (ver [contratos-execucao.md](contratos-execucao.md#ordem-bancária-ob-post-apicontratoscontrato_idcompetenciascompetencia_idordem-bancaria)), em qualquer contrato, sem dar nenhum outro poder. Serve para a conta de uma integração: perfil com "Consultar contratos" + "Lançar ordem bancária". Essas ações não aparecem como nível em `meus-acessos` (só em `acoes`).
- **Regras por setor e diretas continuam hierárquicas** (o nível inclui os de baixo). A decisão de uma porta é: SuperRoot, módulo aberto, regra de setor/direta com nível suficiente **ou** a ação exata no perfil ativo.
- **Perfil ativo:** o usuário pode ter N perfis, mas só **um vale por vez**: o **padrão** ou o escolhido no menu do usuário (`POST /api/autenticacao/perfil-ativo`). Perfil inativo não vale.
- **Perfil novo nasce em branco.** Tela do perfil (como no GLPI): barra lateral com **Perfil** (dados gerais), **todos os módulos** (com a contagem de ações liberadas) e **Usuários**; ao abrir um módulo, as ações dele aparecem como caixas de marcação (com "Marcar/desmarcar todos") e um **Salvar** (sem nenhuma marcada, o módulo sai do perfil).
- **Módulo aberto × fechado:** um módulo sem regras **e sem direitos de perfil** continua aberto a todos. Incluí-lo em um perfil o **fecha** para quem não for contemplado (a tela avisa e pede confirmação). `LeituraRecurso.total_perfis` conta os perfis ativos com o módulo.
- **Níveis em `meus-acessos`:** `acoes` traz as ações do perfil ativo no módulo. O `nivel` mostrado é o maior entre o das regras e o da maior ação marcada, **só para a interface** decidir o que exibir; o backend confere a ação exata. Pontos do código que comparam um nível único (`resolver_acesso`, `exigir_gestao`) usam o lado seguro: só contam o nível quando todas as portas até ele estão abertas.
- **Migração:** `d2f8b6a4c0e1` criou perfis a partir das regras existentes; `e3a9c7b5d1f4` deu nomes a eles (Administrador do sistema, Editor-chefe de Notícias, Editor de Notícias, Gestor de Patrimônio, Gestor de Contratos, Notificações para setores); `f4b0d8c6e2a5` passou os direitos para ações independentes, expandindo cada nível antigo nas ações equivalentes (nenhum acesso mudou).
- **Autorização:** todos os endpoints abaixo são do SuperRoot.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/acl/perfis` | Lista (`LeituraPerfil`: `id`, `nome`, `descricao`, `ativo`, `total_usuarios`, `total_direitos` = módulos, datas) |
| `POST` | `/api/acl/perfis` | Cadastra (`{nome, descricao, ativo}`; nome único sem diferenciar maiúsculas, `409` se repetido). `201` com `DetalhePerfil` (sem módulos) |
| `GET` | `/api/acl/perfis/{perfil_id}` | `DetalhePerfil`: lista + `direitos` (um item por módulo: `recurso_id`, nome, slug, `acoes` marcadas, `acoes_disponiveis`) e `usuarios` (com `padrao`) |
| `PUT` | `/api/acl/perfis/{perfil_id}` | Altera nome, descrição e ativo |
| `DELETE` | `/api/acl/perfis/{perfil_id}` | Exclui (`204`); `409` se houver usuários (retire-os ou desative o perfil) |
| `PUT` | `/api/acl/perfis/{perfil_id}/modulos/{recurso_id}` | Adiciona o módulo ao perfil ou troca as ações: `{"acoes": ["LEITURA", "CONTROLE_TOTAL"]}` (ao menos uma, entre as do módulo; `422` se vazia; `400` para ação que o módulo não oferece ou módulo inexistente) |
| `DELETE` | `/api/acl/perfis/{perfil_id}/modulos/{recurso_id}` | Remove o módulo do perfil (devolve o `DetalhePerfil`; `404` se o módulo não estava no perfil) |
| `PUT` | `/api/acl/perfis/{perfil_id}/usuarios` | Substitui os usuários: `{"usuarios_ids": [1, 2]}`; quem não tinha outro perfil passa a ter este como padrão |
| `PUT` | `/api/acl/perfis/{perfil_id}/setores` | Substitui os setores e grupos sistêmicos que recebem o perfil: `{"setores_ids": [3, 7]}`. Quem é membro (setor ativo) passa a ter o perfil, somado aos atribuídos direto; o detalhe do perfil traz `setores` e a lista, `total_setores`. A API guarda exatamente os ids enviados: a tela (aba Usuários) marca os filhos junto com o pai, e cada um pode ser desmarcado depois. `GET /usuarios/{id}/perfis` informa `via_setores` (nomes dos setores que dão o perfil) e `direto` |
| `GET` | `/api/acl/usuarios/{usuario_id}/perfis` | Perfis do usuário (`perfil_id`, `nome`, `ativo`, `padrao`) |
| `PUT` | `/api/acl/usuarios/{usuario_id}/perfis` | Substitui os perfis: `{"perfis_ids": [1, 2], "padrao_id": 2}`; um só padrão; `400` se `padrao_id` não está na lista |

Auditoria: `acl.perfil.criar`, `.alterar`, `.excluir`, `.modulo`, `.modulo.remover`, `.usuarios` e `acl.usuario.perfis`.

Erros comuns: `404` (`nao_encontrado`) para perfil/usuário inexistente; `403` para quem não é SuperRoot.

---

## Consumo no Angular

- `AcessoService` (`frontend/src/app/core/acesso/acesso.service.ts`) carrega `meus-acessos` após o login. A barra lateral oculta os itens cujo `acl` não aparece, e o `guardaAcl` protege as rotas.
- Tela de administração: `/admin/acl` (`AclComponent`), com abas **Regras**, **Recursos** e **Acesso efetivo**. Restrita ao SuperRoot. Serviço: `AclApiService`.
