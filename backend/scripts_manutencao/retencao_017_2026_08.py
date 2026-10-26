# Criado por José Eduardo Santana Martins
# Este arquivo serve para concluir a retenção de tributos da competência 08/2026 do contrato 017/2026, a pedido do gestor.
"""Retenção 017/2026 · 08/2026 (NF 00001093, bruto R$ 62.333,33).

Mesmo critério que o Financeiro usou na 09/2026 (NF 1101: R$ 8.160,00 = 4,8% do bruto, lançados em IR): 4,8% × R$ 62.333,33 = R$ 2.992,00 em IR,
demais tributos zerados. O líquido fica R$ 59.341,33, exatamente a OB 2026OB01889 do SIGEO ("11 DIAS AGO/26"). Usa o mesmo serviço da tela
(`servico_retencao.salvar_retencao`: PDF da conferência, avisos, auditoria e tarefas), em nome de quem pediu. Não envia e-mail.

Sem argumento só mostra; com `--aplicar` grava.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratos import Competencia, Contrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.contratos import servico_retencao  # noqa: E402

with FabricaSessao() as s:
    c = s.scalar(select(Competencia).join(Contrato).where(Contrato.numero == "017/2026", Competencia.competencia == date(2026, 8, 1), Competencia.tipo == "regular"))
    autor = s.scalar(select(Usuario).where(Usuario.login == "jesmartins"))
    nota = c.notas_fiscais[0]
    ir = (nota.valor_bruto * Decimal("0.048")).quantize(Decimal("0.01"))
    print(f"NF {nota.numero}: bruto {nota.valor_bruto}; IR 4,8% = {ir}; líquido {nota.valor_bruto - ir}; pode conferir: {servico_retencao.pode_conferir(s, c.contrato, autor)}")
    if "--aplicar" not in sys.argv:
        sys.exit("Simulação: nada foi gravado. Rode com --aplicar.")
    servico_retencao.salvar_retencao(s, c.contrato_id, c.id, {nota.id: {"ir": ir}}, True, autor)
    print("Retenção concluída. Etapa atual:", c.etapa_atual)
