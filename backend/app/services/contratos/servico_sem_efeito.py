"""
===============================================================================
ARQUIVO: servico_sem_efeito.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Tornar sem efeito um evento já concluído do contrato (reajuste, repactuação,
aditamento/supressão, prorrogação e vigência retroativa): conferir se nada
depende dele e desfazer o que ele aplicou, com motivo e auditoria.

RESUMO TÉCNICO:
- `verificar(...)` devolve (pode, motivo do bloqueio) sem mudar nada; a tela usa
  para mostrar o botão ativo ou desativado com o motivo.
- `tornar_sem_efeito(...)` confere de novo e desfaz:
  * reajuste/repactuação: preço dos itens volta ao de antes, competências não
    medidas são realinhadas (`sincronizar_competencia`), a competência de
    diferença (automática e manual) sai, o crédito no fundo sai, os meses da
    diferença manual destravam e o valor global reajustado é refeito;
  * aditamento/supressão: quantidades voltam às originais, as competências
    previstas são refeitas e o impacto sai do valor global reajustado;
  * prorrogação e vigência retroativa: reaproveitam o `desfazer` de cada
    serviço, que agora recebe o motivo.
- O registro fica com a situação "sem_efeito", quem, quando e o motivo; a
  auditoria grava "contrato.<tipo>.sem_efeito" com o de/para.

FINALIDADE DE NEGÓCIO:
Decisões do usuário (13/11/2026): qualquer evento pode ser desfeito desde que
nenhum outro dependa dele; bloqueia se a diferença retroativa já foi medida ou
tem NF, se o crédito já foi abatido ou se algum mês já foi medido com o preço
(ou a quantidade) novo; quem pode é a equipe do contrato, com motivo; o evento
continua no histórico com o selo "Sem efeito".

CONTEXTO NO SISTEMA:
Chamado pelas rotas `POST …/{tipo}/{id}/sem-efeito` (api/routes/contratos/
alteracoes.py) e pelas leituras dos painéis (servico_reajuste,
servico_repactuacao, servico_alteracao), que mostram o botão.

===============================================================================
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import (
    AbatimentoReajuste, AlteracaoQuantidade, Competencia, Contrato, CorrecaoItens, Prorrogacao, Reajuste, Repactuacao, VigenciaRetroativa,
)
from app.models.usuario import Usuario
from app.services.contratos import valores
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_competencias import sincronizar_competencia
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.notificacoes import caixa
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
# Tamanho mínimo do motivo (evita "ok", "erro"…): o motivo vai para o histórico e para a auditoria
MOTIVO_MINIMO = 10
# Tipos aceitos na rota (segmento da URL) e o nome usado na auditoria
TIPOS = {"reajustes": "reajuste", "repactuacoes": "repactuacao", "alteracoes": "alteracao", "prorrogacoes": "prorrogacao",
         "vigencias-retroativas": "vigencia_retroativa"}

Procedimento = Reajuste | Repactuacao


# ---------------------------------------------------------------------------------------------
# Apoio
# ---------------------------------------------------------------------------------------------

def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _mes(competencia: Competencia) -> str:
    return f"{competencia.competencia:%m/%Y}"


def _utc(momento: datetime) -> datetime:
    """Data e hora com fuso (o SQLite dos testes devolve sem fuso; gravamos sempre em UTC)."""
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


def _depois(momento: datetime | None, referencia: datetime | None) -> bool:
    """`momento` aconteceu depois de `referencia`? (sem uma das datas, não dá para afirmar: False)"""
    return momento is not None and referencia is not None and _utc(momento) > _utc(referencia)


def _marcar(registro, autor: Usuario, motivo: str) -> None:
    """Grava a situação "sem_efeito" com quem, quando e o motivo."""
    registro.situacao = "sem_efeito"
    registro.sem_efeito_em, registro.sem_efeito_por_id, registro.sem_efeito_por_nome, registro.sem_efeito_motivo = agora_utc(), autor.id, _nome(autor), motivo


def _exigir_motivo(motivo: str) -> str:
    motivo = " ".join((motivo or "").split())
    if len(motivo) < MOTIVO_MINIMO:
        raise ErroRegraContrato(f"Informe o motivo (pelo menos {MOTIVO_MINIMO} caracteres).")
    return motivo[:4000]


def _prorrogacao_posterior(contrato: Contrato, concluido_em: datetime | None) -> str:
    """Prorrogação registrada depois do evento: ela já usou os preços e as quantidades dele."""
    posterior = next((p for p in contrato.prorrogacoes if _depois(p.criado_em, concluido_em)), None)
    if posterior is None:
        return ""
    termo = f" (termo {posterior.numero_termo})" if posterior.numero_termo else ""
    return f"A prorrogação{termo} foi registrada depois e já usa este valor. Torne a prorrogação sem efeito antes."


def _correcao_posterior(sessao: Session, contrato: Contrato, concluido_em: datetime | None) -> str:
    """Correção de itens aplicada depois do evento: ela partiu do cadastro já alterado por ele."""
    aplicadas = sessao.scalars(select(CorrecaoItens).where(CorrecaoItens.contrato_id == contrato.id, CorrecaoItens.situacao == "aplicada")).all()
    if any(_depois(c.decidido_em, concluido_em) for c in aplicadas):
        return "Há correção de itens aplicada depois deste evento, que partiu dos valores dele."
    return ""


# ---------------------------------------------------------------------------------------------
# Reajuste e repactuação (mudam o preço)
# ---------------------------------------------------------------------------------------------

def _diferencas(contrato: Contrato, proc: Procedimento) -> list[Competencia]:
    """Competências de diferença criadas na conclusão (automática e a complementar da diferença manual)."""
    manual_id = proc.diferenca_manual.id if proc.diferenca_manual is not None else None
    if isinstance(proc, Reajuste):
        return [c for c in contrato.competencias
                if (c.tipo == "diferenca_reajuste" and c.reajuste_id == proc.id) or (manual_id is not None and c.diferenca_manual_id == manual_id)]
    return [c for c in contrato.competencias
            if (c.tipo == "diferenca_repactuacao" and c.repactuacao_id == proc.id) or (manual_id is not None and c.diferenca_manual_id == manual_id)]


def _creditos(sessao: Session, proc: Procedimento) -> list[AbatimentoReajuste]:
    coluna = AbatimentoReajuste.reajuste_id if isinstance(proc, Reajuste) else AbatimentoReajuste.repactuacao_id
    return list(sessao.scalars(select(AbatimentoReajuste).where(coluna == proc.id)))


def _bloqueio_preco(sessao: Session, contrato: Contrato, proc: Procedimento) -> str:
    """Motivo que impede tornar o reajuste/repactuação sem efeito ("" = pode)."""
    if proc.situacao != "concluido":
        return "Só um evento concluído pode ser tornado sem efeito."
    # Outro reajuste/repactuação concluído depois fotografou o preço com este
    posterior = next((r for r in valores._reajustes(contrato) if r is not proc and _depois(r.concluido_em, proc.concluido_em)), None)
    if posterior is not None:
        nome = "reajuste" if isinstance(posterior, Reajuste) else "repactuação"
        return f"Há {nome} concluído depois deste (efeito em {posterior.efeito:%d/%m/%Y}), que partiu do preço dele. Torne-o sem efeito antes."
    for motivo in (_prorrogacao_posterior(contrato, proc.concluido_em), _correcao_posterior(sessao, contrato, proc.concluido_em)):
        if motivo:
            return motivo
    # Competência de diferença já em andamento: precisa ser reaberta/zerada antes
    for c in _diferencas(contrato, proc):
        if c.medicao_iniciada_em or c.medicao_concluida_em or c.notas_fiscais or c.etapa_atual != "medicao":
            return f"A competência de diferença ({c.identificador}) já tem medição ou nota fiscal. Reabra e zere a medição dela antes."
    # Crédito do desconto retroativo já aplicado numa medição
    if any(a.competencia_id is not None for a in _creditos(sessao, proc)):
        return "O crédito deste evento já foi aplicado numa medição. Retire o crédito da medição antes."
    # Mês medido depois da conclusão = medido com o preço novo
    vigencia_reajuste = proc.sequencia_vigencia if isinstance(proc, Reajuste) else None
    for c in sorted(contrato.competencias, key=lambda c: c.periodo_inicio):
        if c.tipo not in ("regular", "adicional") or c.periodo_fim < proc.efeito or c.diferencas_manuais:
            continue
        if vigencia_reajuste is not None and c.sequencia_vigencia != vigencia_reajuste:
            continue
        if _depois(c.medicao_concluida_em, proc.concluido_em):
            return f"A competência {_mes(c)} já foi medida com o preço novo. Reabra a medição dela antes."
    return ""


def _desfazer_preco(sessao: Session, contrato: Contrato, proc: Procedimento) -> dict:
    """Desfaz o que a conclusão aplicou. Devolve o de/para para a auditoria."""
    itens = {i.id: i for i in contrato.itens}
    precos = {}
    if isinstance(proc, Reajuste):
        # O preço do cadastro só tinha mudado se o reajuste era da vigência atual (e não há prorrogação depois: conferido no bloqueio)
        if proc.sequencia_vigencia == vigencias(contrato)[-1].sequencia:
            for linha in proc.itens:
                item = itens.get(linha.item_id)
                if item is not None:
                    precos[str(item.id)] = {"de": item.valor_unitario, "para": linha.valor_unitario_atual}
                    item.valor_unitario = linha.valor_unitario_atual
        # Meses cujo retroativo este reajuste acertou voltam a não ter diferença acertada
        for c in contrato.competencias:
            if c.diferenca_coberta_por_reajuste_id == proc.id:
                c.diferenca_coberta_por_reajuste_id = None
    else:
        # A repactuação somou a diferença no preço do cadastro: tira a mesma diferença
        for linha in proc.itens:
            item = itens.get(linha.item_id)
            if item is not None:
                novo = item.valor_unitario - (linha.valor_unitario_repactuado - linha.valor_unitario_atual)
                precos[str(item.id)] = {"de": item.valor_unitario, "para": novo}
                item.valor_unitario = novo
    # Competências de diferença (ainda sem medição: conferido no bloqueio) e créditos no fundo saem
    excluidas = [c.identificador for c in _diferencas(contrato, proc)]
    for c in _diferencas(contrato, proc):
        contrato.competencias.remove(c)
    for credito in _creditos(sessao, proc):
        sessao.delete(credito)
    # Os meses da diferença manual destravam (o registro da diferença fica no histórico do evento)
    if proc.diferenca_manual is not None:
        proc.diferenca_manual.competencias = []
    proc.situacao = "sem_efeito"  # antes de realinhar: a linha do tempo de preços já não enxerga este evento
    sessao.flush()
    for c in contrato.competencias:
        if c.tipo == "regular" and c.medicao_concluida_em is None and not c.diferencas_manuais:
            sincronizar_competencia(contrato, c)
    # Valor global reajustado: refeito pela linha do tempo se ainda houver reajuste/repactuação valendo na vigência atual; senão, vazio
    antes = contrato.valor_global_reajustado
    ultima = vigencias(contrato)[-1]
    restantes = [r for r in valores._reajustes(contrato) if r.efeito <= ultima.fim
                 and (not isinstance(r, Reajuste) or r.sequencia_vigencia == ultima.sequencia)]
    contrato.valor_global_reajustado = valores.valor_global_vigencia(contrato, ultima) if restantes else None
    return {"precos": precos, "competencias_excluidas": excluidas,
            "campos": {"valor_global_reajustado": {"de": antes, "para": contrato.valor_global_reajustado}}}


# ---------------------------------------------------------------------------------------------
# Aditamento / supressão (mudam a quantidade)
# ---------------------------------------------------------------------------------------------

def _bloqueio_alteracao(sessao: Session, contrato: Contrato, alteracao: AlteracaoQuantidade) -> str:
    if alteracao.situacao != "concluida":
        return "Só um evento concluído pode ser tornado sem efeito."
    posterior = next((a for a in contrato.alteracoes if a is not alteracao and a.situacao == "concluida"
                      and a.sequencia_vigencia == alteracao.sequencia_vigencia and _depois(a.concluida_em, alteracao.concluida_em)), None)
    if posterior is not None:
        nome = "aditamento" if posterior.tipo == "aditamento" else "supressão"
        return f"Há {nome} concluído depois deste na mesma vigência (o percentual acumulado depende dele). Torne-o sem efeito antes."
    preco = next((r for r in valores._reajustes(contrato) if _depois(r.concluido_em, alteracao.concluida_em)), None)
    if preco is not None:
        nome = "reajuste" if isinstance(preco, Reajuste) else "repactuação"
        return f"Há {nome} concluído depois deste evento, que partiu destas quantidades. Torne-o sem efeito antes."
    for motivo in (_prorrogacao_posterior(contrato, alteracao.concluida_em), _correcao_posterior(sessao, contrato, alteracao.concluida_em)):
        if motivo:
            return motivo
    for c in sorted(contrato.competencias, key=lambda c: c.periodo_inicio):
        if (c.tipo == "regular" and c.sequencia_vigencia == alteracao.sequencia_vigencia and c.competencia >= alteracao.mes_efeito
                and _depois(c.medicao_concluida_em, alteracao.concluida_em)):
            return f"A competência {_mes(c)} já foi medida com a quantidade nova. Reabra a medição dela antes."
    return ""


def _desfazer_alteracao(contrato: Contrato, alteracao: AlteracaoQuantidade) -> dict:
    from app.services.contratos.servico_alteracao import _recalcular_previstas
    from app.services.contratos.servico_orcamento import obter_ou_criar_previsao

    itens = {i.id: i for i in contrato.itens}
    ultima = vigencias(contrato)[-1].sequencia
    quantidades = {}
    previsao = None
    for linha in alteracao.itens:
        item = itens.get(linha.item_id)
        if item is None or linha.quantidade_nova == linha.quantidade_original:
            continue
        quantidades[str(item.id)] = {"de": linha.quantidade_nova, "para": linha.quantidade_original}
        if linha.tipo == "continuo":
            if alteracao.sequencia_vigencia == ultima:
                item.quantidade_mensal = linha.quantidade_original
        else:
            # Sob demanda: o limite da vigência volta ao original
            previsao = previsao or obter_ou_criar_previsao(contrato, alteracao.sequencia_vigencia)
            limite = next((l for l in previsao.limites if l.item_id == item.id), None)
            if limite is not None:
                limite.quantidade_total = linha.quantidade_original
    antes = contrato.valor_global_reajustado
    if contrato.valor_global_reajustado is not None and alteracao.sequencia_vigencia == ultima:
        contrato.valor_global_reajustado -= alteracao.impacto_valor
    alteracao.situacao = "sem_efeito"
    _recalcular_previstas(contrato, alteracao)
    return {"quantidades": quantidades, "campos": {"valor_global_reajustado": {"de": antes, "para": contrato.valor_global_reajustado}}}


# ---------------------------------------------------------------------------------------------
# Entrada única: verificar e tornar sem efeito
# ---------------------------------------------------------------------------------------------

def _registro(contrato: Contrato, tipo: str, registro_id: uuid.UUID):
    lista = {"reajuste": contrato.reajustes, "repactuacao": contrato.repactuacoes, "alteracao": contrato.alteracoes,
             "prorrogacao": contrato.prorrogacoes, "vigencia_retroativa": contrato.vigencias_retroativas}[tipo]
    registro = next((r for r in lista if r.id == registro_id), None)
    if registro is None:
        raise RegistroNaoEncontrado("Evento")
    return registro


def verificar(sessao: Session, contrato: Contrato, registro, usuario: Usuario | None = None) -> tuple[bool, str]:
    """(pode tornar sem efeito?, motivo do bloqueio). Não muda nada."""
    if usuario is not None and not pode_editar(sessao, contrato, usuario):
        return False, "Só a equipe do contrato pode tornar um evento sem efeito."
    if isinstance(registro, (Reajuste, Repactuacao)):
        motivo = _bloqueio_preco(sessao, contrato, registro)
    elif isinstance(registro, AlteracaoQuantidade):
        motivo = _bloqueio_alteracao(sessao, contrato, registro)
    elif isinstance(registro, Prorrogacao):
        # Regras de sempre da prorrogação: só a mais recente, sem medição nem reajuste/aditamento na vigência nova
        if registro is not contrato.prorrogacoes[-1]:
            return False, "Só a prorrogação mais recente pode ser tornada sem efeito."
        if usuario is None:
            return True, ""
        from app.services.contratos.servico_prorrogacao import pode_desfazer
        return pode_desfazer(sessao, contrato, registro, usuario)
    elif isinstance(registro, VigenciaRetroativa):
        if registro is not contrato.vigencias_retroativas[0]:
            return False, "Só a vigência retroativa mais antiga pode ser tornada sem efeito."
        if usuario is None:
            return True, ""
        from app.services.contratos.servico_vigencia_retroativa import _bloqueio_para_desfazer
        motivo = _bloqueio_para_desfazer(sessao, contrato, usuario)
    else:
        return False, "Este evento não pode ser tornado sem efeito."
    return not motivo, motivo


def completar_leitura(sessao: Session, contrato: Contrato, registro, leitura, usuario: Usuario):
    """Preenche na leitura do histórico os campos do "sem efeito": quem, quando, motivo e se o botão fica ativo (ou o bloqueio)."""
    leitura.sem_efeito_em, leitura.sem_efeito_por, leitura.sem_efeito_motivo = registro.sem_efeito_em, registro.sem_efeito_por_nome, registro.sem_efeito_motivo
    if registro.situacao in ("concluido", "concluida"):
        leitura.pode_tornar_sem_efeito, leitura.motivo_bloqueio = verificar(sessao, contrato, registro, usuario)
    return leitura


def tornar_sem_efeito(sessao: Session, contrato_id: uuid.UUID, tipo_url: str, registro_id: uuid.UUID, motivo: str, autor: Usuario) -> None:
    """Desfaz o evento concluído e grava a situação "sem_efeito" com o motivo (ou levanta o motivo do bloqueio)."""
    tipo = TIPOS.get(tipo_url)
    if tipo is None:
        raise RegistroNaoEncontrado("Tipo de evento")
    motivo = _exigir_motivo(motivo)
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    # Prorrogação e vigência retroativa: o desfazer de cada uma já confere as regras e grava a auditoria
    if tipo == "prorrogacao":
        from app.services.contratos import servico_prorrogacao
        servico_prorrogacao.desfazer(sessao, contrato_id, registro_id, autor, motivo)
        return
    if tipo == "vigencia_retroativa":
        from app.services.contratos import servico_vigencia_retroativa
        servico_vigencia_retroativa.desfazer(sessao, contrato_id, registro_id, autor, motivo)
        return
    registro = _registro(contrato, tipo, registro_id)
    pode, bloqueio = verificar(sessao, contrato, registro)
    if not pode:
        raise ErroRegraContrato(bloqueio, conflito=True)
    if isinstance(registro, AlteracaoQuantidade):
        dados = _desfazer_alteracao(contrato, registro)
        tipo = registro.tipo  # "aditamento" ou "supressao" na auditoria, como na conclusão
    else:
        dados = _desfazer_preco(sessao, contrato, registro)
    _marcar(registro, autor, motivo)
    contrato.versao += 1
    # O aviso "concluído" da equipe sai da caixa de notificações
    chave = "alteracao" if isinstance(registro, AlteracaoQuantidade) else tipo
    caixa.encerrar(sessao, chave=f"{chave}:{registro.id}")
    auditar(sessao, autor.login, f"contrato.{tipo}.sem_efeito", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"registro_id": str(registro.id), "motivo": motivo, **dados})
    sessao.commit()
