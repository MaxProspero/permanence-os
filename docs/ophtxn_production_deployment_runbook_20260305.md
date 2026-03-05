# Ophtxn Production Deployment Runbook

Date: 2026-03-05 (UTC)
Goal: launch official domain + hosting + analytics + lead capture with no-spend-first defaults.

## Deployment Model

1. Static site hosting: Cloudflare Pages (free tier path).
2. Lead capture + analytics events: first-party API endpoints already in `dashboard_api.py`:
   - `POST /api/revenue/intake`
   - `POST /api/revenue/site-event`
3. Runtime config controls domain/API routing from `site/foundation/runtime.config.js`.
4. Spend remains off by default; launch spend later by updating budget fields in `memory/working/ophtxn_production_config.json`.

## Commands

1. Initialize production config:
   - `python cli.py ophtxn-production --action init`
2. Configure domain/runtime and lock no-spend budget:
   - `python cli.py ophtxn-production --action configure --domain ophtxn.<company-domain> --api-domain api.<company-domain> --site-url https://ophtxn.<company-domain> --api-base https://api.<company-domain> --no-spend`
3. Run deploy preflight (toolchain + Cloudflare auth):
   - `python cli.py ophtxn-production --action preflight --check-wrangler`
4. Render runtime config:
   - `python cli.py ophtxn-production --action render-runtime`
5. Check readiness (plus API and wrangler probes):
   - `python cli.py ophtxn-production --action status --check-api --check-wrangler`
6. Enforce strict gate:
   - `python cli.py ophtxn-production --action status --strict --min-score 80`
7. Calculate costs:
   - `python cli.py ophtxn-production --action estimate`
8. Generate deploy sequence:
   - `python cli.py ophtxn-production --action deploy-plan`

## Telegram Shortcuts

- `/prod-status [min-score=<n>] [strict]`
- `/prod-preflight [strict]`
- `/prod-estimate`
- `/prod-plan`
- `/prod-runtime`
- `/prod-config domain=ophtxn.permanencesystems.com api-domain=api.permanencesystems.com site-url=https://ophtxn.permanencesystems.com api-base=https://api.permanencesystems.com no-spend`

## Recommended Domain Split (Company vs Product)

Use your company root for trust, then isolate product/app/api as subdomains:
- Company/site root: `permanencesystems.com`
- Ophtxn product site: `ophtxn.permanencesystems.com`
- App surface (later): `app.permanencesystems.com`
- API surface: `api.permanencesystems.com`

Current configured production target in this repo:
- Primary domain: `ophtxn.permanencesystems.com`
- API domain: `api.permanencesystems.com`

## No-Spend Defaults

- Keep monthly costs at `0` in config budget fields.
- Keep model provider on `ollama` with no-spend mode enabled.
- Use first-party event capture (`/api/revenue/site-event`) instead of paid third-party analytics.
- Keep lead capture on first-party endpoint (`/api/revenue/intake`) with mail fallback.

## Launch Spend Transition

When ready to enable spend:
1. Set real domain annual cost in config (`domain.annual_cost_usd`).
2. Add expected monthly hosting/monitoring/analytics values in `budget`.
3. Re-run `ophtxn-production --action estimate`.
4. Approve the monthly cap before switching any paid services.

## External References (verified 2026-03-05 UTC)

- Cloudflare Developer Platform plans: <https://www.cloudflare.com/plans/developer-platform/>
- Cloudflare Web Analytics docs: <https://www.cloudflare.com/web-analytics/>
- Cloudflare Pages deployment with Wrangler: <https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/>
- Cloudflare custom domains for Pages: <https://developers.cloudflare.com/pages/configuration/custom-domains/>
- Cloudflare Registrar product info: <https://www.cloudflare.com/products/registrar/>
