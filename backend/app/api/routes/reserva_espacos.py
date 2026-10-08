# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da Reserva de Espaços (/api/reserva-espacos): agenda, reservas, fila do fiscal, espaços e painel.
"""Rotas `/api/reserva-espacos`.

Recurso ACL `reserva-espacos` (aberto a todo usuário autenticado enquanto não houver regras). Dentro dele há dois papéis: o **solicitante**
(vê a agenda, solicita, altera e cancela o que criou) e o **fiscal** (tabela de fiscais ou SuperRoot): analisa a fila, cria reservas
predefinidas, cadastra espaços, vê todas as reservas, o painel e a configuração.
"""

from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_acl
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import hoje_sao_paulo, obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.reserva_espacos import STATUS_AGUARDANDO, STATUS_DEFERIDA, EspacoReservavel, ReservaEspaco
from app.models.usuario import Usuario
from app.schemas.reserva_espacos import (
    Analise, Cancelamento, ConfiguracaoLeitura, ContextoReserva, EdicaoReserva, EspacoLeitura, EventoLeitura, Fiscal, GravacaoConfiguracao, GravacaoEspaco,
    GravacaoReserva, ListaReservas, PainelReservas, ReservaDetalhe, ReservaLeitura, ResultadoSolicitacao, StatusReserva,
)
from app.services import servico_reserva_espacos as servico
from app.services.servico_reserva_espacos import DadosReserva, ErroReserva

RECURSO = "reserva-espacos"
roteador = APIRouter(prefix="/reserva-espacos", tags=["Reserva de Espaços"], responses=VALIDACAO)
ver = exigir_acl(RECURSO, NivelAcl.LEITURA)
SEM_FISCAL = {status.HTTP_403_FORBIDDEN: {"description": "Operação exclusiva dos fiscais (`acesso_negado`) ou sem acesso ao recurso (`acl_negado`)."}}
RESERVA_NAO_ENCONTRADA = resposta_nao_encontrado("Reserva")


@contextmanager
def _traduzir(sessao: Session):
    """Erros do serviço viram a resposta padrão `{"detalhe", "codigo"}`."""
    try:
        yield
    except ErroReserva as erro:
        sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _contagem_serie(sessao: Session, r: ReservaEspaco) -> int:
    return len(servico.da_serie(sessao, r)) if r.serie_id else 1


def _reserva(sessao: Session, usuario: Usuario, r: ReservaEspaco, fiscal: bool, serie: int | None = None) -> ReservaLeitura:
    dono = usuario.id in (r.solicitante_id, r.responsavel_id)
    return ReservaLeitura(
        id=r.id, espaco_id=r.espaco_id, espaco_nome=r.espaco.nome, espaco_cor=r.espaco.cor, data=r.data, hora_inicio=r.hora_inicio, hora_fim=r.hora_fim,
        titulo=r.titulo, responsavel_id=r.responsavel_id, responsavel_nome=r.responsavel_nome, solicitante_id=r.solicitante_id,
        solicitante_nome=r.solicitante_nome, observacoes=r.observacoes if (fiscal or dono) else "", participantes=r.participantes, status=r.status,
        fiscal_nome=r.fiscal_nome, justificativa=r.justificativa if (fiscal or dono) else "", serie_id=str(r.serie_id) if r.serie_id else None,
        ocorrencias_serie=serie if serie is not None else _contagem_serie(sessao, r),
        pode_editar=r.status == STATUS_AGUARDANDO and (fiscal or r.solicitante_id == usuario.id),
        pode_cancelar=r.status in (STATUS_AGUARDANDO, STATUS_DEFERIDA) and (fiscal or dono) and r.data >= hoje_sao_paulo(),
        pode_analisar=fiscal and r.status == STATUS_AGUARDANDO, criado_em=r.criado_em,
    )


def _espaco(e: EspacoReservavel) -> EspacoLeitura:
    return EspacoLeitura(id=e.id, nome=e.nome, localizacao=e.localizacao, cor=e.cor, capacidade=e.capacidade, equipamentos=e.equipamentos, descricao=e.descricao, ativo=e.ativo)


def _dados(corpo, **extras) -> DadosReserva:
    return DadosReserva(**{**corpo.model_dump(), **extras})


def _lista(sessao: Session, usuario: Usuario, reservas: list[ReservaEspaco]) -> list[ReservaLeitura]:
    fiscal = servico.eh_fiscal(sessao, usuario)
    contagem: dict = {}
    for r in reservas:
        if r.serie_id and r.serie_id not in contagem:
            contagem[r.serie_id] = len(servico.da_serie(sessao, r))
    return [_reserva(sessao, usuario, r, fiscal, contagem.get(r.serie_id, 1)) for r in reservas]


@roteador.get("/contexto", response_model=ContextoReserva, summary="Papel do usuário e espaços cadastrados",
              description="Informa se o usuário é fiscal e lista os espaços (os inativos só aparecem para o fiscal).")
def contexto(usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ContextoReserva:
    fiscal = servico.eh_fiscal(sessao, usuario)
    consulta = select(EspacoReservavel).order_by(EspacoReservavel.nome)
    if not fiscal:
        consulta = consulta.where(EspacoReservavel.ativo.is_(True))
    return ContextoReserva(eh_fiscal=fiscal, espacos=[_espaco(e) for e in sessao.scalars(consulta)])


@roteador.get("/agenda", response_model=list[ReservaLeitura], summary="Agenda do período",
              description="Reservas deferidas entre `inicio` e `fim` (até 62 dias); o fiscal e o dono veem também as aguardando aprovação.", responses=INVALIDO)
def agenda(inicio: date, fim: date, espaco_id: int | None = None, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[ReservaLeitura]:
    if fim < inicio or (fim - inicio).days > 62:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Informe um período válido de até 62 dias.", "invalido")
    return _lista(sessao, usuario, servico.agenda(sessao, usuario, inicio, fim, espaco_id))


@roteador.get("/disponibilidade", response_model=list[EspacoLeitura], summary="Espaços livres em uma data e horário",
              description="Espaços ativos sem reserva deferida na data e no horário informados.")
def disponibilidade(data: date, hora_inicio: str, hora_fim: str, _: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[EspacoLeitura]:
    from datetime import time

    try:
        ini, fim = time.fromisoformat(hora_inicio), time.fromisoformat(hora_fim)
    except ValueError:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Horário inválido (use HH:MM).", "invalido") from None
    if fim <= ini:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "O horário final deve ser posterior ao inicial.", "invalido")
    return [_espaco(e) for e in servico.disponiveis(sessao, data, ini, fim)]


@roteador.get("/minhas", response_model=list[ReservaLeitura], summary="Minhas reservas", description="Reservas em que o usuário é solicitante ou responsável, da mais recente para a mais antiga.")
def minhas(status_: StatusReserva | None = Query(None, alias="status"), usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[ReservaLeitura]:
    return _lista(sessao, usuario, servico.minhas(sessao, usuario, status_))


@roteador.get("/reservas", response_model=ListaReservas, summary="Todas as reservas (fiscal)", description="Lista paginada com filtros por status, espaço, período e texto.", responses=SEM_FISCAL)
def listar(status_: StatusReserva | None = Query(None, alias="status"), espaco_id: int | None = None, inicio: date | None = None, fim: date | None = None,
           busca: str = "", pagina: int = Query(1, ge=1), tamanho: int = Query(50, ge=1, le=200),
           usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ListaReservas:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    itens, total = servico.listar(sessao, status_, espaco_id, inicio, fim, busca, pagina, tamanho)
    return ListaReservas(total=total, itens=_lista(sessao, usuario, itens))


@roteador.get("/exportar", summary="Exportar reservas em planilha (fiscal)", description="Planilha XLSX com as reservas filtradas (sem paginação).", responses=SEM_FISCAL,
              response_class=Response)
def exportar(status_: StatusReserva | None = Query(None, alias="status"), espaco_id: int | None = None, inicio: date | None = None, fim: date | None = None,
             busca: str = "", usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    itens, _ = servico.listar(sessao, status_, espaco_id, inicio, fim, busca, 1, 100000)
    return Response(servico.exportar_xlsx(itens), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="reservas-espacos.xlsx"'})


@roteador.get("/fila", response_model=list[ReservaLeitura], summary="Fila do fiscal", description="Solicitações aguardando análise, da data mais próxima para a mais distante.", responses=SEM_FISCAL)
def fila(usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[ReservaLeitura]:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    return _lista(sessao, usuario, servico.fila(sessao))


@roteador.get("/reservas/{reserva_id}", response_model=ReservaDetalhe, summary="Detalhe da reserva", description="Dados, linha do tempo e demais ocorrências da série. Só o fiscal, o solicitante e o responsável acessam.",
              responses={**RESERVA_NAO_ENCONTRADA, **SEM_FISCAL})
def detalhe(reserva_id: int, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ReservaDetalhe:
    with _traduzir(sessao):
        r = servico.reserva_ou_erro(sessao, reserva_id)
        if not servico.pode_ver(sessao, usuario, r):
            raise ErroReserva("Você não tem acesso a esta reserva.", 403, "acesso_negado")
    fiscal = servico.eh_fiscal(sessao, usuario)
    serie = servico.da_serie(sessao, r) if r.serie_id else [r]
    base = _reserva(sessao, usuario, r, fiscal, len(serie))
    return ReservaDetalhe(**base.model_dump(), eventos=[EventoLeitura(id=e.id, tipo=e.tipo, usuario_nome=e.usuario_nome, detalhes=e.detalhes, criado_em=e.criado_em) for e in r.eventos],
                          serie=[_reserva(sessao, usuario, o, fiscal, len(serie)) for o in serie if o.id != r.id])


@roteador.post("/reservas", response_model=ResultadoSolicitacao, status_code=status.HTTP_201_CREATED, summary="Solicitar reserva",
               description="Cria a solicitação (ou a série, com `recorrencia`); fica aguardando a análise dos fiscais. Conflito com reserva deferida → 409.", responses={**INVALIDO, **CONFLITO})
def solicitar(corpo: GravacaoReserva, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ResultadoSolicitacao:
    with _traduzir(sessao):
        resultado = servico.solicitar(sessao, usuario, _dados(corpo, responsavel_id=None, responsavel_nome=""))
    sessao.commit()
    return ResultadoSolicitacao(reservas=_lista(sessao, usuario, resultado.reservas), avisos=resultado.avisos)


@roteador.post("/reservas/predefinida", response_model=ResultadoSolicitacao, status_code=status.HTTP_201_CREATED, summary="Criar reserva predefinida (fiscal)",
               description="O fiscal registra a reserva já deferida, em nome do responsável (usuário ou nome digitado).", responses={**INVALIDO, **CONFLITO, **SEM_FISCAL})
def predefinida(corpo: GravacaoReserva, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ResultadoSolicitacao:
    with _traduzir(sessao):
        resultado = servico.solicitar(sessao, usuario, _dados(corpo), predefinida=True)
    sessao.commit()
    return ResultadoSolicitacao(reservas=_lista(sessao, usuario, resultado.reservas), avisos=resultado.avisos)


@roteador.put("/reservas/{reserva_id}", response_model=ReservaLeitura, summary="Alterar reserva", description="Só enquanto aguarda aprovação; o solicitante altera a própria e o fiscal qualquer uma.",
              responses={**RESERVA_NAO_ENCONTRADA, **INVALIDO, **CONFLITO, **SEM_FISCAL})
def editar(reserva_id: int, corpo: EdicaoReserva, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ReservaLeitura:
    with _traduzir(sessao):
        r = servico.reserva_ou_erro(sessao, reserva_id)
        servico.editar(sessao, usuario, r, DadosReserva(**corpo.model_dump()))
    sessao.commit()
    return _reserva(sessao, usuario, r, servico.eh_fiscal(sessao, usuario))


@roteador.post("/reservas/{reserva_id}/analise", response_model=list[ReservaLeitura], summary="Deferir ou indeferir (fiscal)",
               description="Aplica a decisão à série inteira pendente. Indeferir exige justificativa; deferir confere o conflito com reservas deferidas (409).",
               responses={**RESERVA_NAO_ENCONTRADA, **INVALIDO, **CONFLITO, **SEM_FISCAL})
def analisar(reserva_id: int, corpo: Analise, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[ReservaLeitura]:
    with _traduzir(sessao):
        r = servico.reserva_ou_erro(sessao, reserva_id)
        alvo = servico.analisar(sessao, usuario, r, corpo.decisao == "deferir", corpo.justificativa)
    sessao.commit()
    return _lista(sessao, usuario, alvo)


@roteador.post("/reservas/{reserva_id}/cancelamento", response_model=list[ReservaLeitura], summary="Cancelar reserva",
               description="Cancela uma ocorrência, a série ou um período, com motivo obrigatório. O solicitante cancela as próprias; o fiscal, qualquer uma.",
               responses={**RESERVA_NAO_ENCONTRADA, **INVALIDO, **CONFLITO, **SEM_FISCAL})
def cancelar(reserva_id: int, corpo: Cancelamento, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[ReservaLeitura]:
    with _traduzir(sessao):
        r = servico.reserva_ou_erro(sessao, reserva_id)
        alvo = servico.cancelar(sessao, usuario, r, corpo.escopo, corpo.motivo, corpo.de, corpo.ate)
    sessao.commit()
    return _lista(sessao, usuario, alvo)


@roteador.get("/usuarios", response_model=list[Fiscal], summary="Buscar usuários (fiscal)", description="Até 20 usuários ativos por nome ou login, para escolher o responsável de uma reserva predefinida.", responses=SEM_FISCAL)
def usuarios(busca: str = Query("", max_length=100), usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> list[Fiscal]:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    consulta = select(Usuario).where(Usuario.ativo.is_(True))
    if busca.strip():
        termo = f"%{busca.strip().lower()}%"
        consulta = consulta.where((Usuario.login.ilike(termo)) | (Usuario.nome_completo.ilike(termo)))
    return [Fiscal(id=u.id, nome=u.nome_completo or u.login, login=u.login) for u in sessao.scalars(consulta.order_by(Usuario.nome_completo).limit(20))]


# --- Espaços ------------------------------------------------------------------------------------------------------------------------

@roteador.post("/espacos", response_model=EspacoLeitura, status_code=status.HTTP_201_CREATED, summary="Cadastrar espaço (fiscal)", responses={**CONFLITO, **SEM_FISCAL})
def criar_espaco(corpo: GravacaoEspaco, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> EspacoLeitura:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
        espaco = servico.salvar_espaco(sessao, usuario, None, corpo.model_dump())
    sessao.commit()
    return _espaco(espaco)


@roteador.put("/espacos/{espaco_id}", response_model=EspacoLeitura, summary="Alterar espaço (fiscal)", responses={**CONFLITO, **SEM_FISCAL, **resposta_nao_encontrado("Espaço")})
def alterar_espaco(espaco_id: int, corpo: GravacaoEspaco, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> EspacoLeitura:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
        espaco = servico.salvar_espaco(sessao, usuario, servico.espaco_ou_erro(sessao, espaco_id), corpo.model_dump())
    sessao.commit()
    return _espaco(espaco)


@roteador.delete("/espacos/{espaco_id}", summary="Excluir espaço (fiscal)", description="Exclui o espaço sem reservas; se já teve reservas, apenas o inativa. Devolve `{\"resultado\": \"excluido\" | \"inativado\"}`.",
                 responses={**SEM_FISCAL, **resposta_nao_encontrado("Espaço")})
def excluir_espaco(espaco_id: int, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> dict[str, str]:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
        resultado = servico.excluir_espaco(sessao, usuario, servico.espaco_ou_erro(sessao, espaco_id))
    sessao.commit()
    return {"resultado": resultado}


# --- Painel e configuração ----------------------------------------------------------------------------------------------------------

@roteador.get("/painel", response_model=PainelReservas, summary="Painel do mês (fiscal)", description="Indicadores do mês, deferidas por mês do ano, ocupação por espaço e ranking de pessoas.", responses=SEM_FISCAL)
def painel(ano: int | None = Query(None, ge=2000, le=2200), mes: int | None = Query(None, ge=1, le=12), usuario: Usuario = Depends(ver),
           sessao: Session = Depends(obter_sessao)) -> PainelReservas:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    hoje = hoje_sao_paulo()
    return PainelReservas(**servico.painel(sessao, ano or hoje.year, mes or hoje.month))


def _configuracao(sessao: Session) -> ConfiguracaoLeitura:
    cfg = servico.configuracao(sessao)
    fiscais = sessao.scalars(select(Usuario).where(Usuario.id.in_(servico.ids_fiscais(sessao))).order_by(Usuario.nome_completo))
    return ConfiguracaoLeitura(hora_abertura=cfg.hora_abertura, hora_fechamento=cfg.hora_fechamento, antecedencia_minima_horas=cfg.antecedencia_minima_horas,
                               duracao_maxima_horas=cfg.duracao_maxima_horas, fiscais=[Fiscal(id=u.id, nome=u.nome_completo or u.login, login=u.login) for u in fiscais])


@roteador.get("/configuracao", response_model=ConfiguracaoLeitura, summary="Configuração (fiscal)", description="Horário de funcionamento, antecedência mínima, duração máxima e fiscais.", responses=SEM_FISCAL)
def ler_configuracao(usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ConfiguracaoLeitura:
    with _traduzir(sessao):
        servico.exigir_fiscal(sessao, usuario)
    return _configuracao(sessao)


@roteador.put("/configuracao", response_model=ConfiguracaoLeitura, summary="Gravar configuração (SuperRoot)", description="Somente o SuperRoot altera as regras e a lista de fiscais.",
              responses={**INVALIDO, status.HTTP_403_FORBIDDEN: {"description": "Exige SuperRoot (`acesso_negado`)."}})
def gravar_configuracao(corpo: GravacaoConfiguracao, usuario: Usuario = Depends(ver), sessao: Session = Depends(obter_sessao)) -> ConfiguracaoLeitura:
    if not usuario.superusuario:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Somente o SuperRoot altera a configuração.", "acesso_negado")
    if corpo.hora_fechamento <= corpo.hora_abertura:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "O horário de fechamento deve ser posterior ao de abertura.", "invalido")
    with _traduzir(sessao):
        cfg = servico.configuracao(sessao)
        cfg.hora_abertura, cfg.hora_fechamento = corpo.hora_abertura, corpo.hora_fechamento
        cfg.antecedencia_minima_horas, cfg.duracao_maxima_horas = corpo.antecedencia_minima_horas, corpo.duracao_maxima_horas
        servico.definir_fiscais(sessao, usuario, corpo.fiscais_ids)
    sessao.commit()
    return _configuracao(sessao)
