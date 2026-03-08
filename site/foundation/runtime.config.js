(function () {
  var host = window.location.hostname;
  var isLocal = host === "127.0.0.1" || host === "localhost";

  window.__OPHTXN_RUNTIME = {
    siteUrl: isLocal ? "http://127.0.0.1:8787" : "https://ophtxn.com",
    apiBase: isLocal ? "http://127.0.0.1:8000" : "https://api.permanencesystems.com",
    appBase: isLocal ? "http://127.0.0.1:8797" : "https://app.permanencesystems.com",
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
