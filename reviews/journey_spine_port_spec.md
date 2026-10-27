# Journey Spine Port Spec — v1.0 (LOCKED 2026-07-22)

**This file is the contract.** The operator has presented the three reference artifacts
(ACH risk diagram, ACH observatory, tech-risk pilot deck — real 2LoD work product,
bytes stay outside this repo) at least five times across two months; every prior plan
drifted when review rounds consumed the roadmap. This spec ends that:

- **The parking-lot rule:** until every stage below ships, external review findings are
  triaged AGAINST this spec — absorbed only if they land inside a stage already in
  flight, otherwise PARKED in §6 with a date. Review rounds do not preempt stages.
- **Drift is machine-held:** each stage lands with audit gates (C36.x) that FAIL the
  build if its structures go missing. A shipped stage cannot silently regress.
- **Session-survival:** `memory/project_journey_spine_port.md` points here and carries
  stage status; this file is committed and travels in the review bundle.

## 1 · The locked diagnosis (why the reference artifacts land)

1. They open with a BUSINESS OBJECT (breadcrumb → journey → services → window →
   posture) in the first four seconds; the portfolio opens with a methodology.
2. ONE DATED EVENT is the narrative anchor every panel orbits; the portfolio has
   distributions, and humans storyboard around events.
3. The four-hop chain (observed signal → risk IDs → owner → controls) lives in every
   cell WITH its caveat ("applicability not validated", "owner deactivated") — and
   missing data is stated with the same precision as present data.
4. The posture IS the chrome ("no findings · no verdicts · GRC SoR retains ratings ·
   no new work"), not a closing contract section.
5. Audience modes RE-ARGUE the case (different rows per audience), not re-filter it.

Fairness frame (locked): theirs = grounded but unverifiable; ours = verifiable but
ungrounded. End state: journey-shaped telemetry flowing through sealed, gated,
reproducible machinery — a combination neither lineage has.

## 2 · Rename discipline (ABSOLUTE — content-level employer-IP boundary)

**The journey NOMENCLATURE itself is ported (operator directive 2026-07-22):** the
reference artifacts' journey-framing vocabulary and ID style do not cross — this repo
says "critical business journey" / "journey spine" with the `J-SIM-*` id scheme, and
the shipped-bundle assertion machine-bans the reference term so it can never reappear.

No real service names, journey IDs, GRC-vendor names, dates, thresholds, peak values,
or owner names cross into this repo. Every ported structure wears the tag:

> **Structure from the operator's production 2LoD practice; all names, values, and
> dates seeded.**

The bundle assertion (no employer names) continues to enforce this mechanically.

## 3 · The synthetic estate (Stage 1 design — LOCKED unless operator renames)

**Journey:** `J-SIM-001 · Instant Transfer` — a customer moves money out of their
account to an external destination in near-real-time.
Breadcrumb: `Consumer Platform › Money Movement › Instant Transfer`.
Window: seeded 90d, `2026-03-15 → 2026-06-13`.
Posture line: `2LoD independent observation · no findings · no verdicts · seeded telemetry`.

**Stages → services (CNCF-style layers):**

| Stage | Services | Layer | Patterns hung here | Dependency nodes here |
|---|---|---|---|---|
| initiate | edge-gateway, transfer-api | edge / app | RP-02, RP-12 | api_registry |
| risk-check | risk-scorer, identity-verifier | app | RP-05, RP-08 | customer_identity_plane |
| ledger | ledger-writer, event-bus | data / messaging | RP-14, RP-11, RP-01 | primary_datastore, k8s_control_plane |
| rails | settlement-engine, rails-partner (external) | app / external | RP-04, RP-10 | payments_processor |
| settle | notify-svc, recon-batch | app | RP-09, RP-13 | cloud_region (spans all) |

Owners: team handles (team-money-movement, team-identity, team-platform-runtime,
team-treasury-eng, team-sre) — consistent with the A8 named-human gap (disclosed, not
faked). Controls: the patterns' own compensating_controls entries, linked per service
with the caveat **"control linkage seeded · applicability not validated"** in-cell.

**THE incident (the narrative anchor):** `SIM-0531 · event-bus consumer-lag storm ·
2026-05-31` — seeded series (deterministic, seed 42): lag builds from 09:40 ET,
ledger-writer p99 degrades ~5× baseline, retry amplification (the RP-14→RP-11 edge
live), self-recovers in ~2h with zero customer-visible failures — the self-concealing
loop. All peaks DERIVE from the seeded series (gate-recomputable), never typed.
hv cross-reference: kafka_lag scenario = this incident's war-room view; identity_outage
= the risk-check stage dark (fields, not build coupling).

**Journey SLO:** end-to-end transfer p95 < 5s, availability target 99.9% — the number
a board reads first; derived from stage series.

**Signal chip grammar (verbatim as FORMAT):** `SEEDED · {n}pts · {cadence} ·
gen:journey_signal_gen@seed42` — realness class, cardinality, cadence, generator, per
signal. `signal_catalog.json`: signal id → stage → service → owner → query intent.

## 4 · Stages, acceptance gates, status

| Stage | Deliverable | Acceptance (machine-held) | Status |
|---|---|---|---|
| **1a · data spine** | `data/journey_catalog.json` + `signal_catalog.json` emission + seeded incident series + projection block `journey_spine` | C36.1–5: catalog parses; every pattern/dep/control/owner reference resolves; incident peaks RECOMPUTE from seeded series; chain complete (all 4 hops + caveat) per service; SLO + chips derive | **SHIPPED 2026-07-22** (C36.1–5 green · rac audit 107 · probe zero-diff additive) |
| **1b · the journey surface** | `docs/journey.html` — first-paint storyboard: breadcrumb hero → path diagram with badges → dated-incident walk → per-service expand chain → audience rows | first-paint content asserted (breadcrumb, posture, SLO, incident date in first viewport); expand chain click-verified per service; matrix rows added; conservation additive | **SHIPPED 2026-07-22** (first-paint + chain + walk + audiences content-asserted live · C36.6 · screenshot-verified) |
| **2 · signal chips everywhere** | chip grammar on every hv/rac series panel + signal_catalog shipped | chips render per series; catalog reconciles with rendered signals (gate) | **SHIPPED 2026-07-22** (hv heroes + read rows chipped, per-scenario derived; stream_catalog GENERATED; gates C9.1–3; rac's series surface is the journey, chipped in 1a/1b) |
| **3 · operating-model delta** | rac panel: bespoke-chase → automated re-performance, `hard_to_reperform` flags, rating states (candidate → pending confirmation → confirmed) on register findings | states as data; A8 machinery named as mechanism; gate on state vocabulary | **SHIPPED 2026-07-22** (evidence lifecycle derived from test methods 28auto/30bespoke/26hard · rating states derived from register fields 9/6/10 · C37.1–3) |
| **4 · rollup + aggregator contract** | parent→child pattern rollup; `journey_aggregator.json` minimal contract with GATED verbatim-passthrough (hash of generator output == hash consumed) | B-gate: passthrough hash equality | **SHIPPED 2026-07-22** (rollup reconciles with the register C38.1 · passthrough four-way hash-equal C38.2/B12.4 · both surfaces render C38.3) |

Board verbs stay a separate altitude — the observation posture NEVER replaces the
decision surface (v106 proves they coexist).

## 4b · Stage 5 — VISUAL GRAMMAR (added v1.1, 2026-07-22: operator overrules §5's
"no dark-canvas parity" for MECHANICS — "I do not want to tell people. I want them
to see and follow along with ease"). The journey surface must SHOW:

| Device (from the references) | Journey port | Acceptance |
|---|---|---|
| Canvas flow-graph: nodes on the path, bezier edges, flowing particles | The money path as an animated graph — 10 services in 5 stage columns; transfer particles flow left→right | particles animate; nodes positioned per stage |
| Incident play/scrub with phase markers | SIM-0531 player: scrub the 150-pt overlay window; event-bus halo grows with lag, ledger ECG spikes, retry edge thickens (the feedback), drain | play + scrub work; node values update at tick; phases marked |
| Click node → detail card | The four-hop chain becomes a CARD shown on node click, not a stacked wall | click-verified content change |
| Step cards keyed to the walk | Chapter-2 step cards highlight as the scrub passes their phase; clicking a step jumps the scrub | click-verified |
| Trends over time | The 90d series drawn as a chart with the incident spike visible, not stats prose | chart renders from series |
| Rollup/lifecycle as bars not text | Parent bars with evidenced fill; evidence lifecycle stacked bar; rating states as 3-column flow | renders from data |

Status: **journey surface SHIPPED 2026-07-22** (flow-graph + player + cards + trend, all six devices content-asserted live; screenshot-verified). OPEN follow-up: rollup/lifecycle BARS on the workbench panels (last table row) — the journey was the flagship; the panel bars land next.

## 5 · What is explicitly NOT ported

Dark-canvas aesthetic parity, the exact Mermaid diagram, raw-Prometheus replacement of
the MC engine, gate-count inflation, any real byte from the reference artifacts.

**ALL FIVE STAGES SHIPPED 2026-07-22. The parking-lot rule is RETIRED — §6 items
are now eligible for triage in normal rounds. The next instrument is the COLD READ.**

## 6 · Parking lot (review findings deferred until stages ship)

- **PARKED (r44, 2026-07-25): front-door restructure.** GROK review A demands two primary doors (board + journey); GROK review B demands ONE (journey only); Claude review defends the current five-door entry outright. Mutually contradictory — the five-door IA is operator-locked (r43 roll) and only THE COLD READ (unbriefed human) reopens it. GROK's "journey services carry 0 risk IDs" claim was checked and REFUTED against journey_catalog.json (all ten services carry patterns, signals, owner, dependency nodes, non_claim).

- multi-region/multi-account isolation pattern (GROK P2, recurring) — parked 2026-07-22
- namespace/partition failure leaves — parked 2026-07-22
- deferred agent-layer nodes → first-class — parked 2026-07-22
- back-pressure "promotion" re-asks — REFUTED (RP-14 first-class since E4); do not rebuild

- **r50 wave (2026-07-25) dispositions.** Two GROK passes + Claude round-35 triaged.
  CONFIRMED AND ABSORBED: Claude's typed-count drift in the review brief ("74/74 ·
  55/55 · 29/29", "19/19" — all four stale vs the executed 114/63/33 · 26/26). Counts
  now DERIVE from qa/trust_board.json at brief generation and a build gate fails on
  any equal-pair N/N token that is neither a trust-board result, a named in-bundle
  re-executable (OSCAL 18/18, a2a 10/10), nor history-marked — plant-tested (74/74
  planted → exit 1; clean → pass). REFUTED BY DATA: GROK's "the README is still
  review-brief heavy" — GROK never saw README.md (not shipped in the bundle); the r45
  hiring README leads with category, GIF, and the CORRECT counts (210 = 114·63·33,
  plus 26). GROK's "COLD_READ lacks a product README" — the cold pack is priming-free
  BY DESIGN; briefing it would defeat its purpose. GROK's back-pressure P1 — re-ask
  of the REFUTED item above; unchanged. RE-ARGUED, STAYS PARKED: the front door
  (GROK again wants one-or-two doors; the parked entry above stands until THE COLD
  READ). NEW — AWAITING OPERATOR DECISION (strategic, not absorbable from an AI
  round): (a) Claude's repo split — platform monorepo stays canonical, three product
  repos cut as release exports with per-repo cold reads; (b) Claude's board strategy
  chooser (two named, priced strategies from existing lever/suppression leaves as
  rac's closing screen); (c) shipping README.md inside the review bundle so the
  hiring surface is verifiable next wave.

- **r53 wave (2026-07-25) — the split reviewed (2 Claude + 2 GROK passes), zero
  FALSIFIED.** CONFIRMED AND ABSORBED: (a) clipboard copy-link had no rejection
  handler (headless/enterprise-policy denial → unhandled page error) — .catch +
  prompt fallback at BOTH sites (shared ia_runtime.js and rac's inline twin);
  this also resolved Claude's two click-storm page errors. (b) rac/atg in-export
  audits need the pipeline (C25-class determinism gates re-run it — Claude's
  "packages/ leaks atg modules" diagnosis was wrong-mechanism, right-defect);
  pyyaml was missing from ALL THREE requirements.txt — added; README dep lines
  now tell the truth (pip install -r requirements.txt, and WHY: the gate re-runs
  the engine). (c) claim-discipline sweep: "strategy chooser" → "strategy
  decision surface" on every reader-facing surface with an explicit "informs the
  choice; does not re-run the engine on click" line (GROK: a chooser that
  doesn't choose); "±50%" symmetric gloss → "no single judgment moves it more
  than 50%; a joint bad year is +90% ($186.6M)", derived; "severity co-movement"
  → "common-cause severity co-movement"; rac README sends the CRO to board.html
  FIRST; verify_export documented as full-unzip-from-root; trust_board export
  copies carry the shared-harness note; the signed-hold posture gets strategy-
  grade visual weight (Claude: the hold is what makes the other two honest).
  REFUTED: "synthetic not in the first screen" (atg/hv first paragraphs already
  say synthetic/seeded); "purge team handles from A8 surfaces" (team routing IS
  the surfaced A8 gap — org-reality's whole argument; purging it would hide the
  finding). IN FLIGHT ELSEWHERE: hv 145-vs-143 event counts = the stream_catalog
  seed-oscillation side-write, already running as its own task. PARKED:
  register-level accountable_exec column (C15 gate interaction — next round);
  make-the-surface-actually-choose (needs A8 evidence design, not a patch); hv
  worked slice example; per-repo clean-venv CI (needs GitHub repos to exist).
