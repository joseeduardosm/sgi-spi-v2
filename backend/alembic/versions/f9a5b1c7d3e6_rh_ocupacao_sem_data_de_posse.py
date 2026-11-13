"""
===============================================================================
ARQUIVO: f9a5b1c7d3e6_rh_ocupacao_sem_data_de_posse.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Migração Alembic que permite ocupações de cargo sem data de posse e limpa a
data inventada dos vínculos automáticos do cadastro anterior.

RESUMO TÉCNICO:
Torna rh_ocupacoes.inicio anulável e zera (NULL) o início das ocupações cujo
ato é "Vínculo do cadastro anterior". O downgrade preenche as datas vazias com
a data de registro da ocupação e volta a exigir a coluna.

FINALIDADE DE NEGÓCIO:
No RH, a data de posse é informação oficial. Os vínculos criados
automaticamente na migração do cadastro antigo tinham como posse a data da
criação do cadastro, o que era falso; agora ficam sem data até alguém informar
a real.

CONTEXTO NO SISTEMA:
Tabela rh_ocupacoes; telas de cargos e pessoal do RH
(app/api/routes/rh_cargos.py e rh_pessoal.py). Aplicada com 'alembic upgrade
head' (o instalador e a atualização do sistema rodam esse comando).

Revision ID: f9a5b1c7d3e6
Revises: a1c5e9b3d7f4
Create Date: 2026-10-23

===============================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "f9a5b1c7d3e6"
down_revision: str | Sequence[str] | None = "a1c5e9b3d7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Texto do campo "ato" que identifica as ocupações criadas automaticamente na migração
# do cadastro anterior (essas não têm data de posse verdadeira)
ATO_AUTOMATICO = "Vínculo do cadastro anterior"


def upgrade() -> None:
    """A data de posse passa a ser opcional; os vínculos automáticos do cadastro anterior (data inventada da criação do cadastro) ficam sem ela."""
    op.alter_column("rh_ocupacoes", "inicio", existing_type=sa.Date(), nullable=True)
    op.get_bind().execute(sa.text("UPDATE rh_ocupacoes SET inicio = NULL WHERE ato = :ato"), {"ato": ATO_AUTOMATICO})


def downgrade() -> None:
    """Sem data não existe na versão anterior: a data de registro da ocupação ocupa o lugar."""
    op.get_bind().execute(sa.text("UPDATE rh_ocupacoes SET inicio = CAST(registrado_em AS date) WHERE inicio IS NULL"))
    op.alter_column("rh_ocupacoes", "inicio", existing_type=sa.Date(), nullable=False)
