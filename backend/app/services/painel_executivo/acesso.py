# Criado por José Eduardo Santana Martins
# Este arquivo serve para decidir quem pode ver o Painel Executivo (SuperRoot ou quem recebeu regra no recurso ACL `painel-executivo`).
"""Acesso ao Painel Executivo.

Diferente dos demais recursos da ACL, **sem nenhuma regra o painel não fica aberto a todos**: só o SuperRoot
acessa até que o administrador conceda a regra à Diretoria (mesmo critério da triagem de Melhorias).
"""

from sqlalchemy.orm import Session

from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.services import servico_acl

RECURSO = "painel-executivo"


def pode_ver(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot, ou usuário com ao menos LEITURA numa regra do recurso `painel-executivo`."""
    if usuario.superusuario:
        return True
    if not servico_acl.possui_regras(sessao, RECURSO):
        return False
    return servico_acl.resolver_acesso(sessao, usuario, RECURSO) is not None


def exigir(sessao: Session, usuario: Usuario) -> None:
    """403 `acl_negado` quando o usuário não pode ver o painel."""
    if not pode_ver(sessao, usuario):
        raise ErroApi(403, "O Painel Executivo exige acesso ao recurso 'painel-executivo'.", "acl_negado", recurso=RECURSO)
