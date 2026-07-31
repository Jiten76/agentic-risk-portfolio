"""
exposure — v2.0a step 2 — frequency-aware expected loss computation.

Replaces v1.4's "3 methodologies" hack with explicit frequency × severity.

Per amendment A3, each pattern carries `exposure_model`:
  - incident_frequency_per_year: { p50, p95, derivation: { ... } }
  - severity_distribution:        { p50_usd, p95_usd, worst_anchor_usd, basis }

Expected loss per pattern = frequency × severity (both at the same percentile).
Portfolio total = sum across firing patterns weighted by RAG factor.

This module is pure: pattern definitions in → exposure projection out.
Consumed by utils.projection.

Per A11 reproducibility: no I/O, no time-dependent values, no RNG.
"""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


_PATTERNS_FILE = Path(__file__).resolve().parent.parent / "data" / "risk_patterns.json"
_DEPS_FILE = Path(__file__).resolve().parent.parent / "data" / "dependency_catalog.json"


def _load_patterns() -> Dict[str, Dict[str, Any]]:
    raw = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in raw.get("patterns", [])}


_PATTERNS = _load_patterns()


def load_dependency_catalog() -> Dict[str, Any]:
    return json.loads(_DEPS_FILE.read_text(encoding="utf-8"))


_DEPS = load_dependency_catalog()


# ── seeded Monte-Carlo aggregate loss distribution (the CORRECT roll-up) ──────

def _poisson(rng, lam: float) -> int:
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


# Cascade propagation: declared edge strength → per-incident induction probability.
# OPERATOR_CALIBRATED judgment values — a synthetic demonstrator has no co-occurrence
# history to fit; disclosed as such in correlation_model.provenance. Production would
# fit these from internal incident lineage (which incidents actually co-fired).
_CASCADE_STRENGTH_P = {"high": 0.40, "medium": 0.20, "low": 0.10}


@lru_cache(maxsize=32)
def _simulate(seed: int, trials: int, cascade: bool, freq_mult: float, sev_mult: float,
              eff_delta: float, cascade_mult: float, generations: int,
              sev_shock_sigma: float = 0.0, dep_layer: bool = True,
              dep_suppress: tuple = (), dep_freq_mult: float = 1.0,
              dep_recursion: bool = True, beta: float = 0.10, beta_cap: float = 1.5,
              cc_gamma: float = 0.10, dep_load_delta: float = 0.05, failover: bool = True):
    """The ONE trial engine — spec build + seeded trial loop, shared verbatim by
    aggregate_loss_mc AND regulation_residual_view so the two can never drift.
    Returns (specs, n_edges, inh_tot_unsorted, res_tot_unsorted, per_inh, per_res);
    per_* dicts are TRIAL-ORDERED lists (index t = trial t) — callers must not
    mutate them (sort copies).

    E1 — the shared-dependency layer (common-cause events). Pattern-to-pattern
    cascade edges cannot express an AWS region loss, a customer-auth-plane
    outage, an etcd quorum loss: one structural event UNDER several risks at
    once. Per trial, each dependency node draws Poisson degraded/loss events;
    a fired node injects incidents across its declared fan-out — several
    patterns, same trial-year, severity-multiplied — which is exactly the
    correlated fat tail a Head of Technology Risk carries in their head and
    the pre-E1 model could not draw.

    RNG-STREAM ALIGNMENT (the counterfactual contract): dependency events AND
    the severities of their induced incidents are drawn EVERY run in identical
    order, regardless of dep_layer / dep_suppress — suppression only zeroes a
    node's loss CONTRIBUTION. So `dep_layer=False` and every per-node
    suppression run share the base run's exact trial stream: the deltas are
    ceteris-paribus, not sampling noise."""
    rng = random.Random(seed)
    dep_nodes = _DEPS.get("nodes") or []
    specs = []
    for pid, p in _PATTERNS.items():
        em = p.get("exposure_model") or {}
        f = em.get("incident_frequency_per_year") or {}
        s = em.get("severity_distribution") or {}
        cc = p.get("compensating_controls") or {}
        median = float(s.get("p50_usd") or 0)
        p95 = float(s.get("p95_usd") or 0)
        edges = []
        if cascade:
            for e in p.get("cascade_to") or []:
                dst = e.get("pattern_id")
                prob = _CASCADE_STRENGTH_P.get(e.get("strength", ""), 0.0) * cascade_mult
                if dst in _PATTERNS and prob > 0:
                    edges.append((dst, min(0.95, prob)))
        median_adj = median * sev_mult
        specs.append({
            "id": pid,
            "lam": float(f.get("p50") or 0) * freq_mult,
            "mu": math.log(median_adj) if median_adj > 0 else 0.0,
            "sigma": (math.log(p95) - math.log(median)) / 1.645 if (p95 > median > 0) else 0.5,
            "eff": max(0.0, min(95.0, float(cc.get("avg_effectiveness_pct") or 0) + eff_delta)),
            "anchor": int(float(s.get("worst_anchor_usd") or 0)),
            "anchor_basis": s.get("worst_anchor_basis") or s.get("basis") or "",
            "edges": edges,
        })
    n_edges = sum(len(sp["edges"]) for sp in specs)
    inh_tot, res_tot = [], []
    per_inh = {sp["id"]: [] for sp in specs}
    per_res = {sp["id"]: [] for sp in specs}
    # r30 (external finding, Claude round-28: the hub sink misattributes) —
    # per-pattern residual split by PROVENANCE: own base draws vs cascade-
    # induced vs dependency-injected. Pure counting on draws the loop already
    # makes — no RNG consumed, no number moved; induced_share_pct tells a CRO
    # whether to harden the pattern or what FEEDS it.
    prov_base = {sp["id"]: 0.0 for sp in specs}
    prov_casc = {sp["id"]: 0.0 for sp in specs}
    prov_dep = {sp["id"]: 0.0 for sp in specs}
    suppressed = set(dep_suppress)
    # E4: expected annual concurrent incidents — the load-dependence reference
    # point (base Poisson means + expected dependency-injected incidents).
    exp_base = sum(sp["lam"] for sp in specs)
    exp_concurrent = exp_base
    if dep_layer:
        for nd in dep_nodes:
            if nd["id"] in suppressed:
                continue
            af = nd.get("annual_freq") or {}
            fo = nd.get("fan_out") or {}
            for mode in ("loss", "blindness"):
                per_event = sum(int(f.get("induced_incidents") or 1) for f in fo.get(mode) or [])
                exp_concurrent += float(af.get(mode) or 0.0) * dep_freq_mult * per_event
    for _ in range(trials):
        # 1. base incident counts — independent Poisson draws per pattern
        counts = {sp["id"]: _poisson(rng, sp["lam"]) for sp in specs}
        # 1.5 E1 · shared-dependency common-cause events. Draws happen every
        #     run in identical order (see docstring) — suppression only zeroes
        #     the contribution. dep_events[i] = (node_id, [(pattern_id, mult), …])
        #     ATTRIBUTION JUDGMENT (logged, lever-bounded): only structural
        #     LOSS events inject. Base per-pattern frequencies are all-cause
        #     calibrated — routine dependency DEGRADATION is already inside
        #     them; injecting it again would double-count the expected year.
        #     Loss events (region gone, auth plane down, etcd quorum lost) are
        #     the rare common-cause tail the per-pattern rates cannot carry,
        #     because they hit several patterns in the SAME year. Degraded-mode
        #     data stays in the catalog for the E2 divergence KRIs.
        #     E2 adds the BLINDNESS mode (customer identity plane: verification
        #     degraded, plane up — an ATO/recovery-abuse wave). Blindness is a
        #     structural common-cause state, NOT routine degradation, so it
        #     injects alongside loss; degraded stays embedded in base rates.
        # E5(2) · load-dependent dependency nodes: loss frequency scales with
        #     the trial's BASE-incident excess — the identity plane is likelier
        #     to fail when load is already elevated. Uses base counts only (no
        #     suppression input), so all counterfactual runs stay stream-aligned.
        base_excess = max(0.0, sum(counts.values()) - exp_base)
        dep_lam_mult = (min(1.25, 1.0 + dep_load_delta * base_excess)
                        if dep_load_delta > 0 else 1.0)
        dep_events = []
        recursion_mult = 1.0
        n_active_loss = 0
        for nd in dep_nodes:
            af = nd.get("annual_freq") or {}
            fo = nd.get("fan_out") or {}
            for mode in ("loss", "blindness"):
                lam_mode = float(af.get(mode) or 0.0) * dep_freq_mult
                if mode == "loss":
                    lam_mode *= dep_lam_mult
                n_ev = _poisson(rng, lam_mode)
                for _e in range(n_ev):
                    # E5(3) · the multi-region term: region-bounded nodes carry a
                    # failover_failure_prob — the failover ITSELF fails (GitHub
                    # 2018 split-brain class) and the event escalates ×1.5.
                    # The draw is consumed for EVERY loss event of such nodes,
                    # keeping suppression runs stream-aligned.
                    esc = 1.0
                    ffp = float(nd.get("failover_failure_prob") or 0.0)
                    if mode == "loss" and ffp > 0:
                        if rng.random() < ffp and failover:
                            esc = 1.5
                    inj = []
                    for f in fo.get(mode) or []:
                        for _i in range(int(f.get("induced_incidents") or 1)):
                            inj.append((f["pattern_id"], float(f.get("severity_mult") or 1.0) * esc))
                    dep_events.append((nd["id"], inj))
                    if mode == "loss" and dep_layer and nd["id"] not in suppressed:
                        n_active_loss += 1
                    # E2 — the recursion, as a mechanism (Meta 2021-10-04): an
                    # ACTIVE loss of a response_recursion node multiplies every
                    # severity this trial-year — responders are locked out of
                    # the consoles they respond with. No RNG consumed, so
                    # suppression stays stream-aligned.
                    rr = nd.get("response_recursion") or {}
                    if (mode == "loss" and rr and dep_recursion and dep_layer
                            and nd["id"] not in suppressed):
                        recursion_mult = max(recursion_mult, float(rr.get("severity_mult_all") or 1.0))
        # 2. cascade propagation along the declared cascade_to edges: each incident in
        #    the current frontier tests each of its edges A→B once. Truncated at
        #    `generations` hops (default 1) — see aggregate_loss_mc's docstring for
        #    why, and the gen-2 sensitivity lever for the truncation cost (~+10% P95).
        induced = dict.fromkeys(counts, 0)
        frontier = counts
        # E4 — load-dependent induction (external finding, Claude: constant-
        # probability branching structurally cannot produce "explodes out of
        # nowhere"): the induction probability rises with the trial-year's
        # CONCURRENT load — retry amplification, thundering herd, pool
        # exhaustion make the fourth concurrent incident more contagious than
        # the first. p_eff = p_edge × min(cap, 1 + β·(concurrent − 1)),
        # β operator-calibrated (judgment-logged), β=0 = the pre-E4 constant-
        # probability form, shipped as counterfactual + lever. Threshold-only
        # change: the same rng.random() draws are consumed, so β=0 runs stay
        # stream-aligned with the headline.
        n_dep_inc = sum(len(inj) for nid, inj in dep_events
                        if dep_layer and nid not in suppressed)
        concurrent = sum(counts.values()) + n_dep_inc
        # centered on EXPECTED concurrency: a typical year runs at ~1.0× (the
        # pre-E4 form); only EXCESS load amplifies. A first build centered on
        # zero was rejected — it saturated the cap in median years, a blanket
        # cascade doubling instead of a supercritical transition.
        load_mult = (min(beta_cap, 1.0 + beta * max(0.0, concurrent - exp_concurrent))
                     if beta > 0 else 1.0)
        for _gen in range(generations if cascade else 0):
            nxt = dict.fromkeys(counts, 0)
            for sp in specs:
                for _ in range(frontier[sp["id"]]):
                    for dst, prob in sp["edges"]:
                        if rng.random() < min(0.95, prob * load_mult):
                            nxt[dst] += 1
            for k in nxt:
                induced[k] += nxt[k]
            frontier = nxt
            if not any(frontier.values()):
                break
        # 3. severities for base + induced incidents; controls applied per pattern.
        #    Severity draws are independent UNLESS sev_shock_sigma > 0: then ONE
        #    common lognormal factor per trial multiplies every severity — the
        #    BLANKET "same bad day" shock the headline deliberately omits (the
        #    common-CAUSE γ term below is separate and IS in the headline). At the
        #    default 0.0 no RNG is consumed, so the headline stays byte-identical.
        shock = math.exp(rng.gauss(0.0, sev_shock_sigma)) if sev_shock_sigma > 0 else 1.0
        # E5(1) · severity co-movement under common cause (the reviewers'
        # highest-named model gap): a structural loss year raises how BAD
        # incidents are, not just how many — same customers, same positions,
        # same settlement window. γ per active loss event, capped; computed
        # from dep_events with no RNG, so counterfactual runs stay aligned.
        cc_mult = (min(1.3, 1.0 + cc_gamma * n_active_loss)
                   if cc_gamma > 0 else 1.0)
        # E1: severities for dependency-induced incidents — drawn for EVERY
        # event (stream stability), contributed only when the node is active.
        # A dep-induced incident of pattern B uses B's own severity shape ×
        # the fan-out multiplier, and takes B's control haircut — dependencies
        # change how often and how hard patterns fire, never the pattern's
        # own loss physics.
        dep_loss = dict.fromkeys(counts, 0.0)
        spec_by = {sp["id"]: sp for sp in specs}
        for node_id, inj in dep_events:
            active = dep_layer and node_id not in suppressed
            for pid, mult in inj:
                sp = spec_by.get(pid)
                if sp is None:
                    continue
                draw = math.exp(rng.gauss(sp["mu"], sp["sigma"])) * mult * shock * recursion_mult
                if active:
                    dep_loss[pid] += draw
        ti = tr = 0.0
        for sp in specs:
            loss = dep_loss[sp["id"]]
            base_part = casc_part = 0.0
            # identical draw sequence and addition order as the pre-r30 loop
            # (base then induced, accumulated into `loss` one draw at a time)
            # — the split is bookkeeping, byte-stable by construction.
            for _ in range(counts[sp["id"]]):
                d = math.exp(rng.gauss(sp["mu"], sp["sigma"])) * shock * recursion_mult * cc_mult
                loss += d
                base_part += d
            for _ in range(induced[sp["id"]]):
                d = math.exp(rng.gauss(sp["mu"], sp["sigma"])) * shock * recursion_mult * cc_mult
                loss += d
                casc_part += d
            haircut = 1.0 - sp["eff"] / 100.0
            r = loss * haircut
            ti += loss
            tr += r
            per_inh[sp["id"]].append(loss)
            per_res[sp["id"]].append(r)
            prov_base[sp["id"]] += base_part * haircut
            prov_casc[sp["id"]] += casc_part * haircut
            prov_dep[sp["id"]] += dep_loss[sp["id"]] * haircut
        inh_tot.append(ti)
        res_tot.append(tr)
    prov = {sp["id"]: {"base": prov_base[sp["id"]] / trials,
                       "cascade": prov_casc[sp["id"]] / trials,
                       "dep": prov_dep[sp["id"]] / trials} for sp in specs}
    return specs, n_edges, inh_tot, res_tot, per_inh, per_res, prov


@lru_cache(maxsize=64)
def aggregate_loss_mc(seed: int = 42, trials: int = 20000, cascade: bool = True,
                      freq_mult: float = 1.0, sev_mult: float = 1.0,
                      eff_delta: float = 0.0, cascade_mult: float = 1.0,
                      generations: int = 1, sev_shock_sigma: float = 0.0,
                      dep_layer: bool = True, dep_suppress: tuple = (),
                      dep_freq_mult: float = 1.0, dep_recursion: bool = True,
                      beta: float = 0.10, beta_cap: float = 1.5,
                      cc_gamma: float = 0.10, dep_load_delta: float = 0.05,
                      failover: bool = True) -> Dict[str, Any]:
    """Seeded Monte-Carlo aggregate annual-loss distribution — the correct portfolio roll-up.

    Base model: per pattern, Poisson(frequency P50) incidents/yr, each ~ lognormal
    (median = severity P50, 95th = severity P95); summed across all patterns per trial.
    The RESIDUAL view applies each pattern's control effectiveness
    (compensating_controls.avg_effectiveness_pct) per trial.

    v2.0c correlation term — the loss model now honors the artifact's OWN cascade graph.
    Under pure independence, "diversification" was an artifact of the assumption: the same
    projection that declares 22 cause-effect edges (cascade_to: bad deploy → SLO violation,
    policy gap → data exposure) drew every pattern independently, understating correlated
    tails. Now each BASE incident of pattern A tests every declared edge A→B once: with a
    probability keyed to the edge's declared strength (_CASCADE_STRENGTH_P — high 0.40 /
    medium 0.20 / low 0.10, operator_calibrated judgment, NOT fitted co-occurrence history),
    it induces one additional same-trial-year incident of B, drawn from B's severity
    distribution and haircut by B's controls. The default TRUNCATES at ONE generation —
    induced incidents do not themselves cascade. Be precise about what that buys:
    truncation is conservative for MODEL STABILITY (no cycle amplification on
    reciprocal edges like RP-01↔RP-02) but ANTI-conservative for RISK — it understates
    the tail. Multi-generation runs (generations=2,3) lift residual P95 by roughly
    +10% and converge; the gen-2 truncation cost ships as a sensitivity lever so it is
    visible data, not a footnote. Severity co-movement enters ONLY through the E5
    common-cause γ term (severity_comovement) — in years with no structural loss,
    severities remain independent lognormal draws; the blanket σ common shock stays
    excluded (σ=0, priced by the sev_shock lever); a production model would fit
    a full contagion/copula structure to internal loss history.
    cascade=False runs the independence counterfactual; the default result carries that
    counterfactual alongside, so the correlated-tail delta is explicit, not hidden.

    (History: this MC replaced Σ(frequency_P95 × severity_P95), which was wrong twice —
    tail×tail, then summing non-additive percentiles — and produced the non-credible
    $3.13B.) Deterministic for a fixed (seed, trials, cascade) → byte-reproducible +
    sealed (A11's intent is reproducibility; a seeded RNG satisfies it).

    Returns portfolio {inherent, residual} each {mean,p50,p95,p99}, per-pattern
    inherent/residual {p50,p95}, the single largest cited worst-anchor, and the
    correlation_model block (with independence counterfactual when cascade=True).

    Sensitivity levers (all default-neutral; used by sensitivity_analysis to answer
    "how far does the answer move if the calibration judgment is wrong"):
      freq_mult    — multiplies every pattern's Poisson mean
      sev_mult     — multiplies every pattern's severity median (lognormal shape kept)
      eff_delta    — adds percentage points to every pattern's control effectiveness
      cascade_mult — multiplies the cascade induction probabilities (capped at 0.95)
    """
    specs, n_edges, inh_raw, res_raw, per_inh, per_res, prov = _simulate(
        seed, trials, cascade, freq_mult, sev_mult, eff_delta, cascade_mult, generations, sev_shock_sigma,
        dep_layer, dep_suppress, dep_freq_mult, dep_recursion, beta, beta_cap, cc_gamma, dep_load_delta, failover)
    inh_tot = sorted(inh_raw)
    res_tot = sorted(res_raw)

    def _q(a, q):
        return a[min(len(a) - 1, int(len(a) * q))]

    def _rnd(x):
        return int(round(x / 10_000) * 10_000)

    def _dist(a):
        return {"mean": _rnd(sum(a) / len(a)), "p50": _rnd(_q(a, 0.5)),
                "p95": _rnd(_q(a, 0.95)), "p99": _rnd(_q(a, 0.99))}

    def _q_ci(a, q):
        """Order-statistic 95% CI on the q-quantile ESTIMATE — the sampling error of
        the seeded MC itself (finite trials), distinct from parameter uncertainty
        (which the sensitivity levers cover). Rank ± 1.96·sqrt(n·q·(1−q))."""
        n = len(a)
        k = int(n * q)
        half = int(1.96 * math.sqrt(n * q * (1 - q))) + 1
        return [_rnd(a[max(0, k - half)]), _rnd(a[min(n - 1, k + half)])]

    by_pattern = []
    for sp in specs:
        pi, pr = sorted(per_inh[sp["id"]]), sorted(per_res[sp["id"]])
        by_pattern.append({
            "pattern_id": sp["id"],
            "inherent": {"p50": _rnd(_q(pi, 0.5)), "p95": _rnd(_q(pi, 0.95)),
                         "worst_anchor": sp["anchor"], "worst_anchor_basis": sp["anchor_basis"]},
            "controls_avg_eff_pct": round(sp["eff"], 1),
            "residual": {"p50": _rnd(_q(pr, 0.5)), "p95": _rnd(_q(pr, 0.95))},
            "attribution": (lambda pv: {
                "base_mean_usd": _rnd(pv["base"]),
                "cascade_mean_usd": _rnd(pv["cascade"]),
                "dep_mean_usd": _rnd(pv["dep"]),
                "induced_share_pct": round((pv["cascade"] + pv["dep"])
                    / (pv["base"] + pv["cascade"] + pv["dep"]) * 100, 1)
                    if (pv["base"] + pv["cascade"] + pv["dep"]) > 0 else 0.0,
                "note": ("Mean annual RESIDUAL dollars split by provenance — own base "
                         "draws vs cascade-induced vs dependency-injected. A high induced "
                         "share means the treatment lives UPSTREAM (harden what feeds this "
                         "pattern), not in this pattern's own controls."),
            })(prov[sp["id"]]),
        })
    top = max(specs, key=lambda sp: sp["anchor"])
    result = {
        "portfolio": {"inherent": _dist(inh_tot), "residual": _dist(res_tot)},
        "sampling_error": {
            "residual_p95_ci95": _q_ci(res_tot, 0.95),
            "residual_p99_ci95": _q_ci(res_tot, 0.99),
            "note": (
                "Order-statistic 95% CI on the quantile ESTIMATES — the seeded MC's own "
                "sampling error at {n:,} trials. Distinct from parameter uncertainty, "
                "which the sensitivity levers cover.".format(n=trials)
            ),
        },
        "by_pattern": by_pattern,
        "worst_anchor": top["anchor"],
        "worst_anchor_pattern": top["id"],
        "worst_anchor_basis": top["anchor_basis"],
        "avg_eff_pct": round(sum(sp["eff"] for sp in specs) / len(specs), 1),
        "seed": seed, "trials": trials,
        # r29/r30 — the recalibration provenance as DATA, so the why-moved story
        # is leaf-backed (C27.4) not author knowledge. Prior values are sealed
        # HISTORY (fixed constants, same discipline as verify_bundle B6.2).
        "recalibration": {
            "prior_seal": "E5 · sealed 2026-07-21",
            "prior_residual_p95": 312200000,
            "prior_residual_p99": 549400000,
            "prior_inherent_p95": 815400000,
            "moved_by": ("r29 re-anchor: every severity median re-cited to reference data "
                         "(IBM CODB 2024 · Uptime Institute 2023 · ITIC 2024), σ tightened "
                         "to ~1.18 (Basel/ORX severity practice), Σλ trimmed to 6.9/yr, "
                         "dependency stacking capped (fan-out ≤2.0×, 1 induced incident), "
                         "cc double-count on dep-injected draws removed"),
            "band_gate": ("C33 holds the aggregate permanently: P50 0.4–1.5% and P95 2–5% "
                          "of meta.archetype_revenue_usd; P99 below the worst public "
                          "comparable. Recalibrations move within the band or fail the build."),
        },
    }
    if dep_layer and not dep_suppress:
        # E1: the layer-off counterfactual — the pre-E1 model form (patterns +
        # cascade only, no common-cause events), same seed/trials, RNG-aligned
        # (dependency draws still consumed, contributions zeroed). The delta is
        # what the shared-dependency layer ADDS to the tail — visible data.
        dep_off = aggregate_loss_mc(seed, trials, cascade, freq_mult, sev_mult, eff_delta,
                                    cascade_mult, generations, sev_shock_sigma, False, (), dep_freq_mult, dep_recursion,
                                    beta, beta_cap, cc_gamma, dep_load_delta, failover)
        result["dependency_model"] = {
            "type": "common_cause_dependency_layer",
            "nodes": len(_DEPS.get("nodes") or []),
            "provenance": "operator_calibrated",
            "note": (
                "E1 — shared-dependency common-cause events. Per trial, each catalogued "
                "dependency (cloud region, customer identity plane, API registry, K8s "
                "control plane/etcd, workforce IdP, primary datastore, payments processor, "
                "security-agent vendor) draws Poisson degraded/loss events; a fired node "
                "injects incidents across its declared pattern fan-out with severity "
                "multipliers — several patterns, same trial-year. This is the axis "
                "pattern-to-pattern cascade edges cannot express: one structural event "
                "UNDER many risks. Frequencies and fan-outs are operator judgment anchored "
                "to named public incidents (see dependency catalog) — a synthetic "
                "demonstrator has no dependency-failure history to fit. Induced incidents "
                "do not themselves cascade (same one-generation conservatism as the "
                "contagion model, disclosed)."
            ),
            "load_dependence": {
                "delta": dep_load_delta, "cap": 1.25,
                "off_lever": "dep_load_off",
                "note": ("E5(2) — dependency LOSS frequency is load-dependent: "
                         "λ_eff = λ × min(cap, 1 + δ·max(0, base incidents − E[base])). "
                         "The identity plane / etcd is likelier to fail exactly when load "
                         "is already elevated (dep_load_dependence judgment-log entry; "
                         "gated only-lower, C32.1)."),
            },
            "failover_escalation": {
                "escalation_mult": 1.5,
                "nodes": {nd["id"]: nd.get("failover_failure_prob")
                          for nd in (_DEPS.get("nodes") or [])
                          if nd.get("failover_failure_prob")},
                "off_lever": "failover_off",
                "note": ("E5(3) — region-bounded nodes carry failover_failure_prob (with a "
                         "named basis in the catalog): the failover ITSELF fails (GitHub "
                         "2018 split-brain class) and the event escalates ×1.5 "
                         "(failover_escalation judgment-log entry; gated only-lower, C32.1)."),
            },
            "layer_off_counterfactual": {
                "residual_p50": dep_off["portfolio"]["residual"]["p50"],
                "residual_p95": dep_off["portfolio"]["residual"]["p95"],
                "residual_p99": dep_off["portfolio"]["residual"]["p99"],
                "inherent_p95": dep_off["portfolio"]["inherent"]["p95"],
                "note": ("Same seed/trials with every dependency contribution zeroed — the "
                         "pre-E1 model form. The delta vs the headline is what shared-"
                         "dependency concentration adds to the tail."),
            },
        }
    if cc_gamma > 0 and not dep_suppress:
        cc0 = aggregate_loss_mc(seed, trials, cascade, freq_mult, sev_mult, eff_delta, cascade_mult,
                                generations, sev_shock_sigma, dep_layer, dep_suppress, dep_freq_mult,
                                dep_recursion, beta, beta_cap, 0.0, dep_load_delta, failover)
        result["severity_comovement"] = {
            "gamma": cc_gamma, "cap": 1.3,
            "provenance": "operator_calibrated",
            "applies_to": ("base + cascade-induced severity draws in trial-years with an "
                           "active structural LOSS event; dependency-INJECTED draws are "
                           "excluded — they already carry the fan-out severity multiplier "
                           "(dep_attribution: multiplying twice double-counts)"),
            "off_lever": "cc_sev_off",
            "note": ("E5(1) — a structural loss year raises how BAD incidents are, not just "
                     "how many: same customers, same positions, same settlement window. "
                     "sev_mult_eff = min(cap, 1 + γ·active_loss_events). γ is operator "
                     "judgment (cc_severity_comovement judgment-log entry), bounded by the "
                     "off-lever and gated only-lower (C32.1)."),
            "gamma0_counterfactual": {
                "residual_p95": cc0["portfolio"]["residual"]["p95"],
                "residual_p99": cc0["portfolio"]["residual"]["p99"],
                "note": "γ=0 — severity co-movement removed, same seed/trials, stream-aligned.",
            },
        }
    if cascade and beta > 0 and not dep_suppress:
        b0 = aggregate_loss_mc(seed, trials, cascade, freq_mult, sev_mult, eff_delta, cascade_mult,
                               generations, sev_shock_sigma, dep_layer, dep_suppress, dep_freq_mult,
                               dep_recursion, 0.0, beta_cap, cc_gamma, dep_load_delta, failover)
        result["load_dependent_induction"] = {
            "beta": beta, "cap": beta_cap,
            "provenance": "operator_calibrated",
            "note": ("E4 — the induction probability is LOAD-DEPENDENT: p_eff = p_edge × "
                     "min(cap, 1 + β·max(0, concurrent − EXPECTED concurrent)). A typical year runs "
                     "at ~1.0× (the pre-E4 form); only excess load amplifies. Retry amplification, thundering "
                     "herd and pool exhaustion make contagion rise with concurrent stress — the "
                     "subcritical-to-supercritical transition a constant-probability model cannot "
                     "express. β is operator judgment (see the dynamic_cascade judgment-log entry), "
                     "bounded both ways by the beta_zero / beta_up levers."),
            "beta0_counterfactual": {
                "residual_p95": b0["portfolio"]["residual"]["p95"],
                "residual_p99": b0["portfolio"]["residual"]["p99"],
                "note": "β=0 — the pre-E4 constant-probability branching form, same seed/trials, stream-aligned.",
            },
        }
    if cascade:
        # Report the independence counterfactual alongside, so the correlated-tail
        # delta the cascade graph implies is explicit — not an assumption either way.
        base = aggregate_loss_mc(seed, trials, False, freq_mult, sev_mult, eff_delta, cascade_mult,
                                 generations, sev_shock_sigma, dep_layer, dep_suppress, dep_freq_mult, dep_recursion,
                                 beta, beta_cap, cc_gamma, dep_load_delta, failover)
        result["correlation_model"] = {
            "type": "cascade_propagation",
            "edges_used": n_edges,
            "strength_to_probability": dict(_CASCADE_STRENGTH_P),
            "generations": generations,
            "provenance": "operator_calibrated",
            "note": (
                "The loss engine honors the same cascade_to edges the cascade graph renders: "
                "each incident in the frontier tests its declared downstream edges once, "
                "inducing same-trial-year incidents with strength-keyed probability "
                "(high 0.40 / medium 0.20 / low 0.10 — operator judgment, not fitted "
                "co-occurrence history; a synthetic demonstrator has none). TWO DISCLOSED "
                f"LIMITATIONS: (1) propagation truncates at {generations} generation(s) — "
                "stable (no cycle amplification on reciprocal edges) but risk-UNDERSTATING: "
                "multi-generation runs lift residual P95 ~+10% and converge — see the "
                "'Cascade generations 2' sensitivity lever, which makes the truncation cost "
                "visible data. (2) severity co-movement is modeled ONLY through the "
                "common-cause term (see severity_comovement: γ per active structural-loss "
                "event, capped) and the sev_shock lever — in years with NO structural "
                "event, severities remain independent lognormal draws; a production model "
                "would fit a full contagion/copula structure to internal loss history."
            ),
            "independence_counterfactual": {
                "residual_p50": base["portfolio"]["residual"]["p50"],
                "residual_p95": base["portfolio"]["residual"]["p95"],
                "residual_p99": base["portfolio"]["residual"]["p99"],
                "inherent_p95": base["portfolio"]["inherent"]["p95"],
                "note": (
                    "Same seed/trials with cascade edges disabled — the pre-v2.0c "
                    "independence assumption. The delta vs the headline is the "
                    "correlated-tail effect implied by the artifact's own cascade graph."
                ),
            },
        }
    else:
        result["correlation_model"] = {
            "type": "independent",
            "note": "cascade propagation disabled — independence counterfactual / sensitivity run",
        }
    return result


# ── regulatory residual view — residual $ under each triggered obligation ────────

def regulation_residual_view(reg_map: tuple, seed: int = 42, trials: int = 20000) -> Dict[str, Any]:
    """Residual annual-loss distribution PER TRIGGERED REGULATION, from the SAME
    trial matrix as the headline (via _simulate — cannot drift). For each regulation,
    the trial series is the WITHIN-TRIAL SUM of its mapped patterns' residuals —
    quantiles of that series. NEVER the sum of per-pattern percentiles (percentiles
    do not add — the exact failure the portfolio roll-up was rebuilt to kill; the
    naive sum is reported alongside as the anti-example, and audit C21 gates on the
    subset quantile staying below it).

    reg_map: tuple of (reg_id, citation, (pattern_id, ...)) — hashable for callers
    that want to cache around this. Regulations OVERLAP (one pattern can trigger
    several), so the rows do not sum to the portfolio — disclosed in the note.
    """
    _, _, _, res_raw, _, per_res, _ = _simulate(seed, trials, True, 1.0, 1.0, 0.0, 1.0, 1)
    portfolio_p95 = sorted(res_raw)[min(trials - 1, int(trials * 0.95))]

    def _rnd(x):
        return int(round(x / 10_000) * 10_000)

    def _q(a, q):
        return a[min(len(a) - 1, int(len(a) * q))]

    rows = []
    for reg_id, citation, pids, *rest in reg_map:
        applicability = rest[0] if rest else ""
        pids = [p for p in pids if p in per_res]
        if not pids:
            continue
        series = sorted(sum(per_res[p][t] for p in pids) for t in range(trials))
        p95 = _q(series, 0.95)
        # the anti-example: what the naive percentile-sum would have claimed
        naive = sum(_q(sorted(per_res[p]), 0.95) for p in pids)
        rows.append({
            "reg_id": reg_id,
            "citation": citation,
            "applicability": applicability,
            "patterns": list(pids),
            "residual_p50": _rnd(_q(series, 0.5)),
            "residual_p95": _rnd(p95),
            "share_of_portfolio_p95_pct": round(p95 / portfolio_p95 * 100, 1) if portfolio_p95 else 0.0,
            "naive_percentile_sum_p95": _rnd(naive),
        })
    rows.sort(key=lambda r: -r["residual_p95"])
    return {
        "by_regulation": rows,
        "portfolio_residual_p95": _rnd(portfolio_p95),
        "method_note": (
            "Within-trial subset sums over the SAME seeded trial matrix as the "
            "headline — each regulation's quantiles come from its patterns' losses "
            "co-occurring (or not) trial by trial. Regulations OVERLAP (a pattern can "
            "trigger several), so rows do not sum to the portfolio, and shares can "
            "total >100%. The naive Σ-of-per-pattern-P95s is shown only as the "
            "anti-example the roll-up was rebuilt to kill."
        ),
    }


def perimeter_profiles_view(reg_map: tuple, profiles: tuple,
                            seed: int = 42, trials: int = 20000) -> Dict[str, Any]:
    """Round-17 external ask (examiner persona: 'a toggle is not proof of
    re-mapping logic'): the in-perimeter residual PER DECLARED CHARTER, from the
    SAME trial matrix as the headline. For each profile, the trial series is the
    within-trial sum over the UNION of patterns mapped by its in-perimeter
    regulations — quantiles of that series, never summed percentiles.

    profiles: tuple of (profile_id, label, note, ((reg_id, status), ...)) where
    status ∈ {binding-assumed, style-mapping, contractual, out-of-perimeter}.
    Statuses RE-LABEL the existing applicability facts per charter — they mint
    no numbers; the dollars are subset sums. The perimeter DETERMINATION stays
    reserved to Legal/Compliance (same reservation as materiality)."""
    _, _, _, res_raw, _, per_res, _ = _simulate(seed, trials, True, 1.0, 1.0, 0.0, 1.0, 1)
    portfolio_p95 = sorted(res_raw)[min(trials - 1, int(trials * 0.95))]
    reg_pids = {rid: [p for p in pids if p in per_res] for rid, _, pids, *_ in reg_map}

    def _rnd(x):
        return int(round(x / 10_000) * 10_000)

    def _q(a, q):
        return a[min(len(a) - 1, int(len(a) * q))]

    out = []
    for pid_, label, note, statuses in profiles:
        in_regs = [rid for rid, st in statuses if st in ("binding-assumed", "contractual")]
        union: list = sorted({p for rid in in_regs for p in reg_pids.get(rid, [])})
        if union:
            series = sorted(sum(per_res[p][t] for p in union) for t in range(trials))
            p95 = _q(series, 0.95)
        else:
            p95 = 0
        out.append({
            "profile_id": pid_,
            "label": label,
            "note": note,
            "statuses": {rid: st for rid, st in statuses},
            "in_perimeter_regs": in_regs,
            "in_perimeter_patterns": union,
            "in_perimeter_residual_p95": _rnd(p95),
            "share_of_portfolio_p95_pct": round(p95 / portfolio_p95 * 100, 1) if portfolio_p95 else 0.0,
        })
    return {
        "default": profiles[0][0] if profiles else None,
        "profiles": out,
        "method_note": (
            "Same trial matrix as the headline; each profile's dollars are the "
            "within-trial sum over the UNION of its in-perimeter regulations' "
            "patterns. Charter statuses are INDICATIVE re-labels of the disclosed "
            "applicability facts — the perimeter determination is reserved to "
            "Legal/Compliance, exactly like materiality."
        ),
    }


# ── control test-evidence schema — the structure behind the effectiveness % ─────
# Round-7 external finding: "the model's most influential input is its least-
# evidenced one" — control effectiveness is the biggest tornado lever (+52.7% at
# −20pts) yet had no evidence STRUCTURE behind it. A synthetic demonstrator cannot
# cite real control tests, but it can carry the schema a real 2LoD credits against
# — control → method → last_tested → tested_by → result → credited-vs-self-assessed
# — illustratively populated (deterministic, no wall clock) and RECONCILED by
# construction: per pattern, mean(credited) == the avg_effectiveness_pct the MC
# actually uses, so the schema and the model cannot tell two stories.

import hashlib as _hashlib

_TEST_METHODS = ("control replay (synthetic incident)", "tabletop exercise",
                 "sample-based audit", "chaos drill", "pipeline conformance check")
_TEST_ANCHOR = "2026-07-01"  # fixed reference date — reproducible, disclosed illustrative
# method → (reperformance class, hard_to_reperform, basis) — the lifecycle
# classification DERIVES from how the control is tested; nothing invented.
_REPERF = {
    "control replay (synthetic incident)": ("automated", False,
        "re-runnable from the seeded incident pack — the attestation log re-performs it on demand"),
    "pipeline conformance check": ("automated", False,
        "a query against pipeline state — re-performed on every audit pull"),
    "chaos drill": ("automated", True,
        "re-performable but OPERATED — needs a scheduled window and humans on call; the automation claim stops at orchestration"),
    "tabletop exercise": ("bespoke", True,
        "a human exercise — no export re-performs it; evidence is the minutes, and chasing them is the old operating model"),
    "sample-based audit": ("bespoke", True,
        "manual sampling — re-performance means re-sampling; resistant to automation by construction"),
}


def _ct_hash(*parts: str) -> int:
    return int.from_bytes(_hashlib.sha256("|".join(parts).encode()).digest()[:4], "big")


def control_test_evidence(pattern_id: str) -> Dict[str, Any]:
    """Illustrative per-control test-evidence schema for one pattern. The
    credited percentages are scaled so their mean equals the pattern's
    avg_effectiveness_pct — the exact number the MC consumes (audit C22 gates
    the reconciliation). Dates/methods/refs are deterministic illustrative
    anchors (hash-derived from a fixed reference date, never wall clock)."""
    from datetime import date, timedelta
    cc = (_PATTERNS.get(pattern_id) or {}).get("compensating_controls") or {}
    in_place = cc.get("in_place") or []
    avg_eff = float(cc.get("avg_effectiveness_pct") or 0)
    selfs = [float(c.get("effectiveness_pct") or 0) for c in in_place]
    self_mean = sum(selfs) / len(selfs) if selfs else 0.0
    scale = (avg_eff / self_mean) if self_mean > 0 else 0.0
    anchor = date.fromisoformat(_TEST_ANCHOR)
    controls = []
    for c in in_place:
        h = _ct_hash(pattern_id, c.get("name", ""), "control_test")
        self_pct = float(c.get("effectiveness_pct") or 0)
        controls.append({
            "name": c.get("name", ""),
            "self_assessed_pct": self_pct,
            "credited_pct": round(self_pct * scale, 1),
            "method": _TEST_METHODS[h % len(_TEST_METHODS)],
            "last_tested": (anchor - timedelta(days=14 + (h % 150))).isoformat(),
            "tested_by": "2LoD control testing · illustrative",
            "evidence_ref": f"CT-2026-{(h % 9000) + 1000}",
            "result": "pass — credited below self-assessed (independent-validation haircut)",
            # Stage 3 (journey spine port): the evidence LIFECYCLE class, derived
            # from the test method — the v106 question made data: "if we
            # re-perform this assessment, what evidence is available in the
            # current export?" hard_to_reperform=True is the honesty flag that
            # keeps the automation story credible instead of total.
            "reperformance": _REPERF[_TEST_METHODS[h % len(_TEST_METHODS)]][0],
            "hard_to_reperform": _REPERF[_TEST_METHODS[h % len(_TEST_METHODS)]][1],
            "reperformance_basis": _REPERF[_TEST_METHODS[h % len(_TEST_METHODS)]][2],
            # Round-12: the coverage→effectiveness split (C24) must be visible
            # where the credit is displayed, not only in the audit script.
            "basis": c.get("evidence_basis", ""),
        })
    for g in cc.get("gaps") or []:
        controls.append({
            "name": g.get("name", ""),
            "self_assessed_pct": 0.0,
            "credited_pct": 0.0,
            "method": "—",
            "last_tested": None,
            "tested_by": None,
            "evidence_ref": None,
            "result": f"not tested — control gap, planned {g.get('planned', '?')}",
        })
    return {
        "controls": controls,
        "credited_mean_pct": round(sum(c["credited_pct"] for c in controls if c["last_tested"]) / max(1, len([c for c in controls if c["last_tested"]])), 1),
        "mc_uses_pct": avg_eff,
        "haircut_pct": round((1 - scale) * 100, 1) if scale else 0.0,
        "source_status": "illustrative",
        "note": (
            "ILLUSTRATIVE evidence schema — the structure a real 2LoD credits "
            "effectiveness against (method · date · result · credited-vs-self-assessed), "
            "populated deterministically, not from real control tests. Credited "
            "percentages reconcile by construction to the avg_effectiveness_pct the MC "
            "consumes; the gap between self-assessed and credited IS the "
            "independent-validation haircut, shown per control."
        ),
    }


# ── sensitivity analysis — "how far does the answer move if the judgment is wrong" ──

_SENSITIVITY_LEVERS = [
    # (id, label, kwargs) — each is ONE calibration judgment shocked, everything else held
    ("freq_up",     "Incident frequency ×1.5",        {"freq_mult": 1.5}),
    ("freq_down",   "Incident frequency ×0.67",       {"freq_mult": 0.67}),
    ("eff_down",    "Control effectiveness −20 pts",  {"eff_delta": -20.0}),
    ("eff_up",      "Control effectiveness +10 pts",  {"eff_delta": 10.0}),
    ("sev_up",      "Severity medians ×1.5",          {"sev_mult": 1.5}),
    ("sev_down",    "Severity medians ×0.67",         {"sev_mult": 0.67}),
    ("cascade_off", "Cascade off (independence)",     {"cascade": False}),
    ("cascade_up",  "Cascade induction ×1.5",         {"cascade_mult": 1.5}),
    # the truncation cost, visible as data: the headline truncates propagation at one
    # generation (stable but risk-understating); this lever shows gen-2
    ("cascade_gen2", "Cascade generations 2",         {"generations": 2}),
    # JOINT shocks — OAT understates interactions; these two show the compounding a
    # 2LoD actually stresses: the bad year (more incidents AND controls degrade) and
    # the fat-tail year (worse severities AND stronger contagion)
    # the co-movement the headline omits, quantified: one lognormal factor per
    # trial multiplies EVERY severity (σ=0.3 → typical trial ±35%) — the same-bad-day
    # shock (region outage, CrowdStrike-class) the model_form judgment discloses
    ("sev_shock", "Severity common shock (σ=0.3 per trial)", {"sev_shock_sigma": 0.3}),
    # E1 — the shared-dependency layer's own judgments, priced like every other:
    # how far the answer moves if the dependency-event frequencies are wrong,
    # and what the whole layer contributes (the pre-E1 model form).
    ("dep_freq_up",   "Dependency-event frequency ×2",       {"dep_freq_mult": 2.0}),
    ("dep_layer_off", "Dependency layer off (pre-E1 form)",  {"dep_layer": False}),
    ("recursion_off", "Response recursion off (E2 mechanism)", {"dep_recursion": False}),
    ("beta_zero", "Load-dependence off (β=0, constant-probability form)", {"beta": 0.0}),
    ("beta_up",   "Load-dependence β ×2",                    {"beta": 0.20}),
    ("cc_sev_off",   "Common-cause severity co-movement off (γ=0)",  {"cc_gamma": 0.0}),
    ("dep_load_off", "Dependency load-dependence off (δ=0)",         {"dep_load_delta": 0.0}),
    ("failover_off", "Failover-failure escalation off",              {"failover": False}),
    ("joint_bad_year", "Joint: freq ×1.5 + control eff −20 pts", {"freq_mult": 1.5, "eff_delta": -20.0}),
    ("joint_fat_tail", "Joint: severity ×1.5 + cascade ×1.5",    {"sev_mult": 1.5, "cascade_mult": 1.5}),
]


# ── challenged-judgment log — every operator judgment, on the record ────────────
# Round-6 external P0: "a 'challenged judgment' log (who set the 0.40/0.20/0.10
# cascade probabilities, when, and against what)." Dates are the real git-history
# dates of the commits that set each judgment. `challenge` is the question a 2LoD
# would ask — each entry names the lever (or the disclosed gap) that answers it.
_JUDGMENT_LOG = [
    {
        "id": "dep_attribution",
        "judgment": ("E1 dependency layer: only structural LOSS events inject incidents "
                     "(0.04-0.15/yr per node); DEGRADED-mode events do not"),
        "set_by": "author (operator), E1 dependency layer",
        "set_at": "2026-07-20",
        "basis": (
            "Base per-pattern frequencies are all-cause calibrated — routine dependency "
            "degradation is already embedded in them; injecting it again would double-count "
            "the expected year (a build of exactly that form moved P50 from ~$38M to ~$83M "
            "and was rejected). Structural loss events are the rare common-cause tail the "
            "per-pattern rates cannot carry, because one event fires SEVERAL patterns in "
            "the same trial-year. Loss frequencies are judgment anchored to named public "
            "incidents (us-east-1 2021/2017, Auth0 2021, Fastly 2021, Reddit Pi-Day 2023, "
            "CrowdStrike 2024 — see the dependency catalog)."
        ),
        "challenge": ("Prove the base rates exclude structural-loss causes — or show the "
                      "attribution split from incident lineage."),
        "answers_with": ("The honest answer: a synthetic demonstrator cannot show attribution; "
                         "production fits it from incident lineage (which incidents trace to "
                         "which dependency). Bounded both ways as data: the dep_layer_off lever "
                         "is the pre-E1 form; dep_freq_up ×2 doubles every loss rate."),
    },
    {
        "id": "response_recursion",
        "judgment": ("E2: a trial-year with an ACTIVE workforce-IdP loss multiplies every severity that year "
                     "×1.25 (the response recursion)"),
        "set_by": "author (operator), E2 identity mechanics",
        "set_at": "2026-07-21",
        "basis": (
            "Responders authenticate through the same plane they must fix — when it fails, every OTHER incident "
            "that year runs longer because the response function itself is degraded (Meta 2021-10-04: engineers "
            "locked out of the tools and buildings needed for the fix). ×1.25 is operator judgment for a platform "
            "with partial out-of-band paths; a firm with none would be worse."
        ),
        "challenge": "Show me the MTTR inflation from an identity-plane event in the incident history.",
        "answers_with": ("None exists in a synthetic demonstrator — production fits it from incidents that overlapped "
                         "identity outages. Bounded as data: the recursion_off lever removes the mechanism entirely."),
    },
    {
        "id": "aggregate_recalibration_r29",
        "judgment": ("r29: severity medians re-anchored to reference data and every multiplicative mechanism cooled "
                     "— the aggregate must be defensible as a fraction of the archetype's revenue"),
        "set_by": "author (operator), after the operator's own challenge: 'these sound extremely high and fictitious'",
        "set_at": "2026-07-21",
        "basis": (
            "The pre-r29 build implied ~$91M/yr inherent EXPECTED loss (Σ freq × E[sev]) and a $79M MEDIAN residual "
            "year — 2-4% of revenue lost to technology risk in a TYPICAL year at a $2-4B archetype, which no "
            "reference supports (ORX-class op-risk benchmarks put ALL-cause op losses near 1-2% of gross income in "
            "typical years, with technology a fraction). Two compounding causes: (1) severity medians above the "
            "reference data (a $20M MEDIAN vuln event vs IBM CODB 2024 US average $9.36M; re-anchored per pattern "
            "with named refs — IBM CODB 2024, Uptime Institute 2023, ITIC 2024, with Knight/Capital One/TSB/Equifax "
            "held as TAIL anchors, not medians); (2) multiplicative stacking — fan-out ×3.0 · co-movement ×1.5 · "
            "recursion ×1.25 · failover ×1.5 could compound ~8× on one draw, and co-movement double-counted "
            "dependency-injected draws that already carry fan-out multipliers. Post-r29 the sanity frame is "
            "machine-gated (C33): median year ~0.5-1.2% of revenue, stress year (P95) ~2-5%, P99 bounded by the "
            "Knight-class worst anchor's neighborhood."
        ),
        "challenge": "Fit the aggregate to the firm's own loss history and the ORX peer distribution.",
        "answers_with": ("Exactly — that IS the productionization contract's step 1. Synthetically, the defense is "
                         "the reference frame: every median now cites its source, every mechanism its lever, and "
                         "C33 hard-bounds the aggregate against the revenue archetype."),
    },
    {
        "id": "cc_severity_comovement",
        "judgment": "E5/r29: each ACTIVE dependency-loss event multiplies every BASE+cascade severity that trial-year ×1.10 (cap 1.3) — dependency-injected draws are EXCLUDED (they already carry fan-out multipliers; including them double-counted)",
        "set_by": "author (operator), E5 model terms",
        "set_at": "2026-07-21",
        "basis": ("A structural outage raises how BAD incidents are, not just how many — the same customers are "
                  "locked out during the same settlement window the other incidents hit. Both external reviewers "
                  "named independent-severities-under-common-cause the highest remaining model gap."),
        "challenge": "Show severity inflation conditional on dependency events in the loss history.",
        "answers_with": "None exists synthetically; production fits from incidents overlapping dependency outages. Bounded: cc_sev_off lever.",
    },
    {
        "id": "dep_load_dependence",
        "judgment": "E5/r29: dependency LOSS frequency scales ×min(1.25, 1 + 0.05·base-incident excess) — shared planes fail when load is already elevated",
        "set_by": "author (operator), E5 model terms",
        "set_at": "2026-07-21",
        "basis": ("The identity plane and control plane degrade under exactly the volatility that fills the rest of "
                  "the incident queue (the 2021-01 brokerage login failures WERE a load event). Constant Poisson "
                  "rates on the dependency nodes contradicted the load-dependence already priced on the edges."),
        "challenge": "Show dependency-failure clustering against load percentiles.",
        "answers_with": "Production fits it; bounded by the dep_load_off lever.",
    },
    {
        "id": "failover_escalation",
        "judgment": "E5: region-bounded nodes carry failover_failure_prob (cloud_region 0.25, primary_datastore 0.30) — a failed failover escalates the event ×1.5",
        "set_by": "author (operator), E5 model terms",
        "set_at": "2026-07-21",
        "basis": ("Multi-region HA is priced as a discount on loss frequency; E5 prices the case where the DISCOUNT "
                  "ITSELF fails — GitHub 2018-10-21 (43s partition → ~24h impact via failover misbehavior), TSB "
                  "2018 cutover class. The probabilities echo the recover-function's own sub-100% exercise credits."),
        "challenge": "Show live failover exercise pass rates.",
        "answers_with": "The declared DR-exercise gap rows are the honest answer; bounded by the failover_off lever.",
    },
    {
        "id": "dynamic_cascade",
        "judgment": "E4/r29: cascade induction is load-dependent — p_eff = p_edge × min(1.5, 1 + 0.10·max(0, concurrent − E[concurrent])) — cap cooled from 2.0 in the r29 recalibration (retry budgets and breakers are partially deployed, per RP-14's own control rows)",
        "set_by": "author (operator), E4 cascade dynamics",
        "set_at": "2026-07-21",
        "basis": (
            "Constant-probability branching cannot produce supercritical years: nothing made the fourth "
            "concurrent incident more contagious than the first, yet retry amplification (offered load × "
            "1/(1−r) under sustained retries — Google SRE), thundering herd on recovery, and connection-pool "
            "exhaustion are exactly that mechanism. β=0.15 with cap 2.0 is operator judgment for a platform "
            "with retry budgets and circuit breakers partially deployed."
        ),
        "challenge": "Show me the co-occurrence curvature — do incident pairs really cluster superlinearly in your history?",
        "answers_with": ("A synthetic demonstrator cannot; production fits β from incident co-occurrence lineage. "
                         "Bounded as data: beta_zero is the pre-E4 form (the β=0 counterfactual ships inside "
                         "correlation-adjacent output by construction); beta_up doubles it."),
    },
    {
        "id": "freq_reanchor",
        "judgment": "Material-incident frequencies (per-pattern Poisson means, e.g. RP-01 0.8/yr)",
        "set_by": "author (operator), v2.0b recalibration",
        "set_at": "2026-07-09",
        "basis": (
            "Rarity of MATERIAL incidents (<1-2/yr for most patterns) vs the ~$100M/yr "
            "expected loss the illustrative base-rate starting point implied. No public "
            "source publishes a firm's incident-frequency appetite — this is judgment "
            "and says so; the superseded base-rate formulas are kept on RP-01/RP-09 "
            "for the trail."
        ),
        "challenge": "Show me the loss history or incident:deploy ratio behind 0.8/yr.",
        "answers_with": "freq ×1.5 / ×0.67 levers (+35% / −25% at P95) — and the honest answer: none exists; production fits from internal history.",
    },
    {
        "id": "control_eff",
        "judgment": "Control effectiveness percentages (41–73%, avg ~65%) + independent-validation haircut",
        "set_by": "author (operator), v2.0b",
        "set_at": "2026-07-09",
        "basis": (
            "Self-assessed effectiveness overstates realized reduction — a haircut is "
            "applied. The per-control TEST-EVIDENCE SCHEMA (method · date · result · "
            "credited-vs-self-assessed) ships illustratively in the calibration table, "
            "reconciled by construction to the percentage the MC consumes — the "
            "structure a real 2LoD credits against, populated synthetically because "
            "no real control tests exist to cite."
        ),
        "challenge": "Your 65% average effectiveness — where is the control-test evidence?",
        "answers_with": "eff −20 pts lever: the single biggest bar (+52.7% at P95) — plus the per-control evidence schema in the calibration table (illustrative; production replaces with real CCT results).",
    },
    {
        "id": "cascade_probs",
        "judgment": "Cascade induction probabilities — strength high 0.40 / medium 0.20 / low 0.10",
        "set_by": "author (operator), v2.0c correlated MC",
        "set_at": "2026-07-10",
        "basis": (
            "Conditional judgment per declared edge strength; a synthetic demonstrator "
            "has NO co-occurrence history to fit. Production fits these from incident "
            "lineage (which incidents actually co-fired)."
        ),
        "challenge": "Why 0.40 and not 0.25 or 0.60 for a 'high' edge?",
        "answers_with": "cascade ×1.5 lever (+16.7%) and cascade-off counterfactual (−38.9%) bracket the choice; gen-2 lever shows the truncation cost (+9.7%).",
    },
    {
        "id": "severity_medians",
        "judgment": "Severity medians / P95s per pattern (lognormal shape)",
        "set_by": "author (operator), v2.0a→b",
        "set_at": "2026-07-09",
        "basis": (
            "Worst anchors are CITED public events (Knight Capital $440M, Equifax "
            "$700M FTC, …); the medians and P95s are typical-cost judgment scaled "
            "under those anchors, not fitted losses."
        ),
        "challenge": "The anchors are real; why should I believe the medians?",
        "answers_with": "severity ×1.5 / ×0.67 levers (+50% / −33% at P95) — second-biggest bars in the tornado.",
    },
    {
        "id": "model_form",
        "judgment": "Model form — Poisson frequency × lognormal severity, one-generation cascade, independent severities",
        "set_by": "author (operator), v2.0c",
        "set_at": "2026-07-10",
        "basis": (
            "Standard operational-risk decomposition; cascade honors the declared "
            "dependency graph. Two disclosed limitations: generation truncation "
            "understates the tail (~+10%, see gen-2 lever) and severities do not "
            "co-move only through the common-cause γ term (severity_comovement) — "
            "the blanket common shock stays excluded (σ=0), priced by the lever."
        ),
        "challenge": "What if severities co-move on the same bad day? And why σ=0.3 — have you priced fatter shocks?",
        "answers_with": "The 'Severity common shock' lever quantifies the remaining omission, and the σ choice is swept, not asserted: σ=0.3 → +9.1%, σ=0.5 → +26.6%, σ=0.6 → +40.1% at P95 (same seed/trials). σ=0.3 is the operator's moderate-co-movement read; a CrowdStrike-class common shock sits nearer the σ=0.6 figure. The headline excludes the blanket σ shock — the common-CAUSE co-movement term (γ, severity_comovement) has been IN the headline since E5. A production model fits a copula to internal history instead of choosing σ.",
    },
]


def sensitivity_analysis(seed: int = 42, trials: int = 20000) -> Dict[str, Any]:
    """Seeded one-at-a-time sensitivity of the portfolio residual to each calibration
    judgment — the tornado behind the dollars. Every lever re-runs the SAME correlated
    MC with exactly one judgment shocked (frequency re-anchor, control-effectiveness
    self-assessment, severity medians, cascade induction), so the reader sees the range
    the answer occupies if the operator judgment is wrong — instead of a point estimate
    presented as more certain than it is. Deterministic per (seed, trials); the
    cascade_off lever equals correlation_model.independence_counterfactual by
    construction (audit-checked cross-surface).
    """
    baseline = aggregate_loss_mc(seed, trials)
    base_res = baseline["portfolio"]["residual"]

    levers = []
    for lid, label, kw in _SENSITIVITY_LEVERS:
        run = aggregate_loss_mc(seed, trials, **{
            "cascade": kw.get("cascade", True),
            "freq_mult": kw.get("freq_mult", 1.0),
            "sev_mult": kw.get("sev_mult", 1.0),
            "eff_delta": kw.get("eff_delta", 0.0),
            "cascade_mult": kw.get("cascade_mult", 1.0),
            "generations": kw.get("generations", 1),
            "sev_shock_sigma": kw.get("sev_shock_sigma", 0.0),
            "dep_layer": kw.get("dep_layer", True),
            "dep_freq_mult": kw.get("dep_freq_mult", 1.0),
            "dep_recursion": kw.get("dep_recursion", True),
            "beta": kw.get("beta", 0.10),
            "beta_cap": kw.get("beta_cap", 1.5),
            "cc_gamma": kw.get("cc_gamma", 0.10),
            "dep_load_delta": kw.get("dep_load_delta", 0.05),
            "failover": kw.get("failover", True),
        })
        p95 = run["portfolio"]["residual"]["p95"]
        levers.append({
            "id": lid,
            "label": label,
            "residual_p95": p95,
            "residual_p50": run["portfolio"]["residual"]["p50"],
            "delta_p95": p95 - base_res["p95"],
            "delta_p95_pct": round((p95 / base_res["p95"] - 1) * 100, 1) if base_res["p95"] else 0.0,
        })
    levers.sort(key=lambda x: -abs(x["delta_p95"]))

    # calibration table — the per-pattern evidence behind the parameters, one place
    table = []
    for pid, p in _PATTERNS.items():
        em = p.get("exposure_model") or {}
        f = em.get("incident_frequency_per_year") or {}
        s = em.get("severity_distribution") or {}
        cc = p.get("compensating_controls") or {}
        table.append({
            "pattern_id": pid,
            "freq_p50": f.get("p50"), "freq_p95": f.get("p95"),
            "freq_basis": f.get("recalibration_note")
                or "operator judgment — v2.0b re-anchor; superseded base-rate formula kept for the trail",
            "sev_p50_usd": s.get("p50_usd"), "sev_p95_usd": s.get("p95_usd"),
            # r29 — the refs must TRAVEL with the number: per-pattern severity
            # re-anchor basis (IBM CODB / Uptime / ITIC citation) as data
            "sev_basis": s.get("reanchor_basis") or "",
            "worst_anchor_usd": s.get("worst_anchor_usd"),
            "worst_anchor_basis": s.get("worst_anchor_basis") or "",
            "controls_eff_pct": cc.get("avg_effectiveness_pct"),
            "cascade_out_edges": len(p.get("cascade_to") or []),
            "control_evidence": control_test_evidence(pid),
        })

    # Round-12 external ask: the moderate σ=0.3 lever headlines the tornado while
    # the fatter shocks lived only as judgment-log prose — price the choice as
    # DATA so the render can show moderate-vs-fat-tail side by side. Same engine,
    # same seed; the σ=0.3 point reconciles with the sev_shock lever by
    # construction (audit-gated).
    sev_shock_sweep = []
    for sigma in (0.3, 0.5, 0.6):
        run = aggregate_loss_mc(seed, trials, sev_shock_sigma=sigma)
        p95 = run["portfolio"]["residual"]["p95"]
        sev_shock_sweep.append({
            "sigma": sigma,
            "residual_p95": p95,
            "delta_p95_pct": round((p95 / base_res["p95"] - 1) * 100, 1) if base_res["p95"] else 0.0,
        })

    return {
        "baseline": {
            "residual_p50": base_res["p50"], "residual_p95": base_res["p95"],
            "residual_p99": base_res["p99"], "seed": seed, "trials": trials,
        },
        "levers": levers,
        "sev_shock_sweep": {
            "points": sev_shock_sweep,
            "note": (
                "The BLANKET severity shock priced at three strengths — σ=0.3 is the operator's "
                "moderate read (the lever above); σ=0.6 approximates a CrowdStrike-class "
                "common shock. The headline uses σ=0 (blanket shock excluded; the common-CAUSE "
                "co-movement term γ is separately IN the headline — severity_comovement): the choice is "
                "logged in the judgment log, challengeable, and priced here instead of buried."
            ),
        },
        "calibration_table": table,
        "judgment_log": list(_JUDGMENT_LOG),
        "method_note": (
            "One-at-a-time (OAT) shocks on the seeded correlated MC — each lever moves "
            "exactly one calibration judgment and re-runs the full 20k-trial simulation "
            "— plus two JOINT shocks (bad-year: freq×1.5 + eff−20; fat-tail: sev×1.5 + "
            "cascade×1.5) because OAT understates interaction effects. Still not a full "
            "probabilistic sensitivity; the honest first two instruments. All runs are "
            "seed-deterministic and re-runnable. The judgment log records who set each "
            "calibration judgment, when, on what basis — and the 2LoD challenge each "
            "one invites."
        ),
    }


# ── E1 · dependency analysis — "which single thing takes the most P95 with it" ──

def dependency_analysis(seed: int = 42, trials: int = 20000) -> Dict[str, Any]:
    """The dependency tornado — the question a CRO actually asks of a platform:
    which ONE shared dependency carries the most of the tail. For each node in
    the catalog, re-run the SAME seeded MC with that node's contributions
    suppressed (RNG-stream-aligned: draws still consumed, effects zeroed — see
    _simulate) and report the ceteris-paribus P95 delta. The top of this
    tornado IS the concentration-risk agenda, priced; each per-node delta is
    also the value of removing that dependency (the multi-region / multi-
    provider / cell-isolation business case, from the model's own numbers)."""
    base = aggregate_loss_mc(seed, trials)
    base_p95 = base["portfolio"]["residual"]["p95"]
    cat = load_dependency_catalog()
    nodes_out = []
    for nd in cat.get("nodes") or []:
        run = aggregate_loss_mc(seed, trials, dep_suppress=(nd["id"],))
        p95_wo = run["portfolio"]["residual"]["p95"]
        delta = base_p95 - p95_wo
        nodes_out.append({
            "id": nd["id"],
            "name": nd["name"],
            "layer": nd["layer"],
            "containment_boundary": nd["containment_boundary"],
            "annual_freq": nd["annual_freq"],
            "residual_p95_without": p95_wo,
            "delta_p95_usd": delta,
            "delta_p95_pct": round(delta / base_p95 * 100, 1) if base_p95 else 0.0,
            "fan_out_patterns": sorted({f["pattern_id"] for mode in ("loss", "blindness", "degraded")
                                        for f in (nd.get("fan_out") or {}).get(mode) or []}),
            "response_recursion": nd.get("response_recursion") or None,
            "anchors": nd.get("anchors") or [],
            "freq_basis": nd.get("freq_basis") or "",
            "mitigation_note": nd.get("mitigation_note") or "",
        })
    nodes_out.sort(key=lambda n: -n["delta_p95_usd"])
    dep_model = base.get("dependency_model") or {}
    layer_off = dep_model.get("layer_off_counterfactual") or {}
    return {
        "baseline_residual_p95": base_p95,
        "nodes": nodes_out,
        "one_thing": nodes_out[0] if nodes_out else None,
        "layer_contribution_usd": base_p95 - (layer_off.get("residual_p95") or base_p95),
        "layer_off_residual_p95": layer_off.get("residual_p95"),
        "domain_dependencies": cat.get("domain_dependencies") or {},
        "deferred_nodes": cat.get("deferred_nodes") or {},
        "source_status": cat.get("source_status"),
        "provenance_note": cat.get("provenance_note"),
        "method_note": (
            "Per-node ceteris-paribus suppression on the same seeded trial matrix "
            "(RNG-aligned — deltas are structural, not sampling noise). Each delta "
            "prices the tail the platform carries BECAUSE that dependency is shared; "
            "equivalently, the value of the architecture that removes it."
        ),
    }


# ── per-pattern expected loss ────────────────────────────────────────────────

def expected_loss_for_pattern(pattern_id: str) -> Optional[Dict[str, Any]]:
    """Compute per-pattern expected loss at P50, P95 + worst-anchor.

    Returns:
      {
        "pattern_id":         str,
        "p50_usd":             expected loss at P50 frequency × P50 severity
        "p95_usd":             stress-case expected loss at P95 × P95
        "worst_anchor_usd":    the cited worst-anchor severity (not multiplied by frequency)
        "frequency":           { p50, p95, ... },
        "severity":            { p50_usd, p95_usd, worst_anchor_usd, worst_anchor_basis },
        "computation":         human-readable description of the math
      }

    None if the pattern has no exposure_model.
    """
    p = _PATTERNS.get(pattern_id)
    if not p:
        return None
    exposure_model = p.get("exposure_model")
    if not exposure_model:
        return None

    freq = exposure_model.get("incident_frequency_per_year", {})
    sev = exposure_model.get("severity_distribution", {})

    f_p50 = freq.get("p50", 0) or 0
    f_p95 = freq.get("p95", 0) or 0
    s_p50 = sev.get("p50_usd", 0) or 0
    s_p95 = sev.get("p95_usd", 0) or 0
    worst = sev.get("worst_anchor_usd", 0) or 0

    p50_el = f_p50 * s_p50
    p95_el = f_p95 * s_p95

    return {
        "pattern_id":       pattern_id,
        "p50_usd":          p50_el,
        "p95_usd":          p95_el,
        "worst_anchor_usd": worst,
        "frequency":        freq,
        "severity":         sev,
        "computation":      (
            f"Expected loss P50 = frequency P50 ({f_p50}/yr) × severity P50 (${s_p50:,}) = ${p50_el:,.0f}. "
            f"Stress P95 = frequency P95 ({f_p95}/yr) × severity P95 (${s_p95:,}) = ${p95_el:,.0f} — an "
            f"UPPER STRESS SCENARIO (both tails coincide), NOT a fitted loss-distribution percentile; a "
            f"true P95 needs Monte-Carlo aggregation of a Poisson frequency × lognormal severity. "
            f"Worst-anchor (cited comparable event) = ${worst:,}."
        ),
    }


# ── portfolio roll-up ────────────────────────────────────────────────────────

def portfolio_exposure(report: Dict[str, Any]) -> Dict[str, Any]:
    """Portfolio annual-loss distribution — ONE seeded Monte-Carlo aggregate.

    P50 = expected annual loss, P95 = stress (1-in-20 year), from aggregate_loss_mc()
    (Poisson frequency × lognormal severity, summed across patterns) — NOT Σ of per-
    pattern P95 tails, which had inflated the stress ~6× to a non-credible figure. The
    headline is the RESIDUAL (net-of-controls) distribution, identical to
    inherent_residual.portfolio.residual, so the two blocks reconcile to one distribution
    (dissolves the reviewer's two-model finding). Inherent (gross) is surfaced for reference.
    """
    mc = aggregate_loss_mc()
    res = mc["portfolio"]["residual"]
    inh = mc["portfolio"]["inherent"]
    mc_by = {r["pattern_id"]: r for r in mc["by_pattern"]}

    # which patterns are firing + worst RAG (for the per-pattern view)
    firing_rag: Dict[str, str] = {}
    rag_order = {"green": 0, "amber": 1, "red": 2}
    for dr in report.get("domain_reports", {}).values():
        for f in dr.get("findings", []):
            pid = f.get("pattern_id")
            new = f.get("overall_rag", "green")
            if rag_order.get(new, 0) > rag_order.get(firing_rag.get(pid, "green"), 0):
                firing_rag[pid] = new

    per_pattern: List[Dict[str, Any]] = []
    for pid, rag in firing_rag.items():
        r = mc_by.get(pid)
        if not r:
            continue
        per_pattern.append({
            "pattern_id":         pid,
            "rag":                rag,
            "p50_usd_unweighted": r["inherent"]["p50"],
            "p95_usd_unweighted": r["inherent"]["p95"],
            "p50_usd_weighted":   r["residual"]["p50"],
            "p95_usd_weighted":   r["residual"]["p95"],
            "worst_anchor_usd":   r["inherent"]["worst_anchor"],
            "worst_anchor_basis": r["inherent"]["worst_anchor_basis"],
            "attribution":        r.get("attribution") or {},
            "induced_share_pct":  (r.get("attribution") or {}).get("induced_share_pct", 0.0),
            "computation": (
                f"{pid}: MC per-pattern annual-loss distribution — residual P95 "
                f"${r['residual']['p95']:,} (net of {r['controls_avg_eff_pct']}% realized controls), "
                f"inherent P95 ${r['inherent']['p95']:,}."
            ),
        })
    per_pattern.sort(key=lambda x: -x["p95_usd_weighted"])

    corr = mc.get("correlation_model") or {}
    cf = corr.get("independence_counterfactual") or {}
    return {
        "portfolio_total": {
            "p50_usd":            res["p50"],
            "p95_usd":            res["p95"],
            "p99_usd":            res["p99"],
            "mean_usd":           res["mean"],
            "inherent_p50_usd":   inh["p50"],
            "inherent_p95_usd":   inh["p95"],
            "worst_anchor_top": {
                "worst_anchor_usd":   mc["worst_anchor"],
                "pattern_id":         mc["worst_anchor_pattern"],
                "worst_anchor_basis": mc["worst_anchor_basis"],
            },
            "correlation_model":  corr,
            "load_dependent_induction": mc.get("load_dependent_induction") or {},
            "severity_comovement": mc.get("severity_comovement") or {},
            "dependency_model":   mc.get("dependency_model") or {},
            "recalibration":      mc.get("recalibration") or {},
            "sampling_error":     mc.get("sampling_error"),
            "computation": (
                f"Portfolio annual-loss distribution — seeded Monte-Carlo aggregation "
                f"(Poisson frequency × lognormal severity, seed {mc['seed']}, {mc['trials']:,} trials) "
                f"over {len(mc['by_pattern'])} patterns WITH one-generation cascade propagation along "
                f"the {corr.get('edges_used', 0)} declared cascade_graph edges (strength-keyed "
                f"induction probabilities, operator_calibrated), NOT Σ of per-pattern P95 tails "
                f"(percentiles do not add). RESIDUAL (net of controls): expected P50 ${res['p50']:,} "
                f"/ stress P95 ${res['p95']:,} / P99 ${res['p99']:,}. INHERENT (gross): P50 "
                f"${inh['p50']:,} / P95 ${inh['p95']:,}. Independence counterfactual (cascade "
                f"disabled): residual P95 ${cf.get('residual_p95', 0):,} — the delta is the "
                f"correlated-tail effect the cascade graph implies. Worst-anchor is the single "
                f"largest cited comparable, never a sum."
            ),
            "methodology_note": (
                "ONE distribution: inherent (gross) and residual (net) are views of the same seeded "
                "MC — inherent_residual.portfolio.residual carries the identical residual numbers, so "
                "there are no two competing 'P95' figures. 'Expected' = P50, 'stress' = P95. "
                "Percentiles are aggregated by Monte-Carlo, never summed across patterns. CORRELATED "
                "MC (v2.0c): the loss engine honors the same cascade_to edges the cascade graph "
                "renders — an incident can induce its declared downstream incidents in the same "
                "trial-year, so correlated tails are modeled rather than assumed away; the "
                "independence counterfactual is reported alongside for the delta. Induction "
                "probabilities are operator_calibrated judgment (a synthetic demonstrator has no "
                "co-occurrence history to fit). Frequencies calibrated to a large US consumer/crypto "
                "fintech archetype (operator judgment, not sourced); severity anchors are public "
                "events; control effectiveness carries an independent-validation haircut."
            ),
        },
        "by_pattern": per_pattern,
    }
