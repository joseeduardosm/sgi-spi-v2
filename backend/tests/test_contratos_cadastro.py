# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar empresas, prepostos, cadastro, carteira e documentos do contrato.
"""MVP 1: empresas, prepostos, cadastro, carteira, detalhe, documentos e histórico do contrato."""

from datetime import date
from decimal import Decimal

from tests.apoio_contratos import PDF, criar_contrato, criar_empresa, dados_contrato, gerar_cnpj, gerar_cpf, item, restringir_contratos
from tests.conftest import cabecalho, criar_usuario

from app.schemas.contratos.validadores import cnpj_valido, cpf_valido
from app.services.contratos import calculos


# --- Cálculos --------------------------------------------------------------------------------

def test_datas_de_vigencia():
    """Fim da vigência, contagem de meses e montagem das vigências com prorrogação."""
    # 31/01 + 1 mês = 28/02 (fevereiro mais curto) − 1 dia = 27/02
    assert calculos.calcular_data_fim(date(2026, 1, 1), 12) == date(2026, 12, 31)
    assert calculos.calcular_data_fim(date(2026, 1, 31), 1) == date(2026, 2, 27)
    assert calculos.meses_em(date(2026, 1, 1), date(2026, 12, 31)) == 12
    assert calculos.meses_em(date(2026, 1, 15), date(2026, 1, 20)) == 1
    vigencias = calculos.montar_vigencias(date(2026, 1, 1), date(2027, 12, 31), 12, [(date(2027, 1, 1), date(2027, 12, 31))])
    assert [(v.sequencia, v.inicio, v.fim) for v in vigencias] == [
        (1, date(2026, 1, 1), date(2026, 12, 31)),
        (2, date(2027, 1, 1), date(2027, 12, 31)),
    ]


def test_situacao_do_contrato():
    """Ativo, a vencer (≤ 90 dias), encerrado e situação forçada."""
    fim = date(2026, 12, 31)
    assert calculos.calcular_situacao(fim, None, date(2026, 6, 1)) == "ativo"
    assert calculos.calcular_situacao(fim, None, date(2026, 10, 2)) == "a_vencer"
    assert calculos.calcular_situacao(fim, None, date(2027, 1, 1)) == "encerrado"
    assert calculos.calcular_situacao(fim, "suspenso", date(2026, 6, 1)) == "suspenso"


def test_valor_global_da_vigencia_atual():
    """Base mensal e valor global (12 meses do contínuo + limite do sob demanda)."""
    itens = [
        calculos.ItemValor("continuo", Decimal(2), Decimal(0), Decimal("1000")),
        calculos.ItemValor("sob_demanda", Decimal(0), Decimal(100), Decimal("10.50")),
    ]
    assert calculos.base_mensal(itens) == Decimal("2000.00")
    assert calculos.valor_global(itens, 12) == Decimal("25050.00")
    # Limite da vigência (prorrogação) substitui a quantidade original do item sob demanda
    assert calculos.valor_global(itens, 12, [None, Decimal(50)]) == Decimal("24525.00")
    assert calculos.valor_global(itens, 12, valor_reajustado=Decimal("30000")) == Decimal("30000.00")


def test_validadores_de_documentos():
    """CNPJ e CPF válidos (gerados) e inválidos."""
    assert cnpj_valido(gerar_cnpj("112223330001")) and not cnpj_valido("11222333000100")
    assert cpf_valido(gerar_cpf("123456789")) and not cpf_valido("11111111111")


# --- Empresas e prepostos ---------------------------------------------------------------------

def test_empresa_cnpj_unico_e_validado(cliente, admin):
    """CNPJ duplicado dá 409; dígito verificador errado dá 422."""
    empresa = criar_empresa(cliente, admin)
    assert len(empresa["cnpj"]) == 14
    repetida = {"cnpj": empresa["cnpj"], "razao_social": "Outra"}
    assert cliente.post("/api/contratos/empresas", json=repetida, headers=admin).status_code == 409
    r = cliente.post("/api/contratos/empresas", json={"cnpj": "11.222.333/0001-00", "razao_social": "X"}, headers=admin)
    assert r.status_code == 422 and "CNPJ inválido" in r.json()["detalhe"]


def test_prepostos_e_busca_em_qualquer_dado(cliente, admin):
    """Preposto com CPF único na empresa; a busca da empresa encontra pelo nome do preposto."""
    empresa = criar_empresa(cliente, admin)
    criar_empresa(cliente, admin, base="99888777", razao="Outra Empresa SA")
    preposto = {"cpf": gerar_cpf("123456789"), "nome": "Maria Preposta", "email": "maria@acme.com", "cargo": "Gerente"}
    r = cliente.post(f"/api/contratos/empresas/{empresa['id']}/prepostos", json=preposto, headers=admin)
    assert r.status_code == 201 and r.json()["prepostos"][0]["nome"] == "Maria Preposta"
    assert cliente.post(f"/api/contratos/empresas/{empresa['id']}/prepostos", json=preposto, headers=admin).status_code == 409

    lista = cliente.get("/api/contratos/empresas", params={"busca": "maria"}, headers=admin).json()
    assert lista["total"] == 1 and lista["itens"][0]["prepostos"] == ["Maria Preposta"]
    ordenada = cliente.get("/api/contratos/empresas", params={"ordenar": "razao_social", "direcao": "desc"}, headers=admin).json()
    assert [e["razao_social"] for e in ordenada["itens"]] == ["Outra Empresa SA", "ACME Serviços Ltda"]

    preposto_id = r.json()["prepostos"][0]["id"]
    alterado = {**preposto, "nome": "Maria Souza", "ativo": False}
    r = cliente.put(f"/api/contratos/empresas/{empresa['id']}/prepostos/{preposto_id}", json=alterado, headers=admin)
    assert r.json()["prepostos"][0] == {**r.json()["prepostos"][0], "nome": "Maria Souza", "ativo": False}
    assert cliente.delete(f"/api/contratos/empresas/{empresa['id']}/prepostos/{preposto_id}", headers=admin).status_code == 204


def test_empresa_com_contrato_nao_e_excluida_e_inativa_nao_e_opcao(cliente, admin):
    """Empresa com contrato não é excluída (409); inativa sai das opções e não pode ser usada."""
    contrato = criar_contrato(cliente, admin)
    empresa_id = contrato["empresa"]["id"]
    assert cliente.delete(f"/api/contratos/empresas/{empresa_id}", headers=admin).status_code == 409
    dados = {"cnpj": contrato["empresa"]["cnpj"], "razao_social": "ACME Serviços Ltda", "ativa": False}
    assert cliente.put(f"/api/contratos/empresas/{empresa_id}", json=dados, headers=admin).status_code == 200
    assert cliente.get("/api/contratos/empresas/opcoes", headers=admin).json() == []
    r = cliente.post("/api/contratos", json=dados_contrato(empresa_id, "002/2026"), headers=admin)
    assert r.status_code == 400 and "empresa ativa" in r.json()["detalhe"]


# --- Contrato -------------------------------------------------------------------------------

def test_cadastro_calcula_data_final_e_valor_global(cliente, admin):
    """O cadastro calcula data final, base mensal e valor global, e sugere o próximo número."""
    usuario_id = criar_usuario("gestora")
    contrato = criar_contrato(cliente, admin, equipe={"gestor": usuario_id})
    assert contrato["numero"] == "001/2026" and contrato["data_fim"] == "2026-12-31"
    assert contrato["base_mensal"] == "2000.00" and contrato["valor_global"] == "25050.00"
    assert [i["ordem"] for i in contrato["itens"]] == [1, 2]
    assert contrato["itens"][0]["unidade_fornecimento"] == "posto"
    assert contrato["itens"][0]["quantidade_total"] == "24.0000" and contrato["itens"][1]["quantidade_total"] == "100.0000"
    assert contrato["equipe"] == [{**contrato["equipe"][0], "papel": "gestor", "usuario_id": usuario_id, "login": "gestora"}]
    assert contrato["permissoes"] == {"pode_editar": True, "pode_excluir": True}
    assert contrato["data_limite_maxima"] == "2030-12-31"
    assert cliente.get("/api/contratos/proximo-numero", params={"ano": 2026}, headers=admin).json()["numero"] == "002/2026"


def test_numero_unico_e_regras_de_itens(cliente, admin):
    """Número repetido (mesmo sem zeros à esquerda) dá 409; itens e vigências inválidos dão 422."""
    contrato = criar_contrato(cliente, admin)
    r = cliente.post("/api/contratos", json=dados_contrato(contrato["empresa"]["id"], "1/2026"), headers=admin)
    assert r.status_code == 409
    r = cliente.post("/api/contratos", json=dados_contrato(contrato["empresa"]["id"], "002/2026", itens=[item(quantidade_mensal="0")]), headers=admin)
    assert r.status_code == 422
    r = cliente.post("/api/contratos", json=dados_contrato(contrato["empresa"]["id"], "002/2026", vigencia_maxima_meses=6), headers=admin)
    assert r.status_code == 422


def test_busca_por_numero_empresa_apelido_e_objeto(cliente, admin):
    """A carteira encontra por número, apelido, empresa e objeto."""
    contrato = criar_contrato(cliente, admin)
    criar_contrato(cliente, admin, empresa_id=contrato["empresa"]["id"], numero="002/2025", apelido="Vigilância", objeto="Vigilância patrimonial")
    for busca, esperado in [("001/2026", ["001/2026"]), ("vigil", ["002/2025"]), ("acme", ["001/2026", "002/2025"]), ("predial", ["001/2026"])]:
        r = cliente.get("/api/contratos", params={"busca": busca}, headers=admin).json()
        assert [c["numero"] for c in r["itens"]] == esperado, busca


def test_alteracao_com_versao_itens_e_historico(cliente, admin):
    """Alteração com versão correta; versão antiga dá 409; item salvo não muda nome; histórico registra a mudança."""
    contrato = criar_contrato(cliente, admin)
    # Reordena os itens (o sob demanda primeiro) e altera o preço do contínuo
    itens = [{**item(), "id": contrato["itens"][1]["id"], **_campos_item(contrato["itens"][1])}, {**item(), "id": contrato["itens"][0]["id"], "valor_unitario": "1100.00"}]
    dados = dados_contrato(contrato["empresa"]["id"], apelido="Limpeza anexo", itens=itens, versao=contrato["versao"])
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=admin)
    assert r.status_code == 200, r.text
    alterado = r.json()
    assert [i["descricao"] for i in alterado["itens"]] == ["Material", "Limpeza"] and alterado["versao"] == 2
    assert alterado["base_mensal"] == "2200.00"

    # Versão antiga → 409
    assert cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=admin).status_code == 409

    # Item salvo não muda nome
    itens[1]["descricao"] = "Limpeza pesada"
    dados.update(itens=itens, versao=2)
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=admin)
    assert r.status_code == 400 and "não pode mudar nome" in r.json()["detalhe"]

    historico = cliente.get(f"/api/contratos/{contrato['id']}/historico", headers=admin).json()
    assert {"campo": "apelido", "de": "Limpeza sede", "para": "Limpeza anexo"}.items() <= historico[0].items()


def _campos_item(lido: dict) -> dict:
    """Campos imutáveis do item lido + valores do sob demanda, para reenviar o item sem mudanças."""
    return {c: lido[c] for c in ("descricao", "tipo", "calcula_pro_rata")} | {"quantidade_mensal": "0", "quantidade_total": "100", "valor_unitario": "10.50"}


def test_equipe_troca_encerra_designacao_anterior(cliente, admin):
    """Trocar o fiscal encerra a designação anterior e aparece no histórico."""
    a, b = criar_usuario("fiscal-a"), criar_usuario("fiscal-b")
    contrato = criar_contrato(cliente, admin, equipe={"fiscal_tecnico": a})
    dados = dados_contrato(contrato["empresa"]["id"], equipe={"fiscal_tecnico": b}, versao=1,
                           itens=[{**item(), "id": contrato["itens"][0]["id"]}])
    dados["itens"].append({**_campos_item(contrato["itens"][1]), **{k: v for k, v in item().items() if k.startswith("codigo")}, "id": contrato["itens"][1]["id"]})
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=admin)
    assert r.status_code == 200, r.text
    assert [m["login"] for m in r.json()["equipe"]] == ["fiscal-b"]
    historico = cliente.get(f"/api/contratos/{contrato['id']}/historico", headers=admin).json()
    assert any(h["campo"] == "equipe.fiscal_tecnico" and h["para"] == "Pessoa Teste" for h in historico)


def test_poderes_iguais_da_equipe_e_bloqueio_de_estranhos(cliente, admin):
    """Os papéis da equipe têm poderes iguais; estranhos (mesmo com ACL) e leitores não alteram."""
    membro, estranho, leitor = criar_usuario("suplente"), criar_usuario("estranho"), criar_usuario("leitor")
    restringir_contratos(cliente, admin, {membro: "MODIFICACAO", estranho: "MODIFICACAO", leitor: "LEITURA"})
    contrato = criar_contrato(cliente, admin, equipe={"fiscal_tecnico_suplente": membro})
    dados = {**dados_contrato(contrato["empresa"]["id"], apelido="Novo"), "versao": 1}
    dados["itens"] = [{**item(), "id": contrato["itens"][0]["id"]}]
    dados["itens"].append({**item(), **_campos_item(contrato["itens"][1]), "id": contrato["itens"][1]["id"]})

    r = cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=cabecalho(cliente, "estranho"))
    assert r.status_code == 403 and r.json()["codigo"] == "acesso_negado"
    assert cliente.get(f"/api/contratos/{contrato['id']}", headers=cabecalho(cliente, "estranho")).json()["permissoes"]["pode_editar"] is False
    assert cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=cabecalho(cliente, "leitor")).status_code == 403
    r = cliente.put(f"/api/contratos/{contrato['id']}", json=dados, headers=cabecalho(cliente, "suplente"))
    assert r.status_code == 200, r.text
    # Exclusão só com CONTROLE_TOTAL
    assert cliente.delete(f"/api/contratos/{contrato['id']}", headers=cabecalho(cliente, "suplente")).status_code == 403
    assert cliente.delete(f"/api/contratos/{contrato['id']}", headers=admin).status_code == 204


def test_documentos_importantes(cliente, admin):
    """Catálogo de 23 documentos, envio, download com nome padronizado e recusas."""
    contrato = criar_contrato(cliente, admin, numero="012/2026")
    documentos = cliente.get(f"/api/contratos/{contrato['id']}/documentos", headers=admin).json()
    assert len(documentos) == 23 and not any(d["anexado"] for d in documentos)
    url = f"/api/contratos/{contrato['id']}/documentos/12"
    r = cliente.post(url, files={"arquivo": ("contrato.pdf", PDF, "application/pdf")}, headers=admin)
    assert r.status_code == 200, r.text
    assinado = next(d for d in r.json() if d["codigo"] == 12)
    assert assinado["anexado"] and assinado["tamanho"] == len(PDF) and assinado["nome_arquivo"] == "CONTRATO_ASSINADO_SPI_012_2026.pdf"
    download = cliente.get(f"{url}/arquivo", headers=admin)
    assert download.content == PDF and "CONTRATO_ASSINADO_SPI_012_2026.pdf" in download.headers["content-disposition"]
    r = cliente.post(url, files={"arquivo": ("x.pdf", b"nao e pdf", "application/pdf")}, headers=admin)
    assert r.status_code == 400
    assert cliente.post(f"/api/contratos/{contrato['id']}/documentos/24", files={"arquivo": ("x.pdf", PDF)}, headers=admin).status_code == 400
    assert cliente.get(f"/api/contratos/{contrato['id']}/documentos/1/arquivo", headers=admin).status_code == 404
