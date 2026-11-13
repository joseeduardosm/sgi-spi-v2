"""
===============================================================================
ARQUIVO: servico_leitura.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Levar para o cadastro da Rede o que foi lido do equipamento por SSH: testar
o acesso no cadastro, guardar cada leitura, ligar sozinho os vizinhos LLDP,
montar o resumo e aplicar o que o usuário escolher.

RESUMO TÉCNICO:
- `testar`: lê sem gravar nada e sugere o cabo de subida (porta deste ↔
  porta do vizinho de cima já cadastrado), para o passo Conexão do cadastro.
- `ler_e_guardar`: lê com a credencial do equipamento, grava o tipo que
  funcionou, liga os vizinhos LLDP (decisão do usuário: sozinho, quando os
  dois lados estão livres) e guarda a leitura em `rede_leituras`.
- `resumo`: compara a leitura com o cadastro em grupos (equipamento, VLANs
  novas, ligações LLDP, portas com descrição sem ligação, configuração).
- `aplicar`: grava só os itens marcados, pelas mesmas regras de
  app/services/rede/servico.py (porta só tem configuração se estiver ligada).

FINALIDADE DE NEGÓCIO:
Evita digitar portas, VLANs e cabos: o SGI mostra o que o equipamento tem e a
pessoa decide o que vira cadastro.

CONTEXTO NO SISTEMA:
Leitura em app/services/rede/leitura_ssh.py; rotas em
app/api/routes/rede.py; senha cifrada com app/core/criptografia.py.

===============================================================================
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.criptografia import decifrar_segredo
from app.models.rede import TIPOS_PASSIVOS, EquipamentoRede, LeituraRede, ModeloFaceRede, PortaRede, VlanRede
from app.services.rede import leitura_ssh, servico
from app.services.rede.servico import DadosPorta, ErroRede


# Leitura por SSH desligada por enquanto (decisão do usuário, 13/11/2026: vai ser lapidada antes de voltar). O código fica; com False,
# toda leitura é recusada com `409 leitura_desativada` e a tela esconde o acesso SSH. Para religar: True aqui e no frontend
# (LEITURA_SSH_ATIVA em features/rede/rede.models.ts).
LEITURA_SSH_ATIVA = False


def _ler(ip: str, usuario: str, senha: str, porta: int, tipo: str | None) -> leitura_ssh.Leitura:
    """Lê o equipamento; falha de acesso vira erro de regra com a explicação (`409 leitura_falhou`)."""
    if not LEITURA_SSH_ATIVA:
        raise ErroRede("A leitura do equipamento por SSH está desativada por enquanto.", 409, "leitura_desativada")
    if not ip or not usuario or not senha:
        raise ErroRede("Informe o IP de gerência, o usuário e a senha de acesso SSH.")
    try:
        return leitura_ssh.ler(ip, usuario, senha, porta or 22, tipo or None)
    except leitura_ssh.ErroLeitura as erro:
        raise ErroRede(f"Não foi possível ler o equipamento: {erro}", 409, "leitura_falhou") from erro


def _porta_do_modelo(modelo: ModeloFaceRede | None, interface: str) -> int | None:
    if modelo is None:
        return None
    return leitura_ssh.porta_da_interface(interface, modelo.linhas, modelo.colunas, modelo.portas_extras or [])


def _equipamento_por_nome(sessao: Session, nome: str) -> EquipamentoRede | None:
    """Vizinho LLDP pelo nome (sem diferença de maiúsculas; ignora o domínio, ex.: "sw01.spi.local" = "SW01")."""
    curto = (nome or "").strip().split(".")[0]
    if not curto:
        return None
    return sessao.scalar(select(EquipamentoRede).where(func.lower(EquipamentoRede.nome) == curto.lower()))


def _porta_por_numero(e: EquipamentoRede, numero: int | None) -> PortaRede | None:
    return next((p for p in e.portas if p.numero_logico == numero), None) if numero else None


# ---------------------------------------------------------------------------------------------
# Teste no cadastro (nada é gravado)
# ---------------------------------------------------------------------------------------------

def testar(sessao: Session, ip: str, usuario: str, senha: str, porta: int, modelo_face_id: uuid.UUID | None, tipo: str, funcao: str | None) -> dict:
    """Lê o equipamento ainda não cadastrado e sugere o cabo de subida para o passo Conexão.

    A sugestão é o primeiro vizinho LLDP que já está cadastrado, pode ficar acima deste (mesma regra da cadeia) e tem a porta livre.
    """
    leitura = _ler(ip, usuario, senha, porta, None)
    modelo = sessao.get(ModeloFaceRede, modelo_face_id) if modelo_face_id else None
    novo = EquipamentoRede(nome=leitura.nome or "este equipamento", tipo=tipo, funcao=funcao if tipo == "switch" else None)
    sugestao = None
    for v in leitura.vizinhos:
        vizinho = _equipamento_por_nome(sessao, v["vizinho_nome"])
        if vizinho is None or not servico.pode_ficar_acima(novo, vizinho):
            continue
        numero_local = _porta_do_modelo(modelo, v["interface_local"])
        destino = _porta_por_numero(vizinho, _porta_do_modelo(vizinho.modelo_face, v["vizinho_interface"]))
        if numero_local is None or destino is None or servico.ligacoes_da_porta(sessao, destino.id):
            continue
        sugestao = {"porta_numero": numero_local, "destino_equipamento_id": str(vizinho.id), "destino_porta_id": str(destino.id),
                    "texto": f"{v['interface_local']} → {vizinho.nome} · {v['vizinho_interface']}"}
        break
    return {"tipo_acesso": leitura.tipo, "nome": leitura.nome, "modelo": leitura.modelo, "serie": leitura.serie, "versao": leitura.versao,
            "portas": len(leitura.portas), "vlans": len(leitura.vlans), "vizinhos": leitura.vizinhos, "avisos": leitura.avisos, "sugestao": sugestao}


# ---------------------------------------------------------------------------------------------
# Leitura de um equipamento cadastrado
# ---------------------------------------------------------------------------------------------

def ler_e_guardar(sessao: Session, equipamento_id: uuid.UUID, autor: str) -> LeituraRede:
    """Lê o equipamento com a credencial dele, liga sozinho os vizinhos LLDP e guarda a leitura."""
    e = servico.obter_equipamento(sessao, equipamento_id)
    if e.tipo in TIPOS_PASSIVOS:
        raise ErroRede("Patch panel não tem acesso: não há o que ler.")
    if not e.acesso_usuario or not e.acesso_senha:
        raise ErroRede("Cadastre antes o usuário e a senha de acesso SSH do equipamento (em Editar).", 400, "sem_acesso")
    leitura = _ler(e.ip_gerencia, e.acesso_usuario, decifrar_segredo(e.acesso_senha), e.acesso_porta, e.acesso_tipo or None)
    if leitura.tipo:
        e.acesso_tipo = leitura.tipo
    resultado = leitura.como_dict()
    resultado["lldp"] = _ligar_vizinhos(sessao, e, leitura)
    registro = LeituraRede(equipamento_id=e.id, lido_por=autor, resultado=resultado)
    sessao.add(registro)
    sessao.flush()
    return registro


def ultima_leitura(sessao: Session, equipamento_id: uuid.UUID) -> LeituraRede | None:
    return sessao.scalar(select(LeituraRede).where(LeituraRede.equipamento_id == equipamento_id).order_by(LeituraRede.lido_em.desc()).limit(1))


def _ligar_vizinhos(sessao: Session, e: EquipamentoRede, leitura: leitura_ssh.Leitura) -> list[dict]:
    """Vizinhos LLDP (decisão do usuário: ligar sozinho): vizinho cadastrado e as duas portas livres → liga; senão, diz por quê."""
    resultado = []
    for v in leitura.vizinhos:
        item = {**v, "situacao": "nao_ligou", "motivo": ""}
        local = _porta_por_numero(e, _porta_do_modelo(e.modelo_face, v["interface_local"]))
        vizinho = _equipamento_por_nome(sessao, v["vizinho_nome"])
        if local is None:
            item["motivo"] = "A interface não corresponde a nenhuma porta do modelo de face deste equipamento."
        elif vizinho is None:
            item["motivo"] = f"{v['vizinho_nome']} não está cadastrado no SGI."
        else:
            remota = _porta_por_numero(vizinho, _porta_do_modelo(vizinho.modelo_face, v["vizinho_interface"]))
            if remota is None:
                item["motivo"] = f"A interface {v['vizinho_interface']} não corresponde a nenhuma porta do {vizinho.nome}."
            else:
                atual = servico.conexao_da_porta(sessao, local.id) if not servico._eh_patch(local) else None
                if atual is not None and remota.id in (atual.porta_a_id, atual.porta_b_id):
                    item["situacao"] = "ja_estava"
                elif servico.ligacoes_da_porta(sessao, local.id) or servico.ligacoes_da_porta(sessao, remota.id):
                    item["motivo"] = "Uma das duas portas já está ligada a outra coisa no SGI."
                else:
                    try:
                        with sessao.begin_nested():
                            servico.conectar(sessao, local.id, remota.id, None, "")
                        item["situacao"] = "ligada"
                    except ErroRede as erro:
                        item["motivo"] = str(erro)
            item["porta_id"] = str(local.id) if local else None
        resultado.append(item)
    return resultado


# ---------------------------------------------------------------------------------------------
# Resumo e aplicação
# ---------------------------------------------------------------------------------------------

def _texto_config(modo: str | None, pvid: int | None, tag: list[int], sem_tag: list[int], todas: bool, velocidade: int | None, duplex: str | None) -> str:
    partes = [servico.ROTULOS_MODO.get(modo, modo) if modo else "—"]
    if pvid:
        partes.append(f"PVID/VLAN {pvid}")
    if todas:
        partes.append("com tag: todas")
    elif tag:
        partes.append(f"com tag: {len(tag)} VLAN(s)")
    if sem_tag:
        partes.append(f"sem tag: {', '.join(map(str, sem_tag))}")
    if velocidade:
        partes.append(f"{velocidade} Mb/s")
    if duplex:
        partes.append(duplex)
    return " · ".join(partes)


def resumo(sessao: Session, e: EquipamentoRede, registro: LeituraRede) -> dict:
    """O que a leitura traz de diferente do cadastro, em grupos, para a pessoa escolher o que aplicar."""
    r = registro.resultado
    vlans_sgi = {v.numero for v in sessao.scalars(select(VlanRede))}
    por_interface = {}
    descricoes, configuracao = [], []
    sem_ligacao = 0
    portas_lldp = {item.get("porta_id") for item in r.get("lldp", [])}
    for pl in r.get("portas", []):
        porta = _porta_por_numero(e, _porta_do_modelo(e.modelo_face, pl["interface"]))
        if porta is None:
            continue
        por_interface[pl["interface"]] = porta
        ligada = bool(servico.ligacoes_da_porta(sessao, porta.id))
        if not ligada and pl.get("link") and pl.get("descricao") and str(porta.id) not in portas_lldp and not servico._eh_patch(porta):
            descricoes.append({"interface": pl["interface"], "porta_id": str(porta.id), "porta": porta.nome or str(porta.numero_logico),
                               "descricao": pl["descricao"]})
        if pl.get("modo") and not servico._eh_patch(porta):
            lida = _texto_config(pl["modo"], pl.get("pvid"), pl.get("vlans_tag", []), pl.get("vlans_sem_tag", []), pl.get("todas_vlans", False),
                                 pl.get("velocidade"), pl.get("duplex"))
            vlan_atual = next((v.numero for v in sessao.scalars(select(VlanRede).where(VlanRede.id == porta.vlan_nativa_id))), None) if porta.vlan_nativa_id else None
            atual = _texto_config(porta.modo if ligada else None, vlan_atual, [x for x in porta.vlans if x.com_tag], [], False,
                                  porta.velocidade_mbps, porta.duplex) if ligada else "porta sem ligação (em branco)"
            # Porta sem ligação no SGI só entra se puder ser ligada pela descrição do switch (regra: configuração só em porta ligada);
            # as demais (em geral o padrão de fábrica de porta vazia) só são contadas, para o resumo não virar uma lista enorme
            pode = ligada or any(d["porta_id"] == str(porta.id) for d in descricoes)
            if lida != atual and not pode:
                sem_ligacao += 1
            elif lida != atual:
                configuracao.append({"interface": pl["interface"], "porta_id": str(porta.id), "porta": porta.nome or str(porta.numero_logico),
                                     "atual": atual, "lida": lida, "ligada": ligada})
    equipamento = {"serie_lida": r.get("serie", ""), "serie_cadastro": e.numero_serie, "modelo": r.get("modelo", ""), "versao": r.get("versao", ""),
                   "nome_lido": r.get("nome", "")}
    vlans_novas = [{"numero": n, "nome": nome} for n, nome in r.get("vlans", []) if n not in vlans_sgi and n != 1]
    return {"id": str(registro.id), "lido_em": registro.lido_em, "lido_por": registro.lido_por, "aplicada_em": registro.aplicada_em,
            "tipo_acesso": r.get("tipo", ""), "equipamento": equipamento, "vlans_novas": vlans_novas, "lldp": r.get("lldp", []),
            "descricoes": descricoes, "configuracao": configuracao, "portas_sem_ligacao": sem_ligacao, "avisos": r.get("avisos", [])}


@dataclass
class EscolhasLeitura:
    """O que a pessoa marcou no resumo para aplicar."""
    equipamento: bool = False
    vlans: list[int] = field(default_factory=list)
    descricoes: list[str] = field(default_factory=list)
    configuracao: list[str] = field(default_factory=list)


def aplicar(sessao: Session, e: EquipamentoRede, registro: LeituraRede, escolhas: EscolhasLeitura, autor: str) -> list[uuid.UUID]:
    """Grava os itens marcados, nesta ordem: equipamento, VLANs novas, portas ligadas pela descrição e configuração das portas.

    A configuração só vale em porta ligada (regra do SGI): porta marcada que continua sem ligação é pulada. VLANs que o SGI não tem (e não
    foram marcadas para cadastrar) ficam de fora; "todas as VLANs" do switch não vira lista. Devolve as portas alteradas (para a auditoria).
    """
    r = registro.resultado
    alteradas: list[uuid.UUID] = []
    if escolhas.equipamento and r.get("serie"):
        e.numero_serie = r["serie"][:120]
        info = f"Lido do equipamento: {r.get('modelo', '')}, versão {r.get('versao', '')}".strip()
        if info not in (e.observacao or ""):
            e.observacao = f"{e.observacao}\n{info}".strip() if e.observacao else info
    nomes_lidos = dict((n, nome) for n, nome in r.get("vlans", []))
    existentes = {v.numero for v in sessao.scalars(select(VlanRede))}
    for numero in escolhas.vlans:
        if numero not in existentes and 1 <= numero <= 4094:
            servico.salvar_vlan(sessao, None, numero, nomes_lidos.get(numero, "") or f"VLAN {numero}", "Cadastrada pela leitura do equipamento " + e.nome)
    vlan_id = {v.numero: v.id for v in sessao.scalars(select(VlanRede))}
    lidas = {pl["interface"]: pl for pl in r.get("portas", [])}
    for interface in escolhas.descricoes:
        pl = lidas.get(interface)
        porta = _porta_por_numero(e, _porta_do_modelo(e.modelo_face, interface)) if pl else None
        if porta is not None and not servico.ligacoes_da_porta(sessao, porta.id) and pl.get("descricao"):
            servico.conectar(sessao, porta.id, None, None, pl["descricao"])
            alteradas.append(porta.id)
    for interface in escolhas.configuracao:
        pl = lidas.get(interface)
        porta = _porta_por_numero(e, _porta_do_modelo(e.modelo_face, interface)) if pl else None
        if porta is None or not pl.get("modo") or not servico.ligacoes_da_porta(sessao, porta.id):
            continue
        modo = pl["modo"]
        tag = [] if pl.get("todas_vlans") else [vlan_id[n] for n in pl.get("vlans_tag", []) if n in vlan_id]
        sem_tag = [vlan_id[n] for n in pl.get("vlans_sem_tag", []) if n in vlan_id]
        nativa = vlan_id.get(pl.get("pvid")) if modo != "roteada" else None
        dados = DadosPorta(observacao=porta.observacao, modo=modo, vlan_nativa_id=nativa,
                           vlans_tag=tag if modo in ("trunk", "hybrid", "dinamico_auto", "dinamico_desejavel") else [],
                           vlans_sem_tag=sem_tag if modo == "hybrid" else [], velocidade_mbps=pl.get("velocidade"), duplex=pl.get("duplex"), status="up")
        servico._aplicar_configuracao(sessao, porta, dados)
        alteradas.append(porta.id)
    registro.aplicada_em, registro.aplicada_por = agora_utc(), autor
    sessao.flush()
    return alteradas
