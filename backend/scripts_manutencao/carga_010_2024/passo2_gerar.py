# Criado por José Eduardo Santana Martins
# Este arquivo serve para o passo 2 da carga do contrato 010/2024: previsão das vigências retroativas e geração das competências.
import sys
sys.path.insert(0, "scripts_manutencao/carga_010_2024")
from apoio import ALVO, abrir  # noqa: E402
from app.services.contratos import servico_competencias, servico_orcamento  # noqa: E402

sessao, s, contrato, autor = abrir()
sit = servico_competencias.requisitos(contrato)
print(f"[{ALVO}] prontos={sit.prontos} pendências={sit.pendencias}")
if sit.prontos:
    print("geradas:", servico_competencias.gerar_competencias(s, contrato.id, autor))
sessao.__exit__(None, None, None)
