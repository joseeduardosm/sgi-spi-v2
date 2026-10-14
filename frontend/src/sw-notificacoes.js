// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar os pop-ups das notificações do navegador (Web Push) e tratar os botões "Abrir" e "Ciente".
/*
 * Service worker das Notificações (escopo `/`). Fica na raiz do site e convive com o `ngsw-worker.js` do Patrimônio (escopo `/patrimonio/`).
 *
 * O servidor envia um JSON: { titulo, texto (até 200 caracteres), url, tag (id da entrega), entrega_id, token_ciencia }.
 * - push: mostra o pop-up com as ações "Abrir" e "Ciente" (uma notificação por entrega: a `tag` evita repetir).
 * - "Ciente": como este arquivo não tem a sessão do usuário, chama `POST /api/notificacoes/ciencia-por-token` com o token curto do
 *   payload (vale só para aquela entrega, por 7 dias).
 * - clique no pop-up ou em "Abrir": foca uma aba do SGI já aberta e leva ao endereço; sem aba aberta, abre uma nova.
 */

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (evento) => evento.waitUntil(self.clients.claim()));

self.addEventListener('push', (evento) => {
  let dados = {};
  try {
    dados = evento.data ? evento.data.json() : {};
  } catch {
    dados = { titulo: 'SGI SPI', texto: evento.data ? evento.data.text() : '' };
  }
  const opcoes = {
    body: dados.texto || '',
    tag: dados.tag || undefined,
    icon: '/assets/imagens/icone-192.png',
    badge: '/assets/imagens/icone-192.png',
    data: dados,
    actions: [{ action: 'abrir', title: 'Abrir' }, ...(dados.token_ciencia ? [{ action: 'ciente', title: 'Ciente' }] : [])],
  };
  evento.waitUntil(self.registration.showNotification(dados.titulo || 'SGI SPI', opcoes));
});

async function abrirNoSistema(caminho) {
  const destino = new URL(caminho || '/notificacoes', self.location.origin).href;
  const janelas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const mesma = janelas.find((j) => new URL(j.url).origin === self.location.origin);
  if (mesma) {
    await mesma.focus();
    if ('navigate' in mesma) await mesma.navigate(destino).catch(() => undefined);
    return;
  }
  await self.clients.openWindow(destino);
}

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close();
  const dados = evento.notification.data || {};
  if (evento.action === 'ciente' && dados.token_ciencia) {
    evento.waitUntil(
      fetch('/api/notificacoes/ciencia-por-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: dados.token_ciencia }),
      }).catch(() => undefined),
    );
    return;
  }
  evento.waitUntil(abrirNoSistema(dados.url));
});
