# Criado por José Eduardo Santana Martins
# Este arquivo serve para remover do Módulo Tarefas todas as tarefas "Subir no SEI" e "Despachar" geradas pelas competências de contratos, a pedido do solicitante.
"""Remove as tarefas `sei` e `despachar` de contratos (equipe Contratos), inclusive as já concluídas ou em validação.

As competências deixaram de gerar essas duas tarefas (`servico_tarefas_contratos.catalogo`); este script apaga as que já existiam, com o histórico, os comentários
e os anexos delas (em cascata), encerra os avisos de validação pendentes e audita uma linha por tarefa. Não toca nas demais tarefas das competências.

Sem argumento só LISTA (simulação). Com `--aplicar` apaga, numa única transação.

Uso: cd backend && .venv/bin/python scripts_manutencao/remover_tarefas_sei_despacho.py [--aplicar]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.tarefas import Tarefa  # noqa: E402
from app.services import notificacoes  # noqa: E402
from app.services.contratos.servico_tarefas_contratos import ORIGEM  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CHAVES = ("sei", "despachar")
aplicar = "--aplicar" in sys.argv

with FabricaSessao() as s:
    tarefas = list(s.scalars(select(Tarefa).where(Tarefa.origem_tipo == ORIGEM, Tarefa.origem_chave.in_(CHAVES)).order_by(Tarefa.numero)))
    por_chave_status = Counter((t.origem_chave, t.status) for t in tarefas)
    print(f"{len(tarefas)} tarefa(s) de SEI/despacho em contratos:")
    for (chave, status), n in sorted(por_chave_status.items()):
        print(f"  {chave:10} {status:14} {n}")
    trabalhadas = [t for t in tarefas if t.status != "a_fazer"]
    for t in trabalhadas:
        print(f"  (já trabalhada) #{t.numero} {t.status}: {t.titulo}")
    if not aplicar:
        print("\nSimulação: nada foi apagado. Rode com --aplicar para remover.")
        sys.exit(0)
    resumo = [{"numero": t.numero, "titulo": t.titulo, "status": t.status, "chave": t.origem_chave} for t in tarefas]
    for t in tarefas:
        notificacoes.encerrar(s, prefixo=f"tarefa-validacao:{t.id}:")
        auditar(s, "sistema", "tarefas.excluir", t.titulo, "Removida: Subir no SEI e Despachar deixaram de ser tarefas de contratos", alvo_tipo="tarefa", alvo_id=t.id)
        s.delete(t)
    s.commit()
    print(f"\n{len(tarefas)} tarefa(s) removida(s). Resumo:\n" + json.dumps(resumo[:3], ensure_ascii=False) + " …")
