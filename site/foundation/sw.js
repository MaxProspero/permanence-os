var CACHE_NAME = "ophtxn-v3";
var PRECACHE_URLS = [
  "/",
  "/index.html",
  "/rooms.html",
  "/local_hub.html",
  "/official_app.html",
  "/ophtxn_shell.html",
  "/command_center.html",
  "/ai_school.html",
  "/press_kit.html",
  "/runtime.config.js",
  "/manifest.json",
  "/assets/ophtxn_mark.svg",
  "/assets/icon-192.png",
  "/assets/icon-512.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (name) { return name !== CACHE_NAME; })
          .map(function (name) { return caches.delete(name); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  // Network-only for API calls
  if (url.pathname.startsWith("/api/")) return;
  // Network-first: try network, fall back to cache (offline support)
  event.respondWith(
    fetch(event.request).then(function (response) {
      if (response.ok && event.request.method === "GET") {
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(event.request, clone);
        });
      }
      return response;
    }).catch(function () {
      return caches.match(event.request);
    })
  );
});
