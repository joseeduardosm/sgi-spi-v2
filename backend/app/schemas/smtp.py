# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados de entrada e saída dos servidores SMTP.
"""Formatos de entrada e saída das rotas de servidores SMTP.

A senha da conta de envio só entra pela API; nunca é devolvida em nenhuma resposta.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.usuarios import PADRAO_EMAIL

Seguranca = Literal["nenhuma", "starttls", "ssl"]


def _email(valor: str, obrigatorio: bool) -> str:
    """Apara e confere o formato do e-mail (vazio só quando não obrigatório)."""
    valor = valor.strip()
    if not valor:
        if obrigatorio:
            raise ValueError("não pode ser vazio")
        return valor
    if not PADRAO_EMAIL.match(valor):
        raise ValueError("e-mail inválido")
    return valor


class BaseServidorSmtp(BaseModel):
    """Campos comuns ao cadastro, à alteração e ao teste de um servidor."""
    nome: str = Field(..., min_length=1, max_length=100, description="Nome de identificação. Ex.: `Microsoft 365 — chamados`.")
    servidor: str = Field(..., min_length=1, max_length=255, description="Endereço do servidor. Ex.: `smtp.office365.com`.")
    porta: int = Field(587, ge=1, le=65535, description="Porta: 587 (STARTTLS), 465 (SSL) ou 25.")
    seguranca: Seguranca = Field("starttls", description="`starttls` (587/25), `ssl` (465) ou `nenhuma` (só em rede interna).")
    usuario: str = Field("", max_length=254, description="Conta de autenticação. Vazia = servidor sem autenticação (relay).")
    remetente_email: str = Field(..., max_length=254, description="E-mail do remetente (\"De\"). No Microsoft 365, a própria conta ou uma com \"Enviar como\".")
    remetente_nome: str = Field("", max_length=150, description="Nome exibido do remetente. Ex.: `Chamados SPI`.")
    responder_para: str = Field("", max_length=254, description="Endereço para respostas (Reply-To). Vazio = o remetente.")
    tempo_limite_segundos: int = Field(20, ge=3, le=120, description="Tempo máximo de espera por resposta do servidor.")
    ativo: bool = Field(False, description="Servidor usado pelo sistema para enviar e-mails. Ativar um desativa os demais.")

    @field_validator("nome", "servidor")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        """Tira espaços das pontas e recusa valores em branco."""
        valor = valor.strip()
        if not valor:
            raise ValueError("não pode ser vazio")
        return valor

    @field_validator("servidor")
    @classmethod
    def _servidor_sem_esquema(cls, valor: str) -> str:
        """Só o nome ou IP: sem `smtp://`, sem porta e sem espaços."""
        if "://" in valor or " " in valor or ":" in valor.strip("[]"):
            raise ValueError("informe só o nome ou IP do servidor (a porta vai no campo próprio)")
        return valor

    @field_validator("usuario", "remetente_nome")
    @classmethod
    def _aparar_opcional(cls, valor: str) -> str:
        """Tira espaços das pontas."""
        return valor.strip()

    @field_validator("remetente_email")
    @classmethod
    def _remetente(cls, valor: str) -> str:
        """Remetente obrigatório e com formato de e-mail."""
        return _email(valor, obrigatorio=True)

    @field_validator("responder_para")
    @classmethod
    def _responder_para(cls, valor: str) -> str:
        """Reply-To opcional, mas com formato de e-mail se preenchido."""
        return _email(valor, obrigatorio=False)

    @model_validator(mode="after")
    def _porta_e_seguranca(self) -> "BaseServidorSmtp":
        """Recusa combinações que nunca funcionam: SSL direto na 587 ou STARTTLS na 465."""
        if self.seguranca == "ssl" and self.porta == 587:
            raise ValueError("a porta 587 usa STARTTLS; para SSL direto use a porta 465")
        if self.seguranca == "starttls" and self.porta == 465:
            raise ValueError("a porta 465 usa SSL direto; para STARTTLS use a porta 587")
        return self


class CriacaoServidorSmtp(BaseServidorSmtp):
    """Cadastro: com usuário, a senha é obrigatória."""
    senha: str | None = Field(None, max_length=256, description="Senha da conta. Obrigatória quando há usuário.")

    @model_validator(mode="after")
    def _senha_com_usuario(self) -> "CriacaoServidorSmtp":
        """Usuário sem senha não autentica."""
        if self.usuario and not self.senha:
            raise ValueError("informe a senha da conta de autenticação")
        return self


class AlteracaoServidorSmtp(BaseServidorSmtp):
    """Alteração: a senha é opcional; em branco, mantém a gravada."""
    senha: str | None = Field(None, max_length=256, description="Nova senha. Vazia ou ausente preserva a atual.")


class TesteServidorNaoSalvo(CriacaoServidorSmtp):
    """Configuração ainda não salva, para `POST /api/smtp/servidores/testar`."""


class SenhaTemporaria(BaseModel):
    """Corpo opcional do teste de um servidor salvo."""
    senha: str | None = Field(None, max_length=256, description="Senha para usar só neste teste. Vazia usa a senha salva.")


class EnvioTeste(BaseModel):
    """Destinatário do e-mail de teste."""
    destinatario: str = Field(..., max_length=254, description="E-mail que vai receber a mensagem de teste.")

    @field_validator("destinatario")
    @classmethod
    def _destinatario(cls, valor: str) -> str:
        """Destinatário obrigatório e com formato de e-mail."""
        return _email(valor, obrigatorio=True)


class LeituraServidorSmtp(BaseModel):
    """Configuração do servidor. A senha nunca é devolvida (só se há uma gravada)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    servidor: str
    porta: int
    seguranca: Seguranca
    usuario: str
    possui_senha: bool = Field(..., description="Se há senha gravada (o valor nunca é devolvido).")
    remetente_email: str
    remetente_nome: str
    responder_para: str
    tempo_limite_segundos: int
    ativo: bool
    ultimo_teste_em: datetime | None = Field(None, description="Data do último teste de conexão.")
    ultimo_teste_ok: bool | None = None
    ultima_latencia_ms: int | None = Field(None, description="Tempo do último teste (conexão + segurança + autenticação), em ms.")
    ultimo_erro: str | None = Field(None, description="Mensagem do último teste com falha.")
    ultimo_envio_em: datetime | None = Field(None, description="Data do último e-mail de teste.")
    ultimo_envio_ok: bool | None = None
    ultimo_envio_para: str | None = None
    ultimo_envio_mensagem: str | None = None
    criado_em: datetime
    atualizado_em: datetime


class ResultadoSmtp(BaseModel):
    """Resultado de um teste de conexão ou de um envio de teste."""
    sucesso: bool
    latencia_ms: int = Field(..., description="Tempo total da operação, em ms.")
    mensagem: str
    id_mensagem: str | None = Field(None, description="Message-ID do e-mail enviado (só no envio).")
