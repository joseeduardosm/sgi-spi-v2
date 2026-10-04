# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os dados da correção de itens do contrato (proposta, prévia, decisão e histórico).
"""Formatos da correção de itens (`/api/contratos/{id}/itens/correcoes`)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ItemCorrecao(BaseModel):
    """Valores novos de um item (só os campos enviados mudam)."""
    id: uuid.UUID
    valor_unitario: Decimal | None = Field(None, ge=0, max_digits=22, decimal_places=4, description="Preço unitário, até 4 casas.")
    quantidade_mensal: Decimal | None = Field(None, ge=0, max_digits=22, decimal_places=4)
    quantidade_total: Decimal | None = Field(None, ge=0, max_digits=22, decimal_places=4, description="Só sob demanda (teto da vigência).")
    unidade_fornecimento: str | None = Field(None, max_length=50)
    codigo_classe: str | None = Field(None, max_length=80)
    codigo_natureza_despesa: str | None = Field(None, max_length=80)
    codigo_siafisico: str | None = Field(None, max_length=80)
    codigo_catmat_catser: str | None = Field(None, max_length=80)


class GravacaoCorrecao(BaseModel):
    """Proposta de correção: justificativa e os itens com os valores corretos."""
    justificativa: str = Field(..., min_length=20, max_length=4000, description="Por que o cadastro está errado (mínimo 20 caracteres).")
    itens: list[ItemCorrecao] = Field(..., min_length=1, max_length=200)


class Motivo(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=2000)


class PreviaCompetencia(BaseModel):
    competencia: str
    identificador: str
    itens_alterados: list[str]
    itens_incluidos: list[str]
    itens_removidos: list[str]
    valor_antes: str
    valor_depois: str
    variacao: str
    medicao_iniciada: bool
    ciencias_invalidadas: bool


class Previa(BaseModel):
    """O que a correção faria, sem gravar nada."""
    competencias_abertas: list[PreviaCompetencia]
    variacao_total: str = Field(..., description="Soma da variação do valor previsto das competências abertas.")
    congeladas: int = Field(..., description="Competências com medição concluída: nunca mudam.")
    fora_do_calendario: int = Field(..., description="Abertas que não seguem o calendário atual (ex.: migradas do SGI): não são sincronizadas.")
    avisos: list[str]


class MudancaItem(BaseModel):
    item_id: uuid.UUID
    descricao: str
    campos: dict[str, dict[str, Any]]


class LeituraCorrecao(BaseModel):
    id: uuid.UUID
    autor_id: int | None
    autor_nome: str
    justificativa: str
    mudancas: list[MudancaItem]
    previa: dict[str, Any]
    situacao: str
    decidido_por_nome: str
    decidido_em: datetime | None
    motivo_decisao: str
    criado_em: datetime
    pode_decidir: bool = Field(..., description="O usuário pode confirmar ou recusar: outra pessoa que não o autor, com permissão de edição.")
    pode_cancelar: bool


class ListaCorrecoes(BaseModel):
    pode_propor: bool = Field(..., description="Gestor titular vigente ou SuperRoot.")
    itens: list[LeituraCorrecao]


class EntradaHistorico(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID | None
    descricao_item: str
    versao_cadastro: int
    autor_nome: str
    motivo: str
    campos: dict[str, dict[str, Any]]
    criado_em: datetime
