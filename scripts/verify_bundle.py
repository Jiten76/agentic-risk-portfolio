"""
verify_bundle — ONE command that re-executes every claim this bundle can prove
about itself, so a cold reviewer trusts checks, not prose.

Round-12 external review, generalizing the round-11 OSCAL finding: "claimed
18/18, not re-executable from the bundle" applies to every self-reported number
— QA pass counts, reconciliations, headline dollars. This runner is the
consolidation: stdlib-only, run it from the bundle root:

    python3 verify_bundle.py

What it checks here: OSCAL conformance (delegates to source/oscal/
validate_shipped.py), projection count reconciliations, dashboard↔projection
agreement, the landing snapshot against the sealed projections, the QA report's
own arithmetic, the README headline against the data, and a2a card shape.

What it CANNOT check without the repo (disclosed, not hidden): byte-
reproducibility of regeneration (needs the build pipeline), a2a Ed25519
signature verification + scope reconciliation (needs the `cryptography` lib
and the AGENT_SCOPE source of truth), and the full 66/51/25 substance audits
(they re-run the apps; shipped in audits/ for reading).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASS, FAIL, NOTE = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m", "\033[33mNOTE\033[0m"
results: list[bool] = []


def check(cid: str, ok: bool, msg: str) -> None:
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def usd_m(x: float) -> str:
    return f"${x / 1e6:.1f}M"


def main() -> int:
    print(f"bundle self-verification · {HERE}")
    print("=" * 58)

    print("\nB1 · OSCAL conformance (delegates to source/oscal/validate_shipped.py)")
    r = subprocess.run([sys.executable, str(HERE / "source" / "oscal" / "validate_shipped.py")],
                       capture_output=True, text=True)
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith("Summary")]
    check("B1.1 shipped OSCAL documents validate", r.returncode == 0,
          tail[0] if tail else f"exit {r.returncode}")

    print("\nB2 · rac projection internal reconciliation")
    rac = json.loads((HERE / "projections" / "rac.projection.json").read_text())
    counts = rac["meta"]["counts"]
    findings = [f for d in rac["domains"].values() for f in d.get("findings", [])]
    check("B2.1 meta.counts.findings_total == domain contents",
          counts["findings_total"] == len(findings),
          f"{counts['findings_total']} == {len(findings)}")
    by_rag = {"red": 0, "amber": 0, "green": 0}
    for f in findings:
        by_rag[f.get("overall_rag", "green")] = by_rag.get(f.get("overall_rag", "green"), 0) + 1
    check("B2.2 red/amber/green counts reconcile",
          all(counts.get(f"findings_{k}") == v for k, v in by_rag.items()),
          f"{by_rag['red']}R/{by_rag['amber']}A/{by_rag['green']}G")

    print("\nB3 · dashboard ↔ projection agreement (render-from-data, no drift)")
    html = (HERE / "dashboards" / "rac" / "index.html").read_text()
    m = re.search(r'<script[^>]*id="projection-source"[^>]*>(.*?)</script>', html, re.S)
    emb = json.loads(m.group(1)) if m else {}
    emb_p95 = ((emb.get("sensitivity") or {}).get("baseline") or {}).get("residual_p95")
    shp_p95 = ((rac.get("sensitivity") or {}).get("baseline") or {}).get("residual_p95")
    check("B3.1 embedded projection == shipped projection (counts + headline P95)",
          bool(m) and emb.get("meta", {}).get("counts") == counts and emb_p95 == shp_p95,
          f"findings {counts['findings_total']} · P95 {usd_m(shp_p95 or 0)}")

    print("\nB4 · landing snapshot == the sealed projections it claims to copy")
    lhtml = (HERE / "dashboards" / "landing.html").read_text()
    sm = re.search(r'<script id="strip-snapshot" type="application/json">(.*?)</script>', lhtml, re.S)
    if sm:
        snap = json.loads(sm.group(1))
        by = {r_["pattern_id"]: r_ for r_ in rac.get("inherent_residual", {}).get("by_pattern", [])}
        rac_ok = all(snap["rac"].get(k) == by.get("RP-" + k[2:], {}).get("residual", {}).get("p95")
                     for k in ("rp01", "rp06", "rp13"))
        atg = json.loads((HERE / "projections" / "atg.projection.json").read_text())
        cnt = {"RE-03": 0, "RE-04": 0}
        for d in atg.get("domains", {}).values():
            for f in d.get("findings", []):
                for k in cnt:
                    if k in (f.get("finding_id") or ""):
                        cnt[k] += 1
        atg_ok = snap["atg"] == {"re03": cnt["RE-03"], "re04": cnt["RE-04"]}
        hv = json.loads((HERE / "projections" / "hv.projection.json").read_text())
        reg = hv.get("domains", {}).get("deployment_cascade", {}).get("comparison", {}).get("regimes", {})
        hv_ok = (snap["hv"]["ins"] == reg.get("risk_as_code", {}).get("metrics", {}).get("detection_time_min", {}).get("value")
                 and snap["hv"]["man"] == reg.get("traditional", {}).get("metrics", {}).get("detection_time_min", {}).get("value"))
        check("B4.1 all six snapshot values match the projections", rac_ok and atg_ok and hv_ok,
              "byte-equal" if (rac_ok and atg_ok and hv_ok) else f"rac={rac_ok} atg={atg_ok} hv={hv_ok}")
    else:
        check("B4.1 strip snapshot present in landing", False, "missing #strip-snapshot")

    print("\nB5 · QA report's own arithmetic")
    qa = json.loads((HERE / "source" / "qa" / "test_report.json").read_text())
    verdicts = [c.get("verdict") for c in qa["cases"]]
    n_pass = sum(1 for v in verdicts if v in ("PASS", "PASS_AFTER_FIX"))
    n_find = sum(1 for v in verdicts if v == "FINDING")
    s = qa["summary"]
    check("B5.1 summary counts == recounted cases",
          s.get("total") == len(verdicts) and s.get("pass") == n_pass and s.get("findings") == n_find,
          f"total {len(verdicts)} · pass {n_pass} · findings {n_find}")

    print("\nB6 · README headline == the data")
    readme = (HERE / "README.md").read_text()
    check("B6.1 the README's residual P95 appears verbatim from the projection",
          shp_p95 and usd_m(shp_p95) in readme, f"{usd_m(shp_p95 or 0)} found in prose")

    print("\nB7 · a2a sample card shape (signature verify is repo-side — disclosed)")
    issuer = json.loads((HERE / "source" / "a2a" / "issuer.json").read_text())
    cards = list((HERE / "source" / "a2a").glob("*.card.json"))
    REQ = ("schema_version", "card_id", "agent_id", "tool_scope", "issuer", "key_id", "source_status")
    shape_ok = bool(cards) and all(
        all(k in json.loads(c.read_text())["card"] for k in REQ) for c in cards)
    check("B7.1 shipped card(s) schema-complete; issuer key well-formed",
          shape_ok and re.fullmatch(r"[0-9a-f]{64}", issuer.get("public_key_hex", "")) is not None,
          f"{len(cards)} card(s) · key_id {issuer.get('key_id', '?')}")
    print(f"  [{NOTE}] B7.2 · Ed25519 verification + AGENT_SCOPE reconciliation need the repo "
          f"(cryptography lib + scope source): packages/a2a-cards/verify_cards.py, 10 gates")

    print("\nB8 · coverage ≠ effectiveness discipline (audit C24, re-run on the shipped data)")
    # Round-13 external ask: the C24 gate's only input is risk_patterns.json,
    # which ships in this bundle — so the newest discipline is cold-reviewer-
    # verifiable here, same regexes as audits/audit_v2_0a.py C24.
    raw = json.loads((HERE / "source" / "data" / "risk_patterns.json").read_text())
    EFF = re.compile(r"credited|but |misses|not caught|cannot intercept|does not stop|do not stop|"
                     r"residual|decays|pass rate|success rate|burndown|closure rate|detective|recall", re.I)
    COV = re.compile(r"coverage|completion|% |attainment|attestation", re.I)
    ctrls = [(p["id"], c) for p in raw["patterns"]
             for c in p.get("compensating_controls", {}).get("in_place", [])]
    bad_high = [f"{pid}/{c.get('name')}" for pid, c in ctrls
                if c.get("effectiveness_pct", 0) >= 90 and not EFF.search(c.get("evidence_basis", ""))]
    bad_100 = [f"{pid}/{c.get('name')}" for pid, c in ctrls if c.get("effectiveness_pct", 0) >= 100]
    bad_split = [f"{pid}/{c.get('name')}" for pid, c in ctrls
                 if COV.search(c.get("evidence_basis", "")) and not EFF.search(c.get("evidence_basis", ""))]
    cov_n = sum(1 for _, c in ctrls if COV.search(c.get("evidence_basis", "")))
    check("B8.1 no control credits 100%; every credit ≥90 carries an effectiveness rationale",
          not bad_high and not bad_100,
          f"{len(ctrls)} controls clean" if not (bad_high or bad_100) else str((bad_high + bad_100)[:3]))
    check("B8.2 every coverage-language basis carries the coverage→effectiveness split",
          not bad_split and cov_n >= 10,
          f"{cov_n}/{cov_n} split" if not bad_split else str(bad_split[:3]))
    print(f"  [{NOTE}] B8.3 · register determinism (C25) and σ-sweep↔lever reconciliation (C20.7) "
          f"re-run the generation/engine — repo-side; gates ship in audits/audit_v2_0a.py")

    print("\nB9 · IA conservation — classics ship, and the grammar provably lost nothing")
    import hashlib as _hl
    for i, (app, rep_name) in enumerate((("rac", "conservation_report.json"),
                                         ("atg", "conservation_report_atg.json"),
                                         ("hv", "conservation_report_hv.json")), start=1):
        cl = HERE / "dashboards" / app / "archive" / "classic.html"
        new = HERE / "dashboards" / app / "index.html"
        crep_p = HERE / "source" / "qa" / rep_name
        ok9 = cl.exists() and new.exists() and crep_p.exists()
        crep = json.loads(crep_p.read_text()) if crep_p.exists() else {}
        hash_ok = ok9 and crep.get("inputs", {}).get("classic_sha256") == _hl.sha256(cl.read_bytes()).hexdigest() \
            and crep.get("inputs", {}).get("new_sha256") == _hl.sha256(new.read_bytes()).hexdigest()
        check(f"B9.{i} {app}: classic shipped; conservation report PASS and hashes match the shipped files",
              ok9 and crep.get("verdict") == "PASS" and hash_ok,
              f"verdict {crep.get('verdict', 'missing')} · hashes {'match' if hash_ok else 'STALE'}")

    print("\nB10 · cross-view numeric equality — classic, workbench and read carry the SAME numbers")
    # Round-14 external finding: B9 verifies report-internal consistency, not the
    # cross-view invariant itself. This gate re-derives it: the multiset of numeric
    # LEAVES in each view's embedded projection must be identical (ia headlines are
    # strings and timestamps are string leaves, so presentation additions and build
    # clocks cannot hide a moved number — and a moved number cannot hide behind them).
    def _leaves(o, out):
        if isinstance(o, dict):
            for v in o.values():
                _leaves(v, out)
        elif isinstance(o, list):
            for v in o:
                _leaves(v, out)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            out[round(float(o), 9)] = out.get(round(float(o), 9), 0) + 1
    def _numleaf(path):
        if not path.exists():
            return None
        m2 = re.search(r'<script[^>]*id="projection-source"[^>]*>(.*?)</script>',
                       path.read_text(encoding="utf-8", errors="ignore"), re.S)
        if not m2:
            return None
        out = {}
        _leaves(json.loads(m2.group(1)), out)
        return out
    # Round-17 amendment: CONTEMPORARY views (read, and rac's validation) must
    # EQUAL index; the FROZEN classic must be a SUB-multiset of index — additive
    # analytics may add leaves after the freeze, but classic can never hold a
    # number the live views lost. The additive delta is reported, never silent.
    # r43: the reads folded into the workbenches (redirect stubs, not shipped) —
    # contemporary views are rac's validation/board; atg/hv keep only the
    # classic-subset invariant.
    for i, app in enumerate(("rac", "atg", "hv"), start=1):
        base = _numleaf(HERE / "dashboards" / app / "index.html")
        contemp = ("validation", "board") if app == "rac" else ()
        eq_ok = base is not None and all(_numleaf(HERE / "dashboards" / app / f"{v}.html") == base for v in contemp)
        cl = _numleaf(HERE / "dashboards" / app / "archive" / "classic.html")
        lost = {k: c for k, c in cl.items() if c > base.get(k, 0)} if (cl and base) else {"?": 1}
        added = (sum(base.values()) - sum(cl.values())) if (cl and base) else 0
        ok10 = eq_ok and not lost
        n = sum(base.values()) if base else 0
        check(f"B10.{i} {app}: contemporary views equal; frozen classic ⊆ index (nothing lost)",
              ok10, (f"{n:,} leaves · {'/'.join(contemp) or 'index'} == index · classic subset"
                     + (f" (+{added} additive since freeze)" if added else "")) if ok10
              else ("classic holds leaves the live views LOST" if lost else "contemporary views DIVERGE"))

    print("\nB11 · cross-BUILD numeric anchor — the numbers match the sealed baseline")
    # Round-16 external finding: B10 is within-build; nothing gated drift BETWEEN
    # releases. The baseline pins each app's leaf multiset at cut time; changing
    # numbers requires re-cutting it in the same commit (git-visible, never silent).
    base_p = HERE / "source" / "qa" / "numeric_baseline.json"
    base = json.loads(base_p.read_text()) if base_p.exists() else {}
    import hashlib as _hl2
    for i, app in enumerate(("rac", "atg", "hv"), start=1):
        cur = _numleaf(HERE / "dashboards" / app / "index.html")
        ok11, note11 = False, "baseline missing"
        if cur is not None and app in base:
            vals = sorted(v for v, c in cur.items() for _ in range(c))
            sig = _hl2.sha256(json.dumps(vals).encode()).hexdigest()
            ok11 = sig == base[app].get("leaf_multiset_sha256") and len(vals) == base[app].get("leaf_count")
            note11 = (f"{len(vals):,} leaves match the baseline" if ok11
                      else "DRIFT vs baseline — if intentional, re-cut scripts/cut_numeric_baseline.py in the same commit")
        check(f"B11.{i} {app}: numeric leaves match the cross-build baseline", ok11, note11)

    print("\nB12 · the engine's inputs travel WITH the claim — the headline is re-derivable from this delivery")
    # External HIGH (Claude): dependency_catalog.json was absent while carrying
    # ~31% of residual P95 — a stub run yielded $165.7M vs the shipped $239.3M.
    # The gate: the catalog ships, parses, and RECONCILES with the sealed
    # projection's dependency_layer (same node ids, same loss frequencies).
    cat_p = HERE / "source" / "data" / "dependency_catalog.json"
    ok12a = cat_p.exists()
    cat_nodes = {}
    if ok12a:
        try:
            cat_nodes = {n["id"]: n for n in json.loads(cat_p.read_text())["nodes"]}
        except Exception:
            ok12a = False
    check("B12.1 dependency_catalog.json ships and parses (the file behind the concentration layer)",
          ok12a, f"{len(cat_nodes)} nodes" if ok12a else "MISSING or unparseable — the headline is not re-derivable")
    proj = json.loads((HERE / "projections" / "rac.projection.json").read_text())
    dl_nodes = {n["id"]: n for n in (proj.get("dependency_layer") or {}).get("nodes") or []}
    mismatch = [nid for nid in dl_nodes
                if nid not in cat_nodes
                or (cat_nodes[nid].get("annual_freq") or {}).get("loss") != (dl_nodes[nid].get("annual_freq") or {}).get("loss")]
    ok12b = bool(dl_nodes) and not mismatch and set(cat_nodes) == set(dl_nodes)
    check("B12.2 catalog reconciles with the sealed projection's dependency layer (ids + loss frequencies)",
          ok12b, f"{len(dl_nodes)} nodes reconcile" if ok12b else f"mismatch: {mismatch[:3] or 'node sets differ'}")

    print("\nB12.3 · the AGENT estate's catalog travels too (round-30 stage)")
    try:
        acat = json.loads((HERE / "source" / "data" / "agent_dependency_catalog.json").read_text())
        atg_proj = json.loads((HERE / "projections" / "atg.projection.json").read_text())
        adl = {n["id"] for n in (atg_proj.get("agent_dependency_layer") or {}).get("nodes", [])}
        acat_ids = {n["id"] for n in acat.get("nodes", [])}
        ok123 = bool(acat_ids) and acat_ids == adl
    except Exception as e:
        ok123, acat_ids = False, set()
    check("B12.3 agent_dependency_catalog.json ships and reconciles with the atg projection's layer (ids)",
          ok123, f"{len(acat_ids)} agent nodes reconcile" if ok123 else "missing or mismatched")

    print("\nB12.4 · the aggregator passthrough travels VERBATIM (stage 4)")
    try:
        _agg = json.loads((HERE / "source" / "data" / "journey_aggregator.json").read_text())
        import hashlib as _hl
        _re_sha = _hl.sha256(json.dumps(_agg.get("payload"), sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()
        _rp = json.loads((HERE / "projections" / "rac.projection.json").read_text())
        _consumed = ((_rp.get("journey_spine") or {}).get("aggregator") or {}).get("consumed_sha256")
        ok124 = _re_sha == _agg.get("sha256") == _consumed
    except Exception:
        ok124, _re_sha = False, ""
    check("B12.4 journey_aggregator.json ships; its payload's canonical hash matches both its own seal and the projection's consumed hash",
          ok124, f"sha256 {_re_sha[:12]}… three-way equal" if ok124 else "missing or mismatched")

    print("\nB13 · ONE map on every page (r42 — the operator was lost without it)")
    _npages = list((HERE / "dashboards").rglob("*.html"))
    _missing_nav = [str(p.relative_to(HERE)) for p in _npages
                    if "/archive/" not in str(p) and "portfolio-nav" not in p.read_text(errors="replace")]
    check("B13 every shipped dashboard carries the injected navigation drawer (archive/ exempt — frozen zone + its glue)",
          not _missing_nav, f"{sum(1 for p in _npages if '/archive/' not in str(p))} pages navigable"
          if not _missing_nav else f"missing: {_missing_nav[:3]}")

    print("\nB6.2 · superseded human-anchor values appear only as HISTORY")
    # External MODERATE (Claude): the README carried 135.2 unmarked — when an
    # anchored number changes, the old value is misinformation everywhere it
    # survives without a transition marker.
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    # r29 extends the list: every value that was ever a CURRENT headline joins
    # it the round it is superseded (E4 239.3/404.4/69.6; E5 312.2/549.4/79.0/815.4).
    superseded = ("135.2", "182.4", "206.4", "239.3", "404.4", "69.6",
                  "312.2", "549.4", "79.0", "815.4")
    bad_lines = []
    for ln in readme.splitlines():
        for s in superseded:
            if f"${s}M" in ln and "→" not in ln and "was" not in ln.lower() and "historical" not in ln.lower():
                bad_lines.append(f"${s}M: {ln.strip()[:70]}")
    check("B6.2 no superseded headline value in shipped prose without a transition marker (→ / was / historical)",
          not bad_lines, "all superseded values marked as history" if not bad_lines else "; ".join(bad_lines[:2]))

    print("\nB6.4 · WORLD CONSISTENCY — every quoted dollar is current, marked as history, or a transition pair")
    # External (Claude round-32): a §0 feature sentence quoted $278.1M/+105.7% in
    # live voice while the current lever said $186.6M/+90.2% — B6.2's fixed list
    # cannot catch values it was never told about. The CLASS gate: every $X(.X)M
    # token in the README must (a) exist in the CURRENT sealed projections'
    # numeric multiset, (b) sit on a line wearing a history marker, or (c) be
    # part of a $X→$Y supersession pair. External reference constants (cited
    # benchmarks, not portfolio numbers) are allowlisted by name.
    world = set()
    def _walk(o):
        if isinstance(o, dict):
            for _vv in o.values(): _walk(_vv)
        elif isinstance(o, list):
            for _vv in o: _walk(_vv)
        elif isinstance(o, (int, float)) and abs(o) >= 1e5:
            world.add(round(abs(o) / 1e6, 1))
    for _pn in ("rac.projection.json", "atg.projection.json", "hv.projection.json"):
        try:
            _walk(json.loads((HERE / "projections" / _pn).read_text()))
        except Exception:
            pass
    import re as _re
    _MARK = _re.compile(r"\bwas\b|\bhistorical\b|\bthen\b|\bat the time\b|\bsuperseded\b|"
                        r"\bseal\b|\bre-seal|-era\b|\bprior\b", _re.I)
    _PAIR = _re.compile(r"\$\d+(?:\.\d+)?M→\$\d+(?:\.\d+)?M")
    _EXTERNAL = {9.4}  # cited benchmarks (IBM CODB 2024 US mean $9.36M rounds to 9.4)
    _viol = []
    for _ln in (HERE / "README.md").read_text(encoding="utf-8").splitlines():
        for _m in _re.finditer(r"\$(\d+(?:\.\d+)?)M\b", _ln):
            _val = round(float(_m.group(1)), 1)
            if _val in world or _val in _EXTERNAL:
                continue
            if _MARK.search(_ln) or _PAIR.search(_ln):
                continue
            _viol.append(f"${_m.group(1)}M: {_ln.strip()[:60]}")
    check("B6.4 no unmarked out-of-world dollar in shipped prose (the stale-sentence CLASS, not a list)",
          not _viol, "every quoted dollar current, marked, or paired" if not _viol else "; ".join(_viol[:3]))

    print("\n" + "=" * 58)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    # no counts here — typed totals rot (this line said 74/55/29 three rounds
    # after the audits grew); DATA/trust_board.json carries the executed counts.
    print("(repo-side only: regeneration byte-reproducibility, a2a signatures, the per-app substance audits — executed totals in DATA/trust_board.json)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
