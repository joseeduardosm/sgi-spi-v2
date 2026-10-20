# Criado por José Eduardo Santana Martins
# Este arquivo serve para corrigir a grafia da descrição do item do contrato 017/2026 ("erviços" -> "Serviços").
"""Correção única de redação: o item "erviços de Fornecimento de Hardware como Serviço (Hardware as a Service – HaaS)" perdeu a letra S inicial.

Corrige o item do contrato e as cópias dele nas competências (a medição copia a descrição do cadastro). Só mexe nesse contrato.

Uso: cd backend && .venv/bin/python scripts_manutencao/corrigir_descricao_item_contrato_017_2026.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratos import Contrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO_ID = uuid.UUID("fb71cb8b-0a37-4a94-8e17-358460b01a2e")
ERRADO = "erviços de Fornecimento de Hardware como Serviço (Hardware as a Service – HaaS)"
CERTO = "Serviços de Fornecimento de Hardware como Serviço (Hardware as a Service – HaaS)"

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    itens = [i for i in contrato.itens if i.descricao == ERRADO]
    copias = [m for c in contrato.competencias for m in c.itens if m.descricao == ERRADO]
    if not itens:
        sys.exit("Item com a redação errada não encontrado: nada foi alterado.")
    for i in itens:
        i.descricao = CERTO
    for m in copias:
        m.descricao = CERTO
    auditar(s, autor.login, "contrato.item.corrigir_descricao", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"de": ERRADO, "para": CERTO, "itens": len(itens), "copias_em_competencias": len(copias)})
    s.commit()
    print("Itens corrigidos:", len(itens), "| cópias nas competências:", len(copias))

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    print("Agora:", [i.descricao for i in contrato.itens])
