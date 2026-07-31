"""
Validate the emitted OSCAL — structural conformance (OSCAL 1.1.2 required fields),
cross-reference integrity (every component control-id resolves to a catalog control),
and reproducibility (regeneration is byte-identical).

Run:  python3 packages/oscal-bindings/validate.py   (runs build_oscal first)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results = []


def check(cid, ok, msg):
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def _meta_ok(m: dict) -> bool:
    return all(k in m for k in ("title", "last-modified", "version", "oscal-version"))


def main() -> int:
    # (re)build first so we validate current output
    import build_oscal
    build_oscal.main()
    print("\nOSCAL validation")
    print("=" * 58)

    cat = json.loads((DIST / "kri-catalog.oscal.json").read_text())["catalog"]
    comp = json.loads((DIST / "spokes.component-definition.oscal.json").read_text())["component-definition"]

    # C1 · catalog structural conformance
    print("\nC1 · OSCAL catalog conformance")
    check("C1.1 catalog has uuid + conformant metadata", bool(cat.get("uuid")) and _meta_ok(cat["metadata"]),
          f"oscal-version {cat['metadata'].get('oscal-version')}")
    ctrl_ids = [c["id"] for g in cat["groups"] for c in g["controls"]]
    check("C1.2 every control has id + title",
          all(c.get("id") and c.get("title") for g in cat["groups"] for c in g["controls"]),
          f"{len(ctrl_ids)} controls")
    check("C1.3 control ids unique", len(ctrl_ids) == len(set(ctrl_ids)), f"{len(set(ctrl_ids))} unique")
    check("C1.4 every control carries a framework prop",
          all(any(p["name"] == "framework" for p in c.get("props", []))
              for g in cat["groups"] for c in g["controls"]), "all framework-tagged")

    # C2 · component-definition structural conformance
    print("\nC2 · OSCAL component-definition conformance")
    check("C2.1 comp-def has uuid + conformant metadata", bool(comp.get("uuid")) and _meta_ok(comp["metadata"]),
          "ok")
    comps = comp["components"]
    check("C2.2 every component has uuid/type/title + control-implementations",
          all(c.get("uuid") and c.get("type") and c.get("title") and c.get("control-implementations")
              for c in comps), f"{len(comps)} components")

    # C3 · cross-reference integrity — every implemented control-id resolves to a catalog control
    print("\nC3 · cross-reference integrity (comp-def → catalog)")
    catalog_ids = set(ctrl_ids)
    dangling = []
    for c in comps:
        for ci in c["control-implementations"]:
            for ir in ci["implemented-requirements"]:
                if ir["control-id"] not in catalog_ids:
                    dangling.append(f"{c['title']}→{ir['control-id']}")
    check("C3.1 every implemented control-id resolves to a catalog control", not dangling,
          "all resolve" if not dangling else str(dangling[:4]))

    # C4 · reproducibility — deterministic (uuid5 + fixed timestamp)
    print("\nC4 · reproducibility")
    a = (DIST / "kri-catalog.oscal.json").read_text()
    b1 = (DIST / "spokes.component-definition.oscal.json").read_text()
    ar0 = (DIST / "findings.assessment-results.oscal.json").read_text()
    build_oscal.main()
    check("C4.1 regeneration is byte-identical (deterministic uuids + fixed clock)",
          a == (DIST / "kri-catalog.oscal.json").read_text()
          and b1 == (DIST / "spokes.component-definition.oscal.json").read_text()
          and ar0 == (DIST / "findings.assessment-results.oscal.json").read_text(), "byte-stable")

    # C5 · ISO 27001:2022 mapping — every control carries it; caveats where approximate
    print("\nC5 · ISO/IEC 27001:2022 Annex A mapping")
    iso_ok, caveats, bad_codes = 0, 0, []
    import re as _re
    for g in cat["groups"]:
        for c in g["controls"]:
            codes = [p["value"] for p in c.get("props", []) if p.get("name") == "iso-27001-2022"]
            if codes:
                iso_ok += 1
            bad_codes += [x for x in codes if not _re.fullmatch(r"A\.\d+\.\d+", x)]
            if any(p.get("name") == "iso-27001-2022-note" for p in c.get("props", [])):
                caveats += 1
    check("C5.1 every catalog control carries ≥1 ISO 27001:2022 Annex A mapping",
          iso_ok == len(ctrl_ids), f"{iso_ok}/{len(ctrl_ids)} mapped · {caveats} with honest nearest-control caveats")
    check("C5.2 Annex A codes well-formed (A.x.y)", not bad_codes, "all well-formed" if not bad_codes else str(bad_codes[:3]))

    # C5.3/4 · jurisdiction strategy — US (NYDFS/FFIEC/NIST CSF) + EU-Global (ISO
    # 27001 + cloud pair 27017/27018): every control speaks BOTH vocabularies.
    us_ok, global_cloud, bad_fmt = 0, 0, []
    FMT = {"nydfs-500": _re.compile(r"500\.\d{2}(\([a-z0-9]+\))*"),
           "nist-csf-2.0": _re.compile(r"[A-Z]{2}\.[A-Z]{2}(-\d{2})?"),
           "iso-27017": _re.compile(r"(CLD\.)?\d+(\.\d+)*"),
           "iso-27018": _re.compile(r"A\.\d+(\.\d+)?")}
    for g in cat["groups"]:
        for c in g["controls"]:
            props_by = {}
            for p in c.get("props", []):
                props_by.setdefault(p.get("name"), []).append(p["value"])
            if any(props_by.get(k) for k in ("nydfs-500", "ffiec-it-booklet", "nist-csf-2.0")):
                us_ok += 1
            if props_by.get("iso-27017") or props_by.get("iso-27018"):
                global_cloud += 1
            for name, rx in FMT.items():
                bad_fmt += [f"{c['id']}:{v}" for v in props_by.get(name, []) if not rx.fullmatch(v)]
    check("C5.3 every control carries a US mapping (NYDFS 500 / FFIEC / NIST CSF 2.0)",
          us_ok == len(ctrl_ids), f"{us_ok}/{len(ctrl_ids)} · cloud-pair (27017/18) additionally on {global_cloud}")
    check("C5.4 US + cloud-pair codes well-formed per scheme", not bad_fmt,
          "all well-formed" if not bad_fmt else str(bad_fmt[:3]))

    # C6 · assessment-results — end-to-end integrity against the rac projection
    print("\nC6 · assessment-results (end-to-end from findings)")
    ar = json.loads((DIST / "findings.assessment-results.oscal.json").read_text())["assessment-results"]
    res = ar["results"][0]
    proj = build_oscal._load_rac_projection()
    n_proj = sum(len(d.get("findings", [])) for d in proj.get("domains", {}).values())
    check("C6.1 AR findings == projection findings (nothing dropped, nothing invented)",
          len(res["findings"]) == n_proj, f"AR {len(res['findings'])} == projection {n_proj}")
    legal = {"open", "investigating", "remediating", "deviation-requested", "deviation-approved", "closed"}
    bad_status = [r["status"] for r in res["risks"] if r["status"] not in legal]
    check("C6.2 every risk status uses the OSCAL vocabulary", not bad_status,
          "all legal" if not bad_status else str(set(bad_status)))
    stmt_ids = {c["id"] + "_stmt" for g in cat["groups"] for c in g["controls"]}
    dangling_t = [f["target"]["target-id"] for f in res["findings"] if f["target"]["target-id"] not in stmt_ids]
    check("C6.3 every finding target resolves to a catalog control statement", not dangling_t,
          "all resolve" if not dangling_t else str(dangling_t[:3]))
    obs_ids = {o["uuid"] for o in res["observations"]}
    risk_ids = {r["uuid"] for r in res["risks"]}
    linked = all(f["related-observations"][0]["observation-uuid"] in obs_ids
                 and f["related-risks"][0]["risk-uuid"] in risk_ids for f in res["findings"])
    check("C6.4 finding→observation→risk links all resolve", linked, "fully linked")
    ap = json.loads((DIST / "assessment-plan.oscal.json").read_text())["assessment-plan"]
    check("C6.5 AR imports the AP; AP discloses the no-SSP simplification in remarks",
          ar["import-ap"]["href"] == "assessment-plan.oscal.json"
          and "no System Security Plan" in ap["import-ssp"].get("remarks", ""), "honest + linked")
    # Round-10 (external reviewer validated with NIST's official models and caught
    # an invalid AR): every control-selection anywhere must carry include-all or
    # include-controls — a description alone is not valid OSCAL. Shape-gated here
    # so the class cannot recur; the .oscal.json extension IS the claim.
    bad_sel = []
    for doc_name in ("assessment-plan.oscal.json", "findings.assessment-results.oscal.json"):
        doc = json.loads((DIST / doc_name).read_text())
        def walk(o, path=""):
            if isinstance(o, dict):
                if "control-selections" in o:
                    for i, sel in enumerate(o["control-selections"]):
                        if "include-all" not in sel and "include-controls" not in sel:
                            bad_sel.append(f"{doc_name}:{path}[{i}]")
                for k, v in o.items():
                    walk(v, path + "/" + k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")
        walk(doc)
    check("C6.6 every control-selection carries include-all/include-controls (official-schema shape)",
          not bad_sel, "all conformant" if not bad_sel else str(bad_sel[:2]))

    print("\n" + "=" * 58)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
