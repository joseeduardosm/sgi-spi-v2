# Criado por José Eduardo Santana Martins
# Este arquivo serve para implantar direto, sem portaria, a equipe do contrato 017/2026 (Locação Datacenter).
"""Implantação direta da equipe do contrato 017/2026, a pedido do solicitante, dispensando a portaria.

Gestor: Guilherme de Sousa Lima (gslima); fiscal administrativo: Anderson Raphael Monteiro Dias (adias); fiscal técnico: José Eduardo
Santana Martins (jesmartins). O contrato não tinha equipe nem portaria. Só mexe nesse contrato; tudo vai numa única sessão.

Uso: cd backend && .venv/bin/python scripts_manutencao/implantar_equipe_contrato_017_2026.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao, agora_utc  # noqa: E402
from app.models.contratos import Contrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.contratos import setor_equipes  # noqa: E402
from app.services.contratos.servico_contratos import aplicar_equipe_por_ids, designacoes_vigentes  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO_ID = uuid.UUID("fb71cb8b-0a37-4a94-8e17-358460b01a2e")
NOVOS = {"gestor": "gslima", "fiscal_administrativo": "adias", "fiscal_tecnico": "jesmartins"}

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    if contrato is None:
        sys.exit("Contrato não encontrado: nada foi alterado.")
    ids = {papel: s.scalar(select(Usuario.id).where(Usuario.login == login, Usuario.ativo.is_(True))) for papel, login in NOVOS.items()}
    if None in ids.values():
        sys.exit(f"Usuário não encontrado ou inativo: {ids}. Nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    print("Contrato:", contrato.numero, "| autor da operação:", autor.login)
    print("Equipe antes:", [(d.papel, d.nome_usuario) for d in designacoes_vigentes(contrato)])
    mudancas = aplicar_equipe_por_ids(s, contrato, ids, agora_utc())
    contrato.versao += 1
    s.flush()
    setor_equipes.sincronizar(s)
    auditar(s, autor.login, "contrato.equipe.alterar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"campos": mudancas, "origem": "Implantada diretamente a pedido de jesmartins (sem portaria)"})
    s.commit()
    print("Mudanças:", mudancas)

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    print("Equipe agora:", [(d.papel, d.nome_usuario) for d in designacoes_vigentes(contrato)])
