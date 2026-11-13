# Prints do manual: repactuação pela CCT (com diferença manual negativa = crédito) e os créditos aplicados pelo gestor na medição.
# Roda depois de rodar_4_diferenca_manual.py (o reajuste de 01/03/2026 já concluído no laboratório).
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
PDF = "/tmp/claude-1000/-home-administrador-projeto/394947b1-66eb-494c-a248-14ce9096f589/scratchpad/termo.pdf"


def ir(pg, tela="repactuacao"):
    pg.goto(f"{BASE}/contratos/{ID}/{tela}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)


def pdf_em(pg, ancora):
    """Anexa o PDF ao seletor de arquivo mais próximo do texto-âncora."""
    pg.locator(f"xpath=//*[contains(normalize-space(.), '{ancora}')]/following::input[@type='file'][1]").first.set_input_files(PDF); pg.wait_for_timeout(500)


import os


def prints_da_medicao(pg):
    """Medição de outubro preenchida (saldo líquido e NE) e o crédito: disponível e depois aplicado."""
    ir(pg, "execucao/2026-10")
    if pg.locator("tr.linha-desconto-reajuste button").count():  # já aplicado numa rodada anterior: devolve ao fundo
        pg.locator("tr.linha-desconto-reajuste button").first.click(); pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="Usar o saldo líquido").click(); pg.wait_for_timeout(500)
    selecao = pg.locator("select", has=pg.locator("option", has_text="Selecione uma NE"))
    if selecao.locator("option").count() > 1:  # NE ainda não escolhida nesta medição
        selecao.select_option(index=1); pg.wait_for_timeout(300)
        pg.get_by_role("button", name="Adicionar NE").click(); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Salvar medição").click(); pg.wait_for_timeout(3000)
    foto(pg, "md01-creditos-disponiveis",
         [(pg.locator("p.secao-formulario", has_text="Créditos disponíveis"), 1, "esq"), (pg.get_by_role("button", name="Aplicar nesta medição").first, 2, "dir")],
         rolar="p.secao-formulario:has-text('Créditos disponíveis')",
         legendas=["Créditos da SPI ainda não aplicados (de reajuste ou repactuação, calculados ou informados à mão)",
                   "Aplicar nesta medição: o crédito entra inteiro; cada crédito é independente"])
    pg.get_by_role("button", name="Aplicar nesta medição").first.click(); pg.wait_for_timeout(2500)
    foto(pg, "md02-credito-aplicado",
         [(pg.locator("tr.linha-desconto-reajuste").first, 1, "esq"), (pg.locator("tr.linha-desconto-reajuste button").first, 2, "cima"),
          (pg.locator(".aviso-bloco", has_text="Observação:"), 3, "esq")],
         rolar="tr.linha-desconto-reajuste",
         legendas=["O crédito aplicado aparece com a origem e é descontado do total medido", "Retirar: devolve o crédito ao fundo enquanto a medição estiver aberta",
                   "Crédito informado manualmente: a observação acompanha a medição e os documentos"])


if os.environ.get("SO_MEDICAO") == "1":
    with sync_playwright() as p:
        nav, ctx = abrir(p); ctx.set_default_timeout(25000)
        pg = entrar(ctx, "marina")
        ir(pg)
        foto(pg, "rp08-historico", [(pg.locator("#titulo-historico-repactuacao"), 1, "esq")], rolar="#titulo-historico-repactuacao",
             legendas=["Histórico: cada repactuação com o retroativo (e o valor manual) e os arquivos para baixar"])
        prints_da_medicao(pg); nav.close()
    raise SystemExit


with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(25000)
    pg = entrar(ctx, "marina"); ir(pg)
    # Abertura: CCT 05/2026, novos valores a partir de 01/07/2026
    pg.fill("#rep-data-base", "2026-05"); pg.fill("#rep-efeito", "2026-07-01"); pdf_em(pg, "Iniciar repactuação")
    foto(pg, "rp01-iniciar-repactuacao",
         [(pg.locator("#rep-data-base"), 1, "cima"), (pg.locator("#rep-efeito"), 2, "cima"), (pg.locator("app-envio-pdf").first, 3, "esq"),
          (pg.get_by_role("button", name="Abrir repactuação"), 4, "cima")],
         rolar="#titulo-iniciar-repactuacao",
         legendas=["Data-base da CCT (mês e ano)", "Data a partir da qual os novos valores valem", "PDF da Convenção Coletiva: vai também para os Documentos importantes",
                   "Abrir repactuação: cria a elaboração"])
    pg.get_by_role("button", name="Abrir repactuação").click(); pg.wait_for_timeout(3000)
    # Cadastro: componente de custo que diminuiu, vinculado ao item contínuo
    pg.fill("#rep-desc-0", "Plano de saúde"); pg.fill("#rep-vig-0", "120,00"); pg.fill("#rep-rep-0", "100,00")
    pg.locator("input[name^='vinc-0-']").first.check(); pg.wait_for_timeout(1500)
    foto(pg, "rp02-cadastro-das-linhas",
         [(pg.locator("#rep-desc-0"), 1, "cima"), (pg.locator("#rep-rep-0"), 2, "cima"), (pg.locator("input[name^='vinc-0-']").first, 3, "esq"),
          (pg.get_by_role("button", name="Finalizar cadastro"), 4, "cima")],
         rolar="#titulo-repactuacao",
         legendas=["Componente de custo que a CCT mudou (ex.: vale-transporte, plano de saúde)", "Valor vigente e valor repactuado, já por unidade do item financeiro",
                   "Itens do contrato que recebem a diferença (um ou mais)", "Finalizar cadastro: libera a memória de cálculo"])
    pg.get_by_role("button", name="Finalizar cadastro").click(); pg.wait_for_timeout(3000)
    foto(pg, "rp03-memoria-de-calculo", [(pg.locator("#titulo-memoria-repactuacao"), 1, "esq")], rolar="#titulo-memoria-repactuacao",
         legendas=["Preço vigente de cada item + as diferenças das linhas vinculadas, e a nova base mensal"])
    # Retroativo: julho a outubro encerrados sem medição -> pergunta da diferença manual
    manual = pg.locator("app-diferenca-manual")
    foto(pg, "rp04-retroativo-e-pergunta",
         [(pg.locator("#titulo-retroativo-repactuacao"), 1, "esq"), (manual.locator(".aviso-bloco"), 2, "esq")], rolar="#titulo-retroativo-repactuacao",
         legendas=["Memória retroativa: competências a partir da data de vigência", "Meses encerrados sem medição: o sistema pergunta se você quer informar a diferença"])
    pg.get_by_role("button", name="Sim, inserir manualmente").click(); pg.wait_for_timeout(500)
    for rotulo in ("07/2026", "08/2026", "09/2026"):
        manual.locator("label", has_text=rotulo).locator("input[type=checkbox]").check()
    pg.fill("#diferenca-manual-valor", "-480,00")
    pg.fill("#diferenca-manual-justificativa", "Plano de saúde reduzido pela CCT 05/2026; julho a setembro pagos fora do sistema pelo valor antigo. Cálculo anexo.")
    manual.locator("input[type=file]").set_input_files(PDF); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Salvar diferença manual").click(); pg.wait_for_timeout(2500)
    foto(pg, "rp05-diferenca-manual-credito", [(manual.locator("dl"), 1, "esq"), (manual.locator(".aviso-bloco"), 2, "esq")], rolar="app-diferenca-manual",
         legendas=["Valor negativo: vira crédito da SPI no fundo do contrato", "Observação que acompanha o valor na memória e no consolidado"])
    # Memória, consolidado, apostilamento e finalização
    pg.get_by_role("button", name="Gerar e baixar memória (PDF e XLSX)").click(); pg.wait_for_timeout(4000)
    pg.get_by_role("button", name="Gerar consolidado").click(); pg.wait_for_timeout(4000)
    pdf_em(pg, "6. Apostilamento e finalização")
    foto(pg, "rp06-consolidado-e-finalizacao",
         [(pg.locator("#titulo-consolidado-repactuacao"), 1, "esq"), (pg.get_by_role("button", name="Finalizar repactuação"), 2, "cima")], rolar="#titulo-consolidado-repactuacao",
         legendas=["Consolidado: capa, CCT, checklist, memória e a memória externa da diferença manual, num PDF só",
                   "Finalizar: exige cadastro finalizado, memória e consolidado atualizados e o apostilamento assinado"])
    pg.get_by_role("button", name="Finalizar repactuação").click(); pg.wait_for_timeout(800)
    foto(pg, "rp07-confirmar-finalizacao", [], legendas=None)
    pg.wait_for_timeout(6000); pg.get_by_role("button").last.click(); pg.wait_for_timeout(3500)
    ir(pg)
    foto(pg, "rp08-historico", [(pg.locator("#titulo-historico-repactuacao"), 1, "esq")], rolar="#titulo-historico-repactuacao",
         legendas=["Histórico: cada repactuação com o retroativo (e o valor manual) e os arquivos para baixar"])
    prints_da_medicao(pg)
    nav.close()
