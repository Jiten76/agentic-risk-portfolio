# agent-trace-gov

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Governance for AI agents.** It watches what your agents actually did — every action, data
flow, and decision — and flags the governance failures: PII in an output, a missing consent
record, an action outside its remit, data leaving the boundary. Each flag is derived from real
trace rules (not a lookup), carries the evidence trail and a framework citation
(GDPR / EU AI Act / SOC 2 / NIST) to back it, and lands in a single-file dashboard whose every
number you can trace and re-check right in the browser.

> **🔎 Live demo:** _`<GitHub Pages link — added at publish>`_ · or generate it locally (below).
>
> **What's real vs. synthetic (read this first).** This is a **demonstrator**. The input
> agent traces are **synthetic** — produced by a deterministic simulator (`seed 42`, so any
> run reproduces byte-for-byte). Everything downstream is **real**: the risk classification,
> the framework mapping, and the integrity machinery — per-value provenance labelling, the
> SHA-256 hash-chained attestation log verified live in your browser, and the artefact seal.
> No proprietary data; no real customer PII. The dashboard states this in its own banner.

---

## The governance dashboard (v2)

A self-contained HTML artefact (no server, no external calls) built on a **render-from-data**
architecture: the Python pipeline emits an embedded projection JSON, and an in-browser runtime
hydrates every visible value from it — so what ships as evidence and what renders **cannot drift**.

It's organised as a five-act narrative, switchable by role (1LoD engineer / 2LoD exec / 3LoD audit):

| Act | Reads | Surfaces |
|-----|-------|----------|
| **SIGNAL** | what fired | posture hero + findings grouped by risk-event |
| **PROPAGATE** | how risk flows | the lineage-graph hero (agents → systems → external; RE-03 external edges lit, RE-08 loops dashed) |
| **IMPACT** | what's exposed | records/PII-flows-exposed magnitude + framework materiality |
| **DECIDE** | what to do | governance verbs behind a named-human ("A8") gate |
| **ATTEST** | prove it | SHA-256 hash-chained attestation log + regulatory precedent register |

**Integrity + honesty machinery (the point of the piece):**

- **Provenance on every value** — each number is tagged `counted` / `derived` / `published_standard`
  / `illustrative` / `absent`, and the UI shows it. A record count that isn't instrumented renders
  **absent** ("not instrumented"), never a fabricated 0.
- **Hash-chained attestation log** — SHA-256 over canonical JSON, chained genesis→head, **verified
  live in the browser** (the JS canonicalisation byte-matches the Python signer). Take an action in
  DECIDE and watch the chain re-verify.
- **Artefact seal** — a keyless SHA-256 checksum over the embedded projection, **recomputable
  in-browser** (the footer "verify ↪"). It proves the evidence payload is unmodified since seal-time
  and that rendering is deterministic from it — it is *not* a cryptographic signature (see the seal
  tooltip for its exact threat model).
- **Honest magnitude** — distinct PII-bearing / external lineage flows, **not** a dollar figure and
  **not** claimed as the GDPR Art. 33(1)(a) records quantity (that's marked absent).
- **Materiality reserved to Legal** — framework triggers surface facts (GDPR Art. 33/5/32/6(1)(a),
  EU AI Act Art. 14/12/26 *conditioned on the high-risk predicate*, GDPR Ch. V, SOC 2); the
  determination is explicitly reserved.

### Generate + view it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python3 -m utils.atg_html_report 16      # seed 42 → reproducible
open outputs/2026-06_atg_dashboard.html            # any modern browser; self-contained
```

Verify the substance gates (author-written smoke test, not assurance):

```bash
.venv/bin/python3 tools/audit_atg.py               # 50/50
```

---

## Why this exists

Agent systems shipping in 2025–2026 create actions that look like human-authored decisions but
lack the audit trail human-authored decisions carry. The standard answer — "we'll log everything"
— fails when the things worth knowing (who authorised what, which data crossed which boundary,
where consent was verified) aren't what default logs capture. The place to make agent actions
auditable is **design time**, not investigation time. This project is that design-time wrapper.

---

## Risk events

Severity is **consequence-derived per finding** (r56): the class value below is
only the floor; the classifier escalates or de-escalates from what the traces
show, and every rating carries its basis. The scale tops at demonstrated
unauthorized-*action* capability — an agent reaching an effectful tool (funds,
credit, outbound comms) out of scope is critical; a mandatory-notification data
event is high and wears its regulatory clock as an assessment; process gaps sit
below.

| Event                                | Default (floor) | Escalates to critical when…                          | Framework                       |
|--------------------------------------|-----------------|------------------------------------------------------|---------------------------------|
| PII detected in agent output         | High            | — (high iff external/unredacted; medium internal+redacted) | GDPR Art. 5; CCPA §1798.100     |
| Consent record missing               | High            | — (high iff the data egresses; medium internal)      | GDPR Art. 6(1)(a); CCPA §1798.120 |
| Unauthorized external data flow      | Critical        | PII + agent outside authorization (exfiltration shape); PII egress by an authorized agent is HIGH + Art. 33 clock | NIST CSF PR.DS-5                |
| Agent scope exceeded                 | High            | the out-of-scope action is effect-bearing (effectful tool · egress · record-store write · decision) | NIST AI RMF GOVERN-1            |
| Low-confidence automated decision    | Medium          | — (high without a human catch downstream; medium when routed to a human) | NIST AI RMF MEASURE-2           |
| Data-lineage break                   | Medium          | — (high on record-store writes — the 17a-4 shape)    | ISO 27001 A.8.2                 |
| Excessive data retention             | Medium          | — (dormant: no seeded scenario exercises this class) | GDPR Art. 5(e)                  |
| Multi-agent loop                     | Low             | — (medium when the cycle carries effect-bearing actions) | NIST AI RMF MANAGE-2            |

Full taxonomy + citations + real enforcement anchors: [data/action_schema.json](data/action_schema.json),
sourced in [SOURCES.md](SOURCES.md).

---

## Repository layout

```
agent-trace-gov/
├── graph/governance_graph.py   # LangGraph pipeline (run_governance_analysis_full)
├── data/
│   ├── agent_simulator.py      # deterministic synthetic workflow generator (seedable)
│   └── action_schema.json      # risk-event taxonomy + framework citations + incident anchors
├── utils/
│   ├── projection.py           # engine → projection adapter (the honesty disciplines live here)
│   ├── atg_html_report.py      # 5-act stage assembly + drift-free write
│   └── assets/                 # atg_domain.js (renderer) · atg_components.css (design)
├── tools/audit_atg.py          # 50 substance gates (projection + renderer + reproducibility)
├── ui/app.py                   # legacy Streamlit view (the HTML dashboard above supersedes it)
└── outputs/                    # generated dashboard + projection JSON
```

The shared render-from-data core (shell, runtime, hash-chained log, provenance) lives in a sibling
package, `portfolio-core`, imported by this project and by `risk-as-code-agent`.

---

## Connecting a real agent system (intended surface — not yet shipped)

Today the input is the synthetic simulator. The **intended** integration is a thin trace adapter
that normalises a framework's action stream (LangChain / CrewAI / AutoGen / custom) into the schema
in `data/action_schema.json`; the pipeline and dashboard are unchanged downstream. That adapter /
decorator API is **planned, not published** — this repo demonstrates the governance + evidence
layer on reproducible synthetic input.

---

## Regulatory context (2024–2026)

- **EU AI Act** (Reg. 2024/1689) — high-risk obligations phase in through 2026: logging of automated
  decisions, human oversight, data-governance records.
- **NIST AI RMF 1.0** (2023) + **GenAI Profile** (NIST AI 600-1, 2024).
- **SOC 2** Trust Service Criteria — findings map to CC6.1, CC6.6, CC9.2, P3.1, P6.1.

---

## License

[MIT](LICENSE).

## Author

[Jitendraa Joshii](https://linkedin.com/in/jitendraa-joshii-0b8ba51)
