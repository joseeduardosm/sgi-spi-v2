# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os parâmetros do módulo de contratos: leitura, gravação por permissão, validações, auditoria e uso nas regras.
"""Parâmetros de Contratos (`/api/contratos/parametros`): padrões de fábrica, quem grava, validação, auditoria e efeito nas regras."""

from datetime import date

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.auditoria import RegistroAuditoria
from app.models.contratos.parametros import PADROES
from app.services.contratos import calculos, servico_parametros
from tests.apoio_contratos import definir_parametros, restringir_contratos
from tests.conftest import cabecalho, criar_usuario


def _corpo(leitura: dict, **mudancas) -> dict:
    """Corpo do PUT a partir da leitura (sem os campos só de leitura)."""
    corpo = {k: v for k, v in leitura.items() if k not in ("atualizado_por_nome", "atualizado_em", "padroes")}
    return {**corpo, **mudancas}


def test_leitura_traz_os_valores_de_fabrica(cliente, admin):
    # O conftest baixa o corte para 2000 em todo teste; aqui apaga a linha para a leitura recriar com os valores de fábrica
    from app.models.contratos.parametros import ParametrosContratos

    with FabricaSessao() as s:
        s.delete(s.get(ParametrosContratos, 1))
        s.commit()
    servico_parametros.limpar_cache()
    r = cliente.get("/api/contratos/parametros", headers=admin)
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["corte_alertas_a_partir_de"] == "2026-09-01" and dados["dias_atraso"] == 30 and dados["maximo_notas_fiscais"] == 20
    assert dados["atualizado_por_nome"] is None and dados["padroes"]["dias_vigencia_a_vencer"] == 90
    assert set(PADROES) <= set(dados)


def test_so_controle_total_e_superroot_gravam(cliente, admin):
    criar_usuario("leitora")
    leitura = cliente.get("/api/contratos/parametros", headers=admin).json()
    corpo = _corpo(leitura, dias_atraso=45)
    # Quem só consulta (ou só modifica) lê, mas não grava
    restringir_contratos(cliente, admin, {criar_usuario("modificadora"): "MODIFICACAO"})
    assert cliente.get("/api/contratos/parametros", headers=cabecalho(cliente, "modificadora")).status_code == 200
    assert cliente.put("/api/contratos/parametros", json=corpo, headers=cabecalho(cliente, "modificadora")).status_code == 403
    assert cliente.put("/api/contratos/parametros", json=corpo, headers=cabecalho(cliente, "leitora")).status_code == 403
    # SuperRoot grava e a leitura seguinte traz o valor novo e quem alterou
    r = cliente.put("/api/contratos/parametros", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["dias_atraso"] == 45 and r.json()["atualizado_por_nome"]
    assert servico_parametros.valor("dias_atraso") == 45


def test_validacoes_e_coerencia(cliente, admin):
    leitura = cliente.get("/api/contratos/parametros", headers=admin).json()
    assert cliente.put("/api/contratos/parametros", json=_corpo(leitura, dias_atraso=0), headers=admin).status_code == 422
    assert cliente.put("/api/contratos/parametros", json=_corpo(leitura, dias_documento_alto=40, dias_documento_medio=30), headers=admin).status_code == 422
    assert cliente.put("/api/contratos/parametros", json=_corpo(leitura, dias_vigencia_atencao=60, dias_vigencia_a_vencer=90), headers=admin).status_code == 422
    assert cliente.put("/api/contratos/parametros", json={"dias_atraso": 10}, headers=admin).status_code == 422


def test_auditoria_so_do_que_mudou(cliente, admin):
    leitura = cliente.get("/api/contratos/parametros", headers=admin).json()
    cliente.put("/api/contratos/parametros", json=_corpo(leitura, dias_atraso=40, maximo_notas_fiscais=25), headers=admin)
    cliente.put("/api/contratos/parametros", json=_corpo(leitura, dias_atraso=40, maximo_notas_fiscais=25), headers=admin)  # igual: não audita de novo
    with FabricaSessao() as s:
        registros = list(s.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == "contratos.parametros")))
    assert len(registros) == 1
    assert set(registros[0].dados["campos"]) == {"dias_atraso", "maximo_notas_fiscais"}
    assert registros[0].dados["campos"]["dias_atraso"] == {"de": "30", "para": "40"}


def test_parametros_mudam_as_regras():
    # "A vencer" usa o parâmetro: com 10 dias, um contrato que vence em 30 dias fica ativo
    hoje, fim = date(2026, 10, 1), date(2026, 10, 31)
    assert calculos.calcular_situacao(fim, None, hoje).value == "a_vencer"
    definir_parametros(dias_vigencia_a_vencer=10)
    assert calculos.calcular_situacao(fim, None, hoje).value == "ativo"


def test_sem_banco_cai_nos_padroes(monkeypatch):
    servico_parametros.limpar_cache()

    def quebrado(*a, **k):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(servico_parametros, "FabricaSessao", quebrado)
    assert servico_parametros.valor("dias_atraso") == PADROES["dias_atraso"]
    servico_parametros.limpar_cache()
