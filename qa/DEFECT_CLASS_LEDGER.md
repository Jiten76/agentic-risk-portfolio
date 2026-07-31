# Defect-class ledger — every class that ever bit, and what guards it now

*Round-18. The honest answer to "what else have you missed?" is not a list of
unknown bugs — nobody has that — it is this table: every DEFECT CLASS from
eighteen review rounds, who caught its first instance, and whether a STANDING
automated gate now guards the class (vs. a one-time manual check). A class
without a gate is where the next miss lives; this ledger exists so that set
shrinks visibly and on purpose.*

| # | class | first caught by | instances | standing guard NOW |
|---|---|---|---|---|
| 1 | fabricated / baked render values | external (round 2) | hardcoded impact faces; $3.13B tail-sum | C19-class gates + B3 embedded==shipped + render-from-data audits |
| 2 | non-additive statistics | external | Σ of percentiles (portfolio, regulation) | one-MC subset-sum machinery + C21 dominance + naive-Σ anti-example shipped |
| 3 | seed / clock nondeterminism | verify_bundle (B-run) | RISK_RNG_SEED never set (25/26/27 registers); wall-clock date drift | C25 two-run byte-equality + pinned `as_of` + B11 cross-build baseline |
| 4 | wrong-input builds | interaction matrix (ours) | atg read built from a stray glob-last projection | generators pinned to canonical paths + runner asserts rendered period/headline per read |
| 5 | cross-VIEW numeric drift | external spec-check | classic/index/read could diverge silently | conservation fingerprints + B10 leaf equality (contemporary) / sub-multiset (frozen classic) |
| 6 | cross-BUILD numeric drift | external (proved unchecked-but-lucky) | — (none found; gate added preemptively) | B11 vs qa/numeric_baseline.json, re-cut same-commit or fail |
| 7 | dead / cosmetic interactions | human cold-read (round 7) | cosmetic rail; dead scroll; dead read hash routing; missing Escape | interaction matrix + shipped runner (geometric + content-distinctness + zero-JS-error rows), re-run on rebuild |
| 8 | viewport / responsive regressions | external (round 14) | 564px doc at 390 (translation strip); 743px validation dossier (caught by OUR sweep, round 18) | runner overflow row at any viewport + recorded 390 sweep across all surfaces |
| 9 | silent JS handler errors | runner (round 18, first run of the new gate) | unguarded `e.target.matches` killed the rac keyboard layer on edge targets | runner zero-JS-errors row during driven interactions; guard idiom swept class-wide |
| 10 | vocabulary / IP hygiene | user | "armed" metaphor; "breach" misuse; employer name; RAG-token minting in chrome | bundle assertions + protected-token fingerprints (caught the "red cone" caption live) |
| 11 | link integrity | ad-hoc crawl (round 14) | landing→read links would have shipped broken | STANDING bundle-build assertion (round 18) — any broken relative href fails the build |
| 12 | gate vacuity (gates weaker than spec) | external (round 15/16) | B9 checked report-internal consistency, not the invariant | "gates gate the gates": B10/B11 re-derive invariants in-bundle; spec states actual guarantees |
| 13 | ungated new surfaces | external NOTE (round 15) | read.html shipped outside conservation scope | every surface hash-pinned in a conservation report; validation.html was BORN gated |
| 14 | prose / insight drift | external | reworded conclusions pass numeric gates | C26d text-hash changelists w/ mandatory acknowledgment — ACCEPTED, DISCLOSED limit (no semantic freeze) |
| 15 | audience fit / persuasion | personas + human | operator cockpit on the CRO arc; five-dollar-figure opening | NOT automatable — persona reads (warm), fresh-session reads (cold), the human FE reviewer (decisive) |
| 16 | a11y depth (aria on dynamic spine, screen-reader flow) | external mention | boot-killing regression during the fix itself (caught by the runner) | GATED (round-19) — aria-current on the active pill, aria-modal map with focus round-trip, live-region step header, synced accordion semantics, labeled scrub/tour; runner rows enforce all of it |
| 17 | engine double-counting (new model layer re-prices what base calibration already contains) | self (E1) | first dependency-layer build injected degraded-mode events already embedded in all-cause base rates — P50 would have jumped $38M→$83M; REJECTED pre-ship | GATED — the dep_attribution judgment (loss-only injection) is on the challenged-judgment log; C30.3/C30.4 recompute the layer and its counterfactual; dep_layer_off / dep_freq_up levers bound it both ways |
| 18 | mis-centered mechanism (a dynamics term active in the TYPICAL year instead of the tail) | self (E4) | first β build centered load-dependence on zero — the cap saturated in median years (P50 hit $88M), a blanket cascade doubling, not a supercritical transition; REJECTED pre-ship | GATED — β centers on E[concurrent] (typical year ≈ 1.0×); C31.3 asserts the β=0 counterfactual ≤ headline and the beta_zero lever ≡ counterfactual by construction |

## How to read this honestly

- Classes 1–13 and 16 have standing machine gates. A regression there fails a build,
  an audit, or the runner — it cannot ship silently.
- Class 14 is a disclosed trade, not a hole: prose changes are counted and must
  be acknowledged, never frozen.
- Class 15 is the honest frontier: it is caught by people (personas, fresh
  sessions, the human reviewer), not machines — which is why the review loop
  keeps all three instruments. (Class 16 graduated to machine-gated in
  round-19 — and the fix itself introduced a boot-killing bug the runner
  caught on its next sweep, which is the loop working.)
- Track record of the instruments THIS round: the new zero-JS-error row caught
  the unguarded handler on its first execution; the new overflow sweep caught
  the validation dossier's mobile overflow within minutes of the page existing.
  Both fixed and re-verified before this ledger was written.

*Regenerate the evidence: `qa/interaction_matrix_runner.js` per page,
`verify_bundle.py` in the bundle, the three `audits/audit_*.py` in the repo.*
| 19 | load-time runtime throw (wrong-scope variable, ReferenceError) kills every renderer after it in the chain — passes node --check (valid syntax), passes the matrix (error fires before the listener attaches), passes static greps | caught r35 pre-freeze (P vs PROJECTION in renderOperatingModel) | browser per-panel CONTENT assertion — the only instrument that sees it |
