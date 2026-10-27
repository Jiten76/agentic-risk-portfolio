#!/usr/bin/env python3
"""Build PRESENTER_KIT.md — the live-walkthrough script, generated from the
sealed projections (round-17; numbers can never drift from the artifact:
re-run this after any rebuild, and B11 pins the numbers it quotes).

Repo-only material for the presenter — deliberately NOT shipped in
PORTFOLIO_REVIEW or COLD_READ (a cold read that ships its own coaching isn't
cold, and a reviewer who sees the defense cards isn't adversarial).

Run from repo root:  python3 scripts/build_presenter_kit.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def m(x) -> str:
    return f"${(x or 0) / 1e6:.1f}M"


def main() -> int:
    rac = json.loads((ROOT / "apps/risk-as-code-agent/outputs/v2_0a/2026-Q3_projection.json").read_text())
    hv = json.loads((ROOT / "apps/hypervelocity-risk-sim/docs/projection.json").read_text())

    exp = rac["exposure"]["portfolio_total"]
    cf = (exp.get("correlation_model") or {}).get("independence_counterfactual") or {}
    sens = rac.get("sensitivity") or {}
    levers = sens.get("levers") or []
    lv = {l.get("id"): l for l in levers}
    p95s = [l["residual_p95"] for l in levers if l.get("residual_p95")]
    sweep = ((sens.get("sev_shock_sweep") or {}).get("points") or [])
    hi = sweep[-1] if sweep else {}
    gen2 = next((l for l in levers if "gen" in str(l.get("id", "")).lower() or "generation" in str(l.get("label", "")).lower()), {})
    jb = lv.get("joint_bad_year") or {}
    counts = rac["meta"]["counts"]
    regs = (rac.get("regulation_residual") or {}).get("by_regulation") or []
    top_reg = regs[0] if regs else {}
    ci = (exp.get("sampling_error") or {}).get("residual_p95_ci95") or [0, 0]
    reg_hv = hv["domains"]["deployment_cascade"]["comparison"]["regimes"]
    det_i = reg_hv["risk_as_code"]["metrics"]["detection_time_min"]["value"]
    det_m = reg_hv["traditional"]["metrics"]["detection_time_min"]["value"]

    kit = f"""# Presenter Kit — live walkthrough script
*(generated from the sealed projections by `scripts/build_presenter_kit.py` —
re-run after any rebuild; B11 pins these numbers. Not shipped in any review
bundle.)*

## The 90-second opening (say these three sentences early, in order)

1. **"Everything you'll see runs on synthetic, seeded data — no production
   system was touched, and every number on every screen traces to one sealed,
   reproducible projection."**
2. **"The headline — {m(exp['p50_usd'])} expected, {m(exp['p95_usd'])} stress-P95
   residual — is an illustrative correlated Monte-Carlo calibrated to a fintech
   archetype, not a fitted loss history; the sensitivity apparatus prices how far
   it moves if any calibration judgment is wrong."**
3. **"Materiality determinations are reserved to Legal and Compliance — this
   platform surfaces which regimes are *triggered*, it never makes the legal
   call."**

Then the route: **landing → rac read (chapter 1 → 2 → 3) → workbench as
leadership → the map (⌘) → challenge strip → validation package.** One click
per beat; let the pages argue.

## The numbers to hold in your head

| what | value | where it lives |
|---|---|---|
| residual | P50 {m(exp['p50_usd'])} · **P95 {m(exp['p95_usd'])}** · P99 {m(exp['p99_usd'])} | exec hero / read ch.1 |
| inherent | P95 {m(exp['inherent_p95_usd'])} | exec hero |
| independence counterfactual | P95 {m(cf.get('residual_p95'))} — cascade delta explicit + re-runnable | validation §1 |
| single-judgment span | {m(min(p95s))} – {m(max(p95s))} | tornado / hero range line |
| joint bad year | {m(jb.get('residual_p95'))} ({'+' if (jb.get('delta_p95_pct') or 0) >= 0 else ''}{jb.get('delta_p95_pct')}%) | tornado |
| severity co-movement priced to | +{hi.get('delta_p95_pct')}% at σ={hi.get('sigma')} | hero + σ-sweep |
| gen-2 cascade (understatement check) | {'+' if (gen2.get('delta_p95_pct') or 0) >= 0 else ''}{gen2.get('delta_p95_pct')}% | tornado |
| MC sampling error (P95, 95% CI) | {m(ci[0])} – {m(ci[1])} | validation §2 |
| register | {counts['findings_total']} findings · {counts.get('findings_red', counts.get('red', ''))} red · deterministic (C25) | register |
| top regulatory share | {top_reg.get('share_of_portfolio_p95_pct')}% under {top_reg.get('reg_id')} — STYLE-mapping, say so first | regulation view |
| hv detection gap | {det_m} → {det_i} min (illustrative, operator-calibrated) | hv observatory |

## The three cards

**Card 1 — "Is {m(exp['p95_usd'])} your number?"**
Say: *"It's the archetype's number, not a firm's. Seeded correlated Monte-Carlo,
20,000 trials — and the tornado shows it holds {m(min(p95s))}–{m(max(p95s))}
under any single challenged judgment. Production replaces the frequency and
severity inputs with internal loss history and re-runs the same engine — the
engine, the gates, and the challenge apparatus are the product; the dollars are
the demo."* If pressed on conservatism: independence counterfactual
{m(cf.get('residual_p95'))}, gen-2 lever {gen2.get('delta_p95_pct')}%, σ-sweep to
+{hi.get('delta_p95_pct')}%.

**Card 2 — "Is this trajectory real history?"**
Say: *"No — and it says so in the pixels. The current period is the real seeded
register; the prior quarters are synthesized and tagged 'prior: synthesized' on
the tile. The forecast extrapolates the corrected series. That honesty tag class
exists everywhere motion could be misread as measurement."*

**Card 3 — "You're not a national bank — why is OCC App D your biggest bucket?"**
Say: *"Because it's labeled a heightened-standards STYLE mapping, not a claim of
applicability — the applies? flag on every row says exactly that. And the
perimeter selector re-maps the view under a declared charter — national bank,
EU EMI — with the dollars recomputed as subset sums from the same trial matrix.
The determination stays reserved to Legal, exactly like materiality."*

## Do not claim

- Do not call the dollars capital numbers, risk appetite, or "our exposure."
- Do not call the attestations human sign-offs — they are demonstrator decisions;
  the chain math is real.
- Do not call the hv gap measured telemetry — it is operator-calibrated
  illustration, labeled as such.
- Do not claim production readiness — claim a transparent, challengeable,
  render-from-data methodology whose validation questions are already priced.

## If the meeting goes deep

Open `rac/validation.html` — it IS the model-validation dossier (engine spec,
sampling error, tornado, σ-sweep, judgment log, open items). The three written
questions a serious examiner will leave with are already its §6: loss-history
fit, live control testing, perimeter binding.
"""
    out = ROOT / "PRESENTER_KIT.md"
    out.write_text(kit)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
