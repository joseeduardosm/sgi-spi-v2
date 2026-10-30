# Criado por José Eduardo Santana Martins
# Este arquivo serve para enviar as notificações pelos canais externos (e-mail imediato, resumo por e-mail e navegador) depois do commit.
"""Despacho das Notificações pelos canais externos.

Fluxo:
1. `notificar()` grava a notificação, as entregas e os canais de cada destinatário (fotografia da preferência) e **registra o id** em
   `sessao.info` (o id nasce no Python, porque depois do commit não dá para consultar o banco "no escuro").
2. Quando a sessão dá **commit**, o listener `after_commit` inicia o despacho (em uma thread, na hora, ou nada, conforme
   `NOTIFICACOES_DESPACHO`); no **rollback** o registro é descartado e nada sai.
3. O timer `despachar` (a cada 2 minutos) é a rede de segurança: envia o que ficou pendente nos últimos 2 dias.
4. Cada envio é **reivindicado** com `UPDATE … WHERE x_enviado_em IS NULL` e conferência do `rowcount`: a thread e o timer nunca
   mandam em dobro, mesmo correndo ao mesmo tempo.

E-mail: com frequência "imediato" sai como antes; com "diário" ou "semanal" a entrega espera o resumo (`enviar_resumos`, no timer das 7h).
O "não perturbe" já foi aplicado na entrega (navegador e desktop ficam desligados); o e-mail não é afetado por ele.
"""

import logging
import threading
import uuid
from datetime import datetime, timedelta

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FUSO_SAO_PAULO, FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.notificacao_preferencias import ConfigNotificacaoUsuario
from app.models.usuario import Usuario
from app.services import modelo_email, servico_smtp
from app.services.cliente_smtp import SIMULADO, Mensagem as EmailSmtp
from app.services.notificacoes import layout_email, navegador, preferencias
from app.services.notificacoes.catalogo import EVENTOS, ROTULOS_MODULO
from app.services.servico_smtp import SemServidorAtivo

log = logging.getLogger("sgi_spi.notificacoes")

CHAVE_INFO = "notificacoes_a_despachar"
JANELA_PENDENTES = timedelta(days=2)
# Resumo: o que ficou sem sair há mais que isto é descartado do resumo (não faz sentido listar notificação de semanas atrás)
JANELA_RESUMO = timedelta(days=10)


def modo() -> str:
    """`thread`, `sincrono` ou `desligado` (os testes trocam esta função)."""
    return obter_configuracao().notificacoes_despacho


# --- Registro e disparo depois do commit -------------------------------------------------------------------------

def agendar(sessao: Session, notificacao_id: uuid.UUID) -> None:
    """Guarda o id para despachar quando (e se) a sessão der commit."""
    sessao.info.setdefault(CHAVE_INFO, set()).add(notificacao_id)


def _depois_do_commit(sessao: Session) -> None:
    ids = sessao.info.pop(CHAVE_INFO, None)
    if not ids or modo() == "desligado":
        return
    if modo() == "sincrono":
        despachar(ids)
    else:
        threading.Thread(target=despachar, args=(set(ids),), daemon=True, name="notificacoes-despacho").start()


def _depois_do_rollback(sessao: Session) -> None:
    sessao.info.pop(CHAVE_INFO, None)


event.listen(FabricaSessao, "after_commit", _depois_do_commit)
event.listen(FabricaSessao, "after_rollback", _depois_do_rollback)


# --- Reivindicação e envio ---------------------------------------------------------------------------------------

def _reivindicar(sessao: Session, entrega_id: uuid.UUID, coluna: str) -> bool:
    """Marca o envio como "meu" (só uma execução consegue). Faz commit."""
    resultado = sessao.execute(update(EntregaNotificacao).where(EntregaNotificacao.id == entrega_id, getattr(EntregaNotificacao, coluna).is_(None)).values({coluna: agora_utc()}))
    sessao.commit()
    return resultado.rowcount == 1


def _enviar_smtp(sessao: Session, usuario: Usuario | None, assunto: str, texto: str, html: str) -> tuple[bool, str | None]:
    """Envia pelo servidor SMTP ativo. Devolve (ok, erro)."""
    if usuario is None or not (usuario.email or "").strip():
        return False, "Destinatário sem e-mail cadastrado no perfil."
    try:
        resultado = servico_smtp.enviar_email(sessao, EmailSmtp(para=[usuario.email.strip()], assunto=assunto, texto=texto, html=html))
        # Homologação: conta como enviado e guarda a nota de simulação no lugar do erro (fica visível no histórico de envios)
        if resultado.simulado:
            return True, resultado.mensagem
        return resultado.sucesso, None if resultado.sucesso else resultado.mensagem
    except SemServidorAtivo as erro:
        return False, str(erro)


def _entrega(sessao: Session, entrega_id: uuid.UUID) -> EntregaNotificacao:
    return sessao.scalar(select(EntregaNotificacao).where(EntregaNotificacao.id == entrega_id).options(selectinload(EntregaNotificacao.notificacao)))


def _email_da_entrega(sessao: Session, entrega: EntregaNotificacao, prefixo_assunto: str = "") -> tuple[bool, str | None]:
    usuario = sessao.get(Usuario, entrega.destinatario_id)
    n = entrega.notificacao
    texto = f"{modelo_email.corpo_texto(entrega.corpo_copia)}\n\nEnviada por {n.autor_nome}.\n{layout_email.url_completa(n.link)}"
    html = layout_email.html_mensagem(entrega.assunto_copia, entrega.corpo_copia, n.autor_nome, n.link)
    return _enviar_smtp(sessao, usuario, f"{prefixo_assunto}{entrega.assunto_copia}", texto, html)


def enviar_email_imediato(sessao: Session, entrega_id: uuid.UUID) -> bool:
    """E-mail imediato da entrega (se ainda ninguém o enviou). Devolve se esta chamada enviou."""
    if not _reivindicar(sessao, entrega_id, "email_enviado_em"):
        return False
    entrega = _entrega(sessao, entrega_id)
    entrega.email_ok, entrega.email_erro = _email_da_entrega(sessao, entrega)
    sessao.commit()
    return True


def enviar_navegador(sessao: Session, entrega_id: uuid.UUID) -> bool:
    """Pop-up do navegador da entrega (se ainda ninguém o enviou). Devolve se esta chamada tentou o envio."""
    if not _reivindicar(sessao, entrega_id, "navegador_enviado_em"):
        return False
    entrega = _entrega(sessao, entrega_id)
    n = entrega.notificacao
    if obter_configuracao().modo_homologacao:
        # Homologação: o pop-up não é enviado, mas fica registrado como enviado (simulação)
        entrega.navegador_ok, entrega.navegador_erro = True, f"{SIMULADO} pop-up do navegador não enviado."
        sessao.commit()
        return True
    dados = navegador.montar_payload(entrega.id, entrega.assunto_copia, modelo_email.corpo_texto(entrega.corpo_copia), n.link)
    enviados, erro = navegador.enviar(sessao, entrega.destinatario_id, dados)
    entrega.navegador_ok, entrega.navegador_erro = enviados > 0, erro
    sessao.commit()
    return True


def despachar(notificacoes_ids: set[uuid.UUID] | list[uuid.UUID]) -> int:
    """Envia as entregas das notificações informadas (e-mail imediato e navegador). Nunca levanta: erro vai para o log."""
    enviados = 0
    try:
        with FabricaSessao() as sessao:
            ids = [e for e in sessao.scalars(select(EntregaNotificacao.id).where(EntregaNotificacao.notificacao_id.in_(list(notificacoes_ids))))]
            for entrega_id in ids:
                enviados += _despachar_entrega(sessao, entrega_id)
    except Exception:  # noqa: BLE001 - o despacho roda fora da requisição: falhar aqui não pode derrubar quem gravou
        log.exception("Falha ao despachar notificações %s", notificacoes_ids)
    return enviados


def _despachar_entrega(sessao: Session, entrega_id: uuid.UUID) -> int:
    entrega = sessao.get(EntregaNotificacao, entrega_id)
    if entrega is None:
        return 0
    feitos = 0
    try:
        if entrega.canal_email and not entrega.email_resumo and entrega.email_enviado_em is None:
            feitos += enviar_email_imediato(sessao, entrega_id)
        if entrega.canal_navegador and entrega.navegador_enviado_em is None:
            feitos += enviar_navegador(sessao, entrega_id)
    except Exception:  # noqa: BLE001
        sessao.rollback()
        log.exception("Falha ao enviar a entrega %s", entrega_id)
    return feitos


def despachar_pendentes(sessao: Session) -> int:
    """Rede de segurança (timer a cada 2 minutos): envia o que ficou pendente nos últimos 2 dias. Devolve quantos envios fez."""
    limite = agora_utc() - JANELA_PENDENTES
    ids = list(sessao.scalars(
        select(EntregaNotificacao.id).where(
            EntregaNotificacao.entregue_em >= limite,
            ((EntregaNotificacao.canal_email.is_(True)) & (EntregaNotificacao.email_resumo.is_(False)) & (EntregaNotificacao.email_enviado_em.is_(None)))
            | ((EntregaNotificacao.canal_navegador.is_(True)) & (EntregaNotificacao.navegador_enviado_em.is_(None))),
        )
    ))
    return sum(_despachar_entrega(sessao, i) for i in ids)


# --- Resumo por e-mail -------------------------------------------------------------------------------------------

def enviar_resumos(sessao: Session, agora: datetime | None = None) -> int:
    """Resumo diário (todo dia) e semanal (segunda-feira), um e-mail por pessoa, agrupado por módulo. Sem nada pendente, não envia.

    Quem voltou para "imediato" com entregas ainda esperando o resumo recebe junto com o resumo diário. Devolve quantos e-mails saíram.
    """
    agora = agora or agora_utc()
    local = agora.astimezone(FUSO_SAO_PAULO)
    limite = agora - JANELA_RESUMO
    pendentes = list(sessao.scalars(
        select(EntregaNotificacao).where(
            EntregaNotificacao.canal_email.is_(True), EntregaNotificacao.email_resumo.is_(True), EntregaNotificacao.email_enviado_em.is_(None),
            EntregaNotificacao.entregue_em >= limite,
        ).options(selectinload(EntregaNotificacao.notificacao)).order_by(EntregaNotificacao.entregue_em)
    ))
    por_usuario: dict[int, list[EntregaNotificacao]] = {}
    for e in pendentes:
        por_usuario.setdefault(e.destinatario_id, []).append(e)
    enviados = 0
    for usuario_id, entregas in por_usuario.items():
        config = sessao.get(ConfigNotificacaoUsuario, usuario_id)
        if config is not None and config.frequencia_email == "semanal" and local.weekday() != 0:
            continue
        # Só entra no resumo o que esta execução conseguiu reivindicar
        minhas = [e for e in entregas if _reivindicar(sessao, e.id, "email_enviado_em")]
        if not minhas:
            continue
        usuario = sessao.get(Usuario, usuario_id)
        grupos: dict[str, list[tuple[str, str]]] = {}
        for e in minhas:
            modulo = e.notificacao.evento.split(".")[0] if e.notificacao.evento in EVENTOS else "comunicados"
            grupos.setdefault(ROTULOS_MODULO.get(modulo, "Outras"), []).append((e.assunto_copia, layout_email.url_completa(e.notificacao.link or f"/notificacoes/{e.id}")))
        titulo = f"Resumo das suas notificações: {len(minhas)} novidade(s)"
        texto = "\n\n".join(f"{rotulo}\n" + "\n".join(f"- {assunto}: {url}" for assunto, url in itens) for rotulo, itens in grupos.items())
        ok, erro = _enviar_smtp(sessao, usuario, titulo, texto, layout_email.html_resumo(titulo, list(grupos.items())))
        for e in minhas:
            e = sessao.get(EntregaNotificacao, e.id)
            e.email_ok, e.email_erro = ok, erro
        sessao.commit()
        enviados += 1
    return enviados


# --- Lembretes de ciência (e-mail só para quem quer) ---------------------------------------------------------------

def enviar_lembrete_ciencia(sessao: Session, entrega: EntregaNotificacao, prefixo_assunto: str = "Lembrete: ") -> bool:
    """Lembrete por e-mail de uma entrega sem ciência. Só sai se o destinatário ligou o e-mail em "Lembrete de ciência pendente".

    Não mexe nos carimbos da entrega original (o e-mail dela, se houve, já saiu). Devolve se enviou.
    """
    usuario = sessao.get(Usuario, entrega.destinatario_id)
    if usuario is None or not usuario.ativo or not preferencias.email_ligado(sessao, usuario.id, "comunicados.lembrete_ciencia"):
        return False
    ok, _ = _email_da_entrega(sessao, _entrega(sessao, entrega.id), prefixo_assunto)
    return ok


def enviar_teste_email(sessao: Session, usuario: Usuario, assunto: str, corpo: str) -> tuple[bool, str | None]:
    """E-mail de teste ao próprio usuário (botão "Testar" das Preferências), no layout oficial."""
    texto = f"{corpo}\n\n{layout_email.url_completa('/notificacoes')}"
    html = layout_email.html_email(assunto, [corpo], "/notificacoes", "Abrir minhas notificações")
    return _enviar_smtp(sessao, usuario, assunto, texto, html)
