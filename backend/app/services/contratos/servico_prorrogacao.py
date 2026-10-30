# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de prorrogação da vigência, parecer e termo aditivo.
"""Prorrogação da vigência (tela 4): rascunho, parecer opcional, ciências opcionais, registro e desfazer.

Fluxo: a equipe monta um rascunho (prazo, limites dos itens sob demanda e, se quiser, o parecer),
pode registrar ciências no parecer e, com o Termo Aditivo assinado, registra a prorrogação. O
registro cria a nova vigência, anexa o termo aos documentos importantes (024, 025...) e grava a
previsão sob demanda da nova vigência. Só a última prorrogação pode ser desfeita.
"""

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import (
    ApontamentoPrevisao,
    CienciaProrrogacao,
    Contrato,
    DocumentoContrato,
    DocumentoProrrogacao,
    LimitePrevisao,
    ModeloGlobal,
    PrevisaoVigencia,
    ProcessoProrrogacao,
    Prorrogacao,
)
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import (
    CAMPOS_PARECER,
    DocumentoProrrogacaoLeitura,
    GravacaoDadosMinuta,
    GravacaoEnquadramento,
    GravacaoPosAssinatura,
    GravacaoProrrogacao,
    LeituraEnquadramento,
    LeituraMemoriaVersao,
    LeituraMinuta,
    LeituraMinutas,
    LeituraProcessoProrrogacao,
    LeituraProrrogacao,
    PlanoItemLeitura,
    ResumoMemoriaProrrogacao,
)
from app.schemas.contratos.execucao import LeituraArquivo, LeituraCiencia
from app.services import calendario_util, servico_anexos
from app.services.contratos import calculos, memoria_prorrogacao, prorrogacao_documentos, prorrogacao_mascara, servico_enquadramento, servico_pos_assinatura, valores
from app.services.contratos.documentos_execucao import PAPEIS, data_hora, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_configuracao_execucao import checklist_ativo
from app.services.contratos.servico_contratos import designacoes_vigentes, eh_administrador, exigir_edicao, papel_para_ciencia, pode_dar_ciencia, obter_contrato, pode_editar, vigencias
from app.services.documentos.pdf import DocumentoPdf
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
# Os termos aditivos entram no catálogo de documentos a partir do código 024
PRIMEIRO_CODIGO_TERMO = 24
# Títulos das seções do parecer no PDF
ROTULOS_PARECER = {
    "avaliacao_geral": "Avaliação geral da execução contratual",
    "resumo_qualidade": "Resumo executivo das avaliações de qualidade",
    "historico_ocorrencias": "Histórico de ocorrências",
    "reclamacoes": "Reclamações de servidores e tratativas",
    "atendimento_chamados": "Atendimento de chamados e obrigações",
    "parecer": "Parecer para prorrogação contratual",
}


def _arquivo(anexo: Anexo | None) -> LeituraArquivo | None:
    """Converte um anexo no formato de leitura da API (ou None)."""
    return LeituraArquivo(anexo_id=anexo.id, nome=anexo.nome_original, tamanho=anexo.tamanho, enviado_em=anexo.criado_em) if anexo else None


def _rascunho(sessao: Session, contrato: Contrato) -> ProcessoProrrogacao | None:
    """Rascunho em andamento do contrato (no máximo um), com as ciências carregadas."""
    return sessao.scalar(
        select(ProcessoProrrogacao)
        .where(ProcessoProrrogacao.contrato_id == contrato.id, ProcessoProrrogacao.situacao == "rascunho")
        .options(selectinload(ProcessoProrrogacao.ciencias), selectinload(ProcessoProrrogacao.memorias), selectinload(ProcessoProrrogacao.documentos))
    )


def meses_disponiveis(contrato: Contrato) -> int:
    """Meses que ainda cabem até a vigência máxima (máxima − inicial − prorrogações já feitas)."""
    return contrato.vigencia_maxima_meses - contrato.vigencia_inicial_meses - sum(p.meses for p in contrato.prorrogacoes)


def nova_vigencia(contrato: Contrato, meses: int | None) -> tuple[date, date | None]:
    """(início, fim) da nova vigência: começa no dia seguinte ao fim atual; sem prazo, o fim fica vazio."""
    return memoria_prorrogacao.nova_vigencia(contrato, meses)


def _saldo_remanescente(contrato: Contrato, item) -> Decimal:
    """Quanto sobrou do item sob demanda na vigência atual (nunca mais que a quantidade original)."""
    atual = vigencias(contrato)[-1]
    limite = valores.limite_na_vigencia(contrato, item, atual.sequencia)
    return min(item.quantidade_total, max(ZERO, limite - valores.executado_na_vigencia(contrato, item, atual.sequencia)))


def _limite_pela_regra(contrato: Contrato, item, regra: str, manual: Decimal | None) -> Decimal:
    """Limite do item na nova vigência conforme a regra escolhida (saldo, repetir o inicial ou manual)."""
    if regra == "saldo_remanescente":
        return _saldo_remanescente(contrato, item)
    if regra == "repetir_inicial":
        return item.quantidade_total
    return manual if manual is not None else ZERO


def _possui_parecer(processo) -> bool:
    """Indica se algum campo do parecer foi preenchido."""
    return any((getattr(processo, c) or "").strip() for c in CAMPOS_PARECER)


def consultar(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> LeituraProcessoProrrogacao:
    """Dados da tela de prorrogação (com ou sem rascunho salvo)."""
    contrato = obter_contrato(sessao, contrato_id)
    processo = _rascunho(sessao, contrato)
    meses = processo.meses if processo else None
    inicio, fim = nova_vigencia(contrato, meses)
    # Meses da nova vigência (só existem depois de escolhido o prazo)
    competencias = [m.competencia for m in calculos.meses_da_vigencia(calculos.Vigencia(0, inicio, fim))] if fim else []
    regra = processo.regra_sob_demanda if processo else "saldo_remanescente"
    plano = {p["item_id"]: p for p in (processo.plano_sob_demanda if processo else [])}
    itens = []
    # Para cada item sob demanda: o limite salvo no rascunho ou o calculado pela regra
    for item in (i for i in contrato.itens if i.tipo == "sob_demanda"):
        salvo = plano.get(str(item.id), {})
        limite = Decimal(salvo["limite"]) if "limite" in salvo else _limite_pela_regra(contrato, item, regra, None)
        apontados = {c.isoformat(): Decimal(salvo.get("apontamentos", {}).get(c.isoformat(), "0")) for c in competencias}
        itens.append(
            PlanoItemLeitura(
                item_id=item.id, ordem=item.ordem, descricao=item.descricao, quantidade_original=item.quantidade_total,
                saldo_remanescente=_saldo_remanescente(contrato, item), limite=limite, apontamentos=apontados,
                saldo=limite - sum(apontados.values(), ZERO),
            )
        )
    atual = vigencias(contrato)[-1]
    textos = {c: getattr(processo, c) if processo else "" for c in CAMPOS_PARECER}
    memoria = memoria_prorrogacao.resumo(contrato, processo)
    documentos = processo.documentos if processo else []
    ids_inclusao = {d.incluido_por_id for d in documentos if d.incluido_por_id}
    quem_incluiu = {u.id: u.nome_completo or u.login for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids_inclusao)))} if ids_inclusao else {}
    return LeituraProcessoProrrogacao(
        id=processo.id if processo else None, vigencia_atual_inicio=atual.inicio, vigencia_atual_fim=atual.fim, meses=meses,
        nova_vigencia_inicio=inicio, nova_vigencia_fim=fim, meses_disponiveis=meses_disponiveis(contrato),
        meses_nova_vigencia=competencias, regra_sob_demanda=regra, itens_sob_demanda=itens, **textos,
        possui_parecer=bool(processo and _possui_parecer(processo)),
        ciencias=[LeituraCiencia(usuario_id=c.usuario_id, nome=c.nome, papel=c.papel, registrada_em=c.registrada_em) for c in (processo.ciencias if processo else [])],
        relatorio=_arquivo(processo.relatorio_anexo) if processo else None,
        exige_checklist_ativo=bool(contrato.competencias) and checklist_ativo(contrato) is None,
        pode_editar=pode_editar(sessao, contrato, usuario), integra_equipe=pode_dar_ciencia(sessao, contrato, usuario),
        memoria=ResumoMemoriaProrrogacao(**memoria) if memoria else None,
        memorias=[LeituraMemoriaVersao(versao=m.versao, criada_em=m.criado_em, pdf=_arquivo(m.pdf_anexo), xlsx=_arquivo(m.xlsx_anexo)) for m in (processo.memorias if processo else [])],
        memoria_atualizada=bool(processo and memoria_prorrogacao.memoria_atualizada(contrato, processo)),
        checklist=[
            DocumentoProrrogacaoLeitura(id=d.id, ordem=d.ordem, nome=d.nome, observacao=d.observacao, obrigatorio=d.obrigatorio, arquivo=_arquivo(d.anexo),
                                        incluido_no_processo=d.incluido_no_processo, incluido_por_nome=quem_incluiu.get(d.incluido_por_id), incluido_em=d.incluido_em)
            for d in sorted(documentos, key=lambda d: (d.incluido_no_processo, d.ordem))
        ],
        obrigatorios_pendentes=sum(1 for d in documentos if d.obrigatorio and not d.anexo_id),
    )


def _copiar_checklist(sessao: Session, processo: ProcessoProrrogacao) -> None:
    """Ponto de partida do checklist: copia os documentos do modelo "Checklist Prorrogação" ativo (o mais recente), se houver.

    Só copia num processo ainda sem documentos (os do modelo não saem; sem nenhum, o processo nunca recebeu a cópia)."""
    if processo.documentos:
        return
    modelo = sessao.scalar(select(ModeloGlobal).where(ModeloGlobal.tipo == "checklist_prorrogacao", ModeloGlobal.ativo.is_(True))
                           .order_by(ModeloGlobal.atualizado_em.desc()))
    if modelo is None:
        return
    for ordem, item in enumerate((modelo.conteudo or {}).get("itens", []), start=1):
        processo.documentos.append(DocumentoProrrogacao(ordem=ordem, nome=item.get("nome", "")[:500], observacao=(item.get("observacao") or "")[:1000],
                                                        obrigatorio=bool(item.get("obrigatorio", True))))


def _validar_plano(contrato: Contrato, dados: GravacaoProrrogacao) -> list[dict]:
    """Valida o plano dos itens sob demanda e o converte para o formato gravado em JSON."""
    itens = {i.id: i for i in contrato.itens if i.tipo == "sob_demanda"}
    inicio, fim = nova_vigencia(contrato, dados.meses)
    competencias = {m.competencia for m in calculos.meses_da_vigencia(calculos.Vigencia(0, inicio, fim))} if fim else set()
    plano = []
    for linha in dados.plano_sob_demanda:
        item = itens.get(linha.item_id)
        if item is None:
            raise ErroRegraContrato("O plano da prorrogação só aceita itens sob demanda do contrato.")
        # Na regra manual vale o limite digitado; nas outras, o calculado
        limite = linha.limite if dados.regra_sob_demanda == "manual" else _limite_pela_regra(contrato, item, dados.regra_sob_demanda, None)
        # A prorrogação não amplia o objeto: para isso existe o aditamento
        if limite > item.quantidade_total:
            raise ErroRegraContrato(f"O limite de \"{item.descricao}\" não pode passar da quantidade original. Para ampliar o objeto, registre aditamento.")
        apontamentos = {}
        # Apontamentos só em meses da nova vigência; valores zerados são descartados
        for mes, quantidade_mes in linha.apontamentos.items():
            mes = calculos.primeiro_dia(mes)
            if mes not in competencias:
                raise ErroRegraContrato(f"O mês {mes:%m/%Y} não pertence à nova vigência.")
            if quantidade_mes > 0:
                apontamentos[mes.isoformat()] = str(quantidade_mes)
        if sum((Decimal(q) for q in apontamentos.values()), ZERO) > limite:
            raise ErroRegraContrato(f"Os apontamentos de \"{item.descricao}\" passam do limite da nova vigência.")
        plano.append({"item_id": str(item.id), "limite": str(limite), "apontamentos": apontamentos})
    return plano


def salvar(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoProrrogacao, autor: Usuario) -> None:
    """Grava o rascunho da prorrogação (cria se ainda não existir)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if dados.meses and dados.meses > meses_disponiveis(contrato):
        raise ErroRegraContrato(f"A prorrogação ultrapassa a vigência máxima: restam {meses_disponiveis(contrato)} mês(es).")
    processo = _rascunho(sessao, contrato)
    if processo is None:
        processo = ProcessoProrrogacao(contrato_id=contrato.id, criado_por_id=autor.id)
        sessao.add(processo)
    # Compara antes de aplicar, para saber se o texto do parecer mudou (campo não enviado = mantém o gravado)
    parecer_mudou = any(getattr(dados, c) is not None and (getattr(processo, c) or "") != getattr(dados, c) for c in CAMPOS_PARECER)
    processo.meses, processo.regra_sob_demanda = dados.meses, dados.regra_sob_demanda
    processo.plano_sob_demanda = _validar_plano(contrato, dados)
    if dados.calculo_mes_quebrado is not None:
        processo.calculo_mes_quebrado = dados.calculo_mes_quebrado
    for campo in CAMPOS_PARECER:
        if getattr(dados, campo) is not None:
            setattr(processo, campo, getattr(dados, campo))
    _copiar_checklist(sessao, processo)
    # Editar o parecer depois das ciências as invalida (a tela confirma antes)
    removidas = 0
    if parecer_mudou and processo.ciencias:
        removidas = len(processo.ciencias)
        processo.ciencias.clear()
        processo.relatorio_anexo_id = None
    auditar(sessao, autor.login, "contrato.prorrogacao.salvar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"meses": dados.meses, "ciencias_removidas": removidas})
    sessao.commit()


def _rascunho_ou_novo(sessao: Session, contrato: Contrato, autor: Usuario) -> ProcessoProrrogacao:
    """Rascunho em andamento; se ainda não houver, cria um vazio (as minutas podem ser preparadas antes de escolher o prazo)."""
    processo = _rascunho(sessao, contrato)
    if processo is None:
        processo = ProcessoProrrogacao(contrato_id=contrato.id, criado_por_id=autor.id)
        sessao.add(processo)
        _copiar_checklist(sessao, processo)
        sessao.flush()
    return processo


# ---------------------------------------------------------------------------------------------
# Memória de cálculo e checklist da prorrogação
# ---------------------------------------------------------------------------------------------

def gerar_memoria(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> None:
    """Gera o PDF e o XLSX da memória de cálculo (nova versão só se os dados mudaram)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    processo = _rascunho(sessao, contrato)
    if processo is None:
        raise ErroRegraContrato("Informe e salve o prazo da prorrogação antes de gerar a memória de cálculo.")
    memoria_prorrogacao.gerar_arquivos(sessao, contrato, processo, autor)
    auditar(sessao, autor.login, "contrato.prorrogacao.memoria", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"versao": len(processo.memorias)})
    sessao.commit()


def _documento_do_rascunho(sessao: Session, contrato: Contrato, documento_id: uuid.UUID) -> tuple[ProcessoProrrogacao, DocumentoProrrogacao]:
    processo = _rascunho(sessao, contrato)
    documento = next((d for d in (processo.documentos if processo else []) if d.id == documento_id), None)
    if documento is None:
        raise RegistroNaoEncontrado("Documento do checklist")
    return processo, documento


def anexar_documento(sessao: Session, contrato_id: uuid.UUID, documento_id: uuid.UUID, arquivo: BinaryIO, nome: str, autor: Usuario) -> None:
    """Anexa (ou substitui) o PDF de um documento do checklist da prorrogação."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    _, documento = _documento_do_rascunho(sessao, contrato, documento_id)
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome, "contrato-prorrogacao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    auditar(sessao, autor.login, "contrato.prorrogacao.checklist.enviar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


def incluir_documento(sessao: Session, contrato_id: uuid.UUID, nome_documento: str, descricao: str, arquivo: BinaryIO, nome_arquivo: str, autor: Usuario) -> None:
    """Inclui no checklist da prorrogação um documento fora do modelo (nome, descrição e PDF): nunca obrigatório."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    nome_documento = " ".join((nome_documento or "").split())
    if not nome_documento:
        raise ErroRegraContrato("Informe o nome do documento.")
    processo = _rascunho_ou_novo(sessao, contrato, autor)
    documento = DocumentoProrrogacao(
        ordem=max((d.ordem for d in processo.documentos), default=0) + 1, nome=nome_documento[:500], observacao=(descricao or "").strip()[:1000],
        obrigatorio=False, incluido_no_processo=True, incluido_por_id=autor.id, incluido_em=agora_utc(),
    )
    documento.anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome_arquivo, "contrato-prorrogacao-checklist", autor.id, contrato_id=contrato.id)
    documento.enviado_em, documento.enviado_por_id = agora_utc(), autor.id
    processo.documentos.append(documento)
    auditar(sessao, autor.login, "contrato.prorrogacao.checklist.incluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


def excluir_documento(sessao: Session, contrato_id: uuid.UUID, documento_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui um documento incluído durante o processo (os do modelo ficam)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    processo, documento = _documento_do_rascunho(sessao, contrato, documento_id)
    if not documento.incluido_no_processo:
        raise ErroRegraContrato("Só os documentos incluídos durante o processo podem ser excluídos; os do checklist padrão ficam.")
    if documento.anexo is not None:
        servico_anexos.descartar(documento.anexo)
    processo.documentos.remove(documento)
    auditar(sessao, autor.login, "contrato.prorrogacao.checklist.excluir", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"documento": documento.nome})
    sessao.commit()


def minutas(sessao: Session, contrato_id: uuid.UUID) -> LeituraMinutas:
    """Documentos da prorrogação (minutas e despachos) e os dados que os completam."""
    contrato = obter_contrato(sessao, contrato_id)
    return prorrogacao_documentos.panorama(sessao, contrato, _rascunho(sessao, contrato))


def minuta(sessao: Session, contrato_id: uuid.UUID, variante: str) -> LeituraMinuta:
    """Texto preenchido de um documento, pronto para copiar para o SEI."""
    contrato = obter_contrato(sessao, contrato_id)
    return prorrogacao_documentos.gerar(sessao, contrato, _rascunho(sessao, contrato), variante)


def salvar_dados_minuta(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoDadosMinuta, autor: Usuario) -> LeituraMinutas:
    """Grava o que a equipe digitou para completar as minutas (substitui o anterior; texto vazio apaga o dado)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    invalidos = [n for n in dados.dados if n.lower() not in prorrogacao_mascara.PLACEHOLDERS or n.lower() in prorrogacao_mascara.CONDICIONAIS]
    if invalidos:
        raise ErroRegraContrato("Dado desconhecido nas minutas: " + ", ".join(invalidos) + ".")
    processo = _rascunho_ou_novo(sessao, contrato, autor)
    novos = {n.lower(): v.strip() for n, v in dados.dados.items() if v.strip()}
    processo.dados_minuta = novos
    auditar(sessao, autor.login, "contrato.prorrogacao.minutas", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"campos": sorted(novos)})
    sessao.commit()
    return prorrogacao_documentos.panorama(sessao, contrato, processo)


def enquadramento(sessao: Session, contrato_id: uuid.UUID) -> LeituraEnquadramento:
    """Checklist do Parecer Referencial da prorrogação em andamento."""
    contrato = obter_contrato(sessao, contrato_id)
    return servico_enquadramento.consultar(sessao, contrato, _rascunho(sessao, contrato))


def salvar_enquadramento(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoEnquadramento, autor: Usuario) -> LeituraEnquadramento:
    """Grava as respostas do checklist do Parecer Referencial."""
    return servico_enquadramento.salvar(sessao, contrato_id, dados, autor)


def planilha_enquadramento(sessao: Session, contrato_id: uuid.UUID) -> tuple[bytes, str]:
    """Checklist em XLSX (Modelo 6) e o nome sugerido do arquivo."""
    contrato = obter_contrato(sessao, contrato_id)
    return servico_enquadramento.planilha(sessao, contrato, _rascunho(sessao, contrato)), f"checklist-parecer-referencial-{contrato.numero.replace('/', '-')}.xlsx"


def atualizar_pos_assinatura(sessao: Session, contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, dados: GravacaoPosAssinatura, autor: Usuario) -> None:
    """Grava as datas de PNCP, DOE, garantia e Contratos.gov de uma prorrogação registrada."""
    servico_pos_assinatura.atualizar(sessao, contrato_id, prorrogacao_id, dados, autor)


def registrar_ciencia(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> None:
    """Registra a ciência (opcional) de um integrante da equipe no parecer."""
    contrato = obter_contrato(sessao, contrato_id)
    processo = _rascunho(sessao, contrato)
    if processo is None or not _possui_parecer(processo):
        raise ErroRegraContrato("Preencha e salve o parecer antes de registrar ciência.")
    papel = papel_para_ciencia(sessao, contrato, autor)
    if papel is None:
        raise ErroRegraContrato("Somente integrantes da equipe de gestão e fiscalização registram ciência.")
    # Uma ciência por pessoa; a nova ciência invalida o PDF do parecer gerado antes
    if not any(c.usuario_id == autor.id for c in processo.ciencias):
        processo.ciencias.append(CienciaProrrogacao(usuario_id=autor.id, nome=autor.nome_completo or autor.login, papel=papel, registrada_em=agora_utc()))
        processo.relatorio_anexo_id = None
        auditar(sessao, autor.login, "contrato.prorrogacao.ciencia", f"Contrato {contrato.numero}", autor_id=autor.id,
                alvo_tipo="contrato", alvo_id=contrato.id, dados={"papel": papel})
    sessao.commit()


def _pdf_parecer(contrato: Contrato, processo: ProcessoProrrogacao, autor: str) -> bytes:
    """Monta o PDF do parecer: identificação, seções preenchidas, itens sob demanda e ciências."""
    inicio, fim = nova_vigencia(contrato, processo.meses)
    atual = vigencias(contrato)[-1]
    documento = DocumentoPdf("Parecer para prorrogação contratual", f"Contrato {contrato.numero}", autor=autor)
    documento.secao("Identificação do objeto").campos([
        ("Contrato", contrato.numero), ("Contratada", contrato.empresa.razao_social),
        ("Período de avaliação", f"{atual.inicio:%d/%m/%Y} a {atual.fim:%d/%m/%Y}"),
        ("Prorrogação", f"{processo.meses or '—'} mês(es)" + (f" · {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if fim else "")),
        ("Objeto", contrato.objeto),
    ])
    # Só as seções preenchidas entram no documento
    for campo in CAMPOS_PARECER:
        texto = (getattr(processo, campo) or "").strip()
        if texto:
            documento.secao(ROTULOS_PARECER[campo]).paragrafo(texto)
    plano = processo.plano_sob_demanda or []
    if plano:
        itens = {str(i.id): i for i in contrato.itens}
        documento.secao("Itens sob demanda na nova vigência").tabela(
            ["Item", "Qtd. original", "Limite da nova vigência"],
            [[itens[p["item_id"]].descricao, quantidade(itens[p["item_id"]].quantidade_total), quantidade(Decimal(p["limite"]))] for p in plano if p["item_id"] in itens],
            larguras=[5, 2, 2],
        )
    documento.secao("Ciências registradas").tabela(
        ["Nome", "Papel", "Ciência em"], [[c.nome, PAPEIS.get(c.papel, c.papel), data_hora(c.registrada_em)] for c in processo.ciencias], larguras=[4, 3, 2]
    )
    return documento.gerar()


def _hash_parecer(processo: ProcessoProrrogacao) -> str:
    """Hash dos dados do parecer, para não gerar um PDF novo quando nada mudou."""
    origem = {c: getattr(processo, c) for c in CAMPOS_PARECER} | {"meses": processo.meses, "ciencias": [c.usuario_id for c in processo.ciencias]}
    return hashlib.sha256(json.dumps(origem, sort_keys=True, default=str).encode()).hexdigest()


def emitir_parecer(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao, autor: Usuario) -> Anexo | None:
    """PDF do parecer só quando algum campo está preenchido; reaproveita o último se nada mudou."""
    if not _possui_parecer(processo):
        return None
    origem = _hash_parecer(processo)
    if processo.relatorio_anexo_id and processo.relatorio_hash == origem:
        return sessao.get(Anexo, processo.relatorio_anexo_id)
    conteudo = _pdf_parecer(contrato, processo, autor.nome_completo or autor.login)
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, f"parecer-prorrogacao-{contrato.numero_arquivo}.pdf",
                                              "contrato-prorrogacao-parecer", autor.id, contrato_id=contrato.id)
    sessao.flush()
    processo.relatorio_anexo_id, processo.relatorio_hash = anexo.id, origem
    return anexo


def gerar_parecer(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> None:
    """Gera (ou reaproveita) o PDF do parecer a pedido do usuário."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    processo = _rascunho(sessao, contrato)
    if processo is None or emitir_parecer(sessao, contrato, processo, autor) is None:
        raise ErroRegraContrato("Nenhum campo do parecer foi preenchido: a prorrogação será registrada sem relatório.")
    sessao.commit()


def descartar_rascunho(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> None:
    """Descarta o rascunho sem alterar o contrato."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    processo = _rascunho(sessao, contrato)
    if processo:
        sessao.delete(processo)
        auditar(sessao, autor.login, "contrato.prorrogacao.descartar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id)
        sessao.commit()


def registrar(sessao: Session, contrato_id: uuid.UUID, assinada_em: date, numero_termo: str, termo: tuple[BinaryIO, str], autor: Usuario) -> Prorrogacao:
    """Cria a nova vigência, anexa o termo aos documentos (024+) e grava a previsão sob demanda da vigência."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    processo = _rascunho(sessao, contrato)
    if processo is None or not processo.meses:
        raise ErroRegraContrato("Informe e salve o prazo da prorrogação antes de registrá-la.")
    if processo.meses > meses_disponiveis(contrato):
        raise ErroRegraContrato(f"A prorrogação ultrapassa a vigência máxima: restam {meses_disponiveis(contrato)} mês(es).")
    if contrato.competencias and checklist_ativo(contrato) is None:
        raise ErroRegraContrato("O contrato já tem competências geradas: ative um checklist antes de prorrogar.")
    memoria = memoria_prorrogacao.resumo(contrato, processo)
    if memoria and memoria["precisa_escolher"]:
        raise ErroRegraContrato("Escolha como calcular os meses quebrados (pro rata ou integral) antes de registrar.")
    if not memoria_prorrogacao.memoria_atualizada(contrato, processo):
        raise ErroRegraContrato("Gere a memória de cálculo da prorrogação (com os dados atuais) antes de registrar.")
    pendentes = [d.nome for d in processo.documentos if d.obrigatorio and not d.anexo_id]
    if pendentes:
        raise ErroRegraContrato("Anexe os documentos obrigatórios do checklist: " + "; ".join(pendentes) + ".")
    # Emite o parecer final (se houver) e guarda o termo como documento importante com o próximo código
    relatorio = emitir_parecer(sessao, contrato, processo, autor)
    inicio, fim = nova_vigencia(contrato, processo.meses)
    anexo = servico_anexos.guardar_pdf(sessao, termo[0], termo[1], "contrato-prorrogacao-termo", autor.id, contrato_id=contrato.id)
    codigo = max([d.codigo_tipo for d in contrato.documentos] + [PRIMEIRO_CODIGO_TERMO - 1]) + 1
    numero = numero_termo.strip()
    contrato.documentos.append(
        DocumentoContrato(codigo_tipo=codigo, titulo=f"Termo Aditivo{' nº ' + numero if numero else ''} — prorrogação de {processo.meses} mês(es)",
                          anexo=anexo, enviado_em=agora_utc(), enviado_por_id=autor.id)
    )
    # Registro imutável da prorrogação (guarda o fim anterior, para poder desfazer)
    prorrogacao = Prorrogacao(
        meses=processo.meses, assinada_em=assinada_em, numero_termo=numero, fim_anterior=contrato.data_fim, data_inicio=inicio, data_fim=fim,
        anexo=anexo, codigo_documento=codigo, relatorio_anexo_id=relatorio.id if relatorio else None, criado_por_id=autor.id,
        enquadramento=servico_enquadramento.fotografia(sessao, contrato, processo, assinada_em), pncp_prazo_ate=servico_pos_assinatura.prazo_pncp(sessao, contrato, assinada_em),
    )
    contrato.prorrogacoes.append(prorrogacao)
    # Número da nova vigência: retroativas + original + quantidade de prorrogações
    sequencia = len(contrato.vigencias_retroativas) + len(contrato.prorrogacoes) + 1
    sob_demanda = processo.plano_sob_demanda or []
    # Previsão da nova vigência, já selada, com os limites e apontamentos planejados no rascunho
    if any(i.tipo == "sob_demanda" for i in contrato.itens):
        previsao = PrevisaoVigencia(sequencia_vigencia=sequencia, salva=True, salva_em=agora_utc(), salva_por_id=autor.id)
        plano = {p["item_id"]: p for p in sob_demanda}
        for item in (i for i in contrato.itens if i.tipo == "sob_demanda"):
            linha = plano.get(str(item.id))
            limite = Decimal(linha["limite"]) if linha else _limite_pela_regra(contrato, item, processo.regra_sob_demanda, None)
            previsao.limites.append(LimitePrevisao(item_id=item.id, quantidade_total=limite))
            for mes, quantidade_mes in (linha or {}).get("apontamentos", {}).items():
                previsao.apontamentos.append(ApontamentoPrevisao(item_id=item.id, competencia=date.fromisoformat(mes), quantidade=Decimal(quantidade_mes)))
        contrato.previsoes.append(previsao)
    # O contrato passa a terminar no fim da nova vigência
    contrato.data_fim = fim
    # O valor reajustado era a fotografia da vigência anterior; a nova usa os preços atuais
    contrato.valor_global_reajustado = None
    contrato.versao += 1
    processo.situacao = "concluido"
    sessao.flush()
    processo.prorrogacao_id = prorrogacao.id
    auditar(sessao, autor.login, "contrato.prorrogacao.registrar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"campos": {"data_fim": {"de": prorrogacao.fim_anterior, "para": fim}}, "meses": processo.meses,
                                        "termo": numero, "com_parecer": relatorio is not None,
                                        "precisa_analise_juridica": prorrogacao.enquadramento["precisa_juridico"]})
    from app.services.contratos import avisos
    avisos.alteracao_concluida(sessao, contrato, "prorrogacao", prorrogacao.id,
                               f"prorrogação de {processo.meses} meses registrada (vigência até {fim:%d/%m/%Y})", autor)
    sessao.commit()
    return prorrogacao


def listar(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> list[LeituraProrrogacao]:
    """Prorrogações registradas; só a última pode ser desfeita (se as regras permitirem)."""
    contrato = obter_contrato(sessao, contrato_id)
    anexos = {a.id: a for a in sessao.scalars(select(Anexo).where(Anexo.id.in_(
        [p.anexo_id for p in contrato.prorrogacoes] + [p.relatorio_anexo_id for p in contrato.prorrogacoes if p.relatorio_anexo_id])))}
    ultima = contrato.prorrogacoes[-1] if contrato.prorrogacoes else None
    hoje, feriados = date.today(), calendario_util.feriados_cadastrados(sessao)
    return [
        LeituraProrrogacao(
            id=p.id, meses=p.meses, assinada_em=p.assinada_em, numero_termo=p.numero_termo, fim_anterior=p.fim_anterior, data_inicio=p.data_inicio,
            data_fim=p.data_fim, codigo_documento=p.codigo_documento, precisa_analise_juridica=bool((p.enquadramento or {}).get("precisa_juridico")),
            pncp_prazo_ate=p.pncp_prazo_ate, pncp_publicado_em=p.pncp_publicado_em, pncp_numero=p.pncp_numero, situacao_pncp=situacao[0], dias_uteis_pncp=situacao[1],
            doe_publicado_em=p.doe_publicado_em, exige_garantia=contrato.exige_garantia, garantia_comprovada_em=p.garantia_comprovada_em,
            garantia_enviada_dof_em=p.garantia_enviada_dof_em, garantia_pendente=contrato.exige_garantia and p.garantia_comprovada_em is None,
            dados_garantia=p.dados_garantia or {}, contratos_gov_atualizado_em=p.contratos_gov_atualizado_em, termo=_arquivo(anexos.get(p.anexo_id)),
            relatorio=_arquivo(anexos.get(p.relatorio_anexo_id)), pode_desfazer=p is ultima and pode_desfazer(sessao, contrato, p, usuario)[0],
        )
        for p, situacao in ((p, servico_pos_assinatura.situacao_pncp(sessao, p, hoje, feriados)) for p in contrato.prorrogacoes)
    ]


def pode_desfazer(sessao: Session, contrato: Contrato, prorrogacao: Prorrogacao, usuario: Usuario) -> tuple[bool, str]:
    """(pode desfazer?, motivo) para a prorrogação informada."""
    if not pode_editar(sessao, contrato, usuario):
        return False, "Sem permissão para alterar o contrato."
    sequencia = len(contrato.vigencias_retroativas) + contrato.prorrogacoes.index(prorrogacao) + 2
    # Competências geradas na vigência criada por esta prorrogação
    competencias = [c for c in contrato.competencias if c.sequencia_vigencia == sequencia]
    if any(c.medicao_iniciada_em or c.etapa_atual != "medicao" for c in competencias):
        return False, "Há medição registrada na nova vigência. Reabra ou desfaça a execução antes."
    if any(r.sequencia_vigencia == sequencia and r.situacao != "cancelado" for r in contrato.reajustes) or any(
        a.sequencia_vigencia == sequencia and a.situacao != "cancelada" for a in contrato.alteracoes
    ):
        return False, "Há reajuste ou aditamento/supressão na nova vigência. Cancele-os antes."
    return True, ""


def desfazer(sessao: Session, contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, autor: Usuario) -> None:
    """Desfaz a última prorrogação: apaga a vigência criada e devolve o fim anterior ao contrato."""
    contrato = obter_contrato(sessao, contrato_id)
    prorrogacao = next((p for p in contrato.prorrogacoes if p.id == prorrogacao_id), None)
    if prorrogacao is None:
        raise RegistroNaoEncontrado("Prorrogação")
    if prorrogacao is not contrato.prorrogacoes[-1]:
        raise ErroRegraContrato("Somente a prorrogação mais recente pode ser desfeita.")
    permitido, motivo = pode_desfazer(sessao, contrato, prorrogacao, autor)
    if not permitido:
        raise ErroRegraContrato(motivo)
    sequencia = len(contrato.vigencias_retroativas) + len(contrato.prorrogacoes) + 1
    # Remove competências e previsão da vigência desfeita, e o termo dos documentos importantes
    for competencia in [c for c in contrato.competencias if c.sequencia_vigencia == sequencia]:
        contrato.competencias.remove(competencia)
    for previsao in [p for p in contrato.previsoes if p.sequencia_vigencia == sequencia]:
        contrato.previsoes.remove(previsao)
    documento = next((d for d in contrato.documentos if d.codigo_tipo == prorrogacao.codigo_documento), None)
    if documento:
        contrato.documentos.remove(documento)
    anexo = sessao.get(Anexo, prorrogacao.anexo_id)
    servico_anexos.descartar(anexo)
    # O rascunho que originou a prorrogação fica marcado como desfeito (histórico)
    processo = sessao.scalar(select(ProcessoProrrogacao).where(ProcessoProrrogacao.prorrogacao_id == prorrogacao.id))
    if processo:
        processo.situacao = "desfeito"
    contrato.data_fim = prorrogacao.fim_anterior
    contrato.versao += 1
    contrato.prorrogacoes.remove(prorrogacao)
    auditar(sessao, autor.login, "contrato.prorrogacao.desfazer", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato",
            alvo_id=contrato.id, dados={"campos": {"data_fim": {"de": prorrogacao.data_fim, "para": prorrogacao.fim_anterior}}, "termo": prorrogacao.numero_termo})
    sessao.commit()


def arquivo(sessao: Session, contrato_id: uuid.UUID, anexo_id: uuid.UUID):
    """Termo aditivo ou parecer de uma prorrogação registrada, ou o parecer do rascunho."""
    contrato = obter_contrato(sessao, contrato_id)
    # Só permite baixar anexos que pertencem às prorrogações deste contrato ou ao rascunho atual
    permitidos = {p.anexo_id for p in contrato.prorrogacoes} | {v.anexo_id for v in contrato.vigencias_retroativas} | {p.relatorio_anexo_id for p in contrato.prorrogacoes if p.relatorio_anexo_id}
    processo = _rascunho(sessao, contrato)
    if processo and processo.relatorio_anexo_id:
        permitidos.add(processo.relatorio_anexo_id)
    # Memórias de cálculo e documentos do checklist dos processos deste contrato (rascunho ou já registrados)
    for p in sessao.scalars(select(ProcessoProrrogacao).where(ProcessoProrrogacao.contrato_id == contrato.id)
                            .options(selectinload(ProcessoProrrogacao.memorias), selectinload(ProcessoProrrogacao.documentos))):
        permitidos |= {a for m in p.memorias for a in (m.pdf_anexo_id, m.xlsx_anexo_id)} | {d.anexo_id for d in p.documentos if d.anexo_id}
    if anexo_id not in permitidos:
        raise RegistroNaoEncontrado("Arquivo")
    return servico_anexos.resposta_download(sessao.get(Anexo, anexo_id))
