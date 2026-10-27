# agent-trace-gov v2 port — progress

> Live state of the port. Spec is LOCKED (`v2_dashboard_port_spec.md` §14+§15).
> Branches are local-only (no push). Reads in 60s.

## DONE + verified — the rendered ATG dashboard (this autonomous session)

### Stage 0 — `portfolio-core` shared presentation (extracted, not copy-pasted)
- `base.css` — the `:root` warm-terminal token palette (the CSS extraction had
  left these behind → the shared path would have rendered unstyled; now fixed).
- `runtime.js` — the domain-agnostic render-from-data runtime: projection load,
  canonicalJson+sha256+verifyChain, verb modal (A8 named-human gate), lineage
  modal, act/lens/domain switching, **verifyArtefactSeal**, domain registration.
- `presentation.py` — `render_dashboard()` assembles chrome (header, act-tabs,
  rail, modals, footer seal) + CSS + runtime; the **seal is SHA-256 over the
  embedded projection**, recomputed in-browser (independently verifiable).
- `action_log.py` / `provenance.py` — `_canon_numbers` (float-domain closure so
  JS byte-matches the signer) + injectable `set_as_of` clock (reproducibility).

### Stage 3 — the ATG render surfaces (`utils/atg_html_report.py` + assets)
- 5-act IA (SIGNAL · PROPAGATE · IMPACT · DECIDE · ATTEST), render-from-data.
- **Lineage SVG hero** (§15.G): agents→systems→external columns, RE-03 external
  edges lit, RE-08 loops dashed, 86 raw edges deduped to 25 distinct.
- Records-exposed magnitude (DISTINCT flows, matching the graph), framework
  materiality, attestation log + chain detail, RE precedent register.
- 3 **illustrative** seeded attestations (`tools/seed_attestations.py`) → chain
  ships genesis→head-verifiable, not an empty green badge.

### Adversarial hardening — 3 skeptic agents broke it; every finding fixed
risk-officer + sre-engineer + audit-regulator. BLOCKERs + MAJORs, all fixed +
gated:
- **canonicalJson ≠ Python signer** (floats + 0x7f) → `_canon_numbers` closes the
  domain, `>= 0x7f` fixed. Chain verifies 3/3 live (the proof).
- **A8 gate ASCII-only** (rejected 李明/José/Иван, admitted "Payments Team") →
  Unicode + CJK + org-handle denylist. Verified live.
- **Seal unverifiable / non-reproducible** → projection-based + in-browser
  verifier + seeded determinism. "✓ projection verified" live.
- **PII magnitude 13 contradicted the graph's 4** → DISTINCT headline + raw
  traversals secondary; "Art. 33(1)(a) quantity" overclaim retracted.
- **GDPR Art. 33 armed on RE-01** (legal conclusion) → RE-03 only; Art. 5/32 +
  Art. 6(1)(a) added; EU AI Act high-risk predicate stated.
- Hero numbers now badged (counts_provenance); href `safeUrl`; node-type
  normalized (6 agents in AGENTS column); dead `consent_missing` wired;
  localStorage namespaced per project; boot-order registration handshake.

### Gates (all green)
- `tools/audit_atg.py`: **50 / 50** (was 31; +19 close the renderer + reproducibility
  + materiality + canonical gaps the agents exposed).
- Project-1 regression: **39 / 0** + browser-clean (chain 3/3) after every
  shared-core change.
- Browser-verified live: chain 3/3→4/4, A8 Unicode gate, seal ✓, distinct
  magnitude, hero provenance, agent column, 0 console errors.

## How to verify
```bash
cd /Users/jitendranjoshi/code/agent-trace-gov
.venv/bin/python3 tools/audit_atg.py                 # 50/50
.venv/bin/python3 -m utils.atg_html_report 16        # regenerate (seed=42, reproducible)
cd /Users/jitendranjoshi/code/risk-as-code-agent && python3 tools/audit_v2_0a.py   # 39/0
```

## Project-1 divergence — CLOSED via back-port (2026-06-30)
Claude's review meta-point: project-1 still ran its own INLINE runtime with the
pre-fix A8 gate (ASCII-only), canonical (`> 0x7f`), and `signed-by` overclaim — so
the two projects disagreed on whether the A8 gate + chain were correct. Back-ported
all three into `risk-as-code-agent/utils/v2_html_report.py`:
- canonicalJson `>= 0x7f` (float-clean seed chain still verifies 3/3 — 12.4 is
  non-integer so String() already matches Python; no seed change).
- actorIsNamedHuman Unicode + CJK + org-denylist (browser-verified: accepts
  D. Patel / José García / 李明 / Иван Петров / Müller Hans; rejects @platform-team /
  Payments Team / On Call / SRE Rotation / platform).
- seal `signed-by` → `generated-by` + keyless-checksum tooltip.
Both projects now behaviourally consistent. Audit 39/0; 0 console errors.
Residual (documented, low-risk): project-1 keeps `String()` for numbers vs the
shared `_num` guard — harmless (no integer-valued floats in seeds or int-only UI
entries); the guard is defense-in-depth that lands with the full migration.

## NEXT
- **Publish** (gated on user OK): IP-scrub → push → GitHub Pages live demo →
  README screenshot, for agent-trace-gov and risk-as-code-agent.
- Deferred (post-publish, deliberate): full migration of project-1 onto the shared
  `render_dashboard`/runtime — the pure single-source end-state; larger refactor of
  a working reviewed artefact, sequenced after publish, not under shipping pressure.
- Minor: PROPAGATE lineage-node click-to-lineage; dedicated mobile media-query for
  the SVG (degrades via horizontal scroll today).
- Then: hypervelocity-risk-sim port (separate spec); Yukti V3.0; EAP.
