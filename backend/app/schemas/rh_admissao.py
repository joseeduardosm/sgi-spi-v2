# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de entrada e saída das rotas da admissão do RH (modelos, checklists e trilha).
"""Schemas da admissão: modelos editáveis, checklists de documentos e a trilha de admissão."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Serviços que o chamado no GLPI pode pedir (iguais às perguntas do formulário "CGP – Nomeações")
SOLICITACOES = {
    "rede": "Criar usuário de rede", "email": "Criar e-mail corporativo", "sei": "Criar acesso ao SEI", "compras_sp": "Criar acesso ao Compras SP",
    "equipamento": "Provisionar equipamento de trabalho", "estacao": "Preparo da estação", "cracha": "Solicitar crachá",
    "telefone": "Provisionar telefone", "mobiliario": "Provisionar mobiliário",
}


class LeituraModelo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo: str
    nome: str
    assunto: str
    html: str
    atualizado_em: datetime


class GravacaoModelo(BaseModel):
    assunto: str = Field("", max_length=300)
    html: str = Field(..., min_length=1, max_length=60000)


class ItemChecklist(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    descricao: str = Field(..., min_length=1, max_length=300)
    obrigatorio: bool = True


class ClassificacaoChecklist(BaseModel):
    """Classificação do cargo: grupo 1 ou 2 e nível (ex.: grupo 1, nível 15 = "1.15")."""
    model_config = ConfigDict(from_attributes=True)
    grupo: Literal[1, 2]
    nivel: int = Field(..., ge=1, le=18)


class GravacaoChecklist(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    ativo: bool = True
    classificacoes: list[ClassificacaoChecklist] = Field(default_factory=list, max_length=40, description="Classificações a que o checklist se aplica (ex.: 1.15, 1.16, 1.17), uma ou várias.")
    aplica_a_outros: bool = Field(False, description="Vale também para cargos sem classificação (tipo OUTRO).")
    itens: list[ItemChecklist] = Field(default_factory=list, max_length=60)


class LeituraChecklist(GravacaoChecklist):
    id: int


class DocumentoAdmissao(BaseModel):
    id: int
    descricao: str
    obrigatorio: bool
    enviado_em: date | None
    enviado_por_nome: str
    registrado_em: datetime | None
    tem_comprovante: bool
    observacao: str
    incluido_no_processo: bool = Field(False, description="Incluído durante a admissão (não veio do checklist do cargo): nunca obrigatório e pode ser excluído enquanto a etapa estiver aberta.")
    detalhe: str = Field("", description="Descrição do documento incluído durante a admissão.")
    tem_arquivo: bool = Field(False, description="O documento incluído tem arquivo (baixar em `…/documentos/{id}/arquivo`).")
    incluido_por_nome: str = ""
    incluido_em: datetime | None = None


class EtapaAdmissao(BaseModel):
    chave: Literal["chamado", "documentos", "resolucao", "protocolo", "publicacao", "posse", "concluida"]
    rotulo: str
    estado: Literal["feita", "atual", "pendente"]
    em: datetime | date | None = None


class IniciarAdmissao(BaseModel):
    ficha_id: int


class EntradaChamado(BaseModel):
    solicitacoes: dict[str, bool] = Field(default_factory=dict, description="Serviços a pedir (chaves de `SOLICITACOES`); ausentes valem `false`.")
    observacoes: str = Field("", max_length=4000, description="Observações adicionais para a TI (o login proposto da ficha vai junto, na mesma pergunta).")
    usuario_espelho: str = Field("", max_length=100, description="Login de um usuário já existente cujo acesso serve de modelo (pergunta \"Usuário espelho\" do formulário). Opcional.")


class LinkChamado(BaseModel):
    url: str
    texto: str


class EntradaTexto(BaseModel):
    html: str = Field(..., min_length=1, max_length=60000)


class EntradaMotivo(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=2000, description="Justificativa da liberação do número.")


class EntradaProtocolo(BaseModel):
    tipo_protocolo_id: uuid.UUID | None = Field(None, description="Opcional: vale o tipo dos Parâmetros do RH; só é usado (tipo de Resolução) se os Parâmetros não definirem um.")


class EntradaPosse(BaseModel):
    posse_em: date


class EntradaDataPublicacao(BaseModel):
    publicado_em: date


class TipoProtocoloResolucao(BaseModel):
    id: uuid.UUID
    nome: str
    tem_faixa_no_ano: bool


class ResumoAdmissao(BaseModel):
    id: int
    ficha_id: int
    nome: str
    login_proposto: str | None
    cargo_rotulo: str
    setor_nome: str
    status: Literal["andamento", "concluida", "cancelada"]
    etapa: str
    etapa_rotulo: str
    atualizado_em: datetime


class LeituraAdmissao(ResumoAdmissao):
    etapas: list[EtapaAdmissao]
    solicitacoes: dict[str, bool]
    chamado_glpi_id: int | None
    chamado_url: str | None
    chamado_links: list[LinkChamado]
    tem_foto: bool
    documentos: list[DocumentoAdmissao]
    resolucao_html: str | None
    sem_numero: bool = Field(False, description="Resolução sem número: não há etapa do Protocolo e o PDF do D.O.E. fica na própria admissão.")
    numero_protocolo_id: uuid.UUID | None
    numero_protocolo: str | None
    publicado_em: date | None
    tem_publicacao: bool
    email_enviado_em: datetime | None
    email_erro: str | None = None
    email_destino: str | None
    posse_em: date | None
    termo_html: str | None
    concluida_em: datetime | None
    conta_vinculada: bool
    usuario_id: int | None


class TextoParaCopiar(BaseModel):
    """Texto da resolução já preenchido, para colar no SEI."""
    html: str = Field(description="HTML formatado (negrito, listas, tabelas) com os placeholders já trocados pelos valores.")
    texto: str = Field(description="O mesmo texto sem formatação, com uma linha por parágrafo.")
