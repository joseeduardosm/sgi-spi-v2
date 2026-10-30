# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de prorrogação, reajuste e aditamento/supressão.
"""Schemas de prorrogação, reajuste e aditamento/supressão.

Convenção: `Gravacao*`/`Abertura*` = entrada vinda do frontend; `Leitura*`/`Painel*` = saída.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.contratos.empresas import Texto
from app.schemas.contratos.execucao import LeituraArquivo, LeituraCiencia
from app.schemas.contratos.tipos import ValorFator, ValorMonetario, ValorQuantidade, ValorUnitario

# Quantidade de entrada: não negativa, até 4 casas decimais
Quantidade = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
# Como os itens sob demanda são planejados na nova vigência:
# saldo que sobrou, repetir o limite inicial ou informar manualmente
RegraSobDemanda = Literal["saldo_remanescente", "repetir_inicial", "manual"]
# Campos do parecer da prorrogação; se todos estiverem vazios, não há PDF de parecer
CAMPOS_PARECER = ("avaliacao_geral", "resumo_qualidade", "historico_ocorrencias", "reclamacoes", "atendimento_chamados", "parecer")


# ---------------------------------------------------------------------------------------------
# Prorrogação
# ---------------------------------------------------------------------------------------------

class PlanoItemGravacao(BaseModel):
    """Planejamento de um item sob demanda na nova vigência (limite e quantidades por mês)."""
    item_id: uuid.UUID
    limite: Quantidade = Field(..., description="Limite na nova vigência (≤ quantidade original).")
    apontamentos: dict[date, Quantidade] = Field(default_factory=dict, description="Quantidade por mês da nova vigência.")


class GravacaoProrrogacao(BaseModel):
    """Corpo do `PUT /prorrogacao` (rascunho). Todos os campos são opcionais até o registro."""
    meses: int | None = Field(None, ge=1, le=600, description="Prazo da prorrogação.")
    regra_sob_demanda: RegraSobDemanda = "saldo_remanescente"
    plano_sob_demanda: list[PlanoItemGravacao] = Field(default_factory=list)
    calculo_mes_quebrado: Literal["pro_rata", "integral"] | None = Field(
        None, description="Meses quebrados da nova vigência (começa ou termina no meio do mês): `pro_rata` (só os dias da nova vigência) ou `integral` "
                          "(o mês inteiro), uma escolha para todos. Vale só para a memória de cálculo e o valor da prorrogação. Nulo mantém a escolha atual.")
    # Campos do parecer: a tela nova não os envia mais; nulo mantém o que estava gravado
    avaliacao_geral: Texto | None = None
    resumo_qualidade: Texto | None = None
    historico_ocorrencias: Texto | None = None
    reclamacoes: Texto | None = None
    atendimento_chamados: Texto | None = None
    parecer: Texto | None = None


class GravacaoDadosMinuta(BaseModel):
    """Corpo do `PUT /prorrogacao/dados-minuta`: o que a equipe digita para completar as minutas (placeholder → texto)."""
    dados: dict[str, str] = Field(default_factory=dict, description="Placeholder (sem o `#`) → texto digitado. Vale também para corrigir um valor que o SGI calculou. Vazio apaga.")


class LeituraMinutaResumo(BaseModel):
    """Um documento da prorrogação e o que ainda falta digitar nele."""
    variante: str
    titulo: str
    modelo_ativo: bool = Field(..., description="Falso = não há modelo ativo desta variante em Contratos › Modelos.")
    lacunas: list[str] = Field(..., description="Rótulo de cada dado que o texto pede e ainda não existe.")


class LeituraMinuta(BaseModel):
    """Texto de uma minuta preenchido, em HTML, para copiar para o SEI."""
    variante: str
    titulo: str
    html: str
    lacunas: list[str]


class CampoMinuta(BaseModel):
    """Dado da minuta: o que o SGI calculou ou o que a equipe digita."""
    nome: str
    rotulo: str
    descricao: str
    digitado: bool = Field(..., description="Verdadeiro = o SGI não sabe; a equipe digita. Falso = calculado, mas pode ser corrigido.")
    multilinha: bool = False
    valor: str = Field(..., description="O que a equipe digitou (vazio = vale o valor calculado ou fica a lacuna).")
    calculado: str = Field(..., description="O que o SGI calculou (vazio quando não sabe).")


class LeituraMinutas(BaseModel):
    """Passo "Minutas" da prorrogação: os documentos que podem ser gerados e os dados que os completam."""
    documentos: list[LeituraMinutaResumo]
    campos: list[CampoMinuta]


RespostaParecer = Literal["sim", "nao", "na", ""]


class RespostaEnquadramento(BaseModel):
    """Resposta da equipe a um item do checklist do Parecer Referencial."""
    resposta: RespostaParecer = Field("", description="`sim`, `nao`, `na` (não se aplica) ou vazio (vale a conferência automática, se houver).")
    doc: str = Field("", max_length=300, description="Documento e página (ex.: doc. nº 123456, p. 4).")
    obs: str = Field("", max_length=1000)


class GravacaoEnquadramento(BaseModel):
    """Corpo do `PUT /prorrogacao/enquadramento`: respostas por número do item (1 a 37); substitui as anteriores."""
    respostas: dict[int, RespostaEnquadramento] = Field(default_factory=dict)


class ConferenciaAutomatica(BaseModel):
    """O que o SGI conferiu sozinho num item (com a conta, para a equipe poder contestar)."""
    resultado: Literal["sim", "nao", "na"]
    explicacao: str


class ItemEnquadramento(BaseModel):
    numero: int
    texto: str
    referencia: str
    automatica: ConferenciaAutomatica | None
    resposta: RespostaParecer
    doc: str
    obs: str
    efetivo: RespostaParecer = Field(..., description="O que vale: a resposta da equipe; sem ela, a conferência automática; vazio = pendente.")
    contestado: bool = Field(..., description="A equipe respondeu o contrário do que o SGI conferiu.")


class GrupoEnquadramento(BaseModel):
    nome: str
    itens: list[ItemEnquadramento]


class LeituraEnquadramento(BaseModel):
    """Checklist do Parecer Referencial da prorrogação, com o resumo e o aviso de análise jurídica."""
    grupos: list[GrupoEnquadramento]
    total: int
    atendidos: int = Field(..., description="Itens `sim` ou `na`.")
    nao_atendidos: int
    pendentes: int
    precisa_analise_juridica: bool = Field(..., description="Algum item `nao`: o caso sai do Parecer Referencial e precisa da Consultoria Jurídica.")
    motivos: list[str] = Field(..., description="Os itens não atendidos, em texto.")


class GravacaoPosAssinatura(BaseModel):
    """Corpo do `PUT /prorrogacoes/{id}/pos-assinatura`: o que acontece depois da assinatura (substitui o anterior; vazio apaga)."""
    pncp_publicado_em: date | None = None
    pncp_numero: str = Field("", max_length=100, description="Número/link do registro no PNCP.")
    doe_publicado_em: date | None = None
    garantia_comprovada_em: date | None = None
    garantia_enviada_dof_em: date | None = None
    contratos_gov_atualizado_em: date | None = Field(None, description="Campo \"Fiscalização e Gestão Contratual\" do Contratos.gov/AUDESP atualizado.")
    dados_garantia: dict[str, str] = Field(default_factory=dict, description="Dados digitados das planilhas de garantia (responsável, NL, DARE…); chaves em `CAMPOS_GARANTIA`.")


class PlanoItemLeitura(BaseModel):
    """Item sob demanda na tela de prorrogação, com as referências para o usuário decidir o limite."""
    item_id: uuid.UUID
    ordem: int
    descricao: str
    quantidade_original: ValorQuantidade
    saldo_remanescente: ValorQuantidade = Field(..., description="Limite da vigência atual − executado nela.")
    limite: ValorQuantidade
    apontamentos: dict[str, ValorQuantidade]
    saldo: ValorQuantidade


class MesMemoriaProrrogacao(BaseModel):
    """Um mês da nova vigência na memória de cálculo."""
    competencia: str = Field(..., description="MM/AAAA.")
    inicio: date
    fim: date
    quebrado: bool = Field(..., description="A nova vigência começa ou termina no meio deste mês.")
    continuos: ValorMonetario = Field(..., description="Itens contínuos: quantidade mensal × preço × fator do mês (pela escolha nos meses quebrados).")
    sob_demanda: ValorMonetario = Field(..., description="Sob demanda planejado para o mês × preço.")
    total: ValorMonetario


class MesQuebradoProrrogacao(BaseModel):
    """Mês quebrado da nova vigência com o valor dos contínuos em cada opção, para o gestor comparar."""
    competencia: str
    inicio: date
    fim: date
    dias: int = Field(..., description="Dias comerciais (30/360) da nova vigência no mês.")
    pro_rata: ValorMonetario
    integral: ValorMonetario


class TotalAnoProrrogacao(BaseModel):
    ano: int
    total: ValorMonetario


class ResumoMemoriaProrrogacao(BaseModel):
    """Memória de cálculo da prorrogação (só com o prazo informado)."""
    meses: list[MesMemoriaProrrogacao]
    totais_por_ano: list[TotalAnoProrrogacao]
    total: ValorMonetario = Field(..., description="Valor da nova vigência, pela escolha gravada (sem escolha, pro rata).")
    meses_quebrados: list[MesQuebradoProrrogacao]
    total_pro_rata: ValorMonetario
    total_integral: ValorMonetario
    calculo_mes_quebrado: Literal["pro_rata", "integral"] | None
    precisa_escolher: bool = Field(..., description="Há mês quebrado sem escolha: a memória não é gerada até a escolha.")


class DocumentoProrrogacaoLeitura(BaseModel):
    """Documento do checklist da prorrogação (do modelo "Checklist Prorrogação" ou incluído durante o processo)."""
    id: uuid.UUID
    ordem: int
    nome: str
    observacao: str
    obrigatorio: bool
    arquivo: LeituraArquivo | None
    incluido_no_processo: bool
    incluido_por_nome: str | None = None
    incluido_em: datetime | None = None


class LeituraProcessoProrrogacao(BaseModel):
    """Tudo o que a tela de prorrogação precisa para se montar."""
    id: uuid.UUID | None = Field(None, description="Nulo = ainda não há rascunho salvo.")
    vigencia_atual_inicio: date
    vigencia_atual_fim: date
    meses: int | None
    nova_vigencia_inicio: date
    nova_vigencia_fim: date | None
    meses_disponiveis: int = Field(..., description="Vigência máxima − soma das vigências registradas.")
    meses_nova_vigencia: list[date]
    regra_sob_demanda: RegraSobDemanda
    itens_sob_demanda: list[PlanoItemLeitura]
    avaliacao_geral: str
    resumo_qualidade: str
    historico_ocorrencias: str
    reclamacoes: str
    atendimento_chamados: str
    parecer: str
    possui_parecer: bool = Field(..., description="Algum campo do parecer preenchido: o PDF do parecer será emitido.")
    ciencias: list[LeituraCiencia]
    relatorio: LeituraArquivo | None
    exige_checklist_ativo: bool
    pode_editar: bool
    integra_equipe: bool
    memoria: ResumoMemoriaProrrogacao | None = Field(None, description="Memória de cálculo da nova vigência (nula sem prazo).")
    memorias: list["LeituraMemoriaVersao"] = Field(default_factory=list, description="Versões geradas da memória (PDF e XLSX).")
    memoria_atualizada: bool = Field(False, description="A última versão gerada corresponde aos dados de agora (exigido para registrar).")
    checklist: list[DocumentoProrrogacaoLeitura] = Field(default_factory=list, description="Checklist da prorrogação: ponto de partida do modelo ativo, mais os incluídos.")
    obrigatorios_pendentes: int = Field(0, description="Documentos obrigatórios do checklist ainda sem PDF (impedem registrar).")


class LeituraProrrogacao(BaseModel):
    """Prorrogação já registrada (histórico)."""
    id: uuid.UUID
    meses: int
    assinada_em: date
    numero_termo: str
    fim_anterior: date
    data_inicio: date
    data_fim: date
    codigo_documento: int | None
    precisa_analise_juridica: bool = Field(False, description="No registro, o checklist do Parecer Referencial tinha item não atendido.")
    pncp_prazo_ate: date | None = Field(None, description="Último dia útil para divulgar no PNCP (assinatura + 20 dias úteis na licitação, 10 na contratação direta); vazio se o contrato não tem modalidade.")
    pncp_publicado_em: date | None = None
    pncp_numero: str = ""
    situacao_pncp: Literal["sem_prazo", "publicado", "no_prazo", "vencido"] = "sem_prazo"
    dias_uteis_pncp: int | None = Field(None, description="Dias úteis que faltam para o prazo do PNCP (`no_prazo`); nulo nos demais casos.")
    doe_publicado_em: date | None = None
    exige_garantia: bool = False
    garantia_comprovada_em: date | None = None
    garantia_enviada_dof_em: date | None = None
    garantia_pendente: bool = Field(False, description="O contrato exige garantia e a comprovação da renovação ainda não foi registrada.")
    dados_garantia: dict[str, str] = Field(default_factory=dict)
    contratos_gov_atualizado_em: date | None = None
    termo: LeituraArquivo | None
    relatorio: LeituraArquivo | None
    pode_desfazer: bool


class LeituraVigenciaRetroativa(BaseModel):
    """Vigência retroativa já cadastrada (da mais antiga para a mais recente)."""
    id: uuid.UUID
    sequencia: int = Field(..., description="Número da vigência (1 = a mais antiga do contrato).")
    meses: int
    assinada_em: date
    numero_termo: str
    data_inicio: date
    data_fim: date
    codigo_documento: int | None
    termo: LeituraArquivo | None
    reajustada: bool = Field(..., description="Já tem reajuste retroativo concluído (os preços dela foram definidos).")
    pode_desfazer: bool = Field(..., description="Só a vigência retroativa mais antiga, sem medição, reajuste ou alteração.")
    motivo_bloqueio: str = Field("", description="Por que não pode ser desfeita (vazio quando pode).")


# ---------------------------------------------------------------------------------------------
# Reajuste
# ---------------------------------------------------------------------------------------------

class AberturaReajuste(BaseModel):
    """Corpo do `POST /reajustes`: qual vigência e a partir de que data (ou, na forma antiga, de que mês)."""
    sequencia_vigencia: int = Field(..., ge=1)
    retroativo: bool = Field(
        False, description="Reajuste retroativo: define os preços de uma vigência retroativa deflacionando os da vigência seguinte. "
        "A data de efeito é o início da vigência seguinte (não precisa ser informada)."
    )
    data_efeito: date | None = Field(
        None, description="Data a partir da qual os novos valores valem (qualquer dia da vigência). O mês dessa data é pago proporcionalmente "
        "aos dias de cada preço. Em contratos de periodicidade diferente de mensal, vale o 1º dia do mês."
    )
    mes_referencia: date | None = Field(
        None, description="Forma antiga: primeiro mês com os novos valores (qualquer dia; vale o dia 1). Ignorado se `data_efeito` vier."
    )

    @model_validator(mode="after")
    def _uma_das_datas(self) -> "AberturaReajuste":
        if self.data_efeito is None and self.mes_referencia is None and not self.retroativo:
            raise ValueError("Informe a data a partir da qual os novos valores valem (`data_efeito`).")
        return self


class ItemReajusteGravacao(BaseModel):
    """Percentual (positivo = reajuste, negativo = desconto) aplicado a um item e, opcionalmente, um teto para o novo preço."""
    item_id: uuid.UUID
    indice_percentual: Annotated[Decimal, Field(gt=-100, le=1000, max_digits=18, decimal_places=8)] = Field(
        ..., description="Em pontos percentuais: 2 = reajuste de 2%; −3 = desconto de 3%; 0 = item sem alteração. Maior que −100."
    )
    valor_referencial: Annotated[Decimal | None, Field(None, ge=0, max_digits=18, decimal_places=4)] = Field(
        None, description="Teto opcional do preço reajustado (útil no reajuste positivo)."
    )


class GravacaoMemoriaReajuste(BaseModel):
    """Corpo do `PUT /reajustes/{id}/memoria`."""
    itens: list[ItemReajusteGravacao]
    calculo_mes_quebrado: Literal["pro_rata", "integral"] | None = Field(
        None,
        description="Como calcular os meses quebrados pela data de efeito (`resumo_meses.meses_quebrados`), uma escolha para todos os meses e itens: "
                    "`pro_rata` (dias antes do efeito sem reajuste, a partir dele reajustados) ou `integral` (mês inteiro reajustado). "
                    "Nulo mantém a escolha atual. `400` se o reajuste não tem mês quebrado.",
        examples=["pro_rata"],
    )


class ItemReajusteLeitura(BaseModel):
    """Item na tela de reajuste: preço atual, índice e preço reajustado."""
    item_id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str
    quantidade_mensal: ValorQuantidade
    valor_unitario_atual: ValorUnitario
    indice_percentual: ValorFator
    valor_referencial: ValorUnitario | None
    valor_unitario_reajustado: ValorUnitario
    subtotal_reajustado: ValorMonetario


class LeituraMemoriaVersao(BaseModel):
    """Uma versão gerada da memória de cálculo do reajuste (PDF e XLSX)."""
    versao: int
    criada_em: datetime
    pdf: LeituraArquivo
    xlsx: LeituraArquivo


class AbatimentoLeitura(BaseModel):
    """Parte do crédito de desconto abatida numa competência."""
    competencia: str = Field(..., description="Rótulo da competência (MM/AAAA).")
    identificador: str = Field(..., description="Identificador da rota da execução (`AAAA-MM`).")
    medida: bool = Field(..., description="Verdadeiro quando a medição dessa competência já foi concluída.")
    valor: ValorMonetario


class MesEmHaver(BaseModel):
    """Um mês medido a partir da referência e o que ficou em haver com o reajuste."""
    competencia: str = Field(..., description="Rótulo da competência (MM/AAAA).")
    identificador: str = Field(..., description="Identificador da rota da execução (`AAAA-MM`).")
    paga: bool = Field(..., description="`true` com a OB concluída; `false` quando o mês está medido e aguarda a OB.")
    valor_pago: ValorMonetario = Field(..., description="Valor pago nos dias com o novo preço (quantidade × preço pago).")
    valor_reajustado: ValorMonetario = Field(..., description="O mesmo, com o preço reajustado.")
    em_haver: ValorMonetario = Field(..., description="Reajustado menos pago (negativo = crédito da SPI).")


class TrechoMesQuebrado(BaseModel):
    """Um período do item no mês quebrado: os dias, a quantidade proporcional e o valor unitário usado."""
    inicio: date
    fim: date
    dias: int = Field(..., description="Dias comerciais (30/360) do período.")
    reajustado: bool = Field(..., description="`true` se o período usa o valor reajustado; `false`, o valor sem reajuste.")
    quantidade: ValorQuantidade
    valor_unitario: ValorUnitario
    valor: ValorMonetario


class ItemMesQuebrado(BaseModel):
    """Um item do mês quebrado numa das opções: períodos, o que foi pago, o devido e o em haver."""
    ordem: int
    descricao: str
    quantidade_medida: ValorQuantidade
    valor_pago: ValorMonetario = Field(..., description="Quantidade medida × valor pago na medição.")
    trechos: list[TrechoMesQuebrado]
    devido: ValorMonetario = Field(..., description="Soma dos períodos.")
    em_haver: ValorMonetario = Field(..., description="Devido menos pago.")


class OpcaoMesQuebrado(BaseModel):
    """Uma opção de cálculo (pro rata ou integral) de um mês quebrado."""
    itens: list[ItemMesQuebrado]
    valor_pago: ValorMonetario
    devido: ValorMonetario
    em_haver: ValorMonetario


class MesQuebradoReajuste(BaseModel):
    """Mês medido que contém a data de efeito, com as duas opções calculadas para comparação."""
    competencia: str = Field(..., description="Competência como `AAAA-MM`.")
    rotulo: str = Field(..., description="Competência por extenso, para exibição (ex.: `11/2025`).")
    periodo_inicio: date
    periodo_fim: date = Field(..., description="Último dia medido (no mês do fim da vigência, o último dia dela).")
    opcoes: dict[Literal["pro_rata", "integral"], OpcaoMesQuebrado]


class ResumoMesesReajuste(BaseModel):
    """Resumo executivo da memória mês a mês (só em elaboração; reajuste retroativo vem sem meses)."""
    meses: list[MesEmHaver] = Field(default_factory=list, description="Meses medidos a partir da referência (OB paga ou aguardando), em ordem.")
    total_em_haver: ValorMonetario = Field(..., description="Soma do que ficou em haver em todos os meses medidos (= diferença retroativa).")
    meses_quebrados: list[MesQuebradoReajuste] = Field(default_factory=list, description="Meses medidos que contêm a data de efeito, com as duas opções de cálculo.")
    diferenca_pro_rata: ValorMonetario = Field(..., description="Diferença retroativa inteira com os meses quebrados em pro rata.")
    diferenca_integral: ValorMonetario = Field(..., description="Diferença retroativa inteira com os meses quebrados integrais.")
    calculo_mes_quebrado: Literal["pro_rata", "integral"] | None = Field(None, description="Escolha gravada; nulo = ainda não escolhida.")
    precisa_escolher: bool = Field(False, description="`true` quando há mês quebrado sem escolha: a memória (PDF/XLSX) só é gerada depois dela.")


class LeituraReajuste(BaseModel):
    """Reajuste completo, em elaboração ou já encerrado."""
    resumo_meses: ResumoMesesReajuste | None = Field(None, description="Memória mês a mês resumida (só em elaboração).")
    id: uuid.UUID
    situacao: Literal["rascunho", "concluido", "cancelado"]
    retroativo: bool = Field(False, description="Reajuste retroativo (volta no tempo): o preço novo é o da vigência retroativa e o piso é o valor referencial.")
    sequencia_vigencia: int
    vigencia_inicio: date
    vigencia_fim: date
    mes_referencia: date
    data_efeito: date = Field(..., description="Data a partir da qual os novos valores valem (o mês dela é pago proporcionalmente aos dias de cada preço).")
    competencias_recalculadas: int = Field(..., description="Competências não medidas a partir do mês de referência (recebem o novo preço).")
    competencias_com_diferenca: int = Field(
        0, description="Competências já medidas a partir do mês de referência: a diferença de preço delas é acertada na conclusão."
    )
    diferenca_retroativa: ValorMonetario = Field(
        Decimal(0), description="Soma de quantidade medida × (preço novo − preço pago) das competências já medidas: prévia no "
        "rascunho, valor gravado depois de concluído. > 0: competência de diferença a pagar; < 0: crédito da SPI abatido nas próximas medições.",
    )
    competencia_credito: str | None = Field(
        None, description="Rascunho com diferença negativa: rótulo (MM/AAAA) da competência que receberá o crédito; nulo se não houver competência a medir."
    )
    abatimentos: list[AbatimentoLeitura] = Field(default_factory=list, description="Concluído com desconto retroativo: onde o crédito foi (ou será) abatido.")
    credito_pendente: ValorMonetario = Field(Decimal(0), description="Parte do crédito ainda sem competência a medir (vai para a próxima gerada).")
    competencia_diferenca: str | None = Field(
        None, description="Identificador (`AAAA-MM-dif`) da competência complementar gerada na conclusão, se houver."
    )
    itens: list[ItemReajusteLeitura]
    base_atual: ValorMonetario
    base_reajustada: ValorMonetario
    valor_global_atual: ValorMonetario
    valor_global_reajustado: ValorMonetario
    evidencia: LeituraArquivo | None
    apostilamento: LeituraArquivo | None
    memorias: list[LeituraMemoriaVersao]
    concluido_em: datetime | None
    cancelado_em: datetime | None


class VigenciaDisponivel(BaseModel):
    """Vigência que pode ser escolhida ao abrir um reajuste ou alteração."""
    sequencia: int
    inicio: date
    fim: date


class PainelReajuste(BaseModel):
    """Resposta das rotas de reajuste: o que está em andamento, as opções e o histórico."""
    em_andamento: LeituraReajuste | None
    vigencias_disponiveis: list[VigenciaDisponivel] = Field(..., description="Vigências ainda sem reajuste concluído.")
    vigencias_retroativas_disponiveis: list[VigenciaDisponivel] = Field(
        default_factory=list, description="Vigências retroativas que aceitam reajuste retroativo agora (da mais recente para trás, uma por vez)."
    )
    historico: list[LeituraReajuste]
    pode_editar: bool


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão
# ---------------------------------------------------------------------------------------------

class AberturaAlteracao(BaseModel):
    """Corpo do `POST /alteracoes`: tipo, vigência e mês de efeito."""
    tipo: Literal["aditamento", "supressao"]
    sequencia_vigencia: int = Field(..., ge=1)
    mes_efeito: date = Field(..., description="Primeiro mês com as novas quantidades (gravado como dia 1).")


class ItemAlteracaoGravacao(BaseModel):
    """Nova quantidade de um item na alteração."""
    item_id: uuid.UUID
    quantidade_nova: Quantidade = Field(..., description="Contínuo: nova quantidade mensal; sob demanda: novo limite da vigência.")


class GravacaoQuantitativos(BaseModel):
    """Corpo do `PUT /alteracoes/{id}/quantitativos`."""
    itens: list[ItemAlteracaoGravacao]


class ItemAlteracaoLeitura(BaseModel):
    """Item na tela de alteração, com o impacto em R$ e o alerta de ficar abaixo do executado."""
    item_id: uuid.UUID
    ordem: int
    descricao: str
    tipo: str
    valor_unitario: ValorUnitario
    quantidade_original: ValorQuantidade
    quantidade_executada: ValorQuantidade
    quantidade_nova: ValorQuantidade
    impacto_valor: ValorMonetario
    abaixo_do_executado: bool


class LeituraAlteracao(BaseModel):
    """Alteração completa, com percentuais, documentos e ciências."""
    id: uuid.UUID
    tipo: Literal["aditamento", "supressao"]
    situacao: Literal["rascunho", "aguardando_ciencias", "concluida", "cancelada"]
    sequencia_vigencia: int
    vigencia_inicio: date
    vigencia_fim: date
    mes_efeito: date
    meses_restantes: ValorFator = Field(..., description="Meses (com fração) do mês de efeito ao fim da vigência.")
    itens: list[ItemAlteracaoLeitura]
    valor_global_original: ValorMonetario
    impacto_valor: ValorMonetario
    impacto_percentual: ValorMonetario
    acumulado_percentual: ValorMonetario = Field(..., description="Esta alteração + as já concluídas do mesmo tipo na vigência.")
    exige_autorizacao: bool = Field(..., description="Acumulado acima de 25%: autorização do Ordenador de Despesa obrigatória.")
    justificativa: LeituraArquivo | None
    autorizacao: LeituraArquivo | None
    de_acordo: LeituraArquivo | None
    termo: LeituraArquivo | None
    memoria_pdf: LeituraArquivo | None
    memoria_xlsx: LeituraArquivo | None
    consolidado: LeituraArquivo | None
    ciencias: list[LeituraCiencia]
    ciencias_minimas: int
    concluida_em: datetime | None
    cancelada_em: datetime | None


class PainelAlteracao(BaseModel):
    """Resposta das rotas de alteração: a em andamento, as vigências e o histórico."""
    em_andamento: LeituraAlteracao | None
    vigencias: list[VigenciaDisponivel]
    historico: list[LeituraAlteracao]
    pode_editar: bool
    integra_equipe: bool


# A leitura do processo referencia `LeituraMemoriaVersao`, definida mais abaixo neste arquivo
LeituraProcessoProrrogacao.model_rebuild()
