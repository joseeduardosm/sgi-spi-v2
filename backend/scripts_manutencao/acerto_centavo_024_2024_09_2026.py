# Criado por José Eduardo Santana Martins
# Este arquivo serve para levar a medição do contrato 024/2024, competência 09/2026, a R$ 243.448,94 (valor da nota fiscal), a pedido do solicitante.
"""Acerto de −R$ 0,01 na medição 024/2024 · 09/2026.

Com o total medido passando a ser a soma das linhas (cada item arredondado + acerto), esta competência foi a R$ 243.448,95, um centavo acima da nota fiscal
(R$ 243.448,94). O acerto do item 16 (Auxiliar de Serviços Gerais) vai de +R$ 0,12 para +R$ 0,11: o total volta a R$ 243.448,94 em todas as telas e documentos.
Gera a nova versão da memória de cálculo (a v1 mostrava as linhas somando R$ 243.448,95) e audita. Não reabre etapas nem envia e-mail.

Sem argumento só mostra; com `--aplicar` grava.

Uso: cd backend && .venv/bin/python scripts_manutencao/acerto_centavo_024_2024_09_2026.py [--aplicar]
"""
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.core.configuracao import obter_configuracao  # noqa: E402
from app.models.contratos import Competencia  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.contratos import servico_competencias as sc  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO = uuid.UUID("af350112-dfdf-431e-af92-7feae461fd68")
ITEM_ORDEM, ANTES, DEPOIS, ALVO = 16, Decimal("0.12"), Decimal("0.11"), Decimal("243448.94")

with FabricaSessao() as s:
    c = s.scalar(select(Competencia).where(Competencia.contrato_id == CONTRATO, Competencia.competencia == date(2026, 9, 1)))
    item = next(i for i in c.itens if i.ordem == ITEM_ORDEM)
    print(f"Item {item.ordem} {item.descricao_completa}: acerto {item.acerto}; total medido {sc.total_medido(c)}; autorizado {sc.valor_autorizado(c)}")
    if item.acerto != ANTES:
        sys.exit("O acerto do item não é o esperado: nada foi alterado.")
    item.acerto = DEPOIS
    s.flush()
    print(f"Depois: total medido {sc.total_medido(c)}; autorizado {sc.valor_autorizado(c)}; NF {[str(n.valor_bruto) for n in c.notas_fiscais]}")
    if sc.total_medido(c) != ALVO:
        sys.exit("O total não chegou a R$ 243.448,94: nada foi alterado.")
    if "--aplicar" not in sys.argv:
        s.rollback()
        print("Simulação: nada foi gravado. Rode com --aplicar.")
        sys.exit(0)
    root = s.scalar(select(Usuario).where(Usuario.login == obter_configuracao().login_admin))
    memoria = sc.gerar_memoria(s, c.contrato, c, root)
    auditar(s, root.login, "contrato.execucao.medicao.acerto", f"Contrato {c.contrato.numero} · 09/2026",
            f"Acerto do item {ITEM_ORDEM} de {ANTES} para {DEPOIS} (total R$ 243.448,94, igual à NF); memória v{memoria.versao}",
            autor_id=root.id, alvo_tipo="competencia", alvo_id=c.id)
    s.commit()
    print(f"Gravado. Memória de cálculo v{memoria.versao}.")
