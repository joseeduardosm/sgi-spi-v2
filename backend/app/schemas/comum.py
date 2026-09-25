# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir os formatos de erro e de resposta compartilhados pela API.

from pydantic import BaseModel, Field


class RespostaErro(BaseModel):
    detalhe: str = Field(..., description="Mensagem de erro legível, em português.")
    codigo: str = Field(
        ...,
        description=(
            "Código do erro: `nao_autenticado`, `acesso_negado`, `revisao_perfil_obrigatoria`, `acl_negado`, "
            "`nao_encontrado`, `invalido`, `conflito`, `validacao`, `servico_indisponivel`, `erro_interno`."
        ),
    )


class ErroCampo(BaseModel):
    campo: str | None = Field(None, description="Campo com erro (ex.: `perfil.email`). Nulo para erro geral.")
    mensagem: str = Field(..., description="Motivo, em português.")


class RespostaErroValidacao(RespostaErro):
    """Resposta 422: dados fora do schema."""

    erros: list[ErroCampo] = Field(..., description="Erros por campo.")


class RespostaErroAcl(RespostaErro):
    """Resposta 403 com `codigo = acl_negado`."""

    recurso: str = Field(..., description="Slug do recurso.")
    nivel_exigido: str = Field(..., description="Nível exigido.")
    nivel_efetivo: str | None = Field(None, description="Nível efetivo do usuário (nulo = nenhum).")


class RespostaSaude(BaseModel):
    situacao: str = Field(..., description="`ok` quando a API está respondendo.")
    versao: str = Field(..., description="Versão da API.")
