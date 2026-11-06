# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da API do plano de face da rede (/api/rede).
"""Schemas do plano de face da rede (`/api/rede`)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoEquipamento = Literal["switch", "patch_panel", "roteador", "access_point", "outro"]
FuncaoEquipamento = Literal["core_primario", "core_secundario", "distribuicao", "acesso"]
SituacaoPing = Literal["no_ar", "fora"]


class PapeisRede(BaseModel):
    ver: bool
    editar: bool
    administrar: bool


class PortaExtra(BaseModel):
    numero: int = Field(ge=1, description="Número da porta (maior que as da grade).")
    rotulo: str = Field("", max_length=20, description="Ex.: \"SFP 1\".")
    tipo: Literal["cobre", "fibra"] = "cobre"


class GravacaoModelo(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    fabricante: str = Field("", max_length=120)
    linhas: int = Field(2, ge=1, le=8)
    colunas: int = Field(24, ge=1, le=64)
    numeracao: Literal["coluna", "linha"] = Field("coluna", description="`coluna`: 1 em cima, 2 embaixo, 3 em cima...; `linha`: 1..N na primeira linha.")
    portas_extras: list[PortaExtra] = Field(default_factory=list)
    altura_u: int = Field(1, ge=1, le=10)


class ModeloLeitura(GravacaoModelo):
    id: uuid.UUID
    equipamentos: int


class GravacaoEquipamento(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    tipo: TipoEquipamento = "switch"
    modelo_face_id: uuid.UUID | None = Field(None, description="Ao criar, as portas são criadas pelo modelo. Depois de criado não muda (`409 modelo_travado`).")
    bem_id: uuid.UUID | None = None
    localizacao_id: uuid.UUID | None = None
    rack_id: uuid.UUID | None = Field(None, description="Rack já cadastrado (`/rede/racks`).")
    posicao_u: int | None = Field(None, ge=1, le=60, description="U mais baixo que o equipamento ocupa (U1 = embaixo); exige o rack. Não pode sobrepor outro equipamento.")
    ip_gerencia: str = Field("", max_length=45, description="Obrigatório em todo tipo menos `patch_panel` (é o que o ping testa).")
    numero_serie: str = Field("", max_length=120)
    observacao: str = Field("", max_length=4000)
    ativo: bool = True
    funcao: FuncaoEquipamento | None = Field(None, description="Função na topologia; obrigatória em todo tipo menos `patch_panel` (no patch panel é ignorada).")


class EquipamentoResumo(GravacaoEquipamento):
    id: uuid.UUID
    modelo_nome: str
    altura_u: int = Field(1, description="Quantos U o equipamento ocupa no rack (do modelo de face; sem modelo, 1).")
    rack_nome: str
    sala: str
    portas_total: int
    portas_up: int
    portas_down: int
    portas_desativadas: int
    ping_situacao: SituacaoPing | None = Field(None, description="Último resultado do ping (`fora` só depois de 3 falhas seguidas); vazio = sem teste.")
    ping_verificado_em: datetime | None = None
    ping_mudou_em: datetime | None = Field(None, description="Quando passou a estar na situação atual.")
    cadastro_incompleto: bool = Field(False, description="Sem IP de gerência ou sem função (cadastro de antes da regra): a próxima edição exige os dois.")


class ParametrosRede(BaseModel):
    ping_intervalo_min: int = Field(1, ge=1, le=60, description="Minutos entre as rodadas de ping (1 a 60).")


class DispositivoAtrasLeitura(BaseModel):
    """Dispositivo atrás do primeiro, na mesma porta (ex.: o PC ligado no telefone IP)."""
    id: uuid.UUID
    ordem: int
    texto: str
    bem_id: uuid.UUID | None = None


class GravacaoDispositivoAtras(BaseModel):
    bem_id: uuid.UUID | None = Field(None, description="Bem do Patrimônio (ex.: o PC).")
    descricao: str = Field("", max_length=250, description="Ou só uma descrição (ex.: \"Notebook do visitante\").")


class ConexaoLeitura(BaseModel):
    """O outro lado da porta."""
    tipo: Literal["porta", "bem", "descricao"]
    texto: str = Field(description="Ex.: \"Patch panel 3A · porta 12\", \"Impressora (chapa 012345)\".")
    porta_id: uuid.UUID | None = None
    equipamento_id: uuid.UUID | None = None
    bem_id: uuid.UUID | None = None
    atras: list[DispositivoAtrasLeitura] = Field(default_factory=list, description="Dispositivos atrás do primeiro, em ordem (switch → telefone IP → PC).")


class PortaLeitura(BaseModel):
    id: uuid.UUID
    numero_logico: int
    nome: str
    descricao: str
    mac: str
    velocidade_mbps: int | None
    duplex: str | None
    status: str | None
    modo: str
    vlan_nativa_id: uuid.UUID | None
    vlan_nativa: int | None = Field(description="Número da VLAN access, nativa (trunk), PVID (hybrid) ou externa (QinQ).")
    vlans_tag: list[int] = Field(description="Números das VLANs com tag (trunk, hybrid e dinâmicas).")
    vlans_tag_ids: list[uuid.UUID]
    vlans_sem_tag: list[int] = Field(default_factory=list, description="Números das VLANs sem tag além da PVID (só hybrid).")
    vlans_sem_tag_ids: list[uuid.UUID] = Field(default_factory=list)
    vlan_voz_id: uuid.UUID | None = None
    vlan_voz: int | None = Field(None, description="Número da VLAN de voz (access, hybrid e dinâmicas).")
    ip_interface: str = Field("", description="IP da interface (só porta roteada).")
    ultima_mudanca: datetime | None
    erros_entrada: int
    erros_saida: int
    conexao: ConexaoLeitura | None
    ponto: str = Field(description="Código do ponto de rede que chega nesta porta (vazio se nenhum).")
    chamados_abertos: int


class EquipamentoDetalhe(EquipamentoResumo):
    modelo: ModeloLeitura | None
    posicoes: dict[int, tuple[int, int]] = Field(description="Número da porta → (linha, coluna) na grade do modelo.")
    portas: list[PortaLeitura]
    alterado_por: str | None = Field(None, description="Quem fez a alteração mais recente em alguma porta do equipamento; nulo se nenhuma porta foi alterada.")
    alterado_em: datetime | None = Field(None, description="Quando foi essa alteração.")
    alterado_porta_id: uuid.UUID | None = Field(None, description="A porta dessa alteração.")
    alterado_porta: str | None = Field(None, description="Nome (ou número) da porta dessa alteração.")


class ChamadoDaPorta(BaseModel):
    numero: int
    titulo: str
    status_base: str
    aberto_em: datetime


class PortaDetalhe(PortaLeitura):
    equipamento_id: uuid.UUID
    equipamento_nome: str
    equipamento_tipo: str = Field(description="Tipo do equipamento: em `patch_panel` a porta não tem parte lógica (só descrição e situação).")
    alterado_por: str | None = Field(None, description="Quem fez a última alteração da porta (nome completo, ou o autor técnico como `sistema:carga-lldp`); nulo se nunca foi alterada.")
    alterado_em: datetime | None = Field(None, description="Quando foi a última alteração da porta.")
    chamados: list[ChamadoDaPorta] = Field(description="Chamados da porta e do ponto que chega nela (só os que a pessoa enxerga nos Chamados).")


class GravacaoPorta(BaseModel):
    descricao: str = Field("", max_length=250)
    modo: Literal["access", "trunk", "hybrid", "dot1q_tunnel", "dinamico_auto", "dinamico_desejavel", "roteada"] = Field(
        "access", description="access, trunk, hybrid (Huawei/3Com), dot1q_tunnel (QinQ), dinamico_auto/dinamico_desejavel (DTP Cisco) ou roteada (L3).")
    vlan_nativa_id: uuid.UUID | None = Field(None, description="VLAN access, nativa (trunk), PVID (hybrid) ou externa (QinQ); a roteada não tem.")
    vlans_tag: list[uuid.UUID] = Field(default_factory=list, description="Só em trunk, hybrid e dinâmicas.")
    vlans_sem_tag: list[uuid.UUID] = Field(default_factory=list, description="Só em hybrid (além da PVID).")
    vlan_voz_id: uuid.UUID | None = Field(None, description="VLAN de voz: só em access, hybrid e dinâmicas.")
    ip_interface: str = Field("", max_length=49, description="IP da porta roteada com a máscara (ex.: 10.23.0.1/30).")
    velocidade_mbps: int | None = Field(None, ge=1)
    duplex: Literal["full", "half"] | None = None
    status: Literal["up", "down", "desativada"] | None = None


class GravacaoConexao(BaseModel):
    porta_id: uuid.UUID | None = Field(None, description="Outra porta (de patch panel ou de outro equipamento).")
    bem_id: uuid.UUID | None = Field(None, description="Bem do Patrimônio ligado na porta.")
    descricao: str = Field("", max_length=250)
    forcar: bool = Field(False, description="Liga mesmo com porta descrita no switch (dispositivo provável), depois da confirmação na tela.")


class GravacaoVlan(BaseModel):
    numero: int = Field(ge=1, le=4094)
    nome: str = Field("", max_length=120)
    descricao: str = Field("", max_length=2000)
    cor_indice: int | None = Field(None, ge=0, le=11, description="Cor do selo (paleta dos marcadores: 0–11). Ausente: mantém a atual; na criação, sorteia uma de 1 a 11.")


class VlanLeitura(GravacaoVlan):
    id: uuid.UUID
    cor_indice: int
    portas: int


class GravacaoPonto(BaseModel):
    codigo: str = Field(min_length=1, max_length=40, description="Como está escrito na tomada (ex.: \"5A-12\").")
    localizacao_id: uuid.UUID | None = None
    porta_id: uuid.UUID | None = Field(None, description="Porta do patch panel em que o ponto chega.")
    observacao: str = Field("", max_length=2000)


class PontoLeitura(GravacaoPonto):
    id: uuid.UUID
    sala: str
    caminho: list[str] = Field(description="Do ponto até o switch: [\"Patch panel 5A · 12\", \"Switch 5º andar · 7\"].")


class BemResumo(BaseModel):
    """Bem do Patrimônio para ligar numa porta (busca pela chapa ou pela descrição)."""
    id: uuid.UUID
    chapa: str
    descricao: str
    sala: str


class PortaDoBem(BaseModel):
    """Porta de rede em que o bem está ligado (aparece no cadastro do bem)."""
    porta_id: uuid.UUID
    porta_nome: str
    equipamento_id: uuid.UUID
    equipamento_nome: str
    atras_de: str = Field("", description="Quando o bem está atrás de outro dispositivo na porta (ex.: \"Telefone IP (chapa 012345)\"); vazio = direto na porta.")
    dispositivo_id: uuid.UUID | None = Field(None, description="Atrás de outro: o registro dele (para tirar só este bem, sem desligar a porta).")


CorRack = Literal["preto", "cinza", "azul", "verde", "amarelo", "laranja", "vermelho"]


class GravacaoRack(BaseModel):
    nome: str = Field(min_length=1, max_length=80, description="Ex.: \"Rack do 5º andar\".")
    cor: CorRack = "preto"
    localizacao_id: uuid.UUID | None = Field(None, description="Sala do Patrimônio onde fica o rack.")
    altura_u: int = Field(42, ge=1, le=60, description="Quantidade de U do rack.")
    observacao: str = Field("", max_length=2000)


class RackLeitura(GravacaoRack):
    id: uuid.UUID
    sala: str
    equipamentos: int


class SalaResumo(BaseModel):
    id: uuid.UUID
    codigo: str
    nome: str
    rotulo: str = Field("", description="Ex.: \"5º andar › 05A03 — Setor Financeiro\" (o mesmo do Patrimônio).")
    andar: int | None = Field(None, description="Andar (-1 subsolo, 0 térreo), para agrupar a lista.")


class NoTopologia(BaseModel):
    """Um equipamento na árvore da rede (os filhos são os que se ligam a ele por cabo)."""
    id: uuid.UUID
    nome: str
    tipo: TipoEquipamento
    funcao: FuncaoEquipamento | None = None
    ping_situacao: SituacaoPing | None = None
    assumiu: bool = Field(False, description="Core Secundário no lugar de referência porque o Primário está fora do ar.")
    rack_nome: str
    rack_cor: CorRack | None
    sala: str
    ip_gerencia: str
    portas_total: int
    portas_up: int
    portas_down: int
    pontos: int = Field(description="Pontos de rede (tomadas) que chegam nas portas deste equipamento.")
    bens: int = Field(description="Bens do Patrimônio ligados direto nas portas deste equipamento.")
    porta_acima: str = Field(description="Porta deste equipamento que liga ao de cima (vazio na raiz).")
    porta_no_pai: str = Field(description="Porta do equipamento de cima em que o cabo chega.")
    cabos_com_pai: int = Field(description="Quantos cabos ligam este equipamento ao de cima (mais de 1 = agregação ou redundância).")
    tambem_ligado: list[str] = Field(description="Outros equipamentos ligados a este fora da árvore (uplink redundante, anel).")
    filhos: list["NoTopologia"]


class TopologiaRede(BaseModel):
    raizes: list[NoTopologia] = Field(description="As árvores, grupo a grupo: num grupo com cores, um por core (o de referência primeiro); sem core, uma pelo núcleo automático.")
    sem_ligacao: list[NoTopologia] = Field(description="Equipamentos ativos sem cabo para nenhum outro equipamento (pendência do cadastro).")


class EtapaCaminho(BaseModel):
    """Um degrau do caminho até o core (de cima para baixo)."""
    tipo: Literal["equipamento", "ponto"]
    nome: str
    cabo: str = Field("", description="Cabo que liga este degrau ao de cima: \"porta de cima ↔ porta deste\" (vazio no topo).")
    equipamento_id: uuid.UUID | None = None
    tipo_equipamento: TipoEquipamento | None = None
    funcao: FuncaoEquipamento | None = None
    ping_situacao: SituacaoPing | None = None
    porta_entrada: "PortaLeitura | None" = Field(None, description="Porta deste equipamento no cabo que sobe (o quadradinho de cima, com a configuração completa).")
    porta_saida: "PortaLeitura | None" = Field(None, description="Porta deste equipamento no cabo que desce para o próximo degrau (o quadradinho de baixo).")


class DispositivoCaminho(BaseModel):
    texto: str
    bem_id: uuid.UUID | None = None


class CaminhoRede(BaseModel):
    etapas: list[EtapaCaminho] = Field(description="Do core até o último equipamento (e o ponto de rede, se houver), na ordem.")
    dispositivos: list[DispositivoCaminho] = Field(description="O que está ligado na porta, na ordem da cascata (ex.: telefone IP → computador).")
    cabo_dispositivos: str = Field("", description="Porta em que os dispositivos estão ligados.")
    aviso: str = Field("", description="Ex.: o equipamento não tem cabo até o core.")


class IndicadoresRede(BaseModel):
    """Números dos cards do topo da tela da Rede."""
    portas_alteradas: int = Field(description="Portas com qualquer alteração (configuração, ligação, dispositivo atrás, ponto ou carga LLDP) nos últimos 7 dias.")
    portas_ativas_sem_descricao: int = Field(description="Portas ligadas (status `up`) sem descrição.")


class PortaListada(BaseModel):
    """Linha das listas dos indicadores: equipamento | porta | descrição | quem alterou e quando (a última alteração)."""
    porta_id: uuid.UUID
    equipamento_id: uuid.UUID
    equipamento_nome: str
    porta: str = Field(description="Nome da interface ou, sem ele, o número da porta.")
    numero_logico: int
    descricao: str
    alterado_por: str | None = Field(description="Nome de quem fez a última alteração (ou o autor técnico, ex.: `sistema:carga-lldp`); nulo se nunca foi alterada.")
    alterado_em: datetime | None
