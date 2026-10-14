# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir o que os serviços do Patrimônio compartilham: erro, permissões, histórico do bem e avisos.
"""Base comum do módulo Patrimônio.

- `ErroPatrimonio`: regra violada (vira `400`, ou o `status` indicado).
- `controle_total` / `ids_controle_total`: quem administra o módulo (CONTROLE_TOTAL no recurso `patrimonio` ou SuperRoot).
- `registrar_evento`: grava no histórico do bem (somente inserção; o banco barra UPDATE e DELETE).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.acl import NivelAcl
from app.models.patrimonio import Bem, EventoPatrimonio, ParametroPatrimonio
from app.models.usuario import Usuario
from app.services import servico_acl, notificacoes

RECURSO = "patrimonio"
# Valor da UFESP (R$) usado na regra de "não patrimoniável" (abaixo de 45 UFESP e vida útil menor que dois anos); editável pelo controle total
UFESP_PADRAO = "37.02"
LIMITE_UFESP = 45
PARAMETROS_PADRAO = {"ufesp": UFESP_PADRAO}


class ErroPatrimonio(Exception):
    """Regra do Patrimônio violada (vira 400, ou o `status` indicado)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def nome_do_autor(usuario: Usuario | None) -> str:
    if usuario is None:
        return "Sistema"
    return usuario.nome_completo or usuario.login


def controle_total(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL no recurso `patrimonio`."""
    return usuario.superusuario or servico_acl.resolver_acesso(sessao, usuario, RECURSO) == NivelAcl.CONTROLE_TOTAL


def ids_controle_total(sessao: Session) -> list[int]:
    """Usuários ativos que autorizam (para os avisos de solicitações pendentes)."""
    usuarios = sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True)))
    return [u.id for u in usuarios if controle_total(sessao, u)]


def exigir_outra_pessoa(autor: Usuario, solicitante_id: int | None) -> None:
    """Quem solicita nunca aprova a própria solicitação, mesmo com controle total."""
    if solicitante_id is not None and solicitante_id == autor.id:
        raise ErroPatrimonio("Quem solicitou não pode aprovar ou recusar a própria solicitação.", 403, "auto_aprovacao")


def parametro(sessao: Session, chave: str) -> str:
    linha = sessao.get(ParametroPatrimonio, chave)
    return linha.valor if linha is not None else PARAMETROS_PADRAO[chave]


def registrar_evento(
    sessao: Session, bem: Bem, tipo: str, autor: Usuario | None, *, campo: str | None = None, anterior: Any = None, novo: Any = None,
    texto: str = "", dados: dict | None = None, origem: str | None = None, quando: datetime | None = None,
) -> EventoPatrimonio:
    """Uma linha no histórico do bem (sem commit: grava junto com a operação)."""
    evento = EventoPatrimonio(
        id=uuid.uuid4(), bem_id=bem.id, tipo=tipo, campo=campo, valor_anterior=None if anterior is None else str(anterior),
        valor_novo=None if novo is None else str(novo), autor_id=autor.id if autor else None, autor_nome=nome_do_autor(autor), origem=origem,
        texto=texto, dados=dados, ocorrido_em=quando or agora_utc(),
    )
    sessao.add(evento)
    return evento


def avisar(sessao: Session, destinatarios: list[int], assunto: str, corpo: str, chave: str, autor: Usuario | None = None, link: str | None = None, categoria: str = "comunicado", *, evento: str) -> None:
    """Aviso automático do módulo (sem repetir a mesma `chave` para quem já recebeu). Pedidos a aprovar usam a categoria `pendencia`."""
    notificacoes.notificar(sessao, destinatarios, assunto, corpo, chave=chave, categoria=categoria, link=link or "/patrimonio", autor=autor, evento=evento)
