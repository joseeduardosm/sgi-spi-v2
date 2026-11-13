"""
===============================================================================
ARQUIVO: agendador_ldap.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Agendar a sincronização periódica dos usuários do diretório LDAP ativo
(Active Directory do órgão) com as contas do SGI.

RESUMO TÉCNICO:
AgendadorSincronizacaoLdap roda numa thread em segundo plano em cada worker
do uvicorn, a cada `intervalo_sincronizacao_ldap_minutos` (0 desliga). Um
advisory lock do PostgreSQL garante que só um worker sincronize por vez.
Falhas não desativam ninguém: a fotografia incompleta do diretório é
descartada e o erro vai para o log.

FINALIDADE DE NEGÓCIO:
Manter as contas do SGI alinhadas com o diretório da rede: quem entra no
órgão ganha conta, quem tem dados alterados é atualizado e quem sai é
desativado, sem trabalho manual do administrador.

CONTEXTO NO SISTEMA:
Iniciado e parado junto com a API. Chama `servico_ldap.obter_diretorio_ativo`
e `servico_ldap.sincronizar`, que usam `cliente_ldap.py` para consultar o
servidor. O diretório é cadastrado em Administração › Diretórios LDAP.

===============================================================================
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
        """Prepara o sinal de parada; a thread só é criada em iniciar()."""
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
                    # O texto "sistema:..." identifica, no histórico, que a
                    # sincronização foi automática e não feita por uma pessoa.
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
