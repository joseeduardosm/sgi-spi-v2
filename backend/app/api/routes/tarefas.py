# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Módulo Tarefas (tarefas, pipeline, linha do tempo, equipes e marcadores).
"""Rotas `/api/tarefas`. Todas exigem login; as permissões por tarefa e equipe ficam em `servico_tarefas`."""

import uuid
from contextlib import contextmanager
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import agora_utc, obter_sessao
from app.core.erros import ErroApi
from app.models.anexo import Anexo
from app.models.tarefas import AnexoEventoTarefa, EquipeTarefas, EventoTarefa, MarcadorTarefa, Tarefa
from app.models.usuario import Usuario
from app.schemas.tarefas import (
    AnexoLeitura, Contexto, EdicaoTarefa, EquipeLeitura, EquipeResumo, Etapa, EventoLeitura, GravacaoEquipe, GravacaoMarcador,
    Indicadores, ItemChecklist, LinhaDoTempo, ListaTarefas, MarcadorLeitura, Movimento, MudancaPrazo, NovaTarefa, OperacaoChecklist,
    ContagemEquipe, Pessoa, PessoaCarga, RemocaoEvento, Reordenacao, TarefaDetalhe, TarefaResumo, Transferencia,
)
from app.services import servico_anexos
from app.services.tarefas import relatorio_tarefas
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


def _utc(valor: datetime | None) -> datetime | None:
    """Datas sempre com fuso (o SQLite dos testes devolve sem)."""
    return servico._comparavel(valor) if valor else None


def _resumo(sessao: Session, t: Tarefa, prorrogacoes: dict, agora: datetime) -> dict:
    return {
        "id": t.id, "numero": t.numero, "titulo": t.titulo, "status": t.status, "prioridade": t.prioridade, "prazo": _utc(t.prazo),
        "prazo_original": _utc(t.prazo_original), "prorrogacoes": prorrogacoes.get(t.id, 0),
        "atrasada": t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora,
        "equipe": EquipeResumo(id=t.equipe.id, nome=t.equipe.nome) if t.equipe else None, "responsavel": _pessoa(sessao, t.responsavel_id),
        "participantes": len([p for p in t.participantes if p.usuario_id != t.responsavel_id]), "marcadores": [MarcadorLeitura.model_validate(m, from_attributes=True) for m in t.marcadores],
        "checklist_feitos": sum(1 for i in t.checklist if i.concluido_em), "checklist_total": len(t.checklist),
        "carga": round(servico.carga(t, agora), 1), "ordem": t.ordem, "atualizado_em": _utc(t.atualizado_em),
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
              por=chegada[s][1] if s in chegada and i <= atual else None, atual=i == atual, alcancada=i <= atual)
        for i, s in enumerate(ordem)
    ]


def _detalhe(sessao: Session, usuario: Usuario, t: Tarefa) -> TarefaDetalhe:
    agora = agora_utc()
    base = _resumo(sessao, t, _prorrogacoes(sessao, [t.id]), agora)
    pessoas = [p for p in (_pessoa(sessao, i) for i in sorted(servico.envolvidos(t))) if p]
    em_andamento = t.segundos_em_andamento + (int((agora - servico._comparavel(t.em_andamento_desde)).total_seconds()) if t.em_andamento_desde else 0)
    return TarefaDetalhe(
        **base, descricao=t.descricao, criado_por=_pessoa(sessao, t.criado_por_id), criado_em=_utc(t.criado_em), pessoas=pessoas,
        checklist=[ItemChecklist(id=i.id, texto=i.texto, concluido=i.concluido_em is not None) for i in t.checklist],
        etapas=_etapas(sessao, t), segundos_em_andamento=em_andamento, versao=t.versao, acoes=servico.acoes(sessao, usuario, t),
    )


def _filtrar(tarefas: list[Tarefa], status_: list[str], prioridade: str | None, marcador_id: uuid.UUID | None, busca: str,
             responsavel_id: int | None) -> list[Tarefa]:
    termo = busca.strip().lower()
    resultado = []
    for t in tarefas:
        if status_ and t.status not in status_:
            continue
        if prioridade and t.prioridade != prioridade:
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
            agora: datetime) -> tuple[list[Tarefa], Contexto, dict]:
    """Tarefas, contexto e indicadores de um escopo (minhas, equipe ou pessoa), com as permissões conferidas."""
    with _traduzir():
        if escopo == "equipe":
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
                                lider=usuario.id != pessoa.id)
            ind = servico.indicadores(tarefas, agora, pessoa.id)
        else:
            tarefas = servico.minhas(sessao, usuario)
            contexto = Contexto(tipo="minhas", titulo="Minhas tarefas", lider=bool(servico.equipes_lideradas(sessao, usuario)))
            ind = servico.indicadores(tarefas, agora, usuario.id)
    return tarefas, contexto, ind


# ---------------------------------------------------------------------------------------------
# Listas
# ---------------------------------------------------------------------------------------------

@roteador.get("", response_model=ListaTarefas, summary="Listar tarefas (minhas, de uma equipe ou de uma pessoa)",
              description="`escopo`: `minhas` (padrão: envolvida ou criada por mim), `equipe` (`equipe_id`; a liderança vê também as equipes "
                          "abaixo) ou `pessoa` (`login`; a própria pessoa, a liderança das equipes dela ou o SuperRoot). Filtros: `status` "
                          "(repetível), `prioridade`, `marcador_id`, `responsavel_id` e `busca` (título, descrição ou número). Os indicadores "
                          "são do escopo inteiro (sem os filtros).", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Equipe ou pessoa")})
def listar(escopo: str = Query("minhas", pattern="^(minhas|equipe|pessoa)$"), equipe_id: uuid.UUID | None = None, login: str | None = None,
           status_: list[str] = Query([], alias="status"), prioridade: str | None = None, marcador_id: uuid.UUID | None = None,
           responsavel_id: int | None = None, busca: str = Query("", max_length=200), sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> ListaTarefas:
    agora = agora_utc()
    tarefas, contexto, ind = _escopo(sessao, usuario, escopo, equipe_id, login, agora)
    filtradas = _filtrar(tarefas, status_, prioridade, marcador_id, busca, responsavel_id)
    prorrogacoes = _prorrogacoes(sessao, [t.id for t in filtradas])
    return ListaTarefas(contexto=contexto, indicadores=Indicadores(**ind), itens=[TarefaResumo(**_resumo(sessao, t, prorrogacoes, agora)) for t in filtradas])


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


@roteador.get("/equipes/{equipe_id}/marcadores", response_model=list[MarcadorLeitura], summary="Marcadores da equipe",
              description="Marcadores da equipe e os globais (sem equipe).")
def listar_marcadores(equipe_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> list[MarcadorLeitura]:
    lista = sessao.scalars(select(MarcadorTarefa).where((MarcadorTarefa.equipe_id == equipe_id) | MarcadorTarefa.equipe_id.is_(None)).order_by(MarcadorTarefa.nome))
    return [MarcadorLeitura.model_validate(m, from_attributes=True) for m in lista]


@roteador.post("/equipes/{equipe_id}/marcadores", response_model=MarcadorLeitura, status_code=status.HTTP_201_CREATED,
               summary="Criar marcador da equipe", description="Só a liderança da equipe.", responses={**SEM_PERMISSAO, **CONFLITO})
def criar_marcador(equipe_id: uuid.UUID, dados: GravacaoMarcador, sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> MarcadorLeitura:
    with _traduzir():
        return MarcadorLeitura.model_validate(servico.salvar_marcador(sessao, usuario, equipe_id, dados.nome, dados.cor), from_attributes=True)


@roteador.delete("/marcadores/{marcador_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir marcador",
                 description="Só a liderança da equipe do marcador (globais: SuperRoot).", responses={**SEM_PERMISSAO})
def excluir_marcador(marcador_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico.excluir_marcador(sessao, usuario, marcador_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Tarefa
# ---------------------------------------------------------------------------------------------

@roteador.post("", response_model=TarefaDetalhe, status_code=status.HTTP_201_CREATED, summary="Criar tarefa",
               description="Responsável padrão: quem cadastra. Numa equipe, responsável e participantes são da equipe (a liderança pode incluir "
                           "outras pessoas). Os envolvidos recebem aviso com e-mail.", responses={**SEM_PERMISSAO, **INVALIDO})
def criar(dados: NovaTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.criar(sessao, usuario, servico.DadosTarefa(
            titulo=dados.titulo, descricao=dados.descricao, prazo=dados.prazo, prioridade=dados.prioridade, equipe_id=dados.equipe_id,
            responsavel_id=dados.responsavel_id, participantes_ids=tuple(dados.participantes_ids), marcadores_ids=tuple(dados.marcadores_ids)))
    return _detalhe(sessao, usuario, t)


@roteador.get("/{numero}", response_model=TarefaDetalhe, summary="Detalhe da tarefa",
              description="Com as etapas do pipeline e as ações permitidas ao usuário. Sem permissão: 404.", responses={**NAO_ENCONTRADA})
def detalhar(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        return _detalhe(sessao, usuario, servico.obter(sessao, usuario, numero))


@roteador.put("/{numero}", response_model=TarefaDetalhe, summary="Editar tarefa",
              description="Título, descrição, prioridade, participantes e marcadores (o prazo tem rota própria). `versao` evita sobrescrever "
                          "alteração de outra pessoa (409).", responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def editar(numero: int, dados: EdicaoTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.editar(sessao, usuario, servico.obter(sessao, usuario, numero), dados.titulo, dados.descricao, dados.prioridade,
                           tuple(dados.participantes_ids), tuple(dados.marcadores_ids), dados.versao)
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
        t = servico.mover(sessao, usuario, servico.obter(sessao, usuario, numero), dados.acao, dados.texto, dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/transferir", response_model=TarefaDetalhe, summary="Transferir tarefa",
               description="Para membro da equipe (a liderança, para qualquer usuário ativo), com justificativa e novo prazo opcional.",
               responses={**SEM_PERMISSAO, **INVALIDO, **CONFLITO, **NAO_ENCONTRADA})
def transferir(numero: int, dados: Transferencia, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> TarefaDetalhe:
    with _traduzir():
        t = servico.transferir(sessao, usuario, servico.obter(sessao, usuario, numero), dados.para_id, dados.justificativa, dados.novo_prazo, dados.versao)
    return _detalhe(sessao, usuario, t)


@roteador.post("/{numero}/comentarios", response_model=EventoLeitura, status_code=status.HTTP_201_CREATED, summary="Comentar e anexar",
               description="`multipart/form-data`: `texto` e/ou até 5 `arquivos` (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG). Os envolvidos "
                           "recebem aviso. Vale também para tarefa concluída.", responses={**SEM_PERMISSAO, **INVALIDO, **NAO_ENCONTRADA})
async def comentar(numero: int, texto: str = Form(""), arquivos: list[UploadFile] = File(default_factory=list), sessao: Session = Depends(obter_sessao),
                   usuario: Usuario = Depends(obter_usuario_atual)) -> EventoLeitura:
    with _traduzir():
        t = servico.obter(sessao, usuario, numero)
        evento = servico.comentar(sessao, usuario, t, texto, [(a.filename or "arquivo", a.file) for a in arquivos if a.filename])
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
