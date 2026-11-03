# Criado por José Eduardo Santana Martins
# Este arquivo serve para manter os Parâmetros dos Chamados (expedientes, SLAs, categorias) e resolver o que cada categoria herda.
"""Parâmetros dos Chamados.

Regras que impedem por design os erros de configuração vistos no GLPI da SPI:
- **SLA sempre com expediente** (a coluna é obrigatória) e expediente sempre com pelo menos uma faixa de horário;
- **categoria raiz ativa sempre com setor responsável**; as filhas herdam da mãe o que deixarem vazio (setor, SLAs, prioridade, responsável);
- nome de categoria único dentro da mesma mãe; mover ou renomear recalcula o caminho de toda a subárvore;
- nada se apaga: categoria, SLA e expediente são desativados (o histórico continua apontando para eles).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chamados import PRIORIDADES, CategoriaChamados, CategoriaItilChamados, CategoriaSetorPermitido, ExpedienteChamados, FaixaExpedienteChamados, ParametroChamados, SlaChamados
from app.models.rh import Feriado
from app.models.setor import Setor
from app.services.chamados.motor_sla import Expediente

# Valores padrão dos parâmetros (texto, como gravados em `chamados_parametros`)
PADROES = {
    # Dias úteis em que o solicitante ainda pode dizer "Não resolveu"
    "dias_reabrir": "5",
    # O ponto facultativo do RH conta como dia útil no SLA? (padrão: não conta)
    "sla_ponto_facultativo_util": "nao",
    # Próximo número de chamado (o importador ajusta para depois do maior número do GLPI)
    "proximo_numero": "1",
}
SEPARADOR_CAMINHO = " > "


class ErroParametro(Exception):
    """Regra de configuração violada (vira `{"detalhe", "codigo"}` na rota)."""

    def __init__(self, mensagem: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo


# ---------------------------------------------------------------------------------------------
# Parâmetros chave/valor
# ---------------------------------------------------------------------------------------------

def obter(sessao: Session, chave: str) -> str:
    """Valor do parâmetro (o padrão, se ninguém gravou)."""
    linha = sessao.get(ParametroChamados, chave)
    return linha.valor if linha else PADROES[chave]


def obter_inteiro(sessao: Session, chave: str) -> int:
    try:
        return int(obter(sessao, chave))
    except ValueError:
        return int(PADROES[chave])


def gravar(sessao: Session, chave: str, valor: str) -> None:
    linha = sessao.get(ParametroChamados, chave)
    if linha is None:
        sessao.add(ParametroChamados(chave=chave, valor=valor))
    else:
        linha.valor = valor


def reservar_numero(sessao: Session) -> int:
    """Próximo número de chamado, travando a linha do contador (dois chamados ao mesmo tempo não pegam o mesmo número)."""
    linha = sessao.scalar(select(ParametroChamados).where(ParametroChamados.chave == "proximo_numero").with_for_update())
    if linha is None:
        from app.models.chamados import Chamado

        maior = sessao.scalar(select(func.max(Chamado.numero))) or 0
        linha = ParametroChamados(chave="proximo_numero", valor=str(max(maior + 1, int(PADROES["proximo_numero"]))))
        sessao.add(linha)
        sessao.flush()
    numero = int(linha.valor)
    linha.valor = str(numero + 1)
    return numero


# ---------------------------------------------------------------------------------------------
# Feriados e expediente (entrada do motor de horas úteis)
# ---------------------------------------------------------------------------------------------

def feriados_do_sla(sessao: Session) -> set[date]:
    """Feriados do RH que param o relógio do SLA. O ponto facultativo entra, a menos que o parâmetro diga que ele é dia útil."""
    consulta = select(Feriado.data)
    if obter(sessao, "sla_ponto_facultativo_util") == "sim":
        consulta = consulta.where(Feriado.tipo != "ponto_facultativo")
    return set(sessao.scalars(consulta))


def faixas_do_expediente(expediente: ExpedienteChamados) -> Expediente:
    """Expediente no formato do motor: {dia da semana: [(início, fim), ...]}."""
    faixas: dict[int, list[tuple[time, time]]] = {}
    for f in expediente.faixas:
        faixas.setdefault(f.dia_semana, []).append((f.inicio, f.fim))
    return {d: sorted(v) for d, v in faixas.items()}


# ---------------------------------------------------------------------------------------------
# Expedientes
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosFaixa:
    dia_semana: int
    inicio: time
    fim: time


def _aplicar_faixas(expediente: ExpedienteChamados, faixas: list[DadosFaixa]) -> None:
    if not faixas:
        raise ErroParametro("Informe pelo menos uma faixa de horário: expediente sem horário faria o prazo nunca vencer.", 400, "expediente_vazio")
    for f in faixas:
        if not 0 <= f.dia_semana <= 6:
            raise ErroParametro("Dia da semana inválido (0 = segunda ... 6 = domingo).")
        if f.fim <= f.inicio:
            raise ErroParametro("O fim de cada faixa precisa ser depois do início.")
    por_dia: dict[int, list[DadosFaixa]] = {}
    for f in faixas:
        por_dia.setdefault(f.dia_semana, []).append(f)
    for lista in por_dia.values():
        lista.sort(key=lambda x: x.inicio)
        for anterior, seguinte in zip(lista, lista[1:]):
            if seguinte.inicio < anterior.fim:
                raise ErroParametro("Há faixas sobrepostas no mesmo dia.")
    expediente.faixas.clear()
    for f in faixas:
        expediente.faixas.append(FaixaExpedienteChamados(dia_semana=f.dia_semana, inicio=f.inicio, fim=f.fim))


def listar_expedientes(sessao: Session) -> list[ExpedienteChamados]:
    return list(sessao.scalars(select(ExpedienteChamados).order_by(ExpedienteChamados.nome)))


def salvar_expediente(sessao: Session, expediente_id: uuid.UUID | None, nome: str, ativo: bool, faixas: list[DadosFaixa]) -> ExpedienteChamados:
    nome = nome.strip()
    if not nome:
        raise ErroParametro("Informe o nome do expediente.")
    repetido = sessao.scalar(select(ExpedienteChamados.id).where(func.lower(ExpedienteChamados.nome) == nome.lower()))
    if repetido is not None and repetido != expediente_id:
        raise ErroParametro("Já existe um expediente com esse nome.", 409, "conflito")
    expediente = obter_expediente(sessao, expediente_id) if expediente_id else ExpedienteChamados()
    expediente.nome, expediente.ativo = nome, ativo
    _aplicar_faixas(expediente, faixas)
    if expediente_id is None:
        sessao.add(expediente)
    sessao.flush()
    return expediente


def excluir_expediente(sessao: Session, expediente_id: uuid.UUID) -> None:
    """Exclui o expediente que nenhum SLA usa. Em uso, recusa e diz quais SLAs usam (trocar o expediente deles ou desativar este)."""
    expediente = obter_expediente(sessao, expediente_id)
    usuarios = list(sessao.scalars(select(SlaChamados.nome).where(SlaChamados.expediente_id == expediente.id).order_by(SlaChamados.nome)))
    if usuarios:
        raise ErroParametro(
            f"Este expediente é usado pelos SLAs: {', '.join(usuarios)}. Troque o expediente desses SLAs ou desative este, em vez de excluir.",
            409, "em_uso",
        )
    sessao.delete(expediente)
    sessao.flush()


def obter_expediente(sessao: Session, expediente_id: uuid.UUID) -> ExpedienteChamados:
    expediente = sessao.get(ExpedienteChamados, expediente_id)
    if expediente is None:
        raise ErroParametro("Expediente não encontrado.", 404, "nao_encontrado")
    return expediente


# ---------------------------------------------------------------------------------------------
# SLAs
# ---------------------------------------------------------------------------------------------

def listar_slas(sessao: Session) -> list[SlaChamados]:
    return list(sessao.scalars(select(SlaChamados).order_by(SlaChamados.tipo, SlaChamados.nome)))


def obter_sla(sessao: Session, sla_id: uuid.UUID) -> SlaChamados:
    sla = sessao.get(SlaChamados, sla_id)
    if sla is None:
        raise ErroParametro("SLA não encontrado.", 404, "nao_encontrado")
    return sla


def salvar_sla(sessao: Session, sla_id: uuid.UUID | None, nome: str, tipo: str, tempo: int, unidade: str, expediente_id: uuid.UUID, ativo: bool) -> SlaChamados:
    if not nome.strip():
        raise ErroParametro("Informe o nome do SLA.")
    if tempo <= 0:
        raise ErroParametro("O tempo do SLA precisa ser maior que zero.")
    expediente = obter_expediente(sessao, expediente_id)
    if not expediente.ativo:
        raise ErroParametro("Escolha um expediente ativo.")
    sla = obter_sla(sessao, sla_id) if sla_id else SlaChamados()
    sla.nome, sla.tipo, sla.tempo, sla.unidade, sla.expediente_id, sla.ativo = nome.strip(), tipo, tempo, unidade, expediente.id, ativo
    if sla_id is None:
        sessao.add(sla)
    sessao.flush()
    return sla


def excluir_sla(sessao: Session, sla_id: uuid.UUID) -> None:
    """Exclui o SLA que nenhuma categoria nem nenhum chamado usa. Em uso, recusa e diz onde (o histórico dos chamados depende dele)."""
    from app.models.chamados import Chamado

    sla = obter_sla(sessao, sla_id)
    categorias = list(sessao.scalars(
        select(CategoriaChamados.caminho).where((CategoriaChamados.sla_tto_id == sla.id) | (CategoriaChamados.sla_ttr_id == sla.id)).order_by(CategoriaChamados.caminho)
    ))
    if categorias:
        raise ErroParametro(f"Este SLA é usado pelas categorias: {', '.join(categorias[:5])}{'…' if len(categorias) > 5 else ''}. "
                            "Troque o SLA dessas categorias ou desative este, em vez de excluir.", 409, "em_uso")
    chamados = sessao.scalar(select(func.count()).where((Chamado.sla_tto_id == sla.id) | (Chamado.sla_ttr_id == sla.id))) or 0
    if chamados:
        raise ErroParametro(f"Este SLA já foi usado em {chamados} chamado(s) e faz parte do histórico deles. Desative-o em vez de excluir.", 409, "em_uso")
    sessao.delete(sla)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosCategoria:
    nome: str
    pai_id: uuid.UUID | None = None
    ativa: bool = True
    visivel_solicitante: bool = True
    permite_incidente: bool = True
    permite_requisicao: bool = True
    setor_id: int | None = None
    responsavel_id: int | None = None
    sla_tto_id: uuid.UUID | None = None
    sla_ttr_id: uuid.UUID | None = None
    prioridade_padrao: str | None = None
    perguntar_impedindo: bool = True
    sigilosa: bool = False
    ordem: int = 0
    categoria_itil_id: uuid.UUID | None = None
    # "Quem pode escolher este assunto": vazio = vale `visivel_solicitante`; com setores = só os membros deles (e dos setores abaixo)
    setores_permitidos: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class CategoriaEfetiva:
    """O que vale para um chamado aberto na categoria, depois de herdar da mãe o que estiver vazio."""
    setor_id: int | None
    responsavel_id: int | None
    sla_tto_id: uuid.UUID | None
    sla_ttr_id: uuid.UUID | None
    prioridade_padrao: str
    sigilosa: bool
    categoria_itil_id: uuid.UUID | None = None


def listar_categorias(sessao: Session) -> list[CategoriaChamados]:
    return list(sessao.scalars(select(CategoriaChamados).order_by(CategoriaChamados.caminho)))


def obter_categoria(sessao: Session, categoria_id: uuid.UUID) -> CategoriaChamados:
    categoria = sessao.get(CategoriaChamados, categoria_id)
    if categoria is None:
        raise ErroParametro("Categoria não encontrada.", 404, "nao_encontrado")
    return categoria


def efetiva(categoria: CategoriaChamados) -> CategoriaEfetiva:
    """Sobe a árvore preenchendo o que a categoria deixou vazio. A sigilosa vale se qualquer ancestral for sigiloso."""
    setor = responsavel = tto = ttr = prioridade = itil = None
    sigilosa = False
    atual: CategoriaChamados | None = categoria
    while atual is not None:
        itil = itil if itil is not None else atual.categoria_itil_id
        setor = setor if setor is not None else atual.setor_id
        responsavel = responsavel if responsavel is not None else atual.responsavel_id
        tto = tto if tto is not None else atual.sla_tto_id
        ttr = ttr if ttr is not None else atual.sla_ttr_id
        prioridade = prioridade or atual.prioridade_padrao
        sigilosa = sigilosa or atual.sigilosa
        atual = atual.pai
    return CategoriaEfetiva(setor, responsavel, tto, ttr, prioridade or "normal", sigilosa, itil)


def _ancestrais(categoria: CategoriaChamados | None) -> set[uuid.UUID]:
    ids = set()
    while categoria is not None:
        ids.add(categoria.id)
        categoria = categoria.pai
    return ids


def _recalcular_caminho(categoria: CategoriaChamados) -> None:
    """Caminho e nível da categoria e de toda a subárvore."""
    if categoria.pai is None:
        categoria.caminho, categoria.nivel = categoria.nome, 1
    else:
        categoria.caminho, categoria.nivel = f"{categoria.pai.caminho}{SEPARADOR_CAMINHO}{categoria.nome}", categoria.pai.nivel + 1
    for filha in categoria.filhas:
        _recalcular_caminho(filha)


def salvar_categoria(sessao: Session, categoria_id: uuid.UUID | None, dados: DadosCategoria) -> CategoriaChamados:
    nome = dados.nome.strip()
    if not nome:
        raise ErroParametro("Informe o nome da categoria.")
    if SEPARADOR_CAMINHO.strip() in nome:
        raise ErroParametro("O nome não pode ter o caractere \">\" (ele separa os níveis do caminho).")
    if dados.prioridade_padrao is not None and dados.prioridade_padrao not in PRIORIDADES:
        raise ErroParametro("Prioridade inválida.")
    categoria = obter_categoria(sessao, categoria_id) if categoria_id else CategoriaChamados()
    pai = obter_categoria(sessao, dados.pai_id) if dados.pai_id else None
    if categoria_id and pai is not None and categoria.id in _ancestrais(pai):
        raise ErroParametro("Uma categoria não pode ficar dentro dela mesma ou de uma subcategoria sua.")
    # Nome único dentro da mesma mãe (sem diferenciar maiúsculas)
    consulta = select(CategoriaChamados.id).where(func.lower(CategoriaChamados.nome) == nome.lower(),
                                                   CategoriaChamados.pai_id.is_(None) if pai is None else CategoriaChamados.pai_id == pai.id)
    repetida = sessao.scalar(consulta)
    if repetida is not None and repetida != categoria_id:
        raise ErroParametro("Já existe uma categoria com esse nome neste nível.", 409, "conflito")
    if dados.categoria_itil_id is not None:
        itil = sessao.get(CategoriaItilChamados, dados.categoria_itil_id)
        if itil is None or not itil.ativa:
            raise ErroParametro("Escolha uma categoria ITIL ativa (ou deixe vazio para o técnico classificar).")
    for sla_id, tipo in ((dados.sla_tto_id, "tto"), (dados.sla_ttr_id, "ttr")):
        if sla_id is not None and obter_sla(sessao, sla_id).tipo != tipo:
            raise ErroParametro("O SLA escolhido não é do tipo certo (atendimento × solução).")
    if dados.setor_id is not None:
        setor = sessao.get(Setor, dados.setor_id)
        if setor is None or not setor.ativo:
            raise ErroParametro("Escolha um setor ativo como responsável.")
    permitidos = set(dados.setores_permitidos)
    if permitidos and len(list(sessao.scalars(select(Setor.id).where(Setor.id.in_(permitidos), Setor.ativo.is_(True))))) != len(permitidos):
        raise ErroParametro("Um dos setores de \"Quem pode escolher este assunto\" não existe ou está inativo.")
    for campo in ("ativa", "visivel_solicitante", "permite_incidente", "permite_requisicao", "setor_id", "responsavel_id", "sla_tto_id",
                  "sla_ttr_id", "prioridade_padrao", "perguntar_impedindo", "sigilosa", "ordem", "categoria_itil_id"):
        setattr(categoria, campo, getattr(dados, campo))
    categoria.nome, categoria.pai = nome, pai
    # Setores que podem escolher: tira os que saíram e põe os novos (sem regravar os que ficaram)
    for vinculo in list(categoria.setores_permitidos):
        if vinculo.setor_id not in permitidos:
            categoria.setores_permitidos.remove(vinculo)
    atuais = {v.setor_id for v in categoria.setores_permitidos}
    for setor_id in sorted(permitidos - atuais):
        categoria.setores_permitidos.append(CategoriaSetorPermitido(setor_id=setor_id))
    if categoria_id is None:
        sessao.add(categoria)
    # A1: categoria ativa sem setor efetivo (nem próprio, nem herdado) é recusada
    if categoria.ativa and efetiva(categoria).setor_id is None:
        raise ErroParametro("Toda categoria ativa precisa de um setor responsável (próprio ou herdado da categoria-mãe).", 400, "categoria_sem_setor")
    if not categoria.ativa and categoria_id:
        # Sem filha ativa debaixo de mãe inativa
        for filha in categoria.filhas:
            if filha.ativa:
                raise ErroParametro("Desative antes as subcategorias ativas.", 409, "conflito")
    _recalcular_caminho(categoria)
    # Tirar o setor de uma mãe não pode deixar uma filha ativa sem setor herdado
    pendentes = [f.caminho for f in _descendentes(categoria) if f.ativa and efetiva(f).setor_id is None]
    if pendentes:
        raise ErroParametro(f"Estas subcategorias ficariam sem setor responsável: {', '.join(pendentes[:5])}.", 400, "categoria_sem_setor")
    sessao.flush()
    return categoria


def _descendentes(categoria: CategoriaChamados) -> list[CategoriaChamados]:
    resultado = []
    for filha in categoria.filhas:
        resultado.append(filha)
        resultado.extend(_descendentes(filha))
    return resultado


def excluir_categoria(sessao: Session, categoria_id: uuid.UUID) -> None:
    """Exclui a categoria sem subcategorias e sem chamados. Senão recusa: subcategorias ficariam soltas e o histórico aponta para ela."""
    from app.models.chamados import Chamado

    categoria = obter_categoria(sessao, categoria_id)
    if categoria.filhas:
        raise ErroParametro(f"\"{categoria.nome}\" tem subcategorias. Exclua ou mova as subcategorias antes, ou desative a categoria.", 409, "em_uso")
    chamados = sessao.scalar(select(func.count()).where(Chamado.categoria_id == categoria.id)) or 0
    if chamados:
        raise ErroParametro(f"\"{categoria.nome}\" já tem {chamados} chamado(s) e faz parte do histórico deles. Desative-a em vez de excluir.", 409, "em_uso")
    sessao.delete(categoria)
    sessao.flush()


# ---------------------------------------------------------------------------------------------
# Categorias ITIL (classificação técnica, separada dos assuntos)
# ---------------------------------------------------------------------------------------------

def listar_categorias_itil(sessao: Session) -> list[CategoriaItilChamados]:
    return list(sessao.scalars(select(CategoriaItilChamados).order_by(CategoriaItilChamados.caminho)))


def obter_categoria_itil(sessao: Session, itil_id: uuid.UUID) -> CategoriaItilChamados:
    itil = sessao.get(CategoriaItilChamados, itil_id)
    if itil is None:
        raise ErroParametro("Categoria ITIL não encontrada.", 404, "nao_encontrado")
    return itil


def _recalcular_caminho_itil(itil: CategoriaItilChamados) -> None:
    if itil.pai is None:
        itil.caminho, itil.nivel = itil.nome, 1
    else:
        itil.caminho, itil.nivel = f"{itil.pai.caminho}{SEPARADOR_CAMINHO}{itil.nome}", itil.pai.nivel + 1
    for filha in itil.filhas:
        _recalcular_caminho_itil(filha)


def salvar_categoria_itil(sessao: Session, itil_id: uuid.UUID | None, nome: str, pai_id: uuid.UUID | None, ativa: bool, ordem: int) -> CategoriaItilChamados:
    """Cria ou altera (inclusive move) uma categoria ITIL. Mesmas regras da árvore de assuntos: nome único no nível, sem ciclo, sem ">"."""
    nome = nome.strip()
    if not nome:
        raise ErroParametro("Informe o nome da categoria ITIL.")
    if SEPARADOR_CAMINHO.strip() in nome:
        raise ErroParametro("O nome não pode ter o caractere \">\" (ele separa os níveis do caminho).")
    itil = obter_categoria_itil(sessao, itil_id) if itil_id else CategoriaItilChamados()
    pai = obter_categoria_itil(sessao, pai_id) if pai_id else None
    atual = pai
    while itil_id and atual is not None:
        if atual.id == itil_id:
            raise ErroParametro("Uma categoria não pode ficar dentro dela mesma ou de uma subcategoria sua.")
        atual = atual.pai
    repetida = sessao.scalar(select(CategoriaItilChamados.id).where(
        func.lower(CategoriaItilChamados.nome) == nome.lower(),
        CategoriaItilChamados.pai_id.is_(None) if pai is None else CategoriaItilChamados.pai_id == pai.id))
    if repetida is not None and repetida != itil_id:
        raise ErroParametro("Já existe uma categoria ITIL com esse nome neste nível.", 409, "conflito")
    if not ativa and itil_id and any(f.ativa for f in itil.filhas):
        raise ErroParametro("Desative antes as subcategorias ativas.", 409, "conflito")
    itil.nome, itil.pai, itil.ativa, itil.ordem = nome, pai, ativa, ordem
    if itil_id is None:
        sessao.add(itil)
    _recalcular_caminho_itil(itil)
    sessao.flush()
    return itil


def excluir_categoria_itil(sessao: Session, itil_id: uuid.UUID) -> None:
    """Exclui a que não tem subcategorias nem chamados classificados nela; senão, desative."""
    from app.models.chamados import Chamado

    itil = obter_categoria_itil(sessao, itil_id)
    if itil.filhas:
        raise ErroParametro(f"\"{itil.nome}\" tem subcategorias. Exclua ou mova as subcategorias antes, ou desative a categoria.", 409, "em_uso")
    chamados = sessao.scalar(select(func.count()).where(Chamado.categoria_itil_id == itil.id)) or 0
    if chamados:
        raise ErroParametro(f"\"{itil.nome}\" classifica {chamados} chamado(s). Desative-a em vez de excluir.", 409, "em_uso")
    sessao.flush()
    for assunto in sessao.scalars(select(CategoriaChamados).where(CategoriaChamados.categoria_itil_id == itil.id)):
        assunto.categoria_itil_id = None
    sessao.delete(itil)
    sessao.flush()


def setores_ativos(sessao: Session) -> list[tuple[Setor, str]]:
    """Setores ativos com o caminho na hierarquia ("Subsecretaria > Núcleo de TI"), para escolher o responsável."""
    todos = {s.id: s for s in sessao.scalars(select(Setor))}

    def caminho(s: Setor) -> str:
        partes, atual, vistos = [], s, set()
        while atual is not None and atual.id not in vistos:
            vistos.add(atual.id)
            partes.append(atual.nome)
            atual = todos.get(atual.setor_pai_id) if atual.setor_pai_id else None
        return SEPARADOR_CAMINHO.join(reversed(partes))

    return sorted(((s, caminho(s)) for s in todos.values() if s.ativo), key=lambda x: x[1].lower())
