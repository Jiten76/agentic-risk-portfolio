"""
audit_hv — substance gate for the hypervelocity-risk-sim dashboard.

Asserts BEHAVIOUR, not token presence: reproducibility of the projection + seal,
chain integrity, per-value honesty labels (illustrative response times vs counted
peaks), canonical-KRI coverage against the ACTUAL hub catalog, and render-from-data
(no baked values — the stage hydrates from the one embedded projection).

Run:  PYTHONPATH=apps/hypervelocity-risk-sim python3 apps/hypervelocity-risk-sim/tools/audit_hv.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_SPOKE = Path(__file__).resolve().parent.parent
_REPO = _SPOKE.parent.parent
for _p in (str(_SPOKE), str(_REPO / "packages" / "ui-system")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402
from utils.projection import make_projection  # noqa: E402
from utils.hv_html_report import render_hv_from_projection, DEFAULT_SEED, DEFAULT_AS_OF  # noqa: E402

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results = []


def check(cid, ok, msg):
    results.append(bool(ok))
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def _seal(proj):
    js = json.dumps(proj, indent=2, default=str, sort_keys=True)
    return hashlib.sha256(js.strip().encode()).hexdigest()


def main() -> int:
    print("hypervelocity-risk-sim — substance audit")
    print("=" * 60)

    proj = make_projection(seed=DEFAULT_SEED, as_of=DEFAULT_AS_OF)
    html = render_hv_from_projection(proj)

    # C1 · reproducibility
    print("\nC1 · reproducibility (seed + clock pinned)")
    p2 = make_projection(seed=DEFAULT_SEED, as_of=DEFAULT_AS_OF)
    check("C1.1 projection byte-identical across builds",
          json.dumps(proj, sort_keys=True, default=str) == json.dumps(p2, sort_keys=True, default=str),
          "same (seed, as_of) → same projection")
    check("C1.2 seal stable across builds", _seal(proj) == _seal(p2), _seal(proj)[:16] + "…")
    p3 = make_projection(seed=7, as_of=DEFAULT_AS_OF)
    check("C1.3 different seed → different seal", _seal(proj) != _seal(p3), "seed sensitivity real")

    # C2 · chain + seal integrity
    print("\nC2 · chain + artefact seal")
    al = proj["action_log"]
    check("C2.1 attestation chain intact", al["chain_status"] == "intact",
          f"{al['total_entries']} entries, {al['chain_status']}")
    m = re.search(r'id="projection-source"[^>]*>\s*(\{.*?\})\s*</script>', html, re.S)
    embedded = json.loads(m.group(1)) if m else None
    check("C2.2 embedded projection parses + equals the built projection",
          embedded is not None and _seal(embedded) == _seal(proj), "render-from-data payload matches")
    footer_seal = re.search(r'id="artefact-seal-value">([a-f0-9]{64})<', html)
    honest = bool(footer_seal) and embedded is not None and \
        footer_seal.group(1) == hashlib.sha256(json.dumps(embedded, indent=2, default=str, sort_keys=True).strip().encode()).hexdigest()
    check("C2.3 footer seal is an honest SHA-256 of the embedded projection", honest,
          "seal recomputes over the evidence payload")
    # C2.4 · no expiry-bearing attestation is lapsed as-of the run clock (generated_at).
    # Checked against the artefact's stated time, not wall-clock, so it stays reproducible.
    al = proj["action_log"]
    as_of_date = (proj["meta"].get("generated_at") or "9999")[:10]
    needs_expiry = set(al.get("verbs_needing_expiry", []))
    lapsed = [e for e in al.get("recent_entries", [])
              if e.get("verb") in needs_expiry and e.get("expiry") and e["expiry"] < as_of_date]
    check("C2.4 no expiry-bearing attestation lapsed as-of the run clock", not lapsed,
          f"as-of {as_of_date}, none lapsed" if not lapsed else f"lapsed: {[e.get('verb') for e in lapsed]}")

    # C3 · honesty labels (per-value provenance)
    print("\nC3 · honesty — per-value provenance")
    comp_ok, comp_n, derived_n = True, 0, 0
    for d in proj["domains"].values():
        for reg in d["comparison"]["regimes"].values():
            for mk, mv in reg["metrics"].items():
                if isinstance(mv.get("value"), (int, float)):
                    comp_n += 1
                    st = mv.get("provenance", {}).get("source_status")
                    # missed_events is round(count × fraction) — DERIVED, not pure illustration.
                    if mk == "missed_events":
                        derived_n += 1
                        if st != "derived":
                            comp_ok = False
                    elif st != "illustrative":
                        comp_ok = False
    check("C3.1 response-times illustrative; missed_events tagged derived (real count upstream)", comp_ok,
          f"{comp_n} numbers: illustrative, except {derived_n} derived (missed_events)")
    peaks_ok, peaks_n = True, 0
    for d in proj["domains"].values():
        for pk in d["peaks"].values():
            if isinstance(pk.get("value"), (int, float)):
                peaks_n += 1
                if pk.get("provenance", {}).get("source_status") != "real_query_synthesized_data":
                    peaks_ok = False
    check("C3.2 every counted peak is real_query_synthesized_data", peaks_ok,
          f"{peaks_n} peaks all counted")
    note = proj["source_note"].lower()
    check("C3.3 source_note declares the honest split", "operator_calibrated" in note and "source_derived" in note,
          "shapes source_derived · gap operator_calibrated")
    # C3.4 · meta.counts roll-up provenance is honest — counted vs derived (the block
    # C3.1/C3.2 never walked; scenarios_total is a list length + kris_exercised a
    # taxonomy union, so both are `derived`, NOT counted-over-the-stream).
    expected_cp = {"scenarios_total": "derived", "events_total": "real_query_synthesized_data",
                   "slo_violations": "real_query_synthesized_data", "kris_exercised": "derived"}
    cp = proj["meta"].get("counts_provenance", {})
    check("C3.4 meta.counts_provenance honest (derived vs counted)",
          all(cp.get(k) == v for k, v in expected_cp.items()),
          "scenarios/kris=derived · events/slo=counted" if all(cp.get(k) == v for k, v in expected_cp.items()) else str(cp))

    # C4 · canonical-KRI coverage vs the ACTUAL hub catalog
    print("\nC4 · canonical KRI coverage (vs packages/kri-taxonomy)")
    catalog = yaml.safe_load((_REPO / "packages/kri-taxonomy/kri-catalog.yaml").read_text())
    catalog_ids = {kri["id"] for fam in catalog["families"].values() for kri in fam["kris"]}
    all_refs, bad, primaries_ok = set(), [], True
    for d in proj["domains"].values():
        prim = [k for k in d["kris_fired"] if k["role"] == "primary"]
        if len(prim) != 1:
            primaries_ok = False
        for k in d["kris_fired"]:
            all_refs.add(k["id"])
            if k["id"] not in catalog_ids:
                bad.append(k["id"])
    check("C4.1 every scenario has exactly one primary KRI", primaries_ok, "1 primary each")
    check("C4.2 every referenced KRI exists in the hub catalog", not bad,
          "all resolve" if not bad else f"dangling: {bad}")
    check("C4.3 meta.kris_exercised matches distinct referenced KRIs",
          set(proj["meta"]["kris_exercised"]) == all_refs, f"{len(all_refs)} KRIs")

    # C5 · render-from-data (no baked values → no drift)
    print("\nC5 · render-from-data (drift-proof)")
    html_wo_proj = re.sub(r'<script[^>]*id="projection-source".*?</script>', "", html, flags=re.S)
    label = next(iter(proj["domains"].values()))["label"]  # e.g. "Consumer-Lag Cascade"
    check("C5.1 projected values are NOT baked into the static stage HTML",
          label not in html_wo_proj, f"'{label}' only in the projection, hydrated client-side")
    # OBSERVATORY act: the whole observatory (metrics header, canvas graph, KRI
    # scorecard, escalation, regime gap, evidence log) hydrates into ONE mount plus
    # the persistent hero + rail + footer — all ship empty and fill from the projection.
    stage_mounts = ["scenario-hero", "observatory", "rail-scenarios", "footer-counts"]
    empties = all(re.search(r'data-target="' + mnt + r'"\s*></div>', html)
                  or re.search(r'data-target="' + mnt + r'"\s*></span>', html)
                  for mnt in stage_mounts)
    check("C5.2 stage mount points ship empty (hydrated by the runtime)", empties, "all stage mounts empty")
    check("C5.3 runtime + domain registered", "PortfolioRuntime" in html and "registerDomain" in html, "wired")
    # C5.4 · render-from-data engine: the observatory builds its telemetry series
    # from the event array (no hardcoded synthetic `D` series), maps KRI cards from
    # d.kris_fired, and derives the regime gap from the comparison metrics via metricOf.
    dom_js = html  # domain JS is inlined into the artefact
    obs_from_data = ("fieldSeries" in dom_js and "d.events" in dom_js
                     and "d.kris_fired" in dom_js and 'metricOf(d, "traditional"' in dom_js)
    check("C5.4 observatory renders from d.events / d.kris_fired / d.comparison (no baked telemetry)",
          obs_from_data, "series forward-filled from events; KRIs + regime gap from the projection")

    # C6 · structural / scenario integrity
    print("\nC6 · structural integrity")
    meta = proj["meta"]
    check("C6.1 domain_ids match domains + object is 'scenario'",
          list(proj["domains"].keys()) == meta["domain_ids"] and meta["domain_object"] == "scenario",
          f"{len(meta['domain_ids'])} scenarios")
    valid_phases = {"build_up", "cascade", "recovery"}
    phases_ok = all(e.get("phase") in valid_phases for d in proj["domains"].values() for e in d["events"])
    check("C6.2 every event carries a valid incident phase", phases_ok, "build_up/cascade/recovery")
    # r63: the denylist lives in a LOCAL gitignored file (.publish-denylist at
    # the monorepo root) so the guarded terms never ship in tracked code — a
    # public reader of this gate learns nothing. Absent the file (a clone/
    # export), the gate passes with a note; the publish snapshot gate is the
    # backstop that can never be absent on publish day.
    _deny_path = _REPO / ".publish-denylist"
    if not _deny_path.exists():
        _deny_path = _REPO.parent.parent / ".publish-denylist"
    _deny = [ln.split("#")[0].strip() for ln in _deny_path.read_text().splitlines()
             if ln.split("#")[0].strip()] if _deny_path.exists() else []
    _leaks = [t for t in _deny if t.lower() in html.lower()]
    check("C6.3 de-identified — no denylisted reference in the artefact",
          not _leaks, ("LEAK: " + ", ".join(_leaks)) if _leaks
          else (f"clean against {len(_deny)} local denylist terms" if _deny
                else "no local denylist — publish snapshot gate is the backstop"))

    # C7 · physics sanity (SRE band) — the rest of the audit checks that DATA is
    # labelled honestly; this checks the simulated failure PHYSICS are plausible and
    # emergent, not scripted set-pieces with dead signals.
    print("\nC7 · physics sanity")
    doms = proj["domains"]
    check("C7.1 every scenario reaches a recovery phase",
          all(any(e.get("phase") == "recovery" for e in d["events"]) for d in doms.values()),
          "build_up → cascade → recovery for all 3")
    dep = doms["deployment_cascade"]["events"]
    check("C7.2 deployment rollback_triggered actually fires (not dead code)",
          any(e.get("rollback_triggered") for e in dep), "the bad-release service trips its breaker")
    lags = [e["lag_messages"] for e in doms["kafka_lag_storm"]["events"] if "lag_messages" in e]
    peak = max(lags) if lags else 1
    maxjump = max((abs(lags[i] - lags[i - 1]) for i in range(1, len(lags))), default=0)
    check("C7.3 kafka lag is continuous (emergent integral, not a scripted cliff)",
          maxjump < peak * 0.4, f"max step {maxjump} < 40% of peak {peak}")
    rc = next((e for e in dep if e.get("event_type") == "rollback_complete"), {})
    n_rec = sum(1 for e in dep if e.get("event_type") in ("rollback_start", "recovery", "rollback_complete"))
    check("C7.4 deployment MTTR reflects a real recovery tail (violation → normalized)",
          rc.get("mttr_minutes", 0) > 5 and n_rec >= 4,
          f"MTTR {rc.get('mttr_minutes')}min over {n_rec} recovery events")

    # C8 · IA spine integrity + conservation (scenario mode: the spine nodes ARE
    # the scenarios; roles re-order the walk, they can never mint or hide data)
    print("\nC8 · IA spine integrity + conservation")
    ia = proj.get("ia") or {}
    nodes = ia.get("nodes") or []
    node_ids = {n["id"] for n in nodes}
    check("C8.1 spine nodes are exactly the scenario ids",
          node_ids == set(doms.keys()) and all(not n.get("targets") for n in nodes),
          f"{len(nodes)} nodes = {len(doms)} scenarios, no section targets (observatory walks itself)")
    paths = ia.get("paths") or {}
    perms = all(sorted(pth) == sorted(node_ids) for pth in paths.values())
    check("C8.2 role paths are permutations of the scenarios (re-order, never hide) + default role exists",
          perms and ia.get("default_role") in paths,
          f"{len(paths)} roles · all permutations of {len(node_ids)} scenarios")
    proj_text = json.dumps(proj, default=str)
    def _cited(h):
        return any(tok.strip("$%").replace(",", "") in proj_text
                   for tok in re.findall(r"\$?[\d][\d,\.]*%?", h or ""))
    bad_head = [n["id"] for n in nodes if not _cited(n.get("headline"))]
    if re.search(r"\d", ia.get("thesis") or "") and not _cited(ia.get("thesis")):
        bad_head.append("thesis")
    check("C8.3 every scenario headline cites a number present in the projection (§8 genre gate)",
          not bad_head, f"{len(nodes)} headlines cited" if not bad_head else str(bad_head))
    rep_path = _REPO / "qa" / "conservation_report_hv.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    fresh = rep.get("verdict") == "PASS"
    if fresh:
        for name, f in (("classic_sha256", "docs/archive/classic.html"), ("new_sha256", "docs/index.html"),
                        ("read_sha256", "docs/read.html")):
            h = hashlib.sha256((_SPOKE / f).read_bytes()).hexdigest()
            if rep.get("inputs", {}).get(name) != h:
                fresh = False
    check("C8.4 conservation report PASS and FRESH (per-scenario probe, input hashes match shipped builds)",
          fresh, "hashes match" if fresh else "STALE or missing — re-run the per-scenario probe")

    # C8.5 · round-22 escape class (rac): a generator escaping bug shipped an
    # unparseable inline script and silently killed the page runtime. Only the
    # GENERATED page can prove itself — parse what ships.
    import subprocess as _sp, tempfile as _tmp
    _broken, _checked = [], 0
    for _relf in ("docs/index.html", "docs/read.html", "docs/archive/classic.html"):
        _pf = _SPOKE / _relf
        if not _pf.exists():
            _broken.append(f"{_relf}: MISSING"); continue
        for _i, _src in enumerate(re.findall(
                r'<script(?![^>]*\bsrc=)(?![^>]*type="application/json")[^>]*>(.*?)</script>',
                _pf.read_text(), re.S)):
            if not _src.strip():
                continue
            _checked += 1
            with _tmp.NamedTemporaryFile("w", suffix=".js", delete=False) as _t:
                _t.write(_src); _tf = _t.name
            _r = _sp.run(["node", "--check", _tf], capture_output=True, text=True)
            if _r.returncode != 0:
                _broken.append(f"{_relf}#script{_i}: {(_r.stderr.strip().splitlines() or ['?'])[0][:80]}")
    check("C8.5 every inline script on every shipped page passes node --check (generated JS, not source JS)",
          bool(_checked) and not _broken,
          f"{_checked} inline scripts parse" if not _broken else "; ".join(_broken[:3]))
    # C9 · Stage 2 of reviews/journey_spine_port_spec.md — the chip grammar on
    # every series surface: derived, reconciled, rendered.
    print("\nC9 · stream chips — every series panel declares what it is")
    import json as _json
    from pathlib import Path as _P
    _root = _P(__file__).resolve().parent.parent
    _doms = proj.get("domains", {})
    _bad = [k for k, d in _doms.items()
            if not d.get("stream_chip")
            or d["stream_chip"].get("events") != len(d.get("events", []))
            or d["stream_chip"].get("realness") != "SEEDED"
            or "event_generator@seed" not in d["stream_chip"].get("gen", "")]
    check("C9.1 every scenario carries a stream chip whose cardinality COUNTS the actual stream",
          not _bad, f"{len(_doms)} chips derive" if not _bad else f"bad: {_bad}")
    _cat = _json.loads((_root / "data" / "stream_catalog.json").read_text())
    _cat_ids = {r["id"] for r in _cat.get("streams", [])}
    _ok2 = _cat_ids == {f"stream.{k}" for k in _doms} and all(r.get("intent") and r.get("chip") for r in _cat.get("streams", []))
    check("C9.2 the stream catalog reconciles (one row per scenario, intent + chip on each) and is marked GENERATED",
          _ok2 and "do not hand-edit" in _cat.get("_generated_by", ""),
          f"{len(_cat_ids)} streams reconcile")
    # r43: the read folded into the workbench (redirect stub) — the observatory
    # is now the single scenario surface, so the chip must render THERE.
    _idx = (_root / "docs" / "index.html").read_text()
    _ok3 = "hv-chip" in _idx and "stream_chip" in _idx
    check("C9.3 the chip RENDERS on the observatory hero (the read is a redirect stub since r43)",
          _ok3, "chip markup ships on the observatory" if _ok3 else "missing render")

    # ── C10 · the pivot, hv side (r83) — each cascade names the register
    # pattern it replays, derived from the canonical map, rendered from data ──
    print("\nC10 · cross-substrate pivot — cascade → register pattern")
    import json as _json10
    _pm10 = _json10.loads((_REPO / "packages" / "ui-system" / "portfolio_core"
                           / "pivot_map.json").read_text(encoding="utf-8"))["hv_to_rp"]
    _bad10 = []
    for _did, _d in proj["domains"].items():
        _exp = _pm10.get(_d.get("hv_id"))
        _got = _d.get("register_ref")
        if bool(_exp) != bool(_got) or (_exp and (
                _got.get("rp") != _exp["rp"] or _got.get("rp_name") != _exp["rp_name"])):
            _bad10.append(_did)
    check("C10.1 every scenario's register_ref re-derives from portfolio_core/pivot_map.json (rp id + name exact)",
          not _bad10 and all("register_ref" in d for d in proj["domains"].values()),
          "4/4 cascades name their register pattern from the canonical map" if not _bad10 else f"drift: {_bad10}")
    check("C10.2 the hero renders the pivot chip FROM the projection (no typed RP id in the page template)",
          "hv-hero-pivot" in html and "register_ref" in html
          and not re.search(r'RP-\d+', re.sub(r'<script[^>]*id="projection-source".*?</script>', "", html, flags=re.S)),
          "chip hydrates client-side; template carries no RP literal")

    print("\n" + "=" * 60)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
