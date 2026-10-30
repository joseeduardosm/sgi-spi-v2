# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o checklist "a partir de…": documentos incluídos durante a etapa do checklist da competência.
"""Checklist da execução mensal como ponto de partida: durante a etapa dá para incluir documentos fora do modelo.

O incluído vale só para a competência, nunca é obrigatório, pode ser excluído com a etapa aberta, não muda o checklist
do contrato e sobrevive quando a etapa volta e o checklist é copiado de novo.
"""

from tests.apoio_contratos import PDF, conferir_retencao, juntar_nf
from tests.test_checklist_entre_contratos import _ate_o_checklist, _documentos, _hoje, dois_contratos  # noqa: F401 - fixtures

ITENS = [{"nome": "Folha de pagamento"}, {"nome": "Certidão do FGTS", "obrigatorio": False}]


def _incluir(cliente, base, h, nome="Relatório extra", descricao="Pedido pela fiscalização"):
    return cliente.post(f"{base}/checklist/incluir", data={"nome": nome, "descricao": descricao}, files={"arquivo": ("extra.pdf", PDF)}, headers=h)


def test_inclui_nao_trava_entra_e_sai(cliente, dois_contratos):
    a, _, hg, hf = dois_contratos
    base = _ate_o_checklist(cliente, a, hg, hf, itens=ITENS)

    r = _incluir(cliente, base, hg)
    assert r.status_code == 200, r.text
    extra = _documentos(cliente, base, hg)["Relatório extra"]
    assert extra["incluido_no_processo"] is True and extra["obrigatorio"] is False
    assert extra["observacao"] == "Pedido pela fiscalização" and extra["arquivo"] is not None and extra["incluido_por_nome"]
    # Vem depois dos itens do modelo
    assert [d["nome"] for d in cliente.get(base, headers=hg).json()["documentos"]][-1] == "Relatório extra"

    # Sem nome não inclui; item do modelo não pode ser excluído
    assert cliente.post(f"{base}/checklist/incluir", data={"nome": "  "}, files={"arquivo": ("x.pdf", PDF)}, headers=hg).status_code == 400
    folha = _documentos(cliente, base, hg)["Folha de pagamento"]
    assert cliente.delete(f"{base}/checklist/{folha['id']}", headers=hg).status_code == 400

    # O incluído sai; incluo outro e concluo só com o obrigatório do modelo (o incluído não trava)
    assert cliente.delete(f"{base}/checklist/{extra['id']}", headers=hg).status_code == 200
    assert "Relatório extra" not in _documentos(cliente, base, hg)
    assert _incluir(cliente, base, hg, nome="Ata de reunião").status_code == 200
    r = cliente.post(f"{base}/checklist/{folha['id']}", files={"arquivo": ("folha.pdf", PDF)}, headers=hg)
    assert r.status_code == 200, r.text
    assert cliente.post(f"{base}/checklist/concluir", headers=hg).status_code == 200

    # Etapa concluída: não inclui nem exclui mais; o checklist do contrato não ganhou o item
    ata = _documentos(cliente, base, hg)["Ata de reunião"]
    assert _incluir(cliente, base, hg, nome="Tarde demais").status_code == 400
    assert cliente.delete(f"{base}/checklist/{ata['id']}", headers=hg).status_code == 400
    modelo = cliente.get(f"/api/contratos/{a['id']}/checklists", headers=hg).json()[0]
    assert [i["nome"] for i in modelo["itens"]] == [i["nome"] for i in ITENS]


def test_incluido_sobrevive_quando_a_etapa_volta(cliente, dois_contratos):
    a, _, hg, hf = dois_contratos
    base = _ate_o_checklist(cliente, a, hg, hf, itens=ITENS)
    assert _incluir(cliente, base, hg).status_code == 200

    # Volta para a nota fiscal: a cópia do checklist é descartada e refeita quando a etapa recomeça
    r = cliente.post(f"{base}/reabrir", json={"etapa": "nota_fiscal", "justificativa": "Corrigir a NF"}, headers=hg)
    assert r.status_code == 200, r.text
    assert juntar_nf(cliente, base, hg, "2105.00", numero="1").status_code == 200
    assert conferir_retencao(cliente, base, hg).status_code == 200

    documentos = cliente.get(base, headers=hg).json()["documentos"]
    assert [d["nome"] for d in documentos] == ["Folha de pagamento", "Certidão do FGTS", "Relatório extra"]
    assert len({d["ordem"] for d in documentos}) == 3 and documentos[-1]["arquivo"] is not None
