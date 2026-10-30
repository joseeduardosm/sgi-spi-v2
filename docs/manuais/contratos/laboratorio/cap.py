import json, os, sys, time
from playwright.sync_api import sync_playwright
IMG = os.path.abspath("../imagens"); os.makedirs(IMG, exist_ok=True)
BASE = "http://127.0.0.1:8200"
LEGENDAS_ARQ = os.path.abspath("../legendas.json")
LEG = json.load(open(LEGENDAS_ARQ)) if os.path.exists(LEGENDAS_ARQ) else {}

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
    env = dict(os.environ); 
    nav = p.chromium.launch(args=["--no-sandbox"], env=env)
    ctx = nav.new_context(viewport={"width": w, "height": h}, locale="pt-BR", timezone_id="America/Sao_Paulo"); return nav, ctx

def entrar(ctx, login, senha="senha-lab-1"):
    pg = ctx.new_page(); pg.goto(BASE + "/login"); pg.wait_for_load_state("networkidle")
    pg.fill("input[name=login], #login, input[autocomplete=username]", login); pg.fill("input[type=password]", senha)
    pg.keyboard.press("Enter"); pg.wait_for_url(lambda u: "/login" not in u, timeout=20000); pg.wait_for_load_state("networkidle"); return pg

def foto(pg, nome, anot=(), rolar=None, legendas=None, cheia=False):
    """anot: [(seletor, n, lado)]; legendas: textos na ordem de n."""
    if rolar: pg.add_style_tag(content="body::after { content: ''; display: block; height: 900px }"); pg.wait_for_timeout(100); pg.locator(rolar).first.evaluate("e => e.scrollIntoView({block: 'start', behavior: 'instant'})"); pg.evaluate("window.scrollBy({top: -130, behavior: 'instant'})")
    pg.wait_for_timeout(400)
    pg.evaluate("document.querySelectorAll('[data-an]').forEach(e => e.removeAttribute('data-an'))")
    pg.add_style_tag(content="app-botao-melhorias, .botao-melhorias, .fab-melhorias { display: none !important }")
    itens = []
    for i, (alvo, n, lado) in enumerate(anot):
        if isinstance(alvo, str): itens.append({"sel": alvo, "n": n, "lado": lado}); continue
        alvo.first.evaluate("(e, i) => e.setAttribute('data-an', 'a' + i)", i); itens.append({"sel": f"[data-an=a{i}]", "n": n, "lado": lado})
    pg.evaluate(JS_ANOTAR, itens)
    clip = None
    if rolar:
        # O espaço extra no fim da página (só para permitir a rolagem) fica de fora: recorta no rodapé do sistema
        fundo = pg.evaluate("(() => { const r = document.querySelector('app-rodape'); return r ? r.getBoundingClientRect().bottom : 0 })()")
        if 300 < fundo < 860: clip = {"x": 0, "y": 0, "width": 1366, "height": fundo + 6}
    pg.screenshot(path=f"{IMG}/{nome}.png", full_page=cheia, clip=clip)
    if legendas: 
        LEG[nome] = [{"n": i + 1, "texto": t} for i, t in enumerate(legendas)]
        json.dump(LEG, open(LEGENDAS_ARQ, "w"), ensure_ascii=False, indent=1)
    print("foto", nome)
