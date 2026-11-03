# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar, por ping, o IP de gerência de cada equipamento de rede e marcar quem está no ar ou fora do ar.
"""Teste de ping dos equipamentos de rede (rodado a cada minuto pelo timer `sgi-spi-rede-ping`).

Regras (decisão do usuário):
- testa **todo equipamento ativo com IP de gerência** (o patch panel não tem IP);
- a rodada roda no intervalo dos parâmetros da Rede (`ping_intervalo_min`, de 1 a 60 minutos; padrão 1). O timer chama a cada minuto e
  a rodada pula enquanto o intervalo não passou;
- **fora do ar** só depois de **3 falhas seguidas** (uma perda momentânea não troca nada); volta a **no ar** na primeira resposta;
- na topologia, o Core Secundário assume o lugar de referência quando o Primário está fora do ar (ver `servico.topologia`).

O `ping` do sistema é chamado com 1 pacote e 1 segundo de espera, vários em paralelo. Ele precisa da capacidade de rede do próprio
binário (`cap_net_raw`), por isso a unidade do systemd desta tarefa não usa `NoNewPrivileges`.
"""

import ipaddress
import logging
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rede import TIPOS_PASSIVOS, EquipamentoRede, ParametroRede

log = logging.getLogger("sgi_spi.rede")

# Falhas seguidas para dar o equipamento como fora do ar
FALHAS_PARA_FORA = 3
# Quantos pings ao mesmo tempo (a rodada inteira precisa caber em 1 minuto)
PARALELOS = 32
# Intervalo entre as rodadas (minutos): o padrão e os limites aceitos nos parâmetros
INTERVALO_PADRAO_MIN, INTERVALO_MINIMO, INTERVALO_MAXIMO = 1, 1, 60


def _parametro(sessao: Session, chave: str) -> str | None:
    linha = sessao.get(ParametroRede, chave)
    return linha.valor if linha else None


def _gravar_parametro(sessao: Session, chave: str, valor: str) -> None:
    linha = sessao.get(ParametroRede, chave)
    if linha is None:
        sessao.add(ParametroRede(chave=chave, valor=valor))
    else:
        linha.valor = valor


def intervalo_min(sessao: Session) -> int:
    try:
        valor = int(_parametro(sessao, "ping_intervalo_min") or INTERVALO_PADRAO_MIN)
    except ValueError:
        return INTERVALO_PADRAO_MIN
    return min(max(valor, INTERVALO_MINIMO), INTERVALO_MAXIMO)


def gravar_intervalo(sessao: Session, minutos: int) -> None:
    """Grava o intervalo entre as rodadas. Sem commit."""
    if not INTERVALO_MINIMO <= minutos <= INTERVALO_MAXIMO:
        raise ValueError(f"O intervalo entre os pings vai de {INTERVALO_MINIMO} a {INTERVALO_MAXIMO} minutos.")
    _gravar_parametro(sessao, "ping_intervalo_min", str(minutos))


def hora_da_rodada(sessao: Session, agora=None) -> bool:
    """Já passou o intervalo desde a última rodada? (folga de 10 s para o timer, que nunca bate o minuto exato)"""
    from datetime import datetime, timedelta

    agora = agora or agora_utc()
    ultima = _parametro(sessao, "ping_ultima_rodada")
    if not ultima:
        return True
    return agora - datetime.fromisoformat(ultima) >= timedelta(minutes=intervalo_min(sessao)) - timedelta(seconds=10)


def responde(ip: str) -> bool:
    """Um ping (1 pacote, espera de 1 s). IP inválido conta como sem resposta."""
    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    comando = ["ping", "-n", "-c", "1", "-W", "1", str(endereco)] if endereco.version == 4 else ["ping", "-6", "-n", "-c", "1", "-W", "1", str(endereco)]
    try:
        return subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def registrar(e: EquipamentoRede, respondeu: bool, agora) -> bool:
    """Aplica um resultado ao equipamento. Devolve True se a situação mudou (no ar ↔ fora)."""
    anterior = e.ping_situacao
    e.ping_verificado_em = agora
    if respondeu:
        e.ping_falhas, nova = 0, "no_ar"
    else:
        e.ping_falhas = (e.ping_falhas or 0) + 1
        # Até a 3ª falha seguida mantém o que estava (ou "sem teste", no primeiro uso)
        nova = "fora" if e.ping_falhas >= FALHAS_PARA_FORA else anterior
    if nova != anterior:
        e.ping_situacao, e.ping_mudou_em = nova, agora
        return True
    return False


def testar_todos(sessao: Session, testar: Callable[[str], bool] = responde) -> dict[str, int]:
    """Uma rodada: testa todos e grava. Sem commit. Devolve as contagens (testados, no_ar, fora, mudaram)."""
    alvos = list(sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.ativo.is_(True), EquipamentoRede.ip_gerencia != "",
                                                              EquipamentoRede.tipo.not_in(TIPOS_PASSIVOS))))
    with ThreadPoolExecutor(max_workers=PARALELOS) as grupo:
        resultados = list(grupo.map(lambda e: testar(e.ip_gerencia), alvos))
    agora = agora_utc()
    _gravar_parametro(sessao, "ping_ultima_rodada", agora.isoformat())
    mudaram = 0
    for e, ok in zip(alvos, resultados, strict=True):
        if registrar(e, ok, agora):
            mudaram += 1
            log.info("Rede: %s (%s) agora %s", e.nome, e.ip_gerencia, "no ar" if e.ping_situacao == "no_ar" else "fora do ar")
    return {"testados": len(alvos), "no_ar": sum(e.ping_situacao == "no_ar" for e in alvos),
            "fora": sum(e.ping_situacao == "fora" for e in alvos), "mudaram": mudaram}
