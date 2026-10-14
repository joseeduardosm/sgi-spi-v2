# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar o módulo Patrimônio: tabelas, histórico imutável, recurso ACL, árvore de localizações e grupo inicial.
"""patrimonio: módulo de bens móveis

Revision ID: a1c4e7b9d2f6
Revises: f8b3c5d7e9a1
Create Date: 2026-10-10 03:31:55
"""
import uuid
from datetime import UTC, datetime

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c4e7b9d2f6'
down_revision: Union[str, Sequence[str], None] = 'f8b3c5d7e9a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('patrimonio_grupos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('codigo', sa.String(length=40), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('vida_util_meses', sa.Integer(), nullable=True),
    sa.Column('residual_percentual', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('deprecia', sa.Boolean(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_table('patrimonio_parametros',
    sa.Column('chave', sa.String(length=60), nullable=False),
    sa.Column('valor', sa.String(length=200), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('chave')
    )
    op.create_table('patrimonio_classificacoes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('solicitante_id', sa.Integer(), nullable=True),
    sa.Column('criada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('enviada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decidido_por_id', sa.Integer(), nullable=True),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_recusa', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['decidido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['solicitante_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    op.create_index(op.f('ix_patrimonio_classificacoes_status'), 'patrimonio_classificacoes', ['status'], unique=False)
    op.create_table('patrimonio_baixas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('solicitante_id', sa.Integer(), nullable=True),
    sa.Column('criada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('enviada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decidido_por_id', sa.Integer(), nullable=True),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_recusa', sa.Text(), nullable=True),
    sa.Column('termo_anexo_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['decidido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['solicitante_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['termo_anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    op.create_index(op.f('ix_patrimonio_baixas_status'), 'patrimonio_baixas', ['status'], unique=False)
    op.create_table('patrimonio_localizacoes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pai_id', sa.Uuid(), nullable=True),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('codigo', sa.String(length=10), nullable=True),
    sa.Column('andar', sa.Integer(), nullable=True),
    sa.Column('lado', sa.String(length=1), nullable=True),
    sa.Column('setor_id', sa.Integer(), nullable=True),
    sa.Column('responsavel_id', sa.Integer(), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pai_id'], ['patrimonio_localizacoes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['responsavel_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['setor_id'], ['setores.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_index('ix_patrimonio_localizacoes_pai', 'patrimonio_localizacoes', ['pai_id'], unique=False)
    op.create_table('patrimonio_bens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('chapa', sa.String(length=60), nullable=False),
    sa.Column('chapa_chave', sa.String(length=60), nullable=False),
    sa.Column('descricao', sa.String(length=300), nullable=False),
    sa.Column('localizacao_id', sa.Uuid(), nullable=False),
    sa.Column('conservacao', sa.Integer(), nullable=False),
    sa.Column('situacao', sa.String(length=15), nullable=False),
    sa.Column('origem', sa.String(length=10), nullable=False),
    sa.Column('grupo_id', sa.Uuid(), nullable=True),
    sa.Column('uge', sa.String(length=40), nullable=True),
    sa.Column('ua', sa.String(length=40), nullable=True),
    sa.Column('divisao', sa.String(length=80), nullable=True),
    sa.Column('responsavel_id', sa.Integer(), nullable=True),
    sa.Column('valor_aquisicao', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('valor_atual', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('data_aquisicao', sa.Date(), nullable=True),
    sa.Column('garantia_meses', sa.Integer(), nullable=True),
    sa.Column('marca', sa.String(length=80), nullable=True),
    sa.Column('modelo', sa.String(length=80), nullable=True),
    sa.Column('numero_serie', sa.String(length=80), nullable=True),
    sa.Column('nota_fiscal', sa.String(length=60), nullable=True),
    sa.Column('fornecedor', sa.String(length=200), nullable=True),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.Column('classificacao_pendente', sa.Boolean(), nullable=False),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('baixado_em', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['grupo_id'], ['patrimonio_grupos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['localizacao_id'], ['patrimonio_localizacoes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['responsavel_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('chapa_chave'),
    sa.UniqueConstraint('id_cliente')
    )
    op.create_index(op.f('ix_patrimonio_bens_localizacao_id'), 'patrimonio_bens', ['localizacao_id'], unique=False)
    op.create_index('ix_patrimonio_bens_situacao', 'patrimonio_bens', ['situacao'], unique=False)
    op.create_table('patrimonio_movimentacoes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('id_cliente', sa.String(length=64), nullable=True),
    sa.Column('destino_id', sa.Uuid(), nullable=False),
    sa.Column('motivo', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('solicitante_id', sa.Integer(), nullable=True),
    sa.Column('solicitada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decidido_por_id', sa.Integer(), nullable=True),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_recusa', sa.Text(), nullable=True),
    sa.Column('concluida_em', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['decidido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['destino_id'], ['patrimonio_localizacoes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['solicitante_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_cliente')
    )
    op.create_index(op.f('ix_patrimonio_movimentacoes_status'), 'patrimonio_movimentacoes', ['status'], unique=False)
    op.create_table('patrimonio_eventos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('bem_id', sa.Uuid(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('campo', sa.String(length=60), nullable=True),
    sa.Column('valor_anterior', sa.Text(), nullable=True),
    sa.Column('valor_novo', sa.Text(), nullable=True),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=200), nullable=False),
    sa.Column('origem', sa.String(length=80), nullable=True),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('dados', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('ocorrido_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['bem_id'], ['patrimonio_bens.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_patrimonio_eventos_bem', 'patrimonio_eventos', ['bem_id', 'ocorrido_em'], unique=False)
    op.create_index('ix_patrimonio_eventos_campo', 'patrimonio_eventos', ['bem_id', 'campo'], unique=False)
    op.create_table('patrimonio_fotos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('bem_id', sa.Uuid(), nullable=False),
    sa.Column('anexo_id', sa.Uuid(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['bem_id'], ['patrimonio_bens.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_patrimonio_fotos_bem_id'), 'patrimonio_fotos', ['bem_id'], unique=False)
    op.create_table('patrimonio_itens_baixa',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('baixa_id', sa.Uuid(), nullable=False),
    sa.Column('bem_id', sa.Uuid(), nullable=False),
    sa.Column('motivo', sa.String(length=15), nullable=True),
    sa.Column('processo', sa.String(length=80), nullable=True),
    sa.Column('situacao_anterior', sa.String(length=15), nullable=True),
    sa.Column('resultado', sa.String(length=10), nullable=True),
    sa.ForeignKeyConstraint(['baixa_id'], ['patrimonio_baixas.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['bem_id'], ['patrimonio_bens.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('baixa_id', 'bem_id', name='uq_patrimonio_itens_baixa_bem')
    )
    op.create_index(op.f('ix_patrimonio_itens_baixa_baixa_id'), 'patrimonio_itens_baixa', ['baixa_id'], unique=False)
    op.create_index(op.f('ix_patrimonio_itens_baixa_bem_id'), 'patrimonio_itens_baixa', ['bem_id'], unique=False)
    op.create_table('patrimonio_itens_classificacao',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('classificacao_id', sa.Uuid(), nullable=False),
    sa.Column('bem_id', sa.Uuid(), nullable=False),
    sa.Column('justificativa', sa.Text(), nullable=True),
    sa.Column('anexo_id', sa.Uuid(), nullable=True),
    sa.Column('situacao_anterior', sa.String(length=15), nullable=True),
    sa.Column('resultado', sa.String(length=10), nullable=True),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['bem_id'], ['patrimonio_bens.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['classificacao_id'], ['patrimonio_classificacoes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('classificacao_id', 'bem_id', name='uq_patrimonio_itens_classificacao_bem')
    )
    op.create_index(op.f('ix_patrimonio_itens_classificacao_bem_id'), 'patrimonio_itens_classificacao', ['bem_id'], unique=False)
    op.create_index(op.f('ix_patrimonio_itens_classificacao_classificacao_id'), 'patrimonio_itens_classificacao', ['classificacao_id'], unique=False)
    op.create_table('patrimonio_itens_movimentacao',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('movimentacao_id', sa.Uuid(), nullable=False),
    sa.Column('bem_id', sa.Uuid(), nullable=False),
    sa.Column('origem_id', sa.Uuid(), nullable=False),
    sa.Column('recebido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('recebido_por_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['bem_id'], ['patrimonio_bens.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['movimentacao_id'], ['patrimonio_movimentacoes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['origem_id'], ['patrimonio_localizacoes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recebido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('movimentacao_id', 'bem_id', name='uq_patrimonio_itens_movimentacao_bem')
    )
    op.create_index(op.f('ix_patrimonio_itens_movimentacao_bem_id'), 'patrimonio_itens_movimentacao', ['bem_id'], unique=False)
    op.create_index(op.f('ix_patrimonio_itens_movimentacao_movimentacao_id'), 'patrimonio_itens_movimentacao', ['movimentacao_id'], unique=False)


    _proteger_historico()
    _semear_acl()
    _semear_localizacoes()
    _semear_grupo()


def _proteger_historico() -> None:
    """O histórico do bem é só de inserção: no PostgreSQL, um gatilho barra qualquer UPDATE ou DELETE (o SQLite dos testes fica de fora)."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE OR REPLACE FUNCTION patrimonio_eventos_imutavel() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'O histórico do patrimônio não pode ser alterado nem apagado.';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER tg_patrimonio_eventos_imutavel BEFORE UPDATE OR DELETE ON patrimonio_eventos "
               "FOR EACH ROW EXECUTE FUNCTION patrimonio_eventos_imutavel()")


def _semear_acl() -> None:
    """Recurso `patrimonio` na ACL (sem regras: só o SuperRoot acessa até a administração conceder os níveis)."""
    op.execute("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
               "SELECT 'Patrimônio', 'patrimonio', 'Bens móveis do prédio SPI: cadastro, localização, movimentação, inservíveis, baixa e painéis.', "
               "'/patrimonio', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
               "WHERE NOT EXISTS (SELECT 1 FROM acl_recursos WHERE slug = 'patrimonio')")


def _semear_localizacoes() -> None:
    """Gera a árvore inteira: prédio SPI, andares de -1 (subsolo) a 13, lados A e B e 15 salas por lado (ex.: 05A03, 00B15, -1A01)."""
    conexao = op.get_bind()
    tabela = sa.table(
        "patrimonio_localizacoes", sa.column("id", sa.Uuid()), sa.column("pai_id", sa.Uuid()), sa.column("tipo", sa.String()), sa.column("nome", sa.String()),
        sa.column("codigo", sa.String()), sa.column("andar", sa.Integer()), sa.column("lado", sa.String()), sa.column("ativo", sa.Boolean()),
        sa.column("criado_em", sa.DateTime(timezone=True)), sa.column("atualizado_em", sa.DateTime(timezone=True)),
    )
    if conexao.execute(sa.select(sa.func.count()).select_from(tabela)).scalar():
        return
    agora = datetime.now(UTC)
    linhas = []

    def no(pai, tipo, nome, codigo=None, andar=None, lado=None):
        identificador = uuid.uuid4()
        linhas.append({"id": identificador, "pai_id": pai, "tipo": tipo, "nome": nome, "codigo": codigo, "andar": andar, "lado": lado,
                       "ativo": True, "criado_em": agora, "atualizado_em": agora})
        return identificador

    predio = no(None, "predio", "Prédio SPI")
    for andar in range(-1, 14):
        nome_andar = "Subsolo" if andar == -1 else "Térreo" if andar == 0 else f"{andar}º andar"
        id_andar = no(predio, "andar", nome_andar, andar=andar)
        for lado in ("A", "B"):
            id_lado = no(id_andar, "lado", f"Lado {lado}", andar=andar, lado=lado)
            for numero in range(1, 16):
                codigo = f"{andar:02d}{lado}{numero:02d}"
                no(id_lado, "sala", codigo, codigo=codigo, andar=andar, lado=lado)
    op.bulk_insert(tabela, linhas)


def _semear_grupo() -> None:
    """Mobiliário com a referência provisória de dez anos de vida útil e 10% de residual (a tabela oficial ainda será obtida)."""
    op.execute("INSERT INTO patrimonio_grupos (id, codigo, nome, vida_util_meses, residual_percentual, deprecia, ativo, criado_em) "
               f"SELECT '{uuid.uuid4()}', 'MOBILIARIO', 'Mobiliário em geral', 120, 10, true, true, CURRENT_TIMESTAMP "
               "WHERE NOT EXISTS (SELECT 1 FROM patrimonio_grupos WHERE codigo = 'MOBILIARIO')")


def downgrade() -> None:
    """Remove o módulo (e o recurso ACL)."""
    op.execute("DELETE FROM acl_recursos WHERE slug = 'patrimonio'")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS tg_patrimonio_eventos_imutavel ON patrimonio_eventos")
        op.execute("DROP FUNCTION IF EXISTS patrimonio_eventos_imutavel()")
    # As localizações se referenciam: as folhas saem antes dos pais
    op.execute("UPDATE patrimonio_localizacoes SET pai_id = NULL")
    op.drop_index(op.f('ix_patrimonio_itens_movimentacao_movimentacao_id'), table_name='patrimonio_itens_movimentacao')
    op.drop_index(op.f('ix_patrimonio_itens_movimentacao_bem_id'), table_name='patrimonio_itens_movimentacao')
    op.drop_table('patrimonio_itens_movimentacao')
    op.drop_index(op.f('ix_patrimonio_itens_classificacao_classificacao_id'), table_name='patrimonio_itens_classificacao')
    op.drop_index(op.f('ix_patrimonio_itens_classificacao_bem_id'), table_name='patrimonio_itens_classificacao')
    op.drop_table('patrimonio_itens_classificacao')
    op.drop_index(op.f('ix_patrimonio_itens_baixa_bem_id'), table_name='patrimonio_itens_baixa')
    op.drop_index(op.f('ix_patrimonio_itens_baixa_baixa_id'), table_name='patrimonio_itens_baixa')
    op.drop_table('patrimonio_itens_baixa')
    op.drop_index(op.f('ix_patrimonio_fotos_bem_id'), table_name='patrimonio_fotos')
    op.drop_table('patrimonio_fotos')
    op.drop_index('ix_patrimonio_eventos_campo', table_name='patrimonio_eventos')
    op.drop_index('ix_patrimonio_eventos_bem', table_name='patrimonio_eventos')
    op.drop_table('patrimonio_eventos')
    op.drop_index(op.f('ix_patrimonio_movimentacoes_status'), table_name='patrimonio_movimentacoes')
    op.drop_table('patrimonio_movimentacoes')
    op.drop_index('ix_patrimonio_bens_situacao', table_name='patrimonio_bens')
    op.drop_index(op.f('ix_patrimonio_bens_localizacao_id'), table_name='patrimonio_bens')
    op.drop_table('patrimonio_bens')
    op.drop_index('ix_patrimonio_localizacoes_pai', table_name='patrimonio_localizacoes')
    op.drop_table('patrimonio_localizacoes')
    op.drop_index(op.f('ix_patrimonio_baixas_status'), table_name='patrimonio_baixas')
    op.drop_table('patrimonio_baixas')
    op.drop_index(op.f('ix_patrimonio_classificacoes_status'), table_name='patrimonio_classificacoes')
    op.drop_table('patrimonio_classificacoes')
    op.drop_table('patrimonio_parametros')
    op.drop_table('patrimonio_grupos')
