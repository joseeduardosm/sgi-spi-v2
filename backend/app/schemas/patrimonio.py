# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados do Patrimônio (/api/patrimonio).
"""Formatos de entrada e saída do módulo Patrimônio (bens móveis do prédio SPI)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

SituacaoBem = Literal["ativo", "em_manutencao", "inservivel", "extraviado", "baixado"]
OrigemBem = Literal["proprio", "terceiros"]
MotivoBaixa = Literal["alienacao", "doacao", "transferencia", "inutilizacao", "extravio"]
Agrupamento = Literal["andar", "sala", "setor", "grupo"]
GarantiaBem = Literal["indefinida", "vigente", "vencida"]


# --- Acesso ----------------------------------------------------------------------------------

class AcessoPatrimonio(BaseModel):
    usuario_id: int
    pode_operar: bool = Field(..., description="MODIFICACAO ou mais: cadastra bens e solicita movimentações, classificações e baixas.")
    pode_administrar: bool = Field(..., description="CONTROLE_TOTAL (ou SuperRoot): autoriza, recebe, aprova, ajusta local e cadastra salas e parâmetros.")


class OpcaoSetor(BaseModel):
    id: int
    nome: str


# --- Localizações ----------------------------------------------------------------------------

class LocalizacaoLeitura(BaseModel):
    id: uuid.UUID
    pai_id: uuid.UUID | None
    tipo: Literal["predio", "andar", "lado", "sala", "reservado"]
    nome: str
    codigo: str | None = Field(None, description="Só nas salas: andar, lado e número (05A03, 00B15, -1A01).")
    rotulo: str = Field(..., description="Forma curta: \"5º andar › 05A03 — Setor Financeiro\".")
    andar: int | None = Field(None, description="-1 = subsolo, 0 = térreo.")
    lado: str | None
    setor_id: int | None
    setor_nome: str | None
    responsavel_id: int | None
    responsavel_nome: str | None
    deposito_inservivel: bool = Field(False, description="A sala tem o setor \"Depósito inservível\": é o único destino possível dos inservíveis.")
    ativo: bool
    total_bens: int = Field(0, description="Bens na sala (zero nos demais níveis).")


class GravacaoSala(BaseModel):
    numero: int = Field(..., ge=1, le=99, description="Número da sala; andar e lado vêm do nível de cima (código 05A03).")


class GravacaoAreaComum(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200, description="Nome que aparece na tela (ex.: Hall dos elevadores).")
    sigla: str = Field("H", min_length=1, max_length=4, pattern=r"^[A-Za-z]{1,4}$", description="Letras que compõem o código junto com o andar (H → 05H, -1H). Padrão: H.")


class GravacaoDadosSala(BaseModel):
    setor_id: int | None = Field(None, description="Setor da sala.")
    responsavel_id: int | None = Field(None, description="Responsável pelos bens da sala (trocá-lo atualiza todos os bens dela).")


class AtualizacaoLocalizacao(BaseModel):
    nome: str | None = Field(None, max_length=200)
    ativo: bool | None = Field(None, description="Inativar (sala com bens não pode ser excluída, só inativada).")


# --- Grupos e parâmetros ---------------------------------------------------------------------

class GrupoLeitura(BaseModel):
    id: uuid.UUID
    codigo: str
    nome: str
    vida_util_meses: int | None = Field(None, description="Vida útil em meses; nulo = ainda não definida.")
    residual_percentual: Decimal
    deprecia: bool = Field(..., description="Bens culturais não depreciam (os de terceiros também não).")
    ativo: bool


class PrefixoLeitura(BaseModel):
    id: uuid.UUID
    codigo: str = Field(..., description="Prefixo da chapa, em maiúsculas (ex.: SPI).")
    padrao: bool = Field(..., description="É o prefixo que a tela de cadastro traz selecionado.")
    ativo: bool


class GravacaoPrefixo(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20, description="Só letras e números; é gravado em maiúsculas.")


class AtualizacaoPrefixo(BaseModel):
    padrao: bool | None = Field(None, description="`true` torna este o prefixo padrão (o anterior deixa de ser). O padrão precisa estar ativo.")
    ativo: bool | None = Field(None, description="Prefixo inativo não aparece para escolha. O padrão não pode ser inativado.")


class GravacaoGrupo(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=40)
    nome: str = Field(..., min_length=1, max_length=200)
    vida_util_meses: int | None = Field(None, gt=0)
    residual_percentual: Decimal = Field(Decimal("10"), ge=0, le=100)
    deprecia: bool = True


class AtualizacaoGrupo(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    vida_util_meses: int | None = Field(None, gt=0)
    residual_percentual: Decimal | None = Field(None, ge=0, le=100)
    deprecia: bool | None = None
    ativo: bool | None = None


class ParametrosPatrimonio(BaseModel):
    ufesp: str = Field(..., description="Valor da UFESP em reais (ex.: 37.02): base da regra de \"não patrimoniável\" (abaixo de 45 UFESP e vida útil menor que 2 anos).")


# --- Bens ------------------------------------------------------------------------------------

class FotoLeitura(BaseModel):
    id: uuid.UUID
    nome: str


class BemLeitura(BaseModel):
    id: uuid.UUID
    chapa: str | None = Field(None, description="Nula nos bens sem patrimônio (identificados pelo número de série).")
    rotulo: str = Field(..., description="Como mostrar o bem: a chapa ou, sem ela, \"S/N <número de série>\".")
    descricao: str
    localizacao_id: uuid.UUID
    sala_codigo: str | None
    sala_rotulo: str
    andar: int | None
    setor_nome: str | None
    responsavel_id: int | None
    responsavel_nome: str | None
    conservacao: int
    situacao: SituacaoBem
    origem: OrigemBem
    grupo_id: uuid.UUID | None
    grupo_nome: str | None
    uge: str | None
    ua: str | None
    divisao: str | None
    valor_aquisicao: Decimal | None
    valor_atual: Decimal | None
    valor_efetivo: Decimal | None = Field(None, description="Valor que vale nos painéis: o atual informado ou, sem ele, o calculado pela depreciação.")
    data_aquisicao: date | None
    garantia_meses: int | None
    garantia_fim: date | None = Field(None, description="Data de aquisição + meses de garantia; nula (garantia indefinida) sem a data de aquisição.")
    situacao_garantia: GarantiaBem
    vence_em_90_dias: bool
    marca: str | None
    modelo: str | None
    numero_serie: str | None
    nota_fiscal: str | None
    fornecedor: str | None
    observacoes: str | None
    criado_por_nome: str | None = Field(None, description="Quem cadastrou o bem (nulo nos importados e nos cadastros de usuário removido).")
    classificacao_pendente: bool
    em_movimentacao: bool
    dados_contabeis_pendentes: bool
    fotos: list[FotoLeitura]
    avisos: list[str]
    criado_em: datetime
    atualizado_em: datetime
    baixado_em: datetime | None


class ListaBens(BaseModel):
    total: int
    pagina: int
    itens: list[BemLeitura]


class GravacaoBem(BaseModel):
    prefixo: str | None = Field(None, max_length=20, description="Prefixo da chapa (SPI, SLT...). Com prefixo, `chapa` é só o número: números com menos de 6 dígitos são completados com zeros à esquerda e o servidor junta tudo (ex.: SPI + 231 = SPI000231). Texto que não é só número é aceito como foi digitado, depois do prefixo. Sem prefixo, a chapa é gravada como veio.")
    id_cliente: str | None = Field(None, max_length=64, description="Identificador gerado no aparelho: o reenvio de um cadastro feito offline não duplica o bem.")
    chapa: str | None = Field(None, max_length=60, description="Qualquer formato (há bens cedidos ainda não repatrimoniados); única sem diferenciar maiúsculas. Pode faltar se o bem não tem patrimônio, mas então o número de série é obrigatório.")
    descricao: str = Field(..., min_length=1, max_length=300)
    localizacao_id: uuid.UUID = Field(..., description="Sala do bem (precisa ter setor e responsável: `409 sala_sem_responsavel`).")
    conservacao: int = Field(..., ge=1, le=5, description="1 (péssimo) a 5 (ótimo).")
    situacao: Literal["ativo", "em_manutencao"] = "ativo"
    origem: OrigemBem = "proprio"
    grupo_id: uuid.UUID | None = None
    uge: str | None = Field(None, max_length=40)
    ua: str | None = Field(None, max_length=40)
    divisao: str | None = Field(None, max_length=80)
    valor_aquisicao: Decimal | None = Field(None, ge=0)
    valor_atual: Decimal | None = Field(None, ge=0)
    data_aquisicao: date | None = None
    garantia_meses: int | None = Field(None, ge=0)
    marca: str | None = Field(None, max_length=80)
    modelo: str | None = Field(None, max_length=80)
    numero_serie: str | None = Field(None, max_length=80)
    nota_fiscal: str | None = Field(None, max_length=60)
    fornecedor: str | None = Field(None, max_length=200)
    observacoes: str | None = None


class AtualizacaoBem(BaseModel):
    """Só os campos enviados mudam. Local, responsável, inservível/extraviado e baixa seguem fluxos próprios."""
    prefixo: str | None = Field(None, max_length=20, description="Prefixo da nova chapa (veja `GravacaoBem.prefixo`); só vale junto com `chapa`.")
    chapa: str | None = Field(None, max_length=60, description="Vazia remove a chapa (só se o bem tiver número de série).")
    descricao: str | None = Field(None, min_length=1, max_length=300)
    conservacao: int | None = Field(None, ge=1, le=5)
    situacao: Literal["ativo", "em_manutencao"] | None = None
    origem: OrigemBem | None = None
    grupo_id: uuid.UUID | None = None
    uge: str | None = None
    ua: str | None = None
    divisao: str | None = None
    valor_aquisicao: Decimal | None = Field(None, ge=0)
    valor_atual: Decimal | None = Field(None, ge=0)
    data_aquisicao: date | None = None
    garantia_meses: int | None = Field(None, ge=0)
    marca: str | None = None
    modelo: str | None = None
    numero_serie: str | None = None
    nota_fiscal: str | None = None
    fornecedor: str | None = None
    observacoes: str | None = None


class LocalizacaoBem(BaseModel):
    localizacao_id: uuid.UUID = Field(..., description="Sala onde o bem foi encontrado (não pode ser a \"NECESSÁRIO ATUALIZAR\").")


class AjusteLocal(BaseModel):
    localizacao_id: uuid.UUID = Field(..., description="Sala de destino.")
    motivo: str = Field(..., min_length=1, description="Obrigatório; fica no histórico do bem.")


class Reversao(BaseModel):
    justificativa: str = Field(..., min_length=10, description="Mínimo de 10 caracteres.")
    localizacao_id: uuid.UUID | None = Field(None, description="Obrigatória no extraviado: a sala onde foi encontrado.")


class EventoLeitura(BaseModel):
    id: uuid.UUID
    tipo: str
    campo: str | None
    valor_anterior: str | None
    valor_novo: str | None
    autor_nome: str
    origem: str | None
    texto: str
    dados: dict[str, Any] | None
    ocorrido_em: datetime


# --- Movimentações ---------------------------------------------------------------------------

class ItemMovimentacaoLeitura(BaseModel):
    bem_id: uuid.UUID
    chapa: str | None = None
    numero_serie: str | None = Field(None, description="Para conferir o recebimento por leitura do número de série (bem sem chapa).")
    rotulo: str
    descricao: str
    origem_codigo: str | None
    origem_rotulo: str
    recebido_em: datetime | None


class MovimentacaoLeitura(BaseModel):
    id: uuid.UUID
    status: Literal["pendente", "autorizada", "concluida", "recusada", "cancelada"]
    destino_id: uuid.UUID
    destino_codigo: str | None
    destino_rotulo: str
    motivo: str
    solicitante_id: int | None
    solicitante_nome: str
    solicitada_em: datetime
    decidido_por_nome: str | None
    decidido_em: datetime | None
    motivo_recusa: str | None
    concluida_em: datetime | None
    itens: list[ItemMovimentacaoLeitura]


class GravacaoMovimentacao(BaseModel):
    id_cliente: str | None = Field(None, max_length=64, description="Idempotência do envio offline.")
    bens_ids: list[uuid.UUID] = Field(default_factory=list, description="Bens (de origens diferentes, se for o caso) com destino único.")
    chapas: list[str] = Field(default_factory=list, description="Chapas lidas (usadas quando o pedido foi feito sem sinal e o aparelho só conhece a chapa). Pelo menos um bem, por id ou chapa.")
    destino_id: uuid.UUID
    motivo: str = Field(..., min_length=1)


class Motivo(BaseModel):
    motivo: str = Field(..., min_length=1, description="Obrigatório na recusa.")


class Recebimento(BaseModel):
    bem_id: uuid.UUID = Field(..., description="Bem lido no celular, que muda de local na hora.")


# --- Classificações --------------------------------------------------------------------------

class ItemClassificacaoLeitura(BaseModel):
    id: uuid.UUID
    bem_id: uuid.UUID
    chapa: str | None = None
    numero_serie: str | None = None
    rotulo: str
    descricao: str
    sala_rotulo: str
    situacao_anterior: str | None
    justificativa: str | None
    anexo_nome: str | None
    resultado: Literal["aprovado", "recusado"] | None


class ClassificacaoLeitura(BaseModel):
    id: uuid.UUID
    numero: int = Field(..., description="Número de exibição (#12), único entre listas e baixas.")
    tipo: Literal["inservivel", "extraviado"]
    status: Literal["rascunho", "pendente", "aprovada", "parcial", "recusada"]
    solicitante_id: int | None
    solicitante_nome: str
    criada_em: datetime
    enviada_em: datetime | None
    decidido_por_nome: str | None
    decidido_em: datetime | None
    motivo_recusa: str | None
    itens: list[ItemClassificacaoLeitura]


class GravacaoLista(BaseModel):
    id_cliente: str | None = Field(None, max_length=64, description="Idempotência do envio offline.")
    tipo: Literal["inservivel", "extraviado"] | None = Field(None, description="Obrigatório na classificação; ignorado na baixa.")


class EntradaBem(BaseModel):
    bem_id: uuid.UUID | None = Field(None, description="Bem escolhido na lista de uma sala (extraviado).")
    chapa: str | None = Field(None, description="Chapa lida pelo código ou digitada.")


class Justificativa(BaseModel):
    itens_ids: list[uuid.UUID] = Field(..., min_length=1, description="Itens marcados; a justificativa vale para todos.")
    justificativa: str = Field(..., min_length=10, description="Mínimo de 10 caracteres.")


class Decisao(BaseModel):
    aprovados_ids: list[uuid.UUID] = Field(default_factory=list, description="Itens aprovados; os demais são recusados (a recusa exige `motivo_recusa`).")
    motivo_recusa: str | None = None


# --- Baixas ----------------------------------------------------------------------------------

class ItemBaixaLeitura(BaseModel):
    id: uuid.UUID
    bem_id: uuid.UUID
    chapa: str | None = None
    numero_serie: str | None = None
    rotulo: str
    descricao: str
    situacao_anterior: str | None
    valor_aquisicao: Decimal | None
    motivo: MotivoBaixa | None
    processo: str | None
    resultado: Literal["aprovado", "recusado"] | None


class BaixaLeitura(BaseModel):
    id: uuid.UUID
    numero: int = Field(..., description="Número de exibição (#12), único entre listas e baixas.")
    status: Literal["rascunho", "pendente", "aprovada", "parcial", "recusada"]
    solicitante_id: int | None
    solicitante_nome: str
    criada_em: datetime
    enviada_em: datetime | None
    decidido_por_nome: str | None
    decidido_em: datetime | None
    motivo_recusa: str | None
    tem_termo: bool
    itens: list[ItemBaixaLeitura]


class MotivoItensBaixa(BaseModel):
    itens_ids: list[uuid.UUID] = Field(..., min_length=1, description="A seleção toda ou um grupo de itens.")
    motivo: MotivoBaixa
    processo: str = Field(..., min_length=1, max_length=80, description="Número do processo.")


# --- Painel ----------------------------------------------------------------------------------

class IndicadoresPatrimonio(BaseModel):
    total_bens: int
    valor_aquisicao: Decimal = Field(..., description="Fora os bens com dados contábeis pendentes.")
    valor_atual: Decimal = Field(..., description="Fora os bens com dados contábeis pendentes.")
    fora_garantia: int
    aguardando_baixa: int = Field(..., description="Inservíveis e extraviados.")
    solicitacoes_pendentes: int = Field(..., description="Movimentações, classificações e baixas aguardando aprovação.")
    dados_contabeis_pendentes: int
    movimentacoes_em_aberto: int


class GrupoPainel(BaseModel):
    chave: str
    rotulo: str
    quantidade: int
    valor: Decimal


class LinhaGarantia(BaseModel):
    id: uuid.UUID
    chapa: str | None = None
    rotulo: str
    descricao: str
    sala: str
    fim_garantia: date | None
    dias: int | None
    vence_em_90_dias: bool


class LinhaPendente(BaseModel):
    id: uuid.UUID
    chapa: str | None = None
    rotulo: str
    descricao: str
    sala: str


class PainelPatrimonio(BaseModel):
    indicadores: IndicadoresPatrimonio
    agrupar_por: Agrupamento
    grupos: list[GrupoPainel]
    fora_garantia: list[LinhaGarantia]
    vencendo_90_dias: list[LinhaGarantia]
    contabeis_pendentes: list[LinhaPendente]
