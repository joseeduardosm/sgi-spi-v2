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

import heapq
import ipaddress
import uuid
from collections import Counter
from dataclasses import dataclass
from itertools import count

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.acl import NivelAcl
from app.models.chamados import Chamado
from app.models.patrimonio import Bem, Localizacao
from app.models.rede import (
    CORES_RACK, DESCRICAO_DESLIGADA, DUPLEX, FUNCOES_CORE, LADOS_PATCH, FUNCOES_EQUIPAMENTO, MODOS_PORTA, NUMERACOES, STATUS_PORTA, TIPOS_EQUIPAMENTO, TIPOS_PASSIVOS, ConexaoRede, DispositivoAtrasRede, EquipamentoRede, ModeloFaceRede, PontoRede, PortaRede,
    PortaVlanRede, RackRede, VlanRede,
)
from app.models.usuario import Usuario
from app.services import servico_acl
from app.services.servico_auditoria import auditar

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
    # A grade (linhas, colunas, numeração e portas extras) é a forma das portas dos equipamentos: com equipamento usando o modelo, ela
    # não muda (as portas deles não acompanhariam). Nome, fabricante e altura continuam editáveis.
    em_uso = modelo_id is not None and (sessao.scalar(select(func.count()).select_from(EquipamentoRede).where(EquipamentoRede.modelo_face_id == modelo_id)) or 0)
    grade_atual = (modelo.linhas, modelo.colunas, modelo.numeracao, modelo.portas_extras or [])
    modelo.nome, modelo.fabricante, modelo.linhas, modelo.colunas, modelo.numeracao = nome, fabricante.strip()[:120], linhas, colunas, numeracao
    modelo.altura_u = max(1, min(altura_u, 10))
    modelo.portas_extras = _validar_extras(modelo, extras)
    if em_uso and (modelo.linhas, modelo.colunas, modelo.numeracao, modelo.portas_extras) != grade_atual:
        raise ErroRede(f"O modelo está em uso por {em_uso} equipamento(s): a grade e as portas extras não mudam. Crie outro modelo.", 409, "modelo_em_uso")
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
    # Só na criação: o cabo que liga o equipamento a quem está acima dele (cadastro em cadeia)
    ligacao: "DadosLigacaoCadastro | None" = None
    # Acesso SSH só leitura (carga do equipamento). Senha em texto só no caminho: é cifrada ao gravar; None = manter a que está gravada
    acesso_usuario: str = ""
    acesso_senha: str | None = None
    acesso_porta: int = 22


@dataclass
class DadosLigacaoCadastro:
    """O cabo informado no cadastro: "este equipamento, na porta X (configuração), está conectado no equipamento Y, na porta Y (configuração)".

    `destino_lado`: o lado da porta quando o cabo chega num patch panel (fundo ou frente); o outro lado daquela porta precisa levar a quem
    pode ficar acima. `config_destino` só vale para porta de switch (patch panel não tem configuração).
    """
    porta_numero: int
    destino_porta_id: uuid.UUID
    destino_lado: str | None = None
    config: "DadosPorta | None" = None
    config_destino: "DadosPorta | None" = None


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
    # Todo equipamento ativo de rede tem IP de gerência (é o que o ping testa); só o patch panel, passivo, não tem.
    # A função na topologia (core, distribuição, acesso) é só do switch: access point, roteador e "outro" ficam abaixo do acesso (decisão do usuário)
    if d.tipo != "switch":
        d.funcao = None
    elif d.funcao not in FUNCOES_EQUIPAMENTO:
        raise ErroRede("Escolha a função do switch na topologia: core primário, core secundário, distribuição ou acesso.")
    if d.tipo not in TIPOS_PASSIVOS and not d.ip_gerencia.strip():
        raise ErroRede("Informe o IP de gerência (obrigatório em todo equipamento, menos patch panel).")
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
    # Toda porta nasce sem nada ligado: desligada e em branco (decisão do usuário)
    novas = [PortaRede(numero_logico=n, nome=rotulos.get(n, str(n)), status="down", descricao=DESCRICAO_DESLIGADA) for n in numeros if n not in existentes]
    equipamento.portas.extend(novas)
    sessao.flush()
    return len(novas)


def _exigencias_da_cadeia(sessao: Session, d: DadosEquipamento) -> None:
    """Cadastro em cadeia (decisão do usuário): não há distribuição sem core, nem acesso sem core e distribuição, nem AP sem acesso."""
    funcoes = set(sessao.scalars(select(EquipamentoRede.funcao).where(EquipamentoRede.tipo == "switch", EquipamentoRede.funcao.is_not(None))))
    if d.tipo == "switch" and d.funcao == "core_secundario" and "core_primario" not in funcoes:
        raise ErroRede("Cadastre antes o core primário: o core secundário é ligado a ele.", 409, "cadeia_incompleta")
    if d.tipo == "switch" and d.funcao in ("distribuicao", "acesso") and not funcoes & set(FUNCOES_CORE):
        raise ErroRede("Cadastre antes o core: a rede é cadastrada de cima para baixo (core, distribuição, acesso).", 409, "cadeia_incompleta")
    if d.tipo == "switch" and d.funcao == "acesso" and "distribuicao" not in funcoes:
        raise ErroRede("Cadastre antes pelo menos uma distribuição: o acesso vem depois dela.", 409, "cadeia_incompleta")
    if d.tipo not in ("switch",) + TIPOS_PASSIVOS and "acesso" not in funcoes:
        raise ErroRede("Cadastre antes um switch de acesso: o access point, o roteador e os demais ficam ligados nele.", 409, "cadeia_incompleta")


def precisa_de_ligacao(d: DadosEquipamento) -> bool:
    """Todo equipamento entra ligado a quem está acima dele, menos o core primário (o topo) e o patch panel (passivo)."""
    return d.tipo not in TIPOS_PASSIVOS and not (d.tipo == "switch" and d.funcao == "core_primario")


def _conferir_destino(sessao: Session, novo: EquipamentoRede, lig: DadosLigacaoCadastro) -> PortaRede:
    """Confere o lado de cima do cabo do cadastro: a porta precisa estar livre e levar (direto ou atravessando o patch panel) a quem pode ficar
    acima do equipamento novo. Devolve a porta de destino."""
    destino = obter_porta(sessao, lig.destino_porta_id)
    lado = _conferir_lado(destino, lig.destino_lado)
    if conexao_da_porta(sessao, destino.id, lado) is not None:
        raise ErroRede(f"{'O ' + lado + ' da porta' if lado else 'A porta'} {_nome_porta(destino)} já está ocupado." if lado else
                       f"A porta {_nome_porta(destino)} já está ocupada.", 409, "porta_ocupada")
    if lado:
        # Chega num patch panel: o que vale é o que está do outro lado daquela porta
        fio = seguir_fio(sessao, destino, oposto(lado))
        if fio.fim is None:
            raise ErroRede(f"O {oposto(lado)} da porta {_nome_porta(destino)} não leva a nenhum switch: ligue antes esse lado a {rotulo_acima(novo)}.")
        acima = fio.fim.equipamento
    else:
        acima = destino.equipamento
    if not pode_ficar_acima(novo, acima):
        raise ErroRede(f"O {novo.nome} precisa estar ligado a {rotulo_acima(novo)}; {acima.nome} não serve.", 409, "cadeia_invalida")
    return destino


def salvar_equipamento(sessao: Session, equipamento_id: uuid.UUID | None, d: DadosEquipamento) -> EquipamentoRede:
    """Cria ou altera um equipamento.

    Na criação (decisões do usuário): a rede é cadastrada em cadeia (`_exigencias_da_cadeia`) e todo equipamento, menos o core primário e o
    patch panel, já entra com o cabo para quem está acima dele (porta deste, porta do outro e a configuração das duas). As demais portas
    nascem desligadas e em branco. Na edição, o modelo de face, o tipo e a função não mudam (exclui e cadastra de novo).
    """
    _validar_equipamento(sessao, d, equipamento_id)
    item = obter_equipamento(sessao, equipamento_id) if equipamento_id else EquipamentoRede(portas=[])
    novo = equipamento_id is None
    # Regra (decisão do usuário): o modelo de face é escolhido na criação e não muda mais; para trocar, exclui-se o equipamento e
    # cadastra-se de novo. Só o equipamento antigo que ficou sem modelo pode recebê-lo uma vez (as portas são criadas por ele).
    definiu_modelo = not novo and item.modelo_face_id is None and d.modelo_face_id is not None
    if not novo and not definiu_modelo and item.modelo_face_id != d.modelo_face_id:
        raise ErroRede("O modelo de face não muda depois de criado: exclua o equipamento e cadastre de novo com o outro modelo.", 409, "modelo_travado")
    # Tipo e função travados (decisão do usuário): mudariam o lugar do equipamento na cadeia já cadastrada
    if not novo and item.tipo != d.tipo:
        raise ErroRede("O tipo não muda depois de criado: exclua o equipamento e cadastre de novo.", 409, "tipo_travado")
    if not novo and (item.funcao or None) != (d.funcao or None):
        raise ErroRede("A função não muda depois de criado: exclua o equipamento e cadastre de novo.", 409, "funcao_travada")
    ligacao = d.ligacao if novo and precisa_de_ligacao(d) else None
    if novo:
        _exigencias_da_cadeia(sessao, d)
        if precisa_de_ligacao(d) and ligacao is None:
            raise ErroRede("Informe em qual equipamento e porta este está conectado (o cabo para quem está acima dele).", 400, "sem_ligacao")
    if (item.ip_gerencia or "") != d.ip_gerencia.strip():
        # IP novo: o resultado do ping antigo não vale mais; o próximo teste diz a situação
        item.ping_situacao, item.ping_falhas, item.ping_verificado_em, item.ping_mudou_em = None, 0, None, None
    for campo, valor in d.__dict__.items():
        if campo not in ("ligacao", "acesso_senha"):
            setattr(item, campo, valor.strip() if isinstance(valor, str) else valor)
    # Senha do acesso SSH: cifrada; sem usuário, não há acesso (a senha sai junto); senha não enviada mantém a gravada
    if not item.acesso_usuario:
        item.acesso_senha, item.acesso_tipo = "", ""
    elif d.acesso_senha:
        from app.core.criptografia import cifrar_segredo

        item.acesso_senha, item.acesso_tipo = cifrar_segredo(d.acesso_senha), ""
    if item.tipo in TIPOS_PASSIVOS:
        item.acesso_usuario, item.acesso_senha, item.acesso_tipo = "", "", ""
    if ligacao is not None:
        # Confere o destino antes de gravar qualquer coisa (o nome do equipamento novo entra nas mensagens)
        _conferir_destino(sessao, item, ligacao)
    sessao.add(item)
    sessao.flush()
    # As portas nascem do modelo só na criação (ou quando o equipamento antigo recebe o modelo pela primeira vez)
    if novo or definiu_modelo:
        sessao.refresh(item, ["modelo_face"])
        gerar_portas(sessao, item)
    if ligacao is not None:
        _ligar_cadastro(sessao, item, ligacao)
    return item


def _ligar_cadastro(sessao: Session, item: EquipamentoRede, lig: DadosLigacaoCadastro) -> None:
    """Grava o cabo do cadastro e a configuração das duas portas (a de destino só se for de switch)."""
    propria = next((p for p in item.portas if p.numero_logico == lig.porta_numero), None)
    if propria is None:
        raise ErroRede("Escolha uma porta que exista no modelo de face deste equipamento.")
    destino = obter_porta(sessao, lig.destino_porta_id)
    conectar(sessao, propria.id, destino.id, None, "", None, lig.destino_lado)
    _aplicar_configuracao(sessao, propria, lig.config or DadosPorta(status="up"))
    if lig.config_destino is not None and not _eh_patch(destino):
        _aplicar_configuracao(sessao, destino, lig.config_destino)


def excluir_equipamento(sessao: Session, equipamento_id: uuid.UUID) -> None:
    """Exclui o equipamento (as portas e as ligações dele saem junto).

    Não deixa outro equipamento sem cabo para quem está acima dele (decisão do usuário): excluir uma distribuição com acessos pendurados só
    nela, ou o patch panel por onde passa o único cabo de um switch, é recusado (`409 unica_ligacao_para_cima`).
    """
    e = obter_equipamento(sessao, equipamento_id)
    portas = {p.id for p in e.portas}
    afetados: set[uuid.UUID] = set()
    for p in e.portas:
        for c in ligacoes_da_porta(sessao, p.id):
            afetados |= _equipamentos_nas_pontas(sessao, c)
    afetados.discard(e.id)
    _conferir_cadeia(sessao, afetados, lambda c: c.porta_a_id in portas or c.porta_b_id in portas)
    vizinhos = {i for p in e.portas for c in ligacoes_da_porta(sessao, p.id) for i in (c.porta_a_id, c.porta_b_id) if i and i not in portas}
    sessao.delete(e)
    sessao.flush()
    # As portas do outro lado perderam a ligação: ficam em branco ou com a descrição refeita
    for porta_id in vizinhos:
        porta = sessao.get(PortaRede, porta_id)
        if porta is None:
            continue
        if ligacoes_da_porta(sessao, porta.id):
            atualizar_descricao(sessao, porta)
        else:
            limpar_porta(sessao, porta, "down")


@dataclass
class DadosPorta:
    # Anotação livre da porta (a descrição é gerada pelo sistema)
    observacao: str = ""
    modo: str = "access"
    vlan_nativa_id: uuid.UUID | None = None
    vlans_tag: list[uuid.UUID] | None = None
    vlans_sem_tag: list[uuid.UUID] | None = None
    vlan_voz_id: uuid.UUID | None = None
    ip_interface: str = ""
    velocidade_mbps: int | None = None
    duplex: str | None = None
    status: str | None = None


# Alvo das auditorias de porta: cada alteração de qualquer atributo da porta (configuração, ligação, dispositivo atrás, ponto, carga LLDP)
# grava um registro com o id da porta, que alimenta os indicadores "Portas alteradas nos últimos 7 dias" e "quem alterou"
ALVO_PORTA = "rede_porta"


def rotulo_porta_auditoria(porta: PortaRede) -> str:
    """Texto do alvo na auditoria: "SW-5A · 3" (equipamento · nome ou número da porta)."""
    return f"{porta.equipamento.nome} · {porta.nome or porta.numero_logico}"[:255]


def auditar_portas(sessao: Session, autor: str, autor_id: int | None, acao: str, portas_ids) -> None:
    """Registra a alteração de cada porta (sem repetir) na auditoria, com o id dela como alvo."""
    for porta_id in dict.fromkeys(i for i in portas_ids if i is not None):
        porta = sessao.get(PortaRede, porta_id)
        if porta is not None:
            auditar(sessao, autor, acao, rotulo_porta_auditoria(porta), autor_id=autor_id, alvo_tipo=ALVO_PORTA, alvo_id=porta.id)


def pontas_da_conexao(sessao: Session, porta_id: uuid.UUID, lado: str | None = None) -> list[uuid.UUID]:
    """As portas de uma conexão (a própria e, se houver, a do outro lado), para auditar as duas pontas."""
    conexao = conexao_da_porta(sessao, porta_id, lado)
    return [conexao.porta_a_id, conexao.porta_b_id] if conexao is not None else [porta_id]


@dataclass
class PortaListada:
    """Uma linha das listas dos indicadores: a porta, o equipamento e a última alteração dela (quem e quando)."""
    porta: PortaRede
    alterado_por: str | None
    alterado_em: object | None


# Janela do indicador "Portas alteradas": os últimos 7 dias (decisão do usuário), contados a partir de agora
DIAS_PORTAS_ALTERADAS = 7


def _ultima_alteracao(desde=None):
    """Última alteração de cada porta na auditoria (desde `desde`, se informado): alvo_id → (autor, quando).

    O maior horário por porta, ligado de volta à linha da auditoria (funciona no PostgreSQL e no SQLite dos testes; usa o índice de alvo).
    Duas linhas da mesma porta no mesmo instante (ex.: as duas pontas de uma ligação são portas diferentes, então não acontece) ficariam
    as duas; o `max(autor)` desempata.
    """
    from app.models.auditoria import RegistroAuditoria

    filtro = RegistroAuditoria.alvo_tipo == ALVO_PORTA
    if desde is not None:
        filtro = filtro & (RegistroAuditoria.ocorrido_em >= desde)
    maximo = (select(RegistroAuditoria.alvo_id, func.max(RegistroAuditoria.ocorrido_em).label("quando"))
              .where(filtro).group_by(RegistroAuditoria.alvo_id).subquery())
    return (select(RegistroAuditoria.alvo_id, func.max(func.coalesce(func.nullif(Usuario.nome_completo, ""), RegistroAuditoria.autor)).label("autor"),
                   RegistroAuditoria.ocorrido_em)
            .join(maximo, (maximo.c.alvo_id == RegistroAuditoria.alvo_id) & (maximo.c.quando == RegistroAuditoria.ocorrido_em))
            .outerjoin(Usuario, Usuario.id == RegistroAuditoria.autor_id)
            .where(RegistroAuditoria.alvo_tipo == ALVO_PORTA)
            .group_by(RegistroAuditoria.alvo_id, RegistroAuditoria.ocorrido_em).subquery())


def _alteracoes(sessao: Session, ultima, ids: list[str] | None = None) -> dict[uuid.UUID, tuple[str, object]]:
    """Última alteração por porta: {id da porta: (autor, quando)}. Com `ids`, só dessas portas.

    A junção com as portas é feita aqui pelo UUID (o id é gravado de jeitos diferentes no PostgreSQL e no SQLite dos testes)."""
    consulta = select(ultima.c.alvo_id, ultima.c.autor, ultima.c.ocorrido_em)
    if ids is not None:
        consulta = consulta.where(ultima.c.alvo_id.in_(ids))
    resultado = {}
    for alvo, autor, quando in sessao.execute(consulta):
        try:
            resultado[uuid.UUID(alvo)] = (autor, quando)
        except ValueError:
            continue
    return resultado


def _ordenar(itens: list[PortaListada]) -> list[PortaListada]:
    """Mais recente primeiro (sem alteração por último), depois equipamento e número da porta."""
    from datetime import datetime, timezone

    def chave(i: PortaListada):
        quando = i.alterado_em
        instante = quando.replace(tzinfo=quando.tzinfo or timezone.utc).timestamp() if isinstance(quando, datetime) else float("-inf")
        return (-instante, i.porta.equipamento.nome, i.porta.numero_logico)
    return sorted(itens, key=chave)


def portas_alteradas(sessao: Session) -> list[PortaListada]:
    """Portas com qualquer alteração (configuração, ligação, dispositivo atrás, ponto, carga LLDP) nos últimos 7 dias, com a última delas."""
    from datetime import timedelta

    from app.core.banco import agora_utc

    ultimas = _alteracoes(sessao, _ultima_alteracao(agora_utc() - timedelta(days=DIAS_PORTAS_ALTERADAS)))
    if not ultimas:
        return []
    portas = sessao.scalars(select(PortaRede).where(PortaRede.id.in_(list(ultimas))).options(selectinload(PortaRede.equipamento)))
    return _ordenar([PortaListada(p, *ultimas[p.id]) for p in portas])


def _patch_um_lado(sessao: Session) -> list[PortaRede]:
    """Portas de patch panel com um lado ligado e o outro vazio (o cabo para no meio do caminho)."""
    contagem = Counter()
    for c in sessao.scalars(select(ConexaoRede).where(or_(ConexaoRede.lado_a.is_not(None), ConexaoRede.lado_b.is_not(None)))):
        if c.lado_a:
            contagem[c.porta_a_id] += 1
        if c.lado_b and c.porta_b_id:
            contagem[c.porta_b_id] += 1
    ids = [i for i, n in contagem.items() if n == 1]
    return list(sessao.scalars(select(PortaRede).where(PortaRede.id.in_(ids)).options(selectinload(PortaRede.equipamento)))) if ids else []


def portas_patch_um_lado(sessao: Session) -> list[PortaListada]:
    """Portas de patch panel com um lado só ligado (pendência do cadastro), com a última alteração de cada uma (de qualquer época), se houver."""
    portas = _patch_um_lado(sessao)
    ultimas = _alteracoes(sessao, _ultima_alteracao(), [str(p.id) for p in portas]) if portas else {}
    return _ordenar([PortaListada(p, *ultimas.get(p.id, (None, None))) for p in portas])


def ultima_alteracao_da_porta(sessao: Session, porta_id: uuid.UUID) -> tuple[str | None, object | None]:
    """(quem, quando) da última alteração da porta, de qualquer época; (None, None) se nunca foi alterada."""
    return _alteracoes(sessao, _ultima_alteracao(), [str(porta_id)]).get(porta_id, (None, None))


def ultima_alteracao_do_equipamento(sessao: Session, equipamento: EquipamentoRede) -> dict:
    """A alteração mais recente entre todas as portas do equipamento: quem, quando e qual porta (vazio se nenhuma foi alterada)."""
    from datetime import datetime, timezone

    portas = {p.id: p for p in equipamento.portas}
    ultimas = _alteracoes(sessao, _ultima_alteracao(), [str(i) for i in portas]) if portas else {}
    if not ultimas:
        return {}
    instante = lambda q: q.replace(tzinfo=q.tzinfo or timezone.utc) if isinstance(q, datetime) else datetime.min.replace(tzinfo=timezone.utc)  # noqa: E731
    porta_id, (autor, quando) = max(ultimas.items(), key=lambda par: instante(par[1][1]))
    porta = portas[porta_id]
    return {"alterado_por": autor, "alterado_em": quando, "alterado_porta_id": porta_id, "alterado_porta": porta.nome or str(porta.numero_logico)}


def indicadores(sessao: Session) -> dict[str, int]:
    """Números dos cards do topo da Rede (os mesmos critérios das listas)."""
    from datetime import timedelta

    from app.core.banco import agora_utc

    ultimas = _alteracoes(sessao, _ultima_alteracao(agora_utc() - timedelta(days=DIAS_PORTAS_ALTERADAS)))
    # Só as portas que ainda existem (a de um equipamento excluído fica na auditoria, mas não conta)
    alteradas = sessao.scalar(select(func.count()).select_from(PortaRede).where(PortaRede.id.in_(list(ultimas)))) if ultimas else 0
    return {"portas_alteradas": alteradas or 0, "portas_patch_um_lado": len(_patch_um_lado(sessao))}


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
    """Configuração lógica da porta: modo, VLANs, IP, velocidade, duplex, situação e a observação.

    Regras (decisões do usuário):
    - A descrição não é digitada: é gerada pelo sistema a partir do "Ligado a" (ver `atualizar_descricao`).
    - Porta **sem nada ligado** fica desligada ou desativada e em branco: só a situação e a observação mudam; não há configuração.
    - Porta **com algo ligado** fica sempre ligada (`up`); outro status dá `409 porta_com_equipamento`.
    - Por modo (ver `MODOS_PORTA`): VLANs com tag só em trunk, hybrid e dinâmicas; VLANs sem tag (além da PVID) só em hybrid; VLAN de voz em
      access, hybrid e dinâmicas; a roteada não tem VLAN nenhuma e é a única com IP da interface (validado).
    """
    porta = obter_porta(sessao, porta_id)
    observacao = (d.observacao or "").strip()
    if d.status is not None and d.status not in STATUS_PORTA:
        raise ErroRede("Status inválido (up, down ou desativada).")
    if not ligacoes_da_porta(sessao, porta.id):
        # Sem nada ligado: só desligada ou desativada, e a porta fica em branco (a configuração só existe depois de ligar algo)
        if d.status not in STATUS_SEM_USO:
            raise ErroRede(f"A porta {_nome_porta(porta)} não tem nada em \"Ligado a\": ela fica desligada ou desativada. "
                           "Ligue o equipamento antes de configurar.", 409, "porta_sem_ligacao")
        limpar_porta(sessao, porta, d.status)
        porta.observacao = observacao
        sessao.flush()
        return porta
    if d.status != "up":
        raise ErroRede(f"A porta {_nome_porta(porta)} tem um equipamento ligado e fica \"ligada\": retire o equipamento antes de mudar o status.",
                       409, "porta_com_equipamento")
    if porta.equipamento.tipo in TIPOS_PASSIVOS:
        return _alterar_porta_passiva(sessao, porta, d, observacao)
    _aplicar_configuracao(sessao, porta, d)
    porta.observacao = observacao
    sessao.flush()
    return porta


def _aplicar_configuracao(sessao: Session, porta: PortaRede, d: DadosPorta) -> None:
    """Confere e grava a configuração lógica de uma porta ligada de switch/roteador (usada na tela da porta e no cadastro do equipamento)."""
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
    pedidas = ids | sem_tag | {v for v in (d.vlan_nativa_id, d.vlan_voz_id) if v}
    if pedidas - {v.id for v in sessao.scalars(select(VlanRede).where(VlanRede.id.in_(pedidas)))}:
        raise ErroRede("VLAN não encontrada.")
    porta.modo, porta.vlan_nativa_id = d.modo, d.vlan_nativa_id
    porta.vlan_voz_id, porta.ip_interface = d.vlan_voz_id, ip
    porta.velocidade_mbps, porta.duplex, porta.status = d.velocidade_mbps, d.duplex, "up"
    # A nativa/PVID já passa sem tag: não se repete na lista
    porta.vlans = [PortaVlanRede(vlan_id=v, com_tag=True) for v in sorted(ids - {d.vlan_nativa_id}, key=str)] + \
                  [PortaVlanRede(vlan_id=v, com_tag=False) for v in sorted(sem_tag - {d.vlan_nativa_id}, key=str)]
    sessao.flush()


# Situações em que a porta não está em uso (sem nada ligado): ela fica em branco (ver `limpar_porta`)
STATUS_SEM_USO = ("down", "desativada")


def limpar_porta(sessao: Session, porta: PortaRede, status: str) -> PortaRede:
    """Deixa a porta "em branco" (decisão do usuário): sem nada ligado, ela fica desligada ou desativada.

    A descrição volta a "Desligado", o modo volta para access sem VLAN nenhuma (nativa, voz, com e sem tag) e saem IP, velocidade e duplex.
    Ficam a observação (anotação de quem cadastrou) e o que vem do switch e não é configuração (MAC, contadores de erro, última mudança).
    Porta com algo em "Ligado a" (em qualquer lado) é recusada: primeiro se retira o que está ligado.
    """
    if ligacoes_da_porta(sessao, porta.id):
        raise ErroRede(f"A porta {_nome_porta(porta)} tem um equipamento ligado e fica \"ligada\": retire o equipamento antes de mudar o status.",
                       409, "porta_com_equipamento")
    porta.descricao, porta.modo, porta.vlan_nativa_id, porta.vlan_voz_id = DESCRICAO_DESLIGADA, "access", None, None
    porta.ip_interface, porta.velocidade_mbps, porta.duplex, porta.status = "", None, None, status
    porta.vlans = []
    sessao.flush()
    return porta


def _alterar_porta_passiva(sessao: Session, porta: PortaRede, d: DadosPorta, observacao: str) -> PortaRede:
    """Porta de patch panel ligada: só a observação muda (o patch panel não tem parte lógica e a situação é "ligada").

    Pedido com modo diferente de access, VLAN, IP, velocidade ou duplex é recusado.
    """
    if d.modo != "access" or d.vlan_nativa_id or d.vlan_voz_id or d.vlans_tag or d.vlans_sem_tag or d.ip_interface.strip() or d.velocidade_mbps or d.duplex:
        raise ErroRede("Porta de patch panel não tem configuração lógica (modo, VLAN, IP, velocidade ou duplex): só a observação.")
    porta.observacao, porta.status = observacao, "up"
    sessao.flush()
    return porta


# ---------------------------------------------------------------------------------------------
# VLANs
# ---------------------------------------------------------------------------------------------

def listar_vlans(sessao: Session) -> list[VlanRede]:
    return list(sessao.scalars(select(VlanRede).order_by(VlanRede.numero)))


def salvar_vlan(sessao: Session, vlan_id: uuid.UUID | None, numero: int, nome: str, descricao: str, cor_indice: int | None = None) -> VlanRede:
    if not 1 <= numero <= 4094:
        raise ErroRede("O número da VLAN vai de 1 a 4094.")
    repetida = sessao.scalar(select(VlanRede).where(VlanRede.numero == numero))
    if repetida is not None and repetida.id != vlan_id:
        raise ErroRede(f"A VLAN {numero} já existe.", 409, "duplicado")
    vlan = sessao.get(VlanRede, vlan_id) if vlan_id else VlanRede()
    if vlan is None:
        raise _nao_encontrado("VLAN")
    vlan.numero, vlan.nome, vlan.descricao = numero, (nome.strip() or f"VLAN {numero}")[:120], descricao.strip()
    # Cor como a dos marcadores das Tarefas: escolhida (0–11), mantida se não veio, ou sorteada (1–11) na criação
    if cor_indice is not None:
        if not 0 <= cor_indice <= 11:
            raise ErroRede("Cor inválida (de 0 a 11).")
        vlan.cor_indice = cor_indice
    elif vlan_id is None:
        import random

        vlan.cor_indice = random.randint(1, 11)
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

def ligacoes_da_porta(sessao: Session, porta_id: uuid.UUID) -> list[ConexaoRede]:
    """Todas as ligações da porta (no patch panel, até duas: a do fundo e a da frente)."""
    return list(sessao.scalars(select(ConexaoRede).where(or_(ConexaoRede.porta_a_id == porta_id, ConexaoRede.porta_b_id == porta_id))))


def conexao_da_porta(sessao: Session, porta_id: uuid.UUID, lado: str | None = None) -> ConexaoRede | None:
    """A ligação da porta naquele lado (`lado` vazio nas portas que não são de patch panel)."""
    for c in ligacoes_da_porta(sessao, porta_id):
        if (c.porta_a_id == porta_id and (c.lado_a or None) == lado) or (c.porta_b_id == porta_id and (c.lado_b or None) == lado):
            return c
    return None


def lado_na_conexao(c: ConexaoRede, porta_id: uuid.UUID) -> str | None:
    """O lado da porta nesta ligação (vazio fora do patch panel)."""
    return c.lado_a if c.porta_a_id == porta_id else c.lado_b


def outra_ponta(c: ConexaoRede, porta_id: uuid.UUID, lado: str | None = None) -> tuple[uuid.UUID | None, str | None]:
    """A outra ponta da ligação vista da porta (e lado) informados: (id da outra porta ou None se é bem/descrição, lado dela)."""
    if c.porta_a_id == porta_id and (c.lado_a or None) == lado:
        return c.porta_b_id, c.lado_b
    return c.porta_a_id, c.lado_a


def oposto(lado: str | None) -> str | None:
    """O outro lado da porta do patch panel: o cabo que entra pelo fundo sai pela frente, e vice-versa."""
    return {"fundo": "frente", "frente": "fundo"}.get(lado or "")


def _eh_patch(porta: PortaRede) -> bool:
    return porta.equipamento.tipo in TIPOS_PASSIVOS


def _conferir_lado(porta: PortaRede, lado: str | None) -> str | None:
    """Porta de patch panel precisa do lado (fundo ou frente); nas demais, o lado não existe."""
    if _eh_patch(porta):
        if lado not in LADOS_PATCH:
            raise ErroRede(f"Diga o lado da porta {_nome_porta(porta)}: Terminal Punch Down ou Conector RJ45.")
        return lado
    if lado:
        raise ErroRede(f"Só a porta de patch panel tem Terminal Punch Down e Conector RJ45; a porta {_nome_porta(porta)} tem uma ligação só.")
    return None


# Nome que aparece para cada lado da porta do patch panel (decisão do usuário, 13/11/2026). O valor gravado continua "fundo"/"frente".
ROTULOS_LADO = {"frente": "Conector RJ45", "fundo": "Terminal Punch Down"}


def rotulo_lado(lado: str | None) -> str:
    """Nome do lado para o usuário: "frente" vira "Conector RJ45" e "fundo", "Terminal Punch Down"."""
    return ROTULOS_LADO.get(lado or "", lado or "")


def _rotulo_lado(lado: str | None) -> str:
    """Sufixo com o lado, para o texto da ponta: " (Conector RJ45)"."""
    return f" ({rotulo_lado(lado)})" if lado else ""


def texto_da_ponta(sessao: Session, c: ConexaoRede, porta_id: uuid.UUID, lado: str | None = None) -> str:
    """O que está na outra ponta da ligação, em texto: "SPI-SWAC-05A · 1/0/6", "PP-5A · 6 (Terminal Punch Down)", "Impressora (chapa 0123)" ou a descrição."""
    outra_id, outro_lado = outra_ponta(c, porta_id, lado)
    if outra_id is not None:
        outra = obter_porta(sessao, outra_id)
        return f"{outra.equipamento.nome} · {outra.nome or outra.numero_logico}{_rotulo_lado(outro_lado)}"
    return _texto_dispositivo(sessao, c.bem_id, c.descricao)[0]


def descrever_porta(sessao: Session, porta: PortaRede) -> str:
    """Descrição gerada pelo sistema (decisão do usuário): o que está ligado na porta; "Desligado" se não houver nada.

    No patch panel, os dois lados: "Terminal Punch Down: VOIP 08395 · Conector RJ45: SPI-SWAC-05A · 1/0/6" (lado vazio não aparece).
    """
    ligacoes = ligacoes_da_porta(sessao, porta.id)
    if not ligacoes:
        return DESCRICAO_DESLIGADA
    if _eh_patch(porta):
        por_lado = {lado_na_conexao(c, porta.id): c for c in ligacoes}
        partes = [f"{rotulo_lado(lado)}: {texto_da_ponta(sessao, por_lado[lado], porta.id, lado)}" for lado in LADOS_PATCH if lado in por_lado]
        return " · ".join(partes)[:250]
    return texto_da_ponta(sessao, ligacoes[0], porta.id)[:250]


def atualizar_descricao(sessao: Session, porta: PortaRede) -> None:
    porta.descricao = descrever_porta(sessao, porta)


@dataclass
class Fio:
    """Um cabo seguido de ponta a ponta, atravessando os patch panels (entra por um lado da porta e sai pelo outro).

    `saltos`: as portas de patch panel atravessadas, em ordem, com o lado por onde o fio entra e o lado por onde sai.
    `fim`: a porta (fora de patch panel) onde o fio termina; vazio quando termina num bem/descrição (`ligacao_final`) ou num lado sem nada (`aberto`).
    """
    saltos: list[tuple[PortaRede, str | None, str | None]]
    fim: PortaRede | None = None
    ligacao_final: ConexaoRede | None = None
    aberto: bool = False


def seguir_fio(sessao: Session, porta: PortaRede, lado: str | None, ignorar=None) -> Fio:
    """Sai da porta (pelo lado informado) e segue o cabo até a ponta que não é patch panel.

    `ignorar(c)`: ligação que conta como inexistente (para simular um "desligar" ou a exclusão de um equipamento).
    """
    saltos: list[tuple[PortaRede, str | None, str | None]] = []
    atual, lado_atual = porta, lado
    vistos: set[tuple[uuid.UUID, str | None]] = set()
    while True:
        c = conexao_da_porta(sessao, atual.id, lado_atual)
        if c is None or (ignorar is not None and ignorar(c)):
            return Fio(saltos, aberto=True)
        outra_id, outro_lado = outra_ponta(c, atual.id, lado_atual)
        if outra_id is None:
            return Fio(saltos, ligacao_final=c)
        outra = obter_porta(sessao, outra_id)
        if not _eh_patch(outra):
            return Fio(saltos, fim=outra, ligacao_final=c)
        # Patch panel: o cabo atravessa a porta e continua pelo outro lado dela
        if (outra.id, outro_lado) in vistos or len(saltos) > 20:
            return Fio(saltos, aberto=True)
        vistos.add((outra.id, outro_lado))
        saltos.append((outra, outro_lado, oposto(outro_lado)))
        atual, lado_atual = outra, oposto(outro_lado)


# Posição na hierarquia (decisão do usuário): Core primário → Core secundário → Distribuição → Acesso → os demais (AP, roteador, outro)
def posto(e: EquipamentoRede) -> int | None:
    if e.tipo in TIPOS_PASSIVOS:
        return None
    if e.tipo == "switch":
        return {"core_primario": 0, "core_secundario": 1, "distribuicao": 2, "acesso": 3}.get(e.funcao or "", 4)
    return 4


def pode_ficar_acima(de: EquipamentoRede, acima: EquipamentoRede) -> bool:
    """Se `acima` pode ser o equipamento de cima de `de` (cadastro em cadeia, decisão do usuário).

    Core secundário → core primário; distribuição → um core; acesso → distribuição ou core; access point, roteador e "outro" → switch de acesso.
    """
    if acima.tipo != "switch":
        return False
    if de.tipo == "switch":
        permitidas = {"core_secundario": ("core_primario",), "distribuicao": FUNCOES_CORE, "acesso": FUNCOES_CORE + ("distribuicao",)}
        return acima.funcao in permitidas.get(de.funcao or "", ())
    return de.tipo not in TIPOS_PASSIVOS and acima.funcao == "acesso"


ROTULO_ACIMA = {"core_secundario": "o core primário", "distribuicao": "um core", "acesso": "uma distribuição ou um core"}


def rotulo_acima(e: EquipamentoRede) -> str:
    return ROTULO_ACIMA.get(e.funcao or "", "um switch de acesso") if e.tipo == "switch" else "um switch de acesso"


def ligacoes_para_cima(sessao: Session, e: EquipamentoRede, ignorar=None) -> int:
    """Quantos cabos ligam o equipamento a quem pode estar acima dele (direto ou atravessando patch panels)."""
    total = 0
    for p in e.portas:
        if conexao_da_porta(sessao, p.id) is None:
            continue
        fio = seguir_fio(sessao, p, None, ignorar)
        if fio.fim is not None and pode_ficar_acima(e, fio.fim.equipamento):
            total += 1
    return total


def _conferir_cadeia(sessao: Session, equipamentos: set[uuid.UUID], ignorar) -> None:
    """Recusa a mudança que deixaria algum destes equipamentos sem nenhum cabo para quem está acima dele (decisão do usuário).

    O core primário e o patch panel não precisam de ninguém acima. Equipamento que já estava sem ligação para cima não trava nada.
    """
    for eid in equipamentos:
        e = sessao.get(EquipamentoRede, eid)
        if e is None or posto(e) in (None, 0):
            continue
        if ligacoes_para_cima(sessao, e) > 0 and ligacoes_para_cima(sessao, e, ignorar) == 0:
            raise ErroRede(f"O {e.nome} ficaria sem nenhum cabo para {rotulo_acima(e)}. Ligue antes outro cabo para cima e depois desligue este.",
                           409, "unica_ligacao_para_cima")


def _equipamentos_nas_pontas(sessao: Session, c: ConexaoRede) -> set[uuid.UUID]:
    """Os equipamentos (fora patch panel) nas duas pontas do cabo de que esta ligação faz parte."""
    achados: set[uuid.UUID] = set()
    for porta_id, lado in ((c.porta_a_id, c.lado_a), (c.porta_b_id, c.lado_b)):
        if porta_id is None:
            continue
        porta = obter_porta(sessao, porta_id)
        if not _eh_patch(porta):
            achados.add(porta.equipamento_id)
            continue
        # Ponta num patch panel: o cabo continua pelo outro lado daquela porta
        fio = seguir_fio(sessao, porta, oposto(lado))
        if fio.fim is not None:
            achados.add(fio.fim.equipamento_id)
    return achados


def conectar(sessao: Session, porta_id: uuid.UUID, outra_porta_id: uuid.UUID | None, bem_id: uuid.UUID | None, descricao: str,
             lado: str | None = None, outro_lado: str | None = None) -> ConexaoRede:
    """Liga a porta (no patch panel, um dos lados) a outra porta, a um bem do Patrimônio ou só a uma descrição (ex.: "Telefone da recepção").

    Regras (decisões do usuário): cada porta tem uma ligação; a porta de patch panel tem duas, uma no fundo e outra na frente (o lado é
    obrigatório nela e não existe nas demais). Porta ou lado já ligado no SGI é recusado (`409 porta_ocupada`). As pontas passam a "ligada" e
    a descrição de cada uma é gerada pelo sistema.
    """
    porta = obter_porta(sessao, porta_id)
    lado = _conferir_lado(porta, lado)
    if outra_porta_id is None and bem_id is None and not descricao.strip():
        raise ErroRede("Diga o que está ligado: outra porta, um bem do Patrimônio ou uma descrição.")
    outra = obter_porta(sessao, outra_porta_id) if outra_porta_id is not None else None
    if outra is not None:
        if outra.id == porta.id:
            raise ErroRede("Uma porta não se liga nela mesma.")
        outro_lado = _conferir_lado(outra, outro_lado)
    else:
        outro_lado = None
    if bem_id is not None and sessao.get(Bem, bem_id) is None:
        raise ErroRede("Bem do Patrimônio não encontrado.")
    for p, l in ((porta, lado), (outra, outro_lado)):
        if p is not None and conexao_da_porta(sessao, p.id, l) is not None:
            onde = f"O {l} da porta" if l else "A porta"
            raise ErroRede(f"{onde} {_nome_porta(p)} já está ligado: desligue antes de ligar de novo." if l else
                           f"{onde} {_nome_porta(p)} já está ligada: desligue antes de ligar de novo.", 409, "porta_ocupada")
    conexao = ConexaoRede(porta_a_id=porta.id, lado_a=lado, porta_b_id=outra_porta_id, lado_b=outro_lado, bem_id=bem_id,
                          descricao=descricao.strip()[:250])
    sessao.add(conexao)
    sessao.flush()
    # Ligou algo: as pontas ficam "ligadas" e a descrição de cada uma diz o que está do outro lado
    for p in (porta, outra):
        if p is not None:
            p.status = "up"
            atualizar_descricao(sessao, p)
    sessao.flush()
    return conexao


def trocar_ligacao(sessao: Session, porta_id: uuid.UUID, lado: str | None, outra_porta_id: uuid.UUID | None, bem_id: uuid.UUID | None,
                   descricao: str, outro_lado: str | None = None, religar_antigo: bool = False) -> ConexaoRede:
    """Troca o que está ligado na porta (no patch panel, naquele lado) por outra coisa, **numa operação só** (decisão do usuário).

    Serve para mudar o caminho sem passar por um momento "sem cabo para cima" (o desligar recusaria). Com `religar_antigo`, quando o novo
    destino é um lado de patch panel e o antigo era outra porta, o **outro lado** daquela porta do patch panel é ligado no destino antigo: é
    o caso de pôr um patch panel no meio de um cabo que já existia (ex.: CORE 48 ↔ DIST 1 vira CORE 48 ↔ PP 5 frente, PP 5 fundo ↔ DIST 1).
    A configuração da porta fica como está. Ao fim, ninguém pode ter ficado sem cabo para quem está acima (`409 unica_ligacao_para_cima`;
    a rota desfaz tudo). A ponta antiga que ficar sem nada ligado passa a "desligada" e em branco.
    """
    from sqlalchemy import delete

    porta = obter_porta(sessao, porta_id)
    lado = _conferir_lado(porta, lado)
    antiga = conexao_da_porta(sessao, porta.id, lado)
    if antiga is None:
        raise ErroRede("Esta porta não está ligada a nada: use Ligar." if not lado else f"O {lado} desta porta não está ligado a nada: use Ligar.",
                       404, "nao_encontrado")
    # Quem pode ser afetado e quantos cabos para cima cada um tinha antes
    afetados = _equipamentos_nas_pontas(sessao, antiga) | {porta.equipamento_id}
    antes = {eid: ligacoes_para_cima(sessao, e) for eid in afetados if (e := sessao.get(EquipamentoRede, eid)) is not None and posto(e) not in (None, 0)}
    antigo_id, antigo_lado = outra_ponta(antiga, porta.id, lado)
    sessao.execute(delete(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id == antiga.id))
    sessao.delete(antiga)
    sessao.flush()
    nova = conectar(sessao, porta.id, outra_porta_id, bem_id, descricao, lado, outro_lado)
    if religar_antigo and antigo_id is not None and outra_porta_id is not None:
        destino = obter_porta(sessao, outra_porta_id)
        if not _eh_patch(destino):
            raise ErroRede("Religar o destino antigo só vale quando o novo destino é um lado de patch panel.")
        conectar(sessao, destino.id, antigo_id, None, "", oposto(outro_lado), antigo_lado)
    # A cadeia continua inteira? (quem tinha cabo para cima continua tendo)
    for eid, total in antes.items():
        e = sessao.get(EquipamentoRede, eid)
        if total > 0 and ligacoes_para_cima(sessao, e) == 0:
            raise ErroRede(f"Com a troca, o {e.nome} ficaria sem nenhum cabo para {rotulo_acima(e)}. Confira o novo destino "
                           "(no patch panel, o outro lado precisa levar até lá).", 409, "unica_ligacao_para_cima")
    # A ponta antiga que ficou sem nada passa a desligada e em branco; a que ainda tem algo só refaz a descrição
    if antigo_id is not None:
        velha = obter_porta(sessao, antigo_id)
        if ligacoes_da_porta(sessao, velha.id):
            atualizar_descricao(sessao, velha)
        else:
            limpar_porta(sessao, velha, "down")
    atualizar_descricao(sessao, porta)
    sessao.flush()
    return nova


def dispositivos_atras(sessao: Session, conexao_id: uuid.UUID) -> list[DispositivoAtrasRede]:
    return list(sessao.scalars(select(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id == conexao_id).order_by(DispositivoAtrasRede.ordem)))


def adicionar_atras(sessao: Session, porta_id: uuid.UUID, bem_id: uuid.UUID | None, descricao: str, lado: str | None = None) -> DispositivoAtrasRede:
    """Põe um dispositivo **atrás** do último da porta (ex.: o PC ligado no telefone IP). Só vale quando a porta (ou o lado, no patch panel) já
    tem um dispositivo (bem ou descrição): atrás de outra porta de rede não há "dispositivo atrás" (aí é a próxima ligação daquela porta)."""
    porta = obter_porta(sessao, porta_id)
    conexao = conexao_da_porta(sessao, porta_id, _conferir_lado(porta, lado))
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
    alvo = sessao.get(DispositivoAtrasRede, dispositivo_id)
    conexao = sessao.get(ConexaoRede, alvo.conexao_id) if alvo is not None else None
    if conexao is None or porta_id not in (conexao.porta_a_id, conexao.porta_b_id):
        raise _nao_encontrado("Dispositivo")
    sessao.delete(alvo)
    sessao.flush()
    for i, d in enumerate(dispositivos_atras(sessao, conexao.id), 1):
        d.ordem = i
    sessao.flush()


def _nome_porta(p: PortaRede) -> str:
    return f"{p.nome or p.numero_logico} do {p.equipamento.nome}"


def desconectar(sessao: Session, porta_id: uuid.UUID, lado: str | None = None) -> None:
    """Desfaz a ligação da porta (no patch panel, a de um lado).

    Regras (decisões do usuário):
    - Não deixa nenhum equipamento sem cabo para quem está acima dele (`409 unica_ligacao_para_cima`): para trocar a porta, liga-se a nova antes.
    - A porta que fica sem nada ligado (no patch panel, sem nada nos dois lados) passa a "desligada" e fica em branco; a que ainda tem o outro
      lado ligado continua "ligada", só com a descrição refeita.
    """
    from sqlalchemy import delete

    porta = obter_porta(sessao, porta_id)
    conexao = conexao_da_porta(sessao, porta_id, _conferir_lado(porta, lado))
    if conexao is None:
        raise ErroRede("Esta porta não está ligada a nada." if not lado else f"O {lado} desta porta não está ligado a nada.", 404, "nao_encontrado")
    _conferir_cadeia(sessao, _equipamentos_nas_pontas(sessao, conexao), lambda c: c.id == conexao.id)
    pontas = [obter_porta(sessao, i) for i in (conexao.porta_a_id, conexao.porta_b_id) if i is not None]
    # Desligar tira também os dispositivos que estavam atrás do primeiro
    sessao.execute(delete(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id == conexao.id))
    sessao.delete(conexao)
    sessao.flush()
    for p in pontas:
        if ligacoes_da_porta(sessao, p.id):
            atualizar_descricao(sessao, p)
        else:
            limpar_porta(sessao, p, "down")


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
    """Ponto → porta do patch panel → (ligações) porta do switch. Segue no máximo 4 saltos, sem repetir porta."""
    caminho: list[PortaRede] = []
    atual = sessao.get(PortaRede, ponto.porta_id) if ponto.porta_id else None
    while atual is not None and atual not in caminho and len(caminho) < 4:
        caminho.append(atual)
        # A próxima porta é a de qualquer ligação desta que ainda não está no caminho
        seguintes = [sessao.get(PortaRede, outra) for c in ligacoes_da_porta(sessao, atual.id)
                     for outra in (c.porta_b_id if c.porta_a_id == atual.id else c.porta_a_id,) if outra]
        atual = next((x for x in seguintes if x is not None and x not in caminho), None)
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
    - Grupo sem core marcado: uma raiz só, o equipamento da camada mais alta (distribuição antes de acesso); patch panel nunca é a raiz.
      No empate de camada, o que tem mais switches/roteadores vizinhos; depois menos patch panels, pontos e bens, o roteador e o nome.
    - **Organizada por camadas (decisão do usuário):** Core → Distribuição → Acesso → demais. Um equipamento só fica embaixo de alguém de
      camada mais alta; o patch panel aparece entre duas camadas quando o cabo passa por ele, e no fim do ramo quando só serve aquele switch.
      Quem só se liga a equipamentos da mesma camada ou de baixo (cadastro incompleto) fica embaixo do primeiro a que se liga.
    - `raiz_id` (o campo "Núcleo" da tela) só muda a visão: põe aquele equipamento como raiz única do grupo dele.
    - Cada equipamento aparece uma vez na árvore.
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

    def nivel(i: uuid.UUID) -> int:
        # Camada do equipamento: core 0, distribuição 1, acesso 2, os demais (sem função, AP, roteador sem função) 3; patch panel não tem camada própria
        return camada.get(equipamentos[i].funcao or "", 3)

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
            # Sem core: o topo é o equipamento ativo (não patch panel) da camada mais alta do grupo; patch panel nunca é o topo
            ativos = [i for i in grupo if equipamentos[i].tipo != "patch_panel"] or grupo
            topo = [min(ativos, key=lambda i: (nivel(i), peso_de_raiz(i)))]
        pai: dict[uuid.UUID, uuid.UUID | None] = dict.fromkeys(topo)
        # Camada "efetiva" de quem já está na árvore: a do equipamento; o patch panel herda a de quem está acima dele (o cabo passa por ele)
        efetivo: dict[uuid.UUID, int] = {i: nivel(i) for i in topo}

        def pendurar(v: uuid.UUID, atual: uuid.UUID) -> None:
            """Põe `v` embaixo de `atual`, com o cabo entre os dois."""
            pai[v] = atual
            efetivo[v] = efetivo[atual] if equipamentos[v].tipo == "patch_panel" else nivel(v)
            cabos = vizinhos[v][atual]
            filho = nos[v]
            filho.porta_acima, filho.porta_no_pai, filho.cabos_com_pai = cabos[0][0], cabos[0][1], len(cabos)
            filho.porta_acima_id, filho.porta_no_pai_id = cabos[0][2], cabos[0][3]
            nos[atual].filhos.append(filho)

        # 1ª passada, por camadas (decisão do usuário): Core → Distribuição → Acesso → demais, com o patch panel entre duas camadas só quando o
        # cabo passa por ele. Quem está numa camada mais alta é expandido antes; um equipamento só fica embaixo de alguém de camada mais alta
        # (ou de um patch panel que vem de uma camada mais alta). Patch panel fica embaixo de quem chegar nele primeiro.
        # Na mesma camada, vale a ordem de chegada (os cores na ordem deles, com o Primário primeiro), como numa busca em largura
        chegada = count()
        fila = [(efetivo[i], next(chegada), i) for i in topo]
        heapq.heapify(fila)
        while fila:
            _, _, atual = heapq.heappop(fila)
            for v in sorted(vizinhos[atual], key=ordem):
                if v in pai or (equipamentos[v].tipo != "patch_panel" and nivel(v) <= efetivo[atual]):
                    continue
                pendurar(v, atual)
                heapq.heappush(fila, (efetivo[v], next(chegada), v))
        # 2ª passada: quem sobrou só se liga a alguém da mesma camada ou de baixo (cadastro incompleto, ex.: switch de acesso empilhado, ou
        # o "Núcleo" escolhido na tela): fica embaixo do primeiro a que se liga, na ordem da busca em largura, como antes
        fila_restante = [i for i in pai]
        while fila_restante:
            atual = fila_restante.pop(0)
            for v in sorted(vizinhos[atual], key=ordem):
                if v not in pai:
                    pendurar(v, atual)
                    fila_restante.append(v)
            # Os filhos ficam sempre em ordem de camada, quem veio de cada passada
            nos[atual].filhos.sort(key=lambda f: ordem(f.equipamento.id))
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
    # No patch panel, o lado da porta por onde o cabo entra e por onde sai (fundo ou frente)
    lado_entrada: str | None = None
    lado_saida: str | None = None


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


def _rotulo_ponta(p: PortaRede, lado: str | None) -> str:
    return f"{_nome_curto(p)}{_rotulo_lado(lado)}"


def caminho_da_porta(sessao: Session, porta_id: uuid.UUID) -> CaminhoPorta:
    """Do topo (o core do grupo, pela mesma árvore da topologia) até a porta e o que está nela, **seguindo o fio daquela porta**.

    - A subida até o equipamento é a da topologia (cada equipamento embaixo do primeiro a que se liga).
    - Porta de patch panel (decisão do usuário): cada porta é um fio independente, com um cabo no fundo e outro na frente. O caminho sobe pelo
      lado que leva ao equipamento mais alto, atravessa a porta e desce pelo outro lado. Se nenhum lado leva a um switch, o caminho para no
      patch panel com o aviso (nunca usa o cabo de outra porta do mesmo patch panel).
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

    def subir(eid: uuid.UUID) -> list[EtapaCaminho]:
        cadeia: list[EtapaCaminho] = []
        atual: uuid.UUID | None = eid
        saida_de_baixo: uuid.UUID | None = None
        while atual is not None and len(cadeia) < 30:
            de_cima, cabo, entrada, no_pai = pai.get(atual, (None, "", None, None))
            e = sessao.get(EquipamentoRede, atual)
            cadeia.append(EtapaCaminho("equipamento", e.nome, cabo, e, entrada if de_cima else None, saida_de_baixo))
            saida_de_baixo = no_pai
            atual = de_cima
        return list(reversed(cadeia))

    def ancestrais(eid: uuid.UUID) -> set[uuid.UUID]:
        vistos: set[uuid.UUID] = set()
        atual = pai.get(eid, (None,))[0]
        while atual is not None and atual not in vistos:
            vistos.add(atual)
            atual = pai.get(atual, (None,))[0]
        return vistos

    dispositivos: list[tuple[str, uuid.UUID | None]] = []
    cabo_dispositivos = ""

    def descer(etapas: list[EtapaCaminho], fio: Fio, de: PortaRede, de_lado: str | None) -> None:
        """Acrescenta o que vem depois de sair pela porta `de`: os patch panels atravessados e a ponta (equipamento ou dispositivos)."""
        nonlocal cabo_dispositivos
        anterior, anterior_lado = de, de_lado
        for pp, entra, sai in fio.saltos:
            etapas.append(EtapaCaminho("equipamento", pp.equipamento.nome, f"{_rotulo_ponta(anterior, anterior_lado)} ↔ {_rotulo_ponta(pp, entra)}",
                                       pp.equipamento, pp.id, pp.id, entra, sai))
            anterior, anterior_lado = pp, sai
        if fio.fim is not None:
            etapas.append(EtapaCaminho("equipamento", fio.fim.equipamento.nome, f"{_rotulo_ponta(anterior, anterior_lado)} ↔ {_nome_curto(fio.fim)}",
                                       fio.fim.equipamento, fio.fim.id))
        elif fio.ligacao_final is not None:
            c = fio.ligacao_final
            dispositivos.append(_texto_dispositivo(sessao, c.bem_id, c.descricao))
            dispositivos.extend(_texto_dispositivo(sessao, d.bem_id, d.descricao) for d in dispositivos_atras(sessao, c.id))
            cabo_dispositivos = _rotulo_ponta(anterior, anterior_lado)

    aviso = ""
    if not _eh_patch(porta):
        etapas = subir(equipamento.id)
        if conexao_da_porta(sessao, porta.id) is not None:
            fio = seguir_fio(sessao, porta, None)
            cima = fio.fim is not None and (fio.fim.equipamento_id in ancestrais(equipamento.id) or pode_ficar_acima(equipamento, fio.fim.equipamento))
            if not cima:
                # O fio desce desta porta: patch panels no caminho e o que está na ponta
                etapas[-1].porta_saida_id = porta.id
                descer(etapas, fio, porta, None)
    else:
        # Patch panel: o lado de cima é o que leva ao equipamento mais alto da hierarquia
        fios = {lado: seguir_fio(sessao, porta, lado) for lado in LADOS_PATCH if conexao_da_porta(sessao, porta.id, lado) is not None}
        com_switch = [(posto(f.fim.equipamento), lado) for lado, f in fios.items() if f.fim is not None and posto(f.fim.equipamento) is not None]
        if com_switch:
            lado_cima = min(com_switch)[1]
            fio_cima = fios[lado_cima]
            etapas = subir(fio_cima.fim.equipamento_id)
            etapas[-1].porta_saida_id = fio_cima.fim.id
            anterior, anterior_lado = fio_cima.fim, None
            # Volta pelos patch panels do lado de cima até chegar nesta porta
            for pp, entra, sai in reversed(fio_cima.saltos):
                etapas.append(EtapaCaminho("equipamento", pp.equipamento.nome, f"{_rotulo_ponta(anterior, anterior_lado)} ↔ {_rotulo_ponta(pp, sai)}",
                                           pp.equipamento, pp.id, pp.id, sai, entra))
                anterior, anterior_lado = pp, entra
            lado_baixo = oposto(lado_cima)
            etapas.append(EtapaCaminho("equipamento", equipamento.nome, f"{_rotulo_ponta(anterior, anterior_lado)} ↔ {_rotulo_ponta(porta, lado_cima)}",
                                       equipamento, porta.id, porta.id, lado_cima, lado_baixo))
            if lado_baixo in fios:
                descer(etapas, fios[lado_baixo], porta, lado_baixo)
        else:
            etapas = [EtapaCaminho("equipamento", equipamento.nome, "", equipamento, None, porta.id)]
            for lado, f in fios.items():
                descer(etapas, f, porta, lado)
            aviso = f"A porta {_nome_curto(porta)} do {equipamento.nome} não chega a nenhum switch: falta ligar o outro lado dela."
        ponto = sessao.scalar(select(PontoRede).where(PontoRede.porta_id == porta.id))
        if ponto and not dispositivos and (etapas[-1].equipamento is None or etapas[-1].equipamento.id == equipamento.id):
            etapas.append(EtapaCaminho("ponto", ponto.codigo, _nome_curto(porta)))
    # Fora de qualquer árvore = sem cabo para outro equipamento
    if not aviso and etapas[0].equipamento is not None and etapas[0].equipamento.id not in pai:
        aviso = f"O {equipamento.nome} não tem cabo para outro equipamento: o caminho não chega ao core."
    return CaminhoPorta(etapas, dispositivos, cabo_dispositivos, aviso)


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


def portas_do_bem(sessao: Session, bem_id: uuid.UUID) -> list[tuple[PortaRede, ConexaoRede, DispositivoAtrasRede | None]]:
    """Portas em que o bem está ligado (normalmente uma): direto (dispositivo `None`) ou atrás do primeiro dispositivo daquela ligação (o
    registro dele atrás, para tirar só ele). A ligação traz o lado, quando a porta é de patch panel."""
    if sessao.get(Bem, bem_id) is None:
        raise _nao_encontrado("Bem")
    diretas = [(sessao.get(PortaRede, c.porta_a_id), c, None) for c in sessao.scalars(select(ConexaoRede).where(ConexaoRede.bem_id == bem_id))]
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
