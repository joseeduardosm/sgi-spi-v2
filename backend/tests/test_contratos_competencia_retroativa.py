# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o caminho curto das competências anteriores ao corte de alertas (medição, nota fiscal e OB) e a busca da OB no SIGEO.
"""Competência retroativa (anterior ao corte): sem retenção, CADIN, checklist e consolidado; sem e-mails e avisos; busca da OB no SIGEO pela tela."""

from datetime import date

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.contratos import Contrato
from app.models.notificacao import Notificacao
from tests.apoio_contratos import definir_parametros, juntar_nf
from tests.conftest import cabecalho
from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 - fixtures (data fixa de 15/03/2026, SMTP simulado, medição concluída)
from tests.test_smtp import SmtpSimulado


def _processo_financeiro(contrato: dict, valor: str) -> None:
    with FabricaSessao() as s:
        import uuid

        s.get(Contrato, uuid.UUID(contrato["id"])).processo_financeiro = valor
        s.commit()


def test_retroativa_vai_da_nota_fiscal_direto_para_a_ob_sem_emails(cliente, cenario):  # noqa: F811
    contrato, base, gestora = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2026, 9, 1))
    antes = cliente.get(base, headers=gestora).json()
    assert antes["retroativa"] is True and antes["etapas"] == ["medicao", "nota_fiscal", "ordem_bancaria", "concluida"]
    with FabricaSessao() as s:
        avisos_antes = len(list(s.scalars(select(Notificacao))))
    r = juntar_nf(cliente, base, gestora, "2105.00", "123")
    assert r.status_code == 200, r.text
    depois = r.json()
    # Sem retenção, checklist, CADIN nem consolidado: a OB é a próxima etapa
    assert depois["etapa_atual"] == "ordem_bancaria" and depois["etapas_abertas"] == ["ordem_bancaria"]
    assert depois["etapas_concluidas"] == ["medicao", "nota_fiscal"]
    # Nenhum e-mail e nenhum aviso novo (a pendência de retenção do Financeiro nem nasce)
    assert SmtpSimulado.enviadas == []
    with FabricaSessao() as s:
        assert len(list(s.scalars(select(Notificacao)))) == avisos_antes


def test_competencia_depois_do_corte_continua_com_o_fluxo_completo(cliente, cenario):  # noqa: F811
    contrato, base, gestora = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2025, 1, 1))
    detalhe = cliente.get(base, headers=gestora).json()
    assert detalhe["retroativa"] is False and "retencao" in detalhe["etapas"] and "consolidado" in detalhe["etapas"]
    assert juntar_nf(cliente, base, gestora, "2105.00", "123").json()["etapa_atual"] == "retencao"


def test_buscar_ob_no_sigeo_pela_tela(cliente, cenario, monkeypatch):  # noqa: F811
    contrato, base, gestora = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2026, 9, 1))
    # Sem processo financeiro: a busca é recusada (e a tela nem oferece)
    assert juntar_nf(cliente, base, gestora, "2105.00", "123").status_code == 200
    assert cliente.get(base, headers=gestora).json()["pode_buscar_ob_sigeo"] is False
    assert cliente.post(f"{base}/ordem-bancaria/sigeo", headers=gestora).status_code == 400
    _processo_financeiro(contrato, "2024.0596.951")
    assert cliente.get(base, headers=gestora).json()["pode_buscar_ob_sigeo"] is True
    # OB do mês ainda não saiu: nada muda
    monkeypatch.setattr("app.services.servico_integracao_sigeo.baixar_pagamentos", lambda config: [])
    r = cliente.post(f"{base}/ordem-bancaria/sigeo", headers=gestora)
    assert r.status_code == 200 and r.json()["concluida"] is False and "Ainda não há OB" in r.json()["mensagem"]
    # OB do mês no SIGEO com o líquido da competência: conclui, sem e-mail por ser retroativa
    linha = {"COD_PROCESSO": "20240596951", "COD_DOCUMENTO": "390001000012026OB00123", "TIPO_DOCUMENTO": "OB", "DATA_LANCAMENTO": "2026-02-20",
             "VALOR_DOCUMENTO": "2105.00", "DESCRICAO_DOCUMENTO": "SERV. NF 123 REF JAN/26", "CGC_CPF": "11222333000181"}
    monkeypatch.setattr("app.services.servico_integracao_sigeo.baixar_pagamentos", lambda config: [linha])
    r = cliente.post(f"{base}/ordem-bancaria/sigeo", headers=gestora)
    assert r.status_code == 200, r.text
    assert r.json()["concluida"] is True and cliente.get(base, headers=gestora).json()["etapa_atual"] == "concluida"
    assert SmtpSimulado.enviadas == []


def test_retroativa_conclui_a_medicao_sem_preposto_nem_prazo(cliente, cenario):  # noqa: F811
    contrato, base, gestora = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2026, 9, 1))
    # Volta a competência ao início e conclui de novo, agora sem preposto e sem prazo de contestação
    assert cliente.post(f"{base}/zerar", headers=gestora).status_code == 200, "zerar"
    detalhe = cliente.get(base, headers=gestora).json()
    notas = [n["id"] for n in detalhe["notas_selecionadas"]] or [n["id"] for n in cliente.get(f"/api/contratos/{contrato['id']}/notas-empenho", headers=gestora).json()]
    itens = [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in detalhe["itens"]]
    assert cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora).status_code == 200
    assert cliente.post(f"{base}/medicao/ciencia", headers=gestora).status_code == 200
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 200, r.text
    assert r.json()["etapa_atual"] == "nota_fiscal" and SmtpSimulado.enviadas == []


def test_competencia_de_carga_historica_mostra_a_origem_e_os_itens_acima_do_limite(cliente, cenario):  # noqa: F811
    """O detalhe traz a marca da carga histórica, a observação e, item a item, o que passou do limite mensal (a tela mostra um aviso)."""
    from datetime import datetime, timezone
    import uuid

    from app.models.contratos import Competencia

    contrato, base, gestora = cenario
    assert cliente.get(base, headers=gestora).json()["carga_historica"] is None
    competencia_id = uuid.UUID(base.rsplit("/", 1)[1])
    with FabricaSessao() as s:
        k = s.get(Competencia, competencia_id)
        # Mede 1 hora a mais do que o previsto em um item e marca a competência como carga histórica
        item = next(i for i in k.itens if i.quantidade_prevista > 0)
        item.quantidade_medida = item.quantidade_prevista + 1
        k.carga_historica_em, k.carga_historica_obs = datetime.now(timezone.utc), "Lançada depois de paga, do processo SEI 1/2024."
        s.commit()
    h = cliente.get(base, headers=gestora).json()["carga_historica"]
    assert h["observacao"].startswith("Lançada depois de paga") and len(h["excedentes"]) == 1 and "passa do saldo líquido" in h["excedentes"][0]
