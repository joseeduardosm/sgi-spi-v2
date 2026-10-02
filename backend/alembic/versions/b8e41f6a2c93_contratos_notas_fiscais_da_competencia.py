# Criado por José Eduardo Santana Martins
# Este arquivo serve para permitir várias notas fiscais (PDF + XML) por medição, movendo a NF principal e a adicional para uma tabela própria.
"""contratos: várias notas fiscais por competência

Cria `contratos_competencias_notas_fiscais`, copia para ela a NF principal (ordem 1) e a adicional (ordem 2) de cada
competência e remove as colunas `nf_*` antigas. O downgrade devolve as duas primeiras notas às colunas (as demais se perdem).

Revision ID: b8e41f6a2c93
Revises: a7d3c91e5b20
Create Date: 2026-10-01 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b8e41f6a2c93'
down_revision: Union[str, Sequence[str], None] = 'a7d3c91e5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRIBUTOS = ("ir", "inss", "iss", "pis", "cofins", "csll")
# (prefixo das colunas antigas, ordem na tabela nova)
NOTAS = (("nf_", 1), ("nf_adicional_", 2))


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'contratos_competencias_notas_fiscais',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('competencia_id', sa.Uuid(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('anexo_id', sa.Uuid(), nullable=True),
        sa.Column('xml_anexo_id', sa.Uuid(), nullable=True),
        sa.Column('numero', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('chave', sa.String(length=60), nullable=True),
        sa.Column('valor_bruto', sa.Numeric(precision=18, scale=2), nullable=True),
        *[sa.Column(f'retencao_{t}', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0') for t in TRIBUTOS],
        sa.Column('dados_xml', _json(), nullable=True),
        sa.ForeignKeyConstraint(['competencia_id'], ['contratos_competencias.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['xml_anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('competencia_id', 'ordem', name='uq_contratos_notas_fiscais_competencia_ordem'),
    )
    op.create_index('ix_contratos_competencias_notas_fiscais_competencia_id', 'contratos_competencias_notas_fiscais', ['competencia_id'])
    op.create_index('ix_contratos_competencias_notas_fiscais_chave', 'contratos_competencias_notas_fiscais', ['chave'])

    # Copia as notas existentes (a adicional só existe se tiver PDF ou valor)
    for prefixo, ordem in NOTAS:
        retencoes = ", ".join(f"{prefixo}retencao_{t}" for t in TRIBUTOS)
        op.execute(f"""
            INSERT INTO contratos_competencias_notas_fiscais
                (id, competencia_id, ordem, anexo_id, xml_anexo_id, numero, chave, valor_bruto, {', '.join(f'retencao_{t}' for t in TRIBUTOS)}, dados_xml)
            SELECT gen_random_uuid(), id, {ordem}, {prefixo}anexo_id, {prefixo}xml_anexo_id, COALESCE({prefixo}numero, ''), {prefixo}chave,
                   {prefixo}valor_bruto, {retencoes}, {prefixo}dados_xml
            FROM contratos_competencias
            WHERE {prefixo}anexo_id IS NOT NULL OR {prefixo}valor_bruto IS NOT NULL
        """)

    for prefixo, _ in NOTAS:
        op.drop_index(f'ix_contratos_competencias_{prefixo}chave', table_name='contratos_competencias')
        for coluna in ("anexo_id", "numero", "valor_bruto", *[f"retencao_{t}" for t in TRIBUTOS], "xml_anexo_id", "dados_xml", "chave"):
            op.drop_column('contratos_competencias', f'{prefixo}{coluna}')


def downgrade() -> None:
    """Downgrade schema."""
    for prefixo, _ in NOTAS:
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}anexo_id', sa.Uuid(), sa.ForeignKey('anexos.id', ondelete='RESTRICT'), nullable=True))
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}numero', sa.String(length=100), nullable=False, server_default=''))
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}valor_bruto', sa.Numeric(precision=18, scale=2), nullable=True))
        for t in TRIBUTOS:
            op.add_column('contratos_competencias', sa.Column(f'{prefixo}retencao_{t}', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'))
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}xml_anexo_id', sa.Uuid(), sa.ForeignKey('anexos.id', ondelete='RESTRICT'), nullable=True))
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}dados_xml', _json(), nullable=True))
        op.add_column('contratos_competencias', sa.Column(f'{prefixo}chave', sa.String(length=60), nullable=True))
        op.create_index(f'ix_contratos_competencias_{prefixo}chave', 'contratos_competencias', [f'{prefixo}chave'])
    for prefixo, ordem in NOTAS:
        sets = ", ".join([f"{prefixo}anexo_id = n.anexo_id", f"{prefixo}numero = n.numero", f"{prefixo}valor_bruto = n.valor_bruto",
                          *[f"{prefixo}retencao_{t} = n.retencao_{t}" for t in TRIBUTOS],
                          f"{prefixo}xml_anexo_id = n.xml_anexo_id", f"{prefixo}dados_xml = n.dados_xml", f"{prefixo}chave = n.chave"])
        op.execute(f"UPDATE contratos_competencias c SET {sets} FROM contratos_competencias_notas_fiscais n "
                   f"WHERE n.competencia_id = c.id AND n.ordem = {ordem}")
    op.drop_index('ix_contratos_competencias_notas_fiscais_chave', table_name='contratos_competencias_notas_fiscais')
    op.drop_index('ix_contratos_competencias_notas_fiscais_competencia_id', table_name='contratos_competencias_notas_fiscais')
    op.drop_table('contratos_competencias_notas_fiscais')
