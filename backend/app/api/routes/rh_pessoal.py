# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da própria pessoa no RH: boas-vindas do primeiro acesso, bio e a ficha cadastral (legados).
"""Rotas da própria pessoa (`/api/rh/boas-vindas`, `/api/rh/minha-bio`, `/api/rh/minha-ficha`). Qualquer usuário autenticado, só sobre si mesmo."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual, obter_usuario_autenticado
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.rh_boas_vindas import BioGravacao, BioLeitura, BoasVindas
from app.schemas.rh_pre_cadastro import GravacaoMinhaFicha, LeituraFicha
from app.services.rh import servico_boas_vindas, servico_pre_cadastro
from app.services.rh.servico_pre_cadastro import ErroFicha

roteador = APIRouter(prefix="/rh", tags=["Módulo RH: minha vida funcional"], responses=RESPOSTAS_AUTENTICADAS)


@roteador.get("/boas-vindas", response_model=BoasVindas, summary="Boas-vindas do primeiro acesso",
              description="Não exige o perfil em dia (é o primeiro contato da pessoa). `pendente = true` só no primeiro acesso de contas do AD (quem já usava o sistema antes não vê). Traz o texto do modelo \"Boas-vindas\" preenchido e, na primeira consulta, "
                          "envia o mesmo texto ao e-mail da pessoa (uma vez).")
def boas_vindas(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)):
    return servico_boas_vindas.consultar(sessao, usuario)


@roteador.post("/boas-vindas/confirmar", status_code=status.HTTP_204_NO_CONTENT, summary="Marcar as boas-vindas como vistas",
               description="Depois disso o aviso não aparece mais. A tela segue para o cadastro da pessoa (perfil).")
def confirmar_boas_vindas(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)) -> Response:
    servico_boas_vindas.confirmar(sessao, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/minha-bio", response_model=BioLeitura, summary="Minha bio")
def minha_bio(usuario: Usuario = Depends(obter_usuario_atual)):
    return servico_boas_vindas.ler_bio(usuario)


@roteador.put("/minha-bio", response_model=BioLeitura, summary="Salvar minha bio",
              description="Texto livre (até 3000 caracteres). `bio_visivel = true` libera a bio na busca de usuários e no cartão de contato; sem texto, a bio fica oculta.")
def salvar_bio(dados: BioGravacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)):
    return servico_boas_vindas.salvar_bio(sessao, usuario, dados.bio_texto, dados.bio_visivel)


@roteador.get("/minha-ficha", response_model=LeituraFicha | None, summary="Minha ficha cadastral",
              description="A ficha da própria pessoa (a de admissão ou a que ela mesma preencheu); `null` se ainda não existe. Traz `validado_em` quando o RH já validou.")
def minha_ficha(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)):
    return servico_pre_cadastro.minha_ficha(sessao, usuario)


@roteador.put("/minha-ficha", response_model=LeituraFicha, summary="Enviar minha ficha cadastral",
              description="Quem já tinha conta antes do pré-cadastro preenche a ficha e o RH valida (`POST /api/rh/pre-cadastros/{id}/validar`). Cada envio zera a validação. CPF e PIS/PASEP têm os dígitos conferidos.",
              responses=INVALIDO)
def enviar_ficha(dados: GravacaoMinhaFicha, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)):
    try:
        return servico_pre_cadastro.salvar_minha_ficha(sessao, usuario, dados)
    except ErroFicha as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito) from erro
