"""
===============================================================================
ARQUIVO: servico_eventos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Montar a aba "Eventos" do contrato: tudo o que a auditoria registrou sobre ele,
com nome em linguagem de usuário, categoria, filtro, busca, ordenação e
paginação; nos eventos de conclusão, o estado do botão "Tornar sem efeito".

RESUMO TÉCNICO:
- Lê `auditoria` com `alvo_tipo = 'contrato'` e `alvo_id = <id>` (um contrato
  tem centenas a poucos milhares de registros: filtro, busca e ordenação são
  feitos em memória, depois da leitura).
- Nome e categoria vêm de `eventos_catalogo`; o autor vira o nome completo.
- Nas conclusões (reajuste, repactuação, aditamento/supressão, prorrogação e
  vigência retroativa) acha o registro pelo `registro_id` gravado na
  auditoria ou, nos registros antigos, pela data de conclusão (gravada na
  mesma transação) e pergunta a `servico_sem_efeito.verificar` se pode.

FINALIDADE DE NEGÓCIO:
Decisão do usuário (13/11/2026): quem tem Controle total vê todos os eventos
do contrato, com chips por categoria e barra de pesquisa, e pode tornar sem
efeito o que for permitido.

CONTEXTO NO SISTEMA:
Rota GET /contratos/{id}/eventos (api/routes/contratos/contratos.py), exigindo
ACL `contratos` = CONTROLE_TOTAL; tela: aba-eventos.component.ts.

===============================================================================
"""

import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auditoria import RegistroAuditoria
from app.models.usuario import Usuario
from app.schemas.contratos.eventos import EventoContrato, PaginaEventosContrato
from app.services.contratos import eventos_catalogo
from app.services.contratos.servico_contratos import obter_contrato
from app.services.contratos.servico_sem_efeito import verificar

# Diferença máxima entre a hora da auditoria e a da conclusão gravada no registro (mesma transação)
TOLERANCIA = timedelta(seconds=10)
ORDENS = ("ocorrido_em", "evento", "autor", "detalhe")


def _sem_acento(texto: str) -> str:
    """Minúsculas e sem acento, para a busca ("Repactuação" acha "repactuacao")."""
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def _utc(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


def _detalhe(registro: RegistroAuditoria) -> str:
    """Resumo legível: o motivo (se houver), os campos de/para e, por fim, a descrição gravada."""
    dados = registro.dados or {}
    partes = []
    if dados.get("motivo"):
        partes.append(f"Motivo: {dados['motivo']}")
    campos = dados.get("campos") or {}
    if isinstance(campos, dict):
        for nome, valor in list(campos.items())[:4]:
            if isinstance(valor, dict) and ("de" in valor or "para" in valor):
                partes.append(f"{nome.replace('_', ' ')}: {valor.get('de') or '—'} → {valor.get('para') or '—'}")
    if dados.get("justificativa"):
        partes.append(f"Justificativa: {dados['justificativa']}")
    if not partes and registro.detalhes:
        partes.append(registro.detalhes)
    return " · ".join(str(p) for p in partes)[:500]


def _registros_do_tipo(contrato, tipo: str) -> list:
    return {"reajustes": contrato.reajustes, "repactuacoes": contrato.repactuacoes, "alteracoes": contrato.alteracoes,
            "prorrogacoes": contrato.prorrogacoes, "vigencias-retroativas": contrato.vigencias_retroativas}[tipo]


def _quando(registro) -> datetime | None:
    """Data da conclusão gravada no registro (ou da criação, na prorrogação e na vigência retroativa)."""
    return _utc(getattr(registro, "concluido_em", None) or getattr(registro, "concluida_em", None) or getattr(registro, "criado_em", None))


def _achar_registro(contrato, tipo: str, auditoria: RegistroAuditoria):
    """O registro de uma conclusão: pelo `registro_id` gravado ou pela data de conclusão (registros antigos)."""
    lista = _registros_do_tipo(contrato, tipo)
    registro_id = (auditoria.dados or {}).get("registro_id")
    if registro_id:
        return next((r for r in lista if str(r.id) == str(registro_id)), None)
    ocorrido = _utc(auditoria.ocorrido_em)
    candidatos = [r for r in lista if _quando(r) is not None and abs(_quando(r) - ocorrido) <= TOLERANCIA]
    return min(candidatos, key=lambda r: abs(_quando(r) - ocorrido)) if candidatos else None


def listar(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario, categoria: str | None = None, busca: str = "",
           ordem: str = "ocorrido_em", sentido: str = "desc", pagina: int = 1, por_pagina: int = 50) -> PaginaEventosContrato:
    """Eventos do contrato filtrados, buscados, ordenados e paginados."""
    contrato = obter_contrato(sessao, contrato_id)
    registros = list(sessao.scalars(select(RegistroAuditoria).where(RegistroAuditoria.alvo_tipo == "contrato",
                                                                   RegistroAuditoria.alvo_id == str(contrato.id))))
    # Nome completo de cada autor (uma consulta só)
    ids = {r.autor_id for r in registros if r.autor_id}
    nomes = {u.id: u.nome_completo or u.login for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))} if ids else {}
    linhas = []
    for r in registros:
        linhas.append(EventoContrato(
            id=r.id, ocorrido_em=r.ocorrido_em, acao=r.acao, evento=eventos_catalogo.rotulo(r.acao), categoria=eventos_catalogo.categoria(r.acao),
            autor=nomes.get(r.autor_id) or r.autor, detalhe=_detalhe(r)))
    # Busca (sem acento e sem diferença de maiúsculas) em nome, autor, detalhe e no conteúdo gravado
    termo = _sem_acento(busca.strip())
    if termo:
        dados = {r.id: _sem_acento(str(r.dados or "")) for r in registros}
        linhas = [e for e in linhas if termo in _sem_acento(f"{e.evento} {e.autor} {e.detalhe} {e.acao}") or termo in dados[e.id]]
    por_categoria = {c: sum(1 for e in linhas if e.categoria == c) for c in eventos_catalogo.CATEGORIAS}
    if categoria:
        linhas = [e for e in linhas if e.categoria == categoria]
    # Ordenação: texto sem acento; data pelo valor; empate desempata pelo número do registro
    ordem = ordem if ordem in ORDENS else "ocorrido_em"
    chave = (lambda e: (_utc(e.ocorrido_em), e.id)) if ordem == "ocorrido_em" else (lambda e: (_sem_acento(getattr(e, ordem)), e.id))
    linhas.sort(key=chave, reverse=sentido == "desc")
    total = len(linhas)
    por_pagina = max(1, min(por_pagina, 200))
    pagina = max(1, pagina)
    itens = linhas[(pagina - 1) * por_pagina: pagina * por_pagina]
    # Só a página exibida passa pela verificação do botão (ela olha medições, créditos e eventos posteriores)
    por_id = {r.id: r for r in registros}
    for e in itens:
        tipo = eventos_catalogo.CONCLUSOES.get(e.acao)
        if tipo is None:
            continue
        registro = _achar_registro(contrato, tipo, por_id[e.id])
        e.registro_tipo = tipo
        if registro is None:
            # Prorrogação e vigência retroativa somem quando desfeitas
            e.sem_efeito = tipo in ("prorrogacoes", "vigencias-retroativas")
            continue
        e.registro_id = registro.id
        e.sem_efeito = getattr(registro, "situacao", "") == "sem_efeito"
        if not e.sem_efeito:
            e.pode_tornar_sem_efeito, e.motivo_bloqueio = verificar(sessao, contrato, registro, usuario)
    return PaginaEventosContrato(itens=itens, total=total, pagina=pagina, por_pagina=por_pagina, por_categoria=por_categoria)
