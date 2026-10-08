# Criado por José Eduardo Santana Martins
# Este arquivo serve para publicar a documentação da API (Swagger, ReDoc e OpenAPI) só para quem tem acesso na ACL.
"""Documentação da API protegida (`/api/documentacao`, `/api/redoc`, `/api/openapi.json`).

- `/api/openapi.json` exige token e o recurso de ACL `documentacao-api` ≥ LEITURA: é ele que entrega o conteúdo.
- `/api/documentacao` (Swagger) e `/api/redoc` são só a "casca" HTML, sem dado nenhum. O navegador não envia o token ao abrir uma
  página, então a casca lê a sessão do SGI no `localStorage` (mesmo endereço do portal), baixa o OpenAPI com o token e desenha a
  documentação. Sem sessão ou sem permissão, mostra um aviso em vez da documentação.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.dependencias import exigir_acl
from app.models.acl import NivelAcl
from app.models.usuario import Usuario

# `include_in_schema=False`: as próprias páginas de documentação não entram na especificação
roteador = APIRouter(include_in_schema=False)

# Slug do recurso de ACL (criado fechado pela migração; o SuperRoot libera os usuários)
RECURSO = "documentacao-api"
pode_ver = exigir_acl(RECURSO, NivelAcl.LEITURA)

# Script comum: lê o token da sessão do SGI, baixa o OpenAPI e chama `desenhar(especificacao, token)`
_SCRIPT_BASE = """
const CHAVE = 'sgi-spi.sessao';
const aviso = (texto) => { document.getElementById('aviso').textContent = texto; document.getElementById('aviso').hidden = false; };
async function iniciar() {
  let token = null;
  try { token = JSON.parse(localStorage.getItem(CHAVE) || 'null')?.tokenAcesso || null; } catch (e) { token = null; }
  if (!token) return aviso('Faça login no SGI (portal) e abra esta página de novo.');
  const resposta = await fetch('/api/openapi.json', { headers: { Authorization: 'Bearer ' + token } });
  if (resposta.status === 401) return aviso('Sua sessão expirou. Entre no SGI de novo e abra esta página outra vez.');
  if (resposta.status === 403) return aviso('Você não tem acesso à documentação da API. Peça a liberação ao administrador (recurso "documentacao-api").');
  if (!resposta.ok) return aviso('Não foi possível carregar a especificação da API (código ' + resposta.status + ').');
  desenhar(await resposta.json(), token);
}
iniciar().catch(() => aviso('Não foi possível carregar a documentação.'));
"""

_MOLDE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
{cabecalho}
<style>body{{margin:0;font-family:sans-serif}}#aviso{{margin:40px auto;max-width:560px;padding:16px 20px;border:1px solid #e2c4c7;border-radius:8px;background:#fcf3f4;color:#6b2a30}}</style>
</head>
<body>
<p id="aviso" hidden></p>
{corpo}
<script>
{desenho}
{base}
</script>
</body>
</html>"""

_SWAGGER = _MOLDE.format(
    titulo="API SGI SPI – Swagger",
    cabecalho='<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">',
    corpo='<div id="swagger-ui"></div>\n<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>',
    # O token da sessão vai em toda chamada feita pelo "Try it out" (o botão Authorize não é necessário)
    desenho="""function desenhar(especificacao, token) {
  SwaggerUIBundle({
    spec: especificacao,
    dom_id: '#swagger-ui',
    presets: [SwaggerUIBundle.presets.apis],
    requestInterceptor: (req) => { req.headers['Authorization'] = 'Bearer ' + token; return req; },
  });
}""",
    base=_SCRIPT_BASE,
)

_REDOC = _MOLDE.format(
    titulo="API SGI SPI – ReDoc",
    cabecalho="",
    corpo='<div id="redoc"></div>\n<script src="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js"></script>',
    desenho="function desenhar(especificacao) { Redoc.init(especificacao, {}, document.getElementById('redoc')); }",
    base=_SCRIPT_BASE,
)

# Páginas não podem ficar em cache: a casca é pública, mas nunca deve ser guardada com dados
_SEM_CACHE = {"Cache-Control": "no-store"}


@roteador.get("/openapi.json")
def especificacao(request: Request, _: Usuario = Depends(pode_ver)) -> JSONResponse:
    """Especificação OpenAPI da API, só para quem tem o recurso `documentacao-api`."""
    return JSONResponse(request.app.openapi())


@roteador.get("/documentacao", response_class=HTMLResponse)
def swagger() -> HTMLResponse:
    """Casca do Swagger UI: carrega a especificação com o token da sessão do SGI."""
    return HTMLResponse(_SWAGGER, headers=_SEM_CACHE)


@roteador.get("/redoc", response_class=HTMLResponse)
def redoc() -> HTMLResponse:
    """Casca do ReDoc: carrega a especificação com o token da sessão do SGI."""
    return HTMLResponse(_REDOC, headers=_SEM_CACHE)
