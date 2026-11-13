"""
===============================================================================
ARQUIVO: relatorio_itens.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Gerar o relatório em PDF dos itens financeiros do contrato (aba Itens), em
A4 paisagem, no padrão visual dos demais PDFs do sistema.

RESUMO TÉCNICO:
`relatorio_itens` usa os mesmos números da aba Itens
(`servico_contratos.detalhar_contrato`): quantidades da vigência atual,
executado, disponível, valor unitário vigente, subtotal mensal, base mensal
e valor global. Monta identificação, totais e a tabela de itens com
`DocumentoPdf` e devolve os bytes e o nome do arquivo.

FINALIDADE DE NEGÓCIO:
Permite imprimir ou anexar ao processo a situação financeira dos itens do
contrato (quanto foi contratado, executado e ainda disponível), com os
códigos orçamentários (classe, natureza de despesa, SIAFÍSICO, CATMAT/CATSER).

CONTEXTO NO SISTEMA:
Chamado pela rota de download do relatório de itens do contrato. Reaproveita
os formatadores de `documentos_execucao` (moeda, quantidade). O acesso ao
contrato é checado dentro de `detalhar_contrato`.

===============================================================================
"""

import re
import uuid

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.services.contratos.documentos_execucao import moeda, moeda_unitaria, quantidade
from app.services.contratos.servico_contratos import detalhar_contrato
from app.services.documentos.pdf import DocumentoPdf

# Situação técnica do contrato → rótulo do PDF
SITUACOES = {"ativo": "Ativo", "a_vencer": "A vencer", "encerrado": "Encerrado", "suspenso": "Suspenso"}
# Periodicidade de faturamento em meses → nome
PERIODICIDADES = {1: "Mensal", 2: "Bimestral", 3: "Trimestral", 6: "Semestral", 12: "Anual"}


def _cnpj(valor: str) -> str:
    """00.000.000/0000-00 (sem máscara se não tiver 14 dígitos)."""
    d = "".join(ch for ch in valor if ch.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else valor


def _percentual(valor) -> str:
    """Percentual com 2 casas e vírgula decimal (ex.: 12,50%)."""
    return f"{valor:.2f}%".replace(".", ",")


def relatorio_itens(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> tuple[bytes, str]:
    """PDF da aba Itens e o nome do arquivo (`ITENS_SPI_NNN_AAAA.pdf`).

    Parâmetros: `sessao` (banco), `contrato_id` e `usuario` (quem pede; seu nome
    vai como autor do PDF). Não grava nada.
    """
    c = detalhar_contrato(sessao, contrato_id, usuario)
    # A última vigência da lista é a atual
    vigencia = c.vigencias[-1]
    documento = DocumentoPdf("Itens financeiros do contrato", f"Contrato {c.numero} · {c.apelido or c.empresa.razao_social}",
                             paisagem=True, autor=usuario.nome_completo or usuario.login)
    documento.secao("Identificação").campos([
        ("Contrato", c.numero),
        ("Situação", SITUACOES.get(str(c.situacao), str(c.situacao))),
        ("Contratada", f"{c.empresa.razao_social} (CNPJ {_cnpj(c.empresa.cnpj)})"),
        ("Vigência atual", f"{vigencia.sequencia}ª · {vigencia.inicio:%d/%m/%Y} a {vigencia.fim:%d/%m/%Y}"),
        ("Periodicidade", PERIODICIDADES.get(c.periodicidade_meses, f"{c.periodicidade_meses} meses")),
        ("Processo SEI (execução)", c.sei_execucao_numero),
        ("Objeto", c.objeto),
    ])
    documento.secao("Totais da vigência atual").campos([
        ("Base mensal (itens contínuos)", moeda(c.base_mensal)),
        ("Valor global", moeda(c.valor_global)),
        ("Aditamentos acumulados", _percentual(c.aditamento_acumulado_percentual)),
        ("Supressões acumuladas", _percentual(c.supressao_acumulada_percentual)),
    ])
    # Uma linha por item; subtotal mensal só existe para itens contínuos
    linhas = [
        [
            str(i.ordem),
            i.descricao,
            i.unidade_fornecimento or "—",
            ("Contínuo" if i.tipo == "continuo" else "Sob demanda") + "\n" + ("Com pró-rata" if i.calcula_pro_rata else "Sempre integral"),
            f"{i.codigo_classe} · {i.codigo_natureza_despesa} · {i.codigo_siafisico} · {i.codigo_catmat_catser}",
            quantidade(i.quantidade_total),
            quantidade(i.quantidade_mensal),
            quantidade(i.quantidade_executada),
            quantidade(i.quantidade_disponivel),
            moeda_unitaria(i.valor_unitario),
            moeda(i.subtotal_mensal) if i.tipo == "continuo" else "—",
            str(i.vigencia_meses),
        ]
        for i in c.itens
    ]
    documento.secao(f"Itens ({len(c.itens)})").tabela(
        ["Nº", "Descrição", "UF", "Tipo", "Classe · ND · SIAFÍSICO · CATMAT/CATSER", "Qtd. total", "Qtd. mensal", "Exec.",
         "Disp.", "Valor unitário", "Subtotal mensal", "Meses"],
        linhas,
        larguras=[0.5, 2.95, 0.85, 1.2, 2.2, 0.95, 0.95, 0.9, 0.9, 1.15, 1.25, 0.85],
        alinhar_direita=[5, 6, 7, 8, 9, 10, 11],
    )
    # Nome do arquivo: número do contrato com tudo que não é letra/dígito trocado por "_"
    arquivo = re.sub(r"[^0-9A-Za-z]+", "_", c.numero).strip("_") or "SEM_NUMERO"
    return documento.gerar(), f"ITENS_SPI_{arquivo}.pdf"
