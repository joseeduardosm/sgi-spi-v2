# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o Diretório: ramais em cartões, aniversariantes, mural, favoritos, foto, vCard e parabéns automático.
"""Módulo Diretório (`/api/diretorio`)."""

from datetime import date, timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.rh import Afastamento
from app.services import servico_diretorio
from tests.conftest import cabecalho, criar_usuario

URL = "/api/diretorio"


def _png(lado=900, cor=(200, 60, 60)) -> bytes:
    saida = BytesIO()
    Image.new("RGB", (lado, lado // 2), cor).save(saida, "PNG")
    return saida.getvalue()


def _nasc(dias: int, ano=1990) -> date:
    """Nascimento cujo aniversário cai daqui a `dias` dias."""
    alvo = date.today() + timedelta(days=dias)
    return servico_diretorio.data_no_ano(date(ano, alvo.month, alvo.day), ano) if (alvo.month, alvo.day) != (2, 29) else date(1992, 2, 29)


@pytest.fixture
def equipe(cliente):
    """Chefe (Célia) com dois liderados; Bia faz aniversário hoje, Davi daqui a 3 dias, Eva daqui a 20 e Fábio nasceu em 29/02."""
    ids = {}
    for login, nome, nasc, extra in (
        ("celia", "Célia Chefe", None, {"cargo": "Coordenadora", "departamento": "Contratos"}),
        ("bia", "Bia Souza", _nasc(0), {"departamento": "Jurídico", "celular": "(11) 99999-0001"}),
        ("davi", "Davi Lima", _nasc(3), {"departamento": "Contratos", "andar": "3"}),
        ("eva", "Eva Prado", _nasc(20), {"departamento": "TI"}),
    ):
        ids[login] = criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br", ramal=f"10{len(ids)}", data_nascimento=nasc, **extra)
    with FabricaSessao() as s:
        from app.models.usuario import Usuario
        for login in ("bia", "davi"):
            s.get(Usuario, ids[login]).gestor_id = ids["celia"]
        s.commit()
    return ids, {login: cabecalho(cliente, login) for login in ids}


def test_ramais_exigem_login_e_listam_so_ativos_com_ramal(cliente, equipe):
    ids, h = equipe
    assert cliente.get(f"{URL}/ramais").status_code == 401
    criar_usuario("sem_ramal", nome_completo="Sem Ramal", ramal="")
    criar_usuario("inativo", nome_completo="Inativo", ramal="999")
    with FabricaSessao() as s:
        from app.models.usuario import Usuario
        s.scalars(select(Usuario).where(Usuario.login == "inativo")).one().ativo = False
        s.commit()
    r = cliente.get(f"{URL}/ramais", headers=h["bia"])
    assert r.status_code == 200
    nomes = [c["nome"] for c in r.json()["itens"]]
    assert nomes == sorted(nomes) and "Sem Ramal" not in nomes and "Inativo" not in nomes and "Bia Souza" in nomes
    assert "nascimento" not in str(r.json()) and "data_nascimento" not in str(r.json())


def test_busca_sem_acento_filtros_e_paginacao(cliente, equipe):
    _, h = equipe
    assert [c["nome"] for c in cliente.get(f"{URL}/ramais", params={"q": "celia coordenadora"}, headers=h["bia"]).json()["itens"]] == ["Célia Chefe"]
    assert {c["nome"] for c in cliente.get(f"{URL}/ramais", params={"setor": "Contratos"}, headers=h["bia"]).json()["itens"]} == {"Célia Chefe", "Davi Lima"}
    pag = cliente.get(f"{URL}/ramais", params={"tamanho": 2, "pagina": 2}, headers=h["bia"]).json()
    assert pag["total"] == 4 and len(pag["itens"]) == 2 and pag["pagina"] == 2
    filtros = cliente.get(f"{URL}/filtros", headers=h["bia"]).json()
    assert "TI" in filtros["setores"] and "3" in filtros["andares"]
    r = cliente.get(f"{URL}/ramais", params={"q": "99999"}, headers=h["bia"]).json()
    assert r["total"] == 0  # celular não entra na busca de texto; ramal sim
    bia = cliente.get(f"{URL}/ramais", params={"q": "bia"}, headers=h["davi"]).json()["itens"][0]
    assert bia["whatsapp_url"] == "https://wa.me/5511999990001" and bia["local"] == "5 andar - A"


def test_favoritos_vem_primeiro_e_e_por_usuario(cliente, equipe):
    ids, h = equipe
    assert cliente.put(f"{URL}/favoritos/{ids['eva']}", headers=h["bia"]).status_code == 204
    assert cliente.put(f"{URL}/favoritos/{ids['eva']}", headers=h["bia"]).status_code == 204  # idempotente
    itens = cliente.get(f"{URL}/ramais", headers=h["bia"]).json()["itens"]
    assert itens[0]["nome"] == "Eva Prado" and itens[0]["favorito"] is True
    assert cliente.get(f"{URL}/ramais", headers=h["davi"]).json()["itens"][0]["favorito"] is False
    assert [c["nome"] for c in cliente.get(f"{URL}/ramais", params={"favoritos": True}, headers=h["bia"]).json()["itens"]] == ["Eva Prado"]
    assert cliente.delete(f"{URL}/favoritos/{ids['eva']}", headers=h["bia"]).status_code == 204
    assert cliente.put(f"{URL}/favoritos/99999", headers=h["bia"]).status_code == 404


def test_detalhe_com_chefia_e_equipe(cliente, equipe):
    ids, h = equipe
    chefe = cliente.get(f"{URL}/ramais/{ids['celia']}", headers=h["bia"]).json()
    assert [e["nome"] for e in chefe["equipe"]] == ["Bia Souza", "Davi Lima"] and chefe["chefia"] is None
    assert cliente.get(f"{URL}/ramais/{ids['bia']}", headers=h["bia"]).json()["chefia"]["nome"] == "Célia Chefe"
    assert cliente.get(f"{URL}/ramais/99999", headers=h["bia"]).status_code == 404


def test_selo_de_ferias_aparece_e_some_sozinho(cliente, equipe):
    ids, h = equipe
    hoje = date.today()

    def agendar(inicio, fim, status="aprovado"):
        with FabricaSessao() as s:
            s.add(Afastamento(usuario_id=ids["davi"], tipo="ferias", inicio=inicio, fim=fim, dias=(fim - inicio).days + 1, exercicio=hoje.year, status=status))
            s.commit()

    def davi():
        return next(c for c in cliente.get(f"{URL}/ramais", headers=h["bia"]).json()["itens"] if c["nome"] == "Davi Lima")

    agendar(hoje + timedelta(days=5), hoje + timedelta(days=15))  # agendada: ainda sem selo
    assert davi()["ferias_fim"] is None
    agendar(hoje - timedelta(days=1), hoje + timedelta(days=4), "pendente")  # não aprovada: sem selo
    assert davi()["ferias_fim"] is None
    agendar(hoje - timedelta(days=2), hoje + timedelta(days=2))  # em curso: selo
    assert davi()["ferias_fim"] == (hoje + timedelta(days=2)).isoformat()
    assert [c["nome"] for c in cliente.get(f"{URL}/ramais", params={"em_ferias": True}, headers=h["bia"]).json()["itens"]] == ["Davi Lima"]
    # Depois do último dia o selo desaparece sem nenhuma ação (consulta feita 3 dias depois do fim)
    with FabricaSessao() as s:
        from app.models.usuario import Usuario
        pagina = servico_diretorio.listar_ramais(s, s.get(Usuario, ids["bia"]), servico_diretorio.FiltrosRamais(), 1, 50, hoje=hoje + timedelta(days=16))
        assert all(c.ferias_fim is None for c in pagina.itens)


def test_vcard_e_qrcode(cliente, equipe):
    ids, h = equipe
    r = cliente.get(f"{URL}/ramais/{ids['bia']}/vcard", headers=h["davi"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/vcard")
    assert "FN:Bia Souza" in r.text and "EMAIL;TYPE=WORK:bia@sp.gov.br" in r.text and "TEL;TYPE=CELL" in r.text
    q = cliente.get(f"{URL}/ramais/{ids['bia']}/qrcode", headers=h["davi"])
    assert q.status_code == 200 and q.content.startswith(b"\x89PNG")


def test_aniversariantes_dia_semana_mes_sem_ano(cliente, equipe):
    ids, h = equipe
    dia = cliente.get(f"{URL}/aniversariantes", params={"periodo": "dia"}, headers=h["davi"]).json()
    assert [a["nome"] for a in dia] == ["Bia Souza"] and dia[0]["e_hoje"] and dia[0]["dias_restantes"] == 0
    semana = cliente.get(f"{URL}/aniversariantes", params={"periodo": "semana"}, headers=h["davi"]).json()
    assert [a["nome"] for a in semana] == ["Bia Souza", "Davi Lima"] and semana[1]["dias_restantes"] == 3
    assert "1990" not in str(semana)
    mes = cliente.get(f"{URL}/aniversariantes", params={"periodo": "mes"}, headers=h["davi"]).json()
    assert {"Bia Souza"} <= {a["nome"] for a in mes} and all(a["nome"] != "Eva Prado" or a["dias_restantes"] == 20 for a in mes)
    assert cliente.get(f"{URL}/aniversariantes", params={"periodo": "ano"}, headers=h["davi"]).status_code == 422


def test_semana_na_virada_de_ano_e_29_de_fevereiro():
    nasc = date(1990, 1, 2)
    hoje = date(2026, 12, 28)
    assert servico_diretorio._proximo(nasc, hoje) == date(2027, 1, 2)
    assert servico_diretorio.ocorrencia_mais_proxima(nasc, hoje) == date(2027, 1, 2)
    assert servico_diretorio.ocorrencia_mais_proxima(nasc, date(2027, 1, 5)) == date(2027, 1, 2)
    assert servico_diretorio.data_no_ano(date(1992, 2, 29), 2027) == date(2027, 2, 28)
    assert servico_diretorio.data_no_ano(date(1992, 2, 29), 2028) == date(2028, 2, 29)


def test_opt_out_oculta_da_lista_e_do_mural(cliente, equipe):
    ids, h = equipe
    r = cliente.patch(f"{URL}/preferencias", json={"ocultar_aniversario": True}, headers=h["bia"])
    assert r.status_code == 200 and r.json()["ocultar_aniversario"] is True
    assert cliente.get(f"{URL}/aniversariantes", params={"periodo": "dia"}, headers=h["davi"]).json() == []
    assert cliente.post(f"{URL}/aniversariantes/{ids['bia']}/parabens", json={"texto": "Parabéns!"}, headers=h["davi"]).status_code == 404


def test_mural_de_parabens(cliente, equipe):
    ids, h = equipe
    url = f"{URL}/aniversariantes/{ids['bia']}/parabens"
    assert cliente.post(url, json={"texto": "  "}, headers=h["davi"]).status_code == 400  # só espaços
    r = cliente.post(url, json={"texto": "Parabéns, Bia! Muita saúde."}, headers=h["davi"])
    assert r.status_code == 201 and r.json()["meu"] is True
    assert cliente.post(url, json={"texto": "De novo"}, headers=h["davi"]).status_code == 409
    assert cliente.post(url, json={"texto": "Eu mesma"}, headers=h["bia"]).status_code == 400
    # A aniversariante recebe o aviso interno e vê o recado no mural
    with FabricaSessao() as s:
        avisos = list(s.scalars(select(Mensagem.assunto).join(EntregaMensagem).where(EntregaMensagem.destinatario_id == ids["bia"])))
    assert avisos == ["Davi Lima deixou um recado de aniversário para você"]
    mural = cliente.get(url, headers=h["celia"]).json()
    assert [(m["autor_nome"], m["meu"]) for m in mural] == [("Davi Lima", False)]
    lista = cliente.get(f"{URL}/aniversariantes", params={"periodo": "dia"}, headers=h["davi"]).json()[0]
    assert lista["total_parabens"] == 1 and lista["ja_parabenizei"] and lista["pode_parabenizar"]
    assert cliente.delete(url, headers=h["celia"]).status_code == 404
    assert cliente.delete(url, headers=h["davi"]).status_code == 204
    assert cliente.get(url, headers=h["celia"]).json() == []
    # Fora do dia do aniversário (daqui a 3 e a 20 dias) não se deixa recado, e o botão não é oferecido
    for outro in ("davi", "eva"):
        assert cliente.post(f"{URL}/aniversariantes/{ids[outro]}/parabens", json={"texto": "Cedo demais"}, headers=h["celia"]).status_code == 400
    semana = {a["nome"]: a for a in cliente.get(f"{URL}/aniversariantes", params={"periodo": "semana"}, headers=h["celia"]).json()}
    assert semana["Bia Souza"]["pode_parabenizar"] is True and semana["Davi Lima"]["pode_parabenizar"] is False


def test_foto_upload_reduz_serve_e_remove(cliente, equipe):
    ids, h = equipe
    assert cliente.put(f"{URL}/foto", files={"arquivo": ("x.png", b"<html>nao</html>", "image/png")}, headers=h["bia"]).status_code == 400
    r = cliente.put(f"{URL}/foto", files={"arquivo": ("eu.png", _png(), "image/png")}, headers=h["bia"])
    assert r.status_code == 200 and r.json()["foto_origem"] == "upload" and r.json()["foto_url"].startswith(f"/api/diretorio/fotos/{ids['bia']}")
    imagem = cliente.get(r.json()["foto_url"], headers=h["davi"])
    assert imagem.status_code == 200 and Image.open(BytesIO(imagem.content)).size == (400, 400)
    assert cliente.get(r.json()["foto_url"]).status_code == 401
    card = next(c for c in cliente.get(f"{URL}/ramais", params={"q": "bia"}, headers=h["davi"]).json()["itens"])
    assert card["foto_url"] == r.json()["foto_url"]
    assert cliente.delete(f"{URL}/foto", headers=h["bia"]).json()["foto_url"] is None
    assert cliente.get(f"{URL}/fotos/{ids['bia']}", headers=h["davi"]).status_code == 404


def test_foto_do_ldap_nao_sobrescreve_upload_e_nao_duplica(cliente, equipe):
    ids, h = equipe
    from app.models.usuario import Usuario
    with FabricaSessao() as s:
        bia, davi = s.get(Usuario, ids["bia"]), s.get(Usuario, ids["davi"])
        assert servico_diretorio.importar_foto_ldap(s, davi, _png(cor=(1, 2, 3))) is True
        s.commit()
        primeira = davi.foto_anexo_id
        assert servico_diretorio.importar_foto_ldap(s, davi, _png(cor=(1, 2, 3))) is False  # mesma foto: não regrava
        assert servico_diretorio.importar_foto_ldap(s, davi, _png(cor=(250, 2, 3))) is True  # mudou no AD
        assert davi.foto_anexo_id != primeira and davi.foto_origem == "ldap"
        assert servico_diretorio.importar_foto_ldap(s, davi, b"lixo") is False
        servico_diretorio.definir_foto(s, bia, _png(), "upload", bia.id)
        assert servico_diretorio.importar_foto_ldap(s, bia, _png(cor=(9, 9, 9))) is False  # upload do usuário prevalece
        s.commit()


def test_parabens_automatico_do_dia_sem_repetir(cliente, equipe):
    ids, h = equipe
    with FabricaSessao() as s:
        criadas = servico_diretorio.enviar_parabens_do_dia(s)
        assert len(criadas) == 1
        assert servico_diretorio.enviar_parabens_do_dia(s) == []  # segunda execução no mesmo dia não repete
    with FabricaSessao() as s:
        r = s.execute(select(EntregaMensagem.destinatario_id, Mensagem.assunto).join(Mensagem).where(Mensagem.assunto == "Feliz aniversário!")).all()
    assert r == [(ids["bia"], "Feliz aniversário!")]


def test_linkedin_no_perfil_normaliza_e_aparece_no_cartao(cliente, equipe):
    ids, h = equipe
    base = cliente.get("/api/autenticacao/perfil", headers=h["bia"]).json()
    corpo = {k: base[k] for k in ("nome_completo", "email", "ramal", "celular", "cargo", "departamento", "andar", "predio", "data_nascimento", "gestor_id")}
    for invalido in ("https://exemplo.com/in/bia", "javascript:alert(1)", "https://notlinkedin.com/in/x", "linkedin.com"):
        assert cliente.put("/api/autenticacao/perfil", json={**corpo, "linkedin": invalido}, headers=h["bia"]).status_code == 422, invalido
    r = cliente.put("/api/autenticacao/perfil", json={**corpo, "linkedin": "  www.linkedin.com/in/bia-souza/ "}, headers=h["bia"])
    assert r.status_code == 200, r.text
    assert cliente.get("/api/autenticacao/perfil", headers=h["bia"]).json()["linkedin"] == "https://www.linkedin.com/in/bia-souza"
    card = cliente.get(f"{URL}/ramais", params={"q": "bia"}, headers=h["davi"]).json()["itens"][0]
    assert card["linkedin"] == "https://www.linkedin.com/in/bia-souza"
    assert cliente.get(f"{URL}/ramais", params={"q": "davi"}, headers=h["bia"]).json()["itens"][0]["linkedin"] == ""
