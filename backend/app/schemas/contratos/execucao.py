# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de checklists, formulários e competências.
"""Schemas da execução: checklists, formulários de avaliação, modelos globais e competências."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.contratos.empresas import Texto, TextoObrigatorio
from app.schemas.contratos.tipos import ValorFator, ValorMonetario, ValorQuantidade

Etapa = Literal["medicao", "avaliacao", "nota_fiscal", "cadin", "checklist", "consolidado", "ordem_bancaria", "concluida"]
SituacaoCompetencia = Literal["pendente", "disponivel", "em_andamento", "concluida"]


# ---------------------------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------------------------

class GravacaoDocumentoChecklist(BaseModel):
    nome: TextoObrigatorio = Field(..., max_length=500)
    observacao: Texto = Field("", max_length=1000)
    obrigatorio: bool = Field(True, description="Obrigatório precisa estar anexado para concluir a etapa do checklist; opcional, não.")


class GravacaoChecklist(BaseModel):
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[GravacaoDocumentoChecklist] = Field(..., min_length=1, description="Documentos mensais, na ordem.")


class LeituraDocumentoChecklist(BaseModel):
    id: uuid.UUID
    ordem: int
    nome: str
    observacao: str
    obrigatorio: bool


class LeituraChecklist(BaseModel):
    id: uuid.UUID
    versao: int
    nome: str
    ativo: bool
    itens: list[LeituraDocumentoChecklist]
    criado_por_nome: str
    criado_em: datetime
    ativado_em: datetime | None


# ---------------------------------------------------------------------------------------------
# Formulário de avaliação
# ---------------------------------------------------------------------------------------------

class NotaEscala(BaseModel):
    valor: Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)]
    legenda: TextoObrigatorio = Field(..., max_length=100)


class FaixaLiberacao(BaseModel):
    minimo: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
    maximo: Annotated[Decimal | None, Field(None, ge=0, max_digits=8, decimal_places=2)] = Field(None, description="Nulo = sem teto.")
    percentual: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] = Field(..., description="% do pagamento liberado.")
    notas_zero: int | None = Field(
        None, ge=1, le=100,
        description="Também aplica a faixa quando algum grupo tiver ao menos esta quantidade de notas mínimas da escala "
        "(nota 0 no modelo padrão), qualquer que seja a nota final. Nulo = só pela nota.",
    )


class ItemFormulario(BaseModel):
    id: str | None = Field(None, description="Gerado pela API quando vazio.")
    nome: TextoObrigatorio = Field(..., max_length=300)
    descricao: Texto = Field("", max_length=1000)
    peso: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)] = Field(..., description="% dentro do grupo.")


class GrupoFormulario(BaseModel):
    id: str | None = None
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[ItemFormulario] = Field(..., min_length=1)


class DefinicaoFormulario(BaseModel):
    escala: list[NotaEscala] = Field(..., min_length=2, description="Notas em ordem crescente.")
    faixas: list[FaixaLiberacao] = Field(..., min_length=1)
    grupos: list[GrupoFormulario] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _regras(self) -> "DefinicaoFormulario":
        valores = [n.valor for n in self.escala]
        if valores != sorted(valores) or len(set(valores)) != len(valores):
            raise ValueError("a escala de notas deve estar em ordem crescente, sem repetição")
        for faixa in self.faixas:
            if faixa.maximo is not None and faixa.maximo < faixa.minimo:
                raise ValueError("em cada faixa, a nota máxima deve ser maior ou igual à mínima")
        for grupo in self.grupos:
            if sum(i.peso for i in grupo.itens) != 100:
                raise ValueError(f"a soma dos pesos do grupo \"{grupo.nome}\" deve ser 100%")
        return self


class GravacaoFormulario(BaseModel):
    nome: TextoObrigatorio = Field(..., max_length=300)
    definicao: DefinicaoFormulario


class LeituraFormulario(BaseModel):
    id: uuid.UUID
    versao: int
    nome: str
    ativo: bool
    definicao: dict[str, Any]
    criado_por_nome: str
    criado_em: datetime
    ativado_em: datetime | None


# ---------------------------------------------------------------------------------------------
# Modelos globais
# ---------------------------------------------------------------------------------------------

class GravacaoModelo(BaseModel):
    tipo: Literal["checklist", "formulario"]
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[GravacaoDocumentoChecklist] | None = Field(None, description="Obrigatório para `checklist`.")
    definicao: DefinicaoFormulario | None = Field(None, description="Obrigatório para `formulario`.")
    ativo: bool = True

    @model_validator(mode="after")
    def _conteudo(self) -> "GravacaoModelo":
        if self.tipo == "checklist" and not self.itens:
            raise ValueError("o modelo de checklist precisa de ao menos um documento")
        if self.tipo == "formulario" and self.definicao is None:
            raise ValueError("o modelo de formulário precisa da definição")
        return self


class LeituraModelo(BaseModel):
    id: uuid.UUID
    tipo: str
    nome: str
    conteudo: dict[str, Any]
    ativo: bool
    atualizado_em: datetime


# ---------------------------------------------------------------------------------------------
# Competências
# ---------------------------------------------------------------------------------------------

class Requisitos(BaseModel):
    prontos: bool
    pendencias: list[str] = Field(..., description="Motivos que impedem gerar as competências.")


class ResumoCompetencia(BaseModel):
    id: uuid.UUID
    competencia: date
    tipo: str = Field("regular", description="`regular` ou `diferenca_reajuste` (complementar, paga a diferença de um reajuste retroativo).")
    parte: int | None = Field(None, description="1 ou 2 quando o mês se divide entre duas vigências; nulo nos demais casos.")
    identificador: str = Field(..., description="Chave da rota da tela: `AAAA-MM`, `AAAA-MM-1`, `AAAA-MM-2` ou `AAAA-MM-dif`.")
    rotulo: str = Field(..., description="Rótulo para exibição. Ex.: `01/2027 · 1ª parte`.")
    sequencia_vigencia: int
    periodo_inicio: date
    periodo_fim: date
    situacao: SituacaoCompetencia
    etapa_atual: Etapa
    valor_medicao: ValorMonetario | None = Field(None, description="Nulo enquanto a medição não foi salva.")
    possui_avaliacao: bool


class GrupoCompetencias(BaseModel):
    sequencia_vigencia: int
    inicio: date
    fim: date
    competencias: list[ResumoCompetencia]


class PainelExecucao(BaseModel):
    requisitos: Requisitos
    geradas: bool
    grupos: list[GrupoCompetencias]


class LeituraItemMedicao(BaseModel):
    id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str
    calcula_pro_rata: bool
    valor_unitario: ValorMonetario
    fator_meses: ValorFator
    quantidade_prevista: ValorQuantidade
    quantidade_medida: Annotated[Decimal, Field(description="Até 10 casas.")]
    subtotal: ValorMonetario


class LeituraCiencia(BaseModel):
    usuario_id: int | None
    nome: str
    papel: str
    registrada_em: datetime


class LeituraArquivo(BaseModel):
    anexo_id: uuid.UUID
    nome: str
    tamanho: int
    enviado_em: datetime


class LeituraMemoria(BaseModel):
    versao: int
    criada_em: datetime
    arquivo: LeituraArquivo


class NotaSelecionada(BaseModel):
    id: uuid.UUID
    numero: str
    saldo: ValorMonetario = Field(..., description="Saldo contábil da NE (valor original − pagamentos + estornos).")
    saldo_livre: ValorMonetario = Field(..., description="Saldo menos o comprometido por outras competências medidas e ainda não pagas.")


class LeituraNotaFiscal(BaseModel):
    numero: str
    arquivo: LeituraArquivo | None
    valor_bruto: ValorMonetario | None
    retencao_ir: ValorMonetario
    retencao_inss: ValorMonetario
    retencao_iss: ValorMonetario
    retencao_pis: ValorMonetario
    retencao_cofins: ValorMonetario
    valor_liquido: ValorMonetario


class LeituraConsultaCadin(BaseModel):
    id: uuid.UUID
    possui_pendencia: bool
    pendencia: str
    texto_notificacao: str
    certidao: LeituraArquivo
    email: LeituraArquivo | None
    criado_por_nome: str
    criado_em: datetime


class LeituraDocumentoMensal(BaseModel):
    id: uuid.UUID
    ordem: int
    nome: str
    observacao: str
    obrigatorio: bool
    arquivo: LeituraArquivo | None


class RespostaAvaliacao(BaseModel):
    item_id: str
    nota: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
    justificativa: Texto = Field("", max_length=4000)


class AssinaturaAteste(BaseModel):
    papel: Literal["gestor", "fiscal_administrativo", "fiscal_tecnico"]
    usuario_id: int
    nome: str = ""
    ciencia_em: datetime | None = None


class LeituraAvaliacao(BaseModel):
    definicao: dict[str, Any]
    respostas_iniciais: list[RespostaAvaliacao]
    avaliacao_inicial_em: datetime | None
    respostas_gestor: list[RespostaAvaliacao]
    complemento_gestor: str
    avaliacao_gestor_em: datetime | None
    nota_final: ValorMonetario | None
    percentual_liberado: ValorMonetario | None
    assinaturas: list[AssinaturaAteste]
    assinaturas_definidas_em: datetime | None
    pdf_gerado: LeituraArquivo | None
    pdf_assinado: LeituraArquivo | None
    concluida_em: datetime | None
    reconsideracoes: int
    reconsideracao: LeituraArquivo | None


class DetalheCompetencia(ResumoCompetencia):
    contrato_id: uuid.UUID
    contrato_numero: str
    etapas: list[Etapa] = Field(..., description="Etapas desta competência, em ordem (sem `avaliacao` se não houver formulário).")
    pode_editar: bool
    integra_equipe: bool = Field(..., description="O usuário pode registrar ciência.")
    liberada: bool = Field(..., description="O período terminou; a medição pode ser feita.")
    itens: list[LeituraItemMedicao]
    total_previsto: ValorMonetario
    total_medido: ValorMonetario
    notas_selecionadas: list[NotaSelecionada]
    notas_disponiveis: list[NotaSelecionada] = Field(..., description="NEs do contrato com saldo.")
    ciencias: list[LeituraCiencia]
    ciencias_minimas: int
    memorias: list[LeituraMemoria]
    medicao_concluida_em: datetime | None
    avaliacao: LeituraAvaliacao | None
    percentual_autorizado: ValorMonetario = Field(..., description="% liberado pela avaliação (100 sem avaliação).")
    valor_autorizado: ValorMonetario = Field(..., description="Total medido × % liberado pela avaliação (sugestão do valor da NF).")
    valor_a_pagar: ValorMonetario = Field(
        ..., description="Valor que a OB debita nas NEs apontadas: NF + NF adicional (brutos) depois da etapa da NF; antes, o valor autorizado."
    )
    avisos: list[str] = Field(default_factory=list, description="Alertas da medição (ex.: item sob demanda acima do saldo da vigência).")
    reaberturas_permitidas: bool = Field(False, description="O usuário pode reabrir etapas (SuperRoot ou gestor vigente do contrato).")
    nota_fiscal: LeituraNotaFiscal | None
    nota_fiscal_adicional: LeituraNotaFiscal | None
    nf_recebida_em: date | None
    prazo_pagamento_dias: int | None
    vencimento_pagamento: date | None = Field(..., description="Recebimento da NF + prazo (dias corridos).")
    origem_valor_nf: str | None
    nf_concluida_em: datetime | None
    consultas_cadin: list[LeituraConsultaCadin]
    documentos: list[LeituraDocumentoMensal]
    consolidado: LeituraArquivo | None
    ordem_bancaria: LeituraArquivo | None
    concluida_em: datetime | None


class ItemMedidoGravacao(BaseModel):
    id: uuid.UUID
    quantidade_medida: Annotated[Decimal, Field(ge=0, max_digits=28, decimal_places=10)]


class GravacaoMedicao(BaseModel):
    itens: list[ItemMedidoGravacao]
    notas_empenho_ids: list[uuid.UUID] = Field(..., min_length=1, description="NEs em ordem de consumo.")


class ConclusaoMedicao(BaseModel):
    notas_empenho_ids: list[uuid.UUID] = Field(..., min_length=1, description="Deve ser igual à seleção salva.")


class GravacaoAvaliacaoInicial(BaseModel):
    respostas: list[RespostaAvaliacao]


class GravacaoAvaliacaoGestor(BaseModel):
    respostas: list[RespostaAvaliacao]
    complemento: Texto = Field("", max_length=4000)


class GravacaoAssinaturas(BaseModel):
    assinaturas: list[AssinaturaAteste] = Field(..., min_length=1)


class Reabertura(BaseModel):
    etapa: Etapa = Field(..., description="Etapa que volta a ficar aberta (anteriores à atual).")
    justificativa: TextoObrigatorio = Field(..., max_length=2000)
