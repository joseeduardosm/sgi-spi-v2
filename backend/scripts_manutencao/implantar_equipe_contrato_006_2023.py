# Criado por José Eduardo Santana Martins
# Este arquivo serve para implantar de uma vez a equipe do contrato 006/2023 (SAM - PD023333) e cancelar a portaria de designação em andamento.
"""Implantação direta da equipe do contrato 006/2023, a pedido do solicitante, dispensando a portaria.

A equipe passa a ser exatamente a nomeada na portaria em andamento (Guilherme de Sousa Lima, gestor; Anderson Raphael Monteiro Dias, fiscal
administrativo; José Eduardo Santana Martins, fiscal técnico): as demais funções ficam sem designado, e as designações antigas continuam no
histórico com as datas. Depois a portaria é cancelada pelo serviço do sistema (que libera o número no Protocolo, se houver).
Só mexe nesse contrato. Tudo vai numa única sessão: se algo falhar, nada é gravado.

Uso: cd backend && .venv/bin/python scripts_manutencao/implantar_equipe_contrato_006_2023.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao, agora_utc  # noqa: E402
from app.models.contratos import PAPEIS_EQUIPE, Contrato  # noqa: E402
from app.models.contratos.portaria import PortariaContrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.contratos import servico_portaria, setor_equipes  # noqa: E402
from app.services.contratos.servico_contratos import aplicar_equipe_por_ids, designacoes_vigentes  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO_ID = uuid.UUID("86459d18-d9b2-4c50-bd09-ca6f07d6e7cc")
MOTIVO = "Equipe implantada diretamente a pedido do solicitante; portaria dispensada."

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    portaria = s.scalar(select(PortariaContrato).where(PortariaContrato.contrato_id == CONTRATO_ID, PortariaContrato.status == "aguardando_autoridade"))
    if contrato is None or portaria is None:
        sys.exit("Contrato ou portaria em 'aguardando_autoridade' não encontrados: nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    print("Contrato:", contrato.numero, "| autor da operação:", autor.login)
    print("Equipe antes:", [(d.papel, d.nome_usuario) for d in designacoes_vigentes(contrato)])
    nomeados = {n.papel: n.usuario_id for n in portaria.nomeacoes}
    mudancas = aplicar_equipe_por_ids(s, contrato, {papel: nomeados.get(papel) for papel in PAPEIS_EQUIPE}, agora_utc())
    contrato.versao += 1
    s.flush()
    setor_equipes.sincronizar(s)
    auditar(s, autor.login, "contrato.equipe.alterar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"campos": mudancas, "origem": "Implantada diretamente a pedido de jesmartins (portaria cancelada)"})
    servico_portaria.cancelar(s, CONTRATO_ID, portaria.id, MOTIVO, autor)  # grava (commit) equipe e cancelamento juntos
    print("Mudanças:", mudancas)

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    print("Equipe agora:", [(d.papel, d.nome_usuario) for d in designacoes_vigentes(contrato)])
    print("Portarias:", [(p.status, p.motivo) for p in s.scalars(select(PortariaContrato).where(PortariaContrato.contrato_id == CONTRATO_ID))])
