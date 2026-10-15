# Criado por José Eduardo Santana Martins
# Este arquivo serve para numerar (#1, #2…) as listas de inservíveis, de extraviados e as baixas numa sequência única.
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.patrimonio import Baixa, Classificacao


def proximo_numero_relacao(sessao: Session) -> int:
    """Próximo número livre, contando listas de classificação e baixas juntas (o mesmo # nunca se repete)."""
    maior_lista = sessao.scalar(select(func.max(Classificacao.numero))) or 0
    maior_baixa = sessao.scalar(select(func.max(Baixa.numero))) or 0
    return max(maior_lista, maior_baixa) + 1
