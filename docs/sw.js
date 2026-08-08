/* Cache-first app shell so the dashboard works offline once loaded.
   Data JSON is network-first with cache fallback. */
const SHELL = "gse-shell-v1";
const ASSETS = ["./", "index.html", "style.css", "app.js",
  "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith(".json")) {
    // data: network first, fall back to last cached copy
    e.respondWith(
      fetch(e.request).then((r) => {
        const copy = r.clone();
        caches.open(SHELL).then((c) => c.put(e.request, copy));
        return r;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
  }
});
