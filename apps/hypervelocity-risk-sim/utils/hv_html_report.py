"""
utils.hv_html_report — render the hypervelocity dashboard from a projection.

Thin domain wrapper over portfolio_core.presentation.render_dashboard (the shared
chrome/CSS/runtime). This module owns ONLY what is hypervelocity-specific: the
scenario rail, the explorer stage scaffolding (data-target mount points), and the
domain JS + component CSS. Every value is hydrated client-side by the shared
runtime from the embedded projection — render-from-data, drift-proof, same pattern
as agent-trace-gov. write_hv_report() mirrors the drift-free flow: build
projection → write JSON → read it back → render from the LOADED JSON.

Floor = the "scenario observatory": rail = the 3 scenarios; one act = OBSERVATORY,
an animated incident-flow graph driven by the projection's real per-event telemetry
(bezier edges with live ECG telemetry, particle flow, a timeline scrubber, a KRI
scorecard, an escalation ladder, the regime gap, and an evidence log) — every value
render-from-data.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# ── Bootstrap shared portfolio_core (no install; sibling package) ──
_PC_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "ui-system"))
if _PC_PARENT not in sys.path:
    sys.path.insert(0, _PC_PARENT)

from portfolio_core import presentation as _pres  # noqa: E402

from utils.projection import make_projection, ARTEFACT_VERSION, SCHEMA_VERSION  # noqa: E402

_ASSETS = Path(__file__).resolve().parent / "assets"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REPO_URL = "https://github.com/Jiten76/agentic-risk-portfolio"

# Shipped artefact is reproducible: fixed (seed, as_of) → byte-stable projection + seal.
DEFAULT_SEED = 42
DEFAULT_AS_OF = "2026-06-01T09:00:00Z"

# The single act (id = CSS visibility key; name = label). OBSERVATORY replaces the
# old four-act explorer with one animated incident-flow graph driven by the
# projection's real per-event telemetry — one lens, three scenarios.
_ACTS = [
    {"id": "observatory", "num": "01", "name": "OBSERVATORY", "desc": "the incident, playing", "pressed": True},
]

# r44: hv carries NO persona chips. The observatory signs nothing — there is no
# verb surface for a signing identity to gate — so the chips were a second
# identity system duplicating the spine's "viewing as" selector (and their lens
# switch changed nothing visible: a dead control). One identity/navigation
# question at the top: the spine. The named humans live where they matter here —
# in the seeded attestation chain, surfaced by the attestation panel below.


@lru_cache(maxsize=None)
def _asset(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8")


def _panel(eyebrow: str, title: str, sub: str, mount: str) -> str:
    return (
        '<div class="hv-panel">'
        '<div class="panel-header">'
        f'<div class="panel-eyebrow">{eyebrow}</div>'
        f'<h2 class="panel-title">{title}</h2>'
        f'<div class="panel-sub">{sub}</div>'
        "</div>"
        f'<div data-target="{mount}"></div>'
        "</div>"
    )


def _rail_html() -> str:
    # render-from-data: the scenario items + badges are hydrated by the domain JS
    # from projection.meta.domain_ids — no hardcoded literal that could go stale.
    return (
        '<div class="rail-label">scenarios</div>'
        '<div data-target="rail-scenarios"></div>'
    )


def _stage_html() -> str:
    """The observatory stage — the persistent hero + one mount point. The whole
    observatory (metrics header, timeline scrubber, canvas graph, KRI scorecard,
    escalation ladder, regime gap, evidence log) renders into the single mount from
    the projection; the domain JS hydrates every value client-side."""
    return """
    <style>/* ia active: the spine IS scenario selection — retire the duplicate rail */
    body[data-role] .rail { display: none; }
    body[data-role] .workspace { grid-template-columns: 1fr; }</style>
    <div data-target="scenario-hero"></div>

    <section class="hv-section" data-acts="observatory">
      <div data-target="observatory"></div>
    </section>

    <!-- r44: the chain chip retreats from the header to the evidence it
         attests. hv's chain is the seeded attestation log (named human +
         expiry + >=12-word justification per entry); the chip verifies it
         live in-browser. -->
    <section class="hv-section" data-acts="observatory">
      <div class="hv-panel">
        <div class="panel-header">
          <div class="panel-eyebrow">attestation · hash-chain integrity</div>
          <h2 class="panel-title">Hash-chained action log</h2>
          <div class="panel-sub">Embedded attestations are <b>illustrative</b> demonstrator decisions — each carries a named human, an expiry, and a ≥12-word justification (the A8 discipline). The chain math over them is real: SHA-256 over canonical JSON, verified live in your browser.</div>
        </div>
        """ + _pres.chain_status_html(margin="2px 0 4px") + """
      </div>
    </section>
"""


def render_hv_from_projection(projection: Dict[str, Any]) -> str:
    """Render the full hypervelocity dashboard HTML from a projection dict."""
    projection_json = json.dumps(projection, indent=2, default=str, sort_keys=True)
    meta = projection["meta"]
    counts = meta["counts"]
    period = meta.get("period", "")
    domain_js = _asset("hv_domain.js")
    extra_css = _asset("hv_components.css")

    # r44: version + period are footer chrome, not banner content.
    disclosure = (
        "A demonstrator. Scenarios are simulated and reproduce from a seed; the "
        "response-time gap is operator-calibrated <b>illustration</b>, not measured "
        "telemetry; the named people are fictional."
    )
    footer_left = f"<b>{ARTEFACT_VERSION}</b> · period {period} · seed {meta.get('run_seed')}"
    # empty mount — hydrated client-side from the projection (render-from-data; no baked
    # literal that could silently drift from meta.counts).
    footer_right = '<span data-target="footer-counts"></span> · <a href="archive/classic.html" style="color:inherit">classic view ↗</a>'

    return _pres.render_dashboard(
        projection_json,
        title=f"hypervelocity-risk-sim · {ARTEFACT_VERSION}",
        brand_mark="hypervelocity-risk-sim",
        disclosure=disclosure,
        acts=_ACTS,
        rail_html=_rail_html(),
        stage_html=_stage_html(),
        domain_js=domain_js,
        extra_css=extra_css,
        footer_left=footer_left,
        footer_right=footer_right,
        footer_seal_signer=f"hypervelocity-risk-sim::{ARTEFACT_VERSION} pipeline",
        repo_url=_REPO_URL,
        body_lens="engineer",
        body_act="observatory",
        body_domain=meta["domain_ids"][0],
        schema_version=SCHEMA_VERSION,
        artefact_label=ARTEFACT_VERSION,
    )


def write_hv_report(
    output_path: Optional[str] = None,
    seed: int = DEFAULT_SEED,
    as_of: Optional[str] = DEFAULT_AS_OF,
) -> Dict[str, str]:
    """Drift-free generation (mirrors the other spokes): build projection → write
    JSON → read it back → render from the LOADED JSON. Proves the same JSON that
    ships as evidence is exactly the renderer's input. Reproducible under (seed, as_of)."""
    projection = make_projection(seed=seed, as_of=as_of)

    docs_dir = _PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    if output_path is None:
        output_path = str(docs_dir / "index.html")
    projection_path = str(docs_dir / "projection.json")

    Path(projection_path).write_text(
        json.dumps(projection, indent=2, default=str, sort_keys=True), encoding="utf-8")
    # The committed stream-catalog export is written HERE and nowhere else:
    # only the shipped build stamps data/ — audit builds at other seeds
    # (e.g. the C1.3 seed-sensitivity projection) must never rewrite it.
    (_PROJECT_ROOT / "data" / "stream_catalog.json").write_text(json.dumps({
        "_generated_by": f"event_generator@seed{seed} via utils/hv_html_report.write_hv_report — do not hand-edit",
        "port_tag": "Structure from the operator's production 2LoD practice; all names, values, and dates seeded.",
        "streams": projection["stream_catalog"]}, indent=1), encoding="utf-8")
    loaded = json.loads(Path(projection_path).read_text(encoding="utf-8"))
    html_str = render_hv_from_projection(loaded)
    Path(output_path).write_text(html_str, encoding="utf-8")
    return {"html": output_path, "projection": projection_path}


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED
    paths = write_hv_report(seed=seed, as_of=DEFAULT_AS_OF)
    print(f"wrote: {paths['html']}  (seed={seed}, reproducible)")
    print("projection:", paths["projection"])
