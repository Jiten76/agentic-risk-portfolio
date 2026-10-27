"""
portfolio_core.presentation — the shared render-from-data presentation layer.

EXTRACTED (not copy-pasted) from risk-as-code-agent/utils/v2_html_report.py per
port spec §14.D / §15.E step 2. The warm-terminal CSS + M6 responsive, the
generic render-from-data JS plumbing, and the HTML shell are 100%-generic
scaffolding; both risk-as-code-agent and agent-trace-gov import them and supply
their own domain render functions + projection.

Extraction is incremental (§15.E order):
  step 2a — CSS asset (warm_terminal.css)            ← here
  step 2b — generic JS plumbing
  step 2c — shell template (render-iff-present)

Assets live under portfolio_core/assets/ and are read as text (no templating in
the CSS — it is literal). Behavior-preserving: each project gets byte-identical
styling it had inline before the extraction.
"""
from __future__ import annotations

import hashlib
import html as _html
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_ASSETS = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=None)
def read_asset(name: str) -> str:
    """Read a shared presentation asset (css/js/html) as text."""
    return (_ASSETS / name).read_text(encoding="utf-8")


def base_css() -> str:
    """The base design system — the ``:root`` warm-terminal token palette
    (--bg-elev-*, --text-*, --accent, rag colours, type + spacing scales) plus
    base element/component styles. ``warm_terminal.css`` CONSUMES these tokens;
    without base_css every var() is undefined and the dashboard renders unstyled.
    Extracted from risk-as-code-agent/templates/report_styles.css."""
    return read_asset("base.css")


def warm_terminal_css() -> str:
    """The shared warm-terminal design language + M6 responsive CSS.
    Sourced from a single file so all portfolio projects render identically and
    a style fix lands once, not three times."""
    return read_asset("warm_terminal.css")


def dashboard_css() -> str:
    """The full shared stylesheet: base tokens + warm-terminal components, in the
    order risk-as-code-agent composes them (base_styles + _V2_STYLE_INJECT)."""
    return base_css() + "\n\n" + warm_terminal_css()


def runtime_js() -> str:
    """The shared, domain-agnostic render-from-data runtime (step 2b).

    Loads the embedded projection, verifies the hash chain, drives the verb +
    lineage modals and the act/lens/domain switching, and on boot calls the
    domain's ``window.PortfolioDomain.renderAll(ctx)``. Zero domain knowledge —
    each project supplies its own render functions + stage HTML."""
    return read_asset("runtime.js")


def _esc(s: Any) -> str:
    return _html.escape("" if s is None else str(s), quote=True)


def artefact_hash(html_str: str) -> str:
    """SHA-256 over the rendered body with the hash slot neutralised to a
    sentinel, so the digest is stable and any post-attestation edit breaks it.
    Generic (was ``_hash_artefact`` in risk-as-code-agent, port spec §15.E)."""
    sentinel = "{{ARTEFACT_HASH_PLACEHOLDER}}"
    if sentinel not in html_str:
        return ""
    return hashlib.sha256(
        html_str.replace(sentinel, "<<<HASH_INPUT>>>").encode("utf-8")
    ).hexdigest()


# ── shell fragment builders (domain feeds the data; chrome is shared) ──

def _user_chips_html(chips: List[Dict[str, Any]]) -> str:
    out = []
    for c in chips:
        pressed = "true" if c.get("pressed") else "false"
        out.append(
            f'<button class="user-chip" data-lens="{_esc(c["lens"])}" '
            f'data-default-act="{_esc(c.get("default_act", ""))}" '
            f'aria-pressed="{pressed}" type="button">'
            f'<span class="user-chip-avatar">{_esc(c.get("avatar", ""))}</span>'
            f'<span><span class="user-chip-name">{_esc(c.get("name", ""))}</span>'
            f' · <span class="user-chip-role">{_esc(c.get("role", ""))}</span></span>'
            "</button>"
        )
    return "\n      ".join(out)


def signing_context_html(
    user_chips: List[Dict[str, Any]],
    ribbon: Dict[str, str],
    label: str = "signing identity · per A8 every verb needs a named human",
) -> str:
    """The A8 signing context — named personas + acting-as ribbon.

    r44 (external review, verified on rac): the header ran TWO identity systems
    (persona chips + identity ribbon) before a single number rendered. The named
    signing personas belong where signing actually happens, so the DOMAIN places
    this block next to its verb surface — the chrome no longer renders identity.
    Element classes/ids are the contract runtime.js binds to (.user-chip,
    #ribbon-name, #ribbon-role)."""
    return f"""<div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin:6px 0 10px">
          <span style="font-family:var(--font-mono, ui-monospace, monospace); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:rgba(232,223,211,.45)">{_esc(label)}</span>
          <div class="user-strip" role="tablist" aria-label="Switch signing identity">
      {_user_chips_html(user_chips)}
          </div>
          <div class="identity-ribbon" title="Per A8 — every action requires a named human + 12-word justification + expiry">
            <span class="identity-ribbon-label">acting as</span>
            <span class="identity-ribbon-name" id="ribbon-name">{_esc(ribbon.get("name", ""))}</span>
            <span class="identity-ribbon-role" id="ribbon-role">{_esc(ribbon.get("role", ""))}</span>
          </div>
        </div>"""


def chain_status_html(margin: str = "4px 0 10px") -> str:
    """The live chain-verification chip. r44: it retreats from the header to the
    domain's hash-chain evidence section — status next to the thing it attests.
    #chain-status is the id runtime.js renderChainStatus() hydrates."""
    return (
        '<div class="chain-status" id="chain-status" data-state="demo" role="status" aria-live="polite" '
        'title="Per A1 — SHA-256 hash-chained action log integrity, verified live in-browser" '
        f'style="margin:{_esc(margin)}">chain · loading…</div>'
    )


def _act_tabs_html(acts: List[Dict[str, Any]]) -> str:
    out = []
    for a in acts:
        pressed = "true" if a.get("pressed") else "false"
        out.append(
            f'<button class="act-tab" data-act="{_esc(a["id"])}" '
            f'aria-pressed="{pressed}" type="button">'
            f'<span class="act-tab-num">{_esc(a.get("num", ""))}</span>'
            f'<span class="act-tab-name">{_esc(a.get("name", ""))}</span>'
            f'<span class="act-tab-desc">{_esc(a.get("desc", ""))}</span>'
            "</button>"
        )
    return "\n    ".join(out)


# Shared modal markup — element IDs are the contract runtime.js binds to.
_MODALS_HTML = """
  <!-- lineage modal (shared) -->
  <div id="lineage-modal" class="lineage-modal" data-open="false" role="dialog" aria-modal="true" aria-labelledby="lineage-title">
    <div class="lineage-dialog">
      <div class="lineage-dialog-header">
        <div>
          <div id="lineage-title" class="lineage-dialog-title">Lineage</div>
          <div id="lineage-subtitle" class="lineage-dialog-subtitle"></div>
        </div>
        <button id="lineage-close-btn" class="lineage-close" type="button" aria-label="Close">ESC</button>
      </div>
      <div id="lineage-body"></div>
    </div>
  </div>

  <!-- verb confirm modal (shared) — named-human A8 gate lives in runtime.js -->
  <div id="verb-modal" class="verb-modal" data-open="false" role="dialog" aria-modal="true" aria-labelledby="verb-modal-title">
    <form id="verb-form" class="verb-dialog" onsubmit="return false;">
      <h3 id="verb-modal-title" class="verb-dialog-title">Confirm action</h3>
      <div id="verb-context" class="verb-field-hint" style="margin-bottom:var(--s-3); color:var(--text-muted)"></div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-actor">Named human (actor)</label>
        <input id="verb-actor" type="text" placeholder="e.g., D. Patel" autocomplete="off" />
        <div id="verb-actor-hint" class="verb-field-hint">Per A8 — name a person, not a team handle (e.g. D. Patel).</div>
      </div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-justification">Justification (≥12 words)</label>
        <textarea id="verb-justification" placeholder="Specific justification referencing the signal, the risk event, the control gap, and the treatment path being accepted or gated..."></textarea>
        <div id="verb-justification-hint" class="verb-field-hint" data-state="error">0 / 12 words · need 12 more</div>
      </div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-expiry">Expiry (required for gating / acceptance verbs)</label>
        <input id="verb-expiry" type="date" />
        <div class="verb-field-hint">Per A8 — actions without expiry become shelfware.</div>
      </div>
      <div class="verb-dialog-actions">
        <button id="verb-cancel-btn" type="button" class="verb-dialog-cancel">Cancel (ESC)</button>
        <button id="verb-confirm-btn" type="button" class="verb-dialog-confirm" disabled>Confirm</button>
      </div>
    </form>
  </div>
"""


def render_dashboard(
    projection_json: str,
    *,
    brand_mark: str,
    disclosure: str,
    acts: List[Dict[str, Any]],
    rail_html: str,
    stage_html: str,
    domain_js: str,
    footer_left: str,
    footer_right: str = "",
    footer_seal_signer: str = "",
    repo_url: str = "",
    body_lens: str = "engineer",
    body_act: str = "signal",
    body_domain: str = "all",
    schema_version: str = "1.0",
    artefact_label: str = "",
    title: str = "",
    extra_css: str = "",
    extra_head: str = "",
) -> str:
    """Assemble the full render-from-data dashboard HTML.

    The chrome (head/CSS, disclosure, brand-only header, act-tab nav, rail+stage
    layout, footer seal, the two modals, the embedded ``projection-source``
    script, and the shared runtime) is owned here. r44: the chrome renders NO
    identity — one navigation question at the top (the spine); the domain places
    ``signing_context_html`` next to its verb surface and ``chain_status_html``
    in its hash-chain section, and the footer keeps version chrome. The domain
    supplies ``rail_html`` + ``stage_html`` (sections carrying ``data-target``
    mount points) and ``domain_js`` (which defines ``window.PortfolioDomain``).
    Drift is structural-impossible: every visible value is populated by the
    runtime from the one embedded projection."""
    import json as _json
    try:
        _has_ia = bool(_json.loads(projection_json).get("ia"))
    except Exception:
        _has_ia = False

    css = dashboard_css()
    if extra_css:
        css = css + "\n\n" + extra_css
    runtime = runtime_js()
    flowfield = read_asset("flowfield.js")
    # Seal = SHA-256 over the embedded projection (the evidence payload). The
    # runtime recomputes this in-browser from #projection-source.textContent and
    # compares — so the seal is INDEPENDENTLY verifiable, not an unverifiable
    # footer string, and reproducible whenever the projection is reproducible.
    seal = hashlib.sha256(projection_json.strip().encode("utf-8")).hexdigest()

    pre_hash = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
<meta http-equiv="Pragma" content="no-cache" />
<meta http-equiv="Expires" content="0" />
<title>{_esc(title or brand_mark)}</title>
<style>{css}</style>
{extra_head}
<script type="application/json" id="projection-source" data-schema-version="{_esc(schema_version)}" data-artefact-version="{_esc(artefact_label)}">
{projection_json}
</script>
</head>
<body data-lens="{_esc(body_lens)}" data-act="{_esc(body_act)}" data-domain="{_esc(body_domain)}">

  <div class="disclosure">
    <span>{disclosure}</span>
  </div>

  <!-- ═══ Top chrome — brand + motion only. r44 (external review, verified on
       rac): the header ran TWO identity systems (persona chips + identity
       ribbon) plus chain + version chrome before a single number rendered.
       ONE navigation question at the top; the signing personas live where
       verbs are signed, the chain chip with the hash-chain evidence, and the
       footer keeps version. ═══ -->
  <header class="chrome">
    <h1 class="sr-only">{_esc(brand_mark)} — risk-as-code demonstrator</h1>
    <div class="brand">
      <span class="brand-mark">{_esc(brand_mark)}</span>
    </div>
    <div class="chrome-right">
      <button class="motion-toggle" id="motion-toggle" type="button" aria-pressed="false" title="Pause / resume motion (respects your reduced-motion setting)">⏸ motion</button>
    </div>
  </header>

  {('<nav class="spine" id="spine" aria-label="Argument spine — role-sequenced"></nav>'
     if _has_ia else
     f'<nav class="act-tabs" role="tablist" aria-label="Narrative acts">{_act_tabs_html(acts)}</nav>')}

  <div class="workspace">
    <aside class="rail" role="tablist" aria-label="{_esc(body_domain)}">
      {rail_html}
    </aside>
    <main class="panel">
      {stage_html}
    </main>
  </div>

  <footer class="foot">
    <span>{footer_left}</span>
    <span>{footer_right}</span>
    <span class="artefact-seal" title="Keyless SHA-256 checksum over the embedded projection JSON (the evidence payload) — NOT a cryptographic signature. Recompute it in-browser (verify ↪): proves the embedded projection is unmodified since seal-time and that rendering is deterministic from it (render-from-data). It does NOT attest authorship or authority, and the keyless hash does not prevent someone re-sealing modified data.">
      SHA-256 <code class="mono" id="artefact-seal-value">{seal}</code>
      <button id="verify-seal-btn" class="verify-projection-btn" type="button" title="Recompute the projection hash in-browser and compare to the seal.">verify ↪</button>
      <span id="seal-status" class="seal-status"></span>
      · <span class="generated-by">generated-by: {_esc(footer_seal_signer)}</span>
    </span>
    {f'<a href="{_esc(repo_url)}" target="_blank" rel="noopener" style="color:var(--interactive)">{_esc(repo_url)}</a>' if repo_url else ''}
  </footer>
{_MODALS_HTML}
  <script>{flowfield}</script>
  <script>{runtime}</script>
  <script>{domain_js}</script>
  {('<script>' + read_asset('ia_runtime.js') + '</script>') if _has_ia else ''}
</body>
</html>"""

    return pre_hash
