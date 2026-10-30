# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a origem da contratação, a garantia, o representante legal da empresa e os parâmetros da prorrogação.
"""Contrato: modalidade e garantia (gravação, leitura, histórico), representante legal do preposto e parâmetros da prorrogação."""

from app.core.banco import FabricaSessao
from app.models.contratos.parametros import ParametrosContratos
from tests.apoio_contratos import criar_contrato, criar_empresa, dados_contrato


def test_modalidade_e_garantia_gravam_leem_e_vao_para_o_historico(cliente, admin):
    empresa = criar_empresa(cliente, admin)
    contrato = criar_contrato(cliente, admin, empresa_id=empresa["id"])
    assert contrato["modalidade_contratacao"] == "" and contrato["exige_garantia"] is False and contrato["garantia_valor"] is None
    corpo = dados_contrato(empresa["id"], numero=contrato["numero"], modalidade_contratacao="dispensa", exige_garantia=True, garantia_modalidade="seguro_garantia",
                           garantia_percentual="5", garantia_valor="12345.67", garantia_emissor="Seguradora Exemplo S.A.", garantia_cnpj_emissor="11.222.333/0001-81",
                           garantia_apolice="AP-2026-001", versao=contrato["versao"])
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    dados = cliente.get(f"/api/contratos/{contrato['id']}", headers=admin).json()
    assert dados["modalidade_contratacao"] == "dispensa" and dados["exige_garantia"] is True and dados["garantia_modalidade"] == "seguro_garantia"
    assert dados["garantia_valor"] == "12345.67" and dados["garantia_cnpj_emissor"] == "11222333000181" and dados["garantia_apolice"] == "AP-2026-001"
    # Valor inválido é recusado
    assert cliente.put(f"/api/contratos/{contrato['id']}", json={**corpo, "modalidade_contratacao": "outra"}, headers=admin).status_code == 422


def test_preposto_pode_ser_marcado_como_representante_legal(cliente, admin):
    empresa = criar_empresa(cliente, admin)
    r = cliente.post(f"/api/contratos/empresas/{empresa['id']}/prepostos", json={"nome": "Maria Diretora", "cargo": "Diretora", "representante_legal": True}, headers=admin)
    assert r.status_code == 201, r.text
    prepostos = r.json()["prepostos"]
    assert [p["representante_legal"] for p in prepostos if p["nome"] == "Maria Diretora"] == [True]


def test_parametros_da_prorrogacao_tem_padroes_e_gravam(cliente, admin):
    with FabricaSessao() as s:
        linha = s.get(ParametrosContratos, 1)
        if linha is not None:
            s.delete(linha)
            s.commit()
    leitura = cliente.get("/api/contratos/parametros", headers=admin).json()
    assert leitura["ssgc_nome"] == "Laercio Paulino Simões" and leitura["pncp_dias_uteis_licitacao"] == 20 and leitura["pncp_dias_uteis_direta"] == 10
    assert leitura["parecer_referencial_vigencia_ate"] == "2027-02-09"
    corpo = {k: v for k, v in leitura.items() if k not in ("atualizado_por_nome", "atualizado_em", "padroes")}
    r = cliente.put("/api/contratos/parametros", json={**corpo, "ssgc_nome": "Nova Autoridade", "pncp_dias_uteis_direta": 8}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["ssgc_nome"] == "Nova Autoridade" and r.json()["pncp_dias_uteis_direta"] == 8
