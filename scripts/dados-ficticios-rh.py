#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar e remover dados fictícios de férias e licença-prêmio (demonstração e treinamento do Módulo RH).
"""Dados fictícios do Módulo RH: pessoas, dados funcionais e afastamentos para demonstrar o calendário e o painel.

Tudo fica em **usuários fictícios**, sem tocar em nenhum servidor real:
- login começando por `ficticio.` e nome começando por "[FICTÍCIO]";
- sem e-mail e sem senha: não entram no sistema e não recebem nada;
- os afastamentos são gravados direto no banco, sem avisos nem e-mails.

Criados:
- 12 pessoas em setores reais da SPI (os filtros do painel funcionam), com autorizadores também fictícios;
- pedidos **aguardando aprovação**, **aprovados** e **gozados**, de férias e de licença-prêmio;
- sobreposição num setor (alerta de setor) e uma pessoa com férias a vencer.

A remoção apaga os usuários fictícios, e com eles, em cascata, os dados funcionais, os períodos aquisitivos, os
afastamentos e o histórico deles. A CGP pode aprovar ou recusar os pendentes no Painel: os avisos vão para os
fictícios, que não têm e-mail.

Uso (na pasta backend/):
    .venv/bin/python ../scripts/dados-ficticios-rh.py            # mostra o que existe
    .venv/bin/python ../scripts/dados-ficticios-rh.py --criar    # cria (recria, se já existirem)
    .venv/bin/python ../scripts/dados-ficticios-rh.py --remover  # remove tudo
"""

import argparse
import sys
from datetime import date, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import delete, func, select  # noqa: E402

from app.core.banco import FabricaSessao, agora_utc  # noqa: E402
from app.models.rh import Afastamento, DadosFuncionais, EventoAfastamento  # noqa: E402
from app.models.setor import Setor  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.rh import servico_periodos  # noqa: E402
from app.services.rh.servico_afastamentos import hoje  # noqa: E402

PREFIXO = "ficticio."
MARCA = "[FICTÍCIO]"

# Setores reais da estrutura da SPI (os que não existirem no banco são trocados pelo primeiro disponível)
SETORES = [
    "Diretoria de Gestão de Parcerias em Transporte",
    "Coordenadoria de Finanças",
    "Coordenadoria de Gestão de Pessoas",
    "Ouvidoria",
]

# (login, nome, cargo, setor [índice em SETORES], início do período aquisitivo dd/mm, autorizador [login] ou None)
PESSOAS = [
    ("ficticio.chefe.transporte", "Carlos Mendes", "Diretor", 0, (1, 3), None),
    ("ficticio.ana", "Ana Paula Ribeiro", "Assessora Técnica", 0, (10, 1), "ficticio.chefe.transporte"),
    ("ficticio.bruno", "Bruno Almeida", "Analista", 0, (5, 6), "ficticio.chefe.transporte"),
    ("ficticio.camila", "Camila Duarte", "Analista", 0, (20, 2), "ficticio.chefe.transporte"),
    ("ficticio.daniel", "Daniel Farias", "Oficial Administrativo", 0, (15, 11), "ficticio.chefe.transporte"),
    ("ficticio.chefe.financas", "Helena Costa", "Coordenadora", 1, (1, 8), None),
    ("ficticio.eduardo", "Eduardo Lima", "Contador", 1, (12, 4), "ficticio.chefe.financas"),
    ("ficticio.fernanda", "Fernanda Rocha", "Analista", 1, (3, 9), "ficticio.chefe.financas"),
    ("ficticio.gustavo", "Gustavo Nunes", "Assistente", 1, (25, 10), "ficticio.chefe.financas"),
    ("ficticio.isabela", "Isabela Martins", "Analista de RH", 2, (7, 7), "ficticio.chefe.financas"),
    ("ficticio.joao", "João Pedro Santos", "Ouvidor Adjunto", 3, (18, 5), "ficticio.chefe.transporte"),
    ("ficticio.larissa", "Larissa Teixeira", "Assessora", 3, (30, 12), "ficticio.chefe.transporte"),
]


def _dia(base: date, dias: int) -> date:
    return base + timedelta(days=dias)


def afastamentos(ref: date) -> list[tuple[str, str, date, date, str]]:
    """(login, tipo, início, fim, situação), com datas relativas a hoje."""
    return [
        # Aguardando aprovação
        ("ficticio.ana", "ferias", _dia(ref, 35), _dia(ref, 49), "pendente"),
        ("ficticio.bruno", "ferias", _dia(ref, 40), _dia(ref, 54), "pendente"),
        ("ficticio.eduardo", "licenca_premio", _dia(ref, 45), _dia(ref, 59), "pendente"),
        ("ficticio.joao", "ferias", _dia(ref, 60), _dia(ref, 69), "pendente"),
        ("ficticio.gustavo", "ferias", _dia(ref, 38), _dia(ref, 47), "pendente"),
        # Aprovados (futuros e em curso)
        ("ficticio.camila", "ferias", _dia(ref, 42), _dia(ref, 56), "aprovado"),
        ("ficticio.fernanda", "ferias", _dia(ref, 2), _dia(ref, 16), "aprovado"),
        ("ficticio.isabela", "licenca_premio", _dia(ref, 20), _dia(ref, 34), "aprovado"),
        ("ficticio.larissa", "ferias", _dia(ref, 75), _dia(ref, 94), "aprovado"),
        ("ficticio.chefe.financas", "ferias", _dia(ref, 30), _dia(ref, 39), "aprovado"),
        # Já gozados
        ("ficticio.ana", "ferias", _dia(ref, -60), _dia(ref, -46), "gozado"),
        ("ficticio.eduardo", "ferias", _dia(ref, -40), _dia(ref, -31), "gozado"),
        ("ficticio.joao", "licenca_premio", _dia(ref, -25), _dia(ref, -16), "gozado"),
    ]


def _setores_existentes(sessao) -> list[str]:
    nomes = {s.nome for s in sessao.scalars(select(Setor).where(Setor.ativo.is_(True), Setor.sistemico.is_(False)))}
    reserva = next(iter(sorted(nomes)), "")
    return [n if n in nomes else reserva for n in SETORES]


def remover(sessao) -> int:
    ids = list(sessao.scalars(select(Usuario.id).where(Usuario.login.startswith(PREFIXO))))
    if ids:
        # Tira os fictícios de autorizador e superior de quem quer que seja, antes de apagar
        for d in sessao.scalars(select(DadosFuncionais).where(DadosFuncionais.autorizador_id.in_(ids) | DadosFuncionais.substituto_id.in_(ids))):
            d.autorizador_id = None if d.autorizador_id in ids else d.autorizador_id
            d.substituto_id = None if d.substituto_id in ids else d.substituto_id
        sessao.execute(delete(Usuario).where(Usuario.id.in_(ids)))
    return len(ids)


def criar(sessao) -> dict:
    remover(sessao)
    sessao.flush()
    ref = hoje()
    setores = _setores_existentes(sessao)
    usuarios: dict[str, Usuario] = {}
    for login, nome, cargo, setor, _, _ in PESSOAS:
        u = Usuario(login=login, nome_completo=f"{MARCA} {nome}", cargo=cargo, departamento=setores[setor], email="", ativo=True,
                    ramal="0000", andar="1", predio="Fictício", perfil_revisado_em=agora_utc())
        sessao.add(u)
        usuarios[login] = u
    sessao.flush()
    for login, _, _, _, (dia, mes), autorizador in PESSOAS:
        u = usuarios[login]
        u.gestor_id = usuarios[autorizador].id if autorizador else None
        sessao.add(DadosFuncionais(
            usuario_id=u.id, autorizador_id=usuarios[autorizador].id if autorizador else None, sem_superior=autorizador is None,
            inicio_aquisitivo_dia=dia, inicio_aquisitivo_mes=mes, exercicio=ref.year, saldo_lp_dias=90,
            jornada_semanal_horas=40, regime_plantao=False, horario_trabalho_inicio=time(9), horario_trabalho_fim=time(18),
            horario_estudante=False, intervalo_inicio=time(12), intervalo_fim=time(13),
            rg_cin="00.000.000-0", rs_pv="0.000.000/0", atualizado_por_nome="Dados fictícios", atualizado_em=agora_utc(),
        ))
    sessao.flush()
    for u in usuarios.values():
        servico_periodos.vigente(sessao, u.id, ref)
    contagem = {"pendente": 0, "aprovado": 0, "gozado": 0}
    for login, tipo, inicio, fim, situacao in afastamentos(ref):
        u = usuarios[login]
        periodo = servico_periodos.obter(sessao, u.id, *servico_periodos.limites(*_inicio(login), inicio)) if tipo == "ferias" else None
        a = Afastamento(usuario_id=u.id, tipo=tipo, inicio=inicio, fim=fim, dias=(fim - inicio).days + 1, exercicio=inicio.year,
                        status=situacao, solicitado_em=agora_utc(), periodo_aquisitivo_id=periodo.id if periodo else None)
        if situacao != "pendente":
            aprovador = usuarios.get(_autorizador(login) or "ficticio.chefe.financas")
            a.decidido_por_id, a.decidido_por_nome, a.decidido_em = aprovador.id, aprovador.nome_completo, agora_utc()
        sessao.add(a)
        sessao.flush()
        sessao.add(EventoAfastamento(afastamento_id=a.id, de=None, para="pendente", autor_nome=u.nome_completo, ocorrido_em=agora_utc()))
        if situacao != "pendente":
            sessao.add(EventoAfastamento(afastamento_id=a.id, de="pendente", para="aprovado", autor_nome=a.decidido_por_nome, ocorrido_em=agora_utc()))
        if situacao == "gozado":
            sessao.add(EventoAfastamento(afastamento_id=a.id, de="aprovado", para="gozado", autor_nome="Sistema", ocorrido_em=agora_utc()))
        contagem[situacao] += 1
    return {"pessoas": len(usuarios), **contagem}


def _inicio(login: str) -> tuple[int, int]:
    return next(p[4] for p in PESSOAS if p[0] == login)


def _autorizador(login: str) -> str | None:
    return next(p[5] for p in PESSOAS if p[0] == login)


def situacao(sessao) -> str:
    ids = select(Usuario.id).where(Usuario.login.startswith(PREFIXO))
    pessoas = sessao.scalar(select(func.count()).select_from(Usuario).where(Usuario.login.startswith(PREFIXO)))
    por_status = dict(sessao.execute(select(Afastamento.status, func.count()).where(Afastamento.usuario_id.in_(ids)).group_by(Afastamento.status)).all())
    return f"{pessoas} pessoa(s) fictícia(s); afastamentos: {por_status or 'nenhum'}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--criar", action="store_true", help="Cria os dados fictícios (apaga os anteriores antes).")
    grupo.add_argument("--remover", action="store_true", help="Remove todos os dados fictícios.")
    args = parser.parse_args()
    with FabricaSessao() as sessao:
        if args.criar:
            print("Criado:", criar(sessao))
            sessao.commit()
        elif args.remover:
            print(f"Removida(s) {remover(sessao)} pessoa(s) fictícia(s) e tudo o que era delas.")
            sessao.commit()
        print("Situação:", situacao(sessao))
    return 0


if __name__ == "__main__":
    sys.exit(main())
