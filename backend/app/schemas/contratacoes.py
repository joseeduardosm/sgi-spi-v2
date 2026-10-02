# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de Contratações (/api/contratacoes): ETP, TR, árvore, revisões e versões.
"""Formatos de entrada e saída de Contratações."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

TipoDocumento = Literal["etp", "tr"]
Situacao = Literal["rascunho", "em_revisao", "concluido"]
TipoItem = Literal["item", "subitem", "inciso", "alinea", "subsecao"]
Papel = Literal["administrador", "criador", "editor", "revisor"]


class GravacaoDocumento(BaseModel):
    nome: str = Field(..., min_length=1, max_length=300)
    processo: str = Field("", max_length=100, description="Número do processo SEI.")
    link_sei: str | None = Field(None, max_length=500)


class CriacaoDocumento(GravacaoDocumento):
    tipo: TipoDocumento


class GravacaoSituacao(BaseModel):
    situacao: Situacao
    confirmar: bool = Field(False, description="Concluir mesmo com alertas da conferência (os bloqueios nunca passam).")


class GravacaoContratoVinculo(BaseModel):
    contrato_id: uuid.UUID | None = Field(None, description="`null` desfaz o vínculo.")


class GravacaoMembro(BaseModel):
    papel: Literal["editor", "revisor"]


class MembroLeitura(BaseModel):
    usuario_id: int
    nome: str
    login: str
    papel: Literal["editor", "revisor"]


class DocumentoResumo(BaseModel):
    id: uuid.UUID
    tipo: TipoDocumento
    nome: str
    processo: str
    link_sei: str | None
    situacao: Situacao
    criador_id: int | None
    criador_nome: str
    contrato_id: uuid.UUID | None
    contrato_numero: str | None
    criado_em: datetime
    atualizado_em: datetime
    meu_papel: Papel
    revisoes_abertas: int


class ListaDocumentos(BaseModel):
    pode_criar: bool = Field(..., description="MODIFICACAO (ou mais) em `contratacoes`.")
    itens: list[DocumentoResumo]


class LinhaTrLeitura(BaseModel):
    id: uuid.UUID
    ordem: int
    descricao: str
    siafisico: str
    catser_catmat: str
    unidade: str
    quantidade_mensal: Decimal
    quantidade_objeto: Decimal


class GravacaoLinhaTr(BaseModel):
    descricao: str = Field(..., min_length=1)
    siafisico: str = ""
    catser_catmat: str = ""
    unidade: str = ""
    quantidade_mensal: Decimal = Field(Decimal(0), ge=0)
    quantidade_objeto: Decimal = Field(Decimal(0), ge=0)


class RevisaoLeitura(BaseModel):
    id: uuid.UUID
    autor_nome: str
    comentario: str
    conteudo_original: str
    conteudo_proposto: str | None
    conteudo_proposto_html: str | None
    aplicada_em: datetime | None
    aplicada_por_nome: str | None
    resolvida_em: datetime | None
    resolvida_por_nome: str | None
    criada_em: datetime


class ComentarioImportadoLeitura(BaseModel):
    autor: str
    comentado_em: datetime | None
    comentario: str
    trecho: str


class ItemLeitura(BaseModel):
    id: uuid.UUID
    secao_id: uuid.UUID
    pai_id: uuid.UUID | None
    tipo: TipoItem
    ordem: int
    marcador: str = Field(..., description="Marcador jurídico calculado: `1.2.`, `I -`, `a)` ou vazio (subseção).")
    conteudo: str
    conteudo_html: str | None
    precisa_revisao: bool
    revisoes: list[RevisaoLeitura]
    comentarios_importados: list[ComentarioImportadoLeitura]
    linhas_tabela: list[LinhaTrLeitura]
    tem_tabela_tr: bool = Field(..., description="O item aceita a tabela estruturada do TR (item 1.1).")


class SecaoLeitura(BaseModel):
    id: uuid.UUID
    ordem: int
    titulo: str
    itens: list[ItemLeitura] = Field(..., description="Lista plana em pré-ordem; a hierarquia vem de `pai_id`.")


class DocumentoLeitura(DocumentoResumo):
    pode_editar: bool
    pode_gerir: bool
    pode_revisar: bool
    secoes: list[SecaoLeitura]
    membros: list[MembroLeitura]


class GravacaoSecao(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=300)


class GravacaoOrdem(BaseModel):
    ordem: int = Field(..., ge=1)


class CriacaoItem(BaseModel):
    secao_id: uuid.UUID
    pai_id: uuid.UUID | None = None
    tipo: TipoItem = "item"
    conteudo: str | None = None
    conteudo_html: str | None = Field(None, description="HTML do editor; é sanitizado. Tem precedência sobre `conteudo`.")
    posicao: int | None = Field(None, ge=1, description="Posição entre os irmãos (padrão: no fim).")


class EdicaoItem(BaseModel):
    tipo: TipoItem | None = None
    conteudo: str | None = None
    conteudo_html: str | None = None
    precisa_revisao: bool | None = None


class MoverItem(BaseModel):
    secao_id: uuid.UUID
    pai_id: uuid.UUID | None = None
    ordem: int = Field(..., ge=1)


class EntradaLote(BaseModel):
    secao_id: uuid.UUID
    pai_id: uuid.UUID | None = None
    texto: str = Field(..., min_length=1, max_length=200_000, description="Linhas com `#`..`######`, `@` (subseção), `**` (inciso) e `$$` (alínea).")


class PreviaLote(BaseModel):
    itens: list[dict[str, Any]]


class ResultadoLote(BaseModel):
    criados: int


class GravacaoRevisao(BaseModel):
    comentario: str = Field(..., min_length=1, max_length=4000)
    conteudo_proposto: str | None = None
    conteudo_proposto_html: str | None = None


class GravacaoResolucao(BaseModel):
    resolvida: bool = True


class GravacaoVersao(BaseModel):
    resumo: str = Field("", max_length=500, description="Descreva as alterações (opcional), como no BookStack.")


class VersaoResumo(BaseModel):
    numero: int
    tipo: str
    tipo_rotulo: str
    resumo: str
    autor_nome: str
    criada_em: datetime


class VersaoDetalhe(VersaoResumo):
    foto: dict[str, Any]


class GravacaoRestauroItem(BaseModel):
    estado: Literal["antes", "depois"] = "antes"


class ConferenciaLeitura(BaseModel):
    pode_concluir: bool
    bloqueios: list[str]
    alertas: list[str]


class PainelContratacoes(BaseModel):
    total: int
    por_situacao: dict[str, int]
    por_tipo: dict[str, int]
    revisoes_abertas: int
    sem_vinculo: int


class PreviaImportacao(BaseModel):
    arquivo: str
    nome_sugerido: str = Field("", description="Título lido do cabeçalho de um Word exportado pelo sistema.")
    processo_sugerido: str = ""
    sha256: str
    secoes: list[dict[str, Any]]
    avisos: list[str]
    totais: dict[str, int]
    documento_id: uuid.UUID | None = Field(None, description="Preenchido quando a importação foi confirmada.")
