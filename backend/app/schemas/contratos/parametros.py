# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos parâmetros do módulo de contratos (leitura e gravação).
"""Schemas dos parâmetros de Contratos (`/api/contratos/parametros`)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class GravacaoParametrosContratos(BaseModel):
    """Todos os parâmetros (o PUT substitui o conjunto inteiro; a tela sempre envia todos)."""

    # Alertas e cortes
    corte_alertas_a_partir_de: date = Field(..., description="Competências que terminam antes desta data não geram pendências, alertas nem e-mails de aviso (vale o maior entre este corte e o \"Desconsiderar alertas a partir de\" do contrato).")
    corte_marcadores_a_partir_de: date = Field(..., description="Competências que começam antes desta data não aparecem como marcadores na carteira de contratos.")
    dias_pagamento_vencendo: int = Field(..., ge=0, le=365, description="Pagamento que vence em até N dias vira risco médio no painel e no calendário.")
    dias_atraso: int = Field(..., ge=1, le=365, description="Medição sem conclusão há mais de N dias é risco médio; há mais de 2×N, alto (e dispara o aviso de atraso).")
    dias_vigencia_a_vencer: int = Field(..., ge=1, le=730, description="Contrato com fim de vigência em até N dias fica \"a vencer\".")
    dias_vigencia_atencao: int = Field(..., ge=1, le=1460, description="Faixa de atenção da linha do tempo de vigências (precisa ser maior que a de \"a vencer\").")
    dias_sem_prorrogacao_alto: int = Field(..., ge=1, le=730, description="Risco \"a vencer sem prorrogação\": alto com até N dias para o fim, médio acima disso.")
    dias_documento_alto: int = Field(..., ge=0, le=730, description="Documento com validade em até N dias tem severidade alta no calendário.")
    dias_documento_medio: int = Field(..., ge=0, le=730, description="Documento com validade em até N dias tem severidade média no calendário (maior ou igual à alta).")
    dias_fim_vigencia_alto: int = Field(..., ge=0, le=730, description="Fim de vigência em até N dias tem severidade alta no calendário.")
    dias_fim_vigencia_medio: int = Field(..., ge=0, le=730, description="Fim de vigência em até N dias tem severidade média no calendário (maior ou igual à alta).")
    # Regras do contrato
    vigencia_maxima_padrao_meses: int = Field(..., ge=1, le=600, description="Vigência máxima que o formulário de novo contrato já traz preenchida.")
    maximo_meses_vigencia_retroativa: int = Field(..., ge=1, le=600, description="Prazo máximo, em meses, de uma vigência retroativa.")
    limite_aditamento_sem_autorizacao: Decimal = Field(..., ge=0, le=1000, max_digits=7, decimal_places=2, description="Acréscimo acumulado (%) acima do qual o aditamento exige a autorização anexada.")
    limite_acerto_centavos: Decimal = Field(..., ge=0, le=1000, max_digits=10, decimal_places=2, description="Maior acerto (R$, em módulo) permitido por item na medição.")
    maximo_notas_fiscais: int = Field(..., ge=1, le=200, description="Notas fiscais (e documentos de despesa variável) por competência.")
    prazo_pagamento_padrao_dias: int = Field(..., ge=0, le=365, description="Prazo de pagamento que a etapa de nota fiscal sugere, em dias corridos.")
    prazo_nota_fiscal_horas: int = Field(..., ge=1, le=720, description="Prazo para a nota fiscal depois da medição, em horas, nas competências sem prazo de contestação.")
    # Arquivos e limites
    xml_tamanho_maximo_mb: int = Field(..., ge=1, le=100, description="Tamanho máximo do XML de nota fiscal, em MB.")
    planilha_tamanho_maximo_mb: int = Field(..., ge=1, le=100, description="Tamanho máximo das planilhas de importação, em MB.")
    maximo_anexos_ocorrencia: int = Field(..., ge=1, le=50, description="Anexos por ocorrência do diário de bordo.")
    anexos_email_maximo_mb: int = Field(..., ge=1, le=100, description="Soma máxima dos anexos de uma ocorrência enviados por e-mail, em MB.")
    # Prorrogação
    ssgc_nome: str = Field(..., min_length=1, max_length=200, description="Subsecretário(a) de Gestão Corporativa: assina o termo aditivo e as declarações da prorrogação.")
    ssgc_cpf: str = Field(..., max_length=20, description="CPF do(a) Subsecretário(a) de Gestão Corporativa (com a máscara usada nos documentos).")
    secretario_nome: str = Field(..., min_length=1, max_length=200, description="Secretário(a): autoridade máxima no Termo de Ciência e Notificação (TCE).")
    secretario_cpf: str = Field(..., max_length=20, description="CPF do(a) Secretário(a).")
    autoridade_competente_nome: str = Field(..., min_length=1, max_length=200, description="Autoridade competente que assina o despacho de autorização da prorrogação.")
    autoridade_competente_cargo: str = Field(..., min_length=1, max_length=200, description="Cargo da autoridade competente do despacho de autorização.")
    pncp_dias_uteis_licitacao: int = Field(..., ge=1, le=60, description="Prazo, em dias úteis a partir da assinatura, para divulgar no PNCP o termo de contrato de licitação (art. 94 da Lei 14.133).")
    pncp_dias_uteis_direta: int = Field(..., ge=1, le=60, description="O mesmo, para contratação direta (dispensa ou inexigibilidade).")
    aviso_pncp_dias_uteis: int = Field(..., ge=0, le=30, description="Quantos dias úteis antes do prazo do PNCP o sistema lembra a equipe.")
    parecer_referencial_validade_dias: int = Field(..., ge=1, le=1460, description="Validade do Parecer Referencial da PGE, em dias, desde a emissão.")
    parecer_referencial_vigencia_ate: date = Field(..., description="Data até a qual o Parecer Referencial vigente vale (o enquadramento avisa depois dela).")

    @model_validator(mode="after")
    def _coerencia(self):
        if self.dias_documento_medio < self.dias_documento_alto:
            raise ValueError("Documento a vencer: o prazo médio não pode ser menor que o alto.")
        if self.dias_fim_vigencia_medio < self.dias_fim_vigencia_alto:
            raise ValueError("Fim de vigência: o prazo médio não pode ser menor que o alto.")
        if self.dias_vigencia_atencao <= self.dias_vigencia_a_vencer:
            raise ValueError("A faixa de atenção das vigências precisa ser maior que a de \"a vencer\".")
        return self


class LeituraParametrosContratos(GravacaoParametrosContratos):
    """Parâmetros atuais, com quem alterou por último."""

    atualizado_por_nome: str | None = Field(None, description="Quem alterou por último (vazio enquanto ninguém alterou).")
    atualizado_em: datetime | None = Field(None, description="Quando foi alterado por último.")
    padroes: GravacaoParametrosContratos = Field(..., description="Valores de fábrica, para o botão \"Restaurar padrão\".")
