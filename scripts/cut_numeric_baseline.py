#!/usr/bin/env python3
"""Cut qa/numeric_baseline.json — the CROSS-BUILD numeric anchor (round-16, external).

B10 proves classic/index/read carry identical numeric leaves WITHIN a build; it
would pass silently if every number changed BETWEEN builds. This baseline pins
each app's numeric-leaf multiset (as a stable hash + count + the rac P95 for
humans) at release time; verify_bundle B11 recomputes from the shipped pages
and fails on drift. Changing the numbers therefore requires re-running this
script IN THE SAME COMMIT — drift becomes a git-visible decision, never a
silent slide (the same contract the conservation reports enforce for views).

Run from repo root:  python3 scripts/cut_numeric_baseline.py
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = {
    "rac": "apps/risk-as-code-agent/docs/index.html",
    "atg": "apps/agent-trace-gov/docs/index.html",
    "hv":  "apps/hypervelocity-risk-sim/docs/index.html",
}


def leaves(o, out):
    if isinstance(o, dict):
        for v in o.values():
            leaves(v, out)
    elif isinstance(o, list):
        for v in o:
            leaves(v, out)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        out.append(round(float(o), 9))


def multiset_sig(path: Path):
    m = re.search(r'<script[^>]*id="projection-source"[^>]*>(.*?)</script>',
                  path.read_text(encoding="utf-8", errors="ignore"), re.S)
    vals: list = []
    leaves(json.loads(m.group(1)), vals)
    vals.sort()
    sig = hashlib.sha256(json.dumps(vals).encode()).hexdigest()
    return sig, len(vals)


def main() -> int:
    base = {"note": ("cross-build numeric anchor — B11 compares the shipped pages against this. "
                     "If numbers deliberately change, re-run scripts/cut_numeric_baseline.py in the "
                     "SAME commit; a mismatch at verify time means silent drift.")}
    for app, rel in APPS.items():
        sig, n = multiset_sig(ROOT / rel)
        base[app] = {"leaf_multiset_sha256": sig, "leaf_count": n}
    rac_proj = json.loads((ROOT / "apps/risk-as-code-agent/outputs/v2_0a/2026-Q3_projection.json").read_text())
    base["human_anchor"] = {
        "rac_residual_p95_usd": rac_proj["exposure"]["portfolio_total"]["p95_usd"],
        "register_findings": rac_proj["meta"]["counts"]["findings_total"],
    }
    out = ROOT / "qa" / "numeric_baseline.json"
    out.write_text(json.dumps(base, indent=2))
    print(f"baseline cut → {out}")
    for app in APPS:
        print(f"  {app}: {base[app]['leaf_count']:,} leaves · {base[app]['leaf_multiset_sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
