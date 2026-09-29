# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de férias e licença-prêmio (agendamento, aprovação, painel e exportação).
"""Férias e licença-prêmio (Funcionalidade 2 do Módulo RH).

- **Agendamento** pelo próprio usuário, validado pelos parâmetros da CGP (`ParametrosRh`): mínimo de dias
  consecutivos e dias da semana vedados para o início (por tipo), antecedência mínima, dentro do exercício
  (ano civil), saldo do tipo (independentes), sem sobreposição e, se a CGP proibir, sem emenda entre tipos.
- **Status:** pendente → aprovado | recusado; aprovado → cancelado | gozado (automático após o fim).
  Alteração de um aprovado cria um novo pedido pendente (`substitui_id`); ao ser aprovado, o anterior é
  cancelado. Cancelar/alterar: o usuário até o prazo da CGP; a CGP a qualquer momento.
- **Aprovação:** o autorizador, o substituto (se o autorizador estiver afastado) ou a CGP. Recusa exige
  justificativa. O usuário recebe e-mail a cada mudança de status.
- **Painel:** CGP vê todos; autorizador vê os autorizados e a si mesmo; o usuário comum, só a si.
"""

import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.rh import Afastamento, EventoAfastamento, ParametrosRh, PeriodoAquisitivo
from app.models.setor import MembroSetor
from app.models.usuario import Usuario
from app.services import servico_mensagens
from app.services.rh import servico_periodos
from app.services.rh.papeis import (
    SemPermissaoRh,
    aprovadores_de,
    autorizados_por,
    dados_funcionais,
    eh_autorizador,
    eh_cgp,
    exigir_cgp,
    setor_com_descendentes,
    setor_do_usuario,
    usuarios_cgp,
)
from app.services.servico_auditoria import auditar

ATIVOS = ("pendente", "aprovado", "gozado")
ROTULOS_TIPO = {"ferias": "férias", "licenca_premio": "licença-prêmio"}
SIGLAS_TIPO = {"ferias": "F", "licenca_premio": "LP"}
ROTULOS_STATUS = {"pendente": "Pendente", "aprovado": "Aprovado", "recusado": "Recusado", "cancelado": "Cancelado", "gozado": "Gozado"}
DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


class ErroAfastamento(Exception):
    """Regra de agendamento violada (vira 400; `status` pode indicar 404)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def hoje() -> date:
    """Data civil em São Paulo (substituída nos testes)."""
    from app.services.contratos.servico_contratos import hoje as hoje_sp

    return hoje_sp()


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "—"


def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


# --- Parâmetros ---------------------------------------------------------------------------------

def parametros(sessao: Session) -> ParametrosRh:
    """Parâmetros em vigor (a linha é criada com os valores iniciais se ainda não existir)."""
    registro = sessao.get(ParametrosRh, 1)
    if registro is None:
        registro = ParametrosRh(id=1, minimo_dias_ferias=5, minimo_dias_lp=5, inicio_vedado_ferias=[0], inicio_vedado_lp=[0],
                                antecedencia_minima_dias=30, prazo_cancelamento_dias=5, permite_emenda=True, limite_alerta_setor=3)
        sessao.add(registro)
        sessao.flush()
    return registro


def salvar_parametros(sessao: Session, dados: dict, autor: Usuario) -> ParametrosRh:
    exigir_cgp(sessao, autor)
    registro = parametros(sessao)
    antes = {c: getattr(registro, c) for c in dados}
    for campo, valor in dados.items():
        setattr(registro, campo, sorted(set(valor)) if isinstance(valor, list) else valor)
    registro.atualizado_por_nome, registro.atualizado_em = _nome(autor), agora_utc()
    auditar(sessao, autor.login, "rh.parametros", "Parâmetros de férias e licença-prêmio", autor_id=autor.id,
            dados={"campos": {c: {"de": antes[c], "para": dados[c]} for c in dados if antes[c] != dados[c]}})
    sessao.commit()
    return registro


# --- Saldos -------------------------------------------------------------------------------------

@dataclass
class Saldo:
    saldo: int
    usado: int

    @property
    def disponivel(self) -> int:
        return self.saldo - self.usado


def saldos(sessao: Session, usuario_id: int, exercicio: int) -> dict[str, Saldo]:
    """Saldos por tipo.

    - Férias: o período aquisitivo vigente hoje (dias creditados − pedidos que começam nele).
    - Licença-prêmio: saldo informado pela CGP para o exercício (ano civil) − pedidos do exercício.
    """
    dados = dados_funcionais(sessao, usuario_id)
    vale_lp = dados is not None and (dados.exercicio or hoje().year) == exercicio
    usado_lp = sum((a.dias for a in sessao.scalars(select(Afastamento).where(
        Afastamento.usuario_id == usuario_id, Afastamento.tipo == "licenca_premio", Afastamento.exercicio == exercicio,
        Afastamento.status.in_(ATIVOS)))), 0)
    periodo = servico_periodos.vigente(sessao, usuario_id, hoje())
    ferias = (Saldo(periodo.dias_creditados, servico_periodos.usado(sessao, usuario_id, periodo.inicio, periodo.fim))
              if periodo else Saldo(0, 0))
    return {"ferias": ferias, "licenca_premio": Saldo(dados.saldo_lp_dias if vale_lp else 0, usado_lp)}


def periodo_do_pedido(sessao: Session, usuario_id: int, inicio: date) -> tuple[date, date, int, PeriodoAquisitivo | None]:
    """Período aquisitivo que as férias debitam (o vigente ou o próximo): (início, fim, dias creditados, registro)."""
    dados = dados_funcionais(sessao, usuario_id)
    if not dados or not dados.inicio_aquisitivo_dia:
        raise ErroAfastamento("A CGP ainda não informou o início do seu período aquisitivo: não é possível agendar férias.")
    dia, mes = dados.inicio_aquisitivo_dia, dados.inicio_aquisitivo_mes
    atual_inicio, atual_fim = servico_periodos.limites(dia, mes, hoje())
    proximo_inicio, proximo_fim = servico_periodos.limites(dia, mes, atual_fim + timedelta(days=1))
    if inicio < atual_inicio or inicio > proximo_fim:
        raise ErroAfastamento(
            f"As férias precisam começar no período aquisitivo vigente ({_data(atual_inicio)} a {_data(atual_fim)}) "
            f"ou no próximo ({_data(proximo_inicio)} a {_data(proximo_fim)})."
        )
    p_inicio, p_fim = (atual_inicio, atual_fim) if inicio <= atual_fim else (proximo_inicio, proximo_fim)
    registro = servico_periodos.obter(sessao, usuario_id, p_inicio, p_fim, criar=False)
    creditados = registro.dias_creditados if registro else parametros(sessao).dias_ferias_por_periodo
    return p_inicio, p_fim, creditados, registro


# --- Validação do pedido ------------------------------------------------------------------------

def validar_pedido(sessao: Session, usuario: Usuario, tipo: str, inicio: date, fim: date, *, ignorar: list[uuid.UUID] = (),
                   cgp: bool = False) -> int:
    """Confere todas as regras e devolve a quantidade de dias corridos."""
    p = parametros(sessao)
    rotulo = ROTULOS_TIPO[tipo]
    if fim < inicio:
        raise ErroAfastamento("A data final deve ser igual ou posterior à inicial.")
    dias = (fim - inicio).days + 1
    minimo = p.minimo_dias_ferias if tipo == "ferias" else p.minimo_dias_lp
    if dias < minimo:
        raise ErroAfastamento(f"O período de {rotulo} precisa ter pelo menos {minimo} dias consecutivos (pedido de {dias}).")
    vedados = p.inicio_vedado_ferias if tipo == "ferias" else p.inicio_vedado_lp
    if inicio.weekday() in (vedados or []):
        raise ErroAfastamento(f"O período de {rotulo} não pode começar numa {DIAS_SEMANA[inicio.weekday()]}.")
    if p.inicio_vedado_feriado:
        from app.services.rh.servico_feriados import no_intervalo

        feriado = no_intervalo(sessao, inicio, inicio).get(inicio)
        if feriado is not None:
            raise ErroAfastamento(f"O período não pode começar em feriado ou ponto facultativo ({_data(inicio)}: {feriado.descricao}).")
    if tipo == "licenca_premio" and inicio.year != fim.year:
        raise ErroAfastamento(f"A licença-prêmio precisa ficar dentro do exercício (ano civil): termine até 31/12/{inicio.year}.")
    if not cgp and (inicio - hoje()).days < p.antecedencia_minima_dias:
        limite = hoje() + timedelta(days=p.antecedencia_minima_dias)
        raise ErroAfastamento(f"É preciso agendar com {p.antecedencia_minima_dias} dias de antecedência: comece a partir de {_data(limite)}.")
    # Sobreposição com qualquer afastamento ativo (e, se proibido, emenda entre tipos diferentes)
    for outro in sessao.scalars(select(Afastamento).where(Afastamento.usuario_id == usuario.id, Afastamento.status.in_(ATIVOS))):
        if outro.id in ignorar:
            continue
        if outro.inicio <= fim and inicio <= outro.fim:
            raise ErroAfastamento(
                f"O período se sobrepõe a {ROTULOS_TIPO[outro.tipo]} de {_data(outro.inicio)} a {_data(outro.fim)} ({ROTULOS_STATUS[outro.status].lower()})."
            )
        encosta = outro.fim + timedelta(days=1) == inicio or fim + timedelta(days=1) == outro.inicio
        if encosta and not p.permite_emenda and outro.tipo != tipo:
            raise ErroAfastamento("Não é permitido emendar férias e licença-prêmio em sequência.")
    if tipo == "ferias":
        # Férias: saldo do período aquisitivo em que o pedido começa (vigente ou próximo)
        p_inicio, p_fim, creditados, _ = periodo_do_pedido(sessao, usuario.id, inicio)
        disponivel = creditados - servico_periodos.usado(sessao, usuario.id, p_inicio, p_fim, ignorar)
        if dias > disponivel:
            raise ErroAfastamento(
                f"Saldo de férias do período aquisitivo {_data(p_inicio)} a {_data(p_fim)} insuficiente: "
                f"{max(disponivel, 0)} dia(s) disponível(is), pedido de {dias}."
            )
        return dias
    saldo = saldos(sessao, usuario.id, inicio.year)["licenca_premio"]
    liberado = sum((a.dias for a in sessao.scalars(select(Afastamento).where(Afastamento.id.in_(list(ignorar))))
                    if a.tipo == tipo and a.exercicio == inicio.year and a.status in ATIVOS), 0) if ignorar else 0
    disponivel = saldo.disponivel + liberado
    if dias > disponivel:
        raise ErroAfastamento(f"Saldo de {rotulo} insuficiente: {max(disponivel, 0)} dia(s) disponível(is) em {inicio.year}, pedido de {dias}.")
    return dias


# --- Eventos e avisos ---------------------------------------------------------------------------

def _evento(afastamento: Afastamento, de: str | None, para: str, autor: Usuario | None, justificativa: str | None = None) -> None:
    afastamento.eventos.append(EventoAfastamento(de=de, para=para, autor_id=autor.id if autor else None,
                                                 autor_nome=_nome(autor) if autor else "Sistema", justificativa=justificativa,
                                                 ocorrido_em=agora_utc()))


def _descricao(a: Afastamento) -> str:
    return f"{ROTULOS_TIPO[a.tipo]} de {_data(a.inicio)} a {_data(a.fim)} ({a.dias} dias)"


def _avisar_aprovadores(sessao: Session, usuario: Usuario, a: Afastamento) -> None:
    """Autorizador (ou substituto) e CGP: pedido aguardando aprovação (encerrado na decisão)."""
    ids = set(aprovadores_de(sessao, usuario.id, hoje())) | {u.id for u in usuarios_cgp(sessao)}
    ids.discard(usuario.id)
    servico_mensagens.notificar(
        sessao, list(ids), f"{_nome(usuario)} agendou {ROTULOS_TIPO[a.tipo]} e aguarda aprovação",
        f"{_nome(usuario)} ({setor_do_usuario(usuario)}) agendou {_descricao(a)} e aguarda aprovação.",
        chave=f"afastamento:{a.id}:{a.inicio:%Y%m%d}", categoria="pendencia", prioridade="alta", link="/rh/painel-afastamentos",
        email=True,
    )


def _avisar_usuario(sessao: Session, usuario_id: int, a: Afastamento, titulo: str, texto: str) -> None:
    servico_mensagens.notificar(
        sessao, [usuario_id], titulo, texto, chave=f"afastamento-status:{a.id}:{a.status}:{agora_utc():%Y%m%d%H%M%S%f}",
        categoria="comunicado", prioridade="normal", link="/rh/ferias", email=True,
    )


# --- Ações --------------------------------------------------------------------------------------

def _carregar(sessao: Session, afastamento_id: uuid.UUID) -> Afastamento:
    a = sessao.get(Afastamento, afastamento_id)
    if a is None:
        raise ErroAfastamento("Afastamento não encontrado.", 404, "nao_encontrado")
    return a


def _vincular_periodo(sessao: Session, usuario_id: int, tipo: str, inicio: date) -> uuid.UUID | None:
    """Férias: id do período aquisitivo que o pedido debita (criado se ainda não existir)."""
    if tipo != "ferias":
        return None
    p_inicio, p_fim, _, _ = periodo_do_pedido(sessao, usuario_id, inicio)
    return servico_periodos.obter(sessao, usuario_id, p_inicio, p_fim).id


def lancar(sessao: Session, autor: Usuario, usuario_id: int, tipo: str, inicio: date, fim: date, situacao: str,
           justificativa: str, ignorar_saldo: bool = False) -> Afastamento:
    """A CGP lança, em nome do servidor, férias ou licença-prêmio já combinadas ou gozadas fora do sistema.

    Não há antecedência mínima, dia vedado nem mínimo de dias (inclusive retroativo); continuam valendo a
    sobreposição e o saldo (este pode ser ignorado, por exemplo em períodos anteriores ao sistema). O pedido já
    nasce aprovado (ou gozado), com o histórico "lançado pela CGP", e o servidor recebe e-mail.
    """
    exigir_cgp(sessao, autor)
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise ErroAfastamento("Usuário não encontrado.", 404, "nao_encontrado")
    if fim < inicio:
        raise ErroAfastamento("A data final deve ser igual ou posterior à inicial.")
    if situacao == "gozado" and fim >= hoje():
        raise ErroAfastamento("Só períodos já encerrados podem ser lançados como gozados; use \"aprovado\" para os demais.")
    dias = (fim - inicio).days + 1
    for outro in sessao.scalars(select(Afastamento).where(Afastamento.usuario_id == usuario.id, Afastamento.status.in_(ATIVOS))):
        if outro.inicio <= fim and inicio <= outro.fim:
            raise ErroAfastamento(
                f"O período se sobrepõe a {ROTULOS_TIPO[outro.tipo]} de {_data(outro.inicio)} a {_data(outro.fim)} ({ROTULOS_STATUS[outro.status].lower()})."
            )
    periodo_id = None
    if tipo == "ferias":
        dados = dados_funcionais(sessao, usuario.id)
        if not dados or not dados.inicio_aquisitivo_dia:
            raise ErroAfastamento("Informe antes o início do período aquisitivo deste servidor (dados funcionais).")
        p_inicio, p_fim = servico_periodos.limites(dados.inicio_aquisitivo_dia, dados.inicio_aquisitivo_mes, inicio)
        periodo = servico_periodos.obter(sessao, usuario.id, p_inicio, p_fim)
        periodo_id = periodo.id
        disponivel = periodo.dias_creditados - servico_periodos.usado(sessao, usuario.id, p_inicio, p_fim)
        if not ignorar_saldo and dias > disponivel:
            raise ErroAfastamento(
                f"Saldo de férias do período aquisitivo {_data(p_inicio)} a {_data(p_fim)} insuficiente: {max(disponivel, 0)} dia(s) "
                f"disponível(is), lançamento de {dias}. Marque \"ignorar saldo\" se o período é anterior ao sistema."
            )
    elif not ignorar_saldo:
        disponivel = saldos(sessao, usuario.id, inicio.year)["licenca_premio"].disponivel
        if dias > disponivel:
            raise ErroAfastamento(f"Saldo de licença-prêmio insuficiente: {max(disponivel, 0)} dia(s) disponível(is) em {inicio.year}, lançamento de {dias}.")
    a = Afastamento(usuario_id=usuario.id, tipo=tipo, inicio=inicio, fim=fim, dias=dias, exercicio=inicio.year, status=situacao,
                    periodo_aquisitivo_id=periodo_id, solicitado_em=agora_utc(), decidido_por_id=autor.id, decidido_por_nome=_nome(autor),
                    decidido_em=agora_utc())
    _evento(a, None, "aprovado", autor, f"Lançado pela CGP: {justificativa}")
    if situacao == "gozado":
        _evento(a, "aprovado", "gozado", autor)
    sessao.add(a)
    sessao.flush()
    _avisar_usuario(sessao, usuario.id, a, f"{ROTULOS_TIPO[a.tipo]} lançada pela CGP",
                    f"A CGP lançou {_descricao(a)} no seu registro ({ROTULOS_STATUS[situacao].lower()}).\n\nMotivo: {justificativa}")
    auditar(sessao, autor.login, "rh.afastamento.lancar", _descricao(a), autor_id=autor.id, alvo_tipo="afastamento", alvo_id=a.id,
            dados={"usuario_id": usuario.id, "situacao": situacao, "ignorar_saldo": ignorar_saldo, "justificativa": justificativa})
    sessao.commit()
    return a


def agendar(sessao: Session, usuario: Usuario, tipo: str, inicio: date, fim: date) -> Afastamento:
    dias = validar_pedido(sessao, usuario, tipo, inicio, fim)
    a = Afastamento(usuario_id=usuario.id, tipo=tipo, inicio=inicio, fim=fim, dias=dias, exercicio=inicio.year, status="pendente",
                    periodo_aquisitivo_id=_vincular_periodo(sessao, usuario.id, tipo, inicio),
                    solicitado_em=agora_utc())
    _evento(a, None, "pendente", usuario)
    sessao.add(a)
    sessao.flush()
    _avisar_aprovadores(sessao, usuario, a)
    auditar(sessao, usuario.login, "rh.afastamento.agendar", _descricao(a), autor_id=usuario.id, alvo_tipo="afastamento", alvo_id=a.id)
    sessao.commit()
    return a


def _exigir_prazo(sessao: Session, a: Afastamento, autor: Usuario) -> bool:
    """Dono do pedido dentro do prazo, ou CGP. Devolve se o autor é CGP."""
    cgp = eh_cgp(sessao, autor)
    if not cgp:
        if a.usuario_id != autor.id:
            raise SemPermissaoRh("Só o próprio usuário ou a CGP podem alterar ou cancelar este afastamento.")
        prazo = parametros(sessao).prazo_cancelamento_dias
        if (a.inicio - hoje()).days < prazo:
            raise ErroAfastamento(f"O prazo para alterar ou cancelar terminou: é até {prazo} dia(s) antes do início ({_data(a.inicio)}).")
    return cgp


def alterar(sessao: Session, autor: Usuario, afastamento_id: uuid.UUID, tipo: str, inicio: date, fim: date) -> Afastamento:
    """Pendente: muda o próprio pedido. Aprovado: cria um novo pedido pendente que substitui o anterior ao ser aprovado."""
    a = _carregar(sessao, afastamento_id)
    if a.status not in ("pendente", "aprovado"):
        raise ErroAfastamento("Só pedidos pendentes ou aprovados podem ser alterados.")
    cgp = _exigir_prazo(sessao, a, autor)
    usuario = sessao.get(Usuario, a.usuario_id)
    dias = validar_pedido(sessao, usuario, tipo, inicio, fim, ignorar=[a.id], cgp=cgp)
    if a.status == "pendente":
        # O aviso do pedido anterior sai; um novo é enviado com as datas novas
        servico_mensagens.encerrar(sessao, prefixo=f"afastamento:{a.id}:")
        a.tipo, a.inicio, a.fim, a.dias, a.exercicio = tipo, inicio, fim, dias, inicio.year
        a.periodo_aquisitivo_id = _vincular_periodo(sessao, a.usuario_id, tipo, inicio)
        _evento(a, "pendente", "pendente", autor, "Pedido alterado")
        novo = a
    else:
        novo = Afastamento(usuario_id=a.usuario_id, tipo=tipo, inicio=inicio, fim=fim, dias=dias, exercicio=inicio.year, status="pendente",
                           periodo_aquisitivo_id=_vincular_periodo(sessao, a.usuario_id, tipo, inicio),
                           solicitado_em=agora_utc(), substitui_id=a.id)
        _evento(novo, None, "pendente", autor, f"Alteração do período aprovado de {_data(a.inicio)} a {_data(a.fim)}")
        sessao.add(novo)
    sessao.flush()
    _avisar_aprovadores(sessao, usuario, novo)
    auditar(sessao, autor.login, "rh.afastamento.alterar", _descricao(novo), autor_id=autor.id, alvo_tipo="afastamento", alvo_id=novo.id)
    sessao.commit()
    return novo


def cancelar(sessao: Session, autor: Usuario, afastamento_id: uuid.UUID, justificativa: str | None) -> Afastamento:
    a = _carregar(sessao, afastamento_id)
    if a.status not in ("pendente", "aprovado"):
        raise ErroAfastamento("Só pedidos pendentes ou aprovados podem ser cancelados.")
    _exigir_prazo(sessao, a, autor)
    anterior, a.status = a.status, "cancelado"
    _evento(a, anterior, "cancelado", autor, justificativa)
    servico_mensagens.encerrar(sessao, prefixo=f"afastamento:{a.id}:")
    _avisar_usuario(sessao, a.usuario_id, a, f"Afastamento cancelado: {ROTULOS_TIPO[a.tipo]}",
                    f"{_nome(autor)} cancelou {_descricao(a)}." + (f"\n\nJustificativa: {justificativa}" if justificativa else ""))
    auditar(sessao, autor.login, "rh.afastamento.cancelar", _descricao(a), autor_id=autor.id, alvo_tipo="afastamento", alvo_id=a.id)
    sessao.commit()
    return a


def pode_decidir(sessao: Session, autor: Usuario, a: Afastamento, cgp: bool | None = None) -> bool:
    if a.status != "pendente":
        return False
    if cgp if cgp is not None else eh_cgp(sessao, autor):
        return True
    return a.usuario_id != autor.id and autor.id in aprovadores_de(sessao, a.usuario_id, hoje())


def decidir(sessao: Session, autor: Usuario, afastamento_id: uuid.UUID, aprovar: bool, justificativa: str | None) -> Afastamento:
    a = _carregar(sessao, afastamento_id)
    if a.status != "pendente":
        raise ErroAfastamento("Este pedido não está aguardando aprovação.")
    if not pode_decidir(sessao, autor, a):
        raise SemPermissaoRh("Só o autorizador (ou o substituto, se ele estiver afastado) e a CGP podem decidir este pedido.")
    justificativa = (justificativa or "").strip() or None
    if not aprovar and not justificativa:
        raise ErroAfastamento("Informe a justificativa da recusa.")
    a.status = "aprovado" if aprovar else "recusado"
    a.decidido_por_id, a.decidido_por_nome, a.decidido_em, a.justificativa = autor.id, _nome(autor), agora_utc(), justificativa
    _evento(a, "pendente", a.status, autor, justificativa)
    if aprovar and a.substitui_id:
        antigo = sessao.get(Afastamento, a.substitui_id)
        if antigo and antigo.status == "aprovado":
            antigo.status = "cancelado"
            _evento(antigo, "aprovado", "cancelado", autor, "Substituído por alteração aprovada")
    servico_mensagens.encerrar(sessao, prefixo=f"afastamento:{a.id}:")
    if aprovar:
        _avisar_usuario(sessao, a.usuario_id, a, f"{ROTULOS_TIPO[a.tipo].capitalize()} aprovada(s)", f"{_nome(autor)} aprovou {_descricao(a)}.")
    else:
        _avisar_usuario(sessao, a.usuario_id, a, f"{ROTULOS_TIPO[a.tipo].capitalize()} recusada(s)",
                        f"{_nome(autor)} recusou {_descricao(a)}.\n\nJustificativa: {justificativa}")
    auditar(sessao, autor.login, f"rh.afastamento.{'aprovar' if aprovar else 'recusar'}", _descricao(a), autor_id=autor.id,
            alvo_tipo="afastamento", alvo_id=a.id, dados={"justificativa": justificativa})
    sessao.commit()
    return a


def marcar_gozados(sessao: Session, dia: date | None = None) -> int:
    """Aprovados que já terminaram passam a `gozado` (tarefa diária)."""
    dia = dia or hoje()
    gozados = list(sessao.scalars(select(Afastamento).where(Afastamento.status == "aprovado", Afastamento.fim < dia)))
    for a in gozados:
        a.status = "gozado"
        _evento(a, "aprovado", "gozado", None)
        _avisar_usuario(sessao, a.usuario_id, a, f"{ROTULOS_TIPO[a.tipo].capitalize()} gozada(s)", f"Período registrado como gozado: {_descricao(a)}.")
    sessao.commit()
    return len(gozados)


def lembrar_pendentes(sessao: Session, dia: date | None = None, dias_espera: int = 3) -> int:
    """Pedidos pendentes há exatamente `dias_espera` dias: novo aviso (com e-mail) a quem pode aprovar."""
    dia = dia or hoje()
    lembrados = 0
    for a in sessao.scalars(select(Afastamento).where(Afastamento.status == "pendente")):
        if a.solicitado_em.date() != dia - timedelta(days=dias_espera):
            continue
        usuario = sessao.get(Usuario, a.usuario_id)
        ids = set(aprovadores_de(sessao, a.usuario_id, dia)) | {u.id for u in usuarios_cgp(sessao)}
        ids.discard(a.usuario_id)
        if servico_mensagens.notificar(
            sessao, list(ids), f"Lembrete: {_nome(usuario)} aguarda aprovação de {ROTULOS_TIPO[a.tipo]}",
            f"O pedido de {_descricao(a)} de {_nome(usuario)} aguarda aprovação há {dias_espera} dias.",
            chave=f"afastamento:{a.id}:lembrete:{dia:%Y%m%d}", categoria="pendencia", prioridade="alta", link="/rh/painel-afastamentos", email=True,
        ):
            lembrados += 1
    sessao.commit()
    return lembrados


# --- Consultas ----------------------------------------------------------------------------------

def meus(sessao: Session, usuario: Usuario, exercicio: int) -> tuple[dict[str, Saldo], list[Afastamento]]:
    lista = list(sessao.scalars(
        select(Afastamento).where(Afastamento.usuario_id == usuario.id, Afastamento.exercicio == exercicio)
        .options(selectinload(Afastamento.eventos)).order_by(Afastamento.inicio)
    ))
    return saldos(sessao, usuario.id, exercicio), lista


def escopo(sessao: Session, autor: Usuario) -> tuple[bool, list[int]]:
    """(é CGP, ids visíveis). CGP: todos (lista vazia = sem restrição); autorizador: autorizados + ele; comum: ele."""
    if eh_cgp(sessao, autor):
        return True, []
    return False, sorted(set(autorizados_por(sessao, autor.id, hoje())) | {autor.id})


def _ids_do_setor(sessao: Session, setor_id: int) -> set[int]:
    """Usuários do setor e dos setores filhos (por participação ou pelo Departamento em vigor)."""
    setores = setor_com_descendentes(sessao, [setor_id])
    nomes = {s.nome.strip().lower() for s in setores}
    ids = set(sessao.scalars(select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_([s.id for s in setores]))))
    ids |= {u.id for u in sessao.scalars(select(Usuario)) if (u.departamento or "").strip().lower() in nomes}
    return ids


def janela(visao: str, ano: int, mes: int | None) -> tuple[date, date]:
    if visao == "anual":
        return date(ano, 1, 1), date(ano, 12, 31)
    mes = mes or 1
    return date(ano, mes, 1), date(ano, mes, monthrange(ano, mes)[1])


def painel(sessao: Session, autor: Usuario, visao: str, ano: int, mes: int | None, pessoa_id: int | None, setor_id: int | None,
           tipo: str | None) -> dict:
    """Períodos visíveis (pendentes, aprovados e gozados) na janela, com os filtros, alertas e opções."""
    cgp, visiveis = escopo(sessao, autor)
    inicio, fim = janela(visao, ano, mes)
    consulta = select(Afastamento).where(Afastamento.status.in_(ATIVOS), Afastamento.inicio <= fim, Afastamento.fim >= inicio)
    if not cgp:
        consulta = consulta.where(Afastamento.usuario_id.in_(visiveis))
    if pessoa_id:
        consulta = consulta.where(Afastamento.usuario_id == pessoa_id)
    if tipo:
        consulta = consulta.where(Afastamento.tipo == tipo)
    periodos = list(sessao.scalars(consulta.order_by(Afastamento.inicio)))
    if setor_id:
        do_setor = _ids_do_setor(sessao, setor_id)
        periodos = [a for a in periodos if a.usuario_id in do_setor]
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_({a.usuario_id for a in periodos} | set(visiveis))))}
    if cgp:
        pessoas = list(sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))))
    else:
        pessoas = [usuarios[i] for i in visiveis if i in usuarios]
    return {
        "inicio": inicio, "fim": fim, "cgp": cgp,
        "periodos": [(a, usuarios.get(a.usuario_id), pode_decidir(sessao, autor, a, cgp)) for a in periodos],
        "alertas": alertas_setor(sessao, periodos, usuarios, inicio, fim),
        "pessoas": sorted(pessoas, key=lambda u: _nome(u).lower()),
    }


def alertas_setor(sessao: Session, periodos: list[Afastamento], usuarios: dict[int, Usuario], inicio: date, fim: date) -> list[dict]:
    """Faixas de dias em que pelo menos `limite_alerta_setor` pessoas do mesmo setor estão afastadas."""
    limite = parametros(sessao).limite_alerta_setor
    if not limite or limite < 2:
        return []
    por_setor: dict[str, list[Afastamento]] = {}
    for a in periodos:
        por_setor.setdefault(setor_do_usuario(usuarios[a.usuario_id]) if a.usuario_id in usuarios else "Sem setor", []).append(a)
    alertas = []
    for setor, lista in por_setor.items():
        if len({a.usuario_id for a in lista}) < limite:
            continue
        faixa_inicio, maximo, dia = None, 0, inicio
        while dia <= fim + timedelta(days=1):
            pessoas = {a.usuario_id for a in lista if a.inicio <= dia <= a.fim} if dia <= fim else set()
            if len(pessoas) >= limite:
                faixa_inicio = faixa_inicio or dia
                maximo = max(maximo, len(pessoas))
            elif faixa_inicio:
                alertas.append({"setor": setor, "inicio": faixa_inicio, "fim": dia - timedelta(days=1), "pessoas": maximo})
                faixa_inicio, maximo = None, 0
            dia += timedelta(days=1)
    return sorted(alertas, key=lambda x: (x["inicio"], x["setor"]))


def aprovacoes(sessao: Session, autor: Usuario) -> list[tuple[Afastamento, Usuario]]:
    """Pedidos pendentes que o usuário pode decidir."""
    cgp = eh_cgp(sessao, autor)
    pendentes = list(sessao.scalars(select(Afastamento).where(Afastamento.status == "pendente").order_by(Afastamento.solicitado_em)))
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_({a.usuario_id for a in pendentes})))} if pendentes else {}
    return [(a, usuarios[a.usuario_id]) for a in pendentes if pode_decidir(sessao, autor, a, cgp) and a.usuario_id in usuarios]


def papeis(sessao: Session, usuario: Usuario) -> dict[str, bool]:
    return {"cgp": eh_cgp(sessao, usuario), "autorizador": eh_autorizador(sessao, usuario)}


# --- Exportação ---------------------------------------------------------------------------------

def exportar(sessao: Session, autor: Usuario, formato: str, visao: str, ano: int, mes: int | None, pessoa_id: int | None,
             setor_id: int | None, tipo: str | None) -> tuple[bytes, str, str]:
    """Calendário filtrado em PDF (paisagem) ou XLSX (lista de períodos + grade por dia)."""
    dados = painel(sessao, autor, visao, ano, mes, pessoa_id, setor_id, tipo)
    inicio, fim = dados["inicio"], dados["fim"]
    titulo = f"Férias e licença-prêmio · {'ano de ' + str(ano) if visao == 'anual' else f'{mes:02d}/{ano}'}"
    linhas = [
        [_nome(u), setor_do_usuario(u) if u else "—", "Férias" if a.tipo == "ferias" else "Licença-prêmio", a.inicio, a.fim, a.dias,
         ROTULOS_STATUS[a.status]]
        for a, u, _ in dados["periodos"]
    ]
    sufixo = f"{ano}" if visao == "anual" else f"{ano}-{mes:02d}"
    if formato == "xlsx":
        from app.services.documentos.planilha import Aba, Coluna, gerar_planilha

        dias = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
        grade = []
        for a, u, _ in dados["periodos"]:
            marca = SIGLAS_TIPO[a.tipo] + ("" if a.status in ("aprovado", "gozado") else "?")
            grade.append([f"{_nome(u)} – {setor_do_usuario(u) if u else '—'}"] + [marca if a.inicio <= d <= a.fim else "" for d in dias])
        conteudo = gerar_planilha([
            Aba("Períodos", [Coluna("Nome", largura=34), Coluna("Setor", largura=40), Coluna("Tipo", largura=16), Coluna("Início", "DD/MM/YYYY", 12),
                             Coluna("Fim", "DD/MM/YYYY", 12), Coluna("Dias", "0", 8), Coluna("Status", largura=12)],
                linhas, titulo=titulo),
            Aba("Calendário", [Coluna("Pessoa – Setor", largura=46)] + [Coluna(d.strftime("%d/%m"), largura=6) for d in dias], grade,
                titulo=titulo, observacoes=["F = férias, LP = licença-prêmio; com '?' = aguardando aprovação."]),
        ])
        return conteudo, f"ferias-licencas-{sufixo}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    from app.services.documentos.pdf import DocumentoPdf

    documento = DocumentoPdf("Férias e licença-prêmio", titulo, paisagem=True, autor=_nome(autor))
    documento.secao(f"Períodos ({len(linhas)})").tabela(
        ["Nome", "Setor", "Tipo", "Início", "Fim", "Dias", "Status"],
        [[l[0], l[1], l[2], _data(l[3]), _data(l[4]), str(l[5]), l[6]] for l in linhas],
        larguras=[3.2, 4.4, 1.5, 1.2, 1.2, 0.7, 1.2], alinhar_direita=[5],
    )
    if dados["alertas"]:
        documento.secao("Alertas de setor").tabela(
            ["Setor", "De", "Até", "Pessoas afastadas"],
            [[x["setor"], _data(x["inicio"]), _data(x["fim"]), str(x["pessoas"])] for x in dados["alertas"]],
            larguras=[6, 1.5, 1.5, 2], alinhar_direita=[3],
        )
    return documento.gerar(), f"ferias-licencas-{sufixo}.pdf", "application/pdf"


__all__ = ["ErroAfastamento"]
