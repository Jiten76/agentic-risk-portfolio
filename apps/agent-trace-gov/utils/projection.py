"""
utils.projection — agent-trace-gov adapter: governance_report → projection.

The per-domain engine→projection adapter (port spec §14.D / §15.F). It maps the
LangGraph governance result (graph/governance_graph.py) onto the GENERIC
projection contract that portfolio_core's presentation hydrates — so the
dashboard is render-from-data, drift-proof, and shares the foundation's
presentation/log/provenance without copy-paste.

Honesty discipline (port spec §14/§15), enforced field-by-field:
  - Magnitude = "records / PII-flows exposed" (§15.B), COUNTED from pii flows.
    Record COUNT is not instrumented in the traces → marked `absent`, never 0
    or estimated. severity×occurrence is a SORT KEY only (§15.A), never rendered
    as magnitude. NO dollars, NO composite risk score.
  - first_detected = DERIVED (min real trace timestamp per RE×workflow) with
    `derived` provenance (§14.A.2) — not minted forensic history.
  - anchoring_incidents live on patterns_meta[] (RE class), NEVER on a finding
    (§14.A.3 — adjacency is the v1.4 vector).
  - finding-level framework = the coarse per-RE string the engine emits; SOC 2
    control IDs stay at the aggregate `frameworks` level (§14.A).
  - Finance blocks (exposure USD, inherent_residual) are DROPPED; absent blocks
    (defense_layers, skew, trajectory) are omitted, not stubbed (§15.F).
  - Rail = workflow; agent = secondary facet (§14.E). Lineage graph = hero.
  - Demonstrator: input is synthetic (agent_simulator); the governance logic is
    real. telemetry_status says so.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap the shared portfolio_core (no install; sibling dir) ──────────────
_PC_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "ui-system"))
if _PC_PARENT not in sys.path:
    sys.path.insert(0, _PC_PARENT)

from portfolio_core.action_log import ActionLog  # noqa: E402
from portfolio_core.provenance import (  # noqa: E402
    illustrative_provenance, provenance_for_threshold, counted_provenance,
    derived_provenance, absent_provenance, value_with_provenance, set_as_of,
)

ARTEFACT_VERSION = "v2.0-atg-alpha1"
SCHEMA_VERSION = "1.0"

# ── ATG verb vocabulary (port spec §8 / §15.H) — config-driven on the shared log
_ATG_VERBS = ("acknowledge", "escalate", "gate", "suppress",
              "override", "remediate", "certify")
_ATG_VERBS_NEEDING_EXPIRY = ("gate", "suppress")  # time-bound by nature

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"

# severity → rag + sort rank
_SEV_RAG = {"critical": "critical", "high": "critical", "medium": "watch", "low": "watch"}
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# scenario → human navigation label (WF-<hash> ids are opaque to a browsing user)
_SCENARIO_LABEL = {
    "clean": "Clean run",
    "pii_leak": "PII exposure",
    "scope_exceed": "Scope exceeded",
    "consent_gap": "Consent gap",
    "loop": "Agent loop",
    "low_conf": "Low-confidence decision",
    "payment_tool_grab": "Payments tool reached",
    "retail_comms": "Customer comms, gate skipped",
    "ledger_amend": "Ledger write, lineage broken",
}


def _now_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_schema() -> Dict[str, Any]:
    import json
    with open(_DATA_DIR / "action_schema.json") as f:
        return json.load(f)


def _detection_eval_block() -> Dict[str, Any]:
    """Compact detection-efficacy summary DERIVED from qa/detection_eval.json —
    the machine-written injection-eval record (tools/eval_detection.py). Counts
    re-shape here, never re-type; gate C23 byte-verifies the source file and
    this block's consistency with it. Fails loudly if the record is missing —
    a build without its eval is not a sealable build."""
    import json
    path = _PROJECT_ROOT.parent.parent / "qa" / "detection_eval.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    c = doc["counts"]
    names = {re["id"]: re["name"] for re in _load_schema()["risk_events"]}
    return {
        "tp": f"{c['tp_caught']}/{c['tp_total']}",
        "near_miss": f"{c['near_miss_clean']}/{c['near_miss_total']}",
        "false_fires": c["false_fires"],
        "classes_exercised": len(doc["by_class"]),
        "by_class": [
            {"cls": k, "name": names.get(k, k),
             "tp": f"{v['tp_caught']}/{v['tp']}",
             "near_miss": f"{v['nm_clean']}/{v['nm']}"}
            for k, v in sorted(doc["by_class"].items())
        ],
        "coverage_gaps": [g["cls"] for g in doc.get("coverage_gaps", [])],
        "coverage_gap_rows": [
            {"cls": g["cls"], "name": g.get("name", g["cls"]), "note": g.get("note", "")}
            for g in doc.get("coverage_gaps", [])
        ],
        "boundaries_documented": len(doc.get("boundaries_documented", [])),
        "catalog_sha12": doc["catalog_sha256"][:12],
        "injections_total": c["tp_total"] + c["near_miss_total"],
        "loop_closure": doc["loop_closure"],
        "source": "qa/detection_eval.json",
    }


# ── patterns_meta — authoritative RE taxonomy + anchors (anchors live HERE) ────
def _build_patterns_meta(schema: Dict[str, Any]) -> Dict[str, Any]:
    """RE-01..08 from action_schema.json — names, severity, framework, and the
    incident anchors. Per §14.A.3 anchors are keyed to the RE CLASS here and
    NEVER rendered inside an individual finding's impact band."""
    out = []
    for re in schema.get("risk_events", []):
        anchors = []
        for inc in (re.get("incident_reference", []) or [])[:3]:
            anchors.append({
                "name": inc.get("name", ""),
                "date": inc.get("date", ""),
                "summary": inc.get("summary", ""),
                "url": inc.get("source_url", inc.get("url", "")),
            })
        out.append({
            "id": re["id"],
            "name": re.get("name", re["id"]),
            # r56: the class value is a FLOOR, not a rating — findings carry
            # consequence-derived severity; this renders only in the precedent
            # register, labelled as the default
            "severity_default": re.get("severity_default", "medium"),
            "description": re.get("description", ""),
            "framework": re.get("framework", "—"),
            "framework_source_url": re.get("framework_source_url", ""),
            "anchors": anchors,  # class-keyed regulatory precedent register
        })
    return {
        "source_status": "published_standard",
        "source_note": (
            "Authoritative RE taxonomy + framework citations + incident anchors "
            "from data/action_schema.json. Anchors are keyed to the RE class and "
            "render only in the ATTEST/PATTERN precedent register — never inside "
            "a finding's impact band (port spec §14.A.3 / §15.C)."
        ),
        "patterns": out,
    }


# ── findings — per (workflow × RE), reconstructed from real traces ─────────────
def _build_domains_and_findings(
    traces: List[Dict[str, Any]],
    workflows: List[Dict[str, Any]],
    re_meta: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Rail = workflow. A finding = one (workflow, RE) pair, aggregated from the
    real traces that carry that RE. Honest temporal + magnitude derivation."""
    # group trace occurrences by (workflow_id, re_id)
    occ: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    wf_scenarios: Dict[str, str] = {}
    for wf in workflows:
        wf_scenarios[wf.get("workflow_id", "unknown")] = wf.get("scenario", "—")
    for t in traces:
        wid = t.get("workflow_id", "unknown")
        for re_id in (t.get("risk_events", []) or []):
            occ[(wid, re_id)].append(t)

    # build findings, grouped under their workflow domain
    domains: Dict[str, Dict[str, Any]] = {}
    # ensure every workflow appears (clean ones get a coverage row)
    for wf in workflows:
        wid = wf.get("workflow_id", "unknown")
        domains.setdefault(wid, {
            "domain_id": wid,
            "name": wid,
            "scenario": wf.get("scenario", "—"),
            "overall_rag": "evidence",
            "findings": [],
        })

    # r56: findings carry the CONSEQUENCE-derived severity stamped by the
    # classifier (worst instance in the group), its basis sentences, and — for
    # notification-class data events — the regulatory clock as an assessment.
    wf_traces: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in traces:
        wf_traces[t.get("workflow_id", "unknown")].append(t)

    for (wid, re_id), ts in sorted(occ.items()):
        meta = re_meta.get(re_id, {})
        details = [(t.get("risk_event_details") or {}).get(re_id) for t in ts]
        details = [d for d in details if d]
        sev = min((d["severity"] for d in details),
                  key=lambda s: _SEV_RANK.get(s, 9)) if details else meta.get("severity_default", "medium")
        bases = list(dict.fromkeys(d.get("severity_basis", "") for d in details if d.get("severity_basis")))
        # RE-05 de-escalation: a sub-floor decision CAUGHT by a human handoff
        # later in the same workflow is a working control, not an open high
        if re_id == "RE-05" and sev == "high":
            dec_last = max((t.get("timestamp") or "" for t in ts), default="")
            catch = next((t for t in wf_traces.get(wid, [])
                          if t.get("action_type") == "human_handoff"
                          and (t.get("timestamp") or "") > dec_last), None)
            if catch:
                sev = "medium"
                bases.append(f"routed to {catch.get('target')} after the decision — human catch in-workflow")
        rag = _SEV_RAG.get(sev, "watch")
        agents = sorted({t.get("agent_id", "—") for t in ts})
        targets = sorted({t.get("target", "—") for t in ts})
        # honest temporal: derive from real trace timestamps
        stamps = [t.get("timestamp") for t in ts if t.get("timestamp")]
        first_detected = min(stamps) if stamps else None
        last_seen = max(stamps) if stamps else None
        # counted PII exposure for this finding
        pii_traces = [t for t in ts if t.get("pii_detected")]
        data_classes = sorted({
            dc for t in ts
            for dc in (list((t.get("pii_detected") or {}).keys())
                       + [((t.get("data_lineage") or {}).get("data_classification"))])
            if dc
        })
        # real signal is the trace's consent_verified flag (False iff RE-02 fires);
        # the old governance_flag substring matched a field the simulator never emits.
        consent_missing = any(t.get("consent_verified") is False for t in ts)

        finding = {
            "finding_id": f"{re_id}-{wid}",
            "risk_event_id": re_id,
            "name": meta.get("name", re_id),
            "severity": sev,
            # r56: the rating defends itself — consequence basis from the trace's
            # own fields (gate C22 asserts every token exists in the traces), and
            # the notification clock as an ASSESSMENT where the data event runs one
            "severity_basis": " · ".join(bases) if bases else None,
            "severity_default": meta.get("severity_default", "medium"),
            "notification_clock": (
                {"citation": "GDPR Art. 33(1) — 72h from awareness",
                 "window": "72h", "status": "assessment",
                 "note": "candidate personal-data breach (Art. 4(12)); the materiality "
                         "DETERMINATION is reserved to Legal/Compliance"}
                if (re_id == "RE-03" and sev == "high" and pii_traces
                    and any("external" in (t.get("target") or "").lower()
                            or t.get("action_type") == "external_api_call" for t in ts))
                else None),
            "overall_rag": rag,
            "_sort_rank": _SEV_RANK.get(sev, 9),  # severity×occurrence sort key (§15.A) — not rendered
            "occurrence_count": len(ts),
            "workflow_id": wid,
            "agent_id": agents[0] if agents else None,   # secondary facet
            "affected_agents": agents,
            "affected_targets": targets,
            # honest temporal — DERIVED, labelled as such
            "first_detected": value_with_provenance(
                first_detected,
                derived_provenance(computation="min(trace.timestamp) over this RE×workflow's simulated traces")
                if first_detected else absent_provenance("no trace timestamp for this occurrence")),
            # last_seen — same derivation as first_detected (max vs min); wrapped
            # identically so it can't read as un-lineaged minted history.
            "last_seen": value_with_provenance(
                last_seen,
                derived_provenance(computation="max(trace.timestamp) over this RE×workflow's simulated traces")
                if last_seen else absent_provenance("no trace timestamp for this occurrence")),
            # MAGNITUDE (§15.B): records-exposed — flows + data-classes COUNTED
            # from real traces (real_query_synthesized_data, NOT illustrative —
            # a count of real traces is real counting); record COUNT absent
            # (not instrumented). NEVER a dollar / composite.
            "records_exposed": {
                "pii_flow_count": value_with_provenance(
                    len(pii_traces),
                    counted_provenance(source_system="agent_simulator",
                                       source_query="count(traces where pii_detected)",
                                       computation="counted PII flows in this RE×workflow")),
                "data_classes": data_classes,
                "record_count": value_with_provenance(
                    None, absent_provenance("trace does not carry an affected-record count; not instrumented")),
            },
            "consent_missing": consent_missing,
            # finding-level framework = coarse per-RE string (§14.A) — SOC2 IDs stay aggregate
            "framework": meta.get("framework", "—"),
            "framework_source_url": meta.get("framework_source_url", ""),
            "treatment": value_with_provenance(
                None, absent_provenance("populated at Stage 4 from real attestation entries")),
        }
        d = domains[wid]
        d["findings"].append(finding)
        # roll workflow rag up to worst finding
        if rag == "critical":
            d["overall_rag"] = "critical"
        elif rag == "watch" and d["overall_rag"] != "critical":
            d["overall_rag"] = "watch"

    # sort findings within each domain by severity then occurrence
    for d in domains.values():
        d["findings"].sort(key=lambda f: (f["_sort_rank"], -f["occurrence_count"]))

    # human-readable navigation labels — a WF-<hash> id is opaque; the scenario
    # is the meaning ("PII exposure", "Scope exceeded"…). Number per scenario to
    # disambiguate; keep the id as a secondary technical ref.
    _counters: Dict[str, int] = {}
    for wid, d in domains.items():
        base = _SCENARIO_LABEL.get(d.get("scenario", ""), (d.get("scenario") or "Workflow").replace("_", " ").title())
        _counters[base] = _counters.get(base, 0) + 1
        d["label"] = f"{base} {_counters[base]}"
    return domains


# ── lineage graph — the hero (§14.E / §15.G) ───────────────────────────────────
def _build_lineage_graph(lineage_map: Dict[str, Any]) -> Dict[str, Any]:
    nodes = []
    for n in lineage_map.get("nodes", []):
        nid = n.get("id")
        # normalize: an `agent-*` id is an AGENT even when the engine typed it
        # 'system' — else 5 of 6 agents render in the wrong graph column.
        ntype = "agent" if str(nid or "").startswith("agent-") else n.get("type", "node")
        nodes.append({
            "id": nid, "type": ntype,
            "pii_touched": bool(n.get("pii_touched")),
        })
    edges = []
    for e in lineage_map.get("edges", []):
        to = (e.get("to") or "").lower()
        is_external = "external" in to
        edges.append({
            "from": e.get("from"), "to": e.get("to"),
            "action": e.get("action"),
            "pii": bool(e.get("pii")),
            "external": is_external,
            "risk_events": e.get("risk_events", []),
            "workflow_id": e.get("workflow_id"),
            # r56: the edge colors from the WORST consequence-derived severity of
            # the events riding it — not from a category assumption about egress
            "severity": e.get("severity"),
            "rag": _SEV_RAG.get(e.get("severity"), "watch") if e.get("risk_events") else
                   ("watch" if e.get("pii") else "evidence"),
        })
    # detect multi-agent loops (RE-08) — a back-edge / cycle among agents
    loop_edges = [e for e in edges if "RE-08" in (e.get("risk_events") or [])]
    # DISTINCT (from→to) flows — the count the deduped hero graph actually paints.
    # The raw edge total (one logical flow repeated across workflows) is exposed
    # separately as 'traversals', so the magnitude headline matches the arrows on
    # screen and never inflates 4 distinct flows into 13 (adversarial-review fix).
    distinct: Dict[tuple, Dict[str, bool]] = {}
    for e in edges:
        d = distinct.setdefault((e["from"], e["to"]), {"pii": False, "external": False})
        d["pii"] = d["pii"] or e["pii"]
        d["external"] = d["external"] or e["external"]
    pii_distinct = sum(1 for d in distinct.values() if d["pii"])
    ext_distinct = sum(1 for d in distinct.values() if d["external"])
    return {
        "source_status": "real_query_synthesized_data",
        "source_note": (
            "Structural data-flow (agent→system→external) counted from SIMULATED "
            "agent traces — NOT a probabilistic cascade. RE-03 external-flow edges "
            "are lit critical; RE-08 multi-agent loops marked as cycles (port spec "
            "§15.G). Counts are DISTINCT (from→to) flows — matching the painted "
            "graph; raw traversals (same flow across workflows) are exposed "
            "separately. First-paint hero."
        ),
        "nodes": nodes,
        "edges": edges,
        # headline = DISTINCT flows (matches the graph); traversals = raw edges
        "external_flow_count": ext_distinct,
        "pii_flow_count": pii_distinct,
        "external_flow_traversals": sum(1 for e in edges if e["external"]),
        "pii_flow_traversals": sum(1 for e in edges if e["pii"]),
        "distinct_flow_count": len(distinct),
        "loop_edges": loop_edges,
    }


# ── portfolio magnitude (records-exposed roll-up — §15.B) ──────────────────────
def _build_magnitude(domains: Dict[str, Any], lineage: Dict[str, Any]) -> Dict[str, Any]:
    total_pii_flows = lineage.get("pii_flow_count", 0)        # DISTINCT
    total_external = lineage.get("external_flow_count", 0)    # DISTINCT
    pii_traversals = lineage.get("pii_flow_traversals", 0)    # raw edges
    ext_traversals = lineage.get("external_flow_traversals", 0)
    data_classes = sorted({
        dc for d in domains.values() for f in d["findings"]
        for dc in f["records_exposed"]["data_classes"]
    })
    return {
        "source_status": "real_query_synthesized_data",
        "source_note": (
            "Magnitude axis = DISTINCT PII-bearing / external flows in the lineage "
            "(port spec §15.B) — a lineage signal, NOT the GDPR Art. 33(1)(a) "
            "'records / data-subjects' quantity, which is itself not instrumented "
            "and rendered absent below. Flows + data classes are COUNTED (distinct "
            "from→to, matching the graph); raw traversals are a secondary line. No "
            "dollar figure, no composite score. Lives in IMPACT — never on the same "
            "row as a regulatory precedent anchor (§15.C)."
        ),
        # §15.K — provenance ON the magnitude number itself (the figure an exec
        # quotes out of context), not just a prose source_note on the block.
        "pii_flows_exposed": value_with_provenance(
            total_pii_flows,
            counted_provenance(source_system="agent_simulator",
                               source_query="count(distinct (from,to) lineage edges where pii)",
                               computation="counted DISTINCT PII-bearing flows (matches the graph)")),
        "external_flows": value_with_provenance(
            total_external,
            counted_provenance(source_system="agent_simulator",
                               source_query="count(distinct (from,to) lineage edges where external)",
                               computation="counted DISTINCT external-destination flows")),
        # secondary: raw traversals (same logical flow repeated across workflows)
        "pii_flow_traversals": value_with_provenance(
            pii_traversals,
            counted_provenance(source_system="agent_simulator",
                               source_query="count(lineage edges where pii)",
                               computation="raw PII flow traversals across all workflows")),
        "external_flow_traversals": value_with_provenance(
            ext_traversals,
            counted_provenance(source_system="agent_simulator",
                               source_query="count(lineage edges where external)",
                               computation="raw external flow traversals across all workflows")),
        "data_classes": data_classes,
        "record_count": value_with_provenance(
            None, absent_provenance("affected-record / data-subject count not instrumented in traces")),
    }


# ── materiality — framework findings (KEEP, re-sourced; §15.F) ─────────────────
def _build_agent_dependency_layer(
    traces: List[Dict[str, Any]],
    lineage: Dict[str, Any],
    domains: Dict[str, Any],
    re_meta: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """The agent estate's shared-dependency layer (external finding, Claude
    round-28: 'the agent spoke has no common-mode dependency concept — and its
    own lineage graph screams for one'). The structural twin of rac's E1 layer,
    in atg-native units: NO dollars — workflows, traced actions and finding
    classes. Every blast radius DERIVES from the same traces/lineage the
    dashboard renders; the catalog only declares what each node underlies."""
    import json as _json
    from pathlib import Path as _Path
    cat_path = _Path(__file__).resolve().parent.parent / "data" / "agent_dependency_catalog.json"
    cat = _json.loads(cat_path.read_text(encoding="utf-8"))

    all_wf = sorted({t.get("workflow_id") for t in traces if t.get("workflow_id")})
    total_wf = len(all_wf)
    wf_by_action: Dict[str, set] = defaultdict(set)
    for t in traces:
        wf_by_action[t.get("action_type", "")].add(t.get("workflow_id"))
    wf_by_lineage_node: Dict[str, set] = defaultdict(set)
    for e in lineage.get("edges", []):
        for nid in (e.get("from"), e.get("to")):
            if nid:
                wf_by_lineage_node[nid].add(e.get("workflow_id"))

    findings_by_re: Dict[str, int] = defaultdict(int)
    for d in domains.values():
        for f in d["findings"]:
            findings_by_re[f["risk_event_id"]] += 1
    findings_total = sum(findings_by_re.values())

    nodes_out = []
    for nd in cat.get("nodes", []):
        if nd.get("lineage_node"):
            wfs = wf_by_lineage_node.get(nd["lineage_node"], set())
            basis = f"derived from lineage edges of node '{nd['lineage_node']}'"
        elif nd.get("governs_all_traces"):
            wfs = set(all_wf)
            basis = "governs every traced action by construction (the detection plane)"
        else:
            wfs = set()
            for a in nd.get("depends_on_actions", []):
                wfs |= wf_by_action.get(a, set())
            basis = "derived from traces with action_type in " + str(nd.get("depends_on_actions", []))
        blind = (nd.get("modes", {}).get("blindness", {}) or {})
        fan_re = blind.get("fan_out_re", []) or []
        at_stake = sum(findings_by_re.get(r, 0) for r in fan_re)
        nodes_out.append({
            "id": nd["id"], "name": nd["name"], "layer": nd["layer"],
            "rac_analog": nd.get("rac_analog"),
            "containment_boundary": nd.get("containment_boundary"),
            "workflows_affected": len(wfs),
            "workflows_total": total_wf,
            "blast_basis": basis,
            "blindness_re": fan_re,
            "blindness_re_names": [re_meta.get(r, {}).get("name", r) for r in fan_re],
            "findings_at_stake": at_stake,
            "loss_effect": (nd.get("modes", {}).get("loss", {}) or {}).get("effect", ""),
            "blindness_effect": blind.get("effect", ""),
            "anchors": nd.get("anchors", []),
            "mitigation_note": nd.get("mitigation_note", ""),
        })
    nodes_out.sort(key=lambda n: (-n["workflows_affected"], -n["findings_at_stake"]))
    top = nodes_out[0] if nodes_out else {}
    return {
        "source_status": "operator_calibrated",
        "units_note": cat.get("units_note", ""),
        "provenance_note": cat.get("provenance_note", ""),
        "cross_substrate_note": cat.get("cross_substrate_note", ""),
        "nodes": nodes_out,
        "workflows_total": total_wf,
        "findings_total": findings_total,
        "deferred_nodes": cat.get("deferred_nodes", {}),
        "one_thing": (
            f"One agent-layer dependency — the {top.get('name', 'orchestrator')} — transits "
            f"{top.get('workflows_affected', 0)} of {total_wf} workflows: the estate has a control "
            "plane, and this layer puts it on the register. Its blindness mode is the sharper edge: "
            "the classifier plane going dark unmasks every finding class at once while the "
            "dashboard reads green."
        ),
    }


def _build_materiality(report: Dict[str, Any], re_meta: Dict[str, Dict[str, Any]],
                       firing_res: set) -> Dict[str, Any]:
    """Which regulatory obligations the firing risk-events TRIGGER — grouped by
    jurisdiction (EU / US / cross-cutting) so a US reader sees US coverage, not an
    EU-only list. Article-level facts only; every US obligation is conditioned on
    the firm actually being a regulated entity (bank / broker-dealer / FINRA
    member), because this demonstrator does not establish that predicate."""
    triggers = {
        # ── EU ──
        # Art. 33 is a BREACH-notification clock (breach = Art. 4(12)). Only an
        # actual unauthorized external flow (RE-03) is a candidate breach; PII
        # merely detected in a governed internal output (RE-01) is NOT per se a
        # breach, so it must not trigger the 72h clock (adversarial-review fix).
        "gdpr_art_33_34": {
            "jurisdiction": "EU", "regulation_citation": "GDPR Reg. 2016/679 Art. 33(1)–34 — 72h breach notification",
            "triggered_by": ["RE-03"],
            "note": "Unauthorized external flow is a candidate personal-data breach (Art. 4(12)) → 72h notification ASSESSMENT (not a determination).",
        },
        "gdpr_art_5_32": {
            "jurisdiction": "EU", "regulation_citation": "GDPR Art. 5 (principles) / Art. 32 (security of processing)",
            "triggered_by": ["RE-01"],
            "note": "PII detected in agent output → data-minimisation + security-of-processing considerations (not a breach notification).",
        },
        "gdpr_art_6_consent": {
            "jurisdiction": "EU", "regulation_citation": "GDPR Art. 6(1)(a) (consent) / Art. 5(1)(e) (storage limitation)",
            "triggered_by": ["RE-02", "RE-07"],
            "note": "Consent record missing (no Art. 6(1)(a) basis) / excessive retention.",
        },
        # EU AI Act Art. 14/12/26 bind only for HIGH-RISK systems (Art. 6 / Annex
        # III). This artefact does not establish the high-risk predicate, so these
        # are surfaced as CONDITIONALLY applicable.
        "eu_ai_act_art_14_12": {
            "jurisdiction": "EU", "regulation_citation": "EU AI Act Reg. 2024/1689 Art. 14 (human oversight) + Art. 12 (logging) — IF high-risk (Annex III)",
            "triggered_by": ["RE-04", "RE-05"],
            "note": "Agent scope exceeded / low-confidence automated decision → oversight + logging duties APPLY ONLY IF the system is classified high-risk under Annex III (predicate not established here).",
        },
        "eu_ai_act_art_26_gdpr_chV": {
            "jurisdiction": "EU", "regulation_citation": "EU AI Act Art. 26 (deployer, IF high-risk) + GDPR Ch. V Art. 44–49 (transfer basis)",
            "triggered_by": ["RE-03"],
            "note": "Unauthorized external flow = cross-border transfer needing a Ch. V basis; Art. 26 deployer duties apply only if high-risk (Annex III).",
        },
        # ── US ── (the reader's home regulators; each conditioned on entity type)
        "glba_safeguards": {
            "jurisdiction": "US", "regulation_citation": "GLBA Safeguards Rule — 16 CFR §314.4 (access controls, monitoring, disposal) — IF a US financial institution",
            "triggered_by": ["RE-01", "RE-03", "RE-07"],
            "note": "PII in output / unauthorized egress / over-retention engage the Safeguards Rule's access-control, monitoring and disposal duties for covered financial institutions.",
        },
        "sec_reg_sp": {
            "jurisdiction": "US", "regulation_citation": "SEC Regulation S-P — 17 CFR §248.30 safeguards + 2024 incident-response amendment (≈30-day customer notice) — IF broker-dealer / RIA / transfer agent",
            "triggered_by": ["RE-03"],
            "note": "Unauthorized external flow of customer information is the trigger for the Reg S-P safeguards + the 2024 breach-notification amendment — IF the firm is a covered SEC registrant.",
        },
        "sr_11_7_model_risk": {
            "jurisdiction": "US", "regulation_citation": "Fed SR 11-7 / OCC 2011-12 — Model Risk Management (validation, monitoring, effective challenge) — IF a supervised bank",
            "triggered_by": ["RE-04", "RE-05", "RE-06"],
            "note": "Scope-exceeded / low-confidence automated decisions and broken data lineage are model-risk events: they engage validation, ongoing monitoring and effective-challenge duties for supervised institutions.",
        },
        "finra_ai_supervision": {
            "jurisdiction": "US", "regulation_citation": "FINRA Reg. Notice 24-09 (AI) + Rule 3110 (supervision) — IF a FINRA member firm",
            "triggered_by": ["RE-04", "RE-05", "RE-08"],
            "note": "Agent overreach / low-confidence decisions / uncontrolled multi-agent loops engage a member firm's supervisory-system obligations over AI tools.",
        },
        # r56 — the conduct/finance shapes the seeded estate now exercises
        "finra_2210": {
            "jurisdiction": "US", "regulation_citation": "FINRA Rule 2210 (communications with the public) + Reg. Notice 24-09 — IF a FINRA member firm",
            "triggered_by": ["RE-04"],
            "note": "An agent sending customer communications outside its authorization, with the human gate skipped, is a principal-approval gap in 2210 terms — surfaced as fact; the supervisory determination stays with Compliance.",
        },
        "sea_17a4": {
            "jurisdiction": "US", "regulation_citation": "SEA Rule 17a-4 (17 CFR 240.17a-4) · books & records preservation",
            "triggered_by": ["RE-06"],
            "note": "A record-store write with broken lineage threatens the preservation obligation's completeness/integrity premise — IF broker-dealer; same regime and citation the rac register carries, so the cross-substrate loop closes.",
        },
        # ── cross-cutting standards (not jurisdiction-bound) ──
        "nist_ai_rmf": {
            "jurisdiction": "Cross-cutting", "regulation_citation": "NIST AI RMF 1.0 — GOVERN / MAP / MEASURE / MANAGE (voluntary consensus framework)",
            "triggered_by": ["RE-04", "RE-05", "RE-08"],
            "note": "Autonomy/confidence/loop events map to the MEASURE + MANAGE functions; adopting the RMF is voluntary, so this is a maturity signal, not a legal duty.",
        },
        "soc2_cc6": {
            "jurisdiction": "Cross-cutting", "regulation_citation": "SOC 2 Type II — CC6.1 / CC6.6 (logical access, boundary protection)",
            "triggered_by": ["RE-03", "RE-04", "RE-06"],
            "note": "Access / boundary / lineage-integrity criteria.",
        },
    }
    out = {}
    for key, t in triggers.items():
        fired = bool(set(t["triggered_by"]) & firing_res)
        out[key] = {
            "status": "TRIGGERED" if fired else "clear",
            "jurisdiction": t["jurisdiction"],
            "regulation_citation": t["regulation_citation"],
            "triggered_patterns": [r for r in t["triggered_by"] if r in firing_res],
            "provenance": {
                "computation": t["note"]
                + " Materiality DETERMINATION is reserved to Legal/Compliance; this surfaces facts only.",
                "assumptions": [],
            },
        }
    return out


# ── action log (shared core, ATG verbs — §15.H) ────────────────────────────────
# Own INSTANCE (adversarial-review fix): never touches portfolio_core's default
# instance, so risk-as-code-agent (which configures the default) and this project
# cannot stomp each other's verb set / log path even in one process.
_ATG_LOG = ActionLog(
    log_file=_DATA_DIR / "attestation_log.jsonl",
    project_root=_PROJECT_ROOT,
    verbs=_ATG_VERBS,
    verbs_needing_expiry=_ATG_VERBS_NEEDING_EXPIRY,
    justification_min_words=12,
)


def make_projection(result: Dict[str, Any], *, as_of: Optional[str] = None,
                    run_seed: Optional[int] = None) -> Dict[str, Any]:
    """The ATG adapter. Input: the full LangGraph result
    (run_governance_analysis_full). Output: the generic projection contract.

    When ``as_of`` is given, every provenance stamp + generated_at + period uses
    that single fixed time (instead of N independent now() calls), so the
    projection — and the SHA-256 seal computed over it — is byte-reproducible from
    a stated (n, seed). ``run_seed`` is recorded in meta for re-derivation."""
    set_as_of(as_of)  # None → wall-clock now() (default, non-reproducible)
    try:
        return _make_projection(result, as_of=as_of, run_seed=run_seed)
    finally:
        set_as_of(None)  # never leak the fixed clock to a later caller


def _make_projection(result: Dict[str, Any], *, as_of: Optional[str],
                     run_seed: Optional[int]) -> Dict[str, Any]:
    schema = _load_schema()
    re_meta = {re["id"]: re for re in schema.get("risk_events", [])}

    report = result.get("governance_report", {}) or {}
    traces = result.get("cleaned_traces", []) or []
    workflows = result.get("workflows", []) or []
    lineage_map = result.get("lineage_map", {}) or {}

    domains = _build_domains_and_findings(traces, workflows, re_meta)
    lineage = _build_lineage_graph(lineage_map)
    firing_res = {f["risk_event_id"] for d in domains.values() for f in d["findings"]}

    # counts
    sev_counts = defaultdict(int)
    findings_total = 0
    for d in domains.values():
        for f in d["findings"]:
            sev_counts[f["severity"]] += 1
            findings_total += 1

    patterns_meta = _build_patterns_meta(schema)
    magnitude = _build_magnitude(domains, lineage)
    materiality = _build_materiality(report, re_meta, firing_res)
    agent_deps = _build_agent_dependency_layer(traces, lineage, domains, re_meta)

    _gen_at = as_of if as_of else _now_z()
    _period = (as_of[:7] if as_of else datetime.now(timezone.utc).strftime("%Y-%m"))
    projection: Dict[str, Any] = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "artefact_version": ARTEFACT_VERSION,
            "period": _period,
            "generated_at": _gen_at,
            "run_seed": run_seed,                        # reproduce via (n, run_seed)
            "domain_ids": list(domains.keys()),          # the workflow rail
            "domain_object": "workflow",                 # §14.E
            "counts": {
                "findings_total": findings_total,
                "risk_events_total": report.get("risk_events_total", findings_total),
                "critical": sev_counts.get("critical", 0),
                "high": sev_counts.get("high", 0),
                "medium": sev_counts.get("medium", 0),
                "low": sev_counts.get("low", 0),
                "workflows_analyzed": report.get("workflows_analyzed", len(workflows)),
                "actions_traced": report.get("total_actions", len(traces)),
                "pii_flows": lineage.get("pii_flow_count", 0),           # DISTINCT
                "external_flows": lineage.get("external_flow_count", 0), # DISTINCT
            },
            # provenance tier per count, so the SIGNAL hero badges its (loud,
            # first-paint) numbers with the SAME discipline as the magnitude block
            # — the renderer READS this, it does not assert provenance itself.
            # r57 (round-38 reviewer): two vocabularies ride each finding —
            # `severity` is THE RATING (consequence-derived, with basis);
            # `overall_rag` is only the 3-tier display accent (critical|watch|
            # evidence) that colors rows. Documented so a data-reader cannot
            # mistake the accent for a second rating scale.
            "rag_note": ("overall_rag is a 3-tier display accent (critical|watch|evidence) "
                         "derived from severity for row coloring; the rating is `severity`, "
                         "consequence-derived with its basis in `severity_basis`"),
            "counts_provenance": {
                "findings_total": "real_query_synthesized_data",
                "risk_events_total": "real_query_synthesized_data",
                "critical": "derived", "high": "derived",
                "medium": "derived", "low": "derived",
                "workflows_analyzed": "real_query_synthesized_data",
                "actions_traced": "real_query_synthesized_data",
                "pii_flows": "real_query_synthesized_data",
                "external_flows": "real_query_synthesized_data",
            },
            # two denominators sit adjacent — name them so a reader who checks
            # "do the severities sum to the total?" knows which total (they sum to
            # findings_total, not risk_events_total).
            "counts_gloss": (
                "findings_total = grouped (workflow×risk-event) findings; the "
                "severity tiers (critical+high+medium+low) sum to THIS. "
                "risk_events_total = raw risk-event occurrences before grouping."
            ),
            "overall_posture": report.get("overall_posture", "clean"),
            # r68 · detection-efficacy eval — the circularity answer. The block
            # DERIVES from qa/detection_eval.json (machine-written by
            # tools/eval_detection.py, byte-verified by gate C23); nothing here
            # is typed. The loop closes through a human (A8), never by
            # self-tuning — a governor that tunes on what it measures marks its
            # own homework.
            "detection_eval": _detection_eval_block(),
        },
        "domains": domains,
        "patterns_meta": patterns_meta,
        "lineage_graph": lineage,                        # the hero (§14.E)
        "agent_dependency_layer": agent_deps,            # the estate's common-cause nodes
        "magnitude": magnitude,                          # records-exposed (§15.B)
        "materiality": materiality,                      # framework findings
        "frameworks": {                                  # aggregate SOC 2 evidence
            "source_status": "real_query_synthesized_data",
            "soc2_evidence": report.get("soc2_evidence", {}),
            "alignment": report.get("framework_alignment", []),
        },
        "action_log": _ATG_LOG.action_log_summary(),
        "telemetry_status": "synthesised",               # demonstrator, honest
        "source_note": (
            "Input is agent_simulator (synthetic agent traces, scenario-mixed — "
            "port spec §14.G); the governance logic is real. Reproducible under a "
            "run seed (meta.run_seed). Counted values carry "
            "real_query_synthesized_data; derived/absent fields are marked as such."
        ),
        # DROPPED (port spec §15.F): exposure (USD), inherent_residual.
        # ABSENT (omitted, not stubbed): defense_layers, skew, trajectory, actuals.
    }
    # ── IA (platform grammar, spec v2.2): spine + role paths + headlines,
    # all derived from THIS projection — the map cannot say what the page doesn't.
    projection["ia"] = _build_ia(projection)

    return projection


def _build_ia(p: Dict[str, Any]) -> Dict[str, Any]:
    """atg keeps its own act vocabulary; the beat model is a sequencing overlay
    (spec §2). Nodes single-home the five sections; headlines are computed
    findings citing their own panel's numbers (§8 genre, gated on rac by C27.3
    — the same discipline applies here)."""
    def num(x):
        try:
            return len(x)
        except TypeError:
            return x or 0

    meta = p.get("meta", {})
    c = meta.get("counts", {})
    lg = p.get("lineage_graph", {})
    re_counts: Dict[str, int] = {}
    re_names: Dict[str, str] = {}
    for d in (p.get("domains") or {}).values():
        for f in d.get("findings", []):
            fid = f.get("finding_id") or ""
            for k in ("RE-01", "RE-02", "RE-03", "RE-04", "RE-05", "RE-06", "RE-07", "RE-08"):
                if k in fid:
                    re_counts[k] = re_counts.get(k, 0) + 1
                    re_names.setdefault(k, f.get("name") or k)
    al = p.get("action_log", {})
    n_chain = al.get("total_entries") or num(al.get("recent_entries"))

    acts = [
        {"id": "signal",  "name": "Signal",  "desc": "governance pass · which risk events fired"},
        {"id": "pattern", "name": "Propagate", "desc": "observed data-flow · agent → system → external"},
        {"id": "impact",  "name": "Impact",  "desc": "which regulatory obligations the findings trigger"},
        {"id": "decide",  "name": "Decide",  "desc": "governance verbs · named human + justification"},
        {"id": "attest",  "name": "Attest",  "desc": "hash-chained log · precedent register"},
    ]
    nodes = [
        {"id": "trail", "beat": "BELIEVE", "act": "signal", "label": "what fired",
         "headline": f"{c.get('findings_total', 0)} findings from {c.get('actions_traced', 0)} traced actions across "
                     f"{c.get('workflows_analyzed', 0)} workflows — {c.get('critical', 0)} critical, each row reconstructed from the trace stream.",
         "targets": ["signal-hero", "signal-queue"]},
        {"id": "lineage", "beat": "BELIEVE", "act": "pattern", "label": "how risk moves",
         "headline": f"{num(lg.get('nodes'))} nodes and {num(lg.get('edges'))} edges of counted lineage — "
                     f"{num(lg.get('external_flow_count'))} external flows lit critical, {num(lg.get('pii_flow_count'))} PII, {num(lg.get('loop_edges'))} loops.",
         "targets": ["lineage-hero", "pattern-primer"]},
        {"id": "exposure", "beat": "STAKE", "act": "impact", "label": "what it triggers",
         "headline": f"{c.get('critical', 0)} critical + {c.get('high', 0)} high findings mapped to US, EU and cross-cutting obligations — "
                     "article-level facts; the determination stays with Legal/Compliance.",
         "targets": ["impact-magnitude", "impact-materiality"]},
        {"id": "verbs", "beat": "ACT", "act": "decide", "label": "act on it",
         "headline": f"Every verb needs a named human + 12-word justification, hash-chained — {c.get('findings_total', 0)} findings await disposition.",
         "targets": ["decide-verbs", "decide-queue"]},
        {"id": "attest", "beat": "ATTACK", "act": "attest", "label": "prove it",
         "headline": f"{n_chain} chained attestations, SHA-256 verified live in your browser — plus the enforcement-precedent register per RE class.",
         "targets": ["attest-chain", "attest-log", "attest-precedent"]},
    ]
    headlines = {
        "signal-hero": f"{c.get('risk_events_total', 0)} risk events scored this pass — the hero counts them from traces, not opinion.",
        "signal-queue": f"{c.get('findings_total', 0)} workflow×risk-event findings — {c.get('critical', 0)} critical · {c.get('high', 0)} high; click lineage for the evidence trail.",
        "lineage-hero": f"{num(lg.get('distinct_flow_count'))} distinct flows counted from traces — {num(lg.get('external_flow_count'))} unauthorized external (RE-03) lit, {num(lg.get('loop_edges'))} multi-agent loops dashed.",
        "pattern-primer": f"8 risk-event classes with framework citations — {re_counts.get('RE-03', 0)}× {re_names.get('RE-03', 'RE-03')} and {re_counts.get('RE-04', 0)}× {re_names.get('RE-04', 'RE-04')} are the structural catches.",
        "impact-magnitude": f"{num(lg.get('external_flow_traversals'))} external and {num(lg.get('pii_flow_traversals'))} PII traversals — the magnitude counts what actually crossed, not what might.",
        "impact-materiality": "Obligations grouped by jurisdiction, article-level only — flags, not determinations.",
        "decide-verbs": "Four verbs, A8-gated in the browser: named human, 12-word justification, expiry.",
        "agent-dependencies": (
            f"{len((p.get('agent_dependency_layer') or {}).get('nodes', []))} common-cause nodes of the agent "
            f"estate — the orchestrator transits {max([n.get('workflows_affected', 0) for n in (p.get('agent_dependency_layer') or {}).get('nodes', [])] or [0])} "
            f"of {c.get('workflows_analyzed', 0)} workflows; classifier blindness unmasks every finding class at once."
        ),
        "decide-queue": f"{c.get('findings_total', 0)} findings ranked for disposition — the queue is the docket.",
        "attest-chain": "Edit any entry and the chain breaks visibly — the SHA-256 math re-runs on every load.",
        "attest-log": f"{n_chain} attestations on the chain — actor, justification, expiry, thresholds at decision time.",
        "attest-precedent": "Real enforcement precedent per RE class — deliberately separated from any single finding.",
    }
    paths = {
        "basic":       ["trail", "lineage", "exposure", "verbs", "attest"],
        "leadership":  ["exposure", "verbs", "trail", "attest", "lineage"],
        "engineering": ["trail", "lineage", "verbs", "exposure", "attest"],
        "audit":       ["attest", "lineage", "trail", "exposure", "verbs"],
    }
    return {
        "thesis": ("Agents doing governance work leave verifiable evidence trails — "
                   "and the trail is what catches the agent that exceeded its scope."),
        "acts": acts,
        "nodes": nodes,
        "paths": paths,
        "headlines": headlines,
        "default_role": "basic",
        "source_note": "Spine, role paths and every headline derive from this projection.",
    }
