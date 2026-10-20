# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras da baixa de bens inservíveis ou extraviados (lista, motivo, processo, aprovação e termo em PDF).
"""Baixa.

Nasce de **uma lista de inservíveis (ou extraviados) já aprovada** e herda os bens aprovados dela (uma lista por baixa; o mesmo PDF do de acordo pode ser
anexado em várias baixas). O usuário informa motivo (alienação, doação, transferência, inutilização ou extravio) e número do processo, para a seleção toda
ou por grupos de bens, e envia: o sistema gera o **termo em PDF** (para instruir o SEI) e a baixa fica **aguardando o aceite da autoridade**, que é externa.
Quem tem controle total (gestores do patrimônio) **conclui anexando o PDF do de acordo da autoridade**, na maioria das vezes a publicação no D.O.E.: os bens
viram **Baixado**. O bem baixado sai dos painéis, mas nunca é excluído. A baixa aqui não baixa o bem no SAM: o termo serve para fazer isso lá.
"""

import uuid
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.patrimonio import Baixa, Bem, Classificacao, EventoPatrimonio, ItemBaixa, ItemClassificacao
from app.models.usuario import Usuario
from app.models.patrimonio import ColaboradorBaixa
from app.services import servico_anexos
from app.services.patrimonio.numeracao import proximo_numero_relacao
from app.services.documentos.pdf import DocumentoPdf
from app.services.patrimonio import servico_bens
from app.services.patrimonio.base import ErroPatrimonio, avisar, ids_controle_total, nome_do_autor, registrar_evento

MOTIVOS = {"alienacao": "Alienação", "doacao": "Doação", "transferencia": "Transferência", "inutilizacao": "Inutilização", "extravio": "Extravio"}
CARGA = (selectinload(Baixa.itens).selectinload(ItemBaixa.bem).selectinload(Bem.localizacao), selectinload(Baixa.itens).selectinload(ItemBaixa.bem).selectinload(Bem.grupo),
         selectinload(Baixa.solicitante), selectinload(Baixa.decidido_por), selectinload(Baixa.colaboradores))


def obter(sessao: Session, baixa_id: uuid.UUID) -> Baixa:
    baixa = sessao.scalar(select(Baixa).where(Baixa.id == baixa_id).options(*CARGA))
    if baixa is None:
        raise ErroPatrimonio("Baixa não encontrada.", 404, "nao_encontrado")
    return baixa


def listar(sessao: Session, *, status: str | None = None, solicitante_id: int | None = None) -> list[Baixa]:
    consulta = select(Baixa).options(*CARGA).order_by(Baixa.criada_em.desc())
    if status:
        consulta = consulta.where(Baixa.status == status)
    if solicitante_id:
        # "Minhas baixas": as que a pessoa montou e as compartilhadas com ela
        consulta = consulta.where((Baixa.solicitante_id == solicitante_id) | Baixa.colaboradores.any(ColaboradorBaixa.usuario_id == solicitante_id))
    return list(sessao.scalars(consulta))


def criar(sessao: Session, autor: Usuario, *, classificacao_id: uuid.UUID, id_cliente: str | None = None) -> tuple[Baixa, bool]:
    """Começa a baixa herdando os bens aprovados de uma lista de inservíveis/extraviados já aprovada (uma baixa ativa por lista)."""
    if id_cliente:
        existente = sessao.scalar(select(Baixa.id).where(Baixa.id_cliente == id_cliente))
        if existente is not None:
            return obter(sessao, existente), False
    lista = sessao.scalar(select(Classificacao).where(Classificacao.id == classificacao_id).options(selectinload(Classificacao.itens).selectinload(ItemClassificacao.bem)))
    if lista is None:
        raise ErroPatrimonio("Lista de origem não encontrada.", 404, "nao_encontrado")
    if lista.status not in ("aprovada", "parcial"):
        raise ErroPatrimonio("A baixa só nasce de uma lista aprovada (ou aprovada em parte).", 409, "lista_nao_aprovada")
    if sessao.scalar(select(Baixa.id).where(Baixa.classificacao_origem_id == lista.id, Baixa.status != "recusada")) is not None:
        raise ErroPatrimonio("Esta lista já tem uma baixa. O mesmo PDF do de acordo pode ser anexado em várias baixas, mas cada lista tem uma só.", 409, "conflito")
    bens = [i.bem for i in lista.itens if i.resultado == "aprovado" and i.bem.situacao in ("inservivel", "extraviado")]
    if not bens:
        raise ErroPatrimonio("A lista não tem bem aprovado que ainda possa ser baixado.", 409, "sem_bens")
    baixa = Baixa(id=uuid.uuid4(), id_cliente=id_cliente, numero=proximo_numero_relacao(sessao), status="rascunho", solicitante_id=autor.id, classificacao_origem_id=lista.id)
    for bem in bens:
        baixa.itens.append(ItemBaixa(id=uuid.uuid4(), bem_id=bem.id, situacao_anterior=bem.situacao))
    sessao.add(baixa)
    sessao.commit()
    return obter(sessao, baixa.id), True


def _editavel(baixa: Baixa, autor: Usuario) -> None:
    if baixa.status != "rascunho":
        raise ErroPatrimonio("A baixa já foi enviada: não pode mais ser alterada.", 409, "conflito")
    # Quem montou e quem recebeu a baixa compartilhada têm os mesmos poderes sobre ela
    if baixa.solicitante_id != autor.id and autor.id not in baixa.colaboradores_ids:
        raise ErroPatrimonio("Só quem montou a baixa, ou quem recebeu a baixa compartilhada, a altera.", 403, "acl_negado")


def definir_colaboradores(sessao: Session, baixa_id: uuid.UUID, usuarios_ids: list[int], autor: Usuario) -> Baixa:
    """Compartilha a baixa (em rascunho) com as pessoas indicadas, substituindo as anteriores; só quem a montou decide com quem compartilha.

    Quem recebe faz tudo o que o solicitante faz, inclusive enviá-la para aprovação. Por isso não pode, depois, aprová-la.
    """
    baixa = obter(sessao, baixa_id)
    if baixa.status != "rascunho":
        raise ErroPatrimonio("A baixa já foi enviada: não é mais possível compartilhá-la.", 409, "conflito")
    if baixa.solicitante_id != autor.id:
        raise ErroPatrimonio("Só quem montou a baixa escolhe com quem compartilhá-la.", 403, "acl_negado")
    novos = set(usuarios_ids) - {autor.id}
    if novos and set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(novos), Usuario.ativo.is_(True)))) != novos:
        raise ErroPatrimonio("Há usuário inexistente ou inativo na lista de colaboradores.")
    antigos = baixa.colaboradores_ids
    for colaborador in [c for c in baixa.colaboradores if c.usuario_id not in novos]:
        baixa.colaboradores.remove(colaborador)
    for usuario_id in novos - antigos:
        baixa.colaboradores.append(ColaboradorBaixa(baixa_id=baixa.id, usuario_id=usuario_id))
    sessao.flush()
    if novos - antigos:
        avisar(sessao, sorted(novos - antigos), f"Baixa #{baixa.numero} compartilhada com você",
               f"{autor.nome_completo or autor.login} compartilhou a baixa #{baixa.numero}: você pode incluir bens, definir motivo e processo e enviar, como ele.",
               f"patrimonio-bx-colab-{baixa.id}", autor, f"/patrimonio/baixas/{baixa.id}", evento="patrimonio.classificacao_compartilhada")
    sessao.commit()
    return obter(sessao, baixa.id)


def adicionar_bem(sessao: Session, baixa_id: uuid.UUID, autor: Usuario, *, bem_id: uuid.UUID | None = None, chapa: str | None = None) -> Baixa:
    """Leitura contínua de códigos, ou a chapa digitada (extraviados). Só bens já aprovados como inservíveis ou extraviados."""
    baixa = obter(sessao, baixa_id)
    _editavel(baixa, autor)
    if baixa.classificacao_origem_id is not None:
        raise ErroPatrimonio("Esta baixa herda os bens da lista aprovada: para incluir outro bem, aprove-o em uma lista e dê a baixa dela.", 409, "conflito")
    bem = servico_bens.obter(sessao, bem_id) if bem_id else servico_bens.obter_por_chapa(sessao, chapa or "")
    if bem.situacao not in ("inservivel", "extraviado"):
        raise ErroPatrimonio(f"O bem {bem.rotulo} não é inservível nem extraviado: classifique-o antes.", 409, "bem_invalido")
    if any(i.bem_id == bem.id for i in baixa.itens):
        raise ErroPatrimonio(f"O bem {bem.rotulo} já está na lista.", 409, "conflito")
    # Um bem não entra em duas baixas em andamento
    em_outra = sessao.scalar(select(ItemBaixa.id).join(Baixa).where(ItemBaixa.bem_id == bem.id, Baixa.status == "aguardando_aceite"))
    if em_outra is not None:
        raise ErroPatrimonio(f"O bem {bem.rotulo} já está em uma baixa aguardando o aceite da autoridade.", 409, "conflito")
    baixa.itens.append(ItemBaixa(id=uuid.uuid4(), bem_id=bem.id, situacao_anterior=bem.situacao))
    sessao.commit()
    return obter(sessao, baixa.id)


def remover_bem(sessao: Session, baixa_id: uuid.UUID, item_id: uuid.UUID, autor: Usuario) -> Baixa:
    baixa = obter(sessao, baixa_id)
    _editavel(baixa, autor)
    item = next((i for i in baixa.itens if i.id == item_id), None)
    if item is None:
        raise ErroPatrimonio("Item não encontrado.", 404, "nao_encontrado")
    baixa.itens.remove(item)
    sessao.commit()
    return obter(sessao, baixa.id)


def definir_motivo(sessao: Session, baixa_id: uuid.UUID, itens_ids: list[uuid.UUID], motivo: str, processo: str, autor: Usuario) -> Baixa:
    """Motivo e processo para os itens marcados (a seleção toda ou um grupo)."""
    baixa = obter(sessao, baixa_id)
    _editavel(baixa, autor)
    if motivo not in MOTIVOS:
        raise ErroPatrimonio("Motivo inválido: alienação, doação, transferência, inutilização ou extravio.")
    if not (processo or "").strip():
        raise ErroPatrimonio("Informe o número do processo.")
    marcados = [i for i in baixa.itens if i.id in set(itens_ids)]
    if not marcados:
        raise ErroPatrimonio("Marque ao menos um bem da lista.")
    for item in marcados:
        item.motivo, item.processo = motivo, processo.strip()
    sessao.commit()
    return obter(sessao, baixa.id)


def descartar(sessao: Session, baixa_id: uuid.UUID, autor: Usuario) -> None:
    baixa = obter(sessao, baixa_id)
    _editavel(baixa, autor)
    sessao.delete(baixa)
    sessao.commit()


def enviar(sessao: Session, baixa_id: uuid.UUID, autor: Usuario) -> Baixa:
    """Valida motivo e processo, gera o termo em PDF (instrui o SEI) e deixa a baixa aguardando o aceite da autoridade."""
    baixa = obter(sessao, baixa_id)
    _editavel(baixa, autor)
    if not baixa.itens:
        raise ErroPatrimonio("A lista está vazia.")
    sem = [i.bem.rotulo for i in baixa.itens if not i.motivo or not i.processo]
    if sem:
        raise ErroPatrimonio(f"Falta motivo e processo para: {', '.join(sem[:10])}.", 409, "sem_motivo")
    baixa.status, baixa.enviada_em = "aguardando_aceite", agora_utc()
    sessao.flush()
    anexo = servico_anexos.guardar_pdf_gerado(sessao, gerar_termo(sessao, baixa, autor), f"termo-baixa-{hoje_sao_paulo():%Y%m%d}-{baixa.numero}.pdf", "patrimonio-termo-baixa", autor.id)
    sessao.flush()
    baixa.termo_anexo_id = anexo.id
    avisar(sessao, ids_controle_total(sessao), "Baixa aguardando o aceite da autoridade",
           f"{nome_do_autor(autor)} enviou a baixa #{baixa.numero} ({len(baixa.itens)} bem(ns)). Leve o termo à autoridade e, com o de acordo (ou a publicação no D.O.E.), anexe o PDF para concluir.",
           f"patrimonio-bx-{baixa.id}", autor, f"/patrimonio/baixas/{baixa.id}", categoria="pendencia", evento="patrimonio.baixa_pendente")
    sessao.commit()
    return obter(sessao, baixa.id)


def _justificativa(sessao: Session, bem_id: uuid.UUID) -> str:
    """Justificativa da classificação aprovada (a mais recente), para constar no termo."""
    evento = sessao.scalar(select(EventoPatrimonio).where(EventoPatrimonio.bem_id == bem_id, EventoPatrimonio.tipo == "classificou").order_by(EventoPatrimonio.ocorrido_em.desc()))
    return evento.texto if evento else ""


def _real(valor: Decimal | None) -> str:
    return "—" if valor is None else f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_termo(sessao: Session, baixa: Baixa, autor: Usuario) -> bytes:
    """Termo de baixa em PDF: lista de bens, valores, situação anterior e justificativas, para instruir o processo."""
    aprovados = list(baixa.itens)
    documento = DocumentoPdf(titulo="Termo de baixa de bens móveis", subtitulo=f"{len(aprovados)} bem(ns) · {hoje_sao_paulo():%d/%m/%Y}", autor=nome_do_autor(autor))
    documento.secao("Dados da baixa").campos([
        ("Solicitante", nome_do_autor(baixa.solicitante)), ("Baixa nº", f"#{baixa.numero}"),
        ("Enviada em", baixa.enviada_em.strftime("%d/%m/%Y %H:%M") if baixa.enviada_em else "—"), ("Aceite", "Autoridade competente (fora do sistema)"),
    ])
    documento.secao("Bens baixados")
    linhas = []
    total_aquisicao = total_atual = Decimal(0)
    for item in aprovados:
        bem = item.bem
        valor_atual = servico_bens.valor_efetivo(bem)
        total_aquisicao += bem.valor_aquisicao or 0
        total_atual += valor_atual or 0
        linhas.append([bem.rotulo, bem.descricao, item.situacao_anterior.replace("_", " ") if item.situacao_anterior else "", MOTIVOS.get(item.motivo or "", ""), item.processo or "",
                       _real(bem.valor_aquisicao), _real(valor_atual), _justificativa(sessao, bem.id)])
    documento.tabela(["Chapa", "Descrição", "Situação anterior", "Motivo", "Processo", "Aquisição", "Valor atual", "Justificativa"], linhas,
                     larguras=[1.1, 2.6, 1.2, 1.2, 1.3, 1.2, 1.2, 3], alinhar_direita=[5, 6], rodape=["", "Total", "", "", "", _real(total_aquisicao), _real(total_atual), ""])
    documento.paragrafo("A baixa registrada no módulo Patrimônio não baixa o bem no SAM: este termo serve para instruir a baixa lá.")
    return documento.gerar()


def concluir(sessao: Session, baixa_id: uuid.UUID, arquivo: BinaryIO, nome_arquivo: str, autor: Usuario) -> Baixa:
    """Conclui a baixa com o PDF do de acordo da autoridade (na maioria das vezes, a publicação no D.O.E.): os bens viram Baixado.

    Quem tem controle total faz isso, inclusive quem montou a baixa: a decisão é da autoridade, fora do sistema."""
    baixa = obter(sessao, baixa_id)
    if baixa.status != "aguardando_aceite":
        raise ErroPatrimonio("A baixa não está aguardando o aceite da autoridade.", 409, "conflito")
    try:
        anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome_arquivo or "doe.pdf", "patrimonio-baixa-doe", autor.id)
    except servico_anexos.ErroAnexo as erro:
        raise ErroPatrimonio(str(erro)) from erro
    sessao.flush()
    agora = agora_utc()
    for item in baixa.itens:
        bem = servico_bens.obter(sessao, item.bem_id)
        item.resultado = "aprovado"
        registrar_evento(sessao, bem, "baixou", autor, campo="situacao", anterior=bem.situacao, novo="baixado",
                         texto=f"Baixa por {MOTIVOS.get(item.motivo or '', '')}, processo {item.processo}",
                         dados={"solicitante": baixa.solicitante.login if baixa.solicitante else None, "concluida_por": autor.login, "processo": item.processo})
        bem.situacao, bem.baixado_em = "baixado", agora
    baixa.status, baixa.doe_anexo_id = "concluida", anexo.id
    baixa.decidido_por_id, baixa.decidido_em, baixa.motivo_recusa = autor.id, agora, None
    avisar(sessao, sorted(({baixa.solicitante_id} - {None}) | baixa.colaboradores_ids), "Baixa concluída", f"A baixa #{baixa.numero} foi concluída: os bens estão Baixados.",
           f"patrimonio-bx-dec-{baixa.id}", autor, f"/patrimonio/baixas/{baixa.id}", evento="patrimonio.baixa_decidida")
    sessao.commit()
    return obter(sessao, baixa.id)


def recusar(sessao: Session, baixa_id: uuid.UUID, motivo: str, autor: Usuario) -> Baixa:
    """A autoridade não deu o aceite: a baixa é recusada (os bens continuam inservíveis e a lista pode ganhar outra baixa)."""
    baixa = obter(sessao, baixa_id)
    if baixa.status != "aguardando_aceite":
        raise ErroPatrimonio("A baixa não está aguardando o aceite da autoridade.", 409, "conflito")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroPatrimonio("A recusa exige motivo.")
    for item in baixa.itens:
        item.resultado = "recusado"
        registrar_evento(sessao, servico_bens.obter(sessao, item.bem_id), "baixa_recusada", autor, texto=f"Baixa recusada: {motivo}")
    baixa.status, baixa.decidido_por_id, baixa.decidido_em, baixa.motivo_recusa = "recusada", autor.id, agora_utc(), motivo
    avisar(sessao, sorted(({baixa.solicitante_id} - {None}) | baixa.colaboradores_ids), "Baixa recusada", f"A baixa #{baixa.numero} foi recusada: {motivo}",
           f"patrimonio-bx-dec-{baixa.id}", autor, f"/patrimonio/baixas/{baixa.id}", evento="patrimonio.baixa_decidida")
    sessao.commit()
    return obter(sessao, baixa.id)
