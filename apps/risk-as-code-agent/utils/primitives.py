"""
primitives — derive the v1.3 primitives (scope, cascade, correlation, skew,
trajectory deltas, forecast) from current + historical snapshots and from the
cascade rules baked into risk_patterns.json.

These functions are pure: in → out. No I/O, no LLM. Called by html_report.py
at render time.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


_PATTERNS_FILE = Path(__file__).resolve().parent.parent / "data" / "risk_patterns.json"


# ── Pattern metadata (loaded once) ────────────────────────────────────────────

def _load_patterns() -> Dict[str, Dict]:
    raw = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in raw.get("patterns", [])}


_PATTERNS = _load_patterns()


# ── Scope ────────────────────────────────────────────────────────────────────

def scope_for_pattern(report: Dict, pattern_id: str) -> Dict:
    """Returns {tier, n_domains, label}. Tier: isolated|emergent|systemic."""
    n = 0
    domains = []
    for did, dr in report.get("domain_reports", {}).items():
        for f in dr.get("findings", []):
            if f.get("pattern_id") == pattern_id:
                n += 1
                domains.append(dr.get("domain_name", did))
                break
    if n >= 4:
        tier, label = "systemic", "SYSTEMIC"
    elif n >= 2:
        tier, label = "emergent", "EMERGENT"
    elif n == 1:
        tier, label = "isolated", "ISOLATED"
    else:
        tier, label = "absent", "ABSENT"
    return {"tier": tier, "label": label, "n_domains": n, "domains": domains}


# ── Cascade ───────────────────────────────────────────────────────────────────

def _firing_patterns(report: Dict) -> set:
    out = set()
    for dr in report.get("domain_reports", {}).values():
        for f in dr.get("findings", []):
            out.add(f.get("pattern_id"))
    return out


def cascade_for_finding(report: Dict, pattern_id: str) -> Dict:
    """Returns {downstream_firing, upstream_firing} — each a list of:
       {pattern_id, name, strength, rationale} for cascade edges where the
       *other* end is *also* currently firing in this snapshot."""
    p = _PATTERNS.get(pattern_id)
    if not p:
        return {"downstream_firing": [], "upstream_firing": []}
    firing = _firing_patterns(report)

    downstream = []
    for edge in p.get("cascade_to", []):
        target_id = edge["pattern_id"]
        if target_id in firing:
            downstream.append({
                "pattern_id": target_id,
                "name":       _PATTERNS.get(target_id, {}).get("name", target_id),
                "strength":   edge.get("strength", ""),
                "rationale":  edge.get("rationale", ""),
            })
    upstream = []
    for edge in p.get("cascade_from", []):
        source_id = edge["pattern_id"]
        if source_id in firing:
            upstream.append({
                "pattern_id": source_id,
                "name":       _PATTERNS.get(source_id, {}).get("name", source_id),
                "strength":   edge.get("strength", ""),
                "rationale":  edge.get("rationale", ""),
            })
    return {"downstream_firing": downstream, "upstream_firing": upstream}


# ── Correlation across history ───────────────────────────────────────────────

def correlation_for_pattern(history: List[Dict], pattern_id: str) -> List[Dict]:
    """Across N historical snapshots, find pattern pairs that co-fire >=50% with
    the given pattern_id. Returns [{pattern_id, name, co_fire_rate}]."""
    if not history:
        return []
    co_fires: Counter = Counter()
    pattern_fires = 0
    for snap in history:
        firing = _firing_patterns(snap)
        if pattern_id not in firing:
            continue
        pattern_fires += 1
        for other in firing:
            if other != pattern_id:
                co_fires[other] += 1
    if pattern_fires == 0:
        return []
    results = []
    for other, count in co_fires.items():
        rate = count / pattern_fires
        if rate >= 0.5:
            results.append({
                "pattern_id":   other,
                "name":         _PATTERNS.get(other, {}).get("name", other),
                "co_fire_rate": rate,
                "co_fires":     count,
                "of_total":     pattern_fires,
            })
    results.sort(key=lambda x: -x["co_fire_rate"])
    return results


# ── Skew ─────────────────────────────────────────────────────────────────────

def skew_for_pattern(report: Dict, pattern_id: str) -> Dict:
    """Which domain contributes the worst signal value for this pattern?
       Returns {domain, signal, value} or None."""
    worst = None
    rag_order = {"green": 0, "amber": 1, "red": 2}
    for did, dr in report.get("domain_reports", {}).items():
        for f in dr.get("findings", []):
            if f.get("pattern_id") != pattern_id:
                continue
            for sname, sd in (f.get("signals_exceeded") or {}).items():
                if not isinstance(sd, dict):
                    continue
                rag_score = rag_order.get(sd.get("rag", "amber"), 0)
                if worst is None or rag_score > rag_order.get(worst["rag"], 0):
                    worst = {
                        "domain": dr.get("domain_name", did),
                        "signal": sname,
                        "value":  sd.get("value"),
                        "rag":    sd.get("rag", "amber"),
                    }
    return worst


def domain_skew(report: Dict) -> List[Dict]:
    """Per-domain contribution to portfolio red+amber count. Returns sorted desc."""
    out = []
    for did, dr in report.get("domain_reports", {}).items():
        red   = dr.get("red_findings", 0)
        amber = dr.get("amber_findings", 0)
        total = red * 2 + amber  # red weighted 2x
        out.append({
            "domain_id":   did,
            "domain_name": dr.get("domain_name", did),
            "red":         red,
            "amber":       amber,
            "weighted":    total,
            "rag":         dr.get("overall_rag", "green"),
        })
    out.sort(key=lambda x: -x["weighted"])
    return out


# ── Trajectory deltas ────────────────────────────────────────────────────────

def trajectory_delta(history: List[Dict]) -> Dict:
    """Compare current (last) to previous period. Returns trajectory verdict."""
    if len(history) < 2:
        return {"direction": "unknown", "delta_findings": 0, "delta_rag": 0,
                "label": "INSUFFICIENT HISTORY"}
    prev = history[-2]
    curr = history[-1]
    delta_findings = curr.get("total_findings", 0) - prev.get("total_findings", 0)

    rag_order = {"green": 0, "amber": 1, "red": 2}
    delta_rag = rag_order.get(curr.get("overall_rag", "green"), 0) - rag_order.get(prev.get("overall_rag", "green"), 0)

    if delta_findings > 2 or delta_rag > 0:
        direction, label = "worsening", "WORSENING"
    elif delta_findings < -2 or delta_rag < 0:
        direction, label = "improving", "IMPROVING"
    else:
        direction, label = "stable", "STABLE"
    return {
        "direction":       direction,
        "label":           label,
        "delta_findings":  delta_findings,
        "delta_rag":       delta_rag,
        "prev_findings":   prev.get("total_findings", 0),
        "curr_findings":   curr.get("total_findings", 0),
        "prev_period":     prev.get("period", "—"),
        "curr_period":     curr.get("period", "—"),
    }


def domain_trajectory_delta(history: List[Dict], domain_id: str) -> Dict:
    if len(history) < 2:
        return {"direction": "unknown", "delta_findings": 0, "label": "—"}
    prev = history[-2].get("domain_reports", {}).get(domain_id, {})
    curr = history[-1].get("domain_reports", {}).get(domain_id, {})
    delta_findings = curr.get("total_findings", 0) - prev.get("total_findings", 0)
    rag_order = {"green": 0, "amber": 1, "red": 2}
    delta_rag = rag_order.get(curr.get("overall_rag", "green"), 0) - rag_order.get(prev.get("overall_rag", "green"), 0)
    if delta_findings > 1 or delta_rag > 0:
        return {"direction": "worsening", "label": "↑", "delta_findings": delta_findings}
    if delta_findings < -1 or delta_rag < 0:
        return {"direction": "improving", "label": "↓", "delta_findings": delta_findings}
    return {"direction": "stable", "label": "→", "delta_findings": delta_findings}


# ── Forecast (linear extrapolation — illustrative) ───────────────────────────

def forecast_next_period(history: List[Dict]) -> Dict:
    """Project next period's total_findings via simple linear regression of
    findings count over the last N snapshots."""
    if len(history) < 2:
        return {"projected_findings": None, "projected_rag": None, "confidence": "low"}
    xs = list(range(len(history)))
    ys = [snap.get("total_findings", 0) for snap in history]
    # Least-squares slope + intercept
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = mean_y - slope * mean_x
    next_x = n
    projected = max(0, round(intercept + slope * next_x))
    last = ys[-1]
    if projected > last + 2:
        rag, conf = "red", "medium"
    elif projected < last - 2:
        rag, conf = "amber", "medium"
    else:
        rag, conf = history[-1].get("overall_rag", "green"), "low"
    return {
        "projected_findings": projected,
        "projected_rag":      rag,
        "confidence":         conf,
        "slope":              slope,
        "last":               last,
    }


# ── Materiality (per pattern) ────────────────────────────────────────────────

def materiality_for_pattern(pattern_id: str) -> Dict:
    p = _PATTERNS.get(pattern_id, {})
    return p.get("materiality_trigger", {})


def materiality_summary(report: Dict) -> List[Dict]:
    """For the portfolio: which regulatory triggers are fired by current
    firing patterns. Returns [{trigger, label, patterns_firing[], status}]."""
    triggers = {
        "sec_8k":      "SEC 8-K Item 1.05 (cybersecurity incident)",
        "occ_12cfr30": "OCC 12 CFR 30 (heightened standards reporting)",
        "gdpr_art33":  "GDPR Art. 33 (72-hour personal-data breach notification)",
        "eu_ai_act":   "EU AI Act 2024/1689 (high-risk system disclosure)",
    }
    firing = _firing_patterns(report)
    out = []
    for trig, label in triggers.items():
        triggered_patterns = []
        conditional_patterns = []
        for pid in firing:
            mat = _PATTERNS.get(pid, {}).get("materiality_trigger", {})
            v = mat.get(trig)
            if v is True:
                triggered_patterns.append(pid)
            elif v == "conditional":
                conditional_patterns.append(pid)
        if triggered_patterns or conditional_patterns:
            out.append({
                "trigger":     trig,
                "label":       label,
                "triggered":   triggered_patterns,
                "conditional": conditional_patterns,
                "status":      "TRIGGERED" if triggered_patterns else "CONDITIONAL",
            })
    return out
