# Criado por José Eduardo Santana Martins
# Este arquivo serve para conferir no SIGEO se as competências que só esperam a ordem bancária já foram pagas e, se sim, concluir a etapa sozinho.
"""Conferência diária das ordens bancárias no SIGEO.

Para cada competência na etapa "ordem bancária" (sem OB juntada) de um contrato com **Processo Financeiro** preenchido:

1. pega as OBs do SIGEO do(s) mesmo(s) processo(s) (`COD_PROCESSO`; o contrato pode ter mais de um, separados por vírgula), lançadas a partir do início do período e ainda não usadas por outra competência;
2. lê a competência paga no texto livre `DESCRICAO_DOCUMENTO` (`REF NOV/25`, `JUL26`, `SETEMBRO/2026`, `REF. 09/2026`…; ver `competencia_do_texto`);
3. soma as OBs do mês da competência (o pagamento pode vir em partes) e compara com o **líquido** a pagar: valor a pagar (notas fiscais brutas + despesas
   variáveis) menos as retenções conferidas. A OB do SIGEO paga o líquido; os tributos retidos saem em outros documentos.

Igual ao centavo → conclui a etapa: gera o "Comprovante de pagamento (SIGEO)" em PDF no lugar do PDF da OB, debita as NEs (como no lançamento manual) e
manda o e-mail de pagamento. Qualquer dúvida (texto sem mês, valor parcial ou acima, mais de uma competência do mês) → não conclui e grava o motivo em
`ob_sigeo_pendencia`, que aparece na etapa. Sem mês legível no texto nunca conclui: os contratos de valor fixo repetem o mesmo valor todo mês.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.contratos import Competencia, Contrato
from app.services import servico_anexos
from app.services.contratos.erros import ErroRegraContrato

log = logging.getLogger("sgi_spi.sigeo")
ZERO = Decimal(0)
TRIBUTOS = ("ir", "inss", "iss", "pis", "cofins", "csll")
MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10,
         "NOVEMBRO": 11, "DEZEMBRO": 12, "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
# Nome do mês (completo antes da sigla) sem letra colada antes ou depois; ano opcional logo depois (2 ou 4 dígitos). Colado num dia antes
# ("10SET26", "30JAN26") é a data da nota fiscal, não a competência: fica de fora
_MES_NOME = re.compile(r"(?<![A-Z0-9])(" + "|".join(sorted(MESES, key=len, reverse=True)) + r")(?![A-Z])\s*(?:DE\s*)?[/\-. ]?\s*(\d{4}|\d{2})?(?!\d)")
# Sem nome de mês: só número depois de REF/COMP (ex.: "REF. 09/2026", "COMP 9-26"), para não confundir com a data da nota fiscal
_MES_NUMERO = re.compile(r"(?:REF|COMP|COMPET\w*)[^0-9A-Z]{0,4}(\d{1,2})\s*[/\-.]\s*(\d{4}|\d{2})(?!\d)")


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode().upper()


def competencia_do_texto(texto: str, lancamento: date) -> date | None:
    """Mês/ano pago lido do texto livre da OB, ou None (sem mês ou com meses diferentes).

    Ano ausente ou fora de propósito (mais de 1 ano de distância do lançamento, ex.: "AGO/16" lançado em 2026) vira o ano da última ocorrência
    daquele mês até o lançamento ("REF JUL" lançado em agosto/2026 = julho/2026; "REF DEZ" lançado em janeiro/2027 = dezembro/2026).
    """
    t = _normalizar(texto)
    achados = [(MESES[m.group(1)], m.group(2)) for m in _MES_NOME.finditer(t)] or [(int(m.group(1)), m.group(2)) for m in _MES_NUMERO.finditer(t)]
    meses = set()
    for mes, ano_texto in achados:
        if not 1 <= mes <= 12:
            continue
        ano = int(ano_texto) + (2000 if ano_texto and len(ano_texto) == 2 else 0) if ano_texto else None
        if ano is None or abs(ano - lancamento.year) > 1:
            ano = lancamento.year if mes <= lancamento.month else lancamento.year - 1
        meses.add(date(ano, mes, 1))
    return meses.pop() if len(meses) == 1 else None


def processo_normalizado(valor: str | None) -> str:
    """Só os dígitos do processo financeiro (o SIGEO usa `20240605988`; o cadastro pode ter pontos ou barras)."""
    return re.sub(r"\D", "", valor or "")


def processos_do_contrato(valor: str | None) -> set[str]:
    """Um contrato pode ter mais de um processo financeiro (ex.: um por exercício): no campo, separados por vírgula, ponto e vírgula ou espaço."""
    return {p for p in (processo_normalizado(parte) for parte in re.split(r"[,;\s]+", valor or "")) if p}


def numero_ob(codigo: str) -> str:
    """`390001000012026OB01893` → `2026OB01893` (forma curta usada nas telas e no e-mail)."""
    m = re.search(r"(\d{4}OB\d+)$", codigo or "")
    return m.group(1) if m else (codigo or "")


@dataclass
class Pagamento:
    """Uma OB do SIGEO."""
    codigo: str
    processo: str
    lancamento: date
    valor: Decimal
    descricao: str
    competencia: date | None


@dataclass
class Resultado:
    verificadas: int = 0
    # Sem OB do mês no SIGEO ainda: é o normal até o pagamento sair (não é pendência)
    aguardando: int = 0
    concluidas: list[dict] = field(default_factory=list)
    pendencias: list[dict] = field(default_factory=list)
    # Contratos com competência esperando OB e sem processo financeiro: o processo que o SIGEO tem para o CNPJ da contratada
    sugestoes_processo: list[dict] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"verificadas": self.verificadas, "aguardando": self.aguardando, "concluidas": self.concluidas, "pendencias": self.pendencias,
                "sugestoes_processo": self.sugestoes_processo, "erros": self.erros}


def pagamentos(linhas: list[dict[str, str]]) -> list[Pagamento]:
    """Converte as linhas da análise em OBs (ignora as que não são OB ou que vêm sem processo, data ou valor)."""
    resultado = []
    for linha in linhas:
        if (linha.get("TIPO_DOCUMENTO") or "OB") != "OB":
            continue
        try:
            lancamento = date.fromisoformat((linha.get("DATA_LANCAMENTO") or "")[:10])
            valor = Decimal(linha.get("VALOR_DOCUMENTO") or "")
        except (ValueError, InvalidOperation):
            continue
        processo = processo_normalizado(linha.get("COD_PROCESSO"))
        if not processo or not linha.get("COD_DOCUMENTO"):
            continue
        descricao = linha.get("DESCRICAO_DOCUMENTO") or ""
        resultado.append(Pagamento(linha["COD_DOCUMENTO"], processo, lancamento, valor, descricao, competencia_do_texto(descricao, lancamento)))
    return resultado


def liquido_a_pagar(competencia: Competencia) -> Decimal:
    """O que a OB paga: valor a pagar (notas brutas + despesas variáveis) menos as retenções conferidas."""
    from app.services.contratos.servico_competencias import valor_a_pagar

    retencoes = sum((getattr(n, f"retencao_{t}") or ZERO for n in competencia.notas_fiscais for t in TRIBUTOS), ZERO)
    return valor_a_pagar(competencia) - retencoes


def _moeda(valor: Decimal) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _comprovante(contrato: Contrato, competencia: Competencia, obs: list[Pagamento], liquido: Decimal) -> bytes:
    """PDF "Comprovante de pagamento (SIGEO)": guarda no SGI de onde veio a conclusão da etapa."""
    from app.services.documentos.pdf import DocumentoPdf

    documento = DocumentoPdf("Comprovante de pagamento (SIGEO)", f"Contrato {contrato.numero} · Competência {competencia.numero_competencia}", autor="Rotina SIGEO")
    documento.secao("Contrato").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social), ("Processo financeiro", contrato.processo_financeiro),
        ("Competência", competencia.numero_competencia), ("Líquido a pagar (notas − retenções)", _moeda(liquido)),
    ], colunas=1)
    documento.secao("Ordens bancárias encontradas no SIGEO").tabela(
        ["OB", "Lançamento", "Valor", "Descrição no SIGEO"],
        [[numero_ob(o.codigo), f"{o.lancamento:%d/%m/%Y}", _moeda(o.valor), o.descricao] for o in obs],
        larguras=[1.6, 1.1, 1.3, 4.5], alinhar_direita=[2], rodape=["Total", "", _moeda(sum((o.valor for o in obs), ZERO)), ""],
    )
    documento.paragrafo("Etapa concluída automaticamente pela conferência diária do SIGEO: processo financeiro igual ao do contrato, competência lida na descrição "
                        "da OB igual à desta competência e soma das OBs igual ao líquido a pagar.")
    return documento.gerar()


def _ja_usadas(sessao: Session) -> set[str]:
    usadas: set[str] = set()
    for numeros in sessao.scalars(select(Competencia.ob_numero).where(Competencia.ob_numero.is_not(None))):
        usadas |= {n.strip() for n in numeros.split(",") if n.strip()}
    return usadas


def conferir(sessao: Session, linhas: list[dict[str, str]], ensaio: bool = False, hoje: date | None = None) -> Resultado:
    """Confere as competências que esperam OB contra as linhas do SIGEO. Em `ensaio` só relata (nada é gravado)."""
    from app.services.contratos import servico_competencias, servico_tarefas_contratos
    from app.services.contratos.servico_contratos import obter_contrato

    hoje = hoje or hoje_sao_paulo()
    resultado = Resultado()
    todas = pagamentos(linhas)
    usadas = _ja_usadas(sessao)
    autor = servico_tarefas_contratos.usuario_sistema(sessao)
    candidatas = list(sessao.scalars(
        select(Competencia).join(Contrato, Contrato.id == Competencia.contrato_id)
        .where(Competencia.etapa_atual == "ordem_bancaria", Competencia.ob_anexo_id.is_(None), Contrato.processo_financeiro != "")
        .order_by(Competencia.periodo_inicio)))
    concluir: list[tuple] = []
    for competencia in candidatas:
        contrato = obter_contrato(sessao, competencia.contrato_id)
        competencia = next(c for c in contrato.competencias if c.id == competencia.id)
        resultado.verificadas += 1
        processos = processos_do_contrato(contrato.processo_financeiro)
        rotulo = f"{contrato.numero} · {competencia.numero_competencia}"
        do_processo = [p for p in todas if p.processo in processos and p.codigo not in usadas and p.lancamento >= competencia.periodo_inicio]
        do_mes = [p for p in do_processo if p.competencia == competencia.competencia.replace(day=1)]
        irmas = [c for c in contrato.competencias if c.competencia == competencia.competencia and c.id != competencia.id and c.etapa_atual == "ordem_bancaria"]
        liquido = liquido_a_pagar(competencia)
        soma = sum((p.valor for p in do_mes), ZERO)
        motivo = None
        if irmas:
            motivo = "Há mais de uma competência deste mês esperando OB: confira e junte a OB manualmente."
        elif not do_mes and not [p for p in do_processo if p.competencia is None]:
            resultado.aguardando += 1
            if not ensaio:
                competencia.ob_sigeo_pendencia, competencia.ob_sigeo_verificado_em = None, agora_utc()
            continue
        elif not do_mes:
            sem_mes = [p for p in do_processo if p.competencia is None]
            motivo = ("Nenhuma OB com este mês no texto; há OB do processo sem mês legível: "
                      + "; ".join(f"{numero_ob(p.codigo)} ({_moeda(p.valor)}, \"{p.descricao[:60]}\")" for p in sem_mes[:3]) + ". Junte a OB manualmente se for dela.")
        elif soma != liquido:
            motivo = (f"OB(s) {', '.join(numero_ob(p.codigo) for p in do_mes)} somam {_moeda(soma)}, " +
                      (f"faltam {_moeda(liquido - soma)} para o líquido de {_moeda(liquido)} (pagamento parcial?)." if soma < liquido else
                       f"acima do líquido de {_moeda(liquido)}: confira e junte a OB manualmente."))
        if motivo:
            resultado.pendencias.append({"competencia": rotulo, "contrato_id": str(contrato.id), "motivo": motivo})
            if not ensaio:
                competencia.ob_sigeo_pendencia, competencia.ob_sigeo_verificado_em = motivo, agora_utc()
            continue
        numeros = ", ".join(numero_ob(p.codigo) for p in do_mes)
        resultado.concluidas.append({"competencia": rotulo, "contrato_id": str(contrato.id), "ob": numeros, "valor": str(soma)})
        usadas |= {p.codigo for p in do_mes}
        if ensaio:
            continue
        try:
            conteudo = _comprovante(contrato, competencia, do_mes, liquido)
            anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, f"comprovante-sigeo-{contrato.numero_arquivo}-{competencia.competencia:%Y-%m}.pdf",
                                                      "contrato-execucao-ob", autor.id if autor else None, contrato_id=contrato.id)
            servico_competencias.concluir_ordem_bancaria(
                sessao, contrato, competencia, anexo, autor, origem="sigeo", numero=numeros, data=max(p.lancamento for p in do_mes), valor=soma,
                descricao=" | ".join(p.descricao for p in do_mes))
            competencia.ob_sigeo_verificado_em = agora_utc()
            sessao.commit()
            concluir.append((contrato.id, competencia.id))
        except ErroRegraContrato as erro:
            sessao.rollback()
            resultado.concluidas.pop()
            resultado.pendencias.append({"competencia": rotulo, "contrato_id": str(contrato.id), "motivo": f"OB {numeros} achada, mas não deu para concluir: {erro}"})
    resultado.sugestoes_processo = _sugestoes_processo(sessao, linhas)
    if not ensaio:
        sessao.commit()
        from app.services.contratos.servico_notificacoes import notificar_ob

        for contrato_id, competencia_id in concluir:
            try:
                notificar_ob(contrato_id, competencia_id)
            except Exception:  # noqa: BLE001 - o e-mail nunca desfaz a conclusão; o resultado fica gravado na competência
                log.exception("Falha no e-mail de pagamento da competência %s", competencia_id)
    return resultado


def _sugestoes_processo(sessao: Session, linhas: list[dict[str, str]]) -> list[dict]:
    """Contratos sem processo financeiro com competência esperando OB: o(s) processo(s) que o SIGEO usa para o CNPJ da contratada."""
    from collections import Counter

    por_cnpj: dict[str, Counter] = {}
    for linha in linhas:
        cnpj = re.sub(r"\D", "", linha.get("CGC_CPF") or "")
        if cnpj and linha.get("COD_PROCESSO"):
            por_cnpj.setdefault(cnpj, Counter())[processo_normalizado(linha["COD_PROCESSO"])] += 1
    contratos = sessao.scalars(select(Contrato).join(Competencia, Competencia.contrato_id == Contrato.id)
                               .where(Contrato.processo_financeiro == "", Competencia.etapa_atual == "ordem_bancaria").distinct())
    sugestoes = []
    for contrato in contratos:
        processos = por_cnpj.get(re.sub(r"\D", "", contrato.empresa.cnpj or ""))
        if processos:
            sugestoes.append({"contrato_id": str(contrato.id), "contrato": contrato.numero, "empresa": contrato.empresa.razao_social,
                              "processos": [p for p, _ in processos.most_common(3)]})
    return sorted(sugestoes, key=lambda s: s["contrato"])


def executar(sessao: Session, ensaio: bool = False) -> Resultado:
    """Baixa a análise do SIGEO e confere; grava o resumo na configuração (fora do ensaio)."""
    from app.services import servico_integracao_sigeo
    from app.services.sigeo.cliente_obiee import ErroSigeo

    config = servico_integracao_sigeo.obter(sessao)
    try:
        linhas = servico_integracao_sigeo.baixar_pagamentos(config)
        resultado = conferir(sessao, linhas, ensaio=ensaio)
    except ErroSigeo as erro:
        resultado = Resultado(erros=[erro.mensagem])
    if not ensaio:
        config = servico_integracao_sigeo.obter(sessao)
        config.ultima_execucao_em, config.ultimo_resultado = agora_utc(), resultado.como_dict()
        sessao.commit()
    return resultado
