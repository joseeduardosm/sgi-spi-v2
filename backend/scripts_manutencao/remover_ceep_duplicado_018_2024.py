# Criado por José Eduardo Santana Martins
# Este arquivo serve para remover, uma única vez, o segundo "CEEP" (TR 8.3.5, 8.3.6 e 8.3.7) do checklist ativo do contrato 018/2024 e das competências.
"""Remove o item duplicado do checklist ativo e os documentos dele nas competências (só os que não têm arquivo anexado).

Por padrão é um ENSAIO (mostra e desfaz). Para valer: `--aplicar`.
Uso: cd backend && .venv/bin/python scripts_manutencao/remover_ceep_duplicado_018_2024.py [--aplicar]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO = "46eed7d0-a346-46da-baad-4ea5febc407b"
ITEM = "f5f4a6c4-c7dd-42af-a899-264989919189"
TRECHO = "TR 8.3.5, 8.3.6 e 8.3.7%"
APLICAR = "--aplicar" in sys.argv

with FabricaSessao() as s:
    item = s.execute(text("select i.nome, i.observacao, c.ativo from contratos_checklists_itens i join contratos_checklists c on c.id = i.checklist_id "
                          "where i.id = :i and c.contrato_id = :c"), {"i": ITEM, "c": CONTRATO}).one_or_none()
    if item is None or not item.observacao.startswith("TR 8.3.5, 8.3.6 e 8.3.7") or not item.nome.startswith("CEEP"):
        sys.exit("Item não encontrado ou diferente do esperado: nada foi feito.")
    print("Item do checklist:", item.nome, "|", item.observacao[:60], "| ativo:", item.ativo)
    docs = s.execute(text("select d.id, c.competencia, d.anexo_id is not null as anexado from contratos_competencias_documentos d join contratos_competencias c on c.id = d.competencia_id "
                          "where c.contrato_id = :c and d.nome like 'CEEP%' and d.observacao like :t"), {"c": CONTRATO, "t": TRECHO}).all()
    for d in docs:
        print("  competência", d.competencia, "| documento", d.id, "| anexado:", d.anexado)
    anexados = [d for d in docs if d.anexado]
    if anexados:
        sys.exit("Há documento com arquivo anexado: nada foi feito.")
    for d in docs:
        s.execute(text("delete from contratos_competencias_documentos where id = :i"), {"i": d.id})
    s.execute(text("delete from contratos_checklists_itens where id = :i"), {"i": ITEM})
    auditar(s, "manutencao", "contrato.checklist.remover_item", "Contrato 018/2024", f"CEEP duplicado (TR 8.3.5, 8.3.6 e 8.3.7): item do checklist ativo e {len(docs)} documento(s) de competência", alvo_tipo="contrato")
    if APLICAR:
        s.commit()
        print("Aplicado.")
    else:
        s.rollback()
        print("ENSAIO: nada foi alterado. Rode de novo com --aplicar para valer.")
