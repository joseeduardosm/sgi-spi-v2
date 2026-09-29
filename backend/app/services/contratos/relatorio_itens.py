# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o relatório em PDF dos itens financeiros do contrato (aba Itens).
"""Relatório dos itens financeiros do contrato (A4 paisagem, no padrão visual dos demais PDFs).

Usa os mesmos números da aba Itens (`servico_contratos.detalhar_contrato`): quantidades da vigência
atual, executado, disponível, valor unitário vigente, subtotal mensal, base mensal e valor global.
"""

import re
import uuid

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.services.contratos.documentos_execucao import moeda, quantidade
from app.services.contratos.servico_contratos import detalhar_contrato
from app.services.documentos.pdf import DocumentoPdf

SITUACOES = {"ativo": "Ativo", "a_vencer": "A vencer", "encerrado": "Encerrado", "suspenso": "Suspenso"}
PERIODICIDADES = {1: "Mensal", 2: "Bimestral", 3: "Trimestral", 6: "Semestral", 12: "Anual"}


def _cnpj(valor: str) -> str:
    """00.000.000/0000-00 (sem máscara se não tiver 14 dígitos)."""
    d = "".join(ch for ch in valor if ch.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else valor


def _percentual(valor) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def relatorio_itens(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> tuple[bytes, str]:
    """PDF da aba Itens e o nome do arquivo (`ITENS_SPI_NNN_AAAA.pdf`)."""
    c = detalhar_contrato(sessao, contrato_id, usuario)
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
            moeda(i.valor_unitario),
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
    arquivo = re.sub(r"[^0-9A-Za-z]+", "_", c.numero).strip("_") or "SEM_NUMERO"
    return documento.gerar(), f"ITENS_SPI_{arquivo}.pdf"
