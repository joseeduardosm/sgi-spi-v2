# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os rascunhos compartilhados dos formulários do contrato (salvar, ver, versão e permissões).
"""Rascunhos no servidor: um por tela, visível a quem acessa Contratos e gravado por quem edita o contrato."""

from tests.apoio_contratos import criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario


def _url(contrato, tipo="diario", chave=""):
    return f"/api/contratos/{contrato['id']}/rascunhos/{tipo}" + (f"?chave={chave}" if chave else "")


def test_salvar_ver_por_outra_pessoa_e_versao(cliente, admin):
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva")
    leitora = criar_usuario("leitora", nome_completo="Leitora Souza")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", leitora: "LEITURA", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    h, hl, hf = cabecalho(cliente, "gestora"), cabecalho(cliente, "leitora"), cabecalho(cliente, "fiscal")
    # Sem rascunho: null
    assert cliente.get(_url(contrato), headers=h).json() is None
    corpo = {"dados": {"descricao": "<p>Posto <script>x</script>descoberto</p>", "possuiGlosa": False}, "versao": None}
    r = cliente.put(_url(contrato), json=corpo, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 1 and r.json()["atualizado_por_nome"] == "Gestora Silva" and "<script" not in r.json()["dados"]["descricao"]
    # Quem só lê Contratos vê o rascunho, mas não grava nem apaga
    visto = cliente.get(_url(contrato), headers=hl).json()
    assert visto["atualizado_por_nome"] == "Gestora Silva" and visto["versao"] == 1
    assert cliente.put(_url(contrato), json={"dados": {"a": 1}, "versao": 1}, headers=hl).status_code == 403
    assert cliente.delete(_url(contrato), headers=hl).status_code == 403
    # O fiscal (equipe) continua o rascunho; quem não viu a versão nova leva 409
    assert cliente.put(_url(contrato), json={"dados": {"descricao": "Fiscal"}, "versao": 1}, headers=hf).json()["versao"] == 2
    r = cliente.put(_url(contrato), json={"dados": {"descricao": "Gestora"}, "versao": 1}, headers=h)
    assert r.status_code == 409 and "Fiscal Souza" in r.json()["detalhe"]
    # Gravar sem ter visto o rascunho existente também é recusado
    assert cliente.put(_url(contrato), json={"dados": {"x": 1}}, headers=h).status_code == 409
    # Apagar libera para um novo
    assert cliente.delete(_url(contrato), headers=h).status_code == 204
    assert cliente.delete(_url(contrato), headers=h).status_code == 404
    assert cliente.put(_url(contrato), json={"dados": {"x": 1}}, headers=h).status_code == 200


def test_rascunho_por_competencia_exige_competencia_do_contrato(cliente, admin):
    contrato = criar_contrato(cliente, admin)
    assert cliente.get(_url(contrato, "avaliacao"), headers=admin).status_code == 404
    assert cliente.put(_url(contrato, "medicao", "00000000-0000-0000-0000-000000000000"), json={"dados": {}}, headers=admin).status_code == 404
    assert cliente.get(_url(contrato, "outro"), headers=admin).status_code == 422
