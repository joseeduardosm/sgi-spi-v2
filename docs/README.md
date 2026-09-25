# Documentação do contratos-spi

Documentação técnica e funcional da API do **contratos-spi**, sistema de gestão de contratos da Secretaria de Parcerias em Investimentos (SPI).

Esta pasta é parte do código-fonte. Ela é a referência para o desenvolvimento do backend, para o frontend Angular e para futuros sistemas consumidores.

## Índice

| Documento | Conteúdo |
|---|---|
| [api.md](api.md) | Finalidade, arquitetura, URL base, convenções, formato de erros, índice de endpoints |
| [autenticacao.md](autenticacao.md) | Login local e LDAP, token JWT, perfil institucional, papéis, ACL e integração com o Angular |
| [endpoints/autenticacao.md](endpoints/autenticacao.md) | `/api/autenticacao/*`: login, sessão e próprio perfil |
| [endpoints/usuarios.md](endpoints/usuarios.md) | `/api/usuarios/*`: cadastro de usuários |
| [endpoints/setores.md](endpoints/setores.md) | `/api/setores/*`: setores e membros |
| [endpoints/acl.md](endpoints/acl.md) | `/api/acl/*`: recursos, regras e acessos efetivos |
| [endpoints/ldap.md](endpoints/ldap.md) | `/api/ldap/diretorios/*`: diretórios LDAP |
| [endpoints/sistema.md](endpoints/sistema.md) | `/api/saude` |
| [endpoints/contratos-empresas.md](endpoints/contratos-empresas.md) | `/api/contratos/empresas/*`: empresas contratadas e prepostos |
| [endpoints/contratos-cadastro.md](endpoints/contratos-cadastro.md) | `/api/contratos/*`: carteira, cadastro, detalhe, documentos importantes e histórico |
| [endpoints/contratos-orcamento.md](endpoints/contratos-orcamento.md) | Previsão orçamentária e Notas de Empenho |
| [endpoints/contratos-execucao.md](endpoints/contratos-execucao.md) | Checklists, formulários de avaliação, competências e etapas 1 a 7 |
| [endpoints/contratos-alteracoes.md](endpoints/contratos-alteracoes.md) | Prorrogação, reajuste e aditamento/supressão |
| [endpoints/contratos-painel.md](endpoints/contratos-painel.md) | Painel, relatórios gerenciais e modelos globais |
| [endpoints/contratos-migracao-sgi.md](endpoints/contratos-migracao-sgi.md) | `/api/contratos/migracao-sgi`: botão "Importar do SGI" (SuperRoot) |
| [migracao-sgi.md](migracao-sgi.md) | Migração do Módulo de Contratos do SGI SPI (10.23.1.220): extração, carga, conferência e virada |

## Documentação automática (OpenAPI)

O FastAPI gera a especificação a partir do código. Ela permanece sempre habilitada:

| Recurso | URL |
|---|---|
| Swagger UI | `/api/documentacao` |
| ReDoc | `/api/redoc` |
| Especificação OpenAPI (JSON) | `/api/openapi.json` |

O teste `backend/tests/test_autenticacao.py::test_openapi_documenta_endpoints` falha se a lista de caminhos publicada no OpenAPI mudar sem que o teste (e esta documentação) seja atualizado.

## Regra obrigatória de manutenção

Qualquer alteração que envolva a API só está concluída quando a documentação desta pasta estiver atualizada **na mesma implementação**. Isso inclui:

- criação, alteração ou remoção de endpoint;
- alteração de parâmetros, schemas, respostas ou códigos HTTP;
- alteração de autenticação ou autorização;
- criação ou alteração de funcionalidades consumidas pelo frontend.

Fluxo para cada nova funcionalidade:

```text
Implementação → API/Endpoint → Schemas e regras → Documentação em docs/ → OpenAPI/FastAPI → Frontend Angular → Testes
```

Ao remover um endpoint, remova a seção correspondente ou marque-a como **Obsoleto**, indicando a versão e a alternativa, conforme a estratégia de versionamento que vier a ser adotada.

### Como documentar um novo endpoint

1. Crie ou atualize `docs/endpoints/<recurso>.md` seguindo o modelo de [endpoints/autenticacao.md](endpoints/autenticacao.md): finalidade, autorização, requisição, respostas, códigos HTTP, exemplos e consumo no Angular.
2. Inclua o endpoint no índice de [api.md](api.md).
3. No código, declare `summary`, `description`, `response_model` e `responses` na rota, para que o OpenAPI fique completo.
4. Atualize os testes, incluindo `test_openapi_documenta_endpoints`.

Todo o conteúdo (nomes de rotas, campos, códigos de erro e textos) é escrito em português do Brasil. Ver `AGENTS.md` na raiz do projeto.
