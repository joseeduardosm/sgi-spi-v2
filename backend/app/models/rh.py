# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Módulo RH (cadastro validado pela CGP, férias e licença-prêmio).
"""Módulo RH.

- `AlteracaoCadastral`: cada campo do perfil alterado pelo usuário fica pendente até a CGP (Coordenadoria
  de Gestão de Pessoas) validar ou recusar (com correção). É também o histórico do cadastro.
- `DadosFuncionais`: campos exclusivos da CGP, invisíveis ao usuário (autorizador, substituto, saldos).
- `Afastamento` e `EventoAfastamento`: férias e licença-prêmio, com o histórico de status.
- `ParametrosRh`: regras de agendamento, editáveis pela CGP (linha única).
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

STATUS_ALTERACAO = ("pendente", "validada", "recusada", "substituida")
TIPOS_AFASTAMENTO = ("ferias", "licenca_premio")
STATUS_AFASTAMENTO = ("pendente", "aprovado", "recusado", "cancelado", "gozado")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class AlteracaoCadastral(Base):
    """Alteração de um campo do perfil: proposta pelo usuário e analisada pela CGP."""
    __tablename__ = "rh_alteracoes_cadastrais"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(STATUS_ALTERACAO)})", name="ck_rh_alteracoes_cadastrais_status"),
        Index("ix_rh_alteracoes_cadastrais_usuario_status", "usuario_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    campo: Mapped[str] = mapped_column(String(40))
    # Valores como texto (datas em AAAA-MM-DD; superior imediato pelo id)
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_proposto: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="pendente")
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    solicitada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    solicitada_por_nome: Mapped[str] = mapped_column(String(200), default="")
    # Análise da CGP
    analisada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    analisada_por_nome: Mapped[str | None] = mapped_column(String(200))
    analisada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    justificativa: Mapped[str | None] = mapped_column(Text)
    valor_corrigido: Mapped[str | None] = mapped_column(Text)


class DadosFuncionais(Base):
    """Campos exclusivos da CGP (o usuário não vê): autorizador de férias/LP, substituto, período aquisitivo e saldo de LP."""
    __tablename__ = "rh_dados_funcionais"
    __table_args__ = (
        CheckConstraint(
            "(inicio_aquisitivo_dia IS NULL AND inicio_aquisitivo_mes IS NULL) OR "
            "(inicio_aquisitivo_mes BETWEEN 1 AND 12 AND inicio_aquisitivo_dia BETWEEN 1 AND "
            "CASE WHEN inicio_aquisitivo_mes = 2 THEN 29 WHEN inicio_aquisitivo_mes IN (4, 6, 9, 11) THEN 30 ELSE 31 END)",
            name="ck_rh_dados_funcionais_inicio_aquisitivo",
        ),
        CheckConstraint("jornada_semanal_horas IS NULL OR jornada_semanal_horas BETWEEN 1 AND 80", name="ck_rh_dados_funcionais_jornada"),
        CheckConstraint("(horario_trabalho_inicio IS NULL) = (horario_trabalho_fim IS NULL)", name="ck_rh_dados_funcionais_horario"),
        CheckConstraint("(intervalo_inicio IS NULL) = (intervalo_fim IS NULL)", name="ck_rh_dados_funcionais_intervalo"),
    )

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    autorizador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    # Quem aprova no lugar DESTE usuário quando ele (como autorizador) estiver afastado
    substituto_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Topo da hierarquia: dispensado de informar superior imediato
    sem_superior: Mapped[bool] = mapped_column(Boolean, default=False)
    # Início do período aquisitivo de férias: só dia e mês (repete todo ano; 29/02 vira 28/02 nos anos comuns)
    inicio_aquisitivo_dia: Mapped[int | None] = mapped_column(Integer)
    inicio_aquisitivo_mes: Mapped[int | None] = mapped_column(Integer)
    # Exercício (ano civil) do saldo de licença-prêmio
    exercicio: Mapped[int | None] = mapped_column(Integer)
    # Obsoleto para férias (o saldo vem dos períodos aquisitivos); mantido só como histórico
    saldo_ferias_dias: Mapped[int] = mapped_column(Integer, default=0)
    saldo_lp_dias: Mapped[int] = mapped_column(Integer, default=0)
    # Jornada e documentos (exclusivos da CGP e da conta root)
    jornada_semanal_horas: Mapped[int | None] = mapped_column(Integer)
    regime_plantao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Horário de trabalho e intervalo de almoço e descanso (início e fim; os dois ou nenhum)
    horario_trabalho_inicio: Mapped[time | None] = mapped_column(Time)
    horario_trabalho_fim: Mapped[time | None] = mapped_column(Time)
    horario_estudante: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    intervalo_inicio: Mapped[time | None] = mapped_column(Time)
    intervalo_fim: Mapped[time | None] = mapped_column(Time)
    # Documentos: RG ou CIN (Carteira de Identidade Nacional) e nº do RS/PV, como texto (ex.: 12.345.678-9 e 1.234.567/8)
    rg_cin: Mapped[str | None] = mapped_column(String(30))
    rs_pv: Mapped[str | None] = mapped_column(String(30))
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    atualizado_por_nome: Mapped[str | None] = mapped_column(String(200))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Afastamento(Base):
    """Férias ou licença-prêmio agendada por um usuário."""
    __tablename__ = "rh_afastamentos"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_AFASTAMENTO)})", name="ck_rh_afastamentos_tipo"),
        CheckConstraint(f"status IN ({_lista(STATUS_AFASTAMENTO)})", name="ck_rh_afastamentos_status"),
        CheckConstraint("fim >= inicio", name="ck_rh_afastamentos_periodo"),
        Index("ix_rh_afastamentos_usuario_exercicio", "usuario_id", "exercicio"),
        Index("ix_rh_afastamentos_periodo", "inicio", "fim"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(20))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    dias: Mapped[int] = mapped_column(Integer)
    exercicio: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="pendente")
    solicitado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_por_nome: Mapped[str | None] = mapped_column(String(200))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    justificativa: Mapped[str | None] = mapped_column(Text)
    # Etapa 1 (ciente e de acordo do superior imediato): enquanto `aguarda_ciencia`, o aprovador ainda não recebe o pedido
    aguarda_ciencia: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    ciencia_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    ciencia_por_nome: Mapped[str | None] = mapped_column(String(200))
    ciencia_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Férias: período aquisitivo em que o afastamento começa (debita o saldo dele)
    periodo_aquisitivo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rh_periodos_aquisitivos.id", ondelete="SET NULL"), index=True)
    # Alteração: o novo pedido aponta o anterior (cancelado quando o novo é aprovado)
    substitui_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rh_afastamentos.id", ondelete="SET NULL"))

    eventos: Mapped[list["EventoAfastamento"]] = relationship(
        back_populates="afastamento", cascade="all, delete-orphan", order_by="EventoAfastamento.ocorrido_em"
    )


class EventoAfastamento(Base):
    """Mudança de status de um afastamento (histórico)."""
    __tablename__ = "rh_afastamentos_eventos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    afastamento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rh_afastamentos.id", ondelete="CASCADE"), index=True)
    de: Mapped[str | None] = mapped_column(String(12))
    para: Mapped[str] = mapped_column(String(12))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200))
    justificativa: Mapped[str | None] = mapped_column(Text)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    afastamento: Mapped[Afastamento] = relationship(back_populates="eventos")


class PeriodoAquisitivo(Base):
    """Período aquisitivo de férias (12 meses): os dias creditados no início valem até o fim e depois expiram."""
    __tablename__ = "rh_periodos_aquisitivos"
    __table_args__ = (
        UniqueConstraint("usuario_id", "inicio", name="uq_rh_periodos_aquisitivos_usuario_inicio"),
        CheckConstraint("origem IN ('automatico', 'ajuste_cgp')", name="ck_rh_periodos_aquisitivos_origem"),
        CheckConstraint("fim > inicio", name="ck_rh_periodos_aquisitivos_datas"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    dias_creditados: Mapped[int] = mapped_column(Integer)
    origem: Mapped[str] = mapped_column(String(12), default="automatico")
    ajustado_por_nome: Mapped[str | None] = mapped_column(String(200))
    # Registro da expiração (saldo não usado que se perdeu no início do período seguinte)
    expirado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dias_expirados: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ParametrosRh(Base):
    """Regras de agendamento (linha única, id = 1), editáveis pela CGP."""
    __tablename__ = "rh_parametros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    minimo_dias_ferias: Mapped[int] = mapped_column(Integer, default=5)
    minimo_dias_lp: Mapped[int] = mapped_column(Integer, default=5)
    # Dias da semana em que o período não pode começar (0 = segunda … 6 = domingo)
    inicio_vedado_ferias: Mapped[list] = mapped_column(JSON, default=lambda: [0])
    inicio_vedado_lp: Mapped[list] = mapped_column(JSON, default=lambda: [0])
    antecedencia_minima_dias: Mapped[int] = mapped_column(Integer, default=30)
    # Cancelar ou alterar: até N dias antes do início
    prazo_cancelamento_dias: Mapped[int] = mapped_column(Integer, default=5)
    permite_emenda: Mapped[bool] = mapped_column(Boolean, default=True)
    # Alerta quando pelo menos N pessoas do mesmo setor estão afastadas ao mesmo tempo
    limite_alerta_setor: Mapped[int] = mapped_column(Integer, default=3)
    # Férias por período aquisitivo: dias creditados e aviso de expiração (folga somada ao saldo e à antecedência)
    dias_ferias_por_periodo: Mapped[int] = mapped_column(Integer, default=30)
    folga_aviso_ferias_dias: Mapped[int] = mapped_column(Integer, default=15)
    aviso_ferias_ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Períodos (férias e LP) não podem começar em feriado ou ponto facultativo cadastrado
    inicio_vedado_feriado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Data em que abre o agendamento das férias do ano seguinte (nulo = sem a regra); ver `servico_afastamentos.agendamento_antecipado`
    abertura_agendamento_ferias: Mapped[date | None] = mapped_column(Date)
    atualizado_por_nome: Mapped[str | None] = mapped_column(String(200))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


TIPOS_FERIADO = ("feriado", "ponto_facultativo")
ABRANGENCIAS_FERIADO = ("nacional", "estadual", "municipal")


class Feriado(Base):
    """Feriado ou ponto facultativo (um por data), cadastrado pela CGP."""
    __tablename__ = "rh_feriados"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_FERIADO)})", name="ck_rh_feriados_tipo"),
        CheckConstraint(f"abrangencia IN ({_lista(ABRANGENCIAS_FERIADO)})", name="ck_rh_feriados_abrangencia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    data: Mapped[date] = mapped_column(Date, unique=True)
    descricao: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(20))
    abrangencia: Mapped[str] = mapped_column(String(10))
    atualizado_por_nome: Mapped[str | None] = mapped_column(String(200))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
