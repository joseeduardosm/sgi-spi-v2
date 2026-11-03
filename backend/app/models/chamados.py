# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do módulo Chamados (atendimento de TI, DGA e demais setores do órgão).
"""Módulo Chamados (substitui a Assistência do GLPI).

Papéis no chamado (nomes do SGI, não os do GLPI):
- **Solicitante**: quem pediu (`solicitante_id`) e, opcionalmente, o setor em nome do qual pediu (`setor_solicitante_id`);
- **Em cópia**: quem acompanha e recebe os avisos (marco seguinte, tabela de atores);
- **Responsável**: o **setor responsável** (`setor_id`, qualquer setor ativo do SGI) e o **responsável pelo atendimento** (`responsavel_id`, a pessoa).

Tabelas deste arquivo:
- `ParametroChamados`: chave/valor editável (prazos, limites do painel, contador do número do chamado).
- `SetorAtendimentoChamados`: ajustes opcionais de um setor no atendimento (ver todos os chamados, área do painel de TV).
- `ExpedienteChamados` + `FaixaExpedienteChamados`: horário de trabalho usado no cálculo dos prazos (os feriados vêm do RH).
- `SlaChamados`: prazo de atendimento (TTO) ou de solução (TTR); **sempre** ligado a um expediente.
- `CategoriaChamados`: árvore de N níveis; o setor responsável e os SLAs herdam da categoria-mãe quando vazios.
- `Chamado`, `AcompanhamentoChamado`, `SolucaoChamado`, `AnexoChamado`: o chamado e a linha do tempo.
- `CampoChamados` + `ValorCampoChamado`: campos adicionais por categoria (valem para as subcategorias) e as respostas de cada chamado.
- `AtorChamado`: pessoas e setores **em cópia** (veem o chamado e recebem os avisos).
- `TarefaChamado`: tarefas da equipe dentro do chamado.
- `ValidacaoChamado`: aprovação pedida a uma pessoa ou a um setor.
- `StatusApresentacaoChamados` + `SubstatusChamados`: nome exibido e cor de cada status-base, e os sub-status dentro deles (Parâmetros).
- `RecorrenteChamados`: chamado aberto sozinho a cada período (ex.: "Validar os backups", todo dia útil às 8h).
- `ExecucaoChamados`: registro de cada rodada das tarefas automáticas (o vigia e o painel de saúde leem daqui).
- `ServicoRhChamados`: em qual categoria cai cada serviço pedido pelo RH na Nomeação (rede, e-mail, SEI...).
- `SatisfacaoChamado`: nota de 1 a 5 que o solicitante dá ao atendimento depois de resolvido.
- `RespostaProntaChamados`: textos que quem atende insere com um clique (Parâmetros).
- `MotivoPendenciaChamados`: motivos padronizados de "Pendente" (Parâmetros), para os relatórios.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, Time, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

# Status-base: ficam no código porque há regras que dependem deles (pausa do SLA, satisfação, encerramento).
# "solucionado" é o fim do chamado: não existe "fechado" (decisão do usuário).
STATUS_NOVO = "novo"
STATUS_EM_ATENDIMENTO = "em_atendimento"
STATUS_PENDENTE = "pendente"
STATUS_EM_APROVACAO = "em_aprovacao"
STATUS_SOLUCIONADO = "solucionado"
STATUS_BASE = (STATUS_NOVO, STATUS_EM_ATENDIMENTO, STATUS_PENDENTE, STATUS_EM_APROVACAO, STATUS_SOLUCIONADO)
# Status em que o chamado ainda está aberto (conta na fila, no painel e no relógio do SLA)
STATUS_ABERTOS = (STATUS_NOVO, STATUS_EM_ATENDIMENTO, STATUS_PENDENTE, STATUS_EM_APROVACAO)

TIPOS = ("incidente", "requisicao")
PRIORIDADES = ("baixa", "normal", "alta", "urgente")
# De onde veio a prioridade atual (vai para o histórico e explica o selo "Urgente: prazo estourado")
ORIGENS_PRIORIDADE = ("categoria", "solicitante", "responsavel", "sla", "importado")
TIPOS_SLA = ("tto", "ttr")
UNIDADES_SLA = ("minuto", "hora", "dia")
ALVOS_ANEXO = ("chamado", "acompanhamento", "solucao")
TIPOS_CAMPO = ("texto", "texto_longo", "numero", "data", "lista", "sim_nao")
ESTADOS_TAREFA = ("a_fazer", "feita")
STATUS_VALIDACAO = ("aguardando", "aprovada", "recusada")
# Cores possíveis de status e sub-status: os tokens de status do DESIGN.md (nunca hex)
CORES_STATUS = ("info", "alerta", "atencao", "perigo", "sucesso", "neutro")
UNIDADES_RECORRENCIA = ("dia", "semana", "mes")
ESTADOS_EXECUCAO = ("rodando", "ok", "erro")
# Fluxos do RH que abrem chamados: a Nomeação pede os serviços; a Exoneração pede o inverso (desativar, recolher, liberar)
FLUXOS_RH = ("nomeacao", "exoneracao")


def _lista(valores: tuple[str, ...]) -> str:
    """Valores para o CHECK do banco: ('a', 'b')."""
    return ", ".join(f"'{v}'" for v in valores)


class ParametroChamados(Base):
    """Parâmetro editável do módulo (chave e valor em texto, padrão de `patrimonio_parametros`)."""
    __tablename__ = "chamados_parametros"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(400))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class SetorAtendimentoChamados(Base):
    """Ajustes opcionais de um setor no atendimento. Sem linha aqui, o setor recebe chamados normalmente e vê só os dele."""
    __tablename__ = "chamados_setores_atendimento"

    # RESTRICT: setor com ajustes não pode sumir sem antes sair daqui (a reorganização dos setores preserva os que estão em uso)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"), primary_key=True)
    # Os membros enxergam todos os chamados do órgão, não só os do setor (a DGA, hoje)
    ve_todos: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Área do painel de TV (TI, DGA...): por padrão é o setor raiz do próprio setor
    area_painel_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


class ExpedienteChamados(Base):
    """Horário de trabalho (ex.: "Expediente padrão: seg a sex, 8h às 18h"). Os feriados vêm de `rh_feriados`."""
    __tablename__ = "chamados_expedientes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    faixas: Mapped[list["FaixaExpedienteChamados"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan", order_by="FaixaExpedienteChamados.dia_semana, FaixaExpedienteChamados.inicio"
    )


class FaixaExpedienteChamados(Base):
    """Uma faixa de horário em um dia da semana (0 = segunda ... 6 = domingo, como `date.weekday()`). Dia sem faixa = sem expediente."""
    __tablename__ = "chamados_expediente_faixas"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="ck_chamados_faixa_dia"),
        CheckConstraint("fim > inicio", name="ck_chamados_faixa_ordem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    expediente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_expedientes.id", ondelete="CASCADE"), index=True)
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    inicio: Mapped[time] = mapped_column(Time)
    fim: Mapped[time] = mapped_column(Time)

    expediente: Mapped[ExpedienteChamados] = relationship(back_populates="faixas")


class SlaChamados(Base):
    """Prazo de atendimento (tto: até a primeira ação do responsável) ou de solução (ttr), contado só dentro do expediente."""
    __tablename__ = "chamados_slas"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_SLA)})", name="ck_chamados_slas_tipo"),
        CheckConstraint(f"unidade IN ({_lista(UNIDADES_SLA)})", name="ck_chamados_slas_unidade"),
        CheckConstraint("tempo > 0", name="ck_chamados_slas_tempo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(String(3))
    tempo: Mapped[int] = mapped_column(Integer)
    unidade: Mapped[str] = mapped_column(String(6))
    # NOT NULL de propósito: não existe SLA contando 24 horas por 7 dias sem alguém escolher isso (no GLPI da SPI, todos contavam assim)
    expediente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_expedientes.id", ondelete="RESTRICT"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    expediente: Mapped[ExpedienteChamados] = relationship()


class CategoriaItilChamados(Base):
    """Categoria ITIL: a classificação técnica do chamado (ex.: "Infraestrutura > Servidores", "Acessos > Liberação de acesso").

    É separada da categoria de **assunto** (`CategoriaChamados`, o que quem abre escolhe: Impressoras, Crachás...). Só quem atende vê e muda.
    O assunto pode ter uma ITIL padrão (o chamado já nasce classificado) ou nenhuma (fica pendente para o técnico classificar).
    As categorias do GLPI entram aqui na migração, e não nos assuntos.
    """
    __tablename__ = "chamados_categorias_itil"
    __table_args__ = (
        Index("ux_chamados_categorias_itil_pai_nome", text("coalesce(CAST(pai_id AS VARCHAR), '')"), text("lower(nome)"), unique=True),
        Index("ux_chamados_categorias_itil_glpi", "origem_glpi_id", unique=True,
              postgresql_where=text("origem_glpi_id IS NOT NULL"), sqlite_where=text("origem_glpi_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_categorias_itil.id", ondelete="RESTRICT"), index=True)
    nome: Mapped[str] = mapped_column(String(150))
    caminho: Mapped[str] = mapped_column(String(800))
    nivel: Mapped[int] = mapped_column(SmallInteger, default=1)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    pai: Mapped["CategoriaItilChamados | None"] = relationship(remote_side="CategoriaItilChamados.id", back_populates="filhas")
    filhas: Mapped[list["CategoriaItilChamados"]] = relationship(back_populates="pai", order_by="CategoriaItilChamados.ordem, CategoriaItilChamados.nome")


class CategoriaSetorPermitido(Base):
    """"Quem pode escolher este assunto": só os membros destes setores (e dos setores abaixo deles) veem o assunto na abertura.
    Sem nenhuma linha, vale `visivel_solicitante` (qualquer pessoa ou só quem atende). Ex.: "CGP > Nomeação" só para a CGP."""
    __tablename__ = "chamados_categorias_setores"

    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="CASCADE"), primary_key=True)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True, index=True)


class CategoriaChamados(Base):
    """Nó da árvore de categorias. Campos vazios (setor, SLAs, prioridade) herdam da categoria-mãe."""
    __tablename__ = "chamados_categorias"
    __table_args__ = (
        # O nome não se repete dentro da mesma categoria-mãe (a raiz conta como uma mãe só)
        Index("ux_chamados_categorias_pai_nome", text("coalesce(CAST(pai_id AS VARCHAR), '')"), text("lower(nome)"), unique=True),
        Index("ux_chamados_categorias_glpi", "origem_glpi_id", unique=True,
              postgresql_where=text("origem_glpi_id IS NOT NULL"), sqlite_where=text("origem_glpi_id IS NOT NULL")),
        CheckConstraint(f"prioridade_padrao IS NULL OR prioridade_padrao IN ({_lista(PRIORIDADES)})", name="ck_chamados_categorias_prioridade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), index=True)
    nome: Mapped[str] = mapped_column(String(150))
    # Caminho completo para busca e exibição ("INFORMÁTICA > Rede e Internet > Ponto de Rede"), recalculado ao renomear ou mover
    caminho: Mapped[str] = mapped_column(String(800))
    nivel: Mapped[int] = mapped_column(SmallInteger, default=1)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Aparece para quem abre o chamado (as internas, como "Internos > Redes", só para os responsáveis)
    visivel_solicitante: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    permite_incidente: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    permite_requisicao: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Setor responsável (nulo = herda da mãe; a raiz ativa precisa ter, regra do serviço)
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"), index=True)
    # Responsável padrão (pessoa), opcional
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    sla_tto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="RESTRICT"))
    sla_ttr_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="RESTRICT"))
    prioridade_padrao: Mapped[str | None] = mapped_column(String(7))
    # Pergunta "Isso está impedindo você de trabalhar?" na abertura (sim sobe a prioridade um nível)
    perguntar_impedindo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Sigilosa: título oculto para quem não atende e no painel de TV
    sigilosa: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Categoria ITIL que o chamado recebe ao ser aberto neste assunto (nula = herda da mãe; sem nenhuma, fica pendente para o técnico)
    categoria_itil_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_categorias_itil.id", ondelete="SET NULL"))
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    pai: Mapped["CategoriaChamados | None"] = relationship(remote_side="CategoriaChamados.id", back_populates="filhas")
    filhas: Mapped[list["CategoriaChamados"]] = relationship(back_populates="pai", order_by="CategoriaChamados.ordem, CategoriaChamados.nome")
    campos: Mapped[list["CampoChamados"]] = relationship(order_by="CampoChamados.ordem, CampoChamados.criado_em", cascade="all, delete-orphan")
    setores_permitidos: Mapped[list[CategoriaSetorPermitido]] = relationship(cascade="all, delete-orphan")


class Chamado(Base):
    """O chamado. Solucionado é o fim; o importado do GLPI é somente leitura e não tem o SLA recalculado."""
    __tablename__ = "chamados"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS)})", name="ck_chamados_tipo"),
        CheckConstraint(f"status_base IN ({_lista(STATUS_BASE)})", name="ck_chamados_status"),
        CheckConstraint(f"prioridade IN ({_lista(PRIORIDADES)})", name="ck_chamados_prioridade"),
        CheckConstraint(f"prioridade_origem IN ({_lista(ORIGENS_PRIORIDADE)})", name="ck_chamados_prioridade_origem"),
        CheckConstraint("solicitante_id IS NOT NULL OR setor_solicitante_id IS NOT NULL OR solicitante_externo IS NOT NULL", name="ck_chamados_solicitante"),
        Index("ux_chamados_glpi", "origem_glpi_id", unique=True,
              postgresql_where=text("origem_glpi_id IS NOT NULL"), sqlite_where=text("origem_glpi_id IS NOT NULL")),
        # Fila: por setor, status e prioridade, sem os excluídos
        Index("ix_chamados_fila", "setor_id", "status_base", "prioridade",
              postgresql_where=text("excluido_em IS NULL"), sqlite_where=text("excluido_em IS NULL")),
        Index("ix_chamados_responsavel", "responsavel_id", "status_base"),
        Index("ix_chamados_solicitante", "solicitante_id", "aberto_em"),
        Index("ux_chamados_recorrencia", "recorrente_id", "gerado_para", unique=True,
              postgresql_where=text("recorrente_id IS NOT NULL"), sqlite_where=text("recorrente_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Número que as pessoas falam ("chamado 1530"). O importado mantém o número do GLPI; os novos continuam depois do maior.
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    tipo: Mapped[str] = mapped_column(String(10), default="incidente")
    titulo: Mapped[str] = mapped_column(String(250))
    # HTML já sanitizado no servidor (as imagens coladas viram anexo, nunca base64 no texto)
    descricao: Mapped[str] = mapped_column(Text)
    status_base: Mapped[str] = mapped_column(String(14), default=STATUS_NOVO, index=True)
    prioridade: Mapped[str] = mapped_column(String(7), default="normal")
    prioridade_origem: Mapped[str] = mapped_column(String(11), default="categoria")
    impedindo_trabalho: Mapped[bool | None] = mapped_column(Boolean)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="RESTRICT"), index=True)
    # Classificação técnica (só quem atende vê); nula = pendente de classificação
    categoria_itil_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_categorias_itil.id", ondelete="SET NULL"), index=True)
    # Setor responsável (obrigatório: todo chamado nasce com um setor) e o nome dele no momento da atribuição (histórico legível)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"))
    setor_nome: Mapped[str] = mapped_column(String(150))
    # Responsável pelo atendimento (a pessoa)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Setor em nome do qual o pedido foi feito: todos os membros recebem os avisos, inclusive por e-mail
    setor_solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="SET NULL"))
    # E-mail de quem não tem conta (chamados importados do GLPI)
    solicitante_externo: Mapped[str | None] = mapped_column(String(254))
    aberto_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    localizacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"))
    sla_tto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="SET NULL"))
    sla_ttr_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="SET NULL"))
    # Prazos calculados em horas úteis na abertura (o pendente empurra o prazo de solução)
    prazo_tto: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prazo_ttr: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Primeira ação de um responsável (cumpre o prazo de atendimento)
    tomado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    espera_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    espera_minutos_uteis: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tto_estourado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ttr_estourado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aberto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    solucionado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Até quando o solicitante pode dizer "Não resolveu" (5 dias úteis, parâmetro)
    reabrir_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reaberturas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Chamado anterior do mesmo solicitante (o serviço não aceita chamado de outra pessoa)
    relacionado_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados.id", ondelete="SET NULL"))
    # Chamado-pai (Nomeação/Exoneração geram um filho por serviço)
    pai_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados.id", ondelete="RESTRICT"), index=True)
    admissao_id: Mapped[int | None] = mapped_column(ForeignKey("rh_admissoes.id", ondelete="SET NULL"), index=True)
    # Serviço do RH que gerou o chamado (rede, email, sei...): a admissão mostra o andamento de cada um
    servico_rh: Mapped[str | None] = mapped_column(String(30))
    # Exoneração que gerou o chamado (a ocupação de cargo encerrada pelo RH)
    rh_ocupacao_id: Mapped[int | None] = mapped_column(ForeignKey("rh_ocupacoes.id", ondelete="SET NULL"), index=True)
    # Porta do switch ou ponto de rede do problema (plano de face): a porta mostra os chamados dela
    rede_porta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_portas.id", ondelete="SET NULL"), index=True)
    rede_ponto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_pontos.id", ondelete="SET NULL"), index=True)
    # Sub-status escolhido por quem atende (só vale enquanto o status-base for o dele)
    substatus_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_substatus.id", ondelete="SET NULL"))
    # Chamado gerado por um recorrente, e para qual ocorrência (a dupla é única: rodar duas vezes não duplica)
    recorrente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_recorrentes.id", ondelete="SET NULL"))
    gerado_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    importado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    # Trava otimista: duas pessoas não assumem nem alteram o mesmo chamado sem perceber
    versao: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    categoria: Mapped[CategoriaChamados] = relationship()
    categoria_itil: Mapped[CategoriaItilChamados | None] = relationship()
    acompanhamentos: Mapped[list["AcompanhamentoChamado"]] = relationship(
        back_populates="chamado", cascade="all, delete-orphan", order_by="AcompanhamentoChamado.criado_em"
    )
    solucoes: Mapped[list["SolucaoChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan", order_by="SolucaoChamado.criado_em")
    anexos: Mapped[list["AnexoChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan")
    valores: Mapped[list["ValorCampoChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan")
    atores: Mapped[list["AtorChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan")
    tarefas: Mapped[list["TarefaChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan", order_by="TarefaChamado.criado_em")
    validacoes: Mapped[list["ValidacaoChamado"]] = relationship(back_populates="chamado", cascade="all, delete-orphan", order_by="ValidacaoChamado.criado_em")


class AcompanhamentoChamado(Base):
    """Mensagem na linha do tempo. Privada: o solicitante nunca recebe. Automática: mudança de status, prioridade por SLA etc."""
    __tablename__ = "chamados_acompanhamentos"
    __table_args__ = (Index("ix_chamados_acompanhamentos_chamado", "chamado_id", "criado_em"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"))
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(Text)
    privado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    automatico: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="acompanhamentos")


class SolucaoChamado(Base):
    """Solução do chamado. A vigente encerra o chamado; ao reabrir, a anterior fica como substituída."""
    __tablename__ = "chamados_solucoes"
    __table_args__ = (CheckConstraint("status IN ('vigente', 'substituida')", name="ck_chamados_solucoes_status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(11), default="vigente")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="solucoes")


class AnexoChamado(Base):
    """Vínculo de um arquivo de `anexos` com o chamado e com o item da linha do tempo em que entrou."""
    __tablename__ = "chamados_anexos"
    __table_args__ = (CheckConstraint(f"alvo_tipo IN ({_lista(ALVOS_ANEXO)})", name="ck_chamados_anexos_alvo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    anexo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anexos.id", ondelete="RESTRICT"))
    alvo_tipo: Mapped[str] = mapped_column(String(14), default="chamado")
    alvo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Herda do acompanhamento privado: o solicitante não vê nem baixa
    privado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="anexos")
    anexo = relationship("Anexo")


class CampoChamados(Base):
    """Campo adicional de uma categoria (vale também para as subcategorias). Substitui os formulários simples do GLPI."""
    __tablename__ = "chamados_campos"
    __table_args__ = (CheckConstraint(f"tipo IN ({_lista(TIPOS_CAMPO)})", name="ck_chamados_campos_tipo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="CASCADE"), index=True)
    rotulo: Mapped[str] = mapped_column(String(150))
    ajuda: Mapped[str | None] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(String(12))
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Dado pessoal (CPF, RG, telefone pessoal...): aparece mascarado para quem não atende, e ver o valor completo fica auditado (LGPD)
    dado_pessoal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Opções da lista (tipo "lista")
    opcoes: Mapped[list | None] = mapped_column(TipoJson)
    # Só aparece se outro campo tiver um valor: {"campo_id": "...", "igual": "Sim"}
    condicao: Mapped[dict | None] = mapped_column(TipoJson)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ValorCampoChamado(Base):
    """Resposta de um campo adicional em um chamado (texto; números e datas em formato ISO)."""
    __tablename__ = "chamados_valores"

    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), primary_key=True)
    campo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_campos.id", ondelete="RESTRICT"), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)

    chamado: Mapped[Chamado] = relationship(back_populates="valores")
    campo: Mapped[CampoChamados] = relationship()


class AtorChamado(Base):
    """Pessoa ou setor **em cópia**: vê o chamado e recebe os avisos (pelo canal que cada um escolheu)."""
    __tablename__ = "chamados_atores"
    __table_args__ = (
        CheckConstraint("papel IN ('em_copia')", name="ck_chamados_atores_papel"),
        CheckConstraint("(usuario_id IS NULL) <> (setor_id IS NULL)", name="ck_chamados_atores_alvo"),
        Index("ix_chamados_atores_usuario", "usuario_id"),
        Index("ix_chamados_atores_setor", "setor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    papel: Mapped[str] = mapped_column(String(10), default="em_copia")
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="atores")


class TarefaChamado(Base):
    """Tarefa da equipe dentro do chamado (ex.: "trocar o toner", "pedir peça ao fornecedor")."""
    __tablename__ = "chamados_tarefas"
    __table_args__ = (CheckConstraint(f"estado IN ({_lista(ESTADOS_TAREFA)})", name="ck_chamados_tarefas_estado"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(7), default="a_fazer")
    # Privada: o solicitante não vê
    privada: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    feita_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="tarefas")


class ValidacaoChamado(Base):
    """Aprovação pedida a uma pessoa ou a um setor (qualquer membro do setor responde)."""
    __tablename__ = "chamados_validacoes"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(STATUS_VALIDACAO)})", name="ck_chamados_validacoes_status"),
        CheckConstraint("(alvo_usuario_id IS NULL) <> (alvo_setor_id IS NULL)", name="ck_chamados_validacoes_alvo"),
        Index("ix_chamados_validacoes_usuario", "alvo_usuario_id", "status"),
        Index("ix_chamados_validacoes_setor", "alvo_setor_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    alvo_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    alvo_setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="aguardando")
    pedido: Mapped[str] = mapped_column(Text, default="")
    resposta: Mapped[str] = mapped_column(Text, default="")
    respondida_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    chamado: Mapped[Chamado] = relationship(back_populates="validacoes")


class StatusApresentacaoChamados(Base):
    """Nome exibido e cor de um status-base (sem linha aqui, valem o nome e a cor padrão do código)."""
    __tablename__ = "chamados_status_apresentacao"
    __table_args__ = (
        CheckConstraint(f"status_base IN ({_lista(STATUS_BASE)})", name="ck_chamados_status_apresentacao_base"),
        CheckConstraint(f"cor IN ({_lista(CORES_STATUS)})", name="ck_chamados_status_apresentacao_cor"),
    )

    status_base: Mapped[str] = mapped_column(String(14), primary_key=True)
    nome: Mapped[str] = mapped_column(String(60))
    cor: Mapped[str] = mapped_column(String(8))


class SubstatusChamados(Base):
    """Sub-status dentro de um status-base (ex.: "Em atendimento › Aguardando peça"). As regras seguem o status-base."""
    __tablename__ = "chamados_substatus"
    __table_args__ = (
        CheckConstraint(f"status_base IN ({_lista(STATUS_BASE)})", name="ck_chamados_substatus_base"),
        CheckConstraint(f"cor IN ({_lista(CORES_STATUS)})", name="ck_chamados_substatus_cor"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status_base: Mapped[str] = mapped_column(String(14), index=True)
    nome: Mapped[str] = mapped_column(String(60))
    cor: Mapped[str] = mapped_column(String(8))
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class RecorrenteChamados(Base):
    """Chamado aberto sozinho a cada período. A próxima ocorrência anda pelo período; com "só em dia útil", pula fim de semana e feriado do RH."""
    __tablename__ = "chamados_recorrentes"
    __table_args__ = (
        CheckConstraint(f"periodicidade_unidade IN ({_lista(UNIDADES_RECORRENCIA)})", name="ck_chamados_recorrentes_unidade"),
        CheckConstraint("periodicidade_quantidade > 0", name="ck_chamados_recorrentes_quantidade"),
        CheckConstraint("antecedencia_min >= 0", name="ck_chamados_recorrentes_antecedencia"),
        Index("ix_chamados_recorrentes_proxima", "ativo", "proxima_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(200))
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="RESTRICT"))
    titulo: Mapped[str] = mapped_column(String(250))
    descricao: Mapped[str] = mapped_column(Text, default="")
    # Em nome de quem o chamado é aberto (quem cadastrou o recorrente, por padrão)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    periodicidade_quantidade: Mapped[int] = mapped_column(Integer, default=1)
    periodicidade_unidade: Mapped[str] = mapped_column(String(6), default="dia")
    # Abrir N minutos antes da ocorrência (ex.: 60 = o chamado das 8h aparece às 7h)
    antecedencia_min: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    so_dias_uteis: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    proxima_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_geracao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    categoria: Mapped[CategoriaChamados] = relationship()


class ExecucaoChamados(Base):
    """Uma rodada de uma tarefa automática dos Chamados. Rodada "rodando" há tempo demais é tratada como morta pelo vigia."""
    __tablename__ = "chamados_execucoes"
    __table_args__ = (
        CheckConstraint(f"estado IN ({_lista(ESTADOS_EXECUCAO)})", name="ck_chamados_execucoes_estado"),
        Index("ix_chamados_execucoes_tarefa", "tarefa", "iniciada_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tarefa: Mapped[str] = mapped_column(String(30))
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(8), default="rodando")
    resumo: Mapped[str] = mapped_column(String(300), default="")
    erro: Mapped[str | None] = mapped_column(Text)


class ServicoRhChamados(Base):
    """Fila de cada serviço pedido pelo RH (ex.: Nomeação › "Criar usuário de rede" → TI · Helpdesk), com a prioridade e os prazos dele.

    O chamado nasce no assunto fixo do fluxo ("Nomeação (RH)" ou "Exoneração (RH)", fora de uso para quem abre); a fila, a prioridade e os SLAs
    vêm daqui. `categoria_id` é da regra antiga (assunto por serviço) e não é mais usado."""
    __tablename__ = "chamados_servicos_rh"
    __table_args__ = (
        CheckConstraint(f"fluxo IN ({_lista(FLUXOS_RH)})", name="ck_chamados_servicos_rh_fluxo"),
        CheckConstraint(f"prioridade IN ({_lista(PRIORIDADES)})", name="ck_chamados_servicos_rh_prioridade"),
    )

    fluxo: Mapped[str] = mapped_column(String(12), primary_key=True)
    # Chave do serviço (as de `SOLICITACOES` do RH: rede, email, sei...)
    servico: Mapped[str] = mapped_column(String(30), primary_key=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_categorias.id", ondelete="RESTRICT"))
    # Fila: o setor que atende o pedido
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="SET NULL"))
    prioridade: Mapped[str] = mapped_column(String(7), default="normal", server_default="normal")
    sla_tto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="SET NULL"))
    sla_ttr_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chamados_slas.id", ondelete="SET NULL"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    categoria: Mapped[CategoriaChamados | None] = relationship()


class SatisfacaoChamado(Base):
    """Nota do solicitante (1 Péssimo a 5 Ótimo), pedida quando o chamado é resolvido. Reabrir apaga a pesquisa não respondida."""
    __tablename__ = "chamados_satisfacao"
    __table_args__ = (CheckConstraint("nota IS NULL OR nota BETWEEN 1 AND 5", name="ck_chamados_satisfacao_nota"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chamado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), unique=True)
    nota: Mapped[int | None] = mapped_column(SmallInteger)
    comentario: Mapped[str] = mapped_column(Text, default="", server_default="")
    pedida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    respondida_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)


class RespostaProntaChamados(Base):
    """Texto pronto para responder (ex.: "Reinicie o computador e teste de novo"). Sem setor = vale para todos os que atendem."""
    __tablename__ = "chamados_respostas_prontas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(120))
    texto: Mapped[str] = mapped_column(Text)
    setor_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class MotivoPendenciaChamados(Base):
    """Motivo padronizado para pôr um chamado em "Pendente" (ex.: "Aguardando peça"). Quem atende ainda pode escrever outro."""
    __tablename__ = "chamados_motivos_pendencia"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
