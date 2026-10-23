# Criado por José Eduardo Santana Martins
# Este arquivo serve para registrar e consultar o histórico da vida funcional da pessoa (cadastro, documentos, cargos, setores, férias, licença-prêmio e exoneração).
"""Histórico funcional (`rh_historico`).

Livro-razão **somente de inserção**: cada fato guarda **quem registrou e quando**. Os serviços do RH chamam `registrar` na mesma transação da operação. A carga
retroativa (`carga_retroativa`) preenche o que já existia (períodos aquisitivos, afastamentos, alterações cadastrais e ocupações), sem duplicar, pela origem.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import AlteracaoCadastral, Afastamento, EventoAfastamento, PeriodoAquisitivo
from app.models.rh_cargos import HistoricoRh, Ocupacao
from app.models.usuario import Usuario
from app.schemas.rh_cargos import HistoricoUsuario, LeituraHistorico, LeituraOcupacao
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf

TIPOS = {
    "cadastro": "Cadastro",
    "documento": "Documentos",
    "cargo": "Cargo",
    "setor": "Setor",
    "periodo_ferias": "Período de férias",
    "ferias": "Férias",
    "licenca_premio": "Licença-prêmio",
    "exoneracao": "Exoneração",
    "admissao": "Admissão",
    "outro": "Outros",
}


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "Sistema"


def registrar(
    sessao: Session, usuario_id: int, tipo: str, titulo: str, detalhe: str = "", autor: Usuario | None = None, *, quando: datetime | None = None,
    origem: tuple[str, str] | None = None, sigiloso: bool = False, dados: dict | None = None, autor_nome: str | None = None,
) -> HistoricoRh | None:
    """Acrescenta um fato ao histórico (sem commit). Com `origem` (tipo, id) já registrada, não duplica e devolve `None`."""
    if tipo not in TIPOS:
        tipo = "outro"
    if origem is not None:
        existente = sessao.scalar(select(HistoricoRh.id).where(HistoricoRh.origem_tipo == origem[0], HistoricoRh.origem_id == str(origem[1])))
        if existente is not None:
            return None
    evento = HistoricoRh(
        usuario_id=usuario_id, tipo=tipo, titulo=titulo[:300], detalhe=detalhe or "", ocorrido_em=quando or agora_utc(), autor_id=autor.id if autor else None,
        autor_nome=autor_nome or _nome(autor), origem_tipo=origem[0] if origem else None, origem_id=str(origem[1]) if origem else None, sigiloso=sigiloso, dados=dados,
    )
    sessao.add(evento)
    return evento


def _ocupacoes(sessao: Session, usuario_id: int) -> list[LeituraOcupacao]:
    resultado = []
    for o in sessao.scalars(select(Ocupacao).where(Ocupacao.usuario_id == usuario_id).order_by(Ocupacao.inicio.desc().nulls_last(), Ocupacao.id.desc())):
        resultado.append(LeituraOcupacao(
            id=o.id, cargo_id=o.cargo_id, cargo_rotulo=o.cargo.rotulo, setor_id=o.cargo.setor_id, setor_nome=_nome_setor(sessao, o.cargo.setor_id), inicio=o.inicio,
            fim=o.fim, ato=o.ato, motivo_fim=o.motivo_fim, ato_fim=o.ato_fim, registrado_por_nome=o.registrado_por_nome, registrado_em=o.registrado_em))
    return resultado


def _nome_setor(sessao: Session, setor_id: int) -> str:
    from app.models.setor import Setor

    setor = sessao.get(Setor, setor_id)
    return setor.nome if setor else "—"


def consultar(
    sessao: Session, usuario: Usuario, *, ver_sigilosos: bool, tipos: list[str] | None = None, de: date | None = None, ate: date | None = None,
) -> HistoricoUsuario:
    """Histórico da pessoa, do mais recente ao mais antigo. `ver_sigilosos` = quem consulta é o RH."""
    consulta = select(HistoricoRh).where(HistoricoRh.usuario_id == usuario.id).order_by(HistoricoRh.ocorrido_em.desc(), HistoricoRh.id.desc())
    if not ver_sigilosos:
        consulta = consulta.where(HistoricoRh.sigiloso.is_(False))
    if tipos:
        consulta = consulta.where(HistoricoRh.tipo.in_(tipos))
    eventos = []
    for h in sessao.scalars(consulta):
        dia = h.ocorrido_em.astimezone(FUSO_SAO_PAULO).date() if h.ocorrido_em.tzinfo else h.ocorrido_em.date()
        if (de and dia < de) or (ate and dia > ate):
            continue
        eventos.append(LeituraHistorico(id=h.id, tipo=h.tipo, titulo=h.titulo, detalhe=h.detalhe, ocorrido_em=h.ocorrido_em, autor_nome=h.autor_nome, sigiloso=h.sigiloso))
    return HistoricoUsuario(
        usuario_id=usuario.id, nome=usuario.nome_completo or usuario.login, login=usuario.login, cargo_atual=(usuario.cargo or "").strip(),
        setor_atual=(usuario.departamento or "").strip(), ocupacoes=_ocupacoes(sessao, usuario.id), eventos=eventos, tipos=TIPOS,
    )


def _data_hora(instante: datetime | None) -> str:
    """dd/mm/aaaa hh:mm no horário de Brasília."""
    if instante is None:
        return "—"
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=FUSO_SAO_PAULO)
    return instante.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M")


def _data(dia: date | None) -> str:
    return dia.strftime("%d/%m/%Y") if dia else "—"


def gerar_pdf(historico: HistoricoUsuario, gerado_por: str) -> bytes:
    """PDF do histórico funcional: identificação, cargos e setores por onde passou e linha do tempo completa (autor e dd/mm/aaaa hh:mm)."""
    documento = DocumentoPdf(titulo="Histórico funcional", subtitulo=f"{historico.nome} ({historico.login})", paisagem=False, autor=gerado_por)
    documento.secao("Identificação").campos([
        ("Nome", historico.nome), ("Login", historico.login), ("Cargo atual", historico.cargo_atual), ("Setor atual", historico.setor_atual),
    ])
    documento.secao("Cargos e setores por onde passou")
    if historico.ocupacoes:
        documento.tabela(
            ["Cargo", "Setor", "Início", "Fim", "Ato", "Registrado por"],
            [[o.cargo_rotulo, o.setor_nome, _data(o.inicio), _data(o.fim) + (f" ({o.motivo_fim})" if o.motivo_fim and o.fim else ""), o.ato or "—",
              f"{o.registrado_por_nome} em {_data_hora(o.registrado_em)}"] for o in historico.ocupacoes],
            larguras=[3.2, 2.4, 1.3, 1.9, 2, 2.6],
        )
    else:
        documento.paragrafo("Nenhuma ocupação de cargo registrada.")
    documento.secao("Linha do tempo")
    if historico.eventos:
        documento.tabela(
            ["Data e hora", "Tipo", "Evento", "Registrado por"],
            [[_data_hora(e.ocorrido_em), historico.tipos.get(e.tipo, e.tipo), e.titulo + (f"\n{e.detalhe}" if e.detalhe else ""), e.autor_nome] for e in historico.eventos],
            larguras=[1.7, 1.6, 5.6, 2.2],
        )
    else:
        documento.paragrafo("Nenhum evento registrado.")
    return documento.gerar()


def carga_retroativa(sessao: Session, aplicar: bool = False) -> dict[str, int]:
    """Preenche o histórico com o que já existe, sem duplicar (a origem identifica cada fato). Sem `aplicar`, só conta (simulação).

    Fontes: períodos aquisitivos (`periodo_ferias`), afastamentos gozados (`ferias`/`licenca_premio`) e alterações cadastrais validadas (`cadastro`)."""
    contagem = {"periodo_ferias": 0, "ferias": 0, "licenca_premio": 0, "cadastro": 0}

    def novo(origem: tuple[str, str]) -> bool:
        return sessao.scalar(select(HistoricoRh.id).where(HistoricoRh.origem_tipo == origem[0], HistoricoRh.origem_id == origem[1])) is None

    for p in sessao.scalars(select(PeriodoAquisitivo)):
        origem = ("periodo_aquisitivo", str(p.id))
        if novo(origem):
            contagem["periodo_ferias"] += 1
            if aplicar:
                registrar(sessao, p.usuario_id, "periodo_ferias", f"Período aquisitivo de férias {p.inicio:%d/%m/%Y} a {p.fim:%d/%m/%Y}: {p.dias_creditados} dia(s) creditado(s)",
                          f"Origem: {p.origem}", None, quando=_instante(p.inicio), origem=origem, autor_nome=p.ajustado_por_nome or "Sistema")
    for a in sessao.scalars(select(Afastamento).where(Afastamento.status == "gozado")):
        origem = ("afastamento", str(a.id))
        if novo(origem):
            tipo = "ferias" if a.tipo == "ferias" else "licenca_premio"
            contagem[tipo] += 1
            if aplicar:
                rotulo = "Férias" if a.tipo == "ferias" else "Licença-prêmio"
                registrar(sessao, a.usuario_id, tipo, f"{rotulo} gozada de {a.inicio:%d/%m/%Y} a {a.fim:%d/%m/%Y} ({a.dias} dia(s))", "", None, quando=a.decidido_em or _instante(a.fim), origem=origem, autor_nome=a.decidido_por_nome or "Sistema")
    for c in sessao.scalars(select(AlteracaoCadastral).where(AlteracaoCadastral.status == "validada")):
        origem = ("alteracao_cadastral", str(c.id))
        if novo(origem):
            contagem["cadastro"] += 1
            if aplicar:
                registrar(sessao, c.usuario_id, "cadastro", f"Cadastro: {c.campo} alterado", f"De “{c.valor_anterior or '—'}” para “{c.valor_proposto or '—'}”", None,
                          quando=c.analisada_em or c.solicitada_em, origem=origem, autor_nome=c.analisada_por_nome or c.solicitada_por_nome or "Sistema")
    return contagem


def _instante(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 12, 0, tzinfo=FUSO_SAO_PAULO)
