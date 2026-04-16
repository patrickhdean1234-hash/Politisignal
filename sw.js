/**
 * PolitiSignal Service Worker
 * - Background push notifications (when tab is closed)
 * - Offline cache for instant load
 * - Signal polling every 5 minutes when installed
 */

const CACHE = 'politisignal-v2';
const PRECACHE = ['/', '/app.html', '/stocks.html', '/subscribe.html', '/data/signals.json', '/data/prices.json'];

// ── Install: cache shell assets ──────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE).catch(() => {}))
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ───────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first for API, cache-first for assets ────────────────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Always network-first for dynamic data
  if (url.pathname.startsWith('/data/') || url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).then(r => {
        if (r.ok) {
          const clone = r.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return r;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  // Cache-first for HTML/CSS/fonts
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});

// ── Push: show notification when server pushes ───────────────────────────────
self.addEventListener('push', e => {
  let data = { title: 'PolitiSignal Alert', body: 'New political signal detected.', severity: 'high', url: '/app.html' };
  try { if (e.data) data = { ...data, ...e.data.json() }; } catch {}

  const iconMap = { critical: '🚨', high: '⚠️', medium: '📡', low: 'ℹ️' };
  const icon = iconMap[data.severity] || '📡';
  const badgeColor = { critical: '#ff4757', high: '#f1c40f', medium: '#4f7dff', low: '#4a4d62' };

  e.waitUntil(
    self.registration.showNotification(`${icon} ${data.title}`, {
      body: data.body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: data.id || 'politisignal',
      data: { url: data.url || '/app.html' },
      vibrate: data.severity === 'critical' ? [200, 100, 200] : [100],
      requireInteraction: data.severity === 'critical',
    })
  );
});

// ── Notification click: open dashboard ──────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = e.notification.data?.url || '/app.html';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(wins => {
      const match = wins.find(w => w.url.includes('/app.html'));
      if (match) return match.focus();
      return clients.openWindow(target);
    })
  );
});

// ── Background sync: poll for new signals ───────────────────────────────────
self.addEventListener('periodicsync', e => {
  if (e.tag === 'poll-signals') {
    e.waitUntil(checkForNewSignals());
  }
});

async function checkForNewSignals() {
  try {
    const [sigRes, storedStr] = await Promise.all([
      fetch('/data/signals.json?sw=' + Date.now()),
      caches.match('/data/signals.json'),
    ]);
    if (!sigRes.ok) return;
    const fresh = await sigRes.json();

    let prev = [];
    if (storedStr) {
      try { prev = await storedStr.json(); } catch {}
    }

    const prevIds = new Set(prev.map(s => s.id));
    const newOnes = fresh.filter(s => !prevIds.has(s.id) && (s.severity === 'critical' || s.severity === 'high'));

    for (const s of newOnes.slice(0, 3)) {
      await self.registration.showNotification(`🚨 ${s.politician}`, {
        body: s.content.slice(0, 100),
        tag: s.id,
        data: { url: '/app.html' },
        requireInteraction: s.severity === 'critical',
      });
    }
  } catch {}
}
