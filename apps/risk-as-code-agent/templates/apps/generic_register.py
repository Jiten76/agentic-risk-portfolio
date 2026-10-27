"""
Generic Register — v2.0a alpha4 skeleton.

JS reads the embedded projection on page load and populates: summary counts,
portfolio exposure cards, impact-face cards, materiality bar, findings table
(including coverage rows for green domains). Per the external reviewer:
render-from-data, not render-beside-data.

Per spec §5 + amendment A6 (honest collapse copy).
"""

from __future__ import annotations

import html
from typing import Dict, Any


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def render(projection: Dict[str, Any]) -> str:
    """Skeleton — JS populates everything from the embedded projection."""
    return """
    <article class="app-panel app-generic-register" data-app="generic_register" data-visible="false">

      <header class="app-header" data-app="generic_register">
        <div class="app-eyebrow">Generic register · all other domains</div>
        <h2 class="app-title">Risk register</h2>
        <p class="app-subtitle">
          The AI Governance application is the focus of this release. Other domains are served
          by the supporting risk register below; each will receive a dedicated application as
          model and agent governance has.
        </p>
      </header>

      <section class="register-summary">
        <div class="zone-eyebrow" data-target="register-summary-eyebrow">
          Period — · — findings · — domains
        </div>
        <div class="summary-row" data-target="register-summary-row">
          <!-- JS fills 4 stat blocks -->
        </div>
      </section>

      <!-- Portfolio exposure surfaced in Generic Register too -->
      <div class="zone-eyebrow">Portfolio exposure · expected loss (one distribution, three points)</div>
      <div class="register-exposure" data-target="register-exposure">
        <!-- JS fills 4 cards: P50 / P95 / Worst-anchor / RAG factors -->
      </div>

      <!-- Impact-face roll-ups for the 3 faces other than AI Gov's two -->
      <div class="zone-eyebrow">Impact faces · the 3 faces this register's roles act on (AI Gov surfaces regulatory + customer_trust)</div>
      <div class="register-exposure" data-target="register-impact-faces">
        <!-- JS fills 3 face cards: financial / operational / safety -->
      </div>

      <!-- Materiality bar — fired regulatory triggers across the register -->
      <section class="register-materiality" aria-labelledby="register-materiality-label">
        <div class="zone-eyebrow" id="register-materiality-label">Regulatory materiality · article-level disclosure triggers</div>
        <div class="materiality-row" data-target="register-materiality">
          <!-- JS fills materiality cells from proj.materiality -->
        </div>
      </section>

      <!-- Findings register -->
      <section class="register-findings" aria-labelledby="register-findings-label">
        <div class="zone-eyebrow" id="register-findings-label">Findings register · pattern × domain</div>
        <div class="register-note">
          Per amendment <strong>A2 (universal lineage)</strong>: synthesised signal
          values are suppressed in this view. Threshold sources and incident
          citations are real and viewable in the projection. Real values appear
          when telemetry is wired in a later release.
        </div>
        <table class="register-table">
          <thead>
            <tr>
              <th>RAG</th><th>ID</th><th>Pattern</th><th>Domain</th><th>NIST</th><th>First detected</th>
            </tr>
          </thead>
          <tbody data-target="register-tbody">
            <!-- JS fills rows from proj.domains[*].findings + coverage rows for green domains -->
          </tbody>
        </table>
      </section>

      <footer class="app-footer" data-target="app-footer-generic-register">
        <!-- JS fills with period + schema version + telemetry status -->
      </footer>

    </article>
    """
