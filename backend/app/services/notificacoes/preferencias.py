# Criado por José Eduardo Santana Martins
# Este arquivo serve para as preferências de notificação: canais por evento, e-mail em resumo, não perturbe, silenciados e obrigatórias.
"""Preferências das Notificações.

- A **caixa recebe sempre**; e-mail, navegador e desktop são opcionais e começam desmarcados (sem linha em `notificacoes_preferencias`).
- `canais_por_destinatario` calcula, na hora da entrega, os canais de cada pessoa: `(preferência ∪ obrigatórias) − silenciados`,
  limitados aos `canais_disponiveis` do evento; o "não perturbe" tira navegador e desktop (não o e-mail).
- A administração pode **obrigar** um canal para um evento (por setor ou usuário): a pessoa vê marcado e travado.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO, agora_utc
from app.models.notificacao_preferencias import (
    ConfigNotificacaoUsuario, InscricaoNavegador, NotificacaoObrigatoria, NotificacaoSilenciada, PreferenciaNotificacao,
)
from app.models.setor import MembroSetor
from app.models.usuario import Usuario
from app.services.notificacoes import catalogo
from app.services.notificacoes.catalogo import CANAL_DESKTOP, CANAL_EMAIL, CANAL_NAVEGADOR, CANAIS, EVENTOS

FREQUENCIAS = ("imediato", "diario", "semanal")
HORA_RESUMO = 7


class ErroPreferencias(Exception):
    """Preferência inválida (evento ou canal desconhecido, canal indisponível para o evento...)."""

    def __init__(self, detalhe: str, status: int = 422, codigo: str = "validacao") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


@dataclass
class CanaisDoDestinatario:
    """Canais externos de uma entrega e se o e-mail espera o resumo."""

    email: bool = False
    navegador: bool = False
    desktop: bool = False
    email_resumo: bool = False


# --- Não perturbe ----------------------------------------------------------------------------------------------

def em_silencio(config: ConfigNotificacaoUsuario | None, agora: datetime | None = None) -> bool:
    """O "não perturbe" está valendo agora (horário de São Paulo)? Fim de semana inteiro, se a pessoa escolheu; senão a faixa de horas."""
    if config is None:
        return False
    local = (agora or agora_utc()).astimezone(FUSO_SAO_PAULO)
    if config.silencio_fins_de_semana and local.weekday() >= 5:
        return True
    inicio, fim = config.silencio_inicio, config.silencio_fim
    if inicio is None or fim is None or inicio == fim:
        return False
    hora = local.time().replace(second=0, microsecond=0)
    # Faixa que atravessa a meia-noite (ex.: 19h às 7h)
    return inicio <= hora < fim if inicio < fim else (hora >= inicio or hora < fim)


# --- Cálculo dos canais na entrega -----------------------------------------------------------------------------

def canais_por_destinatario(
    sessao: Session, usuarios_ids: Iterable[int], evento: str, *, contrato_id: uuid.UUID | None = None, tarefa_id: uuid.UUID | None = None,
    agora: datetime | None = None,
) -> dict[int, CanaisDoDestinatario]:
    """Canais externos de cada destinatário para o evento. Quem não tem nada marcado fica só com a caixa."""
    ids = set(usuarios_ids)
    resultado = {i: CanaisDoDestinatario() for i in ids}
    if not ids:
        return resultado
    disponiveis = set(EVENTOS[evento].canais_disponiveis)
    marcados: dict[int, set[str]] = {i: set() for i in ids}
    for usuario_id, canal in sessao.execute(select(PreferenciaNotificacao.usuario_id, PreferenciaNotificacao.canal).where(
            PreferenciaNotificacao.evento == evento, PreferenciaNotificacao.usuario_id.in_(ids))):
        marcados[usuario_id].add(canal)
    for obrigatoria in sessao.scalars(select(NotificacaoObrigatoria).where(NotificacaoObrigatoria.evento == evento)):
        if obrigatoria.usuario_id in marcados:
            marcados[obrigatoria.usuario_id].add(obrigatoria.canal)
        if obrigatoria.setor_id is not None:
            for usuario_id in sessao.scalars(select(MembroSetor.usuario_id).where(MembroSetor.setor_id == obrigatoria.setor_id, MembroSetor.usuario_id.in_(ids))):
                marcados[usuario_id].add(obrigatoria.canal)
    # Silenciados cortam os canais externos (a caixa continua)
    silenciados: set[int] = set()
    for tipo, alvo in (("contrato", contrato_id), ("tarefa", tarefa_id)):
        if alvo is not None:
            silenciados |= set(sessao.scalars(select(NotificacaoSilenciada.usuario_id).where(
                NotificacaoSilenciada.tipo == tipo, NotificacaoSilenciada.alvo_id == alvo, NotificacaoSilenciada.usuario_id.in_(ids))))
    configs = {c.usuario_id: c for c in sessao.scalars(select(ConfigNotificacaoUsuario).where(ConfigNotificacaoUsuario.usuario_id.in_(ids)))}
    for usuario_id in ids:
        if usuario_id in silenciados:
            continue
        canais = marcados[usuario_id] & disponiveis
        config = configs.get(usuario_id)
        if em_silencio(config, agora):
            canais -= {CANAL_NAVEGADOR, CANAL_DESKTOP}
        resultado[usuario_id] = CanaisDoDestinatario(
            email=CANAL_EMAIL in canais, navegador=CANAL_NAVEGADOR in canais, desktop=CANAL_DESKTOP in canais,
            email_resumo=CANAL_EMAIL in canais and config is not None and config.frequencia_email != "imediato",
        )
    return resultado


def email_ligado(sessao: Session, usuario_id: int, evento: str) -> bool:
    """O usuário quer e-mail para este evento (preferência ou obrigatória)? Usado nos lembretes que não nascem de `notificar`."""
    return canais_por_destinatario(sessao, [usuario_id], evento)[usuario_id].email


# --- Leitura e gravação pela tela ------------------------------------------------------------------------------

def _obrigatorias_do_usuario(sessao: Session, usuario: Usuario) -> set[tuple[str, str]]:
    """(evento, canal) obrigatórios para o usuário (direto ou pelos setores dele)."""
    setores = set(sessao.scalars(select(MembroSetor.setor_id).where(MembroSetor.usuario_id == usuario.id)))
    pares: set[tuple[str, str]] = set()
    for o in sessao.scalars(select(NotificacaoObrigatoria)):
        if o.usuario_id == usuario.id or (o.setor_id is not None and o.setor_id in setores):
            pares.add((o.evento, o.canal))
    return pares


def _config(sessao: Session, usuario: Usuario) -> ConfigNotificacaoUsuario | None:
    return sessao.get(ConfigNotificacaoUsuario, usuario.id)


def _hora(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def montar(sessao: Session, usuario: Usuario, navegador: dict) -> dict:
    """Tudo o que a tela de Preferências precisa: matriz, configuração, navegador e silenciados."""
    ligados = {(p.evento, p.canal) for p in sessao.scalars(select(PreferenciaNotificacao).where(PreferenciaNotificacao.usuario_id == usuario.id))}
    obrigatorios = _obrigatorias_do_usuario(sessao, usuario)
    modulos = []
    for chave, rotulo, eventos in catalogo.por_modulo():
        itens = []
        for e in eventos:
            canais = {c: {
                "disponivel": c in e.canais_disponiveis,
                "ligado": c in e.canais_disponiveis and ((e.chave, c) in ligados or (e.chave, c) in obrigatorios),
                "obrigatorio": (e.chave, c) in obrigatorios,
            } for c in CANAIS}
            itens.append({"chave": e.chave, "rotulo": e.rotulo, "descricao": e.descricao, "canais": canais})
        modulos.append({"chave": chave, "rotulo": rotulo, "eventos": itens})
    config = _config(sessao, usuario)
    silenciados = sessao.scalars(select(NotificacaoSilenciada).where(NotificacaoSilenciada.usuario_id == usuario.id).order_by(NotificacaoSilenciada.criado_em.desc()))
    return {
        "modulos": modulos,
        "configuracao": {
            "frequencia_email": config.frequencia_email if config else "imediato",
            "silencio_inicio": _hora(config.silencio_inicio) if config else None,
            "silencio_fim": _hora(config.silencio_fim) if config else None,
            "silencio_fins_de_semana": bool(config.silencio_fins_de_semana) if config else False,
        },
        "navegador": navegador,
        "silenciados": [{"id": s.id, "tipo": s.tipo, "alvo_id": s.alvo_id, "rotulo": s.rotulo} for s in silenciados],
    }


def _parse_hora(texto: str | None) -> time | None:
    if not texto:
        return None
    try:
        h, m = texto.split(":")
        return time(int(h), int(m))
    except (ValueError, TypeError) as erro:
        raise ErroPreferencias(f"Horário inválido: {texto}. Use HH:MM.") from erro


def salvar(sessao: Session, usuario: Usuario, canais: dict[str, list[str]], configuracao: dict) -> None:
    """Substitui as preferências do usuário. `canais` = {evento: [canais ligados]}. Obrigatórias ficam sempre (não são gravadas por ele)."""
    obrigatorios = _obrigatorias_do_usuario(sessao, usuario)
    novos: set[tuple[str, str]] = set()
    for evento, lista in canais.items():
        if evento not in EVENTOS:
            raise ErroPreferencias(f"Evento desconhecido: {evento}.")
        for canal in lista:
            if canal not in CANAIS:
                raise ErroPreferencias(f"Canal desconhecido: {canal}.")
            if canal not in EVENTOS[evento].canais_disponiveis:
                raise ErroPreferencias(f"O evento \"{EVENTOS[evento].rotulo}\" não tem o canal {canal}.")
            if (evento, canal) not in obrigatorios:
                novos.add((evento, canal))
    if configuracao.get("frequencia_email", "imediato") not in FREQUENCIAS:
        raise ErroPreferencias("A frequência do e-mail é imediato, diario ou semanal.")
    inicio, fim = _parse_hora(configuracao.get("silencio_inicio")), _parse_hora(configuracao.get("silencio_fim"))
    if (inicio is None) != (fim is None):
        raise ErroPreferencias("Informe o início e o fim do não perturbe (ou deixe os dois vazios).")
    sessao.execute(delete(PreferenciaNotificacao).where(PreferenciaNotificacao.usuario_id == usuario.id))
    sessao.add_all([PreferenciaNotificacao(usuario_id=usuario.id, evento=e, canal=c) for e, c in sorted(novos)])
    linha = _config(sessao, usuario) or ConfigNotificacaoUsuario(usuario_id=usuario.id)
    linha.frequencia_email = configuracao.get("frequencia_email", "imediato")
    linha.silencio_inicio, linha.silencio_fim = inicio, fim
    linha.silencio_fins_de_semana = bool(configuracao.get("silencio_fins_de_semana", False))
    sessao.add(linha)
    sessao.commit()


# --- Silenciados -------------------------------------------------------------------------------------------------

def silenciar(sessao: Session, usuario: Usuario, tipo: str, alvo_id: uuid.UUID, rotulo: str) -> NotificacaoSilenciada:
    """Silencia um contrato ou tarefa (idempotente)."""
    if tipo not in ("contrato", "tarefa"):
        raise ErroPreferencias("Só contratos e tarefas podem ser silenciados.")
    existente = sessao.scalar(select(NotificacaoSilenciada).where(
        NotificacaoSilenciada.usuario_id == usuario.id, NotificacaoSilenciada.tipo == tipo, NotificacaoSilenciada.alvo_id == alvo_id))
    if existente is not None:
        return existente
    linha = NotificacaoSilenciada(usuario_id=usuario.id, tipo=tipo, alvo_id=alvo_id, rotulo=rotulo[:300])
    sessao.add(linha)
    sessao.commit()
    return linha


def voltar_a_avisar(sessao: Session, usuario: Usuario, silenciado_id: int) -> None:
    linha = sessao.get(NotificacaoSilenciada, silenciado_id)
    if linha is None or linha.usuario_id != usuario.id:
        raise ErroPreferencias("Item silenciado não encontrado.", 404, "nao_encontrado")
    sessao.delete(linha)
    sessao.commit()


# --- Situação do navegador (para a tela) -------------------------------------------------------------------------

def total_inscricoes(sessao: Session, usuario: Usuario) -> int:
    return len(list(sessao.scalars(select(InscricaoNavegador.id).where(InscricaoNavegador.usuario_id == usuario.id))))
