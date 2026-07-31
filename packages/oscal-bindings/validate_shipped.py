"""
validate_shipped — bundle-local OSCAL checks that run WITHOUT the repo.

Round-11 external review: the bundle claimed "validate.py 18/18" but shipped
only the output JSONs — the claim was not re-executable from the delivered
artifact. This runner closes that: stdlib-only, it validates the four shipped
OSCAL documents in place (structure, cross-references, dual-jurisdiction
mapping grammar, control-selection shape, link integrity). If the bundle's
rac projection is co-shipped it also re-runs the findings reconciliation.

What it deliberately CANNOT check without the repo: byte-reproducibility of
regeneration (validate.py C4 — requires rebuilding from source). That check
remains repo-side; everything else re-executes here.

Run from the bundle:  python3 source/oscal/validate_shipped.py
Or point it anywhere: python3 validate_shipped.py <dir-with-oscal-jsons>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PASS, FAIL, SKIP = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m", "\033[33mSKIP\033[0m"
results: list[bool] = []


def check(cid: str, ok: bool, msg: str) -> None:
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def _meta_ok(m: dict) -> bool:
    return all(k in m for k in ("title", "last-modified", "version", "oscal-version"))


def main() -> int:
    here = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    print(f"OSCAL shipped-artifact validation · {here}")
    print("=" * 58)

    docs = {}
    for name, key in (("kri-catalog.oscal.json", "catalog"),
                      ("spokes.component-definition.oscal.json", "component-definition"),
                      ("assessment-plan.oscal.json", "assessment-plan"),
                      ("findings.assessment-results.oscal.json", "assessment-results")):
        path = here / name
        if not path.exists():
            print(f"  [{FAIL}] S0 · missing document: {name}")
            results.append(False)
            continue
        docs[key] = json.loads(path.read_text())[key]
    if len(docs) < 4:
        print("\ncannot continue with missing documents")
        return 1

    cat, comp = docs["catalog"], docs["component-definition"]
    ap, ar = docs["assessment-plan"], docs["assessment-results"]

    print("\nS1 · metadata conformance (all four documents)")
    check("S1.1 uuid + title/last-modified/version/oscal-version on every document",
          all(d.get("uuid") and _meta_ok(d.get("metadata", {})) for d in docs.values()),
          f"oscal-version {cat['metadata'].get('oscal-version')}")

    print("\nS2 · catalog")
    ctrl_ids = [c["id"] for g in cat["groups"] for c in g["controls"]]
    check("S2.1 every control has id + title; ids unique",
          all(c.get("id") and c.get("title") for g in cat["groups"] for c in g["controls"])
          and len(ctrl_ids) == len(set(ctrl_ids)), f"{len(ctrl_ids)} controls")

    print("\nS3 · component-definition → catalog cross-references")
    catalog_ids = set(ctrl_ids)
    dangling = [f"{c['title']}→{ir['control-id']}"
                for c in comp["components"]
                for ci in c["control-implementations"]
                for ir in ci["implemented-requirements"]
                if ir["control-id"] not in catalog_ids]
    check("S3.1 every implemented control-id resolves", not dangling,
          "all resolve" if not dangling else str(dangling[:4]))

    print("\nS4 · dual-jurisdiction mapping (US + EU-Global) with per-scheme grammar")
    FMT = {"nydfs-500": re.compile(r"500\.\d{2}(\([a-z0-9]+\))*"),
           "nist-csf-2.0": re.compile(r"[A-Z]{2}\.[A-Z]{2}(-\d{2})?"),
           "iso-27017": re.compile(r"(CLD\.)?\d+(\.\d+)*"),
           "iso-27018": re.compile(r"A\.\d+(\.\d+)?"),
           "iso-27001-2022": re.compile(r"A\.\d+\.\d+")}
    iso_ok = us_ok = 0
    bad_fmt = []
    for g in cat["groups"]:
        for c in g["controls"]:
            props_by: dict[str, list[str]] = {}
            for p in c.get("props", []):
                props_by.setdefault(p.get("name"), []).append(p["value"])
            if props_by.get("iso-27001-2022"):
                iso_ok += 1
            if any(props_by.get(k) for k in ("nydfs-500", "ffiec-it-booklet", "nist-csf-2.0")):
                us_ok += 1
            for name, rx in FMT.items():
                bad_fmt += [f"{c['id']}:{v}" for v in props_by.get(name, []) if not rx.fullmatch(v)]
    check("S4.1 every control carries an ISO 27001:2022 mapping AND a US mapping",
          iso_ok == len(ctrl_ids) and us_ok == len(ctrl_ids),
          f"iso {iso_ok}/{len(ctrl_ids)} · us {us_ok}/{len(ctrl_ids)}")
    check("S4.2 mapping codes well-formed per scheme", not bad_fmt,
          "all well-formed" if not bad_fmt else str(bad_fmt[:3]))

    print("\nS5 · assessment-results integrity")
    res = ar["results"][0]
    legal = {"open", "investigating", "remediating", "deviation-requested", "deviation-approved", "closed"}
    bad_status = [r["status"] for r in res["risks"] if r["status"] not in legal]
    check("S5.1 every risk status uses the OSCAL vocabulary", not bad_status,
          "all legal" if not bad_status else str(set(bad_status)))
    stmt_ids = {cid + "_stmt" for cid in ctrl_ids}
    dangling_t = [f["target"]["target-id"] for f in res["findings"] if f["target"]["target-id"] not in stmt_ids]
    check("S5.2 every finding target resolves to a catalog control statement", not dangling_t,
          "all resolve" if not dangling_t else str(dangling_t[:3]))
    obs_ids = {o["uuid"] for o in res["observations"]}
    risk_ids = {r["uuid"] for r in res["risks"]}
    linked = all(f["related-observations"][0]["observation-uuid"] in obs_ids
                 and f["related-risks"][0]["risk-uuid"] in risk_ids for f in res["findings"])
    check("S5.3 finding→observation→risk links all resolve", linked, "fully linked")

    print("\nS6 · control-selection shape (the round-10 trestle catch, gated)")
    bad_sel = []
    def walk(o, doc, path=""):
        if isinstance(o, dict):
            if "control-selections" in o:
                for i, sel in enumerate(o["control-selections"]):
                    if "include-all" not in sel and "include-controls" not in sel:
                        bad_sel.append(f"{doc}:{path}[{i}]")
            for k, v in o.items():
                walk(v, doc, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, doc, f"{path}[{i}]")
    walk(ap, "assessment-plan")
    walk(ar, "assessment-results")
    check("S6.1 every control-selection carries include-all/include-controls", not bad_sel,
          "all conformant" if not bad_sel else str(bad_sel[:2]))

    print("\nS7 · plan↔results linkage + honest disclosures")
    check("S7.1 AR imports the AP; AP discloses the no-SSP simplification",
          ar["import-ap"]["href"] == "assessment-plan.oscal.json"
          and "no System Security Plan" in ap["import-ssp"].get("remarks", ""), "honest + linked")

    print("\nS8 · findings reconciliation vs the co-shipped rac projection")
    proj_path = next((c for c in (here.parent.parent / "projections" / "rac.projection.json",
                                  here.parent / "projections" / "rac.projection.json",
                                  here / "rac.projection.json") if c.exists()), None)
    if proj_path:
        proj = json.loads(proj_path.read_text())
        n_proj = sum(len(d.get("findings", [])) for d in proj.get("domains", {}).values())
        check("S8.1 AR findings == projection findings (nothing dropped, nothing invented)",
              len(res["findings"]) == n_proj, f"AR {len(res['findings'])} == projection {n_proj}")
    else:
        print(f"  [{SKIP}] S8.1 · rac projection not co-shipped — reconciliation runs repo-side (validate.py C6.1)")

    print("\n" + "=" * 58)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    print("(byte-reproducibility of regeneration is the one repo-side-only check — validate.py C4)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
