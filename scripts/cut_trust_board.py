#!/usr/bin/env python3
"""Cut qa/trust_board.json — the tour's PROOF chapter, machine-written.

Round-21 (user: "evidently visible versus talking"): the trust machinery —
gate counts, conservation verdicts, interaction checks, numeric baselines —
must be VISIBLE, but render-from-data forbids typing '78/78' into a page.
This script EXECUTES the gates and writes what they actually returned; the
tour hydrates from this file. Re-run after any rebuild (stale counts here are
exactly as dishonest as stale hashes in a conservation report).

Run from repo root:  python3 scripts/cut_trust_board.py
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

AUDITS = [
    ("rac", ROOT / "apps/risk-as-code-agent",
     ["/Users/jitendranjoshi/code/risk-as-code-agent/.venv/bin/python3", "tools/audit_v2_0a.py"]),
    ("atg", ROOT / "apps/agent-trace-gov",
     ["/Users/jitendranjoshi/code/agent-trace-gov/.venv/bin/python3", "tools/audit_atg.py"]),
    ("hv", ROOT / "apps/hypervelocity-risk-sim",
     ["python3", "tools/audit_hv.py"]),
]


def summary_counts(text: str):
    # LAST summary line — verify_bundle echoes B1's nested OSCAL summary first
    ms = re.findall(r"Summary:\s*(\d+)\s*PASS(?:\s*·\s*(\d+)\s*WARN)?\s*·\s*(\d+)\s*FAIL\s*·\s*(\d+)\s*total", text)
    if not ms:
        return None
    m = ms[-1]
    return {"pass": int(m[0]), "fail": int(m[2]), "total": int(m[3])}


def main() -> int:
    board = {"note": ("machine-written by scripts/cut_trust_board.py — every count below is the "
                      "RESULT of executing the named gate, never typed. Re-run after rebuilds.")}

    audits = {}
    for name, cwd, cmd in AUDITS:
        env = None
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           env=dict(**__import__("os").environ, PYTHONPATH=str(cwd)))
        c = summary_counts(r.stdout)
        audits[name] = c or {"error": f"exit {r.returncode}"}
    board["audits"] = audits

    bundle_dir = ROOT / "PORTFOLIO_REVIEW"
    if (bundle_dir / "verify_bundle.py").exists():
        r = subprocess.run(["python3", "verify_bundle.py"], cwd=bundle_dir, capture_output=True, text=True)
        board["verify_bundle"] = summary_counts(r.stdout) or {"error": f"exit {r.returncode}"}
        # round-24 (GROK P2): the frozen classic is a SUBSET — surface the
        # additive delta B10 already reports, so nobody reads "conservation
        # PASS" as "classic is a perfect freeze".
        adds = dict(re.findall(r"B10\.\d (\w+):.*?\(\+(\d+) additive since freeze\)", r.stdout))
        board["classic_additive_leaves"] = {a: int(n) for a, n in adds.items()}
    else:
        board["verify_bundle"] = {"error": "bundle not built"}

    # r32 (both externals: "unfalsified gates taken on prose") — execute the
    # falsification harness: planted defects must be CAUGHT by C34/C35.
    r = subprocess.run([str(ROOT.parent / "risk-as-code-agent" / ".venv" / "bin" / "python3"),
                        "tools/test_gate_falsification.py"],
                       cwd=ROOT / "apps" / "risk-as-code-agent", capture_output=True, text=True)
    fm = re.search(r"Summary: (\d+)/(\d+)", r.stdout or "")
    board["gate_falsification"] = ({"caught": int(fm.group(1)), "trials": int(fm.group(2)),
                                    "note": "planted defects (zeroed gamma, stale note, broken attribution sum, "
                                            "out-of-range share, inflated chooser benefit, invented chooser owner) "
                                            "must FAIL their gate; clean run must PASS"}
                                   if fm and r.returncode == 0 else {"error": f"exit {r.returncode}"})

    m = json.loads((ROOT / "qa/interaction_matrix.json").read_text())
    board["interactions"] = m.get("summary", {})

    cons = {}
    for app, f in (("rac", "qa/conservation_report.json"),
                   ("atg", "qa/conservation_report_atg.json"),
                   ("hv", "qa/conservation_report_hv.json")):
        rep = json.loads((ROOT / f).read_text())
        cons[app] = {"verdict": rep.get("verdict"), "run_at": (rep.get("run_at") or "")[:10]}
    board["conservation"] = cons

    base = json.loads((ROOT / "qa/numeric_baseline.json").read_text())
    board["numeric_baseline"] = {a: base[a]["leaf_count"] for a in ("rac", "atg", "hv") if a in base}

    ledger = (ROOT / "qa/DEFECT_CLASS_LEDGER.md").read_text()
    rows = [ln for ln in ledger.splitlines() if re.match(r"\|\s*\d+\s*\|", ln)]
    # machine-gated = every class EXCEPT the explicitly non-automated ones
    gated = sum(1 for ln in rows
                if not re.search(r"NOT automatable|ACCEPTED, DISCLOSED", ln.split("|")[-2]))
    board["defect_classes"] = {"total": len(rows), "machine_gated": gated}

    out = ROOT / "qa/trust_board.json"
    out.write_text(json.dumps(board, indent=2))
    print(f"trust board cut → {out}")
    for k in ("audits", "verify_bundle", "interactions"):
        print(f"  {k}: {board[k]}")
    print(f"  conservation: {[cons[a]['verdict'] for a in cons]}")
    print(f"  defect classes: {board['defect_classes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
