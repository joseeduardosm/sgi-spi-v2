# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras do plano de face da rede: quem pode o quê, equipamentos, portas, VLANs, conexões e pontos.
"""Plano de face da rede (recurso da ACL `rede`).

Papéis, como nos Chamados, **fechado até haver regras** (dados de infraestrutura): sem nenhuma regra nem perfil, só o SuperRoot entra.
- **Leitura** (ver): vê equipamentos, faces, portas, VLANs, conexões e pontos, e os chamados de cada porta (os que já enxerga nos Chamados);
- **Modificação** (editar): muda a configuração lógica das portas, liga e desliga conexões, cadastra pontos de rede;
- **Controle total** (administrar): modelos de face, equipamentos, VLANs e exclusões.

Regras que o banco também garante: cada porta aparece em uma conexão só (dos dois lados); o número da porta é único no equipamento;
o código do ponto é único; um ponto chega em uma porta só.
"""

import ipaddress
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.acl import NivelAcl
from app.models.chamados import Chamado
from app.models.patrimonio import Bem, Localizacao
from app.models.rede import (
    CORES_RACK, DUPLEX, FUNCOES_CORE, FUNCOES_EQUIPAMENTO, MODOS_PORTA, NUMERACOES, STATUS_PORTA, TIPOS_EQUIPAMENTO, TIPOS_PASSIVOS, ConexaoRede, DispositivoAtrasRede, EquipamentoRede, ModeloFaceRede, PontoRede, PortaRede,
    PortaVlanRede, RackRede, VlanRede,
)
from app.models.usuario import Usuario
from app.services import servico_acl

RECURSO_ACL = "rede"


class ErroRede(Exception):
    """Regra do plano de face violada (vira `{"detalhe", "codigo"}` na rota)."""

    def __init__(self, mensagem: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo


@dataclass(frozen=True)
class PapeisRede:
    ver: bool
    editar: bool
    administrar: bool


def papeis(sessao: Session, usuario: Usuario) -> PapeisRede:
    if usuario.superusuario:
        return PapeisRede(True, True, True)
    if not servico_acl.possui_regras(sessao, RECURSO_ACL):
        return PapeisRede(False, False, False)
    administrar = servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.CONTROLE_TOTAL)
    editar = administrar or servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.MODIFICACAO)
    ver = editar or servico_acl.pode_porta(sessao, usuario, RECURSO_ACL, NivelAcl.LEITURA)
    return PapeisRede(ver, editar, administrar)


def _nao_encontrado(o_que: str) -> ErroRede:
    return ErroRede(f"{o_que} não encontrado.", 404, "nao_encontrado")


# ---------------------------------------------------------------------------------------------
# Modelos de face
# ---------------------------------------------------------------------------------------------

def posicoes(modelo: ModeloFaceRede) -> dict[int, tuple[int, int]]:
    """Número da porta → (linha, coluna) na grade, começando em 1. Por coluna: 1 em cima, 2 embaixo, 3 em cima...; por linha: 1..N na 1ª linha."""
    resultado = {}
    for indice in range(modelo.linhas * modelo.colunas):
        if modelo.numeracao == "coluna":
            linha, coluna = indice % modelo.linhas + 1, indice // modelo.linhas + 1
        else:
            linha, coluna = indice // modelo.colunas + 1, indice % modelo.colunas + 1
        resultado[indice + 1] = (linha, coluna)
    return resultado


def _validar_extras(modelo: ModeloFaceRede, extras: list[dict]) -> list[dict]:
    maior = modelo.linhas * modelo.colunas
    vistos, limpos = set(), []
    for e in extras:
        numero = int(e.get("numero", 0))
        if numero <= maior or numero in vistos:
            raise ErroRede(f"Porta extra {numero}: o número precisa ser maior que {maior} (as da grade) e não repetir.")
        vistos.add(numero)
        limpos.append({"numero": numero, "rotulo": str(e.get("rotulo") or numero)[:20], "tipo": "fibra" if e.get("tipo") == "fibra" else "cobre"})
    return sorted(limpos, key=lambda x: x["numero"])


def listar_modelos(sessao: Session) -> list[ModeloFaceRede]:
    return list(sessao.scalars(select(ModeloFaceRede).order_by(ModeloFaceRede.nome)))


def salvar_modelo(sessao: Session, modelo_id: uuid.UUID | None, nome: str, fabricante: str, linhas: int, colunas: int, numeracao: str,
                  extras: list[dict], altura_u: int) -> ModeloFaceRede:
    nome = " ".join(nome.split())
    if not 2 <= len(nome) <= 150:
        raise ErroRede("O nome do modelo precisa ter de 2 a 150 caracteres.")
    if numeracao not in NUMERACOES or not 1 <= linhas <= 8 or not 1 <= colunas <= 64:
        raise ErroRede("Grade inválida: de 1 a 8 linhas, de 1 a 64 colunas, numeração por coluna ou por linha.")
    repetido = sessao.scalar(select(ModeloFaceRede).where(func.lower(ModeloFaceRede.nome) == nome.lower()))
    if repetido is not None and repetido.id != modelo_id:
        raise ErroRede("Já existe um modelo com este nome.", 409, "duplicado")
    modelo = sessao.get(ModeloFaceRede, modelo_id) if modelo_id else ModeloFaceRede()
    if modelo is None:
        raise _nao_encontrado("Modelo de face")
    modelo.nome, modelo.fabricante, modelo.linhas, modelo.colunas, modelo.numeracao = nome, fabricante.strip()[:120], linhas, colunas, numeracao
    modelo.altura_u = max(1, min(altura_u, 10))
    modelo.portas_extras = _validar_extras(modelo, extras)
    sessao.add(modelo)
    sessao.flush()
    return modelo


def excluir_modelo(sessao: Session, modelo_id: uuid.UUID) -> None:
    modelo = sessao.get(ModeloFaceRede, modelo_id)
    if modelo is None:
        raise _nao_encontrado("Modelo de face")
    if sessao.scalar(select(EquipamentoRede.id).where(EquipamentoRede.modelo_face_id == modelo_id).limit(1)) is not None:
        raise ErroRede("Há equipamentos com este modelo: troque o modelo deles antes de excluir.", 409, "em_uso")
    sessao.delete(modelo)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Equipamentos e portas
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosEquipamento:
    nome: str
    tipo: str = "switch"
    modelo_face_id: uuid.UUID | None = None
    bem_id: uuid.UUID | None = None
    localizacao_id: uuid.UUID | None = None
    rack_id: uuid.UUID | None = None
    posicao_u: int | None = None
    ip_gerencia: str = ""
    numero_serie: str = ""
    observacao: str = ""
    ativo: bool = True
    funcao: str | None = None


def cadastro_incompleto(e: EquipamentoRede) -> bool:
    """Equipamento ativo (não passivo) sem IP de gerência ou sem função: veio de antes da regra e precisa ser completado na próxima edição."""
    return e.tipo not in TIPOS_PASSIVOS and (not e.ip_gerencia or not e.funcao)


def listar_equipamentos(sessao: Session, busca: str = "", tipo: str | None = None) -> list[EquipamentoRede]:
    consulta = select(EquipamentoRede).options(selectinload(EquipamentoRede.modelo_face)).order_by(EquipamentoRede.nome)
    if busca.strip():
        termo = f"%{busca.strip()}%"
        consulta = consulta.where(or_(EquipamentoRede.nome.ilike(termo), EquipamentoRede.ip_gerencia.ilike(termo),
                                      EquipamentoRede.rack_id.in_(select(RackRede.id).where(RackRede.nome.ilike(termo)))))
    if tipo:
        consulta = consulta.where(EquipamentoRede.tipo == tipo)
    return list(sessao.scalars(consulta))


def resumo_portas(sessao: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Counter]:
    """Por equipamento: total de portas e quantas up, down e desativadas."""
    resultado: dict[uuid.UUID, Counter] = {i: Counter() for i in ids}
    for equipamento_id, status, total in sessao.execute(
        select(PortaRede.equipamento_id, PortaRede.status, func.count()).where(PortaRede.equipamento_id.in_(ids or [uuid.uuid4()]))
        .group_by(PortaRede.equipamento_id, PortaRede.status)
    ):
        resultado[equipamento_id]["total"] += total
        resultado[equipamento_id][status or "sem"] += total
    return resultado


def obter_equipamento(sessao: Session, equipamento_id: uuid.UUID) -> EquipamentoRede:
    item = sessao.scalar(select(EquipamentoRede).options(selectinload(EquipamentoRede.portas).selectinload(PortaRede.vlans),
                                                         selectinload(EquipamentoRede.modelo_face)).where(EquipamentoRede.id == equipamento_id))
    if item is None:
        raise _nao_encontrado("Equipamento")
    return item


def _validar_equipamento(sessao: Session, d: DadosEquipamento, equipamento_id: uuid.UUID | None = None) -> None:
    if not 2 <= len(d.nome.strip()) <= 150:
        raise ErroRede("O nome precisa ter de 2 a 150 caracteres.")
    if d.tipo not in TIPOS_EQUIPAMENTO:
        raise ErroRede("Tipo inválido (switch, patch_panel, roteador, access_point ou outro).")
    # Todo equipamento ativo de rede tem IP de gerência (é o que o ping testa) e função na topologia; só o patch panel, passivo, não tem
    if d.tipo in TIPOS_PASSIVOS:
        d.funcao = None
    else:
        if not d.ip_gerencia.strip():
            raise ErroRede("Informe o IP de gerência (obrigatório em todo equipamento, menos patch panel).")
        if d.funcao not in FUNCOES_EQUIPAMENTO:
            raise ErroRede("Escolha a função na topologia: core primário, core secundário, distribuição ou acesso.")
    if d.ip_gerencia.strip():
        try:
            ipaddress.ip_address(d.ip_gerencia.strip())
        except ValueError as erro:
            raise ErroRede("IP de gerência inválido.") from erro
    if d.modelo_face_id and sessao.get(ModeloFaceRede, d.modelo_face_id) is None:
        raise ErroRede("Modelo de face não encontrado.")
    if d.bem_id and sessao.get(Bem, d.bem_id) is None:
        raise ErroRede("Bem do Patrimônio não encontrado.")
    if d.localizacao_id and sessao.get(Localizacao, d.localizacao_id) is None:
        raise ErroRede("Sala não encontrada.")
    if d.rack_id is None:
        if d.posicao_u:
            raise ErroRede("Escolha o rack antes da posição (U).")
        return
    rack = sessao.get(RackRede, d.rack_id)
    if rack is None:
        raise ErroRede("Rack não encontrado.")
    if d.posicao_u:
        modelo = sessao.get(ModeloFaceRede, d.modelo_face_id) if d.modelo_face_id else None
        altura = modelo.altura_u if modelo else 1
        topo = d.posicao_u + altura - 1
        if topo > rack.altura_u:
            raise ErroRede(f"O equipamento ocupa do U{d.posicao_u} ao U{topo}, mas o rack {rack.nome} tem {rack.altura_u}U.")
        for outro in sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.rack_id == rack.id, EquipamentoRede.posicao_u.is_not(None),
                                                                   EquipamentoRede.id != (equipamento_id or uuid.uuid4()))):
            alt = outro.modelo_face.altura_u if outro.modelo_face else 1
            if d.posicao_u <= outro.posicao_u + alt - 1 and outro.posicao_u <= topo:
                raise ErroRede(f"O U{d.posicao_u} já está ocupado por {outro.nome} no rack {rack.nome}.", 409, "posicao_ocupada")


def gerar_portas(sessao: Session, equipamento: EquipamentoRede) -> int:
    """Cria as portas que faltam pelo modelo de face (as da grade e as extras). Não apaga nenhuma. Devolve quantas criou."""
    if equipamento.modelo_face is None:
        return 0
    numeros = list(range(1, equipamento.modelo_face.linhas * equipamento.modelo_face.colunas + 1))
    rotulos = {}
    for e in equipamento.modelo_face.portas_extras or []:
        numeros.append(e["numero"])
        rotulos[e["numero"]] = e.get("rotulo", "")
    existentes = {p.numero_logico for p in equipamento.portas}
    novas = [PortaRede(numero_logico=n, nome=rotulos.get(n, str(n))) for n in numeros if n not in existentes]
    equipamento.portas.extend(novas)
    sessao.flush()
    return len(novas)


def salvar_equipamento(sessao: Session, equipamento_id: uuid.UUID | None, d: DadosEquipamento) -> EquipamentoRede:
    _validar_equipamento(sessao, d, equipamento_id)
    item = obter_equipamento(sessao, equipamento_id) if equipamento_id else EquipamentoRede(portas=[])
    novo = equipamento_id is None
    trocou_modelo = item.modelo_face_id != d.modelo_face_id
    if (item.ip_gerencia or "") != d.ip_gerencia.strip():
        # IP novo: o resultado do ping antigo não vale mais; o próximo teste diz a situação
        item.ping_situacao, item.ping_falhas, item.ping_verificado_em, item.ping_mudou_em = None, 0, None, None
    for campo, valor in d.__dict__.items():
        setattr(item, campo, valor.strip() if isinstance(valor, str) else valor)
    sessao.add(item)
    sessao.flush()
    if novo or trocou_modelo:
        sessao.refresh(item, ["modelo_face"])
        gerar_portas(sessao, item)
    return item


def excluir_equipamento(sessao: Session, equipamento_id: uuid.UUID) -> None:
    sessao.delete(obter_equipamento(sessao, equipamento_id))
    sessao.flush()


@dataclass
class DadosPorta:
    descricao: str = ""
    modo: str = "access"
    vlan_nativa_id: uuid.UUID | None = None
    vlans_tag: list[uuid.UUID] | None = None
    vlans_sem_tag: list[uuid.UUID] | None = None
    vlan_voz_id: uuid.UUID | None = None
    ip_interface: str = ""
    velocidade_mbps: int | None = None
    duplex: str | None = None
    status: str | None = None


def obter_porta(sessao: Session, porta_id: uuid.UUID) -> PortaRede:
    porta = sessao.get(PortaRede, porta_id)
    if porta is None:
        raise _nao_encontrado("Porta")
    return porta


# O que cada modo aceita, além da VLAN nativa/PVID/externa (`vlan_nativa_id`, que a roteada não tem)
MODOS_COM_TAG = ("trunk", "hybrid", "dinamico_auto", "dinamico_desejavel")
MODOS_COM_VOZ = ("access", "hybrid", "dinamico_auto", "dinamico_desejavel")
ROTULOS_MODO = {"access": "access", "trunk": "trunk", "hybrid": "hybrid", "dot1q_tunnel": "QinQ (dot1q-tunnel)", "dinamico_auto": "dinâmico auto",
                "dinamico_desejavel": "dinâmico desirable", "roteada": "roteada (L3)"}


def alterar_porta(sessao: Session, porta_id: uuid.UUID, d: DadosPorta) -> PortaRede:
    """Configuração lógica: descrição, modo, VLANs, velocidade, duplex e status (inclusive "desativada").

    Regras por modo (ver `MODOS_PORTA`): VLANs com tag só em trunk, hybrid e dinâmicas; VLANs sem tag (além da PVID) só em hybrid;
    VLAN de voz em access, hybrid e dinâmicas; a roteada não tem VLAN nenhuma e é a única com IP da interface (validado).
    """
    porta = obter_porta(sessao, porta_id)
    if d.modo not in MODOS_PORTA:
        raise ErroRede("Modo inválido.")
    rotulo = ROTULOS_MODO[d.modo]
    ids, sem_tag = set(d.vlans_tag or []), set(d.vlans_sem_tag or [])
    if ids and d.modo not in MODOS_COM_TAG:
        raise ErroRede(f"Porta {rotulo} não tem VLANs com tag (só trunk, hybrid e dinâmicas).")
    if sem_tag and d.modo != "hybrid":
        raise ErroRede("Várias VLANs sem tag é coisa da porta hybrid.")
    if ids & sem_tag:
        raise ErroRede("A mesma VLAN não passa com e sem tag na mesma porta.")
    if d.vlan_voz_id and d.modo not in MODOS_COM_VOZ:
        raise ErroRede(f"Porta {rotulo} não tem VLAN de voz (só access, hybrid e dinâmicas).")
    if d.modo == "roteada" and d.vlan_nativa_id:
        raise ErroRede("Porta roteada (L3) não tem VLAN: o endereço fica no IP da interface.")
    ip = d.ip_interface.strip()
    if ip and d.modo != "roteada":
        raise ErroRede("O IP da interface é só da porta roteada (L3).")
    if ip:
        try:
            ip = str(ipaddress.ip_interface(ip))
        except ValueError:
            raise ErroRede("IP da interface inválido (ex.: 10.23.0.1/30).") from None
    if d.duplex is not None and d.duplex not in DUPLEX:
        raise ErroRede("Duplex inválido (full ou half).")
    if d.status is not None and d.status not in STATUS_PORTA:
        raise ErroRede("Status inválido (up, down ou desativada).")
    # Porta com qualquer coisa ligada (outra porta, bem ou descrição) está necessariamente ligada (decisão do usuário):
    # para desligar ou desativar, primeiro se retira o que está nela
    if d.status != "up" and conexao_da_porta(sessao, porta.id) is not None:
        raise ErroRede(f"A porta {_nome_porta(porta)} tem um equipamento ligado e fica \"ligada\": retire o equipamento antes de mudar o status.",
                       409, "porta_com_equipamento")
    pedidas = ids | sem_tag | {v for v in (d.vlan_nativa_id, d.vlan_voz_id) if v}
    if pedidas - {v.id for v in sessao.scalars(select(VlanRede).where(VlanRede.id.in_(pedidas)))}:
        raise ErroRede("VLAN não encontrada.")
    porta.descricao, porta.modo, porta.vlan_nativa_id = d.descricao.strip()[:250], d.modo, d.vlan_nativa_id
    porta.vlan_voz_id, porta.ip_interface = d.vlan_voz_id, ip
    porta.velocidade_mbps, porta.duplex, porta.status = d.velocidade_mbps, d.duplex, d.status
    # A nativa/PVID já passa sem tag: não se repete na lista
    porta.vlans = [PortaVlanRede(vlan_id=v, com_tag=True) for v in sorted(ids - {d.vlan_nativa_id}, key=str)] + \
                  [PortaVlanRede(vlan_id=v, com_tag=False) for v in sorted(sem_tag - {d.vlan_nativa_id}, key=str)]
    sessao.flush()
    return porta


# ---------------------------------------------------------------------------------------------
# VLANs
# ---------------------------------------------------------------------------------------------

def listar_vlans(sessao: Session) -> list[VlanRede]:
    return list(sessao.scalars(select(VlanRede).order_by(VlanRede.numero)))


def salvar_vlan(sessao: Session, vlan_id: uuid.UUID | None, numero: int, nome: str, descricao: str) -> VlanRede:
    if not 1 <= numero <= 4094:
        raise ErroRede("O número da VLAN vai de 1 a 4094.")
    repetida = sessao.scalar(select(VlanRede).where(VlanRede.numero == numero))
    if repetida is not None and repetida.id != vlan_id:
        raise ErroRede(f"A VLAN {numero} já existe.", 409, "duplicado")
    vlan = sessao.get(VlanRede, vlan_id) if vlan_id else VlanRede()
    if vlan is None:
        raise _nao_encontrado("VLAN")
    vlan.numero, vlan.nome, vlan.descricao = numero, (nome.strip() or f"VLAN {numero}")[:120], descricao.strip()
    sessao.add(vlan)
    sessao.flush()
    return vlan


def excluir_vlan(sessao: Session, vlan_id: uuid.UUID) -> None:
    vlan = sessao.get(VlanRede, vlan_id)
    if vlan is None:
        raise _nao_encontrado("VLAN")
    em_uso = sessao.scalar(select(func.count()).select_from(PortaRede).where((PortaRede.vlan_nativa_id == vlan_id) | (PortaRede.vlan_voz_id == vlan_id))) or 0
    em_uso += sessao.scalar(select(func.count()).select_from(PortaVlanRede).where(PortaVlanRede.vlan_id == vlan_id)) or 0
    if em_uso:
        raise ErroRede(f"A VLAN está em {em_uso} porta(s): tire-a das portas antes de excluir.", 409, "em_uso")
    sessao.delete(vlan)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Conexões
# ---------------------------------------------------------------------------------------------

def conexao_da_porta(sessao: Session, porta_id: uuid.UUID) -> ConexaoRede | None:
    return sessao.scalar(select(ConexaoRede).where(or_(ConexaoRede.porta_a_id == porta_id, ConexaoRede.porta_b_id == porta_id)))


def conectar(sessao: Session, porta_id: uuid.UUID, outra_porta_id: uuid.UUID | None, bem_id: uuid.UUID | None, descricao: str,
             forcar: bool = False) -> ConexaoRede:
    """Liga a porta a outra porta, a um bem do Patrimônio ou só a uma descrição (ex.: "Telefone da recepção").

    Confere as duas pontas (origem e destino): porta já ligada no SGI é recusada (`409 porta_ocupada`); as duas passam ao status "ligada"; porta **descrita no switch**
    (ex.: "Sala 05B05 - Impressora") indica um dispositivo nela e só liga com `forcar` (`409 porta_com_dispositivo`), porque a descrição
    pode ser a do próprio uplink que se está cadastrando. Vale só na ligação porta ↔ porta.
    """
    porta = obter_porta(sessao, porta_id)
    if outra_porta_id is None and bem_id is None and not descricao.strip():
        raise ErroRede("Diga o que está ligado: outra porta, um bem do Patrimônio ou uma descrição.")
    if outra_porta_id is not None:
        if outra_porta_id == porta_id:
            raise ErroRede("Uma porta não se liga nela mesma.")
    outra = obter_porta(sessao, outra_porta_id) if outra_porta_id is not None else None
    if bem_id is not None and sessao.get(Bem, bem_id) is None:
        raise ErroRede("Bem do Patrimônio não encontrado.")
    pontas = [p for p in (porta, outra) if p is not None]
    for p in pontas:
        if conexao_da_porta(sessao, p.id) is not None:
            raise ErroRede(f"A porta {_nome_porta(p)} já está ligada: desligue antes de ligar de novo.", 409, "porta_ocupada")
    # Só na ligação porta ↔ porta: ao ligar um bem ou uma descrição, a descrição da porta costuma ser o próprio dispositivo
    if not forcar and outra is not None:
        descritas = [f"{_nome_porta(p)} está descrita como “{p.descricao.strip()}”" for p in pontas if p.descricao.strip()]
        if descritas:
            raise ErroRede("Pode haver um dispositivo nesta ligação: a porta " + "; a porta ".join(descritas)
                           + ". Confira e confirme para ligar mesmo assim.", 409, "porta_com_dispositivo")
    conexao = ConexaoRede(porta_a_id=porta_id, porta_b_id=outra_porta_id, bem_id=bem_id, descricao=descricao.strip()[:250])
    sessao.add(conexao)
    # Ligou um equipamento: as duas pontas passam a "ligada" na hora (porta com equipamento nunca tem outro status)
    for p in pontas:
        p.status = "up"
    sessao.flush()
    return conexao


def dispositivos_atras(sessao: Session, conexao_id: uuid.UUID) -> list[DispositivoAtrasRede]:
    return list(sessao.scalars(select(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id == conexao_id).order_by(DispositivoAtrasRede.ordem)))


def adicionar_atras(sessao: Session, porta_id: uuid.UUID, bem_id: uuid.UUID | None, descricao: str) -> DispositivoAtrasRede:
    """Põe um dispositivo **atrás** do último da porta (ex.: o PC ligado no telefone IP). Só vale quando a porta já tem um dispositivo (bem ou
    descrição): atrás de outra porta de rede não há "dispositivo atrás" (aí é a próxima ligação daquela porta)."""
    obter_porta(sessao, porta_id)
    conexao = conexao_da_porta(sessao, porta_id)
    if conexao is None or conexao.porta_b_id is not None:
        raise ErroRede("Ligue antes o primeiro dispositivo na porta (um bem ou uma descrição); atrás dele entra o próximo.", 409, "sem_dispositivo")
    if bem_id is None and not descricao.strip():
        raise ErroRede("Diga qual é o dispositivo: um bem do Patrimônio ou uma descrição.")
    if bem_id is not None and sessao.get(Bem, bem_id) is None:
        raise ErroRede("Bem do Patrimônio não encontrado.")
    atuais = dispositivos_atras(sessao, conexao.id)
    if bem_id is not None and (bem_id == conexao.bem_id or any(d.bem_id == bem_id for d in atuais)):
        raise ErroRede("Este bem já está nesta porta.", 409, "duplicado")
    novo = DispositivoAtrasRede(conexao_id=conexao.id, ordem=len(atuais) + 1, bem_id=bem_id, descricao=descricao.strip()[:250])
    sessao.add(novo)
    sessao.flush()
    return novo


def remover_atras(sessao: Session, porta_id: uuid.UUID, dispositivo_id: uuid.UUID) -> None:
    """Tira um dispositivo de trás; os que vinham depois sobem uma posição."""
    conexao = conexao_da_porta(sessao, porta_id)
    alvo = sessao.get(DispositivoAtrasRede, dispositivo_id)
    if conexao is None or alvo is None or alvo.conexao_id != conexao.id:
        raise _nao_encontrado("Dispositivo")
    sessao.delete(alvo)
    sessao.flush()
    for i, d in enumerate(dispositivos_atras(sessao, conexao.id), 1):
        d.ordem = i
    sessao.flush()


def _nome_porta(p: PortaRede) -> str:
    return f"{p.nome or p.numero_logico} do {p.equipamento.nome}"


def desconectar(sessao: Session, porta_id: uuid.UUID) -> None:
    from sqlalchemy import delete

    conexao = conexao_da_porta(sessao, porta_id)
    if conexao is None:
        raise ErroRede("Esta porta não está ligada a nada.", 404, "nao_encontrado")
    # Desligar a porta tira também os dispositivos que estavam atrás do primeiro
    sessao.execute(delete(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id == conexao.id))
    sessao.delete(conexao)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Pontos de rede
# ---------------------------------------------------------------------------------------------

def listar_pontos(sessao: Session, busca: str = "", localizacao_id: uuid.UUID | None = None) -> list[PontoRede]:
    consulta = select(PontoRede).order_by(PontoRede.codigo)
    if busca.strip():
        consulta = consulta.where(PontoRede.codigo.ilike(f"%{busca.strip()}%"))
    if localizacao_id:
        consulta = consulta.where(PontoRede.localizacao_id == localizacao_id)
    return list(sessao.scalars(consulta.limit(500)))


def salvar_ponto(sessao: Session, ponto_id: uuid.UUID | None, codigo: str, localizacao_id: uuid.UUID | None, porta_id: uuid.UUID | None,
                 observacao: str) -> PontoRede:
    codigo = codigo.strip().upper()
    if not 1 <= len(codigo) <= 40:
        raise ErroRede("O código do ponto precisa ter de 1 a 40 caracteres (como está na tomada).")
    repetido = sessao.scalar(select(PontoRede).where(func.upper(PontoRede.codigo) == codigo))
    if repetido is not None and repetido.id != ponto_id:
        raise ErroRede(f"Já existe o ponto {codigo}.", 409, "duplicado")
    if localizacao_id and sessao.get(Localizacao, localizacao_id) is None:
        raise ErroRede("Sala não encontrada.")
    if porta_id is not None:
        obter_porta(sessao, porta_id)
        outro = sessao.scalar(select(PontoRede).where(PontoRede.porta_id == porta_id))
        if outro is not None and outro.id != ponto_id:
            raise ErroRede(f"Esta porta já é do ponto {outro.codigo}.", 409, "porta_ocupada")
    ponto = sessao.get(PontoRede, ponto_id) if ponto_id else PontoRede()
    if ponto is None:
        raise _nao_encontrado("Ponto de rede")
    ponto.codigo, ponto.localizacao_id, ponto.porta_id, ponto.observacao = codigo, localizacao_id, porta_id, observacao.strip()
    sessao.add(ponto)
    sessao.flush()
    return ponto


def excluir_ponto(sessao: Session, ponto_id: uuid.UUID) -> None:
    ponto = sessao.get(PontoRede, ponto_id)
    if ponto is None:
        raise _nao_encontrado("Ponto de rede")
    sessao.delete(ponto)
    sessao.flush()


def caminho_do_ponto(sessao: Session, ponto: PontoRede) -> list[PortaRede]:
    """Ponto → porta do patch panel → (conexão) porta do switch. Segue no máximo 4 saltos, sem repetir porta."""
    caminho: list[PortaRede] = []
    atual = sessao.get(PortaRede, ponto.porta_id) if ponto.porta_id else None
    while atual is not None and atual not in caminho and len(caminho) < 4:
        caminho.append(atual)
        conexao = conexao_da_porta(sessao, atual.id)
        if conexao is None:
            break
        outra = conexao.porta_b_id if conexao.porta_a_id == atual.id else conexao.porta_a_id
        atual = sessao.get(PortaRede, outra) if outra else None
    return caminho


# ---------------------------------------------------------------------------------------------
# Topologia (árvore da rede, montada na hora a partir das conexões)
# ---------------------------------------------------------------------------------------------

@dataclass
class NoTopologia:
    """Um equipamento na árvore. `porta_acima`/`porta_no_pai`: o cabo que o liga ao equipamento de cima (a primeira, se houver mais de um)."""
    equipamento: EquipamentoRede
    portas_total: int = 0
    portas_up: int = 0
    portas_down: int = 0
    pontos: int = 0
    bens: int = 0
    porta_acima: str = ""
    porta_no_pai: str = ""
    cabos_com_pai: int = 0
    tambem_ligado: list[str] | None = None
    filhos: list["NoTopologia"] | None = None
    # Core Secundário no lugar de referência porque o Primário está fora do ar
    assumiu: bool = False
    # Ids das portas do cabo até o de cima (deste equipamento e do de cima), para o caminho da porta
    porta_acima_id: uuid.UUID | None = None
    porta_no_pai_id: uuid.UUID | None = None


def topologia(sessao: Session, raiz_id: uuid.UUID | None = None) -> tuple[list[NoTopologia], list[NoTopologia]]:
    """A rede como árvore, sem nada desenhado à mão: os equipamentos ativos são os nós e os cabos entre portas de equipamentos diferentes, as arestas.

    - Cada grupo de equipamentos ligados entre si (uma "rede ligada") é arrumado à parte; os grupos maiores vêm primeiro.
    - **Núcleo pela função (decisão do usuário):** os cores do grupo (`core_primario`, `core_secundario`) são as raízes, lado a lado, cada um
      com a sua árvore. A ordem é a função: o Primário primeiro; se o ping der o Primário **fora do ar**, o Secundário passa à frente
      (`assumiu`), sem mudar o cadastro. Quantidade de cabos e ordem alfabética não decidem nada entre os cores.
    - Grupo sem core marcado (cadastros de antes da regra): continua a regra automática antiga, uma raiz só, a que tem mais switches/roteadores
      vizinhos; no empate, menos patch panels, pontos e bens, depois o roteador e o nome.
    - `raiz_id` (o campo "Núcleo" da tela) só muda a visão: põe aquele equipamento como raiz única do grupo dele.
    - A árvore sai de uma busca em largura a partir das raízes: cada equipamento aparece uma vez, embaixo do primeiro a que se liga.
      Um cabo a mais para outro ramo (uplink redundante, o outro core) aparece em `tambem_ligado`, sem repetir o equipamento.
    - Filhos em ordem de camada (distribuição, acesso, sem função), com os patch panels por último; depois o nome.
    - Quem não tem cabo para nenhum outro equipamento vai para a segunda lista ("sem ligação"): é a pendência do cadastro.
    """
    equipamentos = {e.id: e for e in sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.ativo.is_(True)).options(selectinload(EquipamentoRede.rack)))}
    nos = {i: NoTopologia(e, tambem_ligado=[], filhos=[]) for i, e in equipamentos.items()}
    dono: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    for porta_id, equipamento_id, nome, numero, situacao in sessao.execute(
            select(PortaRede.id, PortaRede.equipamento_id, PortaRede.nome, PortaRede.numero_logico, PortaRede.status)):
        dono[porta_id] = (equipamento_id, nome or str(numero))
        if equipamento_id in nos:
            no = nos[equipamento_id]
            no.portas_total += 1
            no.portas_up += situacao == "up"
            no.portas_down += situacao == "down"
    for (porta_id,) in sessao.execute(select(PontoRede.porta_id).where(PontoRede.porta_id.is_not(None))):
        if porta_id in dono and dono[porta_id][0] in nos:
            nos[dono[porta_id][0]].pontos += 1

    # Bens ligados atrás do primeiro dispositivo (telefone IP → PC) também contam para o equipamento
    atras_por_conexao = dict(sessao.execute(select(DispositivoAtrasRede.conexao_id, func.count()).where(DispositivoAtrasRede.bem_id.is_not(None))
                                            .group_by(DispositivoAtrasRede.conexao_id)).all())
    # vizinhos[a][b] = cabos entre a e b, como (porta em a, porta em b)
    vizinhos: dict[uuid.UUID, dict[uuid.UUID, list[tuple[str, str]]]] = {i: {} for i in nos}
    for c in sessao.scalars(select(ConexaoRede)):
        a = dono.get(c.porta_a_id)
        if a is None or a[0] not in nos:
            continue
        if c.bem_id:
            nos[a[0]].bens += 1
        nos[a[0]].bens += atras_por_conexao.get(c.id, 0)
        b = dono.get(c.porta_b_id) if c.porta_b_id else None
        if b is None or b[0] not in nos or b[0] == a[0]:
            continue
        vizinhos[a[0]].setdefault(b[0], []).append((a[1], b[1], c.porta_a_id, c.porta_b_id))
        vizinhos[b[0]].setdefault(a[0], []).append((b[1], a[1], c.porta_b_id, c.porta_a_id))

    camada = {"core_primario": 0, "core_secundario": 0, "distribuicao": 1, "acesso": 2}

    def ordem(i: uuid.UUID) -> tuple:
        e = equipamentos[i]
        return (e.tipo == "patch_panel", camada.get(e.funcao or "", 3), e.nome.lower())

    def ordem_core(i: uuid.UUID) -> tuple:
        # Quem está no ar vem antes; entre os no ar, o Primário antes do Secundário
        e = equipamentos[i]
        return (e.ping_situacao == "fora", e.funcao != "core_primario", e.nome.lower())

    def peso_de_raiz(i: uuid.UUID) -> tuple:
        # Mais switches/roteadores vizinhos; no empate, menos coisa de ponta (patch panel, ponto, bem), que o núcleo raramente tem
        ativos = sum(1 for v in vizinhos[i] if equipamentos[v].tipo != "patch_panel")
        ponta = len(vizinhos[i]) - ativos + nos[i].pontos + nos[i].bens
        return (-ativos, ponta, equipamentos[i].tipo != "roteador", equipamentos[i].nome.lower())

    # Grupos ligados (componentes conexos)
    grupos: list[list[uuid.UUID]] = []
    vistos: set[uuid.UUID] = set()
    for inicio in sorted(nos, key=ordem):
        if inicio in vistos or not vizinhos[inicio]:
            continue
        grupo, pilha = [], [inicio]
        vistos.add(inicio)
        while pilha:
            atual = pilha.pop()
            grupo.append(atual)
            for v in vizinhos[atual]:
                if v not in vistos:
                    vistos.add(v)
                    pilha.append(v)
        grupos.append(grupo)
    grupos.sort(key=lambda g: (-len(g), min(peso_de_raiz(i) for i in g)))

    raizes: list[NoTopologia] = []
    for grupo in grupos:
        cores = sorted((i for i in grupo if equipamentos[i].funcao in FUNCOES_CORE), key=ordem_core)
        if raiz_id in grupo:
            topo = [raiz_id]
        elif cores:
            topo = cores
            primario_fora = any(equipamentos[i].funcao == "core_primario" and equipamentos[i].ping_situacao == "fora" for i in cores)
            if primario_fora and equipamentos[cores[0]].funcao == "core_secundario":
                nos[cores[0]].assumiu = True
        else:
            topo = [min(grupo, key=peso_de_raiz)]
        pai: dict[uuid.UUID, uuid.UUID | None] = dict.fromkeys(topo)
        fila = list(topo)
        while fila:
            atual = fila.pop(0)
            for v in sorted(vizinhos[atual], key=ordem):
                if v in pai:
                    continue
                pai[v] = atual
                cabos = vizinhos[v][atual]
                filho = nos[v]
                filho.porta_acima, filho.porta_no_pai, filho.cabos_com_pai = cabos[0][0], cabos[0][1], len(cabos)
                filho.porta_acima_id, filho.porta_no_pai_id = cabos[0][2], cabos[0][3]
                nos[atual].filhos.append(filho)
                fila.append(v)
        for i in grupo:
            nos[i].tambem_ligado = sorted(equipamentos[v].nome for v in vizinhos[i] if v != pai[i] and pai.get(v) != i)
        raizes.extend(nos[i] for i in topo)
    sem_ligacao = [nos[i] for i in sorted(nos, key=ordem) if not vizinhos[i]]
    return raizes, sem_ligacao


# ---------------------------------------------------------------------------------------------
# Caminho da porta até o core
# ---------------------------------------------------------------------------------------------

@dataclass
class EtapaCaminho:
    """Um degrau do caminho: um equipamento (ou o ponto de rede, no fim). `cabo` é o cabo que o liga ao degrau de cima ("porta de cima ↔ porta deste")."""
    tipo: str
    nome: str
    cabo: str = ""
    equipamento: EquipamentoRede | None = None
    # Porta deste equipamento no cabo que sobe (entrada) e no que desce para o próximo degrau (saída)
    porta_entrada_id: uuid.UUID | None = None
    porta_saida_id: uuid.UUID | None = None


@dataclass
class CaminhoPorta:
    etapas: list[EtapaCaminho]
    # O que está ligado na porta, na ordem da cascata (ex.: telefone IP → computador): (texto, bem_id)
    dispositivos: list[tuple[str, uuid.UUID | None]]
    cabo_dispositivos: str = ""
    aviso: str = ""


def _nome_curto(p: PortaRede) -> str:
    return p.nome or str(p.numero_logico)


def _texto_dispositivo(sessao: Session, bem_id: uuid.UUID | None, descricao: str) -> tuple[str, uuid.UUID | None]:
    if bem_id:
        b = sessao.get(Bem, bem_id)
        return (f"{(b.descricao if b else '') or 'Bem'} (chapa {(b.chapa if b else '') or '—'})", bem_id)
    return (descricao or "Dispositivo", None)


def caminho_da_porta(sessao: Session, porta_id: uuid.UUID) -> CaminhoPorta:
    """Do topo (o core do grupo, pela mesma árvore da topologia) até a porta e o que está nela (patch panel, ponto, telefone, computador...).

    - A subida é a da topologia: cada equipamento aparece embaixo do primeiro a que se liga, então o caminho é o mesmo que se vê lá.
    - Porta de patch panel ligada a um switch: o caminho passa por aquele switch e por esta porta (não pela primeira ligação do patch panel).
    - Porta que é a subida do próprio equipamento (o cabo vai para quem está acima): o caminho para nele.
    """
    porta = obter_porta(sessao, porta_id)
    equipamento = porta.equipamento
    raizes, _ = topologia(sessao)
    # Pai de cada equipamento na árvore e o cabo até ele ("porta no pai ↔ porta no filho")
    pai: dict[uuid.UUID, tuple[uuid.UUID | None, str, uuid.UUID | None, uuid.UUID | None]] = {}
    pilha = [(r, None) for r in raizes]
    while pilha:
        no, de_cima = pilha.pop()
        pai[no.equipamento.id] = (de_cima, f"{no.porta_no_pai} ↔ {no.porta_acima}" if de_cima else "", no.porta_acima_id, no.porta_no_pai_id)
        pilha.extend((f, no.equipamento.id) for f in no.filhos or [])
    equipamentos = {e.id: e for e in sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.id.in_(list(pai) + [equipamento.id])))}

    def subir(eid: uuid.UUID) -> list[EtapaCaminho]:
        cadeia: list[EtapaCaminho] = []
        atual: uuid.UUID | None = eid
        saida_de_baixo: uuid.UUID | None = None
        while atual is not None and len(cadeia) < 30:
            de_cima, cabo, entrada, no_pai = pai.get(atual, (None, "", None, None))
            e = equipamentos[atual]
            cadeia.append(EtapaCaminho("equipamento", e.nome, cabo, e, entrada if de_cima else None, saida_de_baixo))
            saida_de_baixo = no_pai
            atual = de_cima
        return list(reversed(cadeia))

    conexao = conexao_da_porta(sessao, porta.id)
    outra = None
    if conexao is not None and conexao.porta_b_id is not None:
        outra = obter_porta(sessao, conexao.porta_b_id if conexao.porta_a_id == porta.id else conexao.porta_a_id)
    aviso = ""
    if equipamento.tipo == "patch_panel" and outra is not None:
        # Patch panel: sobe pelo switch em que esta porta chega
        etapas = subir(outra.equipamento_id)
        etapas[-1].porta_saida_id = outra.id
        etapas.append(EtapaCaminho("equipamento", equipamento.nome, f"{_nome_curto(outra)} ↔ {_nome_curto(porta)}", equipamento, porta.id))
    else:
        etapas = subir(equipamento.id)
        if outra is not None:
            # Porta de subida do próprio equipamento: o caminho termina nele (a tela destaca o quadradinho desta porta, sem aviso)
            if not any(et.equipamento is not None and et.equipamento.id == outra.equipamento_id for et in etapas):
                etapas[-1].porta_saida_id = porta.id
                etapas.append(EtapaCaminho("equipamento", outra.equipamento.nome, f"{_nome_curto(porta)} ↔ {_nome_curto(outra)}", outra.equipamento, outra.id))
                if outra.equipamento.tipo == "patch_panel":
                    ponto = sessao.scalar(select(PontoRede).where(PontoRede.porta_id == outra.id))
                    if ponto:
                        etapas[-1].porta_saida_id = outra.id
                        etapas.append(EtapaCaminho("ponto", ponto.codigo, _nome_curto(outra)))
    if equipamento.tipo == "patch_panel" or outra is None:
        ponto = sessao.scalar(select(PontoRede).where(PontoRede.porta_id == porta.id))
        if ponto:
            etapas[-1].porta_saida_id = porta.id
            etapas.append(EtapaCaminho("ponto", ponto.codigo, _nome_curto(porta)))
    dispositivos: list[tuple[str, uuid.UUID | None]] = []
    if conexao is not None and conexao.porta_b_id is None:
        # Os dispositivos saem desta porta: ela é a saída do último equipamento
        ultimo = next(et for et in reversed(etapas) if et.equipamento is not None)
        ultimo.porta_saida_id = porta.id
        dispositivos.append(_texto_dispositivo(sessao, conexao.bem_id, conexao.descricao))
        dispositivos += [_texto_dispositivo(sessao, d.bem_id, d.descricao) for d in dispositivos_atras(sessao, conexao.id)]
    # Fora de qualquer árvore = sem cabo para outro equipamento
    if etapas[0].equipamento is not None and etapas[0].equipamento.id not in pai:
        aviso = aviso or f"O {equipamento.nome} não tem cabo para outro equipamento: o caminho não chega ao core."
    return CaminhoPorta(etapas, dispositivos, _nome_curto(porta) if dispositivos else "", aviso)


# ---------------------------------------------------------------------------------------------
# Chamados da porta
# ---------------------------------------------------------------------------------------------

def chamados_da_porta(sessao: Session, porta: PortaRede, condicao_visivel) -> list[Chamado]:
    """Chamados da porta e do ponto que chega nela, só os que a pessoa enxerga nos Chamados (`condicao_visivel`), mais recentes primeiro."""
    ponto = sessao.scalar(select(PontoRede).where(PontoRede.porta_id == porta.id))
    alvo = Chamado.rede_porta_id == porta.id
    if ponto is not None:
        alvo = or_(alvo, Chamado.rede_ponto_id == ponto.id)
    return list(sessao.scalars(select(Chamado).where(alvo, Chamado.excluido_em.is_(None), condicao_visivel).order_by(Chamado.aberto_em.desc()).limit(20)))


# ---------------------------------------------------------------------------------------------
# Bens do Patrimônio ligados nas portas
# ---------------------------------------------------------------------------------------------

def buscar_bens(sessao: Session, busca: str) -> list[Bem]:
    """Até 20 bens ativos pela chapa ou pela descrição (pelo menos 2 caracteres)."""
    termo = busca.strip()
    if len(termo) < 2:
        return []
    padrao = f"%{termo}%"
    return list(sessao.scalars(select(Bem).where(Bem.situacao != "baixado", or_(Bem.chapa.ilike(padrao), Bem.descricao.ilike(padrao)))
                               .order_by(Bem.chapa).limit(20)))


def portas_do_bem(sessao: Session, bem_id: uuid.UUID) -> list[tuple[PortaRede, ConexaoRede | None, DispositivoAtrasRede | None]]:
    """Portas em que o bem está ligado (normalmente uma): direto (conexão e dispositivo `None`) ou atrás do primeiro dispositivo daquela
    ligação (a conexão e o registro dele atrás, para tirar só ele)."""
    if sessao.get(Bem, bem_id) is None:
        raise _nao_encontrado("Bem")
    diretas = [(p, None, None) for p in sessao.scalars(select(PortaRede).join(ConexaoRede, ConexaoRede.porta_a_id == PortaRede.id).where(ConexaoRede.bem_id == bem_id))]
    atras = []
    for d in sessao.scalars(select(DispositivoAtrasRede).where(DispositivoAtrasRede.bem_id == bem_id)):
        c = sessao.get(ConexaoRede, d.conexao_id)
        atras.append((sessao.get(PortaRede, c.porta_a_id), c, d))
    return diretas + atras


# ---------------------------------------------------------------------------------------------
# Racks
# ---------------------------------------------------------------------------------------------

def listar_racks(sessao: Session) -> list[RackRede]:
    return list(sessao.scalars(select(RackRede).order_by(RackRede.nome)))


def salvar_rack(sessao: Session, rack_id: uuid.UUID | None, nome: str, cor: str, localizacao_id: uuid.UUID | None, altura_u: int, observacao: str) -> RackRede:
    nome = " ".join(nome.split())
    if not 1 <= len(nome) <= 80:
        raise ErroRede("O nome do rack precisa ter de 1 a 80 caracteres.")
    if cor not in CORES_RACK:
        raise ErroRede("Cor inválida.")
    if not 1 <= altura_u <= 60:
        raise ErroRede("A altura do rack vai de 1 a 60U.")
    if localizacao_id and sessao.get(Localizacao, localizacao_id) is None:
        raise ErroRede("Sala não encontrada.")
    repetido = sessao.scalar(select(RackRede).where(func.lower(RackRede.nome) == nome.lower()))
    if repetido is not None and repetido.id != rack_id:
        raise ErroRede("Já existe um rack com este nome.", 409, "duplicado")
    rack = sessao.get(RackRede, rack_id) if rack_id else RackRede()
    if rack is None:
        raise _nao_encontrado("Rack")
    if rack_id:
        # Diminuir a altura não pode deixar equipamento para fora do rack
        for e in sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.rack_id == rack_id, EquipamentoRede.posicao_u.is_not(None))):
            topo = e.posicao_u + (e.modelo_face.altura_u if e.modelo_face else 1) - 1
            if topo > altura_u:
                raise ErroRede(f"{e.nome} ocupa até o U{topo}: o rack não pode ter menos de {topo}U.", 409, "em_uso")
    rack.nome, rack.cor, rack.localizacao_id, rack.altura_u, rack.observacao = nome, cor, localizacao_id, altura_u, observacao.strip()
    sessao.add(rack)
    sessao.flush()
    return rack


def excluir_rack(sessao: Session, rack_id: uuid.UUID) -> None:
    rack = sessao.get(RackRede, rack_id)
    if rack is None:
        raise _nao_encontrado("Rack")
    if sessao.scalar(select(EquipamentoRede.id).where(EquipamentoRede.rack_id == rack_id).limit(1)) is not None:
        raise ErroRede("Há equipamentos neste rack: tire-os (ou troque o rack deles) antes de excluir.", 409, "em_uso")
    sessao.delete(rack)
    sessao.flush()


def buscar_salas(sessao: Session, busca: str, todas: bool = False) -> list[Localizacao]:
    """Até 20 salas ativas do Patrimônio pelo código ou pelo nome; com `todas`, a lista inteira por andar (o campo de sala da tela filtra)."""
    if todas:
        return list(sessao.scalars(select(Localizacao).where(Localizacao.tipo == "sala", Localizacao.ativo.is_(True))
                                   .order_by(Localizacao.andar, Localizacao.codigo)))
    termo = busca.strip()
    if len(termo) < 2:
        return []
    padrao = f"%{termo}%"
    return list(sessao.scalars(select(Localizacao).where(Localizacao.tipo == "sala", Localizacao.ativo.is_(True),
                                                          or_(Localizacao.codigo.ilike(padrao), Localizacao.nome.ilike(padrao))).order_by(Localizacao.codigo).limit(20)))
