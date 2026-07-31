"""
utils.atg_html_report — render the ATG dashboard from a projection.

Thin domain wrapper over portfolio_core.presentation.render_dashboard (the shared
chrome/CSS/runtime). This module owns ONLY what is ATG-specific: the workflow
rail, the five-act stage scaffolding (data-target mount points), and the domain
JS + component CSS assets. Every value is hydrated client-side by the shared
runtime from the embedded projection — render-from-data, drift-proof (port spec
§14.A.4 / §15.E). write_atg_report() mirrors risk-as-code-agent's drift-free
flow: build projection → write JSON → read it back → render from the loaded JSON.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# ── Bootstrap shared portfolio_core (no install; sibling dir) ──
_PC_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "ui-system"))
if _PC_PARENT not in sys.path:
    sys.path.insert(0, _PC_PARENT)

from portfolio_core import presentation as _pres  # noqa: E402

from utils.projection import make_projection, ARTEFACT_VERSION, SCHEMA_VERSION  # noqa: E402

_ASSETS = Path(__file__).resolve().parent / "assets"
_REPO_URL = "https://github.com/Jiten76/agent-trace-gov"

# Shipped artefact is reproducible: a fixed (seed, as_of) makes the projection —
# and the SHA-256 seal computed over it — byte-stable run-to-run.
DEFAULT_SEED = 42
DEFAULT_AS_OF = "2026-06-01T09:00:00Z"


@lru_cache(maxsize=None)
def _asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


# ── the five-act IA (internal id → label). Act #2 id stays `pattern` so it reuses
#    the shared CSS visibility contract; its LABEL is PROPAGATE (port spec rename).
_ACTS = [
    {"id": "signal",  "num": "01", "name": "SIGNAL",    "desc": "what fired",     "pressed": True},
    {"id": "pattern", "num": "02", "name": "PROPAGATE", "desc": "how it flows"},
    {"id": "impact",  "num": "03", "name": "IMPACT",    "desc": "what's exposed"},
    {"id": "decide",  "num": "04", "name": "DECIDE",    "desc": "what to do"},
    {"id": "attest",  "num": "05", "name": "ATTEST",    "desc": "prove it"},
]

# Personas are shared across the portfolio (consistent 1/2/3-LoD identities).
# r44: they are SIGNING identities, not navigation — rendered in the DECIDE
# panel's A8 signing context (next to the verbs they sign), not in the header.
_CHIPS = [
    {"lens": "engineer", "default_act": "signal", "avatar": "DP",
     "name": "D. Patel",   "role": "1LoD eng",   "pressed": True},
    {"lens": "exec",     "default_act": "impact", "avatar": "SK",
     "name": "S. Khoury",  "role": "2LoD exec"},
    {"lens": "auditor",  "default_act": "attest", "avatar": "MO",
     "name": "M. Okonkwo", "role": "3LoD audit"},
]
_RIBBON = {"name": "D. Patel", "role": "· 1LoD · AI Platform Eng"}


def _panel(eyebrow: str, title: str, sub: str, mount: str, mount_class: str = "") -> str:
    cls = f' class="{mount_class}"' if mount_class else ""
    return (
        '<div class="atg-panel">'
        '<div class="atg-panel-head">'
        f'<div class="atg-panel-eyebrow">{eyebrow}</div>'
        f'<h2 class="atg-panel-title">{title}</h2>'
        f'<div class="atg-panel-sub">{sub}</div>'
        "</div>"
        f'<div data-target="{mount}"{cls}></div>'
        "</div>"
    )


def _rail_html() -> str:
    # render-from-data: the all-count + per-workflow items are hydrated by the
    # runtime/domain JS from the embedded projection — no hardcoded literal that
    # could go stale on first paint.
    return (
        '<div class="rail-label">workflows</div>'
        '<div class="rail-item" data-domain="all" aria-pressed="true" title="All traced workflows">'
        '<span class="rail-name">all_workflows</span>'
        '<span class="rail-badge" data-target="rail-count-all"></span>'
        "</div>"
        '<div class="rail-divider"></div>'
        '<div data-target="rail-domains"></div>'
    )


def _stage_html() -> str:
    """The five-act stage. Bare mount points only — the runtime + domain JS
    hydrate every value from the embedded projection."""
    return f"""
    <section class="atg-section" data-node="trail">
      <div data-target="signal-hero"></div>
      {_panel("SIGNAL · governance pass", "Risk events that fired",
              "Each row is one (workflow × risk-event), reconstructed from real agent traces. Click <b>lineage</b> for the evidence trail.",
              "signal-queue")}
    </section>

    <section class="atg-section" data-node="lineage">
      {_panel("PROPAGATE · observed data-flow", "How risk moves agent → system → external",
              "The first-paint hero: structural lineage COUNTED from traces (not a probabilistic cascade). RE-03 unauthorised external flows are lit; RE-08 multi-agent loops are dashed.",
              "lineage-hero")}
      {_panel("PROPAGATE · taxonomy", "Risk-event classes (RE-01…08)",
              "Authoritative taxonomy + framework citations from action_schema.json. Firing classes are highlighted; incident anchors live in the ATTEST precedent register, never on a finding.",
              "pattern-primer")}
      {_panel("PROPAGATE · shared dependencies", "What the agent estate rides on",
              "The common-cause layer of the AGENT substrate — orchestrator, model provider, tool registry, classifier plane, credential broker. Blast radii are DERIVED from the same traces and lineage this page renders; each node names its rac analog (same mechanism, priced in dollars on the infrastructure substrate). Structural units only — atg deliberately carries no loss-dollar model.",
              "agent-dependencies")}
    </section>

    <section class="atg-section" data-node="exposure">
      <div data-target="impact-magnitude"></div>
      {_panel("IMPACT · regulations triggered", "Which obligations these findings trigger — US, EU &amp; cross-cutting",
              "Which regulatory obligations the firing risk-events trigger, grouped by jurisdiction. Article-level facts only — the materiality DETERMINATION is reserved to Legal/Compliance.",
              "impact-materiality")}
    </section>

    <section class="atg-section" data-node="verbs">
      <!-- r30 (operator finding): the vocabulary is a LEGEND, not a page — as a
           sibling walk unit it became "PANEL 1" with no caption, hiding the
           queue (the act's actual work surface) behind the ▸ arrow and reading
           as a blank act. One panel: queue first, legend as its footer; the
           sub-walker auto-hides on single-unit nodes. -->
      <div class="atg-panel">
        <div class="atg-panel-head">
          <div class="atg-panel-eyebrow">DECIDE · act on a finding</div>
          <h2 class="atg-panel-title">Apply a governance verb</h2>
          <div class="atg-panel-sub">Every action requires a named human + ≥12-word justification (the A8 gate, enforced in your browser) and is hash-chained into the attestation log.</div>
        </div>
        {_pres.signing_context_html(_CHIPS, _RIBBON, label="signing identity · who the verb signs as")}
        <div data-target="decide-queue"></div>
        <div data-target="decide-verbs"></div>
      </div>
    </section>

    <section class="atg-section" data-node="attest">
      <div class="atg-panel">
        <div class="atg-panel-head">
          <div class="atg-panel-eyebrow">ATTEST · chain integrity</div>
          <h2 class="atg-panel-title">Hash-chained attestation log</h2>
          <div class="atg-panel-sub">SHA-256 over canonical JSON, verified live in-browser — byte-matching the Python signer. Embedded attestations are <b>illustrative</b> demonstrator decisions; the chain math over them is real. Actions you take this session append locally and re-verify.</div>
        </div>
        {_pres.chain_status_html()}
        <div data-target="attest-chain"></div>
      </div>
      <div class="atg-panel"><div class="action-log event-stream" data-target="attest-log"></div></div>
      {_panel("ATTEST · regulatory precedent", "Incident anchor register",
              "Real enforcement precedent keyed to the RE class (port spec §14.A.3) — deliberately separated from any single finding's magnitude.",
              "attest-precedent")}
      {_panel("ATTEST · detection efficacy · seeded · deterministic",
              "Graded against traces it was not built against",
              "The audit gates prove the classifier catches the shipped scenarios. This eval injects what it was never shown: in-class variants (different agents, tools, endpoints, boundary values) that must fire, and near-misses one predicate short of the rule that must not. Every figure hydrates from the sealed eval record.",
              "eval-efficacy")}
    </section>
"""


def render_atg_from_projection(projection: Dict[str, Any]) -> str:
    """Render the full ATG dashboard HTML from a projection dict."""
    projection_json = json.dumps(projection, indent=2, default=str, sort_keys=True)
    meta = projection["meta"]
    counts = meta["counts"]
    period = meta.get("period", "")
    domain_js = _asset("atg_domain.js")
    extra_css = _asset("atg_components.css")

    # r44: version + period are footer chrome, not banner content.
    disclosure = (
        "A demonstrator. The agent traces are <b>synthetic</b> and reproduce from a seed; "
        "the governance logic that reads them is real, and every finding traces to its "
        "evidence."
    )
    footer_left = f"<b>{ARTEFACT_VERSION}</b> · period {period} · <a href='archive/classic.html' style='color:inherit'>classic view ↗</a>"
    footer_right = (
        f'<span data-target="footer-counts">{counts["findings_total"]} findings · '
        f'{counts.get("workflows_analyzed", 0)} workflows · {counts.get("actions_traced",0)} actions</span>'
    )

    return _pres.render_dashboard(
        projection_json,
        title=f"agent-trace-gov · {ARTEFACT_VERSION}",
        brand_mark="agent-trace-gov",
        disclosure=disclosure,
        acts=_ACTS,
        rail_html=_rail_html(),
        stage_html=_stage_html(),
        domain_js=domain_js,
        extra_css=extra_css,
        footer_left=footer_left,
        footer_right=footer_right,
        footer_seal_signer=f"agent-trace-gov::{ARTEFACT_VERSION} pipeline",
        repo_url=_REPO_URL,
        body_lens="engineer",
        body_act="signal",
        body_domain="all",
        schema_version=SCHEMA_VERSION,
        artefact_label=ARTEFACT_VERSION,
    )


def write_atg_report(
    result: Dict[str, Any],
    output_path: Optional[str] = None,
    run_seed: Optional[int] = None,
    as_of: Optional[str] = None,
) -> Dict[str, str]:
    """Drift-free generation (mirrors risk-as-code-agent.write_v2_report):
    build projection → write JSON → read it back → render from the LOADED JSON.
    Proves the same JSON that ships as evidence is exactly the renderer's input.

    Pass (run_seed, as_of) — as the shipped pipeline does — for a byte-reproducible
    projection + artefact seal.
    """
    projection = make_projection(result, as_of=as_of, run_seed=run_seed)
    period = projection["meta"]["period"]

    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(exist_ok=True)
    if output_path is None:
        output_path = str(out_dir / f"{period}_atg_dashboard.html")
    projection_path = str(out_dir / f"{period}_atg_projection.json")

    Path(projection_path).write_text(
        json.dumps(projection, indent=2, default=str, sort_keys=True), encoding="utf-8")
    loaded = json.loads(Path(projection_path).read_text(encoding="utf-8"))
    html_str = render_atg_from_projection(loaded)
    Path(output_path).write_text(html_str, encoding="utf-8")
    return {"html": output_path, "projection": projection_path}


if __name__ == "__main__":
    from graph.governance_graph import run_governance_analysis_full
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SEED
    result = run_governance_analysis_full(n, seed=seed)
    paths = write_atg_report(result, run_seed=seed, as_of=DEFAULT_AS_OF)
    print(f"wrote: {paths['html']}  (n={n}, seed={seed}, reproducible)")
    print("projection:", paths["projection"])
