# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de administração dos servidores SMTP.
"""Rotas dos servidores SMTP (`/api/smtp/servidores`), exclusivas do SuperRoot.

Um servidor guarda como o portal envia e-mail (endereço, porta, segurança, conta e remetente).
Só um fica ativo por vez: é por ele que os módulos do sistema enviam mensagens.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.servidor_smtp import ServidorSmtp
from app.models.usuario import Papel, Usuario
from app.schemas.smtp import (
    AlteracaoServidorSmtp,
    CriacaoServidorSmtp,
    EnvioTeste,
    LeituraServidorSmtp,
    ResultadoSmtp,
    SenhaTemporaria,
    TesteServidorNaoSalvo,
)
from app.services import servico_smtp
from app.services.cliente_smtp import ErroSmtp
from app.services.servico_smtp import ServidorNaoEncontrado

roteador = APIRouter(prefix="/smtp/servidores", tags=["Servidores SMTP"], responses=RESPOSTAS_AUTENTICADAS)

super_root = exigir_papeis(Papel.SUPER_ROOT)
NAO_ENCONTRADO = resposta_nao_encontrado("Servidor SMTP")


def _obter(sessao: Session, servidor_id: uuid.UUID) -> ServidorSmtp:
    """Servidor pelo id, ou 404 se não existir."""
    try:
        return servico_smtp.obter_servidor(sessao, servidor_id)
    except ServidorNaoEncontrado:
        raise nao_encontrado("Servidor SMTP")


@roteador.get("", response_model=list[LeituraServidorSmtp], summary="Listar servidores SMTP")
def listar_servidores(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> list[ServidorSmtp]:
    """Todos os servidores cadastrados (a senha nunca é devolvida)."""
    return servico_smtp.listar_servidores(sessao)


@roteador.post(
    "",
    response_model=LeituraServidorSmtp,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar servidor SMTP",
    description="Cifra a senha antes de gravar. Se `ativo` for verdadeiro, desativa os demais.",
    responses=INVALIDO,
)
def criar_servidor(dados: CriacaoServidorSmtp, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> ServidorSmtp:
    """Cadastra o servidor."""
    return servico_smtp.criar_servidor(sessao, dados, autor.login)


@roteador.post(
    "/testar",
    response_model=ResultadoSmtp,
    summary="Testar configuração sem salvar",
    description="Conecta, negocia a segurança e autentica com os dados do formulário, sem gravar nada e sem enviar e-mail.",
)
def testar_sem_salvar(dados: TesteServidorNaoSalvo, _: Usuario = Depends(super_root)) -> ResultadoSmtp:
    """Permite testar os dados do formulário antes de gravar."""
    return ResultadoSmtp(**servico_smtp.testar_parametros(dados).__dict__)


@roteador.get("/{servidor_id}", response_model=LeituraServidorSmtp, summary="Consultar servidor SMTP", responses=NAO_ENCONTRADO)
def consultar_servidor(servidor_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> ServidorSmtp:
    """Detalhe de um servidor."""
    return _obter(sessao, servidor_id)


@roteador.put(
    "/{servidor_id}",
    response_model=LeituraServidorSmtp,
    summary="Alterar servidor SMTP",
    description="`senha` vazia ou ausente preserva a atual; sem `usuario`, a senha gravada é descartada. Ativar um servidor desativa os demais.",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def alterar_servidor(
    servidor_id: uuid.UUID, dados: AlteracaoServidorSmtp, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)
) -> ServidorSmtp:
    """Altera a configuração."""
    _obter(sessao, servidor_id)
    try:
        return servico_smtp.alterar_servidor(sessao, servidor_id, dados, autor.login)
    except ErroSmtp as erro:
        sessao.rollback()
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro


@roteador.delete("/{servidor_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir servidor SMTP", responses=NAO_ENCONTRADO)
def excluir_servidor(servidor_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> Response:
    """Exclui o servidor."""
    _obter(sessao, servidor_id)
    servico_smtp.excluir_servidor(sessao, servidor_id, autor.login)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post(
    "/{servidor_id}/testar",
    response_model=ResultadoSmtp,
    summary="Testar conexão",
    description="Conecta, negocia a segurança e autentica com a configuração salva (sem enviar e-mail); registra data, resultado, tempo e erro.",
    responses=NAO_ENCONTRADO,
)
def testar_servidor(
    servidor_id: uuid.UUID, dados: SenhaTemporaria | None = None, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)
) -> ResultadoSmtp:
    """Testa o servidor salvo; opcionalmente com uma senha digitada na hora (não gravada)."""
    _obter(sessao, servidor_id)
    return ResultadoSmtp(**servico_smtp.testar_servidor(sessao, servidor_id, dados.senha if dados else None).__dict__)


@roteador.post(
    "/{servidor_id}/enviar-teste",
    response_model=ResultadoSmtp,
    summary="Enviar e-mail de teste",
    description="Envia uma mensagem de teste ao destinatário informado pela configuração salva e registra o resultado.",
    responses={**NAO_ENCONTRADO, **INVALIDO},
)
def enviar_teste(
    servidor_id: uuid.UUID, dados: EnvioTeste, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)
) -> ResultadoSmtp:
    """Prova de ponta a ponta: a mensagem precisa chegar à caixa do destinatário."""
    _obter(sessao, servidor_id)
    return ResultadoSmtp(**servico_smtp.enviar_teste(sessao, servidor_id, dados.destinatario, autor.login).__dict__)
