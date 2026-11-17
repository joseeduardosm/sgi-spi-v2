# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados da API do plano de face da rede (/api/rede).
"""Schemas do plano de face da rede (`/api/rede`)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoEquipamento = Literal["switch", "patch_panel", "roteador", "access_point", "firewall", "servidor", "outro"]
FuncaoEquipamento = Literal["core_primario", "core_secundario", "distribuicao", "acesso"]
SituacaoPing = Literal["no_ar", "fora"]
# Lado físico da porta do patch panel: cada porta tem um cabo no fundo e outro na frente
LadoPatch = Literal["fundo", "frente"]


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


class LigacaoCadastro(BaseModel):
    """O cabo informado no cadastro (cadastro em cadeia): "este equipamento, na porta X, está conectado no equipamento Y, na porta Y"."""
    porta_numero: int = Field(ge=1, description="Número lógico da porta **deste** equipamento (do modelo de face).")
    destino_porta_id: uuid.UUID = Field(description="Porta do equipamento de cima, ou de um patch panel no caminho.")
    destino_lado: LadoPatch | None = Field(None, description="Lado da porta de destino quando ela é de patch panel; o outro lado precisa levar a quem fica acima.")
    config: "GravacaoPorta | None" = Field(None, description="Configuração da porta deste equipamento (o status é sempre `up`).")
    config_destino: "GravacaoPorta | None" = Field(None, description="Configuração da porta de destino (ignorada em patch panel).")


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
    funcao: FuncaoEquipamento | None = Field(None, description="Função do **switch** na topologia (obrigatória nele). Nos demais tipos é ignorada. Não muda depois de criado (`409 funcao_travada`).")
    acesso_usuario: str = Field("", max_length=120, description="Usuário SSH só leitura para a carga do equipamento (vazio = sem acesso). Patch panel não tem.")
    acesso_porta: int = Field(22, ge=1, le=65535, description="Porta SSH do equipamento.")


class EscritaEquipamento(GravacaoEquipamento):
    """Gravação do equipamento com a senha do acesso SSH (só na escrita: a senha nunca volta na API)."""
    acesso_senha: str | None = Field(None, max_length=200, description="Senha SSH em texto (cifrada ao gravar). Vazia ou ausente mantém a gravada.")


class CriacaoEquipamento(EscritaEquipamento):
    """Cadastro de equipamento novo: os dados e o cabo para quem fica acima dele."""
    ligacao: LigacaoCadastro | None = Field(None, description="Obrigatória em todo equipamento menos core primário e patch panel (`400 sem_ligacao`). "
                                             "Fora da cadeia: `409 cadeia_incompleta` (falta o core, a distribuição ou o acesso) ou `409 cadeia_invalida`.")


class PortaElegivel(BaseModel):
    """Porta (e lado, no patch panel) onde o equipamento novo pode ser ligado no cadastro."""
    porta_id: uuid.UUID
    lado: LadoPatch | None = Field(None, description="Lado livre da porta do patch panel; o outro lado da mesma porta leva a quem pode ficar acima.")


class DestinoCadastro(BaseModel):
    """Equipamento elegível em "Conectado em" e as portas dele que servem."""
    equipamento_id: uuid.UUID
    portas: list[PortaElegivel]


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
    tem_acesso: bool = Field(False, description="Tem usuário e senha SSH gravados (a senha nunca volta na API).")
    leitura_em: datetime | None = Field(None, description="Quando o equipamento foi lido por SSH pela última vez.")


class ParametrosRede(BaseModel):
    ping_intervalo_min: int = Field(1, ge=1, le=60, description="Minutos entre as rodadas de ping (1 a 60).")


class DispositivoAtrasLeitura(BaseModel):
    """Dispositivo atrás do primeiro, na mesma porta (ex.: o PC ligado no telefone IP)."""
    id: uuid.UUID
    ordem: int
    texto: str
    bem_id: uuid.UUID | None = None


class GravacaoDispositivoAtras(BaseModel):
    lado: LadoPatch | None = Field(None, description="Lado da porta, quando ela é de patch panel (`fundo` ou `frente`).")
    bem_id: uuid.UUID | None = Field(None, description="Bem do Patrimônio (ex.: o PC).")
    descricao: str = Field("", max_length=250, description="Ou só uma descrição (ex.: \"Notebook do visitante\").")


class ConexaoLeitura(BaseModel):
    """O outro lado da porta (no patch panel, de um dos lados dela)."""
    tipo: Literal["porta", "bem", "descricao"]
    lado: LadoPatch | None = Field(None, description="Lado desta porta nesta ligação (só patch panel).")
    outro_lado: LadoPatch | None = Field(None, description="Lado da outra porta, quando ela é de patch panel.")
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
    conexao: ConexaoLeitura | None = Field(description="O que está ligado (fora do patch panel). No patch panel, a primeira ligação que houver (fundo, depois frente).")
    fundo: ConexaoLeitura | None = Field(None, description="Patch panel: o que está ligado no fundo da porta.")
    frente: ConexaoLeitura | None = Field(None, description="Patch panel: o que está ligado na frente da porta.")
    observacao: str = Field("", description="Anotação livre da porta. A `descricao` é gerada pelo sistema a partir das ligações (\"Desligado\" sem nada).")
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
    observacao: str = Field("", max_length=4000, description="Anotação livre (opcional). A descrição não é gravada: o sistema a gera pelas ligações.")
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
    lado: LadoPatch | None = Field(None, description="Lado desta porta, obrigatório quando ela é de patch panel (`fundo` ou `frente`).")
    porta_id: uuid.UUID | None = Field(None, description="Outra porta (de patch panel ou de outro equipamento).")
    outro_lado: LadoPatch | None = Field(None, description="Lado da outra porta, obrigatório quando ela é de patch panel.")
    bem_id: uuid.UUID | None = Field(None, description="Bem do Patrimônio ligado na porta.")
    descricao: str = Field("", max_length=250, description="Ou só uma descrição do que está ligado (ex.: \"Telefone da recepção\").")


class TrocaConexao(GravacaoConexao):
    """Troca o que está ligado na porta (ou no lado dela) por outra coisa, numa operação só."""
    religar_antigo: bool = Field(False, description="Quando o novo destino é um lado de patch panel e o antigo era outra porta: liga o outro lado "
                                                    "daquela porta do patch panel no destino antigo (pôr um patch panel no meio do cabo).")


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
    lado: LadoPatch | None = Field(None, description="Lado da porta, quando ela é de patch panel.")
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
    lado_entrada: LadoPatch | None = Field(None, description="Patch panel: lado da porta por onde o cabo chega de cima.")
    lado_saida: LadoPatch | None = Field(None, description="Patch panel: lado da porta por onde o cabo segue para baixo.")


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
    portas_patch_um_lado: int = Field(description="Portas de patch panel com um lado ligado e o outro vazio (o cabo para no meio do caminho).")


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


class TesteLeitura(BaseModel):
    """Testar e ler um equipamento ainda não cadastrado (passo Dados do cadastro)."""
    ip: str = Field(min_length=3, max_length=45)
    usuario: str = Field(min_length=1, max_length=120)
    senha: str = Field(min_length=1, max_length=200)
    porta: int = Field(22, ge=1, le=65535)
    modelo_face_id: uuid.UUID | None = Field(None, description="Modelo escolhido: traduz o nome das interfaces para as portas da face.")
    tipo: TipoEquipamento = "switch"
    funcao: FuncaoEquipamento | None = None


class ResultadoTesteLeitura(BaseModel):
    tipo_acesso: str = Field("", description="Tipo de equipamento que funcionou (ex.: huawei_vrpv8).")
    nome: str = ""
    modelo: str = ""
    serie: str = ""
    versao: str = ""
    portas: int = 0
    vlans: int = 0
    vizinhos: list[dict] = Field(default_factory=list, description="Vizinhos LLDP: `{interface_local, vizinho_nome, vizinho_interface}`.")
    avisos: list[str] = Field(default_factory=list)
    sugestao: dict | None = Field(None, description="Cabo de subida sugerido: `{porta_numero, destino_equipamento_id, destino_porta_id, texto}`.")


class ResumoLeitura(BaseModel):
    """O que a leitura do equipamento traz de diferente do cadastro, em grupos."""
    id: uuid.UUID
    lido_em: datetime
    lido_por: str
    aplicada_em: datetime | None = None
    tipo_acesso: str = ""
    equipamento: dict = Field(description="`{serie_lida, serie_cadastro, modelo, versao, nome_lido}`.")
    vlans_novas: list[dict] = Field(description="VLANs do equipamento que o SGI não tem: `{numero, nome}`.")
    lldp: list[dict] = Field(description="Vizinhos LLDP e o que aconteceu: `situacao` = `ligada` (ligada agora), `ja_estava` ou `nao_ligou` (com `motivo`).")
    descricoes: list[dict] = Field(description="Portas com link e descrição no switch, sem nada em \"Ligado a\": `{interface, porta_id, porta, descricao}`.")
    configuracao: list[dict] = Field(description="Portas com configuração lida diferente da cadastrada: `{interface, porta_id, porta, atual, lida, ligada}`.")
    portas_sem_ligacao: int = Field(0, description="Portas com configuração lida, mas sem ligação no SGI nem descrição no switch: não entram na lista (configuração só em porta ligada).")
    avisos: list[str] = Field(default_factory=list)


class AplicacaoLeitura(BaseModel):
    """Itens do resumo marcados para aplicar."""
    equipamento: bool = Field(False, description="Gravar o número de série (e modelo/versão na observação).")
    vlans: list[int] = Field(default_factory=list, description="VLANs novas para cadastrar.")
    descricoes: list[str] = Field(default_factory=list, description="Interfaces para ligar como descrição (o texto configurado no switch).")
    configuracao: list[str] = Field(default_factory=list, description="Interfaces para aplicar a configuração lida (só portas ligadas).")


# Referências adiantadas (a ligação do cadastro usa a gravação de porta, definida mais abaixo)
LigacaoCadastro.model_rebuild()
CriacaoEquipamento.model_rebuild()
