"""Schemas da previsão orçamentária e das Notas de Empenho."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.contratos.empresas import TextoObrigatorio
from app.schemas.contratos.tipos import ValorFator, ValorMonetario, ValorQuantidade


class ItemMesPrevisao(BaseModel):
    item_id: uuid.UUID
    ordem: int
    descricao: str
    tipo: Literal["continuo", "sob_demanda"]
    quantidade: ValorQuantidade
    valor_unitario: ValorMonetario
    fator: ValorFator = Field(..., description="Fração do mês (pró-rata 30/360); 1 para itens sempre integrais.")
    subtotal: ValorMonetario


class MesPrevisao(BaseModel):
    competencia: date = Field(..., description="Dia 1 do mês.")
    sequencia_vigencia: int
    inicio: date = Field(..., description="Primeiro dia faturado no mês.")
    fim: date
    fator: ValorFator
    base_mensal: ValorMonetario = Field(..., description="Itens contínuos em mês cheio (sem pró-rata).")
    valor: ValorMonetario = Field(..., description="Valor previsto da competência (com pró-rata e sob demanda).")
    acumulado: ValorMonetario = Field(..., description="Acumulado dentro da vigência.")
    itens: list[ItemMesPrevisao]


class ItemSobDemandaPrevisao(BaseModel):
    item_id: uuid.UUID
    ordem: int
    descricao: str
    limite: ValorQuantidade = Field(..., description="Teto do item na vigência.")
    apontamentos: dict[str, ValorQuantidade] = Field(..., description="Quantidade por mês (`AAAA-MM-01`).")
    saldo: ValorQuantidade = Field(..., description="Limite − soma dos apontamentos.")


class VigenciaPrevisao(BaseModel):
    sequencia: int
    inicio: date
    fim: date
    meses: list[date] = Field(..., description="Meses da vigência (dia 1).")
    possui_sob_demanda: bool
    salva: bool = Field(..., description="Selada: só o SuperRoot altera.")
    salva_em: datetime | None
    salva_por_nome: str | None
    pode_editar: bool = Field(..., description="O usuário pode gravar agora (antes do selo: equipe; depois: só SuperRoot).")
    itens_sob_demanda: list[ItemSobDemandaPrevisao]
    total_previsto: ValorMonetario


class Previsao(BaseModel):
    total_previsto: ValorMonetario = Field(..., description="Soma de todas as vigências.")
    vigencias: list[VigenciaPrevisao]
    meses: list[MesPrevisao]


class ApontamentoGravacao(BaseModel):
    item_id: uuid.UUID
    competencia: date = Field(..., description="Qualquer dia do mês; gravado como dia 1.")
    quantidade: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class GravacaoPrevisao(BaseModel):
    apontamentos: list[ApontamentoGravacao] = Field(..., description="Grade completa dos itens sob demanda (substitui a anterior).")


class GravacaoNotaEmpenho(BaseModel):
    numero: TextoObrigatorio = Field(..., max_length=30, description="Único no contrato.")
    valor_original: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


class MovimentoNota(BaseModel):
    id: uuid.UUID
    data: datetime
    tipo: Literal["pagamento", "estorno"] = Field(..., description="`pagamento` (débito da OB) ou `estorno` (reabertura de competência paga).")
    competencia: date | None
    competencia_id: uuid.UUID | None
    competencia_rotulo: str | None = Field(None, description="Ex.: `01/2027 · 2ª parte`.")
    debito: ValorMonetario = Field(..., description="Positivo no pagamento; negativo no estorno.")
    saldo_apos: ValorMonetario
    justificativa: str = ""
    autor: str | None = None


class LeituraNotaEmpenho(BaseModel):
    id: uuid.UUID
    numero: str
    valor_original: ValorMonetario
    consumido: ValorMonetario
    saldo: ValorMonetario
    comprometido: ValorMonetario = Field(..., description="Reservado por competências com medição concluída e ainda não pagas.")
    saldo_livre: ValorMonetario = Field(..., description="Saldo − comprometido: o que ainda pode ser apontado em novas medições.")
    percentual_consumido: ValorMonetario
    faixa: Literal["verde", "amarelo", "vermelho"] = Field(..., description="Até 50%, até 75%, acima de 75% consumido.")
    vinculada: bool = Field(..., description="Selecionada em alguma competência (não pode ser excluída).")
    movimentos: list[MovimentoNota]
    criado_em: datetime


class LinhaRelatorioNotas(BaseModel):
    contrato: str
    empresa: str
    nota: str
    valor_original: ValorMonetario
    consumido: ValorMonetario
    saldo: ValorMonetario
