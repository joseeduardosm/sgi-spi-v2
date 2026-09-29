# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da tela Mensageria (e-mail de changelog), exclusivas da conta root.
"""Rotas da Mensageria (`/api/mensageria`): só a conta root (login `LOGIN_ADMIN`) acessa.

E-mail de changelog: rascunho a partir do `CHANGELOG.md`, prévia no layout oficial, envio (a todos os usuários
ativos com e-mail ou de teste) e histórico dos envios. A caixa de mensagens de cada usuário continua em
`/api/mensagens`.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_conta_root
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.mensageria import (
    ConteudoChangelog,
    EnvioChangelogLeitura,
    OpcaoSetorChangelog,
    PedidoEnvioChangelog,
    PreviaChangelog,
    RascunhoChangelog,
)
from app.services import servico_changelog, servico_setores

roteador = APIRouter(prefix="/mensageria", tags=["Mensageria"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get("/changelog/rascunho", response_model=RascunhoChangelog, summary="Rascunho do e-mail de changelog",
              description="Assunto e texto sugeridos com as entradas do `CHANGELOG.md` posteriores ao último envio a todos "
                          "(na primeira vez, a entrada mais recente). Sem detalhes técnicos (migrações, endpoints, crases). Traz também "
                          "o total de usuários ativos e os setores disponíveis para o envio a selecionados. Só a conta root.")
def obter_rascunho(sessao: Session = Depends(obter_sessao), _root: Usuario = Depends(exigir_conta_root)) -> RascunhoChangelog:
    r = servico_changelog.rascunho(sessao)
    return RascunhoChangelog(assunto=r.assunto, corpo=r.corpo, desde=r.desde, ate=r.ate, datas=r.datas,
                             total_destinatarios=len(servico_changelog.destinatarios(sessao)), setores=_setores(sessao))


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
                           "`GET /changelog/envios`. Só envios a todos avançam a data do próximo rascunho. Só a conta root.",
               responses={**INVALIDO})
def enviar(dados: PedidoEnvioChangelog, tarefas: BackgroundTasks, sessao: Session = Depends(obter_sessao),
           root: Usuario = Depends(exigir_conta_root)) -> EnvioChangelogLeitura:
    try:
        envio, lista = servico_changelog.registrar_envio(sessao, root, dados.assunto, dados.corpo, dados.destino, dados.email_teste,
                                                         dados.ate_data, dados.usuarios_ids, dados.setores_ids)
    except servico_changelog.ErroChangelog as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    tarefas.add_task(servico_changelog.processar_envio, envio.id, lista)
    return EnvioChangelogLeitura.model_validate(envio)


@roteador.get("/changelog/envios", response_model=list[EnvioChangelogLeitura], summary="Histórico de envios do changelog",
              description="Últimos 30 envios (a todos e de teste), do mais recente para o mais antigo. Só a conta root.")
def listar_envios(sessao: Session = Depends(obter_sessao), _root: Usuario = Depends(exigir_conta_root)) -> list[EnvioChangelogLeitura]:
    return [EnvioChangelogLeitura.model_validate(e) for e in servico_changelog.historico(sessao)]
