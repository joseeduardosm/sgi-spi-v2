# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o texto da portaria de designação e o PDF de evidência das ciências e do aceite.
"""Texto e evidência da portaria de designação de gestão e fiscalização.

O texto da portaria é o HTML da máscara já preenchido (`dados["texto_html"]`, veja `servico_portaria.montar_dados`): a tela mostra e
oferece o botão copiar, como o despacho da última etapa da execução; não há mais minuta em Word ou PDF.

O único PDF é a **evidência**: função, nomeado e data da ciência de cada um, mais o aceite da autoridade. Ele é juntado ao SEI antes da
publicação no Diário Oficial.
"""

from datetime import datetime

from app.services.contratacoes import html_blocos
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
ROTULOS_PAPEL = {
    "gestor": "Gestor",
    "gestor_suplente": "Gestor suplente",
    "fiscal_administrativo": "Fiscal administrativo",
    "fiscal_administrativo_suplente": "Fiscal administrativo suplente",
    "fiscal_tecnico": "Fiscal técnico",
    "fiscal_tecnico_suplente": "Fiscal técnico suplente",
}
RODAPE_EVIDENCIA = (
    "Este documento deverá ser juntado ao processo SEI como evidência da ciência dos servidores designados e do aceite da autoridade "
    "competente, para que, em seguida, seja providenciada a publicação da portaria no Diário Oficial do Estado (D.O.E.). "
    "A designação produz efeitos no sistema somente após a comprovação da publicação, anexada pelo Protocolo."
)


def titulo(dados: dict) -> str:
    return f"Portaria {dados['sigla']} nº {dados['numero']:03d}, de {dados['exercicio']}"


def blocos(dados: dict) -> list[tuple]:
    """Blocos (parágrafos, listas e tabelas) do texto da portaria, já preenchido a partir da máscara."""
    return html_blocos.blocos(dados["texto_html"])


def _data_hora(instante: datetime | None) -> str:
    return instante.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y às %H:%M") if instante else "—"


def gerar_evidencia(dados: dict, contrato_rotulo: str, nomeacoes: list[dict], autoridade: dict, solicitante: str, gerado_por: str) -> bytes:
    """PDF de evidência. `nomeacoes` = [{papel, nome, ciente_em}]; `autoridade` = {nome, cargo, aceita_em}."""
    documento = DocumentoPdf(titulo=f"Evidência de ciência e aceite — {titulo(dados)}", subtitulo=contrato_rotulo, paisagem=False, autor=gerado_por)
    documento.campos([
        ("Portaria", titulo(dados)), ("Contrato", contrato_rotulo),
        ("Empresa", dados.get("empresa", "")), ("Processo SEI", dados.get("processo_sei", "")),
        ("Portaria elaborada por", solicitante), ("Número reservado", f"{dados['numero']:03d}/{dados['exercicio']}"),
    ])
    documento.secao("Ciência dos designados")
    documento.tabela(
        ["Função", "Designado", "Ciência"],
        [[ROTULOS_PAPEL.get(n["papel"], n["papel"]), n["nome"], _data_hora(n["ciente_em"])] for n in nomeacoes],
        larguras=[3, 4, 3],
    )
    documento.secao("Aceite da autoridade competente")
    documento.tabela(
        ["Função", "Autoridade", "Aceite"],
        [[autoridade["cargo"] or "Autoridade competente", autoridade["nome"], _data_hora(autoridade["aceita_em"])]],
        larguras=[3, 4, 3],
    )
    documento.espaco(6)
    documento.paragrafo(RODAPE_EVIDENCIA)
    return documento.gerar()
