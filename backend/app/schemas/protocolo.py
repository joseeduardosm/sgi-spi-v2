# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do Protocolo (/api/protocolo).
"""Formatos de entrada e saída do Protocolo (numeração institucional)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoNumero = Literal["livre", "reservado_cgi", "reservado", "utilizado", "anulado"]
TipoEvento = Literal["reservou", "lancou", "anexou", "concluiu", "liberou", "anulou", "sigilo", "vinculou", "ampliou"]


class GravacaoTipo(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200, description="Nome do documento (Ofício, Portaria…); único sem diferenciar maiúsculas.")
    sequencia: "GravacaoSequencia | None" = Field(None, description="Opcional: cria, na mesma transação, a faixa do primeiro exercício (tela de novo tipo).")
    setor_id: int | None = Field(None, description="Opcional, só na criação: restringe o consumo dos números do tipo a esse setor (e seus filhos). Sem setor, todos podem consumir.")


class SequenciaLeitura(BaseModel):
    id: uuid.UUID
    exercicio: int
    inicio: int
    fim: int
    liberar_a_partir_de: int | None = Field(None, description="Números do início até este (exclusive) ficam \"Reservado CGI\"; nulo = nada reservado.")


class TipoLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    setor_id: int | None = Field(None, description="Setor que pode consumir os números do tipo; nulo = todos.")
    setor_nome: str | None = None
    pode_consumir: bool = Field(True, description="O usuário pode reservar números deste tipo (sem restrição de setor, é do setor, ou administra o Protocolo).")
    sequencias: list[SequenciaLeitura] = Field(default_factory=list, description="Uma por exercício, do mais recente ao mais antigo.")


class ListaTipos(BaseModel):
    pode_administrar: bool = Field(..., description="CONTROLE_TOTAL em `protocolo` (ou SuperRoot): cadastra tipos, amplia faixas, lança números e anula.")
    itens: list[TipoLeitura]


class GravacaoSequencia(BaseModel):
    exercicio: int = Field(..., ge=2000, le=2200)
    inicio: int = Field(..., ge=0)
    fim: int = Field(..., ge=0)
    liberar_a_partir_de: int | None = Field(None, ge=0, description="Opcional, entre `inicio` e `fim + 1`: do início da faixa até este número (exclusive) fica \"Reservado CGI\".")


class GravacaoFaixa(BaseModel):
    inicio: int = Field(..., ge=0, description="Menor que o atual amplia para trás; maior só se os números removidos estiverem livres e sem histórico.")
    fim: int = Field(..., ge=0, description="Maior que o atual amplia para frente.")
    liberar_a_partir_de: int | None = Field(None, ge=0, description="Novo ponto de liberação (nulo remove a reserva). Elevá-lo só vale se os números que passam a ser da CGI não estiverem reservados (`409`).")


class ReservaProximo(BaseModel):
    finalidade: str = Field(..., min_length=1, max_length=1000)
    contrato_id: uuid.UUID | None = Field(None, description="Vínculo opcional com um contrato.")


class ReservaNumero(ReservaProximo):
    """Lançamento de um número específico (só CONTROLE_TOTAL)."""


class Motivo(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=2000)


class GravacaoSigilo(BaseModel):
    sigiloso: bool


class GravacaoContrato(BaseModel):
    contrato_id: uuid.UUID | None = Field(None, description="Nulo remove o vínculo.")


class EventoLeitura(BaseModel):
    tipo: TipoEvento
    autor_nome: str
    texto: str
    ocorrido_em: datetime


class ArquivoLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    tamanho: int
    pode_baixar: bool = Field(..., description="Falso quando o documento é sigiloso e o usuário não é o dono nem o SuperRoot.")


class NumeroLeitura(BaseModel):
    id: uuid.UUID
    sequencia_id: uuid.UUID
    tipo_id: uuid.UUID
    tipo_nome: str
    exercicio: int
    numero: int
    numero_formatado: str = Field(..., description="Ex.: `005/2026`.")
    estado: EstadoNumero
    finalidade: str
    reservado_por_id: int | None
    reservado_por_nome: str
    reservado_em: datetime | None
    usado_em: datetime | None
    contrato_id: uuid.UUID | None
    contrato_numero: str | None = None
    sigiloso: bool
    anulado_em: datetime | None
    motivo_anulacao: str | None
    arquivo: ArquivoLeitura | None
    pode_anexar: bool
    pode_liberar: bool
    pode_concluir_sem_documento: bool = Field(False, description="Reservado e sem documento, e o usuário reservou o número ou administra: pode concluir sem subir o arquivo (`POST /numeros/{id}/concluir-sem-documento`).")
    pode_alterar_sigilo: bool
    pode_reservar: bool = Field(False, description="Livre e o usuário pode escolher este número (administração; a CGI, nos \"Reservado CGI\").")
    eventos: list[EventoLeitura] = Field(default_factory=list, description="Linha do tempo (só no detalhe de um número).")


class ListaNumeros(BaseModel):
    sequencia: SequenciaLeitura
    tipo_id: uuid.UUID
    tipo_nome: str
    pode_consumir: bool = Field(True, description="O usuário pode reservar números deste tipo (tipo sem restrição de setor, usuário do setor, ou administração do Protocolo).")
    pode_administrar: bool
    usuario_id: int
    livres: int
    reservados_cgi: int = Field(0, description="Números ainda \"Reservado CGI\" (livres dentro da faixa da Coordenadoria de Gestão e Infraestrutura).")
    pode_usar_reserva_cgi: bool = Field(False, description="O usuário é da CGI (ou administra o Protocolo) e pode dar andamento na faixa reservada.")
    itens: list[NumeroLeitura]


class MesPainel(BaseModel):
    mes: int
    reservados: int = Field(..., description="Reservados no mês e ainda sem documento.")
    utilizados: int = Field(..., description="Documentos anexados no mês.")


class PessoaPainel(BaseModel):
    usuario_id: int | None
    nome: str
    quantidade: int


class PendentePainel(BaseModel):
    id: uuid.UUID
    numero_formatado: str
    finalidade: str
    reservado_por_nome: str
    reservado_em: datetime


class PainelProtocolo(BaseModel):
    tipo_id: uuid.UUID
    tipo_nome: str
    ano: int
    meses: list[MesPainel]
    mais_reservaram: list[PessoaPainel]
    mais_utilizaram: list[PessoaPainel]
    sem_documento: list[PendentePainel]


GravacaoTipo.model_rebuild()
