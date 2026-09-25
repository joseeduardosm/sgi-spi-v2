# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do cadastro, da carteira e do detalhe do contrato.
"""Schemas do contrato: cadastro, carteira, detalhe, documentos e histórico por campo.

Convenção de nomes: `Gravacao*` = o que o frontend envia; `Leitura*`, `Resumo*` e `Detalhe*` =
o que a API devolve.
"""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.schemas.contratos.empresas import Texto, TextoObrigatorio
from app.schemas.contratos.tipos import ValorMonetario, ValorQuantidade
from app.schemas.contratos.empresas import OpcaoEmpresa as EmpresaDoContrato

# Valores aceitos em campos de escolha (o Pydantic recusa qualquer outro com erro 422)
TipoItem = Literal["continuo", "sob_demanda"]
Situacao = Literal["ativo", "a_vencer", "encerrado", "suspenso"]
Papel = Literal[
    "gestor",
    "gestor_suplente",
    "fiscal_administrativo",
    "fiscal_administrativo_suplente",
    "fiscal_tecnico",
    "fiscal_tecnico_suplente",
]
# Números decimais de entrada: não negativos, com limite de dígitos e de casas decimais
Quantidade = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


def _link(valor: str) -> str:
    """Exige que os links dos processos SEI sejam URLs http(s) sem espaços."""
    if not re.match(r"^https?://\S+$", valor):
        raise ValueError("informe um link começando com http:// ou https://")
    return valor


Link = Annotated[str, AfterValidator(_link)]


class GravacaoItem(BaseModel):
    """Um item do contrato no cadastro/edição."""
    id: uuid.UUID | None = Field(None, description="Nulo = item novo. Itens existentes omitidos da lista são excluídos.")
    descricao: TextoObrigatorio = Field(..., max_length=1000, description="Nome do item. Não muda depois de salvo.")
    tipo: TipoItem = Field(..., description="Não muda depois de salvo.")
    calcula_pro_rata: bool = Field(..., description="Faturamento: `true` com pró-rata, `false` sempre integral. Não muda depois de salvo.")
    codigo_classe: TextoObrigatorio = Field(..., max_length=80)
    codigo_natureza_despesa: TextoObrigatorio = Field(..., max_length=80)
    codigo_siafisico: TextoObrigatorio = Field(..., max_length=80)
    codigo_catmat_catser: TextoObrigatorio = Field(..., max_length=80)
    quantidade_mensal: Quantidade = Field(..., description="Contínuo: > 0. Sob demanda: estimativa mensal (pode ser 0).")
    quantidade_total: Quantidade = Field(Decimal(0), description="Só sob demanda: teto da vigência (> 0).")
    valor_unitario: Dinheiro

    @model_validator(mode="after")
    def _quantidades(self) -> "GravacaoItem":
        """Confere as quantidades conforme o tipo do item."""
        if self.tipo == "continuo" and self.quantidade_mensal <= 0:
            raise ValueError("item contínuo exige quantidade mensal maior que zero")
        if self.tipo == "sob_demanda" and self.quantidade_total <= 0:
            raise ValueError("item sob demanda exige quantidade total da vigência maior que zero")
        # Contínuo não usa quantidade total (ela é calculada: mensal × meses), então zera
        if self.tipo == "continuo":
            self.quantidade_total = Decimal(0)
        return self


class GravacaoEquipe(BaseModel):
    """Um usuário do portal por papel (id em `usuarios`). Nulo = sem responsável."""

    gestor: int | None = None
    gestor_suplente: int | None = None
    fiscal_administrativo: int | None = None
    fiscal_administrativo_suplente: int | None = None
    fiscal_tecnico: int | None = None
    fiscal_tecnico_suplente: int | None = None


class GravacaoContrato(BaseModel):
    """Corpo do `POST /api/contratos` e do `PUT /api/contratos/{id}`."""
    numero: str = Field(..., pattern=r"^\d{1,4}/\d{4}$", description="NNN/AAAA. Único.", examples=["012/2026"])
    empresa_id: uuid.UUID = Field(..., description="Empresa ativa.")
    apelido: Texto = Field("", max_length=200)
    objeto: TextoObrigatorio = Field(..., max_length=4000)
    data_inicio: date
    vigencia_inicial_meses: int = Field(..., ge=1, le=600)
    vigencia_maxima_meses: int = Field(..., ge=1, le=600, description="≥ vigência inicial.")
    periodicidade_meses: Literal[1, 2, 3, 6, 12] = Field(..., description="1 mensal, 2 bimestral, 3 trimestral, 6 semestral, 12 anual.")
    mes_reajuste: int = Field(..., ge=1, le=12)
    sei_gestao_numero: TextoObrigatorio = Field(..., max_length=100)
    sei_gestao_link: Link = Field(..., max_length=1000)
    sei_execucao_numero: TextoObrigatorio = Field(..., max_length=100)
    sei_execucao_link: Link = Field(..., max_length=1000)
    situacao_forcada: Situacao | None = Field(None, description="Nulo = situação calculada pelas datas.")
    equipe: GravacaoEquipe = Field(default_factory=GravacaoEquipe)
    itens: list[GravacaoItem] = Field(default_factory=list, description="Lista completa, na ordem de exibição.")
    versao: int | None = Field(None, description="Na alteração, a `versao` lida. Diferente da atual → 409.")

    @model_validator(mode="after")
    def _vigencias(self) -> "GravacaoContrato":
        """A vigência máxima (com prorrogações) não pode ser menor que a inicial."""
        if self.vigencia_maxima_meses < self.vigencia_inicial_meses:
            raise ValueError("a vigência máxima deve ser maior ou igual à vigência inicial")
        return self


class LeituraItem(BaseModel):
    """Item como aparece no detalhe do contrato, já com saldos calculados."""
    id: uuid.UUID
    ordem: int
    descricao: str
    tipo: TipoItem
    calcula_pro_rata: bool
    codigo_classe: str
    codigo_natureza_despesa: str
    codigo_siafisico: str
    codigo_catmat_catser: str
    quantidade_mensal: ValorQuantidade
    quantidade_total: ValorQuantidade = Field(..., description="Contínuo: mensal × meses da vigência atual. Sob demanda: teto da vigência.")
    quantidade_original: ValorQuantidade = Field(..., description="Sob demanda: teto da vigência inicial (o valor editável no cadastro).")
    quantidade_executada: ValorQuantidade
    quantidade_disponivel: ValorQuantidade
    valor_unitario: ValorMonetario
    subtotal_mensal: ValorMonetario = Field(..., description="Quantidade mensal × valor unitário.")
    vigencia_meses: int


class MembroEquipe(BaseModel):
    """Integrante vigente da equipe em um papel."""
    papel: Papel
    usuario_id: int
    nome: str
    login: str
    desde: datetime | None


class LeituraVigencia(BaseModel):
    """Uma vigência do contrato (a original ou uma prorrogação)."""
    sequencia: int = Field(..., description="1 = inicial; 2, 3… = prorrogações.")
    inicio: date
    fim: date
    meses: int


class PermissoesContrato(BaseModel):
    """O que o usuário logado pode fazer neste contrato (a tela mostra ou esconde botões com isso)."""
    pode_editar: bool = Field(..., description="SuperRoot, criador ou integrante vigente da equipe, com ACL ≥ MODIFICACAO.")
    pode_excluir: bool = Field(..., description="ACL `contratos` = CONTROLE_TOTAL.")


class ResumoContrato(BaseModel):
    """Contrato como aparece na carteira."""
    id: uuid.UUID
    numero: str
    apelido: str
    empresa_razao_social: str
    objeto: str
    data_inicio: date
    data_fim: date = Field(..., description="Fim da vigência atual.")
    situacao: Situacao
    base_mensal: ValorMonetario = Field(..., description="Soma dos subtotais mensais dos itens contínuos.")
    valor_global: ValorMonetario = Field(..., description="Valor da vigência atual (ou o valor reajustado).")


class PaginaContratos(BaseModel):
    """Uma página da carteira de contratos."""
    itens: list[ResumoContrato]
    total: int
    pagina: int
    tamanho_pagina: int


class MarcoLinhaTempo(BaseModel):
    """Um marco da linha do tempo exibida na aba Principal."""
    data: date
    tipo: Literal["inicio", "prazo_inicial", "termo_aditivo", "reajuste", "aditamento", "supressao", "vigencia_atual", "maximo"]
    rotulo: str


class DetalheContrato(ResumoContrato):
    """Detalhe completo do contrato (herda os campos do resumo e acrescenta os demais)."""
    sequencial: int
    ano: int
    empresa: EmpresaDoContrato
    data_fim_prazo_inicial: date = Field(..., description="Início + vigência inicial − 1 dia.")
    data_limite_maxima: date = Field(..., description="Início + vigência máxima − 1 dia.")
    vigencia_inicial_meses: int
    vigencia_maxima_meses: int
    periodicidade_meses: int
    mes_reajuste: int
    sei_gestao_numero: str
    sei_gestao_link: str
    sei_execucao_numero: str
    sei_execucao_link: str
    situacao_forcada: Situacao | None
    vigencias: list[LeituraVigencia]
    marcos: list[MarcoLinhaTempo] = Field(..., description="Marcos da linha do tempo, em ordem de data.")
    aditamento_acumulado_percentual: ValorMonetario = Field(..., description="Aditamentos concluídos na vigência atual (%).")
    supressao_acumulada_percentual: ValorMonetario = Field(..., description="Supressões concluídas na vigência atual (%).")
    itens: list[LeituraItem]
    equipe: list[MembroEquipe] = Field(..., description="Designações vigentes, uma por papel.")
    criador_nome: str | None
    permissoes: PermissoesContrato
    versao: int
    criado_em: datetime
    atualizado_em: datetime


class ProximoNumero(BaseModel):
    """Sugestão de número para um contrato novo."""
    numero: str = Field(..., examples=["013/2026"])
    sequencial: int
    ano: int


class LeituraDocumento(BaseModel):
    """Um documento do catálogo de documentos importantes, anexado ou não."""
    codigo: int
    numero: str = Field(..., description="Código com 3 dígitos (001…).")
    titulo: str
    anexado: bool
    nome_arquivo: str = Field(..., description="Nome padronizado do download: PREFIXO_SPI_NNN_AAAA.pdf.")
    tamanho: int | None = Field(None, description="Bytes.")
    enviado_em: datetime | None
    enviado_por_nome: str | None


class AlteracaoCampo(BaseModel):
    """Uma alteração de campo registrada na auditoria (de → para)."""
    campo: str = Field(..., description="Nome do campo (ex.: `apelido`, `equipe.gestor`).")
    de: Any
    para: Any
    autor: str
    ocorrido_em: datetime
