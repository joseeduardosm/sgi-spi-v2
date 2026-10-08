# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a recusa da nota fiscal pelo Financeiro, o ciclo de nova nota e a trilha no consolidado.
"""Recusa da NF na retenção: justificativa, e-mail com PDF à equipe e a todos os prepostos, etapa NF reaberta, ciclo ilimitado e consolidado."""

from io import BytesIO

from pypdf import PdfReader

from tests.apoio_contratos import PDF, conferir_retencao, juntar_nf
from tests.conftest import cabecalho
from tests.test_contratos_retencao import _ambiente, cenario  # noqa: F401 — fixtures
from tests.test_smtp import SmtpSimulado

JUSTIFICATIVA = "Valor do ISS retido incorreto para o município do prestador."


def _prepostos(cliente, admin, contrato):
    """Dois prepostos ativos da empresa (todos recebem o e-mail da recusa)."""
    empresa = contrato["empresa"]["id"]
    for cpf, nome, email, ativo in (("52998224725", "Preposto Um", "preposto1@empresa.com", True), ("11144477735", "Preposto Dois", "preposto2@empresa.com", True)):
        r = cliente.post(f"/api/contratos/empresas/{empresa}/prepostos", json={"nome": nome, "cpf": cpf, "email": email, "telefone": "11999990000", "ativo": ativo}, headers=admin)
        assert r.status_code == 201, r.text


def test_recusa_envia_email_com_pdf_a_equipe_e_prepostos_e_reabre_a_nf(cliente, admin, cenario):
    contrato, base, gestora = cenario
    _prepostos(cliente, admin, contrato)
    fin = cabecalho(cliente, "financeiro1")
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    # Justificativa obrigatória; só quem confere recusa
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": "curta"}, headers=fin).status_code == 422
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=cabecalho(cliente, "outro")).status_code == 403
    SmtpSimulado.enviadas.clear()
    r = cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=fin)
    assert r.status_code == 200, r.text
    detalhe = r.json()
    # A etapa da nota fiscal volta a ficar aberta e a nota recusada sai da competência
    assert detalhe["etapa_atual"] == "nota_fiscal" and detalhe["etapas_abertas"] == ["nota_fiscal"] and detalhe["notas_fiscais"] == []
    recusa = detalhe["recusas"][0]
    assert recusa["ordem"] == 1 and recusa["justificativa"] == JUSTIFICATIVA and recusa["recusada_por_nome"] == "Fin Membro"
    assert recusa["notas"][0]["numero"] == "123" and recusa["notas"][0]["arquivo"]["nome"]
    # PDF da recusa baixável (para juntar a um processo), e o PDF da nota recusada também
    pdf = cliente.get(f"{base}/arquivos/{recusa['pdf']['anexo_id']}", headers=gestora)
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert pdf.content[:5] == b"%PDF-" and "Recusa nº 1" in texto and "ISS retido incorreto" in texto
    assert cliente.get(f"{base}/arquivos/{recusa['notas'][0]['arquivo']['anexo_id']}", headers=gestora).content[:5] == b"%PDF-"
    # E-mail obrigatório: equipe + TODOS os prepostos (quem recusou em cópia), com o PDF anexado
    mensagem, _, destinatarios, _ = SmtpSimulado.enviadas[0]
    assert mensagem["Subject"] == "Contrato 001/2026 - 01/2026 - Nota fiscal recusada (recusa nº 1)"
    assert {"gestora@sp.gov.br", "fiscal@sp.gov.br", "preposto1@empresa.com", "preposto2@empresa.com", "fin1@sp.gov.br"} <= set(destinatarios)
    assert JUSTIFICATIVA in mensagem.get_body(("plain",)).get_content()
    assert [a.get_content_type() for a in mensagem.iter_attachments()] == ["application/pdf"]
    assert cliente.get(base, headers=gestora).json()["recusas"][0]["email"]["ok"] is True
    # Reenvio do e-mail da recusa
    SmtpSimulado.enviadas.clear()
    r = cliente.post(f"{base}/recusas/{recusa['id']}/reenviar-email", headers=fin)
    assert r.status_code == 200 and len(SmtpSimulado.enviadas) == 1


def test_ciclo_recusa_nova_nota_recusa_e_aprovacao_com_trilha_no_consolidado(cliente, admin, cenario):
    contrato, base, gestora = cenario
    fin = cabecalho(cliente, "financeiro1")
    # Antes da retenção, CADIN e checklist já ficam prontos (correm em paralelo): a recusa não os apaga
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    assert cliente.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=gestora).status_code == 200
    documentos = cliente.get(base, headers=gestora).json()["documentos"]
    for d in documentos:
        cliente.post(f"{base}/checklist/{d['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=gestora)
    antes = cliente.get(base, headers=gestora).json()
    assert antes["etapas_abertas"] == ["retencao"]
    # 1ª recusa → nota 124 (sem XML, com valor informado) → 2ª recusa → nota 125 → aprovação
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=fin).status_code == 200
    estado = cliente.get(base, headers=gestora).json()
    assert estado["etapa_atual"] == "nota_fiscal" and estado["recusas"][0]["ordem"] == 1
    r = juntar_nf(cliente, base, gestora, "2105.00", "124")
    assert r.status_code == 200, r.text
    assert r.json()["etapa_atual"] == "retencao" and r.json()["etapas_abertas"] == ["retencao"]  # CADIN e checklist continuam concluídos
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": "Nota emitida com o CNPJ do tomador incorreto."}, headers=fin).status_code == 200
    r = juntar_nf(cliente, base, gestora, "2105.00", "125")
    assert r.status_code == 200 and [x["ordem"] for x in r.json()["recusas"]] == [1, 2]
    r = conferir_retencao(cliente, base, fin, {"ir": "31.58"})
    assert r.status_code == 200, r.text
    assert r.json()["etapa_atual"] == "consolidado" and r.json()["pode_recusar"] is False
    # Consolidado: nota 123 (recusada) → recusa 1 → nota 124 (recusada) → recusa 2 → nota 125 (aprovada) → retenção
    c = cliente.post(f"{base}/consolidado", headers=gestora)
    assert c.status_code == 200, c.text
    pdf = cliente.get(f"{base}/arquivos/{c.json()['consolidado']['anexo_id']}", headers=gestora).content
    textos = [" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(pdf)).pages]
    indice = textos[0]
    ordem = ["Nota fiscal 123 (recusada)", "Recusa nº 1 da nota fiscal", "Nota fiscal 124 (recusada)", "Recusa nº 2 da nota fiscal", "Nota fiscal 125 (aprovada)",
             "Retenção de tributos (aprovação da nota fiscal)"]
    posicoes = [indice.index(t) for t in ordem]
    assert posicoes == sorted(posicoes)
    # A Folha de autenticação vem antes do resumo executivo, que é o último documento
    fim = " ".join(textos[-5:])
    assert "Folha de autenticação" in fim and fim.index("Folha de autenticação") < fim.index("Resumo executivo")
    assert "Trilha da nota fiscal" in fim and "Nota fiscal aprovada" in fim and "ISS retido incorreto" in fim


def test_recusa_so_com_a_retencao_aberta(cliente, admin, cenario):
    contrato, base, gestora = cenario
    fin = cabecalho(cliente, "financeiro1")
    # Antes da nota fiscal e depois da retenção conferida: não há o que recusar
    assert cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=fin).status_code == 400
    juntar_nf(cliente, base, gestora, "2105.00", "123")
    assert cliente.get(base, headers=fin).json()["pode_recusar"] is True
    conferir_retencao(cliente, base, fin, {"ir": "31.58"})
    r = cliente.post(f"{base}/retencao/recusar", json={"justificativa": JUSTIFICATIVA}, headers=fin)
    assert r.status_code == 400 and "retenção" in r.json()["detalhe"]
