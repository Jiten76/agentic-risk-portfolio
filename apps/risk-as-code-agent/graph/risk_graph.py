"""
Risk-as-Code Agent Graph
========================
LangGraph multi-agent pipeline:

  [Ingestion Agent] → [Mapping Agent] → [Evidence Agent] → [Attestation Agent]

Each node is a pure function operating on shared RiskState.
The graph can run in batch mode (all domains) or single-domain mode.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

# Internal imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.mock_metrics import generate_multi_domain_snapshot, get_demo_scenario
from utils.llm_client import generate_evidence_summary, generate_executive_summary, generate_attestation_statement

# ─── State Schema ────────────────────────────────────────────────────────────

class RiskState(TypedDict):
    # Input
    scenario_map: Dict[str, str]          # {domain_id: scenario}
    target_domains: Optional[List[str]]   # None = all domains

    # Ingestion output
    raw_snapshot: Dict[str, Any]

    # Mapping output
    pattern_hits: Dict[str, List[Dict]]   # {domain_id: [pattern_hit, ...]}

    # Evidence output
    evidence_items: Dict[str, List[Dict]] # {domain_id: [evidence_item, ...]}

    # Attestation output
    attestation_report: Dict[str, Any]

    # Metadata
    run_id: str
    started_at: str
    completed_at: Optional[str]
    errors: List[str]


# ─── Load reference data ─────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

with open(os.path.join(_DATA_DIR, "risk_patterns.json")) as f:
    _RISK_PATTERNS = {p["id"]: p for p in json.load(f)["patterns"]}

with open(os.path.join(_DATA_DIR, "service_catalog.json")) as f:
    _SERVICE_CATALOG = {d["id"]: d for d in json.load(f)["domains"]}


# ─── Agent Nodes ─────────────────────────────────────────────────────────────

def ingestion_agent(state: RiskState) -> RiskState:
    """
    Ingestion Agent — collects telemetry from all target domains.
    In production this would pull from Prometheus/VictoriaMetrics/Thanos.
    Here we generate synthetic but structurally identical snapshots.
    """
    try:
        scenario_map = state.get("scenario_map", {})
        raw = generate_multi_domain_snapshot(scenario_map)

        # Filter to target domains if specified
        if state.get("target_domains"):
            raw["domains"] = {
                k: v for k, v in raw["domains"].items()
                if k in state["target_domains"]
            }

        return {**state, "raw_snapshot": raw}

    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"ingestion_agent: {e}"]}


def mapping_agent(state: RiskState) -> RiskState:
    """
    Mapping Agent — evaluates each signal against risk pattern thresholds.
    Produces a list of pattern hits per domain with RAG status.
    """
    try:
        domains = state["raw_snapshot"].get("domains", {})
        pattern_hits: Dict[str, List[Dict]] = {}

        for domain_id, domain_data in domains.items():
            metrics = domain_data.get("metrics", {})
            hits = []

            for pattern_id, pattern in _RISK_PATTERNS.items():
                breached = {}
                for signal in pattern.get("signals", []):
                    if signal not in metrics:
                        continue
                    val = metrics[signal]
                    thresholds = pattern.get("thresholds", {}).get(signal)
                    if not thresholds:
                        continue

                    green = thresholds["green"]
                    amber = thresholds["amber"]
                    red = thresholds["red"]

                    # Handle both "lower is better" and "higher is better" signals.
                    # Convention: a value EXACTLY on a boundary lands in the WORSE
                    # bucket (hitting the amber line is amber, not green) — inclusive
                    # on the worse side.
                    higher_is_better = green > amber

                    if higher_is_better:      # worse = lower → inclusive at/below
                        if val <= red:
                            rag = "red"
                        elif val <= amber:
                            rag = "amber"
                        else:
                            rag = "green"
                    else:                     # worse = higher → inclusive at/above
                        if val >= red:
                            rag = "red"
                        elif val >= amber:
                            rag = "amber"
                        else:
                            rag = "green"

                    if rag in ("amber", "red"):
                        breached[signal] = {"value": val, "rag": rag, "threshold": thresholds}

                if breached:
                    # Overall RAG = worst signal
                    overall = "red" if any(v["rag"] == "red" for v in breached.values()) else "amber"
                    hits.append({
                        "pattern_id": pattern_id,
                        "pattern_name": pattern["name"],
                        "pattern_description": pattern["description"],
                        "appetite": pattern["appetite"],
                        "overall_rag": overall,
                        "signals_exceeded": breached,
                        "signal_summary": ", ".join(
                            f"{k}={v['value']}" for k, v in list(breached.items())[:3]
                        ),
                        # Surface the pattern's grounding into the finding
                        # so UI / PDF can cite the threshold source + anchoring
                        # incident next to each finding.
                        "threshold_source":     pattern.get("threshold_source"),
                        "threshold_source_url": pattern.get("threshold_source_url"),
                        "incident_reference":   pattern.get("incident_reference", []),
                        "nist_function":        pattern.get("nist_function"),
                    })

            # Sort: red first, then amber
            hits.sort(key=lambda x: (0 if x["overall_rag"] == "red" else 1))
            pattern_hits[domain_id] = hits

        return {**state, "pattern_hits": pattern_hits}

    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"mapping_agent: {e}"], "pattern_hits": {}}


def evidence_agent(state: RiskState) -> RiskState:
    """
    Evidence Agent — generates LLM-backed narrative for each finding.
    Each pattern hit becomes an evidence item with audit-ready prose.
    """
    try:
        evidence_items: Dict[str, List[Dict]] = {}

        for domain_id, hits in state.get("pattern_hits", {}).items():
            items = []
            for hit in hits:
                narrative = generate_evidence_summary(
                    domain=domain_id,
                    pattern_id=hit["pattern_id"],
                    pattern_name=hit["pattern_name"],
                    pattern_description=hit["pattern_description"],
                    signals_exceeded=hit["signals_exceeded"],
                    appetite_statement=hit["appetite"],
                )
                items.append({
                    **hit,
                    "evidence_narrative": narrative,
                    "evidence_collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "evidence_source": "telemetry-auto",
                    "requires_owner_attestation": hit["overall_rag"] == "red",
                })
            evidence_items[domain_id] = items

        return {**state, "evidence_items": evidence_items}

    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"evidence_agent: {e}"], "evidence_items": {}}


def attestation_agent(state: RiskState) -> RiskState:
    """
    Attestation Agent — assembles the final structured report.
    Produces a domain-level summary + overall posture assessment.
    """
    try:
        # Quarter calculation
        now = datetime.now(timezone.utc)
        quarter = f"Q{(now.month - 1) // 3 + 1}"
        period = f"{now.year}-{quarter}"

        domain_reports = {}
        overall_rag = "green"

        for domain_id, items in state.get("evidence_items", {}).items():
            catalog = _SERVICE_CATALOG.get(domain_id, {})
            tier = catalog.get("tier", 2)

            red_count = sum(1 for i in items if i["overall_rag"] == "red")
            amber_count = sum(1 for i in items if i["overall_rag"] == "amber")
            domain_rag = "green" if not items else ("red" if red_count > 0 else "amber")

            if domain_rag == "red":
                overall_rag = "red"
            elif domain_rag == "amber" and overall_rag == "green":
                overall_rag = "amber"

            open_items = [
                {"pattern": i["pattern_id"], "rag": i["overall_rag"], "signals": i["signal_summary"]}
                for i in items if i["overall_rag"] in ("red", "amber")
            ]

            exec_summary = generate_executive_summary(domain_id, items, tier)
            attestation = generate_attestation_statement(
                domain=domain_id,
                period=period,
                total_patterns=len(_RISK_PATTERNS),
                findings_count=len(items),
                open_items=open_items,
            )

            domain_reports[domain_id] = {
                "domain_id": domain_id,
                "domain_name": catalog.get("name", domain_id),
                "tier": tier,
                "period": period,
                "overall_rag": domain_rag,
                "red_findings": red_count,
                "amber_findings": amber_count,
                "total_findings": len(items),
                "patterns_assessed": len(_RISK_PATTERNS),
                "executive_summary": exec_summary,
                "attestation_statement": attestation,
                "findings": items,
                "open_items": open_items,
            }

        report = {
            "report_id": state["run_id"],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "period": period,
            "overall_rag": overall_rag,
            "domains_assessed": len(domain_reports),
            "total_findings": sum(r["total_findings"] for r in domain_reports.values()),
            "methodology": "telemetry-backed evidence — Risk-as-Code Agent Framework v1.0",
            "framework_alignment": ["NIST CSF 2.0", "ISO 31000", "DORA"],
            "domain_reports": domain_reports,
            "errors": state.get("errors", []),
        }

        return {
            **state,
            "attestation_report": report,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"attestation_agent: {e}"],
            "attestation_report": {},
        }


# ─── Graph Assembly ───────────────────────────────────────────────────────────

def build_risk_graph():
    graph = StateGraph(RiskState)

    graph.add_node("ingestion", ingestion_agent)
    graph.add_node("mapping", mapping_agent)
    graph.add_node("evidence", evidence_agent)
    graph.add_node("attestation", attestation_agent)

    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "mapping")
    graph.add_edge("mapping", "evidence")
    graph.add_edge("evidence", "attestation")
    graph.add_edge("attestation", END)

    return graph.compile()


# ─── Entry point ─────────────────────────────────────────────────────────────

def run_risk_assessment(
    scenario_map: Dict[str, str] = None,
    target_domains: List[str] = None,
    demo: bool = False,
) -> Dict[str, Any]:
    """Run the full risk assessment pipeline."""
    import uuid
    # Round-12: the register must be reproducible per RUN — re-seed the
    # telemetry stream so identical inputs give an identical register
    # (three unseeded rebuilds had produced 27/25/26 findings; C25 gates this).
    from data.mock_metrics import reset_rng
    reset_rng()

    if demo:
        # Pre-baked scenario: trading degraded, payments in incident
        scenario_map = {
            "trading": "degraded",
            "payments": "incident",
            "custody": "normal",
            "identity": "normal",
            "platform": "degraded",
        }

    initial_state: RiskState = {
        "scenario_map": scenario_map or {},
        "target_domains": target_domains,
        "raw_snapshot": {},
        "pattern_hits": {},
        "evidence_items": {},
        "attestation_report": {},
        "run_id": str(uuid.uuid4())[:8],
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "completed_at": None,
        "errors": [],
    }

    graph = build_risk_graph()
    result = graph.invoke(initial_state)
    return result["attestation_report"]


if __name__ == "__main__":
    print("Running demo risk assessment...")
    report = run_risk_assessment(demo=True)
    print(json.dumps(report, indent=2))
