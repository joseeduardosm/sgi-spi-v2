# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar a estrutura organizacional oficial da SPI (setores e hierarquia).
"""Estrutura organizacional oficial da Secretaria de Parcerias em Investimentos.

Transcrita do decreto de organização da SPI (DOE, código de autenticidade 2025.03.31.1.1.34.1.220.985372):
- I: unidades vinculadas diretamente ao Secretário de Estado;
- II: Subsecretaria de Gestão de Parcerias de Estado;
- III: Subsecretaria de Gestão Corporativa.

Formato: {nome do setor: {filhos}}. Usada por `servico_setores.substituir_estrutura` e pelo script
`scripts/reorganizar-setores.py`.
"""

ESTRUTURA_SPI: dict[str, dict] = {
    "Secretaria de Parcerias em Investimentos": {
        # I – vinculadas diretamente ao Secretário de Estado
        "Secretaria Executiva": {},
        "Chefia de Gabinete": {},
        "Consultoria Jurídica": {},
        "Ouvidoria": {},
        "Grupo Setorial de Planejamento, Orçamento e Finanças Públicas – GSPOFP": {},
        "Grupo Setorial de Transformação Digital e Tecnologia da Informação e Comunicação – GSTD-TIC": {},
        # II – Subsecretaria de Gestão de Parcerias de Estado
        "Subsecretaria de Gestão de Parcerias de Estado": {
            "Diretoria de Estruturação de Parcerias": {
                "Coordenadoria de Estruturação de Parcerias em Rodovias": {},
                "Coordenadoria de Estruturação de Parcerias em Mobilidade Urbana": {},
                "Coordenadoria de Estruturação de Parcerias em Água e Energia": {},
                "Coordenadoria de Estruturação de Parcerias Sociais": {},
            },
            "Diretoria de Gestão de Parcerias em Transporte": {
                "Coordenadoria de Gestão de Parcerias em Rodovias": {},
                "Coordenadoria de Gestão de Parcerias em Mobilidade Urbana": {},
            },
            "Diretoria de Gestão de Parcerias em Serviços": {
                "Coordenadoria de Gestão de Água e Energia": {},
                "Coordenadoria de Gestão de Parcerias Sociais": {},
            },
        },
        # III – Subsecretaria de Gestão Corporativa
        "Subsecretaria de Gestão Corporativa": {
            "Serviço de Apoio Administrativo": {},
            "Diretoria de Orçamento e Finanças": {
                "Coordenadoria de Orçamento, Metas e Acompanhamento": {},
                "Coordenadoria de Finanças": {},
            },
            "Diretoria de Gestão Administrativa": {
                "Coordenadoria de Gestão e Infraestrutura": {},
                "Coordenadoria de Gestão de Pessoas": {},
                "Coordenadoria de Contratação e Convênios": {},
            },
        },
    },
}


def contar(arvore: dict[str, dict]) -> int:
    """Total de setores da árvore."""
    return sum(1 + contar(filhos) for filhos in arvore.values())
