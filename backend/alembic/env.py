"""
===============================================================================
ARQUIVO: env.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Configurar o Alembic (a ferramenta de migrações do banco) para usar o mesmo
banco e os mesmos modelos da aplicação. É executado a cada comando do Alembic
(`alembic upgrade head`, `alembic revision --autogenerate` etc.).

RESUMO TÉCNICO:
Lê a URL do banco da configuração da aplicação (.env), liga o log do
alembic.ini e aponta `target_metadata` para `Base.metadata` (o retrato das
tabelas montado a partir de `app/models`). Define os modos offline (gera SQL
sem conectar) e online (conecta e aplica em transação, com `compare_type`
ligado para o autogenerate perceber mudança de tipo de coluna).

FINALIDADE DE NEGÓCIO:
Mantém o banco de produção do SGI SPI sempre igual ao que o código espera,
aplicando as mudanças de estrutura de forma ordenada e reversível, sem
intervenção manual em tabelas que guardam contratos, RH, patrimônio etc.

CONTEXTO NO SISTEMA:
Usado pelo Alembic junto com `backend/alembic.ini` e as revisões em
`backend/alembic/versions/`. Importa `app.models` (registra os modelos),
`app.core.banco.Base` e `app.core.configuracao.obter_configuracao`.

===============================================================================
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar o pacote de modelos faz cada classe se registrar em Base.metadata;
# sem isso o autogenerate acharia que nenhuma tabela deveria existir.
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
    """Modo offline: em vez de executar, gera o SQL das migrações.

    Útil para revisar o que será feito ou para entregar o script a quem
    aplica manualmente. `literal_binds=True` escreve os valores direto no SQL
    (sem parâmetros). Não conecta no banco.
    """
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online (o normal): conecta no banco e aplica as migrações.

    Abre uma conexão sem pool (NullPool), configura o contexto com o retrato
    das tabelas e executa as revisões pendentes dentro de uma transação: se
    uma falhar, nada daquela execução fica pela metade.
    """
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
