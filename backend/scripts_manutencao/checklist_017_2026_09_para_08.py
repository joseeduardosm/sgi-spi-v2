# Criado por José Eduardo Santana Martins
# Este arquivo serve para trazer os documentos do checklist da competência 09/2026 para a 08/2026 do contrato 017/2026 e concluir o checklist da 08/2026, a pedido do solicitante.
"""Checklist 017/2026 · 08/2026 a partir da 09/2026.

Cada documento da 08/2026 sem anexo recebe o arquivo do documento de mesmo nome da 09/2026 (o mesmo anexo, sem cópia física; quem e quando enviou
continuam os da 09/2026 e a origem fica marcada como "reaproveitado de 09/2026"). Depois conclui a etapa do checklist (como "Concluir checklist": os
documentos são todos opcionais neste contrato). A retenção de tributos segue aberta. Audita e sincroniza as tarefas.

Sem argumento só mostra; com `--aplicar` grava.

Uso: cd backend && .venv/bin/python scripts_manutencao/checklist_017_2026_09_para_08.py [--aplicar]
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratos import Competencia, Contrato  # noqa: E402
from app.services.contratos import servico_competencias as sc  # noqa: E402
from app.services.contratos.servico_tarefas_contratos import usuario_sistema  # noqa: E402

with FabricaSessao() as s:
    def competencia(mes: int) -> Competencia:
        return s.scalar(select(Competencia).join(Contrato).where(Contrato.numero == "017/2026", Competencia.competencia == date(2026, mes, 1), Competencia.tipo == "regular"))

    agosto, setembro = competencia(8), competencia(9)
    if agosto.checklist_concluido_em is not None:
        sys.exit("O checklist da 08/2026 já está concluído: nada foi alterado.")
    origem = {d.nome: d for d in setembro.documentos if d.anexo_id}
    trazidos = []
    for documento in agosto.documentos:
        par = origem.get(documento.nome)
        if documento.anexo_id or par is None:
            continue
        documento.anexo_id, documento.enviado_em, documento.enviado_por_id = par.anexo_id, par.enviado_em, par.enviado_por_id
        documento.validade_ate = par.validade_ate
        documento.reaproveitado_de, documento.reaproveitado_contrato = setembro.competencia, None
        trazidos.append(documento.nome)
    faltando = [d.nome for d in agosto.documentos if d.obrigatorio and not d.anexo_id]
    print("Trazidos da 09/2026:", trazidos)
    print("Sem anexo (opcionais):", [d.nome for d in agosto.documentos if not d.anexo_id])
    if faltando:
        sys.exit(f"Faltam obrigatórios: {faltando}. Nada foi alterado.")
    if "--aplicar" not in sys.argv:
        s.rollback()
        sys.exit("Simulação: nada foi gravado. Rode com --aplicar.")
    autor = usuario_sistema(s)
    sc.concluir_etapa_paralela(agosto, "checklist")
    sc._auditar(s, autor, "contrato.execucao.checklist.concluir", agosto.contrato, agosto, documentos_da_competencia_09_2026=trazidos,
                opcionais_sem_anexo=[d.nome for d in agosto.documentos if not d.anexo_id], motivo="Documentos da 09/2026 trazidos a pedido do gestor")
    s.commit()
    print("Checklist da 08/2026 concluído. Etapa atual:", agosto.etapa_atual)
