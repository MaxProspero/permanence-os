# Ophtxn Platform Intelligence (March 6, 2026)

Last updated: 2026-03-06 (US)

This brief captures verified external platform signals and how they affect Ophtxn decisions.

## Verified Platform Signals

1. **Perplexity launched "Perplexity Computer" in late February 2026.**
- Perplexity changelog entry dated **February 27, 2026** states Perplexity Computer launch and describes autonomous browser task execution plus connectors.
- Source: [Perplexity changelog](https://www.perplexity.ai/changelog/what-we-shipped---february-27-2026)

2. **Perplexity usage is still tiered and cost-bounded, not unlimited.**
- Perplexity pricing/help docs describe request quotas and differences between daily usage and max mode behavior.
- Source: [Perplexity pricing page](https://www.perplexity.ai/pricing)
- Source: [Perplexity Help Center pricing + usage](https://www.perplexity.ai/help-center/en/articles/10354919-what-is-perplexity-pro)

3. **OpenClaw continues rapid shipping cadence in 2026.**
- OpenClaw release feed shows frequent updates (for example releases through February/March 2026, including `v2026.3.2`).
- Source: [OpenClaw releases](https://github.com/moltbot/moltbot/releases)
- Source: [OpenClaw `v2026.3.2`](https://github.com/moltbot/moltbot/releases/tag/v2026.3.2)

4. **OpenClaw has native concepts for channels and skills.**
- Official docs include channel setup/governance and a skills model.
- Source: [OpenClaw docs - Channels](https://docs.openclaw.ai/guides/channels)
- Source: [OpenClaw docs - Skills](https://docs.openclaw.ai/guides/skills)

## Interpretation For Ophtxn

- **Inference:** Perplexity Computer is useful as a task specialist, but not the best canonical control plane for your product identity.
- **Inference:** OpenClaw is strong as an execution/runtime worker layer, especially for chat channels and repeatable skills.
- **Inference:** Ophtxn should remain the owner of memory, approvals, policy, and UX while federating external systems.

## Recommended Runtime Stack

1. **Control plane:** Ophtxn dashboards (`:8000`, `:8787`, `:8797`) and governance scripts.
2. **Execution plane:** OpenClaw + optional remote worker fleet.
3. **Research accelerator:** Perplexity Computer for bounded deep-research runs.
4. **Infrastructure:** Cloudflare domain + Pages + analytics layer.

## Product Rule

- Keep external agents as pluggable workers.
- Keep Ophtxn as the permanent identity and decision layer.

