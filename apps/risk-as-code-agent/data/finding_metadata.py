"""
finding_metadata — illustrative-but-defensible per-finding metadata that the
pipeline does not yet compute from telemetry.

v1.3.1 (council-driven):
- per-pattern risk-specific acceptance justifications (no more two-string rotation)
- named individual humans + signoff role separate from acceptor
- ticket IDs + owner handles + ETA on treatment plans
- ISO 31000 strict vocabulary (accept / mitigate / transfer / avoid only — "monitor" removed)
- first_detected anchor date so time-in-state can be reconstructed

The fields here are what a real IRM (ServiceNow, Archer, LogicGate) would store
alongside the technical signal. Values are deterministic from
pattern_id + domain_id so the dashboard always shows the same values for the
same finding across regenerations — that's what makes the artefact
re-runnable + auditable.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List


# Per-pattern compensating-controls catalog. Real values; cite framework where applicable.
_COMPENSATING_CONTROLS: Dict[str, List[Dict[str, str]]] = {
    "RP-01": [
        {"name": "Phased rollout (canary + ring deployment)", "framework": "DORA 2024+2025", "effectiveness": "high"},
        {"name": "Automated rollback on SLO violation",          "framework": "Google SRE error budget", "effectiveness": "high"},
        {"name": "Pre-prod load test gate",                   "framework": "internal", "effectiveness": "medium"},
    ],
    "RP-02": [
        {"name": "Multi-AZ failover",                         "framework": "AWS Well-Architected", "effectiveness": "high"},
        {"name": "Circuit breakers on downstream calls",      "framework": "Google SRE", "effectiveness": "medium"},
    ],
    "RP-03": [
        {"name": "OPA / Gatekeeper admission policy",         "framework": "CIS K8s Benchmark", "effectiveness": "high"},
        {"name": "Drift detection (Terraform Cloud / Pulumi)","framework": "CIS Controls v8", "effectiveness": "medium"},
    ],
    "RP-04": [
        {"name": "Runtime SBOM scan (Snyk / Wiz)",            "framework": "EO 14028", "effectiveness": "high"},
        {"name": "WAF virtual-patch rules",                   "framework": "OWASP", "effectiveness": "medium"},
        {"name": "Network segmentation",                      "framework": "NIST CSF PR.AC", "effectiveness": "medium"},
    ],
    "RP-05": [
        {"name": "Just-In-Time elevation (Teleport / AWS SSO)", "framework": "CISA Zero Trust", "effectiveness": "high"},
        {"name": "Hardware MFA for privileged roles",          "framework": "NIST SP 800-63B AAL3", "effectiveness": "high"},
    ],
    "RP-06": [
        {"name": "DLP egress monitoring",                     "framework": "GDPR Art. 32", "effectiveness": "medium"},
        {"name": "Field-level encryption at rest",            "framework": "PCI-DSS 3.4", "effectiveness": "high"},
        {"name": "Synthetic data in non-prod environments",   "framework": "GDPR Art. 5 (data minimisation)", "effectiveness": "high"},
    ],
    "RP-07": [
        {"name": "Vendor SOC 2 review + annual reassessment", "framework": "AICPA TSC", "effectiveness": "medium"},
        {"name": "SBOM ingestion + KEV cross-check",          "framework": "CISA BOD 22-01", "effectiveness": "high"},
    ],
    "RP-08": [
        {"name": "Distributed tracing coverage (OTel)",       "framework": "Google SRE", "effectiveness": "high"},
        {"name": "SIEM ingestion with retention >= 365d",     "framework": "SOC 2 CC7.2", "effectiveness": "medium"},
    ],
    "RP-09": [
        {"name": "Change Advisory Board (CAB) for production","framework": "ITIL 4", "effectiveness": "medium"},
        {"name": "Emergency-change post-hoc review (24h)",    "framework": "internal", "effectiveness": "medium"},
    ],
    "RP-10": [
        {"name": "Pre-deployment model evaluation suite",     "framework": "NIST AI RMF MEASURE-2", "effectiveness": "high"},
        {"name": "Production model performance monitoring",   "framework": "NIST AI 600-1", "effectiveness": "medium"},
    ],
    "RP-11": [
        {"name": "Horizontal Pod Autoscaler with headroom",   "framework": "Google SRE 30% headroom", "effectiveness": "high"},
        {"name": "Load-shedding circuit breakers",            "framework": "Google SRE", "effectiveness": "medium"},
    ],
    "RP-12": [
        {"name": "Documented runbooks per Sev-1 scenario",    "framework": "Google SRE", "effectiveness": "high"},
        {"name": "Quarterly DR / chaos game-day",             "framework": "internal", "effectiveness": "medium"},
    ],
    "RP-13": [
        {"name": "Tool-definition hash pinning",              "framework": "OWASP MCP Top 10", "effectiveness": "high"},
        {"name": "Human-in-loop for any non-read tool call",  "framework": "NIST AI 600-1", "effectiveness": "high"},
        {"name": "Scoped tokens with per-call justification", "framework": "CISA Zero Trust", "effectiveness": "medium"},
        {"name": "Prompt-injection input sanitisation",       "framework": "OWASP LLM Top 10", "effectiveness": "medium"},
    ],
}


# Per-pattern $ exposure basis. The basis cites a comparable real incident.
_FINANCIAL_BASIS: Dict[str, Dict] = {
    "RP-01": {"usd_per_red": 50_000_000, "basis": "Knight Capital 2012 — $440M / 45 min"},
    "RP-02": {"usd_per_red": 20_000_000, "basis": "AWS US-EAST-1 2021 — multi-hour outage, customer-side losses"},
    "RP-03": {"usd_per_red": 30_000_000, "basis": "Capital One 2019 — $80M OCC fine + ~$190M remediation"},
    "RP-04": {"usd_per_red": 80_000_000, "basis": "Equifax 2017 — $700M+ FTC settlement, 147.9M records"},
    "RP-05": {"usd_per_red": 25_000_000, "basis": "Uber 2022 — disclosed remediation + regulatory action"},
    "RP-06": {"usd_per_red": 60_000_000, "basis": "T-Mobile 2023 — ~$350M settlement, 37M customer records"},
    "RP-07": {"usd_per_red": 90_000_000, "basis": "SolarWinds 2020 — multi-firm remediation cost estimates"},
    "RP-08": {"usd_per_red": 10_000_000, "basis": "IBM Cost of a Data Breach 2024 — $4.88M global avg, US ~2x"},
    "RP-09": {"usd_per_red": 15_000_000, "basis": "GitLab 2017 — disclosed customer-credit impact"},
    "RP-10": {"usd_per_red": 40_000_000, "basis": "Zillow Offers 2021 — $304M Q3 inventory write-down"},
    "RP-11": {"usd_per_red": 12_000_000, "basis": "Cloudflare 2019 — 27-min global edge outage"},
    "RP-12": {"usd_per_red": 100_000_000, "basis": "Atlassian 2022 — 14-day customer impact + SLA credits"},
    "RP-13": {"usd_per_red": 35_000_000, "basis": "Samsung 2023 IP exfil + CVE-2025-49596 MCP supply-chain"},
}


# Per-pattern owner role mapping (engineering team that owns the fix).
# Realistic but illustrative. Real deployments wire to their IRM owner registry.
_OWNER_ROUTING: Dict[str, Dict[str, str]] = {
    "RP-01": {"team": "Platform engineering",     "handle": "@release-engineering"},
    "RP-02": {"team": "SRE on-call",              "handle": "@sre-platform"},
    "RP-03": {"team": "Platform security",        "handle": "@platform-secops"},
    "RP-04": {"team": "Security operations",      "handle": "@security-vuln-mgmt"},
    "RP-05": {"team": "Identity & access",        "handle": "@iam-platform"},
    "RP-06": {"team": "Privacy & compliance",     "handle": "@privacy-engineering"},
    "RP-07": {"team": "Third-party risk",         "handle": "@tprm-engineering"},
    "RP-08": {"team": "Detection & observability","handle": "@detection-engineering"},
    "RP-09": {"team": "Release management",       "handle": "@change-management"},
    "RP-10": {"team": "AI governance",            "handle": "@ai-governance"},
    "RP-11": {"team": "Platform engineering",     "handle": "@platform-capacity"},
    "RP-12": {"team": "Incident command",         "handle": "@incident-command"},
    "RP-13": {"team": "AI governance",            "handle": "@agent-platform-security"},
}


# Per-pattern, risk-specific acceptance justification templates.
# Each justification names the *specific* trade-off being accepted, the
# compensating control gap, and the conditions under which acceptance expires.
# Used only when a finding's treatment_plan == "accept".
_ACCEPTANCE_JUSTIFICATIONS: Dict[str, str] = {
    "RP-01": (
        "Change failure rate above DORA Medium threshold (15%) accepted through Q3 2026 to "
        "permit ongoing migration to new CD platform; phased rollout (canary + ring) compensates "
        "for elevated post-release defect rate. Expires when canary coverage reaches >90% of services."
    ),
    "RP-02": (
        "Availability below 99.9% SLO accepted for the duration of the current Multi-AZ "
        "failover validation cycle. Circuit breakers and load shedding provide compensating "
        "containment. Expires on completion of the chaos game-day with no Sev-1."
    ),
    "RP-03": (
        "Policy violation count above threshold (20) accepted while OPA admission policy "
        "rollout completes across remaining 14 namespaces. Drift-detection (Terraform Cloud) "
        "provides interim guardrail. Expires on namespace-coverage report ≥95%."
    ),
    "RP-04": (
        "Critical CVE aging beyond CISA BOD 19-02 SLA (15 days) accepted for the three "
        "upstream-vendor advisories under coordinated disclosure embargo. WAF virtual-patch "
        "rules deployed. Expires on vendor patch release or end of embargo, whichever is sooner."
    ),
    "RP-05": (
        "MFA coverage below 100% accepted for the 14 service accounts under JIT-elevation "
        "migration; standing-privileged access reduced 78% since Q1. Hardware MFA in place for "
        "all human privileged roles. Expires on completion of service-account migration plan."
    ),
    "RP-06": (
        "DLP alert volume above amber threshold (2) accepted while the new field-level encryption "
        "rollout completes across non-prod environments. Synthetic data substitution prevents "
        "additional exposure surface. Expires when prod-mirror encryption coverage reaches 100%."
    ),
    "RP-07": (
        "Open dependency-vuln count above threshold accepted for the duration of the SBOM "
        "ingestion programme. KEV cross-check ensures no exploited-in-wild gaps. Expires on "
        "completion of SBOM coverage across all Tier 1 vendor stacks."
    ),
    "RP-08": (
        "Alert coverage below 95% accepted while OTel instrumentation expands across the four "
        "newly-onboarded services. SIEM retention ≥365 days maintained. Expires on instrumentation "
        "completion + 30-day quiet period to validate."
    ),
    "RP-09": (
        "Emergency change rate above threshold (8%) accepted for Q2 due to known regulatory "
        "deadline-driven hotfix cadence. Post-hoc CAB review within 24h enforced for each. "
        "Expires at end of regulatory window (2026-09-30)."
    ),
    "RP-10": (
        "Model accuracy drift above 5% accepted on the credit-decisioning model under explicit "
        "monthly NIST AI RMF MEASURE-2 review. Pre-deployment evaluation suite tests pass. "
        "Expires on completion of model-retraining cycle currently in flight."
    ),
    "RP-11": (
        "CPU saturation above 85% during peak hours accepted while HPA-tuning programme "
        "completes across the payments service tier. Load-shedding circuit breakers tested "
        "and operational. Expires on HPA rollout to remaining payments pods."
    ),
    "RP-12": (
        "Repeat-incident rate above threshold (15%) accepted while runbook-coverage uplift "
        "programme completes. Quarterly DR / chaos game-day cadence in place. Expires when "
        "runbook coverage reaches 100% of Tier 1 services."
    ),
    "RP-13": (
        "Prompt-injection detection count above threshold accepted while tool-definition hash "
        "pinning rolls out across remaining MCP servers. Human-in-loop already enforced for "
        "all non-read tool calls. Expires when hash-pinning coverage reaches 100% of registered tools."
    ),
}


# Per-pattern, risk-specific early-expiry CONDITIONS (Path B fix E1,
# audit-regulator MRA-grade finding #1). The prior code used a single
# templated conditions string across all acceptances — under 12 CFR 30
# Appendix D § II.M + OCC Bulletin 2021-36 that reads as evidence the
# acceptance was not independently considered. Each condition below names a
# measurable early-expiry trigger tied to that pattern's specific
# compensating-control gap.
_ACCEPTANCE_CONDITIONS: Dict[str, str] = {
    "RP-01": (
        "Early expiry if canary coverage regresses below 90% of services, or if "
        "change-failure-rate crosses the DORA Low boundary (64%) in any 30-day window."
    ),
    "RP-02": (
        "Early expiry on any Sev-1 availability incident during the Multi-AZ "
        "failover validation cycle, or if error-budget burn exceeds 100% before the chaos game-day."
    ),
    "RP-03": (
        "Early expiry if OPA admission-policy namespace coverage stalls below 80%, "
        "or on any policy-bypass detected by Terraform Cloud drift-detection."
    ),
    "RP-04": (
        "Early expiry on vendor patch release, end of the disclosure embargo, or "
        "CISA KEV listing (in-the-wild exploitation) for any of the three CVEs — whichever is first."
    ),
    "RP-05": (
        "Early expiry if standing-privileged access rises above the current baseline, "
        "or if any of the 14 service-account credentials is implicated in an access anomaly."
    ),
    "RP-06": (
        "Early expiry if DLP alert volume doubles, or if the field-level encryption "
        "rollout misses the prod-mirror coverage milestone date."
    ),
    "RP-07": (
        "Early expiry on KEV listing of any open dependency-vuln, or if SBOM ingestion "
        "misses the Tier 1 vendor-stack coverage milestone."
    ),
    "RP-08": (
        "Early expiry if alert coverage regresses below 95%, or if any of the four "
        "newly-onboarded services experiences an undetected incident during the 30-day quiet period."
    ),
    "RP-09": (
        "Early expiry if any emergency change skips the mandated 24h post-hoc CAB review, "
        "or at the close of the regulatory window (2026-09-30) — whichever is first."
    ),
    "RP-10": (
        "Early expiry if model accuracy drift exceeds 8% in any monthly NIST AI RMF "
        "MEASURE-2 review, or if the pre-deployment evaluation suite fails."
    ),
    "RP-11": (
        "Early expiry if CPU saturation exceeds 95% during peak hours, or if any "
        "load-shedding circuit breaker fails to trip under the next scheduled test."
    ),
    "RP-12": (
        "Early expiry if repeat-incident rate exceeds 25%, or on any Tier 1 repeat "
        "Sev-1 that occurs without a closed runbook for the originating incident."
    ),
    "RP-13": (
        "Early expiry if prompt-injection detections double, on any non-read tool call "
        "that bypasses human-in-loop, or on discovery of an unpinned tool-definition mutation."
    ),
}


# Named-individual signers — illustrative but role-realistic.
# A real deployment wires these to the IRM signer registry.
_NAMED_SIGNERS: Dict[str, Dict[str, str]] = {
    "engineering_director": {"name": "D. Patel",     "title": "Director, Platform Engineering",      "role": "1LoD"},
    "engineering_vp":       {"name": "M. Okonkwo",   "title": "VP Engineering",                      "role": "1LoD"},
    "sre_lead":             {"name": "J. Nakamura",  "title": "Lead SRE, Payments",                  "role": "1LoD"},
    "risk_director":        {"name": "S. Khoury",    "title": "Director, Technology Risk",           "role": "2LoD"},
    "risk_head":            {"name": "L. Ferreira",  "title": "Head of Operational Risk",            "role": "2LoD"},
    "ciso_deputy":          {"name": "R. Ahuja",     "title": "Deputy CISO, Cyber Risk",             "role": "2LoD"},
    "audit_partner":        {"name": "T. Williams",  "title": "Partner, Internal Audit",             "role": "3LoD"},
}

# Signoff routing per pattern — who accepts (1LoD), who counter-signs (2LoD).
_SIGNOFF_ROUTING: Dict[str, Dict[str, str]] = {
    "RP-01": {"acceptor": "engineering_director", "countersign": "risk_director"},
    "RP-02": {"acceptor": "sre_lead",             "countersign": "risk_director"},
    "RP-03": {"acceptor": "engineering_vp",       "countersign": "ciso_deputy"},
    "RP-04": {"acceptor": "engineering_director", "countersign": "ciso_deputy"},
    "RP-05": {"acceptor": "engineering_vp",       "countersign": "ciso_deputy"},
    "RP-06": {"acceptor": "engineering_director", "countersign": "risk_head"},
    "RP-07": {"acceptor": "engineering_director", "countersign": "risk_director"},
    "RP-08": {"acceptor": "sre_lead",             "countersign": "risk_director"},
    "RP-09": {"acceptor": "engineering_director", "countersign": "risk_director"},
    "RP-10": {"acceptor": "engineering_vp",       "countersign": "risk_head"},
    "RP-11": {"acceptor": "sre_lead",             "countersign": "risk_director"},
    "RP-12": {"acceptor": "sre_lead",             "countersign": "risk_head"},
    "RP-13": {"acceptor": "engineering_vp",       "countersign": "ciso_deputy"},
}


# ── organizational reality per pattern — ILLUSTRATIVE, but politically honest ──
# Round-8 human review: "can we truly force decisions??? what would be a more
# politically direct, honest, and likely approach?" Answer: 2LoD cannot force
# anything. Its actual levers are: table the item at the right committee, log a
# formal challenge, decline to counter-sign the next acceptance renewal, or
# escalate to the CRO — and each spends political capital. This block carries WHY
# each remediation is actually stalled (competing exec commitments, headcount,
# migrations, vendor contracts — the real reasons), who is accountable by NAME,
# where the decision actually gets made, and what escalating costs. All synthetic,
# deliberately typical of a global consumer/crypto fintech; labeled illustrative.
#
# Committee vocabulary (illustrative org): TRC = Technology Risk Committee
# (monthly, CTO + CRO co-chair); ORC = Operational Risk Committee (monthly);
# SecSteer = Security Steering (bi-weekly, CISO chair); BRC = Board Risk
# Committee (quarterly). Escalation ladder: not-raised → raised-informally →
# committee-agenda → formal-2LoD-challenge → CRO → BRC.
_ORG_CONTEXT: Dict[str, Dict[str, str]] = {
    "RP-01": {
        "accountable_exec": "M. Okonkwo · VP Engineering",
        "stall_reason": "the same release-engineering pod owns the CD-platform migration; remediation and migration compete for identical headcount",
        "competing_commitment": "EU market-entry launch (exec-committee dated, Q3) holds the deploy train — nobody will slow it for a control fix",
        "escalation_state": "raised at TRC 2026-06-17 · minuted, no owner action since",
        "decision_route": "TRC agenda 2026-07-15 — 2LoD can table it and put the delta on record; only the VP can re-sequence the pod",
        "political_cost": "a formal challenge mid-migration reads as 2LoD blocking the org's #1 initiative; declining the Q3 acceptance renewal is quieter and forces the VP to re-own the risk in writing",
    },
    "RP-02": {
        "accountable_exec": "J. Nakamura · Lead SRE, Payments (acting — role unfilled 2 quarters)",
        "stall_reason": "SLO remediation is staffed by the on-call rotation itself; every SEV pulls the same people off the fix",
        "competing_commitment": "peak-season capacity hardening is the SRE org's committed OKR; SLO debt is explicitly below-the-line",
        "escalation_state": "raised informally in SRE sync · never minuted",
        "decision_route": "ORC 2026-07-22 — needs the unfilled Payments-SRE req funded; that is a budget decision, not an engineering one",
        "political_cost": "escalating a staffing gap lands on the CFO's headcount freeze, not on engineering — 2LoD challenge here is really a budget challenge wearing a risk costume",
    },
    "RP-03": {
        "accountable_exec": "M. Okonkwo · VP Engineering",
        "stall_reason": "policy-as-code rollout is blocked on a platform-team API that ships 'next sprint' for the third consecutive sprint",
        "competing_commitment": "the platform team's roadmap is contractually pinned to a partner-bank integration",
        "escalation_state": "committee-agenda · TRC 2026-06-17 assigned an owner; owner reorged away two weeks later",
        "decision_route": "TRC 2026-07-15 — re-assign ownership post-reorg; without a named owner the item will roll a third month",
        "political_cost": "low — this one is process failure, not conflict; the ask is administrative (name an owner), which committees grant cheaply",
    },
    "RP-04": {
        "accountable_exec": "R. Ahuja · Deputy CISO",
        "stall_reason": "KEV patch SLA exceedances sit in a vendor-appliance estate the security org cannot patch itself; vendor maintenance windows are quarterly by contract",
        "competing_commitment": "renegotiating the vendor contract is Procurement's queue, 6-month lead",
        "escalation_state": "formal-2LoD-challenge logged 2026-06-30 (challenge #CH-2026-014)",
        "decision_route": "SecSteer 2026-07-11 — decision needed: pay for out-of-cycle vendor patching (≈$180k/yr, illustrative) or formally accept the SLA gap",
        "political_cost": "already spent — the challenge is logged; the remaining move is forcing an explicit pay-or-accept decision, which execs resent because both options are on the record",
    },
    "RP-05": {
        "accountable_exec": "M. Okonkwo · VP Engineering",
        "stall_reason": "standing-privilege cleanup breaks two internal tools every time it is attempted; the tool owners were reorged into a different reporting line",
        "competing_commitment": "identity team is consumed by the SSO-vendor migration (contract expiry-driven, immovable date)",
        "escalation_state": "raised-informally · 1LoD says 'after SSO migration' for the second quarter running",
        "decision_route": "SecSteer 2026-07-11 — ask for a dated commitment, not a fix: 'which sprint after SSO cutover, in writing'",
        "political_cost": "moderate — pushing before the SSO cutover date lands as tone-deaf; the winning move is a minuted date, then holding to it",
    },
    "RP-06": {
        "accountable_exec": "L. Ferreira · Head of Operational Risk (2LoD-owned control, 1LoD delivery)",
        "stall_reason": "data-retention deletion pipeline is 'done' but Legal has not signed the deletion-scope memo — engineering waits on Legal, Legal waits on outside counsel",
        "competing_commitment": "Legal's queue is consumed by the market-entry licensing work",
        "escalation_state": "committee-agenda · ORC 2026-06-24, action on Legal, no date",
        "decision_route": "ORC 2026-07-22 — the honest ask is a decision DATE from Legal, and interim risk ownership in writing while the memo waits",
        "political_cost": "challenging Legal is the most expensive move in the building; frame as 'we need the date, not the answer' or it will be read as engineering blaming lawyers",
    },
    "RP-07": {
        "accountable_exec": "D. Patel · Director, Platform Engineering",
        "stall_reason": "the concentration risk IS the vendor the platform is built on; 'remediation' means a multi-year second-provider strategy nobody has funded",
        "competing_commitment": "none competing — the item is stalled because it is too big, not too busy",
        "escalation_state": "committee-agenda · standing TRC item for 3 cycles; re-noted, never resourced",
        "decision_route": "BRC (quarterly, next 2026-09) — this is genuinely a board-appetite question: fund multi-provider or formally accept concentration; TRC cannot decide it",
        "political_cost": "putting it to the board without a costed proposal wastes the slot; 2LoD's move is to commission the costing, not to demand the decision",
    },
    "RP-08": {
        "accountable_exec": "J. Nakamura · Lead SRE, Payments",
        "stall_reason": "alert-coverage gaps persist because every new service ships with default dashboards; coverage is nobody's definition-of-done",
        "competing_commitment": "observability platform team measures itself on ingest cost reduction — MORE coverage is against their current OKR",
        "escalation_state": "not-raised — treated as engineering hygiene, invisible at committee level",
        "decision_route": "TRC 2026-07-15 — the ask is a paved-road gate (no prod deploy without KRI wiring), which is a standards decision TRC can actually make",
        "political_cost": "low-moderate — paved-road gates annoy teams for a sprint and then become furniture; the OKR conflict with the observability team is the real fight",
    },
    "RP-09": {
        "accountable_exec": "D. Patel · Director, Platform Engineering",
        "stall_reason": "emergency-change volume is the release process working as designed under launch pressure — the org is choosing speed and papering it as exceptions",
        "competing_commitment": "same EU launch train as RP-01; emergency-change reviews are rubber-stamped to keep it moving",
        "escalation_state": "formal-2LoD-challenge drafted, unsent — pending this week's decision",
        "decision_route": "TRC 2026-07-15 — the direct ask: either raise the emergency-change bar and eat the launch delay, or the accountable exec signs the elevated risk explicitly",
        "political_cost": "high — this challenge says 'your launch cadence is the risk', which is career-adjacent for everyone in the room; it is also exactly the challenge 2LoD exists to make",
    },
    "RP-10": {
        "accountable_exec": "M. Okonkwo · VP Engineering (model owner) + L. Ferreira (validation)",
        "stall_reason": "model-validation backlog: one validator, four models in queue, and validation is a regulatory gate only for the two in scope",
        "competing_commitment": "validator is also the SR 11-7 exam-prep owner (exam fieldwork starts Q4)",
        "escalation_state": "raised-informally · validation queue published, no priority decision",
        "decision_route": "ORC 2026-07-22 — queue-order decision: which two models validate first; contractor budget for the rest",
        "political_cost": "low — queue-ordering is a decision execs will happily make; the contractor ask competes with the same frozen budget as RP-02",
    },
    "RP-11": {
        "accountable_exec": "J. Nakamura · Lead SRE, Payments",
        "stall_reason": "capacity headroom below target in two regions; the fix is a reserved-capacity spend that finance rejected once as 'insurance against a load we have never seen'",
        "competing_commitment": "cloud cost-reduction program (CFO-sponsored) points the same dial the other way",
        "escalation_state": "committee-agenda · ORC 2026-06-24, deferred pending peak-season forecast",
        "decision_route": "ORC 2026-07-22 with the new forecast — the honest framing is price-per-basis-point-of-headroom vs the residual $ on this dashboard",
        "political_cost": "moderate — 2LoD siding with SRE against the CFO's program needs the dollar comparison airtight; that is what the exposure block is FOR",
    },
    "RP-12": {
        "accountable_exec": "S. Khoury · Director, Technology Risk (2LoD owns the process)",
        "stall_reason": "post-incident actions close at 60% because closure is self-attested by the team that wrote them; nobody re-tests",
        "competing_commitment": "incident-command is mid-migration to a new tooling stack; process changes wait for it",
        "escalation_state": "committee-agenda · TRC standing metric, trend flat 3 cycles",
        "decision_route": "TRC 2026-07-15 — 2LoD-owned fix: sampled re-testing of closed actions; needs no 1LoD permission, only 2LoD staffing",
        "political_cost": "none externally — this one is 2LoD's own house; the only cost is admitting the metric was self-attested all along",
    },
    "RP-13": {
        "accountable_exec": "M. Okonkwo · VP Engineering",
        "stall_reason": "agent tool-scopes are wide because narrowing them breaks workflows nobody fully maps; the mapping work is unowned",
        "competing_commitment": "agent platform team is shipping new capabilities weekly; scope-narrowing is anti-roadmap",
        "escalation_state": "raised-informally · one workflow has NO declared scope at all (see atg RE-04)",
        "decision_route": "SecSteer 2026-07-11 — the tractable ask: no NEW agent ships without a declared scope (gate), existing scopes mapped by Q4",
        "political_cost": "low for the gate on new agents; the Q4 backfill will slip unless someone owns the mapping — ask for the name in the minutes",
    },
}


def org_context(pattern_id: str) -> Dict[str, str]:
    """Organizational-reality block for one pattern — ILLUSTRATIVE org dynamics
    (stall reason, competing commitment, escalation state, decision route,
    political cost), deliberately typical of a global consumer/crypto fintech.
    2LoD cannot force remediation; this block says what it CAN do and what each
    move costs."""
    ctx = dict(_ORG_CONTEXT.get(pattern_id, {}))
    if ctx:
        ctx["source_status"] = "illustrative"
    return ctx


# ── internal-audit posture — the 3LoD lifecycle, ILLUSTRATIVE ────────────────────
# Round-8 depth pass: the attest act verified chains but had no AUDIT SHOP in it.
# Real 3LoD reality is issues with management responses, target dates that slip,
# validation that lags closure, and REPEAT findings — the thing examiners actually
# punish. All synthetic; statuses chosen to cover the honest lifecycle including
# one past-due and one repeat.
_AUDIT_ISSUES: List[Dict[str, str]] = [
    {
        "issue_id": "IA-2025-041", "pattern_id": "RP-09", "severity": "high",
        "title": "Emergency-change volume normalizes review bypass",
        "raised": "2025-11-14", "source": "internal audit · change management review",
        "management_response": "REMEDIATE — raise emergency-change bar + weekly CAB look-back; owner VP Engineering",
        "target_date": "2026-04-30", "status": "PAST DUE",
        "repeat_finding": True,
        "note": "REPEAT of IA-2024-118 (same root cause, prior target missed). Second consecutive miss — escalates to Audit Committee reporting per charter.",
    },
    {
        "issue_id": "IA-2026-007", "pattern_id": "RP-12", "severity": "high",
        "title": "Post-incident action closure is self-attested, not re-tested",
        "raised": "2026-02-20", "source": "internal audit · incident management review",
        "management_response": "REMEDIATE — 2LoD sampled re-testing of closed actions; owner Director, Technology Risk",
        "target_date": "2026-08-31", "status": "OPEN · on track",
        "repeat_finding": False,
        "note": "Same gap the dashboard's RP-12 KRI now measures — audit issue and KRI reconcile.",
    },
    {
        "issue_id": "IA-2026-013", "pattern_id": "RP-05", "severity": "medium",
        "title": "Standing privileged access exceeds policy dormancy limits",
        "raised": "2026-03-12", "source": "internal audit · identity & access review",
        "management_response": "REMEDIATE post-SSO-migration — dated commitment requested (see org context); owner VP Engineering",
        "target_date": "2026-10-15", "status": "OPEN · blocked on SSO migration",
        "repeat_finding": False,
        "note": "Target date already re-baselined once (was 2026-06-30).",
    },
    {
        "issue_id": "IA-2025-096", "pattern_id": "RP-04", "severity": "medium",
        "title": "Vendor-appliance patching exceeds KEV SLA by contract design",
        "raised": "2025-09-30", "source": "internal audit · vulnerability management review",
        "management_response": "RISK ACCEPT (interim) — pay-or-accept decision at SecSteer; formal challenge CH-2026-014 logged by 2LoD",
        "target_date": "2026-07-11", "status": "VALIDATION PENDING · decision due",
        "repeat_finding": False,
        "note": "Closure requires evidence of either out-of-cycle patching contract or a signed acceptance with expiry.",
    },
    {
        "issue_id": "IA-2026-019", "pattern_id": "RP-08", "severity": "medium",
        "title": "New services ship without KRI wiring — coverage is nobody's definition-of-done",
        "raised": "2026-04-08", "source": "internal audit · observability thematic",
        "management_response": "REMEDIATE — paved-road deploy gate proposed to TRC 2026-07-15; owner Lead SRE Payments",
        "target_date": "2026-09-30", "status": "OPEN · on track",
        "repeat_finding": False,
        "note": "",
    },
    {
        "issue_id": "EX-2026-002", "pattern_id": "RP-10", "severity": "high",
        "title": "Model validation backlog — two in-scope models past validation due date",
        "raised": "2026-05-22", "source": "ILLUSTRATIVE exam-style item (MRA-analog) · model risk",
        "management_response": "REMEDIATE — queue-order decision + contractor budget at ORC 2026-07-22; owner VP Engineering + Head of Op Risk",
        "target_date": "2026-11-30", "status": "OPEN · regulator-visible",
        "repeat_finding": False,
        "note": "Exam-style items carry committed dates TO THE REGULATOR — a miss here is a different class of event than an internal slip. Illustrative; no real examination is referenced.",
    },
    {
        "issue_id": "IA-2025-112", "pattern_id": "RP-06", "severity": "low",
        "title": "Data-retention deletion evidence not centrally retained",
        "raised": "2025-12-05", "source": "internal audit · privacy review",
        "management_response": "REMEDIATE — deletion-evidence store shipped 2026-05; awaiting 3LoD validation sample",
        "target_date": "2026-06-30", "status": "CLOSED · validation passed 2026-06-24",
        "repeat_finding": False,
        "note": "The one clean closure in the register — closed WITH re-test evidence, the standard the RP-12 issue is trying to make universal.",
    },
]


def internal_audit_posture() -> Dict[str, Any]:
    """The 3LoD register — ILLUSTRATIVE issues with the full lifecycle: management
    response → target date → validation → closure, including one PAST-DUE repeat
    finding (the examiner-bait state) and one exam-style (MRA-analog) item."""
    issues = [dict(i) for i in _AUDIT_ISSUES]
    open_issues = [i for i in issues if not i["status"].startswith("CLOSED")]
    return {
        "source_status": "illustrative",
        "source_note": (
            "ILLUSTRATIVE internal-audit register — synthetic issues written in real "
            "3LoD lifecycle vocabulary (management response, target date, validation, "
            "repeat-finding flag, exam-style analog). No real audit or examination is "
            "referenced. Deliberately includes the states that define a real shop: a "
            "PAST-DUE REPEAT finding (what examiners punish), a re-baselined target, "
            "a closure that required re-test evidence, and a regulator-visible item."
        ),
        "issues": issues,
        "counts": {
            "open": len(open_issues),
            "past_due": len([i for i in issues if "PAST DUE" in i["status"]]),
            "repeat": len([i for i in issues if i["repeat_finding"]]),
            "regulator_visible": len([i for i in issues if i["issue_id"].startswith("EX-")]),
        },
    }


def _stable_hash(*parts: str) -> int:
    """Deterministic 32-bit hash for stable mock metadata across runs."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


# IA Stage B conservation catch: these anchors used datetime.now(), so every
# rebuild that crossed UTC midnight shifted EVERY rendered date by a day —
# the fingerprint gate flagged queue/register drift with zero data changes.
# Pinned to the assessment as-of date; same class of fix as C25 (register
# determinism): identical inputs must give an identical artifact, any day.
_AS_OF = datetime(2026, 7, 14, tzinfo=timezone.utc)


def first_detected(pattern_id: str, domain_id: str, rag: str) -> str:
    """ILLUSTRATIVE detection date — deterministic (stable per finding), NOT
    observed telemetry. Unlike agent-trace-gov (which derives first_detected from
    real trace timestamps), this project's input is synthetic, so the date is a
    reproducible illustrative anchor, disclosed as such by the artefact's
    provenance (illustrative) + disclosure banner. Red findings read older, amber
    newer. Do not present as measured forensic history."""
    h = _stable_hash(pattern_id, domain_id, "first_detected")
    base_days = 90 if rag == "red" else 30
    days_ago = base_days + (h % 60)
    return (_AS_OF - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def time_in_state_days(pattern_id: str, domain_id: str, rag: str) -> int:
    """Days since first_detected (matches the first_detected anchor exactly)."""
    h = _stable_hash(pattern_id, domain_id, "first_detected")
    base_days = 90 if rag == "red" else 30
    return base_days + (h % 60)


def _ticket_id(pattern_id: str, domain_id: str) -> str:
    """Deterministic fake ticket ID per finding. Realistic-looking."""
    h = _stable_hash(pattern_id, domain_id, "ticket")
    prefix_for_pattern = {
        "RP-01": "REL",  "RP-02": "SRE",  "RP-03": "POL",  "RP-04": "SEC",
        "RP-05": "IAM",  "RP-06": "PRIV", "RP-07": "TPRM", "RP-08": "OBS",
        "RP-09": "CHG",  "RP-10": "AIGOV","RP-11": "CAP",  "RP-12": "INC",
        "RP-13": "AGT",
    }
    pfx = prefix_for_pattern.get(pattern_id, "RISK")
    return f"{pfx}-{2026}-{(h % 9000) + 1000}"


def treatment_plan(pattern_id: str, domain_id: str, rag: str) -> Dict[str, str]:
    """Returns {plan, status, eta, ticket, owner_team, owner_handle}.

    ISO 31000 strict vocabulary: accept / mitigate / transfer / avoid. No "monitor".
    """
    h = _stable_hash(pattern_id, domain_id, "treatment")
    if rag == "red":
        plans     = ["mitigate", "mitigate", "mitigate", "transfer", "accept"]
        statuses  = ["in_progress", "in_progress", "blocked", "in_progress", "accepted"]
    else:
        plans     = ["mitigate", "accept", "mitigate", "mitigate"]   # no "monitor"
        statuses  = ["planned", "accepted", "in_progress", "in_progress"]
    plan = plans[h % len(plans)]
    status = statuses[h % len(statuses)]
    eta_days = 14 + (h % 76)
    eta = (_AS_OF + timedelta(days=eta_days)).strftime("%Y-%m-%d")

    owner = _OWNER_ROUTING.get(pattern_id, {"team": "Domain owner", "handle": "@domain-owner"})

    return {
        "plan":         plan,
        "status":       status,
        "eta":          eta,
        "ticket":       _ticket_id(pattern_id, domain_id),
        "owner_team":   owner["team"],
        "owner_handle": owner["handle"],
        # Honesty tag (round-6 external finding): seeded routing uses TEAM handles,
        # which the live A8 verb modal deliberately REJECTS (named human required).
        # The seeded data must not perform a rigor it doesn't possess — so it says so.
        "owner_kind": (
            "illustrative team handle — A8 requires a NAMED HUMAN for live actions; "
            "seeded treatment routing is team-level by design and labeled as such"
        ),
    }


def financial_exposure(pattern_id: str, rag: str) -> Dict:
    """RETRACTED (v1.3). Flat `$/red × factor` exposure with an "industry average"
    basis — no probability term, no frequency×severity. Superseded by the
    frequency×severity model in utils/exposure.py (portfolio_exposure). Retained
    for provenance/history only; NOT rendered by the shipped v2.0a dashboard, and
    the Streamlit app now generates the v2.0a renderer. Do not reintroduce into a
    live surface — this is the exact methodology v1.4 was retracted for."""
    base = _FINANCIAL_BASIS.get(pattern_id, {"usd_per_red": 5_000_000, "basis": "industry average"})
    factor = 1.0 if rag == "red" else 0.25
    return {
        "usd": int(base["usd_per_red"] * factor),
        "basis": base["basis"],
        "_retracted": "v1.3 flat model — superseded by utils.exposure (freq×severity)",
    }


def compensating_controls(pattern_id: str) -> List[Dict[str, str]]:
    return _COMPENSATING_CONTROLS.get(pattern_id, [])


def acceptance_trail(pattern_id: str, domain_id: str, rag: str, treatment: Dict[str, str]) -> List[Dict[str, str]]:
    """Per-finding acceptance record. Only present when treatment.plan == 'accept'
    OR when finding is red AND treatment is in_progress / blocked (representing
    interim residual-risk acceptance until mitigation completes).

    Each record has:
      - accepted_by_name + title + role (1LoD/2LoD/3LoD)
      - countersigned_by_name + title + role
      - accepted_at, expires_at
      - justification (pattern-specific, references signal + compensating control)
      - ticket (links to the underlying decision record)
      - conditions (what causes early expiry)
    """
    if treatment["plan"] != "accept" and rag != "red":
        return []

    h = _stable_hash(pattern_id, domain_id, "acceptance")
    accepted_at = _AS_OF - timedelta(days=30 + (h % 60))
    expires_at = accepted_at + timedelta(days=180)

    routing = _SIGNOFF_ROUTING.get(pattern_id, {"acceptor": "engineering_director", "countersign": "risk_director"})
    acceptor = _NAMED_SIGNERS[routing["acceptor"]]
    countersigner = _NAMED_SIGNERS[routing["countersign"]]

    base_justification = _ACCEPTANCE_JUSTIFICATIONS.get(
        pattern_id,
        f"Residual risk on {pattern_id} accepted pending completion of in-flight mitigation."
    )
    base_conditions = _ACCEPTANCE_CONDITIONS.get(
        pattern_id,
        f"Auto-review at expiry; early expiry if the {pattern_id} compensating-control "
        f"effectiveness drops below its documented medium-tier baseline."
    )
    # Path B fix E1 (audit-regulator): each acceptance is independently
    # considered and domain-scoped. The pattern-level trigger logic is the
    # spine; the domain + expiry scope makes every (pattern, domain) record
    # genuinely distinct rather than recycled boilerplate.
    expires_str = expires_at.strftime("%Y-%m-%d")
    justification = (
        f"[{domain_id}] {base_justification} "
        f"Accepted for the {domain_id} service tier only; the {domain_id} service owner "
        f"re-attests at expiry ({expires_str})."
    )
    conditions = (
        f"{base_conditions} Scoped to the {domain_id} domain; automatic review at "
        f"{expires_str} with {domain_id}-owner re-attestation required to renew."
    )

    return [
        {
            "accepted_by_name":     acceptor["name"],
            "accepted_by_title":    acceptor["title"],
            "accepted_by_role":     acceptor["role"],
            "countersigned_by_name":  countersigner["name"],
            "countersigned_by_title": countersigner["title"],
            "countersigned_by_role":  countersigner["role"],
            "accepted_at":          accepted_at.strftime("%Y-%m-%d"),
            "expires_at":           expires_str,
            "justification":        justification,
            "ticket":               _ticket_id(pattern_id, domain_id),
            "conditions":           conditions,
        }
    ]


# ─── Path B fix F · AI-asset linkage (risk-officer #8, CISO, GROK) ──────────
# Findings on model-/agent-relevant patterns link to the specific AI asset in
# the ai_gov inventory (projection _build_ai_gov uses these exact IDs). This
# kills the silo the audit caught: model/agent inventory and findings were
# unconnected. IDs MUST match utils/projection.py:_build_ai_gov.
_MODEL_BY_DOMAIN: Dict[str, str] = {
    "payments": "fraud-screening-v1",
    "trading":  "trade-routing-v2",
    "ai_gov":   "credit-decision-v3",
    "platform": "credit-decision-v3",
    "custody":  "cust-support-bot",
    "identity": "cust-support-bot",
}
_AGENT_BY_DOMAIN: Dict[str, str] = {
    "payments": "billing-agent",
    "platform": "ops-runbook-agent",
    "ai_gov":   "data-egress-agent",
    "trading":  "billing-agent",
    "custody":  "data-egress-agent",
    "identity": "data-egress-agent",
}
# Patterns that touch a model lifecycle (data on a model · model drift ·
# agentic model) link to a model; agentic tool-use links to an agent.
_MODEL_LINK_PATTERNS = {"RP-06", "RP-10", "RP-13"}
_AGENT_LINK_PATTERNS = {"RP-10", "RP-13"}


def ai_asset_link(pattern_id: str, domain_id: str) -> Dict[str, str]:
    """Return {model_id?, agent_id?} for AI-asset-relevant patterns; {} otherwise."""
    out: Dict[str, str] = {}
    if pattern_id in _MODEL_LINK_PATTERNS:
        out["model_id"] = _MODEL_BY_DOMAIN.get(domain_id, "credit-decision-v3")
    if pattern_id in _AGENT_LINK_PATTERNS:
        out["agent_id"] = _AGENT_BY_DOMAIN.get(domain_id, "billing-agent")
    return out


def enrich_finding(finding: Dict, domain_id: str) -> Dict:
    """Add the v1.3.1+v2.0a metadata fields to a finding in place."""
    pid = finding.get("pattern_id", "")
    rag = finding.get("overall_rag", "amber")

    finding["first_detected"]      = first_detected(pid, domain_id, rag)
    finding["time_in_state_days"]  = time_in_state_days(pid, domain_id, rag)
    finding["treatment"]           = treatment_plan(pid, domain_id, rag)
    finding["org_context"]         = org_context(pid)
    finding["financial_exposure"]  = financial_exposure(pid, rag)
    finding["compensating_controls"] = compensating_controls(pid)
    finding["acceptance_trail"]    = acceptance_trail(pid, domain_id, rag, finding["treatment"])
    # v2.0a impact_vector — populated per A3 / per-app-surfaces-face-it-acts-on
    finding["impact_vector"]       = impact_vector_scores(pid, rag)
    # Path B fix F — AI-asset linkage (model_id / agent_id) for model/agentic patterns
    _link = ai_asset_link(pid, domain_id)
    if _link.get("model_id"):
        finding["model_id"] = _link["model_id"]
    if _link.get("agent_id"):
        finding["agent_id"] = _link["agent_id"]
    return finding


# v2.0a impact vector scoring per amendment A3.
# Each pattern has a deterministic per-face score profile. Each face score is
# multiplied by a RAG factor (red=1.0, amber=0.6, green=0.0).
# Each face: {score: 0..10, evidence: str}.

_PATTERN_IMPACT_PROFILES: Dict[str, Dict[str, tuple]] = {
    # pattern_id → face → (red_base_score, evidence_template)
    "RP-01": {
        "financial":      (8, "Bad release events historically convert to revenue / SLA-credit / market-confidence cost — Knight Capital '12 anchor."),
        "operational":    (9, "Deploy regressions directly burn SLO error budget; current change_failure_rate exceeds DORA Medium cluster boundary."),
        "regulatory":     (4, "Material outage may trigger SEC 8-K Item 1.05 qualitative determination."),
        "customer_trust": (6, "Customer-facing services affected; SLA credit / status-page incidents impact trust."),
        "safety":         (1, "No direct safety surface unless paired with safety-critical workload."),
    },
    "RP-02": {
        "financial":      (7, "Sustained availability SLO violation feeds direct SLA credits + customer-trust cost."),
        "operational":    (10, "Availability IS the operational face — SLO + error-budget exhaustion is its definition."),
        "regulatory":     (5, "OCC heightened-standards resilience-event reporting may apply."),
        "customer_trust": (8, "Customer-visible downtime; trust cost compounds quarter-over-quarter."),
        "safety":         (3, "Safety-relevant if availability supports safety-critical workload."),
    },
    "RP-03": {
        "financial":      (4, "Policy gaps rarely 8-K material alone but feed MRA/MRIA escalation costs."),
        "operational":    (3, "Policy drift adds friction; modest direct operational cost."),
        "regulatory":     (8, "OCC 12 CFR 30 App D heightened-standards finding likely on policy gaps."),
        "customer_trust": (3, "Indirect — surfaces as exceedance blast radius only when paired with data event."),
        "safety":         (1, "Indirect via downstream."),
    },
    "RP-04": {
        "financial":      (9, "Vuln exploitation historically converts to large remediation + fine + settlement; Equifax $700M anchor."),
        "operational":    (6, "Emergency patching consumes engineering bandwidth; SLO-degrading rollouts common."),
        "regulatory":     (9, "Active exploitation triggers SEC 8-K + GDPR Art. 33 + CISA BOD obligations."),
        "customer_trust": (7, "Customer-record exceedance narratives dominate brand recovery cost."),
        "safety":         (2, "Indirect; CVE-class-specific."),
    },
    "RP-05": {
        "financial":      (7, "Identity compromise → exfiltration → remediation. Uber 2022 anchor."),
        "operational":    (5, "Incident-response load + privileged-access lockdown."),
        "regulatory":     (8, "GDPR Art. 33 + SOX § 404 ICFR + state breach laws."),
        "customer_trust": (8, "Customer-credential narratives are reputation-defining."),
        "safety":         (2, "Indirect."),
    },
    "RP-06": {
        "financial":      (9, "PII exceedance settlement + regulatory fine compounds. T-Mobile 2023 anchor."),
        "operational":    (4, "DLP / forensics burden but rarely SLO-burning."),
        "regulatory":     (10, "GDPR Art. 33 (72-hour clock) + CCPA + state-level — the regulatory face IS the headline."),
        "customer_trust": (9, "Customer-record exceedance is the worst-case brand event."),
        "safety":         (3, "Where data drives safety decisions, indirect."),
    },
    "RP-07": {
        "financial":      (8, "Supply-chain blast radius — SolarWinds multi-firm remediation cost."),
        "operational":    (6, "Cross-org incident response + vendor escalation."),
        "regulatory":     (9, "EO 14028 SBOM + OCC TPRM + SEC 8-K (SolarWinds-class)."),
        "customer_trust": (6, "Trust cost compounds with vendor concentration."),
        "safety":         (2, "Indirect."),
    },
    "RP-08": {
        "financial":      (5, "Detection gaps extend exceedance lifecycle, multiplying eventual cost."),
        "operational":    (7, "Direct operational gap — can't fix what you can't see."),
        "regulatory":     (6, "FFIEC + OCC heightened-standards examiner findings."),
        "customer_trust": (3, "Indirect."),
        "safety":         (1, "Indirect."),
    },
    "RP-09": {
        "financial":      (6, "Change failures cascade to deploy + outage cost."),
        "operational":    (7, "Emergency-change load + post-hoc review overhead."),
        "regulatory":     (5, "MRA/MRIA on change-control inadequacy."),
        "customer_trust": (4, "Indirect via cascade."),
        "safety":         (2, "Indirect."),
    },
    "RP-10": {
        "financial":      (8, "Model drift in production cost — Zillow $304M anchor."),
        "operational":    (5, "Eval cycle + retraining cost."),
        "regulatory":     (8, "EU AI Act high-risk Art. 9 / 15 + SEC 8-K on financial-impact event."),
        "customer_trust": (7, "AI-driven customer-facing decisions; trust narratives sticky."),
        "safety":         (4, "Where models drive safety, direct."),
    },
    "RP-11": {
        "financial":      (5, "Capacity-driven outage SLA credits + scaling cost."),
        "operational":    (9, "Saturation → outage; direct operational surface."),
        "regulatory":     (5, "Resilience-event reporting if customer-facing."),
        "customer_trust": (6, "Visible to customers when capacity events surface."),
        "safety":         (3, "Indirect."),
    },
    "RP-12": {
        "financial":      (8, "Extended outage (Atlassian '22 14-day) + SLA credits + churn."),
        "operational":    (8, "RTO / runbook gap is the operational face."),
        "regulatory":     (8, "OCC resilience + SEC 8-K on extended customer impact."),
        "customer_trust": (8, "Recovery duration compounds reputation cost."),
        "safety":         (3, "Indirect."),
    },
    "RP-13": {
        "financial":      (7, "Agentic AI mishaps — Samsung 2023 IP exfil + MCP supply-chain $35M anchor."),
        "operational":    (6, "Agent-action incident response + tool-permission re-scoping."),
        "regulatory":     (10, "EU AI Act Art. 9/13/14/15 high-risk system obligations apply directly; GDPR Art. 33 if agent processes PII."),
        "customer_trust": (8, "Agent-mediated customer interaction; trust narratives mediated through agent behaviour."),
        "safety":         (4, "Tool-use scope violations can have direct safety implications in critical workflows."),
    },
}


def impact_vector_scores(pattern_id: str, rag: str) -> Dict[str, Dict[str, Any]]:
    """Per A3 + spec §3.2. Returns a 5-face impact vector with {score, evidence}.

    Each face's red-base score is scaled by the RAG factor (red=1.0, amber=0.6,
    green=0.0). Evidence text is per-pattern and references the specific
    impact mechanism.
    """
    profile = _PATTERN_IMPACT_PROFILES.get(pattern_id)
    if not profile:
        return {
            face: {"score": None, "evidence": "", "face": face}
            for face in ("financial", "operational", "regulatory", "customer_trust", "safety")
        }
    rag_factor = 1.0 if rag == "red" else (0.6 if rag == "amber" else 0.0)
    out = {}
    for face, (red_base, evidence) in profile.items():
        score = round(red_base * rag_factor, 1)
        out[face] = {
            "face":     face,
            "score":    score,
            "max":      10,
            "evidence": evidence,
        }
    return out
