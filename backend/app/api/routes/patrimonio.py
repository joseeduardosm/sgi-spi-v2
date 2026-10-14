# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Patrimônio (/api/patrimonio): localizações, bens, movimentações, inservíveis/extraviados, baixas e painel.
"""Rotas `/api/patrimonio`.

Níveis do recurso ACL `patrimonio`: **LEITURA** consulta bens, locais, histórico, painéis e exporta; **MODIFICACAO** cadastra e edita bens e
solicita movimentações, classificações (inservível/extraviado) e baixas, sem aprovar nenhuma; **CONTROLE_TOTAL** autoriza, recusa e confirma o
recebimento das movimentações, aprova ou recusa classificações e baixas, cadastra salas e grupos, ajusta parâmetros e muda o local de um bem sem
movimentação (motivo obrigatório). Quem solicita nunca aprova a própria solicitação (`403 auto_aprovacao`), mesmo com controle total.
"""

import uuid
from contextlib import contextmanager
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import hoje_sao_paulo, obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.patrimonio import Bem, Localizacao
from app.models.usuario import Usuario
from app.schemas import patrimonio as esquema
from app.schemas.usuarios import OpcaoUsuario
from app.services import servico_admin_usuarios, servico_anexos
from app.services.patrimonio import exportacao, relatorio_listas, servico_baixas, servico_bens, servico_classificacoes, servico_localizacoes, servico_movimentacoes, servico_paineis, servico_parametros
from app.services.patrimonio.base import RECURSO, ErroPatrimonio, controle_total, nome_do_autor
from app.services.patrimonio.servico_localizacoes import rotulo_curto

roteador = APIRouter(prefix="/patrimonio", tags=["Patrimônio"], responses=VALIDACAO)
ver = exigir_acl(RECURSO, NivelAcl.LEITURA)
operar = exigir_acl(RECURSO, NivelAcl.MODIFICACAO)
administrar = exigir_acl(RECURSO, NivelAcl.CONTROLE_TOTAL)
SEM_ADMIN = {status.HTTP_403_FORBIDDEN: {"description": "Sem CONTROLE_TOTAL em `patrimonio` (`acl_negado`), ou autoaprovação (`auto_aprovacao`)."}}
FORMATO = Literal["xlsx", "pdf"]


@contextmanager
def _traduzir(sessao: Session | None = None):
    """Erros do serviço viram a resposta padrão `{"detalhe", "codigo"}`."""
    try:
        yield
    except ErroPatrimonio as erro:
        if sessao is not None:
            sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _origem(requisicao: Request) -> str:
    """De onde veio a mudança: endereço e canal (cabeçalho `X-Canal`: web, celular ou offline)."""
    canal = requisicao.headers.get("x-canal", "web")[:20]
    return f"{requisicao.client.host if requisicao.client else '?'} · {canal}"[:80]


# --- Construtores das respostas ----------------------------------------------------------------

def _localizacao(l: Localizacao, totais: dict) -> esquema.LocalizacaoLeitura:
    return esquema.LocalizacaoLeitura(
        id=l.id, pai_id=l.pai_id, tipo=l.tipo, nome=l.nome, codigo=l.codigo, rotulo=rotulo_curto(l) if l.tipo == "sala" else l.nome, andar=l.andar, lado=l.lado,
        setor_id=l.setor_id, setor_nome=l.setor.nome if l.setor else None, responsavel_id=l.responsavel_id,
        responsavel_nome=(l.responsavel.nome_completo or l.responsavel.login) if l.responsavel else None,
        deposito_inservivel=servico_localizacoes.eh_deposito_inservivel(l), ativo=l.ativo, total_bens=totais.get(l.id, 0))


def _nome_de(sessao: Session, usuario_id: int | None) -> str | None:
    """Nome de quem cadastrou o bem (a sessão guarda os usuários já lidos, então a lista não refaz a consulta para o mesmo autor)."""
    usuario = sessao.get(Usuario, usuario_id) if usuario_id else None
    return (usuario.nome_completo or usuario.login) if usuario else None


def _bem(sessao: Session, b: Bem, em_mov: bool) -> esquema.BemLeitura:
    sala = b.localizacao
    return esquema.BemLeitura(
        id=b.id, chapa=b.chapa, rotulo=b.rotulo, descricao=b.descricao, localizacao_id=b.localizacao_id, sala_codigo=sala.codigo, sala_rotulo=rotulo_curto(sala), andar=sala.andar,
        setor_nome=sala.setor.nome if sala.setor else None, responsavel_id=b.responsavel_id,
        responsavel_nome=(b.responsavel.nome_completo or b.responsavel.login) if b.responsavel else None, conservacao=b.conservacao, situacao=b.situacao,
        origem=b.origem, grupo_id=b.grupo_id, grupo_nome=b.grupo.nome if b.grupo else None, uge=b.uge, ua=b.ua, divisao=b.divisao, valor_aquisicao=b.valor_aquisicao,
        valor_atual=b.valor_atual, valor_efetivo=servico_bens.valor_efetivo(b), data_aquisicao=b.data_aquisicao, garantia_meses=b.garantia_meses,
        garantia_fim=servico_bens.garantia_fim(b), situacao_garantia=servico_bens.situacao_garantia(b), vence_em_90_dias=servico_bens.vence_em_90_dias(b), marca=b.marca,
        modelo=b.modelo, numero_serie=b.numero_serie, nota_fiscal=b.nota_fiscal, fornecedor=b.fornecedor, observacoes=b.observacoes,
        criado_por_nome=_nome_de(sessao, b.criado_por_id), classificacao_pendente=b.classificacao_pendente, em_movimentacao=em_mov, dados_contabeis_pendentes=b.dados_contabeis_pendentes,
        fotos=[esquema.FotoLeitura(id=f.id, nome=f.anexo.nome_original) for f in b.fotos], avisos=servico_bens.avisos(sessao, b), criado_em=b.criado_em,
        atualizado_em=b.atualizado_em, baixado_em=b.baixado_em)


def _bem_completo(sessao: Session, b: Bem) -> esquema.BemLeitura:
    return _bem(sessao, b, servico_bens.em_movimentacao(sessao, b.id))


def _evento(e) -> esquema.EventoLeitura:
    return esquema.EventoLeitura(id=e.id, tipo=e.tipo, campo=e.campo, valor_anterior=e.valor_anterior, valor_novo=e.valor_novo, autor_nome=e.autor_nome, origem=e.origem,
                                 texto=e.texto, dados=e.dados, ocorrido_em=e.ocorrido_em)


def _movimentacao(m) -> esquema.MovimentacaoLeitura:
    return esquema.MovimentacaoLeitura(
        id=m.id, status=m.status, destino_id=m.destino_id, destino_codigo=m.destino.codigo, destino_rotulo=rotulo_curto(m.destino), motivo=m.motivo,
        solicitante_id=m.solicitante_id, solicitante_nome=nome_do_autor(m.solicitante), solicitada_em=m.solicitada_em,
        decidido_por_nome=nome_do_autor(m.decidido_por) if m.decidido_por else None, decidido_em=m.decidido_em, motivo_recusa=m.motivo_recusa, concluida_em=m.concluida_em,
        itens=[esquema.ItemMovimentacaoLeitura(bem_id=i.bem_id, chapa=i.bem.chapa, numero_serie=i.bem.numero_serie, rotulo=i.bem.rotulo, descricao=i.bem.descricao, origem_codigo=i.origem.codigo, origem_rotulo=rotulo_curto(i.origem),
                                               recebido_em=i.recebido_em) for i in m.itens])


def _classificacao(c) -> esquema.ClassificacaoLeitura:
    return esquema.ClassificacaoLeitura(
        id=c.id, tipo=c.tipo, status=c.status, solicitante_id=c.solicitante_id, solicitante_nome=nome_do_autor(c.solicitante), criada_em=c.criada_em, enviada_em=c.enviada_em,
        decidido_por_nome=nome_do_autor(c.decidido_por) if c.decidido_por else None, decidido_em=c.decidido_em, motivo_recusa=c.motivo_recusa,
        itens=[esquema.ItemClassificacaoLeitura(id=i.id, bem_id=i.bem_id, chapa=i.bem.chapa, numero_serie=i.bem.numero_serie, rotulo=i.bem.rotulo, descricao=i.bem.descricao, sala_rotulo=rotulo_curto(i.bem.localizacao),
                                                situacao_anterior=i.situacao_anterior, justificativa=i.justificativa, anexo_nome=i.anexo.nome_original if i.anexo else None,
                                                resultado=i.resultado) for i in c.itens])


def _baixa(b) -> esquema.BaixaLeitura:
    return esquema.BaixaLeitura(
        id=b.id, status=b.status, solicitante_id=b.solicitante_id, solicitante_nome=nome_do_autor(b.solicitante), criada_em=b.criada_em, enviada_em=b.enviada_em,
        decidido_por_nome=nome_do_autor(b.decidido_por) if b.decidido_por else None, decidido_em=b.decidido_em, motivo_recusa=b.motivo_recusa, tem_termo=b.termo_anexo_id is not None,
        itens=[esquema.ItemBaixaLeitura(id=i.id, bem_id=i.bem_id, chapa=i.bem.chapa, numero_serie=i.bem.numero_serie, rotulo=i.bem.rotulo, descricao=i.bem.descricao, situacao_anterior=i.situacao_anterior,
                                        valor_aquisicao=i.bem.valor_aquisicao, motivo=i.motivo, processo=i.processo, resultado=i.resultado) for i in b.itens])


# --- Acesso ------------------------------------------------------------------------------------

@roteador.get("/acesso", response_model=esquema.AcessoPatrimonio, summary="Meu acesso ao Patrimônio",
              description="Diz se o usuário pode operar (MODIFICACAO) e administrar (CONTROLE_TOTAL): a tela mostra ou esconde as ações.")
def acesso(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.AcessoPatrimonio:
    from app.services import servico_acl

    nivel = None if usuario.superusuario else servico_acl.resolver_acesso(sessao, usuario, RECURSO)
    operar_ = usuario.superusuario or nivel in (NivelAcl.MODIFICACAO, NivelAcl.CONTROLE_TOTAL)
    return esquema.AcessoPatrimonio(usuario_id=usuario.id, pode_operar=operar_, pode_administrar=controle_total(sessao, usuario))


@roteador.get("/opcoes-setores", response_model=list[esquema.OpcaoSetor], summary="Setores para a sala",
              description="Setores ativos, para informar o setor da sala no primeiro cadastro de bem (MODIFICACAO).")
def opcoes_setores(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> list[esquema.OpcaoSetor]:
    from app.models.setor import Setor

    return [esquema.OpcaoSetor(id=s.id, nome=s.nome) for s in sessao.scalars(select(Setor).where(Setor.ativo.is_(True)).order_by(func.lower(Setor.nome)))]


@roteador.get("/opcoes-usuarios", response_model=list[OpcaoUsuario], summary="Usuários para o responsável da sala",
              description="Usuários ativos por nome, login ou cargo (`busca`, até 20), para informar o responsável da sala (MODIFICACAO).")
def opcoes_usuarios(busca: str | None = Query(None, max_length=100), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> list[OpcaoUsuario]:
    return servico_admin_usuarios.opcoes(sessao, busca, 20)


# --- Localizações ------------------------------------------------------------------------------

@roteador.get("/localizacoes", response_model=list[esquema.LocalizacaoLeitura], summary="Árvore de localizações",
              description="Lista plana (prédio, andares, lados e salas) com `pai_id`; a tela monta a árvore. Traz o total de bens de cada sala.")
def listar_localizacoes(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.LocalizacaoLeitura]:
    totais = dict(sessao.execute(select(Bem.localizacao_id, func.count(Bem.id)).where(Bem.situacao != "baixado").group_by(Bem.localizacao_id)).all())
    return [_localizacao(l, totais) for l in servico_localizacoes.listar(sessao)]


@roteador.post("/localizacoes/lados/{lado_id}/salas", response_model=esquema.LocalizacaoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar uma sala",
               description="Só CONTROLE_TOTAL. O usuário digita só o número: andar e lado vêm do nível de cima (código `05A03`). `409` se o código já existir.",
               responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **resposta_nao_encontrado("Localização")})
def criar_sala(lado_id: uuid.UUID, dados: esquema.GravacaoSala, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.LocalizacaoLeitura:
    with _traduzir(sessao):
        return _localizacao(servico_localizacoes.criar_sala(sessao, lado_id, dados.numero), {})


@roteador.post("/localizacoes/andares/{andar_id}/areas-comuns", response_model=esquema.LocalizacaoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar uma área comum no andar",
               description="Só CONTROLE_TOTAL. Hall dos elevadores, copa, escada etc., direto no andar e fora da numeração A/B (sem lado). O código junta o andar e a `sigla` "
                           "(`05H`, `-1H`); `409` se já existir. Como toda sala, precisa de setor e responsável antes do primeiro bem.",
               responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **resposta_nao_encontrado("Localização")})
def criar_area_comum(andar_id: uuid.UUID, dados: esquema.GravacaoAreaComum, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.LocalizacaoLeitura:
    with _traduzir(sessao):
        return _localizacao(servico_localizacoes.criar_area_comum(sessao, andar_id, dados.nome, dados.sigla), {})


@roteador.put("/localizacoes/{localizacao_id}/dados", response_model=esquema.LocalizacaoLeitura, summary="Setor e responsável da sala",
              description="No primeiro cadastro de bem na sala, quem tem MODIFICACAO informa setor e responsável (só enquanto faltam); depois, só CONTROLE_TOTAL altera. "
              "Trocar o responsável atualiza todos os bens da sala, com registro no histórico de cada um.", responses={**CONFLITO, **INVALIDO, **resposta_nao_encontrado("Localização")})
def dados_sala(localizacao_id: uuid.UUID, dados: esquema.GravacaoDadosSala, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.LocalizacaoLeitura:
    with _traduzir(sessao):
        sala = servico_localizacoes.definir_dados_sala(sessao, localizacao_id, dados.setor_id, dados.responsavel_id, usuario, administra=controle_total(sessao, usuario))
        return _localizacao(sala, {})


@roteador.put("/localizacoes/{localizacao_id}", response_model=esquema.LocalizacaoLeitura, summary="Renomear ou inativar uma localização",
              description="Só CONTROLE_TOTAL.", responses={**SEM_ADMIN, **resposta_nao_encontrado("Localização")})
def atualizar_localizacao(localizacao_id: uuid.UUID, dados: esquema.AtualizacaoLocalizacao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.LocalizacaoLeitura:
    with _traduzir(sessao):
        return _localizacao(servico_localizacoes.atualizar_sala(sessao, localizacao_id, nome=dados.nome, ativo=dados.ativo), {})


@roteador.delete("/localizacoes/{localizacao_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir uma sala",
                 description="Só CONTROLE_TOTAL. Sala com bens vinculados não pode ser excluída, só inativada (`409`).", responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Localização")})
def excluir_sala(localizacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> Response:
    with _traduzir(sessao):
        servico_localizacoes.excluir_sala(sessao, localizacao_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Grupos e parâmetros -----------------------------------------------------------------------

@roteador.get("/grupos", response_model=list[esquema.GrupoLeitura], summary="Grupos de material", description="Com vida útil e residual (a depreciação).")
def listar_grupos(todos: bool = Query(False, description="Inclui os inativos."), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.GrupoLeitura]:
    return [esquema.GrupoLeitura.model_validate(g, from_attributes=True) for g in servico_parametros.listar_grupos(sessao, todos)]


@roteador.post("/grupos", response_model=esquema.GrupoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar grupo de material",
               description="Só CONTROLE_TOTAL. Código único (`409`).", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO})
def criar_grupo(dados: esquema.GravacaoGrupo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.GrupoLeitura:
    with _traduzir(sessao):
        return esquema.GrupoLeitura.model_validate(servico_parametros.criar_grupo(sessao, dados.model_dump()), from_attributes=True)


@roteador.put("/grupos/{grupo_id}", response_model=esquema.GrupoLeitura, summary="Alterar grupo de material",
              description="Só CONTROLE_TOTAL. A vida útil de cada grupo é parâmetro editável (a tabela oficial ainda será obtida).", responses={**SEM_ADMIN, **INVALIDO, **resposta_nao_encontrado("Grupo")})
def atualizar_grupo(grupo_id: uuid.UUID, dados: esquema.AtualizacaoGrupo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.GrupoLeitura:
    with _traduzir(sessao):
        return esquema.GrupoLeitura.model_validate(servico_parametros.atualizar_grupo(sessao, grupo_id, dados.model_dump(exclude_unset=True)), from_attributes=True)


@roteador.delete("/grupos/{grupo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir grupo de material",
                 description="Só CONTROLE_TOTAL. Grupo com bens só pode ser inativado (`409`).", responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Grupo")})
def excluir_grupo(grupo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> Response:
    with _traduzir(sessao):
        servico_parametros.excluir_grupo(sessao, grupo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/prefixos", response_model=list[esquema.PrefixoLeitura], summary="Prefixos da chapa",
              description="Prefixos que vêm antes do número da chapa (SPI, SLT, DERSA...), o padrão primeiro. Só os ativos, a menos que `todos=true`.")
def listar_prefixos(todos: bool = Query(False, description="Inclui os inativos."), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.PrefixoLeitura]:
    return [esquema.PrefixoLeitura.model_validate(p, from_attributes=True) for p in servico_parametros.listar_prefixos(sessao, todos)]


@roteador.post("/prefixos", response_model=esquema.PrefixoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar prefixo da chapa",
               description="Só CONTROLE_TOTAL. Só letras e números, gravado em maiúsculas; único (`409`).", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO})
def criar_prefixo(dados: esquema.GravacaoPrefixo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.PrefixoLeitura:
    with _traduzir(sessao):
        return esquema.PrefixoLeitura.model_validate(servico_parametros.criar_prefixo(sessao, dados.codigo), from_attributes=True)


@roteador.put("/prefixos/{prefixo_id}", response_model=esquema.PrefixoLeitura, summary="Alterar prefixo da chapa",
              description="Só CONTROLE_TOTAL. `padrao=true` troca o prefixo padrão do cadastro; o padrão não pode ser inativado nem desmarcado (`409`).",
              responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Prefixo")})
def atualizar_prefixo(prefixo_id: uuid.UUID, dados: esquema.AtualizacaoPrefixo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.PrefixoLeitura:
    with _traduzir(sessao):
        return esquema.PrefixoLeitura.model_validate(servico_parametros.atualizar_prefixo(sessao, prefixo_id, dados.model_dump(exclude_unset=True)), from_attributes=True)


@roteador.delete("/prefixos/{prefixo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir prefixo da chapa",
                 description="Só CONTROLE_TOTAL. O padrão e os prefixos com bens só podem ser inativados (`409`).", responses={**SEM_ADMIN, **CONFLITO, **resposta_nao_encontrado("Prefixo")})
def excluir_prefixo(prefixo_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> Response:
    with _traduzir(sessao):
        servico_parametros.excluir_prefixo(sessao, prefixo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros", response_model=esquema.ParametrosPatrimonio, summary="Parâmetros do módulo", description="Valor da UFESP (regra de \"não patrimoniável\").")
def obter_parametros(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.ParametrosPatrimonio:
    return esquema.ParametrosPatrimonio(**servico_parametros.obter_parametros(sessao))


@roteador.put("/parametros", response_model=esquema.ParametrosPatrimonio, summary="Alterar parâmetros do módulo",
              description="Só CONTROLE_TOTAL.", responses={**SEM_ADMIN, **INVALIDO})
def salvar_parametros(dados: esquema.ParametrosPatrimonio, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.ParametrosPatrimonio:
    with _traduzir(sessao):
        return esquema.ParametrosPatrimonio(**servico_parametros.salvar_parametros(sessao, dados.model_dump()))


# --- Bens --------------------------------------------------------------------------------------

BEM_NAO_ENCONTRADO = resposta_nao_encontrado("Bem")


@roteador.get("/bens", response_model=esquema.ListaBens, summary="Listar bens",
              description="Paginada. `q` procura na chapa, descrição, marca, modelo e número de série; `localizacao_id` aceita um andar, lado ou sala (inclui os de baixo). "
              "Baixados só aparecem com `situacao=baixado` ou `incluir_baixados`. `ordenar_por` e `direcao` ordenam por qualquer coluna da lista (vale para todas as páginas; vazios ficam no fim).")
def listar_bens(
    q: str | None = None, situacao: str | None = Query(None, description="Uma situação ou várias separadas por vírgula (ex.: `inservivel,extraviado`).", max_length=100), localizacao_id: uuid.UUID | None = None, grupo_id: uuid.UUID | None = None,
    conservacao: int | None = Query(None, ge=1, le=5), garantia: esquema.GarantiaBem | None = None, contabeis_pendentes: bool | None = None, incluir_baixados: bool = False,
    ordenar_por: str = Query("chapa", description="Coluna de ordenação: " + ", ".join(servico_bens.ORDENAVEIS) + "."), direcao: Literal["asc", "desc"] = "asc",
    pagina: int = Query(1, ge=1), tamanho: int = Query(30, ge=1, le=200), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver),
) -> esquema.ListaBens:
    with _traduzir():
        bens, total = servico_bens.listar(sessao, q=q, situacao=situacao, localizacao_id=localizacao_id, grupo_id=grupo_id, conservacao=conservacao, garantia=garantia,
                                          contabeis_pendentes=contabeis_pendentes, incluir_baixados=incluir_baixados, pagina=pagina, tamanho=tamanho,
                                          ordenar_por=ordenar_por, direcao=direcao)
    return esquema.ListaBens(total=total, pagina=pagina, itens=[_bem_completo(sessao, b) for b in bens])


@roteador.post("/bens", response_model=esquema.BemLeitura, status_code=status.HTTP_201_CREATED, summary="Cadastrar bem",
               description="MODIFICACAO. Obrigatórios: chapa, descrição, sala, conservação (1 a 5), situação (Ativo ou Em manutenção) e origem. A sala precisa ter setor e responsável "
               "(`409 sala_sem_responsavel`); o bem herda o responsável da sala. Chapa repetida: `409`. Com `id_cliente` já enviado (reenvio offline), devolve o bem existente com `200`.",
               responses={**CONFLITO, **INVALIDO, 200: {"description": "Reenvio de um cadastro offline já recebido (`id_cliente`)."}})
def cadastrar_bem(dados: esquema.GravacaoBem, requisicao: Request, resposta: Response, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        bem, criado = servico_bens.criar(sessao, dados.model_dump(), usuario, origem=_origem(requisicao))
    if not criado:
        resposta.status_code = status.HTTP_200_OK
    return _bem_completo(sessao, bem)


@roteador.get("/bens/sugestoes-descricao", response_model=list[str], summary="Sugestões de descrição",
              description="Descrições já cadastradas que casam com o texto digitado (mínimo de 2 caracteres, até 8), as que começam pelo texto e as mais usadas primeiro. "
              "Alimenta o autocompletar do cadastro, para padronizar (ex.: digitar \"comp\" sugere \"Computador\").")
def sugestoes_descricao(q: str = Query("", max_length=100), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[str]:
    return servico_bens.sugerir_descricoes(sessao, q)


@roteador.get("/bens/chapa/{chapa}", response_model=esquema.BemLeitura, summary="Buscar bem pela chapa ou pelo número de série",
              description="Usado na leitura do código pela câmera e na digitação: acha o bem pela chapa ou, se não houver, pelo número de série. Abre o bem ou, se não existir (`404`), a tela abre o cadastro com a chapa preenchida. Número de série repetido em mais de um bem: `409 ambiguo` (use a chapa). A mesma busca vale para movimentações (`chapas`), listas de inservíveis/extraviados e baixa.", responses={**BEM_NAO_ENCONTRADO, **CONFLITO})
def bem_por_chapa(chapa: str, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.BemLeitura:
    with _traduzir():
        return _bem_completo(sessao, servico_bens.obter_por_chapa(sessao, chapa))


@roteador.get("/bens/{bem_id}", response_model=esquema.BemLeitura, summary="Detalhe do bem", responses=BEM_NAO_ENCONTRADO)
def obter_bem(bem_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.BemLeitura:
    with _traduzir():
        return _bem_completo(sessao, servico_bens.obter(sessao, bem_id))


@roteador.put("/bens/{bem_id}", response_model=esquema.BemLeitura, summary="Alterar bem",
              description="MODIFICACAO. Só os campos enviados mudam e cada campo alterado vira um evento do histórico (anterior, novo, autor, origem). Bem baixado: `409 bem_baixado`. "
              "Local, responsável, inservível/extraviado e baixa seguem fluxos próprios.", responses={**CONFLITO, **INVALIDO, **BEM_NAO_ENCONTRADO})
def alterar_bem(bem_id: uuid.UUID, dados: esquema.AtualizacaoBem, requisicao: Request, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_bens.atualizar(sessao, bem_id, dados.model_dump(exclude_unset=True), usuario, origem=_origem(requisicao)))


@roteador.post("/bens/{bem_id}/localizar", response_model=esquema.BemLeitura, summary="Localizar bem sem local (levantamento)",
               description="MODIFICACAO. Informa a sala de um bem que ainda está em \"NECESSÁRIO ATUALIZAR\" (sem local), sem movimentação nem aprovação; fica no histórico e no trajeto (`localizou`). "
               "Bem que já tem sala: `409 bem_ja_localizado` (use a movimentação). Sala sem setor e responsável: `409 sala_sem_responsavel`. Extraviado, baixado, com classificação pendente ou em movimentação: `409`.",
               responses={**CONFLITO, **INVALIDO, **BEM_NAO_ENCONTRADO})
def localizar_bem(bem_id: uuid.UUID, dados: esquema.LocalizacaoBem, requisicao: Request, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_bens.localizar(sessao, bem_id, dados.localizacao_id, usuario, origem=_origem(requisicao)))


@roteador.post("/bens/{bem_id}/local", response_model=esquema.BemLeitura, summary="Ajustar o local sem movimentação",
               description="Só CONTROLE_TOTAL. Motivo obrigatório, registrado no histórico e no trajeto. Extraviado, baixado, com classificação pendente ou em movimentação: `409`. "
               "Inservível só vai para sala do setor \"Depósito inservível\".", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **BEM_NAO_ENCONTRADO})
def ajustar_local(bem_id: uuid.UUID, dados: esquema.AjusteLocal, requisicao: Request, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_bens.ajustar_local(sessao, bem_id, dados.localizacao_id, dados.motivo, usuario, origem=_origem(requisicao)))


@roteador.post("/bens/{bem_id}/reverter", response_model=esquema.BemLeitura, summary="Devolver inservível ou extraviado a Ativo",
               description="Só CONTROLE_TOTAL, com justificativa (mínimo de 10 caracteres). No extraviado, informe a sala onde foi encontrado.", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **BEM_NAO_ENCONTRADO})
def reverter_bem(bem_id: uuid.UUID, dados: esquema.Reversao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_classificacoes.reverter(sessao, bem_id, dados.justificativa, usuario, localizacao_id=dados.localizacao_id))


@roteador.post("/bens/{bem_id}/fotos", response_model=esquema.BemLeitura, status_code=status.HTTP_201_CREATED, summary="Adicionar foto",
               description="`multipart/form-data` com `arquivo` (PNG ou JPG). Até 3 fotos por bem (`409 limite_fotos`).", responses={**CONFLITO, **INVALIDO, **BEM_NAO_ENCONTRADO})
def adicionar_foto(bem_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_bens.adicionar_foto(sessao, bem_id, arquivo.file, arquivo.filename or "foto.jpg", usuario))


@roteador.delete("/bens/{bem_id}/fotos/{foto_id}", response_model=esquema.BemLeitura, summary="Remover foto", responses={**CONFLITO, **BEM_NAO_ENCONTRADO})
def remover_foto(bem_id: uuid.UUID, foto_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BemLeitura:
    with _traduzir(sessao):
        return _bem_completo(sessao, servico_bens.remover_foto(sessao, bem_id, foto_id, usuario))


@roteador.get("/bens/{bem_id}/fotos/{foto_id}/arquivo", response_class=FileResponse, summary="Baixar a foto", responses=BEM_NAO_ENCONTRADO)
def baixar_foto(bem_id: uuid.UUID, foto_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)):
    with _traduzir():
        bem = servico_bens.obter(sessao, bem_id)
    foto = next((f for f in bem.fotos if f.id == foto_id), None)
    if foto is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Foto não encontrada.", "nao_encontrado")
    try:
        return servico_anexos.resposta_download(foto.anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


@roteador.get("/bens/{bem_id}/historico", response_model=list[esquema.EventoLeitura], summary="Histórico do bem (linha do tempo ou de um campo)",
              description="Todos os eventos, do mais recente ao mais antigo; com `campo`, só o histórico daquele campo (o ícone ao lado de cada campo). Registros não se apagam.", responses=BEM_NAO_ENCONTRADO)
def historico_bem(bem_id: uuid.UUID, campo: str | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.EventoLeitura]:
    with _traduzir():
        return [_evento(e) for e in servico_bens.historico(sessao, bem_id, campo)]


@roteador.get("/bens/{bem_id}/trajeto", response_model=list[esquema.EventoLeitura], summary="Trajeto do bem",
              description="Todos os locais por onde passou, do mais antigo ao mais recente, com quem pediu e quem autorizou cada mudança (em `dados`).", responses=BEM_NAO_ENCONTRADO)
def trajeto_bem(bem_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.EventoLeitura]:
    with _traduzir():
        return [_evento(e) for e in servico_bens.trajeto(sessao, bem_id)]


# --- Movimentações -----------------------------------------------------------------------------

MOV_NAO_ENCONTRADA = resposta_nao_encontrado("Movimentação")


@roteador.get("/movimentacoes", response_model=list[esquema.MovimentacaoLeitura], summary="Listar movimentações",
              description="Filtros por status, período (`de`/`ate`), solicitante, origem e destino.")
def listar_movimentacoes(status_: Literal["pendente", "autorizada", "concluida", "recusada", "cancelada"] | None = Query(None, alias="status"), solicitante_id: int | None = None,
                         de: date | None = None, ate: date | None = None, origem_id: uuid.UUID | None = None, destino_id: uuid.UUID | None = None,
                         sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.MovimentacaoLeitura]:
    return [_movimentacao(m) for m in servico_movimentacoes.listar(sessao, status=status_, solicitante_id=solicitante_id, de=de, ate=ate, origem_id=origem_id, destino_id=destino_id)]


@roteador.post("/movimentacoes", response_model=esquema.MovimentacaoLeitura, status_code=status.HTTP_201_CREATED, summary="Solicitar movimentação",
               description="MODIFICACAO. Bens (por `bens_ids` e/ou `chapas`) de origens diferentes com um único destino. Recusa (`409`) bem baixado, extraviado, com classificação pendente, já em outra movimentação "
               "ou inservível com destino que não seja \"Depósito inservível\". Avisa quem autoriza. Reenvio com o mesmo `id_cliente` devolve a existente (`200`).",
               responses={**CONFLITO, **INVALIDO, 200: {"description": "Reenvio já recebido (`id_cliente`)."}})
def solicitar_movimentacao(dados: esquema.GravacaoMovimentacao, resposta: Response, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        mov, criada = servico_movimentacoes.solicitar(sessao, dados.bens_ids, dados.destino_id, dados.motivo, usuario, id_cliente=dados.id_cliente, chapas=dados.chapas)
    if not criada:
        resposta.status_code = status.HTTP_200_OK
    return _movimentacao(mov)


@roteador.get("/movimentacoes/{movimentacao_id}", response_model=esquema.MovimentacaoLeitura, summary="Detalhe da movimentação", responses=MOV_NAO_ENCONTRADA)
def obter_movimentacao(movimentacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.MovimentacaoLeitura:
    with _traduzir():
        return _movimentacao(servico_movimentacoes.obter(sessao, movimentacao_id))


@roteador.post("/movimentacoes/{movimentacao_id}/autorizar", response_model=esquema.MovimentacaoLeitura, summary="Autorizar movimentação",
               description="Só CONTROLE_TOTAL e nunca o próprio solicitante (`403 auto_aprovacao`). Avisa o solicitante.", responses={**SEM_ADMIN, **CONFLITO, **MOV_NAO_ENCONTRADA})
def autorizar_movimentacao(movimentacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        return _movimentacao(servico_movimentacoes.autorizar(sessao, movimentacao_id, usuario))


@roteador.post("/movimentacoes/{movimentacao_id}/recusar", response_model=esquema.MovimentacaoLeitura, summary="Recusar movimentação",
               description="Só CONTROLE_TOTAL e nunca o próprio solicitante. A recusa exige motivo.", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **MOV_NAO_ENCONTRADA})
def recusar_movimentacao(movimentacao_id: uuid.UUID, dados: esquema.Motivo, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        return _movimentacao(servico_movimentacoes.recusar(sessao, movimentacao_id, dados.motivo, usuario))


@roteador.post("/movimentacoes/{movimentacao_id}/cancelar", response_model=esquema.MovimentacaoLeitura, summary="Cancelar movimentação",
               description="Só o solicitante, enquanto a movimentação está pendente.", responses={**CONFLITO, **MOV_NAO_ENCONTRADA})
def cancelar_movimentacao(movimentacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        return _movimentacao(servico_movimentacoes.cancelar(sessao, movimentacao_id, usuario))


@roteador.post("/movimentacoes/{movimentacao_id}/receber", response_model=esquema.MovimentacaoLeitura, summary="Confirmar o recebimento de um bem",
               description="Só CONTROLE_TOTAL, no celular, lendo o código de cada bem. O recebimento é parcial: cada bem confirmado muda de local na hora (e passa ao responsável da "
               "sala de destino); os outros continuam na origem. Com todos recebidos, a movimentação conclui sozinha.", responses={**SEM_ADMIN, **CONFLITO, **MOV_NAO_ENCONTRADA})
def receber_bem(movimentacao_id: uuid.UUID, dados: esquema.Recebimento, requisicao: Request, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        return _movimentacao(servico_movimentacoes.receber(sessao, movimentacao_id, dados.bem_id, usuario, origem=_origem(requisicao)))


@roteador.post("/movimentacoes/{movimentacao_id}/concluir", response_model=esquema.MovimentacaoLeitura, summary="Encerrar o recebimento",
               description="Só CONTROLE_TOTAL. Os bens que chegaram ficam no destino; os que não chegaram ficam livres para outra movimentação, e o histórico registra quais vieram e quais ficaram.",
               responses={**SEM_ADMIN, **CONFLITO, **MOV_NAO_ENCONTRADA})
def concluir_movimentacao(movimentacao_id: uuid.UUID, requisicao: Request, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.MovimentacaoLeitura:
    with _traduzir(sessao):
        return _movimentacao(servico_movimentacoes.concluir(sessao, movimentacao_id, usuario, origem=_origem(requisicao)))


# --- Inservíveis e extraviados -----------------------------------------------------------------

CLA_NAO_ENCONTRADA = resposta_nao_encontrado("Lista de classificação")


@roteador.get("/classificacoes", response_model=list[esquema.ClassificacaoLeitura], summary="Listas de inservíveis e extraviados",
              description="Filtros por status e solicitante.")
def listar_classificacoes(status_: Literal["rascunho", "pendente", "aprovada", "parcial", "recusada"] | None = Query(None, alias="status"), solicitante_id: int | None = None,
                          sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.ClassificacaoLeitura]:
    return [_classificacao(c) for c in servico_classificacoes.listar(sessao, status=status_, solicitante_id=solicitante_id)]


@roteador.post("/classificacoes", response_model=esquema.ClassificacaoLeitura, status_code=status.HTTP_201_CREATED, summary="Começar uma lista (rascunho)",
               description="MODIFICACAO. O tipo é `inservivel` ou `extraviado`. A lista em montagem é rascunho e resiste à perda de sinal (reenvio com `id_cliente` devolve a existente, `200`).",
               responses={**INVALIDO, 200: {"description": "Reenvio já recebido (`id_cliente`)."}})
def criar_classificacao(dados: esquema.GravacaoLista, resposta: Response, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        lista, criada = servico_classificacoes.criar(sessao, dados.tipo or "", usuario, id_cliente=dados.id_cliente)
    if not criada:
        resposta.status_code = status.HTTP_200_OK
    return _classificacao(lista)


@roteador.get("/classificacoes/{classificacao_id}", response_model=esquema.ClassificacaoLeitura, summary="Detalhe da lista", responses=CLA_NAO_ENCONTRADA)
def obter_classificacao(classificacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.ClassificacaoLeitura:
    with _traduzir():
        return _classificacao(servico_classificacoes.obter(sessao, classificacao_id))


@roteador.delete("/classificacoes/{classificacao_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Descartar o rascunho",
                 description="Só quem montou a lista, e só enquanto é rascunho.", responses={**CONFLITO, **CLA_NAO_ENCONTRADA})
def descartar_classificacao(classificacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> Response:
    with _traduzir(sessao):
        servico_classificacoes.descartar(sessao, classificacao_id, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/classificacoes/{classificacao_id}/bens", response_model=esquema.ClassificacaoLeitura, summary="Incluir um bem na lista",
               description="Pela chapa (leitura do código ou digitada) ou pelo `bem_id` (extraviado, escolhido na lista de uma sala). Só bens cadastrados e Ativos ou Em manutenção: "
               "os demais voltam `409` com o aviso, sem interromper a leitura.", responses={**CONFLITO, **INVALIDO, **CLA_NAO_ENCONTRADA})
def incluir_bem_classificacao(classificacao_id: uuid.UUID, dados: esquema.EntradaBem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.adicionar_bem(sessao, classificacao_id, usuario, bem_id=dados.bem_id, chapa=dados.chapa))


@roteador.delete("/classificacoes/{classificacao_id}/bens/{item_id}", response_model=esquema.ClassificacaoLeitura, summary="Tirar um bem da lista",
                 responses={**CONFLITO, **CLA_NAO_ENCONTRADA})
def tirar_bem_classificacao(classificacao_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.remover_bem(sessao, classificacao_id, item_id, usuario))


@roteador.post("/classificacoes/{classificacao_id}/justificativa", response_model=esquema.ClassificacaoLeitura, summary="Justificar os bens marcados",
               description="Uma justificativa (mínimo de 10 caracteres) vale para todos os itens marcados; também dá para justificar um a um.", responses={**CONFLITO, **INVALIDO, **CLA_NAO_ENCONTRADA})
def justificar_classificacao(classificacao_id: uuid.UUID, dados: esquema.Justificativa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.justificar(sessao, classificacao_id, dados.itens_ids, dados.justificativa, usuario))


@roteador.post("/classificacoes/{classificacao_id}/itens/{item_id}/anexo", response_model=esquema.ClassificacaoLeitura, summary="Anexar ao item",
               description="`multipart/form-data` com `arquivo`. Extraviado: opcional (boletim de ocorrência, e-mail ou foto). Inservível: foto opcional (PNG ou JPG).",
               responses={**CONFLITO, **INVALIDO, **CLA_NAO_ENCONTRADA})
def anexar_classificacao(classificacao_id: uuid.UUID, item_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
                         usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.anexar(sessao, classificacao_id, item_id, arquivo.file, arquivo.filename or "anexo", usuario))


@roteador.get("/classificacoes/{classificacao_id}/itens/{item_id}/anexo", response_class=FileResponse, summary="Baixar o anexo do item", responses=CLA_NAO_ENCONTRADA)
def baixar_anexo_classificacao(classificacao_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)):
    with _traduzir():
        lista = servico_classificacoes.obter(sessao, classificacao_id)
    item = next((i for i in lista.itens if i.id == item_id), None)
    if item is None or item.anexo is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Este item não tem anexo.", "nao_encontrado")
    try:
        return servico_anexos.resposta_download(item.anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


@roteador.post("/classificacoes/{classificacao_id}/enviar", response_model=esquema.ClassificacaoLeitura, summary="Enviar para aprovação",
               description="Todos os bens precisam de justificativa (`409 sem_justificativa`). Os bens ficam com \"Classificação pendente\" e não podem ser movimentados. Avisa quem aprova.",
               responses={**CONFLITO, **INVALIDO, **CLA_NAO_ENCONTRADA})
def enviar_classificacao(classificacao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.enviar(sessao, classificacao_id, usuario))


@roteador.post("/classificacoes/{classificacao_id}/decisao", response_model=esquema.ClassificacaoLeitura, summary="Aprovar, aprovar em parte ou recusar",
               description="Só CONTROLE_TOTAL e nunca o próprio solicitante (`403 auto_aprovacao`). `aprovados_ids` são os itens aprovados (mudam de situação); os demais são recusados, com `motivo_recusa`, e voltam ao que eram.",
               responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **CLA_NAO_ENCONTRADA})
def decidir_classificacao(classificacao_id: uuid.UUID, dados: esquema.Decisao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.ClassificacaoLeitura:
    with _traduzir(sessao):
        return _classificacao(servico_classificacoes.decidir(sessao, classificacao_id, dados.aprovados_ids, dados.motivo_recusa, usuario))


# --- Baixas ------------------------------------------------------------------------------------

BAIXA_NAO_ENCONTRADA = resposta_nao_encontrado("Baixa")


@roteador.get("/baixas", response_model=list[esquema.BaixaLeitura], summary="Listar baixas", description="Filtros por status e solicitante.")
def listar_baixas(status_: Literal["rascunho", "pendente", "aprovada", "parcial", "recusada"] | None = Query(None, alias="status"), solicitante_id: int | None = None,
                  sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.BaixaLeitura]:
    return [_baixa(b) for b in servico_baixas.listar(sessao, status=status_, solicitante_id=solicitante_id)]


@roteador.post("/baixas", response_model=esquema.BaixaLeitura, status_code=status.HTTP_201_CREATED, summary="Começar uma baixa (rascunho)",
               description="MODIFICACAO. Reenvio com o mesmo `id_cliente` devolve a existente (`200`).", responses={200: {"description": "Reenvio já recebido (`id_cliente`)."}})
def criar_baixa(dados: esquema.GravacaoLista, resposta: Response, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        baixa, criada = servico_baixas.criar(sessao, usuario, id_cliente=dados.id_cliente)
    if not criada:
        resposta.status_code = status.HTTP_200_OK
    return _baixa(baixa)


@roteador.get("/baixas/{baixa_id}", response_model=esquema.BaixaLeitura, summary="Detalhe da baixa", responses=BAIXA_NAO_ENCONTRADA)
def obter_baixa(baixa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.BaixaLeitura:
    with _traduzir():
        return _baixa(servico_baixas.obter(sessao, baixa_id))


@roteador.delete("/baixas/{baixa_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Descartar o rascunho", responses={**CONFLITO, **BAIXA_NAO_ENCONTRADA})
def descartar_baixa(baixa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> Response:
    with _traduzir(sessao):
        servico_baixas.descartar(sessao, baixa_id, usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/baixas/{baixa_id}/bens", response_model=esquema.BaixaLeitura, summary="Incluir um bem na baixa",
               description="Leitura contínua de códigos ou chapa digitada (extraviados). Só entram bens já aprovados como inservíveis ou extraviados (`409` nos demais).",
               responses={**CONFLITO, **INVALIDO, **BAIXA_NAO_ENCONTRADA})
def incluir_bem_baixa(baixa_id: uuid.UUID, dados: esquema.EntradaBem, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        return _baixa(servico_baixas.adicionar_bem(sessao, baixa_id, usuario, bem_id=dados.bem_id, chapa=dados.chapa))


@roteador.delete("/baixas/{baixa_id}/bens/{item_id}", response_model=esquema.BaixaLeitura, summary="Tirar um bem da baixa", responses={**CONFLITO, **BAIXA_NAO_ENCONTRADA})
def tirar_bem_baixa(baixa_id: uuid.UUID, item_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        return _baixa(servico_baixas.remover_bem(sessao, baixa_id, item_id, usuario))


@roteador.post("/baixas/{baixa_id}/motivo", response_model=esquema.BaixaLeitura, summary="Motivo e processo dos itens marcados",
               description="Alienação, doação, transferência, inutilização ou extravio, e o número do processo, para a seleção toda ou por grupos.", responses={**CONFLITO, **INVALIDO, **BAIXA_NAO_ENCONTRADA})
def motivo_baixa(baixa_id: uuid.UUID, dados: esquema.MotivoItensBaixa, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        return _baixa(servico_baixas.definir_motivo(sessao, baixa_id, dados.itens_ids, dados.motivo, dados.processo, usuario))


@roteador.post("/baixas/{baixa_id}/enviar", response_model=esquema.BaixaLeitura, summary="Enviar a baixa para aprovação",
               description="Todos os itens precisam de motivo e processo (`409 sem_motivo`). Avisa quem aprova.", responses={**CONFLITO, **INVALIDO, **BAIXA_NAO_ENCONTRADA})
def enviar_baixa(baixa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(operar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        return _baixa(servico_baixas.enviar(sessao, baixa_id, usuario))


@roteador.post("/baixas/{baixa_id}/decisao", response_model=esquema.BaixaLeitura, summary="Aprovar, aprovar em parte ou recusar a baixa",
               description="Só CONTROLE_TOTAL e nunca o próprio solicitante (`403 auto_aprovacao`). Os aprovados viram **Baixado** (com data, solicitante e aprovador), saem dos painéis e "
               "nunca são excluídos; a aprovação gera o termo em PDF. A baixa aqui não baixa o bem no SAM.", responses={**SEM_ADMIN, **CONFLITO, **INVALIDO, **BAIXA_NAO_ENCONTRADA})
def decidir_baixa(baixa_id: uuid.UUID, dados: esquema.Decisao, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(administrar)) -> esquema.BaixaLeitura:
    with _traduzir(sessao):
        return _baixa(servico_baixas.decidir(sessao, baixa_id, dados.aprovados_ids, dados.motivo_recusa, usuario))


@roteador.get("/baixas/{baixa_id}/termo", response_class=FileResponse, summary="Baixar o termo de baixa (PDF)",
              description="Lista de bens, valores, situação anterior e justificativas, para instruir o processo.", responses=BAIXA_NAO_ENCONTRADA)
def baixar_termo(baixa_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)):
    from app.models.anexo import Anexo

    with _traduzir():
        baixa = servico_baixas.obter(sessao, baixa_id)
    anexo = sessao.get(Anexo, baixa.termo_anexo_id) if baixa.termo_anexo_id else None
    if anexo is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Esta baixa ainda não tem termo.", "nao_encontrado")
    try:
        return servico_anexos.resposta_download(anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


# --- Painel e exportação -----------------------------------------------------------------------

@roteador.get("/painel", response_model=esquema.PainelPatrimonio, summary="Painel do Patrimônio",
              description="Indicadores do topo, agrupamento por andar, sala, setor ou grupo (quantidade e valor), bens fora de garantia (com os que vencem em 90 dias) e bens com dados "
              "contábeis pendentes. O baixado sai do painel; os de dados pendentes entram na contagem mas ficam fora dos totais de valor.")
def painel(agrupar_por: esquema.Agrupamento = "andar", situacao: esquema.SituacaoBem | None = None, conservacao: int | None = Query(None, ge=1, le=5),
           garantia: esquema.GarantiaBem | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> esquema.PainelPatrimonio:
    return esquema.PainelPatrimonio(**servico_paineis.painel(sessao, agrupar_por=agrupar_por, situacao=situacao, conservacao=conservacao, garantia=garantia))


@roteador.get("/painel/grupo", response_model=list[esquema.BemLeitura], summary="Bens de uma barra do gráfico",
              description="Clicar numa barra lista os bens daquele grupo (`chave` vem do painel).")
def bens_do_grupo(agrupar_por: esquema.Agrupamento, chave: str, situacao: esquema.SituacaoBem | None = None, conservacao: int | None = Query(None, ge=1, le=5),
                  garantia: esquema.GarantiaBem | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> list[esquema.BemLeitura]:
    bens = servico_paineis.bens_do_grupo(sessao, agrupar_por, chave, situacao=situacao, conservacao=conservacao, garantia=garantia)
    return [_bem_completo(sessao, b) for b in bens]


@roteador.get("/classificacoes/{classificacao_id}/relatorio", response_class=Response, summary="Relatório da lista de inservíveis ou extraviados (PDF ou Excel)",
              description="PDF **consolidado** (índice clicável, relatório com item, chapa, descrição com marca e modelo, local, últimas fotos com data, hora e quem registrou, "
                          "justificativa e link do anexo; fotos em tamanho grande e o anexo de cada item com contracapa, páginas numeradas em sequência) ou Excel (mesmas colunas, "
                          "miniatura da última foto e aba Fotos). LEITURA. Vale para rascunho, pendente e decidida.",
              responses={200: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **INVALIDO, **resposta_nao_encontrado("Lista")})
def relatorio_classificacao(classificacao_id: uuid.UUID, formato: FORMATO = "pdf", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    with _traduzir():
        lista = servico_classificacoes.obter(sessao, classificacao_id)
        conteudo, nome, tipo = relatorio_listas.relatorio_da_classificacao(sessao, lista, formato, usuario, hoje_sao_paulo().strftime("%Y-%m-%d"))
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/baixas/{baixa_id}/relatorio", response_class=Response, summary="Relatório da baixa (PDF ou Excel)",
              description="Mesmo formato do relatório das listas de inservíveis e extraviados, com motivo e processo no lugar da justificativa; o anexo é o do extravio ou do "
                          "inservível que originou a baixa de cada bem. LEITURA. Vale para rascunho, pendente e decidida (o termo oficial continua em `/termo`).",
              responses={200: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **INVALIDO, **BAIXA_NAO_ENCONTRADA})
def relatorio_baixa(baixa_id: uuid.UUID, formato: FORMATO = "pdf", sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    with _traduzir():
        baixa = servico_baixas.obter(sessao, baixa_id)
        conteudo, nome, tipo = relatorio_listas.relatorio_da_baixa(sessao, baixa, formato, usuario, hoje_sao_paulo().strftime("%Y-%m-%d"))
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.get("/exportar/{relatorio}", response_class=Response, summary="Exportar (Excel ou PDF)",
              description="`relatorio`: `bens`, `fora-garantia`, `painel` ou `movimentacoes`. Os filtros são os mesmos das listas e do painel.",
              responses={200: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}, **INVALIDO})
def exportar(relatorio: Literal["bens", "fora-garantia", "painel", "movimentacoes"], formato: FORMATO = "xlsx", q: str | None = None, situacao: esquema.SituacaoBem | None = None,
             localizacao_id: uuid.UUID | None = None, grupo_id: uuid.UUID | None = None, conservacao: int | None = Query(None, ge=1, le=5), garantia: esquema.GarantiaBem | None = None,
             agrupar_por: esquema.Agrupamento = "andar", status_: str | None = Query(None, alias="status"), de: date | None = None, ate: date | None = None,
             origem_id: uuid.UUID | None = None, destino_id: uuid.UUID | None = None, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(ver)) -> Response:
    with _traduzir():
        if relatorio == "bens":
            conteudo, nome, tipo = exportacao.exportar_bens(sessao, formato, usuario, q=q, situacao=situacao, localizacao_id=localizacao_id, grupo_id=grupo_id, conservacao=conservacao, garantia=garantia)
        elif relatorio == "fora-garantia":
            conteudo, nome, tipo = exportacao.exportar_fora_garantia(sessao, formato, usuario)
        elif relatorio == "painel":
            conteudo, nome, tipo = exportacao.exportar_painel(sessao, formato, usuario, agrupar_por, situacao=situacao, conservacao=conservacao, garantia=garantia)
        else:
            conteudo, nome, tipo = exportacao.exportar_movimentacoes(sessao, formato, usuario, status=status_, de=de, ate=ate, origem_id=origem_id, destino_id=destino_id)
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
