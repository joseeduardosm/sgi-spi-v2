# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a geração da assinatura de e-mail (/api/assinatura-email).
"""Assinatura de e-mail institucional: dados do perfil, prévia ao vivo e download em PNG ou HTML."""

import base64

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS
from app.core.banco import obter_sessao
from app.core.configuracao import obter_configuracao
from app.core.erros import ErroApi
from app.models.usuario import Usuario
from app.schemas.assinatura_email import DadosAssinatura, LeituraDadosAssinatura, PreviaAssinatura
from app.services import assinatura_email as servico
from app.services.servico_auditoria import auditar

roteador = APIRouter(prefix="/assinatura-email", tags=["Assinatura de e-mail"], responses=RESPOSTAS_AUTENTICADAS)


def _gerar(dados: DadosAssinatura) -> servico.Resultado:
    opcoes = servico.OpcoesAssinatura(incluir_celular=dados.incluir_celular, incluir_andar_lado=dados.incluir_andar_lado)
    try:
        return servico.gerar(dados.model_dump(exclude={"incluir_celular", "incluir_andar_lado"}), opcoes)
    except servico.ErroAssinatura as erro:
        raise ErroApi(400, str(erro), "invalido") from erro


@roteador.get("/dados", response_model=LeituraDadosAssinatura, summary="Dados para a assinatura",
              description="Dados **em vigor** do perfil (o que está pendente de validação da CGP não entra) para pré-preencher o formulário, "
              "e a lista do que falta (`faltando`: nome, cargo, e-mail).")
def dados(usuario: Usuario = Depends(obter_usuario_atual)) -> LeituraDadosAssinatura:
    em_vigor = servico.dados_em_vigor(usuario)
    return LeituraDadosAssinatura(**em_vigor, faltando=servico.campos_faltando(em_vigor), telefone_prefixo=obter_configuracao().assinatura_telefone_prefixo)


@roteador.post("/previa", response_model=PreviaAssinatura, summary="Prévia da assinatura",
               description="Gera a imagem (PNG 1692×471 em base64), o HTML e os avisos (texto abreviado, campo ausente). "
               "Nome, cargo e e-mail são obrigatórios (`400`). **Não grava nada no perfil.**", responses=INVALIDO)
def previa(dados: DadosAssinatura, _: Usuario = Depends(obter_usuario_atual)) -> PreviaAssinatura:
    resultado = _gerar(dados)
    return PreviaAssinatura(png_base64=base64.b64encode(resultado.png).decode("ascii"), html=resultado.html, avisos=resultado.avisos)


@roteador.post("/png", response_class=Response, summary="Baixar a assinatura em PNG",
               description="`image/png` de 1692×471 (use a 564 px de largura nos clientes de e-mail). Auditado como `assinatura.gerar`.",
               responses={200: {"content": {"image/png": {}}}, **INVALIDO})
def baixar_png(dados: DadosAssinatura, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    resultado = _gerar(dados)
    auditar(sessao, usuario.login, "assinatura.gerar", "png", autor_id=usuario.id, alvo_tipo="usuario", alvo_id=str(usuario.id))
    sessao.commit()
    return Response(resultado.png, media_type="image/png", headers={"Content-Disposition": 'attachment; filename="assinatura-email.png"'})


@roteador.post("/html", response_class=Response, summary="Baixar a assinatura em HTML",
               description="Arquivo `.html` com a assinatura (tabela com estilos inline) para importar no Outlook ou no webmail. Auditado como `assinatura.gerar`.",
               responses={200: {"content": {"text/html": {}}}, **INVALIDO})
def baixar_html(dados: DadosAssinatura, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    resultado = _gerar(dados)
    auditar(sessao, usuario.login, "assinatura.gerar", "html", autor_id=usuario.id, alvo_tipo="usuario", alvo_id=str(usuario.id))
    sessao.commit()
    pagina = f'<!DOCTYPE html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>Assinatura de e-mail</title></head><body>{resultado.html}</body></html>'
    return Response(pagina, media_type="text/html; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="assinatura-email.html"'})
