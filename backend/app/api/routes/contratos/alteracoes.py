"""Rotas de prorrogação, reajuste e aditamento/supressão (`/api/contratos/{contrato_id}/…`)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import ARQUIVO_RECUSADO, SEM_VINCULO, arquivo_pdf, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    AberturaAlteracao,
    AberturaReajuste,
    GravacaoMemoriaReajuste,
    GravacaoProrrogacao,
    GravacaoQuantitativos,
    LeituraProcessoProrrogacao,
    LeituraProrrogacao,
    PainelAlteracao,
    PainelReajuste,
)
from app.services.contratos import servico_alteracao, servico_prorrogacao, servico_reajuste

roteador = APIRouter(prefix="/contratos/{contrato_id}", responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")
ESCRITA = {**NAO_ENCONTRADO, **INVALIDO, **SEM_VINCULO}
UPLOAD = {**NAO_ENCONTRADO, **ARQUIVO_RECUSADO, **SEM_VINCULO}
PDF = {status.HTTP_200_OK: {"content": {"application/pdf": {}}}, **resposta_nao_encontrado("Arquivo")}
PRORROGACAO, REAJUSTE, ALTERACAO = ["Contratos: prorrogação"], ["Contratos: reajuste"], ["Contratos: aditamento e supressão"]


# ---------------------------------------------------------------------------------------------
# Prorrogação
# ---------------------------------------------------------------------------------------------

@roteador.get("/prorrogacao", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Rascunho da prorrogação",
              description="Dados da tela de prorrogação: prazo, nova vigência calculada, itens sob demanda, parecer e ciências.", responses=NAO_ENCONTRADO)
def consultar_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_prorrogacao.consultar(sessao, contrato_id, usuario)


@roteador.put("/prorrogacao", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Salvar rascunho da prorrogação",
              description="Prazo (a soma não passa da vigência máxima), regra e grade dos itens sob demanda (limite ≤ original) e parecer. "
              "Alterar o parecer depois de ciências as apaga.", responses=ESCRITA)
def salvar_prorrogacao(contrato_id: uuid.UUID, dados: GravacaoProrrogacao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_prorrogacao.salvar(sessao, contrato_id, dados, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.delete("/prorrogacao", status_code=status.HTTP_204_NO_CONTENT, tags=PRORROGACAO, summary="Descartar rascunho da prorrogação", responses=ESCRITA)
def descartar_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)) -> Response:
    with traduzir_erros(sessao):
        servico_prorrogacao.descartar_rascunho(sessao, contrato_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/prorrogacao/ciencia", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Registrar minha ciência no parecer",
               description="Opcional; qualquer integrante vigente da equipe, uma vez por pessoa.", responses=ESCRITA)
def ciencia_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_prorrogacao.registrar_ciencia(sessao, contrato_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.post("/prorrogacao/parecer", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Emitir PDF do parecer",
               description="Só quando algum campo do parecer está preenchido; inclui as ciências registradas até o momento.", responses=ESCRITA)
def parecer_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_prorrogacao.gerar_parecer(sessao, contrato_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.post("/prorrogacao/registrar", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Registrar prorrogação",
               description="`multipart/form-data`: `assinada_em`, `numero_termo` (opcional) e `termo` (PDF). Cria a nova vigência, anexa o termo "
               "aos documentos (024+) e grava a previsão sob demanda da nova vigência. Com parecer, emite o PDF final.", responses=UPLOAD)
def registrar_prorrogacao(
    contrato_id: uuid.UUID,
    assinada_em: Annotated[date, Form(description="Data de assinatura do Termo Aditivo.")],
    numero_termo: Annotated[str, Form(max_length=100)] = "",
    termo: UploadFile = File(...),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    with traduzir_erros(sessao):
        servico_prorrogacao.registrar(sessao, contrato_id, assinada_em, numero_termo, arquivo_pdf(termo), autor)
        return servico_prorrogacao.listar(sessao, contrato_id, autor)


@roteador.get("/prorrogacoes", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Histórico de prorrogações", responses=NAO_ENCONTRADO)
def listar_prorrogacoes(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_prorrogacao.listar(sessao, contrato_id, usuario)


@roteador.get("/prorrogacoes/arquivos/{anexo_id}", response_class=FileResponse, tags=PRORROGACAO, summary="Baixar termo ou parecer da prorrogação",
              description="Termo aditivo ou parecer (PDF) de uma prorrogação registrada, ou o parecer do rascunho.", responses=PDF)
def arquivo_prorrogacao(contrato_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_prorrogacao.arquivo(sessao, contrato_id, anexo_id)


@roteador.delete("/prorrogacoes/{prorrogacao_id}", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Desfazer última prorrogação",
                 description="Só a mais recente. Depois de gerada a execução da nova vigência, só o SuperRoot (e sem medição registrada).",
                 responses=ESCRITA)
def desfazer_prorrogacao(contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_prorrogacao.desfazer(sessao, contrato_id, prorrogacao_id, autor)
        return servico_prorrogacao.listar(sessao, contrato_id, autor)


# ---------------------------------------------------------------------------------------------
# Reajuste
# ---------------------------------------------------------------------------------------------

@roteador.get("/reajustes", response_model=PainelReajuste, tags=REAJUSTE, summary="Reajuste em elaboração e histórico", responses=NAO_ENCONTRADO)
def painel_reajuste(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_reajuste.painel(sessao, contrato_id, usuario)


@roteador.post("/reajustes", response_model=PainelReajuste, status_code=status.HTTP_201_CREATED, tags=REAJUSTE, summary="Abrir reajuste",
               description="Mês de referência e vigência ainda não reajustada. Um reajuste em elaboração por vez.", responses={**ESCRITA, **CONFLITO})
def abrir_reajuste(contrato_id: uuid.UUID, dados: AberturaReajuste, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.abrir(sessao, contrato_id, dados, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/evidencia", response_model=PainelReajuste, tags=REAJUSTE, summary="Anexar evidência do índice",
               description="`multipart/form-data` (`arquivo`, PDF). Substitui a anterior.", responses=UPLOAD)
def evidencia_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                       autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.anexar_evidencia(sessao, contrato_id, reajuste_id, *arquivo_pdf(arquivo), autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.put("/reajustes/{reajuste_id}/memoria", response_model=PainelReajuste, tags=REAJUSTE, summary="Salvar memória de cálculo",
              description="Índice (%) e valor referencial (teto opcional) por item. Recalcula preços, bases e valores globais.", responses=ESCRITA)
def memoria_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, sessao: Session = Depends(obter_sessao),
                     autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.salvar_memoria(sessao, contrato_id, reajuste_id, dados, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/memoria/arquivos", response_model=PainelReajuste, tags=REAJUSTE, summary="Gerar memória em PDF e XLSX",
               description="Nova versão só se os dados mudaram.", responses=ESCRITA)
def arquivos_memoria_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.gerar_arquivos_memoria(sessao, contrato_id, reajuste_id, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/concluir", response_model=PainelReajuste, tags=REAJUSTE, summary="Concluir e aplicar reajuste",
               description="`multipart/form-data` com o apostilamento assinado (`arquivo`). Atualiza preços, competências não medidas e valor global.",
               responses=UPLOAD)
def concluir_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.concluir(sessao, contrato_id, reajuste_id, *arquivo_pdf(arquivo), autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/cancelar", response_model=PainelReajuste, tags=REAJUSTE, summary="Cancelar reajuste", responses=ESCRITA)
def cancelar_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_reajuste.cancelar(sessao, contrato_id, reajuste_id, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.get("/reajustes/{reajuste_id}/arquivos/{anexo_id}", response_class=FileResponse, tags=REAJUSTE, summary="Baixar arquivo do reajuste", responses=PDF)
def arquivo_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_reajuste.arquivo(sessao, contrato_id, reajuste_id, anexo_id)


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão
# ---------------------------------------------------------------------------------------------

@roteador.get("/alteracoes", response_model=PainelAlteracao, tags=ALTERACAO, summary="Aditamento/supressão em andamento e histórico", responses=NAO_ENCONTRADO)
def painel_alteracao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_alteracao.painel(sessao, contrato_id, usuario)


@roteador.post("/alteracoes", response_model=PainelAlteracao, status_code=status.HTTP_201_CREATED, tags=ALTERACAO, summary="Iniciar aditamento ou supressão",
               description="Tipo, vigência e mês de efeito. Uma alteração em andamento por vez.", responses={**ESCRITA, **CONFLITO})
def abrir_alteracao(contrato_id: uuid.UUID, dados: AberturaAlteracao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.abrir(sessao, contrato_id, dados, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/documentos/{tipo}", response_model=PainelAlteracao, tags=ALTERACAO, summary="Anexar documento da alteração",
               description="`tipo`: `justificativa` (libera os quantitativos), `autorizacao` (Ordenador de Despesa, acima de 25%), "
               "`de_acordo` (contratada) ou `termo` (Termo Aditivo). Os dois últimos exigem as ciências mínimas.", responses=UPLOAD)
def documento_alteracao(
    contrato_id: uuid.UUID,
    alteracao_id: uuid.UUID,
    tipo: Literal["justificativa", "autorizacao", "de_acordo", "termo"],
    arquivo: UploadFile = File(...),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    with traduzir_erros(sessao):
        servico_alteracao.anexar(sessao, contrato_id, alteracao_id, tipo, *arquivo_pdf(arquivo), autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.put("/alteracoes/{alteracao_id}/quantitativos", response_model=PainelAlteracao, tags=ALTERACAO, summary="Salvar quantitativos e enviar para ciência",
              description="Nova quantidade por item; calcula o impacto em R$ e %. Supressão não fica abaixo do executado.", responses=ESCRITA)
def quantitativos(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, dados: GravacaoQuantitativos, sessao: Session = Depends(obter_sessao),
                  autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.salvar_quantitativos(sessao, contrato_id, alteracao_id, dados, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/ciencia", response_model=PainelAlteracao, tags=ALTERACAO, summary="Registrar minha ciência",
               description="Mínimo de 2 pessoas diferentes da equipe.", responses=ESCRITA)
def ciencia_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.registrar_ciencia(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/memoria", response_model=PainelAlteracao, tags=ALTERACAO, summary="Gerar memória (PDF e XLSX)",
               description="Liberada com as ciências mínimas.", responses=ESCRITA)
def memoria_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.gerar_memoria(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/consolidado", response_model=PainelAlteracao, tags=ALTERACAO, summary="Gerar documento consolidado",
               description="Justificativa, autorização, memória e De Acordo em um PDF.", responses=ESCRITA)
def consolidado_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.gerar_consolidado(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/concluir", response_model=PainelAlteracao, tags=ALTERACAO, summary="Concluir e aplicar alteração",
               description="Exige ciências, De Acordo, Termo Aditivo e, acima de 25% acumulado, a autorização do Ordenador.", responses=ESCRITA)
def concluir_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.concluir(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/cancelar", response_model=PainelAlteracao, tags=ALTERACAO, summary="Cancelar alteração", responses=ESCRITA)
def cancelar_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_alteracao.cancelar(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.get("/alteracoes/{alteracao_id}/arquivos/{anexo_id}", response_class=FileResponse, tags=ALTERACAO, summary="Baixar arquivo da alteração", responses=PDF)
def arquivo_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_alteracao.arquivo(sessao, contrato_id, alteracao_id, anexo_id)
