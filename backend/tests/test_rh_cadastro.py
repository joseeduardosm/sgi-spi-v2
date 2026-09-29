# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a atualização cadastral mensal validada pela CGP (Módulo RH, funcionalidade 1).
"""Atualização cadastral: revisão mensal, superior obrigatório sem ciclos, pendências, validação e recusa pela CGP."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.banco import FabricaSessao, agora_utc
from app.models.usuario import Usuario
from app.services import servico_perfil
from app.tarefas import mensageria
from tests.apoio_rh import criar_cgp, funcionais, simular_smtp
from tests.conftest import PERFIL_COMPLETO, cabecalho, criar_usuario
from tests.test_smtp import SmtpSimulado, dados_servidor

PERFIL = "/api/autenticacao/perfil"


@pytest.fixture(autouse=True)
def _smtp(monkeypatch):
    simular_smtp(monkeypatch)


@pytest.fixture
def pessoas(cliente, admin):
    ids = {
        "chefe": criar_usuario("chefe", nome_completo="Chefe Silva", email="chefe@sp.gov.br"),
        "ana": criar_usuario("ana", nome_completo="Ana Souza", email="ana@sp.gov.br"),
        "rh": criar_usuario("rh", nome_completo="Rita RH", email="rh@sp.gov.br"),
    }
    criar_cgp(ids["rh"])
    assert cliente.post("/api/smtp/servidores", json=dados_servidor(), headers=admin).status_code == 201
    return ids, {k: cabecalho(cliente, k) for k in ids}


def _perfil(**extras):
    """Perfil atual da Ana (sem mudanças) com as alterações informadas."""
    return {**PERFIL_COMPLETO, "nome_completo": "Ana Souza", "email": "ana@sp.gov.br", **extras}


def test_revisao_vence_na_virada_do_mes(cliente):
    uid = criar_usuario("mensal")
    fuso = ZoneInfo("America/Sao_Paulo")
    with FabricaSessao() as sessao:
        usuario = sessao.get(Usuario, uid)
        agora = agora_utc().astimezone(fuso)
        # Confirmado no dia 1º deste mês: vale; no último dia do mês anterior: vencido
        usuario.perfil_revisado_em = agora.replace(day=1, hour=0, minute=5)
        assert not servico_perfil.revisao_vencida(usuario)
        usuario.perfil_revisado_em = agora.replace(day=1, hour=0, minute=5) - timedelta(minutes=10)
        assert servico_perfil.revisao_vencida(usuario)


def test_superior_obrigatorio_proprio_e_ciclo(cliente, pessoas):
    ids, h = pessoas
    r = cliente.put(PERFIL, json=_perfil(), headers=h["ana"])
    assert r.status_code == 400 and "superior imediato" in r.json()["detalhe"]
    r = cliente.put(PERFIL, json=_perfil(gestor_id=ids["ana"]), headers=h["ana"])
    assert r.status_code == 400 and "próprio superior" in r.json()["detalhe"]
    # Ana é superior do chefe (em vigor): o chefe não pode ser superior da Ana
    with FabricaSessao() as sessao:
        sessao.get(Usuario, ids["chefe"]).gestor_id = ids["ana"]
        sessao.commit()
    r = cliente.put(PERFIL, json=_perfil(gestor_id=ids["chefe"]), headers=h["ana"])
    assert r.status_code == 400 and "já é superior" in r.json()["detalhe"]
    # A CGP pode dispensar o topo da hierarquia
    funcionais(ids["ana"], sem_superior=True)
    assert cliente.get(PERFIL, headers=h["ana"]).json()["superior_obrigatorio"] is False
    assert cliente.put(PERFIL, json=_perfil(), headers=h["ana"]).status_code == 200


def test_alteracao_fica_pendente_ate_a_validacao(cliente, pessoas):
    ids, h = pessoas
    r = cliente.put(PERFIL, json=_perfil(gestor_id=ids["chefe"], cargo="Coordenadora"), headers=h["ana"])
    assert r.status_code == 200 and r.json()["perfil_restrito"] is False
    perfil = cliente.get(PERFIL, headers=h["ana"]).json()
    # Os valores em vigor continuam os anteriores
    assert perfil["cargo"] == "Analista" and perfil["gestor_id"] is None
    assert perfil["situacao_campos"]["cargo"]["pendente"] is True and perfil["situacao_campos"]["cargo"]["valor_proposto"] == "Coordenadora"
    assert perfil["situacao_campos"]["gestor_id"]["valor_proposto_rotulo"] == "Chefe Silva"
    # A CGP recebe o aviso por e-mail (fila dos avisos automáticos)
    SmtpSimulado.enviadas.clear()
    with FabricaSessao() as sessao:
        assert mensageria.enviar_emails_pendentes(sessao) == 1
    mensagem, _, para, _ = SmtpSimulado.enviadas[0]
    assert para == ["rh@sp.gov.br"] and mensagem["Subject"] == "Ana Souza alterou seu cadastro e aguarda validação da CGP"
    # Mandar de novo o mesmo valor não duplica; voltar ao valor em vigor descarta a pendência
    cliente.put(PERFIL, json=_perfil(gestor_id=ids["chefe"], cargo="Coordenadora"), headers=h["ana"])
    pendentes = cliente.get("/api/rh/cadastro/pendencias", headers=h["rh"]).json()
    assert [a["campo"] for a in pendentes[0]["alteracoes"]] == ["cargo", "gestor_id"]
    cliente.put(PERFIL, json=_perfil(gestor_id=ids["chefe"]), headers=h["ana"])
    pendentes = cliente.get("/api/rh/cadastro/pendencias", headers=h["rh"]).json()
    assert [a["campo"] for a in pendentes[0]["alteracoes"]] == ["gestor_id"]


def test_validar_e_recusar_com_correcao(cliente, pessoas):
    ids, h = pessoas
    cliente.put(PERFIL, json=_perfil(gestor_id=ids["chefe"], ramal="9999"), headers=h["ana"])
    pendentes = {a["campo"]: a["id"] for a in cliente.get("/api/rh/cadastro/pendencias", headers=h["rh"]).json()[0]["alteracoes"]}
    # Quem não é da CGP não valida
    assert cliente.post(f"/api/rh/cadastro/alteracoes/{pendentes['gestor_id']}/validar", headers=h["ana"]).json()["codigo"] == "sem_permissao"
    r = cliente.post(f"/api/rh/cadastro/alteracoes/{pendentes['gestor_id']}/validar", headers=h["rh"])
    assert r.status_code == 200 and r.json()["perfil"]["gestor_id"] == "Chefe Silva"
    # Recusa exige justificativa; a correção passa a valer e o usuário recebe e-mail
    url = f"/api/rh/cadastro/alteracoes/{pendentes['ramal']}/recusar"
    assert cliente.post(url, json={"justificativa": "", "valor_corrigido": "1111"}, headers=h["rh"]).status_code == 422
    r = cliente.post(url, json={"justificativa": "Ramal inexistente na central.", "valor_corrigido": "1111"}, headers=h["rh"])
    assert r.status_code == 200 and r.json()["perfil"]["ramal"] == "1111" and r.json()["pendentes"] == []
    historico = r.json()["historico"]
    assert {(a["campo"], a["status"], a["analisada_por_nome"]) for a in historico} == {("gestor_id", "validada", "Rita RH"), ("ramal", "recusada", "Rita RH")}
    perfil = cliente.get(PERFIL, headers=h["ana"]).json()
    assert perfil["ramal"] == "1111" and perfil["situacao_campos"]["ramal"]["corrigido"] is True
    assert perfil["situacao_campos"]["gestor_id"]["validado_por"] == "Rita RH"
    SmtpSimulado.enviadas.clear()
    with FabricaSessao() as sessao:
        mensageria.enviar_emails_pendentes(sessao)
    recusa = next(m for m, _, para, _ in SmtpSimulado.enviadas if para == ["ana@sp.gov.br"])
    assert recusa["Subject"] == "Alteração do seu cadastro recusada: Ramal"
    assert "Ramal inexistente na central." in recusa.get_body(("plain",)).get_content()


def test_dados_funcionais_so_para_cgp(cliente, pessoas):
    ids, h = pessoas
    url = f"/api/rh/cadastro/usuarios/{ids['ana']}"
    assert cliente.get(url, headers=h["ana"]).status_code == 403
    with FabricaSessao() as sessao:
        sessao.get(Usuario, ids["ana"]).gestor_id = ids["chefe"]
        sessao.commit()
    detalhe = cliente.get(url, headers=h["rh"]).json()
    assert detalhe["funcionais"]["autorizador_sugerido_id"] == ids["chefe"]
    corpo = {"autorizador_id": ids["chefe"], "substituto_id": None, "sem_superior": False, "exercicio": 2026, "saldo_ferias_dias": 30, "saldo_lp_dias": 90}
    r = cliente.put(f"{url}/funcionais", json=corpo, headers=h["rh"])
    assert r.status_code == 200 and r.json()["funcionais"]["autorizador_nome"] == "Chefe Silva"
    assert cliente.put(f"{url}/funcionais", json={**corpo, "autorizador_id": ids["ana"]}, headers=h["rh"]).status_code == 400
    # Os campos da CGP não aparecem no perfil do usuário
    perfil = cliente.get(PERFIL, headers=h["ana"]).json()
    assert "saldo_ferias_dias" not in perfil and "autorizador_id" not in perfil
    assert cliente.get("/api/rh/papeis", headers=h["chefe"]).json() == {"cgp": False, "autorizador": True}
    assert cliente.get("/api/rh/papeis", headers=h["rh"]).json()["cgp"] is True


def test_jornada_horarios_e_documentos_so_para_a_cgp(cliente, pessoas):
    ids, h = pessoas
    url = f"/api/rh/cadastro/usuarios/{ids['ana']}/funcionais"
    corpo = {
        "autorizador_id": ids["chefe"], "sem_superior": False, "jornada_semanal_horas": 40, "regime_plantao": False,
        "horario_trabalho_inicio": "09:00", "horario_trabalho_fim": "18:00", "horario_estudante": True,
        "intervalo_inicio": "12:00", "intervalo_fim": "13:00", "rg_cin": " 12.345.678-9 ", "rs_pv": "1.234.567/8",
    }
    assert cliente.put(url, json=corpo, headers=h["ana"]).status_code == 403
    r = cliente.put(url, json=corpo, headers=h["rh"])
    assert r.status_code == 200, r.text
    f = r.json()["funcionais"]
    assert (f["jornada_semanal_horas"], f["horario_trabalho_inicio"], f["horario_trabalho_fim"]) == (40, "09:00", "18:00")
    assert (f["intervalo_inicio"], f["intervalo_fim"], f["horario_estudante"], f["regime_plantao"]) == ("12:00", "13:00", True, False)
    assert (f["rg_cin"], f["rs_pv"]) == ("12.345.678-9", "1.234.567/8")
    # Plantão noturno: o fim pode ser menor que o início
    assert cliente.put(url, json={**corpo, "regime_plantao": True, "horario_trabalho_inicio": "19:00", "horario_trabalho_fim": "07:00"},
                       headers=h["rh"]).status_code == 200
    # Regras: pares completos, intervalo crescente, jornada 1–80, documento só com caracteres válidos
    for erro in ({"horario_trabalho_fim": None}, {"intervalo_fim": "11:00"}, {"jornada_semanal_horas": 90}, {"rg_cin": "12<script>"}):
        assert cliente.put(url, json={**corpo, **erro}, headers=h["rh"]).status_code == 422, erro
    # Nada disso aparece no perfil do próprio usuário
    perfil = cliente.get(PERFIL, headers=h["ana"]).json()
    assert "rg_cin" not in str(perfil) and "jornada_semanal_horas" not in str(perfil)


def test_validacao_em_lote(cliente, pessoas):
    from app.models.rh import AlteracaoCadastral

    ids, h = pessoas
    with FabricaSessao() as sessao:
        alteracoes = [
            AlteracaoCadastral(usuario_id=ids["ana"], campo="departamento", valor_anterior="", valor_proposto="Diretoria A", status="pendente",
                               solicitada_por_nome="Ana"),
            AlteracaoCadastral(usuario_id=ids["ana"], campo="ramal", valor_anterior="1234", valor_proposto="5678", status="pendente",
                               solicitada_por_nome="Ana"),
            AlteracaoCadastral(usuario_id=ids["chefe"], campo="departamento", valor_anterior="", valor_proposto="Diretoria B", status="validada",
                               solicitada_por_nome="Chefe"),
        ]
        sessao.add_all(alteracoes)
        sessao.commit()
        lote = [str(a.id) for a in alteracoes]
    url = "/api/rh/cadastro/alteracoes/validar-lote"
    assert cliente.post(url, json={"ids": lote}, headers=h["ana"]).status_code == 403
    r = cliente.post(url, json={"ids": lote}, headers=h["rh"])
    assert r.status_code == 200, r.text
    # As duas pendentes valem; a já analisada volta em "erros" sem impedir as outras
    assert r.json()["validadas"] == 2 and [e["id"] for e in r.json()["erros"]] == [lote[2]]
    with FabricaSessao() as sessao:
        ana = sessao.get(Usuario, ids["ana"])
        assert (ana.departamento, ana.ramal) == ("Diretoria A", "5678")
    assert cliente.post(url, json={"ids": []}, headers=h["rh"]).status_code == 422
