# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da API do módulo Chamados (abertura, fila, detalhe e Parâmetros).
"""Schemas do módulo Chamados (`/api/chamados`).

Os nomes dos papéis são os do SGI: **solicitante**, **em cópia** e **responsável** (setor responsável e responsável pelo atendimento).
"""

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

StatusBase = Literal["novo", "em_atendimento", "pendente", "em_aprovacao", "solucionado"]
Prioridade = Literal["baixa", "normal", "alta", "urgente"]
TipoChamado = Literal["incidente", "requisicao"]
FiltroFila = Literal["abertos", "meus", "setor", "novos", "sem_responsavel", "sem_itil", "solucionados", "todos"]
FiltroMeus = Literal["abertos", "aguardando", "resolvidos", "todos"]
OrdemChamados = Literal["numero", "titulo", "solicitante", "setor", "situacao", "prioridade", "prazo", "aberto_em"]
Direcao = Literal["asc", "desc"]


# ---------------------------------------------------------------------------------------------
# Contexto e catálogo
# ---------------------------------------------------------------------------------------------

class PapeisChamados(BaseModel):
    """O que a pessoa pode fazer no módulo (a tela esconde o resto)."""
    abrir: bool
    atender: bool
    administrar: bool


class SetorResumo(BaseModel):
    id: int
    nome: str
    caminho: str = Field(description="Caminho na hierarquia (\"Subsecretaria > Núcleo de TI\").")


class ContextoChamados(BaseModel):
    papeis: PapeisChamados
    inicio_atendimento: date | None = Field(None, description="Data em que o SGI passa a receber os chamados de todos.")
    atendimento_aberto: bool = Field(False, description="A data já chegou: o \"Abrir chamado\" do sistema abre no SGI (e não mais no GLPI).")
    setores_do_usuario: list[SetorResumo] = Field(description="Setores de que a pessoa é membro: em nome deles ela pode abrir chamado (setor solicitante).")


TipoCampo = Literal["texto", "texto_longo", "numero", "data", "lista", "sim_nao"]


class CondicaoCampo(BaseModel):
    """O campo só aparece quando outro campo tem este valor."""
    campo_id: uuid.UUID
    igual: str


class CampoAdicional(BaseModel):
    """Campo adicional da categoria (ou herdado de uma categoria acima)."""
    id: uuid.UUID
    rotulo: str
    ajuda: str | None
    tipo: TipoCampo
    obrigatorio: bool
    dado_pessoal: bool = Field(description="Aparece mascarado para quem não atende (LGPD).")
    opcoes: list[str] | None
    condicao: CondicaoCampo | None
    ordem: int


class CategoriaCatalogo(BaseModel):
    """Categoria que pode ser escolhida na abertura."""
    id: uuid.UUID
    pai_id: uuid.UUID | None
    nome: str
    caminho: str
    nivel: int
    permite_incidente: bool
    permite_requisicao: bool
    perguntar_impedindo: bool
    setor_nome: str = Field(description="Setor responsável que vai atender (próprio ou herdado da categoria-mãe).")
    campos: list[CampoAdicional] = Field(default_factory=list, description="Campos adicionais (os da categoria e os herdados das categorias acima).")


class LocalResumo(BaseModel):
    id: uuid.UUID
    rotulo: str = Field(description="Ex.: \"5º andar › 05A03 — Setor Financeiro\".")
    codigo: str | None = Field(None, description="Código da sala (ex.: 05A03), para a leitura do QR da porta.")
    andar: int | None = Field(None, description="Andar da sala (-1 subsolo, 0 térreo), para agrupar a lista.")


class ChamadoRelacionavel(BaseModel):
    id: uuid.UUID
    numero: int
    titulo: str
    status_base: "StatusBase"
    aberto_em: datetime


class ContextoAbertura(BaseModel):
    local_sugerido: LocalResumo | None = Field(description="Sala do solicitante pelo Patrimônio (responsável pela sala, sala com mais bens dele ou a única sala do setor).")
    relacionaveis: list[ChamadoRelacionavel] = Field(description="Chamados do próprio solicitante, para escolher o relacionado.")


class PessoaResumo(BaseModel):
    id: int
    nome: str
    login: str = ""
    cargo: str = ""


# ---------------------------------------------------------------------------------------------
# Abertura e respostas
# ---------------------------------------------------------------------------------------------

class AberturaChamado(BaseModel):
    """JSON do campo `dados` do `POST /chamados` (multipart)."""
    titulo: str = Field(min_length=3, max_length=250)
    descricao: str = Field(min_length=1, description="HTML do editor (sanitizado no servidor; imagens coladas viram anexo).")
    categoria_id: uuid.UUID
    tipo: TipoChamado = "incidente"
    impedindo_trabalho: bool | None = Field(None, description="Resposta a \"Isso está impedindo você de trabalhar?\" (sim sobe a prioridade um nível).")
    setor_solicitante_id: int | None = Field(None, description="Abrir em nome de um setor de que a pessoa é membro: todos os membros recebem os avisos, inclusive por e-mail.")
    relacionado_id: uuid.UUID | None = Field(None, description="Chamado anterior relacionado (só um chamado do próprio solicitante).")
    localizacao_id: uuid.UUID | None = Field(None, description="Sala do Patrimônio onde está o problema.")
    rede_porta_id: uuid.UUID | None = Field(None, description="Porta de switch do problema (aberto a partir do plano de face).")
    rede_ponto_id: uuid.UUID | None = Field(None, description="Ponto de rede (tomada) do problema.")
    campos: dict[str, str | int | float | bool | None] = Field(default_factory=dict, description="Respostas dos campos adicionais: `{campo_id: valor}`.")


class NovaResposta(BaseModel):
    """JSON do campo `dados` do `POST /chamados/{numero}/acompanhamentos`."""
    texto: str = Field(min_length=1)
    privado: bool = Field(False, description="Só a equipe que atende escreve e vê mensagens privadas.")


class NovaSolucao(BaseModel):
    """JSON do campo `dados` do `POST /chamados/{numero}/solucao`."""
    texto: str = Field(min_length=1)


class Motivo(BaseModel):
    """Motivo de uma ação (pendente: opcional; não resolveu: obrigatório)."""
    motivo: str = Field("", max_length=2000)


class Alteracao(BaseModel):
    """Só os campos enviados mudam. `versao` é obrigatória (trava otimista)."""
    versao: int
    substatus_id: uuid.UUID | None = Field(None, description="Sub-status do status-base atual; `null` volta ao status-base.")
    categoria_id: uuid.UUID | None = None
    setor_id: int | None = None
    responsavel_id: int | None = Field(None, description="Pessoa ativa do setor responsável; `null` tira o responsável.")
    prioridade: "Prioridade | None" = None
    motivo_prioridade: str | None = Field(None, description="Obrigatório ao mudar a prioridade (vai para o histórico).")


class InclusaoEmCopia(BaseModel):
    usuario_id: int | None = None
    setor_id: int | None = None


class NovaTarefa(BaseModel):
    texto: str = Field(min_length=3, max_length=500)
    responsavel_id: int | None = None
    privada: bool = True


class MarcacaoTarefa(BaseModel):
    feita: bool


class PedidoAprovacao(BaseModel):
    alvo_usuario_id: int | None = None
    alvo_setor_id: int | None = None
    pedido: str = Field(min_length=3, max_length=2000)


class RespostaAprovacao(BaseModel):
    aprovar: bool
    resposta: str = Field("", max_length=2000, description="Obrigatória para não aprovar.")


class Assumir(BaseModel):
    versao: int = Field(description="Versão do chamado que a tela mostrou (trava otimista: outra alteração antes responde 409).")


# ---------------------------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------------------------

class PrazoSla(BaseModel):
    """Situação de um prazo (atendimento ou solução)."""
    vence_em: datetime | None
    cumprido_em: datetime | None = Field(None, description="Quando o prazo foi cumprido (primeira ação ou solução).")
    estourado: bool
    percentual: int | None = Field(None, description="Quanto do prazo já foi consumido, em horas úteis (0 a 100+); nulo sem SLA.")
    pausado: bool = Field(False, description="Chamado pendente: o relógio deste prazo está parado.")
    nivel: Literal["sem", "ok", "alerta", "atencao", "perigo", "cumprido"] = Field(
        "sem", description="Cor do prazo pelos limites dos Parâmetros (padrão 50% alerta, 75% atenção, 90% perigo; cumprido = verde).")


class ChamadoResumo(BaseModel):
    """Linha da fila e de "Meus chamados"."""
    id: uuid.UUID
    numero: int
    titulo: str = Field(description="\"Chamado restrito\" quando a categoria é sigilosa e a pessoa não atende o chamado.")
    tipo: TipoChamado
    status_base: StatusBase
    status_nome: str = Field("", description="Nome exibido do status (o do sub-status, se houver), conforme os Parâmetros.")
    status_cor: str = Field("info", description="Cor do status (token: info, alerta, atencao, perigo, sucesso, neutro).")
    substatus_id: uuid.UUID | None = None
    prioridade: Prioridade
    prioridade_origem: str
    categoria_id: uuid.UUID
    categoria_caminho: str
    setor_id: int
    setor_nome: str
    responsavel_id: int | None
    responsavel_nome: str
    solicitante_id: int | None
    solicitante_nome: str
    aberto_em: datetime
    solucionado_em: datetime | None
    atendimento: PrazoSla
    solucao: PrazoSla
    importado: bool


class ListaChamados(BaseModel):
    total: int
    itens: list[ChamadoResumo]


class AnexoLeitura(BaseModel):
    id: uuid.UUID = Field(description="Id do arquivo (usado em `GET /chamados/{numero}/anexos/{id}`).")
    nome: str
    tamanho: int
    tipo_conteudo: str
    privado: bool


class ItemLinhaTempo(BaseModel):
    """Um item da linha do tempo: acompanhamento (público, privado ou automático) ou solução."""
    id: uuid.UUID
    tipo: Literal["acompanhamento", "solucao"]
    autor_id: int | None
    autor_nome: str
    texto: str
    privado: bool
    automatico: bool
    criado_em: datetime
    anexos: list[AnexoLeitura]


class AcoesChamado(BaseModel):
    """O que a tela pode oferecer para esta pessoa neste chamado."""
    responder: bool
    responder_privado: bool
    assumir: bool
    solucionar: bool
    pendente: bool = False
    retomar: bool = False
    nao_resolveu: bool = Field(False, description="Solicitante, chamado resolvido e dentro do prazo de reabertura.")
    alterar: bool = False
    tarefas: bool = False
    pedir_aprovacao: bool = False
    incluir_em_copia: bool = False
    classificar: bool = Field(False, description="Quem atende: escolhe a categoria ITIL (também depois de resolvido).")


class RespostaCampo(BaseModel):
    campo_id: uuid.UUID
    rotulo: str
    valor: str = Field(description="Dado pessoal vem sempre mascarado; quem atende pede o valor completo em `GET /{numero}/dados-pessoais/{campo_id}` (auditado).")
    dado_pessoal: bool
    mascarado: bool
    pode_revelar: bool = Field(False, description="A pessoa atende o chamado e pode ver o valor completo (a consulta fica na auditoria).")


class EmCopia(BaseModel):
    id: uuid.UUID
    usuario_id: int | None
    setor_id: int | None
    nome: str


class TarefaLeitura(BaseModel):
    id: uuid.UUID
    texto: str
    estado: Literal["a_fazer", "feita"]
    privada: bool
    responsavel_id: int | None
    responsavel_nome: str
    autor_nome: str
    criado_em: datetime
    feita_em: datetime | None


class ValidacaoLeitura(BaseModel):
    id: uuid.UUID
    status: Literal["aguardando", "aprovada", "recusada"]
    alvo_nome: str
    pedido: str
    resposta: str
    solicitante_nome: str
    respondida_por_nome: str
    criado_em: datetime
    respondida_em: datetime | None
    posso_responder: bool


class AprovacaoPendente(BaseModel):
    """Item de "Minhas aprovações"."""
    id: uuid.UUID
    chamado_numero: int
    chamado_titulo: str
    pedido: str
    solicitante_nome: str
    alvo_nome: str
    criado_em: datetime


class ChamadoDetalhe(ChamadoResumo):
    descricao: str
    impedindo_trabalho: bool | None
    setor_solicitante_id: int | None
    setor_solicitante_nome: str
    versao: int
    reabrir_ate: datetime | None
    anexos: list[AnexoLeitura] = Field(description="Anexos da abertura.")
    linha_do_tempo: list[ItemLinhaTempo]
    acoes: AcoesChamado
    local: LocalResumo | None = None
    relacionado: ChamadoRelacionavel | None = None
    campos: list[RespostaCampo] = Field(default_factory=list)
    em_copia: list[EmCopia] = Field(default_factory=list)
    tarefas: list[TarefaLeitura] = Field(default_factory=list, description="As privadas só para quem atende.")
    validacoes: list[ValidacaoLeitura] = Field(default_factory=list)
    reaberturas: int = 0
    pendente_desde: datetime | None = None
    satisfacao: "SatisfacaoLeitura | None" = Field(None, description="Nota de satisfação (marco 6); nula enquanto o chamado não foi resolvido.")
    categoria_itil_id: uuid.UUID | None = Field(None, description="Classificação técnica (só para quem atende; nula = pendente ou não visível).")
    categoria_itil: str = Field("", description="Caminho da categoria ITIL (só para quem atende).")


class CategoriaItilResumo(BaseModel):
    id: uuid.UUID
    caminho: str


class Classificacao(BaseModel):
    versao: int
    categoria_itil_id: uuid.UUID | None = Field(None, description="Categoria ITIL ativa; `null` = pendente.")


class GravacaoCategoriaItil(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    pai_id: uuid.UUID | None = None
    ativa: bool = True
    ordem: int = 0


class CategoriaItilLeitura(GravacaoCategoriaItil):
    id: uuid.UUID
    caminho: str
    nivel: int
    chamados: int = Field(description="Chamados classificados nela.")


# ---------------------------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------------------------

class FaixaExpediente(BaseModel):
    dia_semana: int = Field(ge=0, le=6, description="0 = segunda ... 6 = domingo.")
    inicio: time
    fim: time


class GravacaoExpediente(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    ativo: bool = True
    faixas: list[FaixaExpediente] = Field(min_length=1)


class ExpedienteLeitura(GravacaoExpediente):
    id: uuid.UUID


class GravacaoSla(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    tipo: Literal["tto", "ttr"] = Field(description="`tto` = prazo de atendimento (primeira ação); `ttr` = prazo de solução.")
    tempo: int = Field(gt=0)
    unidade: Literal["minuto", "hora", "dia"]
    expediente_id: uuid.UUID = Field(description="Obrigatório: o prazo só anda dentro do expediente e fora dos feriados do RH.")
    ativo: bool = True


class SlaLeitura(GravacaoSla):
    id: uuid.UUID
    expediente_nome: str


class GravacaoCategoria(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    pai_id: uuid.UUID | None = None
    ativa: bool = True
    visivel_solicitante: bool = True
    permite_incidente: bool = True
    permite_requisicao: bool = True
    setor_id: int | None = Field(None, description="Setor responsável; vazio = herda da categoria-mãe (a raiz ativa precisa ter).")
    responsavel_id: int | None = None
    sla_tto_id: uuid.UUID | None = None
    sla_ttr_id: uuid.UUID | None = None
    prioridade_padrao: Prioridade | None = None
    perguntar_impedindo: bool = True
    sigilosa: bool = False
    ordem: int = 0
    categoria_itil_id: uuid.UUID | None = Field(None, description="Categoria ITIL que o chamado recebe ao abrir; vazio = herda da mãe ou fica pendente.")
    setores_permitidos: list[int] = Field(default_factory=list, description="\"Quem pode escolher este assunto\": só os membros destes setores (e dos de "
                                          "baixo). Vazio = vale `visivel_solicitante` (qualquer pessoa ou só quem atende).")


class CategoriaLeitura(GravacaoCategoria):
    id: uuid.UUID
    caminho: str
    nivel: int
    setor_efetivo_id: int | None
    setor_efetivo_nome: str
    herda_setor: bool


class GravacaoCampo(BaseModel):
    rotulo: str = Field(min_length=1, max_length=150)
    tipo: TipoCampo
    obrigatorio: bool = False
    dado_pessoal: bool = False
    ajuda: str | None = Field(None, max_length=300)
    opcoes: list[str] | None = Field(None, description="Obrigatório para `lista` (pelo menos duas).")
    condicao: CondicaoCampo | None = None
    ordem: int = 0
    ativo: bool = True


class CampoLeitura(GravacaoCampo):
    id: uuid.UUID
    categoria_id: uuid.UUID


CorStatus = Literal["info", "alerta", "atencao", "perigo", "sucesso", "neutro"]


class ParametrosGerais(BaseModel):
    dias_reabrir: int = Field(ge=1, le=30, description="Dias úteis para o solicitante dizer \"Não resolveu\".")
    ponto_facultativo_util: bool = Field(description="O ponto facultativo do RH conta como dia útil no prazo?")
    limite_alerta: int = Field(ge=1, le=100)
    limite_atencao: int = Field(ge=1, le=100)
    limite_perigo: int = Field(ge=1, le=100)
    inicio_atendimento: date | None = Field(None, description="A partir desta data todos abrem chamado no SGI (antes, pelo GLPI; só Controle total abre aqui, para testar).")


class StatusLeitura(BaseModel):
    status_base: StatusBase
    nome: str
    cor: CorStatus


class GravacaoStatus(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    cor: CorStatus


class GravacaoSubstatus(BaseModel):
    status_base: StatusBase
    nome: str = Field(min_length=1, max_length=60)
    cor: CorStatus
    ordem: int = 0
    ativo: bool = True


class SubstatusLeitura(GravacaoSubstatus):
    id: uuid.UUID


class SetorAtendimentoLeitura(BaseModel):
    setor_id: int
    nome: str
    caminho: str
    ve_todos: bool


class GravacaoSetorAtendimento(BaseModel):
    ve_todos: bool


class GravacaoRecorrente(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    categoria_id: uuid.UUID
    titulo: str = Field(min_length=3, max_length=250)
    descricao: str = ""
    periodicidade_quantidade: int = Field(1, gt=0)
    periodicidade_unidade: Literal["dia", "semana", "mes"] = "dia"
    antecedencia_min: int = Field(0, ge=0, le=10080, description="Abrir N minutos antes da ocorrência.")
    so_dias_uteis: bool = Field(True, description="Pula fim de semana e feriado do RH, mantendo o horário.")
    proxima_em: datetime = Field(description="Próxima ocorrência (data e hora).")
    fim_em: datetime | None = None
    ativo: bool = True
    solicitante_id: int | None = Field(None, description="Em nome de quem o chamado é aberto (padrão: quem cadastra).")


class RecorrenteLeitura(GravacaoRecorrente):
    id: uuid.UUID
    categoria_caminho: str
    solicitante_nome: str
    ultima_geracao_em: datetime | None


class TarefaSaude(BaseModel):
    tarefa: str
    ultima_em: datetime | None
    ultimo_estado: str | None
    ultima_ok_em: datetime | None
    ultimo_erro: str | None
    ultimo_resumo: str


class SaudeChamados(BaseModel):
    """Situação das tarefas automáticas e da fila de e-mail, calculada na hora."""
    tarefas: list[TarefaSaude]
    email_parados: int
    email_falhas_24h: int
    email_mais_antigo: datetime | None
    ultimo_erro_email: str | None
    problemas: list[str] = Field(description="Vazio quando está tudo funcionando.")


# ---------------------------------------------------------------------------------------------
# Marco 4: painel de TV, TVs pareadas e chamados do RH
# ---------------------------------------------------------------------------------------------

NivelPainel = Literal["sem", "ok", "alerta", "atencao", "perigo", "resolvido"]


class ItemPainel(BaseModel):
    """Uma linha do painel. Nada além do que a TV mostra: título oculto se a categoria for sigilosa, só os dois primeiros nomes."""
    numero: int
    titulo: str
    solicitante: str = Field(description="Dois primeiros nomes de quem pediu.")
    responsavel: str = Field(description="Dois primeiros nomes do responsável pelo atendimento (vazio = sem responsável).")
    local: str
    setor_nome: str
    aberto_em: datetime
    solucionado_em: datetime | None
    status_base: StatusBase
    status_nome: str
    prioridade: Prioridade
    nivel: NivelPainel = Field(description="Cor da linha: o pior entre os prazos de atendimento e de solução.")
    percentual: int | None = Field(None, description="Quanto do prazo que define a cor já foi consumido.")
    estourado: bool
    pausado: bool


class IndicadoresPainel(BaseModel):
    abertos: int
    sem_responsavel: int
    estourados: int = Field(description="Abertos com o prazo de solução estourado.")
    resolvidos_hoje: int


class ConfigPainel(BaseModel):
    """Como o painel aparece (Parâmetros > Painel). As cores do prazo (50/75/90%) ficam em `limites`, na aba Geral."""
    linhas_por_pagina: int = Field(0, ge=0, le=50, description="0 = automático: quantas linhas couberem na tela.")
    tamanho: Literal["compacto", "normal", "grande"] = Field("normal", description="Tamanho do texto (grande = para ler de longe na TV).")
    segundos_pagina: int = Field(15, ge=5, le=300, description="Quanto tempo cada página fica na tela quando não cabe tudo.")
    voz: bool = Field(True, description="Anunciar por voz os chamados novos.")
    cor_linha: bool = Field(True, description="Cor do prazo na linha inteira (`false`: só no selo da coluna Situação).")
    colunas: list[Literal["abertura", "titulo", "usuario", "local", "espera", "situacao", "responsavel"]] = Field(
        default_factory=lambda: ["abertura", "titulo", "usuario", "local", "espera", "situacao"], description="Colunas mostradas (o título é obrigatório).")


class EstadoPainel(BaseModel):
    """Tudo o que o painel desenha. A tela pede de novo quando chega um evento ao vivo (e, por garantia, a cada 2 minutos)."""
    area: str = Field(description="Nome do setor mostrado (e dos de baixo dele).")
    gerado_em: datetime
    config: ConfigPainel
    limites: dict[str, int] = Field(description="Percentuais das cores: `alerta`, `atencao` e `perigo`.")
    indicadores: IndicadoresPainel
    itens: list[ItemPainel] = Field(description="Só os abertos, sempre pela cor: vermelho, laranja, amarelo e branco (dentro da cor, quem gastou mais do prazo).")


class ConfigServicoRh(BaseModel):
    """Fila, prioridade e prazos de um serviço do RH."""
    setor_id: int | None = Field(None, description="Fila: o setor que atende o pedido (vazio = serviço sem destino).")
    prioridade: Literal["baixa", "normal", "alta", "urgente"] = "normal"
    sla_tto_id: uuid.UUID | None = Field(None, description="Prazo de atendimento (SLA do tipo `tto`); vazio = sem prazo.")
    sla_ttr_id: uuid.UUID | None = Field(None, description="Prazo de solução (SLA do tipo `ttr`); vazio = sem prazo.")


class ServicoRhLeitura(ConfigServicoRh):
    servico: str = Field(description="Chave do serviço (rede, email, sei, compras_sp, equipamento, estacao, cracha, telefone, mobiliario).")
    rotulo: str
    setor_nome: str = ""


class ParametrosRh(BaseModel):
    destino: Literal["glpi", "chamados", "na_data"] = Field(description="`glpi`: o RH envia o formulário do GLPI (hoje). `chamados`: o RH abre os chamados aqui. "
                                                        "`na_data`: GLPI até a data \"a partir de\" (Parâmetros > Geral) e, dali em diante, aqui.")
    destino_atual: Literal["glpi", "chamados"] = Field("glpi", description="Para onde o RH envia hoje (com `na_data`, depende de a data já ter chegado).")
    servicos: list[ServicoRhLeitura] = Field(description="Serviços da Nomeação.")
    servicos_exoneracao: list[ServicoRhLeitura] = Field(description="Serviços da Exoneração (o inverso de cada um da Nomeação).")


class GravacaoParametrosRh(BaseModel):
    destino: Literal["glpi", "chamados", "na_data"]
    servicos: dict[str, ConfigServicoRh] = Field(default_factory=dict, description="Nomeação: serviço → fila, prioridade e prazos. Para `chamados`, todos precisam de fila.")
    servicos_exoneracao: dict[str, ConfigServicoRh] = Field(default_factory=dict, description="Exoneração: serviço → fila, prioridade e prazos (mesma regra).")


# ---------------------------------------------------------------------------------------------
# Marco 6: satisfação, respostas prontas, motivos de pendência e relatórios
# ---------------------------------------------------------------------------------------------

class SatisfacaoLeitura(BaseModel):
    nota: int | None = Field(description="1 Péssimo, 2 Ruim, 3 Regular, 4 Bom, 5 Ótimo; nula enquanto não respondida.")
    rotulo: str
    comentario: str
    respondida_em: datetime | None
    pode_avaliar: bool = Field(description="A pessoa logada pode dar ou mudar a nota (solicitante ou setor solicitante, chamado resolvido).")


class Avaliacao(BaseModel):
    nota: int = Field(ge=1, le=5)
    comentario: str = Field("", max_length=2000)


class GravacaoRespostaPronta(BaseModel):
    titulo: str = Field(min_length=2, max_length=120)
    texto: str = Field(min_length=1, max_length=20000, description="HTML (saneado no servidor).")
    setor_id: int | None = Field(None, description="Sem setor: vale para todos os que atendem.")
    ativo: bool = True
    ordem: int = 0


class RespostaProntaLeitura(GravacaoRespostaPronta):
    id: uuid.UUID
    setor_nome: str


class GravacaoMotivo(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    ativo: bool = True
    ordem: int = 0


class MotivoLeitura(GravacaoMotivo):
    id: uuid.UUID


class LinhaRelatorio(BaseModel):
    id: str = Field("", description="Categoria (uuid) ou setor (número) da linha, para abrir a lista dos chamados dela.")
    nome: str
    abertos: int
    resolvidos: int
    no_prazo_pct: float | None = Field(description="Resolvidos dentro do prazo de solução, entre os que tinham prazo.")


class SemanaRelatorio(BaseModel):
    inicio: date
    abertos: int
    resolvidos: int
    em_aberto_fim: int = Field(0, description="Chamados em aberto no fim da semana (fila); sem o histórico importado.")
    reabertos: int = 0
    horas_mediana_solucao: float | None = None
    atendimento_no_prazo_pct: float | None = None


class PessoaEquipeRelatorio(BaseModel):
    """Quanto a pessoa rendeu: resolvidos (soluções registradas por ela) e assumidos (chamados com ela, assumidos na janela)."""
    usuario_id: int
    nome: str = Field(description="Os dois primeiros nomes.")
    resolvidos_7d: int
    assumidos_7d: int
    resolvidos_30d: int
    assumidos_30d: int
    resolvidos_semana: float = Field(description="Média por semana no período escolhido.")
    assumidos_semana: float


class SetorOpcao(BaseModel):
    id: int
    nome: str


class ResumoRelatorio(BaseModel):
    abertos_no_periodo: int
    resolvidos_no_periodo: int
    em_aberto_agora: int
    atendimento_no_prazo: int
    atendimento_com_prazo: int
    atendimento_no_prazo_pct: float | None
    solucao_no_prazo: int
    solucao_com_prazo: int
    solucao_no_prazo_pct: float | None
    horas_mediana_solucao: float | None = Field(description="Mediana, em horas corridas, da abertura à solução.")
    reabertos: int
    satisfacao_media: float | None
    satisfacao_respostas: int
    satisfacao_pedidas: int


class RelatorioChamados(BaseModel):
    area: str
    inicio: date
    fim: date
    resumo: ResumoRelatorio
    semanas: list[SemanaRelatorio]
    por_categoria: list[LinhaRelatorio] = Field(description="As 15 categorias com mais chamados abertos no período.")
    por_setor: list[LinhaRelatorio]
    por_prioridade: dict[str, int]
    notas: list[int] = Field(description="Quantas notas 1, 2, 3, 4 e 5 no período.")
    equipe: list[PessoaEquipeRelatorio] = Field(default_factory=list, description="As 12 pessoas que mais resolveram nos últimos 30 dias do período.")
    pode_escolher_setor: bool = Field(False, description="Controle total ou líder de um setor com setores abaixo: escolhe o setor e vê \"Por setor responsável\".")
    setores_opcoes: list[SetorOpcao] = Field(default_factory=list, description="Setores que a pessoa pode escolher (vazio se não escolhe).")


# A nota de satisfação é declarada depois do detalhe do chamado
ChamadoDetalhe.model_rebuild()
