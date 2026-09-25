# AGENTS.md: regras para agentes e desenvolvedores do contratos-spi

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

## Documentação da API (obrigatória)

Qualquer criação, alteração ou remoção de endpoint, parâmetro, schema, resposta, código HTTP, autenticação ou autorização deve atualizar `docs/` **na mesma alteração**, seguindo o modelo de `docs/endpoints/autenticacao.md` e o índice de `docs/api.md`. O OpenAPI do FastAPI deve permanecer completo e consistente. O teste `test_openapi_documenta_endpoints` precisa ser atualizado junto.

## Escopo

- Implemente o que foi pedido. Funcionalidades, telas, endpoints ou regras que não constam na solicitação devem ser **propostas e confirmadas antes** de entrar no código, mesmo quando existem no sistema de referência (SGI SPI, 10.23.1.220).

## Estrutura e infraestrutura

- Todo o sistema fica em `/home/administrador/projeto`.
- Persistência em PostgreSQL (SQLAlchemy 2 + Alembic). Toda alteração de modelo exige migração revisada em `backend/alembic/versions/`.
- Detalhes de instalação, execução e manutenção: `README.md`.
