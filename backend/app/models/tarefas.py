# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do Módulo Tarefas (equipes, tarefas, responsáveis, linha do tempo, marcadores e checklist).
"""Módulo Tarefas.

- `EquipeTarefas`: equipe própria do módulo (independente dos setores), com dono, líderes, membros e equipe pai.
- `Tarefa`: a tarefa, com pipeline A fazer → Em andamento → Em validação → Concluída, prazo atual e **prazo original**,
  datas de cada etapa e `versao` (concorrência otimista).
- `ResponsavelTarefa`: todos os responsáveis da tarefa (um ou mais, com os mesmos poderes; `Tarefa.responsavel_id` é o principal, o primeiro); a carga conta para cada um.
- `EventoTarefa`: linha do tempo append-only (criação, edição, status, prazo, transferência, comentário…). Guarda o
  nome do autor como retrato (o histórico continua legível se o usuário sair) e `dados` com de/para e justificativas.
- `MarcadorTarefa`: etiqueta por equipe (ou global, sem equipe); `ItemChecklistTarefa`: checklist da tarefa.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc

FREQUENCIAS_RECORRENCIA = ("diaria", "semanal", "mensal", "anual")
STATUS_TAREFA = ("a_fazer", "em_andamento", "em_validacao", "concluida")
PRIORIDADES_TAREFA = ("baixa", "normal", "alta", "critica")
TIPOS_EVENTO_TAREFA = (
    "criada", "editada", "status", "entregue", "validada", "devolvida", "reaberta", "prazo", "transferida",
    "comentario", "participantes", "marcadores", "checklist", "removido", "escalonada", "atividade", "contrato",
)
SITUACOES_STATUS_EQUIPE = ("no_prazo", "em_risco", "atrasado", "em_espera", "concluido")
TIPOS_ATIVIDADE = ("fazer", "ligar", "email", "reuniao", "revisar", "enviar_documento")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class EquipeTarefas(Base):
    """Equipe do módulo: o dono governa a composição; os líderes validam, devolvem e reabrem tarefas da equipe."""
    __tablename__ = "tarefas_equipes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150))
    dono_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    equipe_pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="SET NULL"))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    membros: Mapped[list["MembroEquipeTarefas"]] = relationship(back_populates="equipe", cascade="all, delete-orphan", lazy="selectin")
    lideres: Mapped[list["LiderEquipeTarefas"]] = relationship(back_populates="equipe", cascade="all, delete-orphan", lazy="selectin")


class MembroEquipeTarefas(Base):
    __tablename__ = "tarefas_equipes_membros"
    __table_args__ = (UniqueConstraint("equipe_id", "usuario_id", name="uq_tarefas_equipes_membros"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    equipe: Mapped[EquipeTarefas] = relationship(back_populates="membros")


class LiderEquipeTarefas(Base):
    __tablename__ = "tarefas_equipes_lideres"
    __table_args__ = (UniqueConstraint("equipe_id", "usuario_id", name="uq_tarefas_equipes_lideres"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    equipe: Mapped[EquipeTarefas] = relationship(back_populates="lideres")


class Tarefa(Base):
    __tablename__ = "tarefas"
    __table_args__ = (
        UniqueConstraint("recorrencia_id", "ocorrencia_em", name="uq_tarefas_recorrencia_ocorrencia"),
        # Tarefa nascida de outro módulo (ex.: etapa de uma competência de contrato): uma só por origem e chave
        UniqueConstraint("origem_tipo", "origem_id", "origem_chave", name="uq_tarefas_origem"),
        CheckConstraint(f"status IN ({_lista(STATUS_TAREFA)})", name="ck_tarefas_status"),
        CheckConstraint(f"prioridade IN ({_lista(PRIORIDADES_TAREFA)})", name="ck_tarefas_prioridade"),
        Index("ix_tarefas_responsavel_status", "responsavel_id", "status"),
        Index("ix_tarefas_equipe_status", "equipe_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Número público (#123), atribuído pelo serviço (maior + 1); os migrados mantêm o número do sistema anterior
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text, default="")
    equipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="SET NULL"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    prazo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Prazo definido na criação: mostra quanto a tarefa foi prorrogada
    prazo_original: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    status: Mapped[str] = mapped_column(String(15), default="a_fazer")
    # Ordem manual (arrastar na lista); menor aparece antes
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    # Datas de cada etapa do pipeline e tempo acumulado em andamento (segundos)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    em_andamento_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    segundos_em_andamento: Mapped[int] = mapped_column(BigInteger, default=0)
    entregue_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    versao: Mapped[int] = mapped_column(Integer, default=1)
    # Marco (milestone) da equipe a que a tarefa pertence
    marco_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_marcos.id", ondelete="SET NULL"), index=True)
    # Estágio (coluna do quadro da equipe); vazio = o primeiro estágio da categoria da situação atual
    estagio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_estagios.id", ondelete="SET NULL"), index=True)
    # Subtarefa: a tarefa mãe (um nível); excluir a mãe leva as subtarefas
    tarefa_pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    # Recorrência: série de origem e a data do prazo da ocorrência (única por série)
    recorrencia_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_recorrencias.id", ondelete="SET NULL"), index=True)
    ocorrencia_em: Mapped[date | None] = mapped_column(Date)
    # Origem em outro módulo (ex.: "contrato_competencia" + id da competência + chave da etapa). `controlada_externamente`: quem a move é o
    # módulo de origem (o usuário só comenta, anexa e segue); falsa nas tarefas manuais que nascem junto, como "Subir no SEI"
    origem_tipo: Mapped[str | None] = mapped_column(String(30))
    origem_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    origem_chave: Mapped[str | None] = mapped_column(String(80))
    controlada_externamente: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    equipe: Mapped[EquipeTarefas | None] = relationship(lazy="joined")
    responsaveis: Mapped[list["ResponsavelTarefa"]] = relationship(back_populates="tarefa", cascade="all, delete-orphan", lazy="selectin")
    marcadores: Mapped[list["MarcadorTarefa"]] = relationship(secondary="tarefas_marcadores_vinculos", lazy="selectin")
    checklist: Mapped[list["ItemChecklistTarefa"]] = relationship(
        back_populates="tarefa", cascade="all, delete-orphan", order_by="ItemChecklistTarefa.posicao", lazy="selectin"
    )


class ResponsavelTarefa(Base):
    __tablename__ = "tarefas_responsaveis"
    __table_args__ = (UniqueConstraint("tarefa_id", "usuario_id", name="uq_tarefas_responsaveis"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tarefa: Mapped[Tarefa] = relationship(back_populates="responsaveis")


class EventoTarefa(Base):
    """Evento da linha do tempo (nunca é editado; remoção só lógica, pelo SuperRoot, com motivo)."""
    __tablename__ = "tarefas_eventos"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_EVENTO_TAREFA)})", name="ck_tarefas_eventos_tipo"),
        Index("ix_tarefas_eventos_tarefa_em", "tarefa_id", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(15))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(300), default="")
    texto: Mapped[str] = mapped_column(Text, default="")
    # De/para, prazos, justificativa, destinatário da transferência etc.
    dados: Mapped[dict] = mapped_column(JSON, default=dict)
    removido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removido_por_nome: Mapped[str | None] = mapped_column(String(200))
    motivo_remocao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    anexos: Mapped[list["AnexoEventoTarefa"]] = relationship(back_populates="evento", cascade="all, delete-orphan", lazy="selectin")


class AnexoEventoTarefa(Base):
    __tablename__ = "tarefas_eventos_anexos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_eventos.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="CASCADE"))
    evento: Mapped[EventoTarefa] = relationship(back_populates="anexos")
    anexo: Mapped["Anexo"] = relationship(lazy="joined")  # noqa: F821


class MarcadorTarefa(Base):
    """Etiqueta por equipe (criada pela liderança) ou global (sem equipe)."""
    __tablename__ = "tarefas_marcadores"
    __table_args__ = (UniqueConstraint("equipe_id", "nome", name="uq_tarefas_marcadores_equipe_nome"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    # Cor da paleta de 12 cores (índice 0 a 11; ver `services/tarefas/paleta.py`); `cor` guarda o hexadecimal da borda por compatibilidade
    cor_indice: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    cor: Mapped[str] = mapped_column(String(7), default="#5364ce")


class VinculoMarcadorTarefa(Base):
    __tablename__ = "tarefas_marcadores_vinculos"

    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), primary_key=True)
    marcador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_marcadores.id", ondelete="CASCADE"), primary_key=True)


class ItemChecklistTarefa(Base):
    __tablename__ = "tarefas_checklist"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    texto: Mapped[str] = mapped_column(String(300))
    posicao: Mapped[int] = mapped_column(Integer, default=0)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    tarefa: Mapped[Tarefa] = relationship(back_populates="checklist")


class RecorrenciaTarefa(Base):
    """Série de tarefas recorrentes: o modelo da tarefa e a regra de repetição (pelo calendário).

    `proxima_data` é a data do **prazo** da próxima ocorrência; ela nasce `antecedencia_dias` antes, na rotina das 07:00.
    A primeira ocorrência é a tarefa criada junto com a série (`inicio` = data do prazo dela).
    """
    __tablename__ = "tarefas_recorrencias"
    __table_args__ = (
        CheckConstraint(f"frequencia IN ({_lista(FREQUENCIAS_RECORRENCIA)})", name="ck_tarefas_recorrencias_frequencia"),
        CheckConstraint("intervalo >= 1", name="ck_tarefas_recorrencias_intervalo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="SET NULL"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Modelo da tarefa
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text, default="")
    prioridade: Mapped[str] = mapped_column(String(10), default="normal")
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    # Regra
    frequencia: Mapped[str] = mapped_column(String(10))
    intervalo: Mapped[int] = mapped_column(Integer, default=1)
    dias_semana: Mapped[list] = mapped_column(JSON, default=list)
    somente_dias_uteis: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    antecedencia_dias: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    hora_prazo: Mapped[time] = mapped_column(Time)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    max_ocorrencias: Mapped[int | None] = mapped_column(Integer)
    # Controle
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    proxima_data: Mapped[date | None] = mapped_column(Date)
    geradas: Mapped[int] = mapped_column(Integer, default=1)
    ultimo_erro: Mapped[str] = mapped_column(Text, default="", server_default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    responsaveis: Mapped[list["ResponsavelRecorrencia"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    marcadores: Mapped[list["MarcadorTarefa"]] = relationship(secondary="tarefas_recorrencias_marcadores", lazy="selectin")
    equipe: Mapped[EquipeTarefas | None] = relationship(lazy="joined")


class ResponsavelRecorrencia(Base):
    __tablename__ = "tarefas_recorrencias_responsaveis"

    recorrencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_recorrencias.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    # Ordem de escolha: o primeiro é o responsável principal
    posicao: Mapped[int] = mapped_column(Integer, default=0)


class VinculoMarcadorRecorrencia(Base):
    __tablename__ = "tarefas_recorrencias_marcadores"

    recorrencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_recorrencias.id", ondelete="CASCADE"), primary_key=True)
    marcador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_marcadores.id", ondelete="CASCADE"), primary_key=True)


class DependenciaTarefa(Base):
    """A tarefa `tarefa_id` fica bloqueada (não inicia) enquanto `bloqueada_por_id` não for concluída."""
    __tablename__ = "tarefas_dependencias"
    __table_args__ = (CheckConstraint("tarefa_id <> bloqueada_por_id", name="ck_tarefas_dependencias_propria"),)

    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), primary_key=True)
    bloqueada_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), primary_key=True, index=True)


class EstagioTarefa(Base):
    """Coluna do quadro da equipe. A `categoria` é uma das 4 situações do pipeline: as regras de validação, permissões e relatórios seguem a categoria."""
    __tablename__ = "tarefas_estagios"
    __table_args__ = (
        UniqueConstraint("equipe_id", "nome", name="uq_tarefas_estagios_equipe_nome"),
        CheckConstraint(f"categoria IN ({_lista(STATUS_TAREFA)})", name="ck_tarefas_estagios_categoria"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    posicao: Mapped[int] = mapped_column(Integer, default=0)
    categoria: Mapped[str] = mapped_column(String(15))
    cor_indice: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AtividadeTarefa(Base):
    """Atividade agendada numa tarefa para uma pessoa (ligar, enviar documento, revisar…), com prazo em data."""
    __tablename__ = "tarefas_atividades"
    __table_args__ = (CheckConstraint(f"tipo IN ({_lista(TIPOS_ATIVIDADE)})", name="ck_tarefas_atividades_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="fazer")
    resumo: Mapped[str] = mapped_column(String(200))
    nota: Mapped[str] = mapped_column(Text, default="")
    prazo: Mapped[date] = mapped_column(Date)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    criada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    feedback: Mapped[str] = mapped_column(Text, default="")

    tarefa: Mapped[Tarefa] = relationship()


class SeguidorTarefa(Base):
    """Quem acompanha a tarefa sem ser responsável: recebe os avisos de comentário, prazo e andamento."""
    __tablename__ = "tarefas_seguidores"

    tarefa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)


class MarcoTarefa(Base):
    """Marco (milestone) da equipe com data-alvo; fica atingido quando todas as suas tarefas concluem (ou manualmente pela liderança)."""
    __tablename__ = "tarefas_marcos"
    __table_args__ = (UniqueConstraint("equipe_id", "nome", name="uq_tarefas_marcos_equipe_nome"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str] = mapped_column(Text, default="")
    data_alvo: Mapped[date] = mapped_column(Date)
    atingido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Atingido (ou reaberto) pela liderança: a conclusão das tarefas não muda mais o estado sozinha
    atingido_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class AtualizacaoStatusEquipe(Base):
    """Atualização periódica da liderança sobre a situação da equipe (no prazo, em risco…), com texto."""
    __tablename__ = "tarefas_atualizacoes_status"
    __table_args__ = (
        CheckConstraint(f"situacao IN ({_lista(SITUACOES_STATUS_EQUIPE)})", name="ck_tarefas_atualizacoes_situacao"),
        Index("ix_tarefas_atualizacoes_equipe_em", "equipe_id", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tarefas_equipes.id", ondelete="CASCADE"))
    situacao: Mapped[str] = mapped_column(String(15))
    texto: Mapped[str] = mapped_column(Text, default="")
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nome: Mapped[str] = mapped_column(String(200), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
