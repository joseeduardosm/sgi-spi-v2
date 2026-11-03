# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o marco 4 dos Chamados: painel de TV, TVs pareadas, tempo real e os chamados da Nomeação do RH.
"""Marco 4 dos Chamados. Usa o cenário de `test_chamados.py` (Suporte TI com o técnico, a solicitante e outra pessoa)."""

import asyncio
import threading
from datetime import timedelta

from sqlalchemy import select

from app.core.banco import FabricaSessao, hoje_sao_paulo
from app.models.chamados import Chamado
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services.chamados import painel, tempo_real
from tests.conftest import cabecalho, criar_usuario
from tests.test_chamados import BASE, _abrir, _preparar

CHAMADOS_BASE = BASE
from tests.test_rh_admissao import RH, _ficha, ambiente  # noqa: F401 — `ambiente` é fixture do pytest


def test_primeiros_nomes_ignoram_particulas():
    assert painel.primeiros_nomes("José Eduardo Santana Martins") == "José Eduardo"
    assert painel.primeiros_nomes("Ana de Souza Lima") == "Ana Souza"
    assert painel.primeiros_nomes("Root") == "Root" and painel.primeiros_nomes("") == ""


def test_painel_com_login_mostra_o_setor_responsavel_e_a_configuracao(cliente, admin):
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]
    estado = cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"]).json()
    assert estado["area"] == "Suporte TI" and estado["limites"] == {"alerta": 50, "atencao": 75, "perigo": 90}
    assert estado["indicadores"] == {"abertos": 1, "sem_responsavel": 1, "estourados": 0, "resolvidos_hoje": 0}
    assert estado["itens"][0]["numero"] == numero and estado["config"]["linhas_por_pagina"] == 0 and estado["config"]["voz"] is True
    # Quem só abre chamados também tem painel: o do seu setor, que não é responsável por nada aqui
    sol = cliente.get(f"{BASE}/painel", headers=c["cab"]["solicitante"])
    assert sol.status_code == 200 and sol.json()["itens"] == [] and sol.json()["area"] == "Coordenadoria de Pessoas"
    # Sem login: 401 (a TV pareada sem login deixou de existir)
    assert cliente.get(f"{BASE}/painel").status_code == 401
    # Exibição nos Parâmetros: só quem administra; o título não sai
    corpo = {"linhas_por_pagina": 12, "tamanho": "compacto", "segundos_pagina": 20, "voz": False, "cor_linha": False,
             "colunas": ["titulo", "situacao", "responsavel"]}
    assert cliente.put(f"{BASE}/parametros/painel", json=corpo, headers=c["cab"]["tecnico"]).status_code == 403
    r = cliente.put(f"{BASE}/parametros/painel", json=corpo, headers=admin)
    assert r.status_code == 200 and r.json() == corpo
    assert cliente.put(f"{BASE}/parametros/painel", json={**corpo, "colunas": ["situacao"]}, headers=admin).status_code == 400
    assert cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"]).json()["config"]["tamanho"] == "compacto"


def test_painel_esconde_titulo_sigiloso(cliente, admin):
    c = _preparar(cliente, admin)
    cliente.put(f"{CHAMADOS_BASE}/parametros/categorias/{c['ids']['categoria']}", json={"nome": "Impressoras", "pai_id": c["ids"]["raiz"], "sigilosa": True}, headers=admin)
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Assunto delicado")
    assert cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"]).json()["itens"][0]["titulo"] != "Assunto delicado"


def test_painel_do_setor_inclui_os_de_baixo_e_nada_de_fora(cliente, admin):
    c = _preparar(cliente, admin)
    # "Redes" fica abaixo do Suporte TI; quem é só de Redes não vê o Suporte TI
    so_redes = criar_usuario("rede1")
    with FabricaSessao() as sessao:
        redes = Setor(nome="Redes", setor_pai_id=c["ids"]["setor_ti"], ativo=True)
        sessao.add(redes)
        sessao.flush()
        redes_id = redes.id
        sessao.add(MembroSetor(setor_id=redes_id, usuario_id=so_redes))
        sessao.commit()
    cliente.post(f"{BASE}/parametros/categorias", json={"nome": "Rede", "pai_id": c["ids"]["raiz"], "setor_id": redes_id}, headers=admin)
    categoria_rede = next(x["id"] for x in cliente.get(f"{BASE}/parametros/categorias", headers=admin).json() if x["nome"] == "Rede")
    _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Da TI")
    _abrir(cliente, c["cab"]["solicitante"], categoria_rede, titulo="Da Rede")
    tecnico = cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"])
    assert tecnico.status_code == 200 and {i["titulo"] for i in tecnico.json()["itens"]} == {"Da TI", "Da Rede"}
    # Quem é só de Redes: precisa atender para ter painel
    cliente.post("/api/acl/regras", json={"recurso_id": _recurso_id(cliente, admin), "nivel": "MODIFICACAO", "usuarios_ids": [so_redes], "setores_ids": []},
                 headers=admin)
    rede = cliente.get(f"{BASE}/painel", headers=cabecalho(cliente, "rede1"))
    assert rede.status_code == 200 and [i["titulo"] for i in rede.json()["itens"]] == ["Da Rede"] and rede.json()["area"] == "Redes"
    # Pedir o setor de cima (ou um de fora) é recusado; quem administra vê todos
    assert cliente.get(f"{BASE}/painel", params={"setor_id": c["ids"]["setor_ti"]}, headers=cabecalho(cliente, "rede1")).status_code == 403
    assert cliente.get(f"{BASE}/painel", params={"setor_id": redes_id}, headers=c["cab"]["tecnico"]).json()["area"] == "Redes"
    assert cliente.get(f"{BASE}/painel", headers=admin).json()["area"] == "Todos os setores"


def _recurso_id(cliente, admin) -> int:
    return next(r["id"] for r in cliente.get("/api/acl/recursos", headers=admin).json() if r["slug"] == "chamados")


def test_resolvido_sai_do_painel_e_conta_no_dia(cliente, admin):
    c = _preparar(cliente, admin)
    chamado = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()
    r = cliente.post(f"{BASE}/{chamado['numero']}/solucao", data={"dados": '{"texto": "<p>Trocado o toner.</p>"}'}, headers=c["cab"]["tecnico"])
    assert r.status_code == 201, r.text
    estado = cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"]).json()
    assert estado["indicadores"]["resolvidos_hoje"] == 1 and estado["indicadores"]["abertos"] == 0
    assert estado["itens"] == []


def test_painel_ordena_pela_cor(cliente, admin):
    """Vermelho, depois laranja, depois amarelo, depois branco, qualquer que seja a ordem de abertura."""
    from datetime import UTC, datetime, timedelta
    c = _preparar(cliente, admin)
    numeros = [_abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo=f"Chamado {i}").json()["numero"] for i in range(4)]
    agora = datetime.now(UTC)
    # Prazo de solução já vencido (vermelho) no último aberto; os demais ficam no começo do prazo (brancos)
    with FabricaSessao() as sessao:
        ultimo = sessao.scalar(select(Chamado).where(Chamado.numero == numeros[-1]))
        ultimo.prazo_ttr, ultimo.ttr_estourado_em = agora - timedelta(minutes=5), agora - timedelta(minutes=5)
        ultimo.prazo_tto, ultimo.tomado_em = ultimo.aberto_em + timedelta(minutes=15), ultimo.aberto_em
        sessao.commit()
    itens = cliente.get(f"{BASE}/painel", headers=c["cab"]["tecnico"]).json()["itens"]
    assert itens[0]["numero"] == numeros[-1] and itens[0]["nivel"] == "perigo"
    ordem = {"perigo": 0, "atencao": 1, "alerta": 2, "ok": 3, "sem": 3}
    assert [ordem[i["nivel"]] for i in itens] == sorted(ordem[i["nivel"]] for i in itens)


# ---------------------------------------------------------------------------------------------
# Tempo real
# ---------------------------------------------------------------------------------------------

def test_commit_avisa_quem_escuta_e_rollback_nao(cliente, admin):
    c = _preparar(cliente, admin)

    async def cenario():
        fila = tempo_real.barramento.assinar()
        try:
            r = await asyncio.to_thread(_abrir, cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
            novo = await asyncio.wait_for(fila.get(), 2)
            await asyncio.to_thread(cliente.post, f"{BASE}/{r.json()['numero']}/assumir", json={"versao": r.json()["versao"]}, headers=c["cab"]["tecnico"])
            alterado = await asyncio.wait_for(fila.get(), 2)

            def desfeito():
                with FabricaSessao() as sessao:
                    sessao.scalar(select(Chamado)).titulo = "Mudou e voltou"
                    sessao.flush()
                    sessao.rollback()

            await asyncio.to_thread(desfeito)
            await asyncio.sleep(0.1)
            return r.json()["numero"], novo, alterado, fila.empty()
        finally:
            tempo_real.barramento.cancelar(fila)

    numero, novo, alterado, vazia = asyncio.run(cenario())
    assert (novo.tipo, novo.numero, novo.setor_id) == ("novo", numero, c["ids"]["setor_ti"])
    assert (alterado.tipo, alterado.numero, alterado.responsavel_id) == ("alterado", numero, c["ids"]["tecnico"])
    assert vazia and tempo_real.barramento.quantidade == 0


def test_evento_diz_a_acao_para_o_painel_falar(cliente, admin):
    """Assumir, resolver, reabrir e transferir viram `acao` no evento; a transferência leva também o setor de antes."""
    c = _preparar(cliente, admin)
    r = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"])
    numero = r.json()["numero"]
    tec, sol = c["cab"]["tecnico"], c["cab"]["solicitante"]

    def passo(acao) -> list:
        async def cenario():
            fila = tempo_real.barramento.assinar()
            try:
                await asyncio.to_thread(acao)
                await asyncio.sleep(0.1)
                eventos = []
                while not fila.empty():
                    eventos.append(fila.get_nowait())
                return [(e.acao, e.setor_anterior_id) for e in eventos if e.numero == numero]
            finally:
                tempo_real.barramento.cancelar(fila)

        return asyncio.run(cenario())

    versao = lambda: cliente.get(f"{BASE}/{numero}", headers=admin).json()["versao"]
    assert passo(lambda: cliente.post(f"{BASE}/{numero}/assumir", json={"versao": versao()}, headers=tec)) == [("assumido", None)]
    assert passo(lambda: cliente.post(f"{BASE}/{numero}/solucao", data={"dados": '{"texto": "<p>Trocado o toner.</p>"}'}, headers=tec)) == [("resolvido", None)]
    assert passo(lambda: cliente.post(f"{BASE}/{numero}/nao-resolveu", json={"motivo": "Continua sem imprimir"}, headers=sol)) == [("reaberto", None)]
    assert passo(lambda: cliente.patch(f"{BASE}/{numero}", json={"versao": versao(), "prioridade": "alta", "motivo_prioridade": "Diretoria parada"},
                                       headers=tec)) == [("", None)]
    transferencia = passo(lambda: cliente.patch(f"{BASE}/{numero}", json={"versao": versao(), "setor_id": c["ids"]["setor_rh"]}, headers=tec))
    assert transferencia == [("transferido", c["ids"]["setor_ti"])]


def test_fluxo_sse_filtra_e_manda_ping():
    async def cenario():
        partes = []

        async def nunca():
            return False

        gerador = tempo_real.fluxo(lambda e: e.setor_id == 1, nunca, duracao=0.5, ping=0.15)
        partes.append(await gerador.__anext__())
        # Entregue de outra thread, como faz a escuta do PostgreSQL
        threading.Thread(target=lambda: [tempo_real.barramento.entregar(tempo_real.Evento("novo", n, s)) for n, s in ((7, 2), (8, 1))]).start()
        async for parte in gerador:
            partes.append(parte)
        return partes

    partes = asyncio.run(cenario())
    assert partes[0].startswith("retry: 5000")
    eventos = [p for p in partes if p.startswith("event:")]
    assert eventos == ['event: chamado\ndata: {"tipo": "novo", "numero": 8, "acao": ""}\n\n'] and ": ping\n\n" in partes


def test_rota_de_eventos_exige_login_e_papel(cliente, admin, monkeypatch):
    c = _preparar(cliente, admin)
    assert cliente.get(f"{BASE}/eventos").status_code == 401
    criar_usuario("sem-papel")
    assert cliente.get(f"{BASE}/eventos", headers=cabecalho(cliente, "sem-papel")).status_code == 403
    monkeypatch.setattr(tempo_real, "DURACAO_MAXIMA", 0.2)
    r = cliente.get(f"{BASE}/eventos", headers=c["cab"]["tecnico"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream") and r.headers["x-accel-buffering"] == "no"
    assert r.text.startswith("retry: 5000")


# ---------------------------------------------------------------------------------------------
# RH: Nomeação abre os chamados aqui depois da virada
# ---------------------------------------------------------------------------------------------

def test_nomeacao_abre_um_chamado_por_servico_depois_da_virada(cliente, ambiente):  # noqa: F811
    amb, admin = ambiente, ambiente["admin"]
    c = _preparar(cliente, admin)
    rh = cliente.get(f"{BASE}/parametros/rh", headers=admin).json()
    assert rh["destino"] == "glpi" and len(rh["servicos"]) == 9 and all(s["setor_id"] is None for s in rh["servicos"])
    # Sem fila para todos os serviços, não liga
    ti = {"setor_id": c["ids"]["setor_ti"]}
    r = cliente.put(f"{BASE}/parametros/rh", json={"destino": "chamados", "servicos": {"rede": ti}}, headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "servico_sem_fila"
    slas = {x["tipo"]: x["id"] for x in cliente.get(f"{BASE}/parametros/slas", headers=admin).json()}
    # Cada serviço com a sua fila, prioridade e prazos; o crachá vai para outro setor, com prioridade alta
    todas = {s["servico"]: {**ti, "prioridade": "normal", "sla_ttr_id": slas["ttr"]} for s in rh["servicos"]}
    todas["cracha"] = {"setor_id": c["ids"]["setor_rh"], "prioridade": "alta"}
    # Também precisa das filas da Exoneração; prazo do tipo errado é recusado
    assert cliente.put(f"{BASE}/parametros/rh", json={"destino": "chamados", "servicos": todas}, headers=admin).status_code == 409
    errado = {**todas, "rede": {**ti, "sla_ttr_id": slas["tto"]}}
    assert cliente.put(f"{BASE}/parametros/rh", json={"destino": "chamados", "servicos": errado, "servicos_exoneracao": todas}, headers=admin).status_code == 400
    r = cliente.put(f"{BASE}/parametros/rh", json={"destino": "chamados", "servicos": todas, "servicos_exoneracao": todas}, headers=admin)
    assert r.status_code == 200 and r.json()["destino"] == "chamados" and r.json()["servicos"][0]["setor_nome"] == "Suporte TI"

    # "Virar junto com a data": sem a data "a partir de" marcada, recusa; com a data no futuro, o RH continua no GLPI; no dia, vira sozinho
    corpo_rh = {"destino": "na_data", "servicos": todas, "servicos_exoneracao": todas}
    assert cliente.put(f"{BASE}/parametros/rh", json=corpo_rh, headers=admin).status_code == 400
    geral = cliente.get(f"{BASE}/parametros/geral", headers=admin).json()
    amanha = (hoje_sao_paulo() + timedelta(days=1)).isoformat()
    cliente.put(f"{BASE}/parametros/geral", json={**geral, "inicio_atendimento": amanha}, headers=admin)
    r = cliente.put(f"{BASE}/parametros/rh", json=corpo_rh, headers=admin)
    assert r.status_code == 200 and r.json()["destino"] == "na_data" and r.json()["destino_atual"] == "glpi"
    cliente.put(f"{BASE}/parametros/geral", json={**geral, "inicio_atendimento": hoje_sao_paulo().isoformat()}, headers=admin)
    assert cliente.get(f"{BASE}/parametros/rh", headers=admin).json()["destino_atual"] == "chamados"

    ficha = _ficha(cliente, amb)
    aid = cliente.post(f"{RH}/admissoes", json={"ficha_id": ficha["id"]}, headers=amb["h"]).json()["id"]
    r = cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {"rede": True, "email": True}, "observacoes": "Começa segunda",
                                                            "usuario_espelho": "mirror.user"}, headers=amb["h"])
    assert r.status_code == 200, r.text
    corpo = r.json()
    # Nada foi ao GLPI; a admissão anda e mostra os chamados do módulo com o status de agora
    assert amb["chamados"] == [] and corpo["etapa"] == "documentos" and corpo["chamados_destino"] == "chamados"
    links = corpo["chamado_links"]
    assert [l["chave"] for l in links] == ["rede", "email"] and all(l["url"] == f"/chamados/{l['numero']}" and l["status_nome"] for l in links)
    # A descrição leva o necessário; CPF e RG só na nota privada (o técnico vê, a solicitante não)
    detalhe = cliente.get(f"{BASE}/{links[0]['numero']}", headers=c["cab"]["tecnico"]).json()
    assert detalhe["titulo"] == "Criar usuário de rede: Joana Pereira Lima" and "joana.lima" in detalhe["descricao"] and "52998224725" not in detalhe["descricao"]
    # Fila, prioridade e prazo vêm do serviço; o assunto é o fixo da Nomeação (fora de uso para quem abre)
    assert detalhe["setor_nome"] == "Suporte TI" and detalhe["prioridade"] == "normal" and detalhe["categoria_caminho"] == "Nomeação (RH)"
    assert detalhe["solucao"]["vence_em"] is not None
    assert "Nomeação (RH)" not in {x["caminho"] for x in cliente.get(f"{BASE}/catalogo", headers=c["cab"]["solicitante"]).json()}
    privada = next(i for i in detalhe["linha_do_tempo"] if i["privado"])
    assert "52998224725" in privada["texto"] and "12.345.678-9" in privada["texto"]
    # Segundo envio é recusado, como no GLPI
    assert cliente.post(f"{RH}/admissoes/{aid}/chamado", json={"solicitacoes": {"rede": True}}, headers=amb["h"]).status_code == 409


def test_exoneracao_pede_o_inverso_da_nomeacao(cliente, ambiente):  # noqa: F811
    amb, admin = ambiente, ambiente["admin"]
    c = _preparar(cliente, admin)
    from app.services.rh import servico_cargos
    pessoa = criar_usuario("saindo", nome_completo="Paulo Roberto Dias")
    with FabricaSessao() as sessao:
        autor = sessao.scalar(select(Usuario).where(Usuario.login == "rh-adm"))
        servico_cargos.ocupar(sessao, amb["cargo"]["id"], pessoa, autor)
        sessao.commit()
    r = cliente.post(f"{RH}/cargos/{amb['cargo']['id']}/vacancia", json={"motivo": "exoneracao", "ato": "Resolução SPI 12/2026"}, headers=amb["h"])
    assert r.status_code == 200, r.text
    ocupacao = r.json()["ocupacao_encerrada_id"]
    leitura = cliente.get(f"{RH}/exoneracoes/{ocupacao}", headers=amb["h"]).json()
    # Sem nomeação no SGI, todos vêm marcados; cada serviço é o inverso do da nomeação
    assert leitura["destino"] == "glpi" and all(leitura["sugestao"].values()) and leitura["sugestao_da_nomeacao"] is False and leitura["servicos"]["rede"] == "Desativar usuário de rede"
    # Antes da virada, a exoneração segue pelo GLPI
    assert cliente.post(f"{RH}/exoneracoes/{ocupacao}/chamados", json={"solicitacoes": {"rede": True}}, headers=amb["h"]).status_code == 409
    todas = {s["servico"]: {"setor_id": c["ids"]["setor_ti"]} for s in cliente.get(f"{BASE}/parametros/rh", headers=admin).json()["servicos"]}
    cliente.put(f"{BASE}/parametros/rh", json={"destino": "chamados", "servicos": todas, "servicos_exoneracao": todas}, headers=admin)
    r = cliente.post(f"{RH}/exoneracoes/{ocupacao}/chamados", json={"solicitacoes": {"rede": True, "cracha": True}, "observacoes": "Último dia: sexta"}, headers=amb["h"])
    assert r.status_code == 200, r.text
    links = r.json()["chamados"]
    assert [l["chave"] for l in links] == ["rede", "cracha"] and all(l["status_nome"] for l in links)
    detalhe = cliente.get(f"{BASE}/{links[0]['numero']}", headers=c["cab"]["tecnico"]).json()
    assert detalhe["titulo"] == "Desativar usuário de rede: Paulo Roberto Dias" and "saindo" in detalhe["descricao"] and "Resolução SPI 12/2026" in detalhe["descricao"]
    # Uma vez só; saída que não é exoneração não tem esta tela
    assert cliente.post(f"{RH}/exoneracoes/{ocupacao}/chamados", json={"solicitacoes": {"rede": True}}, headers=amb["h"]).status_code == 409


def test_responder_sem_responsavel_atribui_e_avisa_assumido(cliente, admin):
    """Quem é do setor responsável responde um chamado sem responsável: vira o responsável e o evento sai como "assumido" (o painel fala)."""
    c = _preparar(cliente, admin)
    numero = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"]).json()["numero"]

    async def cenario():
        fila = tempo_real.barramento.assinar()
        try:
            r = await asyncio.to_thread(cliente.post, f"{BASE}/{numero}/acompanhamentos", data={"dados": '{"texto": "<p>Vou olhar.</p>"}'}, headers=c["cab"]["tecnico"])
            await asyncio.sleep(0.1)
            eventos = []
            while not fila.empty():
                eventos.append(fila.get_nowait())
            return r, eventos
        finally:
            tempo_real.barramento.cancelar(fila)

    r, eventos = asyncio.run(cenario())
    assert r.status_code == 201, r.text
    d = cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).json()
    assert d["responsavel_id"] == c["ids"]["tecnico"] and d["status_base"] == "em_atendimento"
    assert [e.acao for e in eventos if e.numero == numero] == ["assumido"]
    # A resposta do solicitante não muda o responsável
    cliente.post(f"{BASE}/{numero}/acompanhamentos", data={"dados": '{"texto": "<p>Obrigada.</p>"}'}, headers=c["cab"]["solicitante"])
    assert cliente.get(f"{BASE}/{numero}", headers=c["cab"]["tecnico"]).json()["responsavel_id"] == c["ids"]["tecnico"]
