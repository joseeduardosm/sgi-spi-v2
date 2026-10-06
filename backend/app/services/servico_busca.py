# Criado por José Eduardo Santana Martins
# Este arquivo serve para reunir a busca global do portal (contratos, pessoas, setores, tarefas e contratações) respeitando o ACL.
"""Busca global: uma consulta que procura em vários módulos e devolve poucos resultados de cada um.

Cada bloco só entra se o usuário tem pelo menos LEITURA no recurso do módulo (ACL); tarefas valem só as do próprio usuário
(criadas, atribuídas ou em que participa) e contratações só as que ele enxerga. Pessoas vêm do diretório de ramais, aberto a todo usuário logado.
Cada bloco é independente: a falha de um não derruba os demais.
"""

import logging
from urllib.parse import quote

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl
from app.models.tarefas import ParticipanteTarefa, Tarefa
from app.models.usuario import Usuario
from app.schemas.busca import ResultadoBusca
from app.services import servico_acl, servico_setores
from app.services.contratacoes import acesso as acesso_contratacoes
from app.services.contratos import servico_contratos, servico_empresas
from app.services.servico_diretorio import FiltrosRamais, listar_ramais

registro = logging.getLogger("sgi_spi.busca")
# Quantos resultados cada módulo devolve (a tela mostra tudo agrupado)
POR_MODULO = 5
MINIMO_CARACTERES = 2


def _pode(sessao: Session, usuario: Usuario, slug: str) -> bool:
    """O usuário tem ao menos LEITURA no recurso (recurso sem regras fica aberto, como no resto do sistema)."""
    return NivelAcl.posicao(servico_acl.resolver_acesso(sessao, usuario, slug)) >= NivelAcl.posicao(NivelAcl.LEITURA)


def _contratos(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    if not _pode(sessao, usuario, "contratos"):
        return []
    pagina = servico_contratos.listar_contratos(sessao, termo, 1, POR_MODULO)
    return [ResultadoBusca(tipo="contrato", id=str(c.id), titulo=f"Contrato {c.numero}" + (f" · {c.apelido.upper()}" if c.apelido else ""),
                           subtitulo=c.empresa_razao_social, rota=f"/contratos/{c.id}") for c in pagina.itens]


def _empresas(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Empresas contratadas (razão social, nome fantasia, CNPJ, endereço e nome dos prepostos), com o mesmo acesso dos contratos."""
    if not _pode(sessao, usuario, "contratos"):
        return []
    pagina = servico_empresas.listar_empresas(sessao, termo, "razao_social", "asc", 1, POR_MODULO)
    return [ResultadoBusca(tipo="empresa", id=str(e.id), titulo=e.razao_social,
                           subtitulo=" · ".join(x for x in (f"CNPJ {e.cnpj}", f"{len(e.contratos)} contrato(s)" if e.contratos else "", "" if e.ativa else "inativa") if x),
                           rota=f"/contratos/empresas/{e.id}") for e in pagina.itens]


def _setores(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    if not _pode(sessao, usuario, "setores"):
        return []
    return [ResultadoBusca(tipo="setor", id=str(s.id), titulo=s.nome, subtitulo=s.setor_pai_nome or "", rota="/setores")
            for s in servico_setores.listar_setores(sessao, termo)[:POR_MODULO]]


def _pessoas(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    pagina = listar_ramais(sessao, usuario, FiltrosRamais(busca=termo), 1, POR_MODULO)
    return [ResultadoBusca(tipo="pessoa", id=str(p.id), titulo=p.nome, subtitulo=" · ".join(x for x in (p.setor, f"ramal {p.ramal}" if p.ramal else "") if x),
                           rota=f"/ramais?q={quote(p.nome)}") for p in pagina.itens]


def _tarefas(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Tarefas em que o usuário é criador, responsável ou participante, por título ou número."""
    padrao = f"%{termo.lower()}%"
    participa = select(ParticipanteTarefa.tarefa_id).where(ParticipanteTarefa.usuario_id == usuario.id)
    consulta = (
        select(Tarefa)
        .where(or_(Tarefa.criado_por_id == usuario.id, Tarefa.responsavel_id == usuario.id, Tarefa.id.in_(participa)))
        .where(or_(func.lower(Tarefa.titulo).like(padrao), cast(Tarefa.numero, String).like(padrao.replace("#", ""))))
        .order_by(Tarefa.numero.desc())
        .limit(POR_MODULO)
    )
    return [ResultadoBusca(tipo="tarefa", id=str(t.numero), titulo=f"#{t.numero} · {t.titulo}", subtitulo=t.status.replace("_", " "), rota=f"/tarefas/{t.numero}")
            for t in sessao.scalars(consulta)]


def _contratacoes(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    if not _pode(sessao, usuario, "contratacoes"):
        return []
    from app.models.contratacoes import DocumentoContratacao

    padrao = f"%{termo.lower()}%"
    consulta = (
        acesso_contratacoes.visiveis(sessao, usuario)
        .where(or_(func.lower(DocumentoContratacao.nome).like(padrao), func.lower(DocumentoContratacao.processo).like(padrao)))
        .order_by(DocumentoContratacao.atualizado_em.desc())
        .limit(POR_MODULO)
    )
    return [ResultadoBusca(tipo="contratacao", id=str(d.id), titulo=d.nome, subtitulo=f"{d.tipo.upper()}" + (f" · {d.processo}" if d.processo else ""),
                           rota=f"/contratacoes/{d.id}") for d in sessao.scalars(consulta)]


def buscar(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Resultados de todos os módulos para o termo (vazio se tiver menos de 2 caracteres)."""
    termo = (termo or "").strip()
    if len(termo) < MINIMO_CARACTERES:
        return []
    resultados: list[ResultadoBusca] = []
    for bloco in (_contratos, _empresas, _contratacoes, _tarefas, _pessoas, _setores):
        try:
            resultados.extend(bloco(sessao, usuario, termo))
        except Exception:  # noqa: BLE001 — um módulo com problema não pode derrubar a busca inteira
            registro.exception("Falha na busca global (%s)", bloco.__name__)
            sessao.rollback()
    return resultados
