# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor o tempo real dos Chamados, o painel do setor e os Parâmetros do painel e do RH.
"""Rotas do marco 4 dos Chamados (`/api/chamados/...`).

- `GET /chamados/eventos`: fluxo ao vivo (SSE) para quem está logado (fila, meus chamados, detalhe, painel);
- `GET /chamados/painel`: painel de quem está logado (os chamados em que o setor dela, ou um de baixo, é o responsável);
- `/chamados/parametros/painel` e `/parametros/rh`: Parâmetros (só quem administra).

O painel é **sempre com login** (decisão do usuário): a TV da sala fica logada com a conta de alguém do setor.

Este roteador é registrado **antes** do principal dos Chamados, para `/painel` e `/eventos` não serem lidos como número de chamado.
Detalhes em `docs/endpoints/chamados.md` (seção "Marco 4") e `docs/painel-tv-chamados.md`.
"""

from datetime import UTC

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.dependencias import esquema_bearer, obter_usuario_autenticado
from app.api.respostas import INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.api.routes.chamados import SEM_ACESSO, _Montador, _traduzir, administrador, papeis_do_usuario
from app.core.banco import FabricaSessao, agora_utc, obter_sessao
from app.core.erros import ErroApi
from app.models.chamados import STATUS_PENDENTE
from app.models.patrimonio import Localizacao
from app.models.usuario import Usuario
from app.schemas.chamados import (
    ConfigPainel, EstadoPainel, GravacaoParametrosRh, IndicadoresPainel, ItemPainel, ParametrosRh, ServicoRhLeitura,
)
from app.schemas.comum import RespostaErro
from app.schemas.rh_admissao import SOLICITACOES
from app.services import servico_perfil
from app.services.chamados import acesso, painel, rh, tempo_real
from app.services.chamados.acesso import Alcance, Papeis
from app.services.servico_auditoria import auditar

roteador = APIRouter(prefix="/chamados", tags=["Chamados"], responses=VALIDACAO)

FLUXO_SSE = {200: {"content": {"text/event-stream": {}}, "description": "Fluxo `text/event-stream`: `event: chamado` com `{\"tipo\": \"novo\"|\"alterado\", \"numero\"}`, "
                                                                     "mais um comentário `: ping` a cada 20 s. Dura até 30 min; a tela reconecta sozinha."}}
# Ordem de gravidade das cores (o painel pinta a linha com a pior das duas). "Sem prazo" e "no prazo" são o mesmo grupo: a linha branca
_GRAVIDADE = {"sem": 0, "cumprido": 0, "ok": 0, "alerta": 2, "atencao": 3, "perigo": 4}
# Cabeçalhos do fluxo: sem cache e sem o buffer do Nginx (senão o evento só chegaria no fim)
_CABECALHOS_SSE = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


# ---------------------------------------------------------------------------------------------
# Montagem do painel
# ---------------------------------------------------------------------------------------------

def _estado(sessao: Session, setores: set[int] | None, area: str) -> EstadoPainel:
    """Painel de um conjunto de setores. A TV é tela pública: título sigiloso sempre oculto, mesmo no painel de quem atende."""
    montador = _Montador(sessao, None, Papeis(False, False, False), Alcance(0, False, frozenset(), frozenset()))  # type: ignore[arg-type]
    itens_db = painel.chamados(sessao, setores)
    montador.carregar_nomes({i for c in itens_db for i in (c.responsavel_id, c.solicitante_id)})
    locais = {x.id: x.nome for x in sessao.query(Localizacao).filter(Localizacao.id.in_({c.localizacao_id for c in itens_db if c.localizacao_id}))}
    itens: list[tuple[tuple, ItemPainel]] = []
    for c in itens_db:
        r = montador.resumo(c)
        prazos = [p for p in (r["atendimento"], r["solucao"]) if p.nivel not in ("sem", "cumprido")]
        pior = max(prazos, key=lambda p: (_GRAVIDADE[p.nivel], p.percentual or 0), default=None)
        nivel = pior.nivel if pior else "sem"
        item = ItemPainel(
            numero=c.numero, titulo=r["titulo"], solicitante=painel.primeiros_nomes(r["solicitante_nome"]), responsavel=painel.primeiros_nomes(r["responsavel_nome"]),
            local=locais.get(c.localizacao_id, ""), setor_nome=c.setor_nome, aberto_em=c.aberto_em, solucionado_em=c.solucionado_em, status_base=c.status_base,
            status_nome=r["status_nome"], prioridade=c.prioridade, nivel=nivel, percentual=pior.percentual if pior else None,
            estourado=bool(pior and pior.estourado), pausado=c.status_base == STATUS_PENDENTE,
        )
        aberto = c.aberto_em if c.aberto_em.tzinfo else c.aberto_em.replace(tzinfo=UTC)
        # Sempre pela cor (decisão do usuário): todos os vermelhos, depois os laranjas, os amarelos e os brancos;
        # dentro da mesma cor, quem gastou mais do prazo e, empatando, o mais antigo
        itens.append(((-_GRAVIDADE.get(nivel, 0), -(item.percentual or 0), aberto), item))
    itens.sort(key=lambda x: x[0])
    limites = montador.limites
    return EstadoPainel(area=area, gerado_em=agora_utc(), config=ConfigPainel(**painel.config(sessao)), indicadores=IndicadoresPainel(**painel.indicadores(sessao, setores)),
                        limites={"alerta": limites.limite_alerta, "atencao": limites.limite_atencao, "perigo": limites.limite_perigo},
                        itens=[i for _, i in itens])


def _resposta_sse(gerador) -> StreamingResponse:
    return StreamingResponse(gerador, media_type="text/event-stream", headers=_CABECALHOS_SSE)


# ---------------------------------------------------------------------------------------------
# Quem está logado
# ---------------------------------------------------------------------------------------------

@roteador.get("/eventos", summary="Eventos ao vivo", response_class=StreamingResponse, responses={**FLUXO_SSE, **SEM_ACESSO},
              description="Fluxo SSE com cada chamado novo ou alterado **que a pessoa enxerga** (como solicitante, setor solicitante, responsável, "
              "pelos setores que atende ou pelos setores do painel). Só leva `tipo` e `numero`: a tela busca o resto pela rota normal. "
              "Como o `EventSource` do navegador não manda o cabeçalho `Authorization`, o frontend lê o fluxo com `fetch`.")
async def eventos(pedido: Request, credenciais: HTTPAuthorizationCredentials | None = Depends(esquema_bearer)) -> StreamingResponse:
    # A sessão do banco só vive durante a autorização: o fluxo pode durar 30 min e não pode prender uma conexão do pool
    with FabricaSessao() as sessao:
        usuario = obter_usuario_autenticado(Response(), credenciais, sessao)
        if servico_perfil.perfil_restrito(usuario):
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Atualize seu cadastro para continuar usando o sistema.", "revisao_perfil_obrigatoria")
        p = acesso.papeis(sessao, usuario)
        if not p.algum:
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Você não tem acesso ao módulo Chamados.", "acl_negado", recurso=acesso.RECURSO_ACL)
        a = acesso.alcance(sessao, usuario, p)
        do_painel = frozenset(acesso._descendentes(sessao, set(a.setores_membro)))

    def filtro(e: tempo_real.Evento) -> bool:
        # O setor de antes também recebe a transferência: o chamado sai do painel dele na hora
        setores = {e.setor_id, e.setor_anterior_id} - {None}
        return (a.todos or a.usuario_id in (e.solicitante_id, e.responsavel_id) or bool(setores & (set(a.setores_atendidos) | do_painel))
                or (e.setor_solicitante_id is not None and e.setor_solicitante_id in a.setores_membro))

    return _resposta_sse(tempo_real.fluxo(filtro, pedido.is_disconnected))


@roteador.get("/painel", response_model=EstadoPainel, summary="Painel do meu setor",
              description="Painel de quem está logado: os chamados em que o **setor responsável** é um setor de que a pessoa é membro (ou um setor abaixo dele). "
              "Nada fixo: cada pessoa vê o do seu setor. `setor_id` escolhe um desses setores; quem administra pode escolher qualquer um ou, sem `setor_id`, ver todos. "
              "Traz também a configuração de exibição (`config`).",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Setor")})
def painel_logado(setor_id: int | None = Query(None, description="Setor mostrado (ele e os de baixo)."),
                  contexto: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> EstadoPainel:
    usuario, p = contexto
    with _traduzir(sessao):
        setores, area = painel.escopo_da_pessoa(sessao, usuario, p, setor_id)
    return _estado(sessao, setores, area)


# ---------------------------------------------------------------------------------------------
# Parâmetros: exibição do painel
# ---------------------------------------------------------------------------------------------

@roteador.get("/parametros/painel", response_model=ConfigPainel, summary="Exibição do painel", responses=SEM_ACESSO,
              description="Como o painel aparece para todos: linhas por página (0 = quantas couberem na tela), tamanho do texto, tempo de cada página, "
              "voz, cor na linha inteira e as colunas mostradas. As cores do prazo (50/75/90%) ficam na aba Geral.")
def config_painel(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ConfigPainel:
    return ConfigPainel(**painel.config(sessao))


@roteador.put("/parametros/painel", response_model=ConfigPainel, summary="Alterar exibição do painel", responses={**INVALIDO, **SEM_ACESSO})
def gravar_config_painel(corpo: ConfigPainel, usuario: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ConfigPainel:
    with _traduzir(sessao):
        painel.gravar_config(sessao, corpo.model_dump())
        auditar(sessao, usuario.login, "chamados.painel.config", "exibição do painel", autor_id=usuario.id)
        sessao.commit()
    return ConfigPainel(**painel.config(sessao))


# ---------------------------------------------------------------------------------------------
# Parâmetros: RH
# ---------------------------------------------------------------------------------------------

def _servicos_rh(sessao: Session, fluxo: str, rotulos: dict[str, str]) -> list[ServicoRhLeitura]:
    from app.models.setor import Setor

    mapa = rh.servicos(sessao, fluxo)
    nomes = {s.id: s.nome for s in sessao.query(Setor).filter(Setor.id.in_({m.setor_id for m in mapa.values() if m.setor_id}))} if mapa else {}
    resultado = []
    for chave, rotulo in rotulos.items():
        s = mapa.get(chave)
        resultado.append(ServicoRhLeitura(servico=chave, rotulo=rotulo, setor_id=s.setor_id if s else None, setor_nome=nomes.get(s.setor_id, "") if s else "",
                                          prioridade=s.prioridade if s else "normal", sla_tto_id=s.sla_tto_id if s else None, sla_ttr_id=s.sla_ttr_id if s else None))
    return resultado


def _parametros_rh(sessao: Session) -> ParametrosRh:
    return ParametrosRh(destino=rh.destino_configurado(sessao), destino_atual=rh.destino(sessao), servicos=_servicos_rh(sessao, rh.FLUXO_NOMEACAO, SOLICITACOES),
                        servicos_exoneracao=_servicos_rh(sessao, rh.FLUXO_EXONERACAO, rh.SERVICOS_EXONERACAO))


@roteador.get("/parametros/rh", response_model=ParametrosRh, summary="Chamados do RH", responses=SEM_ACESSO,
              description="Para onde vão os chamados do RH (`glpi` hoje, `chamados` depois da virada, `na_data` para virar sozinho na data \"a partir de\"; "
              "`destino_atual` diz para onde vai agora) e, para cada serviço da Nomeação e da Exoneração, a fila "
              "(setor que atende), a prioridade e os prazos.")
def parametros_rh(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ParametrosRh:
    return _parametros_rh(sessao)


@roteador.put("/parametros/rh", response_model=ParametrosRh, summary="Alterar chamados do RH",
              description="Grava a fila, a prioridade e os prazos de cada serviço (Nomeação e Exoneração) e o destino. Para ligar `chamados` ou `na_data`, todo serviço dos dois "
              "fluxos precisa de fila (409 `servico_sem_fila`); `na_data` sem a data \"a partir de\" marcada: 400. Os chamados nascem nos assuntos fixos \"Nomeação (RH)\" e \"Exoneração (RH)\" (fora de uso para quem "
              "abre). A troca vale na hora para o próximo envio do RH; o que já foi enviado ao GLPI continua lá.",
              responses={**INVALIDO, **SEM_ACESSO, status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Serviço sem fila (`servico_sem_fila`)."}})
def gravar_parametros_rh(corpo: GravacaoParametrosRh, usuario: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ParametrosRh:
    with _traduzir(sessao):
        para = lambda d: {k: rh.ConfigServico(v.setor_id, v.prioridade, v.sla_tto_id, v.sla_ttr_id) for k, v in d.items()}
        rh.gravar(sessao, corpo.destino, {rh.FLUXO_NOMEACAO: para(corpo.servicos), rh.FLUXO_EXONERACAO: para(corpo.servicos_exoneracao)},
                  {rh.FLUXO_NOMEACAO: SOLICITACOES, rh.FLUXO_EXONERACAO: rh.SERVICOS_EXONERACAO})
        auditar(sessao, usuario.login, "chamados.rh.destino", corpo.destino, autor_id=usuario.id)
        sessao.commit()
    return _parametros_rh(sessao)
