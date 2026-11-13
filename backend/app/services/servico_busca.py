"""
===============================================================================
ARQUIVO: servico_busca.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Reunir a busca global do portal: uma consulta que procura em vários módulos
(contratos, empresas, contratações, tarefas, pessoas e setores) e devolve
poucos resultados de cada um.

RESUMO TÉCNICO:
Cada módulo tem uma função privada (_contratos, _empresas, ...) que devolve
uma lista de ResultadoBusca. buscar() chama todas em sequência; cada bloco só
entra se o usuário tem ao menos LEITURA no recurso da ACL. Tarefas valem só
as do próprio usuário e contratações só as que ele enxerga. Um bloco que
falhar é registrado no log e ignorado (rollback da sessão), sem derrubar os outros.

FINALIDADE DE NEGÓCIO:
Deixa o servidor da SPI achar rapidamente um contrato, uma empresa, um
colega (ramal) ou uma tarefa a partir de uma caixa única, sem expor
informações de módulos a que ele não tem acesso.

CONTEXTO NO SISTEMA:
Usado pela rota de busca global (barra superior do frontend). Depende de
servico_acl (ACL = controle de acesso por recurso), servico_contratos,
servico_empresas, servico_setores, servico_diretorio (ramais), do acesso das
contratações e dos modelos de Tarefa. Resultado no schema ResultadoBusca.

===============================================================================
"""

import logging
from urllib.parse import quote

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.acl import NivelAcl
from app.models.tarefas import ResponsavelTarefa, Tarefa
from app.models.usuario import Usuario
from app.schemas.busca import ResultadoBusca
from app.services import servico_acl, servico_setores
from app.services.contratacoes import acesso as acesso_contratacoes
from app.services.contratos import servico_contratos, servico_empresas
from app.services.servico_diretorio import FiltrosRamais, listar_ramais

registro = logging.getLogger("sgi_spi.busca")
# Quantos resultados cada módulo devolve (a tela mostra tudo agrupado)
POR_MODULO = 5
# Abaixo disso a busca nem roda (termos de 1 letra trariam resultados demais).
MINIMO_CARACTERES = 2


def _pode(sessao: Session, usuario: Usuario, slug: str) -> bool:
    """O usuário tem ao menos LEITURA no recurso (recurso sem regras fica aberto, como no resto do sistema)."""
    # NivelAcl.posicao transforma o nível (nenhum, leitura, modificação, controle
    # total) num número, para poder comparar "tem pelo menos leitura".
    return NivelAcl.posicao(servico_acl.resolver_acesso(sessao, usuario, slug)) >= NivelAcl.posicao(NivelAcl.LEITURA)


def _contratos(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Contratos cujo número, apelido ou empresa batem com o termo (exige ACL "contratos")."""
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
    """Setores pelo nome (exige ACL "setores"); a rota leva à tela de setores."""
    if not _pode(sessao, usuario, "setores"):
        return []
    return [ResultadoBusca(tipo="setor", id=str(s.id), titulo=s.nome, subtitulo=s.setor_pai_nome or "", rota="/setores")
            for s in servico_setores.listar_setores(sessao, termo)[:POR_MODULO]]


def _pessoas(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Pessoas do diretório de ramais: abertas a todo usuário logado, sem checar ACL."""
    pagina = listar_ramais(sessao, usuario, FiltrosRamais(busca=termo), 1, POR_MODULO)
    return [ResultadoBusca(tipo="pessoa", id=str(p.id), titulo=p.nome, subtitulo=" · ".join(x for x in (p.setor, f"ramal {p.ramal}" if p.ramal else "") if x),
                           rota=f"/ramais?q={quote(p.nome)}") for p in pagina.itens]


def _tarefas(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Tarefas em que o usuário é criador ou responsável, por título ou número."""
    padrao = f"%{termo.lower()}%"
    # Subconsulta com as tarefas em que o usuário aparece como responsável adicional.
    participa = select(ResponsavelTarefa.tarefa_id).where(ResponsavelTarefa.usuario_id == usuario.id)
    consulta = (
        select(Tarefa)
        .where(or_(Tarefa.criado_por_id == usuario.id, Tarefa.responsavel_id == usuario.id, Tarefa.id.in_(participa)))
        # Procura no título (sem diferenciar maiúsculas) ou no número ("#12" vira "12").
        # Só tarefas principais: subtarefas (com tarefa_pai) ficam de fora.
        .where(or_(func.lower(Tarefa.titulo).like(padrao), cast(Tarefa.numero, String).like(padrao.replace("#", ""))), Tarefa.tarefa_pai_id.is_(None))
        .order_by(Tarefa.numero.desc())
        .limit(POR_MODULO)
    )
    return [ResultadoBusca(tipo="tarefa", id=str(t.numero), titulo=f"#{t.numero} · {t.titulo}", subtitulo=t.status.replace("_", " "), rota=f"/tarefas/{t.numero}")
            for t in sessao.scalars(consulta)]


def _contratacoes(sessao: Session, usuario: Usuario, termo: str) -> list[ResultadoBusca]:
    """Contratações (documentos) visíveis ao usuário, pelo nome ou número do processo."""
    if not _pode(sessao, usuario, "contratacoes"):
        return []
    # Import dentro da função para evitar import circular entre os módulos.
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
    # Ordem dos blocos = ordem dos grupos na tela. Cada bloco num try próprio: o
    # rollback limpa a sessão depois de um erro para os blocos seguintes funcionarem.
    for bloco in (_contratos, _empresas, _contratacoes, _tarefas, _pessoas, _setores):
        try:
            resultados.extend(bloco(sessao, usuario, termo))
        except Exception:  # noqa: BLE001 — um módulo com problema não pode derrubar a busca inteira
            registro.exception("Falha na busca global (%s)", bloco.__name__)
            sessao.rollback()
    return resultados
