# Criado por José Eduardo Santana Martins
# Este arquivo serve para agendar a sincronização periódica dos usuários do diretório LDAP.
"""Sincronização periódica do diretório LDAP ativo.

Roda numa thread de cada worker do uvicorn; um advisory lock do PostgreSQL garante que só
um deles sincronize por vez. Falhas não desativam ninguém (a fotografia incompleta é descartada).
"""

import logging
import threading

from sqlalchemy import text

from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.services import servico_ldap
from app.services.cliente_ldap import ErroLdapIndisponivel

registro_log = logging.getLogger(__name__)
# Número qualquer, igual em todos os workers, que identifica a trava no PostgreSQL
ID_TRAVA = 7_300_001  # identificador arbitrário do advisory lock


class AgendadorSincronizacaoLdap:
    """Thread em segundo plano que chama a sincronização LDAP a cada N minutos."""

    # O Event serve para pedir a parada e, ao mesmo tempo, esperar o intervalo (wait com timeout)
    def __init__(self) -> None:
        self._parar = threading.Event()
        self._linha_execucao: threading.Thread | None = None

    def iniciar(self) -> None:
        """Inicia a thread, se o intervalo configurado for maior que zero (0 = desligado)."""
        minutos = obter_configuracao().intervalo_sincronizacao_ldap_minutos
        if minutos <= 0:
            return
        # daemon=True: a thread não impede o processo de encerrar
        self._linha_execucao = threading.Thread(target=self._executar, args=(minutos * 60,), name="sincronizacao-ldap", daemon=True)
        self._linha_execucao.start()

    def parar(self) -> None:
        """Sinaliza a thread para parar (chamado quando a API é desligada)."""
        self._parar.set()

    def _executar(self, intervalo: float) -> None:
        """Laço principal: sincroniza, espera o intervalo e repete até receber o pedido de parada."""
        # Pequeno atraso inicial para não competir com a subida da API
        if self._parar.wait(30):
            return
        while True:
            try:
                self.executar_uma_vez()
            except Exception:  # noqa: BLE001 - a rotina nunca deve derrubar a thread
                registro_log.exception("Erro inesperado na sincronização LDAP automática.")
            # `wait` devolve True se a parada foi pedida durante a espera
            if self._parar.wait(intervalo):
                return

    @staticmethod
    def executar_uma_vez() -> None:
        """Faz uma sincronização, se este worker conseguir a trava; os outros apenas pulam a rodada."""
        with FabricaSessao() as sessao:
            # Trava sem espera: se outro worker já está sincronizando, devolve falso na hora
            obteve_trava = sessao.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": ID_TRAVA}).scalar()
            if not obteve_trava:
                return
            try:
                diretorio = servico_ldap.obter_diretorio_ativo(sessao)
                if diretorio is None:
                    return
                try:
                    r = servico_ldap.sincronizar(sessao, diretorio.id, "sistema:sincronizacao-ldap")
                    registro_log.info(
                        "LDAP sincronizado: %s encontrados, %s criados, %s atualizados, %s desativados.",
                        r.encontrados, r.criados, r.atualizados, r.desativados,
                    )
                except ErroLdapIndisponivel as erro:
                    registro_log.error("Sincronização LDAP automática falhou: %s", erro)
            # A trava é sempre liberada, mesmo se a sincronização falhar
            finally:
                sessao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ID_TRAVA})
                sessao.commit()
