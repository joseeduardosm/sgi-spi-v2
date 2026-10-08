# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor os manuais do BookStack lidos pelo portal (estantes, livros, páginas, busca e imagens).
"""Manuais (`/api/manuais`): conteúdo do BookStack exibido dentro do portal, somente leitura.

Acesso: ACL `manuais` ≥ LEITURA (o recurso nasce sem regras, ou seja, aberto a todo usuário autenticado). O portal lê o BookStack com uma
conta de serviço; o usuário não precisa de conta lá. Erros: `503 manuais_indisponivel` (integração desligada ou sem token),
`502 bookstack_indisponivel` (BookStack fora do ar ou recusou o token) e `404 nao_encontrado`.
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.comum import RespostaErro
from app.schemas.manuais import DetalheLivro, DetalhePagina, ListaManuais, ResultadoBuscaManuais
from app.services import servico_manuais as servico

roteador = APIRouter(prefix="/manuais", tags=["Manuais (BookStack)"], responses=RESPOSTAS_AUTENTICADAS)
pode_ler = exigir_acl("manuais", NivelAcl.LEITURA)

INDISPONIVEL = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": RespostaErro, "description": "Integração desligada ou sem token (`manuais_indisponivel`)."},
    status.HTTP_502_BAD_GATEWAY: {"model": RespostaErro, "description": "O BookStack não respondeu ou recusou o token (`bookstack_indisponivel`)."},
}
NAO_ENCONTRADO = {status.HTTP_404_NOT_FOUND: {"model": RespostaErro, "description": "Conteúdo inexistente ou fora do alcance da conta de serviço (`nao_encontrado`)."}}


@roteador.get("", response_model=ListaManuais, summary="Estantes e livros dos manuais", responses=INDISPONIVEL,
              description="Estantes com seus livros e os livros sem estante, em ordem alfabética (cache de alguns minutos). Exige ACL `manuais` ≥ LEITURA.")
def listar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> ListaManuais:
    """Página inicial dos manuais."""
    return servico.listar(sessao)


@roteador.get("/busca", response_model=ResultadoBuscaManuais, summary="Buscar nos manuais", responses=INDISPONIVEL,
              description="Usa a busca do BookStack (até 30 resultados de páginas, capítulos e livros). Menos de 2 caracteres devolve lista vazia. "
              "O `trecho` traz o termo em `<strong>`. Exige ACL `manuais` ≥ LEITURA.")
def buscar(q: str = Query("", max_length=100, description="Termo de busca."), sessao: Session = Depends(obter_sessao),
           _: Usuario = Depends(pode_ler)) -> ResultadoBuscaManuais:
    """Busca nos manuais."""
    return servico.buscar(sessao, q)


@roteador.get("/imagem", summary="Imagem de um manual", responses={**INDISPONIVEL, **NAO_ENCONTRADO, status.HTTP_200_OK: {"content": {"image/*": {}}, "description": "A imagem."}},
              response_class=Response,
              description="Repassa uma imagem de `/uploads/...` do BookStack (o navegador não tem o token). `caminho` fora de `/uploads/` ou com `..` "
              "responde `400`. Exige ACL `manuais` ≥ LEITURA.")
def imagem(caminho: str = Query(..., max_length=400, description="Caminho da imagem, ex.: `/uploads/images/gallery/2026-01/foto.png`."),
           sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> Response:
    """Bytes da imagem, com cache privado de 1 hora."""
    conteudo, tipo = servico.imagem(sessao, caminho)
    return Response(content=conteudo, media_type=tipo, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@roteador.get("/livros/{livro_id}", response_model=DetalheLivro, summary="Sumário de um livro", responses={**INDISPONIVEL, **NAO_ENCONTRADO},
              description="Capítulos e páginas do livro, na ordem do BookStack. Exige ACL `manuais` ≥ LEITURA.")
def obter_livro(livro_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheLivro:
    """Sumário do livro."""
    return servico.livro(sessao, livro_id)


@roteador.get("/paginas/{pagina_id}", response_model=DetalhePagina, summary="Página de um manual", responses={**INDISPONIVEL, **NAO_ENCONTRADO},
              description="HTML da página já sanitizado (sem scripts, iframes ou estilos; imagens trazem `data-caminho` para baixar por `/api/manuais/imagem`), "
              "livro, capítulo, página anterior e próxima. Exige ACL `manuais` ≥ LEITURA.")
def obter_pagina(pagina_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalhePagina:
    """Página para leitura."""
    return servico.pagina(sessao, pagina_id)
