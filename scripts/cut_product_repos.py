#!/usr/bin/env python3
"""cut_product_repos — release exports for the three product repos (r52).

Operator decision (2026-07-25): the portfolio splits its PRESENTATION, not its
platform. The monorepo stays the canonical engine; three product repos are cut
FROM it by this script — never hand-maintained — each with one room, one story:

  risk-as-code-agent      → the CRO / board / examiner room
  agent-trace-gov         → the AI-governance room
  hypervelocity-risk-sim  → the engineering room

Rules of the cut (the same discipline as the review bundle, applied to repos):
  - Exports preserve the monorepo-relative layout (apps/<slug>/ + packages/ +
    qa/) so every bootstrap path, audit path and build command works UNCHANGED —
    zero hand-edited divergence, byte-identical source.
  - The portfolio nav drawer is stripped from shipped pages (its absolute
    /apps/... map links would be dead in a standalone repo — the exact
    dead-navigation class the operator once caught by hand). The strip is
    marker-based and deterministic; the export's conservation report is then
    RESTAMPED against the export's own bytes, so its freshness gate stays true.
  - Every README number DERIVES from qa/trust_board.json and the sealed
    projections at cut time — counts and dollars are executed, never typed
    (the r50 count-gate discipline, applied to the product pages).
  - MANIFEST.sha256 records every shipped byte; verify_export.py (stdlib-only,
    shipped in each export) re-hashes it and re-verifies the artefact seals,
    link integrity and IP hygiene with ZERO monorepo access. A hand-edit in a
    product repo fails the manifest — B10's philosophy applied to repos.

Run from repo root:  python3 scripts/cut_product_repos.py
Output:              exports/<slug>/   (gitignored; push each as its own repo)
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"

MARK_A = "<!-- portfolio-nav -->"
MARK_B = "<!-- /portfolio-nav -->"

# Shared substrate shipped with EVERY export (small, and it IS the senior
# claim: one taxonomy, one seal-and-gate discipline, one falsification record).
SHARED = [
    "packages/ui-system",
    "packages/kri-taxonomy",
    "packages/a2a-cards",
    "qa/trust_board.json",
    "qa/DEFECT_CLASS_LEDGER.md",
]

# Sealed build outputs the audits read (outputs/ is gitignored in the monorepo;
# the export ships exactly the sealed pair per spoke so the audit runs in-place).
SEALED_OUTPUTS = {
    "risk-as-code-agent": ["outputs/v2_0a/2026-Q3_projection.json",
                           "outputs/v2_0a/2026-Q3_v2_0a_alpha2.html"],
    "agent-trace-gov": ["outputs/2026-06_atg_projection.json",
                        "outputs/2026-06_atg_dashboard.html"],
    "hypervelocity-risk-sim": [],
}

CONSERVATION = {
    "risk-as-code-agent": "qa/conservation_report.json",
    "agent-trace-gov": "qa/conservation_report_atg.json",
    "hypervelocity-risk-sim": "qa/conservation_report_hv.json",
}

# Cross-substrate evidence a spoke's own audit machine-checks (e.g. atg's
# C21.5-class gates verify each agent-substrate node's rac analog against
# rac's dependency catalog — the "one mechanism, two substrates" contract).
EXTRA_FILES = {
    "risk-as-code-agent": [],
    "agent-trace-gov": ["apps/risk-as-code-agent/data/dependency_catalog.json",
                        "qa/detection_eval.json"],
    "hypervelocity-risk-sim": [],
}

# README media, shipped per product from the monorepo assets/ dir — the product
# README embeds them, so the export must carry them (verify_export V3 checks links).
PRODUCT_ASSETS = {
    "risk-as-code-agent": ["journey_demo.gif", "board_asks.png"],
    "agent-trace-gov": ["atg_lineage.png"],
    "hypervelocity-risk-sim": ["observatory_demo.gif"],
}

# conservation input key → repo-relative file (per spoke), for the restamp
CONS_INPUTS = {
    "risk-as-code-agent": {
        "classic_sha256": "apps/risk-as-code-agent/docs/archive/classic.html",
        "new_sha256": "apps/risk-as-code-agent/docs/index.html",
        "read_sha256": "apps/risk-as-code-agent/docs/read.html",
        "validation_sha256": "apps/risk-as-code-agent/docs/validation.html",
        "board_sha256": "apps/risk-as-code-agent/docs/board.html",
        "journey_sha256": "apps/risk-as-code-agent/docs/journey.html",
    },
    "agent-trace-gov": {
        "classic_sha256": "apps/agent-trace-gov/docs/archive/classic.html",
        "new_sha256": "apps/agent-trace-gov/docs/index.html",
        "read_sha256": "apps/agent-trace-gov/docs/read.html",
    },
    "hypervelocity-risk-sim": {
        "classic_sha256": "apps/hypervelocity-risk-sim/docs/archive/classic.html",
        "new_sha256": "apps/hypervelocity-risk-sim/docs/index.html",
        "read_sha256": "apps/hypervelocity-risk-sim/docs/read.html",
    },
}

IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".venv", "node_modules", ".DS_Store",
    "outputs",          # gitignored builds — the sealed pair is added explicitly
    "README.md",        # the pre-monorepo app README; the product README is generated at root
    "STATUS.md",        # pre-monorepo work journal — its era claims ("39/0", "13
                        # patterns") contradict the current sealed state; stays in
                        # the monorepo as history, does not ship as current status
    "CONTRIBUTING.md",  # points at the old standalone repos AND invites hand-edits
                        # the export's manifest discipline exists to reject —
                        # contributions land in the platform repo (README says so)
    # r62 (channel curation, applied to product repos too): streamlit-era infra
    # and scaffolding stay local — the export is the docs-first product
    "Dockerfile", "docker-compose.yml", "ui", "agents", "reviews",
)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def strip_nav(export_root: Path) -> int:
    """Remove the portfolio nav block from every shipped page that carries it."""
    n = 0
    for pg in export_root.rglob("*.html"):
        txt = pg.read_text(encoding="utf-8", errors="ignore")
        if MARK_A in txt and MARK_B in txt:
            pre, post = txt.split(MARK_A)[0], txt.split(MARK_B)[-1]
            pg.write_text(pre + post.lstrip("\n"), encoding="utf-8")
            n += 1
    return n


def restamp_conservation(export_root: Path, slug: str) -> list[str]:
    """The export's conservation report must describe the EXPORT's bytes
    (nav-strip changes page hashes; the fingerprint invariants it records are
    content-level and unaffected — the nav block carries no numeric leaves)."""
    rep = export_root / CONSERVATION[slug]
    d = json.loads(rep.read_text())
    changed = []
    for key, rel in CONS_INPUTS[slug].items():
        f = export_root / rel
        if f.exists() and d["inputs"].get(key) != sha256(f):
            d["inputs"][key] = sha256(f)
            changed.append(key)
    if changed:
        d["export_note"] = ("input hashes restamped by cut_product_repos.py against this "
                            "export's bytes — the portfolio nav drawer (chrome, no numeric "
                            "leaves) is stripped from standalone repos; the fingerprint "
                            "invariants recorded above were established on identical content")
    rep.write_text(json.dumps(d, indent=1, ensure_ascii=True))
    return changed


# ── the stdlib-only verifier shipped inside every export ──
VERIFY_EXPORT = r'''#!/usr/bin/env python3
"""verify_export — re-verify this product repo with ZERO external access.

Stdlib only. Re-hashes every shipped byte against MANIFEST.sha256, recomputes
each dashboard's artefact seal from its own embedded projection, walks every
relative link, and sweeps the IP-hygiene rules. A hand-edit anywhere fails V1.

Run from the repo root:  python3 verify_export.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
results = []


def check(cid, ok, msg):
    results.append(ok)
    print(("  [PASS] " if ok else "  [FAIL] ") + cid + " · " + msg)


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    print("product-repo export verification (stdlib, self-contained)")
    print("=" * 60)

    # V1 · manifest integrity — every byte accounted for, nothing drifted
    manifest = {}
    for line in (ROOT / "MANIFEST.sha256").read_text().splitlines():
        h, _, rel = line.partition("  ")
        manifest[rel] = h
    bad, missing = [], []
    for rel, h in manifest.items():
        f = ROOT / rel
        if not f.exists():
            missing.append(rel)
        elif sha256(f) != h:
            bad.append(rel)
    # running the shipped audits compiles bytecode in place — a runtime
    # artifact of verification itself, not drift; everything else unlisted fails
    extra = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
             if p.is_file() and str(p.relative_to(ROOT)) not in manifest
             and p.name != "MANIFEST.sha256" and ".git" not in p.parts
             and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    check("V1 manifest — every shipped file hashes to its manifest entry, no extras, no gaps",
          not bad and not missing and not extra,
          ("drifted: " + ", ".join(bad[:3])) if bad else
          ("missing: " + ", ".join(missing[:3])) if missing else
          ("unmanifested: " + ", ".join(extra[:3])) if extra else
          f"{len(manifest)} files verified")

    # V2 · artefact seals — two generations, both re-verified:
    #   scheme A (shared chrome): #artefact-seal-value == SHA-256(embedded projection)
    #   scheme B (rac workbench): the printed body-hash re-derives by replacing
    #   its own value with the build sentinel and hashing the page
    sealed = 0
    seal_bad = []
    for pg in sorted(set(ROOT.rglob("docs/**/*.html")) | set(ROOT.rglob("docs/*.html"))):
        txt = pg.read_text(encoding="utf-8", errors="ignore")
        s = re.search(r'id="artefact-seal-value">([0-9a-f]{64})', txt)
        if s:
            m = re.search(r'<script[^>]*id="projection-source"[^>]*>(.*?)</script>', txt, re.S)
            if not m:
                continue
            sealed += 1
            if hashlib.sha256(m.group(1).strip().encode("utf-8")).hexdigest() != s.group(1):
                seal_bad.append(str(pg.relative_to(ROOT)))
            continue
        b = re.search(r'SHA-256 <code class="mono">([0-9a-f]{64})', txt)
        if b:
            sealed += 1
            recomputed = hashlib.sha256(
                txt.replace(b.group(1), "<<<HASH_INPUT>>>").encode("utf-8")).hexdigest()
            if recomputed != b.group(1):
                seal_bad.append(str(pg.relative_to(ROOT)))
    check("V2 artefact seals — every sealed dashboard re-verifies (projection-seal or body-hash scheme)",
          sealed > 0 and not seal_bad,
          ("BROKEN: " + ", ".join(seal_bad)) if seal_bad else f"{sealed} sealed page(s) recomputed")

    # V3 · link integrity — every relative reference on NAVIGABLE pages resolves.
    #   archive/ pages are frozen era-evidence (their links reflect the layout of
    #   their era, by policy never edited); outputs/ copies are sealed audit
    #   inputs, not site pages — both excluded, and said so here.
    dead = []
    for pg in ROOT.rglob("*.html"):
        parts = pg.relative_to(ROOT).parts
        if "archive" in parts or "outputs" in parts:
            continue
        txt = pg.read_text(encoding="utf-8", errors="ignore")
        for ref in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', txt):
            if ref.startswith(("http", "#", "mailto", "javascript", "data:")):
                continue
            if not (pg.parent / ref.split("#")[0].split("?")[0]).resolve().exists():
                dead.append(f"{pg.relative_to(ROOT)} -> {ref}")
    # r72 (external reviewer, prose wave 3): the README is the FIRST page every
    # visitor renders — its image embeds, links, and cited qa/ records live in
    # the seam between prose and bytes, previously outside every perimeter.
    for md in ROOT.rglob("*.md"):
        parts = md.relative_to(ROOT).parts
        if "archive" in parts or "outputs" in parts:
            continue
        txt = md.read_text(encoding="utf-8", errors="ignore")
        refs = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', txt)
        refs += re.findall(r'`(qa/[^`]+\.json)`', txt)
        for ref in refs:
            if ref.startswith(("http", "#", "mailto", "<")):
                continue
            if not (md.parent / ref.split("#")[0]).resolve().exists():
                dead.append(f"{md.relative_to(ROOT)} -> {ref}")
    check("V3 links — every relative reference on navigable pages AND markdown (incl. README image embeds + cited qa/ records) resolves",
          not dead, ("dead: " + "; ".join(dead[:4])) if dead else "all relative references resolve")

    # V4 · hygiene — no portfolio-nav residue; the projections parse with counts
    residue = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.html")
               if "<!-- portfolio-nav -->" in p.read_text(encoding="utf-8", errors="ignore")]
    check("V4 chrome — the portfolio nav drawer (monorepo-absolute links) is fully stripped",
          not residue, ", ".join(residue) or "no residue")

    parsed = 0
    parse_bad = []
    for pg in ROOT.rglob("docs/index.html"):
        txt = pg.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'<script[^>]*id="projection-source"[^>]*>(.*?)</script>', txt, re.S)
        if not m:
            continue
        try:
            proj = json.loads(m.group(1).strip().replace("<\\/", "</"))
            assert proj.get("meta", {}).get("counts")
            parsed += 1
        except Exception as e:
            parse_bad.append(f"{pg.relative_to(ROOT)}: {e}")
    check("V5 projections — every embedded projection parses and carries meta.counts",
          parsed > 0 and not parse_bad, "; ".join(parse_bad) or f"{parsed} projection(s) parsed")

    print("=" * 60)
    npass = sum(1 for r in results if r)
    print(f"Summary: {npass} PASS · {len(results) - npass} FAIL · {len(results)} total")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


# ── README templates — one room each. {placeholders} are DERIVED at cut time. ──

HONESTY_BLOCK = """\
## What is honest here

- All data is **synthetic and seeded** — nothing comes from any production system;
  rebuild with the same seed and you get the same bytes.
- Demonstrator "reviews" and attestations are **AI-generated and disclosed as such**,
  not human sign-offs. Named people are fictional.
- The **materiality determination is reserved to Legal/Compliance** — surfaces flag
  which regulations a finding *triggers*, never whether it is material.
- Where a figure is operator-calibrated illustration rather than measurement, the
  pixel says so next to the number, not in a footnote.
"""

SUBSTRATE_BLOCK = """\
---

*One of three artifacts cut from a shared, sealed risk-as-code substrate — one
taxonomy, one seal-and-gate discipline, one falsification harness
({falsification} planted defects caught on the last cut). The substrate's
verification record ships in this repo under `qa/trust_board.json` — it carries
all three products' executed counts because the harness is shared, not because
this repo contains three products. Re-verify this export any time with
`python3 verify_export.py` (from the repo root, after a FULL unzip — the
manifest covers every file, so a partial tree fails loudly and correctly).
This repo is a release cut, script-generated from the platform repo —
`MANIFEST.sha256` rejects hand-edits by design, so changes land upstream,
never here.*
"""

README_RAC = """\
# risk-as-code-agent — a technology-risk register that prices, argues, and signs

**Technology-risk oversight run as software, at board altitude.** Fourteen failure
patterns priced by a seeded, correlated Monte-Carlo into one challengeable number —
**${p95} residual P95** against ${inh_p95} inherent — with every judgment a
priced, re-runnable lever, and the page ending where a board actually lives:
**a strategy decision surface** (harden the controls: −${benefit} residual
reduction under stated judgments · isolate the shared dependencies: ${ceiling}
ceiling · or hold at appetite and sign for it — each posture priced, owned,
and traceable to the register).

## See it in 60 seconds

```bash
python3 -m http.server 8080
```

For the board/CRO read, start at
<http://localhost:8080/apps/risk-as-code-agent/docs/board.html> — the printable
board brief: five resolutions in board verbs, the number as their evidence, and
the decision surface one link below them. The full workbench (role-sequenced,
operator-dense by design) is
<http://localhost:8080/apps/risk-as-code-agent/docs/index.html>;
`validation.html` is the examiner annex.

![the board brief — five resolutions in board verbs, the number as evidence](assets/board_asks.png)

Every number on a strike is recomputed from the sealed projection at render
time. The brief argues from evidence, then hands the board its actual choice
on the decision surface one link below.

And the same engine at street level — the Instant Transfer money path, played:

![the money path, playing](assets/journey_demo.gif)

The backlog you watch build at the event bus is the seeded bad morning the
register prices, with owner, controls, and explicit non-claims under every
hop. One graph carries both altitudes: the board's number and the engineer's
morning.

## What it proves

- **A number that survives challenge** — the Monte-Carlo is correlated the
  way real bad years are: failures trigger each other, share common causes,
  and get worse together under load. Re-run it with correlations switched off
  and see what they add; move any single judgment and the total moves at most
  {max_single_note}; stress every judgment at once and a joint bad year lands
  at +{joint_pct} ({joint_usd}). A stress number under stated judgments —
  never presented as a capital figure.
- **Decisions with evidence attached** — the A8 gate (named human · ≥12-word
  justification · expiry) on every governance verb, hash-chained into an
  attestation log verified live in the browser; the closing decision surface
  prices the board's actual choice with owners, delivery-risk flags from the
  internal-audit register, and the politics as data (a priced brief you read
  and take to the committee named on it).
- **Built to sit on your telemetry, temporal by design** — the signals and KRI
  series are the shapes a Prometheus scrape or a Splunk/ELK pipeline already
  exports; this demonstrator seeds them (seed 42) so every claim re-checks.
  And posture is a time axis, not a snapshot: the workbench prices NOW, the
  trajectory view holds the quarter-over-quarter trend with a forecast, and
  every judgment re-runs as a lever.
- **A self-auditing artifact** — **{rac_audit} substance gates** run against
  this repo's own bytes: `pip install -r apps/risk-as-code-agent/requirements.txt`,
  then `python3 apps/risk-as-code-agent/tools/audit_v2_0a.py` (gate C25 re-runs
  the actual pipeline to prove register determinism, so the full pipeline deps
  are required — that is the claim being tested). Gate C39.3 cross-checks every
  owner on the decision surface into
  `domains.*.findings[].org_context.accountable_exec` — no invented
  accountability. Plus {falsification} planted-defect falsification trials on
  the shared harness. OSCAL 1.1.2 output validates against the official schema.

{honesty}
{substrate}
"""

README_ATG = """\
# agent-trace-gov — AI-agent governance, counted from traces

**When the regulator asks "how do you govern the agents?", this is a working
answer.** {findings_total} findings derived from {workflows} synthetic agent
workflows ({actions} tool-call actions traced) — an agent reaching a payments
tool out of scope, customer communications sent past the human gate, a ledger
write with broken lineage, PII egress, consent gaps, multi-agent loops — each
carrying its evidence trail, a **consequence-derived severity with its basis in
the pixels** (unauthorized-action capability tops the scale; notification-class
data events wear their regulatory clock), and framework citations (GDPR · EU AI
Act · FINRA · SEA 17a-4 · SOC 2 · NIST), with a counted data-flow lineage graph
and a hash-chained attestation log.

## See it in 60 seconds

```bash
python3 -m http.server 8080
```

Then open <http://localhost:8080/apps/agent-trace-gov/docs/index.html> — the
workbench walks SIGNAL → PROPAGATE → IMPACT → DECIDE → ATTEST on a role spine.

Below, the PROPAGATE chapter's first paint. You are about to open this page,
so read the graph the way it is drawn: agents on the left, systems and data in
the middle, external endpoints on the right, red where a flow ran unauthorized.

![how risk moves — agent → system → external, counted from the traces](assets/atg_lineage.png)

Open PROPAGATE and count the red edges yourself: {ext_gate_words} external
flows had no human gate. The callout derives from the same edges the page
draws, so the caption cannot outrun the graph.

## What it proves

- **Point it at your traces** — the classifier's rules run over
  OpenTelemetry-shaped spans, the same fields your tracing pipeline already
  exports; this demonstrator seeds those spans synthetically (and says so),
  so production integration is exporter configuration. Findings and the
  lineage graph are COUNTED from the traces; the deliberately verdict-free
  posture ("no findings, no verdicts" on observation surfaces) keeps 2LoD
  independence honest.
- **The agent substrate is a dependency layer** — orchestrator, model provider,
  MCP registry, safety-classifier plane, credential broker — each anchored to
  named public incidents, with blast radii derived from the same traces the
  page renders.
- **Actions leave evidence** — the A8 gate (named human · ≥12-word
  justification · expiry) on every governance verb, SHA-256 hash-chained and
  re-verified live in your browser; **{atg_audit} substance gates** run against
  this repo's own bytes (`pip install -r apps/agent-trace-gov/requirements.txt`,
  then `python3 apps/agent-trace-gov/tools/audit_atg.py` — determinism gates
  re-run the actual pipeline, so the pipeline deps are required).
- **Graded against traces it was not built against** — a misbehavior-injection
  eval runs {eval_injections} seeded variants through the same compiled graph:
  {eval_tp} in-class variants caught, {eval_nm} near-misses one predicate short
  cleanly rejected, {eval_ff} false fires. Rule boundaries are named in
  `qa/detection_eval.json`; the {eval_gaps} class has no deriving rule and the
  record says so. The loop closes through a human: rule changes land only via
  the A8 gate, then the eval re-runs and re-seals — a governor that tunes
  itself on what it measures marks its own homework.

{honesty}
{substrate}
"""

README_HV = """\
# hypervelocity-risk-sim — incident economics, replayed minute by minute

**The observatory the SRE room doesn't dismiss.** {scenarios} seeded incident
scenarios ({events} telemetry events) played as an animated flow-graph — cascade
heat, retry amplification, backlog orbit, the blind-spot ghost leg — with a KRI
scorecard, an escalation ladder, and the manual-vs-instrumented response gap
drawn from the same event series the canvas animates.

## See it in 60 seconds

```bash
python3 -m http.server 8080
```

Then open <http://localhost:8080/apps/hypervelocity-risk-sim/docs/index.html> —
pick a scenario on the spine, press play, scrub the timeline.

Below: HV-01, the consumer-lag cascade. The producer holds steady near 96K
msg/s while the consumer stalls, so the backlog tank fills and the lag counter
runs from thousands into the millions; the moment chips walk precursor →
cascade peak → recovery.

![the incident, playing — scrub the timeline and the counters move](assets/observatory_demo.gif)

Note what never happened: throughput stayed green for the entire incident —
watch levels alone and you sleep through the precursor. The divergence KRIs
are what fire,
and the instrumented response closes at audit-ready with the whole timeline
scrubbable for the postmortem.

## What it proves

- **Platform physics at stated scale** — the archetype is an aggregate estate
  (hundreds of K8s apps, 1000+ namespaces, a 10B+ event/day pipeline ACROSS
  them); per-scenario numbers slice plausibly from those totals, and the copy
  says which numbers are seeded and which are operator-calibrated illustration.
- **Divergence over levels** — KRIs are deliberately TREND-form (absorption vs
  arrival, skew age, retry ratio): in self-healing platforms level-metrics stay
  green while divergence grows, so governance instruments the derivative. The
  series are the shapes a Prometheus scrape already carries — seeded here so
  the claim re-checks. The replay is the practice surface: the same minutes a
  postmortem walks and a tabletop exercise scrubs.
- **Deterministic replay** — everything renders from one sealed projection
  (seeded, reproducible); **{hv_audit} substance gates** run against this
  repo's own bytes (`pip install -r apps/hypervelocity-risk-sim/requirements.txt`,
  then `PYTHONPATH=apps/hypervelocity-risk-sim python3
  apps/hypervelocity-risk-sim/tools/audit_hv.py`), and the hash-chained
  attestation log re-verifies live in the page.

{honesty}
{substrate}
"""


def derived_numbers() -> dict:
    board = json.loads((ROOT / "qa" / "trust_board.json").read_text())
    a = board["audits"]
    gf = board.get("gate_falsification") or {}
    rac = json.loads((ROOT / "apps/risk-as-code-agent/outputs/v2_0a/2026-Q3_projection.json").read_text())
    atg = json.loads((ROOT / "apps/agent-trace-gov/outputs/2026-06_atg_projection.json").read_text())
    hv = json.loads((ROOT / "apps/hypervelocity-risk-sim/docs/projection.json").read_text())

    def m(x):
        return f"{(x or 0) / 1e6:.1f}M"

    exp = rac["exposure"]["portfolio_total"]
    sc = rac.get("strategy_chooser") or {}
    strats = {s["id"]: s for s in sc.get("strategies", [])}
    levers = {l["id"]: l for l in rac.get("sensitivity", {}).get("levers", [])}
    max_single = max((abs(l.get("delta_p95_pct") or 0) for lid, l in levers.items()
                      if not str(lid).startswith("joint")), default=0)
    joint = levers.get("joint_bad_year") or {}
    ac, hc = atg["meta"]["counts"], hv["meta"]["counts"]
    # the lineage caption's own leaves — external edges × attestation-log gate
    # actors, the exact derivation the page's flowGate performs client-side
    _ext = [e for e in atg["lineage_graph"]["edges"] if e.get("external")]
    _gact = {}
    for _en in (atg.get("action_log", {}).get("recent_entries") or []):
        for _fid in (_en.get("linked_findings") or []):
            _gact[_fid] = _en.get("actor_name")
    _gtd = lambda wf: bool(wf) and any(f == wf or ("-" + str(wf)) in f for f in _gact)
    _ung = sum(1 for e in _ext if not _gtd(e.get("workflow_id")))
    _w = {2: "two", 3: "three", 4: "four", 5: "five"}
    return {
        "ext_gate_words": f"{_w.get(_ung, _ung)} of {_w.get(len(_ext), len(_ext))}",
        "rac_audit": f"{a['rac']['pass']}/{a['rac']['total']}",
        "atg_audit": f"{a['atg']['pass']}/{a['atg']['total']}",
        "hv_audit": f"{a['hv']['pass']}/{a['hv']['total']}",
        "falsification": f"{gf.get('caught', 0)}/{gf.get('trials', 0)}",
        "p95": m(exp["p95_usd"]), "inh_p95": m(exp["inherent_p95_usd"]),
        "benefit": m((strats.get("harden_controls") or {}).get("benefit_p95_usd")),
        "ceiling": m((strats.get("isolate_dependencies") or {}).get("layer_ceiling_usd")),
        "max_single_note": f"{max_single:.0f}%",
        "joint_pct": f"{joint.get('delta_p95_pct', 0):.0f}%",
        "joint_usd": "$" + m(joint.get("residual_p95")),
        "findings_total": ac["findings_total"], "workflows": ac["workflows_analyzed"],
        "actions": ac["actions_traced"],
        "scenarios": hc["scenarios_total"], "events": hc["events_total"],
        **_eval_numbers(),
    }


def _eval_numbers() -> dict:
    """Detection-efficacy figures DERIVE from the machine-written eval record —
    the same no-typed-counts discipline as every other README number."""
    ev = json.loads((ROOT / "qa" / "detection_eval.json").read_text())
    c = ev["counts"]
    return {
        "eval_tp": f"{c['tp_caught']}/{c['tp_total']}",
        "eval_nm": f"{c['near_miss_clean']}/{c['near_miss_total']}",
        "eval_ff": c["false_fires"],
        "eval_injections": c["tp_total"] + c["near_miss_total"],
        "eval_gaps": ", ".join(g["cls"] for g in ev.get("coverage_gaps", [])),
    }


def cut(slug: str, readme_tpl: str, nums: dict) -> None:
    out = EXPORTS / slug
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # the spoke, monorepo-relative
    shutil.copytree(ROOT / "apps" / slug, out / "apps" / slug, ignore=IGNORE)
    for rel in SEALED_OUTPUTS[slug]:
        dst = out / "apps" / slug / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "apps" / slug / rel, dst)

    # shared substrate + this spoke's conservation evidence + cross-substrate files.
    # The trust board copy gets an in-file label (external review: three products'
    # counts in a one-product repo read as noise without the shared-harness note).
    for rel in SHARED + [CONSERVATION[slug]] + EXTRA_FILES[slug]:
        src = ROOT / rel
        dst = out / rel
        if src.is_dir():
            shutil.copytree(src, dst, ignore=IGNORE)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # the README's embedded media, per product
    (out / "assets").mkdir()
    for name in PRODUCT_ASSETS[slug]:
        shutil.copy2(ROOT / "assets" / name, out / "assets" / name)

    # license to root (GitHub expects it there)
    shutil.copy2(ROOT / "apps" / slug / "LICENSE", out / "LICENSE")

    board_copy = out / "qa" / "trust_board.json"
    bd = json.loads(board_copy.read_text())
    bd["export_note"] = (f"shared substrate harness record — the executed counts cover all three "
                         f"portfolio products because the seal/gate/falsification harness is one "
                         f"system; this repo is {slug}. Its own rows: audits.{'rac' if slug == 'risk-as-code-agent' else 'atg' if slug == 'agent-trace-gov' else 'hv'}.")
    board_copy.write_text(json.dumps(bd, indent=1, ensure_ascii=True))

    stripped = strip_nav(out)
    restamped = restamp_conservation(out, slug)

    # the product README — every number derived at cut time
    readme = readme_tpl.format(
        honesty=HONESTY_BLOCK,
        substrate=SUBSTRATE_BLOCK.format(falsification=nums["falsification"]),
        **{k: v for k, v in nums.items()},
    )
    (out / "README.md").write_text(readme, encoding="utf-8")
    (out / "verify_export.py").write_text(VERIFY_EXPORT, encoding="utf-8")

    # manifest LAST — hashes everything (except itself)
    lines = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            lines.append(f"{sha256(p)}  {p.relative_to(out)}")
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  {slug}: {len(lines)} files · nav stripped from {stripped} page(s) · "
          f"conservation restamped: {restamped or 'none'}")


def main() -> None:
    EXPORTS.mkdir(exist_ok=True)
    nums = derived_numbers()
    print(f"cutting product repos (audits {nums['rac_audit']} · {nums['atg_audit']} · "
          f"{nums['hv_audit']} · falsification {nums['falsification']}):")
    cut("risk-as-code-agent", README_RAC, nums)
    cut("agent-trace-gov", README_ATG, nums)
    cut("hypervelocity-risk-sim", README_HV, nums)
    print(f"exports → {EXPORTS}/  (gitignored; each directory is one product repo)")


if __name__ == "__main__":
    main()
