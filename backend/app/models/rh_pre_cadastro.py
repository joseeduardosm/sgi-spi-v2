# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas da ficha de pré-cadastro de quem vai entrar na SPI (dados pessoais, formações e experiências).
"""Pré-cadastro do RH.

- `PreCadastro`: ficha de quem ainda vai ganhar conta no SGI. Guarda o **login proposto** (único), que segue para a TI no chamado do GLPI; quando a conta aparece
  no Active Directory (sincronização ou primeiro login), a ficha é vinculada ao usuário (`usuario_id`) e o status vira `vinculado`.
- `FichaFormacao` e `FichaExperiencia`: de 1 a N por ficha.

Dados sensíveis (CPF, RG, endereço, PIS...): só o RH acessa (ACL `rh`, controle total).
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

# Situação da ficha: rascunho (RH ainda preenche), aguardando_conta (pronta; a conta ainda não existe no AD), vinculado (conta localizada) e cancelado
STATUS_FICHA = ("rascunho", "aguardando_conta", "vinculado", "cancelado")


class PreCadastro(Base):
    """Ficha de pré-cadastro de emprego preenchida pelo RH."""
    __tablename__ = "rh_pre_cadastros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="rascunho", index=True)
    login_proposto: Mapped[str | None] = mapped_column(String(60))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    vinculado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Identificação
    nome_completo: Mapped[str] = mapped_column(String(200))
    nome_social: Mapped[str] = mapped_column(String(200), default="")
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    sexo: Mapped[str] = mapped_column(String(20), default="")
    estado_civil: Mapped[str] = mapped_column(String(30), default="")
    nacionalidade: Mapped[str] = mapped_column(String(60), default="")
    naturalidade_cidade: Mapped[str] = mapped_column(String(100), default="")
    naturalidade_uf: Mapped[str] = mapped_column(String(2), default="")
    nome_mae: Mapped[str] = mapped_column(String(200), default="")
    nome_pai: Mapped[str] = mapped_column(String(200), default="")

    # Documentos (CPF e PIS só com dígitos)
    cpf: Mapped[str] = mapped_column(String(11), default="")
    rg_numero: Mapped[str] = mapped_column(String(30), default="")
    rg_orgao: Mapped[str] = mapped_column(String(30), default="")
    rg_uf: Mapped[str] = mapped_column(String(2), default="")
    rg_emissao: Mapped[date | None] = mapped_column(Date)
    cin: Mapped[str] = mapped_column(String(30), default="")
    pis_pasep: Mapped[str] = mapped_column(String(11), default="")
    titulo_numero: Mapped[str] = mapped_column(String(20), default="")
    titulo_zona: Mapped[str] = mapped_column(String(5), default="")
    titulo_secao: Mapped[str] = mapped_column(String(5), default="")
    ctps_numero: Mapped[str] = mapped_column(String(20), default="")
    ctps_serie: Mapped[str] = mapped_column(String(10), default="")
    ctps_uf: Mapped[str] = mapped_column(String(2), default="")
    cnh: Mapped[str] = mapped_column(String(20), default="")

    # Contato
    email_pessoal: Mapped[str] = mapped_column(String(200), default="")
    telefone: Mapped[str] = mapped_column(String(30), default="")
    celular: Mapped[str] = mapped_column(String(30), default="")
    emergencia_nome: Mapped[str] = mapped_column(String(200), default="")
    emergencia_parentesco: Mapped[str] = mapped_column(String(60), default="")
    emergencia_telefone: Mapped[str] = mapped_column(String(30), default="")

    # Endereço
    cep: Mapped[str] = mapped_column(String(8), default="")
    logradouro: Mapped[str] = mapped_column(String(200), default="")
    numero: Mapped[str] = mapped_column(String(20), default="")
    complemento: Mapped[str] = mapped_column(String(100), default="")
    bairro: Mapped[str] = mapped_column(String(100), default="")
    cidade: Mapped[str] = mapped_column(String(100), default="")
    uf: Mapped[str] = mapped_column(String(2), default="")

    # Vínculo com o serviço público
    vinculo_tipo: Mapped[str] = mapped_column(String(60), default="")
    orgao_origem: Mapped[str] = mapped_column(String(200), default="")
    cargo_origem: Mapped[str] = mapped_column(String(200), default="")
    rs_pv: Mapped[str] = mapped_column(String(30), default="")
    inicio_previsto: Mapped[date | None] = mapped_column(Date)
    cargo_id: Mapped[int | None] = mapped_column(ForeignKey("rh_cargos.id", ondelete="SET NULL"), index=True)
    observacoes: Mapped[str] = mapped_column(Text, default="")

    # Ficha de quem já tinha conta (legados): a pessoa preenche (`enviada_em`) e o RH valida (`validado_em`)
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    formacoes: Mapped[list["FichaFormacao"]] = relationship(cascade="all, delete-orphan", order_by="FichaFormacao.id", lazy="selectin")
    experiencias: Mapped[list["FichaExperiencia"]] = relationship(cascade="all, delete-orphan", order_by="FichaExperiencia.id", lazy="selectin")


# Login proposto único (sem diferenciar maiúsculas) entre as fichas não canceladas
Index("ux_rh_pre_cadastros_login", func.lower(PreCadastro.login_proposto), unique=True, postgresql_where=PreCadastro.status != "cancelado",
      sqlite_where=PreCadastro.status != "cancelado")


class FichaFormacao(Base):
    """Formação acadêmica da ficha (de 1 a N)."""
    __tablename__ = "rh_ficha_formacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pre_cadastro_id: Mapped[int] = mapped_column(ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), index=True)
    nivel: Mapped[str] = mapped_column(String(60), default="")
    curso: Mapped[str] = mapped_column(String(200), default="")
    instituicao: Mapped[str] = mapped_column(String(200), default="")
    ano_conclusao: Mapped[int | None] = mapped_column(Integer)
    em_andamento: Mapped[bool] = mapped_column(Boolean, default=False)


class FichaExperiencia(Base):
    """Experiência profissional anterior (de 1 a N)."""
    __tablename__ = "rh_ficha_experiencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pre_cadastro_id: Mapped[int] = mapped_column(ForeignKey("rh_pre_cadastros.id", ondelete="CASCADE"), index=True)
    empresa: Mapped[str] = mapped_column(String(200), default="")
    cargo: Mapped[str] = mapped_column(String(200), default="")
    inicio: Mapped[date | None] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    descricao: Mapped[str] = mapped_column(Text, default="")
