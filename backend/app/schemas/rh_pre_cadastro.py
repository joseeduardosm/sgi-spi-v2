# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de entrada e saída das rotas da ficha de pré-cadastro do RH.
"""Schemas do pré-cadastro: ficha completa (dados pessoais, documentos, contato, endereço, vínculo), formações, experiências e checagem de login."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StatusFicha = Literal["rascunho", "aguardando_conta", "vinculado", "cancelado"]


class Formacao(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nivel: str = Field("", max_length=60, description="Ex.: Ensino médio, Graduação, Pós-graduação, Mestrado.")
    curso: str = Field("", max_length=200)
    instituicao: str = Field("", max_length=200)
    ano_conclusao: int | None = Field(None, ge=1950, le=2100)
    em_andamento: bool = False


class Experiencia(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    empresa: str = Field("", max_length=200)
    cargo: str = Field("", max_length=200)
    inicio: date | None = None
    fim: date | None = None
    descricao: str = Field("", max_length=4000)


class CamposFicha(BaseModel):
    """Dados da ficha (iguais na leitura e na gravação). CPF, PIS e CEP aceitam máscara; são gravados só com dígitos."""
    model_config = ConfigDict(from_attributes=True)

    # Identificação
    nome_completo: str = Field(..., min_length=3, max_length=200)
    nome_social: str = Field("", max_length=200)
    data_nascimento: date | None = None
    sexo: str = Field("", max_length=20)
    estado_civil: str = Field("", max_length=30)
    nacionalidade: str = Field("", max_length=60)
    naturalidade_cidade: str = Field("", max_length=100)
    naturalidade_uf: str = Field("", max_length=2)
    nome_mae: str = Field("", max_length=200)
    nome_pai: str = Field("", max_length=200)
    # Documentos
    cpf: str = Field("", max_length=14, description="Com ou sem máscara; os dígitos verificadores são conferidos.")
    rg_numero: str = Field("", max_length=30)
    rg_orgao: str = Field("", max_length=30)
    rg_uf: str = Field("", max_length=2)
    rg_emissao: date | None = None
    cin: str = Field("", max_length=30)
    pis_pasep: str = Field("", max_length=14)
    titulo_numero: str = Field("", max_length=20)
    titulo_zona: str = Field("", max_length=5)
    titulo_secao: str = Field("", max_length=5)
    ctps_numero: str = Field("", max_length=20)
    ctps_serie: str = Field("", max_length=10)
    ctps_uf: str = Field("", max_length=2)
    cnh: str = Field("", max_length=20)
    # Contato
    email_pessoal: str = Field("", max_length=200)
    telefone: str = Field("", max_length=30)
    celular: str = Field("", max_length=30)
    emergencia_nome: str = Field("", max_length=200)
    emergencia_parentesco: str = Field("", max_length=60)
    emergencia_telefone: str = Field("", max_length=30)
    # Endereço
    cep: str = Field("", max_length=9)
    logradouro: str = Field("", max_length=200)
    numero: str = Field("", max_length=20)
    complemento: str = Field("", max_length=100)
    bairro: str = Field("", max_length=100)
    cidade: str = Field("", max_length=100)
    uf: str = Field("", max_length=2)
    # Vínculo
    vinculo_tipo: str = Field("", max_length=60, description="Ex.: Servidor efetivo cedido, Comissionado sem vínculo.")
    orgao_origem: str = Field("", max_length=200)
    cargo_origem: str = Field("", max_length=200)
    rs_pv: str = Field("", max_length=30)
    inicio_previsto: date | None = None
    cargo_id: int | None = Field(None, description="Cargo (vaga) pretendido, de RH > Cargos.")
    observacoes: str = Field("", max_length=4000)


class GravacaoFicha(CamposFicha):
    """Criação e alteração da ficha. `formacoes` e `experiencias` **substituem** as listas anteriores."""
    login_proposto: str | None = Field(None, max_length=60, description="Login que a TI vai criar no AD; precisa estar livre (ver `login-disponivel`).")
    status: Literal["rascunho", "aguardando_conta"] = Field("rascunho", description="`aguardando_conta` = ficha pronta; exige o login proposto.")
    formacoes: list[Formacao] = Field(default_factory=list, max_length=30)
    experiencias: list[Experiencia] = Field(default_factory=list, max_length=50)


class GravacaoMinhaFicha(CamposFicha):
    """Ficha preenchida pela própria pessoa (quem já tinha conta antes do pré-cadastro): vai para validação do RH. Não leva login, status nem cargo pretendido."""
    formacoes: list[Formacao] = Field(default_factory=list, max_length=30)
    experiencias: list[Experiencia] = Field(default_factory=list, max_length=50)


class LeituraFicha(CamposFicha):
    id: int
    status: StatusFicha
    login_proposto: str | None
    usuario_id: int | None
    usuario_nome: str | None = None
    vinculado_em: datetime | None
    enviada_em: datetime | None = None
    validado_em: datetime | None = None
    cargo_rotulo: str | None = None
    criado_em: datetime
    atualizado_em: datetime
    formacoes: list[Formacao]
    experiencias: list[Experiencia]


class ResumoFicha(BaseModel):
    """Linha da lista de fichas (sem dados sensíveis)."""
    id: int
    nome_completo: str
    status: StatusFicha
    login_proposto: str | None
    usuario_id: int | None
    cargo_rotulo: str | None
    inicio_previsto: date | None
    enviada_em: datetime | None = None
    validado_em: datetime | None = None
    atualizado_em: datetime


class LoginDisponivel(BaseModel):
    """Resultado da checagem do login proposto."""
    login: str
    disponivel: bool
    verificado_no_ad: bool = Field(description="`false` quando não há diretório LDAP ativo ou o AD não respondeu (o login só foi conferido no SGI).")
    motivo: Literal["livre", "formato", "usuario", "ficha", "ad", "ad_indisponivel"]
    detalhe: str


class LinhaImportacaoFicha(BaseModel):
    linha: int = Field(description="Linha da planilha (aba Fichas); 0 quando o erro é de outra aba.")
    nome: str
    cpf: str
    login_proposto: str
    cargo_pretendido: str
    erros: list[str]
    ficha_id: int | None = Field(None, description="Ficha criada (só na importação concluída).")


class ResultadoImportacaoFichas(BaseModel):
    total: int
    com_erro: int
    gravado: bool = Field(description="`true` só na importação concluída; a prévia nunca grava.")
    linhas: list[LinhaImportacaoFicha]
