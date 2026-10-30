# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela dos parâmetros do módulo de contratos (cortes de alertas, prazos, limites e regras).
"""Parâmetros do módulo Contratos: linha única (`id = 1`), editada em Contratos › Parâmetros por quem tem controle total.

Os valores de `PADROES` são os que valiam quando os números estavam fixos no código; são também o plano B se o banco falhar.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base

# Valor inicial de cada parâmetro (fonte única: o modelo, a migração, o serviço e os testes leem daqui)
PADROES: dict = {
    # Alertas e cortes
    "corte_alertas_a_partir_de": date(2026, 9, 1),
    "corte_marcadores_a_partir_de": date(2026, 8, 1),
    "dias_pagamento_vencendo": 5,
    "dias_atraso": 30,
    "dias_vigencia_a_vencer": 90,
    "dias_vigencia_atencao": 180,
    "dias_sem_prorrogacao_alto": 60,
    "dias_documento_alto": 15,
    "dias_documento_medio": 30,
    "dias_fim_vigencia_alto": 30,
    "dias_fim_vigencia_medio": 60,
    # Regras do contrato
    "vigencia_maxima_padrao_meses": 60,
    "maximo_meses_vigencia_retroativa": 120,
    "limite_aditamento_sem_autorizacao": Decimal("25"),
    "limite_acerto_centavos": Decimal("1.00"),
    "maximo_notas_fiscais": 20,
    "prazo_pagamento_padrao_dias": 30,
    "prazo_nota_fiscal_horas": 48,
    # Arquivos e limites
    "xml_tamanho_maximo_mb": 5,
    "planilha_tamanho_maximo_mb": 5,
    "maximo_anexos_ocorrencia": 5,
    "anexos_email_maximo_mb": 15,
    # Prorrogação: autoridades que assinam os documentos, prazos de publicação e validade do Parecer Referencial
    "ssgc_nome": "Laercio Paulino Simões",
    "ssgc_cpf": "822.684.878-49",
    "secretario_nome": "Rafael Antonio Cren Benini",
    "secretario_cpf": "223.011.918-42",
    "autoridade_competente_nome": "Laercio Paulino Simões",
    "autoridade_competente_cargo": "Subsecretário de Gestão Corporativa",
    "pncp_dias_uteis_licitacao": 20,
    "pncp_dias_uteis_direta": 10,
    "aviso_pncp_dias_uteis": 5,
    "parecer_referencial_validade_dias": 365,
    "parecer_referencial_vigencia_ate": date(2027, 2, 9),
}


class ParametrosContratos(Base):
    """Linha única de parâmetros do módulo de contratos."""

    __tablename__ = "contratos_parametros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Alertas e cortes: competências anteriores ao corte não geram pendências, alertas nem e-mails de aviso
    corte_alertas_a_partir_de: Mapped[date] = mapped_column(Date, default=PADROES["corte_alertas_a_partir_de"])
    corte_marcadores_a_partir_de: Mapped[date] = mapped_column(Date, default=PADROES["corte_marcadores_a_partir_de"])
    dias_pagamento_vencendo: Mapped[int] = mapped_column(Integer, default=PADROES["dias_pagamento_vencendo"])
    dias_atraso: Mapped[int] = mapped_column(Integer, default=PADROES["dias_atraso"])
    dias_vigencia_a_vencer: Mapped[int] = mapped_column(Integer, default=PADROES["dias_vigencia_a_vencer"])
    dias_vigencia_atencao: Mapped[int] = mapped_column(Integer, default=PADROES["dias_vigencia_atencao"])
    dias_sem_prorrogacao_alto: Mapped[int] = mapped_column(Integer, default=PADROES["dias_sem_prorrogacao_alto"])
    dias_documento_alto: Mapped[int] = mapped_column(Integer, default=PADROES["dias_documento_alto"])
    dias_documento_medio: Mapped[int] = mapped_column(Integer, default=PADROES["dias_documento_medio"])
    dias_fim_vigencia_alto: Mapped[int] = mapped_column(Integer, default=PADROES["dias_fim_vigencia_alto"])
    dias_fim_vigencia_medio: Mapped[int] = mapped_column(Integer, default=PADROES["dias_fim_vigencia_medio"])
    # Regras do contrato
    vigencia_maxima_padrao_meses: Mapped[int] = mapped_column(Integer, default=PADROES["vigencia_maxima_padrao_meses"])
    maximo_meses_vigencia_retroativa: Mapped[int] = mapped_column(Integer, default=PADROES["maximo_meses_vigencia_retroativa"])
    limite_aditamento_sem_autorizacao: Mapped[Decimal] = mapped_column(Numeric(7, 2), default=PADROES["limite_aditamento_sem_autorizacao"])
    limite_acerto_centavos: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=PADROES["limite_acerto_centavos"])
    maximo_notas_fiscais: Mapped[int] = mapped_column(Integer, default=PADROES["maximo_notas_fiscais"])
    prazo_pagamento_padrao_dias: Mapped[int] = mapped_column(Integer, default=PADROES["prazo_pagamento_padrao_dias"])
    prazo_nota_fiscal_horas: Mapped[int] = mapped_column(Integer, default=PADROES["prazo_nota_fiscal_horas"])
    # Arquivos e limites
    xml_tamanho_maximo_mb: Mapped[int] = mapped_column(Integer, default=PADROES["xml_tamanho_maximo_mb"])
    planilha_tamanho_maximo_mb: Mapped[int] = mapped_column(Integer, default=PADROES["planilha_tamanho_maximo_mb"])
    maximo_anexos_ocorrencia: Mapped[int] = mapped_column(Integer, default=PADROES["maximo_anexos_ocorrencia"])
    anexos_email_maximo_mb: Mapped[int] = mapped_column(Integer, default=PADROES["anexos_email_maximo_mb"])
    # Prorrogação
    ssgc_nome: Mapped[str] = mapped_column(String(200), default=PADROES["ssgc_nome"])
    ssgc_cpf: Mapped[str] = mapped_column(String(20), default=PADROES["ssgc_cpf"])
    secretario_nome: Mapped[str] = mapped_column(String(200), default=PADROES["secretario_nome"])
    secretario_cpf: Mapped[str] = mapped_column(String(20), default=PADROES["secretario_cpf"])
    autoridade_competente_nome: Mapped[str] = mapped_column(String(200), default=PADROES["autoridade_competente_nome"])
    autoridade_competente_cargo: Mapped[str] = mapped_column(String(200), default=PADROES["autoridade_competente_cargo"])
    pncp_dias_uteis_licitacao: Mapped[int] = mapped_column(Integer, default=PADROES["pncp_dias_uteis_licitacao"])
    pncp_dias_uteis_direta: Mapped[int] = mapped_column(Integer, default=PADROES["pncp_dias_uteis_direta"])
    aviso_pncp_dias_uteis: Mapped[int] = mapped_column(Integer, default=PADROES["aviso_pncp_dias_uteis"])
    parecer_referencial_validade_dias: Mapped[int] = mapped_column(Integer, default=PADROES["parecer_referencial_validade_dias"])
    parecer_referencial_vigencia_ate: Mapped[date] = mapped_column(Date, default=PADROES["parecer_referencial_vigencia_ate"])
    # Quem alterou por último
    atualizado_por_nome: Mapped[str | None] = mapped_column(String(250))
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
