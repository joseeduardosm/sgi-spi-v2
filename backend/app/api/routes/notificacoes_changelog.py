# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da tela Notificações do sistema (e-mail de changelog), exclusivas da conta root.
"""Rotas das Notificações (`/api/notificacoes`): só a conta root (login `LOGIN_ADMIN`) acessa.

E-mail de changelog: rascunho a partir do `CHANGELOG.md`, prévia no layout oficial, envio (a todos os usuários
ativos com e-mail ou de teste) e histórico dos envios. A caixa de notificações de cada usuário continua em
`/api/notificacoes`.
"""

import uuid

from fastapi import APIRouter, Response, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_conta_root
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.notificacoes_changelog import (
    ContagemChangelog, PedidoContagemChangelog,
    ConteudoChangelog,
    EnvioChangelogLeitura,
    OpcaoSetorChangelog,
    PedidoEnvioChangelog,
    PreviaChangelog,
    RascunhoChangelog,
)
from app.services import servico_changelog, servico_setores

roteador = APIRouter(prefix="/notificacoes", tags=["Notificações do sistema"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get("/changelog/rascunho", response_model=RascunhoChangelog, summary="Rascunho do e-mail de changelog",
              description="Assunto e texto sugeridos com as entradas do `CHANGELOG.md` posteriores ao último envio a todos "
                          "(na primeira vez, a entrada mais recente). Sem detalhes técnicos (migrações, endpoints, crases). Traz também "
                          "o total de usuários ativos e os setores disponíveis para o envio a selecionados. Só a conta root.")
def obter_rascunho(sessao: Session = Depends(obter_sessao), _root: Usuario = Depends(exigir_conta_root)) -> RascunhoChangelog:
    r = servico_changelog.rascunho(sessao)
    return RascunhoChangelog(assunto=r.assunto, corpo=r.corpo, desde=r.desde, ate=r.ate, datas=r.datas,
                             total_destinatarios=len(servico_changelog.destinatarios(sessao)), setores=_setores(sessao))


@roteador.post("/changelog/contagem", response_model=ContagemChangelog, summary="Quantos receberão o e-mail de changelog",
               description="Para a tela mostrar o número antes do envio a `selecionados`: recebe todo escolhido que está ativo e tem e-mail cadastrado, tenha ou não ligado o e-mail de \"Novidades do SGI SPI\". Só a conta root.")
def contagem(dados: PedidoContagemChangelog, sessao: Session = Depends(obter_sessao), _root: Usuario = Depends(exigir_conta_root)) -> ContagemChangelog:
    lista, _ = servico_changelog.selecionados(sessao, list(dados.usuarios_ids), list(dados.setores_ids))
    return ContagemChangelog(total=len(lista), selecionados=servico_changelog.total_selecionados(sessao, list(dados.usuarios_ids), list(dados.setores_ids)))


def _setores(sessao: Session) -> list[OpcaoSetorChangelog]:
    """Setores institucionais na ordem da hierarquia e, depois, os grupos sistêmicos em ordem alfabética."""
    institucionais = [OpcaoSetorChangelog(id=o.id, nome=o.nome, sistemico=False, nivel=o.nivel) for o in servico_setores.opcoes_departamento(sessao)]
    sistemicos = sessao.scalars(select(Setor).where(Setor.ativo.is_(True), Setor.sistemico.is_(True)).order_by(Setor.nome))
    return institucionais + [OpcaoSetorChangelog(id=s.id, nome=s.nome, sistemico=True) for s in sistemicos]


@roteador.post("/changelog/previa", response_model=PreviaChangelog, summary="Prévia do e-mail de changelog",
               description="HTML do e-mail no layout oficial (brasão, cabeçalho institucional, botão e rodapé) para o texto editado. Só a conta root.")
def previa(dados: ConteudoChangelog, _root: Usuario = Depends(exigir_conta_root)) -> PreviaChangelog:
    return PreviaChangelog(html=servico_changelog.html_previa(dados.assunto, dados.corpo))


@roteador.post("/changelog/envios", response_model=EnvioChangelogLeitura, status_code=status.HTTP_202_ACCEPTED,
               summary="Enviar o e-mail de changelog",
               description="Registra o envio e manda, em segundo plano, um e-mail por destinatário: `todos` (usuários ativos com e-mail), "
                           "`selecionados` (`usuarios_ids` e `setores_ids`; um setor inclui os membros, quem o tem como Departamento e os "
                           "setores filhos) ou `teste` (só `email_teste`). `400` se a seleção não tiver ninguém ativo com e-mail. O resultado (`enviados`, `falhas`, `concluido_em`) aparece em "
                           "`GET /changelog/envios`. Só envios a todos avançam a data do próximo rascunho. **Com `agendar_para`** (data e hora com fuso, de 1 minuto a 1 ano à frente; não vale para `teste`) "
                           "o envio fica `agendado` e sai na hora marcada (rotina de 2 em 2 minutos), com os destinatários vigentes naquele momento. Só a conta root.",
               responses={**INVALIDO})
def enviar(dados: PedidoEnvioChangelog, tarefas: BackgroundTasks, sessao: Session = Depends(obter_sessao),
           root: Usuario = Depends(exigir_conta_root)) -> EnvioChangelogLeitura:
    try:
        envio, lista = servico_changelog.registrar_envio(sessao, root, dados.assunto, dados.corpo, dados.destino, dados.email_teste,
                                                         dados.ate_data, dados.usuarios_ids, dados.setores_ids, dados.agendar_para)
    except servico_changelog.ErroChangelog as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro
    # Agendado: a lista vem vazia e o timer (a cada 2 minutos) envia na hora marcada
    if dados.agendar_para is None:
        tarefas.add_task(servico_changelog.processar_envio, envio.id, lista)
    return EnvioChangelogLeitura.model_validate(envio)


@roteador.delete("/changelog/envios/{envio_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancelar um envio agendado",
                 description="Só enquanto o envio está `agendado` (antes da hora marcada). `404` se não existe; `409` se já saiu ou já foi cancelado. Só a conta root.",
                 responses={**INVALIDO})
def cancelar_envio(envio_id: uuid.UUID, sessao: Session = Depends(obter_sessao), root: Usuario = Depends(exigir_conta_root)) -> Response:
    try:
        servico_changelog.cancelar_agendamento(sessao, root, envio_id)
    except servico_changelog.ErroChangelog as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/changelog/envios", response_model=list[EnvioChangelogLeitura], summary="Histórico de envios do changelog",
              description="Últimos 30 envios (a todos, escolhidos, de teste e agendados; cada um com `situacao`), do mais recente para o mais antigo. Só a conta root.")
def listar_envios(sessao: Session = Depends(obter_sessao), _root: Usuario = Depends(exigir_conta_root)) -> list[EnvioChangelogLeitura]:
    return [EnvioChangelogLeitura.model_validate(e) for e in servico_changelog.historico(sessao)]
