# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de checklists, formulários de avaliação e competências de execução.
"""Rotas da execução (`/api/contratos/{contrato_id}/…`): checklists, formulários e competências.

Visão geral do fluxo mensal:
- **Checklists** e **formulários de avaliação** são configurados por contrato, em versões. Só uma
  versão de cada fica ativa; ela é copiada para cada competência gerada.
- **Competência** é o período de execução (mês civil ou grupo de meses, conforme a periodicidade).
  Ela passa por etapas em ordem: 1 medição → 2 avaliação → 3 nota fiscal → 4 CADIN →
  5 checklist → 6 consolidado → 7 ordem bancária (OB), que debita as Notas de Empenho.

Quase todas as rotas de escrita devolvem o detalhe completo da competência já atualizado, para
a tela se redesenhar sem precisar de uma segunda requisição.
"""

import re
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import ARQUIVO_RECUSADO, SEM_VINCULO, arquivo_pdf, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.schemas.contratos.execucao import (
    ConclusaoMedicao,
    GravacaoRetencao,
    DetalheCompetencia,
    GravacaoAvaliacaoGestor,
    GravacaoAvaliacaoInicial,
    GravacaoChecklist,
    GravacaoFormulario,
    GravacaoMedicao,
    LeituraChecklist,
    LeituraFormulario,
    PainelExecucao,
    Reabertura,
)
from app.services.contratos import servico_competencias as competencias
from app.services.contratos import servico_notificacoes, servico_retencao
from app.services.contratos import servico_configuracao_execucao as configuracao

roteador = APIRouter(prefix="/contratos/{contrato_id}", tags=["Contratos: execução"], responses=RESPOSTAS_AUTENTICADAS)
# Respostas de erro documentadas em comum pelas rotas de escrita
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")
NAO_ENCONTRADA = resposta_nao_encontrado("Contrato ou competência")
ESCRITA = {**INVALIDO, **SEM_VINCULO}


# ---------------------------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------------------------

@roteador.get("/checklists", response_model=list[LeituraChecklist], summary="Versões do checklist", responses=NAO_ENCONTRADO,
              description="Mais recente primeiro (sem as excluídas). Exige ACL `contratos` ≥ LEITURA.")
def listar_checklists(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Versões do checklist do contrato (a ativa e as inativas)."""
    with traduzir_erros():
        return configuracao.listar_checklists(sessao, contrato_id)


@roteador.post("/checklists", response_model=list[LeituraChecklist], status_code=status.HTTP_201_CREATED, summary="Criar checklist (versão inativa)",
               description="Cria uma versão inativa. Exige poder editar o contrato. Devolve a lista.", responses={**NAO_ENCONTRADO, **ESCRITA})
def criar_checklist(contrato_id: uuid.UUID, dados: GravacaoChecklist, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Cria uma versão nova, sempre inativa; é preciso ativá-la depois."""
    with traduzir_erros(sessao):
        configuracao.criar_checklist(sessao, contrato_id, dados, autor)
        return configuracao.listar_checklists(sessao, contrato_id)


@roteador.put("/checklists/{checklist_id}", response_model=list[LeituraChecklist], summary="Editar checklist inativo",
              description="Versões ativas não são editadas. Exige poder editar o contrato.", responses={**NAO_ENCONTRADO, **ESCRITA})
def alterar_checklist(contrato_id: uuid.UUID, checklist_id: uuid.UUID, dados: GravacaoChecklist, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(pode_modificar)):
    """Edita uma versão inativa (ativas ficam congeladas para não mudar competências em andamento)."""
    with traduzir_erros(sessao):
        configuracao.alterar_checklist(sessao, contrato_id, checklist_id, dados, autor)
        return configuracao.listar_checklists(sessao, contrato_id)


@roteador.post("/checklists/{checklist_id}/duplicar", response_model=list[LeituraChecklist], status_code=status.HTTP_201_CREATED,
               summary="Duplicar checklist", description="Cria nova versão inativa com o mesmo conteúdo.", responses={**NAO_ENCONTRADO, **ESCRITA})
def duplicar_checklist(contrato_id: uuid.UUID, checklist_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Copia uma versão (útil para criar a próxima a partir da ativa)."""
    with traduzir_erros(sessao):
        configuracao.duplicar_checklist(sessao, contrato_id, checklist_id, autor)
        return configuracao.listar_checklists(sessao, contrato_id)


@roteador.post("/checklists/{checklist_id}/ativar", response_model=list[LeituraChecklist], summary="Ativar checklist",
               description="Desativa as demais versões e aplica esta às competências que ainda não passaram do checklist "
               "(documentos já anexados com o mesmo nome são mantidos).", responses={**NAO_ENCONTRADO, **ESCRITA})
def ativar_checklist(contrato_id: uuid.UUID, checklist_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Ativa a versão e a aplica às competências que ainda não chegaram ao checklist."""
    with traduzir_erros(sessao):
        configuracao.ativar_checklist(sessao, contrato_id, checklist_id, autor)
        return configuracao.listar_checklists(sessao, contrato_id)


@roteador.delete("/checklists/{checklist_id}", response_model=list[LeituraChecklist], summary="Excluir checklist inativo",
                 description="Exclusão lógica; versões ativas não são excluídas. Devolve a lista.", responses={**NAO_ENCONTRADO, **ESCRITA})
def excluir_checklist(contrato_id: uuid.UUID, checklist_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Exclusão lógica de uma versão inativa."""
    with traduzir_erros(sessao):
        configuracao.excluir_checklist(sessao, contrato_id, checklist_id, autor)
        return configuracao.listar_checklists(sessao, contrato_id)


# ---------------------------------------------------------------------------------------------
# Formulários de avaliação
# ---------------------------------------------------------------------------------------------

@roteador.get("/formularios", response_model=list[LeituraFormulario], summary="Versões do formulário de avaliação", responses=NAO_ENCONTRADO,
              description="Mais recente primeiro. Exige ACL `contratos` ≥ LEITURA.")
def listar_formularios(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Versões do formulário de avaliação do contrato."""
    with traduzir_erros():
        return configuracao.listar_formularios(sessao, contrato_id)


@roteador.post("/formularios", response_model=list[LeituraFormulario], status_code=status.HTTP_201_CREATED,
               summary="Criar formulário (versão inativa)", description="Escala crescente, faixas de liberação e grupos com pesos somando 100%.",
               responses={**NAO_ENCONTRADO, **ESCRITA})
def criar_formulario(contrato_id: uuid.UUID, dados: GravacaoFormulario, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Cria um formulário (escala de notas, faixas de % liberado e grupos com pesos)."""
    with traduzir_erros(sessao):
        configuracao.criar_formulario(sessao, contrato_id, dados, autor)
        return configuracao.listar_formularios(sessao, contrato_id)


@roteador.put("/formularios/{formulario_id}", response_model=list[LeituraFormulario], summary="Editar formulário inativo",
              description="Versões ativas não são editadas.", responses={**NAO_ENCONTRADO, **ESCRITA})
def alterar_formulario(contrato_id: uuid.UUID, formulario_id: uuid.UUID, dados: GravacaoFormulario, sessao: Session = Depends(obter_sessao),
                       autor: Usuario = Depends(pode_modificar)):
    """Edita uma versão inativa do formulário."""
    with traduzir_erros(sessao):
        configuracao.alterar_formulario(sessao, contrato_id, formulario_id, dados, autor)
        return configuracao.listar_formularios(sessao, contrato_id)


@roteador.post("/formularios/{formulario_id}/duplicar", response_model=list[LeituraFormulario], status_code=status.HTTP_201_CREATED,
               summary="Duplicar formulário", description="Cria nova versão inativa.", responses={**NAO_ENCONTRADO, **ESCRITA})
def duplicar_formulario(contrato_id: uuid.UUID, formulario_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Copia uma versão do formulário."""
    with traduzir_erros(sessao):
        configuracao.duplicar_formulario(sessao, contrato_id, formulario_id, autor)
        return configuracao.listar_formularios(sessao, contrato_id)


@roteador.post("/formularios/{formulario_id}/ativar", response_model=list[LeituraFormulario], summary="Ativar formulário",
               description="Desativa as demais versões e aplica esta às competências ainda na medição (sem avaliação iniciada).",
               responses={**NAO_ENCONTRADO, **ESCRITA})
def ativar_formulario(contrato_id: uuid.UUID, formulario_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Ativa o formulário e o aplica às competências cuja avaliação ainda não começou."""
    with traduzir_erros(sessao):
        configuracao.ativar_formulario(sessao, contrato_id, formulario_id, autor)
        return configuracao.listar_formularios(sessao, contrato_id)


# ---------------------------------------------------------------------------------------------
# Competências
# ---------------------------------------------------------------------------------------------

@roteador.get("/execucao", response_model=PainelExecucao, summary="Aba Execução", responses=NAO_ENCONTRADO,
              description="Pré-requisitos e competências agrupadas por vigência. Exige ACL `contratos` ≥ LEITURA.")
def painel_execucao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Aba Execução do contrato: pré-requisitos para gerar competências e a lista delas por vigência."""
    with traduzir_erros():
        return competencias.painel(sessao, contrato_id)


@roteador.post("/execucao/gerar", response_model=PainelExecucao, summary="Gerar ou atualizar competências",
               description="Cria as competências que faltam (mês civil × periodicidade), copiando o checklist ativo e o formulário ativo. "
               "Depois disso, itens e ordem só mudam pelo SuperRoot. Pré-requisitos não atendidos → 400 com os motivos.",
               responses={**NAO_ENCONTRADO, **ESCRITA})
def gerar_competencias(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Gera as competências que faltam (operação idempotente: rodar duas vezes não duplica nada)."""
    with traduzir_erros(sessao):
        competencias.gerar_competencias(sessao, contrato_id, autor)
        return competencias.painel(sessao, contrato_id)


@roteador.get("/competencias/identificador/{identificador}", response_model=DetalheCompetencia, summary="Competência pelo identificador",
              description="`identificador` = `AAAA-MM`, `AAAA-MM-1`/`AAAA-MM-2` (mês dividido entre vigências) ou `AAAA-MM-dif` "
              "(diferença de reajuste). É a chave da tela `/contratos/:id/execucao/:identificador`.", responses=NAO_ENCONTRADA)
def competencia_por_identificador(
    contrato_id: uuid.UUID, identificador: str, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)
):
    """Busca a competência pelo identificador legível usado na URL da tela (ex.: `2026-03`)."""
    # Recusa formatos inválidos logo aqui, como 404, sem consultar o banco
    if not re.fullmatch(r"\d{4}-\d{2}(-(\d|dif))?", identificador):
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Competência não encontrada.", "nao_encontrado")
    with traduzir_erros():
        competencia_id = competencias.localizar_competencia(sessao, contrato_id, identificador)
        return competencias.detalhar(sessao, contrato_id, competencia_id, usuario)


@roteador.get("/competencias/{competencia_id}", response_model=DetalheCompetencia, summary="Detalhe da competência",
              description="Todas as etapas, com o que já foi registrado. Exige ACL `contratos` ≥ LEITURA.", responses=NAO_ENCONTRADA)
def detalhar_competencia(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Detalhe completo da competência pelo id."""
    with traduzir_erros():
        return competencias.detalhar(sessao, contrato_id, competencia_id, usuario)


@roteador.get("/competencias/{competencia_id}/arquivos/{anexo_id}", response_class=FileResponse, summary="Baixar arquivo da competência",
              description="Qualquer PDF da competência (memórias, NF, CADIN, checklist, avaliação, consolidado, OB).",
              responses={status.HTTP_200_OK: {"content": {"application/pdf": {}}}, **resposta_nao_encontrado("Arquivo")})
def baixar_arquivo(contrato_id: uuid.UUID, competencia_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                   _: Usuario = Depends(pode_ler)):
    """Baixa qualquer PDF ligado à competência; o serviço confere se o anexo pertence a ela."""
    with traduzir_erros():
        return competencias.arquivo_da_competencia(sessao, contrato_id, competencia_id, anexo_id)


def _depois(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, usuario: Usuario) -> DetalheCompetencia:
    """Atalho usado pelas rotas de escrita para devolver o detalhe atualizado da competência."""
    return competencias.detalhar(sessao, contrato_id, competencia_id, usuario)


@roteador.put("/competencias/{competencia_id}/medicao", response_model=DetalheCompetencia, summary="Salvar medição",
              description="Quantidades medidas de todos os itens e NEs em ordem de consumo (saldo somado ≥ total medido). "
              "Liberada após o fim do período. Qualquer alteração apaga as ciências já registradas.", responses={**NAO_ENCONTRADA, **ESCRITA})
def salvar_medicao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoMedicao, sessao: Session = Depends(obter_sessao),
                   autor: Usuario = Depends(pode_modificar)):
    """Etapa 1: grava as quantidades medidas e as NEs escolhidas; alterar invalida as ciências."""
    with traduzir_erros(sessao):
        competencias.salvar_medicao(sessao, contrato_id, competencia_id, dados, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/medicao/ciencia", response_model=DetalheCompetencia, summary="Registrar minha ciência na medição",
               description="Somente integrantes vigentes da equipe, uma vez por pessoa. Exige a medição salva.", responses={**NAO_ENCONTRADA, **ESCRITA})
def ciencia_medicao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 1: registra a ciência do usuário logado (uma ciência já basta para concluir)."""
    with traduzir_erros(sessao):
        competencias.registrar_ciencia(sessao, contrato_id, competencia_id, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/medicao/concluir", response_model=DetalheCompetencia, summary="Concluir medição e gerar memória",
               description="Exige ao menos uma ciência de integrante da equipe, a mesma seleção de NEs salva e nenhum item acima do saldo "
               "líquido. Gera a memória de cálculo (nova versão só se os dados mudaram), soma o executado nos itens e avança a etapa. "
               "Em segundo plano, envia à equipe e aos prepostos o e-mail com a memória e o diário de bordo do período em PDF, "
               "pedindo a nota fiscal em até 48 horas.", responses={**NAO_ENCONTRADA, **ESCRITA})
def concluir_medicao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: ConclusaoMedicao, tarefas: BackgroundTasks,
                     sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 1: conclui a medição, gera a memória de cálculo em PDF, libera a etapa seguinte e avisa equipe e preposto."""
    with traduzir_erros(sessao):
        competencias.concluir_medicao(sessao, contrato_id, competencia_id, dados.notas_empenho_ids, autor)
        tarefas.add_task(servico_notificacoes.notificar_medicao, competencia_id)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/reenviar-email-medicao", response_model=DetalheCompetencia,
               summary="Reenviar o e-mail da medição",
               description="Envia de novo à equipe e aos prepostos o e-mail da medição concluída (memória + diário do período). "
               "Só depois de concluída a medição. Mesma permissão de edição do contrato.", responses={**NAO_ENCONTRADA, **ESCRITA})
def reenviar_email_medicao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                           autor: Usuario = Depends(pode_modificar)):
    """Reenvio síncrono (a tela mostra o resultado na hora)."""
    with traduzir_erros(sessao):
        servico_notificacoes.exigir_reenvio_medicao(sessao, contrato_id, competencia_id, autor)
        servico_notificacoes.notificar_medicao(competencia_id)
        sessao.expire_all()
        return _depois(sessao, contrato_id, competencia_id, autor)


# --- Etapa 2: avaliação ----------------------------------------------------------------------

@roteador.put("/competencias/{competencia_id}/avaliacao/inicial", response_model=DetalheCompetencia, summary="Salvar avaliação inicial",
              description="Nota de cada item (da escala); abaixo da máxima exige justificativa. Qualquer integrante da equipe.",
              responses={**NAO_ENCONTRADA, **ESCRITA})
def avaliacao_inicial(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoAvaliacaoInicial, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(pode_modificar)):
    """Etapa 2: notas da avaliação inicial feita pela equipe."""
    with traduzir_erros(sessao):
        competencias.salvar_avaliacao_inicial(sessao, contrato_id, competencia_id, dados, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.put("/competencias/{competencia_id}/avaliacao/gestor", response_model=DetalheCompetencia, summary="Salvar avaliação do gestor",
              description="Só quando alguma nota inicial ficou abaixo da máxima (senão, 400 e vale a nota inicial). Nota do gestor por item "
              "(complemento obrigatório abaixo da máxima) e complemento geral. Define a nota final e o % liberado.",
              responses={**NAO_ENCONTRADA, **ESCRITA})
def avaliacao_gestor(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoAvaliacaoGestor, sessao: Session = Depends(obter_sessao),
                     autor: Usuario = Depends(pode_modificar)):
    """Etapa 2: notas do gestor, que definem a nota final e o percentual do pagamento liberado."""
    with traduzir_erros(sessao):
        competencias.salvar_avaliacao_gestor(sessao, contrato_id, competencia_id, dados, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/avaliacao/ciencia", response_model=DetalheCompetencia, summary="Registrar minha ciência no ateste",
               description="Qualquer integrante vigente da equipe, uma vez por pessoa, depois das notas fechadas "
               "(avaliação inicial e, se alguma nota ficou abaixo da máxima, a do gestor). Uma ciência já libera o PDF.", responses={**NAO_ENCONTRADA, **ESCRITA})
def ciencia_ateste(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    """Etapa 2: ciência de um integrante da equipe no ateste."""
    # Aqui basta ACL de leitura: a permissão real é integrar a equipe vigente do contrato
    with traduzir_erros(sessao):
        competencias.registrar_ciencia_ateste(sessao, contrato_id, competencia_id, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/avaliacao/pdf", response_model=DetalheCompetencia, summary="Exportar PDF da avaliação",
               description="Exige ao menos uma ciência da equipe no ateste (as demais podem ser registradas depois).", responses={**NAO_ENCONTRADA, **ESCRITA})
def pdf_avaliacao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 2: gera o PDF do relatório de avaliação para a contratada assinar."""
    with traduzir_erros(sessao):
        competencias.gerar_pdf_avaliacao(sessao, contrato_id, competencia_id, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/avaliacao/assinada", response_model=DetalheCompetencia,
               summary="Enviar relatório assinado pela contratada", description="`multipart/form-data` (`arquivo`, PDF). Conclui a etapa.",
               responses={**NAO_ENCONTRADA, **ARQUIVO_RECUSADO, **SEM_VINCULO})
def avaliacao_assinada(contrato_id: uuid.UUID, competencia_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                       autor: Usuario = Depends(pode_modificar)):
    """Etapa 2: recebe o relatório assinado pela contratada e conclui a etapa."""
    with traduzir_erros(sessao):
        competencias.enviar_avaliacao_assinada(sessao, contrato_id, competencia_id, *arquivo_pdf(arquivo), autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/avaliacao/reconsideracao", response_model=DetalheCompetencia,
               summary="Reconsideração da avaliação (uma vez)", description="Justificativa da contratada em PDF (`arquivo`). Reabre a avaliação; "
               "só antes da nota fiscal.", responses={**NAO_ENCONTRADA, **ARQUIVO_RECUSADO, **SEM_VINCULO})
def reconsideracao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                   autor: Usuario = Depends(pode_modificar)):
    """Etapa 2: recebe o pedido de reconsideração da contratada (uma única vez) e reabre a avaliação."""
    with traduzir_erros(sessao):
        competencias.reconsiderar_avaliacao(sessao, contrato_id, competencia_id, *arquivo_pdf(arquivo), autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


# --- Etapa 3: nota fiscal --------------------------------------------------------------------

@roteador.post("/competencias/{competencia_id}/nota-fiscal", response_model=DetalheCompetencia, summary="Juntar nota fiscal (PDF + XML)",
               description="`multipart/form-data`: NF em PDF (`arquivo`) e XML (`xml`, NF-e ou NFS-e), ambos obrigatórios; data de "
               "recebimento e prazo de pagamento (1 a 3650 dias). NF adicional opcional (`possui_adicional`, `arquivo_adicional`, "
               "`xml_adicional`). Número, chave, valor e as retenções sugeridas vêm do XML; o saldo livre das NEs precisa cobrir as "
               "notas. Conclui a etapa (próxima: retenção de tributos) e envia, em segundo plano, o e-mail ao Financeiro com cópia à "
               "equipe.", responses={**NAO_ENCONTRADA, **ARQUIVO_RECUSADO, **SEM_VINCULO})
def nota_fiscal(
    contrato_id: uuid.UUID,
    competencia_id: uuid.UUID,
    tarefas: BackgroundTasks,
    recebida_em: Annotated[date, Form(description="Data em que a Administração recebeu a NF.")],
    prazo_pagamento_dias: Annotated[int, Form(ge=1, le=3650)],
    possui_adicional: Annotated[bool, Form()] = False,
    arquivo: UploadFile | None = File(None),
    xml: UploadFile | None = File(None),
    arquivo_adicional: UploadFile | None = File(None),
    xml_adicional: UploadFile | None = File(None),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    """Etapa 3: junta a nota fiscal (e a adicional, se houver); os valores são lidos do XML."""
    dados = {"recebida_em": recebida_em, "prazo_pagamento_dias": prazo_pagamento_dias, "possui_adicional": possui_adicional}

    def arquivo_xml(upload: UploadFile | None, padrao: str) -> tuple | None:
        return (upload.file, upload.filename or padrao) if upload else None

    with traduzir_erros(sessao):
        # Os arquivos são opcionais na chamada: ao corrigir depois de reabrir, os anteriores podem ser mantidos
        competencias.registrar_nota_fiscal(
            sessao, contrato_id, competencia_id, dados, arquivo_pdf(arquivo) if arquivo else None, arquivo_xml(xml, "nota_fiscal.xml"),
            arquivo_pdf(arquivo_adicional) if possui_adicional and arquivo_adicional else None,
            arquivo_xml(xml_adicional, "nota_fiscal_adicional.xml") if possui_adicional else None, autor,
        )
        tarefas.add_task(servico_notificacoes.notificar_nf, competencia_id)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/reenviar-email-nf", response_model=DetalheCompetencia, summary="Reenviar o e-mail da NF",
               description="Envia de novo ao Financeiro (cópia à equipe) o aviso da nota fiscal juntada.", responses={**NAO_ENCONTRADA, **ESCRITA})
def reenviar_email_nf(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(pode_modificar)):
    """Reenvio síncrono (a tela mostra o resultado na hora)."""
    with traduzir_erros(sessao):
        servico_notificacoes.exigir_reenvio(sessao, contrato_id, competencia_id, autor, "nf")
        servico_notificacoes.notificar_nf(competencia_id)
        sessao.expire_all()
        return _depois(sessao, contrato_id, competencia_id, autor)


# --- Etapa 4: retenção de tributos -----------------------------------------------------------

@roteador.put("/competencias/{competencia_id}/retencao", response_model=DetalheCompetencia, summary="Salvar retenção de tributos",
              description="Retenções conferidas (IR, INSS, ISS, PIS, COFINS e CSLL; ≥ 0 e soma ≤ bruto) da NF e da adicional, se houver, "
              "e a confirmação de que a discriminação é compatível com o objeto. Permitido ao Financeiro (setor configurado em "
              "`SETOR_FINANCEIRO` e filhos), à equipe do contrato e ao SuperRoot. Gera o PDF da conferência, avança para o CADIN e "
              "envia, em segundo plano, o e-mail à equipe.", responses={**NAO_ENCONTRADA, **ESCRITA})
def salvar_retencao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoRetencao, tarefas: BackgroundTasks,
                    sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    """Etapa 4: conferência do Financeiro."""
    with traduzir_erros(sessao):
        servico_retencao.salvar_retencao(
            sessao, contrato_id, competencia_id, dados.principal.model_dump(), dados.adicional.model_dump() if dados.adicional else None,
            dados.discriminacao_conferida, autor,
        )
        tarefas.add_task(servico_notificacoes.notificar_retencao, competencia_id)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/reenviar-email-retencao", response_model=DetalheCompetencia,
               summary="Reenviar o e-mail da retenção", description="Envia de novo à equipe o aviso das retenções conferidas.",
               responses={**NAO_ENCONTRADA, **ESCRITA})
def reenviar_email_retencao(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao),
                            autor: Usuario = Depends(pode_ler)):
    """Reenvio síncrono (quem pode conferir a retenção)."""
    with traduzir_erros(sessao):
        servico_notificacoes.exigir_reenvio(sessao, contrato_id, competencia_id, autor, "retencao")
        servico_notificacoes.notificar_retencao(competencia_id)
        sessao.expire_all()
        return _depois(sessao, contrato_id, competencia_id, autor)


# --- Etapa 5: CADIN --------------------------------------------------------------------------

@roteador.post("/competencias/{competencia_id}/cadin", response_model=DetalheCompetencia, summary="Registrar consulta ao CADIN",
               description="`multipart/form-data`: `possui_pendencia`, `certidao` (PDF). Com pendência: `pendencia` (até 2000), "
               "`texto_notificacao` e `email` (PDF), e a etapa continua aberta. Sem pendência, conclui a etapa.",
               responses={**NAO_ENCONTRADA, **ARQUIVO_RECUSADO, **SEM_VINCULO})
def cadin(
    contrato_id: uuid.UUID,
    competencia_id: uuid.UUID,
    possui_pendencia: Annotated[bool, Form()],
    certidao: UploadFile = File(...),
    pendencia: Annotated[str, Form(max_length=2000)] = "",
    texto_notificacao: Annotated[str, Form(max_length=2500)] = "",
    email: UploadFile | None = File(None),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    """Etapa 4: registra a consulta ao CADIN. Com pendência, a etapa fica aberta até regularizar."""
    with traduzir_erros(sessao):
        competencias.registrar_cadin(
            sessao, contrato_id, competencia_id, possui_pendencia, pendencia, texto_notificacao, arquivo_pdf(certidao),
            arquivo_pdf(email) if email else None, autor,
        )
        return _depois(sessao, contrato_id, competencia_id, autor)


# --- Etapas 5 a 7 ----------------------------------------------------------------------------

@roteador.post("/competencias/{competencia_id}/checklist/concluir", response_model=DetalheCompetencia, summary="Concluir checklist",
               description="Conclui a etapa quando todos os documentos obrigatórios estão anexados; os opcionais podem ficar sem anexo.",
               responses={**NAO_ENCONTRADA, **ESCRITA})
def concluir_checklist(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 5: conclui o checklist quando todos os documentos obrigatórios estão anexados."""
    # Esta rota precisa vir antes de `/checklist/{documento_id}`, senão "concluir" seria lido como id
    with traduzir_erros(sessao):
        competencias.concluir_checklist(sessao, contrato_id, competencia_id, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/checklist/{documento_id}", response_model=DetalheCompetencia, summary="Anexar documento do checklist",
               description="`multipart/form-data` (`arquivo`, PDF). Com todos os documentos anexados, a etapa conclui sozinha; com os obrigatórios, use `/checklist/concluir`.",
               responses={**resposta_nao_encontrado("Competência ou documento"), **ARQUIVO_RECUSADO, **SEM_VINCULO})
def documento_mensal(contrato_id: uuid.UUID, competencia_id: uuid.UUID, documento_id: uuid.UUID, arquivo: UploadFile = File(...),
                     sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 5: anexa o PDF de um documento do checklist mensal."""
    with traduzir_erros(sessao):
        competencias.enviar_documento_mensal(sessao, contrato_id, competencia_id, documento_id, *arquivo_pdf(arquivo), autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/consolidado", response_model=DetalheCompetencia, summary="Gerar documento consolidado",
               description="Um único PDF na ordem de execução (medição, avaliação, NFs, retenção, CADIN, checklist e, por último, o "
               "resumo executivo), com contracapa antes de cada documento enviado e páginas numeradas em sequência. "
               "Gerar novamente (já existe um consolidado) é só do gestor do contrato ou do SuperRoot, inclusive depois da OB (senão, 403).",
               responses={**NAO_ENCONTRADA, **ESCRITA})
def consolidado(contrato_id: uuid.UUID, competencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Etapa 6: gera o PDF consolidado com todos os documentos da competência."""
    with traduzir_erros(sessao):
        competencias.gerar_consolidado(sessao, contrato_id, competencia_id, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/ordem-bancaria", response_model=DetalheCompetencia, summary="Anexar OB e concluir",
               description="`multipart/form-data` (`arquivo`, PDF). Debita o valor autorizado nas NEs, na ordem escolhida, e conclui a competência.",
               responses={**NAO_ENCONTRADA, **ARQUIVO_RECUSADO, **SEM_VINCULO})
def ordem_bancaria(contrato_id: uuid.UUID, competencia_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                   autor: Usuario = Depends(pode_modificar)):
    """Etapa 7: anexa a OB, debita as NEs na ordem escolhida e conclui a competência."""
    with traduzir_erros(sessao):
        competencias.registrar_ordem_bancaria(sessao, contrato_id, competencia_id, *arquivo_pdf(arquivo), autor)
        return _depois(sessao, contrato_id, competencia_id, autor)


@roteador.post("/competencias/{competencia_id}/reabrir", response_model=DetalheCompetencia, summary="Reabrir etapa (SuperRoot ou gestor)",
               description="Volta para uma etapa anterior com justificativa e desfaz as conclusões posteriores. Se a competência "
               "estava paga, lança **estorno** dos débitos da OB no extrato das NEs (o pagamento original permanece). Anexos e "
               "histórico ficam guardados. Permitido ao SuperRoot e ao gestor vigente do contrato.", responses={**NAO_ENCONTRADA, **INVALIDO})
def reabrir(contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: Reabertura, sessao: Session = Depends(obter_sessao),
            autor: Usuario = Depends(pode_modificar)):
    """Volta a competência para uma etapa anterior, com justificativa registrada na auditoria."""
    with traduzir_erros(sessao):
        competencias.reabrir(sessao, contrato_id, competencia_id, dados, autor)
        return _depois(sessao, contrato_id, competencia_id, autor)
