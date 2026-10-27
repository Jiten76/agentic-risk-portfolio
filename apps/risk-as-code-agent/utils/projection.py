"""
projection — the v2.0a engine.

Pure function `make_projection(report, history) -> Dict`.

Emits ONE role-agnostic JSON projection of the risk graph. Thin role apps
(`templates/apps/ai_gov.py`, `templates/apps/generic_register.py`) consume
this projection — they do not re-read the pipeline output.

This is the architectural correction that retracted v1.4. v1.4 hand-
serialized 16 panels from the pipeline output, producing 1.27 MB of
duplicated content. v2.0a builds the projection once and renders thin
apps on top.

Canonical shape (governed by `reviews/v2_0a_spec.md` §2 +
`reviews/v2_0a_spec_amendments.md` A2 / A3 / A6 / A8 / A9):

  {
    "meta": { ... },
    "domains": { domain_id: { ..., findings: [...] } },
    "cascade_graph": { "edges": [...] },
    "exposure": { "by_pattern": {...}, "portfolio_total": {...} },
    "materiality": { "sec_8k_item_1_05": {
            "applicability": "applies — US public registrant (assumed)",...}, ... },
    "action_log_path": "data/action_log.jsonl",
    "history": [ { period, total_findings, overall_rag }, ... ]
  }

Per-value provenance (A2): every numeric value carries
`{ value, source_status, source_system, source_query, source_timestamp,
   computation, assumptions }`.

`source_status` is tri-state per A2:
  - "real_query_real_data"        — value from a real query against real data
  - "real_query_synthesized_data" — value from a real query against synthesized data
  - "illustrative"                — value hand-set as illustrative

v2.0a step 1: shape locked, provenance + impact_vector + exposure
populated as skeletons; later steps fill them in.
"""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.history_synthesizer import overall_trajectory
from data.finding_metadata import enrich_finding
from utils.exposure import portfolio_exposure
from utils.action_log import action_log_summary
from utils.primitives import (
    scope_for_pattern,
    cascade_for_finding,
    correlation_for_pattern,
    domain_skew,
    trajectory_delta,
    forecast_next_period,
)


# ── pattern lookup (cascade_to / cascade_from / materiality_trigger live here) ─

_PATTERNS_FILE = Path(__file__).resolve().parent.parent / "data" / "risk_patterns.json"


def _load_patterns() -> Dict[str, Dict[str, Any]]:
    """Pattern definitions, keyed by pattern_id. Cascade rules + materiality
    triggers live here (not on the finding)."""
    raw = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in raw.get("patterns", [])}


_PATTERNS = _load_patterns()


PROJECTION_SCHEMA_VERSION = "1.0"
# v2.0a-alpha4: this is the single source of truth for the artefact version.
# The renderer reads it from projection.meta.artefact_version — no hardcoded
# constant in the renderer. Bump here only.
#
# alpha4 makes the renderer JS-driven from the embedded projection (the prior
# alpha3 "drift cannot happen here" claim was actually drift detection +
# manual reconciliation; alpha4 makes it true).
ARTEFACT_VERSION = "v2.0a-alpha4"


# ── provenance helpers — extracted to portfolio_core.provenance (port spec §15.E)
# Aliased to the original private names so every call site below is unchanged
# (behavior-preserving). The shared helpers are the source of truth.
from portfolio_core.provenance import (  # noqa: E402
    illustrative_provenance as _illustrative_provenance,
    provenance_for_threshold as _provenance_for_threshold,
    value_with_provenance as _value_with_provenance,
)


# ── per-finding skeleton fillers (steps 2/3 populate later) ──────────────────

def _impact_vector_wrapped(raw_vector: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Wrap each face with provenance per A2. Raw vector comes from
    data.finding_metadata.impact_vector_scores; we add provenance per face."""
    out = {}
    for face, payload in (raw_vector or {}).items():
        out[face] = {
            "score":      payload.get("score"),
            "max":        payload.get("max", 10),
            "evidence":   payload.get("evidence", ""),
            "provenance": _illustrative_provenance(
                source_system="data.finding_metadata::impact_vector_scores",
                source_query=f"pattern × rag → {face} face",
                computation=f"Per-pattern profile × RAG factor (red=1.0, amber=0.6, green=0.0). Face '{face}' surfaced per amendment A3.",
                assumptions=["Profile is illustrative; production replaces with site-calibrated weights."],
            ),
        }
    return out


# ── cascade graph ────────────────────────────────────────────────────────────

def _cascade_graph(report: Dict[str, Any]) -> Dict[str, Any]:
    """Per spec §3.5 + amendment A6.

    Edges are classified as 'structural' (mechanism-cited, no data needed) or
    'empirical' (require co-occurrence history). v2.0a step 6 will refine the
    classification on the pattern-data side; here we surface what's already
    in the cascade_to / cascade_from blocks plus the firing flag.
    """
    # which patterns are currently firing
    firing = set()
    for dr in report.get("domain_reports", {}).values():
        for f in dr.get("findings", []):
            firing.add(f.get("pattern_id"))

    # Cascade rules live on the PATTERN definition (risk_patterns.json),
    # not on the finding. Iterate the pattern catalog.
    edges: List[Dict[str, Any]] = []
    seen = set()
    for src_pid, pattern in _PATTERNS.items():
        for edge in pattern.get("cascade_to", []) or []:
            dst_pid = edge.get("pattern_id")
            key = (src_pid, dst_pid)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "from":              src_pid,
                "to":                dst_pid,
                # Step 6 will refine; for now any edge with a cited rationale = structural
                "edge_type":         "structural" if edge.get("rationale") else "empirical",
                "mechanism":         edge.get("rationale", ""),
                "strength":          edge.get("strength", ""),
                "currently_firing":  src_pid in firing and dst_pid in firing,
                "provenance":        _illustrative_provenance(
                    source_system="risk_patterns.json",
                    source_query="cascade_to block",
                    computation="Edge classification — v2.0a step 6 will refine structural/empirical split per A6.",
                ),
            })
    return {"edges": edges, "firing_patterns": sorted(firing)}


# ── exposure skeleton (step 2 populates) ─────────────────────────────────────

def _exposure_block(report: Dict[str, Any]) -> Dict[str, Any]:
    """Per spec §3.1 + amendment A3 — frequency-aware expected loss.

    v2.0a step 2: real population via utils.exposure.portfolio_exposure.
    Replaces v1.4's three-methodology hack with one distribution
    (P50 expected / P95 stress / worst-anchor tail).
    """
    portfolio = portfolio_exposure(report)
    # Attach provenance to the headline numbers per A2
    portfolio["portfolio_total"]["provenance"] = _illustrative_provenance(
        source_system="data/risk_patterns.json::exposure_model",
        source_query="Σ over firing patterns of frequency × severity × rag_factor",
        computation=portfolio["portfolio_total"]["computation"],
        assumptions=[
            "Frequencies and severities are illustrative per-pattern profiles.",
            "Production calibrates frequencies from internal incident-rate history.",
            "Production calibrates severities from internal incident-cost history.",
            "RAG factor (red=1.0, amber=0.6, green=0.0) is a portfolio-aggregation weight.",
        ],
    )
    return portfolio


# ── materiality with article-level citations (A9) ────────────────────────────

def _materiality_state(report: Dict[str, Any]) -> Dict[str, Any]:
    """Per A9, regulatory citations are article-level, not framework-name-only.

    Step 9 wires the qualitative-determination workflow per A7. Step 1
    establishes the shape with proper citations.
    """
    # Which patterns are currently firing
    firing = set()
    for dr in report.get("domain_reports", {}).values():
        for f in dr.get("findings", []):
            firing.add(f.get("pattern_id"))

    # Pull materiality_trigger from each firing pattern
    triggered_sec_8k = []
    triggered_occ = []
    triggered_gdpr = []
    triggered_eu_ai_act = []
    conditional_8k = []

    # Materiality triggers live on the PATTERN definition, not on the finding.
    # Look up by firing pattern_id.
    # Round-8 depth pass: the reg set a GLOBAL fintech actually faces. Flags are
    # judgment mappings on the pattern definitions; each block below carries an
    # honest applicability caveat (licence-dependent — EU entity, UK authorisation,
    # NY BitLicense/money-transmitter, card-scheme contract).
    triggered_dora = []
    triggered_fca = []
    triggered_nydfs = []
    triggered_pci = []
    # E3 — the broker-dealer regimes (user: "will this stand FINRA?")
    triggered_finra = []
    triggered_17a4 = []
    triggered_sci = []
    for pid in firing:
        mat = (_PATTERNS.get(pid) or {}).get("materiality_trigger", {}) or {}
        if mat.get("sec_8k") is True:
            triggered_sec_8k.append(pid)
        elif mat.get("sec_8k") == "conditional":
            conditional_8k.append(pid)
        if mat.get("occ_12cfr30") is True:
            triggered_occ.append(pid)
        if mat.get("gdpr_art33") is True:
            triggered_gdpr.append(pid)
        if mat.get("eu_ai_act") is True:
            triggered_eu_ai_act.append(pid)
        if mat.get("dora") is True:
            triggered_dora.append(pid)
        if mat.get("fca_opres") is True:
            triggered_fca.append(pid)
        if mat.get("nydfs_500") is True:
            triggered_nydfs.append(pid)
        if mat.get("pci_dss") is True:
            triggered_pci.append(pid)
        if mat.get("finra_4370") is True:
            triggered_finra.append(pid)
        if mat.get("sea_17a4") is True:
            triggered_17a4.append(pid)
        if mat.get("reg_sci") is True:
            triggered_sci.append(pid)

    return {
        "sec_8k_item_1_05": {
            "applicability": "applies — US public registrant (assumed)",
            "regulation_citation": "17 CFR 229.106(b)–(c) · Form 8-K Item 1.05",
            "model":               "qualitative_determination",
            "clock_days_from_determination": 4,
            "clock_basis":         "business days from the date the registrant determines the incident is material",
            "trigger_logic":       "qualitative reasonable-investor standard — triggered when a firing pattern presents facts a reasonable investor would consider material",
            "triggered_patterns":      sorted(set(triggered_sec_8k)),
            "conditional_patterns": sorted(set(conditional_8k)),
            "status":              "TRIGGERED" if triggered_sec_8k else ("CONDITIONAL" if conditional_8k else "CLEAR"),
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="SEC 8-K Item 1.05 qualitative determination per 17 CFR 229.106. Per A7 + A9, no dollar gate; workflow surfaces facts a reasonable investor would consider.",
            ),
        },
        "occ_12cfr30_app_d": {
            "applicability": "ILLUSTRATIVE STYLE-MAPPING — App D binds large national banks, not this archetype",
            "regulation_citation": "12 CFR 30 Appendix D § II.M and § III",
            "model":               "heightened_standards_reporting",
            "triggered_patterns":      sorted(set(triggered_occ)),
            "status":              "TRIGGERED" if triggered_occ else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation=(
                    "ILLUSTRATIVE heightened-standards-STYLE mapping, not a claim of legal "
                    "applicability: 12 CFR 30 Appendix D formally binds large insured national "
                    "banks above the OCC's heightened-standards thresholds, not a ~$2-4B "
                    "consumer/crypto fintech. The broad trigger set (most operational patterns) "
                    "demonstrates the board-level risk-reporting DISCIPLINE App D codifies — "
                    "production would map to the firm's actual prudential perimeter (state "
                    "trust charter, FRB supervision tier, or none)."
                ),
            ),
        },
        "gdpr_art_33": {
            "applicability": "applies — EU personal data processed",
            "regulation_citation": "GDPR Reg. 2016/679 Art. 33(1)–(5)",
            "model":               "72_hour_notification_to_supervisory_authority",
            "clock_hours_from_awareness": 72,
            "triggered_patterns":      sorted(set(triggered_gdpr)),
            "status":              "TRIGGERED" if triggered_gdpr else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="GDPR Art. 33(1) — 72-hour notification to supervisory authority for personal-data breach.",
            ),
        },
        "eu_ai_act_high_risk": {
            "applicability": "applies if the credit/AI system is classified high-risk (assumed)",
            "regulation_citation": "EU AI Act Reg. 2024/1689 Art. 9 / 10 / 13 / 14 / 15 / 17 / 26 / 73",
            "model":               "high_risk_system_obligations",
            "triggered_patterns":      sorted(set(triggered_eu_ai_act)),
            "status":              "TRIGGERED" if triggered_eu_ai_act else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="EU AI Act high-risk-system obligations — Art. 9 risk management, Art. 10 data governance, Art. 13 transparency, Art. 14 human oversight, Art. 15 accuracy + cybersecurity.",
            ),
        },
        "eu_dora_ict": {
            "applicability": "applies if EU-authorised entity (EMI/MiFID licence assumed)",
            "regulation_citation": "EU 2022/2554 (DORA) Art. 17–19 · major ICT incident reporting",
            "model":               "major_ict_incident_classification_and_report",
            "clock_hours_from_classification": 4,
            "clock_basis":         "initial notification within 4h of classifying the incident as major (and no later than 24h from awareness); intermediate + final reports follow (RTS timelines)",
            "triggered_patterns":      sorted(set(triggered_dora)),
            "status":              "TRIGGERED" if triggered_dora else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation=(
                    "ILLUSTRATIVE mapping assuming an EU-authorised operating entity (EMI/"
                    "MiFID licence) — DORA applies to the EU entity's ICT risk, wherever the "
                    "platform runs. The trigger set is deliberately broad "
                    "because DORA IS the EU ICT-risk framework: incident management (Art. 17), "
                    "classification (Art. 18), reporting (Art. 19), plus ICT third-party risk "
                    "(Art. 28 — RP-07). Production would scope to the licensed entity's "
                    "critical-or-important functions register."
                ),
            ),
        },
        "uk_fca_opres": {
            "applicability": "applies if UK-authorised with payments as an Important Business Service (assumed)",
            "regulation_citation": "FCA PS21/3 · PRA SS1/21 · operational resilience — impact tolerances",
            "model":               "important_business_service_tolerance_breach",
            "triggered_patterns":      sorted(set(triggered_fca)),
            "status":              "TRIGGERED" if triggered_fca else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation=(
                    "ILLUSTRATIVE mapping assuming a UK-authorised entity with payments "
                    "designated an Important Business Service. A tolerance breach (e.g. "
                    "payment-service disruption beyond the board-set impact tolerance) drives "
                    "board engagement and regulator notification. Mapped narrowly to the "
                    "availability/capacity/recovery patterns (RP-02, RP-11, RP-12) — impact "
                    "tolerances are about service continuity, not general control health."
                ),
            ),
        },
        "nydfs_500": {
            "applicability": "applies if NYDFS-covered (BitLicense / NY MTL assumed)",
            "regulation_citation": "23 NYCRR 500.17 · cybersecurity-event notice (72h)",
            "model":               "cyber_event_72h_notification",
            "clock_hours_from_determination": 72,
            "triggered_patterns":      sorted(set(triggered_nydfs)),
            "status":              "TRIGGERED" if triggered_nydfs else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation=(
                    "ILLUSTRATIVE mapping assuming NYDFS-covered status (BitLicense or NY "
                    "money-transmitter licence — typical for a US consumer/crypto fintech). "
                    "500.17 requires notice to the superintendent within 72h of determining a "
                    "reportable cybersecurity event; mapped to the security patterns (RP-04 "
                    "vulnerability, RP-05 access, RP-06 data exposure). Annual 500.17(b) "
                    "certification pressure is what makes weak controls here board-visible."
                ),
            ),
        },
        "finra_4370": {
            "applicability": "applies if FINRA-member broker-dealer (the archetype's retail brokerage line assumes a BD subsidiary)",
            "regulation_citation": "FINRA Rule 4370 (Business Continuity Plans & Emergency Contact Information)",
            "model":               "resilience_obligation",
            "trigger_logic":       "availability / recovery / third-party patterns threaten the BD's ability to meet customer obligations — the exact scope of the 4370 BCP",
            "triggered_patterns":      sorted(set(triggered_finra)),
            "status":              "TRIGGERED" if triggered_finra else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="FINRA 4370 requires a BCP reasonably designed to meet obligations to customers through significant business disruption — mapped from availability/recovery/vendor patterns.",
            ),
        },
        "sea_17a4": {
            "applicability": "applies to the broker-dealer's required records — the hash-chained action log IS this artifact's shape (immutable, timestamped, attributable); production adds the retention schedule + D3P designee",
            "regulation_citation": "SEA Rule 17a-4 (17 CFR 240.17a-4) · books & records preservation",
            "model":               "records_preservation",
            "trigger_logic":       "patterns threatening record completeness/integrity (data exposure, unauthorized change, observability gaps) threaten the 17a-4 preservation obligation",
            "triggered_patterns":      sorted(set(triggered_17a4)),
            "status":              "TRIGGERED" if triggered_17a4 else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="17a-4 requires preservation of required records in a manner with audit-trail integrity (2022 amendments allow audit-trail alternative to WORM) — the platform's hash-chained, append-only action log is exactly that shape.",
            ),
        },
        "reg_sci": {
            "applicability": "ILLUSTRATIVE CONDITIONAL — Reg SCI binds SCI ENTITIES (SROs, plan processors, ATSs above volume thresholds); a retail BD is typically NOT an SCI entity unless its ATS crosses thresholds. Mapped as a discipline STYLE, not a claim of applicability",
            "regulation_citation": "Reg SCI (17 CFR 242.1000–1007) · systems capacity, integrity, resiliency, availability, security",
            "model":               "systems_integrity_style",
            "trigger_logic":       "SCI's own five properties — capacity, integrity, resiliency, availability, security — map directly onto the deploy/availability/vuln/capacity/recovery patterns",
            "triggered_patterns":      sorted(set(triggered_sci)),
            "status":              "TRIGGERED" if triggered_sci else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation="Reg SCI discipline mapping (style, like OCC App D): the five SCI systems properties against the firing patterns; the SCI-entity determination is reserved to Legal/Compliance.",
            ),
        },
        "pci_dss_v4": {
            "applicability": "contractual (card schemes), not statute — CDE scope only",
            "regulation_citation": "PCI-DSS v4.0 (card-scheme contractual, not statute)",
            "model":               "cde_control_requirements",
            "triggered_patterns":      sorted(set(triggered_pci)),
            "status":              "TRIGGERED" if triggered_pci else "CLEAR",
            "provenance":          _illustrative_provenance(
                source_system="risk_patterns.json::materiality_trigger",
                computation=(
                    "HONEST FRAMING: PCI-DSS is a contractual card-scheme obligation, not a "
                    "regulation — but its consequences (fines via acquirer, loss of processing) "
                    "are as real as statute for a payments business. Mapped to cardholder-data-"
                    "environment patterns: RP-04 (Req 6/11 vuln mgmt + testing), RP-05 (Req 7/8 "
                    "access + MFA), RP-06 (Req 3 stored-data protection). Scope is the CDE only "
                    "— production would carry the segmentation boundary, not the whole platform."
                ),
            ),
        },
    }


# ── per-domain projection ────────────────────────────────────────────────────

def _project_finding(
    finding: Dict[str, Any],
    domain_id: str,
    report: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Project a single finding into the canonical projection shape."""
    pid = finding.get("pattern_id", "")

    # Wrap each breached signal with provenance per A2
    signals_exceeded = {}
    for sname, sdetail in (finding.get("signals_exceeded") or {}).items():
        if isinstance(sdetail, dict):
            signals_exceeded[sname] = {
                "value":     sdetail.get("value"),
                "rag":       sdetail.get("rag"),
                "threshold": sdetail.get("threshold"),
                "threshold_provenance": _provenance_for_threshold(
                    finding.get("threshold_source", ""),
                    finding.get("threshold_source_url", ""),
                ),
                "value_provenance":     _illustrative_provenance(
                    source_system="mock_metrics",
                    source_query=f"generate_domain_snapshot({domain_id})::{sname}",
                    computation=f"Synthesised by data.mock_metrics; v2.0a step 4 will wire real telemetry per A2.",
                    assumptions=[
                        "Synthesised pipeline output; tri-state source_status = 'illustrative'",
                    ],
                ),
            }

    scope = scope_for_pattern(report, pid)
    cascade = cascade_for_finding(report, pid)
    correlation = correlation_for_pattern(history, pid) if history else []

    return {
        "finding_id":          f"FIND-{report.get('period', '?')}-{domain_id}-{pid}",
        "pattern_id":          pid,
        "pattern_name":        finding.get("pattern_name", ""),
        "pattern_description": finding.get("pattern_description", ""),
        "nist_function":       finding.get("nist_function", ""),
        "domain_id":           domain_id,
        "overall_rag":         finding.get("overall_rag", "amber"),
        # Temporal fields carry the same provenance envelope atg uses — one honesty
        # discipline across the portfolio (round-6 external finding: rac shipped bare
        # date strings while atg wrapped the identical concept). Status is
        # `illustrative`, NOT atg's `derived`: atg derives first_detected from real
        # trace timestamps; this spoke's input is synthetic, so the date is a
        # reproducible illustrative anchor and says so.
        "first_detected": {
            "value": finding.get("first_detected", "—"),
            "provenance": {
                "source_status":    "illustrative",
                "source_system":    "data/finding_metadata.py::first_detected",
                "source_query":     "deterministic illustrative anchor (stable per finding)",
                "computation": (
                    "NOT observed telemetry — reproducible synthetic anchor (red "
                    "findings read older, amber newer). Contrast agent-trace-gov, "
                    "which derives first_detected as min(trace.timestamp) over real "
                    "traces; this spoke has no timestamps to derive from."
                ),
                "assumptions": ["synthetic anchor date; disclosed via banner + provenance"],
            },
        },
        "time_in_state_days":  finding.get("time_in_state_days", 0),
        "signals_exceeded":    signals_exceeded,
        "scope":               scope,
        "cascade": {
            "upstream_firing":   cascade.get("upstream_firing", []),
            "downstream_firing": cascade.get("downstream_firing", []),
        },
        "correlation":         correlation,
        "impact_vector":       _impact_vector_wrapped(finding.get("impact_vector", {})),
        "treatment":           finding.get("treatment", {}),
        "rating_state":        _rating_state(finding, _AS_OF_FOR_STATES),
        # Organizational reality (illustrative): why remediation actually stalls,
        # who is accountable, where the decision gets made, what escalating costs.
        "org_context":         finding.get("org_context", {}),
        "compensating_controls": finding.get("compensating_controls", []),
        "acceptance_trail":    finding.get("acceptance_trail", []),
        "anchoring_incidents": finding.get("incident_reference", []),
        "appetite":            finding.get("appetite", ""),
        # Path B fix F · AI-asset linkage passthrough (set by enrich_finding)
        "model_id":            finding.get("model_id"),
        "agent_id":            finding.get("agent_id"),
    }


def _project_domain(
    domain_id: str,
    domain_report: Dict[str, Any],
    report: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Project a domain (including its findings) into canonical shape."""
    findings = [
        _project_finding(f, domain_id, report, history)
        for f in domain_report.get("findings", [])
    ]
    return {
        "domain_id":          domain_id,
        "domain_name":        domain_report.get("domain_name", domain_id),
        "tier":               domain_report.get("tier"),
        "overall_rag":        domain_report.get("overall_rag", "green"),
        "red_findings":       domain_report.get("red_findings", 0),
        "amber_findings":     domain_report.get("amber_findings", 0),
        "total_findings":     domain_report.get("total_findings", 0),
        "patterns_assessed":  domain_report.get("patterns_assessed", 0),
        "findings":           findings,
        "executive_summary":  domain_report.get("executive_summary", ""),
        "attestation_statement": domain_report.get("attestation_statement", ""),
    }


# ── history projection ───────────────────────────────────────────────────────

def _project_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per period — minimal shape for trajectory rendering."""
    if not history:
        return []
    out = []
    for snap in history:
        out.append({
            "period":         snap.get("period", "—"),
            "overall_rag":    snap.get("overall_rag", "green"),
            "total_findings": snap.get("total_findings", 0),
            "synthesized":    snap.get("_synthesized", True),
        })
    return out


# ── action log reference (step 5 populates the writer; step 1 declares path) ─

def _action_log_ref() -> Dict[str, Any]:
    """Per A1, verbs append to data/action_log.jsonl on disk.
    v2.0a step 5: read existing entries via utils.action_log."""
    summary = action_log_summary()
    return {
        "path":              summary["path"],
        "schema_version":    summary["schema_version"],
        "schema_note":       "Per A1: actor_name + actor_handle + actor_role + actor_role_tier, verb, target_type/id/name, timestamp, justification (≥12 words), expiry, review_cadence_days, dissenting_voice, linked_findings, thresholds_at_time, previous_action_hash + this_action_hash. Hash-chained append-only.",
        "total_entries":     summary["total_entries"],
        "chain_status":      summary["chain_status"],
        "chain_detail":      summary["chain_detail"],
        "recent_entries":    summary["recent_entries"],
        "verbs_supported":   summary["verbs_supported"],
        "role_tiers":        summary["role_tiers"],
        "justification_min_words": summary["justification_min_words"],
    }


# ── portfolio counts (single source of truth carried from v1.3.1) ───────────

def _portfolio_counts(report: Dict[str, Any]) -> Dict[str, int]:
    """Single source of truth for counts. Hero rendering reads this."""
    findings = []
    for dr in report.get("domain_reports", {}).values():
        for f in dr.get("findings", []):
            findings.append(f)
    f_red   = sum(1 for f in findings if f.get("overall_rag") == "red")
    f_amber = sum(1 for f in findings if f.get("overall_rag") == "amber")
    f_green = sum(1 for f in findings if f.get("overall_rag") == "green")
    domains = report.get("domain_reports", {})
    d_red   = sum(1 for d in domains.values() if d.get("overall_rag") == "red")
    d_amber = sum(1 for d in domains.values() if d.get("overall_rag") == "amber")
    d_green = sum(1 for d in domains.values() if d.get("overall_rag") == "green")
    return {
        "findings_total": len(findings),
        "findings_red":   f_red,
        "findings_amber": f_amber,
        "findings_green": f_green,
        "domains_total":  len(domains),
        "domains_red":    d_red,
        "domains_amber":  d_amber,
        "domains_green":  d_green,
    }


# ── M1 additions — alpha4 warm-terminal UI inputs ───────────────────────────
#
# Five new top-level blocks per the M1 brief. All marked source_status =
# "illustrative" per amendment A2 since no telemetry is wired yet. Names
# are GENERIC engineering taxonomy (no employer-internal nomenclature).
# Additive only — no existing key renamed or removed.


def _build_actuals() -> Dict[str, Any]:
    """Block 1 — 12-month real-event window (S0/S1/outages/near-misses)."""
    return {
        "window_months":   12,
        "source_status":   "illustrative",
        "source_note":     "In production sourced from PagerDuty / Incident.io / internal SEV log.",
        "counts": {
            "s0_incidents":         0,
            "s1_incidents":         2,
            "outages_over_10min":   4,
            "near_misses":          17,
        },
        "mttd_median_min": 14,
        "mttr_median_h":   2.4,
        "events": [
            {
                "date":       "2026-03-14",
                "severity":   "S1",
                "pattern_id": "RP-09",
                "domain":     "platform",
                "team":       "platform-sre",
                "mttd_min":   12,
                "mttr_h":     1.8,
                "summary":    "Emergency-change rollback delay in payments deploy",
            },
            {
                "date":       "2026-05-22",
                "severity":   "S1",
                "pattern_id": "RP-04",
                "domain":     "payments",
                "team":       "payments-core",
                "mttd_min":   18,
                "mttr_h":     3.2,
                "summary":    "KEV-listed CVE remediation slipped past SLA on 2 services",
            },
        ],
    }


def _build_clusters() -> Dict[str, Any]:
    """Block 2 — recurrence per pattern with cluster-flag rule.

    One entry per RP-01..RP-13. Called-out patterns per brief; remaining
    7 filled with plausible illustrative counts (mostly 0–2).
    """
    by_pattern = [
        # called-out per brief
        {"pattern_id": "RP-09", "events_12mo": 8, "last_90d": 3, "is_cluster": True,
         "rag": "critical",   "note": "payments + platform overlap"},
        {"pattern_id": "RP-04", "events_12mo": 4, "last_90d": 1, "is_cluster": False,
         "rag": "watch",    "note": "steady"},
        {"pattern_id": "RP-01", "events_12mo": 3, "last_90d": 0, "is_cluster": False,
         "rag": "watch",    "note": "improving · Q-over-Q -1"},
        {"pattern_id": "RP-13", "events_12mo": 1, "last_90d": 1, "is_cluster": False,
         "rag": "watch",    "note": "first observation"},
        {"pattern_id": "RP-10", "events_12mo": 0, "last_90d": 0, "is_cluster": False,
         "rag": "evidence", "note": "coverage clean"},
        {"pattern_id": "RP-11", "events_12mo": 0, "last_90d": 0, "is_cluster": False,
         "rag": "evidence", "note": "DR-tested"},
        # remaining 7 — kept honest, mostly 0–2
        {"pattern_id": "RP-02", "events_12mo": 2, "last_90d": 1, "is_cluster": False,
         "rag": "watch",    "note": "SLO burn within budget"},
        {"pattern_id": "RP-03", "events_12mo": 1, "last_90d": 0, "is_cluster": False,
         "rag": "watch",    "note": "single CAB-bypass · audited"},
        {"pattern_id": "RP-05", "events_12mo": 2, "last_90d": 1, "is_cluster": False,
         "rag": "watch",    "note": "access-drift on quarterly review"},
        {"pattern_id": "RP-06", "events_12mo": 2, "last_90d": 1, "is_cluster": False,
         "rag": "watch",    "note": "eval-gate coverage gap"},
        {"pattern_id": "RP-07", "events_12mo": 0, "last_90d": 0, "is_cluster": False,
         "rag": "evidence", "note": "lineage registry complete"},
        {"pattern_id": "RP-08", "events_12mo": 1, "last_90d": 0, "is_cluster": False,
         "rag": "watch",    "note": "single near-miss · DLP caught"},
        {"pattern_id": "RP-12", "events_12mo": 0, "last_90d": 0, "is_cluster": False,
         "rag": "evidence", "note": "no repeat-incident pattern"},
    ]
    return {
        "source_status": "illustrative",
        "cluster_rule":  "≥3 events on same pattern within 90 days on overlapping teams",
        "by_pattern":    by_pattern,
    }


# ─── Path B M1 fix · A1 · groups derive from actual findings ────────────────
# Deterministic domain → team / function mapping. Production sources from
# service-catalog (Backstage / internal); illustrative-but-stable here.
_DOMAIN_TEAM = {
    "ai_gov":   "ai-platform",
    "trading":  "trading-platform",
    "payments": "payments-core",
    "custody":  "platform-sre",
    "identity": "security-engineering",
    "platform": "platform-sre",
}
_DOMAIN_FUNCTION = {
    "ai_gov":   "engineering",
    "trading":  "engineering",
    "payments": "engineering",
    "custody":  "data-platform",
    "identity": "security-engineering",
    "platform": "engineering",
}
# AI-pattern findings map to specific model products. Non-AI findings fall
# back to a per-domain product name.
_PATTERN_PRODUCT_AI = {
    "RP-06": "credit-decision-v3",
    "RP-10": "credit-decision-v3",
    "RP-13": "credit-decision-v3",
}
_DOMAIN_PRODUCT_FALLBACK = {
    "ai_gov":   "ai-platform-shared",
    "trading":  "trade-routing-v2",
    "payments": "payments-api",
    "custody":  "custody-platform",
    "identity": "identity-platform",
    "platform": "platform-infra",
}
_OWNER_BY_TEAM = {
    "ai-platform":          ("D. Patel",   "1LoD"),
    "payments-core":        ("L. Tran",    "1LoD"),
    "trading-platform":     ("S. Khoury",  "2LoD"),
    "platform-sre":         ("J. Mendes",  "1LoD"),
    "security-engineering": ("M. Okonkwo", "2LoD"),
}
_OWNER_BY_FUNCTION = {
    "engineering":          ("VP Eng",        "1LoD"),
    "data-platform":        ("Sr Dir Data",   "1LoD"),
    "security-engineering": ("CISO",          "2LoD"),
}
_OWNER_BY_PRODUCT = {
    "credit-decision-v3":  ("D. Patel",   "1LoD"),
    "payments-api":        ("L. Tran",    "1LoD"),
    "trade-routing-v2":    ("S. Khoury",  "2LoD"),
    "custody-platform":    ("J. Mendes",  "1LoD"),
    "identity-platform":   ("M. Okonkwo", "2LoD"),
    "platform-infra":      ("J. Mendes",  "1LoD"),
    "ai-platform-shared":  ("D. Patel",   "1LoD"),
}


def _iterate_report_findings(report: Dict[str, Any]):
    """Yield (domain_id, finding) for each finding in the report.

    Report may carry domains as a dict (projection-side) or a list of
    {domain_id, findings, ...} (raw-side). Handle both.
    """
    domains = report.get("domains")
    if isinstance(domains, dict):
        items = domains.items()
    elif isinstance(domains, list):
        items = [(d.get("domain_id") or d.get("id"), d) for d in domains]
    else:
        return
    for did, dom in items:
        if isinstance(dom, dict):
            for f in dom.get("findings", []) or []:
                yield did, f


def _build_groups(report: Dict[str, Any], inherent_residual: Dict[str, Any]) -> Dict[str, Any]:
    """Block 3 · M1 rebuild (Path B fix A1, risk-officer #1) — group drill-down
    derived from the actual findings list, not literal dicts. Counts now
    reconcile to meta.counts.findings_total by construction.

    Inherent + residual per group = Σ over unique firing patterns of the
    per-pattern inherent/residual carried in `inherent_residual.by_pattern`.
    Pattern contributes once per group regardless of how many findings of that
    pattern fire in that group — pattern-level exposure is the modeling
    primitive (frequency × severity decomposed per pattern, not per finding).
    """
    per_pat = {r["pattern_id"]: r for r in inherent_residual.get("by_pattern", [])}

    def init_group():
        return {
            "finding_count":  0,
            "_pattern_set":   set(),
            "inherent":       {"p50": 0, "p95": 0},
            "residual":       {"p50": 0, "p95": 0},
        }

    by_team: Dict[str, Dict[str, Any]] = {}
    by_function: Dict[str, Dict[str, Any]] = {}
    by_product: Dict[str, Dict[str, Any]] = {}

    for did, f in _iterate_report_findings(report):
        pat = f.get("pattern_id")
        team = _DOMAIN_TEAM.get(did, "platform-sre")
        fn   = _DOMAIN_FUNCTION.get(did, "engineering")
        prod = _PATTERN_PRODUCT_AI.get(pat) or _DOMAIN_PRODUCT_FALLBACK.get(did, "platform-infra")
        for bucket, key in [(by_team, team), (by_function, fn), (by_product, prod)]:
            if key not in bucket:
                bucket[key] = init_group()
            g = bucket[key]
            g["finding_count"] += 1
            if pat and pat not in g["_pattern_set"]:
                g["_pattern_set"].add(pat)
                pir = per_pat.get(pat, {})
                inh = pir.get("inherent", {})
                res = pir.get("residual", {})
                g["inherent"]["p50"] += inh.get("p50", 0)
                g["inherent"]["p95"] += inh.get("p95", 0)
                g["residual"]["p50"] += res.get("p50", 0)
                g["residual"]["p95"] += res.get("p95", 0)

    def finalize(bucket, owner_map):
        rows = []
        for name, g in bucket.items():
            owner, role = owner_map.get(name, ("—", "—"))
            rows.append({
                "name":          name,
                "owner":         owner,
                "owner_role":    role,
                "finding_count": g["finding_count"],
                "inherent":      g["inherent"],
                "residual":      g["residual"],
            })
        return sorted(rows, key=lambda r: -r["finding_count"])

    return {
        "source_status": "real_query_synthesized_data",
        "source_note": (
            "Counts derived from report.domains[*].findings. Domain → team/"
            "function/product mapping is illustrative (production uses "
            "service-catalog — Backstage / internal). Per-group inherent "
            "and residual aggregated from inherent_residual.by_pattern "
            "across unique firing patterns in each group (pattern-level "
            "exposure model; one contribution per pattern per group)."
        ),
        "domain_team_map":     dict(_DOMAIN_TEAM),
        "domain_function_map": dict(_DOMAIN_FUNCTION),
        "by_team":     finalize(by_team,     _OWNER_BY_TEAM),
        "by_function": finalize(by_function, _OWNER_BY_FUNCTION),
        "by_product":  finalize(by_product,  _OWNER_BY_PRODUCT),
    }


# ─── NIST CSF 2.0 function classifier — keyword → function mapping ──────────
# Each compensating control (by name) is classified into one of the 5 CSF
# functions. Coverage per function = mean effectiveness of in-place controls
# classified there, penalised by the share of gaps.
_CSF_KEYWORDS = {
    "identify": ["inventory", "registry", "catalog", "discovery", "lineage",
                 "dataset version", "asset", "sbom"],
    "protect":  ["hitl", "gate", "scope-enforce", "scope-based", "patch",
                 "hash-pin", "waf", "virtual patch", "encryption", "mfa",
                 "provisioning", "segmentation", "canary", "cab", "review",
                 "classifier", "blue-green", "circuit breaker", "capability",
                 "admission", "break-glass", "jit", "just-in-time", "slo budget"],
    "detect":   ["scanner", "drift", "linter", "audit log", "exfil",
                 "detection", "monitor", "kev", "telemetry", "behavioral",
                 "test suite", "adversarial", "eval", "scan"],
    "respond":  ["rollback", "runbook", "kill-switch", "kill switch",
                 "retries", "fallback", "incident", "action-item", "post-mortem",
                 "override audit"],
    "recover":  ["dr ", "dr exercise", "backup", "failover", "multi-region",
                 "restore", "tabletop", "bcp", "recovery"],
}


def _classify_control_to_csf(control_name: str) -> str:
    """Classify a compensating-control name into a NIST CSF function.
    Falls back to 'protect' (the largest preventive bucket) if no keyword hits.
    """
    name = (control_name or "").lower()
    for func, keywords in _CSF_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return func
    return "protect"


def _build_defense_layers() -> Dict[str, Any]:
    """Block 4 · M1 rebuild (Path B fix B2, CISO + risk-officer) — NIST CSF
    5-function coverage DERIVED from per-pattern compensating_controls, not
    hardcoded percentages.

    For each CSF function: collect every in-place control classified there
    across all 13 patterns, plus the gaps. Coverage =
    mean(in_place effectiveness) × (in_place / (in_place + gaps)). The gap
    penalty makes a function with many unfilled gaps score lower even if its
    in-place controls are individually strong.
    """
    func_in_place: Dict[str, List[int]] = {f: [] for f in _CSF_KEYWORDS}
    func_gap_count: Dict[str, int] = {f: 0 for f in _CSF_KEYWORDS}
    func_examples: Dict[str, List[str]] = {f: [] for f in _CSF_KEYWORDS}
    func_gap_examples: Dict[str, List[str]] = {f: [] for f in _CSF_KEYWORDS}

    for pid, pattern in _PATTERNS.items():
        cc = pattern.get("compensating_controls", {}) or {}
        for ctrl in cc.get("in_place", []) or []:
            func = _classify_control_to_csf(ctrl.get("name", ""))
            eff = ctrl.get("effectiveness_pct", 0)
            func_in_place[func].append(eff)
            if len(func_examples[func]) < 3:
                func_examples[func].append(ctrl.get("name", ""))
        for gap in cc.get("gaps", []) or []:
            func = _classify_control_to_csf(gap.get("name", ""))
            func_gap_count[func] += 1
            if len(func_gap_examples[func]) < 2:
                func_gap_examples[func].append(gap.get("name", ""))

    layers = []
    for func in ("identify", "protect", "detect", "respond", "recover"):
        in_place = func_in_place[func]
        gaps = func_gap_count[func]
        n_in = len(in_place)
        if n_in == 0:
            coverage = 0
        else:
            mean_eff = sum(in_place) / n_in
            gap_penalty = n_in / (n_in + gaps) if (n_in + gaps) > 0 else 1.0
            coverage = int(round(mean_eff * gap_penalty))
        rag = "evidence" if coverage >= 70 else ("watch" if coverage >= 50 else "critical")
        note_in = " · ".join(func_examples[func][:2]) or "no controls classified here"
        note_gap = (" · gaps: " + " · ".join(func_gap_examples[func])) if func_gap_examples[func] else ""
        layers.append({
            "name": func,
            "coverage_pct": coverage,
            "rag": rag,
            "note": (note_in + note_gap)[:90],
            "in_place_count": n_in,
            "gap_count": gaps,
        })

    return {
        "source_status": "real_query_synthesized_data",
        "framework":     "NIST CSF 2.0",
        "source_note": (
            "Coverage DERIVED from per-pattern compensating_controls in "
            "data/risk_patterns.json. Each control classified to a CSF function "
            "by name; coverage = mean(in_place effectiveness) × (in_place / "
            "(in_place + gaps)). Control effectiveness percentages are "
            "illustrative until calibrated from CCT / pen-test / observed "
            "incident-frequency reduction."
        ),
        "layers": layers,
    }


def _build_inherent_residual() -> Dict[str, Any]:
    """Block 5 — portfolio + per-pattern inherent vs residual, from the ONE seeded MC.

    Fixes the naive Sigma(per-pattern P95) roll-up (percentiles are not additive) — the
    portfolio inherent/residual are now Monte-Carlo aggregates (utils.exposure.
    aggregate_loss_mc), the SAME distribution the exposure block surfaces (inherent =
    gross, residual = net of realized control effectiveness). Per-pattern inherent/
    residual are that pattern's own annual-loss percentiles. Frequencies calibrated to a
    large US consumer/crypto fintech (~$2-4B rev); severity anchors are public events.
    """
    from utils.exposure import aggregate_loss_mc
    mc = aggregate_loss_mc()
    port = mc["portfolio"]
    res_worst = int(round(mc["worst_anchor"] * (1 - mc["avg_eff_pct"] / 100.0) / 10_000) * 10_000)
    return {
        "source_status": "real_query_synthesized_data",
        "source_note": (
            "ONE seeded Monte-Carlo aggregate loss distribution (Poisson frequency x "
            "lognormal severity, seed {seed}, {n} trials) over ALL patterns in the catalog, WITH "
            "one-generation cascade propagation along the declared cascade_to edges "
            "(v2.0c — the loss engine honors the same dependency graph the cascade panel "
            "renders; induction probabilities are operator_calibrated judgment, and the "
            "independence counterfactual is reported alongside in exposure.portfolio_total."
            "correlation_model). Inherent (gross) and residual (net of realized control "
            "effectiveness) are two views of the SAME distribution, identical to the "
            "exposure block. Percentiles are NOT summed across patterns (the prior Sigma "
            "had inflated inherent P95 to $835M and stress to $3.1B). Frequencies "
            "calibrated to a large US consumer/crypto fintech archetype (operator "
            "judgment, not sourced); severity anchors are public comparable events "
            "(Equifax 2017 $700M FTC, Knight Capital 2012 $440M/45min, Capital One 2019, etc.); "
            "control effectiveness carries an independent-validation haircut (self-assessed "
            "effectiveness overstates realized reduction)."
        ).format(seed=mc["seed"], n="{:,}".format(mc["trials"])),
        "portfolio": {
            "inherent": {
                "p50": port["inherent"]["p50"],
                "p95": port["inherent"]["p95"],
                "p99": port["inherent"]["p99"],
                "mean": port["inherent"]["mean"],
                "worst_anchor": mc["worst_anchor"],
                "worst_anchor_basis": mc["worst_anchor_basis"],
            },
            "controls": {
                "avg_effectiveness_pct": mc["avg_eff_pct"],
                "depth_layers": 4,
                "derivation": "mean realized (post-haircut) effectiveness across {n} patterns".format(n=len(port and mc["by_pattern"])),
            },
            "residual": {
                "p50": port["residual"]["p50"],
                "p95": port["residual"]["p95"],
                "p99": port["residual"]["p99"],
                "mean": port["residual"]["mean"],
                "worst_anchor": res_worst,
                "derivation": "Monte-Carlo aggregate, net of per-pattern realized control effectiveness",
            },
        },
        "by_pattern": mc["by_pattern"],
    }

def _build_sensitivity() -> Dict[str, Any]:
    """Calibration appendix — the tornado behind the dollars (round-5 P0 from both
    external reviewers: 'calibration is narrative, not evidence'). One-at-a-time
    seeded re-runs of the SAME correlated MC, each shocking exactly one calibration
    judgment, plus the per-pattern calibration table (frequency judgment, severity
    anchors, control effectiveness) in one place. Everything derives from
    utils.exposure — render-from-data end to end."""
    from utils.exposure import sensitivity_analysis
    s = sensitivity_analysis()
    s["source_status"] = "real_query_synthesized_data"
    s["source_note"] = (
        "Seeded one-at-a-time sensitivity re-runs of the correlated MC (same engine, "
        "same seed, one judgment shocked per lever) + the per-pattern calibration "
        "basis. This surface exists because the frequency re-anchor and control "
        "effectiveness are OPERATOR JUDGMENT, not fitted history — the tornado shows "
        "how far the headline moves if each judgment is wrong, instead of presenting "
        "a point estimate as more certain than it is. The cascade_off lever equals "
        "correlation_model.independence_counterfactual by construction."
    )
    return s


def _build_journey_spine() -> Dict[str, Any]:
    """Stage 1a of reviews/journey_spine_port_spec.md — the journey as the atomic
    unit of governance. J-SIM-001 threads the EXISTING objects (patterns,
    dependency nodes, controls, owners) onto one end-to-end money path with
    one dated seeded incident as the narrative anchor. Structure from the
    operator's production 2LoD practice; all names, values, dates seeded.
    Every quoted peak DERIVES from utils.journey_signals (gate C36.3 recomputes)."""
    import json as _json
    from pathlib import Path as _P
    from utils.journey_signals import signal_stats, WINDOW, BASE_PTS, BASE_CADENCE, GEN_ID
    cat = _json.loads((_P(__file__).resolve().parent.parent / "data" / "journey_catalog.json").read_text())
    stats = signal_stats()
    # pattern residuals for the chain rows — from the same MC the workbench runs
    from utils.exposure import aggregate_loss_mc
    mc = aggregate_loss_mc()
    by_pat = {r["pattern_id"]: r for r in mc["by_pattern"]}
    from utils.exposure import _PATTERNS as _CATPAT

    _INTENT = {
        "sim.rps_edge": "request rate at the front door — is the journey being asked for",
        "sim.p99_edge": "tail latency at the edge — first place customer pain shows",
        "sim.p99_transfer_api": "orchestration tail latency — the journey's own clock",
        "sim.error_rate_transfer_api": "transfer-path error share — failed asks",
        "sim.p99_risk_score": "risk-decision latency — the gate before money moves",
        "sim.decision_conf_p5": "5th-percentile decision confidence — low-confidence automation share",
        "sim.auth_failure_rate": "customer auth failure share — identity-plane health",
        "sim.p99_identity": "verification tail latency",
        "sim.p99_ledger_write": "ledger write tail latency — did the books keep up",
        "sim.write_retry_rate": "write retry share — the amplification fuel",
        "sim.consumer_lag_p95": "consumer lag depth — work-queue solvency",
        "sim.publish_p99": "publish tail latency into the bus",
        "sim.p99_settle": "settlement submit tail latency",
        "sim.settle_queue_depth": "settlement queue depth — rails backpressure",
        "sim.rail_ack_latency": "external rail acknowledgment latency — the observable edge of the partner",
        "sim.notify_send_rate": "customer notification throughput",
        "sim.recon_break_count": "reconciliation breaks per run — does everyone agree it happened",
    }

    services = []
    for svc in cat["services"]:
        rows = []
        for sig in svc["signals"]:
            s = stats.get(sig) or {}
            rows.append({"id": sig, "unit": s.get("unit"), "mean": s.get("mean"),
                         "p95": s.get("p95"), "max": s.get("max"),
                         "incident_participant": s.get("incident_participant"),
                         "incident_peak": s.get("incident_peak"),
                         "incident_peak_over_baseline": s.get("incident_peak_over_baseline"),
                         "chip": s.get("chip"), "query_intent": _INTENT.get(sig, "")})
        linked = []
        for pid in svc["patterns"]:
            bp = by_pat.get(pid) or {}
            cc = (_CATPAT.get(pid) or {}).get("compensating_controls") or {}
            ctrl_names = [c.get("name") or c.get("control") or str(c) for c in (cc.get("in_place") or [])][:3]
            linked.append({"pattern_id": pid,
                           "residual_p95_usd": (bp.get("residual") or {}).get("p95"),
                           "controls_linked": ctrl_names,
                           "controls_caveat": cat["chain_caveats"]["controls"]})
        services.append({**svc, "signal_rows": rows, "risk_links": linked,
                         "owner_caveat": cat["chain_caveats"]["owners"]})

    inc = dict(cat["incident"])
    for step in inc["narrative_steps"]:
        s = stats.get(step["signal"]) or {}
        step["derived_peak"] = s.get("incident_peak")
        step["derived_peak_over_baseline"] = s.get("incident_peak_over_baseline")
        step["unit"] = s.get("unit")

    # journey SLO derivation — seeded, labeled, never typed on a surface
    stage_p95 = {}
    for st in cat["stages"]:
        lat = [stats[s]["p95"] for svc in cat["services"] if svc["stage"] == st["id"]
               for s in svc["signals"] if stats.get(s, {}).get("unit") == "ms"]
        stage_p95[st["id"]] = round(max(lat), 1) if lat else 0.0
    e2e_p95 = round(sum(stage_p95.values()), 1)
    incident_hours = 2.0
    availability = round(100.0 * (1 - incident_hours / (WINDOW["days"] * 24)), 3)

    signal_catalog = [{"id": sig, "stage": svc["stage"], "service": svc["id"],
                       "owner": svc["owner"], "unit": stats[sig]["unit"],
                       "query_intent": _INTENT.get(sig, ""),
                       "chip": stats[sig]["chip"]}
                      for svc in cat["services"] for sig in svc["signals"]]
    sc_path = _P(__file__).resolve().parent.parent / "data" / "signal_catalog.json"
    sc_path.write_text(_json.dumps({
        "_generated_by": GEN_ID + " via utils/projection._build_journey_spine — do not hand-edit",
        "port_tag": cat["port_tag"],
        "signals": signal_catalog}, indent=1))

    # Stage 4 — the aggregator contract: emit the minimal payload VERBATIM,
    # hash it canonically, and record the hash the consumer embedded. The
    # reference asserts the passthrough; the gates recompute it (C38.2, B12.4).
    from utils.journey_signals import aggregator_payload
    import hashlib as _hl
    _agg = aggregator_payload()
    _agg_canon = _json.dumps(_agg, sort_keys=True, separators=(",", ":"))
    _agg_sha = _hl.sha256(_agg_canon.encode()).hexdigest()
    (_P(__file__).resolve().parent.parent / "data" / "journey_aggregator.json").write_text(
        _json.dumps({"_contract": "journey_aggregator · verbatim · unmodified — canonical sha256 below is "
                                  "recomputed by audit C38.2 and bundle gate B12.4; a consumer that modifies "
                                  "the payload fails the build",
                     "sha256": _agg_sha, "payload": _agg}, indent=1))

    return {
        "source_status": "operator_calibrated",
        "port_tag": cat["port_tag"],
        "journey": cat["journey"],
        "aggregator": {"file": "data/journey_aggregator.json", "consumed_sha256": _agg_sha,
                       "claim": "verbatim · unmodified — gate-verified, not asserted"},
        "window": WINDOW,
        "stages": [dict(st, stage_p95_ms=stage_p95[st["id"]]) for st in cat["stages"]],
        "services": services,
        "incident": inc,
        "slo_derived": {
            "end_to_end_p95_ms": e2e_p95,
            "target_ms": cat["journey"]["slo"]["end_to_end_p95_target_ms"],
            "within_target": e2e_p95 <= cat["journey"]["slo"]["end_to_end_p95_target_ms"],
            "availability_observed_pct": availability,
            "availability_target_pct": cat["journey"]["slo"]["availability_target_pct"],
            "note": ("Derived from the seeded stage series (sum of per-stage worst p95 latency signals; "
                     "availability = window minus the SIM-0531 degradation window). Seeded targets, "
                     "seeded series — the derivation discipline is the point, not the values."),
        },
        "signal_catalog": signal_catalog,
        "chain_caveats": cat["chain_caveats"],
        "generator": {"id": GEN_ID, "base_pts": BASE_PTS, "base_cadence": BASE_CADENCE},
    }


_RATING_STATES = ("confirmed", "candidate_rerating", "pending_engineering_confirmation")
_AS_OF_FOR_STATES = "2026-07-14"  # the projection's pinned clock (meta.as_of) — never wall time


def _rating_state(finding: Dict[str, Any], as_of: str) -> Dict[str, str]:
    """Stage 3 (journey spine port) — the rating-change workflow as DATA,
    DERIVED from fields the register already carries (status, plan, eta) —
    the v106 grammar: candidate rerating → pending Engineering confirmation →
    confirmed. A demonstrator derivation, declared; production replaces it
    with the GRC system's real workflow states."""
    from datetime import date, timedelta
    tr = finding.get("treatment") or {}
    status = tr.get("status", "")
    if status == "in_progress" and tr.get("eta"):
        near = date.fromisoformat(tr["eta"]) <= date.fromisoformat(as_of[:10]) + timedelta(days=60)
        if near:
            return {"state": "pending_engineering_confirmation",
                    "basis": f"treatment {tr.get('ticket', '')} closing (eta {tr['eta']}) — rerating proposed, awaiting Engineering confirmation that the KRIs hold"}
        return {"state": "candidate_rerating",
                "basis": f"treatment in flight (eta {tr['eta']}) — the rerating case builds if it lands"}
    if status == "accepted":
        return {"state": "confirmed",
                "basis": "rating stands under a recorded, expiring acceptance (see the acceptance trail)"}
    return {"state": "confirmed",
            "basis": f"current rating stands — treatment {status or 'not started'}, no rerating case yet"}


def _build_operating_model(domains: Dict[str, Any], as_of: str) -> Dict[str, Any]:
    """Stage 3 — the operating-model delta: bespoke evidence chase → automated
    re-performance, with the A8 hash-chained attestation machinery named as
    the mechanism. Structure from the operator's production 2LoD practice;
    all names, values, and dates seeded."""
    from utils.exposure import control_test_evidence, _PATTERNS
    rows = []
    for pid in _PATTERNS:
        ev = control_test_evidence(pid)
        for c in ev.get("controls", []):
            tested = bool(c.get("reperformance")) and c.get("method") not in (None, "", "—")
            rows.append({"pattern_id": pid, "control": c.get("name"),
                         "method": c.get("method"),
                         # untested/gap controls have NOTHING to re-perform — the
                         # honest third class, counted out loud (the v106 question
                         # answered "none" is still an answer)
                         "reperformance": c.get("reperformance") if tested else "no_evidence_yet",
                         "hard_to_reperform": c.get("hard_to_reperform") if tested else None,
                         "reperformance_basis": c.get("reperformance_basis") if tested else
                             "no test evidence exists yet — nothing to re-perform; the gap itself is the finding"})
    n_auto = sum(1 for r in rows if r["reperformance"] == "automated")
    n_none = sum(1 for r in rows if r["reperformance"] == "no_evidence_yet")
    n_hard = sum(1 for r in rows if r["hard_to_reperform"])
    state_counts: Dict[str, int] = {s: 0 for s in _RATING_STATES}
    for d in domains.values():
        for f in d["findings"]:
            state_counts[f["rating_state"]["state"]] += 1
    return {
        "source_status": "operator_calibrated",
        "port_tag": ("Structure from the operator's production 2LoD practice; "
                     "all names, values, and dates seeded."),
        "before": ("BEFORE — the bespoke evidence chase: each assessment cycle opens with emails, "
                   "screenshots and meeting minutes assembled by hand; the evidence exists only as "
                   "the write-up that chased it, and re-performing the assessment means chasing it again."),
        "after": ("AFTER — automated re-performance: evidence that is a QUERY re-runs on every pull; "
                  "governance actions are A8-gated (named human · 12-word justification · expiry) and "
                  "hash-chained, so the attestation log IS the re-performance record. The flags below "
                  "mark what still resists automation — the honest boundary of the claim."),
        "mechanism": ("The A8 attestation machinery is the re-performance mechanism: SHA-256 over "
                      "canonical JSON, verified in-browser, byte-matching the signer."),
        "evidence_rows": rows,
        "evidence_counts": {"total": len(rows), "automated": n_auto,
                            "bespoke": len(rows) - n_auto - n_none,
                            "no_evidence_yet": n_none, "hard_to_reperform": n_hard},
        "rating_state_counts": state_counts,
        "rating_state_vocabulary": list(_RATING_STATES),
        "derivation_note": ("Rating states DERIVE from the register's own treatment fields "
                            "(accepted → confirmed under acceptance · in_progress with eta ≤60d of the "
                            "as_of → pending Engineering confirmation · in_progress beyond → candidate "
                            "rerating · planned/blocked → confirmed). A demonstrator derivation, declared; "
                            "production replaces it with the GRC system's real workflow states."),
    }


def _build_risk_rollup(domains: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 4 — the parent→child rollup (the Master-Risk-Catalog shape): the
    register findings ARE the child layer, one (pattern × domain) instance
    each; this names the structure. A child is EVIDENCED when the seeded
    telemetry actually fired for it (signals_exceeded non-empty) — derived,
    never asserted."""
    from utils.exposure import _PATTERNS
    parents: Dict[str, Dict[str, Any]] = {}
    for pid, pat in _PATTERNS.items():
        parents[pid] = {"pattern_id": pid, "name": pat.get("name", pid), "children": []}
    for d in domains.values():
        for f in d["findings"]:
            pid = f.get("pattern_id")
            if pid in parents:
                parents[pid]["children"].append({
                    "finding_id": f.get("finding_id"),
                    "domain": f.get("domain_id"),
                    "rag": f.get("overall_rag"),
                    "rating_state": (f.get("rating_state") or {}).get("state"),
                    "evidenced": bool(f.get("signals_exceeded")),
                })
    rows = []
    for pid, pr in parents.items():
        ch = pr["children"]
        rows.append({**pr, "n_children": len(ch),
                     "n_evidenced": sum(1 for c in ch if c["evidenced"])})
    rows.sort(key=lambda r: (-r["n_children"], r["pattern_id"]))
    return {
        "source_status": "real_query_synthesized_data",
        "note": ("Parents = the 14 patterns; children = the register's (pattern × domain) finding "
                 "instances — the layer an ERM master catalog rolls up. EVIDENCED = the seeded "
                 "telemetry fired for that child (signals_exceeded non-empty), the CHILD-RISKS-"
                 "EVIDENCED discipline with the derivation stated."),
        "parents": rows,
        "totals": {"parents": len(rows),
                   "parents_with_children": sum(1 for r in rows if r["n_children"]),
                   "children": sum(r["n_children"] for r in rows),
                   "evidenced": sum(r["n_evidenced"] for r in rows)},
    }


def _build_dependency_layer() -> Dict[str, Any]:
    """E1 — the shared-dependency layer as a first-class projection block.
    The question the pre-E1 model could not answer: which single shared thing
    (cloud region, customer identity plane, API registry, etcd/control plane,
    workforce IdP, datastore, payments rails, security-agent vendor) takes the
    most of the tail with it. Per-node ceteris-paribus suppression on the same
    seeded trial matrix → the dependency tornado; the top node IS the
    concentration-risk agenda, priced. Render-from-data end to end."""
    from utils.exposure import dependency_analysis
    d = dependency_analysis()
    d["source_status"] = "operator_calibrated"
    return d


def _build_regulation_residual(materiality: Dict[str, Any]) -> Dict[str, Any]:
    """Round-6 external ask (CRO/Legal view): "how much of our residual $ already
    sits in a disclosure regime?" Residual P50/P95 per TRIGGERED regulation, from
    the same seeded trial matrix as the headline — within-trial subset sums, never
    summed percentiles (the naive Σ ships alongside as the anti-example)."""
    from utils.exposure import regulation_residual_view
    reg_map = tuple(
        (rid, blk.get("regulation_citation", ""),
         tuple(blk.get("triggered_patterns") or blk.get("conditional_patterns") or []),
         blk.get("applicability", ""))
        for rid, blk in materiality.items()
    )
    view = regulation_residual_view(reg_map)
    view["source_status"] = "real_query_synthesized_data"
    view["source_note"] = (
        "Derived from the SAME seeded MC trial matrix as the portfolio headline "
        "(within-trial subset sums per regulation's triggered patterns — quantiles of "
        "co-occurring losses, not added percentiles). Pattern→regulation mapping comes "
        "from the materiality block (illustrative mappings; OCC App D is a "
        "heightened-standards-STYLE discipline mapping, not a claim of legal "
        "applicability). Regulations overlap, so rows do not sum to the portfolio."
    )

    # ── round-17: perimeter profiles (examiner persona: "a toggle is not proof of
    # re-mapping logic"). Three COARSE charter archetypes; statuses re-label the
    # disclosed applicability facts per charter — indicative only, determination
    # reserved to Legal/Compliance. Dollars = union subset sums, same matrix.
    from utils.exposure import perimeter_profiles_view
    _RESERVED = ("indicative re-mapping under a DECLARED charter — the perimeter "
                 "DETERMINATION is reserved to Legal/Compliance")
    profiles = (
        ("fintech_mtl", "US public fintech · state MTLs + BitLicense · EU EMI (default archetype)",
         "the portfolio's calibrated posture: SEC registrant, NYDFS-covered, EU/UK "
         "authorised, card acquiring — OCC App D remains a style-mapping only; " + _RESERVED,
         (("sec_8k_item_1_05", "binding-assumed"), ("nydfs_500", "binding-assumed"),
          ("gdpr_art_33", "binding-assumed"), ("eu_dora_ict", "binding-assumed"),
          ("uk_fca_opres", "binding-assumed"), ("eu_ai_act_high_risk", "binding-assumed"),
          ("pci_dss_v4", "contractual"), ("occ_12cfr30_app_d", "style-mapping"),
          ("finra_4370", "binding-assumed"), ("sea_17a4", "binding-assumed"),
          ("reg_sci", "style-mapping"))),
        ("us_broker_dealer", "US retail broker-dealer · FINRA member · SEC registrant",
         "the brokerage line as its own charter: FINRA 4370 BCP + SEA 17a-4 records bind; "
         "8-K as registrant; Reg SCI stays a discipline STYLE (not an SCI entity at this "
         "archetype); EU/UK/NYDFS indicatively out; card funding contractual; " + _RESERVED,
         (("sec_8k_item_1_05", "binding-assumed"), ("finra_4370", "binding-assumed"),
          ("sea_17a4", "binding-assumed"), ("pci_dss_v4", "contractual"),
          ("reg_sci", "style-mapping"), ("occ_12cfr30_app_d", "style-mapping"),
          ("nydfs_500", "out-of-perimeter"), ("gdpr_art_33", "out-of-perimeter"),
          ("eu_dora_ict", "out-of-perimeter"), ("uk_fca_opres", "out-of-perimeter"),
          ("eu_ai_act_high_risk", "out-of-perimeter"))),
        ("national_bank", "OCC-chartered national bank (same book of risks)",
         "App D heightened standards bind large national banks; NYDFS Part 500 "
         "indicatively out (federal charter — DFS covers NY-licensed/chartered "
         "entities); everything else as declared; " + _RESERVED,
         (("occ_12cfr30_app_d", "binding-assumed"), ("sec_8k_item_1_05", "binding-assumed"),
          ("gdpr_art_33", "binding-assumed"), ("eu_dora_ict", "binding-assumed"),
          ("uk_fca_opres", "binding-assumed"), ("eu_ai_act_high_risk", "binding-assumed"),
          ("pci_dss_v4", "contractual"), ("nydfs_500", "out-of-perimeter"),
          ("finra_4370", "out-of-perimeter"), ("sea_17a4", "out-of-perimeter"),
          ("reg_sci", "style-mapping"))),
        ("eu_emi", "EU-headquartered EMI · no US listing, no NY licence",
         "DORA/GDPR/AI-Act lead; SEC 8-K and NYDFS indicatively out; OCC stays a "
         "style-mapping; UK retained if UK-authorised; " + _RESERVED,
         (("eu_dora_ict", "binding-assumed"), ("gdpr_art_33", "binding-assumed"),
          ("eu_ai_act_high_risk", "binding-assumed"), ("uk_fca_opres", "binding-assumed"),
          ("pci_dss_v4", "contractual"), ("occ_12cfr30_app_d", "style-mapping"),
          ("sec_8k_item_1_05", "out-of-perimeter"), ("nydfs_500", "out-of-perimeter"),
          ("finra_4370", "out-of-perimeter"), ("sea_17a4", "out-of-perimeter"),
          ("reg_sci", "style-mapping"))),
    )
    view["perimeter_profiles"] = perimeter_profiles_view(reg_map, profiles)
    return view


def _build_patterns_meta() -> Dict[str, Any]:
    """Block 7 (Path B · taxonomy alignment) — authoritative per-pattern
    metadata for the PATTERN-act renderers (pattern primer + evidence ribbons).

    Reads the AUTHORITATIVE names / thresholds / incidents from
    data/risk_patterns.json (_PATTERNS) so the JS never hardcodes a taxonomy
    that can drift from the source of truth. The M4.5 JS renderers previously
    carried an invented taxonomy (RP-06 'eval coverage', RP-10 'agent scope',
    etc.) that contradicted risk_patterns.json — this block kills that drift.
    """
    out = []
    for pid in sorted(_PATTERNS.keys()):
        p = _PATTERNS[pid]
        incidents = p.get("incident_reference", []) or []
        anchor_strs = []
        for inc in incidents[:3]:
            nm = inc.get("name", "")
            dt = inc.get("date", "")
            anchor_strs.append(f"{nm}" + (f" ({dt})" if dt else ""))
        out.append({
            "id": pid,
            "name": p.get("name", pid),
            "description": p.get("description", ""),
            "nist_function": p.get("nist_function", ""),
            "appetite": p.get("appetite", ""),
            "threshold_source": p.get("threshold_source", ""),
            "threshold_source_url": p.get("threshold_source_url", ""),
            "anchors": anchor_strs,
        })
    return {
        "source_status": "published_standard",
        "source_note": (
            "Authoritative pattern taxonomy + thresholds + incident anchors "
            "read from data/risk_patterns.json. Names, threshold sources, and "
            "incident references are the source of truth; renderers must read "
            "from here, not hardcode."
        ),
        "patterns": out,
    }


def _build_ai_gov(_ai_gov_domains: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Block 6 (M4) — AI Governance Lead deep-dive surface.

    Model inventory · agent inventory · MCP supply chain · recent trace ·
    HITL posture. Per the GROK call-out: this is the differentiator surface;
    the AI Gov panel must be the richest, not the thinnest.

    Public anchors used:
    - OWASP MCP Top 10 (2025) — tool permission sprawl, untrusted registration,
      prompt-injection via tool descriptions
    - CVE-2025-49596 (MCP Inspector RCE) · CVSS 9.4
    - NIST AI RMF MEASURE-2.7 (drift telemetry)
    - EU AI Act Art. 9 + Art. 15 (high-risk model obligations)
    - First malicious MCP package on public registries · Sep 2025

    Firm-specific values (drift %, scope-violations/24h, hash-pin compliance %,
    eval coverage %) are illustrative. In production these come from a model
    registry (MLflow / Weights & Biases), agent observability (MCP Inspector
    logs / internal trace store), and supply-chain scanners (Snyk / Socket.dev).
    """
    models = [
        {
            "id": "credit-decision-v3",
            "name": "Credit Decision v3",
            "owner": "D. Patel",
            "team": "ai-platform",
            "stage": "production",
            "framework": "XGBoost · scikit-learn",
            "last_refresh": "2026-02-15",
            "days_since_refresh": 117,
            "drift_metric": "MEASURE-2.7 (KS statistic vs reference)",
            "drift_basis": "NIST AI RMF MEASURE 2.7 · drift telemetry",
            "drift_status": "exceeded",
            "eval_coverage_pct": 62,
            "eval_basis": "internal adversarial test suite + red-team baseline (88% target)",
            "gating_state": "gated",
            "regulatory_class": "EU AI Act Art. 9 high-risk · 17 CFR 229.106(b) cyber-class",
            "rag": "critical",
        },
        {
            "id": "cust-support-bot",
            "name": "Customer Support Bot",
            "owner": "M. Okonkwo",
            "team": "ai-platform",
            "stage": "production",
            "framework": "Claude Sonnet · LangGraph",
            "last_refresh": "2026-05-29",
            "days_since_refresh": 14,
            "drift_metric": "adversarial coverage (red-team baseline)",
            "drift_basis": "internal · 88% baseline",
            "drift_status": "approaching",
            "eval_coverage_pct": 84,
            "eval_basis": "monthly red-team adversarial run · jailbreak corpus",
            "gating_state": "require_eval",
            "regulatory_class": "EU AI Act Art. 50 transparency · CFPB UDAAP",
            "rag": "watch",
        },
        {
            "id": "trade-routing-v2",
            "name": "Trade Routing v2",
            "owner": "S. Khoury",
            "team": "trading-platform",
            "stage": "production",
            "framework": "reinforcement-learning · custom",
            "last_refresh": "2026-05-22",
            "days_since_refresh": 21,
            "drift_metric": "execution-quality variance vs benchmark",
            "drift_basis": "internal SLO · Reg NMS best-ex",
            "drift_status": "within",
            "eval_coverage_pct": 91,
            "eval_basis": "continuous backtest against latency / fill quality",
            "gating_state": "production",
            "regulatory_class": "SEC Reg NMS · FINRA 5310 best execution",
            "rag": "evidence",
        },
        {
            "id": "fraud-screening-v1",
            "name": "Fraud Screening v1",
            "owner": "L. Tran",
            "team": "payments-core",
            "stage": "shadow",
            "framework": "ensemble · LightGBM + features",
            "last_refresh": "2026-06-01",
            "days_since_refresh": 11,
            "drift_metric": "false-positive rate vs prod incumbent",
            "drift_basis": "shadow-mode comparison · 30d window",
            "drift_status": "within",
            "eval_coverage_pct": 78,
            "eval_basis": "fairness audit + adversarial subset",
            "gating_state": "production",
            "regulatory_class": "ECOA · CFPB UDAAP · BSA/AML",
            "rag": "evidence",
        },
    ]

    agents = [
        {
            "id": "billing-agent",
            "name": "Billing Agent",
            "owner": "L. Tran",
            "team": "payments-core",
            "framework": "MCP + LangGraph",
            "mcp_servers": ["stripe-mcp", "internal-billing-mcp"],
            "scope_grant": ["read:invoices", "write:invoices", "read:customers"],
            "scope_violations_24h": 4,
            "scope_violation_basis": "OWASP MCP Top 10 #2 · Tool Permission Sprawl",
            "hash_pin_compliance_pct": 71,
            "hash_pin_basis": "OWASP MCP Top 10 #4 · Untrusted Tool Registration",
            "hitl_required": True,
            "hitl_basis": "MCP specification 'SHOULD' on HITL · widely treated as MUST",
            "last_scope_audit": "2026-05-30",
            "rag": "watch",
        },
        {
            "id": "data-egress-agent",
            "name": "Data Egress Agent",
            "owner": "D. Patel",
            "team": "ai-platform",
            "framework": "MCP + custom",
            "mcp_servers": ["snowflake-mcp", "tableau-mcp"],
            "scope_grant": ["read:warehouse", "read:bi"],
            "scope_violations_24h": 0,
            "scope_violation_basis": "—",
            "hash_pin_compliance_pct": 100,
            "hash_pin_basis": "fully hash-pinned · validated daily",
            "hitl_required": False,
            "hitl_basis": "read-only · low-risk",
            "last_scope_audit": "2026-06-08",
            "rag": "evidence",
        },
        {
            "id": "ops-runbook-agent",
            "name": "Ops Runbook Agent",
            "owner": "J. Mendes",
            "team": "platform-sre",
            "framework": "MCP + LangGraph",
            "mcp_servers": ["github-mcp", "pagerduty-mcp", "k8s-mcp"],
            "scope_grant": ["read:incidents", "write:incidents", "exec:runbooks"],
            "scope_violations_24h": 1,
            "scope_violation_basis": "attempted k8s admin write outside scope",
            "hash_pin_compliance_pct": 89,
            "hash_pin_basis": "1 server (github-mcp) using floating tag",
            "hitl_required": True,
            "hitl_basis": "exec scope · all runbook executions require approval",
            "last_scope_audit": "2026-06-05",
            "rag": "watch",
        },
    ]

    mcp_servers = [
        {
            "id": "stripe-mcp", "name": "Stripe MCP",
            "vendor": "Stripe (official)", "tier": "T1",
            "hash_pinned": True, "version_pin": "sha256:8c2f0e…",
            "last_security_scan": "2026-06-10", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "evidence",
            "note": "official vendor MCP · pinned",
        },
        {
            "id": "internal-billing-mcp", "name": "Internal Billing MCP",
            "vendor": "internal-platform", "tier": "T1",
            "hash_pinned": True, "version_pin": "sha256:3b0e91…",
            "last_security_scan": "2026-06-08", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "evidence",
            "note": "internal · validated daily",
        },
        {
            "id": "github-mcp", "name": "GitHub MCP",
            "vendor": "community (modelcontextprotocol)", "tier": "T2",
            "hash_pinned": False, "version_pin": "latest (floating)",
            "last_security_scan": "2026-06-04", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "watch",
            "note": "floating tag · per OWASP MCP Top 10 #4 untrusted-registration risk",
        },
        {
            "id": "snowflake-mcp", "name": "Snowflake MCP",
            "vendor": "Snowflake (official)", "tier": "T1",
            "hash_pinned": True, "version_pin": "sha256:aaf21d…",
            "last_security_scan": "2026-06-11", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "evidence",
            "note": "official vendor MCP",
        },
        {
            "id": "pagerduty-mcp", "name": "PagerDuty MCP",
            "vendor": "PagerDuty (official)", "tier": "T2",
            "hash_pinned": True, "version_pin": "sha256:6654b6…",
            "last_security_scan": "2026-06-09", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "evidence",
            "note": "official vendor MCP",
        },
        {
            "id": "k8s-mcp", "name": "Kubernetes MCP",
            "vendor": "community", "tier": "T2",
            "hash_pinned": True, "version_pin": "sha256:4a2c8b…",
            "last_security_scan": "2026-06-09", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "watch",
            "note": "community · audit pending for next quarterly review",
        },
        {
            "id": "tableau-mcp", "name": "Tableau MCP",
            "vendor": "community", "tier": "T3",
            "hash_pinned": True, "version_pin": "sha256:ed060d…",
            "last_security_scan": "2026-05-22", "kev_exposure": 0,
            "agents_using": 1,
            "rag": "watch",
            "note": "T3 · 21d since scan · approaching SLA",
        },
    ]

    trace_recent = [
        {"ts": "2026-06-12 14:12", "agent": "billing-agent",     "tool": "billing.write:refund",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": "L. Tran (HITL approved)"},
        {"ts": "2026-06-12 14:09", "agent": "ops-runbook-agent", "tool": "k8s.admin:scale_deployment",
         "scope_ok": False, "flagged": "scope-violation",    "rag": "critical",   "actor_human": "auto-denied"},
        {"ts": "2026-06-12 14:01", "agent": "data-egress-agent","tool": "warehouse.read:customers",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": None},
        {"ts": "2026-06-12 13:58", "agent": "billing-agent",     "tool": "billing.read:invoice",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": None},
        {"ts": "2026-06-12 13:42", "agent": "billing-agent",     "tool": "billing.write:invoice",
         "scope_ok": True,  "flagged": "prompt-injection-attempt", "rag": "watch",
         "actor_human": "L. Tran (reviewed · benign)"},
        {"ts": "2026-06-12 13:35", "agent": "ops-runbook-agent", "tool": "github.read:repo",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": None},
        {"ts": "2026-06-12 13:20", "agent": "billing-agent",     "tool": "billing.write:credit",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": "L. Tran (HITL)"},
        {"ts": "2026-06-12 13:08", "agent": "data-egress-agent","tool": "bi.read:dashboard",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": None},
        {"ts": "2026-06-12 12:55", "agent": "ops-runbook-agent", "tool": "pd.write:acknowledge",
         "scope_ok": True,  "flagged": None,                 "rag": "evidence", "actor_human": "J. Mendes"},
        {"ts": "2026-06-12 12:41", "agent": "billing-agent",     "tool": "billing.admin:refund_admin",
         "scope_ok": False, "flagged": "scope-violation",    "rag": "critical",   "actor_human": "auto-denied"},
    ]

    hitl_posture = {
        "models_total": len(models),
        "models_requiring_hitl": sum(1 for m in models if m.get("gating_state") in ("gated", "require_eval")),
        "agents_total": len(agents),
        "agents_requiring_hitl": sum(1 for a in agents if a.get("hitl_required")),
        "coverage_pct": 75,
        "basis": (
            "MCP specification 'SHOULD' on human-in-loop · widely treated as MUST by "
            "security practitioners (Anthropic · Authzed · Practical DevSecOps). "
            "OWASP MCP Top 10 #1 (Tool Description Injection) — HITL is the "
            "primary mitigation. Per A8: any verb appended without expiry is "
            "shelfware."
        ),
    }

    # Path B fix F · back-link — populate linked_finding_ids on each model /
    # agent from findings that reference them (finding.model_id / agent_id set
    # by data/finding_metadata.py:enrich_finding). Closes the silo bidirectionally.
    by_model: Dict[str, List[str]] = {}
    by_agent: Dict[str, List[str]] = {}
    for dom in (_ai_gov_domains or {}).values():
        if not isinstance(dom, dict):
            continue
        for f in dom.get("findings", []) or []:
            fid = f.get("finding_id")
            if f.get("model_id"):
                by_model.setdefault(f["model_id"], []).append(fid)
            if f.get("agent_id"):
                by_agent.setdefault(f["agent_id"], []).append(fid)
    for m in models:
        m["linked_finding_ids"] = by_model.get(m["id"], [])
    for a in agents:
        a["linked_finding_ids"] = by_agent.get(a["id"], [])

    return {
        "source_status": "illustrative",
        "source_note": (
            "In production sourced from model registry (e.g., MLflow / Weights & "
            "Biases) + agent observability (MCP Inspector logs · internal trace "
            "store) + supply-chain scanner (Snyk · Socket.dev). Firm-specific "
            "values illustrative; public anchors real (OWASP MCP Top 10 2025 · "
            "CVE-2025-49596 CVSS 9.4 · NIST AI RMF MEASURE-2.7 · EU AI Act Art. "
            "9 + 15). linked_finding_ids cross-reference findings carrying "
            "model_id / agent_id (forward link in finding_metadata.py)."
        ),
        "models":       models,
        "agents":       agents,
        "mcp_servers":  mcp_servers,
        "trace_recent": trace_recent,
        "hitl_posture": hitl_posture,
    }


# ── trajectory + forecast (consumed by Leadership-class views) ──────────────

def _project_trajectory(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per spec §3.1; full series + delta verdict + forecast for thin renderers."""
    if not history:
        return {
            "series":         [],
            "overall_delta":  None,
            "forecast":       None,
        }
    delta = trajectory_delta(history)
    forecast = forecast_next_period(history)
    return {
        "series":         _project_history(history),
        "overall_delta":  delta,
        "forecast":       forecast,
    }


# ── top-level make_projection ────────────────────────────────────────────────

def _build_pivot(projection: Dict[str, Any]) -> Dict[str, Any]:
    """r83 — the horizontal↔vertical pivot, as data. journey_rps DERIVES from
    the spine (which register patterns ride the money path); hv_map inverts the
    hand-reviewed cross-substrate mapping in portfolio_core/pivot_map.json
    (each hv cascade = one register pattern, replayed). Gate C40 recomputes
    both; the register renders chips FROM this block, never from typed ids."""
    import json as _json
    from pathlib import Path as _P
    spine = projection.get("journey_spine") or {}
    jr = sorted({rp for svc in (spine.get("services") or [])
                 for rp in (svc.get("patterns") or [])})
    pm_path = (_P(__file__).resolve().parent.parent.parent.parent
               / "packages" / "ui-system" / "portfolio_core" / "pivot_map.json")
    pm = _json.loads(pm_path.read_text(encoding="utf-8"))
    hv_map = {v["rp"]: {"hv_id": k, "rp_name": v["rp_name"], "why": v["why"]}
              for k, v in pm["hv_to_rp"].items()}
    return {
        "journey_rps": jr,
        "hv_map": hv_map,
        "note": ("the pivot as data: journey_rps = register patterns riding the money "
                 "path (derived from journey_spine); hv_map = which incident cascade "
                 "replays a register pattern (hand-reviewed structural mapping, "
                 "machine-gated both sides)"),
        "source": "journey_spine + portfolio_core/pivot_map.json",
    }


def make_projection(
    report: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The engine. Pure function: pipeline output → role-agnostic JSON.

    Args:
      report:  the dict returned by `graph.risk_graph.run_risk_assessment`.
      history: optional list of historical snapshots (also pipeline outputs).
               Used by trajectory / correlation / forecast.

    Returns:
      A dict matching the canonical v2.0a projection shape. Thin role apps
      consume this and ONLY this — they do not re-read the pipeline output.

    This function is intentionally pure and free of I/O so it's trivially
    testable + reproducible (per A11 byte-identical regeneration goal).
    """
    history = history or []

    # Enrich findings with v1.3.1 metadata (treatment, exposure, acceptance
    # trail, etc.) — projection consumes the enriched form.
    for did, dr in report.get("domain_reports", {}).items():
        for f in dr.get("findings", []):
            enrich_finding(f, did)
    for snap in history:
        for did, dr in snap.get("domain_reports", {}).items():
            for f in dr.get("findings", []):
                enrich_finding(f, did)

    # ── project per-domain ──
    domains_out: Dict[str, Any] = {}
    for did, dr in report.get("domain_reports", {}).items():
        domains_out[did] = _project_domain(did, dr, report, history)

    counts = _portfolio_counts(report)
    period = report.get("period", "—")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    projection: Dict[str, Any] = {
        "meta": {
            "schema_version":    PROJECTION_SCHEMA_VERSION,
            "artefact_version":  ARTEFACT_VERSION,
            "period":            period,
            "as_of":             "2026-07-14",  # pinned clock — all dates derive from this, not the build wall clock
            "generated_at":      generated_at,
            "domain_ids":        list(report.get("domain_reports", {}).keys()),
            "patterns_per_domain": report.get("patterns_per_domain", 0),
            "counts":            counts,
            "overall_rag":       report.get("overall_rag", "green"),
            # r29 — the plausibility frame as DATA (C33 gates against it): the
            # archetype is a $2-4B-revenue US consumer/crypto fintech; the
            # midpoint anchors the revenue-fraction sanity checks.
            "archetype_revenue_usd": 3_000_000_000,
        },

        "domains":         domains_out,
        "cascade_graph":   _cascade_graph(report),
        "exposure":        _exposure_block(report),
        "materiality":     _materiality_state(report),
        "trajectory":      _project_trajectory(history),
        "skew":            domain_skew(report),
        "action_log":      _action_log_ref(),

        # v2.0a flag — flips on telemetry integration
        "telemetry_status": "synthesised",
    }

    # ─── M1 additions · alpha4 warm-terminal UI inputs (additive only) ──
    # Path B fix A1/A4/A5/A6: inherent_residual built FIRST (covers all 13
    # patterns with derived portfolio aggregates), then groups DERIVES from
    # actual findings using inherent_residual.by_pattern for per-group
    # inherent/residual aggregation. Counts reconcile to meta.findings_total
    # by construction. Trajectory is post-reconciled to meta.findings_total.
    _ir = _build_inherent_residual()
    projection["inherent_residual"] = _ir
    projection["sensitivity"]       = _build_sensitivity()
    projection["dependency_layer"]  = _build_dependency_layer()
    projection["journey_spine"]         = _build_journey_spine()
    projection["pivot"]                 = _build_pivot(projection)
    projection["operating_model"]   = _build_operating_model(projection["domains"], _AS_OF_FOR_STATES)
    projection["risk_rollup"]       = _build_risk_rollup(projection["domains"])
    projection["regulation_residual"] = _build_regulation_residual(projection["materiality"])
    # Round-8 depth pass — the 3LoD lifecycle register (illustrative)
    from data.finding_metadata import internal_audit_posture
    projection["internal_audit"]    = internal_audit_posture()
    projection["groups"]            = _build_groups({"domains": domains_out}, _ir)
    projection["actuals"]           = _build_actuals()
    projection["clusters"]          = _build_clusters()
    projection["defense_layers"]    = _build_defense_layers()
    projection["ai_gov"]            = _build_ai_gov(domains_out)
    projection["patterns_meta"]     = _build_patterns_meta()
    # Path B fix H · threshold-change governance (audit-regulator) — surface
    # the threshold_history so a reviewer can verify no bound was loosened to
    # make a finding go green. Read straight from risk_patterns.json.
    _raw_patterns = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
    projection["threshold_governance"] = _raw_patterns.get("threshold_governance", {})

    # ─── Path B fix A2 · trajectory.curr_findings reconciles to meta.counts ──
    # CISO #22 + risk-officer C1.5/C1.6 + my pre-flight C1.5/C1.6: history
    # synthesizer produces a 1-finding-per-period snapshot for forward-fill
    # smoothness; the current period's actual count must reflect what the
    # report observed. Post-reconcile rather than refactor synthesizer.
    _real_total = projection["meta"]["counts"]["findings_total"]
    _traj = projection.get("trajectory", {}) or {}
    _od = _traj.get("overall_delta") or {}
    if "curr_findings" in _od:
        _prev = _od.get("prev_findings", 0)
        _od["curr_findings"] = _real_total
        _delta = _real_total - _prev
        _od["delta_findings"] = _delta
        # Path B re-audit fix (CISO): the prior reconcile patched curr/delta but
        # left direction/label stale — producing the written contradiction
        # "direction: improving" while delta = +9. MORE findings QoQ = worsening.
        # Recompute the verdict from the reconciled delta's sign so the evidence
        # JSON and the hero tile agree.
        if _delta > 0:
            _od["direction"], _od["label"] = "worsening", "WORSENING"
        elif _delta < 0:
            _od["direction"], _od["label"] = "improving", "IMPROVING"
        else:
            _od["direction"], _od["label"] = "stable", "STABLE"
        # Honesty (CISO): prev_findings is a synthesized prior, not a real Q1
        # snapshot. Mark it so a reviewer asking "16 from where?" gets an answer.
        _od["prev_findings_source"] = "synthesized prior (history_synthesizer); not a stored Q1 projection"
        _od["derivation"] = (
            "curr = meta.counts.findings_total + meta.overall_rag + meta.period "
            "(post-reconciled from the REAL report — the synthesizer's current-period "
            "slot is a mock re-run and is not trusted for the current row); "
            "direction/label recomputed from sign(delta)"
        )
    # Round-11 (external reviewer): the current-period row must be the REAL
    # report, not the synthesizer's mock re-run of it — the mock run produced
    # 0 findings/green, and reconciling only the count left a green posture
    # (and a stale period label, delta_rag, and forecast) on a red register.
    _real_rag = projection["meta"].get("overall_rag", "green")
    _real_period = projection["meta"].get("period", "—")
    if _traj.get("series"):
        _last = _traj["series"][-1]
        for k in ("total_findings", "findings_total"):
            if k in _last:
                _last[k] = _real_total
        _last["overall_rag"] = _real_rag
        _last["period"] = _real_period
        if "curr_findings" in _od:
            _od["curr_period"] = _real_period
            _rag_ord = {"green": 0, "amber": 1, "red": 2}
            _prev_rag = _traj["series"][-2].get("overall_rag", "green") if len(_traj["series"]) > 1 else "green"
            _od["delta_rag"] = _rag_ord.get(_real_rag, 0) - _rag_ord.get(_prev_rag, 0)
        # Forecast extrapolated over the mock 0 — recompute on the corrected series.
        if _traj.get("forecast") is not None:
            _traj["forecast"] = forecast_next_period(_traj["series"])
    projection["trajectory"] = _traj

    # ── r51: the strategy chooser — the board's actual decision, priced from
    # leaves that already exist. Built BEFORE the ia so the spine can cite it.
    projection["strategy_chooser"] = _build_strategy_chooser(projection)

    # ── IA Stage B (reviews/ia_stage_a_role_spine.md v2.2) — the spine ──
    projection["ia"] = _build_ia(projection)

    return projection


def _build_strategy_chooser(p: Dict[str, Any]) -> Dict[str, Any]:
    """The closing screen: two named, priced risk-management strategies and the
    explicit third path (hold at appetite, which is a signature, not a drift).

    Board rigor rules (r51, operator directive):
      - every dollar RECOMPUTES from leaves already sealed in this projection
        (sensitivity levers, dependency-node suppression, the MC baseline) —
        gate C39 asserts the equalities;
      - suppression deltas are full-isolation counterfactual CEILINGS, said so
        in the copy — a program buys a fraction of a ceiling, never the ceiling;
      - program cost/staffing is NOT modeled and is declared absent rather than
        invented;
      - the politics ride as data: accountable execs, competing commitments and
        decision routes from findings' org_context, delivery-risk flags from
        the internal-audit register, disclosure optics from the materiality map.
    """
    exp = (p.get("exposure") or {}).get("portfolio_total") or {}
    base_p95 = exp.get("p95_usd") or 0
    levers = {l["id"]: l for l in (p.get("sensitivity") or {}).get("levers", [])}

    def lev(lid: str) -> Dict[str, Any]:
        return levers.get(lid) or {}

    dl = p.get("dependency_layer") or {}
    dep_nodes = sorted(dl.get("nodes") or [], key=lambda n: -(n.get("delta_p95_usd") or 0))

    # ── the politics leaves, aggregated from the register ──
    execs: Dict[str, Dict[str, Any]] = {}
    commitments: List[str] = []
    routes: List[str] = []
    acting_gaps: List[str] = []
    acceptances: List[Dict[str, Any]] = []
    red_pattern_ids: List[str] = []
    owner_handles: List[str] = []
    for dom in (p.get("domains") or {}).values():
        for f in dom.get("findings", []):
            oc = f.get("org_context") or {}
            tr = f.get("treatment") or {}
            if f.get("overall_rag") == "red":
                red_pattern_ids.append(f.get("pattern_id"))
                ex = oc.get("accountable_exec")
                if ex:
                    execs.setdefault(ex, {"exec": ex, "red_findings": 0})["red_findings"] += 1
                    if "acting" in ex.lower() or "unfilled" in ex.lower():
                        acting_gaps.append(ex)
                cc = oc.get("competing_commitment")
                if cc and cc not in commitments:
                    commitments.append(cc)
                # normalize "TRC agenda 2026-07-15 — …" / "TRC 2026-07-15" to one
                # committee+date form so the chooser doesn't list near-duplicates
                raw_rt = str(oc.get("decision_route") or "")
                m_rt = re.search(r"\b([A-Z][A-Za-z]*(?:\s+Committee)?)\b.*?(\d{4}-\d{2}-\d{2})", raw_rt)
                rt = f"{m_rt.group(1)} {m_rt.group(2)}" if m_rt else raw_rt.split("—")[0].strip()
                if rt and rt not in routes:
                    routes.append(rt)
            if tr.get("owner_handle") and tr["owner_handle"] not in owner_handles:
                owner_handles.append(tr["owner_handle"])
            for acc in f.get("acceptance_trail") or []:
                acceptances.append({
                    "finding_id": f.get("finding_id"),
                    "accepted_by": f"{acc.get('accepted_by_name', '')} · {acc.get('accepted_by_title', '')}",
                    "expires_at": acc.get("expires_at"),
                })

    # appetite reality for the hold option: which red patterns sit at a
    # zero-tolerance / very-low stated appetite RIGHT NOW
    appetite_by_pattern = {pt.get("id"): str(pt.get("appetite") or "")
                           for pt in (p.get("patterns_meta") or {}).get("patterns", [])}
    strict_reds = sorted({pid for pid in red_pattern_ids
                          if appetite_by_pattern.get(pid, "").lower().startswith(("zero", "very low"))})

    # delivery-risk flags from the register the auditors actually keep
    ia_reg = p.get("internal_audit") or {}
    flags = [{"issue_id": i.get("issue_id"), "title": i.get("title"),
              "status": i.get("status"), "repeat": bool(i.get("repeat_finding")),
              "note": i.get("note") or ""}
             for i in ia_reg.get("issues", [])
             if i.get("status") == "PAST DUE" or i.get("repeat_finding")]
    credit_gate = next((i for i in ia_reg.get("issues", [])
                        if "2lod" in str(i.get("management_response", "")).lower()), None)

    eff_up, eff_down = lev("eff_up"), lev("eff_down")
    dep_off, dep_freq = lev("dep_layer_off"), lev("dep_freq_up")
    joint_bad = lev("joint_bad_year")
    program_nodes = [{
        "id": n.get("id"), "name": n.get("name"),
        "ceiling_delta_p95_usd": n.get("delta_p95_usd"),
        "ceiling_delta_p95_pct": n.get("delta_p95_pct"),
        "containment_boundary": n.get("containment_boundary"),
        "mitigation_note": n.get("mitigation_note"),
    } for n in dep_nodes[:4]]

    sec8k = (p.get("materiality") or {}).get("sec_8k_item_1_05") or {}

    return {
        "one_question": ("The register is priced and challenged. The remaining decision is posture: "
                         "buy down the tail, and in which order — or sign for holding it."),
        "baseline": {
            "residual_p50_usd": exp.get("p50_usd"),
            "residual_p95_usd": base_p95,
            "inherent_p95_usd": exp.get("inherent_p95_usd"),
            "joint_bad_year_p95_usd": joint_bad.get("residual_p95"),
            "cites": ["exposure.portfolio_total", "sensitivity.levers:joint_bad_year"],
        },
        "strategies": [
            {
                "id": "harden_controls",
                "name": "Harden the controls",
                "board_verb": "ENDORSE a control-effectiveness program",
                "thesis": ("The cheapest tail dollars: the estate already owns these controls — "
                           "the program raises how well they work, not how many exist."),
                "benefit_p95_usd": base_p95 - (eff_up.get("residual_p95") or base_p95),
                "benefit_basis": ("recomputes as baseline residual P95 minus the eff_up lever output "
                                  "(+10 pts effectiveness, one change, same seed)"),
                "downside_p95_usd": eff_down.get("residual_p95"),
                "downside_basis": ("the drift direction already evidenced by the register's past-due "
                                   "change-management repeat: eff_down (−20 pts) lever output"),
                "cites": {"levers": ["eff_up", "eff_down"]},
                "owners": sorted(execs.values(), key=lambda e: -e["red_findings"]),
                "owner_handles": owner_handles,
                "delivery_risk_flags": flags,
                "credit_gate": ({"issue_id": credit_gate.get("issue_id"),
                                 "title": credit_gate.get("title"),
                                 "why": ("the +10-pt credit is not bankable until 2LoD sampled "
                                         "re-testing of closed actions lands — the same independent-"
                                         "validation discipline the MC already haircuts for")}
                                if credit_gate else None),
                "political_cost": commitments,
                "time_shape": "quarterly control wins inside existing team ownership; no org boundary crossed",
            },
            {
                "id": "isolate_dependencies",
                "name": "Isolate the shared dependencies",
                "board_verb": "APPROVE an isolation program, first node scoped",
                "thesis": ("The bigger prize and the harder politics: the tail's concentration sits in "
                           "layers no single team owns — isolation is an architecture program that "
                           "crosses executive boundaries."),
                "program_nodes": program_nodes,
                "layer_ceiling_usd": dl.get("layer_contribution_usd"),
                "layer_ceiling_basis": ("the whole-layer counterfactual: dep_layer_off lever removes the "
                                        "shared-dependency mechanism entirely — a CEILING a program "
                                        "approaches, never a promise it collects"),
                "layer_off_residual_p95_usd": dep_off.get("residual_p95"),
                "downside_p95_usd": dep_freq.get("residual_p95"),
                "downside_basis": "dependency-event frequency ×2 (dep_freq_up lever)",
                "cites": {"levers": ["dep_layer_off", "dep_freq_up"],
                          "nodes": [n["id"] for n in program_nodes]},
                "ownership_gap": ("the register routes patterns to teams; the shared layers carry no "
                                  "single accountable owner today — naming one per layer is the "
                                  "program's first deliverable"
                                  + (f" (current signal: {acting_gaps[0]})" if acting_gaps else "")),
                "political_cost": commitments,
                "time_shape": "multi-quarter; displaces roadmap in the platform organizations that own the layers",
            },
        ],
        "hold_option": {
            "label": "Hold at current appetite",
            "reality": ("holding is not the absence of a decision — it is an A8 signature: "
                        f"{len(strict_reds)} red pattern(s) sit at a stated zero-tolerance / very-low "
                        "appetite, so holding requires named acceptances with expiry and conditions"),
            "strict_appetite_reds": strict_reds,
            "acceptances_on_file": acceptances,
            "stress_test_p95_usd": joint_bad.get("residual_p95"),
            "stress_test_basis": "the year a signed hold gets tested: joint_bad_year lever (freq ×1.5 + eff −20 pts)",
        },
        "recommendation": {
            "sequencing": ("2LoD sequencing under the stated judgments: bank the control credit first "
                           "(it needs no new org boundary), scope the isolation program's first node in "
                           "parallel — the largest single concentration, priced above. Either path, the "
                           "board owns the posture; the register owns the delivery."),
            "decision_routes": routes,
            "audit_committee_hook": next((f["note"] for f in flags if f.get("repeat") and "audit committee" in str(f.get("note", "")).lower()), None),
            "disclosure_note": ("This surface is an internal risk-management record. On any realized "
                                "incident, the 8-K Item 1.05 materiality determination — and its "
                                f"{sec8k.get('clock_days_from_determination', 4)}-business-day clock — is "
                                "reserved to Legal/Compliance; this page flags mapped regimes only. "
                                "Either way the decision leaves a minuted, priced record here — the "
                                "record is the defensibility."),
        },
        "provenance": {
            "tier": "derived",
            "note": ("every dollar on this screen recomputes from sensitivity.levers / "
                     "dependency_layer.nodes / exposure.portfolio_total (gate C39); program cost and "
                     "staffing are NOT modeled — declared absent, not implied"),
        },
    }


def _build_ia(p: Dict[str, Any]) -> Dict[str, Any]:
    """The spine: role-sequenced navigation DERIVED FROM the projection it
    navigates (spec §3 — the map cannot say something the page doesn't).
    Nodes single-home every section; role paths sequence them; headlines are
    computed conclusions (spec §8 genre: a finding citing a number from its own
    panel — gated, C27/C26). Roles re-sequence only: same targets, same values."""
    def _m(x):
        return f"${(x or 0) / 1e6:.1f}M"

    counts = p["meta"]["counts"]
    n_patterns = len((p.get("inherent_residual") or {}).get("by_pattern") or []) or 14
    irp = (p.get("inherent_residual") or {}).get("portfolio") or {}
    res_p95, inh_p95 = (irp.get("residual") or {}).get("p95", 0), (irp.get("inherent") or {}).get("p95", 0)
    cut_pct = round((1 - res_p95 / inh_p95) * 100) if inh_p95 else 0
    sens = p.get("sensitivity") or {}
    levers = {l.get("id"): l for l in sens.get("levers") or []}
    n_levers = len(sens.get("levers") or [])
    dl = p.get("dependency_layer") or {}
    one = dl.get("one_thing") or {}
    cascade_off = levers.get("cascade_off") or {}
    joint_bad = levers.get("joint_bad_year") or {}
    max_single = max((abs(l.get("delta_p95_pct") or 0) for lid, l in levers.items()
                      if not str(lid).startswith("joint")), default=0)
    sweep_pts = (sens.get("sev_shock_sweep") or {}).get("points") or []
    sweep_hi = sweep_pts[-1] if sweep_pts else {}
    # r51: the chooser's headline numbers come from the chooser block itself —
    # one derivation, cited twice, so spine and screen cannot disagree.
    sc = p.get("strategy_chooser") or {}
    sc_benefit = next((s.get("benefit_p95_usd") for s in sc.get("strategies", [])
                       if s.get("id") == "harden_controls"), 0)
    sc_ceiling = next((s.get("layer_ceiling_usd") for s in sc.get("strategies", [])
                       if s.get("id") == "isolate_dependencies"), 0)
    edges = len((p.get("cascade_graph") or {}).get("edges") or [])
    regs = (p.get("regulation_residual") or {}).get("by_regulation") or []
    top_reg = regs[0] if regs else {}
    caveat_regs = sum(1 for r in regs if r.get("applicability") and
                      ("ILLUSTRATIVE" in r["applicability"] or "contractual" in r["applicability"]))
    by_pat = {r["pattern_id"]: (r.get("residual") or {}).get("p95", 0)
              for r in (p.get("inherent_residual") or {}).get("by_pattern") or []}
    # round-25 (GROK P1: one source of truth for "the items on the table"):
    # the top-3 red findings by per-pattern residual P95 are SELECTED here,
    # once, deterministically (ties broken by pattern id then domain) — the
    # workbench docket (unscoped) and the Board brief both CONSUME this list;
    # neither re-ranks. Gated by C27.5 (recompute must match).
    red_rows = sorted(((by_pat.get(f.get("pattern_id"), 0), f.get("pattern_id"), did)
                       for did, d in (p.get("domains") or {}).items()
                       for f in d.get("findings") or [] if f.get("overall_rag") == "red"),
                      key=lambda r: (-r[0], r[1], r[2]))
    docket_items = [{"pattern_id": pid, "domain": did, "residual_p95": usd}
                    for usd, pid, did in red_rows[:3]]
    docket_usd = sum(it["residual_p95"] for it in docket_items)
    # round-22 gate C27.4: every $ figure spoken by an ia string must exist as a
    # numeric LEAF — this sum previously lived only inside the prose.
    # round-23: the A8 named-human gap as data — treatments routed to a team
    # handle (@...) instead of a named person. All-team routing is seeded by
    # design and labeled; making it a leaf lets the docket SPEAK it, gated.
    team_routed = sum(1 for d in (p.get("domains") or {}).values()
                      for f in d.get("findings") or []
                      if str((f.get("treatment") or {}).get("owner_handle", "")).startswith("@"))
    derived = {"docket_at_stake_usd": docket_usd,
               "docket_items": docket_items,
               "treatments_team_routed": team_routed}
    ia_issues = (p.get("internal_audit") or {}).get("issues") or []
    past_due = sum(1 for i in ia_issues if "PAST DUE" in str(i.get("status", "")))
    ag = p.get("ai_gov") or {}
    n_agents, n_models, n_mcp = (len(ag.get("agents") or []), len(ag.get("models") or []),
                                 len(ag.get("mcp_servers") or []))
    al = p.get("action_log") or {}
    n_entries = al.get("total_entries") or len(al.get("recent_entries") or [])
    n_domains = counts.get("domains_total", 0)
    n_find, n_red = counts.get("findings_total", 0), counts.get("findings_red", 0)

    # The five act names + descriptions re-home to the spine (spec §3.5, C26f).
    acts = [
        {"id": "signal",  "name": "Signal",  "desc": "telemetry firing · what crossed a threshold"},
        {"id": "pattern", "name": "Pattern", "desc": "which RP pattern · the cascade"},
        {"id": "impact",  "name": "Impact",  "desc": "inherent → controls → residual · actuals · clusters"},
        {"id": "decide",  "name": "Decide",  "desc": "verb queue · gate / accept / escalate / require_eval"},
        {"id": "attest",  "name": "Attest",  "desc": "hash-chained log · materiality · evidence"},
    ]

    nodes = [
        {"id": "stake", "beat": "STAKE", "act": "impact", "label": "what's exposed",
         "headline": f"Controls buy a {cut_pct}% cut — {_m(inh_p95)} inherent shrinks to {_m(res_p95)} residual at P95; the challenge strip prices how far to trust that credit.",
         "targets": ["translation-card-portfolio", "exposure-cards", "impact-secondary", "impact-faces",
                     "dependency-tornado", "per-pattern-translation", "actuals-grid", "actuals-footnote",
                     "recurrence-list", "group-pivot", "defense-layers"]},
        {"id": "register", "beat": "BELIEVE", "act": "signal", "label": "what fired",
         "headline": f"{n_find} findings fired across {n_domains} domains — {n_red} red, ranked by the residual dollars they carry.",
         "targets": ["queue-summary", "queue-rows", "register-summary-eyebrow", "register-summary-row",
                     "register-exposure", "register-impact-faces", "register-tbody", "pattern-primer",
                     "coverage-matrix"]},
        {"id": "cascade", "beat": "BELIEVE", "act": "pattern", "label": "how it flows",
         "headline": f"The dependency graph is ~{abs(cascade_off.get('delta_p95_pct') or 0):.0f}% of the tail — switch the {edges} cascade edges off and P95 falls to {_m(cascade_off.get('residual_p95'))}.",
         "targets": ["cascade-card"]},
        {"id": "ai-gov", "beat": "BELIEVE", "act": "signal", "label": "AI governance",
         "headline": f"{n_agents} agents, {n_models} models, {n_mcp} MCP servers under the same governance substrate — scope, HITL and supply chain in one inventory.",
         "targets": ["ai-gov-hitl", "ai-gov-models", "ai-gov-agents", "ai-gov-mcp", "ai-gov-trace"]},
        {"id": "docket", "beat": "ACT", "act": "decide", "label": "this week's docket",
         "headline": f"Three items carry {_m(docket_usd)} of residual P95 on this week's docket — none can be forced; the levers are challenge, decline-to-countersign, escalate.",
         "targets": ["monday-morning", "org-reality", "verb-summary", "verb-bar", "pause-prompt"]},
        {"id": "regulation", "beat": "ACT", "act": "decide", "label": "regulatory exposure",
         "headline": f"{top_reg.get('share_of_portfolio_p95_pct', 0)}% of stress-P95 sits under {str(top_reg.get('reg_id', 'the top regime')).replace('_', ' ')} — {caveat_regs} of {len(regs)} mapped regimes are style-mappings or contractual; applicability is a flag and a filter, not a footnote.",
         "targets": ["regulation-residual", "register-materiality", "materiality-grid"]},
        {"id": "attack", "beat": "ATTACK", "act": "attest", "label": "challenge this",
         "headline": f"No single judgment moves the number more than ±{max_single:.0f}%; a joint bad year takes it to {_m(joint_bad.get('residual_p95'))} — every assumption priced, logged, challengeable.",
         "targets": ["sensitivity-panel", "internal-audit", "evidence-ribbons", "chain-detail", "action-log"]},
        # r51: the CLOSING DECISION — two priced strategies and the signed hold.
        # The page argues (stake → evidence → challenge), then asks the board's
        # actual question; the story stays the epilogue after the choice.
        {"id": "strategy", "beat": "ACT", "act": "decide", "label": "the choice",
         "headline": (f"Two programs and a signature: +10 pts of control effectiveness is worth "
                      f"{_m(sc_benefit)} off the tail, full dependency isolation ceilings at "
                      f"{_m(sc_ceiling)} — or hold {_m(res_p95)} at appetite and sign for it."),
         "targets": ["strategy-chooser"]},
        # r43 (operator: "13 links/pages... what a mess"): the read page folds
        # home as the workbench's CLOSING CHAPTER — its unique asset, the flow
        # picture with the narrated walker; the number and docket screens it
        # duplicated already live above as panels.
        {"id": "story", "beat": "SEE", "act": "attest", "label": "the read",
         "headline": (f"The closing picture — {n_patterns} patterns through controls and the cascade into "
                      f"{_m(res_p95)} residual P95, sliced three ways; every step opens its evidence node."),
         "targets": ["story-flow"]},
    ]

    # Section-level conclusions (spec §8 genre) — render as one-line strips on
    # section headers; each cites a number that renders in that section.
    headlines = {
        "queue-summary": f"{n_red} red findings want a verb this week — the queue ranks them by residual P95, not by age.",
        "register-tbody": f"{n_find} findings, every one traceable to a public threshold source — click a row for signals, controls, org context.",
        "pattern-primer": f"{n_patterns} patterns cover the failure classes a US consumer/crypto fintech actually has — each anchored to a named public incident.",
        "coverage-matrix": f"{n_patterns} patterns × {n_domains} domains — the out-of-scope cells are declared, not hidden.",
        "cascade-card": f"{edges} declared edges carry the contagion the MC prices — the same graph the correlation model runs on.",
        "translation-card-portfolio": f"{_m(inh_p95)} gross becomes {_m(res_p95)} net — the controls between those numbers are tested below, not asserted.",
        # round-24 (GROK board review, capital-language class): never imply this
        # is a capital figure — it is the model's stress number under the
        # stated, challengeable judgments.
        "exposure-cards": f"P50 {_m((irp.get('residual') or {}).get('p50'))} is the expected year; P95 {_m(res_p95)} is the bad one — a stress number under the stated judgments, not a capital figure.",
        "impact-faces": "5 faces absorb the residual — customers and regulators before the P&L.",
        "per-pattern-translation": f"All {n_patterns} patterns walk the same lifecycle: inherent → controls credited → residual → disclosure trigger.",
        "actuals-grid": "The 12-month actuals are REAL public events, not model output — the anchor the calibration answers to.",
        "recurrence-list": f"Recurrence clusters across the {n_patterns} patterns show which ones re-fire — the argument for fixing causes, not findings.",
        "group-pivot": f"3 cuts of the same {_m(res_p95)} residual — team, function, product — accountability has an address.",
        "defense-layers": "NIST CSF 2.0 five-function coverage — where the defense is thin, the tornado's control lever shows what it costs.",
        "dependency-tornado": (f"One shared dependency — {one.get('name', '')} — carries {_m(one.get('delta_p95_usd'))} "
                               f"of the tail alone; the whole layer adds {_m(dl.get('layer_contribution_usd'))} to residual P95. "
                               "An AWS region, the customer auth plane, etcd: the model can now draw the failure a silo taxonomy cannot."),
        "monday-morning": f"{_m(docket_usd)} rides on three dockets — each names the exec, the committee, and the political cost of escalating.",
        "org-reality": (f"{team_routed} of {n_find} treatments route to a team handle, not a named human — "
                        "A8 makes that the docket's cheapest first ask. Below: who is accountable for the reds, "
                        "and which committee dates the decisions actually sit on."),
        "verb-bar": f"Four verbs, {al.get('justification_min_words', 12)}-word justifications, named humans, expiry — decisions leave evidence here ({n_entries} logged).",
        "pause-prompt": "A8: no silent automation — write-class actions pause for a named human.",
        "regulation-residual": f"{top_reg.get('share_of_portfolio_p95_pct', 0)}% of stress-P95 already sits in a disclosure regime — the binding-only filter separates statutes from style-mappings.",
        "materiality-grid": f"{len(regs)} regimes mapped with honest applicability — the determination stays with Legal/Compliance; this surface only flags.",
        "sensitivity-panel": f"{n_levers} levers, one at a time, same seed — the biggest single move is ±{max_single:.0f}%, and σ-co-movement is priced to +{sweep_hi.get('delta_p95_pct', 0)}%.",
        "internal-audit": f"{len(ia_issues)} audit issues with real lifecycle states — {past_due} PAST DUE and a repeat finding shown, not laundered.",
        "evidence-ribbons": f"All {n_patterns} patterns cite public threshold sources — hover any bound for the derivation.",
        "chain-detail": ("SHA-256 hash-chained action log — edit any entry and the chain breaks visibly. "
                         "This is the SEA 17a-4 books-and-records shape (audit-trail integrity), finally claimed."),
        "action-log": f"{n_entries} actions on the chain — each with actor, justification, expiry, and the threshold values at decision time.",
        "ai-gov-hitl": "HITL posture per A8 — write-class agent verbs carry human sign-off with expiry.",
        "ai-gov-models": f"{n_models} models tracked production/shadow/staging — registry entry is traceability, not a behavior guarantee.",
        "ai-gov-agents": f"{n_agents} agents with scope + 24h violations visible — the RE-04 class atg catches lives here too.",
        "ai-gov-mcp": f"{n_mcp} MCP servers: vendor tier, hash-pin, KEV scan — the supply chain under the agents.",
        "ai-gov-trace": "The last 10 tool calls, flagged events highlighted — governance is a live tail, not a quarterly PDF.",
        "story-flow": (f"{_m(inh_p95)} inherent, minus tested controls, plus cascade compounding, is {_m(res_p95)} "
                       "residual — the whole walk in one animated frame, drawn from this projection only."),
        "strategy-chooser": (f"Two priced postures — {_m(sc_benefit)} bankable from control effectiveness, "
                             f"{_m(sc_ceiling)} ceiling from dependency isolation — and the signed hold; "
                             "program cost is declared not-modeled, never implied."),
    }

    # r51: every role closes on the CHOICE, then the story epilogue.
    paths = {
        "basic":       ["stake", "register", "cascade", "ai-gov", "docket", "regulation", "attack", "strategy", "story"],
        "leadership":  ["stake", "docket", "regulation", "register", "attack", "strategy", "story"],
        "engineering": ["register", "cascade", "docket", "stake", "ai-gov", "attack", "strategy", "story"],
        "audit":       ["attack", "register", "regulation", "ai-gov", "stake", "docket", "strategy", "story"],
    }

    return {
        # round-25 (GROK: "three decisions" on the spine vs four resolutions on
        # the Board brief read as drift): the thesis now speaks the Board's
        # altitude; the docket node still counts its three work ITEMS.
        "thesis": (f"{n_patterns} failure patterns roll up to one challengeable number — {_m(res_p95)} residual P95 — "
                   f"and this week it walks into the boardroom as five resolutions."),
        "acts": acts,
        "nodes": nodes,
        "paths": paths,
        "headlines": headlines,
        "default_role": "basic",
        "derived": derived,
        "source_note": ("Spine, role paths and every headline derive from this projection — "
                        "the map cannot say something the page doesn't (spec C26/C27 gates)."),
    }


# ── debug / verify helpers ───────────────────────────────────────────────────

def projection_summary(projection: Dict[str, Any]) -> str:
    """Compact one-screen summary of the projection. Useful for verification."""
    meta = projection["meta"]
    counts = meta["counts"]
    lines = [
        f"projection · schema {meta['schema_version']} · {ARTEFACT_VERSION}",
        f"period={meta['period']} · generated={meta['generated_at']}",
        f"counts: {counts['findings_total']} findings ({counts['findings_red']}R/{counts['findings_amber']}A/{counts['findings_green']}G) · {counts['domains_total']} domains ({counts['domains_red']}R/{counts['domains_amber']}A/{counts['domains_green']}G)",
        f"cascade edges: {len(projection['cascade_graph']['edges'])} ({sum(1 for e in projection['cascade_graph']['edges'] if e['currently_firing'])} currently firing)",
        f"materiality: 8K={projection['materiality']['sec_8k_item_1_05']['status']} · OCC={projection['materiality']['occ_12cfr30_app_d']['status']} · GDPR={projection['materiality']['gdpr_art_33']['status']} · EU-AI={projection['materiality']['eu_ai_act_high_risk']['status']}",
        f"trajectory series: {len(projection['trajectory']['series'])} periods · forecast={projection['trajectory']['forecast'].get('projected_findings') if projection['trajectory']['forecast'] else 'n/a'}",
        f"action_log: {projection['action_log']['path']} (schema v{projection['action_log']['schema_version']})",
        f"telemetry: {projection['telemetry_status']}",
    ]
    return "\n".join(lines)
