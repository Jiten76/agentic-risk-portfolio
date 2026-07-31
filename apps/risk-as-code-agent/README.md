# risk-as-code-agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Turns engineering and infrastructure telemetry into the risk picture an auditor
expects: what's exposed, how bad, what to fix first, and which regulations it
touches. Every threshold is anchored to a published standard (DORA 2024–2025,
Google SRE, CISA, NIST CSF 2.0, NIST AI 600-1, OWASP MCP Top 10) — never a gut
call dressed as data; see [SOURCES.md](SOURCES.md) for the full citation table.
Synthetic telemetry today, built to attach to Prometheus/OTel in production.
Under the hood: a four-agent LangGraph pipeline.

---

## Why this exists

Every major fintech and platform failure of the last decade was *describable
in retrospect* through telemetry that was visible at the time:

- Knight Capital, 2012-08-01 — a deployment that activated dormant code; $440M
  lost in ~45 minutes; the firm did not survive the week.
- Cloudflare, 2019-07-02 — a single WAF rule with catastrophic regex
  backtracking spiked CPU to 100% across the global edge in seconds.
- AWS US-EAST-1, 2021-12-07 — automated scaling triggered network congestion
  for ~9 hours; downstream impact across most of consumer fintech.
- Atlassian Cloud, 2022-04 — a scripted maintenance job deleted ~775 customer
  sites; some took 14 days to restore.
- CrowdStrike Falcon, 2024-07-19 — a content update crashed ~8.5M Windows
  systems. Largest IT outage in recorded history.

In each case, the *signals were there*. What was missing was a structured way
to convert those signals into evidence a second-line reviewer or board could
read fast enough to act on. Spreadsheet-driven attestation cannot bridge that
gap at hyperscale — by the time the spreadsheet comes back, the system state
it described no longer exists.

This project is one attempt at that bridge.

---

## The pipeline

```
telemetry (Prometheus / OTel / synthetic)
        │
        ▼
[Ingestion]   collects per-domain snapshots
        │
        ▼
[Mapping]     evaluates signals against 13 risk patterns
                  (NIST CSF 2.0 / DORA / ISO 31000 / NIST AI RMF)
        │
        ▼
[Evidence]    generates narrative per finding (Anthropic Claude or mock)
        │
        ▼
[Attestation] produces JSON report + per-domain PDF one-pager
```

Every finding traces back to a specific signal, threshold, and source
citation. Thresholds disagree with you on substance, not on legitimacy.

---

## Grounding (2012–2026)

This is a demo with synthetic telemetry. The risk language is not invented.
Each pattern carries:

- `threshold_source` — the published baseline behind each green/amber/red
  boundary (DORA 2024+2025, Google SRE workbook, CISA BOD 22-01/19-02,
  Kubernetes Pod Security Standards, NIST AI 600-1 GenAI Profile, OWASP MCP
  Top 10, GDPR Art. 33, EU AI Act 2024/1689).
- `incident_reference` — at least one publicly documented post-mortem,
  regulator action, SEC filing, or CVE record per pattern.

The 2012–2026 timeframe is deliberate. A 2022-grounded vocabulary would have
missed three shifts that re-shaped the field:

1. Phased rollout for global-blast-radius changes moved from "best practice"
   to industry default after CrowdStrike 2024-07-19.
2. The MCP / agentic-tool surface became a real source of incidents — first
   malicious MCP package on public registries (Sept 2025), CVE-2025-49596
   (MCP Inspector RCE, CVSS 9.4), the Simon Willison tool-mutation/rug-pull
   analysis. RP-13 was added to cover this; it has no clean 2022 analogue.
3. EU AI Act high-risk obligations and the NIST AI 600-1 GenAI Profile made
   2026 the decisive compliance year for AI in regulated workflows.

Full citation table: [SOURCES.md](SOURCES.md).

---

## Repository layout

```
risk-as-code-agent/
├── graph/
│   └── risk_graph.py        # LangGraph pipeline (entry point)
├── agents/                  # Per-agent logic
├── data/
│   ├── risk_patterns.json   # 14 patterns with thresholds + sources + incidents
│   ├── service_catalog.json # Generic fintech service topology
│   └── mock_metrics.py      # Synthetic telemetry generator (3 scenarios)
├── utils/
│   ├── llm_client.py        # Anthropic Claude + mock fallback
│   └── pdf_generator.py     # PDF one-pager export
├── ui/
│   └── app.py               # Streamlit dashboard
└── outputs/                 # Generated evidence
```

### Pipeline stages

| Stage         | Input               | Output                                         |
|---------------|---------------------|------------------------------------------------|
| Ingestion     | Scenario config     | Raw telemetry snapshot per domain              |
| Mapping       | Telemetry snapshot  | Pattern hits with RAG status per domain        |
| Evidence      | Pattern hits        | Narrative per finding (LLM or mock)            |
| Attestation   | Evidence items      | JSON report + per-domain PDF                   |

### Risk pattern taxonomy

| ID    | Pattern                              | NIST function |
|-------|--------------------------------------|---------------|
| RP-01 | Deployment & Release                 | PR.IP         |
| RP-02 | Availability & Resilience            | RC.RP         |
| RP-03 | Policy-as-Code Compliance            | PR.PT         |
| RP-04 | Vulnerability & Patch                | RS.MI         |
| RP-05 | Access & Identity                    | PR.AC         |
| RP-06 | Data & Privacy                       | PR.DS         |
| RP-07 | Third-Party & Supply Chain           | GV.SC         |
| RP-08 | Observability & Detection            | DE.CM         |
| RP-09 | Change Management                    | PR.IP         |
| RP-10 | AI & Model                           | GV.RM         |
| RP-11 | Capacity & Performance               | PR.PT         |
| RP-12 | Incident & Recovery                  | RC.CO         |
| RP-13 | Agentic AI & Tool-Use (MCP)          | GV.RM         |

---

## Quickstart

Docker:

```bash
git clone https://github.com/Jiten76/risk-as-code-agent
cd risk-as-code-agent
cp .env.example .env          # optionally add ANTHROPIC_API_KEY
docker compose up
```

Open http://localhost:8501.

Local Python:

```bash
git clone https://github.com/Jiten76/risk-as-code-agent
cd risk-as-code-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run ui/app.py
```

Headless:

```bash
python graph/risk_graph.py                     # default scenario
python -c "
from graph.risk_graph import run_risk_assessment
import json
print(json.dumps(run_risk_assessment(scenario_map={
    'trading': 'degraded',
    'payments': 'incident',
    'custody': 'normal',
    'identity': 'normal',
    'platform': 'normal',
}), indent=2))
"
```

**The evidence artifact (v2.0a dashboard).** The canonical, shareable output is a
self-contained, render-from-data HTML dashboard. Its exposure axis is the corrected
**frequency × severity** model (`utils/exposure.py`) — *not* the retracted v1.3 flat
`$/red` model (that renderer is archived; see `utils/html_report.py`). The Streamlit
"Generate HTML report" button produces this dashboard; or headless:

```python
from graph.risk_graph import run_risk_assessment
from utils.v2_html_report import write_v2_report
from pathlib import Path
sm = {'payments': 'incident', 'trading': 'degraded', 'platform': 'degraded',
      'custody': 'normal', 'identity': 'normal'}
print(write_v2_report(run_risk_assessment(scenario_map=sm),
                      Path('outputs/v2_0a/current.html')))  # → open in any browser
```

---

## LLM modes

| Mode      | Config                                          | Behavior                                    |
|-----------|-------------------------------------------------|---------------------------------------------|
| Mock      | `LLM_MODE=mock` (default if no key)             | Offline. Rule-based narrative. CI-friendly. |
| Anthropic | `LLM_MODE=anthropic` + `ANTHROPIC_API_KEY=…`    | Claude Sonnet 4 for narrative + summaries.  |

Mock mode is honest about being a demo. It does not pretend to be the
Anthropic-backed output; the narrative is short, deterministic, and tagged.

---

## Output

The Streamlit dashboard renders:

- Domain risk heatmap (5 domains, RAG status)
- Per-domain findings with evidence narratives
- Signal-level drill-down with threshold context and source citation
- PDF one-pager export per domain

The PDF one-pager structure:

```
─────────────────────────────────────────────────────────────
 risk-as-code-agent  ·  Evidence one-pager
 Domain: Payments & Transfers   Period: 2025-Q2
─────────────────────────────────────────────────────────────
 Overall posture: RED — exceeds appetite
 8 Red findings · 17 Amber findings · 14 patterns assessed
─────────────────────────────────────────────────────────────
 Executive summary
   …
 Findings
   [RED]   RP-02 Availability   mttr=185min, avail=98.8%
   [RED]   RP-01 Deployment     change_failure=28%
   [AMBER] RP-04 Vuln & Patch   aging_p90=55d
 Attestation
   Based on telemetry-backed evidence for 2025-Q2 …
   2LoD Reviewer: _________________   Date: ________
   Domain Owner:  _________________
─────────────────────────────────────────────────────────────
```

The JSON report is the same content in structured form — methodology,
framework alignment, per-domain findings, signal values, citations. Suitable
for ingestion into IRM platforms (ServiceNow, Archer, LogicGate).

---

## Design choices

**Read-only.** The framework observes and reports; it does not write back to
engineering systems. This is what preserves second-line independence.

**Traceability over opinion.** Every finding links to a specific metric, the
threshold it threshold exceedanceed, and the source the threshold came from. There is no
"because I said so" in the report.

**Mock by default.** Runs end-to-end without an API key or live infrastructure.
This is partly for CI and onboarding, and partly because demos that *require*
production data hide more than they show.

**Calibratable.** Thresholds are starting points cited to sources. A real
deployment negotiates them with first-line and second-line and replaces the
defaults. The point of the source citation is to make the disagreement
substantive.

---

## Extending

Add a pattern: edit `data/risk_patterns.json` following the existing schema.
The mapping and evidence stages pick it up automatically.

Connect Prometheus: replace `generate_multi_domain_snapshot()` in
`data/mock_metrics.py` with a real query client; keep the return shape.

```python
from prometheus_api_client import PrometheusConnect
prom = PrometheusConnect(url="http://your-prometheus:9090")
# Query your actual metrics; return in the same per-domain schema.
```

Push to an IRM: the `run_risk_assessment()` return value is plain JSON.

```python
report = run_risk_assessment(scenario_map=scenario_map)
requests.post("https://your-irm/api/findings", json=report)
```

---

## Contributing

Corrections to citations are
high-priority — if a threshold or incident reference is wrong, open an issue
with the source that contradicts it.

## License

MIT.

## Author

[Jitendraa Joshii](https://linkedin.com/in/jitendraa-joshii-0b8ba51).
