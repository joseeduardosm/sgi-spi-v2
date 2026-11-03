# Criado por José Eduardo Santana Martins
# Este arquivo serve para a nota de satisfação, as respostas prontas, os motivos de pendência e os relatórios dos Chamados.
"""Qualidade do atendimento (marco 6).

- **Satisfação:** ao resolver, o chamado ganha uma pesquisa; o solicitante (ou alguém do setor solicitante) dá a nota com um clique
  (1 Péssimo, 2 Ruim, 3 Regular, 4 Bom, 5 Ótimo) e, se quiser, um comentário. Pode mudar a nota enquanto o chamado estiver resolvido.
  Resolver de novo (depois do "Não resolveu") pede a nota outra vez.
- **Respostas prontas:** textos que quem atende insere na resposta; sem setor, valem para todos.
- **Motivos de pendência:** lista padronizada para o "Pendente" (quem atende ainda pode escrever outro).
- **Relatórios:** números do período para o setor de quem atende (e os de baixo), ou de todos para quem administra.
"""

import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FUSO_SAO_PAULO, agora_utc, hoje_sao_paulo
from app.models.chamados import (
    PRIORIDADES, STATUS_ABERTOS, STATUS_SOLUCIONADO, Chamado, MotivoPendenciaChamados, RespostaProntaChamados, SatisfacaoChamado,
)
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.chamados import acesso
from app.services.chamados.acesso import Papeis
from app.services.chamados.parametros import ErroParametro
from app.services.chamados.servico import ErroChamado, obter, preparar_texto

ROTULOS_NOTA = {1: "Péssimo", 2: "Ruim", 3: "Regular", 4: "Bom", 5: "Ótimo"}
MAXIMO_DIAS_RELATORIO = 366


def _utc(valor: datetime | None) -> datetime | None:
    return valor if valor is None or valor.tzinfo else valor.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------------------------
# Satisfação
# ---------------------------------------------------------------------------------------------

def pedir(sessao: Session, chamado: Chamado, agora: datetime) -> None:
    """Chamado resolvido: cria a pesquisa (ou pede de novo, se já havia uma). Sem commit."""
    pesquisa = sessao.scalar(select(SatisfacaoChamado).where(SatisfacaoChamado.chamado_id == chamado.id))
    if pesquisa is None:
        sessao.add(SatisfacaoChamado(chamado_id=chamado.id, pedida_em=agora))
    else:
        pesquisa.pedida_em = agora


def da_pessoa(chamado: Chamado, usuario: Usuario, a: acesso.Alcance) -> bool:
    """Quem pediu ou alguém do setor solicitante."""
    return usuario.id == chamado.solicitante_id or (chamado.setor_solicitante_id is not None and chamado.setor_solicitante_id in a.setores_membro)


def leitura(sessao: Session, chamado: Chamado, usuario: Usuario, a: acesso.Alcance) -> dict | None:
    pesquisa = sessao.scalar(select(SatisfacaoChamado).where(SatisfacaoChamado.chamado_id == chamado.id))
    if pesquisa is None:
        return None
    pode = chamado.status_base == STATUS_SOLUCIONADO and not chamado.importado and da_pessoa(chamado, usuario, a)
    return {"nota": pesquisa.nota, "rotulo": ROTULOS_NOTA.get(pesquisa.nota or 0, ""), "comentario": pesquisa.comentario,
            "respondida_em": pesquisa.respondida_em, "pode_avaliar": pode}


def avaliar(sessao: Session, usuario: Usuario, p: Papeis, numero: int, nota: int, comentario: str) -> Chamado:
    """Grava a nota (1 a 5) e o comentário. Sem commit."""
    chamado, a = obter(sessao, usuario, p, numero)
    if not da_pessoa(chamado, usuario, a):
        raise ErroChamado("Só quem pediu (ou alguém do setor solicitante) avalia o atendimento.", 403, "acesso_negado")
    if chamado.importado or chamado.status_base != STATUS_SOLUCIONADO:
        raise ErroChamado("A nota é dada depois que o chamado é resolvido.", 409, "chamado_aberto")
    if nota not in ROTULOS_NOTA:
        raise ErroChamado("A nota vai de 1 (Péssimo) a 5 (Ótimo).")
    pesquisa = sessao.scalar(select(SatisfacaoChamado).where(SatisfacaoChamado.chamado_id == chamado.id))
    if pesquisa is None:
        pesquisa = SatisfacaoChamado(chamado_id=chamado.id, pedida_em=chamado.solucionado_em or agora_utc())
        sessao.add(pesquisa)
    pesquisa.nota, pesquisa.comentario = nota, comentario.strip()[:2000]
    pesquisa.respondida_em, pesquisa.respondida_por_id = agora_utc(), usuario.id
    chamado.versao += 1
    sessao.flush()
    return chamado


# ---------------------------------------------------------------------------------------------
# Respostas prontas e motivos de pendência
# ---------------------------------------------------------------------------------------------

def listar_respostas(sessao: Session, todas: bool = True, setores: set[int] | None = None) -> list[RespostaProntaChamados]:
    """Todas (Parâmetros) ou só as ativas que valem para os `setores` de quem atende (`None` = todos os setores)."""
    consulta = select(RespostaProntaChamados).order_by(RespostaProntaChamados.ordem, RespostaProntaChamados.titulo)
    if not todas:
        consulta = consulta.where(RespostaProntaChamados.ativo.is_(True))
        if setores is not None:
            consulta = consulta.where(or_(RespostaProntaChamados.setor_id.is_(None), RespostaProntaChamados.setor_id.in_(setores or {-1})))
    return list(sessao.scalars(consulta))


def salvar_resposta(sessao: Session, resposta_id: uuid.UUID | None, titulo: str, texto: str, setor_id: int | None, ativo: bool, ordem: int
                    ) -> RespostaProntaChamados:
    titulo = " ".join(titulo.split())
    if not 2 <= len(titulo) <= 120:
        raise ErroParametro("O título precisa ter de 2 a 120 caracteres.")
    try:
        html, imagens = preparar_texto(texto)
    except ErroChamado as erro:
        raise ErroParametro(str(erro)) from erro
    if imagens:
        raise ErroParametro("Resposta pronta não leva imagem colada.")
    if setor_id is not None and sessao.get(Setor, setor_id) is None:
        raise ErroParametro("Setor não encontrado.")
    item = sessao.get(RespostaProntaChamados, resposta_id) if resposta_id else RespostaProntaChamados()
    if item is None:
        raise ErroParametro("Resposta pronta não encontrada.", 404, "nao_encontrado")
    item.titulo, item.texto, item.setor_id, item.ativo, item.ordem = titulo, html, setor_id, ativo, ordem
    sessao.add(item)
    sessao.flush()
    return item


def excluir_resposta(sessao: Session, resposta_id: uuid.UUID) -> None:
    item = sessao.get(RespostaProntaChamados, resposta_id)
    if item is None:
        raise ErroParametro("Resposta pronta não encontrada.", 404, "nao_encontrado")
    sessao.delete(item)
    sessao.flush()


def listar_motivos(sessao: Session, todos: bool = True) -> list[MotivoPendenciaChamados]:
    consulta = select(MotivoPendenciaChamados).order_by(MotivoPendenciaChamados.ordem, MotivoPendenciaChamados.nome)
    if not todos:
        consulta = consulta.where(MotivoPendenciaChamados.ativo.is_(True))
    return list(sessao.scalars(consulta))


def salvar_motivo(sessao: Session, motivo_id: uuid.UUID | None, nome: str, ativo: bool, ordem: int) -> MotivoPendenciaChamados:
    nome = " ".join(nome.split())
    if not 3 <= len(nome) <= 120:
        raise ErroParametro("O motivo precisa ter de 3 a 120 caracteres.")
    repetido = sessao.scalar(select(MotivoPendenciaChamados).where(MotivoPendenciaChamados.nome.ilike(nome)))
    if repetido is not None and repetido.id != motivo_id:
        raise ErroParametro("Já existe um motivo com este nome.", 409, "duplicado")
    item = sessao.get(MotivoPendenciaChamados, motivo_id) if motivo_id else MotivoPendenciaChamados()
    if item is None:
        raise ErroParametro("Motivo não encontrado.", 404, "nao_encontrado")
    item.nome, item.ativo, item.ordem = nome, ativo, ordem
    sessao.add(item)
    sessao.flush()
    return item


def excluir_motivo(sessao: Session, motivo_id: uuid.UUID) -> None:
    item = sessao.get(MotivoPendenciaChamados, motivo_id)
    if item is None:
        raise ErroParametro("Motivo não encontrado.", 404, "nao_encontrado")
    sessao.delete(item)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------------------------

@dataclass
class _Grupo:
    abertos: int = 0
    resolvidos: int = 0
    no_prazo: int = 0
    com_prazo: int = 0

    id: str = ""

    def linha(self, nome: str) -> dict:
        return {"id": self.id, "nome": nome, "abertos": self.abertos, "resolvidos": self.resolvidos,
                "no_prazo_pct": round(self.no_prazo * 100 / self.com_prazo, 1) if self.com_prazo else None}


@dataclass
class Relatorio:
    area: str
    inicio: date
    fim: date
    resumo: dict = field(default_factory=dict)
    semanas: list[dict] = field(default_factory=list)
    por_categoria: list[dict] = field(default_factory=list)
    por_setor: list[dict] = field(default_factory=list)
    por_prioridade: dict = field(default_factory=dict)
    notas: list[int] = field(default_factory=list)
    equipe: list[dict] = field(default_factory=list)


@dataclass
class VisaoRelatorio:
    """Quanto a pessoa enxerga nos relatórios. `ampla`: Controle total ou líder de um setor que tem setores abaixo; só ela escolhe o setor e
    vê "Por setor responsável". `opcoes`: setores que pode escolher (`None` = todos, para quem administra)."""
    ampla: bool
    membro: set[int]
    opcoes: set[int] | None


def visao(sessao: Session, usuario: Usuario, p: Papeis) -> VisaoRelatorio:
    if not p.atender:
        raise ErroChamado("Os relatórios são de quem atende chamados.", 403, "acesso_negado")
    membro = acesso.setores_do_usuario(sessao, usuario)
    if p.administrar:
        return VisaoRelatorio(True, membro, None)
    liderados = set(sessao.scalars(select(Setor.id).where(Setor.lider_id == usuario.id, Setor.ativo.is_(True))))
    com_filhos = set(sessao.scalars(select(Setor.setor_pai_id).where(Setor.setor_pai_id.in_(liderados), Setor.ativo.is_(True)))) if liderados else set()
    if com_filhos:
        return VisaoRelatorio(True, membro, membro | acesso._descendentes(sessao, com_filhos))
    if not membro:
        raise ErroChamado("Você não é membro de nenhum setor, então não há relatório para mostrar.", 403, "sem_setor")
    return VisaoRelatorio(False, membro, membro)


def escopo(sessao: Session, usuario: Usuario, p: Papeis, setor_id: int | None) -> tuple[set[int] | None, str]:
    """Setores do relatório.

    - Controle total: qualquer setor (e os de baixo); sem escolha, todos.
    - Líder de um setor com setores abaixo: um desses (e os de baixo); sem escolha, o setor dele e os de baixo.
    - Os demais: só o próprio setor (ou setores), sem escolha (`setor_id` de outro setor: 403).
    """
    v = visao(sessao, usuario, p)
    if setor_id is not None:
        setor = sessao.get(Setor, setor_id)
        if setor is None:
            raise ErroChamado("Setor não encontrado.", 404, "nao_encontrado")
        if v.opcoes is not None and setor_id not in v.opcoes:
            raise ErroChamado("Você só vê o relatório do seu setor.", 403, "acesso_negado")
        return (acesso._descendentes(sessao, {setor_id}) if v.ampla else {setor_id}), setor.nome
    if v.opcoes is None:
        return None, "Todos os setores"
    if v.ampla:
        return set(v.opcoes), "Meus setores"
    nomes = sorted(sessao.scalars(select(Setor.nome).where(Setor.id.in_(v.membro))))
    return set(v.membro), " · ".join(nomes)


def _fila_no_fim(sessao: Session, setores: set[int] | None, segunda: date, ate: datetime) -> int:
    """Chamados em aberto no fim da semana (domingo 24h, ou o fim do período se vier antes). Não conta o histórico importado."""
    fim = min(datetime.combine(segunda + timedelta(days=7), time(0), FUSO_SAO_PAULO).astimezone(UTC), ate)
    consulta = select(func.count()).select_from(Chamado).where(
        Chamado.excluido_em.is_(None), Chamado.importado.is_(False), Chamado.aberto_em < fim,
        or_(Chamado.solucionado_em.is_(None), Chamado.solucionado_em >= fim))
    if setores is not None:
        consulta = consulta.where(Chamado.setor_id.in_(setores or {-1}))
    return sessao.scalar(consulta) or 0


def _equipe(sessao: Session, setores: set[int] | None, inicio: date, fim: date) -> list[dict]:
    """Quanto cada pessoa rendeu: **resolvidos** (soluções que ela registrou) e **assumidos** (chamados que estão com ela e foram assumidos na janela).

    Três janelas, terminando no fim do período: últimos 7 dias, últimos 30 dias e a **média por semana** do período escolhido.
    Entram os membros dos setores do relatório (mesmo zerados, para ver quem não está pegando chamado) e quem atendeu chamado desses setores.
    As 12 pessoas que mais resolveram nos últimos 30 dias, em ordem.
    """
    from app.models.chamados import SolucaoChamado
    from app.models.setor import MembroSetor
    from app.services.chamados.painel import primeiros_nomes

    janelas = {"7d": (fim - timedelta(days=6), fim), "30d": (fim - timedelta(days=29), fim), "periodo": (inicio, fim)}
    de = _limites(min(i for i, _ in janelas.values()), fim)[0]
    ate = _limites(fim, fim)[1]
    no_escopo = [Chamado.excluido_em.is_(None)] + ([Chamado.setor_id.in_(setores or {-1})] if setores is not None else [])
    resolucoes = sessao.execute(select(SolucaoChamado.autor_id, SolucaoChamado.chamado_id, SolucaoChamado.criado_em).join(Chamado, Chamado.id == SolucaoChamado.chamado_id)
                                .where(SolucaoChamado.autor_id.is_not(None), SolucaoChamado.criado_em >= de, SolucaoChamado.criado_em < ate, *no_escopo)).all()
    assumidos = sessao.execute(select(Chamado.responsavel_id, Chamado.id, Chamado.tomado_em)
                               .where(Chamado.responsavel_id.is_not(None), Chamado.tomado_em >= de, Chamado.tomado_em < ate, *no_escopo)).all()

    def contar(linhas) -> dict[int, dict[str, int]]:
        resultado: dict[int, dict[str, set]] = defaultdict(lambda: {k: set() for k in janelas})
        for pessoa, chamado, quando in linhas:
            dia = _utc(quando).astimezone(FUSO_SAO_PAULO).date()
            for k, (i, f) in janelas.items():
                if i <= dia <= f:
                    resultado[pessoa][k].add(chamado)
        return {p: {k: len(v) for k, v in j.items()} for p, j in resultado.items()}

    resolvidos, pegos = contar(resolucoes), contar(assumidos)
    pessoas = set(resolvidos) | set(pegos)
    if setores is not None:
        pessoas |= set(sessao.scalars(select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_(setores or {-1}))))
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(pessoas or {-1}), Usuario.ativo.is_(True)))}
    semanas = max(1.0, ((fim - inicio).days + 1) / 7)
    vazio = {k: 0 for k in janelas}
    linhas = []
    for pid, u in usuarios.items():
        r, a = resolvidos.get(pid, vazio), pegos.get(pid, vazio)
        linhas.append({"usuario_id": pid, "nome": primeiros_nomes(u.nome_completo or u.login),
                       "resolvidos_7d": r["7d"], "assumidos_7d": a["7d"], "resolvidos_30d": r["30d"], "assumidos_30d": a["30d"],
                       "resolvidos_semana": round(r["periodo"] / semanas, 1), "assumidos_semana": round(a["periodo"] / semanas, 1)})
    return sorted(linhas, key=lambda x: (-x["resolvidos_30d"], -x["assumidos_30d"], x["nome"]))[:12]


def _limites(inicio: date, fim: date) -> tuple[datetime, datetime]:
    return (datetime.combine(inicio, time(0), FUSO_SAO_PAULO).astimezone(UTC),
            datetime.combine(fim + timedelta(days=1), time(0), FUSO_SAO_PAULO).astimezone(UTC))


def relatorio(sessao: Session, setores: set[int] | None, area: str, inicio: date | None, fim: date | None) -> Relatorio:
    """Números do período (padrão: últimos 30 dias). Inclui o histórico importado do GLPI (comparar antes × depois é o objetivo)."""
    fim = fim or hoje_sao_paulo()
    inicio = inicio or fim - timedelta(days=29)
    if inicio > fim:
        raise ErroChamado("A data inicial vem depois da final.")
    if (fim - inicio).days >= MAXIMO_DIAS_RELATORIO:
        raise ErroChamado("Escolha um período de até 1 ano.")
    de, ate = _limites(inicio, fim)
    base = select(Chamado).options(selectinload(Chamado.categoria)).where(Chamado.excluido_em.is_(None))
    if setores is not None:
        base = base.where(Chamado.setor_id.in_(setores or {-1}))
    do_periodo = list(sessao.scalars(base.where(or_((Chamado.aberto_em >= de) & (Chamado.aberto_em < ate),
                                                     (Chamado.solucionado_em >= de) & (Chamado.solucionado_em < ate)))))
    agora = select(func.count()).select_from(Chamado).where(Chamado.excluido_em.is_(None), Chamado.importado.is_(False), Chamado.status_base.in_(STATUS_ABERTOS))
    if setores is not None:
        agora = agora.where(Chamado.setor_id.in_(setores or {-1}))
    abertos_agora = sessao.scalar(agora) or 0

    def dentro(valor: datetime | None) -> bool:
        v = _utc(valor)
        return v is not None and de <= v < ate

    abertos = [c for c in do_periodo if dentro(c.aberto_em)]
    resolvidos = [c for c in do_periodo if c.status_base == STATUS_SOLUCIONADO and dentro(c.solucionado_em)]
    tto = [c for c in abertos if c.prazo_tto is not None and c.tomado_em is not None]
    tto_ok = sum(1 for c in tto if _utc(c.tomado_em) <= _utc(c.prazo_tto))
    ttr = [c for c in resolvidos if c.prazo_ttr is not None]
    ttr_ok = sum(1 for c in ttr if _utc(c.solucionado_em) <= _utc(c.prazo_ttr))
    horas = [(_utc(c.solucionado_em) - _utc(c.aberto_em)).total_seconds() / 3600 for c in resolvidos]

    ids_resolvidos = [c.id for c in resolvidos]
    pesquisas = list(sessao.scalars(select(SatisfacaoChamado).where(SatisfacaoChamado.chamado_id.in_(ids_resolvidos or [uuid.uuid4()]))))
    notas = [x.nota for x in pesquisas if x.nota]
    rel = Relatorio(area=area, inicio=inicio, fim=fim)
    rel.resumo = {
        "abertos_no_periodo": len(abertos), "resolvidos_no_periodo": len(resolvidos), "em_aberto_agora": abertos_agora,
        "atendimento_no_prazo": tto_ok, "atendimento_com_prazo": len(tto),
        "atendimento_no_prazo_pct": round(tto_ok * 100 / len(tto), 1) if tto else None,
        "solucao_no_prazo": ttr_ok, "solucao_com_prazo": len(ttr), "solucao_no_prazo_pct": round(ttr_ok * 100 / len(ttr), 1) if ttr else None,
        "horas_mediana_solucao": round(statistics.median(horas), 1) if horas else None,
        "reabertos": sum(1 for c in resolvidos if c.reaberturas),
        "satisfacao_media": round(sum(notas) / len(notas), 2) if notas else None, "satisfacao_respostas": len(notas), "satisfacao_pedidas": len(pesquisas),
    }
    rel.notas = [notas.count(n) for n in range(1, 6)]

    # Semanas (segunda a domingo) do período
    segunda = inicio - timedelta(days=inicio.weekday())
    semanas: dict[date, list[int]] = {}
    while segunda <= fim:
        semanas[segunda] = [0, 0]
        segunda += timedelta(days=7)

    def semana(valor: datetime) -> date:
        d = _utc(valor).astimezone(FUSO_SAO_PAULO).date()
        return d - timedelta(days=d.weekday())

    # Por semana também o que alimenta as minissérias dos cartões: reabertos, mediana de solução e atendimento no prazo
    horas_semana: dict[date, list[float]] = defaultdict(list)
    tto_semana: dict[date, list[bool]] = defaultdict(list)
    reabertos_semana: Counter = Counter()
    for c in abertos:
        semanas.setdefault(semana(c.aberto_em), [0, 0])[0] += 1
        if c.prazo_tto is not None and c.tomado_em is not None:
            tto_semana[semana(c.aberto_em)].append(_utc(c.tomado_em) <= _utc(c.prazo_tto))
    for c in resolvidos:
        k = semana(c.solucionado_em)
        semanas.setdefault(k, [0, 0])[1] += 1
        horas_semana[k].append((_utc(c.solucionado_em) - _utc(c.aberto_em)).total_seconds() / 3600)
        reabertos_semana[k] += bool(c.reaberturas)
    rel.semanas = [{
        "inicio": k, "abertos": v[0], "resolvidos": v[1], "em_aberto_fim": _fila_no_fim(sessao, setores, k, ate),
        "reabertos": reabertos_semana[k], "horas_mediana_solucao": round(statistics.median(horas_semana[k]), 1) if horas_semana[k] else None,
        "atendimento_no_prazo_pct": round(sum(tto_semana[k]) * 100 / len(tto_semana[k]), 1) if tto_semana[k] else None,
    } for k, v in sorted(semanas.items())]
    rel.equipe = _equipe(sessao, setores, inicio, fim)

    categorias: dict[str, _Grupo] = defaultdict(_Grupo)
    setores_g: dict[str, _Grupo] = defaultdict(_Grupo)
    for c in abertos + resolvidos:
        categorias[c.categoria.caminho].id = str(c.categoria_id)
        setores_g[c.setor_nome].id = str(c.setor_id)
    for c in abertos:
        categorias[c.categoria.caminho].abertos += 1
        setores_g[c.setor_nome].abertos += 1
    for c in resolvidos:
        for g in (categorias[c.categoria.caminho], setores_g[c.setor_nome]):
            g.resolvidos += 1
            if c.prazo_ttr is not None:
                g.com_prazo += 1
                g.no_prazo += _utc(c.solucionado_em) <= _utc(c.prazo_ttr)
    rel.por_categoria = sorted((g.linha(n) for n, g in categorias.items()), key=lambda x: (-x["abertos"], -x["resolvidos"], x["nome"]))[:15]
    rel.por_setor = sorted((g.linha(n) for n, g in setores_g.items()), key=lambda x: (-x["abertos"], -x["resolvidos"], x["nome"]))
    contagem = Counter(c.prioridade for c in abertos)
    rel.por_prioridade = {p: contagem.get(p, 0) for p in PRIORIDADES}
    return rel
