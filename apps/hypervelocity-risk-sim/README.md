# hypervelocity-risk-sim

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A simulator that replays three fintech failure modes — a Kafka queue backing up,
a bad release cascading, a transaction surge tripping fraud controls — and shows,
minute by minute, how much faster an instrumented, automated team detects, responds,
and reaches audit-ready evidence than a manual one.

The point isn't to claim automation prevents the incident. It's to make the
response-time gap concrete enough to argue about — and honest: every minute figure
is operator-calibrated *illustration*, not measured telemetry.

---

## What it simulates

Three scenarios, each modelled on a recognisable real-world pattern:

**Kafka lag storm.** Consumer lag accumulates from a sustained producer-minus-
consumer rate deficit (120 → several-thousand messages), then cascades into a
payments-domain error-rate spike and an availability SLO violation. This is the classic market-open overload shape —
backed-up message queues during a volume surge, then visible payment
failures, then a visible SLO violation. It's a well-documented public pattern
across consumer-fintech outages; this simulator replays the *shape*, not any
one firm's incident.

**Deployment cascade.** A bad release propagates across six interdependent
services, triggers circuit breakers, then emergency rollbacks. This is the
generic shape of every change-induced cascade post-mortem — Knight Capital
2012 ($440M, 45 minutes), GitLab 2017, CrowdStrike 2024 (8.5M Windows
systems). Change failure rate is a *leading* indicator if you look at it that
way; it shows up as a *lagging* indicator if you don't.

**Transaction-velocity / fraud-control response.** Transaction rate spikes to 8×
baseline, triggering fraud detection and blocking legitimate traffic. The
elevated-velocity signal is *routed to an AML review queue for human
disposition* — a fraud-control signal, **not** a BSA/AML determination (the
simulator makes no money-laundering or SAR/CTR-filing assertion; 31 CFR 1020 is
out of scope). It's the risk/compliance intersection: one signal must route to
fraud and compliance teams that own different SLAs.

---

## The comparison

For each scenario the simulator runs the same event stream through two response
regimes — **manual / checklist** vs **instrumented + automated**. The ranges below
are *operator-calibrated illustration* (not measured telemetry, not benchmark
claims); they model a **competent** manual baseline against automation (a believable
few-fold gap, not a strawman — automation is imperfect too). The **authoritative
per-value figures and their provenance live in the sealed `docs/projection.json`**
under the SHA-256 seal, and render in the dashboard's COMPARE act. The gap reflects
tooling + automation + governance *combined*, not governance discipline alone.

| Dimension          | Manual / checklist  | Instrumented + automated |
|--------------------|---------------------|--------------------------|
| Detection          | 10–12 min           | 2 min                    |
| Escalation         | 20–22 min           | 4–5 min                  |
| Evidence-ready     | 85–100 min          | 10–12 min                |
| Human effort       | 4–4.5 hours         | 0.7–1 hour               |
| Missed events      | ~10% of events      | ~1.5%                    |
| False positives    | 2–4                 | 1                        |
| Audit trail        | Manual notes + logs | Full event trace         |

The "missed events" row is a *derived* figure, not pure illustration:
`round(event_count × ~0.10)` over the seeded stream — the count is real, the
miss-fraction is operator-calibrated (a competent checklist reviewer still sees
~1-in-10 events after the relevant window has closed during a storm). The automated
regime carries a small non-zero false-positive / miss cost too — real instrumented
response isn't perfect.

---

## Quickstart

```bash
git clone https://github.com/Jiten76/hypervelocity-risk-sim
cd hypervelocity-risk-sim
docker compose up
# → http://localhost:8503
```

Local:

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

No API key. No live infrastructure. Pure synthetic event generation.

---

## Using it

1. Select a scenario in the sidebar.
2. Click "Run Simulation".
3. Review the side-by-side comparison.
4. Drill into the event stream to see individual signals.
5. Note which risk patterns from `risk-as-code-agent` (RP-01 through RP-13)
   would fire.

---

## Reproducibility

Scenarios are stochastic by default — each run is a fresh instance of the failure
*shape*. Pass a `seed` for **byte-reproducible** output (the RNG and the timestamp
clock are both pinned), matching the platform's reproducibility discipline and
required for the attestation seal the render-from-data dashboard will carry:

```python
from simulator.event_generator import run_scenario
events, summary = run_scenario("kafka_lag_storm", seed=42)   # identical every run
```

---

## Extending

A new scenario is a function in `simulator/event_generator.py` returning a
`List[Dict]` of event records:

```python
def generate_cert_expiry_cascade(hours_before: int = 2) -> List[Dict]:
    # Generate events for an impending certificate expiry
    # cascading into auth-service failures.
    ...
```

Real event streams replace the generator. Same schema, real source:

```python
from kafka import KafkaConsumer
# Subscribe to your metrics topic; feed the same schema.
```

---

## Related

- [risk-as-code-agent](https://github.com/Jiten76/risk-as-code-agent) — the
  governance framework whose response model this simulator validates.
- [agent-trace-gov](https://github.com/Jiten76/agent-trace-gov) —
  traceability for agentic systems.

Read together: `hypervelocity-risk-sim` generates the event;
`risk-as-code-agent` governs it; `agent-trace-gov` traces it.

---

## License

MIT.

## Author

[Jitendraa Joshii](https://linkedin.com/in/jitendraa-joshii-0b8ba51).
