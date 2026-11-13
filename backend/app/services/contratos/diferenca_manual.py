# Criado por José Eduardo Santana Martins
# Este arquivo serve para tratar a diferença retroativa informada manualmente no reajuste e na repactuação.
"""Diferença retroativa informada manualmente (reajuste e repactuação).

O cálculo automático da diferença retroativa só enxerga meses com **medição concluída** no SGI. Muitos contratos não têm
no sistema as medições de antes da implantação: esses meses foram pagos fora do SGI, no preço antigo. Para eles:

1. O sistema lista as competências **já encerradas**, a partir da data de efeito, **sem medição concluída**
   (`meses_sem_medicao`), e pergunta se o gestor quer informar a diferença à mão.
2. O gestor marca os meses pagos fora do sistema e informa o **valor total** da diferença deles (pode ser negativo),
   a **justificativa** e o **PDF** da memória feita fora do sistema (`gravar`). Enquanto o procedimento está em elaboração,
   pode trocar ou remover (`remover`).
3. Na conclusão (`aplicar_na_conclusao`):
   - os meses marcados ficam **travados no preço de antes** (os itens são copiados já com o preço antigo e não acompanham
     mais o cadastro) e saem do cálculo automático de qualquer procedimento;
   - valor positivo vira uma **competência complementar de uma linha** (fluxo normal: NE, NF, consolidado e OB);
   - valor negativo vira **crédito no fundo** do contrato, que o gestor aplica numa medição.

Em todo documento que cita o valor sai a observação de `DiferencaManual.texto_observacao` (quem informou, quando, meses e justificativa).
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
from app.services.contratos.servico_competencias import garantir_itens, registrar_credito_reajuste
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist
from app.services.contratos import servico_contratos
from app.services.contratos.documentos_execucao import moeda
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import Aba, Coluna
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

    Regulares, encerradas (período já terminou), que terminam na data de efeito ou depois, sem medição concluída no sistema
    (ou já cobertas pela diferença manual de outro procedimento: foram pagas fora do sistema e continuam sem a diferença deste).
    No reajuste, só da vigência dele e sem diferença de reajuste já acertada. Reajuste retroativo não tem (a vigência retroativa
    é lançada antes das medições)."""
    if isinstance(procedimento, Reajuste) and procedimento.retroativo:
        return []
    propria = procedimento.diferenca_manual
    dia = servico_contratos.hoje()  # pelo módulo, para os testes poderem congelar a data
    return sorted(
        (
            c for c in contrato.competencias
            if c.tipo == "regular" and _da_vigencia(c, procedimento)
            and c.periodo_fim >= procedimento.efeito and c.periodo_fim < dia
            and (c.medicao_concluida_em is None or coberta(c, exceto=propria))
            and getattr(c, "diferenca_coberta_por_reajuste_id", None) is None
        ),
        key=lambda c: c.periodo_inicio,
    )


def _mes(competencia: Competencia, propria: DiferencaManual | None) -> MesSemMedicao:
    return MesSemMedicao(competencia_id=competencia.id, identificador=competencia.identificador, rotulo=competencia.numero_competencia,
                         periodo_inicio=competencia.periodo_inicio, periodo_fim=competencia.periodo_fim, coberta_por_outra=coberta(competencia, exceto=propria))


def meses_sem_medicao(contrato: Contrato, procedimento: Procedimento) -> list[MesSemMedicao]:
    """Candidatas no formato da tela (só em elaboração: depois de concluído, a pergunta não se aplica)."""
    if procedimento.situacao != "rascunho":
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


def gravar(sessao: Session, contrato: Contrato, procedimento: Procedimento, valor: Decimal, competencias_ids: list[uuid.UUID], justificativa: str,
           arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Grava (ou substitui) a diferença manual do procedimento em elaboração. Não faz commit."""
    if procedimento.situacao != "rascunho":
        raise ErroRegraContrato("A diferença manual só pode ser informada com o procedimento em elaboração.")
    valor = calculos.arredondar(valor)
    if valor == 0:
        raise ErroRegraContrato("Informe o valor da diferença (diferente de zero; negativo é crédito da SPI).")
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise ErroRegraContrato("Informe a justificativa da diferença manual.")
    if not competencias_ids:
        raise ErroRegraContrato("Marque ao menos um mês pago fora do sistema.")
    por_id = {c.id: c for c in candidatas(contrato, procedimento)}
    fora = [i for i in competencias_ids if i not in por_id]
    if fora:
        raise ErroRegraContrato("Só podem ser marcados meses encerrados, a partir da data de efeito, sem medição concluída no sistema.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-diferenca-manual", autor.id, contrato_id=contrato.id)
    sessao.flush()
    anterior = procedimento.diferenca_manual
    if anterior is not None:
        # Substitui: a anterior sai (os meses dela destravam) e o PDF antigo fica no histórico de anexos
        procedimento.diferenca_manual = None
        sessao.flush()
    meses = sorted((por_id[i] for i in dict.fromkeys(competencias_ids)), key=lambda c: c.periodo_inicio)
    # Os itens do mês são copiados agora, ainda no preço de antes (sem isso, a medição futura copiaria o cadastro com o preço novo)
    for competencia in meses:
        garantir_itens(contrato, competencia)
    manual = DiferencaManual(
        contrato_id=contrato.id, valor=valor, justificativa=justificativa, anexo_id=anexo.id,
        informado_por_id=autor.id, informado_por_nome=autor.nome_completo or autor.login, informado_em=agora_utc(),
    )
    manual.competencias = meses
    procedimento.diferenca_manual = manual
    sessao.flush()
    acao = "contrato.reajuste.diferenca_manual.gravar" if isinstance(procedimento, Reajuste) else "contrato.repactuacao.diferenca_manual.gravar"
    auditar(sessao, autor.login, acao, f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"valor": valor, "meses": manual.rotulos_meses, "justificativa": justificativa})


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
    if manual is None:
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
    # Uma linha só, sem item do contrato: quantidade 1 × o valor informado
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
    secao = documento.nova_pagina().secao("Diferença retroativa informada manualmente (meses pagos fora do sistema)")
    secao.campos([
        ("Meses", manual.texto_meses), ("Valor informado", ("-" if manual.valor < 0 else "") + moeda(abs(manual.valor))),
        ("Destino", texto_destino(manual)), ("Memória anexada", manual.anexo.nome_original),
    ], colunas=1)
    documento.espaco(2)
    documento.paragrafo(f"Observação: {manual.texto_observacao}")


def aba_planilha(contrato: Contrato, procedimento: Procedimento) -> Aba | None:
    """Aba "Diferença manual" da memória em planilha."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return None
    return Aba(
        "Diferença manual",
        [Coluna("Mês", largura=14), Coluna("Período", largura=26)],
        [[c.numero_competencia, f"{c.periodo_inicio:%d/%m/%Y} a {c.periodo_fim:%d/%m/%Y}"] for c in manual.competencias],
        titulo=f"Diferença retroativa informada manualmente — Contrato {contrato.numero}",
        rodape=["Valor informado", float(manual.valor)],
        observacoes=[f"Destino: {texto_destino(manual)}", f"Observação: {manual.texto_observacao}"],
    )


def origem_hash(procedimento: Procedimento) -> list:
    """O que da diferença manual entra no hash da memória (mudou, a memória precisa ser gerada de novo)."""
    manual = procedimento.diferenca_manual
    if manual is None:
        return [None]
    return [str(manual.valor), manual.justificativa, str(manual.anexo_id), sorted(str(c.id) for c in manual.competencias)]
