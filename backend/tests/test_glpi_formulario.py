# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o cliente web do GLPI para formulários nativos (login, leitura das perguntas e envio), com o GLPI simulado, e a gravação cifrada do login web.
"""Cliente web de formulários do GLPI 11 (simulado) e configuração do login web."""

import httpx
import pytest

from app.services.glpi.cliente_formulario import ClienteFormularioGlpi
from app.services.glpi.cliente_glpi import ErroGlpi
from tests.conftest import cabecalho

LOGIN = """<html><head><meta property="glpi:csrf_token" content="csrf-login"></head><body><form>
<input type="hidden" name="noAUTO" value="0"><input type="hidden" name="redirect" value="">
<input type="hidden" name="_glpi_csrf_token" value="csrf-login"><input type="text" id="login_name" name="login_name"><input type="password" id="login_password" name="login_password">
<input type="checkbox" name="login_remember" checked></form></body></html>"""
FORMULARIO = """<html><head><meta property="glpi:csrf_token" content="csrf-form"></head><body>
<h3 class="mb-2">Nome <span class="text-danger">*</span></h3><input type="text" class="form-control" name="answers_44" value="" required>
<h3 class="mb-2">CPF</h3><input type="number" name="answers_53" value="">
<h3 class="mb-2">Criar usuário de rede <span class="text-danger">*</span></h3><input type="hidden" name="answers_42[]" value="">
<label class="form-check"><input type="radio" name="answers_42[]" value="chave-sim"><span class="form-check-label"> Sim </span></label>
<label class="form-check mb-0"><input type="radio" name="answers_42[]" value="chave-nao"><span class="form-check-label"> Não </span></label>
<h3>Observações adicionais</h3><textarea name="answers_109"></textarea><input type="file" name="_uploader_answers_109[]">
<h3 class="mb-2">Foto</h3><input type="file" name="_uploader_answers_85[]"><div class="modal"><h3 class="modal-title">Tipos de Documentos</h3></div></body></html>"""


def _glpi(registro: list, senha_certa: bool = True):
    def tratar(requisicao: httpx.Request) -> httpx.Response:
        registro.append((requisicao.method, requisicao.url.path, requisicao.content.decode(errors="replace") if requisicao.content else "", dict(requisicao.headers)))
        if requisicao.url.path == "/" and requisicao.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if requisicao.url.path == "/front/login.php":
            corpo = requisicao.content.decode()
            ok = senha_certa and "login_name=svc" in corpo and "login_password=segredo" in corpo and "csrf-login" in corpo
            return httpx.Response(302, headers={"location": "/front/central.php" if ok else "/?error=3"})
        if requisicao.url.path == "/Form/Render/8":
            return httpx.Response(200, text=FORMULARIO)
        if requisicao.url.path == "/ajax/fileupload.php":
            return httpx.Response(200, json={"_uploader_answers_85": [{"name": "tmp_foto.png", "prefix": "prefixo1", "display": "foto.png", "id": "x"}]})
        if requisicao.url.path == "/Form/SubmitAnswers":
            return httpx.Response(200, json={"links_to_created_items": ["/front/ticket.form.php?id=1"]})
        return httpx.Response(200, text="")
    return httpx.MockTransport(tratar)


def test_login_leitura_das_perguntas_e_envio():
    registro: list = []
    with ClienteFormularioGlpi("https://glpi.exemplo", "svc", "segredo", transporte=_glpi(registro)) as glpi:
        perguntas, csrf = glpi.perguntas(8)
        assert csrf == "csrf-form"
        assert sorted((p.id, p.tipo, p.rotulo, p.nome) for p in perguntas) == sorted([(42, "radio", "Criar usuário de rede", "answers_42[]"), (44, "text", "Nome", "answers_44"),
                                                                        (53, "number", "CPF", "answers_53"), (85, "file", "Foto", ""), (109, "textarea", "Observações adicionais", "answers_109")])
        assert next(p for p in perguntas if p.id == 44).obrigatoria is True
        assert next(p for p in perguntas if p.id == 42).opcoes == [("chave-sim", "Sim"), ("chave-nao", "Não")]
        foto = next(p for p in perguntas if p.rotulo == "Foto")
        enviado = glpi.subir_arquivo(foto, "foto.png", b"\x89PNG...", "image/png")
        assert enviado["name"] == "tmp_foto.png" and enviado["prefix"] == "prefixo1"
        resposta = glpi.enviar(8, {44: "Ana", 53: "52998224725", 42: "chave-sim"}, {85: [enviado]})
        assert resposta["links_to_created_items"]
    envio = next(r for r in registro if r[1] == "/Form/SubmitAnswers")
    # Escolha vai como o navegador manda: o campo escondido vazio e depois a chave da opção
    assert "forms_id=8" in envio[2] and "answers_44=Ana" in envio[2] and envio[2].count("answers_42%5B%5D=") == 2 and "answers_42%5B%5D=chave-sim" in envio[2] and envio[3]["x-glpi-csrf-token"] == "csrf-form"
    # O arquivo sobe à área temporária do GLPI e vai no envio como o navegador manda (`_answers_`, `_prefix_answers_`, `_tag_answers_`)
    subida = next(r for r in registro if r[1] == "/ajax/fileupload.php")
    assert "_uploader_answers_85" in subida[2] and subida[3]["x-glpi-csrf-token"] == "csrf-form"
    assert "_answers_85%5B0%5D=tmp_foto.png" in envio[2] and "_prefix_answers_85%5B0%5D=prefixo1" in envio[2]
    assert registro[-1][1] == "/front/logout.php"  # sai do GLPI ao terminar


def test_enviar_pergunta_que_nao_existe_mais_avisa():
    with ClienteFormularioGlpi("https://glpi.exemplo", "svc", "segredo", transporte=_glpi([])) as glpi:
        with pytest.raises(ErroGlpi, match="não tem as perguntas"):
            glpi.enviar(8, {999: "x"})


def test_login_recusado_vira_erro_claro():
    with pytest.raises(ErroGlpi, match="recusou o login"):
        with ClienteFormularioGlpi("https://glpi.exemplo", "svc", "errada", transporte=_glpi([], senha_certa=False)):
            pass


def test_senha_web_fica_cifrada_e_nao_volta_pela_api(cliente, admin):
    corpo = {"ativo": True, "url_base": "https://glpi.exemplo", "usuario_web": "svc-sgi", "senha_web": "segredo-web-123", "formulario_nomeacao_id": 8}
    r = cliente.put("/api/integracao-glpi", json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    lido = cliente.get("/api/integracao-glpi", headers=admin).json()
    assert lido["usuario_web"] == "svc-sgi" and lido["possui_senha_web"] is True and lido["login_web_configurado"] is True and "senha_web" not in lido
    assert "segredo-web-123" not in str(lido)
    from app.core.banco import FabricaSessao
    from app.services import servico_integracao_glpi as integracao

    with FabricaSessao() as sessao:
        config = integracao.obter(sessao)
        assert config.senha_web_cifrada and "segredo-web-123" not in config.senha_web_cifrada
        assert integracao.credencial_web(config) == ("svc-sgi", "segredo-web-123")
    # Senha em branco preserva a gravada
    cliente.put("/api/integracao-glpi", json={**corpo, "senha_web": None}, headers=admin)
    with FabricaSessao() as sessao:
        assert integracao.credencial_web(integracao.obter(sessao))[1] == "segredo-web-123"
