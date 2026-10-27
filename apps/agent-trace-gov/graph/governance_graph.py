"""
Agentic Traceability & Governance Pipeline
==========================================
LangGraph pipeline that observes multi-agent workflows and produces:
  - Full action trace with PII detection + redaction
  - Data lineage map
  - Risk event log with framework citations
  - SOC 2 / audit evidence export

  [Trace Collector] → [PII Scanner] → [Risk Classifier] → [Evidence Builder]
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.agent_simulator import generate_workflow_batch
from utils.gov_llm import generate_risk_narrative, generate_soc2_evidence

# ── Load reference data ───────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
with open(os.path.join(_DATA_DIR, "action_schema.json")) as f:
    _SCHEMA = json.load(f)

_RISK_EVENTS = {re["id"]: re for re in _SCHEMA["risk_events"]}
_ACTION_TYPES = {at["id"]: at for at in _SCHEMA["action_types"]}
_LOW_CONF_THRESHOLD = 0.5  # automated-decision confidence floor → RE-05
# r56: consequence classes of targets (funds movement / credit pulls / outbound
# comms vs books-and-records sinks) — the severity deriver keys on these.
_TARGET_CLASSES = _SCHEMA.get("target_classes", {})
_EFFECTFUL_TOOLS = set(_TARGET_CLASSES.get("effectful_tools", []))
_RECORD_STORES = set(_TARGET_CLASSES.get("record_stores", []))
# actions that ACT on the world (vs read/observe) — with an effectful or
# external or record-store target they demonstrate unauthorized-action CAPABILITY
_EFFECT_BEARING_ACTIONS = {"tool_execution", "external_api_call", "data_write", "decision"}


def _closes_cycle(start: str, target: str, edges: set) -> bool:
    """True if `start` can already reach `target` over the directed delegation
    `edges` — i.e. adding a target→start edge would CLOSE a cycle. This catches a
    general N-cycle (A→B→C→A), not just an immediately-repeated 2-cycle edge."""
    if start is None or target is None:
        return False
    stack, seen = [start], set()
    while stack:
        n = stack.pop()
        if n == target:
            return True
        if n in seen:
            continue
        seen.add(n)
        for (u, v) in edges:
            if u == n:
                stack.append(v)
    return False


def _derive_risk_events(trace: Dict[str, Any], seen_delegations: set) -> List[str]:
    """Derive RE-xx from a trace's RAW signals — real rules over
    action_type × egress × pii-scan × consent × scope × confidence. This is the
    classification; the trace stream carries no risk-event labels. The same rules
    would run over real OpenTelemetry spans carrying the same fields."""
    action = trace.get("action_type", "")
    target = (trace.get("target") or "").lower()
    schema = _ACTION_TYPES.get(action, {})
    pii = bool(trace.get("pii_detected"))
    consent_ok = trace.get("consent_verified", True)
    scope = trace.get("agent_scope") or []
    is_external = action == "external_api_call" or "external" in target
    res: List[str] = []

    # Scope: a DEFINED scope the action exceeds is a violation; NO scope at all
    # means the agent is UNGOVERNED — a concern in its own right, never a silent
    # clean pass (principle: absence of policy ≠ compliance — mirrors rac §4).
    scope_defined = bool(scope)
    scope_violation = scope_defined and action not in scope
    ungoverned = not scope_defined
    # RE-04 · action outside a defined scope, OR a sensitive action (external
    #         egress / delegation) by an agent with no authorized scope at all.
    if scope_violation or (ungoverned and (is_external or action == "agent_delegation")):
        res.append("RE-04")
    # RE-01 · PII present in an output-bearing (pii-scannable) action
    if pii and schema.get("pii_scan_required"):
        res.append("RE-01")
    # RE-02 · a consent-requiring action with no consent record
    if schema.get("requires_consent_check") and not consent_ok:
        res.append("RE-02")
    # RE-03 · external egress carrying PII, out of / without a satisfiable scope,
    #         or lacking consent (an ungoverned egress can't be asserted in-scope)
    if is_external and (pii or scope_violation or ungoverned or not consent_ok):
        res.append("RE-03")
    # RE-05 · automated decision below the confidence floor
    conf = trace.get("confidence")
    if action == "decision" and conf is not None and conf < _LOW_CONF_THRESHOLD:
        res.append("RE-05")
    # RE-06 · a write to a books-and-records-shaped sink whose lineage is broken
    #         (r56 — first activation of the class: the 17a-4 preservation shape)
    if action == "data_write" and trace.get("target") in _RECORD_STORES \
            and trace.get("lineage_complete", True) is False:
        res.append("RE-06")
    # RE-08 · a delegation edge that closes a CYCLE in the workflow's delegation
    #         graph = an agent loop — an immediately-repeated edge (2-cycle) OR a
    #         general N-cycle (A→B→C→A), detected by reachability.
    if action == "agent_delegation":
        src, tgt = trace.get("agent_id"), trace.get("target")
        edge = (src, tgt)
        if edge in seen_delegations or _closes_cycle(tgt, src, seen_delegations):
            res.append("RE-08")
        seen_delegations.add(edge)
    return res


def _derive_severity(re_id: str, trace: Dict[str, Any]) -> Dict[str, str]:
    """r56 — the consequence-driven severity table (operator finding: category-
    driven severity read as a privacy scanner; a CRO's scale anchors to
    CONSEQUENCE). One derivation, stamped on the event AND consumed by the
    projection — class `severity_default` is only the floor.

    Order of consequence: demonstrated unauthorized-ACTION capability >
    mandatory-notification data event > authorization/process gap > oversight
    signal. Every basis sentence cites only fields present on this trace."""
    action = trace.get("action_type", "")
    target = trace.get("target") or ""
    tl = target.lower()
    pii_types = sorted((trace.get("pii_detected") or {}).keys())
    pii = bool(pii_types)
    scope = trace.get("agent_scope") or []
    scope_defined = bool(scope)
    scope_violation = scope_defined and action not in scope
    ungoverned = not scope_defined
    is_external = action == "external_api_call" or "external" in tl
    effect_bearing = action in _EFFECT_BEARING_ACTIONS and (
        target in _EFFECTFUL_TOOLS or target in _RECORD_STORES or is_external
        or action == "decision")
    agent = trace.get("agent_id", "the agent")
    default = _RISK_EVENTS.get(re_id, {}).get("severity_default", "medium")
    sev, basis = default, ""

    if re_id == "RE-04":
        if (scope_violation or ungoverned) and effect_bearing:
            sev = "critical"
            basis = (f"{agent} executed {action} against {target} "
                     + ("outside scope " + str(scope) if scope_defined else "with NO defined scope")
                     + " — unauthorized-action capability demonstrated in trace"
                     + (" (effectful tool)" if target in _EFFECTFUL_TOOLS else ""))
        else:
            sev = "high"
            basis = (f"{agent} performed {action} on {target} outside its authorization"
                     + (" (read-class action)" if not effect_bearing else ""))
    elif re_id == "RE-03":
        if pii and (scope_violation or ungoverned):
            sev = "critical"
            basis = (f"PII classes {pii_types} crossed to {target} by an agent outside "
                     "authorization — exfiltration shape")
        elif pii:
            sev = "high"
            basis = (f"PII classes {pii_types} crossed to {target} — candidate personal-data "
                     "breach (GDPR Art. 4(12)); notification clock runs from awareness")
        elif scope_violation or ungoverned:
            sev = "high"
            basis = f"egress to {target} outside authorization; no PII detected on this flow"
        else:
            sev = "medium"
            basis = f"egress to {target} with a consent gap; no PII detected on this flow"
    elif re_id == "RE-01":
        redacted = bool(trace.get("pii_redacted"))
        if is_external or not redacted:
            sev = "high"
            basis = (f"PII classes {pii_types} in {action} output"
                     + (f" bound for {target}" if is_external else " without redaction"))
        else:
            sev = "medium"
            basis = f"PII classes {pii_types} in {action} output; redaction applied, internal sink"
    elif re_id == "RE-02":
        if is_external:
            sev = "high"
            basis = f"consent record absent and the data egresses to {target}"
        else:
            sev = "medium"
            basis = f"consent record absent on {action} to {target} (internal sink)"
    elif re_id == "RE-05":
        conf = trace.get("confidence")
        sev = "high"
        basis = f"automated {target} decision at confidence {conf} < {_LOW_CONF_THRESHOLD}"
        # a human catch downstream is judged at the finding level; the event
        # itself records the sub-floor decision fact
    elif re_id == "RE-06":
        sev = "high" if target in _RECORD_STORES else "medium"
        basis = (f"write to record store {target} with lineage_complete=false — "
                 "books-and-records preservation shape (17a-4 class)")
    elif re_id == "RE-08":
        sev = "medium" if effect_bearing else "low"
        basis = f"delegation cycle at {agent}→{target}" + (" containing effect-bearing actions" if effect_bearing else " (delegation-only)")

    return {"severity": sev, "severity_basis": basis, "severity_default": default}

# ── State ─────────────────────────────────────────────────────────────────────

class GovernanceState(TypedDict):
    workflows:          List[Dict[str, Any]]   # raw workflow batch
    cleaned_traces:     List[Dict[str, Any]]   # PII-scanned traces
    risk_events:        List[Dict[str, Any]]   # classified risk events
    lineage_map:        Dict[str, Any]         # data flow graph
    evidence_items:     List[Dict[str, Any]]   # SOC 2 / audit evidence
    governance_report:  Dict[str, Any]         # final report
    run_id:             str
    started_at:         str
    completed_at:       Optional[str]
    errors:             List[str]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def trace_collector(state: GovernanceState) -> GovernanceState:
    """
    Collect and normalize action traces from all workflows.
    Flattens workflow batch into a unified trace stream.
    """
    try:
        all_traces = []
        for wf in state["workflows"]:
            for trace in wf.get("traces", []):
                all_traces.append({**trace, "workflow_scenario": wf["scenario"]})

        return {**state, "cleaned_traces": all_traces}
    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"trace_collector: {e}"],
                "cleaned_traces": []}


def pii_scanner(state: GovernanceState) -> GovernanceState:
    """
    Scan all traces for PII. Redact where action type requires it.
    Tag each trace with PII classification and consent status.
    """
    try:
        scanned = []
        for trace in state["cleaned_traces"]:
            action_schema = _ACTION_TYPES.get(trace.get("action_type", ""), {})

            # Enforce redaction for external calls and writes with PII
            if trace.get("pii_detected") and action_schema.get("pii_scan_required"):
                trace = {
                    **trace,
                    "pii_redacted": True,
                    "payload_preview": "[REDACTED — PII detected]",
                    "governance_flag": "pii_redaction_applied",
                }

            # Flag missing consent for actions that require it
            if action_schema.get("requires_consent_check") and not trace.get("consent_verified"):
                trace = {
                    **trace,
                    "governance_flag": trace.get("governance_flag", "") + "|consent_missing",
                }

            scanned.append(trace)

        return {**state, "cleaned_traces": scanned}
    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"pii_scanner: {e}"]}


def risk_classifier(state: GovernanceState) -> GovernanceState:
    """
    Classify risk events from traces. Build data lineage map.
    Each risk event gets severity, framework citation, and affected traces.
    """
    try:
        seen_delegations: Dict[str, set] = {}   # per-workflow delegation edges (RE-08)
        classified_traces = []
        risk_events = []
        lineage_nodes = {}
        lineage_edges = []

        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for trace in state["cleaned_traces"]:
            wf = trace.get("workflow_id", "unknown")
            # DERIVE the risk events from the trace's raw signals + write them back
            # onto the trace so downstream (projection/UI) reads classifier output.
            derived = _derive_risk_events(trace, seen_delegations.setdefault(wf, set()))
            # r56: severity derives per (event × trace) from consequence, not
            # category — one derivation here, consumed everywhere downstream.
            details = {re_id: _derive_severity(re_id, trace) for re_id in derived}
            trace = {**trace, "risk_events": derived, "risk_event_details": details}
            classified_traces.append(trace)

            # Build lineage
            src = trace.get("agent_id", "unknown")
            dst = trace.get("target", "unknown")
            if src not in lineage_nodes:
                lineage_nodes[src] = {"id": src, "type": "agent", "pii_touched": False}
            if dst not in lineage_nodes:
                lineage_nodes[dst] = {"id": dst, "type": "system", "pii_touched": False}
            if trace.get("pii_detected"):
                lineage_nodes[src]["pii_touched"] = True
                lineage_nodes[dst]["pii_touched"] = True

            lineage_edges.append({
                "from": src, "to": dst,
                "action": trace.get("action_type"),
                "pii": bool(trace.get("pii_detected")),
                "risk_events": derived,
                # r56: the edge carries the WORST derived severity of the events
                # riding it — the graph colors from consequence, not category
                "severity": (min((details[r]["severity"] for r in derived),
                                 key=lambda s: sev_rank.get(s, 9)) if derived else None),
                "workflow_id": trace.get("workflow_id"),
            })

            # Aggregate the classified risk events
            for re_id in derived:
                schema = _RISK_EVENTS.get(re_id, {})
                risk_events.append({
                    "event_id":      str(uuid.uuid4())[:8],
                    "risk_event_id": re_id,
                    "name":          schema.get("name", re_id),
                    "severity":      details[re_id]["severity"],
                    "severity_basis": details[re_id]["severity_basis"],
                    "severity_default": details[re_id]["severity_default"],
                    "framework":     schema.get("framework", "—"),
                    "auto_redact":   schema.get("auto_redact", False),
                    "alert_required": schema.get("alert_required", False),
                    "workflow_id":   trace.get("workflow_id"),
                    "trace_id":      trace.get("trace_id"),
                    "agent_id":      trace.get("agent_id"),
                    "action_type":   trace.get("action_type"),
                    "target":        trace.get("target"),
                    "timestamp":     trace.get("timestamp"),
                    "status":        trace.get("status"),
                })

        # Sort risk events: critical first
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        risk_events.sort(key=lambda x: severity_order.get(x["severity"], 9))

        lineage_map = {
            "nodes": list(lineage_nodes.values()),
            "edges": lineage_edges,
            "pii_flows": [e for e in lineage_edges if e["pii"]],
            "external_flows": [e for e in lineage_edges
                               if "external" in e.get("to", "").lower()],
        }

        return {**state, "cleaned_traces": classified_traces,
                "risk_events": risk_events, "lineage_map": lineage_map}

    except Exception as e:
        return {**state,
                "errors": state.get("errors", []) + [f"risk_classifier: {e}"],
                "risk_events": [], "lineage_map": {}}


def evidence_builder(state: GovernanceState) -> GovernanceState:
    """
    Build SOC 2 / audit evidence items from risk events and lineage.
    Produces a governance report ready for IRM ingestion.
    """
    try:
        evidence_items = []
        risk_events = state.get("risk_events", [])
        workflows = state.get("workflows", [])
        lineage = state.get("lineage_map", {})

        # Group risk events by type for evidence consolidation
        by_type: Dict[str, List] = {}
        for re in risk_events:
            re_id = re["risk_event_id"]
            by_type.setdefault(re_id, []).append(re)

        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for re_id, events in by_type.items():
            schema = _RISK_EVENTS.get(re_id, {})
            # r56: the class's evidence severity is its WORST derived instance —
            # consequence-driven, never the static class value
            worst = min((e.get("severity", "medium") for e in events),
                        key=lambda s: sev_rank.get(s, 9))
            narrative = generate_risk_narrative(
                risk_event_id=re_id,
                risk_event_name=schema.get("name", re_id),
                severity=worst,
                framework=schema.get("framework", "—"),
                occurrence_count=len(events),
                affected_agents=list({e["agent_id"] for e in events}),
                affected_workflows=list({e["workflow_id"] for e in events}),
            )
            evidence_items.append({
                "evidence_id":       f"EV-{str(uuid.uuid4())[:6].upper()}",
                "risk_event_id":     re_id,
                "risk_event_name":   schema.get("name", re_id),
                "severity":          worst,
                "framework":         schema.get("framework", "—"),
                "framework_source_url": schema.get("framework_source_url"),
                "incident_reference": schema.get("incident_reference", []),
                "occurrence_count":  len(events),
                "affected_agents":   list({e["agent_id"] for e in events}),
                "affected_workflows": list({e["workflow_id"] for e in events}),
                "narrative":         narrative,
                "alert_required":    schema.get("alert_required", False),
                "collected_at":      datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "evidence_source":   "agent-trace-gov-v1.1",
            })

        # SOC 2 Trust Service Criteria mapping
        soc2_evidence = generate_soc2_evidence(
            total_workflows=len(workflows),
            risk_events=risk_events,
            pii_flows=len(lineage.get("pii_flows", [])),
            external_flows=len(lineage.get("external_flows", [])),
        )

        # Build final report
        critical = sum(1 for e in evidence_items if e["severity"] == "critical")
        high     = sum(1 for e in evidence_items if e["severity"] == "high")
        overall  = "critical" if critical > 0 else ("high" if high > 0 else
                   ("medium" if evidence_items else "clean"))

        report = {
            "report_id":          state["run_id"],
            "generated_at":       datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "overall_posture":    overall,
            "workflows_analyzed": len(workflows),
            "total_actions":      len(state.get("cleaned_traces", [])),
            "risk_events_total":  len(risk_events),
            "evidence_items":     evidence_items,
            "lineage_summary": {
                "total_nodes":     len(lineage.get("nodes", [])),
                "total_edges":     len(lineage.get("edges", [])),
                "pii_flow_count":  len(lineage.get("pii_flows", [])),
                "external_flow_count": len(lineage.get("external_flows", [])),
            },
            "soc2_evidence":      soc2_evidence,
            "lineage_map":        lineage,
            "framework_alignment": [
                f["name"] if isinstance(f, dict) else f
                for f in _SCHEMA.get("compliance_frameworks", [])
            ],
            "methodology":        "agent-trace-gov v1.1 — action-level traceability",
            "errors":             state.get("errors", []),
        }

        return {
            **state,
            "evidence_items":    evidence_items,
            "governance_report": report,
            "completed_at":      datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    except Exception as e:
        return {**state,
                "errors": state.get("errors", []) + [f"evidence_builder: {e}"],
                "governance_report": {}}


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_governance_graph():
    graph = StateGraph(GovernanceState)
    graph.add_node("trace_collector", trace_collector)
    graph.add_node("pii_scanner",     pii_scanner)
    graph.add_node("risk_classifier", risk_classifier)
    graph.add_node("evidence_builder",evidence_builder)

    graph.set_entry_point("trace_collector")
    graph.add_edge("trace_collector", "pii_scanner")
    graph.add_edge("pii_scanner",     "risk_classifier")
    graph.add_edge("risk_classifier", "evidence_builder")
    graph.add_edge("evidence_builder", END)

    return graph.compile()


def run_governance_analysis_full(n_workflows: int = 10, seed: Optional[int] = None) -> Dict[str, Any]:
    """Run governance analysis and return the FULL result state — workflows,
    cleaned_traces (real per-trace timestamps + data_classification),
    risk_events, lineage_map, evidence_items, governance_report.

    The v2 dashboard adapter (utils/projection.py) consumes this richer state so
    it can derive honest temporal fields (first_detected = min real trace
    timestamp) and counted magnitude (records-exposed from pii flows × data
    classes) — rather than minting values from the thinner report alone.

    When ``seed`` is given the whole run is deterministic (seeded simulator +
    derived run_id + fixed start clock), so the projection — and the artefact
    seal computed over it — is reproducible from the stated (n, seed).
    Additive: run_governance_analysis() below is unchanged."""
    workflows = generate_workflow_batch(n_workflows, seed=seed)
    if seed is not None:
        run_id = "RUN-" + hashlib.md5(f"{seed}-{n_workflows}".encode()).hexdigest()[:8]
        started_at = "2026-06-01T09:00:00Z"
    else:
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    initial: GovernanceState = {
        "workflows":         workflows,
        "cleaned_traces":    [],
        "risk_events":       [],
        "lineage_map":       {},
        "evidence_items":    [],
        "governance_report": {},
        "run_id":            run_id,
        "started_at":        started_at,
        "completed_at":      None,
        "errors":            [],
    }
    graph = build_governance_graph()
    return graph.invoke(initial)


def run_governance_analysis(n_workflows: int = 10, seed: Optional[int] = None) -> Dict[str, Any]:
    """Run governance analysis on a batch of synthetic agent workflows."""
    return run_governance_analysis_full(n_workflows, seed=seed)["governance_report"]


if __name__ == "__main__":
    import json
    print("Running governance analysis on 10 synthetic workflows...")
    report = run_governance_analysis(10)
    print(f"Overall posture: {report['overall_posture'].upper()}")
    print(f"Workflows analyzed: {report['workflows_analyzed']}")
    print(f"Risk events: {report['risk_events_total']}")
    print(f"Evidence items: {len(report['evidence_items'])}")
    print(f"PII flows detected: {report['lineage_summary']['pii_flow_count']}")
