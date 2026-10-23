# Prints do manual: parâmetros do RH (setor de apoio administrativo).
import sys; sys.path.insert(0, ".")
from cap import *
with sync_playwright() as p:
    nav, ctx = abrir(p); pg = entrar(ctx, "rita")
    pg.goto(BASE + "/rh/parametros"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
    foto(pg, "p13-parametros-setor-apoio", [("#p-saa", 1, "esq")],
         legendas=["Setor de apoio administrativo (SAA): quem dá andamento nos números reservados do Protocolo. Antes era procurado pelo nome do setor no código; agora é escolhido aqui"], rolar="#p-saa")
    nav.close()
