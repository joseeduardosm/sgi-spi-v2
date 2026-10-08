# Criado por José Eduardo Santana Martins
# Este arquivo serve para executar as tarefas agendadas da mensageria (fila de e-mails e lembretes diários).
"""Tarefas agendadas da mensageria.

Uso (pelos timers do systemd, ou à mão para testar):
    backend/.venv/bin/python -m app.tarefas.mensageria emails      # a cada 2 minutos
    backend/.venv/bin/python -m app.tarefas.mensageria lembretes   # todo dia às 07:00

- **emails:** gera os avisos das notícias agendadas que acabaram de aparecer no portal e envia por e-mail os avisos
  automáticos marcados para e-mail (ex.: designação na equipe,
  vencimento), entregues nos últimos 2 dias e ainda não enviados. As mensagens avulsas saem na hora.
- **lembretes:** gera na caixa (e por e-mail) os avisos de vencimento do contrato (90, 60 e 30 dias),
  de competência com medição atrasada e o lembrete de ciência pendente. No Módulo RH, marca como gozados os afastamentos aprovados que terminaram
  e lembra o aprovador de pedidos parados há 3 dias. Tudo idempotente: rodar de novo no mesmo dia não repete avisos.
"""

import logging
import sys
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FabricaSessao, agora_utc
from app.models.auditoria import RegistroAuditoria
from app.models.contratos import Competencia, Contrato
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.usuario import Usuario
from app.services import servico_mensagens, servico_smtp
from app.services.contratos.servico_competencias import anterior_ao_corte
from app.services.cliente_smtp import Mensagem as EmailSmtp
from app.services.servico_auditoria import auditar
from app.services.servico_smtp import SemServidorAtivo

log = logging.getLogger("sgi_spi.mensageria")

MARCOS_VENCIMENTO = (30, 60, 90)
DIAS_ATRASO = 30
DIAS_LEMBRETE_CIENCIA = 3


def enviar_emails_pendentes(sessao: Session) -> int:
    """Fila: avisos automáticos com e-mail ainda não enviado (entregues nos últimos 2 dias)."""
    limite = agora_utc() - timedelta(days=2)
    entregas = list(sessao.scalars(
        select(EntregaMensagem).join(Mensagem)
        .where(Mensagem.origem == "automatica", Mensagem.enviar_email.is_(True), EntregaMensagem.email_enviado_em.is_(None),
               EntregaMensagem.entregue_em >= limite)
        .options(selectinload(EntregaMensagem.mensagem))
    ))
    for entrega in entregas:
        servico_mensagens.enviar_email_da_entrega(sessao, entrega)
    sessao.commit()
    return len(entregas)


def _avisar_vencimentos(sessao: Session, contratos: list[Contrato], dia: date) -> int:
    from app.services.contratos import avisos
    from app.services.contratos.servico_contratos import situacao

    gerados = 0
    for contrato in contratos:
        if situacao(contrato) not in ("ativo", "a_vencer"):
            continue
        dias = (contrato.data_fim - dia).days
        marco = next((m for m in MARCOS_VENCIMENTO if dias <= m), None)
        if marco is None or dias < 0:
            continue
        mensagem = servico_mensagens.notificar(
            sessao, avisos.ids_da_equipe(contrato),
            f"Contrato {contrato.numero} vence em {dias} dia(s) ({contrato.data_fim:%d/%m/%Y})",
            f"A vigência atual do contrato {contrato.numero}" + (f" – {contrato.apelido}" if contrato.apelido else "")
            + f" termina em {contrato.data_fim:%d/%m/%Y}. Verifique a prorrogação ou a nova contratação.",
            # A data de fim entra na chave: depois de uma prorrogação, os marcos valem de novo
            chave=f"vencimento:{contrato.id}:{contrato.data_fim:%Y%m%d}:{marco}", categoria="prazo",
            prioridade="alta" if marco == 30 else "normal", link=f"/contratos/{contrato.id}/prorrogacao", contrato_id=contrato.id, email=True,
        )
        gerados += bool(mensagem)
    return gerados


def _avisar_atrasos(sessao: Session, contratos: list[Contrato], dia: date) -> int:
    from app.services.contratos import avisos

    gerados = 0
    for contrato in contratos:
        for competencia in contrato.competencias:
            if competencia.tipo != "regular" or competencia.medicao_concluida_em is not None or anterior_ao_corte(competencia):
                continue
            if (dia - competencia.periodo_fim).days <= DIAS_ATRASO:
                continue
            mensagem = servico_mensagens.notificar(
                sessao, avisos.ids_da_equipe(contrato),
                f"Contrato {contrato.numero}: medição de {competencia.numero_competencia} atrasada",
                f"O período da competência {competencia.numero_competencia} terminou em {competencia.periodo_fim:%d/%m/%Y} "
                f"e a medição ainda não foi concluída.",
                chave=f"atraso:{competencia.id}", categoria="pendencia", prioridade="alta",
                link=f"/contratos/{contrato.id}/execucao/{competencia.identificador}", contrato_id=contrato.id, email=True,
            )
            gerados += bool(mensagem)
    return gerados


def _email(sessao: Session, usuario: Usuario, assunto: str, paragrafos: list[str], link: str | None) -> bool:
    """Envia um e-mail simples ao usuário (sem e-mail no perfil ou sem SMTP: não envia)."""
    if not (usuario.email or "").strip():
        return False
    try:
        resultado = servico_smtp.enviar_email(sessao, EmailSmtp(
            para=[usuario.email.strip()], assunto=assunto, texto="\n\n".join(paragrafos),
            html=servico_mensagens.html_email(assunto, paragrafos, link, "Abrir a caixa de mensagens" if link == "/mensagens" else "Abrir no sistema"),
        ))
        return resultado.sucesso
    except SemServidorAtivo:
        return False


def _lembrar_ciencias(sessao: Session, dia: date) -> int:
    """Mensagens de prioridade alta/crítica sem ciência há exatamente 3 dias: um lembrete por e-mail."""
    entregas = sessao.scalars(
        select(EntregaMensagem).join(Mensagem)
        .where(Mensagem.prioridade.in_(("alta", "critica")), EntregaMensagem.ciente_em.is_(None), EntregaMensagem.encerrada_em.is_(None))
        .options(selectinload(EntregaMensagem.mensagem))
    )
    enviados = 0
    for entrega in entregas:
        if entrega.entregue_em.date() != dia - timedelta(days=DIAS_LEMBRETE_CIENCIA):
            continue
        usuario = sessao.get(Usuario, entrega.destinatario_id)
        if usuario and usuario.ativo and _email(sessao, usuario, f"Lembrete: {entrega.assunto_copia}",
                                                [entrega.corpo_copia, "Esta mensagem ainda aguarda sua ciência na caixa de mensagens."],
                                                entrega.mensagem.link or "/mensagens"):
            enviados += 1
    return enviados


def gerar_lembretes(sessao: Session, dia: date | None = None) -> dict[str, int]:
    """Lembretes do dia. `dia` padrão: hoje em São Paulo."""
    from app.services.contratos.servico_contratos import hoje

    dia = dia or hoje()
    contratos = list(sessao.scalars(select(Contrato).options(
        selectinload(Contrato.equipe), selectinload(Contrato.competencias).selectinload(Competencia.itens),
    )))
    resultado = {"vencimentos": _avisar_vencimentos(sessao, contratos, dia), "atrasos": _avisar_atrasos(sessao, contratos, dia)}
    sessao.commit()
    resultado["emails_avisos"] = enviar_emails_pendentes(sessao)
    resultado["lembretes_ciencia"] = _lembrar_ciencias(sessao, dia)
    # Módulo RH: afastamentos aprovados que terminaram viram "gozado"; pedidos parados há 3 dias geram lembrete
    from app.services.rh import servico_afastamentos

    resultado["rh_gozados"] = servico_afastamentos.marcar_gozados(sessao, dia)
    # Férias: novos períodos aquisitivos (crédito), expirações e avisos de saldo prestes a expirar
    from app.services.rh import servico_periodos

    resultado["rh_periodos"] = servico_periodos.processar(sessao, dia)
    resultado["rh_lembretes"] = servico_afastamentos.lembrar_pendentes(sessao, dia)
    resultado["rh_boas_vindas"] = servico_afastamentos.dar_boas_vindas(sessao, dia)
    # Virada das competências dos contratos: cria as tarefas de cada etapa e corrige as que divergem do módulo Contratos
    from app.services.contratos import servico_tarefas_contratos

    virada = servico_tarefas_contratos.sincronizar_todas(sessao, dia)
    resultado["contratos_tarefas_criadas"], resultado["contratos_tarefas_atualizadas"] = virada.criadas, virada.atualizadas
    resultado["contratos_tarefas_erros"] = len(virada.erros)
    # Módulo Tarefas: vence amanhã, atrasadas e validação parada há 2+ dias
    from app.services.tarefas import servico_tarefas

    resultado["tarefas"] = servico_tarefas.lembrar(sessao, dia)
    # Tarefas recorrentes: cria as ocorrências cuja data chegou
    from app.services.tarefas import servico_recorrencias

    resultado["tarefas_recorrentes"] = servico_recorrencias.gerar_ocorrencias(sessao, dia)
    # Atividades agendadas das tarefas: as de hoje e as atrasadas
    from app.services.tarefas import servico_atividades

    resultado["tarefas_atividades"] = servico_atividades.lembrar(sessao, dia)
    # Status das equipes: lembrete semanal (segunda-feira) à liderança
    from app.services.tarefas import servico_marcos

    resultado["tarefas_lembrete_status"] = servico_marcos.lembrar(sessao, dia)
    # Protocolo: reservas sem documento há alguns dias
    from app.services import servico_protocolo

    resultado["protocolo"] = servico_protocolo.lembrar_reservas(sessao, dia)
    # Reserva de Espaços: lembrete um dia antes das reservas deferidas
    from app.services import servico_reserva_espacos

    resultado["reserva_espacos"] = servico_reserva_espacos.lembrar(sessao, dia)
    # Contratações: revisões e propostas sem resposta
    from app.services.contratacoes import conferencia

    resultado["contratacoes"] = conferencia.lembrar_revisoes_paradas(sessao, dia)
    resultado["emails_rh"] = enviar_emails_pendentes(sessao)
    sessao.commit()
    return resultado


def main(argumentos: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    comando = argumentos[0] if argumentos else ""
    with FabricaSessao() as sessao:
        if comando == "emails":
            # Notícias agendadas que acabaram de aparecer no portal: gera os avisos antes de enviar a fila de e-mails
            from app.services.noticias.servico_noticias import processar_publicacoes
            log.info("Avisos de notícias publicadas: %s", processar_publicacoes(sessao))
            log.info("E-mails de avisos enviados: %s", enviar_emails_pendentes(sessao))
        elif comando == "lembretes":
            log.info("Lembretes: %s", gerar_lembretes(sessao))
        else:
            print(__doc__)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
