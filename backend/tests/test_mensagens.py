# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a mensageria: envio, caixa, ciência, avisos automáticos dos contratos, e-mails e lembretes.
"""Mensageria (`/api/mensagens`) e tarefas agendadas (`app.tarefas.mensageria`)."""

from datetime import date, timedelta

import smtplib

import pytest

from app.core.banco import FabricaSessao, agora_utc
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.setor import MembroSetor, Setor
from app.tarefas import mensageria
from tests.apoio_contratos import criar_contrato, restringir_contratos
from tests.conftest import cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor

URL = "/api/mensagens"


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    """SMTP simulado: nenhum e-mail sai de verdade."""
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)


def _setor(nome: str, membros: list[int]) -> int:
    with FabricaSessao() as sessao:
        setor = Setor(nome=nome)
        sessao.add(setor)
        sessao.flush()
        for u in membros:
            sessao.add(MembroSetor(setor_id=setor.id, usuario_id=u))
        sessao.commit()
        return setor.id


def _enviar(cliente, h, **extras):
    corpo = {"assunto": "Reunião de alinhamento", "corpo": "Reunião na sexta, às 10h.", "usuarios_ids": [], **extras}
    return cliente.post(URL, json=corpo, headers=h)


@pytest.fixture
def pessoas(cliente, admin):
    ids = {login: criar_usuario(login, nome_completo=f"{login.title()} da Silva", email=f"{login}@sp.gov.br") for login in ("ana", "bruno", "carla")}
    return ids, {login: cabecalho(cliente, login) for login in ids}


# --- Envio e caixa ---------------------------------------------------------------------------------

def test_envio_para_usuarios_e_setores_sem_repetir(cliente, admin, pessoas):
    ids, h = pessoas
    setor = _setor("Diretoria de Contratos", [ids["bruno"], ids["carla"]])
    r = _enviar(cliente, admin, usuarios_ids=[ids["ana"], ids["bruno"]], setores_ids=[setor], prioridade="alta", categoria="prazo")
    assert r.status_code == 201, r.text
    assert r.json()["destinatarios"] == 3
    # Cada um recebe uma vez, com a fotografia do texto
    for login in ("ana", "bruno", "carla"):
        caixa = cliente.get(URL, headers=h[login]).json()
        assert caixa["total"] == 1 and caixa["itens"][0]["assunto"] == "Reunião de alinhamento"
        assert caixa["itens"][0]["estado"] == "nao_visualizada" and caixa["itens"][0]["prioridade"] == "alta"
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 1


def test_setores_exigem_acl_e_validacoes(cliente, admin, pessoas):
    ids, h = pessoas
    setor = _setor("Setor X", [ids["carla"]])
    # Recurso cadastrado com regra só para outra pessoa: sem CONTROLE_TOTAL, setores dão 403
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Mensageria: setores", "slug": "mensageria-setores"}, headers=admin).json()
    cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "CONTROLE_TOTAL", "usuarios_ids": [ids["bruno"]], "setores_ids": []},
                 headers=admin)
    r = _enviar(cliente, h["ana"], setores_ids=[setor])
    assert r.status_code == 403 and r.json()["codigo"] == "acl_negado"
    assert cliente.get(f"{URL}/destinatarios", headers=h["ana"]).json()["pode_enviar_setores"] is False
    destinos = cliente.get(f"{URL}/destinatarios", headers=h["bruno"]).json()
    assert destinos["pode_enviar_setores"] is True and [s["nome"] for s in destinos["setores"]] == ["Setor X"]
    assert _enviar(cliente, h["bruno"], setores_ids=[setor]).status_code == 201
    # Sem destinatário, link externo e expiração no passado
    assert _enviar(cliente, h["ana"]).status_code == 400
    assert _enviar(cliente, h["ana"], usuarios_ids=[ids["bruno"]], link="https://exemplo.com").status_code == 422
    passado = (agora_utc() - timedelta(days=1)).isoformat()
    assert _enviar(cliente, h["ana"], usuarios_ids=[ids["bruno"]], expira_em=passado).status_code == 400


def test_abrir_ciencia_busca_sem_acento_e_entrega_alheia(cliente, admin, pessoas):
    ids, h = pessoas
    _enviar(cliente, admin, assunto="Medição de março", usuarios_ids=[ids["ana"]])
    _enviar(cliente, admin, assunto="Outro assunto", usuarios_ids=[ids["ana"]])
    achadas = cliente.get(URL, params={"busca": "medicao"}, headers=h["ana"]).json()
    assert [i["assunto"] for i in achadas["itens"]] == ["Medição de março"]
    entrega = achadas["itens"][0]["id"]
    # Outro usuário não abre a entrega da Ana
    assert cliente.get(f"{URL}/{entrega}", headers=h["bruno"]).status_code == 404
    aberta = cliente.get(f"{URL}/{entrega}", headers=h["ana"]).json()
    assert aberta["estado"] == "visualizada" and aberta["corpo"] == "Reunião na sexta, às 10h."
    ciente = cliente.post(f"{URL}/{entrega}/ciencia", headers=h["ana"]).json()
    assert ciente["estado"] == "ciente" and ciente["pendente"] is False
    assert cliente.get(URL, params={"estado": "cientes"}, headers=h["ana"]).json()["total"] == 1
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 1


def test_expiradas_somem_da_caixa(cliente, admin, pessoas):
    ids, h = pessoas
    _enviar(cliente, admin, usuarios_ids=[ids["ana"]])
    with FabricaSessao() as sessao:
        sessao.query(Mensagem).update({"expira_em": agora_utc() - timedelta(minutes=1)})
        sessao.commit()
    assert cliente.get(URL, params={"estado": "todas"}, headers=h["ana"]).json()["total"] == 0


def test_email_opcional_enviadas_e_lembrete(cliente, admin, pessoas):
    ids, h = pessoas
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    SmtpSimulado.enviadas.clear()
    r = _enviar(cliente, h["ana"], usuarios_ids=[ids["bruno"], ids["carla"]], enviar_email=True)
    mensagem_id = r.json()["mensagem_id"]
    assert sorted(to[0] for _, _, to, _ in SmtpSimulado.enviadas) == ["bruno@sp.gov.br", "carla@sp.gov.br"]
    # A Carla dá ciência; o acompanhamento mostra a situação de cada um
    entrega = cliente.get(URL, headers=h["carla"]).json()["itens"][0]["id"]
    cliente.post(f"{URL}/{entrega}/ciencia", headers=h["carla"])
    enviadas = cliente.get(f"{URL}/enviadas", headers=h["ana"]).json()
    assert enviadas["itens"][0]["destinatarios"] == 2 and enviadas["itens"][0]["cientes"] == 1
    detalhe = cliente.get(f"{URL}/enviadas/{mensagem_id}", headers=h["ana"]).json()
    assert [(s["nome"], s["ciente_em"] is not None, s["email_ok"]) for s in detalhe["situacao"]] == [
        ("Bruno da Silva", False, True), ("Carla da Silva", True, True)]
    # Só o autor (ou o SuperRoot) acompanha
    assert cliente.get(f"{URL}/enviadas/{mensagem_id}", headers=h["bruno"]).status_code == 404
    SmtpSimulado.enviadas.clear()
    r = cliente.post(f"{URL}/enviadas/{mensagem_id}/lembrar", headers=h["ana"])
    assert r.json()["lembrados"] == 1 and [to[0] for _, _, to, _ in SmtpSimulado.enviadas] == ["bruno@sp.gov.br"]
    assert SmtpSimulado.enviadas[0][0]["Subject"].startswith("Lembrete: ")


# --- Avisos automáticos dos contratos ---------------------------------------------------------------

def test_designacao_na_equipe_abre_janela(cliente, admin, pessoas):
    ids, h = pessoas
    restringir_contratos(cliente, admin, {ids["ana"]: "MODIFICACAO", ids["bruno"]: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": ids["ana"]})
    resumo = cliente.get(f"{URL}/resumo", headers=h["ana"]).json()
    janela = resumo["janela"]
    assert janela["assunto"] == f"Você foi cadastrado como Gestor no contrato {contrato['numero']}"
    assert janela["link"] == f"/contratos/{contrato['id']}" and janela["categoria"] == "atribuicao" and janela["abrir_em_janela"]
    # Abrir a janela marca como visualizada: ela não abre de novo, mas continua pendente de ciência
    cliente.get(f"{URL}/{janela['id']}", headers=h["ana"])
    resumo = cliente.get(f"{URL}/resumo", headers=h["ana"]).json()
    assert resumo["janela"] is None and resumo["pendentes"] == 1
    # Trocar o gestor avisa o novo; manter a equipe não gera aviso de novo
    corpo = {k: contrato[k] for k in ("numero", "apelido", "objeto", "data_inicio", "vigencia_inicial_meses", "vigencia_maxima_meses",
                                      "periodicidade_meses", "mes_reajuste", "sei_gestao_numero", "sei_gestao_link", "sei_execucao_numero",
                                      "sei_execucao_link")}
    itens = [{k: i[k] for k in ("id", "descricao", "tipo", "calcula_pro_rata", "codigo_classe", "codigo_natureza_despesa", "codigo_siafisico",
                                "codigo_catmat_catser", "quantidade_mensal", "valor_unitario", "unidade_fornecimento")} | {"quantidade_total": i["quantidade_original"]}
             for i in contrato["itens"]]
    corpo |= {"empresa_id": contrato["empresa"]["id"], "itens": itens, "equipe": {"gestor": ids["bruno"], "fiscal_tecnico": ids["ana"]},
              "versao": contrato["versao"]}
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    assert cliente.get(f"{URL}/resumo", headers=h["bruno"]).json()["janela"]["assunto"].startswith("Você foi cadastrado como Gestor")
    assert "Fiscal técnico" in cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["janela"]["assunto"]
    # Excluir o contrato apaga os avisos dele
    assert cliente.delete(f"/api/contratos/{contrato['id']}", headers=admin).status_code == 204
    assert cliente.get(URL, params={"estado": "todas"}, headers=h["ana"]).json()["total"] == 0


def test_notificar_nao_repete_chave_e_encerrar(cliente, admin, pessoas):
    from app.services import servico_mensagens

    ids, h = pessoas
    with FabricaSessao() as sessao:
        assert servico_mensagens.notificar(sessao, [ids["ana"]], "Conferir retenção", "Texto", chave="retencao:1", categoria="pendencia")
        assert servico_mensagens.notificar(sessao, [ids["ana"]], "Conferir retenção", "Texto", chave="retencao:1") is None
        sessao.commit()
        assert servico_mensagens.notificar(sessao, [ids["ana"], ids["bruno"]], "Conferir retenção", "Texto", chave="retencao:1")
        sessao.commit()
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 1
    with FabricaSessao() as sessao:
        assert servico_mensagens.encerrar(sessao, chave="retencao:1") == 2
        sessao.commit()
    item = cliente.get(URL, params={"estado": "todas"}, headers=h["ana"]).json()["itens"][0]
    assert item["estado"] == "encerrada" and item["pendente"] is False


# --- Tarefas agendadas -------------------------------------------------------------------------------

def test_lembretes_vencimento_atraso_fila_e_resumo(cliente, admin, pessoas, monkeypatch):
    ids, h = pessoas
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    dia = date(2026, 11, 20)  # contrato de 01/01/2026 a 31/12/2026: faltam 41 dias
    monkeypatch.setattr("app.services.contratos.servico_contratos.hoje", lambda: dia)
    restringir_contratos(cliente, admin, {ids["ana"]: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": ids["ana"]})
    SmtpSimulado.enviadas.clear()
    with FabricaSessao() as sessao:
        # A fila de e-mails leva o aviso da designação na equipe
        assert mensageria.enviar_emails_pendentes(sessao) == 1
        assert mensageria.enviar_emails_pendentes(sessao) == 0
        primeiro = mensageria.gerar_lembretes(sessao, dia)
        segundo = mensageria.gerar_lembretes(sessao, dia)
    assert primeiro["vencimentos"] == 1 and segundo["vencimentos"] == 0
    assert primeiro["resumos_diarios"] == 1 and segundo["resumos_diarios"] == 0
    caixa = cliente.get(URL, headers=h["ana"]).json()
    vencimento = next(i for i in caixa["itens"] if i["categoria"] == "prazo")
    assert vencimento["assunto"] == f"Contrato {contrato['numero']} vence em 41 dia(s) (31/12/2026)"
    assuntos = [m["Subject"] for m, _, _, _ in SmtpSimulado.enviadas]
    assert any("Você foi cadastrado como Gestor" in a for a in assuntos)
    assert any(a.startswith("SGI SPI: ") and "aguardando sua ciência" in a for a in assuntos)
    # Marco seguinte (30 dias) gera um novo aviso
    with FabricaSessao() as sessao:
        assert mensageria.gerar_lembretes(sessao, date(2026, 12, 2))["vencimentos"] == 1


def test_lembrete_de_ciencia_no_terceiro_dia(cliente, admin, pessoas):
    ids, h = pessoas
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    _enviar(cliente, admin, usuarios_ids=[ids["bruno"]], prioridade="critica", assunto="Comunicado urgente")
    entregue = agora_utc().date()
    SmtpSimulado.enviadas.clear()
    with FabricaSessao() as sessao:
        assert mensageria._lembrar_ciencias(sessao, entregue + timedelta(days=2)) == 0
        assert mensageria._lembrar_ciencias(sessao, entregue + timedelta(days=3)) == 1
    assert SmtpSimulado.enviadas[0][0]["Subject"] == "Lembrete: Comunicado urgente"
    with FabricaSessao() as sessao:
        assert sessao.query(EntregaMensagem).count() == 1


def test_email_no_layout_oficial_com_brasao(cliente, admin, pessoas):
    """O e-mail sai no layout oficial, com o brasão embutido (Content-ID) e o rodapé do SGI SPI."""
    ids, h = pessoas
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    SmtpSimulado.enviadas.clear()
    _enviar(cliente, h["ana"], usuarios_ids=[ids["bruno"]], enviar_email=True)
    mensagem = SmtpSimulado.enviadas[0][0]
    html = mensagem.get_body(("html",)).get_content()
    assert "cid:brasao-spi" in html and "GOVERNO DO ESTADO DE SÃO PAULO" in html and "SGI SPI – Sistema de Gestão Integrada" in html
    imagens = [p for p in mensagem.walk() if p.get_content_type() == "image/png"]
    assert len(imagens) == 1 and imagens[0]["Content-ID"] == "<brasao-spi>" and imagens[0].get_content()[:4] == b"\x89PNG"


def test_marcar_varias_como_lidas_nao_lidas_e_cientes(cliente, admin, pessoas):
    ids, h = pessoas
    for assunto in ("Um", "Dois", "Três"):
        _enviar(cliente, admin, usuarios_ids=[ids["ana"], ids["bruno"]], assunto=assunto)
    ana = cliente.get(URL, headers=h["ana"]).json()["itens"]
    todos = [m["id"] for m in ana]
    assert len(todos) == 3 and cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["nao_lidas"] == 3
    r = cliente.post(f"{URL}/lote", json={"ids": todos, "acao": "lida"}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["atualizadas"] == 3
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["nao_lidas"] == 0
    assert cliente.post(f"{URL}/lote", json={"ids": todos[:2], "acao": "nao_lida"}, headers=h["ana"]).json()["atualizadas"] == 2
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["nao_lidas"] == 2
    assert cliente.post(f"{URL}/lote", json={"ids": todos, "acao": "ciente"}, headers=h["ana"]).json()["atualizadas"] == 3
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 0
    # Mensagens de outra pessoa são ignoradas
    assert cliente.post(f"{URL}/lote", json={"ids": todos, "acao": "lida"}, headers=h["bruno"]).json()["atualizadas"] == 0
    assert cliente.get(f"{URL}/resumo", headers=h["bruno"]).json()["nao_lidas"] == 3


def test_mensagem_aparece_formatada_como_o_email_do_changelog(cliente, admin, pessoas):
    """A prévia e o e-mail usam o layout oficial, com `## título`, `- lista` e `**negrito**` renderizados (e HTML do texto escapado)."""
    ids, h = pessoas
    corpo = "## Novidades\nVeja o **ciente** do superior.\n- primeiro item\n- segundo <b>item</b>"
    r = cliente.post(f"{URL}/previa", json={"assunto": "Mudanças nas férias", "corpo": corpo}, headers=h["ana"])
    assert r.status_code == 200
    html = r.json()["html"]
    assert "<h2" in html and "<strong>ciente</strong>" in html and html.count("<li") == 2
    assert "&lt;b&gt;item&lt;/b&gt;" in html and "data:image/png;base64," in html and "cid:brasao-spi" not in html
    assert "Enviada por Ana da Silva." in html
    # O e-mail enviado carrega o mesmo corpo formatado
    SmtpSimulado.enviadas.clear()
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    _enviar(cliente, admin, usuarios_ids=[ids["ana"]], assunto="Mudanças nas férias", corpo=corpo, enviar_email=True)
    with FabricaSessao() as sessao:
        mensageria.enviar_emails_pendentes(sessao)
    mensagem = next(m for m, _, para, _ in SmtpSimulado.enviadas if para == ["ana@sp.gov.br"])
    html_email = next(parte.get_content() for parte in mensagem.walk() if parte.get_content_type() == "text/html")
    assert "<strong>ciente</strong>" in html_email and html_email.count("<li") == 2
