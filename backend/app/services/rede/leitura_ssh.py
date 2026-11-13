"""
===============================================================================
ARQUIVO: leitura_ssh.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ler um equipamento de rede por SSH, só com comandos de consulta, e devolver
o que ele tem: nome, modelo, série, versão, portas (link, velocidade,
duplex, descrição, modo e VLANs), VLANs e vizinhos LLDP.

RESUMO TÉCNICO:
Usa o Netmiko (login, prompt e paginação de cada fabricante). O tipo do
equipamento é detectado sozinho (SSHDetect); se não der, tenta Huawei,
Dell OS6, H3C Comware e Cisco IOS, nessa ordem. Para cada informação há uma
lista de tentativas (comando + leitor tolerante): a primeira que trouxer
algo vale; as que falharem viram aviso. Como reserva comum a todos, lê a
configuração em execução (display current-configuration / show
running-config), que tem o modo e as VLANs de cada porta.
Só comandos que começam com "display" ou "show" são enviados (conferido em
`_so_consulta`); nunca o modo de configuração. A parte de leitura dos
textos (`ler_textos`) não abre conexão e é a que os testes exercitam.

FINALIDADE DE NEGÓCIO:
Decisão do usuário (13/11/2026): no cadastro de switch, AP ou roteador, o SGI
entra só leitura no equipamento e faz a carga, em vez de tudo ser digitado.
Se nenhuma tentativa funcionar, a carga simplesmente não traz nada.

CONTEXTO NO SISTEMA:
Chamado por app/services/rede/servico_leitura.py (resumo e aplicação). Não
grava nada no banco.

===============================================================================
"""
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

# Tipos do Netmiko tentados quando a detecção automática não acerta (os fabricantes da SPI)
TIPOS_TENTADOS = ("huawei_vrpv8", "huawei", "dell_os6", "hp_comware", "cisco_ios")
# Família de comandos de cada tipo: VRP (Huawei, H3C: "display") ou IOS (Cisco, Dell: "show")
FAMILIA = {"huawei_vrpv8": "vrp", "huawei": "vrp", "hp_comware": "vrp", "dell_os6": "ios", "dell_force10": "ios", "cisco_ios": "ios",
           "cisco_xe": "ios", "cisco_nxos": "ios"}
# Interfaces lógicas não viram porta da face (VLAN, agregação, gerência, loopback...)
LOGICAS = re.compile(r"^(vlan|vlanif|eth-trunk|port-channel|po\d|bridge-aggregation|route-aggregation|loopback|null|meth|mgmt|tunnel|nve|stack|"
                     r"inloopback|register-tunnel|management|cpu|fc\d|ethernet\d+/\d+/\d+\.\d+)", re.I)
# Tempo máximo da leitura inteira (segundos): o nginx do SGI encerra as chamadas da API em 60 s
PRAZO_LEITURA = 45
# Uma faixa de VLANs maior que isto (ex.: "1-4094") é tratada como "todas", sem listar uma a uma
FAIXA_TODAS = 1000


class ErroLeitura(Exception):
    """Não foi possível entrar no equipamento (endereço, usuário/senha ou SSH)."""


@dataclass
class PortaLida:
    interface: str
    link: bool | None = None
    velocidade: int | None = None
    duplex: str | None = None
    descricao: str = ""
    # Modo no vocabulário do SGI (access, trunk, hybrid, dot1q_tunnel, dinamico_auto, dinamico_desejavel, roteada) ou vazio
    modo: str | None = None
    pvid: int | None = None
    vlans_tag: list[int] = field(default_factory=list)
    vlans_sem_tag: list[int] = field(default_factory=list)
    # A porta deixa passar todas as VLANs (ex.: "1-4094"): a lista fica vazia
    todas_vlans: bool = False
    desligada_no_switch: bool = False


@dataclass
class Leitura:
    tipo: str = ""
    nome: str = ""
    modelo: str = ""
    serie: str = ""
    versao: str = ""
    portas: list[PortaLida] = field(default_factory=list)
    vlans: list[tuple[int, str]] = field(default_factory=list)
    vizinhos: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------------------------
# Utilitários de texto
# ---------------------------------------------------------------------------------------------

_LONGOS = (("tengigabitethernet", "te"), ("twentyfivegige", "twe"), ("fortygigabitethernet", "fo"), ("hundredgige", "hu"),
           ("gigabitethernet", "gi"), ("fastethernet", "fa"), ("ten-gigabitethernet", "xge"))


def chave_interface(nome: str) -> str:
    """Nome comparável da interface: sem espaços, minúsculo e com os nomes longos encurtados ("GigabitEthernet1/0/1" = "Gi1/0/1")."""
    n = nome.strip().lower().replace(" ", "")
    for longo, curto in _LONGOS:
        if n.startswith(longo):
            return curto + n[len(longo):]
    return n


def eh_logica(nome: str) -> bool:
    return bool(LOGICAS.match(nome.strip()))


def lista_vlans(texto: str) -> tuple[list[int], bool]:
    """VLANs de uma lista nos dois estilos ("10 20 to 30" do VRP; "10,20-30" do IOS). Devolve (números, todas?)."""
    t = texto.lower().replace(",", " ").replace(" to ", "-").replace("--", " ")
    numeros: set[int] = set()
    todas = False
    for parte in t.split():
        if parte in ("all", "todas"):
            return [], True
        m = re.fullmatch(r"(\d+)-(\d+)", parte)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b - a + 1 > FAIXA_TODAS:
                todas = True
                continue
            numeros.update(range(a, b + 1))
        elif parte.isdigit():
            numeros.add(int(parte))
    return sorted(n for n in numeros if 1 <= n <= 4094), todas


def _modo_sgi(texto: str) -> str | None:
    t = texto.strip().lower()
    return {"access": "access", "trunk": "trunk", "hybrid": "hybrid", "general": "hybrid", "desirable": "dinamico_desejavel", "dynamic desirable": "dinamico_desejavel",
            "auto": "dinamico_auto", "dynamic auto": "dinamico_auto", "dot1q-tunnel": "dot1q_tunnel", "qinq": "dot1q_tunnel"}.get(t)


def _velocidade(texto: str) -> int | None:
    """"1000", "10G", "a-1000", "2.5G", "25000" → Mb/s."""
    t = texto.strip().lower().replace("a-", "").replace("mb/s", "").replace("mbps", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([gm]?)", t)
    if not m:
        return None
    valor = float(m.group(1))
    return int(valor * 1000) if m.group(2) == "g" else int(valor)


def _duplex(texto: str) -> str | None:
    t = texto.strip().lower().replace("a-", "")
    return "full" if t.startswith("full") else "half" if t.startswith("half") else None


# ---------------------------------------------------------------------------------------------
# Leitores de cada saída (tolerantes: o que não reconhecem, ignoram)
# ---------------------------------------------------------------------------------------------

def versao_vrp(t: str, r: Leitura) -> bool:
    m = re.search(r"^\s*(?:\d\.)?Board\s+Type\s*:\s*(\S+)", t, re.M) or re.search(r"^(\S+)\(Master\)", t, re.M) \
        or re.search(r"^(?:HUAWEI|H3C)\s+(\S+(?:\s\S+)?)\s+uptime", t, re.M | re.I)
    v = re.search(r"Version\s+([\d.]+(?:\s*\([^)]*\))?)", t)
    if m:
        r.modelo = m.group(1).strip()
    if v:
        r.versao = v.group(1).strip()
    return bool(m or v)


def versao_ios(t: str, r: Leitura) -> bool:
    # Dell: "System Model ID....: N2024P"; Cisco: "Model number: WS-C…" ou a linha "cisco WS-C2960X-48FPD-L (…) processor"
    m = re.search(r"(?:System\s+Model\s+ID|Model\s+[Nn]umber|Machine\s+Type)[ .]*:?\s*(\S+)", t) or re.search(r"^cisco\s+(\S+)\s+\(.*processor", t, re.M | re.I)
    s = re.search(r"(?:Serial\s+[Nn]umber|System\s+[Ss]erial\s+[Nn]umber|Processor\s+board\s+ID)[ .]*:?\s*(\S+)", t)
    v = re.search(r"(?:Software\s+Version|Version)[ .]*:?\s*([\w.()\-]+)", t)
    if m:
        r.modelo = m.group(1).strip().rstrip(",")
    if s and not r.serie:
        r.serie = s.group(1).strip()
    if v:
        r.versao = v.group(1).strip().rstrip(",")
    return bool(m or v)


def serie_vrp(t: str, r: Leitura) -> bool:
    m = re.search(r"ESN[^:\n]*:\s*(\S+)", t) or re.search(r"DEVICE_SERIAL_NUMBER\s*:\s*(\S+)", t) or re.search(r"BarCode=(\S+)", t)
    if m:
        r.serie = m.group(1).strip()
    return bool(m)


def interfaces_vrp(t: str, portas: dict) -> bool:
    """`display interface | include (current state|Speed|Duplex|Description)`: um bloco por interface."""
    achou = False
    atual: PortaLida | None = None
    for linha in t.splitlines():
        m = re.match(r"^(\S+)\s+current state\s*:\s*(.+?)(?:\s*\(|$)", linha)
        if m and not linha.startswith("Line protocol"):
            nome = m.group(1)
            atual = None if eh_logica(nome) else portas.setdefault(chave_interface(nome), PortaLida(nome))
            if atual is not None:
                estado = m.group(2).strip().upper()
                atual.link = estado == "UP"
                atual.desligada_no_switch = "ADMINISTRATIVELY" in estado
                achou = True
            continue
        if atual is None:
            continue
        if linha.startswith("Description:"):
            atual.descricao = linha.split(":", 1)[1].strip()
        v = re.search(r"Speed\s*:\s*(\w+)", linha)
        if v:
            atual.velocidade = _velocidade(v.group(1))
        d = re.search(r"Duplex\s*:\s*(\w+)", linha)
        if d:
            atual.duplex = _duplex(d.group(1))
    return achou


def port_vlan_vrp(t: str, portas: dict) -> bool:
    """`display port vlan` (Huawei): Port | Link Type | PVID | Trunk VLAN List (continua nas linhas de baixo) | Port Description."""
    linhas = t.splitlines()
    cab = next((i for i, l in enumerate(linhas) if re.match(r"\s*Port\s+Link Type\s+PVID", l)), None)
    if cab is None:
        return False
    pos_desc = linhas[cab].find("Port Description")
    atual: PortaLida | None = None
    vlans_txt = ""

    def fechar() -> None:
        if atual is not None:
            numeros, todas = lista_vlans(vlans_txt)
            if atual.modo in ("trunk", "hybrid", "dinamico_auto", "dinamico_desejavel"):
                atual.vlans_tag = [n for n in numeros if n != atual.pvid]
                atual.todas_vlans = todas
    achou = False
    for linha in linhas[cab + 1:]:
        if not linha.strip() or set(linha.strip()) <= {"-"} or linha.startswith("<"):
            continue
        corpo = linha[:pos_desc] if pos_desc > 0 else linha
        if not linha.startswith(" "):
            fechar()
            partes = corpo.split()
            if len(partes) < 3:
                atual = None
                continue
            nome, tipo, pvid = partes[0], partes[1], partes[2]
            atual = None if eh_logica(nome) else portas.setdefault(chave_interface(nome), PortaLida(nome))
            if atual is None:
                continue
            atual.modo = _modo_sgi(tipo) if tipo != "--" else None
            atual.pvid = int(pvid) if pvid.isdigit() and int(pvid) > 0 else None
            vlans_txt = " ".join(partes[3:])
            if pos_desc > 0 and not atual.descricao:
                atual.descricao = linha[pos_desc:].strip()
            achou = True
        elif atual is not None:
            vlans_txt += " " + corpo.strip()
    fechar()
    return achou


def config_vrp(t: str, portas: dict) -> bool:
    """`display current-configuration` (Huawei/H3C): blocos "interface X" com port link-type, vlans, descrição, shutdown."""
    achou = False
    atual: PortaLida | None = None
    for linha in t.splitlines():
        s = linha.strip()
        m = re.match(r"^interface\s+(\S+)", s)
        if m:
            nome = m.group(1)
            atual = None if eh_logica(nome) else portas.setdefault(chave_interface(nome), PortaLida(nome))
            achou = achou or atual is not None
            continue
        if atual is None or not s or s == "#":
            if s == "#":
                atual = None
            continue
        if s.startswith("description "):
            atual.descricao = atual.descricao or s[12:].strip()
        elif s.startswith("port link-type "):
            atual.modo = _modo_sgi(s.split()[-1])
        elif s == "undo portswitch":
            atual.modo = "roteada"
        elif s == "shutdown":
            atual.desligada_no_switch = True
        elif m := re.match(r"port (?:default|access) vlan (\d+)", s):
            atual.pvid = int(m.group(1))
            atual.modo = atual.modo or "access"
        elif m := re.match(r"port (?:trunk|hybrid) pvid vlan (\d+)", s):
            atual.pvid = int(m.group(1))
        elif m := re.match(r"port trunk (?:allow-pass|permit) vlan (.+)", s):
            numeros, todas = lista_vlans(m.group(1))
            atual.vlans_tag = sorted(set(atual.vlans_tag) | set(numeros))
            atual.todas_vlans = atual.todas_vlans or todas
        elif m := re.match(r"port hybrid (tagged|untagged) vlan (.+)", s) or re.match(r"port hybrid vlan (.+?) (tagged|untagged)$", s):
            grupos = m.groups()
            marca, lista = (grupos[0], grupos[1]) if grupos[0] in ("tagged", "untagged") else (grupos[1], grupos[0])
            numeros, _ = lista_vlans(lista)
            alvo = "vlans_tag" if marca == "tagged" else "vlans_sem_tag"
            setattr(atual, alvo, sorted(set(getattr(atual, alvo)) | set(numeros)))
        elif m := re.match(r"speed (\d+)", s):
            atual.velocidade = int(m.group(1))
        elif m := re.match(r"duplex (full|half)", s):
            atual.duplex = m.group(1)
    for p in portas.values():
        if p.pvid in p.vlans_sem_tag:
            p.vlans_sem_tag.remove(p.pvid)
    return achou


def config_ios(t: str, portas: dict) -> bool:
    """`show running-config` (Cisco IOS, Dell OS6): blocos "interface X" com switchport, descrição, shutdown."""
    achou = False
    atual: PortaLida | None = None
    for linha in t.splitlines():
        s = linha.strip()
        m = re.match(r"^interface\s+(.+)$", s)
        if m:
            nome = m.group(1).strip()
            atual = None if eh_logica(nome) else portas.setdefault(chave_interface(nome), PortaLida(nome))
            achou = achou or atual is not None
            continue
        if atual is None:
            continue
        if s in ("!", "exit"):
            atual = None
            continue
        if s.startswith("description "):
            atual.descricao = atual.descricao or s[12:].strip().strip('"')
        elif m := re.match(r"switchport mode (.+)", s):
            atual.modo = _modo_sgi(m.group(1))
        elif s == "no switchport":
            atual.modo = "roteada"
        elif s == "shutdown":
            atual.desligada_no_switch = True
        elif m := re.match(r"switchport access vlan (\d+)", s):
            atual.pvid = int(m.group(1))
            atual.modo = atual.modo or "access"
        elif m := re.match(r"switchport (?:trunk native|general pvid) vlan (\d+)", s) or re.match(r"switchport general pvid (\d+)", s):
            atual.pvid = int(m.group(1))
        elif m := re.match(r"switchport trunk allowed vlan (?:add )?(.+)", s):
            numeros, todas = lista_vlans(m.group(1))
            atual.vlans_tag = sorted(set(atual.vlans_tag) | set(numeros))
            atual.todas_vlans = atual.todas_vlans or todas
        elif m := re.match(r"switchport general allowed vlan add (\S+)\s*(tagged|untagged)?", s):
            numeros, _ = lista_vlans(m.group(1))
            alvo = "vlans_tag" if m.group(2) == "tagged" else "vlans_sem_tag"
            setattr(atual, alvo, sorted(set(getattr(atual, alvo)) | set(numeros)))
        elif m := re.match(r"speed (\d+)", s):
            atual.velocidade = int(m.group(1))
        elif m := re.match(r"duplex (full|half)", s):
            atual.duplex = m.group(1)
    for p in portas.values():
        if p.modo in ("trunk", "hybrid") and p.pvid in p.vlans_tag:
            p.vlans_tag.remove(p.pvid)
    return achou


def status_ios(t: str, portas: dict) -> bool:
    """`show interfaces status` (Cisco/Dell): lido pelas colunas do cabeçalho (a descrição pode ter números, ex.: "Sala 504").

    Cisco: Port | Name | Status (connected/notconnect/disabled) | Vlan | Duplex | Speed; Dell: Port | Description | Duplex | Speed | Neg | Link (Up/Down).
    """
    linhas = t.splitlines()
    cab = next((l for l in linhas if re.match(r"\s*Port\s+", l) and "Duplex" in l and "Speed" in l), None)
    if cab is None:
        return False

    def coluna(linha: str, inicio: int) -> str:
        # O valor que começa na coluna do cabeçalho (ou logo antes, quando o valor é mais largo que o título)
        if inicio < 0 or inicio >= len(linha):
            return ""
        i = inicio
        while i > 0 and linha[i - 1] != " ":
            i -= 1
        return linha[i:].split()[0] if linha[i:].split() else ""
    pos_duplex, pos_speed = cab.find("Duplex"), cab.find("Speed")
    pos_status = cab.find(" Status") + 1 if " Status" in cab else cab.find("Link")
    achou = False
    for l in linhas[linhas.index(cab) + 1:]:
        partes = l.split()
        if not partes or set(l.strip()) <= {"-", " "} or eh_logica(partes[0]) or not re.search(r"\d+/\d+", partes[0]):
            continue
        p = portas.setdefault(chave_interface(partes[0]), PortaLida(partes[0]))
        estado = coluna(l, pos_status).lower()
        if estado in ("connected", "up"):
            p.link = True
        elif estado in ("notconnect", "down", "disabled", "err-disabled", "inactive"):
            p.link = False
            p.desligada_no_switch = estado == "disabled"
        p.duplex = p.duplex or _duplex(coluna(l, pos_duplex))
        p.velocidade = p.velocidade or _velocidade(coluna(l, pos_speed))
        achou = True
    return achou


def lldp_vrp(t: str, r: Leitura) -> bool:
    """`display lldp neighbor brief` (Huawei) e `display lldp neighbor-information list` (H3C)."""
    achou = False
    for l in t.splitlines():
        partes = l.split()
        if len(partes) < 3 or not re.search(r"\d+/\d+", partes[0] + (partes[1] if len(partes) > 1 else "")):
            continue
        if re.match(r"^\S+\s+\d+\s+\S+\s+\S+", l) and re.search(r"\d", partes[0]):
            # Huawei: Local Interface | Exptime | Neighbor Interface | Neighbor Device
            r.vizinhos.append({"interface_local": partes[0], "vizinho_interface": partes[2], "vizinho_nome": " ".join(partes[3:])})
            achou = True
        elif re.search(r"\d+/\d+", partes[1]):
            # H3C: System Name | Local Interface | Chassis ID | Port ID
            r.vizinhos.append({"interface_local": partes[1], "vizinho_interface": partes[-1], "vizinho_nome": partes[0]})
            achou = True
    return achou


def lldp_ios(t: str, r: Leitura) -> bool:
    """`show lldp neighbors` (Cisco: Device ID | Local Intf | Hold | Capability | Port ID) e `show lldp remote-device all` (Dell)."""
    achou = False
    for l in t.splitlines():
        partes = l.split()
        if len(partes) < 3:
            continue
        if re.search(r"\d+/\d+", partes[1]) and not re.search(r"\d+/\d+", partes[0]):
            r.vizinhos.append({"interface_local": partes[1], "vizinho_interface": partes[-1], "vizinho_nome": partes[0]})
            achou = True
        elif re.search(r"\d+/\d+", partes[0]) and len(partes) >= 4:
            # Dell: Interface | RemID | Chassis ID | Port ID | System Name
            r.vizinhos.append({"interface_local": partes[0], "vizinho_interface": partes[3], "vizinho_nome": partes[4] if len(partes) > 4 else ""})
            achou = True
    return achou


def vlans_vrp(t: str, r: Leitura) -> bool:
    """`display vlan` (Huawei: a tabela "VID Type Status ... Description", depois da tabela de portas) e `display vlan brief` (H3C: "VLAN ID Name ...").

    Só lê depois do cabeçalho certo: a tabela de portas do Huawei também começa com o número da VLAN e não pode virar nome.
    """
    linhas = t.splitlines()
    achou = False
    huawei = next((i for i, l in enumerate(linhas) if re.match(r"\s*VID\s+Type\s+Status", l)), None)
    if huawei is not None:
        pos = linhas[huawei].find("Description")
        for l in linhas[huawei + 1:]:
            m = re.match(r"^\s*(\d{1,4})\s+\S+", l)
            if m and 1 <= int(m.group(1)) <= 4094:
                nome = l[pos:].strip().rstrip(".") if pos > 0 else ""
                r.vlans.append((int(m.group(1)), nome))
                achou = True
        return achou
    h3c = next((i for i, l in enumerate(linhas) if re.search(r"VLAN\s*ID\s+Name", l, re.I)), None)
    for l in linhas[(h3c + 1) if h3c is not None else len(linhas):]:
        m = re.match(r"^\s*(\d{1,4})\s+(\S+)", l)
        if m and 1 <= int(m.group(1)) <= 4094:
            r.vlans.append((int(m.group(1)), m.group(2)))
            achou = True
    return achou


def vlans_ios(t: str, r: Leitura) -> bool:
    """`show vlan brief` (Cisco) e `show vlan` (Dell): número e nome."""
    achou = False
    for l in t.splitlines():
        m = re.match(r"^(\d{1,4})\s+(\S+)", l)
        if m and 1 <= int(m.group(1)) <= 4094:
            r.vlans.append((int(m.group(1)), m.group(2)))
            achou = True
    return achou


# Tentativas de cada família: (o que é, comando, leitor, alvo) — alvo "r" (a leitura) ou "portas"
TENTATIVAS: dict[str, list[tuple[str, str, Callable, str]]] = {
    "vrp": [
        ("versão", "display version", versao_vrp, "r"),
        ("número de série", "display device esn", serie_vrp, "r"),
        ("número de série", "display esn", serie_vrp, "r"),
        ("número de série", "display device manuinfo", serie_vrp, "r"),
        ("portas", "display interface | include (current state|Speed|Duplex|Description)", interfaces_vrp, "portas"),
        ("VLANs das portas", "display port vlan", port_vlan_vrp, "portas"),
        ("configuração das portas", "display current-configuration", config_vrp, "portas"),
        ("vizinhos LLDP", "display lldp neighbor brief", lldp_vrp, "r"),
        ("vizinhos LLDP", "display lldp neighbor-information list", lldp_vrp, "r"),
        ("VLANs", "display vlan", vlans_vrp, "r"),
        ("VLANs", "display vlan brief", vlans_vrp, "r"),
    ],
    "ios": [
        ("versão", "show version", versao_ios, "r"),
        ("portas", "show interfaces status", status_ios, "portas"),
        ("configuração das portas", "show running-config", config_ios, "portas"),
        ("vizinhos LLDP", "show lldp neighbors", lldp_ios, "r"),
        ("vizinhos LLDP", "show lldp remote-device all", lldp_ios, "r"),
        ("VLANs", "show vlan brief", vlans_ios, "r"),
        ("VLANs", "show vlan", vlans_ios, "r"),
    ],
}


def _so_consulta(comando: str) -> str:
    """Trava de segurança: só comandos de consulta saem para o equipamento."""
    if not re.match(r"^(display|show)\s", comando):
        raise ValueError(f"Comando não permitido na leitura: {comando}")
    return comando


def ler_textos(familia: str, executar: Callable[[str], str], leitura: Leitura | None = None) -> Leitura:
    """Roda as tentativas da família com a função `executar(comando) -> texto` e monta a leitura.

    Para cada "o que é", a primeira tentativa que trouxer algo vale (a de configuração completa ainda soma ao que já veio). Erro do
    equipamento ("Error", "Invalid input", "Unrecognized command") ou leitor sem resultado = pula para a próxima; nada = aviso.
    """
    r = leitura or Leitura()
    portas: dict[str, PortaLida] = {}
    conseguiu: set[str] = set()
    for o_que, comando, leitor, alvo in TENTATIVAS[familia]:
        # O que já veio de um comando próprio não precisa da tentativa seguinte (a configuração completa sempre soma: tem modo e VLANs)
        if o_que in conseguiu and o_que != "configuração das portas":
            continue
        if o_que == "configuração das portas" and "VLANs das portas" in conseguiu:
            continue
        try:
            texto = executar(_so_consulta(comando)) or ""
        except Exception:  # noqa: BLE001 - falha de um comando não derruba a leitura
            continue
        if re.search(r"(Error:|Invalid input|Unrecognized command|Incomplete command|% Invalid|Wrong parameter)", texto, re.I):
            continue
        try:
            ok = leitor(texto, portas if alvo == "portas" else r)
        except Exception:  # noqa: BLE001 - leitor tolerante: saída inesperada vira "não reconhecido"
            ok = False
        if ok:
            conseguiu.add(o_que)
    r.portas = sorted(portas.values(), key=lambda p: chave_interface(p.interface))
    for o_que in ("versão", "portas", "vizinhos LLDP", "VLANs"):
        if o_que not in conseguiu:
            r.avisos.append(f"Não foi possível ler {o_que} deste equipamento.")
    if "VLANs das portas" not in conseguiu and "configuração das portas" not in conseguiu:
        r.avisos.append("Não foi possível ler o modo e as VLANs das portas.")
    return r


def ler(ip: str, usuario: str, senha: str, porta: int = 22, tipo: str | None = None) -> Leitura:
    """Entra no equipamento (só consulta) e devolve a leitura. Sem tipo conhecido, detecta; se a detecção falhar, tenta cada tipo da SPI."""
    import time

    from netmiko import ConnectHandler, SSHDetect
    from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

    inicio = time.monotonic()
    base = {"host": ip, "username": usuario, "password": senha, "port": porta, "timeout": 20, "conn_timeout": 15, "auth_timeout": 20,
            "banner_timeout": 20, "fast_cli": False}
    candidatos: list[str] = [tipo] if tipo else []
    if not tipo:
        try:
            detectado = SSHDetect(device_type="autodetect", **base).autodetect()
            # "huawei" na detecção cobre o VRP v8 (YunShan) também
            candidatos += ["huawei_vrpv8", "huawei"] if detectado == "huawei" else [detectado] if detectado else []
        except NetmikoAuthenticationException as erro:
            raise ErroLeitura("Usuário ou senha recusados pelo equipamento.") from erro
        except (NetmikoTimeoutException, OSError) as erro:
            raise ErroLeitura(f"O equipamento {ip} não respondeu ao SSH (porta {porta}).") from erro
        except Exception:  # noqa: BLE001 - detecção incerta: seguem as tentativas
            pass
    candidatos += [t for t in TIPOS_TENTADOS if t not in candidatos]
    ultimo_erro: Exception | None = None
    for t in candidatos:
        # Passou do prazo: para de tentar (a chamada da API não pode passar de 60 s)
        if time.monotonic() - inicio > PRAZO_LEITURA:
            break
        try:
            conexao = ConnectHandler(device_type=t, **base)
        except NetmikoAuthenticationException as erro:
            raise ErroLeitura("Usuário ou senha recusados pelo equipamento.") from erro
        except (NetmikoTimeoutException, OSError) as erro:
            raise ErroLeitura(f"O equipamento {ip} não respondeu ao SSH (porta {porta}).") from erro
        except Exception as erro:  # noqa: BLE001 - tipo errado (prompt diferente): tenta o próximo
            ultimo_erro = erro
            continue
        try:
            leitura = Leitura(tipo=t)
            leitura.nome = re.sub(r"^[<\[]|[>\]#]$", "", conexao.find_prompt().strip())
            ler_textos(FAMILIA.get(t, "ios"), lambda c: conexao.send_command(c, read_timeout=60), leitura)
            if leitura.modelo or leitura.portas:
                return leitura
        except Exception as erro:  # noqa: BLE001
            ultimo_erro = erro
        finally:
            try:
                conexao.disconnect()
            except Exception:  # noqa: BLE001
                pass
    vazio = Leitura()
    vazio.avisos.append("Nenhum dos tipos conhecidos (Huawei, Dell, H3C, Cisco) conseguiu ler este equipamento." +
                        (f" Último erro: {ultimo_erro}" if ultimo_erro else ""))
    return vazio


def porta_da_interface(interface: str, linhas: int, colunas: int, extras: list[dict]) -> int | None:
    """Número lógico da porta da face para o nome da interface (genérico para os modelos cadastrados).

    1) nome igual ao rótulo de uma porta extra do modelo (ex.: "25GE1/0/1"); 2) senão, o último número do nome dentro da grade
    ("MultiGE1/0/5" → 5; "Gi1/0/24" → 24). Interface lógica não tem porta.
    """
    if eh_logica(interface):
        return None
    chave = chave_interface(interface)
    for e in extras or []:
        if e.get("rotulo") and chave_interface(e["rotulo"]) == chave:
            return int(e["numero"])
    m = re.search(r"(\d+)$", interface.strip())
    if not m:
        return None
    n = int(m.group(1))
    # Interfaces de fibra com rótulo próprio que não bateu (ex.: outro prefixo) não caem por engano numa porta da grade de cobre
    if extras and any(chave_interface(e.get("rotulo", ""))[:2] == chave[:2] for e in extras) and not any(
            chave_interface(e.get("rotulo", "")) == chave for e in extras):
        return None
    return n if 1 <= n <= linhas * colunas else None
