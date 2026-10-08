# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do painel e dos relatórios gerenciais de contratos.
"""Relatórios gerenciais da carteira (`/api/contratos/relatorios`), restritos ao SuperRoot,
e o painel de contratos (`/api/contratos/painel`), aberto a quem tem leitura no módulo.

Os relatórios são gerados em memória (PDF ou XLSX) e devolvidos como download.
"""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS
from app.api.routes.contratos.comum import pode_ler
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Papel, Usuario
from app.schemas.contratos.autenticacao import VerificacaoDocumento
from app.schemas.contratos.calendario import Calendario
from app.schemas.contratos.painel import Painel, PainelVigencias
from app.services.contratos import servico_autenticacao, servico_calendario, servico_orcamento, servico_painel, servico_relatorios

roteador = APIRouter(prefix="/contratos/relatorios", tags=["Contratos: relatórios"], responses=RESPOSTAS_AUTENTICADAS)
# O painel fica em outro roteador porque o prefixo é `/contratos`, não `/contratos/relatorios`
roteador_painel = APIRouter(prefix="/contratos", tags=["Contratos: painel"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)
# Documentação da resposta 200 de download (PDF ou planilha)
ARQUIVO = {status.HTTP_200_OK: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
                                "description": "Arquivo PDF ou XLSX."}}


def _arquivo(conteudo: bytes, nome: str, tipo: str) -> Response:
    """Resposta de download: `Content-Disposition: attachment` faz o navegador salvar o arquivo."""
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/notas-empenho", summary="Relatório Executivo de Notas de Empenho",
              description="Todas as NEs de todos os contratos, com valor inicial, consumido e saldo. Restrito ao SuperRoot.", responses=ARQUIVO)
def relatorio_notas(formato: Literal["xlsx", "pdf"] = Query("xlsx"), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)):
    """Relatório de todas as NEs; o serviço devolve (conteúdo, nome do arquivo, tipo MIME)."""
    return _arquivo(*servico_orcamento.arquivo_relatorio_notas(sessao, formato, autor))


@roteador.get("/previsao-orcamentaria", summary="Exportar Previsão Orçamentária consolidada",
              description="Exercício, formato (PDF ou XLSX), seções (resumo anual e detalhamento mensal) e cenários em elaboração "
              "(reajustes, aditamentos, supressões e prorrogações) somados à previsão. Restrito ao SuperRoot.", responses=ARQUIVO)
def previsao_orcamentaria(
    exercicio: int = Query(..., ge=2000, le=2100),
    formato: Literal["xlsx", "pdf"] = Query("xlsx"),
    resumo_anual: bool = Query(True),
    detalhamento_mensal: bool = Query(True),
    cenario_reajustes: bool = Query(False),
    cenario_aditamentos: bool = Query(False),
    cenario_supressoes: bool = Query(False),
    cenario_prorrogacoes: bool = Query(False),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(super_root),
):
    """Exporta a previsão consolidada do exercício, com as seções e os cenários escolhidos."""
    # Junta num conjunto só os nomes dos cenários marcados como verdadeiros
    cenarios = {nome for nome, ativo in (("reajustes", cenario_reajustes), ("aditamentos", cenario_aditamentos),
                                         ("supressoes", cenario_supressoes), ("prorrogacoes", cenario_prorrogacoes)) if ativo}
    return _arquivo(*servico_relatorios.exportar(sessao, exercicio, formato, resumo_anual, detalhamento_mensal, cenarios, autor))


@roteador_painel.get("/verificar-documento", response_model=VerificacaoDocumento, summary="Verificar um documento pelo código",
                     description="Confere o código de verificação impresso na Folha de autenticação dos PDFs gerados pelo sistema (relatório de avaliação e memória "
                     "de cálculo) e devolve o registro: tipo, contrato, competência, quem gerou, quando e quem tinha dado ciência. O código sozinho não prova "
                     "que o arquivo é o original: para isso, envie o PDF em `POST /contratos/verificar-documento`. Exige ACL `contratos` ≥ LEITURA.")
def verificar_por_codigo(codigo: str = Query(..., min_length=1, max_length=40), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> VerificacaoDocumento:
    """Verificação pelo código."""
    return VerificacaoDocumento.model_validate(servico_autenticacao.verificar(sessao, codigo=codigo))


@roteador_painel.post("/verificar-documento", response_model=VerificacaoDocumento, summary="Verificar um PDF enviado",
                      description="`multipart/form-data` com `arquivo` (PDF): vale só se o SHA-256 for exatamente o de um documento gerado pelo sistema (o arquivo "
                      "não foi alterado). Não é verificação de assinatura digital. Exige ACL `contratos` ≥ LEITURA.")
def verificar_pdf(arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> VerificacaoDocumento:
    """Verificação pelo arquivo."""
    return VerificacaoDocumento.model_validate(servico_autenticacao.verificar(sessao, conteudo=arquivo.file.read(20 * 1024 * 1024 + 1)[: 20 * 1024 * 1024]))


@roteador_painel.get("/calendario", response_model=Calendario, summary="Calendário de vencimentos de contratos",
                     description="Vencimentos e prazos dos contratos numa lista por data, de `de` a `ate` (até 366 dias): fim de vigência e vigência máxima, "
                     "reajuste, vencimento do pagamento da NF, prazo de 48 h da NF, validade dos documentos do checklist, medição atrasada, empenho "
                     "insuficiente e prazos das tarefas geradas pelos contratos. `meus=true` limita aos contratos em que o usuário é criador ou integrante "
                     "vigente da equipe. `tipos` (separados por vírgula) filtra os tipos. As tarefas só aparecem para quem pode vê-las (regra do módulo "
                     "Tarefas). Contratos encerrados e suspensos ficam de fora. Exige ACL `contratos` ≥ LEITURA.")
def calendario(
    de: date = Query(...), ate: date = Query(...), meus: bool = Query(False), contrato_id: uuid.UUID | None = Query(None),
    empresa_id: uuid.UUID | None = Query(None), tipos: str | None = Query(None, description="Tipos separados por vírgula."),
    sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler),
) -> Calendario:
    """Agrega os eventos do período; os cálculos ficam no serviço."""
    if ate < de or (ate - de).days > 366:
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe um período de no máximo 366 dias (`ate` não pode ser antes de `de`).", "validacao")
    escolhidos = {t.strip() for t in tipos.split(",") if t.strip()} if tipos else None
    if escolhidos and not escolhidos <= set(servico_calendario.TIPOS):
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tipo de evento desconhecido em `tipos`.", "validacao")
    return servico_calendario.montar_calendario(sessao, usuario, de, ate, meus, contrato_id, empresa_id, escolhidos)


@roteador_painel.get("/painel/vigencias", response_model=PainelVigencias, summary="Painel de vigências (vigências)",
                     description="Uma linha do tempo por contrato vigente (ativo ou a vencer): vigência inicial e prorrogações, dias "
                     "restantes e meses ainda prorrogáveis até a vigência máxima. Ordenado do que vence primeiro ao último. Filtro "
                     "opcional por empresa. Exige ACL `contratos` ≥ LEITURA.")
def painel_vigencias(
    empresa_id: uuid.UUID | None = Query(None),
    sessao: Session = Depends(obter_sessao),
    _: Usuario = Depends(pode_ler),
) -> PainelVigencias:
    """Vigências da carteira, para a aba "Vigências"."""
    return servico_painel.vigencias_da_carteira(sessao, empresa_id)


@roteador_painel.get("/painel", response_model=Painel, summary="Painel de contratos",
                     description="Minhas pendências (contratos em que sou criador ou integrante da equipe), alertas de risco da carteira, "
                     "execução orçamentária do exercício (previsto × medido × pago) e números da carteira. Filtros opcionais por empresa "
                     "e contrato (não se aplicam às pendências). Exige ACL `contratos` ≥ LEITURA.")
def painel(
    exercicio: int | None = Query(None, ge=2000, le=2100),
    empresa_id: uuid.UUID | None = Query(None),
    contrato_id: uuid.UUID | None = Query(None),
    sessao: Session = Depends(obter_sessao),
    usuario: Usuario = Depends(pode_ler),
) -> Painel:
    """Monta todos os blocos do painel de uma vez; os cálculos ficam no serviço."""
    return servico_painel.montar_painel(sessao, usuario, exercicio, empresa_id, contrato_id)
