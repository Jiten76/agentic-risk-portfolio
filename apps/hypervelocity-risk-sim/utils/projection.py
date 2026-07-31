"""
utils.projection — hypervelocity-risk-sim adapter: simulation → projection.

The per-domain engine→projection adapter (the third spoke). It runs the seeded
scenario simulator (simulator/event_generator.py) and maps its output onto the
GENERIC projection contract that portfolio_core's presentation hydrates — so the
dashboard is render-from-data, drift-proof, and shares the foundation's
presentation/log/provenance without copy-paste (same pattern as risk-as-code-agent
and agent-trace-gov).

Honesty discipline (mirrors the other two spokes, enforced field-by-field):
  - The spreadsheet-vs-signal RESPONSE-TIME GAP is operator_calibrated ILLUSTRATION
    — wrapped `illustrative` provenance, never presented as measured telemetry.
  - The scenario PEAKS + counts (peak lag, SLO violations, blocked txns, event
    counts) are COUNTED over the seeded event stream → `real_query_synthesized_data`.
  - Rail = scenario. Each scenario carries its HV risk-event (HV-01..03) and the
    canonical KRIs it maps to, read from the hub crosswalk (packages/kri-taxonomy)
    — the platform's one vocabulary, not a private re-labelling.
  - Reproducible: a fixed (seed, as_of) makes the projection — and the SHA-256 seal
    over it — byte-stable. The seed pins both the sim RNG and its event clock.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap: shared portfolio_core (packages/ui-system) + this spoke root ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent            # apps/hypervelocity-risk-sim
_REPO_ROOT = _PROJECT_ROOT.parent.parent                          # monorepo root
_PC_PARENT = str(_REPO_ROOT / "packages" / "ui-system")
for _p in (str(_PROJECT_ROOT), _PC_PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from portfolio_core.action_log import ActionLog  # noqa: E402
from portfolio_core.provenance import (  # noqa: E402
    illustrative_provenance, counted_provenance, derived_provenance,
    value_with_provenance, set_as_of,
)
from simulator.event_generator import run_scenario, compare_response_strategies  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

ARTEFACT_VERSION = "v2.0-hv-alpha1"
SCHEMA_VERSION = "1.0"

_DATA_DIR = _PROJECT_ROOT / "data"
_KRI_DIR = _REPO_ROOT / "packages" / "kri-taxonomy"

# Fixed order = the rail order. Each scenario is one row.
_SCENARIOS = ["kafka_lag_storm", "deployment_cascade", "velocity_surge", "identity_outage"]

# hv-sim uses "risk_as_code" as the signal-based regime key. Label the regimes
# HONESTLY: the gap is manual response vs instrumented+automated response — the
# comparison must NOT smuggle tooling latency into a pure "governance" claim.
_REGIME_LABEL = {"traditional": "Manual / checklist response",
                 "risk_as_code": "Instrumented + automated response"}

# metrics that are DERIVED from a real count (not pure illustration) — they carry
# a `derived` tag, not `illustrative`, because a real count is upstream of them.
_DERIVED_METRICS = {"missed_events"}

# hypervelocity attestation log — seeded with a short ILLUSTRATIVE chain (see
# tools/seed_attestations.py) so the chain DEMONSTRATES the capability (named human +
# expiry + ≥12-word justification + hash chain), not a vacuous empty "intact 0/0" pass.
# Its own instance, so it never touches the other spokes' logs / verb sets.
_HV_LOG = ActionLog(
    log_file=_DATA_DIR / "attestation_log.jsonl",
    project_root=_PROJECT_ROOT,
    verbs=("acknowledge", "escalate", "mitigate", "rollback", "certify"),
    verbs_needing_expiry=("escalate", "mitigate"),
    justification_min_words=12,
)


# ── hub taxonomy: HV risk-event → canonical KRIs (the platform vocabulary) ─────
def _load_kri_mapping() -> Dict[str, Any]:
    """Read the spoke taxonomy + hub crosswalk + catalog once. Returns
    {scenario: {"hv_id","hv_name","frameworks","kris":[{id,name,role}]}}."""
    catalog = yaml.safe_load((_KRI_DIR / "kri-catalog.yaml").read_text())
    kri_name = {kri["id"]: kri["name"]
                for fam in catalog["families"].values() for kri in fam["kris"]}
    crosswalk = yaml.safe_load((_KRI_DIR / "crosswalk.yaml").read_text())
    hv_map = {m["from"]: m for m in crosswalk["spokes"]["hypervelocity-risk-sim"]["map"]}
    risk_events = json.loads((_DATA_DIR / "risk_events.json").read_text())["risk_events"]

    out: Dict[str, Any] = {}
    for re in risk_events:
        m = hv_map.get(re["id"], {})
        kris = [{"id": m.get("primary"), "name": kri_name.get(m.get("primary"), ""), "role": "primary"}]
        for also in m.get("also", []):
            kris.append({"id": also, "name": kri_name.get(also, ""), "role": "also"})
        out[re["scenario"]] = {
            "hv_id": re["id"],
            "hv_name": re["name"],
            "frameworks": re.get("frameworks", []),
            "scope_note": re.get("scope_note", ""),
            "shape_topology_provenance": re.get("shape_topology_provenance", re.get("shape_provenance", "")),
            "shape_parameter_provenance": re.get("shape_parameter_provenance", "operator_calibrated"),
            "metric_provenance": re.get("metric_provenance", ""),
            "kris": [k for k in kris if k["id"]],
        }
    return out


# ── event phase tagging (build-up → cascade → recovery) — timeline-ready ───────
def _phase_tags(events: List[Dict[str, Any]]) -> List[str]:
    """Tag each event with an incident phase. The deployment cascade has an explicit
    lifecycle (deploy → cascade → rollback → recovery) so map by event_type. The
    continuous-load scenarios (kafka lag, velocity) are tagged from the TRAJECTORY of
    their load signal: rising is build-up/cascade, PAST THE PEAK is recovery — so the
    drain/decay tail reads as `recovery`, not `build_up` (the per-event v1 tagger
    mislabelled it, leaving kafka/velocity with zero recovery events)."""
    ets = {e.get("event_type") for e in events}
    if "deployment_start" in ets:
        m = {"deployment_start": "build_up", "cascade_failure": "cascade",
             "rollback_start": "recovery", "recovery": "recovery", "rollback_complete": "recovery"}
        return [m.get(e.get("event_type"), "cascade") for e in events]

    def load(e: Dict[str, Any]) -> float:
        for k in ("lag_messages", "error_rate_pct", "transactions_per_sec", "surge_ratio", "auth_failure_rate_pct"):
            v = e.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return 0.0

    def breached(e: Dict[str, Any]) -> bool:
        return bool(e.get("slo_violation") or e.get("aml_review_routed")
                    or e.get("event_type") == "velocity_surge"
                    or (e.get("surge_ratio") or 0) > 3
                    or e.get("responder_lockout") == 1
                    or (e.get("auth_failure_rate_pct") or 0) > 50)

    loads = [load(e) for e in events]
    peak_i = max(range(len(loads)), key=lambda i: loads[i]) if loads else 0
    tags = []
    for i, e in enumerate(events):
        if i > peak_i:
            tags.append("recovery")           # past the peak → trajectory is down
        elif breached(e):
            tags.append("cascade")
        else:
            tags.append("build_up")
    return tags


def _counted(value: Any, query: str, computation: str) -> Dict[str, Any]:
    return value_with_provenance(value, counted_provenance(
        source_system="event_generator", source_query=query, computation=computation))


def _illustrative(value: Any, computation: str) -> Dict[str, Any]:
    return value_with_provenance(value, illustrative_provenance(
        source_system="operator_calibrated", source_query="synthesized",
        computation=computation,
        assumptions=["operator-calibrated illustration of the response-time gap; "
                     "NOT measured telemetry"]))


def _derived(value: Any, computation: str) -> Dict[str, Any]:
    """A value DERIVED from a real count (not pure illustration): the count is
    upstream, only a coefficient is operator-calibrated. Tagging it `illustrative`
    would be a lineage lie — a partly-counted number wearing a 'fabricated' tag."""
    return value_with_provenance(value, derived_provenance(
        computation=computation,
        assumptions=["real event count is upstream; the miss-fraction (0.4/0.35) is operator_calibrated"]))


# ── war-room response timelines — the PEOPLE in the response gap ────────────────
# Round-8 depth pass: the gap was minutes-on-a-chart; real incidents are humans on
# a bridge. Each timeline's minute marks are CONSISTENT with that regime's
# detection/escalation/evidence metrics (same operator-calibrated response model);
# actors are illustrative roles + names. This is what the manual-vs-instrumented
# gap FEELS like from inside the war room.
_RESPONSE_TIMELINES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "identity_outage": {
        "traditional": [
            {"t_min": 0,  "actor": "support + social", "action": "login-failure reports spike everywhere at once — detection is NOT the problem; the auth dashboard itself needs SSO to open"},
            {"t_min": 3,  "actor": "on-call SRE (S. Iyer)", "action": "page acknowledged from a personal phone — the runbook, the console and the incident tooling all sit behind the failed identity plane"},
            {"t_min": 12, "actor": "war room (improvised)", "action": "bridge assembles on personal devices; nobody can pull auth-service metrics — the people who fix identity authenticate THROUGH identity"},
            {"t_min": 25, "actor": "incident commander (K. Osei)", "action": "SEV-1 declared verbally; escalation stalls hunting for the ONE engineer with a still-valid local admin path"},
            {"t_min": 42, "actor": "platform engineer", "action": "ad-hoc break-glass improvised (shared root credential from a safe) — access restored 42 minutes in; remediation of the plane itself only STARTS now"},
            {"t_min": 120,"actor": "duty analyst", "action": "evidence pack reconstructed after the fact — the lockout window is a hole in its own audit trail"},
        ],
        "risk_as_code": [
            {"t_min": 0,  "actor": "PL-03 KRI", "action": "token-issuance failure rate crosses its band — page carries the causal chain and fires over the OUT-OF-BAND path (paging does not ride the failed plane)"},
            {"t_min": 2,  "actor": "on-call SRE (S. Iyer)", "action": "acks; break-glass identity (pre-provisioned, exercised quarterly, logged) opens the consoles in minutes"},
            {"t_min": 6,  "actor": "incident commander (K. Osei)", "action": "SEV-1 declared from the pre-filled doc; customer-lockout counter and support-queue depth already on the bridge screen"},
            {"t_min": 10, "actor": "platform (human-in-loop)", "action": "fallback token path proposed by runbook, confirmed by a named human; re-auth surge plan staged before recovery begins"},
            {"t_min": 12, "actor": "platform", "action": "evidence pack auto-assembled — out-of-band telemetry recorded THROUGH the lockout; the break-glass use is itself on the log"},
        ],
    },
    "kafka_lag_storm": {
        "traditional": [
            {"t_min": 0,  "actor": "PagerDuty → on-call SRE (S. Iyer)", "action": "payments-latency page fires — one of 37 pages that hour; auto-resolved once by the flapping-alert rule"},
            {"t_min": 12, "actor": "on-call SRE (S. Iyer)", "action": "correlates checkout-latency complaints with consumer lag on payment-events by hand across 4 dashboards; SEV-2 opened"},
            {"t_min": 22, "actor": "incident commander (K. Osei)", "action": "SEV-1 declared; war room opens — Payments, Platform, Support on the bridge; exec comms channel spun up"},
            {"t_min": 34, "actor": "war room", "action": "root-cause hypothesis: consumer group stuck mid-rebalance in eu-west-1 — ~92% of capacity parked; drain plan drafted by hand"},
            {"t_min": 55, "actor": "VP Eng (M. Okonkwo)", "action": "approves consumer scale-out ×3 under the launch change-freeze exception — the approval itself takes 12 minutes to hunt down"},
            {"t_min": 90, "actor": "on-call + duty analyst", "action": "evidence pack assembled by hand from 6 dashboards and Slack scrollback; timestamps disagree across sources"},
        ],
        "risk_as_code": [
            {"t_min": 0,  "actor": "DR-02 KRI", "action": "fires with causal context attached: ~88k msg/s consumer deficit (rebalance stall), stuck-generation ids, projected violation of the 4.8M-message backlog SLO in 6 min"},
            {"t_min": 2,  "actor": "on-call SRE (S. Iyer)", "action": "acks a page that carries the causal chain, not a bare threshold — no dashboard archaeology"},
            {"t_min": 5,  "actor": "incident commander (K. Osei)", "action": "SEV-2 declared from the pre-filled incident doc; RP-02 pattern + drain runbook linked"},
            {"t_min": 8,  "actor": "on-call SRE (human-in-loop)", "action": "confirms the proposed consumer scale-out — automation proposes, a named human disposes"},
            {"t_min": 10, "actor": "platform", "action": "evidence pack auto-assembled: seeded event stream, KRI timeline, decisions — sealed and attributable"},
        ],
    },
    "deployment_cascade": {
        "traditional": [
            {"t_min": 0,  "actor": "release engineer (D. Patel's org)", "action": "v2.4.1 rolling deploy proceeds — canary stage green (the regression is in a code path canary traffic never exercises)"},
            {"t_min": 10, "actor": "on-call SRE", "action": "error budget page for order-router; correlation to the deploy is manual — the deploy dashboard and the error dashboard disagree on timezones"},
            {"t_min": 20, "actor": "incident commander", "action": "SEV-1 declared as breakers open across 4 services; support queue flooding; status page still green"},
            {"t_min": 38, "actor": "war room", "action": "rollback decision argued for 8 minutes — 'is it the deploy or the database?' — before change ticket CHG-2025-0401 is pulled up"},
            {"t_min": 60, "actor": "release engineering", "action": "rollback to v2.4.0 completes; cache warm-up tail keeps p99 elevated another 20 min"},
            {"t_min": 100,"actor": "duty analyst", "action": "evidence pack stitched from deploy logs + breaker metrics + Slack; the 'who approved the deploy' thread takes the longest"},
        ],
        "risk_as_code": [
            {"t_min": 0,  "actor": "DR-01 KRI", "action": "fires on error-vs-deploy correlation the moment svc-0 error crosses its band — change ticket, artifact hash and blast-radius map attached"},
            {"t_min": 2,  "actor": "on-call SRE", "action": "acks; the page already names the deploy, the diff, and the four downstream services in the dependency path"},
            {"t_min": 4,  "actor": "incident commander", "action": "SEV-1 declared; rollback proposal pre-staged with the prior artifact pinned"},
            {"t_min": 7,  "actor": "release engineer (human-in-loop)", "action": "confirms rollback — the decision is one approval, not an argument, because the causal evidence is on the page"},
            {"t_min": 12, "actor": "platform", "action": "evidence pack sealed: deploy → violation → decision → recovery, one timeline, one hash"},
        ],
    },
    "velocity_surge": {
        "traditional": [
            {"t_min": 0,  "actor": "fraud-ops analyst (night shift)", "action": "velocity dashboard spikes; analyst is mid-way through a 200-item review queue and the spike alert has a 4-hour SLA"},
            {"t_min": 12, "actor": "fraud-ops analyst", "action": "manual triage confirms 8× baseline tps concentrated in one corridor; unclear if promo traffic or attack — asks in three Slack channels"},
            {"t_min": 20, "actor": "payments risk duty officer", "action": "escalates; fraud rules tightened by hand — false-positive blocks spike on legitimate customers immediately"},
            {"t_min": 45, "actor": "war room", "action": "AML routing question raised — 'does this need a review-queue disposition?' — nobody on the bridge owns the answer at 3am"},
            {"t_min": 85, "actor": "duty analyst", "action": "evidence assembled by hand; blocked-transaction counts differ between the fraud tool and the payments ledger by ~4%"},
        ],
        "risk_as_code": [
            {"t_min": 0,  "actor": "GV-02 KRI", "action": "fires at 3× baseline with corridor breakdown and a promo-calendar cross-check already attached — 'no scheduled promo' is on the page"},
            {"t_min": 2,  "actor": "fraud-ops analyst", "action": "acks; graduated velocity controls proposed (step-up auth first, hard blocks only above 6×) instead of a blanket rule"},
            {"t_min": 5,  "actor": "payments risk duty officer (human-in-loop)", "action": "confirms; AML review-queue routing fires automatically as a fraud-control signal — explicitly NOT a BSA/AML determination"},
            {"t_min": 10, "actor": "platform", "action": "evidence sealed with blocked-txn counts reconciled to the ledger at write time"},
        ],
    },
}


def _build_comparison(events: List[Dict], scenario: str) -> Dict[str, Any]:
    """Wrap the spreadsheet-vs-signal comparison; every response-time number is
    illustrative (operator_calibrated), labelled as such per-value."""
    cmp = compare_response_strategies(events, scenario)
    out: Dict[str, Any] = {"source_status": "illustrative", "regimes": {}}
    for key, regime in cmp.items():           # "traditional" / "risk_as_code"
        wrapped = {"label": _REGIME_LABEL.get(key, regime.get("name", key)),
                   "name": regime.get("name", key), "metrics": {}}
        for mk, mv in regime.items():
            if mk == "name":
                continue
            if isinstance(mv, (int, float)):
                if mk in _DERIVED_METRICS:
                    wrapped["metrics"][mk] = _derived(
                        mv, f"round(count({scenario} events) × miss_fraction) — event count counted, fraction operator-calibrated")
                else:
                    wrapped["metrics"][mk] = _illustrative(
                        mv, f"{scenario} · {key} · {mk} — operator-calibrated response model")
            else:
                wrapped["metrics"][mk] = {"value": mv, "provenance": {"source_status": "illustrative"}}
        tl = (_RESPONSE_TIMELINES.get(scenario) or {}).get(key)
        if tl:
            wrapped["response_timeline"] = {
                "source_status": "illustrative",
                "note": ("war-room narrative — actors and events are illustrative; minute "
                         "marks are consistent with this regime's operator-calibrated "
                         "response metrics (same model, same numbers)"),
                "entries": tl,
            }
        out["regimes"][key] = wrapped
    return out


def _build_domain(scenario: str, seed: int, kri_map: Dict[str, Any]) -> Dict[str, Any]:
    events, summary = run_scenario(scenario, seed=seed)
    tax = kri_map.get(scenario, {})
    tags = _phase_tags(events)
    phases = [dict(e, phase=tags[i]) for i, e in enumerate(events)]
    phase_counts: Dict[str, int] = {}
    for e in phases:
        phase_counts[e["phase"]] = phase_counts.get(e["phase"], 0) + 1

    # honesty (risk-officer/regulator): `services_hit` and `duration_s` in the summary
    # are INPUT constants (n_services / the loop bound), not counts — so recompute them
    # from the ACTUAL event stream so the "counted" badge is true (e.g. observed span
    # 298s, not the 300s loop bound). Other peaks are genuine max/agg over the stream.
    observed: Dict[str, Any] = {}
    ts = [e.get("t_seconds") for e in events if e.get("t_seconds") is not None]
    if ts:
        observed["duration_s"] = max(ts)
    svcs = {e.get("service") for e in events if e.get("service")}
    if svcs:
        observed["services_hit"] = len(svcs)

    peaks = {}
    for k, v in summary.items():
        if k in ("scenario", "risk_patterns"):
            continue
        if k in observed:
            peaks[k] = _counted(observed[k], f"observed {k} over {scenario} event stream",
                                f"{k} counted from the event stream (not the run parameter)")
        elif isinstance(v, bool):
            # a flag (aml_review_routed / change_failure / rollback) is not a numeric
            # PEAK — skip it (bool is a subclass of int, so it must be caught before the
            # numeric branch or it would render as a tile wearing a false "counted" badge).
            continue
        elif isinstance(v, (int, float)):
            peaks[k] = _counted(v, f"max/agg over {scenario} event stream", f"counted {k}")
        else:
            peaks[k] = {"value": v, "provenance": {"source_status": "real_query_synthesized_data"}}

    # Stage 2 of reviews/journey_spine_port_spec.md — the chip grammar on every
    # series surface: realness · cardinality · window · generator, DERIVED from
    # the actual stream (the reference practice: a signal you can trust on sight
    # because it declares what it is). hv's unit is the event stream.
    tel_fields = {k for e in events for k, v in e.items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)
                  and k not in ("t_seconds",)}
    stream_chip = {
        "realness": "SEEDED",
        "events": len(events),
        "window_s": observed.get("duration_s", 0),
        "telemetry_fields": len(tel_fields),
        "gen": f"event_generator@seed{seed}",
    }

    return {
        "domain_id": scenario,
        "name": summary.get("scenario", scenario),
        "label": tax.get("hv_name", summary.get("scenario", scenario)),
        "hv_id": tax.get("hv_id", ""),
        "overall_rag": "critical",                       # every scenario is a failure case
        "event_count": _counted(len(events), f"count({scenario} events)", "counted events in the stream"),
        "phase_counts": phase_counts,
        "peaks": peaks,
        "comparison": _build_comparison(events, scenario),
        "kris_fired": tax.get("kris", []),
        "frameworks": tax.get("frameworks", []),
        "scope_note": tax.get("scope_note", ""),
        "shape_topology_provenance": tax.get("shape_topology_provenance", tax.get("shape_provenance", "")),
        "shape_parameter_provenance": tax.get("shape_parameter_provenance", "operator_calibrated"),
        "metric_provenance": tax.get("metric_provenance", ""),
        "stream_chip": stream_chip,
        "events": phases,
    }


def make_projection(*, seed: int = 42, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Build the projection. (seed, as_of) fixed → byte-reproducible projection
    and seal. seed pins the sim RNG + event clock; as_of pins every provenance
    stamp + generated_at."""
    set_as_of(as_of)
    try:
        return _make_projection(seed=seed, as_of=as_of)
    finally:
        set_as_of(None)


def _make_projection(*, seed: int, as_of: Optional[str]) -> Dict[str, Any]:
    from datetime import datetime, timezone
    kri_map = _load_kri_mapping()
    domains = {s: _build_domain(s, seed, kri_map) for s in _SCENARIOS}

    # portfolio-level counts (all COUNTED)
    events_total = sum(d["event_count"]["value"] for d in domains.values())
    kris_exercised = sorted({k["id"] for d in domains.values() for k in d["kris_fired"]})

    def _peak_int(d, key):
        return int(d["peaks"].get(key, {}).get("value") or 0)
    slo_violations_total = _peak_int(domains["kafka_lag_storm"], "slo_violations")

    _gen_at = as_of if as_of else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _period = (as_of[:7] if as_of else datetime.now(timezone.utc).strftime("%Y-%m"))

    # Stage 2 — the stream catalog: name your sources of record (GENERATED,
    # reconciled by the audit against the domains it describes). Built here as
    # projection data; the data/stream_catalog.json export belongs to
    # write_hv_report ALONE — make_projection stays a pure function of
    # (seed, as_of), so audit builds at other seeds never touch data/.
    stream_catalog = [{
        "id": f"stream.{s}",
        "scenario": d["label"] or d["name"],
        "hv_id": d["hv_id"],
        "chip": d["stream_chip"],
        "intent": f"the {d['name']} incident replay — every node value, KPI and KRI on the observatory derives from this stream",
    } for s, d in domains.items()]

    projection = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "artefact_version": ARTEFACT_VERSION,
            "period": _period,
            "generated_at": _gen_at,
            "run_seed": seed,
            "domain_ids": _SCENARIOS,               # the scenario rail
            "domain_object": "scenario",
            "modality": "live-simulation",
            "counts": {
                "scenarios_total": len(_SCENARIOS),
                "events_total": events_total,
                "slo_violations": slo_violations_total,
                "kris_exercised": len(kris_exercised),
            },
            "counts_provenance": {
                # honest tiers: events_total + slo_violations are COUNTED over the seeded
                # stream; scenarios_total is DERIVED from the scenario registry (a list
                # length, not a count over data); kris_exercised is DERIVED from the hub
                # crosswalk (a taxonomy set-union, not synthesized data).
                "scenarios_total": "derived",
                "events_total": "real_query_synthesized_data",
                "slo_violations": "real_query_synthesized_data",
                "kris_exercised": "derived",
            },
            "kris_exercised": kris_exercised,
            "overall_posture": "cascade",
            # Round-8 depth pass — the platform these scenarios live on. ILLUSTRATIVE
            # global-fintech archetype (operator-calibrated to public scale references,
            # not measured): the point is that the interesting failure modes are the
            # ones EQUILIBRIUM HIDES — autoscale and microservice complexity mask
            # split-brain and single-points-of-failure until a storm surfaces them
            # (the observatory's ghost node is exactly that class).
            "platform_context": {
                "source_status": "illustrative",
                "facts": [
                    "multi-cloud · multi-region · HA built-in · data-localization boundaries",
                    "~500 apps on K8s across 1,000+ namespaces — the platform IS this composition",
                    "1M+ containers; ~70% destroyed and recreated daily (GitOps-driven)",
                    "20M+ policy-as-code checks/day gating IaC and deploys",
                    "Kafka cumulative pipeline 10B+ events/day ACROSS those apps; backlog peaks in the tens of millions on the largest",
                    "etcd fleets riding their size ceiling with autoscale relief — constant pressure-and-release equilibrium",
                    "100M+ active users; AI/LLM services in the customer-serving path",
                ],
                "note": (
                    "Scale here means COMPOSITION — hundreds of apps × a thousand-plus "
                    "namespaces × regions — not one big number. The platform runs tight: horizontal + vertical autoscaling releases "
                    "pressure as fast as it builds, which means split-brain risk and "
                    "single-points-of-failure stay HIDDEN under the complexity until an "
                    "incident surfaces them. That masked class is what the observatory's "
                    "blind-spot (ghost) node represents."
                ),
            },
        },
        "domains": domains,
        "stream_catalog": stream_catalog,
        "action_log": _HV_LOG.action_log_summary(),
        "telemetry_status": "synthesised",
        "source_note": (
            "Input is a seeded scenario simulator (simulator/event_generator.py). "
            "Scenario provenance is split at the honest granularity: the failure-mode "
            "TOPOLOGY is source_derived from public reporting, but the specific numeric "
            "SHAPE PARAMETERS (degradation depth, phase timing) are operator_calibrated "
            "— tuned, not from any cited source. The spreadsheet-vs-signal response-time "
            "gap is likewise operator_calibrated ILLUSTRATION (labelled per value), not "
            "measured telemetry. "
            "Peaks + counts are COUNTED over the seeded event stream (peak_error_rate / "
            "peak_latency_ms saturate at an operator-set SLO ceiling). Incident-phase tags "
            "(build_up/cascade/recovery) and phase_counts are DERIVED by a trajectory "
            "heuristic over the stream (single-dominant-peak; a multi-peak real trace could "
            "mis-tag a later surge), not raw event fields. Each scenario maps to a "
            "canonical hub KRI via packages/kri-taxonomy. Reproducible under (seed, as_of)."
        ),
    }
    projection["ia"] = _build_ia(projection)
    return projection


def _build_ia(p):
    """hv grammar: the spine nodes ARE the scenarios (one observatory section —
    nothing to sub-walk; the observatory's own play/scrub/tour is the device)."""
    def uv(x):
        return x.get("value") if isinstance(x, dict) and "value" in x else (x or 0)

    doms = p.get("domains", {})
    ids = list(doms.keys())

    def met(d, regime, key):
        m = (((doms.get(d, {}).get("comparison") or {}).get("regimes") or {}).get(regime) or {}).get("metrics") or {}
        v = m.get(key) or {}
        return v.get("value") if isinstance(v, dict) else v

    nodes = []
    for d in ids:
        dom = doms[d]
        det_m, det_i = met(d, "traditional", "detection_time_min"), met(d, "risk_as_code", "detection_time_min")
        ev_m, ev_i = met(d, "traditional", "evidence_ready_min"), met(d, "risk_as_code", "evidence_ready_min")
        nodes.append({
            "id": d, "beat": "BELIEVE", "act": "observatory",
            "label": dom.get("label") or d,
            "headline": (f"{uv(dom.get('event_count'))} events replayed · detection {det_m}→{det_i} min · "
                         f"evidence ready {ev_m}→{ev_i} min · posture {str(dom.get('overall_rag', '')).upper()} — "
                         "play the cascade, scrub the timeline, open the war room."),
            "targets": [],
        })
    order = [n["id"] for n in nodes]
    paths = {
        "basic": order,
        "leadership": sorted(order, key=lambda d: 0 if doms[d].get("overall_rag") == "red" else 1),
        "engineering": sorted(order, key=lambda d: 0 if "kafka" in d else 1),
        "audit": sorted(order, key=lambda d: 0 if "velocity" in d else 1),
    }
    c = p.get("meta", {}).get("counts", {})
    return {
        "thesis": ("The same incident, two regimes: instrumented detection flags in minutes what the manual "
                   "playbook finds in tens — and has audit-ready evidence sooner by the length of a war room."),
        "acts": [{"id": "observatory", "name": "Observatory",
                  "desc": "play the cascade · scrub the timeline · open the war room"}],
        "nodes": nodes,
        "paths": paths,
        "headlines": {},
        "default_role": "basic",
        "source_note": f"{c.get('scenarios_total', 0)} scenarios · {c.get('events_total', 0)} events — spine and headlines derive from this projection.",
    }
