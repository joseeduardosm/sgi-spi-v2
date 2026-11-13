# AGENTS.md: regras para agentes e desenvolvedores do sgi-spi

Este arquivo vale para qualquer agente de IA ou pessoa que altere o código deste repositório.

## Idioma do código: português do Brasil (pt-BR)

Nos códigos **Angular (TypeScript, HTML, SCSS)** e **Python (FastAPI)**:

- **Comentários explicativos** em pt-BR. Isso vale para comentários de linha, blocos, docstrings e JSDoc.
- **Nomes criados no projeto** em pt-BR: variáveis, constantes, parâmetros, atributos, propriedades, funções, métodos, classes, interfaces, tipos, componentes, serviços e arquivos novos. Exemplos: `usuarioAtual`, `carregando`, `salvarDiretorio()`, `ServicoDeUsuarios`, `buscar_por_login()`.
- Escreva nomes **sem acentos e sem cedilha** (`funcao`, `situacao`, `acao`), porque identificadores com caracteres não ASCII causam problemas em ferramentas. Nos comentários, use a acentuação normal.
- **Mantêm o nome original** os elementos que não são do projeto:
  - APIs de frameworks e bibliotecas: `ngOnInit`, `signal`, `HttpClient`, `Depends`, `Session`, `Mapped`, `__init__`, `model_config`...
  - palavras reservadas das linguagens;
  - sufixos de convenção do Angular (`.component.ts`, `.service.ts`, `.spec.ts`);
  - comentários gerados automaticamente por ferramentas (ex.: cabeçalho das migrações do Alembic).
- **Contrato público também em pt-BR:** rotas, parâmetros e campos JSON da API, códigos de erro, tabelas, colunas, índices e constraints do banco, variáveis de ambiente, classes CSS e chaves de armazenamento. Use `snake_case` sem acentos na API e no banco (ex.: `nome_completo`, `revisao_obrigatoria`). Renomear algo do contrato exige migração do banco e atualização de `docs/` na mesma alteração.
- Termos técnicos consagrados mantêm a forma original: LDAP, Base DN, Bind DN, JWT, Bearer, slug, URL, SuperRoot e os níveis `LEITURA`/`MODIFICACAO`/`CONTROLE_TOTAL`.
- Mensagens exibidas ao usuário e mensagens de erro da API também em pt-BR.

## Cabeçalho obrigatório e comentários didáticos

**Todo arquivo de programação** do projeto começa com o bloco de cabeçalho abaixo: `.py` (backend, scripts e laboratórios dos manuais), `.ts`, `.html` e `.scss` do frontend e os scripts `.sh`, `.mjs` e `.js`. Arquivos gerados por build ficam de fora. O teste `backend/tests/test_cabecalho_arquivos.py` falha se faltar o bloco ou alguma seção.

- As quatro seções são escritas **para aquele arquivo**, nunca com texto genérico. **FINALIDADE** diz para que o arquivo existe. **RESUMO TÉCNICO** cita as principais classes, funções, endpoints, validações e integrações. **FINALIDADE DE NEGÓCIO** diz que processo do órgão o arquivo atende e que valor entrega. **CONTEXTO NO SISTEMA** diz com quais módulos, serviços, rotas e tabelas ele se relaciona.
- Python: o bloco **é a docstring do módulo** (uma só). O conteúdo de uma docstring que já existia é incorporado às seções. Se houver *shebang* ou `# -*- coding`, o bloco vem logo depois. Nas migrações do Alembic, as linhas `Revision ID`, `Revises` e `Create Date` ficam no fim do bloco.
- TypeScript, SCSS, `.mjs` e `.js` usam `/** … */`. HTML usa `<!-- … -->`; no `index.html`, o bloco vem depois do `<!doctype html>`. Shell usa `#` em todas as linhas, depois do *shebang*.

```python
"""
===============================================================================
ARQUIVO: nome_do_arquivo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
...

RESUMO TÉCNICO:
...

FINALIDADE DE NEGÓCIO:
...

CONTEXTO NO SISTEMA:
...

===============================================================================
"""
```

```ts
/**
 * =============================================================================
 * ARQUIVO: nome-do-arquivo.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * ...
 *
 * RESUMO TÉCNICO:
 * ...
 *
 * FINALIDADE DE NEGÓCIO:
 * ...
 *
 * CONTEXTO NO SISTEMA:
 * ...
 *
 * =============================================================================
 */
```

**Comentários didáticos (nível estagiário):** o código precisa ser entendido e mantido por um estagiário de desenvolvimento.

- Toda classe, função e método tem docstring ou JSDoc: o que faz, os parâmetros importantes, o retorno, os efeitos (banco, e-mail, arquivos) e a regra de negócio envolvida.
- Antes de cada bloco não trivial (validação, cálculo, consulta, laço, condição de negócio), um comentário explica **o porquê**, não só o quê.
- Recursos do framework que um iniciante pode não conhecer são explicados na primeira vez que aparecem no arquivo: `signal`/`computed`/`effect`, `Depends`, `relationship`, `BackgroundTasks`, Alembic etc.
- Siglas e termos do órgão (NE, OB, CADIN, glosa, preposto, competência) ganham uma explicação curta.
- Comentário errado é pior que nenhum: descreva o que o código realmente faz e não invente regra.

## Documentação da API (obrigatória)

Qualquer criação, alteração ou remoção de endpoint, parâmetro, schema, resposta, código HTTP, autenticação ou autorização deve atualizar `docs/` **na mesma alteração**, seguindo o modelo de `docs/endpoints/autenticacao.md` e o índice de `docs/api.md`. O OpenAPI do FastAPI deve permanecer completo e consistente. O teste `test_openapi_documenta_endpoints` precisa ser atualizado junto.

## Changelog e commits (obrigatório)

- **CHANGELOG, BookStack e GitHub só quando o usuário mandar.** Não atualize o `CHANGELOG.md` da raiz, o BookStack nem faça `git commit`/`git push` por iniciativa própria. Ao terminar uma tarefa, deixe as alterações no working tree e avise que estão prontas. Foque no que foi pedido.
- Quando o usuário mandar atualizar o changelog, a entrada fica na seção da data (a mais recente no topo), em pt-BR, dividida em Adicionado / Alterado / Corrigido / Removido, descrevendo o que mudou para o usuário e citando as migrações do banco e os endpoints criados ou alterados.
- Quando o commit for pedido, ele leva junto as entradas do changelog correspondentes (se o usuário pediu o changelog).

## Layout, margens e paddings (obrigatório)

- Antes de montar uma tela, ache uma equivalente no projeto e **reaproveite a estrutura e as classes dela** (ex.: `.barra-protocolo` + `.campo` com `label` acima do campo; `footer.acoes-formulario` com padding; `.painel-gestao`). Não invente classe de campo ou barra quando já existe uma.
- **Verifique colisão de nomes de classe CSS** (`grep -rn "nome" frontend/src`): estilos globais de outros módulos vazam para o seu componente (ex.: `.cartao-visita` do diretório sobrepôs os cartões do Protocolo).
- Nada fica colado na borda ou em outro elemento: botões, campos, cartões e rodapés precisam de padding interno e espaçamento entre vizinhos. Campos usam o estilo base global de `frontend/src/styles.scss`.
- Rotas de detalhe são páginas (`/rota/:id`), não modais, salvo pedido em contrário.

## Escopo

- Implemente o que foi pedido. Funcionalidades, telas, endpoints ou regras que não constam na solicitação devem ser **propostas e confirmadas antes** de entrar no código, mesmo quando existem no sistema de referência (SGI SPI, 10.23.1.220).

## Estrutura e infraestrutura

- Todo o sistema fica em `/home/administrador/projeto`.
- Persistência em PostgreSQL (SQLAlchemy 2 + Alembic). Toda alteração de modelo exige migração revisada em `backend/alembic/versions/`.
- Detalhes de instalação, execução e manutenção: `README.md`.
- **Recurso novo da ACL** (módulo, `exigir_acl("slug", …)` ou migração que semeia em `acl_recursos`): inclua a entrada em `backend/app/services/acl_niveis.py` com o que **Leitura, Modificação e Controle total liberam naquele módulo** (rótulo curto + frase), a partir do que as rotas realmente exigem. Não deixe nomes genéricos; `test_acl_niveis.py` falha se faltar.
