"""
===============================================================================
ARQUIVO: cap.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ferramenta de captura de telas dos manuais: abre o navegador, entra no
sistema e tira prints com setas numeradas, gravando as legendas.

RESUMO TÉCNICO:
Usa o Playwright (automação do Chromium). `abrir` cria o navegador e o
contexto (tamanho da janela, pt-BR, fuso de São Paulo); `entrar` faz login
pela tela; `foto` destaca os elementos com retângulo, seta e número (o
JavaScript de JS_ANOTAR desenha um SVG por cima da página), salva o PNG em
imgs/ e grava a legenda de cada número em legendas.json.

FINALIDADE DE NEGÓCIO:
Produz prints padronizados e explicados para os manuais que orientam os
servidores da SPI no uso do SGI SPI.

CONTEXTO NO SISTEMA:
Ferramenta de documentação (laboratório), fora do sistema. Importado com
`from cap import *` por rodar*.py; aponta para o lab_web.py (porta 8200).
As legendas são lidas depois pelo publicar_final.py.

===============================================================================
"""

import json, os, sys, time
from playwright.sync_api import sync_playwright
# Pasta dos prints, endereço do laboratório e legendas já gravadas (acumuladas entre roteiros).
IMG = os.path.abspath("imgs"); os.makedirs(IMG, exist_ok=True)
BASE = "http://127.0.0.1:8200"
LEG = json.load(open("legendas.json")) if os.path.exists("legendas.json") else {}

# JavaScript rodado na página: para cada item, desenha retângulo, seta e bolinha
# numerada (lado = de onde vem a seta: esq, dir, cima ou baixo).
JS_ANOTAR = """
(itens) => {
  document.querySelectorAll('.__anot').forEach(e => e.remove());
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.classList.add('__anot');
  svg.setAttribute('style', 'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483647');
  svg.innerHTML = '<defs><marker id="__p" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#c82331"/></marker></defs>';
  document.body.appendChild(svg);
  for (const it of itens) {
    const el = document.querySelector(it.sel); if (!el) { console.log('sem elemento', it.sel); continue; }
    const r = el.getBoundingClientRect();
    const lado = it.lado || 'esq';
    let ex, ey, bx, by;
    if (lado === 'esq') { ex = r.left - 2; ey = r.top + Math.min(r.height / 2, 24); bx = ex - 58; by = ey; }
    else if (lado === 'dir') { ex = r.right + 2; ey = r.top + Math.min(r.height / 2, 24); bx = ex + 58; by = ey; }
    else if (lado === 'cima') { ex = r.left + Math.min(r.width / 2, 60); ey = r.top - 2; bx = ex; by = ey - 52; }
    else { ex = r.left + Math.min(r.width / 2, 60); ey = r.bottom + 2; bx = ex; by = ey + 52; }
    const box = document.createElementNS(NS, 'rect');
    box.setAttribute('x', r.left - 3); box.setAttribute('y', r.top - 3); box.setAttribute('width', r.width + 6); box.setAttribute('height', r.height + 6);
    box.setAttribute('rx', 6); box.setAttribute('fill', 'none'); box.setAttribute('stroke', '#c82331'); box.setAttribute('stroke-width', '2');
    svg.appendChild(box);
    const l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', bx); l.setAttribute('y1', by); l.setAttribute('x2', ex); l.setAttribute('y2', ey);
    l.setAttribute('stroke', '#c82331'); l.setAttribute('stroke-width', '3'); l.setAttribute('marker-end', 'url(#__p)'); svg.appendChild(l);
    const c = document.createElementNS(NS, 'circle'); c.setAttribute('cx', bx); c.setAttribute('cy', by); c.setAttribute('r', 14); c.setAttribute('fill', '#c82331'); svg.appendChild(c);
    const t = document.createElementNS(NS, 'text'); t.setAttribute('x', bx); t.setAttribute('y', by + 5); t.setAttribute('text-anchor', 'middle');
    t.setAttribute('fill', '#fff'); t.setAttribute('font-size', '15'); t.setAttribute('font-weight', '700'); t.setAttribute('font-family', 'Arial'); t.textContent = it.n; svg.appendChild(t);
  }
}
"""

def abrir(p, w=1366, h=860):
    """Abre o Chromium e um contexto com janela w x h, em pt-BR e no fuso de São Paulo; devolve (navegador, contexto)."""
    env = dict(os.environ); 
    nav = p.chromium.launch(args=["--no-sandbox"], env=env)
    ctx = nav.new_context(viewport={"width": w, "height": h}, locale="pt-BR", timezone_id="America/Sao_Paulo"); return nav, ctx

def entrar(ctx, login, senha="senha-lab-1"):
    """Abre a tela de login, entra com `login`/`senha` e espera sair da tela de login; devolve a página."""
    pg = ctx.new_page(); pg.goto(BASE + "/login"); pg.wait_for_load_state("networkidle")
    pg.fill("input[name=login], #login, input[autocomplete=username]", login); pg.fill("input[type=password]", senha)
    pg.keyboard.press("Enter"); pg.wait_for_url(lambda u: "/login" not in u, timeout=20000); pg.wait_for_load_state("networkidle"); return pg

def foto(pg, nome, anot=(), rolar=None, legendas=None, cheia=False):
    """anot: [(seletor, n, lado)]; legendas: textos na ordem de n."""
    # Rola até o elemento indicado e sobe um pouco, para ele não ficar sob o cabeçalho.
    if rolar: pg.locator(rolar).first.scroll_into_view_if_needed(); pg.evaluate("window.scrollBy(0,-90)")
    pg.wait_for_timeout(400)
    # Esconde o botão flutuante de melhorias, que não deve aparecer nos manuais.
    pg.evaluate("document.querySelectorAll('[data-an]').forEach(e => e.removeAttribute('data-an'))")
    pg.add_style_tag(content="app-botao-melhorias, .botao-melhorias, .fab-melhorias { display: none !important }")
    itens = []
    # Alvo pode ser um seletor CSS ou um Locator do Playwright; o Locator ganha um
    # atributo data-an temporário para virar seletor.
    for i, (alvo, n, lado) in enumerate(anot):
        if isinstance(alvo, str): itens.append({"sel": alvo, "n": n, "lado": lado}); continue
        alvo.first.evaluate("(e, i) => e.setAttribute('data-an', 'a' + i)", i); itens.append({"sel": f"[data-an=a{i}]", "n": n, "lado": lado})
    pg.evaluate(JS_ANOTAR, itens)
    pg.screenshot(path=f"{IMG}/{nome}.png", full_page=cheia)
    # Grava as legendas do print na ordem dos números das setas.
    if legendas: 
        LEG[nome] = [{"n": i + 1, "texto": t} for i, t in enumerate(legendas)]
        json.dump(LEG, open("legendas.json", "w"), ensure_ascii=False, indent=1)
    print("foto", nome)
