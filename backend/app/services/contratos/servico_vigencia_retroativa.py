# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar e desfazer vigências retroativas (anteriores ao início do contrato).
"""Vigência retroativa: um termo anterior ao início do contrato, cadastrado para voltar no tempo.

Ela é uma vigência completa (gera competências, checklists, NEs e avaliação da qualidade) e é a base do
reajuste retroativo. Cadastrar uma recua o início do contrato e renumera as vigências: a mais antiga
passa a ser a 1ª. As retroativas formam uma cadeia contínua que termina no dia anterior ao início do contrato.
"""

import uuid
from datetime import date, timedelta
from typing import BinaryIO

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import AlteracaoQuantidade, Competencia, Contrato, DocumentoContrato, ItemMedicao, PrevisaoVigencia, Reajuste, VigenciaRetroativa
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import LeituraVigenciaRetroativa
from app.schemas.contratos.execucao import LeituraArquivo
from app.services import servico_anexos
from app.services.contratos import calculos, servico_parametros
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_configuracao_execucao import checklist_ativo
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.servico_auditoria import auditar

# Mesma numeração dos termos aditivos nos documentos importantes do contrato (024, 025...)
PRIMEIRO_CODIGO_TERMO = 24
# O prazo máximo de uma vigência retroativa (evita datas absurdas por engano) é parâmetro de Contratos: `maximo_meses_vigencia_retroativa`


def periodo_retroativo(contrato: Contrato, meses: int) -> tuple[date, date]:
    """(início, fim) da nova vigência retroativa: termina na véspera do início do contrato e tem `meses` de prazo."""
    return calculos.somar_meses(contrato.data_inicio, -meses), contrato.data_inicio - timedelta(days=1)


def _deslocar_sequencias(sessao: Session, contrato: Contrato, delta: int) -> None:
    """Soma `delta` ao número de vigência de tudo o que aponta para elas (competências, linhas, reajustes, alterações e previsões).

    A previsão tem restrição de unicidade por vigência: o deslocamento passa por números negativos para
    não colidir no meio da atualização. Ao final, a sessão é renovada para recarregar os números novos.
    """
    contrato_id = contrato.id
    competencias = select(Competencia.id).where(Competencia.contrato_id == contrato_id)
    sessao.execute(update(Competencia).where(Competencia.contrato_id == contrato_id).values(sequencia_vigencia=Competencia.sequencia_vigencia + delta),
                   execution_options={"synchronize_session": False})
    sessao.execute(update(ItemMedicao).where(ItemMedicao.competencia_id.in_(competencias)).values(sequencia_vigencia=ItemMedicao.sequencia_vigencia + delta),
                   execution_options={"synchronize_session": False})
    for modelo in (Reajuste, AlteracaoQuantidade):
        sessao.execute(update(modelo).where(modelo.contrato_id == contrato_id).values(sequencia_vigencia=modelo.sequencia_vigencia + delta),
                       execution_options={"synchronize_session": False})
    sessao.execute(update(PrevisaoVigencia).where(PrevisaoVigencia.contrato_id == contrato_id).values(sequencia_vigencia=-(PrevisaoVigencia.sequencia_vigencia + delta)),
                   execution_options={"synchronize_session": False})
    sessao.execute(update(PrevisaoVigencia).where(PrevisaoVigencia.contrato_id == contrato_id).values(sequencia_vigencia=-PrevisaoVigencia.sequencia_vigencia),
                   execution_options={"synchronize_session": False})
    sessao.expire_all()


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _bloqueio_para_desfazer(sessao: Session, contrato: Contrato, usuario: Usuario) -> str:
    """Motivo pelo qual a vigência retroativa mais antiga não pode ser desfeita (vazio = pode)."""
    if not pode_editar(sessao, contrato, usuario):
        return "Sem permissão para alterar o contrato."
    if any(c.sequencia_vigencia == 1 and (c.medicao_iniciada_em or c.etapa_atual != "medicao") for c in contrato.competencias):
        return "Há medição registrada nessa vigência. Reabra ou desfaça a execução antes."
    if any(r.sequencia_vigencia == 1 and r.situacao != "cancelado" for r in contrato.reajustes) or any(
        a.sequencia_vigencia == 1 and a.situacao != "cancelada" for a in contrato.alteracoes
    ):
        return "Há reajuste ou aditamento/supressão nessa vigência. Cancele-os antes."
    return ""


def listar(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> list[LeituraVigenciaRetroativa]:
    """Vigências retroativas, da mais antiga para a mais recente; só a mais antiga pode ser desfeita."""
    contrato = obter_contrato(sessao, contrato_id)
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_([v.anexo_id for v in contrato.vigencias_retroativas])))}
    bloqueio = _bloqueio_para_desfazer(sessao, contrato, usuario)
    reajustadas = {r.sequencia_vigencia for r in contrato.reajustes if r.retroativo and r.situacao == "concluido"}
    return [
        LeituraVigenciaRetroativa(
            id=v.id, sequencia=numero, meses=v.meses, assinada_em=v.assinada_em, numero_termo=v.numero_termo, data_inicio=v.data_inicio,
            data_fim=v.data_fim, codigo_documento=v.codigo_documento, termo=_arquivo(anexos.get(v.anexo_id)), reajustada=numero in reajustadas,
            pode_desfazer=numero == 1 and not bloqueio, motivo_bloqueio=bloqueio if numero == 1 else "Somente a vigência retroativa mais antiga pode ser desfeita.",
        )
        for numero, v in enumerate(contrato.vigencias_retroativas, start=1)
    ]


def registrar(sessao: Session, contrato_id: uuid.UUID, meses: int, assinada_em: date, numero_termo: str, termo: tuple[BinaryIO, str], autor: Usuario) -> VigenciaRetroativa:
    """Cria a vigência retroativa, recua o início do contrato, renumera as vigências e guarda o termo nos documentos (024+)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    maximo = servico_parametros.valor("maximo_meses_vigencia_retroativa")
    if not 1 <= meses <= maximo:
        raise ErroRegraContrato(f"O prazo da vigência retroativa deve ficar entre 1 e {maximo} meses.")
    if contrato.competencias and checklist_ativo(contrato) is None:
        raise ErroRegraContrato("O contrato já tem competências geradas: ative um checklist antes de cadastrar uma vigência retroativa.")
    inicio, fim = periodo_retroativo(contrato, meses)
    inicio_anterior = contrato.data_inicio
    # Os números das vigências existentes sobem uma casa; o contrato é recarregado depois do deslocamento
    _deslocar_sequencias(sessao, contrato, 1)
    contrato = obter_contrato(sessao, contrato_id)
    anexo = servico_anexos.guardar_pdf(sessao, termo[0], termo[1], "contrato-vigencia-retroativa-termo", autor.id, contrato_id=contrato.id)
    codigo = max([d.codigo_tipo for d in contrato.documentos] + [PRIMEIRO_CODIGO_TERMO - 1]) + 1
    numero = numero_termo.strip()
    contrato.documentos.append(
        DocumentoContrato(codigo_tipo=codigo, titulo=f"Termo Aditivo{' nº ' + numero if numero else ''} — vigência retroativa de {meses} mês(es)",
                          anexo=anexo, enviado_em=agora_utc(), enviado_por_id=autor.id)
    )
    retroativa = VigenciaRetroativa(
        meses=meses, assinada_em=assinada_em, numero_termo=numero, data_inicio=inicio, data_fim=fim, inicio_anterior=inicio_anterior,
        anexo=anexo, codigo_documento=codigo, criado_por_id=autor.id,
    )
    contrato.vigencias_retroativas.append(retroativa)
    contrato.data_inicio = inicio
    contrato.versao += 1
    auditar(sessao, autor.login, "contrato.vigencia_retroativa.registrar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"campos": {"data_inicio": {"de": inicio_anterior, "para": inicio}}, "meses": meses, "termo": numero})
    sessao.commit()
    return retroativa


def desfazer(sessao: Session, contrato_id: uuid.UUID, vigencia_id: uuid.UUID, autor: Usuario) -> None:
    """Desfaz a vigência retroativa mais antiga: apaga o que ela criou, devolve o início do contrato e renumera as demais."""
    contrato = obter_contrato(sessao, contrato_id)
    retroativa = next((v for v in contrato.vigencias_retroativas if v.id == vigencia_id), None)
    if retroativa is None:
        raise RegistroNaoEncontrado("Vigência retroativa")
    if retroativa is not contrato.vigencias_retroativas[0]:
        raise ErroRegraContrato("Somente a vigência retroativa mais antiga pode ser desfeita.")
    motivo = _bloqueio_para_desfazer(sessao, contrato, autor)
    if motivo:
        raise ErroRegraContrato(motivo)
    # Remove competências e previsão da vigência desfeita (número 1) e o termo dos documentos importantes
    for competencia in [c for c in contrato.competencias if c.sequencia_vigencia == 1]:
        contrato.competencias.remove(competencia)
    for previsao in [p for p in contrato.previsoes if p.sequencia_vigencia == 1]:
        contrato.previsoes.remove(previsao)
    documento = next((d for d in contrato.documentos if d.codigo_tipo == retroativa.codigo_documento), None)
    if documento:
        contrato.documentos.remove(documento)
    servico_anexos.descartar(sessao.get(Anexo, retroativa.anexo_id))
    inicio_atual, inicio_anterior, termo = contrato.data_inicio, retroativa.inicio_anterior, retroativa.numero_termo
    contrato.vigencias_retroativas.remove(retroativa)
    contrato.data_inicio = inicio_anterior
    contrato.versao += 1
    sessao.flush()
    # As vigências seguintes descem uma casa
    _deslocar_sequencias(sessao, contrato, -1)
    contrato = obter_contrato(sessao, contrato_id)
    auditar(sessao, autor.login, "contrato.vigencia_retroativa.desfazer", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"campos": {"data_inicio": {"de": inicio_atual, "para": inicio_anterior}}, "termo": termo})
    sessao.commit()


def exigir_retroativa(contrato: Contrato, sequencia: int) -> calculos.Vigencia:
    """Vigência pelo número, exigindo que seja retroativa."""
    vigencia = next((v for v in vigencias(contrato) if v.sequencia == sequencia), None)
    if vigencia is None or not vigencia.retroativa:
        raise ErroRegraContrato("A vigência escolhida não é uma vigência retroativa.")
    return vigencia
