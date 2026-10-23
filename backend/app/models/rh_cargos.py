# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de cargos, ocupações (quem está em cada cargo) e o histórico do RH.
"""Cargos do RH.

- `TipoCargo`: CCESP (cargo em comissão), FCESP (função de confiança) ou OUTRO, editável.
- `Cargo`: **uma posição (vaga)** de um setor, com tipo, grupo (1 ou 2), nível (1 a 18) e denominação (ex.: "FCESP 2.16 – Assessor Especial IV").
  O cargo pertence ao setor; a pessoa que o ocupa passa a fazer parte do setor por ele.
- `Ocupacao`: histórico de quem ocupou cada cargo (início, fim, ato e motivo do fim). Fim vazio = ocupação vigente.
- `HistoricoRh`: livro-razão da vida funcional da pessoa (somente inserção): quem registrou, quando e o quê.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

MOTIVOS_FIM = ("troca", "exoneracao", "dispensa", "outro")


class TipoCargo(Base):
    """Tipo de cargo (CCESP, FCESP, OUTRO...)."""
    __tablename__ = "rh_tipos_cargo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(100))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Cargo(Base):
    """Uma posição (vaga) de um setor. Para N vagas do mesmo cargo, N linhas."""
    __tablename__ = "rh_cargos"
    __table_args__ = (Index("ix_rh_cargos_setor", "setor_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"))
    tipo_id: Mapped[int] = mapped_column(ForeignKey("rh_tipos_cargo.id", ondelete="RESTRICT"))
    # Grupo 1 (direção e chefia) ou 2 (assessoria) e nível de 1 a 18; vazios nos cargos sem classificação (OUTRO)
    grupo: Mapped[int | None] = mapped_column(SmallInteger)
    nivel: Mapped[int | None] = mapped_column(SmallInteger)
    denominacao: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    tipo: Mapped[TipoCargo] = relationship(lazy="joined")
    ocupacoes: Mapped[list["Ocupacao"]] = relationship(back_populates="cargo", order_by="Ocupacao.inicio")

    @property
    def classificacao(self) -> str:
        """"FCESP 2.16", "CCESP 1.07" ou só o tipo (OUTRO, sem nível)."""
        if self.nivel is None:
            return self.tipo.codigo
        return f"{self.tipo.codigo} {self.grupo}.{self.nivel:02d}" if self.grupo else f"{self.tipo.codigo} {self.nivel}"

    @property
    def rotulo(self) -> str:
        """Texto exibido ao lado do nome da pessoa (e guardado em `Usuario.cargo`): "FCESP 2.16 – Assessor Especial IV"."""
        return self.denominacao if self.nivel is None and self.tipo.codigo == "OUTRO" else f"{self.classificacao} – {self.denominacao}"

    @property
    def vigente(self) -> "Ocupacao | None":
        return next((o for o in self.ocupacoes if o.fim is None), None)


class Ocupacao(Base):
    """Quem ocupou o cargo e quando. Uma ocupação vigente (fim vazio) por cargo e uma por pessoa."""
    __tablename__ = "rh_ocupacoes"
    __table_args__ = (
        Index("ux_rh_ocupacao_cargo_vigente", "cargo_id", unique=True, postgresql_where=text("fim IS NULL"), sqlite_where=text("fim IS NULL")),
        Index("ux_rh_ocupacao_usuario_vigente", "usuario_id", unique=True, postgresql_where=text("fim IS NULL"), sqlite_where=text("fim IS NULL")),
        Index("ix_rh_ocupacoes_usuario", "usuario_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cargo_id: Mapped[int] = mapped_column(ForeignKey("rh_cargos.id", ondelete="RESTRICT"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    # Ato que nomeou ou designou (resolução, portaria, decreto...) e o que encerrou a ocupação
    ato: Mapped[str] = mapped_column(String(200), default="")
    motivo_fim: Mapped[str | None] = mapped_column(String(20))
    ato_fim: Mapped[str] = mapped_column(String(200), default="")
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    registrado_por_nome: Mapped[str] = mapped_column(String(200), default="")
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    cargo: Mapped[Cargo] = relationship(back_populates="ocupacoes")


class HistoricoRh(Base):
    """Evento da vida funcional da pessoa. Só se acrescenta: nunca se altera nem se apaga (o sistema não tem rota para isso)."""
    __tablename__ = "rh_historico"
    __table_args__ = (
        Index("ix_rh_historico_usuario", "usuario_id", "ocorrido_em"),
        # A carga retroativa e os ganchos não duplicam o mesmo fato de origem
        Index("ux_rh_historico_origem", "origem_tipo", "origem_id", unique=True, postgresql_where=text("origem_tipo IS NOT NULL"), sqlite_where=text("origem_tipo IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # cadastro, documento, cargo, setor, periodo_ferias, ferias, licenca_premio, exoneracao, admissao, outro
    tipo: Mapped[str] = mapped_column(String(30))
    titulo: Mapped[str] = mapped_column(String(300))
    detalhe: Mapped[str] = mapped_column(Text, default="")
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="Sistema")
    origem_tipo: Mapped[str | None] = mapped_column(String(30))
    origem_id: Mapped[str | None] = mapped_column(String(64))
    # Sigiloso: só o RH vê (ex.: documentos pessoais)
    sigiloso: Mapped[bool] = mapped_column(Boolean, default=False)
    dados: Mapped[dict | None] = mapped_column(JSON)
