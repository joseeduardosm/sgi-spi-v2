"""Configuração da aplicação, lida de variáveis de ambiente e do arquivo backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DIRETORIO_BACKEND = Path(__file__).resolve().parents[2]


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DIRETORIO_BACKEND / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nome_aplicacao: str = "contratos-spi"
    versao_aplicacao: str = "0.1.0"
    ambiente: str = "desenvolvimento"
    prefixo_api: str = "/api"

    # JWT
    chave_secreta_jwt: SecretStr = Field(..., min_length=32)
    algoritmo_jwt: str = "HS256"
    minutos_expiracao_token: int = Field(60, gt=0)

    # Banco de dados (PostgreSQL). Ex.: postgresql+psycopg://usuario:senha@localhost:5432/banco
    url_banco_dados: str

    # Chave Fernet usada para cifrar a senha de bind dos diretórios LDAP.
    # Trocar a chave torna ilegíveis as senhas já gravadas (será preciso informá-las de novo).
    chave_cifra_ldap: SecretStr
    # Intervalo da sincronização automática do diretório ativo. 0 desativa a rotina.
    intervalo_sincronizacao_ldap_minutos: int = Field(15, ge=0, le=1440)
    tempo_limite_ldap_segundos: int = Field(5, gt=0, le=60)

    # Conta administrativa principal (SuperRoot local). A senha é armazenada somente como hash
    # bcrypt e é aplicada ao usuário no banco a cada inicialização da API.
    login_admin: str = "root"
    hash_senha_admin: SecretStr
    nome_admin: str = "Administrador"

    # Anexos (PDFs) guardados fora do banco. O banco guarda só os metadados e a chave relativa
    # do arquivo neste diretório (AAAA/MM/<uuid>.pdf).
    anexos_diretorio: Path = DIRETORIO_BACKEND.parent / "dados" / "anexos"
    anexos_tamanho_maximo_mb: int = Field(25, gt=0, le=200)

    # Importação do Módulo de Contratos do SGI SPI (botão do SuperRoot em /contratos). As senhas são
    # digitadas na tela a cada execução e nunca gravadas.
    migracao_sgi_host: str = "10.23.1.220"
    migracao_sgi_usuario: str = "administrador"
    migracao_local_host: str = "127.0.0.1"
    migracao_local_usuario: str = "administrador"
    migracao_diretorio: Path = DIRETORIO_BACKEND.parent / "dados" / "migracao-sgi"

    # Origens liberadas para CORS (apenas quando o frontend não é servido pelo mesmo Nginx)
    origens_cors: list[str] = []


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
