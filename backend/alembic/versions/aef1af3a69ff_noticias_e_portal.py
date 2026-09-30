# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar as tabelas do Módulo Notícias e do portal (atalhos e configuração do slider).
"""noticias e portal: notícias, revisões, anexos, categorias, atalhos e configuração do portal

- cria a linha única de `portal_configuracao`, as categorias iniciais e o recurso `noticias` na ACL
  (sem regras, só o SuperRoot publica; o administrador define redatores e aprovadores na tela de ACL).

Revision ID: aef1af3a69ff
Revises: 9639d1d834db
Create Date: 2026-09-30 17:45:15.581905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aef1af3a69ff'
down_revision: Union[str, Sequence[str], None] = '9639d1d834db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('noticias_categorias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('cor', sa.String(length=7), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('ativa', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nome')
    )
    op.create_table('portal_configuracao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=120), nullable=False),
    sa.Column('subtitulo', sa.String(length=200), nullable=False),
    sa.Column('quantidade_slides', sa.Integer(), nullable=False),
    sa.Column('segundos_por_slide', sa.Integer(), nullable=False),
    sa.Column('passagem_automatica', sa.Boolean(), nullable=False),
    sa.Column('criterio_slider', sa.String(length=12), nullable=False),
    sa.Column('titulo_sobreposto', sa.Boolean(), nullable=False),
    sa.Column('quantidade_cartoes', sa.Integer(), nullable=False),
    sa.Column('exibir_atalhos', sa.Boolean(), nullable=False),
    sa.Column('exibir_todas', sa.Boolean(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_por_nome', sa.String(length=200), nullable=False),
    sa.CheckConstraint("criterio_slider IN ('automatico', 'curadoria')", name='ck_portal_criterio'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('noticias',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(length=240), nullable=False),
    sa.Column('titulo', sa.String(length=220), nullable=False),
    sa.Column('linha_fina', sa.String(length=300), nullable=False),
    sa.Column('corpo_html', sa.Text(), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=True),
    sa.Column('situacao', sa.String(length=12), nullable=False),
    sa.Column('publicar_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('destaque_ate', sa.DateTime(timezone=True), nullable=True),
    sa.Column('fixada', sa.Boolean(), nullable=False),
    sa.Column('ordem_slider', sa.Integer(), nullable=True),
    sa.Column('exige_ciencia', sa.Boolean(), nullable=False),
    sa.Column('publico_aviso', sa.JSON(), nullable=True),
    sa.Column('aviso_enviado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('capa_anexo_id', sa.Uuid(), nullable=True),
    sa.Column('capa_recorte', sa.JSON(), nullable=True),
    sa.Column('capa_modo', sa.String(length=10), nullable=False),
    sa.Column('capa_alt', sa.String(length=300), nullable=False),
    sa.Column('capa_versoes', sa.JSON(), nullable=True),
    sa.Column('autor_id', sa.Integer(), nullable=True),
    sa.Column('autor_nome', sa.String(length=200), nullable=False),
    sa.Column('enviada_revisao_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('aprovado_por_id', sa.Integer(), nullable=True),
    sa.Column('aprovado_por_nome', sa.String(length=200), nullable=True),
    sa.Column('aprovado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_devolucao', sa.Text(), nullable=True),
    sa.Column('visualizacoes', sa.Integer(), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("capa_modo IN ('recortar', 'inteira')", name='ck_noticias_capa_modo'),
    sa.CheckConstraint("situacao IN ('rascunho', 'em_revisao', 'aprovada', 'devolvida', 'arquivada')", name='ck_noticias_situacao'),
    sa.ForeignKeyConstraint(['aprovado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['capa_anexo_id'], ['anexos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['categoria_id'], ['noticias_categorias.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_noticias_autor_id'), 'noticias', ['autor_id'], unique=False)
    op.create_index(op.f('ix_noticias_categoria_id'), 'noticias', ['categoria_id'], unique=False)
    op.create_index('ix_noticias_situacao_publicar', 'noticias', ['situacao', 'publicar_em'], unique=False)
    op.create_table('portal_atalhos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=80), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('imagem_anexo_id', sa.Uuid(), nullable=True),
    sa.Column('imagem_exibicao_id', sa.Uuid(), nullable=True),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('nova_aba', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['imagem_anexo_id'], ['anexos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['imagem_exibicao_id'], ['anexos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('noticias_anexos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('noticia_id', sa.Uuid(), nullable=False),
    sa.Column('anexo_id', sa.Uuid(), nullable=False),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['anexo_id'], ['anexos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['noticia_id'], ['noticias.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_noticias_anexos_noticia_id'), 'noticias_anexos', ['noticia_id'], unique=False)
    op.create_table('noticias_revisoes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('noticia_id', sa.Uuid(), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.String(length=200), nullable=False),
    sa.Column('titulo', sa.String(length=220), nullable=False),
    sa.Column('linha_fina', sa.String(length=300), nullable=False),
    sa.Column('corpo_html', sa.Text(), nullable=False),
    sa.Column('autor_nome', sa.String(length=200), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['noticia_id'], ['noticias.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_noticias_revisoes_noticia_id'), 'noticias_revisoes', ['noticia_id'], unique=False)

    # Dados iniciais
    op.execute("INSERT INTO portal_configuracao (id, titulo, subtitulo, quantidade_slides, segundos_por_slide, passagem_automatica, "
               "criterio_slider, titulo_sobreposto, quantidade_cartoes, exibir_atalhos, exibir_todas, atualizado_em, atualizado_por_nome) "
               "VALUES (1, 'Notícias', 'Comunicados, informes e atualizações institucionais.', 4, 7, true, 'automatico', true, 3, true, true, "
               "CURRENT_TIMESTAMP, '')")
    categorias = [("Comunicados", "#c82331"), ("Saúde e bem-estar", "#2e8b57"), ("Integridade", "#b7791f"), ("Tecnologia", "#2f6fb5"),
                  ("Eventos", "#6b3f99"), ("Campanhas", "#d9731a")]
    for ordem, (nome, cor) in enumerate(categorias):
        op.execute(sa.text("INSERT INTO noticias_categorias (nome, cor, ordem, ativa) VALUES (:n, :c, :o, true)").bindparams(n=nome, c=cor, o=ordem))
    op.execute("INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
               "SELECT 'Notícias', 'noticias', 'Portal de notícias: MODIFICACAO escreve e envia para aprovação; CONTROLE_TOTAL aprova e publica.', "
               "'/noticias/gestao', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
               "WHERE NOT EXISTS (SELECT 1 FROM acl_recursos WHERE slug = 'noticias')")


def downgrade() -> None:
    op.execute("DELETE FROM acl_recursos WHERE slug = 'noticias'")
    op.drop_index(op.f('ix_noticias_revisoes_noticia_id'), table_name='noticias_revisoes')
    op.drop_table('noticias_revisoes')
    op.drop_index(op.f('ix_noticias_anexos_noticia_id'), table_name='noticias_anexos')
    op.drop_table('noticias_anexos')
    op.drop_table('portal_atalhos')
    op.drop_index('ix_noticias_situacao_publicar', table_name='noticias')
    op.drop_index(op.f('ix_noticias_categoria_id'), table_name='noticias')
    op.drop_index(op.f('ix_noticias_autor_id'), table_name='noticias')
    op.drop_table('noticias')
    op.drop_table('portal_configuracao')
    op.drop_table('noticias_categorias')
