# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o módulo Chamados de ponta a ponta (marco 1): abrir, ver na fila, assumir, responder e resolver.
"""Módulo Chamados (`/api/chamados`), marco 1.

Cenário montado pela API como o SuperRoot: expediente comercial, SLAs de atendimento (15 min) e solução (4 h), o setor "Suporte TI"
com um técnico, a categoria "Informática" (setor Suporte TI) e a subcategoria "Impressoras" (herda tudo). Na ACL: o solicitante com
Leitura e o técnico com Modificação. O módulo nasce fechado: sem regras, só o SuperRoot entra.
"""

import base64
import json

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.chamados import AnexoChamado, Chamado
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.setor import Setor
from tests.conftest import cabecalho, criar_usuario

BASE = "/api/chamados"
PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _recurso(cliente, admin) -> int:
    r = cliente.post("/api/acl/recursos", json={"nome": "Chamados", "slug": "chamados"}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _regra(cliente, admin, recurso_id, nivel, usuarios=(), setores=()):
    corpo = {"recurso_id": recurso_id, "nivel": nivel, "usuarios_ids": list(usuarios), "setores_ids": list(setores)}
    r = cliente.post("/api/acl/regras", json=corpo, headers=admin)
    assert r.status_code == 201, r.text


def _setor(cliente, admin, nome, membros) -> int:
    r = cliente.post("/api/setores", json={"nome": nome, "membros_ids": membros}, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _abrir(cliente, cab, categoria_id, titulo="Impressora não imprime", descricao="<p>A impressora do 3º andar parou.</p>", arquivos=None, **extras):
    dados = {"titulo": titulo, "descricao": descricao, "categoria_id": categoria_id, **extras}
    return cliente.post(BASE, data={"dados": json.dumps(dados)}, files=arquivos or [], headers=cab)


def _responder(cliente, cab, numero, texto, privado=False):
    return cliente.post(f"{BASE}/{numero}/acompanhamentos", data={"dados": json.dumps({"texto": texto, "privado": privado})}, headers=cab)


def _preparar(cliente, admin) -> dict:
    """Monta o cenário e devolve ids e cabeçalhos."""
    ids = {"solicitante": criar_usuario("maria"), "tecnico": criar_usuario("joao"), "outro": criar_usuario("pedro")}
    ids["setor_ti"] = _setor(cliente, admin, "Suporte TI", [ids["tecnico"]])
    ids["setor_rh"] = _setor(cliente, admin, "Coordenadoria de Pessoas", [ids["solicitante"], ids["outro"]])
    recurso = _recurso(cliente, admin)
    _regra(cliente, admin, recurso, "LEITURA", usuarios=[ids["solicitante"], ids["outro"]])
    _regra(cliente, admin, recurso, "MODIFICACAO", usuarios=[ids["tecnico"]])
    faixas = [{"dia_semana": d, "inicio": "08:00", "fim": "18:00"} for d in range(5)]
    r = cliente.post(f"{BASE}/parametros/expedientes", json={"nome": "Comercial", "faixas": faixas}, headers=admin)
    assert r.status_code == 201, r.text
    expediente = r.json()["id"]
    tto = cliente.post(f"{BASE}/parametros/slas", json={"nome": "Atendimento", "tipo": "tto", "tempo": 15, "unidade": "minuto", "expediente_id": expediente}, headers=admin)
    ttr = cliente.post(f"{BASE}/parametros/slas", json={"nome": "Solução", "tipo": "ttr", "tempo": 4, "unidade": "hora", "expediente_id": expediente}, headers=admin)
    assert tto.status_code == ttr.status_code == 201, tto.text + ttr.text
    raiz = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "Informática", "setor_id": ids["setor_ti"], "sla_tto_id": tto.json()["id"],
                                                               "sla_ttr_id": ttr.json()["id"]}, headers=admin)
    assert raiz.status_code == 201, raiz.text
    filha = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "Impressoras", "pai_id": raiz.json()["id"]}, headers=admin)
    assert filha.status_code == 201, filha.text
    ids.update(raiz=raiz.json()["id"], categoria=filha.json()["id"], expediente=expediente)
    cab = {k: cabecalho(cliente, login) for k, login in (("solicitante", "maria"), ("tecnico", "joao"), ("outro", "pedro"))}
    return {"ids": ids, "cab": cab}


def test_modulo_fechado_ate_haver_regras(cliente, admin):
    criar_usuario("maria")
    cab = cabecalho(cliente, "maria")
    r = cliente.get(f"{BASE}/contexto", headers=cab)
    assert r.status_code == 200 and r.json()["papeis"] == {"abrir": False, "atender": False, "administrar": False}
    r = cliente.get(f"{BASE}/catalogo", headers=cab)
    assert r.status_code == 403 and r.json()["codigo"] == "acl_negado"
    raiz = cliente.get(f"{BASE}/contexto", headers=admin)
    assert raiz.status_code == 200 and raiz.json()["papeis"] == {"abrir": True, "atender": True, "administrar": True}


def test_parametros_impedem_configuracao_errada(cliente, admin):
    c = _preparar(cliente, admin)
    # Categoria raiz ativa sem setor responsável
    r = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "Sem dono"}, headers=admin)
    assert r.status_code == 400 and r.json()["codigo"] == "categoria_sem_setor"
    # SLA sem expediente não passa nem na validação
    r = cliente.post(f"{BASE}/parametros/slas", json={"nome": "24x7", "tipo": "ttr", "tempo": 4, "unidade": "hora"}, headers=admin)
    assert r.status_code == 422
    # Expediente sem faixas
    r = cliente.post(f"{BASE}/parametros/expedientes", json={"nome": "Vazio", "faixas": []}, headers=admin)
    assert r.status_code == 422
    # Nome repetido no mesmo nível
    r = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "impressoras", "pai_id": c["ids"]["raiz"]}, headers=admin)
    assert r.status_code == 409
    # Tirar o setor da raiz deixaria a filha sem setor herdado
    r = cliente.put(f"{BASE}/parametros/categorias/{c['ids']['raiz']}", json={"nome": "Informática", "setor_id": None}, headers=admin)
    assert r.status_code == 400 and r.json()["codigo"] == "categoria_sem_setor"
    # Só quem administra mexe nos Parâmetros
    assert cliente.get(f"{BASE}/parametros/categorias", headers=c["cab"]["tecnico"]).status_code == 403
    lista = cliente.get(f"{BASE}/parametros/categorias", headers=admin).json()
    filha = next(x for x in lista if x["nome"] == "Impressoras")
    assert filha["caminho"] == "Informática > Impressoras" and filha["herda_setor"] and filha["setor_efetivo_nome"] == "Suporte TI"


def test_abrir_atender_e_resolver_de_ponta_a_ponta(cliente, admin):
    c = _preparar(cliente, admin)
    ids, cab = c["ids"], c["cab"]

    catalogo = cliente.get(f"{BASE}/catalogo", headers=cab["solicitante"]).json()
    assert {x["caminho"] for x in catalogo} == {"Informática", "Informática > Impressoras"}
    assert all(x["setor_nome"] == "Suporte TI" for x in catalogo)

    r = _abrir(cliente, cab["solicitante"], ids["categoria"], impedindo_trabalho=True)
    assert r.status_code == 201, r.text
    chamado = r.json()
    numero = chamado["numero"]
    assert chamado["status_base"] == "novo" and chamado["setor_nome"] == "Suporte TI" and chamado["solicitante_nome"]
    # Impedindo o trabalho: a prioridade da categoria (normal) sobe um nível
    assert chamado["prioridade"] == "alta" and chamado["prioridade_origem"] == "solicitante"
    assert chamado["atendimento"]["vence_em"] and chamado["solucao"]["vence_em"]
    assert {k: chamado["acoes"][k] for k in ("responder", "responder_privado", "assumir", "solucionar")} == {
        "responder": True, "responder_privado": False, "assumir": False, "solucionar": False}

    # O setor responsável recebe o aviso no sino e por e-mail, mesmo sem ter ligado o e-mail
    with FabricaSessao() as sessao:
        entregas = sessao.scalars(
            select(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.like(f"chamados:%:novo"), EntregaNotificacao.destinatario_id == ids["tecnico"])
        ).all()
        assert len(entregas) == 1 and entregas[0].canal_email

    # Quem atende vê na fila; quem não é parte não vê o chamado
    fila = cliente.get(BASE, params={"filtro": "sem_responsavel"}, headers=cab["tecnico"]).json()
    assert [x["numero"] for x in fila["itens"]] == [numero]
    assert cliente.get(f"{BASE}/{numero}", headers=cab["outro"]).status_code == 404
    assert cliente.get(BASE, headers=cab["solicitante"]).status_code == 403
    assert [x["numero"] for x in cliente.get(f"{BASE}/meus", headers=cab["solicitante"]).json()["itens"]] == [numero]

    # Assumir com versão velha: 409; com a certa, vira responsável
    detalhe = cliente.get(f"{BASE}/{numero}", headers=cab["tecnico"]).json()
    assert detalhe["acoes"]["assumir"]
    r = cliente.post(f"{BASE}/{numero}/assumir", json={"versao": detalhe["versao"] + 5}, headers=cab["tecnico"])
    assert r.status_code == 409 and r.json()["codigo"] == "chamado_alterado"
    r = cliente.post(f"{BASE}/{numero}/assumir", json={"versao": detalhe["versao"]}, headers=cab["tecnico"])
    assert r.status_code == 200, r.text
    assert r.json()["status_base"] == "em_atendimento" and r.json()["responsavel_id"] == ids["tecnico"]
    assert r.json()["atendimento"]["cumprido_em"]

    # Mensagem privada da equipe não aparece para o solicitante; o solicitante não escreve em privado
    assert _responder(cliente, cab["tecnico"], numero, "<p>Peça de reposição pedida ao fornecedor.</p>", privado=True).status_code == 201
    assert _responder(cliente, cab["tecnico"], numero, "<p>Estamos trocando o toner.</p>").status_code == 201
    assert _responder(cliente, cab["solicitante"], numero, "segredo", privado=True).status_code == 403
    visto = cliente.get(f"{BASE}/{numero}", headers=cab["solicitante"]).json()
    textos = [i["texto"] for i in visto["linha_do_tempo"]]
    assert not any("fornecedor" in t for t in textos) and any("toner" in t for t in textos)

    # Resolver é o fim: depois disso ninguém responde
    r = cliente.post(f"{BASE}/{numero}/solucao", data={"dados": json.dumps({"texto": "<p>Toner trocado.</p>"})}, headers=cab["tecnico"])
    assert r.status_code == 201, r.text
    assert r.json()["status_base"] == "solucionado" and r.json()["reabrir_ate"] and r.json()["solucao"]["cumprido_em"]
    assert not any(r.json()["acoes"][k] for k in ("responder", "responder_privado", "assumir", "solucionar"))
    r = _responder(cliente, cab["solicitante"], numero, "Obrigada")
    assert r.status_code == 409 and r.json()["codigo"] == "chamado_encerrado"
    assert [x["numero"] for x in cliente.get(f"{BASE}/meus", params={"filtro": "resolvidos"}, headers=cab["solicitante"]).json()["itens"]] == [numero]


def test_imagem_colada_vira_anexo_e_download_respeita_acesso(cliente, admin):
    c = _preparar(cliente, admin)
    ids, cab = c["ids"], c["cab"]
    imagem = base64.b64encode(PNG_1X1).decode()
    r = _abrir(cliente, cab["solicitante"], ids["categoria"], descricao=f'<p>Veja o erro:</p><img src="data:image/png;base64,{imagem}">',
               arquivos=[("arquivos", ("log.txt", b"erro 42", "text/plain"))])
    assert r.status_code == 201, r.text
    chamado = r.json()
    assert "base64" not in chamado["descricao"]
    nomes = sorted(a["nome"] for a in chamado["anexos"])
    assert nomes == ["imagem-colada-1.png", "log.txt"]
    anexo = next(a for a in chamado["anexos"] if a["nome"] == "log.txt")
    baixado = cliente.get(f"{BASE}/{chamado['numero']}/anexos/{anexo['id']}", headers=cab["tecnico"])
    assert baixado.status_code == 200 and baixado.content == b"erro 42"
    assert cliente.get(f"{BASE}/{chamado['numero']}/anexos/{anexo['id']}", headers=cab["outro"]).status_code == 404
    with FabricaSessao() as sessao:
        assert len(sessao.scalars(select(AnexoChamado)).all()) == 2


def test_abrir_em_nome_do_setor_avisa_todos_os_membros_por_email(cliente, admin):
    c = _preparar(cliente, admin)
    ids, cab = c["ids"], c["cab"]
    # Só setor de que a pessoa é membro
    r = _abrir(cliente, cab["solicitante"], ids["categoria"], setor_solicitante_id=ids["setor_ti"])
    assert r.status_code == 403
    r = _abrir(cliente, cab["solicitante"], ids["categoria"], setor_solicitante_id=ids["setor_rh"])
    assert r.status_code == 201, r.text
    numero = r.json()["numero"]
    assert r.json()["setor_solicitante_nome"] == "Coordenadoria de Pessoas"
    with FabricaSessao() as sessao:
        entregas = sessao.scalars(select(EntregaNotificacao).join(Notificacao).where(Notificacao.chave.like("chamados:%:setor-solicitante:abertura"))).all()
        # A própria autora não recebe o aviso do que ela fez; o colega de setor recebe, com e-mail
        assert {e.destinatario_id for e in entregas} == {ids["outro"]} and all(e.canal_email for e in entregas)
    # O colega do setor solicitante enxerga o chamado
    assert cliente.get(f"{BASE}/{numero}", headers=cab["outro"]).status_code == 200


def test_numero_sequencial_e_busca_na_fila(cliente, admin):
    c = _preparar(cliente, admin)
    ids, cab = c["ids"], c["cab"]
    numeros = [_abrir(cliente, cab["solicitante"], ids["categoria"], titulo=t).json()["numero"] for t in ("Mouse quebrado", "Sem rede no 5º")]
    assert numeros[1] == numeros[0] + 1
    achados = cliente.get(BASE, params={"busca": "rede"}, headers=cab["tecnico"]).json()["itens"]
    assert [x["numero"] for x in achados] == [numeros[1]]
    assert [x["numero"] for x in cliente.get(BASE, params={"busca": f"#{numeros[0]}"}, headers=cab["tecnico"]).json()["itens"]] == [numeros[0]]


def test_reorganizar_setores_preserva_setor_usado_por_chamado(cliente, admin):
    from app.services import servico_setores

    c = _preparar(cliente, admin)
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    with FabricaSessao() as sessao:
        resumo = servico_setores.substituir_estrutura(sessao, {"Secretaria": {"Suporte TI": {}}}, "root")
        sessao.commit()
        ti = sessao.get(Setor, c["ids"]["setor_ti"])
        # Suporte TI continua com o mesmo id (os chamados e a categoria seguem apontando para ele), agora dentro de "Secretaria"
        assert ti is not None and ti.ativo and ti.setor_pai_id is not None
        assert resumo["setores_reaproveitados"] == ["Suporte TI"]
        # O setor sem chamados sai, como antes
        assert resumo["setores_removidos"] == ["Coordenadoria de Pessoas"]
        assert sessao.scalar(select(Setor).where(Setor.nome == "Coordenadoria de Pessoas")) is None
        assert sessao.scalar(select(Chamado.setor_id)) == c["ids"]["setor_ti"]


def test_excluir_expediente_so_quando_nenhum_sla_usa(cliente, admin):
    c = _preparar(cliente, admin)
    # O expediente do cenário é usado pelos SLAs: recusa e diz quais
    r = cliente.delete(f"{BASE}/parametros/expedientes/{c['ids']['expediente']}", headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "em_uso" and "Atendimento" in r.json()["detalhe"]
    # Um expediente sem uso sai de verdade
    faixas = [{"dia_semana": 5, "inicio": "08:00", "fim": "12:00"}]
    novo = cliente.post(f"{BASE}/parametros/expedientes", json={"nome": "Sábado", "faixas": faixas}, headers=admin).json()["id"]
    assert cliente.delete(f"{BASE}/parametros/expedientes/{novo}", headers=c["cab"]["tecnico"]).status_code == 403
    assert cliente.delete(f"{BASE}/parametros/expedientes/{novo}", headers=admin).status_code == 204
    assert [e["nome"] for e in cliente.get(f"{BASE}/parametros/expedientes", headers=admin).json()] == ["Comercial"]
    assert cliente.delete(f"{BASE}/parametros/expedientes/{novo}", headers=admin).status_code == 404


def test_excluir_sla_so_quando_ninguem_usa(cliente, admin):
    c = _preparar(cliente, admin)
    slas = {s["nome"]: s["id"] for s in cliente.get(f"{BASE}/parametros/slas", headers=admin).json()}
    # Usado pela categoria "Informática": recusa e diz qual
    r = cliente.delete(f"{BASE}/parametros/slas/{slas['Solução']}", headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "em_uso" and "Informática" in r.json()["detalhe"]
    # Tirado da categoria, mas já usado num chamado: continua recusado (é histórico)
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    cliente.put(f"{BASE}/parametros/categorias/{c['ids']['raiz']}", json={"nome": "Informática", "setor_id": c["ids"]["setor_ti"]}, headers=admin)
    r = cliente.delete(f"{BASE}/parametros/slas/{slas['Solução']}", headers=admin)
    assert r.status_code == 409 and "chamado" in r.json()["detalhe"]
    # Um SLA novo, sem uso, sai de verdade
    novo = cliente.post(f"{BASE}/parametros/slas", json={"nome": "Teste", "tipo": "tto", "tempo": 1, "unidade": "hora", "expediente_id": c["ids"]["expediente"]},
                        headers=admin).json()["id"]
    assert cliente.delete(f"{BASE}/parametros/slas/{novo}", headers=admin).status_code == 204
    assert cliente.delete(f"{BASE}/parametros/slas/{novo}", headers=admin).status_code == 404


def test_excluir_categoria_so_sem_subcategorias_e_sem_chamados(cliente, admin):
    c = _preparar(cliente, admin)
    r = cliente.delete(f"{BASE}/parametros/categorias/{c['ids']['raiz']}", headers=admin)
    assert r.status_code == 409 and "subcategorias" in r.json()["detalhe"]
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    r = cliente.delete(f"{BASE}/parametros/categorias/{c['ids']['categoria']}", headers=admin)
    assert r.status_code == 409 and "chamado" in r.json()["detalhe"]
    nova = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "Monitores", "pai_id": c["ids"]["raiz"]}, headers=admin).json()["id"]
    assert cliente.delete(f"{BASE}/parametros/categorias/{nova}", headers=admin).status_code == 204
    assert "Informática > Monitores" not in [x["caminho"] for x in cliente.get(f"{BASE}/parametros/categorias", headers=admin).json()]


def test_listas_ordenam_pela_coluna_clicada(cliente, admin):
    c = _preparar(cliente, admin)
    for titulo in ("Bravo", "alfa", "Charlie"):
        _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo=titulo)
    titulos = lambda r: [x["titulo"] for x in r.json()["itens"]]
    r = cliente.get(f"{BASE}/meus", params={"ordem": "titulo", "direcao": "asc"}, headers=c["cab"]["solicitante"])
    assert titulos(r) == ["alfa", "Bravo", "Charlie"]
    r = cliente.get(BASE, params={"ordem": "numero", "direcao": "desc"}, headers=c["cab"]["tecnico"])
    assert titulos(r) == ["Charlie", "alfa", "Bravo"]
    r = cliente.get(BASE, params={"ordem": "solicitante", "direcao": "asc"}, headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and len(r.json()["itens"]) == 3
    assert cliente.get(BASE, params={"ordem": "inexistente"}, headers=c["cab"]["tecnico"]).status_code == 422
