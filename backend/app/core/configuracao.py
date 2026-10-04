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
    nome_aplicacao: str = "sgi-spi"
    versao_aplicacao: str = "0.1.0"
    ambiente: str = "desenvolvimento"
    prefixo_api: str = "/api"

    # JWT
    # Chave que assina os tokens de acesso; trocá-la invalida todas as sessões abertas
    chave_secreta_jwt: SecretStr = Field(..., min_length=32)
    algoritmo_jwt: str = "HS256"
    # Validade do token de acesso (depois disso o usuário precisa entrar de novo)
    minutos_expiracao_token: int = Field(60, gt=0)
    # Renovação deslizante: quem usa o sistema recebe um token novo quando faltam menos de N minutos para vencer
    # (a sessão só cai depois de `minutos_expiracao_token` de inatividade). `horas_sessao_maxima` > 0 limita a duração
    # total da sessão mesmo com uso contínuo (0 = sem limite).
    minutos_renovacao_token: int = Field(30, ge=1)
    horas_sessao_maxima: int = Field(0, ge=0)

    # Banco de dados (PostgreSQL). Ex.: postgresql+psycopg://usuario:senha@localhost:5432/banco
    url_banco_dados: str

    # Chave Fernet usada para cifrar a senha de bind dos diretórios LDAP.
    # Trocar a chave torna ilegíveis as senhas já gravadas (será preciso informá-las de novo).
    chave_cifra_ldap: SecretStr
    # Intervalo da sincronização automática do diretório ativo. 0 desativa a rotina.
    intervalo_sincronizacao_ldap_minutos: int = Field(15, ge=0, le=1440)
    # Hora (0 a 23) em que o parabéns automático de aniversário é enviado. -1 desativa a rotina.
    hora_parabens_aniversario: int = Field(8, ge=-1, le=23)
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

    # Endereço do sistema usado nos links dos e-mails (ex.: link direto para a etapa da competência)
    url_publica: str = "https://portal.spi.sp.gov.br"
    # Tomador que deve constar nas notas fiscais (SPI) e setor do Financeiro, que confere as retenções
    tomador_cnpj: str = "96480850000103"
    setor_financeiro: str = "Diretoria de Orçamento e Finanças"
    # Setor da CGP (Coordenadoria de Gestão de Pessoas): administra o Módulo RH (inclui os setores filhos)
    setor_cgp: str = "Coordenadoria de Gestão de Pessoas"

    # Contratações (ETP e TR): versões guardadas por documento, minutos sem edição que abrem uma "sessão" nova (a versão automática
    # guarda o estado de antes da primeira edição) e dias de revisão parada até o aviso ao criador
    contratacoes_limite_versoes: int = Field(100, ge=10)
    contratacoes_sessao_minutos: int = Field(30, ge=1)
    contratacoes_dias_aviso: int = Field(5, ge=1)

    # Protocolo: dias de reserva sem documento anexado até o aviso ao responsável (e de novo ao dobro)
    protocolo_dias_aviso: int = Field(5, ge=1)

    # Assinatura de e-mail institucional (imagem e HTML): textos fixos e prefixo do telefone (ramal = últimos dígitos)
    assinatura_secretaria: str = "Secretaria de Parcerias em Investimentos – SPI"
    assinatura_endereco: str = "Rua Iaiá, 126 - Itaim Bibi"
    assinatura_cidade: str = "São Paulo/SP – CEP 04542-906"
    assinatura_telefone_prefixo: str = "(11) 3702-"

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
