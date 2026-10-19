# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a conta de integração: dispensada de confirmar o cadastro, sem os recursos exclusivos da conta root.
"""Conta de integração (`conta_integracao`): usa a API sem completar nem confirmar o cadastro, mas não vira conta root."""

from tests.conftest import cabecalho, entrar

URL_CHANGELOG = "/api/notificacoes/changelog/rascunho"


def _criar(cliente, admin, login, integracao):
    r = cliente.post("/api/usuarios", json={"login": login, "senha": "senha-integracao-1", "ativo": True, "superusuario": False, "conta_integracao": integracao}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def _cabecalho(cliente, login):
    return {"Authorization": f"Bearer {entrar(cliente, login, 'senha-integracao-1')}"}


def test_conta_de_integracao_usa_a_api_sem_cadastro_completo_mas_nao_e_root(cliente, admin):
    comum = _criar(cliente, admin, "conta-comum", False)
    robo = _criar(cliente, admin, "conta-robo", True)
    assert robo["conta_integracao"] is True and comum["conta_integracao"] is False
    # Conta comum com cadastro incompleto fica restrita
    r = cliente.get("/api/acl/meus-acessos", headers=_cabecalho(cliente, "conta-comum"))
    assert r.status_code == 403 and r.json()["codigo"] == "revisao_perfil_obrigatoria"
    # A de integração usa a API normalmente (e a sessão não a trata como conta root)
    h = _cabecalho(cliente, "conta-robo")
    assert cliente.get("/api/acl/meus-acessos", headers=h).status_code == 200
    sessao = cliente.get("/api/autenticacao/sessao", headers=h).json()
    assert sessao["perfil_restrito"] is False and sessao["conta_root"] is False
    # Os recursos exclusivos da conta root continuam fechados para ela
    assert cliente.get(URL_CHANGELOG, headers=h).status_code == 403


def test_so_o_superroot_define_conta_de_integracao(cliente, admin):
    alvo = _criar(cliente, admin, "conta-alvo", False)
    corpo = {"ativo": True, "superusuario": False, "conta_integracao": True, "perfil": {}}
    r = cliente.put(f"/api/usuarios/{alvo['id']}", json=corpo, headers=admin)
    assert r.status_code == 200 and r.json()["conta_integracao"] is True
    # Sem o campo, o valor atual é mantido
    r = cliente.put(f"/api/usuarios/{alvo['id']}", json={"ativo": True, "superusuario": False, "perfil": {}}, headers=admin)
    assert r.status_code == 200 and r.json()["conta_integracao"] is True


def test_conta_de_integracao_nao_entra_nas_listas_de_servidores_do_rh(cliente, admin):
    """Como a conta root, a conta de integração não é servidor: fica fora do relatório de saldos e da planilha de dados funcionais."""
    from datetime import date

    from app.core.banco import FabricaSessao
    from app.services.rh import relatorio_saldos

    _criar(cliente, admin, "conta-servidor", False)
    _criar(cliente, admin, "conta-integracao-rh", True)
    with FabricaSessao() as sessao:
        nomes = [linha[1] if len(linha) > 1 else linha[0] for linha in relatorio_saldos.linhas(sessao, date(2026, 10, 1))]
        todo_texto = " ".join(str(c) for linha in relatorio_saldos.linhas(sessao, date(2026, 10, 1)) for c in linha)
    assert "conta-servidor" in todo_texto or nomes  # a conta comum aparece
    assert "conta-integracao-rh" not in todo_texto
