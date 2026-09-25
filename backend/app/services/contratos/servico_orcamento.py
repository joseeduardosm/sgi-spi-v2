# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de previsão orçamentária e de Notas de Empenho.
"""Previsão orçamentária (mensal, por vigência) e Notas de Empenho.

- Previsão: quanto o contrato deve custar em cada mês. Itens contínuos entram sozinhos (com
  pró-rata 30/360 nos meses parciais); itens sob demanda entram pelos apontamentos da equipe.
- Notas de Empenho (NE): o orçamento reservado. As ordens bancárias debitam as NEs; o saldo é
  sempre calculado pelo extrato, nunca gravado.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.contratos import (
    ApontamentoPrevisao,
    Competencia,
    Contrato,
    NotaEmpenho,
    PrevisaoVigencia,
    SelecaoNotaEmpenho,
)
from app.models.usuario import Usuario
from app.schemas.contratos.orcamento import (
    GravacaoNotaEmpenho,
    GravacaoPrevisao,
    ItemMesPrevisao,
    ItemSobDemandaPrevisao,
    LeituraNotaEmpenho,
    LinhaRelatorioNotas,
    MesPrevisao,
    MovimentoNota,
    Previsao,
    VigenciaPrevisao,
)
from app.services.contratos import calculos, valores
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_MOEDA, FORMATO_QUANTIDADE, Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

# Atalho para Decimal(0), muito usado nas somas
ZERO = Decimal(0)


# ---------------------------------------------------------------------------------------------
# Previsão
# ---------------------------------------------------------------------------------------------

def apontamentos_da_vigencia(contrato: Contrato, sequencia: int) -> dict[tuple[uuid.UUID, date], Decimal]:
    """Apontamentos da vigência como dicionário {(item_id, mês): quantidade}."""
    previsao = valores.previsao_da_vigencia(contrato, sequencia)
    return {(a.item_id, a.competencia): a.quantidade for a in previsao.apontamentos} if previsao else {}


def meses_previstos(contrato: Contrato) -> list[MesPrevisao]:
    """Tabela mensal consolidada: contínuos em todos os meses (pró-rata 30/360), sob demanda pelos apontamentos."""
    meses: list[MesPrevisao] = []
    for vigencia in vigencias(contrato):
        apontados = apontamentos_da_vigencia(contrato, vigencia.sequencia)
        acumulado = ZERO
        for periodo in calculos.meses_da_vigencia(vigencia):
            itens: list[ItemMesPrevisao] = []
            base = ZERO
            # Preço vigente no mês (considera reajustes já aplicados)
            for item in contrato.itens:
                preco = valores.preco_em(contrato, item, periodo.competencia)
                # Contínuo: quantidade do mês (considera aditamentos/supressões) com pró-rata, se o item usar
                if item.tipo == "continuo":
                    quantidade = valores.quantidade_mensal_em(contrato, item, periodo.competencia)
                    fator = periodo.fator if item.calcula_pro_rata else Decimal(1)
                    # A base mensal ignora o pró-rata: é o valor de um mês cheio
                    base += quantidade * preco
                else:
                    # Sob demanda: só entra no mês se houver apontamento
                    quantidade = apontados.get((item.id, periodo.competencia), ZERO)
                    fator = Decimal(1)
                    if quantidade <= 0:
                        continue
                subtotal = calculos.arredondar(quantidade * preco * fator)
                itens.append(
                    ItemMesPrevisao(
                        item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo,
                        quantidade=quantidade, valor_unitario=preco, fator=fator, subtotal=subtotal,
                    )
                )
            valor = sum((i.subtotal for i in itens), ZERO)
            acumulado += valor
            meses.append(
                MesPrevisao(
                    competencia=periodo.competencia, sequencia_vigencia=vigencia.sequencia, inicio=periodo.inicio,
                    fim=periodo.fim, fator=periodo.fator, base_mensal=calculos.arredondar(base), valor=valor,
                    acumulado=acumulado, itens=itens,
                )
            )
    return meses


def montar_previsao(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> Previsao:
    """Monta a resposta do `GET /previsao`: grade por vigência e a tabela mensal consolidada."""
    contrato = obter_contrato(sessao, contrato_id)
    meses = meses_previstos(contrato)
    editor = pode_editar(sessao, contrato, usuario)
    # Nomes dos usuários para exibir quem selou cada previsão
    nomes = dict(sessao.execute(select(Usuario.id, func.coalesce(Usuario.nome_completo, Usuario.login))).all())
    sob_demanda = [i for i in contrato.itens if i.tipo == "sob_demanda"]
    lista = []
    for vigencia in vigencias(contrato):
        previsao = valores.previsao_da_vigencia(contrato, vigencia.sequencia)
        apontados = apontamentos_da_vigencia(contrato, vigencia.sequencia)
        competencias = [p.competencia for p in calculos.meses_da_vigencia(vigencia)]
        salva = bool(previsao and previsao.salva)
        itens = []
        for item in sob_demanda:
            limite = valores.limite_na_vigencia(contrato, item, vigencia.sequencia)
            por_mes = {c.isoformat(): apontados.get((item.id, c), ZERO) for c in competencias}
            itens.append(
                ItemSobDemandaPrevisao(
                    item_id=item.id, ordem=item.ordem, descricao=item.descricao, limite=limite,
                    apontamentos=por_mes, saldo=limite - sum(por_mes.values(), ZERO),
                )
            )
        lista.append(
            VigenciaPrevisao(
                sequencia=vigencia.sequencia, inicio=vigencia.inicio, fim=vigencia.fim, meses=competencias,
                possui_sob_demanda=bool(sob_demanda), salva=salva,
                salva_em=previsao.salva_em if previsao else None,
                salva_por_nome=nomes.get(previsao.salva_por_id) if previsao and previsao.salva_por_id else None,
                # Antes do selo, quem pode editar o contrato grava; depois, só o SuperRoot
                pode_editar=editor and (not salva or usuario.superusuario),
                itens_sob_demanda=itens,
                total_previsto=sum((m.valor for m in meses if m.sequencia_vigencia == vigencia.sequencia), ZERO),
            )
        )
    return Previsao(total_previsto=sum((m.valor for m in meses), ZERO), vigencias=lista, meses=meses)


def obter_ou_criar_previsao(contrato: Contrato, sequencia: int) -> PrevisaoVigencia:
    """Previsão da vigência; cria uma nova (não salva) se ainda não existir."""
    previsao = valores.previsao_da_vigencia(contrato, sequencia)
    if previsao is None:
        previsao = PrevisaoVigencia(sequencia_vigencia=sequencia)
        contrato.previsoes.append(previsao)
    return previsao


def salvar_previsao(sessao: Session, contrato_id: uuid.UUID, sequencia: int, dados: GravacaoPrevisao, autor: Usuario) -> None:
    """Grava a grade de apontamentos da vigência e sela a previsão."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    vigencia = next((v for v in vigencias(contrato) if v.sequencia == sequencia), None)
    if vigencia is None:
        raise RegistroNaoEncontrado("Vigência")
    previsao = obter_ou_criar_previsao(contrato, sequencia)
    if previsao.salva and not autor.superusuario:
        raise ErroRegraContrato("A previsão desta vigência já foi salva e está selada. Somente o SuperRoot pode alterá-la.")
    # Só itens sob demanda recebem apontamento, e só nos meses da vigência
    itens = {i.id: i for i in contrato.itens if i.tipo == "sob_demanda"}
    competencias = {p.competencia for p in calculos.meses_da_vigencia(vigencia)}
    grade: dict[tuple[uuid.UUID, date], Decimal] = {}
    # Normaliza para o dia 1 e valida item e mês de cada apontamento
    for apontamento in dados.apontamentos:
        mes = calculos.primeiro_dia(apontamento.competencia)
        if apontamento.item_id not in itens:
            raise ErroRegraContrato("Só itens sob demanda do contrato recebem apontamentos na previsão.")
        if mes not in competencias:
            raise ErroRegraContrato(f"O mês {mes:%m/%Y} não pertence à {sequencia}ª vigência.")
        grade[(apontamento.item_id, mes)] = apontamento.quantidade
    # Nenhum item pode ter mais apontado do que o limite da vigência
    for item in itens.values():
        limite = valores.limite_na_vigencia(contrato, item, sequencia)
        apontado = sum((q for (item_id, _), q in grade.items() if item_id == item.id), ZERO)
        if apontado > limite:
            raise ErroRegraContrato(
                f"O item \"{item.descricao}\" ficaria com saldo negativo ({limite - apontado:.4f}). Reduza os apontamentos."
            )
    # Guarda o "antes" para a auditoria e substitui a grade inteira
    anteriores = {(a.item_id, a.competencia): a.quantidade for a in previsao.apontamentos}
    previsao.apontamentos.clear()
    sessao.flush()
    # Quantidade zero não é gravada (célula vazia)
    for (item_id, mes), quantidade in grade.items():
        if quantidade > 0:
            previsao.apontamentos.append(ApontamentoPrevisao(item_id=item_id, competencia=mes, quantidade=quantidade))
    # Sela a previsão; a ação auditada diferencia a primeira gravação da edição de uma selada
    era_salva = previsao.salva
    previsao.salva, previsao.salva_em, previsao.salva_por_id = True, agora_utc(), autor.id
    auditar(
        sessao, autor.login, "contrato.previsao.editar_selada" if era_salva else "contrato.previsao.salvar",
        f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
        dados={"vigencia": sequencia, "antes": {f"{k[0]}|{k[1]}": v for k, v in anteriores.items()},
               "depois": {f"{k[0]}|{k[1]}": v for k, v in grade.items() if v > 0}},
    )
    sessao.commit()


def planilha_previsao(sessao: Session, contrato_id: uuid.UUID, sequencia: int) -> tuple[bytes, str]:
    """Gera a planilha da previsão de uma vigência: aba mensal e aba de itens por competência."""
    contrato = obter_contrato(sessao, contrato_id)
    if not any(v.sequencia == sequencia for v in vigencias(contrato)):
        raise RegistroNaoEncontrado("Vigência")
    meses = [m for m in meses_previstos(contrato) if m.sequencia_vigencia == sequencia]
    linhas_mes = [[f"{m.competencia:%m/%Y}", f"{m.inicio:%d/%m} a {m.fim:%d/%m}", m.base_mensal, m.valor, m.acumulado] for m in meses]
    linhas_itens = [
        [f"{m.competencia:%m/%Y}", i.descricao, "Contínuo" if i.tipo == "continuo" else "Sob demanda", i.quantidade, i.valor_unitario, float(i.fator), i.subtotal]
        for m in meses
        for i in m.itens
    ]
    total = sum((m.valor for m in meses), ZERO)
    conteudo = gerar_planilha(
        [
            Aba(
                "Previsão mensal",
                [Coluna("Competência", largura=13), Coluna("Período faturado", largura=18), Coluna("Base mensal", FORMATO_MOEDA),
                 Coluna("Valor da competência", FORMATO_MOEDA, 20), Coluna("Acumulado", FORMATO_MOEDA, 18)],
                linhas_mes,
                titulo=f"Previsão orçamentária — Contrato {contrato.numero} — {sequencia}ª vigência",
                rodape=["Total", "", "", total, ""],
            ),
            Aba(
                "Itens por competência",
                [Coluna("Competência", largura=13), Coluna("Item", largura=40), Coluna("Tipo", largura=14),
                 Coluna("Quantidade", FORMATO_QUANTIDADE), Coluna("Valor unitário", FORMATO_MOEDA),
                 Coluna("Fator (pró-rata)", "0.0000"), Coluna("Subtotal", FORMATO_MOEDA)],
                linhas_itens,
            ),
        ]
    )
    return conteudo, f"previsao-{contrato.sequencial:03d}-{contrato.ano}-vigencia-{sequencia}.xlsx"


def previsao_salva_em_todas(contrato: Contrato) -> bool:
    """Pré-requisito da execução: cada vigência com item sob demanda precisa de previsão salva."""
    if not any(i.tipo == "sob_demanda" for i in contrato.itens):
        return True
    # Todas as vigências precisam ter previsão salva (o `:=` guarda a previsão para testar `salva`)
    return all((p := valores.previsao_da_vigencia(contrato, v.sequencia)) and p.salva for v in vigencias(contrato))


# ---------------------------------------------------------------------------------------------
# Notas de Empenho
# ---------------------------------------------------------------------------------------------

def carregar_notas(sessao: Session, contrato_id: uuid.UUID) -> list[NotaEmpenho]:
    """NEs do contrato com o extrato já carregado, em ordem de cadastro."""
    return list(
        sessao.scalars(
            select(NotaEmpenho)
            .where(NotaEmpenho.contrato_id == contrato_id)
            .options(selectinload(NotaEmpenho.movimentos))
            .order_by(NotaEmpenho.criado_em)
        )
    )


def faixa_consumo(percentual: Decimal) -> str:
    """Cor do cartão da NE: verde até 50% consumido, amarelo até 75%, vermelho acima."""
    return "verde" if percentual <= 50 else "amarelo" if percentual <= 75 else "vermelho"


def leitura_nota(sessao: Session, nota: NotaEmpenho, comprometido: Decimal = ZERO) -> LeituraNotaEmpenho:
    """Monta a NE com o extrato (saldo após cada lançamento) e as faixas de consumo."""
    # Competências e autores dos lançamentos, buscados em lote para o extrato
    ids = [m.competencia_id for m in nota.movimentos]
    competencias = {c.id: c for c in sessao.scalars(select(Competencia).where(Competencia.id.in_(ids)))} if ids else {}
    autores = dict(
        sessao.execute(
            select(Usuario.id, func.coalesce(Usuario.nome_completo, Usuario.login)).where(
                Usuario.id.in_([m.criado_por_id for m in nota.movimentos if m.criado_por_id])
            )
        ).all()
    )
    # Quantas competências escolheram esta NE (se alguma, ela não pode ser excluída)
    vinculada = sessao.scalar(select(func.count()).where(SelecaoNotaEmpenho.nota_id == nota.id)) or 0
    # Percorre o extrato em ordem, calculando o saldo depois de cada lançamento
    saldo = nota.valor_original
    movimentos = []
    for movimento in nota.movimentos:
        saldo -= movimento.debito
        movimentos.append(
            MovimentoNota(
                id=movimento.id, data=movimento.criado_em, tipo=movimento.tipo,
                competencia=competencias[movimento.competencia_id].competencia if movimento.competencia_id in competencias else None,
                competencia_rotulo=competencias[movimento.competencia_id].numero_competencia if movimento.competencia_id in competencias else None,
                competencia_id=movimento.competencia_id, debito=movimento.debito, saldo_apos=saldo,
                justificativa=movimento.justificativa or "", autor=autores.get(movimento.criado_por_id),
            )
        )
    # Percentual consumido (protege contra divisão por zero)
    percentual = calculos.arredondar(nota.consumido * 100 / nota.valor_original) if nota.valor_original else ZERO
    return LeituraNotaEmpenho(
        id=nota.id, numero=nota.numero, valor_original=nota.valor_original, consumido=nota.consumido, saldo=nota.saldo,
        comprometido=comprometido, saldo_livre=nota.saldo - comprometido,
        percentual_consumido=percentual, faixa=faixa_consumo(percentual), vinculada=bool(vinculada or nota.movimentos),
        movimentos=movimentos, criado_em=nota.criado_em,
    )


def listar_notas(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraNotaEmpenho]:
    """NEs do contrato, com o valor comprometido por medições ainda não pagas."""
    from app.services.contratos.servico_competencias import compromissos  # import tardio: evita ciclo

    contrato = obter_contrato(sessao, contrato_id)
    reservado = compromissos(contrato)
    return [leitura_nota(sessao, n, reservado.get(n.id, ZERO)) for n in carregar_notas(sessao, contrato_id)]


def _numero_em_uso(sessao: Session, contrato_id: uuid.UUID, numero: str, nota_id: uuid.UUID | None) -> bool:
    """Indica se o número de NE já existe em outra nota do mesmo contrato."""
    existente = sessao.scalar(
        select(NotaEmpenho.id).where(NotaEmpenho.contrato_id == contrato_id, func.lower(NotaEmpenho.numero) == numero.lower())
    )
    return existente is not None and existente != nota_id


def criar_nota(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoNotaEmpenho, autor: Usuario) -> None:
    """Cadastra uma NE (número único no contrato)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if _numero_em_uso(sessao, contrato.id, dados.numero, None):
        raise ErroRegraContrato("Já existe uma Nota de Empenho com este número no contrato.", conflito=True)
    sessao.add(NotaEmpenho(contrato_id=contrato.id, numero=dados.numero, valor_original=dados.valor_original, criado_por_id=autor.id))
    auditar(sessao, autor.login, "contrato.nota_empenho.criar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados=dados.model_dump())
    sessao.commit()


def _obter_nota(sessao: Session, contrato_id: uuid.UUID, nota_id: uuid.UUID) -> NotaEmpenho:
    """NE pelo id, desde que pertença ao contrato."""
    nota = sessao.get(NotaEmpenho, nota_id)
    if nota is None or nota.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Nota de Empenho")
    return nota


def alterar_nota(sessao: Session, contrato_id: uuid.UUID, nota_id: uuid.UUID, dados: GravacaoNotaEmpenho, autor: Usuario) -> None:
    """Altera número e valor da NE; o valor não pode ficar abaixo do já consumido."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    nota = _obter_nota(sessao, contrato_id, nota_id)
    if _numero_em_uso(sessao, contrato.id, dados.numero, nota.id):
        raise ErroRegraContrato("Já existe uma Nota de Empenho com este número no contrato.", conflito=True)
    if dados.valor_original < nota.consumido:
        raise ErroRegraContrato(f"O valor não pode ficar abaixo do já consumido (R$ {nota.consumido:.2f}).")
    antes = {"numero": nota.numero, "valor_original": nota.valor_original}
    nota.numero, nota.valor_original = dados.numero, dados.valor_original
    auditar(sessao, autor.login, "contrato.nota_empenho.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"antes": antes, "depois": dados.model_dump()})
    sessao.commit()


def excluir_nota(sessao: Session, contrato_id: uuid.UUID, nota_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui a NE, desde que nunca tenha sido escolhida nem debitada."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    nota = _obter_nota(sessao, contrato_id, nota_id)
    ligada = sessao.scalar(select(func.count()).where(SelecaoNotaEmpenho.nota_id == nota.id))
    if ligada or nota.movimentos:
        raise ErroRegraContrato("A Nota de Empenho está ligada a uma competência ou tem débitos e não pode ser excluída.")
    auditar(sessao, autor.login, "contrato.nota_empenho.excluir", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"numero": nota.numero, "valor_original": nota.valor_original})
    sessao.delete(nota)
    sessao.commit()


def relatorio_notas(sessao: Session) -> list[LinhaRelatorioNotas]:
    """Todas as NEs de todos os contratos (Relatório Executivo de Notas de Empenho)."""
    notas = sessao.scalars(
        select(NotaEmpenho)
        .join(Contrato, Contrato.id == NotaEmpenho.contrato_id)
        .options(selectinload(NotaEmpenho.movimentos), selectinload(NotaEmpenho.contrato).selectinload(Contrato.empresa))
        .order_by(Contrato.ano.desc(), Contrato.sequencial.desc(), NotaEmpenho.numero)
    )
    return [
        LinhaRelatorioNotas(
            contrato=n.contrato.numero, empresa=n.contrato.empresa.razao_social, nota=n.numero,
            valor_original=n.valor_original, consumido=n.consumido, saldo=n.saldo,
        )
        for n in notas
    ]


def arquivo_relatorio_notas(sessao: Session, formato: str, autor: Usuario) -> tuple[bytes, str, str]:
    """Gera o relatório de NEs em XLSX ou PDF; devolve (conteúdo, nome do arquivo, tipo MIME)."""
    # Totais das três colunas de valores
    linhas = relatorio_notas(sessao)
    totais = [sum((getattr(l, c) for l in linhas), ZERO) for c in ("valor_original", "consumido", "saldo")]
    if formato == "xlsx":
        conteudo = gerar_planilha([
            Aba(
                "Notas de Empenho",
                [Coluna("Contrato", largura=12), Coluna("Empresa", largura=40), Coluna("NE", largura=18),
                 Coluna("Valor inicial", FORMATO_MOEDA, 18), Coluna("Consumido", FORMATO_MOEDA, 18), Coluna("Saldo", FORMATO_MOEDA, 18)],
                [[l.contrato, l.empresa, l.nota, l.valor_original, l.consumido, l.saldo] for l in linhas],
                titulo="Relatório Executivo de Notas de Empenho",
                rodape=["Total", "", "", *totais],
            )
        ])
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return conteudo, "relatorio-notas-empenho.xlsx", tipo
    # Qualquer outro formato: PDF em paisagem (a tabela é larga)
    documento = DocumentoPdf("Relatório Executivo de Notas de Empenho", f"{len(linhas)} nota(s) de empenho", paisagem=True,
                             autor=autor.nome_completo or autor.login)
    documento.tabela(
        ["Contrato", "Empresa", "NE", "Valor inicial", "Consumido", "Saldo"],
        [[l.contrato, l.empresa, l.nota, moeda(l.valor_original), moeda(l.consumido), moeda(l.saldo)] for l in linhas],
        larguras=[1, 4, 2, 1.6, 1.6, 1.6], alinhar_direita=[3, 4, 5],
        rodape=["Total", "", "", *[moeda(t) for t in totais]],
    )
    return documento.gerar(), "relatorio-notas-empenho.pdf", "application/pdf"


def moeda(valor: Decimal) -> str:
    """R$ no formato brasileiro, para documentos gerados."""
    # Formata no padrão americano e troca os separadores: 1,234.50 → 1.234,50
    texto = f"{calculos.arredondar(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def saldo_notas(notas: list[NotaEmpenho]) -> Decimal:
    """Soma dos saldos de uma lista de NEs."""
    return sum((n.saldo for n in notas), ZERO)


def movimentos_em_ordem(notas: list[NotaEmpenho], debito: Decimal) -> list[tuple[NotaEmpenho, Decimal]] | None:
    """Distribui o débito pelas NEs na ordem escolhida (esgota a 1ª antes da 2ª). Nulo se faltar saldo."""
    # Tira de cada NE, na ordem, o que ela puder cobrir até zerar o débito
    restante = debito
    lancamentos = []
    for nota in notas:
        if restante <= 0:
            break
        parcela = min(nota.saldo, restante)
        if parcela > 0:
            lancamentos.append((nota, parcela))
            restante -= parcela
    return None if restante > 0 else lancamentos


def notas_por_contrato(sessao: Session) -> dict[uuid.UUID, list[NotaEmpenho]]:
    """Todas as NEs agrupadas por contrato: {contrato_id: [notas]} (usado pelo painel)."""
    agrupadas: dict[uuid.UUID, list[NotaEmpenho]] = defaultdict(list)
    for nota in sessao.scalars(select(NotaEmpenho).options(selectinload(NotaEmpenho.movimentos))):
        agrupadas[nota.contrato_id].append(nota)
    return agrupadas

