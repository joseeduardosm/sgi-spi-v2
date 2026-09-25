# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de login, sessão e perfil.

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequisicaoLogin(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"login": "root", "senha": "********"}]})

    login: str = Field(..., min_length=1, max_length=150, description="Login local, `sAMAccountName` ou `userPrincipalName`.")
    senha: str = Field(..., min_length=1, max_length=128, description="Senha em texto puro (trafega apenas via HTTPS em produção).")


class UsuarioSessao(BaseModel):
    id: int = Field(..., description="Identificador do usuário.")
    login: str = Field(..., description="Login.")
    nome_completo: str = Field(..., description="Nome de exibição.")
    papeis: list[str] = Field(..., description="Papéis do usuário. Ex.: `SuperRoot`.")
    origem: str = Field(..., description="Origem da conta: `local`, `ldap` ou `local_ldap`.")
    perfil_restrito: bool = Field(
        False,
        description="Perfil incompleto ou revalidação vencida: o acesso fica restrito à atualização do próprio perfil.",
    )
    campos_pendentes: list[str] = Field(default_factory=list, description="Campos obrigatórios do perfil não preenchidos.")
    revisao_obrigatoria: bool = Field(False, description="Revalidação do perfil vencida (mais de 30 dias) ou nunca feita.")


class RespostaToken(BaseModel):
    token_acesso: str = Field(..., description="JWT a ser enviado no cabeçalho `Authorization: Bearer <token>`.")
    tipo_token: str = Field("bearer", description="Sempre `bearer`.")
    expira_em_segundos: int = Field(..., description="Validade do token em segundos a partir da emissão.")
    expira_em: datetime = Field(..., description="Instante de expiração do token (UTC, ISO 8601).")
    usuario: UsuarioSessao
