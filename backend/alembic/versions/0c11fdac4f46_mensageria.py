"""
===============================================================================
ARQUIVO: 0c11fdac4f46_mensageria.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Criar as tabelas da mensageria (caixa de mensagens interna do SGI) e o
recurso de ACL que libera o envio de mensagens para setores inteiros.

RESUMO TÉCNICO:
- `mensagens`: conteúdo publicado (avulso ou automático), com prioridade,
  categoria, expiração, link, chave de deduplicação e contrato relacionado
  (apagado em CASCADE junto com o contrato).
- `mensagens_entregas`: a cópia para cada destinatário, com visualizada,
  ciente, encerrada e resultado do e-mail; um destinatário por mensagem.
- Recurso de ACL `mensageria-setores`, criado fechado: uma regra
  CONTROLE_TOTAL só para a conta administrativa principal (ou, se ela não
  existir, para os SuperRoot).

FINALIDADE DE NEGÓCIO:
Dá ao órgão um canal oficial de avisos dentro do sistema (comunicados,
prazos, pendências), com registro de quem leu e deu ciência. O envio para
setores inteiros fica restrito para evitar disparos em massa indevidos.

CONTEXTO NO SISTEMA:
Base dos modelos de mensageria (depois renomeada para notificações em
`d4e8a1c6b2f7`). Relaciona-se com `usuarios`, `contratos` e com as tabelas
da ACL (`acl_recursos`, `acl_regras`, `acl_regras_usuarios`).

Revision ID: 0c11fdac4f46
Revises: 46921c091299
Create Date: 2026-09-28 22:00:00

===============================================================================
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.core.configuracao import obter_configuracao

# Identificação da migração: esta revisão e a anterior
revision: str = "0c11fdac4f46"
down_revision: str | Sequence[str] | None = "46921c091299"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "mensageria-setores"


# O módulo `op` do Alembic traz as operações de esquema (create_table,
# add_column, create_index, drop_* etc.); cada uma vira um comando SQL
# executado no banco.
def upgrade() -> None:
    """Cria as tabelas `mensagens` e `mensagens_entregas`, seus índices e o
    recurso de ACL `mensageria-setores`.
    """
    op.create_table(
        "mensagens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assunto", sa.String(length=300), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("prioridade", sa.String(length=10), nullable=False),
        sa.Column("categoria", sa.String(length=20), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("autor_nome", sa.String(length=200), nullable=False),
        sa.Column("publicada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("origem", sa.String(length=12), nullable=False),
        sa.Column("chave", sa.String(length=200), nullable=True),
        sa.Column("contrato_id", sa.Uuid(), nullable=True),
        sa.Column("abrir_em_janela", sa.Boolean(), nullable=False),
        sa.Column("enviar_email", sa.Boolean(), nullable=False),
        sa.CheckConstraint("prioridade IN ('baixa', 'normal', 'alta', 'critica')", name="ck_mensagens_prioridade"),
        sa.CheckConstraint("categoria IN ('comunicado', 'prazo', 'pendencia', 'revisao', 'atribuicao', 'indisponibilidade', 'normativo')",
                           name="ck_mensagens_categoria"),
        sa.CheckConstraint("origem IN ('avulsa', 'automatica')", name="ck_mensagens_origem"),
        sa.ForeignKeyConstraint(["autor_id"], ["usuarios.id"], ondelete="SET NULL", name="mensagens_autor_id_fkey"),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"], ondelete="CASCADE", name="mensagens_contrato_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="mensagens_pkey"),
    )
    # Índices nas colunas usadas em filtros: mensagens de um autor, busca pela
    # chave de deduplicação (evita repetir aviso automático) e mensagens de um
    # contrato.
    op.create_index("ix_mensagens_autor_id", "mensagens", ["autor_id"])
    op.create_index("ix_mensagens_chave", "mensagens", ["chave"])
    op.create_index("ix_mensagens_contrato_id", "mensagens", ["contrato_id"])
    op.create_table(
        "mensagens_entregas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mensagem_id", sa.Uuid(), nullable=False),
        sa.Column("destinatario_id", sa.Integer(), nullable=False),
        sa.Column("assunto_copia", sa.String(length=300), nullable=False),
        sa.Column("corpo_copia", sa.Text(), nullable=False),
        sa.Column("entregue_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visualizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ciente_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encerrada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_ok", sa.Boolean(), nullable=True),
        sa.Column("email_erro", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["destinatario_id"], ["usuarios.id"], ondelete="CASCADE", name="mensagens_entregas_destinatario_id_fkey"),
        sa.ForeignKeyConstraint(["mensagem_id"], ["mensagens.id"], ondelete="CASCADE", name="mensagens_entregas_mensagem_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="mensagens_entregas_pkey"),
        sa.UniqueConstraint("mensagem_id", "destinatario_id", name="uq_mensagens_entregas_mensagem_destinatario"),
    )
    # Índice composto para a caixa de entrada: entregas de um usuário filtradas
    # por terem ou não ciência.
    op.create_index("ix_mensagens_entregas_destinatario_ciente", "mensagens_entregas", ["destinatario_id", "ciente_em"])
    op.create_index("ix_mensagens_entregas_mensagem_id", "mensagens_entregas", ["mensagem_id"])
    _criar_recurso_acl()


def _criar_recurso_acl() -> None:
    """Cria o recurso `mensageria-setores` fechado (só a conta administrativa).

    É idempotente: se o recurso já existe reaproveita o id, e se já há
    qualquer regra para ele não cria outra. A regra CONTROLE_TOTAL vai para o
    usuário cujo login é `login_admin` da configuração; se ele não existir, vai
    para todos os SuperRoot (coluna `superusuario`). Sem nenhum desses, o
    recurso fica sem regra (ninguém envia para setores).

    ACL = lista de controle de acesso: recurso (módulo/função) + regras que
    dizem qual nível (LEITURA, MODIFICACAO, CONTROLE_TOTAL) cada setor ou
    usuário tem.
    """
    # op.get_bind() devolve a conexão da migração; com ela rodamos SQL de dados
    # (sa.text com parâmetros :nome) dentro da mesma transação.
    conexao = op.get_bind()
    agora = datetime.now(UTC)
    recurso_id = conexao.scalar(sa.text("SELECT id FROM acl_recursos WHERE slug = :slug"), {"slug": SLUG})
    if recurso_id is None:
        recurso_id = conexao.scalar(
            sa.text(
                "INSERT INTO acl_recursos (nome, slug, descricao, url_base, ativo, criado_em, atualizado_em) "
                "VALUES (:nome, :slug, :descricao, '/mensagens', true, :agora, :agora) RETURNING id"
            ),
            {"nome": "Mensageria: envio para setores", "slug": SLUG, "agora": agora,
             "descricao": "Enviar mensagens para setores inteiros na caixa de mensagens (exige CONTROLE_TOTAL)."},
        )
    # Se alguém já configurou regras para o recurso, respeita a configuração
    # existente e não acrescenta outra.
    if conexao.scalar(sa.text("SELECT count(*) FROM acl_regras WHERE recurso_id = :id"), {"id": recurso_id}):
        return
    # Procura a conta administrativa principal; o `or` cai para os SuperRoot
    # quando a lista vem vazia.
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
        conexao.execute(sa.text("INSERT INTO acl_regras_usuarios (regra_id, usuario_id) VALUES (:regra, :usuario)"),
                        {"regra": regra_id, "usuario": usuario_id})


def downgrade() -> None:
    """Desfaz a migração: remove o recurso de ACL (as regras saem em cascata),
    os índices e as tabelas. As mensagens registradas se perdem.
    """
    op.execute(sa.text("DELETE FROM acl_recursos WHERE slug = :slug").bindparams(slug=SLUG))
    op.drop_index("ix_mensagens_entregas_mensagem_id", table_name="mensagens_entregas")
    op.drop_index("ix_mensagens_entregas_destinatario_ciente", table_name="mensagens_entregas")
    op.drop_table("mensagens_entregas")
    op.drop_index("ix_mensagens_contrato_id", table_name="mensagens")
    op.drop_index("ix_mensagens_chave", table_name="mensagens")
    op.drop_index("ix_mensagens_autor_id", table_name="mensagens")
    op.drop_table("mensagens")
