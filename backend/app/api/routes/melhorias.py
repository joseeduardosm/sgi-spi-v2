# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Módulo Melhorias (envio de sugestões, "Minhas sugestões" e triagem).
"""Rotas `/api/melhorias`.

- **Qualquer usuário logado:** envia sugestões (com prints) e acompanha as próprias.
- **Triagem (SuperRoot ou CONTROLE_TOTAL em `melhorias`):** lista, trata, converte em tarefa e exporta (XLSX e PDF).
"""

import uuid
from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.melhorias import SugestaoMelhoria
from app.models.usuario import Usuario
from app.schemas.melhorias import (
    ConversaoTarefa, EventoLeitura, GravacaoSugestao, PaginaSugestoesAutor, PaginaSugestoesTriagem, PodeTriar, PrintLeitura, SugestaoAutor,
    SugestaoTriagem, TratamentoSugestao,
)
from app.services import servico_anexos
from app.services import servico_melhorias as servico
from app.services.servico_melhorias import ErroMelhoria, Filtros

roteador = APIRouter(prefix="/melhorias", tags=["Melhorias"], responses=VALIDACAO)
SEM_TRIAGEM = {status.HTTP_403_FORBIDDEN: {"description": "Sem CONTROLE_TOTAL em `melhorias` (`acl_negado`)."}}
NAO_ENCONTRADA = resposta_nao_encontrado("Sugestão")
SITUACAO = "^(nova|em_analise|aceita|recusada|concluida)$"


@contextmanager
def _traduzir(sessao: Session | None = None):
    try:
        yield
    except ErroMelhoria as erro:
        if sessao is not None:
            sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _prints(s: SugestaoMelhoria) -> list[PrintLeitura]:
    return [PrintLeitura(id=a.anexo.id, nome=a.anexo.nome_original, tamanho=a.anexo.tamanho, url=f"/api/melhorias/sugestoes/{s.numero}/prints/{a.anexo.id}")
            for a in s.anexos if a.anexo.excluido_em is None]


def _autor(s: SugestaoMelhoria) -> SugestaoAutor:
    return SugestaoAutor(id=s.id, numero=s.numero, texto=s.texto, tela=s.tela, modulo=s.modulo, situacao=s.situacao,
                         resposta_publica=s.resposta_publica, criado_em=s.criado_em, atualizado_em=s.atualizado_em, prints=_prints(s))


def _triagem(sessao: Session, s: SugestaoMelhoria) -> SugestaoTriagem:
    return SugestaoTriagem(
        **_autor(s).model_dump(), autor_id=s.autor_id, autor_nome=s.autor_nome, autor_login=s.autor_login, observacao_interna=s.observacao_interna,
        atualizado_por_nome=s.atualizado_por_nome, tarefa_numero=servico.numero_da_tarefa(sessao, s),
        eventos=[EventoLeitura.model_validate(e, from_attributes=True) for e in s.eventos],
    )


def _usuario_triagem(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Usuario:
    with _traduzir():
        servico.exigir_triagem(sessao, usuario)
    return usuario


def _filtros(busca: str = Query("", max_length=200), situacao: str | None = Query(None, pattern=SITUACAO), modulo: str | None = Query(None, max_length=40),
             inicio: date | None = None, fim: date | None = None) -> Filtros:
    if inicio and fim and inicio > fim:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "O início do período é depois do fim.", "invalido")
    return Filtros(busca=busca, situacao=situacao, modulo=modulo, inicio=inicio, fim=fim)


# ---------------------------------------------------------------------------------------------
# Qualquer usuário logado
# ---------------------------------------------------------------------------------------------

@roteador.get("/acesso", response_model=PodeTriar, summary="O usuário faz a triagem?",
              description="Para a tela mostrar a aba Triagem: SuperRoot ou CONTROLE_TOTAL em `melhorias` (sem regras no recurso, só o SuperRoot).")
def acesso(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PodeTriar:
    return PodeTriar(triagem=servico.faz_triagem(sessao, usuario))


@roteador.post("/sugestoes", response_model=SugestaoAutor, status_code=status.HTTP_201_CREATED, summary="Enviar sugestão de melhoria",
               description="`multipart/form-data`: `dados` (JSON de `GravacaoSugestao`: texto até 4.000 caracteres e a tela de origem) e até 3 "
                           "`arquivos` (prints PNG, JPG ou WebP, conferidos pelo conteúdo). Quem faz a triagem recebe aviso na caixa de Mensagens, "
                           "com e-mail.", responses={**INVALIDO})
async def enviar(dados: str = Form(..., description="JSON de `GravacaoSugestao`."), arquivos: list[UploadFile] = File(default_factory=list),
                 sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> SugestaoAutor:
    try:
        gravacao = GravacaoSugestao.model_validate_json(dados)
    except ValidationError as erro:
        mensagem = erro.errors()[0].get("msg", "Dados inválidos.").removeprefix("Value error, ")
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem, "validacao") from erro
    conteudos = [(a.filename or "print.png", await a.read()) for a in arquivos if a.filename]
    with _traduzir(sessao):
        sugestao = servico.registrar(sessao, usuario, gravacao.texto, gravacao.tela, conteudos)
    sessao.commit()
    return _autor(sugestao)


@roteador.get("/minhas", response_model=PaginaSugestoesAutor, summary="Minhas sugestões",
              description="Sugestões do usuário logado, da mais recente para a mais antiga, com a situação e a resposta da equipe "
                          "(sem a observação interna).")
def minhas(pagina: int = Query(1, ge=1), tamanho: int = Query(20, ge=1, le=100), sessao: Session = Depends(obter_sessao),
           usuario: Usuario = Depends(obter_usuario_atual)) -> PaginaSugestoesAutor:
    itens, total = servico.minhas(sessao, usuario, pagina, tamanho)
    return PaginaSugestoesAutor(itens=[_autor(s) for s in itens], total=total, pagina=pagina, tamanho=tamanho)


@roteador.get("/minhas/{numero}", response_model=SugestaoAutor, summary="Uma das minhas sugestões",
              description="Sugestão de outra pessoa → 404.", responses={**NAO_ENCONTRADA})
def minha(numero: int, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> SugestaoAutor:
    with _traduzir():
        return _autor(servico.do_autor(sessao, usuario, numero))


@roteador.get("/sugestoes/{numero}/prints/{anexo_id}", response_class=FileResponse, summary="Baixar print da sugestão",
              description="O autor da sugestão ou quem faz a triagem; os demais → 404.", responses={**NAO_ENCONTRADA})
def baixar_print(numero: int, anexo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)):
    with _traduzir():
        item = servico.print_para_download(sessao, usuario, numero, anexo_id)
    try:
        return servico_anexos.resposta_download(item.anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


# ---------------------------------------------------------------------------------------------
# Triagem
# ---------------------------------------------------------------------------------------------

@roteador.get("/sugestoes", response_model=PaginaSugestoesTriagem, summary="Triagem: listar sugestões",
              description="Filtros: `busca` (texto, autor, login, tela ou número), `situacao`, `modulo` e período de envio (`inicio`/`fim`, "
                          "dias inclusivos). `totais` traz a quantidade por situação com os demais filtros.", responses={**SEM_TRIAGEM, **INVALIDO})
def listar(filtros: Filtros = Depends(_filtros), pagina: int = Query(1, ge=1), tamanho: int = Query(20, ge=1, le=100),
           sessao: Session = Depends(obter_sessao), _usuario: Usuario = Depends(_usuario_triagem)) -> PaginaSugestoesTriagem:
    itens, total, totais, modulos = servico.listar(sessao, filtros, pagina, tamanho)
    return PaginaSugestoesTriagem(itens=[_triagem(sessao, s) for s in itens], total=total, pagina=pagina, tamanho=tamanho, totais=totais, modulos=modulos)


@roteador.get("/sugestoes/exportar", summary="Triagem: exportar em XLSX", response_class=Response,
              description="Planilha com as sugestões dos filtros atuais (os mesmos da lista).", responses={**SEM_TRIAGEM, **INVALIDO})
def exportar(filtros: Filtros = Depends(_filtros), sessao: Session = Depends(obter_sessao), _usuario: Usuario = Depends(_usuario_triagem)) -> Response:
    return Response(servico.planilha(sessao, filtros), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="melhorias.xlsx"'})


@roteador.get("/sugestoes/relatorio", summary="Triagem: relatório em PDF", response_class=Response,
              description="Resumo por situação e por módulo e uma seção por sugestão (com os prints), dos filtros atuais.",
              responses={**SEM_TRIAGEM, **INVALIDO})
def relatorio(filtros: Filtros = Depends(_filtros), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(_usuario_triagem)) -> Response:
    return Response(servico.relatorio_pdf(sessao, filtros, usuario), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="relatorio_melhorias.pdf"'})


@roteador.get("/sugestoes/{numero}", response_model=SugestaoTriagem, summary="Triagem: detalhe da sugestão",
              responses={**SEM_TRIAGEM, **NAO_ENCONTRADA})
def detalhe(numero: int, sessao: Session = Depends(obter_sessao), _usuario: Usuario = Depends(_usuario_triagem)) -> SugestaoTriagem:
    with _traduzir():
        return _triagem(sessao, servico.por_numero(sessao, numero))


@roteador.put("/sugestoes/{numero}", response_model=SugestaoTriagem, summary="Triagem: tratar a sugestão",
              description="Situação, resposta ao autor e observação interna (só a triagem vê). Se a situação mudar, ou a resposta mudar e não "
                          "ficar vazia, o autor recebe aviso na caixa de Mensagens, com e-mail. Sem nenhuma mudança, nada é gravado.",
              responses={**SEM_TRIAGEM, **NAO_ENCONTRADA})
def tratar(numero: int, dados: TratamentoSugestao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(_usuario_triagem)) -> SugestaoTriagem:
    with _traduzir(sessao):
        sugestao = servico.tratar(sessao, numero, dados.situacao, dados.resposta_publica, dados.observacao_interna, usuario)
    sessao.commit()
    return _triagem(sessao, sugestao)


@roteador.post("/sugestoes/{numero}/tarefa", response_model=SugestaoTriagem, summary="Triagem: converter em tarefa",
               description="Cria a tarefa no Módulo Tarefas (título, prazo, prioridade, equipe e responsável; a descrição leva o texto, o autor e a "
                           "tela da sugestão) e marca a sugestão como Aceita, se estava Nova ou Em análise. Valem as regras do Módulo Tarefas "
                           "(ex.: responsável da equipe). Sugestão já convertida → 409.", responses={**SEM_TRIAGEM, **NAO_ENCONTRADA, **INVALIDO, **CONFLITO})
def converter(numero: int, dados: ConversaoTarefa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(_usuario_triagem)) -> SugestaoTriagem:
    with _traduzir(sessao):
        sugestao, _ = servico.converter_em_tarefa(sessao, numero, dados.titulo, dados.prazo, dados.prioridade, dados.equipe_id, dados.responsavel_id, usuario)
    sessao.commit()
    return _triagem(sessao, sugestao)
