<<<<<<< HEAD
var CACHE_NAME = "ophtxn-v1";
=======
var CACHE_NAME = "ophtxn-v7";
>>>>>>> origin/main
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
<<<<<<< HEAD
=======
  "/trading_room.html",
  "/daily_planner.html",
>>>>>>> origin/main
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
<<<<<<< HEAD
  // Cache-first for static assets
  event.respondWith(
    caches.match(event.request).then(function (cached) {
      if (cached) return cached;
      return fetch(event.request).then(function (response) {
        if (response.ok && event.request.method === "GET") {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
=======
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
>>>>>>> origin/main
    })
  );
});
