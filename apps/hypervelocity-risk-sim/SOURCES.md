# SOURCES — what backs the `source_derived` scenario shapes

The three scenarios replay the *shape* of public, well-documented failure modes.
The shapes are `source_derived` from the public reporting below; the specific
numbers a run produces are seeded-synthetic, and the spreadsheet-vs-signal
response-time gap is `operator_calibrated` illustration (labelled per value in the
dashboard and in `data/risk_events.json`), **not** measured telemetry from any firm.

## HV-01 · Consumer-Lag Cascade (Kafka lag storm)
The shape: a consumer-rate degradation (slow partition / rebalance) lets a backlog
integrate from a small sustained producer−consumer deficit, cascading into a
payments error-rate spike and an availability SLO violation.
- Confluent / Apache Kafka docs — consumer lag as `∫(produce − consume)`; lag as the
  canonical saturation signal. <https://docs.confluent.io/platform/current/kafka/monitoring.html>
- Google SRE Book — "Monitoring Distributed Systems" (the four golden signals;
  saturation & latency). <https://sre.google/sre-book/monitoring-distributed-systems/>
- The generic market-open message-queue overload pattern is widely reported across
  consumer-fintech outages; this simulator replays the shape, not any one firm's incident.

## HV-02 · Change-Induced Cascade (bad deployment → rollback)
The shape: a bad release at the deployed service carries the highest error;
downstream impact decays with dependency distance; circuit breakers trip; an
emergency rollback and a recovery tail follow. Change failure rate is a *leading*
indicator if you watch it.
- **Knight Capital**, 2012-08-01 — a deployment that activated dormant code; ~US$440M
  in ~45 minutes. SEC Release 34-70694. <https://www.sec.gov/litigation/admin/2013/34-70694.pdf>
- **GitLab.com**, 2017-01-31 — database incident + postmortem (change-induced, public
  writeup). <https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/>
- **CrowdStrike**, 2024-07-19 — a content-update change cascaded to ~8.5M Windows hosts;
  public post-incident review. <https://www.crowdstrike.com/falcon-content-update-remediation-and-guidance-hub/>
- DORA / Accelerate — change failure rate as a core delivery metric.
  <https://dora.dev/guides/dora-metrics-four-keys/>

## HV-03 · Transaction-Velocity Surge / Fraud-Control Response
The shape: a transaction-rate surge trips fraud detection, which also blocks
legitimate traffic; the elevated-velocity signal is *routed to an AML review queue
for human disposition* — a fraud-control signal, **not** a BSA/AML determination.
The simulator makes no money-laundering or SAR/CTR-filing assertion; 31 CFR 1020 is
out of scope. It illustrates the fraud/compliance ownership seam (different teams,
different SLAs).
- NIST AI RMF — MEASURE 2 (measuring trustworthiness of automated decisioning).
  <https://www.nist.gov/itl/ai-risk-management-framework>
- EU AI Act (Reg. 2024/1689) Art. 14 — human oversight; **binds only high-risk AI
  systems** under Art. 6 / Annex III (a predicate this simulator does not establish).
  <https://artificialintelligenceact.eu/article/14/>
- FinCEN / BSA context (for scope-boundary clarity only — the simulator asserts none
  of it): 31 CFR 1020, SAR/CTR obligations. <https://www.fincen.gov/resources/statutes-regulations>
