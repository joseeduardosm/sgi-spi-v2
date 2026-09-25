# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar a exportação consolidada da previsão orçamentária com cenários.
"""Exportação consolidada da Previsão Orçamentária (SuperRoot), com cenários em elaboração.

A base é a previsão mensal de cada contrato. Os cenários somam o efeito dos processos ainda não
concluídos: reajustes (diferença de preço a partir do mês de referência), aditamentos e supressões
(diferença de quantidade a partir do mês de efeito) e prorrogações (meses da nova vigência).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contratos import Contrato, ProcessoProrrogacao
from app.models.usuario import Usuario
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import moeda
from app.services.contratos.servico_orcamento import meses_previstos
from app.services.contratos.servico_painel import carregar_contratos
from app.services.contratos.servico_contratos import vigencias
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, Aba, Coluna, gerar_planilha

ZERO = Decimal(0)
CENARIOS = {"reajustes": "Reajustes em elaboração", "aditamentos": "Aditamentos em elaboração",
            "supressoes": "Supressões em elaboração", "prorrogacoes": "Prorrogações em elaboração"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass
class LinhaContrato:
    contrato: Contrato
    base: dict[date, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    cenarios: dict[str, dict[date, Decimal]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(Decimal)))

    def total_mes(self, mes: date, cenarios: set[str]) -> Decimal:
        return self.base[mes] + sum((self.cenarios[c][mes] for c in cenarios), ZERO)


def _meses(exercicio: int) -> list[date]:
    return [date(exercicio, m, 1) for m in range(1, 13)]


def _cenario_reajustes(linha: LinhaContrato, exercicio: int) -> None:
    contrato = linha.contrato
    for reajuste in (r for r in contrato.reajustes if r.situacao == "rascunho"):
        vigencia = next((v for v in vigencias(contrato) if v.sequencia == reajuste.sequencia_vigencia), None)
        if vigencia is None:
            continue
        for mes in calculos.meses_da_vigencia(vigencia):
            if mes.competencia.year != exercicio or mes.competencia < reajuste.mes_referencia:
                continue
            for item in reajuste.itens:
                if item.tipo == "continuo":
                    linha.cenarios["reajustes"][mes.competencia] += item.quantidade_mensal * (item.valor_unitario_reajustado - item.valor_unitario_atual) * mes.fator


def _cenario_alteracoes(linha: LinhaContrato, exercicio: int) -> None:
    contrato = linha.contrato
    for alteracao in (a for a in contrato.alteracoes if a.situacao in ("rascunho", "aguardando_ciencias")):
        chave = "aditamentos" if alteracao.tipo == "aditamento" else "supressoes"
        vigencia = next((v for v in vigencias(contrato) if v.sequencia == alteracao.sequencia_vigencia), None)
        if vigencia is None:
            continue
        for mes in calculos.meses_da_vigencia(vigencia):
            if mes.competencia.year != exercicio or mes.competencia < alteracao.mes_efeito:
                continue
            for item in alteracao.itens:
                if item.tipo == "continuo":
                    linha.cenarios[chave][mes.competencia] += (item.quantidade_nova - item.quantidade_original) * item.valor_unitario * mes.fator


def _cenario_prorrogacoes(sessao: Session, linha: LinhaContrato, exercicio: int) -> None:
    contrato = linha.contrato
    processo = sessao.scalar(select(ProcessoProrrogacao).where(ProcessoProrrogacao.contrato_id == contrato.id, ProcessoProrrogacao.situacao == "rascunho"))
    if processo is None or not processo.meses:
        return
    inicio = contrato.data_fim + timedelta(days=1)
    nova = calculos.Vigencia(0, inicio, calculos.calcular_data_fim(inicio, processo.meses))
    plano = {p["item_id"]: p for p in processo.plano_sob_demanda or []}
    for mes in calculos.meses_da_vigencia(nova):
        if mes.competencia.year != exercicio:
            continue
        for item in contrato.itens:
            preco = valores.preco_em(contrato, item, mes.competencia)
            if item.tipo == "continuo":
                fator = mes.fator if item.calcula_pro_rata else Decimal(1)
                linha.cenarios["prorrogacoes"][mes.competencia] += item.quantidade_mensal * preco * fator
            else:
                quantidade = Decimal(plano.get(str(item.id), {}).get("apontamentos", {}).get(mes.competencia.isoformat(), "0"))
                linha.cenarios["prorrogacoes"][mes.competencia] += quantidade * preco


def montar(sessao: Session, exercicio: int, cenarios: set[str]) -> list[LinhaContrato]:
    linhas = []
    for contrato in sorted(carregar_contratos(sessao), key=lambda c: (c.ano, c.sequencial)):
        linha = LinhaContrato(contrato)
        for mes in meses_previstos(contrato):
            if mes.competencia.year == exercicio:
                linha.base[mes.competencia] += mes.valor
        if "reajustes" in cenarios:
            _cenario_reajustes(linha, exercicio)
        if cenarios & {"aditamentos", "supressoes"}:
            _cenario_alteracoes(linha, exercicio)
        if "prorrogacoes" in cenarios:
            _cenario_prorrogacoes(sessao, linha, exercicio)
        if any(linha.total_mes(m, cenarios) for m in _meses(exercicio)):
            linhas.append(linha)
    return linhas


def exportar(sessao: Session, exercicio: int, formato: str, resumo_anual: bool, detalhamento_mensal: bool, cenarios: set[str],
             autor: Usuario) -> tuple[bytes, str, str]:
    linhas = montar(sessao, exercicio, cenarios)
    meses = _meses(exercicio)
    escolhidos = [c for c in CENARIOS if c in cenarios]
    resumo = [
        [l.contrato.numero, l.contrato.empresa.razao_social, calculos.arredondar(sum(l.base.values(), ZERO)),
         *[calculos.arredondar(sum(l.cenarios[c].values(), ZERO)) for c in escolhidos],
         calculos.arredondar(sum((l.total_mes(m, cenarios) for m in meses), ZERO))]
        for l in linhas
    ]
    mensal = [[l.contrato.numero, *[calculos.arredondar(l.total_mes(m, cenarios)) for m in meses]] for l in linhas]
    totais_resumo = ["Total", "", *[sum((r[i] for r in resumo), ZERO) for i in range(2, 3 + len(escolhidos) + 1)]]
    totais_mensal = ["Total", *[sum((r[i] for r in mensal), ZERO) for i in range(1, 13)]]
    titulo = f"Previsão Orçamentária {exercicio}"
    nome = f"previsao-orcamentaria-{exercicio}"
    if formato == "xlsx":
        abas = []
        if resumo_anual:
            abas.append(Aba("Resumo anual", [Coluna("Contrato", largura=12), Coluna("Empresa", largura=40), Coluna("Previsto", FORMATO_MOEDA, 18),
                                             *[Coluna(CENARIOS[c], FORMATO_MOEDA, 22) for c in escolhidos], Coluna("Total", FORMATO_MOEDA, 18)],
                            resumo, titulo=titulo, rodape=totais_resumo))
        if detalhamento_mensal:
            abas.append(Aba("Detalhamento mensal", [Coluna("Contrato", largura=12), *[Coluna(f"{m:%m/%Y}", FORMATO_MOEDA, 14) for m in meses]],
                            mensal, titulo=titulo, rodape=totais_mensal))
        return gerar_planilha(abas or [Aba("Resumo anual", [Coluna("Contrato")], [], titulo=titulo)]), f"{nome}.xlsx", XLSX
    documento = DocumentoPdf(titulo, "Cenários: " + (", ".join(CENARIOS[c] for c in escolhidos) or "somente a previsão"), paisagem=True,
                             autor=autor.nome_completo or autor.login)
    if resumo_anual:
        documento.secao("Resumo anual").tabela(
            ["Contrato", "Empresa", "Previsto", *[CENARIOS[c] for c in escolhidos], "Total"],
            [[r[0], r[1], *[moeda(v) for v in r[2:]]] for r in resumo], alinhar_direita=range(2, 4 + len(escolhidos)),
            larguras=[1.2, 4, 1.6, *[1.8] * len(escolhidos), 1.6], rodape=[totais_resumo[0], "", *[moeda(v) for v in totais_resumo[2:]]],
        )
    if detalhamento_mensal:
        documento.secao("Detalhamento mensal (R$ mil)").tabela(
            ["Contrato", *[f"{m:%m/%y}" for m in meses]],
            [[r[0], *[_mil(v) for v in r[1:]]] for r in mensal], alinhar_direita=range(1, 13),
            larguras=[1.4, *[1] * 12], rodape=["Total", *[_mil(v) for v in totais_mensal[1:]]],
        )
    return documento.gerar(), f"{nome}.pdf", "application/pdf"


def _mil(valor: Decimal) -> str:
    return f"{valor / 1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
