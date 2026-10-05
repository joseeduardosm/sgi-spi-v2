# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o reaproveitamento de documentos do checklist entre contratos da mesma empresa.
"""Documento da empresa: um documento igual, ainda válido, já juntado em outro contrato da mesma empresa é oferecido e, com confirmação, copiado."""

from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from tests.apoio_contratos import PDF, conferir_retencao, criar_contrato, criar_empresa, juntar_nf, restringir_contratos
from tests.conftest import cabecalho, criar_usuario

HOJE = date(2026, 3, 15)
ITENS = [
    {"nome": "Certidão negativa", "com_validade": True, "vale_outros_contratos": True},
    {"nome": "Folha de pagamento"},
]


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: HOJE)
    monkeypatch.setattr("app.services.contratos.servico_competencias.hoje", lambda: HOJE)


def _url(contrato: dict, caminho: str = "") -> str:
    return f"/api/contratos/{contrato['id']}{caminho}"


def _ate_o_checklist(cliente, contrato, gestora, fiscal, itens=ITENS) -> str:
    """Leva a competência 2026-01 do contrato até a etapa do checklist e devolve a URL base dela."""
    sob_demanda = contrato["itens"][1]["id"]
    grade = [{"item_id": sob_demanda, "competencia": "2026-01-01", "quantidade": "10"}]
    assert cliente.put(_url(contrato, "/previsao/1"), json={"apontamentos": grade}, headers=gestora).status_code == 200
    for numero, valor in (("2026NE00001", "1000.00"), ("2026NE00002", "50000.00")):
        assert cliente.post(_url(contrato, "/notas-empenho"), json={"numero": numero, "valor_original": valor}, headers=gestora).status_code == 201
    checklist = cliente.post(_url(contrato, "/checklists"), json={"nome": "Mensal", "itens": itens}, headers=gestora).json()[0]
    assert cliente.post(_url(contrato, f"/checklists/{checklist['id']}/ativar"), headers=gestora).status_code == 200
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    por_numero = {n["numero"]: n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()}
    notas = [por_numero["2026NE00001"], por_numero["2026NE00002"]]  # ordem de consumo: a de saldo menor primeiro
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    r = juntar_nf(cliente, base, gestora, "2105.00", numero=str(int(contrato["numero"][:3])))  # a chave da NF é única por empresa
    assert r.status_code == 200, r.text
    assert conferir_retencao(cliente, base, gestora).status_code == 200
    detalhe = cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora).json()
    assert detalhe["etapa_atual"] == "checklist"
    return base


@pytest.fixture
def dois_contratos(cliente, admin):
    """Dois contratos da mesma empresa (e um de outra), todos com o checklist de 2026-01 aberto."""
    gestora, fiscal = criar_usuario("gestora"), criar_usuario("fiscal")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    hg, hf = cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")
    equipe = {"gestor": gestora, "fiscal_tecnico": fiscal}
    empresa = criar_empresa(cliente, admin)["id"]
    a = criar_contrato(cliente, admin, empresa_id=empresa, numero="001/2026", equipe=equipe)
    b = criar_contrato(cliente, admin, empresa_id=empresa, numero="002/2026", equipe=equipe)
    return a, b, hg, hf


def _documentos(cliente, base: str, h: dict) -> dict:
    return {d["nome"]: d for d in cliente.get(base, headers=h).json()["documentos"]}


def _anexar_certidao(cliente, base: str, h: dict, validade: str = "2026-12-31") -> None:
    doc = _documentos(cliente, base, h)["Certidão negativa"]
    r = cliente.post(f"{base}/checklist/{doc['id']}", files={"arquivo": ("certidao.pdf", PDF)}, data={"validade": validade}, headers=h)
    assert r.status_code == 200, r.text


def test_sugere_e_reaproveita_do_outro_contrato_da_mesma_empresa(cliente, dois_contratos):
    a, b, hg, hf = dois_contratos
    base_a, base_b = _ate_o_checklist(cliente, a, hg, hf), _ate_o_checklist(cliente, b, hg, hf)
    # Sem nada juntado em outro contrato, não há sugestão
    assert _documentos(cliente, base_b, hg)["Certidão negativa"]["sugestao_outro_contrato"] is None
    _anexar_certidao(cliente, base_a, hg)
    doc = _documentos(cliente, base_b, hg)["Certidão negativa"]
    sugestao = doc["sugestao_outro_contrato"]
    assert sugestao["contrato_numero"] == "001/2026" and sugestao["validade_ate"] == "2026-12-31" and sugestao["arquivo_nome"] == "certidao.pdf"
    # O documento que não é da empresa nunca é sugerido
    assert _documentos(cliente, base_b, hg)["Folha de pagamento"]["sugestao_outro_contrato"] is None
    # Nada é copiado sozinho: só com a confirmação
    assert doc["arquivo"] is None
    r = cliente.post(f"{base_b}/checklist/{doc['id']}/reaproveitar", json={"origem_id": sugestao["origem_id"]}, headers=hg)
    assert r.status_code == 200, r.text
    copiado = {d["nome"]: d for d in r.json()["documentos"]}["Certidão negativa"]
    assert copiado["arquivo"] is not None and copiado["validade_ate"] == "2026-12-31"
    assert copiado["reaproveitado_contrato"] == "001/2026" and copiado["reaproveitado_de"] == "2026-01-01"
    # A etapa não conclui: falta a folha de pagamento
    assert r.json()["etapa_atual"] == "checklist"
    # O arquivo reaproveitado é baixável pela competência de destino
    assert cliente.get(f"{base_b}/arquivos/{copiado['arquivo']['anexo_id']}", headers=hg).content[:5] == b"%PDF-"
    # Já tem anexo: não reaproveita de novo
    assert cliente.post(f"{base_b}/checklist/{doc['id']}/reaproveitar", json={"origem_id": sugestao["origem_id"]}, headers=hg).status_code == 400


def test_trazer_todos_conclui_a_etapa_e_o_consolidado_nao_mostra_o_reaproveitamento(cliente, dois_contratos):
    a, b, hg, hf = dois_contratos
    itens = [{"nome": "Certidão negativa", "com_validade": True, "vale_outros_contratos": True}]
    base_a, base_b = _ate_o_checklist(cliente, a, hg, hf, itens), _ate_o_checklist(cliente, b, hg, hf, itens)
    assert cliente.post(f"{base_b}/checklist/reaproveitar-todos", headers=hg).status_code == 400  # nada para trazer
    _anexar_certidao(cliente, base_a, hg)
    r = cliente.post(f"{base_b}/checklist/reaproveitar-todos", headers=hg)
    assert r.status_code == 200, r.text
    assert r.json()["etapa_atual"] == "consolidado"  # todos anexados: a etapa concluiu sozinha
    consolidado = cliente.post(f"{base_b}/consolidado", headers=hg).json()["consolidado"]
    pdf = cliente.get(f"{base_b}/arquivos/{consolidado['anexo_id']}", headers=hg).content
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "Certidão negativa" in texto and "001/2026" not in texto.replace("Contrato 002/2026", "")


def test_recusas(cliente, admin, dois_contratos):
    a, b, hg, hf = dois_contratos
    base_a, base_b = _ate_o_checklist(cliente, a, hg, hf), _ate_o_checklist(cliente, b, hg, hf)
    _anexar_certidao(cliente, base_a, hg, validade="2026-01-20")  # vence antes do fim do período (31/01)
    doc = _documentos(cliente, base_b, hg)["Certidão negativa"]
    assert doc["sugestao_outro_contrato"] is None
    assert cliente.post(f"{base_b}/checklist/reaproveitar-todos", headers=hg).status_code == 400
    # Origem inventada ou item que não é da empresa: 400
    assert cliente.post(f"{base_b}/checklist/{doc['id']}/reaproveitar", json={"origem_id": doc["id"]}, headers=hg).status_code == 400
    folha = _documentos(cliente, base_b, hg)["Folha de pagamento"]
    assert cliente.post(f"{base_b}/checklist/{folha['id']}/reaproveitar", json={"origem_id": doc["id"]}, headers=hg).status_code == 400


def test_outra_empresa_e_nome_diferente_nao_servem(cliente, admin, dois_contratos):
    a, b, hg, hf = dois_contratos
    equipe = {"gestor": _id("gestora"), "fiscal_tecnico": _id("fiscal")}
    outra_empresa = criar_contrato(cliente, admin, empresa_id=criar_empresa(cliente, admin, base="55667788", razao="Outra Ltda")["id"], numero="003/2026", equipe=equipe)
    base_a, base_o = _ate_o_checklist(cliente, a, hg, hf), _ate_o_checklist(cliente, outra_empresa, hg, hf)
    _anexar_certidao(cliente, base_a, hg)
    # Empresas diferentes: sem sugestão, mesmo com o mesmo nome e a marca
    assert _documentos(cliente, base_o, hg)["Certidão negativa"]["sugestao_outro_contrato"] is None
    # Mesma empresa, mas nome diferente: também não
    itens = [{"nome": "Certidão federal", "com_validade": True, "vale_outros_contratos": True}]
    base_b = _ate_o_checklist(cliente, b, hg, hf, itens)
    assert _documentos(cliente, base_b, hg)["Certidão federal"]["sugestao_outro_contrato"] is None


def _id(login: str) -> int:
    from sqlalchemy import select

    from app.core.banco import FabricaSessao
    from app.models.usuario import Usuario

    with FabricaSessao() as sessao:
        return sessao.scalar(select(Usuario.id).where(Usuario.login == login))
