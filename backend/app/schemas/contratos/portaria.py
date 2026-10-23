# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados das autoridades e das portarias de designação dos contratos.
"""Schemas das portarias contratuais. `Gravacao*` = entrada; `Leitura*`/`Painel*` = saída."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GravacaoAutoridade(BaseModel):
    """Corpo de criação e alteração de uma autoridade signatária."""
    sigla: str = Field(..., max_length=60, description="Sigla do título da portaria, ex.: `SPI SSGC`.")
    usuario_id: int = Field(..., description="Usuário do sistema que é a autoridade: ele mesmo dá o aceite.")
    nome: str = Field("", max_length=200, description="Em branco: usa o nome do cadastro do usuário.")
    cargo: str = Field("", max_length=200, description="Em branco: usa o cargo do cadastro do usuário.")
    setor: str = Field("", max_length=200, description="Em branco: usa o departamento do cadastro do usuário.")
    ativa: bool = True


class LeituraAutoridade(GravacaoAutoridade):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    usuario_nome: str | None = Field(None, description="Nome do usuário que dá o aceite.")


class UsuarioAutoridade(BaseModel):
    """Usuário que pode ser escolhido como autoridade, com os dados do cadastro que preenchem o formulário."""
    id: int
    login: str
    nome_completo: str
    cargo: str = ""
    departamento: str = ""


class NomeacaoEntrada(BaseModel):
    """Uma nomeação enviada: função e usuário."""
    papel: str = Field(..., description="`gestor`, `gestor_suplente`, `fiscal_tecnico`, `fiscal_tecnico_suplente`, `fiscal_administrativo` ou `fiscal_administrativo_suplente`.")
    usuario_id: int


class GravacaoNomeacoes(BaseModel):
    """Corpo do `POST /portarias` e do `PUT /portarias/{id}/nomeacoes`: de 1 a 6 funções, com o gestor obrigatório."""
    nomeacoes: list[NomeacaoEntrada] = Field(..., min_length=1, max_length=6)


class EscolhaAutoridade(BaseModel):
    """Corpo do `POST /portarias/{id}/autoridade`: a autoridade escolhida preenche cargo, setor e nome."""
    autoridade_id: uuid.UUID


class MotivoPortaria(BaseModel):
    """Motivo da devolução ou do cancelamento."""
    motivo: str = Field(..., min_length=1, max_length=1000)


class LeituraNomeacao(BaseModel):
    papel: str
    papel_rotulo: str
    usuario_id: int | None
    nome: str
    dados_pendentes: list[str] = Field(..., description="O que falta no cadastro para a nomeação seguir (`RS/PV`, `RG/CIN`, `cargo`): o RH atualiza. Vazio quando completo.")
    ciente_em: datetime | None = Field(None, description="Quando o nomeado deu ciência (nulo: aguardando).")


class LeituraCienciaPendente(BaseModel):
    """Nomeação aguardando a ciência do usuário logado (abre o modal ao entrar no sistema)."""
    portaria_id: uuid.UUID
    contrato_id: uuid.UUID
    contrato: str = Field(..., description="Número e apelido do contrato.")
    papel: str
    papel_rotulo: str
    nomeado_por: str


class LeituraPortaria(BaseModel):
    """Portaria do contrato com o que o usuário pode fazer nela."""
    id: uuid.UUID
    titulo: str
    sigla: str
    numero: int | None = Field(None, description="Só existe depois que a autoridade é escolhida (número reservado no Protocolo).")
    exercicio: int | None
    status: str = Field(..., description="`nomeacao`, `aguardando_ciencia`, `aguardando_autoridade`, `aguardando_aceite`, `aceita`, `publicada` ou `cancelada`.")
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
    nomeacoes: list[LeituraNomeacao]
    texto_html: str | None = Field(None, description="Texto da portaria (HTML da máscara preenchida), para copiar. Só depois da escolha da autoridade.")
    pendencias: list[str] = Field(..., description="O que ainda impede o aceite (processo SEI, objeto, RS).")
    aviso_reserva: str | None = Field(None, description="Mensagem enquanto o número está reservado e a publicação não chegou.")
    tem_evidencia: bool = Field(..., description="O PDF de evidência (ciências e aceite) já foi gerado.")
    pode_decidir: bool = Field(..., description="O usuário é a autoridade signatária (ou SuperRoot) e a portaria aguarda aceite.")
    pode_alterar: bool = Field(..., description="O usuário pode alterar nomeações, escolher a autoridade e cancelar.")
    pode_publicar: bool = Field(False, description="O usuário pode anexar o PDF do D.O.E. pela aba Equipe: portaria aceita e usuário que conduz a portaria (equipe, cadastrante ou controle total).")


class PainelPortarias(BaseModel):
    """Resposta do `GET /portarias`: histórico, autoridades ativas e a equipe vigente (ponto de partida da nova portaria)."""
    portarias: list[LeituraPortaria]
    autoridades: list[LeituraAutoridade]
    em_andamento: bool
    pode_criar: bool = Field(..., description="O usuário é da equipe do contrato, cadastrou o contrato ou tem controle total em Contratos.")
    equipe_vigente: list[NomeacaoEntrada]
