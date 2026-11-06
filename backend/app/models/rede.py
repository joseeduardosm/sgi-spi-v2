# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir as tabelas do plano de face da rede (switches, portas, VLANs, conexões e pontos de rede).
"""Plano de face da rede (recurso da ACL `rede`).

O GLPI não tem isto: lá as tomadas e os cabos estão vazios e o que existe vem do inventário SNMP. Aqui:
- `ModeloFaceRede`: o desenho da face de um modelo de equipamento (linhas × colunas, como as portas são numeradas, portas extras de uplink/fibra);
- `RackRede`: o rack (nome, cor, sala do Patrimônio e altura em U); os equipamentos ficam numa posição U dele;
- `EquipamentoRede`: switch, patch panel ou roteador, com o modelo de face, o bem do Patrimônio, a sala, o rack e o IP de gerência;
- `PortaRede`: cada porta, com a configuração lógica (VLAN nativa/access, trunk, descrição, velocidade, duplex, status, erros);
- `VlanRede` + `PortaVlanRede`: as VLANs e quais passam em cada porta (com ou sem tag);
- `ConexaoRede`: o que está ligado na porta (outra porta, um bem do Patrimônio ou só uma descrição);
- `PontoRede`: o ponto/tomada da sala, ligado à porta do patch panel (e, pela conexão, à porta do switch).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base, agora_utc
from app.models.auditoria import TipoJson

TIPOS_EQUIPAMENTO = ("switch", "patch_panel", "roteador", "access_point", "outro")
# Patch panel é passivo: o único tipo sem IP de gerência e sem função na topologia (decisão do usuário)
TIPOS_PASSIVOS = ("patch_panel",)
# Função na topologia (camadas): o núcleo em alta disponibilidade (primário e secundário), a distribuição e o acesso
FUNCOES_EQUIPAMENTO = ("core_primario", "core_secundario", "distribuicao", "acesso")
FUNCOES_CORE = ("core_primario", "core_secundario")
# Resultado do teste de ping no IP de gerência
SITUACOES_PING = ("no_ar", "fora")
# Como as portas são numeradas na face: por coluna (1 em cima, 2 embaixo, 3 em cima...) ou por linha (1..24 em cima, 25..48 embaixo)
NUMERACOES = ("coluna", "linha")
STATUS_PORTA = ("up", "down", "desativada")
# Modos de porta das marcas em uso (Cisco, Huawei, 3Com/H3C):
# - access: uma VLAN (sem tag), mais a VLAN de voz opcional;
# - trunk: VLAN nativa (sem tag) e as VLANs com tag;
# - hybrid (Huawei, 3Com/H3C): PVID, VLANs sem tag e VLANs com tag na mesma porta;
# - dot1q_tunnel (QinQ, Cisco e Huawei): a VLAN externa que a porta põe no quadro (fica em `vlan_nativa_id`);
# - dinamico_auto / dinamico_desejavel (DTP da Cisco): negocia trunk; guarda a VLAN de access e as de trunk;
# - roteada (porta L3: `no switchport` na Cisco, `undo portswitch` na Huawei): sem VLAN, com o IP da interface.
MODOS_PORTA = ("access", "trunk", "hybrid", "dot1q_tunnel", "dinamico_auto", "dinamico_desejavel", "roteada")
DUPLEX = ("full", "half")
# Cor do rack (para reconhecer na sala): nomes ligados aos tokens de cor do sistema, nunca hex
CORES_RACK = ("preto", "cinza", "azul", "verde", "amarelo", "laranja", "vermelho")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class ModeloFaceRede(Base):
    """Desenho da face de um modelo (ex.: "Switch 48 portas + 4 SFP": 2 linhas × 24 colunas, numeração por coluna, 4 portas de fibra à direita)."""
    __tablename__ = "rede_modelos_face"
    __table_args__ = (
        CheckConstraint(f"numeracao IN ({_lista(NUMERACOES)})", name="ck_rede_modelos_face_numeracao"),
        CheckConstraint("linhas BETWEEN 1 AND 8 AND colunas BETWEEN 1 AND 64", name="ck_rede_modelos_face_grade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150), unique=True)
    fabricante: Mapped[str] = mapped_column(String(120), default="", server_default="")
    linhas: Mapped[int] = mapped_column(Integer, default=2)
    colunas: Mapped[int] = mapped_column(Integer, default=24)
    numeracao: Mapped[str] = mapped_column(String(6), default="coluna")
    # Portas fora da grade principal (uplink, fibra): [{"numero": 49, "rotulo": "SFP 1", "tipo": "fibra"}]
    portas_extras: Mapped[list] = mapped_column(TipoJson, default=list)
    altura_u: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class RackRede(Base):
    """Rack (ex.: "Rack do 5º andar", 42U). A sala vem do Patrimônio; os equipamentos ocupam posições U dele, sem sobrepor."""
    __tablename__ = "rede_racks"
    __table_args__ = (
        CheckConstraint(f"cor IN ({_lista(CORES_RACK)})", name="ck_rede_racks_cor"),
        CheckConstraint("altura_u BETWEEN 1 AND 60", name="ck_rede_racks_altura"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    cor: Mapped[str] = mapped_column(String(10), default="preto", server_default="preto")
    localizacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"))
    altura_u: Mapped[int] = mapped_column(Integer, default=42, server_default="42")
    observacao: Mapped[str] = mapped_column(Text, default="", server_default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class EquipamentoRede(Base):
    """Switch, patch panel, roteador, access point. O bem do Patrimônio e a sala são opcionais (a carga do GLPI casa o que der).

    `funcao` e `ip_gerencia` são obrigatórios em todo tipo menos o patch panel; a exigência é na gravação pela API, e os que já existiam
    sem eles aparecem como "cadastro incompleto" até a próxima edição. `ping_*` é o teste periódico do IP de gerência (tarefa `rede ping`).
    """
    __tablename__ = "rede_equipamentos"
    __table_args__ = (
        CheckConstraint(f"tipo IN ({_lista(TIPOS_EQUIPAMENTO)})", name="ck_rede_equipamentos_tipo"),
        CheckConstraint(f"funcao IS NULL OR funcao IN ({_lista(FUNCOES_EQUIPAMENTO)})", name="ck_rede_equipamentos_funcao"),
        CheckConstraint(f"ping_situacao IS NULL OR ping_situacao IN ({_lista(SITUACOES_PING)})", name="ck_rede_equipamentos_ping"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(String(12), default="switch")
    modelo_face_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_modelos_face.id", ondelete="SET NULL"))
    bem_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="SET NULL"))
    localizacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"), index=True)
    rack_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_racks.id", ondelete="RESTRICT"), index=True)
    posicao_u: Mapped[int | None] = mapped_column(Integer)
    ip_gerencia: Mapped[str] = mapped_column(String(45), default="", server_default="")
    numero_serie: Mapped[str] = mapped_column(String(120), default="", server_default="")
    observacao: Mapped[str] = mapped_column(Text, default="", server_default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    funcao: Mapped[str | None] = mapped_column(String(16))
    # Teste de ping: `no_ar`/`fora` (vazio = nunca testado ou sem IP); "fora" só depois de N falhas seguidas
    ping_situacao: Mapped[str | None] = mapped_column(String(6))
    ping_falhas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ping_verificado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ping_mudou_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    modelo_face: Mapped[ModeloFaceRede | None] = relationship()
    rack: Mapped[RackRede | None] = relationship()
    portas: Mapped[list["PortaRede"]] = relationship(back_populates="equipamento", cascade="all, delete-orphan", order_by="PortaRede.numero_logico")


class VlanRede(Base):
    __tablename__ = "rede_vlans"
    __table_args__ = (CheckConstraint("numero BETWEEN 1 AND 4094", name="ck_rede_vlans_numero"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str] = mapped_column(Text, default="", server_default="")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # Cor do selo da VLAN (mesma paleta de 12 cores dos marcadores das Tarefas; 0 = cinza). Trocar a cor vale em todas as portas.
    cor_indice: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PortaRede(Base):
    """Uma porta do equipamento, com a configuração lógica. `numero_logico` é a posição na face (1, 2, 3...)."""
    __tablename__ = "rede_portas"
    __table_args__ = (
        UniqueConstraint("equipamento_id", "numero_logico", name="uq_rede_portas_numero"),
        CheckConstraint(f"status IS NULL OR status IN ({_lista(STATUS_PORTA)})", name="ck_rede_portas_status"),
        CheckConstraint(f"modo IN ({_lista(MODOS_PORTA)})", name="ck_rede_portas_modo"),
        CheckConstraint(f"duplex IS NULL OR duplex IN ({_lista(DUPLEX)})", name="ck_rede_portas_duplex"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipamento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rede_equipamentos.id", ondelete="CASCADE"))
    numero_logico: Mapped[int] = mapped_column(Integer)
    nome: Mapped[str] = mapped_column(String(120), default="", server_default="")
    # Descrição configurada no switch (ifAlias), ex.: "Sala 504 - impressora"
    descricao: Mapped[str] = mapped_column(String(250), default="", server_default="")
    mac: Mapped[str] = mapped_column(String(17), default="", server_default="")
    velocidade_mbps: Mapped[int | None] = mapped_column(Integer)
    duplex: Mapped[str | None] = mapped_column(String(4))
    status: Mapped[str | None] = mapped_column(String(10))
    modo: Mapped[str] = mapped_column(String(20), default="access", server_default="access")
    # VLAN da porta access, a nativa (sem tag) da trunk, a PVID da hybrid ou a VLAN externa da QinQ
    vlan_nativa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_vlans.id", ondelete="SET NULL"))
    # VLAN de voz (telefone IP) nas portas access, hybrid e dinâmicas
    vlan_voz_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_vlans.id", ondelete="SET NULL"))
    # IP da interface na porta roteada (ex.: 10.23.0.1/30)
    ip_interface: Mapped[str] = mapped_column(String(49), default="", server_default="")
    ultima_mudanca: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erros_entrada: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    erros_saida: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)

    equipamento: Mapped[EquipamentoRede] = relationship(back_populates="portas")
    vlans: Mapped[list["PortaVlanRede"]] = relationship(cascade="all, delete-orphan")


class PortaVlanRede(Base):
    """VLAN que passa na porta além da nativa/PVID: com tag (trunk, hybrid, dinâmicas) ou sem tag (só hybrid)."""
    __tablename__ = "rede_portas_vlans"

    porta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rede_portas.id", ondelete="CASCADE"), primary_key=True)
    vlan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rede_vlans.id", ondelete="CASCADE"), primary_key=True)
    com_tag: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ConexaoRede(Base):
    """O que está ligado numa porta: outra porta (patch panel ↔ switch, switch ↔ switch), um bem do Patrimônio ou só um texto.
    Cada porta aparece em no máximo uma conexão (dos dois lados). Com bem ou texto, pode haver dispositivos **atrás** dele (telefone IP → PC):
    `DispositivoAtrasRede`."""
    __tablename__ = "rede_conexoes"
    __table_args__ = (
        CheckConstraint("porta_b_id IS NULL OR porta_b_id <> porta_a_id", name="ck_rede_conexoes_diferentes"),
        Index("ux_rede_conexoes_a", "porta_a_id", unique=True),
        Index("ux_rede_conexoes_b", "porta_b_id", unique=True, postgresql_where=text("porta_b_id IS NOT NULL"),
              sqlite_where=text("porta_b_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    porta_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rede_portas.id", ondelete="CASCADE"))
    porta_b_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_portas.id", ondelete="CASCADE"))
    bem_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="SET NULL"))
    descricao: Mapped[str] = mapped_column(String(250), default="", server_default="")
    origem_glpi_id: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class DispositivoAtrasRede(Base):
    """Dispositivo ligado **atrás** do primeiro, na mesma porta (ex.: switch → telefone IP → PC: o telefone é a conexão; o PC fica aqui).
    Em ordem (1 = logo atrás do primeiro). É um bem do Patrimônio ou só uma descrição."""
    __tablename__ = "rede_dispositivos_atras"
    __table_args__ = (CheckConstraint("bem_id IS NOT NULL OR descricao <> ''", name="ck_rede_dispositivos_atras_alvo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conexao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rede_conexoes.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer, default=1)
    bem_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_bens.id", ondelete="SET NULL"), index=True)
    descricao: Mapped[str] = mapped_column(String(250), default="", server_default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class PontoRede(Base):
    """Ponto de rede (tomada) da sala: código na parede, sala do Patrimônio e a porta do patch panel em que chega."""
    __tablename__ = "rede_pontos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    localizacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patrimonio_localizacoes.id", ondelete="SET NULL"), index=True)
    porta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rede_portas.id", ondelete="SET NULL"), unique=True)
    observacao: Mapped[str] = mapped_column(Text, default="", server_default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ParametroRede(Base):
    """Parâmetro editável do módulo Rede (chave e valor em texto), como o do Patrimônio. Ex.: `ping_intervalo_min`."""
    __tablename__ = "rede_parametros"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)
