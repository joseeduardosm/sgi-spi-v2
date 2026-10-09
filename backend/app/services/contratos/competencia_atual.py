# Criado por José Eduardo Santana Martins
# Este arquivo serve para descobrir a competência atual de um contrato (a mais antiga ainda não concluída) e as etapas abertas, para a carteira.
"""Competência atual do contrato para a carteira.

Regra: a **mais antiga** competência regular ou de diferença de reajuste ainda não concluída, ignorando as anteriores ao corte de cobrança
(`anterior_ao_corte`, a mesma regra das pendências) e as medições adicionais. Só usa campos já carregados da competência (não consulta o banco).
"""

from app.models.contratos import Contrato
from app.schemas.contratos.contratos import CompetenciaAtualCarteira
from app.services.contratos import servico_contratos


def competencia_atual(contrato: Contrato) -> CompetenciaAtualCarteira | None:
    """`None` quando não há competência em aberto (execução não gerada ou tudo concluído)."""
    # Importados aqui para não criar ciclo: estes serviços já importam o de contratos
    from app.services.contratos.servico_competencias import anterior_ao_corte, etapas_abertas, situacao_competencia
    from app.services.contratos.servico_painel import DIAS_ATRASO, _medir_desde

    candidatas = sorted(
        (c for c in contrato.competencias if c.tipo in ("regular", "diferenca_reajuste") and c.etapa_atual != "concluida" and not anterior_ao_corte(c)),
        key=lambda c: (c.periodo_inicio, c.tipo, c.numero_adicional),
    )
    if not candidatas:
        return None
    c = candidatas[0]
    situacao = situacao_competencia(c)
    etapas = ["medicao"] if situacao in ("pendente", "disponivel") else etapas_abertas(c)
    atrasada = c.medicao_concluida_em is None and (servico_contratos.hoje() - _medir_desde(c)).days > DIAS_ATRASO
    return CompetenciaAtualCarteira(identificador=c.identificador, rotulo=c.numero_competencia, situacao=situacao, etapas=etapas, atrasada=atrasada)
