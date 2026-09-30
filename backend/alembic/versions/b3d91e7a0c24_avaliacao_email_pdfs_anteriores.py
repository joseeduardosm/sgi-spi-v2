# Criado por José Eduardo Santana Martins
# Este arquivo serve para marcar como "não enviadas" as avaliações com PDF gerado antes do envio automático à contratada.
"""avaliação: PDFs gerados antes do envio automático ficam como e-mail não enviado

Sem isso, a tela mostraria "Enviando…" para sempre nessas avaliações (resultado do e-mail vazio).

Revision ID: b3d91e7a0c24
Revises: 57c0f7e1349f
Create Date: 2026-09-30 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3d91e7a0c24'
down_revision: Union[str, Sequence[str], None] = '57c0f7e1349f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENSAGEM = 'Relatório gerado antes do envio automático à contratada: use "Reenviar e-mail" se precisar.'


def upgrade() -> None:
    op.execute(
        "update contratos_competencias_avaliacoes set email_enviado_em = now(), email_ok = false, "
        f"email_erro = '{MENSAGEM}' where pdf_gerado_anexo_id is not null and email_enviado_em is null"
    )


def downgrade() -> None:
    op.execute(
        "update contratos_competencias_avaliacoes set email_enviado_em = null, email_ok = null, email_erro = null "
        f"where email_erro = '{MENSAGEM}'"
    )
