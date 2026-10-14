# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar os canais das Notificações: catálogo, preferências, despacho, Web Push, não perturbe, resumo, silenciados e obrigatórias.
"""Notificações: catálogo de eventos, preferências por usuário, despacho por e-mail e navegador, resumo, não perturbe, silenciados e obrigatórias."""

import re
import smtplib
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.notificacao_preferencias import InscricaoNavegador
from app.models.setor import MembroSetor, Setor
from app.services import notificacoes
from app.services.notificacoes import catalogo, despacho, navegador, preferencias
from tests.apoio_notificacoes import configurar, ligar_canais
from tests.conftest import cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, SmtpSslSimulado, dados_servidor

URL = "/api/notificacoes"
SP = ZoneInfo("America/Sao_Paulo")


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    """SMTP simulado e Web Push simulado (nada sai pela rede); as chaves VAPID existem só no teste."""
    SmtpSimulado.enviadas, SmtpSimulado.conexoes, SmtpSimulado.recusar_remetente = [], [], False
    monkeypatch.setattr(smtplib, "SMTP", SmtpSimulado)
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslSimulado)
    monkeypatch.setattr(navegador, "configurado", lambda: True)
    pushes: list[tuple[dict, str]] = []
    monkeypatch.setattr(navegador, "_enviar_um", lambda assinatura, dados: pushes.append((assinatura, dados)))
    return pushes


@pytest.fixture
def pushes(_ambiente):
    return _ambiente


@pytest.fixture
def pessoas(cliente, admin):
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    ids = {login: criar_usuario(login, nome_completo=f"{login.title()} da Silva", email=f"{login}@sp.gov.br") for login in ("ana", "bruno", "carla")}
    return ids, {login: cabecalho(cliente, login) for login in ids}


def _notificar(destinatarios, evento="contratos.medicao_concluida", chave=None, **extras):
    with FabricaSessao() as sessao:
        n = notificacoes.notificar(sessao, destinatarios, "Medição concluída", "A medição foi concluída.", chave=chave or f"t:{uuid.uuid4()}", evento=evento, link="/contratos", **extras)
        sessao.commit()
        return n.id if n else None


def _entrega(usuario_id, notificacao_id):
    with FabricaSessao() as sessao:
        return sessao.scalar(select(EntregaNotificacao).where(EntregaNotificacao.destinatario_id == usuario_id, EntregaNotificacao.notificacao_id == notificacao_id))


def _proximo_dia(dia_da_semana: int) -> datetime:
    """Próximo dia (0 = segunda) às 7h de São Paulo, a partir de hoje (as entregas dos testes nascem agora)."""
    hoje = datetime.now(SP)
    adiante = (dia_da_semana - hoje.weekday()) % 7 or 7
    return (hoje + timedelta(days=adiante)).replace(hour=7, minute=0, second=0, microsecond=0)


def _inscrever(cliente, headers, endpoint="https://push.exemplo/abc123456789"):
    corpo = {"endpoint": endpoint, "p256dh": "chave-p256dh-de-teste", "auth": "segredo-auth", "rotulo": "Chrome no Windows"}
    return cliente.post(f"{URL}/navegador/inscricoes", json=corpo, headers=headers)


# --- Catálogo ----------------------------------------------------------------------------------------------------

def test_todo_evento_usado_no_codigo_existe_no_catalogo():
    """Erro de digitação em `evento=` falha aqui, em vez de virar um aviso que ninguém consegue configurar."""
    usados = {}
    for arquivo in Path("app").rglob("*.py"):
        for achado in re.findall(r'evento="([a-z_]+\.[a-z_]+)"', arquivo.read_text(encoding="utf-8")):
            usados.setdefault(achado, arquivo.as_posix())
    assert usados, "nenhum evento encontrado: a busca está errada"
    desconhecidos = {e: a for e, a in usados.items() if e not in catalogo.EVENTOS}
    assert not desconhecidos, f"eventos fora do catálogo: {desconhecidos}"


def test_notificar_recusa_evento_desconhecido(cliente, admin, pessoas):
    ids, _ = pessoas
    with FabricaSessao() as sessao:
        with pytest.raises(notificacoes.ErroNotificacao):
            notificacoes.notificar(sessao, [ids["ana"]], "x", "y", chave="k", evento="contratos.inventado")


# --- Padrão: tudo desmarcado -------------------------------------------------------------------------------------

def test_sem_preferencia_recebe_na_caixa_e_nao_por_canal_externo(cliente, admin, pessoas, pushes):
    ids, h = pessoas
    n = _notificar([ids["ana"]])
    e = _entrega(ids["ana"], n)
    assert (e.canal_email, e.canal_navegador, e.canal_desktop) == (False, False, False)
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 1
    with FabricaSessao() as sessao:
        assert despacho.despachar_pendentes(sessao) == 0
    assert SmtpSimulado.enviadas == [] and pushes == []


def test_matriz_de_preferencias_comeca_desmarcada_e_recusa_canal_indisponivel(cliente, admin, pessoas):
    ids, h = pessoas
    r = cliente.get(f"{URL}/preferencias", headers=h["ana"])
    assert r.status_code == 200
    corpo = r.json()
    eventos = [e for m in corpo["modulos"] for e in m["eventos"]]
    assert eventos and not any(c["ligado"] for e in eventos for c in e["canais"].values())
    assert "sistema.teste" not in [e["chave"] for e in eventos]
    novidades = next(e for e in eventos if e["chave"] == "sistema.novidades")
    assert novidades["canais"]["navegador"]["disponivel"] is False
    # Liga e-mail e navegador em um evento, desktop em outro; a configuração vai junto
    r = cliente.put(f"{URL}/preferencias", json={
        "canais": {"contratos.medicao_concluida": ["email", "navegador"], "tarefas.mencao": ["desktop"]},
        "configuracao": {"frequencia_email": "diario", "silencio_inicio": "19:00", "silencio_fim": "07:00", "silencio_fins_de_semana": True}}, headers=h["ana"])
    assert r.status_code == 200, r.text
    ligados = {(e["chave"], c) for m in r.json()["modulos"] for e in m["eventos"] for c, v in e["canais"].items() if v["ligado"]}
    assert ligados == {("contratos.medicao_concluida", "email"), ("contratos.medicao_concluida", "navegador"), ("tarefas.mencao", "desktop")}
    assert r.json()["configuracao"]["frequencia_email"] == "diario" and r.json()["configuracao"]["silencio_inicio"] == "19:00"
    # Substitui tudo; canal fora do evento, evento inventado e horário quebrado são recusados
    assert cliente.put(f"{URL}/preferencias", json={"canais": {"sistema.novidades": ["navegador"]}}, headers=h["ana"]).status_code == 422
    assert cliente.put(f"{URL}/preferencias", json={"canais": {"x.y": ["email"]}}, headers=h["ana"]).status_code == 422
    assert cliente.put(f"{URL}/preferencias", json={"configuracao": {"silencio_inicio": "19:00"}}, headers=h["ana"]).status_code == 422
    assert cliente.put(f"{URL}/preferencias", json={"canais": {}}, headers=h["ana"]).status_code == 200
    assert not any(c["ligado"] for m in cliente.get(f"{URL}/preferencias", headers=h["ana"]).json()["modulos"] for e in m["eventos"] for c in e["canais"].values())
    assert cliente.get(f"{URL}/preferencias").status_code == 401


# --- Despacho ----------------------------------------------------------------------------------------------------

def test_preferencia_ligada_envia_email_e_push_sem_duplicar_entre_thread_e_timer(cliente, admin, pessoas, pushes, monkeypatch):
    ids, h = pessoas
    ligar_canais([ids["ana"]], canais=("email", "navegador"), eventos=["contratos.medicao_concluida"])
    assert _inscrever(cliente, h["ana"]).status_code == 201
    monkeypatch.setattr(despacho, "modo", lambda: "sincrono")
    _notificar([ids["ana"], ids["bruno"]])
    assert [to[0] for _, _, to, _ in SmtpSimulado.enviadas] == ["ana@sp.gov.br"]
    assert len(pushes) == 1 and pushes[0][0]["endpoint"].startswith("https://push.exemplo/")
    # O timer (rede de segurança) não manda de novo o que o despacho já mandou
    with FabricaSessao() as sessao:
        assert despacho.despachar_pendentes(sessao) == 0
    assert len(SmtpSimulado.enviadas) == 1 and len(pushes) == 1
    # Payload do pop-up: título, texto curto, url, tag = entrega e token do botão Ciente
    carga = __import__("json").loads(pushes[0][1])
    assert carga["titulo"] == "Medição concluída" and carga["url"] == "/contratos" and carga["tag"] == carga["entrega_id"] and carga["token_ciencia"]
    # Rollback: nada sai
    monkeypatch.setattr(despacho, "modo", lambda: "sincrono")
    with FabricaSessao() as sessao:
        notificacoes.notificar(sessao, [ids["ana"]], "Não vai sair", "x", chave="rb", evento="contratos.medicao_concluida")
        sessao.rollback()
    assert len(SmtpSimulado.enviadas) == 1 and len(pushes) == 1


def test_timer_envia_o_pendente_e_so_uma_vez(cliente, admin, pessoas, pushes):
    ids, h = pessoas
    ligar_canais([ids["ana"]], canais=("email",))
    _notificar([ids["ana"]])
    assert SmtpSimulado.enviadas == []
    with FabricaSessao() as sessao:
        assert despacho.despachar_pendentes(sessao) == 1
        assert despacho.despachar_pendentes(sessao) == 0
    assert len(SmtpSimulado.enviadas) == 1
    # A reivindicação não deixa duas execuções enviarem a mesma entrega
    n = _notificar([ids["ana"]])
    e = _entrega(ids["ana"], n)
    with FabricaSessao() as a, FabricaSessao() as b:
        assert despacho._reivindicar(a, e.id, "email_enviado_em") is True
        assert despacho._reivindicar(b, e.id, "email_enviado_em") is False


def test_inscricao_expirada_410_e_apagada_e_falha_comum_conta(cliente, admin, pessoas, pushes, monkeypatch):
    ids, h = pessoas
    ligar_canais([ids["ana"]], canais=("navegador",))
    _inscrever(cliente, h["ana"], "https://push.exemplo/morta-410-123456")
    _inscrever(cliente, h["ana"], "https://push.exemplo/viva-com-falha-1234")

    class Falha(Exception):
        def __init__(self, status):
            super().__init__(f"HTTP {status}")
            self.response = type("R", (), {"status_code": status})()

    def enviar(assinatura, dados):
        raise Falha(410 if "morta" in assinatura["endpoint"] else 500)

    monkeypatch.setattr(navegador, "_enviar_um", enviar)
    n = _notificar([ids["ana"]])
    with FabricaSessao() as sessao:
        despacho.despachar_pendentes(sessao)
        restantes = list(sessao.scalars(select(InscricaoNavegador)))
    assert [i.endpoint for i in restantes] == ["https://push.exemplo/viva-com-falha-1234"] and restantes[0].falhas_seguidas == 1
    assert _entrega(ids["ana"], n).navegador_ok is False
    # Inscrições com 10+ falhas seguidas saem na limpeza diária
    with FabricaSessao() as sessao:
        sessao.query(InscricaoNavegador).update({"falhas_seguidas": 10})
        sessao.commit()
        assert navegador.limpar_inscricoes(sessao) == 1


def test_inscricao_pela_api_remocao_e_navegador_indisponivel(cliente, admin, pessoas, monkeypatch):
    ids, h = pessoas
    r = _inscrever(cliente, h["ana"])
    assert r.status_code == 201 and r.json()["inscricoes"] == 1 and r.json()["aparelhos"][0]["rotulo"] == "Chrome no Windows"
    # Mesmo endpoint não duplica
    assert _inscrever(cliente, h["ana"]).json()["inscricoes"] == 1
    r = cliente.post(f"{URL}/navegador/inscricoes/remover", json={"endpoint": "https://push.exemplo/abc123456789"}, headers=h["ana"])
    assert r.status_code == 200 and r.json()["inscricoes"] == 0
    monkeypatch.setattr(navegador, "configurado", lambda: False)
    assert _inscrever(cliente, h["ana"]).status_code == 409
    situacao = cliente.get(f"{URL}/preferencias", headers=h["ana"]).json()["navegador"]
    assert situacao["disponivel"] is False and situacao["chave_publica_vapid"] is None and situacao["explicacao"]


def test_testar_cada_canal(cliente, admin, pessoas, pushes):
    ids, h = pessoas
    r = cliente.post(f"{URL}/testar", json={"canal": "email"}, headers=h["ana"])
    assert r.json()["enviado"] is True and SmtpSimulado.enviadas[-1][0]["Subject"] == "Teste de notificação"
    assert cliente.post(f"{URL}/testar", json={"canal": "navegador"}, headers=h["ana"]).json()["enviado"] is False  # nenhum navegador inscrito
    _inscrever(cliente, h["ana"])
    assert cliente.post(f"{URL}/testar", json={"canal": "navegador"}, headers=h["ana"]).json()["enviado"] is True and len(pushes) == 1
    # Desktop: uma entrega de teste que o cliente Windows alerta (e que expira sozinha)
    assert cliente.post(f"{URL}/testar", json={"canal": "desktop"}, headers=h["ana"]).json()["enviado"] is True
    legado = cliente.get("/api/mensagens", headers=h["ana"]).json()
    assert legado["total"] == 1 and legado["itens"][0]["assunto"] == "Teste de notificação"


# --- Não perturbe, resumo, silenciados, obrigatórias ------------------------------------------------------------

def test_nao_perturbe_segura_navegador_e_desktop_mas_nao_o_email(cliente, admin, pessoas):
    ids, _ = pessoas
    ligar_canais([ids["ana"]], canais=("email", "navegador", "desktop"), eventos=["contratos.medicao_concluida"])
    configurar(ids["ana"], silencio_inicio=time(19, 0), silencio_fim=time(7, 0), silencio_fins_de_semana=False)
    with FabricaSessao() as sessao:
        def canais(hora, dia=11):
            return preferencias.canais_por_destinatario(sessao, [ids["ana"]], "contratos.medicao_concluida", agora=datetime(2026, 11, dia, hora, 0, tzinfo=SP))[ids["ana"]]

        noite = canais(22)
        assert noite.email and not noite.navegador and not noite.desktop
        madrugada = canais(3)
        assert madrugada.email and not madrugada.navegador
        dia = canais(12)
        assert dia.email and dia.navegador and dia.desktop
    configurar(ids["ana"], silencio_inicio=None, silencio_fim=None, silencio_fins_de_semana=True)
    with FabricaSessao() as sessao:
        sabado = preferencias.canais_por_destinatario(sessao, [ids["ana"]], "contratos.medicao_concluida", agora=datetime(2026, 11, 14, 12, 0, tzinfo=SP))[ids["ana"]]
        segunda = preferencias.canais_por_destinatario(sessao, [ids["ana"]], "contratos.medicao_concluida", agora=datetime(2026, 11, 16, 12, 0, tzinfo=SP))[ids["ana"]]
    assert sabado.email and not sabado.navegador and segunda.navegador


def test_resumo_diario_e_semanal_agrupa_por_modulo_e_nao_repete(cliente, admin, pessoas):
    ids, h = pessoas
    ligar_canais([ids["ana"], ids["bruno"]], canais=("email",))
    configurar(ids["ana"], frequencia_email="diario")
    configurar(ids["bruno"], frequencia_email="semanal")
    _notificar([ids["ana"], ids["bruno"]], "contratos.medicao_concluida")
    _notificar([ids["ana"], ids["bruno"]], "tarefas.mencao")
    with FabricaSessao() as sessao:
        assert despacho.despachar_pendentes(sessao) == 0  # resumo não sai na hora
    assert SmtpSimulado.enviadas == []
    # Um dia que não é segunda-feira: só o resumo diário da Ana
    terca = _proximo_dia(1)
    with FabricaSessao() as sessao:
        assert despacho.enviar_resumos(sessao, terca) == 1
        assert despacho.enviar_resumos(sessao, terca.replace(minute=5)) == 0
    assert [to[0] for _, _, to, _ in SmtpSimulado.enviadas] == ["ana@sp.gov.br"]
    html = SmtpSimulado.enviadas[0][0].get_body(("html",)).get_content()
    assert "Contratos (1)" in html and "Tarefas (1)" in html and SmtpSimulado.enviadas[0][0]["Subject"].startswith("Resumo das suas notificações")
    # Segunda-feira: o semanal do Bruno
    segunda = _proximo_dia(0)
    with FabricaSessao() as sessao:
        assert despacho.enviar_resumos(sessao, segunda) == 1
        assert despacho.enviar_resumos(sessao, segunda.replace(minute=5)) == 0
    assert [to[0] for _, _, to, _ in SmtpSimulado.enviadas] == ["ana@sp.gov.br", "bruno@sp.gov.br"]


def test_silenciar_corta_canais_externos_mas_nao_a_caixa(cliente, admin, pessoas, pushes):
    ids, h = pessoas
    from tests.apoio_contratos import criar_contrato, restringir_contratos

    restringir_contratos(cliente, admin, {ids["ana"]: "MODIFICACAO"})
    contrato = criar_contrato(cliente, admin, equipe={"gestor": ids["ana"]})
    ligar_canais([ids["ana"]], canais=("email",))
    n = _notificar([ids["ana"]], contrato_id=uuid.UUID(contrato["id"]), chave="medicao:1")
    entrega_id = str(_entrega(ids["ana"], n).id)
    assert _entrega(ids["ana"], n).canal_email is True
    r = cliente.post(f"{URL}/silenciar", json={"entrega_id": entrega_id}, headers=h["ana"])
    assert r.status_code == 201 and r.json()["tipo"] == "contrato" and contrato["numero"] in r.json()["rotulo"]
    assert cliente.post(f"{URL}/silenciar", json={"entrega_id": entrega_id}, headers=h["ana"]).json()["id"] == r.json()["id"]  # idempotente
    n2 = _notificar([ids["ana"]], contrato_id=uuid.UUID(contrato["id"]), chave="medicao:2")
    e2 = _entrega(ids["ana"], n2)
    assert (e2.canal_email, e2.canal_navegador, e2.canal_desktop) == (False, False, False)
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] >= 2  # a caixa continua recebendo
    # Aviso sem contrato nem tarefa não pode ser silenciado; a lista aparece nas preferências e dá para voltar a avisar
    solta = _notificar([ids["ana"]], chave="solta:1")
    assert cliente.post(f"{URL}/silenciar", json={"entrega_id": str(_entrega(ids["ana"], solta).id)}, headers=h["ana"]).status_code == 400
    assert cliente.post(f"{URL}/silenciar", json={"entrega_id": entrega_id}, headers=h["bruno"]).status_code == 404
    lista = cliente.get(f"{URL}/preferencias", headers=h["ana"]).json()["silenciados"]
    assert len(lista) == 1
    assert cliente.delete(f"{URL}/silenciados/{lista[0]['id']}", headers=h["ana"]).status_code == 204
    assert cliente.delete(f"{URL}/silenciados/{lista[0]['id']}", headers=h["ana"]).status_code == 404
    n3 = _notificar([ids["ana"]], contrato_id=uuid.UUID(contrato["id"]), chave="medicao:3")
    assert _entrega(ids["ana"], n3).canal_email is True


def test_obrigatorias_ligam_o_canal_e_o_put_do_usuario_nao_remove(cliente, admin, pessoas):
    ids, h = pessoas
    with FabricaSessao() as sessao:
        financeiro = Setor(nome="Financeiro")
        sessao.add(financeiro)
        sessao.flush()
        sessao.add(MembroSetor(setor_id=financeiro.id, usuario_id=ids["bruno"]))
        sessao.commit()
        setor_id = financeiro.id
    # Lista começa vazia; usuário comum não administra (o recurso da ACL existe, sem regra para o Bruno)
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Notificações: obrigatórias", "slug": "notificacoes-obrigatorias"}, headers=admin).json()
    # Na ACL, recurso sem regra fica aberto: só a Carla tem CONTROLE_TOTAL (como a migração faz com a conta root)
    assert cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "CONTROLE_TOTAL", "usuarios_ids": [ids["carla"]], "setores_ids": []}, headers=admin).status_code == 201
    assert cliente.get(f"{URL}/obrigatorias", headers=h["carla"]).status_code == 200
    assert cliente.get(f"{URL}/obrigatorias", headers=admin).json() == []
    assert cliente.get(f"{URL}/obrigatorias", headers=h["bruno"]).status_code == 403
    assert cliente.post(f"{URL}/obrigatorias", json={"evento": "contratos.conferir_retencao", "canal": "email", "setor_id": setor_id}, headers=h["bruno"]).status_code == 403
    r = cliente.post(f"{URL}/obrigatorias", json={"evento": "contratos.conferir_retencao", "canal": "email", "setor_id": setor_id}, headers=admin)
    assert r.status_code == 201 and r.json()["setor_nome"] == "Financeiro" and r.json()["evento_rotulo"] == "Conferir retenção de tributos"
    assert cliente.post(f"{URL}/obrigatorias", json={"evento": "contratos.conferir_retencao", "canal": "email", "setor_id": setor_id}, headers=admin).json()["id"] == r.json()["id"]
    assert cliente.post(f"{URL}/obrigatorias", json={"evento": "sistema.novidades", "canal": "desktop", "setor_id": setor_id}, headers=admin).status_code == 422
    assert cliente.post(f"{URL}/obrigatorias", json={"evento": "tarefas.mencao", "canal": "email"}, headers=admin).status_code == 422
    # O Bruno (do Financeiro) recebe por e-mail sem ter marcado nada; a Carla (fora do setor) não
    n = _notificar([ids["bruno"], ids["carla"]], "contratos.conferir_retencao")
    assert _entrega(ids["bruno"], n).canal_email is True and _entrega(ids["carla"], n).canal_email is False
    # Na tela aparece ligado e travado, e o PUT do usuário não consegue tirar
    def celula():
        corpo = cliente.get(f"{URL}/preferencias", headers=h["bruno"]).json()
        return next(e for m in corpo["modulos"] for e in m["eventos"] if e["chave"] == "contratos.conferir_retencao")["canais"]["email"]

    assert celula() == {"disponivel": True, "ligado": True, "obrigatorio": True}
    assert cliente.put(f"{URL}/preferencias", json={"canais": {"contratos.conferir_retencao": []}}, headers=h["bruno"]).status_code == 200
    assert celula()["ligado"] is True
    assert cliente.delete(f"{URL}/obrigatorias/{r.json()['id']}", headers=admin).status_code == 204
    assert celula() == {"disponivel": True, "ligado": False, "obrigatorio": False}


# --- Pop-up, painel e cliente Windows ----------------------------------------------------------------------------

def test_ciencia_pelo_botao_do_popup(cliente, admin, pessoas):
    ids, h = pessoas
    n = _notificar([ids["ana"]])
    entrega = _entrega(ids["ana"], n)
    token = navegador.gerar_token_ciencia(entrega.id)
    r = cliente.post(f"{URL}/ciencia-por-token", json={"token": token})
    assert r.status_code == 200 and r.json() == {"registrada": True}
    assert cliente.get(f"{URL}/resumo", headers=h["ana"]).json()["pendentes"] == 0
    assert cliente.post(f"{URL}/ciencia-por-token", json={"token": token}).json() == {"registrada": False}
    assert cliente.post(f"{URL}/ciencia-por-token", json={"token": "lixo"}).status_code == 401
    # Um token comum de sessão não vale como token de ciência
    assert cliente.post(f"{URL}/ciencia-por-token", json={"token": h["ana"]["Authorization"].split()[-1]}).status_code == 401


def test_cliente_windows_so_ve_entregas_com_desktop_no_formato_antigo(cliente, admin, pessoas):
    ids, h = pessoas
    _notificar([ids["ana"]], chave="sem-desktop")
    resumo = cliente.get("/api/mensagens/resumo", headers=h["ana"]).json()
    assert resumo["pendentes"] == 0 and resumo["nao_lidas"] == 0 and resumo["janela"] is None
    ligar_canais([ids["ana"]], canais=("desktop",), eventos=["contratos.medicao_concluida"])
    _notificar([ids["ana"]], chave="com-desktop")
    resumo = cliente.get("/api/mensagens/resumo", headers=h["ana"]).json()
    assert resumo["pendentes"] == 1 and resumo["nao_lidas"] == 1
    pagina = cliente.get("/api/mensagens", params={"estado": "pendentes", "pagina": 1, "tamanho_pagina": 30}, headers=h["ana"]).json()
    assert pagina["total"] == 1
    item = pagina["itens"][0]
    # Os campos que o SGI Alertas lê continuam com os nomes de sempre
    assert {"id", "assunto", "prioridade", "categoria", "autor_nome", "link"} <= set(item) and item["alertar_desktop"] is True
    # Na API nova a caixa mostra as duas
    assert cliente.get(URL, headers=h["ana"]).json()["total"] == 2


def test_painel_de_entregas_so_o_root(cliente, admin, pessoas, pushes):
    ids, h = pessoas
    ligar_canais([ids["ana"]], canais=("email", "navegador"))
    _inscrever(cliente, h["ana"])
    _notificar([ids["ana"]])
    with FabricaSessao() as sessao:
        despacho.despachar_pendentes(sessao)
    assert cliente.get(f"{URL}/painel-entregas", headers=h["ana"]).status_code == 403
    painel = cliente.get(f"{URL}/painel-entregas", params={"dias": 7}, headers=admin).json()
    por_canal = {l["canal"]: l for l in painel["por_canal"]}
    assert por_canal["email"]["enviadas"] == 1 and por_canal["navegador"]["enviadas"] == 1 and painel["inscricoes_total"] == 1


def test_caixa_esconde_o_que_foi_resolvido_ha_mais_de_x_meses(cliente, admin, pessoas):
    ids, h = pessoas
    from datetime import timedelta

    from app.core.banco import agora_utc

    n = _notificar([ids["ana"]], chave="velha")
    with FabricaSessao() as sessao:
        e = sessao.scalar(select(EntregaNotificacao).where(EntregaNotificacao.notificacao_id == n))
        e.ciente_em = agora_utc() - timedelta(days=200)
        sessao.commit()
    assert cliente.get(URL, params={"estado": "todas"}, headers=h["ana"]).json()["total"] == 0
    with FabricaSessao() as sessao:  # continua no banco, para auditoria
        assert sessao.query(Notificacao).filter(Notificacao.id == n).count() == 1
