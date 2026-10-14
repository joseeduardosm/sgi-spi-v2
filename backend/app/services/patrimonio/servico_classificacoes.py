# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras de classificação de bens como inservíveis ou extraviados (lista, justificativa, aprovação e reversão).
"""Classificação em inservível ou extraviado.

O usuário (modificação) monta uma lista, justifica (mínimo de 10 caracteres, para vários bens de uma vez ou um a um) e envia. Enquanto isso
os bens ficam com "Classificação pendente" e não se movimentam. O controle total (nunca o próprio solicitante) aprova tudo, parte ou recusa.
Só o controle total devolve um inservível/extraviado a Ativo, com justificativa (e a sala onde o extraviado foi achado).
"""

import uuid
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.patrimonio import Bem, Classificacao, ItemClassificacao
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.patrimonio import servico_bens, servico_localizacoes
from app.services.patrimonio.base import ErroPatrimonio, avisar, exigir_outra_pessoa, ids_controle_total, registrar_evento

TIPOS = ("inservivel", "extraviado")
MINIMO_JUSTIFICATIVA = 10
CARGA = (selectinload(Classificacao.itens).selectinload(ItemClassificacao.bem), selectinload(Classificacao.itens).selectinload(ItemClassificacao.anexo),
         selectinload(Classificacao.solicitante), selectinload(Classificacao.decidido_por))


def obter(sessao: Session, classificacao_id: uuid.UUID) -> Classificacao:
    lista = sessao.scalar(select(Classificacao).where(Classificacao.id == classificacao_id).options(*CARGA))
    if lista is None:
        raise ErroPatrimonio("Lista de classificação não encontrada.", 404, "nao_encontrado")
    return lista


def listar(sessao: Session, *, status: str | None = None, solicitante_id: int | None = None) -> list[Classificacao]:
    consulta = select(Classificacao).options(*CARGA).order_by(Classificacao.criada_em.desc())
    if status:
        consulta = consulta.where(Classificacao.status == status)
    if solicitante_id:
        consulta = consulta.where(Classificacao.solicitante_id == solicitante_id)
    return list(sessao.scalars(consulta))


def criar(sessao: Session, tipo: str, autor: Usuario, *, id_cliente: str | None = None) -> tuple[Classificacao, bool]:
    if tipo not in TIPOS:
        raise ErroPatrimonio("O tipo é \"inservivel\" ou \"extraviado\".")
    if id_cliente:
        existente = sessao.scalar(select(Classificacao.id).where(Classificacao.id_cliente == id_cliente))
        if existente is not None:
            return obter(sessao, existente), False
    lista = Classificacao(id=uuid.uuid4(), id_cliente=id_cliente, tipo=tipo, status="rascunho", solicitante_id=autor.id)
    sessao.add(lista)
    sessao.commit()
    return obter(sessao, lista.id), True


def _editavel(lista: Classificacao, autor: Usuario) -> None:
    if lista.status != "rascunho":
        raise ErroPatrimonio("A lista já foi enviada: não pode mais ser alterada.", 409, "conflito")
    if lista.solicitante_id != autor.id:
        raise ErroPatrimonio("Só quem montou a lista a altera.", 403, "acl_negado")


def adicionar_bem(sessao: Session, classificacao_id: uuid.UUID, autor: Usuario, *, bem_id: uuid.UUID | None = None, chapa: str | None = None) -> Classificacao:
    """Entra pela chapa (leitura ou digitação) ou pelo bem escolhido na lista da sala. Bem fora de Ativo/Em manutenção é recusado com aviso."""
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    bem = servico_bens.obter(sessao, bem_id) if bem_id else servico_bens.obter_por_chapa(sessao, chapa or "")
    if bem.situacao not in ("ativo", "em_manutencao"):
        raise ErroPatrimonio(f"O bem {bem.rotulo} está {bem.situacao.replace('_', ' ')} e não pode ser classificado.", 409, "bem_invalido")
    if bem.classificacao_pendente:
        raise ErroPatrimonio(f"O bem {bem.rotulo} já tem uma classificação pendente.", 409, "classificacao_pendente")
    if servico_bens.em_movimentacao(sessao, bem.id):
        raise ErroPatrimonio(f"O bem {bem.rotulo} está em uma movimentação em andamento.", 409, "em_movimentacao")
    if any(i.bem_id == bem.id for i in lista.itens):
        raise ErroPatrimonio(f"O bem {bem.rotulo} já está na lista.", 409, "conflito")
    lista.itens.append(ItemClassificacao(id=uuid.uuid4(), bem_id=bem.id, situacao_anterior=bem.situacao))
    sessao.commit()
    return obter(sessao, lista.id)


def remover_bem(sessao: Session, classificacao_id: uuid.UUID, item_id: uuid.UUID, autor: Usuario) -> Classificacao:
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    item = next((i for i in lista.itens if i.id == item_id), None)
    if item is None:
        raise ErroPatrimonio("Item não encontrado.", 404, "nao_encontrado")
    lista.itens.remove(item)
    sessao.commit()
    return obter(sessao, lista.id)


def justificar(sessao: Session, classificacao_id: uuid.UUID, itens_ids: list[uuid.UUID], justificativa: str, autor: Usuario) -> Classificacao:
    """A mesma justificativa vale para todos os itens marcados (ex.: doze nobreaks "baterias sem carga, conserto inviável")."""
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    texto = (justificativa or "").strip()
    if len(texto) < MINIMO_JUSTIFICATIVA:
        raise ErroPatrimonio(f"A justificativa precisa ter ao menos {MINIMO_JUSTIFICATIVA} caracteres.")
    marcados = [i for i in lista.itens if i.id in set(itens_ids)]
    if not marcados:
        raise ErroPatrimonio("Marque ao menos um bem da lista.")
    for item in marcados:
        item.justificativa = texto
    sessao.commit()
    return obter(sessao, lista.id)


def anexar(sessao: Session, classificacao_id: uuid.UUID, item_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> Classificacao:
    """Extraviado: anexo opcional (boletim de ocorrência, e-mail ou foto). Inservível: foto opcional."""
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    item = next((i for i in lista.itens if i.id == item_id), None)
    if item is None:
        raise ErroPatrimonio("Item não encontrado.", 404, "nao_encontrado")
    if lista.tipo == "inservivel" and not nome.lower().endswith((".png", ".jpg", ".jpeg")):
        raise ErroPatrimonio("No inservível, o anexo é uma foto (PNG ou JPG).")
    try:
        anexo = servico_anexos.guardar_arquivo(sessao, arquivo, nome, "patrimonio-classificacao", autor.id)
    except servico_anexos.ErroAnexo as erro:
        raise ErroPatrimonio(str(erro)) from erro
    sessao.flush()
    item.anexo_id = anexo.id
    sessao.commit()
    return obter(sessao, lista.id)


def descartar(sessao: Session, classificacao_id: uuid.UUID, autor: Usuario) -> None:
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    sessao.delete(lista)
    sessao.commit()


def enviar(sessao: Session, classificacao_id: uuid.UUID, autor: Usuario) -> Classificacao:
    lista = obter(sessao, classificacao_id)
    _editavel(lista, autor)
    if not lista.itens:
        raise ErroPatrimonio("A lista está vazia.")
    sem = [i.bem.rotulo for i in lista.itens if not i.justificativa]
    if sem:
        raise ErroPatrimonio(f"Falta justificativa para: {', '.join(sem[:10])}.", 409, "sem_justificativa")
    for item in lista.itens:
        bem = servico_bens.obter(sessao, item.bem_id)
        if bem.classificacao_pendente or bem.situacao not in ("ativo", "em_manutencao"):
            raise ErroPatrimonio(f"O bem {bem.rotulo} não pode mais ser classificado.", 409, "bem_invalido")
        bem.classificacao_pendente = True
        registrar_evento(sessao, bem, "classificacao_pendente", autor, texto=f"Incluído em lista de {lista.tipo} aguardando aprovação")
    lista.status, lista.enviada_em = "pendente", agora_utc()
    avisar(sessao, ids_controle_total(sessao), f"Classificação de {lista.tipo}s aguardando aprovação",
           f"{autor.nome_completo or autor.login} enviou {len(lista.itens)} bem(ns).", f"patrimonio-cla-{lista.id}", autor, f"/patrimonio/{'extraviados' if lista.tipo == 'extraviado' else 'inserviveis'}/{lista.id}", categoria="pendencia", evento="patrimonio.classificacao_pendente")
    sessao.commit()
    return obter(sessao, lista.id)


def decidir(sessao: Session, classificacao_id: uuid.UUID, aprovados_ids: list[uuid.UUID], motivo_recusa: str | None, autor: Usuario) -> Classificacao:
    """Aprova os itens indicados e recusa os demais (a recusa exige motivo). Os aprovados mudam de situação; os recusados voltam ao que eram."""
    lista = obter(sessao, classificacao_id)
    if lista.status != "pendente":
        raise ErroPatrimonio("A lista não está pendente.", 409, "conflito")
    exigir_outra_pessoa(autor, lista.solicitante_id)
    aprovados = set(aprovados_ids)
    recusados = [i for i in lista.itens if i.id not in aprovados]
    if recusados and not (motivo_recusa and motivo_recusa.strip()):
        raise ErroPatrimonio("A recusa exige motivo.")
    for item in lista.itens:
        bem = servico_bens.obter(sessao, item.bem_id)
        bem.classificacao_pendente = False
        if item.id in aprovados:
            item.resultado = "aprovado"
            registrar_evento(sessao, bem, "classificou", autor, campo="situacao", anterior=bem.situacao, novo=lista.tipo, texto=item.justificativa or "",
                             dados={"solicitante": lista.solicitante.login if lista.solicitante else None, "autorizador": autor.login, "ultima_sala": bem.localizacao.codigo})
            bem.situacao = lista.tipo
        else:
            item.resultado = "recusado"
            registrar_evento(sessao, bem, "classificacao_recusada", autor, texto=f"Classificação como {lista.tipo} recusada: {motivo_recusa.strip()}")
    lista.status = "aprovada" if not recusados else "recusada" if not aprovados else "parcial"
    lista.decidido_por_id, lista.decidido_em, lista.motivo_recusa = autor.id, agora_utc(), (motivo_recusa or "").strip() or None
    avisar(sessao, [lista.solicitante_id] if lista.solicitante_id else [], "Classificação decidida", f"Resultado: {lista.status}.", f"patrimonio-cla-dec-{lista.id}", autor,
           f"/patrimonio/{'extraviados' if lista.tipo == 'extraviado' else 'inserviveis'}/{lista.id}", evento="patrimonio.classificacao_decidida")
    sessao.commit()
    return obter(sessao, lista.id)


def reverter(sessao: Session, bem_id: uuid.UUID, justificativa: str, autor: Usuario, *, localizacao_id: uuid.UUID | None = None) -> Bem:
    """Devolve um inservível (voltou a ser usado) ou extraviado (foi encontrado) a Ativo. Só o controle total; o extraviado informa a sala do achado."""
    bem = servico_bens.obter(sessao, bem_id)
    if bem.situacao not in ("inservivel", "extraviado"):
        raise ErroPatrimonio("Só inservíveis e extraviados podem ser devolvidos a Ativo.", 409, "conflito")
    texto = (justificativa or "").strip()
    if len(texto) < MINIMO_JUSTIFICATIVA:
        raise ErroPatrimonio(f"A justificativa precisa ter ao menos {MINIMO_JUSTIFICATIVA} caracteres.")
    if bem.situacao == "extraviado":
        if localizacao_id is None:
            raise ErroPatrimonio("Informe a sala onde o bem foi encontrado.")
        destino = servico_localizacoes.exigir_sala(sessao, localizacao_id)
        if destino.responsavel_id is None:
            raise ErroPatrimonio("A sala informada ainda não tem setor e responsável.", 409, "sala_sem_responsavel")
        if bem.localizacao_id != destino.id:
            servico_bens.mover_para(sessao, bem, destino, autor, "reverteu", f"Encontrado: {texto}", {"autorizador": autor.login})
    registrar_evento(sessao, bem, "reverteu", autor, campo="situacao", anterior=bem.situacao, novo="ativo", texto=texto)
    bem.situacao = "ativo"
    sessao.commit()
    return servico_bens.obter(sessao, bem.id)
