# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de prorrogação, reajuste e aditamento/supressão.
"""Schemas de prorrogação, reajuste e aditamento/supressão."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.contratos.empresas import Texto
from app.schemas.contratos.execucao import LeituraArquivo, LeituraCiencia
from app.schemas.contratos.tipos import ValorFator, ValorMonetario, ValorQuantidade

Quantidade = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
RegraSobDemanda = Literal["saldo_remanescente", "repetir_inicial", "manual"]
CAMPOS_PARECER = ("avaliacao_geral", "resumo_qualidade", "historico_ocorrencias", "reclamacoes", "atendimento_chamados", "parecer")


# ---------------------------------------------------------------------------------------------
# Prorrogação
# ---------------------------------------------------------------------------------------------

class PlanoItemGravacao(BaseModel):
    item_id: uuid.UUID
    limite: Quantidade = Field(..., description="Limite na nova vigência (≤ quantidade original).")
    apontamentos: dict[date, Quantidade] = Field(default_factory=dict, description="Quantidade por mês da nova vigência.")


class GravacaoProrrogacao(BaseModel):
    meses: int | None = Field(None, ge=1, le=600, description="Prazo da prorrogação.")
    regra_sob_demanda: RegraSobDemanda = "saldo_remanescente"
    plano_sob_demanda: list[PlanoItemGravacao] = Field(default_factory=list)
    avaliacao_geral: Texto = ""
    resumo_qualidade: Texto = ""
    historico_ocorrencias: Texto = ""
    reclamacoes: Texto = ""
    atendimento_chamados: Texto = ""
    parecer: Texto = ""


class PlanoItemLeitura(BaseModel):
    item_id: uuid.UUID
    ordem: int
    descricao: str
    quantidade_original: ValorQuantidade
    saldo_remanescente: ValorQuantidade = Field(..., description="Limite da vigência atual − executado nela.")
    limite: ValorQuantidade
    apontamentos: dict[str, ValorQuantidade]
    saldo: ValorQuantidade


class LeituraProcessoProrrogacao(BaseModel):
    id: uuid.UUID | None = Field(None, description="Nulo = ainda não há rascunho salvo.")
    vigencia_atual_inicio: date
    vigencia_atual_fim: date
    meses: int | None
    nova_vigencia_inicio: date
    nova_vigencia_fim: date | None
    meses_disponiveis: int = Field(..., description="Vigência máxima − soma das vigências registradas.")
    meses_nova_vigencia: list[date]
    regra_sob_demanda: RegraSobDemanda
    itens_sob_demanda: list[PlanoItemLeitura]
    avaliacao_geral: str
    resumo_qualidade: str
    historico_ocorrencias: str
    reclamacoes: str
    atendimento_chamados: str
    parecer: str
    possui_parecer: bool = Field(..., description="Algum campo do parecer preenchido: o PDF do parecer será emitido.")
    ciencias: list[LeituraCiencia]
    relatorio: LeituraArquivo | None
    exige_checklist_ativo: bool
    pode_editar: bool
    integra_equipe: bool


class LeituraProrrogacao(BaseModel):
    id: uuid.UUID
    meses: int
    assinada_em: date
    numero_termo: str
    fim_anterior: date
    data_inicio: date
    data_fim: date
    codigo_documento: int | None
    termo: LeituraArquivo | None
    relatorio: LeituraArquivo | None
    pode_desfazer: bool


# ---------------------------------------------------------------------------------------------
# Reajuste
# ---------------------------------------------------------------------------------------------

class AberturaReajuste(BaseModel):
    sequencia_vigencia: int = Field(..., ge=1)
    mes_referencia: date = Field(..., description="Primeiro mês com os novos valores (qualquer dia; gravado como dia 1).")


class ItemReajusteGravacao(BaseModel):
    item_id: uuid.UUID
    indice_percentual: Annotated[Decimal, Field(ge=-100, le=1000, max_digits=18, decimal_places=8)] = Field(..., description="2 = 2%.")
    valor_referencial: Annotated[Decimal | None, Field(None, ge=0, max_digits=18, decimal_places=2)] = Field(None, description="Teto opcional.")


class GravacaoMemoriaReajuste(BaseModel):
    itens: list[ItemReajusteGravacao]


class ItemReajusteLeitura(BaseModel):
    item_id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str
    quantidade_mensal: ValorQuantidade
    valor_unitario_atual: ValorMonetario
    indice_percentual: ValorFator
    valor_referencial: ValorMonetario | None
    valor_unitario_reajustado: ValorMonetario
    subtotal_reajustado: ValorMonetario


class LeituraMemoriaVersao(BaseModel):
    versao: int
    criada_em: datetime
    pdf: LeituraArquivo
    xlsx: LeituraArquivo


class LeituraReajuste(BaseModel):
    id: uuid.UUID
    situacao: Literal["rascunho", "concluido", "cancelado"]
    sequencia_vigencia: int
    vigencia_inicio: date
    vigencia_fim: date
    mes_referencia: date
    competencias_recalculadas: int = Field(..., description="Competências não medidas a partir do mês de referência (recebem o novo preço).")
    competencias_com_diferenca: int = Field(
        0, description="Competências já medidas a partir do mês de referência: a diferença de preço delas vira uma competência complementar."
    )
    competencia_diferenca: str | None = Field(
        None, description="Identificador (`AAAA-MM-dif`) da competência complementar gerada na conclusão, se houver."
    )
    itens: list[ItemReajusteLeitura]
    base_atual: ValorMonetario
    base_reajustada: ValorMonetario
    valor_global_atual: ValorMonetario
    valor_global_reajustado: ValorMonetario
    evidencia: LeituraArquivo | None
    apostilamento: LeituraArquivo | None
    memorias: list[LeituraMemoriaVersao]
    concluido_em: datetime | None
    cancelado_em: datetime | None


class VigenciaDisponivel(BaseModel):
    sequencia: int
    inicio: date
    fim: date


class PainelReajuste(BaseModel):
    em_andamento: LeituraReajuste | None
    vigencias_disponiveis: list[VigenciaDisponivel] = Field(..., description="Vigências ainda sem reajuste concluído.")
    historico: list[LeituraReajuste]
    pode_editar: bool


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão
# ---------------------------------------------------------------------------------------------

class AberturaAlteracao(BaseModel):
    tipo: Literal["aditamento", "supressao"]
    sequencia_vigencia: int = Field(..., ge=1)
    mes_efeito: date = Field(..., description="Primeiro mês com as novas quantidades (gravado como dia 1).")


class ItemAlteracaoGravacao(BaseModel):
    item_id: uuid.UUID
    quantidade_nova: Quantidade = Field(..., description="Contínuo: nova quantidade mensal; sob demanda: novo limite da vigência.")


class GravacaoQuantitativos(BaseModel):
    itens: list[ItemAlteracaoGravacao]


class ItemAlteracaoLeitura(BaseModel):
    item_id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str
    valor_unitario: ValorMonetario
    quantidade_original: ValorQuantidade
    quantidade_executada: ValorQuantidade
    quantidade_nova: ValorQuantidade
    impacto_valor: ValorMonetario
    abaixo_do_executado: bool


class LeituraAlteracao(BaseModel):
    id: uuid.UUID
    tipo: Literal["aditamento", "supressao"]
    situacao: Literal["rascunho", "aguardando_ciencias", "concluida", "cancelada"]
    sequencia_vigencia: int
    vigencia_inicio: date
    vigencia_fim: date
    mes_efeito: date
    meses_restantes: ValorFator = Field(..., description="Meses (com fração) do mês de efeito ao fim da vigência.")
    itens: list[ItemAlteracaoLeitura]
    valor_global_original: ValorMonetario
    impacto_valor: ValorMonetario
    impacto_percentual: ValorMonetario
    acumulado_percentual: ValorMonetario = Field(..., description="Esta alteração + as já concluídas do mesmo tipo na vigência.")
    exige_autorizacao: bool = Field(..., description="Acumulado acima de 25%: autorização do Ordenador de Despesa obrigatória.")
    justificativa: LeituraArquivo | None
    autorizacao: LeituraArquivo | None
    de_acordo: LeituraArquivo | None
    termo: LeituraArquivo | None
    memoria_pdf: LeituraArquivo | None
    memoria_xlsx: LeituraArquivo | None
    consolidado: LeituraArquivo | None
    ciencias: list[LeituraCiencia]
    ciencias_minimas: int
    concluida_em: datetime | None
    cancelada_em: datetime | None


class PainelAlteracao(BaseModel):
    em_andamento: LeituraAlteracao | None
    vigencias: list[VigenciaDisponivel]
    historico: list[LeituraAlteracao]
    pode_editar: bool
    integra_equipe: bool
