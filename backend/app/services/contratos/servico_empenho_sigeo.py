# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar sozinho, a partir do SIGEO, as Notas de Empenho e os cancelamentos dos contratos que têm Processo Financeiro e ainda não têm empenho.
"""Cadastro automático de NEs e cancelamentos pela análise "EMPENHADO - Execução" do SIGEO.

Só age em contrato com **Processo Financeiro** preenchido e **sem nenhuma NE cadastrada**: nunca altera um contrato que já tem empenho.

Na análise, cada linha é um documento do tipo NE:
- valor **positivo**: uma NE (`COD_DOCUMENTO_ORIGEM` = `COD_DOCUMENTO`), cadastrada com o número curto `AAAANEnnnnn` e o valor como valor original;
- valor **negativo**: um cancelamento (eventos 400093 e 400096); `COD_DOCUMENTO` é o documento do cancelamento e `COD_DOCUMENTO_ORIGEM` é a NE cancelada. Vira um
  cancelamento da NE (valor positivo), com o texto do SIGEO e a data de lançamento na justificativa.

O que não fecha (cancelamento sem a NE na análise, soma de cancelamentos acima do valor, número já usado) vira pendência e nada daquele item é gravado.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation  # noqa: F401

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contratos import CancelamentoNotaEmpenho, Contrato, NotaEmpenho
from app.services.contratos.servico_ob_sigeo import processo_normalizado, processos_do_contrato
from app.services.servico_auditoria import auditar

log = logging.getLogger("sgi_spi.sigeo")
ZERO = Decimal(0)


def numero_curto(codigo: str) -> str:
    """`390105000012025NE00028` → `2025NE00028` (o número usado no SGI); vazio se o código não termina em `AAAANEnnnnn`."""
    m = re.search(r"(\d{4}NE\d+)$", codigo or "")
    return m.group(1) if m else ""


@dataclass
class Cancelamento:
    numero: str
    nota: str  # número curto da NE cancelada
    valor: Decimal  # positivo
    lancamento: date | None
    texto: str


@dataclass
class EmpenhoSigeo:
    numero: str
    valor: Decimal
    lancamento: date | None
    texto: str
    cancelamentos: list[Cancelamento] = field(default_factory=list)


def empenhos_por_processo(linhas: list[dict[str, str]]) -> tuple[dict[str, list[EmpenhoSigeo]], dict[str, list[Cancelamento]]]:
    """Separa a análise em NEs e cancelamentos, por processo. Devolve ({processo: NEs com seus cancelamentos}, {processo: cancelamentos sem a NE na análise})."""
    nes: dict[str, dict[str, EmpenhoSigeo]] = {}
    cancelamentos: dict[str, list[Cancelamento]] = {}
    for linha in linhas:
        processo = processo_normalizado(linha.get("COD_PROCESSO"))
        numero = numero_curto(linha.get("COD_DOCUMENTO", ""))
        try:
            valor = Decimal(linha.get("VALOR_DOCUMENTO") or "")
            lancamento = date.fromisoformat((linha.get("DATA_LANCAMENTO") or "")[:10]) if linha.get("DATA_LANCAMENTO") else None
        except (InvalidOperation, ValueError):
            continue
        if not processo or not numero or valor == 0 or (linha.get("TIPO_DOCUMENTO") or "NE") != "NE":
            continue
        texto = (linha.get("DESCRICAO_DOCUMENTO") or "").strip()
        if valor > 0:
            nes.setdefault(processo, {})[numero] = EmpenhoSigeo(numero, valor, lancamento, texto)
        else:
            cancelamentos.setdefault(processo, []).append(Cancelamento(numero, numero_curto(linha.get("COD_DOCUMENTO_ORIGEM", "")), -valor, lancamento, texto))
    sem_nota: dict[str, list[Cancelamento]] = {}
    for processo, lista in cancelamentos.items():
        for c in lista:
            alvo = nes.get(processo, {}).get(c.nota)
            if alvo is not None:
                alvo.cancelamentos.append(c)
            else:
                sem_nota.setdefault(processo, []).append(c)
    return {p: list(d.values()) for p, d in nes.items()}, sem_nota


@dataclass
class Resultado:
    contratos: list[dict] = field(default_factory=list)
    nes_cadastradas: int = 0
    cancelamentos: int = 0
    pendencias: list[dict] = field(default_factory=list)
    # Contratos com Processo Financeiro, sem NE no SGI e sem NE nenhuma no SIGEO (a análise só traz alguns exercícios)
    sem_empenho_no_sigeo: list[dict] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"contratos": self.contratos, "nes_cadastradas": self.nes_cadastradas, "cancelamentos": self.cancelamentos,
                "pendencias": self.pendencias, "sem_empenho_no_sigeo": self.sem_empenho_no_sigeo}


def cadastrar(sessao: Session, linhas: list[dict[str, str]], autor, ensaio: bool = False) -> Resultado:
    """Cadastra NEs e cancelamentos dos contratos com Processo Financeiro e sem NE. Em `ensaio` só relata (nada é gravado)."""
    resultado = Resultado()
    por_processo, sem_nota = empenhos_por_processo(linhas)
    contratos = sessao.scalars(select(Contrato).where(Contrato.processo_financeiro != "").order_by(Contrato.numero))
    for contrato in contratos:
        if contrato.notas_empenho:
            continue
        processos = processos_do_contrato(contrato.processo_financeiro)
        nes = [ne for p in sorted(processos) for ne in por_processo.get(p, [])]
        rotulo = f"{contrato.numero} · {contrato.apelido or contrato.empresa.razao_social}"
        if not nes:
            resultado.sem_empenho_no_sigeo.append({"contrato_id": str(contrato.id), "contrato": rotulo, "processos": sorted(processos)})
            continue
        gravar: list[tuple[EmpenhoSigeo, list[Cancelamento]]] = []
        usados: set[str] = set()
        for ne in nes:
            if ne.numero in usados:
                resultado.pendencias.append({"contrato": rotulo, "contrato_id": str(contrato.id), "motivo": f"A NE {ne.numero} aparece em mais de um processo do contrato: só a primeira foi considerada."})
                continue
            total_cancelado = sum((c.valor for c in ne.cancelamentos), ZERO)
            if total_cancelado > ne.valor:
                resultado.pendencias.append({"contrato": rotulo, "contrato_id": str(contrato.id),
                                             "motivo": f"Os cancelamentos da NE {ne.numero} (R$ {total_cancelado:.2f}) passam do valor dela (R$ {ne.valor:.2f}): a NE não foi cadastrada."})
                continue
            numeros_cancelamento = [c.numero for c in ne.cancelamentos]
            if len(set(numeros_cancelamento)) != len(numeros_cancelamento) or set(numeros_cancelamento) & (usados | {ne.numero}):
                resultado.pendencias.append({"contrato": rotulo, "contrato_id": str(contrato.id), "motivo": f"Números repetidos nos cancelamentos da NE {ne.numero}: a NE não foi cadastrada."})
                continue
            usados |= {ne.numero, *numeros_cancelamento}
            gravar.append((ne, ne.cancelamentos))
        for p in sorted(processos):
            for c in sem_nota.get(p, []):
                resultado.pendencias.append({"contrato": rotulo, "contrato_id": str(contrato.id),
                                             "motivo": f"Cancelamento {c.numero} (R$ {c.valor:.2f}) é da NE {c.nota or '?'}, que não está na análise: não foi cadastrado."})
        if not gravar:
            continue
        item = {"contrato_id": str(contrato.id), "contrato": rotulo,
                "nes": [{"numero": ne.numero, "valor": str(ne.valor), "cancelamentos": [{"numero": c.numero, "valor": str(c.valor)} for c in cs]} for ne, cs in gravar]}
        resultado.contratos.append(item)
        resultado.nes_cadastradas += len(gravar)
        resultado.cancelamentos += sum(len(cs) for _, cs in gravar)
        if ensaio:
            continue
        for ne, cancelamentos in gravar:
            nota = NotaEmpenho(contrato_id=contrato.id, numero=ne.numero, valor_original=ne.valor, criado_por_id=autor.id if autor else None)
            sessao.add(nota)
            sessao.flush()
            for c in cancelamentos:
                quando = f" (lançado em {c.lancamento:%d/%m/%Y})" if c.lancamento else ""
                sessao.add(CancelamentoNotaEmpenho(contrato_id=contrato.id, nota_id=nota.id, numero=c.numero, valor=c.valor,
                                                   justificativa=f"Cadastrado do SIGEO{quando}: {c.texto}"[:2000], criado_por_id=autor.id if autor else None))
        auditar(sessao, autor.login if autor else "sistema", "contrato.nota_empenho.sigeo", f"Contrato {contrato.numero}", f"{len(gravar)} NE(s) do SIGEO",
                autor_id=autor.id if autor else None, alvo_tipo="contrato", alvo_id=contrato.id, dados=item)
        sessao.commit()
    return resultado
