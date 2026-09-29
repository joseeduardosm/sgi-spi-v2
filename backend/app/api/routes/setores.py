# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de cadastro de setores e membros.
"""Rotas de setores (`/api/setores`).

Setores representam a estrutura institucional (com setor pai e líder) e também "grupos
sistêmicos". Eles servem de grupos de acesso na ACL: uma regra dada a um setor vale para todos
os membros. Consultar exige ACL `setores` ≥ LEITURA; alterar é exclusivo do SuperRoot.
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_gestao
from app.models.setor import Setor
from app.core.erros import ErroApi
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.setores import DetalheSetor, GravacaoSetor, LeituraSetor
from app.services import servico_setores as servico
from app.services.servico_setores import ErroRegraSetor, SetorNaoEncontrado

roteador = APIRouter(prefix="/setores", tags=["Setores"], responses=RESPOSTAS_AUTENTICADAS)

# Dependências de acesso reutilizadas nas rotas abaixo
pode_ler = exigir_acl("setores", NivelAcl.LEITURA)
pode_gerir = exigir_gestao("setores")


def _restricoes_nao_superroot(sessao: Session, autor: Usuario, dados: GravacaoSetor | None = None, setor_id: int | None = None) -> None:
    """Quem gere setores pela ACL (ex.: a CGP) não mexe nos grupos sistêmicos (Administradores, Auditores…),
    que dão acessos no sistema: só o SuperRoot."""
    if autor.superusuario:
        return
    atual = sessao.get(Setor, setor_id) if setor_id is not None else None
    if (dados is not None and dados.sistemico) or (atual is not None and atual.sistemico):
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Somente um SuperRoot pode criar, alterar ou excluir grupos sistêmicos.", "acesso_negado")
NAO_ENCONTRADO = resposta_nao_encontrado("Setor")


@roteador.get("", response_model=list[LeituraSetor], summary="Listar setores", description="Exige ACL `setores` ≥ LEITURA.")
def listar_setores(
    busca: str | None = Query(None, max_length=100), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)
) -> list[LeituraSetor]:
    """Todos os setores em ordem alfabética, com contagem de membros e subordinados."""
    return servico.listar_setores(sessao, busca)


@roteador.get("/{setor_id}", response_model=DetalheSetor, summary="Consultar setor com membros", responses=NAO_ENCONTRADO)
def consultar_setor(setor_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> DetalheSetor:
    """Detalhe do setor com a lista de membros."""
    try:
        return servico.detalhar_setor(sessao, setor_id)
    except SetorNaoEncontrado:
        raise nao_encontrado("Setor")


@roteador.post(
    "",
    response_model=DetalheSetor,
    status_code=status.HTTP_201_CREATED,
    summary="Criar setor",
    description="SuperRoot, ou CONTROLE_TOTAL na ACL `setores` (grupos sistêmicos: só SuperRoot).",
    responses={**CONFLITO, **INVALIDO},
)
def criar_setor(dados: GravacaoSetor, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)) -> DetalheSetor:
    """Cria o setor e devolve o detalhe já com os membros informados."""
    _restricoes_nao_superroot(sessao, autor, dados)
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
    description="`membros_ids` substitui a lista de membros. SuperRoot, ou CONTROLE_TOTAL na ACL `setores` (grupos sistêmicos: só SuperRoot).",
    responses={**NAO_ENCONTRADO, **CONFLITO, **INVALIDO},
)
def alterar_setor(setor_id: int, dados: GravacaoSetor, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)) -> DetalheSetor:
    """Altera os dados e substitui a lista de membros pela enviada."""
    _restricoes_nao_superroot(sessao, autor, dados, setor_id)
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
    description="Somente setores sem membros e sem subordinados. SuperRoot, ou CONTROLE_TOTAL na ACL `setores` (grupos sistêmicos: só SuperRoot).",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def excluir_setor(setor_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_gerir)) -> Response:
    """Exclui o setor (o serviço recusa se ele ainda tiver membros ou setores subordinados)."""
    _restricoes_nao_superroot(sessao, autor, setor_id=setor_id)
    try:
        servico.excluir_setor(sessao, setor_id, autor.login)
    except SetorNaoEncontrado:
        raise nao_encontrado("Setor")
    except ErroRegraSetor as erro:
        raise erro_regra(str(erro), erro.conflito)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
