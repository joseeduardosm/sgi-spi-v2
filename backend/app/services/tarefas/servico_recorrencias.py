# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras das tarefas recorrentes: cálculo das datas, geração diária das ocorrências e gestão das séries.
"""Tarefas recorrentes (pelo calendário).

- A **primeira ocorrência** é a tarefa criada junto com a série; o prazo dela define a data inicial e o horário de todas.
- As seguintes seguem a regra (diária, semanal, mensal ou anual) sobre as **datas de prazo** e nascem `antecedencia_dias` antes
  dessa data, na rotina das 07:00 (`gerar_ocorrencias`), mesmo que a anterior ainda esteja aberta.
- Mensal preserva o dia do mês e, nos meses mais curtos, usa o último dia; anual segue o mesmo princípio para 29/02.
- Com `somente_dias_uteis`, a data que cai em fim de semana ou feriado (`rh_feriados`) vai para o próximo dia útil.
- Depois de uma parada do sistema, só a ocorrência **mais recente** vencida é criada; as anteriores são puladas (contam no limite).
- Editar a série vale só para as próximas ocorrências; pausar, retomar e excluir não mexem nas tarefas já criadas.
"""

import calendar
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from itertools import count
from typing import BinaryIO
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo
from app.models.rh import Feriado
from app.models.tarefas import FREQUENCIAS_RECORRENCIA, MarcadorTarefa, RecorrenciaTarefa, ResponsavelRecorrencia, Tarefa
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.servico_auditoria import auditar
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import DadosTarefa, ErroTarefa

log = logging.getLogger("sgi_spi.tarefas.recorrencia")
FUSO = ZoneInfo("America/Sao_Paulo")
LIMITE_OCORRENCIAS = 366
DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
ROTULOS_FREQUENCIA = {"diaria": "dia", "semanal": "semana", "mensal": "mês", "anual": "ano"}


@dataclass
class RegraRecorrencia:
    """Regra de repetição (a mesma do corpo da API)."""
    frequencia: str
    intervalo: int = 1
    dias_semana: tuple[int, ...] = ()
    somente_dias_uteis: bool = False
    antecedencia_dias: int = 0
    fim: date | None = None
    max_ocorrencias: int | None = None


def regra_da_serie(rec: RecorrenciaTarefa) -> RegraRecorrencia:
    return RegraRecorrencia(rec.frequencia, rec.intervalo, tuple(rec.dias_semana or ()), rec.somente_dias_uteis, rec.antecedencia_dias, rec.fim, rec.max_ocorrencias)


def validar_regra(regra: RegraRecorrencia, inicio: date) -> None:
    if regra.frequencia not in FREQUENCIAS_RECORRENCIA:
        raise ErroTarefa("Frequência de recorrência inválida.")
    if regra.intervalo < 1 or regra.intervalo > 365:
        raise ErroTarefa("O intervalo da recorrência deve ficar entre 1 e 365.")
    if regra.frequencia == "semanal" and (not regra.dias_semana or any(d not in range(7) for d in regra.dias_semana)):
        raise ErroTarefa("Informe os dias da semana da recorrência semanal.")
    if regra.fim is not None and regra.fim < inicio:
        raise ErroTarefa("A data final da recorrência não pode ser anterior à primeira tarefa.")
    if regra.max_ocorrencias is not None and not 1 <= regra.max_ocorrencias <= LIMITE_OCORRENCIAS:
        raise ErroTarefa(f"O número de ocorrências deve ficar entre 1 e {LIMITE_OCORRENCIAS}.")
    if not 0 <= regra.antecedencia_dias <= 60:
        raise ErroTarefa("A antecedência deve ficar entre 0 e 60 dias.")


# --- Datas --------------------------------------------------------------------------------------------------------------------------

def _datas_base(inicio: date, regra: RegraRecorrencia) -> Iterator[date]:
    """Datas da regra, em ordem, a partir da inicial (inclusive), sem ajuste de dia útil."""
    if regra.frequencia == "diaria":
        for k in count(0):
            yield inicio + timedelta(days=k * regra.intervalo)
    elif regra.frequencia == "semanal":
        dias = sorted(set(regra.dias_semana)) or [inicio.weekday()]
        segunda = inicio - timedelta(days=inicio.weekday())
        for semana in count(0, regra.intervalo):
            for dia in dias:
                data = segunda + timedelta(weeks=semana, days=dia)
                if data >= inicio:
                    yield data
    elif regra.frequencia == "mensal":
        for k in count(0, regra.intervalo):
            mes = inicio.month - 1 + k
            ano, mes = inicio.year + mes // 12, mes % 12 + 1
            yield date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))
    else:
        for k in count(0, regra.intervalo):
            ano = inicio.year + k
            yield date(ano, inicio.month, min(inicio.day, calendar.monthrange(ano, inicio.month)[1]))


def _dia_util(data: date, feriados: set[date]) -> date:
    while data.weekday() >= 5 or data in feriados:
        data += timedelta(days=1)
    return data


def feriados_cadastrados(sessao: Session) -> set[date]:
    return set(sessao.scalars(select(Feriado.data)))


def datas(inicio: date, regra: RegraRecorrencia, feriados: set[date]) -> Iterator[date]:
    """Datas de prazo da série, em ordem estritamente crescente (a primeira é `inicio`), já com o ajuste de dia útil, respeitando `fim`."""
    anterior: date | None = None
    for base in _datas_base(inicio, regra):
        data = _dia_util(base, feriados) if regra.somente_dias_uteis else base
        if anterior is not None and data <= anterior:
            continue
        if regra.fim is not None and data > regra.fim:
            return
        anterior = data
        yield data


def proxima_data(inicio: date, regra: RegraRecorrencia, depois: date, feriados: set[date]) -> date | None:
    """Primeira data da série estritamente depois de `depois` (None se a série acabou)."""
    for data in datas(inicio, regra, feriados):
        if data > depois:
            return data
    return None


def proximas(inicio: date, regra: RegraRecorrencia, feriados: set[date], quantidade: int = 3) -> list[date]:
    """As próximas datas depois da primeira (para a prévia da tela), respeitando o limite de ocorrências."""
    resultado: list[date] = []
    for n, data in enumerate(datas(inicio, regra, feriados), start=1):
        if n == 1:
            continue
        if regra.max_ocorrencias is not None and n > regra.max_ocorrencias:
            break
        resultado.append(data)
        if len(resultado) >= quantidade:
            break
    return resultado


def descrever(regra: RegraRecorrencia, inicio: date) -> str:
    """Texto legível da regra, ex.: "A cada 2 semanas, na segunda-feira e na quinta-feira, até 31/12/2026"."""
    n = regra.intervalo
    if regra.frequencia == "diaria":
        base = "Todo dia" if n == 1 else f"A cada {n} dias"
    elif regra.frequencia == "semanal":
        dias = " e ".join(DIAS_SEMANA[d] for d in sorted(set(regra.dias_semana)))
        base = ("Toda semana" if n == 1 else f"A cada {n} semanas") + f", {dias}"
    elif regra.frequencia == "mensal":
        base = (f"Todo mês" if n == 1 else f"A cada {n} meses") + f", no dia {inicio.day}"
    else:
        base = ("Todo ano" if n == 1 else f"A cada {n} anos") + f", em {inicio:%d/%m}"
    partes = [base]
    if regra.somente_dias_uteis:
        partes.append("só em dias úteis")
    if regra.fim is not None:
        partes.append(f"até {regra.fim:%d/%m/%Y}")
    if regra.max_ocorrencias is not None:
        partes.append(f"{regra.max_ocorrencias} vez(es) no total")
    if regra.antecedencia_dias:
        partes.append(f"criada {regra.antecedencia_dias} dia(s) antes do prazo")
    return ", ".join(partes)


def _limitar(rec: RecorrenciaTarefa, proxima: date | None) -> date | None:
    """Encerra a série (sem próxima data) ao atingir o número máximo de ocorrências."""
    if rec.max_ocorrencias is not None and rec.geradas >= rec.max_ocorrencias:
        return None
    return proxima


def _prazo(data: date, hora: time) -> datetime:
    return datetime.combine(data, hora, tzinfo=FUSO)


# --- Criação ------------------------------------------------------------------------------------------------------------------------

def previa(prazo: datetime, regra: RegraRecorrencia, sessao: Session) -> tuple[str, list[date]]:
    """Resumo e próximas datas da regra para o prazo escolhido (tela de nova tarefa)."""
    inicio = prazo.astimezone(FUSO).date()
    validar_regra(regra, inicio)
    return descrever(regra, inicio), proximas(inicio, regra, feriados_cadastrados(sessao))


def criar_com_serie(sessao: Session, autor: Usuario, dados: DadosTarefa, regra: RegraRecorrencia, arquivos: list[tuple[str, BinaryIO]] | None = None) -> Tarefa:
    """Cria a série e a primeira tarefa (a própria, com o prazo informado) na mesma transação."""
    prazo_local = dados.prazo.astimezone(FUSO)
    inicio = prazo_local.date()
    validar_regra(regra, inicio)
    feriados = feriados_cadastrados(sessao)
    responsaveis = dados.responsaveis_ids or (autor.id,)
    rec = RecorrenciaTarefa(
        equipe_id=dados.equipe_id, criado_por_id=autor.id, titulo=dados.titulo, descricao=dados.descricao, prioridade=dados.prioridade,
        checklist=list(dados.checklist), frequencia=regra.frequencia, intervalo=regra.intervalo, dias_semana=sorted(set(regra.dias_semana)),
        somente_dias_uteis=regra.somente_dias_uteis, antecedencia_dias=regra.antecedencia_dias, hora_prazo=prazo_local.time().replace(tzinfo=None),
        inicio=inicio, fim=regra.fim, max_ocorrencias=regra.max_ocorrencias, geradas=1,
    )
    rec.responsaveis = [ResponsavelRecorrencia(usuario_id=i, posicao=n) for n, i in enumerate(dict.fromkeys(responsaveis))]
    equipe = sessao.get(servico.EquipeTarefas, dados.equipe_id) if dados.equipe_id else None
    rec.marcadores = servico._marcadores(sessao, equipe, dados.marcadores_ids)
    rec.proxima_data = _limitar(rec, proxima_data(inicio, regra, inicio, feriados))
    sessao.add(rec)
    sessao.flush()
    try:
        tarefa = servico.criar(sessao, autor, replace(dados, recorrencia_id=rec.id, ocorrencia_em=inicio), arquivos)
    except Exception:
        sessao.rollback()
        raise
    auditar(sessao, autor.login, "tarefas.recorrencia.criar", rec.titulo, descrever(regra, inicio), autor_id=autor.id, alvo_tipo="tarefa-recorrencia", alvo_id=rec.id)
    sessao.commit()
    return tarefa


# --- Geração diária -----------------------------------------------------------------------------------------------------------------

def _gerar_da_serie(sessao: Session, rec: RecorrenciaTarefa, dia: date, feriados: set[date]) -> tuple[int, int]:
    """Cria a ocorrência mais recente vencida da série. Devolve (criadas, puladas)."""
    regra = regra_da_serie(rec)
    vencidas: list[date] = []
    proxima = rec.proxima_data
    consumidas = rec.geradas
    while proxima is not None and proxima - timedelta(days=rec.antecedencia_dias) <= dia and len(vencidas) < LIMITE_OCORRENCIAS:
        vencidas.append(proxima)
        consumidas += 1
        proxima = None if (rec.max_ocorrencias is not None and consumidas >= rec.max_ocorrencias) else proxima_data(rec.inicio, regra, vencidas[-1], feriados)
    if not vencidas:
        return 0, 0
    alvo = vencidas[-1]
    autor = sessao.get(Usuario, rec.criado_por_id) if rec.criado_por_id else None
    if autor is None or not autor.ativo:
        raise ErroTarefa("Quem criou a recorrência não está mais ativo(a).")
    ordenados = [r.usuario_id for r in sorted(rec.responsaveis, key=lambda r: r.posicao)]
    servico.criar(sessao, autor, DadosTarefa(
        titulo=rec.titulo, descricao=rec.descricao, prazo=_prazo(alvo, rec.hora_prazo), prioridade=rec.prioridade, equipe_id=rec.equipe_id,
        responsaveis_ids=tuple(ordenados), marcadores_ids=tuple(m.id for m in rec.marcadores), recorrencia_id=rec.id, ocorrencia_em=alvo,
        automatica=True, checklist=tuple(rec.checklist or ()),
    ))
    rec = sessao.get(RecorrenciaTarefa, rec.id)
    rec.geradas, rec.proxima_data, rec.ultimo_erro = consumidas, proxima, ""
    sessao.commit()
    return 1, len(vencidas) - 1


def gerar_ocorrencias(sessao: Session, dia: date | None = None) -> dict[str, int]:
    """Rotina das 07:00: cria as ocorrências cuja data de criação chegou. Idempotente (a unicidade da série impede repetição)."""
    dia = dia or hoje_sao_paulo()
    feriados = feriados_cadastrados(sessao)
    resultado = {"criadas": 0, "puladas": 0, "pausadas_por_erro": 0}
    ids = list(sessao.scalars(select(RecorrenciaTarefa.id).where(RecorrenciaTarefa.ativa.is_(True), RecorrenciaTarefa.proxima_data.is_not(None))))
    for rec_id in ids:
        rec = sessao.get(RecorrenciaTarefa, rec_id)
        try:
            criadas, puladas = _gerar_da_serie(sessao, rec, dia, feriados)
        except ErroTarefa as erro:
            sessao.rollback()
            rec = sessao.get(RecorrenciaTarefa, rec_id)
            rec.ativa, rec.ultimo_erro = False, str(erro)
            if rec.criado_por_id:
                servico_mensagens.notificar(
                    sessao, [rec.criado_por_id], f"Recorrência pausada: {rec.titulo}",
                    f"Não foi possível gerar a próxima tarefa de \"{rec.titulo}\": {erro} A recorrência foi pausada; ajuste-a e retome.",
                    chave=f"tarefa-recorrencia-erro:{rec.id}:{dia}", categoria="pendencia", prioridade="alta", link="/tarefas", email=True,
                )
            sessao.commit()
            resultado["pausadas_por_erro"] += 1
            log.warning("Recorrência %s pausada: %s", rec_id, erro)
            continue
        resultado["criadas"] += criadas
        resultado["puladas"] += puladas
    return resultado


# --- Gestão da série ----------------------------------------------------------------------------------------------------------------

def pode_gerir(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> bool:
    """Quem criou a série, a liderança da equipe e o SuperRoot."""
    return usuario.superusuario or usuario.id == rec.criado_por_id or (rec.equipe is not None and usuario.id in servico.lideranca(sessao, rec.equipe))


def pode_ver(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> bool:
    if pode_gerir(sessao, usuario, rec):
        return True
    return rec.equipe is not None and usuario.id in servico.membros(rec.equipe)


def obter(sessao: Session, usuario: Usuario, recorrencia_id: uuid.UUID, gerir: bool = False) -> RecorrenciaTarefa:
    rec = sessao.get(RecorrenciaTarefa, recorrencia_id)
    if rec is None or not pode_ver(sessao, usuario, rec):
        raise ErroTarefa("Recorrência não encontrada.", 404, "nao_encontrado")
    if gerir and not pode_gerir(sessao, usuario, rec):
        raise ErroTarefa("Só quem criou a recorrência, a liderança da equipe ou um SuperRoot altera a série.", 403, "sem_permissao")
    return rec


def listar(sessao: Session, usuario: Usuario, equipe_id: uuid.UUID | None) -> list[RecorrenciaTarefa]:
    """Séries da equipe (para quem a vê) ou as pessoais do usuário (sem `equipe_id`)."""
    consulta = select(RecorrenciaTarefa).order_by(RecorrenciaTarefa.titulo)
    consulta = consulta.where(RecorrenciaTarefa.equipe_id == equipe_id) if equipe_id else consulta.where(
        RecorrenciaTarefa.equipe_id.is_(None), RecorrenciaTarefa.criado_por_id == usuario.id)
    return [r for r in sessao.scalars(consulta) if pode_ver(sessao, usuario, r)]


def ultima_ocorrencia(sessao: Session, rec: RecorrenciaTarefa) -> date:
    return sessao.scalar(select(func.max(Tarefa.ocorrencia_em)).where(Tarefa.recorrencia_id == rec.id)) or rec.inicio


def _reprogramar(sessao: Session, rec: RecorrenciaTarefa, hoje: date) -> None:
    """Próxima data = primeira da regra (atual) depois da última ocorrência criada e a partir de hoje (as vencidas durante a pausa não voltam)."""
    minimo = max(ultima_ocorrencia(sessao, rec), hoje - timedelta(days=1))
    rec.proxima_data = _limitar(rec, proxima_data(rec.inicio, regra_da_serie(rec), minimo, feriados_cadastrados(sessao)))


def atualizar(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa, *, titulo: str, descricao: str, prioridade: str, checklist: list[str],
              responsaveis_ids: list[int], marcadores_ids: list[uuid.UUID], regra: RegraRecorrencia, hora_prazo: time | None = None) -> RecorrenciaTarefa:
    """Altera o modelo e a regra; vale só para as próximas ocorrências."""
    validar_regra(regra, rec.inicio)
    equipe = rec.equipe
    pessoas = set(responsaveis_ids)
    if not pessoas:
        raise ErroTarefa("A recorrência precisa de ao menos um responsável.")
    servico._conferir_pessoas(sessao, usuario, equipe, pessoas)
    rec.titulo, rec.descricao, rec.prioridade, rec.checklist = titulo, descricao, prioridade, list(checklist)
    rec.frequencia, rec.intervalo, rec.dias_semana = regra.frequencia, regra.intervalo, sorted(set(regra.dias_semana))
    rec.somente_dias_uteis, rec.antecedencia_dias, rec.fim, rec.max_ocorrencias = regra.somente_dias_uteis, regra.antecedencia_dias, regra.fim, regra.max_ocorrencias
    if hora_prazo is not None:
        rec.hora_prazo = hora_prazo
    rec.responsaveis = [ResponsavelRecorrencia(usuario_id=i, posicao=n) for n, i in enumerate(dict.fromkeys(responsaveis_ids))]
    rec.marcadores = servico._marcadores(sessao, equipe, tuple(marcadores_ids))
    if rec.ativa:
        _reprogramar(sessao, rec, hoje_sao_paulo())
    auditar(sessao, usuario.login, "tarefas.recorrencia.editar", rec.titulo, descrever(regra, rec.inicio), autor_id=usuario.id, alvo_tipo="tarefa-recorrencia", alvo_id=rec.id)
    sessao.commit()
    return rec


def pausar(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> RecorrenciaTarefa:
    rec.ativa = False
    auditar(sessao, usuario.login, "tarefas.recorrencia.pausar", rec.titulo, autor_id=usuario.id, alvo_tipo="tarefa-recorrencia", alvo_id=rec.id)
    sessao.commit()
    return rec


def retomar(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> RecorrenciaTarefa:
    rec.ativa, rec.ultimo_erro = True, ""
    _reprogramar(sessao, rec, hoje_sao_paulo())
    auditar(sessao, usuario.login, "tarefas.recorrencia.retomar", rec.titulo, autor_id=usuario.id, alvo_tipo="tarefa-recorrencia", alvo_id=rec.id)
    sessao.commit()
    return rec


def excluir(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> None:
    """Remove a série; as tarefas já criadas continuam, sem vínculo."""
    auditar(sessao, usuario.login, "tarefas.recorrencia.excluir", rec.titulo, autor_id=usuario.id, alvo_tipo="tarefa-recorrencia", alvo_id=rec.id)
    sessao.delete(rec)
    sessao.commit()
