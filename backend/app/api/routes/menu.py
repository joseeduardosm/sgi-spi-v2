# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a configuração do menu lateral (leitura para todos e gravação por ACL).
"""Menu lateral (`/api/menu`): todo usuário autenticado lê; gravar e restaurar o padrão exige o recurso de ACL `atalhos` ≥ MODIFICACAO."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl, obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import agora_utc, obter_sessao
from app.models.acl import NivelAcl
from app.models.menu import MenuConfiguracao
from app.models.usuario import Usuario
from app.schemas.menu import GravacaoMenu, LeituraMenu
from app.services.servico_auditoria import auditar

roteador = APIRouter(prefix="/menu", tags=["Menu"], responses=RESPOSTAS_AUTENTICADAS)
gerencia = exigir_acl("atalhos", NivelAcl.MODIFICACAO)


def _leitura(linha: MenuConfiguracao | None) -> LeituraMenu:
    if linha is None:
        return LeituraMenu(itens=[], padrao=True)
    return LeituraMenu(itens=linha.itens or [], padrao=False, atualizado_por_nome=linha.atualizado_por_nome, atualizado_em=linha.atualizado_em)


@roteador.get("", response_model=LeituraMenu, summary="Configuração do menu lateral",
              description="Ordem, grupos, nomes, links e itens ocultos definidos pelo administrador. `padrao = true` (e `itens` vazio) quando nada foi configurado. "
              "O menu é montado no cliente: a ACL e o papel continuam decidindo o que cada pessoa vê. Qualquer usuário autenticado.")
def ler(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> LeituraMenu:
    """Configuração para a barra lateral, a busca global e a paleta de comandos."""
    return _leitura(sessao.get(MenuConfiguracao, 1))


@roteador.put("", response_model=LeituraMenu, summary="Gravar a configuração do menu", responses=VALIDACAO,
              description="Substitui a configuração inteira. Módulos citados por `id` do código; grupos e links criados pelo administrador. No máximo 200 nós e dois níveis; "
              "ids repetidos, grupo inexistente e link com endereço inválido são recusados (422). Exige ACL `atalhos` ≥ MODIFICACAO.")
def gravar(dados: GravacaoMenu, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> LeituraMenu:
    linha = sessao.get(MenuConfiguracao, 1) or MenuConfiguracao(id=1)
    linha.itens = [n.model_dump(exclude_none=True) for n in dados.itens]
    linha.atualizado_por_nome, linha.atualizado_em = autor.nome_completo or autor.login, agora_utc()
    sessao.add(linha)
    auditar(sessao, autor.login, "menu.gravar", "Menu lateral", f"{len(dados.itens)} item(ns)", autor_id=autor.id, alvo_tipo="menu", alvo_id=1)
    sessao.commit()
    return _leitura(linha)


@roteador.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Restaurar o menu padrão",
                 description="Apaga a configuração: volta o menu padrão do código. Exige ACL `atalhos` ≥ MODIFICACAO.")
def restaurar(sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerencia)) -> Response:
    linha = sessao.get(MenuConfiguracao, 1)
    if linha is not None:
        sessao.delete(linha)
        auditar(sessao, autor.login, "menu.restaurar", "Menu lateral", autor_id=autor.id, alvo_tipo="menu", alvo_id=1)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
