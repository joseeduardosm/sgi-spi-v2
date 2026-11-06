# Criado por José Eduardo Santana Martins
# Este arquivo serve para ligar as auditorias antigas de configuração de porta à porta (alvo), para os indicadores da Rede.

"""rede: alvo das auditorias antigas de porta

As configurações de porta (`rede.porta.configurar`) eram auditadas só com o texto "EQUIPAMENTO · número". Os indicadores da Rede
("Portas alteradas nos últimos 7 dias" e "quem alterou") procuram pela porta (`alvo_tipo = 'rede_porta'`, `alvo_id` = id da porta).
Esta migração só preenche o alvo das linhas antigas cujo texto ainda corresponde a uma porta existente; não cria nem apaga nada.

Revision ID: b7d9f1a3c5e8
Revises: a6c8e0b2d4f7
Create Date: 2026-11-05
"""
from collections.abc import Sequence

from alembic import op

# Identificação da migração: esta revisão e a anterior
revision: str = "b7d9f1a3c5e8"
down_revision: str | Sequence[str] | None = "a6c8e0b2d4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # "SW-5A · 3" → id da porta 3 do equipamento SW-5A (nome do equipamento + número lógico, como era gravado)
    op.execute("""
        UPDATE auditoria a SET alvo_tipo = 'rede_porta', alvo_id = p.id::text
        FROM rede_portas p JOIN rede_equipamentos e ON e.id = p.equipamento_id
        WHERE a.acao = 'rede.porta.configurar' AND a.alvo_id IS NULL AND a.alvo = e.nome || ' · ' || p.numero_logico
    """)


def downgrade() -> None:
    # Devolve as linhas antigas ao formato anterior (sem alvo); as novas também perdem o alvo, sem prejuízo do texto
    op.execute("UPDATE auditoria SET alvo_tipo = NULL, alvo_id = NULL WHERE acao = 'rede.porta.configurar' AND alvo_tipo = 'rede_porta'")
