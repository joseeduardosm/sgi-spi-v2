# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a nota de satisfação, as respostas prontas, os motivos de pendência e os relatórios dos Chamados.
"""Rotas do marco 6 dos Chamados (`/api/chamados/...`). Registradas antes do roteador principal (os caminhos fixos não podem cair em `/{numero}`).
Detalhes em `docs/endpoints/chamados.md` (seção "Marco 6")."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.respostas import INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.api.routes.chamados import ALTERADO, NAO_ENCONTRADO, SEM_ACESSO, _acao, _traduzir, administrador, papeis_do_usuario
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.chamados import MotivoPendenciaChamados, RespostaProntaChamados
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.chamados import (
    Avaliacao, ChamadoDetalhe, GravacaoMotivo, GravacaoRespostaPronta, LinhaRelatorio, MotivoLeitura, RelatorioChamados, RespostaProntaLeitura, ResumoRelatorio,
    PessoaEquipeRelatorio, SemanaRelatorio, SetorOpcao,
)
from app.services.chamados import acesso, exportacao, qualidade
from app.services.chamados.acesso import Papeis

roteador = APIRouter(prefix="/chamados", tags=["Chamados"], responses=VALIDACAO)


def _quem_atende(ctx: tuple[Usuario, Papeis]) -> tuple[Usuario, Papeis]:
    if not ctx[1].atender:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Só quem atende chamados.", "acesso_negado")
    return ctx


# ---------------------------------------------------------------------------------------------
# Satisfação
# ---------------------------------------------------------------------------------------------

@roteador.post("/{numero}/satisfacao", response_model=ChamadoDetalhe, summary="Dar a nota do atendimento",
               description="O solicitante (ou alguém do setor solicitante) dá a nota de 1 (Péssimo) a 5 (Ótimo), com comentário opcional, depois que o chamado "
               "é resolvido. Pode mudar a nota enquanto o chamado estiver resolvido. Nota 1 ou 2: a tela oferece o \"Não resolveu\" (se ainda no prazo).",
               responses={**INVALIDO, **NAO_ENCONTRADO, **SEM_ACESSO, **ALTERADO})
def avaliar(numero: int, corpo: Avaliacao, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        qualidade.avaliar(sessao, usuario, p, numero, corpo.nota, corpo.comentario)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


# ---------------------------------------------------------------------------------------------
# Respostas prontas e motivos (uso por quem atende)
# ---------------------------------------------------------------------------------------------

def _resposta(sessao: Session, r: RespostaProntaChamados) -> RespostaProntaLeitura:
    setor = sessao.get(Setor, r.setor_id) if r.setor_id else None
    return RespostaProntaLeitura(id=r.id, titulo=r.titulo, texto=r.texto, setor_id=r.setor_id, setor_nome=setor.nome if setor else "", ativo=r.ativo, ordem=r.ordem)


def _motivo(m: MotivoPendenciaChamados) -> MotivoLeitura:
    return MotivoLeitura(id=m.id, nome=m.nome, ativo=m.ativo, ordem=m.ordem)


@roteador.get("/respostas-prontas", response_model=list[RespostaProntaLeitura], summary="Respostas prontas", responses=SEM_ACESSO,
              description="As ativas que valem para quem atende: as sem setor e as dos setores que a pessoa atende (quem administra vê todas).")
def respostas_prontas(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[RespostaProntaLeitura]:
    usuario, p = _quem_atende(ctx)
    a = acesso.alcance(sessao, usuario, p)
    setores = None if a.todos else set(a.setores_atendidos) | set(a.setores_membro)
    return [_resposta(sessao, r) for r in qualidade.listar_respostas(sessao, todas=False, setores=setores)]


@roteador.get("/motivos-pendencia", response_model=list[MotivoLeitura], summary="Motivos de pendência", responses=SEM_ACESSO,
              description="Motivos ativos para escolher ao pôr um chamado em \"Pendente\" (o texto vai no campo `motivo`).")
def motivos(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[MotivoLeitura]:
    _quem_atende(ctx)
    return [_motivo(m) for m in qualidade.listar_motivos(sessao, todos=False)]


# ---------------------------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------------------------

@roteador.get("/relatorios", response_model=RelatorioChamados, summary="Relatórios do atendimento",
              description="Números do período (padrão: últimos 30 dias; até 1 ano): abertos, resolvidos, prazos cumpridos, mediana de solução, reabertos, "
              "satisfação, semanas (com a fila no fim de cada uma), categorias, desempenho da equipe e, para quem escolhe setor, setores e prioridades. "
              "Inclui o histórico importado do GLPI. Escolhe setor (`setor_id`) só quem tem Controle total ou é líder de um setor com setores abaixo "
              "(`pode_escolher_setor`, `setores_opcoes`); os demais veem só o próprio setor (`setor_id` de outro: 403).",
              responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Setor")})
def relatorios(inicio: date | None = Query(None), fim: date | None = Query(None), setor_id: int | None = Query(None),
               ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> RelatorioChamados:
    usuario, p = ctx
    with _traduzir(sessao):
        v = qualidade.visao(sessao, usuario, p)
        setores, area = qualidade.escopo(sessao, usuario, p, setor_id)
        r = qualidade.relatorio(sessao, setores, area, inicio, fim)
    opcoes = []
    if v.ampla:
        consulta = select(Setor).where(Setor.ativo.is_(True)).order_by(Setor.nome)
        if v.opcoes is not None:
            consulta = consulta.where(Setor.id.in_(v.opcoes or {-1}))
        opcoes = [SetorOpcao(id=x.id, nome=x.nome) for x in sessao.scalars(consulta)]
    return RelatorioChamados(area=r.area, inicio=r.inicio, fim=r.fim, resumo=ResumoRelatorio(**r.resumo),
                             semanas=[SemanaRelatorio(**s) for s in r.semanas], por_categoria=[LinhaRelatorio(**x) for x in r.por_categoria],
                             # Quem não escolhe setor não vê a quebra por setor nem as prioridades
                             por_setor=[LinhaRelatorio(**x) for x in r.por_setor] if v.ampla else [],
                             por_prioridade=r.por_prioridade if v.ampla else {}, notas=r.notas,
                             equipe=[PessoaEquipeRelatorio(**x) for x in r.equipe], pode_escolher_setor=v.ampla, setores_opcoes=opcoes)


@roteador.get("/relatorios/exportar", summary="Exportar chamados do período",
              description="Arquivo com os chamados **abertos** entre `inicio` e `fim` (até 1 ano), no escopo do relatório (`setor_id` e os de baixo; sem ele, "
              "os setores que a pessoa atende): Nº, título, descrição, solicitante, setor responsável, responsável e status; com `com_solucao`, mais a "
              "solução vigente. `formato`: `pdf` (A4 paisagem, identidade do sistema) ou `xlsx`. Título: \"Chamados {setor} - {início} a {fim}\".",
              response_class=Response,
              responses={200: {"description": "O arquivo (PDF ou XLSX).", "content": {"application/pdf": {}, exportacao.XLSX: {}}},
                         **INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Setor")})
def exportar_relatorio(inicio: date = Query(..., description="Primeiro dia (abertura)."), fim: date = Query(..., description="Último dia (abertura)."),
                       setor_id: int | None = Query(None), com_solucao: bool = Query(False, description="Inclui a coluna da solução."),
                       formato: str = Query("pdf", pattern="^(pdf|xlsx)$"), ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                       sessao: Session = Depends(obter_sessao)) -> Response:
    usuario, p = ctx
    with _traduzir(sessao):
        setores, area = qualidade.escopo(sessao, usuario, p, setor_id)
        arquivo = exportacao.exportar(sessao, setores, area, inicio, fim, com_solucao, formato, usuario)
    return Response(arquivo.conteudo, media_type=arquivo.tipo, headers={"Content-Disposition": f'attachment; filename="{arquivo.nome}"'})


# ---------------------------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------------------------

@roteador.get("/parametros/respostas-prontas", response_model=list[RespostaProntaLeitura], summary="Respostas prontas (Parâmetros)", responses=SEM_ACESSO)
def parametros_respostas(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[RespostaProntaLeitura]:
    return [_resposta(sessao, r) for r in qualidade.listar_respostas(sessao)]


@roteador.post("/parametros/respostas-prontas", response_model=RespostaProntaLeitura, status_code=status.HTTP_201_CREATED, summary="Criar resposta pronta",
               responses={**INVALIDO, **SEM_ACESSO})
def criar_resposta(corpo: GravacaoRespostaPronta, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> RespostaProntaLeitura:
    with _traduzir(sessao):
        r = qualidade.salvar_resposta(sessao, None, corpo.titulo, corpo.texto, corpo.setor_id, corpo.ativo, corpo.ordem)
        sessao.commit()
    return _resposta(sessao, r)


@roteador.put("/parametros/respostas-prontas/{resposta_id}", response_model=RespostaProntaLeitura, summary="Alterar resposta pronta",
              responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Resposta pronta")})
def alterar_resposta(resposta_id: uuid.UUID, corpo: GravacaoRespostaPronta, _: Usuario = Depends(administrador),
                     sessao: Session = Depends(obter_sessao)) -> RespostaProntaLeitura:
    with _traduzir(sessao):
        r = qualidade.salvar_resposta(sessao, resposta_id, corpo.titulo, corpo.texto, corpo.setor_id, corpo.ativo, corpo.ordem)
        sessao.commit()
    return _resposta(sessao, r)


@roteador.delete("/parametros/respostas-prontas/{resposta_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir resposta pronta",
                 responses={**SEM_ACESSO, **resposta_nao_encontrado("Resposta pronta")})
def excluir_resposta(resposta_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        qualidade.excluir_resposta(sessao, resposta_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros/motivos-pendencia", response_model=list[MotivoLeitura], summary="Motivos de pendência (Parâmetros)", responses=SEM_ACESSO)
def parametros_motivos(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[MotivoLeitura]:
    return [_motivo(m) for m in qualidade.listar_motivos(sessao)]


@roteador.post("/parametros/motivos-pendencia", response_model=MotivoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar motivo de pendência",
               responses={**INVALIDO, **SEM_ACESSO})
def criar_motivo(corpo: GravacaoMotivo, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> MotivoLeitura:
    with _traduzir(sessao):
        m = qualidade.salvar_motivo(sessao, None, corpo.nome, corpo.ativo, corpo.ordem)
        sessao.commit()
    return _motivo(m)


@roteador.put("/parametros/motivos-pendencia/{motivo_id}", response_model=MotivoLeitura, summary="Alterar motivo de pendência",
              responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Motivo")})
def alterar_motivo(motivo_id: uuid.UUID, corpo: GravacaoMotivo, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> MotivoLeitura:
    with _traduzir(sessao):
        m = qualidade.salvar_motivo(sessao, motivo_id, corpo.nome, corpo.ativo, corpo.ordem)
        sessao.commit()
    return _motivo(m)


@roteador.delete("/parametros/motivos-pendencia/{motivo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir motivo de pendência",
                 description="Os chamados que já foram pendentes por este motivo guardam o texto.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Motivo")})
def excluir_motivo(motivo_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        qualidade.excluir_motivo(sessao, motivo_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
