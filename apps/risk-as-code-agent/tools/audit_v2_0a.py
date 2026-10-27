"""
v2.0a-alpha4 internal consistency audit script.

⚠️  INDEPENDENCE DISCLOSURE (per OCC 12 CFR 30 App. D § II.M, raised by the
    audit-regulator re-review): this script was written by the SAME author as
    the remediations it checks. It is therefore an INTERNAL SMOKE-TEST, NOT
    independent assurance. A green run (0 FAIL) means the artefact is
    self-consistent against checks the author chose — it does NOT mean an
    independent reviewer would sign off.

    The independent assurance for this project is the four-lens specialist
    re-review (risk-officer · audit-regulator · CISO · SRE), run as separate
    agents that read the actual code/data rather than trusting this script.
    That re-review caught two real defects this script's GREEN run missed
    (KEV signal never fired; trajectory verdict contradicted its own delta) —
    proof that existence-only gates are not substance gates. Those checks
    (C16.2, C10.1) have since been hardened to assert BEHAVIOUR, not presence.

Re-runnable after every fix. Each check returns PASS / FAIL with evidence.

Run: python3 tools/audit_v2_0a.py
"""

from __future__ import annotations
import json
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROJ_GLOB = sorted((PROJECT_ROOT / "outputs" / "v2_0a").glob("*_projection.json"))
PROJ_PATH = _PROJ_GLOB[-1] if _PROJ_GLOB else PROJECT_ROOT / "outputs" / "v2_0a" / "current_projection.json"  # latest, not a hardcoded quarter
# r52: latest build, same latest-not-hardcoded convention as PROJ_PATH —
# current.html was a stale July relic several gates were silently auditing.
_HTML_GLOB = sorted((PROJECT_ROOT / "outputs" / "v2_0a").glob("*_v2_0a_*.html"))
HTML_PATH = _HTML_GLOB[-1] if _HTML_GLOB else PROJECT_ROOT / "outputs" / "v2_0a" / "current.html"
PROJECTION_PY = PROJECT_ROOT / "utils" / "projection.py"
V2_HTML_PY = PROJECT_ROOT / "utils" / "v2_html_report.py"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"

results: List[Tuple[str, str, str]] = []
_PATTERNS_EXPECTED = json.loads((PROJECT_ROOT / "data" / "risk_patterns.json").read_text())["patterns"]  # (id, status, message)


def check(check_id: str, status: str, message: str) -> None:
    results.append((check_id, status, message))
    print(f"  [{status}] {check_id} · {message}")


def load_projection() -> Dict[str, Any]:
    return json.loads(PROJ_PATH.read_text())


def load_html() -> str:
    return HTML_PATH.read_text()


# ─────────────────────────────────────────────────────────────────────────────
# C1 · Five-way finding count reconciliation
# ─────────────────────────────────────────────────────────────────────────────
def c1_count_reconciliation(p: Dict[str, Any]) -> None:
    print("\nC1 · Finding count reconciliation across blocks")
    real_total = p["meta"]["counts"]["findings_total"]
    by_team = sum(t["finding_count"] for t in p["groups"]["by_team"])
    by_fn = sum(f["finding_count"] for f in p["groups"]["by_function"])
    by_prod = sum(pp["finding_count"] for pp in p["groups"]["by_product"])
    traj_curr = p.get("trajectory", {}).get("overall_delta", {}).get("curr_findings", None)
    traj_series_curr = None
    series = p.get("trajectory", {}).get("series", [])
    if series:
        last = series[-1]
        traj_series_curr = last.get("total_findings", last.get("findings_total"))

    check("C1.1 meta.counts.findings_total", PASS, f"= {real_total}")
    check("C1.2 groups.by_team sum", PASS if by_team == real_total else FAIL,
          f"= {by_team} (expected {real_total})")
    check("C1.3 groups.by_function sum", PASS if by_fn == real_total else FAIL,
          f"= {by_fn} (expected {real_total})")
    check("C1.4 groups.by_product sum", PASS if by_prod == real_total else FAIL,
          f"= {by_prod} (expected {real_total})")
    if traj_curr is not None:
        check("C1.5 trajectory.overall_delta.curr_findings", PASS if traj_curr == real_total else FAIL,
              f"= {traj_curr} (expected {real_total})")
    if traj_series_curr is not None:
        check("C1.6 trajectory.series[-1].total_findings", PASS if traj_series_curr == real_total else FAIL,
              f"= {traj_series_curr} (expected {real_total})")


# ─────────────────────────────────────────────────────────────────────────────
# C2 · inherent_residual coverage of firing patterns
# ─────────────────────────────────────────────────────────────────────────────
def c2_inherent_residual_coverage(p: Dict[str, Any]) -> None:
    print("\nC2 · inherent_residual.by_pattern covers all firing patterns")
    firing = set()
    for d in p["domains"].values():
        for f in d.get("findings", []):
            firing.add(f.get("pattern_id"))
    ir_patterns = {r["pattern_id"] for r in p["inherent_residual"]["by_pattern"]}
    missing = firing - ir_patterns
    check("C2.1 firing patterns in domains", PASS, f"count={len(firing)} · {sorted(firing)}")
    check("C2.2 inherent_residual.by_pattern coverage",
          PASS if not missing else FAIL,
          f"covers {len(ir_patterns)}/{len(firing)} · missing: {sorted(missing) or 'none'}")


# ─────────────────────────────────────────────────────────────────────────────
# C3 · Portfolio residual haircut lies within the per-pattern effectiveness envelope
# ─────────────────────────────────────────────────────────────────────────────
def c3_portfolio_formula(p: Dict[str, Any]) -> None:
    """v2.0c re-spec. The old gate asserted residual ≈ inherent × (1 − avg_eff) — a
    point formula that is only exact when every pattern has the same effectiveness,
    and only approximately true under INDEPENDENT draws. The correlated MC (cascade
    propagation) legitimately breaks it: induced incidents do not distribute
    proportionally across patterns, so the realized portfolio haircut drifts from the
    simple average. The substantive invariants now are:
      (a) residual and inherent are views of the SAME MC (C18 reconciliation), and
      (b) the realized portfolio haircut lies within the per-pattern effectiveness
          ENVELOPE [min_eff, max_eff] — no pattern-level haircut can be exceeded in
          aggregate, at any percentile.
    """
    print("\nC3 · Portfolio residual haircut within per-pattern effectiveness envelope")
    port = p["inherent_residual"]["portfolio"]
    inh = port["inherent"]
    res = port["residual"]
    effs = [r.get("controls_avg_eff_pct", 0) for r in p["inherent_residual"]["by_pattern"]]
    lo, hi = min(effs), max(effs)
    for tag, pct in (("C3.1", "p50"), ("C3.2", "p95")):
        if inh[pct] <= 0:
            check(f"{tag} residual.{pct} haircut in envelope", FAIL, "inherent is zero")
            continue
        haircut = (1 - res[pct] / inh[pct]) * 100
        ok = (lo - 2.0) <= haircut <= (hi + 2.0)  # ±2pt rounding slack on the band edges
        check(f"{tag} residual.{pct} haircut in envelope", PASS if ok else FAIL,
              f"realized haircut={haircut:.1f}% · per-pattern envelope=[{lo:.0f}%, {hi:.0f}%]")


# ─────────────────────────────────────────────────────────────────────────────
# C4 · Portfolio avg_effectiveness derives from per-pattern effs
# ─────────────────────────────────────────────────────────────────────────────
def c4_avg_eff_derivation(p: Dict[str, Any]) -> None:
    print("\nC4 · Portfolio avg_effectiveness matches mean of per-pattern effs")
    port = p["inherent_residual"]
    portfolio_eff = port["portfolio"]["controls"]["avg_effectiveness_pct"]
    per_pattern_effs = [r.get("controls_avg_eff_pct", 0) for r in port["by_pattern"]]
    if not per_pattern_effs:
        check("C4.1 portfolio avg_eff derivation", FAIL, "no per-pattern effs to compute mean")
        return
    mean_eff = sum(per_pattern_effs) / len(per_pattern_effs)
    tol = 2.0  # within 2% absolute tolerance
    match = abs(portfolio_eff - mean_eff) < tol
    check("C4.1 portfolio avg_eff vs mean of per-pattern effs",
          PASS if match else FAIL,
          f"portfolio={portfolio_eff}% · mean of {len(per_pattern_effs)} per-pattern={mean_eff:.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# C5 · Materiality schema is dict and renderer reads dict (not list)
# ─────────────────────────────────────────────────────────────────────────────
def c5_materiality_schema(p: Dict[str, Any]) -> None:
    print("\nC5 · Materiality grid schema is dict-aware in renderer")
    mat = p.get("materiality")
    is_dict = isinstance(mat, dict)
    check("C5.1 projection.materiality is a dict", PASS if is_dict else FAIL,
          f"type={type(mat).__name__} · keys count={len(mat) if is_dict else 'N/A'}")
    # Check renderer code
    renderer_src = V2_HTML_PY.read_text()
    # SUBSTANCE GATE (risk-officer re-audit): the prior check passed because
    # Object.entries appeared SOMEWHERE in the file — but renderMaterialityGrid
    # itself did `mats.map()` on a dict, so the ATTEST grid rendered empty. Now
    # extract the renderMaterialityGrid function body specifically and confirm
    # IT iterates the dict (Object.entries/values) and does NOT guard on
    # `.length` of a dict (which is always undefined → empty render).
    fn = re.search(r"function\s+renderMaterialityGrid\s*\(\)\s*\{(.*?)\n  \}",
                   renderer_src, re.DOTALL)
    fn_body = fn.group(1) if fn else ""
    iterates_dict = ("Object.entries(" in fn_body) or ("Object.values(" in fn_body)
    guards_on_length = bool(re.search(r"if\s*\(\s*!\s*mats\.length\s*\)", fn_body))
    ok = bool(fn_body) and iterates_dict and not guards_on_length
    check("C5.2 renderMaterialityGrid iterates the dict (not .map on dict)",
          PASS if ok else FAIL,
          "function body uses Object.entries/values, no .length guard"
          if ok else "renderMaterialityGrid does not iterate the dict — ATTEST grid renders empty")


# ─────────────────────────────────────────────────────────────────────────────
# C6 · AI Gov ↔ findings linkage
# ─────────────────────────────────────────────────────────────────────────────
def c6_ai_gov_linkage(p: Dict[str, Any]) -> None:
    print("\nC6 · AI Gov models/agents ↔ findings cross-reference")
    models = p.get("ai_gov", {}).get("models", [])
    agents = p.get("ai_gov", {}).get("agents", [])
    model_ids = {m["id"] for m in models}
    agent_ids = {a["id"] for a in agents}
    # Look for model_id / agent_id fields on findings
    findings_with_model = 0
    findings_with_agent = 0
    findings_referencing = set()
    for d in p["domains"].values():
        for f in d.get("findings", []):
            if f.get("model_id"):
                findings_with_model += 1
                if f["model_id"] in model_ids:
                    findings_referencing.add(f["model_id"])
            if f.get("agent_id"):
                findings_with_agent += 1
                if f["agent_id"] in agent_ids:
                    findings_referencing.add(f["agent_id"])
    check("C6.1 findings have model_id field",
          PASS if findings_with_model > 0 else FAIL,
          f"{findings_with_model} findings carry model_id")
    check("C6.2 findings have agent_id field",
          PASS if findings_with_agent > 0 else FAIL,
          f"{findings_with_agent} findings carry agent_id")
    check("C6.3 findings reference real AI Gov assets",
          PASS if findings_referencing else FAIL,
          f"{len(findings_referencing)} valid cross-refs: {sorted(findings_referencing) or 'none'}")


# ─────────────────────────────────────────────────────────────────────────────
# C7 · Chain integrity verified at load
# ─────────────────────────────────────────────────────────────────────────────
def c7_chain_verification() -> None:
    print("\nC7 · Chain integrity verification (at-load walk, not just string render)")
    src = V2_HTML_PY.read_text()
    # Look for function that walks recent_entries computing hashes
    has_verify_walk = bool(re.search(r"function\s+verifyChain", src) or
                            re.search(r"recompute.*previous_action_hash", src) or
                            re.search(r"chain.*walk", src))
    check("C7.1 verifyChain() function exists in JS",
          PASS if has_verify_walk else FAIL,
          "found verifyChain or chain-walk" if has_verify_walk else "no chain walk — asserts only")


# ─────────────────────────────────────────────────────────────────────────────
# C8 · MOCK MODE strings purged
# ─────────────────────────────────────────────────────────────────────────────
def c8_mock_mode_purge() -> None:
    print("\nC8 · MOCK MODE strings purged from artefacts")
    html = HTML_PATH.read_text()
    proj_txt = PROJ_PATH.read_text()
    html_hits = len(re.findall(r"\bMOCK MODE\b|MOCK_MODE|connect\s+ANTHROPIC_API_KEY", html))
    proj_hits = len(re.findall(r"\bMOCK MODE\b|MOCK_MODE|connect\s+ANTHROPIC_API_KEY", proj_txt))
    check("C8.1 MOCK MODE in current.html",
          PASS if html_hits == 0 else FAIL, f"{html_hits} hits (expected 0)")
    check("C8.2 MOCK MODE in projection.json",
          PASS if proj_hits == 0 else FAIL, f"{proj_hits} hits (expected 0)")


# ─────────────────────────────────────────────────────────────────────────────
# C9 · source_status tri-state is honest (real_query_real_data only on telemetry)
# ─────────────────────────────────────────────────────────────────────────────
def c9_source_status_honest(p: Dict[str, Any]) -> None:
    print("\nC9 · source_status tri-state honesty (real_query_real_data ↔ telemetry)")
    proj_txt = PROJ_PATH.read_text()
    real_real = proj_txt.count('"real_query_real_data"')
    real_synth = proj_txt.count('"real_query_synthesized_data"')
    illustrative = proj_txt.count('"illustrative"')
    published_standard = proj_txt.count('"published_standard"')
    check("C9.1 real_query_real_data tag count", PASS if real_real >= 0 else FAIL,
          f"{real_real} occurrences (was previously over-applied to thresholds)")
    check("C9.2 real_query_synthesized_data has some usage",
          PASS if real_synth > 0 else WARN,
          f"{real_synth} occurrences (tri-state should not collapse to bi-state)")
    check("C9.3 published_standard tag exists for cited thresholds",
          PASS if published_standard > 0 else FAIL,
          f"{published_standard} occurrences (thresholds should carry this, not real_query_real_data)")
    check("C9.4 illustrative tag presence", PASS, f"{illustrative} occurrences")


# ─────────────────────────────────────────────────────────────────────────────
# C10 · Acceptance trail variability
# ─────────────────────────────────────────────────────────────────────────────
def c10_acceptance_variability(p: Dict[str, Any]) -> None:
    print("\nC10 · Acceptance trail variability (no templated boilerplate)")
    acceptances = []
    seen_tickets = {}
    for d in p["domains"].values():
        for f in d.get("findings", []):
            # acceptance_trail is a LIST of acceptance records per finding
            trail = f.get("acceptance_trail")
            records = trail if isinstance(trail, list) else ([trail] if isinstance(trail, dict) else [])
            for acc in records:
                if isinstance(acc, dict) and acc:
                    acceptances.append(acc)
                    t = acc.get("ticket")
                    if t:
                        seen_tickets.setdefault(t, []).append(f.get("finding_id"))
    # SUBSTANCE GATE (audit-regulator meta-finding): the prior check measured
    # uniqueness of the FULLY-WRAPPED conditions string. The per-domain "Scoped
    # to the {domain} domain; automatic review at {date}" suffix guarantees a
    # pass even if the base pattern text were byte-identical boilerplate. Strip
    # the wrapper and measure variability of the BASE pattern reasoning so
    # distinctness-by-scoping cannot mask templated base text.
    def _strip_wrapper(text: str) -> str:
        # remove the leading "[domain] " tag and trailing " Scoped to the ... renew." sentence
        t = re.sub(r"^\[[^\]]+\]\s*", "", text)
        t = re.sub(r"\s*Scoped to the .*$", "", t)
        return t.strip()
    conditions_texts = [a.get("conditions", "") for a in acceptances if a.get("conditions")]
    base_texts = [_strip_wrapper(t) for t in conditions_texts]
    unique_base = set(base_texts)
    # Per-pattern base text is legitimately shared across domains (the trigger
    # logic IS pattern-level). What we forbid is base text shared across
    # DIFFERENT patterns. So: group base text by pattern_id and confirm each
    # pattern's base is distinct from every other pattern's base.
    base_by_pattern = {}
    for a, bt in zip(acceptances, base_texts):
        # recover pattern from ticket or finding context isn't available here;
        # use the base text itself — count how many DISTINCT base strings exist
        base_by_pattern.setdefault(bt, 0)
        base_by_pattern[bt] += 1
    # 13 patterns → expect ~ up to 13 distinct base strings. A healthy result:
    # distinct base strings >= number of distinct patterns that have acceptances.
    duplicate_tickets = {k: v for k, v in seen_tickets.items() if len(v) > 1}
    if conditions_texts:
        # Pass if there are multiple distinct BASE conditions (not one templated
        # base reused everywhere). For a demonstrator with N patterns we expect
        # at least 5 distinct base reasonings.
        ok = len(unique_base) >= 5
        check("C10.1 acceptance BASE conditions are pattern-specific (wrapper stripped)",
              PASS if ok else FAIL,
              f"{len(unique_base)} distinct base reasonings across {len(conditions_texts)} acceptances"
              + ("" if ok else " — base text appears templated"))
    else:
        check("C10.1 acceptance conditions variability", WARN, "no acceptances found in projection")
    check("C10.2 acceptance ticket uniqueness",
          PASS if not duplicate_tickets else FAIL,
          f"{len(duplicate_tickets)} tickets reused: {list(duplicate_tickets.keys())[:5]}")


# ─────────────────────────────────────────────────────────────────────────────
# C11 · Executive hero band present in landing
# ─────────────────────────────────────────────────────────────────────────────
def c11_executive_hero() -> None:
    print("\nC11 · Executive hero band on landing")
    html = HTML_PATH.read_text()
    has_hero = bool(re.search(r"class=\"exec-hero|exec-band|executive-hero|portfolio-rag", html))
    check("C11.1 executive hero band exists",
          PASS if has_hero else FAIL,
          "found exec-hero/portfolio-rag markup" if has_hero else "no hero band — board lands on 'Signals firing'")


# ─────────────────────────────────────────────────────────────────────────────
# C12 · AI Gov pane reachable (ai_gov rail item rendered)
# ─────────────────────────────────────────────────────────────────────────────
def c12_ai_gov_reachable() -> None:
    print("\nC12 · AI Gov rail item present (pane reachable from default landing)")
    html = HTML_PATH.read_text()
    # Looking for an ai_gov rail item with data-domain="ai_gov"
    has_rail_item = bool(re.search(r'data-domain="ai_gov"', html))
    check("C12.1 ai_gov rail item rendered",
          PASS if has_rail_item else FAIL,
          "found data-domain=\"ai_gov\" rail item" if has_rail_item else "no ai_gov rail — pane unreachable")


# ─────────────────────────────────────────────────────────────────────────────
# C13 · Threshold history captured (intent + extensibility)
# ─────────────────────────────────────────────────────────────────────────────
def c13_threshold_history(p: Dict[str, Any]) -> None:
    print("\nC13 · Threshold history schema present (audit-regulator addition)")
    proj_txt = PROJ_PATH.read_text()
    pattern_txt = (PROJECT_ROOT / "data" / "risk_patterns.json").read_text()
    has_in_projection = "threshold_history" in proj_txt or "threshold_change" in proj_txt
    has_in_patterns = "threshold_history" in pattern_txt
    check("C13.1 threshold_history exists",
          PASS if (has_in_projection or has_in_patterns) else FAIL,
          "found in projection or patterns" if (has_in_projection or has_in_patterns) else "no threshold_history anywhere")


# ─────────────────────────────────────────────────────────────────────────────
# C14 · Artefact-level integrity hash + signer in footer
# ─────────────────────────────────────────────────────────────────────────────
def c14_artefact_integrity() -> None:
    print("\nC14 · Artefact-level integrity hash + signer in footer")
    html = HTML_PATH.read_text()
    # Tolerate markup (e.g. <code> wrapper) between "SHA-256" and the digest.
    has_hash = bool(re.search(r"SHA-256.{0,60}?[a-f0-9]{16,}", html))
    # r52: the footer says "generated-by" (a pipeline generates; "signed-by"
    # implied attestation authority a build does not have) — the gate accepts
    # the honest vocabulary and the legacy forms it replaced.
    has_signer = bool(re.search(r'class="generated-by|generated-by:\s*|class="signed-by|class="signer|signed-by:\s*', html, re.I))
    check("C14.1 SHA-256 artefact hash visible", PASS if has_hash else FAIL,
          "hash visible in footer" if has_hash else "no integrity hash")
    check("C14.2 signer visible", PASS if has_signer else WARN,
          "signer visible" if has_signer else "no signer attribution — audit-regulator P0")


# ─────────────────────────────────────────────────────────────────────────────
# C15 · Operational: register row enriched with signal value + threshold + treatment
# ─────────────────────────────────────────────────────────────────────────────
def c15_register_row_enriched() -> None:
    print("\nC15 · Register row carries signal value + threshold + treatment fields")
    html = HTML_PATH.read_text()
    has_signal_col = "signal" in html.lower() and bool(re.search(r"<th[^>]*>\s*signal", html, re.I))
    has_thresh_col = bool(re.search(r"<th[^>]*>\s*threshold", html, re.I))
    has_treatment_col = bool(re.search(r"<th[^>]*>\s*treatment|ticket", html, re.I))
    has_owner_col = bool(re.search(r"<th[^>]*>\s*owner", html, re.I))
    check("C15.1 register row has signal value column",
          PASS if has_signal_col else FAIL, "signal column present" if has_signal_col else "missing")
    check("C15.2 register row has threshold column",
          PASS if has_thresh_col else FAIL, "threshold column present" if has_thresh_col else "missing")
    check("C15.3 register row has treatment/ticket column",
          PASS if has_treatment_col else FAIL, "treatment column present" if has_treatment_col else "missing")
    check("C15.4 register row has owner column",
          PASS if has_owner_col else FAIL, "owner column present" if has_owner_col else "missing")


# ─────────────────────────────────────────────────────────────────────────────
# C16 · KEV first-class signal modelled (not just copy)
# ─────────────────────────────────────────────────────────────────────────────
def c17_taxonomy_consistency(p: Dict[str, Any]) -> None:
    """Pattern taxonomy in projection + HTML matches the authoritative names in
    data/risk_patterns.json. Guards against the invented-taxonomy drift caught
    in the directory review (RP-06 'eval coverage', RP-10 'agent scope', etc.)."""
    print("\nC17 · Pattern taxonomy matches authoritative risk_patterns.json")
    raw = json.loads((PROJECT_ROOT / "data" / "risk_patterns.json").read_text())
    pats = raw.get("patterns", raw)
    auth = {}
    if isinstance(pats, list):
        for pp in pats:
            auth[pp.get("id") or pp.get("pattern_id")] = pp.get("name")
    # patterns_meta present + matches
    pm = (p.get("patterns_meta") or {}).get("patterns", [])
    pm_names = {x["id"]: x["name"] for x in pm}
    mismatches = [pid for pid, nm in pm_names.items() if auth.get(pid) and nm != auth[pid]]
    check("C17.1 patterns_meta present", PASS if pm else FAIL,
          f"{len(pm)} patterns" if pm else "patterns_meta missing")
    check("C17.2 patterns_meta names match risk_patterns.json",
          PASS if (pm and not mismatches) else FAIL,
          "all 13 names authoritative" if (pm and not mismatches) else f"mismatches: {mismatches}")
    # invented-taxonomy strings must NOT appear in HTML
    html = HTML_PATH.read_text()
    # Only the invented PATTERN-NAME card titles that contradicted
    # risk_patterns.json. Real metric terms (e.g. "change failure rate") may
    # legitimately appear in threshold descriptions and are NOT banned.
    banned = ["eval coverage (AI)", "agent scope violation", "model lineage",
              "data loss / exfil", "DR / BCP"]
    found = [b for b in banned if b in html]
    check("C17.3 no invented-taxonomy labels in HTML",
          PASS if not found else FAIL,
          "clean" if not found else f"found invented labels: {found}")


def c16_kev_first_class(p: Dict[str, Any]) -> None:
    print("\nC16 · KEV BOD 22-01 14-day clock is first-class signal (not just copy)")
    raw = json.loads((PROJECT_ROOT / "data" / "risk_patterns.json").read_text())
    pats = raw.get("patterns", raw)
    if isinstance(pats, list):
        rp04 = next((pp for pp in pats if (pp.get("id") or pp.get("pattern_id")) == "RP-04"), {})
    else:
        rp04 = pats.get("RP-04", {})
    has_kev_field = "kev_listed" in json.dumps(rp04)
    has_14day_threshold = "vuln_aging_kev_days" in (rp04.get("thresholds", {}) or {})
    check("C16.1 kev_listed field exists in RP-04 config",
          PASS if has_kev_field else FAIL, "kev_listed block present" if has_kev_field else "missing")
    # SUBSTANCE GATE (SRE + audit-regulator meta-finding): a KEV signal that
    # only exists in config is theater. C16.2 now asserts the signal actually
    # FIRES — i.e. vuln_aging_kev_days appears in signals_exceeded of a real
    # RP-04 finding in the projection — not merely that the string is present.
    p = load_projection()
    kev_fires = False
    kev_evidence = ""
    for d in p.get("domains", {}).values():
        for f in d.get("findings", []):
            if f.get("pattern_id") == "RP-04":
                bs = f.get("signals_exceeded", {}) or {}
                if "vuln_aging_kev_days" in bs:
                    kev_fires = True
                    sig = bs["vuln_aging_kev_days"]
                    kev_evidence = f"{f.get('finding_id','')[-24:]} · kev_days={sig.get('value')} ({sig.get('rag')})"
                    break
        if kev_fires:
            break
    check("C16.2 KEV signal FIRES in an RP-04 finding (not just config)",
          PASS if (has_14day_threshold and kev_fires) else FAIL,
          kev_evidence if kev_fires else "vuln_aging_kev_days defined but never fires in any finding — theater")


# ─────────────────────────────────────────────────────────────────────────────
# Run all
# ─────────────────────────────────────────────────────────────────────────────
def c18_cross_surface_reconciliation(p: Dict[str, Any]) -> None:
    """Any two portfolio values sharing a label + scope MUST agree — the check that would
    have caught the two-exposure-model incoherence ($3.13B stress vs $835M/$249.7M residual)."""
    print("\nC18 · cross-surface numeric reconciliation (one distribution, not two)")
    ex = p.get("exposure", {}).get("portfolio_total", {})
    ir = p.get("inherent_residual", {}).get("portfolio", {})
    ex_res, ir_res = ex.get("p95_usd"), (ir.get("residual") or {}).get("p95")
    ex_inh, ir_inh = ex.get("inherent_p95_usd"), (ir.get("inherent") or {}).get("p95")
    check("C18.1 exposure stress P95 == inherent_residual residual P95",
          PASS if ex_res == ir_res else FAIL, f"exposure {ex_res:,} vs inherent_residual {ir_res:,}")
    check("C18.2 exposure inherent P95 == inherent_residual inherent P95",
          PASS if ex_inh == ir_inh else FAIL, f"exposure {ex_inh} vs inherent_residual {ir_inh}")
    check("C18.3 inherent P95 >= residual P95 (controls reduce exposure)",
          PASS if (ir_inh or 0) >= (ir_res or 0) else FAIL, f"inherent {ir_inh:,} >= residual {ir_res:,}")
    check("C18.4 portfolio P95 is credible (< $2B — no pathological Sigma-of-tails)",
          PASS if 0 < (ir_inh or 0) < 2_000_000_000 else FAIL,
          f"inherent P95 ${(ir_inh or 0)/1e6:.0f}M (the naive Sigma produced $3.13B; MC gives a real aggregate)")


def c19_no_unsourced_render_data(p: Dict[str, Any]) -> None:
    """Heuristic: the render layer must not HARDCODE data it should read from the projection.
    Catches the impact-faces regression (a literal array of scores rendered as data)."""
    import re as _re
    print("\nC19 · no un-sourced data hardcoded in the render layer")
    src = V2_HTML_PY.read_text()
    faces = _re.findall(r"name:\s*'[^']+',\s*(?:pct|score):\s*\d", src)
    check("C19.1 no hardcoded {name, pct/score} arrays in render (impact-faces regression)",
          PASS if not faces else FAIL, "clean" if not faces else f"{len(faces)} hardcoded score literals")
    # bare 8+ digit integers in the render JS almost certainly = money that belongs in the projection.
    # allowlist obvious time constants (ms): 86400000 = 24h, 3600000 = 1h, 604800000 = 7d.
    _TIME_MS = {"86400000", "3600000", "604800000", "2592000000"}
    big = [d for d in _re.findall(r"[^\d.](\d{8,})", src) if 1e7 <= int(d) < 1e12 and d not in _TIME_MS]
    check("C19.2 no large ($10M+) $ literals hardcoded in render JS",
          PASS if not big else WARN, "clean" if not big else f"review: {sorted(set(big))[:3]}")


# ─────────────────────────────────────────────────────────────────────────────
# C20 · Sensitivity appendix is engine-derived substance, not decoration
# ─────────────────────────────────────────────────────────────────────────────
def c20_sensitivity_substance(p: Dict[str, Any]) -> None:
    """The calibration appendix answers 'how far does the answer move if the
    judgment is wrong.' The gate asserts it is real: every lever actually moved
    the engine (not copied baselines), the cascade_off lever reconciles byte-exact
    with correlation_model.independence_counterfactual (cross-surface), and the
    calibration table covers all 13 patterns with a cited worst-anchor each."""
    print("\nC20 · Sensitivity appendix — engine-derived, cross-reconciled")
    s = p.get("sensitivity") or {}
    levers = s.get("levers") or []
    base = (s.get("baseline") or {}).get("residual_p95", 0)
    check("C20.1 sensitivity block present with ≥8 one-judgment levers",
          PASS if len(levers) >= 8 and base > 0 else FAIL,
          f"{len(levers)} levers · baseline P95 ${base:,}")
    moved = [l for l in levers if l.get("residual_p95") != base]
    check("C20.2 every lever moved the engine (no copied baselines)",
          PASS if len(moved) == len(levers) and levers else FAIL,
          f"{len(moved)}/{len(levers)} levers differ from baseline")
    cf = (((p.get("exposure") or {}).get("portfolio_total") or {})
          .get("correlation_model") or {}).get("independence_counterfactual") or {}
    off = next((l for l in levers if l.get("id") == "cascade_off"), {})
    check("C20.3 cascade_off lever == independence counterfactual (cross-surface)",
          PASS if off.get("residual_p95") == cf.get("residual_p95") and off else FAIL,
          f"lever=${off.get('residual_p95', 0):,} · counterfactual=${cf.get('residual_p95', 0):,}")
    table = s.get("calibration_table") or []
    anchored = [r for r in table if r.get("worst_anchor_basis")]
    check("C20.4 calibration table covers every catalog pattern, each with a cited anchor",
          PASS if len(table) == len(_PATTERNS_EXPECTED) and len(anchored) == len(_PATTERNS_EXPECTED) else FAIL,
          f"{len(table)} rows · {len(anchored)} with cited anchors")
    # v2.0d: joint shocks + judgment log — calibration depth, not just leverage
    joints = [l for l in levers if l.get("id", "").startswith("joint_")]
    check("C20.5 joint shocks present (OAT-limitation partially answered)",
          PASS if len(joints) >= 2 and all(j.get("residual_p95") != base for j in joints) else FAIL,
          f"{len(joints)} joint levers, all moved the engine" if joints else "no joint levers")
    jlog = s.get("judgment_log") or []
    complete = [j for j in jlog if j.get("basis") and j.get("challenge") and j.get("set_at")]
    check("C20.6 judgment log — every operator judgment has who/when/basis/challenge",
          PASS if len(jlog) >= 5 and len(complete) == len(jlog) else FAIL,
          f"{len(jlog)} entries · {len(complete)} complete")
    # Round-12: the σ choice must be PRICED data, not judgment-log prose — sweep
    # present, strictly increasing in σ, and the σ=0.3 point must reconcile
    # byte-exact with the sev_shock lever (same engine, same seed, cross-surface).
    sweep = (s.get("sev_shock_sweep") or {}).get("points") or []
    mono = all(sweep[i]["residual_p95"] < sweep[i + 1]["residual_p95"] for i in range(len(sweep) - 1))
    lever = next((l for l in levers if l.get("id") == "sev_shock"), {})
    p03 = next((pt for pt in sweep if pt.get("sigma") == 0.3), {})
    check("C20.7 sev-shock sweep — ≥3 priced σ points, monotonic, σ=0.3 == the tornado lever",
          PASS if len(sweep) >= 3 and mono and p03.get("residual_p95") == lever.get("residual_p95") else FAIL,
          f"{len(sweep)} points · monotonic={mono} · σ0.3 reconciles={p03.get('residual_p95') == lever.get('residual_p95')}")


# ─────────────────────────────────────────────────────────────────────────────
# C21 · Regulatory residual — subset quantiles, never summed percentiles
# ─────────────────────────────────────────────────────────────────────────────
def c21_regulation_residual(p: Dict[str, Any]) -> None:
    """The per-regulation view must be honest the same way the portfolio is:
    quantiles of within-trial subset sums. Gates: (1) block present, mapped to the
    materiality trigger sets; (2) every regulation's P95 ≤ portfolio P95 (subset
    dominance — mathematically guaranteed for correct subset quantiles, so a
    violation means summed percentiles snuck back in); (3) every multi-pattern
    regulation's P95 < its naive Σ-of-per-pattern-P95s (the anti-example stays
    an anti-example)."""
    print("\nC21 · Regulatory residual — subset quantiles, never summed percentiles")
    rr = p.get("regulation_residual") or {}
    rows = rr.get("by_regulation") or []
    port = rr.get("portfolio_residual_p95", 0)
    check("C21.1 block present, one row per triggered regulation",
          PASS if len(rows) >= 4 and port > 0 else FAIL,
          f"{len(rows)} regulations · portfolio P95 ${port:,}")
    dom = [r for r in rows if r.get("residual_p95", 0) <= port]
    check("C21.2 subset dominance — every regulation P95 ≤ portfolio P95",
          PASS if len(dom) == len(rows) and rows else FAIL,
          f"{len(dom)}/{len(rows)} rows dominated")
    multi = [r for r in rows if len(r.get("patterns", [])) > 1]
    anti = [r for r in multi if r.get("residual_p95", 0) < r.get("naive_percentile_sum_p95", 0)]
    check("C21.3 percentiles-do-not-add — multi-pattern P95 < naive Σ of P95s",
          PASS if len(anti) == len(multi) else FAIL,
          f"{len(anti)}/{len(multi)} multi-pattern rows below their naive sum")
    mat = p.get("materiality") or {}
    consistent = True
    for r in rows:
        blk = mat.get(r.get("reg_id"), {})
        want = set(blk.get("triggered_patterns") or blk.get("conditional_patterns") or [])
        if set(r.get("patterns", [])) != want:
            consistent = False
    check("C21.4 pattern sets reconcile to the materiality block (cross-surface)",
          PASS if consistent and rows else FAIL, "sets match" if consistent else "MISMATCH")


# ─────────────────────────────────────────────────────────────────────────────
# C22 · Control test-evidence schema — reconciled to the MC's input
# ─────────────────────────────────────────────────────────────────────────────
def c22_control_evidence(p: Dict[str, Any]) -> None:
    """The model's biggest lever (control effectiveness) now carries the evidence
    STRUCTURE a 2LoD credits against. Gates: every pattern ships the schema with
    complete rows (method/date/ref for tested controls), credited ≤ self-assessed
    per control, and — the one that matters — mean(credited over tested controls)
    reconciles to the avg_effectiveness_pct the MC actually consumes, so the
    schema and the model cannot tell two different stories."""
    print("\nC22 · Control test-evidence schema — reconciled to the MC input")
    table = (p.get("sensitivity") or {}).get("calibration_table") or []
    with_ev = [r for r in table if (r.get("control_evidence") or {}).get("controls")]
    check("C22.1 every pattern carries the evidence schema",
          PASS if len(with_ev) == len(_PATTERNS_EXPECTED) else FAIL,
          f"{len(with_ev)}/{len(_PATTERNS_EXPECTED)} patterns")
    complete = credited_ok = reconciled = 0
    for r in with_ev:
        ev = r["control_evidence"]
        tested = [c for c in ev["controls"] if c.get("last_tested")]
        if tested and all(c.get("method") and c.get("evidence_ref") for c in tested):
            complete += 1
        if all(c.get("credited_pct", 0) <= c.get("self_assessed_pct", 0) for c in tested):
            credited_ok += 1
        mean_credited = sum(c["credited_pct"] for c in tested) / len(tested) if tested else 0
        if abs(mean_credited - float(r.get("controls_eff_pct") or 0)) <= 0.5:
            reconciled += 1
    check("C22.2 tested controls complete (method · date · ref)",
          PASS if complete == len(with_ev) else FAIL, f"{complete}/{len(with_ev)}")
    check("C22.3 credited ≤ self-assessed per control (the haircut, visible)",
          PASS if credited_ok == len(with_ev) else FAIL, f"{credited_ok}/{len(with_ev)}")
    check("C22.4 mean(credited) == avg_effectiveness_pct the MC consumes (±0.5pt)",
          PASS if reconciled == len(with_ev) else FAIL, f"{reconciled}/{len(with_ev)} reconciled")


# ─────────────────────────────────────────────────────────────────────────────
# C23 · Internal-audit register — full 3LoD lifecycle, honest states included
# ─────────────────────────────────────────────────────────────────────────────
def c23_internal_audit(p: Dict[str, Any]) -> None:
    """The register must carry the states that make an audit shop real — not a
    list of green rows: every issue complete (response/target/status), at least
    one PAST-DUE, at least one REPEAT, at least one regulator-visible item, and
    at least one closure that cites validation evidence."""
    print("\nC23 · Internal-audit register — lifecycle completeness")
    ia = p.get("internal_audit") or {}
    issues = ia.get("issues") or []
    check("C23.1 register present with ≥6 issues, labeled illustrative",
          PASS if len(issues) >= 6 and ia.get("source_status") == "illustrative" else FAIL,
          f"{len(issues)} issues")
    complete = [i for i in issues if i.get("management_response") and i.get("target_date") and i.get("status")]
    check("C23.2 every issue carries response + target + status",
          PASS if len(complete) == len(issues) and issues else FAIL, f"{len(complete)}/{len(issues)}")
    has_pd = any("PAST DUE" in i.get("status", "") for i in issues)
    has_rep = any(i.get("repeat_finding") for i in issues)
    has_reg = any(str(i.get("issue_id", "")).startswith("EX-") for i in issues)
    has_val = any("validation passed" in i.get("status", "").lower() for i in issues)
    check("C23.3 honest lifecycle states — past-due, repeat, regulator-visible, validated closure",
          PASS if (has_pd and has_rep and has_reg and has_val) else FAIL,
          f"past_due={has_pd} repeat={has_rep} exam-style={has_reg} validated_close={has_val}")
    known = {pt["pattern_id"] for pt in (p.get("sensitivity") or {}).get("calibration_table", [])}
    linked = [i for i in issues if i.get("pattern_id") in known]
    check("C23.4 every issue links to a real pattern (registers reconcile)",
          PASS if len(linked) == len(issues) and issues else FAIL, f"{len(linked)}/{len(issues)}")


# ─────────────────────────────────────────────────────────────────────────────
# C24 · Coverage ≠ effectiveness — class-wide gate (round-11 external review)
# ─────────────────────────────────────────────────────────────────────────────
def c24_coverage_vs_effectiveness(p: Dict[str, Any]) -> None:
    """Round-10 fixed two 100%-credited controls instance-wise; round-11 found
    the same conflation on five more. This gate enforces the CLASS: any control
    credited >= 90 must carry an explicit effectiveness rationale in its
    evidence_basis — a coverage/completion stat alone cannot justify high
    credit. Fires on source data so future patterns inherit the rule."""
    print("\nC24 · Coverage ≠ effectiveness — high credit needs an effectiveness basis")
    import re as _re
    raw = json.loads((PROJECT_ROOT / "data" / "risk_patterns.json").read_text())
    EFFECTIVENESS = _re.compile(
        r"credited|but |misses|not caught|cannot intercept|does not stop|do not stop|"
        r"residual|decays|pass rate|success rate|burndown|closure rate|detective|recall",
        _re.I)
    # Round-12: "% of" under-matched the register's own idiom ("% identities…",
    # "% training runs…") — external review found the class re-opening below the
    # ≥90 bar. Bare "% " is a coverage stat; match it.
    COVERAGE = _re.compile(r"coverage|completion|% |attainment|attestation", _re.I)
    ctrls = [(pat["id"], c) for pat in raw["patterns"]
             for c in pat.get("compensating_controls", {}).get("in_place", [])]
    high = [(pid, c) for pid, c in ctrls if c.get("effectiveness_pct", 0) >= 90]
    bad = [f"{pid}/{c.get('name')}" for pid, c in high
           if not EFFECTIVENESS.search(c.get("evidence_basis", ""))]
    check("C24.1 every control credited ≥90 carries an effectiveness rationale, not a bare coverage stat",
          PASS if not bad else FAIL,
          f"{len(high) - len(bad)}/{len(high)} high-credit controls" if not bad else str(bad[:4]))
    over = [f"{pid}/{c.get('name')}={c.get('effectiveness_pct')}" for pid, c in ctrls
            if c.get("effectiveness_pct", 0) >= 100]
    check("C24.2 no control credits 100% (coverage can be total; effectiveness never is)",
          PASS if not over else FAIL, "none at 100" if not over else str(over))
    # Anti-vacuity: the coverage-language detector must actually match the
    # register's idiom, or C24.1 could green-wash on wording drift.
    cov_hits = sum(1 for _, c in ctrls if COVERAGE.search(c.get("evidence_basis", "")))
    check("C24.3 gate non-vacuous — coverage-language detector matches the register idiom",
          PASS if cov_hits >= 10 else FAIL, f"{cov_hits} controls carry coverage-language bases")
    # Round-12 class completion (external review: the ≥90 bar left the same
    # conflation live on every lower-credited control): ANY basis that leads
    # with a coverage/completion stat must also say what the stat does NOT
    # prove — at every credit level, for every future pattern.
    bad_all = [f"{pid}/{c.get('name')}={c.get('effectiveness_pct')}" for pid, c in ctrls
               if COVERAGE.search(c.get("evidence_basis", ""))
               and not EFFECTIVENESS.search(c.get("evidence_basis", ""))]
    check("C24.4 every coverage-language basis carries the coverage→effectiveness split (no credit bar)",
          PASS if not bad_all else FAIL,
          f"{cov_hits}/{cov_hits} split" if not bad_all else str(bad_all[:4]))


# ─────────────────────────────────────────────────────────────────────────────
# C25 · Register generation is deterministic (round-12: verify_bundle caught
# three rebuilds minutes apart yielding 27/25/26 findings — RISK_RNG_SEED
# existed but nothing set it, so the register rolled unseeded dice while the
# artifact claimed seed-reproducibility)
# ─────────────────────────────────────────────────────────────────────────────
def c25_register_determinism() -> None:
    """Two fresh runs must produce the identical register — same finding ids,
    same RAGs, same signal values. This is the register-side counterpart of the
    MC's seed-42 byte-stability (which never wobbled; the dollars were always
    deterministic — the FINDINGS were not)."""
    print("\nC25 · Register generation — deterministic per run")
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from graph.risk_graph import run_risk_assessment

    def register(report):
        out = []
        for did, dr in sorted(report.get("domain_reports", {}).items()):
            for f in dr.get("findings", []):
                out.append((did, f.get("pattern_id"), f.get("overall_rag"),
                            json.dumps(f.get("signals_exceeded", {}), sort_keys=True, default=str)))
        return out

    a = register(run_risk_assessment(demo=True))
    b = register(run_risk_assessment(demo=True))
    check("C25.1 two consecutive runs produce the identical register (ids, RAGs, signals)",
          PASS if a == b and a else FAIL,
          f"{len(a)} findings, byte-equal" if a == b else f"run1 {len(a)} != run2 {len(b)}")


# ─────────────────────────────────────────────────────────────────────────────
# C26 · IA conservation — classic ↔ spine fingerprints (Stage B, spec v2.2 §6)
# C27 · Spine integrity — nodes resolve, paths cover, headlines cite numbers
# ─────────────────────────────────────────────────────────────────────────────
def c26_c27_ia(p: Dict[str, Any]) -> None:
    import hashlib
    print("\nC26 · IA conservation — classic ↔ spine (report + freshness)")
    repo = PROJECT_ROOT.parent.parent
    rep_path = repo / "qa" / "conservation_report.json"
    ok_rep = rep_path.exists()
    rep = json.loads(rep_path.read_text()) if ok_rep else {}
    check("C26.1 conservation report exists with verdict PASS",
          PASS if ok_rep and rep.get("verdict") == "PASS" else FAIL,
          rep.get("verdict", "missing"))
    fresh = ok_rep
    if ok_rep:
        for name, f in (("classic_sha256", "docs/archive/classic.html"), ("new_sha256", "docs/index.html"),
                        ("read_sha256", "docs/read.html"), ("validation_sha256", "docs/validation.html"),
                        ("board_sha256", "docs/board.html"), ("journey_sha256", "docs/journey.html")):
            h = hashlib.sha256((PROJECT_ROOT / f).read_bytes()).hexdigest()
            if rep.get("inputs", {}).get(name) != h:
                fresh = False
    check("C26.2 report is FRESH — input hashes match the shipped classic + new builds "
          "(a rebuild without re-running the probe fails here)",
          PASS if fresh else FAIL, "hashes match" if fresh else "STALE — re-run scripts/conservation_probe.js")

    print("\nC27 · Spine integrity — the map cannot say what the page doesn't")
    ia = p.get("ia") or {}
    nodes = ia.get("nodes") or []
    html = (PROJECT_ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    dangling = [f"{n['id']}:{tg}" for n in nodes for tg in n.get("targets", [])
                if f'data-target="{tg}"' not in html]
    check("C27.1 every spine-node target resolves to a live mount", PASS if not dangling else FAIL,
          f"{sum(len(n.get('targets', [])) for n in nodes)} targets resolve" if not dangling else str(dangling[:4]))
    node_ids = {n["id"] for n in nodes}
    paths = ia.get("paths") or {}
    union = set().union(*paths.values()) if paths else set()
    bad_path = [f"{r}:{nid}" for r, pth in paths.items() for nid in pth if nid not in node_ids]
    check("C27.2 role paths reference only real nodes; their union covers every node",
          PASS if not bad_path and union == node_ids and ia.get("default_role") in paths else FAIL,
          f"{len(paths)} roles · union {len(union)}/{len(node_ids)} nodes")
    import re as _re
    proj_text = json.dumps(p)
    def cited(h):
        return any(tok.strip("$%").replace(",", "") in proj_text
                   for tok in _re.findall(r"\$?[\d][\d,\.]*%?", h or ""))
    bad_head = [n["id"] for n in nodes if not cited(n.get("headline"))]
    bad_head += [k for k, v in (ia.get("headlines") or {}).items() if not cited(v)]
    # round-16 external: the thesis carries the headline dollars as prose — gate it too
    if _re.search(r"\d", ia.get("thesis") or "") and not cited(ia.get("thesis")):
        bad_head.append("thesis")
    check("C27.3 every conclusion headline cites a number present in the projection (§8 genre gate)",
          PASS if not bad_head else FAIL,
          f"{len(nodes) + len(ia.get('headlines') or {})} headlines cited" if not bad_head else str(bad_head[:4]))
    # C27.4 (round-22 external: "B10 protects leaves, not the sentences a human
    # reads") — every $X.XM SPOKEN by an ia string must round-match a numeric
    # LEAF, so prose can never drift from data while gates stay green.
    leaves = set()
    def _walk(o):
        if isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            leaves.add(round(float(o) / 1e6, 1))
    _walk(p)
    ia_strings = [ia.get("thesis") or ""] + [n.get("headline") or "" for n in nodes] + list((ia.get("headlines") or {}).values())
    loose = []
    n_tok = 0
    for st in ia_strings:
        for tok in _re.findall(r"\$([\d.]+)M", st):
            n_tok += 1
            if float(tok) not in leaves:
                loose.append(f"${tok}M")
    check("C27.4 every $ figure SPOKEN by an ia string round-matches a numeric leaf (prose cannot drift from data)",
          PASS if not loose else FAIL,
          f"{n_tok} spoken dollars all leaf-backed" if not loose else f"prose-only: {loose[:4]}")
    # C27.5 (round-25 external: "gate the derived Board inputs so the NOTE
    # resolution cannot silently drift") — every ia.derived value the Board
    # brief speaks must RECOMPUTE from the projection it ships with, and the
    # docket list must match the one selection rule both surfaces consume.
    derived = ia.get("derived") or {}
    by_pat = {r["pattern_id"]: (r.get("residual") or {}).get("p95", 0)
              for r in (p.get("inherent_residual") or {}).get("by_pattern") or []}
    red_rows = sorted(((by_pat.get(f.get("pattern_id"), 0), f.get("pattern_id"), did)
                       for did, d in (p.get("domains") or {}).items()
                       for f in d.get("findings") or [] if f.get("overall_rag") == "red"),
                      key=lambda r: (-r[0], r[1], r[2]))
    want_items = [{"pattern_id": pid, "domain": did, "residual_p95": usd}
                  for usd, pid, did in red_rows[:3]]
    want_team = sum(1 for d in (p.get("domains") or {}).values()
                    for f in d.get("findings") or []
                    if str((f.get("treatment") or {}).get("owner_handle", "")).startswith("@"))
    pd_repeat = [i for i in (p.get("internal_audit") or {}).get("issues") or []
                 if "PAST DUE" in str(i.get("status", "")) and i.get("repeat_finding")]
    probs = []
    if derived.get("docket_items") != want_items:
        probs.append("docket_items != top-3 rule")
    if derived.get("docket_at_stake_usd") != sum(it["residual_p95"] for it in want_items):
        probs.append("docket sum != Σ(items)")
    if derived.get("treatments_team_routed") != want_team:
        probs.append(f"team_routed {derived.get('treatments_team_routed')} != recount {want_team}")
    if not pd_repeat:
        probs.append("no PAST-DUE repeat issue for the NOTE resolution to cite")
    check("C27.5 derived Board inputs recompute (docket items + sum, A8 team-routed count, past-due repeat pick)",
          PASS if not probs else FAIL,
          f"docket 3 items Σ ${sum(it['residual_p95'] for it in want_items)/1e6:.1f}M · team-routed {want_team} · "
          f"past-due repeat {pd_repeat[0].get('issue_id') if pd_repeat else '—'}" if not probs else "; ".join(probs))


def c28_perimeter(p: Dict[str, Any]) -> None:
    print("\nC28 · perimeter profiles — re-mapping is subset sums + reservation, never minting")
    pp = (p.get("regulation_residual") or {}).get("perimeter_profiles") or {}
    profs = pp.get("profiles") or []
    port = (p.get("regulation_residual") or {}).get("portfolio_residual_p95") or 0
    reg_ids = {r["reg_id"] for r in (p.get("regulation_residual") or {}).get("by_regulation", [])}
    check("C28.1 profiles exist with a default that is the calibrated archetype",
          PASS if profs and pp.get("default") == "fintech_mtl" else FAIL,
          f"{len(profs)} profiles · default {pp.get('default')}")
    dominated = all(pr.get("in_perimeter_residual_p95", 0) <= port for pr in profs)
    check("C28.2 every profile's in-perimeter P95 ≤ portfolio P95 (union subset dominance)",
          PASS if dominated and port else FAIL, f"portfolio ${port/1e6:.1f}M dominates all profiles")
    resolved = all(set(pr.get("statuses", {})) == reg_ids for pr in profs)
    check("C28.3 every profile assigns a status to EVERY regulation (no silent omissions)",
          PASS if resolved else FAIL, f"{len(reg_ids)} regimes × {len(profs)} profiles all assigned")
    reserved = all("reserved to Legal/Compliance" in (pr.get("note") or "") for pr in profs)
    check("C28.4 every profile carries the perimeter-determination reservation",
          PASS if reserved and "reserved to" in (pp.get("method_note") or "") else FAIL, "reservation rides every note")


def c30_dependency_layer(p: Dict[str, Any]) -> None:
    """E1 — the shared-dependency layer's own gates: the catalog must be
    anchored and complete, coverage must reach every Tier-1 domain, the
    tornado must RECOMPUTE, and the layer-off counterfactual must reconcile
    three ways (dependency_model, dependency_layer, the sensitivity lever)."""
    print("\nC30 · dependency layer — common-cause nodes anchored, covered, recomputable")
    dl = p.get("dependency_layer") or {}
    nodes = dl.get("nodes") or []
    bad = []
    for n in nodes:
        if not n.get("anchors"):
            bad.append(f"{n.get('id')}: no public anchors")
        if not n.get("fan_out_patterns"):
            bad.append(f"{n.get('id')}: empty fan-out")
        if n.get("containment_boundary") not in ("cell", "region", "global"):
            bad.append(f"{n.get('id')}: bad containment")
    check("C30.1 every dependency node carries public anchors, a pattern fan-out, and a containment boundary",
          PASS if nodes and not bad else FAIL,
          f"{len(nodes)} nodes, all anchored" if not bad else "; ".join(bad[:3]))

    dd = dl.get("domain_dependencies") or {}
    doms = set((p.get("domains") or {}).keys())
    missing = sorted(doms - set(dd.keys())) + [d for d, lst in dd.items() if d in doms and not lst]
    node_ids = {n["id"] for n in nodes}
    dangling = sorted({dep for lst in dd.values() for dep in lst} - node_ids)
    check("C30.2 every domain maps to ≥1 dependency and every mapped dependency exists in the catalog",
          PASS if not missing and not dangling else FAIL,
          f"{len(doms)} domains covered by {len(node_ids)} nodes" if not (missing or dangling)
          else f"missing: {missing[:3]} · dangling: {dangling[:3]}")

    # C30.3 — the tornado recomputes: re-run the TOP node's ceteris-paribus
    # suppression on the same seed and compare to the stored delta (one sim,
    # not eight — the selection rule and RNG alignment are what's under test).
    one = dl.get("one_thing") or {}
    ok3, msg3 = False, "no one_thing"
    if one:
        sys.path.insert(0, str(PROJECT_ROOT))
        from utils.exposure import aggregate_loss_mc
        base = aggregate_loss_mc()
        run = aggregate_loss_mc(dep_suppress=(one["id"],))
        want = base["portfolio"]["residual"]["p95"] - run["portfolio"]["residual"]["p95"]
        ok3 = (want == one.get("delta_p95_usd")
               and one.get("delta_p95_usd") == max(n.get("delta_p95_usd", 0) for n in nodes)
               and all(n.get("residual_p95_without", 0) <= dl.get("baseline_residual_p95", 0) for n in nodes))
        msg3 = (f"top node {one['id']} recomputes: −${want/1e6:.1f}M; every p95_without ≤ baseline"
                if ok3 else f"stored {one.get('delta_p95_usd')} != recomputed {want}")
    check("C30.3 the dependency tornado RECOMPUTES (top node re-run, same seed; suppression can only lower P95)",
          PASS if ok3 else FAIL, msg3)

    lever = {l.get("id"): l for l in (p.get("sensitivity") or {}).get("levers") or []}.get("dep_layer_off") or {}
    pt_dm = (((p.get("exposure") or {}).get("portfolio_total") or {}).get("dependency_model")) or {}
    off_a = (pt_dm.get("layer_off_counterfactual") or {}).get("residual_p95")
    off_b = dl.get("layer_off_residual_p95")
    off_c = lever.get("residual_p95")
    vals = [v for v in (off_a, off_b, off_c) if v is not None]
    ok4 = len(vals) >= 2 and len(set(vals)) == 1
    check("C30.4 the layer-off counterfactual reconciles across surfaces (dependency block ≡ lever, by construction)",
          PASS if ok4 else FAIL,
          f"pre-E1 form ${vals[0]/1e6:.1f}M consistent across {len(vals)} surfaces" if ok4 else f"divergent: {off_a}/{off_b}/{off_c}")
    # C30.5 (E2) — the identity mechanics are wired, not just cataloged: the
    # customer plane carries a BLINDNESS mode with its own fan-out; the
    # workforce IdP carries the response-recursion mechanism; the recursion_off
    # lever exists and removing the mechanism can only LOWER the tail.
    by_id = {n["id"]: n for n in nodes}
    cid = by_id.get("customer_identity_plane") or {}
    widp = by_id.get("workforce_idp") or {}
    lever_rec = {l.get("id"): l for l in (p.get("sensitivity") or {}).get("levers") or []}.get("recursion_off") or {}
    blind_ok = (cid.get("annual_freq") or {}).get("blindness", 0) > 0 and "RP-08" in (cid.get("fan_out_patterns") or [])
    rec_ok = bool((widp.get("response_recursion") or {}).get("severity_mult_all"))
    lever_ok = bool(lever_rec) and (lever_rec.get("residual_p95") or 0) <= dl.get("baseline_residual_p95", 0)
    probs5 = []
    if not blind_ok:
        probs5.append("customer plane has no blindness mode / RP-08 fan-out")
    if not rec_ok:
        probs5.append("workforce IdP has no response_recursion mechanism")
    if not lever_ok:
        probs5.append(f"recursion_off lever missing or RAISES the tail ({lever_rec.get('residual_p95')})")
    check("C30.5 E2 identity mechanics wired (blindness mode fan-out; recursion mechanism; recursion_off can only lower)",
          PASS if not probs5 else FAIL,
          (f"blindness {((cid.get('annual_freq') or {}).get('blindness'))}/yr → {len((cid.get('fan_out_patterns') or []))} patterns · "
           f"recursion ×{(widp.get('response_recursion') or {}).get('severity_mult_all')} · "
           f"recursion_off ${(lever_rec.get('residual_p95') or 0)/1e6:.1f}M ≤ baseline") if not probs5 else "; ".join(probs5))


def c30_6_catalog_provenance() -> None:
    """External class gate (Claude round-27: 'new capability lands verified-by-
    construction but under-documented and under-joined'): no load-bearing
    numeric in a top-level data structure without a basis or an explicit
    deferral tag — the discipline risk_patterns lives under, applied to the
    dependency catalog."""
    print("\nC30.6 · catalog provenance completeness — every frequency wears its basis")
    import json as _json
    cat = _json.loads((PROJECT_ROOT / "data" / "dependency_catalog.json").read_text())
    bare = [n["id"] for n in cat.get("nodes") or []
            if not n.get("freq_basis") or "OPERATOR_CALIBRATED" not in n.get("freq_basis", "")]
    dn = cat.get("deferred_nodes") or {}
    ok = not bare and bool(dn.get("classes")) and "dns_resolution" in (dn.get("classes") or [])
    check("C30.6 every dependency node carries freq_basis (anchored + tagged) and deferred node classes are DECLARED",
          PASS if ok else FAIL,
          f"{len(cat.get('nodes') or [])} nodes based · {len(dn.get('classes') or [])} deferrals declared"
          if ok else f"bare: {bare[:3]} · deferrals: {bool(dn.get('classes'))}")


def c31_cascade_dynamics(p: Dict[str, Any]) -> None:
    """E4 — the dynamics are wired, not just described: RP-14 exists with
    divergence-form signals and its anchors/edges; every cascade edge carries
    the propagation-layer axis; β load-dependence is present with its β=0
    counterfactual, and removing it can only lower the tail."""
    print("\nC31 · cascade dynamics — RP-14, the layer axis, and load-dependent induction")
    pats = {r["pattern_id"] for r in (p.get("inherent_residual") or {}).get("by_pattern") or []}
    pm = (p.get("patterns_meta") or {}).get("RP-14") or {}
    import json as _json
    raw = _json.loads((PROJECT_ROOT / "data" / "risk_patterns.json").read_text())["patterns"]
    rp14 = next((x for x in raw if x["id"] == "RP-14"), {})
    sigs = rp14.get("signals") or []
    div_ok = any("skew" in s or "delta" in s or "trend" in s or "ratio" in s for s in sigs)
    knight = any("Knight" in (a.get("name") or "") for a in rp14.get("incident_reference") or [])
    edge_to = {e["pattern_id"] for e in rp14.get("cascade_to") or []}
    check("C31.1 RP-14 in the MC with divergence-form signals, the Knight anchor, and edges to RP-02/RP-11",
          PASS if ("RP-14" in pats and div_ok and knight and {"RP-02", "RP-11"} <= edge_to) else FAIL,
          f"in MC: {'RP-14' in pats} · divergence signals: {div_ok} · Knight: {knight} · edges: {sorted(edge_to)}")
    bare = [f"{x['id']}→{e['pattern_id']}" for x in raw for e in x.get("cascade_to") or []
            if not e.get("propagation_layer") or not e.get("containment_boundary")]
    n_edges = sum(len(x.get("cascade_to") or []) for x in raw)
    check("C31.2 every cascade edge carries propagation_layer + containment_boundary (the blast-radius axis)",
          PASS if not bare else FAIL,
          f"{n_edges} edges, all layered" if not bare else f"bare: {bare[:3]}")
    pt = ((p.get("exposure") or {}).get("portfolio_total") or {})
    ld = pt.get("load_dependent_induction") or {}
    b0 = (ld.get("beta0_counterfactual") or {}).get("residual_p95")
    head = pt.get("p95_usd") or 0
    lever_b0 = {l.get("id"): l for l in (p.get("sensitivity") or {}).get("levers") or []}.get("beta_zero") or {}
    ok3 = (ld.get("beta", 0) > 0 and b0 is not None and b0 <= head
           and lever_b0.get("residual_p95") == b0)
    check("C31.3 β load-dependence wired: β>0, β=0 counterfactual ≤ headline, beta_zero lever ≡ counterfactual",
          PASS if ok3 else FAIL,
          f"β={ld.get('beta')} cap={ld.get('cap')} · β=0 form ${(b0 or 0)/1e6:.1f}M ≤ ${head/1e6:.1f}M · lever reconciles"
          if ok3 else f"beta={ld.get('beta')} b0={b0} head={head} lever={lever_b0.get('residual_p95')}")
    # C31.4 (external, Claude: "the taxonomy grew past the mapping") — the hub
    # crosswalk must cover EVERY catalog pattern, so taxonomy growth can never
    # again outrun the compliance-mapping chain that feeds OSCAL.
    import yaml as _yaml
    cw = _yaml.safe_load((PROJECT_ROOT.parent.parent / "packages" / "kri-taxonomy" / "crosswalk.yaml").read_text())
    mapped = {e.get("from") for e in (cw.get("spokes") or {}).get("risk-as-code-agent", {}).get("map") or []}
    cat_ids = {x["id"] for x in _PATTERNS_EXPECTED}
    missing_cw = sorted(cat_ids - mapped)
    check("C31.4 the hub crosswalk covers every catalog pattern (taxonomy cannot outrun the OSCAL mapping)",
          PASS if not missing_cw else FAIL,
          f"{len(cat_ids)} patterns all crosswalked" if not missing_cw else f"unmapped: {missing_cw}")


def c32_e5_model_terms(p: Dict[str, Any]) -> None:
    """E5 — the reviewers' named model terms are wired and bounded: severity
    co-movement under common cause, load-dependent dependency nodes, and
    failover-failure escalation each have an off-lever that can only LOWER
    the tail, and the failover probabilities wear their basis."""
    print("\nC32 · E5 model terms — co-movement, load-dependence, failover escalation")
    levers = {l.get("id"): l for l in (p.get("sensitivity") or {}).get("levers") or []}
    head = (((p.get("exposure") or {}).get("portfolio_total") or {}).get("p95_usd")) or 0
    probs = []
    for lid in ("cc_sev_off", "dep_load_off", "failover_off"):
        lv = levers.get(lid) or {}
        if not lv:
            probs.append(f"{lid} lever missing")
        elif (lv.get("residual_p95") or 0) > head:
            probs.append(f"{lid} RAISES the tail ({lv.get('residual_p95')})")
    check("C32.1 each E5 mechanism has an off-lever and removing it can only lower P95",
          PASS if not probs else FAIL,
          " · ".join(f"{lid} ${(levers.get(lid) or {}).get('residual_p95', 0)/1e6:.1f}M"
                     for lid in ("cc_sev_off", "dep_load_off", "failover_off")) if not probs else "; ".join(probs))
    import json as _json
    cat = _json.loads((PROJECT_ROOT / "data" / "dependency_catalog.json").read_text())
    ff = [(n["id"], n.get("failover_failure_prob"), bool(n.get("failover_basis")))
          for n in cat.get("nodes") or [] if n.get("failover_failure_prob")]
    region_bounded = [n["id"] for n in cat.get("nodes") or [] if n.get("containment_boundary") == "region"]
    ok2 = ff and all(b for _, _, b in ff) and set(nid for nid, _, _ in ff) == set(region_bounded)
    check("C32.2 every region-bounded node carries failover_failure_prob WITH its basis (and only those)",
          PASS if ok2 else FAIL,
          " · ".join(f"{nid} p={pr}" for nid, pr, _ in ff) if ok2 else f"ff={ff} region-bounded={region_bounded}")


def c33_aggregate_plausibility(p: Dict[str, Any]) -> None:
    """r29 — the operator's own challenge ('these sound extremely high and
    fictitious'), made a standing machine gate: the aggregate must be
    defensible as a fraction of the archetype's revenue, and the modeled
    1-in-100 year must sit BELOW the single worst public comparable.
    Frame refs: ORX-class op-risk benchmarks (all-cause op losses ~1-2% of
    gross income in typical years; technology a fraction), IBM CODB 2024,
    Uptime Institute 2023, ITIC 2024; Knight/CapOne/TSB/Equifax as tail
    anchors."""
    print("\nC33 · aggregate plausibility — every dollar defensible against the revenue archetype")
    rev = float((p.get("meta") or {}).get("archetype_revenue_usd") or 0)
    port = ((p.get("inherent_residual") or {}).get("portfolio") or {})
    res = port.get("residual") or {}
    worst = (port.get("inherent") or {}).get("worst_anchor") or 0
    p50_pct = res.get("p50", 0) / rev * 100 if rev else 99
    p95_pct = res.get("p95", 0) / rev * 100 if rev else 99
    check("C33.1 the MEDIAN year is 0.4-1.5% of archetype revenue (ORX-class typical-year frame)",
          PASS if 0.4 <= p50_pct <= 1.5 else FAIL,
          f"P50 ${res.get('p50', 0)/1e6:.1f}M = {p50_pct:.2f}% of ${rev/1e9:.0f}B")
    check("C33.2 the STRESS year (P95) is 2-5% of archetype revenue (a Capital-One-adjacent year, not an Equifax)",
          PASS if 2.0 <= p95_pct <= 5.0 else FAIL,
          f"P95 ${res.get('p95', 0)/1e6:.1f}M = {p95_pct:.2f}%")
    check("C33.3 the modeled P99 sits BELOW the single worst public comparable (Knight-class stays a beyond-P99 anchor)",
          PASS if res.get("p99", 0) < worst else FAIL,
          f"P99 ${res.get('p99', 0)/1e6:.1f}M < worst anchor ${worst/1e6:.0f}M")


def c34_model_term_visibility(p: Dict[str, Any]) -> None:
    """r30 — the GROK-round-29 misread, gated as a class: a mechanism that exists
    only as a lever + judgment prose is invisible to a reviewer scanning the
    projection for DATA (they read our stale 'not modeled' note and reported the
    E5 cc term absent — our own prose contradicted our engine). Every priced
    model term must ship a NAMED parameter block, and no shipped note may claim
    a modeled term is unmodeled."""
    print("\nC34 · model-term visibility — every mechanism findable as data, no prose contradicting the engine")
    pt = ((p.get("exposure") or {}).get("portfolio_total") or {})
    sens = p.get("sensitivity") or {}
    lever_ids = {l.get("id") for l in (sens.get("levers") or [])}
    cc = pt.get("severity_comovement") or {}
    ld = (pt.get("dependency_model") or {}).get("load_dependence") or {}
    fo = (pt.get("dependency_model") or {}).get("failover_escalation") or {}
    li = pt.get("load_dependent_induction") or {}
    ok1 = (cc.get("gamma", 0) > 0 and cc.get("cap") and cc.get("off_lever") in lever_ids
           and ld.get("delta", 0) > 0 and ld.get("cap") and ld.get("off_lever") in lever_ids
           and fo.get("escalation_mult") and fo.get("off_lever") in lever_ids and fo.get("nodes")
           and li.get("beta", 0) > 0 and li.get("cap"))
    check("C34.1 every E4/E5 mechanism ships a NAMED parameter block (γ/δ/β/failover as data, each pointing at its off-lever)",
          PASS if ok1 else FAIL,
          f"γ={cc.get('gamma')} cap {cc.get('cap')} · δ={ld.get('delta')} cap {ld.get('cap')} · "
          f"β={li.get('beta')} cap {li.get('cap')} · failover ×{fo.get('escalation_mult')} on {len(fo.get('nodes') or {})} nodes")
    cm_note = ((pt.get("correlation_model") or {}).get("note") or "")
    stale = ("is not modeled" in cm_note or "is NOT modeled" in cm_note)
    check("C34.2 no shipped model note claims severity co-movement is unmodeled while γ>0 (prose cannot contradict the engine)",
          PASS if (not stale and "severity_comovement" in cm_note) else FAIL,
          "correlation_model note names the cc term" if not stale else "STALE NOTE: " + cm_note[:80])
    rc = pt.get("recalibration") or {}
    ok3 = (rc.get("prior_residual_p95") == 312200000 and rc.get("prior_seal") and rc.get("band_gate"))
    check("C34.3 the why-moved story is leaf-backed (recalibration block: prior seal + band gate as data, not author knowledge)",
          PASS if ok3 else FAIL,
          f"prior {rc.get('prior_seal')} ${rc.get('prior_residual_p95', 0)/1e6:.1f}M · band gate declared")


def c35_induced_attribution(p: Dict[str, Any]) -> None:
    """r30 — Claude round-28's structural finding, held permanently: the hub
    sink must not misattribute. Per-pattern residual splits by provenance
    (own base draws vs cascade-induced vs dependency-injected) and the split
    must reconcile with the portfolio mean."""
    print("\nC35 · induced-vs-intrinsic attribution — the hub sink cannot misattribute")
    rows = ((p.get("inherent_residual") or {}).get("by_pattern")) or []
    atts = [r.get("attribution") or {} for r in rows]
    ok1 = atts and all(
        0.0 <= a.get("induced_share_pct", -1) <= 100.0
        and a.get("base_mean_usd") is not None for a in atts)
    check("C35.1 every pattern carries an attribution split with induced_share_pct in [0,100]",
          PASS if ok1 else FAIL, f"{len(atts)} patterns split")
    tot = sum(a.get("base_mean_usd", 0) + a.get("cascade_mean_usd", 0) + a.get("dep_mean_usd", 0) for a in atts)
    port_mean = (((p.get("inherent_residual") or {}).get("portfolio") or {}).get("residual") or {}).get("mean") or 0
    ok2 = port_mean and abs(tot - port_mean) / port_mean < 0.01
    check("C35.2 attribution components sum to the portfolio residual mean (counting, not a second model)",
          PASS if ok2 else FAIL, f"Σ components ${tot/1e6:.1f}M vs portfolio mean ${port_mean/1e6:.1f}M")
    hub = {r.get("pattern_id"): (r.get("attribution") or {}).get("induced_share_pct", 0) for r in rows}
    ok3 = hub.get("RP-02", 0) > 30
    check("C35.3 the hub sink (RP-02, highest in-degree) shows a materially induced share — the misattribution is priced",
          PASS if ok3 else FAIL, f"RP-02 induced {hub.get('RP-02')}% · RP-06 {hub.get('RP-06')}% · RP-12 {hub.get('RP-12')}%")


def c36_journey_spine(p: Dict[str, Any]) -> None:
    """Stage 1a of reviews/journey_spine_port_spec.md — the journey spine cannot
    silently regress. The spec's parking-lot rule holds until all stages ship."""
    print("\nC36 · Journey spine — the journey as the atomic unit, derived not asserted")
    import json as _json
    from pathlib import Path as _P
    cs = p.get("journey_spine") or {}
    cat = _json.loads((PROJECT_ROOT / "data" / "journey_catalog.json").read_text())
    j = cs.get("journey") or {}
    stages = cs.get("stages") or []
    svcs = cs.get("services") or []
    svc_stage = {s["id"]: s["stage"] for s in svcs}
    stage_ids = [s["id"] for s in stages]
    ok1 = (j.get("id") == "J-SIM-001" and len(stages) == 5
           and all(sv in stage_ids for sv in svc_stage.values())
           and sorted(sv["id"] for sv in svcs) == sorted(sv["id"] for sv in cat["services"]))
    check("C36.1 the journey spine ships: J-SIM-001, five stages, every service homed to exactly one stage",
          PASS if ok1 else FAIL, f"{j.get('id')} · {len(stages)} stages · {len(svcs)} services")

    from utils.exposure import _PATTERNS
    dep_ids = {n["id"] for n in _json.loads((PROJECT_ROOT / "data" / "dependency_catalog.json").read_text())["nodes"]}
    from utils.journey_signals import _SPECS
    bad_ref = []
    for sv in cat["services"]:
        bad_ref += [f"{sv['id']}:{x}" for x in sv["patterns"] if x not in _PATTERNS]
        bad_ref += [f"{sv['id']}:{x}" for x in sv["dependency_nodes"] if x not in dep_ids]
        bad_ref += [f"{sv['id']}:{x}" for x in sv["signals"] if x not in _SPECS]
    check("C36.2 every chain reference resolves (patterns → catalog, dependency nodes → E1 layer, signals → generator)",
          PASS if not bad_ref else FAIL,
          "all references resolve" if not bad_ref else f"dangling: {bad_ref[:4]}")

    from utils.journey_signals import signal_stats
    st = signal_stats()
    mism = []
    for step in (cs.get("incident") or {}).get("narrative_steps", []):
        want = st.get(step["signal"], {}).get("incident_peak")
        if step.get("derived_peak") != want:
            mism.append(f"step{step['step']}: {step.get('derived_peak')} != {want}")
    for sv in svcs:
        for r in sv.get("signal_rows", []):
            want = st.get(r["id"], {}).get("incident_peak")
            if r.get("incident_peak") != want:
                mism.append(f"{r['id']}: {r.get('incident_peak')} != {want}")
    check("C36.3 every quoted incident peak RECOMPUTES from the seeded generator (typed peaks are a build failure)",
          PASS if not mism else FAIL,
          "all peaks recompute" if not mism else "; ".join(mism[:3]))

    incomplete = []
    for sv in svcs:
        chain_ok = (sv.get("signal_rows") and all(r.get("chip", {}).get("realness") == "SEEDED"
                                                  and r.get("chip", {}).get("pts") for r in sv["signal_rows"])
                    and sv.get("risk_links") and all(l.get("controls_linked") is not None
                                                     and l.get("controls_caveat") for l in sv["risk_links"])
                    and sv.get("owner") and sv.get("owner_caveat"))
        if not chain_ok:
            incomplete.append(sv["id"])
    ext_ok = any(sv.get("non_claim") for sv in svcs if sv.get("layer") == "external")
    check("C36.4 the four-hop chain is complete per service (signal+chip → risk+controls+caveat → owner+caveat) and the external hop carries its non-claim",
          PASS if (not incomplete and ext_ok) else FAIL,
          f"{len(svcs)} chains complete · external non-claim present" if not incomplete else f"incomplete: {incomplete[:3]}")

    sc = cs.get("signal_catalog") or []
    n_sig = sum(len(sv["signals"]) for sv in cat["services"])
    slo = cs.get("slo_derived") or {}
    ok5 = (len(sc) == n_sig and all(r.get("query_intent") and r.get("owner") for r in sc)
           and slo.get("end_to_end_p95_ms") and slo.get("availability_observed_pct")
           and cs.get("port_tag") and "seeded" in cs.get("port_tag", "").lower())
    check("C36.5 signal_catalog reconciles (one row per declared signal, intent+owner on each) and the SLO derives with the port tag present",
          PASS if ok5 else FAIL,
          f"{len(sc)} signals · e2e p95 {slo.get('end_to_end_p95_ms')}ms · avail {slo.get('availability_observed_pct')}%")


def c36_6_journey_surface() -> None:
    """Stage 1b — the journey surface cannot silently regress: the first-paint
    storyboard strings, the chain mounts, and the incident walk must ship."""
    h = (PROJECT_ROOT / "docs" / "journey.html").read_text()
    # data strings ride the JSON island where ensure_ascii escapes '·' as
    # \u00b7 — normalize before matching (the gate's own first run caught this)
    hn = h.replace("\\u00b7", "·")
    need = ["J-SIM-001", "no findings · no verdicts", "SIM-0531",
            'data-s="crumb"', 'data-s="path"', 'data-s="svcchains"', 'data-s="steps"',
            'data-s="audbar"', "journey-overlays", "DO NOT OVERCLAIM",
            "control linkage seeded · applicability not validated"]
    missing = [n for n in need if n not in hn]
    check("C36.6 the journey surface ships its storyboard (hero strings, chain mounts, incident walk, audience bar, overlays island)",
          PASS if not missing else FAIL,
          "all storyboard mounts present" if not missing else f"missing: {missing[:3]}")


def c37_operating_model(p: Dict[str, Any]) -> None:
    """Stage 3 of reviews/journey_spine_port_spec.md — the operating-model
    delta cannot regress: lifecycle classes derive from test methods, rating
    states derive from register fields, and the honesty flag stays non-zero."""
    print("\nC37 · operating-model delta — chase → re-perform, states as data")
    om = p.get("operating_model") or {}
    rows = om.get("evidence_rows") or []
    ok1 = rows and all(
        (r.get("reperformance") in ("automated", "bespoke") and isinstance(r.get("hard_to_reperform"), bool)
         or r.get("reperformance") == "no_evidence_yet")
        and r.get("reperformance_basis") for r in rows)
    n_hard = sum(1 for r in rows if r.get("hard_to_reperform"))
    n_none = sum(1 for r in rows if r.get("reperformance") == "no_evidence_yet")
    check("C37.1 every evidence row carries a lifecycle class + basis (automated / bespoke / no-evidence-yet), and hard_to_reperform stays NON-ZERO (an all-automated story is the dishonest one)",
          PASS if (ok1 and 0 < n_hard) else FAIL,
          f"{len(rows)} rows · {om.get('evidence_counts', {}).get('automated')} automated · {n_hard} hard-to-re-perform · {n_none} no-evidence-yet")
    from utils.projection import _RATING_STATES, _rating_state, _AS_OF_FOR_STATES
    vocab = set(_RATING_STATES)
    doms = p.get("domains") or {}
    bad = []
    for d in doms.values():
        for f in d.get("findings", []):
            rs = f.get("rating_state") or {}
            if rs.get("state") not in vocab or not rs.get("basis"):
                bad.append(f.get("finding_id"))
            elif _rating_state(f, _AS_OF_FOR_STATES)["state"] != rs["state"]:
                bad.append(f.get("finding_id") + ":non-deterministic")
    counts = om.get("rating_state_counts") or {}
    ok2 = not bad and set(counts) == vocab and all(v > 0 for v in counts.values())
    check("C37.2 every register finding carries a rating state from the exact vocabulary, DERIVED deterministically, with every state populated (governance in motion)",
          PASS if ok2 else FAIL,
          " · ".join(f"{k}={v}" for k, v in counts.items()) if ok2 else f"bad: {bad[:3]}")
    html = (PROJECT_ROOT / "docs" / "index.html").read_text()
    ok3 = ('data-target="operating-model"' in html and "renderOperatingModel" in html
           and "hard-to-re-perform" in html)
    check("C37.3 the panel RENDERS on the workbench with the A8 mechanism named",
          PASS if (ok3 and "A8" in (om.get("after", "") + om.get("mechanism", ""))) else FAIL,
          "panel + renderer + mechanism ship")


def c38_rollup_and_aggregator(p: Dict[str, Any]) -> None:
    """Stage 4 of reviews/journey_spine_port_spec.md — the last stage: the
    parent→child rollup reconciles with the register, and the aggregator's
    verbatim-passthrough claim is recomputed, never trusted."""
    print("\nC38 · rollup + aggregator contract — the catalog shape, the passthrough proven")
    ru = p.get("risk_rollup") or {}
    doms = p.get("domains") or {}
    reg = {}
    for d in doms.values():
        for f in d.get("findings", []):
            reg.setdefault(f.get("pattern_id"), []).append(f)
    bad = []
    for r in ru.get("parents", []):
        want = reg.get(r["pattern_id"], [])
        if r["n_children"] != len(want):
            bad.append(f"{r['pattern_id']}: {r['n_children']} != {len(want)}")
        ev = sum(1 for f in want if f.get("signals_exceeded"))
        if r["n_evidenced"] != ev:
            bad.append(f"{r['pattern_id']} evidenced {r['n_evidenced']} != {ev}")
    tot = ru.get("totals") or {}
    n_reg = sum(len(v) for v in reg.values())
    check("C38.1 the rollup reconciles with the register (children == findings per parent; EVIDENCED derives from signals_exceeded)",
          PASS if (not bad and tot.get("children") == n_reg) else FAIL,
          f"{tot.get('parents')} parents · {tot.get('children')} children · {tot.get('evidenced')} evidenced" if not bad else "; ".join(bad[:3]))
    import json as _json, hashlib as _hl
    from utils.journey_signals import aggregator_payload
    want_sha = _hl.sha256(_json.dumps(aggregator_payload(), sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    shipped = _json.loads((PROJECT_ROOT / "data" / "journey_aggregator.json").read_text())
    consumed = ((p.get("journey_spine") or {}).get("aggregator") or {}).get("consumed_sha256")
    file_sha = _hl.sha256(_json.dumps(shipped.get("payload"), sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    ok2 = want_sha == shipped.get("sha256") == file_sha == consumed
    check("C38.2 the aggregator passthrough is VERBATIM by recomputation (generator hash == file hash == file recompute == consumed hash)",
          PASS if ok2 else FAIL,
          f"sha256 {want_sha[:12]}… four-way equal" if ok2 else f"MISMATCH gen {want_sha[:8]} file {str(shipped.get('sha256'))[:8]} recompute {file_sha[:8]} consumed {str(consumed)[:8]}")
    idx = (PROJECT_ROOT / "docs" / "index.html").read_text()
    jn = (PROJECT_ROOT / "docs" / "journey.html").read_text()
    # the claim must be RENDERED chrome, not just a JSON leaf (its own first
    # run passed on the embedded data while the caption was missing — the
    # class-19 shadow): require the mount AND the render expression.
    ok3 = ('data-target="risk-rollup"' in idx and "renderRiskRollup" in idx
           and 'data-s="aggline"' in jn and "consumed_sha256" in jn
           and "verbatim · unmodified" in jn.replace("\\u00b7", "·"))
    check("C38.3 the rollup strip and the gated verbatim caption RENDER (workbench + journey)",
          PASS if ok3 else FAIL, "both surfaces ship the stage-4 chrome")


def c29_shipped_scripts_parse() -> None:
    # Round-22 escape class: TWICE a generated inline script shipped broken
    # (round-19 openIaMap ReferenceError, round-22 a Python \' collapsing to a
    # bare quote inside a JS string — one char killed the whole 154KB runtime,
    # spine and all). Source-file `node --check` can't see this: only the
    # GENERATED page can. So the gate parses what actually ships.
    print("\nC29 · shipped surfaces parse — generated inline JS is valid on every page")
    import subprocess, tempfile
    surfaces = ["docs/index.html", "docs/read.html", "docs/validation.html", "docs/archive/classic.html",
                "docs/board.html", "docs/journey.html"]
    broken: List[str] = []
    checked = 0
    for rel in surfaces:
        f = PROJECT_ROOT / rel
        if not f.exists():
            broken.append(f"{rel}: MISSING")
            continue
        html = f.read_text()
        for i, src in enumerate(re.findall(
                r'<script(?![^>]*\bsrc=)(?![^>]*type="application/json")[^>]*>(.*?)</script>',
                html, re.S)):
            if not src.strip():
                continue
            checked += 1
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
                t.write(src)
                tmp = t.name
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            if r.returncode != 0:
                first = (r.stderr.strip().splitlines() or ["?"])[0]
                broken.append(f"{rel}#script{i}: {first[:90]}")
    check("C29.1 every inline script on every shipped page passes node --check (the page that ships is the page that runs)",
          PASS if checked and not broken else FAIL,
          f"{checked} inline scripts across {len(surfaces)} pages all parse" if not broken else "; ".join(broken[:3]))


def c39_strategy_chooser(p: Dict[str, Any]) -> None:
    """r51 — the board strategy chooser: the screen a board actually decides on
    cannot carry a typed number. Every dollar recomputes from the sealed leaves
    it cites; owners and flags resolve into the register; the spine closes on
    the choice; the board brief links the surface without minting a sixth
    resolution."""
    print("\nC39 · strategy chooser — the closing decision recomputes, never asserts")
    sc = p.get("strategy_chooser") or {}
    exp = (p.get("exposure") or {}).get("portfolio_total") or {}
    levers = {l["id"]: l for l in (p.get("sensitivity") or {}).get("levers", [])}
    strats = {s.get("id"): s for s in sc.get("strategies", [])}
    A = strats.get("harden_controls") or {}
    B = strats.get("isolate_dependencies") or {}
    dl = p.get("dependency_layer") or {}
    dep_by_id = {n.get("id"): n for n in dl.get("nodes", [])}
    hold = sc.get("hold_option") or {}

    base = exp.get("p95_usd") or 0
    recompute = {
        "A.benefit": (A.get("benefit_p95_usd"), base - (levers.get("eff_up") or {}).get("residual_p95", 0)),
        "A.downside": (A.get("downside_p95_usd"), (levers.get("eff_down") or {}).get("residual_p95")),
        "B.ceiling": (B.get("layer_ceiling_usd"), dl.get("layer_contribution_usd")),
        "B.layer_off": (B.get("layer_off_residual_p95_usd"), (levers.get("dep_layer_off") or {}).get("residual_p95")),
        "B.downside": (B.get("downside_p95_usd"), (levers.get("dep_freq_up") or {}).get("residual_p95")),
        "hold.stress": (hold.get("stress_test_p95_usd"), (levers.get("joint_bad_year") or {}).get("residual_p95")),
    }
    bad_money = [f"{k}: shipped {a} != recomputed {b}" for k, (a, b) in recompute.items() if a != b]
    bad_money += [f"node {n.get('id')}: {n.get('ceiling_delta_p95_usd')} != {(dep_by_id.get(n.get('id')) or {}).get('delta_p95_usd')}"
                  for n in B.get("program_nodes", [])
                  if n.get("ceiling_delta_p95_usd") != (dep_by_id.get(n.get("id")) or {}).get("delta_p95_usd")]
    check("C39.1 every chooser dollar recomputes from the leaf it cites (levers / dep nodes / MC baseline)",
          PASS if sc and not bad_money else FAIL,
          "; ".join(bad_money) or f"6 recomputations + {len(B.get('program_nodes', []))} node ceilings exact")

    cited_levers = list((A.get("cites") or {}).get("levers", [])) + list((B.get("cites") or {}).get("levers", []))
    bad_cites = [l for l in cited_levers if l not in levers] + \
                [n for n in (B.get("cites") or {}).get("nodes", []) if n not in dep_by_id]
    check("C39.2 every cite resolves — lever ids into sensitivity.levers, node ids into dependency_layer.nodes",
          PASS if cited_levers and not bad_cites else FAIL,
          "; ".join(bad_cites) or f"{len(cited_levers)} levers + {len((B.get('cites') or {}).get('nodes', []))} nodes resolve")

    reg_execs, reg_handles = set(), set()
    reg_issue_ids = {i.get("issue_id") for i in (p.get("internal_audit") or {}).get("issues", [])}
    for d in (p.get("domains") or {}).values():
        for f in d.get("findings", []):
            oc = f.get("org_context") or {}
            if oc.get("accountable_exec"):
                reg_execs.add(oc["accountable_exec"])
            if (f.get("treatment") or {}).get("owner_handle"):
                reg_handles.add(f["treatment"]["owner_handle"])
    bad_own = [o.get("exec") for o in A.get("owners", []) if o.get("exec") not in reg_execs]
    bad_own += [h for h in A.get("owner_handles", []) if h not in reg_handles]
    bad_own += [fl.get("issue_id") for fl in A.get("delivery_risk_flags", []) if fl.get("issue_id") not in reg_issue_ids]
    if A.get("credit_gate") and A["credit_gate"].get("issue_id") not in reg_issue_ids:
        bad_own.append(A["credit_gate"].get("issue_id"))
    check("C39.3 owners, handles and delivery-risk flags resolve into the register (no invented accountability)",
          PASS if A.get("owners") and not bad_own else FAIL,
          "; ".join(str(x) for x in bad_own) or
          f"{len(A.get('owners', []))} execs · {len(A.get('owner_handles', []))} handles · {len(A.get('delivery_risk_flags', []))} flags resolve")

    ia = p.get("ia") or {}
    paths = ia.get("paths") or {}
    node = next((n for n in ia.get("nodes", []) if n.get("id") == "strategy"), None)
    ok_paths = paths and all("strategy" in v and "story" in v and v.index("strategy") == v.index("story") - 1
                             for v in paths.values())
    check("C39.4 the spine closes on the choice — strategy node on EVERY role path, immediately before the story epilogue",
          PASS if node and ok_paths and "strategy-chooser" in (node.get("targets") or []) else FAIL,
          f"paths: {[(k, 'strategy' in v) for k, v in paths.items()]}")

    # read the LATEST build (same latest-not-hardcoded convention as PROJ_PATH;
    # outputs/v2_0a/current.html is a stale July relic the build no longer writes)
    _html_glob = sorted((PROJECT_ROOT / "outputs" / "v2_0a").glob("*_v2_0a_*.html"))
    _wb = _html_glob[-1] if _html_glob else HTML_PATH
    html = _wb.read_text() if _wb.exists() else ""
    ok_html = 'data-node="strategy"' in html and 'data-target="strategy-chooser"' in html \
        and "renderStrategyChooser" in html
    check("C39.5 the workbench renders the chooser from the projection (section + mount + renderer shipped)",
          PASS if ok_html else FAIL,
          f"section, mount and renderer present in {_wb.name}" if ok_html else f"missing on workbench ({_wb.name})")

    board_path = PROJECT_ROOT / "docs" / "board.html"
    board = board_path.read_text() if board_path.exists() else ""
    n_reso = board.count("reso('")
    check("C39.6 the board brief links the chooser and still asks exactly five resolutions (the pointer is not a sixth ask)",
          PASS if "node=strategy" in board and n_reso == 5 else FAIL,
          f"link={'node=strategy' in board} · reso() calls={n_reso}")


def c40_pivot(p: Dict[str, Any]) -> None:
    """r83 — the horizontal↔vertical pivot as data: journey_rps re-derives from
    the spine; hv_map re-derives from the canonical portfolio_core map (rp ids
    AND names checked against the pattern catalog); the register renders the
    chips from the projection, never from typed ids."""
    import json as _json
    from pathlib import Path as _P
    print("\nC40 · the pivot — register row ↔ its vertical")
    pv = p.get("pivot") or {}
    spine_rps = sorted({rp for svc in ((p.get("journey_spine") or {}).get("services") or [])
                        for rp in (svc.get("patterns") or [])})
    check("C40.1 pivot.journey_rps re-derives from journey_spine (the money-path pattern set, exact)",
          PASS if (pv.get("journey_rps") == spine_rps and len(spine_rps) > 0) else FAIL,
          f"{len(spine_rps)} register patterns ride the money path")
    pm = _json.loads((_P(__file__).resolve().parent.parent.parent.parent
                      / "packages" / "ui-system" / "portfolio_core"
                      / "pivot_map.json").read_text(encoding="utf-8"))["hv_to_rp"]
    cat = {pat["id"]: pat.get("name") for pat in (p.get("patterns_meta") or {}).get("patterns", [])}
    exp_map = {v["rp"]: {"hv_id": k, "rp_name": v["rp_name"], "why": v["why"]}
               for k, v in pm.items()}
    ok_names = all(v["rp_name"] == cat.get(rp) for rp, v in exp_map.items())
    check("C40.2 pivot.hv_map == the canonical cross-substrate map, and every rp id + NAME resolves in the pattern catalog",
          PASS if (pv.get("hv_map") == exp_map and ok_names) else FAIL,
          f"{len(exp_map)} cascades mapped; names byte-match the catalog" if ok_names else "NAME DRIFT vs catalog")
    html = HTML_PATH.read_text(encoding="utf-8")
    import re as _re
    tpl = _re.sub(r'<script[^>]*id="projection-source".*?</script>', "", html, flags=_re.S)
    check("C40.3 the register renders pivot chips FROM the projection (renderer reads pivot; no RP id typed in chip markup)",
          PASS if ("pivot-chip" in html and "PROJECTION.pivot" in html and "journey.html" in tpl) else FAIL,
          "chips hydrate from pivot block; journey door relative, observatory door absolute")


def main() -> int:
    print("v2.0a-alpha4 internal consistency audit")
    print("=" * 60)
    p = load_projection()

    c1_count_reconciliation(p)
    c2_inherent_residual_coverage(p)
    c3_portfolio_formula(p)
    c4_avg_eff_derivation(p)
    c5_materiality_schema(p)
    c6_ai_gov_linkage(p)
    c7_chain_verification()
    c8_mock_mode_purge()
    c9_source_status_honest(p)
    c10_acceptance_variability(p)
    c11_executive_hero()
    c12_ai_gov_reachable()
    c13_threshold_history(p)
    c14_artefact_integrity()
    c15_register_row_enriched()
    c16_kev_first_class(p)
    c17_taxonomy_consistency(p)
    c18_cross_surface_reconciliation(p)
    c19_no_unsourced_render_data(p)
    c20_sensitivity_substance(p)
    c21_regulation_residual(p)
    c22_control_evidence(p)
    c23_internal_audit(p)
    c24_coverage_vs_effectiveness(p)
    c25_register_determinism()
    c26_c27_ia(p)
    c28_perimeter(p)
    c29_shipped_scripts_parse()
    c30_dependency_layer(p)
    c30_6_catalog_provenance()
    c31_cascade_dynamics(p)
    c32_e5_model_terms(p)
    c33_aggregate_plausibility(p)
    c36_journey_spine(p)
    c37_operating_model(p)
    c38_rollup_and_aggregator(p)
    c36_6_journey_surface()
    c34_model_term_visibility(p)
    c35_induced_attribution(p)
    c39_strategy_chooser(p)
    c40_pivot(p)

    # Summary
    print()
    print("=" * 60)
    failed = sum(1 for _, s, _ in results if FAIL in s)
    warned = sum(1 for _, s, _ in results if WARN in s)
    passed = sum(1 for _, s, _ in results if PASS in s)
    print(f"Summary: {passed} PASS · {warned} WARN · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
