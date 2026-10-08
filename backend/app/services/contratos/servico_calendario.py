# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir, num só calendário, os vencimentos e prazos dos contratos (vigência, reajuste, NF, certidões e tarefas).
"""Calendário de vencimentos dos contratos.

Agrega, numa lista de eventos por data, o que hoje está espalhado pelo painel, pela rotina de avisos e pelas tarefas: fim de vigência, vigência
máxima, reajuste, vencimento do pagamento da NF, prazo de 48 h da NF, validade dos documentos do checklist, medição atrasada, empenho
insuficiente e prazos das tarefas geradas pelos contratos. Nada é gravado: tudo é calculado na hora.

Leitura: contratos seguem a ACL do módulo (quem lê, vê todos; `meus` limita aos contratos em que a pessoa é criadora ou integrante vigente).
As tarefas dos contratos só aparecem para quem pode ver a tarefa (regra do módulo Tarefas), nunca pela regra aberta de Contratos.
"""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contratos import Contrato
from app.models.tarefas import Tarefa
from app.models.usuario import Usuario
from app.schemas.contratos.calendario import Calendario, EventoCalendario
from app.services.contratos import calculos
from app.services.contratos.servico_competencias import (
    anterior_ao_corte,
    compromissos,
    prazo_nota_fiscal,
    total_previsto_na_hora,
    vencimento_pagamento,
)
from app.services.contratos.servico_contratos import designacoes_vigentes, hoje, situacao
from app.services.contratos.servico_painel import DIAS_ATRASO, DIAS_VENCENDO, carregar_contratos
from app.services.contratos.servico_prorrogacao import meses_disponiveis
from app.services.tarefas import servico_tarefas

FUSO = ZoneInfo("America/Sao_Paulo")
ORIGEM_TAREFA = "contrato_competencia"
TIPOS = (
    "vigencia_fim", "vigencia_maxima", "reajuste", "pagamento_nf", "prazo_nf_48h", "validade_documento", "medicao_atrasada", "empenho_insuficiente",
    "tarefa_contrato",
)
# Documento que vence em até 15 dias é risco alto; em até 30, médio
DIAS_DOCUMENTO_ALTO = 15
DIAS_DOCUMENTO_MEDIO = 30


def _por_dias(dias: int, alto: int = 30, medio: int = 60) -> str:
    """Severidade pela folga em dias (vencido ou dentro do limite alto = alta)."""
    return "alta" if dias <= alto else "media" if dias <= medio else "info"


def _local(momento: datetime) -> datetime:
    return momento.astimezone(FUSO)


def _eventos_do_contrato(contrato: Contrato, referencia: date) -> list[EventoCalendario]:
    """Eventos de um contrato (sem as tarefas, que dependem do usuário)."""
    eventos: list[EventoCalendario] = []

    def novo(data: date, tipo: str, rotulo: str, rota: str, severidade: str, competencia=None, hora: time | None = None, valor=None) -> None:
        eventos.append(EventoCalendario(
            data=data, hora=hora, tipo=tipo, contrato_id=contrato.id, contrato_numero=contrato.numero, contrato_apelido=contrato.apelido, rotulo=rotulo,
            rota=rota, severidade=severidade, competencia_id=competencia.id if competencia is not None else None, valor=valor,
        ))

    estado = situacao(contrato)
    base = f"/contratos/{contrato.id}"
    # Fim da vigência atual e vigência máxima
    novo(contrato.data_fim, "vigencia_fim", "Fim da vigência", f"{base}/prorrogacao" if estado != "encerrado" else base, _por_dias((contrato.data_fim - referencia).days))
    if contrato.vigencia_maxima_meses and meses_disponiveis(contrato) <= 0:
        limite = calculos.data_limite_maxima(contrato.data_inicio, contrato.vigencia_maxima_meses)
        novo(limite, "vigencia_maxima", "Vigência máxima: planejar nova contratação", base, "alta")
    # Reajuste: cada mês de reajuste, a partir do primeiro aniversário, que ainda não tem reajuste aberto
    aniversario = calculos.primeiro_dia(calculos.somar_meses(contrato.data_inicio, 12))
    if contrato.mes_reajuste:
        for ano in range(aniversario.year, max(contrato.data_fim.year, referencia.year) + 1):
            mes = date(ano, contrato.mes_reajuste, 1)
            if mes >= aniversario and mes <= contrato.data_fim and not any(r.situacao != "cancelado" and r.mes_referencia >= mes for r in contrato.reajustes):
                novo(mes, "reajuste", f"Reajuste de {mes:%m/%Y}", f"{base}/reajuste", "media" if mes < referencia else "info")
    abertas = [c for c in contrato.competencias if c.etapa_atual != "concluida" and not anterior_ao_corte(c)]
    for competencia in abertas:
        rota = f"{base}/execucao/{competencia.identificador}"
        rotulo = competencia.numero_competencia
        vencimento = vencimento_pagamento(competencia)
        if vencimento is not None:
            novo(vencimento, "pagamento_nf", f"Pagamento da competência {rotulo}", rota,
                 "alta" if vencimento < referencia else "media" if (vencimento - referencia).days <= DIAS_VENCENDO else "info", competencia)
        limite = prazo_nota_fiscal(competencia) if competencia.etapa_atual == "nota_fiscal" else None
        if limite is not None:
            momento = _local(limite)
            novo(momento.date(), "prazo_nf_48h", f"Prazo de 48 h da nota fiscal ({rotulo})", rota, "alta" if momento.date() < referencia else "media", competencia, momento.time().replace(microsecond=0))
        if competencia.tipo == "regular" and competencia.medicao_concluida_em is None and (referencia - competencia.periodo_fim).days > DIAS_ATRASO:
            atraso = (referencia - competencia.periodo_fim).days
            novo(competencia.periodo_fim + timedelta(days=DIAS_ATRASO), "medicao_atrasada", f"Medição da competência {rotulo} atrasada", rota,
                 "alta" if atraso > 2 * DIAS_ATRASO else "media", competencia)
    # Validade dos documentos do checklist: o que mais demora a vencer de cada documento
    validades: dict[str, tuple] = {}
    for competencia in contrato.competencias:
        for documento in competencia.documentos:
            if documento.com_validade and documento.anexo_id and documento.validade_ate:
                atual = validades.get(documento.nome.strip().lower())
                if atual is None or documento.validade_ate > atual[0].validade_ate:
                    validades[documento.nome.strip().lower()] = (documento, competencia)
    for documento, competencia in validades.values():
        dias = (documento.validade_ate - referencia).days
        novo(documento.validade_ate, "validade_documento", f"Validade: {documento.nome}", f"{base}/execucao/{competencia.identificador}",
             _por_dias(dias, DIAS_DOCUMENTO_ALTO, DIAS_DOCUMENTO_MEDIO), competencia)
    # Empenho: o saldo livre não cobre a próxima competência a medir
    a_medir = sorted((c for c in contrato.competencias if c.medicao_concluida_em is None and c.tipo == "regular" and not anterior_ao_corte(c)), key=lambda c: c.periodo_inicio)
    if a_medir and estado not in ("encerrado", "suspenso"):
        reservado = compromissos(contrato)
        livre = sum((n.saldo - reservado.get(n.id, 0) for n in contrato.notas_empenho), 0)
        necessario = total_previsto_na_hora(contrato, a_medir[0])
        if livre < necessario:
            novo(a_medir[0].periodo_fim, "empenho_insuficiente", f"Saldo das NEs não cobre a competência {a_medir[0].numero_competencia}", base, "alta", a_medir[0], valor=necessario - livre)
    return eventos


def _eventos_de_tarefas(sessao: Session, usuario: Usuario, contratos: dict[uuid.UUID, Contrato], de: date, ate: date, referencia: date) -> list[EventoCalendario]:
    """Prazos das tarefas geradas pelos contratos, só das que o usuário pode ver."""
    competencias = {c.id: (contrato, c) for contrato in contratos.values() for c in contrato.competencias}
    if not competencias:
        return []
    inicio = datetime.combine(de, time.min, tzinfo=FUSO)
    fim = datetime.combine(ate + timedelta(days=1), time.min, tzinfo=FUSO)
    tarefas = sessao.scalars(select(Tarefa).where(
        Tarefa.origem_tipo == ORIGEM_TAREFA, Tarefa.origem_id.in_(competencias), Tarefa.status != "concluida", Tarefa.prazo >= inicio, Tarefa.prazo < fim,
    ))
    eventos = []
    for tarefa in tarefas:
        if not servico_tarefas.pode_ver(sessao, usuario, tarefa):
            continue
        contrato, competencia = competencias[tarefa.origem_id]
        momento = _local(tarefa.prazo)
        dias = (momento.date() - referencia).days
        eventos.append(EventoCalendario(
            data=momento.date(), hora=momento.time().replace(microsecond=0), tipo="tarefa_contrato", contrato_id=contrato.id, contrato_numero=contrato.numero,
            contrato_apelido=contrato.apelido, rotulo=f"#{tarefa.numero} {tarefa.titulo}", rota=f"/tarefas/{tarefa.numero}",
            severidade="alta" if dias < 0 else "media" if dias <= 1 else "info", competencia_id=competencia.id,
        ))
    return eventos


def montar_calendario(
    sessao: Session, usuario: Usuario, de: date, ate: date, meus: bool = False, contrato_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None, tipos: set[str] | None = None,
) -> Calendario:
    """Eventos de `de` a `ate` (inclusive), dos contratos que a pessoa lê, em ordem de data e gravidade."""
    referencia = hoje()
    contratos = [c for c in carregar_contratos(sessao)
                 if (contrato_id is None or c.id == contrato_id) and (empresa_id is None or c.empresa_id == empresa_id)
                 and situacao(c) not in ("encerrado", "suspenso")]
    if meus:
        contratos = [c for c in contratos if c.criador_id == usuario.id or any(d.usuario_id == usuario.id for d in designacoes_vigentes(c))]
    eventos: list[EventoCalendario] = []
    for contrato in contratos:
        eventos += _eventos_do_contrato(contrato, referencia)
    if not tipos or "tarefa_contrato" in tipos:
        eventos += _eventos_de_tarefas(sessao, usuario, {c.id: c for c in contratos}, de, ate, referencia)
    ordem = {"alta": 0, "media": 1, "info": 2}
    filtrados = [e for e in eventos if de <= e.data <= ate and (not tipos or e.tipo in tipos)]
    filtrados.sort(key=lambda e: (e.data, e.hora or time.min, ordem[e.severidade], e.contrato_numero))
    return Calendario(de=de, ate=ate, eventos=filtrados)
