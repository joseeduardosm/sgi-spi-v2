# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o marco 6 dos Chamados: nota de satisfação, respostas prontas, motivos de pendência e relatórios.
"""Marco 6 dos Chamados. Usa o cenário de `test_chamados.py` (Suporte TI com o técnico, a solicitante e outra pessoa)."""

from datetime import timedelta

from app.core.banco import hoje_sao_paulo
from tests.test_chamados import BASE, _abrir, _preparar


def _resolver(cliente, c, numero, texto="<p>Trocado o toner.</p>"):
    r = cliente.post(f"{BASE}/{numero}/solucao", data={"dados": f'{{"texto": "{texto}"}}'}, headers=c["cab"]["tecnico"])
    assert r.status_code == 201, r.text


def test_nota_de_satisfacao_depois_de_resolver(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    # Antes de resolver não há pesquisa nem nota
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["solicitante"]).json()["satisfacao"] is None
    assert cliente.post(f"{BASE}/{numero}/satisfacao", json={"nota": 5}, headers=c["cab"]["solicitante"]).status_code == 409
    _resolver(cliente, c, numero)
    detalhe = cliente.get(f"{BASE}/{numero}", headers=c["cab"]["solicitante"]).json()
    assert detalhe["satisfacao"] == {"nota": None, "rotulo": "", "comentario": "", "respondida_em": None, "pode_avaliar": True}
    # Só quem pediu avalia; nota fora de 1..5 não passa
    assert cliente.post(f"{BASE}/{numero}/satisfacao", json={"nota": 4}, headers=c["cab"]["tecnico"]).status_code == 403
    assert cliente.post(f"{BASE}/{numero}/satisfacao", json={"nota": 6}, headers=c["cab"]["solicitante"]).status_code == 422
    r = cliente.post(f"{BASE}/{numero}/satisfacao", json={"nota": 2, "comentario": "Demorou"}, headers=c["cab"]["solicitante"])
    assert r.status_code == 200 and r.json()["satisfacao"]["rotulo"] == "Ruim" and r.json()["satisfacao"]["comentario"] == "Demorou"
    # Muda a nota enquanto está resolvido; quem atende vê a nota, mas não avalia
    r = cliente.post(f"{BASE}/{numero}/satisfacao", json={"nota": 4}, headers=c["cab"]["solicitante"])
    assert r.json()["satisfacao"]["nota"] == 4
    tecnico = cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).json()["satisfacao"]
    assert tecnico["nota"] == 4 and tecnico["pode_avaliar"] is False
    # Reaberto, não dá para avaliar; resolvido de novo, pede de novo
    assert cliente.post(f"{BASE}/{numero}/nao-resolveu", json={"motivo": "Voltou a falhar"}, headers=c["cab"]["solicitante"]).status_code == 200
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["solicitante"]).json()["satisfacao"]["pode_avaliar"] is False
    _resolver(cliente, c, numero, "<p>Agora foi.</p>")
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["solicitante"]).json()["satisfacao"]["pode_avaliar"] is True


def test_respostas_prontas_e_motivos(cliente, admin):
    c = _preparar(cliente, admin)
    geral = cliente.post(f"{BASE}/parametros/respostas-prontas", json={"titulo": "Reiniciar", "texto": "<p>Reinicie e teste.</p><script>x</script>"}, headers=admin)
    assert geral.status_code == 201 and "<script>" not in geral.json()["texto"]
    cliente.post(f"{BASE}/parametros/respostas-prontas", json={"titulo": "Do RH", "texto": "<p>RH</p>", "setor_id": c["ids"]["setor_rh"]}, headers=admin)
    cliente.post(f"{BASE}/parametros/respostas-prontas", json={"titulo": "Inativa", "texto": "<p>x</p>", "ativo": False}, headers=admin)
    # O técnico (Suporte TI) vê só as gerais ativas; quem só abre não vê
    assert [x["titulo"] for x in cliente.get(f"{BASE}/respostas-prontas", headers=c["cab"]["tecnico"]).json()] == ["Reiniciar"]
    assert cliente.get(f"{BASE}/respostas-prontas", headers=c["cab"]["solicitante"]).status_code == 403
    assert len(cliente.get(f"{BASE}/parametros/respostas-prontas", headers=admin).json()) == 3
    assert cliente.delete(f"{BASE}/parametros/respostas-prontas/{geral.json()['id']}", headers=admin).status_code == 204

    m = cliente.post(f"{BASE}/parametros/motivos-pendencia", json={"nome": "Aguardando peça"}, headers=admin)
    assert m.status_code == 201
    assert cliente.post(f"{BASE}/parametros/motivos-pendencia", json={"nome": "aguardando peça"}, headers=admin).status_code == 409
    assert [x["nome"] for x in cliente.get(f"{BASE}/motivos-pendencia", headers=c["cab"]["tecnico"]).json()] == ["Aguardando peça"]
    assert cliente.put(f"{BASE}/parametros/motivos-pendencia/{m.json()['id']}", json={"nome": "Aguardando peça", "ativo": False}, headers=admin).status_code == 200
    assert cliente.get(f"{BASE}/motivos-pendencia", headers=c["cab"]["tecnico"]).json() == []
    assert cliente.post(f"{BASE}/parametros/motivos-pendencia", json={"nome": "X"}, headers=c["cab"]["tecnico"]).status_code == 403


def test_relatorio_do_periodo(cliente, admin):
    c = _preparar(cliente, admin)
    a = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Outro", impedindo_trabalho=True)
    _resolver(cliente, c, a)
    cliente.post(f"{BASE}/{a}/satisfacao", json={"nota": 5}, headers=c["cab"]["solicitante"])
    r = cliente.get(f"{BASE}/relatorios", headers=c["cab"]["tecnico"])
    assert r.status_code == 200, r.text
    d = r.json()
    # Membro comum: só o próprio setor, sem escolha e sem a quebra por setor/prioridade
    assert d["area"] == "Suporte TI" and d["fim"] == hoje_sao_paulo().isoformat()
    assert (d["pode_escolher_setor"], d["setores_opcoes"], d["por_setor"], d["por_prioridade"]) == (False, [], [], {})
    # Equipe: o técnico resolveu 1 e assumiu 1 (ao resolver, o chamado passou para ele)
    tecnico = next(x for x in d["equipe"] if x["usuario_id"] == c["ids"]["tecnico"])
    assert (tecnico["resolvidos_7d"], tecnico["resolvidos_30d"], tecnico["assumidos_30d"]) == (1, 1, 1)
    # Fila no fim de cada semana (o que estava aberto no domingo à noite, ou no fim do período)
    assert d["semanas"][-1]["em_aberto_fim"] == 1
    resumo = d["resumo"]
    assert (resumo["abertos_no_periodo"], resumo["resolvidos_no_periodo"], resumo["em_aberto_agora"]) == (2, 1, 1)
    assert resumo["solucao_no_prazo_pct"] == 100.0 and resumo["satisfacao_media"] == 5.0 and d["notas"] == [0, 0, 0, 0, 1]
    assert d["por_categoria"][0] == {"id": c["ids"]["categoria"], "nome": "Informática > Impressoras", "abertos": 2, "resolvidos": 1, "no_prazo_pct": 100.0}
    assert sum(s["abertos"] for s in d["semanas"]) == 2
    # Setor fora do alcance, período invertido ou longo demais, e quem só abre: recusados
    assert cliente.get(f"{BASE}/relatorios", params={"setor_id": c["ids"]["setor_rh"]}, headers=c["cab"]["tecnico"]).status_code == 403
    hoje = hoje_sao_paulo()
    assert cliente.get(f"{BASE}/relatorios", params={"inicio": hoje.isoformat(), "fim": (hoje - timedelta(days=1)).isoformat()}, headers=admin).status_code == 400
    assert cliente.get(f"{BASE}/relatorios", params={"inicio": (hoje - timedelta(days=400)).isoformat()}, headers=admin).status_code == 400
    assert cliente.get(f"{BASE}/relatorios", headers=c["cab"]["solicitante"]).status_code == 403
    assert cliente.get(f"{BASE}/relatorios", headers=admin).json()["area"] == "Todos os setores"
    completo = cliente.get(f"{BASE}/relatorios", headers=admin).json()
    assert completo["pode_escolher_setor"] and len(completo["setores_opcoes"]) >= 2 and sum(completo["por_prioridade"].values()) == 2
    # Líder de um setor com setores abaixo: escolhe entre o dele e os de baixo, e vê a quebra por setor
    from app.core.banco import FabricaSessao
    from app.models.setor import Setor
    with FabricaSessao() as sessao:
        ti = sessao.get(Setor, c["ids"]["setor_ti"])
        ti.lider_id = c["ids"]["tecnico"]
        sessao.add(Setor(nome="Redes", setor_pai_id=ti.id))
        sessao.commit()
    lider = cliente.get(f"{BASE}/relatorios", headers=c["cab"]["tecnico"]).json()
    assert lider["pode_escolher_setor"] and {x["nome"] for x in lider["setores_opcoes"]} == {"Suporte TI", "Redes"} and lider["por_setor"]


def test_exportar_chamados_do_periodo(cliente, admin):
    """PDF ou XLSX com os abertos no período; a solução só entra quando pedida; o título leva o setor e as datas."""
    from io import BytesIO

    from openpyxl import load_workbook

    c = _preparar(cliente, admin)
    a = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    _resolver(cliente, c, a, "<p>Trocado o toner &amp; limpo.</p>")
    hoje = hoje_sao_paulo().isoformat()
    params = {"inicio": hoje, "fim": hoje, "setor_id": c["ids"]["setor_ti"], "formato": "xlsx"}
    r = cliente.get(f"{BASE}/relatorios/exportar", params=params, headers=c["cab"]["tecnico"])
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"] == f'attachment; filename="chamados-{hoje}-a-{hoje}.xlsx"'
    valores = [[x for x in linha if x is not None] for linha in load_workbook(BytesIO(r.content)).active.iter_rows(values_only=True)]
    data = hoje_sao_paulo().strftime("%d/%m/%Y")
    assert any(f"Chamados Suporte TI - {data} a {data}" in str(v) for linha in valores for v in linha)
    cabecalho = next(l for l in valores if l and l[0] == "Nº")
    assert cabecalho == ["Nº", "Título", "Descrição", "Solicitante", "Setor responsável", "Responsável", "Status"]
    # Com a solução: a coluna a mais, em texto sem marcação
    r = cliente.get(f"{BASE}/relatorios/exportar", params={**params, "com_solucao": True}, headers=c["cab"]["tecnico"])
    linhas = [[x for x in l if x is not None] for l in load_workbook(BytesIO(r.content)).active.iter_rows(values_only=True)]
    linha = next(l for l in linhas if l and l[0] == a)
    assert linha[-1] == "Trocado o toner & limpo." and linha[4] == "Suporte TI"
    # PDF, e as mesmas recusas do relatório (formato, período, quem só abre)
    pdf = cliente.get(f"{BASE}/relatorios/exportar", params={**params, "formato": "pdf"}, headers=c["cab"]["tecnico"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    assert cliente.get(f"{BASE}/relatorios/exportar", params={**params, "formato": "doc"}, headers=c["cab"]["tecnico"]).status_code == 422
    ontem = (hoje_sao_paulo() - timedelta(days=1)).isoformat()
    assert cliente.get(f"{BASE}/relatorios/exportar", params={**params, "fim": ontem}, headers=c["cab"]["tecnico"]).status_code == 400
    assert cliente.get(f"{BASE}/relatorios/exportar", params=params, headers=c["cab"]["solicitante"]).status_code == 403


def test_clique_no_relatorio_abre_a_lista_com_o_mesmo_numero(cliente, admin):
    """Cada número do relatório, aberto como recorte da fila, traz exatamente os chamados que ele contou."""
    c = _preparar(cliente, admin)
    a = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Outro")
    _resolver(cliente, c, a)
    cliente.post(f"{BASE}/{a}/satisfacao", json={"nota": 5}, headers=c["cab"]["solicitante"])
    tec = c["cab"]["tecnico"]
    hoje = hoje_sao_paulo().isoformat()
    r = cliente.get(f"{BASE}/relatorios", params={"inicio": hoje, "fim": hoje}, headers=tec).json()
    lista = lambda **f: [x["numero"] for x in cliente.get(BASE, params={"filtro": "todos", "escopo_relatorio": True, **f}, headers=tec).json()["itens"]]
    assert len(lista(aberto_de=hoje, aberto_ate=hoje)) == r["resumo"]["abertos_no_periodo"] == 2
    assert lista(resolvido_de=hoje, resolvido_ate=hoje) == [a]
    pessoa = next(x for x in r["equipe"] if x["usuario_id"] == c["ids"]["tecnico"])
    assert len(lista(resolvido_por=pessoa["usuario_id"], resolvido_de=hoje, resolvido_ate=hoje)) == pessoa["resolvidos_7d"] == 1
    assert len(lista(assumido_por=pessoa["usuario_id"], assumido_de=hoje, assumido_ate=hoje)) == pessoa["assumidos_7d"]
    categoria = r["por_categoria"][0]
    assert categoria["id"] and len(lista(categoria_id=categoria["id"], aberto_de=hoje, aberto_ate=hoje)) == categoria["abertos"]
    assert lista(nota=5, resolvido_de=hoje, resolvido_ate=hoje) == [a] and lista(reabertos=True) == []
    # Sem recorte, a fila continua como era; setor do relatório fora do alcance: recusado
    assert cliente.get(BASE, params={"filtro": "todos"}, headers=tec).json()["total"] == 2
    assert cliente.get(BASE, params={"escopo_relatorio": True, "relatorio_setor_id": c["ids"]["setor_rh"]}, headers=tec).status_code == 403


def test_categoria_itil_separada_do_assunto(cliente, admin):
    """Árvore ITIL nos Parâmetros; o assunto pode trazer uma padrão; só quem atende vê e classifica (também depois de resolvido)."""
    c = _preparar(cliente, admin)
    raiz = cliente.post(f"{BASE}/parametros/categorias-itil", json={"nome": "Infraestrutura"}, headers=admin).json()
    servidores = cliente.post(f"{BASE}/parametros/categorias-itil", json={"nome": "Servidores", "pai_id": raiz["id"]}, headers=admin)
    assert servidores.status_code == 201 and servidores.json()["caminho"] == "Infraestrutura > Servidores"
    assert cliente.post(f"{BASE}/parametros/categorias-itil", json={"nome": "servidores", "pai_id": raiz["id"]}, headers=admin).status_code == 409
    assert cliente.post(f"{BASE}/parametros/categorias-itil", json={"nome": "X"}, headers=c["cab"]["tecnico"]).status_code == 403
    # Sem padrão no assunto: o chamado nasce pendente e aparece no filtro "sem_itil"
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    tec = c["cab"]["tecnico"]
    d = cliente.get(f"{BASE}/{numero}", headers=tec).json()
    assert d["categoria_itil_id"] is None and d["acoes"]["classificar"]
    assert numero in [x["numero"] for x in cliente.get(BASE, params={"filtro": "sem_itil"}, headers=tec).json()["itens"]]
    # Quem atende classifica; vai como nota privada; o solicitante não vê nem a classificação nem a nota
    r = cliente.put(f"{BASE}/{numero}/categoria-itil", json={"versao": d["versao"], "categoria_itil_id": servidores.json()["id"]}, headers=tec)
    assert r.status_code == 200 and r.json()["categoria_itil"] == "Infraestrutura > Servidores"
    visto = cliente.get(f"{BASE}/{numero}", headers=c["cab"]["solicitante"]).json()
    assert visto["categoria_itil"] == "" and not visto["acoes"]["classificar"] and not any("ITIL" in i["texto"] for i in visto["linha_do_tempo"])
    assert cliente.put(f"{BASE}/{numero}/categoria-itil", json={"versao": visto["versao"], "categoria_itil_id": None}, headers=c["cab"]["solicitante"]).status_code == 403
    # Em uso: não exclui (desativa); a lista para classificar só traz as ativas
    assert cliente.delete(f"{BASE}/parametros/categorias-itil/{servidores.json()['id']}", headers=admin).json()["codigo"] == "em_uso"
    assert {x["caminho"] for x in cliente.get(f"{BASE}/categorias-itil", headers=tec).json()} == {"Infraestrutura", "Infraestrutura > Servidores"}
    # Com padrão no assunto, o chamado já nasce classificado
    cat = next(x for x in cliente.get(f"{BASE}/parametros/categorias", headers=admin).json() if x["id"] == c["ids"]["categoria"])
    corpo = {k: cat[k] for k in ("nome", "pai_id", "ativa", "visivel_solicitante", "permite_incidente", "permite_requisicao", "setor_id", "responsavel_id",
                                 "sla_tto_id", "sla_ttr_id", "prioridade_padrao", "perguntar_impedindo", "sigilosa", "ordem")}
    assert cliente.put(f"{BASE}/parametros/categorias/{cat['id']}", json={**corpo, "categoria_itil_id": raiz["id"]}, headers=admin).status_code == 200
    outro = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Outro").json()["numero"]
    assert cliente.get(f"{BASE}/{outro}", headers=tec).json()["categoria_itil"] == "Infraestrutura"


def test_atendimento_no_sgi_a_partir_de_uma_data(cliente, admin):
    """Data marcada no futuro: só Controle total abre (testes); os demais recebem 409 e a tela manda ao GLPI. Chegou a data: todos abrem."""
    from app.core.banco import hoje_sao_paulo

    c = _preparar(cliente, admin)
    geral = cliente.get(f"{BASE}/parametros/geral", headers=admin).json()
    assert geral["inicio_atendimento"] is None and cliente.get(f"{BASE}/contexto", headers=c["cab"]["solicitante"]).json()["atendimento_aberto"] is False
    amanha = (hoje_sao_paulo() + timedelta(days=1)).isoformat()
    assert cliente.put(f"{BASE}/parametros/geral", json={**geral, "inicio_atendimento": amanha}, headers=admin).status_code == 200
    r = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    assert r.status_code == 409 and r.json()["codigo"] == "antes_do_inicio"
    assert _abrir(cliente, admin, c["ids"]["categoria"]).status_code == 201  # Controle total testa antes
    contexto = cliente.get(f"{BASE}/contexto", headers=c["cab"]["solicitante"]).json()
    assert contexto["inicio_atendimento"] == amanha and contexto["atendimento_aberto"] is False
    # Chegou a data: todos abrem e o "Abrir chamado" do sistema passa a ser o do SGI
    hoje = hoje_sao_paulo().isoformat()
    cliente.put(f"{BASE}/parametros/geral", json={**geral, "inicio_atendimento": hoje}, headers=admin)
    assert _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).status_code == 201
    assert cliente.get(f"{BASE}/contexto", headers=c["cab"]["solicitante"]).json()["atendimento_aberto"] is True


def test_quem_pode_escolher_o_assunto(cliente, admin):
    """Assunto restrito a setores: só os membros deles (e dos de baixo) veem e abrem; o atendente de outro setor não; Controle total vê tudo."""
    c = _preparar(cliente, admin)
    r = cliente.post(f"{BASE}/parametros/categorias", json={"nome": "CGP Nomeação", "pai_id": c["ids"]["raiz"], "setores_permitidos": [c["ids"]["setor_rh"]]},
                     headers=admin)
    assert r.status_code == 201 and r.json()["setores_permitidos"] == [c["ids"]["setor_rh"]]
    nomeacao = r.json()["id"]
    caminhos = lambda cab: {x["caminho"] for x in cliente.get(f"{BASE}/catalogo", headers=cab).json()}
    assert "Informática > CGP Nomeação" in caminhos(c["cab"]["solicitante"])   # maria é da Coordenadoria de Pessoas
    assert "Informática > CGP Nomeação" not in caminhos(c["cab"]["tecnico"])   # joao atende, mas é da TI
    assert "Informática > CGP Nomeação" in caminhos(admin)
    assert _abrir(cliente, c["cab"]["tecnico"], nomeacao).status_code == 400
    assert _abrir(cliente, c["cab"]["solicitante"], nomeacao).status_code == 201
    # Setor inexistente é recusado; tirar os setores volta a valer "qualquer pessoa"
    corpo = {"nome": "CGP Nomeação", "pai_id": c["ids"]["raiz"]}
    assert cliente.put(f"{BASE}/parametros/categorias/{nomeacao}", json={**corpo, "setores_permitidos": [99999]}, headers=admin).status_code == 400
    assert cliente.put(f"{BASE}/parametros/categorias/{nomeacao}", json={**corpo, "setores_permitidos": []}, headers=admin).json()["setores_permitidos"] == []
    assert "Informática > CGP Nomeação" in caminhos(c["cab"]["tecnico"])
