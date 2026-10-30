# Criado por José Eduardo Santana Martins
# Este arquivo serve para descobrir a competência atual de um contrato (a mais antiga ainda não concluída) e as etapas abertas, para a carteira.
"""Competência atual do contrato para a carteira.

Regra: a **mais antiga** competência regular ou de diferença de reajuste ainda não concluída, a partir do corte dos marcadores (parâmetro de Contratos), sem as medições adicionais. Só usa campos já carregados da competência (não consulta o banco).
"""

from datetime import date

from app.models.contratos import Contrato
from app.schemas.contratos.contratos import CompetenciaAtualCarteira
from app.services.contratos import servico_contratos, servico_parametros




def _entra_nos_marcadores(c) -> bool:
    """Competência regular ou de diferença de reajuste, não concluída, a partir do corte dos marcadores (parâmetro de Contratos) (as medições adicionais ficam de fora)."""
    return c.tipo in ("regular", "diferenca_reajuste") and c.etapa_atual != "concluida" and c.periodo_inicio >= servico_parametros.valor("corte_marcadores_a_partir_de")


def _resumo(c) -> CompetenciaAtualCarteira:
    from app.services.contratos.servico_competencias import etapas_abertas, situacao_competencia
    from app.services.contratos.servico_painel import _medir_desde

    situacao = situacao_competencia(c)
    etapas = ["medicao"] if situacao in ("pendente", "disponivel") else etapas_abertas(c)
    atrasada = c.medicao_concluida_em is None and (servico_contratos.hoje() - _medir_desde(c)).days > servico_parametros.valor("dias_atraso")
    return CompetenciaAtualCarteira(identificador=c.identificador, rotulo=c.numero_competencia, situacao=situacao, etapas=etapas, atrasada=atrasada)


def competencias_em_andamento(contrato: Contrato) -> list[CompetenciaAtualCarteira]:
    """Todas as competências **já iniciadas** (medição iniciada ou etapa além da medição), da mais antiga à mais nova, a partir do corte dos marcadores (parâmetro de Contratos).

    Cada uma vira uma linha de marcador na carteira: `(MM/AAAA - etapa)`."""
    from app.services.contratos.servico_competencias import situacao_competencia

    candidatas = sorted((c for c in contrato.competencias if _entra_nos_marcadores(c)), key=lambda c: (c.periodo_inicio, c.tipo, c.numero_adicional))
    return [_resumo(c) for c in candidatas if situacao_competencia(c) == "em_andamento"]


def competencia_atual(contrato: Contrato) -> CompetenciaAtualCarteira | None:
    """`None` quando não há competência em aberto (execução não gerada ou tudo concluído)."""
    candidatas = sorted((c for c in contrato.competencias if _entra_nos_marcadores(c)), key=lambda c: (c.periodo_inicio, c.tipo, c.numero_adicional))
    return _resumo(candidatas[0]) if candidatas else None
