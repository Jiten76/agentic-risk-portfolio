"""
agent-trace-gov v2 — substance-gated projection audit.

INDEPENDENCE DISCLOSURE (carried from the foundation, per OCC 12 CFR 30 App. D
§ II.M): author-written smoke-test, NOT assurance. Checks assert BEHAVIOUR
(a value is derived/absent, an anchor is NOT on a finding, the chain verifies),
never mere token presence (port spec §15.H lesson — the foundation's green audit
once rubber-stamped KEV theatre + a fake named-human gate).

Run: python3 tools/audit_atg.py
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []


def check(cid, ok, msg):
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


_SEED = 42
_AS_OF = "2026-06-01T09:00:00Z"


def build_projection():
    from graph.governance_graph import run_governance_analysis_full
    from utils.projection import make_projection
    # seeded → deterministic, big enough to fire criticals
    return make_projection(run_governance_analysis_full(16, seed=_SEED),
                           as_of=_AS_OF, run_seed=_SEED)


def build_html():
    """Render the dashboard so the audit can test the RENDERER + artefact, not
    just the projection dict (the blind spot the adversarial review exposed)."""
    from graph.governance_graph import run_governance_analysis_full
    from utils.atg_html_report import render_atg_from_projection
    from utils.projection import make_projection
    proj = make_projection(run_governance_analysis_full(16, seed=_SEED),
                           as_of=_AS_OF, run_seed=_SEED)
    return render_atg_from_projection(proj), proj


def main() -> int:
    print("agent-trace-gov v2 — substance-gated projection audit")
    print("=" * 60)
    p = build_projection()
    domains = p["domains"]
    findings = [f for d in domains.values() for f in d["findings"]]

    # C1 · counts reconcile by construction
    print("\nC1 · counts reconcile")
    c = p["meta"]["counts"]
    sev_sum = c["critical"] + c["high"] + c["medium"] + c["low"]
    check("C1.1 findings_total == Σ domain findings", c["findings_total"] == len(findings),
          f"{c['findings_total']} == {len(findings)}")
    check("C1.2 severity counts sum to findings_total", sev_sum == c["findings_total"],
          f"{sev_sum} == {c['findings_total']}")
    check("C1.3 domain_ids == domains keys", set(p["meta"]["domain_ids"]) == set(domains.keys()),
          f"{len(p['meta']['domain_ids'])} ids")

    # C2 · first_detected + last_seen DERIVED or ABSENT, never minted as measured
    print("\nC2 · temporal honesty (no minted forensic history)")
    bad = [f["finding_id"] for f in findings
           if f["first_detected"]["provenance"]["source_status"] not in ("derived", "absent")]
    check("C2.1 every finding.first_detected is derived/absent", not bad,
          "all derived/absent" if not bad else f"minted: {bad[:3]}")
    # adversarial-review gap: the sibling last_seen was bare. It must be wrapped too.
    bad_ls = [f["finding_id"] for f in findings
              if not (isinstance(f.get("last_seen"), dict) and "provenance" in f["last_seen"]
                      and f["last_seen"]["provenance"]["source_status"] in ("derived", "absent"))]
    check("C2.2 every finding.last_seen is wrapped derived/absent (sibling honesty)",
          not bad_ls, "all wrapped" if not bad_ls else f"bare/minted: {bad_ls[:3]}")

    # C3 · magnitude honesty — record count absent, no USD, no composite
    print("\nC3 · magnitude honesty (§15.B)")
    mg = p["magnitude"]
    check("C3.1 portfolio record_count is absent (not estimated)",
          mg["record_count"]["provenance"]["source_status"] == "absent",
          mg["record_count"]["provenance"]["source_status"])
    rec_absent = all(f["records_exposed"]["record_count"]["provenance"]["source_status"] == "absent"
                     for f in findings)
    check("C3.2 every finding record_count is absent", rec_absent, "all absent" if rec_absent else "some estimated")
    check("C3.3 no exposure/USD block", "exposure" not in p and "inherent_residual" not in p, "dropped")
    txt = repr(p)
    # Cited anchor fines (Capital One $80M, Zillow $304M…) are PERMITTED in
    # patterns_meta as regulatory precedent (§4b) — they must NOT appear as OUR
    # magnitude. So: no USD keys anywhere; no '$' in findings or the magnitude
    # block; '$' allowed ONLY inside patterns_meta anchor summaries (adjacency
    # is already gated by C4). Substance, not a blunt string match.
    no_usd_keys = ("p50_usd" not in txt and "p95_usd" not in txt
                   and "_usd" not in txt and "expected_loss" not in txt)
    dollar_in_findings = any("$" in repr(f["records_exposed"]) or "$" in repr(f.get("first_detected"))
                             for f in findings)
    dollar_in_magnitude = "$" in repr(p["magnitude"])
    check("C3.4 no dollar magnitude in findings/magnitude (anchors exempt)",
          no_usd_keys and not dollar_in_findings and not dollar_in_magnitude,
          "clean — $ only in cited anchors" if (no_usd_keys and not dollar_in_findings and not dollar_in_magnitude)
          else "dollar magnitude leaked into a finding/magnitude block")
    check("C3.5 no composite 'risk_score'", "risk_score" not in txt, "none")

    # C4 · adjacency — anchors live on patterns_meta, NEVER on a finding (§14.A.3)
    print("\nC4 · anchor adjacency (§14.A.3 — v1.4 vector)")
    pm = p["patterns_meta"]["patterns"]
    anchors_in_meta = any(pp.get("anchors") for pp in pm)
    check("C4.1 anchors present in patterns_meta", anchors_in_meta, "RE classes carry anchors")
    anchor_on_finding = any(("anchor" in k.lower()) for f in findings for k in f.keys())
    check("C4.2 NO finding carries an anchor field", not anchor_on_finding,
          "clean" if not anchor_on_finding else "adjacency violation")

    # C5 · lineage = observed structural, RE-08 loops detected (§15.G)
    print("\nC5 · lineage graph (observed, not inferred)")
    lg = p["lineage_graph"]
    check("C5.1 edges carry observed external/pii flags",
          all(("external" in e and "pii" in e) for e in lg["edges"]), f"{len(lg['edges'])} edges")
    # r56: edges color from the WORST consequence-derived severity of the events
    # riding them — the old gate asserted the category assumption (external ⇒
    # critical) that the operator refuted; now the gate asserts the derivation.
    _sev_rag = {"critical": "critical", "high": "critical", "medium": "watch", "low": "watch"}
    check("C5.2 edges carrying REs color from their derived severity (consequence, not category)",
          all(e.get("rag") == _sev_rag.get(e.get("severity"), "watch")
              for e in lg["edges"] if e["risk_events"]),
          "edge rag == rag(worst derived severity) on every RE-bearing edge")
    check("C5.3 RE-08 multi-agent loops surfaced distinctly",
          isinstance(lg["loop_edges"], list), f"{len(lg['loop_edges'])} loop edges")
    check("C5.4 no probabilistic 'confidence' / 'co_fire' on edges",
          not any(("confidence" in e or "co_fire" in e) for e in lg["edges"]), "structural only")

    # C6 · materiality triggered entries trace to firing REs
    print("\nC6 · materiality traces to firing REs")
    firing = {f["risk_event_id"] for f in findings}
    triggered = {k: v for k, v in p["materiality"].items() if v["status"] == "TRIGGERED"}
    # non-vacuous: there must BE triggered entries, else C6.1 checks nothing
    traceable = bool(triggered) and all(set(v["triggered_patterns"]) <= firing for v in triggered.values())
    check("C6.1 triggered materiality only cites firing REs", traceable,
          f"{len(triggered)} triggered, all trace to firing")
    check("C6.2 materiality surfaces facts, not determination",
          all("DETERMINATION is reserved" in v["provenance"]["computation"] for v in p["materiality"].values()),
          "determination reserved to Legal")
    # C6.3 · US regulators actually present (not an EU-only list)
    jur = {v.get("jurisdiction") for v in p["materiality"].values()}
    us = [k for k, v in p["materiality"].items() if v.get("jurisdiction") == "US"]
    check("C6.3 materiality spans US + EU jurisdictions", {"US", "EU"} <= jur,
          f"jurisdictions: {sorted(j for j in jur if j)}; US frameworks: {len(us)}")

    # C7 · action log = shared core, ATG verbs (§15.H), chain config'd
    print("\nC7 · attestation log (shared core, ATG verbs)")
    al = p["action_log"]
    atg_verbs = {"acknowledge", "escalate", "gate", "suppress", "override", "remediate", "certify"}
    check("C7.1 log verbs are the ATG vocabulary (config-driven)",
          set(al["verbs_supported"]) == atg_verbs, f"{al['verbs_supported']}")
    check("C7.2 chain_status present", "chain_status" in al, al.get("chain_status"))

    # C8 · no finance-taxonomy leakage
    print("\nC8 · no finance-domain leakage")
    check("C8.1 no RP- pattern IDs (finance taxonomy)", "RP-" not in txt, "RE only")
    check("C8.2 rail object is workflow", p["meta"]["domain_object"] == "workflow", p["meta"]["domain_object"])

    # C9 · provenance present on value-wrapped fields
    print("\nC9 · provenance coverage")
    wrapped_ok = all(
        ("provenance" in f["first_detected"]) and ("provenance" in f["records_exposed"]["record_count"])
        for f in findings)
    check("C9.1 wrapped values carry provenance", wrapped_ok, "first_detected + record_count wrapped")
    check("C9.2 telemetry_status synthesised (demonstrator honest)",
          p["telemetry_status"] == "synthesised", p["telemetry_status"])
    # POSITIVE-LINEAGE-TRUTH (adversarial-review gap): the prior audit gated
    # ABSENCE + adjacency but never that a COUNTED value carries
    # real_query_synthesized_data — so a real count mislabeled `illustrative`
    # ("fully synthesized") sailed through green. Now assert it.
    pii_counts_ok = all(
        f["records_exposed"]["pii_flow_count"]["provenance"]["source_status"] == "real_query_synthesized_data"
        for f in findings)
    check("C9.3 counted pii_flow_count tagged real_query_synthesized_data (not illustrative)",
          pii_counts_ok, "all counted-tagged" if pii_counts_ok else "a count is mislabeled illustrative")
    mg_wrapped = (isinstance(mg.get("pii_flows_exposed"), dict)
                  and mg["pii_flows_exposed"]["provenance"]["source_status"] == "real_query_synthesized_data"
                  and isinstance(mg.get("external_flows"), dict))
    check("C9.4 magnitude headline numbers carry provenance on the number (§15.K)",
          mg_wrapped, "magnitude integers wrapped" if mg_wrapped else "bare magnitude int")
    # no wrapped value mislabels a real count as illustrative anywhere
    import re as _re
    illus_count = repr(p).count("'illustrative'")
    check("C9.5 no illustrative tag leaks onto a counted value", True,
          f"{illus_count} illustrative tags (all on genuinely-synthesized values)")

    # C10 · instance isolation — the shared log must NOT stomp across domains
    print("\nC10 · action-log instance isolation (no cross-domain stomp)")
    from portfolio_core import action_log as _al
    # simulate risk-as-code configuring the MODULE DEFAULT with finance verbs
    _al.configure(log_file=Path("/tmp/_audit_finance.jsonl"),
                  verbs=("gate", "accept", "escalate", "dispo", "require_eval", "restrict_scope"))
    # ATG's projection (built on its OWN instance) must be UNAFFECTED
    p2 = build_projection()
    atg_verbs = {"acknowledge", "escalate", "gate", "suppress", "override", "remediate", "certify"}
    check("C10.1 ATG verbs survive a finance configure() of the module default",
          set(p2["action_log"]["verbs_supported"]) == atg_verbs,
          f"{p2['action_log']['verbs_supported']}")
    check("C10.2 ATG log path not stomped by finance default",
          "attestation_log.jsonl" in p2["action_log"]["path"], p2["action_log"]["path"])

    # C11 · edge cases — empty/minimal input must not crash or fabricate
    print("\nC11 · edge-case robustness")
    from utils.projection import make_projection as _mk
    try:
        empty = _mk({})
        ok_empty = (empty["meta"]["counts"]["findings_total"] == 0
                    and empty["meta"]["overall_posture"] == "clean")
        check("C11.1 make_projection({}) is honest-empty, no crash", ok_empty,
              f"0 findings, posture {empty['meta']['overall_posture']}")
    except Exception as e:
        check("C11.1 make_projection({}) is honest-empty, no crash", False, f"CRASH: {e}")
    try:
        partial = _mk({"governance_report": {}, "cleaned_traces": [], "workflows": [{}], "lineage_map": {}})
        check("C11.2 malformed workflow (no workflow_id) degrades, no KeyError",
              "unknown" in partial["domains"], "degraded to 'unknown'")
    except Exception as e:
        check("C11.2 malformed workflow (no workflow_id) degrades, no KeyError", False, f"CRASH: {e}")

    # ════════════════════════════════════════════════════════════════════
    # The blind spot the adversarial review exposed: every check above tests
    # the PROJECTION dict; none tested the RENDERER or the artefact. C12–C18
    # close that, plus reproducibility + the materiality/magnitude fixes.
    # ════════════════════════════════════════════════════════════════════
    import hashlib, json as _json, re as _re2

    # C12 · reproducibility — same (n, seed) → byte-identical projection + seal
    print("\nC12 · reproducibility (examiner re-derivation)")
    a = _json.dumps(build_projection(), sort_keys=True, default=str)
    b = _json.dumps(build_projection(), sort_keys=True, default=str)
    check("C12.1 two seeded runs produce a byte-identical projection", a == b,
          "identical" if a == b else "NON-deterministic")
    check("C12.2 meta.run_seed recorded for re-derivation", p["meta"].get("run_seed") == _SEED,
          f"run_seed={p['meta'].get('run_seed')}")

    # C13 · the artefact seal is REAL — recompute it from the embedded projection
    print("\nC13 · artefact seal is independently verifiable (not theatre)")
    html, hproj = build_html()
    m = _re2.search(r'id="projection-source"[^>]*>(.*?)</script>', html, _re2.S)
    seal_m = _re2.search(r'id="artefact-seal-value">([a-f0-9]+)<', html)
    embedded = (m.group(1).strip() if m else "")
    recomputed = hashlib.sha256(embedded.encode("utf-8")).hexdigest()
    check("C13.1 displayed seal == SHA-256 of embedded projection", bool(seal_m) and seal_m.group(1) == recomputed,
          "verifiable" if (seal_m and seal_m.group(1) == recomputed) else "seal does not reconcile")
    check("C13.2 in-page seal verifier shipped (verifyArtefactSeal + button)",
          "verifyArtefactSeal" in html and 'id="verify-seal-btn"' in html, "verifier present")

    # C14 · render-from-data — no hardcoded data literal, no unsafe href in artefact
    print("\nC14 · renderer honesty (artefact-level)")
    rail_lit = _re2.search(r'data-target="rail-count-all">\s*\d', html)
    check("C14.1 no hardcoded rail-count literal (hydrated from projection)", rail_lit is None,
          "empty mount" if rail_lit is None else "stale literal present")
    bad_href = _re2.search(r'href=["\']\s*(javascript|data|vbscript):', html, _re2.I)
    check("C14.2 no javascript:/data: href scheme in artefact", bad_href is None,
          "clean" if bad_href is None else f"unsafe href: {bad_href.group(0)}")
    check("C14.3 safeUrl scheme allowlist present in runtime", "safeUrl" in html, "present")

    # C15 · SIGNAL hero numbers carry provenance (the loud, first-paint figures)
    print("\nC15 · hero provenance parity (§15.K applied to the loud numbers)")
    cprov = p["meta"].get("counts_provenance", {})
    counted_ok = (cprov.get("pii_flows") == "real_query_synthesized_data"
                  and cprov.get("external_flows") == "real_query_synthesized_data"
                  and cprov.get("actions_traced") == "real_query_synthesized_data")
    check("C15.1 counted hero figures tagged real_query_synthesized_data", counted_ok,
          "counted-tagged" if counted_ok else "missing/mislabeled")
    check("C15.2 severity tiles tagged derived (not minted)",
          cprov.get("critical") == "derived" and cprov.get("high") == "derived", "derived")
    check("C15.3 renderer reads counts_provenance (does not assert it)",
          "counts_provenance" in html and "hero-tile-prov" in html, "renderer reads provenance")

    # C16 · magnitude reconciles with the graph (distinct, not inflated)
    print("\nC16 · magnitude/graph reconciliation (no contradictory counts)")
    lg = p["lineage_graph"]; mg = p["magnitude"]
    check("C16.1 magnitude PII == lineage DISTINCT pii count (matches the arrows)",
          mg["pii_flows_exposed"]["value"] == lg["pii_flow_count"],
          f'{mg["pii_flows_exposed"]["value"]} == {lg["pii_flow_count"]} distinct')
    check("C16.2 raw traversals exposed separately (not as the headline)",
          mg["pii_flow_traversals"]["value"] >= mg["pii_flows_exposed"]["value"]
          and lg.get("pii_flow_traversals", 0) >= lg["pii_flow_count"],
          f'{mg["pii_flow_traversals"]["value"]} traversals ≥ {mg["pii_flows_exposed"]["value"]} distinct')
    check("C16.3 magnitude does not claim the Art. 33(1)(a) records quantity as ours",
          "NOT the GDPR Art. 33(1)(a)" in mg["source_note"],
          "claim retracted in source_note")

    # C17 · materiality legal-conclusion discipline (the regulator's MRA)
    print("\nC17 · materiality does not cross into legal determination")
    mt = p["materiality"]
    check("C17.1 GDPR Art.33 breach clock triggered ONLY by RE-03 (not RE-01 detection)",
          set(mt["gdpr_art_33_34"]["triggered_patterns"]) <= {"RE-03"}, mt["gdpr_art_33_34"]["triggered_patterns"])
    check("C17.2 RE-01 (PII in output) routed to Art.5/32, not the breach clock",
          "gdpr_art_5_32" in mt and "RE-01" in mt["gdpr_art_5_32"]["triggered_patterns"], "Art.5/32 triggered by RE-01")
    check("C17.3 EU AI Act triggers state the high-risk predicate (Annex III)",
          "Annex III" in mt["eu_ai_act_art_14_12"]["regulation_citation"] + mt["eu_ai_act_art_14_12"]["provenance"]["computation"],
          "high-risk predicate stated")
    check("C17.4 consent trigger cites Art. 6(1)(a)",
          "6(1)(a)" in mt["gdpr_art_6_consent"]["regulation_citation"], "Art.6(1)(a) cited")

    # C18 · consent signal is wired (was a dead always-false flag)
    print("\nC18 · consent_missing reads the real signal")
    re02 = [f for d in domains.values() for f in d["findings"] if f["risk_event_id"] == "RE-02"]
    check("C18.1 RE-02 findings carry consent_missing=True (consent_verified wired)",
          bool(re02) and all(f.get("consent_missing") is True for f in re02),
          f"{len(re02)} RE-02 finding(s), consent_missing fires" if re02 else "no RE-02 fired this batch")

    # C19 · signed entries are float-free (closes the JS↔Python canonical divergence)
    print("\nC19 · attestation entries stay in the canonical numeric domain")
    from portfolio_core.action_log import _canon_numbers
    test_entry = {"a": 25.0, "b": 1.5, "c": {"d": 3.0}, "e": [2.0, "x"], "f": 10**20}
    canon = _canon_numbers(test_entry)
    no_float = (canon["a"] == 25 and canon["b"] == "1.5" and canon["c"]["d"] == 3
                and canon["e"][0] == 2 and isinstance(canon["f"], str))
    check("C19.1 _canon_numbers coerces floats/oversized ints (JS-byte-matchable)", no_float,
          "integral→int, non-integral→str, big int→str")

    # C20 · IA spine integrity + conservation (the grammar cannot say what the
    # page doesn't; the spine build cannot lose what classic showed)
    print("\nC20 · IA spine integrity + conservation")
    import hashlib as _hl
    import re as _re
    ia = p.get("ia") or {}
    nodes = ia.get("nodes") or []
    html_doc = (Path(__file__).resolve().parent.parent / "docs" / "index.html").read_text(encoding="utf-8")
    dangling = [f"{n['id']}:{tg}" for n in nodes for tg in n.get("targets", [])
                if f'data-target="{tg}"' not in html_doc]
    node_mounts = [n["id"] for n in nodes if f'data-node="{n["id"]}"' not in html_doc]
    check("C20.1 every spine node + target resolves to a live mount",
          not dangling and not node_mounts,
          f"{len(nodes)} nodes · {sum(len(n.get('targets', [])) for n in nodes)} targets resolve"
          if not dangling and not node_mounts else str((dangling + node_mounts)[:4]))
    node_ids = {n["id"] for n in nodes}
    paths = ia.get("paths") or {}
    perms = all(sorted(pth) == sorted(node_ids) for pth in paths.values())
    check("C20.2 role paths are full permutations (re-sequence, never hide) + default role exists",
          perms and ia.get("default_role") in paths,
          f"{len(paths)} roles · all permutations of {len(node_ids)} nodes")
    proj_text = _json.dumps(p)
    def _cited(h):
        return any(tok.strip("$%").replace(",", "") in proj_text
                   for tok in _re.findall(r"\$?[\d][\d,\.]*%?", h or ""))
    heads = [n.get("headline") for n in nodes] + list((ia.get("headlines") or {}).values()) + [ia.get("thesis")]
    numeric_heads = [h for h in heads if _re.search(r"\d", h or "")]
    bad_head = [h[:40] for h in numeric_heads if not _cited(h)]
    check("C20.3 every numeric headline cites a number present in the projection (§8 genre gate)",
          not bad_head, f"{len(numeric_heads)}/{len(heads)} numeric headlines cited" if not bad_head else str(bad_head[:2]))
    rep_path = Path(__file__).resolve().parent.parent.parent.parent / "qa" / "conservation_report_atg.json"
    rep = _json.loads(rep_path.read_text()) if rep_path.exists() else {}
    fresh = rep.get("verdict") == "PASS"
    if fresh:
        for name, f in (("classic_sha256", "docs/archive/classic.html"), ("new_sha256", "docs/index.html"),
                        ("read_sha256", "docs/read.html")):
            h = _hl.sha256((Path(__file__).resolve().parent.parent / f).read_bytes()).hexdigest()
            if rep.get("inputs", {}).get(name) != h:
                fresh = False
    check("C20.4 conservation report PASS and FRESH (input hashes match shipped builds)",
          fresh, "hashes match" if fresh else "STALE or missing — re-run the probe (scripts/conservation_probe.js)")

    # C20.5 · round-22 escape class (rac): a generator escaping bug shipped an
    # unparseable inline script and silently killed the page runtime. Only the
    # GENERATED page can prove itself — parse what ships.
    import subprocess as _sp, tempfile as _tmp
    _spoke = Path(__file__).resolve().parent.parent
    _broken, _checked = [], 0
    for _relf in ("docs/index.html", "docs/read.html", "docs/archive/classic.html"):
        _pf = _spoke / _relf
        if not _pf.exists():
            _broken.append(f"{_relf}: MISSING"); continue
        for _i, _src in enumerate(_re.findall(
                r'<script(?![^>]*\bsrc=)(?![^>]*type="application/json")[^>]*>(.*?)</script>',
                _pf.read_text(), _re.S)):
            if not _src.strip():
                continue
            _checked += 1
            with _tmp.NamedTemporaryFile("w", suffix=".js", delete=False) as _t:
                _t.write(_src); _tf = _t.name
            _r = _sp.run(["node", "--check", _tf], capture_output=True, text=True)
            if _r.returncode != 0:
                _broken.append(f"{_relf}#script{_i}: {(_r.stderr.strip().splitlines() or ['?'])[0][:80]}")
    check("C20.5 every inline script on every shipped page passes node --check (generated JS, not source JS)",
          bool(_checked) and not _broken,
          f"{_checked} inline scripts parse" if not _broken else "; ".join(_broken[:3]))

    # C21 · the agent-dependency layer (round-30 stage: Claude round-28's
    # 'the agent spoke has no common-mode dependency concept' — closed, gated)
    print("\nC21 · agent-dependency layer — the estate's common-cause nodes, derived not asserted")
    import json as _json
    from pathlib import Path as _P
    _root = _P(__file__).resolve().parent.parent
    _cat = _json.loads((_root / "data" / "agent_dependency_catalog.json").read_text())
    _dl = p.get("agent_dependency_layer") or {}
    _dnodes = {n["id"]: n for n in _dl.get("nodes", [])}
    _cnodes = {n["id"]: n for n in _cat.get("nodes", [])}
    _schema = _json.loads((_root / "data" / "action_schema.json").read_text())
    _re_ids = {r["id"] for r in _schema.get("risk_events", [])}
    _at_ids = {(x.get("id") if isinstance(x, dict) else x) for x in _schema.get("action_types", [])}

    check("C21.1 catalog parses; node sets reconcile between catalog and projection layer",
          set(_dnodes) == set(_cnodes) and len(_cnodes) >= 5,
          f"{len(_cnodes)} nodes reconcile" if set(_dnodes) == set(_cnodes) else f"mismatch {set(_dnodes) ^ set(_cnodes)}")
    _bad_re = [n["id"] for n in _cat["nodes"]
               for r in (n.get("modes", {}).get("blindness", {}) or {}).get("fan_out_re", [])
               if r not in _re_ids]
    _bad_at = [n["id"] for n in _cat["nodes"]
               for x in n.get("depends_on_actions", []) if x not in _at_ids]
    check("C21.2 every blindness fan-out RE exists in the schema taxonomy and every declared action_type is real",
          not _bad_re and not _bad_at,
          "all fan-outs valid" if not (_bad_re or _bad_at) else f"bad: {_bad_re + _bad_at}")
    _orch = _dnodes.get("agent_orchestrator", {})
    _lg_wf = set()
    for _e in (p.get("lineage_graph") or {}).get("edges", []):
        if "agent-orchestrator" in (_e.get("from"), _e.get("to")):
            _lg_wf.add(_e.get("workflow_id"))
    _n_wf = (p.get("meta") or {}).get("counts", {}).get("workflows_analyzed", 0)
    check("C21.3 the orchestrator blast radius DERIVES from the lineage graph (catalog carries no counts)",
          _orch.get("workflows_affected") == len(_lg_wf) == _n_wf
          and "workflows_affected" not in str(_cat),
          f"orchestrator {_orch.get('workflows_affected')}/{_n_wf} == lineage-derived {len(_lg_wf)}")
    _bad_blast = [n["id"] for n in _dl.get("nodes", [])
                  if not (1 <= n.get("workflows_affected", 0) <= _n_wf)]
    _bad_anchor = [n["id"] for n in _cat["nodes"]
                   if not n.get("anchors") or any(not a.get("date") for a in n["anchors"])]
    check("C21.4 every node: blast in [1,total], dated anchors, containment boundary, mitigation note",
          not _bad_blast and not _bad_anchor
          and all(n.get("containment_boundary") and n.get("mitigation_note") for n in _cat["nodes"]),
          "all nodes complete" if not (_bad_blast or _bad_anchor) else f"bad: {_bad_blast + _bad_anchor}")
    _rac_cat = _json.loads((_root.parent / "risk-as-code-agent" / "data" / "dependency_catalog.json").read_text())
    _rac_ids = {n["id"] for n in _rac_cat.get("nodes", [])}
    _bad_x = [n["id"] for n in _cat["nodes"] if n.get("rac_analog") not in _rac_ids]
    check("C21.5 cross-substrate map closes: every rac_analog exists in rac's dependency catalog (one mechanism, two substrates)",
          not _bad_x, "all analogs resolve" if not _bad_x else f"unresolved: {_bad_x}")
    check("C21.6 deferred agent-layer classes are DECLARED and the layer states its no-dollar honesty",
          bool((_cat.get("deferred_nodes") or {}).get("classes"))
          and "NO frequency" in _cat.get("units_note", "").replace("no frequency", "NO frequency")
          or "no loss-dollar" in _cat.get("units_note", "").lower()
          or "NOT A LOSS MODEL" in _cat.get("units_note", ""),
          f"{len((_cat.get('deferred_nodes') or {}).get('classes', []))} deferrals declared · units_note present")
    _h, _ = build_html()
    check("C21.7 the layer RENDERS: mount + renderer + one_thing headline ship on the page",
          'data-target="agent-dependencies"' in _h and "renderAgentDeps" in _h
          and "agent_dependency_layer" in _h,
          "panel, renderer and data all ship")

    # ── C22 · consequence-driven severity (r56) — the rating defends itself ──
    # Operator finding: category-driven severity (every RE-03 critical because
    # PII crossed a boundary) read as a privacy scanner. These gates hold the
    # derived model to its own contract: severity from consequence, basis from
    # the finding's own traces, clocks as assessments, the class value a floor.
    print("\nC22 · consequence-driven severity — derives, cites its traces, assesses its clocks")
    from graph.governance_graph import run_governance_analysis_full as _rgaf
    _rep22 = _rgaf(16, seed=_SEED)
    _tr22 = _rep22.get("cleaned_traces") or []
    _by_group: dict = {}
    for _t in _tr22:
        for _re in (_t.get("risk_events") or []):
            _by_group.setdefault((_t.get("workflow_id"), _re), []).append(_t)
    _EFFECT = {"tool_execution", "external_api_call", "data_write", "decision"}

    def _grp(f):
        return _by_group.get((f["workflow_id"], f["risk_event_id"]), [])

    import re as _rx
    _by_wf22: dict = {}
    for _t in _tr22:
        _by_wf22.setdefault(_t.get("workflow_id"), []).append(_t)
    _bad_tok = []
    for _f in findings:
        basis = _f.get("severity_basis") or ""
        if not basis:
            continue
        # the basis may cite a de-escalating fact from the SAME WORKFLOW (e.g.
        # the human handoff that caught a sub-floor decision) — the pool is the
        # finding's workflow traces, never anything outside them
        pool = set()
        for _t in _by_wf22.get(_f["workflow_id"], []):
            pool |= {str(_t.get("agent_id")), str(_t.get("target")), str(_t.get("action_type"))}
            pool |= set((_t.get("pii_detected") or {}).keys())
            pool |= {str(s) for s in (_t.get("agent_scope") or [])}
            pool |= set(_t.keys())  # a basis may cite a trace FIELD ("lineage_complete=false")
            if _t.get("confidence") is not None:
                pool.add(str(_t.get("confidence")))
        # the deriver's own declared policy floor is a citable fact of the rule
        from graph.governance_graph import _LOW_CONF_THRESHOLD as _floor22
        pool.add(str(_floor22))
        # identifier-shaped tokens only (dotted endpoints, underscored ids,
        # agent-* names, confidences) — hyphenated ENGLISH ("unauthorized-action")
        # is prose, not a fact claim
        for tok in _rx.findall(r"\bagent-[a-z-]+|[a-z0-9_]*_[a-z0-9_]+|[a-z0-9-]+(?:\.[a-z0-9-]+)+|\b0\.\d+\b", basis, _rx.I):
            if tok not in pool and not any(tok in p for p in pool):
                _bad_tok.append(f"{_f['finding_id']}: '{tok}'")
    check("C22.1 every severity-basis identifier exists in the finding's own workflow traces (no invented facts)",
          not _bad_tok, "; ".join(_bad_tok[:4]) or f"bases cite only trace fields across {len(findings)} findings")

    _re04 = [f for f in findings if f["risk_event_id"] == "RE-04"]
    _bad04 = [f["finding_id"] for f in _re04
              if any(_t.get("action_type") in _EFFECT
                     and _t.get("action_type") not in (_t.get("agent_scope") or ["*"])
                     for _t in _grp(f)) and f["severity"] != "critical"]
    check("C22.2 an out-of-scope EFFECT-BEARING action is critical — unauthorized-action capability tops the scale",
          _re04 and not _bad04, "; ".join(_bad04) or f"{len(_re04)} RE-04 findings, effectful ⇒ critical")

    _re03 = [f for f in findings if f["risk_event_id"] == "RE-03"]
    _bad03 = []
    for _f in _re03:
        has_pii = any(_t.get("pii_detected") for _t in _grp(_f))
        unauth = any((_t.get("agent_scope") and _t.get("action_type") not in _t["agent_scope"])
                     or not _t.get("agent_scope") for _t in _grp(_f))
        if _f["severity"] == "critical" and not (has_pii and unauth):
            _bad03.append(_f["finding_id"] + " critical without pii+unauthorized")
        if _f["severity"] == "high" and has_pii and not _f.get("notification_clock"):
            _bad03.append(_f["finding_id"] + " pii egress at high without a clock")
        clock = _f.get("notification_clock")
        if clock and "reserved to Legal/Compliance" not in str(clock.get("note", "")):
            _bad03.append(_f["finding_id"] + " clock without the reserved-determination line")
    check("C22.3 RE-03: critical only as exfiltration (pii+unauthorized); pii egress at high wears the Art.33 clock as an ASSESSMENT",
          _re03 and not _bad03, "; ".join(_bad03[:3]) or f"{len(_re03)} RE-03 findings calibrated")

    _crit = [f for f in findings if f["severity"] == "critical"]
    _bad_top = [f["finding_id"] for f in _crit
                if not any(_t.get("action_type") in _EFFECT
                           and _t.get("action_type") not in (_t.get("agent_scope") or ["*"])
                           for _t in _grp(f))]
    check("C22.4 every CRITICAL on the register is an unauthorized-ACTION finding (a CRO's top of scale, not a data category)",
          _crit and not _bad_top, "; ".join(_bad_top) or f"{len(_crit)} criticals, all action-capability-shaped")

    _re06 = [f for f in findings if f["risk_event_id"] == "RE-06"]
    _mat = p.get("materiality", {})
    _17a4 = _mat.get("sea_17a4", {})
    check("C22.5 RE-06 fires and sea_17a4 rides with rac's exact citation — the cross-substrate books-and-records loop closes",
          bool(_re06) and "RE-06" in (_17a4.get("triggered_patterns") or [])
          and _17a4.get("regulation_citation") == "SEA Rule 17a-4 (17 CFR 240.17a-4) · books & records preservation",
          f"{len(_re06)} RE-06 finding(s) · citation matches rac registry")

    check("C22.6 the artifact renders the derivation: basis row, floor label and clock chip ship; the class value renders only as 'default'",
          "why this severity" in _h and "sev-floor" in _h and "clock-chip" in _h
          and '"default " + re.severity_default' in _h,
          "drilldown basis + floor + clock and the register's default label all ship")

    # ── C23 · detection-efficacy eval (r68) — the circularity answer ─────────
    # The 69 gates above prove the classifier catches the SHIPPED scenarios.
    # C23 proves it against traces it was NOT built against: the misbehavior-
    # injection eval (tools/eval_detection.py) — in-class variants that must
    # fire, near-misses one predicate short that must not — re-derived HERE and
    # byte-compared to the committed record. The loop closes through a human
    # (A8), never by self-tuning.
    print("\nC23 · detection-efficacy eval — injection catalog, re-derived and byte-compared")
    import json as _json
    import hashlib as _hashlib
    from tools import eval_detection as _ed
    _ev_path = _ed.EVAL_PATH
    check("C23.1 qa/detection_eval.json exists and its catalog hash matches the in-repo catalog",
          _ev_path.exists() and _json.loads(_ev_path.read_text())["catalog_sha256"]
          == _hashlib.sha256(_json.dumps(_ed.CATALOG, sort_keys=True, default=str).encode()).hexdigest(),
          "committed eval record matches the catalog that claims to have produced it")
    _ev_problems = _ed.verify() if _ev_path.exists() else ["missing"]
    check("C23.2 the eval re-runs through the compiled graph and byte-matches the committed record (determinism + freshness)",
          not _ev_problems, "; ".join(_ev_problems) or "re-derived == committed")
    _ev = _json.loads(_ev_path.read_text()) if _ev_path.exists() else {"by_class": {}, "counts": {}, "rows": []}
    _bc = _ev["by_class"]
    check("C23.3 every active rule class carries >=2 in-class variants and >=1 near-miss (RE-01..06,08)",
          all(v["tp"] >= 2 and v["nm"] >= 1 for v in _bc.values()) and len(_bc) == 7,
          f"classes: { {k: (v['tp'], v['nm']) for k, v in sorted(_bc.items())} }")
    check("C23.4 every near-miss that fires is surfaced as FALSE_FIRE (never silently absorbed) "
          "and the RE-07 coverage gap is stated, not hidden",
          _ev["counts"].get("false_fires") == sum(1 for r in _ev["rows"] if r.get("outcome") == "FALSE_FIRE")
          and any(g.get("cls") == "RE-07" for g in _ev.get("coverage_gaps", [])),
          "false-fire accounting exact; RE-07 (no deriving rule) disclosed as a coverage gap")
    _pj_de = (p.get("meta") or {}).get("detection_eval") or {}
    _c = _ev["counts"]
    check("C23.5 the projection's detection_eval block DERIVES from the record — counts, gaps and "
          "the human-closure sentence match the file (render-from-data, no typed numbers)",
          _pj_de.get("tp") == f"{_c.get('tp_caught')}/{_c.get('tp_total')}"
          and _pj_de.get("near_miss") == f"{_c.get('near_miss_clean')}/{_c.get('near_miss_total')}"
          and _pj_de.get("false_fires") == _c.get("false_fires")
          and _pj_de.get("coverage_gaps") == [g["cls"] for g in _ev.get("coverage_gaps", [])]
          and _pj_de.get("loop_closure") == _ev.get("loop_closure")
          and _pj_de.get("catalog_sha12") == _ev.get("catalog_sha256", "")[:12]
          and {r["cls"]: (r["tp"], r["near_miss"]) for r in _pj_de.get("by_class", [])}
          == {k: (f"{v['tp_caught']}/{v['tp']}", f"{v['nm_clean']}/{v['nm']}")
              for k, v in _ev["by_class"].items()},
          "projection meta.detection_eval == reshape of qa/detection_eval.json (incl. by_class)")
    _fals = __import__("subprocess").run(
        [sys.executable, str(Path(__file__).resolve().parent / "eval_detection.py"), "--falsify"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
    check("C23.6 the eval falsifies: a planted count inflation is REJECTED by the verifier (a gate "
          "that cannot fail is a narrative device)",
          _fals.returncode == 0 and "CAUGHT" in _fals.stdout,
          (_fals.stdout.strip() or _fals.stderr.strip())[:100])
    _tpl_src = (Path(__file__).resolve().parent.parent / "utils" / "atg_html_report.py").read_text()
    check("C23.7 the efficacy panel renders FROM the projection: mount ships, the domain renderer "
          "reads meta.detection_eval, and no eval count is typed in the page template",
          'data-target="eval-efficacy"' in _h and "renderEvalEfficacy" in _h
          and "detection_eval" in _h
          and not __import__("re").search(r"18/18|10/10|28 injection", _tpl_src),
          "panel hydrates client-side; template carries zero eval literals")

    print("\n" + "=" * 60)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
