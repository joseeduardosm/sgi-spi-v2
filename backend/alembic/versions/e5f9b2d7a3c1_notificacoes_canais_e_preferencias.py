# Criado por José Eduardo Santana Martins
# Este arquivo serve para criar os canais (e-mail, navegador, desktop) e as preferências das Notificações, sem perder o histórico.
"""notificacoes: canais e preferencias

- `notificacoes`: ganha `evento` e `tarefa_id`; perde `enviar_email` (quem decide o e-mail agora é a preferência do destinatário).
- `notificacoes_entregas`: ganha os canais (fotografia da preferência na entrega) e o resultado do envio ao navegador. As entregas que
  já tiveram e-mail enviado ficam com `canal_email = true`, para o histórico continuar correto e nada antigo ser reenviado.
- Tabelas novas: preferências, configuração por usuário, inscrições do navegador, silenciados e obrigatórias (todas começam vazias:
  todo mundo começa com os canais desmarcados).

Revision ID: e5f9b2d7a3c1
Revises: d4e8a1c6b2f7
Create Date: 2026-10-12 04:00:00
"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.configuracao import obter_configuracao

# revision identifiers, used by Alembic.
revision: str = 'e5f9b2d7a3c1'
down_revision: Union[str, Sequence[str], None] = 'd4e8a1c6b2f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Colunas novas, tabelas novas e o preenchimento do histórico de e-mail."""
    op.add_column('notificacoes', sa.Column('evento', sa.String(length=60), nullable=True))
    op.add_column('notificacoes', sa.Column('tarefa_id', sa.Uuid(), nullable=True))
    op.create_index('ix_notificacoes_evento', 'notificacoes', ['evento'])
    op.create_index('ix_notificacoes_tarefa_id', 'notificacoes', ['tarefa_id'])
    op.create_foreign_key('notificacoes_tarefa_id_fkey', 'notificacoes', 'tarefas', ['tarefa_id'], ['id'], ondelete='CASCADE')
    op.drop_column('notificacoes', 'enviar_email')

    for coluna in ('canal_email', 'canal_navegador', 'canal_desktop', 'email_resumo'):
        op.add_column('notificacoes_entregas', sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('notificacoes_entregas', sa.Column('navegador_enviado_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notificacoes_entregas', sa.Column('navegador_ok', sa.Boolean(), nullable=True))
    op.add_column('notificacoes_entregas', sa.Column('navegador_erro', sa.Text(), nullable=True))
    # Histórico: quem já teve e-mail enviado mantém o canal de e-mail marcado
    op.execute('UPDATE notificacoes_entregas SET canal_email = true WHERE email_enviado_em IS NOT NULL')

    op.create_table(
        'notificacoes_preferencias',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evento', sa.String(length=60), nullable=False),
        sa.Column('canal', sa.String(length=10), nullable=False),
        sa.UniqueConstraint('usuario_id', 'evento', 'canal', name='uq_notificacoes_preferencias_usuario_evento_canal'),
        sa.CheckConstraint("canal IN ('email', 'navegador', 'desktop')", name='ck_notificacoes_preferencias_canal'),
    )
    op.create_index('ix_notificacoes_preferencias_usuario_id', 'notificacoes_preferencias', ['usuario_id'])
    op.create_table(
        'notificacoes_config_usuario',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('frequencia_email', sa.String(length=10), nullable=False, server_default='imediato'),
        sa.Column('silencio_inicio', sa.Time(), nullable=True),
        sa.Column('silencio_fim', sa.Time(), nullable=True),
        sa.Column('silencio_fins_de_semana', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("frequencia_email IN ('imediato', 'diario', 'semanal')", name='ck_notificacoes_config_usuario_frequencia'),
    )
    op.create_table(
        'notificacoes_inscricoes_navegador',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False, unique=True),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('rotulo', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('criada_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ultimo_envio_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('falhas_seguidas', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_notificacoes_inscricoes_navegador_usuario_id', 'notificacoes_inscricoes_navegador', ['usuario_id'])
    op.create_table(
        'notificacoes_silenciados',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('alvo_id', sa.Uuid(), nullable=False),
        sa.Column('rotulo', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('usuario_id', 'tipo', 'alvo_id', name='uq_notificacoes_silenciados_usuario_tipo_alvo'),
        sa.CheckConstraint("tipo IN ('contrato', 'tarefa')", name='ck_notificacoes_silenciados_tipo'),
    )
    op.create_index('ix_notificacoes_silenciados_usuario_id', 'notificacoes_silenciados', ['usuario_id'])
    op.create_table(
        'notificacoes_obrigatorias',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('evento', sa.String(length=60), nullable=False),
        sa.Column('canal', sa.String(length=10), nullable=False),
        sa.Column('setor_id', sa.Integer(), sa.ForeignKey('setores.id', ondelete='CASCADE'), nullable=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=True),
        sa.Column('criada_por_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('criada_em', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("canal IN ('email', 'navegador', 'desktop')", name='ck_notificacoes_obrigatorias_canal'),
        sa.CheckConstraint('(setor_id IS NULL) <> (usuario_id IS NULL)', name='ck_notificacoes_obrigatorias_alvo'),
    )
    op.create_index('ix_notificacoes_obrigatorias_setor_id', 'notificacoes_obrigatorias', ['setor_id'])
    op.create_index('ix_notificacoes_obrigatorias_usuario_id', 'notificacoes_obrigatorias', ['usuario_id'])
    _criar_recurso_acl()


def _criar_recurso_acl() -> None:
    """Recurso `notificacoes-obrigatorias` **fechado**: uma regra CONTROLE_TOTAL só para a conta administrativa principal.

    Na ACL, recurso sem nenhuma regra fica aberto a todos; por isso a regra é criada junto (a administração libera outras pessoas depois).
    """
    conexao = op.get_bind()
    agora = datetime.now(UTC)
    recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = 'notificacoes-obrigatorias'"))
    if recurso_id is None:
        recurso_id = conexao.scalar(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES ('Notificações: eventos obrigatórios', 'notificacoes-obrigatorias', "
                "'Definir quais eventos e canais de notificação são obrigatórios para um setor ou usuário (exige CONTROLE_TOTAL).', "
                "'/admin/notificacoes-sistema', true, :agora, :agora) RETURNING id"
            ),
            {"agora": agora},
        )
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    usuarios = conexao.scalars(
        sa.text("SELECT id FROM usuarios WHERE lower(login) = lower(:login)"), {"login": obter_configuracao().login_admin}
    ).all() or conexao.scalars(sa.text("SELECT id FROM usuarios WHERE superusuario")).all()
    if not usuarios:
        return
    regra_id = conexao.scalar(
        sa.text("INSERT INTO acl_regras (recurso_id, nivel, criado_em, atualizado_em) VALUES (:id, 'CONTROLE_TOTAL', :agora, :agora) RETURNING id"),
        {"id": recurso_id, "agora": agora},
    )
    for usuario_id in usuarios:
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:regra, :usuario)"), {"regra": regra_id, "usuario": usuario_id})


def downgrade() -> None:
    """Remove as tabelas e as colunas novas; `enviar_email` volta valendo falso (o dado antigo não é recuperável)."""
    op.execute("DELETE FROM acl_recursos WHERE slug = 'notificacoes-obrigatorias'")
    for tabela in ('notificacoes_obrigatorias', 'notificacoes_silenciados', 'notificacoes_inscricoes_navegador', 'notificacoes_config_usuario', 'notificacoes_preferencias'):
        op.drop_table(tabela)
    for coluna in ('navegador_erro', 'navegador_ok', 'navegador_enviado_em', 'email_resumo', 'canal_desktop', 'canal_navegador', 'canal_email'):
        op.drop_column('notificacoes_entregas', coluna)
    op.add_column('notificacoes', sa.Column('enviar_email', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_constraint('notificacoes_tarefa_id_fkey', 'notificacoes', type_='foreignkey')
    op.drop_index('ix_notificacoes_tarefa_id', table_name='notificacoes')
    op.drop_index('ix_notificacoes_evento', table_name='notificacoes')
    op.drop_column('notificacoes', 'tarefa_id')
    op.drop_column('notificacoes', 'evento')
