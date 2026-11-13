"""
===============================================================================
ARQUIVO: diferenca_manual.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Tratar o cálculo manual da diferença retroativa do reajuste e da repactuação:
a escolha "manual ou automático", a diferença informada mês a mês e o que
acontece com ela na conclusão.

RESUMO TÉCNICO:

A memória retroativa começa com a pergunta "Cálculo manual ou automático?" (`modo_retroativo` do procedimento, gravado por
`escolher_modo`). No **automático** o sistema calcula a diferença pelas medições concluídas no SGI (como sempre fez). No
**manual** o sistema **não calcula nada sozinho** (decisão do usuário de 13/11/2026):

1. O sistema lista os meses da data de efeito **até o mês em andamento (inclusive)**, medidos ou não no SGI
   (`meses_sem_medicao`, nome mantido por compatibilidade).
2. O gestor informa a **diferença de cada mês** (pode ser negativa), a **justificativa** e o **PDF** da memória feita fora
   do sistema (`gravar`). O total é a soma dos meses. Enquanto o procedimento está em elaboração, pode trocar ou remover (`remover`).
3. Na conclusão (`aplicar_na_conclusao`):
   - os meses marcados ficam **travados no preço de antes** (os itens são copiados já com o preço antigo e não acompanham
     mais o cadastro) e saem do cálculo automático de qualquer procedimento;
   - total positivo vira uma **competência complementar** com uma linha por mês (fluxo normal: NE, NF, consolidado e OB);
   - valor negativo vira **crédito no fundo** do contrato, que o gestor aplica numa medição.

Em todo documento que cita o valor sai a observação de `DiferencaManual.texto_observacao` (quem informou, quando, meses e justificativa).

FINALIDADE DE NEGÓCIO:
Muitos meses foram pagos fora do SGI, ou o gestor prefere a memória feita
por fora. No cálculo manual vale só o que ele informa, mês a mês, sem o
sistema somar uma diferença automática por cima (caso do contrato 007/2024).

CONTEXTO NO SISTEMA:
Usado por servico_reajuste.py e servico_repactuacao.py (rotas
`…/modo-retroativo` e `…/diferenca-manual`); modelo DiferencaManual em
app/models/contratos/alteracoes.py; tela no componente app-diferenca-manual.

===============================================================================
"""

import uuid
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Competencia, Contrato, DiferencaManual, ItemMedicao, Reajuste, Repactuacao
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import DiferencaManualLeitura, MesSemMedicao
from app.schemas.contratos.execucao import LeituraArquivo
from app.services import servico_anexos
from app.services.contratos import calculos
from app.services.contratos.erros import ErroRegraContrato
from app.services.contratos.servico_competencias import _periodos_por_inicio, garantir_itens, itens_previstos, registrar_credito_reajuste
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist
from app.services.contratos import servico_contratos
from app.services.contratos.documentos_execucao import moeda
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, Aba, Coluna
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)

Procedimento = Reajuste | Repactuacao


def coberta(competencia: Competencia, exceto: DiferencaManual | None = None) -> bool:
    """O mês está coberto por alguma diferença manual (fora `exceto`)? Coberto = pago fora do sistema, travado e fora do cálculo automático."""
    return any(d is not exceto for d in competencia.diferencas_manuais)


def _da_vigencia(competencia: Competencia, procedimento: Procedimento) -> bool:
    """O reajuste vale para uma vigência só; a repactuação vale da data de efeito em diante, em qualquer vigência."""
    return not isinstance(procedimento, Reajuste) or competencia.sequencia_vigencia == procedimento.sequencia_vigencia


def candidatas(contrato: Contrato, procedimento: Procedimento) -> list[Competencia]:
    """Competências que podem entrar na diferença manual deste procedimento.

    Regulares, que terminam na data de efeito ou depois e que já começaram (da data de efeito até o mês em andamento, inclusive),
    medidas ou não no SGI: no cálculo manual o gestor informa a diferença de qualquer um desses meses. No reajuste, só da vigência
    dele e sem diferença de reajuste já acertada. Reajuste retroativo não tem (a vigência retroativa é lançada antes das medições)."""
    if isinstance(procedimento, Reajuste) and procedimento.retroativo:
        return []
    dia = servico_contratos.hoje()  # pelo módulo, para os testes poderem congelar a data
    return sorted(
        (
            c for c in contrato.competencias
            if c.tipo == "regular" and _da_vigencia(c, procedimento)
            # Da data de efeito até o mês em andamento (começou até hoje); meses futuros ficam de fora
            and c.periodo_fim >= procedimento.efeito and c.periodo_inicio <= dia
            and getattr(c, "diferenca_coberta_por_reajuste_id", None) is None
        ),
        key=lambda c: c.periodo_inicio,
    )


def _mes(competencia: Competencia, propria: DiferencaManual | None) -> MesSemMedicao:
    """Um mês no formato da tela: situação no SGI (medido? em andamento?) e o valor já informado nele, se houver."""
    dia = servico_contratos.hoje()
    valor = (propria.valores_meses or {}).get(str(competencia.id)) if propria is not None else None
    return MesSemMedicao(competencia_id=competencia.id, identificador=competencia.identificador, rotulo=competencia.numero_competencia,
                         periodo_inicio=competencia.periodo_inicio, periodo_fim=competencia.periodo_fim, coberta_por_outra=coberta(competencia, exceto=propria),
                         medida=competencia.medicao_concluida_em is not None, em_andamento=competencia.periodo_fim >= dia,
                         valor=Decimal(valor) if valor is not None else None)


def meses_sem_medicao(contrato: Contrato, procedimento: Procedimento) -> list[MesSemMedicao]:
    """Candidatas no formato da tela (só em elaboração e no cálculo manual: depois de concluído, a pergunta não se aplica)."""
    if procedimento.situacao != "rascunho" or getattr(procedimento, "modo_retroativo", None) != "manual":
        return []
    return [_mes(c, procedimento.diferenca_manual) for c in candidatas(contrato, procedimento)]


def leitura(contrato: Contrato, procedimento: Procedimento) -> DiferencaManualLeitura | None:
    """A diferença manual gravada, com a observação e a complementar gerada (se houver)."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return None
    anexo = manual.anexo
    complementar = next((c for c in contrato.competencias if c.diferenca_manual_id == manual.id), None)
    return DiferencaManualLeitura(
        valor=manual.valor, justificativa=manual.justificativa, meses=[_mes(c, manual) for c in manual.competencias],
        arquivo=LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em),
        informado_por=manual.informado_por_nome, informado_em=manual.informado_em, observacao=manual.texto_observacao,
        competencia_diferenca=complementar.identificador if complementar else None,
    )


MODOS = ("automatico", "manual")


def escolher_modo(sessao: Session, contrato: Contrato, procedimento: Procedimento, modo: str, autor: Usuario) -> None:
    """Grava a resposta de "Cálculo manual ou automático?". Trocar de modo apaga a diferença manual informada. Não faz commit.

    A memória gerada antes deixa de valer sozinha: o modo entra no hash da memória (`origem_hash`)."""
    if procedimento.situacao != "rascunho":
        raise ErroRegraContrato("O cálculo só pode ser escolhido com o procedimento em elaboração.")
    if modo not in MODOS:
        raise ErroRegraContrato("Escolha o cálculo manual ou automático.")
    if procedimento.modo_retroativo == modo:
        return
    anterior = procedimento.modo_retroativo
    # A diferença manual só existe no cálculo manual: ao trocar, sai (os meses destravam)
    if procedimento.diferenca_manual is not None:
        procedimento.diferenca_manual = None
        sessao.flush()
    procedimento.modo_retroativo, procedimento.modo_retroativo_em = modo, agora_utc()
    acao = "contrato.reajuste.modo_retroativo" if isinstance(procedimento, Reajuste) else "contrato.repactuacao.modo_retroativo"
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"campos": {"modo_retroativo": {"de": anterior, "para": modo}}})


def exigir_modo(procedimento: Procedimento) -> None:
    """A memória e a conclusão só andam depois da resposta de "Cálculo manual ou automático?".

    O reajuste retroativo não tem diferença a acertar (é lançado antes das medições): não precisa da pergunta."""
    if isinstance(procedimento, Reajuste) and procedimento.retroativo:
        return
    if procedimento.modo_retroativo not in MODOS:
        raise ErroRegraContrato("Escolha o cálculo manual ou automático na memória de cálculo.")


def exigir_pronto_para_concluir(procedimento: Procedimento, memoria_criada_em) -> None:
    """Na conclusão: modo escolhido, memória gerada depois da escolha e, no manual, a diferença mês a mês informada."""
    exigir_modo(procedimento)
    if procedimento.modo_retroativo_em is not None and memoria_criada_em is not None and memoria_criada_em < procedimento.modo_retroativo_em:
        raise ErroRegraContrato("Gere a memória de cálculo de novo: o cálculo (manual ou automático) mudou depois dela.")
    if manual(procedimento) and procedimento.diferenca_manual is None:
        raise ErroRegraContrato("Cálculo manual: informe a diferença mês a mês (ou escolha o cálculo automático) antes de concluir.")


def manual(procedimento: Procedimento) -> bool:
    """O procedimento está no cálculo manual? (nele, o sistema não calcula a diferença dos meses medidos)"""
    return getattr(procedimento, "modo_retroativo", None) == "manual"


def _travar_itens(contrato: Contrato, competencia: Competencia) -> None:
    """Copia agora os itens do mês ainda sem itens, no preço de antes (vale também para o mês em andamento).

    Sem isso, a medição futura copiaria o cadastro já com o preço novo. Mês já medido não é tocado (já tem os itens pagos)."""
    if competencia.itens or competencia.medicao_concluida_em is not None or competencia.tipo != "regular":
        return
    if garantir_itens(contrato, competencia):
        return
    # Mês em andamento (medição ainda não liberada): copia do mesmo jeito, com o período do calendário atual
    periodo = _periodos_por_inicio(contrato).get(competencia.periodo_inicio)
    if periodo is not None:
        competencia.itens = itens_previstos(contrato, periodo)
        competencia.versao_cadastro_sincronizada = contrato.versao_cadastro


def gravar(sessao: Session, contrato: Contrato, procedimento: Procedimento, competencias_ids: list[uuid.UUID], valores: list[Decimal], justificativa: str,
           arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Grava (ou substitui) a diferença manual do procedimento em elaboração: a diferença de cada mês. Não faz commit."""
    if procedimento.situacao != "rascunho":
        raise ErroRegraContrato("A diferença manual só pode ser informada com o procedimento em elaboração.")
    if not manual(procedimento):
        raise ErroRegraContrato("Escolha o cálculo manual para informar a diferença mês a mês.")
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise ErroRegraContrato("Informe a justificativa da diferença manual.")
    if not competencias_ids:
        raise ErroRegraContrato("Informe a diferença de ao menos um mês.")
    if len(valores) != len(competencias_ids):
        raise ErroRegraContrato("Informe um valor para cada mês.")
    # Mês repetido: vale o último valor enviado
    por_mes = {i: calculos.arredondar(v) for i, v in zip(competencias_ids, valores)}
    if any(v == 0 for v in por_mes.values()):
        raise ErroRegraContrato("A diferença de cada mês informado precisa ser diferente de zero (negativo é crédito da SPI).")
    valor = calculos.arredondar(sum(por_mes.values(), ZERO))
    if valor == 0:
        raise ErroRegraContrato("O total da diferença não pode ser zero.")
    por_id = {c.id: c for c in candidatas(contrato, procedimento)}
    fora = [i for i in por_mes if i not in por_id]
    if fora:
        raise ErroRegraContrato("Só podem ser informados meses da data de efeito até o mês atual.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-diferenca-manual", autor.id, contrato_id=contrato.id)
    sessao.flush()
    anterior = procedimento.diferenca_manual
    if anterior is not None:
        # Substitui: a anterior sai (os meses dela destravam) e o PDF antigo fica no histórico de anexos
        procedimento.diferenca_manual = None
        sessao.flush()
    meses = sorted((por_id[i] for i in por_mes), key=lambda c: c.periodo_inicio)
    # Os itens do mês são copiados agora, ainda no preço de antes (sem isso, a medição futura copiaria o cadastro com o preço novo)
    for competencia in meses:
        _travar_itens(contrato, competencia)
    nova = DiferencaManual(
        contrato_id=contrato.id, valor=valor, justificativa=justificativa, anexo_id=anexo.id,
        valores_meses={str(c.id): str(por_mes[c.id]) for c in meses},
        informado_por_id=autor.id, informado_por_nome=autor.nome_completo or autor.login, informado_em=agora_utc(),
    )
    nova.competencias = meses
    procedimento.diferenca_manual = nova
    sessao.flush()
    acao = "contrato.reajuste.diferenca_manual.gravar" if isinstance(procedimento, Reajuste) else "contrato.repactuacao.diferenca_manual.gravar"
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"valor": valor, "meses": nova.rotulos_meses, "valores_meses": {c.numero_competencia: str(por_mes[c.id]) for c in meses},
                   "justificativa": justificativa})


def remover(sessao: Session, contrato: Contrato, procedimento: Procedimento, autor: Usuario) -> None:
    """Remove a diferença manual do procedimento em elaboração (os meses destravam). Não faz commit."""
    if procedimento.situacao != "rascunho":
        raise ErroRegraContrato("A diferença manual só pode ser removida com o procedimento em elaboração.")
    if procedimento.diferenca_manual is None:
        raise ErroRegraContrato("Não há diferença manual informada.")
    procedimento.diferenca_manual = None
    sessao.flush()
    acao = "contrato.reajuste.diferenca_manual.remover" if isinstance(procedimento, Reajuste) else "contrato.repactuacao.diferenca_manual.remover"
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id, dados={})


def conferir_antes_de_concluir(contrato: Contrato, procedimento: Procedimento) -> None:
    """Os meses marcados continuam sem medição concluída? (alguém pode ter medido um deles depois de a diferença ser informada)."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return
    validas = {c.id for c in candidatas(contrato, procedimento)}
    medidas = [c.numero_competencia for c in manual.competencias if c.id not in validas]
    if medidas:
        raise ErroRegraContrato(f"Os meses {', '.join(medidas)} foram medidos no sistema depois de a diferença manual ser informada. "
                                "Revise a diferença manual antes de concluir.")


def aplicar_na_conclusao(sessao: Session, contrato: Contrato, procedimento: Procedimento) -> Competencia | None:
    """Lança a diferença manual na conclusão: complementar de uma linha (positiva) ou crédito no fundo (negativa).

    Os meses já estão travados desde a gravação (os itens foram copiados no preço de antes e `sincronizar_competencia` não os toca).
    Devolve a competência complementar criada, se houver."""
    manual = procedimento.diferenca_manual
    if manual is None or not manual.competencias:
        return None
    if manual.valor < 0:
        if isinstance(procedimento, Reajuste):
            registrar_credito_reajuste(sessao, contrato, procedimento, -manual.valor, diferenca_manual=manual)
        else:
            registrar_credito_reajuste(sessao, contrato, None, -manual.valor, repactuacao=procedimento, diferenca_manual=manual)
        return None
    meses = manual.competencias
    tipo = "diferenca_reajuste" if isinstance(procedimento, Reajuste) else "diferenca_repactuacao"
    # Duas complementares manuais no mesmo período e tipo ficam numeradas (a restrição única do banco inclui `numero_adicional`)
    numero = 1 + max((c.numero_adicional for c in contrato.competencias if c.tipo == tipo and c.periodo_inicio == meses[0].periodo_inicio), default=0)
    competencia = Competencia(
        tipo=tipo, competencia=procedimento.mes_referencia, numero_adicional=numero, diferenca_manual_id=manual.id,
        reajuste_id=procedimento.id if isinstance(procedimento, Reajuste) else None,
        repactuacao_id=procedimento.id if isinstance(procedimento, Repactuacao) else None,
        periodo_inicio=meses[0].periodo_inicio, periodo_fim=meses[-1].periodo_fim, sequencia_vigencia=meses[-1].sequencia_vigencia, etapa_atual="medicao",
    )
    origem = "reajuste" if isinstance(procedimento, Reajuste) else "repactuação"
    por_mes = valores_por_mes(manual)
    if por_mes and all(v > 0 for _, v in por_mes):
        # Uma linha por mês (sem item do contrato): quantidade 1 × a diferença informada naquele mês
        for ordem, (mes, valor) in enumerate(por_mes, start=1):
            competencia.itens.append(ItemMedicao(
                item_id=None, ordem=ordem, descricao=f"Diferença retroativa de {origem} de {mes.numero_competencia} informada manualmente",
                tipo="continuo", calcula_pro_rata=False, valor_unitario=valor, fator_meses=Decimal(1), quantidade_prevista=Decimal(1),
                quantidade_medida=Decimal(1),
            ))
    else:
        # Diferença antiga (só o total) ou meses com sinais diferentes: uma linha só com o total (o detalhe fica na memória)
        competencia.itens.append(ItemMedicao(
            item_id=None, ordem=1, descricao=f"Diferença retroativa de {origem} informada manualmente ({manual.texto_meses})", tipo="continuo",
            calcula_pro_rata=False, valor_unitario=manual.valor, fator_meses=Decimal(1), quantidade_prevista=Decimal(1), quantidade_medida=Decimal(1),
        ))
    checklist = checklist_ativo(contrato)
    if checklist:
        copiar_checklist(competencia, checklist)
    contrato.competencias.append(competencia)
    return competencia


# ---------------------------------------------------------------------------------------------
# Memória de cálculo (PDF e planilha) e textos
# ---------------------------------------------------------------------------------------------

def valores_por_mes(manual: DiferencaManual) -> list[tuple[Competencia, Decimal]]:
    """[(mês, diferença informada)] em ordem; vazio nas diferenças antigas, em que só o total foi informado."""
    valores = manual.valores_meses or {}
    if not valores:
        return []
    return [(c, Decimal(valores[str(c.id)])) for c in manual.competencias if str(c.id) in valores]


def _situacao_sgi(competencia: Competencia) -> str:
    """Situação do mês no SGI para a memória: medido, em andamento ou sem medição."""
    if competencia.medicao_concluida_em is not None:
        return "Medido no SGI"
    if competencia.periodo_fim >= servico_contratos.hoje():
        return "Em andamento"
    return "Sem medição no SGI"


def texto_destino(manual: DiferencaManual) -> str:
    """O que acontece com o valor na conclusão."""
    if manual.valor > 0:
        return f"{moeda(manual.valor)} a pagar em competência complementar (diferença informada manualmente)"
    return f"crédito de {moeda(-manual.valor)} da SPI, no fundo do contrato (o gestor aplica numa medição)"


def secao_pdf(documento: DocumentoPdf, procedimento: Procedimento) -> None:
    """Seção "Diferença informada manualmente" da memória em PDF: meses, valor, destino e a observação."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return
    secao = documento.nova_pagina().secao("Diferença retroativa informada manualmente (cálculo manual)")
    secao.campos([
        ("Meses", manual.texto_meses), ("Valor total informado", ("-" if manual.valor < 0 else "") + moeda(abs(manual.valor))),
        ("Destino", texto_destino(manual)), ("Memória anexada", manual.anexo.nome_original),
    ], colunas=1)
    por_mes = valores_por_mes(manual)
    if por_mes:
        documento.espaco(2)
        documento.tabela(["Mês", "Situação no SGI", "Diferença"],
                         [[c.numero_competencia, _situacao_sgi(c), ("-" if v < 0 else "") + moeda(abs(v))] for c, v in por_mes], larguras=[3, 4, 3])
    documento.espaco(2)
    documento.paragrafo("No cálculo manual o sistema não calcula a diferença dos meses medidos: vale só o valor informado acima.")
    documento.paragrafo(f"Observação: {manual.texto_observacao}")


def aba_planilha(contrato: Contrato, procedimento: Procedimento) -> Aba | None:
    """Aba "Diferença manual" da memória em planilha."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return None
    valores = dict((c.id, v) for c, v in valores_por_mes(manual))
    return Aba(
        "Diferença manual",
        [Coluna("Mês", largura=14), Coluna("Período", largura=26), Coluna("Situação no SGI", largura=20), Coluna("Diferença", formato=FORMATO_MOEDA, largura=16)],
        [[c.numero_competencia, f"{c.periodo_inicio:%d/%m/%Y} a {c.periodo_fim:%d/%m/%Y}", _situacao_sgi(c),
          float(valores[c.id]) if c.id in valores else None] for c in manual.competencias],
        titulo=f"Diferença retroativa informada manualmente — Contrato {contrato.numero}",
        rodape=["Valor informado", float(manual.valor)],
        observacoes=[f"Destino: {texto_destino(manual)}", f"Observação: {manual.texto_observacao}"],
    )


def origem_hash(procedimento: Procedimento) -> list:
    """O que da diferença manual entra no hash da memória (mudou, a memória precisa ser gerada de novo)."""
    manual = procedimento.diferenca_manual
    modo = getattr(procedimento, "modo_retroativo", None)
    if manual is None:
        return [modo, None]
    return [modo, str(manual.valor), manual.justificativa, str(manual.anexo_id), sorted(str(c.id) for c in manual.competencias),
            sorted((manual.valores_meses or {}).items())]
