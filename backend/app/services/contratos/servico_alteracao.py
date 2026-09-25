# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de aditamento e supressão de quantidades.
"""Aditamento e supressão de quantidades (tela 7).

Abas em sequência: 1 justificativa técnica → 2 quantitativos (impacto em R$ e %) → 3 memória e
ciências (mínimo de 2 pessoas) → 4 formalização (De Acordo da contratada, consolidado, termo) e
conclusão, que aplica as novas quantidades. Uma alteração em andamento por vez.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import AlteracaoQuantidade, CienciaAlteracao, Contrato, ItemAlteracao, LimitePrevisao
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    AberturaAlteracao,
    GravacaoQuantitativos,
    ItemAlteracaoLeitura,
    LeituraAlteracao,
    PainelAlteracao,
    VigenciaDisponivel,
)
from app.schemas.contratos.execucao import LeituraArquivo, LeituraCiencia
from app.services import servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import PAPEIS, data_hora, moeda, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_competencias import CIENCIAS_MINIMAS
from app.services.contratos.servico_contratos import designacoes_vigentes, exigir_edicao, integra_equipe, obter_contrato, pode_editar, vigencias
from app.services.contratos.servico_orcamento import obter_ou_criar_previsao
from app.services.documentos.pdf import DocumentoPdf, mesclar_pdfs
from app.services.documentos.planilha import FORMATO_MOEDA, FORMATO_QUANTIDADE, Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
# Acima de 25% acumulado na vigência, a lei exige autorização do Ordenador de Despesa
LIMITE_SEM_AUTORIZACAO = Decimal(25)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Documentos aceitos: tipo → (coluna onde o id do anexo é gravado, categoria do anexo)
DOCUMENTOS = {
    "justificativa": ("justificativa_anexo_id", "contrato-alteracao-justificativa"),
    "autorizacao": ("autorizacao_anexo_id", "contrato-alteracao-autorizacao"),
    "de_acordo": ("de_acordo_anexo_id", "contrato-alteracao-de-acordo"),
    "termo": ("termo_anexo_id", "contrato-alteracao-termo"),
}


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    """Converte um anexo no formato de leitura da API (ou None)."""
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _carregar(sessao: Session, contrato: Contrato) -> list[AlteracaoQuantidade]:
    """Alterações do contrato com itens e ciências carregados, da mais antiga para a mais recente."""
    return list(
        sessao.scalars(
            select(AlteracaoQuantidade)
            .where(AlteracaoQuantidade.contrato_id == contrato.id)
            .options(selectinload(AlteracaoQuantidade.itens), selectinload(AlteracaoQuantidade.ciencias))
            .order_by(AlteracaoQuantidade.criado_em)
        )
    )


def _vigencia(contrato: Contrato, alteracao: AlteracaoQuantidade) -> calculos.Vigencia:
    """Vigência a que a alteração se refere."""
    return next(v for v in vigencias(contrato) if v.sequencia == alteracao.sequencia_vigencia)


def _acumulado(contrato: Contrato, alteracoes: list[AlteracaoQuantidade], alteracao: AlteracaoQuantidade) -> Decimal:
    """Percentual acumulado do mesmo tipo na vigência: as concluídas anteriores + esta."""
    anteriores = sum(
        (abs(a.impacto_percentual) for a in alteracoes
         if a.situacao == "concluida" and a.tipo == alteracao.tipo and a.sequencia_vigencia == alteracao.sequencia_vigencia and a.id != alteracao.id),
        ZERO,
    )
    return anteriores + abs(alteracao.impacto_percentual)


def acumulados_da_vigencia_atual(contrato: Contrato) -> tuple[Decimal, Decimal]:
    """(% aditado, % suprimido) acumulados na vigência atual, para a aba Principal."""
    atual = vigencias(contrato)[-1].sequencia
    concluidas = [a for a in contrato.alteracoes if a.situacao == "concluida" and a.sequencia_vigencia == atual]
    return (
        sum((abs(a.impacto_percentual) for a in concluidas if a.tipo == "aditamento"), ZERO),
        sum((abs(a.impacto_percentual) for a in concluidas if a.tipo == "supressao"), ZERO),
    )


def fator_restante(vigencia: calculos.Vigencia, desde: date, calcula_pro_rata: bool = True) -> Decimal:
    """Meses da vigência a partir do mês de efeito; com pró-rata, cada mês parcial conta pela fração 30/360."""
    return sum(((m.fator if calcula_pro_rata else Decimal(1)) for m in calculos.meses_da_vigencia(vigencia) if m.competencia >= desde), ZERO)


def leitura(sessao: Session, contrato: Contrato, alteracao: AlteracaoQuantidade, alteracoes: list[AlteracaoQuantidade]) -> LeituraAlteracao:
    """Converte a alteração para o formato de leitura, com o acumulado e o alerta dos 25%."""
    # Anexos da alteração em uma consulta
    ids = [getattr(alteracao, c) for c in ("justificativa_anexo_id", "autorizacao_anexo_id", "de_acordo_anexo_id", "termo_anexo_id",
                                           "memoria_pdf_anexo_id", "memoria_xlsx_anexo_id", "consolidado_anexo_id")]
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_([i for i in ids if i])))}
    acumulado = _acumulado(contrato, alteracoes, alteracao)
    return LeituraAlteracao(
        id=alteracao.id, tipo=alteracao.tipo, situacao=alteracao.situacao, sequencia_vigencia=alteracao.sequencia_vigencia,
        vigencia_inicio=alteracao.vigencia_inicio, vigencia_fim=alteracao.vigencia_fim, mes_efeito=alteracao.mes_efeito,
        meses_restantes=fator_restante(_vigencia(contrato, alteracao), alteracao.mes_efeito) if alteracao.situacao != "cancelada" else ZERO,
        itens=[
            ItemAlteracaoLeitura(
                item_id=i.item_id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo, valor_unitario=i.valor_unitario,
                quantidade_original=i.quantidade_original, quantidade_executada=i.quantidade_executada, quantidade_nova=i.quantidade_nova,
                impacto_valor=i.impacto_valor, abaixo_do_executado=i.tipo == "sob_demanda" and i.quantidade_nova < i.quantidade_executada,
            )
            for i in alteracao.itens
        ],
        valor_global_original=alteracao.valor_global_original, impacto_valor=alteracao.impacto_valor,
        impacto_percentual=alteracao.impacto_percentual, acumulado_percentual=acumulado, exige_autorizacao=acumulado > LIMITE_SEM_AUTORIZACAO,
        justificativa=_arquivo(anexos.get(alteracao.justificativa_anexo_id)), autorizacao=_arquivo(anexos.get(alteracao.autorizacao_anexo_id)),
        de_acordo=_arquivo(anexos.get(alteracao.de_acordo_anexo_id)), termo=_arquivo(anexos.get(alteracao.termo_anexo_id)),
        memoria_pdf=_arquivo(anexos.get(alteracao.memoria_pdf_anexo_id)), memoria_xlsx=_arquivo(anexos.get(alteracao.memoria_xlsx_anexo_id)),
        consolidado=_arquivo(anexos.get(alteracao.consolidado_anexo_id)),
        ciencias=[LeituraCiencia(usuario_id=c.usuario_id, nome=c.nome, papel=c.papel, registrada_em=c.registrada_em) for c in alteracao.ciencias],
        ciencias_minimas=CIENCIAS_MINIMAS, concluida_em=alteracao.concluida_em, cancelada_em=alteracao.cancelada_em,
    )


def painel(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> PainelAlteracao:
    """Alteração em andamento (se houver), vigências e histórico."""
    contrato = obter_contrato(sessao, contrato_id)
    alteracoes = _carregar(sessao, contrato)
    andamento = next((a for a in alteracoes if a.situacao in ("rascunho", "aguardando_ciencias")), None)
    return PainelAlteracao(
        em_andamento=leitura(sessao, contrato, andamento, alteracoes) if andamento else None,
        vigencias=[VigenciaDisponivel(sequencia=v.sequencia, inicio=v.inicio, fim=v.fim) for v in vigencias(contrato)],
        historico=[leitura(sessao, contrato, a, alteracoes) for a in alteracoes if a is not andamento],
        pode_editar=pode_editar(sessao, contrato, usuario), integra_equipe=integra_equipe(contrato, usuario),
    )


def _em_andamento(sessao: Session, contrato: Contrato, alteracao_id: uuid.UUID) -> tuple[AlteracaoQuantidade, list]:
    """(alteração, todas as alterações), exigindo que a pedida ainda esteja em andamento."""
    alteracoes = _carregar(sessao, contrato)
    alteracao = next((a for a in alteracoes if a.id == alteracao_id), None)
    if alteracao is None:
        raise RegistroNaoEncontrado("Alteração")
    if alteracao.situacao not in ("rascunho", "aguardando_ciencias"):
        raise ErroRegraContrato("Esta alteração não está mais em andamento.")
    return alteracao, alteracoes


def abrir(sessao: Session, contrato_id: uuid.UUID, dados: AberturaAlteracao, autor: Usuario) -> None:
    """Inicia um aditamento ou uma supressão, fotografando os itens na data de efeito."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if any(a.situacao in ("rascunho", "aguardando_ciencias") for a in _carregar(sessao, contrato)):
        raise ErroRegraContrato("Já existe um aditamento ou supressão em andamento.", conflito=True)
    vigencia = next((v for v in vigencias(contrato) if v.sequencia == dados.sequencia_vigencia), None)
    if vigencia is None:
        raise RegistroNaoEncontrado("Vigência")
    # O mês de efeito é normalizado para o dia 1 e precisa estar dentro da vigência
    efeito = calculos.primeiro_dia(dados.mes_efeito)
    if not calculos.primeiro_dia(vigencia.inicio) <= efeito <= vigencia.fim:
        raise ErroRegraContrato("O mês de efeito precisa estar dentro da vigência escolhida.")
    # Guarda o valor global da vigência antes da alteração (base do percentual)
    alteracao = AlteracaoQuantidade(
        contrato_id=contrato.id, tipo=dados.tipo, sequencia_vigencia=vigencia.sequencia, vigencia_inicio=vigencia.inicio, vigencia_fim=vigencia.fim,
        mes_efeito=efeito, valor_global_original=valores.valor_global_vigencia(contrato, vigencia), criado_por_id=autor.id,
    )
    # Quantidade de referência: mensal (contínuo) ou limite da vigência (sob demanda)
    for item in contrato.itens:
        atual = (valores.quantidade_mensal_em(contrato, item, efeito) if item.tipo == "continuo"
                 else valores.limite_na_vigencia(contrato, item, vigencia.sequencia))
        alteracao.itens.append(
            ItemAlteracao(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, tipo=item.tipo, valor_unitario=valores.preco_em(contrato, item, efeito),
                quantidade_original=atual, quantidade_nova=atual, quantidade_executada=valores.executado_na_vigencia(contrato, item, vigencia.sequencia),
            )
        )
    sessao.add(alteracao)
    auditar(sessao, autor.login, f"contrato.{dados.tipo}.abrir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"vigencia": vigencia.sequencia, "mes_efeito": efeito})
    sessao.commit()


def anexar(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, tipo_documento: str, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa justificativa técnica, autorização do Ordenador, De Acordo da contratada ou termo aditivo."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, _ = _em_andamento(sessao, contrato, alteracao_id)
    if tipo_documento not in DOCUMENTOS:
        raise RegistroNaoEncontrado("Tipo de documento")
    # De Acordo e Termo só depois das ciências mínimas
    if tipo_documento in ("de_acordo", "termo") and len(alteracao.ciencias) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato("A formalização é liberada depois das ciências mínimas.")
    coluna, categoria = DOCUMENTOS[tipo_documento]
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, categoria, autor.id, contrato_id=contrato.id)
    sessao.flush()
    setattr(alteracao, coluna, anexo.id)
    # Um novo De Acordo invalida o consolidado gerado antes
    if tipo_documento == "de_acordo":
        alteracao.consolidado_anexo_id = None
    auditar(sessao, autor.login, f"contrato.{alteracao.tipo}.documento", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": tipo_documento})
    sessao.commit()


def salvar_quantitativos(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, dados: GravacaoQuantitativos, autor: Usuario) -> None:
    """Calcula o impacto e envia para ciência. Reenviar apaga as ciências anteriores."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, _ = _em_andamento(sessao, contrato, alteracao_id)
    if alteracao.justificativa_anexo_id is None:
        raise ErroRegraContrato("Anexe a justificativa técnica assinada antes de informar os quantitativos.")
    # Cada linha da alteração, por item
    linhas = {i.item_id: i for i in alteracao.itens}
    if {i.item_id for i in dados.itens} - set(linhas):
        raise ErroRegraContrato("Um dos itens não pertence a esta alteração.")
    vigencia = _vigencia(contrato, alteracao)
    itens_contrato = {i.id: i for i in contrato.itens}
    # Meses afetados: do mês de efeito até o fim da vigência
    meses_efeito = [m for m in calculos.meses_da_vigencia(vigencia) if m.competencia >= alteracao.mes_efeito]
    for entrada in dados.itens:
        linha = linhas[entrada.item_id]
        nova = entrada.quantidade_nova
        # Aditamento só aumenta, supressão só diminui, e a supressão não fica abaixo do já executado
        if alteracao.tipo == "aditamento" and nova < linha.quantidade_original:
            raise ErroRegraContrato(f"No aditamento, a nova quantidade de \"{linha.descricao}\" não pode ser menor que a atual.")
        if alteracao.tipo == "supressao" and nova > linha.quantidade_original:
            raise ErroRegraContrato(f"Na supressão, a nova quantidade de \"{linha.descricao}\" não pode ser maior que a atual.")
        if alteracao.tipo == "supressao" and linha.tipo == "sob_demanda" and nova < linha.quantidade_executada:
            raise ErroRegraContrato(f"A nova quantidade de \"{linha.descricao}\" ficaria abaixo do já executado ({linha.quantidade_executada:.4f}).")
        linha.quantidade_nova = nova
        diferenca = nova - linha.quantidade_original
        item = itens_contrato.get(linha.item_id)
        if linha.tipo == "continuo" and item is not None:
            # Preço de cada mês (reajustes posteriores ao efeito também contam) e fator 30/360 do item
            linha.impacto_valor = calculos.arredondar(sum(
                (diferenca * valores.preco_em(contrato, item, m.competencia) * (m.fator if item.calcula_pro_rata else Decimal(1))
                 for m in meses_efeito),
                ZERO,
            ))
        # Sob demanda: impacto = diferença no limite × preço unitário
        else:
            linha.impacto_valor = calculos.arredondar(diferenca * linha.valor_unitario)
    # Totais da alteração: impacto em R$ e em % do valor global original da vigência
    alteracao.impacto_valor = sum((i.impacto_valor for i in alteracao.itens), ZERO)
    alteracao.impacto_percentual = (
        (alteracao.impacto_valor * 100 / alteracao.valor_global_original).quantize(Decimal("0.0001")) if alteracao.valor_global_original else ZERO
    )
    if alteracao.impacto_valor == 0:
        raise ErroRegraContrato("Nenhuma quantidade foi alterada.")
    # Novos quantitativos invalidam ciências, memória e consolidado anteriores
    alteracao.ciencias.clear()
    alteracao.memoria_pdf_anexo_id = alteracao.memoria_xlsx_anexo_id = alteracao.consolidado_anexo_id = None
    alteracao.situacao = "aguardando_ciencias"
    auditar(sessao, autor.login, f"contrato.{alteracao.tipo}.quantitativos", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"impacto": alteracao.impacto_valor, "percentual": alteracao.impacto_percentual})
    sessao.commit()


def registrar_ciencia(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, autor: Usuario) -> None:
    """Registra a ciência de um integrante da equipe (uma por pessoa)."""
    contrato = obter_contrato(sessao, contrato_id)
    alteracao, _ = _em_andamento(sessao, contrato, alteracao_id)
    if alteracao.situacao != "aguardando_ciencias":
        raise ErroRegraContrato("Salve os quantitativos antes de registrar ciência.")
    designacao = next((d for d in designacoes_vigentes(contrato) if d.usuario_id == autor.id), None)
    if designacao is None:
        raise ErroRegraContrato("Somente integrantes da equipe de gestão e fiscalização registram ciência.")
    if not any(c.usuario_id == autor.id for c in alteracao.ciencias):
        # Uma nova ciência invalida a memória gerada antes (ela lista as ciências)
        alteracao.ciencias.append(CienciaAlteracao(usuario_id=autor.id, nome=autor.nome_completo or autor.login, papel=designacao.papel, registrada_em=agora_utc()))
        alteracao.memoria_pdf_anexo_id = alteracao.memoria_xlsx_anexo_id = None
        auditar(sessao, autor.login, f"contrato.{alteracao.tipo}.ciencia", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def _linhas(alteracao: AlteracaoQuantidade) -> list[list]:
    """Linhas da tabela da memória (usadas no PDF e na planilha)."""
    return [[i.ordem, i.descricao, "Contínuo" if i.tipo == "continuo" else "Sob demanda", i.valor_unitario, i.quantidade_original,
             i.quantidade_executada, i.quantidade_nova, i.impacto_valor] for i in alteracao.itens]


def gerar_memoria(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, autor: Usuario) -> None:
    """Gera a memória de cálculo em PDF e XLSX (liberada com as ciências mínimas)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, alteracoes = _em_andamento(sessao, contrato, alteracao_id)
    if len(alteracao.ciencias) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato(f"A memória é liberada com ao menos {CIENCIAS_MINIMAS} ciências de pessoas diferentes.")
    rotulo = "Aditamento" if alteracao.tipo == "aditamento" else "Supressão"
    documento = DocumentoPdf(f"Memória de cálculo — {rotulo}", f"Contrato {contrato.numero} · {alteracao.sequencia_vigencia}ª vigência",
                             paisagem=True, autor=autor.nome_completo or autor.login)
    documento.secao("Identificação").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social),
        ("Vigência", f"{alteracao.vigencia_inicio:%d/%m/%Y} a {alteracao.vigencia_fim:%d/%m/%Y}"), ("Mês de efeito", f"{alteracao.mes_efeito:%m/%Y}"),
    ])
    documento.secao("Quantitativos").tabela(
        ["Item", "Descrição", "Tipo", "Valor unitário", "Qtd. atual", "Executado", "Nova qtd.", "Impacto"],
        [[str(l[0]), l[1], l[2], moeda(l[3]), quantidade(l[4]), quantidade(l[5]), quantidade(l[6]), moeda(l[7])] for l in _linhas(alteracao)],
        larguras=[0.5, 4, 1.2, 1.4, 1.2, 1.2, 1.2, 1.5], alinhar_direita=[3, 4, 5, 6, 7],
        rodape=["", "Impacto total", "", "", "", "", f"{alteracao.impacto_percentual:.2f}%".replace(".", ","), moeda(alteracao.impacto_valor)],
    )
    documento.secao("Ciências").tabela(["Nome", "Papel", "Ciência em"],
                                       [[c.nome, PAPEIS.get(c.papel, c.papel), data_hora(c.registrada_em)] for c in alteracao.ciencias], larguras=[4, 3, 2])
    base = f"memoria-{alteracao.tipo}-{contrato.sequencial:03d}-{contrato.ano}"
    pdf = servico_anexos.guardar_pdf_gerado(sessao, documento.gerar(), f"{base}.pdf", "contrato-alteracao-memoria", autor.id, contrato_id=contrato.id)
    xlsx = servico_anexos.guardar_arquivo_gerado(sessao, gerar_planilha([Aba(
        rotulo,
        [Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Tipo", largura=14), Coluna("Valor unitário", FORMATO_MOEDA),
         Coluna("Qtd. atual", FORMATO_QUANTIDADE), Coluna("Executado", FORMATO_QUANTIDADE), Coluna("Nova qtd.", FORMATO_QUANTIDADE), Coluna("Impacto", FORMATO_MOEDA)],
        _linhas(alteracao), titulo=f"{rotulo} — Contrato {contrato.numero}", rodape=["", "Total", "", "", "", "", "", alteracao.impacto_valor],
    )]), f"{base}.xlsx", XLSX, "contrato-alteracao-memoria", autor.id, contrato_id=contrato.id)
    sessao.flush()
    alteracao.memoria_pdf_anexo_id, alteracao.memoria_xlsx_anexo_id = pdf.id, xlsx.id
    sessao.commit()


def gerar_consolidado(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, autor: Usuario) -> None:
    """Junta justificativa, autorização, memória e De Acordo em um único PDF."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, _ = _em_andamento(sessao, contrato, alteracao_id)
    if alteracao.de_acordo_anexo_id is None or alteracao.memoria_pdf_anexo_id is None:
        raise ErroRegraContrato("O consolidado exige a memória em PDF e o De Acordo da contratada.")
    partes = []
    # Ordem das peças no consolidado; as que não existem são puladas
    for coluna in ("justificativa_anexo_id", "autorizacao_anexo_id", "memoria_pdf_anexo_id", "de_acordo_anexo_id"):
        anexo = sessao.get(Anexo, getattr(alteracao, coluna)) if getattr(alteracao, coluna) else None
        if anexo:
            partes.append(servico_anexos.caminho(anexo))
    nome = f"consolidado-{alteracao.tipo}-{contrato.sequencial:03d}-{contrato.ano}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, mesclar_pdfs(partes), nome, "contrato-alteracao-consolidado", autor.id, contrato_id=contrato.id)
    sessao.flush()
    alteracao.consolidado_anexo_id = anexo.id
    sessao.commit()


def concluir(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, autor: Usuario) -> None:
    """Aplica as novas quantidades: contínuo muda a quantidade mensal; sob demanda, o limite da vigência."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, alteracoes = _em_andamento(sessao, contrato, alteracao_id)
    if len(alteracao.ciencias) < CIENCIAS_MINIMAS:
        raise ErroRegraContrato(f"A conclusão exige ao menos {CIENCIAS_MINIMAS} ciências de pessoas diferentes.")
    if _acumulado(contrato, alteracoes, alteracao) > LIMITE_SEM_AUTORIZACAO and alteracao.autorizacao_anexo_id is None:
        raise ErroRegraContrato("Acima de 25%: anexe a autorização do Ordenador de Despesa.")
    faltando = [n for n, c in (("De Acordo da contratada", "de_acordo_anexo_id"), ("Termo Aditivo assinado", "termo_anexo_id")) if getattr(alteracao, c) is None]
    if faltando:
        raise ErroRegraContrato("Anexe: " + ", ".join(faltando) + ".")
    # Aplica as novas quantidades item a item
    itens = {i.id: i for i in contrato.itens}
    ultima = vigencias(contrato)[-1].sequencia
    previsao = None
    for linha in alteracao.itens:
        item = itens.get(linha.item_id)
        if item is None or linha.quantidade_nova == linha.quantidade_original:
            continue
        # Contínuo: muda a quantidade mensal do cadastro (se for a vigência atual)
        if linha.tipo == "continuo":
            if alteracao.sequencia_vigencia == ultima:
                item.quantidade_mensal = linha.quantidade_nova
        else:
            # Sob demanda: grava o novo limite na previsão da vigência
            previsao = previsao or obter_ou_criar_previsao(contrato, alteracao.sequencia_vigencia)
            limite = next((l for l in previsao.limites if l.item_id == item.id), None)
            if limite:
                limite.quantidade_total = linha.quantidade_nova
            else:
                previsao.limites.append(LimitePrevisao(item_id=item.id, quantidade_total=linha.quantidade_nova))
    alteracao.situacao, alteracao.concluida_em = "concluida", agora_utc()
    # Depois de um reajuste, o valor global da vigência atual é uma fotografia: soma-se o impacto
    if contrato.valor_global_reajustado is not None and alteracao.sequencia_vigencia == ultima:
        contrato.valor_global_reajustado += alteracao.impacto_valor
    sessao.flush()
    _recalcular_previstas(contrato, alteracao)
    contrato.versao += 1
    auditar(sessao, autor.login, f"contrato.{alteracao.tipo}.concluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"impacto": alteracao.impacto_valor, "percentual": alteracao.impacto_percentual})
    sessao.commit()


def _recalcular_previstas(contrato: Contrato, alteracao: AlteracaoQuantidade) -> None:
    """Competências ainda não medidas a partir do mês de efeito recebem a nova quantidade prevista (contínuos)."""
    # Períodos de execução indexados pelo início, para recalcular a quantidade prevista
    periodos = {p.inicio: p for p in calculos.periodos_de_execucao(vigencias(contrato), contrato.periodicidade_meses)}
    itens = {i.id: i for i in contrato.itens}
    for competencia in contrato.competencias:
        if competencia.sequencia_vigencia != alteracao.sequencia_vigencia or competencia.competencia < alteracao.mes_efeito:
            continue
        # Só competências ainda não medidas, geradas pelo calendário atual
        if competencia.medicao_concluida_em is not None or competencia.periodo_inicio not in periodos:
            continue
        for linha in competencia.itens:
            item = itens.get(linha.item_id)
            if item is None or item.tipo != "continuo":
                continue
            prevista = ZERO
            for mes in periodos[competencia.periodo_inicio].meses:
                prevista += calculos.quantidade_prevista_continua(valores.quantidade_mensal_em(contrato, item, mes.competencia), item.calcula_pro_rata, [mes])[0]
            linha.quantidade_prevista = prevista


def cancelar(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, autor: Usuario) -> None:
    """Cancela a alteração em andamento (nada muda no contrato)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    alteracao, _ = _em_andamento(sessao, contrato, alteracao_id)
    alteracao.situacao, alteracao.cancelada_em = "cancelada", agora_utc()
    auditar(sessao, autor.login, f"contrato.{alteracao.tipo}.cancelar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def arquivo(sessao: Session, contrato_id: uuid.UUID, alteracao_id: uuid.UUID, anexo_id: uuid.UUID):
    """Baixa um arquivo da alteração; só aceita anexos que pertencem a ela."""
    contrato = obter_contrato(sessao, contrato_id)
    alteracao = next((a for a in _carregar(sessao, contrato) if a.id == alteracao_id), None)
    if alteracao is None:
        raise RegistroNaoEncontrado("Alteração")
    permitidos = {getattr(alteracao, c) for c in ("justificativa_anexo_id", "autorizacao_anexo_id", "de_acordo_anexo_id", "termo_anexo_id",
                                                   "memoria_pdf_anexo_id", "memoria_xlsx_anexo_id", "consolidado_anexo_id")}
    if anexo_id not in permitidos:
        raise RegistroNaoEncontrado("Arquivo")
    return servico_anexos.resposta_download(sessao.get(Anexo, anexo_id))

