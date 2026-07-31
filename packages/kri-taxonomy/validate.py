"""
Validate the canonical KRI catalog + crosswalk against the spokes' ACTUAL
taxonomies. Substance-gated: asserts real coverage (every risk pattern that
exists in a spoke maps to a real canonical KRI), not mere token presence.

Run:  python3 packages/kri-taxonomy/validate.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # repo root
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results = []


def check(cid, ok, msg):
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def spoke_ids_risk_as_code() -> set:
    d = json.loads((ROOT / "apps/risk-as-code-agent/data/risk_patterns.json").read_text())
    return {p["id"] for p in d["patterns"]}


def spoke_ids_agent_trace_gov() -> set:
    s = json.loads((ROOT / "apps/agent-trace-gov/data/action_schema.json").read_text())
    return {re["id"] for re in s["risk_events"]}


def spoke_ids_hypervelocity() -> set:
    s = json.loads((ROOT / "apps/hypervelocity-risk-sim/data/risk_events.json").read_text())
    return {re["id"] for re in s["risk_events"]}


def main() -> int:
    print("canonical KRI catalog + crosswalk — validation")
    print("=" * 58)
    catalog = yaml.safe_load((HERE / "kri-catalog.yaml").read_text())
    crosswalk = yaml.safe_load((HERE / "crosswalk.yaml").read_text())

    canonical = {}
    for fam_key, fam in catalog["families"].items():
        for kri in fam["kris"]:
            canonical[kri["id"]] = fam_key

    # C1 · canonical ids unique + well-formed <FAMILY>-NN
    print("\nC1 · canonical catalog integrity")
    ids = [k["id"] for f in catalog["families"].values() for k in f["kris"]]
    check("C1.1 ids unique", len(ids) == len(set(ids)), f"{len(ids)} KRIs, {len(set(ids))} unique")
    bad_scheme = [i for i in ids if not re.match(r"^(AS|DP|PL|DR|GV)-\d{2}$", i)]
    check("C1.2 ids match <FAMILY>-NN scheme", not bad_scheme, "all well-formed" if not bad_scheme else str(bad_scheme))
    prefix_ok = all(i.split("-")[0] == fam for i, fam in canonical.items())
    check("C1.3 each id's prefix matches its family", prefix_ok, "aligned")
    fw_ok = all(k.get("frameworks") for f in catalog["families"].values() for k in f["kris"])
    check("C1.4 every KRI carries framework alignment", fw_ok, "all cited")

    # C2 · crosswalk references only real canonical KRIs
    print("\nC2 · crosswalk targets are real canonical KRIs")
    bad_targets = []
    for spoke, cfg in crosswalk["spokes"].items():
        for m in cfg["map"]:
            for tgt in [m["primary"], *m.get("also", [])]:
                if tgt not in canonical:
                    bad_targets.append(f"{spoke}:{m['from']}→{tgt}")
    check("C2.1 no crosswalk entry points at a non-existent KRI", not bad_targets,
          "all targets valid" if not bad_targets else str(bad_targets[:4]))

    # C3 · every ACTUAL spoke taxonomy id is covered by the crosswalk (no orphans)
    print("\nC3 · coverage — every real spoke pattern maps (no orphans)")
    actual = {"risk-as-code-agent": spoke_ids_risk_as_code(),
              "agent-trace-gov": spoke_ids_agent_trace_gov(),
              "hypervelocity-risk-sim": spoke_ids_hypervelocity()}
    for spoke, real_ids in actual.items():
        mapped = {m["from"] for m in crosswalk["spokes"][spoke]["map"]}
        orphans = real_ids - mapped
        check(f"C3.{spoke} every {spoke} pattern is crosswalked",
              not orphans, f"{len(real_ids)} patterns, all mapped" if not orphans else f"orphans: {sorted(orphans)}")

    # C4 · crosswalk has no phantom entries (mapping a spoke id that doesn't exist)
    print("\nC4 · no phantom crosswalk entries")
    for spoke, real_ids in actual.items():
        mapped = {m["from"] for m in crosswalk["spokes"][spoke]["map"]}
        phantom = mapped - real_ids
        check(f"C4.{spoke} no phantom {spoke} mappings",
              not phantom, "clean" if not phantom else f"phantom: {sorted(phantom)}")

    # informational — canonical KRIs no spoke maps to yet (headroom, not a failure)
    used = {m["primary"] for c in crosswalk["spokes"].values() for m in c["map"]}
    used |= {t for c in crosswalk["spokes"].values() for m in c["map"] for t in m.get("also", [])}
    unused = sorted(set(canonical) - used)
    print(f"\n  · headroom: {len(unused)} canonical KRIs not yet exercised by a spoke "
          f"({', '.join(unused) if unused else 'none'}) — capacity for new spokes")

    print("\n" + "=" * 58)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
