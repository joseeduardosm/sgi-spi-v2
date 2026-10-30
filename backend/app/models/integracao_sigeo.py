# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir a tabela da integração com o SIGEO (OBIEE da Fazenda), de onde vêm as ordens bancárias pagas.
"""Integração com o SIGEO: linha única com o endereço, a análise consultada e a credencial (senha cifrada)."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc

URL_PADRAO = "https://www.sigeo.fazenda.sp.gov.br/analytics/saw.dll"
ANALISE_PADRAO = "/users/31818707810/SPI - Execução/PAGO - Execução Contrato - Gestor"
ANALISE_EMPENHADO_PADRAO = "/users/31818707810/SPI - Execução/EMPENHADO - Execução"


class IntegracaoSigeo(Base):
    """Configuração (id = 1). A senha fica cifrada com a chave de cifra do sistema e nunca volta à tela."""

    __tablename__ = "integracao_sigeo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    url_base: Mapped[str] = mapped_column(String(300), default=URL_PADRAO)
    # Caminho da análise salva no catálogo do OBIEE (colunas COD_PROCESSO, COD_DOCUMENTO, DATA_LANCAMENTO, DESCRICAO_DOCUMENTO, VALOR_DOCUMENTO…)
    caminho_analise: Mapped[str] = mapped_column(String(500), default=ANALISE_PADRAO)
    # Análise das Notas de Empenho (e cancelamentos) emitidas: usada para cadastrar sozinha as NEs dos contratos com Processo Financeiro e sem empenho
    caminho_analise_empenhado: Mapped[str] = mapped_column(String(500), default=ANALISE_EMPENHADO_PADRAO, server_default=ANALISE_EMPENHADO_PADRAO)
    usuario: Mapped[str] = mapped_column(String(100), default="")
    senha_cifrada: Mapped[str] = mapped_column(String(600), default="")
    # Hora do dia (0–23, horário de Brasília) a partir da qual a conferência diária roda; o timer passa de hora em hora e só confere uma vez por dia
    hora_conferencia: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    # Resultado da última conferência (rotina das 08:00 ou "Executar agora"): resumo e pendências
    ultima_execucao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_resultado: Mapped[dict | None] = mapped_column(JSON)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_por: Mapped[str] = mapped_column(String(200), default="")
