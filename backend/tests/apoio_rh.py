# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir os auxiliares dos testes do Módulo RH.
"""Auxiliares dos testes do RH: setor da CGP, dados funcionais e SMTP simulado."""

import smtplib

from app.core.banco import FabricaSessao
from app.models.rh import DadosFuncionais
from app.models.setor import MembroSetor, Setor
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado


def criar_cgp(*membros: int) -> int:
    """Setor "Coordenadoria de Gestão de Pessoas" (com um filho) e os membros informados."""
    with FabricaSessao() as sessao:
        cgp = Setor(nome="Coordenadoria de Gestão de Pessoas")
        sessao.add(cgp)
        sessao.flush()
        sessao.add(Setor(nome="Núcleo de Folha", setor_pai_id=cgp.id))
        for u in membros:
            sessao.add(MembroSetor(setor_id=cgp.id, usuario_id=u))
        sessao.commit()
        return cgp.id


def funcionais(usuario_id: int, **campos) -> None:
    with FabricaSessao() as sessao:
        registro = sessao.get(DadosFuncionais, usuario_id) or DadosFuncionais(usuario_id=usuario_id)
        for c, v in campos.items():
            setattr(registro, c, v)
        sessao.add(registro)
        sessao.commit()


def simular_smtp(monkeypatch) -> None:
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)
