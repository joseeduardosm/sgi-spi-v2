# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a administração e a sincronização dos diretórios LDAP.
"""Testes dos diretórios LDAP: cadastro, teste de conexão, sincronização, login corporativo e permissões.

Usam o AD simulado da fixture `ad` (ldap3 MOCK_SYNC), sem rede.
"""

import uuid

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models import DiretorioLdap, RegistroAuditoria, Usuario
from tests.conftest import cabecalho, dados_diretorio, entrar

URL = "/api/ldap/diretorios"


def _criar(cliente, admin, **alteracoes):
    """Cadastra um diretório pela API e devolve o JSON."""
    r = cliente.post(URL, json=dados_diretorio(**alteracoes), headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


# --- Cadastro -----------------------------------------------------------------

def test_cadastro_cifra_senha_e_nao_a_devolve(cliente, admin, ad):
    """A senha de bind é gravada cifrada e nunca aparece na resposta."""
    corpo = _criar(cliente, admin, ativo=False)
    assert "senha_bind" not in corpo and "senha_bind_cifrada" not in corpo
    with FabricaSessao() as sessao:
        diretorio = sessao.get(DiretorioLdap, uuid.UUID(corpo["id"]))
        assert diretorio.senha_bind_cifrada and "svc-senha" not in diretorio.senha_bind_cifrada


def test_apenas_um_diretorio_ativo(cliente, admin, ad):
    """Ativar um diretório desativa o outro."""
    a = _criar(cliente, admin, nome="A")
    _criar(cliente, admin, nome="B")
    estados = {d["nome"]: d["ativo"] for d in cliente.get(URL, headers=admin).json()}
    assert estados == {"A": False, "B": True}
    cliente.put(f"{URL}/{a['id']}", json=dados_diretorio(nome="A", senha_bind=""), headers=admin)
    estados = {d["nome"]: d["ativo"] for d in cliente.get(URL, headers=admin).json()}
    assert estados == {"A": True, "B": False}


def test_edicao_sem_senha_preserva_a_atual(cliente, admin, ad):
    """Alterar sem mandar senha mantém a senha gravada (o teste de conexão continua funcionando)."""
    d = _criar(cliente, admin, ativo=False)
    r = cliente.put(f"{URL}/{d['id']}", json=dados_diretorio(nome="Novo", ativo=False, senha_bind=None), headers=admin)
    assert r.status_code == 200 and r.json()["nome"] == "Novo"
    assert cliente.post(f"{URL}/{d['id']}/testar", headers=admin).json()["sucesso"] is True


def test_cadastro_exige_senha_e_campos(cliente, admin):
    """Senha vazia ou campo só com espaços são recusados (422)."""
    r = cliente.post(URL, json=dados_diretorio(senha_bind=""), headers=admin)
    assert r.status_code == 422 and r.json()["erros"][0]["campo"] == "senha_bind"
    r = cliente.post(URL, json=dados_diretorio(servidor="  "), headers=admin)
    assert r.status_code == 422


def test_exclusao_e_404(cliente, admin, ad):
    """Diretório excluído passa a responder 404."""
    d = _criar(cliente, admin, ativo=False)
    assert cliente.delete(f"{URL}/{d['id']}", headers=admin).status_code == 204
    r = cliente.get(f"{URL}/{d['id']}", headers=admin)
    assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"


def test_operacoes_registradas_na_auditoria(cliente, admin, ad):
    """Criar, alterar, sincronizar e excluir ficam na auditoria, nessa ordem."""
    d = _criar(cliente, admin, ativo=False)
    cliente.put(f"{URL}/{d['id']}", json=dados_diretorio(ativo=False), headers=admin)
    cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin)
    cliente.delete(f"{URL}/{d['id']}", headers=admin)
    with FabricaSessao() as sessao:
        acoes = [a.acao for a in sessao.scalars(select(RegistroAuditoria).order_by(RegistroAuditoria.id))]
    assert acoes == ["ldap.criar", "ldap.alterar", "ldap.sincronizar", "ldap.excluir"]


# --- Teste de conectividade -----------------------------------------------------

def test_teste_registra_resultado(cliente, admin, ad):
    """Teste bem-sucedido grava data, resultado e limpa o erro."""
    d = _criar(cliente, admin, ativo=False)
    r = cliente.post(f"{URL}/{d['id']}/testar", headers=admin).json()
    assert r["sucesso"] is True and r["latencia_ms"] >= 0
    salvo = cliente.get(f"{URL}/{d['id']}", headers=admin).json()
    assert salvo["ultimo_teste_ok"] is True and salvo["ultimo_teste_em"] and salvo["ultimo_erro"] is None


def test_teste_com_falha_registra_erro(cliente, admin, ad):
    """Servidor fora do ar: o teste falha e o erro fica registrado."""
    d = _criar(cliente, admin, ativo=False, servidor="fora-do-ar")
    r = cliente.post(f"{URL}/{d['id']}/testar", headers=admin).json()
    assert r["sucesso"] is False and "Não foi possível conectar" in r["mensagem"]
    salvo = cliente.get(f"{URL}/{d['id']}", headers=admin).json()
    assert salvo["ultimo_teste_ok"] is False and salvo["ultimo_erro"]


def test_teste_sem_salvar_valida_credencial_e_base_dn(cliente, admin, ad):
    """Teste sem salvar detecta senha errada e Base DN inexistente."""
    assert cliente.post(f"{URL}/testar", json=dados_diretorio(), headers=admin).json()["sucesso"] is True
    ruim = cliente.post(f"{URL}/testar", json=dados_diretorio(senha_bind="errada"), headers=admin).json()
    assert ruim["sucesso"] is False and "conta técnica" in ruim["mensagem"]
    sem_base = cliente.post(f"{URL}/testar", json=dados_diretorio(base_dn="dc=outro,dc=local"), headers=admin).json()
    assert sem_base["sucesso"] is False


# --- Sincronização --------------------------------------------------------------

def test_sincronizacao_cria_atualiza_e_desativa(cliente, admin, ad):
    """1ª sincronização cria as contas; depois, quem sumiu do AD é desativado (o root não é afetado)."""
    ad.adicionar_usuario("maria", "m-senha", "Maria Silva", "maria@spi.local")
    ad.adicionar_usuario("joao", "j-senha", "Joao Souza")
    d = _criar(cliente, admin, ativo=False)

    r = cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin).json()
    assert (r["encontrados"], r["criados"], r["atualizados"], r["desativados"]) == (2, 2, 0, 0)

    ad.remover_usuario("Joao Souza")
    r = cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin).json()
    assert (r["encontrados"], r["criados"], r["atualizados"], r["desativados"]) == (1, 0, 1, 1)

    with FabricaSessao() as sessao:
        usuarios = {u.login: u for u in sessao.scalars(select(Usuario))}
    assert usuarios["maria"].origem == "ldap" and usuarios["maria"].hash_senha is None
    assert usuarios["maria"].email == "maria@spi.local" and usuarios["maria"].id_externo
    assert usuarios["joao"].ativo is False
    assert usuarios["root"].ativo is True


def test_sincronizacao_preserva_conta_local_homonima(cliente, admin, ad):
    """Pessoa do AD com o mesmo login de uma conta local (root) é ignorada."""
    ad.adicionar_usuario("root", "qualquer", "Root Corporativo")
    d = _criar(cliente, admin, ativo=False)
    r = cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin).json()
    assert r["ignorados"] == 1 and r["criados"] == 0
    with FabricaSessao() as sessao:
        root = sessao.scalar(select(Usuario).where(Usuario.login == "root"))
    assert root.origem == "local" and root.diretorio_id is None and root.superusuario


def test_sincronizacao_com_diretorio_fora_do_ar_nao_altera_usuarios(cliente, admin, ad):
    """Com o AD fora do ar, a sincronização responde 503 e não mexe em ninguém."""
    d = _criar(cliente, admin, ativo=False, servidor="fora-do-ar")
    r = cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin)
    assert r.status_code == 503 and "Nenhum usuário foi alterado" in r.json()["detalhe"]
    assert r.json()["codigo"] == "servico_indisponivel"


def test_conta_desativada_no_ad_fica_inativa(cliente, admin, ad):
    """Conta desativada no AD entra no portal como inativa."""
    ad.adicionar_usuario("ana", "a-senha", "Ana", desativado=True)
    d = _criar(cliente, admin, ativo=False)
    cliente.post(f"{URL}/{d['id']}/sincronizar", headers=admin)
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Usuario).where(Usuario.login == "ana")).ativo is False


# --- Login corporativo --------------------------------------------------------

def test_login_ldap_cria_conta_de_representacao(cliente, admin, ad):
    """O 1º login corporativo cria a conta de representação; senha errada dá 401."""
    ad.adicionar_usuario("maria", "m-senha", "Maria Silva", "maria@spi.local")
    _criar(cliente, admin)  # ativo
    r = cliente.post("/api/autenticacao/login", json={"login": "maria", "senha": "m-senha"})
    assert r.status_code == 200
    usuario = r.json()["usuario"]
    assert usuario["login"] == "maria" and usuario["origem"] == "ldap" and usuario["papeis"] == []
    assert cliente.post("/api/autenticacao/login", json={"login": "maria", "senha": "errada"}).status_code == 401


def test_login_por_user_principal_name(cliente, admin, ad):
    """Login também funciona no formato usuario@dominio."""
    ad.adicionar_usuario("maria", "m-senha", "Maria Silva")
    _criar(cliente, admin)
    r = cliente.post("/api/autenticacao/login", json={"login": "maria@spi.local", "senha": "m-senha"})
    assert r.status_code == 200 and r.json()["usuario"]["login"] == "maria"


def test_login_conta_desativada_no_ad_recusado(cliente, admin, ad):
    """Conta desativada no AD não consegue entrar."""
    ad.adicionar_usuario("ana", "a-senha", "Ana", desativado=True)
    _criar(cliente, admin)
    assert cliente.post("/api/autenticacao/login", json={"login": "ana", "senha": "a-senha"}).status_code == 401


def test_ldap_indisponivel_permite_login_local(cliente, admin, ad):
    """Com o AD fora do ar, a conta local continua entrando."""
    _criar(cliente, admin, servidor="fora-do-ar")
    assert cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "senha-teste"}).status_code == 200


def test_identidade_ldap_nunca_assume_superusuario(cliente, admin, ad):
    """Uma identidade do AD com o login do superusuário nunca assume essa conta."""
    ad.adicionar_usuario("root", "senha-do-ad", "Impostor")
    _criar(cliente, admin)
    assert cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "senha-do-ad"}).status_code == 401
    assert cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "senha-teste"}).status_code == 200


def test_conta_local_homonima_vira_local_ldap(cliente, admin, ad):
    """Conta local com o mesmo login de uma pessoa do AD passa a aceitar as duas senhas."""
    import bcrypt

    with FabricaSessao() as sessao:
        sessao.add(Usuario(login="carlos", hash_senha=bcrypt.hashpw(b"local", bcrypt.gensalt(4)).decode(), nome_completo="Carlos"))
        sessao.commit()
    ad.adicionar_usuario("carlos", "c-ad", "Carlos Corporativo")
    d = _criar(cliente, admin, ativo=False)
    cliente.put(f"{URL}/{d['id']}", json=dados_diretorio(), headers=admin)  # ativa
    r = cliente.post("/api/autenticacao/login", json={"login": "carlos", "senha": "c-ad"})
    assert r.status_code == 200 and r.json()["usuario"]["origem"] == "local_ldap"
    # a senha local continua valendo como contingência
    assert cliente.post("/api/autenticacao/login", json={"login": "carlos", "senha": "local"}).status_code == 200


# --- Autorização ----------------------------------------------------------------

def test_somente_superroot_administra(cliente, admin, ad):
    """Usuário comum recebe 403 e sem token 401 na administração LDAP."""
    ad.adicionar_usuario("maria", "m-senha", "Maria Silva")
    _criar(cliente, admin)
    maria = {"Authorization": f"Bearer {entrar(cliente, 'maria', 'm-senha')}"}
    assert cliente.get(URL, headers=maria).status_code == 403
    assert cliente.get(URL).status_code == 401


def test_diagnostico_de_login(cliente, admin, ad):
    """O diagnóstico encontra logins existentes e informa quando não existem."""
    ad.adicionar_usuario("maria", "m-senha", "Maria Silva")
    d = _criar(cliente, admin, ativo=False)
    r = cliente.get(f"{URL}/{d['id']}/diagnosticar", params={"login": "maria"}, headers=admin).json()
    assert r["encontrado"] is True and r["login"] == "maria"
    r = cliente.get(f"{URL}/{d['id']}/diagnosticar", params={"login": "ninguem"}, headers=admin).json()
    assert r["encontrado"] is False


def test_cabecalho_de_usuario_comum_funciona(cliente, ad):
    """Usuário local comum consegue consultar a própria sessão."""
    from tests.conftest import criar_usuario

    criar_usuario("comum")
    assert cliente.get("/api/autenticacao/sessao", headers=cabecalho(cliente, "comum")).status_code == 200
