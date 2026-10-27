# agent-trace-gov v2.0 — dashboard port spec & external-review brief

> **Status:** DRAFT for external review (new Claude session + Grok). Not yet
> signed off; no code written. The two starred decisions below are the ones I
> most want challenged.
> **Author's standing instruction:** no compromises, no cutting corners. If a
> recommendation here is the *easy* path rather than the *right* path, say so.

---

## 0. How to review this (what feedback is wanted)

This is a spec for porting a mature governance-dashboard foundation (from a
sibling project, `risk-as-code-agent`) onto `agent-trace-gov`. I want a
**reviewer's teardown**, not encouragement. Specifically pressure-test:

1. **The architecture call** (§4 ★): keep agent-trace-gov's existing engine and
   add an adapter, vs. lifting the sibling's engine wholesale. Is the adapter
   seam (§6) the right boundary, or does it leak?
2. **The impact-axis call** (§4 ★): honest non-dollar impact vs. an
   "illustrative" dollar model. Is the non-dollar model *actually* defensible,
   or is it just a different flavour of hand-waving?
3. **The honesty rules** (§10): does anything here "perform a rigor it doesn't
   possess" (the phrase that sank v1.4 — see §2)? Where is a number asserted
   without a lineage to back it?
4. **The 5-act mapping** (§7): does the SIGNAL→PATTERN→IMPACT→DECIDE→ATTEST
   narrative fit *this* domain, or is it a borrowed costume?
5. **Scope discipline** (§11): is the staged plan honestly stoppable, or does
   stage 1 secretly require stage 4?

---

## 1. The portfolio context

Three small cybersecurity-risk portfolio projects share a skeleton
(`agents/ graph/ data/ ui/ utils/`):

- **`risk-as-code-agent`** — the deepest. Just shipped **v2.0a-alpha4** + an M6
  responsive pass: a render-from-data, warm-terminal governance dashboard with a
  reusable engine/presentation split, frequency-aware exposure, per-finding
  provenance, hash-chained action log, and a 39-check internal audit. This is
  the **foundation** being ported.
- **`agent-trace-gov`** — v1.1. A grounded LangGraph governance pipeline with a
  Streamlit UI. **The target** of this port. (This doc.)
- **`hypervelocity-risk-sim`** — v1.1. Next in line after this (separate spec).

The portfolio brief: "quick visible wins on three small projects, then bigger
flagship work." The foundation is reusable infrastructure, so this port is the
payoff on that investment — `agent-trace-gov` gets a real dashboard without
rebuilding the engine concepts from scratch.

---

## 2. The quality bar (why this is strict)

The sibling project's predecessor, **v1.4, was retracted** after an external
reviewer's teardown. The dispositive failures (these define the bar this port
must clear):

- **Fabricated exposure.** "$374.5M exposure" was a *sum of other companies'
  worst historical analogs* (e.g. Knight Capital's $440M), presented as if it
  were this firm's expected loss. Three methodologies, one severity axis, **no
  probability term.** → *This is why §4 ★ rejects a dollar model for
  agent-trace-gov.*
- **Confidence labels on unmeasured things.** "high/medium/low confidence" on
  cascade edges that were never measured; an "≥50% co-fire" claim at n=2.
- **Disclaimers instead of lineage.** "MOCK MODE" stamped 157 times instead of
  clickable provenance on each number.
- **The reviewer's verdict:** v1.4 *"performed a rigor it did not possess."*

The corrective build (v2.0a) fixed all of these with: a frequency model
(expected loss, not summed analogs), provenance on every number, a real
hash-chained log with an in-browser `verifyChain()`, and honest "illustrative +
labeled" framing. **This port must inherit that discipline, not just the CSS.**

---

## 3. The two artifacts, briefly

### 3a. The foundation (`risk-as-code-agent` v2.0a) — what's reusable

| Layer | What it is | Reusability |
|---|---|---|
| **Engine** (`utils/projection.py::make_projection`) | Pure function → one role-agnostic JSON **projection**. | Contract is generic; *content* is finance-coupled. |
| **Presentation** (`utils/v2_html_report.py`, ~4200 LOC) | Warm-terminal, render-from-data HTML. Reads an embedded `<script id="projection-source">`; JS hydrates `data-target` slots. 5-act IA, user switcher, domain rail, exec hero band. | **~100% generic** — pure scaffolding + `data-target` slots. |
| **Action log** (`utils/action_log.py`) | Append-only JSONL, SHA-256 hash-chained, `verify_chain()`. Verbs + role tiers + 12-word-justification rule. | **100% generic.** |
| **Provenance** (`utils/projection.py` helpers) | Every number wraps `{value, provenance{source_status, source_system, source_query, computation, assumptions}}`. 4 source-status tiers incl. `published_standard` + `illustrative`. | **100% generic.** |
| **Exposure** (`utils/exposure.py`) | frequency × severity at P50/P95/worst-anchor. | Math generic; **USD + finance anchors are the coupled part** (see §4 ★). |
| **Audit** (`tools/audit_v2_0a.py`) | 39 substance-gated internal-consistency checks. | Logic generic; pattern IDs hardcoded — parameterize. |
| **Data** (`data/risk_patterns.json` etc.) | 13 finance risk patterns (RP-01..RP-13), USD anchors, SEC/OCC/GDPR triggers. | **0% — this is the domain layer agent-trace-gov replaces with its own.** |

### 3b. The target (`agent-trace-gov` v1.1) — what already exists and is good

agent-trace-gov is **already an AI-governance project** — it is not a foreign
domain we're forcing the dashboard onto. It has:

- **A grounded engine** — `graph/governance_graph.py`: a 4-stage LangGraph
  pipeline (`trace_collector → pii_scanner → risk_classifier → evidence_builder`)
  → `run_governance_analysis(n)` → a structured `governance_report`.
- **A real taxonomy** — `data/action_schema.json`: 8 action types + **8 risk
  events RE-01..RE-08** (PII detected, consent missing, unauthorized external
  flow, agent scope exceeded, low-confidence automated decision, lineage break,
  excessive retention, multi-agent loop). Each RE carries severity, a
  `framework_source_url`, and **incident anchors** (ChatGPT Redis 2023, Air
  Canada 2024, CVE-2025-49596 MCP Inspector RCE 2025, Amazon €746M GDPR, …).
- **Framework alignment** — GDPR, CCPA, NIST CSF 2.0, NIST AI RMF, ISO 27001,
  **SOC 2 (CC6.1, CC6.6, CC9.2, P3.1, P6.1)**, EU AI Act.
- **Real domain objects** — Workflow → Agent → Action/Trace → Risk Event →
  Data-Lineage Edge. Atomic unit = the **action/trace record**.
- **An established voice** (v1.1 "grounding + voice pass"): forensic,
  incident-driven, non-prescriptive, citations are defensible not decorative.
- **Current UI:** a Streamlit app (`ui/app.py`) — a structured narrative
  explorer (4 tabs), *not* a dense data dashboard. This is what the port
  upgrades.

**The punchline:** agent-trace-gov's engine already does, in its own domain,
exactly what the foundation's engine does in finance — classify, anchor to
incidents, map to frameworks, produce a structured report. That is why the
recommendation is to **adapt, not replace.**

---

## 4. The proposal ★

### 4a. Architecture: **Adapter port** (keep agent-trace-gov's engine)

Keep `governance_graph.py` as the domain source of truth. Add a thin
**projection adapter** (`utils/projection.py`, new) that maps
`governance_report → projection` (the generic contract, §6). Lift the
presentation layer, action log, and provenance system from the foundation onto
that projection. Raise the engine to foundation rigor where it falls short
(provenance wrapping, an honest impact model, the hash-chained decision log).

- *Rejected alternative — engine reskin:* lift the foundation's
  `projection.py`/data layer and swap RP-01..RP-13 for RE-01..RE-08. This throws
  away agent-trace-gov's working, grounded engine (PII scan, lineage graph, SOC
  2 mapping) and risks re-importing finance assumptions. **It's the corner-cut.**

### 4b. Impact axis: **honest non-dollar impact**

No fabricated currency. Impact is expressed in domain-native, defensible terms:

| Axis | Source (already in `governance_report` or trivially derivable) |
|---|---|
| **Severity × occurrence** | RE severity tier × `occurrence_count` (real, counted). |
| **Blast radius** | `affected_agents`, `affected_workflows`, # PII flows, # external flows. |
| **Data exposure** | data classes touched (email/phone/SSN/account/name), `consent_verified` gaps. |
| **Regulatory exposure** | *qualitative* — framework citation + the real-world anchor incident, **not** a synthetic fine estimate. e.g. "RE-07 → GDPR Art. 5(e); anchor: Amazon €746M." |

The anchor incidents' real fines (Amazon €746M, Meta €390M) may be *displayed as
cited anchors* (what regulators actually levied for this class) — but never
summed into a fabricated "our exposure" number. That distinction is the entire
v1.4 lesson.

---

## 5. Concept mapping (foundation → agent-trace-gov)

| Foundation (finance) | agent-trace-gov (AI governance) |
|---|---|
| Finding (pattern × domain) | **Risk event occurrence** (RE × workflow/agent) |
| 13 risk patterns RP-01..RP-13 | **8 risk events RE-01..RE-08** (the taxonomy) |
| Service domains (payments, trading, custody…) | **Agents** (or workflows) — the rail filter |
| Breached signals + thresholds | **Risk signals** in actions (`pii_detected`, `confidence<x`, `consent_verified=false`, scope drift) |
| Cascade edges (pattern→pattern) | **Data-lineage edges** (agent→system→external) + multi-agent loop (RE-08) |
| Impact vector (financial/operational/…) | **Honest impact** (§4b): severity×occurrence, blast radius, data class, reg exposure |
| USD expected loss (P50/P95) | **Occurrence-weighted severity** (no $) |
| Materiality (SEC 8-K, OCC, GDPR) | **Framework findings** (SOC 2 criteria, GDPR/CCPA/NIST AI RMF) — already produced by `evidence_builder` |
| Verb affordances (gate/accept/escalate…) | **Governance verbs** (§8) |
| Hash-chained action log | **Attestation log** — the immutable record of finding→decision→remediation→sign-off (agent-trace-gov's reason to exist) |
| Anchoring incidents | **Already present** in `action_schema.json` per RE |

---

## 6. The adapter seam — projection contract the engine must emit

The adapter's job: emit one JSON projection matching the foundation's contract,
so the presentation layer hydrates unchanged. Target shape (domain-mapped):

```jsonc
{
  "meta": { "schema_version, artefact_version, period, generated_at,
            "domain_ids": [<agent_id|workflow_id>...],  // the rail
            "counts": { risk_events_total, critical, high, medium, low,
                        workflows_analyzed, actions_traced, pii_flows, external_flows },
            "overall_posture": "critical|high|medium|clean" },
  "domains": { "<agent_or_workflow_id>": { name, tier, overall_rag,
               risk_events:[...], executive_summary, attestation_statement } },
  "findings": [ {                              // = risk-event occurrences
     "finding_id": "RE-…-<workflow>-<agent>",
     "risk_event_id": "RE-04", "name", "severity", "nist_function",
     "first_detected", "time_in_state",
     "breached_signals": { "<signal>": { value, rag, threshold, value_provenance } },
     "blast_radius": { affected_agents, affected_workflows, pii_flows },
     "lineage": { upstream:[...], downstream:[...] },          // from lineage_map
     "impact": { severity_tier, occurrence_count, data_classes:[...],
                 regulatory: [ { framework, citation, anchor_incident } ] },  // NO $
     "treatment": { decision, status, owner, ticket },
     "frameworks": [ { id:"SOC2 CC6.1", status:"finding|satisfied", note } ],
     "anchoring_incidents": [ { name, date, summary, url } ],  // already in schema
     "agent_id", "workflow_id"
  } ],
  "lineage_graph": { nodes:[...], edges:[...] },               // from lineage_map
  "frameworks": { "SOC2": {...}, "GDPR": {...} },              // from soc2_evidence
  "action_log_path": "data/attestation_log.jsonl",
  "patterns_meta": [ {id, name, description, framework, severity} ],  // RE-01..08
  "history": [ ... ], "actuals": { ... }                       // optional, honest-only
}
```

**Provenance rule:** every numeric value carries `value_provenance`. For
agent-trace-gov most values are `real_query_synthesized_data` (counted from
simulator traces — honest: real counting over synthetic input) or
`published_standard` (framework citations). The simulator's synthetic nature is
disclosed once, at the banner, not stamped 157 times.

---

## 7. 5-act IA mapping for this domain

| Act | agent-trace-gov meaning |
|---|---|
| **SIGNAL** | What fired in an action — PII detected, consent missing, confidence below threshold, scope exceeded. The raw observation. |
| **PATTERN** | Which RE risk-event class, and the lineage/loop: "5 agents touched PII across 3 workflows; an unauthorized external flow to a non-allowlisted endpoint." |
| **IMPACT** | Honest blast radius (§4b): agents/workflows affected, data classes, framework findings — no $. |
| **DECIDE** | Governance verb on the finding (§8). |
| **ATTEST** | The hash-chained attestation log + SOC 2 evidence pack — agent-trace-gov's core output, now first-class. |

This is a *better* fit than finance: agent-trace-gov literally exists to produce
the ATTEST artifact, so act 5 is its native endpoint, not a bolt-on.

---

## 8. Governance verb taxonomy (replaces finance verbs)

`acknowledge` · `escalate` · `gate` (block an agent scope/tool) · `suppress`
(mute N days + reason) · `override` (mark false-positive + evidence) ·
`remediate` (link ticket) · `certify` (auditor sign-off). Each writes a
hash-chained attestation entry: `{finding_id, verb, actor, role_tier,
justification(≥12 words), evidence_id, expiry?}` — reusing `action_log.py`
unchanged.

---

## 9. What's lifted / adapted / new

- **Lift as-is:** `v2_html_report.py` (presentation), `action_log.py`,
  provenance helpers, the audit-tool *harness* (`tools/audit_*.py`), warm-terminal CSS + M6 responsive pass.
- **Adapt:** a new `utils/projection.py` adapter (`governance_report →
  projection`); the audit checks (parameterize RP→RE); `patterns_meta` from
  `action_schema.json`.
- **New / honest stubs:** the impact model (§4b); `attestation_log.jsonl`
  seeded from real decisions; an integrity seal.
- **Keep untouched:** `graph/governance_graph.py`, `data/action_schema.json`,
  `data/agent_simulator.py`, `SOURCES.md` voice.

---

## 10. Honesty rules (carried from v2.0a; non-negotiable)

1. **No fabricated exposure.** No synthetic dollar figure. Anchor incidents'
   real fines may be *cited*, never *summed into "our exposure."*
2. **Provenance, not disclaimers.** Every number has a lineage chip; synthetic
   input disclosed once at the banner.
3. **No confidence on unmeasured things.** Lineage edges are *structural*
   (observed flows), not probabilistic. No "co-fire %" unless actually counted.
4. **Demonstrator framing.** Input is `agent_simulator.py` (synthetic); the
   *governance logic* is real. Labeling says exactly that.
5. **The audit gates substance, not strings.** Ported checks assert a signal
   *fires in a real finding*, not that a config key exists.

---

## 11. Staged plan (each stage stoppable; sign-off between)

1. **Spec lock** (this doc + external review) → freeze decisions. ← *we are here*
2. **Adapter + projection** — `governance_report → projection.json`; a port of
   the audit harness goes green on internal consistency. *No UI yet.* Stop.
3. **Presentation wire-up** — embed projection, hydrate the dashboard, 5-act IA
   in the agent-trace-gov domain. Stop.
4. **Decision surface** — verbs + hash-chained attestation log + `verifyChain()`
   in-browser. Stop.
5. **Honesty + polish pass** — provenance coverage, responsive (inherit M6),
   integrity seal, demonstrator labeling. Re-review. Stop.

No stage starts before the prior one is signed off. No GitHub push without
explicit OK (distribution discipline).

---

## 12. Acceptance criteria (definition of done)

The external reviewer's directional questions all answer yes:
- Is provenance on every number? Is the synthetic input disclosed honestly (once)?
- Is impact expressed without a fabricated dollar figure?
- Is the attestation log real (hash-chained, in-browser verifiable)?
- Does the 5-act narrative read native to AI-trace governance, not borrowed?
- Does a ported audit gate **substance** (signal fires in a real finding)?
- Does it not "perform a rigor it doesn't possess"?

---

## 13. Open questions I most want the reviewers to answer

1. Is "honest non-dollar impact" (§4b) genuinely defensible to a SOC 2 auditor,
   or does an exec audience need *some* magnitude axis — and if so, what honest
   one (e.g. "records exposed", "agent-hours unsupervised")?
2. Is the **agent** or the **workflow** the right rail/primary object? (Finance
   used service domains; agent-trace-gov could go either way.)
3. Does keeping two engines (LangGraph for ATG, none lifted) create a
   maintenance seam that will rot, vs. one unified engine across the portfolio?
4. Is the attestation log meaningfully different from the foundation's action
   log, or am I renaming the same thing?
5. What's missing — a modality, a claim, a regulatory mapping — that a real
   compliance officer shipping agents in 2026 would immediately ask for?

---

# 14. Amendments from the 4-lens review (v2.0 — OPERATIVE)

> **Status: this section supersedes any conflicting prose above and is the
> spec of record once locked.** Produced by a 4-lens teardown (2026-06-23):
> 2LoD **risk-officer**, **audit-regulator** (SOC 2 / GDPR examiner),
> **design-lead**, **sre/architecture** — each reading the actual
> `governance_graph.py`, `action_schema.json`, `agent_simulator.py`, and the
> foundation's `projection.py`, not just this prose. Pending second opinion
> (Grok) against THIS amended spec before final lock, per §0.

## 14.0 What held (do not touch)
- **§4a adapter-over-reskin** — keep agent-trace-gov's LangGraph engine; add an
  adapter. Three lenses explicitly endorsed; none objected.
- **§4b non-dollar thesis** — refusing a fabricated dollar figure is correct.
  All four affirmed. (But the *impact model* underneath needs §14.B.)
- **§3b/§10.3 lineage edges are genuinely observed** (src→dst per trace in
  `risk_classifier`), not inferred. Holds.

## 14.A — §6 contract is the #1 fix; rework BEFORE lock (risk-officer + audit-regulator + sre)
The §6 projection contract demands fields the engine does not produce, and
silently drops finance blocks the lifted presentation hydrates. Both are
"perform a rigor it doesn't possess" risks. Required changes:

1. **Fields the engine cannot produce — derive-and-label or drop:**
   - `first_detected` / `time_in_state` — engine emits per-trace `timestamp`
     only (`governance_graph.py:151`); there is no detection-event ledger. Either
     compute `first_detected = min(timestamp)` over the grouped events **and mark
     its provenance `derived`**, or omit the field. The adapter must NOT mint
     forensic history the engine never observed.
   - finding-level `frameworks[]` SOC 2 control IDs — the engine maps a coarse
     framework string per RE; SOC 2 control IDs (CC6.1…) are computed only at the
     **aggregate** `soc2_evidence` level. Per-finding control-ID claims must be
     **engine-emitted, not adapter-decorated**, or they are decoration (§10.5).
   - `treatment{}` — net-new, no source object. Until it links to real
     `attestation_log.jsonl` entries it is words, not provenance. Mark `absent`
     until the decision surface (Stage 4) populates it.
   - `breached_signals.threshold` — the engine never stores a threshold;
     `confidence: 0.41` is a string literal in the simulator, never compared. Do
     not render a `threshold` chip implying a measured bound.
2. **Add a 5th provenance tier `derived` (and an `absent` marker)** alongside
   `real_query_real_data` / `real_query_synthesized_data` / `published_standard`
   / `illustrative`. The honest minority (derived/absent fields above) carry it.
3. **`anchoring_incidents` moves OUT of `findings[]` up to `patterns_meta[]`**,
   keyed to the RE *class*. v1.4 died on **adjacency**, not summation: a
   €746M anchor rendered inside an individual finding's impact band asserts it as
   this firm's exposure by proximity. Anchors live in a separate "regulatory
   precedent" register keyed to RE class, never on a finding's impact row.
4. **§6 must enumerate every foundation top-level block as KEEP / STUB / DROP.**
   The lifted `v2_html_report.py` hydrates finance blocks the AI domain lacks —
   `exposure` (USD P50/P95), `materiality` (SEC 8-K / OCC clocks),
   `inherent_residual`, `defense_layers`, `skew`. Resolution (ties to §14.D): the
   presentation becomes **projection-driven — render a block iff present**; the
   AI projection simply omits finance blocks, and they do not render. No honest-
   stub theater, no per-domain forks of the presentation. This makes §9's "lift
   as-is" TRUE rather than false.

## 14.B — The magnitude axis (ALL FOUR lenses)
`severity × occurrence_count` is **not** a magnitude or a distribution — no
probability term (the exact v1.4 exposure defect). Required:
- **Add "records / PII-flows exposed" as the magnitude axis** — counted from
  `lineage_map.pii_flows × data-classes-per-flow` (provenance
  `real_query_synthesized_data`), no modeled term. It is the number GDPR
  Art. 33(1)(a) notification turns on. (audit-regulator: strictly superior to
  "agent-hours unsupervised," which needs a duration model the simulator lacks.)
- **Drop the P50/P95 percentile framing entirely** — do not let the foundation's
  exposure widget imply a distribution that does not exist (design-lead).
- **`severity × occurrence` survives only as a sort key**, never rendered or
  labeled as impact/magnitude (risk-officer).
- **No composite "risk score"** blending radius + severity + data-classes — a
  weighted composite performs a precision the weights don't possess
  (audit-regulator; §10 by the back door).
- Carry an inline `synthetic_input` chip on the magnitude number specifically
  (not just the banner) — it's the one figure an exec quotes out of context.

## 14.C — Sever cascade → lineage (design-lead + sre)
Strike the §5 mapping row "Cascade edges → data-lineage edges." Finance cascades
are **probabilistic pattern→pattern inferences** (`_cascade_graph` reads
`cascade_to`/`rationale`/`materiality_trigger` off the pattern catalog —
RE-01..08 have none of that); lineage edges are **observed structural data-flow**.
Same field name = re-importing the v1.4 "confidence on unmeasured things" sin.
RE-08 (multi-agent loop) also does not belong on the lineage-edge row; it is its
own structural event.

## 14.D — Two-engine rot → shared-core extraction (sre; supersedes §4a/§9/§13-Q3)
Keeping two engines while copy-pasting the foundation rots (every foundation
improvement hand-re-ported) AND makes §9's "lift as-is" false. **Decision: the
RIGHT path, not the copy-paste corner-cut.**
- **Extract a shared package `portfolio-core`** that both `risk-as-code-agent`
  and `agent-trace-gov` import: the render-from-data **presentation**,
  `action_log.py` + `verify_chain()`, the **provenance helpers**, and the audit
  **harness**. ~100%-generic layer per §3a.
- **`make_projection` stays per-domain** — irreducibly domain-coupled; each
  project emits the generic projection contract, the shared core renders it.
- The extraction **forces the presentation to become truly projection-driven**
  (§14.A.4) — a real quality gain that flows BACK into project 1.
- This **dissolves §13-Q4**: the "attestation log" is literally the shared
  `action_log`, domain-configured (verbs in §8) — a rename, now made structural.
- **Discipline gate (non-negotiable):** the extraction must be
  **behavior-preserving for `risk-as-code-agent`** — after it imports
  `portfolio-core`, project 1 must still pass its 39-check audit AND render
  pixel-identically in the browser. That green + identical render is the gate;
  if it fails, the extraction is wrong and is fixed before the port proceeds.

## 14.E — IA: lineage graph is the hero; workflow is the rail (design-lead)
- **The lineage graph is the first-paint hero, not a 6-tile numeric exec band.**
  Finance used a numeric band because money is scalar with no native spatial
  object; agent-trace-gov has real node-edge data (agent→system→external).
  Lead with the graph — RE-03 external-flow edges lit critical — and demote the
  counts to a thin strip beneath. `lineage_graph` is promoted from IMPACT to
  the hero slot.
- **Workflow is the rail / primary object; agent is the secondary facet** (a
  within-workflow filter), not user-switchable. RE-03/04/08 are cross-agent
  events that only exist at workflow altitude — an agent rail shreds them. SOC 2
  evidence attaches to a system boundary = the workflow. (§13-Q2 answered.)
- **Rename act 2 PATTERN → PROPAGATE**, and give it the lineage/loop job (SIGNAL
  and PATTERN are near-identical gestures here — a signal *is* its RE class;
  there is no finance-style multi-signal cascade). 5-act spine kept for portfolio
  continuity. (§13-Q4 narrative; §0.4 answered: native-with-this-adjustment.)

## 14.F — Regulatory mappings to add (audit-regulator; additive to `action_schema.json`)
1. **EU AI Act Art. 14 (human oversight) + Art. 12 (automatic logging/record-
   keeping)** — the #1 gap for a 2026 deployer. RE-04 (scope exceeded) + RE-05
   (low-confidence decision) are Art. 14 failures; the attestation log itself is
   the Art. 12 control.
2. **GDPR Art. 33 / 34 (72-hour breach notification)** — RE-01 / RE-03 are
   notifiable-breach triggers; also *why* "records exposed" (§14.B) is the right
   magnitude (Art. 33(1)(a) requires it by name).
3. **EU AI Act Art. 26 (deployer obligations) + GDPR Ch. V Art. 44–49
   (cross-border transfer basis)** — RE-03 "unauthorized external flow" is a
   transfer event with no lawfulness basis cited; "external → to where, under
   what SCC/adequacy basis?" is the immediate compliance question.

## 14.G — Honest demonstrator bound, stated not implied (sre; amends §10)
Add to §10: the simulator emits **6 deterministic scenarios on an `i % len`
rotation** (`agent_simulator.py:190`) — every `pii_leak` is byte-identical. "Real
logic over synthetic input" is honest labeling but has a **credibility floor it
cannot cross as a demonstrator**: real traces carry malformed spans, partial PII
hits, clock skew. State this bound explicitly in §10; do not imply trace-fidelity
the fixture can't support.

## 14.H — §10.5 audit gate is currently unsatisfiable; restate honestly (risk-officer)
The simulator **pre-assigns** risk events in scenario tuples (`"RE-01,RE-03"`,
`agent_simulator.py:109,146`) — findings are hand-labeled in the fixture, not
detected from signal values. So "the audit asserts a signal *fires in a real
finding*" cannot hold as written. Resolution: **§10.5 honestly states the audit
gates *classification + projection plumbing* (the RE is correctly carried from
schema → report → projection → render), NOT *detection*.** Detection-from-signals
is a named, deferred capability (would require the engine to derive RE-IDs from
`pii_detected` / `confidence < x` / `consent_verified=false` / scope drift), not
a claim this demonstrator makes.

## 14.I — §11 re-cut (sre; the staging was not honestly stoppable at 2→3)
The old Stage 2 ("adapter + projection, no UI, stop") cannot freeze the
projection schema without knowing Stage 3's presentation slot demands — the §14.A
coupling. Re-cut:

| Stage | Scope | Stoppable? |
|---|---|---|
| **0 · Shared-core extraction** | Extract `portfolio-core`; project 1 imports it; **project 1 stays 39/0 + pixel-identical** (§14.D gate). No agent-trace-gov change yet. | ✅ hard gate |
| **1 · Spec lock** | This amended spec + Grok → freeze. ← *here* | ✅ |
| **2 · Adapter + projection + contract reconciliation** | `governance_report → projection` adapter; resolve §14.A KEEP/STUB/DROP against the real presentation slot demands (owns the contract↔presentation reconciliation, not pretending it can stop before seeing it); port the audit harness, gating **substance** (§14.H). No new UI. | ✅ |
| **3 · Presentation wire-up** | Embed projection; hydrate the projection-driven presentation; lineage-graph hero + workflow rail + PROPAGATE (§14.E). | ✅ |
| **4 · Decision surface** | Governance verbs + shared hash-chained attestation log + in-browser `verifyChain()`; populate `treatment{}` (closes §14.A.1). | ✅ |
| **5 · Honesty + polish** | Provenance coverage incl. `derived`/`absent` tiers; responsive (inherit M6); integrity seal; demonstrator labeling (§14.G); reg mappings (§14.F). Re-review. | ✅ |

No stage starts before the prior is signed off. No GitHub push without explicit OK.

## 14.J — Deferred-but-named for real production use (sre §13-Q5; not in scope, stated honestly)
Named so the demonstrator's boundary is explicit: (1) **live trace ingestion**
(OTel / LangSmith span export) replacing the simulator; (2) **verb write-back
round-trip** (acknowledge/suppress persist + re-render — without it the dashboard
is a viewer); (3) **auditor export** (PDF/CSV/JSON evidence pack — the actual SOC
2 deliverable). These define "what's missing to be a tool, not a demonstrator,"
and are honestly out of scope for this port.

---

# 15. Lock amendments — GROK + new-Claude spec review (v2.1 — THIS LOCKS THE SPEC)

> Second-opinion review (2026-06-23): **GROK 9.4/10** + a **new Claude session**,
> both against the §14-amended spec. Both endorsed the architecture (§4a adapter,
> §4b non-dollar, §14.D shared-core) — no architecture change. They found prose
> contradictions, one hard staging gate, and under-specified detail. §15
> resolves all of it and is the **operative spec of record**; on conflict, §15 >
> §14 > §1–13.

## 15.A — Resolve the §4b ↔ §14.B contradiction (Claude #1)
§4b's table still leads with "Severity × occurrence" as the impact axis; §14.B
demoted it to a **non-rendered sort key**. Same class of internal contradiction
as the foundation's `worst_anchor_sum_usd` (a stored artifact contradicting
adjacent text), here in prose. **Resolution: §4b is superseded by §14.B.** The
operative impact model is:
- **Magnitude axis = "records / PII-flows exposed"** (the rendered number).
- **`severity × occurrence` = a sort key only**, never rendered, never labeled
  impact/magnitude. (A reader implementing top-to-bottom must not ship the §4b
  version.) Treat the §4b table row as historical.

## 15.B — Magnitude axis: concrete derivation + provenance (GROK #2)
"records exposed" must not become a second hand-wave. Locked derivation:
```
records_exposed(finding) = Σ over the finding's pii_flows of
                           records_in_flow × distinct_data_classes_in_flow
```
- **Source:** `lineage_map.pii_flows` (counted from traces) × the flow's
  `data_classes` (email/phone/SSN/account/name — counted). `records_in_flow` is
  the trace-reported affected-record count where present; **where the trace does
  not carry a count, the field is `absent` (not 0, not estimated)** — the magnitude
  shows "≥ N flows, record count not instrumented," never a fabricated number.
- **Provenance:** `real_query_synthesized_data` (real counting over synthetic
  input) for counted flows; `absent` for un-instrumented record counts.
- **Surfacing:** one **magnitude card** in IMPACT showing records-exposed +
  flow count + data-class chips, each value lineage-clickable. It **replaces the
  finance exposure widget entirely** (no P50/P95 scaffolding — §14.B).
- Carries an inline **`synthetic_input` chip on the number itself** (§15.K).

## 15.C — Act-level adjacency (Claude #3 — extends §14.A.3)
§14.A.3 moved anchors out of `findings[]`; it stopped one step short. The
**records-exposed magnitude (§15.B) and the anchor/precedent register must never
share a viewport region** — proximity makes a reader's eye do the multiplication
the spec refused to do (records × €746M = reconstructed fabricated exposure, with
no summed figure). **Lock: the anchor/precedent register lives in ATTEST (or
PATTERN/PROPAGATE), keyed to RE class. It NEVER renders in IMPACT alongside the
counted magnitude.** Adjacency is a v1.4 vector at the act level, not just the
field level.

## 15.D — Stage 0 extracts the FIXED core; strengthen the gate (Claude #2 — HARD GATE)
"Lift `action_log.py` + `verifyChain()` as-is" was **false at review time** — that
subsystem had four live defects (fake named-human gate; stale chain badge; the
`_local` write/verify hash asymmetry; the `worst_anchor_sum_usd` artifact).
- **Precondition (DONE):** the foundation's action-log fix-round landed as
  **commit `822d819`** on `risk-as-code-agent@v2.0a-m6`, browser-verified.
  **Stage 0 extracts that fixed subsystem, not the pre-fix one.**
- **Gate strengthened.** §14.D's "39/0 + pixel-identical" is necessary but NOT
  sufficient — the 39-check audit is the same author-written smoke test that
  passed 39/0 *with* the defects present; pixel-identical does not exercise chain
  logic. **Stage 0's gate ADDS the browser-verified integrity behaviors:** (1)
  `@platform` / slug / single-token rejected, named human accepted; (2) chain
  badge refreshes on local append without reload; (3) a locally-appended entry
  verifies `N/N` after a reload (not `N-1/N`). All three must pass in an actual
  browser against project 1 post-extraction, OR the extraction is wrong.

## 15.E — Shared-core extraction sequence (GROK #3)
Locked order, each step behavior-preserving for project 1 (audit + browser gate
§15.D between steps):
1. **`action_log.py` + provenance helpers** first (pure Python, no UI coupling) —
   smallest, highest-value, and the fixed subsystem (§15.D).
2. **Presentation** (`v2_html_report.py` render-from-data + CSS/JS) — the large
   one; this is where the §14.A.4 "render-iff-present" decoupling is forced
   (finance blocks become projection-driven, not hardcoded).
3. **Audit harness** (`tools/audit_*.py`) last — parameterize pattern IDs
   (RP↔RE); the substance-gate logic is generic, the IDs are not.
`make_projection` stays per-domain in each project, never in `portfolio-core`.

## 15.F — §6 KEEP / STUB / DROP table, explicit (GROK #1 — makes §14.A.4 concrete)
Every foundation top-level projection block, resolved for the AI domain:

| Block | Disposition | Rule |
|---|---|---|
| `meta`, `domains`, `findings` | **KEEP** | domain-mapped (RE occurrences, workflow rail) |
| `patterns_meta` | **KEEP** | from `action_schema.json` (RE-01..08) |
| `lineage_graph` | **KEEP + PROMOTE** | the hero (§14.E / §15.I) |
| `action_log` | **KEEP** | the shared fixed core (§15.D) |
| `materiality` | **KEEP, re-source** | framework findings (SOC 2 / GDPR / EU AI Act), not SEC/OCC dollar clocks |
| `exposure` (USD P50/P95) | **DROP** | replaced by records-exposed magnitude (§15.B) |
| `inherent_residual` | **DROP** | finance frequency×severity; no AI-domain equivalent shipped |
| `defense_layers` (NIST CSF) | **STUB → absent** | not counted from traces; render only if a real control-coverage source exists, else omit |
| `skew`, `actuals`, `trajectory` | **STUB → absent** | honest-only; omit unless counted |
| `groups` | **KEEP, re-map** | by workflow / agent / data-class instead of finance teams |
**STUB rule:** a stubbed block is **omitted from the projection entirely** (the
presentation renders iff present, §14.A.4) — never emitted with placeholder/zero
values. No honest-stub theater.

## 15.G — Lineage-graph hero: rendering defined (GROK #4)
- **Static inline SVG**, server-rendered from `lineage_graph.{nodes,edges}` — no
  runtime force-layout (deterministic, self-contained, print/export-safe, matches
  the render-from-data contract). Layered left→right: agents → systems → external.
- **Edges colored by RAG**; RE-03 external-flow edges to non-allowlisted
  endpoints lit `breach`. Node size = flow volume (counted).
- **RE-08 (multi-agent loop)** renders distinctly: a **back-edge / cycle
  highlighted** (the only non-DAG element), labeled as a loop — it is structurally
  different from a forward data-flow and must read as such.
- Filterable by RE class (the secondary agent facet, §14.E). Counts strip sits
  beneath, not above.
- Responsive: on narrow widths the SVG scrolls within its card (inherits M6
  in-card scroll); it does not force page-level horizontal scroll (GROK minor).

## 15.H — Attestation-log seam: config-driven (GROK #5; closes §13-Q4)
`portfolio-core`'s `action_log` is **configured, not subclassed**, per domain:
- domain passes a **verb vocabulary** (`acknowledge·escalate·gate·suppress·
  override·remediate·certify` for ATG vs `gate·accept·escalate·dispo·
  require_eval·restrict_scope` for finance) + an optional `evidence_id` field in
  the entry schema.
- The hash-chain, `verify_chain()`, the ≥12-word + named-human + expiry rules are
  **identical and shared** (the fixed core). So the "attestation log" is literally
  the shared action log with a domain verb set — a config, made structural (§14.D).

## 15.I — Name the costume (Claude #4 — honesty, amends §7)
§7 must state plainly: **SIGNAL and PROPAGATE are two views of one gesture** in
this domain (a signal *is* its RE class; there is no finance-style multi-signal
confluence). They are retained as two acts **for portfolio IA consistency — a
presentation choice, not a claim that this domain has five native stages.** Say
it so it cannot be mistaken for a structural rigor. (The 5-act spine still ships;
the honesty is in naming why.)

## 15.J — Viewer-vs-tool stoppability (Claude #5 — amends §14.I)
`treatment{}` is `absent` until Stage 4 populates it from real attestation
entries (§14.A.1). Therefore: **Stages 0–3 produce a read-only VIEWER; the
artefact becomes a governance INSTRUMENT only at Stage 4.** The §11 stoppability
claim must carry this qualifier — *Stage 3 is a stoppable viewer; Stage 4 is the
first stoppable tool* — so no stakeholder stops at Stage 3 thinking they have a
governance tool when they have a renderer. (Answers §0.5: no stage secretly
requires a later one, but the *value proposition* requires Stage 4 — said plainly.)

## 15.K — Synthetic-input surfacing (GROK #6 + Claude)
Beyond the one-time banner (§10.4): the **records-exposed magnitude and any
lineage node/edge count carry an inline `synthetic_input` chip on the number
itself.** These are the figures a reader quotes out of context; the simulator's
6-deterministic-scenario floor (§14.G) is disclosed at the point of the number,
not only at the page top.

## 15.L — Minor (GROK)
- **Keyboard nav + command palette** inherit from `portfolio-core` (j/k, verb
  shortcuts) — part of the lifted presentation, no new work.
- **No GitHub push until Stage 0 is green** (the §15.D gate passes) — explicit
  enforcement, extends the standing distribution discipline.

---

## Spec status: LOCKED (v2.1)

Both big bets survived two review rounds (4-lens + GROK/Claude). §14 + §15 are the
operative amendments; the architecture is sound and frozen. **Execution order:**
1. **Stage 0** — shared-core extraction (§15.D/E/F), extracting the fixed
   (`822d819`) action-log core, project 1 held to 39/0 + pixel-identical + the
   three integrity behaviors. No agent-trace-gov change, no push.
2. **Stages 2–5** — adapter + projection (§15.F table) → presentation
   (lineage-graph hero §15.G) → decision surface (§15.H) → honesty + polish.
No stage starts before the prior is signed off. No push without explicit OK.
