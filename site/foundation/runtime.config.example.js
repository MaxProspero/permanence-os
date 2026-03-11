(function () {
  var host = window.location.hostname;
  var isLocal = host === "127.0.0.1" || host === "localhost";

  window.__OPHTXN_RUNTIME = {
    // Public site URL — Cloudflare Pages domain.
    siteUrl: isLocal ? "http://127.0.0.1:8787" : "https://ophtxn.com",

    // Dashboard API base — Cloudflare Tunnel to local Command Center.
    apiBase: isLocal ? "http://127.0.0.1:8000" : "https://api.permanencesystems.com",

    // Foundation API / Ophtxn Shell — Cloudflare Tunnel to local app surface.
    appBase: isLocal ? "http://127.0.0.1:8797" : "https://app.permanencesystems.com",

    // Convenience aliases for inter-page links.
    commandCenterUrl: isLocal ? "http://127.0.0.1:8000" : "https://api.permanencesystems.com",
    shellUrl: isLocal ? "http://127.0.0.1:8797/app/ophtxn" : "https://app.permanencesystems.com/app/ophtxn",

    source: "foundation_site",
    analyticsEnabled: true,
    trackPageViews: true,
    trackCtas: true,
    leadCaptureEnabled: true,
    leadCaptureEndpoint: "/api/revenue/intake",
    siteEventEndpoint: "/api/revenue/site-event",
    fallbackEmail: "hello@ophtxn.com",
  };
})();
