# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a API do plano de face da rede (/api/rede): equipamentos, faces, portas, VLANs, conexões e pontos.
"""Rotas `/api/rede` (plano de face). Recurso da ACL `rede`, **fechado até haver regras** (só o SuperRoot):
Leitura vê, Modificação muda portas, conexões e pontos, Controle total cuida de modelos, equipamentos e VLANs.
Detalhes em `docs/endpoints/rede.md`."""

import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.chamados import STATUS_ABERTOS, Chamado
from app.models.patrimonio import Bem, Localizacao
from app.models.rede import ConexaoRede, DispositivoAtrasRede, EquipamentoRede, ModeloFaceRede, PontoRede, PortaRede, PortaVlanRede, RackRede, VlanRede
from app.models.usuario import Usuario
from app.schemas.comum import RespostaErro
from app.schemas.rede import (
    BemResumo, CaminhoRede, ChamadoDaPorta, DispositivoCaminho, EtapaCaminho, ParametrosRede, ConexaoLeitura, DispositivoAtrasLeitura, GravacaoDispositivoAtras, GravacaoRack, PortaDoBem, RackLeitura, SalaResumo, EquipamentoDetalhe, EquipamentoResumo, GravacaoConexao, GravacaoEquipamento, GravacaoModelo, GravacaoPonto,
    GravacaoPorta, GravacaoVlan, ModeloLeitura, NoTopologia, PapeisRede, PontoLeitura, PortaDetalhe, PortaLeitura, TopologiaRede, VlanLeitura,
)
from app.services.chamados import acesso as acesso_chamados
from app.services.rede import ping, servico
from app.services.rede.servico import DadosEquipamento, DadosPorta, ErroRede
from app.services.servico_auditoria import auditar

roteador = APIRouter(prefix="/rede", tags=["Rede (plano de face)"], responses=VALIDACAO)

SEM_ACESSO = {status.HTTP_403_FORBIDDEN: {"model": RespostaErro, "description": "Sem o nível necessário no recurso `rede` (`acesso_negado`)."}}


def _papeis(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> tuple[Usuario, servico.PapeisRede]:
    return usuario, servico.papeis(sessao, usuario)


def _exigir(nivel: str):
    """Dependência: o papel mínimo (`ver`, `editar` ou `administrar`)."""
    def verificar(ctx: tuple[Usuario, servico.PapeisRede] = Depends(_papeis)) -> Usuario:
        if not getattr(ctx[1], nivel):
            mensagens = {"ver": "Você não tem acesso ao plano de face.", "editar": "Só quem edita a rede muda portas, conexões e pontos.",
                         "administrar": "Só a administração da rede cuida de modelos, equipamentos e VLANs."}
            raise ErroApi(status.HTTP_403_FORBIDDEN, mensagens[nivel], "acesso_negado")
        return ctx[0]
    return verificar


@contextmanager
def _traduzir(sessao: Session):
    try:
        yield
    except ErroRede as erro:
        sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


# ---------------------------------------------------------------------------------------------
# Montagem das respostas
# ---------------------------------------------------------------------------------------------

def _modelo(sessao: Session, m: ModeloFaceRede) -> ModeloLeitura:
    em_uso = sessao.scalar(select(func.count()).select_from(EquipamentoRede).where(EquipamentoRede.modelo_face_id == m.id)) or 0
    return ModeloLeitura(id=m.id, nome=m.nome, fabricante=m.fabricante, linhas=m.linhas, colunas=m.colunas, numeracao=m.numeracao,
                         portas_extras=m.portas_extras or [], altura_u=m.altura_u, equipamentos=em_uso)


def _resumo(sessao: Session, e: EquipamentoRede, contagem: Counter, salas: dict) -> dict:
    return dict(id=e.id, nome=e.nome, tipo=e.tipo, modelo_face_id=e.modelo_face_id, bem_id=e.bem_id, localizacao_id=e.localizacao_id, rack_id=e.rack_id, rack_nome=e.rack.nome if e.rack else "",
                posicao_u=e.posicao_u, ip_gerencia=e.ip_gerencia, numero_serie=e.numero_serie, observacao=e.observacao, ativo=e.ativo,
                modelo_nome=e.modelo_face.nome if e.modelo_face else "", altura_u=e.modelo_face.altura_u if e.modelo_face else 1, sala=salas.get(e.localizacao_id, ""), portas_total=contagem["total"],
                portas_up=contagem["up"], portas_down=contagem["down"], portas_desativadas=contagem["desativada"], funcao=e.funcao,
                ping_situacao=e.ping_situacao, ping_verificado_em=e.ping_verificado_em, ping_mudou_em=e.ping_mudou_em, cadastro_incompleto=servico.cadastro_incompleto(e))


def _salas(sessao: Session, ids) -> dict:
    ids = {i for i in ids if i}
    return {x.id: x.nome for x in sessao.scalars(select(Localizacao).where(Localizacao.id.in_(ids)))} if ids else {}


def _rotulo_porta(sessao: Session, porta_id: uuid.UUID, cache: dict) -> tuple[str, uuid.UUID | None]:
    if porta_id not in cache:
        p = sessao.get(PortaRede, porta_id)
        cache[porta_id] = (f"{p.equipamento.nome} · porta {p.nome or p.numero_logico}", p.equipamento_id) if p else ("(porta removida)", None)
    return cache[porta_id]


def _texto_bem(b) -> str:
    return f"{getattr(b, 'descricao', '') or 'Bem'} (chapa {b.chapa or '—'})"


def _portas(sessao: Session, portas: list[PortaRede]) -> list[PortaLeitura]:
    ids = [p.id for p in portas]
    vlans = {v.id: v.numero for v in sessao.scalars(select(VlanRede))}
    conexoes = list(sessao.scalars(select(ConexaoRede).where((ConexaoRede.porta_a_id.in_(ids)) | (ConexaoRede.porta_b_id.in_(ids))))) if ids else []
    por_porta = {}
    for c in conexoes:
        por_porta[c.porta_a_id] = (c, c.porta_b_id)
        if c.porta_b_id:
            por_porta[c.porta_b_id] = (c, c.porta_a_id)
    atras = defaultdict(list)
    for d in sessao.scalars(select(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id.in_([c.id for c in conexoes])).order_by(DispositivoAtrasRede.ordem)) if conexoes else []:
        atras[d.conexao_id].append(d)
    ids_bens = {c.bem_id for c in conexoes if c.bem_id} | {d.bem_id for lista in atras.values() for d in lista if d.bem_id}
    bens = {b.id: b for b in sessao.scalars(select(Bem).where(Bem.id.in_(ids_bens)))} if ids_bens else {}
    pontos = {pt.porta_id: pt.codigo for pt in sessao.scalars(select(PontoRede).where(PontoRede.porta_id.in_(ids)))} if ids else {}
    abertos = {porta_id: total for porta_id, total in sessao.execute(
        select(Chamado.rede_porta_id, func.count()).where(Chamado.rede_porta_id.in_(ids), Chamado.status_base.in_(STATUS_ABERTOS), Chamado.excluido_em.is_(None))
        .group_by(Chamado.rede_porta_id))} if ids else {}
    cache: dict = {}
    resultado = []
    for p in portas:
        conexao = None
        if p.id in por_porta:
            c, outra = por_porta[p.id]
            if outra:
                texto, equipamento_id = _rotulo_porta(sessao, outra, cache)
                conexao = ConexaoLeitura(tipo="porta", texto=texto, porta_id=outra, equipamento_id=equipamento_id)
            else:
                fila = [DispositivoAtrasLeitura(id=d.id, ordem=d.ordem, bem_id=d.bem_id, texto=_texto_bem(bens.get(d.bem_id)) if d.bem_id in bens else d.descricao)
                        for d in atras.get(c.id, [])]
                if c.bem_id and c.bem_id in bens:
                    conexao = ConexaoLeitura(tipo="bem", texto=_texto_bem(bens[c.bem_id]), bem_id=c.bem_id, atras=fila)
                else:
                    conexao = ConexaoLeitura(tipo="descricao", texto=c.descricao, atras=fila)
        tag = sorted(vlans[x.vlan_id] for x in p.vlans if x.com_tag and x.vlan_id in vlans)
        sem_tag = sorted(vlans[x.vlan_id] for x in p.vlans if not x.com_tag and x.vlan_id in vlans)
        resultado.append(PortaLeitura(
            id=p.id, numero_logico=p.numero_logico, nome=p.nome, descricao=p.descricao, mac=p.mac, velocidade_mbps=p.velocidade_mbps, duplex=p.duplex,
            status=p.status, modo=p.modo, vlan_nativa_id=p.vlan_nativa_id, vlan_nativa=vlans.get(p.vlan_nativa_id), vlans_tag=tag,
            vlans_tag_ids=[x.vlan_id for x in p.vlans if x.com_tag], vlans_sem_tag=sem_tag, vlans_sem_tag_ids=[x.vlan_id for x in p.vlans if not x.com_tag],
            vlan_voz_id=p.vlan_voz_id, vlan_voz=vlans.get(p.vlan_voz_id), ip_interface=p.ip_interface, ultima_mudanca=p.ultima_mudanca, erros_entrada=p.erros_entrada, erros_saida=p.erros_saida,
            conexao=conexao, ponto=pontos.get(p.id, ""), chamados_abertos=abertos.get(p.id, 0),
        ))
    return resultado


def _detalhe(sessao: Session, e: EquipamentoRede) -> EquipamentoDetalhe:
    contagem = servico.resumo_portas(sessao, [e.id])[e.id]
    return EquipamentoDetalhe(**_resumo(sessao, e, contagem, _salas(sessao, [e.localizacao_id])),
                              modelo=_modelo(sessao, e.modelo_face) if e.modelo_face else None,
                              posicoes=servico.posicoes(e.modelo_face) if e.modelo_face else {}, portas=_portas(sessao, list(e.portas)))


def _ponto(sessao: Session, pt: PontoRede, salas: dict) -> PontoLeitura:
    cache: dict = {}
    caminho = [_rotulo_porta(sessao, p.id, cache)[0] for p in servico.caminho_do_ponto(sessao, pt)]
    return PontoLeitura(id=pt.id, codigo=pt.codigo, localizacao_id=pt.localizacao_id, porta_id=pt.porta_id, observacao=pt.observacao,
                        sala=salas.get(pt.localizacao_id, ""), caminho=caminho)


# ---------------------------------------------------------------------------------------------
# Contexto e equipamentos
# ---------------------------------------------------------------------------------------------

@roteador.get("/contexto", response_model=PapeisRede, summary="Papéis no plano de face",
              description="O que a pessoa pode fazer (200 mesmo sem nenhum papel: a tela esconde o módulo).")
def contexto(ctx: tuple[Usuario, servico.PapeisRede] = Depends(_papeis)) -> PapeisRede:
    return PapeisRede(**ctx[1].__dict__)


@roteador.get("/parametros", response_model=ParametrosRede, summary="Parâmetros da Rede", responses=SEM_ACESSO,
              description="Configurações do módulo: o intervalo entre as rodadas de ping dos equipamentos.")
def parametros(_: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ParametrosRede:
    return ParametrosRede(ping_intervalo_min=ping.intervalo_min(sessao))


@roteador.put("/parametros", response_model=ParametrosRede, summary="Alterar parâmetros da Rede", responses={**INVALIDO, **SEM_ACESSO},
              description="Grava o intervalo entre as rodadas de ping (1 a 60 minutos). Vale a partir da próxima rodada.")
def gravar_parametros(corpo: ParametrosRede, usuario: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ParametrosRede:
    ping.gravar_intervalo(sessao, corpo.ping_intervalo_min)
    auditar(sessao, usuario.login, "rede.parametros", f"ping_intervalo_min={corpo.ping_intervalo_min}", autor_id=usuario.id)
    sessao.commit()
    return ParametrosRede(ping_intervalo_min=ping.intervalo_min(sessao))


@roteador.get("/topologia", response_model=TopologiaRede, summary="Topologia da rede", responses=SEM_ACESSO,
              description="A rede como árvore, montada na hora a partir dos cabos entre portas de equipamentos (nada é desenhado à mão): "
                          "o núcleo no topo, embaixo os switches ligados a ele e assim por diante, com os pontos e bens de cada um. "
                          "Equipamentos sem cabo para outro equipamento vêm em `sem_ligacao`. Os cores (função) ficam no topo, lado a lado, o Primário primeiro "
                          "(o Secundário passa à frente, com `assumiu`, se o ping der o Primário fora do ar); grupo sem core usa o núcleo automático. "
                          "`raiz_id` só muda a visão.")
def topologia(raiz_id: uuid.UUID | None = Query(None, description="Equipamento que fica no topo do seu grupo (o núcleo), se a escolha automática não servir."),
              _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> TopologiaRede:
    raizes, sem_ligacao = servico.topologia(sessao, raiz_id)
    todos: list[EquipamentoRede] = []
    pilha = [*raizes, *sem_ligacao]
    while pilha:
        n = pilha.pop()
        todos.append(n.equipamento)
        pilha.extend(n.filhos or [])
    # Sem sala própria, o equipamento fica na sala do rack
    salas = _salas(sessao, [i for e in todos for i in (e.localizacao_id, e.rack.localizacao_id if e.rack else None)])

    def montar(n: servico.NoTopologia) -> NoTopologia:
        e = n.equipamento
        sala = salas.get(e.localizacao_id) or (salas.get(e.rack.localizacao_id, "") if e.rack else "")
        return NoTopologia(id=e.id, nome=e.nome, tipo=e.tipo, funcao=e.funcao, ping_situacao=e.ping_situacao, assumiu=n.assumiu, rack_nome=e.rack.nome if e.rack else "", rack_cor=e.rack.cor if e.rack else None, sala=sala,
                           ip_gerencia=e.ip_gerencia, portas_total=n.portas_total, portas_up=n.portas_up, portas_down=n.portas_down, pontos=n.pontos,
                           bens=n.bens, porta_acima=n.porta_acima, porta_no_pai=n.porta_no_pai, cabos_com_pai=n.cabos_com_pai,
                           tambem_ligado=n.tambem_ligado or [], filhos=[montar(f) for f in n.filhos or []])

    return TopologiaRede(raizes=[montar(r) for r in raizes], sem_ligacao=[montar(n) for n in sem_ligacao])


@roteador.get("/equipamentos", response_model=list[EquipamentoResumo], summary="Equipamentos", responses=SEM_ACESSO,
              description="Switches, patch panels e roteadores, com a contagem de portas por status.")
def equipamentos(busca: str = Query("", max_length=100), tipo: str | None = Query(None), _: Usuario = Depends(_exigir("ver")),
                 sessao: Session = Depends(obter_sessao)) -> list[EquipamentoResumo]:
    itens = servico.listar_equipamentos(sessao, busca, tipo)
    contagens = servico.resumo_portas(sessao, [e.id for e in itens])
    salas = _salas(sessao, [e.localizacao_id for e in itens])
    return [EquipamentoResumo(**_resumo(sessao, e, contagens[e.id], salas)) for e in itens]


@roteador.post("/equipamentos", response_model=EquipamentoDetalhe, status_code=status.HTTP_201_CREATED, summary="Cadastrar equipamento",
               description="Com modelo de face, as portas são criadas pelo modelo.", responses={**INVALIDO, **SEM_ACESSO})
def criar_equipamento(corpo: GravacaoEquipamento, usuario: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        e = servico.salvar_equipamento(sessao, None, DadosEquipamento(**corpo.model_dump()))
        auditar(sessao, usuario.login, "rede.equipamento.criar", e.nome, autor_id=usuario.id)
        sessao.commit()
    return _detalhe(sessao, servico.obter_equipamento(sessao, e.id))


@roteador.get("/equipamentos/{equipamento_id}", response_model=EquipamentoDetalhe, summary="Face do equipamento",
              description="O equipamento, o modelo (grade, numeração, portas extras), a posição de cada porta na grade e as portas com a configuração "
              "lógica, o que está ligado, o ponto de rede e os chamados abertos.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Equipamento")})
def equipamento(equipamento_id: uuid.UUID, _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        return _detalhe(sessao, servico.obter_equipamento(sessao, equipamento_id))


@roteador.put("/equipamentos/{equipamento_id}", response_model=EquipamentoDetalhe, summary="Alterar equipamento",
              description="Trocar o modelo cria as portas que faltam (nenhuma é apagada).", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Equipamento")})
def alterar_equipamento(equipamento_id: uuid.UUID, corpo: GravacaoEquipamento, usuario: Usuario = Depends(_exigir("administrar")),
                        sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        e = servico.salvar_equipamento(sessao, equipamento_id, DadosEquipamento(**corpo.model_dump()))
        sessao.commit()
    return _detalhe(sessao, servico.obter_equipamento(sessao, e.id))


@roteador.delete("/equipamentos/{equipamento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir equipamento",
                 description="Apaga as portas e as conexões delas; os chamados ficam sem a porta.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Equipamento")})
def excluir_equipamento(equipamento_id: uuid.UUID, usuario: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.excluir_equipamento(sessao, equipamento_id)
        auditar(sessao, usuario.login, "rede.equipamento.excluir", str(equipamento_id), autor_id=usuario.id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Portas e conexões
# ---------------------------------------------------------------------------------------------

def _porta_detalhe(sessao: Session, usuario: Usuario, porta: PortaRede) -> PortaDetalhe:
    p = acesso_chamados.papeis(sessao, usuario)
    chamados = []
    if p.algum:
        visivel = acesso_chamados.filtro_visibilidade(acesso_chamados.alcance(sessao, usuario, p))
        chamados = [ChamadoDaPorta(numero=c.numero, titulo=c.titulo, status_base=c.status_base, aberto_em=c.aberto_em)
                    for c in servico.chamados_da_porta(sessao, porta, visivel)]
    return PortaDetalhe(**_portas(sessao, [porta])[0].model_dump(), equipamento_id=porta.equipamento_id, equipamento_nome=porta.equipamento.nome,
                        chamados=chamados)


@roteador.get("/portas/{porta_id}", response_model=PortaDetalhe, summary="Painel da porta",
              description="Configuração lógica, o outro lado, o ponto de rede e os chamados da porta (e do ponto), só os que a pessoa vê nos Chamados.",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Porta")})
def porta(porta_id: uuid.UUID, usuario: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.get("/portas/{porta_id}/caminho", response_model=CaminhoRede, summary="Caminho da porta até o core",
              description="Do core (topo da árvore da topologia) até esta porta e o que está nela: os equipamentos no caminho, o cabo entre cada um "
              "(\"porta de cima ↔ porta de baixo\"), o patch panel e o ponto de rede (se cadastrados) e os dispositivos em cascata (telefone → computador).",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Porta")})
def caminho_da_porta(porta_id: uuid.UUID, _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> CaminhoRede:
    with _traduzir(sessao):
        c = servico.caminho_da_porta(sessao, porta_id)
    # Configuração completa das portas dos quadradinhos (a mesma leitura da face, para a dica ao passar o mouse)
    ids = {i for e in c.etapas for i in (e.porta_entrada_id, e.porta_saida_id) if i}
    portas = {p.id: p for p in _portas(sessao, list(sessao.scalars(select(PortaRede).where(PortaRede.id.in_(ids)))))} if ids else {}
    return CaminhoRede(
        etapas=[EtapaCaminho(tipo=e.tipo, nome=e.nome, cabo=e.cabo, equipamento_id=e.equipamento.id if e.equipamento else None,
                             tipo_equipamento=e.equipamento.tipo if e.equipamento else None, funcao=e.equipamento.funcao if e.equipamento else None,
                             ping_situacao=e.equipamento.ping_situacao if e.equipamento else None,
                             porta_entrada=portas.get(e.porta_entrada_id), porta_saida=portas.get(e.porta_saida_id)) for e in c.etapas],
        dispositivos=[DispositivoCaminho(texto=t, bem_id=b) for t, b in c.dispositivos], cabo_dispositivos=c.cabo_dispositivos, aviso=c.aviso)


@roteador.put("/portas/{porta_id}", response_model=PortaDetalhe, summary="Configurar porta",
              description="Descrição, modo (access, trunk, hybrid, QinQ, dinâmico auto/desirable ou roteada), VLAN access/nativa/PVID/externa, VLANs com "
              "tag (trunk, hybrid, dinâmicas), VLANs sem tag (hybrid), VLAN de voz (access, hybrid, dinâmicas), IP da interface (roteada), velocidade, "
              "duplex e status. Combinação que o modo não aceita: 400. Porta com algo ligado fica \"ligada\" (`up`): outro status dá `409 porta_com_equipamento` "
              "(retire o equipamento antes). É o **cadastro** da configuração: o SGI não fala com o switch.",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def configurar_porta(porta_id: uuid.UUID, corpo: GravacaoPorta, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        p = servico.alterar_porta(sessao, porta_id, DadosPorta(descricao=corpo.descricao, modo=corpo.modo, vlan_nativa_id=corpo.vlan_nativa_id,
                                                               vlans_tag=corpo.vlans_tag, vlans_sem_tag=corpo.vlans_sem_tag, vlan_voz_id=corpo.vlan_voz_id,
                                                               ip_interface=corpo.ip_interface, velocidade_mbps=corpo.velocidade_mbps, duplex=corpo.duplex,
                                                               status=corpo.status))
        auditar(sessao, usuario.login, "rede.porta.configurar", f"{p.equipamento.nome} · {p.numero_logico}", autor_id=usuario.id)
        sessao.commit()
    return _porta_detalhe(sessao, usuario, p)


@roteador.post("/portas/{porta_id}/conexao", response_model=PortaDetalhe, status_code=status.HTTP_201_CREATED, summary="Ligar a porta",
               description="Liga a outra porta, a um bem do Patrimônio ou a uma descrição. Confere as duas pontas: porta já ligada (de qualquer lado): "
                           "`409 porta_ocupada`; na ligação porta ↔ porta, porta descrita no switch (dispositivo provável): `409 porta_com_dispositivo`, "
                           "que a tela confirma e reenvia com `forcar=true`. As duas pontas passam ao status \"ligada\" (`up`).",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def ligar(porta_id: uuid.UUID, corpo: GravacaoConexao, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.conectar(sessao, porta_id, corpo.porta_id, corpo.bem_id, corpo.descricao, corpo.forcar)
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.delete("/portas/{porta_id}/conexao", response_model=PortaDetalhe, summary="Desligar a porta", responses={**SEM_ACESSO, **resposta_nao_encontrado("Conexão")})
def desligar(porta_id: uuid.UUID, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.desconectar(sessao, porta_id)
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.post("/portas/{porta_id}/conexao/atras", response_model=PortaDetalhe, status_code=status.HTTP_201_CREATED, summary="Pôr um dispositivo atrás",
               description="Mais de um dispositivo na mesma porta, em cascata (switch → telefone IP → PC): entra atrás do último. A porta precisa ter um "
               "primeiro dispositivo (bem ou descrição): `409 sem_dispositivo`. Mesmo bem duas vezes na porta: `409 duplicado`.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def adicionar_atras(porta_id: uuid.UUID, corpo: GravacaoDispositivoAtras, usuario: Usuario = Depends(_exigir("editar")),
                    sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.adicionar_atras(sessao, porta_id, corpo.bem_id, corpo.descricao)
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.delete("/portas/{porta_id}/conexao/atras/{dispositivo_id}", response_model=PortaDetalhe, summary="Tirar um dispositivo de trás",
                 description="Os que vinham depois sobem uma posição.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Dispositivo")})
def remover_atras(porta_id: uuid.UUID, dispositivo_id: uuid.UUID, usuario: Usuario = Depends(_exigir("editar")),
                  sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.remover_atras(sessao, porta_id, dispositivo_id)
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


# ---------------------------------------------------------------------------------------------
# Modelos de face e VLANs
# ---------------------------------------------------------------------------------------------

@roteador.get("/modelos", response_model=list[ModeloLeitura], summary="Modelos de face", responses=SEM_ACESSO)
def modelos(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[ModeloLeitura]:
    return [_modelo(sessao, m) for m in servico.listar_modelos(sessao)]


@roteador.post("/modelos", response_model=ModeloLeitura, status_code=status.HTTP_201_CREATED, summary="Criar modelo de face",
               description="Grade (1–8 linhas × 1–64 colunas), numeração e portas extras (número maior que as da grade).", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_modelo(corpo: GravacaoModelo, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ModeloLeitura:
    with _traduzir(sessao):
        m = servico.salvar_modelo(sessao, None, corpo.nome, corpo.fabricante, corpo.linhas, corpo.colunas, corpo.numeracao,
                                  [x.model_dump() for x in corpo.portas_extras], corpo.altura_u)
        sessao.commit()
    return _modelo(sessao, m)


@roteador.put("/modelos/{modelo_id}", response_model=ModeloLeitura, summary="Alterar modelo de face",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Modelo de face")})
def alterar_modelo(modelo_id: uuid.UUID, corpo: GravacaoModelo, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ModeloLeitura:
    with _traduzir(sessao):
        m = servico.salvar_modelo(sessao, modelo_id, corpo.nome, corpo.fabricante, corpo.linhas, corpo.colunas, corpo.numeracao,
                                  [x.model_dump() for x in corpo.portas_extras], corpo.altura_u)
        sessao.commit()
    return _modelo(sessao, m)


@roteador.delete("/modelos/{modelo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir modelo de face",
                 description="Com equipamentos usando: `409 em_uso`.", responses={**SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Modelo de face")})
def excluir_modelo(modelo_id: uuid.UUID, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.excluir_modelo(sessao, modelo_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _vlan(sessao: Session, v: VlanRede) -> VlanLeitura:
    portas = (sessao.scalar(select(func.count()).select_from(PortaRede).where((PortaRede.vlan_nativa_id == v.id) | (PortaRede.vlan_voz_id == v.id))) or 0) + \
             (sessao.scalar(select(func.count()).select_from(PortaVlanRede).where(PortaVlanRede.vlan_id == v.id)) or 0)
    return VlanLeitura(id=v.id, numero=v.numero, nome=v.nome, descricao=v.descricao, portas=portas)


@roteador.get("/vlans", response_model=list[VlanLeitura], summary="VLANs", responses=SEM_ACESSO)
def vlans(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[VlanLeitura]:
    return [_vlan(sessao, v) for v in servico.listar_vlans(sessao)]


@roteador.post("/vlans", response_model=VlanLeitura, status_code=status.HTTP_201_CREATED, summary="Criar VLAN", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_vlan(corpo: GravacaoVlan, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> VlanLeitura:
    with _traduzir(sessao):
        v = servico.salvar_vlan(sessao, None, corpo.numero, corpo.nome, corpo.descricao)
        sessao.commit()
    return _vlan(sessao, v)


@roteador.put("/vlans/{vlan_id}", response_model=VlanLeitura, summary="Alterar VLAN", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("VLAN")})
def alterar_vlan(vlan_id: uuid.UUID, corpo: GravacaoVlan, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> VlanLeitura:
    with _traduzir(sessao):
        v = servico.salvar_vlan(sessao, vlan_id, corpo.numero, corpo.nome, corpo.descricao)
        sessao.commit()
    return _vlan(sessao, v)


@roteador.delete("/vlans/{vlan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir VLAN",
                 description="Em uso por alguma porta: `409 em_uso`.", responses={**SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("VLAN")})
def excluir_vlan(vlan_id: uuid.UUID, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.excluir_vlan(sessao, vlan_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Pontos de rede
# ---------------------------------------------------------------------------------------------

@roteador.get("/pontos", response_model=list[PontoLeitura], summary="Pontos de rede", responses=SEM_ACESSO,
              description="Até 500, por código ou sala, com o caminho até o switch.")
def pontos(busca: str = Query("", max_length=40), localizacao_id: uuid.UUID | None = Query(None), _: Usuario = Depends(_exigir("ver")),
           sessao: Session = Depends(obter_sessao)) -> list[PontoLeitura]:
    itens = servico.listar_pontos(sessao, busca, localizacao_id)
    salas = _salas(sessao, [x.localizacao_id for x in itens])
    return [_ponto(sessao, x, salas) for x in itens]


@roteador.post("/pontos", response_model=PontoLeitura, status_code=status.HTTP_201_CREATED, summary="Cadastrar ponto de rede",
               description="Código único (como na tomada); a porta do patch panel só pode ser de um ponto.", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_ponto(corpo: GravacaoPonto, _: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PontoLeitura:
    with _traduzir(sessao):
        pt = servico.salvar_ponto(sessao, None, corpo.codigo, corpo.localizacao_id, corpo.porta_id, corpo.observacao)
        sessao.commit()
    return _ponto(sessao, pt, _salas(sessao, [pt.localizacao_id]))


@roteador.put("/pontos/{ponto_id}", response_model=PontoLeitura, summary="Alterar ponto de rede",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Ponto de rede")})
def alterar_ponto(ponto_id: uuid.UUID, corpo: GravacaoPonto, _: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PontoLeitura:
    with _traduzir(sessao):
        pt = servico.salvar_ponto(sessao, ponto_id, corpo.codigo, corpo.localizacao_id, corpo.porta_id, corpo.observacao)
        sessao.commit()
    return _ponto(sessao, pt, _salas(sessao, [pt.localizacao_id]))


@roteador.delete("/pontos/{ponto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir ponto de rede",
                 description="Os chamados que apontavam o ponto ficam sem ele.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Ponto de rede")})
def excluir_ponto(ponto_id: uuid.UUID, _: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.excluir_ponto(sessao, ponto_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Bens do Patrimônio (a ligação aparece no cadastro do bem e na porta)
# ---------------------------------------------------------------------------------------------

@roteador.get("/bens", response_model=list[BemResumo], summary="Buscar bem do Patrimônio", responses=SEM_ACESSO,
              description="Até 20 bens não baixados pela chapa ou pela descrição (mínimo 2 caracteres), para ligar numa porta.")
def bens(busca: str = Query("", max_length=100), _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[BemResumo]:
    itens = servico.buscar_bens(sessao, busca)
    salas = _salas(sessao, [b.localizacao_id for b in itens])
    return [BemResumo(id=b.id, chapa=b.chapa or "", descricao=b.descricao, sala=salas.get(b.localizacao_id, "")) for b in itens]


@roteador.get("/bens/{bem_id}/portas", response_model=list[PortaDoBem], summary="Portas em que o bem está ligado", responses={**SEM_ACESSO, **resposta_nao_encontrado("Bem")},
              description="Para o cadastro do bem no Patrimônio: em qual switch e porta ele está ligado. Ligar e desligar usam `POST`/`DELETE /rede/portas/{id}/conexao`.")
def portas_do_bem(bem_id: uuid.UUID, _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[PortaDoBem]:
    with _traduzir(sessao):
        resultado = []
        for p, conexao, dispositivo in servico.portas_do_bem(sessao, bem_id):
            frente = ""
            if conexao is not None:
                primeiro = sessao.get(Bem, conexao.bem_id) if conexao.bem_id else None
                frente = _texto_bem(primeiro) if primeiro else conexao.descricao
            resultado.append(PortaDoBem(porta_id=p.id, porta_nome=p.nome or str(p.numero_logico), equipamento_id=p.equipamento_id,
                                        equipamento_nome=p.equipamento.nome, atras_de=frente, dispositivo_id=dispositivo.id if dispositivo else None))
        return resultado


# ---------------------------------------------------------------------------------------------
# Racks
# ---------------------------------------------------------------------------------------------

def _rack(sessao: Session, r: RackRede, salas: dict) -> RackLeitura:
    total = sessao.scalar(select(func.count()).select_from(EquipamentoRede).where(EquipamentoRede.rack_id == r.id)) or 0
    return RackLeitura(id=r.id, nome=r.nome, cor=r.cor, localizacao_id=r.localizacao_id, altura_u=r.altura_u, observacao=r.observacao,
                       sala=salas.get(r.localizacao_id, ""), equipamentos=total)


@roteador.get("/racks", response_model=list[RackLeitura], summary="Racks", responses=SEM_ACESSO,
              description="Os racks (nome, cor, sala do Patrimônio e altura em U), com quantos equipamentos têm.")
def racks(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[RackLeitura]:
    itens = servico.listar_racks(sessao)
    salas = _salas(sessao, [r.localizacao_id for r in itens])
    return [_rack(sessao, r, salas) for r in itens]


@roteador.post("/racks", response_model=RackLeitura, status_code=status.HTTP_201_CREATED, summary="Cadastrar rack", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_rack(corpo: GravacaoRack, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> RackLeitura:
    with _traduzir(sessao):
        r = servico.salvar_rack(sessao, None, corpo.nome, corpo.cor, corpo.localizacao_id, corpo.altura_u, corpo.observacao)
        sessao.commit()
    return _rack(sessao, r, _salas(sessao, [r.localizacao_id]))


@roteador.put("/racks/{rack_id}", response_model=RackLeitura, summary="Alterar rack",
              description="Diminuir a altura não pode deixar equipamento para fora (`409 em_uso`).", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Rack")})
def alterar_rack(rack_id: uuid.UUID, corpo: GravacaoRack, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> RackLeitura:
    with _traduzir(sessao):
        r = servico.salvar_rack(sessao, rack_id, corpo.nome, corpo.cor, corpo.localizacao_id, corpo.altura_u, corpo.observacao)
        sessao.commit()
    return _rack(sessao, r, _salas(sessao, [r.localizacao_id]))


@roteador.delete("/racks/{rack_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir rack",
                 description="Com equipamentos: `409 em_uso`.", responses={**SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Rack")})
def excluir_rack(rack_id: uuid.UUID, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.excluir_rack(sessao, rack_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/salas", response_model=list[SalaResumo], summary="Buscar sala do Patrimônio", responses=SEM_ACESSO,
              description="Até 20 salas ativas pelo código ou pelo nome (mínimo 2 caracteres); com `todas=true`, todas as salas ativas por andar "
                          "(o campo de sala do rack filtra enquanto se digita).")
def salas(busca: str = Query("", max_length=60), todas: bool = Query(False, description="Todas as salas ativas, sem busca."),
          _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[SalaResumo]:
    from app.services.patrimonio import servico_localizacoes

    return [SalaResumo(id=x.id, codigo=x.codigo or "", nome=x.nome, rotulo=servico_localizacoes.rotulo_curto(x), andar=x.andar)
            for x in servico.buscar_salas(sessao, busca, todas)]
