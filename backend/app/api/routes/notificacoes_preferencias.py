# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas das preferências de notificação (canais por evento, navegador, testar, silenciar e obrigatórias).
"""Preferências das Notificações (`/api/notificacoes/preferencias` e vizinhas).

Estas rotas ficam num roteador à parte, incluído **antes** do da caixa: caminhos de um segmento como `/preferencias` não podem cair
em `/{entrega_id}`.
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, exigir_conta_root, obter_usuario_atual
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, VALIDACAO, resposta_nao_encontrado
from app.core.banco import FabricaSessao, agora_utc, obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.contratos import Contrato
from app.models.notificacao import EntregaNotificacao, Notificacao
from app.models.notificacao_preferencias import InscricaoNavegador, NotificacaoObrigatoria
from app.models.setor import Setor
from app.models.tarefas import Tarefa
from app.models.usuario import Usuario
from app.schemas.notificacoes_preferencias import (
    CienciaPorToken, GravacaoPreferencias, InscricaoNavegadorEntrada, LinhaEntrega, ObrigatoriaEntrada, ObrigatoriaLeitura, PainelEntregas,
    PedidoSilenciar, PreferenciasLeitura, RemocaoInscricao, RespostaTeste, Silenciado, SituacaoNavegador, TesteCanal,
)
from app.services import notificacoes as servico
from app.services.notificacoes import despacho, navegador, preferencias
from app.services.notificacoes.catalogo import EVENTOS

roteador = APIRouter(prefix="/notificacoes", tags=["Notificações: preferências"], responses=RESPOSTAS_AUTENTICADAS)

obrigatorias_acl = exigir_acl("notificacoes-obrigatorias", NivelAcl.CONTROLE_TOTAL)
NAO_ENCONTRADA = resposta_nao_encontrado("Item não encontrado.")


def _traduzir(erro: Exception) -> ErroApi:
    return ErroApi(getattr(erro, "status", 422), str(erro), getattr(erro, "codigo", "validacao"))


def _leitura(sessao: Session, usuario: Usuario) -> PreferenciasLeitura:
    return PreferenciasLeitura(**preferencias.montar(sessao, usuario, navegador.situacao(sessao, usuario)))


@roteador.get("/preferencias", response_model=PreferenciasLeitura, summary="Minhas preferências de notificação",
              description="O catálogo de eventos agrupado por módulo, com o que está ligado em cada canal (e-mail, navegador e desktop; a caixa recebe sempre), "
              "a configuração (frequência do e-mail e não perturbe), a situação do navegador (chave pública VAPID e quantos navegadores estão inscritos) e a lista de silenciados. "
              "Tudo começa desmarcado. Canais obrigatórios aparecem ligados e travados.")
def ler_preferencias(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciasLeitura:
    return _leitura(sessao, usuario)


@roteador.put("/preferencias", response_model=PreferenciasLeitura, summary="Salvar minhas preferências de notificação", responses=VALIDACAO,
              description="Substitui tudo de uma vez (canais por evento e configuração). Canal fora dos `canais` disponíveis do evento, evento desconhecido, frequência ou horário inválidos: `422`. "
              "Os canais obrigatórios não saem por aqui: continuam ligados.")
def salvar_preferencias(dados: GravacaoPreferencias, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciasLeitura:
    try:
        preferencias.salvar(sessao, usuario, {e: list(c) for e, c in dados.canais.items()}, dados.configuracao.model_dump())
    except preferencias.ErroPreferencias as erro:
        raise _traduzir(erro) from erro
    return _leitura(sessao, usuario)


@roteador.post("/navegador/inscricoes", response_model=SituacaoNavegador, status_code=status.HTTP_201_CREATED, summary="Inscrever este navegador",
               description="Registra (ou atualiza, pelo `endpoint`) a inscrição Web Push deste navegador para o usuário logado. Sem as chaves VAPID no servidor: `409 navegador_indisponivel`.",
               responses={**VALIDACAO, status.HTTP_409_CONFLICT: {"description": "O servidor não tem as chaves VAPID (`navegador_indisponivel`)."}})
def inscrever_navegador(dados: InscricaoNavegadorEntrada, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> SituacaoNavegador:
    if not navegador.configurado():
        raise ErroApi(status.HTTP_409_CONFLICT, "As notificações do navegador não estão configuradas no servidor.", "navegador_indisponivel")
    navegador.inscrever(sessao, usuario, dados.endpoint, dados.p256dh, dados.auth, dados.rotulo)
    return SituacaoNavegador(**navegador.situacao(sessao, usuario))


@roteador.post("/navegador/inscricoes/remover", response_model=SituacaoNavegador, summary="Remover este navegador",
               description="Cancela a inscrição Web Push do `endpoint` informado (só do próprio usuário; sem inscrição, não faz nada).", responses=VALIDACAO)
def remover_navegador(dados: RemocaoInscricao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> SituacaoNavegador:
    navegador.remover(sessao, usuario, dados.endpoint)
    return SituacaoNavegador(**navegador.situacao(sessao, usuario))


@roteador.post("/testar", response_model=RespostaTeste, summary="Testar um canal",
               description="Envia uma notificação de teste ao próprio usuário pelo canal escolhido: e-mail (servidor SMTP ativo e e-mail no perfil), navegador (pop-up nos navegadores inscritos) "
               "ou desktop (uma entrega de teste que o cliente Windows alerta e que expira sozinha em 3 minutos). Resultado em `enviado` e `detalhe` (não é erro HTTP quando o canal não está pronto).",
               responses=VALIDACAO)
def testar(dados: TesteCanal, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> RespostaTeste:
    assunto, corpo = "Teste de notificação", "Se você está vendo isto, este canal está funcionando."
    if dados.canal == "email":
        ok, erro = despacho.enviar_teste_email(sessao, usuario, assunto, corpo)
        return RespostaTeste(enviado=ok, detalhe="E-mail enviado." if ok else (erro or "Não foi possível enviar o e-mail."))
    if dados.canal == "navegador":
        enviados, erro = navegador.enviar(sessao, usuario.id, navegador.montar_payload(uuid.uuid4(), assunto, corpo, "/notificacoes"))
        return RespostaTeste(enviado=enviados > 0, detalhe=f"Enviado a {enviados} navegador(es)." if enviados else (erro or "Nenhum navegador inscrito."))
    notificacao = servico.notificar(
        sessao, [usuario.id], assunto, corpo, chave=f"teste-desktop:{usuario.id}:{uuid.uuid4()}", evento="sistema.teste", link="/notificacoes",
        abrir_em_janela=False,
    )
    notificacao.expira_em = agora_utc() + timedelta(minutes=3)
    for entrega in notificacao.entregas:
        entrega.canal_desktop = True
    sessao.commit()
    return RespostaTeste(enviado=True, detalhe="Teste criado: o SGI Alertas (Windows) mostra o alerta em até 1 minuto; ele some sozinho em 3 minutos.")


@roteador.post("/silenciar", response_model=Silenciado, status_code=status.HTTP_201_CREATED, summary="Silenciar um contrato ou tarefa",
               description="A partir de uma notificação da própria caixa ligada a um contrato ou tarefa: não avisar mais por e-mail, navegador nem desktop (a caixa continua recebendo). Idempotente.",
               responses={**INVALIDO, **NAO_ENCONTRADA})
def silenciar(dados: PedidoSilenciar, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Silenciado:
    entrega = sessao.scalar(select(EntregaNotificacao).where(EntregaNotificacao.id == dados.entrega_id, EntregaNotificacao.destinatario_id == usuario.id))
    if entrega is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Notificação não encontrada.", "nao_encontrado")
    n = entrega.notificacao
    candidatos = [t for t, alvo in (("contrato", n.contrato_id), ("tarefa", n.tarefa_id)) if alvo is not None and dados.tipo in (None, t)]
    if len(candidatos) != 1:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Esta notificação não está ligada a um contrato ou tarefa (ou é preciso informar qual silenciar).", "invalido")
    tipo = candidatos[0]
    alvo = n.contrato_id if tipo == "contrato" else n.tarefa_id
    if tipo == "contrato":
        contrato = sessao.get(Contrato, alvo)
        rotulo = f"Contrato {contrato.numero}" + (f" – {contrato.apelido}" if contrato and contrato.apelido else "") if contrato else "Contrato"
    else:
        tarefa = sessao.get(Tarefa, alvo)
        rotulo = f"Tarefa #{tarefa.numero} {tarefa.titulo}" if tarefa else "Tarefa"
    linha = preferencias.silenciar(sessao, usuario, tipo, alvo, rotulo)
    return Silenciado(id=linha.id, tipo=linha.tipo, alvo_id=linha.alvo_id, rotulo=linha.rotulo)


@roteador.delete("/silenciados/{silenciado_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Voltar a avisar",
                 description="Tira o contrato ou tarefa da lista de silenciados do próprio usuário.", responses=NAO_ENCONTRADA)
def voltar_a_avisar(silenciado_id: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    try:
        preferencias.voltar_a_avisar(sessao, usuario, silenciado_id)
    except preferencias.ErroPreferencias as erro:
        raise _traduzir(erro) from erro
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/ciencia-por-token", status_code=status.HTTP_200_OK, summary="Ciência pelo botão do pop-up",
               description="Usada pelo service worker do navegador (sem sessão): o `token` do payload do pop-up vale só para dar ciência àquela entrega, por 7 dias. "
               "Se a entrega já tem ciência, não faz nada (`registrada=false`). Token inválido ou expirado: `401`.",
               responses={status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido ou expirado (`token_invalido`)."}})
def ciencia_por_token(dados: CienciaPorToken, sessao: Session = Depends(obter_sessao)) -> dict:
    entrega_id = navegador.validar_token_ciencia(dados.token)
    entrega = sessao.get(EntregaNotificacao, entrega_id) if entrega_id else None
    if entrega is None:
        raise ErroApi(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado.", "token_invalido")
    if entrega.ciente_em is not None:
        return {"registrada": False}
    usuario = sessao.get(Usuario, entrega.destinatario_id)
    servico.registrar_ciencia(sessao, usuario, entrega.id)
    return {"registrada": True}


# --- Administração (root e quem tiver CONTROLE_TOTAL em `notificacoes-obrigatorias`) ---------------------------------

def _obrigatoria(sessao: Session, o: NotificacaoObrigatoria) -> ObrigatoriaLeitura:
    setor = sessao.get(Setor, o.setor_id) if o.setor_id else None
    alvo = sessao.get(Usuario, o.usuario_id) if o.usuario_id else None
    return ObrigatoriaLeitura(
        id=o.id, evento=o.evento, evento_rotulo=EVENTOS[o.evento].rotulo if o.evento in EVENTOS else o.evento, canal=o.canal, setor_id=o.setor_id,
        setor_nome=setor.nome if setor else None, usuario_id=o.usuario_id, usuario_nome=(alvo.nome_completo or alvo.login) if alvo else None, criada_em=o.criada_em,
    )


@roteador.get("/obrigatorias", response_model=list[ObrigatoriaLeitura], summary="Notificações obrigatórias",
              description="Eventos e canais impostos pela administração a um setor ou usuário. Exige CONTROLE_TOTAL no recurso `notificacoes-obrigatorias` (ou SuperRoot). A lista começa vazia.")
def listar_obrigatorias(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obrigatorias_acl)) -> list[ObrigatoriaLeitura]:
    return [_obrigatoria(sessao, o) for o in sessao.scalars(select(NotificacaoObrigatoria).order_by(NotificacaoObrigatoria.id))]


@roteador.post("/obrigatorias", response_model=ObrigatoriaLeitura, status_code=status.HTTP_201_CREATED, summary="Tornar um canal obrigatório",
               description="Evento + canal para **um** setor ou **um** usuário (nunca os dois). Quem recebe vê o canal ligado e travado (\"definida pela administração\"). Repetir a mesma regra devolve a existente.",
               responses=VALIDACAO)
def criar_obrigatoria(dados: ObrigatoriaEntrada, sessao: Session = Depends(obter_sessao), admin: Usuario = Depends(obrigatorias_acl)) -> ObrigatoriaLeitura:
    if dados.evento not in EVENTOS or dados.canal not in EVENTOS[dados.evento].canais_disponiveis:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Evento desconhecido ou sem este canal.", "validacao")
    if (dados.setor_id is None) == (dados.usuario_id is None):
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe o setor ou o usuário (um só).", "validacao")
    if dados.setor_id is not None and sessao.get(Setor, dados.setor_id) is None:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Setor não encontrado.", "validacao")
    if dados.usuario_id is not None and sessao.get(Usuario, dados.usuario_id) is None:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Usuário não encontrado.", "validacao")
    existente = sessao.scalar(select(NotificacaoObrigatoria).where(
        NotificacaoObrigatoria.evento == dados.evento, NotificacaoObrigatoria.canal == dados.canal,
        NotificacaoObrigatoria.setor_id == dados.setor_id if dados.setor_id is not None else NotificacaoObrigatoria.usuario_id == dados.usuario_id))
    if existente is None:
        existente = NotificacaoObrigatoria(evento=dados.evento, canal=dados.canal, setor_id=dados.setor_id, usuario_id=dados.usuario_id, criada_por_id=admin.id)
        sessao.add(existente)
        sessao.commit()
    return _obrigatoria(sessao, existente)


@roteador.delete("/obrigatorias/{obrigatoria_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remover uma obrigatoriedade",
                 description="Exige CONTROLE_TOTAL no recurso `notificacoes-obrigatorias` (ou SuperRoot). O canal volta a depender só da escolha de cada pessoa.", responses=NAO_ENCONTRADA)
def remover_obrigatoria(obrigatoria_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obrigatorias_acl)) -> Response:
    linha = sessao.get(NotificacaoObrigatoria, obrigatoria_id)
    if linha is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Regra não encontrada.", "nao_encontrado")
    sessao.delete(linha)
    sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/painel-entregas", response_model=PainelEntregas, summary="Painel de entregas (e-mail e navegador)",
              description="Só a conta root. Quantas notificações saíram e quantas falharam, por canal, nos últimos `dias`; as últimas mensagens de erro e as inscrições do navegador com falhas seguidas.")
def painel_entregas(dias: int = Query(7, ge=1, le=90), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(exigir_conta_root)) -> PainelEntregas:
    desde = agora_utc() - timedelta(days=dias)
    por_canal = []
    for canal, enviado, ok in (("email", EntregaNotificacao.email_enviado_em, EntregaNotificacao.email_ok), ("navegador", EntregaNotificacao.navegador_enviado_em, EntregaNotificacao.navegador_ok)):
        total_ok = sessao.scalar(select(func.count()).select_from(EntregaNotificacao).where(enviado >= desde, ok.is_(True))) or 0
        total_falha = sessao.scalar(select(func.count()).select_from(EntregaNotificacao).where(enviado >= desde, ok.is_(False))) or 0
        por_canal.append(LinhaEntrega(canal=canal, enviadas=total_ok, falhas=total_falha))
    erros: list[str] = []
    for coluna, enviado, ok in ((EntregaNotificacao.email_erro, EntregaNotificacao.email_enviado_em, EntregaNotificacao.email_ok), (EntregaNotificacao.navegador_erro, EntregaNotificacao.navegador_enviado_em, EntregaNotificacao.navegador_ok)):
        erros += [e for e in sessao.scalars(select(coluna).where(enviado >= desde, ok.is_(False), coluna.is_not(None)).order_by(enviado.desc()).limit(20)) if e]
    return PainelEntregas(
        dias=dias, por_canal=por_canal, ultimas_falhas=erros[:20],
        inscricoes_total=sessao.scalar(select(func.count()).select_from(InscricaoNavegador)) or 0,
        inscricoes_com_falhas=sessao.scalar(select(func.count()).select_from(InscricaoNavegador).where(InscricaoNavegador.falhas_seguidas >= 3)) or 0,
    )
