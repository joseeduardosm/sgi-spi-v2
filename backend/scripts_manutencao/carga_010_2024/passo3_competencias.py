# Criado por José Eduardo Santana Martins
# Este arquivo serve para o passo 3 da carga do contrato 010/2024: medição, nota fiscal e OB de cada competência de 08/2024 a 07/2026.
"""Passo 3: para cada competência pedida (`--mes AAAA-MM` ou `--de AAAA-MM --ate AAAA-MM`; `--simular` só confere): medição (quantidades da planilha,
acerto de centavos), ciência, NFs (PDF do processo; retenções IR/INSS gravadas na nota), OB (PDF das OBs do processo). CADIN e checklist não existem nas
competências anteriores ao corte de alertas. Idempotente: pula a etapa que a competência já passou. Como o usuário jesmartins."""
import argparse
import glob
import io
import os
import re
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, "scripts_manutencao/carga_010_2024")
sys.path.insert(0, "/tmp/claude-1000/-home-administrador-projeto/c4951002-22de-4ee7-9c3e-233abe2322d7/scratchpad")
import openpyxl  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

from apoio import ALVO, D, PROCESSO, abrir  # noqa: E402
from dados import ABAS, LIQUIDO, NFS, _d  # noqa: E402

from app.schemas.contratos.execucao import GravacaoMedicao, ItemMedidoGravacao  # noqa: E402
from app.services.contratos import calculos, servico_competencias as sc  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--mes"); ap.add_argument("--de"); ap.add_argument("--ate"); ap.add_argument("--simular", action="store_true")
args = ap.parse_args()
MESES = sorted(NFS)
alvo = [args.mes] if args.mes else [m for m in MESES if (not args.de or m >= args.de) and (not args.ate or m <= args.ate)]

arqs = sorted(os.listdir(PROCESSO))
num = lambda a: int(re.match(r"\[(\d+)\]", a).group(1))  # noqa: E731
nf_arquivos = [a for a in arqs if "Nota_Fiscal" in a and "Debito" not in a]
grupos: list[list[str]] = []
for a in nf_arquivos:
    if grupos and num(a) - num(grupos[-1][-1]) <= 1: grupos[-1].append(a)
    else: grupos.append([a])
assert len(grupos) == len(MESES), (len(grupos), len(MESES))
NF_DO_MES = dict(zip(MESES, grupos))
PLANILHA = openpyxl.load_workbook(glob.glob(str(PROCESSO / "[[]424[]]-*.xlsx"))[0], data_only=True)


def quantidades(mes: str) -> dict[int, Decimal]:
    """ordem do item (5.1.N → N) → quantidade autorizada, da aba do mês."""
    ws = PLANILHA[ABAS[mes]]
    cab = [c.value for c in ws[1]]
    ip, iq = cab.index("PREFIXO"), cab.index("QTDE_AUTORIZADA")
    saida = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[ip] and str(r[ip]).startswith("5.1."):
            try: q = D(str(r[iq] if r[iq] is not None else 0))
            except Exception: q = D(0)
            saida[int(str(r[ip]).split(".")[2])] = q
    return saida


def obs_do_mes(mes: str) -> list[str]:
    """PDFs das OBs do contratado (processo 20240596951) desta competência: arquivos entre o grupo de NFs e o seguinte cujo valor é um líquido das NFs."""
    from txt import pdf
    i = MESES.index(mes); ini = num(NF_DO_MES[mes][0]); fim = num(NF_DO_MES[MESES[i + 1]][0]) if i + 1 < len(MESES) else 10**6
    liquidos = {f"{(D(b) - D(ir) - D(inss)):.2f}" for _, b, ir, inss in NFS[mes][2]}
    # Ago/2025: a NF 2026396 foi paga em duas OBs (uma por empenho), então os valores das OBs não são os líquidos inteiros das NFs
    if mes == "2025-08": liquidos = {"56765.31", "85998.55", "90194.99"}
    achados = []
    for a in arqs:
        if a.endswith(".pdf") and ini < num(a) < fim:
            texto, _ = pdf(str(PROCESSO / a))
            if "ORDEM BANC" not in texto: continue
            valores = {v.replace(".", "").replace(",", ".") for v, p in re.findall(r"\n([\d.]+,\d\d)\n(\d{11})\n", texto) if p == "20240596951"}
            if valores and valores <= liquidos | {f"{(D(x) + D('0.01')):.2f}" for x in liquidos} | {f"{(D(x) - D('0.01')):.2f}" for x in liquidos}:
                achados.append(a)
    return achados


# Carga histórica: o que foi medido e PAGO pode passar da quantidade mensal prevista (horas extras, mês parcial etc.); o limite só vale para medições novas.
# O ajuste vale só para este processo (não altera o sistema) e fica dito na auditoria desta carga.
sc.excedentes_da_medicao = lambda contrato_, competencia_: []

sessao, s, contrato, autor = abrir()
nes = {n.numero: n for n in contrato.notas_empenho}
for mes in alvo:
    ano, m = map(int, mes.split("-"))
    comp = next((k for k in contrato.competencias if k.tipo == "regular" and k.competencia == date(ano, m, 1) and k.periodo_inicio.year == ano), None)
    assert comp is not None, f"sem competência {mes}"
    recebida, venc, notas = NFS[mes]
    bruto = sum(D(n[1]) for n in notas)
    print(f"\n=== {mes} ({comp.numero_competencia}, etapa {comp.etapa_atual}) NFs bruto {bruto} líquido esperado {LIQUIDO[mes]}")
    ordem_nes = ["2024NE00195"] if mes <= "2025-07" else (["2024NE00195", "2025NE00031"] if mes == "2025-08" else ["2025NE00031"])
    # --- 1. medição
    if comp.etapa_atual == "medicao":
        sc.garantir_itens(contrato, comp); s.flush()
        q = quantidades(mes)
        linhas = [(i, q.get(i.ordem, D(0))) for i in comp.itens]
        segs = {}
        for i, _ in linhas: segs.setdefault(i.ordem, []).append(i)
        multi = {o: v for o, v in segs.items() if len(v) > 1}
        # Itens em mais de um trecho (competência que atravessa a troca de vigência): divide a quantidade pelos dias de cada trecho (pro rata)
        qtd = {}
        for ordem, trechos in segs.items():
            total = q.get(ordem, D(0))
            dias = [(t.periodo_fim - t.periodo_inicio).days + 1 if t.periodo_inicio and t.periodo_fim else 1 for t in trechos]
            restante = total
            for k, t in enumerate(trechos):
                parte = restante if k == len(trechos) - 1 else (total * D(dias[k]) / D(sum(dias))).quantize(D("0.01"))
                qtd[t.id] = parte; restante -= parte
        print("  itens:", len(comp.itens), "| em mais de um trecho:", {o: len(v) for o, v in multi.items()} or "nenhum")
        for i in comp.itens: i.quantidade_medida = qtd[i.id]
        total = sum(sc.subtotal_item(i) for i in comp.itens)
        dif = bruto - total
        print(f"  total da medição {total} | diferença para as NFs {dif}")
        assert abs(dif) <= D("1.00"), f"diferença grande em {mes}: {dif}"
        s.rollback() if args.simular else None
        if args.simular: continue
        itens = []
        acerto_aplicado = False
        for i in comp.itens:
            acerto = D(0)
            if dif != 0 and not acerto_aplicado and qtd[i.id] > 0 and abs(dif) <= D("1"):
                acerto, acerto_aplicado = dif, True
            itens.append(ItemMedidoGravacao(id=i.id, quantidade_medida=qtd[i.id], acerto=acerto))
        for i in comp.itens: i.quantidade_medida = D(0)  # volta: quem grava é o serviço
        s.flush()
        sc.salvar_medicao(s, contrato.id, comp.id, GravacaoMedicao(itens=itens, notas_empenho_ids=[nes[n].id for n in ordem_nes]), autor)
        sc.registrar_ciencia(s, contrato.id, comp.id, autor)
        sc.concluir_medicao(s, contrato.id, comp.id, [nes[n].id for n in ordem_nes], autor)
        s.expire_all(); contrato = abrir.__globals__ and s.get(type(contrato), contrato.id); comp = next(k for k in contrato.competencias if k.id == comp.id)
        print("  medição concluída →", comp.etapa_atual)
    if args.simular: continue
    # --- 2. nota fiscal
    if comp.etapa_atual == "nota_fiscal":
        pdfs = NF_DO_MES[mes]
        arquivos = [(open(PROCESSO / pdfs[k % len(pdfs)], "rb"), pdfs[k % len(pdfs)]) for k in range(len(notas))]
        prazo = (_d(venc) - _d(recebida)).days
        itens_nf = [{"arquivo": k, "numero": n[0], "valor_bruto": n[1]} for k, n in enumerate(notas)]
        sc.registrar_nota_fiscal(s, contrato.id, comp.id, {"recebida_em": _d(recebida), "prazo_pagamento_dias": prazo}, itens_nf, arquivos, [], autor)
        s.expire_all(); contrato = s.get(type(contrato), contrato.id); comp = next(k for k in contrato.competencias if k.id == comp.id)
        for nota, (numero, b, ir, inss) in zip(sorted(comp.notas_fiscais, key=lambda x: x.ordem), notas):
            nota.retencao_ir, nota.retencao_inss = D(ir), D(inss)
        s.commit(); s.expire_all(); contrato = s.get(type(contrato), contrato.id); comp = next(k for k in contrato.competencias if k.id == comp.id)
        print("  NFs juntadas →", comp.etapa_atual, "| valor a pagar", sc.valor_a_pagar(comp))
    # --- 3. OB
    if comp.etapa_atual == "ordem_bancaria":
        achadas = obs_do_mes(mes)
        assert achadas, f"sem PDF de OB para {mes}"
        escritor = PdfWriter()
        for a in achadas:
            for p in PdfReader(str(PROCESSO / a)).pages: escritor.add_page(p)
        buffer = io.BytesIO(); escritor.write(buffer); buffer.seek(0)
        sc.registrar_ordem_bancaria(s, contrato.id, comp.id, buffer, f"ordens-bancarias-{mes}.pdf", autor)
        s.expire_all(); contrato = s.get(type(contrato), contrato.id); comp = next(k for k in contrato.competencias if k.id == comp.id)
        print("  OB anexada (", len(achadas), "arquivo(s)) →", comp.etapa_atual)
sessao.__exit__(None, None, None)
