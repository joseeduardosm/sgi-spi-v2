# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter o cadastro de feriados e pontos facultativos do Módulo RH.
"""Feriados e pontos facultativos (um por data), cadastrados manualmente pela CGP.

Usados em:
- validação dos pedidos de férias e licença-prêmio, quando o parâmetro `inicio_vedado_feriado` está ligado;
- calendário de férias e painel (destaque dos dias);
- folha de ponto (linhas "FERIADO" e "PONTO FACULTATIVO", com a descrição).
"""

import uuid
from datetime import date

from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import Feriado
from app.models.usuario import Usuario
from app.services.rh.papeis import exigir_cgp
from app.services.rh.servico_cadastro import ErroCadastro
from app.services.servico_auditoria import auditar

ROTULOS_TIPO = {"feriado": "Feriado", "ponto_facultativo": "Ponto facultativo"}
CAMPOS = ("data", "descricao", "tipo", "abrangencia")


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def listar(sessao: Session, ano: int) -> list[Feriado]:
    """Feriados e pontos facultativos do ano, em ordem de data."""
    return list(sessao.scalars(select(Feriado).where(extract("year", Feriado.data) == ano).order_by(Feriado.data)))


def no_intervalo(sessao: Session, inicio: date, fim: date) -> dict[date, Feriado]:
    """Por data, os cadastrados entre `inicio` e `fim` (inclusive)."""
    return {f.data: f for f in sessao.scalars(select(Feriado).where(Feriado.data.between(inicio, fim)))}


def _obter(sessao: Session, feriado_id: uuid.UUID) -> Feriado:
    feriado = sessao.get(Feriado, feriado_id)
    if feriado is None:
        raise ErroCadastro("Feriado ou ponto facultativo não encontrado.", 404, "nao_encontrado")
    return feriado


def _conferir_data(sessao: Session, data: date, ignorar: uuid.UUID | None = None) -> None:
    """Uma data só pode ter um cadastro (409)."""
    existente = sessao.scalar(select(Feriado).where(Feriado.data == data))
    if existente is not None and existente.id != ignorar:
        raise ErroCadastro(
            f"Já existe {ROTULOS_TIPO[existente.tipo].lower()} em {data:%d/%m/%Y}: {existente.descricao}.", 409, "conflito"
        )


def criar(sessao: Session, dados: dict, autor: Usuario) -> Feriado:
    exigir_cgp(sessao, autor)
    _conferir_data(sessao, dados["data"])
    feriado = Feriado(**{c: dados[c] for c in CAMPOS}, atualizado_por_nome=_nome(autor), atualizado_em=agora_utc())
    sessao.add(feriado)
    sessao.flush()
    auditar(sessao, autor.login, "rh.feriados.criar", f"{feriado.data:%d/%m/%Y} {feriado.descricao}", autor_id=autor.id,
            alvo_tipo="feriado", alvo_id=feriado.id, dados={c: dados[c] for c in CAMPOS})
    sessao.commit()
    return feriado


def alterar(sessao: Session, feriado_id: uuid.UUID, dados: dict, autor: Usuario) -> Feriado:
    exigir_cgp(sessao, autor)
    feriado = _obter(sessao, feriado_id)
    _conferir_data(sessao, dados["data"], ignorar=feriado.id)
    antes = {c: getattr(feriado, c) for c in CAMPOS}
    for campo in CAMPOS:
        setattr(feriado, campo, dados[campo])
    feriado.atualizado_por_nome, feriado.atualizado_em = _nome(autor), agora_utc()
    auditar(sessao, autor.login, "rh.feriados.alterar", f"{feriado.data:%d/%m/%Y} {feriado.descricao}", autor_id=autor.id,
            alvo_tipo="feriado", alvo_id=feriado.id,
            dados={"campos": {c: {"de": antes[c], "para": dados[c]} for c in CAMPOS if antes[c] != dados[c]}})
    sessao.commit()
    return feriado


def excluir(sessao: Session, feriado_id: uuid.UUID, autor: Usuario) -> None:
    exigir_cgp(sessao, autor)
    feriado = _obter(sessao, feriado_id)
    auditar(sessao, autor.login, "rh.feriados.excluir", f"{feriado.data:%d/%m/%Y} {feriado.descricao}", autor_id=autor.id,
            alvo_tipo="feriado", alvo_id=feriado.id)
    sessao.delete(feriado)
    sessao.commit()
