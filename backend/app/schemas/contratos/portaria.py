# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados das autoridades e das portarias de designação dos contratos.
"""Schemas das portarias contratuais. `Gravacao*` = entrada; `Leitura*`/`Painel*` = saída."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GravacaoAutoridade(BaseModel):
    """Corpo de criação e alteração de uma autoridade signatária."""
    sigla: str = Field(..., max_length=60, description="Sigla do título da portaria, ex.: `SPI SSGC`.")
    nome: str = Field(..., max_length=200)
    cargo: str = Field(..., max_length=200)
    setor: str = Field(..., max_length=200)
    usuario_id: int | None = Field(None, description="Usuário que dá o aceite pela autoridade.")
    ativa: bool = True


class LeituraAutoridade(GravacaoAutoridade):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    usuario_nome: str | None = Field(None, description="Nome do usuário que dá o aceite.")


class SolicitacaoPortaria(BaseModel):
    """Corpo do `POST /portarias`: a autoridade escolhida preenche cargo, setor e nome."""
    autoridade_id: uuid.UUID


class MotivoPortaria(BaseModel):
    """Motivo da devolução ou do cancelamento."""
    motivo: str = Field(..., min_length=1, max_length=1000)


class LeituraPessoaPortaria(BaseModel):
    papel: str
    papel_rotulo: str
    nome: str
    rs_informado: bool = Field(..., description="O RS está cadastrado no RH (o número em si nunca é exposto).")


class LeituraPortaria(BaseModel):
    """Portaria do contrato com o que o usuário pode fazer nela."""
    id: uuid.UUID
    titulo: str
    sigla: str
    numero: int
    exercicio: int
    status: str
    status_rotulo: str
    motivo: str
    autoridade_nome: str
    solicitada_por_nome: str
    solicitada_em: datetime
    aceita_por_nome: str | None
    aceita_em: datetime | None
    publicada_em: datetime | None
    numero_protocolo_id: uuid.UUID | None
    anterior: str | None = Field(None, description="Portaria anterior citada na revogação (None: usou a máscara sem portaria anterior).")
    equipe: list[LeituraPessoaPortaria]
    pendencias: list[str] = Field(..., description="O que ainda impede o aceite (RS, processo SEI, objeto).")
    pode_decidir: bool = Field(..., description="O usuário é a autoridade signatária (ou SuperRoot) e a portaria aguarda aceite.")
    pode_alterar: bool = Field(..., description="O usuário pode reenviar, cancelar e anexar o PDF publicado.")


class PainelPortarias(BaseModel):
    """Resposta do `GET /portarias`: histórico, autoridades ativas para a solicitação e se já há portaria em andamento."""
    portarias: list[LeituraPortaria]
    autoridades: list[LeituraAutoridade]
    em_andamento: bool
