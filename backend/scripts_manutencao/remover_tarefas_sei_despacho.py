"""
===============================================================================
ARQUIVO: remover_tarefas_sei_despacho.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Script de manutenção que remove do Módulo Tarefas todas as tarefas "Subir no
SEI" (chave sei) e "Despachar" (chave despachar) geradas pelas competências
de contratos, inclusive as já concluídas ou em validação.

RESUMO TÉCNICO:
Busca as tarefas com origem_tipo de contratos (ORIGEM) e origem_chave em
CHAVES, mostra a contagem por chave e status e as já trabalhadas. Sem
argumento só LISTA (simulação). Com --aplicar, para cada tarefa encerra os
avisos de validação pendentes (notificacoes.encerrar), audita uma linha e
apaga a tarefa (histórico, comentários e anexos vão em cascata), com um único
commit no fim.
Uso: cd backend && .venv/bin/python scripts_manutencao/remover_tarefas_sei_despacho.py [--aplicar]

FINALIDADE DE NEGÓCIO:
As competências (meses de execução dos contratos) deixaram de gerar essas
duas tarefas (servico_tarefas_contratos.catalogo); o script limpa as que já
existiam, a pedido do solicitante. SEI é o sistema de processo eletrônico.
Não toca nas demais tarefas das competências.

CONTEXTO NO SISTEMA:
Modelo Tarefa (Módulo Tarefas), servico_tarefas_contratos (ORIGEM), serviço
de notificações e serviço de auditoria.

===============================================================================
"""
import json
import sys
from collections import Counter
from pathlib import Path

# Coloca a pasta backend/ no caminho de import, para "app" ser encontrado ao rodar o script direto.
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
    # Destaca as tarefas que alguém já mexeu (status diferente de "a fazer"), para conferência antes de apagar.
    trabalhadas = [t for t in tarefas if t.status != "a_fazer"]
    for t in trabalhadas:
        print(f"  (já trabalhada) #{t.numero} {t.status}: {t.titulo}")
    # Modo simulação: sai sem alterar nada.
    if not aplicar:
        print("\nSimulação: nada foi apagado. Rode com --aplicar para remover.")
        sys.exit(0)
    resumo = [{"numero": t.numero, "titulo": t.titulo, "status": t.status, "chave": t.origem_chave} for t in tarefas]
    # Para cada tarefa: fecha os avisos de validação, audita e apaga (as filhas saem em cascata).
    for t in tarefas:
        notificacoes.encerrar(s, prefixo=f"tarefa-validacao:{t.id}:")
        auditar(s, "sistema", "tarefas.excluir", t.titulo, "Removida: Subir no SEI e Despachar deixaram de ser tarefas de contratos", alvo_tipo="tarefa", alvo_id=t.id)
        s.delete(t)
    s.commit()
    print(f"\n{len(tarefas)} tarefa(s) removida(s). Resumo:\n" + json.dumps(resumo[:3], ensure_ascii=False) + " …")
