from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_papeis
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Papel, Usuario
from app.schemas.setores import DetalheSetor, GravacaoSetor, LeituraSetor
from app.services import servico_setores as servico
from app.services.servico_setores import ErroRegraSetor, SetorNaoEncontrado

roteador = APIRouter(prefix="/setores", tags=["Setores"], responses=RESPOSTAS_AUTENTICADAS)

pode_ler = exigir_acl("setores", NivelAcl.LEITURA)
super_root = exigir_papeis(Papel.SUPER_ROOT)
NAO_ENCONTRADO = resposta_nao_encontrado("Setor")


@roteador.get("", response_model=list[LeituraSetor], summary="Listar setores", description="Exige ACL `setores` ≥ LEITURA.")
def listar_setores(
    busca: str | None = Query(None, max_length=100), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)
) -> list[LeituraSetor]:
    return servico.listar_setores(sessao, busca)


@roteador.get("/{setor_id}", response_model=DetalheSetor, summary="Consultar setor com membros", responses=NAO_ENCONTRADO)
def consultar_setor(setor_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheSetor:
    try:
        return servico.detalhar_setor(sessao, setor_id)
    except SetorNaoEncontrado:
        raise nao_encontrado("Setor")


@roteador.post(
    "",
    response_model=DetalheSetor,
    status_code=status.HTTP_201_CREATED,
    summary="Criar setor",
    description="Restrito ao SuperRoot.",
    responses={**CONFLITO, **INVALIDO},
)
def criar_setor(dados: GravacaoSetor, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> DetalheSetor:
    try:
        setor = servico.criar_setor(sessao, dados, autor.login)
    except ErroRegraSetor as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)
    return servico.detalhar_setor(sessao, setor.id)


@roteador.put(
    "/{setor_id}",
    response_model=DetalheSetor,
    summary="Alterar setor",
    description="`membros_ids` substitui a lista de membros. Restrito ao SuperRoot.",
    responses={**NAO_ENCONTRADO, **CONFLITO, **INVALIDO},
)
def alterar_setor(setor_id: int, dados: GravacaoSetor, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> DetalheSetor:
    try:
        servico.alterar_setor(sessao, setor_id, dados, autor.login)
    except SetorNaoEncontrado:
        raise nao_encontrado("Setor")
    except ErroRegraSetor as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito)
    return servico.detalhar_setor(sessao, setor_id)


@roteador.delete(
    "/{setor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir setor",
    description="Somente setores sem membros e sem subordinados. Restrito ao SuperRoot.",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def excluir_setor(setor_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    try:
        servico.excluir_setor(sessao, setor_id, autor.login)
    except SetorNaoEncontrado:
        raise nao_encontrado("Setor")
    except ErroRegraSetor as erro:
        raise erro_regra(str(erro), erro.conflito)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
