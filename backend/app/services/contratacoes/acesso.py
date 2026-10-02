# Criado por José Eduardo Santana Martins
# Este arquivo serve para decidir quem vê, edita, revisa e aplica propostas em cada documento de Contratações.
"""Acesso aos documentos de Contratações.

Recurso ACL `contratacoes`: LEITURA vê os documentos em que é criador ou membro; MODIFICACAO também cria documentos;
CONTROLE_TOTAL e SuperRoot veem e administram todos. Em cada documento: o criador e os **editores** editam, aplicam propostas,
compartilham (só o criador e a administração) e concluem; os **revisores** só comentam e propõem.
"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl
from app.models.contratacoes import DocumentoContratacao, MembroDocumento
from app.models.usuario import Usuario
from app.services import servico_acl

RECURSO = "contratacoes"


class ErroContratacao(Exception):
    """Regra do módulo violada (vira 400, ou o `status` indicado)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def administra(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL no recurso: vê e administra todos os documentos."""
    return usuario.superusuario or servico_acl.resolver_acesso(sessao, usuario, RECURSO) == NivelAcl.CONTROLE_TOTAL


def papel(sessao: Session, usuario: Usuario, documento: DocumentoContratacao) -> str | None:
    """`administrador`, `criador`, `editor`, `revisor` ou None (sem acesso ao documento)."""
    if administra(sessao, usuario):
        return "administrador"
    if documento.criador_id == usuario.id:
        return "criador"
    membro = next((m for m in documento.membros if m.usuario_id == usuario.id), None)
    return membro.papel if membro else None


def exigir(sessao: Session, usuario: Usuario, documento: DocumentoContratacao, minimo: str) -> str:
    """Papel do usuário, ou erro: `ver` (qualquer papel), `revisar` (todos menos nenhum), `editar` (criador, editor, administrador)
    ou `gerir` (criador e administrador: compartilhar e excluir)."""
    atual = papel(sessao, usuario, documento)
    if atual is None:
        # Não revela que o documento existe
        raise ErroContratacao("Documento não encontrado.", 404, "nao_encontrado")
    permitidos = {
        "ver": {"administrador", "criador", "editor", "revisor"}, "revisar": {"administrador", "criador", "editor", "revisor"},
        "editar": {"administrador", "criador", "editor"}, "gerir": {"administrador", "criador"},
    }[minimo]
    if atual not in permitidos:
        raise ErroContratacao({"editar": "Só quem edita o documento pode fazer isso.", "gerir": "Só o criador ou a administração pode fazer isso."}.get(minimo, "Sem permissão."),
                              403, "sem_permissao")
    return atual


def pode_editar(papel_atual: str | None) -> bool:
    return papel_atual in ("administrador", "criador", "editor")


def obter(sessao: Session, usuario: Usuario, documento_id: uuid.UUID, minimo: str = "ver") -> tuple[DocumentoContratacao, str]:
    documento = sessao.get(DocumentoContratacao, documento_id)
    if documento is None:
        raise ErroContratacao("Documento não encontrado.", 404, "nao_encontrado")
    return documento, exigir(sessao, usuario, documento, minimo)


def visiveis(sessao: Session, usuario: Usuario):
    """Consulta dos documentos que o usuário enxerga."""
    consulta = select(DocumentoContratacao)
    if administra(sessao, usuario):
        return consulta
    membro = select(MembroDocumento.documento_id).where(MembroDocumento.usuario_id == usuario.id)
    return consulta.where(or_(DocumentoContratacao.criador_id == usuario.id, DocumentoContratacao.id.in_(membro)))
