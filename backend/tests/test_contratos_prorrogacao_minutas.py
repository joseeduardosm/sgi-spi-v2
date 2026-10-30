# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as minutas e despachos da prorrogação: modelos, preenchimento, lacunas, dados digitados e extenso.
"""Prorrogação: tipo de modelo `prorrogacao`, preenchimento das minutas, escolha da Declaração pela modalidade e dados digitados."""

from datetime import date
from decimal import Decimal

from app.services.contratacoes import conteudo as conteudo_html
from app.services.contratos import extenso, modelos_prorrogacao_padrao, prorrogacao_mascara
from tests.apoio_contratos import criar_contrato, criar_empresa, dados_contrato


def _semear_modelos(cliente, admin) -> None:
    """No banco de teste não há a semente da migração: cria os sete modelos padrão pela API."""
    for variante, (nome, html) in modelos_prorrogacao_padrao.MODELOS.items():
        r = cliente.post("/api/contratos/modelos", json={"tipo": "prorrogacao", "nome": nome, "html": html, "variante": variante, "ativo": True}, headers=admin)
        assert r.status_code == 201, r.text


def test_extenso_de_numeros_valores_e_datas():
    assert extenso.inteiro(1100) == "mil e cem" and extenso.inteiro(2001) == "dois mil e um" and extenso.inteiro(1200000) == "um milhão e duzentos mil"
    assert extenso.reais(Decimal("1234.56")) == "mil duzentos e trinta e quatro reais e cinquenta e seis centavos"
    assert extenso.reais(Decimal("1")) == "um real" and extenso.reais(Decimal("1000000")) == "um milhão de reais"
    assert extenso.real(Decimal("1234567.8")) == "R$ 1.234.567,80"
    assert extenso.meses(12) == "12 (doze) meses" and extenso.meses(1) == "1 (um) mês"
    assert extenso.data(date(2026, 11, 1)) == "1º de novembro de 2026" and extenso.mes_ano(date(2026, 11, 5)) == "novembro de 2026"


def test_modelos_padrao_so_usam_placeholders_validos():
    for variante, (_nome, html) in modelos_prorrogacao_padrao.MODELOS.items():
        assert variante in prorrogacao_mascara.VARIANTES
        assert prorrogacao_mascara.invalidos(conteudo_html.sanitizar(html)) == [], variante
    assert set(modelos_prorrogacao_padrao.MODELOS) == set(prorrogacao_mascara.VARIANTES)


def test_preencher_lacunas_condicionais_e_escape():
    html, lacunas = prorrogacao_mascara.preencher(
        "<p>A #nrocontrato e ##dotacao##</p><p>#secustosnaorenovaveis fora</p><p>#sedemandavariavel dentro #razaosocialempresa</p>",
        {"nrocontrato": "1/2026", "razaosocialempresa": "A & B <Ltda>"}, {"secustosnaorenovaveis": False, "sedemandavariavel": True})
    assert "1/2026" in html and "fora" not in html and "A &amp; B &lt;Ltda&gt;" in html and "#" not in html
    assert "[classificação funcional e categoria econômica]" in html and lacunas == ["classificação funcional e categoria econômica"]


def test_modelo_com_placeholder_invalido_e_recusado(cliente, admin):
    corpo = {"tipo": "prorrogacao", "nome": "X", "html": "<p>#naoexiste</p>", "variante": "minuta_aditivo", "ativo": True}
    assert cliente.post("/api/contratos/modelos", json=corpo, headers=admin).status_code == 400
    # A variante da prorrogação é obrigatória e não pode ser a da portaria
    assert cliente.post("/api/contratos/modelos", json={**corpo, "html": "<p>ok</p>", "variante": "sem_anterior"}, headers=admin).status_code == 422
    # Só um modelo ativo por variante
    ok = {**corpo, "html": "<p>#nrocontrato</p>"}
    assert cliente.post("/api/contratos/modelos", json=ok, headers=admin).status_code == 201
    assert cliente.post("/api/contratos/modelos", json=ok, headers=admin).status_code == 409
    placeholders = cliente.get("/api/contratos/modelos/prorrogacao/placeholders", headers=admin).json()
    assert {"nrocontrato", "testemunhaanome", "secustosnaorenovaveis"} <= {p["nome"] for p in placeholders}


def test_minutas_preenchem_com_o_contrato_e_escolhem_a_declaracao_pela_modalidade(cliente, admin):
    _semear_modelos(cliente, admin)
    empresa = criar_empresa(cliente, admin)
    cliente.post(f"/api/contratos/empresas/{empresa['id']}/prepostos", json={"nome": "Maria Diretora", "cargo": "Diretora", "cpf": "529.982.247-25", "representante_legal": True}, headers=admin)
    contrato = criar_contrato(cliente, admin, empresa_id=empresa["id"])
    base = f"/api/contratos/{contrato['id']}"

    # Sem modalidade cadastrada, as duas declarações aparecem
    r = cliente.get(f"{base}/prorrogacao/minutas", headers=admin)
    assert r.status_code == 200, r.text
    variantes = [d["variante"] for d in r.json()["documentos"]]
    assert "declaracao_atendimento_licitacao" in variantes and "declaracao_atendimento_direta" in variantes and len(variantes) == 7

    corpo = dados_contrato(empresa["id"], numero=contrato["numero"], modalidade_contratacao="dispensa", versao=contrato["versao"])
    assert cliente.put(base, json=corpo, headers=admin).status_code == 200
    variantes = [d["variante"] for d in cliente.get(f"{base}/prorrogacao/minutas", headers=admin).json()["documentos"]]
    assert "declaracao_atendimento_direta" in variantes and "declaracao_atendimento_licitacao" not in variantes

    # Prazo salvo no rascunho: a minuta traz meses, datas e o representante legal
    assert cliente.put(f"{base}/prorrogacao", json={"meses": 12}, headers=admin).status_code == 200
    minuta = cliente.get(f"{base}/prorrogacao/minutas/minuta_aditivo", headers=admin).json()
    assert contrato["numero"] in minuta["html"] and "12 (doze) meses" in minuta["html"] and "Maria Diretora" in minuta["html"] and "529.982.247-25" in minuta["html"]
    assert "10 (dez) dias úteis" in minuta["html"] and "GIBBOR" not in minuta["html"]
    assert "nome da 1ª testemunha" in minuta["lacunas"] and "classificação funcional e categoria econômica" in minuta["lacunas"]
    # Cláusulas opcionais ficam de fora enquanto não forem ligadas
    assert "1.2." not in minuta["html"] and "2.3." not in minuta["html"]


def test_dados_digitados_completam_corrigem_e_ligam_clausulas(cliente, admin):
    _semear_modelos(cliente, admin)
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}"
    r = cliente.put(f"{base}/prorrogacao/dados-minuta", json={"dados": {
        "testemunhaanome": "Fulano de Tal", "dotacao": "10.122.0001 / 3.3.90.39", "valorprorrogacao": "1.500.000,00", "efeitoscustos": "01/01/2027", "nrotermo": "3º"}}, headers=admin)
    assert r.status_code == 200, r.text
    campos = {c["nome"]: c for c in r.json()["campos"]}
    assert campos["testemunhaanome"]["valor"] == "Fulano de Tal" and campos["testemunhaanome"]["digitado"] is True
    assert campos["valorprorrogacao"]["digitado"] is False and campos["valorprorrogacao"]["valor"] == "1.500.000,00"
    minuta = cliente.get(f"{base}/prorrogacao/minutas/minuta_aditivo", headers=admin).json()
    assert "Fulano de Tal" in minuta["html"] and "10.122.0001 / 3.3.90.39" in minuta["html"] and "R$ 1.500.000,00" in minuta["html"]
    assert "um milhão e quinhentos mil reais" in minuta["html"] and "3º TERMO" in minuta["html"]
    # Cláusula 1.2 ligada pela data de efeito
    assert "1.2." in minuta["html"] and "01/01/2027" in minuta["html"]
    # O conjunto enviado substitui o anterior; dado desconhecido ou condicional é recusado
    cliente.put(f"{base}/prorrogacao/dados-minuta", json={"dados": {"testemunhaanome": ""}}, headers=admin)
    assert "Fulano de Tal" not in cliente.get(f"{base}/prorrogacao/minutas/minuta_aditivo", headers=admin).json()["html"]
    assert cliente.put(f"{base}/prorrogacao/dados-minuta", json={"dados": {"inventado": "x"}}, headers=admin).status_code == 400
    assert cliente.put(f"{base}/prorrogacao/dados-minuta", json={"dados": {"serepactuacao": "x"}}, headers=admin).status_code == 400


def test_minuta_sem_modelo_ativo_ou_variante_inexistente_da_404(cliente, admin):
    contrato = criar_contrato(cliente, admin)
    base = f"/api/contratos/{contrato['id']}"
    assert cliente.get(f"{base}/prorrogacao/minutas/minuta_aditivo", headers=admin).status_code == 404
    assert cliente.get(f"{base}/prorrogacao/minutas/outra", headers=admin).status_code == 404
    docs = cliente.get(f"{base}/prorrogacao/minutas", headers=admin).json()["documentos"]
    assert all(d["modelo_ativo"] is False for d in docs)
