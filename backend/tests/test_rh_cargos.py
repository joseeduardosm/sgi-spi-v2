# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar cargos (vagas por setor), ocupação, exoneração, reconciliação, organograma e histórico funcional do RH.
"""Cargos do RH: vagas em lote, quem ocupa, setor pelo cargo, troca e exoneração, histórico com autor e data, PDF e organograma."""

import io

import pytest
from pypdf import PdfReader

from app.services.rh.cargo_legado import interpretar
from tests.apoio_rh import criar_cgp
from tests.conftest import cabecalho, criar_usuario

RH = "/api/rh"


def test_interpretar_cargo_do_texto_livre():
    c = interpretar("FCESP 2.16 - Assessor Especial IV")
    assert (c.tipo, c.grupo, c.nivel, c.denominacao, c.interpretado) == ("FCESP", 2, 16, "Assessor Especial IV", True)
    c = interpretar("ccesp 1.15 – Diretor")
    assert (c.tipo, c.grupo, c.nivel, c.denominacao) == ("CCESP", 1, 15, "Diretor")
    c = interpretar("Analista de TI")
    c2 = interpretar("Assessor II - CCESP  2.10")
    assert (c2.tipo, c2.grupo, c2.nivel, c2.denominacao) == ("CCESP", 2, 10, "Assessor II")
    c3 = interpretar("Secretário Executivo - CCESP 1.18 (NES)")
    assert (c3.grupo, c3.nivel, c3.denominacao) == (1, 18, "Secretário Executivo")
    assert (c.tipo, c.grupo, c.nivel, c.interpretado) == ("OUTRO", None, None, False) and c.denominacao == "Analista de TI"
    assert interpretar("CCESP 2.20 - Nivel inexistente").interpretado is False and interpretar("  ") is None


@pytest.fixture
def ambiente(cliente, admin):
    """O RH (membro da CGP), uma pessoa sem acesso, dois setores e os tipos de cargo."""
    rh = criar_usuario("rh-cargos", nome_completo="Rita do RH")
    pessoa = criar_usuario("fulano", nome_completo="Fulano de Tal", cargo="", departamento="")
    outra = criar_usuario("beltrana", nome_completo="Beltrana Silva", cargo="Analista", departamento="Outro Setor")
    criar_cgp(rh)
    h = cabecalho(cliente, "rh-cargos")
    setor_a = cliente.post("/api/setores", json={"nome": "Subsecretaria de Gestão Corporativa", "sigla": "SGC", "tipo_unidade": "subsecretaria"}, headers=h).json()
    setor_b = cliente.post("/api/setores", json={"nome": "Diretoria de Gestão Administrativa", "setor_pai_id": setor_a["id"], "tipo_unidade": "diretoria"}, headers=h).json()
    tipos = {t["codigo"]: t["id"] for t in cliente.get(f"{RH}/tipos-cargo", headers=h).json()}
    return {"h": h, "pessoa": pessoa, "outra": outra, "a": setor_a, "b": setor_b, "tipos": tipos}


def _criar(cliente, amb, setor, tipo="FCESP", grupo=2, nivel=16, denominacao="Assessor Especial IV", quantidade=1):
    r = cliente.post(f"{RH}/cargos", json={"setor_id": setor["id"], "tipo_id": amb["tipos"][tipo], "grupo": grupo, "nivel": nivel, "denominacao": denominacao, "quantidade": quantidade}, headers=amb["h"])
    assert r.status_code == 201, r.text
    return r.json()


def test_setor_ganha_sigla_e_tipo_e_cargos_sao_vagas_em_lote(cliente, ambiente):
    amb = ambiente
    assert amb["a"]["sigla"] == "SGC" and amb["a"]["tipo_unidade"] == "subsecretaria"
    vagas = _criar(cliente, amb, amb["a"], quantidade=3)
    assert len(vagas) == 3 and {v["rotulo"] for v in vagas} == {"FCESP 2.16 – Assessor Especial IV"} and all(v["ocupante"] is None for v in vagas)
    # CCESP/FCESP exigem grupo e nível; os dois vêm juntos
    r = cliente.post(f"{RH}/cargos", json={"setor_id": amb["a"]["id"], "tipo_id": amb["tipos"]["CCESP"], "denominacao": "Sem nível"}, headers=amb["h"])
    assert r.status_code == 400
    r = cliente.post(f"{RH}/cargos", json={"setor_id": amb["a"]["id"], "tipo_id": amb["tipos"]["OUTRO"], "grupo": 1, "denominacao": "Só grupo"}, headers=amb["h"])
    assert r.status_code == 400
    outro = cliente.post(f"{RH}/cargos", json={"setor_id": amb["a"]["id"], "tipo_id": amb["tipos"]["OUTRO"], "denominacao": "Analista"}, headers=amb["h"]).json()[0]
    assert outro["rotulo"] == "Analista" and outro["classificacao"] == "OUTRO"
    assert len(cliente.get(f"{RH}/cargos", params={"situacao": "vago"}, headers=amb["h"]).json()) == 4


def test_ocupar_faz_a_pessoa_entrar_no_setor_pelo_cargo_e_vai_para_o_historico(cliente, ambiente):
    amb = ambiente
    vaga = _criar(cliente, amb, amb["a"])[0]
    r = cliente.post(f"{RH}/cargos/{vaga['id']}/ocupacao", json={"usuario_id": amb["pessoa"], "inicio": "2026-03-02", "ato": "Resolução SPI 12/2026"}, headers=amb["h"])
    assert r.status_code == 201, r.text
    assert r.json()["ocupante"]["nome"] == "Fulano de Tal" and r.json()["ocupante"]["inicio"] == "2026-03-02"
    # Espelho no perfil e participação no setor
    from app.core.banco import FabricaSessao
    from app.models.usuario import Usuario

    with FabricaSessao() as sessao:
        pessoa = sessao.get(Usuario, amb["pessoa"])
        assert pessoa.cargo == "FCESP 2.16 – Assessor Especial IV" and pessoa.departamento == "Subsecretaria de Gestão Corporativa"
    membros = cliente.get(f"/api/setores/{amb['a']['id']}", headers=amb["h"]).json()["membros"]
    assert [m["login"] for m in membros] == ["fulano"]
    # O cargo ocupado não se ocupa de novo nem se muda de setor
    assert cliente.post(f"{RH}/cargos/{vaga['id']}/ocupacao", json={"usuario_id": amb["outra"]}, headers=amb["h"]).status_code == 409
    mudar = {"setor_id": amb["b"]["id"], "tipo_id": amb["tipos"]["FCESP"], "grupo": 2, "nivel": 16, "denominacao": "Assessor Especial IV"}
    assert cliente.put(f"{RH}/cargos/{vaga['id']}", json=mudar, headers=amb["h"]).status_code == 409
    # Histórico: o fato, com quem registrou
    historico = cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", headers=amb["h"]).json()
    titulos = [e["titulo"] for e in historico["eventos"]]
    assert any("Assumiu FCESP 2.16 – Assessor Especial IV no setor Subsecretaria de Gestão Corporativa" in t for t in titulos)
    assert all(e["autor_nome"] == "Rita do RH" for e in historico["eventos"]) and historico["ocupacoes"][0]["ato"] == "Resolução SPI 12/2026"


def test_trocar_de_cargo_e_exoneracao(cliente, ambiente):
    amb = ambiente
    a = _criar(cliente, amb, amb["a"])[0]
    b = _criar(cliente, amb, amb["b"], tipo="CCESP", grupo=1, nivel=15, denominacao="Diretor")[0]
    assert cliente.post(f"{RH}/cargos/{a['id']}/ocupacao", json={"usuario_id": amb["pessoa"], "inicio": "2026-01-10"}, headers=amb["h"]).status_code == 201
    # Ocupar outro cargo encerra o anterior (troca) e muda a pessoa de setor
    assert cliente.post(f"{RH}/cargos/{b['id']}/ocupacao", json={"usuario_id": amb["pessoa"], "inicio": "2026-06-01"}, headers=amb["h"]).status_code == 201
    anterior = next(c for c in cliente.get(f"{RH}/cargos", headers=amb["h"]).json() if c["id"] == a["id"])
    assert anterior["ocupante"] is None
    assert [m["login"] for m in cliente.get(f"/api/setores/{amb['a']['id']}", headers=amb["h"]).json()["membros"]] == []
    assert [m["login"] for m in cliente.get(f"/api/setores/{amb['b']['id']}", headers=amb["h"]).json()["membros"]] == ["fulano"]
    # Exoneração: encerra, tira do setor e fica no histórico como tipo próprio
    r = cliente.post(f"{RH}/cargos/{b['id']}/vacancia", json={"fim": "2026-09-30", "motivo": "exoneracao", "ato": "Decreto de 30/09/2026"}, headers=amb["h"])
    assert r.status_code == 200 and r.json()["ocupante"] is None
    assert cliente.post(f"{RH}/cargos/{b['id']}/vacancia", json={}, headers=amb["h"]).status_code == 409
    h = cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", headers=amb["h"]).json()
    assert [e["tipo"] for e in h["eventos"] if e["tipo"] == "exoneracao"] == ["exoneracao"]
    assert [o["motivo_fim"] for o in h["ocupacoes"]] == ["exoneracao", "troca"]
    # Cargo que já teve ocupante (e está vago) pode ser excluído; o histórico de ocupações dele sai junto
    assert cliente.delete(f"{RH}/cargos/{b['id']}", headers=amb["h"]).status_code == 204
    assert [o["motivo_fim"] for o in cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", headers=amb["h"]).json()["ocupacoes"]] == ["troca"]
    vazia = _criar(cliente, amb, amb["a"], denominacao="Vaga nunca ocupada")[0]
    assert cliente.delete(f"{RH}/cargos/{vazia['id']}", headers=amb["h"]).status_code == 204


def test_reconciliar_cadastros_antigos_cria_o_cargo_do_texto_e_vincula(cliente, ambiente):
    amb = ambiente
    antigo = criar_usuario("antigo", nome_completo="Antigo Cadastro", cargo="FCESP 2.16 - Assessor Especial IV", departamento="Subsecretaria de Gestão Corporativa")
    sem_setor = criar_usuario("sem-setor", nome_completo="Sem Setor", cargo="Analista de TI", departamento="Setor que não existe")
    pend = {p["login"]: p for p in cliente.get(f"{RH}/cargos-a-reconciliar", headers=amb["h"]).json()}
    assert pend["antigo"]["interpretado"] is True and pend["antigo"]["setor_id"] == amb["a"]["id"] and pend["antigo"]["sugestao"].startswith("FCESP 2.16")
    assert pend["sem-setor"]["interpretado"] is False and pend["sem-setor"]["setor_id"] is None
    r = cliente.post(f"{RH}/cargos-a-reconciliar/{antigo}", json={}, headers=amb["h"])
    assert r.status_code == 200 and r.json()["rotulo"] == "FCESP 2.16 – Assessor Especial IV" and r.json()["ocupante"]["login"] == "antigo"
    # Sem setor correspondente, é preciso informar o setor
    assert cliente.post(f"{RH}/cargos-a-reconciliar/{sem_setor}", json={}, headers=amb["h"]).status_code == 400
    r = cliente.post(f"{RH}/cargos-a-reconciliar/{sem_setor}", json={"setor_id": amb["b"]["id"]}, headers=amb["h"])
    assert r.status_code == 200 and r.json()["tipo_codigo"] == "OUTRO" and r.json()["setor_nome"] == "Diretoria de Gestão Administrativa"
    assert "antigo" not in {p["login"] for p in cliente.get(f"{RH}/cargos-a-reconciliar", headers=amb["h"]).json()}


def test_organograma_e_permissoes(cliente, ambiente):
    amb = ambiente
    vaga = _criar(cliente, amb, amb["a"], quantidade=3)
    ldap = criar_usuario("ldap1", nome_completo="Pessoa do AD", origem="ldap")
    # Uma vaga com pessoa do LDAP, outra com conta local (fica fora do organograma) e uma vazia
    cliente.post(f"{RH}/cargos/{vaga[0]['id']}/ocupacao", json={"usuario_id": ldap}, headers=amb["h"])
    cliente.post(f"{RH}/cargos/{vaga[1]['id']}/ocupacao", json={"usuario_id": amb["pessoa"]}, headers=amb["h"])
    raiz = next(n for n in cliente.get(f"{RH}/organograma", headers=amb["h"]).json() if n["setor_id"] == amb["a"]["id"])
    assert raiz["sigla"] == "SGC" and raiz["total_posicoes"] == 2 and raiz["total_vagas"] == 1 and [f["nome"] for f in raiz["filhos"]] == ["Diretoria de Gestão Administrativa"]
    assert [p["ocupante"]["login"] if p["ocupante"] else None for p in raiz["posicoes"]] == ["ldap1", None]
    assert raiz["lider"] is None and raiz["lider_nome"] is None  # setor sem líder definido
    sem_vagas = next(n for n in cliente.get(f"{RH}/organograma", params={"incluir_vagas": "false"}, headers=amb["h"]).json() if n["setor_id"] == amb["a"]["id"])
    assert len(sem_vagas["posicoes"]) == 1 and sem_vagas["total_vagas"] == 1
    # Quem não está no RH não consulta nem altera
    comum = cabecalho(cliente, "beltrana")
    assert cliente.get(f"{RH}/cargos", headers=comum).status_code == 403
    # O organograma é aberto, mas sem as vagas para quem não é do RH nem lidera o setor
    vagas_de = lambda cab, setor: next(n for n in cliente.get(f"{RH}/organograma", headers=cab).json() if n["setor_id"] == setor["id"])
    assert vagas_de(comum, amb["a"])["total_vagas"] == 0 and all(p["ocupante"] for p in vagas_de(comum, amb["a"])["posicoes"])
    assert cliente.post(f"{RH}/cargos", json={"setor_id": amb["a"]["id"], "tipo_id": amb["tipos"]["OUTRO"], "denominacao": "X"}, headers=comum).status_code == 403


def test_historico_so_para_o_rh_e_a_propria_pessoa_e_exporta_pdf(cliente, ambiente):
    amb = ambiente
    vaga = _criar(cliente, amb, amb["a"])[0]
    cliente.post(f"{RH}/cargos/{vaga['id']}/ocupacao", json={"usuario_id": amb["pessoa"], "ato": "Resolução 7"}, headers=amb["h"])
    proprio, outra = cabecalho(cliente, "fulano"), cabecalho(cliente, "beltrana")
    assert cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", headers=proprio).status_code == 200
    assert cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", headers=outra).status_code == 403
    assert cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico.pdf", headers=outra).status_code == 403
    # Filtro por tipo
    so_setor = cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico", params={"tipos": ["setor"]}, headers=amb["h"]).json()
    assert {e["tipo"] for e in so_setor["eventos"]} == {"setor"}
    r = cliente.get(f"{RH}/usuarios/{amb['pessoa']}/historico.pdf", headers=proprio)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    texto = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    assert "Histórico funcional" in texto and "Fulano de Tal" in texto and "Assumiu FCESP 2.16" in texto and "Rita do RH" in texto


def test_busca_de_usuarios_acha_cargo_setor_chefia_e_dados_do_rh(cliente, ambiente):
    """A busca da lista de usuários procura no cargo, no setor, na chefia imediata e mediata; os dados funcionais só valem para o RH."""
    from tests.apoio_rh import funcionais

    amb = ambiente
    chefe_a = criar_usuario("chefe-a", nome_completo="Marlene Chefona")
    chefe_b = criar_usuario("chefe-b", nome_completo="Otávio Diretor")
    # Líder da subsecretaria (A) e da diretoria filha (B)
    cliente.put(f"/api/setores/{amb['a']['id']}", json={"nome": amb["a"]["nome"], "sigla": "SGC", "tipo_unidade": "subsecretaria", "lider_id": chefe_a}, headers=amb["h"])
    cliente.put(f"/api/setores/{amb['b']['id']}", json={"nome": amb["b"]["nome"], "setor_pai_id": amb["a"]["id"], "tipo_unidade": "diretoria", "lider_id": chefe_b}, headers=amb["h"])
    vaga = _criar(cliente, amb, amb["b"], tipo="CCESP", grupo=2, nivel=10, denominacao="Assessor II")[0]
    cliente.post(f"{RH}/cargos/{vaga['id']}/ocupacao", json={"usuario_id": amb["pessoa"]}, headers=amb["h"])
    funcionais(amb["pessoa"], rs_pv="RS-998877", rg_cin="12.345.678-9")

    def logins(texto, headers):
        r = cliente.get("/api/usuarios", params={"busca": texto}, headers=headers)
        assert r.status_code == 200, r.text
        itens = r.json()["itens"]
        return {u["login"] for u in itens}

    rh, comum = amb["h"], cabecalho(cliente, "beltrana")
    assert "fulano" in logins("assessor", rh) and "fulano" in logins("CCESP 2.10", rh)        # cargo (denominação e classificação)
    assert "fulano" in logins("gestão administrativa", rh)                                    # setor do cargo
    assert "fulano" in logins("otávio", rh) and "fulano" in logins("marlene", rh)             # chefia imediata e mediata
    assert "fulano" in logins("assessor otávio", rh) and "fulano" not in logins("assessor zzz", rh)  # todas as palavras
    assert "fulano" in logins("998877", rh) and "fulano" in logins("12.345.678", rh)          # dados funcionais: só o RH
    assert "fulano" not in logins("998877", comum)


def test_vagas_so_para_a_lideranca_do_setor_e_a_cadeia_acima(cliente, ambiente):
    """O líder do setor e os líderes acima veem as vagas; liderados, colegas e líderes de outros setores não."""
    from app.core.banco import FabricaSessao
    from app.models.setor import Setor

    amb = ambiente
    _criar(cliente, amb, amb["a"], quantidade=2)  # vagas no setor pai (a)
    _criar(cliente, amb, amb["b"], quantidade=1)  # e no filho (b)
    chefe_a, chefe_b = criar_usuario("chefe-a", nome_completo="Chefe A"), criar_usuario("chefe-b", nome_completo="Chefe B")
    outro = cliente.post("/api/setores", json={"nome": "Setor Vizinho", "tipo_unidade": "diretoria"}, headers=amb["h"]).json()
    chefe_v = criar_usuario("chefe-v", nome_completo="Chefe V")
    with FabricaSessao() as sessao:
        sessao.get(Setor, amb["a"]["id"]).lider_id = chefe_a
        sessao.get(Setor, amb["b"]["id"]).lider_id = chefe_b
        sessao.get(Setor, outro["id"]).lider_id = chefe_v
        sessao.commit()
    def vagas(login):
        arvore = cliente.get(f"{RH}/organograma", headers=cabecalho(cliente, login)).json()
        pai = next(n for n in arvore if n["setor_id"] == amb["a"]["id"])
        filho = pai["filhos"][0]
        return pai["total_vagas"], filho["total_vagas"]
    assert vagas("chefe-a") == (2, 1)   # o líder do pai vê as vagas dele e as do filho (cadeia para baixo)
    assert vagas("chefe-b") == (0, 1)   # o líder do filho vê só as do filho: quem está abaixo não vê as do pai
    assert vagas("chefe-v") == (0, 0)   # líder de outro setor, mesmo nível: nada
    assert vagas("beltrana") == (0, 0)  # pessoa comum: nada
    arvore_rh = cliente.get(f"{RH}/organograma", headers=amb["h"]).json()
    assert next(n for n in arvore_rh if n["setor_id"] == amb["a"]["id"])["total_vagas"] == 2  # o RH vê tudo


def test_busca_pelo_nome_do_chefe_traz_ele_primeiro_e_o_seletor_so_ele(cliente, ambiente):
    """Na lista de usuários, quem tem o nome pesquisado vem antes dos liderados que só casaram pela chefia; nos seletores de pessoa a busca é só pela própria pessoa."""
    from app.core.banco import FabricaSessao
    from app.models.setor import Setor

    amb = ambiente
    chefe = criar_usuario("zz-chefe", nome_completo="Zélia Chefe da Silva", cargo="Subsecretária", departamento="Subsecretaria de Gestão Corporativa")
    with FabricaSessao() as sessao:
        sessao.get(Setor, amb["a"]["id"]).lider_id = chefe
        sessao.commit()
    # Uma pessoa com cargo no setor chefiado: acha "zélia" pela chefia, mas não é a Zélia
    vaga = _criar(cliente, amb, amb["a"])[0]
    assert cliente.post(f"{RH}/cargos/{vaga['id']}/ocupacao", json={"usuario_id": amb["outra"]}, headers=amb["h"]).status_code == 201
    lista = cliente.get("/api/usuarios", params={"busca": "zélia"}, headers=amb["h"]).json()["itens"]
    logins = [u["login"] for u in lista]
    assert logins[0] == "zz-chefe" and "beltrana" in logins  # o chefe primeiro; o liderado também aparece (busca por chefia)
    # Seletor (ex.: notificações): só a própria pessoa, nunca os liderados
    seletor = cliente.get("/api/usuarios/opcoes", params={"busca": "zélia"}, headers=amb["h"]).json()
    assert [u["login"] for u in seletor] == ["zz-chefe"]


def test_vinculo_automatico_fica_sem_data_de_posse_e_permite_realocar(cliente, ambiente):
    amb = ambiente
    antigo = criar_usuario("antigo2", nome_completo="Antigo Cadastro", cargo="FCESP 2.16 - Assessor Especial IV", departamento="Subsecretaria de Gestão Corporativa")
    r = cliente.post(f"{RH}/cargos-a-reconciliar/{antigo}", json={}, headers=amb["h"])
    assert r.status_code == 200 and r.json()["ocupante"]["login"] == "antigo2"
    assert r.json()["ocupante"]["inicio"] is None and r.json()["ocupante"]["ato"] == "Vínculo do cadastro anterior"
    historico = cliente.get(f"{RH}/usuarios/{antigo}/historico", headers=amb["h"]).json()
    assert historico["ocupacoes"][0]["inicio"] is None
    # Realocar: ocupar outro cargo, com qualquer data de posse, encerra o vínculo automático como troca
    novo = _criar(cliente, amb, amb["b"], tipo="CCESP", grupo=1, nivel=15, denominacao="Diretor")[0]
    r = cliente.post(f"{RH}/cargos/{novo['id']}/ocupacao", json={"usuario_id": antigo, "inicio": "2020-01-10"}, headers=amb["h"])
    assert r.status_code == 201, r.text
    historico = cliente.get(f"{RH}/usuarios/{antigo}/historico", headers=amb["h"]).json()
    assert [(o["inicio"], o["motivo_fim"]) for o in historico["ocupacoes"]] == [("2020-01-10", None), (None, "troca")]


def test_excluir_cargo_ocupado_ou_com_admissao_ativa_responde_409(cliente, ambiente):
    amb = ambiente
    ocupada = _criar(cliente, amb, amb["a"], denominacao="Vaga ocupada")[0]
    assert cliente.post(f"{RH}/cargos/{ocupada['id']}/ocupacao", json={"usuario_id": amb["pessoa"], "inicio": "2026-01-10"}, headers=amb["h"]).status_code == 201
    assert cliente.delete(f"{RH}/cargos/{ocupada['id']}", headers=amb["h"]).status_code == 409  # ocupado agora: vague antes
    from app.core.banco import FabricaSessao
    from app.models.rh_admissao import Admissao
    from app.models.rh_pre_cadastro import PreCadastro

    vaga = _criar(cliente, amb, amb["a"], denominacao="Vaga com admissão")[0]
    with FabricaSessao() as sessao:
        ficha = PreCadastro(nome_completo="Pessoa Teste", cpf="52998224725", status="rascunho")
        sessao.add(ficha)
        sessao.flush()
        admissao = Admissao(pre_cadastro_id=ficha.id, cargo_id=vaga["id"], status="andamento")
        sessao.add(admissao)
        sessao.commit()
        admissao_id = admissao.id
    r = cliente.delete(f"{RH}/cargos/{vaga['id']}", headers=amb["h"])
    assert r.status_code == 409 and "admissão" in r.json()["detalhe"]
    # Admissão cancelada não impede: sai junto com a vaga
    with FabricaSessao() as sessao:
        sessao.get(Admissao, admissao_id).status = "cancelada"
        sessao.commit()
    assert cliente.delete(f"{RH}/cargos/{vaga['id']}", headers=amb["h"]).status_code == 204
    with FabricaSessao() as sessao:
        assert sessao.get(Admissao, admissao_id) is None
