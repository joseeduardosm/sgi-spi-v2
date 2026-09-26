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
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import (
    ETAPAS,
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
from app.models.contratos.execucao import ETAPAS_PARALELAS
from app.models.usuario import Usuario
from app.schemas.contratos.execucao import (
    ConferenciaNota,
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
    LeituraConsultaCadin,
    LeituraDocumentoMensal,
    LeituraItemMedicao,
    LeituraMemoria,
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
from app.services.contratos import calculos, documentos_execucao, leitor_nota_xml, servico_diario, servico_retencao, valores
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist, formulario_ativo
from app.services.contratos.servico_contratos import (
    designacoes_vigentes,
    exigir_edicao,
    hoje,
    integra_equipe,
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
            selectinload(Competencia.ciencias),
            selectinload(Competencia.memorias).selectinload(MemoriaMedicao.anexo),
            selectinload(Competencia.consultas_cadin),
            selectinload(Competencia.documentos),
            selectinload(Competencia.avaliacao),
        )
    )
    if competencia is None:
        raise RegistroNaoEncontrado("Competência")
    return competencia


def etapas_da_competencia(competencia: Competencia) -> list[str]:
    """Etapas desta competência em ordem (sem "avaliacao" quando não há formulário)."""
    return [e for e in ETAPAS if e != "avaliacao" or competencia.avaliacao is not None]


def proxima_etapa(competencia: Competencia, etapa: str) -> str:
    """Etapa seguinte a `etapa` nesta competência."""
    etapas = etapas_da_competencia(competencia)
    return etapas[etapas.index(etapa) + 1]


def total_medido(competencia: Competencia) -> Decimal:
    """Total medido: soma de quantidade medida × preço de cada item, arredondado."""
    return calculos.arredondar(sum((i.quantidade_medida * i.valor_unitario for i in competencia.itens), ZERO))


def valor_a_pagar(competencia: Competencia) -> Decimal:
    """Valor que a Ordem Bancária debita nas NEs apontadas.

    Com a nota fiscal concluída: NF principal + NF adicional (valores brutos). Antes disso, a estimativa é
    o valor autorizado da medição (medido × % liberado pela avaliação).
    """
    if competencia.nf_concluida_em is not None and competencia.nf_valor_bruto is not None:
        return calculos.arredondar(competencia.nf_valor_bruto + (competencia.nf_adicional_valor_bruto or ZERO))
    return calculos.arredondar(total_medido(competencia) * percentual_liberado(competencia) / CEM)


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
    if hoje() <= competencia.periodo_fim:
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


def _exigir_liberada(competencia: Competencia) -> None:
    """Só libera a medição depois do fim do período (não se mede um mês que ainda não acabou)."""
    if hoje() <= competencia.periodo_fim:
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


def _auditar(sessao: Session, autor: Usuario, acao: str, contrato: Contrato, competencia: Competencia, **dados) -> None:
    """Registra a operação na auditoria, identificando contrato e competência."""
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"competencia": competencia.competencia, **dados})


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


def itens_previstos(contrato: Contrato, periodo: calculos.PeriodoExecucao) -> list[ItemMedicao]:
    """Fotografia dos itens na competência: preço vigente e quantidade prevista (pró-rata por item)."""
    apontados = apontamentos_da_vigencia(contrato, periodo.sequencia_vigencia)
    itens = []
    for item in contrato.itens:
        preco = valores.preco_em(contrato, item, periodo.competencia)
        # Contínuo: soma mês a mês, pois quantidade e pró-rata podem variar dentro do período
        if item.tipo == "continuo":
            quantidade, fator = ZERO, ZERO
            for mes in periodo.meses:
                q, f = calculos.quantidade_prevista_continua(
                    valores.quantidade_mensal_em(contrato, item, mes.competencia), item.calcula_pro_rata, [mes]
                )
                quantidade, fator = quantidade + q, fator + f
        else:
            # Sob demanda: soma dos apontamentos da previsão nos meses do período
            quantidade = sum((apontados.get((item.id, m.competencia), ZERO) for m in periodo.meses), ZERO)
            fator = Decimal(len(periodo.meses))
        itens.append(
            ItemMedicao(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo,
                calcula_pro_rata=item.calcula_pro_rata, valor_unitario=preco, fator_meses=fator,
                quantidade_prevista=quantidade.quantize(QUATRO_CASAS), quantidade_medida=ZERO,
            )
        )
    return itens


def gerar_competencias(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> int:
    """Cria as competências que faltam (idempotente). Depois disso, itens e ordem ficam bloqueados."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    situacao = requisitos(contrato)
    if not situacao.prontos:
        raise ErroRegraContrato("Complete a base do contrato: " + " ".join(situacao.pendencias))
    checklist = checklist_ativo(contrato)
    formulario = formulario_ativo(contrato)
    # Períodos já cobertos. Competências migradas do SGI seguem o aniversário do contrato (ex.: 15/01 a
    # 14/02): um período civil que se sobrepõe a qualquer uma delas não é gerado de novo.
    existentes = [(c.periodo_inicio, c.periodo_fim) for c in contrato.competencias if c.tipo == "regular"]
    geradas = 0
    for periodo in calculos.periodos_de_execucao(vigencias(contrato), contrato.periodicidade_meses):
        if any(inicio <= periodo.fim and periodo.inicio <= fim for inicio, fim in existentes):
            continue
        # Cada competência nova recebe a fotografia dos itens, a cópia do checklist e, se houver, do formulário
        competencia = Competencia(
            competencia=periodo.competencia, periodo_inicio=periodo.inicio, periodo_fim=periodo.fim,
            sequencia_vigencia=periodo.sequencia_vigencia, etapa_atual="medicao",
        )
        competencia.itens = itens_previstos(contrato, periodo)
        copiar_checklist(competencia, checklist)
        if formulario:
            competencia.avaliacao = AvaliacaoCompetencia(formulario_id=formulario.id, definicao=formulario.definicao)
        contrato.competencias.append(competencia)
        geradas += 1
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
                competencias=[resumo(c) for c in sorted(competencias, key=lambda c: c.periodo_inicio)],
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
        possui_avaliacao=competencia.avaliacao is not None,
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

def _nota_fiscal(contrato: Contrato, competencia: Competencia, adicional: bool) -> LeituraNotaFiscal | None:
    """Dados da nota fiscal principal ou da adicional (os campos têm o mesmo nome com prefixos diferentes)."""
    # Mesmo código para as duas notas: só muda o prefixo dos campos (nf_ ou nf_adicional_)
    prefixo = "nf_adicional_" if adicional else "nf_"
    anexo = competencia.nf_adicional_anexo if adicional else competencia.nf_anexo
    xml = competencia.nf_adicional_xml_anexo if adicional else competencia.nf_xml_anexo
    dados_xml = getattr(competencia, f"{prefixo}dados_xml")
    bruto = getattr(competencia, f"{prefixo}valor_bruto")
    if anexo is None and bruto is None:
        return None
    # Valor líquido = bruto − retenções (nunca negativo)
    retencoes = {r: getattr(competencia, f"{prefixo}retencao_{r}") or ZERO for r in ("ir", "inss", "iss", "pis", "cofins", "csll")}
    esperado = None if adicional else servico_retencao.valor_autorizado(competencia)
    return LeituraNotaFiscal(
        numero=getattr(competencia, f"{prefixo}numero"), arquivo=_arquivo(anexo), xml=_arquivo(xml), dados_xml=dados_xml,
        conferencias=[ConferenciaNota(**c.__dict__) for c in servico_retencao.conferencias(contrato, competencia, dados_xml, esperado)],
        valor_bruto=bruto,
        **{f"retencao_{r}": v for r, v in retencoes.items()},
        valor_liquido=max(ZERO, (bruto or ZERO) - sum(retencoes.values(), ZERO)),
    )


def detalhar(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, usuario: Usuario) -> DetalheCompetencia:
    """Detalhe completo da competência (resposta de quase todas as rotas da execução)."""
    contrato = obter_contrato(sessao, contrato_id)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    # Todos os anexos da competência em uma consulta: {id: anexo}
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(_ids_anexos(competencia))))}
    selecionadas = [n.nota_id for n in competencia.notas]
    notas = {n.id: n for n in contrato.notas_empenho}
    # Saldo reservado por OUTRAS competências (esta fica de fora, pois é a que está sendo editada)
    reservado = compromissos(contrato, exceto=competencia.id)

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
    vencimento = (
        competencia.nf_recebida_em + timedelta(days=competencia.prazo_pagamento_dias)
        if competencia.nf_recebida_em and competencia.prazo_pagamento_dias
        else None
    )
    return DetalheCompetencia(
        **resumo(competencia).model_dump(),
        contrato_id=contrato.id, contrato_numero=contrato.numero, etapas=etapas_da_competencia(competencia),
        pode_editar=pode_editar(sessao, contrato, usuario), integra_equipe=integra_equipe(contrato, usuario),
        pode_gerar_consolidado_novamente=pode_gerar_consolidado_novamente(contrato, usuario) and pode_editar(sessao, contrato, usuario),
        liberada=hoje() > competencia.periodo_fim,
        itens=[
            LeituraItemMedicao(
                id=i.id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo, calcula_pro_rata=i.calcula_pro_rata,
                valor_unitario=i.valor_unitario, fator_meses=i.fator_meses, quantidade_prevista=i.quantidade_prevista,
                quantidade_medida=i.quantidade_medida, subtotal=calculos.arredondar(i.quantidade_medida * i.valor_unitario),
                saldo=saldos[i.id].saldo, glosas=saldos[i.id].glosas, saldo_liquido=saldos[i.id].saldo_liquido,
            )
            for i in competencia.itens
        ],
        total_previsto=calculos.arredondar(sum((i.quantidade_prevista * i.valor_unitario for i in competencia.itens), ZERO)),
        total_medido=medido,
        notas_selecionadas=[opcao_nota(notas[n]) for n in selecionadas if n in notas],
        notas_disponiveis=[opcao_nota(n) for n in contrato.notas_empenho if n.saldo - reservado.get(n.id, ZERO) > 0],
        ciencias=[LeituraCiencia(usuario_id=c.usuario_id, nome=c.nome, papel=c.papel, registrada_em=c.registrada_em) for c in competencia.ciencias],
        ciencias_minimas=CIENCIAS_MINIMAS,
        memorias=[LeituraMemoria(versao=m.versao, criada_em=m.criado_em, arquivo=_arquivo(m.anexo)) for m in competencia.memorias],
        medicao_concluida_em=competencia.medicao_concluida_em,
        avaliacao=_leitura_avaliacao(competencia.avaliacao, anexos) if competencia.avaliacao else None,
        percentual_autorizado=percentual,
        valor_autorizado=calculos.arredondar(medido * percentual / CEM),
        valor_a_pagar=valor_a_pagar(competencia),
        avisos=excedentes_da_medicao(contrato, competencia) if competencia.medicao_concluida_em is None else [],
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
        etapas_abertas=etapas_abertas(competencia),
        etapas_concluidas=etapas_concluidas(competencia),
        email_medicao=EmailMedicao(
            enviado_em=competencia.email_medicao_enviado_em, ok=competencia.email_medicao_ok,
            destinatarios=competencia.email_medicao_destinatarios or [], erro=competencia.email_medicao_erro,
        ),
        nota_fiscal=_nota_fiscal(contrato, competencia, False),
        nota_fiscal_adicional=_nota_fiscal(contrato, competencia, True),
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
            LeituraDocumentoMensal(id=d.id, ordem=d.ordem, nome=d.nome, observacao=d.observacao, obrigatorio=d.obrigatorio, arquivo=_arquivo(anexos.get(d.anexo_id)))
            for d in competencia.documentos
        ],
        consolidado=_arquivo(competencia.consolidado_anexo),
        ordem_bancaria=_arquivo(competencia.ob_anexo),
        concluida_em=competencia.concluida_em,
    )


def _ids_anexos(competencia: Competencia) -> set[uuid.UUID]:
    """Todos os anexos da competência (usados no detalhe e para autorizar downloads)."""
    ids = {competencia.nf_anexo_id, competencia.nf_adicional_anexo_id, competencia.consolidado_anexo_id, competencia.ob_anexo_id,
           competencia.nf_xml_anexo_id, competencia.nf_adicional_xml_anexo_id, competencia.retencao_pdf_anexo_id}
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
    glosas = servico_diario.glosas_do_periodo(contrato, competencia.periodo_inicio, competencia.periodo_fim) if regular else {}
    resultado = {}
    for linha in competencia.itens:
        item = itens.get(linha.item_id)
        if not regular:
            saldo = linha.quantidade_medida
        elif item is not None and item.tipo == "sob_demanda":
            limite = valores.limite_na_vigencia(contrato, item, competencia.sequencia_vigencia)
            executado = valores.executado_na_vigencia(contrato, item, competencia.sequencia_vigencia, exceto=competencia.id)
            saldo = max(ZERO, limite - executado)
        else:
            saldo = linha.quantidade_prevista
        glosa = glosas.get(linha.item_id, ZERO)
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
                f"\"{linha.descricao}\": a medição ({linha.quantidade_medida:.4f}) passa do saldo líquido "
                f"({saldo.saldo_liquido:.4f} = {conta}).{dica}"
            )
    return avisos


def salvar_medicao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: GravacaoMedicao, autor: Usuario) -> None:
    """Etapa 1: grava as quantidades medidas e as NEs escolhidas (em ordem de consumo)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
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
    _exigir_liberada(competencia)
    _exigir_etapa(competencia, "medicao", "A medição")
    if competencia.medicao_iniciada_em is None:
        raise ErroRegraContrato("Salve a medição antes de registrar a ciência.")
    papel = _papel_do_usuario(contrato, autor)
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
        "itens": [[i.ordem, i.descricao, str(i.valor_unitario), str(i.quantidade_prevista), str(i.quantidade_medida)] for i in competencia.itens],
        "ciencias": [[c.usuario_id, c.nome, c.papel] for c in competencia.ciencias],
        "notas": [str(n.nota_id) for n in competencia.notas],
    }
    # `sort_keys` garante o mesmo texto (e o mesmo hash) para os mesmos dados
    return hashlib.sha256(json.dumps(origem, sort_keys=True).encode()).hexdigest()


def concluir_medicao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, notas_ids: list[uuid.UUID], autor: Usuario) -> None:
    """Etapa 1: conclui a medição, gera a memória de cálculo e avança para a próxima etapa."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_liberada(competencia)
    _exigir_etapa(competencia, "medicao", "A medição")
    # Regras para concluir: ciências mínimas, mesma seleção de NEs salva, saldo e limite dos itens sob demanda
    if len({c.usuario_id for c in competencia.ciencias}) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato("A conclusão exige ao menos uma ciência de integrante da equipe.")
    if [n.nota_id for n in competencia.notas] != notas_ids:
        raise ErroRegraContrato("As Notas de Empenho foram alteradas na tela. Salve a medição novamente antes de concluir.")
    notas = _resolver_notas(contrato, notas_ids)
    _exigir_saldo(notas, valor_a_pagar(competencia), compromissos(contrato, exceto=competencia.id))
    # De novo na conclusão: uma glosa pode ter sido registrada depois de a medição ser salva
    excedentes = excedentes_da_medicao(contrato, competencia)
    if excedentes:
        raise ErroRegraContrato(" ".join(excedentes))
    # Gera o PDF, marca a conclusão, avança a etapa e atualiza o executado dos itens do contrato
    gerar_memoria(sessao, contrato, competencia, autor)
    competencia.medicao_concluida_em = agora_utc()
    competencia.etapa_atual = proxima_etapa(competencia, "medicao")
    atualizar_executado(contrato)
    _auditar(sessao, autor, "contrato.execucao.medicao.concluir", contrato, competencia, total=total_medido(competencia))
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
    nome = f"memoria-medicao-{contrato.sequencial:03d}-{contrato.ano}-{competencia.competencia:%Y-%m}-v{versao}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, nome, "contrato-execucao-memoria", autor.id, contrato_id=contrato.id)
    memoria = MemoriaMedicao(versao=versao, anexo=anexo, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc())
    competencia.memorias.append(memoria)
    return memoria


def atualizar_executado(contrato: Contrato) -> None:
    """Quantidade executada de cada item = soma das medições concluídas (todas as vigências)."""
    for item in contrato.itens:
        item.quantidade_executada = sum(
            (
                linha.quantidade_medida
                for c in contrato.competencias
                if c.medicao_concluida_em is not None and c.tipo == "regular"
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


def _validar_respostas(definicao: dict, respostas: list[RespostaAvaliacao], exigir_justificativa: str) -> list[dict]:
    """Confere as respostas e as devolve no formato gravado em JSON.

    Exige nota para todos os itens, só valores da escala e justificativa quando a nota é abaixo da máxima.
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


def _leitura_avaliacao(avaliacao: AvaliacaoCompetencia, anexos: dict) -> LeituraAvaliacao:
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
    if exigir_equipe and _papel_do_usuario(contrato, autor) is None:
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
    avaliacao.respostas_iniciais = _validar_respostas(avaliacao.definicao, dados.respostas, "Justifique a nota do item")
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
    avaliacao.respostas_gestor = _validar_respostas(avaliacao.definicao, dados.respostas, "Complemente a nota do item")
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
    papel = _papel_do_usuario(contrato, autor)
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
    nome = f"avaliacao-{contrato.sequencial:03d}-{contrato.ano}-{competencia.competencia:%Y-%m}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, nome, "contrato-execucao-avaliacao", autor.id, contrato_id=contrato.id)
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
        select(Competencia).where(
            Competencia.id != competencia.id, (Competencia.nf_chave == chave) | (Competencia.nf_adicional_chave == chave)
        )
    )
    if outra is not None:
        raise ErroRegraContrato(
            f"A nota fiscal {qual} (chave {chave}) já foi juntada à competência {outra.numero_competencia} do contrato {outra.contrato.numero}."
        )


def registrar_nota_fiscal(
    sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, dados: dict, arquivo: tuple | None, xml: tuple | None,
    arquivo_adicional: tuple | None, xml_adicional: tuple | None, autor: Usuario,
) -> None:
    """Etapa 3: junta a NF (PDF + XML obrigatórios) e, opcionalmente, a NF adicional; os valores vêm do XML.

    `dados`: recebida_em, prazo_pagamento_dias e possui_adicional. As retenções lidas do XML ficam como sugestão
    para a etapa de retenção de tributos, onde o Financeiro confere e confirma.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "nota_fiscal", "A nota fiscal")
    # PDF e XML são obrigatórios (na correção depois de reabrir, os arquivos anteriores podem ser mantidos)
    if arquivo is None and competencia.nf_anexo_id is None:
        raise ErroRegraContrato("Selecione a nota fiscal em PDF.")
    if xml is None and competencia.nf_xml_anexo_id is None:
        raise ErroRegraContrato("Selecione o XML da nota fiscal.")
    principal = _ler_xml(xml) if xml else (None, competencia.nf_dados_xml)
    _exigir_nota_inedita(sessao, competencia, principal[1].get("chave"), "principal")
    adicional = None
    if dados.get("possui_adicional"):
        if arquivo_adicional is None and competencia.nf_adicional_anexo_id is None:
            raise ErroRegraContrato("Selecione o PDF da nota fiscal adicional.")
        if xml_adicional is None and competencia.nf_adicional_xml_anexo_id is None:
            raise ErroRegraContrato("Selecione o XML da nota fiscal adicional.")
        adicional = _ler_xml(xml_adicional) if xml_adicional else (None, competencia.nf_adicional_dados_xml)
        if adicional[1].get("chave") and adicional[1].get("chave") == principal[1].get("chave"):
            raise ErroRegraContrato("A nota fiscal adicional é a mesma da principal.")
        _exigir_nota_inedita(sessao, competencia, adicional[1].get("chave"), "adicional")
    # As duas notas são pagas pelas NEs apontadas na medição: o saldo livre delas precisa cobrir o total
    bruto = Decimal(principal[1]["valor_bruto"])
    bruto_adicional = Decimal(adicional[1]["valor_bruto"]) if adicional else ZERO
    notas = _resolver_notas(contrato, [n.nota_id for n in competencia.notas])
    _exigir_saldo(notas, calculos.arredondar(bruto + bruto_adicional), compromissos(contrato, exceto=competencia.id))

    categoria_xml = "contrato-execucao-nf-xml"
    if arquivo:
        competencia.nf_anexo = servico_anexos.guardar_pdf(sessao, arquivo[0], arquivo[1], "contrato-execucao-nf", autor.id, contrato_id=contrato.id)
    if xml:
        competencia.nf_xml_anexo = servico_anexos.guardar_arquivo_gerado(
            sessao, principal[0], xml[1] or "nota_fiscal.xml", "application/xml", categoria_xml, autor.id, contrato_id=contrato.id)
    _aplicar_nota(competencia, "nf_", principal[1])
    if adicional:
        if arquivo_adicional:
            competencia.nf_adicional_anexo = servico_anexos.guardar_pdf(
                sessao, arquivo_adicional[0], arquivo_adicional[1], "contrato-execucao-nf-adicional", autor.id, contrato_id=contrato.id)
        if xml_adicional:
            competencia.nf_adicional_xml_anexo = servico_anexos.guardar_arquivo_gerado(
                sessao, adicional[0], xml_adicional[1] or "nota_fiscal_adicional.xml", "application/xml", categoria_xml, autor.id,
                contrato_id=contrato.id)
        _aplicar_nota(competencia, "nf_adicional_", adicional[1])
    else:
        # Sem nota adicional nesta gravação: limpa uma adicional registrada antes (ex.: após reabertura)
        competencia.nf_adicional_numero, competencia.nf_adicional_valor_bruto = "", None
        competencia.nf_adicional_dados_xml, competencia.nf_adicional_chave = None, None
        competencia.nf_adicional_anexo_id = competencia.nf_adicional_xml_anexo_id = None
    competencia.nf_recebida_em, competencia.prazo_pagamento_dias = dados["recebida_em"], dados["prazo_pagamento_dias"]
    competencia.origem_valor_nf = None
    competencia.nf_concluida_em = agora_utc()
    # Uma NF nova (ou corrigida) exige nova conferência de tributos
    competencia.retencao_concluida_em, competencia.retencao_pdf_anexo_id = None, None
    competencia.retencao_por_id, competencia.retencao_por_nome, competencia.retencao_discriminacao_conferida = None, "", False
    competencia.etapa_atual = proxima_etapa(competencia, "nota_fiscal")
    _auditar(sessao, autor, "contrato.execucao.nota_fiscal.concluir", contrato, competencia, numero=competencia.nf_numero, bruto=bruto,
             chave=competencia.nf_chave)
    sessao.commit()


def _aplicar_nota(competencia: Competencia, prefixo: str, dados: dict) -> None:
    """Grava número, chave, bruto e dados do XML; as retenções do XML ficam como sugestão para a conferência."""
    setattr(competencia, f"{prefixo}numero", (dados.get("numero") or "")[:100])
    setattr(competencia, f"{prefixo}chave", dados.get("chave"))
    setattr(competencia, f"{prefixo}valor_bruto", Decimal(dados["valor_bruto"]))
    setattr(competencia, f"{prefixo}dados_xml", dados)
    for tributo, valor in (dados.get("retencoes") or {}).items():
        setattr(competencia, f"{prefixo}retencao_{tributo}", Decimal(valor or "0"))


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

def enviar_documento_mensal(sessao: Session, contrato_id, competencia_id, documento_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Etapa 5: anexa o PDF de um documento do checklist mensal."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    _exigir_etapa(competencia, "checklist", "O checklist")
    documento = next((d for d in competencia.documentos if d.id == documento_id), None)
    if documento is None:
        raise RegistroNaoEncontrado("Documento do checklist")
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-execucao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    sessao.flush()
    # Com todos os documentos anexados (obrigatórios e opcionais), a etapa conclui sozinha
    if all(d.anexo_id for d in competencia.documentos):
        concluir_etapa_paralela(competencia, "checklist")
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
    _auditar(sessao, autor, "contrato.execucao.checklist.concluir", contrato, competencia,
             opcionais_sem_anexo=[d.nome for d in competencia.documentos if not d.anexo_id])
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Etapa 6 — documento consolidado
# ---------------------------------------------------------------------------------------------

def pode_gerar_consolidado_novamente(contrato: Contrato, usuario: Usuario) -> bool:
    """Gerar o consolidado **novamente** (já existe um) é só do gestor titular vigente ou do SuperRoot."""
    return usuario.superusuario or _papel_do_usuario(contrato, usuario) == "gestor"


def gerar_consolidado(sessao: Session, contrato_id, competencia_id, autor: Usuario) -> None:
    """Etapa 6: gera o PDF consolidado (todos os documentos da competência, na ordem de execução).

    A primeira geração é de quem pode editar o contrato. Gerar novamente (substituir um
    consolidado existente) é só do gestor do contrato ou do SuperRoot, inclusive depois da OB.
    """
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if competencia.consolidado_anexo_id is not None and not pode_gerar_consolidado_novamente(contrato, autor):
        raise SemPermissaoContrato("Somente o gestor do contrato ou o SuperRoot podem gerar novamente o documento consolidado.")
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
    conteudo = documentos_execucao.consolidado(contrato, competencia, detalhe, anexos, _nome(autor), enviados_por)
    nome = f"consolidado-{contrato.sequencial:03d}-{contrato.ano}-{competencia.competencia:%Y-%m}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, nome, "contrato-execucao-consolidado", autor.id, contrato_id=contrato.id)
    competencia.consolidado_anexo, competencia.consolidado_em = anexo, agora_utc()
    if competencia.etapa_atual == "consolidado":
        competencia.etapa_atual = "ordem_bancaria"
    _auditar(sessao, autor, "contrato.execucao.consolidado", contrato, competencia)
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

def pode_reabrir(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """SuperRoot, ou o gestor vigente do contrato (papel `gestor`) com permissão de edição."""
    if usuario.superusuario:
        return True
    return _papel_do_usuario(contrato, usuario) == "gestor" and pode_editar(sessao, contrato, usuario)


def reabrir(sessao: Session, contrato_id, competencia_id, dados: Reabertura, autor: Usuario) -> None:
    """Volta a competência para uma etapa anterior, desfazendo as conclusões posteriores.

    Anexos e histórico são mantidos (auditoria). Se a competência já estava paga, cada débito da OB
    ganha um lançamento de **estorno** no extrato da NE (o pagamento original permanece registrado).
    """
    contrato = obter_contrato(sessao, contrato_id)
    if not pode_reabrir(sessao, contrato, autor):
        raise SemPermissaoContrato("Somente o SuperRoot ou o gestor do contrato podem reabrir etapas e estornar pagamentos.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    # Só é possível voltar para uma etapa anterior à atual
    etapas = etapas_da_competencia(competencia)
    if dados.etapa not in etapas or etapas.index(dados.etapa) >= etapas.index(competencia.etapa_atual):
        raise ErroRegraContrato("Escolha uma etapa anterior à etapa atual desta competência.")
    alvo = etapas.index(dados.etapa)

    def reaberta(etapa: str) -> bool:
        """Indica se a etapa volta a ficar aberta (é a etapa escolhida ou uma posterior a ela)."""
        return etapa in etapas and etapas.index(etapa) >= alvo

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
    # Desfaz as conclusões das etapas reabertas (anexos continuam guardados)
    if reaberta("consolidado"):
        competencia.consolidado_anexo_id, competencia.consolidado_em = None, None
    if reaberta("cadin"):
        competencia.cadin_concluido_em = None
    if reaberta("checklist"):
        competencia.checklist_concluido_em = None
    if reaberta("retencao"):
        competencia.retencao_concluida_em, competencia.retencao_pdf_anexo_id = None, None
        competencia.retencao_por_id, competencia.retencao_por_nome, competencia.retencao_discriminacao_conferida = None, "", False
    if reaberta("nota_fiscal"):
        competencia.nf_concluida_em = None
    if reaberta("avaliacao") and competencia.avaliacao:
        competencia.avaliacao.concluida_em, competencia.avaliacao.pdf_assinado_anexo_id = None, None
    # Reabrir a medição apaga as ciências e recalcula o executado dos itens
    if reaberta("medicao"):
        competencia.medicao_concluida_em = None
        competencia.ciencias.clear()
        atualizar_executado(contrato)
    etapa_anterior = competencia.etapa_atual
    competencia.etapa_atual = dados.etapa
    _auditar(sessao, autor, "contrato.execucao.reabrir", contrato, competencia, de=etapa_anterior, para=dados.etapa,
             justificativa=dados.justificativa, estornos=estornos)
    sessao.commit()
