# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da ficha de pré-cadastro do RH e da checagem do login proposto.
"""Pré-cadastro (`/api/rh/pre-cadastros`). Dados pessoais sensíveis: só o RH (ACL `rh`, controle total)."""

from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_rh
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.core.erros import ErroApi
from app.schemas.rh_pre_cadastro import GravacaoFicha, LeituraFicha, LinhaImportacaoFicha, LoginDisponivel, ResultadoImportacaoFichas, ResumoFicha
from app.services.rh import importacao_pre_cadastro, servico_pre_cadastro
from app.services.rh.servico_pre_cadastro import ErroFicha, FichaNaoEncontrada

roteador = APIRouter(prefix="/rh/pre-cadastros", tags=["Módulo RH: pré-cadastro"], responses=RESPOSTAS_AUTENTICADAS)

rh = exigir_rh(NivelAcl.CONTROLE_TOTAL)
NAO_ENCONTRADO = resposta_nao_encontrado("Ficha")


@contextmanager
def _traduzir(sessao: Session):
    try:
        yield
    except FichaNaoEncontrada as erro:
        sessao.rollback()
        raise nao_encontrado("Ficha") from erro
    except ErroFicha as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito) from erro


@roteador.get("/login-disponivel", response_model=LoginDisponivel, summary="Conferir o login proposto",
              description="Confere se o login está livre no SGI (usuários e outras fichas) e no AD (só leitura). `verificado_no_ad = false` quando o AD não está configurado ou não respondeu. "
                          "Exige **Controle total** no RH.")
def login_disponivel(login: str = Query(..., max_length=60), ficha_id: int | None = Query(None, description="Ficha em edição (o login dela não conta como ocupado)."),
                     sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_pre_cadastro.login_disponivel(sessao, login, ficha_id)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _resultado(linhas, gravado: bool) -> ResultadoImportacaoFichas:
    return ResultadoImportacaoFichas(
        total=len(linhas), com_erro=sum(1 for l in linhas if l.erros), gravado=gravado,
        linhas=[LinhaImportacaoFicha(linha=l.linha, nome=l.nome, cpf=l.cpf, login_proposto=l.login, cargo_pretendido=l.cargo_rotulo, erros=l.erros, ficha_id=l.ficha_id) for l in linhas],
    )


async def _planilha(arquivo: UploadFile) -> bytes:
    if not (arquivo.filename or "").lower().endswith(".xlsx"):
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Envie a planilha no formato .xlsx.", "invalido")
    return await arquivo.read(importacao_pre_cadastro.TAMANHO_MAXIMO + 1)


@roteador.get("/importacao/modelo", response_class=Response, summary="Formulário XLSX da ficha de pré-cadastro",
              description="Formulário XLSX de **uma pessoa**, em uma aba só (\"Ficha\"): instruções no topo, seções, rótulos bloqueados, só as células de resposta liberadas, listas onde há opções fixas e alertas que explicam o preenchimento. O RH envia à pessoa, que preenche e devolve. Exige **Controle total** no RH.",
              responses={200: {"content": {XLSX: {}}}})
def modelo_importacao(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)) -> Response:
    return Response(importacao_pre_cadastro.modelo(sessao), media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="modelo-fichas-pre-cadastro.xlsx"'})


@roteador.post("/importacao/previa", response_model=ResultadoImportacaoFichas, summary="Prévia da ficha da planilha",
               description="`multipart/form-data` com a planilha em `arquivo`. Confere sem gravar: por linha, os erros (CPF, PIS, CEP, UF, login único no SGI/AD, CPF já cadastrado, vaga inexistente). Exige **Controle total** no RH.",
               responses=INVALIDO)
async def previa_importacao(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    conteudo = await _planilha(arquivo)
    with _traduzir(sessao):
        return _resultado(importacao_pre_cadastro.conferir(sessao, conteudo, autor), gravado=False)


@roteador.post("/importacao", response_model=ResultadoImportacaoFichas, status_code=status.HTTP_201_CREATED, summary="Importar a ficha da planilha",
               description="Mesma planilha da prévia. Confere de novo e, **sem nenhum erro**, cria a ficha como rascunho (o RH completa setor e cargo pretendidos, login proposto e início previsto). "
                           "Com erro, nada é gravado (`400`). Auditado como `rh.pre_cadastro.importar`.", responses={**INVALIDO, **CONFLITO})
async def importar(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    conteudo = await _planilha(arquivo)
    with _traduzir(sessao):
        return _resultado(importacao_pre_cadastro.importar(sessao, conteudo, autor), gravado=True)


@roteador.get("", response_model=list[ResumoFicha], summary="Listar fichas de pré-cadastro",
              description="Mais recentes primeiro. `busca` procura por todas as palavras em nome, login, CPF, documentos, RS/PV e cargo de origem; `status`: rascunho, aguardando_conta, vinculado ou cancelado.")
def listar(busca: str | None = Query(None, max_length=100), status_ficha: str | None = Query(None, alias="status", pattern="^(rascunho|aguardando_conta|vinculado|cancelado)$"),
           pendentes_de_validacao: bool = Query(False, description="Só as fichas que a própria pessoa enviou e o RH ainda não validou."),
           sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_pre_cadastro.listar(sessao, busca, status_ficha, pendentes_de_validacao)


@roteador.post("", response_model=LeituraFicha, status_code=status.HTTP_201_CREATED, summary="Criar ficha de pré-cadastro",
               description="CPF e PIS/PASEP têm os dígitos conferidos. O login proposto precisa estar livre (409 se existir no SGI, em outra ficha ou no AD). Exige **Controle total** no RH.",
               responses={**INVALIDO, **CONFLITO})
def criar(dados: GravacaoFicha, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_pre_cadastro.criar(sessao, dados, autor)


@roteador.get("/{ficha_id}", response_model=LeituraFicha, summary="Consultar ficha", responses=NAO_ENCONTRADO)
def consultar(ficha_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_pre_cadastro.obter(sessao, ficha_id)


@roteador.put("/{ficha_id}", response_model=LeituraFicha, summary="Alterar ficha",
              description="Substitui os dados, as formações e as experiências. Ficha vinculada a uma conta ou cancelada não se altera (409).", responses={**NAO_ENCONTRADO, **INVALIDO, **CONFLITO})
def alterar(ficha_id: int, dados: GravacaoFicha, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_pre_cadastro.alterar(sessao, ficha_id, dados, autor)


@roteador.delete("/{ficha_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancelar ficha",
                 description="Marca a ficha como cancelada e libera o login proposto. Ficha já vinculada a uma conta não se cancela (409).", responses={**NAO_ENCONTRADO, **CONFLITO})
def cancelar(ficha_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)) -> Response:
    with _traduzir(sessao):
        servico_pre_cadastro.cancelar(sessao, ficha_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/{ficha_id}/validar", response_model=LeituraFicha, summary="Validar a ficha enviada pela pessoa",
               description="Para quem já tinha conta antes do pré-cadastro (legados): a pessoa preenche em `GET/PUT /api/rh/minha-ficha` e o RH confere e valida. Registra no histórico dela. 409 se a pessoa ainda não enviou.",
               responses={**NAO_ENCONTRADO, **CONFLITO})
def validar(ficha_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_pre_cadastro.validar(sessao, ficha_id, autor)
