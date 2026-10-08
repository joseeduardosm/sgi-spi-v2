# Criado por José Eduardo Santana Martins
# Este arquivo serve para enviar, uma vez por dia, o parabéns automático aos aniversariantes do dia.
"""Rotina diária do parabéns automático.

Roda numa thread de cada worker; o advisory lock do PostgreSQL e a chave única da mensagem
(`aniversario:<usuário>:<data>`) garantem que ninguém receba duas vezes, mesmo com vários workers ou reinícios.
"""

import logging
import threading
from datetime import date, datetime

from sqlalchemy import text

from app.core.banco import FUSO_SAO_PAULO
from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.services import servico_diretorio, servico_mensagens

registro_log = logging.getLogger(__name__)
ID_TRAVA = 7_300_002  # identificador arbitrário do advisory lock (o da sincronização LDAP é 7_300_001)
INTERVALO_VERIFICACAO = 900  # a cada 15 minutos confere se já passou da hora do envio


class AgendadorParabens:
    """Thread em segundo plano que dispara o parabéns do dia depois da hora configurada."""

    def __init__(self) -> None:
        self._parar = threading.Event()
        self._ultimo_envio: date | None = None

    def iniciar(self) -> None:
        """Inicia a thread, se `hora_parabens_aniversario` for 0 ou mais (-1 desliga)."""
        if obter_configuracao().hora_parabens_aniversario < 0:
            return
        threading.Thread(target=self._executar, name="parabens-aniversario", daemon=True).start()

    def parar(self) -> None:
        self._parar.set()

    def _executar(self) -> None:
        if self._parar.wait(60):
            return
        while True:
            agora = datetime.now(FUSO_SAO_PAULO)
            if agora.hour >= obter_configuracao().hora_parabens_aniversario and self._ultimo_envio != agora.date():
                try:
                    self.executar_uma_vez(agora.date())
                    self._ultimo_envio = agora.date()
                except Exception:  # noqa: BLE001 - a rotina nunca deve derrubar a thread
                    registro_log.exception("Erro inesperado no parabéns automático de aniversário.")
            if self._parar.wait(INTERVALO_VERIFICACAO):
                return

    @staticmethod
    def executar_uma_vez(hoje: date) -> int:
        """Envia os parabéns de `hoje` (se este worker obtiver a trava). Devolve quantas mensagens foram criadas."""
        with FabricaSessao() as sessao:
            if not sessao.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": ID_TRAVA}).scalar():
                return 0
            try:
                mensagens = servico_diretorio.enviar_parabens_do_dia(sessao, hoje)
                ids = [m.id for m in mensagens]
            finally:
                sessao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ID_TRAVA})
                sessao.commit()
        for mensagem_id in ids:
            servico_mensagens.enviar_emails(mensagem_id)
        registro_log.info("Parabéns automático: %s mensagem(ns) para %s.", len(ids), hoje.isoformat())
        return len(ids)
