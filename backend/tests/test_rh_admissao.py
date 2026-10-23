# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a admissão do RH: modelos, checklists e a trilha completa (chamado, documentos, resolução, Protocolo, publicação, e-mail, posse, entrada no SGI).
"""Admissão do RH."""

import io

import pytest

from app.core.banco import FabricaSessao, hoje_sao_paulo
from app.services.glpi.cliente_formulario import PerguntaFormulario
from app.services.cliente_smtp import ResultadoSmtp
from tests.apoio_contratos import PDF
from tests.apoio_rh import criar_cgp
from tests.conftest import cabecalho, criar_usuario

RH = "/api/rh"
CPF_OK = "529.982.247-25"


@pytest.fixture
def ambiente(cliente, admin, monkeypatch):
    """O RH, um cargo vago, um checklist para FCESP, uma faixa de Resolução no Protocolo e GLPI e SMTP simulados."""
    criar_cgp(criar_usuario("rh-adm", nome_completo="Rita do RH"))
    h = cabecalho(cliente, "rh-adm")
    setor = cliente.post("/api/setores", json={"nome": "Subsecretaria de Gestão Corporativa", "sigla": "SGC"}, headers=h).json()
    tipos = {t["codigo"]: t["id"] for t in cliente.get(f"{RH}/tipos-cargo", headers=h).json()}
    cargo = cliente.post(f"{RH}/cargos", json={"setor_id": setor["id"], "tipo_id": tipos["FCESP"], "grupo": 2, "nivel": 16, "denominacao": "Assessor Especial IV", "quantidade": 1}, headers=h).json()[0]
    cliente.post(f"{RH}/checklists", json={"nome": "Documentos de FCESP", "classificacoes": [{"grupo": 2, "nivel": 16}, {"grupo": 2, "nivel": 15}], "itens": [{"descricao": "RG", "obrigatorio": True}, {"descricao": "Foto 3x4", "obrigatorio": False}]}, headers=h)
    tipo = cliente.post("/api/protocolo/tipos", json={"nome": "Resoluções SPI 1"}, headers=admin).json()
    cliente.post(f"/api/protocolo/tipos/{tipo['id']}/sequencias", json={"exercicio": hoje_sao_paulo().year, "inicio": 1, "fim": 20}, headers=admin)
    enviados = []
    monkeypatch.setattr("app.services.rh.servico_admissao._cliente_formulario", lambda sessao: (_FormularioFalso(enviados), 8))
    emails = []
    monkeypatch.setattr("app.services.servico_smtp.enviar_email", lambda sessao, mensagem: emails.append(mensagem) or ResultadoSmtp(True, 1, "ok"))
    return {"h": h, "admin": admin, "cargo": cargo, "tipo_protocolo": tipo["id"], "chamados": enviados, "emails": emails}


class _FormularioFalso:
    """O formulário "CGP - Nomeações" do GLPI (ids e opções reais) sem falar com o GLPI: guarda o que foi enviado."""

    def __init__(self, enviados: list) -> None:
        self.enviados = enviados

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def perguntas(self, formulario_id):
        def radio(i, titulo, sim, nao):
            return PerguntaFormulario(id=i, nome=f"answers_{i}[]", rotulo=titulo, tipo="radio", opcoes=[(sim, "Sim"), (nao, "Não")])

        lista = [
            PerguntaFormulario(id=44, nome="answers_44", rotulo="Nome", tipo="text", obrigatoria=True), PerguntaFormulario(id=47, nome="answers_47", rotulo="Cargo", tipo="text", obrigatoria=True),
            PerguntaFormulario(id=48, nome="answers_48", rotulo="Registo do Servidor (RS)", tipo="number"), PerguntaFormulario(id=49, nome="answers_49", rotulo="Lotação", tipo="text", obrigatoria=True),
            PerguntaFormulario(id=50, nome="answers_50", rotulo="Data de início", tipo="text"), PerguntaFormulario(id=51, nome="answers_51", rotulo="Usuário espelho", tipo="text"),
            PerguntaFormulario(id=52, nome="answers_52", rotulo="RG", tipo="text", obrigatoria=True), PerguntaFormulario(id=53, nome="answers_53", rotulo="CPF", tipo="number", obrigatoria=True),
            radio(42, "Criar usuário de rede", "r1", "r2"), radio(72, "Criar e-mail corporativo", "e1", "e2"), radio(73, "Criar acesso ao SEI", "s1", "s2"),
            radio(74, "Criar acesso ao Compras SP", "c1", "c2"), radio(75, "Provisionar equipamento de trabalho", "q1", "q2"), radio(76, "Preparo da estação", "t1", "t2"),
            radio(77, "Solicitar crachá", "k1", "k2"), radio(79, "Provisionar telefone", "f1", "f2"), radio(83, "Provisionar mobiliário", "m1", "m2"),
            radio(104, "Alguma observação adicional?", "o1", "o2"), PerguntaFormulario(id=109, nome="answers_109", rotulo="Observações adicionais", tipo="textarea"),
            PerguntaFormulario(id=85, rotulo="Foto", tipo="file", uploader="_uploader_answers_85"),
        ]
        return lista, "csrf"

    def subir_arquivo(self, pergunta, nome, conteudo, tipo_mime):
        self.enviados.append(("upload", pergunta.id, nome, len(conteudo), tipo_mime))
        return {"name": "tmp_" + nome, "prefix": "pfx"}

    def enviar(self, formulario_id, respostas, arquivos=None):
        self.enviados.append((formulario_id, respostas, arquivos))
        return {"links_to_created_items": ['<a href="/front/ticket.form.php?id=901">Chamado 901</a>', '<a href="/front/ticket.form.php?id=902">Chamado 902</a>']}


def _ficha(cliente, amb, **extra):
    corpo = {"nome_completo": "Joana Pereira Lima", "cpf": CPF_OK, "rg_numero": "12.345.678-9", "rs_pv": "654321-0", "email_pessoal": "joana@exemplo.com", "inicio_previsto": "2026-11-03",
             "cargo_id": amb["cargo"]["id"], "login_proposto": "joana.lima", "status": "aguardando_conta", **extra}
    r = cliente.post(f"{RH}/pre-cadastros", json=corpo, headers=amb["h"])
    assert r.status_code == 201, r.text
    return r.json()


def test_modelos_padrao_placeholders_e_checklists(cliente, ambiente):
    h = ambiente["h"]
    modelos = {m["tipo"]: m for m in cliente.get(f"{RH}/modelos", headers=h).json()}
    assert set(modelos) == {"resolucao_nomeacao", "email_nomeacao_publicada", "termo_posse", "boas_vindas"} and "#numeroresolucao" in modelos["resolucao_nomeacao"]["html"]
    assert "nome" in cliente.get(f"{RH}/modelos/placeholders", headers=h).json()
    # Placeholder fora da lista barra o salvamento; texto válido grava; restaurar volta ao padrão
    assert cliente.put(f"{RH}/modelos/termo_posse", json={"assunto": "", "html": "<p>#inventado</p>"}, headers=h).status_code == 400
    assert cliente.put(f"{RH}/modelos/termo_posse", json={"assunto": "", "html": "<p>Posse de #nome</p>"}, headers=h).status_code == 200
    assert cliente.post(f"{RH}/modelos/termo_posse/restaurar", headers=h).json()["html"].startswith("<h2>TERMO DE POSSE")
    lista = cliente.get(f"{RH}/checklists", headers=h).json()
    assert len(lista) == 1 and lista[0]["classificacoes"] == [{"grupo": 2, "nivel": 15}, {"grupo": 2, "nivel": 16}] and lista[0]["aplica_a_outros"] is False
    # Sem classificação nem "outros" o checklist não vale para nada; nível fora de 1 a 18 e grupo fora de 1 e 2 são recusados
    assert cliente.post(f"{RH}/checklists", json={"nome": "Vazio", "itens": []}, headers=h).status_code == 400
    assert cliente.post(f"{RH}/checklists", json={"nome": "Ruim", "classificacoes": [{"grupo": 3, "nivel": 5}], "itens": []}, headers=h).status_code == 422
    assert cliente.post(f"{RH}/checklists", json={"nome": "Ruim", "classificacoes": [{"grupo": 1, "nivel": 19}], "itens": []}, headers=h).status_code == 422
    # Só o RH (controle total)
    criar_usuario("sem-rh", nome_completo="Sem RH")
    assert cliente.get(f"{RH}/modelos", headers=cabecalho(cliente, "sem-rh")).status_code == 403


def test_trilha_completa_da_admissao(cliente, ambiente):
    amb, h = ambiente, ambiente["h"]
    ficha = _ficha(cliente, amb)
    adm = cliente.post(f"{RH}/admissoes", json={"ficha_id": ficha["id"]}, headers=h)
    assert adm.status_code == 201, adm.text
    adm = adm.json()
    aid = adm["id"]
    assert adm["etapa"] == "chamado" and [d["descricao"] for d in adm["documentos"]] == ["RG", "Foto 3x4"]
    # Cargo já tem admissão em andamento
    assert cliente.post(f"{RH}/admissoes", json={"ficha_id": ficha["id"]}, headers=h).status_code == 409
    # Etapas à frente ficam bloqueadas
    assert cliente.post(f"{RH}/admissoes/{aid}/documentos/concluir", headers=h).status_code == 409
    assert cliente.post(f"{RH}/admissoes/{aid}/resolucao", headers=h).status_code == 409

    # 0. Foto (opcional): só PNG/JPG válidos; vai no formulário e depois para a intranet
    import io as _io

    from PIL import Image

    imagem = _io.BytesIO()
    Image.new("RGB", (20, 20), (200, 30, 40)).save(imagem, "PNG")
    assert cliente.put(f"{RH}/admissoes/{aid}/foto", files={"arquivo": ("foto.txt", _io.BytesIO(b"texto"), "text/plain")}, headers=h).status_code == 400
    r = cliente.put(f"{RH}/admissoes/{aid}/foto", files={"arquivo": ("foto.png", _io.BytesIO(imagem.getvalue()), "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["tem_foto"] is True and cliente.get(f"{RH}/admissoes/{aid}/foto", headers=h).status_code == 200

    # 1. Chamado
    r = cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {"rede": True, "email": True, "sei": False}, "observacoes": "Urgente", "usuario_espelho": "mirror.user"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["chamado_glpi_id"] == 901 and r.json()["etapa"] == "documentos" and r.json()["solicitacoes"]["rede"] is True
    assert [l["texto"] for l in r.json()["chamado_links"]] == ["Chamado 901", "Chamado 902"] and r.json()["chamado_links"][0]["url"].endswith("/front/ticket.form.php?id=901")
    *_, (formulario_id, respostas, arquivos) = amb["chamados"]
    # As respostas vão pelos títulos das perguntas: dados da ficha, Sim/Não pelas chaves reais e o login proposto nas observações
    assert formulario_id == 8 and respostas[44] == "Joana Pereira Lima" and respostas[53] == "52998224725" and respostas[48] == "6543210" and respostas[50] == "2026-11-03"
    assert respostas[52] == "12.345.678-9" and respostas[47].startswith("FCESP 2.16") and respostas[49] == "Subsecretaria de Gestão Corporativa" and respostas[51] == "mirror.user"
    assert respostas[42] == "r1" and respostas[72] == "e1" and respostas[73] == "s2" and respostas[104] == "o1"
    assert "Login de rede proposto: joana.lima" in respostas[109] and "Urgente" in respostas[109]
    # A foto subiu ao GLPI (pergunta "Foto") e vai no envio com o nome temporário devolvido
    upload = next(e for e in amb["chamados"] if e[0] == "upload")
    assert upload[1] == 85 and upload[2].startswith("foto-admissao-") and upload[4] == "image/png" and arquivos == {85: [{"name": "tmp_" + upload[2], "prefix": "pfx"}]}
    assert cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {}}, headers=h).status_code == 409

    # 2. Documentos: obrigatório pendente trava; comprovante opcional
    assert cliente.post(f"{RH}/admissoes/{aid}/documentos/concluir", headers=h).status_code == 400
    rg = adm["documentos"][0]["id"]
    r = cliente.post(f"{RH}/admissoes/{aid}/documentos/{rg}", data={"enviado_em": "2026-10-20", "observacao": "Enviado"}, files={"comprovante": ("comprovante.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["documentos"][0]["tem_comprovante"] is True
    assert cliente.get(f"{RH}/admissoes/{aid}/documentos/{rg}/comprovante", headers=h).status_code == 200
    r = cliente.post(f"{RH}/admissoes/{aid}/documentos/concluir", headers=h)
    assert r.status_code == 200 and r.json()["etapa"] == "resolucao"

    # 3. Resolução: texto do modelo, edição, PDF com MINUTA
    r = cliente.post(f"{RH}/admissoes/{aid}/resolucao", headers=h)
    assert r.status_code == 200 and "#nome" in r.json()["resolucao_html"] and r.json()["etapa"] == "protocolo"
    assert cliente.put(f"{RH}/admissoes/{aid}/resolucao", json={"html": "<p>#naoexiste</p>"}, headers=h).status_code == 400
    copia = cliente.get(f"{RH}/admissoes/{aid}/resolucao/copia", headers=h).json()
    assert "Joana Pereira Lima" in copia["texto"] and "<strong>" in copia["html"] and "#nome" not in copia["html"] and "RESOLUÇÃO SPI" in copia["texto"]
    pdf = cliente.get(f"{RH}/admissoes/{aid}/resolucao.pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # 4. Número no Protocolo (tipo de Resolução)
    assert cliente.get(f"{RH}/admissoes/tipos-protocolo", headers=h).json()[0]["tem_faixa_no_ano"] is True
    r = cliente.post(f"{RH}/admissoes/{aid}/protocolo", json={"tipo_protocolo_id": amb["tipo_protocolo"]}, headers=h)
    assert r.status_code == 200, r.text
    numero = r.json()["numero_protocolo"]
    assert numero.startswith("001/") and r.json()["etapa"] == "publicacao"

    # 5. Publicação: só PDF; anexa ao número e registra
    assert cliente.post(f"{RH}/admissoes/{aid}/publicacao", data={"publicado_em": "2026-10-21"}, files={"arquivo": ("doe.txt", io.BytesIO(b"x"), "text/plain")}, headers=h).status_code == 409
    r = cliente.post(f"{RH}/admissoes/{aid}/publicacao", data={"publicado_em": "2026-10-21"}, files={"arquivo": ("doe.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["publicado_em"] == "2026-10-21" and r.json()["tem_publicacao"] is True and r.json()["etapa"] == "posse"
    assert cliente.get(f"{RH}/admissoes/{aid}/publicacao.pdf", headers=h).status_code == 200
    assert cliente.get(f"{RH}/admissoes/{aid}/resolucao.pdf", headers=h).status_code == 200  # agora sem marca d'água

    # E-mail "Sua nomeação foi publicada": sai sozinho ao registrar a publicação, com o PDF e a data informada; reenviar já enviado é 409
    assert r.json()["email_enviado_em"] is not None and r.json()["email_erro"] is None
    msg = amb["emails"][0]
    assert msg.para == ["joana@exemplo.com"] and msg.assunto == "Sua nomeação foi publicada" and len(msg.anexos) == 1 and "Assessor Especial IV" in msg.texto and "21/10/2026" in msg.texto
    assert len(amb["emails"]) == 1 and cliente.post(f"{RH}/admissoes/{aid}/email", headers=h).status_code == 409

    # 6. Posse (não anterior à publicação) e termo em PDF
    assert cliente.post(f"{RH}/admissoes/{aid}/posse", json={"posse_em": "2026-10-01"}, headers=h).status_code == 400
    r = cliente.post(f"{RH}/admissoes/{aid}/posse", json={"posse_em": "2026-11-03"}, headers=h)
    assert r.status_code == 200 and r.json()["etapa"] == "concluida" and "#nome" in r.json()["termo_html"]
    assert cliente.get(f"{RH}/admissoes/{aid}/termo.pdf", headers=h).content.startswith(b"%PDF")

    # 8. Sem conta no SGI/AD a admissão não conclui; quando a conta aparece, a ficha vincula e a pessoa assume o cargo
    r = cliente.post(f"{RH}/admissoes/{aid}/concluir", headers=h)
    assert r.status_code == 409 and "joana.lima" in r.json()["detalhe"]
    from app.models.diretorio_ldap import DiretorioLdap
    from app.services import servico_ldap
    from app.services.cliente_ldap import IdentidadeLdap

    with FabricaSessao() as sessao:
        diretorio = DiretorioLdap(nome="AD teste", servidor="ad.local", porta=389, usar_ssl=False, base_dn="DC=a,DC=b", bind_dn="x", senha_bind_cifrada="x", ativo=True)
        sessao.add(diretorio)
        sessao.commit()
        servico_ldap.aplicar_fotografia(sessao, diretorio, [IdentidadeLdap(login="joana.lima", nome_completo="Joana Pereira Lima", email="joana@spi.sp.gov.br", dn="CN=j", id_externo="guid-j")])
        sessao.commit()
    r = cliente.post(f"{RH}/admissoes/{aid}/concluir", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "concluida"
    uid = r.json()["usuario_id"]
    # A foto da admissão virou a foto do Diretório (intranet) da pessoa
    with FabricaSessao() as sessao:
        from app.models.usuario import Usuario

        pessoa = sessao.get(Usuario, uid)
        assert pessoa.foto_anexo_id is not None and pessoa.foto_origem == "upload"
    hist = cliente.get(f"{RH}/usuarios/{uid}/historico", headers=h).json()
    assert any(e["tipo"] == "documento" and "RG" in e["titulo"] for e in hist["eventos"])
    assert any(e["tipo"] == "admissao" for e in hist["eventos"]) and hist["cargo_atual"].startswith("FCESP 2.16")
    assert cliente.get(f"{RH}/cargos", params={"situacao": "ocupado"}, headers=h).json()[0]["ocupante"]["login"] == "joana.lima"


def test_cancelar_libera_o_numero_do_protocolo(cliente, ambiente):
    amb, h = ambiente, ambiente["h"]
    aid = cliente.post(f"{RH}/admissoes", json={"ficha_id": _ficha(cliente, amb)["id"]}, headers=h).json()["id"]
    # Sem checklist obrigatório pendente? RG é obrigatório: registra e segue até reservar o número
    cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {}}, headers=h)
    rg = cliente.get(f"{RH}/admissoes/{aid}", headers=h).json()["documentos"][0]["id"]
    cliente.post(f"{RH}/admissoes/{aid}/documentos/{rg}", data={"enviado_em": "2026-10-20"}, headers=h)
    cliente.post(f"{RH}/admissoes/{aid}/documentos/concluir", headers=h)
    cliente.post(f"{RH}/admissoes/{aid}/resolucao", headers=h)
    assert cliente.post(f"{RH}/admissoes/{aid}/protocolo", json={"tipo_protocolo_id": amb["tipo_protocolo"]}, headers=h).status_code == 200
    r = cliente.post(f"{RH}/admissoes/{aid}/cancelar", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    # A vaga ficou livre de novo: outra ficha pode iniciar a admissão do mesmo cargo
    aid2 = cliente.post(f"{RH}/admissoes", json={"ficha_id": _ficha(cliente, amb, nome_completo="Outra Pessoa", cpf="", login_proposto="outra.pessoa")["id"]}, headers=h)
    assert aid2.status_code == 201, aid2.text


def _avancar_ate_a_publicacao(cliente, amb) -> int:
    h = amb["h"]
    aid = cliente.post(f"{RH}/admissoes", json={"ficha_id": _ficha(cliente, amb)["id"]}, headers=h).json()["id"]
    cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {}}, headers=h)
    rg = cliente.get(f"{RH}/admissoes/{aid}", headers=h).json()["documentos"][0]["id"]
    cliente.post(f"{RH}/admissoes/{aid}/documentos/{rg}", data={"enviado_em": "2026-10-20"}, headers=h)
    cliente.post(f"{RH}/admissoes/{aid}/documentos/concluir", headers=h)
    cliente.post(f"{RH}/admissoes/{aid}/resolucao", headers=h)
    cliente.post(f"{RH}/admissoes/{aid}/protocolo", json={"tipo_protocolo_id": amb["tipo_protocolo"]}, headers=h)
    return aid


def test_falha_do_email_nao_desfaz_a_publicacao_e_o_rh_reenvia(cliente, ambiente, monkeypatch):
    amb, h = ambiente, ambiente["h"]
    aid = _avancar_ate_a_publicacao(cliente, amb)
    monkeypatch.setattr("app.services.servico_smtp.enviar_email", lambda sessao, mensagem: ResultadoSmtp(False, 0, "servidor de e-mail fora do ar"))
    r = cliente.post(f"{RH}/admissoes/{aid}/publicacao", data={"publicado_em": "2026-10-21"}, files={"arquivo": ("doe.pdf", io.BytesIO(PDF), "application/pdf")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["tem_publicacao"] is True and r.json()["etapa"] == "posse" and r.json()["email_enviado_em"] is None and "fora do ar" in r.json()["email_erro"]
    assert cliente.post(f"{RH}/admissoes/{aid}/email", headers=h).status_code == 400  # ainda fora do ar: o motivo continua guardado
    monkeypatch.setattr("app.services.servico_smtp.enviar_email", lambda sessao, mensagem: amb["emails"].append(mensagem) or ResultadoSmtp(True, 1, "ok"))
    r = cliente.post(f"{RH}/admissoes/{aid}/email", headers=h)
    assert r.status_code == 200 and r.json()["email_enviado_em"] is not None and r.json()["email_erro"] is None and len(amb["emails"]) == 1


def test_pdf_anexado_direto_no_protocolo_tambem_envia_o_email(cliente, ambiente):
    amb, h = ambiente, ambiente["h"]
    aid = _avancar_ate_a_publicacao(cliente, amb)
    numero_id = cliente.get(f"{RH}/admissoes/{aid}", headers=h).json()["numero_protocolo_id"]
    r = cliente.post(f"/api/protocolo/numeros/{numero_id}/anexo", files={"arquivo": ("doe.pdf", io.BytesIO(PDF), "application/pdf")}, headers=amb["admin"])
    assert r.status_code == 200, r.text
    adm = cliente.get(f"{RH}/admissoes/{aid}", headers=h).json()
    assert adm["tem_publicacao"] is True and adm["email_enviado_em"] is not None and len(amb["emails"]) == 1 and amb["emails"][0].para == ["joana@exemplo.com"]
