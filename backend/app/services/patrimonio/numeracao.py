"""
===============================================================================
ARQUIVO: numeracao.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Numerar (#1, #2...) as listas de inservíveis, de extraviados e as baixas do
Patrimônio numa sequência única, compartilhada entre os três tipos.

RESUMO TÉCNICO:
Uma única função, proximo_numero_relacao, que consulta o maior número já
usado em Classificacao (listas) e em Baixa e devolve o seguinte. Não grava
nada: quem chama atribui o número ao registro e faz o commit.

FINALIDADE DE NEGÓCIO:
Cada relação de bens enviada para decisão ganha um número que nunca se
repete, o que facilita citar a relação em processos e conversas ("lista
#12", "baixa #13") sem ambiguidade.

CONTEXTO NO SISTEMA:
Usado pelos serviços servico_classificacoes.py e servico_baixas.py ao enviar
uma lista ou baixa. Lê as tabelas dos modelos Classificacao e Baixa
(app.models.patrimonio).

===============================================================================
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.patrimonio import Baixa, Classificacao


def proximo_numero_relacao(sessao: Session) -> int:
    """Próximo número livre, contando listas de classificação e baixas juntas (o mesmo # nunca se repete).

    Parâmetros:
        sessao: sessão do SQLAlchemy (``Session``), a "conversa" aberta com o
            banco dentro da requisição.

    Retorno:
        O maior número existente entre listas e baixas, mais 1 (ou 1 quando
        ainda não há nenhuma). Só lê o banco; não grava nada.
    """
    # MAX() devolve NULL (None no Python) quando a tabela está vazia; o "or 0" trata esse caso
    maior_lista = sessao.scalar(select(func.max(Classificacao.numero))) or 0
    maior_baixa = sessao.scalar(select(func.max(Baixa.numero))) or 0
    # As duas sequências são uma só: o próximo número vem depois do maior dos dois
    return max(maior_lista, maior_baixa) + 1
