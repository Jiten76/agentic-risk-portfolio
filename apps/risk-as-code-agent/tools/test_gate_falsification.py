#!/usr/bin/env python3
"""Gate falsification harness — r32.

Both external reviewers converged on the same challenge: C34/C35 are
"unfalsified gates taken on prose" — nobody has planted a defect and watched
them catch it. This harness does exactly that: it builds the real projection
once, then plants FOUR seeded defects (a zeroed γ block, a restored stale
'not modeled' note, a broken attribution sum, an out-of-range induced share)
into deep copies and asserts the corresponding gate FAILS on each mutant —
and PASSES on the untouched original.

A gate that cannot fail is a narrative device; this file is the proof these
four can. Run from apps/risk-as-code-agent:
    python3 tools/test_gate_falsification.py
Exit 0 = every planted defect was caught AND the clean run passes.
"""
import copy
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.audit_v2_0a as audit  # noqa: E402


def _run_gate(fn, p):
    """Run one gate function on projection dict p; return list of bool results
    (rac's results are (id, status, msg) tuples — True iff status is PASS)."""
    start = len(audit.results)
    with redirect_stdout(io.StringIO()):
        fn(p)
    return [status == audit.PASS for (_cid, status, _msg) in audit.results[start:]]


def main() -> int:
    print("gate falsification harness — planted defects must be CAUGHT")
    print("=" * 60)
    p0 = audit.load_projection()

    outcomes = []

    def trial(name, fn, mutant, expect_fail_idx):
        res = _run_gate(fn, mutant)
        caught = res[expect_fail_idx] is False
        outcomes.append(caught)
        print(f"  [{'CAUGHT' if caught else 'MISSED'}] {name} · gate results {res}")

    # 0 · control: the clean projection passes all three gates end-to-end
    clean = (_run_gate(audit.c34_model_term_visibility, p0)
             + _run_gate(audit.c35_induced_attribution, p0)
             + _run_gate(audit.c39_strategy_chooser, p0))
    clean_ok = all(clean)
    outcomes.append(clean_ok)
    print(f"  [{'PASS' if clean_ok else 'FAIL'}] control · clean projection passes C34+C35+C39 ({len(clean)} checks)")

    # 1 · zero the γ block — C34.1 must fail
    m = copy.deepcopy(p0)
    m["exposure"]["portfolio_total"]["severity_comovement"]["gamma"] = 0
    trial("defect 1: severity_comovement.gamma zeroed", audit.c34_model_term_visibility, m, 0)

    # 2 · restore the stale pre-r30 note — C34.2 must fail
    m = copy.deepcopy(p0)
    m["exposure"]["portfolio_total"]["correlation_model"]["note"] = (
        "severities remain independent lognormal draws even where counts "
        "correlate — common-shock severity correlation is not modeled"
    )
    trial("defect 2: stale 'not modeled' note restored", audit.c34_model_term_visibility, m, 1)

    # 3 · break the attribution sum — C35.2 must fail
    m = copy.deepcopy(p0)
    m["inherent_residual"]["by_pattern"][0]["attribution"]["base_mean_usd"] *= 2.0
    trial("defect 3: one pattern's base_mean_usd doubled", audit.c35_induced_attribution, m, 1)

    # 4 · out-of-range induced share — C35.1 must fail
    m = copy.deepcopy(p0)
    m["inherent_residual"]["by_pattern"][0]["attribution"]["induced_share_pct"] = 150.0
    trial("defect 4: induced_share_pct = 150", audit.c35_induced_attribution, m, 0)

    # 5 · r51: inflate the chooser's strategy benefit — C39.1 must fail (the
    #     board decision screen cannot carry a dollar its leaves don't recompute)
    m = copy.deepcopy(p0)
    m["strategy_chooser"]["strategies"][0]["benefit_p95_usd"] += 1_000_000
    trial("defect 5: strategy benefit inflated $1M", audit.c39_strategy_chooser, m, 0)

    # 6 · r51: invent an accountable exec on the chooser — C39.3 must fail
    #     (no invented accountability survives the register cross-check)
    m = copy.deepcopy(p0)
    m["strategy_chooser"]["strategies"][0]["owners"][0]["exec"] = "R. Invented · Chief Imaginary Officer"
    trial("defect 6: invented accountable exec", audit.c39_strategy_chooser, m, 2)

    print("=" * 60)
    ok = all(outcomes)
    print(f"Summary: {sum(outcomes)}/{len(outcomes)} " + ("— all planted defects caught, clean run passes" if ok else "— GATE FAILED TO CATCH A PLANTED DEFECT"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
