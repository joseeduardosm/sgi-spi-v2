# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a etapa "Retenção de Tributos", a NF com XML e os e-mails ao Financeiro e à equipe.
"""Retenção de tributos: leitura do XML (NF-e e NFS-e), etapa de NF com PDF + XML, permissão do Financeiro
(membro ou Departamento do setor configurado e filhos), conferências automáticas, PDF, e-mails e pendências.

O envio usa o servidor SMTP simulado de `tests/test_smtp.py` (sem rede).
"""

import smtplib
from datetime import date
from pathlib import Path

import pytest

from app.services.contratos.erros import ErroRegraContrato
from app.services.contratos.leitor_nota_xml import ler_nota
from tests.apoio_contratos import (
    CNPJ_SPI,
    PDF,
    conferir_retencao,
    criar_contrato,
    juntar_nf,
    restringir_contratos,
)
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor

HOJE = date(2026, 3, 15)
EXEMPLO = Path(__file__).parent / "dados" / "nfe_exemplo.xml"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    for modulo in ("servico_contratos", "servico_competencias", "servico_diario"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: HOJE)
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)


# --- Leitura do XML --------------------------------------------------------------------------------

def test_le_a_nfe_real_de_exemplo():
    dados = ler_nota(EXEMPLO.read_bytes())
    assert (dados.modelo, dados.numero, dados.serie, dados.emissao) == ("nfe", "363", "1", "2026-09-25")
    assert dados.chave == "35260905686994000165550010000003631068862301" and dados.autorizada is True
    assert dados.emitente.cnpj == "05686994000165" and dados.emitente.razao_social == "AGINET DATACENTER INFORMATICA LTDA"
    assert dados.tomador.cnpj == CNPJ_SPI and dados.valor_bruto == "1341970.42"
    assert len(dados.itens) == 6 and dados.itens[0].valor_unitario == "288816.3375"
    assert dados.competencia is None and dados.codigo_servico is None and set(dados.retencoes.values()) == {"0.00"}


def test_le_nfse_padrao_nacional():
    xml = f"""<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS3550308123"><nNFSe>77</nNFSe>
      <emit><CNPJ>11222333000181</CNPJ><xNome>ACME</xNome></emit><valores><vISSQN>50.00</vISSQN><vLiq>1845.00</vLiq></valores>
      <DPS><infDPS><dhEmi>2026-02-03T10:00:00-03:00</dhEmi><dCompet>2026-01-31</dCompet>
      <toma><CNPJ>{CNPJ_SPI}</CNPJ><xNome>SPI</xNome></toma>
      <serv><cServ><cTribNac>070201</cTribNac><xDescServ>Limpeza predial - janeiro/2026</xDescServ></cServ></serv>
      <valores><vServPrest><vServ>2000.00</vServ></vServPrest><trib><tribMun><tpRetISSQN>2</tpRetISSQN></tribMun>
      <tribFed><piscofins><vPis>13.00</vPis><vCofins>60.00</vCofins><tpRetPisCofins>1</tpRetPisCofins></piscofins>
      <vRetCP>0.00</vRetCP><vRetIRRF>30.00</vRetIRRF><vRetCSLL>2.00</vRetCSLL></tribFed></trib></valores></infDPS></DPS></infNFSe></NFSe>"""
    dados = ler_nota(xml.encode())
    assert (dados.modelo, dados.numero, dados.competencia, dados.codigo_servico) == ("nfse_nacional", "77", "2026-01-31", "070201")
    assert dados.valor_bruto == "2000.00" and dados.valor_liquido == "1845.00" and "Limpeza" in dados.discriminacao
    assert dados.retencoes == {"ir": "30.00", "inss": "0.00", "iss": "50.00", "pis": "13.00", "cofins": "60.00", "csll": "2.00"}


def test_le_nfse_da_prefeitura_de_sao_paulo():
    xml = f"""<RetornoConsulta xmlns="http://www.prefeitura.sp.gov.br/nfe"><NFe xmlns="">
      <ChaveNFe><InscricaoPrestador>12345678</InscricaoPrestador><NumeroNFe>4512</NumeroNFe><CodigoVerificacao>ABCD1234</CodigoVerificacao></ChaveNFe>
      <DataEmissaoNFe>2026-02-03T10:00:00</DataEmissaoNFe><DataFatoGeradorNFe>2026-01-31T00:00:00</DataFatoGeradorNFe>
      <CPFCNPJPrestador><CNPJ>11222333000181</CNPJ></CPFCNPJPrestador><RazaoSocialPrestador>ACME</RazaoSocialPrestador>
      <StatusNFe>N</StatusNFe><ValorServicos>2000.00</ValorServicos><CodigoServico>7870</CodigoServico>
      <ValorPIS>13.00</ValorPIS><ValorCOFINS>60.00</ValorCOFINS><ValorINSS>0</ValorINSS><ValorIR>30.00</ValorIR><ValorCSLL>2.00</ValorCSLL>
      <ISSRetido>true</ISSRetido><ValorISS>100.00</ValorISS>
      <CPFCNPJTomador><CNPJ>{CNPJ_SPI}</CNPJ></CPFCNPJTomador><RazaoSocialTomador>SPI</RazaoSocialTomador>
      <Discriminacao>Limpeza predial - janeiro/2026</Discriminacao></NFe></RetornoConsulta>"""
    dados = ler_nota(xml.encode())
    assert (dados.modelo, dados.numero, dados.codigo_servico, dados.autorizada) == ("nfse_sp", "4512", "7870", True)
    assert dados.tomador.cnpj == CNPJ_SPI and dados.retencoes["iss"] == "100.00" and dados.retencoes["ir"] == "30.00"


@pytest.mark.parametrize("conteudo, trecho", [
    (b"", "vazio"),
    (b"nao e xml", "XML válido"),
    (b"<?xml version='1.0'?><outro/>", "não reconhecido"),
    (b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]><NFe/>", "DOCTYPE"),
])
def test_xml_invalido_e_recusado(conteudo, trecho):
    with pytest.raises(ErroRegraContrato, match=trecho):
        ler_nota(conteudo)


# --- Cenário com equipe, Financeiro e SMTP ------------------------------------------------------------

@pytest.fixture
def cenario(cliente, admin):
    """Competência 01/2026 com medição concluída; Financeiro = membro do setor filho e usuário pelo Departamento."""
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva", email="gestora@sp.gov.br")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza", email="fiscal@sp.gov.br")
    membro = criar_usuario("financeiro1", nome_completo="Fin Membro", email="fin1@sp.gov.br")
    departamento = criar_usuario("financeiro2", nome_completo="Fin Departamento", email="fin2@sp.gov.br", departamento="Contabilidade")
    outro = criar_usuario("outro", email="outro@sp.gov.br")
    # O Financeiro precisa ao menos de LEITURA em contratos (a ACL continua valendo)
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO", membro: "LEITURA", departamento: "LEITURA", outro: "LEITURA"})
    raiz = cliente.post("/api/setores", json={"nome": "Diretoria de Orçamento e Finanças", "membros_ids": []}, headers=admin).json()["id"]
    cliente.post("/api/setores", json={"nome": "Execução Orçamentária", "setor_pai_id": raiz, "membros_ids": [membro]}, headers=admin)
    cliente.post("/api/setores", json={"nome": "Contabilidade", "setor_pai_id": raiz, "membros_ids": []}, headers=admin)
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    g, f = cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")
    _preparar_execucao(cliente, contrato, g)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=g)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=g).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=g).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]]
    cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=g)
    cliente.post(f"{base}/medicao/ciencia", headers=g)
    cliente.post(f"{base}/medicao/ciencia", headers=f)
    assert cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=g).status_code == 200
    SmtpSimulado.enviadas.clear()
    return contrato, base, g


def test_nf_envia_email_ao_financeiro_com_copia_para_a_equipe(cliente, cenario):
    contrato, base, gestora = cenario
    r = juntar_nf(cliente, base, gestora, "2105.00", "123", retencoes={"vIRRF": "31.58"})
    assert r.status_code == 200, r.text
    detalhe = r.json()
    assert detalhe["etapa_atual"] == "retencao" and detalhe["nota_fiscal"]["retencao_ir"] == "31.58"  # sugestão lida do XML
    assert detalhe["nota_fiscal"]["xml"]["nome"] == "nf.xml" and detalhe["nota_fiscal"]["dados_xml"]["numero"] == "123"
    conferencias = {c["descricao"]: c["situacao"] for c in detalhe["nota_fiscal"]["conferencias"]}
    assert conferencias["Tomador = SPI"] == "ok" and conferencias["Emitente = empresa contratada"] == "ok"
    assert conferencias["Valor × valor autorizado da medição"] == "ok" and conferencias["Nota autorizada"] == "ok"

    mensagem, _, destinatarios, _ = SmtpSimulado.enviadas[0]
    assert mensagem["Subject"] == "Contrato 001/2026 - 01/2026 - Nota fiscal anexada no sistema"
    assert mensagem["To"] == "fin1@sp.gov.br, fin2@sp.gov.br" and mensagem["Cc"] == "gestora@sp.gov.br, fiscal@sp.gov.br"
    texto = mensagem.get_body(("plain",)).get_content()
    assert "Foi juntada a nota fiscal para conferência de tributação pelo setor competente" in texto
    assert f"/contratos/{contrato['id']}/execucao/2026-01?etapa=retencao" in texto
    assert cliente.get(base, headers=gestora).json()["email_nf"]["ok"] is True


def test_mesma_nota_nao_entra_em_duas_competencias(cliente, cenario):
    contrato, base, gestora = cenario
    assert juntar_nf(cliente, base, gestora, "2105.00", "123").status_code == 200
    fevereiro = cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=gestora).json()
    outra = _url(contrato, f"/competencias/{fevereiro['id']}")
    # fevereiro ainda está na medição: força a etapa só para testar a chave repetida
    from app.core.banco import FabricaSessao
    from app.models.contratos import Competencia

    with FabricaSessao() as sessao:
        sessao.get(Competencia, __import__("uuid").UUID(fevereiro["id"])).etapa_atual = "nota_fiscal"
        sessao.commit()
    r = juntar_nf(cliente, outra, gestora, "2105.00", "123")
    assert r.status_code == 400 and "já foi juntada à competência 01/2026" in r.json()["detalhe"]


def test_financeiro_confere_mesmo_fora_da_equipe_e_outros_nao(cliente, admin, cenario):
    contrato, base, gestora = cenario
    juntar_nf(cliente, base, gestora, "2105.00", "123", cnpj_emitente="99888777000100")
    detalhe = cliente.get(base, headers=cabecalho(cliente, "financeiro1")).json()
    assert detalhe["pode_conferir_retencao"] is True and detalhe["pode_editar"] is False
    assert {c["descricao"]: c["situacao"] for c in detalhe["nota_fiscal"]["conferencias"]}["Emitente = empresa contratada"] == "alerta"
    r = conferir_retencao(cliente, base, cabecalho(cliente, "outro"), {"ir": "31.58"})
    assert r.status_code == 403 and "Financeiro" in r.json()["detalhe"]

    # Pendência no painel do Financeiro (membro do setor filho)
    pendencias = cliente.get("/api/contratos/painel", headers=cabecalho(cliente, "financeiro1")).json()["minhas_pendencias"]
    assert [p["tipo"] for p in pendencias] == ["retencao"] and "conferir a retenção" in pendencias[0]["descricao"]

    # Financeiro pelo Departamento salva: PDF gerado, etapa avança e e-mail à equipe com o link da próxima etapa
    SmtpSimulado.enviadas.clear()
    r = conferir_retencao(cliente, base, cabecalho(cliente, "financeiro2"), {"ir": "31.58", "csll": "10"})
    assert r.status_code == 200, r.text
    detalhe = r.json()
    assert detalhe["etapa_atual"] == "cadin" and detalhe["retencao"]["por_nome"] == "Fin Departamento"
    assert detalhe["nota_fiscal"]["retencao_csll"] == "10.00" and detalhe["nota_fiscal"]["valor_liquido"] == "2063.42"
    pdf = cliente.get(f"{base}/arquivos/{detalhe['retencao']['pdf']['anexo_id']}", headers=gestora)
    assert pdf.content[:5] == b"%PDF-"
    mensagem, _, destinatarios, _ = SmtpSimulado.enviadas[0]
    assert mensagem["Subject"] == "Contrato 001/2026 - 01/2026 - Retenções tributárias conferidas"
    assert sorted(destinatarios) == ["fiscal@sp.gov.br", "gestora@sp.gov.br"]
    assert "?etapa=cadin" in mensagem.get_body(("plain",)).get_content()


def test_sem_financeiro_cadastrado_o_erro_fica_registrado(cliente, admin, cenario):
    contrato, base, gestora = cenario
    for setor in cliente.get("/api/setores", headers=admin).json():
        cliente.put(f"/api/setores/{setor['id']}", json={"nome": setor["nome"] + " (antigo)", "setor_pai_id": setor.get("setor_pai_id"),
                                                         "membros_ids": []}, headers=admin)
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    email = cliente.get(base, headers=gestora).json()["email_nf"]
    assert email["ok"] is False and "Nenhum usuário do Financeiro" in email["erro"]


def test_reabrir_a_nota_fiscal_desfaz_a_conferencia(cliente, admin, cenario):
    contrato, base, gestora = cenario
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    conferir_retencao(cliente, base, gestora, {"ir": "31.58"})
    r = cliente.post(f"{base}/reabrir", json={"etapa": "nota_fiscal", "justificativa": "NF errada"}, headers=admin)
    assert r.status_code == 200 and r.json()["etapa_atual"] == "nota_fiscal" and r.json()["retencao"] is None
    # Nova NF: exige nova conferência
    assert juntar_nf(cliente, base, gestora, "2105.00", "124").json()["etapa_atual"] == "retencao"


def test_cadin_e_checklist_em_paralelo_com_a_retencao_e_consolidado_so_no_fim(cliente, cenario):
    """Depois da NF, CADIN e checklist já podem ser feitos; o consolidado exige também a retenção conferida."""
    contrato, base, gestora = cenario
    detalhe = juntar_nf(cliente, base, gestora, "2105.00", "123").json()
    assert detalhe["etapas_abertas"] == ["retencao", "cadin", "checklist"]

    r = cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200 and r.json()["etapas_abertas"] == ["retencao", "checklist"] and "cadin" in r.json()["etapas_concluidas"]
    for documento in r.json()["documentos"]:
        r = cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    detalhe = r.json()
    assert detalhe["etapas_abertas"] == ["retencao"] and detalhe["etapa_atual"] == "retencao"

    r = cliente.post(f"{base}/consolidado", headers=gestora)
    assert r.status_code == 400 and "Falta concluir: retenção de tributos" in r.json()["detalhe"]
    r = cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora)
    assert r.status_code == 400 and "já foi concluída" in r.json()["detalhe"]

    detalhe = conferir_retencao(cliente, base, gestora, {"ir": "31.58"}).json()
    assert detalhe["etapa_atual"] == "consolidado" and detalhe["etapas_abertas"] == ["consolidado"]
    assert cliente.post(f"{base}/consolidado", headers=gestora).json()["etapa_atual"] == "ordem_bancaria"
