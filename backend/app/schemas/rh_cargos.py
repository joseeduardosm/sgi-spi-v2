# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de entrada e saída das rotas de cargos, ocupações, organograma e histórico do RH.
"""Schemas de cargos, ocupações, organograma e histórico do RH."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LeituraTipoCargo(BaseModel):
    id: int
    codigo: str
    nome: str
    ordem: int
    ativo: bool


class GravacaoTipoCargo(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20, description="Código curto em maiúsculas (ex.: CCESP).")
    nome: str = Field(..., min_length=1, max_length=100)
    ordem: int = Field(0, ge=0, le=999)
    ativo: bool = True


class OcupanteCargo(BaseModel):
    """Pessoa que ocupa o cargo hoje."""
    usuario_id: int
    nome: str
    login: str
    inicio: date
    ato: str = ""
    tem_foto: bool = False
    foto_url: str | None = Field(None, description="Caminho da foto do Diretório (exige o token de acesso); nulo quando não há foto.")


class LeituraCargo(BaseModel):
    """Uma posição (vaga) de um setor, com o ocupante vigente (se houver)."""
    id: int
    setor_id: int
    setor_nome: str
    tipo_id: int
    tipo_codigo: str
    grupo: int | None
    nivel: int | None
    denominacao: str
    classificacao: str = Field(..., description='"FCESP 2.16", "CCESP 1.07" ou só o tipo (OUTRO).')
    rotulo: str = Field(..., description='"FCESP 2.16 – Assessor Especial IV": o que aparece ao lado do nome da pessoa.')
    ativo: bool
    ocupante: OcupanteCargo | None = None


class GravacaoCargo(BaseModel):
    """Dados para criar vagas (`quantidade` linhas iguais) ou alterar uma vaga."""
    setor_id: int
    tipo_id: int
    grupo: Literal[1, 2] | None = Field(None, description="Grupo do quadro (1 = direção e chefia; 2 = assessoria). Vazio nos cargos sem classificação.")
    nivel: int | None = Field(None, ge=1, le=18, description="Nível de 1 a 18 (o quadro da SPI vai de 1.07 a 1.18 e de 2.04 a 2.17). Vazio nos cargos sem classificação.")
    denominacao: str = Field(..., min_length=1, max_length=200)
    quantidade: int = Field(1, ge=1, le=50, description="Quantas vagas iguais criar (só na criação).")
    ativo: bool = True


class OcuparCargo(BaseModel):
    usuario_id: int
    inicio: date | None = Field(None, description="Data da posse; vazio = hoje.")
    ato: str = Field("", max_length=200, description="Ato que nomeou ou designou (resolução, portaria, decreto...).")


class VagarCargo(BaseModel):
    fim: date | None = Field(None, description="Data em que deixou o cargo; vazio = hoje.")
    motivo: Literal["troca", "exoneracao", "dispensa", "outro"] = "outro"
    ato: str = Field("", max_length=200, description="Ato do desligamento (ex.: exoneração publicada).")


class LeituraOcupacao(BaseModel):
    id: int
    cargo_id: int
    cargo_rotulo: str
    setor_id: int
    setor_nome: str
    inicio: date
    fim: date | None
    ato: str
    motivo_fim: str | None
    ato_fim: str
    registrado_por_nome: str
    registrado_em: datetime


class PendenciaCargo(BaseModel):
    """Pessoa com cargo em texto livre ainda sem vínculo com um cargo cadastrado (A reconciliar)."""
    usuario_id: int
    nome: str
    login: str
    cargo_texto: str
    departamento_texto: str
    interpretado: bool = Field(..., description="O texto segue o padrão do quadro (tipo, grupo, nível, denominação).")
    sugestao: str | None = Field(None, description="Rótulo que seria criado a partir do texto.")
    setor_id: int | None = Field(None, description="Setor encontrado pelo departamento; vazio se não existe.")


class VincularCargoLegado(BaseModel):
    """Cria o cargo a partir do texto da pessoa (no setor informado ou no do departamento) e a aloca."""
    setor_id: int | None = Field(None, description="Setor do cargo; vazio = o do departamento da pessoa.")
    cargo_id: int | None = Field(None, description="Cargo já existente e vago; vazio = criar a partir do texto.")


class LiderSetor(BaseModel):
    """Líder da unidade (campo `lider` do setor), com o que o organograma mostra: foto, nome e cargo."""
    usuario_id: int
    nome: str
    cargo: str = ""
    foto_url: str | None = Field(None, description="Caminho da foto do Diretório (exige o token de acesso); nulo quando não há foto.")


class NoOrganograma(BaseModel):
    """Unidade do organograma, com as posições e as unidades subordinadas."""
    setor_id: int
    nome: str
    sigla: str | None
    tipo_unidade: str | None
    lider_nome: str | None
    lider: LiderSetor | None = None
    total_posicoes: int
    total_vagas: int
    posicoes: list[LeituraCargo]
    filhos: list["NoOrganograma"]


class LeituraHistorico(BaseModel):
    id: int
    tipo: str
    titulo: str
    detalhe: str
    ocorrido_em: datetime
    autor_nome: str
    sigiloso: bool


class HistoricoUsuario(BaseModel):
    usuario_id: int
    nome: str
    login: str
    cargo_atual: str
    setor_atual: str
    ocupacoes: list[LeituraOcupacao]
    eventos: list[LeituraHistorico]
    tipos: dict[str, str] = Field(..., description="Rótulo de cada tipo de evento, para os filtros da tela.")
