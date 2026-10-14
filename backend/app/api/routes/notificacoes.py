# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas das notificações (caixa de notificações, envio e acompanhamento).
"""Notificações (`/api/notificacoes`): caixa de entrada de cada usuário, envio avulso e acompanhamento.

Todas as rotas exigem apenas login (perfil em dia). Cada usuário só enxerga as próprias entregas; ids de
entregas alheias respondem 404. O envio para setores exige SuperRoot ou ACL `notificacoes-setores` ≥
CONTROLE_TOTAL. Nenhuma mensagem bloqueia a navegação.
"""

import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import FabricaSessao, obter_sessao
from app.core.erros import ErroApi
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.usuario import Usuario
from app.schemas.notificacoes import (
    Destinatarios,
    EntregaDetalhe,
    EntregaResumo,
    EnviadaDetalhe,
    EnviadaResumo,
    EnvioMensagem,
    OpcaoDestinatario,
    PaginaEntregas,
    LoteMensagens,
    PaginaEnviadas,
    PreviaMensagem,
    RespostaEnvio,
    RespostaLembrete,
    RespostaPrevia,
    RespostaLote,
    ResumoCaixa,
    SituacaoDestinatario,
)
from app.services import notificacoes as servico
from app.services.notificacoes import despacho

roteador = APIRouter(prefix="/notificacoes", tags=["Notificações"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADA = resposta_nao_encontrado("Notificacao")


@contextmanager
def _traduzir():
    """Converte `ErroNotificacao` no erro padrão da API ({detalhe, codigo})."""
    try:
        yield
    except servico.ErroNotificacao as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _estado(e: EntregaNotificacao) -> str:
    if e.ciente_em:
        return "ciente"
    if e.encerrada_em:
        return "encerrada"
    return "visualizada" if e.visualizada_em else "nao_visualizada"


def _resumo(e: EntregaNotificacao) -> EntregaResumo:
    m = e.notificacao
    return EntregaResumo(
        id=e.id, assunto=e.assunto_copia, prioridade=m.prioridade, categoria=m.categoria, autor_nome=m.autor_nome, origem=m.origem,
        link=m.link, entregue_em=e.entregue_em, visualizada_em=e.visualizada_em, ciente_em=e.ciente_em, encerrada_em=e.encerrada_em,
        estado=_estado(e), pendente=servico.pendente(e), evento=m.evento, alertar_desktop=e.canal_desktop,
        contrato_id=m.contrato_id, tarefa_id=m.tarefa_id,
    )


def _enviar_lembretes(entregas_ids: list[uuid.UUID]) -> None:
    """Segundo plano: lembrete por e-mail de cada entrega pendente (só para quem ligou o e-mail do lembrete de ciência)."""
    with FabricaSessao() as sessao:
        for entrega_id in entregas_ids:
            entrega = sessao.get(EntregaNotificacao, entrega_id)
            if entrega is not None:
                despacho.enviar_lembrete_ciencia(sessao, entrega)


def _detalhe(e: EntregaNotificacao) -> EntregaDetalhe:
    return EntregaDetalhe(**_resumo(e).model_dump(), corpo=e.corpo_copia,
                          abrir_em_janela=e.notificacao.abrir_em_janela)


def _enviada(m: Notificacao) -> EnviadaResumo:
    return EnviadaResumo(
        id=m.id, assunto=m.assunto, prioridade=m.prioridade, categoria=m.categoria, publicada_em=m.publicada_em, expira_em=m.expira_em,
        destinatarios=len(m.entregas),
        visualizadas=sum(1 for e in m.entregas if e.visualizada_em), cientes=sum(1 for e in m.entregas if e.ciente_em),
    )


# Pasta com o instalador do SGI SPI Alertas (cliente Windows), ao lado de `backend/`
PASTA_CLIENTE_WINDOWS = Path(__file__).resolve().parents[4] / "client"


def _instalador_mais_novo() -> Path | None:
    """O MSI `SgiSpiAlertas-<versão>.msi` de maior versão (ex.: 1.10.0 vence 1.9.0), ou None se não houver nenhum."""
    def versao(arquivo: Path) -> tuple[int, ...]:
        return tuple(int(n) for n in re.findall(r"\d+", arquivo.stem.removeprefix("SgiSpiAlertas-")))

    instaladores = [a for a in PASTA_CLIENTE_WINDOWS.glob("SgiSpiAlertas-*.msi") if a.is_file()]
    return max(instaladores, key=versao, default=None)


@roteador.get("/cliente-windows", response_class=FileResponse, summary="Baixar o SGI SPI Alertas (instalador para Windows)",
              description="Entrega o instalador `.msi` mais recente do aplicativo de bandeja do Windows que mostra os avisos (canal Desktop). Qualquer usuário autenticado. "
                          "`404` se o instalador não estiver publicado no servidor.",
              responses={200: {"content": {"application/x-msi": {}}, "description": "O instalador."}, **resposta_nao_encontrado("Instalador")})
def baixar_cliente_windows(usuario: Usuario = Depends(obter_usuario_atual)) -> FileResponse:
    instalador = _instalador_mais_novo()
    if instalador is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "O instalador do SGI Alertas ainda não está disponível neste servidor.", "nao_encontrado")
    return FileResponse(instalador, media_type="application/x-msi", filename=instalador.name)


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


@roteador.get("/enviadas/{notificacao_id}", response_model=EnviadaDetalhe, summary="Acompanhar uma mensagem enviada",
              description="Situação de cada destinatário (visualizou, ciente, e-mail). Só o autor ou o SuperRoot.",
              responses=NAO_ENCONTRADA)
def detalhar_enviada(notificacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> EnviadaDetalhe:
    with _traduzir():
        mensagem, usuarios = servico.enviada(sessao, usuario, notificacao_id)
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


@roteador.post("/enviadas/{notificacao_id}/lembrar", response_model=RespostaLembrete, summary="Lembrar quem não deu ciência",
               description="Envia um lembrete por e-mail a cada destinatário ainda sem ciência que ligou o e-mail em \"Lembrete de ciência pendente\" nas Preferências. Só o autor ou o SuperRoot.",
               responses={**INVALIDO, **NAO_ENCONTRADA})
def lembrar(notificacao_id: uuid.UUID, tarefas: BackgroundTasks, sessao: Session = Depends(obter_sessao),
            usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaLembrete:
    with _traduzir():
        pendentes = servico.lembrar_pendentes(sessao, usuario, notificacao_id)
    tarefas.add_task(_enviar_lembretes, pendentes)
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
               description="Notificacao avulsa para usuários e (com permissão) setores. Setores viram a lista de membros e ninguém recebe "
               "duas vezes; só usuários ativos recebem. Cada destinatário recebe pelos canais que ligou em Preferências (a caixa recebe sempre).",
               responses={**INVALIDO, status.HTTP_403_FORBIDDEN: {"description": "Envio para setores sem permissão (`acl_negado`)."}})
def enviar(dados: EnvioMensagem, sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaEnvio:
    with _traduzir():
        mensagem = servico.enviar_avulsa(sessao, servico.DadosEnvio(**dados.model_dump()), usuario)
    return RespostaEnvio(notificacao_id=mensagem.id, destinatarios=len(mensagem.entregas))


@roteador.post("/previa", response_model=RespostaPrevia, summary="Prévia da mensagem no layout do e-mail",
               description="Devolve o HTML do e-mail oficial (o mesmo do changelog) com o texto formatado: `## título`, `- lista` e `**negrito**`. "
               "A caixa de notificações e a tela de nova mensagem exibem esse HTML.", responses=INVALIDO)
def previa(dados: PreviaMensagem, usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaPrevia:
    autor = dados.autor_nome or usuario.nome_completo or usuario.login
    return RespostaPrevia(html=servico.previa_mensagem(dados.assunto.strip() or "(sem assunto)", dados.corpo or " ", autor, dados.link))


@roteador.post("/lote", response_model=RespostaLote, summary="Marcar várias mensagens",
               description="Marca as mensagens selecionadas da própria caixa como lidas, não lidas ou cientes. Ids de outras pessoas são ignorados.",
               responses=INVALIDO)
def marcar_lote(dados: LoteMensagens, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaLote:
    return RespostaLote(atualizadas=servico.marcar_em_lote(sessao, usuario, dados.ids, dados.acao))


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
