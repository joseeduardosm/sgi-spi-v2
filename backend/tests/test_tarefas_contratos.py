# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a integração Contratos × Tarefas: tarefas de cada etapa da competência, controle pelo módulo de contratos e histórico.
"""Tarefas das competências de contratos (`servico_tarefas_contratos`)."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.contratos import Competencia, Contrato
from app.models.rh import Feriado
from app.models.tarefas import EventoTarefa, Tarefa
from app.models.usuario import Usuario
from app.services.contratos import servico_competencias, servico_tarefas_contratos as stc
from app.services.tarefas import servico_tarefas as servico
from tests.apoio_contratos import PDF, conferir_retencao, juntar_nf
from tests.conftest import cabecalho
from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 — fixtures
from tests.test_contratos_recusa_nf import JUSTIFICATIVA

# Competência 01/2026: fim do período em 31/01, virada (n) em 01/02/2026 (domingo); "hoje" dos testes: 15/03/2026
HOJE = date(2026, 3, 15)


_DIA = {"hoje": date(2026, 1, 10)}  # antes da virada de 01/2026: a integração fica quieta enquanto o cenário é montado


@pytest.fixture(autouse=True)
def _corte(monkeypatch):
    """A competência de teste é de janeiro: libera o corte de cobrança e controla o "hoje" da integração (`_ligar` avança para 15/03)."""
    _DIA["hoje"] = date(2026, 1, 10)
    monkeypatch.setattr(servico_competencias, "PENDENCIAS_A_PARTIR_DE", date(2026, 1, 1))
    monkeypatch.setattr(stc, "hoje_sao_paulo", lambda: _DIA["hoje"])


def _ligar() -> None:
    """Passa o "hoje" da integração para 15/03/2026: a competência de janeiro já foi liberada."""
    _DIA["hoje"] = HOJE


def _tarefas() -> dict[str, Tarefa]:
    """Tarefas da competência de janeiro, por chave da etapa."""
    with FabricaSessao() as s:
        janeiro = s.scalar(select(Competencia.id).where(Competencia.competencia == date(2026, 1, 1)))
        lista = list(s.scalars(select(Tarefa).where(Tarefa.origem_tipo == stc.ORIGEM, Tarefa.origem_id == janeiro)))
        for t in lista:
            s.expunge(t)
        return {t.origem_chave: t for t in lista}


def _sincronizar(ensaio: bool = False) -> stc.Resultado:
    _ligar()
    with FabricaSessao() as s:
        return stc.sincronizar_todas(s, HOJE, ensaio=ensaio)


def _estados() -> dict[str, str]:
    return {k: t.status for k, t in _tarefas().items()}


def test_virada_cria_as_tarefas_de_cada_etapa_e_espelha_a_medicao_concluida(cliente, cenario):
    r = _sincronizar()
    assert r.erros == [] and set(_tarefas()) == {"medicao", "nf:1", "retencao:1:1", "cadin", "checklist", "consolidado", "sei", "despachar", "ob"}
    estados = _estados()
    # Medição já concluída em Contratos: nasce concluída; as demais nascem a fazer (SEI e despacho são manuais)
    assert estados["medicao"] == "concluida"
    assert {estados[k] for k in ("nf:1", "retencao:1:1", "cadin", "checklist", "consolidado", "sei", "despachar", "ob")} == {"a_fazer"}
    tarefas = _tarefas()
    medicao = tarefas["medicao"]
    assert medicao.controlada_externamente and medicao.titulo.startswith("Medição — ") and medicao.titulo.endswith("001/2026 — 01/2026") and medicao.equipe.nome == "Contratos"
    assert "Tarefa criada pelo módulo Contratos somente para dimensionamento e monitoramento do trabalho" in medicao.descricao
    assert not tarefas["sei"].controlada_externamente and "Tarefa criada pelo módulo Contratos" not in tarefas["sei"].descricao
    # Responsáveis = equipe vigente do contrato (gestora primeiro); o conjunto de marcadores traz o contrato e a etapa
    assert {m.nome for m in medicao.marcadores} == {"001/2026", "Medição"}
    assert medicao.responsavel_id is not None


def test_equipe_contratos_recebe_os_membros_e_tira_as_tarefas_da_fila_pessoal(cliente, cenario):
    _sincronizar()
    medicao = _tarefas()["medicao"]
    with FabricaSessao() as s:
        equipe = s.get(Tarefa, medicao.id).equipe
        membros = servico.membros(equipe)
        assert medicao.responsavel_id in membros
        responsavel = s.get(Usuario, medicao.responsavel_id)
        # Continua responsável, mas a tarefa de contratos não aparece em "Minhas tarefas" (só na equipe)
        assert medicao.id not in {t.id for t in servico.minhas(s, responsavel)}
        assert medicao.id in {t.id for t in servico.da_equipe(s, responsavel, equipe.id)[1]}


def test_titulo_traz_apelido_e_numero_do_contrato():
    class _C:
        def __init__(self, apelido, numero): self.apelido, self.numero = apelido, numero

    assert stc._rotulo_contrato(_C("Limpeza", "001/2026")) == "Limpeza - 001/2026"
    assert stc._rotulo_contrato(_C("  ", "001/2026")) == "001/2026"


def test_prazos_em_dias_uteis_contados_da_virada(cliente, cenario):
    _sincronizar()
    t = _tarefas()

    def dia(chave):
        return stc._data_local(t[chave].prazo)

    # n = 01/02/2026 (domingo): n+2 = terça 03/02; n+4 = quinta 05/02; n+5 = sexta 06/02; n+6 = segunda 09/02; n+7 = terça 10/02
    assert [dia(c) for c in ("medicao", "nf:1", "retencao:1:1", "cadin", "sei")] == [date(2026, 2, 3), date(2026, 2, 5), date(2026, 2, 6), date(2026, 2, 9), date(2026, 2, 10)]
    # Juntar a OB: sem NF, n + 30 dias corridos
    assert dia("ob") == date(2026, 3, 3)
    # 06/02 é feriado: depois de quinta 05/02, o 1º dia útil é segunda 09/02 e o 2º é terça 10/02
    assert stc.somar_uteis(date(2026, 2, 5), 2, {date(2026, 2, 6)}) == date(2026, 2, 10)


def test_idempotente_e_ensaio_nao_grava(cliente, cenario):
    antes = _sincronizar(ensaio=True)
    assert antes.criadas == 18 and _tarefas() == {}  # janeiro e fevereiro, 9 tarefas cada
    primeiro = _sincronizar()
    segundo = _sincronizar()
    assert primeiro.criadas == 18 and segundo.criadas == 0 and segundo.atualizadas == 0
    with FabricaSessao() as s:
        assert len(list(s.scalars(select(Tarefa).where(Tarefa.origem_tipo == stc.ORIGEM)))) == 18


def test_liberar_todas_as_competencias_fica_de_fora(cliente, cenario):
    with FabricaSessao() as s:
        for c in s.scalars(select(Contrato)):
            c.liberar_todas_competencias = True
        s.commit()
    assert _sincronizar().criadas == 0 and _tarefas() == {}
    with FabricaSessao() as s:
        assert s.scalar(select(Tarefa.id).where(Tarefa.origem_tipo == stc.ORIGEM)) is None


def test_etapas_andam_sozinhas_e_o_historico_mostra_quem_fez(cliente, cenario):
    contrato, base, gestora = cenario
    _sincronizar()
    # Nota fiscal juntada em Contratos: a tarefa da NF conclui e a da retenção passa a em andamento, na hora, pelo autor real
    assert juntar_nf(cliente, base, gestora, "2105.00", "123").status_code == 200
    estados = _estados()
    assert estados["nf:1"] == "concluida" and estados["retencao:1:1"] == "em_andamento"
    nf = _tarefas()["nf:1"]
    with FabricaSessao() as s:
        eventos = list(s.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == nf.id).order_by(EventoTarefa.criado_em)))
    status = [e for e in eventos if e.tipo == "status"]
    # a_fazer → em_andamento → concluida, autor = quem juntou a NF (Gestora Silva), com de/para para o Desempenho
    assert [(e.dados["de"], e.dados["para"]) for e in status] == [("a_fazer", "em_andamento"), ("em_andamento", "concluida")]
    assert all(e.autor_nome == "Gestora Silva" for e in status) and "Notas juntadas: NF 123" in status[-1].texto
    # Retenção conferida: conclui a retenção, e o prazo da OB passa a ser o vencimento do pagamento (NF de 05/02 + 30 dias)
    assert conferir_retencao(cliente, base, gestora).status_code in (200, 403)


def test_recusa_da_nf_fecha_a_rodada_com_o_motivo_e_abre_a_seguinte(cliente, admin, cenario):
    contrato, base, gestora = cenario
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    _sincronizar()
    assert _estados()["retencao:1:1"] == "em_andamento"
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=cabecalho(cliente, "financeiro1")).status_code == 200
    estados = _estados()
    # A rodada 1 (NF e retenção) fecha; nascem a NF e a retenção da 2ª rodada
    assert estados["nf:1"] == "concluida" and estados["retencao:1:1"] == "concluida"
    assert estados["nf:2"] == "a_fazer" and estados["retencao:2:1"] == "a_fazer"
    tarefas = _tarefas()
    assert tarefas["nf:2"].titulo.startswith("Subir a nota fiscal (2ª rodada)")
    with FabricaSessao() as s:
        textos = [e.texto for e in s.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == tarefas["nf:1"].id))]
    assert any(JUSTIFICATIVA in t for t in textos)


def test_varias_notas_geram_uma_retencao_por_nota(cliente, cenario):
    contrato, base, gestora = cenario
    _sincronizar()
    assert juntar_nf(cliente, base, gestora, "1000.00", "10", adicional=("1105.00", "11")).status_code == 200
    chaves = sorted(k for k in _tarefas() if k.startswith("retencao:1:"))
    assert chaves == ["retencao:1:1", "retencao:1:2"]
    assert {t.titulo.rsplit(" — ", 2)[0] for k, t in _tarefas().items() if k.startswith("retencao")} == {"Retenção de tributos — NF 10", "Retenção de tributos — NF 11"}


def test_reabrir_a_etapa_volta_a_tarefa(cliente, admin, cenario):
    contrato, base, gestora = cenario
    _sincronizar()
    assert _estados()["medicao"] == "concluida"
    r = cliente.post(f"{base}/reabrir", json={"etapa": "medicao", "justificativa": "Correção de quantidades na medição."}, headers=gestora)
    assert r.status_code == 200, r.text
    assert _estados()["medicao"] == "em_andamento"
    with FabricaSessao() as s:
        t = _tarefas()["medicao"]
        eventos = list(s.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == t.id, EventoTarefa.tipo == "reaberta")))
    assert len(eventos) == 1 and eventos[0].dados == {"de": "concluida", "para": "em_andamento"}


def test_tarefa_controlada_nao_se_move_pelo_usuario_mas_aceita_comentario(cliente, admin, cenario):
    _sincronizar()
    numero = _tarefas()["cadin"].numero
    t = cliente.get(f"/api/tarefas/{numero}", headers=admin).json()
    assert t["controlada_externamente"] is True and t["origem_tipo"] == "contrato_competencia"
    assert t["origem_link"].startswith("/contratos/") and "execucao/2026-01" in t["origem_link"] and t["origem_rotulo"] == "Contrato 001/2026 · 01/2026"
    # Mesmo o SuperRoot só comenta, ajusta responsáveis e prazo: nada de iniciar, entregar, concluir, excluir ou subtarefas
    assert set(t["acoes"]) <= {"comentar", "editar", "prazo", "transferir"} and "iniciar" not in t["acoes"] and "excluir" not in t["acoes"]
    r = cliente.post(f"/api/tarefas/{numero}/mover", json={"acao": "iniciar"}, headers=admin)
    assert r.status_code == 403
    assert cliente.post(f"/api/tarefas/{numero}/subtarefas", json={"titulo": "x"}, headers=admin).status_code == 403
    assert cliente.delete(f"/api/tarefas/{numero}", headers=admin).status_code == 403
    assert cliente.put(f"/api/tarefas/{numero}", json={"titulo": "outro", "descricao": "x", "prioridade": "normal", "responsaveis_ids": [t["responsavel"]["id"]], "marcadores_ids": []},
                       headers=admin).status_code == 403
    assert cliente.post(f"/api/tarefas/{numero}/comentarios", data={"texto": "Aguardando a certidão."}, headers=admin).status_code == 201
    # Já a tarefa manual (SEI) anda normalmente
    sei = _tarefas()["sei"].numero
    assert cliente.post(f"/api/tarefas/{sei}/mover", json={"acao": "iniciar"}, headers=admin).status_code == 200


def test_tarefas_de_contrato_nao_pesam_na_carga(cliente, admin, cenario):
    _sincronizar()
    lista = cliente.get("/api/tarefas", params={"escopo": "equipe", "equipe_id": str(_tarefas()["medicao"].equipe_id)}, headers=admin).json()
    assert lista["indicadores"]["carga"] == 0 or all(i["carga"] == 0 for i in lista["itens"] if i["controlada_externamente"])
    filtrada = cliente.get("/api/tarefas", params={"escopo": "equipe", "equipe_id": str(_tarefas()["medicao"].equipe_id), "origem": "contratos"}, headers=admin).json()
    assert filtrada["itens"] and all(i["origem_tipo"] == "contrato_competencia" for i in filtrada["itens"])


def test_endpoint_de_sincronizacao_so_para_superroot_e_com_ensaio(cliente, admin, cenario):
    _ligar()
    r = cliente.post("/api/tarefas/contratos/sincronizar", headers=cabecalho(cliente, "gestora"))
    assert r.status_code == 403
    r = cliente.post("/api/tarefas/contratos/sincronizar", headers=admin)
    assert r.status_code == 200 and r.json()["ensaio"] is True and r.json()["criadas"] == 18 and _tarefas() == {}
    r = cliente.post("/api/tarefas/contratos/sincronizar", params={"ensaio": "false"}, headers=admin)
    assert r.status_code == 200 and r.json()["ensaio"] is False and _tarefas() != {}


def test_desempenho_reconstroi_o_historico_das_tarefas_espelhadas(cliente, admin, cenario):
    from app.services.tarefas import desempenho_tarefas as d

    _sincronizar()
    medicao = _tarefas()["medicao"]
    with FabricaSessao() as s:
        t = s.get(Tarefa, medicao.id)
        eventos = list(s.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == t.id)))
        historico = d.reconstruir(t, eventos)
        assert historico.situacao_em(datetime(2100, 1, 1, tzinfo=timezone.utc)) == "concluida"
    assert servico.carga(medicao, datetime.now(timezone.utc)) == 0.0
