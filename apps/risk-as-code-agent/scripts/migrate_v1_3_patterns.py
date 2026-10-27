"""
One-shot migration: add cascade_to / cascade_from / materiality_trigger to
each pattern in data/risk_patterns.json. Idempotent.

Run from repo root:
    python scripts/migrate_v1_3_patterns.py
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATTERNS_FILE = REPO / "data" / "risk_patterns.json"

# Cascade graph — engineering-defensible, each edge cites the canonical incident
# (or the cited threshold source) that establishes the link.
CASCADE_EDGES = {
    "RP-01": {
        "cascade_to": [
            {"pattern_id": "RP-02", "strength": "high",
             "rationale": "Bad deploy crashes service or degrades SLO (CrowdStrike 2024-07-19; Knight Capital 2012-08-01)"},
            {"pattern_id": "RP-12", "strength": "medium",
             "rationale": "Repeated deployment failures elevate repeat-incident rate and erode RTO confidence"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-09", "strength": "high",
             "rationale": "Emergency changes bypass review and drive deploy failure rate up (GitLab 2017-01-31)"},
            {"pattern_id": "RP-08", "strength": "low",
             "rationale": "Observability gaps delay detection of bad deploys, extending blast radius"},
        ],
    },
    "RP-02": {
        "cascade_to": [
            {"pattern_id": "RP-12", "strength": "high",
             "rationale": "Availability breaches feed repeat-incident rate and RTO breach count (Atlassian 2022 14-day outage)"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-01", "strength": "high",
             "rationale": "Deploy regressions are the most common availability root cause"},
            {"pattern_id": "RP-11", "strength": "high",
             "rationale": "Capacity saturation = outage (Cloudflare 2019-07-02 regex CPU exhaustion)"},
            {"pattern_id": "RP-08", "strength": "medium",
             "rationale": "Detection gaps extend availability breach duration (SolarWinds — 9-month dwell time)"},
        ],
    },
    "RP-03": {
        "cascade_to": [
            {"pattern_id": "RP-06", "strength": "high",
             "rationale": "Policy gaps allow misconfigurations to expose data (Capital One 2019-07-19 WAF SSRF)"},
            {"pattern_id": "RP-05", "strength": "medium",
             "rationale": "Missing admission policy lets over-privileged identities enter production"},
        ],
        "cascade_from": [],
    },
    "RP-04": {
        "cascade_to": [
            {"pattern_id": "RP-07", "strength": "medium",
             "rationale": "Critical CVEs in shared libraries cascade through SBOM (Log4Shell 2021-12-10)"},
            {"pattern_id": "RP-06", "strength": "medium",
             "rationale": "Unpatched vulnerabilities exploited to access PII (Equifax 2017-09-07, CVE-2017-5638)"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-07", "strength": "medium",
             "rationale": "Third-party vendor CVEs land in the patch backlog (SolarWinds, MOVEit)"},
            {"pattern_id": "RP-08", "strength": "low",
             "rationale": "Observability gaps hide vulnerable asset inventory"},
        ],
    },
    "RP-05": {
        "cascade_to": [
            {"pattern_id": "RP-06", "strength": "high",
             "rationale": "Excess access = data breach blast radius (Uber 2022-09-15 MFA fatigue; Capital One 2019)"},
            {"pattern_id": "RP-13", "strength": "medium",
             "rationale": "Over-scoped tokens cascade into agent tool misuse (MCP rug-pull pattern)"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-03", "strength": "medium",
             "rationale": "Policy gaps allow standing-privileged access patterns"},
        ],
    },
    "RP-06": {
        "cascade_to": [],
        "cascade_from": [
            {"pattern_id": "RP-05", "strength": "high",
             "rationale": "Most PII breaches are access-control failures upstream"},
            {"pattern_id": "RP-04", "strength": "medium",
             "rationale": "CVE exploitation → data exfiltration (Equifax)"},
            {"pattern_id": "RP-13", "strength": "high",
             "rationale": "Agentic AI processes PII through unauthorized external endpoints (Samsung 2023-04-30)"},
            {"pattern_id": "RP-03", "strength": "high",
             "rationale": "Missing data-handling policy lets PII flow unchecked (Capital One)"},
        ],
    },
    "RP-07": {
        "cascade_to": [
            {"pattern_id": "RP-04", "strength": "medium",
             "rationale": "Vendor CVEs become patch obligations (SolarWinds 2020-12, Log4Shell)"},
            {"pattern_id": "RP-01", "strength": "low",
             "rationale": "Compromised vendor releases (CrowdStrike 2024-07-19) become deploy events"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-13", "strength": "medium",
             "rationale": "Malicious MCP packages enter the agent-tool supply chain (Sept 2025)"},
        ],
    },
    "RP-08": {
        "cascade_to": [
            {"pattern_id": "RP-02", "strength": "medium",
             "rationale": "Detection gaps extend outage duration (IBM 2024 — 258-day breach lifecycle)"},
            {"pattern_id": "RP-04", "strength": "low",
             "rationale": "Can't patch what you can't see — asset-inventory gaps"},
            {"pattern_id": "RP-01", "strength": "low",
             "rationale": "Deploy regressions go un-noticed until customer-visible"},
        ],
        "cascade_from": [],
    },
    "RP-09": {
        "cascade_to": [
            {"pattern_id": "RP-01", "strength": "high",
             "rationale": "Emergency changes drive deploy failure rate (GitLab 2017-01-31)"},
            {"pattern_id": "RP-12", "strength": "medium",
             "rationale": "Unreviewed changes increase post-incident workload"},
        ],
        "cascade_from": [],
    },
    "RP-10": {
        "cascade_to": [
            {"pattern_id": "RP-06", "strength": "medium",
             "rationale": "Model drift in production touches PII boundaries (Zillow 2021-11-02)"},
            {"pattern_id": "RP-13", "strength": "high",
             "rationale": "Untrustworthy models in agentic context amplify tool-use risk"},
        ],
        "cascade_from": [],
    },
    "RP-11": {
        "cascade_to": [
            {"pattern_id": "RP-02", "strength": "high",
             "rationale": "Capacity saturation = outage (Cloudflare 2019-07-02; GitHub 2018-10-21)"},
            {"pattern_id": "RP-12", "strength": "medium",
             "rationale": "Sustained capacity stress increases repeat incidents"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-09", "strength": "medium",
             "rationale": "Emergency changes elevate capacity volatility"},
        ],
    },
    "RP-12": {
        "cascade_to": [],
        "cascade_from": [
            {"pattern_id": "RP-02", "strength": "high",
             "rationale": "Repeat availability breaches feed repeat-incident metric"},
            {"pattern_id": "RP-01", "strength": "medium",
             "rationale": "Deploy regressions account for the largest share of post-incident workload"},
            {"pattern_id": "RP-11", "strength": "medium",
             "rationale": "Capacity events drive Sev-1 incident frequency"},
        ],
    },
    "RP-13": {
        "cascade_to": [
            {"pattern_id": "RP-06", "strength": "high",
             "rationale": "Agentic AI tool-use exfiltrates PII (Samsung 2023-04-30; ChatGPT Redis bug 2023-03-20)"},
            {"pattern_id": "RP-07", "strength": "medium",
             "rationale": "Malicious MCP packages enter the tool supply chain (Sept 2025 first malicious package)"},
        ],
        "cascade_from": [
            {"pattern_id": "RP-05", "strength": "medium",
             "rationale": "Over-scoped tokens are the precondition for MCP rug-pull abuse"},
            {"pattern_id": "RP-10", "strength": "high",
             "rationale": "Untrusted model outputs become agentic tool-use vectors"},
        ],
    },
}

# Regulatory disclosure triggers per pattern. Conservative — only flagged when
# the cited authority explicitly applies. Values are: true | false | "conditional".
MATERIALITY = {
    "RP-01": {"sec_8k": True,  "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Material outage triggers SEC Item 1.05 (cybersecurity); OCC heightened standards require release-failure reporting for systemically important institutions."},
    "RP-02": {"sec_8k": True,  "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Sustained SLA breach is materially disclosable under SEC 8-K Item 1.05; OCC requires resilience event reporting."},
    "RP-03": {"sec_8k": False, "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Internal-control failures rarely meet 8-K materiality alone but feed OCC's MRA / MRIA escalation path."},
    "RP-04": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": "conditional", "eu_ai_act": False,
              "note": "Critical vuln becomes 8-K-material if actively exploited; GDPR Art. 33 triggered if exploitation leads to data breach."},
    "RP-05": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": "conditional", "eu_ai_act": False,
              "note": "Identity compromise alone is not 8-K material; coupled with data access it triggers GDPR Art. 33 and likely 8-K."},
    "RP-06": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": True, "eu_ai_act": False,
              "note": "GDPR Art. 33 mandates 72-hour notification of personal-data breaches; CCPA §1798.82 has parallel state-level obligations."},
    "RP-07": {"sec_8k": True,  "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Supply-chain compromise is 8-K Item 1.05 material (SolarWinds-class); OCC TPRM expectations apply."},
    "RP-08": {"sec_8k": False, "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Detection gaps surface only via OCC heightened-standards examinations and SOC 2 CC7.x criteria."},
    "RP-09": {"sec_8k": False, "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Change-management failures feed OCC MRA / MRIA; not directly 8-K-disclosable."},
    "RP-10": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": False, "eu_ai_act": "conditional",
              "note": "EU AI Act high-risk system obligations apply from 2026; SEC 8-K materiality if model failure causes financial loss (Zillow 2021)."},
    "RP-11": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": False, "eu_ai_act": False,
              "note": "Capacity-driven outage becomes 8-K material when customer-facing services breach SLA."},
    "RP-12": {"sec_8k": True,  "occ_12cfr30": True,  "gdpr_art33": False, "eu_ai_act": False,
              "note": "Extended outage (Atlassian 2022 14-day) is 8-K Item 1.05 material; OCC requires Sev-1 postmortem within 5 days."},
    "RP-13": {"sec_8k": "conditional", "occ_12cfr30": True, "gdpr_art33": "conditional", "eu_ai_act": True,
              "note": "Agentic AI in EU high-risk context: EU AI Act post-market monitoring obligations from 2026; PII exfiltration via agent tools triggers GDPR Art. 33."},
}


def main() -> None:
    data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    data["version"] = "1.3"
    data["grounding_note"] += (
        " v1.3 adds cascade rules and regulatory-materiality triggers — see "
        "DESIGN.md for the locked spec and the cascade-rule rationale per edge."
    )

    for p in data["patterns"]:
        pid = p["id"]
        if pid in CASCADE_EDGES:
            p["cascade_to"]   = CASCADE_EDGES[pid]["cascade_to"]
            p["cascade_from"] = CASCADE_EDGES[pid]["cascade_from"]
        else:
            p.setdefault("cascade_to", [])
            p.setdefault("cascade_from", [])
        if pid in MATERIALITY:
            p["materiality_trigger"] = MATERIALITY[pid]

    PATTERNS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {PATTERNS_FILE.relative_to(REPO)} — version {data['version']}, "
          f"{len(data['patterns'])} patterns, "
          f"{sum(len(p.get('cascade_to', [])) + len(p.get('cascade_from', [])) for p in data['patterns'])} cascade edges, "
          f"{sum(1 for p in data['patterns'] if 'materiality_trigger' in p)} materiality blocks")


if __name__ == "__main__":
    main()
