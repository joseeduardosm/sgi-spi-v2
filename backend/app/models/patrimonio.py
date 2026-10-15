# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do módulo Patrimônio (bens móveis do prédio SPI): localizações, bens, movimentações, classificações e baixas.
"""Módulo Patrimônio.

- `Localizacao`: árvore de até cinco níveis (prédio, andar, lado, sala e um nível reservado). A sala guarda setor e responsável.
- `GrupoMaterial`: grupo de material com vida útil e residual (parâmetros da depreciação).
- `Bem`: o bem móvel (chapa, descrição, sala, situação, valores, garantia...). Nunca é excluído.
- `FotoBem`: até três fotos por bem (arquivos em `anexos`).
- `EventoPatrimonio`: histórico **somente de inserção** (campo alterado, valor anterior e novo, quem, quando e de onde). O banco barra UPDATE e DELETE.
- `Movimentacao` / `ItemMovimentacao`: troca de local com autorização e recebimento parcial.
- `Classificacao` / `ItemClassificacao`: lista de bens inservíveis ou extraviados, com justificativa, enviada para aprovação.
- `Baixa` / `ItemBaixa`: baixa dos bens já classificados, com motivo e número do processo.
- `ParametroPatrimonio`: parâmetros editáveis pelo controle total (ex.: valor da UFESP).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

# Níveis da árvore de localizações (o quinto fica reservado para usos futuros)
TIPOS_LOCALIZACAO = ("predio", "andar", "lado", "sala", "reservado")
SITUACOES_BEM = ("ativo", "em_manutencao", "inservivel", "extraviado", "baixado")
ORIGENS_BEM = ("proprio", "terceiros")


class Localizacao(Base):
    """Nó da árvore de localizações (prédio SPI > andar > lado > sala)."""
    __tablename__ = "patrimonio_localizacoes"
    __table_args__ = (Index("ix_patrimonio_localizacoes_pai", "pai_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="RESTRICT"))
    tipo: Mapped[str] = mapped_column(String(10))
    nome: Mapped[str] = mapped_column(String(200))
    # Só as salas têm código (ex.: 05A03, 00B15, -1A01); único em todo o sistema
    codigo: Mapped[str | None] = mapped_column(String(10), unique=True)
    # Andar (-1 = subsolo, 0 = térreo) e lado (A/B), gravados também nas salas para ordenar e filtrar sem percorrer a árvore
    andar: Mapped[int | None] = mapped_column(Integer)
    lado: Mapped[str | None] = mapped_column(String(1))
    # Só nas salas: setor e responsável, informados no primeiro cadastro de bem feito ali
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="SET NULL"))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    pai: Mapped["Localizacao | None"] = relationship(remote_side="Localizacao.id", back_populates="filhos")
    filhos: Mapped[list["Localizacao"]] = relationship(back_populates="pai")
    setor = relationship("Setor", foreign_keys=[setor_id])
    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])


class GrupoMaterial(Base):
    """Grupo de material do SAM, com os parâmetros de depreciação (a vida útil oficial ainda será obtida: fica editável)."""
    __tablename__ = "patrimonio_grupos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    # Vida útil em meses; nulo = ainda não definida (o bem não deprecia por cálculo)
    vida_util_meses: Mapped[int | None] = mapped_column(Integer)
    residual_percentual: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10"))
    # Bens culturais e de terceiros não depreciam
    deprecia: Mapped[bool] = mapped_column(Boolean, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class PrefixoChapa(Base):
    """Prefixo que vem antes do número da chapa (SPI, SLT, DERSA...). Um é o padrão do cadastro; os demais se escolhem na tela."""
    __tablename__ = "patrimonio_prefixos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Sempre em maiúsculas, só letras e números
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    padrao: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class Bem(Base):
    """Bem móvel. Nunca é excluído: baixado, sai dos painéis mas o histórico permanece."""
    __tablename__ = "patrimonio_bens"
    __table_args__ = (Index("ix_patrimonio_bens_situacao", "situacao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Identificador gerado no aparelho: o reenvio de um cadastro feito offline não duplica o bem
    id_cliente: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Opcional: ativos importados do GLPI podem não ter patrimônio e então só têm o número de série (o banco aceita vários nulos na unicidade)
    chapa: Mapped[str | None] = mapped_column(String(60))
    # Chapa em minúsculas e sem espaços nas pontas: garante a unicidade no banco (aceita qualquer formato)
    chapa_chave: Mapped[str | None] = mapped_column(String(60), unique=True)
    descricao: Mapped[str] = mapped_column(String(300))
    localizacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="RESTRICT"), index=True)
    conservacao: Mapped[int] = mapped_column(Integer)
    situacao: Mapped[str] = mapped_column(String(15), default="ativo")
    origem: Mapped[str] = mapped_column(String(10), default="proprio")
    grupo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_grupos.id", ondelete="SET NULL"))
    uge: Mapped[str | None] = mapped_column(String(40))
    ua: Mapped[str | None] = mapped_column(String(40))
    divisao: Mapped[str | None] = mapped_column(String(80))
    # Cópia do responsável da sala (muda junto com ela ou na movimentação); não se edita no bem
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    valor_aquisicao: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    valor_atual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    data_aquisicao: Mapped[date | None] = mapped_column(Date)
    garantia_meses: Mapped[int | None] = mapped_column(Integer)
    marca: Mapped[str | None] = mapped_column(String(80))
    modelo: Mapped[str | None] = mapped_column(String(80))
    numero_serie: Mapped[str | None] = mapped_column(String(80))
    nota_fiscal: Mapped[str | None] = mapped_column(String(60))
    fornecedor: Mapped[str | None] = mapped_column(String(200))
    observacoes: Mapped[str | None] = mapped_column(Text)
    # "Classificação pendente": o bem está numa lista enviada para aprovação e não pode ser movimentado
    classificacao_pendente: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
    baixado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    localizacao: Mapped[Localizacao] = relationship(foreign_keys=[localizacao_id])
    grupo: Mapped[GrupoMaterial | None] = relationship()
    responsavel = relationship("Usuario", foreign_keys=[responsavel_id])
    fotos: Mapped[list["FotoBem"]] = relationship(back_populates="bem", cascade="all, delete-orphan", order_by="FotoBem.ordem")

    @property
    def rotulo(self) -> str:
        """Como o bem aparece nas telas e mensagens: a chapa ou, sem ela, o número de série ("S/N ...")."""
        if self.chapa:
            return self.chapa
        return f"S/N {self.numero_serie}" if self.numero_serie else "Sem identificação"

    @property
    def dados_contabeis_pendentes(self) -> bool:
        """Sem grupo, valor de aquisição ou data de aquisição: o bem entra na contagem, mas fica fora dos totais de valor."""
        return self.grupo_id is None or self.valor_aquisicao is None or self.data_aquisicao is None


class FotoBem(Base):
    """Foto do bem (até três); o arquivo fica em `anexos`."""
    __tablename__ = "patrimonio_fotos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    bem: Mapped[Bem] = relationship(back_populates="fotos")
    anexo = relationship("Anexo")


class EventoPatrimonio(Base):
    """Histórico do bem: **só inserção** (o banco barra UPDATE e DELETE). Um registro por campo alterado ou por acontecimento."""
    __tablename__ = "patrimonio_eventos"
    __table_args__ = (Index("ix_patrimonio_eventos_bem", "bem_id", "ocorrido_em"), Index("ix_patrimonio_eventos_campo", "bem_id", "campo"))

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="RESTRICT"))
    # cadastrou, alterou, moveu, ajustou_local, localizou, classificou, reverteu, baixou, responsavel
    tipo: Mapped[str] = mapped_column(String(40))
    campo: Mapped[str | None] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_novo: Mapped[str | None] = mapped_column(Text)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    # De onde veio a mudança (endereço IP e canal: web, celular ou fila offline)
    origem: Mapped[str | None] = mapped_column(String(80))
    texto: Mapped[str] = mapped_column(Text, default="")
    # Trajeto: locais de origem e destino, quem pediu e quem autorizou
    dados: Mapped[dict | None] = mapped_column(TipoJson)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class Movimentacao(Base):
    """Troca de local de um ou mais bens: solicitação, autorização, recebimento parcial e conclusão."""
    __tablename__ = "patrimonio_movimentacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_cliente: Mapped[str | None] = mapped_column(String(64), unique=True)
    destino_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="RESTRICT"))
    motivo: Mapped[str] = mapped_column(Text)
    # pendente > autorizada > concluida; ou recusada / cancelada
    status: Mapped[str] = mapped_column(String(12), default="pendente", index=True)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_recusa: Mapped[str | None] = mapped_column(Text)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    destino: Mapped[Localizacao] = relationship(foreign_keys=[destino_id])
    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    decidido_por = relationship("Usuario", foreign_keys=[decidido_por_id])
    itens: Mapped[list["ItemMovimentacao"]] = relationship(back_populates="movimentacao", cascade="all, delete-orphan")


class ItemMovimentacao(Base):
    """Um bem da movimentação. `recebido_em` preenchido = o bem já chegou ao destino."""
    __tablename__ = "patrimonio_itens_movimentacao"
    __table_args__ = (UniqueConstraint("movimentacao_id", "bem_id", name="uq_patrimonio_itens_movimentacao_bem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    movimentacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_movimentacoes.id", ondelete="CASCADE"), index=True)
    bem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="RESTRICT"), index=True)
    origem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="RESTRICT"))
    recebido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recebido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    movimentacao: Mapped[Movimentacao] = relationship(back_populates="itens")
    bem: Mapped[Bem] = relationship()
    origem: Mapped[Localizacao] = relationship(foreign_keys=[origem_id])


class Classificacao(Base):
    """Lista de bens a classificar como inservíveis ou extraviados. Rascunho até ser enviada para aprovação."""
    __tablename__ = "patrimonio_classificacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_cliente: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Número de exibição (#12), sequência única entre listas de inservíveis, de extraviados e baixas
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    tipo: Mapped[str] = mapped_column(String(10))
    # rascunho > pendente > aprovada / parcial / recusada
    status: Mapped[str] = mapped_column(String(10), default="rascunho", index=True)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_recusa: Mapped[str | None] = mapped_column(Text)

    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    decidido_por = relationship("Usuario", foreign_keys=[decidido_por_id])
    itens: Mapped[list["ItemClassificacao"]] = relationship(back_populates="classificacao", cascade="all, delete-orphan")


class ItemClassificacao(Base):
    __tablename__ = "patrimonio_itens_classificacao"
    __table_args__ = (UniqueConstraint("classificacao_id", "bem_id", name="uq_patrimonio_itens_classificacao_bem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    classificacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_classificacoes.id", ondelete="CASCADE"), index=True)
    bem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="RESTRICT"), index=True)
    justificativa: Mapped[str | None] = mapped_column(Text)
    # Boletim de ocorrência, e-mail ou foto (extraviado) / foto (inservível)
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    situacao_anterior: Mapped[str | None] = mapped_column(String(15))
    # aprovado / recusado (nulo enquanto a lista não foi decidida)
    resultado: Mapped[str | None] = mapped_column(String(10))

    classificacao: Mapped[Classificacao] = relationship(back_populates="itens")
    bem: Mapped[Bem] = relationship()
    anexo = relationship("Anexo")


class Baixa(Base):
    """Baixa de bens já classificados como inservíveis ou extraviados."""
    __tablename__ = "patrimonio_baixas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_cliente: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Número de exibição (#12), sequência única entre listas de inservíveis, de extraviados e baixas
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(10), default="rascunho", index=True)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_recusa: Mapped[str | None] = mapped_column(Text)
    # Termo em PDF gerado na aprovação (instrui o processo; a baixa no SAM é feita à parte)
    termo_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))

    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    decidido_por = relationship("Usuario", foreign_keys=[decidido_por_id])
    itens: Mapped[list["ItemBaixa"]] = relationship(back_populates="baixa", cascade="all, delete-orphan")


class ItemBaixa(Base):
    __tablename__ = "patrimonio_itens_baixa"
    __table_args__ = (UniqueConstraint("baixa_id", "bem_id", name="uq_patrimonio_itens_baixa_bem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    baixa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_baixas.id", ondelete="CASCADE"), index=True)
    bem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="RESTRICT"), index=True)
    # alienacao, doacao, transferencia, inutilizacao ou extravio; vale para a seleção toda ou por grupos de bens
    motivo: Mapped[str | None] = mapped_column(String(15))
    processo: Mapped[str | None] = mapped_column(String(80))
    situacao_anterior: Mapped[str | None] = mapped_column(String(15))
    resultado: Mapped[str | None] = mapped_column(String(10))

    baixa: Mapped[Baixa] = relationship(back_populates="itens")
    bem: Mapped[Bem] = relationship()


class ParametroPatrimonio(Base):
    """Parâmetro editável do módulo (chave e valor em texto)."""
    __tablename__ = "patrimonio_parametros"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
