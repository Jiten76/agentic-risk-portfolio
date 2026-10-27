# Sources & Grounding

Every threshold in `data/risk_patterns.json` carries a `threshold_source` and
`threshold_source_url`. Every pattern carries one or more `incident_reference`
entries pointing to a publicly documented post-mortem, regulator action, SEC
filing, or CVE record.

Citations span 2012 to 2026. The post-2024 weight reflects field shifts —
agentic-AI tool use, the post-CrowdStrike re-evaluation of release process,
EU AI Act and NIST AI RMF GenAI Profile enforcement — that a 2022-anchored
vocabulary cannot describe.

The intent is auditability. A second-line reviewer should be able to follow
each finding back to its source, recognise the pattern from real-world
experience, and disagree on substance rather than on legitimacy.

---

## Threshold sources

| Source | Year | Used by | URL |
|---|---|---|---|
| DORA 2024 — Accelerate State of DevOps | 2024 | RP-01 cluster boundaries | https://dora.dev/research/2024/dora-report/ |
| DORA 2025 — State of AI-assisted Software Development | 2025 | RP-01 AI-adoption nuance, RP-09 throughput/instability | https://dora.dev/research/2025/dora-report/ |
| Google SRE — Implementing SLOs | ongoing | RP-02 availability_pct, mttr_minutes | https://sre.google/workbook/implementing-slos/ |
| Google SRE — Alerting on SLOs | ongoing | RP-08 mean_time_to_detect (minutes-grain) | https://sre.google/workbook/alerting-on-slos/ |
| Google SRE — Four Golden Signals | ongoing | RP-11 saturation + latency | https://sre.google/sre-book/monitoring-distributed-systems/ |
| Google SRE — Postmortem Culture | ongoing | RP-12 repeat_incident_rate | https://sre.google/sre-book/postmortem-culture/ |
| Kubernetes Pod Security Standards (GA 1.25) | 2022→ | RP-03 admission_webhook_denials | https://kubernetes.io/docs/concepts/security/pod-security-standards/ |
| CISA BOD 22-01 (KEV remediation) | 2021 | RP-04 vuln_aging_days_p90 | https://www.cisa.gov/news-events/directives/bod-22-01-reducing-significant-risk-known-exploited-vulnerabilities |
| CISA BOD 19-02 (Critical/High SLAs) | 2019 | RP-04 critical_vuln_count | https://www.cisa.gov/news-events/directives/bod-19-02-vulnerability-remediation-requirements |
| CISA Zero Trust Maturity Model v2 | 2023 | RP-05 orphaned_account_count | https://www.cisa.gov/zero-trust-maturity-model |
| NIST CSF 2.0 | 2024 | All patterns — `nist_function` mapping; RP-07 GV.SC | https://www.nist.gov/cyberframework |
| NIST AI RMF 1.0 | 2023 | RP-10 baseline | https://www.nist.gov/itl/ai-risk-management-framework |
| NIST AI 600-1 — Generative AI Profile | Jul 2024 | RP-10 + RP-13 (prompt injection, data poisoning, confabulation) | https://www.nist.gov/itl/ai-risk-management-framework |
| NIST AI RMF — Critical Infrastructure Profile (concept) | Apr 2026 | RP-10 critical-infra context | https://www.nist.gov/itl/ai-risk-management-framework |
| EU AI Act (Reg. 2024/1689) | Aug 2024 in force; high-risk obligations phase to 2026 | RP-10 high-risk obligations | https://artificialintelligenceact.eu |
| Practical DevSecOps MCP Security Guide | 2025 | RP-13 anchor | https://www.practical-devsecops.com/mcp-security-guide/ |
| GDPR Article 33 | 2018 | RP-06 dlp_alert_count, pii_scan_findings | https://gdpr-info.eu/art-33-gdpr/ |
| IBM Cost of a Data Breach Report 2024 | 2024 | RP-08 dwell-time context | https://www.ibm.com/reports/data-breach |
| CIS Controls v8 | 2021 | RP-03 policy_violation_count | https://www.cisecurity.org/controls/cis-controls-list |

## Incident references (by date)

| Pattern | Anchoring incident | Date | Source |
|---|---|---|---|
| RP-01 Deployment | Knight Capital trading loss ($440M) | 2012-08-01 | SEC litigation 34-70694 |
| RP-01 / RP-09 | GitLab database outage | 2017-01-31 | GitLab postmortem |
| RP-04 / RP-06 | Equifax — Apache Struts (147.9M records) | 2017-09-07 | GAO-18-559 / FTC settlement |
| RP-11 | GitHub MySQL replication incident | 2018-10-21 | GitHub Engineering blog |
| RP-02 / RP-11 | Cloudflare regex outage | 2019-07-02 | Cloudflare blog |
| RP-03 | Capital One breach ($80M OCC fine) | 2019-07-19 | OCC consent order |
| RP-07 / RP-08 | SolarWinds SUNBURST | 2020-12-13 | CISA AA20-352A |
| RP-04 / RP-07 | Log4Shell (CVE-2021-44228) | 2021-12-10 | NVD |
| RP-10 | Zillow Offers wind-down ($304M write-down) | 2021-11-02 | SEC shareholder letter |
| RP-02 | AWS US-EAST-1 outage | 2021-12-07 | AWS public message |
| RP-05 | Okta — Lapsus$ third-party compromise | 2022-01-21 | Okta security advisory |
| RP-12 | Atlassian 14-day Cloud outage | 2022-04-04 | Atlassian PIR |
| RP-05 | Uber MFA-fatigue breach | 2022-09-15 | Uber newsroom |
| RP-06 | T-Mobile 37M records | 2023-01-19 | T-Mobile disclosure |
| RP-01 / RP-07 | CrowdStrike Falcon — ~8.5M Windows systems | 2024-07-19 | CrowdStrike PIR + CISA |
| RP-13 | Tool-mutation / rug-pull pattern (Simon Willison) | 2025-04-09 | simonwillison.net |
| RP-13 | CVE-2025-49596 — MCP Inspector RCE (CVSS 9.4) | 2025-06-01 | NVD |
| RP-07 / RP-13 | First malicious MCP package on public registries | 2025-09-01 | Authzed MCP breaches timeline |
| RP-10 | NIST AI RMF Critical Infrastructure Profile (concept note) | 2026-04-07 | NIST |

## Why the timeframe spans 2012–2026

A vocabulary anchored to 2022 would miss three field shifts between 2023 and
2026:

1. Release-process expectations after CrowdStrike (2024-07-19). A single
   security-vendor content update reached ~8.5M Windows machines before any
   regional canary surfaced the defect. Phased rollout for global-blast-radius
   changes moved from "best practice" to industry default.
2. The agentic-AI tool-use surface (2024–2026). MCP launched late 2024;
   Practical DevSecOps MCP Security Guide followed in 2025; CVE-2025-49596 (MCP Inspector RCE,
   CVSS 9.4) and the first malicious MCP package on public registries landed
   within months. Prompt injection, tool poisoning, and tool mutation are
   documented incident classes, not hypotheticals. RP-13 covers this
   ground; the 2022 vocabulary did not.
3. EU AI Act / NIST AI 600-1 enforcement convergence (2025–2026). 2026 is
   the year high-risk obligations under the EU AI Act phase in, and the
   year the NIST AI RMF Critical Infrastructure Profile concept was
   released (Apr 2026).

## Calibration

Thresholds are starting points, not mandates. Two reviewers can legitimately
disagree on whether `change_failure_rate` should fire at 15% (DORA Medium) or
10% (DORA High). The point of the citation is to keep that disagreement
substantive.

A production deployment will typically:

1. Replace defaults with the appetite negotiated between first and second
   lines.
2. Add internal incident references alongside the public ones — public
   incidents are the floor, not the ceiling.
3. Drop signals it cannot actually measure.

## Reporting an error

If a threshold or citation is wrong, open an issue with the source that
contradicts it. Corrections are high-priority.
