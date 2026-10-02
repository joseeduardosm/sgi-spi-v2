# Criado por José Eduardo Santana Martins
# Este arquivo serve para concentrar as regras do Módulo Notícias: permissões, fluxo editorial, capa, avisos e o portal.
"""Regras do Módulo Notícias.

**Permissões (recurso `noticias` da ACL):**
- `MODIFICACAO` = redator: escreve, edita os próprios rascunhos e devolvidas, envia para aprovação.
- `CONTROLE_TOTAL` = aprovador: aprova, devolve, publica direto, edita publicadas, arquiva e configura o portal.
- Sem nenhuma regra cadastrada no recurso, só o SuperRoot escreve (ninguém vira aprovador por acaso).

**Visibilidade:** a notícia aparece no portal quando está `aprovada` e `publicar_em` já passou; o agendamento não
depende de rotina. A rotina de 2 em 2 minutos (`processar_publicacoes`) só dispara os avisos das que acabaram de aparecer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.acl import NivelAcl
from app.models.anexo import Anexo
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.noticias import AnexoNoticia, AtalhoPortal, CategoriaNoticia, ConfiguracaoPortal, Noticia, RevisaoNoticia
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services import servico_acl, servico_anexos, servico_mensagens
from app.services.noticias import imagens
from app.services.noticias.sanitizacao import limpar_html, slug_de, texto_puro
from app.services.servico_auditoria import auditar

RECURSO = "noticias"
EDITAVEIS_REDATOR = ("rascunho", "devolvida")


class ErroNoticia(Exception):
    """Regra do módulo violada (vira {"detalhe", "codigo"} na rota)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido"):
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def _exigir(condicao: bool, detalhe: str) -> None:
    if not condicao:
        raise ErroNoticia(detalhe, 403, "sem_permissao")


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "—"


# ---------------------------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------------------------

def nivel(sessao: Session, usuario: Usuario | None) -> str | None:
    """Nível no recurso `noticias` (sem regras cadastradas, só o SuperRoot escreve)."""
    if usuario is None:
        return None
    if usuario.superusuario:
        return NivelAcl.CONTROLE_TOTAL
    if not servico_acl.possui_regras(sessao, RECURSO):
        return None
    return servico_acl.resolver_acesso(sessao, usuario, RECURSO)


def eh_redator(sessao: Session, usuario: Usuario) -> bool:
    return NivelAcl.posicao(nivel(sessao, usuario)) >= NivelAcl.posicao(NivelAcl.MODIFICACAO)


def eh_aprovador(sessao: Session, usuario: Usuario) -> bool:
    return nivel(sessao, usuario) == NivelAcl.CONTROLE_TOTAL


def aprovadores(sessao: Session) -> list[Usuario]:
    """Quem recebe o pedido de aprovação: CONTROLE_TOTAL em `noticias` e SuperRoot (ativos)."""
    return [u for u in sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))) if eh_aprovador(sessao, u)]


def pode_editar(sessao: Session, usuario: Usuario, noticia: Noticia) -> bool:
    if eh_aprovador(sessao, usuario):
        return noticia.situacao != "arquivada"
    return eh_redator(sessao, usuario) and noticia.autor_id == usuario.id and noticia.situacao in EDITAVEIS_REDATOR


def acoes(sessao: Session, usuario: Usuario, noticia: Noticia) -> list[str]:
    """Ações permitidas agora (a tela mostra só estas)."""
    aprovador, lista = eh_aprovador(sessao, usuario), []
    if pode_editar(sessao, usuario, noticia):
        lista.append("editar")
    if noticia.situacao in EDITAVEIS_REDATOR and (aprovador or noticia.autor_id == usuario.id) and eh_redator(sessao, usuario):
        lista.append("enviar_revisao")
    if aprovador and noticia.situacao in ("rascunho", "em_revisao", "devolvida"):
        lista += ["aprovar"] + (["devolver"] if noticia.situacao == "em_revisao" else [])
    if aprovador and noticia.situacao == "aprovada":
        lista.append("arquivar")
    if aprovador and noticia.situacao == "arquivada":
        lista.append("desarquivar")
    if (aprovador and noticia.situacao != "aprovada") or usuario.superusuario or (
            noticia.autor_id == usuario.id and noticia.situacao in EDITAVEIS_REDATOR):
        lista.append("excluir")
    return lista


# ---------------------------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------------------------

def _comparavel(valor: datetime | None) -> datetime | None:
    """Data com fuso (o SQLite dos testes devolve sem)."""
    from datetime import timezone
    if valor is None:
        return None
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


def visivel(noticia: Noticia, agora: datetime | None = None) -> bool:
    agora = agora or agora_utc()
    return noticia.situacao == "aprovada" and noticia.publicar_em is not None and _comparavel(noticia.publicar_em) <= agora


def _visiveis(agora: datetime):
    return select(Noticia).where(Noticia.situacao == "aprovada", Noticia.publicar_em <= agora)


def obter(sessao: Session, noticia_id) -> Noticia:
    noticia = sessao.get(Noticia, noticia_id)
    if noticia is None:
        raise ErroNoticia("Notícia não encontrada.", 404, "nao_encontrado")
    return noticia


def obter_publica(sessao: Session, slug: str, agora: datetime | None = None) -> Noticia:
    noticia = sessao.scalar(select(Noticia).where(Noticia.slug == slug))
    if noticia is None or not visivel(noticia, agora):
        raise ErroNoticia("Notícia não encontrada.", 404, "nao_encontrado")
    return noticia


def listar_publicas(sessao: Session, busca: str = "", categoria_id: int | None = None, ano: int | None = None, mes: int | None = None,
                    pagina: int = 1, tamanho: int = 12, agora: datetime | None = None) -> tuple[list[Noticia], int]:
    """Arquivo público: mais recentes primeiro, com busca (título, linha fina e corpo), categoria e mês."""
    agora = agora or agora_utc()
    consulta = _visiveis(agora)
    termo = busca.strip().lower()
    if termo:
        like = f"%{termo}%"
        consulta = consulta.where(or_(func.lower(Noticia.titulo).like(like), func.lower(Noticia.linha_fina).like(like),
                                      func.lower(Noticia.corpo_html).like(like)))
    if categoria_id:
        consulta = consulta.where(Noticia.categoria_id == categoria_id)
    if ano:
        consulta = consulta.where(extract("year", Noticia.publicar_em) == ano)
    if mes:
        consulta = consulta.where(extract("month", Noticia.publicar_em) == mes)
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = list(sessao.scalars(consulta.order_by(Noticia.publicar_em.desc()).offset((pagina - 1) * tamanho).limit(tamanho)))
    return itens, total


def leia_tambem(sessao: Session, noticia: Noticia, agora: datetime | None = None, limite: int = 3) -> list[Noticia]:
    """Outras notícias da mesma categoria (ou as mais recentes)."""
    agora = agora or agora_utc()
    base = _visiveis(agora).where(Noticia.id != noticia.id).order_by(Noticia.publicar_em.desc())
    lista = list(sessao.scalars(base.where(Noticia.categoria_id == noticia.categoria_id).limit(limite))) if noticia.categoria_id else []
    if len(lista) < limite:
        ids = {n.id for n in lista}
        lista += [n for n in sessao.scalars(base.limit(limite + len(ids))) if n.id not in ids][: limite - len(lista)]
    return lista


def configuracao(sessao: Session) -> ConfiguracaoPortal:
    config = sessao.get(ConfiguracaoPortal, 1)
    if config is None:
        config = ConfiguracaoPortal(id=1)
        sessao.add(config)
        sessao.flush()
    return config


@dataclass
class Portal:
    configuracao: ConfiguracaoPortal
    slides: list[Noticia] = field(default_factory=list)
    cartoes: list[Noticia] = field(default_factory=list)
    atalhos: list[AtalhoPortal] = field(default_factory=list)


def portal(sessao: Session, agora: datetime | None = None) -> Portal:
    """Página inicial: slider conforme a configuração, cartões sem repetir os slides e atalhos."""
    agora = agora or agora_utc()
    config = configuracao(sessao)
    recentes = list(sessao.scalars(_visiveis(agora).order_by(Noticia.publicar_em.desc()).limit(60)))
    em_destaque = [n for n in recentes if n.destaque_ate is None or _comparavel(n.destaque_ate) > agora]
    if config.criterio_slider == "curadoria":
        slides = sorted([n for n in em_destaque if n.ordem_slider is not None], key=lambda n: n.ordem_slider)
    else:
        slides = sorted(em_destaque, key=lambda n: (not n.fixada, -_comparavel(n.publicar_em).timestamp()))
    slides = slides[: config.quantidade_slides]
    usados = {n.id for n in slides}
    cartoes = [n for n in recentes if n.id not in usados][: config.quantidade_cartoes]
    atalhos = list(sessao.scalars(select(AtalhoPortal).where(AtalhoPortal.ativo.is_(True)).order_by(AtalhoPortal.ordem, AtalhoPortal.id))) \
        if config.exibir_atalhos else []
    return Portal(config, slides, cartoes, atalhos)


def gestao(sessao: Session, usuario: Usuario, situacao: str = "", busca: str = "") -> list[Noticia]:
    """Lista da gestão: aprovadores veem tudo; redatores veem as próprias e as já aprovadas."""
    _exigir(eh_redator(sessao, usuario), "Você não tem acesso à gestão de notícias.")
    consulta = select(Noticia)
    if not eh_aprovador(sessao, usuario):
        consulta = consulta.where(or_(Noticia.autor_id == usuario.id, Noticia.situacao.in_(("aprovada", "arquivada"))))
    if situacao:
        consulta = consulta.where(Noticia.situacao == situacao)
    if busca.strip():
        consulta = consulta.where(func.lower(Noticia.titulo).like(f"%{busca.strip().lower()}%"))
    return list(sessao.scalars(consulta.order_by(Noticia.atualizado_em.desc()).limit(500)))


def contagem_por_situacao(sessao: Session, usuario: Usuario) -> dict[str, int]:
    return {s: len(gestao(sessao, usuario, s)) for s in ("rascunho", "em_revisao", "aprovada", "devolvida", "arquivada")}


# ---------------------------------------------------------------------------------------------
# Edição
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosNoticia:
    titulo: str
    linha_fina: str = ""
    corpo_html: str = ""
    categoria_id: int | None = None
    publicar_em: datetime | None = None
    destaque_ate: datetime | None = None
    fixada: bool = False
    exige_ciencia: bool = False
    usuarios_aviso: list[int] = field(default_factory=list)
    setores_aviso: list[int] = field(default_factory=list)
    capa_alt: str = ""


def _slug_unico(sessao: Session, titulo: str, ignorar=None) -> str:
    base = slug_de(titulo)
    candidato, n = base, 2
    while True:
        existente = sessao.scalar(select(Noticia.id).where(Noticia.slug == candidato))
        if existente is None or existente == ignorar:
            return candidato
        candidato, n = f"{base}-{n}", n + 1


def _revisao(sessao: Session, noticia: Noticia, autor: Usuario | None, descricao: str) -> None:
    sessao.add(RevisaoNoticia(noticia_id=noticia.id, versao=noticia.versao, descricao=descricao, titulo=noticia.titulo,
                              linha_fina=noticia.linha_fina, corpo_html=noticia.corpo_html, autor_nome=_nome(autor), criado_em=agora_utc()))


def _aplicar(sessao: Session, noticia: Noticia, dados: DadosNoticia) -> None:
    titulo = dados.titulo.strip()
    if not titulo:
        raise ErroNoticia("Informe o título.")
    if dados.categoria_id and sessao.get(CategoriaNoticia, dados.categoria_id) is None:
        raise ErroNoticia("Categoria inexistente.")
    if dados.destaque_ate and dados.publicar_em and _comparavel(dados.destaque_ate) <= _comparavel(dados.publicar_em):
        raise ErroNoticia("O fim do destaque precisa ser depois da publicação.")
    if titulo != noticia.titulo or not noticia.slug:
        noticia.slug = _slug_unico(sessao, titulo, noticia.id)
    noticia.titulo, noticia.linha_fina = titulo[:220], dados.linha_fina.strip()[:300]
    noticia.corpo_html = limpar_html(dados.corpo_html)
    # Notícia aprovada sempre tem data de publicação: sem ela (campo vazio na edição) sairia do portal, pois só aparece com `publicar_em <= agora`
    publicar_em = dados.publicar_em or (noticia.publicar_em if noticia.situacao == "aprovada" else None)
    noticia.categoria_id, noticia.publicar_em, noticia.destaque_ate = dados.categoria_id, publicar_em, dados.destaque_ate
    noticia.fixada, noticia.exige_ciencia = dados.fixada, dados.exige_ciencia
    publico = {"usuarios_ids": sorted(set(dados.usuarios_aviso)), "setores_ids": sorted(set(dados.setores_aviso))}
    noticia.publico_aviso = publico if (publico["usuarios_ids"] or publico["setores_ids"]) else None
    noticia.capa_alt = dados.capa_alt.strip()[:300]


def criar(sessao: Session, autor: Usuario, dados: DadosNoticia) -> Noticia:
    _exigir(eh_redator(sessao, autor), "Só redatores (MODIFICAÇÃO em notícias) e aprovadores escrevem notícias.")
    noticia = Noticia(slug="", titulo="", autor_id=autor.id, autor_nome=_nome(autor), situacao="rascunho", versao=1, criado_em=agora_utc())
    sessao.add(noticia)
    _aplicar(sessao, noticia, dados)
    sessao.flush()
    _revisao(sessao, noticia, autor, "Criada")
    auditar(sessao, autor.login, "noticias.criar", noticia.titulo, autor_id=autor.id, alvo_tipo="noticia", alvo_id=noticia.id)
    sessao.commit()
    return noticia


def editar(sessao: Session, autor: Usuario, noticia: Noticia, dados: DadosNoticia, versao: int | None) -> Noticia:
    _exigir(pode_editar(sessao, autor, noticia), "Você não pode editar esta notícia agora.")
    if versao is not None and versao != noticia.versao:
        raise ErroNoticia("A notícia foi alterada por outra pessoa depois que você a abriu. Recarregue a página.", 409, "conflito")
    _aplicar(sessao, noticia, dados)
    noticia.versao += 1
    _revisao(sessao, noticia, autor, "Editada")
    auditar(sessao, autor.login, "noticias.editar", noticia.titulo, autor_id=autor.id, alvo_tipo="noticia", alvo_id=noticia.id)
    sessao.commit()
    return noticia


def _completa(noticia: Noticia) -> None:
    faltando = [n for n, ok in (("título", noticia.titulo), ("texto", texto_puro(noticia.corpo_html)), ("capa", noticia.capa_versoes),
                                ("descrição da capa (texto alternativo)", noticia.capa_alt)) if not ok]
    if faltando:
        raise ErroNoticia("Antes de enviar, preencha: " + ", ".join(faltando) + ".")


# ---------------------------------------------------------------------------------------------
# Fluxo editorial
# ---------------------------------------------------------------------------------------------

def _link_gestao(noticia: Noticia) -> str:
    return f"/noticias/gestao/{noticia.id}"


def enviar_revisao(sessao: Session, autor: Usuario, noticia: Noticia) -> Noticia:
    _exigir("enviar_revisao" in acoes(sessao, autor, noticia), "Você não pode enviar esta notícia para aprovação agora.")
    _completa(noticia)
    agora = agora_utc()
    if noticia.publicar_em and _comparavel(noticia.publicar_em) < agora:
        noticia.publicar_em = None  # data já passou: vira pedido de publicação imediata
    noticia.situacao, noticia.enviada_revisao_em, noticia.motivo_devolucao = "em_revisao", agora, None
    noticia.versao += 1
    _revisao(sessao, noticia, autor, "Enviada para aprovação")
    quando = f"agendada para {_data_hora(noticia.publicar_em)}" if noticia.publicar_em else "publicação imediata após a aprovação"
    servico_mensagens.notificar(
        sessao, [u.id for u in aprovadores(sessao)], f"Notícia aguardando aprovação: {noticia.titulo}",
        f"{_nome(autor)} enviou a notícia \"{noticia.titulo}\" para aprovação ({quando}).",
        chave=f"noticia-aprovacao:{noticia.id}:{noticia.versao}", categoria="pendencia", link=_link_gestao(noticia), email=True, autor=autor,
    )
    auditar(sessao, autor.login, "noticias.enviar_revisao", noticia.titulo, autor_id=autor.id, alvo_tipo="noticia", alvo_id=noticia.id)
    sessao.commit()
    return noticia


def aprovar(sessao: Session, aprovador: Usuario, noticia: Noticia, publicar_em: datetime | None = None) -> Noticia:
    _exigir("aprovar" in acoes(sessao, aprovador, noticia), "Só aprovadores (CONTROLE TOTAL em notícias) aprovam.")
    _completa(noticia)
    agora = agora_utc()
    quando = publicar_em or noticia.publicar_em
    noticia.publicar_em = quando if quando and _comparavel(quando) > agora else agora
    noticia.situacao, noticia.aprovado_por_id, noticia.aprovado_por_nome, noticia.aprovado_em = "aprovada", aprovador.id, _nome(aprovador), agora
    noticia.versao += 1
    _revisao(sessao, noticia, aprovador, "Aprovada")
    servico_mensagens.encerrar(sessao, prefixo=f"noticia-aprovacao:{noticia.id}:")
    texto = "já está no portal" if visivel(noticia, agora) else f"será publicada em {_data_hora(noticia.publicar_em)}"
    servico_mensagens.notificar(sessao, [noticia.autor_id], f"Notícia aprovada: {noticia.titulo}",
                                f"{_nome(aprovador)} aprovou a notícia \"{noticia.titulo}\", que {texto}.",
                                chave=f"noticia-aprovada:{noticia.id}:{noticia.versao}", link=_link_gestao(noticia), email=True, autor=aprovador)
    auditar(sessao, aprovador.login, "noticias.aprovar", noticia.titulo, autor_id=aprovador.id, alvo_tipo="noticia", alvo_id=noticia.id,
            dados={"publicar_em": noticia.publicar_em.isoformat()})
    if visivel(noticia, agora):
        _avisar_publicacao(sessao, noticia)
    sessao.commit()
    return noticia


def devolver(sessao: Session, aprovador: Usuario, noticia: Noticia, motivo: str) -> Noticia:
    _exigir("devolver" in acoes(sessao, aprovador, noticia), "Só aprovadores devolvem notícias em revisão.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroNoticia("Informe o que precisa ser ajustado.")
    noticia.situacao, noticia.motivo_devolucao = "devolvida", motivo
    noticia.versao += 1
    _revisao(sessao, noticia, aprovador, "Devolvida para ajustes")
    servico_mensagens.encerrar(sessao, prefixo=f"noticia-aprovacao:{noticia.id}:")
    servico_mensagens.notificar(sessao, [noticia.autor_id], f"Notícia devolvida para ajustes: {noticia.titulo}",
                                f"{_nome(aprovador)} devolveu a notícia \"{noticia.titulo}\".\n\nO que ajustar: {motivo}",
                                chave=f"noticia-devolvida:{noticia.id}:{noticia.versao}", categoria="pendencia", link=_link_gestao(noticia),
                                email=True, autor=aprovador)
    auditar(sessao, aprovador.login, "noticias.devolver", noticia.titulo, autor_id=aprovador.id, alvo_tipo="noticia", alvo_id=noticia.id,
            dados={"motivo": motivo})
    sessao.commit()
    return noticia


def arquivar(sessao: Session, aprovador: Usuario, noticia: Noticia, arquivar_: bool = True) -> Noticia:
    _exigir(("arquivar" if arquivar_ else "desarquivar") in acoes(sessao, aprovador, noticia), "Ação não permitida.")
    noticia.situacao = "arquivada" if arquivar_ else "aprovada"
    noticia.versao += 1
    _revisao(sessao, noticia, aprovador, "Arquivada" if arquivar_ else "Desarquivada")
    auditar(sessao, aprovador.login, "noticias.arquivar" if arquivar_ else "noticias.desarquivar", noticia.titulo, autor_id=aprovador.id,
            alvo_tipo="noticia", alvo_id=noticia.id)
    sessao.commit()
    return noticia


def excluir(sessao: Session, usuario: Usuario, noticia: Noticia) -> None:
    _exigir("excluir" in acoes(sessao, usuario, noticia), "Você não pode excluir esta notícia.")
    servico_mensagens.encerrar(sessao, prefixo=f"noticia-aprovacao:{noticia.id}:")
    auditar(sessao, usuario.login, "noticias.excluir", noticia.titulo, autor_id=usuario.id, alvo_tipo="noticia", alvo_id=noticia.id)
    sessao.delete(noticia)
    sessao.commit()


def _data_hora(valor: datetime | None) -> str:
    from zoneinfo import ZoneInfo
    return _comparavel(valor).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M") if valor else "—"


# ---------------------------------------------------------------------------------------------
# Avisos da publicação
# ---------------------------------------------------------------------------------------------

def destinatarios_aviso(sessao: Session, noticia: Noticia) -> list[int]:
    """Usuários escolhidos + pessoas dos setores escolhidos (e dos setores abaixo deles)."""
    from app.services.rh.papeis import setor_com_descendentes, usuarios_dos_setores
    publico = noticia.publico_aviso or {}
    ids = set(publico.get("usuarios_ids") or [])
    setores = setor_com_descendentes(sessao, list(publico.get("setores_ids") or []))
    ids |= {u.id for u in usuarios_dos_setores(sessao, setores)}
    return sorted(ids)


def _avisar_publicacao(sessao: Session, noticia: Noticia) -> int:
    if not noticia.publico_aviso or noticia.aviso_enviado_em:
        return 0
    ids = destinatarios_aviso(sessao, noticia)
    corpo = (noticia.linha_fina or texto_puro(noticia.corpo_html)[:280])
    if noticia.exige_ciencia:
        corpo += "\n\nEste comunicado pede a sua ciência: abra a mensagem e registre que leu."
    servico_mensagens.notificar(
        sessao, ids, ("Comunicado: " if noticia.exige_ciencia else "Notícia: ") + noticia.titulo, corpo,
        chave=f"noticia-aviso:{noticia.id}", categoria="comunicado", prioridade="alta" if noticia.exige_ciencia else "normal",
        link=f"/noticias/{noticia.slug}", email=True, abrir_em_janela=noticia.exige_ciencia,
    )
    noticia.aviso_enviado_em = agora_utc()
    return len(ids)


def processar_publicacoes(sessao: Session, agora: datetime | None = None) -> int:
    """Rotina (a cada 2 min): dispara o aviso das notícias que acabaram de aparecer no portal."""
    agora = agora or agora_utc()
    pendentes = list(sessao.scalars(_visiveis(agora).where(Noticia.publico_aviso.is_not(None), Noticia.aviso_enviado_em.is_(None))))
    for noticia in pendentes:
        _avisar_publicacao(sessao, noticia)
    sessao.commit()
    return len(pendentes)


def ciencias(sessao: Session, noticia: Noticia) -> tuple[int, int, list[tuple[str, datetime | None]]]:
    """Destinatários do aviso, quantos deram ciência e a lista (nome, ciente_em)."""
    entregas = list(sessao.execute(
        select(Usuario, EntregaMensagem.ciente_em).join(EntregaMensagem, EntregaMensagem.destinatario_id == Usuario.id)
        .join(Mensagem).where(Mensagem.chave == f"noticia-aviso:{noticia.id}").order_by(Usuario.nome_completo)
    ))
    lista = [(_nome(u), _comparavel(ciente)) for u, ciente in entregas]
    return len(lista), sum(1 for _, c in lista if c), lista


# ---------------------------------------------------------------------------------------------
# Capa e anexos
# ---------------------------------------------------------------------------------------------

def _gravar_versoes(sessao: Session, noticia: Noticia, original: bytes, autor: Usuario | None) -> None:
    imagem, _ = imagens.abrir(original)
    versoes, usado = imagens.versoes_capa(imagem, noticia.capa_modo, noticia.capa_recorte)
    noticia.capa_recorte = usado
    noticia.capa_versoes = {
        tamanho: str(servico_anexos.guardar_arquivo_gerado(sessao, conteudo, f"capa-{tamanho}.webp", "image/webp", "noticia-capa-versao",
                                                             autor.id if autor else None).id)
        for tamanho, conteudo in versoes.items()
    }


def definir_capa(sessao: Session, autor: Usuario, noticia: Noticia, conteudo: bytes | None, nome: str, modo: str, recorte: dict | None) -> Noticia:
    """Nova imagem (ou só novo recorte/modo da atual) e regeneração das versões WebP."""
    _exigir(pode_editar(sessao, autor, noticia), "Você não pode alterar a capa desta notícia agora.")
    if modo not in ("recortar", "inteira"):
        raise ErroNoticia("Modo da capa inválido.")
    try:
        if conteudo is not None:
            _, tipo = imagens.abrir(conteudo)
            extensao = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[tipo]
            original = servico_anexos.guardar_arquivo_gerado(sessao, conteudo, (nome or "capa")[:200] + ("" if nome.lower().endswith(extensao) else extensao),
                                                             tipo, "noticia-capa", autor.id)
            noticia.capa_anexo_id, noticia.capa_recorte = original.id, None
        elif noticia.capa_anexo_id is None:
            raise ErroNoticia("Envie a imagem da capa.")
        else:
            conteudo = servico_anexos.caminho(sessao.get(Anexo, noticia.capa_anexo_id)).read_bytes()
        noticia.capa_modo = modo
        if recorte is not None:
            noticia.capa_recorte = recorte
        _gravar_versoes(sessao, noticia, conteudo, autor)
    except imagens.ErroImagem as erro:
        raise ErroNoticia(str(erro)) from erro
    noticia.versao += 1
    sessao.commit()
    return noticia


def anexar(sessao: Session, autor: Usuario, noticia: Noticia, conteudo: bytes, nome: str) -> Noticia:
    _exigir(pode_editar(sessao, autor, noticia), "Você não pode anexar arquivos a esta notícia agora.")
    if len(noticia.anexos) >= 10:
        raise ErroNoticia("Até 10 anexos por notícia.")
    try:
        anexo = servico_anexos.guardar_arquivo(sessao, BytesIO(conteudo), nome, "noticia-anexo", autor.id)
    except servico_anexos.ErroAnexo as erro:
        raise ErroNoticia(str(erro)) from erro
    noticia.anexos.append(AnexoNoticia(anexo_id=anexo.id, ordem=len(noticia.anexos)))
    sessao.commit()
    sessao.refresh(noticia)
    return noticia


def remover_anexo(sessao: Session, autor: Usuario, noticia: Noticia, anexo_id) -> Noticia:
    _exigir(pode_editar(sessao, autor, noticia), "Você não pode alterar os anexos desta notícia agora.")
    vinculo = next((a for a in noticia.anexos if a.anexo_id == anexo_id), None)
    if vinculo is None:
        raise ErroNoticia("Anexo não encontrado.", 404, "nao_encontrado")
    noticia.anexos.remove(vinculo)
    sessao.commit()
    return noticia


def anexo_publico(sessao: Session, noticia: Noticia, anexo_id) -> Anexo:
    """Arquivo de uma notícia (capa, versão da capa ou anexo) — só os que pertencem a ela."""
    permitidos = {str(a.anexo_id) for a in noticia.anexos} | set((noticia.capa_versoes or {}).values())
    if str(anexo_id) not in permitidos:
        raise ErroNoticia("Arquivo não encontrado.", 404, "nao_encontrado")
    anexo = sessao.get(Anexo, anexo_id)
    if anexo is None or anexo.excluido_em is not None:
        raise ErroNoticia("Arquivo não encontrado.", 404, "nao_encontrado")
    return anexo


# ---------------------------------------------------------------------------------------------
# Categorias, atalhos e configuração (aprovadores)
# ---------------------------------------------------------------------------------------------

def salvar_categoria(sessao: Session, autor: Usuario, categoria_id: int | None, nome: str, cor: str, ordem: int, ativa: bool) -> CategoriaNoticia:
    _exigir(eh_aprovador(sessao, autor), "Só aprovadores gerenciam categorias.")
    nome = nome.strip()
    repetida = sessao.scalar(select(CategoriaNoticia).where(func.lower(CategoriaNoticia.nome) == nome.lower()))
    if repetida is not None and repetida.id != categoria_id:
        raise ErroNoticia("Já existe uma categoria com esse nome.", 409, "conflito")
    categoria = sessao.get(CategoriaNoticia, categoria_id) if categoria_id else CategoriaNoticia()
    if categoria is None:
        raise ErroNoticia("Categoria não encontrada.", 404, "nao_encontrado")
    categoria.nome, categoria.cor, categoria.ordem, categoria.ativa = nome, cor, ordem, ativa
    sessao.add(categoria)
    sessao.commit()
    return categoria


def salvar_atalho(sessao: Session, autor: Usuario, atalho_id: int | None, titulo: str, url: str, ativo: bool, nova_aba: bool,
                  imagem: bytes | None = None, nome_imagem: str = "") -> AtalhoPortal:
    _exigir(eh_aprovador(sessao, autor), "Só aprovadores gerenciam os atalhos do portal.")
    atalho = sessao.get(AtalhoPortal, atalho_id) if atalho_id else AtalhoPortal(ordem=(sessao.scalar(select(func.max(AtalhoPortal.ordem))) or 0) + 1)
    if atalho is None:
        raise ErroNoticia("Atalho não encontrado.", 404, "nao_encontrado")
    atalho.titulo, atalho.url, atalho.ativo, atalho.nova_aba = titulo.strip()[:80], url.strip()[:500], ativo, nova_aba
    if imagem is not None:
        try:
            figura, tipo = imagens.abrir(imagem)
        except imagens.ErroImagem as erro:
            raise ErroNoticia(str(erro)) from erro
        original = servico_anexos.guardar_arquivo_gerado(sessao, imagem, nome_imagem or "atalho", tipo, "portal-atalho", autor.id)
        exibicao = servico_anexos.guardar_arquivo_gerado(sessao, imagens.versao_atalho(figura), "atalho.webp", "image/webp", "portal-atalho", autor.id)
        atalho.imagem_anexo_id, atalho.imagem_exibicao_id = original.id, exibicao.id
    sessao.add(atalho)
    auditar(sessao, autor.login, "portal.atalho.salvar", atalho.titulo, autor_id=autor.id)
    sessao.commit()
    return atalho


def excluir_atalho(sessao: Session, autor: Usuario, atalho_id: int) -> None:
    _exigir(eh_aprovador(sessao, autor), "Só aprovadores gerenciam os atalhos do portal.")
    atalho = sessao.get(AtalhoPortal, atalho_id)
    if atalho is None:
        raise ErroNoticia("Atalho não encontrado.", 404, "nao_encontrado")
    auditar(sessao, autor.login, "portal.atalho.excluir", atalho.titulo, autor_id=autor.id)
    sessao.delete(atalho)
    sessao.commit()


def ordenar_atalhos(sessao: Session, autor: Usuario, ids: list[int]) -> None:
    _exigir(eh_aprovador(sessao, autor), "Só aprovadores gerenciam os atalhos do portal.")
    for posicao, i in enumerate(ids):
        atalho = sessao.get(AtalhoPortal, i)
        if atalho is not None:
            atalho.ordem = posicao
    sessao.commit()


def salvar_configuracao(sessao: Session, autor: Usuario, dados: dict, curadoria: list | None) -> ConfiguracaoPortal:
    """Parâmetros do portal e, na curadoria, a ordem das notícias do slider (ids; as demais saem da curadoria)."""
    _exigir(eh_aprovador(sessao, autor), "Só aprovadores configuram o portal.")
    config = configuracao(sessao)
    for chave, valor in dados.items():
        setattr(config, chave, valor)
    config.atualizado_por_nome = _nome(autor)
    if curadoria is not None:
        for noticia in sessao.scalars(select(Noticia).where(Noticia.ordem_slider.is_not(None))):
            noticia.ordem_slider = None
        for posicao, noticia_id in enumerate(curadoria):
            noticia = sessao.get(Noticia, noticia_id)
            if noticia is not None:
                noticia.ordem_slider = posicao
    auditar(sessao, autor.login, "portal.configurar", "Configuração do portal", autor_id=autor.id, dados={k: str(v) for k, v in dados.items()})
    sessao.commit()
    return config


def setores_opcoes(sessao: Session) -> list[Setor]:
    return list(sessao.scalars(select(Setor).where(Setor.ativo.is_(True)).order_by(Setor.nome)))
