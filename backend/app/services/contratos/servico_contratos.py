# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de cadastro, edição, equipe, documentos e histórico do contrato.
"""Contratos: carteira, cadastro, edição, equipe, documentos importantes e histórico por campo.

Também concentra funções usadas pelos outros serviços do módulo: carregar o contrato com tudo
o que os cálculos precisam (`obter_contrato`), conferir quem pode editar (`exigir_edicao`),
montar as vigências e calcular os totais.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import BinaryIO
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select

from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.acl import NivelAcl
from app.models.anexo import Anexo
from app.models.contratos import (
    PAPEIS_EQUIPE,
    AlteracaoQuantidade,
    Checklist,
    Competencia,
    Contrato,
    DesignacaoEquipe,
    DocumentoContrato,
    EmpresaContratada,
    ItemContrato,
    NotaEmpenho,
    PrevisaoVigencia,
    Reajuste,
)
from app.models.usuario import Usuario
from app.schemas.contratos.contratos import (
    AlteracaoCampo,
    DetalheContrato,
    GravacaoContrato,
    GravacaoItem,
    LeituraDocumento,
    LeituraItem,
    LeituraVigencia,
    MarcoLinhaTempo,
    MembroEquipe,
    PaginaContratos,
    PermissoesContrato,
    ProximoNumero,
    ResumoContrato,
)
from app.schemas.contratos.empresas import OpcaoEmpresa
from app.services import servico_acl, servico_anexos
from app.services.contratos import calculos, valores
from app.services.contratos.catalogo_documentos import CATALOGO, POR_CODIGO, nome_download
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.servico_auditoria import auditar, auditar_alteracoes, historico_campos

# Datas "de hoje" seguem o horário de Brasília
FUSO = ZoneInfo("America/Sao_Paulo")
# Slug do módulo na ACL
RECURSO = "contratos"
# Campos do contrato acompanhados pelo histórico "quem alterou, quando, de → para"
CAMPOS_AUDITADOS = (
    "numero", "empresa_id", "apelido", "objeto", "data_inicio", "data_fim", "vigencia_inicial_meses",
    "vigencia_maxima_meses", "periodicidade_meses", "mes_reajuste", "sei_gestao_numero", "sei_gestao_link",
    "sei_execucao_numero", "sei_execucao_link", "situacao_forcada",
)
# Campos do item que não mudam depois de salvo (mudar exigiria excluir e criar outro item)
CAMPOS_ITEM_IMUTAVEIS = ("descricao", "tipo", "calcula_pro_rata")
# Campos do item que podem ser editados a qualquer momento (até a geração das competências)
CAMPOS_ITEM_EDITAVEIS = (
    "codigo_classe", "codigo_natureza_despesa", "codigo_siafisico", "codigo_catmat_catser",
    "quantidade_mensal", "quantidade_total", "valor_unitario",
)


def hoje() -> date:
    """Data civil em São Paulo (as regras de vigência e execução usam o fuso local)."""
    return datetime.now(FUSO).date()


# ---------------------------------------------------------------------------------------------
# Carregamento e permissões
# ---------------------------------------------------------------------------------------------

def opcoes_carga_completa() -> list:
    """Tudo o que os cálculos de vigência, saldo e valor precisam, sem uma consulta por item."""
    # `selectinload` busca cada relacionamento em uma consulta separada para todos os registros de uma vez,
    # evitando o problema de "N+1 consultas" (uma por item, uma por competência...)
    return [
        selectinload(Contrato.itens),
        selectinload(Contrato.equipe),
        selectinload(Contrato.empresa),
        selectinload(Contrato.prorrogacoes),
        selectinload(Contrato.previsoes).selectinload(PrevisaoVigencia.limites),
        selectinload(Contrato.previsoes).selectinload(PrevisaoVigencia.apontamentos),
        selectinload(Contrato.competencias).selectinload(Competencia.itens),
        selectinload(Contrato.reajustes).selectinload(Reajuste.itens),
        selectinload(Contrato.alteracoes).selectinload(AlteracaoQuantidade.itens),
        selectinload(Contrato.notas_empenho).selectinload(NotaEmpenho.movimentos),
        selectinload(Contrato.checklists).selectinload(Checklist.itens),
        selectinload(Contrato.formularios),
    ]


def obter_contrato(sessao: Session, contrato_id: uuid.UUID) -> Contrato:
    """Contrato completo pelo id, ou `RegistroNaoEncontrado` (vira 404)."""
    contrato = sessao.scalar(select(Contrato).where(Contrato.id == contrato_id).options(*opcoes_carga_completa()))
    if contrato is None:
        raise RegistroNaoEncontrado("Contrato")
    return contrato


def designacoes_vigentes(contrato: Contrato, momento: datetime | None = None) -> list[DesignacaoEquipe]:
    """Designações da equipe válidas no momento (as trocas encerram a anterior com `valido_ate`)."""
    agora = momento or agora_utc()
    return [
        d for d in contrato.equipe
        if (d.valido_de is None or _utc(d.valido_de) <= agora) and (d.valido_ate is None or _utc(d.valido_ate) > agora)
    ]


def _utc(valor: datetime) -> datetime:
    """Garante fuso UTC na data (necessário para comparar com `agora_utc`)."""
    # SQLite devolve datas sem fuso; tudo é gravado em UTC
    return valor if valor.tzinfo else valor.replace(tzinfo=ZoneInfo("UTC"))


def integra_equipe(contrato: Contrato, usuario: Usuario) -> bool:
    """Indica se o usuário está na equipe vigente do contrato (em qualquer um dos seis papéis)."""
    return any(d.usuario_id == usuario.id for d in designacoes_vigentes(contrato))


def pode_editar(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """SuperRoot, criador ou integrante vigente da equipe — sempre com ACL ≥ MODIFICACAO."""
    # Primeiro a ACL: sem pelo menos MODIFICACAO, ninguém edita
    nivel = servico_acl.resolver_acesso(sessao, usuario, RECURSO)
    if NivelAcl.posicao(nivel) < NivelAcl.posicao(NivelAcl.MODIFICACAO):
        return False
    return usuario.superusuario or contrato.criador_id == usuario.id or integra_equipe(contrato, usuario)


def exigir_edicao(sessao: Session, contrato: Contrato, usuario: Usuario) -> None:
    """Levanta `SemPermissaoContrato` (vira 403) se o usuário não pode alterar o contrato."""
    if not pode_editar(sessao, contrato, usuario):
        raise SemPermissaoContrato(
            "Somente o criador do contrato, os integrantes da equipe de gestão e fiscalização ou o SuperRoot podem alterá-lo."
        )


def permissoes(sessao: Session, contrato: Contrato, usuario: Usuario) -> PermissoesContrato:
    """Permissões do usuário no contrato, enviadas ao frontend para mostrar ou esconder botões."""
    nivel = servico_acl.resolver_acesso(sessao, usuario, RECURSO)
    return PermissoesContrato(
        pode_editar=pode_editar(sessao, contrato, usuario),
        pode_excluir=nivel == NivelAcl.CONTROLE_TOTAL,
    )


# ---------------------------------------------------------------------------------------------
# Cálculos derivados
# ---------------------------------------------------------------------------------------------

def vigencias(contrato: Contrato) -> list[calculos.Vigencia]:
    """Vigências do contrato: a inicial e uma por prorrogação registrada."""
    prorrogacoes = [(p.data_inicio, p.data_fim) for p in contrato.prorrogacoes]
    return calculos.montar_vigencias(contrato.data_inicio, contrato.data_fim, contrato.vigencia_inicial_meses, prorrogacoes)


def item_valor(contrato: Contrato, item: ItemContrato, vigencia: calculos.Vigencia) -> calculos.ItemValor:
    """Item com a quantidade executada na vigência (cada vigência tem saldo próprio)."""
    return calculos.ItemValor(
        tipo=item.tipo,
        quantidade_mensal=item.quantidade_mensal,
        quantidade_total=valores.limite_na_vigencia(contrato, item, vigencia.sequencia),
        valor_unitario=item.valor_unitario,
        quantidade_executada=valores.executado_na_vigencia(contrato, item, vigencia.sequencia),
    )


def totais(contrato: Contrato) -> tuple[Decimal, Decimal]:
    """(base mensal atual, valor global da vigência atual).

    O valor global é somado mês a mês (`valores.valor_global_vigencia`), o mesmo cálculo da previsão:
    reajustes e aditamentos/supressões valem só a partir do mês de efeito.
    """
    atual = vigencias(contrato)[-1]
    # A vigência atual é sempre a última da lista
    itens = [item_valor(contrato, i, atual) for i in contrato.itens]
    return calculos.base_mensal(itens), valores.valor_global_vigencia(contrato, atual)


def situacao(contrato: Contrato) -> str:
    """Situação do contrato hoje (ativo, a vencer, encerrado ou suspenso)."""
    return calculos.calcular_situacao(contrato.data_fim, contrato.situacao_forcada, hoje()).value


# ---------------------------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------------------------

def _numero(termo: str) -> tuple[int, int] | None:
    """Interpreta "12/2026" como (12, 2026); outro formato → None."""
    partes = termo.split("/")
    if len(partes) == 2 and all(p.isdigit() for p in partes) and len(partes[1]) == 4:
        return int(partes[0]), int(partes[1])
    return None


def listar_contratos(sessao: Session, busca: str | None, pagina: int, tamanho_pagina: int) -> PaginaContratos:
    """Carteira paginada, com busca por apelido, objeto, empresa ou número."""
    # O join com a empresa permite buscar pela razão social e pelo nome fantasia
    consulta = select(Contrato).join(EmpresaContratada, EmpresaContratada.id == Contrato.empresa_id)
    termo = (busca or "").strip().lower()
    if termo:
        padrao = f"%{termo}%"
        condicoes = [
            func.lower(Contrato.apelido).like(padrao),
            func.lower(Contrato.objeto).like(padrao),
            func.lower(EmpresaContratada.razao_social).like(padrao),
            func.lower(EmpresaContratada.nome_fantasia).like(padrao),
        ]
        # Número completo (12/2026) ou só o sequencial (12)
        numero = _numero(termo)
        if numero:
            condicoes.append((Contrato.sequencial == numero[0]) & (Contrato.ano == numero[1]))
        elif termo.isdigit():
            condicoes.append(Contrato.sequencial == int(termo))
        consulta = consulta.where(or_(*condicoes))
    # Total antes de paginar; depois, a página pedida, dos contratos mais recentes para os mais antigos
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    contratos = sessao.scalars(
        consulta.options(*opcoes_carga_resumo())
        .order_by(Contrato.ano.desc(), Contrato.sequencial.desc())
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
    )
    return PaginaContratos(itens=[resumo(c) for c in contratos], total=total, pagina=pagina, tamanho_pagina=tamanho_pagina)


def opcoes_carga_resumo() -> list:
    """Relacionamentos necessários para calcular os totais sem uma consulta por contrato."""
    return [
        selectinload(Contrato.itens),
        selectinload(Contrato.empresa),
        selectinload(Contrato.prorrogacoes),
        selectinload(Contrato.previsoes).selectinload(PrevisaoVigencia.limites),
        selectinload(Contrato.competencias).selectinload(Competencia.itens),
    ]


def resumo(contrato: Contrato) -> ResumoContrato:
    """Converte o contrato na linha da carteira (com base mensal e valor global calculados)."""
    base, valor = totais(contrato)
    return ResumoContrato(
        id=contrato.id,
        numero=contrato.numero,
        apelido=contrato.apelido,
        empresa_razao_social=contrato.empresa.razao_social,
        objeto=contrato.objeto,
        data_inicio=contrato.data_inicio,
        data_fim=contrato.data_fim,
        situacao=situacao(contrato),
        base_mensal=base,
        valor_global=valor,
    )


def leitura_itens(contrato: Contrato) -> list[LeituraItem]:
    """Itens do contrato com as quantidades e saldos da vigência atual."""
    atual = vigencias(contrato)[-1]
    itens = []
    for item in contrato.itens:
        valor = item_valor(contrato, item, atual)
        itens.append(
            LeituraItem(
                id=item.id,
                ordem=item.ordem,
                descricao=item.descricao,
                tipo=item.tipo,
                calcula_pro_rata=item.calcula_pro_rata,
                codigo_classe=item.codigo_classe,
                codigo_natureza_despesa=item.codigo_natureza_despesa,
                codigo_siafisico=item.codigo_siafisico,
                codigo_catmat_catser=item.codigo_catmat_catser,
                quantidade_mensal=item.quantidade_mensal,
                quantidade_total=calculos.quantidade_acumulada(valor, atual.meses),
                quantidade_original=item.quantidade_total,
                quantidade_executada=valor.quantidade_executada,
                quantidade_disponivel=calculos.quantidade_disponivel(valor, atual.meses),
                valor_unitario=item.valor_unitario,
                subtotal_mensal=calculos.arredondar(calculos.subtotal_mensal(valor)),
                vigencia_meses=atual.meses,
            )
        )
    return itens


def detalhar_contrato(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> DetalheContrato:
    """Monta o detalhe completo do contrato para a tela."""
    # Logins da equipe em uma consulta só: {usuario_id: login}
    contrato = obter_contrato(sessao, contrato_id)
    logins = dict(sessao.execute(select(Usuario.id, Usuario.login).where(Usuario.id.in_([d.usuario_id for d in contrato.equipe]))).all())
    criador = sessao.get(Usuario, contrato.criador_id) if contrato.criador_id else None
    # Equipe vigente na ordem fixa dos papéis (gestor, suplente, fiscais...)
    equipe = sorted(designacoes_vigentes(contrato), key=lambda d: PAPEIS_EQUIPE.index(d.papel))
    atual = vigencias(contrato)[-1].sequencia
    # Percentuais acumulados de aditamento e de supressão já concluídos na vigência atual
    acumulado = {
        tipo: sum((abs(a.impacto_percentual) for a in contrato.alteracoes if a.situacao == "concluida" and a.tipo == tipo and a.sequencia_vigencia == atual), Decimal(0))
        for tipo in ("aditamento", "supressao")
    }
    return DetalheContrato(
        # `**resumo(...)` reaproveita os campos da carteira e acrescenta os do detalhe
        **resumo(contrato).model_dump(),
        sequencial=contrato.sequencial,
        ano=contrato.ano,
        empresa=OpcaoEmpresa.model_validate(contrato.empresa, from_attributes=True),
        data_fim_prazo_inicial=calculos.calcular_data_fim(contrato.data_inicio, contrato.vigencia_inicial_meses),
        data_limite_maxima=calculos.data_limite_maxima(contrato.data_inicio, contrato.vigencia_maxima_meses),
        vigencia_inicial_meses=contrato.vigencia_inicial_meses,
        vigencia_maxima_meses=contrato.vigencia_maxima_meses,
        periodicidade_meses=contrato.periodicidade_meses,
        mes_reajuste=contrato.mes_reajuste,
        sei_gestao_numero=contrato.sei_gestao_numero,
        sei_gestao_link=contrato.sei_gestao_link,
        sei_execucao_numero=contrato.sei_execucao_numero,
        sei_execucao_link=contrato.sei_execucao_link,
        situacao_forcada=contrato.situacao_forcada,
        vigencias=[LeituraVigencia(sequencia=v.sequencia, inicio=v.inicio, fim=v.fim, meses=v.meses) for v in vigencias(contrato)],
        marcos=marcos(contrato),
        aditamento_acumulado_percentual=acumulado["aditamento"],
        supressao_acumulada_percentual=acumulado["supressao"],
        itens=leitura_itens(contrato),
        equipe=[
            MembroEquipe(papel=d.papel, usuario_id=d.usuario_id, nome=d.nome_usuario, login=logins.get(d.usuario_id, ""), desde=d.valido_de)
            for d in equipe
        ],
        criador_nome=(criador.nome_completo or criador.login) if criador else None,
        permissoes=permissoes(sessao, contrato, usuario),
        versao=contrato.versao,
        criado_em=contrato.criado_em,
        atualizado_em=contrato.atualizado_em,
    )


def marcos(contrato: Contrato) -> list[MarcoLinhaTempo]:
    """Início, prazo inicial, termos aditivos, reajustes, aditamentos/supressões, vigência atual e máximo."""
    # Marcos fixos: início e fim do prazo inicial
    lista = [
        MarcoLinhaTempo(data=contrato.data_inicio, tipo="inicio", rotulo="Início"),
        MarcoLinhaTempo(
            data=calculos.calcular_data_fim(contrato.data_inicio, contrato.vigencia_inicial_meses), tipo="prazo_inicial",
            rotulo=f"Prazo inicial ({contrato.vigencia_inicial_meses}m)",
        ),
    ]
    for prorrogacao in contrato.prorrogacoes:
        # Uma marca por prorrogação, reajuste e alteração (os cancelados não aparecem)
        numero = f" nº {prorrogacao.numero_termo}" if prorrogacao.numero_termo else ""
        lista.append(MarcoLinhaTempo(data=prorrogacao.data_inicio, tipo="termo_aditivo", rotulo=f"TA{numero} (+{prorrogacao.meses}m)"))
    for reajuste in contrato.reajustes:
        if reajuste.situacao != "cancelado":
            rotulo = "Reajuste em elaboração" if reajuste.situacao == "rascunho" else "Reajuste aplicado"
            lista.append(MarcoLinhaTempo(data=reajuste.mes_referencia, tipo="reajuste", rotulo=rotulo))
    for alteracao in contrato.alteracoes:
        if alteracao.situacao != "cancelada":
            nome = "Aditamento" if alteracao.tipo == "aditamento" else "Supressão"
            sufixo = f" {abs(alteracao.impacto_percentual):.2f}%".replace(".", ",") if alteracao.situacao == "concluida" else " em elaboração"
            lista.append(MarcoLinhaTempo(data=alteracao.mes_efeito, tipo=alteracao.tipo, rotulo=f"{nome}{sufixo}"))
    lista.append(MarcoLinhaTempo(data=contrato.data_fim, tipo="vigencia_atual", rotulo="Vigência atual"))
    # Por fim, o fim da vigência atual e o limite máximo; a lista sai em ordem de data
    lista.append(MarcoLinhaTempo(
        data=calculos.data_limite_maxima(contrato.data_inicio, contrato.vigencia_maxima_meses), tipo="maximo",
        rotulo=f"Máximo ({contrato.vigencia_maxima_meses}m)",
    ))
    return sorted(lista, key=lambda m: m.data)


def proximo_numero(sessao: Session, ano: int) -> ProximoNumero:
    """Sugere o próximo número do ano: o maior sequencial já usado + 1."""
    maior = sessao.scalar(select(func.max(Contrato.sequencial)).where(Contrato.ano == ano)) or 0
    return ProximoNumero(numero=f"{maior + 1:03d}/{ano:04d}", sequencial=maior + 1, ano=ano)


# ---------------------------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------------------------

def _dados_auditados(contrato: Contrato) -> dict:
    """Retrato dos campos auditados do contrato (para comparar antes e depois)."""
    dados = {c: getattr(contrato, c) for c in CAMPOS_AUDITADOS if c != "numero"}
    dados["numero"] = contrato.numero
    return dados


def _validar_cabecalho(sessao: Session, dados: GravacaoContrato, contrato: Contrato | None) -> tuple[int, int]:
    """Valida número único e empresa; devolve (sequencial, ano) já separados."""
    # "12/2026" → (12, 2026)
    sequencial, ano = (int(p) for p in dados.numero.split("/"))
    if sequencial < 1:
        raise ErroRegraContrato("O número do contrato deve ser maior que zero.")
    existente = sessao.scalar(select(Contrato.id).where(Contrato.sequencial == sequencial, Contrato.ano == ano))
    # O número não pode repetir, exceto o do próprio contrato na alteração
    if existente is not None and (contrato is None or existente != contrato.id):
        raise ErroRegraContrato(f"Já existe um contrato com o número {sequencial:03d}/{ano:04d}.", conflito=True)
    empresa = sessao.get(EmpresaContratada, dados.empresa_id)
    if empresa is None:
        raise ErroRegraContrato("Empresa não encontrada.")
    # Contrato existente pode manter uma empresa que foi inativada depois
    if not empresa.ativa and (contrato is None or contrato.empresa_id != empresa.id):
        raise ErroRegraContrato("Selecione uma empresa ativa.")
    return sequencial, ano


def _aplicar_cabecalho(contrato: Contrato, dados: GravacaoContrato, sequencial: int, ano: int) -> None:
    """Copia os dados do cabeçalho para o contrato, respeitando as regras de vigência."""
    # Depois de uma prorrogação, as datas iniciais ficam travadas (as vigências dependem delas)
    datas_bloqueadas = bool(contrato.id and contrato.prorrogacoes)
    if datas_bloqueadas and (
        dados.data_inicio != contrato.data_inicio or dados.vigencia_inicial_meses != contrato.vigencia_inicial_meses
    ):
        raise ErroRegraContrato("Depois de uma prorrogação, a data inicial e a vigência inicial não podem ser alteradas.")
    soma_vigencias = dados.vigencia_inicial_meses + (sum(p.meses for p in contrato.prorrogacoes) if contrato.id else 0)
    # A vigência máxima não pode ficar menor que a soma das vigências já registradas
    if dados.vigencia_maxima_meses < soma_vigencias:
        raise ErroRegraContrato(f"A vigência máxima deve ser de ao menos {soma_vigencias} meses (soma das vigências registradas).")
    contrato.sequencial, contrato.ano = sequencial, ano
    for campo in (
        "empresa_id", "apelido", "objeto", "data_inicio", "vigencia_inicial_meses", "vigencia_maxima_meses",
        "periodicidade_meses", "mes_reajuste", "sei_gestao_numero", "sei_gestao_link", "sei_execucao_numero",
        "sei_execucao_link", "situacao_forcada",
    ):
        setattr(contrato, campo, getattr(dados, campo))
    if not datas_bloqueadas:
        # O fim da vigência é calculado pelo início e pelo prazo inicial
        contrato.data_fim = calculos.calcular_data_fim(dados.data_inicio, dados.vigencia_inicial_meses)


def itens_bloqueados(contrato: Contrato) -> bool:
    """Depois de geradas as competências, itens, ordem e vigência só mudam pelo SuperRoot."""
    return bool(contrato.id and contrato.competencias)


def _aplicar_itens(contrato: Contrato, itens: list[GravacaoItem], usuario: Usuario) -> dict:
    """Sincroniza a lista de itens e devolve o resumo das mudanças para a auditoria."""
    atuais = {i.id: i for i in contrato.itens}
    # Mapa dos itens atuais e conjunto dos ids enviados
    enviados = {i.id for i in itens if i.id is not None}
    desconhecidos = enviados - set(atuais)
    if desconhecidos:
        raise ErroRegraContrato("Um dos itens enviados não pertence a este contrato.")
    mudancas: dict = {"adicionados": [], "removidos": [], "alterados": {}}
    for item_id, item in atuais.items():
        # 1º: remove os itens que não vieram na lista (se ainda não tiverem execução)
        if item_id not in enviados:
            if item.quantidade_executada > 0:
                raise ErroRegraContrato(f"O item \"{item.descricao}\" já tem execução e não pode ser excluído.")
            mudancas["removidos"].append(item.descricao)
            contrato.itens.remove(item)
    for ordem, dados in enumerate(itens, start=1):
        # 2º: percorre a lista na ordem recebida (a posição define a nova ordem); item sem id é novo
        if dados.id is None:
            novo = ItemContrato(ordem=ordem, **dados.model_dump(exclude={"id"}))
            contrato.itens.append(novo)
            mudancas["adicionados"].append(dados.descricao)
            continue
        item = atuais[dados.id]
        if any(getattr(item, c) != getattr(dados, c) for c in CAMPOS_ITEM_IMUTAVEIS):
            # Item existente: nome, tipo e faturamento não podem mudar
            raise ErroRegraContrato(
                f"O item \"{item.descricao}\" não pode mudar nome, tipo nem faturamento. Exclua-o e crie outro."
            )
        alterados = {
            # Registra, campo a campo, o que mudou (para a auditoria)
            c: {"de": getattr(item, c), "para": getattr(dados, c)}
            for c in CAMPOS_ITEM_EDITAVEIS
            if getattr(item, c) != getattr(dados, c)
        }
        if item.ordem != ordem:
            alterados["ordem"] = {"de": item.ordem, "para": ordem}
        for campo in CAMPOS_ITEM_EDITAVEIS:
            setattr(item, campo, getattr(dados, campo))
        item.ordem = ordem
        if alterados:
            mudancas["alterados"][item.descricao] = alterados
    houve = any(mudancas[c] for c in mudancas)
    # Com competências já geradas, só o SuperRoot pode mexer nos itens
    if houve and itens_bloqueados(contrato) and not usuario.superusuario:
        raise ErroRegraContrato("As competências de execução já foram geradas: itens e ordem só podem ser alterados pelo SuperRoot.")
    return mudancas if houve else {}


def _aplicar_equipe(sessao: Session, contrato: Contrato, dados: GravacaoContrato) -> dict:
    """Troca de designados: encerra a designação anterior e abre (ou reabre) a nova."""
    agora = agora_utc()
    # Designações vigentes indexadas pelo papel
    vigentes = {d.papel: d for d in designacoes_vigentes(contrato, agora)}
    alteracoes: dict = {}
    for papel in PAPEIS_EQUIPE:
        novo_id = getattr(dados.equipe, papel)
        # Mesmo usuário no papel: nada muda
        atual = vigentes.get(papel)
        if (atual.usuario_id if atual else None) == novo_id:
            continue
        if atual:
            # Encerra a designação anterior
            atual.valido_ate = agora
        nome_novo = None
        if novo_id is not None:
            usuario = sessao.get(Usuario, novo_id)
            if usuario is None or not usuario.ativo:
                raise ErroRegraContrato("Um dos usuários designados para a equipe não existe ou está inativo.")
            nome_novo = usuario.nome_completo or usuario.login
            existente = next((d for d in contrato.equipe if d.usuario_id == novo_id and d.papel == papel), None)
            if existente:
                # Se a pessoa já ocupou este papel antes, reabre a designação antiga em vez de criar outra
                existente.valido_de, existente.valido_ate, existente.nome_usuario = agora, None, nome_novo
            else:
                contrato.equipe.append(DesignacaoEquipe(usuario_id=novo_id, papel=papel, nome_usuario=nome_novo, valido_de=agora))
            # Ponto único para a futura caixa de notificações (designação na equipe)
        alteracoes[f"equipe.{papel}"] = {"de": atual.nome_usuario if atual else None, "para": nome_novo}
    return alteracoes


def criar_contrato(sessao: Session, dados: GravacaoContrato, autor: Usuario) -> Contrato:
    """Cadastra o contrato com itens e equipe; o autor fica como criador."""
    sequencial, ano = _validar_cabecalho(sessao, dados, None)
    contrato = Contrato(criador_id=autor.id, versao=1)
    _aplicar_cabecalho(contrato, dados, sequencial, ano)
    sessao.add(contrato)
    _aplicar_itens(contrato, dados.itens, autor)
    _aplicar_equipe(sessao, contrato, dados)
    sessao.flush()
    auditar(sessao, autor.login, "contrato.criar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"numero": contrato.numero, "itens": len(dados.itens)})
    sessao.commit()
    return contrato


def alterar_contrato(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoContrato, autor: Usuario) -> Contrato:
    """Altera o contrato inteiro (cabeçalho, itens e equipe) com controle de concorrência."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    # Controle de concorrência otimista: se a versão lida não é a atual, alguém salvou antes
    if dados.versao is None or dados.versao != contrato.versao:
        raise ErroRegraContrato(
            "O contrato foi alterado por outra pessoa depois que você o abriu. Recarregue a página e refaça a alteração.",
            conflito=True,
        )
    sequencial, ano = _validar_cabecalho(sessao, dados, contrato)
    antes = _dados_auditados(contrato)
    _aplicar_cabecalho(contrato, dados, sequencial, ano)
    mudancas_itens = _aplicar_itens(contrato, dados.itens, autor)
    mudancas_equipe = _aplicar_equipe(sessao, contrato, dados)
    # Cada gravação incrementa a versão
    contrato.versao += 1
    # Três registros de auditoria: campos do cabeçalho, equipe e itens
    auditar_alteracoes(sessao, autor.login, autor.id, "contrato.alterar", "contrato", contrato.id,
                       f"Contrato {contrato.numero}", antes, _dados_auditados(contrato))
    if mudancas_equipe:
        auditar(sessao, autor.login, "contrato.equipe.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
                alvo_tipo="contrato", alvo_id=contrato.id, dados={"campos": mudancas_equipe})
    if mudancas_itens:
        auditar(sessao, autor.login, "contrato.itens.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
                alvo_tipo="contrato", alvo_id=contrato.id, dados={"itens": mudancas_itens})
    sessao.commit()
    return contrato


def excluir_contrato(sessao: Session, contrato_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui o contrato; os anexos são marcados como excluídos (os arquivos ficam em disco)."""
    contrato = obter_contrato(sessao, contrato_id)
    # Todos os arquivos do contrato (documentos, execução, prorrogações, reajustes e alterações)
    for anexo in sessao.scalars(select(Anexo).where(Anexo.contrato_id == contrato.id, Anexo.excluido_em.is_(None))):
        servico_anexos.descartar(anexo)
    for documento in contrato.documentos:
        if documento.anexo and documento.anexo.excluido_em is None:
            servico_anexos.descartar(documento.anexo)
    auditar(sessao, autor.login, "contrato.excluir", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados=_dados_auditados(contrato))
    sessao.delete(contrato)
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Documentos importantes (repositório opcional; nada depende deles)
# ---------------------------------------------------------------------------------------------

def listar_documentos(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraDocumento]:
    """Lista o catálogo inteiro (anexados ou não) mais os termos aditivos já anexados."""
    contrato = obter_contrato(sessao, contrato_id)
    anexados = {d.codigo_tipo: d for d in contrato.documentos}
    # Nomes de quem enviou cada documento, em uma consulta
    nomes = dict(
        sessao.execute(
            select(Usuario.id, func.coalesce(Usuario.nome_completo, Usuario.login)).where(
                Usuario.id.in_([d.enviado_por_id for d in contrato.documentos if d.enviado_por_id])
            )
        ).all()
    )
    # Códigos do catálogo (001–023) seguidos dos termos aditivos (024+) existentes
    codigos = [t.codigo for t in CATALOGO] + sorted(c for c in anexados if c not in POR_CODIGO)
    lista = []
    for codigo in codigos:
        documento = anexados.get(codigo)
        # Anexo marcado como excluído conta como "não anexado"
        anexo = documento.anexo if documento and documento.anexo and documento.anexo.excluido_em is None else None
        lista.append(
            LeituraDocumento(
                codigo=codigo,
                numero=f"{codigo:03d}",
                titulo=documento.titulo if documento else POR_CODIGO[codigo].titulo,
                anexado=anexo is not None,
                nome_arquivo=nome_download(codigo, contrato.sequencial, contrato.ano),
                tamanho=anexo.tamanho if anexo else None,
                enviado_em=documento.enviado_em if anexo else None,
                enviado_por_nome=nomes.get(documento.enviado_por_id) if anexo else None,
            )
        )
    return lista


def enviar_documento(
    sessao: Session, contrato_id: uuid.UUID, codigo: int, arquivo: BinaryIO, nome_arquivo: str, autor: Usuario
) -> None:
    """Anexa (ou substitui) o PDF de um documento do catálogo."""
    # Termos aditivos (024+) entram só pelo fluxo da prorrogação
    if codigo not in POR_CODIGO:
        raise ErroRegraContrato("Tipo de documento inválido. Os termos aditivos são anexados pela prorrogação.")
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    anexo = servico_anexos.guardar_pdf(sessao, arquivo, nome_arquivo, "contrato-documento", autor.id, contrato_id=contrato.id)
    # Primeiro envio cria o registro do documento; reenvio descarta o anexo anterior
    documento = next((d for d in contrato.documentos if d.codigo_tipo == codigo), None)
    if documento is None:
        documento = DocumentoContrato(codigo_tipo=codigo, titulo=POR_CODIGO[codigo].titulo)
        contrato.documentos.append(documento)
    elif documento.anexo:
        servico_anexos.descartar(documento.anexo)
    documento.anexo = anexo
    documento.enviado_em = agora_utc()
    documento.enviado_por_id = autor.id
    auditar(sessao, autor.login, "contrato.documento.enviar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"codigo": codigo, "titulo": documento.titulo, "arquivo": nome_arquivo, "sha256": anexo.sha256})
    sessao.commit()


def documento_para_download(sessao: Session, contrato_id: uuid.UUID, codigo: int):
    """Resposta de download do documento, com o nome padronizado."""
    contrato = obter_contrato(sessao, contrato_id)
    documento = next((d for d in contrato.documentos if d.codigo_tipo == codigo), None)
    if documento is None or documento.anexo is None:
        raise RegistroNaoEncontrado("Documento")
    return servico_anexos.resposta_download(documento.anexo, nome_download(codigo, contrato.sequencial, contrato.ano))


# ---------------------------------------------------------------------------------------------
# Histórico por campo
# ---------------------------------------------------------------------------------------------

def historico(sessao: Session, contrato_id: uuid.UUID) -> list[AlteracaoCampo]:
    """Histórico campo a campo do contrato, do mais recente para o mais antigo."""
    obter_contrato(sessao, contrato_id)
    alteracoes = []
    # Cada registro de auditoria pode conter vários campos; vira uma linha por campo
    for registro in historico_campos(sessao, "contrato", contrato_id):
        for campo, mudanca in ((registro.dados or {}).get("campos") or {}).items():
            alteracoes.append(
                AlteracaoCampo(campo=campo, de=mudanca.get("de"), para=mudanca.get("para"), autor=registro.autor, ocorrido_em=registro.ocorrido_em)
            )
    return alteracoes
