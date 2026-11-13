"""
===============================================================================
ARQUIVO: servico_rascunhos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Guardar, ler e apagar os rascunhos compartilhados dos formulários do contrato
(diário, avaliação e medição) no servidor.

RESUMO TÉCNICO:
Um rascunho por tela de um contrato, identificado por (contrato, tipo, chave):
o diário não tem chave; avaliação e medição usam o id da competência. Ler
exige acesso a Contratos (a rota cobra a ACL); gravar e apagar exigem poder
editar o contrato. A gravação usa controle de versão otimista: se alguém
salvou depois da versão que o autor abriu, recusa com conflito (409). O HTML
do diário é sanitizado e o tamanho é limitado a TAMANHO_MAXIMO caracteres.

FINALIDADE DE NEGÓCIO:
Evita que a equipe perca o que digitou num formulário longo e permite que um
integrante continue o rascunho de outro, sem que um sobrescreva o trabalho do
colega sem perceber.

CONTEXTO NO SISTEMA:
Chamado pelas rotas de rascunho de contratos. Modelo RascunhoContrato
(tabela de rascunhos), schema GravacaoRascunho, servico_contratos (permissão),
tarefas.descricao (sanitização do HTML) e servico_auditoria.

===============================================================================
"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos.rascunho import RascunhoContrato
from app.models.usuario import Usuario
from app.schemas.contratos.rascunho import GravacaoRascunho
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato
from app.services.servico_auditoria import auditar
from app.services.tarefas.descricao import sanitizar_descricao

# Limite do rascunho serializado em JSON (caracteres), para não encher o banco com um formulário gigante
TAMANHO_MAXIMO = 300_000


def _chave_valida(contrato, tipo: str, chave: str) -> str:
    """Diário não tem chave; avaliação e medição usam o id de uma competência do contrato."""
    chave = (chave or "").strip()
    if tipo == "diario":
        return ""
    if not any(str(c.id) == chave for c in contrato.competencias):
        raise RegistroNaoEncontrado("Competência")
    return chave


def _buscar(sessao: Session, contrato_id: uuid.UUID, tipo: str, chave: str) -> RascunhoContrato | None:
    """Rascunho de (contrato, tipo, chave), ou None se ainda não houver."""
    return sessao.scalar(select(RascunhoContrato).where(RascunhoContrato.contrato_id == contrato_id, RascunhoContrato.tipo == tipo, RascunhoContrato.chave == chave))


def obter(sessao: Session, contrato_id: uuid.UUID, tipo: str, chave: str) -> RascunhoContrato | None:
    """Lê o rascunho da tela; valida antes que a chave é uma competência do contrato (404 se não for)."""
    contrato = obter_contrato(sessao, contrato_id)
    return _buscar(sessao, contrato.id, tipo, _chave_valida(contrato, tipo, chave))


def gravar(sessao: Session, contrato_id: uuid.UUID, tipo: str, chave: str, dados: GravacaoRascunho, autor: Usuario) -> RascunhoContrato:
    """Cria o rascunho ou grava por cima; recusa (`409`) se outra pessoa salvou depois da versão que o autor viu."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    chave = _chave_valida(contrato, tipo, chave)
    conteudo = dict(dados.dados)
    # O relato do diário é HTML do editor rico: sanitizado já aqui, como na ocorrência registrada
    if isinstance(conteudo.get("descricao"), str):
        conteudo["descricao"] = sanitizar_descricao(conteudo["descricao"])
    if len(json.dumps(conteudo, ensure_ascii=False, default=str)) > TAMANHO_MAXIMO:
        raise ErroRegraContrato("O rascunho é grande demais para ser salvo.")
    atual = _buscar(sessao, contrato.id, tipo, chave)
    # Controle otimista: a versão que o autor abriu tem de ser a versão gravada agora (0 = ainda não existia)
    if (dados.versao or 0) != (atual.versao if atual else 0):
        quem = f"{atual.atualizado_por_nome} salvou" if atual else "O rascunho foi apagado"
        raise ErroRegraContrato(f"{quem} um rascunho mais novo depois do que você abriu. Recarregue para ver antes de salvar por cima.", conflito=True)
    nome = autor.nome_completo or autor.login
    if atual is None:
        atual = RascunhoContrato(contrato_id=contrato.id, tipo=tipo, chave=chave, dados=conteudo, versao=1, atualizado_por_id=autor.id, atualizado_por_nome=nome)
        sessao.add(atual)
    else:
        atual.dados, atual.versao, atual.atualizado_em, atual.atualizado_por_id, atual.atualizado_por_nome = conteudo, atual.versao + 1, agora_utc(), autor.id, nome
    auditar(sessao, autor.login, "contrato.rascunho.salvar", f"Contrato {contrato.numero}", tipo, autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()
    return atual


def excluir(sessao: Session, contrato_id: uuid.UUID, tipo: str, chave: str, autor: Usuario) -> None:
    """Apaga o rascunho (quem edita o contrato). Sem rascunho, não há o que apagar (`404`)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    atual = _buscar(sessao, contrato.id, tipo, _chave_valida(contrato, tipo, chave))
    if atual is None:
        raise RegistroNaoEncontrado("Rascunho")
    auditar(sessao, autor.login, "contrato.rascunho.excluir", f"Contrato {contrato.numero}", tipo, autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.delete(atual)
    sessao.commit()
