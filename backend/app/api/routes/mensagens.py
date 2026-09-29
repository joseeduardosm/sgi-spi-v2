# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da mensageria (caixa de mensagens, envio e acompanhamento).
"""Mensageria (`/api/mensagens`): caixa de entrada de cada usuário, envio avulso e acompanhamento.

Todas as rotas exigem apenas login (perfil em dia). Cada usuário só enxerga as próprias entregas; ids de
entregas alheias respondem 404. O envio para setores exige SuperRoot ou ACL `mensageria-setores` ≥
CONTROLE_TOTAL. Nenhuma mensagem bloqueia a navegação.
"""

import uuid
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.usuario import Usuario
from app.schemas.mensagens import (
    Destinatarios,
    EntregaDetalhe,
    EntregaResumo,
    EnviadaDetalhe,
    EnviadaResumo,
    EnvioMensagem,
    OpcaoDestinatario,
    PaginaEntregas,
    PaginaEnviadas,
    RespostaEnvio,
    RespostaLembrete,
    ResumoCaixa,
    SituacaoDestinatario,
)
from app.services import servico_mensagens as servico

roteador = APIRouter(prefix="/mensagens", tags=["Mensageria"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADA = resposta_nao_encontrado("Mensagem")


@contextmanager
def _traduzir():
    """Converte `ErroMensagem` no erro padrão da API ({detalhe, codigo})."""
    try:
        yield
    except servico.ErroMensagem as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _estado(e: EntregaMensagem) -> str:
    if e.ciente_em:
        return "ciente"
    if e.encerrada_em:
        return "encerrada"
    return "visualizada" if e.visualizada_em else "nao_visualizada"


def _resumo(e: EntregaMensagem) -> EntregaResumo:
    m = e.mensagem
    return EntregaResumo(
        id=e.id, assunto=e.assunto_copia, prioridade=m.prioridade, categoria=m.categoria, autor_nome=m.autor_nome, origem=m.origem,
        link=m.link, entregue_em=e.entregue_em, visualizada_em=e.visualizada_em, ciente_em=e.ciente_em, encerrada_em=e.encerrada_em,
        estado=_estado(e), pendente=servico.pendente(e),
    )


def _detalhe(e: EntregaMensagem) -> EntregaDetalhe:
    return EntregaDetalhe(**_resumo(e).model_dump(), corpo=e.corpo_copia, contrato_id=e.mensagem.contrato_id,
                          abrir_em_janela=e.mensagem.abrir_em_janela)


def _enviada(m: Mensagem) -> EnviadaResumo:
    return EnviadaResumo(
        id=m.id, assunto=m.assunto, prioridade=m.prioridade, categoria=m.categoria, publicada_em=m.publicada_em, expira_em=m.expira_em,
        enviar_email=m.enviar_email, destinatarios=len(m.entregas),
        visualizadas=sum(1 for e in m.entregas if e.visualizada_em), cientes=sum(1 for e in m.entregas if e.ciente_em),
    )


@roteador.get("/resumo", response_model=ResumoCaixa, summary="Resumo da caixa (sino)",
              description="Pendentes (sem ciência e sem encerramento), não lidas e a próxima mensagem a abrir em janela.")
def resumo(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> ResumoCaixa:
    pendentes, nao_lidas, janela = servico.resumo(sessao, usuario)
    return ResumoCaixa(pendentes=pendentes, nao_lidas=nao_lidas, janela=_detalhe(janela) if janela else None)


@roteador.get("/destinatarios", response_model=Destinatarios, summary="Destinatários disponíveis",
              description="Usuários ativos e, para quem pode enviar para setores, os setores ativos.")
def destinatarios(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Destinatarios:
    usuarios, setores, pode = servico.destinatarios_disponiveis(sessao, usuario)
    return Destinatarios(
        usuarios=[OpcaoDestinatario(id=u.id, nome=u.nome_completo or u.login, detalhe=" · ".join(x for x in (u.login, u.departamento) if x))
                  for u in usuarios],
        setores=[OpcaoDestinatario(id=s.id, nome=s.nome) for s in setores],
        pode_enviar_setores=pode,
    )


@roteador.get("/enviadas", response_model=PaginaEnviadas, summary="Mensagens enviadas por mim",
              description="Mensagens avulsas do usuário com os números de visualização e ciência.")
def listar_enviadas(pagina: int = Query(1, ge=1), tamanho_pagina: int = Query(20, ge=1, le=100), sessao: Session = Depends(obter_sessao),
                    usuario: Usuario = Depends(obter_usuario_atual)) -> PaginaEnviadas:
    itens, total = servico.enviadas(sessao, usuario, pagina, tamanho_pagina)
    return PaginaEnviadas(itens=[_enviada(m) for m in itens], total=total, pagina=pagina, tamanho_pagina=tamanho_pagina)


@roteador.get("/enviadas/{mensagem_id}", response_model=EnviadaDetalhe, summary="Acompanhar uma mensagem enviada",
              description="Situação de cada destinatário (visualizou, ciente, e-mail). Só o autor ou o SuperRoot.",
              responses=NAO_ENCONTRADA)
def detalhar_enviada(mensagem_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EnviadaDetalhe:
    with _traduzir():
        mensagem, usuarios = servico.enviada(sessao, usuario, mensagem_id)
    situacao = [
        SituacaoDestinatario(
            usuario_id=e.destinatario_id, nome=(usuarios[e.destinatario_id].nome_completo or usuarios[e.destinatario_id].login)
            if e.destinatario_id in usuarios else f"Usuário {e.destinatario_id}",
            visualizada_em=e.visualizada_em, ciente_em=e.ciente_em, encerrada_em=e.encerrada_em,
            email_enviado_em=e.email_enviado_em, email_ok=e.email_ok, email_erro=e.email_erro,
        )
        for e in mensagem.entregas
    ]
    situacao.sort(key=lambda s: (s.ciente_em is not None, s.nome.lower()))
    return EnviadaDetalhe(**_enviada(mensagem).model_dump(), corpo=mensagem.corpo, link=mensagem.link, situacao=situacao)


@roteador.post("/enviadas/{mensagem_id}/lembrar", response_model=RespostaLembrete, summary="Lembrar quem não deu ciência",
               description="Envia um e-mail de lembrete a cada destinatário ainda sem ciência. Só o autor ou o SuperRoot.",
               responses={**INVALIDO, **NAO_ENCONTRADA})
def lembrar(mensagem_id: uuid.UUID, tarefas: BackgroundTasks, sessao: Session = Depends(obter_sessao),
            usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaLembrete:
    with _traduzir():
        pendentes = servico.lembrar_pendentes(sessao, usuario, mensagem_id)
    tarefas.add_task(servico.enviar_emails, mensagem_id, pendentes, "Lembrete: ")
    return RespostaLembrete(lembrados=len(pendentes))


@roteador.get("", response_model=PaginaEntregas, summary="Caixa de entrada",
              description="Mensagens do usuário, das mais recentes para as mais antigas. `estado`: `pendentes` (padrão), `cientes` "
              "(com ciência ou encerradas) ou `todas`. A busca procura no assunto, no texto e no remetente, sem diferenciar acentos. "
              "Mensagens expiradas não aparecem.")
def listar(estado: Literal["pendentes", "cientes", "todas"] = "pendentes", busca: str = Query("", max_length=200),
           pagina: int = Query(1, ge=1), tamanho_pagina: int = Query(20, ge=1, le=100),
           sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PaginaEntregas:
    itens, total = servico.listar(sessao, usuario, estado, busca, pagina, tamanho_pagina)
    return PaginaEntregas(itens=[_resumo(e) for e in itens], total=total, pagina=pagina, tamanho_pagina=tamanho_pagina)


@roteador.post("", response_model=RespostaEnvio, status_code=status.HTTP_201_CREATED, summary="Enviar mensagem",
               description="Mensagem avulsa para usuários e (com permissão) setores. Setores viram a lista de membros e ninguém recebe "
               "duas vezes; só usuários ativos recebem. Com `enviar_email`, o e-mail sai em segundo plano.",
               responses={**INVALIDO, status.HTTP_403_FORBIDDEN: {"description": "Envio para setores sem permissão (`acl_negado`)."}})
def enviar(dados: EnvioMensagem, tarefas: BackgroundTasks, sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaEnvio:
    with _traduzir():
        mensagem = servico.enviar_avulsa(sessao, servico.DadosEnvio(**dados.model_dump()), usuario)
    if mensagem.enviar_email:
        tarefas.add_task(servico.enviar_emails, mensagem.id)
    return RespostaEnvio(mensagem_id=mensagem.id, destinatarios=len(mensagem.entregas))


@roteador.get("/{entrega_id}", response_model=EntregaDetalhe, summary="Abrir mensagem",
              description="Devolve o texto e registra a primeira visualização. Entrega de outro usuário: 404.", responses=NAO_ENCONTRADA)
def abrir(entrega_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EntregaDetalhe:
    with _traduzir():
        return _detalhe(servico.abrir(sessao, usuario, entrega_id))


@roteador.post("/{entrega_id}/ciencia", response_model=EntregaDetalhe, summary="Registrar ciência",
               description="\"Li e estou ciente\". Também marca como visualizada; repetir não muda a data.", responses=NAO_ENCONTRADA)
def registrar_ciencia(entrega_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EntregaDetalhe:
    with _traduzir():
        return _detalhe(servico.registrar_ciencia(sessao, usuario, entrega_id))
