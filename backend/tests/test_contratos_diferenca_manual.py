# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a diferença retroativa informada manualmente (reajuste e repactuação) para meses pagos fora do sistema.
"""Diferença retroativa manual: meses encerrados sem medição concluída, travados no preço de antes.

Contrato de apoio (o de `test_contratos_reajuste_desconto`): item 1 contínuo (2 × R$ 1.000,00/mês) e item 2 sob demanda.
Hoje = 15/03/2026: janeiro e fevereiro estão encerrados; março ainda não.
"""

import io

import pytest
from pypdf import PdfReader

from tests.apoio_contratos import PDF, corpo_conclusao
from tests.test_contratos_alteracoes import equipe  # noqa: F401 (fixture)
from tests.test_contratos_execucao import _preparar_execucao, _url
from tests.test_contratos_reajuste_desconto import _abrir, _aplicar, _competencia, _concluir, _hoje, _medir, cenario  # noqa: F401 (fixtures)


def _texto_pdf(conteudo: bytes) -> str:
    """Texto de todas as páginas do PDF, numa linha só (as quebras de linha do PDF viram espaço)."""
    return " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(conteudo)).pages)


def _informar(cliente, url, h, valor, competencias, justificativa="Meses pagos antes da implantação do SGI"):
    """`PUT …/diferenca-manual` com os meses (ids), o valor, a justificativa e o PDF."""
    return cliente.put(f"{url}/diferenca-manual", data={"valor": valor, "competencias_ids": competencias, "justificativa": justificativa},
                       files={"arquivo": ("memoria-externa.pdf", PDF)}, headers=h)


def test_reajuste_lista_os_meses_sem_medicao_e_valida_o_preenchimento(cliente, cenario):
    """Só os meses encerrados desde o efeito e sem medição concluída; valor zero, justificativa vazia e mês fora da lista são recusados."""
    contrato, h, notas = cenario
    _medir(cliente, contrato, h, notas, "2026-01")
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    reajuste = r.json()["em_andamento"]
    # Janeiro está medido (entra no cálculo automático); março ainda não terminou
    assert [m["rotulo"] for m in reajuste["meses_sem_medicao"]] == ["02/2026"]
    assert reajuste["diferenca_manual"] is None
    fevereiro = reajuste["meses_sem_medicao"][0]["competencia_id"]
    marco = _competencia(cliente, contrato, h, "2026-03")["id"]
    assert _informar(cliente, url, h, "0", [fevereiro]).status_code == 400
    assert _informar(cliente, url, h, "300", [fevereiro], justificativa="   ").status_code == 400
    assert _informar(cliente, url, h, "300", [marco]).status_code == 400
    sem_pdf = cliente.put(f"{url}/diferenca-manual", data={"valor": "300", "competencias_ids": [fevereiro], "justificativa": "x"}, headers=h)
    assert sem_pdf.status_code == 422

    r = _informar(cliente, url, h, "300", [fevereiro])
    assert r.status_code == 200, r.text
    manual = r.json()["em_andamento"]["diferenca_manual"]
    assert manual["valor"] == "300.00" and [m["rotulo"] for m in manual["meses"]] == ["02/2026"]
    assert manual["observacao"].startswith("O valor de R$ 300,00 foi inserido manualmente por ")
    assert "devido à falta de medição de 02/2026, não tendo sido utilizada a função do sistema para cálculo automático" in manual["observacao"]
    assert manual["observacao"].endswith("Justificativa: Meses pagos antes da implantação do SGI")
    # Remover destrava; remover de novo dá 400
    assert cliente.delete(f"{url}/diferenca-manual", headers=h).json()["em_andamento"]["diferenca_manual"] is None
    assert cliente.delete(f"{url}/diferenca-manual", headers=h).status_code == 400


def test_reajuste_com_diferenca_manual_positiva_gera_complementar_e_trava_o_mes(cliente, cenario):
    """Janeiro e fevereiro pagos fora do sistema: +10% desde janeiro, diferença informada de R$ 400,00.

    Os dois meses ficam no preço antigo (R$ 1.000,00), não entram no cálculo automático e a diferença vira uma complementar de uma linha.
    Março (não encerrado) recebe o preço novo. A memória e a complementar trazem a observação."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    meses = [m["competencia_id"] for m in r.json()["em_andamento"]["meses_sem_medicao"]]
    assert len(meses) == 2
    reajuste = _informar(cliente, url, h, "400", meses).json()["em_andamento"]
    assert reajuste["diferenca_retroativa"] == "0.00"
    painel = _concluir(cliente, h, url)
    historico = painel["historico"][0]
    assert historico["competencia_diferenca"] is None
    assert historico["diferenca_manual"]["competencia_diferenca"] == "2026-01-dif-manual"
    memoria = historico["memorias"][-1]["pdf"]["anexo_id"]
    texto = _texto_pdf(cliente.get(f"{url}/arquivos/{memoria}", headers=h).content)
    assert "Diferença retroativa informada manualmente" in texto and "foi inserido manualmente por" in texto
    # O PDF externo também pode ser baixado pelo reajuste
    externo = historico["diferenca_manual"]["arquivo"]["anexo_id"]
    assert cliente.get(f"{url}/arquivos/{externo}", headers=h).status_code == 200

    # Meses travados no preço de antes; março com o preço novo
    for identificador in ("2026-01", "2026-02"):
        assert _competencia(cliente, contrato, h, identificador)["itens"][0]["valor_unitario"] == "1000.0000"
    assert _competencia(cliente, contrato, h, "2026-03")["itens"][0]["valor_unitario"] == "1100.0000"
    # Gerar a execução de novo não destrava
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    assert _competencia(cliente, contrato, h, "2026-02")["itens"][0]["valor_unitario"] == "1000.0000"

    # Complementar de uma linha: segue o fluxo normal da medição (só as NEs são escolhidas)
    complementar = _competencia(cliente, contrato, h, "2026-01-dif-manual")
    assert complementar["rotulo"].startswith("Diferença de reajuste informada manualmente 01/2026 a 02/2026")
    assert [(i["descricao"], i["valor_unitario"], i["quantidade_medida"]) for i in complementar["itens"]] == [
        ("Diferença retroativa de reajuste informada manualmente (01/2026 e 02/2026)", "400.0000", "1.0000000000")]
    assert complementar["diferenca_manual"] is True and complementar["observacoes_manuais"][0].startswith("O valor de R$ 400,00 foi inserido manualmente")
    medida = _medir(cliente, contrato, h, notas, "2026-01-dif-manual")
    assert medida["total_medido"] == "400.00" and medida["valor_autorizado"] == "400.00"
    memoria_medicao = medida["memorias"][-1]["arquivo"]["anexo_id"]
    texto = _texto_pdf(cliente.get(_url(contrato, f"/competencias/{medida['id']}/arquivos/{memoria_medicao}"), headers=h).content)
    assert "Observações" in texto and "O valor de R$ 400,00 foi inserido manualmente por" in texto


def test_mes_travado_medido_depois_fica_no_preco_antigo(cliente, cenario):
    """Fevereiro coberto pela diferença manual e medido depois no sistema: a medição usa o preço antigo (o que foi pago de fato)."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    fevereiro = next(m["competencia_id"] for m in r.json()["em_andamento"]["meses_sem_medicao"] if m["rotulo"] == "02/2026")
    _informar(cliente, url, h, "200", [fevereiro])
    _concluir(cliente, h, url)
    medida = _medir(cliente, contrato, h, notas, "2026-02")
    assert medida["itens"][0]["valor_unitario"] == "1000.0000"


def test_mes_medido_antes_da_conclusao_impede_concluir(cliente, cenario):
    """Mês marcado e depois medido no sistema (com o reajuste ainda em elaboração): a conclusão pede revisão."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    janeiro = next(m["competencia_id"] for m in r.json()["em_andamento"]["meses_sem_medicao"] if m["rotulo"] == "01/2026")
    _informar(cliente, url, h, "200", [janeiro])
    _medir(cliente, contrato, h, notas, "2026-01")
    cliente.post(f"{url}/evidencia", files={"arquivo": ("ev.pdf", PDF)}, headers=h)
    cliente.post(f"{url}/memoria/arquivos", headers=h)
    r = cliente.post(f"{url}/concluir", files={"arquivo": ("ap.pdf", PDF)}, headers=h)
    assert r.status_code == 400 and "Revise a diferença manual" in r.json()["detalhe"]


def test_diferenca_manual_negativa_vira_credito_manual_no_fundo(cliente, cenario):
    """Desconto informado à mão (−R$ 150,00) vira crédito no fundo, marcado como manual e com a observação; o gestor aplica em março."""
    contrato, h, notas = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["-10", "0"])
    meses = [m["competencia_id"] for m in r.json()["em_andamento"]["meses_sem_medicao"]]
    _informar(cliente, url, h, "-150", meses)
    historico = _concluir(cliente, h, url)["historico"][0]
    assert historico["diferenca_manual"]["competencia_diferenca"] is None and historico["credito_pendente"] == "150.00"
    marco = _competencia(cliente, contrato, h, "2026-03")
    credito = marco["creditos_disponiveis"][0]
    assert credito["manual"] is True and credito["rotulo"] == "Crédito de Reajuste (ref. 01/2026) · valor manual"
    assert credito["observacao"].startswith("O valor de -R$ 150,00 foi inserido manualmente por ")
    assert _aplicar(cliente, contrato, h, "2026-03")["desconto_reajuste"] == "150.00"


def test_cancelar_reajuste_destrava_os_meses(cliente, cenario):
    """Cancelado o reajuste, os meses marcados voltam a ser candidatos (sem trava) no próximo."""
    contrato, h, _ = cenario
    url, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    meses = [m["competencia_id"] for m in r.json()["em_andamento"]["meses_sem_medicao"]]
    _informar(cliente, url, h, "400", meses)
    assert cliente.post(f"{url}/cancelar", headers=h).status_code == 200
    _, r = _abrir(cliente, contrato, h, "2026-01-01", ["10", "0"])
    assert [m["coberta_por_outra"] for m in r.json()["em_andamento"]["meses_sem_medicao"]] == [False, False]


def test_repactuacao_com_diferenca_manual_positiva(cliente, admin, equipe):  # noqa: F811
    """Repactuação desde janeiro sem nada medido: diferença manual de R$ 250,00 vira complementar própria; o consolidado traz a observação."""
    contrato, gestora, _ = equipe
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    painel = cliente.post(_url(contrato, "/repactuacoes"), data={"data_base_cct": "2026-01-01", "data_efeito": "2026-01-01"},
                          files={"arquivo": ("cct.pdf", PDF)}, headers=gestora).json()
    continuo = next(i for i in painel["itens_contrato"] if i["tipo"] == "continuo")
    url = _url(contrato, f"/repactuacoes/{painel['em_andamento']['id']}")
    rep = cliente.put(f"{url}/linhas", json={"finalizar": True, "linhas": [
        {"descricao": "Vale-transporte", "valor_vigente": "100", "valor_repactuado": "110", "itens_ids": [continuo["id"]]}]}, headers=gestora).json()["em_andamento"]
    meses = [m["competencia_id"] for m in rep["meses_sem_medicao"]]
    assert [m["rotulo"] for m in rep["meses_sem_medicao"]] == ["01/2026", "02/2026"]
    r = _informar(cliente, url, gestora, "250", meses)
    assert r.status_code == 200, r.text
    # Os meses travados não aparecem como "recebem o novo preço"
    assert all(c["competencia"] not in ("01/2026", "02/2026") for c in r.json()["em_andamento"]["competencias"])
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
