"""
===============================================================================
ARQUIVO: test_empenho_sigeo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar o cadastro automático das NEs (notas de empenho) e dos cancelamentos
a partir da análise de empenhos exportada do SIGEO.

RESUMO TÉCNICO:
Testa as funções de app/services/contratos/servico_empenho_sigeo.py:
numero_curto, empenhos_por_processo (separa NEs e cancelamentos) e
cadastrar (modo ensaio, que não grava, e modo real). As linhas imitam as
colunas da planilha do SIGEO (COD_PROCESSO, COD_DOCUMENTO, VALOR_DOCUMENTO
etc.). Confere idempotência, pendências e a rota restrita a SuperRoot.

FINALIDADE DE NEGÓCIO:
SIGEO é o sistema de execução orçamentária do Estado; a NE reserva o
orçamento para pagar o contrato. O cadastro automático só preenche
contratos que têm Processo Financeiro e ainda não têm NE, evitando
duplicar ou sobrescrever o que a equipe já lançou. Cancelamento maior que a
NE vira pendência para análise humana.

CONTEXTO NO SISTEMA:
Serviço servico_empenho_sigeo, modelos Contrato e NotaEmpenho e a rota
/api/integracao-sigeo/empenhos (só SuperRoot, o papel administrativo do
sistema). Reaproveita a fixture equipe de test_contratos_execucao.py.

===============================================================================
"""

import uuid

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.contratos import Contrato, NotaEmpenho
from app.models.usuario import Usuario
from app.services.contratos import servico_empenho_sigeo as se
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _url, equipe  # noqa: F401 - fixture reaproveitada


def _linha(processo, documento, valor, origem=None, data="2025-03-10", texto="SERVICOS DE LOCACAO"):
    """Monta uma linha da análise de empenhos do SIGEO.

    documento e origem são os números sequenciais da NE (origem aponta a NE
    cancelada; valor negativo = cancelamento).
    """
    return {"COD_PROCESSO": processo, "COD_DOCUMENTO": f"390105000012025NE{documento:05d}", "COD_DOCUMENTO_ORIGEM": f"390105000012025NE{(origem or documento):05d}",
            "TIPO_DOCUMENTO": "NE", "VALOR_DOCUMENTO": str(valor), "DATA_LANCAMENTO": data, "DESCRICAO_DOCUMENTO": texto}


def test_numero_curto_e_separacao_de_nes_e_cancelamentos():
    """Reduz o código longo ao número curto da NE e agrupa NEs e cancelamentos por processo.

    Cancelamento de NE ausente da análise fica separado (sem_nota).
    """
    assert se.numero_curto("390105000012025NE00028") == "2025NE00028" and se.numero_curto("lixo") == ""
    linhas = [_linha("20250139231", 5, "300000.00"), _linha("20250139231", 11, "-232308.00", origem=5, texto="CANCELAMENTO DA NOTA DE EMPENHO 2025NE00005"),
              _linha("20250139231", 12, "-10.00", origem=99)]  # cancelamento de NE que não está na análise
    nes, sem_nota = se.empenhos_por_processo(linhas)
    assert [(n.numero, n.valor, [(c.numero, c.valor) for c in n.cancelamentos]) for n in nes["20250139231"]] == [("2025NE00005", se.Decimal("300000.00"), [("2025NE00011", se.Decimal("232308.00"))])]
    assert [(c.numero, c.nota) for c in sem_nota["20250139231"]] == [("2025NE00012", "2025NE00099")]


@pytest.fixture
def contrato_sem_ne(cliente, equipe):  # noqa: F811
    """Contrato da fixture equipe com dois Processos Financeiros gravados direto no banco e nenhuma NE."""
    contrato, gestora, _ = equipe
    with FabricaSessao() as s:
        s.get(Contrato, uuid.UUID(contrato["id"])).processo_financeiro = "2025.0139.231, 20260315789"
        s.commit()
    return contrato


def test_cadastra_nes_e_cancelamentos_so_de_contrato_sem_ne(cliente, contrato_sem_ne):
    """Ensaio conta sem gravar; o cadastro real grava NEs, cancelamentos e saldo, e repetir não cadastra de novo."""
    linhas = [_linha("20250139231", 5, "300000.00"), _linha("20250139231", 11, "-232308.00", origem=5, texto="CANCELAMENTO DO EMPENHO 2025NE00005"),
              _linha("20250139231", 6, "1000.00"), _linha("20260315789", 7, "500.00"), _linha("99999999999", 8, "1.00")]
    with FabricaSessao() as s:
        autor = s.scalar(select(Usuario).where(Usuario.login == "root")) or s.scalar(select(Usuario))
        ensaio = se.cadastrar(s, linhas, autor, ensaio=True)
        assert ensaio.nes_cadastradas == 3 and ensaio.cancelamentos == 1
        assert s.scalar(select(NotaEmpenho).where(NotaEmpenho.contrato_id == uuid.UUID(contrato_sem_ne["id"]))) is None  # o ensaio não grava
        r = se.cadastrar(s, linhas, autor)
        assert r.nes_cadastradas == 3 and r.cancelamentos == 1 and r.pendencias == []
        notas = {n.numero: n for n in s.scalars(select(NotaEmpenho).where(NotaEmpenho.contrato_id == uuid.UUID(contrato_sem_ne["id"])))}
        assert set(notas) == {"2025NE00005", "2025NE00006", "2025NE00007"}
        n5 = notas["2025NE00005"]
        assert n5.valor_original == se.Decimal("300000.00") and n5.cancelado == se.Decimal("232308.00") and n5.saldo == se.Decimal("67692.00")
        assert [c.numero for c in n5.cancelamentos] == ["2025NE00011"] and "SIGEO" in n5.cancelamentos[0].justificativa
        # Idempotente: agora o contrato já tem NE e nada mais é cadastrado
        assert se.cadastrar(s, linhas, autor).nes_cadastradas == 0


def test_pendencias_e_contrato_sem_empenho_no_sigeo(cliente, contrato_sem_ne):
    """Cancelamento acima da NE vira pendência; contrato sem nenhuma NE na análise é listado à parte."""
    with FabricaSessao() as s:
        autor = s.scalar(select(Usuario))
        # Cancelamentos acima do valor da NE: a NE não é cadastrada e vira pendência
        r = se.cadastrar(s, [_linha("20250139231", 5, "100.00"), _linha("20250139231", 11, "-150.00", origem=5)], autor)
        assert r.nes_cadastradas == 0 and "passam do valor" in r.pendencias[0]["motivo"]
        # Nenhuma NE do processo na análise: o contrato é listado
        r = se.cadastrar(s, [_linha("11111111111", 1, "10.00")], autor)
        assert r.nes_cadastradas == 0 and len(r.sem_empenho_no_sigeo) == 1


def test_rota_de_empenhos_so_superroot(cliente, admin):
    """Usuário comum leva 403 na rota de importação de empenhos."""
    criar_usuario("comum-emp")
    assert cliente.post("/api/integracao-sigeo/empenhos", headers=cabecalho(cliente, "comum-emp")).status_code == 403
