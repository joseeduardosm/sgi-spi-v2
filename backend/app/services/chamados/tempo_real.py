# Criado por José Eduardo Santana Martins
# Este arquivo serve para avisar as telas abertas (fila, painel de TV) assim que um chamado muda, sem elas ficarem perguntando.
"""Tempo real dos Chamados.

Como funciona:
1. **Coleta**: ganchos na sessão do SQLAlchemy anotam cada chamado novo ou alterado (inclusive por uma resposta, tarefa, aprovação...)
   durante o `flush`. Nada sai se a transação for desfeita.
2. **Publicação**: depois do `commit`, cada evento vai para o canal `sgi_chamados` do PostgreSQL (`pg_notify`). Assim chega a todos os
   processos: os dois workers da API e as tarefas automáticas (o prazo estourado também aparece ao vivo). No SQLite (testes) a
   entrega é direta, no próprio processo.
3. **Escuta**: em cada worker, uma linha de execução faz `LISTEN sgi_chamados` e repassa o evento às conexões abertas (SSE).

O evento é mínimo (`tipo`, `numero` e os setores, para filtrar): a tela recebe só `tipo` e `numero` e busca de novo o que precisa,
pela rota normal (que confere a visibilidade). Nenhum título nem nome pessoal passa pelo canal.
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import identity_key

from app.core.banco import motor
from app.models.chamados import STATUS_SOLUCIONADO, AcompanhamentoChamado, AtorChamado, Chamado, SolucaoChamado, TarefaChamado, ValidacaoChamado

log = logging.getLogger(__name__)

CANAL = "sgi_chamados"
# Intervalo do "ping" (comentário SSE): mantém a conexão viva no Nginx (timeout de 60 s) e revela quem desconectou
INTERVALO_PING = 20.0
# Uma conexão dura no máximo isto; a tela reconecta sozinha e a autorização é conferida de novo
DURACAO_MAXIMA = 30 * 60.0
# Eventos guardados por conexão lenta antes de descartar (a tela recarrega tudo ao receber o próximo)
TAMANHO_FILA = 200
# Partes do chamado: mudar qualquer uma delas avisa as telas do chamado a que pertencem
_FILHOS = (AcompanhamentoChamado, SolucaoChamado, TarefaChamado, ValidacaoChamado, AtorChamado)


@dataclass(frozen=True)
class Evento:
    """O que mudou: `novo` (abertura) ou `alterado`. Os setores e o solicitante servem só para filtrar quem recebe.

    `acao` diz o que aconteceu de marcante, para o painel anunciar por voz: `assumido` (ganhou responsável ou trocou de responsável),
    `resolvido`, `reaberto` ou `transferido` (mudou de setor responsável; `setor_anterior_id` faz o painel do setor de antes saber também).
    Vazio = outra mudança (resposta, tarefa, prioridade...).
    """
    tipo: str
    numero: int
    setor_id: int
    solicitante_id: int | None = None
    setor_solicitante_id: int | None = None
    responsavel_id: int | None = None
    acao: str = ""
    setor_anterior_id: int | None = None

    def para_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def de_json(cls, carga: str) -> "Evento":
        return cls(**json.loads(carga))


# ---------------------------------------------------------------------------------------------
# Distribuição dentro do processo (às conexões SSE abertas neste worker)
# ---------------------------------------------------------------------------------------------

class _Barramento:
    """Conexões abertas neste processo. Cada uma tem a sua fila asyncio, alimentada de forma segura a partir de outra thread."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._assinantes: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._ouvinte: threading.Thread | None = None

    def assinar(self) -> asyncio.Queue:
        fila: asyncio.Queue = asyncio.Queue(TAMANHO_FILA)
        with self._trava:
            self._assinantes.add((asyncio.get_running_loop(), fila))
        _garantir_ouvinte()
        return fila

    def cancelar(self, fila: asyncio.Queue) -> None:
        with self._trava:
            self._assinantes = {x for x in self._assinantes if x[1] is not fila}

    def entregar(self, evento: Evento) -> None:
        with self._trava:
            assinantes = list(self._assinantes)
        for laco, fila in assinantes:
            try:
                laco.call_soon_threadsafe(_colocar, fila, evento)
            except RuntimeError:
                # O laço já foi encerrado (worker parando): a conexão some no próximo `cancelar`
                pass

    @property
    def quantidade(self) -> int:
        return len(self._assinantes)


def _colocar(fila: asyncio.Queue, evento: Evento) -> None:
    try:
        fila.put_nowait(evento)
    except asyncio.QueueFull:
        log.warning("Conexão de tempo real lenta: evento do chamado %s descartado", evento.numero)


barramento = _Barramento()


# ---------------------------------------------------------------------------------------------
# Escuta do PostgreSQL (uma thread por processo, iniciada na primeira conexão SSE)
# ---------------------------------------------------------------------------------------------

def _usa_postgres() -> bool:
    return motor.dialect.name == "postgresql"


def _garantir_ouvinte() -> None:
    if not _usa_postgres() or (barramento._ouvinte is not None and barramento._ouvinte.is_alive()):
        return
    with barramento._trava:
        if barramento._ouvinte is not None and barramento._ouvinte.is_alive():
            return
        barramento._ouvinte = threading.Thread(target=_escutar, name="chamados-tempo-real", daemon=True)
        barramento._ouvinte.start()


def _escutar() -> None:
    """LISTEN contínuo, com reconexão. Usa o psycopg direto (fora do pool do SQLAlchemy), em modo autocommit."""
    import psycopg

    conninfo = motor.url.set(drivername="postgresql").render_as_string(hide_password=False)
    while True:
        try:
            with psycopg.connect(conninfo, autocommit=True) as conexao:
                conexao.execute(f"LISTEN {CANAL}")
                log.info("Tempo real dos Chamados: escutando o canal %s", CANAL)
                for aviso in conexao.notifies():
                    try:
                        barramento.entregar(Evento.de_json(aviso.payload))
                    except (TypeError, ValueError):
                        log.warning("Aviso inválido no canal %s", CANAL)
        except Exception:  # noqa: BLE001 — qualquer queda do banco: espera e reconecta
            log.exception("Tempo real dos Chamados: conexão de escuta caiu; nova tentativa em 5 s")
            time.sleep(5)


# ---------------------------------------------------------------------------------------------
# Coleta e publicação (ganchos da sessão)
# ---------------------------------------------------------------------------------------------

# Ordem de importância: se várias coisas mudam juntas (ex.: resolveu e trocou o responsável), vale a primeira da lista
_ACOES = ("resolvido", "reaberto", "transferido", "assumido")


def _acao(chamado: Chamado) -> tuple[str, int | None]:
    """O que mudou de marcante neste flush (pelo histórico dos atributos, que no `after_flush` ainda é o de antes) e o setor anterior."""
    estado = inspect(chamado)
    status, setor, responsavel = (estado.attrs[n].history for n in ("status_base", "setor_id", "responsavel_id"))
    acoes = []
    if status.has_changes() and status.deleted:
        antes, depois = status.deleted[0], chamado.status_base
        if depois == STATUS_SOLUCIONADO and antes != STATUS_SOLUCIONADO:
            acoes.append("resolvido")
        elif antes == STATUS_SOLUCIONADO and depois != STATUS_SOLUCIONADO:
            acoes.append("reaberto")
    setor_anterior = setor.deleted[0] if setor.has_changes() and setor.deleted else None
    if setor_anterior is not None and setor_anterior != chamado.setor_id:
        acoes.append("transferido")
    if responsavel.has_changes() and chamado.responsavel_id is not None and (responsavel.deleted or [None])[0] != chamado.responsavel_id:
        acoes.append("assumido")
    return (min(acoes, key=_ACOES.index) if acoes else ""), setor_anterior


def marcar_acao(sessao: Session, chamado: Chamado, acao: str) -> None:
    """Para mudanças gravadas por UPDATE direto (ex.: assumir, atômico), que o histórico do ORM não vê: a ação vai no próximo evento."""
    sessao.info.setdefault("chamados_acoes", {})[chamado.numero] = acao


def _anotar(sessao: Session, chamado: Chamado, tipo: str) -> None:
    if chamado.numero is None or chamado.setor_id is None:
        return
    pendentes: dict[int, Evento] = sessao.info.setdefault("chamados_eventos", {})
    anterior = pendentes.get(chamado.numero)
    acao, setor_anterior = _acao(chamado) if tipo == "alterado" else ("", None)
    marcada = sessao.info.get("chamados_acoes", {}).get(chamado.numero, "")
    if marcada and (not acao or _ACOES.index(marcada) < _ACOES.index(acao)):
        acao = marcada
    # Vários flushes na mesma transação: guarda a ação mais importante e o primeiro setor de antes
    if anterior is not None:
        if anterior.acao and (not acao or _ACOES.index(anterior.acao) < _ACOES.index(acao)):
            acao = anterior.acao
        setor_anterior = anterior.setor_anterior_id or setor_anterior
    pendentes[chamado.numero] = Evento(
        "novo" if tipo == "novo" or (anterior and anterior.tipo == "novo") else "alterado",
        chamado.numero, chamado.setor_id, chamado.solicitante_id, chamado.setor_solicitante_id, chamado.responsavel_id,
        acao, setor_anterior,
    )


@event.listens_for(Session, "after_flush")
def _coletar(sessao: Session, _contexto) -> None:
    # Cargas em lote (importação do GLPI) não acordam as telas: seriam milhares de eventos sem ninguém para ver
    if sessao.info.get("sem_tempo_real"):
        return
    for obj in sessao.new:
        if isinstance(obj, Chamado):
            _anotar(sessao, obj, "novo")
    for obj in list(sessao.dirty) + list(sessao.new) + list(sessao.deleted):
        if isinstance(obj, Chamado) and obj not in sessao.new and sessao.is_modified(obj, include_collections=False):
            _anotar(sessao, obj, "alterado")
        elif isinstance(obj, _FILHOS):
            # O chamado costuma estar carregado (a regra o leu antes); se não estiver, a própria mudança do chamado avisa
            chamado = sessao.identity_map.get(identity_key(Chamado, obj.chamado_id)) if obj.chamado_id else None
            if chamado is not None:
                _anotar(sessao, chamado, "alterado")


@event.listens_for(Session, "after_commit")
def _publicar_apos_commit(sessao: Session) -> None:
    sessao.info.pop("chamados_acoes", None)
    eventos = list(sessao.info.pop("chamados_eventos", {}).values())
    if eventos:
        publicar(eventos)


@event.listens_for(Session, "after_rollback")
def _descartar(sessao: Session) -> None:
    sessao.info.pop("chamados_eventos", None)
    sessao.info.pop("chamados_acoes", None)


@event.listens_for(Session, "after_soft_rollback")
def _descartar_parcial(sessao: Session, transacao) -> None:
    # Rollback de um ponto de salvamento (begin_nested): só a transação externa desfeita apaga a lista
    if transacao.parent is None:
        sessao.info.pop("chamados_eventos", None)
        sessao.info.pop("chamados_acoes", None)


def publicar(eventos: list[Evento]) -> None:
    """Manda os eventos aos processos (PostgreSQL) ou direto às conexões deste processo (SQLite). Falha aqui nunca derruba a regra."""
    if not _usa_postgres():
        for e in eventos:
            barramento.entregar(e)
        return
    try:
        with motor.connect() as conexao:
            for e in eventos:
                conexao.execute(text("SELECT pg_notify(:canal, :carga)"), {"canal": CANAL, "carga": e.para_json()})
            conexao.commit()
    except Exception:  # noqa: BLE001 — a tela atualiza na próxima consulta; o chamado já foi gravado
        log.exception("Não foi possível publicar %d evento(s) de tempo real", len(eventos))


# ---------------------------------------------------------------------------------------------
# Fluxo SSE
# ---------------------------------------------------------------------------------------------

async def fluxo(filtro: Callable[[Evento], bool], desconectou: Callable[[], object], *,
                duracao: float | None = None, ping: float | None = None) -> AsyncIterator[str]:
    """Texto do `text/event-stream`: `event: chamado` com `{tipo, numero, acao}` para cada evento que passa no filtro, mais o ping."""
    fila = barramento.assinar()
    duracao = DURACAO_MAXIMA if duracao is None else duracao
    ping = INTERVALO_PING if ping is None else ping
    fim = time.monotonic() + duracao
    try:
        # A tela espera 5 s antes de reconectar (o navegador usa o `retry`; o nosso cliente lê o mesmo valor)
        yield "retry: 5000\n: conectado\n\n"
        while (restante := fim - time.monotonic()) > 0:
            try:
                evento = await asyncio.wait_for(fila.get(), min(ping, restante))
            except TimeoutError:
                if await desconectou():
                    break
                yield ": ping\n\n"
                continue
            if filtro(evento):
                yield f"event: chamado\ndata: {json.dumps({'tipo': evento.tipo, 'numero': evento.numero, 'acao': evento.acao})}\n\n"
    finally:
        barramento.cancelar(fila)
