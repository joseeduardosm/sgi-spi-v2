# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do diário de bordo do contrato.
"""Diário de bordo (`/api/contratos/{contrato_id}/diario`): ocorrências e glosas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.contratos.tipos import ValorQuantidade


class GravacaoGlosa(BaseModel):
    """Item e quantidade a glosar."""
    item_id: uuid.UUID
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)] = Field(..., description="Quantidade do item a glosar (até 4 casas).")


class GravacaoOcorrencia(BaseModel):
    """Nova ocorrência. Com `possui_glosa`, informe ao menos um item com quantidade."""
    data_ocorrencia: date = Field(..., description="Dia em que a ocorrência aconteceu (não pode ser futuro).")
    descricao: str = Field(..., min_length=1, max_length=4000, description="Relato da ocorrência.")
    possui_glosa: bool = Field(False, description="A ocorrência implicará glosa?")
    glosas: list[GravacaoGlosa] = Field(default_factory=list, description="Itens e quantidades a glosar (só com `possui_glosa`).")
    impacta_avaliacao: bool = Field(False, description="A ocorrência impacta a avaliação da qualidade?")
    enviar_email: bool = Field(False, description="Envia o e-mail desta etapa (equipe, prepostos ou Financeiro). Padrão `false`: só envia quem marcar.")
    prepostos_ids: list[uuid.UUID] | None = Field(None, description="Prepostos que recebem o e-mail (só com `enviar_email`). `null` = todos os ativos; lista vazia = nenhum (só a equipe).")
    itens_avaliacao: list[str] = Field(default_factory=list, max_length=50,
                                       description="Ids dos itens do formulário de avaliação ativo impactados (só com `impacta_avaliacao`).")

    @field_validator("descricao")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Tira espaços das pontas e recusa relato em branco."""
        valor = valor.strip()
        if not valor:
            raise ValueError("descreva a ocorrência")
        return valor

    @model_validator(mode="after")
    def _glosas(self) -> "GravacaoOcorrencia":
        """Com glosa: ao menos um item, sem repetir item. Sem glosa: nenhum item."""
        if self.possui_glosa and not self.glosas:
            raise ValueError("informe o item e a quantidade a glosar")
        if not self.possui_glosa and self.glosas:
            raise ValueError("itens de glosa só podem ser informados quando a ocorrência implicar glosa")
        if len({g.item_id for g in self.glosas}) != len(self.glosas):
            raise ValueError("cada item pode aparecer uma só vez na glosa")
        if self.impacta_avaliacao and not self.itens_avaliacao:
            raise ValueError("escolha o item do formulário de avaliação impactado pela ocorrência")
        if not self.impacta_avaliacao and self.itens_avaliacao:
            raise ValueError("itens de avaliação só podem ser informados quando a ocorrência impactar a avaliação")
        self.itens_avaliacao = list(dict.fromkeys(self.itens_avaliacao))
        return self


class LeituraGlosa(BaseModel):
    item_id: uuid.UUID
    descricao_item: str
    quantidade: ValorQuantidade


class LeituraAnexoOcorrencia(BaseModel):
    """Arquivo anexado à ocorrência."""
    id: uuid.UUID
    nome: str
    tamanho: int
    tipo: str


class LeituraItemAvaliacao(BaseModel):
    """Item do formulário de avaliação impactado (retrato do nome e do grupo no registro)."""
    item_id: str
    item_nome: str
    grupo_nome: str


class EnvioEmail(BaseModel):
    """Resultado do e-mail enviado à equipe e ao preposto."""
    enviado_em: datetime | None = Field(None, description="Nulo enquanto o envio (em segundo plano) não terminou.")
    ok: bool | None = None
    destinatarios: list[str] = []
    erro: str | None = None


class LeituraOcorrencia(BaseModel):
    id: uuid.UUID
    data_ocorrencia: date
    descricao: str
    possui_glosa: bool
    glosas: list[LeituraGlosa]
    registrada_por_id: int | None
    registrada_por_nome: str
    registrada_por_papel: str = Field(..., description="Papel de quem registrou (ex.: `gestor`, `fiscal_tecnico`) ou vazio.")
    criado_em: datetime = Field(..., description="Data e hora do registro.")
    competencia_rotulo: str | None = Field(None, description="Competência cujo período contém a data da ocorrência.")
    anexos: list[LeituraAnexoOcorrencia] = []
    impacta_avaliacao: bool = False
    itens_avaliacao: list[LeituraItemAvaliacao] = []
    medicao_ja_concluida: bool = Field(False, description="A glosa foi registrada depois de concluída a medição dessa competência: só vale se a medição for reaberta.")
    email: EnvioEmail


class OpcaoItemGlosa(BaseModel):
    """Item do contrato disponível no combobox da glosa."""
    id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str


class OpcaoItemAvaliacao(BaseModel):
    """Item do formulário de avaliação ativo, para marcar o impacto da ocorrência."""
    id: str
    nome: str
    grupo: str


class DiarioContrato(BaseModel):
    ocorrencias: list[LeituraOcorrencia] = Field(..., description="Em ordem cronológica de registro (mais antiga primeiro).")
    pode_registrar: bool
    itens: list[OpcaoItemGlosa]
    itens_avaliacao: list[OpcaoItemAvaliacao] = Field(default_factory=list,
                                                      description="Itens do formulário de avaliação ativo (vazio sem formulário ativo).")
