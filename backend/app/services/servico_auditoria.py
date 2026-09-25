# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar a auditoria das operações e o histórico de alterações por campo.
"""Auditoria: registro de quem fez o quê, quando e em qual registro.

Além da tabela `auditoria` (consultável pelo sistema), cada operação também vai para o log do
serviço (journalctl), o que ajuda a investigar problemas.
"""

import logging
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria

# Logger próprio, para filtrar as linhas de auditoria no journal do systemd
registro_log = logging.getLogger("contratos_spi.auditoria")


def auditar(
    sessao: Session,
    autor: str,
    acao: str,
    alvo: str,
    detalhes: str | None = None,
    *,
    autor_id: int | None = None,
    alvo_tipo: str | None = None,
    alvo_id: str | UUID | None = None,
    dados: Mapping[str, Any] | None = None,
) -> None:
    """Registra a operação na tabela `auditoria` (gravada no commit da transação corrente).

    `alvo_tipo`/`alvo_id` identificam o registro de forma estruturada (histórico por campo) e
    `dados` guarda o conteúdo do ato em JSON.
    """
    # Apenas adiciona à sessão: a linha é gravada junto com a operação auditada, no mesmo commit.
    # Se a operação falhar e houver rollback, a auditoria também é descartada (fica coerente).
    sessao.add(
        RegistroAuditoria(
            autor=autor,
            autor_id=autor_id,
            acao=acao,
            alvo=alvo,
            detalhes=detalhes,
            alvo_tipo=alvo_tipo,
            alvo_id=str(alvo_id) if alvo_id is not None else None,
            dados=valor_json(dict(dados)) if dados is not None else None,
        )
    )
    registro_log.info("%s %s %s %s", autor, acao, alvo, detalhes or "")


def valor_json(valor: Any) -> Any:
    """Converte valores do domínio (Decimal, datas, UUID, enums) para tipos aceitos em JSON."""
    # Dicionários e listas são convertidos recursivamente, item a item
    if isinstance(valor, Mapping):
        return {str(chave): valor_json(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [valor_json(item) for item in valor]
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, Enum):
        return valor.value
    return valor


def diferencas(antes: Mapping[str, Any], depois: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Campos cujo valor mudou, no formato {campo: {"de": ..., "para": ...}}."""
    # Compara depois de converter para JSON, para que Decimal("1.0") e "1.0" sejam considerados iguais
    return {
        campo: {"de": valor_json(antes.get(campo)), "para": valor_json(depois.get(campo))}
        for campo in depois
        if valor_json(antes.get(campo)) != valor_json(depois.get(campo))
    }


def auditar_alteracoes(
    sessao: Session,
    autor: str,
    autor_id: int | None,
    acao: str,
    alvo_tipo: str,
    alvo_id: str | UUID,
    alvo: str,
    antes: Mapping[str, Any],
    depois: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Audita somente os campos alterados. Sem diferença, nada é gravado."""
    # Só grava quando algo realmente mudou (salvar sem alterar nada não polui o histórico)
    campos = diferencas(antes, depois)
    if campos:
        auditar(
            sessao, autor, acao, alvo, f"{len(campos)} campo(s) alterado(s)",
            autor_id=autor_id, alvo_tipo=alvo_tipo, alvo_id=alvo_id, dados={"campos": campos},
        )
    return campos


def historico_campos(sessao: Session, alvo_tipo: str, alvo_id: str | UUID) -> list[RegistroAuditoria]:
    """Registros com alterações de campos do alvo, do mais recente para o mais antigo."""
    return list(
        sessao.scalars(
            select(RegistroAuditoria)
            .where(RegistroAuditoria.alvo_tipo == alvo_tipo, RegistroAuditoria.alvo_id == str(alvo_id))
            .order_by(RegistroAuditoria.ocorrido_em.desc(), RegistroAuditoria.id.desc())
        )
    )
