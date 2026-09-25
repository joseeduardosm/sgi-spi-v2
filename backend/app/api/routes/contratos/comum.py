# Criado por José Eduardo Santana Martins
# Este arquivo serve para compartilhar dependências e a conversão de erros entre as rotas do módulo de contratos.
"""Dependências e conversão de erros compartilhadas pelas rotas do módulo de contratos."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import erro_regra, nao_encontrado
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.schemas.comum import RespostaErro
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.servico_anexos import ErroAnexo

RECURSO = "contratos"
pode_ler = exigir_acl(RECURSO, NivelAcl.LEITURA)
pode_modificar = exigir_acl(RECURSO, NivelAcl.MODIFICACAO)
controle_total = exigir_acl(RECURSO, NivelAcl.CONTROLE_TOTAL)

SEM_VINCULO = {
    status.HTTP_403_FORBIDDEN: {
        "model": RespostaErro,
        "description": "ACL insuficiente (`acl_negado`) ou usuário sem vínculo com o contrato (`acesso_negado`): "
        "só o criador, a equipe vigente ou o SuperRoot alteram o contrato.",
    }
}
ARQUIVO_RECUSADO = {
    status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Regra violada ou arquivo recusado (não é PDF, vazio, grande demais) (`invalido`)."}
}


@contextmanager
def traduzir_erros(sessao: Session | None = None) -> Iterator[None]:
    """Converte as exceções de domínio no formato de erro da API, desfazendo a transação."""
    try:
        yield
    except RegistroNaoEncontrado as erro:
        if sessao:
            sessao.rollback()
        raise nao_encontrado(erro.o_que) from erro
    except ErroRegraContrato as erro:
        if sessao:
            sessao.rollback()
        raise erro_regra(str(erro), erro.conflito) from erro
    except SemPermissaoContrato as erro:
        if sessao:
            sessao.rollback()
        raise ErroApi(status.HTTP_403_FORBIDDEN, str(erro), "acesso_negado") from erro
    except ErroAnexo as erro:
        if sessao:
            sessao.rollback()
        raise erro_regra(str(erro), False) from erro


def arquivo_pdf(arquivo: UploadFile) -> tuple:
    """(conteúdo, nome original) de um upload para o serviço de anexos."""
    return arquivo.file, arquivo.filename or "documento.pdf"
