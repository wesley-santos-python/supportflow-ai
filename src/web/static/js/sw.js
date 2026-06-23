/*
 * SupportFlow AI — Service Worker (PWA).
 *
 * Objetivo mínimo e seguro: tornar o app "instalável" (janela própria no
 * Mac/Windows) e acelerar o carregamento dos arquivos estáticos via cache.
 * NÃO interceptamos páginas, /api nem POSTs — esses sempre vão à rede para
 * não correr o risco de servir conteúdo desatualizado ou quebrar formulários.
 */
const CACHE = "sfa-static-v1";
const ASSETS = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/favicon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
      .catch(() => {}),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Só os estáticos passam pelo cache (stale-while-revalidate). Tudo o mais
  // (páginas, /api) segue o caminho normal da rede, sem interceptação.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(req).then((cached) => {
          const network = fetch(req)
            .then((res) => {
              if (res && res.status === 200) cache.put(req, res.clone());
              return res;
            })
            .catch(() => cached);
          return cached || network;
        }),
      ),
    );
  }
});
