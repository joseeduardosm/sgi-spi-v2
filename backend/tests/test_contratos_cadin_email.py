# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o e-mail de pendência no CADIN (máscara em Modelos), o envio aos prepostos e o memorial no consolidado.
"""CADIN: máscara `email_cadin`, e-mail Para prepostos / Cc equipe, reenvio e o memorial do consolidado."""

import re
import smtplib
from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.services.contratos import email_cadin_mascara, email_ob_mascara
from tests.apoio_contratos import corpo_conclusao, definir_parametros, PDF, conferir_retencao, criar_contrato, gerar_cpf, juntar_nf, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_contratos_execucao import HOJE, _preparar_execucao, _url
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    for modulo in ("servico_contratos", "servico_competencias", "servico_diario"):
        monkeypatch.setattr(f"app.services.contratos.{modulo}.hoje", lambda: HOJE)
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com gestora e fiscal (com e-mail), um preposto ativo e um inativo, SMTP ativo e a execução até a etapa do CADIN."""
    gestora = criar_usuario("gestora", nome_completo="Gestora Silva", email="gestora@sp.gov.br")
    fiscal = criar_usuario("fiscal", nome_completo="Fiscal Souza", email="fiscal@sp.gov.br")
    restringir_contratos(cliente, admin, {gestora: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestora, "fiscal_tecnico": fiscal})
    empresa = contrato["empresa"]["id"]
    for base, nome, email, ativo in (("111222333", "Paulo Preposto", "paulo@acme.com", True), ("444555666", "Ana Antiga", "ana@acme.com", False)):
        assert cliente.post(f"/api/contratos/empresas/{empresa}/prepostos", json={"cpf": gerar_cpf(base), "nome": nome, "email": email, "ativo": ativo}, headers=admin).status_code == 201
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    # O banco de teste nasce sem a máscara que a migração semeia: grava a mesma máscara padrão
    padrao = {"tipo": "email_cadin", "nome": "E-mail de pendência no CADIN", "assunto": email_cadin_mascara.ASSUNTO_PADRAO, "html": email_cadin_mascara.HTML_PADRAO, "ativo": True}
    assert cliente.post("/api/contratos/modelos", json=padrao, headers=admin).status_code == 201
    h = cabecalho(cliente, "gestora")
    _preparar_execucao(cliente, contrato, h)
    cliente.post(_url(contrato, "/execucao/gerar"), headers=h)
    notas = [n["id"] for n in cliente.get(_url(contrato, "/notas-empenho"), headers=h).json()]
    competencia = cliente.get(_url(contrato, "/competencias/identificador/2026-01"), headers=h).json()
    base = _url(contrato, f"/competencias/{competencia['id']}")
    medicao = {"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in competencia["itens"]], "notas_empenho_ids": notas}
    cliente.put(f"{base}/medicao", json=medicao, headers=h)
    cliente.post(f"{base}/medicao/ciencia", headers=h)
    cliente.post(f"{base}/medicao/ciencia", headers=cabecalho(cliente, "fiscal"))
    cliente.post(f"{base}/medicao/concluir", json=corpo_conclusao(f"{base}", notas), headers=h)
    assert juntar_nf(cliente, base, h, "2105.00").status_code == 200
    assert conferir_retencao(cliente, base, h).status_code == 200
    for documento in cliente.get(base, headers=h).json()["documentos"]:
        r = cliente.post(f"{base}/checklist/{documento['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=h)
    assert r.json()["etapa_atual"] == "cadin"
    SmtpSimulado.enviadas.clear()
    return contrato, h, base


def _cadin(cliente, base, h, pendencia: bool, texto="Débito de ICMS em aberto"):
    """Registra a consulta; o e-mail sai em segundo plano (já terminou quando a chamada volta), então devolve o detalhe **atualizado**."""
    dados = {"possui_pendencia": "true" if pendencia else "false", **({"pendencia": texto} if pendencia else {})}
    r = cliente.post(f"{base}/cadin", data=dados, files={"certidao": ("c.pdf", PDF)}, headers=h)
    assert r.status_code == 200, r.text
    return cliente.get(base, headers=h)


def test_pendencia_envia_a_mascara_aos_prepostos_com_a_equipe_em_copia(cliente, admin, cenario):
    contrato, h, base = cenario
    r = _cadin(cliente, base, h, True)
    assert r.json()["etapa_atual"] == "cadin"
    assert len(SmtpSimulado.enviadas) == 1
    mensagem = SmtpSimulado.enviadas[0][0]
    # Para: só o preposto ativo; Cc: a equipe do contrato
    assert mensagem["To"] == "paulo@acme.com" and "ana@acme.com" not in str(mensagem["To"]) + str(mensagem["Cc"])
    assert set(a.strip() for a in mensagem["Cc"].split(",")) == {"gestora@sp.gov.br", "fiscal@sp.gov.br"}
    # A máscara padrão foi preenchida com os dados do contrato e da consulta
    assert mensagem["Subject"] == f"Contrato {contrato['numero']} - Janeiro/2026 - Pendência no CADIN"
    html = mensagem.get_body(("html",)).get_content()
    assert "Débito de ICMS em aberto" in html and contrato["empresa"]["razao_social"] in html and "Gestora Silva" in html and "#" not in re.sub(r"&#\d+;|#[0-9a-fA-F]{3,6}", "", html)
    # O resultado fica na consulta, com a cópia do e-mail em PDF para o consolidado
    consulta = r.json()["consultas_cadin"][0]
    assert consulta["email_ok"] is True and consulta["email_destinatarios"][0] == "paulo@acme.com" and consulta["email"]["nome"].endswith(".pdf")
    # Consulta sem pendência não envia e-mail
    SmtpSimulado.enviadas.clear()
    assert _cadin(cliente, base, h, False).json()["etapa_atual"] == "consolidado" and SmtpSimulado.enviadas == []


def test_pendencia_sem_preposto_ou_sem_mascara_grava_a_falha_e_reenvia(cliente, admin, cenario):
    contrato, h, base = cenario
    empresa = contrato["empresa"]["id"]
    prepostos = cliente.get(f"/api/contratos/empresas/{empresa}", headers=admin).json()["prepostos"]
    paulo = next(p for p in prepostos if p["email"] == "paulo@acme.com")
    cliente.put(f"/api/contratos/empresas/{empresa}/prepostos/{paulo['id']}", json={**{k: paulo[k] for k in ("cpf", "nome", "email")}, "ativo": False}, headers=admin)
    consulta = _cadin(cliente, base, h, True).json()["consultas_cadin"][0]
    assert consulta["email_ok"] is False and "preposto" in consulta["email_erro"] and SmtpSimulado.enviadas == []
    # Reativa o preposto e reenvia
    cliente.put(f"/api/contratos/empresas/{empresa}/prepostos/{paulo['id']}", json={**{k: paulo[k] for k in ("cpf", "nome", "email")}, "ativo": True}, headers=admin)
    r = cliente.post(f"{base}/cadin/{consulta['id']}/reenviar-email", headers=h)
    assert r.status_code == 200 and len(SmtpSimulado.enviadas) == 1
    assert cliente.get(base, headers=h).json()["consultas_cadin"][0]["email_ok"] is True
    # Consulta sem pendência não tem e-mail para reenviar; consulta inexistente é 404
    sem = _cadin(cliente, base, h, False).json()["consultas_cadin"][-1]
    assert cliente.post(f"{base}/cadin/{sem['id']}/reenviar-email", headers=h).status_code == 400
    assert cliente.post(f"{base}/cadin/00000000-0000-0000-0000-000000000000/reenviar-email", headers=h).status_code == 404


def test_mascara_do_email_de_cadin_valida_placeholders_e_so_uma_ativa(cliente, admin, cenario):
    contrato, h, base = cenario
    modelos = cliente.get("/api/contratos/modelos", params={"tipo": "email_cadin", "somente_ativos": "false"}, headers=h).json()
    assert len(modelos) == 1 and modelos[0]["ativo"] and "#pendencia" in modelos[0]["conteudo"]["html"]
    nomes = {p["nome"] for p in cliente.get("/api/contratos/modelos/email-cadin/placeholders", headers=h).json()}
    assert {"pendencia", "dataconsulta", "horaconsulta", "usuarioconsulta", "nrocontrato", "razaosocialempresa"} <= nomes and "nomeautoridade" not in nomes
    corpo = {"tipo": "email_cadin", "nome": "Outro", "assunto": "Aviso #nrocontrato", "html": "<p>Oi #pendencia</p>", "ativo": True}
    # Quem tem só MODIFICACAO não grava; a máscara ativa já existe (409); placeholder inválido (400)
    assert cliente.post("/api/contratos/modelos", json=corpo, headers=h).status_code == 403
    assert cliente.post("/api/contratos/modelos", json=corpo, headers=admin).status_code == 409
    assert cliente.post("/api/contratos/modelos", json={**corpo, "html": "<p>#naoexiste</p>", "ativo": False}, headers=admin).status_code == 400
    assert cliente.post("/api/contratos/modelos", json={**corpo, "assunto": "#naoexiste", "ativo": False}, headers=admin).status_code == 400
    assert cliente.post("/api/contratos/modelos", json={**corpo, "assunto": ""}, headers=admin).status_code == 422
    # Troca da máscara: a nova passa a valer
    cliente.put(f"/api/contratos/modelos/{modelos[0]['id']}", json={**corpo, "nome": "Padrão", "ativo": False}, headers=admin)
    assert cliente.post("/api/contratos/modelos", json={**corpo, "html": "<p>Atenção: #pendencia</p>"}, headers=admin).status_code == 201
    _cadin(cliente, base, h, True, texto="Multa")
    assert SmtpSimulado.enviadas[0][0]["Subject"] == f"Aviso {contrato['numero']}"
    assert "Atenção: Multa" in SmtpSimulado.enviadas[0][0].get_body(("html",)).get_content()
    # Sem nenhuma máscara ativa, a falha fica registrada
    for m in cliente.get("/api/contratos/modelos", params={"tipo": "email_cadin"}, headers=h).json():
        cliente.put(f"/api/contratos/modelos/{m['id']}", json={**corpo, "nome": m["nome"], "ativo": False}, headers=admin)
    SmtpSimulado.enviadas.clear()
    consulta = _cadin(cliente, base, h, True, texto="Outra").json()["consultas_cadin"][-1]
    assert consulta["email_ok"] is False and "máscara" in consulta["email_erro"] and SmtpSimulado.enviadas == []


def _textos_do_consolidado(cliente, base, h) -> list[str]:
    r = cliente.post(f"{base}/consolidado", headers=h)
    assert r.status_code == 200, r.text
    pdf = cliente.get(f"{base}/arquivos/{r.json()['consolidado']['anexo_id']}", headers=h).content
    return [" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(pdf)).pages]


def test_consolidado_com_pendencia_tem_o_memorial_depois_da_ultima_certidao(cliente, admin, cenario):
    contrato, h, base = cenario
    _cadin(cliente, base, h, True, texto="Débito A")
    _cadin(cliente, base, h, True, texto="Débito B")
    assert _cadin(cliente, base, h, False).json()["etapa_atual"] == "consolidado"
    textos = _textos_do_consolidado(cliente, base, h)
    indice = textos[0]
    assert "Memorial do CADIN" in indice
    memorial = next(i for i, t in enumerate(textos) if "Memorial do CADIN" in t and "Consultas ao CADIN" in t)
    # Contracapas das 3 certidões (com data-hora e quem registrou) e o memorial logo depois da última certidão
    certidoes = [i for i, t in enumerate(textos) if re.search(r"· CADIN Certidão do CADIN", t)]
    assert len(certidoes) == 3 and certidoes[-1] < memorial
    assert all(re.search(r"Consulta registrada em \d{2}/\d{2}/\d{4} \d{2}:\d{2}", textos[i]) and "Registrada por" in textos[i] for i in certidoes)
    # O memorial só traz os fatos: nº, data-hora, resultado e quem inseriu; sem frase de conclusão
    assert textos[memorial].count("Com pendência") == 2 and textos[memorial].count("Sem pendência") == 1 and "Gestora Silva" in textos[memorial]
    assert not re.search(r"demora|atraso|regulariz|culpa|devido|motivo", textos[memorial], re.I)
    # O e-mail enviado também entra (a cópia em PDF), antes do memorial
    assert any("E-mail de notificação da pendência no CADIN" in t and "Débito" not in "" for t in textos[:memorial])


def test_consolidado_sem_pendencia_continua_so_com_contracapa_e_certidao(cliente, admin, cenario):
    contrato, h, base = cenario
    assert _cadin(cliente, base, h, False).json()["etapa_atual"] == "consolidado"
    textos = _textos_do_consolidado(cliente, base, h)
    assert not any("Memorial do CADIN" in t for t in textos)
    assert sum(1 for t in textos if re.search(r"· CADIN Certidão do CADIN", t)) == 1


def test_pendencia_no_cadin_vira_ocorrencia_no_diario_com_a_mesma_data_e_hora(cliente, admin, cenario):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    contrato, h, base = cenario
    r = _cadin(cliente, base, h, True, "Débito de ICMS em aberto")
    consulta = r.json()["consultas_cadin"][0]
    ocorrencias = cliente.get(_url(contrato, "/diario"), headers=h).json()["ocorrencias"]
    assert len(ocorrencias) == 1
    o = ocorrencias[0]
    # Mesmo instante da consulta (data e hora de registro), na competência da etapa
    assert datetime.fromisoformat(o["criado_em"]) == datetime.fromisoformat(consulta["criado_em"])
    instante = datetime.fromisoformat(consulta["criado_em"])
    # O SQLite devolve instantes sem fuso (UTC); em produção vêm com fuso
    quando = (instante if instante.tzinfo else instante.replace(tzinfo=ZoneInfo("UTC"))).astimezone(ZoneInfo("America/Sao_Paulo"))
    assert o["data_ocorrencia"] == quando.date().isoformat() and o["competencia_afetada"] == "2026-01"
    assert "Débito de ICMS em aberto" in o["descricao"] and "Pendência no CADIN" in o["descricao"]
    assert o["possui_glosa"] is False and o["impacta_avaliacao"] is False
    # Reenviar o e-mail não duplica a ocorrência, e consulta sem pendência não cria ocorrência
    assert cliente.post(f"{base}/cadin/{consulta['id']}/reenviar-email", headers=h).status_code == 200
    _cadin(cliente, base, h, False)
    assert len(cliente.get(_url(contrato, "/diario"), headers=h).json()["ocorrencias"]) == 1


def test_conta_de_integracao_so_lanca_a_ob_pela_acao_do_perfil(cliente, admin, cenario):
    """Perfil com "Consultar contratos" + "Lançar ordem bancária" anexa a OB em qualquer contrato, sem estar na equipe e sem poder mais nada."""
    contrato, h, base = cenario
    assert _cadin(cliente, base, h, False).json()["etapa_atual"] == "consolidado"
    assert cliente.post(f"{base}/consolidado", headers=h).json()["etapa_atual"] == "ordem_bancaria"
    robo = criar_usuario("robo-ob")
    leitor = criar_usuario("leitor-ob")
    contratos_id = next(r["id"] for r in cliente.get("/api/acl/recursos", headers=admin).json() if r["slug"] == "contratos")
    acoes = {a["codigo"] for r in cliente.get("/api/acl/recursos", headers=admin).json() if r["slug"] == "contratos" for a in r["acoes"]}
    assert "LANCAR_OB" in acoes
    for nome, usuario, marcadas in (("Integração OB", robo, ["LEITURA", "LANCAR_OB"]), ("Só consulta", leitor, ["LEITURA"])):
        perfil = cliente.post("/api/acl/perfis", json={"nome": nome}, headers=admin).json()["id"]
        assert cliente.put(f"/api/acl/perfis/{perfil}/modulos/{contratos_id}", json={"acoes": marcadas}, headers=admin).status_code == 200
        assert cliente.put(f"/api/acl/perfis/{perfil}/usuarios", json={"usuarios_ids": [usuario]}, headers=admin).status_code == 200
    # Ação que o módulo não oferece é recusada
    perfil_x = cliente.post("/api/acl/perfis", json={"nome": "X"}, headers=admin).json()["id"]
    assert cliente.put(f"/api/acl/perfis/{perfil_x}/modulos/{contratos_id}", json={"acoes": ["INVENTADA"]}, headers=admin).status_code == 400
    # O detalhe da competência diz quem pode lançar a OB (a tela mostra o botão a quem tem a ação, mesmo sem editar o contrato)
    hl = cabecalho(cliente, "leitor-ob")
    assert cliente.get(base, headers=cabecalho(cliente, "robo-ob")).json()["pode_lancar_ob"] is True
    assert cliente.get(base, headers=hl).json()["pode_lancar_ob"] is False
    # Quem só consulta não lança a OB
    assert cliente.get(base, headers=hl).status_code == 200
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=hl).status_code == 403
    # A conta da integração lança a OB (não está na equipe) e continua sem poder alterar o contrato
    hr = cabecalho(cliente, "robo-ob")
    assert cliente.post(f"{base}/consolidado", headers=hr).status_code == 403
    r = cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=hr)
    assert r.status_code == 200 and r.json()["etapa_atual"] == "concluida"
    # Não repete: a competência já está concluída
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=hr).status_code == 400


def test_ob_lancada_avisa_os_prepostos_pela_mascara_e_pode_reenviar(cliente, admin, cenario):
    """Ao lançar a OB, a máscara "E-mail de pagamento" vai aos prepostos (equipe em Cc), com valor e data; falha e reenvio ficam registrados."""
    contrato, h, base = cenario
    definir_parametros(corte_alertas_a_partir_de=date(2000, 1, 1))  # a competência do cenário é de 01/2026: sem o corte, o e-mail de pagamento não sai
    assert _cadin(cliente, base, h, False).json()["etapa_atual"] == "consolidado"
    assert cliente.post(f"{base}/consolidado", headers=h).json()["etapa_atual"] == "ordem_bancaria"
    # Sem máscara ativa: a OB é lançada e o e-mail registra a falha com a explicação
    SmtpSimulado.enviadas.clear()
    assert cliente.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=h).json()["etapa_atual"] == "concluida"
    falha = cliente.get(base, headers=h).json()["email_ob"]
    assert falha["ok"] is False and "máscara" in falha["erro"] and SmtpSimulado.enviadas == []
    # Cadastra a máscara padrão (placeholder fora da lista é recusado; duas ativas, também)
    padrao = {"tipo": "email_ob", "nome": "E-mail de pagamento", "assunto": email_ob_mascara.ASSUNTO_PADRAO, "html": email_ob_mascara.HTML_PADRAO, "ativo": True}
    assert cliente.post("/api/contratos/modelos", json={**padrao, "html": "<p>#naoexiste</p>"}, headers=admin).status_code == 400
    assert cliente.post("/api/contratos/modelos", json=padrao, headers=admin).status_code == 201
    assert cliente.post("/api/contratos/modelos", json={**padrao, "nome": "Outra"}, headers=admin).status_code == 409
    nomes = {p["nome"] for p in cliente.get("/api/contratos/modelos/email-ob/placeholders", headers=admin).json()}
    assert {"valorpago", "datapagamento", "horapagamento", "usuarioob", "nrocontrato"} <= nomes
    # Reenviar: Para = preposto ativo; Cc = equipe; o texto leva o valor e o dia
    assert cliente.post(f"{base}/ordem-bancaria/reenviar-email", headers=h).status_code == 200
    assert len(SmtpSimulado.enviadas) == 1
    mensagem = SmtpSimulado.enviadas[0][0]
    assert mensagem["To"] == "paulo@acme.com" and set(a.strip() for a in mensagem["Cc"].split(",")) == {"gestora@sp.gov.br", "fiscal@sp.gov.br"}
    assert mensagem["Subject"] == f"Contrato {contrato['numero']} - Janeiro/2026 - Pagamento efetuado"
    corpo = mensagem.get_body(("html",)).get_content()
    assert "R$ 2.105,00" in corpo and "Janeiro/2026" in corpo and "Gestora Silva" in corpo and "#" not in re.sub(r"&#\d+;|#[0-9a-fA-F]{3,6}", "", corpo)
    ok = cliente.get(base, headers=h).json()["email_ob"]
    assert ok["ok"] is True and ok["destinatarios"][0] == "paulo@acme.com"
    # Não há o que avisar antes da OB
    outra = cliente.get(_url(contrato, "/competencias/identificador/2026-02"), headers=h).json()
    assert cliente.post(_url(contrato, f"/competencias/{outra['id']}/ordem-bancaria/reenviar-email"), headers=h).status_code == 400


def test_consolidado_traz_o_diario_de_bordo_quando_ha_ocorrencia_na_competencia(cliente, admin, cenario):
    """Toda competência com ocorrência (aqui, a pendência no CADIN vira ocorrência) leva o diário de bordo no consolidado, mesmo sem avaliação."""
    contrato, h, base = cenario
    _cadin(cliente, base, h, True, "Débito de ICMS em aberto")
    _cadin(cliente, base, h, False)
    textos = _textos_do_consolidado(cliente, base, h)
    assert "Diário de bordo da competência" in textos[0]  # no índice
    assert any("Débito de ICMS em aberto" in t and "Diário de bordo" in t for t in textos)


def test_consolidado_sem_ocorrencia_nao_tem_diario(cliente, admin, cenario):
    contrato, h, base = cenario
    _cadin(cliente, base, h, False)
    assert not any("Diário de bordo da competência" in t for t in _textos_do_consolidado(cliente, base, h))
