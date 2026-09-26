# contratos-spi: instruções para agentes

**Leia e siga `AGENTS.md`**: código em pt-BR (nomes e comentários), documentação obrigatória da API e escopo.

- Todo o sistema fica em `/home/administrador/projeto` (sem cópia em /var/www). Nginx e systemd apontam para cá; API em 127.0.0.1:8000.

- Backend FastAPI em `backend/` (venv em `backend/.venv`, testes `backend/.venv/bin/pytest -q`). Frontend Angular em `frontend/` (`npx ng test --watch=false`, `npx ng build`).
- **Regra obrigatória:** toda criação, alteração ou remoção de endpoint, parâmetro, schema, resposta, código HTTP, autenticação/autorização ou funcionalidade consumida pelo frontend deve atualizar `docs/` (em português) **na mesma alteração**. Siga o modelo de `docs/endpoints/autenticacao.md` e o índice de `docs/api.md`. Atualize também `test_openapi_documenta_endpoints`.
- **Toda alteração é registrada no `CHANGELOG.md`** (raiz) na hora: data, Adicionado/Alterado/Corrigido/Removido, migrações e endpoints. **Commit e push no Git só quando o usuário mandar**; até lá, as alterações ficam no working tree (ver `AGENTS.md`).
- Fluxo: implementação → endpoint → schemas e regras → docs/ → OpenAPI (summary, description, response_model, responses) → Angular → testes.
- Novas telas usam a identidade visual de `frontend/src/styles.scss` (referência: portal em 10.23.3.190). Não invente outra identidade.
- Novas rotas autenticadas entram como filhas da rota `''` (`LayoutAutenticadoComponent` + `guardaAutenticacao`/`guardaPerfil`) em `frontend/src/app/app.routes.ts`; módulos usam `guardaAcl`. Todo módulo novo ganha item na barra lateral em `frontend/src/app/core/navegacao/navegacao.ts` (grupo `modulos`) e recurso na ACL; no backend, `exigir_acl("slug", nivel)`.
- Senhas nunca em texto puro no código ou no `.env`: use hash bcrypt (`scripts/gerar-hash-senha.py`).
- Banco PostgreSQL via SQLAlchemy 2 + Alembic: toda alteração de modelo em `backend/app/models/` exige migração em `backend/alembic/versions/` (autogenerate + revisão manual).
- Papel administrativo é `SuperRoot` (coluna `superusuario`). Módulos existentes: autenticação (local + LDAP), perfil institucional (revalidação a cada 30 dias), usuários, setores, ACL, diretórios LDAP e servidores SMTP (envio de e-mail).
- Contrato da API, banco, variáveis de ambiente e código estão em pt-BR (ver `AGENTS.md`). Erros da API: `{"detalhe", "codigo"}`.
