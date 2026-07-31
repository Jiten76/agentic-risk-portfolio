# Design lock — risk-as-code-agent v1.3

> Locked 2026-05-21 after two iterations that thrashed on the wrong abstraction.
> This document is the source of truth for the dashboard rebuild. Do not re-litigate
> without an explicit version bump and a new lock decision.

---

## 0. Intent

A **risk operating system** that answers — for the role that's asking it — whether
posture is improving, whether a finding is isolated or systemic, whether something
upstream is causing it, and whether it's defensible against a regulator.

It is **not**: an audit report, a printable assessment, a Streamlit demo, or a
"slap-some-charts-on-it" GRC tool.

The deliverable is a **single self-contained HTML artifact** generated from the
LangGraph pipeline output. Print-clean. Shareable. Re-generatable from real
telemetry when integrated.

---

## 1. Persona model — role-tuned, not abstract layers

The IA mistake we already made: labelling views *strategic / tactical /
operational*. That's abstraction-talk; users don't think in layers, they think in
roles. We map to the 19-role taxonomy already established in EAP `Dashboard.js`.

| View label | Role archetypes (EAP) | The question the view answers |
|---|---|---|
| **Engineering** | VP Engineering · DevSecOps Engineer · Release Manager · SOC Expert · DevSecOps Manager | *"What do I fix today, and is something upstream causing this?"* |
| **Leadership** | CEO · CISO · CTO · CFO · VP Product · VP Infrastructure | *"Is posture improving? What's it costing? What do I disclose?"* |
| **Audit** *(deferred — phase 2)* | GRC Expert · Compliance Director · Legal Director · AI Governance Lead | *"Is the evidence defensible against a regulator? Where's the acceptance trail?"* |

Each view has a banner with `title` + `subtitle` describing what that role sees,
mirroring the EAP `dashboards` map pattern.

**Other 13 EAP roles** (SOC Lead, Product Manager, etc.) are out of scope for
v1.3. They become trivial additions in v1.4 — same data model, different view
filters.

---

## 2. Primitives — what the dashboard actually computes and surfaces

Thirteen primitives, ✓ = primary surface in that view, • = available on drill-in.

| # | Primitive | Engineering | Leadership | Audit (v2) |
|---|---|:---:|:---:|:---:|
| 1 | **Trajectory** — Q-over-Q delta, per-domain + per-pattern sparklines, worsening/stable/improving | • | ✓ | • |
| 2 | **Scope** — isolated (1 domain) / emergent (2–3) / systemic (4+) | ✓ | ✓ | ✓ |
| 3 | **Cascade** — upstream / downstream pattern dependencies, encoded as cited rules in JSON | ✓ | • | ✓ |
| 4 | **Correlation** — pattern pairs that co-fire across history >50% of the time | ✓ | • | ✓ |
| 5 | **Skew** — which domain or signal is pulling the portfolio average | ✓ | ✓ | • |
| 6 | **Forecast** — next-period projection based on trajectory + cascade | • | ✓ | • |
| 7 | **Accountability** — NIST function → owner role mapping, escalation path | ✓ | ✓ | ✓ |
| 8 | **Materiality** — SEC 8-K threshold, GDPR Art. 33 72-hour trigger, OCC 12 CFR 30 disclosure flag | • | ✓ | ✓ |
| 9 | **Time-in-state** — duration of breach (1 day vs 90 days is different work) | ✓ | ✓ | ✓ |
| 10 | **Treatment plan** — ISO 31000 four-corner: accept / mitigate / transfer / avoid + current status | ✓ | • | ✓ |
| 11 | **Compensating controls** — what else is in place when primary control is RED | ✓ | • | ✓ |
| 12 | **Financial exposure** — $ estimate cited to comparable past incidents | • | ✓ | • |
| 13 | **Risk acceptance audit trail** — who accepted residual risk, when, with what justification, expiry | • | ✓ | ✓ |

---

## 3. Data model additions to support the primitives

### 3.1 In `data/risk_patterns.json` (per-pattern)

```json
{
  "id": "RP-11",
  ...
  "cascade_to": [
    {"pattern_id": "RP-02", "strength": "high", "rationale": "Capacity exhaustion → availability breach (Cloudflare 2019, GitHub 2018-10-21)"},
    {"pattern_id": "RP-12", "strength": "medium", "rationale": "Sustained capacity issues → repeat-incident-rate increase"}
  ],
  "cascade_from": [
    {"pattern_id": "RP-09", "strength": "medium", "rationale": "Emergency changes elevate capacity volatility"}
  ],
  "materiality_trigger": {
    "sec_8k": false,
    "gdpr_art33": false,
    "occ_12cfr30": true,
    "note": "OCC heightened standards require capacity event reporting for systemically important institutions"
  }
}
```

### 3.2 In synthesized history (new — `data/history_synthesizer.py`)

Generates N quarter-snapshots from the same pipeline at varying intensities:

```
outputs/history/2025-Q3_snapshot.json
outputs/history/2025-Q4_snapshot.json
outputs/history/2026-Q1_snapshot.json
outputs/history/2026-Q2_snapshot.json  ← current
```

**Honesty discipline:** UI banner says *"Historical snapshots synthesised for
demo. Connect telemetry stream for real history."* No pretending these are real.

### 3.3 In per-finding metadata (new — `data/finding_metadata.py`)

Mocked but defensible — each finding gets:

- `time_in_state_days`: int (derived from history snapshots)
- `treatment_plan`: `"mitigate"` | `"accept"` | `"transfer"` | `"avoid"`
- `treatment_status`: `"planned"` | `"in_progress"` | `"blocked"` | `"closed"` | `"accepted"`
- `treatment_eta`: ISO date
- `compensating_controls`: `[{name, framework, effectiveness: "high|medium|low"}]`
- `financial_exposure_usd`: int (cited to comparable incident)
- `financial_exposure_basis`: string (e.g., "Knight Capital 2012 — $440M / 45 min")
- `acceptance_trail`: `[{accepted_by, accepted_at, justification, expires_at, signoff_role}]`

These are illustrative defaults. UI marks the section *"illustrative — connect
your IRM for live values."*

---

## 4. Visual language — locked from v1.2, do not re-litigate

- **Tokens** in `templates/report_styles.css` — type scale (1.18 ratio), spacing
  (4px base), single warm-gold accent (`#c9a86a`), RAG (`#e85c5c / #e8a04a /
  #5fb87a`), glass surfaces (`backdrop-filter: blur(20px)`), warm off-white text
  on deep navy (`#0a0d14`).
- **Lists are rows**, not cards. Cards are for at-a-glance summary panels (e.g.,
  domain heatmap, top fixes), not for itemised content.
- **Click row to expand inline.** Never a separate page.
- **Filter chips** for severity / domain / treatment-status / scope.
- **Sparklines** are unicode block characters (`▁▂▃▄▅▆▇█`) or inline SVG —
  not Chart.js, not D3. Self-contained file is non-negotiable.
- **No emoji decoration** anywhere. Status uses RAG tags, not icons.
- **Brand mark** — monospace `risk-as-code-agent / v1.X` lockup with gold slash.
- **Print-clean** — expanded rows stay expanded, tab nav hidden, semantic-only
  color.

---

## 5. Build sequence

1. **v1.3a — Engineering view** ✅ shipped in v1.3.1.
2. **v1.3b — Leadership view** ✅ shipped in v1.3.1.
3. **v1.3.1 — council-driven fixes** (added post-lock, 2026-05-27 — see §10).
4. **v1.4 — Audit view + Financial Impact tab.** Adds the full evidence chain +
   Article-level regulatory citations + dedicated Financial Impact view with
   three methodologies side-by-side, estimated-vs-actual differentiation, and
   materiality bridge. **Sub-tabs per role explicitly deferred** to v1.5+ —
   the locked decision is to learn from use, not to pre-build.
5. **v1.5 — Port to agent-trace-gov + hypervelocity-risk-sim.** Same design
   tokens, different content shapes.
6. **v2.0 — Yukti V1.x dashboard rework.** Same design tokens, but interactive
   (live data, not artefact). Out of scope for the portfolio-week window.

---

## 6. Definition of done — review-driven, not predeclared

We **do not predeclare** what done looks like. After each `v1.3x` build:

1. Generate the artefact from real pipeline data.
2. Open it in the browser.
3. Apply the **10-second persona test**: can the role this view targets find the
   answer to its question within 10 seconds of scrolling?
4. If yes for both Engineering and Leadership, lock the build and move to v1.4.
   If no, iterate the failing view only — do not re-litigate the spec.

The user reserves veto on whether each iteration passes. This is the only place
in the process where iteration is allowed.

---

## 7. Out of scope (explicitly do NOT build now)

- Real Prometheus / OTel integration (stays mock; integration spec is in README).
- Real LLM trajectory analysis (mock narratives only; Anthropic mode supported
  but not required).
- ML forecasting models (forecast = simple linear extrapolation cited as
  illustrative).
- Multi-tenancy / auth (single-org artefact).
- Threshold change / approval workflow (cited in JSON; no edit UI).
- Trend forecasting beyond next-period projection.
- Cross-org peer benchmarking.
- Mobile-optimised interactions beyond basic responsive layout.

---

## 8. Honesty discipline

These rules apply to every iteration:

- API errors never leak into user-facing narrative (fixed in v1.2; do not
  regress).
- Synthesized history is labelled as such in the UI.
- Mock financial exposure cites a real incident as basis.
- Compensating-control effectiveness is mocked but defensible (no
  `effectiveness: 100%`).
- All thresholds carry `threshold_source` + `threshold_source_url` (v1.1
  invariant).
- All findings carry `incident_reference[]` with at least one cited public
  postmortem / regulator action / CVE record (v1.1 invariant).

---

## 9. Versioning

- v1.0 — initial release (May 2026)
- v1.1 — grounding pass: threshold sources + incident references for all 13 patterns
- v1.2 — voice pass, UI rebuild, LLM wiring, deprecation sweep
- v1.3 — dashboard IA + 13 primitives + Engineering + Leadership views (✅ shipped)
- v1.3.1 — council-driven fixes (✅ shipped 2026-05-27)
- **v1.4 — Audit view + Financial Impact tab + 16 role sub-tabs** — *RETRACTED* (built filters, not apps; see external review at `reviews/v2_0_external_review.md`).
- **v2.0a — Foundation + AI Governance Lead deep build** — (locked spec at `reviews/v2_0a_spec.md`, build in progress).
- v2.0 — Remaining 5–6 role apps (CISO posture / GRC register-mechanics / Compliance framework-coverage / Legal qualitative-materiality / practitioner queues / team-lead+ops-owner apps), built on the v2.0a foundation.
- v2.5 — design-system port to sibling repos (agent-trace-gov, hypervelocity-risk-sim).
- v3.0 — Yukti V1.x dashboard rework (live data, separate effort; inherits v2.0a foundation).

---

## 10. v1.4 scope amendment (proposed 2026-05-27, awaiting user lock)

Added after the council review of v1.3 surfaced two structural concerns that v1.3.1 partially addressed but did not fully resolve:

### 10.1 Audit view (carried forward from §5)

3-persona spec from §1 closes when Audit view ships. Adds:
- Full per-finding evidence chain: `first_detected` (✅ v1.3.1) + threshold-history surface (v1.4) + reconstructible state at moment-of-detection
- Article-level regulatory citations: GDPR Art. 33(1), 12 CFR 30 App. D § II / III, EU AI Act Art. 9 / 17 / 26 / 73, SOC 2 TSC control IDs (CC6.1, CC6.6, CC9.2, P3.1, P6.1)
- Framework-by-framework rollup: findings by framework, with control-ID-level mapping
- Acceptance-trail integrity view (named signers + countersigner + dissent capture — v1.3.1 already provides the underlying data)

### 10.2 Financial Impact tab (new — from session feedback 2026-05-27)

The current single $ figure on the Leadership view conflates:
- Forward-looking modelled exposure (what comparable incidents cost)
- Backward-looking incurred losses (what actually happened this period)
- One methodology presented as fact (when real teams use multiple)

The Financial Impact tab separates these explicitly:

| Sub-section | Content |
|---|---|
| Methodology selector (3) | (1) Comparable-incident (current) — basis: Knight Capital, Equifax, etc. · (2) Insurance/actuarial — IBM Cost of Data Breach + AON/Marsh ranges · (3) Bottom-up engineering — service-revenue × downtime × probability |
| Estimated forward exposure | Per-domain breakdown with methodology variance shown side-by-side. Confidence intervals where available. |
| Actual incurred losses YTD | SLA credits paid · regulatory fines · incident response costs · reconciliation with model predictions |
| Materiality bridge | Disclosure thresholds per regulator (SEC 8-K, OCC, FRB) · currently armed: which domains exceed which threshold |
| Assumptions & disputed values | Methodology notes (defaults vs site-specific) · pending review items (where leadership hasn't ratified the number) |

**Locked decision:** Financial Impact gets its own tab because (a) it's contentious, (b) it has multiple defensible methodologies, (c) it's the single biggest source of pushback from financially-literate stakeholders, and (d) it removes pressure from the Leadership view to summarise a number that is actually three different numbers.

### 10.3 Sub-tabs per role — explicitly deferred

Adding role-level sub-tabs (CEO / CISO / CFO / CTO under Leadership; VP-Eng / Release Manager / DevSecOps / SOC Expert under Engineering) is **explicitly out of v1.4 scope**.

Reasoning:
- Real content variance per role is modest — most differences are filter preferences + emphasis, not new data.
- Pre-building 6–10 sub-tabs before learning from use is gold-plating.
- Revisit after v1.5 port lands and we have the design language in use across all 3 projects.

This decision can be revisited only with another DESIGN.md amendment and changelog entry.

### 10.4 Definition-of-done for v1.4

- Audit view passes a re-run of the council against the `audit-regulator` persona — target verdict: examination outcome moves from MRA → observation or no-finding.
- Financial Impact tab passes the `ciso` persona — target verdict: "would take to board" (and add a `cfo` persona before re-running if there's bandwidth).
- Engineering view + Leadership view remain unchanged in v1.4 except where v1.4 additions naturally refine them (e.g., Leadership view's exposure section becomes a pointer to the new Financial Impact tab).

### 10.5 Effort budget for v1.4

8–12 hours total:
- Audit view: ~4h
- Financial Impact tab: ~4–6h
- Article-level citation refinements: ~1–2h

### 10.6 Discipline gates inherited from STATUS.md

- Every new feature proposal must pass the *would-this-also-benefit-Yukti?* test.
- Every iteration past v1.4 defers v1.5 port, which defers Yukti V2.0. The discipline rule: ship v1.4 → ship v1.5 → then decide whether to continue refining the trio or start Yukti.

---

*Locked. Future agents: edit this file only with explicit version bump and a one-line changelog at the bottom. Do not unwind decisions in §1–§4 mid-iteration.*

## 11. v2.0 amendment — RETRACT v1.4, lock v2.0a (2026-05-27)

v1.4's "16 role sub-tabs" approach is **retracted**. An external review (`reviews/v2_0_external_review.md`) demonstrated that the approach built filters, not apps — four governance roles (CISO, GRC, Compliance, Legal) rendered byte-identical because the unit of design was the register, not the job. The artefact performed a rigor it did not possess.

§10 (v1.4 scope amendment) is preserved in this file as a historical record of the failed direction but **does not govern future work**.

### v2.0a — corrective build (locked, see `reviews/v2_0a_spec.md`)

- Build a reusable engine: pipeline emits one role-agnostic JSON projection; thin role-specific apps consume it.
- Frequency-aware exposure model: P(incident|signal_state) × severity, surfaced as P50 / P95 / worst-anchor on one distribution. Replaces the v1.4 "3 methodologies" hack.
- Per-finding impact vector: {financial, operational, regulatory, customer_trust, safety}. Each role app surfaces the face it acts on.
- Provenance / lineage on every number: source query + timestamp + computation + assumptions, clickable modal. Replaces the "MOCK MODE" wallpaper.
- Per-role verb affordances (mock UI buttons): gate, accept, escalate, dispo, require-eval, restrict-scope.
- Cascade edges split into structural (mechanism-cited, no data needed) vs empirical (require n-history). The "≥50% co-fire, n=2" claim removed.
- AI Governance Lead built end-to-end as a real app (model/agent inventory, eval+guardrail status, MCP supply chain, intervention queue, trace stream) — the foundation's first consumer.
- The other 15 role views collapse into a single honest "Generic Register" view that explicitly admits it isn't the per-role-app pattern.
- "Risk operating system" branding dropped until v2.0 ships the remaining role apps.
- SEC 8-K Item 1.05 corrected — qualitative-determination workflow + 4-business-day clock; no dollar trigger.

### Estimated effort

v2.0a: ~51–68 hours (~5–7 calendar weeks at 2 hrs/day).
v2.0 (after v2.0a survives external review): ~80–100 hours additional.

### Definition of done

See `reviews/v2_0a_spec.md` §9. v2.0a passes when the external reviewer's directional fix questions all answer yes.

---

*Locked. Future agents: edit this file only with explicit version bump and a one-line changelog at the bottom. Do not unwind decisions in §1–§4 mid-iteration. §10 is historical; v2.0a (§11) governs.*

## Changelog

- 2026-05-21 — v1.3 spec locked after persona-model + primitives + sequence agreed with user.
- 2026-05-27 — v1.3.1 shipped (council-driven fixes from `reviews/v1_3_council_review.md`). v1.4 scope amendment proposed (§10) — Financial Impact tab added, sub-tabs per role explicitly deferred. STATUS.md created as session-level discipline doc.
- 2026-05-27 — v1.4 retracted after external review (`reviews/v2_0_external_review.md`). v2.0a spec locked (`reviews/v2_0a_spec.md`) — engine/presentation split + frequency-aware exposure + impact vectors + provenance + per-role verbs + AI Gov Lead deep build + honest collapse of 15 other role views + "risk OS" branding drop + SEC 8-K factual correction.
