# Criado por José Eduardo Santana Martins
# Este arquivo serve para as tarefas automáticas dos Chamados: estouro de prazo, geração dos recorrentes, vigia e painel de saúde.
"""Tarefas automáticas dos Chamados (rodadas pelos timers do systemd: `python -m app.tarefas.chamados minuto|vigia`).

- **minuto** (a cada minuto):
  - prazo de **atendimento** estourado (ninguém agiu a tempo): marca e avisa o setor responsável;
  - prazo de **solução** estourado (fora do pendente): marca, **sobe a prioridade para Urgente** (`prioridade_origem = sla`, decisão do
    usuário), registra na linha do tempo e avisa o responsável (ou o setor), também por e-mail;
  - gera os **recorrentes** devidos (um por ocorrência: a dupla recorrente + ocorrência é única no banco, rodar duas vezes não duplica).
- **vigia** (a cada 5 minutos): confere se a tarefa `minuto` está rodando e se a fila de e-mail anda. Se algo parou, avisa quem administra
  os Chamados **pelo sino** (que não depende do e-mail): no GLPI da SPI, a fila de e-mail ficou meses parada sem ninguém saber.

`saude()` monta o painel de saúde na hora da leitura: mesmo com o agendador parado, a tela mostra o problema.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO, agora_utc
from app.models.acl import NivelAcl
from app.models.chamados import (
    STATUS_ABERTOS, STATUS_PENDENTE, STATUS_SOLUCIONADO, AcompanhamentoChamado, Chamado, ExecucaoChamados, RecorrenteChamados,
)
from app.models.notificacao import EntregaNotificacao
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services import notificacoes, servico_acl
from app.services.chamados import configuracao, parametros
from app.services.chamados.acesso import Papeis
from app.services.chamados.servico import DadosAbertura, ErroChamado, _avisar, abrir, membros_ativos

log = logging.getLogger("sgi_spi.chamados")

TAREFAS = ("minuto", "vigia")
# A tarefa "minuto" sem rodar há mais que isto é problema
ATRASO_MINUTO = timedelta(minutes=10)
# Rodada "rodando" há mais que isto morreu no meio (ex.: o banco reiniciou)
RODADA_MORTA = timedelta(minutes=15)
# E-mail que devia ter saído e ainda espera há mais que isto
EMAIL_PARADO = timedelta(minutes=30)
# Tudo pode gerar no máximo isto de chamados recorrentes numa rodada (proteção contra um cadastro errado)
MAXIMO_RECORRENTES_POR_RODADA = 200


def _utc(instante: datetime | None) -> datetime | None:
    from datetime import UTC

    return None if instante is None else instante if instante.tzinfo else instante.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------------------------
# Prazos
# ---------------------------------------------------------------------------------------------

def verificar_prazos(sessao: Session, agora: datetime | None = None) -> tuple[int, int]:
    """Marca os prazos estourados e devolve (atendimento, solução) marcados nesta rodada. Sem commit.
    Os avisos saem sem autor (é o sistema): o `notificar` só usa o autor para não avisar quem fez a ação."""
    agora = agora or agora_utc()
    base = select(Chamado).where(Chamado.excluido_em.is_(None), Chamado.importado.is_(False), Chamado.status_base != STATUS_SOLUCIONADO)
    tto = list(sessao.scalars(base.where(Chamado.prazo_tto.is_not(None), Chamado.prazo_tto < agora, Chamado.tomado_em.is_(None),
                                          Chamado.tto_estourado_em.is_(None))))
    for c in tto:
        c.tto_estourado_em = agora
        _avisar(sessao, membros_ativos(sessao, c.setor_id), f"Chamado #{c.numero} sem atendimento no prazo",
                f"Ninguém agiu no chamado \"{c.titulo}\" dentro do prazo de atendimento.", c, "sla:tto", "chamados.sla_estourado", None)
    ttr = list(sessao.scalars(base.where(Chamado.prazo_ttr.is_not(None), Chamado.prazo_ttr < agora, Chamado.ttr_estourado_em.is_(None),
                                          Chamado.status_base != STATUS_PENDENTE)))
    for c in ttr:
        c.ttr_estourado_em = agora
        anterior = c.prioridade
        c.prioridade, c.prioridade_origem = "urgente", "sla"
        c.versao += 1
        c.acompanhamentos.append(AcompanhamentoChamado(
            texto=f"Prazo de solução estourado: prioridade {anterior} → urgente (automático).", automatico=True, criado_em=agora))
        ids = [c.responsavel_id] if c.responsavel_id else membros_ativos(sessao, c.setor_id)
        _avisar(sessao, ids, f"Chamado #{c.numero} estourou o prazo e virou Urgente", f"O chamado \"{c.titulo}\" passou do prazo de solução.",
                c, f"sla:ttr:{c.reaberturas}", "chamados.sla_estourado", None, forcar_email=True, prioridade="alta")
    return len(tto), len(ttr)


# ---------------------------------------------------------------------------------------------
# Recorrentes
# ---------------------------------------------------------------------------------------------

def gerar_recorrentes(sessao: Session, agora: datetime | None = None) -> int:
    """Abre os chamados recorrentes cuja ocorrência (menos a antecedência) já chegou. Depois de uma parada longa, gera só a ocorrência
    devida mais recente e pula para a próxima futura (não abre uma enxurrada de chamados atrasados)."""
    agora = agora or agora_utc()
    feriados = parametros.feriados_do_sla(sessao)
    gerados = 0
    candidatos = list(sessao.scalars(select(RecorrenteChamados).where(RecorrenteChamados.ativo.is_(True)).order_by(RecorrenteChamados.proxima_em)))
    for item in candidatos:
        if gerados >= MAXIMO_RECORRENTES_POR_RODADA:
            break
        proxima = _utc(item.proxima_em)
        if proxima - timedelta(minutes=item.antecedencia_min) > agora:
            continue
        if item.fim_em is not None and proxima > _utc(item.fim_em):
            item.ativo = False
            continue
        # Pula as ocorrências que já passaram enquanto o agendador esteve parado, ficando com a mais recente
        while True:
            seguinte = configuracao.proxima_ocorrencia(item, proxima, feriados)
            if seguinte - timedelta(minutes=item.antecedencia_min) > agora:
                break
            item.proxima_em = proxima = seguinte
        if _gerar_um(sessao, item, proxima):
            gerados += 1
        item.ultima_geracao_em = agora
        item.proxima_em = configuracao.proxima_ocorrencia(item, proxima, feriados)
    return gerados


def _gerar_um(sessao: Session, item: RecorrenteChamados, ocorrencia: datetime) -> bool:
    solicitante = sessao.get(Usuario, item.solicitante_id)
    if solicitante is None or not solicitante.ativo:
        log.warning("Recorrente %s sem solicitante ativo: chamado não gerado", item.nome)
        return False
    ponto = sessao.begin_nested()
    try:
        chamado = abrir(sessao, solicitante, Papeis(True, True, True), DadosAbertura(
            titulo=item.titulo, descricao=item.descricao or item.titulo, categoria_id=item.categoria_id, tipo="requisicao"
            if not item.categoria.permite_incidente else "incidente"))
        chamado.recorrente_id, chamado.gerado_para = item.id, ocorrencia
        sessao.flush()
        ponto.commit()
        return True
    except (IntegrityError, ErroChamado) as erro:
        # Já gerado (outra rodada chegou antes) ou a categoria deixou de valer: não gera de novo nesta ocorrência
        ponto.rollback()
        log.warning("Recorrente %s: ocorrência %s não gerada (%s)", item.nome, ocorrencia, erro)
        return False


# ---------------------------------------------------------------------------------------------
# Execução, vigia e saúde
# ---------------------------------------------------------------------------------------------

def executar(sessao_fabrica: Callable[[], Session], tarefa: str, funcao: Callable[[Session], str]) -> bool:
    """Roda uma tarefa registrando a rodada (início, fim, resumo e erro) para o vigia e o painel de saúde."""
    with sessao_fabrica() as sessao:
        rodada = ExecucaoChamados(tarefa=tarefa)
        sessao.add(rodada)
        sessao.commit()
        rodada_id = rodada.id
    with sessao_fabrica() as sessao:
        try:
            resumo = funcao(sessao)
            sessao.commit()
            estado, erro = "ok", None
        except Exception as falha:  # noqa: BLE001 (registra qualquer falha para o painel de saúde)
            sessao.rollback()
            log.exception("Tarefa %s dos Chamados falhou", tarefa)
            resumo, estado, erro = "", "erro", f"{type(falha).__name__}: {falha}"[:2000]
    with sessao_fabrica() as sessao:
        rodada = sessao.get(ExecucaoChamados, rodada_id)
        rodada.terminada_em, rodada.estado, rodada.resumo, rodada.erro = agora_utc(), estado, (resumo or "")[:300], erro
        # Guarda só os últimos 30 dias de rodadas
        sessao.execute(ExecucaoChamados.__table__.delete().where(ExecucaoChamados.iniciada_em < agora_utc() - timedelta(days=30)))
        sessao.commit()
    return estado == "ok"


# Resumo diário do líder: a partir desta hora (São Paulo), uma vez por dia útil
parametros.PADROES["resumo_lider_hora"] = "7"
parametros.PADROES["resumo_lider_ultimo"] = ""


def resumo_diario_lideres(sessao: Session, agora: datetime | None = None) -> int:
    """No começo de cada dia útil, o líder de cada setor recebe por e-mail a lista dos chamados em aberto em que o setor é o responsável.

    Decisão do usuário, para não encher a caixa de ninguém: só um por dia, só em dia útil (fim de semana e feriado do RH não), e só
    para quem tem chamado aberto. Devolve quantos resumos saíram.
    """
    agora_sp = (agora or agora_utc()).astimezone(FUSO_SAO_PAULO)
    hoje = agora_sp.date()
    if agora_sp.weekday() >= 5 or hoje in parametros.feriados_do_sla(sessao) or agora_sp.hour < parametros.obter_inteiro(sessao, "resumo_lider_hora"):
        return 0
    if parametros.obter(sessao, "resumo_lider_ultimo") == hoje.isoformat():
        return 0
    enviados = 0
    apresentacao = configuracao.apresentacao(sessao)
    for setor in sessao.scalars(select(Setor).where(Setor.ativo.is_(True), Setor.lider_id.is_not(None)).order_by(Setor.nome)):
        abertos = list(sessao.scalars(select(Chamado).where(Chamado.setor_id == setor.id, Chamado.status_base.in_(STATUS_ABERTOS),
                                                            Chamado.excluido_em.is_(None), Chamado.importado.is_(False)).order_by(Chamado.aberto_em)))
        if not abertos:
            continue
        nomes = {u.id: (u.nome_completo or u.login) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_({c.responsavel_id for c in abertos if c.responsavel_id})))}
        estourados = sum(1 for c in abertos if c.ttr_estourado_em is not None)
        sem_responsavel = sum(1 for c in abertos if c.responsavel_id is None)
        linhas = [f"#{c.numero} · {c.titulo[:120]} · {apresentacao[c.status_base][0]} · "
                  f"{'prazo estourado' if c.ttr_estourado_em else 'no prazo'} · {nomes.get(c.responsavel_id, 'sem responsável')}" for c in abertos[:50]]
        if len(abertos) > 50:
            linhas.append(f"... e mais {len(abertos) - 50}. Veja todos na fila de atendimento.")
        corpo = (f"Bom dia! O setor {setor.nome} tem {len(abertos)} chamado(s) em aberto ({estourados} com prazo estourado, {sem_responsavel} sem responsável):\n\n"
                 + "\n".join(linhas))
        if notificacoes.notificar(sessao, [setor.lider_id], f"Chamados em aberto do {setor.nome}: {len(abertos)}", corpo,
                                  chave=f"chamados:resumo-lider:{hoje.isoformat()}:{setor.id}", categoria="atribuicao", link="/chamados/fila",
                                  evento="chamados.resumo_lider", forcar_email=True) is not None:
            enviados += 1
    parametros.gravar(sessao, "resumo_lider_ultimo", hoje.isoformat())
    sessao.flush()
    return enviados


def rodar_minuto(sessao: Session) -> str:
    tto, ttr = verificar_prazos(sessao)
    gerados = gerar_recorrentes(sessao)
    resumos = resumo_diario_lideres(sessao)
    return f"{tto} prazo(s) de atendimento e {ttr} de solução estourados; {gerados} recorrente(s) gerado(s); {resumos} resumo(s) a líderes"


@dataclass
class Saude:
    tarefas: list[dict] = field(default_factory=list)
    email_parados: int = 0
    email_falhas_24h: int = 0
    email_mais_antigo: datetime | None = None
    ultimo_erro_email: str | None = None
    problemas: list[str] = field(default_factory=list)


def saude(sessao: Session, agora: datetime | None = None) -> Saude:
    """Situação das tarefas automáticas e da fila de e-mail, calculada na hora (não depende do vigia ter rodado)."""
    agora = agora or agora_utc()
    s = Saude()
    for tarefa in TAREFAS:
        ultima = sessao.scalar(select(ExecucaoChamados).where(ExecucaoChamados.tarefa == tarefa).order_by(ExecucaoChamados.iniciada_em.desc()).limit(1))
        ultima_ok = sessao.scalar(select(func.max(ExecucaoChamados.terminada_em)).where(ExecucaoChamados.tarefa == tarefa, ExecucaoChamados.estado == "ok"))
        s.tarefas.append({"tarefa": tarefa, "ultima_em": ultima.iniciada_em if ultima else None, "ultimo_estado": ultima.estado if ultima else None,
                          "ultima_ok_em": ultima_ok, "ultimo_erro": ultima.erro if ultima and ultima.estado == "erro" else None,
                          "ultimo_resumo": ultima.resumo if ultima else ""})
    minuto = s.tarefas[0]
    if minuto["ultima_ok_em"] is None or _utc(minuto["ultima_ok_em"]) < agora - ATRASO_MINUTO:
        quando = f"desde {configuracao_data(minuto['ultima_ok_em'])}" if minuto["ultima_ok_em"] else "nunca rodaram"
        s.problemas.append(f"As tarefas automáticas dos Chamados (prazos e recorrentes) {'não rodam ' + quando if minuto['ultima_ok_em'] else quando}.")
    if minuto["ultimo_estado"] == "erro":
        s.problemas.append(f"A última rodada das tarefas automáticas falhou: {minuto['ultimo_erro']}")
    pendentes = select(EntregaNotificacao).where(EntregaNotificacao.canal_email.is_(True), EntregaNotificacao.email_resumo.is_(False),
                                                 EntregaNotificacao.email_enviado_em.is_(None), EntregaNotificacao.entregue_em < agora - EMAIL_PARADO)
    s.email_parados = sessao.scalar(select(func.count()).select_from(pendentes.subquery())) or 0
    s.email_mais_antigo = sessao.scalar(select(func.min(EntregaNotificacao.entregue_em)).where(
        EntregaNotificacao.canal_email.is_(True), EntregaNotificacao.email_resumo.is_(False), EntregaNotificacao.email_enviado_em.is_(None)))
    falhas = select(EntregaNotificacao).where(EntregaNotificacao.email_ok.is_(False), EntregaNotificacao.email_enviado_em >= agora - timedelta(hours=24))
    s.email_falhas_24h = sessao.scalar(select(func.count()).select_from(falhas.subquery())) or 0
    s.ultimo_erro_email = sessao.scalar(select(EntregaNotificacao.email_erro).where(EntregaNotificacao.email_ok.is_(False))
                                        .order_by(EntregaNotificacao.email_enviado_em.desc()).limit(1))
    if s.email_parados:
        s.problemas.append(f"{s.email_parados} e-mail(s) esperando há mais de {int(EMAIL_PARADO.total_seconds() // 60)} minutos: o envio pode ter parado.")
    if s.email_falhas_24h:
        s.problemas.append(f"{s.email_falhas_24h} e-mail(s) falharam nas últimas 24 horas. Último erro: {s.ultimo_erro_email or 'sem detalhe'}.")
    return s


def configuracao_data(valor: datetime | None) -> str:
    from app.core.banco import em_sao_paulo

    return em_sao_paulo(_utc(valor)).strftime("%d/%m/%Y %H:%M") if valor else ""


def vigiar(sessao: Session, agora: datetime | None = None) -> str:
    """Encerra rodadas mortas e avisa quem administra os Chamados, pelo sino, quando algo parou (no máximo um aviso por problema por dia)."""
    agora = agora or agora_utc()
    mortas = list(sessao.scalars(select(ExecucaoChamados).where(ExecucaoChamados.estado == "rodando",
                                                                ExecucaoChamados.iniciada_em < agora - RODADA_MORTA)))
    for rodada in mortas:
        rodada.estado, rodada.terminada_em, rodada.erro = "erro", agora, "Interrompida (ficou rodando tempo demais)."
    s = saude(sessao, agora)
    if s.problemas:
        administradores = servico_acl.usuarios_com_nivel(sessao, "chamados", NivelAcl.CONTROLE_TOTAL)
        administradores |= set(sessao.scalars(select(Usuario.id).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True))))
        dia = agora.strftime("%Y-%m-%d")
        for i, problema in enumerate(s.problemas):
            notificacoes.notificar(sessao, sorted(administradores), "Chamados: algo parou de funcionar", problema,
                                   chave=f"chamados:saude:{dia}:{i}:{problema[:40]}", categoria="pendencia", prioridade="alta",
                                   link="/chamados/parametros?aba=saude", evento="chamados.saude")
    return f"{len(mortas)} rodada(s) encerrada(s); {len(s.problemas)} problema(s)"

