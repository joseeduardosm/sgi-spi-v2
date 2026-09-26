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
        "unidade_fornecimento": "posto",
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


# --- Nota fiscal (PDF + XML) e retenção de tributos ------------------------------------------------

CNPJ_CONTRATADA = gerar_cnpj("112223330001")  # empresa padrão de `criar_empresa`
CNPJ_SPI = "96480850000103"


def xml_nfe(valor: str, numero: str = "1", cnpj_emitente: str = CNPJ_CONTRATADA, cnpj_tomador: str = CNPJ_SPI,
            retencoes: dict | None = None, chave: str | None = None) -> bytes:
    """XML de NF-e (modelo 55) mínimo e autorizado, no layout da SEFAZ, para os testes."""
    chave = chave or f"35260{cnpj_emitente}55001{int(numero):09d}1{int(numero):08d}1"[:44].ljust(44, "0")
    r = {"vIRRF": "0.00", "vRetPrev": "0.00", "vRetPIS": "0.00", "vRetCOFINS": "0.00", "vRetCSLL": "0.00", **(retencoes or {})}
    ret = "".join(f"<{k}>{v}</{k}>" for k, v in r.items())
    return f"""<?xml version="1.0" encoding="UTF-8"?><nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
<NFe><infNFe Id="NFe{chave}" versao="4.00"><ide><nNF>{numero}</nNF><serie>1</serie><dhEmi>2026-02-03T10:00:00-03:00</dhEmi></ide>
<emit><CNPJ>{cnpj_emitente}</CNPJ><xNome>ACME Serviços Ltda</xNome></emit>
<dest><CNPJ>{cnpj_tomador}</CNPJ><xNome>SECRETARIA DE PARCERIAS EM INVESTIMENTOS</xNome></dest>
<det nItem="1"><prod><xProd>Serviços de limpeza</xProd><qCom>1.0000</qCom><vUnCom>{valor}</vUnCom><vProd>{valor}</vProd></prod></det>
<total><ICMSTot><vNF>{valor}</vNF></ICMSTot><retTrib>{ret}</retTrib></total></infNFe></NFe>
<protNFe versao="4.00"><infProt><chNFe>{chave}</chNFe><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>
</nfeProc>""".encode()


def juntar_nf(cliente, base: str, h: dict, valor: str, numero: str = "1", adicional: tuple[str, str] | None = None,
              recebida_em: str = "2026-02-05", prazo: str = "30", **xml_extras):
    """Etapa 3: envia PDF + XML (e a adicional, se `adicional=(valor, numero)`); devolve a resposta."""
    dados = {"recebida_em": recebida_em, "prazo_pagamento_dias": prazo}
    arquivos = {"arquivo": ("nf.pdf", PDF, "application/pdf"), "xml": ("nf.xml", xml_nfe(valor, numero, **xml_extras), "application/xml")}
    if adicional:
        dados["possui_adicional"] = "true"
        arquivos["arquivo_adicional"] = ("nf2.pdf", PDF, "application/pdf")
        arquivos["xml_adicional"] = ("nf2.xml", xml_nfe(adicional[0], adicional[1]), "application/xml")
    return cliente.post(f"{base}/nota-fiscal", data=dados, files=arquivos, headers=h)


def conferir_retencao(cliente, base: str, h: dict, principal: dict | None = None, adicional: dict | None = None, discriminacao: bool = True):
    """Etapa 4: salva a retenção de tributos; devolve a resposta."""
    corpo = {"principal": principal or {}, "adicional": adicional, "discriminacao_conferida": discriminacao}
    return cliente.put(f"{base}/retencao", json=corpo, headers=h)
