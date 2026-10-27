"""
html_report v1.3.1 — Self-contained HTML risk operating system.

⚠️ ARCHIVED (v1.3). This renderer displays the RETRACTED flat `$/red` exposure
model (data.finding_metadata.financial_exposure). It is NO LONGER the shipped
surface — ui/app.py generates the v2.0a render-from-data dashboard
(utils.v2_html_report.write_v2_report), whose exposure is the corrected
frequency×severity model (utils.exposure). Kept for history; do not wire back
to a live entrypoint.

Council-driven fixes from outputs/council/v1_3_review.md:
  [1] Single source-of-truth counts; hero stats use explicit denominators.
  [2] Trajectory vs forecast reconciliation in forecast card.
  [3] Acceptance trail uses per-pattern justification + named human signers +
      countersigner + ticket + conditions.
  [4] Treatment pill renders ticket + owner handle + ETA; ISO 31000 strict
      vocabulary (no "monitor").
  [5] Signal cells render inline threshold + smart rounding (no spurious
      precision).
  [6] Auto-expand limited to the top-1 red finding by financial exposure.

Two views (Engineering + Leadership; Audit deferred per DESIGN.md).
"""

from __future__ import annotations

import html
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from data.history_synthesizer import (
    generate_history, trajectory_for_domain, overall_trajectory,
    trajectory_for_pattern, sparkline,
)
from data.finding_metadata import enrich_finding
from utils.primitives import (
    scope_for_pattern, cascade_for_finding, correlation_for_pattern,
    skew_for_pattern, domain_skew, trajectory_delta, domain_trajectory_delta,
    forecast_next_period, materiality_summary,
)


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_template_asset(filename: str) -> str:
    return (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _fmt_usd(n: int | float) -> str:
    if n is None:
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000_000: return f"${n / 1_000_000_000:.1f}B"
    if abs(n) >= 1_000_000:     return f"${n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:         return f"${n / 1_000:.0f}K"
    return f"${n:.0f}"


def _fmt_signal_value(name: str, value: Any) -> str:
    """Smart rounding based on signal name. No more vuln_aging_days_p90=62.157.

    - *_count, count → int
    - *_pct, *_rate → 1 decimal place
    - *_days, *_minutes, *_ms, *_seconds → int (whole units)
    - default → 1 decimal place
    """
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _esc(value)

    n = name.lower()
    if "count" in n:
        return str(int(round(v)))
    if n.endswith(("_days", "_minutes", "_ms", "_seconds")) or n in ("mttr_minutes",):
        return str(int(round(v)))
    if n.endswith(("_pct", "_rate")) or "rate" in n or "pct" in n:
        return f"{v:.1f}"
    # Heuristic: integer-ish values become int
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"


def _aging_tier(days: int) -> str:
    if days >= 60: return "high"
    if days >= 21: return "mid"
    return "low"


def _signal_threshold_label(signal_name: str, threshold: Dict[str, Any] | None) -> str:
    """Short inline threshold label, e.g. 'red≥25' or 'red≤95'.

    Direction matters: for change_failure_rate, higher is worse (red≥red).
    For availability_pct, lower is worse (red≤red). We infer from the
    relationship: if green > amber, higher is better → red is on the LOW side.
    """
    if not isinstance(threshold, dict):
        return ""
    red = threshold.get("red")
    if red is None:
        return ""
    green = threshold.get("green")
    amber = threshold.get("amber")
    higher_is_better = (isinstance(green, (int, float)) and isinstance(amber, (int, float))
                       and green > amber)
    arrow = "≤" if higher_is_better else "≥"
    # Format the red threshold per signal type
    red_str = _fmt_signal_value(signal_name, red)
    return f"red{arrow}{red_str}"


def _all_findings(report: Dict[str, Any]):
    """Flatten to (domain_id, domain_name, finding) tuples."""
    for did, dr in report.get("domain_reports", {}).items():
        for f in dr.get("findings", []):
            yield (did, dr.get("domain_name", did), f)


def _scenario_map_from_report(report: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for did, dr in report.get("domain_reports", {}).items():
        snap = dr.get("snapshot", {})
        out[did] = snap.get("scenario", "normal")
    return out


def _portfolio_counts(report: Dict[str, Any]) -> Dict[str, int]:
    """Single source of truth — counts findings AND domains separately.
    All hero stats and section summaries must read from this dict."""
    findings = list(_all_findings(report))
    f_red   = sum(1 for _, _, f in findings if f.get("overall_rag") == "red")
    f_amber = sum(1 for _, _, f in findings if f.get("overall_rag") == "amber")
    f_green = sum(1 for _, _, f in findings if f.get("overall_rag") == "green")
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


# ── hero / header ────────────────────────────────────────────────────────────

def _hero_headline(report: Dict[str, Any]) -> str:
    c = _portfolio_counts(report)
    overall = report.get("overall_rag", "green")
    domains = report.get("domain_reports", {})
    red_doms = [d.get("domain_name", k).split(" &")[0]
                for k, d in domains.items() if d.get("overall_rag") == "red"]
    amber_doms = [d.get("domain_name", k).split(" &")[0]
                  for k, d in domains.items() if d.get("overall_rag") == "amber"]

    if overall == "red":
        leads = ", ".join(red_doms) if red_doms else "Multiple domains"
        verb = "are" if len(red_doms) != 1 else "is"
        return (
            f'<span class="rag-token rag-red-text">{_esc(leads)}</span> '
            f'{verb} <span class="rag-token rag-red-text">RED</span>. '
            f'<span style="color:var(--text-muted)">{c["findings_total"]} findings '
            f'({c["findings_red"]} red · {c["findings_amber"]} amber) '
            f'across {c["domains_total"]} domains.</span>'
        )
    if overall == "amber":
        leads = ", ".join(amber_doms[:2]) if amber_doms else "Posture"
        verb = "approach" if len(amber_doms) != 1 else "approaches"
        return (
            f'{_esc(leads)} {verb} '
            f'<span class="rag-token rag-amber-text">AMBER</span>. '
            f'<span style="color:var(--text-muted)">{c["findings_total"]} findings '
            f'({c["findings_red"]} red · {c["findings_amber"]} amber).</span>'
        )
    return (
        f'Posture <span class="rag-token rag-green-text">GREEN</span> '
        f'across all {c["domains_total"]} domains.'
    )


def _render_hero_bar(report: Dict[str, Any]) -> str:
    overall = report.get("overall_rag", "green")
    c = _portfolio_counts(report)

    return f"""
    <section class="hero-bar" data-rag="{_esc(overall)}">
      <div class="posture-orb" data-rag="{_esc(overall)}">{_esc(overall.upper())}</div>
      <h1 class="hero-headline">{_hero_headline(report)}</h1>
      <div class="hero-stats">
        <div class="hero-stat"><span class="hero-stat-label">Findings total</span><span class="hero-stat-value">{c["findings_total"]}</span></div>
        <div class="hero-stat"><span class="hero-stat-label">Red findings</span><span class="hero-stat-value">{c["findings_red"]}</span></div>
        <div class="hero-stat"><span class="hero-stat-label">Amber findings</span><span class="hero-stat-value">{c["findings_amber"]}</span></div>
        <div class="hero-stat"><span class="hero-stat-label">Red domains</span><span class="hero-stat-value">{c["domains_red"]} / {c["domains_total"]}</span></div>
      </div>
    </section>
    """


# ── Engineering view ─────────────────────────────────────────────────────────

def _render_cascade_chip(direction: str, edge: Dict) -> str:
    arrow = "↓" if direction == "down" else "↑"
    label = "drives" if direction == "down" else "driven by"
    return (
        f'<span class="cascade-chip" title="{_esc(edge.get("rationale", ""))}">'
        f'<span class="arrow">{arrow}</span> '
        f'<span>{label}</span> '
        f'<span class="pid">{_esc(edge["pattern_id"])}</span> '
        f'<span style="color:var(--text-faint)">({_esc(edge.get("strength", ""))})</span>'
        f'</span>'
    )


def _render_signal_compact(breached: Dict, limit: int = 2) -> str:
    """Inline signal cell — name = value with red threshold tag on the right.

    Per council item 5: '`change_failure_rate=19  red≥25`' is operational.
    Spurious precision (62.157 days) is replaced by smart rounding.
    """
    parts = []
    for k, v in list((breached or {}).items())[:limit]:
        if isinstance(v, dict):
            val = _fmt_signal_value(k, v.get("value"))
            rag = v.get("rag", "amber")
            thr_label = _signal_threshold_label(k, v.get("threshold"))
            chip = (
                f'<span style="color:var(--text-muted)">{_esc(k)}=</span>'
                f'<span style="color:var(--{rag})"><b>{_esc(val)}</b></span>'
            )
            if thr_label:
                chip += f'  <span class="threshold-inline">{_esc(thr_label)}</span>'
            parts.append(chip)
    return "  ·  ".join(parts)


def _render_treatment_pill(treatment: Dict, compact: bool = False) -> str:
    """Renders treatment as: plan · status · ticket · @owner · ETA.

    Per council item 4. If compact=True, drops owner handle to save row width.
    """
    plan = treatment.get("plan", "—")
    status = treatment.get("status", "")
    ticket = treatment.get("ticket", "")
    owner = treatment.get("owner_handle", "")
    eta = treatment.get("eta", "")

    bits = [
        f'<span class="plan">{_esc(plan)}</span>',
        f'<span>{_esc(status)}</span>',
    ]
    if ticket:
        bits.append(f'<span class="ticket">{_esc(ticket)}</span>')
    if owner and not compact:
        bits.append(f'<span class="owner-handle">{_esc(owner)}</span>')
    if eta:
        bits.append(f'<span class="eta">ETA {_esc(eta)}</span>')

    sep = '<span style="color:var(--text-faint)">·</span>'
    inner = f' {sep} '.join(bits)
    return f'<span class="treatment-pill" data-status="{_esc(status)}">{inner}</span>'


def _render_acceptance_block(a: Dict, compact: bool = False) -> str:
    """Render a single acceptance record. New shape (v1.3.1) carries named
    individual humans, role tier, countersigner, ticket, conditions."""
    acceptor_line = (
        f'{_esc(a.get("accepted_by_name"))} '
        f'<span style="color:var(--text-muted)">— {_esc(a.get("accepted_by_title"))} '
        f'({_esc(a.get("accepted_by_role"))})</span>'
    )
    countersign_line = ""
    if a.get("countersigned_by_name"):
        countersign_line = (
            f'<div class="when">Countersigned by '
            f'<b>{_esc(a.get("countersigned_by_name"))}</b> · '
            f'{_esc(a.get("countersigned_by_title"))} '
            f'({_esc(a.get("countersigned_by_role"))})</div>'
        )
    ticket = a.get("ticket", "")
    ticket_line = ""
    if ticket:
        ticket_line = (
            f'<div class="when">Decision record: '
            f'<span class="ticket-inline">{_esc(ticket)}</span></div>'
        )
    conditions = a.get("conditions", "")
    conditions_line = ""
    if conditions:
        conditions_line = (
            f'<div class="when" style="margin-top:4px"><i>{_esc(conditions)}</i></div>'
        )

    return f"""
    <div class="acceptance-block">
      <div class="who">Accepted by {acceptor_line}</div>
      <div class="what">{_esc(a.get("justification", ""))}</div>
      <div class="when">on {_esc(a.get("accepted_at"))} · expires {_esc(a.get("expires_at"))}</div>
      {countersign_line}
      {ticket_line}
      {conditions_line}
    </div>
    """


def _render_finding_detail(finding: Dict, report: Dict, history: List[Dict]) -> str:
    pid = finding.get("pattern_id", "")
    narrative = finding.get("evidence_narrative") or ""
    thr_src = finding.get("threshold_source")
    thr_url = finding.get("threshold_source_url")
    appetite = finding.get("appetite") or ""
    incidents = finding.get("incident_reference") or []
    controls = finding.get("compensating_controls", [])
    acceptance = finding.get("acceptance_trail", [])
    first_det = finding.get("first_detected", "—")
    time_days = finding.get("time_in_state_days", 0)

    cascade = cascade_for_finding(report, pid)
    correlation = correlation_for_pattern(history, pid)

    # Left column
    left = []

    # First-detected anchor (council item 7 partial: surface the date so duration is reconstructible)
    left.append(f"""
    <div>
      <div class="detail-label">First detected</div>
      <div class="detail-body">{_esc(first_det)} · in state {time_days} days</div>
    </div>
    """)

    if narrative:
        left.append(f"""
        <div>
          <div class="detail-label">Evidence narrative</div>
          <div class="detail-body">{_esc(narrative)}</div>
        </div>
        """)

    if cascade["upstream_firing"] or cascade["downstream_firing"]:
        chips_up   = "".join(_render_cascade_chip("up",   e) for e in cascade["upstream_firing"])
        chips_down = "".join(_render_cascade_chip("down", e) for e in cascade["downstream_firing"])
        left.append(f"""
        <div>
          <div class="detail-label">Cascade — currently firing chains</div>
          <div class="detail-body">{chips_up}{chips_down}</div>
        </div>
        """)

    if correlation:
        items = "".join(
            f'<span class="cascade-chip">'
            f'<span style="color:var(--text-faint)">co-fired</span> '
            f'<span class="pid">{_esc(c["pattern_id"])}</span> '
            f'<span style="color:var(--text-faint)">{c["co_fires"]}/{c["of_total"]} qtrs</span>'
            f'</span>'
            for c in correlation
        )
        left.append(f"""
        <div>
          <div class="detail-label">Historical correlation (≥50% co-fire across history)</div>
          <div class="detail-body">{items}</div>
        </div>
        """)

    if thr_src:
        body = _esc(thr_src)
        if thr_url:
            body += f' <a href="{_esc(thr_url)}" target="_blank" rel="noopener">source ↗</a>'
        left.append(f"""
        <div>
          <div class="detail-label">Threshold source</div>
          <div class="detail-body">{body}</div>
        </div>
        """)

    if appetite:
        left.append(f"""
        <div>
          <div class="detail-label">Risk appetite</div>
          <div class="detail-body">{_esc(appetite)}</div>
        </div>
        """)

    # Right column
    right = []
    if controls:
        items = "".join(
            f'<li>'
            f'<span class="ctrl-name">{_esc(c["name"])}</span>'
            f'<span class="ctrl-meta eff-{_esc(c.get("effectiveness", "low"))}">'
            f'{_esc(c.get("effectiveness", "—"))} · {_esc(c.get("framework", ""))}'
            f'</span></li>'
            for c in controls
        )
        right.append(f"""
        <div>
          <div class="detail-label">Compensating controls ({len(controls)})</div>
          <ul class="controls-list">{items}</ul>
        </div>
        """)

    if acceptance:
        blocks = "".join(_render_acceptance_block(a) for a in acceptance)
        right.append(f"""
        <div>
          <div class="detail-label">Risk acceptance audit trail</div>
          {blocks}
        </div>
        """)

    if incidents:
        items = []
        for ref in incidents:
            url = ref.get("url", "")
            name = _esc(ref.get("name", ""))
            date = _esc(ref.get("date", ""))
            summary = _esc(ref.get("summary", ""))
            link = f'<a href="{_esc(url)}" target="_blank" rel="noopener">{name}</a>' if url else name
            items.append(f'<li><span class="meta">{date} · {link}</span><div class="detail-body">{summary}</div></li>')
        right.append(f"""
        <div>
          <div class="detail-label">Anchoring incidents ({len(incidents)})</div>
          <ul class="incident-list">{''.join(items)}</ul>
        </div>
        """)

    return f'<div>{"".join(left)}</div><div>{"".join(right)}</div>'


def _render_engineering_findings_table(report: Dict, history: List[Dict]) -> str:
    findings = list(_all_findings(report))
    if not findings:
        return '<div class="empty-row">No material findings this period.</div>'

    # Council item 6: auto-expand only the top-1 red finding by financial exposure.
    top_red_key = None
    top_red_exposure = -1
    for did, dname, f in findings:
        if f.get("overall_rag") != "red":
            continue
        exp = (f.get("financial_exposure") or {}).get("usd", 0)
        if exp > top_red_exposure:
            top_red_exposure = exp
            top_red_key = (did, f.get("pattern_id"))

    rows = []
    for did, dname, f in findings:
        rag = f.get("overall_rag", "amber")
        pid = f.get("pattern_id", "")
        pname = f.get("pattern_name", "")
        breached = f.get("signals_exceeded", {})
        incidents = f.get("incident_reference") or []
        treatment = f.get("treatment", {})
        time_days = f.get("time_in_state_days", 0)
        first_det = f.get("first_detected", "—")
        aging = _aging_tier(time_days)

        scope = scope_for_pattern(report, pid)
        cascade = cascade_for_finding(report, pid)

        search_text = " ".join([
            pid, pname, dname,
            *list((breached or {}).keys()),
            *(ref.get("name", "") for ref in incidents),
            scope["label"], treatment.get("plan", ""),
            treatment.get("ticket", ""), treatment.get("owner_handle", ""),
        ])

        # Top-1 red auto-expand
        is_top_red = (rag == "red" and (did, pid) == top_red_key)
        expanded = "true" if is_top_red else "false"

        # Inline cascade chips — only currently-firing edges (council item 9 partial)
        cascade_inline = ""
        if cascade["upstream_firing"]:
            cascade_inline += _render_cascade_chip("up", cascade["upstream_firing"][0])
        if cascade["downstream_firing"]:
            cascade_inline += _render_cascade_chip("down", cascade["downstream_firing"][0])

        # Last-seen-as incident lead
        incident_short = ""
        if incidents:
            ref = incidents[0]
            incident_short = (
                f'<span class="date">{_esc(ref.get("date", ""))}</span>'
                f'{_esc(ref.get("name", "").split(" — ")[0])}'
            )

        rows.append(f"""
        <div class="finding-row"
             data-rag="{_esc(rag)}"
             data-domain="{_esc(did)}"
             data-expanded="{expanded}"
             data-treatment="{_esc(treatment.get('status', ''))}"
             data-search="{_esc(search_text)}">
          <div><span class="rag-tag" data-rag="{_esc(rag)}">{_esc(rag.upper())}</span></div>
          <div class="pid">{_esc(pid)}</div>
          <div class="pname">
            {_esc(pname)} <span style="color:var(--text-faint)">· {_esc(dname.split(' &')[0])}</span>
            <div style="margin-top:4px; display:flex; gap:6px; flex-wrap:wrap; align-items:center">
              <span class="scope-tag" data-tier="{_esc(scope['tier'])}">{_esc(scope['label'])} {scope['n_domains']}d</span>
              {_render_treatment_pill(treatment, compact=True)}
              <span class="time-state" data-aging="{aging}">first detected {_esc(first_det)} · {time_days}d in state</span>
            </div>
          </div>
          <div class="signals">{_render_signal_compact(breached, limit=2)}</div>
          <div class="incident">{incident_short}{('<div class="cascade-strip">' + cascade_inline + '</div>') if cascade_inline else ''}</div>
          <div class="chev"></div>
        </div>
        <div class="finding-detail">{_render_finding_detail(f, report, history)}</div>
        """)

    return f"""
    <div class="findings-table">
      <div class="findings-header">
        <div>RAG</div><div>ID</div><div>Pattern · Domain · Scope · Treatment · First detected</div>
        <div>Signals (value · threshold)</div><div>Last seen · Cascade</div><div></div>
      </div>
      {''.join(rows)}
      <div class="empty-row" data-hidden="true">No findings match the current filters.</div>
    </div>
    """


def _render_engineering_skew(report: Dict) -> str:
    skews = domain_skew(report)
    if not skews:
        return ""
    max_w = max(s["weighted"] for s in skews) or 1
    rows = []
    for s in skews:
        pct = int((s["weighted"] / max_w) * 100)
        rows.append(f"""
        <div class="skew-row">
          <div class="skew-name">{_esc(s['domain_name'])}</div>
          <div class="skew-bar" style="--pct:{pct}%"></div>
          <div class="skew-num">{s['red']}R · {s['amber']}A findings</div>
          <div><span class="rag-tag" data-rag="{_esc(s['rag'])}">{_esc(s['rag'].upper())}</span></div>
        </div>
        """)
    return f"""
    <div class="findings-table" style="margin-bottom:var(--s-4)">
      <div class="signal-family">Portfolio skew — which domain is pulling the average</div>
      {''.join(rows)}
    </div>
    """


def _render_engineering_filter_bar(report: Dict) -> str:
    findings = list(_all_findings(report))
    total = len(findings)
    by_rag = Counter(f.get("overall_rag", "green") for _, _, f in findings)
    by_domain = Counter()
    domain_names = {}
    for did, dname, _ in findings:
        by_domain[did] += 1
        domain_names[did] = dname

    rag_chips = [
        f'<button class="filter-chip" data-filter="rag" data-value="all">'
        f'All <span class="count">{total}</span></button>'
    ]
    for rag, label in [("red", "Red"), ("amber", "Amber"), ("green", "Green")]:
        n = by_rag.get(rag, 0)
        active = "true" if rag in ("red", "amber") else "false"
        rag_chips.append(
            f'<button class="filter-chip" data-filter="rag" data-value="{rag}" '
            f'data-rag="{rag}" data-active="{active}">'
            f'{label} <span class="count">{n}</span></button>'
        )

    dom_chips = [
        '<button class="filter-chip" data-filter="domain" data-value="all" data-active="true">All</button>'
    ]
    for did, n in by_domain.most_common():
        short = domain_names[did].split(" &")[0]
        dom_chips.append(
            f'<button class="filter-chip" data-filter="domain" data-value="{_esc(did)}" '
            f'data-active="false">{_esc(short)} <span class="count">{n}</span></button>'
        )

    return f"""
    <div class="filter-bar">
      <div class="filter-group" data-label="Severity">{''.join(rag_chips)}</div>
      <div class="filter-group" data-label="Domain">{''.join(dom_chips)}</div>
      <input class="filter-search" type="search" placeholder="Search pattern, signal, incident, ticket, owner..." />
      <span class="hero-stat-label" style="margin-left:auto" data-filter-summary></span>
    </div>
    """


def _render_engineering_view(report: Dict, history: List[Dict]) -> str:
    return f"""
    <div id="tab-engineering" class="tab-panel">
      <div class="section-eyebrow">Engineering · VP Engineering · DevSecOps · Release Manager · SOC Expert</div>
      <h2 class="section-title">What to fix today — and what's upstream of it</h2>

      {_render_engineering_skew(report)}
      {_render_engineering_filter_bar(report)}
      {_render_engineering_findings_table(report, history)}
    </div>
    """


# ── Leadership view ──────────────────────────────────────────────────────────

def _render_trajectory_section(history: List[Dict]) -> str:
    overall = overall_trajectory(history)
    if not overall:
        return ""

    domain_ids = list(history[-1].get("domain_reports", {}).keys())
    overall_vals = [o["findings"] for o in overall]
    overall_spark = sparkline(overall_vals)
    overall_delta = trajectory_delta(history)

    domain_rows = []
    for did in domain_ids:
        series = trajectory_for_domain(history, did)
        vals = [s["total"] for s in series]
        spark = sparkline(vals)
        delta = domain_trajectory_delta(history, did)
        cur_rag = series[-1]["rag"]
        cur_n = series[-1]["total"]
        dname = history[-1]["domain_reports"][did].get("domain_name", did).split(" &")[0]
        domain_rows.append(f"""
        <div class="trajectory-row">
          <div class="traj-name">{_esc(dname)}</div>
          <div class="traj-spark" title="4 quarters: {' · '.join(s['period'] for s in series)}">{spark}</div>
          <div class="traj-delta" data-dir="{_esc(delta['direction'])}">{_esc(delta['label'])} {delta.get('delta_findings', 0):+d}</div>
          <div class="traj-rag"><span class="rag-tag" data-rag="{_esc(cur_rag)}">{cur_n}</span></div>
        </div>
        """)

    return f"""
    <div class="findings-table" style="margin-bottom:var(--s-5)">
      <div class="signal-family">
        Portfolio trajectory ·
        {_esc(overall[0]['period'])} → {_esc(overall[-1]['period'])} ·
        <span style="color:var(--{('red' if overall_delta['direction'] == 'worsening' else ('green' if overall_delta['direction'] == 'improving' else 'text-muted'))})">
          {_esc(overall_delta['label'])}
        </span>
        <span style="color:var(--text-faint)"> · {overall_delta['curr_findings']} findings ({overall_delta['delta_findings']:+d} vs {_esc(overall_delta['prev_period'])})</span>
      </div>
      <div class="trajectory-row" style="background:rgba(0,0,0,0.18)">
        <div class="traj-name" style="font-weight:600">Portfolio overall</div>
        <div class="traj-spark" style="font-size:1.2rem">{overall_spark}</div>
        <div class="traj-delta" data-dir="{_esc(overall_delta['direction'])}">{_esc(overall_delta['label'])} {overall_delta['delta_findings']:+d}</div>
        <div></div>
      </div>
      {''.join(domain_rows)}
    </div>
    """


def _render_forecast_card(history: List[Dict]) -> str:
    """Council item 2: reconcile trajectory verdict vs forecast direction.

    If Q-over-Q delta says 'improving' but multi-quarter slope says 'worsening',
    surface both — do not pretend the page is internally consistent when it isn't.
    """
    f = forecast_next_period(history)
    if f.get("projected_findings") is None:
        return ""

    delta = trajectory_delta(history)
    qq_dir = delta.get("direction", "stable")       # last-period change
    slope_dir = (
        "worsening" if f["slope"] > 0.5
        else ("improving" if f["slope"] < -0.5 else "stable")
    )

    # Reconciliation language
    if qq_dir == slope_dir:
        # Aligned — single direction message
        if slope_dir == "worsening":
            phrase = "Trend continues to worsen at current rate."
        elif slope_dir == "improving":
            phrase = "Trend continues to improve at current rate."
        else:
            phrase = "Trend remains stable at current rate."
    else:
        # Divergent — name both directions, do not paper over
        if qq_dir == "improving" and slope_dir == "worsening":
            phrase = (
                "Improved this quarter, but multi-quarter trend remains upward. "
                "Run-rate suggests current improvement does not yet bend the curve."
            )
        elif qq_dir == "worsening" and slope_dir == "improving":
            phrase = (
                "Regressed this quarter, but multi-quarter trend is favourable. "
                "Treat this quarter as a single-period outlier pending Q+1 data."
            )
        elif qq_dir == "stable" and slope_dir == "worsening":
            phrase = "Flat this quarter, but multi-quarter trend remains upward."
        elif qq_dir == "stable" and slope_dir == "improving":
            phrase = "Flat this quarter, but multi-quarter trend is favourable."
        else:
            phrase = "Trajectory mixed across periods."

    return f"""
    <div class="forecast-card" data-rag="{_esc(f['projected_rag'])}">
      <div>
        <div class="forecast-meta">Next period projection</div>
        <div class="forecast-number">{f['projected_findings']}</div>
        <div class="forecast-meta">findings · confidence {_esc(f['confidence'])}</div>
      </div>
      <div>
        <div class="forecast-detail">
          {_esc(phrase)} Linear extrapolation across {len(history)} historical quarters.
          This is illustrative, not a probabilistic forecast.
        </div>
      </div>
    </div>
    """


def _render_materiality(report: Dict) -> str:
    flags = materiality_summary(report)
    if not flags:
        return '<div style="color:var(--text-muted); font-size:var(--t-caption)">No regulatory disclosure triggers fired this period.</div>'

    blocks = []
    for f in flags:
        triggered_str = (
            f"{len(f['triggered'])} firing pattern{'s' if len(f['triggered']) != 1 else ''} fire this trigger"
            if f["triggered"]
            else f"{len(f['conditional'])} pattern{'s' if len(f['conditional']) != 1 else ''} make this conditional"
        )
        blocks.append(f"""
        <div class="materiality-flag" data-status="{_esc(f['status'])}">
          <div class="trigger-label">{_esc(f['trigger'])} · {_esc(f['status'])}</div>
          <div class="trigger-desc">{_esc(f['label'])}</div>
          <div class="trigger-meta">{_esc(triggered_str)}: {', '.join(f['triggered'] or f['conditional'])}</div>
        </div>
        """)
    return f'<div class="materiality-bar">{"".join(blocks)}</div>'


def _render_financial_exposure(report: Dict) -> str:
    by_domain = {}
    by_domain_red = {}
    by_domain_basis = {}
    for did, dname, f in _all_findings(report):
        exp = f.get("financial_exposure", {})
        usd = exp.get("usd", 0)
        by_domain[did] = (dname, by_domain.get(did, (dname, 0))[1] + usd)
        if f.get("overall_rag") == "red":
            by_domain_red[did] = (dname, by_domain_red.get(did, (dname, 0))[1] + usd)
            # Track the largest single basis citation per domain (for surfacing)
            if exp.get("usd", 0) > by_domain_basis.get(did, {"usd": 0})["usd"]:
                by_domain_basis[did] = {"usd": usd, "basis": exp.get("basis", "")}
    if not by_domain:
        return ""

    cards = []
    sorted_doms = sorted(by_domain.items(), key=lambda x: -x[1][1])
    portfolio_total = sum(t[1] for t in by_domain.values())
    portfolio_red_total = sum(t[1] for t in by_domain_red.values())

    cards.append(f"""
    <div class="exposure-card" data-rag="red">
      <div class="exposure-amount">{_fmt_usd(portfolio_total)}</div>
      <div class="exposure-basis">Portfolio total · {_fmt_usd(portfolio_red_total)} from red findings</div>
    </div>
    """)

    for did, (dname, usd) in sorted_doms[:5]:
        red_usd = by_domain_red.get(did, (dname, 0))[1]
        rag = "red" if red_usd > 0 else "amber"
        basis = by_domain_basis.get(did, {}).get("basis", "")
        basis_line = (
            f"Largest comparable: {_esc(basis)}"
            if basis
            else f"{_esc(dname.split(' &')[0])} · {_fmt_usd(red_usd)} red exposure"
        )
        cards.append(f"""
        <div class="exposure-card" data-rag="{rag}">
          <div class="exposure-amount">{_fmt_usd(usd)}</div>
          <div class="exposure-basis">{_esc(dname.split(' &')[0])} · {basis_line}</div>
        </div>
        """)
    return f"""
    <div class="section-eyebrow">Financial exposure · estimates cited to comparable real incidents</div>
    <div class="exposure-strip" style="margin-bottom:var(--s-5)">{''.join(cards)}</div>
    """


def _render_acceptance_trail_section(report: Dict) -> str:
    """Leadership-view roll-up of all active acceptances. New shape includes
    named acceptor + countersigner + ticket + conditions."""
    items = []
    for did, dname, f in _all_findings(report):
        for a in (f.get("acceptance_trail") or []):
            items.append((did, dname, f, a))
    if not items:
        return ""

    blocks = []
    for did, dname, f, a in items[:10]:
        # Compact Leadership variant — show the named acceptor + pattern + ticket
        header = (
            f'<b>{_esc(a.get("accepted_by_name"))}</b> '
            f'<span style="color:var(--text-muted)">({_esc(a.get("accepted_by_role"))})</span> '
            f'· {_esc(f.get("pattern_id"))} {_esc(f.get("pattern_name"))} '
            f'· {_esc(dname.split(" &")[0])}'
        )
        countersign = ""
        if a.get("countersigned_by_name"):
            countersign = (
                f'<div class="when">Countersigned: '
                f'<b>{_esc(a.get("countersigned_by_name"))}</b> '
                f'({_esc(a.get("countersigned_by_role"))})</div>'
            )
        ticket = a.get("ticket", "")
        ticket_line = ""
        if ticket:
            ticket_line = (
                f'<div class="when">Decision record: '
                f'<span class="ticket-inline">{_esc(ticket)}</span></div>'
            )

        blocks.append(f"""
        <div class="acceptance-block">
          <div class="who">{header}</div>
          <div class="what">{_esc(a.get("justification"))}</div>
          <div class="when">accepted {_esc(a.get("accepted_at"))} · expires {_esc(a.get("expires_at"))}</div>
          {countersign}
          {ticket_line}
        </div>
        """)
    return f"""
    <div class="section-eyebrow">Risk acceptance audit trail · active acceptances ({len(items)})</div>
    <div style="display:flex; flex-direction:column; gap:var(--s-2); margin-bottom:var(--s-5)">
      {''.join(blocks)}
    </div>
    """


def _render_top_fixes_leadership(report: Dict) -> str:
    fixes = []
    nist_owners = {
        "PR.IP": "Platform engineering",   "RC.RP": "SRE on-call",
        "PR.PT": "Platform engineering",   "RS.MI": "Security operations",
        "PR.AC": "Identity & access",      "PR.DS": "Privacy & compliance",
        "GV.SC": "Third-party risk",       "DE.CM": "SRE / detection",
        "GV.RM": "AI governance",          "RC.CO": "Incident command",
    }
    nist_plain_english = {
        "PR.IP": "Information Protection",  "RC.RP": "Recovery Planning",
        "PR.PT": "Protective Technology",   "RS.MI": "Response — Mitigation",
        "PR.AC": "Access Control",          "PR.DS": "Data Security",
        "GV.SC": "Supply Chain Risk",       "DE.CM": "Continuous Monitoring",
        "GV.RM": "Risk Management Governance", "RC.CO": "Recovery — Communications",
    }
    for did, dname, f in _all_findings(report):
        if f.get("overall_rag") != "red":
            continue
        exp = f.get("financial_exposure", {})
        treatment = f.get("treatment", {})
        nist = f.get("nist_function", "")
        fixes.append({
            "domain": dname.split(' &')[0],
            "pid": f.get("pattern_id"),
            "pname": f.get("pattern_name"),
            "nist": nist,
            "nist_label": nist_plain_english.get(nist, nist),
            "owner": nist_owners.get(nist, "Domain owner"),
            "usd": exp.get("usd", 0),
            "basis": exp.get("basis", ""),
            "treatment": treatment,
        })
    fixes.sort(key=lambda x: -x["usd"])
    if not fixes:
        return '<div style="color:var(--text-muted); font-size:var(--t-caption)">No red findings.</div>'

    rows = []
    for i, fix in enumerate(fixes[:5]):
        t = fix["treatment"]
        meta_parts = [
            f"{_esc(fix['nist_label'])} ({_esc(fix['nist'])})",
            f"{_fmt_usd(fix['usd'])} exposure",
        ]
        if fix["basis"]:
            meta_parts.append(f"basis: {_esc(fix['basis'])}")
        if t.get("plan"):
            tp = f"{_esc(t['plan'])} ({_esc(t.get('status', ''))})"
            if t.get("ticket"):
                tp += f" · {_esc(t['ticket'])}"
            if t.get("eta"):
                tp += f" · ETA {_esc(t['eta'])}"
            meta_parts.append(tp)
        rows.append(f"""
        <div class="top-fix">
          <div class="top-fix-rank">{i+1}</div>
          <div class="top-fix-body">
            <div class="top-fix-title">{_esc(fix['pid'])} {_esc(fix['pname'])} · {_esc(fix['domain'])}</div>
            <div class="top-fix-meta">{' · '.join(meta_parts)}</div>
          </div>
          <div class="top-fix-owner">{_esc(fix['owner'])}</div>
        </div>
        """)
    return f'<div class="top-fixes">{"".join(rows)}</div>'


def _render_leadership_view(report: Dict, history: List[Dict]) -> str:
    return f"""
    <div id="tab-leadership" class="tab-panel">
      <div class="section-eyebrow">Leadership · CEO · CISO · CTO · CFO · VP Product · VP Infrastructure</div>
      <h2 class="section-title">Are we improving, what's it costing, what do we disclose</h2>

      {_render_trajectory_section(history)}

      <div class="strat-grid">
        <div>
          <div class="section-eyebrow">Forecast · next period</div>
          {_render_forecast_card(history)}
        </div>
        <div>
          <div class="section-eyebrow">Top fixes ranked by financial exposure</div>
          {_render_top_fixes_leadership(report)}
        </div>
      </div>

      <div class="section-eyebrow" style="margin-top:var(--s-5)">Regulatory materiality · disclosure triggers fired by current posture</div>
      {_render_materiality(report)}

      {_render_financial_exposure(report)}

      {_render_acceptance_trail_section(report)}
    </div>
    """


# ── Top-level renderer ───────────────────────────────────────────────────────

def render_report(report: Dict, history: Optional[List[Dict]] = None) -> str:
    styles = _read_template_asset("report_styles.css")
    script = _read_template_asset("report_script.js")

    if history is None:
        history = generate_history(_scenario_map_from_report(report))

    # Enrich every finding with v1.3.1 metadata
    for did, dr in report.get("domain_reports", {}).items():
        for f in dr.get("findings", []):
            enrich_finding(f, did)
    for snap in history:
        for did, dr in snap.get("domain_reports", {}).items():
            for f in dr.get("findings", []):
                enrich_finding(f, did)

    period = report.get("period", "—")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    c = _portfolio_counts(report)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>risk-as-code-agent · {_esc(period)}</title>
  <style>{styles}</style>
</head>
<body>
  <main class="container">

    <header class="topbar">
      <div class="brand">
        <span class="brand-name">risk-as-code-agent</span>
        <span class="brand-slash">/</span>
        <span class="brand-meta">v1.3.1 · risk operating system</span>
      </div>
      <div class="topbar-meta">{_esc(period)} · generated {_esc(generated_at)}</div>
    </header>

    {_render_hero_bar(report)}

    <div class="synth-banner">
      Threshold sources and incident citations are real · synthesised history and IRM-style metadata
      (ticket IDs, named signers, acceptance trail) map to your IRM at integration time
    </div>

    <!-- Tab radios drive panel visibility -->
    <input type="radio" name="tabs" id="tab-engineering-r" checked />
    <input type="radio" name="tabs" id="tab-leadership-r" />

    <nav class="tab-nav" role="tablist" aria-label="Report views">
      <label for="tab-engineering-r" role="tab">
        <span class="tab-name">Engineering</span>
        <span class="tab-meta">{c["findings_total"]} findings · cascade · treatment</span>
      </label>
      <label for="tab-leadership-r" role="tab">
        <span class="tab-name">Leadership</span>
        <span class="tab-meta">trajectory · exposure · materiality</span>
      </label>
    </nav>

    <div class="tab-panels">
      {_render_engineering_view(report, history)}
      {_render_leadership_view(report, history)}
    </div>

    <footer class="footer">
      <span>risk-as-code-agent v1.3.1 · {c["domains_total"]} domains · {c["findings_total"]} findings · self-contained · prints clean</span>
      <a href="https://github.com/Jiten76/risk-as-code-agent" target="_blank" rel="noopener">github.com/Jiten76/risk-as-code-agent</a>
    </footer>
  </main>

  <script>{script}</script>
</body>
</html>"""


def write_report(report: Dict, output_path: Optional[str] = None) -> str:
    if output_path is None:
        period = report.get("period", "report")
        os.makedirs("outputs", exist_ok=True)
        output_path = f"outputs/{period}_risk_dashboard.html"
    html_str = render_report(report)
    Path(output_path).write_text(html_str, encoding="utf-8")
    return output_path
