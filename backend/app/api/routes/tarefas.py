# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Módulo Tarefas (tarefas, pipeline, linha do tempo, equipes e marcadores).
"""Rotas `/api/tarefas`. Todas exigem login; as permissões por tarefa e equipe ficam em `servico_tarefas`."""

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import agora_utc, hoje_sao_paulo, obter_sessao
from app.core.erros import ErroApi
from app.models.anexo import Anexo
from app.models.tarefas import AnexoEventoTarefa, AtividadeTarefa, AtualizacaoStatusEquipe, MarcoTarefa, DependenciaTarefa, EquipeTarefas, EstagioTarefa, EventoTarefa, MarcadorTarefa, RecorrenciaTarefa, Tarefa
from app.models.usuario import Usuario
from app.schemas.tarefas import (
    AnexoLeitura, Contexto, EdicaoTarefa, EquipeLeitura, EquipeResumo, Etapa, EventoLeitura, GravacaoEquipe, GravacaoMarcador,
    Indicadores, ItemChecklist, LinhaDoTempo, ListaTarefas, MarcadorLeitura, Movimento, MudancaPrazo, NovaTarefa, OperacaoChecklist,
    AgendaPessoa, AtividadeLeitura, AtualizacaoStatusLeitura, ConclusaoAtividade, GravacaoMarco, GravacaoStatusEquipe, MarcoDaTarefa, MarcoLeitura, ContagemEquipe, DesempenhoEquipe, Dependencias, GravacaoAtividade, EstagioLeitura, GravacaoEstagios, MudancaEstagio, GravacaoRecorrencia, NovaSubtarefa, TarefaLigada, ItemAgenda, Pessoa, PessoaCarga, PreviaRecorrencia, RecorrenciaLeitura, RecorrenciaResumo,
    RegraRecorrenciaEntrada, RemocaoEvento, Reordenacao, RespostaPreviaRecorrencia, ResumoSincronizacaoContratos, TarefaDetalhe, TarefaResumo, Transferencia,
)
from app.services import servico_anexos
from app.services.sla import servico_sla
from app.services.tarefas import desempenho_tarefas, memorial_tarefa, paleta, relatorio_tarefas, servico_atividades, servico_estagios, servico_marcos, servico_recorrencias, servico_subtarefas
from app.services.tarefas import servico_tarefas as servico
from app.services.tarefas.servico_tarefas import ROTULOS_STATUS, ErroTarefa

roteador = APIRouter(prefix="/tarefas", tags=["Módulo Tarefas"], responses=RESPOSTAS_AUTENTICADAS)
SEM_PERMISSAO = {status.HTTP_403_FORBIDDEN: {"description": "Sem permissão nesta tarefa ou equipe (`sem_permissao`)."}}
NAO_ENCONTRADA = resposta_nao_encontrado("Tarefa")
# Filtros da linha do tempo (chips da tela) → tipos de evento
FILTROS_LINHA = {
    "comentarios": ("comentario",),
    "status": ("status", "entregue", "validada", "devolvida", "reaberta"),
    "prazos": ("prazo",),
    "atribuicoes": ("criada", "transferida", "editada"),
}


@contextmanager
def _traduzir():
    try:
        yield
    except ErroTarefa as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _pessoa(sessao: Session, usuario_id: int | None) -> Pessoa | None:
    u = sessao.get(Usuario, usuario_id) if usuario_id else None
    return Pessoa(id=u.id, nome=u.nome_completo or u.login, login=u.login) if u else None


def _prorrogacoes(sessao: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    linhas = sessao.execute(select(EventoTarefa.tarefa_id, func.count()).where(EventoTarefa.tarefa_id.in_(ids), EventoTarefa.tipo == "prazo")
                            .group_by(EventoTarefa.tarefa_id))
    return dict(linhas.all())


def _contagens(sessao: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    """Por tarefa: prorrogações, comentários e anexos (três consultas agregadas para a lista inteira, sem N+1).

    Eventos removidos pelo SuperRoot não contam nos comentários nem nos anexos.
    """
    resultado: dict[uuid.UUID, dict[str, int]] = {
        i: {"prorrogacoes": 0, "comentarios": 0, "anexos": 0, "subtarefas_total": 0, "subtarefas_concluidas": 0, "bloqueada": 0} for i in ids}
    if not ids:
        return resultado
    for tarefa_id, total in _prorrogacoes(sessao, ids).items():
        resultado[tarefa_id]["prorrogacoes"] = total
    comentarios = sessao.execute(
        select(EventoTarefa.tarefa_id, func.count()).where(
            EventoTarefa.tarefa_id.in_(ids), EventoTarefa.tipo == "comentario", EventoTarefa.removido_em.is_(None)
        ).group_by(EventoTarefa.tarefa_id)
    )
    for tarefa_id, total in comentarios:
        resultado[tarefa_id]["comentarios"] = total
    anexos = sessao.execute(
        select(EventoTarefa.tarefa_id, func.count(AnexoEventoTarefa.id)).join(AnexoEventoTarefa, AnexoEventoTarefa.evento_id == EventoTarefa.id)
        .where(EventoTarefa.tarefa_id.in_(ids), EventoTarefa.removido_em.is_(None)).group_by(EventoTarefa.tarefa_id)
    )
    for tarefa_id, total in anexos:
        resultado[tarefa_id]["anexos"] = total
    # Subtarefas (total e concluídas) e tarefas bloqueadas por alguma ainda aberta
    for mae_id, status_sub, total in sessao.execute(select(Tarefa.tarefa_pai_id, Tarefa.status, func.count()).where(Tarefa.tarefa_pai_id.in_(ids)).group_by(Tarefa.tarefa_pai_id, Tarefa.status)):
        resultado[mae_id]["subtarefas_total"] += total
        if status_sub == "concluida":
            resultado[mae_id]["subtarefas_concluidas"] += total
    bloqueadora = aliased(Tarefa)
    for tarefa_id in sessao.scalars(select(DependenciaTarefa.tarefa_id).join(bloqueadora, bloqueadora.id == DependenciaTarefa.bloqueada_por_id)
                                    .where(DependenciaTarefa.tarefa_id.in_(ids), bloqueadora.status != "concluida").distinct()):
        resultado[tarefa_id]["bloqueada"] = 1
    return resultado


def _envolvidos(sessao: Session, t: Tarefa) -> list[Pessoa]:
    """Responsável principal primeiro e depois os demais responsáveis (em ordem de nome), para os avatares do cartão."""
    outros = [p for p in (_pessoa(sessao, i) for i in servico.envolvidos(t) if i != t.responsavel_id) if p]
    responsavel = _pessoa(sessao, t.responsavel_id)
    return ([responsavel] if responsavel else []) + sorted(outros, key=lambda p: p.nome.lower())


def _utc(valor: datetime | None) -> datetime | None:
    """Datas sempre com fuso (o SQLite dos testes devolve sem)."""
    return servico._comparavel(valor) if valor else None


def _numeros_das_maes(sessao: Session, tarefas: list[Tarefa]) -> dict[uuid.UUID, int]:
    """Número da tarefa mãe de cada subtarefa da lista (uma consulta só)."""
    ids = {t.tarefa_pai_id for t in tarefas if t.tarefa_pai_id}
    return dict(sessao.execute(select(Tarefa.id, Tarefa.numero).where(Tarefa.id.in_(ids))).all()) if ids else {}


def _padroes_de_estagio(sessao: Session, tarefas: list[Tarefa]) -> dict[tuple, uuid.UUID]:
    """Primeiro estágio de cada categoria das equipes das tarefas (a coluna de quem ainda não tem estágio próprio)."""
    equipes = {t.equipe_id for t in tarefas if t.equipe_id}
    if not equipes:
        return {}
    padroes: dict[tuple, uuid.UUID] = {}
    for e in sessao.scalars(select(EstagioTarefa).where(EstagioTarefa.equipe_id.in_(equipes)).order_by(EstagioTarefa.posicao)):
        padroes.setdefault((e.equipe_id, e.categoria), e.id)
    return padroes


def _resumo(sessao: Session, t: Tarefa, contagens: dict, agora: datetime, pais: dict | None = None, padroes: dict | None = None) -> dict:
    """Campos do `TarefaResumo`. `contagens` vem de `_contagens` (prorrogações, comentários e anexos por tarefa)."""
    numeros = contagens.get(t.id, {})
    return {
        "id": t.id, "numero": t.numero, "titulo": t.titulo, "status": t.status, "prioridade": t.prioridade, "prazo": _utc(t.prazo),
        "prazo_original": _utc(t.prazo_original), "prorrogacoes": numeros.get("prorrogacoes", 0),
        "atrasada": t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora, "dias_em_aberto": servico.dias_em_aberto(t, agora),
        "equipe": EquipeResumo(id=t.equipe.id, nome=t.equipe.nome) if t.equipe else None, "responsavel": _pessoa(sessao, t.responsavel_id),
        "responsaveis": _envolvidos(sessao, t),
        "marcadores": [MarcadorLeitura.model_validate(m, from_attributes=True) for m in t.marcadores],
        "checklist_feitos": sum(1 for i in t.checklist if i.concluido_em), "checklist_total": len(t.checklist),
        "comentarios": numeros.get("comentarios", 0), "anexos": numeros.get("anexos", 0),
        "carga": round(servico.carga(t, agora), 1), "ordem": t.ordem, "criado_em": _utc(t.criado_em), "iniciada_em": _utc(t.iniciada_em),
        "concluida_em": _utc(t.concluida_em), "atualizado_em": _utc(t.atualizado_em),
        "tarefa_pai_numero": (pais or {}).get(t.tarefa_pai_id), "subtarefas_total": numeros.get("subtarefas_total", 0),
        "subtarefas_concluidas": numeros.get("subtarefas_concluidas", 0), "bloqueada": bool(numeros.get("bloqueada", 0)),
        "estagio_id": t.estagio_id or (padroes or {}).get((t.equipe_id, t.status)), "marco_id": t.marco_id,
        "origem_tipo": t.origem_tipo, "controlada_externamente": bool(t.controlada_externamente), "sla": servico_sla.da_tarefa(sessao, t),
    }


def _etapas(sessao: Session, t: Tarefa) -> list[Etapa]:
    """Linha de etapas do pipeline: quando (pela última vez) a tarefa chegou a cada etapa e quem a levou."""
    chegada: dict[str, tuple[datetime, str]] = {"a_fazer": (t.criado_em, "")}
    for e in sessao.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == t.id, EventoTarefa.removido_em.is_(None)).order_by(EventoTarefa.criado_em)):
        if e.tipo == "criada":
            chegada["a_fazer"] = (e.criado_em, e.autor_nome)
        para = (e.dados or {}).get("para")
        if para in ROTULOS_STATUS and e.tipo in ("status", "entregue", "validada", "devolvida", "reaberta"):
            chegada[para] = (e.criado_em, e.autor_nome)
    ordem = list(ROTULOS_STATUS)
    atual = ordem.index(t.status)
    return [
        Etapa(status=s, rotulo=ROTULOS_STATUS[s], em=_utc(chegada[s][0]) if s in chegada and i <= atual else None,
              por=chegada[s][1] if s in chegada and i <= atual else None, atual=i == atual,
              # Etapa pulada (ex.: concluída sem passar pela validação) não conta como alcançada
              alcancada=i == atual or (i < atual and s in chegada))
        for i, s in enumerate(ordem)
    ]


def _ligada(sessao: Session, t: Tarefa) -> TarefaLigada:
    return TarefaLigada(numero=t.numero, titulo=t.titulo, status=t.status, prazo=_utc(t.prazo), responsavel=_pessoa(sessao, t.responsavel_id))


def _seguidores(sessao: Session, usuario: Usuario, t: Tarefa) -> dict:
    ids = servico.seguidores(sessao, t)
    return {"seguindo": usuario.id in ids, "seguidores": [p for p in (_pessoa(sessao, i) for i in sorted(ids)) if p]}


def _ligadas(sessao: Session, usuario: Usuario, t: Tarefa) -> dict:
    """Mãe, subtarefas e dependências da tarefa para o detalhe."""
    mae = sessao.get(Tarefa, t.tarefa_pai_id) if t.tarefa_pai_id else None
    subtarefas = list(sessao.scalars(select(Tarefa).where(Tarefa.tarefa_pai_id == t.id).order_by(Tarefa.numero)))
    bloqueadoras = list(sessao.scalars(select(Tarefa).join(DependenciaTarefa, DependenciaTarefa.bloqueada_por_id == Tarefa.id)
                                       .where(DependenciaTarefa.tarefa_id == t.id).order_by(Tarefa.numero)))
    bloqueadas = list(sessao.scalars(select(Tarefa).join(DependenciaTarefa, DependenciaTarefa.tarefa_id == Tarefa.id)
                                     .where(DependenciaTarefa.bloqueada_por_id == t.id).order_by(Tarefa.numero)))
    return {
        "tarefa_pai": _ligada(sessao, mae) if mae else None, "subtarefas": [_ligada(sessao, x) for x in subtarefas],
        "bloqueada_por": [_ligada(sessao, x) for x in bloqueadoras], "bloqueia": [_ligada(sessao, x) for x in bloqueadas],
        "pode_criar_subtarefa": (t.tarefa_pai_id is None and t.status != "concluida" and not t.controlada_externamente
                                 and servico.pode_editar(sessao, usuario, t)),
    }


def _resumo_recorrencia(sessao: Session, t: Tarefa) -> RecorrenciaResumo | None:
    rec = sessao.get(RecorrenciaTarefa, t.recorrencia_id) if t.recorrencia_id else None
    if rec is None:
        return None
    return RecorrenciaResumo(id=rec.id, resumo=servico_recorrencias.descrever(servico_recorrencias.regra_da_serie(rec), rec.inicio), ativa=rec.ativa,
                             proxima_data=rec.proxima_data, ocorrencia_em=t.ocorrencia_em)


def _origem(sessao: Session, t: Tarefa) -> dict:
    """Link e rótulo da origem (competência de contrato), quando a tarefa nasceu de outro módulo."""
    if t.origem_tipo != "contrato_competencia" or t.origem_id is None:
        return {}
    from app.models.contratos.execucao import Competencia

    competencia = sessao.get(Competencia, t.origem_id)
    if competencia is None:
        return {}
    return {"origem_link": f"/contratos/{competencia.contrato_id}/execucao/{competencia.identificador}",
            "origem_rotulo": f"Contrato {competencia.contrato.numero} · {competencia.numero_competencia}"}


def _detalhe(sessao: Session, usuario: Usuario, t: Tarefa) -> TarefaDetalhe:
    agora = agora_utc()
    base = _resumo(sessao, t, _contagens(sessao, [t.id]), agora, _numeros_das_maes(sessao, [t]), _padroes_de_estagio(sessao, [t]))
    em_andamento = t.segundos_em_andamento + (int((agora - servico._comparavel(t.em_andamento_desde)).total_seconds()) if t.em_andamento_desde else 0)
    return TarefaDetalhe(
        **base, descricao=t.descricao, usuario_lidera=servico.eh_lider(sessao, usuario, t), recorrencia=_resumo_recorrencia(sessao, t), **_ligadas(sessao, usuario, t), **_seguidores(sessao, usuario, t), criado_por=_pessoa(sessao, t.criado_por_id),
        checklist=[ItemChecklist(id=i.id, texto=i.texto, concluido=i.concluido_em is not None) for i in t.checklist],
        etapas=_etapas(sessao, t), segundos_em_andamento=em_andamento, versao=t.versao, acoes=servico.acoes(sessao, usuario, t),
        **_origem(sessao, t),
    )


def _filtrar(tarefas: list[Tarefa], status_: list[str], prioridade: str | None, marcador_id: uuid.UUID | None, busca: str,
             responsavel_id: int | None, origem: str | None = None) -> list[Tarefa]:
    termo = busca.strip().lower()
    resultado = []
    for t in tarefas:
        if status_ and t.status not in status_:
            continue
        if prioridade and t.prioridade != prioridade:
            continue
        if origem == "contratos" and t.origem_tipo != "contrato_competencia":
            continue
        if origem == "manual" and t.origem_tipo is not None:
            continue
        if marcador_id and marcador_id not in {m.id for m in t.marcadores}:
            continue
        if responsavel_id and responsavel_id not in servico.envolvidos(t):
            continue
        if termo and not (termo.lstrip("#").isdigit() and int(termo.lstrip("#")) == t.numero) and termo not in f"{t.titulo} {t.descricao}".lower():
            continue
        resultado.append(t)
    # Ordem manual (arrastar) e, no empate, prazo
    return sorted(resultado, key=lambda t: (t.ordem, servico._comparavel(t.prazo), t.numero))


def _escopo(sessao: Session, usuario: Usuario, escopo: str, equipe_id: uuid.UUID | None, login: str | None,
            agora: datetime, tarefa: int | None = None) -> tuple[list[Tarefa], Contexto, dict]:
    """Tarefas, contexto e indicadores de um escopo (minhas, equipe, pessoa ou subtarefas de uma tarefa), com as permissões conferidas."""
    with _traduzir():
        if escopo == "subtarefas":
            if tarefa is None:
                raise ErroTarefa("Informe a tarefa.")
            mae = servico.obter(sessao, usuario, tarefa)
            tarefas = servico_subtarefas.da_mae(sessao, mae)
            rotulo_equipe = (mae.equipe.nome if mae.equipe.nome.lower().startswith("equipe") else f"Equipe {mae.equipe.nome}") if mae.equipe else "Sem equipe"
            contexto = Contexto(tipo="subtarefas", titulo=f"{rotulo_equipe} - Tarefa {mae.titulo} - Subtarefas", equipe_id=mae.equipe_id, tarefa_numero=mae.numero,
                                tarefa_titulo=mae.titulo, lider=servico.eh_lider(sessao, usuario, mae))
            ind = servico.indicadores(tarefas, agora)
        elif escopo == "equipe":
            if equipe_id is None:
                raise ErroTarefa("Informe a equipe.")
            equipe, tarefas = servico.da_equipe(sessao, usuario, equipe_id)
            lider = usuario.superusuario or usuario.id in servico.lideranca(sessao, equipe)
            contexto = Contexto(tipo="equipe", titulo=equipe.nome if equipe.nome.lower().startswith("equipe") else f"Equipe {equipe.nome}", equipe_id=equipe.id, lider=lider)
            ind = servico.indicadores(tarefas, agora)
        elif escopo == "pessoa":
            pessoa = sessao.scalar(select(Usuario).where(func.lower(Usuario.login) == (login or "").lower()))
            if pessoa is None:
                raise ErroTarefa("Pessoa não encontrada.", 404, "nao_encontrado")
            tarefas = servico.da_pessoa(sessao, usuario, pessoa)
            contexto = Contexto(tipo="pessoa", titulo=f"Tarefas de {pessoa.nome_completo or pessoa.login}", login=pessoa.login,
                                pessoa_id=pessoa.id, lider=usuario.id != pessoa.id)
            ind = servico.indicadores(tarefas, agora, pessoa.id)
        else:
            tarefas = servico.minhas(sessao, usuario)
            contexto = Contexto(tipo="minhas", titulo="Minhas tarefas", pessoa_id=usuario.id, lider=bool(servico.equipes_lideradas(sessao, usuario)))
            ind = servico.indicadores(tarefas, agora, usuario.id)
    return tarefas, contexto, ind


# ---------------------------------------------------------------------------------------------
# Listas
# ---------------------------------------------------------------------------------------------

@roteador.get("", response_model=ListaTarefas, summary="Listar tarefas (minhas, de uma equipe ou de uma pessoa)",
              description="`escopo`: `minhas` (padrão: envolvida ou criada por mim), `equipe` (`equipe_id`; a liderança vê também as equipes "
                          "abaixo), `pessoa` (`login`; a própria pessoa, a liderança das equipes dela ou o SuperRoot) ou `subtarefas` (`tarefa`: as "
                          "subtarefas de uma tarefa-mãe visível ao usuário, com título \"Equipe X - Tarefa Título - Subtarefas\"). Só tarefas-mãe entram em "
                          "`minhas`, `equipe` e `pessoa`: subtarefas têm quadro próprio. Filtros: `status` "
                          "(repetível), `prioridade`, `marcador_id`, `responsavel_id`, `origem` (`contratos` = tarefas das competências de contratos; "
                          "`manual` = as demais) e `busca` (título, descrição ou número). Os indicadores "
                          "são do escopo inteiro (sem os filtros).", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Equipe ou pessoa")})
def listar(escopo: str = Query("minhas", pattern="^(minhas|equipe|pessoa|subtarefas)$"), equipe_id: uuid.UUID | None = None, login: str | None = None,
           tarefa: int | None = Query(None, description="Número da tarefa-mãe (escopo `subtarefas`)."),
           status_: list[str] = Query([], alias="status"), prioridade: str | None = None, marcador_id: uuid.UUID | None = None,
           responsavel_id: int | None = None, busca: str = Query("", max_length=200),
           origem: str | None = Query(None, pattern="^(contratos|manual)$"), sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> ListaTarefas:
    agora = agora_utc()
    tarefas, contexto, ind = _escopo(sessao, usuario, escopo, equipe_id, login, agora, tarefa)
    filtradas = _filtrar(tarefas, status_, prioridade, marcador_id, busca, responsavel_id, origem)
    contagens = _contagens(sessao, [t.id for t in filtradas])
    maes = _numeros_das_maes(sessao, filtradas)
    padroes = _padroes_de_estagio(sessao, filtradas)
    return ListaTarefas(contexto=contexto, indicadores=Indicadores(**ind), itens=[TarefaResumo(**_resumo(sessao, t, contagens, agora, maes, padroes)) for t in filtradas])


@roteador.post("/ordem", status_code=status.HTTP_204_NO_CONTENT, summary="Reordenar tarefas (arrastar)",
               description="Grava a nova ordem manual. Só as tarefas que o usuário pode editar mudam; as demais são ignoradas.")
def reordenar(dados: Reordenacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    servico.reordenar(sessao, usuario, dados.numeros)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/relatorio", summary="Relatório de tarefas (XLSX ou PDF)", response_class=Response,
              description="Tarefas do escopo (`minhas`, `equipe` com `equipe_id` ou `pessoa` com `login`, com as mesmas permissões da lista) "
                          "ativas no período `de`–`ate` (criadas até o fim e abertas ou concluídas a partir do início), opcionalmente de um "
                          "`marcador_id`. XLSX: abas Tarefas e Por pessoa; PDF: resumo, pessoas e lista.",
              responses={200: {"content": {relatorio_tarefas.XLSX: {}, "application/pdf": {}}, "description": "Arquivo gerado."},
                         **SEM_PERMISSAO, **resposta_nao_encontrado("Equipe ou pessoa")})
def relatorio(formato: str = Query("xlsx", pattern="^(xlsx|pdf)$"), escopo: str = Query("minhas", pattern="^(minhas|equipe|pessoa)$"),
              equipe_id: uuid.UUID | None = None, login: str | None = None, marcador_id: uuid.UUID | None = None, de: date | None = None,
              ate: date | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    if de and ate and de > ate:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "O início do período é depois do fim.", "invalido")
    agora = agora_utc()
    tarefas, contexto, _ = _escopo(sessao, usuario, escopo, equipe_id, login, agora)
    if marcador_id:
        tarefas = [t for t in tarefas if marcador_id in {m.id for m in t.marcadores}]
    conteudo, nome, midia = relatorio_tarefas.gerar(sessao, usuario, contexto.titulo, tarefas, _prorrogacoes(sessao, [t.id for t in tarefas]),
                                                    formato, de, ate, agora)
    return Response(conteudo, media_type=midia, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/pessoas", response_model=list[PessoaCarga], summary="Pessoas com a carga atual",
              description="Para o seletor de responsável e a visão da liderança: com `equipe_id`, os membros e a liderança da equipe (exige ser "
                          "da equipe), com `na_equipe` (contagens só das tarefas da equipe); sem ela, busca entre os usuários ativos (`busca`, "
                          "até 20). `carga`, `faixa`, `a_fazer`, `em_andamento` e `atrasadas` são sempre de todas as tarefas da pessoa.", responses={**SEM_PERMISSAO})
def pessoas(equipe_id: uuid.UUID | None = None, busca: str = Query("", max_length=100), sessao: Session = Depends(obter_sessao),
            usuario: Usuario = Depends(obter_usuario_atual)) -> list[PessoaCarga]:
    with _traduzir():
        if equipe_id:
            equipe = sessao.get(EquipeTarefas, equipe_id)
            if equipe is None or equipe not in servico.equipes_visiveis(sessao, usuario):
                raise ErroTarefa("Equipe não encontrada.", 404, "nao_encontrado")
            ids = servico.membros(equipe)
            usuarios = [u for u in (sessao.get(Usuario, i) for i in ids) if u and u.ativo]
        else:
            termo = f"%{busca.strip().lower()}%"
            usuarios = list(sessao.scalars(select(Usuario).where(
                Usuario.ativo.is_(True), func.lower(Usuario.nome_completo + " " + Usuario.login).like(termo)).order_by(Usuario.nome_completo).limit(20)))
    agora = agora_utc()
    cargas = servico.carga_das_pessoas(sessao, {u.id for u in usuarios}, agora)
    extras: dict[int, dict] = {}
    if equipe_id:
        # `na_equipe`: contagens só das tarefas desta equipe (visão da liderança); as demais são de todas as tarefas da pessoa
        for t in sessao.scalars(select(Tarefa).where(Tarefa.equipe_id == equipe_id)):
            atrasada = t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora
            for i in servico.envolvidos(t):
                c = extras.setdefault(i, {"a_fazer": 0, "em_andamento": 0, "atrasadas": 0, "em_validacao": 0, "concluidas": 0})
                c["concluidas" if t.status == "concluida" else t.status] += 1
                c["atrasadas"] += atrasada
        vazio = {"a_fazer": 0, "em_andamento": 0, "atrasadas": 0, "em_validacao": 0, "concluidas": 0}
        extras = {u.id: {"na_equipe": ContagemEquipe(**extras.get(u.id, vazio))} for u in usuarios}
    lista = [PessoaCarga(id=u.id, nome=u.nome_completo or u.login, login=u.login, cargo=u.cargo or "", **cargas[u.id], **extras.get(u.id, {}))
             for u in usuarios]
    return sorted(lista, key=lambda p: (-p.carga, p.nome.lower()))


@roteador.get("/pessoas/{usuario_id}/agenda", response_model=AgendaPessoa, summary="Agenda de uma pessoa (painel ao atribuir)",
              description="Carga e tarefas da pessoa para o painel que aparece ao escolher os responsáveis: **todas** as "
                          "abertas (a fazer, em andamento e em validação), com título, e as concluídas no período `de`–`ate` (padrão: 30 dias "
                          "antes a 60 dias depois de hoje). Aberto a qualquer usuário logado, porque quem atribui precisa ver a agenda de "
                          "quem recebe; `abrivel` diz se o usuário pode abrir cada tarefa. `400` se `de` > `ate`.",
              responses=resposta_nao_encontrado("Pessoa"))
def agenda(usuario_id: int, de: date | None = None, ate: date | None = None, sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> AgendaPessoa:
    pessoa = sessao.get(Usuario, usuario_id)
    if pessoa is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Pessoa não encontrada.", "nao_encontrado")
    agora = agora_utc()
    inicio = datetime.combine(de, datetime.min.time(), agora.tzinfo) if de else agora - timedelta(days=30)
    fim = datetime.combine(ate, datetime.max.time(), agora.tzinfo) if ate else agora + timedelta(days=60)
    if inicio > fim:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "O início do período é depois do fim.", "invalido")
    carga = servico.carga_das_pessoas(sessao, {pessoa.id}, agora)[pessoa.id]
    itens = [
        ItemAgenda(
            numero=t.numero, titulo=t.titulo, status=t.status, prioridade=t.prioridade, inicio=_utc(t.iniciada_em or t.criado_em),
            prazo=_utc(t.prazo), concluida_em=_utc(t.concluida_em), atrasada=t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora,
            equipe=EquipeResumo(id=t.equipe.id, nome=t.equipe.nome) if t.equipe else None,
            abrivel=servico.pode_ver(sessao, usuario, t),
        )
        for t in servico.agenda(sessao, pessoa, inicio, fim)
    ]
    return AgendaPessoa(pessoa=PessoaCarga(id=pessoa.id, nome=pessoa.nome_completo or pessoa.login, login=pessoa.login, cargo=pessoa.cargo or "", **carga),
                        de=inicio, ate=fim, itens=itens)


# ---------------------------------------------------------------------------------------------
# Equipes e marcadores
# ---------------------------------------------------------------------------------------------

def _equipe_leitura(sessao: Session, usuario: Usuario, e: EquipeTarefas) -> EquipeLeitura:
    _, tarefas = servico.da_equipe(sessao, usuario, e.id)
    pai = sessao.get(EquipeTarefas, e.equipe_pai_id) if e.equipe_pai_id else None
    return EquipeLeitura(
        id=e.id, nome=e.nome, equipe_pai_id=e.equipe_pai_id, equipe_pai_nome=pai.nome if pai else None, dono=_pessoa(sessao, e.dono_id),
        lideres=[p for p in (_pessoa(sessao, l.usuario_id) for l in e.lideres) if p], membros=[p for p in (_pessoa(sessao, m.usuario_id) for m in e.membros) if p],
        indicadores=Indicadores(**servico.indicadores(tarefas, agora_utc())), lider=usuario.superusuario or usuario.id in servico.lideranca(sessao, e),
        pode_configurar=servico.pode_configurar(usuario, e),
    )


@roteador.post("/contratos/sincronizar", response_model=ResumoSincronizacaoContratos, summary="Sincronizar as tarefas das competências de contratos",
               description="SuperRoot. Cria e atualiza, na equipe **Contratos**, as tarefas de cada etapa das competências regulares já liberadas "
                           "(contratos sem \"Liberar todas as competências\"), espelhando o estado real em Contratos: etapas já feitas nascem concluídas, com as "
                           "datas e os autores reais. É idempotente e roda sozinha todo dia às 07:00. Com `ensaio=true` (padrão) nada é gravado: o resumo mostra "
                           "o que seria feito.", responses={**SEM_PERMISSAO})
def sincronizar_contratos(ensaio: bool = Query(True, description="Só simula, sem gravar."),
                          sessao: Session = Depends(obter_sessao),
                          usuario: Usuario = Depends(obter_usuario_atual)) -> ResumoSincronizacaoContratos:
    if not usuario.superusuario:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Só um SuperRoot sincroniza as tarefas dos contratos.", "sem_permissao")
    from app.services.contratos import servico_tarefas_contratos

    r = servico_tarefas_contratos.sincronizar_todas(sessao, ensaio=ensaio)
    return ResumoSincronizacaoContratos(ensaio=ensaio, competencias=r.competencias, criadas=r.criadas, atualizadas=r.atualizadas, removidas=r.removidas, erros=r.erros)


@roteador.get("/equipes", response_model=list[EquipeLeitura], summary="Minhas equipes",
              description="Equipes em que o usuário é membro ou liderança (e as abaixo das que lidera); SuperRoot vê todas. Com indicadores.")
def listar_equipes(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[EquipeLeitura]:
    return [_equipe_leitura(sessao, usuario, e) for e in servico.equipes_visiveis(sessao, usuario)]


@roteador.post("/equipes", response_model=EquipeLeitura, status_code=status.HTTP_201_CREATED, summary="Criar equipe",
               description="Qualquer usuário cria; quem cria é o dono (governa membros e líderes).", responses={**INVALIDO})
def criar_equipe(dados: GravacaoEquipe, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EquipeLeitura:
    with _traduzir():
        e = servico.salvar_equipe(sessao, usuario, None, dados.nome, dados.equipe_pai_id, dados.lideres_ids, dados.membros_ids)
        return _equipe_leitura(sessao, usuario, e)


@roteador.put("/equipes/{equipe_id}", response_model=EquipeLeitura, summary="Alterar equipe",
              description="Dono da equipe ou SuperRoot.", responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Equipe")})
def alterar_equipe(equipe_id: uuid.UUID, dados: GravacaoEquipe, sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> EquipeLeitura:
    with _traduzir():
        e = servico.salvar_equipe(sessao, usuario, equipe_id, dados.nome, dados.equipe_pai_id, dados.lideres_ids, dados.membros_ids)
        return _equipe_leitura(sessao, usuario, e)


@roteador.delete("/equipes/{equipe_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir equipe",
                 description="Desativa a equipe (dono ou SuperRoot); recusa se houver tarefas em aberto.",
                 responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Equipe")})
def excluir_equipe(equipe_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir_equipe(sessao, usuario, equipe_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _leitura_marcador(m: MarcadorTarefa, usos: int = 0) -> MarcadorLeitura:
    return MarcadorLeitura(id=m.id, nome=m.nome, cor=m.cor, cor_indice=m.cor_indice, equipe_id=m.equipe_id, usos=usos)


@roteador.get("/equipes/{equipe_id}/desempenho", response_model=DesempenhoEquipe, summary="Desempenho da equipe (burndown e vazão)",
              description="Para a liderança (dono, líderes, inclusive de equipes acima, e SuperRoot): **burndown** em número de tarefas (real, ideal e escopo), "
                          "**vazão** semanal (criadas × concluídas e média móvel de 4 semanas), **tempo de ciclo e lead time** por semana (mediana e P85), "
                          "**fluxo acumulado** por situação e concluídas por pessoa. Inclui as sub-equipes. Padrão: últimos 30 dias; `marcador_id` filtra. "
                          "O histórico é reconstruído da linha do tempo. `403` fora da liderança; `400` se `de` > `ate` ou período > 366 dias.",
              responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Equipe")})
def desempenho_equipe(equipe_id: uuid.UUID, de: date | None = None, ate: date | None = None, marcador_id: uuid.UUID | None = None,
                      sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> DesempenhoEquipe:
    fim = ate or hoje_sao_paulo()
    inicio = de or fim - timedelta(days=29)
    with _traduzir():
        resultado = desempenho_tarefas.calcular(sessao, usuario, equipe_id, inicio, fim, marcador_id)
        ultimas = servico_marcos.historico(sessao, usuario, equipe_id, 1)
        return DesempenhoEquipe(**resultado, marcos=[_leitura_marco(m, p) for m, p in servico_marcos.listar(sessao, usuario, equipe_id)],
                                status_atual=_leitura_status(ultimas[0]) if ultimas else None)


@roteador.get("/pessoas/{usuario_id}/desempenho", response_model=DesempenhoEquipe, summary="Desempenho de uma pessoa (burndown e vazão)",
              description="Os mesmos gráficos e números do desempenho da equipe, para **uma pessoa**: todas as tarefas em que ela é responsável, de qualquer "
                          "equipe e também as pessoais (sem equipe). A própria pessoa e o SuperRoot veem tudo; a liderança vê só as tarefas das equipes que lidera "
                          "(as pessoais de outra pessoa ficam de fora). `escopo` volta como `pessoa`, `equipe_id` vazio e `equipe_nome` com o nome da pessoa. "
                          "Padrão: últimos 30 dias; `marcador_id` filtra. `403` fora dessas regras; `400` se `de` > `ate` ou período > 366 dias.",
              responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Pessoa")})
def desempenho_pessoa(usuario_id: int, de: date | None = None, ate: date | None = None, marcador_id: uuid.UUID | None = None,
                      sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> DesempenhoEquipe:
    fim = ate or hoje_sao_paulo()
    inicio = de or fim - timedelta(days=29)
    with _traduzir():
        pessoa = sessao.get(Usuario, usuario_id)
        if pessoa is None:
            raise ErroTarefa("Pessoa não encontrada.", 404, "nao_encontrado")
        return DesempenhoEquipe(**desempenho_tarefas.calcular_pessoa(sessao, usuario, pessoa, inicio, fim, marcador_id))


def _leitura_estagio(e: EstagioTarefa) -> EstagioLeitura:
    return EstagioLeitura(id=e.id, nome=e.nome, categoria=e.categoria, posicao=e.posicao, cor_indice=e.cor_indice)


# ---------------------------------------------------------------------------------------------
# Atividades agendadas e seguidores
# ---------------------------------------------------------------------------------------------

def _leitura_atividade(sessao: Session, usuario: Usuario, a: AtividadeTarefa, t: Tarefa) -> AtividadeLeitura:
    hoje = hoje_sao_paulo()
    situacao = "concluida" if a.concluida_em else "atrasada" if a.prazo < hoje else "hoje" if a.prazo == hoje else "futura"
    return AtividadeLeitura(
        id=a.id, tarefa_numero=t.numero, tarefa_titulo=t.titulo, tipo=a.tipo, resumo=a.resumo, nota=a.nota, prazo=a.prazo, situacao=situacao,
        responsavel=_pessoa(sessao, a.responsavel_id), criada_por=_pessoa(sessao, a.criada_por_id), concluida_em=_utc(a.concluida_em),
        concluida_por=_pessoa(sessao, a.concluida_por_id), feedback=a.feedback,
        pode_mexer=a.concluida_em is None and (usuario.id in (a.responsavel_id, a.criada_por_id) or servico.pode_editar(sessao, usuario, t)),
    )


@roteador.get("/atividades", response_model=list[AtividadeLeitura], summary="Minhas atividades",
              description="Atividades agendadas para o usuário: abertas, por data (atrasadas, hoje e futuras) ou, com `concluidas=true`, as 50 últimas concluídas.")
def minhas_atividades(concluidas: bool = False, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[AtividadeLeitura]:
    return [_leitura_atividade(sessao, usuario, a, t) for a, t in servico_atividades.minhas(sessao, usuario, concluidas)]


@roteador.put("/atividades/{atividade_id}", response_model=AtividadeLeitura, summary="Alterar atividade",
              description="Quem agendou, quem faz ou quem edita a tarefa. Atividade concluída: `409`.", responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **resposta_nao_encontrado("Atividade")})
def alterar_atividade(atividade_id: uuid.UUID, dados: GravacaoAtividade, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtividadeLeitura:
    with _traduzir():
        a, t = servico_atividades.obter(sessao, usuario, atividade_id)
        servico_atividades.atualizar(sessao, usuario, a, t, servico_atividades.DadosAtividade(dados.resumo, dados.tipo, dados.nota, dados.prazo, dados.responsavel_id))
        return _leitura_atividade(sessao, usuario, a, t)


@roteador.post("/atividades/{atividade_id}/concluir", response_model=AtividadeLeitura, summary="Concluir atividade",
               description="Com `feedback` opcional, que vai para a linha do tempo da tarefa. Quem agendou (se for outra pessoa) é avisado.",
               responses={**SEM_PERMISSAO, **CONFLITO, **resposta_nao_encontrado("Atividade")})
def concluir_atividade(atividade_id: uuid.UUID, dados: ConclusaoAtividade, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtividadeLeitura:
    with _traduzir():
        a, t = servico_atividades.obter(sessao, usuario, atividade_id)
        servico_atividades.concluir(sessao, usuario, a, t, dados.feedback)
        return _leitura_atividade(sessao, usuario, a, t)


@roteador.delete("/atividades/{atividade_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir atividade",
                 responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Atividade")})
def excluir_atividade(atividade_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        a, t = servico_atividades.obter(sessao, usuario, atividade_id)
        servico_atividades.excluir(sessao, usuario, a, t)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Marcos e status da equipe
# ---------------------------------------------------------------------------------------------

def _leitura_marco(m: MarcoTarefa, p: dict) -> MarcoLeitura:
    return MarcoLeitura(id=m.id, nome=m.nome, descricao=m.descricao, data_alvo=m.data_alvo, atingido_em=_utc(m.atingido_em), **p)


def _leitura_status(a: AtualizacaoStatusEquipe) -> AtualizacaoStatusLeitura:
    return AtualizacaoStatusLeitura(id=a.id, situacao=a.situacao, texto=a.texto, autor_nome=a.autor_nome, criado_em=_utc(a.criado_em))


@roteador.get("/equipes/{equipe_id}/marcos", response_model=list[MarcoLeitura], summary="Marcos da equipe",
              description="Marcos (milestones) com progresso (tarefas, concluídas e atrasadas) e situação derivada, por data-alvo. Membros e liderança.",
              responses={**resposta_nao_encontrado("Equipe")})
def listar_marcos(equipe_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[MarcoLeitura]:
    with _traduzir():
        return [_leitura_marco(m, p) for m, p in servico_marcos.listar(sessao, usuario, equipe_id)]


@roteador.post("/equipes/{equipe_id}/marcos", response_model=MarcoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar marco",
               description="Só a liderança. Nome único na equipe (`409`).", responses={**SEM_PERMISSAO, **CONFLITO})
def criar_marco(equipe_id: uuid.UUID, dados: GravacaoMarco, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> MarcoLeitura:
    with _traduzir():
        m = servico_marcos.salvar(sessao, usuario, equipe_id, servico_marcos.DadosMarco(dados.nome, dados.data_alvo, dados.descricao))
        return _leitura_marco(m, servico_marcos.progresso(sessao, m))


@roteador.put("/marcos/{marco_id}", response_model=MarcoLeitura, summary="Alterar marco", description="Só a liderança.", responses={**SEM_PERMISSAO, **CONFLITO, **resposta_nao_encontrado("Marco")})
def alterar_marco(marco_id: uuid.UUID, dados: GravacaoMarco, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> MarcoLeitura:
    with _traduzir():
        marco = servico_marcos.obter(sessao, usuario, marco_id, lider=True)
        m = servico_marcos.salvar(sessao, usuario, marco.equipe_id, servico_marcos.DadosMarco(dados.nome, dados.data_alvo, dados.descricao), marco)
        return _leitura_marco(m, servico_marcos.progresso(sessao, m))


@roteador.delete("/marcos/{marco_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir marco",
                 description="Só a liderança. As tarefas continuam, sem marco.", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Marco")})
def excluir_marco(marco_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico_marcos.excluir(sessao, usuario, servico_marcos.obter(sessao, usuario, marco_id, lider=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/marcos/{marco_id}/atingir", response_model=MarcoLeitura, summary="Marcar o marco como atingido",
               description="Decisão manual da liderança; o estado fica fixo (a conclusão das tarefas não o muda mais).", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Marco")})
def atingir_marco(marco_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> MarcoLeitura:
    with _traduzir():
        m = servico_marcos.atingir(sessao, usuario, servico_marcos.obter(sessao, usuario, marco_id, lider=True), True)
        return _leitura_marco(m, servico_marcos.progresso(sessao, m))


@roteador.post("/marcos/{marco_id}/reabrir", response_model=MarcoLeitura, summary="Reabrir o marco",
               description="Decisão manual da liderança: volta a aberto e o estado fica fixo.", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Marco")})
def reabrir_marco(marco_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> MarcoLeitura:
    with _traduzir():
        m = servico_marcos.atingir(sessao, usuario, servico_marcos.obter(sessao, usuario, marco_id, lider=True), False)
        return _leitura_marco(m, servico_marcos.progresso(sessao, m))


@roteador.get("/equipes/{equipe_id}/status", response_model=list[AtualizacaoStatusLeitura], summary="Atualizações de status da equipe",
              description="As últimas 30 atualizações publicadas pela liderança, da mais recente para a mais antiga (a primeira é a situação atual). Membros e liderança.",
              responses={**resposta_nao_encontrado("Equipe")})
def historico_status(equipe_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[AtualizacaoStatusLeitura]:
    with _traduzir():
        return [_leitura_status(a) for a in servico_marcos.historico(sessao, usuario, equipe_id)]


@roteador.post("/equipes/{equipe_id}/status", response_model=AtualizacaoStatusLeitura, status_code=status.HTTP_201_CREATED, summary="Publicar atualização de status",
               description="Só a liderança. `situacao`: no_prazo, em_risco, atrasado, em_espera ou concluido, com texto opcional. Membros e liderança são avisados "
                           "(e-mail só em risco ou atrasado). Toda segunda-feira a liderança é lembrada se não houver atualização há 7 dias.", responses={**SEM_PERMISSAO, **INVALIDO})
def publicar_status(equipe_id: uuid.UUID, dados: GravacaoStatusEquipe, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtualizacaoStatusLeitura:
    with _traduzir():
        return _leitura_status(servico_marcos.publicar(sessao, usuario, equipe_id, dados.situacao, dados.texto))


@roteador.get("/equipes/{equipe_id}/estagios", response_model=list[EstagioLeitura], summary="Estágios (colunas) da equipe",
              description="As colunas do quadro da equipe, em ordem. Cada estágio tem uma `categoria` (a situação do pipeline que ele representa). Uma equipe sem estágios "
                          "ganha os 4 padrão na primeira consulta. Membros, liderança e SuperRoot.", responses={**resposta_nao_encontrado("Equipe")})
def listar_estagios(equipe_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[EstagioLeitura]:
    with _traduzir():
        return [_leitura_estagio(e) for e in servico_estagios.listar(sessao, usuario, equipe_id)]


@roteador.put("/equipes/{equipe_id}/estagios", response_model=list[EstagioLeitura], summary="Configurar estágios da equipe",
              description="Grava a lista completa e ordenada (de 4 a 20 estágios). Ordem do pipeline entre as categorias; ao menos um \"A fazer\" e um \"Em andamento\" e "
                          "exatamente um \"Em validação\" e um \"Concluída\"; nomes únicos. Estágio com tarefas só é excluído depois de movê-las (`409`). Só a liderança.",
              responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **resposta_nao_encontrado("Equipe")})
def configurar_estagios(equipe_id: uuid.UUID, dados: GravacaoEstagios, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[EstagioLeitura]:
    with _traduzir():
        itens = [servico_estagios.DadosEstagio(nome=e.nome, categoria=e.categoria, cor_indice=e.cor_indice, id=e.id) for e in dados.estagios]
        return [_leitura_estagio(e) for e in servico_estagios.substituir(sessao, usuario, equipe_id, itens)]


@roteador.get("/equipes/{equipe_id}/marcadores", response_model=list[MarcadorLeitura], summary="Marcadores da equipe (mais usados primeiro)",
              description="Marcadores da equipe e os globais (sem equipe), ordenados pelo **uso nas últimas 1000 tarefas da equipe** e depois por nome. "
                          "`busca` filtra por trecho do nome (sem diferenciar maiúsculas nem acentos); `limite` (padrão 100) corta a lista. "
                          "Alimenta o campo de marcadores (lista ao focar e filtro ao digitar).")
def listar_marcadores(equipe_id: uuid.UUID, busca: str = Query("", max_length=120), limite: int = Query(100, ge=1, le=500),
                      sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> list[MarcadorLeitura]:
    return [_leitura_marcador(m, usos) for m, usos in servico.listar_marcadores(sessao, equipe_id, busca, limite)]


@roteador.post("/equipes/{equipe_id}/marcadores", response_model=MarcadorLeitura, status_code=status.HTTP_201_CREATED,
               summary="Criar marcador da equipe",
               description="Membros e liderança da equipe criam na hora (como \"Criar 'texto'\" do Odoo). Se já existe um marcador com o mesmo nome "
                           "(sem diferenciar maiúsculas), devolve o existente sem alterar. Sem `cor_indice`, sorteia uma cor de 1 a 11.",
               responses={**SEM_PERMISSAO})
def criar_marcador(equipe_id: uuid.UUID, dados: GravacaoMarcador, sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> MarcadorLeitura:
    with _traduzir():
        return _leitura_marcador(servico.salvar_marcador(sessao, usuario, equipe_id, dados.nome, _cor_do_marcador(dados)))


@roteador.put("/equipes/{equipe_id}/marcadores/{marcador_id}", response_model=MarcadorLeitura, summary="Alterar marcador (nome e cor)",
              description="Só a liderança da equipe. Nome repetido na equipe: `409`.", responses={**SEM_PERMISSAO, **CONFLITO, **resposta_nao_encontrado("Marcador")})
def alterar_marcador(equipe_id: uuid.UUID, marcador_id: uuid.UUID, dados: GravacaoMarcador, sessao: Session = Depends(obter_sessao),
                     usuario: Usuario = Depends(obter_usuario_atual)) -> MarcadorLeitura:
    with _traduzir():
        return _leitura_marcador(servico.salvar_marcador(sessao, usuario, equipe_id, dados.nome, _cor_do_marcador(dados), marcador_id))


def _cor_do_marcador(dados: GravacaoMarcador) -> int | None:
    """`cor_indice` tem prioridade; o hexadecimal legado vira a cor da paleta mais próxima."""
    if dados.cor_indice is not None:
        return dados.cor_indice
    return paleta.indice_mais_proximo(dados.cor) if dados.cor else None


@roteador.delete("/marcadores/{marcador_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir marcador",
                 description="Só a liderança da equipe do marcador (globais: SuperRoot).", responses={**SEM_PERMISSAO})
def excluir_marcador(marcador_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir_marcador(sessao, usuario, marcador_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Tarefa
# ---------------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------------
# Tarefas recorrentes
# ---------------------------------------------------------------------------------------------

def _leitura_marcador_serie(m: MarcadorTarefa) -> MarcadorLeitura:
    return MarcadorLeitura(id=m.id, nome=m.nome, cor=m.cor, cor_indice=m.cor_indice, equipe_id=m.equipe_id)


def _leitura_recorrencia(sessao: Session, usuario: Usuario, rec: RecorrenciaTarefa) -> RecorrenciaLeitura:
    regra = servico_recorrencias.regra_da_serie(rec)
    feriados = servico_recorrencias.feriados_cadastrados(sessao)
    proximas: list = []
    if rec.proxima_data is not None:
        proximas, atual, consumidas = [rec.proxima_data], rec.proxima_data, rec.geradas + 1
        while len(proximas) < 3 and not (rec.max_ocorrencias is not None and consumidas >= rec.max_ocorrencias):
            atual = servico_recorrencias.proxima_data(rec.inicio, regra, atual, feriados)
            if atual is None:
                break
            proximas.append(atual)
            consumidas += 1
    ordenados = sorted(rec.responsaveis, key=lambda r: r.posicao)
    return RecorrenciaLeitura(
        id=rec.id, equipe=EquipeResumo(id=rec.equipe.id, nome=rec.equipe.nome) if rec.equipe else None, titulo=rec.titulo, descricao=rec.descricao,
        prioridade=rec.prioridade, checklist=list(rec.checklist or []), responsaveis=[p for p in (_pessoa(sessao, r.usuario_id) for r in ordenados) if p],
        marcadores=[_leitura_marcador_serie(m) for m in rec.marcadores], regra=_entrada_da_regra(regra), resumo=servico_recorrencias.descrever(regra, rec.inicio),
        inicio=rec.inicio, hora_prazo=rec.hora_prazo, ativa=rec.ativa, proxima_data=rec.proxima_data, proximas=proximas, geradas=rec.geradas,
        ultimo_erro=rec.ultimo_erro or "", criado_por=_pessoa(sessao, rec.criado_por_id), pode_gerir=servico_recorrencias.pode_gerir(sessao, usuario, rec),
    )


@roteador.post("/recorrencias/previa", response_model=RespostaPreviaRecorrencia, summary="Prévia da recorrência",
               description="Texto da regra e as próximas datas de prazo (depois da primeira) para o prazo escolhido; usa o mesmo cálculo da geração, "
                           "inclusive dias úteis e feriados cadastrados. `400` se a regra for inválida.", responses={**INVALIDO})
def previa_recorrencia(dados: PreviaRecorrencia, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> RespostaPreviaRecorrencia:
    with _traduzir():
        resumo, proximas = servico_recorrencias.previa(dados.prazo, _regra(dados.regra), sessao)
    return RespostaPreviaRecorrencia(resumo=resumo, proximas=proximas)


@roteador.get("/recorrencias", response_model=list[RecorrenciaLeitura], summary="Séries recorrentes da equipe",
              description="Séries da equipe (para membros e liderança) ou, sem `equipe_id`, as séries pessoais do usuário.")
def listar_recorrencias(equipe_id: uuid.UUID | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[RecorrenciaLeitura]:
    return [_leitura_recorrencia(sessao, usuario, r) for r in servico_recorrencias.listar(sessao, usuario, equipe_id)]


@roteador.get("/recorrencias/{recorrencia_id}", response_model=RecorrenciaLeitura, summary="Série recorrente",
              responses={**resposta_nao_encontrado("Recorrência")})
def obter_recorrencia(recorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RecorrenciaLeitura:
    with _traduzir():
        return _leitura_recorrencia(sessao, usuario, servico_recorrencias.obter(sessao, usuario, recorrencia_id))


@roteador.put("/recorrencias/{recorrencia_id}", response_model=RecorrenciaLeitura, summary="Alterar série recorrente",
              description="Altera o modelo e a regra; vale só para as próximas ocorrências (as já criadas não mudam). Quem criou a série, a liderança da equipe "
                          "ou o SuperRoot.", responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Recorrência")})
def alterar_recorrencia(recorrencia_id: uuid.UUID, dados: GravacaoRecorrencia, sessao: Session = Depends(obter_sessao),
                        usuario: Usuario = Depends(obter_usuario_atual)) -> RecorrenciaLeitura:
    with _traduzir():
        rec = servico_recorrencias.obter(sessao, usuario, recorrencia_id, gerir=True)
        servico_recorrencias.atualizar(
            sessao, usuario, rec, titulo=dados.titulo, descricao=dados.descricao, prioridade=dados.prioridade, checklist=dados.checklist,
            responsaveis_ids=dados.responsaveis_ids, marcadores_ids=dados.marcadores_ids, regra=_regra(dados.regra), hora_prazo=dados.hora_prazo)
        return _leitura_recorrencia(sessao, usuario, rec)


@roteador.post("/recorrencias/{recorrencia_id}/pausar", response_model=RecorrenciaLeitura, summary="Pausar série recorrente",
               description="Não gera novas ocorrências até ser retomada. As tarefas já criadas continuam.", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Recorrência")})
def pausar_recorrencia(recorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RecorrenciaLeitura:
    with _traduzir():
        rec = servico_recorrencias.pausar(sessao, usuario, servico_recorrencias.obter(sessao, usuario, recorrencia_id, gerir=True))
        return _leitura_recorrencia(sessao, usuario, rec)


@roteador.post("/recorrencias/{recorrencia_id}/retomar", response_model=RecorrenciaLeitura, summary="Retomar série recorrente",
               description="Volta a gerar a partir da próxima data da regra (as vencidas durante a pausa não são criadas).", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Recorrência")})
def retomar_recorrencia(recorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RecorrenciaLeitura:
    with _traduzir():
        rec = servico_recorrencias.retomar(sessao, usuario, servico_recorrencias.obter(sessao, usuario, recorrencia_id, gerir=True))
        return _leitura_recorrencia(sessao, usuario, rec)


@roteador.delete("/recorrencias/{recorrencia_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir série recorrente",
                 description="Remove a série; as tarefas já criadas continuam, sem vínculo.", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Recorrência")})
def excluir_recorrencia(recorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico_recorrencias.excluir(sessao, usuario, servico_recorrencias.obter(sessao, usuario, recorrencia_id, gerir=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _regra(entrada: RegraRecorrenciaEntrada) -> servico_recorrencias.RegraRecorrencia:
    return servico_recorrencias.RegraRecorrencia(
        entrada.frequencia, entrada.intervalo, tuple(entrada.dias_semana), entrada.somente_dias_uteis, entrada.antecedencia_dias, entrada.fim, entrada.max_ocorrencias)


def _entrada_da_regra(regra: servico_recorrencias.RegraRecorrencia) -> RegraRecorrenciaEntrada:
    return RegraRecorrenciaEntrada(
        frequencia=regra.frequencia, intervalo=regra.intervalo, dias_semana=list(regra.dias_semana), somente_dias_uteis=regra.somente_dias_uteis,
        antecedencia_dias=regra.antecedencia_dias, fim=regra.fim, max_ocorrencias=regra.max_ocorrencias)


def _criar(sessao: Session, usuario: Usuario, dados: NovaTarefa, arquivos: list | None) -> Tarefa:
    """Cria a tarefa e, se houver `recorrencia`, a série junto (a tarefa é a primeira ocorrência)."""
    base = servico.DadosTarefa(
        titulo=dados.titulo, descricao=dados.descricao, prazo=dados.prazo, prioridade=dados.prioridade, equipe_id=dados.equipe_id,
        responsaveis_ids=tuple(dados.responsaveis_ids), marcadores_ids=tuple(dados.marcadores_ids))
    if dados.recorrencia is not None:
        return servico_recorrencias.criar_com_serie(sessao, usuario, base, _regra(dados.recorrencia), arquivos)
    return servico.criar(sessao, usuario, base, arquivos)


@roteador.post("", response_model=TarefaDetalhe, status_code=status.HTTP_201_CREATED, summary="Criar tarefa",
               description="Responsáveis (um ou mais, com os mesmos poderes; o primeiro é o principal); padrão: quem cadastra. Numa equipe, os responsáveis são da equipe (a liderança pode incluir "
                           "outras pessoas). Os envolvidos recebem aviso com e-mail.", responses={**SEM_PERMISSAO, **INVALIDO})
def criar(dados: NovaTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = _criar(sessao, usuario, dados, None)
    return _detalhe(sessao, usuario, t)


@roteador.post("/com-anexos", response_model=TarefaDetalhe, status_code=status.HTTP_201_CREATED, summary="Criar tarefa com anexos",
               description="Igual a `POST /api/tarefas`, mas em `multipart/form-data`: `dados` (JSON do corpo de criação, como texto) e até 5 `arquivos` "
                           "(PDF, Office/LibreOffice, TXT, CSV, PNG, JPG). Os arquivos ficam no evento \"Tarefa criada\" da linha do tempo; arquivo recusado "
                           "(tipo, tamanho ou vazio) cancela a criação (`400`).", responses={**SEM_PERMISSAO, **INVALIDO})
async def criar_com_anexos(dados: str = Form(...), arquivos: list[UploadFile] = File(default_factory=list), sessao: Session = Depends(obter_sessao),
                           usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    try:
        nova = NovaTarefa.model_validate_json(dados)
    except ValueError as erro:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_CONTENT, "Dados da tarefa inválidos.", "validacao") from erro
    with _traduzir():
        t = _criar(sessao, usuario, nova, [(a.filename or "arquivo", a.file) for a in arquivos if a.filename])
    return _detalhe(sessao, usuario, t)


@roteador.get("/{numero}", response_model=TarefaDetalhe, summary="Detalhe da tarefa",
              description="Com as etapas do pipeline e as ações permitidas ao usuário. Sem permissão: 404.", responses={**NAO_ENCONTRADA})
def detalhar(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        return _detalhe(sessao, usuario, servico.obter(sessao, usuario, numero))


@roteador.put("/{numero}", response_model=TarefaDetalhe, summary="Editar tarefa",
              description="Título, descrição, prioridade, responsáveis e marcadores (o prazo tem rota própria). `versao` evita sobrescrever "
                          "alteração de outra pessoa (409).", responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def editar(numero: int, dados: EdicaoTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.editar(sessao, usuario, servico.obter(sessao, usuario, numero), dados.titulo, dados.descricao, dados.prioridade,
                           tuple(dados.responsaveis_ids), tuple(dados.marcadores_ids), dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/subtarefas", response_model=TarefaDetalhe, status_code=status.HTTP_201_CREATED, summary="Criar subtarefa",
               description="Cria uma subtarefa da tarefa (um só nível). Herda equipe e marcadores; sem prazo, usa o da mãe (que não pode ser ultrapassado); sem responsáveis, "
                           "usa os da mãe. A subtarefa tem andamento próprio (a mãe se move sem depender dela; ao mover a mãe, cada subtarefa só ganha um registro na linha do tempo). Devolve a subtarefa criada.",
               responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
def criar_subtarefa(numero: int, dados: NovaSubtarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        mae = servico.obter(sessao, usuario, numero)
        sub = servico_subtarefas.criar_subtarefa(sessao, usuario, mae, servico_subtarefas.DadosSubtarefa(
            titulo=dados.titulo, descricao=dados.descricao, prazo=dados.prazo, prioridade=dados.prioridade, responsaveis_ids=tuple(dados.responsaveis_ids)))
    return _detalhe(sessao, usuario, sub)


@roteador.put("/{numero}/dependencias", response_model=TarefaDetalhe, summary="Definir tarefas bloqueadoras",
              description="Substitui a lista de tarefas que bloqueiam esta (`numeros`): ela não inicia enquanto alguma não for concluída. As tarefas precisam ser da mesma equipe "
                          "e visíveis ao usuário; `400` para a própria tarefa, mãe/subtarefa, outra equipe ou ciclo.", responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
def definir_dependencias(numero: int, dados: Dependencias, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico_subtarefas.definir_dependencias(sessao, usuario, servico.obter(sessao, usuario, numero), dados.numeros)
    return _detalhe(sessao, usuario, t)


@roteador.get("/{numero}/atividades", response_model=list[AtividadeLeitura], summary="Atividades da tarefa",
              description="Abertas primeiro (por data) e depois as concluídas.", responses={**NAO_ENCONTRADA})
def atividades_da_tarefa(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> list[AtividadeLeitura]:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
    return [_leitura_atividade(sessao, usuario, a, t) for a in servico_atividades.listar(sessao, usuario, t)]


@roteador.post("/{numero}/atividades", response_model=AtividadeLeitura, status_code=status.HTTP_201_CREATED, summary="Agendar atividade",
               description="Tipos: fazer, ligar, email, reuniao, revisar, enviar_documento. `prazo` (data; padrão hoje) e `responsavel_id` (padrão: quem agenda; numa equipe, "
                           "da equipe). Quem é agendado por outra pessoa recebe aviso com e-mail. A rotina das 07:00 avisa as de hoje e as atrasadas.",
               responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
def agendar_atividade(numero: int, dados: GravacaoAtividade, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AtividadeLeitura:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
        a = servico_atividades.criar(sessao, usuario, t, servico_atividades.DadosAtividade(dados.resumo, dados.tipo, dados.nota, dados.prazo, dados.responsavel_id))
        return _leitura_atividade(sessao, usuario, a, t)


@roteador.post("/{numero}/seguir", response_model=TarefaDetalhe, summary="Seguir a tarefa",
               description="Quem segue recebe os avisos informativos (comentários, prazos e validação) sem ser responsável.", responses={**NAO_ENCONTRADA})
def seguir_tarefa(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico_atividades.seguir(sessao, usuario, servico.obter(sessao, usuario, numero), True)
    return _detalhe(sessao, usuario, t)


@roteador.delete("/{numero}/seguir", response_model=TarefaDetalhe, summary="Deixar de seguir a tarefa", responses={**NAO_ENCONTRADA})
def deixar_de_seguir(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico_atividades.seguir(sessao, usuario, servico.obter(sessao, usuario, numero), False)
    return _detalhe(sessao, usuario, t)


@roteador.put("/{numero}/marco", response_model=TarefaDetalhe, summary="Definir o marco da tarefa",
              description="Liga a tarefa a um marco da mesma equipe (ou tira, com `marco_id` vazio). Quem edita a tarefa. O marco é reavaliado: com todas as tarefas concluídas, fica atingido.",
              responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
def definir_marco(numero: int, dados: MarcoDaTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico_marcos.definir_marco_da_tarefa(sessao, usuario, servico.obter(sessao, usuario, numero), dados.marco_id)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/prazo", response_model=TarefaDetalhe, summary="Alterar prazo",
               description="Justificativa obrigatória; entra na linha do tempo e os envolvidos são avisados.",
               responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def alterar_prazo(numero: int, dados: MudancaPrazo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.alterar_prazo(sessao, usuario, servico.obter(sessao, usuario, numero), dados.prazo, dados.justificativa, dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/mover", response_model=TarefaDetalhe, summary="Mover no pipeline",
               description="`acao`: iniciar, pausar, entregar (para validação), validar, devolver (motivo obrigatório), concluir (liderança) ou "
                           "reabrir (motivo obrigatório). A permissão depende do papel e da etapa atual (ver `acoes` no detalhe).",
               responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def mover(numero: int, dados: Movimento, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.mover(sessao, usuario, servico.obter(sessao, usuario, numero), dados.acao, dados.texto, dados.versao, dados.estagio_id)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/estagio", response_model=TarefaDetalhe, summary="Mudar de estágio (mesma situação)",
               description="Troca a coluna da tarefa dentro da **mesma categoria** (ex.: de \"Triagem\" para \"Em análise\", ambas em andamento). Para outra situação, use "
                           "`POST /{numero}/mover` com `estagio_id`. Responsáveis e liderança.", responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def mudar_estagio(numero: int, dados: MudancaEstagio, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico_estagios.definir_estagio(sessao, usuario, servico.obter(sessao, usuario, numero), dados.estagio_id, dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/transferir", response_model=TarefaDetalhe, summary="Transferir tarefa",
               description="Para membro da equipe (a liderança, para qualquer usuário ativo), com justificativa e novo prazo opcional.",
               responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def transferir(numero: int, dados: Transferencia, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.transferir(sessao, usuario, servico.obter(sessao, usuario, numero), dados.para_id, dados.justificativa, dados.novo_prazo, dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/comentarios", response_model=EventoLeitura, status_code=status.HTTP_201_CREATED, summary="Comentar e anexar",
               description="`multipart/form-data`: `texto` e/ou até 5 `arquivos` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG) e, opcionalmente, "
                           "`em_resposta_a` (id de um comentário desta tarefa): a resposta guarda em `dados` quem e o que foi respondido (`resposta_a`, "
                           "`resposta_autor`, `resposta_texto`) e aparece no topo da lista como qualquer comentário novo; `404` se o comentário não existir "
                           "nesta tarefa ou já foi removido. Os envolvidos recebem aviso. Vale também para tarefa concluída.", responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
async def comentar(numero: int, texto: str = Form(""), em_resposta_a: uuid.UUID | None = Form(None), arquivos: list[UploadFile] = File(default_factory=list),
                   sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EventoLeitura:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
        evento = servico.comentar(sessao, usuario, t, texto, [(a.filename or "arquivo", a.file) for a in arquivos if a.filename], em_resposta_a)
    return _evento(evento)


def _evento(e: EventoTarefa) -> EventoLeitura:
    return EventoLeitura(
        id=e.id, tipo=e.tipo, titulo=e.titulo, texto="" if e.removido_em else e.texto, dados={} if e.removido_em else (e.dados or {}),
        autor=e.autor_nome, criado_em=_utc(e.criado_em), removido=e.removido_em is not None, motivo_remocao=e.motivo_remocao,
        anexos=[AnexoLeitura(id=v.anexo.id, nome=v.anexo.nome_original, tamanho=v.anexo.tamanho, tipo=v.anexo.tipo_conteudo,
                             removido=v.anexo.excluido_em is not None) for v in e.anexos],
    )


@roteador.get("/{numero}/linha-do-tempo", response_model=LinhaDoTempo, summary="Linha do tempo",
              description="Mais recentes primeiro. `filtro`: comentarios, anexos, status, prazos ou atribuicoes (vazio: tudo). Paginação por "
                          "`antes_de` (data do último item recebido) e `limite`.", responses={**NAO_ENCONTRADA})
def linha_do_tempo(numero: int, filtro: str = Query("", pattern="^(|comentarios|anexos|status|prazos|atribuicoes)$"), antes_de: datetime | None = None,
                   limite: int = Query(30, ge=1, le=100), sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> LinhaDoTempo:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
    consulta = select(EventoTarefa).where(EventoTarefa.tarefa_id == t.id)
    if filtro == "anexos":
        consulta = consulta.where(EventoTarefa.id.in_(select(AnexoEventoTarefa.evento_id)))
    elif filtro:
        consulta = consulta.where(EventoTarefa.tipo.in_(FILTROS_LINHA[filtro]))
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    if antes_de is not None:
        consulta = consulta.where(EventoTarefa.criado_em < antes_de)
    itens = list(sessao.scalars(consulta.order_by(EventoTarefa.criado_em.desc()).limit(limite + 1)))
    return LinhaDoTempo(total=total, itens=[_evento(e) for e in itens[:limite]], tem_mais=len(itens) > limite)


@roteador.get("/{numero}/memorial", summary="Relatório memorial da tarefa (PDF ou XLSX)", response_class=Response,
              description="Dados da tarefa, dias em aberto e **todos** os acontecimentos da linha do tempo (comentários, situação, prazos, atribuições, anexos, checklist, "
                          "escalonamentos), do mais antigo ao mais recente. Itens removidos aparecem identificados, sem o conteúdo. Quem vê a tarefa pode emitir. "
                          "XLSX: abas **Resumo** e **Acontecimentos**.",
              responses={200: {"content": {memorial_tarefa.XLSX: {}, "application/pdf": {}}, "description": "Arquivo gerado."}, **NAO_ENCONTRADA})
def memorial(numero: int, formato: str = Query("pdf", pattern="^(pdf|xlsx)$"), sessao: Session = Depends(obter_sessao),
             usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
    conteudo, nome, midia = memorial_tarefa.gerar(sessao, usuario, t, formato, agora_utc())
    return Response(conteudo, media_type=midia, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/{numero}/anexos/{anexo_id}", response_class=FileResponse, summary="Baixar anexo",
              description="Confere se o usuário pode ver a tarefa e se o anexo é dela.", responses={**NAO_ENCONTRADA})
def baixar_anexo(numero: int, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> FileResponse:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
    vinculo = sessao.scalar(select(AnexoEventoTarefa).join(EventoTarefa, EventoTarefa.id == AnexoEventoTarefa.evento_id)
                            .where(EventoTarefa.tarefa_id == t.id, AnexoEventoTarefa.anexo_id == anexo_id))
    anexo = sessao.get(Anexo, anexo_id) if vinculo else None
    if anexo is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Anexo não encontrado.", "nao_encontrado")
    try:
        return servico_anexos.resposta_download(anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


@roteador.post("/{numero}/eventos/{evento_id}/remover", response_model=EventoLeitura, summary="Remover item da linha do tempo (SuperRoot)",
               description="Remoção lógica com motivo; o registro da remoção entra na linha do tempo.", responses={**SEM_PERMISSAO, **NAO_ENCONTRADA})
def remover_evento(numero: int, evento_id: uuid.UUID, dados: RemocaoEvento, sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> EventoLeitura:
    with _traduzir():
        return _evento(servico.remover_evento(sessao, usuario, servico.obter(sessao, usuario, numero), evento_id, dados.motivo))


@roteador.post("/{numero}/checklist", response_model=TarefaDetalhe, summary="Checklist da tarefa",
               description="`acao`: incluir (`texto`), marcar ou remover (`item_id`).", responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
def checklist(numero: int, dados: OperacaoChecklist, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.checklist(sessao, usuario, servico.obter(sessao, usuario, numero), dados.acao, dados.texto, dados.item_id)
    return _detalhe(sessao, usuario, t)


@roteador.delete("/{numero}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir tarefa",
                 description="Quem criou ou a liderança.", responses={**SEM_PERMISSAO, **NAO_ENCONTRADA})
def excluir(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir(sessao, usuario, servico.obter(sessao, usuario, numero))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
