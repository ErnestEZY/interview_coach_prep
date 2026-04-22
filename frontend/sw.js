const CACHE_NAME = 'icp-cache-v3';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/styles.css',
  '/static/js/app.js',
  '/static/images/favicon-32x32.png',
  '/static/pages/dashboard.html',
  '/static/pages/resume_builder.html',
  '/static/pages/find-jobs.html',
  '/static/pages/history.html',
  '/static/pages/interview.html'
];

// Use Cache-First for these external libraries
const CDN_URLS = [
  'cdn.jsdelivr.net',
  'unpkg.com',
  'cdnjs.cloudflare.com',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'static.careerjet.org'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching core assets');
      // Use cache.addAll but catch individual failures if needed
      return cache.addAll(ASSETS_TO_CACHE).catch(err => {
        console.error('[SW] Pre-cache failed:', err);
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => {
          console.log('[SW] Deleting old cache:', key);
          return caches.delete(key);
        })
      );
    })
  );
  return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Only handle GET requests with http/https schemes
  if (event.request.method !== 'GET' || !url.protocol.startsWith('http')) return;

  // Strategy for CDN assets: Cache-First
  const isCDN = CDN_URLS.some(domain => url.hostname.includes(domain));
  
  if (isCDN) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;

        return fetch(event.request).then((response) => {
          // Cache opaque responses (for cross-origin scripts) or valid CORS responses
          if (response && (response.status === 200 || response.type === 'opaque')) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => {
          // If fetch fails and no cache, we must return something
          return new Response('Network error occurred', { status: 408, statusText: 'Network Error' });
        });
      })
    );
    return;
  }

  // Strategy for local assets: Stale-While-Revalidate
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return networkResponse;
      }).catch((err) => {
        console.log('[SW] Fetch failed:', err);
        return cached || new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
      });

      return cached || fetchPromise;
    })
  );
});