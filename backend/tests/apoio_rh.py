"""
===============================================================================
ARQUIVO: apoio_rh.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Reúne os auxiliares dos testes do Módulo RH: setor da CGP, dados
funcionais e SMTP simulado.

RESUMO TÉCNICO:
criar_cgp cria o setor "Coordenadoria de Gestão de Pessoas" com um filho e
membros; funcionais grava DadosFuncionais do usuário; simular_smtp troca
smtplib.SMTP e SMTP_SSL pelas classes simuladas de test_smtp, que guardam
as mensagens em memória em vez de enviar.

FINALIDADE DE NEGÓCIO:
O RH depende da CGP (Coordenadoria de Gestão de Pessoas), que recebe e trata
as solicitações dos servidores; os testes precisam desse setor e de dados
funcionais para reproduzir os fluxos e conferir os e-mails enviados.

CONTEXTO NO SISTEMA:
Modelos DadosFuncionais (rh), Setor e MembroSetor; tests/test_smtp
(SmtpSimulado, SmtpSslSimulado). Usado pelos test_rh_*.py.

===============================================================================
"""
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
        # flush envia o INSERT sem encerrar a transação, para cgp.id já existir antes do commit.
        sessao.flush()
        sessao.add(Setor(nome="Núcleo de Folha", setor_pai_id=cgp.id))
        for u in membros:
            sessao.add(MembroSetor(setor_id=cgp.id, usuario_id=u))
        sessao.commit()
        return cgp.id


def funcionais(usuario_id: int, **campos) -> None:
    """Grava (cria ou atualiza) os dados funcionais do usuário com os campos informados."""
    with FabricaSessao() as sessao:
        registro = sessao.get(DadosFuncionais, usuario_id) or DadosFuncionais(usuario_id=usuario_id)
        for c, v in campos.items():
            setattr(registro, c, v)
        sessao.add(registro)
        sessao.commit()


def simular_smtp(monkeypatch) -> None:
    """Troca o SMTP real pelo simulado durante o teste e zera as mensagens e conexões registradas.

    `monkeypatch` é a fixture do pytest que substitui um atributo e o restaura ao fim do teste.
    """
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)
