#!/usr/bin/env python3
"""
===============================================================================
ARQUIVO: migrar-reserva-espacos-243.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migrar a reserva de espaços do servidor 10.23.1.243 (espaços, reservas,
eventos e fiscais) para o módulo Reserva de Espaços do SGI SPI.

RESUMO TÉCNICO:
Lê o pacote de `scripts/extrair-reserva-espacos-243.py` (CSVs):
- objetos viram espaços (id antigo em `origem_id`, recarga idempotente);
- reservas viram reservas (id antigo em `origem_id`, `serie_id`, status,
  justificativa e datas de criação preservados);
- eventos viram a linha do tempo (o payload original vai em `detalhes`);
- usuários antigos são ligados aos usuários do SGI pelo login; sem
  correspondência (ex.: root) ficam só com o nome;
- fiscais = membros do grupo de fiscais da origem que existem no SGI;
- data com ano absurdo (ex.: 0020-06-22, reserva de teste) tem o ano
  corrigido para 2026.
Nenhum aviso é disparado (as reservas entram com o lembrete já marcado como
enviado). Imprime uma conferência das contagens por status.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-reserva-espacos-243.py <pacote>           # ensaio
    .venv/bin/python ../scripts/migrar-reserva-espacos-243.py <pacote> --gravar  # grava
    ... --gravar --substituir   # apaga antes espaços e reservas com id de origem

FINALIDADE DE NEGÓCIO:
Mantém a agenda dos espaços da SPI (salas, auditório etc.) e o histórico de
pedidos, deferimentos e indeferimentos ao trocar o sistema antigo pelo SGI,
sem conflitos de horário nem perda de reservas futuras.

CONTEXTO NO SISTEMA:
Usa os modelos de app.models.reserva_espacos (EspacoReservavel,
ReservaEspaco, EventoReservaEspaco, FiscalReservaEspacos) e Usuario. Esta
docstring aparece no --help (o argparse a usa como descrição). Roda fora da
API, a partir da pasta backend.

===============================================================================
"""

import argparse
import csv
import json
import sys
import uuid
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path

# Coloca a pasta backend/ no caminho de importação para usar os modelos do sistema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.reserva_espacos import EspacoReservavel, EventoReservaEspaco, FiscalReservaEspacos, ReservaEspaco  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

# Ano usado para corrigir datas de teste com ano absurdo (menor que 1000).
ANO_CORRIGIDO = 2026


def _ler(pacote: Path, nome: str) -> list[dict]:
    """Lê `<pacote>/<nome>.csv` como lista de dicionários (uma linha por registro)."""
    with open(pacote / f"{nome}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _instante(valor: str | None) -> datetime | None:
    """Converte a data/hora ISO do CSV em datetime (None se vazia)."""
    return datetime.fromisoformat(valor) if valor else None


def _data(valor: str) -> date:
    """Converte a data ISO; ano menor que 1000 (dado de teste) vira ANO_CORRIGIDO."""
    d = date.fromisoformat(valor)
    return d.replace(year=ANO_CORRIGIDO) if d.year < 1000 else d


def _nome_antigo(u: dict) -> str:
    """Nome completo do usuário antigo (ou o login, se não houver nome)."""
    return (f"{u['first_name']} {u['last_name']}".strip()) or u["username"]


def migrar(pacote: Path, gravar: bool, substituir: bool) -> int:
    """Carrega espaços, reservas, eventos e fiscais do pacote numa transação.

    Parâmetros: `pacote` (pasta com os CSVs), `gravar` (commit em vez de
    rollback) e `substituir` (apaga antes a carga anterior). Imprime a
    conferência e devolve o código de saída (0).
    """
    objetos, reservas, eventos = _ler(pacote, "objetos"), _ler(pacote, "reservas"), _ler(pacote, "eventos")
    usuarios_antigos = {int(u["id"]): u for u in _ler(pacote, "usuarios")}
    fiscais = [f["username"] for f in _ler(pacote, "fiscais")]
    relatorio: list[str] = []
    with FabricaSessao() as sessao:
        # --substituir: apaga o que veio de cargas anteriores (só registros com origem_id).
        if substituir:
            sessao.execute(delete(ReservaEspaco).where(ReservaEspaco.origem_id.is_not(None)))
            sessao.execute(delete(EspacoReservavel).where(EspacoReservavel.origem_id.is_not(None)))
            sessao.flush()
        # Usuários do SGI indexados pelo login em minúsculas, para casar com os antigos.
        por_login = {u.login.lower(): u for u in sessao.scalars(select(Usuario))}

        def usuario_sgi(id_antigo: int | None) -> tuple[Usuario | None, str]:
            """Devolve (usuário do SGI ou None, nome para exibir) a partir do id antigo; anota no relatório quem não foi achado."""
            antigo = usuarios_antigos.get(id_antigo or 0)
            if not antigo:
                return None, ""
            sgi = por_login.get(antigo["username"].lower())
            if sgi is None:
                relatorio.append(f"sem usuário no SGI: {antigo['username']} (mantido só o nome)")
            return sgi, (sgi.nome_completo or sgi.login) if sgi else _nome_antigo(antigo)

        # Espaços: procura pelo id de origem e, se não achar, pelo nome (sem diferenciar
        # maiúsculas); cria quando não existe e atualiza os dados da origem.
        espacos: dict[int, EspacoReservavel] = {}
        for o in objetos:
            e = sessao.scalar(select(EspacoReservavel).where(EspacoReservavel.origem_id == int(o["id"]))) \
                or sessao.scalar(select(EspacoReservavel).where(func.lower(EspacoReservavel.nome) == o["nome"].lower()))
            if e is None:
                e = EspacoReservavel(origem_id=int(o["id"]))
                sessao.add(e)
            e.origem_id = int(o["id"])
            e.nome, e.localizacao, e.cor, e.ativo = o["nome"], o["localizacao"], o["cor"], o["ativo"] == "t"
            e.criado_em = _instante(o["criado_em"]) or e.criado_em
            sessao.flush()
            espacos[int(o["id"])] = e

        # Reservas: só cria as que ainda não vieram (idempotência pelo origem_id).
        novas: dict[int, ReservaEspaco] = {}
        for r in reservas:
            if sessao.scalar(select(ReservaEspaco.id).where(ReservaEspaco.origem_id == int(r["id"]))):
                continue
            criador, nome_criador = usuario_sgi(int(r["criado_por_id"]) if r["criado_por_id"] else None)
            fiscal, nome_fiscal = usuario_sgi(int(r["fiscal_responsavel_id"]) if r["fiscal_responsavel_id"] else None)
            # lembrete_enviado=True evita que o sistema mande lembrete de reservas migradas.
            nova = ReservaEspaco(
                origem_id=int(r["id"]), espaco_id=espacos[int(r["objeto_id"])].id, data=_data(r["data"]), hora_inicio=time.fromisoformat(r["hora_inicio"]),
                hora_fim=time.fromisoformat(r["hora_fim"]), titulo=r["titulo"], responsavel_nome=r["responsavel"], observacoes=r["observacoes"],
                solicitante_id=criador.id if criador else None, solicitante_nome=nome_criador, status=r["status"],
                fiscal_id=fiscal.id if fiscal else None, fiscal_nome=nome_fiscal, justificativa=r["justificativa_indeferimento"],
                serie_id=uuid.UUID(r["serie_id"]) if r["serie_id"] else None, lembrete_enviado=True,
                criado_em=_instante(r["criado_em"]), atualizado_em=_instante(r["atualizado_em"]),
            )
            # O responsável é texto livre na origem; quando bate com o nome de um usuário do SGI, liga-se a ele
            responsavel = next((u for u in por_login.values() if (u.nome_completo or "").lower() == r["responsavel"].strip().lower()), None)
            nova.responsavel_id = responsavel.id if responsavel else None
            sessao.add(nova)
            sessao.flush()
            novas[int(r["id"])] = nova

        # Eventos: viram a linha do tempo das reservas criadas nesta carga.
        for ev in eventos:
            reserva = novas.get(int(ev["reserva_id"]))
            if reserva is None:
                continue
            autor, nome_autor = usuario_sgi(int(ev["usuario_id"]) if ev["usuario_id"] else None)
            reserva.eventos.append(EventoReservaEspaco(
                tipo=ev["acao"], usuario_id=autor.id if autor else None, usuario_nome=nome_autor or "Sistema",
                detalhes=json.loads(ev["payload"]) if ev["payload"] else None, criado_em=_instante(ev["criado_em"]),
            ))

        # Fiscais: só entram os que existem no SGI e ainda não estão cadastrados.
        ja = set(sessao.scalars(select(FiscalReservaEspacos.usuario_id)))
        for login in fiscais:
            sgi = por_login.get(login.lower())
            if sgi is None:
                relatorio.append(f"fiscal sem usuário no SGI: {login}")
            elif sgi.id not in ja:
                sessao.add(FiscalReservaEspacos(usuario_id=sgi.id))
        sessao.flush()

        # Conferência contra a origem
        total_antigo = Counter(r["status"] for r in reservas)
        total_novo = Counter(sessao.scalars(select(ReservaEspaco.status).where(ReservaEspaco.origem_id.is_not(None))))
        print(f"espaços: {len(objetos)} na origem, {sessao.scalar(select(func.count(EspacoReservavel.id)).where(EspacoReservavel.origem_id.is_not(None)))} no SGI")
        print(f"reservas novas nesta carga: {len(novas)} de {len(reservas)}; eventos na origem: {len(eventos)}")
        print("status origem:", dict(total_antigo), "| SGI:", dict(total_novo))
        for linha in sorted(set(relatorio)):
            print("aviso:", linha)
        if total_antigo != total_novo:
            print("ATENÇÃO: contagens por status diferentes (esperado quando a carga já havia sido feita e há alterações no SGI).")
        # Ensaio por padrão: rollback desfaz tudo; só --gravar confirma (commit).
        if gravar:
            sessao.commit()
            print("GRAVADO.")
        else:
            sessao.rollback()
            print("Ensaio concluído: nada foi gravado (use --gravar).")
    return 0


if __name__ == "__main__":
    # A docstring do módulo é a descrição do --help (RawDescription mantém as quebras de linha).
    analisador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analisador.add_argument("pacote", type=Path)
    analisador.add_argument("--gravar", action="store_true")
    analisador.add_argument("--substituir", action="store_true")
    argumentos = analisador.parse_args()
    sys.exit(migrar(argumentos.pacote, argumentos.gravar, argumentos.substituir))
