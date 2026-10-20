# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o diário de bordo do contrato, as glosas na medição e os e-mails à equipe e ao preposto.
"""Diário de bordo: registro de ocorrências (com e sem glosa), permissões, glosas pelo período da
competência, medição limitada ao saldo líquido e os e-mails da ocorrência e da medição concluída.

O envio usa o servidor SMTP simulado de `tests/test_smtp.py` (sem rede).
"""

import smtplib
from datetime import date, datetime

import pytest

from app.services.calendario_util import somar_uteis
from app.services.documentos.pdf import FUSO_SAO_PAULO
from tests.apoio_contratos import corpo_conclusao, criar_contrato, gerar_cpf, restringir_contratos
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


def _ocorrencia(cliente, contrato, h, arquivos=None, **extras):
    """Registra a ocorrência (multipart: `dados` em JSON e, se houver, `arquivos`)."""
    import json
    corpo = {"data_ocorrencia": "2026-01-10", "descricao": "Posto descoberto das 8h às 12h.", "possui_glosa": False, "glosas": [], "enviar_email": True, **extras}
    return cliente.post(_url(contrato, "/diario"), data={"dados": json.dumps(corpo)}, files=[("arquivos", a) for a in (arquivos or [])], headers=h)


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


def test_ocorrencia_em_rich_text_e_sanitizada_e_vira_texto_nos_pdfs(cliente, admin, cenario):
    """O relato vem do editor rico: scripts saem, a formatação fica e o PDF do diário e o e-mail usam o texto puro."""
    from pypdf import PdfReader
    from io import BytesIO

    contrato, gestora, _ = cenario
    html = '<p>Posto <strong>descoberto</strong> das 8h às 12h.</p><ul><li>Sem reposição</li></ul><script>alert(1)</script>'
    r = _ocorrencia(cliente, contrato, gestora, descricao=html)
    assert r.status_code == 201, r.text
    salva = r.json()["descricao"]
    assert "<strong>descoberto</strong>" in salva and "<ul>" in salva and "script" not in salva
    # Editor vazio (só <p></p>) é recusado como relato em branco
    assert _ocorrencia(cliente, contrato, gestora, descricao="<p></p>").status_code == 422
    pdf = cliente.get(_url(contrato, "/diario/pdf"), params={"inicio": "2026-01-01", "fim": "2026-01-31"}, headers=gestora).content
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "descoberto" in texto and "<strong>" not in texto and "<ul>" not in texto


def test_pdf_do_diario_tem_uma_pagina_por_dia_com_ocorrencia(cliente, admin, cenario):
    """Diário de verdade: um dia = uma página com todas as ocorrências dele; dias sem ocorrência não geram página; texto enorme não quebra."""
    from io import BytesIO

    from pypdf import PdfReader

    contrato, gestora, _ = cenario
    _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-01-10", descricao="Primeira do dia dez.")
    _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-01-10", descricao="Segunda do dia dez.")
    _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-01-20", descricao="Única do dia vinte.")
    gigante = _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-01-25", descricao="palavra longa de relato. " * 700)
    assert gigante.status_code == 201, gigante.text
    pdf = cliente.get(_url(contrato, "/diario/pdf"), params={"inicio": "2026-01-01", "fim": "2026-01-31"}, headers=gestora).content
    paginas = [p.extract_text() for p in PdfReader(BytesIO(pdf)).pages]
    assert "Sábado, 10 de janeiro de 2026" in paginas[0] and "Primeira do dia dez" in paginas[0] and "Segunda do dia dez" in paginas[0]
    assert "Terça-feira, 20 de janeiro de 2026" in paginas[1] and "Única do dia vinte" in paginas[1] and "Primeira" not in paginas[1]
    assert not any("Dia 11" in p or "11 de janeiro" in p for p in paginas)
    assert "Domingo, 25 de janeiro de 2026" in paginas[2] and len(paginas) > 3


def test_pdf_do_diario_junta_os_anexos_no_fim_numa_lista(cliente, admin, cenario):
    """Anexos das ocorrências: lista de anexos no fim, e cada arquivo vem com folha de rosto (PDF como está, imagem como página, TXT só na folha)."""
    import base64
    from io import BytesIO

    from pypdf import PdfReader

    from tests.apoio_contratos import PDF

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    contrato, gestora, _ = cenario
    arquivos = [("foto-posto.png", png, "image/png"), ("laudo.pdf", PDF, "application/pdf"), ("nota.txt", b"texto simples", "text/plain")]
    r = _ocorrencia(cliente, contrato, gestora, arquivos=arquivos, data_ocorrencia="2026-01-12")
    assert r.status_code == 201, r.text
    pdf = cliente.get(_url(contrato, "/diario/pdf"), params={"inicio": "2026-01-01", "fim": "2026-01-31"}, headers=gestora).content
    paginas = [p.extract_text() for p in PdfReader(BytesIO(pdf)).pages]
    lista = next(i for i, t in enumerate(paginas) if "Lista de anexos (3)" in t)
    assert all(nome in paginas[lista] for nome in ("foto-posto.png", "laudo.pdf", "nota.txt"))
    # Diário (1 dia + lista) e depois: folha de rosto + imagem, folha de rosto + PDF, folha de rosto do TXT
    assert len(paginas) == lista + 1 + (2 + 2 + 1)
    assert "Anexo 1 de 3" in paginas[lista + 1] and "Anexo 3 de 3" in paginas[-1] and "não é exibido dentro do PDF" in paginas[-1]
    assert "Página 1 de" in paginas[0]


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
    r = cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(f"{base}", notas), headers=gestora)
    assert r.status_code == 400 and "saldo líquido" in r.json()["detalhe"]


def test_competencia_afetada_pode_ser_diferente_da_data_da_ocorrencia(cliente, admin, cenario):
    """Ocorrência de 03/02 que afeta a competência 01/2026: a glosa vale em janeiro (não em fevereiro) e o diário mostra a competência afetada."""
    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    limpeza = _itens(contrato)["Limpeza"]
    diario = cliente.get(_url(contrato, "/diario"), headers=gestora).json()
    assert {"identificador": "2026-01", "rotulo": "01/2026"}.items() <= next(c for c in diario["competencias"] if c["identificador"] == "2026-01").items()
    # Competência inexistente é recusada
    assert _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-02-03", competencia_afetada="2031-05").status_code == 400
    r = _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-02-03", competencia_afetada="2026-01", possui_glosa=True, glosas=[{"item_id": limpeza, "quantidade": "0.5"}])
    assert r.status_code == 201, r.text
    assert (r.json()["competencia_afetada"], r.json()["competencia_rotulo"]) == ("2026-01", "01/2026")
    # Sem informar, vale a competência da data
    assert _ocorrencia(cliente, contrato, gestora, data_ocorrencia="2026-02-04").json()["competencia_afetada"] == "2026-02"
    janeiro = _competencia(cliente, contrato, gestora, "2026-01")
    fevereiro = _competencia(cliente, contrato, gestora, "2026-02")
    assert [g["quantidade"] for g in janeiro["glosas_periodo"]] == ["0.5000"] and fevereiro["glosas_periodo"] == []
    linha = next(i for i in janeiro["itens"] if i["descricao"] == "Limpeza")
    assert linha["glosas"] == "0.5000"


def test_medicao_concluida_envia_so_a_medicao_com_ciencia_e_prazo_de_contestacao(cliente, admin, cenario):
    """Sem avaliação, ao concluir a medição sai o e-mail único: memória, documento executivo (valor a faturar) e diário, abrindo o prazo de contestação em dias úteis."""
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
    r = cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(f"{base}", notas), headers=gestora)
    assert r.status_code == 200, r.text

    detalhe = cliente.get(base, headers=gestora).json()
    assert detalhe["email_medicao"]["ok"] is True and "paulo@acme.com" in detalhe["email_medicao"]["destinatarios"]
    mensagem, _, _, _ = SmtpSimulado.enviadas[0]
    assert "medição 01/2026 concluída: emitir nota fiscal" in mensagem["Subject"]
    assert mensagem["Reply-To"] == "gestora@sp.gov.br, fiscal@sp.gov.br"
    texto = mensagem.get_body(("plain",)).get_content()
    assert "dia(s) útil(eis)" in texto and "Valor líquido a faturar" in texto and "ACME" in texto
    assert "para ciência" in texto and "Estando de acordo com a medição" in texto and "contestação" in texto and "assine" not in texto
    html = mensagem.get_body(("html",)).get_content()
    assert "PDF e arquivo XML" in texto and "PDF e arquivo XML" in html
    anexos = {a.get_filename(): a.get_content() for a in mensagem.iter_attachments()}
    assert set(anexos) == {"memoria_medicao_001_2026_2026-01.pdf"}  # só a medição: sem diário nem documento executivo no e-mail
    assert all(conteudo[:5] == b"%PDF-" for conteudo in anexos.values())

    # O envio abriu o prazo de contestação: 3 dias úteis, aberto, com o documento executivo disponível
    contestacao = detalhe["contestacao"]
    assert contestacao["prazo_dias"] == 3 and contestacao["situacao"] == "aberto" and contestacao["documento_executivo_versao"] == 1
    assert contestacao["documento_executivo"]["nome"].startswith("documento-executivo-") and detalhe["pode_reemitir_medicao"] is True
    baixado = cliente.get(f"{base}/arquivos/{contestacao['documento_executivo']['anexo_id']}", headers=gestora)
    assert baixado.status_code == 200 and baixado.content[:5] == b"%PDF-"
    inicio = datetime.fromisoformat(contestacao["inicio_em"]).astimezone(FUSO_SAO_PAULO).date()
    limite = datetime.fromisoformat(contestacao["limite_em"]).astimezone(FUSO_SAO_PAULO)
    assert limite.date() == somar_uteis(inicio, 3, set())  # o teste não tem feriados cadastrados
    assert limite.weekday() < 5  # o prazo termina sempre num dia útil

    # Não há mais reenvio livre; a reemissão (contestação aceita) gera nova versão e reinicia o prazo
    assert cliente.post(f"{base}/reenviar-email-medicao", headers=gestora).status_code in (404, 405)
    r = cliente.post(f"{base}/medicao/reemitir", json={"prazo_contestacao_dias": 5}, headers=gestora)
    assert r.status_code == 200, r.text
    assert len(SmtpSimulado.enviadas) == 2 and "reemissão, versão 2" in SmtpSimulado.enviadas[1][0]["Subject"]
    nova = r.json()["contestacao"]
    assert nova["prazo_dias"] == 5 and nova["documento_executivo_versao"] == 2 and nova["situacao"] == "aberto"


def test_escolha_dos_prepostos_que_recebem_o_email_da_medicao(cliente, admin, cenario):
    """O seletor lista só prepostos ativos com e-mail; o fiscal escolhe um ou mais, e a reemissão pode trocar a escolha."""
    contrato, gestora, fiscal = cenario
    r = cliente.post(f"/api/contratos/empresas/{contrato['empresa']['id']}/prepostos", json={"cpf": gerar_cpf("777888999"), "nome": "Bruno Preposto", "email": "bruno@acme.com"}, headers=admin)
    assert r.status_code == 201, r.text
    lista = cliente.get(_url(contrato, "/prepostos"), headers=gestora).json()
    assert sorted(p["nome"] for p in lista) == ["Bruno Preposto", "Paulo Preposto"]  # Ana Antiga está inativa
    ids = {p["nome"]: p["id"] for p in lista}
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    SmtpSimulado.enviadas.clear()
    competencia = _competencia(cliente, contrato, gestora)
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["saldo_liquido"]} for i in competencia["itens"]]
    cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    corpo = {**corpo_conclusao(f"{base}", notas), "prepostos_ids": [ids["Bruno Preposto"]]}
    assert cliente.post(f"{base}/medicao/concluir", json=corpo, headers=gestora).status_code == 200
    destinatarios = cliente.get(base, headers=gestora).json()["email_medicao"]["destinatarios"]
    assert "bruno@acme.com" in destinatarios and "paulo@acme.com" not in destinatarios and "gestora@sp.gov.br" in destinatarios
    # Reemissão sem escolha nova: vale a feita ao concluir; com escolha nova (dois prepostos), ela passa a valer
    assert cliente.post(f"{base}/medicao/reemitir", json={}, headers=gestora).status_code == 200
    assert "paulo@acme.com" not in cliente.get(base, headers=gestora).json()["email_medicao"]["destinatarios"]
    r = cliente.post(f"{base}/medicao/reemitir", json={"prepostos_ids": list(ids.values())}, headers=gestora)
    assert r.status_code == 200 and {"bruno@acme.com", "paulo@acme.com"} <= set(r.json()["email_medicao"]["destinatarios"])


def test_documento_marcado_para_enviar_vai_no_email_da_medicao_com_a_observacao(cliente, admin, cenario):
    """"Pedir para enviar" pode ser ligado no checklist ativo e, ao concluir a medição, o mesmo e-mail pede os documentos marcados."""
    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)  # checklist ativo: "Folha de pagamento" e "FGTS"
    ativo = next(c for c in cliente.get(_url(contrato, "/checklists"), headers=gestora).json() if c["ativo"])
    fgts = next(i for i in ativo["itens"] if i["nome"] == "FGTS")
    assert fgts["pedir_envio"] is False
    r = cliente.put(_url(contrato, f"/checklists/{ativo['id']}/itens/{fgts['id']}/pedir-envio"), json={"pedir_envio": True}, headers=gestora)
    assert r.status_code == 200, r.text
    marcado = next(c for c in r.json() if c["id"] == ativo["id"])
    assert [i["pedir_envio"] for i in marcado["itens"] if i["nome"] == "FGTS"] == [True]
    # Documento que não pertence ao checklist não existe (404)
    zero = "00000000-0000-0000-0000-000000000000"
    assert cliente.put(_url(contrato, f"/checklists/{ativo['id']}/itens/{zero}/pedir-envio"), json={"pedir_envio": True}, headers=gestora).status_code == 404

    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    SmtpSimulado.enviadas.clear()
    competencia = _competencia(cliente, contrato, gestora)
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["saldo_liquido"]} for i in competencia["itens"]]
    cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    r = cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(f"{base}", notas), headers=gestora)
    assert r.status_code == 200, r.text
    corpo = SmtpSimulado.enviadas[0][0].get_body(("html",)).get_content()
    assert "Solicitamos também o envio dos documentos abaixo" in corpo and "FGTS" in corpo and "Folha de pagamento" not in corpo


# --- Anexos, impacto na avaliação e e-mail da avaliação ----------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def test_anexos_e_impacto_na_avaliacao_e_email_do_relatorio(cliente, admin, cenario):
    """Anexos no registro e no e-mail; ocorrência que impacta item da avaliação exige justificativa da nota máxima;
    o PDF da avaliação vai aos prepostos (cópia para a equipe) ao ser gerado, e pode ser reenviado."""
    import io
    from pypdf import PdfReader
    from tests.test_contratos_execucao import FORMULARIO, PDF

    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)
    # Sem formulário ativo, não há itens para marcar o impacto
    assert _ocorrencia(cliente, contrato, gestora, impacta_avaliacao=True, itens_avaliacao=["x"]).status_code == 400
    formularios = cliente.post(_url(contrato, "/formularios"), json=FORMULARIO, headers=gestora).json()
    cliente.post(_url(contrato, f"/formularios/{formularios[0]['id']}/ativar"), headers=gestora)
    opcoes = {i["nome"]: i["id"] for i in cliente.get(_url(contrato, "/diario"), headers=gestora).json()["itens_avaliacao"]}
    assert set(opcoes) == {"Pontualidade", "Limpeza"}
    # Impacto sem item → 422; arquivo de formato não aceito → 400
    assert _ocorrencia(cliente, contrato, gestora, impacta_avaliacao=True).status_code == 422
    ruim = _ocorrencia(cliente, contrato, gestora, arquivos=[("pagina.html", b"<script>", "text/html")])
    assert ruim.status_code == 400
    SmtpSimulado.enviadas.clear()
    r = _ocorrencia(cliente, contrato, gestora, impacta_avaliacao=True, itens_avaliacao=[opcoes["Limpeza"]],
                    arquivos=[("foto.png", PNG, "image/png"), ("relatorio.pdf", PDF, "application/pdf")])
    assert r.status_code == 201, r.text
    ocorrencia = r.json()
    assert [a["nome"] for a in ocorrencia["anexos"]] == ["foto.png", "relatorio.pdf"]
    assert ocorrencia["impacta_avaliacao"] is True and ocorrencia["itens_avaliacao"][0]["item_nome"] == "Limpeza"
    anexo = ocorrencia["anexos"][0]
    baixado = cliente.get(_url(contrato, f"/diario/{ocorrencia['id']}/anexos/{anexo['id']}"), headers=fiscal)
    assert baixado.status_code == 200 and baixado.content == PNG
    mensagem, _, _, _ = SmtpSimulado.enviadas[0]
    assert {a.get_filename() for a in mensagem.iter_attachments()} == {"foto.png", "relatorio.pdf"}
    assert "Impacta a avaliação da qualidade: Sim — Limpeza" in mensagem.get_body(("plain",)).get_content()

    # Competência 01/2026: medição e avaliação
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=gestora).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["saldo_liquido"]} for i in competencia["itens"]], "notas_empenho_ids": notas}
    assert cliente.put(f"{base}/medicao", json=medicao, headers=gestora).status_code == 200
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    # Com avaliação de qualidade, os prepostos e o prazo ficam para o fim da avaliação: a medição conclui sem eles
    assert cliente.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": notas}, headers=gestora).status_code == 200
    detalhe = cliente.get(base, headers=gestora).json()
    itens = {i["nome"]: i["id"] for g in detalhe["avaliacao"]["definicao"]["grupos"] for i in g["itens"]}
    assert [o["itens"] for o in detalhe["avaliacao"]["ocorrencias"]] == [[itens["Limpeza"]]]
    toda_maxima = {"respostas": [{"item_id": itens["Pontualidade"], "nota": "10"}, {"item_id": itens["Limpeza"], "nota": "10"}]}
    r = cliente.put(f"{base}/avaliacao/inicial", json=toda_maxima, headers=fiscal)
    assert r.status_code == 400 and "justifique a nota máxima" in r.json()["detalhe"]
    toda_maxima["respostas"][1]["justificativa"] = "Ocorrência pontual, resolvida no mesmo dia."
    assert cliente.put(f"{base}/avaliacao/inicial", json=toda_maxima, headers=fiscal).status_code == 200

    # Ao finalizar a avaliação sai o e-mail único da medição. Antes disso nada foi enviado e o envio consta como pendente
    cliente.post(f"{base}/avaliacao/ciencia", headers=gestora)
    detalhe = cliente.get(base, headers=gestora).json()
    assert detalhe["email_medicao_pendente"] is True and detalhe["email_medicao"]["enviado_em"] is None and detalhe["contestacao"] is None
    SmtpSimulado.enviadas.clear()
    # A via assinada só vale depois do envio da Medição e da Avaliação
    assert cliente.post(f"{base}/avaliacao/assinada", files={"arquivo": ("assinada.pdf", PDF)}, headers=gestora).status_code == 400
    # Sem os prepostos e o prazo, o envio não sai (e valores fora da faixa são recusados)
    assert cliente.post(f"{base}/avaliacao/enviar", json={}, headers=gestora).status_code == 400
    assert cliente.post(f"{base}/avaliacao/enviar", json={"prepostos_ids": [], "prazo_contestacao_dias": 3}, headers=gestora).status_code == 422
    assert SmtpSimulado.enviadas == []
    preposto = cliente.get(_url(contrato, "/prepostos"), headers=gestora).json()[0]["id"]
    r = cliente.post(f"{base}/avaliacao/enviar", json={"prepostos_ids": [preposto], "prazo_contestacao_dias": 3}, headers=gestora)
    assert r.status_code == 200, r.text
    detalhe = cliente.get(base, headers=gestora).json()
    assert detalhe["avaliacao"]["pdf_gerado"] is not None
    assert detalhe["email_medicao"]["ok"] is True and "paulo@acme.com" in detalhe["email_medicao"]["destinatarios"] and detalhe["email_medicao_pendente"] is False
    assert detalhe["contestacao"]["situacao"] == "aberto" and detalhe["contestacao"]["prazo_dias"] == 3
    mensagem = SmtpSimulado.enviadas[0][0]
    anexos = {a.get_filename(): a.get_content() for a in mensagem.iter_attachments()}
    assert set(anexos) == {"avaliacao_001_2026_2026-01.pdf", "memoria_medicao_001_2026_2026-01.pdf"}  # um e-mail só, com os dois anexos
    assert "assine o relatório de avaliação" in mensagem.get_body(("plain",)).get_content() and "assinar a avaliação" in mensagem["Subject"]
    texto_pdf = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(anexos["avaliacao_001_2026_2026-01.pdf"])).pages)
    assert "Ocorrências do diário de bordo consideradas" in texto_pdf
    # A contratada devolve o relatório assinado: conclui a avaliação, sem novo e-mail
    SmtpSimulado.enviadas.clear()
    r = cliente.post(f"{base}/avaliacao/assinada", files={"arquivo": ("assinada.pdf", PDF)}, headers=gestora)
    assert r.status_code == 200, r.text
    assert SmtpSimulado.enviadas == []
    detalhe = cliente.get(base, headers=gestora).json()

    # Juntar a nota fiscal encerra o prazo de contestação
    from tests.apoio_contratos import juntar_nf

    assert juntar_nf(cliente, base, gestora, detalhe["valor_autorizado"]).status_code in (200, 201)
    encerrada = cliente.get(base, headers=gestora).json()
    assert encerrada["contestacao"]["situacao"] == "encerrado" and encerrada["contestacao"]["encerrada_em"] is not None
    assert encerrada["pode_reemitir_medicao"] is False
    assert cliente.post(f"{base}/medicao/reemitir", json={}, headers=gestora).status_code == 400


def test_conclusao_da_medicao_exige_ao_menos_um_preposto_e_o_prazo(cliente, admin, cenario):
    """O e-mail à contratada é obrigatório: ao menos um preposto ativo com e-mail da empresa e o prazo (1 a 60 dias úteis)."""
    contrato, gestora, fiscal = cenario
    _preparar_execucao(cliente, contrato, gestora)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=gestora)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=gestora).json()]
    competencia = _competencia(cliente, contrato, gestora)
    base = _url(contrato, f"/competencias/{competencia['id']}")
    itens = [{"id": i["id"], "quantidade_medida": i["saldo_liquido"]} for i in competencia["itens"]]
    cliente.put(f"{base}/medicao", json={"itens": itens, "notas_empenho_ids": notas}, headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=gestora)
    cliente.post(f"{base}/medicao/ciencia", headers=fiscal)
    ok = corpo_conclusao(f"{base}", notas)
    sem_prepostos = {k: v for k, v in ok.items() if k != "prepostos_ids"}
    sem_prazo = {k: v for k, v in ok.items() if k != "prazo_contestacao_dias"}
    # Sem avaliação no contrato, faltar um dos dois barra a conclusão (400); valores fora da faixa nem chegam à regra (422)
    for corpo in (sem_prepostos, sem_prazo):
        r = cliente.post(f"{base}/medicao/concluir", json=corpo, headers=gestora)
        assert r.status_code == 400, r.text
    for corpo in ({**ok, "prepostos_ids": []}, {**ok, "prazo_contestacao_dias": 0}, {**ok, "prazo_contestacao_dias": 61}):
        assert cliente.post(f"{base}/medicao/concluir", json=corpo, headers=gestora).status_code == 422
    # Preposto inativo (Ana Antiga) não vale
    todos = cliente.get(f"/api/contratos/empresas/{contrato['empresa']['id']}", headers=gestora).json()["prepostos"]
    inativo = next(p["id"] for p in todos if not p["ativo"])
    r = cliente.post(f"{base}/medicao/concluir", json={**ok, "prepostos_ids": [inativo]}, headers=gestora)
    assert r.status_code == 400 and "ao menos um preposto ativo" in r.json()["detalhe"]
    assert cliente.post(f"{base}/medicao/concluir", json=ok, headers=gestora).status_code == 200
