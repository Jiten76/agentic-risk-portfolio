"""
history_synthesizer — produces N quarter-snapshots of pipeline output by running
the assessment at progressively worsening (or improving) intensities.

Used by html_report.py to draw trajectories (Q-over-Q delta, sparklines) and to
compute correlation across snapshots.

The UI labels these snapshots as SYNTHESIZED so consumers know historical data
is illustrative until a real telemetry stream is connected.
"""
from __future__ import annotations

import os
from typing import Dict, List

# Four quarters of synthesised history, each describing the scenario per domain.
# The shape mimics a slow worsening of Payments + Platform, with Trading and
# Custody / Identity remaining mostly stable. Designed so each quarter is
# defensibly different from the next (no monotonic uniform increase).
# Period labels are the three quarters PRECEDING the live assessment period
# (meta.period, clock-derived in risk_graph) plus the current one — the last
# entry stands in for the current period and make_projection post-reconciles
# its period/rag/count from the REAL report, so its label here is a fallback.
HISTORY_SCENARIOS: List[Dict[str, Dict[str, str]]] = [
    {
        "period": "2025-Q4",
        "scenarios": {
            "trading":  "normal",
            "payments": "normal",
            "custody":  "normal",
            "identity": "normal",
            "platform": "normal",
        },
    },
    {
        "period": "2026-Q1",
        "scenarios": {
            "trading":  "normal",
            "payments": "degraded",
            "custody":  "normal",
            "identity": "normal",
            "platform": "normal",
        },
    },
    {
        "period": "2026-Q2",
        "scenarios": {
            "trading":  "degraded",
            "payments": "degraded",
            "custody":  "normal",
            "identity": "normal",
            "platform": "degraded",
        },
    },
    {
        "period": "2026-Q3",
        "scenarios": {
            "trading":  "degraded",
            "payments": "incident",
            "custody":  "normal",
            "identity": "normal",
            "platform": "degraded",
        },
    },
]


def generate_history(current_scenario_map: Dict[str, str] | None = None) -> List[Dict]:
    """Run the pipeline at each historical scenario; return list of reports.

    If `current_scenario_map` is provided, it overrides the last (current) period.
    """
    # Lazy import to avoid pulling the graph module at history_synthesizer import time
    from graph.risk_graph import run_risk_assessment

    out: List[Dict] = []
    for i, hist in enumerate(HISTORY_SCENARIOS):
        scen = hist["scenarios"]
        if i == len(HISTORY_SCENARIOS) - 1 and current_scenario_map:
            scen = current_scenario_map
        # Force mock mode for synthesized history — no API spend on synthetic runs
        prior_mode = os.environ.get("LLM_MODE")
        os.environ["LLM_MODE"] = "mock"
        try:
            report = run_risk_assessment(scenario_map=scen)
        finally:
            if prior_mode is None:
                os.environ.pop("LLM_MODE", None)
            else:
                os.environ["LLM_MODE"] = prior_mode
        report["period"] = hist["period"]
        report["_synthesized"] = (i < len(HISTORY_SCENARIOS) - 1)  # mark all but the current period
        out.append(report)
    return out


def trajectory_for_domain(history: List[Dict], domain_id: str) -> List[Dict]:
    """Return [{period, rag, red, amber, findings}] per quarter for a domain."""
    series = []
    for snap in history:
        dr = snap.get("domain_reports", {}).get(domain_id, {})
        series.append({
            "period": snap.get("period", "?"),
            "rag":    dr.get("overall_rag", "green"),
            "red":    dr.get("red_findings", 0),
            "amber":  dr.get("amber_findings", 0),
            "total":  dr.get("total_findings", 0),
        })
    return series


def trajectory_for_pattern(history: List[Dict], pattern_id: str) -> List[Dict]:
    """Return [{period, fired_in_n_domains, worst_rag}] per quarter for a pattern."""
    series = []
    for snap in history:
        n_domains = 0
        worst = "green"
        rag_order = {"green": 0, "amber": 1, "red": 2}
        for dr in snap.get("domain_reports", {}).values():
            for f in dr.get("findings", []):
                if f.get("pattern_id") == pattern_id:
                    n_domains += 1
                    if rag_order.get(f.get("overall_rag", "green"), 0) > rag_order.get(worst, 0):
                        worst = f.get("overall_rag", "green")
                    break
        series.append({
            "period": snap.get("period", "?"),
            "fired_in_n_domains": n_domains,
            "worst_rag": worst,
        })
    return series


def overall_trajectory(history: List[Dict]) -> List[Dict]:
    """Per-quarter overall posture + finding count for the portfolio."""
    return [
        {
            "period": snap.get("period", "?"),
            "rag":    snap.get("overall_rag", "green"),
            "findings": snap.get("total_findings", 0),
        }
        for snap in history
    ]


# Unicode block characters for sparklines (matches "no external libs" rule)
_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: List[int | float], width: int | None = None) -> str:
    """Render a unicode sparkline from a list of numeric values."""
    if not values:
        return ""
    if width is not None and len(values) > width:
        # downsample
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]
    lo, hi = min(values), max(values)
    if hi == lo:
        return _BLOCKS[len(_BLOCKS) // 2] * len(values)
    out = []
    for v in values:
        idx = int(((v - lo) / (hi - lo)) * (len(_BLOCKS) - 1))
        out.append(_BLOCKS[idx])
    return "".join(out)
