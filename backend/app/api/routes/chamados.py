# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do módulo Chamados (/api/chamados): abertura, fila, detalhe, atendimento e Parâmetros.
"""Rotas `/api/chamados` (módulo Chamados, que substitui a Assistência do GLPI).

Recurso ACL `chamados`: **Leitura** abre e acompanha os próprios chamados; **Modificação** atende (fila dos seus setores, assumir,
responder, solucionar); **Controle total** vê todos e cuida dos Parâmetros. **Fechado até a virada:** sem regras nem perfis na ACL,
só o SuperRoot entra. Detalhes em `docs/endpoints/chamados.md`.

As rotas fixas (`/contexto`, `/catalogo`, `/meus`, `/parametros/...`) vêm antes de `/{numero}` para não serem lidas como número.
"""

import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO, resposta_nao_encontrado
from app.core.banco import agora_utc, obter_sessao
from app.core.erros import ErroApi
from app.models.chamados import STATUS_PENDENTE, STATUS_SOLUCIONADO, CategoriaChamados, Chamado, SlaChamados, SubstatusChamados
from app.models.patrimonio import Localizacao
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.chamados import (
    GravacaoRecorrente, GravacaoSetorAtendimento, GravacaoStatus, GravacaoSubstatus, ParametrosGerais, RecorrenteLeitura, SaudeChamados, SetorAtendimentoLeitura,
    StatusLeitura, SubstatusLeitura, TarefaSaude,
    AberturaChamado, Alteracao, AprovacaoPendente, CampoAdicional, CampoLeitura, ChamadoRelacionavel, CondicaoCampo, ContextoAbertura, EmCopia, GravacaoCampo,
    InclusaoEmCopia, LocalResumo, MarcacaoTarefa, Motivo, NovaTarefa, PedidoAprovacao, PessoaResumo, RespostaAprovacao, RespostaCampo, TarefaLeitura,
    ValidacaoLeitura, AcoesChamado, AnexoLeitura, Assumir, CategoriaCatalogo, CategoriaLeitura, ChamadoDetalhe, ChamadoResumo, ContextoChamados,
    Direcao, ExpedienteLeitura, FaixaExpediente, FiltroFila, FiltroMeus, GravacaoCategoria, GravacaoExpediente, GravacaoSla, ItemLinhaTempo, ListaChamados,
    NovaResposta, NovaSolucao, OrdemChamados, PapeisChamados, PrazoSla, SetorResumo, SlaLeitura,
    CategoriaItilLeitura, CategoriaItilResumo, Classificacao, GravacaoCategoriaItil,
)
from app.schemas.comum import RespostaErro
from app.services import servico_anexos
from app.services.chamados import acesso, acoes, campos as campos_adicionais, configuracao, motor_sla, parametros, qualidade, servico, tarefas_agendadas
from app.services.patrimonio import servico_localizacoes
from app.services.chamados.acesso import Alcance, Papeis
from app.services.chamados.campos import DadosCampo
from app.services.chamados.parametros import DadosCategoria, DadosFaixa, ErroParametro
from app.services.chamados.servico import Arquivo, DadosAbertura, ErroChamado

roteador = APIRouter(prefix="/chamados", tags=["Chamados"], responses=VALIDACAO)

SEM_ACESSO = {status.HTTP_403_FORBIDDEN: {"model": RespostaErro, "description": "Sem o papel necessário no recurso `chamados` (`acesso_negado`)."}}
NAO_ENCONTRADO = resposta_nao_encontrado("Chamado")
ALTERADO = {status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Chamado resolvido ou importado, somente leitura (`chamado_encerrado`), ou alterado por outra pessoa (`chamado_alterado`)."}}
ERROS_ABERTURA = {**INVALIDO, **SEM_ACESSO, status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Setor responsável da categoria inativo (`categoria_sem_setor`)."}}
TITULO_RESTRITO = "Chamado restrito"


def papeis_do_usuario(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> tuple[Usuario, Papeis]:
    """Usuário logado e os papéis dele no módulo; sem nenhum papel, 403 (o módulo está fechado até a virada)."""
    p = acesso.papeis(sessao, usuario)
    if not p.algum:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Você não tem acesso ao módulo Chamados.", "acl_negado", recurso=acesso.RECURSO_ACL)
    return usuario, p


def administrador(contexto: tuple[Usuario, Papeis] = Depends(papeis_do_usuario)) -> Usuario:
    usuario, p = contexto
    if not p.administrar:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Só a administração dos Chamados (Controle total) mexe nos Parâmetros.", "acesso_negado")
    return usuario


@contextmanager
def _traduzir(sessao: Session):
    """Erros dos serviços viram a resposta padrão `{"detalhe", "codigo"}` (e desfazem o que ficou pela metade)."""
    try:
        yield
    except (ErroChamado, ErroParametro) as erro:
        sessao.rollback()
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro
    except motor_sla.ErroExpediente as erro:
        sessao.rollback()
        raise ErroApi(status.HTTP_409_CONFLICT, str(erro), "expediente_vazio") from erro


def _json(modelo: type[BaseModel], dados: str) -> BaseModel:
    """Campo `dados` (JSON) de um envio multipart, validado pelo schema."""
    try:
        return modelo.model_validate_json(dados)
    except ValidationError as erro:
        mensagem = erro.errors()[0].get("msg", "Dados inválidos.").removeprefix("Value error, ")
        raise ErroApi(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem, "validacao") from erro


async def _arquivos(arquivos: list[UploadFile]) -> list[Arquivo]:
    limite = servico_anexos.tamanho_maximo() + 1
    return [Arquivo(a.filename or "anexo", await a.read(limite)) for a in arquivos if a.filename]


# ---------------------------------------------------------------------------------------------
# Montagem das respostas
# ---------------------------------------------------------------------------------------------

class _Montador:
    """Converte chamados em resposta, guardando por requisição os nomes, os feriados e os expedientes já lidos."""

    def __init__(self, sessao: Session, usuario: Usuario, p: Papeis, a: Alcance) -> None:
        self.sessao, self.usuario, self.p, self.a = sessao, usuario, p, a
        self.feriados: set | None = None
        self.nomes: dict[int, str] = {}
        self.apresentacao = configuracao.apresentacao(sessao)
        self.limites = configuracao.geral(sessao)
        self.substatus = {x.id: x for x in configuracao.listar_substatus(sessao)}

    def carregar_nomes(self, ids: set[int | None]) -> None:
        faltam = {i for i in ids if i is not None and i not in self.nomes}
        self.nomes.update(servico.nomes_de_usuarios(self.sessao, faltam))

    def prazo(self, sla_id: uuid.UUID | None, aberto_em: datetime, vence_em: datetime | None, cumprido_em: datetime | None, estourado_em: datetime | None,
              espera: int = 0, pausado: bool = False) -> PrazoSla:
        if vence_em is None:
            return PrazoSla(vence_em=None, cumprido_em=None if pausado else cumprido_em, estourado=False, percentual=None, nivel="sem")
        referencia = cumprido_em or agora_utc()
        estourado = estourado_em is not None or _depois(referencia, vence_em)
        percentual = None
        sla = self.sessao.get(SlaChamados, sla_id) if sla_id else None
        if sla is not None:
            if self.feriados is None:
                self.feriados = parametros.feriados_do_sla(self.sessao)
            faixas = parametros.faixas_do_expediente(sla.expediente)
            total = motor_sla.minutos_uteis_entre(aberto_em, vence_em, faixas, self.feriados)
            usado = max(0, motor_sla.minutos_uteis_entre(aberto_em, referencia, faixas, self.feriados) - espera)
            percentual = 100 if total <= 0 else round(usado * 100 / total)
        cumprido = cumprido_em is not None and not pausado
        nivel = configuracao.nivel_do_prazo(percentual, estourado, cumprido, True, self.limites)
        return PrazoSla(vence_em=vence_em, cumprido_em=cumprido_em if cumprido else None, estourado=estourado, percentual=percentual, pausado=pausado, nivel=nivel)

    def resumo(self, c: Chamado) -> dict:
        self.carregar_nomes({c.responsavel_id, c.solicitante_id})
        sigiloso = parametros.efetiva(c.categoria).sigilosa and not acesso.atende(self.a, self.p, c)
        # Nome e cor do status pelos Parâmetros; o sub-status (se for do status atual) aparece no lugar do nome
        nome_status, cor_status = self.apresentacao[c.status_base]
        sub = self.substatus.get(c.substatus_id) if c.substatus_id else None
        if sub is not None and sub.status_base == c.status_base:
            nome_status, cor_status = f"{nome_status} › {sub.nome}", sub.cor
        else:
            sub = None
        return dict(
            status_nome=nome_status, status_cor=cor_status, substatus_id=sub.id if sub else None,
            id=c.id, numero=c.numero, titulo=TITULO_RESTRITO if sigiloso else c.titulo, tipo=c.tipo, status_base=c.status_base, prioridade=c.prioridade,
            prioridade_origem=c.prioridade_origem, categoria_id=c.categoria_id, categoria_caminho=c.categoria.caminho, setor_id=c.setor_id, setor_nome=c.setor_nome,
            responsavel_id=c.responsavel_id, responsavel_nome=self.nomes.get(c.responsavel_id, ""), solicitante_id=c.solicitante_id,
            solicitante_nome=self.nomes.get(c.solicitante_id, c.solicitante_externo or ""), aberto_em=c.aberto_em, solucionado_em=c.solucionado_em,
            atendimento=self.prazo(c.sla_tto_id, c.aberto_em, c.prazo_tto, c.tomado_em, c.tto_estourado_em),
            # Pendente: o relógio da solução está parado (o percentual congela no instante da pausa)
            solucao=self.prazo(c.sla_ttr_id, c.aberto_em, c.prazo_ttr, c.solucionado_em or (c.espera_desde if c.status_base == STATUS_PENDENTE else None),
                               c.ttr_estourado_em, c.espera_minutos_uteis, pausado=c.status_base == STATUS_PENDENTE),
            importado=c.importado,
        )

    def lista(self, itens: list[Chamado], total: int) -> ListaChamados:
        self.carregar_nomes({i for c in itens for i in (c.responsavel_id, c.solicitante_id)})
        return ListaChamados(total=total, itens=[ChamadoResumo(**self.resumo(c)) for c in itens])

    def detalhe(self, c: Chamado) -> ChamadoDetalhe:
        atende = acesso.atende(self.a, self.p, c)
        self.carregar_nomes({x.autor_id for x in c.acompanhamentos} | {x.autor_id for x in c.solucoes})
        anexos_por_alvo: dict[uuid.UUID | None, list[AnexoLeitura]] = {}
        for v in c.anexos:
            if v.privado and not atende:
                continue
            anexos_por_alvo.setdefault(v.alvo_id, []).append(
                AnexoLeitura(id=v.anexo_id, nome=v.anexo.nome_original, tamanho=v.anexo.tamanho, tipo_conteudo=v.anexo.tipo_conteudo, privado=v.privado)
            )
        itens = [
            ItemLinhaTempo(id=x.id, tipo="acompanhamento", autor_id=x.autor_id, autor_nome=self.nomes.get(x.autor_id, ""), texto=x.texto, privado=x.privado,
                           automatico=x.automatico, criado_em=x.criado_em, anexos=anexos_por_alvo.get(x.id, []))
            for x in c.acompanhamentos if atende or not x.privado
        ] + [
            ItemLinhaTempo(id=s.id, tipo="solucao", autor_id=s.autor_id, autor_nome=self.nomes.get(s.autor_id, ""), texto=s.texto, privado=False,
                           automatico=False, criado_em=s.criado_em, anexos=anexos_por_alvo.get(s.id, []))
            for s in c.solucoes
        ]
        itens.sort(key=lambda i: _utc(i.criado_em))
        aberto = c.status_base != STATUS_SOLUCIONADO and not c.importado
        sigiloso = parametros.efetiva(c.categoria).sigilosa and not atende
        setor_sol = self.sessao.get(Setor, c.setor_solicitante_id) if c.setor_solicitante_id else None
        do_solicitante = self.usuario.id == c.solicitante_id or (c.setor_solicitante_id is not None and c.setor_solicitante_id in self.a.setores_membro)
        reabrir = (c.status_base == STATUS_SOLUCIONADO and not c.importado and do_solicitante and c.reabrir_ate is not None
                   and not _depois(agora_utc(), c.reabrir_ate))
        self.carregar_nomes({t.responsavel_id for t in c.tarefas} | {t.autor_id for t in c.tarefas}
                            | {v.solicitante_id for v in c.validacoes} | {v.respondida_por_id for v in c.validacoes} | {v.alvo_usuario_id for v in c.validacoes}
                            | {x.usuario_id for x in c.atores})
        setores = {s.id: s.nome for s in self.sessao.query(Setor).filter(Setor.id.in_({x.setor_id for x in c.atores} | {v.alvo_setor_id for v in c.validacoes}))}
        local = self.sessao.get(Localizacao, c.localizacao_id) if c.localizacao_id else None
        relacionado = self.sessao.get(Chamado, c.relacionado_id) if c.relacionado_id else None
        return ChamadoDetalhe(
            **self.resumo(c), descricao="" if sigiloso else c.descricao, impedindo_trabalho=c.impedindo_trabalho,
            setor_solicitante_id=c.setor_solicitante_id, setor_solicitante_nome=setor_sol.nome if setor_sol else "", versao=c.versao,
            reabrir_ate=c.reabrir_ate, anexos=anexos_por_alvo.get(None, []), linha_do_tempo=[] if sigiloso else itens,
            acoes=AcoesChamado(
                responder=aberto and not sigiloso, responder_privado=aberto and atende, assumir=aberto and atende and c.responsavel_id is None,
                solucionar=aberto and atende, pendente=aberto and atende and c.status_base != STATUS_PENDENTE,
                retomar=aberto and atende and c.status_base == STATUS_PENDENTE, nao_resolveu=reabrir, alterar=aberto and atende, tarefas=atende,
                pedir_aprovacao=aberto and atende, incluir_em_copia=aberto and (atende or self.usuario.id == c.solicitante_id),
                classificar=atende and not c.importado,
            ),
            # A categoria ITIL é técnica: só quem atende vê
            categoria_itil_id=c.categoria_itil_id if atende else None, categoria_itil=c.categoria_itil.caminho if atende and c.categoria_itil else "",
            local=LocalResumo(id=local.id, rotulo=servico_localizacoes.rotulo_curto(local)) if local else None,
            relacionado=_relacionavel(relacionado) if relacionado and (self.a.todos or acesso.ve(self.a, relacionado)) else None,
            campos=[] if sigiloso else [
                # LGPD: o dado pessoal vem mascarado para todos; quem atende revela na rota auditada
                RespostaCampo(campo_id=v.campo_id, rotulo=v.campo.rotulo, dado_pessoal=v.campo.dado_pessoal, mascarado=v.campo.dado_pessoal,
                              pode_revelar=v.campo.dado_pessoal and atende, valor=campos_adicionais.mascarar(v.valor) if v.campo.dado_pessoal else v.valor)
                for v in campos_adicionais.respostas_do_chamado(c)
            ],
            em_copia=[EmCopia(id=x.id, usuario_id=x.usuario_id, setor_id=x.setor_id, nome=self.nomes.get(x.usuario_id, "") if x.usuario_id else setores.get(x.setor_id, ""))
                      for x in c.atores],
            tarefas=[TarefaLeitura(id=t.id, texto=t.texto, estado=t.estado, privada=t.privada, responsavel_id=t.responsavel_id,
                                   responsavel_nome=self.nomes.get(t.responsavel_id, ""), autor_nome=self.nomes.get(t.autor_id, ""), criado_em=t.criado_em,
                                   feita_em=t.feita_em) for t in c.tarefas if atende or not t.privada],
            validacoes=[ValidacaoLeitura(id=v.id, status=v.status, pedido=v.pedido, resposta=v.resposta, criado_em=v.criado_em, respondida_em=v.respondida_em,
                                         alvo_nome=self.nomes.get(v.alvo_usuario_id, "") if v.alvo_usuario_id else setores.get(v.alvo_setor_id, ""),
                                         solicitante_nome=self.nomes.get(v.solicitante_id, ""), respondida_por_nome=self.nomes.get(v.respondida_por_id, ""),
                                         posso_responder=v.status == "aguardando" and acoes._pode_responder(self.sessao, self.usuario, v))
                        for v in c.validacoes],
            reaberturas=c.reaberturas, pendente_desde=c.espera_desde if c.status_base == STATUS_PENDENTE else None,
            satisfacao=qualidade.leitura(self.sessao, c, self.usuario, self.a),
        )


def _relacionavel(c: Chamado) -> ChamadoRelacionavel:
    return ChamadoRelacionavel(id=c.id, numero=c.numero, titulo=c.titulo, status_base=c.status_base, aberto_em=c.aberto_em)


def _campo(campo) -> CampoAdicional:
    return CampoAdicional(id=campo.id, rotulo=campo.rotulo, ajuda=campo.ajuda, tipo=campo.tipo, obrigatorio=campo.obrigatorio, dado_pessoal=campo.dado_pessoal,
                          opcoes=campo.opcoes, condicao=CondicaoCampo(**campo.condicao) if campo.condicao else None, ordem=campo.ordem)


def _utc(instante: datetime) -> datetime:
    """Data com fuso (o SQLite devolve sem fuso; tudo no banco é UTC)."""
    return instante if instante.tzinfo else instante.replace(tzinfo=UTC)


def _depois(a: datetime, b: datetime) -> bool:
    return _utc(a) > _utc(b)


def _montador(sessao: Session, usuario: Usuario, p: Papeis) -> _Montador:
    return _Montador(sessao, usuario, p, acesso.alcance(sessao, usuario, p))


# ---------------------------------------------------------------------------------------------
# Contexto, catálogo e abertura
# ---------------------------------------------------------------------------------------------

@roteador.get("/contexto", response_model=ContextoChamados, summary="Papéis no módulo e setores do usuário",
              description="O que a pessoa pode fazer (abrir, atender, administrar) e os setores de que é membro (para abrir em nome de um setor). "
              "Responde `200` mesmo sem nenhum papel (tudo `false`, sem setores): é por ela que o menu decide se mostra o módulo, que fica fechado "
              "(só SuperRoot) enquanto a ACL não tiver regras.")
def contexto(usuario: Usuario = Depends(obter_usuario_atual), sessao: Session = Depends(obter_sessao)) -> ContextoChamados:
    p = acesso.papeis(sessao, usuario)
    inicio, aberto = configuracao.inicio_atendimento(sessao), configuracao.atendimento_aberto(sessao)
    if not p.algum:
        return ContextoChamados(papeis=PapeisChamados(abrir=False, atender=False, administrar=False), setores_do_usuario=[],
                                inicio_atendimento=inicio, atendimento_aberto=aberto)
    membro = acesso.setores_do_usuario(sessao, usuario)
    setores = [SetorResumo(id=s.id, nome=s.nome, caminho=caminho) for s, caminho in parametros.setores_ativos(sessao) if s.id in membro]
    return ContextoChamados(papeis=PapeisChamados(abrir=p.abrir, atender=p.atender, administrar=p.administrar), setores_do_usuario=setores,
                            inicio_atendimento=inicio, atendimento_aberto=aberto)


@roteador.get("/catalogo", response_model=list[CategoriaCatalogo], summary="Categorias para abrir chamado",
              description="Categorias ativas, com setor responsável e (para quem só abre) visíveis ao solicitante, em ordem de caminho.", responses=SEM_ACESSO)
def catalogo(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[CategoriaCatalogo]:
    _, p = ctx
    setores = {s.id: s.nome for s, _ in parametros.setores_ativos(sessao)}
    return [
        CategoriaCatalogo(id=c.id, pai_id=c.pai_id, nome=c.nome, caminho=c.caminho, nivel=c.nivel, permite_incidente=c.permite_incidente,
                          permite_requisicao=c.permite_requisicao, perguntar_impedindo=c.perguntar_impedindo,
                          setor_nome=setores.get(parametros.efetiva(c).setor_id, ""), campos=[_campo(x) for x in campos_adicionais.herdados(c)])
        for c in servico.catalogo(sessao, p, ctx[0])
    ]


@roteador.post("", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Abrir chamado", responses=ERROS_ABERTURA,
               description="`multipart/form-data`: `dados` (JSON de `AberturaChamado`) e até 10 `arquivos` (PDF, Office, imagens, TXT/CSV, no limite de tamanho "
               "dos anexos do SGI). O chamado nasce com o setor responsável da categoria (próprio ou herdado), a prioridade da categoria (sobe um nível se "
               "estiver impedindo o trabalho) e os prazos dos SLAs em horas úteis. Os membros do setor responsável e do setor solicitante recebem o aviso "
               "no sino e por e-mail. Imagens coladas no texto viram anexos.")
async def abrir(dados: str = Form(..., description="JSON de `AberturaChamado`."), arquivos: list[UploadFile] = File(default_factory=list),
                ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    corpo = _json(AberturaChamado, dados)
    conteudos = await _arquivos(arquivos)
    with _traduzir(sessao):
        chamado = servico.abrir(sessao, usuario, p, DadosAbertura(**corpo.model_dump(), arquivos=conteudos))
        sessao.commit()
    chamado, _ = servico.obter(sessao, usuario, p, chamado.numero)
    return _montador(sessao, usuario, p).detalhe(chamado)


@roteador.get("/abertura/contexto", response_model=ContextoAbertura, summary="Sala sugerida e chamados relacionáveis",
              description="A sala do solicitante pelo Patrimônio (responsável pela sala, sala com mais bens dele ou a única sala do setor) e os chamados "
              "do próprio solicitante, para escolher o relacionado.", responses=SEM_ACESSO)
def contexto_abertura(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ContextoAbertura:
    usuario, _ = ctx
    sala = acoes.local_sugerido(sessao, usuario)
    return ContextoAbertura(local_sugerido=LocalResumo(id=sala.id, rotulo=servico_localizacoes.rotulo_curto(sala)) if sala else None,
                            relacionaveis=[_relacionavel(c) for c in acoes.relacionaveis(sessao, usuario)])


@roteador.get("/locais", response_model=list[LocalResumo], summary="Buscar sala do Patrimônio",
              description="Salas ativas cujo código, nome ou setor contém `busca` (até `limite`; a abertura pede todas para o campo \"Onde podemos te encontrar?\").",
              responses=SEM_ACESSO)
def locais(busca: str = "", limite: int = Query(20, ge=1, le=2000, description="Quantas salas no máximo."),
           _: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[LocalResumo]:
    return [LocalResumo(id=s.id, rotulo=servico_localizacoes.rotulo_curto(s), codigo=s.codigo, andar=s.andar) for s in acoes.buscar_locais(sessao, busca, limite)]


@roteador.get("/pessoas", response_model=list[PessoaResumo], summary="Buscar pessoas",
              description="Até 20 usuários ativos cujo nome ou login contém `busca` (para em cópia, aprovação e tarefas).", responses=SEM_ACESSO)
def pessoas(busca: str = "", _: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[PessoaResumo]:
    from sqlalchemy import or_, select

    termo = f"%{busca.strip()}%"
    consulta = select(Usuario).where(Usuario.ativo.is_(True), Usuario.conta_integracao.is_(False), or_(Usuario.nome_completo.ilike(termo), Usuario.login.ilike(termo)))
    return [PessoaResumo(id=u.id, nome=u.nome_completo or u.login, login=u.login, cargo=u.cargo or "") for u in sessao.scalars(consulta.order_by(Usuario.nome_completo).limit(20))]


@roteador.get("/setores", response_model=list[SetorResumo], summary="Setores ativos",
              description="Todos os setores ativos com o caminho na hierarquia (para em cópia, aprovação e troca de setor).", responses=SEM_ACESSO)
def setores_ativos(_: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[SetorResumo]:
    return [SetorResumo(id=s.id, nome=s.nome, caminho=c) for s, c in parametros.setores_ativos(sessao)]


@roteador.get("/aprovacoes/minhas", response_model=list[AprovacaoPendente], summary="Minhas aprovações",
              description="Aprovações aguardando a pessoa ou um setor de que ela é membro.", responses=SEM_ACESSO)
def minhas_aprovacoes(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[AprovacaoPendente]:
    usuario, _ = ctx
    lista = acoes.minhas_aprovacoes(sessao, usuario)
    nomes = servico.nomes_de_usuarios(sessao, {v.solicitante_id for v in lista} | {v.alvo_usuario_id for v in lista})
    setores = {s.id: s.nome for s, _ in parametros.setores_ativos(sessao)}
    return [AprovacaoPendente(id=v.id, chamado_numero=v.chamado.numero, chamado_titulo=v.chamado.titulo, pedido=v.pedido,
                              solicitante_nome=nomes.get(v.solicitante_id, ""), criado_em=v.criado_em,
                              alvo_nome=nomes.get(v.alvo_usuario_id, "") if v.alvo_usuario_id else setores.get(v.alvo_setor_id, ""))
            for v in lista]


@roteador.post("/aprovacoes/{validacao_id}/responder", response_model=ChamadoDetalhe, summary="Aprovar ou não aprovar",
               description="A pessoa (ou um membro do setor) responde. Não aprovar exige o motivo. Sem outra aprovação aguardando, o chamado volta ao atendimento.",
               responses={**NAO_ENCONTRADO, **SEM_ACESSO, status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Já respondida (`ja_respondida`)."}})
def responder_aprovacao(validacao_id: uuid.UUID, corpo: RespostaAprovacao, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                        sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        v = acoes.responder_aprovacao(sessao, usuario, validacao_id, corpo.aprovar, corpo.resposta)
        numero = v.chamado.numero
        sessao.commit()
    c, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(c)


@roteador.get("/meus", response_model=ListaChamados, summary="Meus chamados",
              description="Chamados em que a pessoa é solicitante ou que foram abertos em nome de um setor dela, do mais recente para o mais antigo. "
              "`filtro`: `abertos` (padrão), `aguardando` (pendentes de resposta), `resolvidos` ou `todos`. "
              "`ordem` (coluna clicada: `numero`, `titulo`, `solicitante`, `setor`, `situacao`, `prioridade`, `prazo` ou `aberto_em`) e `direcao` (`asc`/`desc`); "
              "sem `ordem`, do mais recente para o mais antigo.", responses=SEM_ACESSO)
def meus(filtro: FiltroMeus = "abertos", busca: str = "", pagina: int = Query(1, ge=1), tamanho: int = Query(30, ge=1, le=100),
         ordem: OrdemChamados | None = None, direcao: Direcao = "asc",
         ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ListaChamados:
    usuario, p = ctx
    with _traduzir(sessao):
        itens, total = servico.meus(sessao, usuario, p, filtro, busca, pagina, tamanho, ordem, direcao)
    return _montador(sessao, usuario, p).lista(itens, total)


@roteador.get("", response_model=ListaChamados, summary="Fila de atendimento",
              description="Chamados que a pessoa enxerga (setores dela, setores abaixo se for líder, ou todos com \"ver todos\" ou Controle total). "
              "`filtro`: `abertos` (padrão), `meus` (eu sou o responsável), `setor`, `novos`, `sem_responsavel`, `solucionados` ou `todos`. "
              "`busca`: número (`1530` ou `#1530`), título ou nome do solicitante. Ordem padrão: prioridade, prazo de solução, abertura; "
              "`ordem` + `direcao` (`asc`/`desc`) ordenam pela coluna clicada (ver `GET /meus`). Exige Modificação. "
              "**Recorte dos Relatórios** (clique num número): `escopo_relatorio` + `relatorio_setor_id` (os setores do relatório), `aberto_de/ate`, "
              "`resolvido_de/ate` (com `resolvido_por`: soluções registradas pela pessoa), `assumido_por` + `assumido_de/ate`, `categoria_id`, `nota` e "
              "`reabertos`. Datas inclusivas, em dias de São Paulo.",
              responses=SEM_ACESSO)
def fila(filtro: FiltroFila = "abertos", busca: str = "", setor_id: int | None = None, pagina: int = Query(1, ge=1), tamanho: int = Query(50, ge=1, le=200),
         ordem: OrdemChamados | None = None, direcao: Direcao = "asc",
         escopo_relatorio: bool = False, relatorio_setor_id: int | None = None, aberto_de: date | None = None, aberto_ate: date | None = None,
         resolvido_de: date | None = None, resolvido_ate: date | None = None, resolvido_por: int | None = None, assumido_por: int | None = None,
         assumido_de: date | None = None, assumido_ate: date | None = None, categoria_id: uuid.UUID | None = None,
         nota: int | None = Query(None, ge=1, le=5), reabertos: bool = False,
         ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ListaChamados:
    usuario, p = ctx
    recorte = servico.Recorte(escopo_relatorio, relatorio_setor_id, aberto_de, aberto_ate, resolvido_de, resolvido_ate, resolvido_por, assumido_por,
                              assumido_de, assumido_ate, categoria_id, nota, reabertos)
    with _traduzir(sessao):
        itens, total = servico.fila(sessao, usuario, p, filtro, busca, setor_id, pagina, tamanho, ordem, direcao,
                                    recorte if recorte != servico.Recorte() else None)
    return _montador(sessao, usuario, p).lista(itens, total)


# ---------------------------------------------------------------------------------------------
# Parâmetros (Controle total)
# ---------------------------------------------------------------------------------------------

def _expediente(e) -> ExpedienteLeitura:
    return ExpedienteLeitura(id=e.id, nome=e.nome, ativo=e.ativo, faixas=[FaixaExpediente(dia_semana=f.dia_semana, inicio=f.inicio, fim=f.fim) for f in e.faixas])


def _sla(s: SlaChamados) -> SlaLeitura:
    return SlaLeitura(id=s.id, nome=s.nome, tipo=s.tipo, tempo=s.tempo, unidade=s.unidade, expediente_id=s.expediente_id, ativo=s.ativo,
                      expediente_nome=s.expediente.nome)


def _categoria(c: CategoriaChamados, setores: dict[int, str]) -> CategoriaLeitura:
    efetivo = parametros.efetiva(c).setor_id
    return CategoriaLeitura(
        id=c.id, nome=c.nome, pai_id=c.pai_id, ativa=c.ativa, visivel_solicitante=c.visivel_solicitante, permite_incidente=c.permite_incidente,
        permite_requisicao=c.permite_requisicao, setor_id=c.setor_id, responsavel_id=c.responsavel_id, sla_tto_id=c.sla_tto_id, sla_ttr_id=c.sla_ttr_id,
        prioridade_padrao=c.prioridade_padrao, perguntar_impedindo=c.perguntar_impedindo, sigilosa=c.sigilosa, ordem=c.ordem, caminho=c.caminho, nivel=c.nivel,
        categoria_itil_id=c.categoria_itil_id, setores_permitidos=sorted(v.setor_id for v in c.setores_permitidos),
        setor_efetivo_id=efetivo, setor_efetivo_nome=setores.get(efetivo, ""), herda_setor=c.setor_id is None,
    )


@roteador.get("/parametros/setores", response_model=list[SetorResumo], summary="Setores que podem ser responsáveis",
              description="Todo setor ativo do SGI (oficial ou sistêmico) pode ser responsável por uma categoria ou receber chamado.", responses=SEM_ACESSO)
def setores(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[SetorResumo]:
    return [SetorResumo(id=s.id, nome=s.nome, caminho=c) for s, c in parametros.setores_ativos(sessao)]


@roteador.get("/parametros/expedientes", response_model=list[ExpedienteLeitura], summary="Expedientes", responses=SEM_ACESSO,
              description="Horários de trabalho usados no cálculo dos prazos (os feriados vêm do RH).")
def expedientes(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[ExpedienteLeitura]:
    return [_expediente(e) for e in parametros.listar_expedientes(sessao)]


@roteador.post("/parametros/expedientes", response_model=ExpedienteLeitura, status_code=status.HTTP_201_CREATED, summary="Criar expediente",
               description="Nome único e pelo menos uma faixa de horário (sem faixas sobrepostas no mesmo dia).", responses={**INVALIDO, **CONFLITO, **SEM_ACESSO})
def criar_expediente(corpo: GravacaoExpediente, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ExpedienteLeitura:
    with _traduzir(sessao):
        e = parametros.salvar_expediente(sessao, None, corpo.nome, corpo.ativo, [DadosFaixa(**f.model_dump()) for f in corpo.faixas])
        sessao.commit()
    return _expediente(e)


@roteador.put("/parametros/expedientes/{expediente_id}", response_model=ExpedienteLeitura, summary="Alterar expediente",
              description="Troca nome, situação e faixas. Vale para os prazos dos próximos chamados.", responses={**INVALIDO, **CONFLITO, **SEM_ACESSO, **resposta_nao_encontrado("Expediente")})
def alterar_expediente(expediente_id: uuid.UUID, corpo: GravacaoExpediente, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ExpedienteLeitura:
    with _traduzir(sessao):
        e = parametros.salvar_expediente(sessao, expediente_id, corpo.nome, corpo.ativo, [DadosFaixa(**f.model_dump()) for f in corpo.faixas])
        sessao.commit()
    return _expediente(e)


@roteador.delete("/parametros/expedientes/{expediente_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir expediente",
                 description="Exclui o expediente que nenhum SLA usa. Em uso por algum SLA, `409 em_uso` com os nomes dos SLAs: troque o expediente deles "
                 "ou desative este (os prazos dependem do horário de trabalho).",
                 responses={**SEM_ACESSO, **resposta_nao_encontrado("Expediente"),
                            status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Expediente usado por SLAs (`em_uso`)."}})
def excluir_expediente(expediente_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        parametros.excluir_expediente(sessao, expediente_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros/slas", response_model=list[SlaLeitura], summary="SLAs", responses=SEM_ACESSO,
              description="Prazos de atendimento (`tto`) e de solução (`ttr`), sempre ligados a um expediente.")
def slas(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[SlaLeitura]:
    return [_sla(s) for s in parametros.listar_slas(sessao)]


@roteador.post("/parametros/slas", response_model=SlaLeitura, status_code=status.HTTP_201_CREATED, summary="Criar SLA",
               description="Tempo maior que zero e expediente ativo obrigatório.", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Expediente")})
def criar_sla(corpo: GravacaoSla, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> SlaLeitura:
    with _traduzir(sessao):
        s = parametros.salvar_sla(sessao, None, corpo.nome, corpo.tipo, corpo.tempo, corpo.unidade, corpo.expediente_id, corpo.ativo)
        sessao.commit()
    return _sla(s)


@roteador.put("/parametros/slas/{sla_id}", response_model=SlaLeitura, summary="Alterar SLA",
              description="Vale para os próximos chamados (os prazos já calculados não mudam).", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("SLA")})
def alterar_sla(sla_id: uuid.UUID, corpo: GravacaoSla, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> SlaLeitura:
    with _traduzir(sessao):
        s = parametros.salvar_sla(sessao, sla_id, corpo.nome, corpo.tipo, corpo.tempo, corpo.unidade, corpo.expediente_id, corpo.ativo)
        sessao.commit()
    return _sla(s)


@roteador.delete("/parametros/slas/{sla_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir SLA",
                 description="Exclui o SLA que nenhuma categoria nem nenhum chamado usa. Em uso, `409 em_uso` dizendo onde: troque o SLA das categorias "
                 "ou desative-o (chamados já calculados com ele guardam o prazo no histórico).",
                 responses={**SEM_ACESSO, **resposta_nao_encontrado("SLA"),
                            status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "SLA usado por categorias ou chamados (`em_uso`)."}})
def excluir_sla(sla_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        parametros.excluir_sla(sessao, sla_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros/categorias", response_model=list[CategoriaLeitura], summary="Categorias (árvore)", responses=SEM_ACESSO,
              description="Todas as categorias, ativas e inativas, em ordem de caminho, com o setor responsável efetivo (próprio ou herdado).")
def categorias(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[CategoriaLeitura]:
    nomes = {s.id: s.nome for s, _ in parametros.setores_ativos(sessao)}
    return [_categoria(c, nomes) for c in parametros.listar_categorias(sessao)]


_ERROS_CATEGORIA = {status.HTTP_400_BAD_REQUEST: {"model": RespostaErro, "description": "Regra violada (`invalido`) ou categoria ativa sem setor responsável, própria ou herdada (`categoria_sem_setor`)."},
                    **CONFLITO, **SEM_ACESSO}


@roteador.post("/parametros/categorias", response_model=CategoriaLeitura, status_code=status.HTTP_201_CREATED, summary="Criar categoria",
               description="Nome único dentro da mesma categoria-mãe. Toda categoria ativa precisa de setor responsável (próprio ou herdado).", responses=_ERROS_CATEGORIA)
def criar_categoria(corpo: GravacaoCategoria, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> CategoriaLeitura:
    with _traduzir(sessao):
        c = parametros.salvar_categoria(sessao, None, DadosCategoria(**corpo.model_dump()))
        sessao.commit()
    return _categoria(c, {s.id: s.nome for s, _ in parametros.setores_ativos(sessao)})


@roteador.put("/parametros/categorias/{categoria_id}", response_model=CategoriaLeitura, summary="Alterar ou mover categoria",
              description="Renomear ou trocar a categoria-mãe recalcula o caminho da subárvore. Desativar não apaga (o histórico fica); só desativa sem subcategorias ativas.",
              responses={**_ERROS_CATEGORIA, **resposta_nao_encontrado("Categoria")})
def alterar_categoria(categoria_id: uuid.UUID, corpo: GravacaoCategoria, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> CategoriaLeitura:
    with _traduzir(sessao):
        c = parametros.salvar_categoria(sessao, categoria_id, DadosCategoria(**corpo.model_dump()))
        sessao.commit()
    return _categoria(c, {s.id: s.nome for s, _ in parametros.setores_ativos(sessao)})


@roteador.delete("/parametros/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir categoria",
                 description="Exclui a categoria sem subcategorias e sem chamados. Com subcategorias ou já usada em chamados, `409 em_uso`: desative-a "
                 "(o histórico continua apontando para ela).",
                 responses={**SEM_ACESSO, **resposta_nao_encontrado("Categoria"),
                            status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Categoria com subcategorias ou com chamados (`em_uso`)."}})
def excluir_categoria(categoria_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        parametros.excluir_categoria(sessao, categoria_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------------
# Categorias ITIL (classificação técnica, separada dos assuntos)
# ---------------------------------------------------------------------------------------------

def _itil(sessao: Session, c) -> CategoriaItilLeitura:
    usados = sessao.scalar(select(func.count()).select_from(Chamado).where(Chamado.categoria_itil_id == c.id)) or 0
    return CategoriaItilLeitura(id=c.id, nome=c.nome, pai_id=c.pai_id, ativa=c.ativa, ordem=c.ordem, caminho=c.caminho, nivel=c.nivel, chamados=usados)


@roteador.get("/parametros/categorias-itil", response_model=list[CategoriaItilLeitura], summary="Categorias ITIL (árvore)", responses=SEM_ACESSO,
              description="A classificação técnica dos chamados, em ordem de caminho. Separada das categorias de assunto (o que quem abre escolhe).")
def categorias_itil(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[CategoriaItilLeitura]:
    return [_itil(sessao, c) for c in parametros.listar_categorias_itil(sessao)]


@roteador.post("/parametros/categorias-itil", response_model=CategoriaItilLeitura, status_code=status.HTTP_201_CREATED, summary="Criar categoria ITIL",
               description="Nome único no mesmo nível (`409 conflito`), sem o caractere \">\".", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def criar_categoria_itil(corpo: GravacaoCategoriaItil, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> CategoriaItilLeitura:
    with _traduzir(sessao):
        c = parametros.salvar_categoria_itil(sessao, None, corpo.nome, corpo.pai_id, corpo.ativa, corpo.ordem)
        sessao.commit()
    return _itil(sessao, c)


@roteador.put("/parametros/categorias-itil/{itil_id}", response_model=CategoriaItilLeitura, summary="Alterar ou mover categoria ITIL",
              description="Mover para dentro dela mesma ou de uma filha: 400. Desativar com filha ativa: `409 conflito`.",
              responses={**INVALIDO, **SEM_ACESSO, **CONFLITO, **resposta_nao_encontrado("Categoria ITIL")})
def alterar_categoria_itil(itil_id: uuid.UUID, corpo: GravacaoCategoriaItil, _: Usuario = Depends(administrador),
                           sessao: Session = Depends(obter_sessao)) -> CategoriaItilLeitura:
    with _traduzir(sessao):
        c = parametros.salvar_categoria_itil(sessao, itil_id, corpo.nome, corpo.pai_id, corpo.ativa, corpo.ordem)
        sessao.commit()
    return _itil(sessao, c)


@roteador.delete("/parametros/categorias-itil/{itil_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir categoria ITIL",
                 description="Só sem subcategorias e sem chamados classificados (`409 em_uso`: desative). Os assuntos que a usavam como padrão ficam sem padrão.",
                 responses={**SEM_ACESSO, **resposta_nao_encontrado("Categoria ITIL"), status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Em uso."}})
def excluir_categoria_itil(itil_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        parametros.excluir_categoria_itil(sessao, itil_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/categorias-itil", response_model=list[CategoriaItilResumo], summary="Categorias ITIL para classificar",
              description="As ativas, para quem atende escolher no chamado.", responses=SEM_ACESSO)
def categorias_itil_ativas(ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[CategoriaItilResumo]:
    if not ctx[1].atender:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "A categoria ITIL é de quem atende chamados.", "acesso_negado")
    return [CategoriaItilResumo(id=c.id, caminho=c.caminho) for c in parametros.listar_categorias_itil(sessao) if c.ativa]


def _campo_leitura(c) -> CampoLeitura:
    return CampoLeitura(id=c.id, categoria_id=c.categoria_id, rotulo=c.rotulo, tipo=c.tipo, obrigatorio=c.obrigatorio, dado_pessoal=c.dado_pessoal, ajuda=c.ajuda,
                        opcoes=c.opcoes, condicao=CondicaoCampo(**c.condicao) if c.condicao else None, ordem=c.ordem, ativo=c.ativo)


def _dados_campo(corpo: GravacaoCampo) -> DadosCampo:
    return DadosCampo(rotulo=corpo.rotulo, tipo=corpo.tipo, obrigatorio=corpo.obrigatorio, dado_pessoal=corpo.dado_pessoal, ajuda=corpo.ajuda, opcoes=corpo.opcoes,
                      condicao={"campo_id": str(corpo.condicao.campo_id), "igual": corpo.condicao.igual} if corpo.condicao else None, ordem=corpo.ordem,
                      ativo=corpo.ativo)


_ERROS_CAMPO = {**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Categoria ou campo")}


@roteador.get("/parametros/categorias/{categoria_id}/campos", response_model=list[CampoLeitura], summary="Campos adicionais da categoria",
              description="Os campos cadastrados nesta categoria (sem os herdados), ativos e inativos.", responses=_ERROS_CAMPO)
def campos_da_categoria(categoria_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[CampoLeitura]:
    with _traduzir(sessao):
        categoria = parametros.obter_categoria(sessao, categoria_id)
    return [_campo_leitura(c) for c in categoria.campos]


@roteador.post("/parametros/categorias/{categoria_id}/campos", response_model=CampoLeitura, status_code=status.HTTP_201_CREATED, summary="Criar campo adicional",
               description="Vale para a categoria e as subcategorias. `lista` exige duas opções ou mais; a `condicao` aponta para outro campo da categoria "
               "ou de uma categoria acima. `dado_pessoal` mascara o valor para quem não atende.", responses=_ERROS_CAMPO)
def criar_campo(categoria_id: uuid.UUID, corpo: GravacaoCampo, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> CampoLeitura:
    with _traduzir(sessao):
        c = campos_adicionais.salvar_campo(sessao, categoria_id, None, _dados_campo(corpo))
        sessao.commit()
    return _campo_leitura(c)


@roteador.put("/parametros/categorias/{categoria_id}/campos/{campo_id}", response_model=CampoLeitura, summary="Alterar campo adicional",
              description="Mesmas regras da criação.", responses=_ERROS_CAMPO)
def alterar_campo(categoria_id: uuid.UUID, campo_id: uuid.UUID, corpo: GravacaoCampo, _: Usuario = Depends(administrador),
                  sessao: Session = Depends(obter_sessao)) -> CampoLeitura:
    with _traduzir(sessao):
        c = campos_adicionais.salvar_campo(sessao, categoria_id, campo_id, _dados_campo(corpo))
        sessao.commit()
    return _campo_leitura(c)


@roteador.delete("/parametros/categorias/{categoria_id}/campos/{campo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir campo adicional",
                 description="Exclui o campo que nenhum chamado respondeu; já respondido, `409 em_uso` (desative-o).",
                 responses={**_ERROS_CAMPO, status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Campo já respondido (`em_uso`)."}})
def excluir_campo(categoria_id: uuid.UUID, campo_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        campos_adicionais.excluir_campo(sessao, categoria_id, campo_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros/geral", response_model=ParametrosGerais, summary="Parâmetros gerais",
              description="Dias para reabrir, ponto facultativo, os limites de cor do prazo e a data de início do atendimento no SGI.", responses=SEM_ACESSO)
def geral(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ParametrosGerais:
    return ParametrosGerais(**vars(configuracao.geral(sessao)))


@roteador.put("/parametros/geral", response_model=ParametrosGerais, summary="Gravar os parâmetros gerais",
              description="Os limites precisam crescer (alerta < atenção < perigo ≤ 100). Valem para as próximas leituras.", responses={**INVALIDO, **SEM_ACESSO})
def salvar_geral(corpo: ParametrosGerais, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> ParametrosGerais:
    with _traduzir(sessao):
        g = configuracao.salvar_geral(sessao, configuracao.Geral(**corpo.model_dump()))
        sessao.commit()
    return ParametrosGerais(**vars(g))


@roteador.get("/parametros/status", response_model=list[StatusLeitura], summary="Status: nome exibido e cor",
              description="Os cinco status-base (fixos no código, as regras dependem deles) com o nome e a cor atuais.", responses=SEM_ACESSO)
def status_base(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[StatusLeitura]:
    return [StatusLeitura(status_base=b, nome=n, cor=c) for b, (n, c) in configuracao.apresentacao(sessao).items()]


@roteador.put("/parametros/status/{status}", response_model=list[StatusLeitura], summary="Mudar nome e cor de um status",
              description="Só o nome exibido e a cor; o comportamento do status não muda.", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Status")})
def salvar_status(status: str, corpo: GravacaoStatus, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[StatusLeitura]:
    with _traduzir(sessao):
        configuracao.salvar_apresentacao(sessao, status, corpo.nome, corpo.cor)
        sessao.commit()
    return [StatusLeitura(status_base=b, nome=n, cor=c) for b, (n, c) in configuracao.apresentacao(sessao).items()]


def _substatus(x: SubstatusChamados) -> SubstatusLeitura:
    return SubstatusLeitura(id=x.id, status_base=x.status_base, nome=x.nome, cor=x.cor, ordem=x.ordem, ativo=x.ativo)


@roteador.get("/substatus", response_model=list[SubstatusLeitura], summary="Sub-status", responses=SEM_ACESSO,
              description="Todos os sub-status (ativos e inativos), para quem atende escolher e para os Parâmetros.")
def substatus(_: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[SubstatusLeitura]:
    return [_substatus(x) for x in configuracao.listar_substatus(sessao)]


@roteador.post("/parametros/substatus", response_model=SubstatusLeitura, status_code=status.HTTP_201_CREATED, summary="Criar sub-status",
               description="Sub-status dentro de um status-base (ex.: \"Aguardando peça\" em \"Em atendimento\").", responses={**INVALIDO, **SEM_ACESSO})
def criar_substatus(corpo: GravacaoSubstatus, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> SubstatusLeitura:
    with _traduzir(sessao):
        x = configuracao.salvar_substatus(sessao, None, corpo.status_base, corpo.nome, corpo.cor, corpo.ordem, corpo.ativo)
        sessao.commit()
    return _substatus(x)


@roteador.put("/parametros/substatus/{substatus_id}", response_model=SubstatusLeitura, summary="Alterar sub-status",
              description="Mesmas regras da criação.", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Sub-status")})
def alterar_substatus(substatus_id: uuid.UUID, corpo: GravacaoSubstatus, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> SubstatusLeitura:
    with _traduzir(sessao):
        x = configuracao.salvar_substatus(sessao, substatus_id, corpo.status_base, corpo.nome, corpo.cor, corpo.ordem, corpo.ativo)
        sessao.commit()
    return _substatus(x)


@roteador.delete("/parametros/substatus/{substatus_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir sub-status",
                 description="Os chamados que estavam nele ficam só com o status-base.", responses={**SEM_ACESSO, **resposta_nao_encontrado("Sub-status")})
def excluir_substatus(substatus_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        configuracao.excluir_substatus(sessao, substatus_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/parametros/setores-atendimento", response_model=list[SetorAtendimentoLeitura], summary="Setores de atendimento",
              description="Todos os setores ativos (qualquer um pode atender) e o ajuste \"vê todos os chamados\".", responses=SEM_ACESSO)
def setores_atendimento(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[SetorAtendimentoLeitura]:
    return [SetorAtendimentoLeitura(setor_id=s.id, nome=s.nome, caminho=c, ve_todos=v) for s, c, v in configuracao.setores_atendimento(sessao)]


@roteador.put("/parametros/setores-atendimento/{setor_id}", response_model=SetorAtendimentoLeitura, summary="Ajustar setor de atendimento",
              description="`ve_todos`: os membros do setor que atendem enxergam os chamados de todos os setores.",
              responses={**SEM_ACESSO, **resposta_nao_encontrado("Setor")})
def salvar_setor_atendimento(setor_id: int, corpo: GravacaoSetorAtendimento, _: Usuario = Depends(administrador),
                             sessao: Session = Depends(obter_sessao)) -> SetorAtendimentoLeitura:
    with _traduzir(sessao):
        configuracao.salvar_setor_atendimento(sessao, setor_id, corpo.ve_todos)
        sessao.commit()
    s, c, v = next(x for x in configuracao.setores_atendimento(sessao) if x[0].id == setor_id)
    return SetorAtendimentoLeitura(setor_id=s.id, nome=s.nome, caminho=c, ve_todos=v)


def _recorrente(sessao: Session, r) -> RecorrenteLeitura:
    pessoa = sessao.get(Usuario, r.solicitante_id)
    return RecorrenteLeitura(
        id=r.id, nome=r.nome, categoria_id=r.categoria_id, titulo=r.titulo, descricao=r.descricao, periodicidade_quantidade=r.periodicidade_quantidade,
        periodicidade_unidade=r.periodicidade_unidade, antecedencia_min=r.antecedencia_min, so_dias_uteis=r.so_dias_uteis, proxima_em=r.proxima_em,
        fim_em=r.fim_em, ativo=r.ativo, solicitante_id=r.solicitante_id, categoria_caminho=r.categoria.caminho,
        solicitante_nome=(pessoa.nome_completo or pessoa.login) if pessoa else "", ultima_geracao_em=r.ultima_geracao_em,
    )


@roteador.get("/parametros/recorrentes", response_model=list[RecorrenteLeitura], summary="Chamados recorrentes", responses=SEM_ACESSO,
              description="Chamados abertos sozinhos a cada período (gerados pela tarefa automática `minuto`).")
def recorrentes(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> list[RecorrenteLeitura]:
    return [_recorrente(sessao, r) for r in configuracao.listar_recorrentes(sessao)]


@roteador.post("/parametros/recorrentes", response_model=RecorrenteLeitura, status_code=status.HTTP_201_CREATED, summary="Criar recorrente",
               description="Categoria ativa com setor responsável; o chamado é aberto em nome de `solicitante_id` (padrão: quem cadastra), `antecedencia_min` "
               "minutos antes de cada ocorrência. Com `so_dias_uteis`, a ocorrência que cair em fim de semana ou feriado do RH passa para o próximo dia útil.",
               responses={**INVALIDO, **SEM_ACESSO})
def criar_recorrente(corpo: GravacaoRecorrente, usuario: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> RecorrenteLeitura:
    with _traduzir(sessao):
        r = configuracao.salvar_recorrente(sessao, None, configuracao.DadosRecorrente(**corpo.model_dump()), usuario)
        sessao.commit()
    return _recorrente(sessao, r)


@roteador.put("/parametros/recorrentes/{recorrente_id}", response_model=RecorrenteLeitura, summary="Alterar recorrente",
              description="Mesmas regras da criação.", responses={**INVALIDO, **SEM_ACESSO, **resposta_nao_encontrado("Recorrente")})
def alterar_recorrente(recorrente_id: uuid.UUID, corpo: GravacaoRecorrente, usuario: Usuario = Depends(administrador),
                       sessao: Session = Depends(obter_sessao)) -> RecorrenteLeitura:
    with _traduzir(sessao):
        r = configuracao.salvar_recorrente(sessao, recorrente_id, configuracao.DadosRecorrente(**corpo.model_dump()), usuario)
        sessao.commit()
    return _recorrente(sessao, r)


@roteador.delete("/parametros/recorrentes/{recorrente_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir recorrente",
                 description="Os chamados já gerados continuam (só perdem o vínculo).", responses={**SEM_ACESSO, **resposta_nao_encontrado("Recorrente")})
def excluir_recorrente(recorrente_id: uuid.UUID, _: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> Response:
    with _traduzir(sessao):
        configuracao.excluir_recorrente(sessao, recorrente_id)
        sessao.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.get("/saude", response_model=SaudeChamados, summary="Painel de saúde",
              description="Última rodada de cada tarefa automática, e-mails parados ou com falha e a lista de problemas, calculados na hora "
              "(mostra o problema mesmo com o agendador parado). Só quem administra.", responses=SEM_ACESSO)
def saude(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> SaudeChamados:
    s = tarefas_agendadas.saude(sessao)
    return SaudeChamados(tarefas=[TarefaSaude(**t) for t in s.tarefas], email_parados=s.email_parados, email_falhas_24h=s.email_falhas_24h,
                         email_mais_antigo=s.email_mais_antigo, ultimo_erro_email=s.ultimo_erro_email, problemas=s.problemas)


# ---------------------------------------------------------------------------------------------
# Um chamado
# ---------------------------------------------------------------------------------------------

@roteador.get("/{numero}", response_model=ChamadoDetalhe, summary="Chamado e linha do tempo",
              description="O chamado, a linha do tempo (sem as mensagens privadas para quem não atende) e as ações que a pessoa pode fazer. "
              "Categoria sigilosa: quem não atende vê só \"Chamado restrito\". `404` também para quem não enxerga o chamado.", responses={**NAO_ENCONTRADO, **SEM_ACESSO})
def detalhe(numero: int, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        chamado, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(chamado)


@roteador.post("/{numero}/assumir", response_model=ChamadoDetalhe, summary="Assumir o chamado",
               description="A pessoa vira a responsável pelo atendimento (o chamado passa a \"Em atendimento\" e o prazo de atendimento é cumprido). "
               "Atômico: se outra pessoa assumiu ou alterou antes (`versao` diferente), responde `409 chamado_alterado`.",
               responses={**NAO_ENCONTRADO, **SEM_ACESSO, **ALTERADO})
def assumir(numero: int, corpo: Assumir, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        servico.assumir(sessao, usuario, p, numero, corpo.versao)
        sessao.commit()
    chamado, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(chamado)


@roteador.post("/{numero}/acompanhamentos", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Responder no chamado",
               description="`multipart/form-data`: `dados` (JSON de `NovaResposta`) e até 10 `arquivos`. O solicitante só escreve em público; a mensagem "
               "privada é da equipe. A primeira resposta de quem atende cumpre o prazo de atendimento. Avisa o outro lado.",
               responses={**INVALIDO, **NAO_ENCONTRADO, **SEM_ACESSO, **ALTERADO})
async def responder(numero: int, dados: str = Form(..., description="JSON de `NovaResposta`."), arquivos: list[UploadFile] = File(default_factory=list),
                    ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    corpo = _json(NovaResposta, dados)
    conteudos = await _arquivos(arquivos)
    with _traduzir(sessao):
        servico.responder(sessao, usuario, p, numero, corpo.texto, corpo.privado, conteudos)
        sessao.commit()
    chamado, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(chamado)


@roteador.post("/{numero}/solucao", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Resolver o chamado",
               description="`multipart/form-data`: `dados` (JSON de `NovaSolucao`) e até 10 `arquivos`. Resolver é o fim do chamado: o relógio para e o "
               "solicitante tem alguns dias úteis (parâmetro, padrão 5) para dizer \"Não resolveu\" (marco seguinte). Avisa o solicitante e os membros do "
               "setor solicitante (estes também por e-mail).", responses={**INVALIDO, **NAO_ENCONTRADO, **SEM_ACESSO, **ALTERADO})
async def solucionar(numero: int, dados: str = Form(..., description="JSON de `NovaSolucao`."), arquivos: list[UploadFile] = File(default_factory=list),
                     ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    corpo = _json(NovaSolucao, dados)
    conteudos = await _arquivos(arquivos)
    with _traduzir(sessao):
        servico.solucionar(sessao, usuario, p, numero, corpo.texto, conteudos)
        sessao.commit()
    chamado, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(chamado)


@roteador.get("/{numero}/anexos/{anexo_id}", summary="Baixar anexo do chamado", response_class=FileResponse,
              description="Entrega o arquivo para quem vê o chamado; o anexo de mensagem privada só para quem atende.", responses={**NAO_ENCONTRADO, **SEM_ACESSO})
def baixar_anexo(numero: int, anexo_id: uuid.UUID, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> FileResponse:
    usuario, p = ctx
    with _traduzir(sessao):
        vinculo = servico.anexo_do_chamado(sessao, usuario, p, numero, anexo_id)
    try:
        return servico_anexos.resposta_download(vinculo.anexo)
    except servico_anexos.ErroAnexo as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro


def _acao(sessao: Session, usuario: Usuario, p: Papeis, numero: int) -> ChamadoDetalhe:
    """Detalhe do chamado depois de uma ação (já com o commit feito)."""
    chamado, a = servico.obter(sessao, usuario, p, numero)
    return _Montador(sessao, usuario, p, a).detalhe(chamado)


def _acao_ou_nada(sessao: Session, usuario: Usuario, p: Papeis, numero: int) -> ChamadoDetalhe | None:
    """Como `_acao`, mas a ação pode ter tirado a pessoa do chamado (passou para outro setor, saiu da cópia): aí devolve `null`."""
    try:
        return _acao(sessao, usuario, p, numero)
    except ErroChamado:
        return None


_ERROS_ACAO = {**INVALIDO, **NAO_ENCONTRADO, **SEM_ACESSO, **ALTERADO}


@roteador.patch("/{numero}", response_model=ChamadoDetalhe | None, summary="Alterar o chamado",
                description="Quem atende troca **só o que enviar**: `responsavel_id` (pessoa ativa do setor responsável; `null` tira), `setor_id` (avisa o setor novo, "
                "com e-mail), `categoria_id` (reaplica setor, SLAs e prioridade da categoria nova) e `prioridade` (com `motivo_prioridade`). Tudo vai para o "
                "histórico. `versao` diferente da atual: `409 chamado_alterado`. Responde `null` quando a pessoa deixa de ver o chamado (ex.: passou para um setor que "
                "ela não atende).", responses=_ERROS_ACAO)
def alterar(numero: int, corpo: Alteracao, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe | None:
    usuario, p = ctx
    campos = corpo.model_dump(exclude_unset=True)
    versao = campos.pop("versao")
    with _traduzir(sessao):
        acoes.alterar(sessao, usuario, p, numero, versao, campos=campos)
        sessao.commit()
    return _acao_ou_nada(sessao, usuario, p, numero)


@roteador.put("/{numero}/categoria-itil", response_model=ChamadoDetalhe, summary="Classificar (categoria ITIL)",
              description="Quem atende escolhe a categoria ITIL (`null` = pendente), também depois de resolvido. Vai para a linha do tempo como nota privada; "
              "o solicitante não vê a classificação. `versao` diferente da atual: `409 chamado_alterado`.", responses=_ERROS_ACAO)
def classificar(numero: int, corpo: Classificacao, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.classificar(sessao, usuario, p, numero, corpo.versao, corpo.categoria_itil_id)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.get("/{numero}/responsaveis", response_model=list[PessoaResumo], summary="Quem pode ser o responsável",
              description="Membros ativos do setor responsável (para trocar o responsável). Só para quem atende.", responses={**NAO_ENCONTRADO, **SEM_ACESSO})
def responsaveis(numero: int, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> list[PessoaResumo]:
    usuario, p = ctx
    with _traduzir(sessao):
        pessoas_setor = acoes.responsaveis_possiveis(sessao, usuario, p, numero)
    return [PessoaResumo(id=u.id, nome=u.nome_completo or u.login, login=u.login, cargo=u.cargo or "") for u in pessoas_setor]


@roteador.post("/{numero}/pendente", response_model=ChamadoDetalhe, summary="Pôr em pendente",
               description="Pausa o prazo de solução (o tempo útil parado empurra o prazo). `motivo` opcional, avisado ao solicitante. A resposta do solicitante "
               "retoma o atendimento sozinha.", responses=_ERROS_ACAO)
def pendente(numero: int, corpo: Motivo, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.pendente(sessao, usuario, p, numero, corpo.motivo)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.post("/{numero}/retomar", response_model=ChamadoDetalhe, summary="Retomar o atendimento",
               description="Sai do pendente: o prazo de solução volta a contar, empurrado pelo tempo útil parado.", responses=_ERROS_ACAO)
def retomar(numero: int, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.retomar(sessao, usuario, p, numero)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.post("/{numero}/nao-resolveu", response_model=ChamadoDetalhe, summary="Não resolveu (reabrir)",
               description="O solicitante (ou alguém do setor solicitante) reabre o chamado resolvido em até `dias_reabrir` dias úteis (padrão 5), com o motivo "
               "(mínimo 5 caracteres). O chamado volta ao atendimento com prazo de solução novo, e o responsável (ou o setor) é avisado. Fora do prazo: "
               "`409 prazo_reabertura` (abra um chamado novo, relacionado a este).",
               responses={**INVALIDO, **NAO_ENCONTRADO, **SEM_ACESSO,
                          status.HTTP_409_CONFLICT: {"model": RespostaErro, "description": "Prazo de reabertura vencido (`prazo_reabertura`) ou chamado não resolvido (`chamado_aberto`)."}})
def nao_resolveu(numero: int, corpo: Motivo, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.nao_resolveu(sessao, usuario, p, numero, corpo.motivo)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.post("/{numero}/em-copia", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Pôr em cópia",
               description="Quem atende ou quem pediu inclui uma pessoa (`usuario_id`) ou um setor (`setor_id`). Quem está em cópia vê o chamado e recebe os avisos "
               "pelo canal que escolheu.", responses=_ERROS_ACAO)
def incluir_em_copia(numero: int, corpo: InclusaoEmCopia, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                     sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.incluir_em_copia(sessao, usuario, p, numero, corpo.usuario_id, corpo.setor_id)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.delete("/{numero}/em-copia/{ator_id}", response_model=ChamadoDetalhe | None, summary="Tirar da cópia",
                 description="Quem atende, quem pediu ou a própria pessoa. Responde `null` quando a pessoa saiu da própria cópia e deixou de ver o chamado.",
                 responses=_ERROS_ACAO)
def remover_em_copia(numero: int, ator_id: uuid.UUID, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                     sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe | None:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.remover_em_copia(sessao, usuario, p, numero, ator_id)
        sessao.commit()
    return _acao_ou_nada(sessao, usuario, p, numero)


@roteador.post("/{numero}/tarefas", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Criar tarefa",
               description="Tarefa da equipe (privada por padrão: o solicitante não vê). Avisa o responsável da tarefa.", responses=_ERROS_ACAO)
def criar_tarefa(numero: int, corpo: NovaTarefa, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.criar_tarefa(sessao, usuario, p, numero, corpo.texto, corpo.responsavel_id, corpo.privada)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.patch("/{numero}/tarefas/{tarefa_id}", response_model=ChamadoDetalhe, summary="Marcar tarefa feita ou a fazer",
                description="Só quem atende.", responses=_ERROS_ACAO)
def marcar_tarefa(numero: int, tarefa_id: uuid.UUID, corpo: MarcacaoTarefa, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                  sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.marcar_tarefa(sessao, usuario, p, numero, tarefa_id, corpo.feita)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.post("/{numero}/aprovacoes", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED, summary="Pedir aprovação",
               description="Quem atende pede aprovação a uma pessoa (`alvo_usuario_id`) ou a um setor (`alvo_setor_id`, qualquer membro responde). O chamado fica "
               "\"Em aprovação\" e quem aprova é avisado também por e-mail.", responses=_ERROS_ACAO)
def pedir_aprovacao(numero: int, corpo: PedidoAprovacao, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario),
                    sessao: Session = Depends(obter_sessao)) -> ChamadoDetalhe:
    usuario, p = ctx
    with _traduzir(sessao):
        acoes.pedir_aprovacao(sessao, usuario, p, numero, corpo.alvo_usuario_id, corpo.alvo_setor_id, corpo.pedido)
        sessao.commit()
    return _acao(sessao, usuario, p, numero)


@roteador.get("/{numero}/dados-pessoais/{campo_id}", summary="Ver dado pessoal completo",
              description="Valor completo de um campo marcado como dado pessoal, só para quem atende o chamado. Cada consulta fica na auditoria (LGPD).",
              responses={**NAO_ENCONTRADO, **SEM_ACESSO})
def dado_pessoal(numero: int, campo_id: uuid.UUID, ctx: tuple[Usuario, Papeis] = Depends(papeis_do_usuario), sessao: Session = Depends(obter_sessao)) -> dict:
    usuario, p = ctx
    with _traduzir(sessao):
        valor = acoes.dado_pessoal(sessao, usuario, p, numero, campo_id)
        sessao.commit()
    return {"valor": valor}
