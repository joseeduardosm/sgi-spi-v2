# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do diário de bordo do contrato.
"""Diário de bordo do contrato (`/api/contratos/{contrato_id}/diario`).

Leitura: ACL `contratos` ≥ LEITURA. Registro e reenvio de e-mail: quem pode editar o contrato (criador,
equipe vigente ou SuperRoot, com ACL ≥ MODIFICACAO). As ocorrências não são editadas nem excluídas.
"""

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.diario import DiarioContrato, GravacaoOcorrencia, LeituraOcorrencia
from app.services.contratos import servico_diario, servico_notificacoes
from app.services.contratos.servico_contratos import obter_contrato

roteador = APIRouter(prefix="/contratos/{contrato_id}/diario", tags=["Contratos: diário de bordo"], responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato ou ocorrência")
ESCRITA = {**INVALIDO, **SEM_VINCULO}


@roteador.get("", response_model=DiarioContrato, summary="Diário de bordo do contrato",
              description="Ocorrências em ordem de registro (com glosas, competência da data e resultado do e-mail), "
              "se o usuário pode registrar e os itens do contrato para o combobox da glosa.", responses=NAO_ENCONTRADO)
def listar_diario(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Diário completo do contrato."""
    with traduzir_erros(sessao):
        return servico_diario.diario(sessao, contrato_id, usuario)


@roteador.post(
    "",
    response_model=LeituraOcorrencia,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar ocorrência",
    description=(
        "Registra a ocorrência (data não futura, relato e, se houver, itens e quantidades a glosar). As glosas valem na competência "
        "cujo período contém a data. Em segundo plano, envia o registro por e-mail à equipe vigente e aos prepostos ativos "
        "(respostas vão para a equipe)."
    ),
    responses={**NAO_ENCONTRADO, **ESCRITA},
)
def registrar_ocorrencia(contrato_id: uuid.UUID, dados: GravacaoOcorrencia, tarefas: BackgroundTasks,
                         sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Registra e agenda o e-mail."""
    with traduzir_erros(sessao):
        ocorrencia = servico_diario.registrar(sessao, contrato_id, dados, autor)
        tarefas.add_task(servico_notificacoes.notificar_ocorrencia, ocorrencia.id)
        return servico_diario.leitura(obter_contrato(sessao, contrato_id), ocorrencia)


@roteador.post("/{ocorrencia_id}/reenviar", response_model=LeituraOcorrencia, summary="Reenviar o e-mail da ocorrência",
               description="Envia de novo o registro à equipe e aos prepostos e devolve a ocorrência com o novo resultado.",
               responses={**NAO_ENCONTRADO, **ESCRITA})
def reenviar_email(contrato_id: uuid.UUID, ocorrencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                   autor: Usuario = Depends(pode_modificar)):
    """Reenvio síncrono (a tela mostra o resultado na hora)."""
    with traduzir_erros(sessao):
        servico_notificacoes.exigir_reenvio_ocorrencia(sessao, contrato_id, ocorrencia_id, autor)
        servico_notificacoes.notificar_ocorrencia(ocorrencia_id)
        sessao.expire_all()
        contrato = obter_contrato(sessao, contrato_id)
        return servico_diario.leitura(contrato, servico_diario.obter_ocorrencia(contrato, ocorrencia_id))


@roteador.get("/pdf", summary="Diário de bordo em PDF", response_class=Response,
              description="Ocorrências com data no período (limites inclusivos; sem período = todo o contrato) e glosas por item.",
              responses={200: {"content": {"application/pdf": {}}}, **NAO_ENCONTRADO})
def diario_pdf(
    contrato_id: uuid.UUID,
    inicio: date | None = Query(None, description="Data inicial (AAAA-MM-DD)."),
    fim: date | None = Query(None, description="Data final (AAAA-MM-DD)."),
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(pode_ler),
) -> Response:
    """PDF do diário (mesmo padrão visual da memória de cálculo)."""
    with traduzir_erros(sessao):
        contrato = obter_contrato(sessao, contrato_id)
        conteudo = servico_diario.gerar_pdf(contrato, inicio, fim, autor=usuario.nome_completo or usuario.login)
    nome = f"DIARIO_DE_BORDO_SPI_{contrato.sequencial:03d}_{contrato.ano}.pdf"
    return Response(conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome}"'})
