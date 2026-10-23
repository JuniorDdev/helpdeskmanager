const CACHE_NAME = 'helpdesk-manager-shell-v2';
const APP_SHELL = [
  '/offline.html',
  '/manifest.webmanifest',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icons/helpdesk-icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(
      names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin) return;

  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline.html')));
    return;
  }

  if (requestUrl.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(event.request).then((response) => {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)));
        return response;
      }).catch(() => caches.match(event.request))
    );
  }
});
