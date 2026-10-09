# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas de checklists, formulários, competências e etapas da execução.
"""Execução mensal: checklists, formulários de avaliação, competências e suas etapas.

Cada competência guarda fotografias (itens e preços, checklist, formulário) do momento em que foi
gerada, para que documentos já emitidos não mudem com alterações posteriores do contrato.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.anexo import Anexo
from app.models.auditoria import TipoJson
from app.models.contratos.contrato import Contrato, _lista_sql

# Etapas da competência, em ordem. `avaliacao` só existe quando a competência tem formulário.
ETAPAS = ("medicao", "avaliacao", "nota_fiscal", "retencao", "cadin", "checklist", "consolidado", "ordem_bancaria", "concluida")
# Etapas feitas em paralelo depois da nota fiscal (qualquer ordem); o consolidado só depois de todas
ETAPAS_PARALELAS = ("retencao", "cadin", "checklist")
# Competência regular (período de execução), complementar (paga a diferença de um reajuste retroativo) ou adicional
# (outra medição e outro pagamento no mesmo mês de uma competência, com justificativa)
TIPOS_COMPETENCIA = ("regular", "diferenca_reajuste", "adicional")


class Checklist(Base):
    """Versão do checklist de documentos mensais do contrato (etapa 5)."""

    __tablename__ = "contratos_checklists"
    # Número de versão sequencial por contrato (1, 2, 3...)
    __table_args__ = (UniqueConstraint("contrato_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(300))
    # Só uma versão fica ativa por vez; é ela que é copiada para as competências novas
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    ativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Nome do autor fotografado (continua legível se o usuário for excluído)
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    # Exclusão lógica (só versões inativas)
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="checklists")
    itens: Mapped[list["ItemChecklist"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", order_by="[ItemChecklist.obrigatorio.desc(), ItemChecklist.ordem]"
    )


class ItemChecklist(Base):
    """Documento exigido no checklist (ex.: "Folha de pagamento", "GFIP")."""
    __tablename__ = "contratos_checklists_itens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    checklist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_checklists.id", ondelete="CASCADE"), index=True)
    # Posição do documento na lista
    ordem: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(500))
    observacao: Mapped[str] = mapped_column(String(1000), default="")
    # Obrigatório: precisa estar anexado para concluir a etapa; opcional: pode ficar sem anexo
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Documento com validade (certidões, apólices…): informa-se até quando vale e, se ainda valer, vira o documento da competência seguinte
    com_validade: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Documento da empresa (ex.: certidão): se já foi juntado e ainda vale em outro contrato da mesma empresa, a execução oferece reaproveitá-lo
    vale_outros_contratos: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # "Pedir para enviar": ao concluir a medição, o e-mail à empresa pede este documento (com a observação). Pode ser mudado com o checklist ativo
    pedir_envio: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    checklist: Mapped[Checklist] = relationship(back_populates="itens")


class FormularioAvaliacao(Base):
    """Versão do formulário de avaliação dos serviços (etapa 2, opcional).

    `definicao`: {"escala": [{"valor", "legenda"}], "faixas": [{"minimo", "maximo", "percentual"}],
    "grupos": [{"id", "nome", "itens": [{"id", "nome", "descricao", "peso"}]}]}.
    """

    __tablename__ = "contratos_formularios"
    # Estrutura inteira do formulário guardada em JSON (escala, faixas e grupos de itens)
    __table_args__ = (UniqueConstraint("contrato_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(300))
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    definicao: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    ativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    # Exclusão lógica (só versões inativas): a versão some da lista, mas continua nas avaliações que a usaram
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    contrato: Mapped[Contrato] = relationship(back_populates="formularios")


class ModeloGlobal(Base):
    """Modelo reutilizável de checklist ou de formulário (SuperRoot), clonado para os contratos, ou máscara de portaria (SuperRoot ou controle total).

    `conteudo`: checklist → {"itens": [{"nome", "observacao"}]}; formulário → a mesma `definicao`.
    """

    __tablename__ = "contratos_modelos"
    # Tipos aceitos; `portaria` guarda a máscara do texto da portaria de designação ({"html", "variante"})
    __table_args__ = (CheckConstraint("tipo IN ('checklist', 'formulario', 'portaria')", name="ck_contratos_modelos_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    nome: Mapped[str] = mapped_column(String(300))
    # Conteúdo em JSON, no mesmo formato usado pelo checklist ou pelo formulário do contrato
    conteudo: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class Competencia(Base):
    """Competência: um período de execução do contrato e o andamento das suas etapas.

    Guarda as datas de cada etapa e os dados da nota fiscal diretamente na linha; os demais
    registros (itens medidos, NEs, ciências, memórias, CADIN, documentos, avaliação) ficam em
    tabelas filhas.
    """
    __tablename__ = "contratos_competencias"
    # Regras garantidas pelo banco: uma competência por período e tipo, e valores válidos
    __table_args__ = (
        UniqueConstraint("contrato_id", "periodo_inicio", "tipo", "numero_adicional", name="contratos_competencias_contrato_id_periodo_inicio_tipo_key"),
        CheckConstraint(f"etapa_atual IN ({_lista_sql(ETAPAS)})", name="ck_contratos_competencias_etapa"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_COMPETENCIA)})", name="ck_contratos_competencias_tipo"),
        CheckConstraint("origem_valor_nf IS NULL OR origem_valor_nf IN ('medicao', 'manual')", name="ck_contratos_competencias_origem_nf"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    # Vigência a que o período pertence (1 = original; 2+ = prorrogações)
    sequencia_vigencia: Mapped[int] = mapped_column(Integer, default=1)
    # Dia 1 do primeiro mês do período
    competencia: Mapped[date] = mapped_column(Date)
    # Datas reais do período (podem ser parciais no início e no fim do contrato)
    periodo_inicio: Mapped[date] = mapped_column(Date)
    periodo_fim: Mapped[date] = mapped_column(Date)
    # Etapa em que a competência está agora (uma das `ETAPAS`)
    etapa_atual: Mapped[str] = mapped_column(String(20), default="medicao")
    tipo: Mapped[str] = mapped_column(String(30), default="regular", server_default="regular")
    # Medição adicional: número (1, 2…; 0 nas demais), justificativa, anexo opcional e quem incluiu
    numero_adicional: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    adicional_justificativa: Mapped[str] = mapped_column(Text, default="", server_default="")
    adicional_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    adicional_por_nome: Mapped[str] = mapped_column(String(250), default="", server_default="")
    # Reajuste que originou a competência de diferença (somente tipo = diferenca_reajuste)
    reajuste_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_reajustes.id", ondelete="SET NULL"), index=True)

    # Etapa 1 — medição
    medicao_iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    medicao_concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Enquanto a medição não é concluída, a competência regular acompanha o cadastro dos itens: guarda com qual `Contrato.versao_cadastro` foi calculada
    versao_cadastro_sincronizada: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # Etapa 3 — nota fiscal (uma ou mais)
    # As notas fiscais (uma ou mais, cada uma com PDF e XML) ficam em `notas_fiscais`
    # Data de recebimento da NF: com o prazo de pagamento, define o vencimento
    nf_recebida_em: Mapped[date | None] = mapped_column(Date)
    prazo_pagamento_dias: Mapped[int | None] = mapped_column(Integer)
    # De onde veio o valor bruto: calculado pela medição ou digitado (manual)
    origem_valor_nf: Mapped[str | None] = mapped_column(String(20))
    nf_concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 4 — retenção de tributos (conferida pelo Financeiro ou pela equipe)
    retencao_concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retencao_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    retencao_por_nome: Mapped[str] = mapped_column(String(250), default="", server_default="")
    retencao_discriminacao_conferida: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    retencao_pdf_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # Etapas 5 e 6 — CADIN e checklist correm em paralelo com a retenção; o consolidado exige as três concluídas
    cadin_concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checklist_concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 6 — documento consolidado
    consolidado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    consolidado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Etapa 7 — ordem bancária
    ob_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    ob_enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # E-mail ao Financeiro (cópia para a equipe) quando a nota fiscal é juntada
    email_nf_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_nf_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_nf_destinatarios: Mapped[list[Any]] = mapped_column(TipoJson, default=list, server_default=text("'[]'"))
    email_nf_erro: Mapped[str | None] = mapped_column(Text)
    # E-mail à equipe quando o Financeiro salva a retenção
    email_retencao_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_retencao_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_retencao_destinatarios: Mapped[list[Any]] = mapped_column(TipoJson, default=list, server_default=text("'[]'"))
    email_retencao_erro: Mapped[str | None] = mapped_column(Text)
    # E-mail à equipe e ao preposto ao concluir a medição (memória + diário do período; pede a NF em 48 h)
    email_medicao_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_medicao_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_medicao_destinatarios: Mapped[list[Any]] = mapped_column(TipoJson, default=list, server_default=text("'[]'"))
    email_medicao_erro: Mapped[str | None] = mapped_column(Text)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    # Registros filhos da competência (apagados junto com ela)
    contrato: Mapped[Contrato] = relationship(back_populates="competencias")
    itens: Mapped[list["ItemMedicao"]] = relationship(back_populates="competencia", cascade="all, delete-orphan", order_by="[ItemMedicao.ordem, ItemMedicao.segmento]")
    notas: Mapped[list["SelecaoNotaEmpenho"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="SelecaoNotaEmpenho.ordem"
    )
    ciencias: Mapped[list["CienciaMedicao"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="CienciaMedicao.registrada_em"
    )
    memorias: Mapped[list["MemoriaMedicao"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="MemoriaMedicao.versao"
    )
    consultas_cadin: Mapped[list["ConsultaCadin"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="ConsultaCadin.criado_em"
    )
    notas_fiscais: Mapped[list["NotaFiscalCompetencia"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="NotaFiscalCompetencia.ordem"
    )
    # Notas de débito, recibos e outros documentos das despesas variáveis (juntados na etapa da nota fiscal; não passam pela retenção)
    despesas_variaveis: Mapped[list["DespesaVariavel"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="DespesaVariavel.ordem"
    )
    # Recusas da nota fiscal pelo Financeiro (histórico do ciclo nota → recusa → nova nota → … → aprovação)
    recusas: Mapped[list["RecusaNota"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="RecusaNota.ordem"
    )
    documentos: Mapped[list["DocumentoMensal"]] = relationship(
        back_populates="competencia", cascade="all, delete-orphan", order_by="[DocumentoMensal.obrigatorio.desc(), DocumentoMensal.ordem]"
    )
    avaliacao: Mapped["AvaliacaoCompetencia | None"] = relationship(back_populates="competencia", cascade="all, delete-orphan", uselist=False)
    # Créditos de desconto de reajuste abatidos no valor autorizado desta competência
    abatimentos_reajuste: Mapped[list["AbatimentoReajuste"]] = relationship(  # noqa: F821
        back_populates="competencia", order_by="AbatimentoReajuste.criado_em"
    )
    # Os anexos têm várias FKs para a mesma tabela `anexos`; `foreign_keys` diz qual coluna usar em cada uma
    retencao_pdf_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[retencao_pdf_anexo_id])
    consolidado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[consolidado_anexo_id])
    ob_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[ob_anexo_id])
    adicional_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[adicional_anexo_id])

    @property
    def parte(self) -> int | None:
        """1 ou 2 quando o mês civil se divide entre duas vigências (virada no meio do mês); senão nulo."""
        # Diferença de reajuste não se divide em partes
        if self.tipo != "regular" or self.contrato is None:
            return None
        # "Irmãs" = competências regulares do mesmo mês civil, em ordem de início
        irmas = sorted(
            (c for c in self.contrato.competencias if c.tipo == "regular" and c.competencia == self.competencia),
            key=lambda c: c.periodo_inicio,
        )
        return irmas.index(self) + 1 if len(irmas) > 1 and self in irmas else None

    @property
    def identificador(self) -> str:
        """Chave da rota da tela: `AAAA-MM`, `AAAA-MM-1`/`AAAA-MM-2` (mês dividido) ou `AAAA-MM-dif` (diferença de reajuste)."""
        if self.tipo == "diferenca_reajuste":
            return f"{self.competencia:%Y-%m}-dif"
        if self.tipo == "adicional":
            return f"{self.competencia:%Y-%m}-adicional-{self.numero_adicional}"
        return f"{self.competencia:%Y-%m}" + (f"-{self.parte}" if self.parte else "")

    @property
    def numero_competencia(self) -> str:
        """Rótulo exibido: `01/2027`, `01/2027 · 1ª parte` ou `Diferença de reajuste 01/2026 a 04/2026`."""
        if self.tipo == "diferenca_reajuste":
            return f"Diferença de reajuste {self.periodo_inicio:%m/%Y} a {self.periodo_fim:%m/%Y}"
        if self.tipo == "adicional":
            return f"{self.competencia:%m/%Y} · Medição adicional {self.numero_adicional}"
        return f"{self.competencia:%m/%Y}" + (f" · {self.parte}ª parte" if self.parte else "")


class ItemMedicao(Base):
    """Fotografia do item do contrato na competência, com a quantidade prevista e a medida."""

    __tablename__ = "contratos_competencias_itens"
    __table_args__ = (UniqueConstraint("competencia_id", "item_id", "segmento", name="uq_contratos_competencias_itens_trecho"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # SET NULL: a fotografia continua existindo mesmo se o item for removido do contrato
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_itens.id", ondelete="SET NULL"), index=True)
    # Dados do item copiados no momento da geração (a fotografia)
    ordem: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(String(1000))
    tipo: Mapped[str] = mapped_column(String(20))
    calcula_pro_rata: Mapped[bool] = mapped_column(Boolean, default=True)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    # Meses equivalentes do período (ex.: 0,5333 em mês parcial com pró-rata)
    fator_meses: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(1))
    quantidade_prevista: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    # 28 dígitos (18 inteiros + 10 casas), como o schema: contratos com quantidades na casa dos bilhões
    quantidade_medida: Mapped[Decimal] = mapped_column(Numeric(28, 10), default=Decimal(0))
    # Mês com virada (prorrogação ou reajuste no meio do mês): o item aparece uma vez por trecho do mês. `segmento` numera os trechos (1, 2…),
    # `periodo_*` dizem os dias de cada um e `periodo_rotulo` é o texto exibido ("01/09 a 19/09/2026 · preço anterior"). Mês sem virada: segmento 1 e nulos
    segmento: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    periodo_inicio: Mapped[date | None] = mapped_column(Date)
    periodo_fim: Mapped[date | None] = mapped_column(Date)
    periodo_rotulo: Mapped[str] = mapped_column(String(120), default="", server_default="")
    # Vigência do trecho (nula = a da competência); decide o limite e o executado dos itens sob demanda
    sequencia_vigencia: Mapped[int | None] = mapped_column(Integer)
    # Marcado na medição da competência: o item é despesa variável (subtotal à parte; exige documento de despesa na etapa da nota fiscal)
    despesa_variavel: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    competencia: Mapped[Competencia] = relationship(back_populates="itens")

    @property
    def descricao_completa(self) -> str:
        """Descrição com o trecho do mês, quando o mês tem virada ("Item — 01/09 a 19/09/2026 · preço anterior")."""
        return f"{self.descricao} — {self.periodo_rotulo}" if self.periodo_rotulo else self.descricao


class SelecaoNotaEmpenho(Base):
    """NEs escolhidas na medição, em ordem de consumo: o débito esgota a 1ª antes de passar à 2ª."""

    __tablename__ = "contratos_competencias_notas"

    # Chave primária composta: a mesma NE não é escolhida duas vezes na mesma competência
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), primary_key=True)
    # A exclusão da NE ligada a competência é barrada pelo serviço; o CASCADE permite excluir o contrato inteiro
    nota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_notas_empenho.id", ondelete="CASCADE"), primary_key=True, index=True)
    # Ordem de consumo (1 = primeira a ser debitada)
    ordem: Mapped[int] = mapped_column(Integer)

    competencia: Mapped[Competencia] = relationship(back_populates="notas")


class CienciaMedicao(Base):
    """Ciência de um integrante da equipe na medição (uma ciência já basta para concluir)."""

    __tablename__ = "contratos_competencias_ciencias"
    # Uma ciência por pessoa em cada competência
    __table_args__ = (UniqueConstraint("competencia_id", "usuario_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Nome e papel na equipe fotografados no momento da ciência
    nome: Mapped[str] = mapped_column(String(250))
    papel: Mapped[str] = mapped_column(String(40))
    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="ciencias")


class MemoriaMedicao(Base):
    """Memória de cálculo em PDF. Nova versão só quando os dados (hash) mudam."""

    __tablename__ = "contratos_competencias_memorias"
    __table_args__ = (UniqueConstraint("competencia_id", "versao"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    versao: Mapped[int] = mapped_column(Integer)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # Medição dos itens de despesas variáveis (PDF à parte, só quando a competência tem esses itens)
    anexo_despesas_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # Hash dos dados que geraram o PDF; se não mudou, não é preciso gerar outra versão
    hash_origem: Mapped[str] = mapped_column(String(64))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="memorias")
    anexo: Mapped[Anexo] = relationship(foreign_keys=[anexo_id])
    anexo_despesas: Mapped[Anexo | None] = relationship(foreign_keys=[anexo_despesas_id])


class ConsultaCadin(Base):
    """Consulta ao CADIN. Com pendência, a etapa continua aberta; sem pendência, conclui."""

    __tablename__ = "contratos_competencias_cadin"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    # Com pendência, guarda a descrição e o texto da notificação enviada à contratada
    possui_pendencia: Mapped[bool] = mapped_column(Boolean)
    pendencia: Mapped[str] = mapped_column(String(2000), default="")
    texto_notificacao: Mapped[str] = mapped_column(String(2500), default="")
    # Certidão consultada (obrigatória) e o e-mail de notificação (só com pendência)
    certidao_anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    email_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_por_nome: Mapped[str] = mapped_column(String(250))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    competencia: Mapped[Competencia] = relationship(back_populates="consultas_cadin")
    certidao_anexo: Mapped[Anexo] = relationship(foreign_keys=[certidao_anexo_id])
    email_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[email_anexo_id])


class DocumentoMensal(Base):
    """Documento do checklist copiado para a competência (um PDF por documento)."""

    __tablename__ = "contratos_competencias_documentos"
    __table_args__ = (UniqueConstraint("competencia_id", "ordem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    # Versão do checklist de origem (sem FK: a versão pode ser excluída logicamente depois)
    checklist_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    ordem: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(500))
    observacao: Mapped[str] = mapped_column(String(1000), default="")
    # Copiado do item do checklist; os opcionais não bloqueiam a conclusão da etapa
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Copiado do item do checklist; `validade_ate` é informada no envio. Um documento ainda válido é reaproveitado na competência seguinte
    # e `reaproveitado_de` guarda a competência (mês) de onde veio o arquivo
    com_validade: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    validade_ate: Mapped[date | None] = mapped_column(Date)
    reaproveitado_de: Mapped[date | None] = mapped_column(Date)
    # Copiado do item do checklist (documento da empresa). `reaproveitado_contrato`: número do contrato de onde o arquivo veio,
    # quando foi reaproveitado de outro contrato da mesma empresa (só para a tela; o consolidado não mostra)
    vale_outros_contratos: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    reaproveitado_contrato: Mapped[str | None] = mapped_column(String(60))
    # PDF anexado pelo usuário (vazio enquanto não enviado)
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    competencia: Mapped[Competencia] = relationship(back_populates="documentos")
    anexo: Mapped[Anexo | None] = relationship()


class AvaliacaoCompetencia(Base):
    """Avaliação dos serviços na competência (etapa 2), com a fotografia do formulário.

    Respostas: [{"item_id", "nota", "justificativa"}]. Ciências do ateste (coluna `assinaturas`):
    [{"papel", "usuario_id", "nome", "ciencia_em"}], uma por integrante da equipe que deu ciência.
    """

    __tablename__ = "contratos_competencias_avaliacoes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # `unique`: no máximo uma avaliação por competência
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), unique=True)
    # Versão do formulário de origem e a cópia (fotografia) da sua definição
    formulario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    definicao: Mapped[dict[str, Any]] = mapped_column(TipoJson)
    # Avaliação inicial, feita por qualquer integrante da equipe
    respostas_iniciais: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    avaliador_inicial_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    avaliacao_inicial_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Avaliação do gestor, que define a nota final
    respostas_gestor: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    complemento_gestor: Mapped[str] = mapped_column(String(4000), default="")
    gestor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    avaliacao_gestor_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ciências da equipe no ateste (o nome da coluna vem da versão com assinantes indicados por papel)
    assinaturas: Mapped[list[Any]] = mapped_column(TipoJson, default=list)
    assinaturas_definidas_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # PDF gerado pelo sistema e a via assinada devolvida pela contratada
    pdf_gerado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    pdf_assinado_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A contratada pode pedir reconsideração uma única vez
    reconsideracoes: Mapped[int] = mapped_column(Integer, default=0)
    reconsideracao_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # E-mail do relatório de avaliação à contratada (enviado ao gerar o PDF), para devolução assinada
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_destinatarios: Mapped[list[Any]] = mapped_column(TipoJson, default=list, server_default=text("'[]'"))
    email_erro: Mapped[str | None] = mapped_column(Text)

    competencia: Mapped[Competencia] = relationship(back_populates="avaliacao")
    pdf_gerado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[pdf_gerado_anexo_id])
    pdf_assinado_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[pdf_assinado_anexo_id])
    reconsideracao_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[reconsideracao_anexo_id])


class NotaFiscalCompetencia(Base):
    """Nota fiscal juntada à competência (etapa 3): PDF, XML, valores lidos do XML e retenções conferidas.

    Uma medição pode ter várias notas (`ordem` 1, 2, …); o valor a pagar é a soma dos brutos.
    """
    __tablename__ = "contratos_competencias_notas_fiscais"
    __table_args__ = (UniqueConstraint("competencia_id", "ordem", name="uq_contratos_notas_fiscais_competencia_ordem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    xml_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    numero: Mapped[str] = mapped_column(String(100), default="")
    chave: Mapped[str | None] = mapped_column(String(60), index=True)
    valor_bruto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    # Retenções de tributos (sugeridas pelo XML e conferidas na etapa de retenção)
    retencao_ir: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    retencao_inss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    retencao_iss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    retencao_pis: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    retencao_cofins: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0))
    retencao_csll: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal(0), server_default=text("0"))
    dados_xml: Mapped[dict[str, Any] | None] = mapped_column(TipoJson)

    competencia: Mapped["Competencia"] = relationship(back_populates="notas_fiscais")
    anexo: Mapped[Anexo | None] = relationship(foreign_keys=[anexo_id])
    xml_anexo: Mapped[Anexo | None] = relationship(foreign_keys=[xml_anexo_id])

    @property
    def rotulo(self) -> str:
        """"NF 123" (ou "NF 2" pela ordem, se o XML não trouxe número)."""
        return f"NF {self.numero}" if self.numero else f"NF {self.ordem}"


TIPOS_DESPESA_VARIAVEL = ("nota_debito", "recibo", "outros")


class DespesaVariavel(Base):
    """Documento de despesa variável (nota de débito, recibo ou outros) juntado na etapa da nota fiscal.

    Não vai para a validação do Financeiro (retenção): fica só como documento juntado e entra no consolidado.
    """
    __tablename__ = "contratos_competencias_despesas_variaveis"
    __table_args__ = (
        UniqueConstraint("competencia_id", "ordem", name="uq_contratos_despesas_variaveis_competencia_ordem"),
        CheckConstraint(f"tipo IN ({_lista_sql(TIPOS_DESPESA_VARIAVEL)})", name="ck_contratos_despesas_variaveis_tipo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))
    numero: Mapped[str] = mapped_column(String(100), default="")
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))

    competencia: Mapped["Competencia"] = relationship(back_populates="despesas_variaveis")
    anexo: Mapped[Anexo | None] = relationship(foreign_keys=[anexo_id])

    @property
    def rotulo(self) -> str:
        """"Nota de débito 12", "Recibo 3" ou "Outros 1" (número informado ou posição)."""
        nome = {"nota_debito": "Nota de débito", "recibo": "Recibo", "outros": "Outros"}[self.tipo]
        return f"{nome} {self.numero or self.ordem}"


class RecusaNota(Base):
    """Recusa da(s) nota(s) fiscal(is) pelo Financeiro na retenção de tributos (etapa 4).

    A competência volta para a etapa da nota fiscal, onde se junta outra nota; o ciclo pode se repetir sem limite até a retenção ser
    conferida. `notas` guarda o retrato das notas recusadas ([{numero, valor_bruto, chave, anexo_id, xml_anexo_id}]): os PDFs
    ficam preservados mesmo depois de as notas ativas serem substituídas, para a trilha do consolidado.
    """

    __tablename__ = "contratos_competencias_recusas"
    __table_args__ = (UniqueConstraint("competencia_id", "ordem", name="uq_contratos_recusas_competencia_ordem"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    competencia_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contratos_competencias.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    justificativa: Mapped[str] = mapped_column(Text)
    recusada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    recusada_por_nome: Mapped[str] = mapped_column(String(250), default="")
    recusada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notas: Mapped[list[dict[str, Any]]] = mapped_column(TipoJson, default=list)
    # PDF da recusa, gerado pelo sistema (para juntar a um processo)
    pdf_anexo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    # E-mail à equipe e a todos os prepostos (obrigatório), com o PDF anexado
    email_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_ok: Mapped[bool | None] = mapped_column(Boolean)
    email_destinatarios: Mapped[list[str]] = mapped_column(TipoJson, default=list)
    email_erro: Mapped[str | None] = mapped_column(Text)

    competencia: Mapped[Competencia] = relationship(back_populates="recusas")
    pdf_anexo: Mapped[Anexo | None] = relationship()
