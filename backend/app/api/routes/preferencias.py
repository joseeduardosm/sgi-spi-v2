"""
===============================================================================
ARQUIVO: preferencias.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Expor a API das preferências de colunas das listagens
(/api/preferencias/colunas/{tela}): quais colunas cada usuário escolheu
mostrar em cada tela e em que ordem.

RESUMO TÉCNICO:
Três rotas (GET lê, PUT grava, DELETE restaura o padrão) sobre a tabela
PreferenciaColunas. Cada linha é uma "visão": a pessoal (usuario_id do
usuário logado) ou a global da tela (usuario_id nulo). A leitura devolve as
duas; a gravação e a remoção da visão global exigem o papel SuperRoot
(administrador geral do sistema). O id da tela é validado por expressão
regular no caminho.

FINALIDADE DE NEGÓCIO:
Permite que cada servidor monte a listagem do jeito que trabalha (por
exemplo, esconder colunas que não usa no Patrimônio) e que a administração
defina um padrão para todos que ainda não personalizaram a tela.

CONTEXTO NO SISTEMA:
Usada pelo seletor de colunas das tabelas do frontend. Modelo em
app/models/preferencia_colunas.py, schemas em app/schemas/preferencias.py,
documentação em docs/endpoints/. O roteador é incluído em app/main.py.

===============================================================================
"""

from typing import Annotated

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.preferencia_colunas import PreferenciaColunas
from app.models.usuario import Papel, Usuario
from app.schemas.preferencias import GravacaoColunas, PreferenciaColunasLeitura

# APIRouter agrupa as rotas deste módulo sob um prefixo comum (/preferencias) e uma etiqueta (tag)
# na documentação OpenAPI. As respostas de erro padrão de rota autenticada (401 etc.) valem para
# todas.
roteador = APIRouter(prefix="/preferencias", tags=["Preferências de colunas"], responses=RESPOSTAS_AUTENTICADAS)

# Tipo reaproveitável do parâmetro {tela} do caminho: Annotated junta o tipo (str) às regras de
# validação do FastAPI (tamanho e só letras minúsculas, números, ponto, sublinhado e hífen). Valor
# fora da regra vira erro 422 antes de chegar à função.
Tela = Annotated[str, Path(min_length=1, max_length=60, pattern=r"^[a-z0-9_.-]+$", description="Identificador da tela (ex.: `patrimonio.bens`).")]


# Parâmetro de consulta ?visao=: Literal limita os valores aceitos a pessoal ou global.
Visao = Annotated[Literal["pessoal", "global"], Query(description="`pessoal` (padrão): a visão do próprio usuário. `global`: a visão de todos que não têm visão pessoal (só o SuperRoot grava).")]


def _preferencia(sessao: Session, usuario: Usuario | None, tela: str) -> PreferenciaColunas | None:
    """
    Busca a linha de preferência de uma tela.

    Com um usuário, devolve a visão pessoal dele; com `usuario=None`, a visão global da
    tela (linha com usuario_id nulo). Devolve None quando ninguém escolheu ainda. Só lê
    o banco.
    """
    filtro = PreferenciaColunas.usuario_id == usuario.id if usuario is not None else PreferenciaColunas.usuario_id.is_(None)
    return sessao.scalar(select(PreferenciaColunas).where(filtro, PreferenciaColunas.tela == tela))


def _dono(sessao: Session, usuario: Usuario, visao: str) -> Usuario | None:
    """
    Decide de quem é a visão que será gravada ou apagada.

    Com `visao="global"`, só o SuperRoot (papel de administrador geral) pode mexer e o
    dono é None (linha global); qualquer outro usuário recebe erro 403 `acesso_negado`.
    Na visão pessoal, o dono é o próprio usuário logado.
    """
    if visao == "global":
        if not usuario.possui_papel(Papel.SUPER_ROOT):
            raise ErroApi(status.HTTP_403_FORBIDDEN, "Só o SuperRoot altera a visão global.", "acesso_negado")
        return None
    return usuario


def _leitura(sessao: Session, usuario: Usuario, tela: str) -> PreferenciaColunasLeitura:
    """
    Monta a resposta padrão das três rotas: a visão pessoal do usuário (`colunas`, nula
    se nunca escolheu) e a global da tela (`padrao_global`).

    O frontend usa a pessoal; se ela for nula, cai na global; se as duas forem nulas,
    usa o padrão fixo da tela.
    """
    pessoal, global_ = _preferencia(sessao, usuario, tela), _preferencia(sessao, None, tela)
    return PreferenciaColunasLeitura(tela=tela, colunas=list(pessoal.colunas) if pessoal else None, padrao_global=list(global_.colunas) if global_ else None)


@roteador.get("/colunas/{tela}", response_model=PreferenciaColunasLeitura, summary="Minhas colunas da listagem",
              description="Colunas que o usuário escolheu mostrar na listagem da tela, na ordem (`colunas`; nulo = nunca escolheu), e a visão global da tela (`padrao_global`), usada por quem não tem visão pessoal. "
              "Cada usuário vê só as próprias.")
# Depends(...) pede ao FastAPI que entregue, a cada requisição, a sessão do banco (obter_sessao) e o
# usuário autenticado pelo token (obter_usuario_atual); sem token válido a rota nem executa.
def minhas_colunas(tela: Tela, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciaColunasLeitura:
    """Lê a visão pessoal do usuário logado e a global da tela."""
    return _leitura(sessao, usuario, tela)


@roteador.put("/colunas/{tela}", response_model=PreferenciaColunasLeitura, summary="Salvar as colunas da listagem", responses={**VALIDACAO, 403: {"description": "`visao=global` sem ser SuperRoot (`acesso_negado`)."}},
              description="Substitui a lista inteira, na ordem enviada (de 1 a 80 ids, sem repetir), na visão pessoal (padrão) ou, com `visao=global`, na visão global (só SuperRoot). "
              "O servidor não confere se a tela conhece as colunas: a tela ignora as que não existirem mais.")
def salvar_colunas(tela: Tela, dados: GravacaoColunas, visao: Visao = "pessoal", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PreferenciaColunasLeitura:
    """Grava (ou troca) as colunas da visão pessoal ou global."""
    dono = _dono(sessao, usuario, visao)
    linha = _preferencia(sessao, dono, tela)
    if linha is None:
        # Primeira escolha nesta tela: cria a linha. Se já existia, apenas troca a lista inteira
        # (não há mescla).
        sessao.add(PreferenciaColunas(usuario_id=dono.id if dono else None, tela=tela, colunas=dados.colunas))
    else:
        linha.colunas = dados.colunas
    sessao.commit()
    return _leitura(sessao, usuario, tela)


@roteador.delete("/colunas/{tela}", status_code=status.HTTP_204_NO_CONTENT, summary="Restaurar o padrão das colunas", responses={403: {"description": "`visao=global` sem ser SuperRoot (`acesso_negado`)."}},
                 description="Apaga a visão pessoal (padrão) ou, com `visao=global`, a global (só SuperRoot): volta a valer a visão seguinte (global, depois o padrão da tela). Sem escolha anterior, também responde `204`.")
def restaurar_colunas(tela: Tela, visao: Visao = "pessoal", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    """Remove a visão pessoal ou global."""
    linha = _preferencia(sessao, _dono(sessao, usuario, visao), tela)
    if linha is not None:
        sessao.delete(linha)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
