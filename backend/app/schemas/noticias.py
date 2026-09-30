# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída do Módulo Notícias e do portal.
"""Formatos das rotas `/api/noticias` e `/api/portal`."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SituacaoNoticia = Literal["rascunho", "em_revisao", "aprovada", "devolvida", "arquivada"]


class CategoriaLeitura(BaseModel):
    id: int
    nome: str
    cor: str
    ordem: int
    ativa: bool


class ArquivoLeitura(BaseModel):
    id: uuid.UUID
    nome: str
    tamanho: int
    tipo: str
    url: str


class NoticiaCartao(BaseModel):
    """Notícia em lista, slider ou cartão."""
    id: uuid.UUID
    slug: str
    titulo: str
    linha_fina: str
    categoria: CategoriaLeitura | None
    publicada_em: datetime | None
    fixada: bool
    capa: dict[str, str] = Field(..., description="URL de cada versão WebP 2:1 (`1600`, `800`, `400`). Vazio se não houver capa.")
    capa_alt: str
    capa_modo: str


class NoticiaPublica(NoticiaCartao):
    corpo_html: str = Field(..., description="HTML já sanitizado no servidor.")
    anexos: list[ArquivoLeitura]
    leia_tambem: list[NoticiaCartao]


class PaginaNoticias(BaseModel):
    itens: list[NoticiaCartao]
    total: int
    pagina: int
    tamanho: int


class AtalhoLeitura(BaseModel):
    id: int
    titulo: str
    url: str
    nova_aba: bool
    ativo: bool
    ordem: int
    imagem: str | None = Field(None, description="URL da imagem (WebP).")


class ConfiguracaoLeitura(BaseModel):
    titulo: str
    subtitulo: str
    quantidade_slides: int
    segundos_por_slide: int
    passagem_automatica: bool
    criterio_slider: Literal["automatico", "curadoria"]
    titulo_sobreposto: bool
    quantidade_cartoes: int
    exibir_atalhos: bool
    exibir_todas: bool
    atualizado_em: datetime | None = None
    atualizado_por_nome: str = ""


class PortalLeitura(BaseModel):
    """Página inicial pública."""
    configuracao: ConfiguracaoLeitura
    slides: list[NoticiaCartao]
    cartoes: list[NoticiaCartao]
    atalhos: list[AtalhoLeitura]
    categorias: list[CategoriaLeitura]


# --- Gestão ---------------------------------------------------------------------------------------

class Pessoa(BaseModel):
    id: int
    nome: str
    login: str = ""


class SetorResumo(BaseModel):
    id: int
    nome: str


class NoticiaGestaoResumo(BaseModel):
    id: uuid.UUID
    slug: str
    titulo: str
    situacao: SituacaoNoticia
    visivel: bool = Field(..., description="Aparece no portal agora (aprovada e com a data de publicação já passada).")
    categoria: CategoriaLeitura | None
    autor_nome: str
    publicar_em: datetime | None
    atualizado_em: datetime
    fixada: bool
    capa: dict[str, str]


class CienciaResumo(BaseModel):
    total: int
    cientes: int


class NoticiaGestao(NoticiaGestaoResumo):
    linha_fina: str
    corpo_html: str
    categoria_id: int | None
    destaque_ate: datetime | None
    exige_ciencia: bool
    usuarios_aviso: list[Pessoa]
    setores_aviso: list[SetorResumo]
    aviso_enviado_em: datetime | None
    capa_modo: Literal["recortar", "inteira"]
    capa_recorte: dict | None
    capa_alt: str
    capa_original: str | None = Field(None, description="URL da imagem original (para o recorte no editor).")
    anexos: list[ArquivoLeitura]
    autor_id: int | None
    enviada_revisao_em: datetime | None
    aprovado_por_nome: str | None
    aprovado_em: datetime | None
    motivo_devolucao: str | None
    visualizacoes: int
    ciencia: CienciaResumo | None
    versao: int
    acoes: list[str] = Field(..., description="Ações permitidas ao usuário agora.")


class GravacaoNoticia(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=220)
    linha_fina: str = Field("", max_length=300)
    corpo_html: str = Field("", max_length=200_000)
    categoria_id: int | None = None
    publicar_em: datetime | None = Field(None, description="Vazio: publicação imediata após a aprovação.")
    destaque_ate: datetime | None = Field(None, description="Depois desta data a notícia sai do slider.")
    fixada: bool = False
    exige_ciencia: bool = False
    usuarios_aviso: list[int] = Field(default_factory=list, max_length=500)
    setores_aviso: list[int] = Field(default_factory=list, max_length=200)
    capa_alt: str = Field("", max_length=300)
    versao: int | None = Field(None, description="Versão lida (409 se outra pessoa alterou antes).")


class Aprovacao(BaseModel):
    publicar_em: datetime | None = Field(None, description="Opcional: ajusta a data pedida pelo redator.")


class Devolucao(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=4000)


class RevisaoLeitura(BaseModel):
    versao: int
    descricao: str
    titulo: str
    linha_fina: str
    corpo_html: str
    autor_nome: str
    criado_em: datetime


class PessoaCiencia(BaseModel):
    nome: str
    ciente_em: datetime | None


class CienciaLeitura(BaseModel):
    total: int
    cientes: int
    pessoas: list[PessoaCiencia]


class PapelNoticias(BaseModel):
    nivel: str | None
    redator: bool
    aprovador: bool
    aguardando_aprovacao: int
    contagem: dict[str, int]


class GravacaoCategoria(BaseModel):
    nome: str = Field(..., min_length=1, max_length=60)
    cor: str = Field("#c82331", pattern=r"^#[0-9a-fA-F]{6}$")
    ordem: int = 0
    ativa: bool = True


class GravacaoConfiguracao(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=120)
    subtitulo: str = Field("", max_length=200)
    quantidade_slides: int = Field(..., ge=1, le=10)
    segundos_por_slide: int = Field(..., ge=3, le=60)
    passagem_automatica: bool
    criterio_slider: Literal["automatico", "curadoria"]
    titulo_sobreposto: bool
    quantidade_cartoes: int = Field(..., ge=0, le=12)
    exibir_atalhos: bool
    exibir_todas: bool
    curadoria: list[uuid.UUID] | None = Field(None, description="Na curadoria: ids das notícias do slider, em ordem.")


class ConfiguracaoGestao(BaseModel):
    configuracao: ConfiguracaoLeitura
    curadoria: list[NoticiaCartao]
    candidatas: list[NoticiaCartao] = Field(..., description="Notícias publicadas recentes, para montar a curadoria.")


class Reordenacao(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)
