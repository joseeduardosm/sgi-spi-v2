# Criado por José Eduardo Santana Martins
# Este arquivo serve para configurar o Alembic (ferramenta de migrações) para usar o banco e os modelos da aplicação.
"""Arquivo de ambiente do Alembic, executado a cada comando (`alembic upgrade head`, `revision` etc.).

Ele diz ao Alembic qual banco usar (a mesma URL da aplicação, vinda do .env) e qual é o "retrato"
esperado das tabelas (`Base.metadata`, montado a partir dos modelos em `app/models`). Com isso, o
`--autogenerate` compara o retrato com o banco real e propõe a migração.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 - registra os modelos em Base.metadata
from app.core.banco import Base
from app.core.configuracao import obter_configuracao

# Objeto de configuração lido do alembic.ini
config = context.config
# Usa a URL do banco da aplicação; o "%" é dobrado porque o arquivo .ini trata "%" como especial
config.set_main_option("sqlalchemy.url", obter_configuracao().url_banco_dados.replace("%", "%%"))
# Liga o log configurado no alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Retrato das tabelas esperadas (todas as classes de app/models)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline: em vez de executar, gera o SQL (útil para revisar ou aplicar manualmente)."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online (o normal): conecta no banco e aplica as migrações em uma transação."""
    # NullPool: abre uma conexão só para a migração, sem manter um pool
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # compare_type=True faz o autogenerate perceber também mudanças de tipo das colunas
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


# O Alembic decide o modo pelo comando usado (`--sql` = offline)
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
