# Criado por José Eduardo Santana Martins
# Este arquivo serve para o passo 4 da carga do contrato 010/2024: marcar nas 24 competências lançadas que vieram de carga histórica.
import sys
from datetime import date
sys.path.insert(0, "scripts_manutencao/carga_010_2024")
from apoio import ALVO, abrir  # noqa: E402
from dados import NFS  # noqa: E402
from app.core.banco import agora_utc  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

OBS = ("Esta competência foi lançada depois de paga, a partir do processo SEI de pagamento 021.00001802/2024-10 (planilha de medição, notas fiscais e ordens "
       "bancárias do processo). Por isso o limite mensal de quantidades não foi aplicado e a medição reflete o que de fato foi apurado e pago. "
       "Retenção, checklist, CADIN e consolidado não existem nesta competência.")
sessao, s, contrato, autor = abrir()
marcadas = 0
for k in contrato.competencias:
    if k.tipo == "regular" and f"{k.competencia:%Y-%m}" in NFS and k.periodo_fim <= date(2026, 7, 31) and k.carga_historica_em is None:
        k.carga_historica_em, k.carga_historica_obs = agora_utc(), OBS; marcadas += 1
auditar(s, autor.login, "contrato.execucao.carga_historica", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
        dados={"competencias": marcadas, "processo": "021.00001802/2024-10"})
s.commit()
print(f"[{ALVO}] {marcadas} competências marcadas")
sessao.__exit__(None, None, None)
