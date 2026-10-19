# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de login, sessão e perfil.
"""Formatos de entrada e saída do login e da sessão."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequisicaoLogin(BaseModel):
    """Corpo do `POST /api/autenticacao/login`."""

    # Exemplo exibido na documentação interativa (/api/docs)
    model_config = ConfigDict(json_schema_extra={"examples": [{"login": "root", "senha": "********"}]})

    login: str = Field(..., min_length=1, max_length=150, description="Login local, `sAMAccountName` ou `userPrincipalName`.")
    senha: str = Field(..., min_length=1, max_length=128, description="Senha em texto puro (trafega apenas via HTTPS em produção).")


class PerfilSessao(BaseModel):
    """Perfil de acesso do usuário (para o menu do usuário)."""
    id: int = Field(..., description="Identificador do perfil.")
    nome: str = Field(..., description="Nome do perfil.")


class PersonificadorSessao(BaseModel):
    """SuperRoot que está personificando o usuário da sessão."""
    id: int
    login: str
    nome_completo: str


class UsuarioSessao(BaseModel):
    """Resumo do usuário logado, usado pelo frontend para montar o menu e aplicar restrições."""
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
    conta_root: bool = Field(False, description="Conta administrativa principal (login `LOGIN_ADMIN`): libera a tela Notificações do sistema.")
    tema: Literal["claro", "escuro", "auto"] = Field("auto", description="Tema da interface escolhido pelo usuário (`auto` segue o sistema operacional).")
    perfis: list[PerfilSessao] = Field(default_factory=list, description="Perfis de acesso ativos do usuário (entre eles ele alterna no menu do usuário).")
    perfil_ativo: PerfilSessao | None = Field(None, description="Perfil que vale nesta sessão (o escolhido ou o padrão); nulo se o usuário não tem perfis.")
    personificado_por: PersonificadorSessao | None = Field(
        None, description="Só na personificação: o SuperRoot real que está usando a sessão como este usuário (o frontend mostra a faixa \"Parar de personificar\").")


class RespostaToken(BaseModel):
    """Resposta do login: o token JWT e os dados do usuário, para não precisar de outra chamada."""
    token_acesso: str = Field(..., description="JWT a ser enviado no cabeçalho `Authorization: Bearer <token>`.")
    tipo_token: str = Field("bearer", description="Sempre `bearer`.")
    expira_em_segundos: int = Field(..., description="Validade do token em segundos a partir da emissão.")
    expira_em: datetime = Field(..., description="Instante de expiração do token (UTC, ISO 8601).")
    usuario: UsuarioSessao


class PreferenciaTema(BaseModel):
    """Corpo do `PUT /api/autenticacao/tema`."""

    tema: Literal["claro", "escuro", "auto"] = Field(..., description="`claro`, `escuro` ou `auto` (segue o tema do sistema operacional).")


class PedidoPerfilAtivo(BaseModel):
    """Corpo do `POST /api/autenticacao/perfil-ativo`."""
    perfil_id: int = Field(..., description="Perfil (ativo e do próprio usuário) que passa a valer na sessão.")


class PedidoPersonificar(BaseModel):
    """Corpo do `POST /api/autenticacao/personificar`."""
    usuario_id: int = Field(..., description="Usuário ativo cujo acesso o SuperRoot quer testar.")
