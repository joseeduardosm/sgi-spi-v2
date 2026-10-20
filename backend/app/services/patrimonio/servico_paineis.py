# Criado por José Eduardo Santana Martins
# Este arquivo serve para calcular os painéis do Patrimônio: indicadores do topo, agrupamento (andar, sala, setor, grupo) e bens fora de garantia.
"""Painéis do Patrimônio.

O bem baixado sai dos painéis. Bens com "dados contábeis pendentes" entram na contagem, mas ficam fora dos totais de valor e aparecem numa lista
própria. O valor que vale é o atual informado no bem (normalmente o do SAM); sem ele, o calculado pela depreciação.
"""

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo
from app.models.patrimonio import Baixa, Bem, Classificacao, Movimentacao
from app.services.patrimonio import servico_bens
from app.services.patrimonio.servico_localizacoes import rotulo_curto

AGRUPAMENTOS = ("andar", "sala", "setor", "grupo")


def _bens_do_painel(sessao: Session, situacao: str | None, conservacao: int | None, garantia: str | None) -> list[Bem]:
    consulta = select(Bem).where(Bem.situacao != "baixado").options(*servico_bens.OPCOES_AO_CARREGAR)
    if situacao:
        consulta = consulta.where(Bem.situacao == situacao)
    if conservacao:
        consulta = consulta.where(Bem.conservacao == conservacao)
    bens = list(sessao.scalars(consulta))
    if garantia:
        bens = [b for b in bens if servico_bens.situacao_garantia(b) == garantia]
    return bens


def _chave(bem: Bem, agrupar_por: str) -> tuple[str, str]:
    """Chave de ordenação e rótulo do grupo."""
    sala = bem.localizacao
    if agrupar_por == "andar":
        if sala.andar is None:
            return ("zz", "Sem andar")
        rotulo = "Subsolo" if sala.andar == -1 else "Térreo" if sala.andar == 0 else f"{sala.andar}º andar"
        return (f"{sala.andar + 1:03d}", rotulo)
    if agrupar_por == "sala":
        return (sala.codigo or sala.nome, rotulo_curto(sala))
    if agrupar_por == "setor":
        nome = sala.setor.nome if sala.setor else "Sem setor"
        return (nome.lower(), nome)
    nome = bem.grupo.nome if bem.grupo else "Sem grupo"
    return (nome.lower(), nome)


def painel(sessao: Session, *, agrupar_por: str = "andar", situacao: str | None = None, conservacao: int | None = None, garantia: str | None = None) -> dict:
    hoje = hoje_sao_paulo()
    bens = _bens_do_painel(sessao, situacao, conservacao, garantia)
    aquisicao = atual = Decimal(0)
    grupos: dict[tuple[str, str], dict] = defaultdict(lambda: {"quantidade": 0, "valor": Decimal(0)})
    fora_garantia, pendentes = [], []
    for bem in bens:
        grupo = grupos[_chave(bem, agrupar_por if agrupar_por in AGRUPAMENTOS else "andar")]
        grupo["quantidade"] += 1
        if bem.dados_contabeis_pendentes:
            pendentes.append(bem)
        else:
            valor = servico_bens.valor_efetivo(bem, hoje) or Decimal(0)
            aquisicao += bem.valor_aquisicao or 0
            atual += valor
            grupo["valor"] += valor
        if servico_bens.situacao_garantia(bem, hoje) == "vencida":
            fora_garantia.append(bem)
    em_aberto = sessao.scalar(select(func.count(Movimentacao.id)).where(Movimentacao.status.in_(("pendente", "autorizada")))) or 0
    solicitacoes = (sessao.scalar(select(func.count(Movimentacao.id)).where(Movimentacao.status == "pendente")) or 0) \
        + (sessao.scalar(select(func.count(Classificacao.id)).where(Classificacao.status == "pendente")) or 0) \
        + (sessao.scalar(select(func.count(Baixa.id)).where(Baixa.status == "aguardando_aceite")) or 0)
    return {
        "indicadores": {
            "total_bens": len(bens), "valor_aquisicao": aquisicao, "valor_atual": atual, "fora_garantia": len(fora_garantia),
            "aguardando_baixa": sum(1 for b in bens if b.situacao in ("inservivel", "extraviado")), "solicitacoes_pendentes": solicitacoes,
            "dados_contabeis_pendentes": len(pendentes), "movimentacoes_em_aberto": em_aberto,
        },
        "agrupar_por": agrupar_por,
        "grupos": [{"chave": k[0], "rotulo": k[1], **v} for k, v in sorted(grupos.items())],
        "fora_garantia": [linha_garantia(b, hoje) for b in sorted(fora_garantia, key=lambda b: servico_bens.garantia_fim(b) or hoje)],
        "vencendo_90_dias": [linha_garantia(b, hoje) for b in bens if servico_bens.vence_em_90_dias(b, hoje)],
        "contabeis_pendentes": [{"id": b.id, "chapa": b.chapa, "rotulo": b.rotulo, "descricao": b.descricao, "sala": rotulo_curto(b.localizacao)} for b in pendentes],
    }


def linha_garantia(bem: Bem, hoje) -> dict:
    fim = servico_bens.garantia_fim(bem)
    return {"id": bem.id, "chapa": bem.chapa, "rotulo": bem.rotulo, "descricao": bem.descricao, "sala": rotulo_curto(bem.localizacao), "fim_garantia": fim,
            "dias": (fim - hoje).days if fim else None, "vence_em_90_dias": servico_bens.vence_em_90_dias(bem, hoje)}


def bens_do_grupo(sessao: Session, agrupar_por: str, chave: str, **filtros) -> list[Bem]:
    """Lista dos bens de uma barra do gráfico (clique no grupo)."""
    bens = _bens_do_painel(sessao, filtros.get("situacao"), filtros.get("conservacao"), filtros.get("garantia"))
    return [b for b in bens if _chave(b, agrupar_por)[0] == chave]
