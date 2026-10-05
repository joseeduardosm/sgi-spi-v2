# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a abertura de chamado pelo SGI (o chamado é criado no GLPI).
"""Chamados (`/api/chamados`): todo usuário autenticado abre chamado pelo SGI (ACL `abrir-chamado`, sem regras = aberta a todos)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.chamados import AberturaChamado, ChamadoAberto, DadosSolicitante, ListaChamados, ListaLocais, LocalChamado
from app.schemas.comum import RespostaErro
from app.services import servico_chamados

roteador = APIRouter(prefix="/chamados", tags=["Chamados (GLPI)"], responses=RESPOSTAS_AUTENTICADAS)
pode_abrir = exigir_acl("abrir-chamado", NivelAcl.LEITURA)

ERROS_ABERTURA = {
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": RespostaErro, "description": "Limite de 5 chamados por hora atingido (`limite_excedido`)."},
    status.HTTP_502_BAD_GATEWAY: {"model": RespostaErro, "description": "O GLPI não respondeu ou recusou o pedido (`glpi_indisponivel`)."},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": RespostaErro, "description": "Integração desligada ou sem credenciais (`integracao_desativada`)."},
    **VALIDACAO,
}


@roteador.get("/solicitante", response_model=DadosSolicitante, summary="Dados que vão no chamado",
              description="Nome, setor, superior imediato, e-mail, telefone (ramal), celular (só se preenchido) e andar - lado, do cadastro do usuário logado. "
              "A tela mostra esses dados, somente leitura, no modal de abertura. Exige ACL `abrir-chamado` ≥ LEITURA (sem regras: todos).")
def solicitante(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_abrir)) -> DadosSolicitante:
    """Dados do cadastro do usuário logado."""
    return servico_chamados.dados_do_solicitante(sessao, usuario)


@roteador.get("/locais", response_model=ListaLocais, summary="Locais do problema (localizações do GLPI)", responses=ERROS_ABERTURA,
              description="Localizações do GLPI para a pergunta obrigatória \"Local do Problema\" (como no formulário do GLPI), em ordem alfabética: `{id, nome}` com o nome "
              "completo (ex.: `05º Andar > Lado B`). Exige ACL `abrir-chamado` ≥ LEITURA.")
def locais(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_abrir)) -> ListaLocais:
    """Locais para a tela montar a lista."""
    return ListaLocais(itens=[LocalChamado(id=i, nome=n) for i, n in servico_chamados.listar_locais(sessao)])


@roteador.post("", response_model=ChamadoAberto, status_code=status.HTTP_201_CREATED, summary="Abrir chamado no GLPI", responses=ERROS_ABERTURA,
               description="`multipart/form-data`: `dados` (JSON `{\"assunto\", \"descricao\", \"local_id\"}`, assunto de 3 a 200 caracteres, descrição de 10 a 5000 e o local obrigatório) e até 5 `arquivos` "
               "(imagens coladas ou escolhidas, PDF, Word .docx, Excel .xlsx ou CSV; até 5 MB cada, conferidos pelo conteúdo), anexados ao chamado. "
               "Cria o chamado no GLPI em nome do usuário (solicitante achado pelo login, depois pelo e-mail); os demais dados vêm do cadastro e o texto termina com "
               "\"Aberto pelo SGI\". Sem categoria: a TI classifica. Anexo que o GLPI recuse não desfaz a abertura: vem em `anexos_com_falha`. "
               "Limite de 5 chamados por hora por usuário. Exige ACL `abrir-chamado` ≥ LEITURA.")
async def abrir(dados: str = Form(..., description="JSON de `AberturaChamado`."), arquivos: list[UploadFile] = File(default_factory=list),
                sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_abrir)) -> ChamadoAberto:
    """Abre o chamado (com os anexos) e devolve o número e o link."""
    try:
        corpo = AberturaChamado.model_validate_json(dados)
    except ValidationError as erro:
        mensagem = erro.errors()[0].get("msg", "Dados inválidos.").removeprefix("Value error, ")
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem, "validacao") from erro
    conteudos = [(a.filename or "anexo", await a.read(servico_chamados.TAMANHO_MAXIMO_ANEXO + 1)) for a in arquivos if a.filename]
    return servico_chamados.abrir(sessao, usuario, corpo.assunto, corpo.descricao, corpo.local_id, conteudos)


@roteador.get("", response_model=ListaChamados, summary="Meus chamados abertos pelo SGI",
              description="Últimos 20 chamados que o usuário abriu pelo SGI, com o link para cada um no GLPI.")
def meus_chamados(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_abrir)) -> ListaChamados:
    """Chamados do usuário logado."""
    return servico_chamados.listar(sessao, usuario)
