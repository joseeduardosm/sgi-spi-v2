# Criado por José Eduardo Santana Martins
# Este arquivo serve para compartilhar dependências e a conversão de erros entre as rotas do módulo de contratos.
"""Peças compartilhadas pelas rotas do módulo de contratos.

- Dependências de ACL do recurso `contratos` nos três níveis (leitura, modificação e controle total).
- Descrições prontas de respostas de erro para a documentação OpenAPI.
- `traduzir_erros`: transforma as exceções de domínio dos serviços em respostas HTTP no padrão
  `{"detalhe", "codigo"}`, para que as rotas fiquem curtas e sem blocos try/except repetidos.
"""

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

# Slug do recurso na ACL; todas as rotas do módulo conferem o nível do usuário nele
RECURSO = "contratos"
pode_ler = exigir_acl(RECURSO, NivelAcl.LEITURA)
pode_modificar = exigir_acl(RECURSO, NivelAcl.MODIFICACAO)
controle_total = exigir_acl(RECURSO, NivelAcl.CONTROLE_TOTAL)

# Documentação do 403: além da ACL, o serviço confere se o usuário tem vínculo com o contrato
SEM_VINCULO = {
    status.HTTP_403_FORBIDDEN: {
        "model": RespostaErro,
        "description": "ACL insuficiente (`acl_negado`) ou usuário sem vínculo com o contrato (`acesso_negado`): "
        "só o criador, a equipe vigente ou o SuperRoot alteram o contrato.",
    }
}
# Documentação do 400 das rotas que recebem PDF
ARQUIVO_RECUSADO = {
    status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Regra violada ou arquivo recusado (não é PDF, vazio, grande demais) (`invalido`)."}
}


@contextmanager
def traduzir_erros(sessao: Session | None = None) -> Iterator[None]:
    """Converte as exceções de domínio no formato de erro da API, desfazendo a transação."""
    # Cada tipo de exceção de domínio vira um código HTTP. O rollback evita que uma gravação
    # parcial feita antes do erro seja confirmada no fim da requisição.
    try:
        yield
    # Registro inexistente (contrato, item, competência...) → 404
    except RegistroNaoEncontrado as erro:
        if sessao:
            sessao.rollback()
        raise nao_encontrado(erro.o_que) from erro
    # Regra de negócio violada → 400, ou 409 quando for conflito (ex.: duplicidade)
    except ErroRegraContrato as erro:
        if sessao:
            sessao.rollback()
        raise erro_regra(str(erro), erro.conflito) from erro
    # Usuário sem vínculo com o contrato (não é criador, equipe nem SuperRoot) → 403
    except SemPermissaoContrato as erro:
        if sessao:
            sessao.rollback()
        raise ErroApi(status.HTTP_403_FORBIDDEN, str(erro), "acesso_negado") from erro
    # PDF recusado pelo serviço de anexos (vazio, grande demais, não é PDF) → 400
    except ErroAnexo as erro:
        if sessao:
            sessao.rollback()
        raise erro_regra(str(erro), False) from erro


def arquivo_pdf(arquivo: UploadFile) -> tuple:
    """(conteúdo, nome original) de um upload para o serviço de anexos."""
    # O serviço lê o arquivo como fluxo (sem carregar tudo na memória); sem nome, usa um padrão
    return arquivo.file, arquivo.filename or "documento.pdf"
