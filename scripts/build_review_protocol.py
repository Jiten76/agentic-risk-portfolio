#!/usr/bin/env python3
"""build_review_protocol — the GUIDED deep-review instrument (r54).

Emits reviews/DEEP_REVIEW_PROTOCOL.md: an intent-vs-experience walkthrough of
every app, tab, link and flow, for a BRIEFED reviewer.

Two-instrument rule (hard): this protocol is the SECOND instrument. The cold
read (unbriefed human, no document, "tell me what it is and where you got
lost") always runs FIRST — handing someone this file before their first look
burns them as a cold reader permanently. Same person may do both, only in
that order.

House discipline: the coverage inventory DERIVES from the sealed projections
(ia.paths, ia.nodes, acts, domains) and the shipped docs/ trees — a hand-typed
checklist would drift the first time a node lands; a derived one cannot claim
a surface the pages don't have. The INTENT/EXPECT/ASK prose is authored here,
on top of the derived skeleton.

Run from repo root:  python3 scripts/build_review_protocol.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reviews" / "DEEP_REVIEW_PROTOCOL.md"

PROJ = {
    "rac": ROOT / "apps/risk-as-code-agent/outputs/v2_0a/2026-Q3_projection.json",
    "atg": ROOT / "apps/agent-trace-gov/outputs/2026-06_atg_projection.json",
    "hv": ROOT / "apps/hypervelocity-risk-sim/docs/projection.json",
}
DOCS = {
    "rac": ROOT / "apps/risk-as-code-agent/docs",
    "atg": ROOT / "apps/agent-trace-gov/docs",
    "hv": ROOT / "apps/hypervelocity-risk-sim/docs",
}


def load(k: str) -> dict:
    return json.loads(PROJ[k].read_text())


def coverage_tables(p: dict, base_url: str) -> str:
    """The derived skeleton: roles × path, node inventory, acts."""
    ia = p.get("ia") or {}
    nodes = {n["id"]: n for n in ia.get("nodes", [])}
    out = ["**Role paths (every row is a walk you can run; the spine order IS the argument):**", ""]
    out.append("| role | the walk, in order |")
    out.append("|---|---|")
    for role, path in sorted((ia.get("paths") or {}).items()):
        seq = " → ".join(f"`{nid}`" for nid in path)
        out.append(f"| `{role}` | {seq} |")
    out.append("")
    out.append("**Node inventory (open each via `#role=<role>&node=<id>`; every listed mount must render content, not a stub):**")
    out.append("")
    out.append("| node | label | act | mounts to check |")
    out.append("|---|---|---|---|")
    for nid, n in nodes.items():
        tg = n.get("targets") or []
        out.append(f"| `{nid}` | {n.get('label','')} | {n.get('act','')} | {len(tg)}: " +
                   ", ".join(f"`{t}`" for t in tg[:6]) + (" …" if len(tg) > 6 else "") + " |")
    out.append("")
    out.append(f"Base URL for this track: `{base_url}`")
    return "\n".join(out)


def page_inventory(k: str, base_url: str) -> str:
    """Every shipped page under docs/ — the annex sweep's checklist."""
    rows = []
    for f in sorted(DOCS[k].rglob("*.html")):
        rel = f.relative_to(DOCS[k])
        kind = ("frozen archive — links reflect its era, review CONTENT only"
                if "archive" in rel.parts else
                "redirect stub — must bounce to a live page" if rel.name in ("read.html", "tour.html")
                else "live page")
        rows.append(f"| `{rel}` | {kind} |")
    return "\n".join(["| page | what it is |", "|---|---|"] + rows)


def beats(title: str, items: list[tuple[str, str, str, str]]) -> str:
    out = [f"### Core spine — {title}", ""]
    for i, (intent, walk, expect, ask) in enumerate(items, 1):
        out += [f"**Beat {i} · INTENT** — {intent}",
                f"- **WALK**: {walk}",
                f"- **EXPECT**: {expect}"]
        if ask:
            out.append(f"- **ASK**: {ask}")
        out.append("")
    return "\n".join(out)


def main() -> None:
    rac, atg, hv = load("rac"), load("atg"), load("hv")
    rc = rac["meta"]["counts"]; ac = atg["meta"]["counts"]; hc = hv["meta"]["counts"]
    rac_p95 = rac["exposure"]["portfolio_total"]["p95_usd"] / 1e6
    sc = rac.get("strategy_chooser") or {}
    strats = {s["id"]: s for s in sc.get("strategies", [])}
    benefit = (strats.get("harden_controls") or {}).get("benefit_p95_usd", 0) / 1e6
    ceiling = (strats.get("isolate_dependencies") or {}).get("layer_ceiling_usd", 0) / 1e6

    doc = []
    doc.append(f"""# Deep Review Protocol — guided intent-vs-experience walkthrough

**What this is.** A briefed, beat-by-beat review of every app, tab, link and
flow. Each beat states the INTENT (what we are trying to flow through that
surface), the WALK (exact clicks), and the EXPECT (what it looks like when the
intent lands). Your job is to report where experience diverges from intent —
this is a failure hunt, not a tour.

**THE HARD RULE.** This is the SECOND instrument. If you have never seen these
pages: STOP, close this file, open the app with no context, and give your
unbriefed first-minute read to the operator ("what is this? what would you
trust? where did you get lost?"). Only then return here. A cold read cannot be
re-run on a briefed brain.

**How to run.** From the repo root:

```bash
python3 -m http.server 8080
```

**Capture, after EVERY beat** (verbatim notes beat-by-beat; do not summarize
at the end):
1. Where did you stall or re-read?
2. What did you NOT believe, and why?
3. What would you cut?
4. What did you expect to happen that didn't?

Severity-tag anything broken: FALSIFIED (claim contradicts the bytes) ·
BROKEN (interaction fails) · OVERSTATED (words ahead of the surface) ·
CONFUSING (intent didn't land) · IMPROVEMENT. Confirmed findings are recorded
in `qa/DEFECT_CLASS_LEDGER.md` as human-review entries.

**Out of scope, deliberately:** redesigning the front door / information
architecture (that question is reserved to unbriefed cold readers), and the
politeness reflex. If a beat bored you, say so — boredom is data.

**Global questions (answer once, at the very end):**
- What is this portfolio, in your own one sentence?
- What would you trust enough to act on? What would you never act on?
- If you had to delete one third of everything you saw, what goes?

---

## Track 0 · The portfolio hub (only when reviewing the monorepo, not a product repo)

**INTENT** — one category sentence, then one obvious primary path; a visitor
should know what this is in 20 seconds and be walking the journey in 60.

- **WALK**: open `http://localhost:8080/PORTFOLIO_INDEX.html`. Read only the
  first screen for 20 seconds. Then follow whatever the page pushes hardest.
  Then open the MAP drawer (left edge) and visit each destination once.
- **EXPECT**: the category sentence lands before any number; the journey is
  visibly the "start here" door; the MAP's you-are-here highlight tracks you;
  every MAP link resolves.
- **ASK**: after the first screen, what did you believe this repo was FOR?
  Which door did you actually click first, and why that one?

---

## Track 1 · risk-as-code-agent — the CRO / board / examiner room

**The argument this app must carry:** fourteen failure patterns become one
challengeable number (${rac_p95:.1f}M residual P95), every judgment is a priced
lever, and the page ends on a DECISION — two priced postures (−${benefit:.1f}M
bankable · ${ceiling:.1f}M ceiling) or a signed hold. Currently
{rc['findings_total']} findings across {rc['domains_total']} domains,
{rc['findings_red']} red.

""")
    doc.append(beats("rac (walk as `leadership`, then re-walk two beats as `engineering`)", [
        ("The header asks ONE question (where am I); identity lives where verbs live, version lives in the footer.",
         "Open `apps/risk-as-code-agent/docs/index.html#role=leadership`. Look only above the fold.",
         "Brand + motion toggle only in the header; the spine ('viewing as' + step pills) is the sole navigation; the disclosure names synthetic data without version chrome.",
         "What is the FIRST number you saw, and did you want it that early?"),
        ("The stake lands as a translated argument: gross → controls → net, not a wall of tiles.",
         "Walk to `stake` (step pill or `#node=stake`). Read the headline strip, then hover an exposure card, then find the dependency tornado.",
         "The inherent→residual cut reads in one line; the tornado names shared layers (identity plane on top) with per-node dollars.",
         "Could you re-state 'what could a bad year cost and why' after 60 seconds? Try, out loud."),
        ("Every register row is evidence, not a rating: click-through must hit signals, thresholds with public sources, and org context.",
         "Walk to `register`. Click the top red row. Open its lineage. Then find who is ACCOUNTABLE for it.",
         "Signal values with threshold sources; org context carries a named exec, a competing commitment, a decision route.",
         "Did the accountability read as real organizational texture or as filler names?"),
        ("The cascade is a priced mechanism, not a diagram: switching it off must move the number.",
         "Walk to `cascade`. Find the sentence that prices the graph (independence counterfactual).",
         "Edges counted; the 'switch it off and P95 falls to …' claim is present and specific.", ""),
        ("The docket is where verbs live — and A8 makes every verb a named human with a justification.",
         "Walk to `docket`. Read the org-reality strip. Open any verb from the queue. Type a 3-word justification. Then cancel.",
         "The signing context sits with the verbs; the modal REFUSES short justifications (counter visible); cancel leaves no trace.",
         "Did the A8 gate feel like governance or like friction theater? Be honest."),
        ("Regulation is a flag, not a verdict: applicability caveats must survive into the pixels.",
         "Walk to `regulation`. Find one regime marked as style-mapping/contractual vs one that binds.",
         "The † caveat (or equivalent) is visible in the grid AND in any docket rows citing regimes; 'determination reserved to Legal' appears.", ""),
        ("The challenge apparatus is the credibility: every judgment priced, the chain breakable, the seal recomputable.",
         "Walk to `attack`. Read the tornado. Then scroll to the hash chain, note 'intact'. Then footer: click `verify ↪`.",
         "No single lever >50%, joint bad year +90% — stated; the chain chip sits WITH the chain; the seal verifies in-browser.",
         "Pick the ONE lever you'd challenge in a real 2LoD meeting. Was it one click away?"),
        ("The closing screen is a decision, not a dashboard: two priced postures and a signed hold, with owners and politics as data.",
         "Walk to `strategy`. Recompute one dollar in your head from the basis lines. Find the credit gate, the PAST DUE flag, the acting-role gap, the competing commitments. Read the hold strip fully.",
         "−$24.3M and $33.9M carry their derivations in the pixels; the hold carries a SIGN verb and the $186.6M stress figure at the same visual weight; nothing on this screen claims to re-run the engine.",
         "Would you take THIS page to your board? What is missing before you would?"),
        ("The story is an epilogue, not a summary: the whole argument in one animated picture.",
         "Walk to `story`. Press the walker through all steps. Click one step's evidence link.",
         "Each step scrolls to a live node; the flow picture animates from the projection.", ""),
        ("The board brief opens on asks, not numbers — and routes back to the decision surface without minting a sixth ask.",
         "Open `apps/risk-as-code-agent/docs/board.html`. Count the resolutions. Follow the pointer under them.",
         "Five resolutions in board verbs; the number is chapter 02; the pointer lands on the leadership decision surface, hydrated.",
         "Read resolution 03 aloud. Is it actually decidable as written?"),
        ("The journey is the 60-second proof: one money path under stress, evidence under every hop, no verdicts.",
         "Open `apps/risk-as-code-agent/docs/journey.html`. Press play. Scrub. Click two services. Find the non-claim ribbon.",
         "Lanes/direction/retry-loop/backlog read as a system under stress; every service opens patterns + owner + signals; the ribbon says no findings, no verdicts.",
         "At the peak, could you tell WHERE the incident is concentrating without reading labels?"),
    ]))
    doc.append(coverage_tables(rac, "http://localhost:8080/apps/risk-as-code-agent/docs/index.html"))
    doc.append("\n**Annex sweep (after core; ~20 min):** `validation.html` end-to-end "
               "(the examiner annex: §7 contract, levers behind each step); every page "
               "below; every remaining node × your second role; the lineage modal ESC/"
               "backdrop behavior; the MAP drawer from every page (monorepo only).\n")
    doc.append(page_inventory("rac", "http://localhost:8080/apps/risk-as-code-agent/docs/"))

    doc.append(f"""

---

## Track 2 · agent-trace-gov — the AI-governance room

**The argument this app must carry:** agent governance with evidence —
{ac['findings_total']} findings derived from {ac['workflows_analyzed']} synthetic
workflows ({ac['actions_traced']} traced actions), a counted lineage graph, a
verdict-free observation posture, and a hash-chained attestation log.

""")
    doc.append(beats("atg (walk as `basic`, re-walk DECIDE as `auditor`)", [
        ("Same header grammar as rac: one question at the top, no identity chrome.",
         "Open `apps/agent-trace-gov/docs/index.html`. Above the fold only.",
         "Brand + motion; spine with 'viewing as'; disclosure says synthetic traces plainly.", ""),
        ("Findings fire from traces, not opinions: every row must open an evidence trail.",
         "Walk to the signal node. Click the top finding's lineage.",
         "The trail shows the actual trace steps that produced the finding — workflow, action, rule.",
         "Did any finding read as asserted rather than derived? Name it."),
        ("The lineage graph is COUNTED from traces — and direction is drawn.",
         "Walk to the propagate/lineage node. Count chevrons on a few flows. Find an RE-03 external flow and an RE-08 loop.",
         "Arrowheads ride every flow at their midpoints; external flows are lit; loops are dashed.", ""),
        ("The agent substrate is a dependency layer with named public anchors — structural, deliberately dollar-free.",
         "Same act: read the shared-dependencies panel. Find the rac-analog tags and one named incident anchor.",
         "Orchestrator/model-provider/registry/classifier/broker each carry blast radius, an anchor, and a cross-substrate analog; NO dollars claimed here.",
         "Did the deliberate absence of dollars read as honesty or as a gap?"),
        ("Regulations are grouped facts, not verdicts.",
         "Walk to impact. Find one US and one EU obligation tied to a firing class.",
         "Article-level citations; the materiality determination is explicitly reserved.", ""),
        ("DECIDE is where identity appears — and only there.",
         "Walk to the decide node. Switch signing identity to M. Okonkwo. Open a verb from the queue; cancel.",
         "The signing strip exists ONLY here; the acting-as ribbon updates on click; the A8 modal enforces the 12-word floor.",
         "Scroll back up: is there ANY identity control above this panel? (There must not be.)"),
        ("ATTEST is a chain you can break, not a badge.",
         "Walk to attest. Read the chain chip. Read the precedent register.",
         "'chain · intact N/N' in green NEXT to the chain detail; embedded attestations labeled illustrative; precedent anchors are real incidents keyed to RE classes.", ""),
        ("The copy-link survives a hostile browser.",
         "Click the spine's `⧉ link` button.",
         "Either the clipboard takes it silently or a prompt offers the URL — never a console error.", ""),
    ]))
    doc.append(coverage_tables(atg, "http://localhost:8080/apps/agent-trace-gov/docs/index.html"))
    doc.append("\n**Annex sweep:** every remaining node × role; the workflow rail (does "
               "scoping to one workflow change the queue AND the lineage?); footer seal "
               "`verify ↪`; the frozen classic.\n")
    doc.append(page_inventory("atg", "http://localhost:8080/apps/agent-trace-gov/docs/"))

    doc.append(f"""

---

## Track 3 · hypervelocity-risk-sim — the engineering room

**The argument this app must carry:** incident economics replayed —
{hc['scenarios_total']} seeded scenarios, {hc['events_total']} events, divergence-form
KRIs, an honest manual-vs-instrumented gap, and a failure SHAPE you can see
before you read a single label.

""")
    doc.append(beats("hv (walk as `engineering`)", [
        ("One question at the top; the spine IS scenario selection.",
         "Open `apps/hypervelocity-risk-sim/docs/index.html`. Above the fold only.",
         "Brand + motion; 'viewing as' + four scenario pills; NO persona chips anywhere on this app.", ""),
        ("Each scenario is a different SHAPE, not a different dataset.",
         "Play `kafka_lag_storm` to peak. Then switch to `deployment_cascade`, then `identity_outage`. Watch 20 seconds each.",
         "Backlog blowup vs cascade fan vs the recursion where responders are locked out WITH customers — distinguishable at a glance, before reading.",
         "Cover the labels: could you still say which scenario you're in? What visual told you?"),
        ("Direction and blindness are drawn honestly.",
         "At peak on any scenario, find arrowheads mid-edge, then find the ghost leg.",
         "Every observed flow carries direction; the unobservable leg carries NONE — no signal, no claimed arrow.", ""),
        ("The gap is illustration and says so at the point of reading.",
         "Find the manual-vs-instrumented response gap. Read its caption.",
         "The minutes wear 'operator-calibrated illustration, NOT measured telemetry' next to the numbers, not in a distant footnote.",
         "Did any number in this app feel like it claimed measurement it doesn't have?"),
        ("KRIs are divergence-form because self-healing platforms mask levels.",
         "Read the KRI scorecard on kafka. Find one trend/divergence KRI and restate what it instruments.",
         "Absorption-vs-arrival, skew-age, retry-ratio style derivatives — not raw level gauges.", ""),
        ("The chain lives with its evidence here too.",
         "Scroll to the attestation panel below the observatory.",
         "'Hash-chained action log' panel: illustrative attestations disclosed, chain chip verifies green in-browser.", ""),
        ("The escalation ladder and evidence log tie the replay to governance reality.",
         "Play recovery on any scenario; watch the ladder and the evidence log fill.",
         "Rungs fire in causal order; the log's audit-ready line appears in recovery.", ""),
    ]))
    doc.append(coverage_tables(hv, "http://localhost:8080/apps/hypervelocity-risk-sim/docs/index.html"))
    doc.append("\n**Annex sweep:** all four scenarios × play/scrub/4× speed/tour; the war-room "
               "dialog; footer seal `verify ↪`; the frozen classic + read stub.\n")
    doc.append(page_inventory("hv", "http://localhost:8080/apps/hypervelocity-risk-sim/docs/"))

    doc.append("""

---

## After the walk — the capture you hand back

1. Your beat-by-beat notes, verbatim (stalls, disbeliefs, cuts, missed expectations).
2. The three global answers.
3. Anything tagged FALSIFIED or BROKEN, with the exact page + click path to reproduce.

The operator triages every item against the bytes before disposition — you will
get back a CONFIRMED / REFUTED / PARKED verdict per finding, the same treatment
every AI review wave received.

*Generated by `scripts/build_review_protocol.py` from the sealed projections —
the coverage tables cannot claim a node the pages don't have. Regenerate after
any rebuild.*
""")

    OUT.write_text("\n".join(doc), encoding="utf-8")
    n_beats = sum(s.count("**Beat ") for s in doc)
    print(f"wrote {OUT.relative_to(ROOT)} · {n_beats} authored beats + derived coverage for 3 tracks")


if __name__ == "__main__":
    main()
