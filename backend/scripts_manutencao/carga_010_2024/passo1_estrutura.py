# Criado por José Eduardo Santana Martins
# Este arquivo serve para o passo 1 da carga histórica do contrato 010/2024: Processo Financeiro, Notas de Empenho e vigências retroativas.
"""Passo 1: processo financeiro, NEs antigas e as duas vigências retroativas (1º TA e contrato original). Idempotente: não repete o que já existe."""
import sys
from datetime import date

sys.path.insert(0, "scripts_manutencao/carga_010_2024")
from apoio import ALVO, D, TERMOS, PROCESSO, abrir, arquivo  # noqa: E402

from app.schemas.contratos.orcamento import GravacaoNotaEmpenho  # noqa: E402
from app.services.contratos import servico_orcamento, servico_vigencia_retroativa  # noqa: E402

PROCESSOS_FINANCEIROS = "20240596951, 20250189447, 20260148724"
# Valores originais das NEs não constam no processo: 2024NE00195 = soma bruta das NFs que ela pagou; 2025NE00031 = SIGEO (R$ 1.081.826,38 + reforço de R$ 1.938.869,23)
BRUTO_PAGO_PELA_NE_2024 = [  # ago/24 a jul/25 (mês cheio) + a parte de ago/25 que o processo empenhou nela ([221])
    "169362.18", "180385.52", "152573.43", "153218.68", "182810.45", "256946.07", "222150.11", "205248.00", "238187.33", "219902.59", "226357.92", "234584.10", "186478.23"]
NE_2024 = sum((D(v) for v in BRUTO_PAGO_PELA_NE_2024), D(0))
NE_2025 = D("1081826.38") + D("1938869.23")

sessao, s, contrato, autor = abrir()
print(f"[{ALVO}] contrato {contrato.numero} início {contrato.data_inicio} processo_financeiro={contrato.processo_financeiro!r}")
if not contrato.processo_financeiro:
    contrato.processo_financeiro = PROCESSOS_FINANCEIROS
    s.commit(); print("processo financeiro gravado")
for numero, valor in (("2024NE00195", NE_2024), ("2025NE00031", NE_2025)):
    if not any(n.numero == numero for n in contrato.notas_empenho):
        servico_orcamento.criar_nota(s, contrato.id, GravacaoNotaEmpenho(numero=numero, valor_original=valor), autor); print("NE criada", numero, valor)
        s.expire_all(); contrato = s.get(type(contrato), contrato.id)
# Vigências retroativas: da mais recente para a mais antiga (cada uma termina na véspera do início atual)
TERMO_1 = TERMOS / "SEI_0077151247_Termo_Aditivo.pdf"
CONTRATO_ORIGINAL = next(PROCESSO.glob("[[]002[]]-*Contrato.pdf"))
def retro(meses, assinada, numero, pdf):
    if any(r.assinada_em == assinada for r in contrato.vigencias_retroativas): return
    servico_vigencia_retroativa.registrar(s, contrato.id, meses, assinada, numero, arquivo(pdf), autor); print("retroativa", numero, "meses", meses)
retro(12, date(2025, 8, 5), "1º Termo de Aditamento (SEI 0077151247)", TERMO_1)
s.expire_all(); contrato = s.get(type(contrato), contrato.id)
retro(12, date(2024, 8, 5), "Contrato 010/2024 (SEI 0040547976)", CONTRATO_ORIGINAL)
s.expire_all(); contrato = s.get(type(contrato), contrato.id)
print("início agora:", contrato.data_inicio, "| vigências:", [(v.sequencia, v.inicio, v.fim) for v in __import__("app.services.contratos.servico_contratos", fromlist=["vigencias"]).vigencias(contrato)])
print("NEs:", [(n.numero, n.valor_original) for n in contrato.notas_empenho])
sessao.__exit__(None, None, None)
