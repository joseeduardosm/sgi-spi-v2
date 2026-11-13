"""
===============================================================================
ARQUIVO: test_contratos_reajuste_limbo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar o "limbo" do reajuste: o que acontece com os meses medidos antes do
mês de referência (mes_referencia) quando o reajuste é aplicado depois.

RESUMO TÉCNICO:
Congela a data em 15/03/2026, gera a execução de um contrato iniciado em
janeiro/2026, mede janeiro e fevereiro e abre um reajuste com referência em
fevereiro. Confere pela API que só um mês entra na diferença retroativa e,
direto no banco (Competencia), que só o mês coberto fica marcado com o
reajuste em diferenca_coberta_por_reajuste_id.

FINALIDADE DE NEGÓCIO:
Protege a regra de que o reajuste só cobra diferença de preço dos meses a
partir da referência: o mês anterior (faturado com o preço antigo e fora do
alcance do índice) não é cobrado, e o mês coberto fica marcado para não ser
cobrado de novo por outro reajuste.

CONTEXTO NO SISTEMA:
Usa o roteiro de execução de test_contratos_execucao.py e os apoios de
tests/apoio_contratos.py. Exercita as rotas de reajustes e competências e
os serviços servico_reajuste e servico_competencias.

===============================================================================
"""

from datetime import date
import pytest

from tests.apoio_contratos import PDF, corpo_conclusao, criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    """Congela a data para que janeiro e fevereiro sejam meses passados (medíveis)."""
    # monkeypatch (fixture do pytest) troca a função "hoje" dos serviços só durante
    # o teste e a restaura sozinho no fim.
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com execução gerada; devolve (contrato_id, cabeçalho da gestora, ids das NEs)."""
    gestora = criar_usuario("gestora-limbo")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora})
    h = cabecalho(cliente, "gestora-limbo")
    _preparar_execucao(cliente, contrato, h)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=h).json()]
    return contrato, h, notas


def _medir(cliente, contrato, h, notas, identificador):
    """Mede o previsto e conclui a medição do mês indicado."""
    comp = cliente.get(_url(contrato, f"/competencias/identificador/{identificador}"), headers=h).json()
    base = _url(contrato, f"/competencias/{comp['id']}")
    corpo = {
        "itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in comp["itens"]],
        "notas_empenho_ids": notas,
    }
    assert cliente.put(f"{base}/medicao", json=corpo, headers=h).status_code == 200
    cliente.post(f"{base}/medicao/ciencia", headers=h)
    r = cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(base, notas), headers=h)
    assert r.status_code == 200, r.text
    return comp["id"]


def _abrir_reajuste(cliente, contrato, h, referencia, percentual="5"):
    """Cria um reajuste e aplica o mesmo percentual em todos os itens."""
    reajuste = cliente.post(
        _url(contrato, "/reajustes"),
        json={"sequencia_vigencia": 1, "mes_referencia": referencia},
        headers=h,
    ).json()["em_andamento"]
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    itens = [{"item_id": i["item_id"], "indice_percentual": percentual} for i in reajuste["itens"]]
    cliente.put(f"{url}/memoria", json={"itens": itens}, headers=h)
    return url, reajuste["id"]


def _concluir_reajuste(cliente, h, url):
    """Conclui o reajuste (evidência + arquivos + conclusão)."""
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    assert cliente.post(f"{url}/memoria/arquivos", headers=h).status_code == 200
    r = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_mes_antes_da_referencia_nao_entra_e_o_coberto_fica_marcado(cliente, cenario):
    """Janeiro (antes da referência de fevereiro) fica fora da diferença; fevereiro entra e, concluído, fica marcado."""
    # Imports locais: só este teste lê o banco direto para conferir a marcação.
    import uuid
    from app.core.banco import FabricaSessao
    from app.models.contratos.execucao import Competencia

    contrato, h, notas = cenario
    jan = _medir(cliente, contrato, h, notas, "2026-01")
    fev = _medir(cliente, contrato, h, notas, "2026-02")

    # Referência em fevereiro: janeiro fica antes dela e não deve entrar na diferença
    # (daí competencias_com_diferenca == 1).
    url, reajuste_id = _abrir_reajuste(cliente, contrato, h, "2026-02-01", percentual="10")
    em_andamento = cliente.get(_url(contrato, "/reajustes"), headers=h).json()["em_andamento"]
    assert em_andamento["competencias_com_diferenca"] == 1
    assert float(em_andamento["diferenca_retroativa"]) > 0

    _concluir_reajuste(cliente, h, url)
    # Confere no banco: só fevereiro aponta para o reajuste concluído; janeiro
    # continua sem marcação (ficou fora da diferença).
    with FabricaSessao() as sessao:
        assert sessao.get(Competencia, uuid.UUID(jan)).diferenca_coberta_por_reajuste_id is None
        assert sessao.get(Competencia, uuid.UUID(fev)).diferenca_coberta_por_reajuste_id == uuid.UUID(reajuste_id)
