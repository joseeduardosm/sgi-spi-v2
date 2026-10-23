# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o primeiro acesso (boas-vindas por tela e e-mail), a bio opcional na busca e no cartão, e a ficha dos legados com validação do RH.
"""Boas-vindas, bio e ficha dos legados."""

import pytest

from app.core.banco import FabricaSessao
from app.models.usuario import Usuario
from app.services.cliente_smtp import ResultadoSmtp
from tests.apoio_rh import criar_cgp
from tests.conftest import cabecalho, criar_usuario

RH = "/api/rh"


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setattr("app.services.servico_smtp.enviar_email", lambda sessao, mensagem: enviados.append(mensagem) or ResultadoSmtp(True, 1, "ok"))
    return enviados


def test_boas_vindas_aparecem_uma_vez_e_enviam_um_email(cliente, admin, emails):
    # Conta do AD recém-criada (primeiro acesso) e conta antiga (já marcada como vista)
    criar_usuario("nova.pessoa", nome_completo="Nova Pessoa", email="nova@spi.sp.gov.br", origem="ldap", cargo="FCESP 2.16 – Assessor Especial IV", departamento="Diretoria X")
    criar_usuario("antiga", nome_completo="Pessoa Antiga", origem="ldap")
    with FabricaSessao() as sessao:
        from app.core.banco import agora_utc

        antiga = sessao.query(Usuario).filter_by(login="antiga").one()
        antiga.boas_vindas_em = agora_utc()
        sessao.commit()
    h, h_antiga = cabecalho(cliente, "nova.pessoa"), cabecalho(cliente, "antiga")
    r = cliente.get(f"{RH}/boas-vindas", headers=h).json()
    assert r["pendente"] is True and "Nova Pessoa" in r["html"] and "Assessor Especial IV" in r["html"] and "nova.pessoa" in r["html"]
    assert len(emails) == 1 and emails[0].para == ["nova@spi.sp.gov.br"]
    # A segunda consulta não reenvia o e-mail; depois de confirmar, não aparece mais
    assert cliente.get(f"{RH}/boas-vindas", headers=h).json()["pendente"] is True and len(emails) == 1
    assert cliente.post(f"{RH}/boas-vindas/confirmar", headers=h).status_code == 204
    assert cliente.get(f"{RH}/boas-vindas", headers=h).json()["pendente"] is False
    assert cliente.get(f"{RH}/boas-vindas", headers=h_antiga).json()["pendente"] is False


def test_bio_so_entra_na_busca_e_no_cartao_quando_liberada(cliente, admin):
    criar_usuario("autora", nome_completo="Autora da Bio", cargo="Analista", departamento="Setor A")
    criar_usuario("leitor", nome_completo="Leitor Comum", cargo="Analista", departamento="Setor B")
    ha, hl = cabecalho(cliente, "autora"), cabecalho(cliente, "leitor")
    assert cliente.put(f"{RH}/minha-bio", json={"bio_texto": "Física nuclear, 38 anos, apaixonada por trilhas", "bio_visivel": False}, headers=ha).json()["bio_visivel"] is False
    # A bio entra na busca da lista de usuários (não nos seletores de pessoa, que procuram só pela própria pessoa)
    achar = lambda termo: [u["login"] for u in cliente.get("/api/usuarios", params={"busca": termo}, headers=admin).json()["itens"]]
    assert achar("nuclear") == []
    assert cliente.put(f"{RH}/minha-bio", json={"bio_texto": "Física nuclear, 38 anos, apaixonada por trilhas", "bio_visivel": True}, headers=ha).json()["bio_visivel"] is True
    assert achar("nuclear") == ["autora"]
    uid = cliente.get("/api/usuarios/opcoes", params={"busca": "autora"}, headers=hl).json()[0]["id"]
    assert "trilhas" in cliente.get(f"/api/diretorio/ramais/{uid}", headers=hl).json()["bio"]
    # Sem texto, a bio fica oculta mesmo marcada como visível
    assert cliente.put(f"{RH}/minha-bio", json={"bio_texto": "  ", "bio_visivel": True}, headers=ha).json()["bio_visivel"] is False


def test_ficha_do_legado_precisa_da_validacao_do_rh(cliente, admin):
    criar_cgp(criar_usuario("rh-vf", nome_completo="Rita do RH"))
    criar_usuario("legado", nome_completo="Pessoa Legada", cargo="Analista", departamento="Setor A")
    hr, hl = cabecalho(cliente, "rh-vf"), cabecalho(cliente, "legado")
    assert cliente.get(f"{RH}/minha-ficha", headers=hl).json() is None
    corpo = {"nome_completo": "Pessoa Legada", "cpf": "529.982.247-25", "celular": "11 98888-7777", "formacoes": [{"nivel": "Graduação", "curso": "Direito"}]}
    r = cliente.put(f"{RH}/minha-ficha", json=corpo, headers=hl)
    assert r.status_code == 200, r.text
    ficha = r.json()
    assert ficha["status"] == "vinculado" and ficha["cpf"] == "52998224725" and ficha["validado_em"] is None
    assert cliente.put(f"{RH}/minha-ficha", json={**corpo, "cpf": "111.111.111-11"}, headers=hl).status_code == 400
    # O RH vê pendente, corrige e valida; a validação entra no histórico (sigilosa)
    pend = cliente.get(f"{RH}/pre-cadastros", params={"pendentes_de_validacao": "true"}, headers=hr).json()
    assert [f["nome_completo"] for f in pend] == ["Pessoa Legada"]
    assert cliente.put(f"{RH}/pre-cadastros/{ficha['id']}", json={**corpo, "nome_mae": "Maria Legada"}, headers=hr).status_code == 200
    r = cliente.post(f"{RH}/pre-cadastros/{ficha['id']}/validar", headers=hr)
    assert r.status_code == 200 and r.json()["validado_em"] and r.json()["nome_mae"] == "Maria Legada" and r.json()["status"] == "vinculado"
    assert cliente.get(f"{RH}/pre-cadastros", params={"pendentes_de_validacao": "true"}, headers=hr).json() == []
    # Reenviar zera a validação
    assert cliente.put(f"{RH}/minha-ficha", json=corpo, headers=hl).json()["validado_em"] is None
    # Quem não enviou não tem o que validar
    criar_usuario("outra", nome_completo="Outra")
    assert cliente.post(f"{RH}/pre-cadastros/9999/validar", headers=hr).status_code == 404
