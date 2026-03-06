window.__OPHTXN_RUNTIME = {
  // Public site URL (domain) for production.
  siteUrl: "https://ophtxn.com",

  // API base for intake + event capture.
  // Keep local default for no-spend testing, or point to your deployed API host.
  apiBase: "https://api.ophtxn.com",

  source: "foundation_site",
  analyticsEnabled: true,
  trackPageViews: true,
  trackCtas: true,
  leadCaptureEnabled: true,
  leadCaptureEndpoint: "/api/revenue/intake",
  siteEventEndpoint: "/api/revenue/site-event",
  fallbackEmail: "hello@ophtxn.com",
};
