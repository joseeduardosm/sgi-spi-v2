# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a conferência das ordens bancárias no SIGEO: leitura da competência no texto livre, casamento e conclusão da etapa.
"""SIGEO: competência lida do texto da OB, casamento por processo + mês + líquido, conclusão automática e integração (só SuperRoot)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao, agora_utc
from app.models.contratos import Competencia, Contrato, NotaEmpenho
from app.models.contratos.execucao import NotaFiscalCompetencia, SelecaoNotaEmpenho
from app.services.contratos import servico_ob_sigeo as so
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url, equipe  # noqa: F401 - fixture reaproveitada


@pytest.mark.parametrize("texto, lancamento, esperado", [
    ("- 2A AMB. NF 91873 - 01/12/25 REF NOV/25", date(2026, 1, 2), date(2025, 11, 1)),
    ("VALE REFEICAO NF 08709949 REF. SET26", date(2026, 10, 1), date(2026, 9, 1)),
    ("NF 24548 DE 05/03/26 - REF. FEV/2026", date(2026, 3, 10), date(2026, 2, 1)),
    ("MANUT. PREDIAL NF. 1543 DE 14/08/26 JUL", date(2026, 8, 20), date(2026, 7, 1)),
    ("SERV.LIMPEZA NF 713 REF AGO/16", date(2026, 9, 10), date(2026, 8, 1)),  # ano digitado errado: vale o do lançamento
    ("NF 1093 DE 10SET26 (11 DIAS AGO/26)", date(2026, 9, 15), date(2026, 8, 1)),  # "10SET26" é a data da NF
    ("REF. 09/2026", date(2026, 10, 5), date(2026, 9, 1)),
    ("SETEMBRO DE 2026", date(2026, 10, 5), date(2026, 9, 1)),
    ("REF DEZ", date(2027, 1, 10), date(2026, 12, 1)),
    ("SER.MANUT. ELEVADOR NF 1114498 DE 16/12", date(2026, 1, 5), None),  # só a data da NF: sem competência
    ("NF 1 JUL/26 E AGO/26", date(2026, 9, 1), None),  # dois meses: ambíguo
])
def test_competencia_do_texto(texto, lancamento, esperado):
    assert so.competencia_do_texto(texto, lancamento) == esperado


def _linha(processo, codigo, valor, descricao, lancamento="2026-10-05"):
    return {"COD_PROCESSO": processo, "COD_DOCUMENTO": f"390001000012026OB{codigo:05d}", "TIPO_DOCUMENTO": "OB", "DATA_LANCAMENTO": lancamento,
            "VALOR_DOCUMENTO": str(valor), "DESCRICAO_DOCUMENTO": descricao, "CGC_CPF": "11222333000181"}


@pytest.fixture
def esperando_ob(cliente, equipe):  # noqa: F811
    """Competência 09/2026 do contrato na etapa da OB: NF de R$ 1.000,00 com R$ 100,00 retidos (líquido R$ 900,00) e uma NE selecionada."""
    contrato, gestora, _ = equipe
    _preparar_execucao(cliente, contrato, gestora)
    assert cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora).status_code == 200
    with FabricaSessao() as s:
        c = s.scalar(select(Competencia).where(Competencia.contrato_id == uuid.UUID(contrato["id"]), Competencia.competencia == date(2026, 9, 1), Competencia.tipo == "regular"))
        agora = agora_utc()
        c.medicao_concluida_em = c.nf_concluida_em = agora
        c.etapa_atual = "ordem_bancaria"
        s.add(NotaFiscalCompetencia(competencia_id=c.id, ordem=1, numero="1", valor_bruto=Decimal("1000.00"), retencao_ir=Decimal("100.00")))
        nota = s.scalar(select(NotaEmpenho).where(NotaEmpenho.contrato_id == c.contrato_id, NotaEmpenho.numero == "2026NE00002"))
        s.add(SelecaoNotaEmpenho(competencia_id=c.id, nota_id=nota.id, ordem=1))
        s.get(Contrato, c.contrato_id).processo_financeiro = "2024.0605.988"
        s.commit()
        return contrato, c.id, gestora


def test_conclui_quando_processo_mes_e_liquido_batem_em_partes(cliente, esperando_ob, monkeypatch):
    contrato, competencia_id, gestora = esperando_ob
    enviados = []
    monkeypatch.setattr("app.services.contratos.servico_notificacoes.notificar_ob", lambda a, b: enviados.append(b))
    linhas = [
        _linha("20240605988", 10, "800.00", "SERV. NF 1 REF SET/26 PARCIAL"),
        _linha("20240605988", 11, "100.00", "SERV. NF 1 SET/26 COMPLEMENTO"),
        _linha("20240605988", 12, "900.00", "SERV. NF 0 REF AGO/26"),  # outro mês: não entra
        _linha("99999999999", 13, "900.00", "OUTRO PROCESSO SET/26"),
    ]
    with FabricaSessao() as s:
        ensaio = so.conferir(s, linhas, ensaio=True)
    assert [c["ob"] for c in ensaio.concluidas] == ["2026OB00010, 2026OB00011"]
    with FabricaSessao() as s:
        assert s.get(Competencia, competencia_id).etapa_atual == "ordem_bancaria"  # o ensaio não grava
        r = so.conferir(s, linhas)
    assert len(r.concluidas) == 1 and enviados == [competencia_id]
    detalhe = cliente.get(_url(contrato, f"/competencias/{competencia_id}"), headers=gestora).json()
    assert detalhe["etapa_atual"] == "concluida" and detalhe["ob_origem"] == "sigeo" and detalhe["ob_numero"] == "2026OB00010, 2026OB00011"
    assert Decimal(detalhe["ob_valor"]) == Decimal("900.00") and detalhe["ordem_bancaria"]["nome"].startswith("comprovante-sigeo")
    # A NE foi debitada pelo valor a pagar (bruto), como no lançamento manual; rodar de novo não faz nada
    with FabricaSessao() as s:
        assert so.conferir(s, linhas).verificadas == 0


def test_nao_conclui_parcial_nem_sem_mes(cliente, esperando_ob, monkeypatch):
    contrato, competencia_id, gestora = esperando_ob
    monkeypatch.setattr("app.services.contratos.servico_notificacoes.notificar_ob", lambda a, b: None)
    with FabricaSessao() as s:
        r = so.conferir(s, [_linha("20240605988", 20, "800.00", "SERV. NF 1 REF SET/26 PARCIAL")])
    assert r.concluidas == [] and "faltam R$ 100,00" in r.pendencias[0]["motivo"]
    with FabricaSessao() as s:
        r = so.conferir(s, [_linha("20240605988", 21, "900.00", "SERV. NF 1 DE 03/10/26")])
    assert r.concluidas == [] and "sem mês legível" in r.pendencias[0]["motivo"]
    detalhe = cliente.get(_url(contrato, f"/competencias/{competencia_id}"), headers=gestora).json()
    assert detalhe["etapa_atual"] == "ordem_bancaria" and "sem mês legível" in detalhe["ob_sigeo_pendencia"]
    # Sem nenhuma OB do processo: só aguarda (não é pendência)
    with FabricaSessao() as s:
        r = so.conferir(s, [])
    assert r.aguardando == 1 and r.pendencias == []


def test_integracao_sigeo_so_superroot_e_senha_nunca_volta(cliente, admin):
    criar_usuario("comum-sigeo")
    assert cliente.get("/api/integracao-sigeo", headers=cabecalho(cliente, "comum-sigeo")).status_code == 403
    corpo = {"ativo": True, "url_base": "https://sigeo.exemplo/analytics/saw.dll", "caminho_analise": "/users/x/analise", "usuario": "u1", "senha": "segredo", "hora_conferencia": 9}
    r = cliente.put("/api/integracao-sigeo", json=corpo, headers=admin)
    assert r.status_code == 200 and r.json()["possui_senha"] is True and "segredo" not in r.text and r.json()["hora_conferencia"] == 9
    # Senha vazia preserva a gravada
    assert cliente.put("/api/integracao-sigeo", json={**corpo, "senha": ""}, headers=admin).json()["possui_senha"] is True


def test_contrato_com_dois_processos_e_hora_da_conferencia():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.services import servico_integracao_sigeo as si

    assert so.processos_do_contrato("20250139231, 20260315789") == {"20250139231", "20260315789"}
    assert so.processos_do_contrato("2025.0139.231; 2026.0315.789") == {"20250139231", "20260315789"}
    assert so.processos_do_contrato("") == set()
    config = SimpleNamespace(hora_conferencia=8, ultima_execucao_em=None)
    as_7 = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)  # 07:00 em Brasília
    as_9 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # 09:00 em Brasília
    assert not si.hora_de_conferir(config, as_7) and si.hora_de_conferir(config, as_9)
    config.ultima_execucao_em = datetime(2026, 10, 27, 11, 5, tzinfo=timezone.utc)  # já conferiu hoje às 08:05
    assert not si.hora_de_conferir(config, as_9)
