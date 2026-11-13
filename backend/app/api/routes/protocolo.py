"""
===============================================================================
ARQUIVO: protocolo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Expor a API do Protocolo (/api/protocolo): tipos de documento, sequências de
numeração por exercício (ano), reserva e uso de números, anexação do
documento, sigilo, vínculo com contrato, painel e exportação.

RESUMO TÉCNICO:
Camada HTTP fina sobre app/services/servico_protocolo.py. Cada rota exige um
nível do recurso `protocolo` da ACL (lista de controle de acesso):
- LEITURA vê a numeração, o painel e a linha do tempo, e exporta;
- MODIFICACAO reserva o próximo número, anexa o documento do que reservou,
  libera a própria reserva, marca sigilo e vincula contrato;
- CONTROLE_TOTAL (ou o SuperRoot) cadastra tipos, cria e amplia sequências,
  lança um número específico e anula.
Erros do serviço (ErroProtocolo) viram a resposta padrão {detalhe, codigo}
pelo gerenciador de contexto _traduzir. _numero monta a leitura de um número
com as permissões de cada ação já calculadas para a tela.

FINALIDADE DE NEGÓCIO:
Substitui o caderno/planilha de numeração de documentos oficiais da SPI
(ofícios, portarias etc.): cada número é reservado por uma pessoa, com
finalidade, sem duplicidade, e fica registrado quem usou, quando e com qual
documento. A faixa "Reservado CGI" guarda o início da numeração para a
Coordenadoria de Gestão e Infraestrutura.

CONTEXTO NO SISTEMA:
Modelos em app/models/protocolo.py, schemas em app/schemas/protocolo.py,
anexos em app/services/servico_anexos.py. Números de RDM (requisição de
mudança) gerados pelas Tarefas usam um tipo "sistêmico" e consultam
app/services/tarefas/servico_rdm.py. Documentação em
docs/endpoints/protocolo.md; tela Protocolo no frontend.

===============================================================================
"""

import uuid
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.contratos import Contrato
from app.models.protocolo import NumeroProtocolo, TipoProtocolo
from app.models.usuario import Usuario
from app.schemas.protocolo import (
    ArquivoLeitura, EventoLeitura, GravacaoContrato, GravacaoFaixa, GravacaoSequencia, GravacaoSigilo, GravacaoTipo, ListaNumeros, ListaTipos, Motivo,
    NumeroLeitura, PainelProtocolo, PendentePainel, PessoaPainel, MesPainel, ReservaNumero, ReservaProximo, SequenciaLeitura, TipoLeitura,
)
from app.services import servico_anexos
from app.services import servico_protocolo as servico
from app.services.servico_protocolo import ErroProtocolo, formatar_numero

# APIRouter agrupa as rotas sob /protocolo. As três dependências abaixo (ver, operar, administrar)
# são criadas por exigir_acl: usadas em Depends(...), devolvem o usuário logado ou respondem 403 se
# ele não tiver o nível pedido no recurso `protocolo`.
roteador = APIRouter(prefix="/protocolo", tags=["Protocolo"], responses=VALIDACAO)
ver = exigir_acl(servico.RECURSO, NivelAcl.LEITURA)
operar = exigir_acl(servico.RECURSO, NivelAcl.MODIFICACAO)
administrar = exigir_acl(servico.RECURSO, NivelAcl.CONTROLE_TOTAL)
SEM_ADMIN = {status.HTTP_403_FORBIDDEN: {"description": "Sem CONTROLE_TOTAL em `protocolo` (`acl_negado`)."}}
NUMERO_NAO_ENCONTRADO = resposta_nao_encontrado("Número")


@contextmanager
def _traduzir(sessao: Session | None = None):
    """
    Gerenciador de contexto (usado com `with`) que converte erros do serviço em resposta
    HTTP.

    Quando o serviço levanta ErroProtocolo, desfaz a transação (rollback) se uma sessão
    foi passada e relança como ErroApi com o status e o código do erro, gerando o corpo
    padrão `{"detalhe", "codigo"}`. Rotas só de leitura chamam sem sessão.
    """
    try:
        yield
    except ErroProtocolo as erro:
        if sessao is not None:
            sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _sequencia(s) -> SequenciaLeitura:
    """
    Converte a sequência (faixa de números de um tipo num exercício) para o schema de
    resposta.
    """
    return SequenciaLeitura(id=s.id, exercicio=s.exercicio, inicio=s.inicio, fim=s.fim, liberar_a_partir_de=s.liberar_a_partir_de)


def _tipo(t: TipoProtocolo, pode_consumir: bool = True) -> TipoLeitura:
    """
    Converte um tipo de documento para o schema de resposta, com as sequências de todos
    os exercícios.

    `pode_consumir` diz se o usuário pode reservar números deste tipo (tipos restritos a
    um setor só aceitam reserva desse setor e da administração).
    """
    return TipoLeitura(id=t.id, nome=t.nome, setor_id=t.setor_id, setor_nome=t.setor.nome if t.setor else None, pode_consumir=pode_consumir, sequencias=[_sequencia(s) for s in t.sequencias])


def _numero(sessao: Session, n: NumeroProtocolo, usuario: Usuario, admin: bool, eventos: bool = False, contratos: dict | None = None, cgi: bool = False,
            rdms: dict | None = None) -> NumeroLeitura:
    """
    Monta a leitura completa de um número para a tela, já com as permissões de cada
    ação.

    Parâmetros: `admin` indica CONTROLE_TOTAL; `eventos` inclui a linha do tempo;
    `contratos` e `rdms` são caches (id -> dado) para a grade não fazer uma consulta por
    número; `cgi` indica que o usuário pode usar a faixa "Reservado CGI".

    Regras refletidas nos campos `pode_*`: tipo sistêmico (RDM SGI) não tem ação manual;
    anexar, liberar e concluir sem documento cabem a quem reservou ou à administração;
    sigilo cabe a quem reservou ou ao SuperRoot; o arquivo só pode ser baixado por quem
    tem permissão de ver documento sigiloso. Pode consultar o banco (contrato e RDM)
    quando os caches não vierem.
    """
    from app.services.tarefas import servico_rdm

    # Tipo numerado só pelo sistema (RDM SGI): sem ações manuais; mostra a situação da RDM e a tarefa
    sistemico = n.sequencia.tipo.nome_chave in servico.TIPOS_SISTEMICOS
    rdm = ((rdms if rdms is not None else servico_rdm.por_numero_protocolo(sessao, [n.id])).get(n.id)) if sistemico else None
    arquivo = None
    if n.anexo is not None and n.anexo.excluido_em is None:
        arquivo = ArquivoLeitura(id=n.anexo.id, nome=n.anexo.nome_original, tamanho=n.anexo.tamanho, pode_baixar=servico.pode_ver_documento(n, usuario))
    dono = n.reservado_por_id == usuario.id
    ativo = n.anulado_em is None
    contrato_numero = (contratos or {}).get(n.contrato_id) if n.contrato_id else None
    if n.contrato_id and contratos is None:
        contrato = sessao.get(Contrato, n.contrato_id)
        contrato_numero = contrato.numero if contrato else None
    return NumeroLeitura(
        id=n.id, sequencia_id=n.sequencia_id, tipo_id=n.sequencia.tipo_id, tipo_nome=n.sequencia.tipo.nome, exercicio=n.sequencia.exercicio, numero=n.numero,
        numero_formatado=servico_rdm.formatar(n.numero, n.sequencia.exercicio) if sistemico else formatar_numero(n.numero, n.sequencia.exercicio), estado=n.estado, finalidade=n.finalidade, reservado_por_id=n.reservado_por_id,
        reservado_por_nome=n.reservado_por_nome, reservado_em=n.reservado_em, usado_em=n.usado_em, contrato_id=n.contrato_id, contrato_numero=contrato_numero,
        sigiloso=n.sigiloso, anulado_em=n.anulado_em, motivo_anulacao=n.motivo_anulacao, arquivo=arquivo,
        pode_anexar=not sistemico and ativo and n.reservado_em is not None and n.anexo_id is None and (dono or admin),
        pode_liberar=not sistemico and n.estado == "reservado" and (dono or admin),
        pode_concluir_sem_documento=not sistemico and n.estado == "reservado" and (dono or admin),
        pode_alterar_sigilo=ativo and n.reservado_em is not None and (dono or usuario.superusuario),
        pode_reservar=not sistemico and n.estado in ("livre", "reservado_cgi") and (admin or (n.estado == "reservado_cgi" and cgi)),
        rdm_situacao=rdm[0] if rdm else None, tarefa_numero=rdm[1] if rdm else None,
        eventos=[EventoLeitura(tipo=e.tipo, autor_nome=e.autor_nome, texto=e.texto, ocorrido_em=e.ocorrido_em) for e in n.eventos] if eventos else [],
    )


# --- Tipos e sequências ---------------------------------------------------------------------

# Lista só os tipos que o usuário pode ver (pode_ver_tipo) e informa, por tipo, se ele pode reservar
# números (pode_consumir_tipo).
@roteador.get("/tipos", response_model=ListaTipos, summary="Tipos de documento e suas sequências",
              description="Os tipos que o usuário pode ver, com a sequência de cada exercício (tipo restrito a um setor só aparece para o setor, para a administração e para o Serviço de Apoio Administrativo). `pode_administrar` indica CONTROLE_TOTAL (ou SuperRoot).")
def listar_tipos(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> ListaTipos:
    return ListaTipos(pode_administrar=servico.controle_total(sessao, usuario), itens=[_tipo(t, servico.pode_consumir_tipo(sessao, t, usuario)) for t in servico.listar_tipos(sessao) if servico.pode_ver_tipo(sessao, t, usuario)])


# Cria o tipo e, opcionalmente, a sequência do primeiro exercício na mesma transação.
@roteador.post("/tipos", response_model=TipoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar tipo de documento",
               description="Só CONTROLE_TOTAL. Nome único (sem diferenciar maiúsculas): `409` se já existir. Com `sequencia`, cria também a faixa do primeiro exercício (com \"liberar a partir de\") na mesma transação. Com `setor_id`, só esse setor (e seus filhos) e a administração reservam números do tipo (`403` nos demais); sem setor, todos reservam.", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO})
def criar_tipo(dados: GravacaoTipo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> TipoLeitura:
    with _traduzir(sessao):
        sequencia = dados.sequencia.model_dump() if dados.sequencia else None
        return _tipo(servico.criar_tipo(sessao, dados.nome, usuario, sequencia, dados.setor_id))


# Sem description= no decorador: não colocar docstring aqui, pois ela viraria a descrição da rota no
# OpenAPI. Troca só o nome do tipo (o serviço confere duplicidade).
@roteador.put("/tipos/{tipo_id}", response_model=TipoLeitura, summary="Renomear tipo de documento", responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Tipo")})
def renomear_tipo(tipo_id: uuid.UUID, dados: GravacaoTipo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> TipoLeitura:
    with _traduzir(sessao):
        return _tipo(servico.renomear_tipo(sessao, tipo_id, dados.nome, usuario))


@roteador.delete("/tipos/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir tipo de documento",
                 description="Só tipos sem números reservados, utilizados ou anulados (`409` nos demais).", responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Tipo")})
def excluir_tipo(tipo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> Response:
    with _traduzir(sessao):
        servico.excluir_tipo(sessao, tipo_id, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Uma sequência é a faixa de números de um tipo em um exercício (ano). O serviço cria uma linha por
# número da faixa.
@roteador.post("/tipos/{tipo_id}/sequencias", response_model=SequenciaLeitura, status_code=status.HTTP_201_CREATED, summary="Criar a sequência de um exercício",
               description="Só CONTROLE_TOTAL. Cria os números da faixa (até 10.000); `liberar_a_partir_de` opcional reserva à CGI o início da faixa. Uma sequência por tipo e exercício (`409`).",
               responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **resposta_nao_encontrado("Tipo")})
def criar_sequencia(tipo_id: uuid.UUID, dados: GravacaoSequencia, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> SequenciaLeitura:
    with _traduzir(sessao):
        return _sequencia(servico.criar_sequencia(sessao, tipo_id, dados.exercicio, dados.inicio, dados.fim, usuario, dados.liberar_a_partir_de))


@roteador.put("/sequencias/{sequencia_id}/faixa", response_model=SequenciaLeitura, summary="Ampliar (ou encolher) a faixa",
              description="Só CONTROLE_TOTAL. `inicio` menor amplia para trás e `fim` maior amplia para frente (criando só os números novos). "
              "Encolher só vale para pontas livres e sem histórico (`409`).", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **resposta_nao_encontrado("Sequência")})
def alterar_faixa(sequencia_id: uuid.UUID, dados: GravacaoFaixa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> SequenciaLeitura:
    with _traduzir(sessao):
        return _sequencia(servico.alterar_faixa(sessao, sequencia_id, dados.inicio, dados.fim, usuario, dados.liberar_a_partir_de))


@roteador.delete("/sequencias/{sequencia_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir o exercício de um tipo",
                 description="Só CONTROLE_TOTAL. Apaga a faixa e os números do exercício, mas só se nenhum número foi reservado, utilizado ou anulado (`409`). Os demais exercícios do tipo não mudam.",
                 responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Sequência")})
def excluir_sequencia(sequencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> Response:
    with _traduzir(sessao):
        servico.excluir_sequencia(sessao, sequencia_id, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Números ------------------------------------------------------------------------------

@roteador.get("/sequencias/{sequencia_id}/numeros", response_model=ListaNumeros, summary="Números de uma sequência",
              description="A grade de números do tipo e exercício, com o estado de cada um e o que o usuário pode fazer.", responses=resposta_nao_encontrado("Sequência"))
def numeros(sequencia_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> ListaNumeros:
    with _traduzir():
        sequencia, itens = servico.numeros_da_sequencia(sessao, sequencia_id, usuario)
    admin = servico.controle_total(sessao, usuario)
    cgi = servico.pode_usar_reserva_cgi(sessao, usuario)
    # Busca de uma vez o número de todos os contratos vinculados na grade (evita uma consulta por
    # linha).
    contratos = {c.id: c.numero for c in sessao.query(Contrato).filter(Contrato.id.in_({n.contrato_id for n in itens if n.contrato_id}))} if any(n.contrato_id for n in itens) else {}
    for n in itens:
        n.sequencia = sequencia
    # RDM SGI: situação de todas as RDMs da grade numa consulta só
    from app.services.tarefas import servico_rdm

    rdms = servico_rdm.por_numero_protocolo(sessao, [n.id for n in itens]) if sequencia.tipo.nome_chave in servico.TIPOS_SISTEMICOS else None
    return ListaNumeros(sequencia=_sequencia(sequencia), tipo_id=sequencia.tipo_id, tipo_nome=sequencia.tipo.nome, pode_consumir=servico.pode_consumir_tipo(sessao, sequencia.tipo, usuario), pode_administrar=admin, usuario_id=usuario.id,
                        livres=sum(1 for n in itens if n.estado == "livre"), reservados_cgi=sum(1 for n in itens if n.estado == "reservado_cgi"), pode_usar_reserva_cgi=cgi,
                        itens=[_numero(sessao, n, usuario, admin, contratos=contratos, cgi=cgi, rdms=rdms) for n in itens])


# Rota mais usada do módulo: o serviço trava a sequência e pega o menor número livre, então duas
# pessoas nunca recebem o mesmo número.
@roteador.post("/sequencias/{sequencia_id}/proximo", response_model=NumeroLeitura, status_code=status.HTTP_201_CREATED, summary="Reservar o próximo número",
               description="Reserva o **menor número livre** da sequência, com a finalidade (e o contrato, se houver). Atômico: duas pessoas nunca recebem o mesmo. "
               "A faixa \"Reservado CGI\" só entra para quem é da Coordenadoria de Gestão e Infraestrutura, que começa por ela; os demais (inclusive a administração) recebem a partir do ponto de liberação. "
               "`409 sequencia_esgotada` quando não há mais livres.", responses={**CONFLITO, **INVALIDO, **resposta_nao_encontrado("Sequência")})
def reservar_proximo(sequencia_id: uuid.UUID, dados: ReservaProximo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.proximo(sessao, sequencia_id, dados.finalidade, dados.contrato_id, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True, cgi=servico.pode_usar_reserva_cgi(sessao, usuario))


@roteador.get("/numeros/{numero_id}", response_model=NumeroLeitura, summary="Detalhe de um número, com a linha do tempo",
              description="Dados do número e a **linha do tempo** (visível mesmo se o documento for sigiloso).", responses=NUMERO_NAO_ENCONTRADO)
def detalhe(numero_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> NumeroLeitura:
    with _traduzir():
        n = servico.obter(sessao, numero_id, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


@roteador.post("/numeros/{numero_id}/reservar", response_model=NumeroLeitura, summary="Lançar um número específico",
               description="CONTROLE_TOTAL escolhe qualquer número livre; a Coordenadoria de Gestão e Infraestrutura escolhe só entre os \"Reservado CGI\" (`403` nos demais casos). `409` se já foi reservado ou anulado.",
               responses={**CONFLITO, **INVALIDO, **NUMERO_NAO_ENCONTRADO, status.HTTP_403_FORBIDDEN: {"description": "Sem permissão para escolher este número (`sem_permissao`)."}})
def lancar(numero_id: uuid.UUID, dados: ReservaNumero, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.lancar(sessao, numero_id, dados.finalidade, dados.contrato_id, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True, cgi=True)


@roteador.post("/numeros/{numero_id}/concluir-sem-documento", response_model=NumeroLeitura, summary="Concluir a reserva sem subir o documento",
               description="Quem reservou ou a administração. Para documentos que não podem ser subidos (sigilosos, por exemplo): o número reservado passa a `utilizado` sem arquivo, com o motivo na linha do tempo (evento `concluiu`). "
                           "A justificativa (`motivo`) é obrigatória. `409` se o número já tem documento, não está reservado ou é de portaria de designação/admissão (exigem o PDF do D.O.E.). O documento ainda pode ser anexado depois.",
               responses={**CONFLITO, **INVALIDO, **NUMERO_NAO_ENCONTRADO, status.HTTP_403_FORBIDDEN: {"description": "Não é quem reservou nem a administração."}})
def concluir_sem_documento(numero_id: uuid.UUID, dados: Motivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.concluir_sem_documento(sessao, numero_id, dados.motivo, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


@roteador.post("/numeros/{numero_id}/liberar", response_model=NumeroLeitura, summary="Liberar uma reserva sem documento",
               description="Quem reservou ou a administração. Só número reservado e sem documento; volta a livre. Motivo obrigatório; o histórico permanece.",
               responses={**CONFLITO, **INVALIDO, **NUMERO_NAO_ENCONTRADO, status.HTTP_403_FORBIDDEN: {"description": "Não é quem reservou nem a administração."}})
def liberar(numero_id: uuid.UUID, dados: Motivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.liberar(sessao, numero_id, dados.motivo, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


@roteador.post("/numeros/{numero_id}/anular", response_model=NumeroLeitura, summary="Anular um número",
               description="Só CONTROLE_TOTAL. Tira o número de uso para sempre, com motivo obrigatório (o documento anexado fica guardado).",
               responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **NUMERO_NAO_ENCONTRADO})
def anular(numero_id: uuid.UUID, dados: Motivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.anular(sessao, numero_id, dados.motivo, usuario)
    return _numero(sessao, n, usuario, True, eventos=True)


@roteador.post("/numeros/{numero_id}/anexo", response_model=NumeroLeitura, summary="Anexar o documento",
               description="`multipart/form-data` com `arquivo` (PDF, Office/LibreOffice, TXT, CSV, PNG ou JPG). Só quem reservou ou a administração; o número passa a "
               "**utilizado** e não aceita outro documento.", responses={**CONFLITO, **INVALIDO, **NUMERO_NAO_ENCONTRADO})
def anexar(numero_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.anexar(sessao, numero_id, arquivo.file, arquivo.filename or "documento", usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


# Download do documento anexado: confere se existe arquivo ativo e se o usuário pode ver documento
# sigiloso antes de enviar o arquivo do disco.
@roteador.get("/numeros/{numero_id}/anexo", response_class=FileResponse, summary="Baixar o documento",
              description="**Documento sigiloso:** só quem reservou o número e o SuperRoot (`403 documento_sigiloso` para os demais).",
              responses={**NUMERO_NAO_ENCONTRADO, status.HTTP_403_FORBIDDEN: {"description": "Documento sigiloso (`documento_sigiloso`)."}})
def baixar(numero_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)):
    with _traduzir():
        n = servico.obter(sessao, numero_id, usuario)
    if n.anexo is None or n.anexo.excluido_em is not None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Este número não tem documento anexado.", "nao_encontrado")
    if not servico.pode_ver_documento(n, usuario):
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Este documento é sigiloso: só quem reservou o número e o SuperRoot podem abri-lo.", "documento_sigiloso")
    try:
        return servico_anexos.resposta_download(n.anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


@roteador.put("/numeros/{numero_id}/sigilo", response_model=NumeroLeitura, summary="Marcar ou desmarcar o sigilo do documento",
              description="Quem reservou o número ou o SuperRoot. Documento sigiloso: só o dono e o SuperRoot veem o arquivo; a linha do tempo continua visível.",
              responses={**CONFLITO, **NUMERO_NAO_ENCONTRADO})
def sigilo(numero_id: uuid.UUID, dados: GravacaoSigilo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.definir_sigilo(sessao, numero_id, dados.sigiloso, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


@roteador.put("/numeros/{numero_id}/contrato", response_model=NumeroLeitura, summary="Vincular o número a um contrato",
              description="Quem reservou ou a administração; exige acesso ao Módulo de Contratos. `contrato_id` nulo remove o vínculo.",
              responses={**CONFLITO, **NUMERO_NAO_ENCONTRADO})
def contrato(numero_id: uuid.UUID, dados: GravacaoContrato, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> NumeroLeitura:
    with _traduzir(sessao):
        n = servico.vincular_contrato(sessao, numero_id, dados.contrato_id, usuario)
    return _numero(sessao, n, usuario, servico.controle_total(sessao, usuario), eventos=True)


@roteador.get("/contratos/{contrato_id}", response_model=list[NumeroLeitura], summary="Documentos do Protocolo vinculados a um contrato",
              description="Números vinculados ao contrato (do mais recente ao mais antigo), para a ficha do contrato.")
def do_contrato(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[NumeroLeitura]:
    admin = servico.controle_total(sessao, usuario)
    return [_numero(sessao, n, usuario, admin) for n in servico.numeros_do_contrato(sessao, contrato_id, usuario)]


# --- Painel e exportação -----------------------------------------------------------------

# Painel anual de um tipo: o serviço devolve um dicionário com meses, ranking de pessoas e
# pendências, convertido aqui para os schemas de resposta.
@roteador.get("/painel", response_model=PainelProtocolo, summary="Painel do Protocolo",
              description="Reservas e utilizações por mês, top 10 pessoas e reservados sem documento, de um tipo e exercício.", responses={**INVALIDO, **resposta_nao_encontrado("Tipo")})
def painel(tipo_id: uuid.UUID = Query(...), ano: int = Query(..., ge=2000, le=2200), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> PainelProtocolo:
    with _traduzir():
        d = servico.painel(sessao, tipo_id, ano, usuario)
    return PainelProtocolo(
        tipo_id=d["tipo"].id, tipo_nome=d["tipo"].nome, ano=ano, meses=[MesPainel(**m) for m in d["meses"]],
        mais_reservaram=[PessoaPainel(usuario_id=p.usuario_id, nome=p.nome, quantidade=p.quantidade) for p in d["mais_reservaram"]],
        mais_utilizaram=[PessoaPainel(usuario_id=p.usuario_id, nome=p.nome, quantidade=p.quantidade) for p in d["mais_utilizaram"]],
        sem_documento=[PendentePainel(id=n.id, numero_formatado=formatar_numero(n.numero, n.sequencia.exercicio), finalidade=n.finalidade,
                                      reservado_por_nome=n.reservado_por_nome, reservado_em=n.reservado_em) for n in d["sem_documento"]],
    )


# Gera a planilha (XLSX) ou o PDF no serviço e devolve como anexo (Content-Disposition: attachment
# faz o navegador baixar o arquivo).
@roteador.get("/exportar", response_class=Response, summary="Exportar o controle (XLSX ou PDF)",
              description="Números com movimento (reservados, utilizados e anulados), com filtros opcionais por tipo e exercício. Não inclui o conteúdo dos documentos.",
              responses={200: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **INVALIDO})
def exportar(formato: Literal["xlsx", "pdf"] = "xlsx", tipo_id: uuid.UUID | None = None, exercicio: int | None = Query(None, ge=2000, le=2200),
             sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    with _traduzir():
        conteudo, nome, tipo = servico.exportar(sessao, tipo_id, exercicio, formato, usuario)
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
