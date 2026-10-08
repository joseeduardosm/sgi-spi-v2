# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da Reserva de Espaços: conflito, recorrência, análise dos fiscais, cancelamento e avisos.
"""Reserva de Espaços.

- **Conflito:** só reservas DEFERIDAS bloqueiam (mesmo espaço, mesma data, horários que se sobrepõem); pendentes geram apenas aviso.
- **Série:** uma recorrência (diária, semanal, quinzenal, mensal) cria várias reservas com o mesmo `serie_id`; deferir e indeferir
  valem para a série inteira; cancelar pode ser uma ocorrência, a série ou um período.
- **Papéis:** fiscal (tabela `reserva_espacos_fiscais`) ou SuperRoot analisa, cadastra espaços e cria reserva predefinida; o solicitante
  vê e altera só o que criou, enquanto aguarda aprovação.
- **Avisos:** pela mensageria (`servico_mensagens.notificar`, com e-mail), sempre sem commit (gravam junto da operação).
"""

import calendar
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FUSO_SAO_PAULO, agora_utc, hoje_sao_paulo
from app.models.reserva_espacos import (
    STATUS_AGUARDANDO, STATUS_CANCELADA, STATUS_DEFERIDA, STATUS_INDEFERIDA, ConfiguracaoReservaEspacos, EspacoReservavel,
    EventoReservaEspaco, FiscalReservaEspacos, ReservaEspaco,
)
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.servico_auditoria import auditar

RECORRENCIAS = ("nenhuma", "diaria", "semanal", "quinzenal", "mensal")
LIMITE_OCORRENCIAS = 120
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


class ErroReserva(Exception):
    """Regra violada; `status` é o código HTTP e `codigo` o código do erro da API."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


@dataclass
class DadosReserva:
    espaco_id: int
    data: date
    hora_inicio: time
    hora_fim: time
    titulo: str
    responsavel_id: int | None = None
    responsavel_nome: str = ""
    observacoes: str = ""
    participantes: int | None = None
    recorrencia: str = "nenhuma"
    recorrencia_ate: date | None = None


@dataclass
class ResultadoSolicitacao:
    reservas: list[ReservaEspaco]
    avisos: list[str] = field(default_factory=list)


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def formatar_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def formatar_hora(h: time) -> str:
    return h.strftime("%H:%M")


def configuracao(sessao: Session) -> ConfiguracaoReservaEspacos:
    """Linha única de configuração (criada com os padrões se não existir)."""
    cfg = sessao.get(ConfiguracaoReservaEspacos, 1)
    if cfg is None:
        cfg = ConfiguracaoReservaEspacos(id=1, hora_abertura=time(7, 0), hora_fechamento=time(19, 0), antecedencia_minima_horas=0, duracao_maxima_horas=0)
        sessao.add(cfg)
        sessao.flush()
    return cfg


# --- Papéis -------------------------------------------------------------------------------------------------------------------------

def ids_fiscais(sessao: Session) -> list[int]:
    return list(sessao.scalars(select(FiscalReservaEspacos.usuario_id)))


def eh_fiscal(sessao: Session, usuario: Usuario) -> bool:
    if usuario.superusuario:
        return True
    return sessao.get(FiscalReservaEspacos, usuario.id) is not None


def exigir_fiscal(sessao: Session, usuario: Usuario) -> None:
    if not eh_fiscal(sessao, usuario):
        raise ErroReserva("Somente os fiscais da reserva de espaços realizam esta operação.", 403, "acesso_negado")


def pode_ver(sessao: Session, usuario: Usuario, reserva: ReservaEspaco) -> bool:
    return eh_fiscal(sessao, usuario) or usuario.id in (reserva.solicitante_id, reserva.responsavel_id)


def _destinatarios_fiscais(sessao: Session) -> list[int]:
    """Fiscais ativos; sem nenhum, os SuperRoots (a solicitação nunca fica sem destinatário)."""
    ids = ids_fiscais(sessao)
    if ids:
        return ids
    return list(sessao.scalars(select(Usuario.id).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True))))


def definir_fiscais(sessao: Session, autor: Usuario, usuarios_ids: list[int]) -> list[int]:
    """Substitui a lista de fiscais."""
    ids = sorted(set(usuarios_ids))
    if ids:
        existentes = set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(ids), Usuario.ativo.is_(True))))
        faltando = set(ids) - existentes
        if faltando:
            raise ErroReserva("Há usuários inexistentes ou inativos na lista de fiscais.", 400, "invalido")
    atuais = set(ids_fiscais(sessao))
    for uid in atuais - set(ids):
        sessao.delete(sessao.get(FiscalReservaEspacos, uid))
    for uid in set(ids) - atuais:
        sessao.add(FiscalReservaEspacos(usuario_id=uid))
    auditar(sessao, autor.login, "reserva_espacos.fiscais", "Fiscais da reserva de espaços", f"{len(ids)} fiscal(is)", autor_id=autor.id)
    return ids


# --- Espaços ------------------------------------------------------------------------------------------------------------------------

def espaco_ou_erro(sessao: Session, espaco_id: int) -> EspacoReservavel:
    espaco = sessao.get(EspacoReservavel, espaco_id)
    if espaco is None:
        raise ErroReserva("Espaço não encontrado.", 404, "nao_encontrado")
    return espaco


def salvar_espaco(sessao: Session, autor: Usuario, espaco: EspacoReservavel | None, valores: dict) -> EspacoReservavel:
    nome = valores["nome"].strip()
    duplicado = sessao.scalar(select(EspacoReservavel.id).where(func.lower(EspacoReservavel.nome) == nome.lower()))
    if duplicado and (espaco is None or duplicado != espaco.id):
        raise ErroReserva("Já existe um espaço com este nome.", 409, "conflito")
    novo = espaco is None
    espaco = espaco or EspacoReservavel()
    for campo, valor in valores.items():
        setattr(espaco, campo, nome if campo == "nome" else valor)
    sessao.add(espaco)
    sessao.flush()
    auditar(sessao, autor.login, "reserva_espacos.espaco_criar" if novo else "reserva_espacos.espaco_editar", espaco.nome, autor_id=autor.id,
            alvo_tipo="reserva_espaco_espaco", alvo_id=str(espaco.id))
    return espaco


def excluir_espaco(sessao: Session, autor: Usuario, espaco: EspacoReservavel) -> str:
    """Exclui o espaço sem reservas; com reservas, apenas o inativa. Devolve `excluido` ou `inativado`."""
    if sessao.scalar(select(func.count(ReservaEspaco.id)).where(ReservaEspaco.espaco_id == espaco.id)):
        espaco.ativo = False
        resultado = "inativado"
    else:
        sessao.delete(espaco)
        resultado = "excluido"
    auditar(sessao, autor.login, f"reserva_espacos.espaco_{resultado}", espaco.nome, autor_id=autor.id)
    return resultado


# --- Datas e conflitos --------------------------------------------------------------------------------------------------------------

def datas_da_recorrencia(inicio: date, tipo: str, ate: date | None) -> list[date]:
    """Datas da recorrência (a primeira é a própria data). O mensal preserva o dia, ajustando ao fim de meses mais curtos."""
    if tipo == "nenhuma":
        return [inicio]
    if ate is None or ate < inicio:
        raise ErroReserva("Informe a data final da recorrência (igual ou posterior à data inicial).")
    datas: list[date] = []
    atual = inicio
    indice = 0
    while atual <= ate:
        datas.append(atual)
        if len(datas) > LIMITE_OCORRENCIAS:
            raise ErroReserva(f"A recorrência gera mais de {LIMITE_OCORRENCIAS} reservas; reduza o período.")
        indice += 1
        if tipo == "diaria":
            atual = inicio + timedelta(days=indice)
        elif tipo == "semanal":
            atual = inicio + timedelta(weeks=indice)
        elif tipo == "quinzenal":
            atual = inicio + timedelta(weeks=2 * indice)
        else:
            mes = inicio.month - 1 + indice
            ano, mes = inicio.year + mes // 12, mes % 12 + 1
            atual = date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))
    return datas


def conflitos(sessao: Session, espaco_id: int, dia: date, inicio: time, fim: time, status: str = STATUS_DEFERIDA, ignorar_ids: set[int] | None = None,
              bloquear: bool = False) -> list[ReservaEspaco]:
    """Reservas do espaço, na data, com o `status` dado e horário que se sobrepõe (`inicio < fim_outra` e `fim > inicio_outra`)."""
    consulta = select(ReservaEspaco).where(
        ReservaEspaco.espaco_id == espaco_id, ReservaEspaco.data == dia, ReservaEspaco.status == status,
        ReservaEspaco.hora_inicio < fim, ReservaEspaco.hora_fim > inicio,
    )
    if ignorar_ids:
        consulta = consulta.where(ReservaEspaco.id.not_in(ignorar_ids))
    if bloquear:
        consulta = consulta.with_for_update()
    return list(sessao.scalars(consulta.order_by(ReservaEspaco.hora_inicio)))


def _descrever(r: ReservaEspaco) -> str:
    return f"{formatar_data(r.data)} {formatar_hora(r.hora_inicio)}–{formatar_hora(r.hora_fim)} ({r.titulo})"


def _validar_horario(sessao: Session, dados: DadosReserva, fiscal: bool) -> None:
    if dados.hora_fim <= dados.hora_inicio:
        raise ErroReserva("O horário final deve ser posterior ao inicial.")
    cfg = configuracao(sessao)
    if dados.hora_inicio < cfg.hora_abertura or dados.hora_fim > cfg.hora_fechamento:
        raise ErroReserva(f"Reservas só podem ocorrer entre {formatar_hora(cfg.hora_abertura)} e {formatar_hora(cfg.hora_fechamento)}.")
    if fiscal:
        return
    duracao = (datetime.combine(dados.data, dados.hora_fim) - datetime.combine(dados.data, dados.hora_inicio)).total_seconds() / 3600
    if cfg.duracao_maxima_horas and duracao > cfg.duracao_maxima_horas:
        raise ErroReserva(f"A duração máxima de uma reserva é de {cfg.duracao_maxima_horas} hora(s).")
    if cfg.antecedencia_minima_horas:
        inicio = datetime.combine(dados.data, dados.hora_inicio, tzinfo=FUSO_SAO_PAULO)
        if inicio - agora_utc() < timedelta(hours=cfg.antecedencia_minima_horas):
            raise ErroReserva(f"A solicitação exige antecedência mínima de {cfg.antecedencia_minima_horas} hora(s).")


def _validar_dados(dados: DadosReserva) -> None:
    if dados.recorrencia not in RECORRENCIAS:
        raise ErroReserva("Recorrência inválida.")
    if not dados.titulo.strip():
        raise ErroReserva("Informe o título da reserva.")


def _evento(reserva: ReservaEspaco, tipo: str, usuario: Usuario | None, detalhes: dict | None = None) -> None:
    reserva.eventos.append(EventoReservaEspaco(
        tipo=tipo, usuario_id=usuario.id if usuario else None, usuario_nome=_nome(usuario) if usuario else "Sistema", detalhes=detalhes,
    ))


# --- Solicitação --------------------------------------------------------------------------------------------------------------------

def solicitar(sessao: Session, usuario: Usuario, dados: DadosReserva, predefinida: bool = False) -> ResultadoSolicitacao:
    """Cria a reserva (ou a série). `predefinida` (só fiscal) já nasce DEFERIDA, em nome do responsável indicado."""
    _validar_dados(dados)
    fiscal = eh_fiscal(sessao, usuario)
    if predefinida and not fiscal:
        raise ErroReserva("Somente os fiscais criam reservas predefinidas.", 403, "acesso_negado")
    espaco = espaco_ou_erro(sessao, dados.espaco_id)
    if not espaco.ativo:
        raise ErroReserva("O espaço está inativo e não aceita reservas.")
    datas = datas_da_recorrencia(dados.data, dados.recorrencia, dados.recorrencia_ate)
    _validar_horario(sessao, dados, fiscal)
    if dados.data < hoje_sao_paulo() and not fiscal:
        raise ErroReserva("Não é possível solicitar reserva em data passada.")
    ocupadas, avisos = [], []
    if espaco.capacidade and dados.participantes and dados.participantes > espaco.capacidade:
        avisos.append(f"{espaco.nome} comporta {espaco.capacidade} pessoas e a reserva prevê {dados.participantes}.")
    for dia in datas:
        bloqueio = conflitos(sessao, espaco.id, dia, dados.hora_inicio, dados.hora_fim, bloquear=True)
        if bloqueio:
            ocupadas.append(f"{formatar_data(dia)} (já reservado: {bloqueio[0].titulo})")
        elif conflitos(sessao, espaco.id, dia, dados.hora_inicio, dados.hora_fim, STATUS_AGUARDANDO):
            avisos.append(f"Já há solicitação aguardando aprovação para {espaco.nome} em {formatar_data(dia)} neste horário.")
    if ocupadas:
        raise ErroReserva(f"{espaco.nome} está ocupado em: " + "; ".join(ocupadas) + ".", 409, "conflito")

    responsavel = sessao.get(Usuario, dados.responsavel_id) if dados.responsavel_id else None
    if dados.responsavel_id and responsavel is None:
        raise ErroReserva("Responsável não encontrado.", 404, "nao_encontrado")
    if predefinida:
        responsavel_nome = _nome(responsavel) if responsavel else dados.responsavel_nome.strip()
        if not responsavel_nome:
            raise ErroReserva("Informe o responsável pela reserva.")
    else:
        responsavel, responsavel_nome = usuario, _nome(usuario)
    serie = uuid.uuid4() if len(datas) > 1 else None
    reservas = []
    for dia in datas:
        r = ReservaEspaco(
            espaco_id=espaco.id, data=dia, hora_inicio=dados.hora_inicio, hora_fim=dados.hora_fim, titulo=dados.titulo.strip(),
            responsavel_id=responsavel.id if responsavel else None, responsavel_nome=responsavel_nome, observacoes=dados.observacoes.strip(),
            participantes=dados.participantes, solicitante_id=usuario.id, solicitante_nome=_nome(usuario), serie_id=serie,
            status=STATUS_DEFERIDA if predefinida else STATUS_AGUARDANDO,
            fiscal_id=usuario.id if predefinida else None, fiscal_nome=_nome(usuario) if predefinida else "",
        )
        _evento(r, "CRIACAO", usuario, {"predefinida": predefinida, "recorrencia": dados.recorrencia, "ocorrencias": len(datas)})
        sessao.add(r)
        reservas.append(r)
    sessao.flush()
    auditar(sessao, usuario.login, "reserva_espacos.solicitar", f"{espaco.nome} · {dados.titulo}", f"{len(reservas)} reserva(s)", autor_id=usuario.id,
            alvo_tipo="reserva_espaco", alvo_id=str(reservas[0].id))
    _avisar_nova(sessao, usuario, reservas, espaco, predefinida)
    return ResultadoSolicitacao(reservas, avisos)


def _periodo(reservas: list[ReservaEspaco]) -> str:
    primeira, ultima = reservas[0], reservas[-1]
    quando = f"{formatar_data(primeira.data)} ({formatar_hora(primeira.hora_inicio)}–{formatar_hora(primeira.hora_fim)})"
    return quando if len(reservas) == 1 else f"{len(reservas)} ocorrências, de {formatar_data(primeira.data)} a {formatar_data(ultima.data)}, {formatar_hora(primeira.hora_inicio)}–{formatar_hora(primeira.hora_fim)}"


def _avisar_nova(sessao: Session, usuario: Usuario, reservas: list[ReservaEspaco], espaco: EspacoReservavel, predefinida: bool) -> None:
    primeira = reservas[0]
    if predefinida:
        if primeira.responsavel_id and primeira.responsavel_id != usuario.id:
            servico_mensagens.notificar(
                sessao, [primeira.responsavel_id], f"Reserva de {espaco.nome} registrada em seu nome",
                f"{_nome(usuario)} registrou a reserva \"{primeira.titulo}\" em {espaco.nome}: {_periodo(reservas)}.",
                chave=f"reserva-espacos:{primeira.id}:predefinida", link=f"/reserva-espacos/reservas/{primeira.id}", email=True, autor=usuario,
            )
        return
    servico_mensagens.notificar(
        sessao, _destinatarios_fiscais(sessao), f"Nova solicitação de reserva: {espaco.nome}",
        f"{_nome(usuario)} solicitou \"{primeira.titulo}\" em {espaco.nome}: {_periodo(reservas)}. Analise a solicitação na fila do fiscal.",
        chave=f"reserva-espacos:{primeira.id}:nova", categoria="pendencia", prioridade="alta", link="/reserva-espacos/fila", email=True, autor=usuario,
    )


# --- Consulta -----------------------------------------------------------------------------------------------------------------------

def reserva_ou_erro(sessao: Session, reserva_id: int) -> ReservaEspaco:
    reserva = sessao.scalar(select(ReservaEspaco).where(ReservaEspaco.id == reserva_id).options(selectinload(ReservaEspaco.espaco), selectinload(ReservaEspaco.eventos)))
    if reserva is None:
        raise ErroReserva("Reserva não encontrada.", 404, "nao_encontrado")
    return reserva


def da_serie(sessao: Session, reserva: ReservaEspaco) -> list[ReservaEspaco]:
    """Todas as ocorrências da série (ou só a própria reserva), em ordem de data."""
    if reserva.serie_id is None:
        return [reserva]
    return list(sessao.scalars(select(ReservaEspaco).where(ReservaEspaco.serie_id == reserva.serie_id).order_by(ReservaEspaco.data, ReservaEspaco.hora_inicio)))


def agenda(sessao: Session, usuario: Usuario, inicio: date, fim: date, espaco_id: int | None = None) -> list[ReservaEspaco]:
    """Reservas deferidas do período; o fiscal e o dono veem também as aguardando aprovação."""
    consulta = select(ReservaEspaco).where(ReservaEspaco.data >= inicio, ReservaEspaco.data <= fim).options(selectinload(ReservaEspaco.espaco))
    if espaco_id:
        consulta = consulta.where(ReservaEspaco.espaco_id == espaco_id)
    reservas = list(sessao.scalars(consulta.order_by(ReservaEspaco.data, ReservaEspaco.hora_inicio)))
    fiscal = eh_fiscal(sessao, usuario)
    visiveis = []
    for r in reservas:
        if r.status == STATUS_DEFERIDA or (r.status == STATUS_AGUARDANDO and (fiscal or usuario.id in (r.solicitante_id, r.responsavel_id))):
            visiveis.append(r)
    return visiveis


def minhas(sessao: Session, usuario: Usuario, status: str | None = None) -> list[ReservaEspaco]:
    consulta = select(ReservaEspaco).where((ReservaEspaco.solicitante_id == usuario.id) | (ReservaEspaco.responsavel_id == usuario.id)).options(selectinload(ReservaEspaco.espaco))
    if status:
        consulta = consulta.where(ReservaEspaco.status == status)
    return list(sessao.scalars(consulta.order_by(ReservaEspaco.data.desc(), ReservaEspaco.hora_inicio)))


def listar(sessao: Session, status: str | None, espaco_id: int | None, inicio: date | None, fim: date | None, busca: str,
           pagina: int, tamanho: int) -> tuple[list[ReservaEspaco], int]:
    """Todas as reservas (fiscal), com filtros e paginação."""
    consulta = select(ReservaEspaco)
    if status:
        consulta = consulta.where(ReservaEspaco.status == status)
    if espaco_id:
        consulta = consulta.where(ReservaEspaco.espaco_id == espaco_id)
    if inicio:
        consulta = consulta.where(ReservaEspaco.data >= inicio)
    if fim:
        consulta = consulta.where(ReservaEspaco.data <= fim)
    if busca.strip():
        termo = f"%{busca.strip().lower()}%"
        consulta = consulta.where(func.lower(ReservaEspaco.titulo + " " + ReservaEspaco.responsavel_nome + " " + ReservaEspaco.solicitante_nome).like(termo))
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = list(sessao.scalars(consulta.options(selectinload(ReservaEspaco.espaco)).order_by(ReservaEspaco.data.desc(), ReservaEspaco.hora_inicio)
                                .offset((pagina - 1) * tamanho).limit(tamanho)))
    return itens, total


def fila(sessao: Session) -> list[ReservaEspaco]:
    """Solicitações aguardando análise, da data mais próxima para a mais distante."""
    return list(sessao.scalars(select(ReservaEspaco).where(ReservaEspaco.status == STATUS_AGUARDANDO)
                               .options(selectinload(ReservaEspaco.espaco)).order_by(ReservaEspaco.data, ReservaEspaco.hora_inicio)))


def disponiveis(sessao: Session, dia: date, inicio: time, fim: time) -> list[EspacoReservavel]:
    """Espaços ativos sem reserva deferida na data e no horário."""
    espacos = list(sessao.scalars(select(EspacoReservavel).where(EspacoReservavel.ativo.is_(True)).order_by(EspacoReservavel.nome)))
    return [e for e in espacos if not conflitos(sessao, e.id, dia, inicio, fim)]


# --- Edição, análise e cancelamento -------------------------------------------------------------------------------------------------

def editar(sessao: Session, usuario: Usuario, reserva: ReservaEspaco, dados: DadosReserva) -> ReservaEspaco:
    """Altera uma reserva aguardando aprovação (o solicitante, ou o fiscal); a recorrência não muda depois de criada."""
    fiscal = eh_fiscal(sessao, usuario)
    if not fiscal and reserva.solicitante_id != usuario.id:
        raise ErroReserva("Você só altera as reservas que solicitou.", 403, "acesso_negado")
    if reserva.status != STATUS_AGUARDANDO:
        raise ErroReserva("Só é possível alterar reservas aguardando aprovação.", 409, "conflito")
    _validar_dados(dados)
    espaco = espaco_ou_erro(sessao, dados.espaco_id)
    if not espaco.ativo:
        raise ErroReserva("O espaço está inativo e não aceita reservas.")
    _validar_horario(sessao, dados, fiscal)
    if conflitos(sessao, espaco.id, dados.data, dados.hora_inicio, dados.hora_fim, bloquear=True):
        raise ErroReserva(f"{espaco.nome} já está reservado nesta data e horário.", 409, "conflito")
    antes = {"espaco": reserva.espaco.nome, "data": formatar_data(reserva.data), "inicio": formatar_hora(reserva.hora_inicio), "fim": formatar_hora(reserva.hora_fim),
             "titulo": reserva.titulo}
    reserva.espaco_id, reserva.data, reserva.hora_inicio, reserva.hora_fim = espaco.id, dados.data, dados.hora_inicio, dados.hora_fim
    reserva.titulo, reserva.observacoes, reserva.participantes = dados.titulo.strip(), dados.observacoes.strip(), dados.participantes
    sessao.flush()
    sessao.refresh(reserva, ["espaco"])
    _evento(reserva, "EDICAO", usuario, {"antes": antes})
    auditar(sessao, usuario.login, "reserva_espacos.editar", f"{espaco.nome} · {reserva.titulo}", autor_id=usuario.id, alvo_tipo="reserva_espaco", alvo_id=str(reserva.id))
    return reserva


def analisar(sessao: Session, fiscal: Usuario, reserva: ReservaEspaco, deferir: bool, justificativa: str = "") -> list[ReservaEspaco]:
    """Defere ou indefere a reserva e toda a sua série pendente, em bloco: se uma ocorrência conflitar, nenhuma é deferida."""
    exigir_fiscal(sessao, fiscal)
    justificativa = justificativa.strip()
    if not deferir and not justificativa:
        raise ErroReserva("Informe a justificativa do indeferimento.")
    alvo = [r for r in da_serie(sessao, reserva) if r.status == STATUS_AGUARDANDO]
    if reserva.status != STATUS_AGUARDANDO or not alvo:
        raise ErroReserva("A reserva não está aguardando aprovação.", 409, "conflito")
    if deferir:
        ids = {r.id for r in alvo}
        for r in alvo:
            colisao = conflitos(sessao, r.espaco_id, r.data, r.hora_inicio, r.hora_fim, ignorar_ids=ids, bloquear=True)
            if colisao:
                raise ErroReserva(f"Conflito em {formatar_data(r.data)}: {r.espaco.nome} já está reservado ({colisao[0].titulo}, "
                                  f"{formatar_hora(colisao[0].hora_inicio)}–{formatar_hora(colisao[0].hora_fim)}).", 409, "conflito")
    for r in alvo:
        r.status = STATUS_DEFERIDA if deferir else STATUS_INDEFERIDA
        r.fiscal_id, r.fiscal_nome = fiscal.id, _nome(fiscal)
        r.justificativa = "" if deferir else justificativa
        _evento(r, "DEFERIMENTO" if deferir else "INDEFERIMENTO", fiscal, {"justificativa": justificativa} if justificativa else None)
    auditar(sessao, fiscal.login, "reserva_espacos.deferir" if deferir else "reserva_espacos.indeferir", f"{reserva.espaco.nome} · {reserva.titulo}",
            f"{len(alvo)} reserva(s)", autor_id=fiscal.id, alvo_tipo="reserva_espaco", alvo_id=str(reserva.id))
    primeira = alvo[0]
    destinatarios = [i for i in {primeira.solicitante_id, primeira.responsavel_id} if i]
    servico_mensagens.notificar(
        sessao, destinatarios, f"Reserva {'deferida' if deferir else 'indeferida'}: {reserva.espaco.nome}",
        f"Sua solicitação \"{primeira.titulo}\" ({_periodo(alvo)}) foi {'deferida' if deferir else 'indeferida'} por {_nome(fiscal)}."
        + (f" Justificativa: {justificativa}" if not deferir else ""),
        chave=f"reserva-espacos:{primeira.id}:{'deferida' if deferir else 'indeferida'}", link=f"/reserva-espacos/reservas/{primeira.id}", email=True, autor=fiscal,
    )
    servico_mensagens.encerrar(sessao, chave=f"reserva-espacos:{primeira.id}:nova")
    return alvo


def cancelar(sessao: Session, usuario: Usuario, reserva: ReservaEspaco, escopo: str, motivo: str, de: date | None = None, ate: date | None = None) -> list[ReservaEspaco]:
    """Cancela uma ocorrência (`ocorrencia`), a série ativa (`serie`) ou as ocorrências de um período (`periodo`)."""
    fiscal = eh_fiscal(sessao, usuario)
    if not fiscal and usuario.id not in (reserva.solicitante_id, reserva.responsavel_id):
        raise ErroReserva("Você só cancela as reservas que solicitou.", 403, "acesso_negado")
    motivo = motivo.strip()
    if not motivo:
        raise ErroReserva("Informe o motivo do cancelamento.")
    ativas = (STATUS_AGUARDANDO, STATUS_DEFERIDA)
    if reserva.status not in ativas:
        raise ErroReserva("Só reservas aguardando aprovação ou deferidas podem ser canceladas.", 409, "conflito")
    if escopo == "ocorrencia" or reserva.serie_id is None:
        alvo = [reserva]
    elif escopo == "serie":
        alvo = [r for r in da_serie(sessao, reserva) if r.status in ativas]
    elif escopo == "periodo":
        if de is None or ate is None or ate < de:
            raise ErroReserva("Informe o período do cancelamento (início e fim).")
        alvo = [r for r in da_serie(sessao, reserva) if r.status in ativas and de <= r.data <= ate]
    else:
        raise ErroReserva("Escopo de cancelamento inválido.")
    if not alvo:
        raise ErroReserva("Nenhuma reserva ativa no escopo informado.", 409, "conflito")
    for r in alvo:
        r.status = STATUS_CANCELADA
        r.justificativa = motivo
        _evento(r, "CANCELAMENTO", usuario, {"escopo": escopo, "motivo": motivo})
    auditar(sessao, usuario.login, "reserva_espacos.cancelar", f"{reserva.espaco.nome} · {reserva.titulo}", f"{len(alvo)} reserva(s) — {escopo}", autor_id=usuario.id,
            alvo_tipo="reserva_espaco", alvo_id=str(reserva.id))
    destinatarios = [i for i in {reserva.solicitante_id, reserva.responsavel_id} if i]
    if usuario.id in destinatarios:
        destinatarios = []
        if fiscal_ids := _destinatarios_fiscais(sessao):
            servico_mensagens.notificar(
                sessao, fiscal_ids, f"Reserva cancelada: {reserva.espaco.nome}", f"{_nome(usuario)} cancelou \"{reserva.titulo}\" ({_periodo(alvo)}). Motivo: {motivo}",
                chave=f"reserva-espacos:{reserva.id}:cancelada:{len(alvo)}", link=f"/reserva-espacos/reservas/{reserva.id}", autor=usuario,
            )
    servico_mensagens.notificar(
        sessao, destinatarios, f"Reserva cancelada: {reserva.espaco.nome}", f"A reserva \"{reserva.titulo}\" ({_periodo(alvo)}) foi cancelada por {_nome(usuario)}. Motivo: {motivo}",
        chave=f"reserva-espacos:{reserva.id}:cancelada:{len(alvo)}", link=f"/reserva-espacos/reservas/{reserva.id}", email=True, autor=usuario,
    )
    return alvo


# --- Painel e exportação ------------------------------------------------------------------------------------------------------------

def painel(sessao: Session, ano: int, mes: int) -> dict:
    """Indicadores do mês (total, por status, espaços, média por dia útil de uso), por mês do ano e ranking de espaços e pessoas."""
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])
    reservas = list(sessao.scalars(select(ReservaEspaco).where(ReservaEspaco.data >= inicio, ReservaEspaco.data <= fim).options(selectinload(ReservaEspaco.espaco))))
    por_status = Counter(r.status for r in reservas)
    deferidas = [r for r in reservas if r.status == STATUS_DEFERIDA]
    cfg = configuracao(sessao)
    horas_dia = max((datetime.combine(inicio, cfg.hora_fechamento) - datetime.combine(inicio, cfg.hora_abertura)).total_seconds() / 3600, 1)
    ativos = list(sessao.scalars(select(EspacoReservavel).where(EspacoReservavel.ativo.is_(True))))
    dias_uteis = sum(1 for d in range(1, fim.day + 1) if date(ano, mes, d).weekday() < 5) or 1
    horas_ocupadas = {e.id: 0.0 for e in ativos}
    for r in deferidas:
        horas_ocupadas[r.espaco_id] = horas_ocupadas.get(r.espaco_id, 0) + (datetime.combine(r.data, r.hora_fim) - datetime.combine(r.data, r.hora_inicio)).total_seconds() / 3600
    ocupacao = [{"espaco": e.nome, "cor": e.cor, "horas": round(horas_ocupadas.get(e.id, 0), 1), "reservas": sum(1 for r in deferidas if r.espaco_id == e.id),
                 "ocupacao_percentual": round(100 * horas_ocupadas.get(e.id, 0) / (horas_dia * dias_uteis), 1)} for e in ativos]
    pessoas = Counter(r.responsavel_nome or r.solicitante_nome for r in reservas if r.status != STATUS_CANCELADA)
    por_mes = []
    for m in range(1, 13):
        ini, fi = date(ano, m, 1), date(ano, m, calendar.monthrange(ano, m)[1])
        por_mes.append({"mes": m, "rotulo": MESES[m - 1][:3], "total": sessao.scalar(select(func.count(ReservaEspaco.id)).where(
            ReservaEspaco.data >= ini, ReservaEspaco.data <= fi, ReservaEspaco.status == STATUS_DEFERIDA)) or 0})
    return {
        "ano": ano, "mes": mes, "total": len(reservas), "deferidas": por_status[STATUS_DEFERIDA], "indeferidas": por_status[STATUS_INDEFERIDA],
        "aguardando": por_status[STATUS_AGUARDANDO], "canceladas": por_status[STATUS_CANCELADA], "espacos_ativos": len(ativos),
        "media_por_dia": round(len(deferidas) / dias_uteis, 2), "por_mes": por_mes,
        "ocupacao": sorted(ocupacao, key=lambda o: -o["horas"]),
        "pessoas": [{"nome": nome, "total": total} for nome, total in pessoas.most_common(15)],
    }


def exportar_xlsx(reservas: list[ReservaEspaco]) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Font

    livro = Workbook()
    folha = livro.active
    folha.title = "Reservas"
    folha.append(["Data", "Início", "Fim", "Espaço", "Título", "Responsável", "Solicitante", "Status", "Fiscal", "Justificativa/motivo", "Série"])
    for celula in folha[1]:
        celula.font = Font(bold=True)
    for r in reservas:
        folha.append([r.data, formatar_hora(r.hora_inicio), formatar_hora(r.hora_fim), r.espaco.nome, r.titulo, r.responsavel_nome, r.solicitante_nome,
                      r.status, r.fiscal_nome, r.justificativa, str(r.serie_id) if r.serie_id else ""])
    for coluna, largura in zip("ABCDEFGHIJK", (12, 8, 8, 24, 36, 28, 28, 22, 28, 40, 38)):
        folha.column_dimensions[coluna].width = largura
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()


# --- Lembretes ----------------------------------------------------------------------------------------------------------------------

def lembrar(sessao: Session, dia: date | None = None) -> int:
    """Um dia antes, avisa (com e-mail) o responsável e o solicitante das reservas deferidas. Idempotente pela marca da reserva."""
    dia = dia or hoje_sao_paulo()
    amanha = dia + timedelta(days=1)
    avisadas = 0
    for r in sessao.scalars(select(ReservaEspaco).where(ReservaEspaco.data == amanha, ReservaEspaco.status == STATUS_DEFERIDA, ReservaEspaco.lembrete_enviado.is_(False))
                            .options(selectinload(ReservaEspaco.espaco))):
        r.lembrete_enviado = True
        if servico_mensagens.notificar(
            sessao, [i for i in {r.solicitante_id, r.responsavel_id} if i], f"Lembrete: {r.espaco.nome} amanhã",
            f"Você tem a reserva \"{r.titulo}\" em {r.espaco.nome} amanhã, {formatar_data(r.data)}, das {formatar_hora(r.hora_inicio)} às {formatar_hora(r.hora_fim)}. "
            "Se não for usar o espaço, cancele a reserva para liberá-lo.",
            chave=f"reserva-espacos:{r.id}:lembrete", categoria="prazo", link=f"/reserva-espacos/reservas/{r.id}", email=True,
        ):
            avisadas += 1
    sessao.commit()
    return avisadas
