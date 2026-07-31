"""
AI Governance Lead app — v2.0a alpha4.

The skeleton emits stable container IDs; JS reads the embedded projection
on page load and populates them. The prior alpha3 approach rendered the
queue + exposure + action log + impact summary server-side in Python and
ALSO embedded the projection in <script id="projection-source"> — meaning
the data lived in two places, reconciled by hand. The external reviewer
caught that the "drift cannot happen here" claim was an overclaim:
verification was checking that two parallel sources happened to agree.

Alpha4 fixes it. The structure below is a skeleton. The numbers, queue
items, action log entries, and impact summary cards all come from
proj.* read by the JS layer in utils/v2_html_report.py:_V2_SCRIPT_INJECT.

Per spec §4 and amendments A4 + A5 + A8 + A12.
"""

from __future__ import annotations

import html
from typing import Dict, Any


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def render(projection: Dict[str, Any]) -> str:
    """Skeleton — JS populates the dynamic content from the embedded projection."""
    # Use the projection only for things that must be in the static HTML for
    # accessibility / SEO / first-paint (the static h2 title + subtitle copy).
    # All numeric values + lists are JS-rendered.
    return """
    <article class="app-panel app-ai-gov" data-app="ai_gov" data-visible="true">

      <header class="app-header" data-app="ai_gov">
        <div class="app-eyebrow">AI Governance · model + agent oversight</div>
        <h2 class="app-title">AI Governance Lead</h2>
        <p class="app-subtitle">
          Gate models. Require evals. Restrict tool scope. Surface facts for the qualitative
          materiality determination — never assert the determination itself.
        </p>
      </header>

      <!-- Hero zone — Active Intervention Queue. JS-populated from
           proj.domains[*].findings filtered to RP-06 / RP-10 / RP-13. -->
      <section class="hero-zone intervention-queue" aria-labelledby="intervention-queue-label">
        <div class="zone-eyebrow" id="intervention-queue-label" data-target="queue-summary">
          Active Intervention Queue · loading…
        </div>
        <div class="queue-rows" data-target="queue-rows" tabindex="0" aria-label="Intervention queue, use j/k to navigate"></div>
      </section>

      <!-- Portfolio exposure — JS-populated from proj.exposure.portfolio_total -->
      <section class="hero-zone" aria-labelledby="hero-zone-label">
        <div class="zone-eyebrow" id="hero-zone-label">Portfolio exposure · expected loss + impact faces this app acts on</div>
        <div class="impact-summary" data-target="exposure-cards">
          <!-- JS fills 4 cards: Expected loss P50, Stress P95, Worst-anchor, EU AI Act status -->
        </div>
        <div class="impact-secondary" data-target="impact-secondary">
          <!-- JS fills the regulatory + customer_trust face sums -->
        </div>
      </section>

      <!-- v2.0a step 5: verb affordances + recent action log entries.
           JS reads proj.action_log.recent_entries + any localStorage entries. -->
      <section class="verb-zone" aria-labelledby="verb-zone-label">
        <div class="zone-eyebrow" id="verb-zone-label" data-target="verb-summary">
          Verb affordances · loading…
        </div>
        <div class="verb-bar" data-target="verb-bar">
          <!-- JS renders 6 verb buttons targeting MODEL-001 by default -->
        </div>
        <div class="action-log" data-target="action-log">
          <!-- JS renders entries — projection.action_log.recent_entries + localStorage -->
        </div>
      </section>

      <!-- Working surface — Model + Agent inventory (step 7 builds real data) -->
      <div class="working-surface">
        <section class="working-pane" aria-labelledby="model-inventory-label">
          <div class="zone-eyebrow" id="model-inventory-label">Model inventory · evals + guardrails</div>
          <div class="placeholder-card">
            <div class="placeholder-title">Model registry — step 7</div>
            <div class="placeholder-body">
              Inline verb chips on row hover: <code>Gate</code> · <code>Require eval</code> ·
              <code>Restrict scope</code>. Hover-card on every numeric value reveals
              <em>source query · timestamp · computation</em> (per A2 lineage).
            </div>
          </div>
        </section>

        <section class="working-pane" aria-labelledby="agent-inventory-label">
          <div class="zone-eyebrow" id="agent-inventory-label">Agent inventory · tool permissions + trace</div>
          <div class="placeholder-card">
            <div class="placeholder-title">Agent registry — step 7</div>
            <div class="placeholder-body">
              Per-agent MCP server connections, tool permissions, hash-pinning status,
              HITL gating, scope-violation count last 24h.
            </div>
          </div>
        </section>
      </div>

      <!-- Context rail -->
      <aside class="context-rail" aria-labelledby="context-rail-label">
        <div class="zone-eyebrow" id="context-rail-label">Context · supply chain + trace</div>
        <div class="placeholder-card placeholder-card-small">
          <div class="placeholder-title">MCP supply chain</div>
          <div class="placeholder-body">
            Connected MCP servers, KEV status, last security scan, hash-pinning compliance.
          </div>
        </div>
        <div class="placeholder-card placeholder-card-small">
          <div class="placeholder-title">Trace stream (live-tail)</div>
          <div class="placeholder-body">
            Last 24h agent action stream. Scope violations + prompt-injection
            attempts highlighted. Click any entry → projection lineage modal.
          </div>
        </div>
      </aside>

      <!-- Compliance footer (period + telemetry status read from projection by JS) -->
      <footer class="app-footer" data-target="app-footer-ai-gov">
        <!-- JS fills with period + schema version + telemetry status -->
      </footer>

    </article>
    """
