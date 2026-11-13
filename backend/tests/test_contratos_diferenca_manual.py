"""
===============================================================================
ARQUIVO: test_contratos_diferenca_manual.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar o cálculo manual da diferença retroativa (reajuste e repactuação):
a memória pergunta "manual ou automático?" e, no manual, o gestor informa a
diferença mês a mês.

RESUMO TÉCNICO:
Regra (decisão do usuário de 13/11/2026):
- no cálculo manual o sistema não calcula nada sozinho, nem a diferença dos meses medidos no SGI;
- podem ser informados os meses da data de efeito até o mês em andamento (inclusive), medidos ou não;
- os meses informados ficam travados no preço de antes; o total (soma dos meses) vira complementar (positivo) ou crédito (negativo).

Contrato de apoio (o de `test_contratos_reajuste_desconto`): item 1 contínuo (2 × R$ 1.000,00/mês) e item 2 sob demanda.
Hoje = 15/03/2026: janeiro e fevereiro estão encerrados; março está em andamento; abril é futuro.

FINALIDADE DE NEGÓCIO:
Garante que, no cálculo manual, vale só o valor informado (sem diferença
automática dos meses medidos), que os meses ficam no preço antigo e que o
total vira complementar ou crédito.

CONTEXTO NO SISTEMA:
Rotas `…/modo-retroativo` e `…/diferenca-manual` do reajuste e da
repactuação; serviço app/services/contratos/diferenca_manual.py.

===============================================================================
"""

import io
from datetime import date

import pytest
from pypdf import PdfReader

from tests.apoio_contratos import PDF, escolher_calculo
from tests.test_contratos_alteracoes import equipe  # noqa: F401 (fixture)
from tests.test_contratos_execucao import _preparar_execucao, _url
from tests.test_contratos_reajuste_desconto import _abrir, _aplicar, _competencia, _concluir, _hoje, _medir, cenario  # noqa: F401 (fixtures)


def _texto_pdf(conteudo: bytes) -> str:
    """Texto de todas as páginas do PDF, numa linha só (as quebras de linha do PDF viram espaço)."""
    return " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(conteudo)).pages)


def _informar(cliente, url, h, meses: dict, justificativa="Meses pagos antes da implantação do SGI"):
    """`PUT …/diferenca-manual` com {id do mês: valor}, a justificativa e o PDF (ids e valores vão repetidos, na mesma ordem)."""
    return cliente.put(f"{url}/diferenca-manual", data={"competencias_ids": list(meses), "valores": list(meses.values()), "justificativa": justificativa},
                       files={"arquivo": ("memoria-externa.pdf", PDF)}, headers=h)


def _avancar_para_abril(monkeypatch):
    """Passa "hoje" para 15/04/2026: março termina e a medição dele é liberada."""
    for modulo in ("servico_contratos", "servico_competencias"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: date(2026, 4, 15))


def _meses(painel: dict) -> dict:
    """{rótulo (MM/AAAA): mês} da lista de meses do cálculo manual."""
    return {m["rotulo"]: m for m in painel["em_andamento"]["meses_sem_medicao"]}


def test_memoria_e_conclusao_exigem_a_escolha_do_calculo(cliente, cenario):
    """Sem responder "manual ou automático?" não se gera a memória; no automático não há lista de meses para informar."""
    contrato, h, _ = cenario
    reajuste = cliente.post(_url(contrato, "/reajustes"), json={"sequencia_vigencia": 1, "mes_referencia": "2026-01-01"}, headers=h).json()["em_andamento"]
    url = _url(contrato, f"/reajustes/{reajuste['id']}")
    assert reajuste["modo_retroativo"] is None
    r = cliente.post(f"{url}/memoria/arquivos", headers=h)
    assert r.status_code == 400 and "manual ou automático" in r.json()["detalhe"]
    assert cliente.put(f"{url}/modo-retroativo", json={"modo": "outro"}, headers=h).status_code == 422
    painel = escolher_calculo(cliente, url, h, "automatico")
    assert painel["em_andamento"]["modo_retroativo"] == "automatico" and painel["em_andamento"]["meses_sem_medicao"] == []
    # No automático não se informa diferença manual
    assert _informar(cliente, url, h, {}).status_code in (400, 422)


def test_manual_lista_do_efeito_ate_o_mes_em_andamento_medidos_ou_nao(cliente, cenario):
    """Janeiro medido no SGI, fevereiro sem medição e março em andamento entram; abril (futuro) não. Valores inválidos são recusados."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    meses = _meses(escolher_calculo(cliente, url, h, "manual"))
    assert list(meses) == ["01/2026", "02/2026", "03/2026"]
    assert meses["01/2026"]["medida"] is True and meses["02/2026"]["medida"] is False
    assert meses["03/2026"]["em_andamento"] is True and meses["02/2026"]["em_andamento"] is False
    janeiro, marco = meses["01/2026"]["competencia_id"], meses["03/2026"]["competencia_id"]
    abril = _competencia(cliente, contrato, h, "2026-04")["id"]
    assert _informar(cliente, url, h, {janeiro: "0"}).status_code == 400
    assert _informar(cliente, url, h, {janeiro: "100", marco: "-100"}).status_code == 400  # total zero
    assert _informar(cliente, url, h, {janeiro: "100"}, justificativa="   ").status_code == 400
    assert _informar(cliente, url, h, {abril: "100"}).status_code == 400
    sem_pdf = cliente.put(f"{url}/diferenca-manual", data={"competencias_ids": [janeiro], "valores": ["100"], "justificativa": "x"}, headers=h)
    assert sem_pdf.status_code == 422

    r = _informar(cliente, url, h, {janeiro: "120", marco: "80"})
    assert r.status_code == 200, r.text
    reajuste = r.json()["em_andamento"]
    manual = reajuste["diferenca_manual"]
    assert manual["valor"] == "200.00"
    assert [(m["rotulo"], m["valor"]) for m in manual["meses"]] == [("01/2026", "120.00"), ("03/2026", "80.00")]
    # O valor já informado volta na lista para a tela preencher os campos
    assert _meses(r.json())["01/2026"]["valor"] == "120.00" and _meses(r.json())["02/2026"]["valor"] is None
    assert manual["observacao"].startswith("O valor de R$ 200,00 foi inserido manualmente por ")
    assert "referente aos meses 01/2026 e 03/2026, no cálculo manual, não tendo sido utilizada a função do sistema para cálculo automático" in manual["observacao"]
    # Janeiro foi medido, mas no manual o sistema não calcula a diferença dele
    assert reajuste["diferenca_retroativa"] == "0.00" and reajuste["competencias_com_diferenca"] == 0
    # Remover destrava; remover de novo dá 400
    assert cliente.delete(f"{url}/diferenca-manual", headers=h).json()["em_andamento"]["diferenca_manual"] is None
    assert cliente.delete(f"{url}/diferenca-manual", headers=h).status_code == 400


def test_trocar_para_automatico_apaga_a_diferenca_e_exige_memoria_nova(cliente, cenario):
    """Diferença informada no manual some ao trocar para o automático; a memória gerada antes da troca não serve para concluir."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    fevereiro = _meses(r.json())["02/2026"]["competencia_id"]
    _informar(cliente, url, h, {fevereiro: "300"})
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    assert cliente.post(f"{url}/memoria/arquivos", headers=h).status_code == 200
    painel = escolher_calculo(cliente, url, h, "automatico")["em_andamento"]
    assert painel["diferenca_manual"] is None
    # Automático: janeiro medido volta a ter a diferença calculada pelo sistema
    assert painel["competencias_com_diferenca"] == 1
    r = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h)
    assert r.status_code == 400 and "Gere a memória de cálculo de novo" in r.json()["detalhe"]


def test_manual_sem_diferenca_informada_nao_conclui(cliente, cenario):
    """Escolheu o manual e não informou nenhum mês: a conclusão pede a diferença (ou a troca para o automático)."""
    contrato, h, _ = cenario
    url, _ = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    assert cliente.post(f"{url}/memoria/arquivos", headers=h).status_code == 200
    r = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h)
    assert r.status_code == 400 and "informe a diferença mês a mês" in r.json()["detalhe"]


def test_manual_positivo_gera_complementar_por_mes_sem_diferenca_automatica(cliente, cenario, monkeypatch):
    """+10% desde janeiro; janeiro medido no SGI. Manual: janeiro R$ 200, fevereiro R$ 200 e março (em andamento) R$ 100.

    Não há competência de diferença automática; a complementar tem uma linha por mês. Os três meses ficam no preço antigo (março
    inclusive, mesmo medido depois); abril recebe o preço novo. A memória traz a tabela mês a mês e a observação."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    meses = _meses(r.json())
    _informar(cliente, url, h, {meses["01/2026"]["competencia_id"]: "200", meses["02/2026"]["competencia_id"]: "200",
                                meses["03/2026"]["competencia_id"]: "100"})
    painel = _concluir(cliente, h, url)
    historico = painel["historico"][0]
    assert historico["competencia_diferenca"] is None and historico["diferenca_retroativa"] == "0.00"
    assert historico["diferenca_manual"]["competencia_diferenca"] == "2026-01-dif-manual"
    memoria = historico["memorias"][-1]["pdf"]["anexo_id"]
    texto = _texto_pdf(cliente.get(f"{url}/arquivos/{memoria}", headers=h).content)
    assert "Diferença retroativa informada manualmente" in texto and "Medido no SGI" in texto and "Em andamento" in texto
    externo = historico["diferenca_manual"]["arquivo"]["anexo_id"]
    assert cliente.get(f"{url}/arquivos/{externo}", headers=h).status_code == 200

    # Meses informados travados no preço de antes; abril com o preço novo
    for identificador in ("2026-02", "2026-03"):
        assert _competencia(cliente, contrato, h, identificador)["itens"][0]["valor_unitario"] == "1000.0000"
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    assert _competencia(cliente, contrato, h, "2026-03")["itens"][0]["valor_unitario"] == "1000.0000"
    # Abril (não informado) recebe o preço novo quando a medição dele começa (em maio, depois de abril terminar)
    for modulo in ("servico_contratos", "servico_competencias"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: date(2026, 5, 15))
    assert _medir(cliente, contrato, h, notas, "2026-04")["itens"][0]["valor_unitario"] == "1100.0000"

    complementar = _competencia(cliente, contrato, h, "2026-01-dif-manual")
    assert [(i["descricao"], i["valor_unitario"]) for i in complementar["itens"]] == [
        ("Diferença retroativa de reajuste de 01/2026 informada manualmente", "200.0000"),
        ("Diferença retroativa de reajuste de 02/2026 informada manualmente", "200.0000"),
        ("Diferença retroativa de reajuste de 03/2026 informada manualmente", "100.0000")]
    medida = _medir(cliente, contrato, h, notas, "2026-01-dif-manual")
    assert medida["total_medido"] == "500.00"


def test_mes_em_andamento_informado_e_medido_depois_fica_no_preco_antigo(cliente, cenario, monkeypatch):
    """Março (em andamento) informado no manual e medido depois da conclusão: a medição usa o preço antigo."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    _informar(cliente, url, h, {_meses(r.json())["03/2026"]["competencia_id"]: "100"})
    _concluir(cliente, h, url)
    _avancar_para_abril(monkeypatch)
    medida = _medir(cliente, contrato, h, notas, "2026-03")
    assert medida["itens"][0]["valor_unitario"] == "1000.0000"


def test_manual_negativo_vira_credito_manual_no_fundo(cliente, cenario):
    """Desconto informado à mão (−R$ 100,00 e −R$ 50,00) vira crédito de R$ 150,00 no fundo, marcado como manual; o gestor aplica em março."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["-10", "0"], modo="manual")
    meses = _meses(r.json())
    _informar(cliente, url, h, {meses["01/2026"]["competencia_id"]: "-100", meses["02/2026"]["competencia_id"]: "-50"})
    historico = _concluir(cliente, h, url)["historico"][0]
    assert historico["diferenca_manual"]["competencia_diferenca"] is None and historico["credito_pendente"] == "150.00"
    marco = _competencia(cliente, contrato, h, "2026-03")
    credito = marco["creditos_disponiveis"][0]
    assert credito["manual"] is True and credito["rotulo"] == "Crédito de Reajuste (ref. 01/2026) · valor manual"
    assert credito["observacao"].startswith("O valor de -R$ 150,00 foi inserido manualmente por ")
    assert _aplicar(cliente, contrato, h, "2026-03")["desconto_reajuste"] == "150.00"


def test_cancelar_reajuste_destrava_os_meses(cliente, cenario):
    """Cancelado o reajuste, os meses informados voltam a ser candidatos (sem trava) no próximo."""
    contrato, h, _ = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    meses = _meses(r.json())
    _informar(cliente, url, h, {meses["01/2026"]["competencia_id"]: "200", meses["02/2026"]["competencia_id"]: "200"})
    assert cliente.post(f"{url}/cancelar", headers=h).status_code == 200
    _, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"], modo="manual")
    assert [m["coberta_por_outra"] for m in r.json()["em_andamento"]["meses_sem_medicao"]] == [False, False, False]


def test_repactuacao_manual_sem_diferenca_automatica_dos_meses_medidos(cliente, admin, equipe):  # noqa: F811
    """Repactuação desde janeiro com janeiro medido: no manual, só a diferença informada (R$ 250,00) vira complementar; nada automático."""
    from tests.test_contratos_repactuacao import _medir_janeiro

    contrato, gestora, fiscal = equipe
    _medir_janeiro(cliente, contrato, gestora, fiscal)
    painel = cliente.post(_url(contrato, "/repactuacoes"), data={"data_base_cct": "2026-01-01", "data_efeito": "2026-01-01"},
                          files={"arquivo": ("cct.pdf", PDF)}, headers=gestora).json()
    continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
    url = _url(contrato, f"/repactuacoes/{painel['em_andamento']['id']}")
    cliente.put(f"{url}/linhas", json={"finalizar": True, "linhas": [
        {"descricao": "Vale-transporte", "valor_vigente": "100", "valor_repactuado": "110", "itens_ids": [continuo["id"]]}]}, headers=gestora)
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 400  # falta escolher o cálculo
    rep = escolher_calculo(cliente, url, gestora, "manual")["em_andamento"]
    assert [m["rotulo"] for m in rep["meses_sem_medicao"]] == ["01/2026", "02/2026", "03/2026"]
    assert rep["meses_sem_medicao"][0]["medida"] is True
    # No manual não há competência medida no retroativo automático
    assert all(not c["medida"] for c in rep["competencias"]) and rep["total_retroativo"] == "0.00"
    meses = {m["rotulo"]: m["competencia_id"] for m in rep["meses_sem_medicao"]}
    r = _informar(cliente, url, gestora, {meses["01/2026"]: "150", meses["02/2026"]: "100"})
    assert r.status_code == 200, r.text
    assert cliente.post(f"{url}/memoria", headers=gestora).status_code == 200
    assert cliente.post(f"{url}/consolidado", headers=gestora).status_code == 200
    final = cliente.post(f"{url}/finalizar", files={"arquivo": ("ap.pdf", PDF)}, headers=gestora)
    assert final.status_code == 200, final.text
    historico = final.json()["historico"][0]
    assert historico["competencia_diferenca"] is None
    assert historico["diferenca_manual"]["competencia_diferenca"] == "2026-01-dif-repactuacao-manual"
    texto = _texto_pdf(cliente.get(f"{url}/arquivos/{historico['consolidado']['anexo_id']}", headers=gestora).content)
    assert "foi inserido manualmente por" in texto
    complementar = cliente.get(_url(contrato, "/competencias/identificador/2026-01-dif-repactuacao-manual"), headers=gestora).json()
    assert complementar["total_medido"] == "250.00"
