"""
===============================================================================
ARQUIVO: erros.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir as exceções de regra de negócio (domínio) do módulo de contratos.

RESUMO TÉCNICO:
Os serviços não conhecem HTTP: só levantam estas exceções com uma mensagem
pronta para o usuário. A função `traduzir_erros` (em
`api/routes/contratos/comum.py`) as transforma em 404 (`RegistroNaoEncontrado`),
400 ou 409 (`ErroRegraContrato`) e 403 (`SemPermissaoContrato`).

FINALIDADE DE NEGÓCIO:
Garante que toda regra violada (ex.: valor inválido, registro duplicado,
pessoa fora da equipe do contrato) chegue à tela com uma mensagem clara em
português, em vez de um erro técnico.

CONTEXTO NO SISTEMA:
Usado por todos os serviços em `services/contratos/` e traduzido pelas rotas
de `api/routes/contratos/`. A resposta de erro segue o padrão da API:
`{"detalhe", "codigo"}`.

===============================================================================
"""


class RegistroNaoEncontrado(Exception):
    """O registro pedido não existe (vira 404). `o_que` compõe a mensagem: "Contrato não encontrado."."""

    def __init__(self, o_que: str) -> None:
        """Guarda o nome do registro (ex.: "Contrato") para a rota montar a mensagem."""
        super().__init__(o_que)
        self.o_que = o_que


class ErroRegraContrato(Exception):
    """Regra de negócio violada: 409 quando `conflito` (duplicidade/concorrência), senão 400."""

    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        """`mensagem` vai direto para o usuário; `conflito=True` faz a rota responder 409."""
        super().__init__(mensagem)
        self.conflito = conflito


class SemPermissaoContrato(Exception):
    """Usuário com ACL suficiente, mas sem vínculo com o contrato (vira 403 `acesso_negado`).

    ACL é o controle de acesso por módulo (Leitura, Modificação, Controle total).
    Mesmo com ACL, quem não faz parte da equipe do contrato não pode mexer nele.
    """
