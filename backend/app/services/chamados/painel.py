# Criado por José Eduardo Santana Martins
# Este arquivo serve para montar o painel dos Chamados: quais chamados cada pessoa vê e como o painel aparece (Parâmetros).
"""Painel de TV.

**Quem aparece em cada painel (regra do usuário):** o setor e todos os setores abaixo dele na hierarquia. A TV da TI mostra só a TI;
a da CGI, só a CGI; a da DGA, a DGA e a CGI; a da Subsecretaria, tudo o que está abaixo dela.
- **Sempre com login** (decisão do usuário): a pessoa vê os chamados em que o **setor responsável** é um setor de que ela é membro (ou um
  abaixo dele). Nada fica fixo no código: cada setor tem o seu painel. Quem administra pode escolher qualquer setor (ou todos).
- A TV da sala fica logada com a conta de alguém do setor, em tela cheia.
- A exibição (linhas por página, tamanho do texto, tempo de cada página, voz, cor na linha, colunas) fica nos Parâmetros.
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import FUSO_SAO_PAULO, agora_utc
from app.models.chamados import STATUS_ABERTOS, STATUS_SOLUCIONADO, Chamado
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.chamados import acesso, parametros
from app.services.chamados.acesso import Papeis
from app.services.chamados.parametros import ErroParametro

# Teto de linhas devolvidas (a TV pagina sozinha; acima disto o painel mostra só os mais urgentes)
MAXIMO_ITENS = 200
# Partículas que não contam como nome em "dois primeiros nomes" (Maria da Silva Souza → Maria Silva)
_PARTICULAS = {"da", "das", "de", "do", "dos", "e", "d'"}


def primeiros_nomes(nome: str) -> str:
    """Os dois primeiros nomes, sem as partículas ("José Eduardo Santana" → "José Eduardo"; "Ana de Souza" → "Ana Souza")."""
    partes = [p for p in nome.split() if p.lower() not in _PARTICULAS]
    return " ".join(partes[:2])


# ---------------------------------------------------------------------------------------------
# Escopo (setores mostrados)
# ---------------------------------------------------------------------------------------------

def setores_do_painel(sessao: Session, setor_id: int) -> set[int]:
    """O setor e todos os de baixo."""
    return acesso._descendentes(sessao, {setor_id})


def escopo_da_pessoa(sessao: Session, usuario: Usuario, p: Papeis, setor_id: int | None) -> tuple[set[int] | None, str]:
    """Setores do painel aberto por uma pessoa, e o nome da área. `None` = todos (só quem administra)."""
    if setor_id is None:
        if p.administrar:
            return None, "Todos os setores"
        membro = acesso.setores_do_usuario(sessao, usuario)
        if not membro:
            raise ErroParametro("Você não é membro de nenhum setor, então não há painel para mostrar.", 403, "sem_setor")
        nomes = sorted(s.nome for s in sessao.scalars(select(Setor).where(Setor.id.in_(membro))))
        return acesso._descendentes(sessao, membro), " · ".join(nomes)
    setor = sessao.get(Setor, setor_id)
    if setor is None:
        raise ErroParametro("Setor não encontrado.", 404, "nao_encontrado")
    if not p.administrar and setor_id not in acesso._descendentes(sessao, acesso.setores_do_usuario(sessao, usuario)):
        raise ErroParametro("Você só vê o painel do seu setor e dos setores abaixo dele.", 403, "acesso_negado")
    return setores_do_painel(sessao, setor_id), setor.nome


# ---------------------------------------------------------------------------------------------
# Chamados e indicadores
# ---------------------------------------------------------------------------------------------

def _inicio_do_dia() -> datetime:
    agora = datetime.now(FUSO_SAO_PAULO)
    return agora.replace(hour=0, minute=0, second=0, microsecond=0)


def chamados(sessao: Session, setores: set[int] | None) -> list[Chamado]:
    """Só os abertos (decisão do usuário: resolvido não aparece no painel; conta só no indicador "resolvidos hoje"). O histórico importado não entra."""
    consulta = (
        select(Chamado).options(selectinload(Chamado.categoria))
        .where(Chamado.excluido_em.is_(None), Chamado.importado.is_(False), Chamado.status_base.in_(STATUS_ABERTOS))
        .order_by(Chamado.aberto_em).limit(MAXIMO_ITENS)
    )
    if setores is not None:
        consulta = consulta.where(Chamado.setor_id.in_(setores))
    return list(sessao.scalars(consulta))


def indicadores(sessao: Session, setores: set[int] | None) -> dict[str, int]:
    """Números do topo: abertos, sem responsável, com prazo de solução estourado e resolvidos hoje."""
    base = [Chamado.excluido_em.is_(None), Chamado.importado.is_(False)]
    if setores is not None:
        base.append(Chamado.setor_id.in_(setores))
    abertos = [*base, Chamado.status_base.in_(STATUS_ABERTOS)]
    agora = agora_utc()

    def contar(*condicoes) -> int:
        return sessao.scalar(select(func.count()).select_from(Chamado).where(*condicoes)) or 0

    return {
        "abertos": contar(*abertos),
        "sem_responsavel": contar(*abertos, Chamado.responsavel_id.is_(None)),
        # Estourado: marcado pela tarefa automática ou já vencido (e não pausado, porque no pendente o relógio para)
        "estourados": contar(*abertos, or_(Chamado.ttr_estourado_em.is_not(None),
                                           (Chamado.prazo_ttr < agora) & (Chamado.status_base != "pendente"))),
        "resolvidos_hoje": contar(*base, Chamado.status_base == STATUS_SOLUCIONADO, Chamado.solucionado_em >= _inicio_do_dia()),
    }


# ---------------------------------------------------------------------------------------------
# Configuração de exibição (Parâmetros > Painel)
# ---------------------------------------------------------------------------------------------

COLUNAS = ("abertura", "titulo", "usuario", "local", "espera", "situacao", "responsavel")
TAMANHOS = ("compacto", "normal", "grande")
parametros.PADROES.update({
    # 0 = automático: quantas linhas couberem na tela
    "painel_linhas": "0",
    "painel_tamanho": "normal",
    "painel_segundos_pagina": "15",
    "painel_voz": "sim",
    # Cor do prazo na linha inteira (sim) ou só no selo da coluna Situação (não)
    "painel_cor_linha": "sim",
    "painel_colunas": "abertura,titulo,usuario,local,espera,situacao",
})


def config(sessao: Session) -> dict:
    colunas = [c for c in parametros.obter(sessao, "painel_colunas").split(",") if c in COLUNAS] or ["titulo", "situacao"]
    tamanho = parametros.obter(sessao, "painel_tamanho")
    return {
        "linhas_por_pagina": parametros.obter_inteiro(sessao, "painel_linhas"),
        "tamanho": tamanho if tamanho in TAMANHOS else "normal",
        "segundos_pagina": parametros.obter_inteiro(sessao, "painel_segundos_pagina"),
        "voz": parametros.obter(sessao, "painel_voz") == "sim",
        "cor_linha": parametros.obter(sessao, "painel_cor_linha") == "sim",
        "colunas": colunas,
    }


def gravar_config(sessao: Session, dados: dict) -> None:
    """Grava a exibição do painel. Sem commit."""
    colunas = [c for c in dados["colunas"] if c in COLUNAS]
    if "titulo" not in colunas:
        raise ErroParametro("O título do chamado não pode sair do painel.")
    if dados["tamanho"] not in TAMANHOS:
        raise ErroParametro("Tamanho inválido (compacto, normal ou grande).")
    if not 0 <= dados["linhas_por_pagina"] <= 50 or not 5 <= dados["segundos_pagina"] <= 300:
        raise ErroParametro("Linhas de 0 (automático) a 50 e de 5 a 300 segundos por página.")
    for chave, valor in (("painel_linhas", dados["linhas_por_pagina"]), ("painel_tamanho", dados["tamanho"]), ("painel_segundos_pagina", dados["segundos_pagina"]),
                         ("painel_voz", "sim" if dados["voz"] else "nao"),
                         ("painel_cor_linha", "sim" if dados["cor_linha"] else "nao"), ("painel_colunas", ",".join(c for c in COLUNAS if c in colunas))):
        parametros.gravar(sessao, chave, str(valor))
    sessao.flush()
