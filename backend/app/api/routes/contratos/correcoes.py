# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da correção de itens do contrato (proposta com prévia, confirmação por outra pessoa e histórico).
"""Correção de itens do contrato (`/api/contratos/{contrato_id}/itens/…`).

Depois de geradas as competências, o gestor titular (ou o SuperRoot) **propõe** a correção de preço e quantidades; **outra pessoa** com
permissão de edição confirma. As competências abertas (medição não concluída) são sincronizadas; as concluídas nunca mudam.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.correcoes import EntradaHistorico, GravacaoCorrecao, LeituraCorrecao, ListaCorrecoes, Motivo, MudancaItem, Previa
from app.services.contratos import servico_correcao_itens as servico
from app.services.contratos.servico_contratos import obter_contrato

roteador = APIRouter(prefix="/contratos/{contrato_id}/itens", tags=["Contratos: correção de itens"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato ou correção")
ESCRITA = {**NAO_ENCONTRADO, **INVALIDO, **SEM_VINCULO}


def _leitura(sessao: Session, contrato_id: uuid.UUID, c, usuario: Usuario) -> LeituraCorrecao:
    contrato = obter_contrato(sessao, contrato_id)
    return LeituraCorrecao(
        id=c.id, autor_id=c.autor_id, autor_nome=c.autor_nome, justificativa=c.justificativa, mudancas=[MudancaItem(**m) for m in c.mudancas], previa=c.previa,
        situacao=c.situacao, decidido_por_nome=c.decidido_por_nome, decidido_em=c.decidido_em, motivo_decisao=c.motivo_decisao, criado_em=c.criado_em,
        pode_decidir=servico.pode_decidir(sessao, contrato, c, usuario), pode_cancelar=c.situacao == "pendente" and (c.autor_id == usuario.id or usuario.superusuario))


@roteador.get("/correcoes", response_model=ListaCorrecoes, summary="Correções de itens",
              description="Propostas pendentes e decididas, da mais recente para a mais antiga. `pode_propor`: gestor titular vigente ou SuperRoot. Exige ACL `contratos` ≥ LEITURA.",
              responses=NAO_ENCONTRADO)
def listar(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        contrato = obter_contrato(sessao, contrato_id)
        return ListaCorrecoes(pode_propor=servico.pode_propor(contrato, usuario), itens=[_leitura(sessao, contrato_id, c, usuario) for c in servico.listar(sessao, contrato_id)])


@roteador.get("/historico", response_model=list[EntradaHistorico], summary="Histórico dos itens",
              description="Cada mudança de item (quem, quando, motivo, antes e depois, versão do cadastro), da mais recente para a mais antiga.", responses=NAO_ENCONTRADO)
def historico(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return [EntradaHistorico(id=h.id, item_id=h.item_id, descricao_item=h.descricao_item, versao_cadastro=h.versao_cadastro, autor_nome=h.autor_nome, motivo=h.motivo,
                                 campos=h.campos, criado_em=h.criado_em) for h in servico.historico(sessao, contrato_id)]


@roteador.post("/correcoes/previa", response_model=Previa, summary="Prévia da correção",
               description="Mostra quais competências abertas mudariam, a variação do valor previsto, e o que não muda (concluídas). **Não grava nada.** Só gestor titular ou SuperRoot.",
               responses=ESCRITA)
def previa(contrato_id: uuid.UUID, dados: GravacaoCorrecao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        return servico.calcular_previa(sessao, contrato_id, dados, autor)


@roteador.post("/correcoes", response_model=LeituraCorrecao, status_code=status.HTTP_201_CREATED, summary="Propor correção de itens",
               description="Registra a proposta como **pendente** e avisa a equipe. O cadastro só muda quando **outra pessoa** confirmar. Justificativa com ao menos 20 caracteres. "
               "Preço de item já reajustado e quantidade de item já aditado são recusados (`400`).", responses=ESCRITA)
def propor(contrato_id: uuid.UUID, dados: GravacaoCorrecao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        correcao = servico.propor(sessao, contrato_id, dados, autor)
        return _leitura(sessao, contrato_id, correcao, autor)


@roteador.post("/correcoes/{correcao_id}/confirmar", response_model=LeituraCorrecao, summary="Confirmar correção",
               description="Segundo par de olhos: outra pessoa (não o autor) com permissão de edição, ou o SuperRoot. Grava o cadastro, sobe a versão, registra o histórico, "
               "sincroniza as competências abertas e invalida as ciências das que mudaram. `409` se o cadastro mudou depois da proposta ou se já foi decidida.", responses=ESCRITA)
def confirmar(contrato_id: uuid.UUID, correcao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        return _leitura(sessao, contrato_id, servico.confirmar(sessao, contrato_id, correcao_id, usuario), usuario)


@roteador.post("/correcoes/{correcao_id}/recusar", response_model=LeituraCorrecao, summary="Recusar correção", description="Mesmas regras de quem confirma; exige `motivo`.", responses=ESCRITA)
def recusar(contrato_id: uuid.UUID, correcao_id: uuid.UUID, dados: Motivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        return _leitura(sessao, contrato_id, servico.recusar(sessao, contrato_id, correcao_id, usuario, dados.motivo), usuario)


@roteador.post("/correcoes/{correcao_id}/cancelar", response_model=LeituraCorrecao, summary="Cancelar proposta", description="Só o autor (ou o SuperRoot), enquanto pendente.", responses=ESCRITA)
def cancelar(contrato_id: uuid.UUID, correcao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        return _leitura(sessao, contrato_id, servico.cancelar(sessao, contrato_id, correcao_id, usuario), usuario)
