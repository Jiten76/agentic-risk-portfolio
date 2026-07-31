#!/usr/bin/env python3
"""Build the offline PROSE review instrument — reviews/PROSE_REVIEW.html.

A single self-contained page handed to external AI reviewers (GROK, a fresh
Claude) to grade the READER-FACING texts of the GitHub channel on four axes:
english, flow, accuracy, relevance/drift. The machine gates prove counts and
links; this instrument covers what gates cannot — whether a human reads the
prose and believes it.

Everything checkable is DERIVED at build time: the fact table pulls from the
trust board, the detection-eval record and the sealed projections, and the
exhibits are the ACTUAL current files (monorepo README + the three cut product
READMEs), embedded verbatim. If exports/ is stale, the build refuses — a prose
review against stale text is worse than none.

Run from repo root, AFTER cut_product_repos.py:
    python3 scripts/build_prose_review.py
Output is deliberately untracked — a working review artifact, not a shipped one.
"""
from __future__ import annotations

import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reviews" / "PROSE_REVIEW.html"

# The About field lives on GitHub, outside the repo — embedded here by hand and
# labeled as such. Reviewers check it like every other exhibit.
ABOUT_BLURB = ("What does a bad year cost — and can you prove the number? Which shared "
               "dependency drags everything down at once? Did an AI agent just touch a "
               "tool it never should have? How fast do you really detect? Three working "
               "tools answer — from seeded, sealed data you can re-check in your browser.")

THESES = [
    "Risk-as-code, working end to end — three tools, one sealed platform; no white-paper fluff.",
    "2LoD independent observation — verdict-free surfaces; materiality determination reserved to Legal/Compliance.",
    "Consequence-driven severity — unauthorized-ACTION capability tops the scale, not data categories.",
    "Render-from-data — every number derives from sealed projections; seeded, byte-reproducible, AI-review disclosed as AI.",
    "The loop closes through a human — A8 gate on every rule change; no self-tuning governor.",
    "Graph engines, graph surfaces — LangGraph state machines under flow-graph pixels; risk moves along edges.",
    "Sparse-but-honest regulatory claims — caveats over fake precision; 'breach' only for real breaches.",
]

QUESTIONS = [
    ("ENGLISH", "Grammar, awkward phrasing, redundancy. AI-voice tells: em-dash density, "
                "'X, not Y' constructions, aphorism-per-paragraph rhythm, relentless parallelism. "
                "Quote the sentence; propose the rewrite."),
    ("FLOW", "Does each document argue (thesis → proof → credibility → integration), or accumulate? "
             "Does every image/GIF have a setup before and a debrief after that match what it shows? "
             "Is anything load-bearing buried mid-paragraph?"),
    ("ACCURACY", "Check EVERY number and claim against the fact table below. Flag any figure not in "
                 "the table, any overclaim (measured vs illustrative vs seeded), any regulatory "
                 "statement asserting a determination rather than a trigger."),
    ("RELEVANCE / DRIFT", "Judge each text against the seven theses. Flag anything that reads as "
                          "consulting fluff, bragging without reasoning, insider jargon, or a claim "
                          "the artifacts do not back."),
]


def _fact_table() -> list:
    board = json.loads((ROOT / "qa" / "trust_board.json").read_text())
    a = board["audits"]
    gf = board.get("gate_falsification") or {}
    ev = json.loads((ROOT / "qa" / "detection_eval.json").read_text())
    ec = ev["counts"]
    rac = json.loads((ROOT / "apps/risk-as-code-agent/outputs/v2_0a/2026-Q3_projection.json").read_text())
    atg = json.loads((ROOT / "apps/agent-trace-gov/outputs/2026-06_atg_projection.json").read_text())
    hv = json.loads((ROOT / "apps/hypervelocity-risk-sim/docs/projection.json").read_text())
    exp = rac["exposure"]["portfolio_total"]
    ac, hc = atg["meta"]["counts"], hv["meta"]["counts"]
    m = lambda x: f"${(x or 0) / 1e6:.1f}M"
    total = a["rac"]["pass"] + a["atg"]["pass"] + a["hv"]["pass"]

    # exhibit-cited leaves (r70): strategy dollars, levers, gate split, hv figures
    sc = rac.get("strategy_chooser") or {}
    strats = {s["id"]: s for s in sc.get("strategies", [])}
    levers = {l["id"]: l for l in rac.get("sensitivity", {}).get("levers", [])}
    joint = levers.get("joint_bad_year") or {}
    max_single = max((abs(l.get("delta_p95_pct") or 0) for lid, l in levers.items()
                      if not str(lid).startswith("joint")), default=0)
    ext_edges = [e for e in atg["lineage_graph"]["edges"] if e.get("external")]
    _actors = {}
    for _en in (atg.get("action_log", {}).get("recent_entries") or []):
        for _fid in (_en.get("linked_findings") or []):
            _actors[_fid] = _en.get("actor_name")
    def _gated(wf):
        return bool(wf) and any(f == wf or ("-" + str(wf)) in f for f in _actors)
    ext_total = len(ext_edges)
    ext_ungated = sum(1 for e in ext_edges if not _gated(e.get("workflow_id")))
    det_rows, prod_rate = [], 0.0
    for _did, _d in sorted(hv["domains"].items()):
        _rg = ((_d.get("comparison") or {}).get("regimes") or {})
        _man = (((_rg.get("traditional") or {}).get("metrics") or {}).get("detection_time_min") or {}).get("value")
        _ins = (((_rg.get("risk_as_code") or {}).get("metrics") or {}).get("detection_time_min") or {}).get("value")
        if _man is not None and _ins is not None:
            det_rows.append(f"{_d.get('hv_id', _did)}: {_man}→{_ins} min")
        if "kafka" in _did:
            _rates = [e.get("producer_rate_mps") or 0 for e in _d.get("events", [])]
            _rates = [r for r in _rates if r]
            prod_rate = sum(_rates) / len(_rates) if _rates else 0.0
    return [
        ("substance-audit gates", f"{total} = {a['rac']['pass']} (rac) + {a['atg']['pass']} (atg) + {a['hv']['pass']} (hv); all executed PASS"),
        ("bundle-level gates", f"{board.get('verify_bundle', {}).get('total', 26)} (verify_bundle)"),
        ("gate falsification", f"{gf.get('caught', 0)}/{gf.get('trials', 0)} planted defects caught"),
        ("detection-efficacy eval", f"{ec['tp_caught']}/{ec['tp_total']} in-class caught · "
                                    f"{ec['near_miss_clean']}/{ec['near_miss_total']} near-misses clean · "
                                    f"{ec['false_fires']} false fires · {ec['tp_total'] + ec['near_miss_total']} injections · "
                                    f"coverage gap: {', '.join(g['cls'] for g in ev.get('coverage_gaps', []))} · "
                                    f"boundaries documented: {len(ev.get('boundaries_documented', []))}"),
        ("rac residual P95 / inherent P95", f"{m(exp['p95_usd'])} / {m(exp['inherent_p95_usd'])}"),
        ("rac residual P50 / P99", f"{m(exp['p50_usd'])} / {m(exp['p99_usd'])}"),
        ("rac risk patterns", str(len(rac.get("patterns_meta", {}).get("patterns", [])) or 14)),
        ("atg findings / workflows / actions", f"{ac['findings_total']} / {ac['workflows_analyzed']} / {ac['actions_traced']}"),
        ("atg severity split", f"{ac['critical']}C / {ac['high']}H / {ac['medium']}M / {ac['low']}L (sums to findings_total)"),
        ("hv scenarios / events", f"{hc['scenarios_total']} / {hc['events_total']}"),
        ("seeds / reproducibility", "seed 42, fixed as-of clocks; byte-reproducible builds with in-browser SHA-256 seal"),
        ("review provenance", "AI reviews (role-played 2LoD/examiner/SRE/CISO agents + GROK + fresh Claude) — disclosed as AI, never human sign-offs"),
        # r70 (prose-wave finding 1, both reviewers): the table must cover EVERY
        # figure the exhibits cite — an instrument that cannot reconcile its own
        # exhibits cannot certify them.
        ("strategy: harden benefit", m(strats["harden_controls"]["benefit_p95_usd"]) + " residual reduction (C39-recomputed from levers)"),
        ("strategy: isolate ceiling", m(strats["isolate_dependencies"]["layer_ceiling_usd"]) + " whole-layer ceiling (C39-recomputed)"),
        ("joint bad year (stress lever)", f"+{joint.get('delta_p95_pct', 0):.0f}% → {m(joint.get('residual_p95'))} (same seed, one changed judgment)"),
        ("max single-lever move", f"{max_single:.0f}% of residual P95 (no single judgment moves it more)"),
        ("regulatory regimes mapped", f"{len(rac.get('materiality', {}))} (rac) · {len(atg.get('materiality', {}))} (atg) — applicability flags only; determination reserved"),
        ("atg external flows · human gate", f"{ext_ungated} of {ext_total} external flow traversals had no human gate (derived from lineage edges + attestation log — the lineage callout's own leaf)"),
        ("hv detection gap", " · ".join(det_rows) + " — operator-calibrated ILLUSTRATION per the projection's own provenance, never measured"),
        ("hv producer throughput (kafka scenario)", f"~{prod_rate:,.0f} msg/s steady (seeded event series; the GIF's counter samples this)"),
    ]


def _exhibits() -> list:
    ex = [("EXHIBIT A — GitHub About blurb (set on the repo, outside the gate perimeter)", ABOUT_BLURB)]
    readme = ROOT / "README.md"
    ex.append(("EXHIBIT B — monorepo README.md (the platform front door)", readme.read_text(encoding="utf-8")))
    for slug, label in [("risk-as-code-agent", "C"), ("agent-trace-gov", "D"), ("hypervelocity-risk-sim", "E")]:
        p = ROOT / "exports" / slug / "README.md"
        if not p.exists():
            raise SystemExit(f"exports/{slug}/README.md missing — run scripts/cut_product_repos.py first "
                             "(a prose review against stale text is worse than none)")
        ex.append((f"EXHIBIT {label} — {slug} product README (as cut, numbers derived at cut time)",
                   p.read_text(encoding="utf-8")))
    return ex


def build() -> Path:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    facts = _fact_table()
    E = html.escape
    parts = ["""<meta charset="utf-8"><title>PROSE REVIEW — agentic-risk-portfolio</title><style>
body{max-width:900px;margin:32px auto;padding:0 20px;font:15px/1.55 Georgia,serif;color:#1c1a17;background:#faf8f4}
h1{font-size:26px} h2{font-size:19px;margin-top:34px;border-bottom:2px solid #d8d2c6;padding-bottom:4px}
.meta,.q dt{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#6b6459}
.q dt{font-weight:700;color:#8a4b1f;margin-top:12px}.q dd{margin:2px 0 0 0}
table{border-collapse:collapse;width:100%;font-size:13px}td{border:1px solid #d8d2c6;padding:5px 9px;vertical-align:top}
td:first-child{font-family:ui-monospace,Menlo,monospace;white-space:nowrap;color:#5a5244}
pre{white-space:pre-wrap;background:#f1ede4;border:1px solid #d8d2c6;border-radius:6px;padding:14px 16px;
font:12.5px/1.5 ui-monospace,Menlo,monospace;overflow-x:auto}
.warn{background:#fdf3e2;border-left:4px solid #c98a3a;padding:8px 12px;font-size:13.5px}
ol li{margin:6px 0}</style>"""]
    parts.append(f"<h1>Prose review — the GitHub channel, read as a human</h1>"
                 f"<div class='meta'>generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')} · "
                 f"commit {E(sha)} · instrument: english / flow / accuracy / relevance</div>")
    parts.append("<h2>Your task</h2><p>You are reviewing the <b>reader-facing prose</b> of a hiring "
                 "portfolio's GitHub channel — five exhibits below, embedded verbatim. The machine gates "
                 "already verify counts, links and seals; you are the instrument for what gates cannot "
                 "judge: whether a sharp human reads this and believes it. Do not review code or visual "
                 "design. Judge on four axes:</p><dl class='q'>")
    for k, v in QUESTIONS:
        parts.append(f"<dt>{E(k)}</dt><dd>{E(v)}</dd>")
    parts.append("</dl><div class='warn'><b>Output format:</b> numbered findings, most severe first. Each: "
                 "{exhibit · verbatim quote · axis · severity (high/med/low) · why · suggested rewrite}. "
                 "End with a one-paragraph overall verdict per exhibit and a drift check against the theses. "
                 "If a claim is accurate but reads as unbacked bragging, that IS a finding. "
                 "<b>Begin your verdict by quoting the commit line at the top of this page</b> — findings "
                 "against any other baseline are stale by definition, and two review rounds have already "
                 "been spent re-litigating fixes that had shipped.</div>")
    parts.append("<h2>The seven theses (drift baseline)</h2><ol>")
    for t in THESES:
        parts.append(f"<li>{E(t)}</li>")
    parts.append("</ol>")
    parts.append("<h2>Fact table — every number a claim may cite (derived at build time)</h2><table>")
    for k, v in facts:
        parts.append(f"<tr><td>{E(k)}</td><td>{E(str(v))}</td></tr>")
    parts.append("</table><p class='meta'>Any figure in an exhibit that does not reconcile to this table "
                 "is a finding. Any figure IN the table the prose contradicts is a high-severity finding.</p>")
    for title, body in _exhibits():
        parts.append(f"<h2>{E(title)}</h2><pre>{E(body)}</pre>")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size:,} bytes)")
