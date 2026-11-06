# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a tela Administração › Versões: ver, buscar e instalar versões e (na homologação) aprovar. Só SuperRoot.
"""Rotas de `/api/admin/versoes` (atualização do SGI pelo GitHub; regras em `app/services/servico_versoes.py`)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Papel, Usuario
from app.schemas.versoes import AndamentoAtualizacao, PainelVersoes, PedidoAtualizacao, VersaoAprovadaAgora
from app.services import servico_versoes
from app.services.servico_auditoria import auditar
from app.services.servico_versoes import ErroVersoes

roteador = APIRouter(prefix="/admin/versoes", tags=["Versões do sistema"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


def _painel() -> PainelVersoes:
    try:
        dados = servico_versoes.situacao()
    except ErroVersoes as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    andamento = AndamentoAtualizacao(**{k: v for k, v in dados.pop("andamento").items() if k in AndamentoAtualizacao.model_fields})
    return PainelVersoes(**dados, andamento=andamento, log=servico_versoes.log() if andamento.situacao == "erro" else "")


@roteador.get("", response_model=PainelVersoes, summary="Versões do sistema",
              description="Versão em execução, ambiente, se há alteração local e o andamento da última atualização. Produção: as versões aprovadas "
                          "mais novas que a atual (com as novidades do CHANGELOG e os commits). Homologação: os commits novos do ramo acompanhado e se a "
                          "versão em execução já foi aprovada. Não vai ao GitHub (use `POST …/buscar`). Só SuperRoot.", responses=INVALIDO)
def painel(_: Usuario = Depends(super_root)) -> PainelVersoes:
    return _painel()


@roteador.post("/buscar", response_model=PainelVersoes, summary="Buscar versões novas no GitHub",
               description="`git fetch --tags` e devolve o painel atualizado. `400` se o GitHub não responder. Só SuperRoot.", responses=INVALIDO)
def buscar(_: Usuario = Depends(super_root)) -> PainelVersoes:
    try:
        servico_versoes.buscar()
    except ErroVersoes as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    return _painel()


@roteador.post("/atualizar", response_model=PainelVersoes, status_code=status.HTTP_202_ACCEPTED, summary="Atualizar o sistema",
               description="Produção: instala uma versão aprovada (`alvo` = tag). Homologação: leva ao último commit do ramo acompanhado (`alvo` = ramo). "
                           "`confirmacao` = `ATUALIZAR`. Grava o pedido e liga a unidade `sgi-spi-atualizar` (fora da API): backup geral, código, "
                           "dependências, migrações, build e reinício; se falhar, volta sozinha. Acompanhe por `GET` (`andamento`). `400`: sem a "
                           "confirmação, alvo inválido, alteração local, outra operação em andamento ou unidade não instalada. Só SuperRoot.",
               responses=INVALIDO)
def atualizar(corpo: PedidoAtualizacao, autor: Usuario = Depends(super_root), sessao: Session = Depends(obter_sessao)) -> PainelVersoes:
    try:
        pedido = servico_versoes.pedir_atualizacao(corpo.alvo.strip(), corpo.confirmacao, autor.login, autor.id, autor.nome_completo or autor.login)
    except ErroVersoes as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    auditar(sessao, autor.login, "sistema.versao.pedir", f"{pedido['de']} → {pedido['alvo']}", autor_id=autor.id, alvo_tipo="versao")
    sessao.commit()
    return _painel()


@roteador.post("/aprovar", response_model=VersaoAprovadaAgora, status_code=status.HTTP_201_CREATED, summary="Aprovar a versão (homologação)",
               description="Só na homologação (`MODO_HOMOLOGACAO=true`), sem alteração local e com o commit já no GitHub: cria a tag anotada "
                           "`vAAAA.MM.DD[.N]` (quem aprovou, quando e as novidades do CHANGELOG) e a envia ao GitHub, onde a produção a enxerga. `400` "
                           "fora da homologação, já aprovada ou sem permissão de escrita no GitHub. Só SuperRoot.", responses=INVALIDO)
def aprovar(autor: Usuario = Depends(super_root), sessao: Session = Depends(obter_sessao)) -> VersaoAprovadaAgora:
    try:
        tag = servico_versoes.aprovar(autor.nome_completo or autor.login)
    except ErroVersoes as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    auditar(sessao, autor.login, "sistema.versao.aprovar", tag, autor_id=autor.id, alvo_tipo="versao")
    sessao.commit()
    return VersaoAprovadaAgora(tag=tag)
