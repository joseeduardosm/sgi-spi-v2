# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler a configuração da aplicação das variáveis de ambiente e do backend/.env.
"""Configuração da aplicação, lida de variáveis de ambiente e do arquivo backend/.env.

Cada atributo de `Configuracao` corresponde a uma variável de ambiente com o mesmo nome em
maiúsculas (ex.: `url_banco_dados` ↔ `URL_BANCO_DADOS`). Variáveis do sistema têm prioridade
sobre o arquivo `.env`. Os valores sem padrão são obrigatórios: a API não sobe sem eles.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pasta `backend/` (dois níveis acima deste arquivo: app/core/ → app/ → backend/)
DIRETORIO_BACKEND = Path(__file__).resolve().parents[2]


class Configuracao(BaseSettings):
    """Todas as configurações da API, validadas pelo Pydantic na inicialização.

    Campos `SecretStr` (chaves e hashes) não aparecem em logs nem em mensagens de erro: o valor
    real só é lido com `.get_secret_value()`.
    """

    model_config = SettingsConfigDict(
        # Arquivo .env ao lado do código do backend
        env_file=DIRETORIO_BACKEND / ".env",
        env_file_encoding="utf-8",
        # Variáveis desconhecidas no .env são ignoradas em vez de derrubar a inicialização
        extra="ignore",
    )

    # Identificação da aplicação e prefixo comum de todas as rotas (/api/...)
    nome_aplicacao: str = "contratos-spi"
    versao_aplicacao: str = "0.1.0"
    ambiente: str = "desenvolvimento"
    prefixo_api: str = "/api"

    # JWT
    # Chave que assina os tokens de acesso; trocá-la invalida todas as sessões abertas
    chave_secreta_jwt: SecretStr = Field(..., min_length=32)
    algoritmo_jwt: str = "HS256"
    # Validade do token de acesso (depois disso o usuário precisa entrar de novo)
    minutos_expiracao_token: int = Field(60, gt=0)

    # Banco de dados (PostgreSQL). Ex.: postgresql+psycopg://usuario:senha@localhost:5432/banco
    url_banco_dados: str

    # Chave Fernet usada para cifrar a senha de bind dos diretórios LDAP.
    # Trocar a chave torna ilegíveis as senhas já gravadas (será preciso informá-las de novo).
    chave_cifra_ldap: SecretStr
    # Intervalo da sincronização automática do diretório ativo. 0 desativa a rotina.
    intervalo_sincronizacao_ldap_minutos: int = Field(15, ge=0, le=1440)
    # Tempo máximo de espera por uma resposta do servidor LDAP
    tempo_limite_ldap_segundos: int = Field(5, gt=0, le=60)

    # Conta administrativa principal (SuperRoot local). A senha é armazenada somente como hash
    # bcrypt e é aplicada ao usuário no banco a cada inicialização da API.
    login_admin: str = "root"
    hash_senha_admin: SecretStr
    nome_admin: str = "Administrador"

    # Anexos (PDFs) guardados fora do banco. O banco guarda só os metadados e a chave relativa
    # do arquivo neste diretório (AAAA/MM/<uuid>.pdf).
    anexos_diretorio: Path = DIRETORIO_BACKEND.parent / "dados" / "anexos"
    # Tamanho máximo de cada PDF enviado; o Nginx precisa aceitar um pouco mais que isso
    anexos_tamanho_maximo_mb: int = Field(25, gt=0, le=200)

    # Importação do Módulo de Contratos do SGI SPI (botão do SuperRoot em /contratos). As senhas são
    # digitadas na tela a cada execução e nunca gravadas.
    migracao_sgi_host: str = "10.23.1.220"
    migracao_sgi_usuario: str = "administrador"
    migracao_local_host: str = "127.0.0.1"
    migracao_local_usuario: str = "administrador"
    # Pasta onde os dados extraídos do SGI ficam guardados durante a importação
    migracao_diretorio: Path = DIRETORIO_BACKEND.parent / "dados" / "migracao-sgi"

    # Origens liberadas para CORS (apenas quando o frontend não é servido pelo mesmo Nginx)
    origens_cors: list[str] = []


@lru_cache
def obter_configuracao() -> Configuracao:
    """Configuração única da aplicação.

    O `lru_cache` faz o arquivo .env ser lido uma só vez: as chamadas seguintes devolvem o mesmo
    objeto, sem custo. Os testes alteram atributos desse objeto para simular outras configurações.
    """
    return Configuracao()
