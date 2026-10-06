# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a assinatura de e-mail (dados do perfil, prévia, PNG e HTML).
"""Assinatura de e-mail (`/api/assinatura-email`): PNG em alta resolução, HTML copiável, avisos e perfil intacto."""

import base64
import io

from PIL import Image
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models import RegistroAuditoria
from app.models.rh import AlteracaoCadastral
from app.models.usuario import Usuario
from tests.conftest import PERFIL_COMPLETO, cabecalho, criar_usuario

URL = "/api/assinatura-email"
DADOS = {"nome_completo": "Elaine Bothmann", "cargo": "Assessor II", "departamento": "Coordenadoria de Gestão de Pessoas",
         "email": "ebothmann@sp.gov.br", "ramal": "8178", "celular": "11999998888", "andar": "5", "lado": "B"}


def _png(resposta) -> Image.Image:
    return Image.open(io.BytesIO(resposta.content))


def test_exige_login(cliente):
    assert cliente.get(f"{URL}/dados").status_code == 401
    assert cliente.post(f"{URL}/previa", json=DADOS).status_code == 401


def test_dados_vem_do_perfil_em_vigor_e_nao_do_pendente(cliente):
    criar_usuario("ana", nome_completo="Ana Souza", email="ana@sp.gov.br", cargo="Analista", ramal="1234", celular="11988887777")
    h = cabecalho(cliente, "ana")
    dados = cliente.get(f"{URL}/dados", headers=h).json()
    assert dados["nome_completo"] == "Ana Souza" and dados["cargo"] == "Analista" and dados["ramal"] == "1234"
    assert dados["faltando"] == [] and dados["incluir_celular"] is False and dados["telefone_prefixo"] == "(11) 3702-"
    # Uma alteração do cargo fica pendente de validação da CGP: a assinatura continua com o valor em vigor
    perfil = {**PERFIL_COMPLETO, "nome_completo": "Ana Souza", "email": "ana@sp.gov.br", "cargo": "Coordenadora", "gestor_id": None}
    cliente.put("/api/autenticacao/perfil", json=perfil, headers=h)
    assert cliente.get(f"{URL}/dados", headers=h).json()["cargo"] == "Analista"


def test_dados_informa_o_que_falta(cliente, admin):
    # A conta root não tem perfil institucional: a tela avisa o que precisa ser preenchido antes de gerar
    faltando = cliente.get(f"{URL}/dados", headers=admin).json()["faltando"]
    assert "cargo" in faltando and "e-mail" in faltando


def test_previa_devolve_png_em_alta_resolucao_html_e_nao_grava_no_perfil(cliente):
    uid = criar_usuario("elaine", nome_completo="Elaine Bothmann", email="ebothmann@sp.gov.br", cargo="Assessor II")
    h = cabecalho(cliente, "elaine")
    r = cliente.post(f"{URL}/previa", json={**DADOS, "incluir_celular": True, "incluir_andar_lado": True}, headers=h)
    assert r.status_code == 200, r.text
    corpo = r.json()
    imagem = Image.open(io.BytesIO(base64.b64decode(corpo["png_base64"])))
    assert imagem.size == (1765, 492) and imagem.format == "PNG"
    assert "(11) 3702-8178" in corpo["html"] and "Cel. (11) 99999-8888" in corpo["html"] and "5º andar · Lado B" in corpo["html"]
    assert 'alt="' in corpo["html"] and "data:image/png;base64," in corpo["html"] and 'width="564"' in corpo["html"]
    assert corpo["avisos"] == []
    # Nada foi gravado no perfil nem na fila de validação da CGP
    with FabricaSessao() as sessao:
        usuario = sessao.get(Usuario, uid)
        assert usuario.cargo == "Assessor II" and usuario.celular == "" and sessao.scalars(select(AlteracaoCadastral)).first() is None


def test_celular_e_andar_so_aparecem_quando_marcados(cliente):
    h = cabecalho_de_teste(cliente)
    html = cliente.post(f"{URL}/previa", json=DADOS, headers=h).json()["html"]
    assert "Cel." not in html and "andar" not in html
    html = cliente.post(f"{URL}/previa", json={**DADOS, "incluir_celular": True}, headers=h).json()["html"]
    assert "Cel." in html and "andar" not in html
    # Marcado, mas ausente no perfil: aviso (a imagem sai sem a linha)
    sem = {**DADOS, "celular": "", "incluir_celular": True}
    assert any("celular" in a for a in cliente.post(f"{URL}/previa", json=sem, headers=h).json()["avisos"])


def cabecalho_de_teste(cliente):
    criar_usuario("qualquer", nome_completo="Qualquer Pessoa", email="q@sp.gov.br")
    return cabecalho(cliente, "qualquer")


def test_texto_longo_e_abreviado_com_aviso_e_a_imagem_mantem_o_tamanho(cliente):
    h = cabecalho_de_teste(cliente)
    longo = {**DADOS, "email": "nome.sobrenome.muito.extenso.de.teste.da.assinatura@sp.gov.br",
             "cargo": "Cargo extremamente descritivo " * 6, "departamento": "Departamento com nome muito comprido " * 4}
    r = cliente.post(f"{URL}/previa", json=longo, headers=h)
    assert r.status_code == 200
    avisos = " ".join(r.json()["avisos"])
    assert "E-mail e telefone muito longo" in avisos and "Cargo muito longo" in avisos and "Órgão muito longo" in avisos
    assert Image.open(io.BytesIO(base64.b64decode(r.json()["png_base64"]))).size == (1765, 492)


def test_html_escapa_o_que_o_usuario_digita(cliente):
    h = cabecalho_de_teste(cliente)
    r = cliente.post(f"{URL}/previa", json={**DADOS, "nome_completo": "<script>alert(1)</script>", "cargo": '"><img src=x>'}, headers=h)
    html = r.json()["html"]
    assert "<script>" not in html and "&lt;script&gt;" in html and "<img src=x>" not in html


def test_validacoes(cliente):
    h = cabecalho_de_teste(cliente)
    assert cliente.post(f"{URL}/previa", json={**DADOS, "email": "invalido"}, headers=h).status_code == 422
    assert cliente.post(f"{URL}/previa", json={**DADOS, "ramal": "81 78"}, headers=h).status_code == 422
    assert cliente.post(f"{URL}/previa", json={**DADOS, "celular": "abc"}, headers=h).status_code == 422
    r = cliente.post(f"{URL}/previa", json={**DADOS, "nome_completo": "", "cargo": ""}, headers=h)
    assert r.status_code == 400 and "nome, cargo" in r.json()["detalhe"]


def test_baixar_png_e_html_com_auditoria(cliente):
    h = cabecalho_de_teste(cliente)
    r = cliente.post(f"{URL}/png", json=DADOS, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert 'filename="assinatura-email.png"' in r.headers["content-disposition"] and _png(r).size == (1765, 492)
    r = cliente.post(f"{URL}/html", json=DADOS, headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in r.text and "ebothmann@sp.gov.br" in r.text
    with FabricaSessao() as sessao:
        acoes = list(sessao.scalars(select(RegistroAuditoria.acao).where(RegistroAuditoria.acao == "assinatura.gerar")))
    assert len(acoes) == 2
