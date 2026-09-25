"""Exceções de domínio do módulo de contratos, convertidas em respostas HTTP pelas rotas."""


class RegistroNaoEncontrado(Exception):
    """O registro pedido não existe (vira 404). `o_que` compõe a mensagem: "Contrato não encontrado."."""

    def __init__(self, o_que: str) -> None:
        super().__init__(o_que)
        self.o_que = o_que


class ErroRegraContrato(Exception):
    """Regra de negócio violada: 409 quando `conflito` (duplicidade/concorrência), senão 400."""

    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


class SemPermissaoContrato(Exception):
    """Usuário com ACL suficiente, mas sem vínculo com o contrato (vira 403 `acesso_negado`)."""
