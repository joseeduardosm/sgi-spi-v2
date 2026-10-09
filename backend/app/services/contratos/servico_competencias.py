# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de geração e das etapas 1 a 7 das competências.
"""Competências de execução: geração, etapas 1 a 7, avaliação dos serviços e reabertura.

Etapas: 1 medição → 2 avaliação (se houver formulário) → 3 nota fiscal → 4 CADIN → 5 checklist →
6 consolidado → 7 ordem bancária → concluída. Etapas futuras ficam bloqueadas; as passadas, só
para consulta. A situação exibida (pendente/disponível/em andamento/concluída) não é gravada.

Padrão das funções de escrita: carregar o contrato → conferir permissão (`exigir_edicao`) →
carregar a competência → conferir a etapa aberta → validar → gravar → auditar → commit.
Qualquer regra violada levanta `ErroRegraContrato`, e a transação é desfeita pela rota.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import BinaryIO

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import (
    DespesaVariavel,
    NotaFiscalCompetencia,
    ETAPAS,
    AbatimentoReajuste,
    AvaliacaoCompetencia,
    CienciaMedicao,
    Competencia,
    ConsultaCadin,
    Contrato,
    ItemMedicao,
    MemoriaMedicao,
    MovimentoNotaEmpenho,
    NotaEmpenho,
    SelecaoNotaEmpenho,
)
from app.models.contratos.execucao import ETAPAS_PARALELAS, DocumentoMensal
from app.models.usuario import Usuario
from app.schemas.contratos.execucao import (
    ConferenciaNota,
    DescontoReajuste,
    DetalheCompetencia,
    EmailMedicao,
    GlosaDoPeriodo,
    GravacaoAvaliacaoGestor,
    GravacaoAvaliacaoInicial,
    GravacaoMedicao,
    GrupoCompetencias,
    LeituraArquivo,
    LeituraAvaliacao,
    LeituraCiencia,
    OcorrenciaAvaliacao,
    LeituraConsultaCadin,
    LeituraDocumentoMensal,
    LeituraRecusa,
    NotaRecusada,
    SugestaoOutroContrato,
    LeituraItemMedicao,
    LeituraMemoria,
    LeituraDespesaVariavel,
    LeituraNotaFiscal,
    LeituraRetencao,
    NotaSelecionada,
    PainelExecucao,
    Reabertura,
    Requisitos,
    RespostaAvaliacao,
    ResumoCompetencia,
)
from app.services import servico_anexos
from app.services.contratos import avisos, calculos, documentos_execucao, leitor_nota_xml, servico_autenticacao, servico_diario, servico_retencao, valores
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.contratos.servico_configuracao_execucao import (
    _nome_chave,
    _ordem_checklist,
    checklist_ativo,
    formulario_ativo,
    puxar_checklist,
    reaproveitar_validos,
)
from app.services.contratos.servico_contratos import (
    designacoes_vigentes,
    eh_administrador,
    exigir_edicao,
    hoje,
    pode_dar_ciencia,
    papel_para_ciencia,
    obter_contrato,
    pode_editar,
    vigencias,
)
from app.services.contratos.servico_orcamento import apontamentos_da_vigencia, movimentos_em_ordem, previsao_salva_em_todas
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
# Mínimo de ciências da equipe para avançar a etapa (medição e alteração): uma ciência já basta
CIENCIAS_MINIMAS = 1
# Constantes de apoio: 100 (para percentuais) e a precisão de 4 casas das quantidades
CEM = Decimal(100)
QUATRO_CASAS = Decimal("0.0001")


# ---------------------------------------------------------------------------------------------
# Consultas auxiliares
# ---------------------------------------------------------------------------------------------

def _carregar_competencia(sessao: Session, contrato: Contrato, competencia_id: uuid.UUID) -> Competencia:
    """Competência do contrato com todos os registros filhos carregados, ou 404."""
    # A condição com o contrato impede abrir a competência de outro contrato pela URL
    competencia = sessao.scalar(
        select(Competencia)
        .where(Competencia.id == competencia_id, Competencia.contrato_id == contrato.id)
        .options(
            selectinload(Competencia.itens),
            selectinload(Competencia.notas),
            selectinload(Competencia.recusas),
            selectinload(Competencia.ciencias),
            selectinload(Competencia.memorias).selectinload(MemoriaMedicao.anexo),
            selectinload(Competencia.consultas_cadin),
            selectinload(Competencia.documentos),
            selectinload(Competencia.avaliacao),
            selectinload(Competencia.abatimentos_reajuste).selectinload(AbatimentoReajuste.reajuste),
        )
    )
    if competencia is None:
        raise RegistroNaoEncontrado("Competência")
    return competencia


def tem_avaliacao(competencia: Competencia) -> bool:
    """A competência tem (ou terá) a etapa de avaliação.

    A avaliação é copiada do formulário ativo ao concluir a medição (`puxar_avaliacao`). Até lá, a etapa existe se a competência
    regular ainda está na medição e há formulário ativo; depois, se a avaliação foi criada.
    """
    if competencia.avaliacao is not None:
        return True
    return competencia.tipo in ("regular", "adicional") and competencia.etapa_atual == "medicao" and formulario_ativo(competencia.contrato) is not None


def puxar_avaliacao(sessao: Session, contrato: Contrato, competencia: Competencia) -> None:
    """Início da avaliação: a competência copia o formulário ATIVO agora (sem formulário ativo, uma cópia antiga é mantida)."""
    formulario = formulario_ativo(contrato)
    if formulario is None:
        return
    competencia.avaliacao = None
    # A exclusão precisa ir ao banco antes da nova linha (há uma avaliação por competência)
    sessao.flush()
    competencia.avaliacao = AvaliacaoCompetencia(formulario_id=formulario.id, definicao=formulario.definicao)


# Pendências e alertas de execução (competências) anteriores a esta data foram "limpos": não aparecem em "Minhas pendências",
# nos alertas da carteira nem geram mais avisos de atraso
PENDENCIAS_A_PARTIR_DE = date(2026, 9, 1)


def anterior_ao_corte(competencia: Competencia) -> bool:
    """Competência anterior ao corte de alertas: a pendência dela não é cobrada.

    O corte é a maior entre o global (`PENDENCIAS_A_PARTIR_DE`) e a data "Desconsiderar alertas a partir de" do contrato, se houver."""
    desde = competencia.periodo_fim if competencia.tipo == "regular" else competencia.criado_em.date()
    contrato = competencia.contrato
    corte = max(PENDENCIAS_A_PARTIR_DE, contrato.alertas_a_partir_de) if contrato is not None and contrato.alertas_a_partir_de else PENDENCIAS_A_PARTIR_DE
    return desde < corte


def etapas_da_competencia(competencia: Competencia) -> list[str]:
    """Etapas desta competência em ordem (sem "avaliacao" quando não há formulário)."""
    return [e for e in ETAPAS if e != "avaliacao" or tem_avaliacao(competencia)]


def proxima_etapa(competencia: Competencia, etapa: str) -> str:
    """Etapa seguinte a `etapa` nesta competência."""
    etapas = etapas_da_competencia(competencia)
    return etapas[etapas.index(etapa) + 1]


def total_medido(competencia: Competencia) -> Decimal:
    """Total medido: soma de quantidade medida × preço de cada item, arredondado."""
    return calculos.arredondar(sum((i.quantidade_medida * i.valor_unitario for i in competencia.itens), ZERO))


def subtotal_medicao(competencia: Competencia) -> Decimal:
    """Subtotal dos itens que não são despesas variáveis."""
    return calculos.arredondar(sum((i.quantidade_medida * i.valor_unitario for i in competencia.itens if not i.despesa_variavel), ZERO))


def subtotal_despesas_variaveis(competencia: Competencia) -> Decimal:
    """Subtotal dos itens marcados como despesas variáveis."""
    return calculos.arredondar(sum((i.quantidade_medida * i.valor_unitario for i in competencia.itens if i.despesa_variavel), ZERO))


def tem_despesas_variaveis(competencia: Competencia) -> bool:
    return any(i.despesa_variavel for i in competencia.itens)


def total_despesas_juntadas(competencia: Competencia) -> Decimal:
    """Soma dos valores das notas de débito, recibos e outros documentos de despesas variáveis juntados."""
    return calculos.arredondar(sum((d.valor for d in competencia.despesas_variaveis), ZERO))


def desconto_reajuste(competencia: Competencia) -> Decimal:
    """Crédito de desconto de reajuste abatido nesta competência (soma dos abatimentos)."""
    return calculos.arredondar(sum((a.valor for a in competencia.abatimentos_reajuste), ZERO))


def valor_autorizado_bruto(competencia: Competencia) -> Decimal:
    """Total medido × % liberado pela avaliação, antes do desconto de reajuste."""
    return calculos.arredondar(total_medido(competencia) * percentual_liberado(competencia) / CEM)


def valor_autorizado(competencia: Competencia) -> Decimal:
    """Valor autorizado para a NF: medido × % liberado − desconto de reajuste (nunca negativo)."""
    return max(ZERO, valor_autorizado_bruto(competencia) - desconto_reajuste(competencia))


def valor_a_pagar(competencia: Competencia) -> Decimal:
    """Valor que a Ordem Bancária debita nas NEs apontadas.

    Com a nota fiscal concluída: a soma dos valores brutos de todas as notas mais os documentos de despesas variáveis. Antes disso, a estimativa é
    o valor autorizado da medição (medido × % liberado pela avaliação − desconto de reajuste).
    """
    if competencia.nf_concluida_em is not None and competencia.notas_fiscais:
        return calculos.arredondar(total_bruto_notas(competencia) + total_despesas_juntadas(competencia))
    return valor_autorizado(competencia)


def vencimento_pagamento(competencia: Competencia) -> date | None:
    """Vencimento do pagamento: data de recebimento da NF + prazo em dias corridos (vazio até a NF ser juntada)."""
    if competencia.nf_recebida_em and competencia.prazo_pagamento_dias:
        return competencia.nf_recebida_em + timedelta(days=competencia.prazo_pagamento_dias)
    return None


# Prazo para a empresa enviar a nota fiscal depois da medição concluída (o e-mail da medição avisa as 48 horas)
PRAZO_NOTA_FISCAL_HORAS = 48


def prazo_nota_fiscal(competencia: Competencia) -> datetime | None:
    """Limite de 48 h para a NF: conclusão da medição + 48 h, só enquanto a NF não foi juntada."""
    if competencia.medicao_concluida_em is None or competencia.nf_concluida_em is not None:
        return None
    return competencia.medicao_concluida_em + timedelta(hours=PRAZO_NOTA_FISCAL_HORAS)


def total_bruto_notas(competencia: Competencia) -> Decimal:
    """Soma dos valores brutos das notas fiscais juntadas."""
    return calculos.arredondar(sum((n.valor_bruto or ZERO for n in competencia.notas_fiscais), ZERO))


# ---------------------------------------------------------------------------------------------
# Crédito de desconto de reajuste (abatido nas próximas medições)
# ---------------------------------------------------------------------------------------------

def proxima_competencia_a_medir(contrato: Contrato, depois_de: Competencia | None = None) -> Competencia | None:
    """Primeira competência regular com a medição ainda aberta (depois de `depois_de`, se informada)."""
    candidatas = sorted(
        (c for c in contrato.competencias
         if c.tipo == "regular" and c.medicao_concluida_em is None and c is not depois_de
         and (depois_de is None or c.periodo_inicio > depois_de.periodo_inicio)),
        key=lambda c: c.periodo_inicio,
    )
    return candidatas[0] if candidatas else None


def registrar_credito_reajuste(sessao: Session, contrato: Contrato, reajuste, valor: Decimal) -> AbatimentoReajuste:
    """Crédito de um desconto retroativo: vai para a próxima competência a medir (ou fica pendente)."""
    abatimento = AbatimentoReajuste(contrato_id=contrato.id, reajuste_id=reajuste.id, valor=valor,
                                    competencia=proxima_competencia_a_medir(contrato), criado_em=agora_utc())
    sessao.add(abatimento)
    return abatimento


def vincular_creditos_pendentes(sessao: Session, contrato: Contrato) -> None:
    """Créditos sem competência (não havia o que medir) vão para a próxima competência a medir."""
    destino = proxima_competencia_a_medir(contrato)
    if destino is None:
        return
    for abatimento in sessao.scalars(select(AbatimentoReajuste).where(
        AbatimentoReajuste.contrato_id == contrato.id, AbatimentoReajuste.competencia_id.is_(None)
    )):
        abatimento.competencia = destino


def ajustar_abatimentos(sessao: Session, contrato: Contrato, competencia: Competencia) -> None:
    """Se o desconto passar do valor autorizado bruto, a sobra segue para a próxima competência a medir.

    Chamado ao concluir a medição e a avaliação (quando o % liberado fica definitivo). O abatimento
    reduzido continua na competência (mesmo zerado) e a sobra aponta para ele em `origem_id`, para que
    uma reabertura da medição possa devolvê-la (`recolher_sobras`).
    """
    excesso = desconto_reajuste(competencia) - valor_autorizado_bruto(competencia)
    if excesso <= 0:
        return
    destino = proxima_competencia_a_medir(contrato, depois_de=competencia)
    # Reduz os abatimentos mais recentes primeiro
    for abatimento in reversed(list(competencia.abatimentos_reajuste)):
        parte = min(excesso, abatimento.valor)
        if parte <= 0:
            continue
        abatimento.valor -= parte
        sessao.add(AbatimentoReajuste(contrato_id=contrato.id, reajuste_id=abatimento.reajuste_id, origem_id=abatimento.id,
                                      valor=parte, competencia=destino, criado_em=agora_utc()))
        excesso -= parte
        if excesso <= 0:
            break


def recolher_sobras(sessao: Session, competencia: Competencia) -> None:
    """Reabertura da medição: as sobras ainda não usadas voltam ao abatimento de origem."""
    ids = [a.id for a in competencia.abatimentos_reajuste]
    if not ids:
        return
    origens = {a.id: a for a in competencia.abatimentos_reajuste}
    for sobra in list(sessao.scalars(select(AbatimentoReajuste).where(AbatimentoReajuste.origem_id.in_(ids)))):
        # Sobra já abatida numa medição concluída fica onde está
        if sobra.competencia is not None and sobra.competencia.medicao_concluida_em is not None:
            continue
        origens[sobra.origem_id].valor += sobra.valor
        if sobra.competencia is not None:
            sobra.competencia.abatimentos_reajuste.remove(sobra)
        sessao.delete(sobra)


def compromissos(contrato: Contrato, exceto: uuid.UUID | None = None) -> dict[uuid.UUID, Decimal]:
    """Saldo reservado em cada NE pelas competências com medição concluída e ainda não pagas.

    As competências são percorridas em ordem de período e cada uma consome as suas NEs na ordem
    apontada, como fará a Ordem Bancária. `exceto` ignora a competência em edição.
    """
    # Saldo ainda livre e valor reservado em cada NE do contrato
    livre = {n.id: n.saldo for n in contrato.notas_empenho}
    reservado: dict[uuid.UUID, Decimal] = {n.id: ZERO for n in contrato.notas_empenho}
    # Competências medidas e ainda não pagas, em ordem cronológica
    pendentes = sorted(
        (c for c in contrato.competencias if c.medicao_concluida_em is not None and c.etapa_atual != "concluida" and c.id != exceto),
        key=lambda c: (c.periodo_inicio, c.tipo),
    )
    for competencia in pendentes:
        restante = valor_a_pagar(competencia)
        for selecao in competencia.notas:
            if restante <= 0:
                break
            # Cada NE contribui com o que ainda tiver de livre, até cobrir o valor da competência
            parcela = min(max(livre.get(selecao.nota_id, ZERO), ZERO), restante)
            if parcela > 0:
                livre[selecao.nota_id] -= parcela
                reservado[selecao.nota_id] += parcela
                restante -= parcela
    return reservado


def situacao_competencia(competencia: Competencia) -> str:
    """Situação exibida na lista: concluída, pendente (período não acabou), em andamento ou disponível."""
    if competencia.etapa_atual == "concluida":
        return "concluida"
    if not _liberada(competencia):
        return "pendente"
    if competencia.medicao_iniciada_em is not None or competencia.etapa_atual != "medicao":
        return "em_andamento"
    return "disponivel"


# Coluna que marca a conclusão de cada etapa paralela
CONCLUSAO_PARALELA = {"retencao": "retencao_concluida_em", "cadin": "cadin_concluido_em", "checklist": "checklist_concluido_em"}


def etapas_abertas(competencia: Competencia) -> list[str]:
    """Etapas que aceitam gravação agora. Depois da NF, retenção, CADIN e checklist ficam abertos ao mesmo tempo."""
    if competencia.etapa_atual in ETAPAS_PARALELAS:
        return [e for e in ETAPAS_PARALELAS if getattr(competencia, CONCLUSAO_PARALELA[e]) is None]
    return [] if competencia.etapa_atual == "concluida" else [competencia.etapa_atual]


def etapas_concluidas(competencia: Competencia) -> list[str]:
    """Etapas já concluídas (as paralelas pela data de conclusão; as demais pela posição)."""
    etapas = etapas_da_competencia(competencia)
    atual = etapas.index(competencia.etapa_atual)
    concluidas = []
    for indice, etapa in enumerate(etapas):
        if etapa == "concluida":
            continue
        if etapa in ETAPAS_PARALELAS and competencia.etapa_atual in ETAPAS_PARALELAS:
            feita = getattr(competencia, CONCLUSAO_PARALELA[etapa]) is not None
        else:
            feita = indice < atual
        if feita:
            concluidas.append(etapa)
    return concluidas


def concluir_etapa_paralela(competencia: Competencia, etapa: str) -> None:
    """Marca a etapa paralela como concluída; com as três concluídas, libera o documento consolidado."""
    setattr(competencia, CONCLUSAO_PARALELA[etapa], agora_utc())
    pendentes = [e for e in ETAPAS_PARALELAS if getattr(competencia, CONCLUSAO_PARALELA[e]) is None]
    competencia.etapa_atual = pendentes[0] if pendentes else "consolidado"


def _exigir_etapa(competencia: Competencia, etapa: str, descricao: str) -> None:
    """Levanta erro se `etapa` não estiver aberta na competência."""
    if etapa not in etapas_abertas(competencia):
        situacao = "já foi concluída" if etapa in etapas_concluidas(competencia) else "não está aberta"
        raise ErroRegraContrato(f"{descricao} {situacao} nesta competência (etapa atual: {competencia.etapa_atual}).")


def _liberada(competencia: Competencia) -> bool:
    """A medição só é liberada depois do fim do período, exceto nos contratos com "Liberar todas as competências"."""
    return competencia.tipo == "adicional" or competencia.contrato.liberar_todas_competencias or hoje() > competencia.periodo_fim


def _exigir_liberada(competencia: Competencia) -> None:
    """Só libera a medição depois do fim do período (não se mede um mês que ainda não acabou), salvo "Liberar todas as competências"."""
    if not _liberada(competencia):
        raise ErroRegraContrato(f"A medição será liberada após o encerramento do período ({competencia.periodo_fim:%d/%m/%Y}).")


def _papel_do_usuario(contrato: Contrato, usuario: Usuario) -> str | None:
    """Papel do usuário na equipe vigente (ex.: "gestor"), ou None se não fizer parte."""
    designacao = next((d for d in designacoes_vigentes(contrato) if d.usuario_id == usuario.id), None)
    return designacao.papel if designacao else None


def _nome(usuario: Usuario) -> str:
    """Nome de exibição do usuário."""
    return usuario.nome_completo or usuario.login


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    """Converte um anexo no formato de leitura da API (ou None)."""
    if anexo is None:
        return None
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em)


def _recusa(recusa, anexos: dict) -> LeituraRecusa:
    """Recusa no formato da API, com os arquivos das notas recusadas e o PDF da recusa."""
    def arq(valor):
        return _arquivo(anexos.get(uuid.UUID(valor))) if valor else None

    return LeituraRecusa(
        id=recusa.id, ordem=recusa.ordem, justificativa=recusa.justificativa, recusada_por_nome=recusa.recusada_por_nome, recusada_em=recusa.recusada_em,
        notas=[NotaRecusada(rotulo=n.get("rotulo") or n.get("numero") or "Nota fiscal", numero=n.get("numero"), valor_bruto=n.get("valor_bruto"),
                            chave=n.get("chave"), arquivo=arq(n.get("anexo_id")), xml=arq(n.get("xml_anexo_id"))) for n in recusa.notas],
        pdf=_arquivo(anexos.get(recusa.pdf_anexo_id)),
        email=EmailMedicao(enviado_em=recusa.email_enviado_em, ok=recusa.email_ok, destinatarios=recusa.email_destinatarios or [], erro=recusa.email_erro),
    )


def _auditar(sessao: Session, autor: Usuario, acao: str, contrato: Contrato, competencia: Competencia, **dados) -> None:
    """Registra a operação na auditoria, identificando contrato e competência."""
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"competencia": competencia.competencia, **dados})
    sincronizar_tarefas(sessao, competencia, autor)


def sincronizar_tarefas(sessao: Session, competencia: Competencia, autor: Usuario) -> None:
    """Depois de uma ação na competência, leva as tarefas dela no Módulo Tarefas ao estado novo (nunca derruba a ação: falha vira log)."""
    from app.services.contratos import servico_tarefas_contratos

    servico_tarefas_contratos.sincronizar_seguro(sessao, competencia, autor)


# ---------------------------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------------------------

def requisitos(contrato: Contrato) -> Requisitos:
    """Confere o que falta para gerar as competências; cada pendência vira uma frase para a tela."""
    pendencias = []
    if not contrato.itens:
        pendencias.append("Cadastre ao menos um item financeiro.")
    if not designacoes_vigentes(contrato):
        pendencias.append("Designe ao menos um integrante da equipe de gestão e fiscalização.")
    if not previsao_salva_em_todas(contrato):
        pendencias.append("Salve a previsão orçamentária de cada vigência (há itens sob demanda).")
    if checklist_ativo(contrato) is None:
        pendencias.append("Ative um checklist de documentos mensais.")
    if not any(n.saldo > 0 for n in contrato.notas_empenho):
        pendencias.append("Cadastre ao menos uma Nota de Empenho com saldo.")
    return Requisitos(prontos=not pendencias, pendencias=pendencias)


def _rotulo_do_trecho(trecho: valores.TrechoCompetencia, precos: list[Decimal], n: int) -> str:
    """Texto do trecho de um item ("01/09 a 19/09/2026 · preço anterior"): o sufixo só aparece quando o preço muda entre trechos."""
    base = f"{trecho.inicio:%d/%m} a {trecho.fim:%d/%m/%Y}"
    if n > 0 and precos[n] != precos[n - 1]:
        return f"{base} · preço reajustado"
    if n + 1 < len(precos) and precos[n] != precos[n + 1]:
        return f"{base} · preço anterior"
    return base


def itens_previstos(contrato: Contrato, periodo: calculos.PeriodoExecucao, itens_do_contrato=None) -> list[ItemMedicao]:
    """Fotografia dos itens na competência: preço vigente e quantidade prevista (pró-rata por item).

    A competência é cortada em trechos nas viradas (mudança de vigência ou data de efeito de reajuste). Sem virada, uma linha por item.
    Com virada, o item entra uma vez por trecho, com o preço do trecho; o mês cortado é pago pelos dias de cada parte (todos os itens,
    inclusive os "sempre integral"). Fora dele, vale a regra de sempre: pró-rata nos meses parciais para quem usa; mês cheio para os demais.

    `itens_do_contrato` permite calcular com itens alternativos (a prévia de uma correção usa cópias com os valores propostos, sem tocar no cadastro).
    """
    trechos = valores.trechos_da_competencia(contrato, periodo)
    dividido = len(trechos) > 1
    partes_por_mes: dict = {}
    for trecho in trechos:
        for parte in trecho.partes:
            partes_por_mes.setdefault(parte.competencia, []).append(parte)
    apontados_por_vigencia: dict = {}

    def apontados(sequencia: int) -> dict:
        if sequencia not in apontados_por_vigencia:
            apontados_por_vigencia[sequencia] = apontamentos_da_vigencia(contrato, sequencia)
        return apontados_por_vigencia[sequencia]

    itens = []
    for item in (contrato.itens if itens_do_contrato is None else itens_do_contrato):
        precos = [valores.preco_em(contrato, item, t.inicio) for t in trechos]
        for n, trecho in enumerate(trechos):
            quantidade, fator = ZERO, ZERO
            for parte in trecho.partes:
                irmas = partes_por_mes[parte.competencia]
                if item.tipo == "continuo":
                    # Mês cortado: pelos dias da parte; senão, pró-rata (se o item usar) ou mês cheio
                    f = parte.fator if (len(irmas) > 1 or item.calcula_pro_rata) else Decimal(1)
                    quantidade += valores.quantidade_mensal_em(contrato, item, parte.competencia) * f
                else:
                    # Sob demanda: o apontamento do mês na vigência da parte, repartido pelos dias se o mês tem mais de um preço nela
                    mesma_vigencia = [i for i in irmas if i.sequencia_vigencia == parte.sequencia_vigencia]
                    soma = sum((i.fator for i in mesma_vigencia), ZERO) or Decimal(1)
                    f = parte.fator / soma if len(mesma_vigencia) > 1 else Decimal(1)
                    quantidade += apontados(parte.sequencia_vigencia).get((item.id, parte.competencia), ZERO) * f
                fator += f
            linha = ItemMedicao(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo, calcula_pro_rata=item.calcula_pro_rata,
                valor_unitario=precos[n], fator_meses=fator, quantidade_prevista=quantidade.quantize(QUATRO_CASAS), quantidade_medida=ZERO,
                segmento=n + 1, periodo_rotulo="",
            )
            if dividido:
                linha.periodo_inicio, linha.periodo_fim, linha.sequencia_vigencia = trecho.inicio, trecho.fim, trecho.sequencia_vigencia
                linha.periodo_rotulo = _rotulo_do_trecho(trecho, precos, n)
            itens.append(linha)
    return itens


def competencias_abertas(contrato: Contrato) -> list[Competencia]:
    """Competências regulares com itens copiados e sem medição concluída: seguem o cadastro dos itens (as concluídas são histórico congelado).

    Competência que ainda não iniciou a medição não tem itens: ela os copia do cadastro quando a medição começa (`garantir_itens`).
    """
    return [c for c in contrato.competencias if c.tipo == "regular" and c.medicao_concluida_em is None and c.itens]


def _periodos_por_inicio(contrato: Contrato) -> dict:
    return {p.inicio: p for p in calculos.periodos_de_execucao(vigencias(contrato), contrato.periodicidade_meses)}


def sincronizar_competencia(contrato: Contrato, competencia: Competencia, periodos: dict | None = None, itens_do_contrato=None, aplicar: bool = True) -> dict | None:
    """Alinha as linhas de item de uma competência aberta ao cadastro, preservando a `quantidade_medida`.

    Atualiza preço, quantidade prevista, fator, ordem e descrição; cria a linha de item novo; remove a de item que saiu do contrato (se nada foi
    medido nele). Competência fora do calendário atual (migrada do SGI) não é tocada (`None`). Com `aplicar=False` só calcula (prévia).
    Devolve `{"alteradas": [...], "incluidas": [...], "removidas": [...], "valor_antes", "valor_depois"}`.
    """
    periodos = periodos if periodos is not None else _periodos_por_inicio(contrato)
    periodo = periodos.get(competencia.periodo_inicio)
    if periodo is None:
        return None
    atuais = {(i.item_id, i.segmento): i for i in competencia.itens if i.item_id is not None}
    novos = {(i.item_id, i.segmento): i for i in itens_previstos(contrato, periodo, itens_do_contrato)}
    resultado: dict = {"alteradas": [], "incluidas": [], "removidas": [], "valor_antes": ZERO, "valor_depois": ZERO}
    # Mudou a divisão do mês em trechos (reajuste ou prorrogação no meio do mês) e já há quantidade medida: as linhas não são refeitas
    if {c[1] for c in atuais} != {c[1] for c in novos} and any(i.quantidade_medida > 0 for i in competencia.itens):
        resultado["estrutura_mantida"] = True
        return resultado
    for linha in competencia.itens:
        resultado["valor_antes"] += linha.valor_unitario * linha.quantidade_prevista
    for chave, novo in novos.items():
        linha = atuais.get(chave)
        resultado["valor_depois"] += novo.valor_unitario * novo.quantidade_prevista
        if linha is None:
            resultado["incluidas"].append(novo.descricao)
            if aplicar:
                competencia.itens.append(novo)
            continue
        mudou = (linha.valor_unitario, linha.quantidade_prevista, linha.fator_meses) != (novo.valor_unitario, novo.quantidade_prevista, novo.fator_meses)
        if mudou:
            resultado["alteradas"].append(linha.descricao)
        if aplicar:
            linha.ordem, linha.descricao, linha.tipo, linha.calcula_pro_rata = novo.ordem, novo.descricao, novo.tipo, novo.calcula_pro_rata
            linha.valor_unitario, linha.fator_meses, linha.quantidade_prevista = novo.valor_unitario, novo.fator_meses, novo.quantidade_prevista
            linha.periodo_inicio, linha.periodo_fim, linha.periodo_rotulo, linha.sequencia_vigencia = novo.periodo_inicio, novo.periodo_fim, novo.periodo_rotulo, novo.sequencia_vigencia
    for chave, linha in atuais.items():
        if chave not in novos and linha.quantidade_medida == 0:
            resultado["removidas"].append(linha.descricao)
            if aplicar:
                competencia.itens.remove(linha)
    # O que foi medido nunca sai: linha de item removido com quantidade medida fica (a correção impede essa remoção antes)
    if aplicar:
        competencia.versao_cadastro_sincronizada = contrato.versao_cadastro
        if (resultado["alteradas"] or resultado["incluidas"] or resultado["removidas"]) and competencia.ciencias:
            competencia.ciencias.clear()  # as ciências atestavam os valores anteriores
            resultado["ciencias_invalidadas"] = True
    return resultado


def sincronizar_abertas(contrato: Contrato) -> list[tuple[Competencia, dict]]:
    """Sincroniza todas as competências abertas do contrato; devolve só as que mudaram."""
    periodos = _periodos_por_inicio(contrato)
    mudadas = []
    for competencia in competencias_abertas(contrato):
        r = sincronizar_competencia(contrato, competencia, periodos)
        if r and (r["alteradas"] or r["incluidas"] or r["removidas"]):
            mudadas.append((competencia, r))
    return mudadas


def garantir_itens(contrato: Contrato, competencia: Competencia) -> bool:
    """Início da medição: a competência liberada copia os itens do cadastro agora (uma única vez; depois ficam congelados).

    Antes disso (período em andamento) ela não guarda itens. Competências complementares e migradas do SGI já nascem completas
    ou fora do calendário e não são tocadas. Devolve se copiou.
    """
    if competencia.tipo != "regular" or competencia.itens or competencia.medicao_concluida_em is not None or not _liberada(competencia):
        return False
    periodo = _periodos_por_inicio(contrato).get(competencia.periodo_inicio)
    if periodo is None:
        return False
    competencia.itens = itens_previstos(contrato, periodo)
    competencia.versao_cadastro_sincronizada = contrato.versao_cadastro
    return True


def total_previsto_na_hora(contrato: Contrato, competencia: Competencia) -> Decimal:
    """Total previsto da competência: o das linhas copiadas ou, se ainda não começou a medição, o calculado agora pelo cadastro."""
    if competencia.itens:
        linhas = competencia.itens
    else:
        periodo = _periodos_por_inicio(contrato).get(competencia.periodo_inicio)
        linhas = itens_previstos(contrato, periodo) if periodo else []
    return calculos.arredondar(sum((i.quantidade_prevista * i.valor_unitario for i in linhas), ZERO))


def sincronizar_se_defasada(contrato: Contrato, competencia: Competencia) -> bool:
    """Rede de segurança: antes de escrever numa competência aberta, alinha-a ao cadastro se a versão ficou para trás. Devolve se algum valor mudou."""
    if competencia.itens and competencia.tipo == "regular" and competencia.medicao_concluida_em is None and competencia.versao_cadastro_sincronizada != contrato.versao_cadastro:
        r = sincronizar_competencia(contrato, competencia)
        return bool(r and (r["alteradas"] or r["incluidas"] or r["removidas"]))
    return False


def gerar_competencias(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> int:
    """Cria as competências que faltam (idempotente). Depois disso, itens e ordem ficam bloqueados."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    situacao = requisitos(contrato)
    if not situacao.prontos:
        raise ErroRegraContrato("Complete a base do contrato: " + " ".join(situacao.pendencias))
    # Períodos já cobertos. Competências migradas do SGI seguem o aniversário do contrato (ex.: 15/01 a
    # 14/02): um período civil que se sobrepõe a qualquer uma delas não é gerado de novo.
    existentes = [(c.periodo_inicio, c.periodo_fim) for c in contrato.competencias if c.tipo == "regular"]
    geradas = 0
    for periodo in calculos.periodos_de_execucao(vigencias(contrato), contrato.periodicidade_meses):
        if any(inicio <= periodo.fim and periodo.inicio <= fim for inicio, fim in existentes):
            continue
        # A competência nasce vazia: itens, formulário e checklist são copiados quando a etapa correspondente começa
        competencia = Competencia(
            competencia=periodo.competencia, periodo_inicio=periodo.inicio, periodo_fim=periodo.fim,
            sequencia_vigencia=periodo.sequencia_vigencia, etapa_atual="medicao", versao_cadastro_sincronizada=contrato.versao_cadastro,
        )
        contrato.competencias.append(competencia)
        geradas += 1
    # Crédito de desconto de reajuste sem competência a medir: vai para a primeira nova
    vincular_creditos_pendentes(sessao, contrato)
    auditar(sessao, autor.login, "contrato.execucao.gerar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"geradas": geradas})
    sessao.commit()
    return geradas


def painel(sessao: Session, contrato_id: uuid.UUID) -> PainelExecucao:
    """Aba Execução: pré-requisitos e competências agrupadas por vigência."""
    contrato = obter_contrato(sessao, contrato_id)
    grupos = []
    for vigencia in vigencias(contrato):
        competencias = [c for c in contrato.competencias if c.sequencia_vigencia == vigencia.sequencia]
        grupos.append(
            GrupoCompetencias(
                sequencia_vigencia=vigencia.sequencia, inicio=vigencia.inicio, fim=vigencia.fim,
                competencias=[resumo(c) for c in sorted(competencias, key=lambda c: (c.periodo_inicio, c.tipo == "adicional", c.numero_adicional))],
            )
        )
    return PainelExecucao(requisitos=requisitos(contrato), geradas=bool(contrato.competencias), grupos=grupos)


def resumo(competencia: Competencia) -> ResumoCompetencia:
    """Converte a competência na linha da lista da aba Execução."""
    return ResumoCompetencia(
        id=competencia.id, competencia=competencia.competencia, tipo=competencia.tipo, parte=competencia.parte,
        identificador=competencia.identificador, rotulo=competencia.numero_competencia, sequencia_vigencia=competencia.sequencia_vigencia,
        periodo_inicio=competencia.periodo_inicio, periodo_fim=competencia.periodo_fim, situacao=situacao_competencia(competencia),
        etapa_atual=competencia.etapa_atual,
        valor_medicao=total_medido(competencia) if competencia.medicao_iniciada_em else None,
        possui_avaliacao=tem_avaliacao(competencia), numero_adicional=competencia.numero_adicional,
    )


def localizar_competencia(sessao: Session, contrato_id: uuid.UUID, identificador: str) -> uuid.UUID:
    """Id da competência pelo identificador da rota `/contratos/:id/execucao/:identificador`.

    `AAAA-MM` (mês com uma competência só; num mês dividido, abre a 1ª parte), `AAAA-MM-1`/`AAAA-MM-2`
    (partes de um mês dividido entre vigências) ou `AAAA-MM-dif` (diferença de reajuste).
    """
    contrato = obter_contrato(sessao, contrato_id)
    # Busca exata; sem resultado para "AAAA-MM", tenta a 1ª parte de um mês dividido
    exatas = [c for c in contrato.competencias if c.identificador == identificador]
    if not exatas and re.fullmatch(r"\d{4}-\d{2}", identificador):
        exatas = [c for c in contrato.competencias if c.identificador == f"{identificador}-1"]
    if not exatas:
        raise RegistroNaoEncontrado("Competência")
    return exatas[0].id


# ---------------------------------------------------------------------------------------------
# Detalhe
# ---------------------------------------------------------------------------------------------

def _notas_fiscais(contrato: Contrato, competencia: Competencia) -> list[LeituraNotaFiscal]:
    """Notas fiscais juntadas (em ordem), com as conferências automáticas e o valor líquido de cada uma."""
    total = total_bruto_notas(competencia)
    esperado = servico_retencao.valor_autorizado(competencia)
    leituras = []
    for nota in competencia.notas_fiscais:
        # Valor líquido = bruto − retenções (nunca negativo)
        retencoes = {r: getattr(nota, f"retencao_{r}") or ZERO for r in ("ir", "inss", "iss", "pis", "cofins", "csll")}
        # A conferência "valor × autorizado" compara o total das notas e aparece só na primeira
        conferencias = servico_retencao.conferencias(contrato, competencia, nota.dados_xml, esperado if nota.ordem == competencia.notas_fiscais[0].ordem else None, total)
        leituras.append(LeituraNotaFiscal(
            id=nota.id, ordem=nota.ordem, numero=nota.numero, arquivo=_arquivo(nota.anexo), xml=_arquivo(nota.xml_anexo), dados_xml=nota.dados_xml,
            conferencias=[ConferenciaNota(**c.__dict__) for c in conferencias], valor_bruto=nota.valor_bruto,
            **{f"retencao_{r}": v for r, v in retencoes.items()},
            valor_liquido=max(ZERO, (nota.valor_bruto or ZERO) - sum(retencoes.values(), ZERO)),
        ))
    return leituras


def detalhar(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, usuario: Usuario) -> DetalheCompetencia:
    """Detalhe completo da competência (resposta de quase todas as rotas da execução)."""
    contrato = obter_contrato(sessao, contrato_id)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    # Primeiro acesso com o período encerrado: a medição começa e os itens são copiados (uma vez só)
    if garantir_itens(contrato, competencia):
        sessao.commit()
    # Todos os anexos da competência em uma consulta: {id: anexo}
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(_ids_anexos(competencia))))}
    selecionadas = [n.nota_id for n in competencia.notas]
    notas = {n.id: n for n in contrato.notas_empenho}
    # Saldo reservado por OUTRAS competências (esta fica de fora, pois é a que está sendo editada)
    reservado = compromissos(contrato, exceto=competencia.id)
    # Documentos iguais, ainda válidos, de outros contratos da mesma empresa (só com o checklist aberto)
    sugestoes = _candidatos_outros_contratos(sessao, contrato, competencia) if "checklist" in etapas_abertas(competencia) else {}

    def opcao_nota(nota: NotaEmpenho) -> NotaSelecionada:
        """NE no formato da tela, com o saldo livre já descontado do reservado."""
        return NotaSelecionada(id=nota.id, numero=nota.numero, saldo=nota.saldo, saldo_livre=nota.saldo - reservado.get(nota.id, ZERO))

    percentual = percentual_liberado(competencia)
    medido = total_medido(competencia)
    saldos = saldos_da_medicao(contrato, competencia)
    glosas_periodo = (
        [
            GlosaDoPeriodo(ocorrencia_id=o.id, data_ocorrencia=o.data_ocorrencia, descricao_ocorrencia=o.descricao,
                           registrada_por_nome=o.registrada_por_nome, item_id=g.item_id, descricao_item=g.descricao_item, quantidade=g.quantidade)
            for o in servico_diario.ocorrencias_do_periodo(contrato, competencia.periodo_inicio, competencia.periodo_fim)
            for g in o.glosas
        ]
        if competencia.tipo == "regular" else []
    )
    # Vencimento do pagamento = data de recebimento da NF + prazo em dias corridos
    vencimento = vencimento_pagamento(competencia)
    return DetalheCompetencia(
        **resumo(competencia).model_dump(),
        contrato_id=contrato.id, contrato_numero=contrato.numero, empresa_cnpj="".join(c for c in contrato.empresa.cnpj if c.isdigit()),
        etapas=etapas_da_competencia(competencia),
        pode_editar=pode_editar(sessao, contrato, usuario), integra_equipe=pode_dar_ciencia(sessao, contrato, usuario),
        pode_gerar_consolidado_novamente=pode_gerar_consolidado_novamente(contrato, usuario) and pode_editar(sessao, contrato, usuario),
        liberada=_liberada(competencia),
        itens=[
            LeituraItemMedicao(
                id=i.id, ordem=i.ordem, descricao=i.descricao, segmento=i.segmento, periodo_rotulo=i.periodo_rotulo or "", tipo=i.tipo, calcula_pro_rata=i.calcula_pro_rata,
                valor_unitario=i.valor_unitario, fator_meses=i.fator_meses, quantidade_prevista=i.quantidade_prevista,
                quantidade_medida=i.quantidade_medida, subtotal=calculos.arredondar(i.quantidade_medida * i.valor_unitario),
                saldo=saldos[i.id].saldo, glosas=saldos[i.id].glosas, saldo_liquido=saldos[i.id].saldo_liquido, despesa_variavel=i.despesa_variavel,
            )
            for i in competencia.itens
        ],
        total_previsto=calculos.arredondar(sum((i.quantidade_prevista * i.valor_unitario for i in competencia.itens), ZERO)),
        total_medido=medido,
        subtotal_medicao=subtotal_medicao(competencia), subtotal_despesas_variaveis=subtotal_despesas_variaveis(competencia),
        tem_despesas_variaveis=tem_despesas_variaveis(competencia),
        despesas_variaveis=[
            LeituraDespesaVariavel(id=d.id, ordem=d.ordem, tipo=d.tipo, numero=d.numero, rotulo=d.rotulo, valor=d.valor, arquivo=_arquivo(d.anexo))
            for d in competencia.despesas_variaveis
        ],
        notas_selecionadas=[opcao_nota(notas[n]) for n in selecionadas if n in notas],
        notas_disponiveis=[opcao_nota(n) for n in contrato.notas_empenho if n.saldo - reservado.get(n.id, ZERO) > 0],
        ciencias=[LeituraCiencia(usuario_id=c.usuario_id, nome=c.nome, papel=c.papel, registrada_em=c.registrada_em) for c in competencia.ciencias],
        ciencias_minimas=CIENCIAS_MINIMAS,
        memorias=[LeituraMemoria(versao=m.versao, criada_em=m.criado_em, arquivo=_arquivo(m.anexo), arquivo_despesas=_arquivo(m.anexo_despesas)) for m in competencia.memorias],
        medicao_concluida_em=competencia.medicao_concluida_em,
        avaliacao=_leitura_avaliacao(competencia.avaliacao, anexos, contrato) if competencia.avaliacao else None,
        percentual_autorizado=percentual,
        valor_autorizado=valor_autorizado(competencia),
        desconto_reajuste=desconto_reajuste(competencia),
        descontos_reajuste=[
            DescontoReajuste(reajuste_id=a.reajuste_id, mes_referencia=a.reajuste.mes_referencia, valor=a.valor)
            for a in competencia.abatimentos_reajuste if a.valor > 0
        ],
        valor_a_pagar=valor_a_pagar(competencia),
        avisos=(excedentes_da_medicao(contrato, competencia) if competencia.medicao_concluida_em is None else [])
        + avisos_de_impacto_tardio(contrato, competencia) + avisos_da_medicao_adicional(contrato, competencia),
        pode_incluir_adicional=contrato.permite_medicao_adicional and pode_editar(sessao, contrato, usuario),
        pode_excluir_adicional=competencia.tipo == "adicional" and competencia.etapa_atual != "concluida" and pode_editar(sessao, contrato, usuario),
        adicional_justificativa=competencia.adicional_justificativa, adicional_por_nome=competencia.adicional_por_nome,
        adicional_anexo=_arquivo(competencia.adicional_anexo),
        reaberturas_permitidas=pode_reabrir(sessao, contrato, usuario),
        glosas_periodo=glosas_periodo,
        email_nf=EmailMedicao(enviado_em=competencia.email_nf_enviado_em, ok=competencia.email_nf_ok,
                              destinatarios=competencia.email_nf_destinatarios or [], erro=competencia.email_nf_erro),
        email_retencao=EmailMedicao(enviado_em=competencia.email_retencao_enviado_em, ok=competencia.email_retencao_ok,
                                    destinatarios=competencia.email_retencao_destinatarios or [], erro=competencia.email_retencao_erro),
        retencao=LeituraRetencao(
            concluida_em=competencia.retencao_concluida_em, por_nome=competencia.retencao_por_nome,
            discriminacao_conferida=competencia.retencao_discriminacao_conferida, pdf=_arquivo(competencia.retencao_pdf_anexo),
        ) if competencia.retencao_concluida_em else None,
        pode_conferir_retencao=servico_retencao.pode_conferir(sessao, contrato, usuario),
        recusas=[_recusa(r, anexos) for r in competencia.recusas],
        pode_recusar="retencao" in etapas_abertas(competencia) and servico_retencao.pode_conferir(sessao, contrato, usuario),
        etapas_abertas=etapas_abertas(competencia),
        etapas_concluidas=etapas_concluidas(competencia),
        email_medicao=EmailMedicao(
            enviado_em=competencia.email_medicao_enviado_em, ok=competencia.email_medicao_ok,
            destinatarios=competencia.email_medicao_destinatarios or [], erro=competencia.email_medicao_erro,
        ),
        notas_fiscais=_notas_fiscais(contrato, competencia),
        nf_recebida_em=competencia.nf_recebida_em, prazo_pagamento_dias=competencia.prazo_pagamento_dias,
        vencimento_pagamento=vencimento, origem_valor_nf=competencia.origem_valor_nf, nf_concluida_em=competencia.nf_concluida_em,
        consultas_cadin=[
            LeituraConsultaCadin(
                id=c.id, possui_pendencia=c.possui_pendencia, pendencia=c.pendencia, texto_notificacao=c.texto_notificacao,
                certidao=_arquivo(anexos.get(c.certidao_anexo_id)), email=_arquivo(anexos.get(c.email_anexo_id)),
                criado_por_nome=c.criado_por_nome, criado_em=c.criado_em,
            )
            for c in competencia.consultas_cadin
        ],
        documentos=[
            LeituraDocumentoMensal(id=d.id, ordem=d.ordem, nome=d.nome, observacao=d.observacao, obrigatorio=d.obrigatorio, com_validade=d.com_validade,
                                   validade_ate=d.validade_ate, reaproveitado_de=d.reaproveitado_de, vale_outros_contratos=d.vale_outros_contratos,
                                   reaproveitado_contrato=d.reaproveitado_contrato, sugestao_outro_contrato=_sugestao(d, sugestoes),
                                   arquivo=_arquivo(anexos.get(d.anexo_id)))
            for d in sorted(competencia.documentos, key=_ordem_checklist)
        ],
        consolidado=_arquivo(competencia.consolidado_anexo),
        ordem_bancaria=_arquivo(competencia.ob_anexo),
        concluida_em=competencia.concluida_em,
    )


def _ids_anexos(competencia: Competencia) -> set[uuid.UUID]:
    """Todos os anexos da competência (usados no detalhe e para autorizar downloads)."""
    ids = {competencia.consolidado_anexo_id, competencia.ob_anexo_id, competencia.retencao_pdf_anexo_id, competencia.adicional_anexo_id}
    ids |= {n.anexo_id for n in competencia.notas_fiscais} | {n.xml_anexo_id for n in competencia.notas_fiscais}
    ids |= {d.anexo_id for d in competencia.despesas_variaveis} | {m.anexo_despesas_id for m in competencia.memorias}
    # Recusas da nota fiscal: o PDF da recusa e os arquivos das notas recusadas
    for recusa in competencia.recusas:
        ids.add(recusa.pdf_anexo_id)
        for nota in recusa.notas:
            ids |= {uuid.UUID(nota[k]) for k in ("anexo_id", "xml_anexo_id") if nota.get(k)}
    ids |= {m.anexo_id for m in competencia.memorias}
    ids |= {c.certidao_anexo_id for c in competencia.consultas_cadin} | {c.email_anexo_id for c in competencia.consultas_cadin}
    ids |= {d.anexo_id for d in competencia.documentos}
    if competencia.avaliacao:
        a = competencia.avaliacao
        ids |= {a.pdf_gerado_anexo_id, a.pdf_assinado_anexo_id, a.reconsideracao_anexo_id}
    return {i for i in ids if i}


def arquivo_da_competencia(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, anexo_id: uuid.UUID):
    """Baixa um arquivo da competência; recusa ids de anexos que não pertencem a ela."""
    contrato = obter_contrato(sessao, contrato_id)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if anexo_id not in _ids_anexos(competencia):
        raise RegistroNaoEncontrado("Arquivo")
    anexo = sessao.get(Anexo, anexo_id)
    return servico_anexos.resposta_download(anexo)


# ---------------------------------------------------------------------------------------------
# Etapa 1 — medição
# ---------------------------------------------------------------------------------------------

def _resolver_notas(contrato: Contrato, ids: list[uuid.UUID]) -> list[NotaEmpenho]:
    """Converte os ids escolhidos em NEs do contrato, na mesma ordem, recusando repetidos e estranhos."""
    if len(set(ids)) != len(ids):
        raise ErroRegraContrato("A mesma Nota de Empenho foi selecionada mais de uma vez.")
    notas = {n.id: n for n in contrato.notas_empenho}
    if any(i not in notas for i in ids):
        raise ErroRegraContrato("Uma das Notas de Empenho não pertence a este contrato.")
    return [notas[i] for i in ids]


def _exigir_saldo(notas: list[NotaEmpenho], valor: Decimal, reservado: dict[uuid.UUID, Decimal] | None = None) -> None:
    """Exige que as NEs cubram o valor. Com `reservado`, conta só o saldo livre (desconta outras competências a pagar)."""
    # Soma o saldo (livre, se houver reservas) das NEs escolhidas
    reservado = reservado or {}
    saldo = sum((n.saldo - reservado.get(n.id, ZERO) for n in notas), ZERO)
    if saldo < valor:
        numeros = ", ".join(n.numero for n in notas)
        tipo = "livre " if any(reservado.get(n.id) for n in notas) else ""
        raise ErroRegraContrato(
            f"As NEs selecionadas ({numeros}) não têm saldo {tipo}suficiente: saldo {tipo}R$ {saldo:.2f}; necessário R$ {valor:.2f}."
            + (" Parte do saldo está comprometida com competências já medidas e ainda não pagas." if tipo else "")
        )


@dataclass(frozen=True)
class SaldoItem:
    """Quanto pode ser medido de um item na competência: saldo − glosas do período = saldo líquido."""
    saldo: Decimal
    glosas: Decimal
    saldo_liquido: Decimal


def saldos_da_medicao(contrato: Contrato, competencia: Competencia) -> dict[uuid.UUID, SaldoItem]:
    """Saldo, glosas e saldo líquido de cada linha da medição (chave: id da linha da competência).

    - Saldo do item contínuo: a quantidade prevista da competência (já com pró-rata);
    - saldo do item sob demanda: o que resta do item na vigência (limite − executado nas outras competências);
    - glosas: soma das glosas do diário de bordo com data dentro do período da competência;
    - diferença de reajuste: sem glosas; o saldo é a quantidade já medida (fixa).
    """
    itens = {i.id: i for i in contrato.itens}
    regular = competencia.tipo == "regular"
    adicional = competencia.tipo == "adicional"
    # Glosas por período: cada trecho do mês (mês com virada) recebe as glosas das datas dele; sem trecho, as do período todo
    glosas_por_periodo: dict = {}

    def glosas_do_trecho(linha) -> dict:
        periodo = (linha.periodo_inicio or competencia.periodo_inicio, linha.periodo_fim or competencia.periodo_fim)
        if periodo not in glosas_por_periodo:
            glosas_por_periodo[periodo] = servico_diario.glosas_do_periodo(contrato, *periodo) if regular else {}
        return glosas_por_periodo[periodo]

    resultado = {}
    for linha in competencia.itens:
        item = itens.get(linha.item_id)
        if not regular and not (adicional and item is not None and item.tipo == "sob_demanda"):
            # Diferença de reajuste e medição adicional (itens contínuos): sem teto; a adicional só avisa quando passa do previsto
            saldo = linha.quantidade_medida
        elif item is not None and item.tipo == "sob_demanda":
            sequencia = linha.sequencia_vigencia or competencia.sequencia_vigencia
            limite = valores.limite_na_vigencia(contrato, item, sequencia)
            executado = valores.executado_na_vigencia(contrato, item, sequencia, exceto=competencia.id)
            # Outras linhas do mesmo item (outros trechos) nesta competência e na mesma vigência já consomem parte do saldo
            vizinhas = sum((o.quantidade_medida for o in competencia.itens
                            if o is not linha and o.item_id == linha.item_id and (o.sequencia_vigencia or competencia.sequencia_vigencia) == sequencia), ZERO)
            saldo = max(ZERO, limite - executado - vizinhas)
        else:
            saldo = linha.quantidade_prevista
        glosa = glosas_do_trecho(linha).get(linha.item_id, ZERO)
        resultado[linha.id] = SaldoItem(saldo, glosa, max(ZERO, saldo - glosa))
    return resultado


def excedentes_da_medicao(contrato: Contrato, competencia: Competencia) -> list[str]:
    """Linhas cuja medição passa do saldo líquido (saldo − glosas), com a explicação de cada uma."""
    saldos = saldos_da_medicao(contrato, competencia)
    avisos = []
    for linha in competencia.itens:
        saldo = saldos[linha.id]
        if linha.quantidade_medida > saldo.saldo_liquido:
            conta = f"saldo {saldo.saldo:.4f} − glosas {saldo.glosas:.4f}" if saldo.glosas else f"saldo {saldo.saldo:.4f}"
            dica = " Registre um aditamento para ampliar o limite." if linha.tipo == "sob_demanda" and not saldo.glosas else ""
            avisos.append(
                f"\"{linha.descricao_completa}\": a medição ({linha.quantidade_medida:.4f}) passa do saldo líquido "
                f"({saldo.saldo_liquido:.4f} = {conta}).{dica}"
            )
    return avisos


def salvar_medicao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoMedicao, autor: Usuario) -> None:
    """Etapa 1: grava as quantidades medidas e as NEs escolhidas (em ordem de consumo)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    garantir_itens(contrato, competencia)
    sincronizar_se_defasada(contrato, competencia)
    _exigir_liberada(competencia)
    _exigir_etapa(competencia, "medicao", "A medição")
    # A medição precisa trazer todos os itens da competência, nem mais nem menos
    itens = {i.id: i for i in competencia.itens}
    if {i.id for i in dados.itens} != set(itens) or len(dados.itens) != len(itens):
        raise ErroRegraContrato("Informe a medição de todos os itens da competência.")
    notas = _resolver_notas(contrato, dados.notas_empenho_ids)
    # Competência de diferença de reajuste: quantidades fixas (já medidas); só as NEs mudam
    if competencia.tipo == "diferenca_reajuste" and any(itens[linha.id].quantidade_medida != linha.quantidade_medida for linha in dados.itens):
        raise ErroRegraContrato("Na diferença de reajuste as quantidades são as já medidas e não podem ser alteradas; escolha só as NEs.")
    # Aplica as quantidades, anotando se alguma mudou
    alterou = False
    for linha in dados.itens:
        item = itens[linha.id]
        alterou |= item.quantidade_medida != linha.quantidade_medida
        item.quantidade_medida = linha.quantidade_medida
        if linha.despesa_variavel is not None:
            alterou |= item.despesa_variavel != linha.despesa_variavel
            item.despesa_variavel = linha.despesa_variavel
    # Nenhum item pode ser medido acima do saldo líquido (saldo − glosas do diário de bordo)
    excedentes = excedentes_da_medicao(contrato, competencia)
    if excedentes:
        raise ErroRegraContrato(" ".join(excedentes))
    # As NEs precisam cobrir o valor a pagar, descontado o que outras competências já reservaram
    _exigir_saldo(notas, valor_a_pagar(competencia), compromissos(contrato, exceto=competencia.id))
    # Se a seleção de NEs mudou, substitui a lista (a posição define a ordem de consumo)
    anteriores = [n.nota_id for n in competencia.notas]
    if anteriores != dados.notas_empenho_ids:
        alterou = True
        competencia.notas.clear()
        sessao.flush()
        competencia.notas.extend(SelecaoNotaEmpenho(nota_id=n.id, ordem=o) for o, n in enumerate(notas, start=1))
    # Ciências atestam a fotografia anterior: qualquer alteração as invalida
    if alterou and competencia.ciencias:
        competencia.ciencias.clear()
    competencia.medicao_iniciada_em = competencia.medicao_iniciada_em or agora_utc()
    _auditar(sessao, autor, "contrato.execucao.medicao.salvar", contrato, competencia, total=total_medido(competencia))
    sessao.commit()


def registrar_ciencia(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, autor: Usuario) -> None:
    """Etapa 1: registra a ciência do usuário logado na medição salva."""
    contrato = obter_contrato(sessao, contrato_id)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    garantir_itens(contrato, competencia)
    if sincronizar_se_defasada(contrato, competencia):
        sessao.commit()
        raise ErroRegraContrato("Os itens do contrato foram atualizados por uma correção de cadastro. Recarregue a página e confira os valores antes de dar ciência.")
    _exigir_liberada(competencia)
    _exigir_etapa(competencia, "medicao", "A medição")
    if competencia.medicao_iniciada_em is None:
        raise ErroRegraContrato("Salve a medição antes de registrar a ciência.")
    papel = papel_para_ciencia(sessao, contrato, autor)
    if papel is None:
        raise ErroRegraContrato("Somente integrantes da equipe de gestão e fiscalização registram ciência.")
    # Ciência repetida da mesma pessoa é ignorada (não gera erro)
    if any(c.usuario_id == autor.id for c in competencia.ciencias):
        return
    competencia.ciencias.append(CienciaMedicao(usuario_id=autor.id, nome=_nome(autor), papel=papel, registrada_em=agora_utc()))
    _auditar(sessao, autor, "contrato.execucao.medicao.ciencia", contrato, competencia, papel=papel)
    sessao.commit()


def _hash_medicao(contrato: Contrato, competencia: Competencia) -> str:
    """Impressão digital dos dados da medição, para saber se a memória em PDF precisa de nova versão."""
    origem = {
        "contrato": contrato.numero,
        "competencia": competencia.competencia.isoformat(),
        "itens": [[i.ordem, i.descricao_completa, str(i.valor_unitario), str(i.quantidade_prevista), str(i.quantidade_medida), i.despesa_variavel] for i in competencia.itens],
        "ciencias": [[c.usuario_id, c.nome, c.papel] for c in competencia.ciencias],
        "notas": [str(n.nota_id) for n in competencia.notas],
        "desconto_reajuste": str(desconto_reajuste(competencia)),
    }
    # `sort_keys` garante o mesmo texto (e o mesmo hash) para os mesmos dados
    return hashlib.sha256(json.dumps(origem, sort_keys=True).encode()).hexdigest()


def concluir_medicao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, notas_ids: list[uuid.UUID], autor: Usuario) -> None:
    """Etapa 1: conclui a medição, gera a memória de cálculo e avança para a próxima etapa."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    garantir_itens(contrato, competencia)
    sincronizar_se_defasada(contrato, competencia)
    _exigir_liberada(competencia)
    _exigir_etapa(competencia, "medicao", "A medição")
    if competencia.tipo == "adicional" and not any(i.quantidade_medida > 0 for i in competencia.itens):
        raise ErroRegraContrato("Informe a quantidade de ao menos um item para concluir a medição adicional.")
    # Regras para concluir: ciências mínimas, mesma seleção de NEs salva, saldo e limite dos itens sob demanda
    if len({c.usuario_id for c in competencia.ciencias}) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato("A conclusão exige ao menos uma ciência de integrante da equipe.")
    if [n.nota_id for n in competencia.notas] != notas_ids:
        raise ErroRegraContrato("As Notas de Empenho foram alteradas na tela. Salve a medição novamente antes de concluir.")
    notas = _resolver_notas(contrato, notas_ids)
    # Desconto de reajuste maior que a medição: a sobra segue para a próxima competência
    ajustar_abatimentos(sessao, contrato, competencia)
    _exigir_saldo(notas, valor_a_pagar(competencia), compromissos(contrato, exceto=competencia.id))
    # De novo na conclusão: uma glosa pode ter sido registrada depois de a medição ser salva
    excedentes = excedentes_da_medicao(contrato, competencia)
    if excedentes:
        raise ErroRegraContrato(" ".join(excedentes))
    # Gera o PDF, marca a conclusão, avança a etapa e atualiza o executado dos itens do contrato
    gerar_memoria(sessao, contrato, competencia, autor)
    competencia.medicao_concluida_em = agora_utc()
    # A avaliação começa agora: copia o formulário ativo neste momento
    puxar_avaliacao(sessao, contrato, competencia)
    competencia.etapa_atual = proxima_etapa(competencia, "medicao")
    atualizar_executado(contrato)
    _auditar(sessao, autor, "contrato.execucao.medicao.concluir", contrato, competencia, total=total_medido(competencia))
    avisos.medicao_concluida(sessao, contrato, competencia, autor)
    sessao.commit()


def gerar_memoria(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> MemoriaMedicao:
    """Memória de cálculo em PDF; nova versão só se os dados mudaram desde a última."""
    # Mesmos dados da última versão: reaproveita a memória existente
    origem = _hash_medicao(contrato, competencia)
    ultima = competencia.memorias[-1] if competencia.memorias else None
    if ultima and ultima.hash_origem == origem:
        return ultima
    versao = (ultima.versao + 1) if ultima else 1
    notas = {n.id: n for n in contrato.notas_empenho}
    conteudo = documentos_execucao.memoria_medicao(contrato, competencia, [notas[n.nota_id] for n in competencia.notas], versao, _nome(autor))
    nome = f"memoria-medicao-{contrato.numero_arquivo}-{competencia.competencia:%Y-%m}-v{versao}.pdf"
    anexo = servico_autenticacao.guardar_autenticado(
        sessao, conteudo, nome, "contrato-execucao-memoria", "memoria_medicao", contrato, competencia, autor.id, _nome(autor),
        [{"nome": c.nome, "papel": c.papel, "em": c.registrada_em} for c in competencia.ciencias],
    )
    # Com despesas variáveis, a medição delas sai em outro PDF (no consolidado vem depois da nota fiscal)
    anexo_despesas = None
    if tem_despesas_variaveis(competencia):
        conteudo_despesas = documentos_execucao.memoria_despesas_variaveis(contrato, competencia, versao, _nome(autor))
        anexo_despesas = servico_anexos.guardar_pdf_gerado(
            sessao, conteudo_despesas, f"medicao-despesas-variaveis-{contrato.numero_arquivo}-{competencia.competencia:%Y-%m}-v{versao}.pdf",
            "contrato-execucao-memoria", autor.id, contrato_id=contrato.id)
    memoria = MemoriaMedicao(versao=versao, anexo=anexo, anexo_despesas=anexo_despesas, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc())
    competencia.memorias.append(memoria)
    return memoria


def atualizar_executado(contrato: Contrato) -> None:
    """Quantidade executada de cada item = soma das medições concluídas (todas as vigências)."""
    for item in contrato.itens:
        item.quantidade_executada = sum(
            (
                linha.quantidade_medida
                for c in contrato.competencias
                if c.medicao_concluida_em is not None and c.tipo in ("regular", "adicional")
                for linha in c.itens
                if linha.item_id == item.id
            ),
            ZERO,
        ).quantize(QUATRO_CASAS, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------------------------
# Etapa 2 — avaliação dos serviços
# ---------------------------------------------------------------------------------------------

def _itens_formulario(definicao: dict) -> dict[str, dict]:
    """Itens do formulário indexados pelo id: {item_id: item}."""
    return {item["id"]: item for grupo in definicao.get("grupos", []) for item in grupo.get("itens", [])}


def _nota_maxima(definicao: dict) -> Decimal:
    """Maior nota da escala do formulário."""
    return max(Decimal(str(n["valor"])) for n in definicao["escala"])


def _validar_respostas(definicao: dict, respostas: list[RespostaAvaliacao], exigir_justificativa: str,
                       impactados: set[str] | frozenset[str] = frozenset()) -> list[dict]:
    """Confere as respostas e as devolve no formato gravado em JSON.

    Exige nota para todos os itens, só valores da escala e justificativa quando a nota é abaixo da máxima — ou quando é a
    máxima num item com ocorrências do diário de bordo no período (`impactados`).
    """
    itens = _itens_formulario(definicao)
    escala = {Decimal(str(n["valor"])) for n in definicao["escala"]}
    maxima = _nota_maxima(definicao)
    por_item = {r.item_id: r for r in respostas}
    if set(por_item) != set(itens):
        raise ErroRegraContrato("Informe a nota de todos os itens do formulário.")
    for item_id, resposta in por_item.items():
        if resposta.nota not in escala:
            raise ErroRegraContrato(f"A nota {resposta.nota} não pertence à escala do formulário.")
        if resposta.nota < maxima and not resposta.justificativa:
            raise ErroRegraContrato(f"{exigir_justificativa} \"{itens[item_id]['nome']}\" (nota abaixo da máxima).")
        if resposta.nota == maxima and item_id in impactados and not (resposta.justificativa or "").strip():
            raise ErroRegraContrato(f"O item \"{itens[item_id]['nome']}\" tem ocorrências no diário de bordo no período: "
                                    "justifique a nota máxima.")
    return [{"item_id": r.item_id, "nota": str(r.nota), "justificativa": r.justificativa} for r in respostas]


def _notas_por_item(avaliacao: AvaliacaoCompetencia) -> dict[str, Decimal]:
    """Nota vigente de cada item: a do gestor, se houver; senão, a da avaliação inicial."""
    # O dicionário do gestor vem por último e, por isso, sobrepõe as notas iniciais
    iniciais = {r["item_id"]: Decimal(r["nota"]) for r in avaliacao.respostas_iniciais or []}
    gestor = {r["item_id"]: Decimal(r["nota"]) for r in avaliacao.respostas_gestor or []}
    return {**iniciais, **gestor}


def nota_final(avaliacao: AvaliacaoCompetencia) -> Decimal | None:
    """Soma das notas dos grupos; em cada grupo, soma de nota × peso (planilha oficial, célula "Nota Final")."""
    if not avaliacao.respostas_iniciais:
        return None
    notas = _notas_por_item(avaliacao)
    # Cada item contribui com nota × peso ÷ 100
    total = sum(
        (notas.get(i["id"], ZERO) * Decimal(str(i["peso"])) / CEM for g in avaliacao.definicao.get("grupos", []) for i in g["itens"]),
        ZERO,
    )
    return calculos.arredondar(total)


def maximo_de_notas_minimas_por_grupo(avaliacao: AvaliacaoCompetencia) -> int:
    """Maior quantidade, entre os grupos, de itens com a nota mínima da escala (a "nota 0" da planilha)."""
    definicao = avaliacao.definicao
    if not avaliacao.respostas_iniciais or not definicao.get("escala"):
        return 0
    minima = min(Decimal(str(n["valor"])) for n in definicao["escala"])
    # Conta, em cada grupo, os itens com a nota mínima, e fica com o maior valor
    notas = _notas_por_item(avaliacao)
    return max((sum(1 for i in g["itens"] if notas.get(i["id"]) == minima) for g in definicao.get("grupos", [])), default=0)


def percentual_da_nota(definicao: dict, nota: Decimal, notas_minimas_no_grupo: int = 0) -> Decimal:
    """% liberado. Pela nota: faixa com mínimo ≤ nota ≤ máximo (entre várias, a de maior mínimo).

    Faixas com `notas_zero` também se aplicam quando algum grupo tem ao menos essa quantidade de notas
    mínimas. Entre as faixas aplicáveis vale a de menor percentual. Sem faixa: 0%.
    """
    faixas = definicao.get("faixas", [])
    # Faixas em que a nota cabe; entre elas, vale a de maior mínimo (a mais específica)
    pela_nota = [
        f for f in faixas
        if Decimal(str(f["minimo"])) <= nota and (f.get("maximo") is None or nota <= Decimal(str(f["maximo"])))
    ]
    candidatas = [max(pela_nota, key=lambda f: Decimal(str(f["minimo"])))] if pela_nota else []
    # Faixas acionadas pela quantidade de notas mínimas em um grupo
    candidatas += [f for f in faixas if f.get("notas_zero") and notas_minimas_no_grupo >= int(f["notas_zero"])]
    # Entre as candidatas, vale a mais restritiva (menor percentual)
    if not candidatas:
        return ZERO
    return min(Decimal(str(f["percentual"])) for f in candidatas)


def percentual_liberado(competencia: Competencia) -> Decimal:
    """% do pagamento autorizado. Sem avaliação: 100%. Avaliação sem notas ainda: 100% (provisório)."""
    avaliacao = competencia.avaliacao
    if avaliacao is None:
        return CEM
    nota = nota_final(avaliacao)
    return CEM if nota is None else percentual_da_nota(avaliacao.definicao, nota, maximo_de_notas_minimas_por_grupo(avaliacao))


def ocorrencias_da_avaliacao(contrato: Contrato, competencia: Competencia) -> list[OcorrenciaAvaliacao]:
    """Ocorrências do período que impactam itens do formulário desta avaliação (com os ids desses itens)."""
    avaliacao = competencia.avaliacao
    if avaliacao is None:
        return []
    por_item = servico_diario.itens_impactados(contrato, competencia, avaliacao.definicao)
    itens_da: dict[uuid.UUID, list[str]] = {}
    ocorrencias: dict[uuid.UUID, object] = {}
    for item_id, lista in por_item.items():
        for o in lista:
            ocorrencias[o.id] = o
            itens_da.setdefault(o.id, []).append(item_id)
    return [OcorrenciaAvaliacao(id=o.id, data_ocorrencia=o.data_ocorrencia, descricao=o.descricao, registrada_por_nome=o.registrada_por_nome,
                                itens=itens_da[o.id]) for o in sorted(ocorrencias.values(), key=lambda x: (x.data_ocorrencia, x.criado_em))]


def _utc(valor: datetime) -> datetime:
    """Data com fuso UTC (o SQLite dos testes devolve datas sem fuso)."""
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


def avisos_da_medicao_adicional(contrato: Contrato, competencia: Competencia) -> list[str]:
    """Aviso informativo (não bloqueia): itens contínuos cuja soma das medições do mesmo período passa da quantidade prevista."""
    if competencia.tipo != "adicional":
        return []
    do_periodo = [c for c in contrato.competencias if c.periodo_inicio == competencia.periodo_inicio and c.tipo in ("regular", "adicional")]
    previstas: dict = {}
    medidas: dict = {}
    for c in do_periodo:
        for linha in c.itens:
            if linha.tipo != "continuo" or linha.item_id is None:
                continue
            if c.tipo == "regular":
                previstas[linha.item_id] = previstas.get(linha.item_id, ZERO) + linha.quantidade_prevista
            medidas[linha.item_id] = medidas.get(linha.item_id, ZERO) + linha.quantidade_medida
    descricoes = {i.item_id: i.descricao for i in competencia.itens}
    return [
        f"\"{descricoes[item_id]}\": somando as medições do período ({total:.4f}), passa da quantidade prevista ({previstas[item_id]:.4f}); "
        "fica registrado como medição adicional."
        for item_id, total in medidas.items() if item_id in previstas and item_id in descricoes and total > previstas[item_id]
    ]


def excluir_medicao_adicional(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui a medição adicional com tudo o que ela tem (itens, ciências, avaliação, nota fiscal etc.), para a equipe refazê-la do zero.

    Só vale para `tipo = adicional` e para quem edita a execução. Uma adicional já paga precisa ser zerada antes (o estorno da OB
    fica no extrato das NEs). Os arquivos continuam guardados no histórico de anexos.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if competencia.tipo != "adicional":
        raise ErroRegraContrato("Somente medições adicionais podem ser excluídas.", conflito=True)
    if competencia.etapa_atual == "concluida":
        raise ErroRegraContrato("Esta medição adicional já foi paga. Zere a competência (o que estorna a ordem bancária) antes de excluí-la.", conflito=True)
    auditar(sessao, autor.login, "contrato.execucao.adicional.excluir", f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"competencia": competencia.competencia, "numero_adicional": competencia.numero_adicional, "etapa": competencia.etapa_atual,
                   "justificativa_original": competencia.adicional_justificativa})
    sessao.delete(competencia)
    sessao.commit()


def _itens_zerados_da_adicional(contrato: Contrato, periodo_inicio: date) -> list[ItemMedicao]:
    """Itens do contrato com quantidades zeradas e o preço do início do período (início de uma medição adicional)."""
    return [
        ItemMedicao(
            item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo, calcula_pro_rata=item.calcula_pro_rata,
            valor_unitario=valores.preco_em(contrato, item, periodo_inicio), fator_meses=Decimal(1), quantidade_prevista=ZERO,
            quantidade_medida=ZERO, segmento=1, periodo_rotulo="",
        )
        for item in contrato.itens
    ]


def incluir_medicao_adicional(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, justificativa: str,
                              arquivo: BinaryIO | None, nome_arquivo: str, autor: Usuario) -> Competencia:
    """Cria outra medição (e outro pagamento) no período da competência, com justificativa e anexo opcional.

    Exige o contrato com "medição adicional" permitida. Os itens do contrato entram zerados, com o preço do início do período;
    o resto do rito (ciências, avaliação, nota fiscal, retenção, CADIN, checklist, consolidado e OB) é o das demais competências.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if not contrato.permite_medicao_adicional:
        raise ErroRegraContrato("Este contrato não permite medição adicional. Ative a opção no cadastro do contrato.", conflito=True)
    origem = _carregar_competencia(sessao, contrato, competencia_id)
    justificativa = justificativa.strip()
    if not justificativa:
        raise ErroRegraContrato("Informe a justificativa da nova medição.")
    numero = 1 + max((c.numero_adicional for c in contrato.competencias if c.tipo == "adicional" and c.periodo_inicio == origem.periodo_inicio), default=0)
    adicional = Competencia(
        tipo="adicional", numero_adicional=numero, competencia=origem.competencia, periodo_inicio=origem.periodo_inicio, periodo_fim=origem.periodo_fim,
        sequencia_vigencia=origem.sequencia_vigencia, etapa_atual="medicao", versao_cadastro_sincronizada=contrato.versao_cadastro,
        adicional_justificativa=justificativa, adicional_por_nome=_nome(autor),
    )
    adicional.itens.extend(_itens_zerados_da_adicional(contrato, origem.periodo_inicio))
    if arquivo is not None:
        adicional.adicional_anexo = servico_anexos.guardar_pdf(
            sessao, arquivo, nome_arquivo, "contrato-execucao-medicao-adicional", autor.id, contrato_id=contrato.id
        )
    contrato.competencias.append(adicional)
    sessao.flush()
    _auditar(sessao, autor, "contrato.execucao.adicional.incluir", contrato, adicional, numero=numero, justificativa=justificativa)
    avisos.medicao_adicional_incluida(sessao, contrato, adicional, autor)
    sessao.commit()
    return adicional


def avisos_de_impacto_tardio(contrato: Contrato, competencia: Competencia) -> list[str]:
    """Ocorrência que impacta a avaliação registrada depois de salva a avaliação (as notas foram dadas sem ela)."""
    avaliacao = competencia.avaliacao
    if avaliacao is None or avaliacao.avaliacao_inicial_em is None or avaliacao.concluida_em is not None:
        return []
    limite = _utc(avaliacao.avaliacao_gestor_em or avaliacao.avaliacao_inicial_em)
    tardias = [o for o in servico_diario.ocorrencias_que_impactam(contrato, competencia) if _utc(o.criado_em) > limite]
    return [f"Ocorrência de {o.data_ocorrencia:%d/%m/%Y} registrada no diário depois da avaliação impacta itens avaliados: revise as notas."
            for o in tardias]


def _leitura_avaliacao(avaliacao: AvaliacaoCompetencia, anexos: dict, contrato: Contrato | None = None) -> LeituraAvaliacao:
    """Converte a avaliação para o formato de leitura (com nota final e % liberado calculados)."""
    nota = nota_final(avaliacao)
    return LeituraAvaliacao(
        definicao=avaliacao.definicao,
        respostas_iniciais=avaliacao.respostas_iniciais or [], avaliacao_inicial_em=avaliacao.avaliacao_inicial_em,
        respostas_gestor=avaliacao.respostas_gestor or [], complemento_gestor=avaliacao.complemento_gestor,
        avaliacao_gestor_em=avaliacao.avaliacao_gestor_em, nota_final=nota,
        percentual_liberado=(
            percentual_da_nota(avaliacao.definicao, nota, maximo_de_notas_minimas_por_grupo(avaliacao)) if nota is not None else None
        ),
        precisa_avaliacao_gestor=precisa_avaliacao_gestor(avaliacao),
        ciencias=[
            LeituraCiencia(usuario_id=c["usuario_id"], nome=c["nome"], papel=c["papel"], registrada_em=c["ciencia_em"])
            for c in ciencias_ateste(avaliacao)
        ],
        pdf_gerado=_arquivo(anexos.get(avaliacao.pdf_gerado_anexo_id)), pdf_assinado=_arquivo(anexos.get(avaliacao.pdf_assinado_anexo_id)),
        concluida_em=avaliacao.concluida_em, reconsideracoes=avaliacao.reconsideracoes,
        reconsideracao=_arquivo(anexos.get(avaliacao.reconsideracao_anexo_id)),
        ocorrencias=ocorrencias_da_avaliacao(contrato, avaliacao.competencia) if contrato is not None else [],
        email=EmailMedicao(enviado_em=avaliacao.email_enviado_em, ok=avaliacao.email_ok,
                           destinatarios=avaliacao.email_destinatarios or [], erro=avaliacao.email_erro),
    )


def _avaliacao_aberta(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, autor: Usuario, exigir_equipe: bool = True):
    """Valida e devolve (contrato, competência, avaliação) para as rotas da etapa 2.

    Exige edição no contrato, formulário na competência e a etapa de avaliação aberta; por padrão,
    também exige que o usuário seja da equipe.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if competencia.avaliacao is None:
        raise ErroRegraContrato("Esta competência não tem formulário de avaliação.")
    _exigir_etapa(competencia, "avaliacao", "A avaliação")
    if exigir_equipe and not pode_dar_ciencia(sessao, contrato, autor):
        raise ErroRegraContrato("Somente integrantes da equipe de gestão e fiscalização avaliam os serviços.")
    return contrato, competencia, competencia.avaliacao


def ciencias_ateste(avaliacao: AvaliacaoCompetencia) -> list[dict]:
    """Ciências registradas no ateste: [{"papel", "usuario_id", "nome", "ciencia_em"}].

    Ficam na coluna JSON `assinaturas`. Registros antigos (e os migrados do SGI) podem trazer
    pessoas indicadas que não deram ciência (`ciencia_em` vazio): essas não contam e são omitidas.
    """
    return [a for a in avaliacao.assinaturas or [] if a.get("ciencia_em")]


def precisa_avaliacao_gestor(avaliacao: AvaliacaoCompetencia) -> bool:
    """A avaliação do gestor só é necessária quando alguma nota inicial ficou abaixo da máxima."""
    if not avaliacao.respostas_iniciais:
        return False
    maxima = _nota_maxima(avaliacao.definicao)
    return any(Decimal(r["nota"]) < maxima for r in avaliacao.respostas_iniciais)


def avaliacao_pronta_para_ciencia(avaliacao: AvaliacaoCompetencia) -> bool:
    """Notas fechadas: avaliação inicial salva e, se for necessária, a do gestor também."""
    if not avaliacao.respostas_iniciais:
        return False
    return not precisa_avaliacao_gestor(avaliacao) or avaliacao.avaliacao_gestor_em is not None


def _invalidar_documento(avaliacao: AvaliacaoCompetencia) -> None:
    """Mudanças nas notas apagam as ciências do ateste e invalidam o PDF já gerado (como na medição)."""
    avaliacao.assinaturas, avaliacao.assinaturas_definidas_em = [], None
    avaliacao.pdf_gerado_anexo_id = None


def salvar_avaliacao_inicial(sessao: Session, contrato_id, competencia_id, dados: GravacaoAvaliacaoInicial, autor: Usuario) -> None:
    """Etapa 2: grava as notas da avaliação inicial (qualquer integrante da equipe)."""
    contrato, competencia, avaliacao = _avaliacao_aberta(sessao, contrato_id, competencia_id, autor)
    impactados = set(servico_diario.itens_impactados(contrato, competencia, avaliacao.definicao))
    avaliacao.respostas_iniciais = _validar_respostas(avaliacao.definicao, dados.respostas, "Justifique a nota do item", impactados)
    avaliacao.avaliador_inicial_id, avaliacao.avaliacao_inicial_em = autor.id, agora_utc()
    # Todas as notas na máxima: a avaliação do gestor deixa de ser necessária, e uma feita antes
    # (sobre notas iniciais que mudaram) é descartada para não sobrepor as novas notas
    if not precisa_avaliacao_gestor(avaliacao):
        avaliacao.respostas_gestor, avaliacao.complemento_gestor = [], ""
        avaliacao.gestor_id, avaliacao.avaliacao_gestor_em = None, None
    _invalidar_documento(avaliacao)
    _auditar(sessao, autor, "contrato.execucao.avaliacao.inicial", contrato, competencia)
    sessao.commit()


def salvar_avaliacao_gestor(sessao: Session, contrato_id, competencia_id, dados: GravacaoAvaliacaoGestor, autor: Usuario) -> None:
    """Etapa 2: grava as notas do gestor e o complemento geral (definem a nota final)."""
    contrato, competencia, avaliacao = _avaliacao_aberta(sessao, contrato_id, competencia_id, autor)
    if not avaliacao.respostas_iniciais:
        raise ErroRegraContrato("Registre a avaliação inicial antes da avaliação do gestor.")
    # Só há avaliação do gestor quando alguma nota inicial ficou abaixo da máxima
    if not precisa_avaliacao_gestor(avaliacao):
        raise ErroRegraContrato("Todas as notas iniciais estão na máxima: a avaliação do gestor não é necessária.")
    impactados = set(servico_diario.itens_impactados(contrato, competencia, avaliacao.definicao))
    avaliacao.respostas_gestor = _validar_respostas(avaliacao.definicao, dados.respostas, "Complemente a nota do item", impactados)
    avaliacao.complemento_gestor = dados.complemento
    avaliacao.gestor_id, avaliacao.avaliacao_gestor_em = autor.id, agora_utc()
    _invalidar_documento(avaliacao)
    _auditar(sessao, autor, "contrato.execucao.avaliacao.gestor", contrato, competencia, nota=nota_final(avaliacao))
    sessao.commit()


def registrar_ciencia_ateste(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Etapa 2: registra a ciência do usuário no ateste (qualquer integrante vigente da equipe).

    Funciona como a ciência da medição: uma por pessoa, com o papel da equipe fotografado.
    Uma ciência (`CIENCIAS_MINIMAS`) já libera a exportação do PDF.
    """
    contrato = obter_contrato(sessao, contrato_id)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    avaliacao = competencia.avaliacao
    if avaliacao is None:
        raise ErroRegraContrato("Esta competência não tem formulário de avaliação.")
    _exigir_etapa(competencia, "avaliacao", "A avaliação")
    if not avaliacao_pronta_para_ciencia(avaliacao):
        raise ErroRegraContrato("Conclua as notas da avaliação antes de registrar a ciência no ateste.")
    papel = papel_para_ciencia(sessao, contrato, autor)
    if papel is None:
        raise ErroRegraContrato("Somente integrantes da equipe de gestão e fiscalização registram ciência.")
    # Ciência repetida da mesma pessoa é ignorada (não gera erro)
    if any(c["usuario_id"] == autor.id for c in ciencias_ateste(avaliacao)):
        return
    # Reatribui a lista (e não usa append) para o SQLAlchemy perceber a mudança na coluna JSON
    ciencia = {"papel": papel, "usuario_id": autor.id, "nome": _nome(autor), "ciencia_em": agora_utc().isoformat()}
    avaliacao.assinaturas = [*ciencias_ateste(avaliacao), ciencia]
    _auditar(sessao, autor, "contrato.execucao.avaliacao.ciencia_ateste", contrato, competencia, papel=papel)
    sessao.commit()


def gerar_pdf_avaliacao(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Etapa 2: gera o PDF do relatório de avaliação, depois de ao menos uma ciência no ateste."""
    contrato, competencia, avaliacao = _avaliacao_aberta(sessao, contrato_id, competencia_id, autor, exigir_equipe=False)
    # Basta uma das pessoas indicadas ter dado ciência; as demais podem registrar depois, até a conclusão
    if len(ciencias_ateste(avaliacao)) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato("Registre ao menos uma ciência da equipe no ateste antes de exportar o PDF.")
    conteudo = documentos_execucao.relatorio_avaliacao(contrato, competencia, nota_final(avaliacao), percentual_liberado(competencia), _nome(autor))
    nome = f"avaliacao-{contrato.numero_arquivo}-{competencia.competencia:%Y-%m}.pdf"
    # O PDF leva a Folha de autenticação (código, hash e quem deu ciência no ateste); a via assinada pela contratada continua sendo enviada à parte
    anexo = servico_autenticacao.guardar_autenticado(
        sessao, conteudo, nome, "contrato-execucao-avaliacao", "avaliacao", contrato, competencia, autor.id, _nome(autor),
        [{"nome": c["nome"], "papel": c["papel"], "em": c["ciencia_em"]} for c in ciencias_ateste(avaliacao)],
    )
    sessao.flush()
    avaliacao.pdf_gerado_anexo_id = anexo.id
    _auditar(sessao, autor, "contrato.execucao.avaliacao.pdf", contrato, competencia)
    sessao.commit()


def enviar_avaliacao_assinada(sessao: Session, contrato_id, competencia_id, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Etapa 2: recebe a via assinada pela contratada e conclui a avaliação."""
    contrato, competencia, avaliacao = _avaliacao_aberta(sessao, contrato_id, competencia_id, autor, exigir_equipe=False)
    if avaliacao.pdf_gerado_anexo_id is None:
        raise ErroRegraContrato("Exporte o PDF da avaliação antes de enviar a via assinada pela contratada.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-execucao-avaliacao-assinada", autor.id, contrato_id=contrato.id)
    sessao.flush()
    avaliacao.pdf_assinado_anexo_id, avaliacao.concluida_em = anexo.id, agora_utc()
    competencia.etapa_atual = proxima_etapa(competencia, "avaliacao")
    # Com o % liberado definitivo, o desconto de reajuste que não couber segue para a próxima competência
    ajustar_abatimentos(sessao, contrato, competencia)
    _auditar(sessao, autor, "contrato.execucao.avaliacao.concluir", contrato, competencia, percentual=percentual_liberado(competencia))
    sessao.commit()


def reconsiderar_avaliacao(sessao: Session, contrato_id, competencia_id, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """A contratada pede reconsideração uma única vez, antes da nota fiscal: a avaliação reabre."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    avaliacao = competencia.avaliacao
    if avaliacao is None or avaliacao.concluida_em is None:
        raise ErroRegraContrato("A reconsideração só é possível depois de concluída a avaliação.")
    _exigir_etapa(competencia, "nota_fiscal", "A reconsideração")
    if avaliacao.reconsideracoes >= 1:
        raise ErroRegraContrato("A reconsideração já foi utilizada nesta competência.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-execucao-reconsideracao", autor.id, contrato_id=contrato.id)
    sessao.flush()
    # Registra o pedido e desfaz a conclusão: a avaliação volta a ficar aberta para novas notas
    avaliacao.reconsideracao_anexo_id, avaliacao.reconsideracoes = anexo.id, avaliacao.reconsideracoes + 1
    avaliacao.concluida_em, avaliacao.pdf_assinado_anexo_id = None, None
    _invalidar_documento(avaliacao)
    competencia.etapa_atual = "avaliacao"
    _auditar(sessao, autor, "contrato.execucao.avaliacao.reconsiderar", contrato, competencia)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Etapa 3 — nota fiscal
# ---------------------------------------------------------------------------------------------

def _ler_xml(arquivo_xml: tuple) -> tuple[bytes, dict]:
    """Lê o XML enviado (conteúdo e dados normalizados); XML ilegível ou de outro tipo vira `ErroRegraContrato`."""
    conteudo = arquivo_xml[0].read()
    dados = leitor_nota_xml.ler_nota(conteudo).como_dict()
    if not dados.get("valor_bruto"):
        raise ErroRegraContrato("O XML não traz o valor da nota fiscal.")
    return conteudo, dados


def _exigir_nota_inedita(sessao: Session, competencia: Competencia, chave: str | None, qual: str) -> None:
    """A mesma nota (chave) não pode ser juntada em outra competência."""
    if not chave:
        return
    outra = sessao.scalar(
        select(NotaFiscalCompetencia).where(NotaFiscalCompetencia.competencia_id != competencia.id, NotaFiscalCompetencia.chave == chave)
    )
    if outra is not None:
        raise ErroRegraContrato(
            f"A nota fiscal {qual} (chave {chave}) já foi juntada à competência {outra.competencia.numero_competencia} "
            f"do contrato {outra.competencia.contrato.numero}."
        )


MAXIMO_NOTAS = 20


def registrar_nota_fiscal(
    sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: dict, notas: list[dict], arquivos: list[tuple],
    xmls: list[tuple], autor: Usuario, despesas: list[dict] | None = None, arquivos_despesas: list[tuple] | None = None,
) -> None:
    """Etapa 3: junta uma ou mais notas fiscais (PDF obrigatório; XML opcional); os valores vêm dos XMLs ou, sem XML, são informados.

    `dados`: recebida_em e prazo_pagamento_dias. `notas`: a lista final, na ordem desejada; cada item traz `id` (nota já
    registrada, que mantém os arquivos que não forem trocados) e/ou `arquivo` e `xml` (posições nas listas `arquivos` e `xmls`).
    Notas que ficam fora da lista são removidas. As retenções lidas dos XMLs ficam como sugestão para a etapa de retenção
    de tributos, onde o Financeiro confere e confirma.

    Com item marcado como despesa variável na medição, a etapa exige ao menos uma nota fiscal **e** ao menos um documento de despesa
    (`despesas`: nota de débito, recibo ou outros, com valor e PDF), e a soma dos documentos precisa ser igual ao Subtotal - Despesas
    Variáveis. Os documentos não vão para a retenção (só a nota fiscal passa pela validação do Financeiro); ficam juntados e entram no consolidado.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "nota_fiscal", "A nota fiscal")
    if not notas:
        raise ErroRegraContrato("Junte pelo menos uma nota fiscal.")
    if len(notas) > MAXIMO_NOTAS:
        raise ErroRegraContrato(f"No máximo {MAXIMO_NOTAS} notas fiscais por competência.")
    existentes = {n.id: n for n in competencia.notas_fiscais}
    preparadas = []  # (nota existente | None, posição do PDF, posição do XML, conteúdo e dados lidos do XML | None, rótulo)
    chaves: dict[str, int] = {}
    for posicao, item in enumerate(notas, start=1):
        existente = existentes.get(item.get("id")) if item.get("id") else None
        if item.get("id") and existente is None:
            raise ErroRegraContrato(f"A nota fiscal {posicao} não pertence a esta competência.")
        ipdf, ixml = item.get("arquivo"), item.get("xml")
        for indice, lista, qual in ((ipdf, arquivos, "PDF"), (ixml, xmls, "XML")):
            if indice is not None and not 0 <= indice < len(lista):
                raise ErroRegraContrato(f"Arquivo {qual} da nota fiscal {posicao} não foi enviado.")
        # O PDF é obrigatório em cada nota (na correção depois de reabrir, o arquivo anterior pode ser mantido)
        if ipdf is None and (existente is None or existente.anexo_id is None):
            raise ErroRegraContrato(f"Selecione a nota fiscal {posicao} em PDF.")
        if ixml is not None:
            lido = _ler_xml(xmls[ixml])
        elif existente is not None and existente.dados_xml:
            lido = (None, existente.dados_xml)
        else:
            # Sem XML: o valor bruto (e, se quiser, o número) é informado; não há chave nem retenções sugeridas
            valor = item.get("valor_bruto") or (existente.valor_bruto if existente is not None else None)
            if not valor:
                raise ErroRegraContrato(f"Informe o valor bruto da nota fiscal {posicao} (ou selecione o XML).")
            lido = (None, {"valor_bruto": str(valor), "numero": item.get("numero") or (existente.numero if existente is not None else ""), "manual": True})
        chave = lido[1].get("chave")
        if chave:
            if chave in chaves:
                raise ErroRegraContrato(f"A nota fiscal {posicao} é a mesma da nota {chaves[chave]}.")
            chaves[chave] = posicao
            _exigir_nota_inedita(sessao, competencia, chave, str(posicao))
        preparadas.append((existente, ipdf, ixml, lido, posicao))
    preparadas_despesas = _preparar_despesas(competencia, despesas or [], arquivos_despesas or [])
    # Todas as notas (e os documentos de despesas variáveis) são pagas pelas NEs apontadas na medição: o saldo livre delas precisa cobrir o total
    total = calculos.arredondar(sum((Decimal(lido[1]["valor_bruto"]) for _, _, _, lido, _ in preparadas), ZERO))
    total_despesas = calculos.arredondar(sum((item["valor"] for item, *_ in preparadas_despesas), ZERO))
    ne = _resolver_notas(contrato, [n.nota_id for n in competencia.notas])
    _exigir_saldo(ne, total + total_despesas, compromissos(contrato, exceto=competencia.id))

    # Remove as notas que ficaram de fora e libera a ordem (a restrição de unicidade é por competência e ordem)
    mantidas = {e.id for e, *_ in preparadas if e is not None}
    for nota in list(competencia.notas_fiscais):
        if nota.id not in mantidas:
            competencia.notas_fiscais.remove(nota)
    sessao.flush()
    for nota in competencia.notas_fiscais:
        nota.ordem += 1000
    sessao.flush()
    categoria_xml = "contrato-execucao-nf-xml"
    for existente, ipdf, ixml, lido, posicao in preparadas:
        nota = existente
        if nota is None:
            nota = NotaFiscalCompetencia(competencia_id=competencia.id, ordem=posicao)
            competencia.notas_fiscais.append(nota)
        nota.ordem = posicao
        if ipdf is not None:
            nota.anexo = servico_anexos.guardar_pdf(sessao, arquivos[ipdf][0], arquivos[ipdf][1], "contrato-execucao-nf", autor.id, contrato_id=contrato.id)
        if ixml is not None:
            nota.xml_anexo = servico_anexos.guardar_arquivo_gerado(
                sessao, lido[0], xmls[ixml][1] or "nota_fiscal.xml", "application/xml", categoria_xml, autor.id, contrato_id=contrato.id)
        _aplicar_nota(nota, lido[1])
    _gravar_despesas(sessao, contrato, competencia, preparadas_despesas, arquivos_despesas or [], autor)
    competencia.nf_recebida_em, competencia.prazo_pagamento_dias = dados["recebida_em"], dados["prazo_pagamento_dias"]
    competencia.origem_valor_nf = None
    competencia.nf_concluida_em = agora_utc()
    # Uma NF nova (ou corrigida) exige nova conferência de tributos
    competencia.retencao_concluida_em, competencia.retencao_pdf_anexo_id = None, None
    competencia.retencao_por_id, competencia.retencao_por_nome, competencia.retencao_discriminacao_conferida = None, "", False
    # As etapas paralelas começam agora: o checklist ativo é copiado neste momento
    puxar_checklist(contrato, competencia)
    competencia.etapa_atual = proxima_etapa(competencia, "nota_fiscal")
    sessao.flush()
    _auditar(sessao, autor, "contrato.execucao.nota_fiscal.concluir", contrato, competencia,
             notas=[{"numero": n.numero, "chave": n.chave, "bruto": n.valor_bruto} for n in competencia.notas_fiscais], bruto=total,
             despesas_variaveis=[{"tipo": d.tipo, "numero": d.numero, "valor": d.valor} for d in competencia.despesas_variaveis])
    avisos.nota_fiscal_juntada(sessao, contrato, competencia, autor)
    sessao.commit()


def _preparar_despesas(competencia: Competencia, despesas: list[dict], arquivos: list[tuple]) -> list[tuple]:
    """Confere os documentos de despesas variáveis: obrigatórios com item marcado, PDF em cada um e soma igual ao subtotal marcado.

    Devolve `(item, existente | None, posição do PDF)` na ordem final. Sem item marcado, não há documentos (a lista precisa vir vazia)."""
    if not tem_despesas_variaveis(competencia):
        if despesas:
            raise ErroRegraContrato("Esta competência não tem item marcado como despesa variável: não junte documentos de despesas variáveis.")
        return []
    if not despesas:
        raise ErroRegraContrato("Há itens de despesas variáveis na medição: junte ao menos uma nota de débito, recibo ou outro documento da despesa.")
    if len(despesas) > MAXIMO_NOTAS:
        raise ErroRegraContrato(f"No máximo {MAXIMO_NOTAS} documentos de despesas variáveis por competência.")
    existentes = {d.id: d for d in competencia.despesas_variaveis}
    preparadas = []
    for posicao, item in enumerate(despesas, start=1):
        existente = existentes.get(item.get("id")) if item.get("id") else None
        if item.get("id") and existente is None:
            raise ErroRegraContrato(f"O documento de despesa {posicao} não pertence a esta competência.")
        indice = item.get("arquivo")
        if indice is not None and not 0 <= indice < len(arquivos):
            raise ErroRegraContrato(f"O PDF do documento de despesa {posicao} não foi enviado.")
        if indice is None and (existente is None or existente.anexo_id is None):
            raise ErroRegraContrato(f"Selecione o PDF do documento de despesa {posicao}.")
        preparadas.append((item, existente, indice))
    esperado, informado = subtotal_despesas_variaveis(competencia), calculos.arredondar(sum((item["valor"] for item, *_ in preparadas), ZERO))
    if informado != esperado:
        raise ErroRegraContrato(
            f"A soma dos documentos de despesas variáveis (R$ {informado:,.2f}) precisa ser igual ao Subtotal - Despesas Variáveis da medição (R$ {esperado:,.2f})."
        )
    return preparadas


def _gravar_despesas(sessao: Session, contrato: Contrato, competencia: Competencia, preparadas: list[tuple], arquivos: list[tuple], autor: Usuario) -> None:
    """Substitui a lista de documentos de despesas variáveis pela final (mantém o PDF dos que não foram trocados)."""
    mantidas = {e.id for _, e, _ in preparadas if e is not None}
    for documento in list(competencia.despesas_variaveis):
        if documento.id not in mantidas:
            competencia.despesas_variaveis.remove(documento)
    sessao.flush()
    for documento in competencia.despesas_variaveis:
        documento.ordem += 1000
    sessao.flush()
    for posicao, (item, existente, indice) in enumerate(preparadas, start=1):
        documento = existente
        if documento is None:
            documento = DespesaVariavel(competencia_id=competencia.id, ordem=posicao, tipo=item["tipo"], valor=item["valor"])
            competencia.despesas_variaveis.append(documento)
        documento.ordem, documento.tipo, documento.valor, documento.numero = posicao, item["tipo"], item["valor"], (item.get("numero") or "")[:100]
        if indice is not None:
            documento.anexo = servico_anexos.guardar_pdf(sessao, arquivos[indice][0], arquivos[indice][1], "contrato-execucao-despesa-variavel", autor.id, contrato_id=contrato.id)


def _aplicar_nota(nota: NotaFiscalCompetencia, dados: dict) -> None:
    """Grava número, chave, bruto e dados do XML; as retenções do XML ficam como sugestão para a conferência.

    Nota sem XML (`dados["manual"]`): só número e valor bruto; sem dados do XML, chave nem retenções sugeridas.
    """
    nota.numero = (dados.get("numero") or "")[:100]
    nota.chave = dados.get("chave")
    nota.valor_bruto = Decimal(dados["valor_bruto"])
    nota.dados_xml = None if dados.get("manual") else dados
    for tributo in ("ir", "inss", "iss", "pis", "cofins", "csll"):
        setattr(nota, f"retencao_{tributo}", Decimal((dados.get("retencoes") or {}).get(tributo) or "0"))


def _validar_retencoes(retencoes: dict[str, Decimal], bruto: Decimal, qual: str) -> None:
    """Retenções não podem ser negativas nem somar mais que o valor bruto da nota."""
    if any(v < 0 for v in retencoes.values()):
        raise ErroRegraContrato("As retenções não podem ser negativas.")
    if sum(retencoes.values(), ZERO) > bruto:
        raise ErroRegraContrato(f"A soma das retenções da nota {qual} passa do valor bruto.")


# ---------------------------------------------------------------------------------------------
# Etapa 4 — CADIN
# ---------------------------------------------------------------------------------------------

def registrar_cadin(
    sessao: Session, contrato_id, competencia_id, possui_pendencia: bool, pendencia: str, texto_notificacao: str,
    certidao: tuple, email: tuple | None, autor: Usuario,
) -> None:
    """Etapa 4: registra a consulta ao CADIN; sem pendência, a etapa é concluída."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "cadin", "A consulta ao CADIN")
    # Com pendência, a descrição e o e-mail de comunicação à contratada são obrigatórios
    if possui_pendencia and (not pendencia.strip() or email is None):
        raise ErroRegraContrato("Com pendência no CADIN, descreva a pendência e anexe o e-mail de comunicação.")
    # Cada consulta é guardada (histórico); os textos da pendência só valem quando há pendência
    consulta = ConsultaCadin(
        possui_pendencia=possui_pendencia, pendencia=pendencia.strip() if possui_pendencia else "",
        texto_notificacao=texto_notificacao.strip() if possui_pendencia else "",
        certidao_anexo=servico_anexos.guardar_pdf(sessao, certidao[0], certidao[1], "contrato-execucao-cadin-certidao", autor.id, contrato_id=contrato.id),
        email_anexo=servico_anexos.guardar_pdf(sessao, email[0], email[1], "contrato-execucao-cadin-email", autor.id, contrato_id=contrato.id) if possui_pendencia and email else None,
        criado_por_id=autor.id, criado_por_nome=_nome(autor), criado_em=agora_utc(),
    )
    competencia.consultas_cadin.append(consulta)
    # Com pendência, a etapa continua aberta até uma nova consulta sem pendência
    if not possui_pendencia:
        concluir_etapa_paralela(competencia, "cadin")
    _auditar(sessao, autor, "contrato.execucao.cadin", contrato, competencia, possui_pendencia=possui_pendencia)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Etapa 5 — checklist mensal
# ---------------------------------------------------------------------------------------------

def _candidatos_outros_contratos(sessao: Session, contrato: Contrato, competencia: Competencia) -> dict[str, tuple[DocumentoMensal, Competencia, Contrato]]:
    """Documentos da empresa ainda válidos, já juntados em OUTROS contratos da mesma empresa, por nome (sem diferenciar maiúsculas/espaços).

    Só entram os marcados como "documento da empresa": com validade, a que cubra o último dia do período desta competência (mesmo critério do
    reaproveitamento entre competências); sem validade, os juntados na mesma competência (mês) do outro contrato. Havendo mais de um com o mesmo nome, vale o de maior validade. Só procura se esta competência tem
    algum documento da empresa ainda sem anexo.
    """
    if not any(d.vale_outros_contratos and d.anexo_id is None for d in competencia.documentos):
        return {}
    consulta = (
        select(DocumentoMensal, Competencia, Contrato)
        .join(Competencia, DocumentoMensal.competencia_id == Competencia.id)
        .join(Contrato, Competencia.contrato_id == Contrato.id)
        .where(
            Contrato.empresa_id == contrato.empresa_id, Contrato.id != contrato.id,
            DocumentoMensal.vale_outros_contratos.is_(True), DocumentoMensal.anexo_id.is_not(None),
            or_(
                # Com validade: ainda vale no fim do período; sem validade: foi juntado na mesma competência (mês) do outro contrato
                and_(DocumentoMensal.com_validade.is_(True), DocumentoMensal.validade_ate >= competencia.periodo_fim),
                and_(DocumentoMensal.com_validade.is_(False), Competencia.tipo == "regular", Competencia.competencia == competencia.competencia),
            ),
        )
    )
    melhores: dict[str, tuple[DocumentoMensal, Competencia, Contrato]] = {}
    for documento, origem_competencia, origem_contrato in sessao.execute(consulta):
        chave = _nome_chave(documento.nome)
        atual = melhores.get(chave)
        if atual is None or (documento.validade_ate or date.min) > (atual[0].validade_ate or date.min):
            melhores[chave] = (documento, origem_competencia, origem_contrato)
    return melhores


def _sugestao(documento: DocumentoMensal, sugestoes: dict) -> SugestaoOutroContrato | None:
    """Sugestão de reaproveitamento para um documento da empresa ainda sem anexo."""
    par = sugestoes.get(_nome_chave(documento.nome)) if documento.vale_outros_contratos and documento.anexo_id is None else None
    if par is None:
        return None
    origem, origem_competencia, origem_contrato = par
    return SugestaoOutroContrato(
        origem_id=origem.id, contrato_numero=origem_contrato.numero, competencia=origem.reaproveitado_de or origem_competencia.competencia,
        validade_ate=origem.validade_ate, arquivo_nome=origem.anexo.nome_original if origem.anexo else "",
    )


def _copiar_de_outro_contrato(documento: DocumentoMensal, par: tuple[DocumentoMensal, Competencia, Contrato]) -> None:
    """Copia o arquivo e a validade; a origem fica guardada para a tela (em cadeia, mantém a origem original)."""
    origem, origem_competencia, origem_contrato = par
    documento.anexo_id, documento.enviado_em, documento.enviado_por_id = origem.anexo_id, origem.enviado_em, origem.enviado_por_id
    documento.validade_ate = origem.validade_ate
    documento.reaproveitado_de = origem.reaproveitado_de or origem_competencia.competencia
    documento.reaproveitado_contrato = origem.reaproveitado_contrato or origem_contrato.numero


def _concluir_se_completo(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> None:
    """Com todos os documentos anexados (obrigatórios e opcionais), a etapa do checklist conclui sozinha."""
    if all(d.anexo_id for d in competencia.documentos):
        concluir_etapa_paralela(competencia, "checklist")
        _estender_validos(sessao, contrato, competencia, autor)


def reaproveitar_de_outro_contrato(sessao: Session, contrato_id, competencia_id, documento_id: uuid.UUID, origem_id: uuid.UUID, autor: Usuario) -> None:
    """Etapa 5: traz para o documento o arquivo do mesmo documento da empresa, ainda válido, de outro contrato da mesma empresa."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "checklist", "O checklist")
    documento = next((d for d in competencia.documentos if d.id == documento_id), None)
    if documento is None:
        raise RegistroNaoEncontrado("Documento do checklist")
    if not documento.vale_outros_contratos or documento.anexo_id is not None:
        raise ErroRegraContrato("Este documento não aceita reaproveitamento de outro contrato (precisa ser documento da empresa e estar sem anexo).")
    par = _candidatos_outros_contratos(sessao, contrato, competencia).get(_nome_chave(documento.nome))
    if par is None or par[0].id != origem_id:
        raise ErroRegraContrato("O documento de origem não está mais disponível ou não vale para esta competência.")
    _copiar_de_outro_contrato(documento, par)
    sessao.flush()
    _concluir_se_completo(sessao, contrato, competencia, autor)
    _auditar(sessao, autor, "contrato.execucao.checklist.reaproveitar_contrato", contrato, competencia,
             documentos=[documento.nome], contrato_origem=par[2].numero)
    sessao.commit()


def reaproveitar_todos_de_outros_contratos(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> list[str]:
    """Etapa 5: traz de uma vez todos os documentos da empresa que têm um igual, ainda válido, em outro contrato. Devolve os nomes."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "checklist", "O checklist")
    candidatos = _candidatos_outros_contratos(sessao, contrato, competencia)
    trazidos, origens = [], set()
    for documento in competencia.documentos:
        par = candidatos.get(_nome_chave(documento.nome))
        if par is not None and documento.vale_outros_contratos and documento.anexo_id is None:
            _copiar_de_outro_contrato(documento, par)
            trazidos.append(documento.nome)
            origens.add(par[2].numero)
    if not trazidos:
        raise ErroRegraContrato("Não há documentos válidos de outros contratos da empresa para trazer.")
    sessao.flush()
    _concluir_se_completo(sessao, contrato, competencia, autor)
    _auditar(sessao, autor, "contrato.execucao.checklist.reaproveitar_contrato", contrato, competencia,
             documentos=trazidos, contratos_origem=sorted(origens))
    sessao.commit()
    return trazidos


def _estender_validos(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> None:
    """Com o checklist concluído, os documentos com validade ainda válidos passam para a competência seguinte."""
    reaproveitados = reaproveitar_validos(contrato, competencia)
    if reaproveitados:
        _auditar(sessao, autor, "contrato.execucao.checklist.reaproveitar", contrato, competencia, documentos=reaproveitados)


def enviar_documento_mensal(sessao: Session, contrato_id, competencia_id, documento_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario,
                            validade_ate: date | None = None) -> None:
    """Etapa 5: anexa o PDF de um documento do checklist mensal (documento com validade exige a data de validade)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "checklist", "O checklist")
    documento = next((d for d in competencia.documentos if d.id == documento_id), None)
    if documento is None:
        raise RegistroNaoEncontrado("Documento do checklist")
    if documento.com_validade and validade_ate is None:
        raise ErroRegraContrato("Informe até quando o documento é válido.")
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-execucao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    # Um envio novo substitui o arquivo (inclusive um reaproveitado) e a validade
    documento.validade_ate, documento.reaproveitado_de, documento.reaproveitado_contrato = (validade_ate if documento.com_validade else None), None, None
    sessao.flush()
    # Com todos os documentos anexados (obrigatórios e opcionais), a etapa conclui sozinha
    if all(d.anexo_id for d in competencia.documentos):
        concluir_etapa_paralela(competencia, "checklist")
        _estender_validos(sessao, contrato, competencia, autor)
    _auditar(sessao, autor, "contrato.execucao.checklist.enviar", contrato, competencia, documento=documento.nome)
    sessao.commit()


def concluir_checklist(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Conclui a etapa com os obrigatórios anexados; os opcionais podem ficar sem anexo."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "checklist", "O checklist")
    faltando = [d.nome for d in competencia.documentos if d.obrigatorio and not d.anexo_id]
    if faltando:
        raise ErroRegraContrato("Anexe os documentos obrigatórios: " + "; ".join(faltando) + ".")
    concluir_etapa_paralela(competencia, "checklist")
    _estender_validos(sessao, contrato, competencia, autor)
    _auditar(sessao, autor, "contrato.execucao.checklist.concluir", contrato, competencia,
             opcionais_sem_anexo=[d.nome for d in competencia.documentos if not d.anexo_id])
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Etapa 6 — documento consolidado
# ---------------------------------------------------------------------------------------------

def pode_gerar_consolidado_novamente(contrato: Contrato, usuario: Usuario) -> bool:
    """Gerar o consolidado **novamente** (já existe um) é de todos que podem editar o contrato, com os mesmos direitos da primeira geração.

    A edição já é exigida por `gerar_consolidado` e pelo detalhe da competência (`pode_gerar_consolidado_novamente and pode_editar`); aqui não há restrição extra."""
    return True


def gerar_consolidado(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Etapa 6: gera o PDF consolidado (todos os documentos da competência, na ordem de execução).

    Quem pode editar o contrato gera e gera novamente (substituir um
    consolidado existente) é só do gestor do contrato ou do SuperRoot, inclusive depois da OB.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if competencia.etapa_atual not in ("consolidado", "ordem_bancaria", "concluida"):
        rotulos = {"medicao": "medição", "avaliacao": "avaliação", "nota_fiscal": "nota fiscal", "retencao": "retenção de tributos",
                   "cadin": "CADIN", "checklist": "checklist"}
        faltam = [rotulos[e] for e in etapas_da_competencia(competencia) if e in rotulos and e not in etapas_concluidas(competencia)]
        raise ErroRegraContrato("O documento consolidado só é gerado com todas as etapas anteriores concluídas. Falta concluir: "
                                + ", ".join(faltam) + ".")
    # Reaproveita o detalhe (mesmos números da tela) para montar o resumo executivo do PDF
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(_ids_anexos(competencia))))}
    # Nome completo de quem enviou cada arquivo (vai na contracapa: "Enviado em … por …")
    ids_envio = {a.enviado_por_id for a in anexos.values() if a.enviado_por_id}
    enviados_por = {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids_envio)))} if ids_envio else {}
    detalhe = detalhar(sessao, contrato_id, competencia_id, autor)
    # Ciências que valem para a Folha de autenticação: as da medição e as do ateste da avaliação
    ciencias = [{"nome": c.nome, "papel": c.papel, "em": c.registrada_em} for c in competencia.ciencias]
    if competencia.avaliacao is not None:
        ciencias += [{"nome": c["nome"], "papel": c["papel"], "em": c["ciencia_em"]} for c in ciencias_ateste(competencia.avaliacao)]
    conteudo, sha_composicao = documentos_execucao.consolidado(contrato, competencia, detalhe, anexos, _nome(autor), enviados_por, ciencias)
    nome = f"consolidado-{contrato.numero_arquivo}-{competencia.competencia:%Y-%m}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, nome, "contrato-execucao-consolidado", autor.id, contrato_id=contrato.id)
    competencia.consolidado_anexo, competencia.consolidado_em = anexo, agora_utc()
    sessao.flush()
    servico_autenticacao.registrar(sessao, anexo, sha_composicao, "consolidado", contrato, competencia, _nome(autor), competencia.consolidado_em,
                                   servico_autenticacao.retrato_ciencias(ciencias))
    if competencia.etapa_atual == "consolidado":
        competencia.etapa_atual = "ordem_bancaria"
    _auditar(sessao, autor, "contrato.execucao.consolidado", contrato, competencia)
    avisos.consolidado_gerado(sessao, competencia)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Etapa 7 — ordem bancária
# ---------------------------------------------------------------------------------------------

def registrar_ordem_bancaria(sessao: Session, contrato_id, competencia_id, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa a OB, debita o valor autorizado nas NEs (em ordem) e conclui a competência."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "ordem_bancaria", "A ordem bancária")
    # Divide o valor a pagar entre as NEs na ordem escolhida; se faltar saldo, `_exigir_saldo` explica quanto
    notas = _resolver_notas(contrato, [n.nota_id for n in competencia.notas])
    debito = valor_a_pagar(competencia)
    lancamentos = movimentos_em_ordem(notas, debito)
    if lancamentos is None:
        _exigir_saldo(notas, debito)
    competencia.ob_anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-execucao-ob", autor.id, contrato_id=contrato.id)
    agora = agora_utc()
    # Um lançamento de pagamento no extrato de cada NE usada
    for nota, valor in lancamentos or []:
        nota.movimentos.append(
            MovimentoNotaEmpenho(competencia_id=competencia.id, tipo="pagamento", debito=valor, criado_por_id=autor.id, criado_em=agora)
        )
    competencia.ob_enviada_em = competencia.concluida_em = agora
    competencia.etapa_atual = "concluida"
    _auditar(sessao, autor, "contrato.execucao.ordem_bancaria", contrato, competencia, debito=debito,
             notas={n.numero: v for n, v in lancamentos or []})
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Reabertura (SuperRoot ou gestor do contrato)
# ---------------------------------------------------------------------------------------------

def _descartar_checklist(sessao: Session, competencia: Competencia) -> None:
    """Descarta a cópia do checklist (e os anexos dela); ela é copiada de novo do checklist ativo quando a etapa recomeçar."""
    competencia.documentos.clear()
    sessao.flush()


def _descartar_nota_fiscal(competencia: Competencia) -> None:
    """Remove as notas fiscais juntadas, o histórico de recusas e os dados de recebimento e de e-mail da etapa."""
    competencia.notas_fiscais.clear()
    competencia.despesas_variaveis.clear()
    competencia.recusas.clear()
    competencia.nf_recebida_em = competencia.prazo_pagamento_dias = competencia.origem_valor_nf = None
    competencia.email_nf_enviado_em = competencia.email_nf_ok = competencia.email_nf_erro = None
    competencia.email_nf_destinatarios = []


def _descartar_avaliacao(sessao: Session, competencia: Competencia) -> None:
    """Apaga a avaliação (notas, ciências, PDFs); ela é copiada de novo do formulário ativo quando a etapa recomeçar."""
    competencia.avaliacao = None
    sessao.flush()


def pode_reabrir(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """SuperRoot, controle total em Contratos, ou o gestor vigente do contrato (papel `gestor`) com permissão de edição."""
    if eh_administrador(sessao, usuario):
        return True
    return _papel_do_usuario(contrato, usuario) == "gestor" and pode_editar(sessao, contrato, usuario)


def reabrir(sessao: Session, contrato_id, competencia_id, dados: Reabertura, autor: Usuario) -> None:
    """Volta a competência para uma etapa anterior, desfazendo as conclusões posteriores.

    Reabrir a etapa X mantém X preenchida e DESCARTA as posteriores (começam vazias; a avaliação é refeita com o
    formulário ativo). Anexos e histórico são mantidos (auditoria). Se a competência já estava paga, cada débito
    da OB ganha um lançamento de **estorno** no extrato da NE (o pagamento original permanece registrado).
    """
    contrato = obter_contrato(sessao, contrato_id)
    if not pode_reabrir(sessao, contrato, autor):
        raise SemPermissaoContrato("Somente o SuperRoot ou o gestor do contrato podem reabrir etapas e estornar pagamentos.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    # Só é possível voltar para uma etapa anterior à atual
    etapas = etapas_da_competencia(competencia)
    if dados.etapa not in etapas or etapas.index(dados.etapa) >= etapas.index(competencia.etapa_atual):
        raise ErroRegraContrato("Escolha uma etapa anterior à etapa atual desta competência.")
    _reabrir_etapa(sessao, contrato, competencia, dados, autor)
    sessao.commit()


def zerar(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Zera a competência: todas as etapas voltam ao início, inclusive a medição (SuperRoot ou gestor).

    Estorna a OB se já paga, descarta avaliação, nota fiscal, retenção, CADIN, checklist e consolidado e apaga a medição
    (itens copiados, quantidades medidas, ciências, memórias, NEs escolhidas e e-mail). Anexos e
    histórico continuam guardados. Na medição adicional os itens são mantidos (só as quantidades voltam a zero), pois ela não os recopia.
    """
    contrato = obter_contrato(sessao, contrato_id)
    if not pode_reabrir(sessao, contrato, autor):
        raise SemPermissaoContrato("Somente o SuperRoot ou o gestor do contrato podem zerar a competência.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _reabrir_etapa(sessao, contrato, competencia, Reabertura(etapa="medicao", justificativa="Competência zerada"), autor)
    # Na regular os itens saem junto: a medição recomeça e copia o cadastro de novo no próximo acesso
    if competencia.tipo == "adicional":
        # A adicional não recopia o cadastro sozinha (`garantir_itens` só atende a regular): os itens ficam e só as quantidades voltam a zero
        for item in competencia.itens:
            item.quantidade_medida = ZERO
    else:
        competencia.itens.clear()
    competencia.notas.clear()
    competencia.memorias.clear()
    competencia.medicao_iniciada_em = None
    competencia.email_medicao_enviado_em = competencia.email_medicao_ok = competencia.email_medicao_erro = None
    competencia.email_medicao_destinatarios = []
    atualizar_executado(contrato)
    _auditar(sessao, autor, "contrato.execucao.zerar", contrato, competencia)
    sessao.commit()


def _reabrir_etapa(sessao: Session, contrato: Contrato, competencia: Competencia, dados: Reabertura, autor: Usuario) -> None:
    """Corpo da reabertura (sem validar a etapa nem gravar): usado por `reabrir` e `zerar`."""
    etapas = etapas_da_competencia(competencia)
    alvo = etapas.index(dados.etapa)

    def posterior(etapa: str) -> bool:
        """Etapa depois da escolhida. Retenção, CADIN e checklist são paralelos: reabrir um não descarta os outros."""
        if etapa not in etapas or etapas.index(etapa) <= alvo:
            return False
        return not (etapa in ETAPAS_PARALELAS and dados.etapa in ETAPAS_PARALELAS)

    # Competência paga: estorna no extrato de cada NE o valor líquido que ela debitou
    estornos = {}
    if competencia.etapa_atual == "concluida":
        agora = agora_utc()
        for nota in contrato.notas_empenho:
            liquido = sum((m.debito for m in nota.movimentos if m.competencia_id == competencia.id), ZERO)
            if liquido > 0:
                nota.movimentos.append(
                    MovimentoNotaEmpenho(
                        competencia_id=competencia.id, tipo="estorno", debito=-liquido, justificativa=dados.justificativa,
                        criado_por_id=autor.id, criado_em=agora,
                    )
                )
                estornos[nota.numero] = liquido
        competencia.concluida_em = competencia.ob_enviada_em = None
        competencia.ob_anexo_id = None
    # A etapa escolhida volta a ficar aberta mantendo o que foi preenchido; as POSTERIORES são descartadas e
    # começam vazias quando a competência chegar a elas (anexos antigos continuam guardados, sem vínculo)
    descartadas = [e for e in etapas if posterior(e)]
    if "consolidado" in descartadas or dados.etapa == "consolidado":
        competencia.consolidado_anexo_id, competencia.consolidado_em = None, None
    if "cadin" in descartadas:
        competencia.consultas_cadin.clear()
    if "cadin" in descartadas or dados.etapa == "cadin":
        competencia.cadin_concluido_em = None
    if "checklist" in descartadas:
        _descartar_checklist(sessao, competencia)
    if "checklist" in descartadas or dados.etapa == "checklist":
        competencia.checklist_concluido_em = None
    if "retencao" in descartadas or dados.etapa == "retencao":
        competencia.retencao_concluida_em, competencia.retencao_pdf_anexo_id = None, None
        competencia.retencao_por_id, competencia.retencao_por_nome, competencia.retencao_discriminacao_conferida = None, "", False
    if "retencao" in descartadas:
        competencia.email_retencao_enviado_em = competencia.email_retencao_ok = competencia.email_retencao_erro = None
        competencia.email_retencao_destinatarios = []
    if "nota_fiscal" in descartadas:
        _descartar_nota_fiscal(competencia)
    if "nota_fiscal" in descartadas or dados.etapa == "nota_fiscal":
        competencia.nf_concluida_em = None
    if "avaliacao" in descartadas:
        _descartar_avaliacao(sessao, competencia)
    elif dados.etapa == "avaliacao" and competencia.avaliacao:
        competencia.avaliacao.concluida_em, competencia.avaliacao.pdf_assinado_anexo_id = None, None
    # Reabrir a medição apaga as ciências e recalcula o executado dos itens
    if dados.etapa == "medicao":
        competencia.medicao_concluida_em = None
        competencia.ciencias.clear()
        # Sobras de desconto de reajuste ainda não usadas voltam para esta competência
        recolher_sobras(sessao, competencia)
        atualizar_executado(contrato)
    etapa_anterior = competencia.etapa_atual
    competencia.etapa_atual = dados.etapa
    _auditar(sessao, autor, "contrato.execucao.reabrir", contrato, competencia, de=etapa_anterior, para=dados.etapa,
             justificativa=dados.justificativa, estornos=estornos, descartadas=descartadas)
