# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de checklists, formulários e competências.
"""Schemas da execução: checklists, formulários de avaliação, modelos globais e competências.

`DetalheCompetencia` é o maior deles: reúne tudo o que a tela de execução mostra em todas as
etapas, para que uma única resposta redesenhe a tela inteira.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.contratos.empresas import Texto, TextoObrigatorio
from app.schemas.contratos.tipos import ValorFator, ValorMonetario, ValorQuantidade, ValorUnitario

# Etapas da competência (iguais às do modelo) e a situação resumida mostrada na aba Execução
Etapa = Literal["medicao", "avaliacao", "nota_fiscal", "retencao", "checklist", "cadin", "consolidado", "ordem_bancaria", "concluida"]
SituacaoCompetencia = Literal["pendente", "disponivel", "em_andamento", "concluida"]


# ---------------------------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------------------------

class GravacaoDocumentoChecklist(BaseModel):
    """Um documento no cadastro de um checklist."""
    nome: TextoObrigatorio = Field(..., max_length=500)
    observacao: Texto = Field("", max_length=1000)
    obrigatorio: bool = Field(True, description="Obrigatório precisa estar anexado para concluir a etapa do checklist; opcional, não.")
    com_validade: bool = Field(False, description="Documento com validade: o envio exige a data de validade e, se ainda valer, ele é reaproveitado na competência seguinte.")
    vale_outros_contratos: bool = Field(False, description="Documento da empresa: se já foi juntado e ainda vale em outro contrato da mesma empresa, a execução oferece reaproveitá-lo. Sem `com_validade`, vale o documento juntado na mesma competência (mês) do outro contrato.")
    pedir_envio: bool = Field(False, description="Pedir para enviar: ao concluir a medição, o e-mail à empresa pede este documento (com a observação).")


class GravacaoChecklist(BaseModel):
    """Corpo para criar ou editar uma versão do checklist (pelo menos um documento)."""
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[GravacaoDocumentoChecklist] = Field(..., min_length=1, description="Documentos mensais, na ordem.")


class LeituraDocumentoChecklist(BaseModel):
    """Documento do checklist como é devolvido pela API."""
    id: uuid.UUID
    ordem: int
    nome: str
    observacao: str
    obrigatorio: bool
    com_validade: bool
    vale_outros_contratos: bool = False
    pedir_envio: bool = False


class AlteracaoPedirEnvio(BaseModel):
    """Corpo de `PUT .../checklists/{id}/itens/{item_id}/pedir-envio`: liga ou desliga o pedido de envio de um documento (vale com o checklist ativo)."""
    pedir_envio: bool


class LeituraChecklist(BaseModel):
    """Versão do checklist com seus documentos."""
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
    """Uma nota possível da escala (ex.: 0 = "Insatisfatório", 10 = "Ótimo")."""
    valor: Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)]
    legenda: TextoObrigatorio = Field(..., max_length=100)


class FaixaLiberacao(BaseModel):
    """Faixa de nota final que define quanto do pagamento é liberado."""
    minimo: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
    maximo: Annotated[Decimal | None, Field(None, ge=0, max_digits=8, decimal_places=2)] = Field(None, description="Nulo = sem teto.")
    percentual: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] = Field(..., description="% do pagamento liberado.")
    notas_zero: int | None = Field(
        None, ge=1, le=100,
        description="Também aplica a faixa quando algum grupo tiver ao menos esta quantidade de notas mínimas da escala "
        "(nota 0 no modelo padrão), qualquer que seja a nota final. Nulo = só pela nota.",
    )


class ItemFormulario(BaseModel):
    """Item avaliado dentro de um grupo, com o peso dele no grupo."""
    id: str | None = Field(None, description="Gerado pela API quando vazio.")
    nome: TextoObrigatorio = Field(..., max_length=300)
    descricao: Texto = Field("", max_length=1000)
    peso: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)] = Field(..., description="% dentro do grupo.")


class GrupoFormulario(BaseModel):
    """Grupo de itens do formulário (os pesos dos itens somam 100%)."""
    id: str | None = None
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[ItemFormulario] = Field(..., min_length=1)


class DefinicaoFormulario(BaseModel):
    """Estrutura completa do formulário: escala, faixas e grupos."""
    escala: list[NotaEscala] = Field(..., min_length=2, description="Notas em ordem crescente.")
    faixas: list[FaixaLiberacao] = Field(..., min_length=1)
    grupos: list[GrupoFormulario] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _regras(self) -> "DefinicaoFormulario":
        """Valida a coerência da estrutura inteira (regras que envolvem mais de um campo)."""
        # A escala precisa ser estritamente crescente (ordenada e sem repetição)
        valores = [n.valor for n in self.escala]
        if valores != sorted(valores) or len(set(valores)) != len(valores):
            raise ValueError("a escala de notas deve estar em ordem crescente, sem repetição")
        # Cada faixa precisa ter máximo ≥ mínimo (máximo vazio = sem teto)
        for faixa in self.faixas:
            if faixa.maximo is not None and faixa.maximo < faixa.minimo:
                raise ValueError("em cada faixa, a nota máxima deve ser maior ou igual à mínima")
        # Em cada grupo, os pesos dos itens precisam somar exatamente 100
        for grupo in self.grupos:
            if sum(i.peso for i in grupo.itens) != 100:
                raise ValueError(f"a soma dos pesos do grupo \"{grupo.nome}\" deve ser 100%")
        return self


class GravacaoFormulario(BaseModel):
    """Corpo para criar ou editar uma versão do formulário."""
    nome: TextoObrigatorio = Field(..., max_length=300)
    definicao: DefinicaoFormulario


class LeituraFormulario(BaseModel):
    """Versão do formulário como é devolvida pela API."""
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
    """Corpo para criar ou alterar um modelo global. O conteúdo exigido depende do `tipo`."""
    tipo: Literal["checklist", "formulario", "portaria", "despacho", "email_cadin", "email_ob", "prorrogacao", "checklist_prorrogacao"]
    nome: TextoObrigatorio = Field(..., max_length=300)
    itens: list[GravacaoDocumentoChecklist] | None = Field(None, description="Obrigatório para `checklist` e `checklist_prorrogacao` (documentos pedidos na prorrogação; só `nome`, `observacao` e `obrigatorio` contam).")
    definicao: DefinicaoFormulario | None = Field(None, description="Obrigatório para `formulario`.")
    html: str | None = Field(None, description="Obrigatório para `portaria`, `despacho`, `email_cadin`, `email_ob` e `prorrogacao`: máscara em HTML com os placeholders permitidos (`#nomegestor`...).")
    assunto: str | None = Field(None, max_length=300, description="Obrigatório para `email_cadin` e `email_ob`: assunto do e-mail (aceita os mesmos placeholders).")
    variante: Literal[
        "com_anterior", "sem_anterior",
        "despacho_instrucao", "declaracao_atendimento_licitacao", "declaracao_atendimento_direta", "minuta_aditivo", "termo_ciencia", "declaracao_tce", "despacho_autorizacao",
    ] | None = Field(None, description="Obrigatório para `portaria` (`com_anterior` ou `sem_anterior`) e para `prorrogacao` (qual documento da prorrogação a máscara escreve).")
    ativo: bool = True

    @model_validator(mode="after")
    def _conteudo(self) -> "GravacaoModelo":
        """Checklist precisa de documentos; formulário precisa de definição."""
        if self.tipo in ("checklist", "checklist_prorrogacao") and not self.itens:
            raise ValueError("o modelo de checklist precisa de ao menos um documento")
        if self.tipo == "formulario" and self.definicao is None:
            raise ValueError("o modelo de formulário precisa da definição")
        if self.tipo == "portaria" and (not (self.html or "").strip() or self.variante is None):
            raise ValueError("o modelo de portaria precisa do texto e da variante (com ou sem portaria anterior)")
        if self.tipo == "portaria" and self.variante not in ("com_anterior", "sem_anterior"):
            raise ValueError("a variante da portaria é com_anterior ou sem_anterior")
        if self.tipo == "prorrogacao" and (not (self.html or "").strip() or self.variante in (None, "com_anterior", "sem_anterior")):
            raise ValueError("o modelo de prorrogação precisa do texto e de qual documento ele escreve (variante)")
        if self.tipo == "despacho" and not (self.html or "").strip():
            raise ValueError("o modelo de despacho precisa do texto")
        if self.tipo == "email_cadin" and (not (self.html or "").strip() or not (self.assunto or "").strip()):
            raise ValueError("o modelo de e-mail de CADIN precisa do assunto e do texto")
        if self.tipo == "email_ob" and (not (self.html or "").strip() or not (self.assunto or "").strip()):
            raise ValueError("o modelo de e-mail de pagamento precisa do assunto e do texto")
        return self


class PlaceholderPortaria(BaseModel):
    """Placeholder aceito nas máscaras de portaria (escrito `#nome` no texto)."""
    nome: str
    descricao: str
    da_anterior: bool = Field(..., description="Só vale na máscara com portaria anterior.")


class LeituraModelo(BaseModel):
    """Modelo global como é devolvido pela API."""
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
    """Pré-requisitos para gerar as competências (ex.: checklist ativo, NE cadastrada)."""
    prontos: bool
    pendencias: list[str] = Field(..., description="Motivos que impedem gerar as competências.")


class ResumoCompetencia(BaseModel):
    """Competência na lista da aba Execução."""
    id: uuid.UUID
    competencia: date
    tipo: str = Field("regular", description="`regular`, `diferenca_reajuste` (complementar, paga a diferença de um reajuste retroativo) ou `adicional` (outra medição e outro pagamento no mesmo período).")
    numero_adicional: int = Field(0, description="Número da medição adicional (1, 2…); 0 nas demais.")
    parte: int | None = Field(None, description="1 ou 2 quando o mês se divide entre duas vigências; nulo nos demais casos.")
    identificador: str = Field(..., description="Chave da rota da tela: `AAAA-MM`, `AAAA-MM-1`, `AAAA-MM-2`, `AAAA-MM-dif` ou `AAAA-MM-adicional-N`.")
    rotulo: str = Field(..., description="Rótulo para exibição. Ex.: `01/2027 · 1ª parte`.")
    sequencia_vigencia: int
    periodo_inicio: date
    periodo_fim: date
    situacao: SituacaoCompetencia
    etapa_atual: Etapa
    valor_medicao: ValorMonetario | None = Field(None, description="Nulo enquanto a medição não foi salva.")
    possui_avaliacao: bool
    diferenca_coberta_por_reajuste_id: uuid.UUID | None = Field(None, description="Reajuste que calculou e pagou o retroativo desta competência regular; nulo se ainda não coberta.")


class GrupoCompetencias(BaseModel):
    """Competências de uma vigência (a aba Execução agrupa por vigência)."""
    sequencia_vigencia: int
    inicio: date
    fim: date
    competencias: list[ResumoCompetencia]


class PainelExecucao(BaseModel):
    """Resposta da aba Execução."""
    requisitos: Requisitos
    geradas: bool
    grupos: list[GrupoCompetencias]


class LeituraItemMedicao(BaseModel):
    """Item na medição: previsto (com pró-rata) e medido."""
    id: uuid.UUID
    ordem: int
    descricao: str
    segmento: int = Field(1, description="Trecho do mês (1, 2…) quando o mês tem virada de vigência ou de preço; 1 nos demais meses.")
    periodo_rotulo: str = Field("", description="Dias do trecho e o que mudou (ex.: `01/09 a 19/09/2026 · preço anterior`); vazio quando o mês não tem virada.")
    tipo: str
    calcula_pro_rata: bool
    valor_unitario: ValorUnitario
    fator_meses: ValorFator
    quantidade_prevista: ValorQuantidade
    quantidade_medida: Annotated[Decimal, Field(description="Até 10 casas.")]
    acerto: Annotated[Decimal, Field(description="Acerto de centavos lançado na medição (ex.: 0,01 ou -0,02); soma ao `subtotal`.")] = Decimal(0)
    subtotal: ValorMonetario
    saldo: ValorQuantidade = Field(..., description="Contínuo: previsto da competência; sob demanda: saldo do item na vigência.")
    glosas: ValorQuantidade = Field(..., description="Glosas do diário de bordo com data no período da competência.")
    saldo_liquido: ValorQuantidade = Field(..., description="Saldo − glosas (mínimo 0): o máximo que pode ser medido.")
    despesa_variavel: bool = Field(False, description="Item marcado como despesa variável nesta medição (subtotal à parte; exige nota de débito, recibo ou outros na etapa da nota fiscal).")


class GlosaDoPeriodo(BaseModel):
    """Glosa do diário de bordo que vale nesta competência."""
    ocorrencia_id: uuid.UUID
    data_ocorrencia: date
    descricao_ocorrencia: str
    registrada_por_nome: str
    item_id: uuid.UUID
    descricao_item: str
    quantidade: ValorQuantidade


class EmailMedicao(BaseModel):
    """E-mail enviado à equipe e ao preposto ao concluir a medição (pede a NF em até 48 h)."""
    enviado_em: datetime | None = None
    ok: bool | None = None
    destinatarios: list[str] = []
    erro: str | None = None


class LeituraCiencia(BaseModel):
    """Ciência registrada por um integrante."""
    usuario_id: int | None
    nome: str
    papel: str
    registrada_em: datetime


class LeituraArquivo(BaseModel):
    """Referência a um PDF anexado (para montar o link de download)."""
    anexo_id: uuid.UUID
    nome: str
    tamanho: int
    enviado_em: datetime


class Contestacao(BaseModel):
    """Prazo de contestação da contratada (dias úteis a contar do e-mail único da medição); juntar a nota fiscal o encerra."""
    prazo_dias: int = Field(..., description="Dias úteis informados pelo fiscal.")
    inicio_em: datetime = Field(..., description="Quando o e-mail único foi enviado (abre o prazo).")
    limite_em: datetime = Field(..., description="Fim do último dia útil do prazo (horário de Brasília).")
    situacao: Literal["aberto", "vencido", "encerrado"] = Field(
        ..., description="`aberto` (dentro do prazo), `vencido` (passou do limite sem a nota fiscal) ou `encerrado` (nota fiscal juntada).")
    encerrada_em: datetime | None = Field(None, description="Quando a nota fiscal foi juntada (só em `encerrado`).")
    dias_uteis_decorridos: int = Field(..., description="Dias úteis já consumidos (até a nota fiscal, se encerrado).")
    dias_uteis_restantes: int = Field(..., description="Dias úteis que faltam (0 quando vencido ou encerrado).")
    percentual: int = Field(..., ge=0, le=100, description="Parte do prazo consumida, para a barra de progresso.")
    documento_executivo: LeituraArquivo | None = Field(None, description="PDF com o valor a faturar enviado no e-mail (última versão).")
    documento_executivo_versao: int = Field(0, description="Sobe a cada reemissão após contestação aceita.")


class LeituraMemoria(BaseModel):
    """Uma versão da memória de cálculo da medição."""
    versao: int
    criada_em: datetime
    arquivo: LeituraArquivo
    arquivo_despesas: LeituraArquivo | None = Field(None, description="Medição dos itens de despesas variáveis (PDF à parte), quando a competência tem esses itens.")


class NotaSelecionada(BaseModel):
    """NE na medição, com o saldo contábil e o saldo ainda livre para novas medições."""
    id: uuid.UUID
    numero: str
    saldo: ValorMonetario = Field(..., description="Saldo contábil da NE (valor original − pagamentos + estornos).")
    saldo_livre: ValorMonetario = Field(..., description="Saldo menos o comprometido por outras competências medidas e ainda não pagas.")


class ConferenciaNota(BaseModel):
    """Conferência automática da nota (etapa de retenção)."""
    descricao: str
    situacao: Literal["ok", "alerta", "info"] = Field(..., description="`ok` conforme, `alerta` conferir, `info` sem como verificar.")
    detalhe: str


class LeituraNotaFiscal(BaseModel):
    """Dados de uma nota fiscal registrada (a competência pode ter várias, em `ordem`)."""
    id: uuid.UUID
    ordem: int = Field(..., description="Posição da nota na competência (1, 2, …).")
    numero: str
    arquivo: LeituraArquivo | None
    xml: LeituraArquivo | None = Field(None, description="XML da nota (NF-e ou NFS-e).")
    dados_xml: dict[str, Any] | None = Field(None, description="Dados lidos do XML (ver docs: emitente, tomador, itens, retenções…).")
    conferencias: list[ConferenciaNota] = []
    valor_bruto: ValorMonetario | None
    retencao_ir: ValorMonetario
    retencao_inss: ValorMonetario
    retencao_iss: ValorMonetario
    retencao_pis: ValorMonetario
    retencao_cofins: ValorMonetario
    retencao_csll: ValorMonetario = Decimal(0)
    valor_liquido: ValorMonetario


class RetencoesNota(BaseModel):
    """Retenções conferidas de uma nota (valores ≥ 0; a soma não passa do bruto)."""
    ir: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)
    inss: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)
    iss: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)
    pis: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)
    cofins: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)
    csll: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] = Decimal(0)


class RetencoesDaNota(RetencoesNota):
    """Retenções conferidas de uma das notas da competência."""
    nota_id: uuid.UUID = Field(..., description="`id` da nota fiscal (de `notas_fiscais` no detalhe da competência).")


class ItemNotaFiscal(BaseModel):
    """Uma nota fiscal na gravação da etapa 3 (a lista inteira, na ordem final)."""
    id: uuid.UUID | None = Field(None, description="Nota já registrada, que mantém os arquivos que não forem trocados; vazio para uma nota nova.")
    arquivo: int | None = Field(None, ge=0, description="Posição, na lista `arquivos`, do PDF desta nota.")
    xml: int | None = Field(None, ge=0, description="Posição, na lista `xmls`, do XML desta nota. Opcional: sem XML, informe `valor_bruto`.")
    valor_bruto: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)] | None = Field(
        None, description="Valor bruto da nota. Obrigatório quando a nota não tem XML; com XML, vale o valor lido dele.")
    numero: str | None = Field(None, max_length=100, description="Número da nota, para a nota sem XML (opcional).")


class ItemDespesaVariavel(BaseModel):
    """Um documento de despesa variável na gravação da etapa 3 (a lista inteira, na ordem final)."""
    id: uuid.UUID | None = Field(None, description="Documento já registrado, que mantém o arquivo se não for trocado; vazio para um novo.")
    tipo: Literal["nota_debito", "recibo", "outros"] = Field(..., description="Nota de débito, recibo ou outros.")
    numero: str | None = Field(None, max_length=100, description="Número do documento (opcional).")
    valor: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)] = Field(..., description="Valor do documento.")
    arquivo: int | None = Field(None, ge=0, description="Posição, na lista `arquivos_despesas`, do PDF deste documento.")


class LeituraDespesaVariavel(BaseModel):
    """Documento de despesa variável juntado (não passa pela retenção; entra no consolidado)."""
    id: uuid.UUID
    ordem: int
    tipo: Literal["nota_debito", "recibo", "outros"]
    numero: str
    rotulo: str
    valor: ValorMonetario
    arquivo: LeituraArquivo | None


class GravacaoRetencao(BaseModel):
    """Conferência da etapa 4: retenções de cada nota fiscal e a confirmação da discriminação."""
    notas: list[RetencoesDaNota] = Field(..., min_length=1, description="Uma entrada para cada nota fiscal da competência.")
    discriminacao_conferida: bool = Field(..., description="A discriminação dos serviços é compatível com o objeto (obrigatório = true).")
    enviar_email: bool = Field(False, description="Envia o e-mail desta etapa (equipe, prepostos ou Financeiro). Padrão `false`: só envia quem marcar.")


class LeituraRetencao(BaseModel):
    """Conferência registrada na etapa 4."""
    concluida_em: datetime | None
    por_nome: str
    discriminacao_conferida: bool
    pdf: LeituraArquivo | None


class NotaRecusada(BaseModel):
    """Retrato de uma nota fiscal recusada (os PDFs ficam disponíveis para baixar)."""
    rotulo: str
    numero: str | None = None
    valor_bruto: ValorMonetario | None = None
    chave: str | None = None
    arquivo: LeituraArquivo | None = Field(None, description="PDF da nota recusada.")
    xml: LeituraArquivo | None = None


class LeituraRecusa(BaseModel):
    """Recusa da nota fiscal pelo Financeiro (ciclo nota → recusa → nova nota → … → aprovação)."""
    id: uuid.UUID
    ordem: int
    justificativa: str
    recusada_por_nome: str
    recusada_em: datetime
    notas: list[NotaRecusada]
    pdf: LeituraArquivo | None = Field(None, description="PDF da recusa, para juntar a um processo.")
    email: "EmailMedicao" = Field(description="E-mail à equipe e a todos os prepostos, com o PDF anexado.")


class GravacaoRecusa(BaseModel):
    """Corpo do `POST …/retencao/recusar`."""
    justificativa: str = Field(..., min_length=10, max_length=4000, description="Motivo da recusa (obrigatório, mínimo de 10 caracteres).")


class LeituraConsultaCadin(BaseModel):
    """Uma consulta ao CADIN (a competência guarda o histórico de todas)."""
    id: uuid.UUID
    possui_pendencia: bool
    pendencia: str
    texto_notificacao: str
    certidao: LeituraArquivo
    email: LeituraArquivo | None = Field(None, description="Cópia (PDF) do e-mail enviado pelo sistema aos prepostos; vai ao consolidado.")
    criado_por_nome: str
    criado_em: datetime
    email_enviado_em: datetime | None = Field(None, description="Quando o sistema tentou enviar o e-mail (nulo: ainda não tentou, ou consulta sem pendência).")
    email_ok: bool | None = Field(None, description="Resultado do envio (nulo: sem tentativa).")
    email_destinatarios: list[str] = Field(default_factory=list, description="Para (prepostos) e Cc (equipe) do último envio.")
    email_erro: str | None = Field(None, description="Motivo da falha (sem máscara ativa, sem preposto com e-mail, SMTP).")


class SugestaoOutroContrato(BaseModel):
    """Documento ainda válido de outro contrato da mesma empresa que pode ser reaproveitado na competência."""
    origem_id: uuid.UUID = Field(..., description="Id do documento de origem (enviar em `reaproveitar`).")
    contrato_numero: str
    competencia: date = Field(..., description="Mês da competência de origem (dia 1).")
    validade_ate: date | None = Field(None, description="Validade do documento de origem (vazio quando o documento não tem validade: vale o da mesma competência).")
    arquivo_nome: str


class ReaproveitamentoDocumento(BaseModel):
    """Corpo de `POST …/checklist/{documento_id}/reaproveitar`."""
    origem_id: uuid.UUID = Field(..., description="`sugestao_outro_contrato.origem_id` do documento.")


class LeituraDocumentoMensal(BaseModel):
    """Documento do checklist na competência, com o PDF anexado (se houver)."""
    id: uuid.UUID
    ordem: int
    nome: str
    observacao: str
    obrigatorio: bool
    com_validade: bool = False
    validade_ate: date | None = Field(None, description="Até quando o documento vale (só em documento com validade).")
    reaproveitado_de: date | None = Field(None, description="Mês da competência de onde o arquivo foi reaproveitado (dia 1).")
    vale_outros_contratos: bool = Field(False, description="Documento da empresa: pode ser reaproveitado de outro contrato da mesma empresa.")
    reaproveitado_contrato: str | None = Field(None, description="Número do contrato de onde o arquivo foi reaproveitado, quando veio de outro contrato.")
    sugestao_outro_contrato: "SugestaoOutroContrato | None" = Field(
        None, description="Documento igual, ainda válido, já juntado em outro contrato da mesma empresa (só na etapa do checklist, sem anexo).")
    arquivo: LeituraArquivo | None
    incluido_no_processo: bool = Field(False, description="Incluído durante o processo (não veio do modelo do checklist): nunca obrigatório e pode ser excluído enquanto a etapa estiver aberta.")
    incluido_por_nome: str | None = Field(None, description="Quem incluiu o documento (só nos incluídos durante o processo).")
    incluido_em: datetime | None = None


class RespostaAvaliacao(BaseModel):
    """Nota dada a um item do formulário (com justificativa quando abaixo da máxima)."""
    item_id: str
    nota: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
    justificativa: Texto = Field("", max_length=4000)


class OcorrenciaAvaliacao(BaseModel):
    """Ocorrência do diário de bordo (no período da competência) que impacta itens da avaliação."""
    id: uuid.UUID
    data_ocorrencia: date
    descricao: str
    registrada_por_nome: str
    itens: list[str] = Field(..., description="Ids dos itens do formulário desta avaliação impactados.")


class LeituraAvaliacao(BaseModel):
    """Avaliação da competência (etapa 2)."""
    definicao: dict[str, Any]
    respostas_iniciais: list[RespostaAvaliacao]
    avaliacao_inicial_em: datetime | None
    respostas_gestor: list[RespostaAvaliacao]
    complemento_gestor: str
    avaliacao_gestor_em: datetime | None
    nota_final: ValorMonetario | None
    percentual_liberado: ValorMonetario | None
    precisa_avaliacao_gestor: bool = Field(
        ..., description="Verdadeiro quando alguma nota inicial ficou abaixo da máxima; só então a avaliação do gestor é feita."
    )
    ciencias: list[LeituraCiencia] = Field(
        ..., description="Ciências da equipe no ateste (qualquer integrante vigente; `ciencias_minimas` já libera o PDF)."
    )
    pdf_gerado: LeituraArquivo | None
    pdf_assinado: LeituraArquivo | None
    concluida_em: datetime | None
    reconsideracoes: int
    reconsideracao: LeituraArquivo | None
    ocorrencias: list[OcorrenciaAvaliacao] = Field(
        default_factory=list, description="Ocorrências do diário no período que impactam itens: nota máxima nesses itens exige justificativa.")
    email: EmailMedicao = Field(default_factory=EmailMedicao,
                                description="E-mail do relatório à contratada (enviado ao gerar o PDF, para devolução assinada).")


class DescontoReajuste(BaseModel):
    """Parte do crédito de um reajuste com desconto retroativo, abatida nesta competência."""
    reajuste_id: uuid.UUID
    mes_referencia: date = Field(..., description="Mês de referência do reajuste que gerou o crédito.")
    valor: ValorMonetario


class LeituraCargaHistorica(BaseModel):
    """Marca de uma competência lançada por carga histórica: o limite mensal de quantidades não foi aplicado."""

    em: datetime = Field(..., description="Quando a carga lançou a competência.")
    observacao: str = Field(..., description="De onde vieram os dados (ex.: processo SEI de pagamento) e o que não foi aplicado.")
    excedentes: list[str] = Field(default_factory=list, description="Itens medidos (e pagos) acima do saldo mensal previsto, com a conta de cada um.")


class DetalheCompetencia(ResumoCompetencia):
    """Detalhe completo da competência: tudo o que a tela de execução precisa em uma resposta."""
    contrato_id: uuid.UUID
    contrato_numero: str
    empresa_cnpj: str = Field(..., description="CNPJ da empresa contratada, só dígitos (para copiar na consulta ao CADIN).")
    pode_incluir_adicional: bool = Field(False, description="O contrato permite medição adicional e o usuário pode incluí-la (botão \"Incluir nova medição\").")
    pode_excluir_adicional: bool = Field(False, description="A competência é uma medição adicional ainda não paga e o usuário pode excluí-la (botão \"Excluir medição adicional\").")
    adicional_justificativa: str = Field("", description="Justificativa informada ao incluir a medição adicional (vazio nas demais).")
    adicional_por_nome: str = Field("", description="Quem incluiu a medição adicional.")
    adicional_anexo: LeituraArquivo | None = Field(None, description="Anexo opcional da justificativa da medição adicional.")
    etapas: list[Etapa] = Field(..., description="Etapas desta competência, em ordem (sem `avaliacao` se não houver formulário).")
    pode_editar: bool
    pode_lancar_ob: bool = Field(False, description="O usuário pode anexar a Ordem Bancária e reenviar o e-mail de pagamento: quem pode editar o contrato ou tem a ação \"Lançar ordem bancária\" no perfil.")
    integra_equipe: bool = Field(..., description="O usuário pode registrar ciência.")
    pode_gerar_consolidado_novamente: bool = Field(
        ..., description="O usuário pode substituir o consolidado já gerado (todos que podem editar o contrato)."
    )
    liberada: bool = Field(..., description="O período terminou; a medição pode ser feita.")
    itens: list[LeituraItemMedicao]
    total_previsto: ValorMonetario
    total_medido: ValorMonetario = Field(..., description="Total da medição: Subtotal - Medição + Subtotal - Despesas Variáveis.")
    subtotal_medicao: ValorMonetario = Field(Decimal(0), description="Subtotal dos itens que não são despesas variáveis.")
    subtotal_despesas_variaveis: ValorMonetario = Field(Decimal(0), description="Subtotal dos itens marcados como despesas variáveis.")
    tem_despesas_variaveis: bool = Field(False, description="Há item marcado como despesa variável: a etapa da nota fiscal exige nota fiscal e documento de despesa.")
    despesas_variaveis: list[LeituraDespesaVariavel] = Field(default_factory=list, description="Notas de débito, recibos e outros juntados na etapa da nota fiscal.")
    notas_selecionadas: list[NotaSelecionada]
    notas_disponiveis: list[NotaSelecionada] = Field(..., description="NEs do contrato com saldo.")
    ciencias: list[LeituraCiencia]
    ciencias_minimas: int
    memorias: list[LeituraMemoria]
    medicao_concluida_em: datetime | None
    avaliacao: LeituraAvaliacao | None
    percentual_autorizado: ValorMonetario = Field(..., description="% liberado pela avaliação (100 sem avaliação).")
    valor_autorizado: ValorMonetario = Field(
        ..., description="Total medido × % liberado pela avaliação − desconto de reajuste (sugestão do valor da NF; nunca negativo)."
    )
    desconto_reajuste: ValorMonetario = Field(
        Decimal(0), description="Crédito de desconto de reajuste retroativo abatido nesta competência (0 quando não há)."
    )
    descontos_reajuste: list[DescontoReajuste] = Field(default_factory=list, description="Origem de cada desconto abatido.")
    valor_a_pagar: ValorMonetario = Field(
        ..., description="Valor que a OB debita nas NEs apontadas: soma das NFs (brutos) depois da etapa da NF; antes, o valor autorizado."
    )
    avisos: list[str] = Field(default_factory=list, description="Alertas da medição (ex.: item medido acima do saldo líquido).")
    glosas_periodo: list[GlosaDoPeriodo] = Field(default_factory=list, description="Glosas do diário de bordo que valem nesta competência.")
    email_medicao: EmailMedicao = Field(default_factory=EmailMedicao, description="Resultado do e-mail único da medição (medição + avaliação concluídas).")
    contestacao: Contestacao | None = Field(None, description="Prazo de contestação da contratada; nulo enquanto o e-mail único não foi enviado com sucesso.")
    prazo_contestacao_dias: int | None = Field(None, description="Prazo (dias úteis) informado pelo fiscal ao concluir a medição.")
    email_medicao_pendente: bool = Field(False, description="Envio solicitado, aguardando a conclusão da avaliação para o e-mail único sair.")
    pode_reemitir_medicao: bool = Field(False, description="Verdadeiro quando é possível reemitir o pacote (após contestação aceita) ou repetir um envio que falhou.")
    email_nf: EmailMedicao = Field(default_factory=EmailMedicao, description="E-mail ao Financeiro (cópia à equipe) com a NF juntada.")
    email_ob: EmailMedicao = Field(default_factory=EmailMedicao, description="E-mail aos prepostos avisando que a competência foi paga (enviado ao lançar a Ordem Bancária, pela máscara \"E-mail de pagamento\").")
    email_retencao: EmailMedicao = Field(default_factory=EmailMedicao, description="E-mail à equipe com as retenções conferidas.")
    retencao: LeituraRetencao | None = Field(None, description="Conferência da retenção de tributos, se feita.")
    pode_conferir_retencao: bool = Field(False, description="O usuário pode fazer a etapa de retenção (Financeiro, equipe ou SuperRoot).")
    recusas: list[LeituraRecusa] = Field(default_factory=list, description="Recusas da nota fiscal, da primeira para a última (trilha do ciclo).")
    pode_recusar: bool = Field(False, description="O usuário pode recusar a nota agora (mesma permissão da retenção, com a retenção aberta).")
    etapas_abertas: list[Etapa] = Field(default_factory=list, description="Etapas que aceitam gravação agora (retenção e checklist em paralelo; depois, só o CADIN).")
    etapas_concluidas: list[Etapa] = Field(default_factory=list, description="Etapas já concluídas.")
    retroativa: bool = Field(False, description="Competência anterior ao corte de alertas, em caminho curto: só medição, avaliação (se houver), nota fiscal e OB; sem e-mails nem avisos e sem preposto/prazo na conclusão da medição.")
    pode_buscar_ob_sigeo: bool = Field(False, description="A competência espera a OB e o contrato tem Processo Financeiro: a tela oferece \"Buscar a OB no SIGEO\".")
    reaberturas_permitidas: bool = Field(False, description="O usuário pode reabrir etapas (SuperRoot ou gestor vigente do contrato).")
    notas_fiscais: list[LeituraNotaFiscal] = Field(default_factory=list, description="Notas fiscais juntadas na etapa 3 (uma ou mais), em ordem.")
    nf_recebida_em: date | None
    prazo_pagamento_dias: int | None
    vencimento_pagamento: date | None = Field(..., description="Recebimento da NF + prazo (dias corridos).")
    origem_valor_nf: str | None
    nf_concluida_em: datetime | None
    consultas_cadin: list[LeituraConsultaCadin]
    documentos: list[LeituraDocumentoMensal]
    consolidado: LeituraArquivo | None
    ordem_bancaria: LeituraArquivo | None
    ob_origem: str | None = Field(None, description="`manual` (PDF juntado) ou `sigeo` (achada pela conferência diária no SIGEO).")
    ob_numero: str | None = Field(None, description="Número(s) da OB vindos do SIGEO (ex.: `2026OB01893`).")
    ob_data: date | None = Field(None, description="Data de lançamento da OB no SIGEO.")
    ob_valor: Decimal | None = Field(None, description="Valor pago (soma das OBs do mês) segundo o SIGEO.")
    ob_sigeo_pendencia: str | None = Field(None, description="Por que a conferência do SIGEO ainda não concluiu esta OB (ex.: pagamento parcial).")
    carga_historica: "LeituraCargaHistorica | None" = Field(None, description="Preenchido quando a competência foi lançada depois de paga (carga histórica): de onde veio e quais itens passaram do limite mensal.")
    ob_sigeo_verificado_em: datetime | None = None
    concluida_em: datetime | None


class ItemMedidoGravacao(BaseModel):
    """Quantidade medida de um item (até 10 casas decimais, como no sistema de origem)."""
    id: uuid.UUID
    quantidade_medida: Annotated[Decimal, Field(ge=0, max_digits=28, decimal_places=10)]
    acerto: Annotated[Decimal, Field(ge=-1, le=1, max_digits=6, decimal_places=2, description="Acerto de centavos do item (de -1,00 a +1,00; ex.: 0,01 ou -0,02) para absorver dízimas e arredondamentos. Só em item medido; vazio mantém o acerto atual.")] | None = None
    despesa_variavel: bool | None = Field(None, description="Marca o item como despesa variável nesta medição; vazio mantém a marca atual.")


class GravacaoMedicao(BaseModel):
    """Corpo do `PUT /medicao`."""
    itens: list[ItemMedidoGravacao]
    notas_empenho_ids: list[uuid.UUID] = Field(..., min_length=1, description="NEs em ordem de consumo.")


class PrepostoDoEmail(BaseModel):
    """Preposto ativo com e-mail, candidato a receber os comunicados da execução."""
    id: uuid.UUID
    nome: str
    email: str
    cargo: str


class UsuarioFinanceiro(BaseModel):
    id: int
    nome: str
    email: str
    cargo: str


class GrupoFinanceiro(BaseModel):
    """Um setor do Financeiro com os usuários ativos que têm e-mail (`setor_id` nulo = quem não é de nenhum setor)."""
    setor_id: int | None = None
    setor: str = Field(..., description="Caminho do setor, ex.: `DOF › Contabilidade`.")
    usuarios: list[UsuarioFinanceiro]


class ConclusaoMedicao(BaseModel):
    """Corpo do `POST /medicao/concluir`; a seleção de NEs precisa bater com a salva.

    O e-mail único à contratada é obrigatório. Sem avaliação de qualidade no contrato, `prepostos_ids` e `prazo_contestacao_dias` são exigidos aqui
    (o e-mail sai logo em seguida). Com avaliação, podem ser omitidos: são informados ao concluir a avaliação (`POST /avaliacao/assinada`)."""
    notas_empenho_ids: list[uuid.UUID] = Field(..., min_length=1, description="Deve ser igual à seleção salva.")
    prepostos_ids: list[uuid.UUID] | None = Field(
        None, min_length=1, description="Prepostos da contratada que recebem o e-mail único (um ou mais, ativos e com e-mail). A equipe vigente também recebe. "
        "Obrigatório quando o contrato não tem avaliação de qualidade.")
    prazo_contestacao_dias: int | None = Field(
        None, ge=1, le=60, description="Prazo, em dias úteis a contar do e-mail, para a contratada contestar glosas e descontos. Obrigatório quando o contrato não tem avaliação de qualidade.")


class EnvioMedicaoAvaliacao(BaseModel):
    """Corpo do `POST /avaliacao/enviar`: quem recebe o e-mail único da medição e o prazo para a contratada contestar."""
    prepostos_ids: list[uuid.UUID] | None = Field(
        None, min_length=1, description="Prepostos da contratada que recebem (um ou mais, ativos e com e-mail). Sem eles valem os escolhidos antes (reenvio).")
    prazo_contestacao_dias: int | None = Field(None, ge=1, le=60, description="Prazo em dias úteis a contar do e-mail. Sem ele vale o anterior (reenvio).")


class ReemissaoMedicao(BaseModel):
    """Corpo do `POST /medicao/reemitir`: nova comunicação após contestação aceita (ou repetição de um envio que falhou)."""
    prazo_contestacao_dias: int | None = Field(None, ge=1, le=60, description="Novo prazo em dias úteis; sem ele, vale o anterior.")
    prepostos_ids: list[uuid.UUID] | None = Field(None, min_length=1, description="Prepostos que recebem a reemissão (ao menos um); sem eles, valem os escolhidos ao concluir a medição.")


class GravacaoAvaliacaoInicial(BaseModel):
    """Corpo do `PUT /avaliacao/inicial`."""
    respostas: list[RespostaAvaliacao]


class GravacaoAvaliacaoGestor(BaseModel):
    """Corpo do `PUT /avaliacao/gestor`."""
    respostas: list[RespostaAvaliacao]
    complemento: Texto = Field("", max_length=4000)


class Reabertura(BaseModel):
    """Corpo do `POST /reabrir`: para qual etapa voltar e por quê."""
    etapa: Etapa = Field(..., description="Etapa que volta a ficar aberta (anteriores à atual).")
    justificativa: TextoObrigatorio = Field(..., max_length=2000)


class DespachoCompetencia(BaseModel):
    """Texto do despacho de pagamento da competência (para mostrar e copiar)."""
    html: str | None = Field(None, description="HTML formatado do despacho (parágrafos, negrito, centralizado); nulo se não há máscara de despacho ativa.")
    titulo: str = Field("", description="Título do despacho, com contrato e mês.")


class ResultadoBuscaObSigeo(BaseModel):
    """Resultado da busca da OB de uma competência no SIGEO."""

    concluida: bool = Field(..., description="A OB do mês foi encontrada, conferida com o líquido a pagar e a competência foi concluída.")
    mensagem: str = Field(..., description="O que aconteceu, em texto para o usuário (OB encontrada, motivo da pendência ou \"ainda não saiu\").")
