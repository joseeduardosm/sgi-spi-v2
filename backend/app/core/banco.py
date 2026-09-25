# Criado por José Eduardo Santana Martins
# Este arquivo serve para configurar a conexão com o banco (SQLAlchemy) e a sessão usada por requisição.
"""Engine, sessão e classe base do SQLAlchemy."""

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.configuracao import obter_configuracao


class Base(DeclarativeBase):
    pass


def agora_utc() -> datetime:
    return datetime.now(UTC)


motor = create_engine(obter_configuracao().url_banco_dados, pool_pre_ping=True)

if motor.dialect.name == "sqlite":
    # O SQLite (usado nos testes) só verifica chaves estrangeiras quando pedido, como o PostgreSQL faz sempre

    @event.listens_for(motor, "connect")
    def _ativar_chaves_estrangeiras(conexao, _registro) -> None:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
FabricaSessao = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão de banco por requisição."""
    sessao = FabricaSessao()
    try:
        yield sessao
    finally:
        sessao.close()
