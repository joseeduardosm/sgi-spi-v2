# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do diário de bordo do contrato.
"""Diário de bordo do contrato (`/api/contratos/{contrato_id}/diario`).

Leitura: ACL `contratos` ≥ LEITURA. Registro e reenvio de e-mail: quem pode editar o contrato (criador,
equipe vigente ou SuperRoot, com ACL ≥ MODIFICACAO). As ocorrências não são editadas nem excluídas.
"""

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
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
        "`multipart/form-data`: `dados` (JSON de `GravacaoOcorrencia`: data não futura, relato, glosas e, se a ocorrência impactar a "
        "avaliação da qualidade, os itens do formulário ativo) e até 5 `arquivos` (PDF, Office/LibreOffice, TXT, CSV, PNG ou JPG, "
        "conferidos pelo conteúdo). As glosas valem na competência cujo período contém a data. Só com `enviar_email = true` (em `dados`; padrão "
        "`false`) envia, em segundo plano, o registro por e-mail à equipe vigente e aos prepostos ativos, com os anexos (respostas vão para a equipe)."
    ),
    responses={**NAO_ENCONTRADO, **ESCRITA},
)
async def registrar_ocorrencia(contrato_id: uuid.UUID, tarefas: BackgroundTasks, dados: str = Form(..., description="JSON de `GravacaoOcorrencia`."),
                               arquivos: list[UploadFile] = File(default_factory=list), sessao: Session = Depends(obter_sessao),
                               autor: Usuario = Depends(pode_modificar)):
    """Registra (com os anexos) e agenda o e-mail."""
    try:
        gravacao = GravacaoOcorrencia.model_validate_json(dados)
    except ValidationError as erro:
        mensagem = erro.errors()[0].get("msg", "Dados inválidos.").removeprefix("Value error, ")
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem, "validacao") from erro
    conteudos = [(a.filename or "arquivo", await a.read()) for a in arquivos if a.filename]
    with traduzir_erros(sessao):
        ocorrencia = servico_diario.registrar(sessao, contrato_id, gravacao, autor, conteudos)
        if gravacao.enviar_email:
            tarefas.add_task(servico_notificacoes.notificar_ocorrencia, ocorrencia.id, gravacao.prepostos_ids)
        return servico_diario.leitura(obter_contrato(sessao, contrato_id), ocorrencia)


@roteador.get("/{ocorrencia_id}/anexos/{anexo_id}", response_class=FileResponse, summary="Baixar anexo da ocorrência",
              responses=NAO_ENCONTRADO)
def baixar_anexo(contrato_id: uuid.UUID, ocorrencia_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                 _usuario: Usuario = Depends(pode_ler)):
    """Arquivo anexado a uma ocorrência (quem pode ler o contrato)."""
    from app.services import servico_anexos
    with traduzir_erros(sessao):
        anexo = servico_diario.anexo_da_ocorrencia(obter_contrato(sessao, contrato_id), ocorrencia_id, anexo_id)
    try:
        return servico_anexos.resposta_download(anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


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
    nome = f"DIARIO_DE_BORDO_SPI_{contrato.numero_arquivo}.pdf"
    return Response(conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome}"'})
