"""
===============================================================================
ARQUIVO: sla.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir a tabela da política de SLA (acordo de nível de serviço): quantos
dias úteis valem para responder e para resolver, por módulo e prioridade.

RESUMO TÉCNICO:
Um modelo SQLAlchemy, SlaPolitica (tabela sla_politicas), com unicidade do
par módulo + prioridade e restrições (CheckConstraint) que limitam o módulo
a "tarefas" ou "melhorias" e exigem resolução >= resposta >= 0.
MODULOS_SLA lista os módulos aceitos.

FINALIDADE DE NEGÓCIO:
Dar prazos claros para as demandas internas: nas Tarefas o prazo depende da
prioridade (baixa, normal, alta, crítica); nas Melhorias há uma regra só.
Com isso o sistema mostra o que está no prazo e o que atrasou.

CONTEXTO NO SISTEMA:
Lido pelos serviços de SLA, de Tarefas e de Melhorias para calcular prazos;
editado pela tela de política de SLA (schemas/sla.py). Os dias úteis
consideram os feriados cadastrados no RH (models/rh.py, Feriado).

===============================================================================
"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

# Módulos que têm política de SLA (SLA = acordo de nível de serviço, o prazo combinado
# para responder e resolver uma demanda). O CheckConstraint abaixo repete a lista no banco.
MODULOS_SLA = ("tarefas", "melhorias")


class SlaPolitica(Base):
    """Uma linha da política: `modulo` + `prioridade` (vazia em Melhorias, que tem uma regra só).

    Os prazos são contados em dias úteis a partir da criação do item (o cálculo fica em
    `services/sla/servico_sla.py`). `ativo = False` desliga a regra sem apagá-la.
    """

    __tablename__ = "sla_politicas"
    # Regras garantidas pelo próprio banco (mesmo se alguém gravar fora da API):
    # uma linha por módulo + prioridade, módulo válido e resolução nunca antes da resposta
    __table_args__ = (
        UniqueConstraint("modulo", "prioridade", name="uq_sla_politicas_modulo_prioridade"),
        CheckConstraint("modulo IN ('tarefas', 'melhorias')", name="ck_sla_politicas_modulo"),
        CheckConstraint("dias_uteis_resposta >= 0 AND dias_uteis_resolucao >= dias_uteis_resposta", name="ck_sla_politicas_dias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modulo: Mapped[str] = mapped_column(String(20))
    # `baixa`, `normal`, `alta` ou `critica` nas tarefas; texto vazio em Melhorias (a unicidade vale para o par)
    prioridade: Mapped[str] = mapped_column(String(10), default="", server_default="")
    dias_uteis_resposta: Mapped[int] = mapped_column(Integer)
    dias_uteis_resolucao: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
