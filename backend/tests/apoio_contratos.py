# Criado por José Eduardo Santana Martins
# Este arquivo serve para oferecer dados e funções de apoio aos testes do módulo de contratos.
"""Apoio aos testes do módulo de contratos: documentos válidos, empresa, contrato e ACL."""

from datetime import date

from fastapi.testclient import TestClient

from app.schemas.contratos.validadores import _digito
from app.services.documentos.pdf import DocumentoPdf

# PDF válido de verdade, gerado pelo próprio sistema, para os testes de upload
PDF = DocumentoPdf("Documento de teste").paragrafo("conteúdo").gerar()


def gerar_cnpj(base: str) -> str:
    """CNPJ válido a partir de uma base (completa com zeros e calcula os dígitos verificadores)."""
    base = base.rjust(12, "0")[:12]
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    primeiro = _digito(base, pesos)
    return base + primeiro + _digito(base + primeiro, [6, *pesos])


def gerar_cpf(base: str) -> str:
    """CPF válido a partir de uma base (completa com zeros e calcula os dígitos verificadores)."""
    base = base.rjust(9, "0")[:9]
    primeiro = _digito(base, list(range(10, 1, -1)))
    return base + primeiro + _digito(base + primeiro, list(range(11, 1, -1)))


def criar_empresa(cliente: TestClient, cabecalho: dict, base: str = "11222333", razao: str = "ACME Serviços Ltda") -> dict:
    """Cadastra uma empresa pela API e devolve o JSON da resposta."""
    r = cliente.post(
        "/api/contratos/empresas",
        json={"cnpj": gerar_cnpj(base + "0001"), "razao_social": razao, "nome_fantasia": "ACME", "endereco": "Rua A, 1"},
        headers=cabecalho,
    )
    assert r.status_code == 201, r.text
    return r.json()


def item(descricao: str = "Limpeza", tipo: str = "continuo", **extras) -> dict:
    """Item de contrato pronto para o cadastro; os argumentos sobrescrevem campos."""
    dados = {
        "descricao": descricao,
        "tipo": tipo,
        "calcula_pro_rata": True,
        "codigo_classe": "01",
        "codigo_natureza_despesa": "339039",
        "codigo_siafisico": "123",
        "codigo_catmat_catser": "456",
        "quantidade_mensal": "2",
        "quantidade_total": "0",
        "valor_unitario": "1000.00",
    }
    dados.update(extras)
    return dados


def dados_contrato(empresa_id: str, numero: str = "001/2026", **extras) -> dict:
    """Corpo completo de cadastro de contrato (um item contínuo e um sob demanda)."""
    dados = {
        "numero": numero,
        "empresa_id": empresa_id,
        "apelido": "Limpeza sede",
        "objeto": "Serviços contínuos de limpeza predial",
        "data_inicio": date(2026, 1, 1).isoformat(),
        "vigencia_inicial_meses": 12,
        "vigencia_maxima_meses": 60,
        "periodicidade_meses": 1,
        "mes_reajuste": 1,
        "sei_gestao_numero": "SPI-PRC-2026/00001",
        "sei_gestao_link": "https://sei.sp.gov.br/gestao",
        "sei_execucao_numero": "SPI-PRC-2026/00002",
        "sei_execucao_link": "https://sei.sp.gov.br/execucao",
        "equipe": {},
        "itens": [item(), item("Material", "sob_demanda", quantidade_mensal="0", quantidade_total="100", valor_unitario="10.50")],
    }
    dados.update(extras)
    return dados


def criar_contrato(cliente: TestClient, cabecalho: dict, **extras) -> dict:
    """Cadastra um contrato pela API (criando a empresa, se não for informada) e devolve o detalhe."""
    empresa_id = extras.pop("empresa_id", None) or criar_empresa(cliente, cabecalho)["id"]
    r = cliente.post("/api/contratos", json=dados_contrato(empresa_id, **extras), headers=cabecalho)
    assert r.status_code == 201, r.text
    return r.json()


def restringir_contratos(cliente: TestClient, admin: dict, niveis: dict[int, str]) -> None:
    """Cadastra o recurso `contratos` com uma regra por usuário (ex.: {id: "MODIFICACAO"})."""
    r = cliente.post("/api/acl/recursos", json={"nome": "Contratos", "slug": "contratos"}, headers=admin)
    assert r.status_code == 201, r.text
    for usuario_id, nivel in niveis.items():
        corpo = {"recurso_id": r.json()["id"], "nivel": nivel, "usuarios_ids": [usuario_id], "setores_ids": []}
        assert cliente.post("/api/acl/regras", json=corpo, headers=admin).status_code == 201
