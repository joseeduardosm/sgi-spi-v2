# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas do Módulo RH (cadastro validado pela CGP, férias e licença-prêmio).
"""Módulo RH (`/api/rh`).

- `papeis`: o que o usuário é no RH (CGP, autorizador).
- `cadastro/*`: validação das alterações de cadastro e dados funcionais (só CGP).
- `afastamentos/*`: férias e licença-prêmio (usuário, autorizador e CGP).
- `parametros`: regras de agendamento (leitura para todos; gravação só CGP).

Todas as rotas exigem login com perfil em dia. Sem o papel exigido: `403 sem_permissao`.
"""

import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.rh import AlteracaoCadastral, Afastamento, PeriodoAquisitivo
from app.models.usuario import Usuario
from app.schemas.rh import (
    LinhaImportacaoRh,
    ResultadoImportacaoRh,
    LancamentoAfastamento,
    ResultadoValidacaoLote,
    ValidacaoLote,
    AfastamentoLeitura,
    AjustePeriodo,
    CompetenciaFolha,
    ErroLote,
    FeriadoLeitura,
    FeriasAVencer,
    GravacaoFeriado,
    PeriodoAtual,
    PeriodoLeitura,
    ProximoPeriodo,
    AlertaSetor,
    AlteracaoLeitura,
    CadastroRh,
    DadosFuncionaisLeitura,
    Decisao,
    EventoLeitura,
    GravacaoDadosFuncionais,
    GravacaoParametros,
    MeusAfastamentos,
    OpcaoPessoa,
    OpcaoSetor,
    PainelAfastamentos,
    PapeisRh,
    ParametrosLeitura,
    PedidoAfastamento,
    Recusa,
    SaldoLeitura,
    UsuarioPendente,
)
from app.services import servico_setores
from app.services.rh import servico_afastamentos as afastamentos
from app.services.rh import servico_cadastro as cadastro
from app.services.rh import folha_ponto, importacao_funcionais, relatorio_saldos, servico_feriados, servico_periodos
from app.services.servico_auditoria import auditar
from app.services.rh.papeis import SemPermissaoRh, dados_funcionais, eh_cgp, setor_do_usuario, usuarios_cgp

roteador = APIRouter(prefix="/rh", tags=["Módulo RH"], responses=RESPOSTAS_AUTENTICADAS)
SEM_PERMISSAO = {status.HTTP_403_FORBIDDEN: {"description": "Sem o papel exigido no RH (`sem_permissao`)."}}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@contextmanager
def _traduzir():
    """Erros do RH no formato padrão da API."""
    try:
        yield
    except SemPermissaoRh as erro:
        raise ErroApi(status.HTTP_403_FORBIDDEN, str(erro), "sem_permissao") from erro
    except (cadastro.ErroCadastro, afastamentos.ErroAfastamento) as erro:
        raise ErroApi(erro.status, str(erro), erro.codigo) from erro


def _nome(u: Usuario | None) -> str:
    return (u.nome_completo or u.login) if u else "—"


@roteador.get("/papeis", response_model=PapeisRh, summary="Meus papéis no RH",
              description="Se o usuário é da CGP (ou SuperRoot) e se é autorizador de alguém; define os atalhos do módulo.")
def meus_papeis(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> PapeisRh:
    return PapeisRh(**afastamentos.papeis(sessao, usuario))


# --- Cadastro (CGP) -----------------------------------------------------------------------------

def _alteracao(sessao: Session, a: AlteracaoCadastral) -> AlteracaoLeitura:
    return AlteracaoLeitura(
        id=a.id, campo=a.campo, rotulo=cadastro.ROTULOS.get(a.campo, a.campo),
        valor_anterior=a.valor_anterior, valor_anterior_rotulo=cadastro.rotulo_valor(sessao, a.campo, a.valor_anterior),
        valor_proposto=a.valor_proposto, valor_proposto_rotulo=cadastro.rotulo_valor(sessao, a.campo, a.valor_proposto),
        status=a.status, solicitada_em=a.solicitada_em, solicitada_por_nome=a.solicitada_por_nome, analisada_por_nome=a.analisada_por_nome,
        analisada_em=a.analisada_em, justificativa=a.justificativa, valor_corrigido=a.valor_corrigido,
        valor_corrigido_rotulo=cadastro.rotulo_valor(sessao, a.campo, a.valor_corrigido) if a.status == "recusada" else None,
    )


def _cadastro(sessao: Session, usuario: Usuario) -> CadastroRh:
    dados = dados_funcionais(sessao, usuario.id)
    autorizador = sessao.get(Usuario, dados.autorizador_id) if dados and dados.autorizador_id else None
    substituto = sessao.get(Usuario, dados.substituto_id) if dados and dados.substituto_id else None
    return CadastroRh(
        usuario_id=usuario.id, nome=_nome(usuario), login=usuario.login,
        perfil={c: cadastro.rotulo_valor(sessao, c, cadastro.para_texto(c, getattr(usuario, c))) for c in cadastro.CAMPOS},
        pendentes=[_alteracao(sessao, a) for a in cadastro.pendentes_do_usuario(sessao, usuario.id)],
        historico=[_alteracao(sessao, a) for a in cadastro.historico(sessao, usuario.id)],
        funcionais=DadosFuncionaisLeitura(
            autorizador_id=dados.autorizador_id if dados else None, autorizador_nome=_nome(autorizador) if autorizador else None,
            autorizador_sugerido_id=usuario.gestor_id, substituto_id=dados.substituto_id if dados else None,
            substituto_nome=_nome(substituto) if substituto else None, sem_superior=bool(dados and dados.sem_superior),
            inicio_periodo_aquisitivo=servico_periodos.texto_inicio(dados), periodos=_periodos(sessao, usuario.id),
            exercicio=dados.exercicio if dados else None,
            saldo_lp_dias=dados.saldo_lp_dias if dados else 0,
            jornada_semanal_horas=dados.jornada_semanal_horas if dados else None, regime_plantao=bool(dados and dados.regime_plantao),
            horario_trabalho_inicio=_hora(dados and dados.horario_trabalho_inicio), horario_trabalho_fim=_hora(dados and dados.horario_trabalho_fim),
            horario_estudante=bool(dados and dados.horario_estudante),
            intervalo_inicio=_hora(dados and dados.intervalo_inicio), intervalo_fim=_hora(dados and dados.intervalo_fim),
            rg_cin=dados.rg_cin if dados else None, rs_pv=dados.rs_pv if dados else None,
            atualizado_por_nome=dados.atualizado_por_nome if dados else None,
            atualizado_em=dados.atualizado_em if dados else None,
        ),
    )


def _hora(valor) -> str | None:
    """`HH:MM` (ou nulo)."""
    return valor.strftime("%H:%M") if valor else None


def _periodos(sessao: Session, usuario_id: int) -> list[PeriodoLeitura]:
    """Períodos aquisitivos (o vigente é criado se faltar), do mais recente para o mais antigo."""
    hoje = afastamentos.hoje()
    vigente = servico_periodos.vigente(sessao, usuario_id, hoje)
    lista = sessao.scalars(select(PeriodoAquisitivo).where(PeriodoAquisitivo.usuario_id == usuario_id).order_by(PeriodoAquisitivo.inicio.desc()))
    resultado = []
    for per in lista:
        usado = servico_periodos.usado(sessao, usuario_id, per.inicio, per.fim)
        resultado.append(PeriodoLeitura(exercicio=servico_periodos.exercicio_do_periodo(per.inicio, per.fim), inicio=per.inicio, fim=per.fim, dias_creditados=per.dias_creditados, usado=usado,
                                        disponivel=max(per.dias_creditados - usado, 0) if per.fim >= hoje else 0,
                                        dias_expirados=per.dias_expirados, origem=per.origem, vigente=vigente is not None and per.id == vigente.id))
    sessao.commit()
    return resultado


def _usuario(sessao: Session, usuario_id: int) -> Usuario:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.", "nao_encontrado")
    return usuario


@roteador.get("/cadastro/pendencias", response_model=list[UsuarioPendente], summary="Alterações de cadastro pendentes",
              description="Usuários com alterações aguardando validação, das mais antigas para as mais novas. Só CGP.", responses=SEM_PERMISSAO)
def listar_pendencias(sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> list[UsuarioPendente]:
    with _traduzir():
        grupos = cadastro.pendencias(sessao, autor)
    return [UsuarioPendente(usuario_id=u.id, nome=_nome(u), login=u.login, departamento=u.departamento or "",
                            alteracoes=[_alteracao(sessao, a) for a in lista]) for u, lista in grupos]


@roteador.get("/cadastro/usuarios/{usuario_id}", response_model=CadastroRh, summary="Cadastro de um usuário (CGP)",
              description="Valores em vigor, pendências, histórico completo e dados funcionais. Só CGP.",
              responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Usuário")})
def detalhar_cadastro(usuario_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> CadastroRh:
    with _traduzir():
        if not eh_cgp(sessao, autor):
            raise SemPermissaoRh("Somente a CGP pode consultar o cadastro de outros usuários.")
        return _cadastro(sessao, _usuario(sessao, usuario_id))


def _resultado_importacao(linhas, gravado: bool) -> ResultadoImportacaoRh:
    return ResultadoImportacaoRh(
        total=len(linhas), com_mudanca=sum(1 for l in linhas if l.mudancas and not l.erros), com_erro=sum(1 for l in linhas if l.erros),
        gravado=gravado, linhas=[LinhaImportacaoRh(linha=l.linha, login=l.login, nome=l.nome, mudancas=l.mudancas, erros=l.erros) for l in linhas],
    )


async def _planilha(arquivo: UploadFile) -> bytes:
    if not (arquivo.filename or "").lower().endswith(".xlsx"):
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Envie a planilha no formato .xlsx.", "invalido")
    return await arquivo.read(importacao_funcionais.TAMANHO_MAXIMO + 1)


@roteador.get("/cadastro/funcionais/importacao/modelo", response_class=Response, summary="Modelo da carga de dados funcionais",
              description="Planilha com todos os servidores ativos e os valores atuais dos dados funcionais, mais uma aba de instruções. Só CGP.",
              responses={200: {"content": {XLSX: {}}}, **SEM_PERMISSAO})
def modelo_importacao_funcionais(sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        conteudo = importacao_funcionais.modelo(sessao, autor)
    return Response(conteudo, media_type=XLSX, headers={"Content-Disposition": 'attachment; filename="dados-funcionais-rh.xlsx"'})


@roteador.post("/cadastro/funcionais/importacao/previa", response_model=ResultadoImportacaoRh, summary="Prévia da carga de dados funcionais",
               description="`multipart/form-data` com a planilha em `arquivo`. Confere sem gravar: por linha, o que muda e os erros. "
                           "Célula vazia mantém o valor atual. Só CGP.", responses={**SEM_PERMISSAO, **INVALIDO})
async def previa_importacao_funcionais(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao),
                                       autor: Usuario = Depends(obter_usuario_atual)) -> ResultadoImportacaoRh:
    conteudo = await _planilha(arquivo)
    with _traduzir():
        cadastro.exigir_cgp(sessao, autor)
        return _resultado_importacao(importacao_funcionais.conferir(sessao, conteudo), gravado=False)


@roteador.post("/cadastro/funcionais/importacao", response_model=ResultadoImportacaoRh, summary="Importar a carga de dados funcionais",
               description="Mesma planilha da prévia. Confere de novo e, **sem nenhum erro**, grava tudo numa transação (dados funcionais e "
                           "dias disponíveis do período vigente). Com erro, nada é gravado (`400`). Auditado como "
                           "`rh.cadastro.funcionais_lote`. Só CGP.", responses={**SEM_PERMISSAO, **INVALIDO})
async def importar_funcionais(arquivo: UploadFile = File(..., description="Planilha .xlsx"), sessao: Session = Depends(obter_sessao),
                              autor: Usuario = Depends(obter_usuario_atual)) -> ResultadoImportacaoRh:
    conteudo = await _planilha(arquivo)
    with _traduzir():
        return _resultado_importacao(importacao_funcionais.importar(sessao, conteudo, autor), gravado=True)


@roteador.post("/cadastro/alteracoes/validar-lote", response_model=ResultadoValidacaoLote, summary="Validar alterações em lote",
               description="Valida várias alterações de uma vez. As que não puderem ser validadas (já analisadas, superior em ciclo) "
                           "voltam em `erros`, sem impedir as demais. Só CGP.", responses={**SEM_PERMISSAO})
def validar_lote(dados: ValidacaoLote, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> ResultadoValidacaoLote:
    with _traduzir():
        validadas, erros = cadastro.validar_lote(sessao, dados.ids, autor)
    return ResultadoValidacaoLote(validadas=len(validadas), erros=[ErroLote(id=i, detalhe=d) for i, d in erros])


@roteador.post("/cadastro/alteracoes/{alteracao_id}/validar", response_model=CadastroRh, summary="Validar alteração",
               description="O valor proposto passa a valer e o campo mostra \"Validado por … em …\". Só CGP.",
               responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Alteração")})
def validar_alteracao(alteracao_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> CadastroRh:
    with _traduzir():
        a = cadastro.validar(sessao, alteracao_id, autor)
        return _cadastro(sessao, _usuario(sessao, a.usuario_id))


@roteador.post("/cadastro/alteracoes/{alteracao_id}/recusar", response_model=CadastroRh, summary="Recusar alteração com correção",
               description="Justificativa obrigatória; o `valor_corrigido` passa a valer e o usuário recebe um e-mail. Só CGP.",
               responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Alteração")})
def recusar_alteracao(alteracao_id: uuid.UUID, dados: Recusa, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(obter_usuario_atual)) -> CadastroRh:
    with _traduzir():
        a = cadastro.recusar(sessao, alteracao_id, dados.justificativa, dados.valor_corrigido, autor)
        return _cadastro(sessao, _usuario(sessao, a.usuario_id))


@roteador.put("/cadastro/usuarios/{usuario_id}/funcionais", response_model=CadastroRh, summary="Gravar dados funcionais",
              description="Autorizador de férias/LP (sugestão: o superior imediato), substituto, topo da hierarquia, exercício e saldos. "
              "Invisíveis ao usuário. Só CGP.", responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Usuário")})
def gravar_funcionais(usuario_id: int, dados: GravacaoDadosFuncionais, sessao: Session = Depends(obter_sessao),
                      autor: Usuario = Depends(obter_usuario_atual)) -> CadastroRh:
    with _traduzir():
        cadastro.salvar_funcionais(sessao, usuario_id, dados.model_dump(), autor)
        return _cadastro(sessao, _usuario(sessao, usuario_id))


@roteador.put("/cadastro/usuarios/{usuario_id}/periodo-vigente", response_model=CadastroRh, summary="Ajustar o período aquisitivo vigente",
              description="Altera os dias creditados no período aquisitivo vigente (ex.: férias já gozadas antes do sistema). Só CGP.",
              responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Usuário")})
def ajustar_periodo(usuario_id: int, dados: AjustePeriodo, sessao: Session = Depends(obter_sessao),
                    autor: Usuario = Depends(obter_usuario_atual)) -> CadastroRh:
    with _traduzir():
        cadastro.ajustar_periodo_vigente(sessao, usuario_id, dados.dias_creditados, autor)
        return _cadastro(sessao, _usuario(sessao, usuario_id))


# --- Feriados e pontos facultativos ------------------------------------------------------------

@roteador.get("/feriados", response_model=list[FeriadoLeitura], summary="Feriados e pontos facultativos do ano",
              description="Todos os usuários leem. Em ordem de data.")
def listar_feriados(ano: int = Query(..., ge=2000, le=2100), sessao: Session = Depends(obter_sessao),
                    _: Usuario = Depends(obter_usuario_atual)) -> list[FeriadoLeitura]:
    return [FeriadoLeitura.model_validate(f, from_attributes=True) for f in servico_feriados.listar(sessao, ano)]


@roteador.post("/feriados", response_model=FeriadoLeitura, status_code=status.HTTP_201_CREATED, summary="Cadastrar feriado ou ponto facultativo",
               description="Só CGP. Uma data só pode ter um cadastro (`409 conflito`). Auditado como `rh.feriados.criar`.",
               responses={**SEM_PERMISSAO, **CONFLITO})
def criar_feriado(dados: GravacaoFeriado, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> FeriadoLeitura:
    with _traduzir():
        f = servico_feriados.criar(sessao, dados.model_dump(), autor)
    return FeriadoLeitura.model_validate(f, from_attributes=True)


@roteador.put("/feriados/{feriado_id}", response_model=FeriadoLeitura, summary="Alterar feriado ou ponto facultativo",
              description="Só CGP. Auditado como `rh.feriados.alterar`.",
              responses={**SEM_PERMISSAO, **CONFLITO, **resposta_nao_encontrado("Feriado")})
def alterar_feriado(feriado_id: uuid.UUID, dados: GravacaoFeriado, sessao: Session = Depends(obter_sessao),
                    autor: Usuario = Depends(obter_usuario_atual)) -> FeriadoLeitura:
    with _traduzir():
        f = servico_feriados.alterar(sessao, feriado_id, dados.model_dump(), autor)
    return FeriadoLeitura.model_validate(f, from_attributes=True)


@roteador.delete("/feriados/{feriado_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir feriado ou ponto facultativo",
                 description="Só CGP. Auditado como `rh.feriados.excluir`.", responses={**SEM_PERMISSAO, **resposta_nao_encontrado("Feriado")})
def excluir_feriado(feriado_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        servico_feriados.excluir(sessao, feriado_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Relatório de saldos -----------------------------------------------------------------------

@roteador.get("/relatorios/saldos", response_class=Response, summary="Relatório de saldos de férias e licença-prêmio (CGP)",
              description="Uma linha por servidor ativo: setor, autorizador, período aquisitivo vigente (creditados, agendados, "
                          "disponíveis, fim, data-limite para pedir) e licença-prêmio do ano. Quem não tem o início do período aquisitivo "
                          "aparece como \"não informado\". XLSX ou PDF. Só CGP.",
              responses={200: {"content": {"application/pdf": {}, XLSX: {}}}, **SEM_PERMISSAO})
def relatorio_de_saldos(formato: Literal["pdf", "xlsx"] = "xlsx", sessao: Session = Depends(obter_sessao),
                        autor: Usuario = Depends(obter_usuario_atual)) -> Response:
    with _traduzir():
        conteudo, nome, midia = relatorio_saldos.gerar(sessao, autor, formato, afastamentos.hoje())
    return Response(conteudo, media_type=midia, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# --- Folha de ponto -----------------------------------------------------------------------------

MESES_ANTERIORES_FOLHA, MESES_SEGUINTES_FOLHA = 12, 2


def _competencias_folha() -> list[tuple[int, int]]:
    """Do mês atual (São Paulo) 12 meses para trás e 2 para frente, do mais recente ao mais antigo."""
    hoje = afastamentos.hoje()
    base = hoje.year * 12 + hoje.month - 1
    return [(n // 12, n % 12 + 1) for n in range(base + MESES_SEGUINTES_FOLHA, base - MESES_ANTERIORES_FOLHA - 1, -1)]


@roteador.get("/folha-ponto/competencias", response_model=list[CompetenciaFolha], summary="Competências da folha de ponto",
              description="Meses que o usuário pode gerar: do mês atual 12 para trás e 2 para frente (mais recente primeiro).")
def competencias_folha(_: Usuario = Depends(obter_usuario_atual)) -> list[CompetenciaFolha]:
    hoje = afastamentos.hoje()
    return [CompetenciaFolha(valor=f"{a}-{m:02d}", rotulo=folha_ponto.rotulo_competencia(a, m).capitalize(),
                             atual=(a, m) == (hoje.year, hoje.month)) for a, m in _competencias_folha()]


@roteador.get("/folha-ponto", response_class=Response, summary="Gerar a folha de ponto (PDF)",
              description="Folha de ponto do próprio usuário na competência `AAAA-MM`: cabeçalho com o setor, identificação "
                          "(dados funcionais da CGP), uma linha por dia com sábados, domingos, feriados, pontos facultativos e "
                          "férias/licença-prêmio aprovadas ou gozadas; verso com a consolidação. Exige os dados funcionais preenchidos "
                          "e nenhuma alteração de cadastro aguardando validação: senão `409` (`folha_dados_incompletos` ou "
                          "`folha_cadastro_pendente`) e a CGP recebe aviso com e-mail (um por motivo e por dia).",
              responses={200: {"content": {"application/pdf": {}}}, **INVALIDO,
                         status.HTTP_409_CONFLICT: {"description": "Dados funcionais incompletos ou cadastro aguardando validação."}})
def gerar_folha_ponto(competencia: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="`AAAA-MM`."),
                      sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    ano, mes = int(competencia[:4]), int(competencia[5:])
    if (ano, mes) not in _competencias_folha():
        raise ErroApi(status.HTTP_400_BAD_REQUEST, "Competência fora do período disponível (últimos 12 meses e próximos 2).", "invalido")
    try:
        folha_ponto.verificar(sessao, usuario, afastamentos.hoje())
    except folha_ponto.FolhaBloqueada as erro:
        raise ErroApi(status.HTTP_409_CONFLICT, str(erro), erro.codigo) from erro
    conteudo = folha_ponto.gerar(sessao, usuario, ano, mes)
    auditar(sessao, usuario.login, "rh.folha_ponto", competencia, autor_id=usuario.id, alvo_tipo="usuario", alvo_id=str(usuario.id))
    sessao.commit()
    nome = f"folha-ponto-{competencia}-{usuario.login}.pdf"
    return Response(conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# --- Parâmetros ---------------------------------------------------------------------------------

@roteador.get("/parametros", response_model=ParametrosLeitura, summary="Regras de agendamento",
              description="Parâmetros de férias e licença-prêmio em vigor (todos podem ler).")
def ler_parametros(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(obter_usuario_atual)) -> ParametrosLeitura:
    p = afastamentos.parametros(sessao)
    sessao.commit()
    return _parametros_leitura(sessao, p)


def _parametros_leitura(sessao: Session, p) -> ParametrosLeitura:
    """Parâmetros com a quantidade de pessoas da CGP (a tela alerta quando ninguém recebe os avisos da CGP)."""
    return ParametrosLeitura.model_validate(p, from_attributes=True).model_copy(update={"membros_cgp": len(usuarios_cgp(sessao))})


@roteador.put("/parametros", response_model=ParametrosLeitura, summary="Alterar regras de agendamento",
              description="Só CGP. Valem para os próximos pedidos e alterações.", responses={**SEM_PERMISSAO})
def gravar_parametros(dados: GravacaoParametros, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> ParametrosLeitura:
    with _traduzir():
        p = afastamentos.salvar_parametros(sessao, dados.model_dump(), autor)
    return _parametros_leitura(sessao, p)


# --- Afastamentos -------------------------------------------------------------------------------

def _afastamento(sessao: Session, a: Afastamento, usuario: Usuario | None, autor: Usuario, pode_decidir: bool = False,
                 eventos: bool = False) -> AfastamentoLeitura:
    prazo = afastamentos.parametros(sessao).prazo_cancelamento_dias
    no_prazo = (a.inicio - afastamentos.hoje()).days >= prazo
    return AfastamentoLeitura(
        id=a.id, usuario_id=a.usuario_id, nome=_nome(usuario), setor=setor_do_usuario(usuario) if usuario else "—", tipo=a.tipo,
        inicio=a.inicio, fim=a.fim, dias=a.dias, exercicio=a.exercicio, status=a.status, solicitado_em=a.solicitado_em,
        decidido_por_nome=a.decidido_por_nome, decidido_em=a.decidido_em, justificativa=a.justificativa, substitui_id=a.substitui_id,
        aguarda_ciencia=a.aguarda_ciencia, ciencia_por_nome=a.ciencia_por_nome, ciencia_em=a.ciencia_em,
        pode_dar_ciencia=afastamentos.pode_dar_ciencia(sessao, autor, a, usuario), pode_decidir=pode_decidir, pode_alterar=a.status in ("pendente", "aprovado") and a.usuario_id == autor.id and no_prazo,
        eventos=[EventoLeitura(de=e.de, para=e.para, autor_nome=e.autor_nome, justificativa=e.justificativa, ocorrido_em=e.ocorrido_em)
                 for e in a.eventos] if eventos else [],
    )


@roteador.get("/afastamentos/meus", response_model=MeusAfastamentos, summary="Minhas férias e licenças-prêmio",
              description="Saldos do exercício (ano civil), pedidos com histórico de status e as regras em vigor.")
def meus_afastamentos(exercicio: int | None = Query(None, ge=2000, le=2100), sessao: Session = Depends(obter_sessao),
                      usuario: Usuario = Depends(obter_usuario_atual)) -> MeusAfastamentos:
    ano = exercicio or afastamentos.hoje().year
    saldos, lista = afastamentos.meus(sessao, usuario, ano)
    p = afastamentos.parametros(sessao)
    hoje = afastamentos.hoje()
    periodo = servico_periodos.vigente(sessao, usuario.id, hoje)
    atual = proximo = None
    if periodo:
        s_atual = servico_periodos.situacao(sessao, periodo, hoje)
        atual = PeriodoAtual(exercicio=servico_periodos.exercicio_do_periodo(periodo.inicio, periodo.fim), inicio=periodo.inicio, fim=periodo.fim, dias_creditados=periodo.dias_creditados, usado=s_atual.usado,
                             disponivel=s_atual.disponivel, expira_em_dias=s_atual.expira_em_dias, data_limite_inicio=s_atual.data_limite_inicio,
                             data_limite_pedido=s_atual.data_limite_pedido, alerta_expiracao=s_atual.em_alerta)
        p_inicio, p_fim, creditados, _ = afastamentos.periodo_do_pedido(sessao, usuario.id, periodo.fim + timedelta(days=1))
        proximo = ProximoPeriodo(exercicio=servico_periodos.exercicio_do_periodo(p_inicio, p_fim), inicio=p_inicio, fim=p_fim, dias_creditados_previstos=creditados,
                                 usado=servico_periodos.usado(sessao, usuario.id, p_inicio, p_fim))
    sessao.commit()
    return MeusAfastamentos(
        exercicio=ano, saldos={t: SaldoLeitura(saldo=s.saldo, usado=s.usado, disponivel=s.disponivel) for t, s in saldos.items()},
        periodo_vigente=atual, proximo_periodo=proximo, agendamento_antecipado=afastamentos.agendamento_antecipado(sessao, usuario.id),
        afastamentos=[_afastamento(sessao, a, usuario, usuario, eventos=True) for a in lista],
        parametros=ParametrosLeitura.model_validate(p, from_attributes=True),
        feriados=_feriados(sessao, date(ano, 1, 1), date(ano, 12, 31)),
    )


def _feriados(sessao: Session, inicio, fim) -> list[FeriadoLeitura]:
    """Feriados e pontos facultativos entre as datas, em ordem."""
    return [FeriadoLeitura.model_validate(f, from_attributes=True) for _, f in sorted(servico_feriados.no_intervalo(sessao, inicio, fim).items())]


@roteador.post("/afastamentos/lancamento", response_model=AfastamentoLeitura, status_code=status.HTTP_201_CREATED,
               summary="Lançar afastamento em nome do servidor (CGP)",
               description="Férias ou licença-prêmio já combinadas ou gozadas fora do sistema, inclusive retroativas. Sem antecedência, "
                           "dia vedado nem mínimo de dias; valem a sobreposição e o saldo (que pode ser ignorado com `ignorar_saldo`). "
                           "Nasce aprovado ou gozado, e o servidor recebe e-mail. Auditado como `rh.afastamento.lancar`. Só CGP.",
               responses={**SEM_PERMISSAO, **INVALIDO, **resposta_nao_encontrado("Usuário")})
def lancar_afastamento(dados: LancamentoAfastamento, sessao: Session = Depends(obter_sessao),
                       autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.lancar(sessao, autor, dados.usuario_id, dados.tipo, dados.inicio, dados.fim, dados.situacao,
                                dados.justificativa.strip(), dados.ignorar_saldo)
        dono = _usuario(sessao, a.usuario_id)
    return _afastamento(sessao, a, dono, autor, eventos=True)


@roteador.post("/afastamentos", response_model=AfastamentoLeitura, status_code=status.HTTP_201_CREATED, summary="Agendar férias ou licença-prêmio",
               description="Valida as regras da CGP (mínimo de dias, início vedado, antecedência, exercício, saldo do tipo, sobreposição e "
               "emenda). Em duas etapas: o superior imediato recebe o pedido para o ciente e de acordo; só depois o autorizador (ou substituto) e a CGP "
               "recebem e-mail para aprovar. Sem superior, ou se ele for o próprio aprovador, vai direto à aprovação.", responses={**INVALIDO})
def agendar(dados: PedidoAfastamento, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.agendar(sessao, usuario, dados.tipo, dados.inicio, dados.fim)
    return _afastamento(sessao, a, usuario, usuario, eventos=True)


@roteador.put("/afastamentos/{afastamento_id}", response_model=AfastamentoLeitura, summary="Alterar pedido",
              description="Pendente: muda o próprio pedido. Aprovado: cria um novo pedido pendente, que cancela o anterior ao ser aprovado. "
              "Até o prazo da CGP (a CGP pode a qualquer momento).",
              responses={**INVALIDO, **SEM_PERMISSAO, **resposta_nao_encontrado("Afastamento")})
def alterar(afastamento_id: uuid.UUID, dados: PedidoAfastamento, sessao: Session = Depends(obter_sessao),
            autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.alterar(sessao, autor, afastamento_id, dados.tipo, dados.inicio, dados.fim)
    return _afastamento(sessao, a, sessao.get(Usuario, a.usuario_id), autor, eventos=True)


@roteador.post("/afastamentos/{afastamento_id}/cancelar", response_model=AfastamentoLeitura, summary="Cancelar pedido",
               description="Pendente ou aprovado, até o prazo da CGP (a CGP pode a qualquer momento).",
               responses={**INVALIDO, **SEM_PERMISSAO, **resposta_nao_encontrado("Afastamento")})
def cancelar(afastamento_id: uuid.UUID, dados: Decisao, sessao: Session = Depends(obter_sessao),
             autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.cancelar(sessao, autor, afastamento_id, dados.justificativa)
    return _afastamento(sessao, a, sessao.get(Usuario, a.usuario_id), autor, eventos=True)


@roteador.post("/afastamentos/{afastamento_id}/ciencia", response_model=AfastamentoLeitura, summary="Ciente e de acordo do superior imediato",
               description="Etapa 1: só o superior imediato do solicitante. Não aprova o pedido: registra a ciência, avisa o solicitante por e-mail e "
               "libera o pedido para o aprovador. `400` se o pedido não aguarda ciência.",
               responses={**INVALIDO, **SEM_PERMISSAO, **resposta_nao_encontrado("Afastamento")})
def dar_ciencia(afastamento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.dar_ciencia(sessao, autor, afastamento_id)
    return _afastamento(sessao, a, sessao.get(Usuario, a.usuario_id), autor, eventos=True)


@roteador.post("/afastamentos/{afastamento_id}/aprovar", response_model=AfastamentoLeitura, summary="Aprovar pedido",
               description="Etapa 2: autorizador, substituto (com o autorizador afastado) ou CGP, depois do ciente do superior imediato (`409 aguarda_ciencia` antes "
               "disso, exceto para a CGP). O usuário recebe e-mail.",
               responses={**INVALIDO, **SEM_PERMISSAO, **resposta_nao_encontrado("Afastamento")})
def aprovar(afastamento_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.decidir(sessao, autor, afastamento_id, True, None)
    return _afastamento(sessao, a, sessao.get(Usuario, a.usuario_id), autor, eventos=True)


@roteador.post("/afastamentos/{afastamento_id}/recusar", response_model=AfastamentoLeitura, summary="Recusar pedido",
               description="Justificativa obrigatória. Quem pode: o autorizador, o substituto ou a CGP; na etapa 1, também o superior imediato. O usuário recebe e-mail com a justificativa.",
               responses={**INVALIDO, **SEM_PERMISSAO, **resposta_nao_encontrado("Afastamento")})
def recusar(afastamento_id: uuid.UUID, dados: Decisao, sessao: Session = Depends(obter_sessao),
            autor: Usuario = Depends(obter_usuario_atual)) -> AfastamentoLeitura:
    with _traduzir():
        a = afastamentos.decidir(sessao, autor, afastamento_id, False, dados.justificativa)
    return _afastamento(sessao, a, sessao.get(Usuario, a.usuario_id), autor, eventos=True)


@roteador.get("/afastamentos/aprovacoes", response_model=list[AfastamentoLeitura], summary="Aguardando minha aprovação",
              description="Pedidos pendentes que o usuário pode decidir ou aos quais pode dar o ciente e de acordo (`pode_dar_ciencia`); CGP: todos.")
def listar_aprovacoes(sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> list[AfastamentoLeitura]:
    return [_afastamento(sessao, a, u, autor, pode_decidir=afastamentos.pode_decidir(sessao, autor, a)) for a, u in afastamentos.aprovacoes(sessao, autor)]


Visao = Literal["mensal", "anual"]


@roteador.get("/afastamentos/painel", response_model=PainelAfastamentos, summary="Painel de férias e licenças-prêmio",
              description="Pendentes, aprovados e gozados na janela (mês ou ano), com filtros por pessoa, setor (inclui os filhos) e tipo, e "
              "alertas de setor. Escopo: CGP vê todos; autorizador vê os autorizados e a si mesmo; os demais, só a si.")
def painel(visao: Visao = "mensal", ano: int = Query(..., ge=2000, le=2100), mes: int | None = Query(None, ge=1, le=12),
           pessoa_id: int | None = None, setor_id: int | None = None, tipo: Literal["ferias", "licenca_premio"] | None = None,
           sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)) -> PainelAfastamentos:
    dados = afastamentos.painel(sessao, autor, visao, ano, mes, pessoa_id, setor_id, tipo)
    return PainelAfastamentos(
        visao=visao, inicio=dados["inicio"], fim=dados["fim"], cgp=dados["cgp"],
        periodos=[_afastamento(sessao, a, u, autor, pode_decidir=p) for a, u, p in dados["periodos"]],
        alertas=[AlertaSetor(**x) for x in dados["alertas"]],
        pessoas=[OpcaoPessoa(id=u.id, nome=_nome(u), setor=setor_do_usuario(u)) for u in dados["pessoas"]],
        setores=[OpcaoSetor(id=o.id, nome=o.nome, nivel=o.nivel) for o in servico_setores.opcoes_departamento(sessao)],
        ferias_a_vencer=_ferias_a_vencer(sessao, autor),
        feriados=_feriados(sessao, dados["inicio"], dados["fim"]),
    )


def _ferias_a_vencer(sessao: Session, autor: Usuario) -> list[FeriasAVencer]:
    """Quem tem saldo de férias não agendado e período terminando em até 90 dias (escopo do painel)."""
    cgp, visiveis = afastamentos.escopo(sessao, autor)
    if not cgp and visiveis == [autor.id]:
        return []
    lista = servico_periodos.a_vencer(sessao, None if cgp else visiveis, afastamentos.hoje())
    sessao.commit()
    return [FeriasAVencer(usuario_id=u.id, nome=_nome(u), setor=setor_do_usuario(u), periodo_inicio=s.periodo.inicio, periodo_fim=s.periodo.fim,
                          disponivel=s.disponivel, data_limite_pedido=s.data_limite_pedido) for u, s in lista]


@roteador.get("/afastamentos/painel/exportar", response_class=Response, summary="Exportar o painel (PDF ou XLSX)",
              description="Mesmos filtros do painel. XLSX: lista de períodos e grade por dia; PDF: lista e alertas de setor.",
              responses={200: {"content": {"application/pdf": {}, XLSX: {}}}})
def exportar(formato: Literal["pdf", "xlsx"] = "pdf", visao: Visao = "mensal", ano: int = Query(..., ge=2000, le=2100),
             mes: int | None = Query(None, ge=1, le=12), pessoa_id: int | None = None, setor_id: int | None = None,
             tipo: Literal["ferias", "licenca_premio"] | None = None, sessao: Session = Depends(obter_sessao),
             autor: Usuario = Depends(obter_usuario_atual)) -> Response:
    conteudo, nome, midia = afastamentos.exportar(sessao, autor, formato, visao, ano, mes, pessoa_id, setor_id, tipo)
    return Response(conteudo, media_type=midia, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
