# Prints do manual: diferença retroativa informada manualmente no reajuste (meses pagos fora do sistema) e a competência complementar.
import sys; sys.path.insert(0, "."); sys.path.append("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from cap import *
ID = open("/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio/ids.txt").read().split()[0]
PDF = "/tmp/claude-1000/-home-administrador-projeto/394947b1-66eb-494c-a248-14ce9096f589/scratchpad/termo.pdf"


def ir(pg, tela="reajuste"):
    pg.goto(f"{BASE}/contratos/{ID}/{tela}"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2000)


def pdf_em(pg, ancora):
    """Anexa o PDF ao seletor de arquivo mais próximo do texto-âncora."""
    pg.locator(f"xpath=//*[contains(normalize-space(.), '{ancora}')]/following::input[@type='file'][1]").first.set_input_files(PDF); pg.wait_for_timeout(500)


import os
SO_COMPLEMENTAR = os.environ.get("SO_COMPLEMENTAR") == "1"  # refaz só o print da complementar (o reajuste já está concluído no laboratório)


def foto_complementar(pg):
    """A competência complementar de uma linha, na execução, com a observação."""
    ir(pg, "execucao/2026-03-dif-manual")
    foto(pg, "rj11-complementar-diferenca-manual",
         [(pg.locator("table.tabela-gestao tbody tr").first, 1, "esq"), (pg.locator(".aviso-bloco", has_text="Observação:"), 2, "esq")],
         rolar="#titulo-medicao",
         legendas=["Uma linha só, com o valor informado: segue o fluxo normal (NE, nota fiscal, consolidado e OB)",
                   "A observação da diferença manual aparece na tela e nos documentos da competência"])


if SO_COMPLEMENTAR:
    with sync_playwright() as p:
        nav, ctx = abrir(p); ctx.set_default_timeout(25000)
        foto_complementar(entrar(ctx, "marina")); nav.close()
    raise SystemExit
with sync_playwright() as p:
    nav, ctx = abrir(p); ctx.set_default_timeout(25000)
    pg = entrar(ctx, "marina"); ir(pg)
    # Reajuste de 5% a partir de 01/03/2026: março a outubro estão encerrados e sem medição no sistema
    pg.fill("#reajuste-data", "2026-03-01"); pg.select_option("#reajuste-vigencia", index=0)
    pg.get_by_role("button", name="Abrir reajuste", exact=True).click(); pg.wait_for_timeout(2500)
    manual = pg.locator("app-diferenca-manual")
    foto(pg, "rj07-pergunta-diferenca-manual",
         [(manual.locator(".aviso-bloco"), 1, "cima"), (pg.get_by_role("button", name="Sim, inserir manualmente"), 2, "baixo"), (pg.get_by_role("button", name="Não", exact=True), 3, "dir")],
         rolar="app-diferenca-manual",
         legendas=["O sistema encontrou meses já encerrados, a partir da data de efeito, sem medição concluída", "Sim: abre o formulário para informar a diferença desses meses",
                   "Não: os meses seguem o fluxo normal e serão medidos com o preço novo"])
    pg.get_by_role("button", name="Sim, inserir manualmente").click(); pg.wait_for_timeout(500)
    for rotulo in ("03/2026", "04/2026", "05/2026", "06/2026"):
        manual.locator("label", has_text=rotulo).locator("input[type=checkbox]").check()
    pg.fill("#diferenca-manual-valor", "1.234,56")
    pg.fill("#diferenca-manual-justificativa", "Meses de março a junho de 2026 pagos antes da implantação do SGI, com o preço anterior ao reajuste. Cálculo na planilha anexa.")
    manual.locator("input[type=file]").set_input_files(PDF); pg.wait_for_timeout(500)
    foto(pg, "rj08-formulario-diferenca-manual",
         [(manual.locator(".linha-caixas"), 1, "esq"), (pg.locator("#diferenca-manual-valor"), 2, "esq"), (manual.locator("app-envio-pdf"), 3, "dir"),
          (pg.locator("#diferenca-manual-justificativa"), 4, "esq"), (pg.get_by_role("button", name="Salvar diferença manual"), 5, "baixo")],
         rolar="app-diferenca-manual",
         legendas=["Marque os meses que foram pagos fora do sistema", "Valor total da diferença desses meses (negativo = crédito da SPI)",
                   "PDF com a memória de cálculo feita fora do sistema", "Justificativa: sai na observação dos documentos", "Salvar: todos os campos são obrigatórios"])
    pg.get_by_role("button", name="Salvar diferença manual").click(); pg.wait_for_timeout(2500)
    foto(pg, "rj09-diferenca-manual-salva",
         [(manual.locator("dl"), 1, "esq"), (manual.locator(".aviso-bloco"), 2, "esq"), (pg.get_by_role("button", name="Alterar"), 3, "baixo")],
         rolar="app-diferenca-manual",
         legendas=["Meses pagos fora do sistema e o valor informado", "Observação que acompanha o valor em todos os documentos",
                   "Alterar ou remover enquanto o reajuste estiver em elaboração"])
    # Conclui o reajuste: evidência, memória (5%), arquivos, apostilamento
    pdf_em(pg, "1. Evidência do índice"); pg.get_by_role("button", name="Anexar").click(); pg.wait_for_timeout(2500)
    pg.fill("#indice-todos", "5"); pg.get_by_role("button", name="Aplicar a todos").click(); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="Salvar memória").click(); pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="Gerar e baixar PDF e XLSX").click(); pg.wait_for_timeout(4000)
    pdf_em(pg, "3. Apostilamento e conclusão")
    pg.get_by_role("button", name="Concluir e aplicar reajuste").click(); pg.wait_for_timeout(800)
    foto(pg, "rj10-confirmar-com-diferenca-manual", [], legendas=None)
    pg.wait_for_timeout(6000); pg.get_by_role("button").last.click(); pg.wait_for_timeout(3500)
    # A competência complementar de uma linha, na execução
    foto_complementar(pg)
    nav.close()
