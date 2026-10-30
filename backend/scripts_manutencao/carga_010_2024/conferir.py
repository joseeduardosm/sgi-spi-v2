# Criado por José Eduardo Santana Martins
# Este arquivo serve para conferir, depois da carga, o contrato 010/2024: etapas, totais por competência, saldos das NEs, e-mails e avisos gerados.
import sys
sys.path.insert(0, "scripts_manutencao/carga_010_2024")
from apoio import ALVO, D, abrir  # noqa: E402
from dados import LIQUIDO, NFS  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from app.models.notificacao import Notificacao  # noqa: E402
from app.services.contratos import servico_competencias as sc  # noqa: E402

sessao, s, contrato, autor = abrir()
print(f"[{ALVO}] processo financeiro: {contrato.processo_financeiro}")
ruins = 0
for k in sorted(contrato.competencias, key=lambda c: c.periodo_inicio):
    mes = f"{k.competencia:%Y-%m}"
    if mes not in NFS or k.periodo_fim > __import__("datetime").date(2026, 7, 31): continue
    bruto = sc.valor_a_pagar(k); esperado = sum(D(n[1]) for n in NFS[mes][2])
    liquido = bruto - sum(((n.retencao_ir or 0) + (n.retencao_inss or 0)) for n in k.notas_fiscais)
    ok = k.etapa_atual == "concluida" and bruto == esperado and abs(liquido - D(LIQUIDO[mes])) <= D("0.011") and k.email_ob_enviado_em is None and not k.email_medicao_ok
    ruins += not ok
    print(f"  {mes} {k.etapa_atual:<10} bruto {bruto} líquido {liquido} NFs {len(k.notas_fiscais)} {'OK' if ok else '<<< CONFERIR'}")
print("competências com problema:", ruins)
for n in sorted(contrato.notas_empenho, key=lambda n: n.numero):
    print(f"  NE {n.numero} original {n.valor_original} saldo {n.saldo}")
print("avisos (notificações) do contrato:", s.scalar(select(func.count()).select_from(Notificacao).where(Notificacao.contrato_id == contrato.id)))
sessao.__exit__(None, None, None)
