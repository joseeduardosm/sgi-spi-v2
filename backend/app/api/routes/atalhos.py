# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor os atalhos fixos da barra lateral (leitura para todos e cadastro por ACL).
"""Atalhos fixos (`/api/atalhos`): todo usuário autenticado lê os ativos; criar, alterar e excluir exige o recurso de ACL `atalhos` ≥ MODIFICACAO."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencias import exigir_acl, obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.atalho_fixo import AtalhoFixo, CategoriaAtalho
from app.models.usuario import Usuario
from app.schemas.atalhos import (
    GravacaoAtalho,
    GravacaoCategoriaAtalho,
    LeituraAtalho,
    LeituraCategoriaAtalho,
    ListaAtalhos,
)
from app.services.servico_auditoria import auditar

roteador = APIRouter(prefix="/atalhos", tags=["Atalhos"], responses=RESPOSTAS_AUTENTICADAS)
gerencia = exigir_acl("atalhos", NivelAcl.MODIFICACAO)
NAO_ENCONTRADO = resposta_nao_encontrado("Atalho ou categoria")


def _atalho(a: AtalhoFixo) -> LeituraAtalho:
    return LeituraAtalho(id=a.id, categoria_id=a.categoria_id, titulo=a.titulo, url=a.url, externo=not a.url.startswith("/"), nova_aba=a.nova_aba,
                         ordem=a.ordem, ativo=a.ativo)


def _categoria(c: CategoriaAtalho, so_ativos: bool) -> LeituraCategoriaAtalho:
    return LeituraCategoriaAtalho(id=c.id, nome=c.nome, ordem=c.ordem, ativo=c.ativo,
                                  atalhos=[_atalho(a) for a in c.atalhos if a.ativo or not so_ativos])


def _lista(sessao: Session, so_ativos: bool) -> ListaAtalhos:
    consulta = select(CategoriaAtalho).options(selectinload(CategoriaAtalho.atalhos)).order_by(CategoriaAtalho.ordem, func.lower(CategoriaAtalho.nome))
    if so_ativos:
        consulta = consulta.where(CategoriaAtalho.ativo.is_(True))
    categorias = [_categoria(c, so_ativos) for c in sessao.scalars(consulta)]
    # Na leitura comum, categoria sem nenhum atalho ativo não aparece na barra lateral
    return ListaAtalhos(categorias=[c for c in categorias if c.atalhos or not so_ativos])


@roteador.get("", response_model=ListaAtalhos, summary="Atalhos fixos da barra lateral",
              description="Categorias e atalhos **ativos**, na ordem de exibição (categorias sem atalho ativo ficam de fora). Qualquer usuário autenticado.")
def listar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> ListaAtalhos:
    """Atalhos para montar o grupo dobrável "Atalhos" da barra lateral."""
    return _lista(sessao, so_ativos=True)


@roteador.get("/gestao", response_model=ListaAtalhos, summary="Atalhos para gerenciar (inclui inativos)",
              description="Todas as categorias e atalhos, inclusive os inativos e as categorias vazias. Exige ACL `atalhos` ≥ MODIFICACAO.")
def listar_gestao(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(gerencia)) -> ListaAtalhos:
    """Lista completa para a tela de cadastro."""
    return _lista(sessao, so_ativos=False)


def _nome_unico(sessao: Session, nome: str, exceto: int | None = None) -> None:
    existente = sessao.scalar(select(CategoriaAtalho.id).where(func.lower(CategoriaAtalho.nome) == nome.lower()))
    if existente is not None and existente != exceto:
        raise ErroApi(status.HTTP_409_CONFLICT, "Já existe uma categoria com esse nome.", "conflito")


@roteador.post("/categorias", response_model=LeituraCategoriaAtalho, status_code=status.HTTP_201_CREATED, summary="Criar categoria",
               responses={**VALIDACAO, status.HTTP_409_CONFLICT: {"description": "Já existe categoria com o mesmo nome (`conflito`)."}},
               description="Exige ACL `atalhos` ≥ MODIFICACAO. O nome é único (sem diferenciar maiúsculas).")
def criar_categoria(dados: GravacaoCategoriaAtalho, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> LeituraCategoriaAtalho:
    _nome_unico(sessao, dados.nome)
    categoria = CategoriaAtalho(nome=dados.nome, ordem=dados.ordem, ativo=dados.ativo)
    sessao.add(categoria)
    sessao.flush()
    auditar(sessao, autor.login, "atalho.categoria.criar", categoria.nome, autor_id=autor.id, alvo_tipo="atalho_categoria", alvo_id=categoria.id)
    sessao.commit()
    return _categoria(categoria, so_ativos=False)


@roteador.put("/categorias/{categoria_id}", response_model=LeituraCategoriaAtalho, summary="Alterar categoria",
              responses={**NAO_ENCONTRADO, **VALIDACAO, status.HTTP_409_CONFLICT: {"description": "Nome já usado (`conflito`)."}},
              description="Exige ACL `atalhos` ≥ MODIFICACAO.")
def alterar_categoria(categoria_id: int, dados: GravacaoCategoriaAtalho, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(gerencia)) -> LeituraCategoriaAtalho:
    categoria = sessao.get(CategoriaAtalho, categoria_id)
    if categoria is None:
        raise nao_encontrado("Categoria")
    _nome_unico(sessao, dados.nome, categoria.id)
    categoria.nome, categoria.ordem, categoria.ativo = dados.nome, dados.ordem, dados.ativo
    auditar(sessao, autor.login, "atalho.categoria.alterar", categoria.nome, autor_id=autor.id, alvo_tipo="atalho_categoria", alvo_id=categoria.id)
    sessao.commit()
    return _categoria(categoria, so_ativos=False)


@roteador.delete("/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir categoria",
                 responses=NAO_ENCONTRADO, description="Exclui também todos os atalhos da categoria. Exige ACL `atalhos` ≥ MODIFICACAO.")
def excluir_categoria(categoria_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> Response:
    categoria = sessao.get(CategoriaAtalho, categoria_id)
    if categoria is None:
        raise nao_encontrado("Categoria")
    auditar(sessao, autor.login, "atalho.categoria.excluir", categoria.nome, f"{len(categoria.atalhos)} atalho(s)", autor_id=autor.id,
            alvo_tipo="atalho_categoria", alvo_id=categoria.id)
    sessao.delete(categoria)
    sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _aplicar(atalho: AtalhoFixo, dados: GravacaoAtalho) -> None:
    atalho.categoria_id, atalho.titulo, atalho.url, atalho.ordem, atalho.ativo = dados.categoria_id, dados.titulo, dados.url, dados.ordem, dados.ativo
    # Sem escolha: externo abre em nova aba; interno, na mesma
    atalho.nova_aba = dados.nova_aba if dados.nova_aba is not None else not dados.url.startswith("/")


@roteador.post("/itens", response_model=LeituraAtalho, status_code=status.HTTP_201_CREATED, summary="Criar atalho",
               responses={**NAO_ENCONTRADO, **VALIDACAO}, description="`url`: rota interna (`/contratos`) ou `http(s)://…` (outros esquemas, como `javascript:`, são recusados). "
               "Exige ACL `atalhos` ≥ MODIFICACAO.")
def criar_atalho(dados: GravacaoAtalho, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> LeituraAtalho:
    if sessao.get(CategoriaAtalho, dados.categoria_id) is None:
        raise nao_encontrado("Categoria")
    atalho = AtalhoFixo()
    _aplicar(atalho, dados)
    sessao.add(atalho)
    sessao.flush()
    auditar(sessao, autor.login, "atalho.criar", atalho.titulo, atalho.url, autor_id=autor.id, alvo_tipo="atalho", alvo_id=atalho.id)
    sessao.commit()
    return _atalho(atalho)


@roteador.put("/itens/{atalho_id}", response_model=LeituraAtalho, summary="Alterar atalho", responses={**NAO_ENCONTRADO, **VALIDACAO},
              description="Exige ACL `atalhos` ≥ MODIFICACAO. Pode mudar de categoria.")
def alterar_atalho(atalho_id: int, dados: GravacaoAtalho, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> LeituraAtalho:
    atalho = sessao.get(AtalhoFixo, atalho_id)
    if atalho is None or sessao.get(CategoriaAtalho, dados.categoria_id) is None:
        raise nao_encontrado("Atalho ou categoria")
    _aplicar(atalho, dados)
    auditar(sessao, autor.login, "atalho.alterar", atalho.titulo, atalho.url, autor_id=autor.id, alvo_tipo="atalho", alvo_id=atalho.id)
    sessao.commit()
    return _atalho(atalho)


@roteador.delete("/itens/{atalho_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir atalho", responses=NAO_ENCONTRADO,
                 description="Exige ACL `atalhos` ≥ MODIFICACAO.")
def excluir_atalho(atalho_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> Response:
    atalho = sessao.get(AtalhoFixo, atalho_id)
    if atalho is None:
        raise nao_encontrado("Atalho")
    auditar(sessao, autor.login, "atalho.excluir", atalho.titulo, atalho.url, autor_id=autor.id, alvo_tipo="atalho", alvo_id=atalho.id)
    sessao.delete(atalho)
    sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
