# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras do atendimento dos Chamados: abrir, listar, ver, assumir, responder e solucionar.
"""Atendimento dos Chamados (marco 1: abrir um chamado de ponta a ponta).

Fluxo: o solicitante abre o chamado escolhendo a categoria → o chamado nasce com o **setor responsável** da categoria (próprio
ou herdado), a prioridade da categoria e os prazos dos SLAs em horas úteis → quem atende vê na fila, assume, responde e soluciona.
**Solucionado é o fim** do chamado (não existe "fechado").

Avisos (sempre sem commit, gravam junto da operação):
- quando um **setor** é responsável ou solicitante, **todos os membros ativos** recebem no sino **e por e-mail** (`forcar_email=True`);
- o solicitante recebe quando alguém assume, quando a equipe responde em público e quando o chamado é resolvido;
- o responsável recebe quando o solicitante responde (sem responsável, o setor recebe pelo canal que cada um escolheu).

Texto rico: o HTML passa pelo sanitizador do SGI e **toda imagem colada em base64 vira anexo** antes de gravar (no GLPI 11.0.8,
imagem base64 grande no texto quebrava o envio de e-mails: issue #25265).
"""

import base64
import binascii
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time as hora
from io import BytesIO

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FUSO_SAO_PAULO, agora_utc, em_sao_paulo
from app.models.chamados import (
    PRIORIDADES, STATUS_ABERTOS, STATUS_EM_ATENDIMENTO, STATUS_NOVO, STATUS_PENDENTE, STATUS_SOLUCIONADO, TIPOS, AcompanhamentoChamado, AnexoChamado,
    AtorChamado, CategoriaChamados, Chamado, SlaChamados, SolucaoChamado, ValorCampoChamado,
)
from app.models.patrimonio import Localizacao
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import notificacoes, servico_anexos
from app.services.chamados import acesso, campos as campos_adicionais, motor_sla, parametros
from app.services.chamados import tempo_real  # registra os ganchos que avisam as telas ao vivo (e marca ações gravadas por UPDATE direto)
from app.services.chamados.acesso import Alcance, Papeis
from app.services.servico_auditoria import auditar
from app.services.tarefas.descricao import sanitizar_descricao, texto_da_descricao

CATEGORIA_ANEXO = "chamados"
# Limites da abertura e das respostas
MAXIMO_ANEXOS = 10
MAXIMO_TEXTO = 50_000
# Imagem colada no editor: <img src="data:image/png;base64,....">
_IMAGEM_BASE64 = re.compile(r"<img\b[^>]*?src=[\"']data:image/(png|jpe?g);base64,([A-Za-z0-9+/=\s]+)[\"'][^>]*>", re.IGNORECASE)
EXTENSOES_IMAGEM = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg"}


class ErroChamado(Exception):
    """Regra do atendimento violada (vira `{"detalhe", "codigo"}` na rota)."""

    def __init__(self, mensagem: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo


@dataclass
class Arquivo:
    """Arquivo recebido (nome original e conteúdo)."""
    nome: str
    conteudo: bytes


@dataclass
class RegrasFixas:
    """Fila, prioridade e SLAs que vêm de fora do assunto (chamados do RH: cada serviço tem os seus). O assunto vira só o "lugar" do chamado."""
    setor_id: int
    prioridade: str = "normal"
    sla_tto_id: uuid.UUID | None = None
    sla_ttr_id: uuid.UUID | None = None


@dataclass
class DadosAbertura:
    titulo: str
    descricao: str
    categoria_id: uuid.UUID
    tipo: str = "incidente"
    impedindo_trabalho: bool | None = None
    setor_solicitante_id: int | None = None
    relacionado_id: uuid.UUID | None = None
    localizacao_id: uuid.UUID | None = None
    rede_porta_id: uuid.UUID | None = None
    rede_ponto_id: uuid.UUID | None = None
    campos: dict[str, object] = field(default_factory=dict)
    arquivos: list[Arquivo] = field(default_factory=list)
    # Aberto pelo sistema (RH) com regras próprias: o assunto não precisa estar no catálogo e não dita fila, prioridade nem prazos
    fixas: RegrasFixas | None = None


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else ""


def _link(chamado: Chamado) -> str:
    return f"/chamados/{chamado.numero}"


# ---------------------------------------------------------------------------------------------
# Texto rico e anexos
# ---------------------------------------------------------------------------------------------

def preparar_texto(html: str, obrigatorio: bool = True) -> tuple[str, list[Arquivo]]:
    """Sanitiza o HTML e tira dele as imagens coladas em base64, que viram arquivos (anexos) à parte."""
    imagens: list[Arquivo] = []

    def extrair(achado: re.Match) -> str:
        try:
            dados = base64.b64decode(re.sub(r"\s", "", achado.group(2)), validate=True)
        except (binascii.Error, ValueError):
            return ""
        imagens.append(Arquivo(f"imagem-colada-{len(imagens) + 1}{EXTENSOES_IMAGEM[achado.group(1).lower()]}", dados))
        return ""

    sem_imagens = _IMAGEM_BASE64.sub(extrair, html or "")
    if len(sem_imagens) > MAXIMO_TEXTO:
        raise ErroChamado("O texto passou do tamanho máximo. Envie o conteúdo longo como anexo.")
    try:
        limpo = sanitizar_descricao(sem_imagens)
    except ValueError as erro:
        raise ErroChamado(str(erro)) from erro
    if obrigatorio and not texto_da_descricao(limpo).strip() and not imagens:
        raise ErroChamado("Escreva o texto antes de enviar.")
    return limpo, imagens


def _guardar_anexos(sessao: Session, chamado: Chamado, arquivos: list[Arquivo], autor: Usuario, alvo_tipo: str, alvo_id: uuid.UUID | None, privado: bool) -> None:
    if len(arquivos) > MAXIMO_ANEXOS:
        raise ErroChamado(f"Envie no máximo {MAXIMO_ANEXOS} arquivos de cada vez.")
    for arquivo in arquivos:
        try:
            anexo = servico_anexos.guardar_arquivo(sessao, BytesIO(arquivo.conteudo), arquivo.nome, CATEGORIA_ANEXO, autor.id)
        except servico_anexos.ErroAnexo as erro:
            raise ErroChamado(f"{arquivo.nome}: {erro}") from erro
        sessao.flush()
        chamado.anexos.append(AnexoChamado(anexo_id=anexo.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id, privado=privado))


# ---------------------------------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------------------------------

def membros_ativos(sessao: Session, setor_id: int | None) -> list[int]:
    """Membros ativos de um setor (para os avisos que vão ao setor inteiro)."""
    if setor_id is None:
        return []
    return list(sessao.scalars(
        select(MembroSetor.usuario_id).join(Usuario, Usuario.id == MembroSetor.usuario_id).where(MembroSetor.setor_id == setor_id, Usuario.ativo.is_(True))
    ))


def _avisar(sessao: Session, ids: list[int], assunto: str, corpo: str, chamado: Chamado, sufixo: str, evento: str, autor: Usuario, *,
            forcar_email: bool = False, prioridade: str = "normal") -> None:
    notificacoes.notificar(
        sessao, ids, assunto[:300], corpo, chave=f"chamados:{chamado.id}:{sufixo}", categoria="atribuicao", prioridade=prioridade,
        link=_link(chamado), autor=autor, evento=evento, forcar_email=forcar_email,
    )


def _titulo_aviso(chamado: Chamado, sigilosa: bool) -> str:
    return f"#{chamado.numero}" if sigilosa else f"#{chamado.numero} {chamado.titulo}"


# ---------------------------------------------------------------------------------------------
# Catálogo e abertura
# ---------------------------------------------------------------------------------------------

def catalogo(sessao: Session, p: Papeis, usuario: Usuario | None = None) -> list[CategoriaChamados]:
    """Categorias que a pessoa pode escolher na abertura: ativas (com os ancestrais), com setor responsável e que ela pode escolher.

    "Quem pode escolher" vale para a categoria e para cada ancestral: com setores escolhidos, só os membros deles (e dos setores abaixo);
    sem setores, qualquer pessoa ou só quem atende (`visivel_solicitante`). Controle total vê todas. Sem `usuario` (troca de assunto feita
    por quem atende), a restrição por setor não se aplica.
    """
    todas = parametros.listar_categorias(sessao)
    ativas = {c.id for c in todas if c.ativa}
    membro = acesso.setores_do_usuario(sessao, usuario) if usuario is not None and not p.administrar else set()
    cache_setores: dict[uuid.UUID, set[int]] = {}

    def pode(x: CategoriaChamados) -> bool:
        if p.administrar:
            return True
        if x.setores_permitidos and usuario is not None:
            if x.id not in cache_setores:
                cache_setores[x.id] = acesso._descendentes(sessao, {v.setor_id for v in x.setores_permitidos})
            return bool(membro & cache_setores[x.id])
        return p.atender or x.visivel_solicitante

    escolhiveis = []
    for c in todas:
        caminho_ativo = c.ativa and all(a in ativas for a in _ancestrais_ids(c))
        visivel = all(pode(x) for x in _linha(c))
        if caminho_ativo and visivel and parametros.efetiva(c).setor_id is not None:
            escolhiveis.append(c)
    return escolhiveis


def _linha(categoria: CategoriaChamados) -> list[CategoriaChamados]:
    """A categoria e os ancestrais dela."""
    linha, atual = [], categoria
    while atual is not None:
        linha.append(atual)
        atual = atual.pai
    return linha


def _ancestrais_ids(categoria: CategoriaChamados) -> list[uuid.UUID]:
    return [c.id for c in _linha(categoria)[1:]]


def _subir_prioridade(prioridade: str) -> str:
    """Um nível acima (urgente é o teto)."""
    return PRIORIDADES[min(PRIORIDADES.index(prioridade) + 1, len(PRIORIDADES) - 1)]


def _prazo(sessao: Session, sla_id: uuid.UUID | None, inicio, feriados) -> tuple[uuid.UUID | None, object]:
    if sla_id is None:
        return None, None
    sla = sessao.get(SlaChamados, sla_id)
    if sla is None or not sla.ativo:
        return None, None
    return sla.id, motor_sla.prazo_do_sla(inicio, sla.tempo, sla.unidade, parametros.faixas_do_expediente(sla.expediente), feriados)


def abrir(sessao: Session, usuario: Usuario, p: Papeis, dados: DadosAbertura) -> Chamado:
    """Abre o chamado, calcula os prazos e avisa o setor responsável (e o setor solicitante, se houver). Sem commit."""
    if not p.abrir:
        raise ErroChamado("Você não tem acesso para abrir chamados.", 403, "acesso_negado")
    # "A partir de": com a data marcada e ainda no futuro, só quem administra abre aqui (testes e treinamento); os demais usam o GLPI até lá
    from app.services.chamados import configuracao

    inicio = configuracao.inicio_atendimento(sessao)
    if inicio is not None and not configuracao.atendimento_aberto(sessao) and not p.administrar:
        raise ErroChamado(f"Os chamados passam a ser abertos aqui a partir de {inicio.strftime('%d/%m/%Y')}. Até lá, abra pelo GLPI.", 409, "antes_do_inicio")
    titulo = " ".join(dados.titulo.split())
    if not 3 <= len(titulo) <= 250:
        raise ErroChamado("O título precisa ter de 3 a 250 caracteres.")
    if dados.tipo not in TIPOS:
        raise ErroChamado("Tipo inválido (incidente ou requisição).")
    categoria = sessao.get(CategoriaChamados, dados.categoria_id)
    if categoria is None or (dados.fixas is None and categoria not in catalogo(sessao, p, usuario)):
        raise ErroChamado("Escolha uma categoria disponível.", 400, "categoria_invalida")
    if dados.fixas is None and ((dados.tipo == "incidente" and not categoria.permite_incidente) or (dados.tipo == "requisicao" and not categoria.permite_requisicao)):
        raise ErroChamado("Esta categoria não aceita este tipo de chamado.", 400, "categoria_invalida")
    if dados.setor_solicitante_id is not None and dados.setor_solicitante_id not in acesso.setores_do_usuario(sessao, usuario):
        raise ErroChamado("Você só pode abrir chamado em nome de um setor de que é membro.", 403, "acesso_negado")
    descricao, imagens = preparar_texto(dados.descricao)
    respostas = campos_adicionais.validar_respostas(categoria, dados.campos)
    if dados.relacionado_id is not None:
        relacionado = sessao.get(Chamado, dados.relacionado_id)
        # Só um chamado do próprio solicitante (decisão do usuário): o de outra pessoa nem é revelado
        if relacionado is None or relacionado.solicitante_id != usuario.id or relacionado.excluido_em is not None:
            raise ErroChamado("Escolha um chamado relacionado entre os seus.", 400, "relacionado_invalido")
    if dados.localizacao_id is not None:
        local = sessao.get(Localizacao, dados.localizacao_id)
        if local is None or not local.ativo or local.tipo != "sala":
            raise ErroChamado("Escolha uma sala ativa do Patrimônio.", 400, "local_invalido")
    # Porta ou ponto de rede (plano de face): só precisa existir; quem abre pelo ponto lê o código na tomada
    from app.models.rede import PontoRede, PortaRede
    if dados.rede_porta_id is not None and sessao.get(PortaRede, dados.rede_porta_id) is None:
        raise ErroChamado("Porta de rede não encontrada.", 400, "porta_invalida")
    if dados.rede_ponto_id is not None and sessao.get(PontoRede, dados.rede_ponto_id) is None:
        raise ErroChamado("Ponto de rede não encontrado.", 400, "ponto_invalido")
    efetiva = parametros.efetiva(categoria)
    if dados.fixas is not None:
        # Regras do serviço (RH) por cima das do assunto fixo
        from dataclasses import replace

        f = dados.fixas
        efetiva = replace(efetiva, setor_id=f.setor_id, prioridade_padrao=f.prioridade, sla_tto_id=f.sla_tto_id, sla_ttr_id=f.sla_ttr_id, responsavel_id=None)
    setor = sessao.get(Setor, efetiva.setor_id)
    if setor is None or not setor.ativo:
        raise ErroChamado("O setor responsável por esta categoria está inativo. Avise a administração dos Chamados.", 409, "categoria_sem_setor")

    agora = agora_utc()
    feriados = parametros.feriados_do_sla(sessao)
    prioridade, origem = efetiva.prioridade_padrao, "categoria"
    if dados.impedindo_trabalho and categoria.perguntar_impedindo:
        prioridade, origem = _subir_prioridade(prioridade), "solicitante"
    sla_tto_id, prazo_tto = _prazo(sessao, efetiva.sla_tto_id, agora, feriados)
    sla_ttr_id, prazo_ttr = _prazo(sessao, efetiva.sla_ttr_id, agora, feriados)
    chamado = Chamado(
        numero=parametros.reservar_numero(sessao), tipo=dados.tipo, titulo=titulo, descricao=descricao,
        status_base=STATUS_EM_ATENDIMENTO if efetiva.responsavel_id else STATUS_NOVO,
        prioridade=prioridade, prioridade_origem=origem, impedindo_trabalho=dados.impedindo_trabalho if categoria.perguntar_impedindo else None,
        categoria_id=categoria.id, categoria_itil_id=efetiva.categoria_itil_id, setor_id=setor.id, setor_nome=setor.nome, responsavel_id=efetiva.responsavel_id,
        solicitante_id=usuario.id, setor_solicitante_id=dados.setor_solicitante_id, aberto_por_id=usuario.id,
        sla_tto_id=sla_tto_id, prazo_tto=prazo_tto, sla_ttr_id=sla_ttr_id, prazo_ttr=prazo_ttr, aberto_em=agora,
        relacionado_id=dados.relacionado_id, localizacao_id=dados.localizacao_id, rede_porta_id=dados.rede_porta_id, rede_ponto_id=dados.rede_ponto_id,
    )
    sessao.add(chamado)
    sessao.flush()
    for campo_id, valor in respostas.items():
        chamado.valores.append(ValorCampoChamado(campo_id=campo_id, valor=valor))
    _guardar_anexos(sessao, chamado, imagens + dados.arquivos, usuario, "chamado", None, False)
    auditar(sessao, usuario.login, "chamados.abrir", f"#{chamado.numero}", titulo, autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)

    titulo_aviso = _titulo_aviso(chamado, efetiva.sigilosa)
    corpo = f"{_nome(usuario)} abriu o chamado {titulo_aviso} ({categoria.caminho})."
    _avisar(sessao, membros_ativos(sessao, setor.id), f"Novo chamado para {setor.nome}: {titulo_aviso}", corpo, chamado, "novo",
            "chamados.novo", usuario, forcar_email=True, prioridade="alta" if prioridade in ("alta", "urgente") else "normal")
    if efetiva.responsavel_id:
        _avisar(sessao, [efetiva.responsavel_id], f"Chamado atribuído a você: {titulo_aviso}", corpo, chamado, "novo", "chamados.novo", usuario, forcar_email=True)
    if dados.setor_solicitante_id:
        setor_sol = sessao.get(Setor, dados.setor_solicitante_id)
        _avisar(sessao, membros_ativos(sessao, dados.setor_solicitante_id), f"Chamado aberto em nome de {setor_sol.nome if setor_sol else 'seu setor'}: {titulo_aviso}",
                corpo, chamado, "setor-solicitante:abertura", "chamados.setor_solicitante", usuario, forcar_email=True)
    return chamado


# ---------------------------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------------------------

FILTROS_FILA = ("abertos", "meus", "setor", "novos", "sem_responsavel", "solucionados", "todos")
FILTROS_MEUS = ("abertos", "aguardando", "resolvidos", "todos")


def _base_consulta():
    return select(Chamado).where(Chamado.excluido_em.is_(None)).options(selectinload(Chamado.categoria))


def _aplicar_busca(consulta, busca: str):
    termo = busca.strip().lstrip("#")
    if not termo:
        return consulta
    if termo.isdigit():
        return consulta.where(or_(Chamado.numero == int(termo), Chamado.titulo.ilike(f"%{termo}%")))
    solicitantes = select(Usuario.id).where(or_(Usuario.nome_completo.ilike(f"%{termo}%"), Usuario.login.ilike(f"%{termo}%")))
    return consulta.where(or_(Chamado.titulo.ilike(f"%{termo}%"), Chamado.solicitante_id.in_(solicitantes)))


def _paginar(sessao: Session, consulta, pagina: int, tamanho: int) -> tuple[list[Chamado], int]:
    total = sessao.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    itens = list(sessao.scalars(consulta.offset((pagina - 1) * tamanho).limit(tamanho)))
    return itens, total


def _ordenar_fila(consulta):
    """Mais urgente primeiro, depois o prazo de solução que vence antes (sem prazo por último), depois o mais antigo."""
    peso = case({"urgente": 0, "alta": 1, "normal": 2, "baixa": 3}, value=Chamado.prioridade, else_=4)
    return consulta.order_by(peso, Chamado.prazo_ttr.is_(None), Chamado.prazo_ttr, Chamado.aberto_em)


ORDENS = ("numero", "titulo", "solicitante", "setor", "situacao", "prioridade", "prazo", "aberto_em")


def _ordenar_por_coluna(consulta, ordem: str, direcao: str):
    """Ordem escolhida clicando no cabeçalho da coluna. O número do chamado desempata (mais recente primeiro)."""
    from sqlalchemy.orm import aliased

    if ordem == "solicitante":
        pessoa = aliased(Usuario)
        consulta = consulta.outerjoin(pessoa, pessoa.id == Chamado.solicitante_id)
        chave = func.lower(func.coalesce(pessoa.nome_completo, pessoa.login, Chamado.solicitante_externo, ""))
    else:
        chave = {
            "numero": Chamado.numero,
            "titulo": func.lower(Chamado.titulo),
            "setor": func.lower(Chamado.setor_nome),
            # Na ordem do andamento: novo, em atendimento, pendente, em aprovação, resolvido
            "situacao": case({s: i for i, s in enumerate(("novo", "em_atendimento", "pendente", "em_aprovacao", "solucionado"))}, value=Chamado.status_base, else_=9),
            "prioridade": case({"baixa": 0, "normal": 1, "alta": 2, "urgente": 3}, value=Chamado.prioridade, else_=1),
            "prazo": Chamado.prazo_ttr,
            "aberto_em": Chamado.aberto_em,
        }[ordem]
    coluna = chave.desc() if direcao == "desc" else chave.asc()
    # Sem prazo vai sempre para o fim, nos dois sentidos
    extras = [Chamado.prazo_ttr.is_(None)] if ordem == "prazo" else []
    return consulta.order_by(None).order_by(*extras, coluna, Chamado.numero.desc())


@dataclass
class Recorte:
    """Recorte vindo de um clique nos Relatórios: reproduz o que aquele número contou. Datas inclusivas (dias de São Paulo).

    - `escopo_relatorio` + `relatorio_setor_id`: os mesmos setores do relatório (`qualidade.escopo`);
    - `aberto_de/ate`: abertura no intervalo; `resolvido_de/ate`: solução no intervalo (com `resolvido_por`, a solução registrada por essa
      pessoa, mesmo que o chamado tenha sido reaberto depois; sem ela, chamado solucionado);
    - `assumido_por` + `assumido_de/ate`: chamado com a pessoa, assumido no intervalo;
    - `categoria_id`, `nota` (satisfação 1–5) e `reabertos` (já teve "Não resolveu").
    """
    escopo_relatorio: bool = False
    relatorio_setor_id: int | None = None
    aberto_de: date | None = None
    aberto_ate: date | None = None
    resolvido_de: date | None = None
    resolvido_ate: date | None = None
    resolvido_por: int | None = None
    assumido_por: int | None = None
    assumido_de: date | None = None
    assumido_ate: date | None = None
    categoria_id: uuid.UUID | None = None
    nota: int | None = None
    reabertos: bool = False


def _intervalo(coluna, de: date | None, ate: date | None) -> list:
    """Condições de um intervalo de dias (inclusivo) em horário de São Paulo sobre uma coluna de data e hora."""
    from datetime import UTC, timedelta
    condicoes = []
    if de:
        condicoes.append(coluna >= datetime.combine(de, hora(0), FUSO_SAO_PAULO).astimezone(UTC))
    if ate:
        condicoes.append(coluna < datetime.combine(ate + timedelta(days=1), hora(0), FUSO_SAO_PAULO).astimezone(UTC))
    return condicoes


def _aplicar_recorte(sessao: Session, usuario: Usuario, p: Papeis, consulta, r: Recorte):
    from app.models.chamados import SatisfacaoChamado
    from app.services.chamados import qualidade

    if r.escopo_relatorio:
        setores, _ = qualidade.escopo(sessao, usuario, p, r.relatorio_setor_id)
        if setores is not None:
            consulta = consulta.where(Chamado.setor_id.in_(setores or {-1}))
    consulta = consulta.where(*_intervalo(Chamado.aberto_em, r.aberto_de, r.aberto_ate))
    if r.resolvido_por is not None:
        solucoes = select(SolucaoChamado.chamado_id).where(SolucaoChamado.autor_id == r.resolvido_por,
                                                           *_intervalo(SolucaoChamado.criado_em, r.resolvido_de, r.resolvido_ate))
        consulta = consulta.where(Chamado.id.in_(solucoes))
    elif r.resolvido_de or r.resolvido_ate:
        consulta = consulta.where(Chamado.status_base == STATUS_SOLUCIONADO, *_intervalo(Chamado.solucionado_em, r.resolvido_de, r.resolvido_ate))
    if r.assumido_por is not None:
        consulta = consulta.where(Chamado.responsavel_id == r.assumido_por, *_intervalo(Chamado.tomado_em, r.assumido_de, r.assumido_ate))
    if r.categoria_id is not None:
        consulta = consulta.where(Chamado.categoria_id == r.categoria_id)
    if r.nota is not None:
        consulta = consulta.where(Chamado.id.in_(select(SatisfacaoChamado.chamado_id).where(SatisfacaoChamado.nota == r.nota)))
    if r.reabertos:
        consulta = consulta.where(Chamado.reaberturas > 0)
    return consulta


def fila(sessao: Session, usuario: Usuario, p: Papeis, filtro: str, busca: str, setor_id: int | None, pagina: int, tamanho: int,
         ordem: str | None = None, direcao: str = "asc", recorte: Recorte | None = None) -> tuple[list[Chamado], int]:
    """Fila de quem atende, já limitada ao que a pessoa enxerga. `recorte`: o clique num número dos Relatórios."""
    if not p.atender:
        raise ErroChamado("A fila é de quem atende chamados.", 403, "acesso_negado")
    a = acesso.alcance(sessao, usuario, p)
    consulta = _base_consulta().where(acesso.filtro_visibilidade(a))
    if filtro == "meus":
        consulta = consulta.where(Chamado.responsavel_id == usuario.id, Chamado.status_base.in_(STATUS_ABERTOS))
    elif filtro == "setor":
        consulta = consulta.where(Chamado.setor_id.in_(a.setores_atendidos or {-1}), Chamado.status_base.in_(STATUS_ABERTOS))
    elif filtro == "novos":
        consulta = consulta.where(Chamado.status_base == STATUS_NOVO)
    elif filtro == "sem_itil":
        # Pendentes de classificação ITIL (abertos ou resolvidos), para o técnico ir classificando
        consulta = consulta.where(Chamado.categoria_itil_id.is_(None))
    elif filtro == "sem_responsavel":
        consulta = consulta.where(Chamado.responsavel_id.is_(None), Chamado.status_base.in_(STATUS_ABERTOS))
    elif filtro == "solucionados":
        consulta = consulta.where(Chamado.status_base == STATUS_SOLUCIONADO)
    elif filtro == "abertos":
        consulta = consulta.where(Chamado.status_base.in_(STATUS_ABERTOS))
    # O histórico importado do GLPI é só leitura: não entra nas listas de trabalho (aparece em "Resolvidos" e "Todos")
    if filtro not in ("solucionados", "todos"):
        consulta = consulta.where(Chamado.importado.is_(False))
    if setor_id is not None:
        consulta = consulta.where(Chamado.setor_id == setor_id)
    if recorte is not None:
        consulta = _aplicar_recorte(sessao, usuario, p, consulta, recorte)
    consulta = _ordenar_fila(_aplicar_busca(consulta, busca))
    if filtro == "solucionados":
        consulta = consulta.order_by(None).order_by(Chamado.solucionado_em.desc())
    if ordem:
        consulta = _ordenar_por_coluna(consulta, ordem, direcao)
    return _paginar(sessao, consulta, pagina, tamanho)


def meus(sessao: Session, usuario: Usuario, p: Papeis, filtro: str, busca: str, pagina: int, tamanho: int,
         ordem: str | None = None, direcao: str = "asc") -> tuple[list[Chamado], int]:
    """Chamados em que a pessoa é solicitante, que foram abertos em nome de um setor dela ou em que ela (ou um setor dela) está em cópia."""
    if not p.abrir:
        raise ErroChamado("Você não tem acesso aos Chamados.", 403, "acesso_negado")
    setores = acesso.setores_do_usuario(sessao, usuario)
    em_copia = select(AtorChamado.chamado_id).where(or_(AtorChamado.usuario_id == usuario.id, AtorChamado.setor_id.in_(setores or {-1})))
    proprios = or_(Chamado.solicitante_id == usuario.id, Chamado.setor_solicitante_id.in_(setores or {-1}), Chamado.id.in_(em_copia))
    consulta = _base_consulta().where(proprios)
    if filtro == "abertos":
        consulta = consulta.where(Chamado.status_base.in_(STATUS_ABERTOS))
    elif filtro == "aguardando":
        consulta = consulta.where(Chamado.status_base == "pendente")
    elif filtro == "resolvidos":
        consulta = consulta.where(Chamado.status_base == STATUS_SOLUCIONADO)
    consulta = _aplicar_busca(consulta, busca).order_by(Chamado.aberto_em.desc())
    if ordem:
        consulta = _ordenar_por_coluna(consulta, ordem, direcao)
    return _paginar(sessao, consulta, pagina, tamanho)


def obter(sessao: Session, usuario: Usuario, p: Papeis, numero: int) -> tuple[Chamado, Alcance]:
    """Chamado pelo número, se a pessoa o enxerga (404 para quem não enxerga, sem revelar que existe)."""
    if not p.abrir:
        raise ErroChamado("Você não tem acesso aos Chamados.", 403, "acesso_negado")
    chamado = sessao.scalar(
        select(Chamado).where(Chamado.numero == numero, Chamado.excluido_em.is_(None))
        .options(selectinload(Chamado.acompanhamentos), selectinload(Chamado.solucoes), selectinload(Chamado.anexos).selectinload(AnexoChamado.anexo),
                 selectinload(Chamado.categoria), selectinload(Chamado.atores), selectinload(Chamado.tarefas), selectinload(Chamado.validacoes),
                 selectinload(Chamado.valores).selectinload(ValorCampoChamado.campo))
    )
    a = acesso.alcance(sessao, usuario, p)
    if chamado is None or not acesso.ve(a, chamado):
        raise ErroChamado("Chamado não encontrado.", 404, "nao_encontrado")
    return chamado, a


# ---------------------------------------------------------------------------------------------
# Atendimento
# ---------------------------------------------------------------------------------------------

def _exigir_aberto(chamado: Chamado) -> None:
    if chamado.importado:
        raise ErroChamado("Chamado importado do GLPI: somente leitura.", 409, "chamado_encerrado")
    if chamado.status_base == STATUS_SOLUCIONADO:
        raise ErroChamado("Este chamado já foi resolvido.", 409, "chamado_encerrado")


def assumir(sessao: Session, usuario: Usuario, p: Papeis, numero: int, versao: int) -> Chamado:
    """Assume o chamado de forma atômica: se outra pessoa assumiu ou alterou antes, responde 409 e a tela recarrega."""
    chamado, a = obter(sessao, usuario, p, numero)
    if not acesso.atende(a, p, chamado):
        raise ErroChamado("Só quem atende o setor responsável assume este chamado.", 403, "acesso_negado")
    _exigir_aberto(chamado)
    if chamado.responsavel_id == usuario.id:
        return chamado
    agora = agora_utc()
    resultado = sessao.execute(
        update(Chamado).where(Chamado.id == chamado.id, Chamado.versao == versao, Chamado.responsavel_id.is_(None))
        .values(responsavel_id=usuario.id, status_base=STATUS_EM_ATENDIMENTO, tomado_em=func.coalesce(Chamado.tomado_em, agora),
                versao=Chamado.versao + 1, atualizado_em=agora)
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount != 1:
        raise ErroChamado("Este chamado foi alterado por outra pessoa (ou já tem responsável). Recarregue para ver como está.", 409, "chamado_alterado")
    sessao.refresh(chamado)
    # O UPDATE atômico não passa pelo histórico do ORM: o painel precisa saber que foi "assumido" para anunciar
    tempo_real.marcar_acao(sessao, chamado, "assumido")
    chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=usuario.id, texto=f"{_nome(usuario)} assumiu o chamado.", automatico=True))
    auditar(sessao, usuario.login, "chamados.assumir", f"#{chamado.numero}", autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    if chamado.solicitante_id:
        _avisar(sessao, [chamado.solicitante_id], f"Seu chamado #{chamado.numero} está em atendimento",
                f"{_nome(usuario)} está cuidando do seu chamado \"{chamado.titulo}\".", chamado, f"assumido:{usuario.id}", "chamados.assumido", usuario)
    return chamado


def responder(sessao: Session, usuario: Usuario, p: Papeis, numero: int, texto: str, privado: bool, arquivos: list[Arquivo]) -> AcompanhamentoChamado:
    """Acompanhamento na linha do tempo. O solicitante só escreve em público; a primeira resposta de quem atende cumpre o prazo de atendimento.
    Quem é do setor responsável e responde um chamado ainda sem responsável vira o responsável (como se tivesse assumido)."""
    chamado, a = obter(sessao, usuario, p, numero)
    _exigir_aberto(chamado)
    atendente = acesso.atende(a, p, chamado)
    if privado and not atendente:
        raise ErroChamado("Só a equipe que atende escreve mensagens privadas.", 403, "acesso_negado")
    html, imagens = preparar_texto(texto)
    agora = agora_utc()
    acompanhamento = AcompanhamentoChamado(autor_id=usuario.id, texto=html, privado=privado, criado_em=agora)
    chamado.acompanhamentos.append(acompanhamento)
    if atendente and chamado.tomado_em is None and usuario.id != chamado.solicitante_id:
        chamado.tomado_em = agora
    # Quem é do setor responsável e responde um chamado sem responsável passa a ser o responsável (como "assumir"; o painel fala "assumido")
    if (atendente and chamado.responsavel_id is None and usuario.id != chamado.solicitante_id
            and sessao.get(MembroSetor, {"setor_id": chamado.setor_id, "usuario_id": usuario.id}) is not None):
        chamado.responsavel_id = usuario.id
        if chamado.status_base == STATUS_NOVO:
            chamado.status_base = STATUS_EM_ATENDIMENTO
        chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=usuario.id, texto=f"{_nome(usuario)} assumiu o chamado ao responder.", automatico=True,
                                                             criado_em=agora))
        tempo_real.marcar_acao(sessao, chamado, "assumido")
    # Pendente aguardando o solicitante: a resposta dele retoma o atendimento (e o relógio do prazo)
    if chamado.status_base == STATUS_PENDENTE and not privado and not atendente:
        retomar_relogio(sessao, chamado, agora)
        chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=usuario.id, texto="Atendimento retomado pela resposta do solicitante.", automatico=True,
                                                             criado_em=agora))
    chamado.versao += 1
    sessao.flush()
    _guardar_anexos(sessao, chamado, imagens + arquivos, usuario, "acompanhamento", acompanhamento.id, privado)
    if not privado:
        trecho = texto_da_descricao(html)[:300]
        if usuario.id == chamado.solicitante_id or not atendente:
            # O solicitante respondeu: avisa o responsável; sem responsável, o setor (pelo canal de cada um)
            ids = [chamado.responsavel_id] if chamado.responsavel_id else membros_ativos(sessao, chamado.setor_id)
            _avisar(sessao, ids, f"Resposta do solicitante no chamado #{chamado.numero}", f"{_nome(usuario)}: {trecho}", chamado,
                    f"acompanhamento:{acompanhamento.id}", "chamados.acompanhamento", usuario)
        elif chamado.solicitante_id:
            _avisar(sessao, [chamado.solicitante_id], f"Nova resposta no seu chamado #{chamado.numero}", f"{_nome(usuario)}: {trecho}", chamado,
                    f"acompanhamento:{acompanhamento.id}", "chamados.acompanhamento", usuario)
        _avisar(sessao, ids_em_copia(sessao, chamado), f"Nova resposta no chamado #{chamado.numero}", f"{_nome(usuario)}: {trecho}", chamado,
                f"acompanhamento:{acompanhamento.id}:copia", "chamados.acompanhamento", usuario)
    return acompanhamento


def solucionar(sessao: Session, usuario: Usuario, p: Papeis, numero: int, texto: str, arquivos: list[Arquivo]) -> SolucaoChamado:
    """Resolve o chamado (o fim): grava a solução, para o relógio, abre a janela do "Não resolveu" e avisa o solicitante."""
    chamado, a = obter(sessao, usuario, p, numero)
    if not acesso.atende(a, p, chamado):
        raise ErroChamado("Só quem atende o setor responsável resolve este chamado.", 403, "acesso_negado")
    _exigir_aberto(chamado)
    html, imagens = preparar_texto(texto)
    agora = agora_utc()
    solucao = SolucaoChamado(autor_id=usuario.id, texto=html, criado_em=agora)
    chamado.solucoes.append(solucao)
    chamado.status_base = STATUS_SOLUCIONADO
    chamado.solucionado_em = agora
    chamado.tomado_em = chamado.tomado_em or agora
    if chamado.responsavel_id is None:
        chamado.responsavel_id = usuario.id
    if chamado.espera_desde is not None:
        retomar_relogio(sessao, chamado, agora)
    chamado.reabrir_ate = _limite_reabertura(sessao, agora)
    chamado.versao += 1
    sessao.flush()
    # Pede a nota de satisfação ao solicitante (marco 6)
    from app.services.chamados import qualidade
    qualidade.pedir(sessao, chamado, agora)
    _guardar_anexos(sessao, chamado, imagens + arquivos, usuario, "solucao", solucao.id, False)
    auditar(sessao, usuario.login, "chamados.solucionar", f"#{chamado.numero}", autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    sigilosa = parametros.efetiva(chamado.categoria).sigilosa
    corpo = (f"{_nome(usuario)} resolveu o chamado {_titulo_aviso(chamado, sigilosa)}: {texto_da_descricao(html)[:300]}"
             " Dê uma nota ao atendimento na página do chamado.")
    if chamado.solicitante_id:
        _avisar(sessao, [chamado.solicitante_id], f"Chamado #{chamado.numero} resolvido", corpo, chamado, f"solucao:{solucao.id}", "chamados.solucionado", usuario)
    if chamado.setor_solicitante_id:
        _avisar(sessao, membros_ativos(sessao, chamado.setor_solicitante_id), f"Chamado #{chamado.numero} do seu setor resolvido", corpo, chamado,
                f"setor-solicitante:solucao:{solucao.id}", "chamados.setor_solicitante", usuario, forcar_email=True)
    _avisar(sessao, ids_em_copia(sessao, chamado), f"Chamado #{chamado.numero} resolvido", corpo, chamado, f"solucao:{solucao.id}:copia",
            "chamados.solucionado", usuario)
    return solucao


def _limite_reabertura(sessao: Session, agora) -> object:
    """Fim do prazo do "Não resolveu": N dias úteis (segunda a sexta, sem os feriados do RH), até o fim do dia."""
    dias = parametros.obter_inteiro(sessao, "dias_reabrir")
    semana = {d: [(hora(0), hora(23, 59))] for d in range(5)}
    dia = motor_sla.proximo_dia_util(em_sao_paulo(agora).date(), dias, semana, parametros.feriados_do_sla(sessao))
    return datetime.combine(dia, hora(23, 59, 59), FUSO_SAO_PAULO)


def anexo_do_chamado(sessao: Session, usuario: Usuario, p: Papeis, numero: int, anexo_id: uuid.UUID) -> AnexoChamado:
    """Anexo para download, se a pessoa vê o chamado (e, se o anexo for privado, se ela atende)."""
    chamado, a = obter(sessao, usuario, p, numero)
    vinculo = next((x for x in chamado.anexos if x.anexo_id == anexo_id), None)
    if vinculo is None or (vinculo.privado and not acesso.atende(a, p, chamado)):
        raise ErroChamado("Anexo não encontrado.", 404, "nao_encontrado")
    return vinculo


def nomes_de_usuarios(sessao: Session, ids: set[int]) -> dict[int, str]:
    """Nome de exibição de cada usuário (para a linha do tempo e as listas)."""
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))}


def ids_em_copia(sessao: Session, chamado: Chamado) -> list[int]:
    """Pessoas em cópia e membros ativos dos setores em cópia."""
    ids: set[int] = set()
    for ator in chamado.atores:
        if ator.usuario_id:
            ids.add(ator.usuario_id)
        elif ator.setor_id:
            ids.update(membros_ativos(sessao, ator.setor_id))
    return sorted(ids)


def faixas_do_sla(sessao: Session, sla_id: uuid.UUID | None):
    """Expediente do SLA (ou None se o chamado não tem SLA)."""
    sla = sessao.get(SlaChamados, sla_id) if sla_id else None
    return parametros.faixas_do_expediente(sla.expediente) if sla else None


def retomar_relogio(sessao: Session, chamado: Chamado, agora) -> None:
    """Fim da pausa: soma o tempo útil parado e empurra o prazo de solução pelo mesmo tanto. O status volta a "Em atendimento"
    (ou "Novo", se ninguém assumiu)."""
    if chamado.espera_desde is not None:
        faixas = faixas_do_sla(sessao, chamado.sla_ttr_id)
        if faixas and chamado.prazo_ttr is not None:
            feriados = parametros.feriados_do_sla(sessao)
            parado = motor_sla.minutos_uteis_entre(chamado.espera_desde, agora, faixas, feriados)
            chamado.espera_minutos_uteis += parado
            chamado.prazo_ttr = motor_sla.somar_minutos_uteis(chamado.prazo_ttr, parado, faixas, feriados)
        chamado.espera_desde = None
    if chamado.status_base == STATUS_PENDENTE:
        chamado.status_base = STATUS_EM_ATENDIMENTO if chamado.responsavel_id else STATUS_NOVO
