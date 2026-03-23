/* ============================================================
   FONTESIN Service Worker – Offline-first PWA
   Version: 1.0.0
   ============================================================ */

const CACHE_NAME = 'fontesin-v1';
const STATIC_CACHE = 'fontesin-static-v1';
const DYNAMIC_CACHE = 'fontesin-dynamic-v1';

// Core files to pre-cache (app shell)
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/dashboard.html',
  '/companies.html',
  '/company-detail.html',
  '/messages.html',
  '/login.html',
  '/register.html',
  '/css/style.css',
  '/css/app.css',
  '/css/responsive.css',
  '/js/app.js',
  '/js/main.js',
  '/images/logo_full.png',
  '/images/logo_white.png',
  '/images/icons/icon-192.png',
  '/images/icons/icon-512.png',
];

// ── Install: pre-cache app shell ──────────────────────────────
self.addEventListener('install', function(event) {
  console.log('[SW] Installing…');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(function(cache) {
        console.log('[SW] Pre-caching app shell');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(function() {
        return self.skipWaiting();
      })
      .catch(function(err) {
        console.warn('[SW] Pre-cache failed (some files may not exist yet):', err);
        return self.skipWaiting();
      })
  );
});

// ── Activate: clean old caches ────────────────────────────────
self.addEventListener('activate', function(event) {
  console.log('[SW] Activating…');
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames
          .filter(function(name) {
            return name !== STATIC_CACHE && name !== DYNAMIC_CACHE;
          })
          .map(function(name) {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ── Fetch: stale-while-revalidate strategy ────────────────────
self.addEventListener('fetch', function(event) {
  const url = new URL(event.request.url);

  // Skip non-GET requests and external requests
  if (event.request.method !== 'GET') return;
  if (!url.origin.includes(self.location.origin) &&
      !url.hostname.includes('fonts.googleapis.com') &&
      !url.hostname.includes('fonts.gstatic.com')) return;

  // For HTML pages: network-first (fresh content when online)
  if (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then(function(response) {
          const clone = response.clone();
          caches.open(DYNAMIC_CACHE).then(function(cache) {
            cache.put(event.request, clone);
          });
          return response;
        })
        .catch(function() {
          return caches.match(event.request)
            .then(function(cached) {
              return cached || caches.match('/index.html');
            });
        })
    );
    return;
  }

  // For static assets: cache-first
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) return cached;
      return fetch(event.request).then(function(response) {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(DYNAMIC_CACHE).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(function() {
        // Return a fallback for images
        if (event.request.destination === 'image') {
          return new Response(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="#f0f5f8"/><text x="50" y="55" text-anchor="middle" fill="#5F8FAA" font-size="12">FONTESIN</text></svg>',
            { headers: { 'Content-Type': 'image/svg+xml' } }
          );
        }
      });
    })
  );
});

// ── Background sync (for offline form submissions) ────────────
self.addEventListener('sync', function(event) {
  if (event.tag === 'sync-messages') {
    console.log('[SW] Background sync: messages');
  }
});

// ── Push notifications ────────────────────────────────────────
self.addEventListener('push', function(event) {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'FONTESIN';
  const options = {
    body: data.body || 'You have a new notification',
    icon: '/images/icons/icon-192.png',
    badge: '/images/icons/icon-72.png',
    vibrate: [100, 50, 100],
    data: { url: data.url || '/dashboard.html' },
    actions: [
      { action: 'open', title: 'Open' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.action === 'dismiss') return;
  const url = event.notification.data.url || '/dashboard.html';
  event.waitUntil(clients.openWindow(url));
});
