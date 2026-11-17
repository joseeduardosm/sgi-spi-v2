"""
===============================================================================
ARQUIVO: rede.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Expor a API do plano de face da rede (/api/rede): equipamentos (switches,
patch panels, roteadores), modelos de face, portas e suas conexões, VLANs,
pontos de rede, racks, topologia, indicadores e a ligação com os bens do
Patrimônio.

RESUMO TÉCNICO:
Recurso da ACL `rede`, fechado até haver regras (na prática, só o SuperRoot).
Os papéis vêm de servico.papeis e são exigidos pela dependência _exigir:
- ver (Leitura) consulta tudo;
- editar (Modificação) muda portas, conexões, dispositivos e pontos;
- administrar (Controle total) cuida de modelos, equipamentos, VLANs, racks
  e parâmetros (intervalo do ping).
As funções _modelo, _resumo, _portas, _detalhe, _ponto, _vlan e _rack montam
as respostas juntando dados em lote (poucas consultas por tela). Erros do
serviço (ErroRede) viram {detalhe, codigo} via _traduzir. Toda alteração
de porta é auditada (servico.auditar_portas).

FINALIDADE DE NEGÓCIO:
Documenta a rede física da SPI: o que está ligado em cada porta, em qual
ponto de tomada, em que sala e rack, e o caminho até o núcleo. Ajuda o
suporte a achar um equipamento, abrir chamado sobre uma porta e manter o
cadastro em dia. O SGI não configura o switch: é só o cadastro.

CONTEXTO NO SISTEMA:
Regras em app/services/rede/servico.py (e ping.py para o monitoramento),
modelos em app/models/rede.py, schemas em app/schemas/rede.py. Usa bens e
salas do Patrimônio (app/models/patrimonio.py) e chamados do módulo
Chamados (app/services/chamados/acesso.py). Documentação em
docs/endpoints/rede.md; tela Rede no frontend.

===============================================================================
"""

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
from app.models.rede import ConexaoRede, LeituraRede, DispositivoAtrasRede, EquipamentoRede, ModeloFaceRede, PontoRede, PortaRede, PortaVlanRede, RackRede, VlanRede
from app.models.usuario import Usuario
from app.schemas.comum import RespostaErro
from app.schemas.rede import (
    AplicacaoLeitura, BemResumo, CaminhoRede, CriacaoEquipamento, DestinoCadastro, PortaElegivel, FuncaoEquipamento, TipoEquipamento, EscritaEquipamento, ResultadoTesteLeitura, ResumoLeitura, TesteLeitura, TrocaConexao, ChamadoDaPorta, DispositivoCaminho, EtapaCaminho, ParametrosRede, ConexaoLeitura, DispositivoAtrasLeitura, GravacaoDispositivoAtras, GravacaoRack, PortaDoBem, RackLeitura, SalaResumo, EquipamentoDetalhe, EquipamentoResumo, GravacaoConexao, GravacaoModelo, GravacaoPonto,
    GravacaoPorta, GravacaoVlan, IndicadoresRede, ModeloLeitura, NoTopologia, PapeisRede, PontoLeitura, PortaDetalhe, PortaLeitura, PortaListada, TopologiaRede, VlanLeitura,
)
from app.services.chamados import acesso as acesso_chamados
from app.services.rede import ping, servico, servico_leitura
from app.services.rede.servico import DadosEquipamento, DadosLigacaoCadastro, DadosPorta, ErroRede
from app.services.servico_auditoria import auditar

# APIRouter agrupa as rotas deste módulo sob /rede, com a etiqueta usada na documentação OpenAPI.
roteador = APIRouter(prefix="/rede", tags=["Rede (plano de face)"], responses=VALIDACAO)

SEM_ACESSO = {status.HTTP_403_FORBIDDEN: {"model": RespostaErro, "description": "Sem o nível necessário no recurso `rede` (`acesso_negado`)."}}


def _papeis(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> tuple[Usuario, servico.PapeisRede]:
    """
    Dependência do FastAPI que devolve o usuário logado e os papéis dele na Rede (ver,
    editar, administrar).

    Depends(...) faz o FastAPI chamar obter_usuario_atual e obter_sessao antes, a cada
    requisição.
    """
    return usuario, servico.papeis(sessao, usuario)


def _exigir(nivel: str):
    """
    Fábrica de dependência: devolve uma função que exige o papel mínimo (`ver`, `editar`
    ou `administrar`).

    Uso: `Depends(_exigir("editar"))`. Sem o papel, responde 403 `acesso_negado` com uma
    mensagem própria do papel; com o papel, devolve o usuário logado.
    """
    def verificar(ctx: tuple[Usuario, servico.PapeisRede] = Depends(_papeis)) -> Usuario:
        if not getattr(ctx[1], nivel):
            mensagens = {"ver": "Você não tem acesso ao plano de face.", "editar": "Só quem edita a rede muda portas, conexões e pontos.",
                         "administrar": "Só a administração da rede cuida de modelos, equipamentos e VLANs."}
            raise ErroApi(status.HTTP_403_FORBIDDEN, mensagens[nivel], "acesso_negado")
        return ctx[0]
    return verificar


@contextmanager
def _traduzir(sessao: Session):
    """
    Gerenciador de contexto (usado com `with`): erro de regra do serviço (ErroRede)
    desfaz a transação e vira ErroApi com o status e o código do erro.
    """
    try:
        yield
    except ErroRede as erro:
        sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


# ---------------------------------------------------------------------------------------------
# Montagem das respostas
# ---------------------------------------------------------------------------------------------

def _modelo(sessao: Session, m: ModeloFaceRede) -> ModeloLeitura:
    """
    Converte um modelo de face para a resposta, contando quantos equipamentos o usam (o
    modelo em uso tem a grade travada).
    """
    em_uso = sessao.scalar(select(func.count()).select_from(EquipamentoRede).where(EquipamentoRede.modelo_face_id == m.id)) or 0
    return ModeloLeitura(id=m.id, nome=m.nome, fabricante=m.fabricante, linhas=m.linhas, colunas=m.colunas, numeracao=m.numeracao,
                         portas_extras=m.portas_extras or [], altura_u=m.altura_u, equipamentos=em_uso)


def _resumo(sessao: Session, e: EquipamentoRede, contagem: Counter, salas: dict) -> dict:
    """
    Monta o dicionário de resumo de um equipamento (campos comuns a EquipamentoResumo e
    EquipamentoDetalhe).

    `contagem` traz o total de portas e quantas estão up, down e desativadas; `salas` é
    um cache id -> nome da sala do Patrimônio.
    """
    return dict(id=e.id, nome=e.nome, tipo=e.tipo, modelo_face_id=e.modelo_face_id, bem_id=e.bem_id, localizacao_id=e.localizacao_id, rack_id=e.rack_id, rack_nome=e.rack.nome if e.rack else "",
                posicao_u=e.posicao_u, ip_gerencia=e.ip_gerencia, numero_serie=e.numero_serie, observacao=e.observacao, ativo=e.ativo,
                modelo_nome=e.modelo_face.nome if e.modelo_face else "", altura_u=e.modelo_face.altura_u if e.modelo_face else 1, sala=salas.get(e.localizacao_id, ""), portas_total=contagem["total"],
                portas_up=contagem["up"], portas_down=contagem["down"], portas_desativadas=contagem["desativada"], funcao=e.funcao,
                ping_situacao=e.ping_situacao, ping_verificado_em=e.ping_verificado_em, ping_mudou_em=e.ping_mudou_em, cadastro_incompleto=servico.cadastro_incompleto(e),
                acesso_usuario=e.acesso_usuario, acesso_porta=e.acesso_porta, tem_acesso=bool(e.acesso_usuario and e.acesso_senha),
                leitura_em=sessao.scalar(select(func.max(LeituraRede.lido_em)).where(LeituraRede.equipamento_id == e.id)))


def _salas(sessao: Session, ids) -> dict:
    """
    Busca de uma vez o nome das salas (localizações do Patrimônio) pelos ids informados,
    ignorando nulos. Devolve {id: nome}.
    """
    ids = {i for i in ids if i}
    return {x.id: x.nome for x in sessao.scalars(select(Localizacao).where(Localizacao.id.in_(ids)))} if ids else {}


def _rotulo_porta(sessao: Session, porta_id: uuid.UUID, cache: dict) -> tuple[str, uuid.UUID | None]:
    """
    Texto "Equipamento · porta N" de uma porta e o id do equipamento dela.

    Usa `cache` (dicionário compartilhado pelo chamador) para não buscar a mesma porta
    duas vezes. Porta que não existe mais vira "(porta removida)".
    """
    if porta_id not in cache:
        p = sessao.get(PortaRede, porta_id)
        cache[porta_id] = (f"{p.equipamento.nome} · porta {p.nome or p.numero_logico}", p.equipamento_id) if p else ("(porta removida)", None)
    return cache[porta_id]


def _texto_bem(b) -> str:
    """Texto curto de um bem do Patrimônio: descrição e chapa (número de tombamento)."""
    return f"{getattr(b, 'descricao', '') or 'Bem'} (chapa {b.chapa or '—'})"


def _portas(sessao: Session, portas: list[PortaRede]) -> list[PortaLeitura]:
    """
    Monta a leitura de uma lista de portas com tudo que a face do equipamento mostra.

    Para evitar uma consulta por porta, carrega em lote: VLANs, conexões das portas,
    dispositivos em cascata (atrás), bens ligados, pontos de rede e quantidade de
    chamados abertos por porta. Depois, para cada porta, descreve o outro lado da
    conexão (outra porta, um bem ou só uma descrição) e separa as VLANs com tag e sem
    tag.
    """
    ids = [p.id for p in portas]
    vlans = {v.id: v.numero for v in sessao.scalars(select(VlanRede))}
    conexoes = list(sessao.scalars(select(ConexaoRede).where((ConexaoRede.porta_a_id.in_(ids)) | (ConexaoRede.porta_b_id.in_(ids))))) if ids else []
    # Por porta, as ligações dela com o lado (no patch panel, até duas: fundo e frente): (ligação, lado desta porta, outra porta, lado da outra)
    por_porta: dict[uuid.UUID, list[tuple]] = defaultdict(list)
    for c in conexoes:
        por_porta[c.porta_a_id].append((c, c.lado_a, c.porta_b_id, c.lado_b))
        if c.porta_b_id:
            por_porta[c.porta_b_id].append((c, c.lado_b, c.porta_a_id, c.lado_a))
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
    def leitura(c, lado, outra, outro_lado) -> ConexaoLeitura:
        """O outro lado de uma ligação desta porta: outra porta (com o lado, se for patch panel), um bem ou só uma descrição."""
        if outra:
            texto, equipamento_id = _rotulo_porta(sessao, outra, cache)
            return ConexaoLeitura(tipo="porta", lado=lado, outro_lado=outro_lado, texto=texto + (f" ({outro_lado})" if outro_lado else ""),
                                  porta_id=outra, equipamento_id=equipamento_id)
        fila = [DispositivoAtrasLeitura(id=d.id, ordem=d.ordem, bem_id=d.bem_id, texto=_texto_bem(bens.get(d.bem_id)) if d.bem_id in bens else d.descricao)
                for d in atras.get(c.id, [])]
        if c.bem_id and c.bem_id in bens:
            return ConexaoLeitura(tipo="bem", lado=lado, texto=_texto_bem(bens[c.bem_id]), bem_id=c.bem_id, atras=fila)
        return ConexaoLeitura(tipo="descricao", lado=lado, texto=c.descricao, atras=fila)

    for p in portas:
        lados = {lado: leitura(c, lado, outra, outro_lado) for c, lado, outra, outro_lado in por_porta.get(p.id, [])}
        # Fora do patch panel há uma ligação só (lado vazio); no patch panel, a primeira que houver (fundo, depois frente)
        conexao = lados.get(None) or lados.get("fundo") or lados.get("frente")
        # VLAN com tag (trunk) e sem tag (hybrid) ficam em listas separadas, ordenadas pelo número.
        tag = sorted(vlans[x.vlan_id] for x in p.vlans if x.com_tag and x.vlan_id in vlans)
        sem_tag = sorted(vlans[x.vlan_id] for x in p.vlans if not x.com_tag and x.vlan_id in vlans)
        resultado.append(PortaLeitura(
            id=p.id, numero_logico=p.numero_logico, nome=p.nome, descricao=p.descricao, mac=p.mac, velocidade_mbps=p.velocidade_mbps, duplex=p.duplex,
            status=p.status, modo=p.modo, vlan_nativa_id=p.vlan_nativa_id, vlan_nativa=vlans.get(p.vlan_nativa_id), vlans_tag=tag,
            vlans_tag_ids=[x.vlan_id for x in p.vlans if x.com_tag], vlans_sem_tag=sem_tag, vlans_sem_tag_ids=[x.vlan_id for x in p.vlans if not x.com_tag],
            vlan_voz_id=p.vlan_voz_id, vlan_voz=vlans.get(p.vlan_voz_id), ip_interface=p.ip_interface, ultima_mudanca=p.ultima_mudanca, erros_entrada=p.erros_entrada, erros_saida=p.erros_saida,
            conexao=conexao, fundo=lados.get("fundo"), frente=lados.get("frente"), observacao=p.observacao,
            ponto=pontos.get(p.id, ""), chamados_abertos=abertos.get(p.id, 0),
        ))
    return resultado


def _detalhe(sessao: Session, e: EquipamentoRede) -> EquipamentoDetalhe:
    """
    Monta a face completa de um equipamento: resumo, modelo, posição de cada porta na
    grade, portas e a última alteração.
    """
    contagem = servico.resumo_portas(sessao, [e.id])[e.id]
    return EquipamentoDetalhe(**_resumo(sessao, e, contagem, _salas(sessao, [e.localizacao_id])),
                              modelo=_modelo(sessao, e.modelo_face) if e.modelo_face else None,
                              posicoes=servico.posicoes(e.modelo_face) if e.modelo_face else {}, portas=_portas(sessao, list(e.portas)),
                              **servico.ultima_alteracao_do_equipamento(sessao, e))


def _ponto(sessao: Session, pt: PontoRede, salas: dict) -> PontoLeitura:
    """
    Converte um ponto de rede (tomada) para a resposta, com o caminho em texto da tomada
    até o switch.
    """
    cache: dict = {}
    caminho = [_rotulo_porta(sessao, p.id, cache)[0] for p in servico.caminho_do_ponto(sessao, pt)]
    return PontoLeitura(id=pt.id, codigo=pt.codigo, localizacao_id=pt.localizacao_id, porta_id=pt.porta_id, observacao=pt.observacao,
                        sala=salas.get(pt.localizacao_id, ""), caminho=caminho)


# ---------------------------------------------------------------------------------------------
# Contexto e equipamentos
# ---------------------------------------------------------------------------------------------

# Rotas de contexto e equipamentos. Responde 200 mesmo sem papel: a tela usa as flags para esconder
# o módulo.
@roteador.get("/contexto", response_model=PapeisRede, summary="Papéis no plano de face",
              description="O que a pessoa pode fazer (200 mesmo sem nenhum papel: a tela esconde o módulo).")
def contexto(ctx: tuple[Usuario, servico.PapeisRede] = Depends(_papeis)) -> PapeisRede:
    return PapeisRede(**ctx[1].__dict__)


@roteador.get("/parametros", response_model=ParametrosRede, summary="Parâmetros da Rede", responses=SEM_ACESSO,
              description="Configurações do módulo: o intervalo entre as rodadas de ping dos equipamentos.")
def parametros(_: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ParametrosRede:
    return ParametrosRede(ping_intervalo_min=ping.intervalo_min(sessao))


# Grava o intervalo do ping, registra na auditoria e confirma (commit) a transação.
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
    # Percorre a árvore com uma pilha (sem recursão) só para juntar todos os equipamentos e buscar
    # as salas de uma vez.
    pilha = [*raizes, *sem_ligacao]
    while pilha:
        n = pilha.pop()
        todos.append(n.equipamento)
        pilha.extend(n.filhos or [])
    # Sem sala própria, o equipamento fica na sala do rack
    salas = _salas(sessao, [i for e in todos for i in (e.localizacao_id, e.rack.localizacao_id if e.rack else None)])

    # Converte, recursivamente, cada nó da árvore do serviço no schema NoTopologia da resposta.
    def montar(n: servico.NoTopologia) -> NoTopologia:
        e = n.equipamento
        sala = salas.get(e.localizacao_id) or (salas.get(e.rack.localizacao_id, "") if e.rack else "")
        return NoTopologia(id=e.id, nome=e.nome, tipo=e.tipo, funcao=e.funcao, ping_situacao=e.ping_situacao, assumiu=n.assumiu, rack_nome=e.rack.nome if e.rack else "", rack_cor=e.rack.cor if e.rack else None, sala=sala,
                           ip_gerencia=e.ip_gerencia, portas_total=n.portas_total, portas_up=n.portas_up, portas_down=n.portas_down, pontos=n.pontos,
                           bens=n.bens, porta_acima=n.porta_acima, porta_no_pai=n.porta_no_pai, cabos_com_pai=n.cabos_com_pai,
                           tambem_ligado=n.tambem_ligado or [], filhos=[montar(f) for f in n.filhos or []])

    return TopologiaRede(raizes=[montar(r) for r in raizes], sem_ligacao=[montar(n) for n in sem_ligacao])


def _listadas(itens: list[servico.PortaListada]) -> list[PortaListada]:
    """
    Converte as portas listadas pelo serviço (alteradas recentemente ou sem descrição)
    para a resposta, com quem e quando alterou por último.
    """
    return [PortaListada(porta_id=i.porta.id, equipamento_id=i.porta.equipamento_id, equipamento_nome=i.porta.equipamento.nome,
                         porta=i.porta.nome or str(i.porta.numero_logico), numero_logico=i.porta.numero_logico, descricao=i.porta.descricao,
                         alterado_por=i.alterado_por, alterado_em=i.alterado_em) for i in itens]


@roteador.get("/indicadores", response_model=IndicadoresRede, summary="Indicadores da Rede", responses=SEM_ACESSO,
              description="Os cards do topo: portas alteradas nos últimos 7 dias (qualquer atributo: configuração, ligação, dispositivo atrás, ponto ou "
                          "carga LLDP) e portas ligadas sem descrição.")
def indicadores(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> IndicadoresRede:
    return IndicadoresRede(**servico.indicadores(sessao))


@roteador.get("/portas-alteradas", response_model=list[PortaListada], summary="Portas alteradas nos últimos 7 dias", responses=SEM_ACESSO,
              description="Cada porta uma vez, com a última alteração dos últimos 7 dias (quem e quando), da mais recente para a mais antiga.")
def portas_alteradas(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[PortaListada]:
    return _listadas(servico.portas_alteradas(sessao))


@roteador.get("/portas-patch-um-lado", response_model=list[PortaListada], summary="Portas de patch panel com um lado só", responses=SEM_ACESSO,
              description="Portas de patch panel com um lado (fundo ou frente) ligado e o outro vazio, com a última alteração de cada uma (de qualquer época).")
def portas_patch_um_lado(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[PortaListada]:
    return _listadas(servico.portas_patch_um_lado(sessao))


@roteador.get("/equipamentos", response_model=list[EquipamentoResumo], summary="Equipamentos", responses=SEM_ACESSO,
              description="Switches, patch panels e roteadores, com a contagem de portas por status.")
def equipamentos(busca: str = Query("", max_length=100), tipo: str | None = Query(None), _: Usuario = Depends(_exigir("ver")),
                 sessao: Session = Depends(obter_sessao)) -> list[EquipamentoResumo]:
    itens = servico.listar_equipamentos(sessao, busca, tipo)
    contagens = servico.resumo_portas(sessao, [e.id for e in itens])
    salas = _salas(sessao, [e.localizacao_id for e in itens])
    return [EquipamentoResumo(**_resumo(sessao, e, contagens[e.id], salas)) for e in itens]


# Padrão das rotas de gravação deste módulo: dentro de _traduzir, chama o serviço, audita e faz
# commit; só depois relê o equipamento para a resposta.
def _dados_porta(g: GravacaoPorta | None) -> DadosPorta | None:
    """Converte a gravação de porta da API para o formato do serviço (sem a parte só da tela)."""
    if g is None:
        return None
    return DadosPorta(observacao=g.observacao, modo=g.modo, vlan_nativa_id=g.vlan_nativa_id, vlans_tag=g.vlans_tag, vlans_sem_tag=g.vlans_sem_tag,
                      vlan_voz_id=g.vlan_voz_id, ip_interface=g.ip_interface, velocidade_mbps=g.velocidade_mbps, duplex=g.duplex, status=g.status)


@roteador.get("/equipamentos/destinos-cadastro", response_model=list[DestinoCadastro], summary="Onde o equipamento novo pode ser ligado",
              description="Para o passo Conexão do cadastro em cadeia: os equipamentos elegíveis para ficar acima de um equipamento novo deste tipo e "
                          "função (switch que pode ficar acima e chega ao core; patch panel com uma porta cujo outro lado leva a ele) e, de cada um, as "
                          "portas livres que servem (com o lado, no patch panel). Só leitura; as mesmas regras são conferidas de novo ao cadastrar.",
              responses={**SEM_ACESSO})
def destinos_cadastro(tipo: TipoEquipamento, funcao: FuncaoEquipamento | None = None, _: Usuario = Depends(_exigir("administrar")),
                      sessao: Session = Depends(obter_sessao)) -> list[DestinoCadastro]:
    with _traduzir(sessao):
        return [DestinoCadastro(equipamento_id=e.id, portas=[PortaElegivel(porta_id=p.id, lado=lado) for p, lado in portas])
                for e, portas in servico.destinos_do_cadastro(sessao, tipo, funcao)]


@roteador.post("/equipamentos", response_model=EquipamentoDetalhe, status_code=status.HTTP_201_CREATED, summary="Cadastrar equipamento",
               description="Cadastro **em cadeia** (core → distribuição → acesso → APs/roteadores/outros): sem o core, não entra distribuição; sem core "
                           "e distribuição, não entra acesso; sem acesso, não entra AP (`409 cadeia_incompleta`). Todo equipamento, menos core primário e "
                           "patch panel, já entra com o cabo para quem fica acima dele (`ligacao`): a porta dele, a porta do outro (direto ou num patch "
                           "panel, com o lado, desde que o outro lado daquela porta leve a quem pode ficar acima) e a configuração das duas. As portas "
                           "nascem do modelo de face, desligadas e em branco.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_equipamento(corpo: CriacaoEquipamento, usuario: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        dados = corpo.model_dump(exclude={"ligacao"})
        lig = corpo.ligacao
        ligacao = DadosLigacaoCadastro(porta_numero=lig.porta_numero, destino_porta_id=lig.destino_porta_id, destino_lado=lig.destino_lado,
                                       config=_dados_porta(lig.config), config_destino=_dados_porta(lig.config_destino)) if lig else None
        e = servico.salvar_equipamento(sessao, None, DadosEquipamento(**dados, ligacao=ligacao))
        auditar(sessao, usuario.login, "rede.equipamento.criar", e.nome, autor_id=usuario.id)
        if ligacao is not None:
            propria = next((p.id for p in e.portas if p.numero_logico == ligacao.porta_numero), None)
            servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ligar", [propria, ligacao.destino_porta_id])
        sessao.commit()
    return _detalhe(sessao, servico.obter_equipamento(sessao, e.id))


@roteador.get("/equipamentos/{equipamento_id}", response_model=EquipamentoDetalhe, summary="Face do equipamento",
              description="O equipamento, o modelo (grade, numeração, portas extras), a posição de cada porta na grade e as portas com a configuração "
              "lógica, o que está ligado, o ponto de rede e os chamados abertos.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Equipamento")})
def equipamento(equipamento_id: uuid.UUID, _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        return _detalhe(sessao, servico.obter_equipamento(sessao, equipamento_id))


@roteador.put("/equipamentos/{equipamento_id}", response_model=EquipamentoDetalhe, summary="Alterar equipamento",
              description="O modelo de face, o tipo e a função não mudam depois de criado: `409 modelo_travado` / `409 tipo_travado` / "
                          "`409 funcao_travada` (exclua e cadastre de novo). Só o equipamento antigo sem modelo pode recebê-lo uma vez (as portas são criadas por ele).",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Equipamento")})
def alterar_equipamento(equipamento_id: uuid.UUID, corpo: EscritaEquipamento, usuario: Usuario = Depends(_exigir("administrar")),
                        sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        e = servico.salvar_equipamento(sessao, equipamento_id, DadosEquipamento(**corpo.model_dump()))
        auditar(sessao, usuario.login, "rede.equipamento.alterar", e.nome, autor_id=usuario.id, alvo_tipo="rede_equipamento", alvo_id=e.id)
        sessao.commit()
    return _detalhe(sessao, servico.obter_equipamento(sessao, e.id))


# ---------------------------------------------------------------------------------------------
# Leitura do equipamento por SSH (carga)
# ---------------------------------------------------------------------------------------------

def _resumo_leitura(sessao: Session, equipamento_id: uuid.UUID, registro: LeituraRede) -> ResumoLeitura:
    return ResumoLeitura(**servico_leitura.resumo(sessao, servico.obter_equipamento(sessao, equipamento_id), registro))


@roteador.post("/leitura/testar", response_model=ResultadoTesteLeitura, summary="Testar e ler um equipamento (cadastro)",
               description="Entra por SSH **só leitura** (comandos display/show) no IP informado e devolve o que leu, sem gravar nada: nome, modelo, "
                           "série, versão, quantas portas e VLANs, vizinhos LLDP e a **sugestão do cabo de subida** (vizinho já cadastrado que pode "
                           "ficar acima, com a porta livre). Detecta o fabricante (Huawei, Dell, H3C, Cisco) e tenta outros se não der. Acesso "
                           "recusado ou sem resposta: `409 leitura_falhou`.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def testar_leitura(corpo: TesteLeitura, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ResultadoTesteLeitura:
    with _traduzir(sessao):
        return ResultadoTesteLeitura(**servico_leitura.testar(sessao, corpo.ip.strip(), corpo.usuario, corpo.senha, corpo.porta, corpo.modelo_face_id,
                                                               corpo.tipo, corpo.funcao))


@roteador.post("/equipamentos/{equipamento_id}/leitura", response_model=ResumoLeitura, status_code=status.HTTP_201_CREATED,
               summary="Ler o equipamento (carga)",
               description="Lê o equipamento por SSH com o acesso gravado nele, **liga sozinho os vizinhos LLDP** já cadastrados (quando as duas portas "
                           "estão livres), guarda a leitura e devolve o resumo do que mais pode ser aplicado. Sem acesso gravado: `400 sem_acesso`; "
                           "falha de acesso: `409 leitura_falhou`.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Equipamento")})
def ler_equipamento(equipamento_id: uuid.UUID, usuario: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> ResumoLeitura:
    with _traduzir(sessao):
        registro = servico_leitura.ler_e_guardar(sessao, equipamento_id, usuario.login)
        ligadas = [i["porta_id"] for i in registro.resultado.get("lldp", []) if i.get("situacao") == "ligada" and i.get("porta_id")]
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ligar", [uuid.UUID(x) for x in ligadas])
        auditar(sessao, usuario.login, "rede.equipamento.leitura", str(equipamento_id), autor_id=usuario.id, alvo_tipo="rede_equipamento", alvo_id=equipamento_id)
        sessao.commit()
        return _resumo_leitura(sessao, equipamento_id, registro)


@roteador.get("/equipamentos/{equipamento_id}/leitura", response_model=ResumoLeitura | None, summary="Última leitura do equipamento",
              description="O resumo da leitura mais recente (nulo se o equipamento nunca foi lido).",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Equipamento")})
def ultima_leitura(equipamento_id: uuid.UUID, _: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> ResumoLeitura | None:
    with _traduzir(sessao):
        servico.obter_equipamento(sessao, equipamento_id)
        registro = servico_leitura.ultima_leitura(sessao, equipamento_id)
        return _resumo_leitura(sessao, equipamento_id, registro) if registro else None


@roteador.post("/equipamentos/{equipamento_id}/leitura/aplicar", response_model=EquipamentoDetalhe, summary="Aplicar a leitura",
               description="Grava os itens marcados da última leitura: número de série, VLANs novas, portas ligadas pela descrição do switch e a "
                           "configuração lida (modo, VLANs, velocidade, duplex) — esta só nas portas ligadas, pela regra do SGI. Sem leitura: 404.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Leitura")})
def aplicar_leitura(equipamento_id: uuid.UUID, corpo: AplicacaoLeitura, usuario: Usuario = Depends(_exigir("administrar")),
                    sessao: Session = Depends(obter_sessao)) -> EquipamentoDetalhe:
    with _traduzir(sessao):
        e = servico.obter_equipamento(sessao, equipamento_id)
        registro = servico_leitura.ultima_leitura(sessao, equipamento_id)
        if registro is None:
            raise ErroRede("Este equipamento ainda não foi lido.", 404, "nao_encontrado")
        portas = servico_leitura.aplicar(sessao, e, registro, servico_leitura.EscolhasLeitura(**corpo.model_dump()), usuario.login)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.configurar", portas)
        auditar(sessao, usuario.login, "rede.equipamento.leitura_aplicada", e.nome, autor_id=usuario.id, alvo_tipo="rede_equipamento", alvo_id=e.id)
        sessao.commit()
    return _detalhe(sessao, servico.obter_equipamento(sessao, equipamento_id))


@roteador.delete("/equipamentos/{equipamento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir equipamento",
                 description="Apaga as portas e as conexões delas; os chamados ficam sem a porta. Não deixa outro equipamento sem cabo para quem fica "
                             "acima dele (`409 unica_ligacao_para_cima`), e as portas do outro lado ficam em branco.",
                 responses={**SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Equipamento")})
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
    """
    Monta o painel de uma porta: a leitura da porta, o equipamento e os chamados ligados
    a ela.

    Os chamados respeitam a visibilidade do módulo Chamados: quem não tem papel lá
    recebe a lista vazia, e quem tem vê só os chamados do seu alcance.
    """
    p = acesso_chamados.papeis(sessao, usuario)
    chamados = []
    if p.algum:
        visivel = acesso_chamados.filtro_visibilidade(acesso_chamados.alcance(sessao, usuario, p))
        chamados = [ChamadoDaPorta(numero=c.numero, titulo=c.titulo, status_base=c.status_base, aberto_em=c.aberto_em)
                    for c in servico.chamados_da_porta(sessao, porta, visivel)]
    return PortaDetalhe(**_portas(sessao, [porta])[0].model_dump(), equipamento_id=porta.equipamento_id, equipamento_nome=porta.equipamento.nome,
                        equipamento_tipo=porta.equipamento.tipo, chamados=chamados,
                        **dict(zip(("alterado_por", "alterado_em"), servico.ultima_alteracao_da_porta(sessao, porta.id))))


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
                             porta_entrada=portas.get(e.porta_entrada_id), porta_saida=portas.get(e.porta_saida_id),
                             lado_entrada=e.lado_entrada, lado_saida=e.lado_saida) for e in c.etapas],
        dispositivos=[DispositivoCaminho(texto=t, bem_id=b) for t, b in c.dispositivos], cabo_dispositivos=c.cabo_dispositivos, aviso=c.aviso)


@roteador.put("/portas/{porta_id}", response_model=PortaDetalhe, summary="Configurar porta",
              description="Observação (texto livre), modo (access, trunk, hybrid, QinQ, dinâmico auto/desirable ou roteada), VLAN access/nativa/PVID/"
              "externa, VLANs com tag (trunk, hybrid, dinâmicas), VLANs sem tag (hybrid), VLAN de voz (access, hybrid, dinâmicas), IP da interface "
              "(roteada), velocidade, duplex e status. A **descrição não é gravada**: o sistema a gera pelas ligações (\"Desligado\" sem nada). "
              "Porta **sem nada ligado** só fica `down` ou `desativada` e em branco (outro status: `409 porta_sem_ligacao`; o resto do corpo, menos a "
              "observação, é ignorado). Porta com algo ligado fica `up` (outro status: `409 porta_com_equipamento`). **Porta de patch panel** não tem parte "
              "lógica: só a observação. Combinação que o modo não aceita: 400. É o **cadastro** da configuração: o SGI não fala com o switch.",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def configurar_porta(porta_id: uuid.UUID, corpo: GravacaoPorta, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        p = servico.alterar_porta(sessao, porta_id, _dados_porta(corpo))
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.configurar", [p.id])
        sessao.commit()
    return _porta_detalhe(sessao, usuario, p)


@roteador.post("/portas/{porta_id}/conexao", response_model=PortaDetalhe, status_code=status.HTTP_201_CREATED, summary="Ligar a porta",
               description="Liga a porta a outra porta, a um bem do Patrimônio ou a uma descrição. Porta de **patch panel** tem dois lados (`lado`: "
                           "`fundo` ou `frente`), cada um com uma ligação; nas demais, `lado` não existe (400). Na outra ponta vale o mesmo (`outro_lado`). "
                           "Porta ou lado já ligado: `409 porta_ocupada`. As pontas passam a \"ligada\" (`up`) e a descrição de cada uma é gerada pelo sistema.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def ligar(porta_id: uuid.UUID, corpo: GravacaoConexao, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.conectar(sessao, porta_id, corpo.porta_id, corpo.bem_id, corpo.descricao, corpo.lado, corpo.outro_lado)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ligar", [porta_id, corpo.porta_id])
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


# Sem description= no decorador: não colocar docstring (viraria a descrição no OpenAPI). As pontas
# são lidas antes de desligar para auditar as duas portas.
@roteador.delete("/portas/{porta_id}/conexao", response_model=PortaDetalhe, summary="Desligar a porta",
                 description="Desfaz a ligação da porta (no patch panel, a do `lado` informado) e tira os dispositivos de trás. Não deixa nenhum "
                             "equipamento sem cabo para quem fica acima dele (`409 unica_ligacao_para_cima`: ligue antes outro cabo). A ponta que fica sem nada "
                             "ligado passa a `down` e em branco (descrição \"Desligado\", modo access, sem VLANs, voz, IP, velocidade e duplex); a porta de patch "
                             "panel com o outro lado ainda ligado continua `up`.",
                 responses={**SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Conexão")})
def desligar(porta_id: uuid.UUID, lado: str | None = Query(None, pattern="^(fundo|frente)$", description="Lado da porta de patch panel."),
             usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        pontas = servico.pontas_da_conexao(sessao, porta_id, lado)
        servico.desconectar(sessao, porta_id, lado)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.desligar", pontas)
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.post("/portas/{porta_id}/conexao/trocar", response_model=PortaDetalhe, summary="Trocar a ligação da porta",
               description="Troca o que está ligado na porta (no patch panel, no `lado` informado) por outra porta, bem ou descrição, numa operação "
                           "só: não passa por um momento sem cabo para cima. Com `religar_antigo`, se o novo destino é um lado de patch panel e o antigo "
                           "era outra porta, o outro lado daquela porta do patch panel é ligado no destino antigo (pôr um patch panel no meio do cabo). "
                           "Se alguém ficar sem cabo para cima depois da troca: `409 unica_ligacao_para_cima` e nada muda. Sem ligação: 404.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Ligação")})
def trocar(porta_id: uuid.UUID, corpo: TrocaConexao, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        antigas = servico.pontas_da_conexao(sessao, porta_id, corpo.lado)
        servico.trocar_ligacao(sessao, porta_id, corpo.lado, corpo.porta_id, corpo.bem_id, corpo.descricao, corpo.outro_lado, corpo.religar_antigo)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ligar", [*antigas, corpo.porta_id])
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.post("/portas/{porta_id}/conexao/atras", response_model=PortaDetalhe, status_code=status.HTTP_201_CREATED, summary="Pôr um dispositivo atrás",
               description="Mais de um dispositivo na mesma porta, em cascata (switch → telefone IP → PC): entra atrás do último. A porta precisa ter um "
               "primeiro dispositivo (bem ou descrição): `409 sem_dispositivo`. Mesmo bem duas vezes na porta: `409 duplicado`. No patch panel, informe o `lado`.",
               responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Porta")})
def adicionar_atras(porta_id: uuid.UUID, corpo: GravacaoDispositivoAtras, usuario: Usuario = Depends(_exigir("editar")),
                    sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.adicionar_atras(sessao, porta_id, corpo.bem_id, corpo.descricao, corpo.lado)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.atras", [porta_id])
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


@roteador.delete("/portas/{porta_id}/conexao/atras/{dispositivo_id}", response_model=PortaDetalhe, summary="Tirar um dispositivo de trás",
                 description="Os que vinham depois sobem uma posição.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Dispositivo")})
def remover_atras(porta_id: uuid.UUID, dispositivo_id: uuid.UUID, usuario: Usuario = Depends(_exigir("editar")),
                  sessao: Session = Depends(obter_sessao)) -> PortaDetalhe:
    with _traduzir(sessao):
        servico.remover_atras(sessao, porta_id, dispositivo_id)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.atras", [porta_id])
        sessao.commit()
        return _porta_detalhe(sessao, usuario, servico.obter_porta(sessao, porta_id))


# ---------------------------------------------------------------------------------------------
# Modelos de face e VLANs
# ---------------------------------------------------------------------------------------------

# Rotas de modelos de face (sem description= em algumas: comentários com # para não alterar o
# OpenAPI).
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
              description="Nome, fabricante e altura mudam sempre. A grade (linhas, colunas, numeração) e as portas extras só mudam se nenhum equipamento "
                          "usa o modelo; em uso: `409 modelo_em_uso` (crie outro modelo).",
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
    """
    Converte uma VLAN para a resposta, contando quantas portas a usam (como nativa, de
    voz ou na lista de VLANs da porta).
    """
    portas = (sessao.scalar(select(func.count()).select_from(PortaRede).where((PortaRede.vlan_nativa_id == v.id) | (PortaRede.vlan_voz_id == v.id))) or 0) + \
             (sessao.scalar(select(func.count()).select_from(PortaVlanRede).where(PortaVlanRede.vlan_id == v.id)) or 0)
    return VlanLeitura(id=v.id, numero=v.numero, nome=v.nome, descricao=v.descricao, cor_indice=v.cor_indice, portas=portas)


@roteador.get("/vlans", response_model=list[VlanLeitura], summary="VLANs", responses=SEM_ACESSO)
def vlans(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[VlanLeitura]:
    return [_vlan(sessao, v) for v in servico.listar_vlans(sessao)]


@roteador.post("/vlans", response_model=VlanLeitura, status_code=status.HTTP_201_CREATED, summary="Criar VLAN", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_vlan(corpo: GravacaoVlan, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> VlanLeitura:
    with _traduzir(sessao):
        v = servico.salvar_vlan(sessao, None, corpo.numero, corpo.nome, corpo.descricao, corpo.cor_indice)
        sessao.commit()
    return _vlan(sessao, v)


@roteador.put("/vlans/{vlan_id}", response_model=VlanLeitura, summary="Alterar VLAN", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("VLAN")})
def alterar_vlan(vlan_id: uuid.UUID, corpo: GravacaoVlan, _: Usuario = Depends(_exigir("administrar")), sessao: Session = Depends(obter_sessao)) -> VlanLeitura:
    with _traduzir(sessao):
        v = servico.salvar_vlan(sessao, vlan_id, corpo.numero, corpo.nome, corpo.descricao, corpo.cor_indice)
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
def criar_ponto(corpo: GravacaoPonto, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PontoLeitura:
    with _traduzir(sessao):
        pt = servico.salvar_ponto(sessao, None, corpo.codigo, corpo.localizacao_id, corpo.porta_id, corpo.observacao)
        # O ponto aparece na porta: ligar o ponto a uma porta é uma alteração dela
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ponto", [pt.porta_id])
        sessao.commit()
    return _ponto(sessao, pt, _salas(sessao, [pt.localizacao_id]))


# Guarda a porta anterior do ponto antes de salvar, para auditar tanto a porta que perdeu quanto a
# que ganhou o ponto.
@roteador.put("/pontos/{ponto_id}", response_model=PontoLeitura, summary="Alterar ponto de rede",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Ponto de rede")})
def alterar_ponto(ponto_id: uuid.UUID, corpo: GravacaoPonto, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> PontoLeitura:
    with _traduzir(sessao):
        anterior = sessao.scalar(select(PontoRede.porta_id).where(PontoRede.id == ponto_id))
        pt = servico.salvar_ponto(sessao, ponto_id, corpo.codigo, corpo.localizacao_id, corpo.porta_id, corpo.observacao)
        # A porta que perdeu e a que ganhou o ponto mudaram (ou a mesma, se mudou o código)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ponto", [anterior, pt.porta_id])
        sessao.commit()
    return _ponto(sessao, pt, _salas(sessao, [pt.localizacao_id]))


@roteador.delete("/pontos/{ponto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir ponto de rede",
                 description="Os chamados que apontavam o ponto ficam sem ele.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Ponto de rede")})
def excluir_ponto(ponto_id: uuid.UUID, usuario: Usuario = Depends(_exigir("editar")), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        anterior = sessao.scalar(select(PontoRede.porta_id).where(PontoRede.id == ponto_id))
        servico.excluir_ponto(sessao, ponto_id)
        servico.auditar_portas(sessao, usuario.login, usuario.id, "rede.porta.ponto", [anterior])
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
            # atras_de: o primeiro dispositivo da conexão, quando o bem está em cascata atrás dele
            # (ex.: PC atrás de um telefone IP).
            primeiro_texto = ""
            if dispositivo is not None:
                primeiro = sessao.get(Bem, conexao.bem_id) if conexao.bem_id else None
                primeiro_texto = _texto_bem(primeiro) if primeiro else conexao.descricao
            resultado.append(PortaDoBem(porta_id=p.id, porta_nome=p.nome or str(p.numero_logico), equipamento_id=p.equipamento_id,
                                        equipamento_nome=p.equipamento.nome, lado=conexao.lado_a, atras_de=primeiro_texto,
                                        dispositivo_id=dispositivo.id if dispositivo else None))
        return resultado


# ---------------------------------------------------------------------------------------------
# Racks
# ---------------------------------------------------------------------------------------------

def _rack(sessao: Session, r: RackRede, salas: dict) -> RackLeitura:
    """
    Converte um rack para a resposta, com a sala e o total de equipamentos montados
    nele.
    """
    total = sessao.scalar(select(func.count()).select_from(EquipamentoRede).where(EquipamentoRede.rack_id == r.id)) or 0
    return RackLeitura(id=r.id, nome=r.nome, cor=r.cor, localizacao_id=r.localizacao_id, altura_u=r.altura_u, observacao=r.observacao,
                       sala=salas.get(r.localizacao_id, ""), equipamentos=total)


@roteador.get("/racks", response_model=list[RackLeitura], summary="Racks", responses=SEM_ACESSO,
              description="Os racks (nome, cor, sala do Patrimônio e altura em U), com quantos equipamentos têm.")
def racks(_: Usuario = Depends(_exigir("ver")), sessao: Session = Depends(obter_sessao)) -> list[RackLeitura]:
    itens = servico.listar_racks(sessao)
    salas = _salas(sessao, [r.localizacao_id for r in itens])
    return [_rack(sessao, r, salas) for r in itens]


# Rotas de racks: só a administração da rede grava; ver basta para listar.
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
