# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de prorrogação, reajuste e aditamento/supressão do contrato.
"""Rotas de prorrogação, reajuste e aditamento/supressão (`/api/contratos/{contrato_id}/…`).

Os três são "atos" que mudam o contrato depois de assinado:
- **Prorrogação**: estende o prazo, criando uma nova vigência (Termo Aditivo).
- **Reajuste**: corrige os preços pelo índice do contrato (apostilamento), uma vez por vigência.
- **Aditamento/supressão**: aumenta ou diminui as quantidades dos itens, respeitando o limite
  legal de 25% (acima disso, exige autorização do Ordenador de Despesa).

Cada ato é montado como rascunho (várias gravações), recebe ciências e documentos e só altera o
contrato ao ser concluído/registrado. As rotas de escrita devolvem o painel do ato atualizado.
"""

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
    LeituraReajuste,
    AberturaAlteracao,
    AberturaReajuste,
    GravacaoDadosMinuta,
    GravacaoEnquadramento,
    GravacaoMemoriaReajuste,
    GravacaoPosAssinatura,
    GravacaoProrrogacao,
    GravacaoQuantitativos,
    LeituraEnquadramento,
    LeituraMinuta,
    LeituraMinutas,
    LeituraProcessoProrrogacao,
    LeituraProrrogacao,
    LeituraVigenciaRetroativa,
    PainelAlteracao,
    PainelReajuste,
)
from app.services.contratos import servico_alteracao, servico_pos_assinatura, servico_prorrogacao, servico_reajuste, servico_vigencia_retroativa

# As tags ficam em cada rota (e não no roteador) para separar os três grupos na documentação
roteador = APIRouter(prefix="/contratos/{contrato_id}", responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato")
# Conjuntos de respostas de erro documentadas, reutilizados nas rotas abaixo
ESCRITA = {**NAO_ENCONTRADO, **INVALIDO, **SEM_VINCULO}
UPLOAD = {**NAO_ENCONTRADO, **ARQUIVO_RECUSADO, **SEM_VINCULO}
PDF = {status.HTTP_200_OK: {"content": {"application/pdf": {}}}, **resposta_nao_encontrado("Arquivo")}
PRORROGACAO, REAJUSTE, ALTERACAO = ["Contratos: prorrogação"], ["Contratos: reajuste"], ["Contratos: aditamento e supressão"]


# ---------------------------------------------------------------------------------------------
# Vigência retroativa
# ---------------------------------------------------------------------------------------------

@roteador.get("/vigencias-retroativas", response_model=list[LeituraVigenciaRetroativa], tags=PRORROGACAO, summary="Vigências retroativas",
              description="Vigências anteriores ao início do contrato, da mais antiga para a mais recente. Só a mais antiga pode ser desfeita.",
              responses=NAO_ENCONTRADO)
def listar_vigencias_retroativas(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Vigências retroativas já cadastradas."""
    with traduzir_erros():
        return servico_vigencia_retroativa.listar(sessao, contrato_id, usuario)


@roteador.post("/vigencias-retroativas", response_model=list[LeituraVigenciaRetroativa], tags=PRORROGACAO, summary="Cadastrar vigência retroativa",
               description="`multipart/form-data`: `meses`, `assinada_em`, `numero_termo` (opcional) e `termo` (PDF). A nova vigência termina na véspera do "
               "início atual do contrato; o início do contrato recua, as vigências existentes são renumeradas (a mais antiga passa a ser a 1ª) e o "
               "termo entra nos documentos importantes (024+). A vigência retroativa gera competências como qualquer outra e serve de base para o "
               "reajuste retroativo.", responses=UPLOAD)
def cadastrar_vigencia_retroativa(
    contrato_id: uuid.UUID,
    meses: Annotated[int, Form(ge=1, le=600, description="Prazo da vigência retroativa, em meses (o limite do dia a dia é o parâmetro `maximo_meses_vigencia_retroativa`).")],
    assinada_em: Annotated[date, Form(description="Data de assinatura do Termo Aditivo.")],
    numero_termo: Annotated[str, Form(max_length=100)] = "",
    termo: UploadFile = File(...),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    """Cadastra a vigência retroativa assinada e devolve a lista atualizada."""
    with traduzir_erros(sessao):
        servico_vigencia_retroativa.registrar(sessao, contrato_id, meses, assinada_em, numero_termo, arquivo_pdf(termo), autor)
        return servico_vigencia_retroativa.listar(sessao, contrato_id, autor)


@roteador.delete("/vigencias-retroativas/{vigencia_id}", response_model=list[LeituraVigenciaRetroativa], tags=PRORROGACAO,
                 summary="Desfazer vigência retroativa",
                 description="Só a mais antiga e sem medição, reajuste ou aditamento/supressão. Devolve o início anterior ao contrato, apaga as "
                 "competências e a previsão da vigência e renumera as demais.", responses=ESCRITA)
def desfazer_vigencia_retroativa(contrato_id: uuid.UUID, vigencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Desfaz a vigência retroativa mais antiga."""
    with traduzir_erros(sessao):
        servico_vigencia_retroativa.desfazer(sessao, contrato_id, vigencia_id, autor)
        return servico_vigencia_retroativa.listar(sessao, contrato_id, autor)


# ---------------------------------------------------------------------------------------------
# Prorrogação
# ---------------------------------------------------------------------------------------------

@roteador.get("/prorrogacao", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Rascunho da prorrogação",
              description="Dados da tela de prorrogação: prazo, nova vigência calculada, itens sob demanda, memória de cálculo (meses, totais por ano, "
              "meses quebrados com as duas opções e versões geradas), checklist da prorrogação e, das telas antigas, parecer e ciências.", responses=NAO_ENCONTRADO)
def consultar_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Rascunho da prorrogação em andamento (ou vazio, se nenhuma foi iniciada)."""
    with traduzir_erros():
        return servico_prorrogacao.consultar(sessao, contrato_id, usuario)


@roteador.put("/prorrogacao", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Salvar rascunho da prorrogação",
              description="Prazo (a soma não passa da vigência máxima), regra e grade dos itens sob demanda (limite ≤ original) e `calculo_mes_quebrado` "
              "(`pro_rata` ou `integral`, para os meses quebrados da nova vigência; nulo mantém). Campos do parecer não enviados ficam como estão; alterar o "
              "parecer depois de ciências as apaga. Ao criar o rascunho, copia o checklist do modelo \"Checklist Prorrogação\" ativo.", responses=ESCRITA)
def salvar_prorrogacao(contrato_id: uuid.UUID, dados: GravacaoProrrogacao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Grava o rascunho; o serviço valida o prazo contra a vigência máxima do contrato."""
    with traduzir_erros(sessao):
        servico_prorrogacao.salvar(sessao, contrato_id, dados, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.delete("/prorrogacao", status_code=status.HTTP_204_NO_CONTENT, tags=PRORROGACAO, summary="Descartar rascunho da prorrogação", responses=ESCRITA)
def descartar_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)) -> Response:
    """Descarta o rascunho da prorrogação sem alterar o contrato."""
    with traduzir_erros(sessao):
        servico_prorrogacao.descartar_rascunho(sessao, contrato_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/prorrogacao/memoria/arquivos", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Gerar a memória de cálculo da prorrogação",
               description="PDF e XLSX: capa \"Prorrogação de dd/mm/aaaa a dd/mm/aaaa\", tabela mês a mês (itens contínuos, sob demanda planejado e total), total "
               "por ano e total da nova vigência. Nova versão só se os dados mudaram. `400` sem prazo ou com mês quebrado sem `calculo_mes_quebrado`.", responses=ESCRITA)
def memoria_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Gera (ou reaproveita) a memória de cálculo da prorrogação em rascunho."""
    with traduzir_erros(sessao):
        servico_prorrogacao.gerar_memoria(sessao, contrato_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


# Antes de `checklist/{documento_id}`: senão "incluir" seria lido como id do documento
@roteador.post("/prorrogacao/checklist/incluir", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Incluir documento no checklist da prorrogação",
               description="`multipart/form-data` (`nome`, `descricao` opcional e `arquivo` PDF). O checklist padrão é o ponto de partida: o incluído vale só para esta "
               "prorrogação, **nunca é obrigatório** e pode ser excluído. `400` sem nome.", responses={**ESCRITA, **ARQUIVO_RECUSADO})
def incluir_documento_prorrogacao(contrato_id: uuid.UUID, nome: str = Form(..., max_length=500), descricao: str = Form("", max_length=1000), arquivo: UploadFile = File(...),
                                  sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Inclui um documento fora do modelo no checklist da prorrogação."""
    with traduzir_erros(sessao):
        servico_prorrogacao.incluir_documento(sessao, contrato_id, nome, descricao, *arquivo_pdf(arquivo), autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.post("/prorrogacao/checklist/{documento_id}", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Anexar documento do checklist da prorrogação",
               description="`multipart/form-data` (`arquivo`, PDF). Substitui o anterior. Os obrigatórios sem PDF impedem registrar a prorrogação.",
               responses={**ESCRITA, **ARQUIVO_RECUSADO})
def anexar_documento_prorrogacao(contrato_id: uuid.UUID, documento_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                                 autor: Usuario = Depends(pode_modificar)):
    """Anexa o PDF de um documento do checklist da prorrogação."""
    with traduzir_erros(sessao):
        servico_prorrogacao.anexar_documento(sessao, contrato_id, documento_id, *arquivo_pdf(arquivo), autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.delete("/prorrogacao/checklist/{documento_id}", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Excluir documento incluído no checklist da prorrogação",
                 description="Só para documento incluído durante o processo; os do checklist padrão não saem (`400`). O arquivo é descartado (exclusão lógica).",
                 responses=ESCRITA)
def excluir_documento_prorrogacao(contrato_id: uuid.UUID, documento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Exclui um documento incluído no checklist da prorrogação."""
    with traduzir_erros(sessao):
        servico_prorrogacao.excluir_documento(sessao, contrato_id, documento_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.get("/prorrogacao/minutas", response_model=LeituraMinutas, tags=PRORROGACAO, summary="Minutas e despachos da prorrogação",
              description="Documentos que o SGI escreve para o processo da prorrogação (minuta do termo aditivo, Termo de Ciência, Declaração de Atendimento, declaração do TCE e os dois despachos), com o que ainda falta digitar em cada um, e os dados que os completam (os que a equipe digita e os que o SGI calcula). A Declaração de Atendimento sai da modalidade cadastrada no contrato. Exige ACL `contratos` ≥ LEITURA.",
              responses=NAO_ENCONTRADO)
def listar_minutas_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Panorama das minutas da prorrogação em andamento."""
    with traduzir_erros(sessao):
        return servico_prorrogacao.minutas(sessao, contrato_id)


@roteador.get("/prorrogacao/minutas/{variante}", response_model=LeituraMinuta, tags=PRORROGACAO, summary="Texto de uma minuta da prorrogação",
              description="HTML da minuta preenchido com os dados do contrato e da prorrogação, pronto para copiar para o SEI. Dado que falta aparece como `[rótulo]` no texto e na lista `lacunas`. `404` se a variante não existe ou não há modelo ativo em Contratos › Modelos.",
              responses=NAO_ENCONTRADO)
def minuta_prorrogacao(contrato_id: uuid.UUID, variante: str, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Texto de uma minuta."""
    with traduzir_erros(sessao):
        return servico_prorrogacao.minuta(sessao, contrato_id, variante)


@roteador.put("/prorrogacao/dados-minuta", response_model=LeituraMinutas, tags=PRORROGACAO, summary="Salvar os dados digitados das minutas",
              description="Grava o que a equipe digitou para completar as minutas (testemunhas, nº dos documentos do SEI, dotação…), ou a correção de um valor que o SGI calculou. Substitui o conjunto anterior. Cria o rascunho da prorrogação se ainda não existir. `400` para dado desconhecido.",
              responses=ESCRITA)
def salvar_dados_minuta_prorrogacao(contrato_id: uuid.UUID, dados: GravacaoDadosMinuta, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Salva os dados digitados das minutas."""
    with traduzir_erros(sessao):
        return servico_prorrogacao.salvar_dados_minuta(sessao, contrato_id, dados, autor)


@roteador.get("/prorrogacao/enquadramento", response_model=LeituraEnquadramento, tags=PRORROGACAO, summary="Checklist do Parecer Referencial",
              description="Os 37 itens da lista de verificação do Parecer Referencial NLC nº 1/2026, em nove grupos, com a resposta da equipe, a conferência automática do SGI (com a conta) e o que vale em cada item. `precisa_analise_juridica` é verdadeiro se algum item vale `nao`: o caso sai do Parecer Referencial e precisa da Consultoria Jurídica (só avisa, não bloqueia o registro). Exige ACL `contratos` ≥ LEITURA.",
              responses=NAO_ENCONTRADO)
def enquadramento_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Checklist do Parecer Referencial da prorrogação em andamento."""
    with traduzir_erros(sessao):
        return servico_prorrogacao.enquadramento(sessao, contrato_id)


@roteador.put("/prorrogacao/enquadramento", response_model=LeituraEnquadramento, tags=PRORROGACAO, summary="Salvar as respostas do checklist do Parecer Referencial",
              description="Grava as respostas por número do item (1 a 37), substituindo as anteriores; cria o rascunho da prorrogação se ainda não existir. `400` para item desconhecido.",
              responses=ESCRITA)
def salvar_enquadramento_prorrogacao(contrato_id: uuid.UUID, dados: GravacaoEnquadramento, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Salva as respostas do checklist."""
    with traduzir_erros(sessao):
        return servico_prorrogacao.salvar_enquadramento(sessao, contrato_id, dados, autor)


@roteador.get("/prorrogacao/enquadramento/planilha", response_class=Response, tags=PRORROGACAO, summary="Baixar o checklist do Parecer Referencial (XLSX)",
              description="O checklist no formato do Modelo 6 da SPI, com as respostas, os documentos e as observações preenchidos. Exige ACL `contratos` ≥ LEITURA.",
              responses={status.HTTP_200_OK: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **NAO_ENCONTRADO})
def planilha_enquadramento_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Planilha do checklist."""
    with traduzir_erros(sessao):
        conteudo, nome = servico_prorrogacao.planilha_enquadramento(sessao, contrato_id)
    return Response(conteudo, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.post("/prorrogacao/ciencia", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Registrar minha ciência no parecer",
               description="Opcional; qualquer integrante vigente da equipe, uma vez por pessoa.", responses=ESCRITA)
def ciencia_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Registra a ciência do usuário no parecer (opcional na prorrogação)."""
    with traduzir_erros(sessao):
        servico_prorrogacao.registrar_ciencia(sessao, contrato_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.post("/prorrogacao/parecer", response_model=LeituraProcessoProrrogacao, tags=PRORROGACAO, summary="Emitir PDF do parecer",
               description="Só quando algum campo do parecer está preenchido; inclui as ciências registradas até o momento.", responses=ESCRITA)
def parecer_prorrogacao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Gera o PDF do parecer com as ciências registradas até agora."""
    with traduzir_erros(sessao):
        servico_prorrogacao.gerar_parecer(sessao, contrato_id, autor)
        return servico_prorrogacao.consultar(sessao, contrato_id, autor)


@roteador.post("/prorrogacao/registrar", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Registrar prorrogação",
               description="`multipart/form-data`: `assinada_em`, `numero_termo` (opcional) e `termo` (PDF). Cria a nova vigência, anexa o termo "
               "aos documentos (024+) e grava a previsão sob demanda da nova vigência. Com parecer, emite o PDF final. `400` se há mês quebrado sem "
               "`calculo_mes_quebrado`, se a memória de cálculo não foi gerada com os dados atuais ou se falta PDF em documento obrigatório do checklist.", responses=UPLOAD)
def registrar_prorrogacao(
    contrato_id: uuid.UUID,
    assinada_em: Annotated[date, Form(description="Data de assinatura do Termo Aditivo.")],
    numero_termo: Annotated[str, Form(max_length=100)] = "",
    termo: UploadFile = File(...),
    sessao: Session = Depends(obter_sessao),
    autor: Usuario = Depends(pode_modificar),
):
    """Registra a prorrogação assinada: cria a nova vigência e anexa o Termo Aditivo aos documentos."""
    with traduzir_erros(sessao):
        servico_prorrogacao.registrar(sessao, contrato_id, assinada_em, numero_termo, arquivo_pdf(termo), autor)
        return servico_prorrogacao.listar(sessao, contrato_id, autor)


@roteador.get("/prorrogacoes", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Histórico de prorrogações", responses=NAO_ENCONTRADO)
def listar_prorrogacoes(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Prorrogações já registradas, da mais recente para a mais antiga."""
    with traduzir_erros():
        return servico_prorrogacao.listar(sessao, contrato_id, usuario)


@roteador.get("/prorrogacoes/arquivos/{anexo_id}", response_class=FileResponse, tags=PRORROGACAO, summary="Baixar termo ou parecer da prorrogação",
              description="Termo aditivo ou parecer (PDF) de uma prorrogação registrada, ou o parecer do rascunho.", responses=PDF)
def arquivo_prorrogacao(contrato_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Baixa o termo ou o parecer de uma prorrogação."""
    with traduzir_erros():
        return servico_prorrogacao.arquivo(sessao, contrato_id, anexo_id)


@roteador.put("/prorrogacoes/{prorrogacao_id}/pos-assinatura", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Registrar o pós-assinatura da prorrogação",
              description="Grava as datas e dados do que vem depois da assinatura: divulgação no PNCP (data e número), publicação no DOE, comprovação da garantia e envio dos dados à DOF, atualização do Contratos.gov e os dados digitados das planilhas de garantia. Substitui o que havia; datas anteriores à assinatura são recusadas (`400`). Devolve o histórico de prorrogações com as situações recalculadas.",
              responses={**ESCRITA, **resposta_nao_encontrado("Prorrogação")})
def pos_assinatura_prorrogacao(contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, dados: GravacaoPosAssinatura, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Registra PNCP, DOE, garantia e Contratos.gov da prorrogação."""
    with traduzir_erros(sessao):
        servico_prorrogacao.atualizar_pos_assinatura(sessao, contrato_id, prorrogacao_id, dados, autor)
        return servico_prorrogacao.listar(sessao, contrato_id, autor)


@roteador.get("/prorrogacoes/{prorrogacao_id}/garantia/planilha", response_class=Response, tags=PRORROGACAO, summary="Baixar a planilha de dados de garantia para a DOF",
              description="Planilha XLSX (Modelo 9 da SPI para caução em dinheiro; Modelo 10 para seguro, fiança e demais), preenchida com o contrato, a prorrogação, a garantia cadastrada e os dados digitados. `400` se o contrato não tem garantia cadastrada. Exige ACL `contratos` ≥ LEITURA.",
              responses={status.HTTP_200_OK: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **ESCRITA})
def planilha_garantia_prorrogacao(contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Planilha de garantia."""
    with traduzir_erros(sessao):
        conteudo, nome = servico_pos_assinatura.planilha_garantia(sessao, contrato_id, prorrogacao_id)
    return Response(conteudo, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.delete("/prorrogacoes/{prorrogacao_id}", response_model=list[LeituraProrrogacao], tags=PRORROGACAO, summary="Desfazer última prorrogação",
                 description="Só a mais recente. Depois de gerada a execução da nova vigência, só o SuperRoot (e sem medição registrada).",
                 responses=ESCRITA)
def desfazer_prorrogacao(contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Desfaz a última prorrogação (só a mais recente, para não deixar buracos entre vigências)."""
    with traduzir_erros(sessao):
        servico_prorrogacao.desfazer(sessao, contrato_id, prorrogacao_id, autor)
        return servico_prorrogacao.listar(sessao, contrato_id, autor)


# ---------------------------------------------------------------------------------------------
# Reajuste
# ---------------------------------------------------------------------------------------------

@roteador.get("/reajustes", response_model=PainelReajuste, tags=REAJUSTE, summary="Reajuste em elaboração e histórico", responses=NAO_ENCONTRADO)
def painel_reajuste(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Reajuste em elaboração (se houver) e os já concluídos ou cancelados."""
    with traduzir_erros():
        return servico_reajuste.painel(sessao, contrato_id, usuario)


@roteador.post("/reajustes", response_model=PainelReajuste, status_code=status.HTTP_201_CREATED, tags=REAJUSTE, summary="Abrir reajuste",
               description="Data de efeito e vigência ainda não reajustada. Um reajuste em elaboração por vez. Com `retroativo`, a vigência é uma retroativa "
               "(da mais recente para a mais antiga), a data de efeito é o início da vigência seguinte e o preço novo é o anterior ÷ (1 + índice), com o "
               "valor referencial como piso.", responses={**ESCRITA, **CONFLITO})
def abrir_reajuste(contrato_id: uuid.UUID, dados: AberturaReajuste, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Abre um reajuste para uma vigência; 409 se já houver outro em elaboração."""
    with traduzir_erros(sessao):
        servico_reajuste.abrir(sessao, contrato_id, dados, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/evidencia", response_model=PainelReajuste, tags=REAJUSTE, summary="Anexar evidência do índice",
               description="`multipart/form-data` (`arquivo`, PDF). Substitui a anterior.", responses=UPLOAD)
def evidencia_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                       autor: Usuario = Depends(pode_modificar)):
    """Anexa o PDF que comprova o índice usado (ex.: publicação do IPCA)."""
    with traduzir_erros(sessao):
        servico_reajuste.anexar_evidencia(sessao, contrato_id, reajuste_id, *arquivo_pdf(arquivo), autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.put("/reajustes/{reajuste_id}/memoria", response_model=PainelReajuste, tags=REAJUSTE, summary="Salvar memória de cálculo",
              description="Índice (%) e valor referencial (teto opcional) por item. Recalcula preços, bases e valores globais. "
                          "`calculo_mes_quebrado` grava como calcular os meses quebrados pela data de efeito, uma escolha para todos os meses e itens: "
                          "`pro_rata` (dias antes do efeito sem reajuste, a partir dele reajustados) ou `integral` (mês inteiro reajustado). "
                          "Nulo mantém a escolha atual; `400` se o reajuste não tem mês quebrado.",
              responses=ESCRITA)
def memoria_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, sessao: Session = Depends(obter_sessao),
                     autor: Usuario = Depends(pode_modificar)):
    """Grava o índice, os tetos por item e o cálculo dos meses quebrados; o serviço recalcula os novos preços."""
    with traduzir_erros(sessao):
        servico_reajuste.salvar_memoria(sessao, contrato_id, reajuste_id, dados, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/memoria/previa", response_model=LeituraReajuste, tags=REAJUSTE, summary="Prévia da memória de cálculo (calculadora)",
               description="Mesmo corpo de `PUT …/memoria` (índice e teto por item, mais `calculo_mes_quebrado`), mas **não grava nada**: devolve o reajuste como ficaria com esses valores (novos preços, base e valor global, "
               "diferença retroativa e `resumo_meses`), para a tela recalcular enquanto a pessoa digita. `resumo_meses.meses_quebrados` já traz as duas opções calculadas, período a período. Só reajuste em elaboração (`400` nos demais casos).",
               responses=ESCRITA)
def previa_memoria_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, dados: GravacaoMemoriaReajuste, sessao: Session = Depends(obter_sessao),
                            autor: Usuario = Depends(pode_modificar)):
    """Calcula sem gravar."""
    with traduzir_erros(sessao):
        return servico_reajuste.previa_memoria(sessao, contrato_id, reajuste_id, dados, autor)


@roteador.post("/reajustes/{reajuste_id}/memoria/arquivos", response_model=PainelReajuste, tags=REAJUSTE, summary="Gerar memória em PDF e XLSX",
               description="Nova versão só se os dados mudaram. Com mês quebrado pela data de efeito, inclui a opção escolhida e a memória período a período. "
                           "`400` (`invalido`) se há mês quebrado e o cálculo dele (`calculo_mes_quebrado`) ainda não foi escolhido.", responses=ESCRITA)
def arquivos_memoria_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Gera a memória de cálculo do reajuste em PDF e em planilha."""
    with traduzir_erros(sessao):
        servico_reajuste.gerar_arquivos_memoria(sessao, contrato_id, reajuste_id, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/concluir", response_model=PainelReajuste, tags=REAJUSTE, summary="Concluir e aplicar reajuste",
               description="`multipart/form-data` com o apostilamento assinado (`arquivo`). Atualiza preços, competências não medidas e valor global.",
               responses=UPLOAD)
def concluir_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(pode_modificar)):
    """Conclui com o apostilamento assinado e aplica os novos preços ao contrato."""
    with traduzir_erros(sessao):
        servico_reajuste.concluir(sessao, contrato_id, reajuste_id, *arquivo_pdf(arquivo), autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.post("/reajustes/{reajuste_id}/cancelar", response_model=PainelReajuste, tags=REAJUSTE, summary="Cancelar reajuste", responses=ESCRITA)
def cancelar_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Cancela o reajuste em elaboração sem alterar o contrato."""
    with traduzir_erros(sessao):
        servico_reajuste.cancelar(sessao, contrato_id, reajuste_id, autor)
        return servico_reajuste.painel(sessao, contrato_id, autor)


@roteador.get("/reajustes/{reajuste_id}/arquivos/{anexo_id}", response_class=FileResponse, tags=REAJUSTE, summary="Baixar arquivo do reajuste", responses=PDF)
def arquivo_reajuste(contrato_id: uuid.UUID, reajuste_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Baixa um arquivo do reajuste (evidência, memória ou apostilamento)."""
    with traduzir_erros():
        return servico_reajuste.arquivo(sessao, contrato_id, reajuste_id, anexo_id)


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão
# ---------------------------------------------------------------------------------------------

@roteador.get("/alteracoes", response_model=PainelAlteracao, tags=ALTERACAO, summary="Aditamento/supressão em andamento e histórico", responses=NAO_ENCONTRADO)
def painel_alteracao(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    """Aditamento/supressão em andamento (se houver) e o histórico, com os percentuais acumulados."""
    with traduzir_erros():
        return servico_alteracao.painel(sessao, contrato_id, usuario)


@roteador.post("/alteracoes", response_model=PainelAlteracao, status_code=status.HTTP_201_CREATED, tags=ALTERACAO, summary="Iniciar aditamento ou supressão",
               description="Tipo, vigência e mês de efeito. Uma alteração em andamento por vez.", responses={**ESCRITA, **CONFLITO})
def abrir_alteracao(contrato_id: uuid.UUID, dados: AberturaAlteracao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Inicia um aditamento ou uma supressão; 409 se já houver outro em andamento."""
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
    """Anexa um dos documentos do processo; o `tipo` define qual."""
    with traduzir_erros(sessao):
        servico_alteracao.anexar(sessao, contrato_id, alteracao_id, tipo, *arquivo_pdf(arquivo), autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.put("/alteracoes/{alteracao_id}/quantitativos", response_model=PainelAlteracao, tags=ALTERACAO, summary="Salvar quantitativos e enviar para ciência",
              description="Nova quantidade por item; calcula o impacto em R$ e %. Supressão não fica abaixo do executado.", responses=ESCRITA)
def quantitativos(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, dados: GravacaoQuantitativos, sessao: Session = Depends(obter_sessao),
                  autor: Usuario = Depends(pode_modificar)):
    """Grava as novas quantidades por item e calcula o impacto financeiro."""
    with traduzir_erros(sessao):
        servico_alteracao.salvar_quantitativos(sessao, contrato_id, alteracao_id, dados, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/ciencia", response_model=PainelAlteracao, tags=ALTERACAO, summary="Registrar minha ciência",
               description="Uma ciência de integrante da equipe já libera a memória e a formalização.", responses=ESCRITA)
def ciencia_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Registra a ciência do usuário (uma ciência já basta para avançar)."""
    with traduzir_erros(sessao):
        servico_alteracao.registrar_ciencia(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/memoria", response_model=PainelAlteracao, tags=ALTERACAO, summary="Gerar memória (PDF e XLSX)",
               description="Liberada com as ciências mínimas.", responses=ESCRITA)
def memoria_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Gera a memória de cálculo da alteração em PDF e em planilha."""
    with traduzir_erros(sessao):
        servico_alteracao.gerar_memoria(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/consolidado", response_model=PainelAlteracao, tags=ALTERACAO, summary="Gerar documento consolidado",
               description="Justificativa, autorização, memória e De Acordo em um PDF.", responses=ESCRITA)
def consolidado_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Junta os documentos da alteração em um único PDF."""
    with traduzir_erros(sessao):
        servico_alteracao.gerar_consolidado(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/concluir", response_model=PainelAlteracao, tags=ALTERACAO, summary="Concluir e aplicar alteração",
               description="Exige ciências, De Acordo, Termo Aditivo e, acima de 25% acumulado, a autorização do Ordenador.", responses=ESCRITA)
def concluir_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Conclui a alteração e aplica as novas quantidades e valores ao contrato."""
    with traduzir_erros(sessao):
        servico_alteracao.concluir(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.post("/alteracoes/{alteracao_id}/cancelar", response_model=PainelAlteracao, tags=ALTERACAO, summary="Cancelar alteração", responses=ESCRITA)
def cancelar_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    """Cancela a alteração em andamento sem mudar o contrato."""
    with traduzir_erros(sessao):
        servico_alteracao.cancelar(sessao, contrato_id, alteracao_id, autor)
        return servico_alteracao.painel(sessao, contrato_id, autor)


@roteador.get("/alteracoes/{alteracao_id}/arquivos/{anexo_id}", response_class=FileResponse, tags=ALTERACAO, summary="Baixar arquivo da alteração", responses=PDF)
def arquivo_alteracao(contrato_id: uuid.UUID, alteracao_id: uuid.UUID, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    """Baixa um arquivo da alteração."""
    with traduzir_erros():
        return servico_alteracao.arquivo(sessao, contrato_id, alteracao_id, anexo_id)
