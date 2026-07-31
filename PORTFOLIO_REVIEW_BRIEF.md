# Portfolio Review Brief — FULL top-to-bottom deep review

**You are reviewing a personal portfolio (not employer work; all data is synthetic/seeded).**
This round is a **complete re-examination, not a delta review**: re-derive, re-click and try to
falsify EVERYTHING — every number, every claim, every page, every interaction — as if you had
never seen it. Two lenses at once:
1. **Adversarial honesty + rigor** — try to falsify any claim; name the file, the value, why it's wrong.
2. **Improvement + gaps** — assume it's basically sound and tell me what would make it *materially
   better*, and what's *missing*: analytical rigor, provenance, visual/UX, governance credibility,
   what an OCC / FRB / SEC examiner or a fintech CRO would still poke at. Be specific and prioritised.

> **Context.** All prior review rounds are closed — §0 is the ledger of what changed and why;
> use it to verify the fixes are real, not to limit your scope. **Since your last look (r44
> triage, §0.34), rounds r45–r56 (§0.35–§0.37) are new surface**: the journey scene redrawn as a
> real flow-graph (lanes, direction, the cycle lens, the blowup hub), the direction grammar swept
> onto every live canvas, the r44 one-identity-question header principle propagated to the atg/hv
> workbenches (signing personas retreat to where verbs are signed; hv drops them entirely),
> rac CLOSES on a board strategy decision surface — two priced postures plus the signed hold, every
> dollar C39-gated to recompute from its cited leaf — and atg severity moved from category to
> CONSEQUENCE (every rating derives from its own traces with a machine-gated basis; every critical
> is an unauthorized-action finding) —
> judged under the same zero-drift contract (classic pages frozen + fingerprint conservation
> reports). A known blind spot to avoid repeating: seven earlier AI review rounds verified data
> honesty and element existence but never CLICKED — a human then found dead navigation in
> minutes. **Serve the pages and drive the interactions** (§2.5–2.7, §3.6, and the §0.35 ATTACK
> steps); element presence and passing audits prove nothing about flow. The front-door
> restructure stays PARKED (§0.34): three reviewers produced three incompatible front doors, so
> the five-door IA stands until an unbriefed human cold-read decides — new evidence is welcome,
> re-argument is not.

---

## 0. What changed since the last review (verify these are real, not cosmetic)

1. **Exposure re-modeled — the $3.13B is gone.** The portfolio roll-up was `Σ(freq_P95 × sev_P95)`
   across patterns — wrong twice (tail×tail, then summing non-additive percentiles). Replaced with
   **one seeded Monte-Carlo aggregate** (Poisson frequency × lognormal severity, seed 42,
   20,000 trials) in `source/rac/exposure.py::aggregate_loss_mc`. Frequencies recalibrated to a
   large US consumer/crypto fintech; control effectiveness carries an independent-validation
   haircut. Current portfolio annual loss (RESIDUAL, net of controls): **expected P50
   $30.8M / stress P95 $98.1M / P99 $156.2M**; INHERENT (gross)
   P95 **$246.3M**. Tail ratio ~3.2× (was ~36×).
   *Round 5 (§0.10): the MC is now CORRELATED — cascade propagation along the declared edges —
   so these figures supersede the earlier independence-based ones.*
2. **One distribution, not two.** `exposure.portfolio_total` and `inherent_residual.portfolio`
   are now views of the SAME MC — a new audit gate (**C18 cross-surface reconciliation**) asserts
   the shared values agree, so the two-model incoherence cannot recur.
3. **No unsourced render data.** A new gate (**C19**) flags hardcoded `{name, score}` arrays and
   large `$` literals in the render layer — the check that would have caught the fabricated
   impact-faces (now computed from the impact-vector).
4. **AI-governance surface wired into a reachable view** (was render-but-hide).
5. **atg human-gate honesty:** the "no human gate" claim is now labelled as the
   *workflow-level attestation proxy* it is (a human reviewed the workflow, not the specific edge).
6. **Language purge:** the "armed" gun-metaphor was removed from the ENTIRE artifact — data,
   status values, DOM classes, CSS, and copy — not just the one status label. "Materiality" is
   used only as the reserved-to-Legal determination; the UI says which regulations are *triggered*.
7. **hv rebuilt as one Incident Flow Observatory.** The four static acts (compare/cascade/map/
   timeline) were folded into a single animated flow-graph: canvas topology with the incident
   playing over a scrubbable timeline, an ECG telemetry line riding each edge off the real seeded
   event series, flowing particles, pulsing severity node-glows, a blind-spot ghost node for the
   unobservable leg, a metrics header, a KRI scorecard, an escalation ladder, the manual-vs-
   instrumented gap, and an evidence log — all render-from-data across all three scenarios
   (`source/hv/hv_domain.js`, `renderObservatory` + `TOPO`). A new audit gate (**C5.4**) enforces
   that the observatory builds its series from `d.events`, maps KRIs from `d.kris_fired`, and
   derives the gap from `metricOf(...)`.
8. **Deep-review round-3 fixes.** From the last external pass: atg RE-04 no longer treats an
   *ungoverned* agent (no declared scope) as compliant, and RE-08 now does real cycle detection
   (general N-cycles via reachability, not just an immediately-repeated 2-cycle edge); the rac
   worst-anchor is attributed to its pattern (RP-04) instead of "None," and a visible
   **calibration-basis note** states the MC is an *illustrative seeded model, not a fitted loss
   history*; mobile overflow and accessibility (a document `<h1>` + `aria-live` on the live
   chain-verification) are closed. Note: one prior reviewer flagged "$3.126B still live" in the
   exposure block — that was a **stale read of an older bundle**; the build was reconciled at
   $82.75M at the time (check `exposure.p95_usd == inherent_residual.residual.p95`; the headline
   has since moved with the v2.0c correlated MC — see §0.10).
9. **Round-4 fixes + reproducibility.** hv provenance is now split at the right granularity
   (`shape_topology_provenance: source_derived` vs `shape_parameter_provenance: operator_calibrated`)
   — the failure-mode topology is cited; the specific tuned parameters are not, and no longer claim
   to be. **This bundle now ships the two generator INPUTS** (`source/data/`) so you can reproduce
   the seeded outputs yourself (§4) instead of trusting the code — the one gap prior rounds had to
   take on faith. An IP-hygiene pass also de-identified a peer-band example in the pattern metadata
   (a company name → generic public peers); it never rendered, but it shouldn't sit in the data.
10. **Round-5: the MC now honors its own cascade graph (v2.0c).** Both prior reviewers converged
   on the same headline: the loss engine drew all 13 patterns *independently* while the same
   projection declared 22 cause-effect edges — internally contradictory, and "diversification"
   was an artifact of the assumption. The engine now runs **one-generation cascade propagation**:
   each base incident tests its declared `cascade_to` edges once (strength-keyed induction
   probability, high 0.40 / medium 0.20 / low 0.10 — `operator_calibrated` judgment, disclosed),
   inducing correlated same-trial-year incidents. Induced incidents do not re-cascade
   (conservative; no cycle amplification). The **independence counterfactual is reported inside
   the projection** (`exposure.portfolio_total.correlation_model`): residual P95
   $68.4M without cascade vs $98.1M with — the correlated-tail delta is
   explicit, not hidden. Also this round: the exec-hero trajectory tile now carries a visible
   "prior: synthesized" tag (honesty-in-pixels, not just in data); the OCC App D note states it is
   an illustrative heightened-standards-STYLE mapping, not a claim of legal applicability to a
   $2–4B fintech; RP-01/RP-09's superseded base-rate formulas are labeled `derivation_status:
   SUPERSEDED STARTING POINT` (and RP-01's p50 now matches its cited 15%); the frequency
   re-anchor is now framed as **operator judgment, not a sourced peer study** (named-company
   peer references removed); and the atg inputs + hub KRI taxonomy YAMLs ship in the bundle
   (§4) — the last open reproduction ask.
11. **Round-5, the two P-level builds.** (a) **Calibration appendix** (both reviewers' P0 —
   "calibration is narrative, not evidence"): the rac IMPACT act now carries a **sensitivity
   tornado** — eight seeded one-at-a-time re-runs of the correlated MC, each shocking exactly one
   calibration judgment. Stress P95 spans **$64.2M–$186.6M**
   around the $98.1M headline; the top lever is control effectiveness (−20 pts →
   +52.7%), i.e. the surface itself tells a 2LoD which judgment to challenge first. Plus a
   per-pattern calibration table (frequency judgment · severity anchors w/ cited public events ·
   control eff). Audit gate C20 (4 checks) asserts the levers actually moved the engine and the
   cascade-off lever reconciles byte-exact with the counterfactual. (b) **The landing**
   (both reviewers' P1 — "three demos, thesis is author knowledge"): `dashboards/landing.html`
   now leads with the one-substrate/three-lenses claim — substrate diagram (signals → findings →
   lineage → residual $ → replay over the KRI spine) and a "same risk, three views" strip built
   from the real crosswalk rows (DR-01 priced by RP-01 / replayed by HV-02; DP-01 priced by
   RP-06 / caught at runtime by RE-03), with honest "—" where a modality doesn't exercise a KRI.
12. **Round-6 — every finding from the last double-review, closed.** (a) *"Conservative" had the
   conservatism backwards* (quantified by the reviewer, reproduced by us to the decimal): the
   one-generation cascade truncation is stable but risk-UNDERSTATING — gen-2 lifts residual P95 to
   $111.0M (+13.2% — current-build value; the round-6 world said a then-current $148.3M/+9.7%).
   Fixed as data: **"Cascade generations 2" is now a tornado lever**, and every
   note says "stable but risk-understating" instead of "conservative." (b) *Severity independence*
   (counts correlate, severities don't) now disclosed in the visible calibration note, not just the
   docstring. (c) **MC sampling error ships**: order-statistic 95% CI on the quantile estimates
   (P95 ±~2%, P99 ±~5% at 20k trials), in the projection and on the tornado headline. (d) rac
   `first_detected` now carries the same **provenance envelope** atg uses — status `illustrative`
   (honestly different from atg's `derived`: atg has real trace timestamps; rac's input is
   synthetic and the envelope says so). (e) Treatment **team handles honestly tagged** ("A8
   requires a NAMED HUMAN for live actions; seeded routing is team-level by design"). (f)
   **Calibration depth**: two JOINT shocks (bad-year freq×1.5+eff−20 → $186.6M,
   +90.2% — current-build value, visibly super-additive, the OAT limitation shown as
   data; the round-6 world said $278.1M/+105.7%, then-current) + a **challenged-judgment log**
   (who set each judgment, when — real git dates — on what basis, and the 2LoD challenge each
   invites) + a "How a 2LoD would challenge this" box where the severity-comovement challenge
   honestly answers "not modeled — the one challenge without a lever." (g) **Regulatory residual
   view**: residual $ per triggered regulation from the SAME trial matrix (within-trial subset
   sums, never summed percentiles — the naive Σ ships as the labeled anti-example; audit C21
   gates subset dominance). 95% of portfolio stress-P95 sits under the OCC-style mapping, 50%
   under SEC 8-K. (h) **Monday-morning screen** atop DECIDE: the three decisions to force this
   week — owner, residual $ at stake, triggered regs, the A8 verb the treatment state waits on.
   (i) Landing: **shared-object strip** — DR-01/DP-01/AS-02 shown across their lenses with values
   hydrated from the three sealed projections (never typed into the page); bundle links now work
   offline. (j) Bundle ships `hub/action_log.py` + `hub/provenance.py` — the last unreproduced
   layer. One reviewer claim was wrong and unfixed on purpose: "delta_pct all None" — the field
   is `delta_p95_pct` and it is populated.
13. **Round-8 — the DEPTH pass (human review: "so simple it borders unlikely to occur").** Four
   builds, all illustrative-labeled: (a) **Organizational reality** — per-pattern `org_context`
   (why remediation actually stalls: migrations owning the same headcount, exec-committed
   launches, budget freezes, Legal's queue; who is accountable BY NAME; which committee decides,
   with dates; what escalating costs politically). The Monday-morning screen now says 2LoD's real
   levers — table it, formal challenge, decline to counter-sign, escalate to CRO — instead of
   pretending it can "force" anything. (b) **Global regulations** — materiality grows 4 → 8:
   EU DORA Art. 17–19, UK FCA PS21/3 / PRA SS1/21 impact tolerances, NYDFS 23 NYCRR 500.17,
   PCI-DSS v4.0 (honestly framed as contractual), each with licence-dependent applicability
   caveats; the regulatory-residual view now shows DORA carrying $58.3M
   of stress-P95 — the second-biggest obligation bucket. (c) **Engineering scale** — hv
   recalibrated from toy magnitudes to a ~420k msg/s 3-region topic over 768 partitions: kafka
   peak backlog is now **~2.38M messages**, deploys at 38k req/s/service, velocity 9.2k → 74k tps.
   **Your previously recorded hv reproduction values (peak 5,695 etc.) are SUPERSEDED by design**
   — re-run `run_scenario(..., seed=42)` against this bundle's source for the new peaks; shapes,
   physics, and detection-gap minutes are unchanged. Plus war-room timelines per scenario ×
   regime — the PEOPLE inside the response gap, minute marks consistent with the response
   metrics. rac's RP-01/RP-09 superseded derivations retold at CD scale (78k deploys/yr,
   material conversion 1e-4 — no more "weekly release train"). (d) **Audit lifecycle** — an
   internal-audit register on ATTEST with the states that make a 3LoD shop real: management
   responses, target dates (one re-baselined, one PAST DUE), a REPEAT finding, an exam-style
   (MRA-analog) regulator-visible item, and one closure with re-test evidence. Audit gates C23
   (×4) enforce the lifecycle completeness; rac audit now 63 gates.
14. **Round-9 — vocabulary, scale composition, OSCAL end-to-end, a2a-cards, dead code.** (a)
   **"Breach" reserved for its real meaning** (user correction: governance/cyber term) — ~350 sites
   renamed across data keys, JS↔CSS contracts and prose (`signals_exceeded`, `slo_violation`,
   `velocity_surge`, severity tier `critical`); regulator-correct uses kept (GDPR Art. 33, state
   breach laws, Reg S-P, FCA tolerance, IBM *Cost of a Data Breach*); the hv attestation chain was
   RE-SEEDED, not edited, since its text is hash-linked. **Your previously recorded scenario id
   `velocity_breach` and field names (`slo_breach`, `breached_signals`, `breach_ratio`) are
   RENAMED** — update your re-run scripts. (b) **Scale = composition**: the platform context is now
   ~500 K8s apps · 1,000+ namespaces · multi-region HA; kafka is a ~96k msg/s slice of a 10B+/day
   cumulative pipeline, and the storm is a rebalance stall (92% of consumer capacity parked ~2.5
   min) → **peak backlog ~11.85M messages**, full drain in a 600s scenario; `duration_s` is now
   counted from the stream. (c) **OSCAL end-to-end**: assessment-plan + assessment-results
   generated from the live rac findings (reconciled 1:1 — re-run `source/oscal/validate_shipped.py`
   S8.1 for the current count; risk statuses map treatment states;
   no-SSP simplification disclosed in plan remarks) and the catalog is **dual-jurisdiction
   mapped** — US: NYDFS 500 / FFIEC / NIST CSF 2.0, EU-Global: ISO 27001:2022 Annex A + the
   27017/27018 cloud pair — validate.py 18/18, incl. an official-schema shape gate on every
   control-selection (round-10 external trestle validation caught an invalid AR; fixed +
   gated). **Re-executable from this bundle**: `python3 source/oscal/validate_shipped.py`
   re-runs every check except byte-reproducibility (repo-side only) against the shipped
   JSONs, including the findings reconciliation vs the co-shipped rac projection. (d) **a2a-cards
   graduates from roadmap to working demonstrator**: Ed25519-signed identity cards for all 10
   known agents, verifier with a TAMPER gate (adds a scope to a signed card, asserts the
   signature breaks), a NO-SCOPE-DRIFT gate against the same AGENT_SCOPE the RE-04 classifier
   enforces, and seed-42 trace reconciliation — 10/10; committed TEST key loudly disclosed
   (`a2a/` in this bundle). (e) QA-2 closed: the legacy app-nav dead code is deleted, not
   silently kept.
15. **Round-11 — trajectory honesty, coverage≠effectiveness as a GATE, σ swept, re-executable
   claims.** (a) **Trajectory bug (external catch): the current-period row was a mock re-run** —
   it showed green/2026-Q2 on a red 2026-Q3 register, and the forecast extrapolated over the
   mock's zero. The current row now post-reconciles period/RAG/count from the REAL report and
   the forecast is recomputed from the corrected series; synthesized priors relabeled to the
   three preceding quarters. (b) **Coverage-vs-effectiveness propagated as a class, then
   gated**: 11 control bases rewritten to state what the coverage stat does NOT prove (4
   re-scored: ITGC audit 95→88, KEV 95→93, MFA 98→96, DR tabletop 95→88 — the MC input is
   untouched, headline unchanged); new audit gates C24 (×3) fail any control credited ≥90
   without an explicit effectiveness rationale — rac audit now 66 gates. **Register count
   moved 26→27** (calibration inputs feed the seeded generation; counts reconcile everywhere
   by C1, and the new findings carry the full enrichment schema). (c) **σ=0.3 is swept, not
   asserted**: the severity-common-shock judgment-log entry now prices σ=0.3/+9.1%,
   σ=0.5/+26.6%, σ=0.6/+40.1% at P95. (d) **Applicability flags now reach the Monday-morning
   docket** († on style-mapping/contractual regimes) and the regulation view carries a legend.
   (e) The landing's shared-object strip **hydrates standalone** via a build-time snapshot of
   the sealed projections (labeled as such when used; live fetch always wins when served).
16. **Round-12 — the class completes, and every claim gets a runner.** (a) **Coverage ≠
   effectiveness finished class-wide**: the round-11 fix stopped at the ≥90 bar; external
   review re-opened it below the bar, and the broadened detector found the class was 17
   controls, not the 8 flagged (the register's own "% identities…"-style stats under-matched
   both regexes). All 17 bases rewritten with the split (scores untouched — the discount was
   already priced; the basis now says why); **new gate C24.4** enforces the split at EVERY
   credit level, and the C24 detector now matches bare "% " stats. To the reviewer who asked
   for the check ID: **C24.1–C24.4 in `audits/audit_v2_0a.py`** (this bundle ships it there,
   not under source/). (b) **σ priced as data, not prose**: `sensitivity.sev_shock_sweep`
   carries the three priced points; the tornado renders a moderate-vs-fat-tail call-out from
   it, and gate C20.7 asserts the sweep is monotonic and its σ=0.3 point reconciles byte-exact
   with the lever. (c) **C24 in the pixels**: the control-evidence table chips every
   coverage-stat control (hover = full basis) and footnotes the gates. (d) **Applicability is
   now a filter**, not only a flag: the regulation view toggles to binding/licence-scoped
   rows only. (e) **`python3 verify_bundle.py` (bundle root)** re-executes every
   in-bundle-checkable claim in one command: OSCAL conformance, projection reconciliations,
   dashboard↔projection agreement, the landing snapshot, the QA report's own arithmetic, the
   README headline vs the data, a2a card shape — with the repo-side-only checks disclosed,
   not hidden. (f) **Correction you should hold us to — the register was NOT reproducible
   until now.** verify_bundle's first run caught the OSCAL AR (25 findings) disagreeing with
   the projection (26); root cause: the telemetry generator's `RISK_RNG_SEED` hook existed
   since v2.0a-alpha2 but nothing ever set it, so every register rebuild rolled unseeded
   dice — three rebuilds minutes apart yielded 27, 25, then 26 findings. The register
   movements earlier briefs attributed to data edits (25→26 in round 10, 26→27 in round 11)
   were **noise, not signal** — the DOLLARS were always seed-42 stable; the FINDINGS were
   not. Fixed: determinism is now the default (seed `2026-Q3-baseline`, re-seeded per run),
   new gate **C25** asserts two consecutive runs produce the identical register, and the
   canonical register is **25 findings**. If you recorded a 26- or 27-finding register in a
   prior round, it was an unrepeatable draw; this one re-runs.
17. **Round-13 — the loop converges.** (a) **The fat-tail range now rides the headline
   itself**: the exec-hero residual tile carries "excl. severity co-movement: up to +40.1%
   at σ=0.6 (priced ↓)" rendered from `sev_shock_sweep` — the σ=0 choice is visible at the
   point of reading, not two panels down. (b) **C24 ported into `verify_bundle.py`** (B8.1–
   B8.2, same regexes, runs on the shipped `risk_patterns.json`) — the newest gate is now
   cold-reviewer-verifiable without the repo; C25/C20.7 stay repo-side (they re-run the
   generator/engine) and B8.3 says so. (c) **Register churn: decided — versioned content.**
   With determinism default (round-12), the register only moves when `risk_patterns.json`
   or the pipeline changes, and both are git-visible; C25 re-proves stability on every
   audit run. The 25-finding register IS the canonical scenario. (d) On "make C24 active at
   the point of decision": for a generated artifact the BUILD is the point of decision —
   C24 failing the audit blocks the number from ever reaching the tornado or the docket.
   There is no runtime credit-entry workflow to gate; a production deployment would put the
   same check in the control-attestation intake path.
18. **Round-14 — the platform grammar: pages argue, they don't accumulate.** The failure this
   round wasn't a number — it was FLOW (human review: "endless scroll… what are we trying to
   say? what's in it for the reader?"). Every surface now follows one grammar: (a) each app
   ships a **read page** (`dashboards/<app>/read.html`) — a one-viewport three-chapter argument
   (countdown numeral, a live flow-picture, the ledger) whose every sentence and number renders
   from the sealed projection; generators author chrome only (zero-drift). (b) The workbenches
   carry a **role-sequenced spine** — `#role=engineering&node=…` deep links; roles re-sequence
   the walk, they never re-value; `#canonical` expands everything for comparison. (c) hv's three
   scenarios are now three visibly DIFFERENT failure shapes — a backlog tank that fills, a blast
   cone that widens, a fork whose blocked branch thickens behind a closing gate — all driven by
   counted series at the scrub tick, no invented components. (d) Each pre-grammar page is
   **frozen as `classic.html`**, and **conservation manifests**
   (`source/qa/conservation_report*.json`) prove the new views lost nothing. Classic is
   re-frozen at every ENGINE EPOCH and each freeze is loudly recorded in the manifest's
   run_at chain — E1 (dependency layer) → E2–E5 (identity/perimeter/cascade/model terms) →
   r29/r29b (the reference re-anchor + refs-travel amendment) → r30 (attribution +
   model-term visibility): if you diff classic across git history, that chain is the
   complete explanation. The manifests hash the exact shipped builds (C26.2/C20.4
   freshness gates): in-browser own-text
   fingerprints per data-target (numeric multisets + protected RAG tokens), classic vs
   `#canonical`, per scenario for hv. The probe CAUGHT one violation during this round — a
   chrome caption minting the protected token "red" — reworded before the reports were cut.
   New audit gates: rac C26–C27, atg C20.1–4, hv C8.1–4 (spine mounts resolve, role paths are
   permutations, §8 headline genre, conservation freshness). **Path change: dashboards are now
   per-app folders** (`dashboards/rac/index.html`, not `dashboards/rac.html`) so every in-app
   relative link (read ↔ workbench ↔ classic) works offline without rewrites — update any
   recorded paths from earlier rounds.
19. **Round-15 — both round-14 reviews closed, and the interaction matrix lands.** (a) *Mobile
   regression (Claude M1)*: the 5-col translation strip forced a 564px document at 390px —
   stacks at ≤620px now; every surface re-measured clean at 390. (b) *Narrowed guarantee
   (Claude M2)*: spec §6's seal-equality clause amended to the actual invariant and **B10.1–3**
   added — numeric-LEAF multiset equality across classic/index/read, re-derived in-bundle
   (1,692/79/748 leaves per app). (c) *read.html gated (Claude N3)*: `read_sha256` +
   disposition in every conservation report; audit freshness gates cover it. (d) *Shapes on
   the front door (GROK #3)*: the hv read's race canvas draws the per-scenario tank/cone/fork
   glyph with counted captions; scenario chips carry matching icons. (e) *Power-user friction
   (GROK #1)*: a persistent **workbench ↗** link rides every read masthead. (f) **The
   interaction matrix (GROK #2/#6)**: `source/qa/interaction_matrix.json` — 88 recorded
   checks driving the real DOM (role × node with geometric only-active-node assertions +
   per-node visible-text distinctness, walkers, map/Escape, pills, drop-down, browser back,
   chapters, keys, live deep links). It CAUGHT and fixed three real defects during the run:
   reads parsed `#act=N` only at load (live hash/back dead → hashchange bound), the atg read
   resolved its projection glob-last (a stray mis-build projection silently swapped its data →
   generators pinned to canonical), and the ia map had no Escape binding (added). (g) *Prose
   drift beyond numeric/protected tokens (GROK #4)*: **accepted + disclosed limit** — C26d
   text-hash changelists with mandatory acknowledgment, not semantic freezing; stated in each
   conservation report.
20. **Round-16 — both reviewers' residuals dispositioned, none silently.** (a) *Leadership
   cockpit (flagged twice)*: FIXED — `body[data-role="leadership"]` hides keyboard hints,
   per-row verbs, and the domain rail via display rules only (textContent and the
   conservation fingerprints untouched — re-probed to prove it); acknowledged in every
   conservation report. (b) *Rail precedes the argument*: same fix, same acknowledgment.
   (c) *Cross-build drift unchecked*: `source/qa/numeric_baseline.json` + **B11.1–3** pin
   the numeric-leaf multiset across releases — changing numbers now requires re-cutting
   the baseline in the same commit. (d) *Matrix evidence summary-level*: the assertion
   harness ships (`source/qa/interaction_matrix_runner.js`) — paste-per-page, prints
   per-check evidence; coverage is re-executable. (e) *Thesis numbers ride prose*: the §8
   genre gates now include `ia.thesis` (C27.3/C20.3/C8.3). (f) *Workbench→read one-way*:
   every spine carries a chrome "↞ the read" backlink. (g) *Spine statefulness*: DECLINED
   deliberately and recorded in the spec — position lives in the hash (durable across
   reload/copy-link); enforcing progression would break deep links, the map, and audit's
   attack-first entry. (h) *rac read chapter-2 density*: acknowledged as the softest
   argument node — held for the human FE reviewer's call rather than reworked over the
   reviewers' heads; it is the acceptance-test surface.
21. **Round-17 — the persona reads become surfaces.** Warm CRO/examiner/hiring-manager
   persona reviews + a first fully-cold fresh-session read produced four builds:
   (a) **Leadership one-number opening** (CRO: "five dollar figures before my first sip of
   coffee") — under `#role=leadership` the residual tile leads 2×2 with the single-judgment
   range line ("holds $X–$Y under any single challenged judgment"), everything else recedes;
   display-only, zero role minting (re-probed). (b) **Perimeter selector** (examiner: "a
   toggle is not proof of re-mapping logic") — declare a charter (fintech-MTL default /
   national bank / EU EMI) and the regulation view re-maps: in-perimeter dollars are UNION
   subset sums from the SAME trial matrix, computed in the projection (never in render),
   statuses re-label the disclosed applicability facts, and every profile carries the
   reservation to Legal/Compliance. Gated by **C28.1–4**. (c) **`rac/validation.html`** —
   the model-validation dossier: engine spec, sampling CI, tornado, σ-sweep, judgment log,
   and the three open items an examiner would file. Same sealed projection, hydrated
   client-side, gated by `validation_sha256` freshness + B10 numeric equality across all
   FOUR rac views. (d) A presenter kit exists repo-side (generated from the sealed
   projections) — deliberately NOT in this bundle: a cold read that ships its own coaching
   isn't cold.
22. **Rounds 18–21 — the loop turns inward, then the portfolio learns to speak.** (a)
   **Defect-class ledger** (`source/qa/DEFECT_CLASS_LEDGER.md`): all 16 defect classes from
   the full review history, who caught each first, and its standing guard — 14 machine-gated,
   1 disclosed trade (prose), 1 human-only (persuasion). Three new class gates landed with it
   and each CAUGHT a real defect on its first run: zero-JS-errors (an unguarded
   `e.target.matches` that killed the rac keyboard layer), viewport-overflow (the brand-new
   validation dossier shipping 743px wide at 390), and read-renders-its-own-projection (the
   glob-bug class, gated class-wide). (b) **A11y machine-gated** (was the last manual class):
   aria-current on the active pill, aria-modal map with a focus round-trip, live-region step
   header, synced accordion semantics — enforced by runner rows; the fix itself introduced a
   boot-killing bug the runner caught next sweep. (c) **The landing argues now** (human FE
   verdict: "wordy, dull, preaching"): ~450 words of prose cut to ~90; three LIVE numbers ARE
   the doors (then-current $135.2M P95 / 16 findings / 10→2 min, hydrated, never typed); all copy swept to
   plain English. (d) **`tour.html` — the 2-minute tour**: the portfolio-level answers made
   visible — the six organs of a 2LoD platform as live deep-linking chips, scope declared
   in/out in the artifact for the first time, the trust board (every count EXECUTED by
   `cut_trust_board.py` and written to `source/qa/trust_board.json`, never typed — the
   closed-bar teaser self-computes "297 checks executed"), the ±span device ("a heat map
   cannot say this"), real-vs-illustrative as columns, the 10→2 economics, and
   "swap the inputs, keep the engine and gates" as three visible steps.
23. **Rounds 22–23 — the decision graph closes, then the number learns to travel.** (a) All
   three round-22 reviewers converged on one P0 — the CRO could reach the then-headline
   (was $135.2M) but had to hunt
   for this week's decisions. Closed: the leadership hero carries a live CTA ("this week's
   three decisions · $63.4M at stake" — the then-current CTA → the docket in ONE click); the docket sum became a
   sealed leaf (`ia.derived.docket_at_stake_usd`) and gate **C27.4** now fails the build if any
   $ spoken by a headline lacks a matching numeric leaf (it caught this very figure on first
   run). Role switches preserve your node when it exists on the new path. (b) A one-character
   generator escape shipped an unparseable inline script and silently killed the whole page
   runtime — caught, and now machine-gated on every SHIPPED page (**C29.1/C20.5/C8.5**:
   node --check the generated JS, not the source). (c) **`rac/board.html`** — the Board
   brief: one printable page (the number → what challenging it does → the three decisions →
   regulatory posture → the productionization contract), hydrated ENTIRELY from the same
   sealed projection; **B10 asserts exact leaf equality** with the workbench, so the brief
   cannot say a number the workbench doesn't. ATTACK: diff its every figure against
   `projections/rac.projection.json`. (d) **org-reality** — the docket walk's aggregate org
   panel: who answers for the 8 reds (with the residual riding on each name), which committee
   dates the decisions sit on, and the A8 gap as data — `treatments_team_routed` (25 of 25
   route to a team handle, not a named human) is a sealed leaf, not prose. ATTACK: recompute
   both aggregates from the projection's `org_context`/`treatment` blocks. (e) The
   productionization contract is now explicit in `rac/validation.html` §7 — what swaps, what
   cannot change, and acceptance decided by the gates re-running green on real inputs.
25. **E1 — THE ENGINE CHANGED: the shared-dependency layer.** Every number in this bundle
   re-sealed (residual P50 $38.3M→$54.4M · P95 $135.2M→$182.4M · P99 $242.6M→$321.6M).
   The author's charge: the old model was SPEECHLESS about an AWS region loss, a customer-
   auth-plane outage, an etcd quorum loss — pattern-to-pattern cascade edges cannot express
   one structural event UNDER several risks at once. E1 adds 8 first-class common-cause
   dependency nodes (cloud region · CUSTOMER identity/session plane · API registry/service
   discovery · K8s control plane/etcd · workforce IdP · primary datastore · payments
   processor · security-agent vendor), each with public-incident-anchored loss frequencies
   (us-east-1 2021/2017, Auth0 2021, the 2021-01 brokerage login failures, Fastly 2021,
   Reddit Pi-Day 2023, Datadog 2023, Visa 2018, CrowdStrike 2024) and a declared pattern
   fan-out with severity multipliers. Per trial, structural LOSS events inject correlated
   incidents across the fan-out — the common-cause fat tail. The DEPENDENCY TORNADO
   (workbench, stake beat; per-node ceteris-paribus suppression on the same seeded trials,
   RNG-stream-aligned) answers the question a CRO actually asks — which single thing takes
   the most of my P95 — and leads with the customer identity plane (−$14.4M at the E1 seal). The whole
   layer added $45.4M to P95 at that seal; the pre-E1 form ships as the dep_layer_off counterfactual AND
   sensitivity lever. HONESTY TRAIL: a first build that also injected degraded-mode events
   was REJECTED for double-counting the expected year (P50 would have hit ~$83M); the
   attribution judgment is entry #1 on the challenged-judgment log (dep_attribution),
   lever-bounded both ways (dep_freq_up ×2). Gated by C30.1–4 (anchors/coverage/tornado-
   recompute/counterfactual-reconcile — rac is now 85 gates); the Board brief's challenge
   tiles gained the concentration question, priced. ATTACK VECTORS: (a) recompute any
   tornado bar from the sealed projection + catalog; (b) challenge the loss frequencies
   against their anchors; (c) argue the attribution judgment (are structural losses really
   absent from the base per-pattern rates?); (d) the CONSERVATION EPOCH — classic was
   re-frozen at E1 (pre-E1 classic archived as classic_pre_e1.html); verify the freeze is
   clean and the epoch is loudly recorded in DATA/conservation_report.json.
26. **E2–E4 — THE ENGINE ROADMAP COMPLETES. Headline at this stage (historical — superseded
   by item 27): P50 was $69.6M · P95 was $239.3M · P99 was $404.4M (each E-stage re-sealed
   every number; the ledger above is historical).**
   (a) **E2 — identity mechanics.** The customer identity plane gained a BLINDNESS mode
   (verification degraded while the plane is UP — an ATO/recovery-abuse wave firing
   RP-05/06/08; anchors 0ktapus/Twilio 2022, Okta session-token replay 2023), and RESPONSE
   RECURSION became a mechanism: a trial-year with an active workforce-IdP loss multiplies
   EVERY severity that year ×1.25 (Meta 2021-10-04 — responders locked out of the tools
   that fix the outage; recursion_off lever bounds it). The dependency tornado leads with
   the customer identity plane (−$37.0M at the E2 seal) — identity is the platform's largest structural
   concentration by the model's own arithmetic. hv gained its 4th scenario,
   `identity_outage`: detection near-parity, ACCESS the bottleneck (tool access 42→6 min);
   the observatory's 4th signature shape is the WALL, with the workforce-SSO ghost leg
   pulsing dark while responders are locked out. (b) **E3 — the broker-dealer perimeter.**
   Three regimes joined (11 total): finra_4370 (BCP), sea_17a4 (the hash-chained action
   log CLAIMS its books-and-records shape — audit-trail alternative per the 2022
   amendments), reg_sci (ILLUSTRATIVE CONDITIONAL — binds SCI entities, kept OUT of every
   dollar union). The 4th charter `us_broker_dealer` prices LOWEST ($195.5M-era) — honest:
   its union covers fewer patterns than the EU stack. (c) **E4 — cascade dynamics.**
   Induction is now LOAD-DEPENDENT: p_eff = p_edge × min(2.0, 1 + 0.15·max(0, concurrent −
   E[concurrent])) — supercritical years exist ($22.9M at P95 / $38M at P99 at the E4 seal, over the β=0
   form, which ships as counterfactual AND beta_zero lever, identical by construction).
   RP-14 "Skew & Backpressure Accumulation" is the 14th pattern — drift between things
   that must agree, KRIs in DIVERGENCE form (level-KRIs are what self-healing masks),
   Knight 2012 as the $440M anchor, the LOWEST control credit in the catalog (38%) by
   thesis. All 26 cascade edges carry propagation_layer + containment_boundary. THE
   HONESTY TRAIL: three engine builds were REJECTED pre-ship and are now ledger classes
   17-18 (double-counting; mis-centered mechanism) — the engine argues with itself and
   keeps the record. ATTACK VECTORS: recompute any tornado bar or β delta from the sealed
   projection; argue dep_attribution and dynamic_cascade on the judgment log; challenge
   the blindness/recursion/β calibrations against their anchors; verify the beta_zero
   lever ≡ the β=0 counterfactual and recursion_off ≤ headline; check every '13/14
   patterns' string DERIVES (the audit's own hardcoded counts were de-rotted); confirm
   classic re-froze cleanly at each epoch (E1–E4 entries in DATA/conservation_report.json).
27. **E5 + r29 — THE ENGINE'S LAST TERMS LAND, THEN THE AUTHOR ATTACKS HIS OWN NUMBER.
   Current headline: P50 $30.8M · P95 $98.1M · P99 $156.2M residual · inherent P95 $246.3M.**
   (a) **E5 — three model terms.** Severity CO-MOVEMENT under common cause (an active
   structural loss multiplies base+cascade severities that trial-year, γ=0.10 cap 1.3 —
   dep-INJECTED draws are excluded, see the honesty trail); LOAD-DEPENDENT dependency
   nodes (structural loss frequency rises with base-incident excess, δ=0.05 cap 1.25);
   FAILOVER-FAILURE escalation (region-bounded nodes carry failover_failure_prob with a
   named basis — cloud_region 0.25, primary_datastore 0.30 — and a failed failover
   escalates ×1.5). Each mechanism ships with an off-lever gated to only-lower (C32.1-2).
   (b) **r29 — the recalibration.** The author's own challenge, verbatim: the E5 headline —
   which was $312.2M residual P95 · was $549.4M P99 · was $815.4M inherent P95 — "sounds extremely high and
   fictitious … I am not saying blindly change but it needs to be defensible in scenario
   and math and refs." The autopsy found five compounding causes: sum(λ·E[sev]) had
   crept, at the time, to ~$91M/yr inherent EXPECTED loss; severity medians sat above reference data
   (then a $20M median vulnerability-exploitation loss vs IBM CODB 2024's $9.36M US mean
   BREACH); dependency fan-outs could stack ~8× multiplicatively on one draw; the cc
   term double-counted dep-injected incidents; and a first re-anchor pass fattened σ to
   ~1.65 by dropping medians more than p95s. The fix, in order: every severity median
   re-anchored to a NAMED reference (IBM CODB 2024 · Uptime Institute 2023 outage-cost
   bands · ITIC 2024) with a `reanchor_basis` string ON the pattern; p95/p50 ratios
   tightened to ~7× (σ≈1.18 — Basel/ORX op-risk severity practice); frequencies trimmed
   to Σλ=6.9/yr; fan-out severity mults capped at 2.0 and induced incidents at 1 (one
   structural event = ONE material incident per affected pattern); γ/δ/β cooled to
   .10/.05/.10; the cc double-count removed. Industry-decade catastrophes (Knight,
   Equifax, TSB) now live where they belong — in worst_anchor fields and the MC's tail
   COMPOSITION, not inside one incident's severity distribution. Result: P50 $30.8M =
   1.03% of the $3B revenue archetype (ORX-class typical year), P95 $98.1M = 3.27%
   (a Capital-One-adjacent stress year), P99 $156.2M BELOW the worst public comparable.
   The archetype revenue is now a sealed leaf (`meta.archetype_revenue_usd`) and gate
   **C33.1-3** holds all three bands PERMANENTLY — the operator's plausibility challenge
   became a machine gate (rac is now 96 gates). HONESTY TRAIL: the σ-fattening
   intermediate build was caught and rejected before ship; the whole story is judgment-log
   entry `aggregate_recalibration_r29`. The Board brief's why-moved line is now
   direction-NEUTRAL (numbers must be explainable when they fall, not only when they
   rise). ATTACK VECTORS: (a) recompute any pattern's p50→mean under lognormal σ≈1.18
   and check Σλ·E[sev] against the stated expected-loss frame; (b) challenge any
   `reanchor_basis` against its named source; (c) verify C33's bands against ORX/CODB
   yourself — argue the bands, not just the point values; (d) the r29 CONSERVATION
   EPOCH: exactly 15 numDiff targets, all dollar-bearing, zero role-minting — verify in
   DATA/conservation_report.json; (e) every superseded headline in this README must wear
   a transition marker (B6.2 now lists 10 values).
28. **r30 — THE ROUND WHERE OUR OWN PROSE WAS THE BUG, plus induced-vs-intrinsic
   attribution. Headline unchanged: P50 $30.8M · P95 $98.1M · P99 $156.2M (verified
   byte-identical through every change below).** Round-29 externals reported the E5
   severity-co-movement and dependency-load terms ABSENT. Triage found they were wrong —
   and right: both mechanisms were live (cc_sev_off $90.7M · dep_load_off $95.2M, gated
   C32), but the shipped correlation_model note still said severity co-movement "is not
   modeled" — OUR OWN STALE DISCLOSURE contradicted the engine, and the reviewers
   correctly read the prose. Fixed as a CLASS: every "co-movement excluded" claim swept
   across all surfaces (the blanket σ shock remains excluded and priced; the common-CAUSE
   γ term is in the headline and now says so), every E4/E5 mechanism ships a NAMED
   parameter block (severity_comovement γ/cap, dependency_model.load_dependence δ/cap,
   failover_escalation, alongside β) with off-lever pointers, and gate **C34** holds it:
   named blocks must exist and no shipped note may claim a modeled term is unmodeled.
   (b) **Induced-vs-intrinsic attribution** (external structural finding: RP-02 receives
   12 in-edges and a flat per-pattern $ misattributes induced load as intrinsic risk).
   The trial loop now counts provenance — own base draws vs cascade-induced vs
   dependency-injected — per pattern, in residual dollars: `attribution` +
   `induced_share_pct` on every by_pattern row, rendered on the per-pattern swimlane
   ("85% induced — treat upstream" on RP-06; RP-12 78%, RP-02 65%). Components sum to
   the portfolio residual mean EXACTLY (counting, not a second model) — gate **C35**
   (rac is now 102 gates). (c) The Board why-moved line names the prior seal from a new
   sealed `recalibration` leaf (was $312.2M at E5 → $98.1M), the validation limits
   chapter answers headline volatility with the C33 band + B6.2 marker machinery, the
   hardcoded "three items below" became a derived count, and COLD_READ now ships the
   dependency catalog + risk patterns (a reviewer re-derived from a pack that lacked
   the engine's inputs — re-derivability now travels with EVERY pack). REFUTATIONS
   RECORDED (fourth time for one of them): per-node dollar fields populated
   (delta_p95_usd/residual_p95_without on every node); the dependency layer already IS
   a Board ask (resolution 4 hydrates layer_contribution_usd); the docket is already
   single-sourced (ia.derived.docket_items, C27.5); RP-14 has been a full first-class
   back-pressure pattern since E4. ATTACK VECTORS: (a) recompute any induced share from
   the sealed by_pattern attribution and check Σ components ≡ portfolio residual mean;
   (b) grep the projection for severity_comovement/load_dependence — the parameters are
   data now, argue γ/δ against their judgment-log entries; (c) try to find ANY shipped
   sentence claiming an implemented term is unmodeled (C34.2 says you can't).
29. **r31 — THE AGENT ESTATE GETS ITS DEPENDENCY LAYER (the round-28 reviewer's
   'strongest remaining move', built).** atg now carries `data/agent_dependency_catalog.json`
   — five common-cause nodes of the AGENT substrate: the agent orchestrator, the model
   provider, the tool/MCP registry, the safety-classifier plane, and the credential
   broker. The structural twin of rac's E1 layer with one deliberate difference: NO
   dollars — atg's currency is workflows, traced actions and finding classes, and the
   catalog says so out loud (units_note; production attaches fitted agent-incident
   history before pricing). Every blast radius DERIVES at build time from the same
   traces and lineage the dashboard renders — the catalog declares WHAT each node
   underlies (a lineage node, a set of action types, or governs-all), never the counts.
   The lineage graph proves the headline: `agent-orchestrator` transits **16 of 16
   workflows** — the estate has a control plane and it is now on the register. Each
   node carries loss AND blindness modes; the sharpest is the classifier plane's:
   detections drop to zero while violations continue and the dashboard reads GREEN —
   absorbed violations accumulating unlogged, the divergence thesis on the agent
   substrate. Every node names its `rac_analog` (orchestrator≈k8s_control_plane,
   model_provider≈cloud_region, mcp_registry≈api_registry, classifier≈
   security_agent_vendor, credential_broker≈workforce_idp) — ONE mechanism, TWO
   substrates, and gate **C21.5** machine-closes the map against rac's catalog.
   Anchors are real public incidents (postmark-mcp 2025 · CVE-2025-49596 · OpenAI
   2023-11-08 · CrowdStrike 2024 · Okta 2023 · CircleCI 2023 · tj-actions 2025);
   where the class has no public precedent (a first-party orchestrator) the anchor is
   labeled CLASS_ANALOG — declared, not hidden. Renders as the third PROPAGATE panel
   (blast-radius bars + blindness rows + deferred-classes footnote). Gated by
   **C21.1–7** (atg audit now 63): reconciliation, taxonomy validity, DERIVED-not-
   asserted orchestrator blast, anchor completeness, cross-substrate closure,
   declared deferrals + no-dollar honesty, and renders-on-page. Ships in BOTH packs;
   **B12.3** verifies it travels (verify_bundle now 23). The audit's own C8
   taxonomy-boundary gate caught the first draft citing 'RP-14' inside atg — fixed
   to a nameless cross-reference; the machinery polices even the story about itself.
   ATTACK VECTORS: (a) recompute any blast radius from the shipped traces/lineage;
   (b) argue a fan-out RE mapping against the taxonomy; (c) argue the CLASS_ANALOG
   anchors; (d) try to find a fifth-node analog rac does NOT price — the asymmetry
   is now a feature with a seam you can probe.
30. **r32 — THE PROSE JOINS THE WORLD MODEL (and the gates prove they can fail).**
   (a) **B6.4, the world-consistency gate** — Claude's round-32 finding: a §0 feature
   sentence quoted the joint-shock lever at a then-stale $278.1M/+105.7% in live voice while the
   current lever said $186.6M/+90.2% — B6.2's fixed list could never catch a
   value it wasn't told about. Now EVERY $-token in this README must exist in the
   current sealed projections' numeric multiset, sit on a line wearing a history
   marker, or be part of a $X→$Y supersession pair (external benchmark citations
   allowlisted by name). The two live-voiced feature sentences (joint shocks, gen-2
   truncation cost) now DERIVE from the current levers — they can never lag the
   engine again — and the historical narrative lines the sweep flagged wear explicit
   markers. (b) **The falsification harness** (`source/rac/tools/test_gate_falsification.py`) —
   both reviewers converged on "C34/C35 are unfalsified gates taken on prose." Four
   planted defects (severity_comovement.gamma zeroed · the pre-r30 stale "not modeled"
   note restored · one pattern's attribution sum broken · induced_share_pct=150) must
   each be CAUGHT by its gate while the clean projection passes — executed on every
   trust-board cut (DATA/trust_board.json → gate_falsification). A gate that cannot
   fail is a narrative device; these four demonstrably can. (c) The Board ch1 lede's
   resolution count now DERIVES from the rendered resolutions (it said "four" while
   ch2 said five — the last hardcoded count on the surface). (d) REFUTATIONS RECORDED
   (none silent): GROK round-32 re-reported severity co-movement absent and dependency
   nodes constant-rate — both live since E5, named as data since r30
   (severity_comovement γ=0.10/cap 1.3 · dependency_model.load_dependence δ=0.05/cap
   1.25), gated by C34 — and re-asked for the why-moved line, the dependency Board ask,
   and docket single-sourcing, all shipped and content-asserted in r30 (items 27–28).
   ATTACK VECTORS: (a) find an unmarked stale dollar B6.4 misses; (b) plant a defect
   C34/C35 do NOT catch and name it; (c) diff classic across git history and check the
   epoch chain explains every change.
31. **r33 · JOURNEY SPINE STAGE 1a — the journey becomes the atomic unit (data layer).**
   The operator put their three real 2LoD reference artifacts next to this portfolio and
   named the gap: those land because they open with a BUSINESS OBJECT (a named Critical
   User Journey), anchor on ONE DATED EVENT, and carry the signal → risk → owner →
   control chain with the caveat in the same cell. The port is now under a LOCKED
   in-repo contract (`source/reviews/journey_spine_port_spec.md` — stages, acceptance
   gates, a parking-lot rule so review rounds can no longer consume the roadmap, and
   an absolute rename discipline: structure from the operator's production practice,
   all names/values/dates seeded). Stage 1a ships: **J-SIM-001 · Instant Transfer**
   (`data/journey_catalog.json`) — five stages (initiate → risk-check → ledger → rails →
   settle), ten seeded services threading the EXISTING objects (RP patterns,
   dependency nodes, controls, team owners) onto one money path; **SIM-0531**, the
   dated seeded incident (event-bus consumer-lag storm, four narrative steps with
   do-not-overclaim lines, every peak DERIVED from the deterministic generator —
   never typed); a derived journey SLO; and `data/signal_catalog.json` (GENERATED —
   signal → stage → service → owner → query intent, each with the chip grammar
   `SEEDED · 2160pts · 1h · gen:journey_signal_gen@seed42`). Gates **C36.1–5** hold it:
   spine ships, every reference resolves, peaks RECOMPUTE, the four-hop chain is
   complete per service with the external hop's non-claim, catalog reconciles.
   Stage 1b (the journey surface) is next per the spec. ATTACK VECTORS: (a) re-run
   the generator and diff any quoted peak; (b) find a chain hop missing its caveat;
   (c) find a real-world name that crossed — the rename discipline is gated by the
   bundle assertion.
32. **r34–r36 · THE JOURNEY-SPINE PORT COMPLETES (stages 2–4) — grounding devices from
   the operator's production practice, inside the verified world.** (a) **Stage 2 — the
   chip grammar**: every hv scenario hero and read row declares what its series IS
   (SEEDED · events · window · fields · generator, all DERIVED from the stream);
   `data/stream_catalog.json` GENERATED and reconciled (hv gates C9.1–3). (b) **Stage 3 —
   the operating-model delta**: evidence lifecycle derived from test methods (28
   automated · 16 bespoke · 14 no-evidence-yet · 26 flagged hard-to-re-perform — C37.1
   keeps the honesty flag NON-ZERO forever), rating-change workflow states derived from
   register fields (confirmed / candidate rerating / pending Engineering confirmation,
   all populated, C37.2), the A8 hash-chained machinery NAMED as the re-performance
   mechanism (C37.3). (c) **Stage 4 — the catalog shape + the proven passthrough**:
   patterns become parents of the register's (pattern × domain) child risks with
   per-child EVIDENCED status derived from fired telemetry (C38.1), and
   `data/journey_aggregator.json` ships the minimal journey contract whose
   "verbatim · unmodified" claim is RECOMPUTED four ways (generator hash == file seal ==
   file recompute == consumed hash; C38.2 + bundle gate B12.4) — the reference practice
   asserts the passthrough, this artifact proves it. HONESTY TRAIL: defect class 19
   joined the ledger mid-port — a load-time ReferenceError that passed node --check,
   the interaction matrix, AND static greps; only live per-panel content assertion saw
   the dead panel (the instrument is now named on the ledger). ATTACK VECTORS:
   (a) recompute the aggregator hash from the shipped payload; (b) diff the rollup
   against the register; (c) re-derive any rating state from the treatment fields the
   derivation note declares; (d) find a series panel WITHOUT a chip.
33. **r37–r43 · THE JOURNEY LEARNS TO MOVE, THEN THE PORTFOLIO STOPS SPRAWLING.**
   (a) **Stage 5 — visual grammar (r37–r41)**: `rac/journey.html` became the animated
   flow-graph the reference genre demands — canvas-drawn service nodes with pulsing
   glows, particle trails on the money path, a play/scrub incident player with derived
   phases (build/peak/drain from half-peak crossings), the SIM-0531 chain and incident
   COMBINED into one live graph, per-audience "so what" tiles. Honesty catches en
   route: a strided downsample ERASED the incident spike from the trend chart (the
   operator caught it from a screenshot; per-bucket max-pooling fixed it, and the
   caption had been quietly betraying it all along); rAF starvation in non-compositing
   panes forced a time-based scheduler. (b) **r42 — one map on every page**: the
   operator was lost in the link graph ("without it I am completely lost"), so ONE
   injected nav drawer (idempotent markers, runtime-resolved hrefs in this bundle so
   shipped bytes stay audit-identical — gate B13) landed on every destination.
   (c) **r43 — 13 pages fold to FIVE doors** ("what a mess. No wonder I'm lost"):
   the tour folded INTO the landing (one front door), each spoke's read folded into
   its workbench — rac's as a real closing chapter (`#node=story`: the read's flow
   picture + narrated walker, now an ia node on every role path; its number/docket
   screens were already workbench panels), atg/hv's by recognition that their reads
   duplicated the lineage hero and the observatory outright. Board + validation are
   demoted to PRINT ANNEXES of rac. Reads/tour are redirect stubs (old links live);
   pre-fold pages frozen under `archive/` next to the classics; NOTHING deleted.
   ATTACK: open `rac/index.html#role=basic&node=story` and press the walker — every
   step must open its evidence node; then try to find a destination that is not one
   of the five doors.
34. **r44 · THE REVIEWERS DISAGREE, THE DATA DECIDES.** Three simultaneous external
   reviews (two GROK, one Claude) were triaged against the parking-lot rule, with
   every factual claim CHECKED before disposition. REFUTED BY DATA: GROK's central
   claim that journey services carry "0 risk IDs" — all ten services in
   `journey_catalog.json` carry risk-pattern ids, signals, a named team owner,
   dependency nodes, and a per-service non-claim (GROK read the deliberately
   minimal aggregator, not the catalog). CONFIRMED AND ABSORBED: (a) the Board
   brief opened on the number, not the asks — the resolutions now open and the
   stress number is their evidence chapter; (b) the workbench header ran TWO
   identity systems before any number rendered — the role lens keeps the spine,
   the named signing personas retreat to the verb bar (the A8 signing context),
   the chain chip to the hash-chain section; (c) no surface stated the product
   category in plain words — the landing now opens with one sentence ("risk-as-
   code: technology-risk oversight run as software…"); (d) author language leaked
   into pixels ("Risk-OS", "you are the amber line", "folded in", build-version
   chrome in headers) — swept to footers/comments as a class; (e) the journey's
   non-claim ("no findings, no verdicts") promoted from chip to the page ribbon.
   PARKED, NOT ABSORBED: the front-door restructure — GROK #1 wants two doors,
   GROK #2 wants one, Claude says the current entry is the strongest in 34
   rounds; three AI reviewers producing three incompatible front doors is
   reviewer saturation, and the operator-locked five-door IA (r43) stands until
   THE COLD READ (an unbriefed human) decides. Back-pressure promotion stays
   REFUTED (spec §6).
35. **r45–r49 · THE SHOP WINDOW, THE GRAPH GRAMMAR, AND THE r44 PRINCIPLE
   FINISHES ITS SWEEP.** (a) **r45 — packaging day**: triage of the second
   review wave found the REPO README (the product page, not this brief)
   understating the work with stale trust claims (old audit counts, no
   category line, no journey); rewritten for the hiring reader — category
   sentence, 60-second journey GIF, the adversarial method AS method, and a
   verifiable-only author section (a reviewer-invented "22 years, CISO seats"
   biography had no basis in records and was NOT used). GROK's third pass
   conceded board order, flagship door and posture ribbon; its remaining asks
   re-argue the parked door war and stay parked. (b) **r46–r48 — the journey
   scene becomes a GRAPH, then the grammar sweeps every canvas**: stage lanes,
   mid-edge arrowheads with source→target gradients, the always-visible retry
   loop and backlog orbit ring, the warm family palette (r46); the LAYOUT
   itself becomes the story — entry descent, decision fan, bottleneck
   convergence drawn larger, the ledger⇄bus cycle lens, the breathing blowup
   hub with shock rings, the one-to-many explosion at four heights (r47);
   then direction is drawn on EVERY live graph — hv observatory mid-edge
   arrowheads where the unobservable ghost leg deliberately carries none (no
   signal, no claimed direction), atg lineage chevrons riding all 25 flows at
   their true bezier midpoints, RE-08 loops included (r48). Process teeth
   from r46b/c: a nav re-injection must restamp ALL pages, and commit chains
   now assert the ACTUAL pass counts — never just that a summary line
   printed. (c) **r49 — the r44 header principle propagates to the spokes it
   missed** (r48 flagged the atg/hv persona strips as "the un-propagated r44
   defect" and parked it rather than smuggle it in): the shared chrome
   (`source/hub/presentation.py`) now renders NO identity — one navigation
   question at the top (the role spine); atg's named signing personas +
   acting-as ribbon retreat INTO the DECIDE panel as the A8 signing context
   directly above the queue they sign, and its chain chip into the ATTEST
   chain-integrity panel; hv loses persona chips ENTIRELY — the observatory
   signs nothing, so the chips were a second identity system duplicating the
   spine's "viewing as" selector whose lens switch changed nothing visible (a
   dead control, the exact class a human cold-read once caught), and the
   chain chip retreats to a new attestation panel that says plainly the
   seeded attestations are illustrative while the chain math over them is
   real; version/period chrome left both banners (footers keep it). ATTACK:
   on `atg/index.html` open `#role=basic&node=verbs` — the signing strip must
   be visible THERE and nowhere above; switch identity and watch the
   acting-as ribbon change; walk to `#node=attest` — the chain chip must sit
   WITH the chain it verifies and go green after the live walk. On
   `hv/index.html` try to find ANY persona control outside the spine's
   "viewing as" — there must be none — then find the chain chip live-verified
   in the attestation panel. Headers on both spokes must answer ONE question
   (where am I, where next) and nothing else.
36. **r51 · THE CLOSING SCREEN IS A DECISION — the strategy decision surface.** The wave-3
   review triage confirmed one defect (typed counts in this brief — now DERIVED
   from the trust board with a build gate that fails on any unexecuted N/N
   token, plant-tested) and landed one approved build: rac closes on a board
   strategy decision surface (a priced brief with owners — it informs the
   choice; it does not re-run the engine on click, and the copy says so).
   Two named, priced postures — HARDEN THE CONTROLS (the
   eff_up lever: benefit recomputes as baseline minus lever output; downside is
   the eff_down drift the register's past-due repeat already evidences) and
   ISOLATE THE SHARED DEPENDENCIES (per-node suppression ceilings, top-4
   program scope; the whole-layer number is stated as a CEILING a program
   approaches, never a promise) — plus the explicit third path: HOLD AT
   CURRENT APPETITE, which is a signature, not a drift (red patterns at
   zero-tolerance/very-low stated appetite are named; the acceptances already
   on file ride with expiry; the joint-bad-year lever prices the year a signed
   hold gets tested). The politics ship as data, not prose: accountable execs
   with red-finding counts (including the acting/unfilled-role gap), the
   past-due repeat as a delivery-risk flag, the 2LoD re-testing issue as the
   credit gate on bankability, competing commitments verbatim from the
   register, committee decision routes, and the 8-K Item 1.05
   determination-reserved-to-Legal disclosure line. Program cost/staffing is
   NOT modeled and says so. Gate C39 (6 checks) asserts every dollar
   recomputes from the leaf it cites, owners resolve into the register, the
   spine closes on the choice on every role path, and the board brief links
   the surface without minting a sixth resolution; the falsification harness
   grew two plants (inflated benefit, invented exec — both CAUGHT, 7/7).
   ATTACK: open `rac/index.html#role=leadership&node=strategy` — recompute
   any dollar on the screen from `projections/rac.projection.json`
   (sensitivity.levers / dependency_layer.nodes); try to find an owner,
   flag, or committee that does not exist in the register; then open the
   board brief and confirm the decision-surface pointer did not become a sixth ask.
37. **r55–r56 · THE OPERATOR'S COLD READ, THEN SEVERITY LEARNS CONSEQUENCE.**
   (a) **r55 — the composition lesson**: the operator's own cold read found what
   37 AI rounds could not — locally-justified parts assembled into an inhuman
   whole (metaphors in pixels, caption-grade mono for body reading matter, deep
   links that pull nobody, capability-flexing panels). Process changed: static
   mock → 60-second operator verdict → build. The landing shipped under the new
   grammar: one number as the face, the seeded incident as a red alert strip
   with one button, gauges, four trust chips — every numeral hydrated from the
   sealed projections. (b) **r56 — atg severity moves from category to
   CONSEQUENCE** (operator: all five criticals were RE-03/PII-shaped while
   Agent Scope Exceeded sat at high — "a privacy scanner in a risk-platform
   costume"): severity now DERIVES per finding from its own traces
   (unauthorized-ACTION capability tops the scale; notification-class data
   events sit at high wearing the Art. 33 clock as an ASSESSMENT; the class
   value is a floor rendered only in the precedent register), each rating
   carries a machine-gated basis, and the seeded estate gained the finance
   shapes — a payments-tool grab, customer comms sent past the human gate, a
   ledger write with broken lineage (RE-06 first activation, sea_17a4 with
   rac's exact citation — the cross-substrate loop closes). Six new gates
   (C22.1–.6) hold the model to its contract; a planted deriver defect was
   CAUGHT by two of them. Conservation EPOCH: classic archived and re-frozen
   at the r56 build. En route the export seal caught inject_nav accreting one
   newline per cycle — fixed at source. ATTACK: open `atg/index.html`, drill
   any finding — the severity must carry a "why this severity" basis whose
   identifiers exist in that finding's own traces; every CRITICAL on the
   register must be an unauthorized-action finding; each PII-egress RE-03 at
   high must wear the clock chip with the reserved-determination line.
24. **Round 24 — the Board surface reaches Board altitude.** (a) `rac/board.html`'s three
   decisions became four RESOLUTIONS in Board verbs — ENDORSE the methodology / APPROVE the
   productionization roadmap / REQUIRE a 2LoD challenge on control effectiveness (the top
   lever, hydrated) / NOTE the past-due repeat + the A8 named-human gap — with the residual
   reds demoted to evidence rows carrying triggered regimes, stall reasons, and the political
   cost of escalating. ATTACK: verify every number inside a resolution against the projection
   (levers, `ia.derived`, the internal-audit register). (b) The capital-language class is
   dead: "plan capital on this" was rewritten at BOTH sites (board hero + the workbench
   exposure headline) to "a stress number under the stated judgments, not a capital figure."
   (c) Leadership dualism resolved by declaration, not redirection: the workbench shows a
   leadership-only altitude bar naming board.html the Board surface (auto-redirect was
   DECLINED — roles re-sequence, never gate); the tour gained a persona router. (d) TWO new
   state-driven rendered-ness matrix rows (external finding: interaction-state-dependent
   rendering defeats static checks): the applicability filter's default/filtered/restored
   cycle and every perimeter profile rendering ITS in-perimeter dollars. (e) The conservation
   tile now speaks B10's own additive count ("classic ⊆ index · +N leaves added, none lost")
   and validation §7's steps each carry the sensitivity lever that already prices their
   impact plus a named acceptance gate.

---

## 1. What this is

A hub-and-spoke monorepo of three fintech "risk-as-code" demonstrators sharing one platform:

- **rac — risk-as-code-agent**: a quantified risk register. Per-pattern **inherent → controls →
  residual** dollar exposure, which regulation each finding triggers, and the treatment decision.
- **atg — agent-trace-gov**: governance over AI-agent execution traces. Findings, a data-flow
  **lineage** graph, **human-in-the-loop gates**, and a hash-chained attestation log.
- **hv — hypervelocity-risk-sim**: an incident simulator. Three scenarios, each an animated
  **Incident Flow Observatory** — the incident playing through a component pipeline over a
  scrubbable timeline, with a manual-vs-instrumented response comparison folded in.

**Design invariants — the claims to test:**
- **Render-from-data**: every value shown is hydrated client-side from ONE embedded JSON blob
  (`<script id="projection-source">`). No number is hand-typed into the render code.
- **Reproducibility + seal**: the projection is byte-reproducible from a fixed seed; a SHA-256
  seal is recomputed in-browser (footer "verify ↪").
- **Provenance**: values carry a tier (real-query / synthesized / published-standard /
  illustrative / derived / absent).
- **Honesty**: data is simulated and disclosed as such; attestations are AI-generated, not human
  sign-offs; the *materiality determination* is reserved to Legal/Compliance.

---

## 2. What I most want scrutinised

1. **rac exposure (§0.1):** is the seeded-MC aggregation defensible? Are the recalibrated
   frequencies and the control-effectiveness haircut reasonable for a ~$2–4B-revenue US
   consumer/crypto fintech? Does $98.1M stress-P95 residual pass an exec smell-test?
2. **rac IMPACT swimlane** (patterns × Inherent → Controls → Residual → Regulation-triggered →
   Decision): does every cell trace to the projection?
3. **hv Incident Flow Observatory** — press play / scrub the timeline. Does the ECG on each edge
   genuinely ride the seeded `d.events` series? Is the manual-vs-instrumented gap honest? Does the
   blind-spot ghost node (unobservable leg) read as a governance statement, not decoration?
4. **atg PROPAGATE** lineage sankey with human-in-the-loop nodes + the derived headline
   "N of M external flows had no human gate" (and its workflow-level caveat).
5. **The READ, folded home (r43).** The story-first read pages no longer ship as separate
   files — rac's read is the workbench's CLOSING CHAPTER (`rac/index.html#role=basic&node=story`:
   the cascade flow-picture with a narrated six-step walker whose every step opens its evidence
   node), and atg/hv's reads were recognized as duplicates of the lineage hero and the
   observatory. Press on both axes: (a) *zero-drift* — every walker caption and canvas label
   must trace to the embedded projection; (b) *does the closing chapter LAND* — after walking
   the spine, does the one-picture recap earn its place, and do its links actually navigate?
6. **The role spine + walkers (`index.html#role=…&node=…`) — also new.** Roles must re-SEQUENCE,
   never re-value: switch all four roles and diff the numbers (the conservation reports +
   audit gates claim this is impossible — try to break it). Walk every node with the step
   walker: does each click visibly change the content above the fold? Do deep links land on
   the right panel on first load? Does `#canonical` genuinely show everything?
7. **The landing + `tour.html` — the portfolio finally speaks for itself; try to make it lie.**
   (a) The landing's three door numbers and the tour's six organ chips, trust-board tiles,
   lever span, and gap bars all claim to be FETCHED, never typed — falsify that: diff every
   displayed value against the shipped projections and `source/qa/trust_board.json`. (b) The
   trust board's counts claim to be EXECUTED — pressure the circularity: the counter is a
   script; can its numbers diverge from what the shipped audits actually produce? Re-derive
   at least one (run `verify_bundle.py`, compare its 26/26 to the tile). (c) The scope
   declaration (out-by-choice: market · trading · counterparty · liquidity · predictive
   markets) — is it honest, complete, and correctly framed as a decision? (d) The
   plain-English sweep — flag ANY remaining insider phrase a cold reader can't parse.
   (e) The two-minute claim itself: from landing → tour → one read, does a cold reader know
   what this is, why to believe it, and where it goes — in two minutes?
8. **hv's three failure shapes** — a backlog tank (HV-01), a blast cone (HV-02), a fork behind
   a closing gate (HV-03). Are they *instantly* distinguishable? And are they honest — every
   drawn magnitude (tank fill, cone reach/angle, branch width, gate swing) must be driven by a
   counted series at the scrub tick, no invented components (check `source/hv/hv_domain.js`,
   `sigTank/sigCone/sigFork`).

---

## 3. The questions to press

1. **Does every displayed number trace to the embedded projection?** Pick any figure and find it
   in `#projection-source`. A number invented in render JS is a finding.
2. **Are the visual simplifications honestly disclosed?** Swimlane cells are per-phase aggregates;
   the kafka deficit chart smooths rates; response-gap minutes are operator-calibrated
   illustration, not measured telemetry. Is each caption sufficient?
3. **Are the derived claims sound?** — atg gate derivation; rac "Regulation triggered" mapping
   (from `materiality.triggered_patterns`); hv severity thresholds + the manual-vs-instrumented gap.
4. **Does the honesty framing hold everywhere?** Is "simulated/seeded, not live" present wherever
   motion could be misread as live? Is the materiality-reserved boundary respected?
5. **Reproducibility/seal**: does "verify ↪" pass? Is the seal genuinely over the payload?
6. **Does every interaction respond, visibly, above the fold?** Serve the bundle
   (`cd dashboards && python3 -m http.server 8300`), then click every affordance — read-page
   chapters and continue buttons, spine pills, role drop-down, step walkers, hv scenario pills,
   play/scrub/tour, act tabs on classic — and assert the CONTENT changed where you were looking.
   Report anything that is cosmetic, dead, or scrolls to the wrong place. This is the defect
   class prior AI rounds systematically missed; treat it as first-class, not polish.

---

## 4. How to verify quickly

- **One command first: `python3 verify_bundle.py`** (bundle root, stdlib-only) — re-executes
  every claim this bundle can prove about itself: OSCAL conformance, projection
  reconciliations, dashboard↔projection agreement, the landing snapshot, the QA report's
  arithmetic, the README headline vs the data. Repo-side-only checks are disclosed in its
  output, not hidden.
- Each dashboard HTML is self-contained: open it, search source for `id="projection-source"` —
  that JSON is the single source of truth for every displayed value.
- Each spoke ships a **substance-gated audit** (`audits/audit_*.py`) asserting *behaviour*
  (render-from-data, provenance tiers, chain integrity, cross-surface reconciliation), not token
  presence. Current: **rac 120/120 · atg 69/69 · hv 33/33**, zero FAIL. (These run against
  the source tree — their `outputs/`-style paths reference the repo, not this flattened bundle; they
  are included as *evidence of the gates*, not to be executed in place.)
- Footer **"verify ↪"** recomputes SHA-256 over the projection in-browser.
- **Reproduce the numbers yourself — the generator inputs are included** (`source/data/`).
  Don't take "reproducible from seed" on faith; re-run it:
  - **rac (the headline $ distribution):** `cd source/rac && python3 -c "import exposure;
    r=exposure.aggregate_loss_mc(seed=42)['portfolio']['residual']; print('residual  P50 %.1fM  P95
    %.1fM  P99 %.1fM' % (r['p50']/1e6, r['p95']/1e6, r['p99']/1e6))"` — reads
    `source/data/risk_patterns.json` in place, runs the 20,000-trial Poisson×lognormal MC **with
    cascade propagation**, and prints `residual  P50 $30.8M  P95 $98.1M  P99
    $156.2M` — **identical** to `projections/rac.projection.json`
    (`exposure.portfolio_total.{p50,p95,p99}_usd`). Change the seed and the numbers move; re-use
    42 and it's byte-identical — a **genuine Monte-Carlo**, sampled, not scripted. Pass
    `cascade=False` and you reproduce the **independence counterfactual** the projection reports in
    `exposure.portfolio_total.correlation_model` (residual P95 $68.4M) — so the
    correlated-tail delta is itself re-runnable, not asserted.
  - **atg (governance findings):** inputs now ship — `source/data/action_schema.json`, the
    hash-chained `source/data/attestation_log.jsonl`, and the seeded trace generator
    `source/atg/agent_simulator.py`. `atg/projection.py` anchors its data dir at
    `parent.parent/data` == `source/data/`, so the schema + log resolve in place; the governance
    logic (`governance_graph.py`) is pure trace → findings.
  - **hub KRI taxonomy:** `source/packages/kri-taxonomy/{kri-catalog,crosswalk}.yaml` — hv's
    *full* projection reads these (its `_REPO_ROOT` anchor expects the repo nesting
    `apps/<spoke>/utils/`; recreate that nesting or point `_KRI_DIR` at the shipped folder).
  - **QA test cases to re-validate:** `source/qa/TEST_REPORT.md` (+ `test_report.json`) — 40
    browser-driven cases across three lenses (user interactions, functional accuracy vs the
    embedded projection, auditor compliance), each with steps/expected/actual. A human cold-read
    found dead navigation that five prior review rounds missed (they attacked the numbers, never
    clicked the tabs) — those defects are fixed and re-verified; please try to falsify the
    recorded results, especially the interaction rows (serve the dashboards, click, diff content).
  - **hv (the incident series):** `cd source/hv && python3 -c "from event_generator import
    run_scenario; ev,summary=run_scenario('kafka_lag_storm', seed=42); print(len(ev), summary)"` —
    regenerates the event stream the observatory's ECG rides. Note the honest contrast: hv is a
    **deterministic seeded *replay* of one operator-calibrated incident shape** (+jitter), NOT a
    sampled distribution — which is why `risk_events.json` now splits `shape_topology_provenance`
    (source_derived) from `shape_parameter_provenance` (operator_calibrated). It presents no
    percentiles, so it never dresses a single realization as sampling.

---

## 5. Known limitations — already disclosed (tell me if a disclosure is insufficient or a claim overreaches)

- All data is **synthetic / seeded**; nothing is from a production system.
- rac dollar figures are a **seeded-MC illustration** calibrated to a fintech archetype, not a
  fitted loss history.
- hv response-time gaps are **operator-calibrated illustration**, not measured.
- Attestations / "reviews" are **illustrative and AI-generated**, not human sign-offs.
- Employer-specific names are de-identified; scenarios use generic service names.

---

## 5b. Open design questions — I genuinely want your call

1. **hv audience lensing.** The shell already has 1LoD / 2LoD / 3LoD persona chips (engineer /
   exec / auditor). The observatory does *not* currently re-narrate per persona. Worth it — should
   the graph emphasise different panels per audience — or does the shell lens already suffice and
   internal audience tabs would just duplicate?
2. **rac exposure credibility.** Is a seeded Monte-Carlo the right instrument for a *portfolio*
   roll-up of 13 patterns, or does it over-promise rigor on synthetic frequencies? What would a
   real 2LoD challenge?
3. **Cross-spoke coherence.** Both prior rounds said the thesis was author knowledge, so
   `dashboards/landing.html` now leads with it (substrate diagram + crosswalk strip — §0.11).
   Does it LAND for a fresh reader, or is it still telling rather than showing? What one change
   would make it undeniable?
4. **What's the biggest *gap*** — the one thing a skeptical fintech CRO or a bank examiner would
   say is missing before they'd trust any of this?

---

## 6. Folder map

```
PORTFOLIO_REVIEW/
  README.md                     ← this brief
  PRODUCT_README.md             ← the repo's hiring-reader README, shipped VERBATIM so the
                                  hiring surface is verifiable, not asserted (r51 / Claude 0.3) —
                                  hold its claims to the same standard as everything else
  dashboards/  landing.html                   ← start here (doors + the guided tour, folded in r43)
       rac/ atg/ hv/                          ← per app: index.html (the workbench, role-spine;
                                                rac ends on the folded read chapter) · rac also:
                                                journey.html · board.html · validation.html ·
                                                archive/classic.html (frozen pre-grammar page)
  projections/ rac.projection.json ...        ← single source of truth for every number
  source/      rac/ atg/ hv/ hub/             ← code that PRODUCES the output
       data/   risk_patterns.json risk_events.json  ← generator INPUTS (reproduce §4)
       qa/     conservation_report*.json      ← classic ↔ new fingerprint verdicts
  audits/      audit_v2_0a.py audit_atg.py audit_hv.py   ← the substance gate
```

**Accuracy chain to verify:** `simulator/generator (seeded)` → `projection.py (builds JSON +
provenance)` → `projections/*.json (seal-covered payload)` → `*_html_report.py / *_domain.js
(render-from-data)` → `dashboards/*.html (pixels)`. A value is honest only if it survives that
whole chain unmodified.
