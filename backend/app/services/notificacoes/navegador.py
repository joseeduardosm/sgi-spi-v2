# Criado por José Eduardo Santana Martins
# Este arquivo serve para as notificações do navegador (Web Push): inscrições, envio e o token de ciência do pop-up.
"""Notificações do navegador (Web Push).

- As chaves VAPID vêm do `.env` (`CHAVE_PUBLICA_VAPID`, `CHAVE_PRIVADA_VAPID`, `CONTATO_VAPID`); sem elas o canal fica indisponível.
- Cada navegador inscrito é uma linha em `notificacoes_inscricoes_navegador`. O serviço de push responder `404`/`410` apaga a inscrição
  (o navegador cancelou); outras falhas somam em `falhas_seguidas` (a limpeza diária apaga as que passam de 10).
- O pop-up tem o botão **Ciente**: o service worker não tem a sessão do usuário, então o payload leva um token curto (7 dias) que vale
  só para dar ciência àquela entrega (`gerar_token_ciencia` / `validar_token_ciencia`).
"""

import json
import logging
import uuid
from datetime import timedelta
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.notificacao_preferencias import InscricaoNavegador
from app.models.usuario import Usuario

log = logging.getLogger("sgi_spi.notificacoes")

LIMITE_TEXTO = 200
FALHAS_PARA_APAGAR = 10
DIAS_SEM_USO_PARA_APAGAR = 90
DIAS_TOKEN_CIENCIA = 7
FINALIDADE_CIENCIA = "ciencia_push"


def configurado() -> bool:
    """As três variáveis VAPID estão preenchidas?"""
    c = obter_configuracao()
    return bool(c.chave_publica_vapid and c.chave_privada_vapid.get_secret_value() and c.contato_vapid)


def situacao(sessao: Session, usuario: Usuario) -> dict:
    """Situação do canal para a tela: disponível? chave pública e quantos navegadores a pessoa já inscreveu."""
    inscricoes = list(sessao.scalars(select(InscricaoNavegador).where(InscricaoNavegador.usuario_id == usuario.id).order_by(InscricaoNavegador.criada_em)))
    return {
        "disponivel": configurado(),
        "chave_publica_vapid": obter_configuracao().chave_publica_vapid if configurado() else None,
        "inscricoes": len(inscricoes),
        "aparelhos": [{"id": i.id, "rotulo": i.rotulo or "Navegador", "criada_em": i.criada_em, "ultimo_envio_em": i.ultimo_envio_em} for i in inscricoes],
        "explicacao": None if configurado() else "O servidor ainda não tem as chaves de notificação do navegador (VAPID): peça à TI para configurá-las.",
    }


def inscrever(sessao: Session, usuario: Usuario, endpoint: str, p256dh: str, auth: str, rotulo: str) -> InscricaoNavegador:
    """Cria ou atualiza a inscrição pelo `endpoint` (o mesmo navegador não duplica; se mudou de dono, passa para quem entrou agora)."""
    linha = sessao.scalar(select(InscricaoNavegador).where(InscricaoNavegador.endpoint == endpoint))
    if linha is None:
        linha = InscricaoNavegador(id=uuid.uuid4(), usuario_id=usuario.id, endpoint=endpoint, p256dh=p256dh, auth=auth, rotulo=rotulo[:200])
        sessao.add(linha)
    else:
        linha.usuario_id, linha.p256dh, linha.auth, linha.rotulo, linha.falhas_seguidas = usuario.id, p256dh, auth, rotulo[:200], 0
    sessao.commit()
    return linha


def remover(sessao: Session, usuario: Usuario, endpoint: str) -> bool:
    """Remove a inscrição do próprio usuário. Devolve se havia o que remover."""
    linha = sessao.scalar(select(InscricaoNavegador).where(InscricaoNavegador.endpoint == endpoint, InscricaoNavegador.usuario_id == usuario.id))
    if linha is None:
        return False
    sessao.delete(linha)
    sessao.commit()
    return True


# --- Token de ciência (botão "Ciente" do pop-up) -----------------------------------------------------------------

def gerar_token_ciencia(entrega_id: uuid.UUID) -> str:
    """Token curto que só vale para dar ciência à entrega informada."""
    c = obter_configuracao()
    corpo = {"fin": FINALIDADE_CIENCIA, "entrega": str(entrega_id), "exp": agora_utc() + timedelta(days=DIAS_TOKEN_CIENCIA)}
    return jwt.encode(corpo, c.chave_secreta_jwt.get_secret_value(), algorithm=c.algoritmo_jwt)


def validar_token_ciencia(token: str) -> uuid.UUID | None:
    """Id da entrega, ou `None` se o token é inválido, expirou ou não é de ciência."""
    c = obter_configuracao()
    try:
        corpo = jwt.decode(token, c.chave_secreta_jwt.get_secret_value(), algorithms=[c.algoritmo_jwt])
        if corpo.get("fin") != FINALIDADE_CIENCIA:
            return None
        return uuid.UUID(corpo["entrega"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


# --- Envio -------------------------------------------------------------------------------------------------------

def _enviar_um(assinatura: dict[str, Any], dados: str) -> None:
    """Uma chamada ao serviço de push (separada para os testes substituírem sem rede)."""
    from pywebpush import webpush

    c = obter_configuracao()
    webpush(subscription_info=assinatura, data=dados, vapid_private_key=c.chave_privada_vapid.get_secret_value(),
            vapid_claims={"sub": c.contato_vapid}, ttl=60 * 60 * 12, timeout=10)


def _status_da_falha(erro: Exception) -> int | None:
    resposta = getattr(erro, "response", None)
    return getattr(resposta, "status_code", None)


def resumir(texto: str) -> str:
    """Texto do pop-up: sem quebras de linha e com no máximo 200 caracteres."""
    plano = " ".join(texto.split())
    return plano if len(plano) <= LIMITE_TEXTO else plano[: LIMITE_TEXTO - 1].rstrip() + "…"


def montar_payload(entrega_id: uuid.UUID, titulo: str, texto: str, link: str | None) -> str:
    """JSON enviado ao service worker: título, texto curto, url, tag (um pop-up por entrega) e o token do botão Ciente."""
    return json.dumps({
        "titulo": titulo[:120], "texto": resumir(texto), "url": link or f"/notificacoes/{entrega_id}", "tag": str(entrega_id),
        "entrega_id": str(entrega_id), "token_ciencia": gerar_token_ciencia(entrega_id),
    }, ensure_ascii=False)


def enviar(sessao: Session, usuario_id: int, dados: str) -> tuple[int, str | None]:
    """Envia o payload a todos os navegadores do usuário. Devolve (quantos receberam, erro resumido ou None).

    404/410 apagam a inscrição; outra falha soma em `falhas_seguidas`. Faz commit.
    """
    if not configurado():
        return 0, "Notificações do navegador não configuradas (VAPID)."
    inscricoes = list(sessao.scalars(select(InscricaoNavegador).where(InscricaoNavegador.usuario_id == usuario_id)))
    if not inscricoes:
        return 0, "Nenhum navegador inscrito."
    enviados, erros = 0, []
    for ins in inscricoes:
        try:
            _enviar_um({"endpoint": ins.endpoint, "keys": {"p256dh": ins.p256dh, "auth": ins.auth}}, dados)
            ins.ultimo_envio_em, ins.falhas_seguidas = agora_utc(), 0
            enviados += 1
        except Exception as erro:  # noqa: BLE001 - qualquer falha do serviço de push é registrada, não derruba o despacho
            status = _status_da_falha(erro)
            if status in (404, 410):
                sessao.delete(ins)
                erros.append(f"inscrição expirada ({status}) removida")
            else:
                ins.falhas_seguidas += 1
                erros.append(f"falha {status or ''}: {str(erro)[:150]}".strip())
            log.warning("Push para o usuário %s falhou: %s", usuario_id, erro)
    sessao.commit()
    return enviados, "; ".join(erros) if erros and not enviados else None


def limpar_inscricoes(sessao: Session) -> int:
    """Apaga as inscrições com 10+ falhas seguidas ou sem uso há 90 dias. Devolve quantas saíram (faz commit)."""
    limite_uso = agora_utc() - timedelta(days=DIAS_SEM_USO_PARA_APAGAR)
    apagadas = 0
    for ins in sessao.scalars(select(InscricaoNavegador)):
        ultimo = ins.ultimo_envio_em or ins.criada_em
        ultimo = ultimo if ultimo.tzinfo else ultimo.replace(tzinfo=agora_utc().tzinfo)
        if ins.falhas_seguidas >= FALHAS_PARA_APAGAR or ultimo < limite_uso:
            sessao.delete(ins)
            apagadas += 1
    sessao.commit()
    return apagadas
