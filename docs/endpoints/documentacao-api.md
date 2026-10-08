# Documentação da API (`/api/openapi.json`, `/api/documentacao`, `/api/redoc`)

Implementação: `backend/app/api/routes/documentacao.py` (as rotas automáticas do FastAPI ficam desligadas em `main.py`). Migração `c6e0a4b8d2f1` cria o recurso de ACL `documentacao-api`.

## Acesso

- **`GET /api/openapi.json`**: exige token Bearer e ACL `documentacao-api` ≥ LEITURA. `401` sem token; `403` (`acl_negado`) sem permissão. SuperRoot sempre acessa.
- **`GET /api/documentacao`** (Swagger UI) e **`GET /api/redoc`** (ReDoc): páginas HTML **sem nenhum dado**. O navegador não envia token ao abrir uma página, então o script da página lê a sessão do SGI no `localStorage` (mesmo endereço do portal), baixa o `openapi.json` com o token e desenha a documentação. Sem sessão, com sessão expirada ou sem a ACL, aparece um aviso explicativo. No Swagger, o token da sessão vai em todas as chamadas do "Try it out" (não é preciso usar o botão Authorize).
- O recurso nasce **fechado**: regra CONTROLE_TOTAL só para a conta administrativa; o SuperRoot libera usuários e setores em Controle de acesso. O item "Documentação da API" do menu lateral aparece para quem tem o recurso.
- As três rotas não aparecem na própria especificação.
