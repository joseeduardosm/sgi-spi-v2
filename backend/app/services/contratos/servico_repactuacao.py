# Criado por José Eduardo Santana Martins
# Este arquivo serve para a repactuação do contrato pela Convenção Coletiva de Trabalho (CCT): cadastro, memória, retroativo, checklist,
# consolidado e finalização, com a atualização automática dos preços dos itens vinculados.
"""Repactuação (Lei 14.133, art. 135): a CCT muda componentes de custo e o preço de cada posto sobe pela diferença deles.

Regras (decisões do usuário, 03/11/2026):
- Cada linha é um componente de custo (ex.: "Vale-transporte", R$ 198 → R$ 220), com valores **já por unidade do item financeiro**
  (a pessoa calcula dias e encargos), ligado a 1..N itens do contrato. A **diferença em R$** da linha soma no preço unitário de cada item
  vinculado; um item vinculado a várias linhas soma todas.
- Memória por item financeiro: preço vigente → novo × quantidade mensal = impacto; nova base mensal = base vigente + soma dos impactos
  (só os contínuos entram na base; o sob demanda muda só o preço).
- Vale a partir da **data de vigência** (`data_efeito`). Mês quebrado igual ao reajuste: uma escolha (pro rata ou integral) para todos.
- Retroativo igual ao reajuste: as competências já **medidas** (pagas ou não) entram na diferença — positiva vira competência de diferença
  a pagar, negativa vira crédito abatido nas próximas medições; as **não medidas** recebem o novo preço na medição.
  A diferença de cada medida é a própria diferença do item × quantidade medida × fração do mês a partir do efeito (não "preço novo −
  preço pago"), para que uma repactuação seguinte nunca cobre de novo a diferença desta.
- A CCT vai para os Documentos importantes como "CCT mm/aaaa" (data-base da CCT).

Fluxo: abrir (CCT) → linhas e vínculos ("Finalizar" o cadastro) → memória (PDF/XLSX) → checklist → consolidado → apostilamento e finalizar.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import (
    Competencia, Contrato, DocumentoContrato, DocumentoRepactuacao, ItemMedicao, ItemRepactuacao, LinhaRepactuacao, MemoriaRepactuacao,
    ModeloGlobal, Repactuacao, VinculoLinhaRepactuacao,
)
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    CompetenciaRetroativaRepactuacao, DocumentoProrrogacaoLeitura, GravacaoLinhasRepactuacao, ItemContratoOpcao, ItemRepactuacaoLeitura,
    LeituraMemoriaVersao, LeituraRepactuacao, LinhaRepactuacaoLeitura, OpcaoMesQuebradoRepactuacao, PainelRepactuacao,
)
from app.schemas.contratos.execucao import LeituraArquivo
from app.services import servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.documentos_execucao import moeda, moeda_unitaria, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_competencias import proxima_competencia_a_medir, registrar_credito_reajuste, sincronizar_competencia
from app.services.contratos.servico_configuracao_execucao import checklist_ativo, copiar_checklist
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato, pode_editar, vigencias
from app.services.documentos.pdf import DocumentoPdf, mesclar_pdfs
from app.services.documentos.planilha import FORMATO_MOEDA, FORMATO_MOEDA_UNITARIA, FORMATO_QUANTIDADE, Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Documentos importantes: códigos 001–023 são o catálogo; do 024 em diante, os anexados pelos processos (termos aditivos, CCT)
PRIMEIRO_CODIGO_EXTRA = 24
ROTULOS_MODO = {"pro_rata": "pro rata (dias antes do efeito com o preço antigo, a partir dele com o novo)", "integral": "integral (mês inteiro repactuado)"}
# Situação exibida das competências do período retroativo, pela etapa em que estão
SITUACOES = {"medicao": "Aguardando medição", "avaliacao": "Na avaliação", "nota_fiscal": "Na nota fiscal", "retencao": "Na retenção e documentos",
             "cadin": "No CADIN", "checklist": "No checklist", "consolidado": "No consolidado", "ordem_bancaria": "Aguardando OB", "concluida": "Paga"}


# ---------------------------------------------------------------------------------------------
# Carga e regras básicas
# ---------------------------------------------------------------------------------------------

def _carregar(sessao: Session, contrato: Contrato) -> list[Repactuacao]:
    """Repactuações do contrato com tudo carregado, da mais antiga para a mais recente."""
    return list(sessao.scalars(
        select(Repactuacao).where(Repactuacao.contrato_id == contrato.id)
        .options(selectinload(Repactuacao.linhas).selectinload(LinhaRepactuacao.vinculos), selectinload(Repactuacao.itens),
                 selectinload(Repactuacao.memorias).selectinload(MemoriaRepactuacao.pdf_anexo),
                 selectinload(Repactuacao.memorias).selectinload(MemoriaRepactuacao.xlsx_anexo),
                 selectinload(Repactuacao.documentos).selectinload(DocumentoRepactuacao.anexo),
                 selectinload(Repactuacao.cct_anexo), selectinload(Repactuacao.consolidado_anexo), selectinload(Repactuacao.apostilamento_anexo))
        .order_by(Repactuacao.criado_em)
    ))


def _em_andamento(sessao: Session, contrato: Contrato, repactuacao_id: uuid.UUID) -> Repactuacao:
    """A repactuação em rascunho do contrato, ou erro."""
    repactuacao = next((r for r in _carregar(sessao, contrato) if r.id == repactuacao_id), None)
    if repactuacao is None:
        raise RegistroNaoEncontrado("Repactuação")
    if repactuacao.situacao != "rascunho":
        raise ErroRegraContrato("Esta repactuação já foi concluída ou cancelada.", conflito=True)
    return repactuacao


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


# ---------------------------------------------------------------------------------------------
# Cálculo: preços novos, base mensal e retroativo
# ---------------------------------------------------------------------------------------------

def diferencas_por_item(repactuacao: Repactuacao) -> dict[uuid.UUID, Decimal]:
    """Soma das diferenças (repactuado − vigente) das linhas vinculadas a cada item financeiro."""
    deltas: dict[uuid.UUID, Decimal] = {}
    for linha in repactuacao.linhas:
        for vinculo in linha.vinculos:
            deltas[vinculo.item_id] = deltas.get(vinculo.item_id, ZERO) + linha.diferenca
    return deltas


def fotografar(contrato: Contrato, repactuacao: Repactuacao) -> None:
    """Refaz a fotografia por item (preço na data de efeito → preço + diferenças) e as bases mensais. Sem commit."""
    deltas = diferencas_por_item(repactuacao)
    itens = {i.id: i for i in contrato.itens}
    repactuacao.itens.clear()
    # Apaga as fotografias antigas antes de gravar as novas (mesmo item: o índice único não aceita as duas ao mesmo tempo)
    sessao = object_session(repactuacao)
    if sessao is not None:
        sessao.flush()
    base_atual = impacto = ZERO
    for item in sorted(contrato.itens, key=lambda i: i.ordem):
        preco = valores.preco_em(contrato, item, repactuacao.efeito)
        qtd = valores.quantidade_mensal_em(contrato, item, repactuacao.mes_referencia) if item.tipo == "continuo" else ZERO
        if item.tipo == "continuo":
            base_atual += qtd * preco
        if item.id not in deltas:
            continue
        novo = preco + deltas[item.id]
        if novo < 0:
            raise ErroRegraContrato(f"O item \"{item.descricao}\" ficaria com preço negativo ({moeda_unitaria(novo)}).")
        if item.tipo == "continuo":
            impacto += qtd * deltas[item.id]
        repactuacao.itens.append(ItemRepactuacao(item_id=item.id, ordem=item.ordem, descricao=itens[item.id].descricao[:1000], tipo=item.tipo,
                                                 quantidade_mensal=qtd, valor_unitario_atual=preco, valor_unitario_repactuado=novo))
    repactuacao.base_atual = calculos.arredondar(base_atual)
    repactuacao.base_repactuada = calculos.arredondar(base_atual + impacto)


def _quebrada(inicio: date, fim: date, efeito: date) -> bool:
    return inicio < efeito <= fim


def _fracao(inicio: date, fim: date, efeito: date, modo: str) -> Decimal:
    """Quanto do período vale a diferença: nada antes do efeito, tudo depois; no período quebrado, integral ou os dias a partir do efeito."""
    if fim < efeito:
        return ZERO
    if inicio >= efeito or modo == "integral":
        return Decimal(1)
    total = calculos.dias_comerciais(inicio, fim) or 1
    return Decimal(calculos.dias_comerciais(efeito, fim)) / Decimal(total)


def _medidas(contrato: Contrato, repactuacao: Repactuacao) -> list[Competencia]:
    """Competências já medidas (regulares e adicionais) que terminam no efeito ou depois: a diferença delas é paga à parte."""
    return sorted((c for c in contrato.competencias if c.tipo in ("regular", "adicional") and c.medicao_concluida_em is not None
                   and c.periodo_fim >= repactuacao.efeito), key=lambda c: (c.periodo_inicio, c.numero_adicional))


def _nao_medidas(contrato: Contrato, repactuacao: Repactuacao) -> list[Competencia]:
    """Competências regulares ainda não medidas a partir do efeito: recebem o novo preço na medição."""
    return sorted((c for c in contrato.competencias if c.tipo == "regular" and c.medicao_concluida_em is None and c.periodo_fim >= repactuacao.efeito),
                  key=lambda c: c.periodo_inicio)


@dataclass
class Retroativo:
    linhas: list[CompetenciaRetroativaRepactuacao]
    medidas: list[Competencia]
    quantidades: dict  # item → quantidade medida que vale a diferença (já com a fração do mês)
    valores: dict  # item → valor da diferença
    total_pagas: Decimal
    total: Decimal
    tem_quebrada: bool


def retroativo(contrato: Contrato, repactuacao: Repactuacao, modo: str | None = None) -> Retroativo:
    """Competências do período retroativo e a diferença de cada medida (diferença do item × quantidade medida × fração do mês)."""
    modo = modo or repactuacao.calculo_mes_quebrado or "pro_rata"
    deltas = {i.item_id: i.diferenca for i in repactuacao.itens}
    efeito = repactuacao.efeito
    linhas, quantidades, valores_dif = [], {}, {}
    total_pagas = total = ZERO
    tem_quebrada = False
    medidas = _medidas(contrato, repactuacao)
    for c in medidas:
        pago = diferenca = ZERO
        for linha in c.itens:
            pago += calculos.arredondar(linha.quantidade_medida * linha.valor_unitario) + (linha.acerto or ZERO)
            if linha.item_id not in deltas or linha.quantidade_medida <= 0:
                continue
            inicio, fim = linha.periodo_inicio or c.periodo_inicio, linha.periodo_fim or c.periodo_fim
            if _quebrada(inicio, fim, efeito):
                tem_quebrada = True
            qtd = linha.quantidade_medida * _fracao(inicio, fim, efeito, modo)
            if qtd <= 0:
                continue
            valor = qtd * deltas[linha.item_id]
            quantidades[linha.item_id] = quantidades.get(linha.item_id, ZERO) + qtd
            valores_dif[linha.item_id] = valores_dif.get(linha.item_id, ZERO) + valor
            diferenca += valor
        diferenca = calculos.arredondar(diferenca)
        paga = c.etapa_atual == "concluida"
        total += diferenca
        if paga:
            total_pagas += diferenca
        linhas.append(CompetenciaRetroativaRepactuacao(
            identificador=c.identificador, competencia=c.numero_competencia, medida=True, paga=paga, situacao=SITUACOES.get(c.etapa_atual, c.etapa_atual),
            quebrada=_quebrada(c.periodo_inicio, c.periodo_fim, efeito), valor_pago=pago, valor_repactuado=pago + diferenca, diferenca=diferenca))
    for c in _nao_medidas(contrato, repactuacao):
        linhas.append(CompetenciaRetroativaRepactuacao(
            identificador=c.identificador, competencia=c.numero_competencia, medida=False, paga=False, situacao=SITUACOES.get(c.etapa_atual, c.etapa_atual),
            quebrada=_quebrada(c.periodo_inicio, c.periodo_fim, efeito)))
    return Retroativo(linhas, medidas, quantidades, valores_dif, total_pagas, total, tem_quebrada)


def _hash(contrato: Contrato, repactuacao: Repactuacao) -> str:
    """Impressão digital do que a memória mostra: muda a memória, muda o hash."""
    r = retroativo(contrato, repactuacao)
    return hashlib.sha256(json.dumps(
        [[l.ordem, l.descricao, str(l.valor_vigente), str(l.valor_repactuado), sorted(str(v.item_id) for v in l.vinculos)] for l in repactuacao.linhas]
        + [[str(i.item_id), str(i.valor_unitario_atual), str(i.valor_unitario_repactuado), str(i.quantidade_mensal)] for i in repactuacao.itens]
        + [str(repactuacao.data_base_cct), str(repactuacao.efeito), str(repactuacao.calculo_mes_quebrado)]
        + [[x.identificador, x.paga, str(x.valor_pago), str(x.diferenca)] for x in r.linhas]
    ).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------------------------

def leitura(contrato: Contrato, repactuacao: Repactuacao) -> LeituraRepactuacao:
    r = retroativo(contrato, repactuacao)
    opcoes = []
    if r.tem_quebrada:
        opcoes = [OpcaoMesQuebradoRepactuacao(calculo=m, total_diferenca=retroativo(contrato, repactuacao, m).total) for m in ("pro_rata", "integral")]
    documentos = sorted(repactuacao.documentos, key=lambda d: (d.incluido_no_processo, d.ordem))
    ultima = repactuacao.memorias[-1] if repactuacao.memorias else None
    consolidado = repactuacao.consolidado_anexo
    marcos = [m.criado_em for m in repactuacao.memorias] + [d.enviado_em for d in documentos if d.enviado_em]
    competencia_dif = next((c for c in contrato.competencias if c.tipo == "diferenca_repactuacao" and c.repactuacao_id == repactuacao.id), None)
    return LeituraRepactuacao(
        id=repactuacao.id, situacao=repactuacao.situacao, data_base_cct=repactuacao.data_base_cct, mes_referencia=repactuacao.mes_referencia,
        data_efeito=repactuacao.data_efeito, cadastro_concluido=repactuacao.cadastro_concluido_em is not None,
        linhas=[LinhaRepactuacaoLeitura(
            id=l.id, ordem=l.ordem, descricao=l.descricao, valor_vigente=l.valor_vigente, valor_repactuado=l.valor_repactuado, diferenca=l.diferenca,
            diferenca_percentual=(l.diferenca / l.valor_vigente * 100).quantize(Decimal("0.0001")) if l.valor_vigente else ZERO,
            itens_ids=[v.item_id for v in l.vinculos]) for l in repactuacao.linhas],
        itens=[ItemRepactuacaoLeitura(
            item_id=i.item_id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo, quantidade_mensal=i.quantidade_mensal, valor_unitario_atual=i.valor_unitario_atual,
            valor_unitario_repactuado=i.valor_unitario_repactuado, diferenca=i.diferenca,
            impacto_mensal=calculos.arredondar(i.quantidade_mensal * i.diferenca) if i.tipo == "continuo" else ZERO) for i in repactuacao.itens],
        base_atual=repactuacao.base_atual, total_diferencas=repactuacao.base_repactuada - repactuacao.base_atual, base_repactuada=repactuacao.base_repactuada,
        calculo_mes_quebrado=repactuacao.calculo_mes_quebrado, opcoes_mes_quebrado=opcoes, competencias=r.linhas,
        total_retroativo_pagas=r.total_pagas, total_retroativo=r.total,
        memorias=[LeituraMemoriaVersao(versao=m.versao, criada_em=m.criado_em, pdf=_arquivo(m.pdf_anexo), xlsx=_arquivo(m.xlsx_anexo)) for m in repactuacao.memorias],
        memoria_atualizada=ultima is not None and ultima.hash_origem == _hash(contrato, repactuacao),
        checklist=[DocumentoProrrogacaoLeitura(id=d.id, ordem=d.ordem, nome=d.nome, observacao=d.observacao, obrigatorio=d.obrigatorio, arquivo=_arquivo(d.anexo),
                                               incluido_no_processo=d.incluido_no_processo, incluido_em=d.incluido_em) for d in documentos],
        obrigatorios_pendentes=sum(1 for d in documentos if d.obrigatorio and not d.anexo_id),
        cct=_arquivo(repactuacao.cct_anexo), consolidado=_arquivo(consolidado),
        consolidado_atualizado=consolidado is not None and all(consolidado.criado_em >= m for m in marcos),
        apostilamento=_arquivo(repactuacao.apostilamento_anexo), diferenca_retroativa=repactuacao.diferenca_retroativa,
        competencia_diferenca=competencia_dif.identificador if competencia_dif else None,
        criado_em=repactuacao.criado_em, concluido_em=repactuacao.concluido_em, cancelado_em=repactuacao.cancelado_em,
    )


def painel(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> PainelRepactuacao:
    contrato = obter_contrato(sessao, contrato_id)
    lista = _carregar(sessao, contrato)
    em_andamento = next((r for r in lista if r.situacao == "rascunho"), None)
    return PainelRepactuacao(
        em_andamento=leitura(contrato, em_andamento) if em_andamento else None,
        historico=[leitura(contrato, r) for r in reversed(lista) if r.situacao != "rascunho"],
        itens_contrato=[ItemContratoOpcao(id=i.id, ordem=i.ordem, descricao=i.descricao, tipo=i.tipo, valor_unitario=i.valor_unitario)
                        for i in sorted(contrato.itens, key=lambda i: i.ordem)],
        pode_editar=pode_editar(sessao, contrato, usuario),
    )


# ---------------------------------------------------------------------------------------------
# Passo 1: abrir (CCT) e cadastrar as linhas
# ---------------------------------------------------------------------------------------------

def abrir(sessao: Session, contrato_id: uuid.UUID, data_base_cct: date, data_efeito: date, arquivo: BinaryIO, nome: str, autor: Usuario) -> uuid.UUID:
    """Abre a repactuação com a CCT (vai também para os Documentos importantes como "CCT mm/aaaa")."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if any(r.situacao == "rascunho" for r in _carregar(sessao, contrato)):
        raise ErroRegraContrato("Já existe uma repactuação em elaboração neste contrato: conclua ou cancele antes.", conflito=True)
    lista = vigencias(contrato)
    if not lista or not lista[0].inicio <= data_efeito <= lista[-1].fim:
        raise ErroRegraContrato("A data de vigência da repactuação precisa estar dentro das vigências do contrato.")
    # A linha do tempo de preços é uma só: um reajuste ou repactuação já concluído depois desta data teria fotografado o preço sem ela
    posterior = [r for r in valores._reajustes(contrato) if r.efeito > data_efeito]
    if posterior:
        raise ErroRegraContrato(f"Já há reajuste ou repactuação concluído com efeito em {posterior[-1].efeito:%d/%m/%Y}, depois de {data_efeito:%d/%m/%Y}: "
                                "a repactuação precisa valer a partir dessa data ou depois.", conflito=True)
    data_base = data_base_cct.replace(day=1)
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-repactuacao-cct", autor.id, contrato_id=contrato.id)
    sessao.flush()
    repactuacao = Repactuacao(contrato_id=contrato.id, data_base_cct=data_base, mes_referencia=data_efeito.replace(day=1), data_efeito=data_efeito,
                              cct_anexo_id=anexo.id, criado_por_id=autor.id, criado_em=agora_utc())
    sessao.add(repactuacao)
    # CCT nos Documentos importantes, com o próximo código livre depois do catálogo
    codigo = max([d.codigo_tipo for d in contrato.documentos] + [PRIMEIRO_CODIGO_EXTRA - 1]) + 1
    contrato.documentos.append(DocumentoContrato(codigo_tipo=codigo, titulo=f"CCT {data_base:%m/%Y}", anexo_id=anexo.id, enviado_em=agora_utc(), enviado_por_id=autor.id))
    _copiar_checklist(sessao, repactuacao)
    sessao.flush()
    auditar(sessao, autor.login, "contrato.repactuacao.abrir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"data_base_cct": data_base, "data_efeito": data_efeito})
    sessao.commit()
    return repactuacao.id


def _validar_linhas(contrato: Contrato, dados: GravacaoLinhasRepactuacao) -> None:
    itens = {i.id for i in contrato.itens}
    for n, linha in enumerate(dados.linhas, start=1):
        if not linha.descricao.strip():
            raise ErroRegraContrato(f"Informe a descrição da linha {n}.")
        if set(linha.itens_ids) - itens:
            raise ErroRegraContrato(f"A linha {n} está vinculada a um item que não é deste contrato.")
        if len(set(linha.itens_ids)) != len(linha.itens_ids):
            raise ErroRegraContrato(f"A linha {n} tem o mesmo item vinculado duas vezes.")


def _aplicar_linhas(contrato: Contrato, repactuacao: Repactuacao, dados: GravacaoLinhasRepactuacao) -> None:
    _validar_linhas(contrato, dados)
    repactuacao.linhas.clear()
    for n, linha in enumerate(dados.linhas, start=1):
        repactuacao.linhas.append(LinhaRepactuacao(
            ordem=n, descricao=" ".join(linha.descricao.split())[:500], valor_vigente=linha.valor_vigente, valor_repactuado=linha.valor_repactuado,
            vinculos=[VinculoLinhaRepactuacao(item_id=i) for i in linha.itens_ids]))
    fotografar(contrato, repactuacao)


def salvar_linhas(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, dados: GravacaoLinhasRepactuacao, autor: Usuario) -> None:
    """Grava as linhas e os vínculos (recalcula os preços novos); com `finalizar`, conclui o cadastro e libera a memória."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    _aplicar_linhas(contrato, repactuacao, dados)
    if dados.finalizar:
        repactuacao.cadastro_concluido_em = agora_utc()
    auditar(sessao, autor.login, "contrato.repactuacao.linhas", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"linhas": [[l.descricao, str(l.valor_vigente), str(l.valor_repactuado), len(l.vinculos)] for l in repactuacao.linhas],
                   "finalizar": dados.finalizar})
    sessao.commit()


def previa(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, dados: GravacaoLinhasRepactuacao, autor: Usuario) -> LeituraRepactuacao:
    """Os mesmos cálculos sem gravar nada (a tela recalcula enquanto se digita)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    try:
        _aplicar_linhas(contrato, repactuacao, dados)
        sessao.flush()
        return leitura(contrato, repactuacao)
    finally:
        sessao.rollback()


def escolher_mes_quebrado(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, calculo: str, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    repactuacao.calculo_mes_quebrado = calculo
    auditar(sessao, autor.login, "contrato.repactuacao.mes_quebrado", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"calculo": calculo})
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Passo 2 e 3: memória de cálculo (com o retroativo)
# ---------------------------------------------------------------------------------------------

def _percentual(valor: Decimal) -> str:
    return ("+" if valor > 0 else "-" if valor < 0 else "") + f"{abs(valor):.2f}".replace(".", ",") + "%"


def _sinal(valor: Decimal, unitario: bool = False) -> str:
    return ("+" if valor > 0 else "-" if valor < 0 else "") + (moeda_unitaria if unitario else moeda)(abs(valor))


def _texto_destino(contrato: Contrato, total: Decimal) -> str:
    if total > 0:
        return f"{moeda(total)} a pagar em competência de diferença de repactuação"
    if total < 0:
        destino = proxima_competencia_a_medir(contrato)
        onde = f"na medição de {destino.numero_competencia}" if destino else "na próxima competência gerada"
        return f"crédito de {moeda(-total)} da SPI, abatido {onde}"
    return "sem diferença (nenhuma competência medida a partir da data de vigência)"


def _pdf_memoria(contrato: Contrato, repactuacao: Repactuacao, versao: int, autor: Usuario) -> bytes:
    l = leitura(contrato, repactuacao)
    documento = DocumentoPdf("Memória de cálculo da repactuação", f"Contrato {contrato.numero} · CCT {repactuacao.data_base_cct:%m/%Y} · versão {versao}",
                             paisagem=True, autor=_nome(autor))
    documento.secao("Identificação").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social), ("CCT (data-base)", f"{repactuacao.data_base_cct:%m/%Y}"),
        ("Novos valores a partir de", f"{repactuacao.efeito:%d/%m/%Y}"),
    ])
    documento.secao("Itens da repactuação (valores por unidade do item financeiro)").tabela(
        ["Nº", "Descrição", "Valor vigente", "Valor repactuado", "Diferença %", "Diferença R$"],
        [[str(x.ordem), x.descricao, moeda_unitaria(x.valor_vigente), moeda_unitaria(x.valor_repactuado), _percentual(x.diferenca_percentual),
          _sinal(x.diferenca, unitario=True)] for x in l.linhas],
        larguras=[0.6, 5, 1.6, 1.6, 1.2, 1.6], alinhar_direita=[2, 3, 4, 5],
        rodape=["", "Total das diferenças dos itens", "", "", "", _sinal(sum((x.diferenca for x in l.linhas), ZERO), unitario=True)],
    )
    documento.secao("Itens financeiros (preço vigente + diferenças das linhas vinculadas)").tabela(
        ["Item", "Descrição", "Preço vigente", "Novo preço", "Diferença", "Qtd. mensal", "Impacto mensal"],
        [[str(i.ordem), i.descricao, moeda_unitaria(i.valor_unitario_atual), moeda_unitaria(i.valor_unitario_repactuado), _sinal(i.diferenca, unitario=True),
          quantidade(i.quantidade_mensal) if i.tipo == "continuo" else "sob demanda", moeda(i.impacto_mensal)] for i in l.itens],
        larguras=[0.6, 5, 1.5, 1.5, 1.3, 1.2, 1.6], alinhar_direita=[2, 3, 4, 5, 6],
    )
    documento.secao("Totais").campos([
        ("Base mensal vigente", moeda(l.base_atual)), ("Total das diferenças da repactuação", _sinal(l.total_diferencas)),
        ("Nova base mensal repactuada", moeda(l.base_repactuada)),
    ])
    medidas = [x for x in l.competencias if x.medida]
    nao_medidas = [x for x in l.competencias if not x.medida]
    if medidas:
        documento.secao("Retroativo: competências já medidas (a diferença é paga à parte)").tabela(
            ["Competência", "Situação", "Valor pago", "Valor repactuado", "Diferença"],
            [[x.competencia + (" (mês quebrado)" if x.quebrada else ""), x.situacao, moeda(x.valor_pago), moeda(x.valor_repactuado), _sinal(x.diferenca)] for x in medidas],
            larguras=[3, 2.4, 1.8, 1.8, 1.8], alinhar_direita=[2, 3, 4],
            rodape=["Total", "", "", "", _sinal(l.total_retroativo)],
        )
    if nao_medidas:
        documento.secao("Competências ainda não medidas (recebem o novo preço na medição)").tabela(
            ["Competência", "Situação"], [[x.competencia, x.situacao] for x in nao_medidas], larguras=[4, 4])
    documento.secao("Resumo").campos([
        ("Diferença das competências pagas", _sinal(l.total_retroativo_pagas)),
        ("Diferença total das competências medidas", _sinal(l.total_retroativo)),
        ("Destino", _texto_destino(contrato, l.total_retroativo)),
        *([("Meses quebrados", ROTULOS_MODO[repactuacao.calculo_mes_quebrado or "pro_rata"])] if l.opcoes_mes_quebrado else []),
    ])
    return documento.gerar()


def _xlsx_memoria(contrato: Contrato, repactuacao: Repactuacao) -> bytes:
    l = leitura(contrato, repactuacao)
    abas = [
        Aba("Repactuação", [Coluna("Nº", largura=6), Coluna("Descrição", largura=40), Coluna("Valor vigente", FORMATO_MOEDA_UNITARIA),
                            Coluna("Valor repactuado", FORMATO_MOEDA_UNITARIA), Coluna("Diferença %", "+0.00;-0.00;0.00"), Coluna("Diferença R$", FORMATO_MOEDA_UNITARIA)],
            [[x.ordem, x.descricao, x.valor_vigente, x.valor_repactuado, x.diferenca_percentual, x.diferenca] for x in l.linhas],
            titulo=f"Repactuação (CCT {repactuacao.data_base_cct:%m/%Y}) — Contrato {contrato.numero} — a partir de {repactuacao.efeito:%d/%m/%Y}",
            rodape=["", "Total das diferenças dos itens", "", "", "", sum((x.diferenca for x in l.linhas), ZERO)]),
        Aba("Itens financeiros", [Coluna("Item", largura=6), Coluna("Descrição", largura=40), Coluna("Preço vigente", FORMATO_MOEDA_UNITARIA),
                                  Coluna("Novo preço", FORMATO_MOEDA_UNITARIA), Coluna("Diferença", FORMATO_MOEDA_UNITARIA), Coluna("Qtd. mensal", FORMATO_QUANTIDADE),
                                  Coluna("Impacto mensal", FORMATO_MOEDA, 18)],
            [[i.ordem, i.descricao, i.valor_unitario_atual, i.valor_unitario_repactuado, i.diferenca, i.quantidade_mensal, i.impacto_mensal] for i in l.itens],
            titulo=f"Itens financeiros — Contrato {contrato.numero}",
            observacoes=[f"Base mensal vigente: {moeda(l.base_atual)}", f"Total das diferenças: {moeda(l.total_diferencas)}",
                         f"Nova base mensal repactuada: {moeda(l.base_repactuada)}"]),
        Aba("Retroativo", [Coluna("Competência", largura=24), Coluna("Situação", largura=24), Coluna("Valor pago", FORMATO_MOEDA, 18),
                           Coluna("Valor repactuado", FORMATO_MOEDA, 18), Coluna("Diferença", FORMATO_MOEDA, 18)],
            [[x.competencia, x.situacao, x.valor_pago, x.valor_repactuado, x.diferenca] for x in l.competencias],
            titulo=f"Retroativo a partir de {repactuacao.efeito:%d/%m/%Y} — Contrato {contrato.numero}",
            observacoes=[f"Diferença das competências pagas: {moeda(l.total_retroativo_pagas)}", f"Diferença total das medidas: {moeda(l.total_retroativo)}",
                         f"Destino: {_texto_destino(contrato, l.total_retroativo)}"]),
    ]
    return gerar_planilha(abas)


def gerar_memoria(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, autor: Usuario) -> None:
    """PDF e XLSX da memória; nova versão só se os dados mudaram."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    if repactuacao.cadastro_concluido_em is None or not repactuacao.linhas:
        raise ErroRegraContrato("Finalize o cadastro dos itens da repactuação antes de gerar a memória.")
    if repactuacao.calculo_mes_quebrado is None and retroativo(contrato, repactuacao).tem_quebrada:
        raise ErroRegraContrato("Escolha como calcular os meses quebrados (pro rata ou integral) antes de gerar a memória.")
    origem = _hash(contrato, repactuacao)
    if repactuacao.memorias and repactuacao.memorias[-1].hash_origem == origem:
        return
    versao = len(repactuacao.memorias) + 1
    base = f"memoria-repactuacao-{contrato.numero_arquivo}-v{versao}"
    pdf = servico_anexos.guardar_pdf_gerado(sessao, _pdf_memoria(contrato, repactuacao, versao, autor), f"{base}.pdf", "contrato-repactuacao-memoria", autor.id, contrato_id=contrato.id)
    xlsx = servico_anexos.guardar_arquivo_gerado(sessao, _xlsx_memoria(contrato, repactuacao), f"{base}.xlsx", XLSX, "contrato-repactuacao-memoria", autor.id, contrato_id=contrato.id)
    repactuacao.memorias.append(MemoriaRepactuacao(versao=versao, pdf_anexo=pdf, xlsx_anexo=xlsx, hash_origem=origem, criado_por_id=autor.id, criado_em=agora_utc()))
    auditar(sessao, autor.login, "contrato.repactuacao.memoria", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"versao": versao})
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Passo 4: checklist (mesmo padrão da prorrogação)
# ---------------------------------------------------------------------------------------------

def _copiar_checklist(sessao: Session, repactuacao: Repactuacao) -> None:
    """Ponto de partida: os documentos do modelo "Checklist Repactuação" ativo (Contratos › Modelos), se houver."""
    modelo = sessao.scalar(select(ModeloGlobal).where(ModeloGlobal.tipo == "checklist_repactuacao", ModeloGlobal.ativo.is_(True))
                           .order_by(ModeloGlobal.atualizado_em.desc()))
    if modelo is None:
        return
    for ordem, item in enumerate((modelo.conteudo or {}).get("itens", []), start=1):
        repactuacao.documentos.append(DocumentoRepactuacao(ordem=ordem, nome=item.get("nome", "")[:500], observacao=(item.get("observacao") or "")[:1000],
                                                           obrigatorio=bool(item.get("obrigatorio", True))))


def _documento(repactuacao: Repactuacao, documento_id: uuid.UUID) -> DocumentoRepactuacao:
    documento = next((d for d in repactuacao.documentos if d.id == documento_id), None)
    if documento is None:
        raise RegistroNaoEncontrado("Documento")
    return documento


def anexar_documento(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, documento_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    documento = _documento(_em_andamento(sessao, contrato, repactuacao_id), documento_id)
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-repactuacao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    auditar(sessao, autor.login, "contrato.repactuacao.checklist.enviar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


def incluir_documento(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, nome_documento: str, descricao: str, arquivo: BinaryIO,
                      nome_arquivo: str, autor: Usuario) -> None:
    """Documento fora do modelo (nome, descrição e PDF): nunca obrigatório."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    nome_documento = " ".join((nome_documento or "").split())
    if not nome_documento:
        raise ErroRegraContrato("Informe o nome do documento.")
    documento = DocumentoRepactuacao(ordem=max((d.ordem for d in repactuacao.documentos), default=0) + 1, nome=nome_documento[:500],
                                     observacao=(descricao or "").strip()[:1000], obrigatorio=False, incluido_no_processo=True, incluido_por_id=autor.id,
                                     incluido_em=agora_utc())
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome_arquivo, "contrato-repactuacao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    repactuacao.documentos.append(documento)
    auditar(sessao, autor.login, "contrato.repactuacao.checklist.incluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


def excluir_documento(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, documento_id: uuid.UUID, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    documento = _documento(repactuacao, documento_id)
    if not documento.incluido_no_processo:
        raise ErroRegraContrato("Só os documentos incluídos durante o processo podem ser excluídos; os do checklist padrão ficam.")
    if documento.anexo is not None:
        servico_anexos.descartar(documento.anexo)
    repactuacao.documentos.remove(documento)
    auditar(sessao, autor.login, "contrato.repactuacao.checklist.excluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Passo 5: documento consolidado
# ---------------------------------------------------------------------------------------------

def _capa(contrato: Contrato, repactuacao: Repactuacao, autor: Usuario) -> bytes:
    l = leitura(contrato, repactuacao)
    documento = DocumentoPdf("Repactuação do contrato", f"Contrato {contrato.numero} · CCT {repactuacao.data_base_cct:%m/%Y}", autor=_nome(autor))
    documento.secao("Contrato").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social), ("Objeto", (contrato.objeto or "")[:400]),
    ])
    documento.secao("Repactuação").campos([
        ("CCT (data-base)", f"{repactuacao.data_base_cct:%m/%Y}"), ("Novos valores a partir de", f"{repactuacao.efeito:%d/%m/%Y}"),
        ("Itens repactuados", str(len(l.linhas))), ("Base mensal vigente", moeda(l.base_atual)), ("Nova base mensal", moeda(l.base_repactuada)),
        ("Diferença retroativa", _texto_destino(contrato, l.total_retroativo)),
    ])
    documento.secao("Conteúdo").campos([("1", "Convenção Coletiva de Trabalho"), ("2", "Checklist de repactuação (documentos)"), ("3", "Memória de cálculo")])
    return documento.gerar()


def gerar_consolidado(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, autor: Usuario) -> None:
    """Capa + CCT + documentos do checklist + memória de cálculo, num PDF só."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    if not repactuacao.memorias or repactuacao.memorias[-1].hash_origem != _hash(contrato, repactuacao):
        raise ErroRegraContrato("Gere a memória de cálculo atualizada antes do consolidado.")
    partes: list = [_capa(contrato, repactuacao, autor), servico_anexos.caminho(repactuacao.cct_anexo)]
    partes += [servico_anexos.caminho(d.anexo) for d in sorted(repactuacao.documentos, key=lambda d: (d.incluido_no_processo, d.ordem)) if d.anexo]
    partes.append(servico_anexos.caminho(repactuacao.memorias[-1].pdf_anexo))
    nome = f"consolidado-repactuacao-{contrato.numero_arquivo}-{repactuacao.data_base_cct:%Y-%m}.pdf"
    anexo = servico_anexos.guardar_pdf_gerado(sessao, mesclar_pdfs(partes), nome, "contrato-repactuacao-consolidado", autor.id, contrato_id=contrato.id)
    sessao.flush()
    repactuacao.consolidado_anexo = anexo
    auditar(sessao, autor.login, "contrato.repactuacao.consolidado", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Passo 6: apostilamento e finalização
# ---------------------------------------------------------------------------------------------

def _competencia_diferenca(contrato: Contrato, repactuacao: Repactuacao, r: Retroativo) -> Competencia | None:
    """Competência complementar com a diferença das quantidades já medidas (só quando a diferença líquida é positiva)."""
    if not r.quantidades or calculos.arredondar(r.total) <= 0:
        return None
    itens = {i.id: i for i in contrato.itens}
    # Cada repactuação gera a sua competência de diferença: duas no mesmo período ficam numeradas (1, 2…), como as medições adicionais
    numero = 1 + max((c.numero_adicional for c in contrato.competencias if c.tipo == "diferenca_repactuacao"
                      and c.periodo_inicio == r.medidas[0].periodo_inicio), default=0)
    competencia = Competencia(tipo="diferenca_repactuacao", repactuacao_id=repactuacao.id, competencia=repactuacao.mes_referencia, numero_adicional=numero,
                              periodo_inicio=r.medidas[0].periodo_inicio, periodo_fim=r.medidas[-1].periodo_fim,
                              sequencia_vigencia=r.medidas[-1].sequencia_vigencia, etapa_atual="medicao")
    for item_id, total_medido in r.quantidades.items():
        if calculos.arredondar(r.valores[item_id]) == 0:
            continue
        item = itens[item_id]
        unitario = (r.valores[item_id] / total_medido).quantize(Decimal("0.0001"))
        competencia.itens.append(ItemMedicao(
            item_id=item_id, ordem=item.ordem, descricao=f"{item.descricao} (diferença de repactuação)", tipo=item.tipo, calcula_pro_rata=item.calcula_pro_rata,
            valor_unitario=unitario, fator_meses=Decimal(len(r.medidas)), quantidade_prevista=total_medido, quantidade_medida=total_medido))
    checklist = checklist_ativo(contrato)
    if checklist:
        copiar_checklist(competencia, checklist)
    contrato.competencias.append(competencia)
    return competencia


def finalizar(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa o apostilamento assinado e aplica a repactuação: preços dos itens vinculados, medições futuras, diferença ou crédito do retroativo."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    if repactuacao.cadastro_concluido_em is None:
        raise ErroRegraContrato("Finalize o cadastro dos itens da repactuação.")
    if not repactuacao.memorias or repactuacao.memorias[-1].hash_origem != _hash(contrato, repactuacao):
        raise ErroRegraContrato("Gere a memória de cálculo atualizada antes de finalizar.")
    if any(d.obrigatorio and not d.anexo_id for d in repactuacao.documentos):
        raise ErroRegraContrato("Anexe os documentos obrigatórios do checklist antes de finalizar.")
    if repactuacao.consolidado_anexo_id is None:
        raise ErroRegraContrato("Gere o documento consolidado antes de finalizar.")
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-repactuacao-apostilamento", autor.id, contrato_id=contrato.id)
    sessao.flush()
    repactuacao.apostilamento_anexo_id = anexo.id
    # A diferença das medidas é calculada antes de mudar a situação (depois, `preco_em` já enxerga a repactuação)
    r = retroativo(contrato, repactuacao)
    deltas = {i.item_id: i.diferenca for i in repactuacao.itens}
    # O preço do cadastro é o de hoje: recebe a diferença se a repactuação já vale (ou valerá) na vigência atual
    for item in contrato.itens:
        if item.id in deltas:
            item.valor_unitario = item.valor_unitario + deltas[item.id]
    repactuacao.situacao = "concluido"
    sessao.flush()
    for competencia in _nao_medidas(contrato, repactuacao):
        sincronizar_competencia(contrato, competencia)
    repactuacao.diferenca_retroativa = calculos.arredondar(r.total)
    diferenca = _competencia_diferenca(contrato, repactuacao, r)
    if repactuacao.diferenca_retroativa < 0:
        registrar_credito_reajuste(sessao, contrato, None, -repactuacao.diferenca_retroativa, repactuacao=repactuacao)
    ultima = vigencias(contrato)[-1]
    if contrato.valor_global_reajustado is not None or repactuacao.efeito <= ultima.fim:
        contrato.valor_global_reajustado = valores.valor_global_vigencia(contrato, ultima)
    repactuacao.concluido_em = agora_utc()
    contrato.versao += 1
    auditar(sessao, autor.login, "contrato.repactuacao.finalizar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"data_efeito": repactuacao.efeito, "diferenca_retroativa": repactuacao.diferenca_retroativa,
                   "competencia_diferenca": diferenca.identificador if diferenca else None,
                   "itens": {str(k): str(v) for k, v in deltas.items()}})
    from app.services.contratos import avisos
    avisos.alteracao_concluida(sessao, contrato, "repactuacao", repactuacao.id, f"repactuação (CCT {repactuacao.data_base_cct:%m/%Y}) aplicada a partir de "
                               f"{repactuacao.efeito:%d/%m/%Y}", autor)
    sessao.commit()


def cancelar(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, autor: Usuario) -> None:
    """Cancela a repactuação em elaboração (nada muda nos preços; a CCT continua nos Documentos importantes)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    repactuacao = _em_andamento(sessao, contrato, repactuacao_id)
    repactuacao.situacao, repactuacao.cancelado_em = "cancelado", agora_utc()
    auditar(sessao, autor.login, "contrato.repactuacao.cancelar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
    sessao.commit()


def arquivo(sessao: Session, contrato_id: uuid.UUID, repactuacao_id: uuid.UUID, anexo_id: uuid.UUID):
    """Baixa um arquivo da repactuação; só aceita anexos que pertencem a ela."""
    contrato = obter_contrato(sessao, contrato_id)
    repactuacao = next((r for r in _carregar(sessao, contrato) if r.id == repactuacao_id), None)
    if repactuacao is None:
        raise RegistroNaoEncontrado("Repactuação")
    permitidos = ({repactuacao.cct_anexo_id, repactuacao.consolidado_anexo_id, repactuacao.apostilamento_anexo_id}
                  | {m.pdf_anexo_id for m in repactuacao.memorias} | {m.xlsx_anexo_id for m in repactuacao.memorias}
                  | {d.anexo_id for d in repactuacao.documentos if d.anexo_id})
    if anexo_id not in permitidos:
        raise RegistroNaoEncontrado("Arquivo")
    return servico_anexos.resposta_download(sessao.get(Anexo, anexo_id))
