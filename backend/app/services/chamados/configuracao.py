# Criado por José Eduardo Santana Martins
# Este arquivo serve para os Parâmetros do marco 3 dos Chamados: Geral, status e sub-status, setores de atendimento e recorrentes.
"""Parâmetros do marco 3.

- **Geral**: dias para dizer "Não resolveu", se o ponto facultativo do RH conta como dia útil e os limites de cor do prazo
  (padrão 50% âmbar, 75% laranja, 90% vermelho; decisão do usuário).
- **Status**: os cinco status-base ficam no código (as regras dependem deles); aqui só o nome exibido e a cor de cada um, e os
  sub-status dentro deles (ex.: "Em atendimento › Aguardando peça"). As cores são os tokens de status do DESIGN.md.
- **Setores de atendimento**: o ajuste "vê todos os chamados" de cada setor (qualquer setor ativo pode atender, sem cadastro).
- **Recorrentes**: chamado aberto sozinho a cada período, gerado pela tarefa automática `minuto`.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as hora, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO
from app.models.chamados import (
    CORES_STATUS, STATUS_BASE, UNIDADES_RECORRENCIA, CategoriaChamados, RecorrenteChamados, SetorAtendimentoChamados, StatusApresentacaoChamados,
    SubstatusChamados,
)
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.chamados import parametros
from app.services.chamados.parametros import ErroParametro

# Nome e cor padrão de cada status-base (valem enquanto ninguém mudar nos Parâmetros)
PADRAO_STATUS: dict[str, tuple[str, str]] = {
    "novo": ("Novo", "info"),
    "em_atendimento": ("Em atendimento", "info"),
    "pendente": ("Pendente", "alerta"),
    "em_aprovacao": ("Em aprovação", "info"),
    "solucionado": ("Resolvido", "sucesso"),
}
PADROES_GERAL = {"limite_alerta": "50", "limite_atencao": "75", "limite_perigo": "90"}
parametros.PADROES.update(PADROES_GERAL)


# ---------------------------------------------------------------------------------------------
# Geral
# ---------------------------------------------------------------------------------------------

@dataclass
class Geral:
    dias_reabrir: int
    ponto_facultativo_util: bool
    limite_alerta: int
    limite_atencao: int
    limite_perigo: int
    # A partir desta data (São Paulo) todos abrem chamado no SGI; antes, só quem tem Controle total (testes). Nula = sem data marcada.
    inicio_atendimento: date | None = None


def geral(sessao: Session) -> Geral:
    return Geral(
        dias_reabrir=parametros.obter_inteiro(sessao, "dias_reabrir"),
        ponto_facultativo_util=parametros.obter(sessao, "sla_ponto_facultativo_util") == "sim",
        limite_alerta=parametros.obter_inteiro(sessao, "limite_alerta"),
        limite_atencao=parametros.obter_inteiro(sessao, "limite_atencao"),
        limite_perigo=parametros.obter_inteiro(sessao, "limite_perigo"),
        inicio_atendimento=inicio_atendimento(sessao),
    )


parametros.PADROES.setdefault("inicio_atendimento", "")


def inicio_atendimento(sessao: Session) -> date | None:
    """Data em que o SGI passa a receber os chamados de todos (antes: GLPI). Nula = ainda não marcada."""
    try:
        valor = parametros.obter(sessao, "inicio_atendimento")
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def atendimento_aberto(sessao: Session) -> bool:
    """O SGI já recebe os chamados de todos? (a data chegou)."""
    from app.core.banco import hoje_sao_paulo

    inicio = inicio_atendimento(sessao)
    return inicio is not None and hoje_sao_paulo() >= inicio


def salvar_geral(sessao: Session, dados: Geral) -> Geral:
    if not 1 <= dados.dias_reabrir <= 30:
        raise ErroParametro("Os dias para reabrir vão de 1 a 30.")
    if not 0 < dados.limite_alerta < dados.limite_atencao < dados.limite_perigo <= 100:
        raise ErroParametro("Os limites precisam crescer: alerta < atenção < perigo, até 100%.")
    parametros.gravar(sessao, "dias_reabrir", str(dados.dias_reabrir))
    parametros.gravar(sessao, "sla_ponto_facultativo_util", "sim" if dados.ponto_facultativo_util else "nao")
    for chave in ("limite_alerta", "limite_atencao", "limite_perigo"):
        parametros.gravar(sessao, chave, str(getattr(dados, chave)))
    parametros.gravar(sessao, "inicio_atendimento", dados.inicio_atendimento.isoformat() if dados.inicio_atendimento else "")
    sessao.flush()
    return geral(sessao)


def nivel_do_prazo(percentual: int | None, estourado: bool, cumprido: bool, tem_prazo: bool, limites: Geral) -> str:
    """Cor do prazo: cumprido = verde (vermelho se foi com atraso); senão pela parte consumida (alerta, atenção, perigo)."""
    if not tem_prazo:
        return "sem"
    if cumprido:
        return "perigo" if estourado else "cumprido"
    if estourado:
        return "perigo"
    p = percentual or 0
    if p >= limites.limite_perigo:
        return "perigo"
    if p >= limites.limite_atencao:
        return "atencao"
    if p >= limites.limite_alerta:
        return "alerta"
    return "ok"


# ---------------------------------------------------------------------------------------------
# Status e sub-status
# ---------------------------------------------------------------------------------------------

def apresentacao(sessao: Session) -> dict[str, tuple[str, str]]:
    """{status_base: (nome, cor)} com o que os Parâmetros mudaram por cima do padrão."""
    nomes = dict(PADRAO_STATUS)
    for linha in sessao.scalars(select(StatusApresentacaoChamados)):
        nomes[linha.status_base] = (linha.nome, linha.cor)
    return nomes


def salvar_apresentacao(sessao: Session, status_base: str, nome: str, cor: str) -> None:
    if status_base not in STATUS_BASE:
        raise ErroParametro("Status inexistente.", 404, "nao_encontrado")
    if not nome.strip() or cor not in CORES_STATUS:
        raise ErroParametro("Informe o nome e uma cor válida.")
    linha = sessao.get(StatusApresentacaoChamados, status_base)
    if linha is None:
        sessao.add(StatusApresentacaoChamados(status_base=status_base, nome=nome.strip()[:60], cor=cor))
    else:
        linha.nome, linha.cor = nome.strip()[:60], cor
    sessao.flush()


def listar_substatus(sessao: Session) -> list[SubstatusChamados]:
    return list(sessao.scalars(select(SubstatusChamados).order_by(SubstatusChamados.status_base, SubstatusChamados.ordem, SubstatusChamados.nome)))


def salvar_substatus(sessao: Session, substatus_id: uuid.UUID | None, status_base: str, nome: str, cor: str, ordem: int, ativo: bool) -> SubstatusChamados:
    if status_base not in STATUS_BASE:
        raise ErroParametro("Status-base inexistente.")
    if not nome.strip() or cor not in CORES_STATUS:
        raise ErroParametro("Informe o nome e uma cor válida.")
    item = sessao.get(SubstatusChamados, substatus_id) if substatus_id else SubstatusChamados()
    if item is None:
        raise ErroParametro("Sub-status não encontrado.", 404, "nao_encontrado")
    item.status_base, item.nome, item.cor, item.ordem, item.ativo = status_base, nome.strip()[:60], cor, ordem, ativo
    if substatus_id is None:
        sessao.add(item)
    sessao.flush()
    return item


def excluir_substatus(sessao: Session, substatus_id: uuid.UUID) -> None:
    """Exclui o sub-status (os chamados que estavam nele ficam só com o status-base: a coluna é SET NULL)."""
    item = sessao.get(SubstatusChamados, substatus_id)
    if item is None:
        raise ErroParametro("Sub-status não encontrado.", 404, "nao_encontrado")
    sessao.delete(item)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Setores de atendimento
# ---------------------------------------------------------------------------------------------

def setores_atendimento(sessao: Session) -> list[tuple[Setor, str, bool]]:
    """Todos os setores ativos (qualquer um pode atender) com o ajuste "vê todos os chamados"."""
    ajustes = {a.setor_id: a.ve_todos for a in sessao.scalars(select(SetorAtendimentoChamados))}
    return [(s, caminho, ajustes.get(s.id, False)) for s, caminho in parametros.setores_ativos(sessao)]


def salvar_setor_atendimento(sessao: Session, setor_id: int, ve_todos: bool) -> None:
    setor = sessao.get(Setor, setor_id)
    if setor is None or not setor.ativo:
        raise ErroParametro("Setor não encontrado.", 404, "nao_encontrado")
    linha = sessao.get(SetorAtendimentoChamados, setor_id)
    if linha is None:
        sessao.add(SetorAtendimentoChamados(setor_id=setor_id, ve_todos=ve_todos))
    else:
        linha.ve_todos = ve_todos
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Recorrentes
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosRecorrente:
    nome: str
    categoria_id: uuid.UUID
    titulo: str
    descricao: str
    periodicidade_quantidade: int
    periodicidade_unidade: str
    antecedencia_min: int
    so_dias_uteis: bool
    proxima_em: datetime
    fim_em: datetime | None
    ativo: bool
    solicitante_id: int | None = None


def listar_recorrentes(sessao: Session) -> list[RecorrenteChamados]:
    return list(sessao.scalars(select(RecorrenteChamados).order_by(RecorrenteChamados.nome)))


def salvar_recorrente(sessao: Session, recorrente_id: uuid.UUID | None, dados: DadosRecorrente, autor: Usuario) -> RecorrenteChamados:
    if not dados.nome.strip() or not 3 <= len(dados.titulo.strip()) <= 250:
        raise ErroParametro("Informe o nome e um título de 3 a 250 caracteres.")
    if dados.periodicidade_unidade not in UNIDADES_RECORRENCIA or dados.periodicidade_quantidade <= 0:
        raise ErroParametro("Periodicidade inválida.")
    if dados.antecedencia_min < 0 or dados.antecedencia_min > 7 * 24 * 60:
        raise ErroParametro("A antecedência vai de 0 a 7 dias (em minutos).")
    categoria = sessao.get(CategoriaChamados, dados.categoria_id)
    if categoria is None or not categoria.ativa or parametros.efetiva(categoria).setor_id is None:
        raise ErroParametro("Escolha uma categoria ativa com setor responsável.")
    if dados.fim_em is not None and dados.fim_em <= dados.proxima_em:
        raise ErroParametro("O fim precisa ser depois da próxima ocorrência.")
    item = sessao.get(RecorrenteChamados, recorrente_id) if recorrente_id else RecorrenteChamados(solicitante_id=dados.solicitante_id or autor.id)
    if item is None:
        raise ErroParametro("Recorrente não encontrado.", 404, "nao_encontrado")
    item.nome, item.categoria_id, item.titulo, item.descricao = dados.nome.strip()[:200], categoria.id, dados.titulo.strip(), dados.descricao or ""
    item.periodicidade_quantidade, item.periodicidade_unidade = dados.periodicidade_quantidade, dados.periodicidade_unidade
    item.antecedencia_min, item.so_dias_uteis, item.proxima_em, item.fim_em, item.ativo = (
        dados.antecedencia_min, dados.so_dias_uteis, dados.proxima_em, dados.fim_em, dados.ativo)
    if dados.solicitante_id:
        item.solicitante_id = dados.solicitante_id
    if recorrente_id is None:
        sessao.add(item)
    sessao.flush()
    return item


def excluir_recorrente(sessao: Session, recorrente_id: uuid.UUID) -> None:
    """Exclui o recorrente (os chamados que ele gerou continuam, só perdem o vínculo)."""
    item = sessao.get(RecorrenteChamados, recorrente_id)
    if item is None:
        raise ErroParametro("Recorrente não encontrado.", 404, "nao_encontrado")
    sessao.delete(item)
    sessao.flush()


def _somar_periodo(instante: datetime, quantidade: int, unidade: str) -> datetime:
    """Próxima ocorrência, contada no fuso de São Paulo (mês: mesmo dia, ajustado ao fim de meses curtos)."""
    local = instante.astimezone(FUSO_SAO_PAULO)
    if unidade == "dia":
        novo = local + timedelta(days=quantidade)
    elif unidade == "semana":
        novo = local + timedelta(weeks=quantidade)
    else:
        mes = local.month - 1 + quantidade
        ano, mes = local.year + mes // 12, mes % 12 + 1
        dia = min(local.day, [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1])
        novo = local.replace(year=ano, month=mes, day=dia)
    return datetime.combine(novo.date(), novo.time(), FUSO_SAO_PAULO)


def _para_dia_util(instante: datetime, feriados: set[date]) -> datetime:
    """Se cair em fim de semana ou feriado do RH, vai para o próximo dia útil, no mesmo horário."""
    local = instante.astimezone(FUSO_SAO_PAULO)
    dia = local.date()
    while dia.weekday() >= 5 or dia in feriados:
        dia += timedelta(days=1)
    return datetime.combine(dia, hora(local.hour, local.minute), FUSO_SAO_PAULO)


def proxima_ocorrencia(item: RecorrenteChamados, depois_de: datetime, feriados: set[date]) -> datetime:
    """A ocorrência seguinte à atual, já empurrada para dia útil quando o recorrente pede."""
    proxima = _somar_periodo(item.proxima_em, item.periodicidade_quantidade, item.periodicidade_unidade)
    return _para_dia_util(proxima, feriados) if item.so_dias_uteis else proxima
