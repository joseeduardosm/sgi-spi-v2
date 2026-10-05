# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a abertura de chamado pelo SGI no GLPI (GLPI simulado) e a configuração da integração.
"""Chamados: ACL aberta a todos, conteúdo com os dados do cadastro, solicitante no GLPI, limites, erros e segredos."""

import json

import httpx
import pytest

from app.services.glpi import cliente_glpi
from tests.conftest import cabecalho, criar_usuario

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
CONFIG = "/api/integracao-glpi"
CHAMADOS = "/api/chamados"


def abrir_chamado(cliente, h, assunto, descricao, arquivos=(), local_id=38):
    """POST multipart: `dados` (JSON) e os `arquivos` [(nome, conteúdo, tipo)]."""
    return cliente.post(CHAMADOS, data={"dados": json.dumps({"assunto": assunto, "descricao": descricao, "local_id": local_id})},
                        files=[("arquivos", a) for a in arquivos] or None, headers=h)


class GlpiSimulado:
    """GLPI de mentira: guarda as chamadas e responde como a API REST."""

    def __init__(self) -> None:
        self.chamadas: list[httpx.Request] = []
        self.usuarios = {"fulano": 77, "xfulano": 99}
        self.emails: dict[str, int] = {}
        self.proximo = 1500
        self.falhar_criacao = False
        self.falhar_anexo = False
        self.multipart: list[httpx.Request] = []

    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        self.chamadas.append(requisicao)
        caminho = requisicao.url.path
        if caminho.endswith("/initSession"):
            if requisicao.headers.get("Authorization") != "user_token USER123":
                return httpx.Response(401, json=["ERROR_GLPI_LOGIN", "credenciais"])
            return httpx.Response(200, json={"session_token": "SESSAO"})
        if caminho.endswith("/killSession"):
            return httpx.Response(200)
        if caminho.endswith("/search/Location"):
            return httpx.Response(200, json={"totalcount": 2, "data": [{"1": "05º Andar > Lado B", "2": 38}, {"1": "00 - Térreo", "2": 1}]})
        if caminho.endswith("/search/User"):
            parametros = dict(requisicao.url.params)
            valor, campo = parametros["criteria[0][value]"], parametros["criteria[0][field]"]
            base = self.emails if campo == "5" else self.usuarios
            # Como o GLPI real: "contains" devolve também parecidos (o cliente precisa exigir o idêntico)
            dados = [{campo: chave, "2": id_} for chave, id_ in base.items() if valor.lower() in chave.lower()]
            if parametros["criteria[0][searchtype]"] != "contains":
                dados = []
            return httpx.Response(200, json={"totalcount": len(dados), "data": dados} if dados else {"totalcount": 0})
        if caminho.endswith("/Ticket"):
            if self.falhar_criacao:
                return httpx.Response(400, json=["ERROR_JSON_PAYLOAD_INVALID", "ruim"])
            if "multipart" in requisicao.headers.get("content-type", ""):
                # Com anexos: o GLPI recebe o manifesto (JSON com `_filename`) e os arquivos na mesma requisição
                if self.falhar_anexo:
                    return httpx.Response(400, json=["ERROR_GLPI_ADD", "tipo não permitido"])
                self.multipart.append(requisicao)
            self.proximo += 1
            return httpx.Response(201, json={"id": self.proximo, "message": "Item adicionado"})
        return httpx.Response(404)

    def ticket(self) -> dict:
        corpo = [c for c in self.chamadas if c.url.path.endswith("/Ticket")][-1]
        if "multipart" in corpo.headers.get("content-type", ""):
            texto = corpo.content.decode("latin-1")
            inicio = texto.index('{"input"')
            return json.JSONDecoder().raw_decode(texto[inicio:])[0]["input"]
        return json.loads(corpo.content)["input"]


@pytest.fixture
def glpi(monkeypatch):
    simulado = GlpiSimulado()
    original = cliente_glpi.ClienteGlpi.__init__

    def com_transporte(self, url_base, app_token, user_token, transporte=None):
        original(self, url_base, app_token, user_token, httpx.MockTransport(simulado))

    monkeypatch.setattr(cliente_glpi.ClienteGlpi, "__init__", com_transporte)
    return simulado


@pytest.fixture
def configurada(cliente, admin):
    r = cliente.put(CONFIG, json={"ativo": True, "url_base": "https://glpi.exemplo.gov.br", "app_token": "APP123", "user_token": "USER123"}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def _perfil(login="fulano", **extras):
    """Usuário com o perfil completo; os argumentos sobrescrevem campos do cadastro."""
    dados = dict(nome_completo="Fulano de Tal", email="fulano@sp.gov.br", ramal="8123", departamento="Setor X", andar="5", predio="A", celular="")
    dados.update(extras)
    return criar_usuario(login, **dados)


def test_configuracao_nao_expoe_tokens_e_so_o_superroot_altera(cliente, admin):
    _perfil()
    comum = cabecalho(cliente, "fulano")
    assert cliente.get(CONFIG, headers=comum).status_code == 403
    assert cliente.put(CONFIG, json={"ativo": True, "url_base": "https://glpi.exemplo.gov.br"}, headers=comum).status_code == 403
    r = cliente.put(CONFIG, json={"ativo": True, "url_base": "https://glpi.exemplo.gov.br/", "app_token": "APP123", "user_token": "USER123"}, headers=admin)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["url_base"] == "https://glpi.exemplo.gov.br" and corpo["possui_user_token"] and corpo["possui_app_token"] and corpo["configurada"]
    assert "USER123" not in r.text and "APP123" not in r.text
    # Salvar sem tokens preserva os gravados
    r = cliente.put(CONFIG, json={"ativo": False, "url_base": "https://glpi.exemplo.gov.br"}, headers=admin)
    assert r.json()["possui_user_token"] and r.json()["ativo"] is False


def test_testar_conexao(cliente, admin, glpi, configurada):
    assert cliente.post(f"{CONFIG}/testar", headers=admin).json()["sucesso"] is True
    # Token errado: o GLPI recusa e a mensagem é curta
    cliente.put(CONFIG, json={"ativo": True, "url_base": "https://glpi.exemplo.gov.br", "user_token": "ERRADO"}, headers=admin)
    r = cliente.post(f"{CONFIG}/testar", headers=admin).json()
    assert r["sucesso"] is False and "credenciais" in r["mensagem"]


def test_integracao_desligada_devolve_503(cliente, glpi):
    _perfil()
    r = abrir_chamado(cliente, cabecalho(cliente, "fulano"), "Sem rede", "Meu computador está sem rede.")
    assert r.status_code == 503 and r.json()["codigo"] == "integracao_desativada"


def test_todo_usuario_abre_chamado_com_os_dados_do_cadastro(cliente, admin, glpi, configurada):
    gestor = criar_usuario("chefe", nome_completo="Chefe Silva")
    _perfil(gestor_id=gestor, celular="(11) 99999-0000")
    h = cabecalho(cliente, "fulano")
    dados = cliente.get(f"{CHAMADOS}/solicitante", headers=h).json()
    assert dados == {"nome": "Fulano de Tal", "setor": "Setor X", "superior_imediato": "Chefe Silva", "email": "fulano@sp.gov.br",
                     "telefone": "8123", "celular": "(11) 99999-0000", "andar_lado": "5º andar - A", "aguardando_validacao": []}
    r = abrir_chamado(cliente, h, "  Sem rede  ", "Meu computador <b>não</b> conecta.\nJá reiniciei.")
    assert r.status_code == 201, r.text
    resposta = r.json()
    assert resposta["glpi_id"] == 1501 and resposta["url"] == "https://glpi.exemplo.gov.br/front/ticket.form.php?id=1501" and resposta["assunto"] == "Sem rede"
    ticket = glpi.ticket()
    # Como o formulário "Informática" do GLPI: título com prefixo, requerente, grupo atribuído, SLAs, localização, modelo e sem categoria
    assert ticket["name"] == "Informática | Sem rede" and ticket["_users_id_requester"] == 77 and ticket["users_id_recipient"] == 77
    assert ticket["_users_id_requester_notif"] == {"use_notification": [1], "alternative_email": [""]}
    assert ticket["type"] == 1 and ticket["urgency"] == 3 and ticket["impact"] == 3 and ticket["requesttypes_id"] == 1 and "itilcategories_id" not in ticket
    assert ticket["_groups_id_assign"] == 4 and ticket["slas_id_tto"] == 2 and ticket["slas_id_ttr"] == 1 and ticket["tickettemplates_id"] == 1
    assert ticket["locations_id"] == 38 and ticket["entities_id"] == 0
    html = ticket["content"]
    assert html.startswith("<p><b>1) Assunto</b>: Sem rede<br><b>2) Descrição de Problema</b>: <p>Meu computador &lt;b&gt;não&lt;/b&gt; conecta.</p>\n<p>Já reiniciei.</p>")
    assert "<b>3) Local do Problema</b>: 05º Andar &gt; Lado B<br></p>" in html
    # Descrição escapada, dados do cadastro, celular (preenchido) e a assinatura no fim
    assert "&lt;b&gt;não&lt;/b&gt;" in html and "<b>não</b>" not in html
    for esperado in ("Fulano de Tal", "Setor X", "Chefe Silva", "fulano@sp.gov.br", "8123", "(11) 99999-0000", "5º andar - A"):
        assert esperado in html
    assert html.rstrip().endswith("<p><i>Aberto pelo SGI</i></p>")
    # Sessão sempre encerrada e meus chamados listados
    assert glpi.chamadas[-1].url.path.endswith("/killSession")
    assert [c["glpi_id"] for c in cliente.get(CHAMADOS, headers=h).json()["itens"]] == [1501]


def test_celular_vazio_nao_aparece_e_solicitante_por_email_ou_sem_cadastro(cliente, admin, glpi, configurada):
    _perfil("sicrano", nome_completo="Sicrano", email="sicrano@sp.gov.br")
    h = cabecalho(cliente, "sicrano")
    # Não existe no GLPI pelo login, mas existe pelo e-mail
    glpi.emails["sicrano@sp.gov.br"] = 88
    assert abrir_chamado(cliente, h, "Teste um", "Descrição do teste um").status_code == 201
    ticket = glpi.ticket()
    assert ticket["_users_id_requester"] == 88 and "Celular" not in ticket["content"]
    # Sem cadastro no GLPI: e-mail alternativo e aviso no conteúdo
    glpi.emails.clear(); glpi.chamadas.clear()
    assert abrir_chamado(cliente, h, "Teste dois", "Descrição do teste dois").status_code == 201
    ticket = glpi.ticket()
    assert ticket["_users_id_requester"] == 0 and ticket["_users_id_requester_notif"]["alternative_email"] == ["sicrano@sp.gov.br"]
    assert "sem cadastro no GLPI" in ticket["content"]


def test_limite_por_hora_e_falha_do_glpi(cliente, admin, glpi, configurada):
    _perfil()
    h = cabecalho(cliente, "fulano")
    glpi.falhar_criacao = True
    r = abrir_chamado(cliente, h, "Falha", "Descrição da falha longa")
    assert r.status_code == 502 and r.json()["codigo"] == "glpi_indisponivel" and "mantido" in r.json()["detalhe"]
    assert cliente.get(CHAMADOS, headers=h).json()["itens"] == []  # nada registrado
    glpi.falhar_criacao = False
    for n in range(5):
        assert abrir_chamado(cliente, h, f"Chamado {n}", "Descrição do chamado").status_code == 201
    r = abrir_chamado(cliente, h, "Sexto", "Descrição do sexto chamado")
    assert r.status_code == 429 and r.json()["codigo"] == "limite_excedido"
    # Validação do corpo
    assert abrir_chamado(cliente, h, "ab", "curta").status_code == 422
    assert cliente.post(CHAMADOS, data={"dados": json.dumps({"assunto": "Ok ok", "descricao": "Descrição ok ok", "local_id": 38})}).status_code == 401


def test_anexos_vao_para_o_chamado_no_glpi(cliente, admin, glpi, configurada):
    _perfil()
    h = cabecalho(cliente, "fulano")
    r = abrir_chamado(cliente, h, "Com anexos", "Segue o print do erro e o PDF.", [("imagem-colada-1.png", PNG, "image/png"), ("laudo.pdf", b"%PDF-1.4 teste", "application/pdf")])
    assert r.status_code == 201, r.text
    assert r.json()["anexos_enviados"] == 2 and r.json()["anexos_com_falha"] == []
    # O chamado é criado já com os arquivos (multipart com `_filename`) e continua sem categoria
    ticket = glpi.ticket()
    assert ticket["_filename"] == ["imagem-colada-1.png", "laudo.pdf"] and ticket["name"] == "Informática | Com anexos" and "itilcategories_id" not in ticket
    assert b"imagem-colada-1.png" in glpi.multipart[0].content and b"%PDF-1.4 teste" in glpi.multipart[0].content


def test_anexo_recusado_pelo_glpi_nao_desfaz_o_chamado(cliente, admin, glpi, configurada):
    _perfil()
    h = cabecalho(cliente, "fulano")
    glpi.falhar_anexo = True
    r = abrir_chamado(cliente, h, "Com anexo", "Descrição do chamado com anexo.", [("a.png", PNG, "image/png")])
    # O GLPI recusou com anexos: o chamado é aberto sem eles e a tela é avisada
    assert r.status_code == 201 and r.json()["anexos_enviados"] == 0 and r.json()["anexos_com_falha"] == ["a.png"]
    assert "_filename" not in glpi.ticket()


def test_validacao_dos_anexos(cliente, admin, glpi, configurada):
    _perfil()
    h = cabecalho(cliente, "fulano")
    def tenta(*arquivos):
        return abrir_chamado(cliente, h, "Assunto", "Descrição do problema aqui.", arquivos)
    assert tenta(("virus.exe", b"MZ....", "application/octet-stream")).status_code == 422
    assert tenta(("falso.png", b"isso nao e imagem", "image/png")).status_code == 422
    assert tenta(("vazio.pdf", b"", "application/pdf")).status_code == 422
    assert tenta(*[(f"{n}.png", PNG, "image/png") for n in range(6)]).status_code == 422
    assert tenta(("grande.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024), "application/pdf")).status_code == 422
    assert not glpi.chamadas  # nada foi enviado ao GLPI


def test_dados_temporarios_do_cadastro_valem_no_chamado_ate_a_cgp_validar(cliente, admin, glpi, configurada):
    """Primeiro cadastro: tudo está pendente de validação, mas o chamado já sai com o que o usuário informou, marcado como temporário."""
    from app.core.banco import FabricaSessao
    from app.models.usuario import Usuario
    from app.services.rh.servico_cadastro import _registrar

    criar_usuario("novato", nome_completo="Novato", email="novato@sp.gov.br", ramal="1111", departamento="", andar="", predio="", celular="")
    h = cabecalho(cliente, "novato")
    with FabricaSessao() as sessao:
        usuario = sessao.query(Usuario).filter_by(login="novato").one()
        for campo, valor in (("departamento", "Setor Novo"), ("andar", "7"), ("predio", "B"), ("ramal", "2222")):
            _registrar(sessao, usuario, campo, valor, usuario, "pendente")
        sessao.commit()
    dados = cliente.get(f"{CHAMADOS}/solicitante", headers=h).json()
    assert dados["setor"] == "Setor Novo" and dados["andar_lado"] == "7º andar - B" and dados["telefone"] == "2222"
    assert set(dados["aguardando_validacao"]) == {"departamento", "andar", "predio", "ramal"}
    r = abrir_chamado(cliente, h, "Sem rede", "Meu computador está sem rede.")
    assert r.status_code == 201, r.text
    html = glpi.ticket()["content"]
    assert "Setor Novo" in html and "7º andar - B" in html and "aguardam validação da CGP" in html


def test_local_do_problema_e_obrigatorio_e_vem_do_glpi(cliente, admin, glpi, configurada):
    _perfil()
    h = cabecalho(cliente, "fulano")
    locais = cliente.get(f"{CHAMADOS}/locais", headers=h).json()["itens"]
    assert [l["nome"] for l in locais] == ["00 - Térreo", "05º Andar > Lado B"] and locais[0]["id"] == 1
    # Sem local, ou com um local que não existe no GLPI: recusado, sem criar chamado
    r = cliente.post(CHAMADOS, data={"dados": json.dumps({"assunto": "Sem local", "descricao": "Descrição do problema."})}, headers=h)
    assert r.status_code == 422
    assert abrir_chamado(cliente, h, "Local ruim", "Descrição do problema.", local_id=9999).status_code == 422
    assert not any(c.url.path.endswith("/Ticket") for c in glpi.chamadas)


def test_configuracao_do_formulario_e_editavel_e_desligavel(cliente, admin, glpi, configurada):
    """Grupo, SLAs e modelo vêm da configuração (0 = nenhum) e o prefixo do título também."""
    _perfil()
    h = cabecalho(cliente, "fulano")
    corpo = {"ativo": True, "url_base": "https://glpi.exemplo.gov.br", "prefixo_titulo": "TI", "grupo_atribuido_id": 0, "sla_atendimento_id": 0, "sla_solucao_id": 5, "template_id": 0}
    r = cliente.put(CONFIG, json=corpo, headers=admin)
    assert r.json()["prefixo_titulo"] == "TI" and r.json()["grupo_atribuido_id"] is None and r.json()["sla_solucao_id"] == 5
    assert abrir_chamado(cliente, h, "Config", "Descrição do problema.").status_code == 201
    ticket = glpi.ticket()
    assert ticket["name"] == "TI | Config" and "_groups_id_assign" not in ticket and "slas_id_tto" not in ticket and ticket["slas_id_ttr"] == 5 and "tickettemplates_id" not in ticket
