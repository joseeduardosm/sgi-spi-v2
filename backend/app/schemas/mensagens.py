# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da mensageria (caixa de mensagens, envio e acompanhamento).
"""Schemas da mensageria (`/api/mensagens`)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.contratos.empresas import TextoObrigatorio

Prioridade = Literal["baixa", "normal", "alta", "critica"]
Categoria = Literal["comunicado", "prazo", "pendencia", "revisao", "atribuicao", "indisponibilidade", "normativo"]
EstadoEntrega = Literal["nao_visualizada", "visualizada", "ciente", "encerrada"]


class EnvioMensagem(BaseModel):
    """Corpo do `POST /api/mensagens`: mensagem avulsa."""
    assunto: TextoObrigatorio = Field(..., max_length=300)
    corpo: TextoObrigatorio = Field(..., max_length=12000, description="Texto simples (quebras de linha são mantidas).")
    prioridade: Prioridade = "normal"
    categoria: Categoria = "comunicado"
    usuarios_ids: list[int] = Field(default_factory=list, max_length=2000)
    setores_ids: list[int] = Field(default_factory=list, max_length=500, description="Exige SuperRoot ou ACL `mensageria-setores` ≥ CONTROLE_TOTAL.")
    expira_em: datetime | None = Field(None, description="Depois desta data a mensagem some das caixas (futuro).")
    link: str | None = Field(None, max_length=500, description="Caminho interno do sistema, começando com `/` (ex.: `/contratos/…`).")
    enviar_email: bool = Field(False, description="Também envia por e-mail (servidor SMTP ativo; e-mail do perfil).")

    @field_validator("link")
    @classmethod
    def _link_interno(cls, valor: str | None) -> str | None:
        valor = (valor or "").strip()
        if not valor:
            return None
        if not valor.startswith("/") or valor.startswith("//"):
            raise ValueError("Use um caminho interno do sistema, começando com / (ex.: /contratos).")
        return valor


class EntregaResumo(BaseModel):
    """Uma mensagem na caixa de entrada (sem o texto)."""
    id: uuid.UUID = Field(..., description="Id da entrega (usado nas rotas de leitura e ciência).")
    assunto: str
    prioridade: Prioridade
    categoria: Categoria
    autor_nome: str
    origem: Literal["avulsa", "automatica"]
    link: str | None
    entregue_em: datetime
    visualizada_em: datetime | None
    ciente_em: datetime | None
    encerrada_em: datetime | None = Field(..., description="Pendência resolvida pela própria ação no sistema.")
    estado: EstadoEntrega
    pendente: bool = Field(..., description="Sem ciência e sem encerramento.")


class EntregaDetalhe(EntregaResumo):
    """Mensagem aberta, com o texto."""
    corpo: str
    contrato_id: uuid.UUID | None
    abrir_em_janela: bool


class PaginaEntregas(BaseModel):
    itens: list[EntregaResumo]
    total: int
    pagina: int
    tamanho_pagina: int


class ResumoCaixa(BaseModel):
    """Contador do sino e a janela (modal) a abrir, se houver."""
    pendentes: int
    nao_lidas: int
    janela: EntregaDetalhe | None = Field(..., description="Aviso a mostrar em janela (ex.: designação na equipe de um contrato).")


class OpcaoDestinatario(BaseModel):
    id: int
    nome: str
    detalhe: str = Field("", description="Login e departamento (usuários) ou nº de membros (setores).")


class Destinatarios(BaseModel):
    usuarios: list[OpcaoDestinatario]
    setores: list[OpcaoDestinatario]
    pode_enviar_setores: bool


class RespostaEnvio(BaseModel):
    mensagem_id: uuid.UUID
    destinatarios: int


class EnviadaResumo(BaseModel):
    """Mensagem avulsa enviada pelo usuário, com os números de leitura."""
    id: uuid.UUID
    assunto: str
    prioridade: Prioridade
    categoria: Categoria
    publicada_em: datetime
    expira_em: datetime | None
    enviar_email: bool
    destinatarios: int
    visualizadas: int
    cientes: int


class PaginaEnviadas(BaseModel):
    itens: list[EnviadaResumo]
    total: int
    pagina: int
    tamanho_pagina: int


class SituacaoDestinatario(BaseModel):
    usuario_id: int
    nome: str
    visualizada_em: datetime | None
    ciente_em: datetime | None
    encerrada_em: datetime | None
    email_enviado_em: datetime | None
    email_ok: bool | None
    email_erro: str | None


class EnviadaDetalhe(EnviadaResumo):
    corpo: str
    link: str | None
    situacao: list[SituacaoDestinatario]


class LoteMensagens(BaseModel):
    """Ação sobre várias mensagens da própria caixa de uma vez."""
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500, description="Entregas (ids da caixa) afetadas.")
    acao: Literal["lida", "nao_lida", "ciente"] = Field(
        ..., description="`lida`: marca como visualizada; `nao_lida`: remove a visualização (a ciência já registrada não muda); "
        "`ciente`: registra a ciência (também marca como visualizada).")


class RespostaLote(BaseModel):
    atualizadas: int = Field(..., description="Mensagens que mudaram de situação (as demais já estavam assim ou não são suas).")


class PreviaMensagem(BaseModel):
    """Texto de uma mensagem para ver no layout do e-mail."""
    assunto: str = Field("", max_length=300)
    corpo: str = Field("", max_length=12000, description="Aceita `## título`, `- item` (2 espaços por subnível) e `**negrito**`.")
    link: str | None = Field(None, max_length=300)
    autor_nome: str | None = Field(None, max_length=200, description="Quem enviou (padrão: o próprio usuário).")


class RespostaPrevia(BaseModel):
    html: str = Field(..., description="E-mail completo no layout oficial, com o brasão embutido (`data:`).")


class RespostaLembrete(BaseModel):
    lembrados: int = Field(..., description="Destinatários sem ciência que receberão o e-mail de lembrete.")
