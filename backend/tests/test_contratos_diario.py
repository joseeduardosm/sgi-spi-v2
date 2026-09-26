# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o diário de bordo do contrato, as glosas na medição e os e-mails à equipe e ao preposto.
"""Diário de bordo: registro de ocorrências (com e sem glosa), permissões, glosas pelo período da
competência, medição limitada ao saldo líquido e os e-mails da ocorrência e da medição concluída.

O envio usa o servidor SMTP simulado de `tests/test_smtp.py` (sem rede).
"""

import smtplib
from datetime import date

import pytest

from tests.apoio_contratos import criar_contrato, gerar_cpf, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import _preparar_execucao, _url
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor

HOJE = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    """Data fixa (15/03/2026) e SMTP simulado."""
    for modulo in ("servico_contratos", "servico_competencias", "servico_diario"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: HOJE)
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com gestora e fiscal (e-mails próprios), um preposto ativo e um inativo, e SMTP ativo."""
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva", email="gestora@sp.gov.br")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza", email="fiscal@sp.gov.br")
    criar_usuario("outro", email="outro@sp.gov.br")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    empresa = contrato["empresa"]["id"]
    for base, nome, email, ativo in (("111222333", "Paulo Preposto", "paulo@acme.com", True), ("444555666", "Ana Antiga", "ana@acme.com", False)):
        r = cliente.post(f"/api/contratos/empresas/{empresa}/prepostos", json={"cpf": gerar_cpf(base), "nome": nome, "email": email, "ativo": ativo},
                         headers=admin)
        assert r.status_code == 201, r.text
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    return contrato, cabecalho(cliente, "gestora"), cabecalho(cliente, "fiscal")


def _itens(contrato):
    return {i["descricao"]: i["id"] for i in contrato["itens"]}


def _ocorrencia(cliente, contrato, h, **extras):
    corpo = {"data_ocorrencia": "2026-01-10", "descricao": "Posto descoberto das 8h às 12h.", "possui_glosa": False, "glosas": [], **extras}
    return cliente.post(_url(contrato, "/diario"), json=corpo, headers=h)


# --- Registro -------------------------------------------------------------------------------------

def test_registro_com_glosa_e_email_a_equipe_e_preposto(cliente, admin, cenario):
    """A ocorrência é registrada com a glosa e o e-mail vai à equipe + prepostos ativos, com resposta para a equipe."""
    contrato, gestora, _ = cenario
    itens = _itens(contrato)
    r = _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=[{"item_id": itens["Limpeza"], "quantidade": "0.5"}])
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["registrada_por_nome"] == "Gestora Silva" and corpo["registrada_por_papel"] == "gestor"
    assert corpo["glosas"] == [{"item_id": itens["Limpeza"], "descricao_item": "Limpeza", "quantidade": "0.5000"}]

    # O e-mail sai em segundo plano: depois da resposta, o resultado já está gravado
    diario = cliente.get(_url(contrato, "/diario"), headers=gestora).json()
    email = diario["ocorrencias"][0]["email"]
    assert email["ok"] is True and sorted(email["destinatarios"]) == ["fiscal@sp.gov.br", "gestora@sp.gov.br", "paulo@acme.com"]
    mensagem, _, destinatarios, _ = SmtpSimulado.enviadas[0]
    assert "[Diário de bordo] Contrato 001/2026" in mensagem["Subject"] and "ana@acme.com" not in destinatarios
    assert mensagem["Reply-To"] == "gestora@sp.gov.br, fiscal@sp.gov.br"
    texto = mensagem.get_body(("plain",)).get_content()
    assert "Haverá glosa: Sim" in texto and "Limpeza: 0,5" in texto and "Posto descoberto" in texto


def test_validacoes_do_registro(cliente, admin, cenario):
    """Glosa sem item, item repetido, data futura e item de outro contrato são recusados."""
    contrato, gestora, _ = cenario
    item = _itens(contrato)["Limpeza"]
    assert _ocorrencia(cliente, contrato, gestora, possui_glosa=True).status_code == 422
    repetido = [{"item_id": item, "quantidade": "1"}, {"item_id": item, "quantidade": "2"}]
    assert _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=repetido).status_code == 422
    assert _ocorrencia(cliente, contrato, gestora, possui_glosa=False, glosas=[{"item_id": item, "quantidade": "1"}]).status_code == 422
    assert _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=[{"item_id": item, "quantidade": "0"}]).status_code == 422
    r = _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-03-16")
    assert r.status_code == 400 and "futura" in r.json()["detalhe"]
    outro = criar_contrato(cliente, admin, numero="002/2026", empresa_id=contrato["empresa"]["id"])
    r = _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=[{"item_id": outro["itens"][0]["id"], "quantidade": "1"}])
    assert r.status_code == 400 and "não é deste contrato" in r.json()["detalhe"]


def test_so_quem_edita_o_contrato_registra(cliente, admin, cenario):
    """Usuário fora da equipe lê o diário, mas não registra (403)."""
    contrato, _, _ = cenario
    outro = cabecalho(cliente, "outro")
    assert _ocorrencia(cliente, contrato, outro).status_code == 403
    diario = cliente.get(_url(contrato, "/diario"), headers=admin).json()
    assert diario["pode_registrar"] is True and {i["descricao"] for i in diario["itens"]} == {"Limpeza", "Material"}


def test_sem_servidor_smtp_ativo_grava_o_erro_e_permite_reenviar(cliente, admin, cenario):
    """Sem servidor ativo, a ocorrência é salva e o erro fica registrado; o reenvio funciona depois de ativar."""
    contrato, gestora, _ = cenario
    servidor = cliente.get("/api/smtp/servidores", headers=admin).json()[0]
    cliente.put(f"/api/smtp/servidores/{servidor['id']}", json=dados_servidor(ativo=False, senha=None), headers=admin)
    ocorrencia = _ocorrencia(cliente, contrato, gestora).json()
    email = cliente.get(_url(contrato, "/diario"), headers=gestora).json()["ocorrencias"][0]["email"]
    assert email["ok"] is False and "Nenhum servidor SMTP ativo" in email["erro"]
    cliente.put(f"/api/smtp/servidores/{servidor['id']}", json=dados_servidor(senha=None), headers=admin)
    r = cliente.post(_url(contrato, f"/diario/{ocorrencia['id']}/reenviar"), headers=gestora)
    assert r.status_code == 200 and r.json()["email"]["ok"] is True


def test_pdf_do_diario(cliente, admin, cenario):
    """O diário em PDF sai com o nome padronizado."""
    contrato, gestora, _ = cenario
    _ocorrencia(cliente, contrato, gestora)
    r = cliente.get(_url(contrato, "/diario/pdf"), params={"inicio": "2026-01-01", "fim": "2026-01-31"}, headers=gestora)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and "DIARIO_DE_BORDO_SPI_001_2026.pdf" in r.headers["content-disposition"]


# --- Medição ---------------------------------------------------------------------------------------

def _competencia(cliente, contrato, h, identificador="2026-01"):
    return cliente.get(_url(contrato, f"/competencias/identificador/{identificador}"), headers=h).json()


def test_glosas_do_periodo_limitam_a_medicao(cliente, admin, cenario):
    """Glosa com data no período reduz o saldo líquido; medir acima dele é recusado (ao salvar e ao concluir)."""
    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    limpeza = _itens(contrato)["Limpeza"]
    # Janeiro: glosa de 0,5; fevereiro (outra competência) não conta em janeiro
    _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=[{"item_id": limpeza, "quantidade": "0.5"}])
    _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-02-03", possui_glosa=True, glosas=[{"item_id": limpeza, "quantidade": "1"}])
    competencia = _competencia(cliente, contrato, gestora)
    linha = next(i for i in competencia["itens"] if i["descricao"] == "Limpeza")
    assert (linha["saldo"], linha["glosas"], linha["saldo_liquido"]) == ("2.0000", "0.5000", "1.5000")
    assert [g["quantidade"] for g in competencia["glosas_periodo"]] == ["0.5000"]

    base = _url(contrato, f"/competencias/{competencia['id']}")
    medir = lambda q: [{"id": i["id"], "quantidade_medida": q if i["descricao"] == "Limpeza" else i["quantidade_prevista"]} for i in competencia["itens"]]  # noqa: E731
    r = cliente.put(f"{base}/medicao", json={"itens": medir("2"), "notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 400 and "saldo líquido (1.5000 = saldo 2.0000 − glosas 0.5000)" in r.json()["detalhe"]
    assert cliente.put(f"{base}/medicao", json={"itens": medir("1.5"), "notas_empenho_ids": notas}, headers=gestora).status_code == 200

    # Uma glosa registrada depois de salvar a medição impede a conclusão
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-01-20", possui_glosa=True, glosas=[{"item_id": limpeza, "quantidade": "0.25"}])
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 400 and "saldo líquido" in r.json()["detalhe"]


def test_medicao_concluida_envia_memoria_e_diario_pedindo_nf_em_48h(cliente, admin, cenario):
    """Ao concluir a medição, o e-mail leva a memória e o diário do período em PDF e pede a NF em até 48 h."""
    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    _ocorrencia(cliente, contrato, gestora, possui_glosa=True, glosas=[{"item_id": _itens(contrato)["Limpeza"], "quantidade": "0.5"}])
    SmtpSimulado.enviadas.clear()
    competencia = _competencia(cliente, contrato, gestora)
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["saldo_liquido"]} for i in competencia["itens"]]
    assert cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora).status_code == 200
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    r = cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora)
    assert r.status_code == 200, r.text

    detalhe = cliente.get(base, headers=gestora).json()
    assert detalhe["email_medicao"]["ok"] is True and "paulo@acme.com" in detalhe["email_medicao"]["destinatarios"]
    mensagem, _, _, _ = SmtpSimulado.enviadas[0]
    assert "medição 01/2026 concluída: emitir nota fiscal" in mensagem["Subject"]
    assert mensagem["Reply-To"] == "gestora@sp.gov.br, fiscal@sp.gov.br"
    texto = mensagem.get_body(("plain",)).get_content()
    assert "em até 48 horas" in texto and "ACME" in texto
    anexos = {a.get_filename(): a.get_content() for a in mensagem.iter_attachments()}
    assert set(anexos) == {"memoria_medicao_001_2026_2026-01.pdf", "diario_de_bordo_001_2026_2026-01.pdf"}
    assert all(conteudo[:5] == b"%PDF-" for conteudo in anexos.values())

    # Reenvio manual
    r = cliente.post(f"{base}/reenviar-email-medicao", headers=gestora)
    assert r.status_code == 200 and len(SmtpSimulado.enviadas) == 2
