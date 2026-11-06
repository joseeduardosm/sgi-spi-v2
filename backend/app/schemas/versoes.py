# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de entrada e saída da tela Administração › Versões (atualização do SGI pelo GitHub).
"""Schemas das versões do sistema (homologação aprova, produção instala)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CommitVersao(BaseModel):
    """Um commit que a atualização traria."""
    commit: str = Field(..., description="Hash curto.")
    titulo: str
    autor: str
    data: datetime


class VersaoAprovada(BaseModel):
    """Versão aprovada na homologação (tag `vAAAA.MM.DD[.N]`) mais nova que a em execução."""
    alvo: str = Field(..., description="Nome da tag (é o `alvo` de `POST …/atualizar`).")
    aprovada_por: str | None
    aprovada_em: datetime | None
    mensagem: str = Field(..., description="Mensagem da tag: quem aprovou, quando e as novidades do CHANGELOG.")
    novidades: str = Field(..., description="O que o CHANGELOG.md ganhou entre a versão em execução e esta.")
    commits: list[CommitVersao]


class AndamentoAtualizacao(BaseModel):
    """Situação da última atualização (roda na unidade `sgi-spi-atualizar`, fora da API)."""
    operacao: Literal["atualizar"] | None = None
    situacao: Literal["em_andamento", "concluido", "erro", "reiniciando"] | None = Field(
        None, description="`reiniciando`: a API está reiniciando com a versão nova; consulte `GET /api/saude` até voltar.")
    mensagem: str = ""
    etapa: str | None = Field(None, description="`conferir`, `backup`, `codigo`, `dependencias`, `migracoes`, `build`, `reiniciar`. No erro, a etapa em que parou.")
    percentual: float | None = None
    de: str | None = Field(None, description="Versão de antes.")
    para: str | None = Field(None, description="Versão pedida.")
    voltou: bool | None = Field(None, description="No erro: `true` se a volta automática deixou o sistema na versão anterior; `false` se ela também falhou.")
    atualizado_em: datetime | None = None


class PainelVersoes(BaseModel):
    """Tela Administração › Versões."""
    homologacao: bool = Field(..., description="Servidor de homologação (aprova versões e acompanha o ramo) ou produção (instala versões aprovadas).")
    versao: str = Field(..., description="Versão da API em execução.")
    versao_no_disco: str = Field(..., description="Versão do código no disco (difere de `versao` enquanto a API não reinicia).")
    commit: str
    arvore_limpa: bool = Field(..., description="Sem alteração local em arquivo versionado; com alteração, atualizar e aprovar ficam bloqueados.")
    ramo: str = Field(..., description="Ramo do GitHub acompanhado pela homologação.")
    aprovada: str | None = Field(None, description="Homologação: a tag que já aprova a versão em execução, se houver.")
    commits_novos: list[CommitVersao] = Field(..., description="Homologação: commits do ramo que a atualização traria.")
    versoes: list[VersaoAprovada] = Field(..., description="Produção: versões aprovadas mais novas que a em execução.")
    andamento: AndamentoAtualizacao
    log: str = Field("", description="Final do log da última atualização (quando deu erro).")


class PedidoAtualizacao(BaseModel):
    alvo: str = Field(..., max_length=120, description="Produção: a tag aprovada. Homologação: o nome do ramo acompanhado.")
    confirmacao: str = Field(..., description="Precisa ser `ATUALIZAR`.")


class VersaoAprovadaAgora(BaseModel):
    tag: str = Field(..., description="Tag criada e enviada ao GitHub.")
