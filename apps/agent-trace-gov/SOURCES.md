# Sources & Grounding

Every risk event in `data/action_schema.json` carries a `framework_source_url`
and one or more `incident_reference` entries pointing to a publicly documented
post-mortem, regulator action, or CVE record. The goal is auditability: a
reviewer should be able to follow each finding back to its source, recognise
the pattern from real-world experience, and disagree on substance rather than
on legitimacy.

Citations span 2017 to 2026, weighted toward 2023–2026 to cover the agentic
era — Redis bug PII leak (Mar 2023), Samsung ChatGPT data leak (Apr 2023),
the Air Canada chatbot liability ruling (Feb 2024), CVE-2025-49596 (MCP
Inspector RCE), and the first malicious MCP package on public registries
(Sept 2025).

---

## Framework sources

| Source | Used by | URL |
|---|---|---|
| GDPR Art. 5 (lawfulness, fairness, transparency; storage limitation) | RE-01, RE-07 | https://gdpr-info.eu/art-5-gdpr/ |
| GDPR Art. 6 (lawfulness of processing; valid legal basis) | RE-02 | https://gdpr-info.eu/art-6-gdpr/ |
| CCPA §1798.100 (right to know) | RE-01 | https://oag.ca.gov/privacy/ccpa |
| CCPA §1798.120 (right to opt out) | RE-02 | https://oag.ca.gov/privacy/ccpa |
| NIST CSF 2.0 PR.DS-5 (data leak protection) | RE-03 | https://www.nist.gov/cyberframework |
| NIST AI RMF 1.0 — GOVERN-1 | RE-04 | https://www.nist.gov/itl/ai-risk-management-framework |
| NIST AI RMF 1.0 — MEASURE-2 | RE-05 | https://www.nist.gov/itl/ai-risk-management-framework |
| NIST AI RMF 1.0 — MANAGE-2 | RE-08 | https://www.nist.gov/itl/ai-risk-management-framework |
| NIST AI 600-1 GenAI Profile (Jul 2024) | cross-cutting | https://www.nist.gov/itl/ai-risk-management-framework |
| ISO/IEC 27001:2022 A.8.13 | RE-06 | https://www.iso.org/standard/27001 |
| EU AI Act (Reg. 2024/1689) | cross-cutting | https://artificialintelligenceact.eu |
| Practical DevSecOps MCP Security Guide (2025) | RE-04, RE-08 | https://www.practical-devsecops.com/mcp-security-guide/ |
| SOC 2 Trust Service Criteria | CC6.1, CC6.6, CC9.2, P3.1, P6.1 | https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2 |

## Incident references (by date)

| Event | Anchoring incident | Date | Source |
|---|---|---|---|
| RE-03 | Capital One — SSRF to AWS metadata, $80M OCC fine | 2019-07-19 | OCC consent order |
| RE-05 | Zillow Offers — model drift, $304M write-down | 2021-11-02 | SEC shareholder letter |
| RE-07 | Amazon — CNPD €746M GDPR fine (Luxembourg) | 2021-07-30 | CNPD (Luxembourg) enforcement decision; Amazon 10-Q corroboration |
| RE-06 | Atlassian Cloud — 14-day partial outage | 2022-04-04 | Atlassian PIR |
| RE-02 | Meta — Irish DPC €390M for Article 6 violation | 2023-01-04 | DPC announcement |
| RE-01 | ChatGPT — Redis bug exposed conversation titles + payment metadata | 2023-03-20 | OpenAI postmortem |
| RE-01 / RE-03 | Samsung — semiconductor source code pasted into ChatGPT | 2023-04-30 | Samsung internal ban (TechCrunch coverage) |
| RE-05 | Moffatt v. Air Canada — airline liable for chatbot hallucination | 2024-02-14 | BC Civil Resolution Tribunal |
| RE-04 | Tool-mutation / rug-pull pattern (Simon Willison) | 2025-04-09 | simonwillison.net |
| RE-04 | CVE-2025-49596 — MCP Inspector RCE (CVSS 9.4) | 2025-06-01 | NVD |
| RE-08 | MCPTox benchmark — most agents vulnerable to tool-output prompt injection | 2025-08-01 | Practical DevSecOps |

## Why the timeframe weights 2023–2026

The agent-trace-gov pattern category is dominated by post-2022 incidents
because the surface itself is post-2022:

- **ChatGPT Mar 20 2023** established that agent backends can leak PII at
  scale through ordinary infrastructure bugs (a redis-py race), not just
  through model-output leakage. This is the canonical "shared cache + agent
  output" failure.
- **Samsung Apr 2023** showed that the most common agent-data egress today
  is not a malicious actor — it is an authorised engineer pasting code into
  a third-party model service. Egress controls have to assume good intent
  and still catch it.
- **Meta DPC Jan 2023** + the EU AI Act phase-in make 2026 the year consent
  capture moves from "good practice" to "regulator-enforced control".
- **Air Canada Feb 2024** is the first ruling that bit a deployer for
  agent confidence. Chatbot output is now legally a company statement;
  RE-05 ("Low-confidence automated decision") is the audit-trail you need
  if the next ruling lands harder.
- **MCP CVE-2025-49596 + first malicious MCP package Sept 2025** moved
  agent-tool risk from theoretical to documented. RE-04 ("Agent scope
  exceeded") and RE-08 ("Multi-agent loop") have real incident classes now.

## Calibration

The severity tier on each RE event is the floor for an audit-defensible
default — not a mandate. A production deployment should:

1. Re-rank severity against local regulatory exposure (e.g., RE-02 may be
   "critical" not "high" in a GDPR-regulated workflow).
2. Add internal incident references alongside the public ones.
3. Drop or split risk events that don't map to the actual agent
   architecture in scope.

## Reporting an error

If a citation is wrong, open an issue with the source that contradicts it.
Corrections are high-priority.
