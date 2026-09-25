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
ID_TRAVA = 7_300_001  # identificador arbitrário do advisory lock


class AgendadorSincronizacaoLdap:
    def __init__(self) -> None:
        self._parar = threading.Event()
        self._linha_execucao: threading.Thread | None = None

    def iniciar(self) -> None:
        minutos = obter_configuracao().intervalo_sincronizacao_ldap_minutos
        if minutos <= 0:
            return
        self._linha_execucao = threading.Thread(target=self._executar, args=(minutos * 60,), name="sincronizacao-ldap", daemon=True)
        self._linha_execucao.start()

    def parar(self) -> None:
        self._parar.set()

    def _executar(self, intervalo: float) -> None:
        # Pequeno atraso inicial para não competir com a subida da API
        if self._parar.wait(30):
            return
        while True:
            try:
                self.executar_uma_vez()
            except Exception:  # noqa: BLE001 - a rotina nunca deve derrubar a thread
                registro_log.exception("Erro inesperado na sincronização LDAP automática.")
            if self._parar.wait(intervalo):
                return

    @staticmethod
    def executar_uma_vez() -> None:
        with FabricaSessao() as sessao:
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
            finally:
                sessao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ID_TRAVA})
                sessao.commit()
