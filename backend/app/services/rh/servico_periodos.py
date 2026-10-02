# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular os períodos aquisitivos de férias, o saldo de cada um, a expiração e os avisos.
"""Períodos aquisitivos de férias.

- A CGP informa, para cada pessoa, o **início do período aquisitivo** só como dia e mês (dd/mm).
- Cada período dura 12 meses: começa no dd/mm e termina na véspera do mesmo dd/mm do ano seguinte
  (29/02 vira 28/02 nos anos comuns). No início de cada período são creditados `dias_ferias_por_periodo`
  (parâmetro, padrão 30) e o saldo não usado do período anterior **expira**.
- As férias debitam o saldo do período em que **começam**. Dá para agendar no período vigente ou no próximo.
- Cada período é a **janela de gozo de um exercício**: os 30 dias entram no início dela e podem ser agendados e usufruídos
  dentro dela (ver `exercicio_do_periodo`).
- **Aviso de expiração** (e-mail oficial à pessoa, ao autorizador/substituto e à CGP), enquanto houver saldo
  não agendado:
  - data-limite para começar = fim do período − saldo não agendado + 1 (para caber todo o saldo);
  - data-limite para pedir = data-limite para começar − antecedência mínima de agendamento;
  - 1º aviso = data-limite para pedir − folga (parâmetro, padrão 15). Ou seja, com antecedência de
    saldo + antecedência mínima + folga em relação ao fim do período;
  - lembrete 7 dias antes da data-limite para pedir e último aviso na própria data-limite.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import Afastamento, DadosFuncionais, ParametrosRh, PeriodoAquisitivo
from app.models.usuario import Usuario
from app.services import servico_mensagens

ATIVOS = ("pendente", "aprovado", "gozado")
DIAS_LEMBRETE = 7


def aniversario(ano: int, dia: int, mes: int) -> date:
    """dd/mm no ano informado (29/02 vira 28/02 nos anos comuns)."""
    try:
        return date(ano, mes, dia)
    except ValueError:
        return date(ano, mes, dia - 1)


def limites(dia_inicio: int, mes_inicio: int, referencia: date) -> tuple[date, date]:
    """(início, fim) do período aquisitivo que contém a data de referência."""
    inicio = aniversario(referencia.year, dia_inicio, mes_inicio)
    if inicio > referencia:
        inicio = aniversario(referencia.year - 1, dia_inicio, mes_inicio)
    fim = aniversario(inicio.year + 1, dia_inicio, mes_inicio) - timedelta(days=1)
    return inicio, fim


def exercicio_do_periodo(inicio: date, fim: date) -> int:
    """Exercício da janela de gozo: o ano em que cai a maior parte dos seus 12 meses.

    Janela 01/01/2027 a 31/12/2027 → 2027; 31/12/2026 a 30/12/2027 → 2027; 15/03/2027 a 14/03/2028 → 2027.
    Os 30 dias creditados no início da janela podem ser agendados e usufruídos dentro dela; o que sobra expira no fim.
    """
    return (inicio + (fim - inicio) / 2).year


def texto_inicio(dados: DadosFuncionais | None) -> str | None:
    """Início do período aquisitivo como "DD/MM" (ou None)."""
    if not dados or not dados.inicio_aquisitivo_dia:
        return None
    return f"{dados.inicio_aquisitivo_dia:02d}/{dados.inicio_aquisitivo_mes:02d}"


def ler_inicio(texto: str | None) -> tuple[int | None, int | None]:
    """"15/03" → (15, 3); vazio → (None, None). Lança ValueError se não for um dd/mm válido."""
    texto = (texto or "").strip()
    if not texto:
        return None, None
    partes = texto.split("/")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        raise ValueError("Informe o início do período aquisitivo no formato dd/mm (ex.: 15/03).")
    dia, mes = int(partes[0]), int(partes[1])
    try:
        date(2024, mes, dia)  # 2024 é bissexto: aceita 29/02
    except ValueError as erro:
        raise ValueError("Início do período aquisitivo inválido: confira o dia e o mês.") from erro
    return dia, mes


def _parametros(sessao: Session) -> ParametrosRh:
    from app.services.rh.servico_afastamentos import parametros

    return parametros(sessao)


def obter(sessao: Session, usuario_id: int, inicio: date, fim: date, criar: bool = True) -> PeriodoAquisitivo | None:
    """Período (usuário, início); criado com os dias do parâmetro se ainda não existir."""
    periodo = sessao.scalar(select(PeriodoAquisitivo).where(PeriodoAquisitivo.usuario_id == usuario_id, PeriodoAquisitivo.inicio == inicio))
    if periodo is None and criar:
        periodo = PeriodoAquisitivo(usuario_id=usuario_id, inicio=inicio, fim=fim, dias_creditados=_parametros(sessao).dias_ferias_por_periodo,
                                    origem="automatico", criado_em=agora_utc())
        sessao.add(periodo)
        sessao.flush()
    return periodo


def vigente(sessao: Session, usuario_id: int, referencia: date, criar: bool = True) -> PeriodoAquisitivo | None:
    """Período aquisitivo vigente na data (None se a CGP ainda não informou o início)."""
    dados = sessao.get(DadosFuncionais, usuario_id)
    if not dados or not dados.inicio_aquisitivo_dia:
        return None
    inicio, fim = limites(dados.inicio_aquisitivo_dia, dados.inicio_aquisitivo_mes, referencia)
    return obter(sessao, usuario_id, inicio, fim, criar)


def usado(sessao: Session, usuario_id: int, inicio: date, fim: date, ignorar: list = ()) -> int:
    """Dias de férias (pendentes, aprovadas e gozadas) que começam no período."""
    consulta = select(func.coalesce(func.sum(Afastamento.dias), 0)).where(
        Afastamento.usuario_id == usuario_id, Afastamento.tipo == "ferias", Afastamento.status.in_(ATIVOS),
        Afastamento.inicio >= inicio, Afastamento.inicio <= fim,
    )
    if ignorar:
        consulta = consulta.where(Afastamento.id.not_in(list(ignorar)))
    return int(sessao.scalar(consulta) or 0)


@dataclass
class SituacaoPeriodo:
    periodo: PeriodoAquisitivo
    usado: int
    disponivel: int
    data_limite_inicio: date | None
    data_limite_pedido: date | None
    data_aviso: date | None
    expira_em_dias: int
    em_alerta: bool


def situacao(sessao: Session, periodo: PeriodoAquisitivo, referencia: date) -> SituacaoPeriodo:
    """Saldo e datas do aviso de expiração do período."""
    p = _parametros(sessao)
    gasto = usado(sessao, periodo.usuario_id, periodo.inicio, periodo.fim)
    disponivel = max(periodo.dias_creditados - gasto, 0)
    limite_inicio = limite_pedido = aviso = None
    if disponivel > 0:
        limite_inicio = periodo.fim - timedelta(days=disponivel - 1)
        limite_pedido = limite_inicio - timedelta(days=p.antecedencia_minima_dias)
        aviso = limite_pedido - timedelta(days=p.folga_aviso_ferias_dias)
    return SituacaoPeriodo(
        periodo=periodo, usado=gasto, disponivel=disponivel, data_limite_inicio=limite_inicio, data_limite_pedido=limite_pedido,
        data_aviso=aviso, expira_em_dias=(periodo.fim - referencia).days + 1,
        em_alerta=bool(aviso and aviso <= referencia <= periodo.fim),
    )


# --- Tarefa diária ------------------------------------------------------------------------------

def _data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _nome(u: Usuario) -> str:
    return u.nome_completo or u.login


def _destinatarios(sessao: Session, usuario_id: int, referencia: date) -> list[int]:
    from app.services.rh.papeis import aprovadores_de, usuarios_cgp

    return list({usuario_id, *aprovadores_de(sessao, usuario_id, referencia), *(u.id for u in usuarios_cgp(sessao))})


def _expirar_anteriores(sessao: Session, usuario_id: int, referencia: date) -> int:
    """Registra a expiração dos períodos já encerrados (saldo não usado)."""
    expirados = 0
    for periodo in sessao.scalars(select(PeriodoAquisitivo).where(
        PeriodoAquisitivo.usuario_id == usuario_id, PeriodoAquisitivo.fim < referencia, PeriodoAquisitivo.expirado_em.is_(None),
    )):
        periodo.dias_expirados = max(periodo.dias_creditados - usado(sessao, usuario_id, periodo.inicio, periodo.fim), 0)
        periodo.expirado_em = agora_utc()
        expirados += 1
    return expirados


def processar(sessao: Session, referencia: date) -> dict[str, int]:
    """Cria os períodos que começaram, registra as expirações e envia os avisos (idempotente pelas chaves)."""
    p = _parametros(sessao)
    resultado = {"creditos": 0, "expiracoes": 0, "avisos": 0}
    pessoas = sessao.execute(select(DadosFuncionais, Usuario).join(Usuario, Usuario.id == DadosFuncionais.usuario_id).where(
        DadosFuncionais.inicio_aquisitivo_dia.is_not(None), Usuario.ativo.is_(True),
    )).all()
    for dados, usuario in pessoas:
        inicio, fim = limites(dados.inicio_aquisitivo_dia, dados.inicio_aquisitivo_mes, referencia)
        existia = obter(sessao, usuario.id, inicio, fim, criar=False) is not None
        periodo = obter(sessao, usuario.id, inicio, fim)
        resultado["expiracoes"] += _expirar_anteriores(sessao, usuario.id, referencia)
        # Crédito do novo período (só avisa se ele começou há pouco: evita e-mails em massa na primeira execução)
        if not existia and (referencia - inicio).days <= 7:
            if servico_mensagens.notificar(
                sessao, [usuario.id], f"Novo período aquisitivo: {periodo.dias_creditados} dias de férias disponíveis",
                f"Começou o seu período aquisitivo de {_data(periodo.inicio)} a {_data(periodo.fim)}, com {periodo.dias_creditados} dias de férias. "
                f"O saldo que não for usado até {_data(periodo.fim)} expira no início do período seguinte.",
                chave=f"ferias-periodo:{usuario.id}:{periodo.inicio:%Y%m%d}:credito", categoria="comunicado", link="/rh/ferias", email=True,
            ):
                resultado["creditos"] += 1
        if not p.aviso_ferias_ativo:
            continue
        s = situacao(sessao, periodo, referencia)
        if not s.data_aviso or referencia > periodo.fim:
            continue
        # O marco mais recente já alcançado (um e-mail por marco; na primeira execução, só o mais recente)
        marcos = [("inicial", s.data_aviso), ("lembrete", s.data_limite_pedido - timedelta(days=DIAS_LEMBRETE)), ("ultimo", s.data_limite_pedido)]
        alcancados = [(nome, data_marco) for nome, data_marco in marcos if data_marco <= referencia]
        if not alcancados:
            continue
        marco, _ = max(alcancados, key=lambda m: m[1])
        titulos = {
            "inicial": f"Férias a vencer: {_nome(usuario)} tem {s.disponivel} dia(s) até {_data(periodo.fim)}",
            "lembrete": f"Lembrete: {_nome(usuario)} precisa agendar {s.disponivel} dia(s) de férias",
            "ultimo": f"Último dia para pedir férias sem perder dias: {_nome(usuario)}",
        }
        if servico_mensagens.notificar(
            sessao, _destinatarios(sessao, usuario.id, referencia), titulos[marco],
            f"O período aquisitivo de {_nome(usuario)} vai de {_data(periodo.inicio)} a {_data(periodo.fim)}. "
            f"Ainda há {s.disponivel} dia(s) de férias não agendados, que expiram em {_data(periodo.fim + timedelta(days=1))}, "
            "no início do próximo período aquisitivo.\n\n"
            f"Para usar todo o saldo, as férias precisam começar até {_data(s.data_limite_inicio)}; com a antecedência mínima de "
            f"{p.antecedencia_minima_dias} dias, o pedido deve ser feito até {_data(s.data_limite_pedido)}.\n\n"
            "Agende as férias no SGI SPI (RH → Férias e LP).",
            chave=f"ferias-periodo:{usuario.id}:{periodo.inicio:%Y%m%d}:{marco}", categoria="prazo",
            prioridade="critica" if marco == "ultimo" else "alta", link="/rh/ferias", email=True,
        ):
            resultado["avisos"] += 1
    sessao.commit()
    return resultado


def a_vencer(sessao: Session, ids: list[int] | None, referencia: date, dentro_de: int = 90) -> list[tuple[Usuario, SituacaoPeriodo]]:
    """Pessoas com saldo não agendado e período terminando em até `dentro_de` dias (painel "Férias a vencer")."""
    consulta = select(DadosFuncionais, Usuario).join(Usuario, Usuario.id == DadosFuncionais.usuario_id).where(
        DadosFuncionais.inicio_aquisitivo_dia.is_not(None), Usuario.ativo.is_(True))
    if ids is not None:
        consulta = consulta.where(Usuario.id.in_(ids))
    lista = []
    for dados, usuario in sessao.execute(consulta).all():
        inicio, fim = limites(dados.inicio_aquisitivo_dia, dados.inicio_aquisitivo_mes, referencia)
        if (fim - referencia).days > dentro_de:
            continue
        s = situacao(sessao, obter(sessao, usuario.id, inicio, fim), referencia)
        if s.disponivel > 0:
            lista.append((usuario, s))
    return sorted(lista, key=lambda x: x[1].data_limite_pedido or x[1].periodo.fim)
