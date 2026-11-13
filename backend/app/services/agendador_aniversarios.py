"""
===============================================================================
ARQUIVO: agendador_aniversarios.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Enviar, uma vez por dia, o parabéns automático aos aniversariantes do dia.

RESUMO TÉCNICO:
AgendadorParabens roda numa thread em segundo plano em cada worker da API.
A cada 15 minutos confere se já passou da hora configurada
(`hora_parabens_aniversario`; -1 desliga) e, se ainda não enviou hoje, chama
executar_uma_vez(). O advisory lock do PostgreSQL e a chave única da mensagem
(`aniversario:<usuário>:<data>`) garantem que ninguém receba duas vezes,
mesmo com vários workers ou reinícios.

FINALIDADE DE NEGÓCIO:
Valorizar as pessoas da SPI com uma mensagem de parabéns no dia do
aniversário, sem depender de alguém lembrar de enviar.

CONTEXTO NO SISTEMA:
Iniciado e parado junto com a API (ciclo de vida do app FastAPI). Quem monta
e grava as mensagens é `servico_diretorio.enviar_parabens_do_dia`; e-mail e
pop-up saem pelo mecanismo de notificações, conforme as Preferências de cada
pessoa. Usa a data de nascimento do perfil institucional.

===============================================================================
"""

import logging
import threading
from datetime import date, datetime

from sqlalchemy import text

from app.core.banco import FUSO_SAO_PAULO
from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.services import servico_diretorio

registro_log = logging.getLogger(__name__)
ID_TRAVA = 7_300_002  # identificador arbitrário do advisory lock (o da sincronização LDAP é 7_300_001)
INTERVALO_VERIFICACAO = 900  # a cada 15 minutos confere se já passou da hora do envio


class AgendadorParabens:
    """Thread em segundo plano que dispara o parabéns do dia depois da hora configurada."""

    def __init__(self) -> None:
        """Prepara o sinal de parada e a memória do último dia já enviado."""
        # threading.Event: sinal compartilhado entre threads. `set()` pede a
        # parada; `wait(segundos)` espera o tempo e devolve True se a parada
        # foi pedida nesse meio tempo (serve de "sleep interrompível").
        self._parar = threading.Event()
        self._ultimo_envio: date | None = None

    def iniciar(self) -> None:
        """Inicia a thread, se `hora_parabens_aniversario` for 0 ou mais (-1 desliga)."""
        if obter_configuracao().hora_parabens_aniversario < 0:
            return
        # daemon=True: a thread não impede o processo de encerrar
        threading.Thread(target=self._executar, name="parabens-aniversario", daemon=True).start()

    def parar(self) -> None:
        """Sinaliza a thread para parar (chamado quando a API é desligada)."""
        self._parar.set()

    def _executar(self) -> None:
        """Laço principal: confere a hora a cada 15 minutos e envia uma vez por dia."""
        # Espera 1 minuto antes da primeira conferência para não competir com a subida da API
        if self._parar.wait(60):
            return
        while True:
            agora = datetime.now(FUSO_SAO_PAULO)
            # Envia só depois da hora configurada (horário de São Paulo) e só se
            # este worker ainda não enviou hoje. Se outro worker já enviou, a
            # chave única da mensagem impede a duplicata.
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
        """Envia os parabéns de `hoje` (se este worker obtiver a trava). Devolve quantas mensagens foram criadas.

        Efeitos: grava as mensagens no banco (commit), o que dispara e-mail e
        pop-up. Se outro worker estiver com a trava, não faz nada e devolve 0.
        """
        # FabricaSessao() abre uma sessão do SQLAlchemy (conexão com o banco);
        # o `with` garante que ela seja fechada no fim.
        with FabricaSessao() as sessao:
            # pg_try_advisory_lock: trava "lógica" do PostgreSQL identificada por
            # um número. Não espera: devolve falso na hora se outro worker já a tem.
            if not sessao.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": ID_TRAVA}).scalar():
                return 0
            try:
                mensagens = servico_diretorio.enviar_parabens_do_dia(sessao, hoje)
                ids = [m.id for m in mensagens]
            finally:
                sessao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ID_TRAVA})
                sessao.commit()
        # Os e-mails e pop-ups saem sozinhos no commit (cada pessoa recebe pelos canais que ligou em Preferências)
        registro_log.info("Parabéns automático: %s mensagem(ns) para %s.", len(ids), hoje.isoformat())
        return len(ids)
