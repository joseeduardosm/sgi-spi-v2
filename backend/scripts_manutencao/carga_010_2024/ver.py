# Criado por José Eduardo Santana Martins
# Este arquivo serve para listar as competências do contrato 010/2024 (etapa, período, itens e total medido) durante a carga histórica.
import sys
sys.path.insert(0, "scripts_manutencao/carga_010_2024")
from apoio import ALVO, abrir  # noqa: E402
from app.services.contratos.servico_competencias import total_medido, e_retroativa  # noqa: E402

sessao, s, contrato, autor = abrir()
print(f"[{ALVO}] {len(contrato.competencias)} competências")
for k in sorted(contrato.competencias, key=lambda c: (c.periodo_inicio, c.tipo)):
    print(f"  {k.numero_competencia:>9} {k.tipo:<8} {k.periodo_inicio}..{k.periodo_fim} vig{k.sequencia_vigencia} etapa={k.etapa_atual:<14} itens={len(k.itens)} medido={total_medido(k)} retro={e_retroativa(k)}")
sessao.__exit__(None, None, None)
