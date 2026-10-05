# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da abertura de chamado pelo SGI.
"""Schemas de `/api/chamados`."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DadosSolicitante(BaseModel):
    """Dados do cadastro do usuário que acompanham o chamado (a tela os mostra, somente leitura)."""

    nome: str
    setor: str = Field("", description="Departamento do perfil.")
    superior_imediato: str = ""
    email: str = ""
    telefone: str = Field("", description="Ramal.")
    celular: str = Field("", description="Só vem preenchido quando o usuário informou.")
    andar_lado: str = Field("", description="Ex.: `5º andar - A`.")
    aguardando_validacao: list[str] = Field(default_factory=list, description="Campos do cadastro cujo valor ainda é uma alteração aguardando validação da CGP (valem como temporários no chamado).")


class AberturaChamado(BaseModel):
    """Corpo do `POST /api/chamados`."""

    assunto: str = Field(..., min_length=3, max_length=200, description="Título do chamado.")
    descricao: str = Field(..., min_length=10, max_length=5000, description="Descrição do problema.")
    local_id: int = Field(..., ge=1, description="Local do problema: id de uma localização do GLPI (`GET /api/chamados/locais`). Obrigatório, como no formulário do GLPI.")

    @field_validator("assunto", "descricao")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Tira espaços das pontas; texto só de espaços não vale."""
        valor = valor.strip()
        if not valor:
            raise ValueError("informe o texto")
        return valor


class LocalChamado(BaseModel):
    """Uma localização do GLPI para a pergunta "Local do Problema"."""

    id: int
    nome: str = Field(..., description="Nome completo, ex.: `05º Andar > Lado B`.")


class ListaLocais(BaseModel):
    """Localizações do GLPI, em ordem alfabética."""

    itens: list[LocalChamado]


class ChamadoAberto(BaseModel):
    """Chamado criado no GLPI."""

    glpi_id: int = Field(..., description="Número do chamado no GLPI.")
    assunto: str
    url: str = Field(..., description="Endereço do chamado no GLPI.")
    aberto_em: datetime
    anexos_enviados: int = Field(0, description="Quantos anexos chegaram ao chamado.")
    anexos_com_falha: list[str] = Field(default_factory=list, description="Nomes dos anexos que o GLPI não aceitou (o chamado foi aberto mesmo assim).")


class ListaChamados(BaseModel):
    """Últimos chamados abertos pelo usuário no SGI."""

    itens: list[ChamadoAberto]
