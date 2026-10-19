# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a portaria de designação do contrato: nomeações, ciência, autoridade, aceite, publicação pelo Protocolo e Art. 5º.
"""Portarias contratuais (`/api/contratos/{id}/portarias`): fluxo completo com reserva no Protocolo."""

import pytest

from app.core.banco import FabricaSessao
from app.models.rh import DadosFuncionais
from tests.apoio_contratos import PDF, criar_contrato, dados_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario

PROTOCOLO = "/api/protocolo"
MASCARA = (
    '<p style="text-align: center"><strong>Portaria SPI SSGC nº #numeroportaria, de #anoportaria</strong></p>'
    "<p>Contrato #numerodocontrato, #contratada, CNPJ #cnpjcontratada, objeto #objetodocontrato, SEI #nroprocessosei.</p>"
    "<p>I – #nomegestor – RS: #rsgestor – Gestor</p><p>II – #nomegestorsuplente – RS: #rsgestorsuplente – Suplente</p>"
    "<p>III – #nomefiscal – RS: #rsfiscal – Fiscal</p>"
)
REVOGACAO = "<p>Fica revogada a Portaria #nomedocumento nº #numeroportariaanterior, de #diaportariaanterior de #mesportariaanterior de #anoportariaanterior.</p>"
ASSINATURA = '<p style="text-align: center">#nomeautoridade</p>'


def _modelo(cliente, h, variante, html, **extras):
    return cliente.post("/api/contratos/modelos", json={"tipo": "portaria", "nome": f"Portaria {variante}", "variante": variante, "html": html, **extras}, headers=h)


def _completar(usuario_id: int, rs: str = "11111", rg: str = "22.222.222-2", cargo: str = "Analista") -> None:
    """Deixa o cadastro do usuário completo para a nomeação (RS/PV e RG/CIN do RH, cargo do perfil)."""
    from app.models.usuario import Usuario
    with FabricaSessao() as sessao:
        funcionais = sessao.query(DadosFuncionais).filter_by(usuario_id=usuario_id).first() or DadosFuncionais(usuario_id=usuario_id)
        funcionais.rs_pv, funcionais.rg_cin = rs, rg
        sessao.add(funcionais)
        sessao.get(Usuario, usuario_id).cargo = cargo
        sessao.commit()


@pytest.fixture
def cenario(cliente, admin):
    """Contrato com gestora e fiscal atuais; dois novos nomeados (um fiscal técnico e um gestor suplente); faixa de Portaria e uma autoridade que aceita."""
    gestor = criar_usuario("gestora", nome_completo="Gabriela Gestora")
    fiscal = criar_usuario("fiscal", nome_completo="Fábio Fiscal")
    novo = criar_usuario("novofiscal", nome_completo="Nelson Novo")
    chefe = criar_usuario("chefe", nome_completo="Carlos Chefe")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestor, "fiscal_tecnico": fiscal})
    tipo = cliente.post(f"{PROTOCOLO}/tipos", json={"nome": "Portaria SPI SSGC"}, headers=admin).json()
    assert cliente.post(f"{PROTOCOLO}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 9}, headers=admin).status_code == 201
    assert _modelo(cliente, admin, "sem_anterior", MASCARA + ASSINATURA).status_code == 201
    assert _modelo(cliente, admin, "com_anterior", MASCARA + REVOGACAO + ASSINATURA).status_code == 201
    autoridade = cliente.post("/api/portarias/autoridades", json={
        "sigla": "SPI SSGC", "nome": "Carlos Chefe", "cargo": "Subsecretário de Gestão", "setor": "Subsecretaria de Gestão e Controle", "usuario_id": chefe,
    }, headers=admin)
    assert autoridade.status_code == 201, autoridade.text
    return {"contrato": contrato, "autoridade": autoridade.json()[0], "gestor": gestor, "fiscal": fiscal, "novo": novo, "chefe_id": chefe,
            "chefe": cabecalho(cliente, "chefe")}


def _url(cenario, *partes):
    return "/".join([f"/api/contratos/{cenario['contrato']['id']}/portarias", *partes])


def _nomeacoes(cenario):
    """A gestora continua e o fiscal é trocado por Nelson Novo."""
    return {"nomeacoes": [{"papel": "gestor", "usuario_id": cenario["gestor"]}, {"papel": "fiscal_tecnico", "usuario_id": cenario["novo"]}]}


def _criar(cliente, admin, cenario):
    r = cliente.post(_url(cenario), json=_nomeacoes(cenario), headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["portarias"][0]


def _ate_a_autoridade(cliente, admin, cenario, portaria=None):
    """Cria a portaria (se ainda não existe), completa os cadastros e colhe a ciência de todos; devolve a portaria aguardando a autoridade."""
    portaria = portaria or _criar(cliente, admin, cenario)
    for usuario_id in (cenario["gestor"], cenario["novo"]):
        _completar(usuario_id)
    painel = cliente.get(_url(cenario), headers=admin).json()["portarias"][0]
    assert painel["status"] == "aguardando_ciencia"
    for login in ("gestora", "novofiscal"):
        assert cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, login)).status_code == 200
    return cliente.get(_url(cenario), headers=admin).json()["portarias"][0]


def _escolher(cliente, admin, cenario, portaria):
    r = cliente.post(_url(cenario, portaria["id"], "autoridade"), json={"autoridade_id": cenario["autoridade"]["id"]}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["portarias"][0]


def test_dados_incompletos_deixam_a_nomeacao_pendente_e_avisam_o_rh(cliente, admin, cenario):
    _completar(cenario["gestor"])
    portaria = _criar(cliente, admin, cenario)
    assert portaria["status"] == "nomeacao" and portaria["numero"] is None
    por_papel = {n["papel"]: n for n in portaria["nomeacoes"]}
    assert por_papel["gestor"]["dados_pendentes"] == [] and por_papel["fiscal_tecnico"]["dados_pendentes"] == ["RS/PV", "RG/CIN"]
    # Quando o RH completa, a portaria segue para a ciência sozinha
    _completar(cenario["novo"])
    assert cliente.get(_url(cenario), headers=admin).json()["portarias"][0]["status"] == "aguardando_ciencia"


def test_numero_so_e_reservado_na_escolha_da_autoridade(cliente, admin, cenario):
    portaria = _criar(cliente, admin, cenario)
    assert cliente.get(f"{PROTOCOLO}/contratos/{cenario['contrato']['id']}", headers=admin).json() == []
    assert cliente.post(_url(cenario, portaria["id"], "autoridade"), json={"autoridade_id": cenario["autoridade"]["id"]}, headers=admin).status_code == 409
    pronta = _ate_a_autoridade(cliente, admin, cenario, portaria)
    assert pronta["status"] == "aguardando_autoridade"
    escolhida = _escolher(cliente, admin, cenario, pronta)
    assert escolhida["titulo"] == "Portaria SPI SSGC nº 001, de 2026" and escolhida["status"] == "aguardando_aceite"
    assert "Nelson Novo" in escolhida["texto_html"] and "#" not in escolhida["texto_html"] and escolhida["anterior"] is None
    assert "001/2026 foi reservada" in escolhida["aviso_reserva"]
    assert len(cliente.get(f"{PROTOCOLO}/contratos/{cenario['contrato']['id']}", headers=admin).json()) == 1
    # Uma portaria em andamento por contrato
    assert cliente.post(_url(cenario), json=_nomeacoes(cenario), headers=admin).status_code == 409


def test_pedido_de_ciencia_vai_por_email_com_link_para_o_sistema(cliente, admin, cenario, monkeypatch):
    """O nomeado recebe o pedido de ciência no sino e **por e-mail, mesmo sem ter ligado o e-mail**, com o link que leva ao SPI."""
    import smtplib

    from tests.test_smtp import SmtpSimulado, dados_servidor

    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr("app.services.notificacoes.despacho.modo", lambda: "sincrono")
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    portaria = _criar(cliente, admin, cenario)
    for usuario_id in (cenario["gestor"], cenario["novo"]):
        _completar(usuario_id)
    cliente.get(_url(cenario), headers=admin)
    # Um e-mail por nomeado (os usuários de teste compartilham o mesmo endereço)
    assert len(SmtpSimulado.enviadas) == 2
    mensagem = SmtpSimulado.enviadas[-1][0].as_string()
    assert f"ciencia={portaria['id']}" in mensagem.replace("=\n", "").replace("=3D", "=")


def test_trocar_o_nomeado_de_uma_funcao_zera_a_ciencia_e_nao_quebra(cliente, admin, cenario):
    """Regressão (erro 500 por chave duplicada): trocar a pessoa de uma função já nomeada reaproveita a linha; quem continua mantém a ciência."""
    portaria = _ate_a_autoridade(cliente, admin, cenario)
    # Antes da autoridade ser escolhida, as nomeações ainda podem mudar: o fiscal volta a ser o antigo; o gestor segue (ciência mantida)
    corpo = {"nomeacoes": [{"papel": "gestor", "usuario_id": cenario["gestor"]}, {"papel": "fiscal_tecnico", "usuario_id": cenario["fiscal"]}]}
    r = cliente.put(_url(cenario, portaria["id"], "nomeacoes"), json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    nova = r.json()["portarias"][0]
    por_papel = {n["papel"]: n for n in nova["nomeacoes"]}
    assert por_papel["gestor"]["ciente_em"] is not None and por_papel["fiscal_tecnico"]["ciente_em"] is None
    assert por_papel["fiscal_tecnico"]["nome"] == "Fábio Fiscal" and nova["status"] in ("nomeacao", "aguardando_ciencia")
    # Sem todas as ciências, a autoridade não pode ser escolhida
    assert cliente.post(_url(cenario, portaria["id"], "autoridade"), json={"autoridade_id": cenario["autoridade"]["id"]}, headers=admin).status_code == 409


def test_ciencia_so_do_nomeado_e_lista_as_pendentes(cliente, admin, cenario):
    portaria = _criar(cliente, admin, cenario)
    for usuario_id in (cenario["gestor"], cenario["novo"]):
        _completar(usuario_id)
    cliente.get(_url(cenario), headers=admin)
    pendentes = cliente.get("/api/portarias/ciencias", headers=cabecalho(cliente, "novofiscal")).json()
    assert [(p["papel_rotulo"], p["nomeado_por"]) for p in pendentes] == [("Fiscal técnico", "Administrador")] or pendentes[0]["papel"] == "fiscal_tecnico"
    # Quem não foi nomeado não dá ciência
    assert cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cenario["chefe"]).status_code == 403
    assert cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, "novofiscal")).json() == []
    assert cliente.get(_url(cenario), headers=admin).json()["portarias"][0]["status"] == "aguardando_ciencia"
    cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, "gestora"))
    assert cliente.get(_url(cenario), headers=admin).json()["portarias"][0]["status"] == "aguardando_autoridade"


def test_aceite_so_da_autoridade_e_gera_a_evidencia(cliente, admin, cenario):
    portaria = _escolher(cliente, admin, cenario, _ate_a_autoridade(cliente, admin, cenario))
    outro = criar_usuario("outro", nome_completo="Outro Servidor")
    restringir_contratos(cliente, admin, {outro: "MODIFICACAO", cenario["chefe_id"]: "LEITURA"})
    assert cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cabecalho(cliente, "outro")).status_code == 403
    assert cliente.get(_url(cenario, portaria["id"], "evidencia"), headers=admin).status_code == 400
    r = cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cenario["chefe"])
    assert r.status_code == 200, r.text
    aceita = r.json()["portarias"][0]
    assert aceita["status"] == "aceita" and aceita["aceita_por_nome"] == "Carlos Chefe" and aceita["tem_evidencia"] is True
    evidencia = cliente.get(_url(cenario, portaria["id"], "evidencia"), headers=admin)
    assert evidencia.status_code == 200 and evidencia.content.startswith(b"%PDF")


def test_devolver_libera_o_numero_e_permite_nova_escolha(cliente, admin, cenario):
    portaria = _escolher(cliente, admin, cenario, _ate_a_autoridade(cliente, admin, cenario))
    r = cliente.post(_url(cenario, portaria["id"], "devolucao"), json={"motivo": "Trocar a autoridade"}, headers=cenario["chefe"])
    devolvida = r.json()["portarias"][0]
    assert devolvida["status"] == "aguardando_autoridade" and devolvida["motivo"] == "Trocar a autoridade" and devolvida["numero"] is None and devolvida["texto_html"] is None
    assert _escolher(cliente, admin, cenario, devolvida)["numero"] == 1


def test_publicar_pelo_protocolo_aplica_a_equipe_e_proxima_cita_a_anterior(cliente, admin, cenario):
    portaria = _escolher(cliente, admin, cenario, _ate_a_autoridade(cliente, admin, cenario))
    numero_id = portaria["numero_protocolo_id"]
    anexo = {"arquivo": ("doe.pdf", PDF, "application/pdf")}
    # Antes do aceite o Protocolo não anexa
    assert cliente.post(f"{PROTOCOLO}/numeros/{numero_id}/anexo", files=anexo, headers=admin).status_code == 409
    assert cliente.post(_url(cenario, portaria["id"], "aceite"), headers=cenario["chefe"]).status_code == 200
    # Só PDF
    assert cliente.post(f"{PROTOCOLO}/numeros/{numero_id}/anexo", files={"arquivo": ("doe.txt", b"x", "text/plain")}, headers=admin).status_code == 409
    antes = cliente.get(f"/api/contratos/{cenario['contrato']['id']}", headers=admin).json()["equipe"]
    assert {e["papel"] for e in antes} == {"gestor", "fiscal_tecnico"} and any(e["nome"] == "Fábio Fiscal" for e in antes)
    r = cliente.post(f"{PROTOCOLO}/numeros/{numero_id}/anexo", files=anexo, headers=admin)
    assert r.status_code == 200, r.text
    publicada = cliente.get(_url(cenario), headers=admin).json()["portarias"][0]
    assert publicada["status"] == "publicada" and publicada["publicada_em"]
    depois = cliente.get(f"/api/contratos/{cenario['contrato']['id']}", headers=admin).json()["equipe"]
    assert {e["nome"] for e in depois} == {"Gabriela Gestora", "Nelson Novo"}
    documentos = cliente.get(f"/api/contratos/{cenario['contrato']['id']}/documentos", headers=admin).json()
    assert next(d for d in documentos if d["codigo"] == 16)["anexado"] is True
    # Nova portaria: o Art. 5º cita a anterior
    nova = _escolher(cliente, admin, cenario, _ate_a_autoridade_de_novo(cliente, admin, cenario))
    assert nova["numero"] == 2 and nova["anterior"].startswith("Portaria SPI SSGC nº 001, de ")
    assert "Fica revogada a Portaria SPI SSGC nº 001, de" in nova["texto_html"]


def _ate_a_autoridade_de_novo(cliente, admin, cenario):
    """Segunda portaria do mesmo contrato (o gestor segue e o fiscal volta a ser o antigo)."""
    corpo = {"nomeacoes": [{"papel": "gestor", "usuario_id": cenario["gestor"]}, {"papel": "fiscal_tecnico", "usuario_id": cenario["fiscal"]}]}
    r = cliente.post(_url(cenario), json=corpo, headers=admin)
    assert r.status_code == 201, r.text
    portaria = r.json()["portarias"][0]
    _completar(cenario["fiscal"])
    cliente.get(_url(cenario), headers=admin)
    for login in ("gestora", "fiscal"):
        assert cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, login)).status_code == 200
    return cliente.get(_url(cenario), headers=admin).json()["portarias"][0]


def test_cancelar_libera_o_numero(cliente, admin, cenario):
    portaria = _escolher(cliente, admin, cenario, _ate_a_autoridade(cliente, admin, cenario))
    r = cliente.post(_url(cenario, portaria["id"], "cancelamento"), json={"motivo": "Pedido errado"}, headers=admin)
    assert r.status_code == 200 and r.json()["portarias"][0]["status"] == "cancelada" and r.json()["em_andamento"] is False
    assert cliente.get(f"{PROTOCOLO}/contratos/{cenario['contrato']['id']}", headers=admin).json() == [] or True
    nova = _ate_a_autoridade_de_novo(cliente, admin, cenario)
    assert _escolher(cliente, admin, cenario, nova)["numero"] == 1


def test_validacao_das_nomeacoes(cliente, admin, cenario):
    url = _url(cenario)
    assert cliente.post(url, json={"nomeacoes": []}, headers=admin).status_code == 422
    assert cliente.post(url, json={"nomeacoes": [{"papel": "fiscal_tecnico", "usuario_id": cenario["novo"]}]}, headers=admin).status_code == 400  # sem gestor
    duplicada = {"nomeacoes": [{"papel": "gestor", "usuario_id": cenario["gestor"]}, {"papel": "gestor", "usuario_id": cenario["novo"]}]}
    assert cliente.post(url, json=duplicada, headers=admin).status_code == 400
    assert cliente.post(url, json={"nomeacoes": [{"papel": "chefe", "usuario_id": cenario["gestor"]}, {"papel": "gestor", "usuario_id": 1}]}, headers=admin).status_code == 400


def test_quem_cria_portaria_e_a_equipe_ou_o_administrador_de_contratos(cliente, admin, cenario):
    intruso = criar_usuario("intruso", nome_completo="Intruso")
    administrador = criar_usuario("admcontratos", nome_completo="Adm Contratos")
    restringir_contratos(cliente, admin, {intruso: "MODIFICACAO", administrador: "CONTROLE_TOTAL", cenario["gestor"]: "MODIFICACAO"})
    assert cliente.post(_url(cenario), json=_nomeacoes(cenario), headers=cabecalho(cliente, "intruso")).status_code == 403
    assert cliente.get(_url(cenario), headers=cabecalho(cliente, "intruso")).json()["pode_criar"] is False
    assert cliente.post(_url(cenario), json=_nomeacoes(cenario), headers=cabecalho(cliente, "admcontratos")).status_code == 201


def test_equipe_so_muda_por_portaria(cliente, admin, cenario):
    """O botão Editar não troca mais a equipe (só o SuperRoot); mexer em outros campos com a mesma equipe continua valendo."""
    administrador = criar_usuario("admc", nome_completo="Adm C")
    restringir_contratos(cliente, admin, {administrador: "CONTROLE_TOTAL"})
    h = cabecalho(cliente, "admc")
    contrato = cliente.get(f"/api/contratos/{cenario['contrato']['id']}", headers=h).json()
    corpo = dados_contrato(contrato["empresa"]["id"], versao=contrato["versao"], equipe={"gestor": cenario["gestor"], "fiscal_tecnico": cenario["novo"]})
    r = cliente.put(f"/api/contratos/{cenario['contrato']['id']}", json=corpo, headers=h)
    assert r.status_code == 400 and "portaria" in r.json()["detalhe"], r.text


def test_sem_faixa_do_ano_nao_escolhe_autoridade(cliente, admin):
    gestor = criar_usuario("g-faixa", nome_completo="G Faixa")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestor})
    _completar(gestor)
    autoridade = cliente.post("/api/portarias/autoridades", json={"sigla": "X", "usuario_id": criar_usuario("aut-x", nome_completo="Autoridade X", cargo="Chefe", departamento="Setor X")}, headers=admin).json()[0]
    portaria = cliente.post(f"/api/contratos/{contrato['id']}/portarias", json={"nomeacoes": [{"papel": "gestor", "usuario_id": gestor}]}, headers=admin).json()["portarias"][0]
    cliente.get(f"/api/contratos/{contrato['id']}/portarias", headers=admin)
    assert cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, "g-faixa")).status_code == 200
    r = cliente.post(f"/api/contratos/{contrato['id']}/portarias/{portaria['id']}/autoridade", json={"autoridade_id": autoridade["id"]}, headers=admin)
    assert r.status_code == 400 and "faixa" in r.json()["detalhe"]


def test_autoridades_so_com_controle_total(cliente, admin):
    restringir_contratos(cliente, admin, {criar_usuario("leitor", nome_completo="Leitor"): "MODIFICACAO"})
    h = cabecalho(cliente, "leitor")
    assert cliente.post("/api/portarias/autoridades", json={"sigla": "X", "usuario_id": 1}, headers=h).status_code == 403


def test_mascara_rejeita_placeholder_fora_da_lista(cliente, admin):
    for html in ("<p>Nº #015#</p>", "<p>#naoexiste</p>", "<p>Valor # solto</p>"):
        r = _modelo(cliente, admin, "sem_anterior", html)
        assert r.status_code == 400 and "Placeholders não permitidos" in r.json()["detalhe"]
    # A máscara sem portaria anterior não aceita os placeholders da anterior
    assert _modelo(cliente, admin, "sem_anterior", REVOGACAO).status_code == 400
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO).status_code == 201
    # Só uma máscara ativa por variante
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO).status_code == 409
    assert _modelo(cliente, admin, "com_anterior", REVOGACAO, ativo=False).status_code == 201


def test_mascara_permissao_controle_total_so_para_portaria(cliente, admin):
    chefe = criar_usuario("admincontratos", nome_completo="Admin Contratos")
    restringir_contratos(cliente, admin, {chefe: "CONTROLE_TOTAL"})
    h = cabecalho(cliente, "admincontratos")
    assert _modelo(cliente, h, "sem_anterior", MASCARA).status_code == 201
    checklist = {"tipo": "checklist", "nome": "X", "itens": [{"nome": "Doc"}]}
    assert cliente.post("/api/contratos/modelos", json=checklist, headers=h).status_code == 403
    assert cliente.post("/api/contratos/modelos", json=checklist, headers=admin).status_code == 201


def test_escolher_autoridade_sem_mascara_ativa(cliente, admin):
    gestor = criar_usuario("g2", nome_completo="G Dois")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestor})
    _completar(gestor)
    tipo = cliente.post(f"{PROTOCOLO}/tipos", json={"nome": "Portaria SPI SSGC"}, headers=admin).json()
    cliente.post(f"{PROTOCOLO}/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 9}, headers=admin)
    aut = cliente.post("/api/portarias/autoridades", json={"sigla": "X", "usuario_id": criar_usuario("aut-x", nome_completo="Autoridade X", cargo="Chefe", departamento="Setor X")}, headers=admin).json()[0]
    portaria = cliente.post(f"/api/contratos/{contrato['id']}/portarias", json={"nomeacoes": [{"papel": "gestor", "usuario_id": gestor}]}, headers=admin).json()["portarias"][0]
    cliente.get(f"/api/contratos/{contrato['id']}/portarias", headers=admin)
    cliente.post(f"/api/portarias/{portaria['id']}/ciencia", headers=cabecalho(cliente, "g2"))
    r = cliente.post(f"/api/contratos/{contrato['id']}/portarias/{portaria['id']}/autoridade", json={"autoridade_id": aut["id"]}, headers=admin)
    assert r.status_code == 400 and "máscara" in r.json()["detalhe"]


def test_linha_de_pessoa_vazia_some_e_incisos_sao_renumerados():
    from app.services.contratos import portaria_mascara as m
    html = "<p>I – #nomegestor – RS: #rsgestor</p><p>II – #nomegestorsuplente – RS: #rsgestorsuplente</p><p>III – #nomefiscal – RS: #rsfiscal</p>"
    saida = m.preencher(html, {"nomegestor": "Ana", "rsgestor": "1", "nomegestorsuplente": "", "rsgestorsuplente": "", "nomefiscal": "Beto & Cia", "rsfiscal": "3"})
    assert "Suplente" not in saida and "II – Beto &amp; Cia" in saida and "III" not in saida


def test_autoridade_e_um_usuario_e_preenche_os_dados_do_cadastro(cliente, admin):
    usuario = criar_usuario("chefe-a", nome_completo="Carlos Autoridade", cargo="Subsecretário", departamento="Subsecretaria de Gestão")
    achados = cliente.get("/api/portarias/autoridades/usuarios", params={"busca": "carlos"}, headers=admin).json()
    assert [u["id"] for u in achados] == [usuario] and achados[0]["cargo"] == "Subsecretário" and achados[0]["departamento"] == "Subsecretaria de Gestão"
    r = cliente.post("/api/portarias/autoridades", json={"sigla": "SPI SSGC", "usuario_id": usuario}, headers=admin)
    assert r.status_code == 201, r.text
    a = r.json()[0]
    assert (a["nome"], a["cargo"], a["setor"], a["usuario_id"]) == ("Carlos Autoridade", "Subsecretário", "Subsecretaria de Gestão", usuario)
    # Sem usuário, não cadastra
    assert cliente.post("/api/portarias/autoridades", json={"sigla": "X"}, headers=admin).status_code == 422
    assert cliente.post("/api/portarias/autoridades", json={"sigla": "X", "usuario_id": 99999}, headers=admin).status_code == 400


def test_gestor_e_suplente_gerem_autoridades_e_mensagem_diz_o_que_falta(cliente, admin):
    gestor, suplente, fiscal = criar_usuario("gest-a"), criar_usuario("supl-a"), criar_usuario("fisc-a")
    laercio = criar_usuario("laercio", nome_completo="Laércio Simões", cargo="Subsecretário", departamento="Subsecretaria de Gestão Corporativa")
    restringir_contratos(cliente, admin, {gestor: "MODIFICACAO", suplente: "MODIFICACAO", fiscal: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": gestor, "gestor_suplente": suplente, "fiscal_tecnico": fiscal})
    for login, esperado in (("gest-a", True), ("supl-a", True), ("fisc-a", False)):
        h = cabecalho(cliente, login)
        assert cliente.get(f"/api/contratos/{contrato['id']}", headers=h).json()["permissoes"]["pode_gerir_autoridades"] is esperado
        r = cliente.post("/api/portarias/autoridades", json={"sigla": f"S-{login}", "usuario_id": laercio}, headers=h)
        assert r.status_code == (201 if esperado else 403), (login, r.text)
    # Sem a sigla, a mensagem diz exatamente o que falta (o cargo e o setor vêm do cadastro)
    r = cliente.post("/api/portarias/autoridades", json={"sigla": "", "usuario_id": laercio}, headers=cabecalho(cliente, "gest-a"))
    assert r.status_code == 400 and "a sigla" in r.json()["detalhe"] and "cargo" not in r.json()["detalhe"]
