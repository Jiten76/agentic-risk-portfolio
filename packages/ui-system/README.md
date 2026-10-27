# portfolio-core

The shared, genuinely-reusable layer across the cybersecurity-risk portfolio
(`risk-as-code-agent`, `agent-trace-gov`, `hypervelocity-risk-sim`). Extracted —
not copy-pasted — per the agent-trace-gov v2 port spec §14.D / §15.D–F, so the
portfolio's "reusable foundation" claim is TRUE rather than asserted.

Consuming projects import `portfolio_core` via a 3-line sys.path bootstrap
(portfolio-core sits beside each project under `/…/code/`); no pip install.

## Extraction status (port spec §15.E order)
- [x] `action_log` + `provenance`  — Stage 0 step 1 (hash-chained log, quad/quint-state provenance)
- [ ] `presentation` (render-from-data shell + CSS/JS)  — step 2
- [ ] `audit harness` (parameterized)  — step 3

`make_projection` stays per-domain in each project — it is irreducibly
domain-coupled and is NOT shared.
