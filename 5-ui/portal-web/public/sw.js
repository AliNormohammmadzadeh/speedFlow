// SpeedFlow portal service worker (task 5.5) — offline app-shell caching.
const CACHE = 'speedflow-portal-v1'
const APP_SHELL = ['/', '/index.html', '/icon.svg', '/manifest.webmanifest']

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', event => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)

  // Never cache live API data — always go to network, fail soft.
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request).catch(() => new Response('{"offline":true}', { headers: { 'Content-Type': 'application/json' } })))
    return
  }

  // Cache-first for the static app shell + assets; fall back to cached index for navigations.
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached
      return fetch(request)
        .then(resp => {
          const copy = resp.clone()
          caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => {})
          return resp
        })
        .catch(() => (request.mode === 'navigate' ? caches.match('/index.html') : undefined))
    }),
  )
})
