# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter o catálogo fixo dos documentos importantes do contrato.
"""Catálogo fixo dos documentos importantes do contrato (001 a 023).

Os termos aditivos de prorrogação entram depois como 024, 025… (MVP 5). O prefixo compõe o
nome padronizado do arquivo baixado: `PREFIXO_SPI_NNN_AAAA.pdf`.
"""

from typing import NamedTuple


class TipoDocumento(NamedTuple):
    """Um tipo de documento: código (001…), título exibido e prefixo do nome do arquivo."""
    codigo: int
    titulo: str
    prefixo: str


CATALOGO: tuple[TipoDocumento, ...] = (
    TipoDocumento(1, "Documento de Formalização da Demanda — DFD", "DFD"),
    TipoDocumento(2, "Estudo Técnico Preliminar — ETP", "ETP"),
    TipoDocumento(3, "Mapa de Riscos", "MAPA_RISCOS"),
    TipoDocumento(4, "Termo de Referência — TR", "TR"),
    TipoDocumento(5, "Parecer da Consultoria Jurídica", "PARECER_CJ"),
    TipoDocumento(6, "Despacho Saneador", "DESP_SANEADOR"),
    TipoDocumento(7, "Autorização da Autoridade Competente", "AUT_AUTORIDADE"),
    TipoDocumento(8, "Proposta Homologada", "PROP_VENC"),
    TipoDocumento(9, "Atos de Adjudicação e Homologação", "ADJ_HOM"),
    TipoDocumento(10, "Nota de Empenho Inicial", "EMPENHO_INICIAL"),
    TipoDocumento(11, "Garantia Contratual", "GARANTIA_CONTRATUAL"),
    TipoDocumento(12, "Contrato Assinado", "CONTRATO_ASSINADO"),
    TipoDocumento(13, "Extrato de Publicação do Contrato", "PUBLIC_EXTRATO_DOE"),
    TipoDocumento(14, "Comprovante de Publicação no PNCP", "PUBLIC_PNCP"),
    TipoDocumento(15, "Comprovação de Publicação no Site da SPI", "PUBLIC_SITE"),
    TipoDocumento(16, "Extrato da Portaria de Designação dos Gestores/Fiscalizadores", "PORTARIA_GESTOR_FISCAL"),
    TipoDocumento(17, "Extrato da Nota de Lançamento da Garantia Contratual", "SIAFEM_GARANTIA"),
    TipoDocumento(18, "Termo de Ciência e Notificação — TCESP", "TERMO_CIENCIA_TCESP"),
    TipoDocumento(19, "Cadastro do Responsável — TCESP", "CAD_RESP_TCESP"),
    TipoDocumento(20, "Declaração de Documentos à Disposição do TCESP", "DECL_DOCS_TCESP"),
    TipoDocumento(21, "Pesquisa de Preços para Reajuste Contratual", "PESQ_PRECOS_REAJUSTE"),
    TipoDocumento(22, "Ordem de Início dos Serviços/Fornecimento", "ORDEM_INICIO_SERVICOS"),
    TipoDocumento(23, "Termos de Recebimento Provisório e Definitivo", "TERMO_RECEBIMENTO"),
)
# Acesso rápido ao tipo pelo código: {1: TipoDocumento(...), ...}
POR_CODIGO = {tipo.codigo: tipo for tipo in CATALOGO}
# Prefixo dos termos aditivos de prorrogação (códigos 024 em diante)
PREFIXO_TERMO_ADITIVO = "TERMO_ADITIVO"


def nome_download(codigo: int, sequencial: int, ano: int) -> str:
    """Nome do arquivo baixado, ex.: `DFD_SPI_012_2026.pdf` ou `TERMO_ADITIVO_024_SPI_012_2026.pdf`."""
    # Código fora do catálogo = termo aditivo de prorrogação (024 em diante)
    tipo = POR_CODIGO.get(codigo)
    prefixo = tipo.prefixo if tipo else f"{PREFIXO_TERMO_ADITIVO}_{codigo:03d}"
    return f"{prefixo}_SPI_{sequencial:03d}_{ano:04d}.pdf"
