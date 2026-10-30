# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular, mês a mês, o valor da nova vigência de uma prorrogação ainda não registrada e gerar a memória de cálculo.
"""Memória de cálculo da prorrogação.

A nova vigência ainda não existe no contrato enquanto a prorrogação é um rascunho, então a conta é feita aqui, mês a mês,
sobre os meses que ela vai cobrir (começa no dia seguinte ao fim atual):

- itens contínuos: quantidade mensal × preço vigente no início do mês × fator do mês;
- itens sob demanda: a quantidade planejada para o mês no rascunho × preço (a grade já é a quantidade daquele mês).

**Meses quebrados** (a nova vigência começa ou termina no meio do mês) usam a escolha do gestor, uma só para todos:
`pro_rata` cobra os dias da nova vigência (30/360); `integral`, o mês inteiro. Vale para todos os itens contínuos e só
para a memória e o valor da prorrogação: a execução continua seguindo o faturamento de cada item.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Contrato, MemoriaProrrogacao, ProcessoProrrogacao
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import moeda
from app.services.contratos.erros import ErroRegraContrato
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, Aba, Coluna, gerar_planilha

ZERO = Decimal(0)
MODOS = ("pro_rata", "integral")
ROTULOS_MODO = {"pro_rata": "Pro rata (só os dias da nova vigência no mês)", "integral": "Integral (o mês inteiro)"}
# Tipo MIME das planilhas .xlsx
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Versão do layout dos arquivos: ao mudar o layout, sobe e a próxima geração cria versão nova
FORMATO_MEMORIA = 1


@dataclass
class MesProrrogacao:
    """Um mês da nova vigência com o valor dos contínuos e do sob demanda planejado."""
    competencia: object
    inicio: object
    fim: object
    fator: Decimal
    quebrado: bool
    continuos: Decimal
    sob_demanda: Decimal

    @property
    def rotulo(self) -> str:
        return f"{self.competencia:%m/%Y}"

    @property
    def total(self) -> Decimal:
        return self.continuos + self.sob_demanda


def nova_vigencia(contrato: Contrato, meses: int | None):
    """(início, fim) da nova vigência: começa no dia seguinte ao fim atual; sem prazo, o fim fica vazio."""
    inicio = contrato.data_fim + timedelta(days=1)
    return inicio, calculos.calcular_data_fim(inicio, meses) if meses else None


def _periodos(contrato: Contrato, meses: int | None) -> list[calculos.PeriodoMensal]:
    inicio, fim = nova_vigencia(contrato, meses)
    if fim is None:
        return []
    sequencia = len(contrato.vigencias_retroativas) + len(contrato.prorrogacoes) + 2
    return list(calculos.meses_da_vigencia(calculos.Vigencia(sequencia, inicio, fim)))


def _planejado(plano: list | None) -> dict:
    """Quantidade planejada de cada item sob demanda por mês: {(item_id, 'AAAA-MM-01'): quantidade}."""
    return {(p["item_id"], mes): Decimal(q) for p in (plano or []) for mes, q in p.get("apontamentos", {}).items()}


def calcular_meses(contrato: Contrato, meses: int | None, plano: list | None, modo: str | None) -> list[MesProrrogacao]:
    """Os meses da nova vigência com o valor de cada um, pela escolha `modo` nos meses quebrados (sem escolha, pro rata)."""
    modo = modo or "pro_rata"
    planejado = _planejado(plano)
    saida = []
    for periodo in _periodos(contrato, meses):
        quebrado = periodo.fator < 1
        # Mês quebrado: pelos dias (pro rata) ou cheio (integral), para todos os contínuos; mês inteiro: 1
        fator = (periodo.fator if modo == "pro_rata" else Decimal(1)) if quebrado else Decimal(1)
        continuos = sob_demanda = ZERO
        for item in contrato.itens:
            preco = valores.preco_em(contrato, item, periodo.inicio)
            if item.tipo == "continuo":
                continuos += valores.quantidade_mensal_em(contrato, item, periodo.competencia) * preco * fator
            else:
                sob_demanda += planejado.get((str(item.id), periodo.competencia.isoformat()), ZERO) * preco
        saida.append(MesProrrogacao(periodo.competencia, periodo.inicio, periodo.fim, periodo.fator, quebrado,
                                    calculos.arredondar(continuos), calculos.arredondar(sob_demanda)))
    return saida


def valor_do_periodo(contrato: Contrato, meses: int | None, plano: list | None, modo: str | None, ano: int | None = None) -> Decimal:
    """Valor da nova vigência (ou só dos meses de um ano), pela mesma conta da memória."""
    return calculos.arredondar(sum((m.total for m in calcular_meses(contrato, meses, plano, modo) if ano is None or m.competencia.year == ano), ZERO))


def _totais_por_ano(meses: list[MesProrrogacao]) -> list[dict]:
    anos: dict[int, Decimal] = {}
    for m in meses:
        anos[m.competencia.year] = anos.get(m.competencia.year, ZERO) + m.total
    return [{"ano": ano, "total": calculos.arredondar(total)} for ano, total in sorted(anos.items())]


def resumo(contrato: Contrato, processo: ProcessoProrrogacao | None) -> dict | None:
    """Memória para a tela: meses, totais por ano e da vigência, e as duas opções dos meses quebrados para comparar."""
    if processo is None or not processo.meses:
        return None
    plano, escolha = processo.plano_sob_demanda, processo.calculo_mes_quebrado
    meses = calcular_meses(contrato, processo.meses, plano, escolha)
    opcoes = {modo: calcular_meses(contrato, processo.meses, plano, modo) for modo in MODOS}
    quebrados = [
        {"competencia": m.rotulo, "inicio": m.inicio, "fim": m.fim,
         "dias": calculos.dias_comerciais(m.inicio, m.fim),
         "pro_rata": next(o.continuos for o in opcoes["pro_rata"] if o.competencia == m.competencia),
         "integral": next(o.continuos for o in opcoes["integral"] if o.competencia == m.competencia)}
        for m in meses if m.quebrado
    ]
    return {
        "meses": [{"competencia": m.rotulo, "inicio": m.inicio, "fim": m.fim, "quebrado": m.quebrado,
                   "continuos": m.continuos, "sob_demanda": m.sob_demanda, "total": calculos.arredondar(m.total)} for m in meses],
        "totais_por_ano": _totais_por_ano(meses),
        "total": calculos.arredondar(sum((m.total for m in meses), ZERO)),
        "meses_quebrados": quebrados,
        "total_pro_rata": calculos.arredondar(sum((m.total for m in opcoes["pro_rata"]), ZERO)),
        "total_integral": calculos.arredondar(sum((m.total for m in opcoes["integral"]), ZERO)),
        "calculo_mes_quebrado": escolha,
        "precisa_escolher": bool(quebrados) and escolha is None,
    }


def hash_atual(contrato: Contrato, processo: ProcessoProrrogacao) -> str:
    """Hash dos dados que formam a memória: muda quando o prazo, a escolha, os preços, as quantidades ou o plano mudam."""
    meses = calcular_meses(contrato, processo.meses, processo.plano_sob_demanda, processo.calculo_mes_quebrado)
    return hashlib.sha256(json.dumps(
        [processo.meses, processo.calculo_mes_quebrado, FORMATO_MEMORIA, contrato.data_fim.isoformat()]
        + [[m.rotulo, str(m.continuos), str(m.sob_demanda)] for m in meses]
    ).encode()).hexdigest()


def memoria_atualizada(contrato: Contrato, processo: ProcessoProrrogacao) -> bool:
    """A última versão gerada corresponde aos dados de agora (exigido para registrar)."""
    return bool(processo.memorias) and processo.memorias[-1].hash_origem == hash_atual(contrato, processo)


def gerar_arquivos(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao, autor: Usuario) -> None:
    """PDF e XLSX da memória; nova versão só se os dados mudaram. Exige o prazo e, havendo mês quebrado, a escolha."""
    dados = resumo(contrato, processo)
    if dados is None:
        raise ErroRegraContrato("Informe e salve o prazo da prorrogação antes de gerar a memória de cálculo.")
    if dados["precisa_escolher"]:
        raise ErroRegraContrato("Escolha como calcular os meses quebrados (pro rata ou integral) antes de gerar a memória de cálculo.")
    origem = hash_atual(contrato, processo)
    if processo.memorias and processo.memorias[-1].hash_origem == origem:
        return
    versao = len(processo.memorias) + 1
    base = f"memoria-prorrogacao-{contrato.numero_arquivo}-v{versao}"
    pdf = servico_anexos.guardar_pdf_gerado(sessao, _pdf(contrato, processo, dados, versao, autor), f"{base}.pdf", "contrato-prorrogacao-memoria", autor.id, contrato_id=contrato.id)
    xlsx = servico_anexos.guardar_arquivo_gerado(sessao, _xlsx(contrato, processo, dados), f"{base}.xlsx", XLSX, "contrato-prorrogacao-memoria", autor.id, contrato_id=contrato.id)
    processo.memorias.append(MemoriaProrrogacao(versao=versao, pdf_anexo=pdf, xlsx_anexo=xlsx, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc()))


def _texto_quebrados(processo: ProcessoProrrogacao, dados: dict) -> list[str]:
    if not dados["meses_quebrados"]:
        return ["A nova vigência não tem mês quebrado: todos os meses são cheios."]
    linhas = [f"Cálculo escolhido: {ROTULOS_MODO[processo.calculo_mes_quebrado or 'pro_rata']}."]
    for q in dados["meses_quebrados"]:
        linhas.append(f"{q['competencia']} ({q['inicio']:%d/%m} a {q['fim']:%d/%m/%Y}, {q['dias']} dia(s)): pro rata {moeda(q['pro_rata'])} · integral {moeda(q['integral'])} (itens contínuos)")
    return linhas


def _pdf(contrato: Contrato, processo: ProcessoProrrogacao, dados: dict, versao: int, autor: Usuario) -> bytes:
    """Capa com a nova vigência, a tabela executiva mês a mês, os totais por ano e o total da nova vigência."""
    inicio, fim = nova_vigencia(contrato, processo.meses)
    documento = DocumentoPdf(f"Prorrogação de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}", f"Contrato {contrato.numero} · memória de cálculo · versão {versao}",
                             paisagem=True, autor=autor.nome_completo or autor.login)
    documento.secao("Identificação").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social),
        ("Fim da vigência atual", f"{contrato.data_fim:%d/%m/%Y}"), ("Nova vigência", f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"),
        ("Prazo", f"{processo.meses} mês(es)"), ("Total da nova vigência", moeda(dados["total"])),
    ])
    documento.secao("Meses quebrados")
    for linha in _texto_quebrados(processo, dados):
        documento.paragrafo(linha)
    documento.nova_pagina().secao("Tabela executiva da nova vigência").tabela(
        ["Mês", "Período", "Itens contínuos (base mensal)", "Sob demanda planejado", "Total do mês"],
        [[m["competencia"], f"{m['inicio']:%d/%m} a {m['fim']:%d/%m/%Y}" + (" (quebrado)" if m["quebrado"] else ""),
          moeda(m["continuos"]), moeda(m["sob_demanda"]), moeda(m["total"])] for m in dados["meses"]],
        larguras=[1, 2.4, 2, 2, 2], alinhar_direita=[2, 3, 4],
        rodape=["Total", "", moeda(sum((m["continuos"] for m in dados["meses"]), ZERO)), moeda(sum((m["sob_demanda"] for m in dados["meses"]), ZERO)), moeda(dados["total"])],
    )
    documento.secao("Totais por ano").tabela(
        ["Ano", "Total"], [[f"Total para {a['ano']}", moeda(a["total"])] for a in dados["totais_por_ano"]],
        larguras=[2, 2], alinhar_direita=[1], rodape=["Total da nova vigência", moeda(dados["total"])],
    )
    return documento.gerar()


def _xlsx(contrato: Contrato, processo: ProcessoProrrogacao, dados: dict) -> bytes:
    """Mesma tabela do PDF (aba "Memória") e os totais por ano (aba "Por ano")."""
    inicio, fim = nova_vigencia(contrato, processo.meses)
    titulo = f"Prorrogação de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} — Contrato {contrato.numero}"
    return gerar_planilha([
        Aba("Memória",
            [Coluna("Mês", largura=10), Coluna("Período", largura=30), Coluna("Itens contínuos (base mensal)", FORMATO_MOEDA, 22),
             Coluna("Sob demanda planejado", FORMATO_MOEDA, 22), Coluna("Total do mês", FORMATO_MOEDA, 20)],
            [[m["competencia"], f"{m['inicio']:%d/%m} a {m['fim']:%d/%m/%Y}" + (" (quebrado)" if m["quebrado"] else ""), m["continuos"], m["sob_demanda"], m["total"]]
             for m in dados["meses"]],
            titulo=titulo,
            rodape=["Total", "", sum((m["continuos"] for m in dados["meses"]), ZERO), sum((m["sob_demanda"] for m in dados["meses"]), ZERO), dados["total"]],
            observacoes=_texto_quebrados(processo, dados)),
        Aba("Por ano", [Coluna("Ano", largura=24), Coluna("Total", FORMATO_MOEDA, 22)],
            [[f"Total para {a['ano']}", a["total"]] for a in dados["totais_por_ano"]], titulo=titulo,
            rodape=["Total da nova vigência", dados["total"]]),
    ])
