import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseDiretorio(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100, description="Nome de identificação do diretório.")
    servidor: str = Field(..., min_length=1, max_length=255, description="Servidor (nome ou IP).")
    porta: int = Field(389, ge=1, le=65535, description="Porta. 389 para LDAP, 636 para LDAPS.")
    usar_ssl: bool = Field(False, description="Usar LDAPS (SSL/TLS).")
    base_dn: str = Field(..., min_length=1, max_length=500, description="Base DN das buscas. Ex.: `DC=spi,DC=sp,DC=gov,DC=br`.")
    bind_dn: str = Field(..., min_length=1, max_length=500, description="Conta técnica: DN, `usuario@dominio` ou `DOMINIO\\usuario`.")
    ativo: bool = Field(False, description="Ativar este diretório. Ativar um desativa os demais.")

    @field_validator("nome", "servidor", "base_dn", "bind_dn")
    @classmethod
    def _aparar(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("não pode ser vazio")
        return valor


class CriacaoDiretorio(BaseDiretorio):
    senha_bind: str = Field(..., min_length=1, max_length=256, description="Senha da conta técnica. Obrigatória no cadastro.")


class AlteracaoDiretorio(BaseDiretorio):
    senha_bind: str | None = Field(None, max_length=256, description="Nova senha da conta técnica. Vazia ou ausente preserva a atual.")


class TesteDiretorioNaoSalvo(BaseDiretorio):
    """Configuração ainda não salva, para `POST /api/ldap/diretorios/testar`."""

    senha_bind: str = Field(..., min_length=1, max_length=256)


class SenhaBindTemporaria(BaseModel):
    senha_bind: str | None = Field(None, max_length=256, description="Senha para usar só neste teste. Vazia usa a senha salva.")


class LeituraDiretorio(BaseModel):
    """Configuração do diretório. A senha de bind nunca é devolvida."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    servidor: str
    porta: int
    usar_ssl: bool
    base_dn: str
    bind_dn: str
    ativo: bool
    ultimo_teste_em: datetime | None = Field(None, description="Data do último teste de conectividade.")
    ultimo_teste_ok: bool | None = Field(None, description="Resultado do último teste.")
    ultima_latencia_ms: int | None = Field(None, description="Tempo de resposta do último teste, em ms.")
    ultimo_erro: str | None = Field(None, description="Mensagem de erro do último teste com falha.")
    ultima_sincronizacao_em: datetime | None = None
    ultima_sincronizacao_ok: bool | None = None
    ultima_sincronizacao_mensagem: str | None = Field(None, description="Resumo ou erro da última sincronização.")
    criado_em: datetime
    atualizado_em: datetime


class ResultadoTeste(BaseModel):
    sucesso: bool
    latencia_ms: int = Field(..., description="Tempo de conexão + bind + validação da Base DN, em ms.")
    mensagem: str


class ResultadoSincronizacao(BaseModel):
    encontrados: int = Field(..., description="Identidades encontradas no diretório.")
    criados: int = Field(..., description="Contas corporativas criadas.")
    atualizados: int = Field(..., description="Contas existentes atualizadas.")
    desativados: int = Field(..., description="Contas exclusivamente LDAP desativadas por não constarem mais no diretório.")
    ignorados: int = Field(..., description="Identidades ignoradas por existir conta local homônima não vinculada.")
    sincronizado_em: datetime


class DiagnosticoLogin(BaseModel):
    encontrado: bool
    entradas: int
    mensagem: str
    login: str | None = None
    nome_principal: str | None = Field(None, description="userPrincipalName.")
    dn: str | None = None
