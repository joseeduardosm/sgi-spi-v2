# Criado por José Eduardo Santana Martins
# Este arquivo serve para apagar do Patrimônio os bens importados do GLPI (id_cliente "glpi:%") e o histórico deles, uma única vez.
"""Limpeza única dos bens importados do GLPI.

O histórico do patrimônio é protegido por gatilho (não pode ser alterado nem apagado), então o gatilho é desligado só durante esta
transação e religado antes do commit. Se as contagens não forem as esperadas, tudo é desfeito (inclusive o gatilho).
Backup prévio: backend/backup-patrimonio-glpi-20261013.json.

Uso: cd backend && .venv/bin/python scripts_manutencao/limpar_patrimonio_glpi.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402

ESPERADO_EVENTOS, ESPERADO_BENS = 1458, 1202

with FabricaSessao() as s:
    gatilhos = [r[0] for r in s.execute(text("select tgname from pg_trigger where tgrelid='patrimonio_eventos'::regclass and not tgisinternal"))]
    print("gatilhos de patrimonio_eventos:", gatilhos)
    for g in gatilhos:
        s.execute(text(f'alter table patrimonio_eventos disable trigger "{g}"'))
    filtro = "(select id from patrimonio_bens where id_cliente like 'glpi:%')"
    eventos = s.execute(text(f"delete from patrimonio_eventos where bem_id in {filtro}")).rowcount
    bens = s.execute(text("delete from patrimonio_bens where id_cliente like 'glpi:%'")).rowcount
    for g in gatilhos:
        s.execute(text(f'alter table patrimonio_eventos enable trigger "{g}"'))
    print("eventos:", eventos, "bens:", bens)
    if (eventos, bens) != (ESPERADO_EVENTOS, ESPERADO_BENS):
        s.rollback()
        print("Contagem diferente do esperado: nada foi alterado.")
        sys.exit(1)
    s.commit()

with FabricaSessao() as s:
    print("bens restantes:", s.execute(text("select count(*) from patrimonio_bens")).scalar())
    print("gatilhos (O = ligado):", s.execute(text("select tgname, tgenabled from pg_trigger where tgrelid='patrimonio_eventos'::regclass and not tgisinternal")).all())
