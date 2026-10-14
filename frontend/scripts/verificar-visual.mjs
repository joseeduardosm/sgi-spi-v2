// Criado por José Eduardo Santana Martins
// Este arquivo serve para conferir a interface com um Chromium sem tela: esqueletos, barra de progresso, entrada e saída de modal e menu, reduced-motion e erros de console.
// Verificação visual com Chromium headless: API simulada (nada real é tocado), esqueletos, reduced-motion e erros de console.
import { createServer } from 'node:http';
import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, extname } from 'node:path';
import { spawn } from 'node:child_process';

const DIST = join(process.cwd(), 'dist', 'sgi-spi', 'browser');
const SAIDA = process.argv[2];
const CHROME = process.env.CHROME ?? 'chromium';
const TIPOS = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json', '.json': 'application/json', '.woff2': 'font/woff2' };
mkdirSync(SAIDA, { recursive: true });

const servidor = createServer((req, res) => {
  const caminho = decodeURIComponent(req.url.split('?')[0]);
  let arquivo = join(DIST, caminho);
  if (!existsSync(arquivo) || caminho === '/' || !extname(caminho)) arquivo = join(DIST, 'index.html');
  res.writeHead(200, { 'Content-Type': TIPOS[extname(arquivo)] ?? 'application/octet-stream' });
  res.end(readFileSync(arquivo));
}).listen(4311);

const chrome = spawn(CHROME, ['--no-sandbox', '--disable-gpu', '--remote-debugging-port=9333', '--user-data-dir=' + (process.env.TMPDIR ?? '/tmp') + '/chrome-visual-sgi-' + Date.now(), '--window-size=1280,800', 'about:blank'], { stdio: 'ignore' });
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
let alvo;
for (let i = 0; i < 40; i++) { try { alvo = (await (await fetch('http://127.0.0.1:9333/json')).json()).find((t) => t.type === 'page'); if (alvo) break; } catch { /* aguardando */ } await dormir(250); }
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = new Map(); const eventos = [];
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } else eventos.push(d); };
const cdp = (metodo, params = {}) => new Promise((r) => { const n = ++id; pend.set(n, r); ws.send(JSON.stringify({ id: n, method: metodo, params })); });

const usuario = { id: 1, login: 'teste', nome_completo: 'Pessoa de Teste', papeis: ['SuperRoot'], origem: 'local', tema: 'claro' };
const sessao = { tokenAcesso: 'x.y.z', expiraEm: Date.now() + 3600_000, usuario };
const recursos = ['contratos', 'tarefas', 'patrimonio', 'rh', 'protocolo', 'reserva-espacos', 'contratacoes', 'noticias', 'manuais', 'diretorio'].map((slug, i) => ({ recurso_id: i + 1, nome: slug, slug, url_base: `/${slug}`, nivel: 'CONTROLE_TOTAL' }));
const ATRASO_API = Number(process.env.ATRASO_API ?? 2500);

await cdp('Page.enable'); await cdp('Runtime.enable'); await cdp('Log.enable');
await cdp('Fetch.enable', { patterns: [{ urlPattern: '*/api/*' }] });
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: `localStorage.setItem('sgi-spi.sessao', ${JSON.stringify(JSON.stringify(sessao))});` });
const erros = [];

// Responde às chamadas da API: sessão e acessos na hora; o restante com atraso, para dar tempo de ver o esqueleto
async function tratarFetch(e) {
  const url = new URL(e.request.url); const caminho = url.pathname;
  let corpo = [], espera = ATRASO_API;
  if (caminho.endsWith('/autenticacao/sessao')) { corpo = usuario; espera = 0; }
  else if (caminho.endsWith('/acl/meus-acessos')) { corpo = recursos; espera = 0; }
  else if (caminho.endsWith('/painel-executivo/acesso')) { corpo = { pode: true }; espera = 0; }
  else if (/resumo$/.test(caminho)) { corpo = { pendentes: 0, nao_lidas: 0, janela: null }; espera = 0; }
  else if (/\/(favoritos|recentes|atalhos)/.test(caminho)) { corpo = { itens: [] }; espera = 0; }
  else if (/\/preferencias/.test(caminho)) { corpo = {}; espera = 0; }
  else if (caminho.endsWith('/notificacoes/destinatarios')) { corpo = { usuarios: [], setores: [], pode_enviar_setores: false }; espera = 300; }
  else if (caminho.endsWith('/notificacoes') || caminho.endsWith('/notificacoes/enviadas')) { corpo = { itens: [], total: 0, pagina: 1, tamanho_pagina: 20 }; }
  await dormir(espera);
  await cdp('Fetch.fulfillRequest', { requestId: e.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }], body: Buffer.from(JSON.stringify(corpo)).toString('base64') });
}
async function laco() {
  while (true) {
    const i = eventos.findIndex((x) => x.method === 'Fetch.requestPaused');
    if (i >= 0) { const [e] = eventos.splice(i, 1); tratarFetch(e.params); continue; }
    const j = eventos.findIndex((x) => x.method === 'Runtime.exceptionThrown' || (x.method === 'Runtime.consoleAPICalled' && x.params.type === 'error') || (x.method === 'Log.entryAdded' && x.params.entry.level === 'error'));
    if (j >= 0) { const [e] = eventos.splice(j, 1); erros.push({ rota: rotaAtual, msg: JSON.stringify(e.params).slice(0, 300) }); continue; }
    await dormir(20);
  }
}
let rotaAtual = ''; laco();

async function foto(nome) {
  const r = await cdp('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(SAIDA, `${nome}.png`), Buffer.from(r.result.data, 'base64'));
}
const rotas = (process.env.ROTAS ?? '/patrimonio,/notificacoes,/tarefas,/contratos/minhas-pendencias,/contratos/painel,/patrimonio/parametros').split(',');
const reduzido = process.env.REDUZIDO === '1';
if (reduzido) await cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
for (const rota of rotas) {
  rotaAtual = rota;
  await cdp('Page.navigate', { url: `http://localhost:4311${rota}` });
  await dormir(1100);
  await foto(`${rota.replace(/\W+/g, '_')}${reduzido ? '_reduzido' : ''}_1_carregando`);
  await dormir(ATRASO_API + 1500);
  await foto(`${rota.replace(/\W+/g, '_')}${reduzido ? '_reduzido' : ''}_2_depois`);
}
const avaliar = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const relatorio = {};
const clicar = async (expr) => {
  const caixa = await avaliar("(() => { const e = (" + expr + "); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()");
  if (!caixa) return false;
  await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: caixa.x, y: caixa.y });
  await cdp('Input.dispatchMouseEvent', { type: 'mousePressed', x: caixa.x, y: caixa.y, button: 'left', clickCount: 1 });
  await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', x: caixa.x, y: caixa.y, button: 'left', clickCount: 1 });
  return true;
};
// Espera um seletor aparecer e devolve o estilo de animação logo que ele surge
const surgiu = async (seletor, ms = 6000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const r = await avaliar("(() => { const m = document.querySelector('" + seletor + "'); return m ? getComputedStyle(m).animationName + ' ' + getComputedStyle(m).animationDuration : null; })()");
    if (r) return r;
    await dormir(15);
  }
  return 'não apareceu';
};
if (process.env.CENARIO === 'modal') {
  rotaAtual = '/notificacoes (modal)';
  await cdp('Page.navigate', { url: 'http://localhost:4311/notificacoes' });
  await dormir(1000);
  relatorio.esqueleto_brilho = await avaliar("(() => { const e = document.querySelector('.esq'); return e ? getComputedStyle(e, '::after').animationName + ' / ' + getComputedStyle(e, '::after').display : 'sem esqueleto'; })()");
  await dormir(ATRASO_API + 1200);
  relatorio.clicou_nova = await clicar("[...document.querySelectorAll('button')].find(b => /Nova notificação/.test(b.textContent))");
  relatorio.modal_entrada = await surgiu('.modal-portal', 8000);
  relatorio.fundo_entrada = await avaliar("(() => { const m = document.querySelector('.fundo-modal'); return m ? getComputedStyle(m).animationName : 'sem fundo'; })()");
  await foto('modal_aberto_inicio');
  await dormir(600);
  await foto('modal_aberto');
  await dormir(ATRASO_API + 800);
  // Registra, com horário, o que acontece com o modal ao fechar (classe de saída e remoção do DOM)
  await avaliar("(() => { window.__log = []; const m = document.querySelector('.modal-portal'); const t0 = performance.now(); const reg = (e) => window.__log.push([Math.round(performance.now() - t0), e]); reg('antes'); new MutationObserver((ms) => ms.forEach((x) => { if (x.type === 'attributes') reg('classe: ' + m.className); if (x.type === 'childList' && [...x.removedNodes].includes(m)) reg('removido'); })).observe(m, { attributes: true, attributeFilter: ['class'] }); new MutationObserver((ms) => ms.forEach((x) => { if ([...x.removedNodes].includes(m)) reg('removido do DOM'); })).observe(m.parentNode, { childList: true }); })()");
  relatorio.clicou_cancelar = await avaliar("(() => { const b = [...document.querySelectorAll('.modal-portal button')].find(b => /Cancelar/.test(b.textContent)); b?.click(); return !!b; })()");
  await dormir(600);
  relatorio.linha_do_tempo_saida_modal = await avaliar("window.__log");
  relatorio.modal_removido = await avaliar("document.querySelector('.modal-portal') === null");
  relatorio.clicou_menu = await clicar("document.querySelector('.menu-usuario-gatilho')");
  relatorio.menu_entrada = await surgiu('.menu-usuario-lista', 2000);
  await foto('menu_usuario');
}
console.log(JSON.stringify(relatorio, null, 2));
await dormir(300);
writeFileSync(join(SAIDA, 'erros.json'), JSON.stringify(erros, null, 2));
console.log('erros de console/exceções:', erros.length);
ws.close(); chrome.kill(); servidor.close(); process.exit(0);
