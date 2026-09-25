# Criado por José Eduardo Santana Martins
# Este arquivo serve para configurar a conexão com o banco (SQLAlchemy) e a sessão usada por requisição.
"""Engine, sessão e classe base do SQLAlchemy.

Todo acesso ao banco passa por aqui:
- `Base` é a classe-mãe de todos os modelos (tabelas) em `app/models/`;
- `motor` é a conexão com o PostgreSQL (ou com o SQLite nos testes);
- `obter_sessao` entrega uma sessão por requisição HTTP e a fecha no final.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.configuracao import obter_configuracao


class Base(DeclarativeBase):
    """Classe-mãe dos modelos: o SQLAlchemy registra aqui todas as tabelas declaradas.

    O Alembic usa `Base.metadata` para comparar os modelos com o banco e gerar migrações.
    """

    pass


def agora_utc() -> datetime:
    """Data e hora atuais em UTC.

    Todas as datas com hora são gravadas em UTC, para não depender do fuso do servidor; as telas
    convertem para o horário de São Paulo na exibição.
    """
    return datetime.now(UTC)


# Conexão com o banco, a partir de URL_BANCO_DADOS. `pool_pre_ping` testa a conexão antes de usá-la,
# evitando erro quando o PostgreSQL fechou conexões ociosas (ex.: depois de uma reinicialização).
motor = create_engine(obter_configuracao().url_banco_dados, pool_pre_ping=True)

if motor.dialect.name == "sqlite":
    # O SQLite (usado nos testes) só verifica chaves estrangeiras quando pedido, como o PostgreSQL faz sempre

    @event.listens_for(motor, "connect")
    def _ativar_chaves_estrangeiras(conexao, _registro) -> None:
        """Liga a verificação de chaves estrangeiras em cada nova conexão SQLite."""
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
# Fábrica de sessões. `autoflush=False` evita gravações implícitas no meio das regras de negócio;
# `expire_on_commit=False` mantém os objetos legíveis depois do commit (as rotas os usam na resposta).
FabricaSessao = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão de banco por requisição.

    O `yield` entrega a sessão à rota; o bloco `finally` garante que ela seja fechada mesmo quando
    a rota termina com erro, devolvendo a conexão ao pool.
    """
    sessao = FabricaSessao()
    try:
        yield sessao
    finally:
        sessao.close()
