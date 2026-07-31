"""
v2_html_report — thin assembly for the v2.0a engine + apps.

This module replaces `utils/html_report.py` once v2.0a is feature-complete.
Until then, both coexist:
  - `utils/html_report.py`         — v1.3.1, locked, ships the council-passed dashboard.
  - `utils/v2_html_report.py`      — v2.0a, in progress per the build sequence.

`render_v2_report(report, history)`:
  1. Build the projection (the engine).
  2. Inline shared CSS + JS assets.
  3. Call each app's `render(projection)` to produce its panel.
  4. Assemble the panels behind a primary tab nav.
  5. Emit self-contained HTML.

Per `reviews/v2_0a_spec.md` §2 (engine/presentation split) and amendments
A4 / A12 (hierarchy + brand differentiation).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.history_synthesizer import generate_history
from utils.projection import make_projection, projection_summary, ARTEFACT_VERSION

# Each app exports render(projection) -> str
from templates.apps import ai_gov, generic_register


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


import os as _os, sys as _sys
_PC = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "..", "packages", "ui-system"))
if _PC not in _sys.path:
    _sys.path.insert(0, _PC)
from portfolio_core.presentation import warm_terminal_css as _warm_terminal_css


def _read_asset(filename: str) -> str:
    return (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")


def _scenario_map_from_report(report: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for did, dr in report.get("domain_reports", {}).items():
        snap = dr.get("snapshot", {})
        out[did] = snap.get("scenario", "normal")
    return out


# ── v2.0a-specific CSS additions (live alongside v1.3.1 tokens) ──────────────

# Warm-terminal CSS + M6 responsive — extracted to portfolio_core
# (port spec §15.E step 2a). Byte-identical; sourced once, shared by all
# portfolio projects. A style fix now lands in one place.
_V2_STYLE_INJECT = _warm_terminal_css()


_V2_SCRIPT_INJECT = """
// v2.0a alpha4 — render-from-data layer.
// JS reads the embedded projection on page load and populates every dynamic
// container marked data-target=. The Python server emits skeleton; JS does
// the rendering. No more "render beside the data" — drift becomes
// architecturally impossible because there is only one source.
//
// Plus: lineage modal, verb confirm modal,
// keyboard navigation (j/k/c/g/e/d), and localStorage verb persistence.

(function () {
  // ── Load embedded projection ──
  let PROJECTION = {};
  const projScript = document.getElementById('projection-source');
  if (projScript) {
    try { PROJECTION = JSON.parse(projScript.textContent || '{}'); }
    catch (e) { console.error('Failed to parse embedded projection:', e); }
  }

  // ── localStorage for verb confirmations (alpha4) ──
  // Per Grok review: "even client-side localStorage + re-render makes it feel alive."
  // Append-only, hash-chained continuation of the embedded action log.
  const LS_KEY = 'risk_as_code_action_log';
  function loadLocalActions() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
  }
  function saveLocalActions(entries) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(entries)); }
    catch (e) { console.warn('localStorage write failed:', e); }
  }
  async function sha256Hex(s) {
    const bytes = new TextEncoder().encode(s);
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  function getAllActionEntries() {
    const embedded = ((PROJECTION.action_log || {}).recent_entries) || [];
    const local = loadLocalActions();
    return embedded.concat(local);
  }

  // ── M4.5/B1 · canonical JSON matching Python json.dumps(sort_keys=True,
  //    default=str) — keys sorted recursively, ', ' + ': ' separators,
  //    ensure_ascii (non-ASCII → \\uXXXX). This must byte-match the Python
  //    _hash_entry() in utils/action_log.py or the recomputed hash won't agree.
  function _ensureAscii(str) {
    let out = '';
    for (const ch of str) {
      const code = ch.codePointAt(0);
      if (code >= 0x7f) {  // Python ensure_ascii escapes >= 0x7f (DEL included)
        if (code > 0xffff) {
          // surrogate pair
          const h = code - 0x10000;
          const hi = 0xd800 + (h >> 10);
          const lo = 0xdc00 + (h & 0x3ff);
          out += '\\\\u' + hi.toString(16).padStart(4, '0') + '\\\\u' + lo.toString(16).padStart(4, '0');
        } else {
          out += '\\\\u' + code.toString(16).padStart(4, '0');
        }
      } else {
        out += ch;
      }
    }
    return out;
  }
  function canonicalJson(obj) {
    if (obj === null || obj === undefined) return 'null';
    if (typeof obj === 'boolean') return obj ? 'true' : 'false';
    if (typeof obj === 'number') return String(obj);
    if (typeof obj === 'string') return _ensureAscii(JSON.stringify(obj));
    if (Array.isArray(obj)) return '[' + obj.map(canonicalJson).join(', ') + ']';
    if (typeof obj === 'object') {
      const keys = Object.keys(obj).sort();
      return '{' + keys.map((k) => _ensureAscii(JSON.stringify(k)) + ': ' + canonicalJson(obj[k])).join(', ') + '}';
    }
    return _ensureAscii(JSON.stringify(String(obj)));
  }

  // ── B1 · real chain verification (replaces the asserted "intact" string).
  //    Walks loaded entries (embedded recent_entries + localStorage):
  //    (1) content integrity — recompute SHA-256 of each entry minus
  //        this_action_hash, compare to stored;
  //    (2) link integrity — each entry's previous_action_hash equals the
  //        prior entry's this_action_hash within the loaded window.
  //    Honest about partial windows: the embedded projection carries only the
  //    last N entries, so genesis-to-head verification needs the full
  //    action_log.jsonl (server-side). We report what we can prove from here.
  async function verifyChain() {
    const entries = getAllActionEntries();
    if (!entries.length) {
      return { valid: true, verified: 0, total: 0, partial: false,
               note: 'no entries to verify' };
    }
    let contentOk = 0, linkOk = 0, brokenAt = null, reason = '';
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      // content integrity
      const eMinus = {};
      for (const k of Object.keys(e)) {
        if (k !== 'this_action_hash' && k !== '_local') eMinus[k] = e[k];
      }
      const recomputed = await sha256Hex(canonicalJson(eMinus));
      if (e.this_action_hash && recomputed === e.this_action_hash) {
        contentOk++;
      } else if (e.this_action_hash) {
        // Re-audit fix (Claude defect #3): no _local exemption. Write + verify
        // now hash symmetrically (canonicalJson, _local stripped on both sides),
        // so local entries verify on their own merits. Any mismatch is a real
        // content break, embedded or local.
        if (brokenAt === null) { brokenAt = i; reason = 'content hash mismatch at entry ' + i; }
      }
      // link integrity within window
      if (i > 0) {
        const prev = entries[i - 1];
        if (e.previous_action_hash && prev.this_action_hash &&
            e.previous_action_hash === prev.this_action_hash) {
          linkOk++;
        } else if (e.previous_action_hash && prev.this_action_hash) {
          if (brokenAt === null) { brokenAt = i; reason = 'link break: previous_action_hash != prior this_action_hash'; }
        }
      }
    }
    const firstLinksGenesis = (entries[0].previous_action_hash === 'GENESIS');
    const partial = !firstLinksGenesis;
    const valid = (brokenAt === null);
    return {
      valid, verified: contentOk, total: entries.length,
      links_ok: linkOk, partial, brokenAt, reason,
      note: partial
        ? 'window verified · full chain-to-genesis needs server-side action_log.jsonl'
        : 'full chain verified genesis→head',
    };
  }

  // ── Helpers ──
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function fmtUsd(n) {
    if (n == null || n === 0) return '0';
    const v = +n;
    if (Math.abs(v) >= 1e9)  return (v / 1e9).toFixed(1) + 'B';
    if (Math.abs(v) >= 1e6)  return (v / 1e6).toFixed(1) + 'M';
    if (Math.abs(v) >= 1e3)  return (v / 1e3).toFixed(0) + 'K';
    return v.toFixed(0);
  }
  function targets(name) {
    return document.querySelectorAll('[data-target="' + name + '"]');
  }
  function setTarget(name, html) {
    targets(name).forEach((el) => { el.innerHTML = html; });
  }

  // ── alpha4: render every dynamic surface from the projection ──
  function renderHero() {
    const meta = PROJECTION.meta || {};
    const counts = meta.counts || {};
    // (No JS hero headline needed — the Python skeleton has the static copy.)
    // The intervention queue + exposure cards live elsewhere; this just
    // sets the version label + counts in the topbar/footer if any are
    // marked with data-target.
    setTarget('topbar-version', esc(meta.artefact_version || ''));
    setTarget('footer-counts',
      esc('' + (counts.findings_total || 0) + ' findings · ' + (counts.domains_total || 0) + ' domains'));
  }

  function renderInterventionQueue() {
    const AI_PATTERNS = new Set(['RP-06', 'RP-10', 'RP-13']);
    const domains = PROJECTION.domains || {};
    const domFilter = activeDomain();
    const items = [];
    for (const did of Object.keys(domains)) {
      if (domFilter && did !== domFilter) continue;
      const dom = domains[did];
      for (const f of (dom.findings || [])) {
        if (AI_PATTERNS.has(f.pattern_id) && (f.overall_rag === 'red' || f.overall_rag === 'amber')) {
          items.push({
            finding_id:   f.finding_id,
            pattern_id:   f.pattern_id,
            pattern_name: f.pattern_name,
            domain_name:  (dom.domain_name || '').split(' &')[0],
            rag:          f.overall_rag,
            // first_detected is provenance-wrapped {value, provenance} (illustrative anchor)
            first_detected: fdVal(f.first_detected),
            time_in_state_days: f.time_in_state_days || 0,
            treatment_ticket: (f.treatment || {}).ticket || '—',
            owner_handle:     (f.treatment || {}).owner_handle || '',
            owner_kind:       (f.treatment || {}).owner_kind || '',
            model_id:     f.model_id || '',
            agent_id:     f.agent_id || '',
          });
        }
      }
    }
    items.sort((a, b) => {
      if (a.rag !== b.rag) return a.rag === 'red' ? -1 : 1;
      return (b.time_in_state_days || 0) - (a.time_in_state_days || 0);
    });

    const top = items.slice(0, 6);
    const summary =
      items.length + ' AI-relevant findings · ' +
      items.filter((i) => i.rag === 'red').length + ' red';
    // operator chrome rides in a role-tierable span: display:none for leadership
    // leaves textContent (and the conservation fingerprint) untouched.
    setTarget('queue-summary', 'Active Intervention Queue · ' + esc(domainLabel()) + ' · ' + esc(summary)
      + '<span class="kbd-hint"> · keyboard: j/k navigate · c claim · g gate · e escalate</span>');

    if (!top.length) {
      setTarget('queue-rows', '<div class="queue-empty">No AI-relevant findings '
        + (activeDomain() ? 'in <b>' + esc(activeDomain()) + '</b> — pick all_portfolio on the rail for the full queue.' : 'firing in this period. Queue clear.') + '</div>');
      return;
    }

    const html = top.map((item, idx) => {
      const days = item.time_in_state_days || 0;
      const slaTarget = item.rag === 'red' ? 30 : 90;
      const remaining = slaTarget - days;
      const state = remaining < 0 ? 'overdue' : (remaining < 7 ? 'warning' : 'ok');
      const slaText = remaining < 0 ? (Math.abs(remaining) + 'd overdue') : (remaining + 'd remaining');
      return '<div class="queue-item" data-rag="' + esc(item.rag) + '" data-sla="' + esc(state) +
             '" data-queue-idx="' + idx + '" tabindex="0">' +
        '<div class="queue-rag-col"><span class="rag-tag" data-rag="' + esc(item.rag) + '">' + esc(item.rag.toUpperCase()) + '</span></div>' +
        '<div class="queue-id-col">' +
          '<div class="queue-pid">' + esc(item.pattern_id) + '</div>' +
          '<div class="queue-pname">' + esc(item.pattern_name) + ' · ' + esc(item.domain_name) +
            (item.model_id ? ' · <span style="color:var(--signal)" title="linked AI model">⊳ ' + esc(item.model_id) + '</span>' : '') +
            (item.agent_id ? ' · <span style="color:var(--insight)" title="linked agent">⊳ ' + esc(item.agent_id) + '</span>' : '') +
          '</div>' +
        '</div>' +
        '<div class="queue-sla-col">' +
          '<div class="queue-sla" data-state="' + esc(state) + '">' + esc(slaText) + '</div>' +
          '<div class="queue-meta">first detected ' + esc(item.first_detected) + ' · ' + days + 'd in state</div>' +
        '</div>' +
        '<div class="queue-treatment-col">' +
          '<div class="queue-ticket">' + esc(item.treatment_ticket) + '</div>' +
          '<div class="queue-owner">' + esc(item.owner_handle) + (item.owner_kind ? ' <span class="illustrative-tag" title="' + esc(item.owner_kind) + '">team handle</span>' : '') + '</div>' +
        '</div>' +
        '<div class="queue-actions-col">' +
          '<button class="queue-claim-btn verb-btn" data-verb="claim" data-target-id="' + esc(item.finding_id) +
            '" data-target-name="' + esc(item.pattern_id + ' · ' + item.domain_name) +
            '" data-target-type="finding">claim</button>' +
          '<button class="queue-gate-btn verb-btn" data-verb="gate" data-target-id="' + esc(item.finding_id) +
            '" data-target-name="' + esc(item.pattern_id + ' · ' + item.domain_name) +
            '" data-target-type="finding">gate</button>' +
        '</div>' +
      '</div>';
    }).join('');
    setTarget('queue-rows', html);
  }

  function renderExposureCards() {
    const ex = ((PROJECTION.exposure || {}).portfolio_total) || {};
    const provenance = ex.provenance || {};
    const worst = ex.worst_anchor_top || {};
    const materiality = PROJECTION.materiality || {};
    const euAi = materiality.eu_ai_act_high_risk || {};
    const triggered = euAi.triggered_patterns || [];

    const provJson = (p) => esc(JSON.stringify(p || {}));

    const worstProv = {
      source_status: 'illustrative',
      source_system: 'data/risk_patterns.json::exposure_model::severity_distribution',
      source_query: 'top firing pattern ' + (worst.pattern_id || '?') + '::worst_anchor_usd',
      computation: 'Largest worst-anchor across firing patterns: ' + (worst.worst_anchor_basis || '') + '. NOT in headline per A7 — proper noun dominates the eye; click to see basis.',
      assumptions: ['Worst-anchor is a single cited comparable, not a forecast.'],
    };

    const cards = [];
    cards.push('<div class="impact-card" data-rag="red">' +
      '<div class="impact-label">Expected loss (P50)</div>' +
      '<div class="impact-number"><span class="lineage-link" data-prov="' + provJson(provenance) + '" data-label="Portfolio expected loss P50">$' + fmtUsd(ex.p50_usd) + '</span></div>' +
      '<div class="impact-detail">portfolio P50 · click for derivation</div>' +
    '</div>');
    cards.push('<div class="impact-card" data-rag="amber">' +
      '<div class="impact-label">Stress (P95)</div>' +
      '<div class="impact-number"><span class="lineage-link" data-prov="' + provJson(provenance) + '" data-label="Portfolio stress P95">$' + fmtUsd(ex.p95_usd) + '</span></div>' +
      '<div class="impact-detail">bad-year scenario · click for derivation</div>' +
    '</div>');
    cards.push('<div class="impact-card">' +
      '<div class="impact-label">Worst-anchor (top firing pattern)</div>' +
      '<div class="impact-number"><span class="lineage-link" data-prov="' + provJson(worstProv) + '" data-label="Worst-anchor">$' + fmtUsd(worst.worst_anchor_usd) + '</span></div>' +
      '<div class="impact-detail">' + (worst.pattern_id ? '<b>' + esc(worst.pattern_id) + '</b> · ' : '') + esc((worst.worst_anchor_basis || 'No anchor').slice(0, 52)) + ((worst.worst_anchor_basis || '').length > 52 ? '...' : '') + '</div>' +
    '</div>');
    cards.push('<div class="impact-card" data-rag="' + (triggered.length ? 'red' : 'green') + '">' +
      '<div class="impact-label">EU AI Act</div>' +
      '<div class="impact-number"><span class="lineage-link" data-prov="' + provJson(euAi.provenance || {}) + '" data-label="EU AI Act high-risk status">' + (triggered.length ? 'TRIGGERED' : 'CLEAR') + '</span></div>' +
      '<div class="impact-detail">' + (triggered.length ? esc(triggered.join(', ') + ' triggering this obligation') : 'No high-risk system findings') + '</div>' +
    '</div>');
    const calib = '<div class="exposure-calibration" style="grid-column:1/-1; margin-top:14px; font-size:var(--t-caption); color:var(--text-mut); line-height:1.6; border-top:1px solid var(--border); padding-top:11px">'
      + '<b style="color:var(--text)">Calibration basis</b> — an <b>illustrative seeded Monte-Carlo</b> (Poisson frequency × lognormal severity, <b>with one-generation cascade propagation</b> along the declared cascade edges — the loss engine honors the same dependency graph the cascade panel shows, and reports the independence counterfactual alongside), <b>not a fitted loss history</b>. '
      + 'Per-pattern frequencies are calibrated to a large US consumer/crypto fintech archetype — <b>operator judgment, not a sourced peer study</b> (each pattern carries its own derivation in <code>data/risk_patterns.json::exposure_model</code>); severities are anchored to <b>public breach events</b> (e.g. Equifax $700M); control effectiveness is self-assessed with an independent-validation haircut; cascade induction probabilities are operator-calibrated. '
      + '<b>Two disclosed model limitations:</b> propagation truncates at one generation — stable, but it <b>understates the tail</b> (the "Cascade generations 2" lever below shows the cost, ~+10% at P95); and severity co-movement enters the headline ONLY through the common-cause term (γ per active structural-loss year — see <code>severity_comovement</code>, off-lever priced) — the BLANKET common shock stays excluded (σ=0) and the "Severity common shock" lever below prices that remaining omission (~+9% at P95) instead of leaving it as prose. '
      + 'A production model would fit the firm’s own loss history and back-test these parameters — this demonstrator does not claim that, and the numbers are labelled illustrative throughout.</div>';
    setTarget('exposure-cards', cards.join('') + calib);
  }

  // ── IMPACT/DECIDE · calibration appendix — sensitivity tornado + basis table ──
  // Round-5 P0 (both external reviewers): "calibration is narrative, not evidence."
  // Every number here is hydrated from PROJECTION.sensitivity — seeded engine re-runs,
  // one calibration judgment shocked per lever. No value is computed in this layer.
  function renderSensitivity() {
    const s = PROJECTION.sensitivity || {};
    const base = s.baseline || {};
    const levers = s.levers || [];
    const table = s.calibration_table || [];
    if (!levers.length) { setTarget('sensitivity-panel', '<div class="impact-detail">no sensitivity block in projection</div>'); return; }

    const lo = Math.min.apply(null, levers.map(l => l.residual_p95).concat([base.residual_p95]));
    const hi = Math.max.apply(null, levers.map(l => l.residual_p95).concat([base.residual_p95]));
    const maxAbs = Math.max.apply(null, levers.map(l => Math.abs(l.delta_p95)));

    // headline — the at-a-glance insight, before any bar is read
    const se = ((PROJECTION.exposure || {}).portfolio_total || {}).sampling_error || {};
    const ci = se.residual_p95_ci95 || [];
    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:4px">'
      + 'If a calibration judgment is wrong, stress P95 spans <b>$' + fmtUsd(lo) + ' – $' + fmtUsd(hi) + '</b>'
      + ' around the <b>$' + fmtUsd(base.residual_p95) + '</b> headline'
      + (ci.length === 2 ? ' <span style="font-size:var(--t-caption); color:var(--text-mut)" title="' + esc(se.note || '') + '">(MC sampling error: P95 $' + fmtUsd(ci[0]) + '–$' + fmtUsd(ci[1]) + ')</span>' : '')
      + ' <span class="illustrative-tag">seeded re-runs · ' + (base.trials || 0).toLocaleString() + ' trials each</span></div>'
      + '<div style="font-size:var(--t-caption); color:var(--text-mut); margin-bottom:12px">one judgment shocked per lever, everything else held · sorted by impact — the top bar is the judgment most worth challenging</div>';

    // tornado — center axis = headline; left = decrease (green), right = increase (red)
    html += '<div role="img" aria-label="Sensitivity tornado: portfolio residual P95 under each single-judgment shock">';
    levers.forEach(function (l) {
      const w = maxAbs ? Math.round(Math.abs(l.delta_p95) / maxAbs * 100) : 0;
      const up = l.delta_p95 >= 0;
      html += '<div style="display:flex; align-items:center; gap:10px; margin:5px 0; font-size:var(--t-caption)">'
        + '<div style="flex:0 0 218px; text-align:right; color:var(--text-mut)">' + esc(l.label) + '</div>'
        + '<div style="flex:1; display:flex; min-width:120px">'
        +   '<div style="flex:1; display:flex; justify-content:flex-end">'
        +     (!up ? '<div style="width:' + w + '%; min-width:2px; height:13px; border-radius:3px 0 0 3px; background:var(--green); opacity:.75"></div>' : '')
        +   '</div>'
        +   '<div style="width:1px; background:var(--border)"></div>'
        +   '<div style="flex:1; display:flex">'
        +     (up ? '<div style="width:' + w + '%; min-width:2px; height:13px; border-radius:0 3px 3px 0; background:var(--red); opacity:.75"></div>' : '')
        +   '</div>'
        + '</div>'
        + '<div style="flex:0 0 150px; font-family:var(--font-mono); color:var(--text)">$' + fmtUsd(l.residual_p95)
        +   ' <span style="color:' + (up ? 'var(--red)' : 'var(--green)') + '">' + (up ? '+' : '') + l.delta_p95_pct + '%</span></div>'
        + '</div>';
    });
    html += '</div>';

    // moderate-vs-fat-tail call-out — the σ choice priced as data, not buried in
    // the judgment log (round-12 external ask). Rendered from sev_shock_sweep.
    const sweep = (s.sev_shock_sweep || {}).points || [];
    if (sweep.length) {
      html += '<div style="margin-top:10px; padding:9px 14px; border:1px solid var(--border); border-left:3px solid var(--amber); border-radius:8px; font-size:var(--t-caption); line-height:1.55">'
        + '<b style="color:var(--text)">Severity co-movement, priced:</b> '
        + sweep.map(function (pt) {
            return '<span style="font-family:var(--font-mono); color:var(--text)">σ=' + pt.sigma + ' → $' + fmtUsd(pt.residual_p95)
              + ' <span style="color:var(--red)">+' + pt.delta_p95_pct + '%</span></span>';
          }).join(' · ')
        + '<div style="color:var(--text-mut); margin-top:4px">' + esc((s.sev_shock_sweep || {}).note || '') + '</div>'
        + '</div>';
    }

    // calibration table — progressive disclosure; the per-pattern evidence in one place
    html += '<details style="margin-top:14px"><summary style="cursor:pointer; font-size:var(--t-caption); color:var(--text-mut)">calibration basis · per-pattern frequency judgment, severity anchors, control effectiveness (' + table.length + ' patterns)</summary>'
      + '<div style="margin-top:8px; font-size:var(--t-micro); color:var(--text-mut)">r29 re-anchor: every severity median cites a named reference — IBM Cost of a Data Breach 2024 · Uptime Institute outage-cost 2023 · ITIC hourly-cost 2024 — with p95/p50 held near the Basel/ORX severity band; the full per-pattern basis is on each severity cell (hover) and in <span style="font-family:var(--font-mono)">data/risk_patterns.json</span>. Industry-decade catastrophes stay in the worst-anchor column, not inside the medians.</div>' 
      + '<div style="overflow-x:auto"><table style="width:100%; border-collapse:collapse; margin-top:9px; font-size:var(--t-micro); font-family:var(--font-mono)">'
      + '<thead><tr style="color:var(--text-mut); text-align:left">'
      + '<th style="padding:4px 8px">pattern</th><th style="padding:4px 8px">freq/yr p50·p95</th><th style="padding:4px 8px">severity p50·p95</th><th style="padding:4px 8px">worst anchor (cited public event)</th><th style="padding:4px 8px">ctrl eff</th><th style="padding:4px 8px">edges→</th>'
      + '</tr></thead><tbody>';
    table.forEach(function (r) {
      html += '<tr style="border-top:1px solid var(--border)">'
        + '<td style="padding:4px 8px; color:var(--text)">' + esc(r.pattern_id) + '</td>'
        + '<td style="padding:4px 8px" title="' + esc(r.freq_basis || '') + '">' + r.freq_p50 + ' · ' + r.freq_p95 + ' <span class="illustrative-tag">judgment</span></td>'
        + '<td style="padding:4px 8px" title="' + esc(r.sev_basis || '') + '">$' + fmtUsd(r.sev_p50_usd) + ' · $' + fmtUsd(r.sev_p95_usd) + (r.sev_basis ? ' <span class="illustrative-tag" title="' + esc(r.sev_basis) + '">r29 basis</span>' : '') + '</td>' 
        + '<td style="padding:4px 8px; color:var(--text-mut)">$' + fmtUsd(r.worst_anchor_usd) + ' — ' + esc(r.worst_anchor_basis) + '</td>'
        + '<td style="padding:4px 8px">' + r.controls_eff_pct + '%</td>'
        + '<td style="padding:4px 8px">' + r.cascade_out_edges + '</td>'
        + '</tr>';
    });
    html += '</tbody></table></div></details>';

    // ── control test-evidence schema — the structure behind the biggest lever.
    // Illustrative by construction (no real control tests exist to cite); credited
    // percentages reconcile to the avg_effectiveness_pct the MC consumes (C22).
    const evRows = [];
    table.forEach(function (r) {
      ((r.control_evidence || {}).controls || []).forEach(function (c) { evRows.push({ pid: r.pattern_id, c: c }); });
    });
    if (evRows.length) {
      const evNote = ((table[0] || {}).control_evidence || {}).note || '';
      html += '<details style="margin-top:10px"><summary style="cursor:pointer; font-size:var(--t-caption); color:var(--text-mut)">control test evidence · illustrative schema — method · date · credited vs self-assessed (' + evRows.length + ' controls)</summary>'
        + '<div style="font-size:var(--t-micro); color:var(--text-faint); margin:8px 0 4px; line-height:1.5">' + esc(evNote) + '</div>'
        + '<div style="overflow-x:auto"><table style="width:100%; border-collapse:collapse; margin-top:5px; font-size:var(--t-micro); font-family:var(--font-mono)">'
        + '<thead><tr style="color:var(--text-mut); text-align:left">'
        + '<th style="padding:4px 8px">pattern</th><th style="padding:4px 8px">control</th><th style="padding:4px 8px">self → credited</th><th style="padding:4px 8px">method</th><th style="padding:4px 8px">last tested</th><th style="padding:4px 8px">ref</th>'
        + '</tr></thead><tbody>';
      let covSplit = 0;
      evRows.forEach(function (row) {
        const c = row.c;
        const gap = !c.last_tested;
        // coverage-stat controls declare the split inline ("(coverage) — but…");
        // surface it as a chip so the C24 discipline lives in the pixels too
        const isCov = /[(](coverage|completion|attestation)[^)]*[)]/.test(c.basis || '');
        if (isCov) covSplit++;
        html += '<tr style="border-top:1px solid var(--border)' + (gap ? '; opacity:.55' : '') + '">'
          + '<td style="padding:4px 8px; color:var(--text)">' + esc(row.pid) + '</td>'
          + '<td style="padding:4px 8px; color:var(--text-mut)" title="' + esc(c.basis || c.result || '') + '">' + esc(c.name)
          +   (isCov ? ' <span style="font-size:var(--t-micro); color:var(--amber); border:1px solid var(--amber); border-radius:4px; padding:0 4px; opacity:.8" title="' + esc(c.basis || '') + '">coverage stat — credit discounted</span>' : '')
          + '</td>'
          + '<td style="padding:4px 8px">' + (gap ? '—' : c.self_assessed_pct + '% → <b>' + c.credited_pct + '%</b>') + '</td>'
          + '<td style="padding:4px 8px; color:var(--text-mut)">' + esc(c.method || '—') + '</td>'
          + '<td style="padding:4px 8px">' + esc(c.last_tested || 'not tested') + '</td>'
          + '<td style="padding:4px 8px; color:var(--text-mut)">' + esc(c.evidence_ref || '—') + '</td>'
          + '</tr>';
      });
      html += '</tbody></table></div>'
        + '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:6px; line-height:1.5">'
        + covSplit + ' of ' + evRows.length + ' controls are measured by a coverage/completion stat — each basis states what the stat does <b>not</b> prove (hover a chip). '
        + 'Enforced, not editorial: audit gates C24.1–C24.4 fail the build on any coverage-language basis without an effectiveness rationale, and on any credit ≥90 without one.</div>'
        + '</details>';
    }

    // ── "How a 2LoD would challenge this" — every judgment invites its question,
    // and each question names the lever (or the disclosed gap) that answers it.
    const jlog = s.judgment_log || [];
    if (jlog.length) {
      html += '<div style="margin-top:14px; border:1px solid var(--border); border-left:3px solid var(--signal); border-radius:8px; padding:12px 16px">'
        + '<div style="font-size:var(--t-caption); color:var(--text); font-weight:600; margin-bottom:8px">How a 2LoD would challenge this</div>';
      jlog.forEach(function (j) {
        html += '<div style="margin:7px 0; font-size:var(--t-caption); line-height:1.55">'
          + '<span style="color:var(--text)">&ldquo;' + esc(j.challenge) + '&rdquo;</span><br>'
          + '<span style="color:var(--text-mut)">↳ ' + esc(j.answers_with) + '</span>'
          + '</div>';
      });
      html += '</div>';

      // judgment log — who set each judgment, when, on what basis (progressive disclosure)
      html += '<details style="margin-top:10px"><summary style="cursor:pointer; font-size:var(--t-caption); color:var(--text-mut)">judgment log · who set each calibration judgment, when, on what basis (' + jlog.length + ' entries)</summary>'
        + '<div style="overflow-x:auto"><table style="width:100%; border-collapse:collapse; margin-top:9px; font-size:var(--t-micro)">'
        + '<thead><tr style="color:var(--text-mut); text-align:left; font-family:var(--font-mono)">'
        + '<th style="padding:4px 8px">judgment</th><th style="padding:4px 8px">set by · when</th><th style="padding:4px 8px">basis</th></tr></thead><tbody>';
      jlog.forEach(function (j) {
        html += '<tr style="border-top:1px solid var(--border); vertical-align:top">'
          + '<td style="padding:5px 8px; color:var(--text)">' + esc(j.judgment) + '</td>'
          + '<td style="padding:5px 8px; font-family:var(--font-mono); color:var(--text-mut); white-space:nowrap">' + esc(j.set_by) + '<br>' + esc(j.set_at) + '</td>'
          + '<td style="padding:5px 8px; color:var(--text-mut)">' + esc(j.basis) + '</td>'
          + '</tr>';
      });
      html += '</tbody></table></div></details>';
    }

    // method note — honest about what OAT does and does not capture
    html += '<div style="margin-top:10px; font-size:var(--t-micro); color:var(--text-faint); line-height:1.5">' + esc(s.method_note || '') + '</div>';

    setTarget('sensitivity-panel', html);
  }

  // ── IMPACT/DECIDE · regulatory residual — the Legal/CRO view ─────────────────
  // "How much of our residual $ already sits in a disclosure regime?" Same trial
  // matrix as the headline; within-trial subset sums per regulation. The naive
  // Σ-of-P95s ships alongside as the anti-example (percentiles do not add).
  let regBindingOnly = false;  // round-12: applicability as a FILTER, not just a flag
  let perimeterId = null;      // round-17: declared charter (null = projection default)
  function renderRegulationResidual() {
    const rr = PROJECTION.regulation_residual || {};
    const allRows = rr.by_regulation || [];
    if (!allRows.length) { setTarget('regulation-residual', '<div class="impact-detail">no regulation_residual block</div>'); return; }
    const isCaveat = function (r) { return /ILLUSTRATIVE|contractual/.test(r.applicability || ''); };
    const binding = allRows.filter(function (r) { return !isCaveat(r); });
    const rows = regBindingOnly ? binding : allRows;
    const port = rr.portfolio_residual_p95 || 0;
    const top = allRows[0];
    // round-26 (external, Claude — MODERATE: "the control re-scopes the data;
    // the sentence doesn't"): the conclusion line is now STATE-AWARE. Under a
    // non-default charter it re-derives from that profile's own leaves; the
    // default state renders byte-identical to the acknowledged fingerprint.
    const ppSel = rr.perimeter_profiles || {};
    const selProf = (perimeterId && perimeterId !== ppSel.default)
      ? ((ppSel.profiles || []).filter(function (x) { return x.profile_id === perimeterId; })[0] || null)
      : null;

    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:4px">'
      + (selProf
        ? '<b>' + selProf.share_of_portfolio_p95_pct + '%</b> of portfolio stress-P95 sits in the <b>' + esc(selProf.label) + '</b> perimeter'
          + ' — $' + fmtUsd(selProf.in_perimeter_residual_p95) + ' across ' + selProf.in_perimeter_regs.length + ' regimes (union subset, same trials)'
          + ' · the table below stays portfolio-wide'
        : '<b>' + top.share_of_portfolio_p95_pct + '%</b> of portfolio stress-P95 sits under ' + esc((top.citation || top.reg_id).split(' §')[0])
          + (allRows[1] ? ' · <b>' + allRows[1].share_of_portfolio_p95_pct + '%</b> under ' + esc((allRows[1].citation || allRows[1].reg_id).split(' Item')[0]) : ''))
      + ' <span class="illustrative-tag">same seeded MC · subset quantiles</span></div>'
      + '<div style="font-size:var(--t-caption); color:var(--text-mut); margin-bottom:12px">regulations overlap — a pattern can trigger several, so rows do not sum to the portfolio ($' + fmtUsd(port) + ' P95) · every row carries a first-class <b>applies?</b> flag — <span style="color:var(--amber)">amber</span> marks style-mappings and contractual regimes, not binding statutes · '
      + '<button data-target="reg-filter-toggle" style="font:inherit; font-size:var(--t-micro); color:var(--text); background:var(--surface-3); border:1px solid var(--border); border-radius:5px; padding:1px 8px; cursor:pointer">'
      +   (regBindingOnly ? 'showing binding/licence-scoped only (' + binding.length + ') — show all ' + allRows.length : 'show binding/licence-scoped only (' + binding.length + ' of ' + allRows.length + ')')
      + '</button></div>';

    rows.forEach(function (r) {
      const w = Math.min(100, r.share_of_portfolio_p95_pct);
      html += '<div style="margin:8px 0">'
        + '<div style="display:flex; gap:10px; align-items:baseline; font-size:var(--t-caption)">'
        +   '<span style="font-family:var(--font-mono); color:var(--text); flex:0 0 175px">' + esc(r.reg_id) + '</span>'
        +   '<span style="color:var(--text-mut); flex:1">' + esc(r.citation) + ' · ' + r.patterns.length + ' pattern' + (r.patterns.length > 1 ? 's' : '') + '</span>'
        +   '<span style="font-family:var(--font-mono); color:var(--text)">$' + fmtUsd(r.residual_p95) + ' <span style="color:var(--text-mut)">(' + r.share_of_portfolio_p95_pct + '%)</span></span>'
        + '</div>'
        + '<div style="height:11px; background:var(--surface-3); border-radius:3px; margin-top:3px; overflow:hidden">'
        +   '<div style="width:' + w + '%; height:100%; background:var(--amber); opacity:.7"></div>'
        + '</div>'
        + (r.applicability
            ? '<div style="font-size:var(--t-micro); color:' + (/ILLUSTRATIVE|contractual/.test(r.applicability) ? 'var(--amber)' : 'var(--text-faint)') + '; margin-top:2px">applies? ' + esc(r.applicability) + '</div>'
            : '')
        + (r.patterns.length > 1
            ? '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:2px">naive Σ of per-pattern P95s would claim $' + fmtUsd(r.naive_percentile_sum_p95) + ' — percentiles do not add; the subset quantile is the honest number</div>'
            : '')
        + '</div>';
    });
    // round-17 examiner persona ("a toggle is not proof of re-mapping logic"):
    // the DECLARED-charter view. All profile-specific content — including the
    // re-mapped dollars — lives inside a nested [data-target] so the parent
    // fingerprint stays byte-stable (own-text rule); the dollars themselves are
    // union subset sums computed in the projection, never derived in render.
    const pp = rr.perimeter_profiles || {};
    const profs = pp.profiles || [];
    if (profs.length) {
      const cur = profs.filter(function (x) { return x.profile_id === (perimeterId || pp.default); })[0] || profs[0];
      html += '<div style="margin-top:14px; padding-top:10px; border-top:1px solid var(--border)">'
        + '<span style="font-size:var(--t-caption); color:var(--text-mut)">viewing perimeter as </span>'
        + '<select data-target="perimeter-sel" style="font:inherit; font-size:var(--t-micro); color:var(--text); background:var(--surface-3); border:1px solid var(--border); border-radius:5px; padding:2px 6px">'
        + profs.map(function (x) { return '<option value="' + esc(x.profile_id) + '"' + (x.profile_id === cur.profile_id ? ' selected' : '') + '>' + esc(x.label) + '</option>'; }).join('')
        + '</select>'
        + '<div data-target="perimeter-summary" style="margin-top:8px; font-size:var(--t-caption); color:var(--text); line-height:1.6">'
        +   'in-perimeter residual <b>$' + fmtUsd(cur.in_perimeter_residual_p95) + '</b> · <b>' + cur.share_of_portfolio_p95_pct + '%</b> of portfolio stress-P95 · '
        +   cur.in_perimeter_regs.length + ' regimes over ' + cur.in_perimeter_patterns.length + ' patterns (union subset sum, same trial matrix)'
        +   '<div style="font-size:var(--t-micro); color:var(--text-mut); margin-top:3px">'
        +     Object.keys(cur.statuses).map(function (rid) { return esc(rid) + ': ' + esc(cur.statuses[rid]); }).join(' · ')
        +   '</div>'
        +   '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:3px">' + esc(cur.note) + '</div>'
        +   '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:2px">' + esc(pp.method_note || '') + '</div>'
        + '</div></div>';
    }
    html += '<div style="margin-top:10px; font-size:var(--t-micro); color:var(--text-faint); line-height:1.5">' + esc(rr.source_note || rr.method_note || '') + '</div>';
    setTarget('regulation-residual', html);
    const tgl = document.querySelector('[data-target="reg-filter-toggle"]');
    if (tgl) tgl.addEventListener('click', function () { regBindingOnly = !regBindingOnly; renderRegulationResidual(); });
    const psel = document.querySelector('[data-target="perimeter-sel"]');
    if (psel) psel.addEventListener('change', function () { perimeterId = this.value; renderRegulationResidual(); });
  }

  // ── ATTEST · internal audit posture — the 3LoD lifecycle register ─────────────
  // Round-8 depth pass: the attest act verified hash chains but had no audit SHOP
  // in it. This renders the illustrative issue register with the states that make
  // audit real: management responses, target dates (one re-baselined, one PAST
  // DUE), validation-pending, a clean re-tested closure, a REPEAT finding, and an
  // exam-style (MRA-analog) regulator-visible item.
  function renderInternalAudit() {
    const ia = PROJECTION.internal_audit || {};
    const issues = ia.issues || [];
    if (!issues.length) { setTarget('internal-audit', '<div class="impact-detail">no internal_audit block</div>'); return; }
    const c = ia.counts || {};
    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:4px">'
      + '<b>' + (c.open || 0) + '</b> open issues · <b>' + (c.past_due || 0) + '</b> past due · <b>' + (c.repeat || 0) + '</b> repeat · <b>' + (c.regulator_visible || 0) + '</b> regulator-visible'
      + ' <span class="illustrative-tag" title="' + esc(ia.source_note || '') + '">illustrative register</span></div>'
      + '<div style="font-size:var(--t-caption); color:var(--text-mut); margin-bottom:10px">repeat findings and missed regulator dates are what examiners actually punish — the register carries both states on purpose</div>';
    issues.forEach(function (iss) {
      const pastDue = /PAST DUE/.test(iss.status);
      const closed = /^CLOSED/.test(iss.status);
      html += '<div style="padding:8px 12px; margin:6px 0; border:1px solid var(--border); border-left:3px solid ' + (pastDue ? 'var(--red)' : closed ? 'var(--green)' : 'var(--amber)') + '; border-radius:8px; opacity:' + (closed ? '.75' : '1') + '">'
        + '<div style="display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; font-size:var(--t-caption)">'
        + '<span style="font-family:var(--font-mono); color:var(--text)">' + esc(iss.issue_id) + '</span>'
        + '<span style="font-family:var(--font-mono); color:var(--text-faint)">' + esc(iss.pattern_id) + ' · ' + esc(iss.severity) + '</span>'
        + '<span style="flex:1; color:var(--text)">' + esc(iss.title) + '</span>'
        + (iss.repeat_finding ? '<span style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--red); border:1px solid var(--border); border-radius:4px; padding:1px 7px">REPEAT</span>' : '')
        + '<span style="font-family:var(--font-mono); font-size:var(--t-micro); color:' + (pastDue ? 'var(--red)' : 'var(--text-mut)') + '">' + esc(iss.status) + '</span>'
        + '</div>'
        + '<div style="margin-top:4px; font-size:var(--t-micro); color:var(--text-mut); line-height:1.5">'
        + '<span style="color:var(--text-faint)">raised</span> ' + esc(iss.raised) + ' · ' + esc(iss.source)
        + ' · <span style="color:var(--text-faint)">response:</span> ' + esc(iss.management_response)
        + ' · <span style="color:var(--text-faint)">target:</span> ' + esc(iss.target_date)
        + (iss.note ? '<br><span style="color:var(--text-faint)">↳ ' + esc(iss.note) + '</span>' : '')
        + '</div></div>';
    });
    setTarget('internal-audit', html);
  }

  // ── DECIDE · the Monday-morning screen ───────────────────────────────────────
  // Round-8 human review: "can we truly force decisions???" No. 2LoD's actual
  // levers are: table the item at the right committee, log a formal challenge,
  // decline to counter-sign the next acceptance renewal, or escalate to the CRO —
  // and each spends political capital. This screen now says WHERE each decision
  // actually gets made, WHO is accountable by name, WHY it is really stalled
  // (competing exec commitments, budget freezes, reorgs — from org_context,
  // illustrative), and what the escalation costs. Pure composition of projection
  // data — no number computed here that doesn't already live in the projection.
  function renderMondayMorning() {
    const domains = PROJECTION.domains || {};
    const mats = PROJECTION.materiality || {};
    const irBy = {};
    ((PROJECTION.inherent_residual || {}).by_pattern || []).forEach(function (r) {
      irBy[r.pattern_id] = (r.residual || {}).p95 || 0;
    });
    // reverse map: pattern → short regulation cites. † carries the applicability
    // caveat through to the docket — a style-mapping or contractual regime must
    // not read as a binding statute on the decision screen either.
    const regsFor = {};
    let anyCaveat = false;
    Object.keys(mats).forEach(function (rid) {
      const blk = mats[rid] || {};
      const caveat = /ILLUSTRATIVE|contractual/.test(blk.applicability || '');
      if (caveat) anyCaveat = true;
      (blk.triggered_patterns || blk.conditional_patterns || []).forEach(function (pid) {
        (regsFor[pid] = regsFor[pid] || []).push((REG_SHORT[rid] || (blk.regulation_citation || rid).split(' ')[0]) + (caveat ? '†' : ''));
      });
    });
    // candidate decisions: red findings ranked by residual P95 (rail-scoped)
    const mmDomFilter = activeDomain();
    const cands = [];
    Object.keys(domains).forEach(function (did) {
      if (mmDomFilter && did !== mmDomFilter) return;
      (domains[did].findings || []).forEach(function (f) {
        if (f.overall_rag !== 'red') return;
        const tr = f.treatment || {};
        // the A8 verb this row is waiting on, from the treatment state — an
        // affordance label, not an invented instruction
        let verb = 'dispo';
        if (tr.status === 'blocked') verb = 'escalate';
        else if (tr.status === 'planned') verb = 'gate';
        else if (tr.status === 'accepted') verb = 'accept (re-affirm)';
        else if ((f.time_in_state_days || 0) > 90) verb = 'escalate (stalled)';
        cands.push({
          pid: f.pattern_id, name: f.pattern_name || '', did: did,
          days: f.time_in_state_days || 0,
          resid: irBy[f.pattern_id] || 0,
          owner: tr.owner_handle || '—', ownerKind: tr.owner_kind || '',
          ticket: tr.ticket || '—', status: tr.status || '—', verb: verb,
          regs: regsFor[f.pattern_id] || [],
          org: f.org_context || {},
        });
      });
    });
    // round-25 (one source of truth): unscoped, the docket CONSUMES the
    // projection's derived selection — the same list the Board brief renders;
    // neither surface re-ranks. Rail-scoped views still rank their subset.
    const diSel = (((PROJECTION.ia || {}).derived) || {}).docket_items;
    let top3;
    if (!mmDomFilter && diSel && diSel.length) {
      top3 = diSel.map(function (it) {
        return cands.filter(function (c) { return c.pid === it.pattern_id && c.did === it.domain; })[0];
      }).filter(Boolean);
    } else {
      cands.sort(function (a, b) { return b.resid - a.resid; });
      top3 = cands.slice(0, 3);
    }
    if (!top3.length) { setTarget('monday-morning', '<div class="impact-detail">no red findings — nothing to force this week</div>'); return; }
    const atStake = top3.reduce(function (s, c) { return s + c.resid; }, 0);

    // expiring acceptances (30d) — same rule the exec hero uses
    let expiring = 0;
    const now = new Date(((PROJECTION.meta || {}).as_of || '') + 'T00:00:00Z');  // pinned as-of, not the visitor's wall clock
    Object.keys(domains).forEach(function (did) {
      (domains[did].findings || []).forEach(function (f) {
        (f.acceptance_trail || []).forEach(function (acc) {
          if (!acc.expires_at) return;
          const days = Math.round((new Date(acc.expires_at) - now) / 86400000);
          if (days >= 0 && days <= 30) expiring++;
        });
      });
    });

    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:4px">'
      + '<b>' + top3.length + '</b> items to put in front of the right people this week · <b>≤$' + fmtUsd(atStake) + '</b> per-pattern residual P95 riding on them'
      + ' <span class="illustrative-tag" title="ranked by per-pattern residual P95 from the seeded MC; org dynamics are illustrative — deliberately typical of a global fintech">illustrative docket · seeded</span></div>'
      + '<div style="font-size:var(--t-caption); color:var(--text-mut); margin-bottom:12px">2LoD cannot force remediation. Its levers: <b>table it</b> at the right committee · <b>log a formal challenge</b> · <b>decline to counter-sign</b> the next acceptance renewal · <b>escalate to the CRO</b>. Each spends political capital — this docket ranks where it’s worth spending.'
      + (anyCaveat ? ' <span style="color:var(--text-faint)">† style-mapping or contractual regime, not a binding statute — see the applies? flags in the regulation view.</span>' : '') + '</div>';

    top3.forEach(function (c, i) {
      const o = c.org || {};
      html += '<div style="padding:10px 14px; margin:7px 0; border:1px solid var(--border); border-left:3px solid var(--red); border-radius:8px">'
        // row 1 — what + who + $ + state
        + '<div style="display:flex; gap:12px; align-items:baseline; flex-wrap:wrap">'
        + '<span style="font-family:var(--font-mono); color:var(--text-faint)">' + (i + 1) + '</span>'
        + '<span style="flex:1 1 230px"><b style="font-family:var(--font-mono); color:var(--text)">' + esc(c.pid) + '</b> <span style="color:var(--text-mut)">' + esc(c.name) + '</span><br>'
        +   '<span style="font-size:var(--t-micro); color:var(--text-faint)">' + esc(c.did) + ' · ' + esc(c.ticket) + ' · ' + c.days + 'd in state · ' + esc(c.status) + ' · ' + (c.regs.length ? c.regs.join(' · ') : 'no reg triggered') + '</span></span>'
        + '<span style="font-family:var(--font-mono); font-size:var(--t-caption); color:var(--text)">$' + fmtUsd(c.resid) + '<br><span style="color:var(--text-faint); font-size:var(--t-micro)">residual P95</span></span>'
        + '<span style="font-size:var(--t-caption); color:var(--text); text-align:right">' + esc(o.accountable_exec || c.owner) + '<br><span style="font-size:var(--t-micro); color:var(--text-faint)">accountable' + (o.accountable_exec ? '' : ' (team handle)') + '</span></span>'
        + '</div>'
        // row 2 — the organizational truth: why stalled, where decided, what it costs
        + (o.stall_reason
          ? '<div style="margin-top:7px; font-size:var(--t-micro); line-height:1.55; color:var(--text-mut)">'
            + '<span style="color:var(--text-faint)">really stalled because</span> ' + esc(o.stall_reason)
            + (o.competing_commitment ? ' <span style="color:var(--text-faint)">· competing:</span> ' + esc(o.competing_commitment) : '') + '<br>'
            + '<span style="color:var(--text-faint)">state:</span> ' + esc(o.escalation_state || '—')
            + ' <span style="color:var(--text-faint)">· decided at:</span> <b style="color:var(--text)">' + esc(o.decision_route || '—') + '</b><br>'
            + '<span style="color:var(--text-faint)">cost of escalating:</span> ' + esc(o.political_cost || '—')
            + '</div>'
          : '')
        + '</div>';
    });
    html += '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:8px">'
      + (expiring ? expiring + ' acceptance(s) expire within 30d — the cheapest lever on the board: doing nothing forces re-acceptance in writing.' : 'no acceptances expire within 30d.')
      + ' Per-row $ are per-pattern residual P95 (not additive; the portfolio number lives in the exposure block). Org dynamics are illustrative — the stall reasons, committees, and names are synthetic, deliberately typical.</div>';
    setTarget('monday-morning', html);
  }

  // ── DECIDE · org reality (round-23) ──────────────────────────────────────
  // The aggregate the docket rows only show one at a time: which execs answer
  // for the reds (with the residual dollars they answer for), which committee
  // dates the decisions sit on, and the A8 named-human gap as a count. Pure
  // composition of projection data — exec sums re-add the same per-pattern
  // residual P95 leaves the docket ranks by; the A8 count is the
  // ia.derived.treatments_team_routed leaf.
  function renderRiskRollup() {
    var ru = PROJECTION.risk_rollup || {};
    var rows = ru.parents || [];
    if (!rows.length) { setTarget('risk-rollup', ''); return; }
    var tot = ru.totals || {};
    var html = '<div style="display:flex; gap:16px; flex-wrap:wrap; font-family:var(--font-mono); font-size:var(--t-caption); margin-bottom:8px">'
      + '<span><b style="font-size:1.3em">' + tot.parents + '</b> parent patterns</span>'
      + '<span><b style="font-size:1.3em">' + tot.children + '</b> child risks (pattern × domain)</span>'
      + '<span style="color:var(--ok, #6BAF7A)"><b style="font-size:1.3em">' + tot.evidenced + '</b> children EVIDENCED — telemetry fired, derived not asserted</span></div>'
      + '<div style="display:flex; gap:6px; flex-wrap:wrap; font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut)">'
      + rows.filter(function (r) { return r.n_children > 0; }).map(function (r) {
          return '<span style="border:1px solid var(--border); border-radius:999px; padding:2px 10px" title="'
            + esc(r.children.map(function (c) { return c.finding_id + ' (' + c.domain + ' · ' + (c.evidenced ? 'evidenced' : 'no signal in window') + ' · ' + c.rating_state + ')'; }).join(' · '))
            + '"><b style="color:var(--text)">' + esc(r.pattern_id) + '</b> · ' + r.n_children + ' child' + (r.n_children > 1 ? 'ren' : '') + ' · ' + r.n_evidenced + ' evidenced</span>';
        }).join('')
      + '</div>'
      + '<div style="font-size:var(--t-micro); color:var(--text-mut); margin-top:6px">' + esc(ru.note || '') + '</div>';
    setTarget('risk-rollup', html);
  }

  function renderOperatingModel() {
    var om = PROJECTION.operating_model || {};
    if (!om.evidence_counts) { setTarget('operating-model', ''); return; }
    var ec = om.evidence_counts, rs = om.rating_state_counts || {};
    var lbl = {confirmed: 'CONFIRMED', candidate_rerating: 'CANDIDATE RERATING', pending_engineering_confirmation: 'PENDING ENGINEERING CONFIRMATION'};
    var html = '<div style="font-size:var(--t-caption); color:var(--text-mut); line-height:1.6; margin-bottom:10px">'
      + esc(om.before || '') + '</div>'
      + '<div style="font-size:var(--t-caption); color:var(--text); line-height:1.6; margin-bottom:12px">'
      + esc(om.after || '') + '</div>'
      + '<div style="display:flex; gap:18px; flex-wrap:wrap; font-family:var(--font-mono); font-size:var(--t-caption); margin-bottom:10px">'
      + '<span><b style="font-size:1.4em">' + ec.automated + '</b> of ' + ec.total + ' evidence rows re-perform automatically</span>'
      + '<span><b style="font-size:1.4em">' + ec.bespoke + '</b> remain bespoke</span>'
      + '<span style="color:var(--bad, #C84A4A)"><b style="font-size:1.4em">' + (ec.no_evidence_yet || 0) + '</b> have no test evidence yet — nothing to re-perform</span>'
      + '<span style="color:var(--amber, #C9A26B)"><b style="font-size:1.4em">' + ec.hard_to_reperform + '</b> flagged hard-to-re-perform — the honest boundary</span></div>'
      + '<div style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut); margin-bottom:10px">rating-change workflow on the register (derived — see note): '
      + Object.keys(rs).map(function (k) { return '<b style="color:var(--text)">' + rs[k] + '</b> ' + esc(lbl[k] || k); }).join(' · ')
      + '</div>'
      + '<details><summary style="cursor:pointer; font-size:var(--t-micro); color:var(--text-mut)">the evidence lifecycle, per control (' + ec.total + ' rows) — method → re-performance class</summary>'
      + '<div style="max-height:260px; overflow:auto; margin-top:8px">'
      + (om.evidence_rows || []).map(function (r) {
          return '<div style="display:flex; gap:10px; flex-wrap:wrap; font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut); padding:3px 0; border-top:1px solid var(--border)">'
            + '<span style="color:var(--text)">' + esc(r.pattern_id) + '</span>'
            + '<span style="flex:1 1 200px">' + esc(r.control) + '</span>'
            + '<span>' + esc(r.method) + '</span>'
            + '<span style="color:' + (r.reperformance === 'automated' ? 'var(--ok, #6BAF7A)' : (r.reperformance === 'no_evidence_yet' ? 'var(--bad, #C84A4A)' : 'var(--amber, #C9A26B)')) + '">' + esc(r.reperformance)
            + (r.hard_to_reperform ? ' · hard-to-re-perform' : '') + '</span>'
            + '<span style="flex-basis:100%; font-style:italic; opacity:.8">' + esc(r.reperformance_basis) + '</span></div>';
        }).join('')
      + '</div></details>'
      + '<div style="font-size:var(--t-micro); color:var(--text-mut); margin-top:8px">' + esc(om.mechanism || '') + ' ' + esc(om.derivation_note || '') + '</div>';
    setTarget('operating-model', html);
  }

  function renderOrgReality() {
    const domains = PROJECTION.domains || {};
    const irBy = {};
    ((PROJECTION.inherent_residual || {}).by_pattern || []).forEach(function (r) {
      irBy[r.pattern_id] = (r.residual || {}).p95 || 0;
    });
    const execs = {};   // accountable_exec → {n, usd}
    const routes = {};  // committee head (before the em-dash) → count
    let teamRouted = (((PROJECTION.ia || {}).derived) || {}).treatments_team_routed;
    Object.keys(domains).forEach(function (did) {
      (domains[did].findings || []).forEach(function (f) {
        const o = f.org_context || {};
        if (f.overall_rag === 'red') {
          const ex = o.accountable_exec || '(no accountable exec recorded)';
          (execs[ex] = execs[ex] || { n: 0, usd: 0 });
          execs[ex].n++; execs[ex].usd += irBy[f.pattern_id] || 0;
        }
        const rt = String(o.decision_route || '').split('—')[0].trim();
        if (rt) routes[rt] = (routes[rt] || 0) + 1;
      });
    });
    const exRows = Object.keys(execs).map(function (k) { return { ex: k, n: execs[k].n, usd: execs[k].usd }; })
      .sort(function (a, b) { return b.usd - a.usd; });
    const rtRows = Object.keys(routes).map(function (k) { return { rt: k, n: routes[k] }; })
      .sort(function (a, b) { return b.n - a.n; });
    const nFind = ((PROJECTION.meta || {}).counts || {}).findings_total || 0;

    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:10px">'
      + '<b>' + (teamRouted == null ? '—' : teamRouted) + '</b> of <b>' + nFind + '</b> treatments route to a team handle, not a named human'
      + ' — <span style="color:var(--text-mut)">A8 requires a named owner for live actions; the cheapest first ask on every docket row is a name.</span>'
      + ' <span class="illustrative-tag" title="team-level routing is seeded by design and labeled on every treatment — the gap this row prices is the demonstrator&#39;s own">illustrative · seeded</span></div>'
      + '<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px">';
    // column 1 — who answers for the reds
    html += '<div><div style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-faint); letter-spacing:.12em; text-transform:uppercase; margin-bottom:6px">who answers for the reds</div>';
    exRows.forEach(function (r) {
      html += '<div style="display:flex; gap:10px; align-items:baseline; padding:5px 0; border-bottom:1px solid var(--border)">'
        + '<span style="flex:1; color:var(--text)">' + esc(r.ex) + '</span>'
        + '<span style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut)">' + r.n + ' red' + (r.n > 1 ? 's' : '') + '</span>'
        + '<span style="font-family:var(--font-mono); font-size:var(--t-caption); color:var(--text)">$' + fmtUsd(r.usd) + '</span>'
        + '</div>';
    });
    html += '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:5px">Σ of per-pattern residual P95 riding on each name (not additive across the portfolio).</div></div>';
    // column 2 — where the decisions actually sit
    html += '<div><div style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-faint); letter-spacing:.12em; text-transform:uppercase; margin-bottom:6px">where the decisions sit</div>';
    rtRows.forEach(function (r) {
      html += '<div style="display:flex; gap:10px; align-items:baseline; padding:5px 0; border-bottom:1px solid var(--border)">'
        + '<span style="flex:1; color:var(--text)">' + esc(r.rt) + '</span>'
        + '<span style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut)">' + r.n + ' item' + (r.n > 1 ? 's' : '') + '</span>'
        + '</div>';
    });
    html += '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:5px">Committee names and dates come from each finding&#39;s decision route — org dynamics are illustrative, deliberately typical.</div></div>';
    html += '</div>';
    setTarget('org-reality', html);
  }

  // ── E1 · the dependency tornado — which single shared thing takes the most
  // of the tail. Bars are per-node ceteris-paribus P95 deltas from the SAME
  // seeded trial matrix (RNG-aligned suppression); each bar is equally the
  // priced value of the architecture that removes that dependency. Pure
  // render of PROJECTION.dependency_layer — nothing computed here.
  function renderDependencyTornado() {
    const dl = PROJECTION.dependency_layer || {};
    const nodes = dl.nodes || [];
    if (!nodes.length) { setTarget('dependency-tornado', '<div class="impact-detail">no dependency layer in this projection</div>'); return; }
    const one = dl.one_thing || {};
    const maxD = Math.max.apply(null, nodes.map(function (n) { return n.delta_p95_usd || 0; })) || 1;
    let html = '<div style="font-size:var(--t-body); color:var(--text); margin-bottom:4px">'
      + 'One shared dependency — <b>' + esc(one.name || '') + '</b> — carries <b>$' + fmtUsd(one.delta_p95_usd) + '</b> of the tail alone; '
      + 'the whole layer adds <b>$' + fmtUsd(dl.layer_contribution_usd) + '</b> to residual P95 '
      + '(pre-E1 model form: $' + fmtUsd(dl.layer_off_residual_p95) + ')'
      + ' <span class="illustrative-tag" title="' + esc(dl.provenance_note || '') + '">loss frequencies operator-calibrated · anchored to named public incidents</span></div>'
      + '<div style="font-size:var(--t-caption); color:var(--text-mut); margin-bottom:12px">An AWS region, the customer auth plane, the API registry, etcd — '
      + 'one structural event under several risks at once. Pattern-to-pattern cascade edges cannot draw this; the dependency layer prices it. '
      + 'Each bar = remove that dependency, re-run the same seeded trials, watch P95 move — equally the value of the architecture that removes it.</div>';
    nodes.forEach(function (n) {
      const w = Math.max(2, Math.round((n.delta_p95_usd || 0) / maxD * 100));
      const anchors = (n.anchors || []).map(function (a) { return a.name + ' (' + a.date + ')'; }).join(' · ');
      html += '<div style="margin:9px 0" title="' + esc((n.freq_basis ? n.freq_basis + ' — ' : '') + anchors) + '">'
        + '<div style="display:flex; gap:10px; align-items:baseline; font-size:var(--t-caption)">'
        +   '<span style="font-family:var(--font-mono); color:var(--text); flex:0 0 250px">' + esc(n.name) + '</span>'
        +   '<span style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-faint); flex:0 0 130px">' + esc(n.layer) + ' · ' + esc(n.containment_boundary) + '</span>'
        +   '<span style="flex:1"></span>'
        +   '<span style="font-family:var(--font-mono); color:var(--text)">−$' + fmtUsd(n.delta_p95_usd) + ' <span style="color:var(--text-mut)">(' + n.delta_p95_pct + '%)</span></span>'
        + '</div>'
        + '<div style="height:11px; background:var(--surface-3); border-radius:3px; margin-top:3px; overflow:hidden">'
        +   '<div style="width:' + w + '%; height:100%; background:var(--red); opacity:.62"></div>'
        + '</div>'
        + '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:2px">loss ' + (((n.annual_freq || {}).loss) || 0) + '/yr'
        + (((n.annual_freq || {}).blindness) ? ' · blindness ' + n.annual_freq.blindness + '/yr (verification degraded, plane up)' : '')
        + ((n.response_recursion || {}).severity_mult_all ? ' · <span style="color:var(--amber)">recursion ×' + n.response_recursion.severity_mult_all + ' on every severity while down</span>' : '')
        + ' · fires ' + esc((n.fan_out_patterns || []).join(', ')) + ' · ' + esc(n.mitigation_note || '') + '</div>'
        + '</div>';
    });
    const defc = ((dl.deferred_nodes || {}).classes || []);
    if (defc.length) {
      html += '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:8px">DECLARED DEFERRALS — node classes named so their absence is a decision, not a blind spot: '
        + esc(defc.join(' · ')) + ' <span title="' + esc((dl.deferred_nodes || {}).note || '') + '">(hover for the reasoning, incl. the DNS/Meta-anchor seam)</span></div>';
    }
    html += '<div style="font-size:var(--t-micro); color:var(--text-faint); margin-top:8px">' + esc(dl.method_note || '')
      + ' Judgments are on the challenged-judgment log (dep_attribution); the dep_freq_up ×2 and dep_layer_off levers bound them both ways in the tornado above.</div>';
    setTarget('dependency-tornado', html);
  }

  // Impact-vector secondary roll-up (regulatory + customer_trust)
  function renderImpactSecondary() {
    let sumReg = 0, sumCt = 0;
    const domains = PROJECTION.domains || {};
    for (const did of Object.keys(domains)) {
      for (const f of (domains[did].findings || [])) {
        const iv = f.impact_vector || {};
        sumReg += +((iv.regulatory || {}).score || 0);
        sumCt += +((iv.customer_trust || {}).score || 0);
      }
    }
    setTarget('impact-secondary',
      '<span class="impact-secondary-label">Regulatory-face score Σ ' + sumReg.toFixed(1) + '</span>' +
      '<span class="impact-secondary-sep">·</span>' +
      '<span class="impact-secondary-label">Customer-trust-face score Σ ' + sumCt.toFixed(1) + '</span>');
  }

  function renderVerbBar() {
    const log = PROJECTION.action_log || {};
    const verbs = log.verbs_supported || ['gate', 'accept', 'escalate', 'dispo', 'require_eval', 'restrict_scope'];
    const buttons = verbs.map((v) =>
      '<button class="verb-btn" data-verb="' + esc(v) +
      '" data-target-id="MODEL-001" data-target-name="credit-decision-v3" data-target-type="model">' +
      esc(v.replace(/_/g, ' ')) + '</button>'
    ).join('');
    setTarget('verb-bar', buttons);

    const local = loadLocalActions();
    const totalCount = (log.total_entries || 0) + local.length;
    setTarget('verb-summary', esc(
      'Verb affordances · ' + totalCount + ' prior actions · chain ' + (log.chain_status || '—') +
      (local.length ? ' (+' + local.length + ' from localStorage)' : '')
    ));
  }

  function renderActionLog() {
    const entries = getAllActionEntries();
    if (!entries.length) {
      setTarget('action-log',
        '<div class="action-log-empty">No actions recorded yet. Use the verb buttons above to gate, accept, ' +
        'escalate, or require_eval on the AI inventory. Each action requires ≥12-word justification + ' +
        'named human + expiry per amendment A8 and writes to <code>data/action_log.jsonl</code> ' +
        '(hash-chained append-only).</div>');
      return;
    }
    // Show last 5 entries (most recent at top)
    const recent = entries.slice(-5).reverse();
    const html = recent.map((e) => {
      const verb = e.verb || '';
      const verbDisp = verb.toUpperCase().replace(/_/g, ' ');
      const justification = e.justification || '';
      const expiry = e.expiry || '';
      const hash = (e.this_action_hash || '').slice(0, 12);
      const expiresHtml = expiry ? '<span>expires ' + esc(expiry) + '</span>' : '';
      const localBadge = e._local ? '<span class="action-log-local-badge">LOCAL</span>' : '';
      return '<div class="action-log-entry" data-verb="' + esc(verb) + '">' +
        '<div class="action-log-head">' +
          '<span class="action-log-actor">' + esc(e.actor_name || '') +
            '<span class="action-log-role"> · ' + esc(e.actor_role || '') + ' (' + esc(e.actor_role_tier || '') + ')</span>' +
          '</span>' +
          '<span class="action-log-verb" data-verb="' + esc(verb) + '">' + esc(verbDisp) + '</span>' +
          '<span class="action-log-target">' + esc(e.target_name || '') +
            ' <span style="color:var(--text-faint)">(' + esc(e.target_id || '') + ')</span>' +
          '</span>' +
          localBadge +
        '</div>' +
        '<div class="action-log-justification">' + esc(justification) + '</div>' +
        '<div class="action-log-meta">' +
          '<span>recorded ' + esc((e.timestamp || '').slice(0, 19)) + '</span>' +
          expiresHtml +
          '<span class="action-log-hash">hash ' + esc(hash) + '…</span>' +
        '</div>' +
      '</div>';
    }).join('');
    setTarget('action-log', '<div class="action-log">' + html + '</div>');
  }

  function renderAppFooter() {
    const meta = PROJECTION.meta || {};
    const tel = PROJECTION.telemetry_status || '—';
    const footerHtml = 'Period ' + esc(meta.period || '—') +
                       ' · Schema ' + esc(meta.schema_version || '—') +
                       ' · Telemetry: <em>' + esc(tel) + '</em>';
    targets('app-footer-ai-gov').forEach((el) => { el.innerHTML = footerHtml; });
    targets('app-footer-generic-register').forEach((el) => { el.innerHTML = footerHtml; });
  }

  // ── Generic Register ──
  function renderRegisterSummary() {
    const meta = PROJECTION.meta || {};
    const counts = meta.counts || {};
    const cascadeEdges = (PROJECTION.cascade_graph || {}).edges || [];
    const firingEdges = cascadeEdges.filter((e) => e.currently_firing);
    setTarget('register-summary-eyebrow', esc(
      'Period ' + (meta.period || '—') + ' · ' +
      (counts.findings_total || 0) + ' findings · ' + (counts.domains_total || 0) + ' domains'
    ));
    const stats = [
      { label: 'Red findings',   value: counts.findings_red || 0 },
      { label: 'Amber findings', value: counts.findings_amber || 0 },
      { label: 'Red domains',    value: (counts.domains_red || 0) + ' / ' + (counts.domains_total || 0) },
      { label: 'Cascade chains firing', value: firingEdges.length },
    ];
    setTarget('register-summary-row', stats.map((s) =>
      '<div class="summary-stat"><span class="summary-label">' + esc(s.label) + '</span>' +
      '<span class="summary-value">' + esc(s.value) + '</span></div>'
    ).join(''));
  }

  function renderRegisterExposure() {
    const ex = ((PROJECTION.exposure || {}).portfolio_total) || {};
    const worst = ex.worst_anchor_top || {};
    const cards = [
      { label: 'Expected loss · P50', value: '$' + fmtUsd(ex.p50_usd),
        title: ex.computation || '' },
      { label: 'Stress · P95', value: '$' + fmtUsd(ex.p95_usd),
        title: ex.methodology_note || '' },
      { label: 'Worst-anchor · ' + (worst.pattern_id || '—'),
        value: '$' + fmtUsd(worst.worst_anchor_usd),
        title: 'Worst-anchor — single largest cited comparable historical event for the top firing pattern. Lives in lineage, NOT in headline.' },
      { label: 'RAG factors', value: 'R 1.0 · A 0.6 · G 0.0',
        title: 'RAG aggregation weights per A3 — red findings contribute full EL, amber 60%, green 0%.' },
    ];
    setTarget('register-exposure', cards.map((c) =>
      '<div class="exp-card" title="' + esc(c.title) + '">' +
      '<div class="exp-label">' + esc(c.label) + '</div>' +
      '<div class="exp-value">' + esc(c.value) + '</div>' +
      '</div>'
    ).join(''));
  }

  function renderRegisterImpactFaces() {
    const sums = { financial: 0, operational: 0, safety: 0 };
    const tops = { financial: null, operational: null, safety: null };
    for (const did of Object.keys(PROJECTION.domains || {})) {
      const dom = PROJECTION.domains[did];
      for (const f of (dom.findings || [])) {
        const iv = f.impact_vector || {};
        for (const face of Object.keys(sums)) {
          const score = +((iv[face] || {}).score || 0);
          sums[face] += score;
          if (!tops[face] || score > tops[face][0]) {
            tops[face] = [score, f.pattern_id, (dom.domain_name || '').split(' &')[0]];
          }
        }
      }
    }
    const cards = [
      { face: 'financial',   label: 'Financial face (Σ score)',   hint: 'CFO / Treasury' },
      { face: 'operational', label: 'Operational face (Σ score)', hint: 'SRE / VP Engineering' },
      { face: 'safety',      label: 'Safety face (Σ score)',      hint: 'Risk Officer / Legal' },
    ];
    setTarget('register-impact-faces', cards.map((c) => {
      const s = sums[c.face];
      const t = tops[c.face];
      const top = t ? ('Highest: ' + t[1] + ' · ' + t[2] + ' (' + t[0].toFixed(1) + '/10)') : '—';
      return '<div class="exp-card" title="' + esc(c.face) + '-face roll-up across firing findings. ' + esc(c.hint) + ' acts on this face per A3.">' +
        '<div class="exp-label">' + esc(c.label) + '</div>' +
        '<div class="exp-value">' + s.toFixed(1) + '</div>' +
        '<div class="impact-detail" style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-faint); margin-top:4px">' + esc(top) + '</div>' +
      '</div>';
    }).join(''));
  }

  function renderRegisterMateriality() {
    const m = PROJECTION.materiality || {};
    const keys = Object.keys(m);
    const cells = keys.map((k) => {
      const v = m[k];
      const triggered = (v.triggered_patterns || []).length;
      const conditional = (v.conditional_patterns || []).length;
      const triggeredStr = triggered > 0
        ? triggered + ' firing pattern' + (triggered !== 1 ? 's' : '') + ' trigger this obligation'
        : conditional + ' pattern' + (conditional !== 1 ? 's' : '') + ' make this conditional';
      const pids = (v.triggered_patterns || v.conditional_patterns || []).join(', ');
      return '<div class="materiality-cell" data-status="' + esc(v.status || 'CLEAR') + '">' +
        '<div class="materiality-citation">' + esc(v.regulation_citation || '') + '</div>' +
        '<div class="materiality-status">' + esc(v.status === 'TRIGGERED' ? 'TRIGGERED' : (v.status || 'CLEAR')) + '</div>' +
        '<div class="materiality-pattern-count">' + esc(triggeredStr) + (pids ? ': ' + esc(pids) : '') + '</div>' +
      '</div>';
    });
    const caveat = '<div class="materiality-caveat" style="font-size:var(--t-caption); color:var(--text-mut); margin-top:10px; line-height:1.5; border-top:1px solid var(--border); padding-top:8px">'
      + 'These are the regulations the firing patterns <b>trigger</b> — the surface flags what fired, it does not adjudicate. The formal <b>materiality DETERMINATION is reserved to Legal / Compliance</b>.</div>';
    setTarget('register-materiality', cells.join('') + caveat);
  }

  function renderRegisterTbody() {
    const rows = [];
    const seen = new Set();
    const regDomFilter = activeDomain();
    for (const did of Object.keys(PROJECTION.domains || {})) {
      if (regDomFilter && did !== regDomFilter) continue;
      const dom = PROJECTION.domains[did];
      const findings = dom.findings || [];
      if (findings.length === 0) {
        // Coverage row for green domain
        const n = dom.patterns_assessed || 0;
        rows.push({
          type: 'coverage',
          rag: 'green',
          domain_name: (dom.domain_name || '').split(' &')[0],
          patterns_assessed: n,
        });
      } else {
        for (const f of findings) {
          const key = f.pattern_id + '|' + did;
          if (seen.has(key)) continue;
          seen.add(key);
          // Block D · extract top breached signal: name + threshold (real) ·
          // synthesized value suppressed per A2.
          const bs = f.signals_exceeded || {};
          let sigName = '—', sigThreshold = '—';
          const sigKeys = Object.keys(bs);
          if (sigKeys.length) {
            sigName = sigKeys[0];
            const sig = bs[sigName] || {};
            const th = sig.threshold || {};
            const bound = (th[f.overall_rag] != null) ? th[f.overall_rag]
                        : (th.red != null ? th.red : (th.amber != null ? th.amber : null));
            if (bound != null) sigThreshold = (f.overall_rag === 'red' ? '≥' : '≈') + bound;
          }
          const tr = f.treatment || {};
          rows.push({
            type: 'finding',
            rag: f.overall_rag,
            pid: f.pattern_id,
            pattern_name: f.pattern_name,
            domain_name: (dom.domain_name || '').split(' &')[0],
            signal_name: sigName,
            signal_threshold: sigThreshold,
            owner: tr.owner_handle || '—',
            ticket: tr.ticket || (f.acceptance_trail && f.acceptance_trail[0] ? f.acceptance_trail[0].ticket : '—'),
            days: f.time_in_state_days || 0,
            first_detected: fdVal(f.first_detected),
          });
        }
      }
    }
    const ragRank = { red: 0, amber: 1, green: 2 };
    rows.sort((a, b) => (ragRank[a.rag] || 9) - (ragRank[b.rag] || 9));

    const html = rows.map((r) => {
      if (r.type === 'coverage') {
        const n = r.patterns_assessed;
        return '<tr data-rag="green" class="coverage-row">' +
          '<td class="rag-cell"><span class="rag-tag" data-rag="green">GREEN</span></td>' +
          '<td class="pid-cell">—</td>' +
          '<td colspan="6"><em>' + esc(r.domain_name) + ' · ' + n + '/' + n + ' patterns assessed · all within appetite</em></td>' +
          '<td class="date-cell">—</td>' +
        '</tr>';
      }
      return '<tr data-rag="' + esc(r.rag) + '">' +
        '<td class="rag-cell"><span class="rag-tag" data-rag="' + esc(r.rag) + '">' + esc((r.rag || '').toUpperCase()) + '</span></td>' +
        '<td class="pid-cell">' + esc(r.pid) + '</td>' +
        '<td>' + esc(r.pattern_name) + '</td>' +
        '<td>' + esc(r.domain_name) + '</td>' +
        '<td class="signal-cell" title="synthesized signal value suppressed per A2; name + threshold are real" style="font-family:var(--font-mono); font-size:var(--t-micro)">' + esc(r.signal_name) + '</td>' +
        '<td class="threshold-cell" title="threshold is real — published_standard provenance" style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-dim)">' + esc(r.signal_threshold) + '</td>' +
        '<td class="owner-cell" style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--evidence)">' + esc(r.owner) + '</td>' +
        '<td class="ticket-cell" style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-dim)">' + esc(r.ticket) + ' · ' + r.days + 'd</td>' +
        '<td class="date-cell">' + esc(r.first_detected) + '</td>' +
      '</tr>';
    }).join('');
    setTarget('register-tbody', html);
  }

  // ══════════════════════════════════════════════════════════════════════
  // M3 · render-from-data for warm-terminal 5-act IA components
  // Each function reads from PROJECTION (loaded once on boot) and writes
  // to a [data-target=...] container. Empty / missing data → empty-state
  // with cited-basis note. No fabrication.
  // ══════════════════════════════════════════════════════════════════════

  function fmtUsdRange(low, high, worst) {
    const parts = [];
    if (low != null)  parts.push('<span class="lo">$' + fmtUsd(low) + '</span>');
    if (high != null) parts.push('<span class="sep">—</span><span class="hi">$' + fmtUsd(high) + '</span>');
    if (worst != null) parts.push('<span class="sep">·</span><span class="worst">worst $' + fmtUsd(worst) + '</span>');
    return parts.join(' ');
  }

  function illustrativeTag(status) {
    if (status === 'real_query_real_data') return '<span class="real-tag">real</span>';
    return '<span class="illustrative-tag">illustrative</span>';
  }

  // first_detected ships provenance-wrapped ({value, provenance} — illustrative
  // anchor, same envelope discipline as atg). Unwrap for display; tolerate the
  // old bare-string shape so the renderer never breaks on a stale projection.
  function fdVal(fd) {
    if (fd && typeof fd === 'object') return fd.value || '—';
    return fd || '—';
  }

  // Short display labels for regulation ids — ONE map for every mount (swimlane,
  // exec tile, Monday docket). OCC + DORA carry the illustrative-mapping marker.
  const REG_SHORT = {
    eu_ai_act_high_risk: 'EU AI Act', gdpr_art_33: 'GDPR Art.33',
    occ_12cfr30_app_d: 'OCC App-D · illus.', sec_8k_item_1_05: 'SEC 8-K 1.05',
    eu_dora_ict: 'DORA Art.17–19', uk_fca_opres: 'FCA op-res', nydfs_500: 'NYDFS 500.17',
    pci_dss_v4: 'PCI-DSS v4', finra_4370: 'FINRA 4370', sea_17a4: 'SEA 17a-4',
    reg_sci: 'Reg SCI · style',
  };

  // The domain the rail has selected — null means all_portfolio (no filter).
  // Finding-level surfaces (queue, register, Monday-morning) filter on this and
  // re-render when the rail changes; portfolio AGGREGATES (exposure, tornado,
  // regulatory residual) deliberately do NOT — their eyebrows say "portfolio-wide"
  // so the non-change reads as intentional, not broken.
  function activeDomain() {
    const d = document.body.dataset.domain || 'all';
    return (d === 'all' || d === 'ai_gov') ? null : d;
  }
  function domainLabel() {
    const d = activeDomain();
    return d ? d : 'all_portfolio';
  }

  // ── Block C · Executive hero band — the 10-second board answer ──────────
  function renderExecHero() {
    const meta = PROJECTION.meta || {};
    const counts = meta.counts || {};
    const ir = (PROJECTION.inherent_residual || {}).portfolio || {};
    const traj = (PROJECTION.trajectory || {}).overall_delta || {};
    const mats = PROJECTION.materiality || {};
    const domains = PROJECTION.domains || {};

    // Tile 1 · portfolio RAG
    const overall = meta.overall_rag || 'green';
    const ragMap = { red: 'critical', amber: 'watch', green: 'evidence' };
    const t1rag = ragMap[overall] || 'evidence';
    const reds = counts.red || counts.findings_red || 0;
    const ambers = counts.amber || counts.findings_amber || 0;

    // Tile 2 · QoQ trajectory verdict
    const delta = (traj.delta_findings != null) ? traj.delta_findings : null;
    let trendClass = 'exec-trend-flat', trendWord = 'STABLE', trendArrow = '→';
    if (delta != null && delta < 0) { trendClass = 'exec-trend-down'; trendWord = 'IMPROVING'; trendArrow = '▼'; }
    else if (delta != null && delta > 0) { trendClass = 'exec-trend-up'; trendWord = 'WORSENING'; trendArrow = '▲'; }
    const t2rag = (delta != null && delta > 0) ? 'critical' : (delta != null && delta < 0 ? 'evidence' : 'watch');
    // Honesty-in-pixels: the prior period is SYNTHESIZED (history_synthesizer),
    // and the loudest tile must say so — a reader who never opens the projection
    // JSON must still see that the QoQ trend rests on an illustrative prior.
    const priorSynthetic = /synthes/i.test(traj.prev_findings_source || '');

    // Tile 3 · residual P95 with worst-anchor
    const res = ir.residual || {};
    const inh = ir.inherent || {};

    // Tile 4 · top-3 fixes — red findings ranked by RESIDUAL EXPOSURE (P95),
    // not age (CISO re-audit: boards rank by dollars, not time-in-state).
    const irByPattern = {};
    ((PROJECTION.inherent_residual || {}).by_pattern || []).forEach((r) => {
      irByPattern[r.pattern_id] = (r.residual || {}).p95 || 0;
    });
    const allFindings = [];
    Object.keys(domains).forEach((did) => {
      (domains[did].findings || []).forEach((f) => {
        if (f.overall_rag === 'red') {
          allFindings.push({
            pid: f.pattern_id, did: did,
            days: f.time_in_state_days || 0,
            residual_p95: irByPattern[f.pattern_id] || 0,
            owner: (f.treatment || {}).owner_handle || '',
            model: f.model_id || '', agent: f.agent_id || '',
          });
        }
      });
    });
    allFindings.sort((a, b) => (b.residual_p95 || 0) - (a.residual_p95 || 0));
    const top3 = allFindings.slice(0, 3);

    // Tile 5 · regs triggered
    let triggered = 0; const triggeredCites = [];
    if (mats && typeof mats === 'object') {
      Object.keys(mats).forEach((k) => {
        const m = mats[k];
        if (m && (m.status === 'TRIGGERED' || m.triggered === true)) {
          triggered++;
          const cite = REG_SHORT[k] || (m.regulation_citation || k).split(' ')[0];
          if (triggeredCites.length < 3) triggeredCites.push(cite);
        }
      });
    }

    // Tile 6 · acceptances expiring in 30d
    const now = new Date(((PROJECTION.meta || {}).as_of || '') + 'T00:00:00Z');  // pinned as-of, not the visitor's wall clock
    let expiring = 0; const expSoon = [];
    Object.keys(domains).forEach((did) => {
      (domains[did].findings || []).forEach((f) => {
        (f.acceptance_trail || []).forEach((acc) => {
          if (acc.expires_at) {
            const exp = new Date(acc.expires_at);
            const days = Math.round((exp - now) / 86400000);
            if (days >= 0 && days <= 30) { expiring++; if (expSoon.length < 3) expSoon.push(acc.expires_at); }
          }
        });
      });
    });

    let html =
      // Tile 1
      '<div class="exec-tile" data-tile="posture" data-rag="' + t1rag + '">'
      + '<div class="exec-tile-label">portfolio posture</div>'
      + '<div class="exec-tile-value">' + esc(overall.toUpperCase()) + '</div>'
      + '<div class="exec-tile-sub">' + (counts.findings_total || 0) + ' findings · ' + reds + ' red · ' + ambers + ' amber</div>'
      + '</div>'
      // Tile 2
      + '<div class="exec-tile" data-tile="trajectory" data-rag="' + t2rag + '">'
      + '<div class="exec-tile-label">QoQ trajectory</div>'
      + '<div class="exec-tile-value ' + trendClass + '">' + trendArrow + ' ' + trendWord + '</div>'
      + '<div class="exec-tile-sub">' + (delta != null ? (delta > 0 ? '+' : '') + delta + ' findings vs prior period'
          + (priorSynthetic ? ' · <span class="illustrative-tag" title="' + esc(traj.prev_findings_source || '') + '">prior: synthesized</span>' : '')
          : 'no prior period') + '</div>'
      + '</div>'
      // Tile 3 — round-13: the headline's σ=0 choice must be visible AT the
      // headline, not two panels down: the fat-tail range rides the tile itself.
      + '<div class="exec-tile" data-tile="residual" data-rag="watch">'
      + '<div class="exec-tile-label">residual exposure · P95</div>'
      + '<div class="exec-tile-value"><span class="lineage-link" data-prov="portfolio-residual">$' + fmtUsd(res.p95) + '</span></div>'
      + '<div class="exec-tile-sub">inherent $' + fmtUsd(inh.p95) + ' · worst $' + fmtUsd(res.worst_anchor) + '<br>' + illustrativeTag((PROJECTION.inherent_residual || {}).source_status)
      + (function () {
          const sw = ((PROJECTION.sensitivity || {}).sev_shock_sweep || {}).points || [];
          if (!sw.length) return '';
          const hi = sw[sw.length - 1];
          return '<br><span title="the common-cause co-movement term (γ) is IN the headline; the BLANKET σ common shock is excluded (σ=0) — the sweep prices that remaining omission, see calibration">excl. blanket severity shock: up to <b>+' + hi.delta_p95_pct + '%</b> at σ=' + hi.sigma + ' (priced ↓)</span>';
        })()
      // round-17 CRO persona: ONE number + its range. Nested data-target keeps the
      // parent fingerprint clean (own-text rule) — additive, acknowledged.
      + (function () {
          const lv = ((PROJECTION.sensitivity || {}).levers || []).map((l) => l.residual_p95).filter((v) => v > 0);
          if (!lv.length) return '';
          return '<span data-target="hero-range"><br>holds <b>$' + fmtUsd(Math.min.apply(null, lv)) + '–' + fmtUsd(Math.max.apply(null, lv)) + '</b> under any single challenged judgment (tornado ↓)</span>';
        })()
      // round-22 (all three reviewers): the CRO's missing edge — number → this
      // week's decisions in ONE visible click. Leadership-only via CSS; the
      // docket $ hydrates from the ia.derived leaf (C27.4-backed), nested
      // target keeps the hero fingerprint clean.
      + (function () {
          const d = (((PROJECTION.ia || {}).derived) || {}).docket_at_stake_usd;
          if (!d) return '';
          return '<a data-target="hero-docket-cta" class="lead-cta" href="#role=leadership&node=docket">→ this week\\'s docket — three items · $' + fmtUsd(d) + ' at stake</a>';
        })()
      // round-23: the printable board brief — chrome link (no data), nested
      // target so the hero fingerprint stays byte-stable; leadership-only CSS.
      + '<a data-target="hero-board-link" class="lead-cta" href="board.html">the board brief — one page, printable ↪</a>'
      + '<a data-target="hero-journey-link" class="lead-cta" href="journey.html">the journey — one money path, walked ↪</a>'
      + '</div>'
      + '</div>'
      // Tile 4
      + '<div class="exec-tile" data-tile="fixes" data-rag="critical">'
      + '<div class="exec-tile-label">top fixes (by residual $)</div>'
      + '<div class="exec-tile-list">'
      + (top3.length ? top3.map((t) =>
          '<div><span class="rp">' + esc(t.pid) + '</span> · ' + esc(t.did) + ' · <span class="res">$' + fmtUsd(t.residual_p95) + '</span> · ' + t.days + 'd'
          + (t.model ? ' · ⊳' + esc(t.model) : (t.agent ? ' · ⊳' + esc(t.agent) : '')) + '</div>'
        ).join('') : '<div style="color:var(--evidence)">no red findings</div>')
      + '</div>'
      + '</div>'
      // Tile 5
      + '<div class="exec-tile" data-tile="regulatory" data-rag="' + (triggered > 0 ? 'watch' : 'evidence') + '">'
      + '<div class="exec-tile-label">regulatory · triggered</div>'
      + '<div class="exec-tile-value">' + triggered + '</div>'
      + '<div class="exec-tile-sub">' + (triggeredCites.length ? esc(triggeredCites.join(' · ')) : 'none triggered this period') + '</div>'
      + '</div>'
      // Tile 6
      + '<div class="exec-tile" data-tile="expiring" data-rag="' + (expiring > 0 ? 'watch' : 'evidence') + '">'
      + '<div class="exec-tile-label">acceptances expiring ≤30d</div>'
      + '<div class="exec-tile-value">' + expiring + '</div>'
      + '<div class="exec-tile-sub">' + (expSoon.length ? esc(expSoon.join(' · ')) : 'none expiring soon') + '</div>'
      + '</div>';

    // Challenge strip (spec §5, GROK #2 resolution): the number's credibility
    // machinery stays in pixels for EVERY role — this is the door to ATTACK
    // depth, and every value on it is computed, never typed.
    const csens = PROJECTION.sensitivity || {};
    const clv = {}; (csens.levers || []).forEach(function (l) { clv[l.id] = l; });
    const cMax = Math.max.apply(null, (csens.levers || []).filter(function (l) { return String(l.id).indexOf('joint') !== 0; }).map(function (l) { return Math.abs(l.delta_p95_pct || 0); }).concat([0]));
    const cJb = clv.joint_bad_year || {};
    const cSw = ((csens.sev_shock_sweep || {}).points || []);
    const cHi = cSw.length ? cSw[cSw.length - 1] : {};
    html += '<button type="button" class="challenge-strip" data-target="challenge-strip">'
      + '<b>challenge this number ↓</b> holds ±' + cMax.toFixed(0) + '% under any single judgment · joint bad year $' + fmtUsd(cJb.residual_p95) + ' · σ co-movement priced to +' + (cHi.delta_p95_pct || 0) + '%'
      + ' <span>— every lever seeded + re-runnable; the levers live behind this strip · <a href="validation.html" onclick="event.stopPropagation()" style="color:inherit">full validation package ↗</a></span></button>';
    setTarget('exec-hero', html);
    const cs = document.querySelector('.challenge-strip');
    if (cs) cs.addEventListener('click', function () { iaGo(document.body.dataset.role || 'basic', 'attack'); });
  }

  // ── Chrome chain status · B1 · now from a real verifyChain() walk ───────
  async function renderChainStatus() {
    const el = document.getElementById('chain-status');
    if (!el) return;
    // initial state while the async walk runs
    el.innerHTML = 'chain · verifying…';
    let res;
    try {
      res = await verifyChain();
    } catch (e) {
      el.innerHTML = 'chain · verify-error';
      el.setAttribute('data-state', 'demo');
      el.title = 'verifyChain() threw: ' + (e && e.message);
      return;
    }
    const label = res.valid
      ? (res.partial ? 'verified ' + res.verified + '/' + res.total + ' (window)'
                     : 'intact ' + res.verified + '/' + res.total)
      : 'BREAK @ ' + res.brokenAt;
    el.innerHTML = 'chain · ' + esc(label);
    el.setAttribute('data-state', res.valid ? 'verified' : 'broken');
    el.title = 'B1 · live verifyChain() walk · ' + res.note
             + (res.reason ? ' · ' + res.reason : '')
             + ' · SHA-256 over canonical JSON matching utils/action_log.py';
  }

  // ── Left rail · per-domain finding count ────────────────────────────────
  function renderRailDomains() {
    const domains = PROJECTION.domains || {};
    const rows = Object.keys(domains).map((did) => {
      const dom = domains[did];
      const findings = dom.findings || [];
      const count = findings.length;
      let rag = 'evidence';
      if (findings.some((f) => f.overall_rag === 'red'))   rag = 'critical';
      else if (findings.some((f) => f.overall_rag === 'amber')) rag = 'watch';
      const badge = count > 0
        ? '<span class="rail-badge" data-rag="' + rag + '">' + count + '</span>'
        : '<span class="rail-badge" data-rag="evidence">cov</span>';
      return '<div class="rail-item" data-domain="' + esc(did) + '">'
        + '<span class="rail-name">' + esc(did) + '</span>'
        + badge + '</div>';
    }).join('');
    // AI-governance deep-dive: its own rail entry so the ai-gov pane (HITL / model
    // inventory / agent inventory / MCP / trace) is reachable — it renders real data
    // from PROJECTION.ai_gov but was previously gated to a domain with no rail item
    // (render-but-hide). Now an explicit, visible view.
    setTarget('rail-domains', rows
      + '<div class="rail-item rail-aigov" data-domain="ai_gov" title="AI-agent governance deep-dive">'
      + '<span class="rail-name">AI governance</span>'
      + '<span class="rail-badge" data-rag="watch">AI</span></div>');
  }

  // ── IMPACT · translation card · inherent → controls → residual (portfolio)
  function renderTranslationCardPortfolio() {
    const ir = PROJECTION.inherent_residual || {};
    const p  = ir.portfolio || {};
    const inherent = p.inherent || {};
    const controls = p.controls || {};
    const residual = p.residual || {};
    if (!p.inherent && !p.residual) {
      setTarget('translation-card-portfolio',
        '<div class="translation-card" style="padding:24px; color:var(--text-mut); font-family:var(--font-mono); font-size:13px;">inherent_residual block not in projection — wire in M1 first.</div>');
      return;
    }
    const inh = '$' + fmtUsd(inherent.p50) + ' <span class="sep">—</span> $' + fmtUsd(inherent.p95)
              + (inherent.worst_anchor != null ? '<br>worst $' + fmtUsd(inherent.worst_anchor) : '');
    const res = '<span class="lo">$' + fmtUsd(residual.p50) + '</span> <span class="sep">—</span> <span class="hi">$' + fmtUsd(residual.p95) + '</span>'
              + (residual.worst_anchor != null ? '<br>worst $' + fmtUsd(residual.worst_anchor) : '');
    const html = '<div class="translation-card">'
      + '<div class="translation-col" data-side="inherent">'
      +   '<div class="translation-col-label">inherent (no controls)</div>'
      +   '<div class="translation-col-range">' + inh + '</div>'
      +   '<div class="translation-col-meta">' + illustrativeTag(ir.source_status)
      +     ' &nbsp;Σ freq × severity · anchor ' + esc(inherent.worst_anchor_basis || '—') + '</div>'
      + '</div>'
      + '<div class="translation-arrow">→</div>'
      + '<div class="translation-col">'
      +   '<div class="translation-col-label">compensating controls · depth ' + (controls.depth_layers || '?') + '/5 · avg ' + (controls.avg_effectiveness_pct || 0) + '%</div>'
      +   '<div class="control-list" style="font-size:11px; padding-top:8px;">'
      +     '<div class="control-row"><span class="control-status" data-state="in-place">✓</span><span class="control-name">HITL gates · scope · patch (cross-pattern)</span><span class="control-effectiveness">strong</span></div>'
      +     '<div class="control-row"><span class="control-status" data-state="in-place">✓</span><span class="control-name">hash-pin · safety filter · WAF</span><span class="control-effectiveness">solid</span></div>'
      +     '<div class="control-row"><span class="control-status" data-state="gap">!</span><span class="control-name">detect-layer thin (see Defense Layers)</span><span class="control-effectiveness">48%</span></div>'
      +     '<div class="control-row"><span class="control-status" data-state="gap">!</span><span class="control-name">kill-switch · exfil-detect</span><span class="control-effectiveness">Q3 plan</span></div>'
      +   '</div>'
      +   '<div class="translation-col-meta">verbs should close gaps, not duplicate strong controls</div>'
      + '</div>'
      + '<div class="translation-arrow">→</div>'
      + '<div class="translation-col" data-side="residual">'
      +   '<div class="translation-col-label">residual (after controls)</div>'
      +   '<div class="translation-col-range">' + res + '</div>'
      +   '<div class="translation-col-meta">' + illustrativeTag(ir.source_status)
      +     ' &nbsp;inherent × (1 − eff) per pattern · Σ</div>'
      + '</div>'
      + '</div>';
    setTarget('translation-card-portfolio', html);
  }

  // ── IMPACT · defense layers · NIST CSF 5-function ───────────────────────
  function renderDefenseLayers() {
    const dl = PROJECTION.defense_layers || {};
    const layers = dl.layers || [];
    if (!layers.length) {
      setTarget('defense-layers',
        '<div class="defense-layers" style="color:var(--text-mut);">defense_layers block not in projection.</div>');
      return;
    }
    const rows = layers.map((l) => {
      const rag = l.rag || 'evidence';
      return '<div class="defense-layer-row" data-rag="' + esc(rag) + '">'
        + '<span class="defense-layer-name">' + esc(l.name) + '</span>'
        + '<div class="defense-layer-bar"><span style="width:' + (l.coverage_pct || 0) + '%"></span></div>'
        + '<span class="defense-layer-score">' + (l.coverage_pct || 0) + '%</span>'
        + '<span class="defense-layer-note">' + esc(l.note || '') + '</span>'
        + '</div>';
    }).join('');
    setTarget('defense-layers',
      '<div class="defense-layers">' + rows
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:12px;">'
      + illustrativeTag(dl.source_status) + ' &nbsp;framework: ' + esc(dl.framework || 'NIST CSF 2.0')
      + '</p></div>');
  }

  // ── IMPACT · per-pattern inherent → controls → residual rows ────────────
  function renderPerPatternTranslation() {
    const ir = PROJECTION.inherent_residual || {};
    const rows = ir.by_pattern || [];
    if (!rows.length) {
      setTarget('per-pattern-translation',
        '<div style="color:var(--text-mut);">inherent_residual.by_pattern not in projection.</div>');
      return;
    }
    // pattern → the regulation(s) it triggers (from materiality triggered_patterns)
    const mt = PROJECTION.materiality || {};
    const regBy = {};
    Object.keys(mt).forEach((k) => {
      (mt[k].triggered_patterns || []).forEach((pid) => { (regBy[pid] = regBy[pid] || []).push(REG_SHORT[k] || k); });
    });
    function cell(v, sev, note, flow) {
      return '<div class="swim-cell" data-sev="' + esc(sev) + '"' + (flow ? ' data-flow="1"' : '') + '>'
        + '<span class="swim-v">' + esc(v) + '</span>'
        + (note ? '<span class="swim-n">' + esc(note) + '</span>' : '') + '</div>';
    }
    // the ONE thing — use the STORED portfolio figures. Percentiles do NOT sum, so the
    // portfolio P95 is NOT Σ(per-pattern P95); read inherent_residual.portfolio directly
    // (render-from-data + statistically correct, and consistent with the exec-hero tile).
    const port = (PROJECTION.inherent_residual || {}).portfolio || {};
    const inhP95 = (port.inherent || {}).p95 || 0, resP95 = (port.residual || {}).p95 || 0;
    const cut = inhP95 ? Math.round((1 - resP95 / inhP95) * 100) : 0;
    let material = 0;
    rows.forEach((r) => { if ((regBy[r.pattern_id] || []).length) material++; });
    const banner = '<div class="msg-banner" data-sev="high">'
      + '<span class="msg-banner-icon" aria-hidden="true">⚠</span>'
      + '<span class="msg-banner-text"><span class="msg-banner-head">$' + fmtUsd(resP95) + ' residual exposure — portfolio P95, after controls</span>'
      + '<span class="msg-banner-sub">controls cut it ' + cut + '% from $' + fmtUsd(inhP95)
      + ' inherent P95 · ' + material + ' of ' + rows.length + ' patterns trigger a regulatory obligation · '
      + 'residual (net) view of the one seeded Monte-Carlo loss distribution · each row shows its INDUCED share '
      + '— the mean-residual fraction arriving by cascade or shared-dependency injection rather than its '
      + 'own base rate (a high share means the fix lives upstream)</span></span></div>';
    // swimlane: patterns (rows) × the risk lifecycle (columns)
    const top = rows.slice().sort((a, b) => ((b.residual || {}).p95 || 0) - ((a.residual || {}).p95 || 0)).slice(0, 8);
    const stages = ['Inherent (P95)', 'Controls', 'Residual (P95)', 'Regulation triggered', 'Decision'];
    let html = banner + '<div class="swim" style="grid-template-columns:84px repeat(5,1fr)">';
    html += '<div class="swim-corner">pattern <span>╲</span> stage</div>';
    stages.forEach((s) => { html += '<div class="swim-phase">' + esc(s) + '</div>'; });
    top.forEach((r) => {
      const inh = r.inherent || {}, res = r.residual || {}, eff = r.controls_avg_eff_pct || 0;
      const regs = regBy[r.pattern_id] || [], isMat = regs.length > 0, rp = res.p95 || 0;
      html += '<div class="swim-lane"><span>' + esc(r.pattern_id) + '</span></div>';
      html += cell('$' + fmtUsd(inh.p95), 'critical', 'worst-case', true);
      html += cell(eff + '% eff', eff >= 70 ? 'evidence' : (eff >= 40 ? 'watch' : 'critical'), 'avg control', true);
      const att = r.attribution || {}; const indPct = att.induced_share_pct || 0;
      html += cell('$' + fmtUsd(rp), rp >= 1e7 ? 'critical' : (rp >= 3e6 ? 'watch' : 'normal'),
        indPct >= 50 ? indPct + '% induced — treat upstream' : 'after controls · ' + indPct + '% induced', true);
      html += cell(isMat ? regs[0] : '—', isMat ? 'watch' : 'normal',
        isMat ? ((regs[0] || '').indexOf('OCC') === 0
                  ? 'illustrative standards-STYLE mapping' + (regs.length > 1 ? ' · +' + (regs.length - 1) + ' more' : '')
                  : (regs.length > 1 ? '+' + (regs.length - 1) + ' more' : 'triggered'))
              : 'no trigger', true);
      html += cell(isMat ? '→ Legal review' : 'within tolerance', isMat ? 'watch' : 'evidence', isMat ? 'determination' : 'accepted', false);
    });
    html += '</div>';
    setTarget('per-pattern-translation', html);
  }

  // ── IMPACT / DECIDE · actuals tiles · 12-mo real events ────────────────
  function renderActuals() {
    const a = PROJECTION.actuals || {};
    const counts = a.counts || {};
    if (!Object.keys(counts).length) {
      setTarget('actuals-grid',
        '<div style="color:var(--text-mut); padding:12px;">actuals block not in projection.</div>');
      return;
    }
    const cells = [
      { label: 'S0 incidents',     count: counts.s0_incidents || 0,
        rag: (counts.s0_incidents || 0) === 0 ? 'evidence' : 'critical',
        meta: (counts.s0_incidents || 0) === 0 ? 'none in window' : 'see events' },
      { label: 'S1 incidents',     count: counts.s1_incidents || 0,
        rag: (counts.s1_incidents || 0) === 0 ? 'evidence' : 'watch',
        meta: (a.events || []).filter((e) => e.severity === 'S1').map((e) => e.pattern_id).join(' · ') || '—' },
      { label: 'outages >10min',   count: counts.outages_over_10min || 0,
        rag: (counts.outages_over_10min || 0) >= 3 ? 'critical' : (counts.outages_over_10min || 0) > 0 ? 'watch' : 'evidence',
        meta: counts.outages_over_10min ? 'see incident-mgmt' : 'none' },
      { label: 'near-misses',      count: counts.near_misses || 0,
        rag: (counts.near_misses || 0) >= 10 ? 'watch' : 'evidence',
        meta: 'control-hardening triggered' },
    ];
    const html = cells.map((c) => {
      return '<div class="actuals-tile" data-rag="' + c.rag + '">'
        + '<div class="actuals-tile-label">' + esc(c.label) + '</div>'
        + '<div class="actuals-tile-count">' + c.count + '</div>'
        + '<div class="actuals-tile-meta">' + esc(c.meta) + '</div>'
        + '</div>';
    }).join('');
    setTarget('actuals-grid', html);
    // footnote
    const foot = illustrativeTag(a.source_status)
      + ' &nbsp;window: ' + (a.window_months || 12) + 'mo'
      + ' · MTTD median <code style="background:var(--surface-3); padding:1px 5px; border-radius:3px">' + (a.mttd_median_min || '?') + ' min</code>'
      + ' · MTTR median <code style="background:var(--surface-3); padding:1px 5px; border-radius:3px">' + (a.mttr_median_h || '?') + ' h</code>'
      + ' · ' + esc(a.source_note || '');
    setTarget('actuals-footnote', foot);
  }

  // ── IMPACT · recurrence per pattern + cluster flags ────────────────────
  function renderClusters() {
    const c = PROJECTION.clusters || {};
    const rows = (c.by_pattern || []).filter((r) => r.events_12mo > 0 || r.rag === 'evidence');
    if (!rows.length) {
      setTarget('recurrence-list',
        '<div style="color:var(--text-mut); padding:12px;">clusters block not in projection.</div>');
      return;
    }
    const maxEvents = Math.max(1, ...rows.map((r) => r.events_12mo || 0));
    const html = '<div class="recurrence-list">' + rows.map((r) => {
      const pct = ((r.events_12mo || 0) / maxEvents) * 100;
      const note = (r.is_cluster ? '<span class="cluster-flag">cluster</span>' : '') + esc(r.note || '');
      return '<div class="recurrence-row" data-rag="' + esc(r.rag || 'watch') + '">'
        + '<span class="recurrence-pattern">' + esc(r.pattern_id) + '</span>'
        + '<div class="recurrence-bar"><span style="width:' + pct + '%"></span></div>'
        + '<span class="recurrence-count">' + (r.events_12mo || 0) + '</span>'
        + '<span class="recurrence-note">' + note + '</span>'
        + '</div>';
    }).join('')
    + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:12px;">'
    + illustrativeTag(c.source_status) + ' &nbsp;rule: ' + esc(c.cluster_rule || '≥3 events same pattern within 90d on overlapping teams')
    + '</p></div>';
    setTarget('recurrence-list', html);
  }

  // ── IMPACT · group drill-down (team / function / product) ───────────────
  let _activeGroup = 'team';
  function renderGroupPivot() {
    const g = PROJECTION.groups || {};
    const panels = [];
    ['team', 'function', 'product'].forEach((kind) => {
      const key = 'by_' + kind;
      const rows = g[key] || [];
      const hidden = kind !== _activeGroup ? 'style="display:none"' : '';
      const list = rows.map((r) => {
        const inh = r.inherent || {};
        const res = r.residual || {};
        return '<div class="group-row">'
          + '<span class="group-row-name"><span class="role-prefix">' + esc(kind) + '</span>' + esc(r.name) + '</span>'
          + '<span class="group-row-owner">' + esc(r.owner || '—') + '<span class="role-suffix">· ' + esc(r.owner_role || '') + '</span></span>'
          + '<span class="group-row-count">' + (r.finding_count || 0) + '</span>'
          + '<span class="group-row-inherent">inh $' + fmtUsd(inh.p50) + ' — $' + fmtUsd(inh.p95) + '</span>'
          + '<span class="group-row-residual">res $' + fmtUsd(res.p50) + ' — <span class="hi">$' + fmtUsd(res.p95) + '</span></span>'
          + '</div>';
      }).join('');
      panels.push('<div class="group-panel" data-group-panel="' + kind + '" data-active="' + (kind === _activeGroup) + '" ' + hidden + '><div class="group-list">' + list + '</div></div>');
    });
    setTarget('group-pivot', panels.join('')
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:12px;">'
      + illustrativeTag(g.source_status) + ' &nbsp;' + esc(g.source_note || '')
      + '</p>');
  }

  // ── IMPACT · impact faces · residual scoring ────────────────────────────
  function renderImpactFaces() {
    // Face intensity = MEAN per-finding impact score (0–10) for each face, normalised to 0–1.
    // Computed from impact_vector across firing findings — no hardcoded values (render-from-data).
    // The Σ-score roll-up of the same vectors renders in ATTEST (renderRegisterImpactFaces).
    const order = ['financial', 'operational', 'regulatory', 'customer_trust', 'safety'];
    const label = { financial: 'financial', operational: 'operational', regulatory: 'regulatory', customer_trust: 'customer trust', safety: 'safety' };
    const sum = {}, cnt = {};
    for (const did of Object.keys(PROJECTION.domains || {})) {
      for (const f of (PROJECTION.domains[did].findings || [])) {
        const iv = f.impact_vector || {};
        for (const face of order) {
          const s = (iv[face] || {}).score;
          if (typeof s === 'number') { sum[face] = (sum[face] || 0) + s; cnt[face] = (cnt[face] || 0) + 1; }
        }
      }
    }
    const html = order.map((face) => {
      const mean = cnt[face] ? sum[face] / cnt[face] : 0;   // 0–10
      const score = mean / 10;                              // 0–1
      const pct = Math.round(score * 100);
      const rag = score >= 0.6 ? 'critical' : (score >= 0.3 ? 'watch' : 'evidence');
      return '<div class="impact-face" data-rag="' + rag + '">'
        + '<div class="impact-face-name">' + esc(label[face]) + '</div>'
        + '<div class="impact-face-bar"><span style="width:' + pct + '%"></span></div>'
        + '<div class="impact-face-score">' + score.toFixed(2) + '</div>'
        + '</div>';
    }).join('');
    setTarget('impact-faces', html);
  }

  // ── ATTEST · materiality grid · article-level triggers ──────────────────
  function renderMaterialityGrid() {
    // Risk-officer re-audit fix: PROJECTION.materiality is a DICT keyed by
    // regulator (eu_ai_act_high_risk · gdpr_art_33 · occ_12cfr30_app_d ·
    // sec_8k_item_1_05), NOT a list. The prior code did `mats.length` on a
    // dict (undefined) → guard fired → ATTEST grid rendered permanently empty.
    // Iterate with Object.entries and map the real fields.
    const mats = PROJECTION.materiality || {};
    const entries = Object.entries(mats);
    if (!entries.length) {
      setTarget('materiality-grid', '<div style="color:var(--text-mut)">no materiality triggers in projection.</div>');
      return;
    }
    const html = entries.map(([key, m]) => {
      const triggered = (String(m.status || '').toUpperCase() === 'TRIGGERED' || m.triggered === true);
      const prov = m.provenance || {};
      const triggeredPatterns = (m.triggered_patterns || []).join(' · ');
      const body = (prov.computation || m.summary || m.note || '')
        + (triggeredPatterns ? ' · triggered by ' + triggeredPatterns : '');
      return '<div class="materiality-tile" data-status="' + (triggered ? 'triggered' : 'not-triggered') + '">'
        + '<div class="materiality-tile-cite">' + esc(m.regulation_citation || m.cite || key) + '</div>'
        + '<div class="materiality-tile-status">' + esc(triggered ? 'TRIGGERED' : 'clear') + '</div>'
        + '<div class="materiality-tile-body">' + esc(body.slice(0, 200)) + '</div>'
        + '</div>';
    }).join('');
    setTarget('materiality-grid', '<div class="materiality-grid">' + html + '</div>');
  }

  // ── ATTEST · chain integrity detail ─────────────────────────────────────
  function renderChainDetail() {
    const log = PROJECTION.action_log || {};
    const entries = (log.recent_entries || []);
    const head = (entries.length ? entries[entries.length - 1].this_action_hash : '—') || '—';
    const total = entries.length + loadLocalActions().length;
    const lastTs = entries.length ? entries[entries.length - 1].timestamp : '—';
    const html = '<div class="chain-detail">'
      + '<div class="chain-detail-row"><span class="chain-detail-label">head</span><span class="chain-detail-value"><code>' + esc((head || '').slice(0, 20)) + '…</code></span></div>'
      + '<div class="chain-detail-row"><span class="chain-detail-label">entries</span><span class="chain-detail-value">' + total + ' · last <code>' + esc(lastTs) + '</code></span></div>'
      + '<div class="chain-detail-row"><span class="chain-detail-label">scheme</span><span class="chain-detail-value">SHA-256 over canonical JSON · prev_hash chained</span></div>'
      + '<div class="chain-detail-row"><span class="chain-detail-label">status</span><span class="chain-detail-value">' + esc(log.chain_status || 'intact') + '</span></div>'
      + '</div>';
    setTarget('chain-detail', html);
  }

  // ── Panel header (eyebrow + title) re-renders per act/domain/lens ──────
  const ACT_TITLES = {
    signal:  'Signals firing',
    pattern: 'Pattern taxonomy',
    impact:  'Impact range · inherent → residual',
    decide:  'Verb queue',
    attest:  'Attestation · materiality · chain',
  };
  function renderPanelHeader() {
    const act    = document.body.dataset.act    || 'signal';
    const dom    = document.body.dataset.domain || 'all';
    const lens   = document.body.dataset.lens   || 'engineer';
    const eyebrow = document.getElementById('panel-eyebrow');
    const title   = document.getElementById('panel-title');
    if (eyebrow) eyebrow.innerHTML = esc(act) + '  ·  ' + esc(dom === 'all' ? 'all_portfolio' : dom) + '  ·  <span class="mono">' + esc(lens) + '</span>';
    if (title)   title.textContent = ACT_TITLES[act] || act;
  }

  // ── User switcher · sets body[data-lens] + jumps to user's default act ─
  const USERS = {
    engineer: { name: 'D. Patel',   role: '· 1LoD · Director, AI Platform' },
    exec:     { name: 'S. Khoury',  role: '· 2LoD · Director, Technology Risk' },
    auditor:  { name: 'M. Okonkwo', role: '· 3LoD · Senior Manager, Internal Audit' },
  };
  function wireUserSwitcher() {
    document.querySelectorAll('.user-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        // IA Stage B: the user strip is the A8 acting-IDENTITY control only —
        // reading order belongs to the spine's role drop-down (spec §3.5).
        const lens = chip.dataset.lens;
        document.body.dataset.lens = lens;
        document.querySelectorAll('.user-chip').forEach((c) => c.setAttribute('aria-pressed', c === chip ? 'true' : 'false'));
        const u = USERS[lens];
        if (u) {
          const n = document.getElementById('ribbon-name'); if (n) n.textContent = u.name;
          const r = document.getElementById('ribbon-role'); if (r) r.textContent = u.role;
        }
        renderPanelHeader();
      });
    });
  }

  // Scroll the panel header (the start of act-controlled content) into view.
  // The always-on region above it (disclosure + chrome + exec hero) is ~2,500px
  // tall — without this, clicking an act or domain changes nothing the user can
  // SEE, which reads as "the tabs are broken" (verified by a human cold-read).
  function scrollToPanel() {
    const ph = document.querySelector('.panel-header') || document.getElementById('panel-title');
    if (!ph) return;
    const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    ph.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
  }

  // ── IA spine (Stage B, spec v2.2) — ONE navigation system ──────────────
  // Hash is the only state (#role=X&node=Y). Roles re-sequence, never re-value
  // (C26b). No DOM reordering: sections keep canonical order; the active node's
  // sections expand, the rest collapse to headline bars. body[data-act] stays
  // synced to the active node's act so legacy consumers (eyebrow) keep working.
  const IA = PROJECTION.ia || { nodes: [], paths: {}, headlines: {}, acts: [] };
  const IA_NODES = {}; (IA.nodes || []).forEach(function (n) { IA_NODES[n.id] = n; });
  function iaHash() {
    const h = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      const q = kv.split('='); if (q[0]) h[q[0]] = decodeURIComponent(q[1] || '');
    });
    return h;
  }
  function iaState() {
    const h = iaHash();
    const role = (IA.paths && IA.paths[h.role]) ? h.role : (IA.default_role || 'basic');
    const path = IA.paths[role] || [];
    const node = (h.node && IA_NODES[h.node]) ? h.node : path[0];
    return { role: role, node: node, path: path, canonical: ('canonical' in h) };
  }
  function iaGo(role, node) {
    location.hash = 'role=' + role + (node ? '&node=' + node : '');
  }
  function renderSpine(st) {
    const el = document.getElementById('spine'); if (!el) return;
    let html = '<label class="spine-role">viewing as <select id="spine-role-sel" aria-label="Choose your lens">'
      + Object.keys(IA.paths).map(function (r) {
          return '<option value="' + r + '"' + (r === st.role ? ' selected' : '') + '>' + r + '</option>';
        }).join('')
      + '</select></label>';
    st.path.forEach(function (nid, i) {
      const n = IA_NODES[nid]; if (!n) return;
      const actName = (IA.acts.find(function (a) { return a.id === n.act; }) || { name: n.act }).name;
      html += '<button type="button" class="spine-node" data-spine="' + nid + '" aria-pressed="' + (nid === st.node) + '"' + (nid === st.node ? ' aria-current="step"' : '') + ' title="' + esc(n.beat + ' · ' + actName + ' — ' + (n.headline || '')) + '">'
        + '<span class="spine-num">' + (i + 1) + '</span><span class="spine-label">' + esc(n.label) + '</span></button>';
    });
    html += '<button type="button" class="spine-map-btn" id="spine-map-btn" aria-haspopup="dialog" title="the whole argument, mapped">map ⌘</button>'
      + '<button type="button" class="spine-copy" id="spine-copy" title="copy a fully-qualified link to this view">⧉ link</button>'
      + '<a class="spine-read" href="#role=' + st.role + '&node=story" title="the closing picture — the whole argument in one frame">↞ the read</a>';
    el.innerHTML = html;
    document.getElementById('spine-role-sel').addEventListener('change', function () {
      // round-22: position survives a role switch when the node exists on the
      // new path (re-sequence, don't reset); otherwise the new path's start.
      var cur = iaState().node;
      iaGo(this.value, (IA.paths[this.value] || []).indexOf(cur) >= 0 ? cur : null);
    });
    el.querySelectorAll('.spine-node').forEach(function (b) {
      b.addEventListener('click', function () { iaGo(st.role, b.dataset.spine); });
    });
    document.getElementById('spine-map-btn').addEventListener('click', function () { openIaMap(iaState()); });
    document.getElementById('spine-copy').addEventListener('click', function () {
      const url = location.origin + location.pathname + '#role=' + st.role + '&node=' + st.node;
      // r53 (external review): clipboard write can be DENIED (headless, enterprise
      // policy) — an unhandled rejection is a page error; fall back to a prompt
      // the user can copy from, and never let the denial escape.
      const fallback = function () { try { window.prompt('copy the link:', url); } catch (e) { } };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).catch(fallback);
      } else { fallback(); }
    });
  }
  function openIaMap(st) {
    let ov = document.getElementById('ia-map');
    if (!ov) {
      ov = document.createElement('div'); ov.id = 'ia-map'; ov.className = 'ia-map';
      ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-label', 'Argument map'); ov.setAttribute('aria-modal', 'true');
      document.body.appendChild(ov);
    }
    const beats = [];
    (IA.nodes || []).forEach(function (n) { if (beats.indexOf(n.beat) < 0) beats.push(n.beat); });
    let html = '<div class="ia-map-inner"><div class="ia-map-head"><span><b>the argument, mapped</b> — ' + esc(IA.thesis || '') + '</span>'
      + '<button id="ia-map-close" type="button">close ✕</button></div>';
    beats.forEach(function (b) {
      html += '<div class="ia-map-beat"><span>' + esc(b) + '</span>';
      (IA.nodes || []).forEach(function (n) {
        if (n.beat !== b) return;
        const onPath = st.path.indexOf(n.id) >= 0;
        html += '<button type="button" class="ia-map-node' + (onPath ? ' on-path' : '') + (n.id === st.node ? ' here' : '') + '" data-mapnode="' + n.id + '">'
          + '<b>' + esc(n.label) + '</b><span>' + esc(n.headline || '') + '</span></button>';
      });
      html += '</div>';
    });
    html += '<div class="ia-map-acts">the five acts live on: '
      + (IA.acts || []).map(function (a) { return '<span><b>' + esc(a.name) + '</b> — ' + esc(a.desc) + '</span>'; }).join(' · ')
      + '</div></div>';
    ov.innerHTML = html; ov.style.display = 'flex';
    function closeMap() {
      ov.style.display = 'none';
      var mb = document.getElementById('spine-map-btn');
      if (mb) mb.focus();
    }
    document.getElementById('ia-map-close').addEventListener('click', closeMap);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && ov.style.display !== 'none') closeMap();
    });
    // focus enters the dialog only on an interactive open (the boot build has
    // no 'show' param here — the button being active IS the interactive signal)
    if (document.activeElement && document.activeElement.id === 'spine-map-btn') {
      var cb = document.getElementById('ia-map-close'); if (cb) cb.focus();
    }
    ov.querySelectorAll('.ia-map-node').forEach(function (b) {
      b.addEventListener('click', function () { ov.style.display = 'none'; iaGo(st.role, b.dataset.mapnode); });
    });
  }
  // sub-walker: within a step, ONE panel at a time — spotlight, its finding
  // (the ia headline), evidence in place; ▸ past the last panel advances to
  // the next step (the platform grammar: succinct, impactful, traceable)
  var subIdx = 0, subNode = null;
  function subSections(nodeId) {
    return Array.prototype.slice.call(document.querySelectorAll('[data-node="' + nodeId + '"]'));
  }
  function applySub(st) {
    if (st.canonical) return;
    if (subNode !== st.node) { subNode = st.node; subIdx = 0; }
    var secs = subSections(st.node);
    if (subIdx >= secs.length) subIdx = 0;
    secs.forEach(function (s, i) { s.classList.toggle('sub-on', i === subIdx); });
    var sw = document.getElementById('sub-walker');
    if (!sw) return;
    var cur = secs[subIdx];
    var tgt = cur && cur.querySelector('[data-target]');
    var cap = (tgt && (IA.headlines || {})[tgt.getAttribute('data-target')]) ||
      ((cur && cur.querySelector('.section-eyebrow')) ? cur.querySelector('.section-eyebrow').textContent : '');
    sw.innerHTML = '<button type="button" class="sub-btn" id="sub-prev">◂</button>'
      + '<span class="sub-count">PANEL ' + (subIdx + 1) + ' / ' + secs.length + '</span>'
      + '<span class="sub-cap">' + esc(cap) + '</span>'
      + '<button type="button" class="sub-btn" id="sub-next">▸</button>';
    document.getElementById('sub-prev').addEventListener('click', function () {
      if (subIdx > 0) { subIdx--; applySub(iaState()); }
      else { var i2 = st.path.indexOf(st.node); if (i2 > 0) { subIdx = 0; iaGo(st.role, st.path[i2 - 1]); } }
    });
    document.getElementById('sub-next').addEventListener('click', function () {
      if (subIdx < secs.length - 1) { subIdx++; applySub(iaState()); }
      else { var i2 = st.path.indexOf(st.node); if (i2 < st.path.length - 1) { subIdx = 0; iaGo(st.role, st.path[i2 + 1]); } }
    });
  }
  function renderStepHeader(st) {
    // ONE header above the content that repeats EXACTLY what was clicked —
    // big label + its finding + prev/next. Replaces the deleted bar list
    // (round-15 user catch: spine + bars was the same list twice, and landed
    // content never echoed the pill, so clicks gave no confirmation).
    let sh = document.getElementById('step-header');
    if (!sh) {
      sh = document.createElement('div');
      sh.id = 'step-header'; sh.className = 'step-header';
      sh.setAttribute('aria-live', 'polite');
      const ph = document.querySelector('.panel-header');
      ph.parentNode.insertBefore(sh, ph.nextSibling);
    }
    const n = IA_NODES[st.node] || {};
    const i = st.path.indexOf(st.node);
    const actName = (IA.acts.find(function (a) { return a.id === n.act; }) || { name: n.act || '' }).name;
    const prev = i > 0 ? IA_NODES[st.path[i - 1]] : null;
    const next = i >= 0 && i < st.path.length - 1 ? IA_NODES[st.path[i + 1]] : null;
    sh.innerHTML = '<div class="step-kicker">step ' + (i + 1) + ' of ' + st.path.length + ' · ' + esc(n.beat || '') + ' · ' + esc(actName) + '</div>'
      + '<div class="step-row"><h2 class="step-title">' + esc(n.label || '') + '</h2>'
      + '<span class="step-nav">'
      + (prev ? '<button type="button" class="step-btn" data-step="' + st.path[i - 1] + '">◂ ' + esc(prev.label) + '</button>' : '')
      + (next ? '<button type="button" class="step-btn" data-step="' + st.path[i + 1] + '">' + esc(next.label) + ' ▸</button>' : '')
      + '</span></div>'
      + '<p class="step-headline">' + esc(n.headline || '') + '</p>'
      + '<div class="sub-walker" id="sub-walker"></div>';
    sh.querySelectorAll('.step-btn').forEach(function (b) {
      b.addEventListener('click', function () { iaGo(st.role, b.dataset.step); });
    });
  }
  let iaBooted = false;
  function scrollToNode(nodeId) {
    // behavior:'auto' + rAF deferral — a smooth scroll here gets CANCELED by
    // the spine/TOC re-render in the same frame (focused button destroyed),
    // which left every click visually inert (round-14 user catch, verified by
    // screenshot: state changed, viewport stayed at the hero).
    // imperative scroll + one retry: scrollIntoView after a hashchange gets
    // silently reset by native fragment handling in some hosts — computed
    // scrollTo defeats it, the 80ms retry defeats any late reset
    const doScroll = function () {
      const s = document.getElementById('step-header') || document.querySelector('[data-node="' + nodeId + '"].node-on');
      if (!s) return;
      const y = s.getBoundingClientRect().top + window.scrollY - 84;
      window.scrollTo(0, Math.max(0, y));
    };
    // synchronous + timer retry — NOT rAF: rAF never fires when the page
    // isn't compositing (hidden tab/pane), which made navigation depend on
    // the compositor. Layout is computed on demand; sync scroll is safe here.
    doScroll();
    setTimeout(doScroll, 80);
  }
  function injectSectionHeadlines() {
    document.querySelectorAll('[data-node]').forEach(function (s) {
      if (s.querySelector('.section-headline')) return;
      const tgt = s.querySelector('[data-target]');
      const line = tgt && (IA.headlines || {})[tgt.getAttribute('data-target')];
      if (!line) return;
      const d = document.createElement('div');
      d.className = 'section-headline';
      d.textContent = line;
      s.insertBefore(d, s.firstChild);
    });
  }
  function applyIa() {
    const st = iaState();
    document.body.dataset.role = st.role;
    document.body.dataset.iaNode = st.node || '';
    const n = IA_NODES[st.node] || {};
    if (n.act) document.body.dataset.act = n.act;
    if (st.canonical) document.body.setAttribute('data-canonical', '1');
    else document.body.removeAttribute('data-canonical');
    document.querySelectorAll('[data-node]').forEach(function (s) {
      s.classList.toggle('node-on', st.canonical || s.getAttribute('data-node') === st.node);
    });
    const pane = document.querySelector('.ai-gov-pane');
    if (pane) pane.classList.toggle('node-open', st.canonical || st.node === 'ai-gov');
    renderStepHeader(st);
    applySub(st);
    renderSpine(st);
    renderPanelHeader();
    const th = document.getElementById('ia-thesis');
    if (th) th.textContent = IA.thesis || '';
    // scroll on every navigation AND on first load when the link names a node
    // (spec §1: a shared deep link lands ON the node, not at the top)
    if ((iaBooted || iaHash().node) && !st.canonical) scrollToNode(st.node);
    iaBooted = true;
  }
  function wireSpine() {
    openIaMap(iaState());
    var ov0 = document.getElementById('ia-map');
    if (ov0) ov0.style.display = 'none';
    injectSectionHeadlines();
    window.addEventListener('hashchange', applyIa);
    applyIa();
  }

  // ── Rail · set body[data-domain] ───────────────────────────────────────
  // Event delegation on document — the domain rail items are rendered AFTER boot by
  // renderRailDomains(), so direct per-item binding at boot missed them (only the static
  // "all" item ever got a handler). Delegation catches every rail-item, whenever added.
  function wireRail() {
    document.addEventListener('click', (e) => {
      const item = e.target.closest && e.target.closest('.rail-item[data-domain]');
      if (!item) return;
      document.body.dataset.domain = item.dataset.domain;
      document.querySelectorAll('.rail-item').forEach((i) => i.setAttribute('aria-pressed', i === item ? 'true' : 'false'));
      renderPanelHeader();
      // Re-render every FINDING-level surface for the selected domain. (This was
      // the human cold-read's biggest catch: the rail set a body attribute and
      // re-rendered nothing, so domain clicks were cosmetic.) Portfolio
      // aggregates deliberately stay put — their eyebrows say "portfolio-wide".
      renderInterventionQueue();
      renderRegisterTbody();
      renderMondayMorning();
      scrollToPanel();
    });
  }

  // ── Group pivot tab strip ──────────────────────────────────────────────
  function wireGroupPivot() {
    document.querySelectorAll('.group-tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        _activeGroup = btn.dataset.group;
        document.querySelectorAll('.group-tab-btn').forEach((b) => b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'));
        renderGroupPivot();
      });
    });
  }

  // ══════════════════════════════════════════════════════════════════════
  // M4 · AI Governance Lead deep-dive renderers
  // ══════════════════════════════════════════════════════════════════════

  function renderAiGovHitl() {
    const ai = PROJECTION.ai_gov || {};
    const h  = ai.hitl_posture || {};
    if (!h.coverage_pct && h.coverage_pct !== 0) {
      setTarget('ai-gov-hitl', '<div style="color:var(--text-mut)">ai_gov.hitl_posture not in projection.</div>');
      return;
    }
    const rag = h.coverage_pct >= 80 ? 'evidence' : (h.coverage_pct >= 60 ? 'watch' : 'critical');
    setTarget('ai-gov-hitl',
      '<div class="hitl-gauge">'
      +   '<div class="hitl-gauge-circle" data-rag="' + rag + '">' + (h.coverage_pct || 0) + '%</div>'
      +   '<div class="hitl-gauge-body">'
      +     '<div><b>' + (h.models_requiring_hitl || 0) + '</b> of <b>' + (h.models_total || 0) + '</b> models · HITL or eval-gated</div>'
      +     '<div><b>' + (h.agents_requiring_hitl || 0) + '</b> of <b>' + (h.agents_total || 0) + '</b> agents · HITL required</div>'
      +     '<div style="color:var(--text-mut); font-size:11px; margin-top:4px;">' + illustrativeTag(ai.source_status) + ' &nbsp;basis: ' + esc((h.basis || '').slice(0, 200)) + '…</div>'
      +   '</div>'
      +   '<div class="hitl-gauge-meta">'
      +     '<b style="color:var(--text)">No neutral default.</b> Any verb without expiry = shelfware. Per amendment A8.'
      +   '</div>'
      + '</div>');
  }

  function renderAiGovModels() {
    const ai = PROJECTION.ai_gov || {};
    const models = ai.models || [];
    if (!models.length) {
      setTarget('ai-gov-models', '<div style="color:var(--text-mut)">ai_gov.models not in projection.</div>');
      return;
    }
    const rows = models.map((m) => {
      const linked = (m.linked_finding_ids || []);
      const linkTag = linked.length
        ? '<span style="color:var(--signal); font-size:10px; margin-left:8px;" title="' + esc(linked.join(' · ')) + '">← ' + linked.length + ' finding' + (linked.length > 1 ? 's' : '') + '</span>'
        : '';
      return '<div class="inventory-row">'
        + '<span class="inv-name">' + esc(m.name) + '<span style="color:var(--text-mut); font-size:11px; margin-left:8px;">' + esc(m.framework || '') + '</span>' + linkTag + '</span>'
        + '<span class="inv-stage" data-stage="' + esc(m.stage || 'production') + '">' + esc(m.stage || '?') + '</span>'
        + '<span class="inv-owner">' + esc(m.owner || '—') + '</span>'
        + '<span style="color:var(--text-dim); font-size:11px;">' + esc(m.drift_metric || '') + '<br><span style="color:var(--text-mut); font-size:10px;">last refresh ' + esc(m.last_refresh || '?') + ' · ' + (m.days_since_refresh || 0) + 'd ago</span></span>'
        + '<span class="inv-drift-status" data-state="' + esc(m.drift_status || 'within') + '">' + esc(m.drift_status || '?') + '</span>'
        + '<span class="inv-gating" data-state="' + esc(m.gating_state || 'production') + '">' + esc(m.gating_state || '?') + ' '
        +   '<span class="inv-hover-verbs">'
        +     '<span class="inv-hover-verb">gate</span>'
        +     '<span class="inv-hover-verb">eval</span>'
        +     '<span class="inv-hover-verb">restrict</span>'
        +   '</span>'
        + '</span>'
        + '</div>';
    }).join('');
    setTarget('ai-gov-models',
      '<div class="inventory inv-models">'
      + '<div class="inventory-header">'
      +   '<span>model · framework</span><span>stage</span><span>owner</span><span>drift metric · refresh</span><span>drift</span><span>gating · verbs</span>'
      + '</div>'
      + rows
      + '</div>'
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:8px;">'
      + illustrativeTag(ai.source_status) + ' &nbsp;hover any row for inline verb chips (gate · require eval · restrict scope). Production source: model registry (MLflow / W&amp;B).</p>');
  }

  function renderAiGovAgents() {
    const ai = PROJECTION.ai_gov || {};
    const agents = ai.agents || [];
    if (!agents.length) {
      setTarget('ai-gov-agents', '<div style="color:var(--text-mut)">ai_gov.agents not in projection.</div>');
      return;
    }
    const rows = agents.map((a) => {
      const mcps = (a.mcp_servers || []).map((s) => '<code>' + esc(s) + '</code>').join(' ');
      const scopes = (a.scope_grant || []).map((s) => '<code>' + esc(s) + '</code>').join(' ');
      const v = a.scope_violations_24h || 0;
      const vState = v === 0 ? 'evidence' : (v <= 2 ? 'watch' : 'critical');
      const hp = a.hash_pin_compliance_pct || 0;
      const linked = (a.linked_finding_ids || []);
      const linkTag = linked.length
        ? '<span style="color:var(--signal); font-size:10px; margin-left:8px;" title="' + esc(linked.join(' · ')) + '">← ' + linked.length + ' finding' + (linked.length > 1 ? 's' : '') + '</span>'
        : '';
      return '<div class="inventory-row">'
        + '<span class="inv-name">' + esc(a.name) + '<span style="color:var(--text-mut); font-size:11px; margin-left:8px;">' + esc(a.framework || '') + '</span>' + linkTag + '</span>'
        + '<span class="inv-owner" style="color:var(--evidence)">' + esc(a.owner || '—') + '<span style="color:var(--text-mut); font-size:10px; display:block;">' + esc(a.team || '') + '</span></span>'
        + '<span class="inv-mcp-list">' + mcps + '<span style="color:var(--text-mut); font-size:10px; display:block; margin-top:2px;">hash-pin ' + hp + '%</span></span>'
        + '<span class="inv-scope-list">' + scopes + '</span>'
        + '<span class="inv-violations" data-state="' + vState + '">' + v + '</span>'
        + '<span class="inv-hitl" data-required="' + (a.hitl_required ? 'true' : 'false') + '">' + (a.hitl_required ? 'HITL' : 'none') + '</span>'
        + '</div>';
    }).join('');
    setTarget('ai-gov-agents',
      '<div class="inventory inv-agents">'
      + '<div class="inventory-header">'
      +   '<span>agent · framework</span><span>owner · team</span><span>MCP servers · hash-pin</span><span>scope grant</span><span>24h viol.</span><span>HITL</span>'
      + '</div>'
      + rows
      + '</div>'
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:8px;">'
      + illustrativeTag(ai.source_status) + ' &nbsp;basis: OWASP MCP Top 10 (2025) #2 Tool Permission Sprawl · CVE-2025-49596 CVSS 9.4 MCP Inspector RCE. Scope-violation rate = read-scoped agent attempting write within rolling 24h.</p>');
  }

  function renderAiGovMcp() {
    const ai = PROJECTION.ai_gov || {};
    const servers = ai.mcp_servers || [];
    if (!servers.length) {
      setTarget('ai-gov-mcp', '<div style="color:var(--text-mut)">ai_gov.mcp_servers not in projection.</div>');
      return;
    }
    const rows = servers.map((s) => {
      const kev = s.kev_exposure || 0;
      const kevState = kev === 0 ? '0' : 'watch';
      return '<div class="inventory-row">'
        + '<span class="inv-name">' + esc(s.name) + '</span>'
        + '<span class="inv-vendor">' + esc(s.vendor || '—') + '</span>'
        + '<span class="inv-tier">' + esc(s.tier || '—') + '</span>'
        + '<span class="inv-hashpin" data-pinned="' + (s.hash_pinned ? 'true' : 'false') + '">'
        +   (s.hash_pinned ? '✓ pinned' : '✗ floating')
        +   '<span style="color:var(--text-mut); font-size:10px; display:block; margin-top:2px;">' + esc((s.version_pin || '').slice(0, 14)) + '</span>'
        + '</span>'
        + '<span class="inv-scan">' + esc(s.last_security_scan || '—') + '</span>'
        + '<span class="inv-kev" data-count="' + kevState + '">' + kev + '</span>'
        + '<span class="inv-note">' + esc(s.note || '') + '</span>'
        + '</div>';
    }).join('');
    setTarget('ai-gov-mcp',
      '<div class="inventory inv-mcp">'
      + '<div class="inventory-header">'
      +   '<span>server</span><span>vendor</span><span>tier</span><span>hash-pin · version</span><span>last-scan</span><span>KEV</span><span>note</span>'
      + '</div>'
      + rows
      + '</div>'
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:8px;">'
      + illustrativeTag(ai.source_status) + ' &nbsp;hash-pinning per OWASP MCP Top 10 #4 (Untrusted Tool Registration). Floating tags = silent-mutation risk (Simon Willison Apr 2025). Production source: Snyk / Socket.dev / internal supply-chain scanner.</p>');
  }

  function renderAiGovTrace() {
    const ai = PROJECTION.ai_gov || {};
    const trace = ai.trace_recent || [];
    if (!trace.length) {
      setTarget('ai-gov-trace', '<div style="color:var(--text-mut)">ai_gov.trace_recent not in projection.</div>');
      return;
    }
    const rows = trace.map((t) => {
      const flag = t.flagged || 'ok';
      return '<div class="trace-row" data-rag="' + esc(t.rag || 'evidence') + '">'
        + '<span class="trace-time">' + esc(t.ts) + '</span>'
        + '<span class="trace-agent">' + esc(t.agent) + '</span>'
        + '<span class="trace-tool">' + esc(t.tool) + '</span>'
        + '<span class="trace-flag" data-flag="' + esc(flag) + '">' + esc(flag) + '</span>'
        + '<span class="trace-actor">' + esc(t.actor_human || '—') + '</span>'
        + '</div>';
    }).join('');
    setTarget('ai-gov-trace',
      '<div class="trace-stream">' + rows + '</div>'
      + '<p style="font-family:var(--font-mono); font-size:11px; color:var(--text-mut); margin-top:8px;">'
      + illustrativeTag(ai.source_status) + ' &nbsp;live-tail mock. Production: MCP Inspector logs · trace-store stream. Flagged events: scope-violation (read→write attempts) · prompt-injection-attempt (heuristic + classifier).</p>');
  }

  // ══════════════════════════════════════════════════════════════════════
  // M4.5 · PATTERN / SIGNAL / DECIDE renderers — fill the empty-header bug
  // ══════════════════════════════════════════════════════════════════════

  // Build the 13 RP-pattern × N-domain coverage matrix from PROJECTION.domains.
  // Cell state: red (≥1 R finding) · amber (≥1 A finding) · green (clean,
  // pattern in-scope) · oos (pattern out-of-scope for domain · dashed).
  function renderCoverageMatrix() {
    const allPatterns = [
      'RP-01','RP-02','RP-03','RP-04','RP-05','RP-06','RP-07',
      'RP-08','RP-09','RP-10','RP-11','RP-12','RP-13'
    ];
    const domains = PROJECTION.domains || {};
    const dids = Object.keys(domains);
    if (!dids.length) {
      setTarget('coverage-matrix', '<div style="color:var(--text-mut); padding:12px;">No domains in projection.</div>');
      return;
    }
    // Build cell map: domain → pattern → {rag, in_scope, count}
    const cellMap = {};
    dids.forEach((did) => {
      const dom = domains[did];
      const findings = dom.findings || [];
      const scope = dom.scope || {};
      cellMap[did] = {};
      allPatterns.forEach((p) => {
        const inScope = scope[p] !== false; // default in-scope
        const matching = findings.filter((f) => f.pattern_id === p);
        let rag = inScope ? 'evidence' : 'oos';
        if (matching.some((f) => f.overall_rag === 'red'))   rag = 'critical';
        else if (matching.some((f) => f.overall_rag === 'amber')) rag = 'watch';
        cellMap[did][p] = { rag: rag, count: matching.length, in_scope: inScope };
      });
    });
    // Render table
    let html = '<div class="matrix"><div class="matrix-table" style="grid-template-columns: 130px repeat(13, minmax(36px, 1fr));">';
    html += '<div class="matrix-corner"></div>';
    allPatterns.forEach((p) => { html += '<div class="matrix-th">' + esc(p.replace('RP-', '')) + '</div>'; });
    dids.forEach((did) => {
      html += '<div class="matrix-row-label">' + esc(did) + '</div>';
      allPatterns.forEach((p) => {
        const c = cellMap[did][p];
        const label = c.rag === 'critical' ? 'R' : c.rag === 'watch' ? 'A' : c.rag === 'evidence' ? 'G' : 'oos';
        html += '<div class="matrix-cell" data-rag="' + c.rag + '" title="' + esc(did + ' × ' + p + ' · ' + (c.in_scope ? (c.count + ' finding(s)') : 'out-of-scope')) + '">' + label + '</div>';
      });
    });
    html += '</div>';
    html += '<div class="matrix-legend">'
         +  '<span><i data-rag="critical"></i> breach (R)</span>'
         +  '<span><i data-rag="watch"></i> watch (A)</span>'
         +  '<span><i data-rag="evidence"></i> coverage clean (G)</span>'
         +  '<span><i data-rag="oos"></i> out-of-scope (silence rendered)</span>'
         + '</div></div>';
    setTarget('coverage-matrix', html);
  }

  // 13 click-to-expand cards · one per RP pattern. Reads the AUTHORITATIVE
  // taxonomy from PROJECTION.patterns_meta (sourced from risk_patterns.json) —
  // no hardcoded names that can drift from the source of truth.
  function renderPatternPrimer() {
    const meta = (PROJECTION.patterns_meta || {}).patterns || [];
    if (!meta.length) {
      setTarget('pattern-primer', '<div style="color:var(--text-mut)">patterns_meta not in projection.</div>');
      return;
    }
    // Count findings per pattern across all domains
    const counts = {};
    Object.values(PROJECTION.domains || {}).forEach((d) => {
      (d.findings || []).forEach((f) => { counts[f.pattern_id] = (counts[f.pattern_id] || 0) + 1; });
    });
    const html = meta.map((p) => {
      const c = counts[p.id] || 0;
      const anchors = (p.anchors || []).join(' · ') || '—';
      const thresh = p.threshold_source || '—';
      return '<details class="expand-card">'
        + '<summary class="expand-card-summary">'
        +   '<span class="expand-icon">▸</span>'
        +   '<span class="expand-card-title"><span class="pattern-tag">' + esc(p.id) + '</span>&nbsp;&nbsp;' + esc(p.name) + '</span>'
        +   '<span class="expand-card-meta">' + esc(p.nist_function || '') + '</span>'
        +   '<span class="expand-card-meta">' + c + ' findings</span>'
        + '</summary>'
        + '<div class="expand-card-body">'
        +   '<p>' + esc(p.description || '') + '</p>'
        +   '<p><b>threshold source:</b> ' + esc(thresh) + '</p>'
        +   '<p><b>appetite:</b> ' + esc(p.appetite || '—') + '</p>'
        +   '<p><b>public anchors:</b> ' + esc(anchors) + '</p>'
        + '</div>'
        + '</details>';
    }).join('');
    setTarget('pattern-primer', html);
  }

  // Substrate causal chain for top red finding (preferring RP-13 → RP-04 → RP-08).
  function renderCascadeCard() {
    // Pick top red finding
    let topFinding = null;
    for (const did of Object.keys(PROJECTION.domains || {})) {
      const fs = (PROJECTION.domains[did].findings || []).filter((f) => f.overall_rag === 'red');
      if (fs.length) { topFinding = fs[0]; break; }
    }
    if (!topFinding) {
      setTarget('cascade-card', '<div class="cascade-card" style="color:var(--text-mut);">No red findings in this period — cascade trace not applicable.</div>');
      return;
    }
    // Read cascade graph from projection if present
    const graph = PROJECTION.cascade_graph || {};
    const edges = graph.edges || [];
    const fromTop = edges.filter((e) => e.from === topFinding.pattern_id).slice(0, 3);
    const steps = [{
      label: topFinding.pattern_id + ' · ' + (topFinding.pattern_name || ''),
      note:  'fires first · ' + esc(topFinding.signal_summary || Object.keys(topFinding.signals_exceeded || {})[0] || 'signals exceeded'),
    }];
    fromTop.forEach((e) => {
      steps.push({ label: e.to, note: '↓ ' + esc(e.mechanism || 'cascades into') + ' · cited basis ' + esc(e.basis || '—') });
    });
    steps.push({ label: 'verb · gate or require_eval', note: 'closure requires named-human + ≥12-word justification + expiry per A8' });
    const html = '<div class="cascade-card"><ol class="cascade-list">'
      + steps.map((s, i) => '<li class="cascade-step" data-num="' + (i + 1) + '"><div><em>' + esc(s.label) + '</em><br>' + s.note + '</div></li>').join('')
      + '</ol></div>';
    setTarget('cascade-card', html);
  }

  // Per-pattern threshold provenance ribbons — reads AUTHORITATIVE thresholds
  // from PROJECTION.patterns_meta (risk_patterns.json), filtered to firing
  // patterns. No hardcoded citations that can drift.
  function renderEvidenceRibbons() {
    const meta = (PROJECTION.patterns_meta || {}).patterns || [];
    const byId = {};
    meta.forEach((p) => { byId[p.id] = p; });
    // Find firing patterns across portfolio
    const firing = new Set();
    Object.values(PROJECTION.domains || {}).forEach((d) => {
      (d.findings || []).forEach((f) => firing.add(f.pattern_id));
    });
    const firingList = Array.from(firing).filter((pid) => byId[pid]).sort().slice(0, 8);
    if (!firingList.length) {
      setTarget('evidence-ribbons', '<div style="color:var(--text-mut)">No firing patterns to cite.</div>');
      return;
    }
    const html = firingList.map((pid) => {
      const p = byId[pid];
      const url = p.threshold_source_url || '';
      const srcLabel = (p.threshold_source || '').split('.')[0].slice(0, 90);
      return '<div class="evidence-ribbon">'
        + '<span class="ribbon-id">' + esc(pid) + ' · ' + esc(p.name) + '</span>'
        + '<div class="ribbon-body">' + esc((p.threshold_source || '').slice(0, 220))
        +   '<span class="src">' + esc(srcLabel)
        +   (url ? ' · <a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(url.replace(/^https?:\\/\\//, '').slice(0, 48)) + '</a>' : '')
        +   '</span>'
        + '</div>'
        + '<div class="ribbon-meta">' + esc((p.nist_function || '').slice(0, 16)) + '</div>'
        + '</div>';
    }).join('');
    setTarget('evidence-ribbons', html);
  }

  // Decision point — pause prompt question for top red finding.
  function renderPausePrompt() {
    let topRed = null;
    for (const did of Object.keys(PROJECTION.domains || {})) {
      const fs = (PROJECTION.domains[did].findings || []).filter((f) => f.overall_rag === 'red');
      if (fs.length) { topRed = fs[0]; break; }
    }
    if (!topRed) {
      setTarget('pause-prompt', '<div style="color:var(--text-mut); padding:12px;">No red findings · no decision pending.</div>');
      return;
    }
    setTarget('pause-prompt',
      '<div class="pause-prompt">'
      + '<div class="pause-prompt-eyebrow">pause and decide</div>'
      + '<div class="pause-prompt-question">'
      +   esc(topRed.pattern_id) + ' fired on <b>' + esc(topRed.domain_name || topRed.domain_id || '—') + '</b> at ' + esc(topRed.signal_summary || 'red threshold')
      +   ' · <b>gate</b>, <b>require_eval</b>, or accept with named-human signoff?'
      + '</div>'
      + '<div class="pause-prompt-hint">≥12-word justification + expiry · no neutral default · per amendment A8.</div>'
      + '</div>');
  }

  // ── THE READ · closing chapter (r43: 13 pages → 5 doors) ───────────────
  // Folded from docs/read.html — the read's unique assets (the flow picture
  // and its narrated walker) land here; the number/docket screens it also
  // carried already exist above as panels. Same sealed projection, no new values.
  function renderStoryFlow() {
    const cv = document.getElementById('story-flow-cv');
    if (!cv || cv.dataset.wired) return;
    cv.dataset.wired = '1';
    const M2 = (x) => '$' + ((x || 0) / 1e6).toFixed(1) + 'M';
    const irp = (PROJECTION.inherent_residual || {}).portfolio || {};
    const res = irp.residual || {}, inh = irp.inherent || {};
    const counts = (PROJECTION.meta || {}).counts || {};
    const byPatArr = (PROJECTION.inherent_residual || {}).by_pattern || [];
    const firing = ((PROJECTION.cascade_graph || {}).firing_patterns) || [];
    const edges = ((PROJECTION.cascade_graph || {}).edges || []).length;
    const clv = {}; ((PROJECTION.sensitivity || {}).levers || []).forEach((l) => { clv[l.id] = l; });
    const cascAdd = res.p95 - ((clv.cascade_off || {}).residual_p95 || res.p95);
    const cut = inh.p95 ? Math.round((1 - res.p95 / inh.p95) * 100) : 0;
    const byPat = {}; byPatArr.forEach((r) => { byPat[r.pattern_id] = (r.residual || {}).p95 || 0; });
    const cands = [];
    const worstRag = {};
    Object.keys(PROJECTION.domains || {}).forEach((did) => {
      ((PROJECTION.domains[did] || {}).findings || []).forEach((f) => {
        const r = f.overall_rag, prev = worstRag[f.pattern_id];
        if (r === 'red' || (r === 'amber' && prev !== 'red')) worstRag[f.pattern_id] = r;
        if (r === 'red') cands.push({ usd: byPat[f.pattern_id] || 0 });
      });
    });
    cands.sort((a, b) => b.usd - a.usd);
    const docket3 = cands.slice(0, 3).reduce((s, c) => s + c.usd, 0);
    const pats = byPatArr.map((r) => ({ id: r.pattern_id, usd: (r.residual || {}).p95 || 0 }))
      .sort((a, b) => b.usd - a.usd);
    const top = pats.slice(0, 5), rest = pats.slice(5);
    const topPat = pats[0] || { id: '', usd: 0 };
    const topReg = ((PROJECTION.regulation_residual || {}).by_regulation || [{}])[0] || {};
    setTarget('story-flow', esc(M2(inh.p95) + ' inherent  −  ' + cut + '% controls  +  ' + M2(cascAdd)
      + ' cascade compounding (' + edges + ' edges)  =  ' + M2(res.p95)
      + ' residual · drawn from the sealed projection only — the read, folded home'));

    const DW = 940, DH = 500;
    const lanes = top.map((x, i2) => ({ y: 76 + i2 * 64, t: x.id, v: M2(x.usd), rag: worstRag[x.id] }));
    lanes.push({ y: 76 + 5 * 64 + 12, t: '+ ' + rest.length + ' more', v: firing.length + ' of ' + pats.length + ' firing', rag: 'agg' });
    const inhCap = { x: 300, y: DH / 2 - 118, w: 26, h: 236 };
    const ctrl = { x: 428 }, casc = { x: 560 };
    const resCap = { x: 690, y: DH / 2 - 92, w: 26, h: 184 };
    const slices = [
      { y: 96, t1: 'BY PATTERN', t2: (counts.findings_red || 0) + ' red, ranked by $' },
      { y: DH / 2, t1: 'BY REGULATION', t2: (topReg.share_of_portfolio_p95_pct || 0) + '% top regime' },
      { y: DH - 96, t1: 'BY DECISION', t2: M2(docket3) + ' · 3 dockets' }
    ];
    const bez = (p0, p1, bend) => {
      const mx = (p0.x + p1.x) / 2 + (bend || 0);
      return [p0, { x: mx, y: p0.y }, { x: mx, y: p1.y }, p1];
    };
    const bpt = (b, tt) => {
      const u = 1 - tt;
      return { x: u*u*u*b[0].x + 3*u*u*tt*b[1].x + 3*u*tt*tt*b[2].x + tt*tt*tt*b[3].x,
               y: u*u*u*b[0].y + 3*u*u*tt*b[1].y + 3*u*tt*tt*b[2].y + tt*tt*tt*b[3].y };
    };
    const paths = [];
    lanes.forEach((n) => {
      paths.push({ b: bez({ x: 166, y: n.y }, { x: inhCap.x, y: DH / 2 + (n.y - DH / 2) * 0.35 }, -24),
        c: n.rag === 'red' ? 'rgba(200,74,74,.16)' : 'rgba(201,162,107,.16)',
        pc: n.rag === 'red' ? 'rgba(200,74,74,.85)' : 'rgba(201,162,107,.9)' });
    });
    const mid = (x1, x2, col, pc) => { paths.push({ b: [{ x: x1, y: DH/2 }, { x: (x1+x2)/2, y: DH/2 }, { x: (x1+x2)/2, y: DH/2 }, { x: x2, y: DH/2 }], c: col, pc: pc }); };
    mid(inhCap.x + inhCap.w, ctrl.x - 6, 'rgba(232,223,211,.25)', 'rgba(232,223,211,.7)');
    mid(ctrl.x + 96, casc.x - 6, 'rgba(107,175,122,.4)', 'rgba(107,175,122,.9)');
    mid(casc.x + 100, resCap.x, 'rgba(224,145,58,.4)', 'rgba(224,145,58,.9)');
    slices.forEach((s) => {
      paths.push({ b: bez({ x: resCap.x + resCap.w, y: DH / 2 }, { x: 790, y: s.y }, 30), c: 'rgba(201,162,107,.16)', pc: 'rgba(201,162,107,.9)' });
    });
    const particles = [];
    paths.forEach((p2, i2) => { for (let k = 0; k < 3; k++) particles.push({ p: p2, t: (i2 * 0.13 + k * 0.33) % 1, v: 0.0018 + (i2 % 5) * 0.0004 }); });

    const WSTEPS = [
      { cap: firing.length + ' of ' + pats.length + ' patterns fired — ' + (counts.findings_red || 0) + ' red findings; the biggest, ' + topPat.id + ', carries ' + M2(topPat.usd) + ' on its own', node: 'register', x: [30, 290] },
      { cap: M2(inh.p95) + ' inherent P95 — the annual-loss distribution BEFORE any control credit, same seeded MC', node: 'stake', x: [250, 400] },
      { cap: 'controls subtract −' + cut + '%: credited from test evidence, below self-assessed — never assumed', node: 'attack', x: [400, 540] },
      { cap: 'the cascade adds ' + M2(cascAdd) + ' back — contagion compounds through ' + edges + ' declared edges; patterns do NOT sum', node: 'cascade', x: [536, 680] },
      { cap: M2(res.p95) + ' residual P95 — one distribution; every downstream view is a slice of its trials, never a re-model', node: 'stake', x: [655, 760] },
      { cap: 'three slices: the queue (' + (counts.findings_red || 0) + ' red by $) · regulation (' + (topReg.share_of_portfolio_p95_pct || 0) + '% top regime) · Monday (' + M2(docket3) + ' on 3 dockets)', node: 'docket', x: [755, 940] }
    ];
    let wIdx = 0, spot = WSTEPS[0].x;
    function wRender() {
      document.getElementById('story-step').textContent = 'STEP ' + (wIdx + 1) + ' / ' + WSTEPS.length;
      document.getElementById('story-cap').textContent = WSTEPS[wIdx].cap;
      spot = WSTEPS[wIdx].x;
    }
    document.getElementById('story-prev').addEventListener('click', () => { wIdx = (wIdx + WSTEPS.length - 1) % WSTEPS.length; wRender(); });
    document.getElementById('story-next').addEventListener('click', () => { wIdx = (wIdx + 1) % WSTEPS.length; wRender(); });
    document.getElementById('story-link').addEventListener('click', (e) => {
      e.preventDefault(); iaGo(document.body.dataset.role || 'basic', WSTEPS[wIdx].node);
    });
    wRender();

    let ctx, S = 1;
    function size() {
      const cw = Math.min(cv.parentNode.clientWidth || DW, 990);
      const dpr = window.devicePixelRatio || 1;
      cv.width = Math.round(cw * dpr); cv.height = Math.round(cw * DH / DW * dpr);
      cv.style.width = Math.round(cw) + 'px'; cv.style.height = Math.round(cw * DH / DW) + 'px';
      ctx = cv.getContext('2d'); S = cw * dpr / DW;
      ctx.setTransform(S, 0, 0, S, 0, 0);
    }
    function strokeB(b, style, w) {
      ctx.strokeStyle = style; ctx.lineWidth = w;
      ctx.beginPath(); ctx.moveTo(b[0].x, b[0].y);
      ctx.bezierCurveTo(b[1].x, b[1].y, b[2].x, b[2].y, b[3].x, b[3].y); ctx.stroke();
    }
    function boxAt(x, y, w, h, col, title, l1, l2, l3) {
      ctx.strokeStyle = col; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.roundRect(x, y, w, h, 10); ctx.stroke();
      ctx.fillStyle = col; ctx.font = '600 12px ui-monospace, Menlo, monospace';
      ctx.fillText(title, x + 12, y + 22);
      ctx.font = '10.5px ui-monospace, Menlo, monospace';
      ctx.fillText(l1, x + 12, y + 40);
      ctx.fillStyle = 'rgba(232,223,211,.45)';
      ctx.fillText(l2, x + 12, y + 56);
      ctx.fillText(l3, x + 12, y + 70);
    }
    function frame() {
      ctx.clearRect(0, 0, DW, DH);
      ctx.font = '10.5px ui-monospace, Menlo, monospace';
      ctx.fillStyle = 'rgba(232,223,211,.45)';
      ctx.fillText(pats.length + ' PATTERNS — TOP 5 BY $', 40, 24);
      paths.forEach((p2) => { strokeB(p2.b, p2.c, 1.2); });
      lanes.forEach((n) => {
        const col = n.rag === 'agg' ? 'rgba(232,223,211,.30)' : n.rag === 'red' ? '#C84A4A' : '#E0913A';
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(150, n.y, n.rag === 'agg' ? 7 : 9, 0, 7); ctx.fill();
        ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(232,223,211,.65)'; ctx.fillText(n.t, 132, n.y - 2);
        ctx.fillStyle = 'rgba(232,223,211,.38)'; ctx.fillText(n.v, 132, n.y + 12);
        ctx.textAlign = 'left';
      });
      const g1 = ctx.createLinearGradient(0, inhCap.y, 0, inhCap.y + inhCap.h);
      g1.addColorStop(0, 'rgba(232,223,211,.32)'); g1.addColorStop(1, 'rgba(232,223,211,.08)');
      ctx.fillStyle = g1; ctx.beginPath(); ctx.roundRect(inhCap.x, inhCap.y, inhCap.w, inhCap.h, 12); ctx.fill();
      ctx.fillStyle = 'rgba(232,223,211,.7)'; ctx.font = '600 12px ui-monospace, Menlo, monospace';
      ctx.fillText(M2(inh.p95), inhCap.x - 20, inhCap.y - 24);
      ctx.font = '10.5px ui-monospace, Menlo, monospace';
      ctx.fillStyle = 'rgba(232,223,211,.45)'; ctx.fillText('INHERENT P95', inhCap.x - 20, inhCap.y - 10);
      boxAt(ctrl.x, DH / 2 - 44, 96, 88, 'rgba(107,175,122,.75)', 'CONTROLS', '−' + cut + '% credited', 'tested, not', 'assumed');
      boxAt(casc.x, DH / 2 - 44, 100, 88, 'rgba(224,145,58,.75)', 'CASCADE', '+' + M2(cascAdd), 'compounds via', edges + ' edges');
      const g2 = ctx.createLinearGradient(0, resCap.y, 0, resCap.y + resCap.h);
      g2.addColorStop(0, 'rgba(201,162,107,.6)'); g2.addColorStop(1, 'rgba(201,162,107,.14)');
      ctx.fillStyle = g2; ctx.beginPath(); ctx.roundRect(resCap.x, resCap.y, resCap.w, resCap.h, 12); ctx.fill();
      ctx.fillStyle = '#C9A26B'; ctx.font = '600 12px ui-monospace, Menlo, monospace';
      ctx.fillText(M2(res.p95), resCap.x - 20, resCap.y - 24);
      ctx.font = '10.5px ui-monospace, Menlo, monospace';
      ctx.fillText('RESIDUAL P95', resCap.x - 20, resCap.y - 10);
      const fit = (txt, maxW) => {
        if (ctx.measureText(txt).width <= maxW) return txt;
        while (txt.length > 1 && ctx.measureText(txt + '…').width > maxW) txt = txt.slice(0, -1);
        return txt + '…';
      };
      slices.forEach((s) => {
        ctx.strokeStyle = 'rgba(214,196,162,.25)'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(790, s.y - 28, 140, 56, 10); ctx.stroke();
        ctx.fillStyle = '#C9A26B'; ctx.fillText(fit(s.t1, 116), 802, s.y - 6);
        ctx.fillStyle = 'rgba(232,223,211,.55)'; ctx.fillText(fit(s.t2, 116), 802, s.y + 12);
      });
      particles.forEach((pt) => {
        const q = bpt(pt.p.b, pt.t);
        const inSpot = !spot || (q.x >= spot[0] && q.x <= spot[1]);
        ctx.fillStyle = pt.p.pc;
        ctx.globalAlpha = inSpot ? 0.9 : 0.18; ctx.beginPath(); ctx.arc(q.x, q.y, inSpot ? 2.6 : 1.8, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
      });
      if (spot) {
        ctx.fillStyle = 'rgba(20,17,13,.45)';
        if (spot[0] > 0) ctx.fillRect(0, 30, spot[0], DH - 62);
        if (spot[1] < DW) ctx.fillRect(spot[1], 30, DW - spot[1], DH - 62);
        ctx.strokeStyle = 'rgba(201,162,107,.35)'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(spot[0] + 2, 32, spot[1] - spot[0] - 4, DH - 66, 12); ctx.stroke();
      }
    }
    let inited = false;
    function init() {
      inited = true;
      size(); frame();
      const reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!reduced) {
        let last = 0;
        const step = (ts) => {
          if (ts - last > 28) {
            last = ts;
            particles.forEach((pt) => { pt.t += pt.v; if (pt.t > 1) pt.t = 0; });
            frame();
          }
          requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
      window.addEventListener('resize', () => { size(); frame(); });
    }
    function ensure() { if (!inited && cv.parentNode.clientWidth) init(); }
    window.addEventListener('hashchange', () => setTimeout(ensure, 40));
    setTimeout(ensure, 40);
  }

  // ── r51 · THE CHOICE — two priced strategies + the signed hold. Every number
  //    here reads strategy_chooser leaves (no literals); C39 gates the math.
  function renderStrategyChooser() {
    const sc = PROJECTION.strategy_chooser || {};
    const strats = sc.strategies || [];
    const A = strats.find((s) => s.id === 'harden_controls') || {};
    const B = strats.find((s) => s.id === 'isolate_dependencies') || {};
    const hold = sc.hold_option || {};
    const rec = sc.recommendation || {};

    const flagHtml = (f) => {
      const bad = f.status === 'PAST DUE';
      return '<span class="sc-flag" style="color:' + (bad ? '#e5484d' : '#C9A26B') + '">'
        + esc(f.issue_id) + (f.status ? ' · ' + esc(f.status) : '') + (f.repeat ? ' · REPEAT' : '') + '</span>';
    };

    let html = '<div style="font-size:16.5px; line-height:1.55; max-width:900px">' + esc(sc.one_question || '') + '</div>';

    let a = '<div class="sc-tile">'
      + '<div class="sc-verb">' + esc(A.board_verb || '') + '</div>'
      + '<div class="sc-name">' + esc(A.name || '') + '</div>'
      + '<div class="sc-thesis">' + esc(A.thesis || '') + '</div>'
      + '<div class="sc-price" style="color:var(--posture-clear, #7fb069)">−$' + fmtUsd(A.benefit_p95_usd)
      + ' <span style="font-size:13px; font-weight:400">off residual P95</span></div>'
      + '<div class="sc-basis">' + esc(A.benefit_basis || '') + ' · downside if controls drift: $'
      + fmtUsd(A.downside_p95_usd) + ' — ' + esc(A.downside_basis || '') + '</div>';
    if (A.credit_gate) {
      a += '<div class="sc-row"><span class="sc-label">credit gate</span><br>'
        + esc(A.credit_gate.issue_id) + ' — ' + esc(A.credit_gate.why) + '</div>';
    }
    a += '<div class="sc-row"><span class="sc-label">accountable for the reds</span><br>'
      + (A.owners || []).map((o) => esc(o.exec) + ' (' + o.red_findings + ')').join(' · ') + '</div>';
    if ((A.delivery_risk_flags || []).length) {
      a += '<div class="sc-row"><span class="sc-label">delivery risk on record</span><br>'
        + A.delivery_risk_flags.map(flagHtml).join('') + '</div>';
    }
    a += '<div class="sc-row"><span class="sc-label">time shape</span><br>' + esc(A.time_shape || '') + '</div>'
      + '<div class="sc-basis" style="margin-top:auto; padding-top:10px">recomputes: baseline − levers.eff_up · gate C39</div>'
      + '</div>';

    let b = '<div class="sc-tile">'
      + '<div class="sc-verb">' + esc(B.board_verb || '') + '</div>'
      + '<div class="sc-name">' + esc(B.name || '') + '</div>'
      + '<div class="sc-thesis">' + esc(B.thesis || '') + '</div>'
      + '<div class="sc-price" style="color:#C9A26B">$' + fmtUsd(B.layer_ceiling_usd)
      + ' <span style="font-size:13px; font-weight:400">ceiling · whole layer</span></div>'
      + '<div class="sc-basis">' + esc(B.layer_ceiling_basis || '') + ' · the concentrating world: $'
      + fmtUsd(B.downside_p95_usd) + ' — ' + esc(B.downside_basis || '') + '</div>'
      + '<div class="sc-row"><span class="sc-label">program scope · per-node isolation ceilings</span></div>';
    (B.program_nodes || []).forEach((n) => {
      b += '<div class="sc-node"><span>' + esc(n.name) + '</span>'
        + '<span style="font-family:var(--font-mono, ui-monospace, monospace); white-space:nowrap">−$'
        + fmtUsd(n.ceiling_delta_p95_usd) + ' · ' + (n.ceiling_delta_p95_pct || 0) + '%</span></div>';
    });
    b += '<div class="sc-row"><span class="sc-label">ownership gap</span><br>' + esc(B.ownership_gap || '') + '</div>'
      + '<div class="sc-row"><span class="sc-label">time shape</span><br>' + esc(B.time_shape || '') + '</div>'
      + '<div class="sc-basis" style="margin-top:auto; padding-top:10px">recomputes: dependency_layer.nodes + levers.dep_layer_off · gate C39</div>'
      + '</div>';

    html += '<div class="sc-grid">' + a + b + '</div>';

    const cc = A.political_cost || [];
    if (cc.length) {
      html += '<div class="sc-strip"><span class="sc-label">the political terrain — competing commitments, from the register verbatim</span>'
        + cc.map((c) => '<div class="sc-row" style="margin-top:5px">· ' + esc(c) + '</div>').join('') + '</div>';
    }

    // r53 (external review): the signed hold is what makes the other two
    // postures honest — it carries the same visual weight as a strategy, not
    // a footnote's.
    const reds = hold.strict_appetite_reds || [];
    let h = '<div class="sc-strip" style="border-color:rgba(229,72,77,.45); background:rgba(229,72,77,.05)">'
      + '<div class="sc-verb" style="color:#e5484d">SIGN — ' + esc(hold.label || 'hold at current appetite') + '</div>'
      + '<div class="sc-price" style="color:#e5484d; margin:6px 0 2px">$' + fmtUsd(hold.stress_test_p95_usd)
      + ' <span style="font-size:13px; font-weight:400">the year a signed hold gets tested</span></div>'
      + '<div class="sc-basis">' + esc(hold.stress_test_basis || '') + '</div>'
      + '<div class="sc-row">' + esc(hold.reality || '')
      + (reds.length ? ' — currently: ' + reds.map(esc).join(', ') : '') + '</div>';
    const accs = hold.acceptances_on_file || [];
    if (accs.length) {
      const shown = accs.slice(0, 5);
      h += '<div class="sc-row"><span class="sc-label">acceptances already on file (' + accs.length + ')</span><br>'
        + shown.map((x) => esc(x.accepted_by) + ' → ' + esc(x.finding_id)
          + (x.expires_at ? ' · expires ' + esc(x.expires_at) : '')).join('<br>')
        + (accs.length > shown.length
            ? '<br><span class="sc-basis">+' + (accs.length - shown.length)
              + ' more — every one on the register with conditions and expiry</span>' : '')
        + '</div>';
    }
    h += '</div>';
    html += h;

    html += '<div class="sc-strip" style="background:rgba(201,162,107,.06)">'
      + '<span class="sc-label">2LoD recommendation · sequencing</span>'
      + '<div class="sc-row">' + esc(rec.sequencing || '') + '</div>'
      + ((rec.decision_routes || []).length
          ? '<div class="sc-row"><span class="sc-label">decision routes on the register</span><br>' + rec.decision_routes.map(esc).join(' · ') + '</div>' : '')
      + (rec.audit_committee_hook
          ? '<div class="sc-row"><span class="sc-label">audit-committee visibility</span><br>' + esc(rec.audit_committee_hook) + '</div>' : '')
      + '<div class="sc-basis" style="margin-top:9px">' + esc(rec.disclosure_note || '') + '</div>'
      + '</div>';

    setTarget('strategy-chooser', html);
  }

  function renderAll() {
    renderHero();
    renderInterventionQueue();
    renderExposureCards();
    renderImpactSecondary();
    renderSensitivity();
    renderRegulationResidual();
    renderMondayMorning();
    renderOrgReality();
    renderOperatingModel();
    renderRiskRollup();
    renderDependencyTornado();
    renderInternalAudit();
    renderVerbBar();
    renderActionLog();
    renderAppFooter();
    renderRegisterSummary();
    renderRegisterExposure();
    renderRegisterImpactFaces();
    renderRegisterMateriality();
    renderRegisterTbody();
    // M3 · warm-terminal IA components
    renderExecHero();
    renderChainStatus();
    renderRailDomains();
    renderTranslationCardPortfolio();
    renderDefenseLayers();
    renderPerPatternTranslation();
    renderActuals();
    renderClusters();
    renderGroupPivot();
    renderImpactFaces();
    renderMaterialityGrid();
    renderChainDetail();
    renderPanelHeader();
    // M4 · AI Governance Lead deep-dive
    renderAiGovHitl();
    renderAiGovModels();
    renderAiGovAgents();
    renderAiGovMcp();
    renderAiGovTrace();
    // M4.5 · PATTERN / SIGNAL / DECIDE renderers (kill the empty-header bug)
    renderCoverageMatrix();
    renderPatternPrimer();
    renderCascadeCard();
    renderEvidenceRibbons();
    renderPausePrompt();
    renderStrategyChooser();
    renderStoryFlow();
    // Re-wire after re-render — lineage and verb buttons live in JS-built content now.
    wireDynamicHandlers();
  }

  // (QA-2 resolved: the legacy alpha3 app-nav switcher was dead code — no
  //  .app-nav-tab elements have been rendered since the domain rail absorbed the
  //  ai_gov view. Deleted rather than silently kept.)

  // M3 wire-up — user switcher · act tabs · rail · group pivot
  wireUserSwitcher();
  wireSpine();
  wireRail();
  wireGroupPivot();

  // ── Lineage modal ──
  const modal = document.getElementById('lineage-modal');
  const modalTitle = document.getElementById('lineage-title');
  const modalSubtitle = document.getElementById('lineage-subtitle');
  const modalBody = document.getElementById('lineage-body');

  function renderAssumptions(arr) {
    if (!arr || !arr.length) return '<em style="color:var(--text-faint)">No assumptions stated</em>';
    return arr.map((a) => '<div class="lineage-assumption">' + esc(a) + '</div>').join('');
  }

  function openLineage(provJson, labelText) {
    let prov = {};
    try { prov = JSON.parse(provJson); }
    catch (e) { prov = { error: 'Invalid provenance: ' + e.message }; }
    modalTitle.textContent = labelText || 'Lineage';
    modalSubtitle.textContent = 'Source · Query · Timestamp · Computation · Assumptions';
    const statusBadge = prov.source_status
      ? '<span class="lineage-status-badge" data-status="' + esc(prov.source_status) + '">'
        + esc(prov.source_status.replace(/_/g, ' ')) + '</span>' : '';
    modalBody.innerHTML = [
      '<div class="lineage-section"><div class="lineage-section-label">Source status</div><div class="lineage-section-body">' + statusBadge + '</div></div>',
      '<div class="lineage-section"><div class="lineage-section-label">Source system</div><div class="lineage-section-body"><code>' + esc(prov.source_system || '—') + '</code></div></div>',
      '<div class="lineage-section"><div class="lineage-section-label">Source query</div><div class="lineage-section-body"><code>' + esc(prov.source_query || '—') + '</code></div></div>',
      '<div class="lineage-section"><div class="lineage-section-label">Source timestamp (UTC)</div><div class="lineage-section-body"><code>' + esc(prov.source_timestamp || '—') + '</code></div></div>',
      '<div class="lineage-section"><div class="lineage-section-label">Computation</div><div class="lineage-section-body">' + esc(prov.computation || '—') + '</div></div>',
      '<div class="lineage-section"><div class="lineage-section-label">Assumptions</div><div class="lineage-section-body">' + renderAssumptions(prov.assumptions) + '</div></div>'
    ].join('');
    modal.setAttribute('data-open', 'true');
  }
  function closeLineage() { modal.setAttribute('data-open', 'false'); }
  modal.addEventListener('click', (e) => { if (e.target === modal) closeLineage(); });
  const closeBtn = document.getElementById('lineage-close-btn');
  if (closeBtn) closeBtn.addEventListener('click', closeLineage);

  // ── Verb confirm modal ──
  const verbModal = document.getElementById('verb-modal');
  const verbTitle = document.getElementById('verb-modal-title');
  const verbJust = document.getElementById('verb-justification');
  const verbJustHint = document.getElementById('verb-justification-hint');
  const verbActor = document.getElementById('verb-actor');
  const verbExpiry = document.getElementById('verb-expiry');
  const verbConfirm = document.getElementById('verb-confirm-btn');
  const verbCancel = document.getElementById('verb-cancel-btn');
  const verbContext = document.getElementById('verb-context');
  let activeVerb = null;
  let activeTarget = null;
  const VERBS_NEEDING_EXPIRY = ['gate', 'accept', 'require_eval', 'restrict_scope'];
  const JUSTIFICATION_MIN_WORDS = 12;
  function wordCount(s) { return (s || '').trim().split(/\\s+/).filter(Boolean).length; }
  // Re-audit fix (Claude defect #1): A8 requires a NAMED HUMAN, not a team
  // handle. The prior check only tested non-empty, so "@platform" passed and
  // wrote an attestation entry — performing a rigor it didn't possess, the
  // exact v1.4 failure class, on the seal. Enforce a real-name shape: reject
  // @handles, slugs (_ or /), and single-token values; require two name tokens.
  function actorIsNamedHuman(raw) {
    const v = (raw || '').trim();
    if (!v) return false;
    if (v.startsWith('@')) return false;            // handle
    if (/[_/]/.test(v)) return false;               // slug like sre_team / sre/oncall
    // reject org / team / rotation / service handles masquerading as a person
    if (/(^|[\\s.\\-])(teams?|rotations?|rota|on[-\\s]?call|service\\s+accounts?|accounts?|bots?|robots?|ops|admin|sysadmin|systems?|group|queue|desk|automation|pipeline|svc|daemon|cron|webhook|integration)([\\s.\\-]|$)/i.test(v)) return false;
    // space-less CJK personal name (family+given written together, e.g. 李明)
    if (/^[\\u3400-\\u9fff\\u3040-\\u30ff\\uac00-\\ud7af]{2,}$/.test(v)) return true;
    // otherwise require >= 2 Unicode-letter tokens (accepts José García, Иван Петров)
    try { return /^[\\p{L}][\\p{L}.'’-]*(\\s+[\\p{L}][\\p{L}.'’-]*)+$/u.test(v); }
    catch (e) { return /^[A-Za-z][A-Za-z.'’-]*(\\s+[A-Za-z][A-Za-z.'’-]*)+$/.test(v); }
  }
  function updateConfirmState() {
    const justOk = wordCount(verbJust.value) >= JUSTIFICATION_MIN_WORDS;
    const actorOk = actorIsNamedHuman(verbActor.value);
    const expiryNeeded = VERBS_NEEDING_EXPIRY.includes(activeVerb);
    const expiryOk = expiryNeeded ? !!verbExpiry.value : true;
    verbConfirm.disabled = !(justOk && actorOk && expiryOk);
    // Surface WHY the actor field is rejected (mirrors the justification hint).
    const actorHint = document.getElementById('verb-actor-hint');
    if (actorHint) {
      const v = (verbActor.value || '').trim();
      if (!v) {
        actorHint.removeAttribute('data-state');
        actorHint.textContent = 'Per A8 — name a person, not a team handle (e.g. D. Patel).';
      } else if (!actorOk) {
        actorHint.setAttribute('data-state', 'error');
        actorHint.textContent = 'Per A8 — "' + v + '" is not a named human. Use a person\\'s name (e.g. D. Patel), not a handle/team.';
      } else {
        actorHint.setAttribute('data-state', 'ok');
        actorHint.textContent = 'Named human ✓';
      }
    }
  }
  function openVerb(verb, targetId, targetName, targetType) {
    activeVerb = verb;
    activeTarget = { id: targetId, name: targetName, type: targetType };
    verbTitle.textContent = verb.replace(/_/g, ' ').toUpperCase() + ' — ' + targetName;
    verbContext.textContent =
      'Target ' + (targetType || 'finding') + ' ' + (targetId || '?') +
      ' · per amendment A8: named human + ≥' + JUSTIFICATION_MIN_WORDS +
      '-word justification + ' +
      (VERBS_NEEDING_EXPIRY.includes(verb) ? 'expiry required' : 'expiry not required');
    verbJust.value = '';
    verbActor.value = '';
    verbExpiry.value = '';
    verbExpiry.disabled = !VERBS_NEEDING_EXPIRY.includes(verb);
    updateConfirmState();
    verbModal.setAttribute('data-open', 'true');
    setTimeout(() => verbJust.focus(), 50);
  }
  function closeVerb() {
    verbModal.setAttribute('data-open', 'false');
    activeVerb = null;
    activeTarget = null;
  }
  verbJust.addEventListener('input', () => {
    const n = wordCount(verbJust.value);
    if (n >= JUSTIFICATION_MIN_WORDS) {
      verbJustHint.textContent = n + ' words · ok';
      verbJustHint.setAttribute('data-state', 'ok');
    } else {
      verbJustHint.textContent = n + ' / ' + JUSTIFICATION_MIN_WORDS + ' words · need ' + (JUSTIFICATION_MIN_WORDS - n) + ' more';
      verbJustHint.setAttribute('data-state', 'error');
    }
    updateConfirmState();
  });
  verbActor.addEventListener('input', updateConfirmState);
  verbExpiry.addEventListener('input', updateConfirmState);

  // ── alpha4: verb confirm persists to localStorage with hash chain ──
  verbConfirm.addEventListener('click', async () => {
    const allEntries = getAllActionEntries();
    const lastHash = allEntries.length
      ? (allEntries[allEntries.length - 1].this_action_hash || 'GENESIS')
      : 'GENESIS';
    const newEntry = {
      schema_version: '1.0',
      actor_name:     verbActor.value.trim(),
      actor_handle:   '@' + verbActor.value.trim().split(/\\s+/).join('').toLowerCase(),
      actor_role:     'Self-attested · client session',
      actor_role_tier: '1LoD',
      verb:           activeVerb,
      target_type:    activeTarget.type,
      target_id:      activeTarget.id,
      target_name:    activeTarget.name,
      timestamp:      new Date().toISOString(),
      justification:  verbJust.value,
      justification_min_words: JUSTIFICATION_MIN_WORDS,
      expiry:         verbExpiry.value || null,
      review_cadence_days: 30,
      dissenting_voice: null,
      linked_findings: [activeTarget.id],
      thresholds_at_time: {},
      previous_action_hash: lastHash,
      _local: true, // marks this as a localStorage entry vs embedded
    };
    // Re-audit fix (Claude defect #3): the write path must hash over EXACTLY
    // what verifyChain() recomputes — canonicalJson() (Python-matching ", "/": "
    // separators), stripping BOTH this_action_hash AND _local. The prior code
    // used JSON.stringify (compact, no spaces) and left _local in, so a local
    // entry's stored hash could never match the verifier's recompute — the
    // verifier then "papered over" it by exempting _local entries. Now write
    // and verify are symmetric, so local entries verify on their own merits.
    const eForHash = {};
    for (const k of Object.keys(newEntry)) {
      if (k !== 'this_action_hash' && k !== '_local') eForHash[k] = newEntry[k];
    }
    try { newEntry.this_action_hash = await sha256Hex(canonicalJson(eForHash)); }
    catch (e) { newEntry.this_action_hash = 'unhashed-' + Date.now(); }
    const local = loadLocalActions();
    local.push(newEntry);
    saveLocalActions(local);

    closeVerb();
    // Re-render the action log + verb summary so the new entry appears
    renderActionLog();
    renderVerbBar();
    // Re-audit fix (Claude defect #2): re-run the chain walk for the chrome
    // badge so it reflects the new entry immediately, not after a page reload.
    renderChainStatus();
  });
  verbCancel.addEventListener('click', closeVerb);
  verbModal.addEventListener('click', (e) => { if (e.target === verbModal) closeVerb(); });

  // ── Wire dynamic handlers (re-called after each renderAll) ──
  function wireDynamicHandlers() {
    document.querySelectorAll('.lineage-link').forEach((el) => {
      if (el.dataset.wired === '1') return;
      el.dataset.wired = '1';
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        openLineage(el.getAttribute('data-prov') || '{}', el.getAttribute('data-label') || 'Lineage');
      });
    });
    document.querySelectorAll('.verb-btn').forEach((b) => {
      if (b.dataset.wired === '1') return;
      b.dataset.wired = '1';
      b.addEventListener('click', () => {
        openVerb(
          b.dataset.verb,
          b.dataset.targetId || b.dataset.target || '?',
          b.dataset.targetName || b.dataset.targetId || '?',
          b.dataset.targetType || 'finding'
        );
      });
    });
    document.querySelectorAll('.queue-item').forEach((row) => {
      if (row.dataset.wired === '1') return;
      row.dataset.wired = '1';
      row.addEventListener('click', (e) => {
        if (e.target.closest && e.target.closest('button')) return;
        // Future: row click opens detail expand
      });
    });
  }

  // ── alpha4: keyboard nav (j/k navigate, c claim, g gate, e escalate, d dispo) ──
  let selectedQueueIdx = -1;
  function updateQueueSelection() {
    document.querySelectorAll('.queue-item').forEach((row, idx) => {
      if (idx === selectedQueueIdx) {
        row.setAttribute('data-selected', 'true');
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        row.removeAttribute('data-selected');
      }
    });
  }
  function getSelectedQueueRow() {
    const rows = document.querySelectorAll('.queue-item');
    return selectedQueueIdx >= 0 && selectedQueueIdx < rows.length ? rows[selectedQueueIdx] : null;
  }
  function fireVerbOnSelected(verb) {
    const row = getSelectedQueueRow();
    if (!row) return;
    const btn = row.querySelector('.verb-btn[data-verb="' + verb + '"]');
    if (btn) { btn.click(); return; }
    // Verb not on this row — open verb modal manually with row's target
    const findingId = row.querySelector('.verb-btn').dataset.targetId;
    const findingName = row.querySelector('.verb-btn').dataset.targetName;
    openVerb(verb, findingId, findingName, 'finding');
  }
  document.addEventListener('keydown', (e) => {
    // Don't capture when typing in modal inputs
    if (e.target.matches && e.target.matches('input, textarea, select')) return;
    if (verbModal.getAttribute('data-open') === 'true' || modal.getAttribute('data-open') === 'true') {
      if (e.key === 'Escape') {
        if (verbModal.getAttribute('data-open') === 'true') closeVerb();
        if (modal.getAttribute('data-open') === 'true') closeLineage();
      }
      return;
    }
    const rows = document.querySelectorAll('.queue-item');
    if (e.key === 'j') {
      if (selectedQueueIdx < rows.length - 1) selectedQueueIdx++;
      else selectedQueueIdx = 0;
      updateQueueSelection();
      e.preventDefault();
    } else if (e.key === 'k') {
      if (selectedQueueIdx > 0) selectedQueueIdx--;
      else selectedQueueIdx = rows.length - 1;
      updateQueueSelection();
      e.preventDefault();
    } else if (e.key === 'c') {
      fireVerbOnSelected('claim');
      e.preventDefault();
    } else if (e.key === 'g') {
      fireVerbOnSelected('gate');
      e.preventDefault();
    } else if (e.key === 'e') {
      fireVerbOnSelected('escalate');
      e.preventDefault();
    } else if (e.key === 'd') {
      fireVerbOnSelected('dispo');
      e.preventDefault();
    }
  });

  // ── alpha4: verify-projection button now reports render-from-data ──
  const verifyBtn = document.getElementById('verify-projection-btn');
  if (verifyBtn) {
    verifyBtn.addEventListener('click', () => {
      const meta = PROJECTION.meta || {};
      const counts = meta.counts || {};
      const cascadeEdges = ((PROJECTION.cascade_graph || {}).edges || []);
      const firingEdges = cascadeEdges.filter((e) => e.currently_firing);
      const actionLog = PROJECTION.action_log || {};
      const exposure = (PROJECTION.exposure && PROJECTION.exposure.portfolio_total) || {};
      const materiality = PROJECTION.materiality || {};
      const triggeredTriggers = Object.entries(materiality)
        .filter(([k, v]) => v.status === 'TRIGGERED').map(([k]) => k);
      const local = loadLocalActions();
      const summary = [
        '╔═══════════════════════════════════════════════════════════╗',
        '║  ALPHA4 · RENDER-FROM-DATA · NOT RENDER-BESIDE-DATA       ║',
        '╚═══════════════════════════════════════════════════════════╝',
        '',
        'Every dynamic surface on this page is JS-built from the embedded',
        'projection. The drift the prior alpha3 verify-button detected by',
        'comparison cannot happen here — there is only one source.',
        '',
        'Artefact:    ' + (meta.artefact_version || '?'),
        'Schema:      v' + (meta.schema_version || '?'),
        'Period:      ' + (meta.period || '?'),
        '',
        '── Counts ─────────────────────────',
        'Findings:    ' + (counts.findings_total || 0) +
          ' (' + (counts.findings_red || 0) + 'R / ' + (counts.findings_amber || 0) + 'A / ' + (counts.findings_green || 0) + 'G)',
        'Domains:     ' + (counts.domains_total || 0) +
          ' (' + (counts.domains_red || 0) + 'R / ' + (counts.domains_amber || 0) + 'A / ' + (counts.domains_green || 0) + 'G)',
        '',
        '── Cascade ───────────────────────',
        'Total edges:  ' + cascadeEdges.length,
        'Firing now:   ' + firingEdges.length,
        '',
        '── Materiality ──────────────────',
        'Triggered:    ' + (triggeredTriggers.length ? triggeredTriggers.join(', ') : 'none'),
        '',
        '── Exposure ─────────────────────',
        'P50:          $' + ((exposure.p50_usd || 0) / 1e6).toFixed(1) + 'M',
        'P95:          $' + ((exposure.p95_usd || 0) / 1e6).toFixed(1) + 'M',
        '',
        '── Action log ───────────────────',
        'Embedded:     ' + (actionLog.total_entries || 0) + ' entries',
        'LocalStorage: ' + local.length + ' entries (alpha4 verb confirmations)',
        'Chain:        ' + (actionLog.chain_status || '?') +
          (local.length ? ' (extended client-side)' : ''),
      ].join('\\n');
      // Non-blocking overlay (was a native alert(), which froze automated
      // reviewers' tooling, read as a page hang, and was the weakest UX on the
      // page's flagship honesty affordance — QA-pass finding).
      let ov = document.getElementById('verify-overlay');
      if (!ov) {
        ov = document.createElement('div');
        ov.id = 'verify-overlay';
        ov.setAttribute('role', 'dialog');
        ov.setAttribute('aria-label', 'Render-from-data verification');
        ov.style.cssText = 'position:fixed; inset:0; z-index:200; background:rgba(0,0,0,.55); display:flex; align-items:center; justify-content:center; padding:24px';
        ov.innerHTML = '<div style="background:var(--surface-1); border:1px solid var(--border); border-radius:10px; max-width:720px; max-height:80vh; overflow:auto; padding:18px 22px">'
          + '<pre id="verify-overlay-pre" style="margin:0; font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text); white-space:pre-wrap"></pre>'
          + '<button id="verify-overlay-close" type="button" style="margin-top:12px; font-family:var(--font-mono); background:none; border:1px solid var(--border); border-radius:6px; color:var(--text-mut); padding:4px 14px; cursor:pointer">close · esc</button></div>';
        document.body.appendChild(ov);
        const closeOv = () => { ov.style.display = 'none'; };
        ov.addEventListener('click', (e) => { if (e.target === ov) closeOv(); });
        document.getElementById('verify-overlay-close').addEventListener('click', closeOv);
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeOv(); });
      }
      document.getElementById('verify-overlay-pre').textContent = summary;
      ov.style.display = 'flex';
      document.getElementById('verify-overlay-close').focus();
    });
  }

  // ── Conservation hook (IA Stage B, spec §6): dumps every data-target's
  // rendered text so classic and new builds can be fingerprint-compared
  // (C26a–e). Present in BOTH views; returns {target: textContent}.
  window.__dumpTargets = function () {
    const out = {};
    document.querySelectorAll('[data-target]').forEach(function (el) {
      out[el.getAttribute('data-target')] = el.textContent;
    });
    out['__banner__'] = (document.querySelector('.disclosure') || {}).textContent || '';
    return out;
  };

  // ── Boot: render everything from the embedded projection ──
  renderAll();
})();
"""


# ── step 4: lineage-link wrapper ─────────────────────────────────────────────

def lineage_span(value_text: str, provenance: Dict[str, Any], label: str = "") -> str:
    """Wrap a value in a span that opens the lineage modal on click.

    Used by app renderers (ai_gov, generic_register) per amendment A2 to
    surface clickable provenance on every numeric value. Replaces the
    title-attribute hover-card minimum bar that alpha2 shipped.
    """
    if not provenance:
        return value_text
    # JSON-encode the provenance object for data-prov attribute. html.escape
    # the JSON so quotes don't break the attribute.
    prov_json = json.dumps(provenance, default=str)
    safe_prov = prov_json.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    safe_label = (label or "").replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<span class="lineage-link" data-prov="{safe_prov}" data-label="{safe_label}">{value_text}</span>'


def _hash_artefact(html_str: str) -> str:
    """SHA-256 of the rendered HTML body (excluding the hash itself).
    Per amendment A11: artefact hash in footer for tamper-evidence.

    We compute by replacing the placeholder with a known sentinel, hashing,
    then re-injecting the real digest. Step 11 of the build will harden this.
    """
    sentinel = "{{ARTEFACT_HASH_PLACEHOLDER}}"
    if sentinel not in html_str:
        return ""
    canonicalized = html_str.replace(sentinel, "<<<HASH_INPUT>>>")
    return hashlib.sha256(canonicalized.encode("utf-8")).hexdigest()


def render_v2_from_projection(projection: Dict[str, Any]) -> str:
    """Pure renderer — input projection dict, output HTML.

    v2.0a-alpha2 — per the Claude review on alpha1: the renderer must
    consume the projection, not re-build it. This function takes the
    projection as a parameter, has no I/O, and is deterministic
    relative to its input. Drift between projection JSON and rendered
    HTML is architecturally impossible because they share one source.
    """

    # Inline shared CSS + JS assets.
    base_styles = _read_asset("report_styles.css")
    base_script = _read_asset("report_script.js")
    styles = base_styles + "\n\n" + _V2_STYLE_INJECT
    script = base_script + "\n\n" + _V2_SCRIPT_INJECT

    # 3. M3: outer shell now emits the 5-act IA directly; the per-app render
    # functions are deferred to M4 (AI Gov depth) and M5 (register port).
    # Keeping the imports so M4/M5 can re-engage them without code archaeology.
    _ = ai_gov, generic_register  # noqa: F841 — referenced to keep imports live

    # 4. Assemble — ALL labels read from projection.meta. No module-level constants.
    period         = projection["meta"]["period"]
    generated_at   = projection["meta"]["generated_at"]
    counts         = projection["meta"]["counts"]
    artefact_label = projection["meta"]["artefact_version"]  # alpha3: from projection, not module constant
    schema_version = projection["meta"]["schema_version"]

    # alpha3: embed the projection JSON inline so the artefact contains the
    # data it was rendered from. This is the architectural lock — the HTML
    # cannot drift from its source because the source IS the HTML.
    embedded_projection_json = json.dumps(projection, default=str, sort_keys=True)
    # Escape `</script>` inside the JSON so it can't terminate the script tag.
    embedded_projection_json = embedded_projection_json.replace("</", "<\\/")

    pre_hash_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>risk-as-code-agent · {period}</title>

  <!-- v2.0a-alpha4 M4.5 · self-contained: no external font CDN, no external
       network call. System-font fallback stack in --font-sans / --font-mono
       inside report_styles.css gives a clean engineering-grade read on every
       platform. Audit / air-gapped environments stay clean. -->

  <!-- v2.0a-alpha4: embedded projection. The HTML literally contains the
       data it was rendered from. Self-verifying. Cannot drift. -->
  <script type="application/json" id="projection-source" data-schema-version="{schema_version}" data-artefact-version="{artefact_label}">
{embedded_projection_json}
  </script>

  <style>{styles}</style>
</head>
<body data-lens="engineer" data-act="signal" data-domain="all">

  <!-- ═══ Disclosure banner ═══ -->
  <div class="disclosure">
    <span>A demonstrator on <b>synthetic</b> telemetry. Firm-specific dollar figures are illustrative; the risk logic and every threshold's public source are real, and each number traces to it.</span>
  </div>

  <!-- ═══ Top chrome — brand only. r44 (external review, verified): the header
       ran TWO identity systems (persona chips + role lens) before a single
       number rendered. The role lens on the spine is the reading question;
       the named signing personas retreat to the verb bar where signing
       actually happens; the chain chip retreats to the hash-chain section. ═══ -->
  <header class="chrome">
    <div class="brand">
      <span class="brand-mark">risk-as-code-agent</span>
    </div>
  </header>

  <!-- ═══ IA spine — ONE navigation system (Stage B, spec v2.2). The five act
       names + descriptions re-home here and into the map overlay (C26f);
       the 01–05 numerals retire (classic.html keeps them forever). ═══ -->
  <nav class="spine" id="spine" aria-label="Argument spine — role-sequenced">
    <!-- JS renders role drop-down + the role path's nodes from PROJECTION.ia -->
  </nav>

  <!-- ═══ Workspace — left rail (domain filter) + main panel ═══ -->
  <div class="workspace">
    <aside class="rail" role="tablist" aria-label="Domain">
      <div class="rail-label">domains</div>
      <div class="rail-item" data-domain="all" aria-pressed="true">
        <span class="rail-name">all_portfolio</span><span class="rail-badge" data-target="rail-count-all">{counts["findings_total"]}</span>
      </div>
      <div class="rail-divider"></div>
      <div data-target="rail-domains">
        <!-- JS fills domain rail items from PROJECTION.domains -->
      </div>
    </aside>

    <main class="panel">

      <!-- round-24 (GROK P0: leadership dualism): the workbench declares its
           altitude to the leadership lens — the Board surface is board.html;
           this page is the drill-down. Chrome only (no data), leadership-only
           via CSS; auto-redirecting the role was DECLINED (roles re-sequence,
           never gate — spec §, user-ratified round-16). -->
      <div class="altitude-bar" data-target="altitude-bar">you are in the drill-down ·
        the five asks — <b>ENDORSE · APPROVE · REQUIRE · REQUIRE · NOTE</b> — live on
        <a href="board.html">the Board brief, one page ↪</a></div>

      <!-- ═══ Block C · Executive hero band — the FIRST painted element so the
           board reads the 10-second answer before any act-specific title ═══ -->
      <div class="exec-hero" data-target="exec-hero"></div>

      <!-- panel header — eyebrow + title updated by JS per act/domain/lens -->
      <header class="panel-header">
        <div class="panel-eyebrow" id="panel-eyebrow">signal  ·  all_portfolio  ·  <span class="mono">engineer</span></div>
        <h1 class="panel-title" id="panel-title">Portfolio risk · 2026-Q2</h1>\n        <div class="ia-thesis" id="ia-thesis"></div>
      </header>

      <!-- ═══ AI Governance deep-dive (visible only when domain=ai_gov) ═══ -->
      <div class="ai-gov-pane">
        <section class="section" data-node="ai-gov">
          <div class="section-eyebrow">HITL posture · MCP spec §HITL · OWASP MCP #1 · A8 expiry rule</div>
          <div data-target="ai-gov-hitl"></div>
        </section>

        <section class="section" data-node="ai-gov">
          <div class="section-eyebrow">model inventory · production · shadow · staging — hover for verbs</div>
          <div data-target="ai-gov-models"></div>
        </section>

        <section class="section" data-node="ai-gov">
          <div class="section-eyebrow">agent inventory · MCP servers · scope · 24h violations · HITL</div>
          <div data-target="ai-gov-agents"></div>
        </section>

        <section class="section" data-node="ai-gov">
          <div class="section-eyebrow">MCP supply chain · vendor tier · hash-pin · last-scan · KEV</div>
          <div data-target="ai-gov-mcp"></div>
        </section>

        <section class="section" data-node="ai-gov">
          <div class="section-eyebrow">trace · live-tail · 10 most recent tool calls — flagged events highlighted</div>
          <div data-target="ai-gov-trace"></div>
        </section>
      </div>

      <!-- ═══ DECIDE · the Monday-morning screen (first thing a 2LoD sees) ═══ -->
      <section class="section" data-node="docket">
        <div class="section-eyebrow">monday morning · where each decision actually gets made — and what escalating costs</div>
        <div data-target="monday-morning"></div>
      </section>

      <!-- ═══ DECIDE · org reality (round-23: cold-GROK P1 — org_context was
           only legible row-by-row inside the docket; this is the aggregate) ═══ -->
      <section class="section" data-node="docket">
        <div class="section-eyebrow">org reality · portfolio-wide · who answers for the reds, which committee decides, and the A8 gap</div>
        <div data-target="org-reality"></div>
        <div style="margin-top:18px"><div style="font-family:var(--font-mono); font-size:var(--t-micro); letter-spacing:.14em; text-transform:uppercase; color:var(--text-mut); margin-bottom:6px">DECIDE · the operating-model delta — chase → re-perform</div><div data-target="operating-model"></div></div>
      </section>

      <!-- ═══ SIGNAL act ═══ -->
      <section class="section" data-node="register">
        <div class="section-eyebrow" data-target="queue-summary">verb queue · loading…</div>
        <div class="queue" data-target="queue-rows" tabindex="0" aria-label="Intervention queue, use j/k to navigate"></div>
      </section>

      <section class="section" data-node="register">
        <div class="section-eyebrow">coverage matrix · all patterns × domains · out-of-scope cells dashed</div>
        <div data-target="coverage-matrix"></div>
      </section>

      <section class="section" data-node="docket">
        <div class="section-eyebrow">decision point · per amendment A8</div>
        <div data-target="pause-prompt"></div>
      </section>

      <!-- ═══ PATTERN act ═══ -->
      <section class="section" data-node="register">
        <div class="section-eyebrow">pattern primer · click to expand</div>
        <div data-target="pattern-primer"></div>
      </section>

      <section class="section" data-node="cascade">
        <div class="section-eyebrow">cascade trace · the substrate causal chain</div>
        <div data-target="cascade-card"></div>
      </section>

      <section class="section" data-node="attack">
        <div class="section-eyebrow">threshold provenance · every cited bound</div>
        <div data-target="evidence-ribbons"></div>
      </section>

      <!-- ═══ IMPACT act ═══ -->
      <section class="section" data-node="stake">
        <div class="section-eyebrow">portfolio · inherent → compensating controls → residual · portfolio-wide (rail does not filter this)</div>
        <div data-target="translation-card-portfolio"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">defense layers · NIST CSF 2.0 5-function coverage · portfolio-wide</div>
        <div data-target="defense-layers"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">impact faces · 5 dimensions of who absorbs (residual) · portfolio-wide</div>
        <div class="impact-summary" data-target="exposure-cards"></div>
        <div class="impact-secondary" data-target="impact-secondary"></div>
        <div class="impact-faces" data-target="impact-faces"></div>
      </section>

      <!-- ═══ E1 · the shared-dependency layer — which single thing takes the
           most of the tail (the axis pattern-to-pattern edges cannot express:
           a region loss, the customer auth plane, etcd — one structural event
           UNDER several risks at once) ═══ -->
      <section class="section" data-node="stake">
        <div class="section-eyebrow">shared dependencies · portfolio-wide · the concentration question, priced — remove each dependency, same seed, and watch P95 move</div>
        <div data-target="dependency-tornado"></div>
      </section>

      <section class="section" data-node="attack">
        <div class="section-eyebrow">calibration appendix · sensitivity tornado — how far the answer moves if the judgment is wrong · portfolio-wide</div>
        <div data-target="sensitivity-panel"></div>
      </section>

      <section class="section" data-node="regulation">
        <div class="section-eyebrow">regulatory residual · how much stress-P95 already sits under each triggered obligation · portfolio-wide</div>
        <div data-target="regulation-residual"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">risk lifecycle · inherent → controls → residual → materiality → decision</div>
        <div data-target="per-pattern-translation"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">actuals · 12-month window · real events (not modeled) · portfolio-wide</div>
        <div class="actuals-grid" data-target="actuals-grid"></div>
        <div class="actuals-footnote" data-target="actuals-footnote" style="font-family:var(--font-mono); font-size:var(--t-micro); color:var(--text-mut); margin-top:8px;"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">trend clusters · recurrence per pattern · portfolio-wide</div>
        <div data-target="recurrence-list"></div>
      </section>

      <section class="section" data-node="stake">
        <div class="section-eyebrow">drill-down · team · function · product</div>
        <div class="group-tab-strip" role="tablist" aria-label="Group pivot">
          <button class="group-tab-btn" data-group="team"     aria-pressed="true"  type="button">by team</button>
          <button class="group-tab-btn" data-group="function" aria-pressed="false" type="button">by function</button>
          <button class="group-tab-btn" data-group="product"  aria-pressed="false" type="button">by product</button>
        </div>
        <div data-target="group-pivot"></div>
      </section>

      <!-- ═══ DECIDE act · verb affordances (existing alpha3 verb-bar lives here) ═══ -->
      <section class="section" data-node="docket">
        <div class="section-eyebrow" data-target="verb-summary">verb affordances · loading…</div>
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin:6px 0 10px">
          <span style="font-family:var(--font-mono, ui-monospace, monospace); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:rgba(232,223,211,.45)">signing identity · per A8 every verb needs a named human</span>
          <div class="user-strip" role="tablist" aria-label="Switch signing identity">
            <button class="user-chip" data-lens="engineer" data-default-act="signal" aria-pressed="true" type="button">
              <span class="user-chip-avatar">DP</span>
              <span><span class="user-chip-name">D. Patel</span> · <span class="user-chip-role">1LoD eng</span></span>
            </button>
            <button class="user-chip" data-lens="exec" data-default-act="impact" aria-pressed="false" type="button">
              <span class="user-chip-avatar">SK</span>
              <span><span class="user-chip-name">S. Khoury</span> · <span class="user-chip-role">2LoD exec</span></span>
            </button>
            <button class="user-chip" data-lens="auditor" data-default-act="attest" aria-pressed="false" type="button">
              <span class="user-chip-avatar">MO</span>
              <span><span class="user-chip-name">M. Okonkwo</span> · <span class="user-chip-role">3LoD audit</span></span>
            </button>
          </div>
          <div class="identity-ribbon" title="Per A8 — every action requires named human + 12-word justification + expiry">
            <span class="identity-ribbon-label">acting as</span>
            <span class="identity-ribbon-name" id="ribbon-name">D. Patel</span>
            <span class="identity-ribbon-role" id="ribbon-role">· 1LoD · Director, AI Platform</span>
          </div>
        </div>
        <div class="verb-bar" data-target="verb-bar"></div>
      </section>

      <!-- ═══ ATTEST act ═══ -->
      <section class="section" data-node="regulation">
        <div class="section-eyebrow">regulatory materiality · article-level disclosure triggers · portfolio-wide</div>
        <div class="materiality-row" data-target="register-materiality"></div>
        <div class="materiality-grid" data-target="materiality-grid"></div>
      </section>

      <section class="section" data-node="attack">
        <div class="section-eyebrow">internal audit posture · the 3LoD lifecycle — responses, target dates, validation, repeats</div>
        <div data-target="internal-audit"></div>
      </section>

      <section class="section" data-node="attack">
        <div class="section-eyebrow">hash-chain integrity · per amendment A1</div>
        <div class="chain-status" id="chain-status" role="status" aria-live="polite" title="Per A1 — SHA-256 hash-chained action log integrity"
             data-target="chain-status-text" style="margin:4px 0 10px">chain · loading…</div>
        <div data-target="chain-detail"></div>
      </section>

      <section class="section" data-node="attack">
        <div class="section-eyebrow">action log · hash-chained · append-only</div>
        <div class="action-log event-stream" data-target="action-log"></div>
      </section>

      <!-- ═══ Generic register hidden under attest for now — to be folded in M5 ═══ -->
      <section class="section" data-node="register">
        <div class="section-eyebrow">findings register · pattern × domain</div>
        <div class="register-summary">
          <div class="zone-eyebrow" data-target="register-summary-eyebrow">register · loading…</div>
          <div class="summary-row" data-target="register-summary-row"></div>
          <div style="margin-top:12px"><div style="font-family:var(--font-mono); font-size:var(--t-micro); letter-spacing:.14em; text-transform:uppercase; color:var(--text-mut); margin-bottom:5px">the catalog rollup — parents → children, evidenced</div><div data-target="risk-rollup"></div></div>
        </div>
        <div class="register-exposure" data-target="register-exposure"></div>
        <div class="register-exposure" data-target="register-impact-faces"></div>
        <div class="table-scroll">
          <table class="register-table">
            <thead>
              <tr><th>RAG</th><th>ID</th><th>Pattern</th><th>Domain</th><th>Signal</th><th>Threshold</th><th>Owner</th><th>Treatment · age</th><th>First detected</th></tr>
            </thead>
            <tbody data-target="register-tbody"></tbody>
          </table>
        </div>
      </section>

      <!-- ═══ THE CHOICE · closing decision (r51) — two priced strategies and
           the signed hold. Every dollar recomputes from sealed leaves (C39);
           program cost is declared not-modeled, never implied. ═══ -->
      <section class="section" data-node="strategy">
        <style>
          .sc-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 10px; }}
          @media (max-width: 900px) {{ .sc-grid {{ grid-template-columns: 1fr; }} }}
          .sc-tile {{ border: 1px solid rgba(214,196,162,.30); border-radius: 12px; padding: 16px 18px; background: rgba(201,162,107,.05); display: flex; flex-direction: column; }}
          .sc-verb {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: #C9A26B; }}
          .sc-name {{ font-size: 19px; font-weight: 700; margin: 4px 0 2px; }}
          .sc-thesis {{ font-size: 13px; color: rgba(232,223,211,.7); line-height: 1.5; }}
          .sc-price {{ font-size: 26px; font-weight: 700; margin: 10px 0 2px; }}
          .sc-basis {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 10.5px; color: rgba(232,223,211,.5); line-height: 1.55; }}
          .sc-row {{ font-size: 13px; color: rgba(232,223,211,.75); margin-top: 9px; line-height: 1.55; }}
          .sc-label {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: rgba(232,223,211,.45); }}
          .sc-flag {{ display: inline-block; font-family: var(--font-mono, ui-monospace, monospace); font-size: 10px; letter-spacing: .05em; border: 1px solid; border-radius: 6px; padding: 1px 7px; margin: 3px 5px 0 0; }}
          .sc-node {{ display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; padding: 3px 0; border-bottom: 1px dashed rgba(214,196,162,.16); }}
          .sc-strip {{ border: 1px solid rgba(214,196,162,.30); border-radius: 12px; padding: 13px 18px; margin-top: 14px; }}
        </style>
        <div class="section-eyebrow">the choice · closing decision — two priced strategies, one signed hold; the levers price outcomes, program cost is not modeled</div>
        <div data-target="strategy-chooser"></div>
      </section>

      <!-- ═══ THE READ · closing chapter (r43) — the whole argument in one picture ═══ -->
      <section class="section" data-node="story">
        <style>
          .story-flowwrap {{ position: relative; width: 100%; max-width: 990px; margin: 2px auto 10px; }}
          #story-flow-cv {{ width: 100%; display: block; }}
          .story-walker {{ display: flex; align-items: center; gap: 14px; margin: 10px auto 0; max-width: 990px;
            background: rgba(201,162,107,.07); border: 1px solid rgba(214,196,162,.30); border-radius: 12px; padding: 12px 16px; }}
          .story-wbtn {{ background: rgba(201,162,107,.16); border: 1px solid #C9A26B; border-radius: 9px; color: #C9A26B;
            font: inherit; font-size: 16px; font-weight: 700; padding: 8px 18px; cursor: pointer; }}
          .story-wbtn:hover {{ background: rgba(201,162,107,.30); }}
          .story-wcap {{ flex: 1; font-size: 14.5px; color: rgba(232,223,211,.68); line-height: 1.45; }}
          .story-wstep {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 11px; color: #C9A26B; margin-right: 10px; letter-spacing: .1em; }}
          .story-wlink {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 11.5px; color: #C9A26B; text-decoration: none;
            border-bottom: 1px solid rgba(214,196,162,.30); margin-left: 12px; white-space: nowrap; cursor: pointer; }}
        </style>
        <div class="section-eyebrow">the read · closing chapter — the whole argument in one animated picture; every step opens its evidence node</div>
        <div class="story-flowwrap"><canvas id="story-flow-cv" role="img" aria-label="Failure patterns flow through controls and the cascade into one loss distribution, sliced three ways"></canvas></div>
        <div class="story-walker">
          <button class="story-wbtn" id="story-prev" type="button" aria-label="previous step">◂</button>
          <div class="story-wcap"><span class="story-wstep" id="story-step"></span><span id="story-cap"></span>
            <a id="story-link" class="story-wlink">open the evidence →</a></div>
          <button class="story-wbtn" id="story-next" type="button" aria-label="next step">▸</button>
        </div>
        <div data-target="story-flow" style="font-family:var(--font-mono, ui-monospace, monospace); font-size:11px; color:rgba(232,223,211,.45); max-width:990px; margin:8px auto 0"></div>
      </section>

    </main>
  </div>

  <!-- ═══ Footer ═══ -->
  <footer class="foot">
    <span><b>{artefact_label}</b> · period {period} · generated {generated_at}</span>
    <span>
      <span data-target="footer-counts">{counts["findings_total"]} findings · {counts["domains_total"]} domains</span> ·
      <a href="archive/classic.html" class="classic-link" title="the pre-spine v2.0a page, frozen 2026-07-14 — every panel, one scroll">classic view ↗</a> ·
      <button id="verify-projection-btn" class="verify-projection-btn" type="button" title="Click to verify: the projection JSON is embedded in this file; the renderer reads from it; what you see is what was rendered.">projection embedded ↪</button>
    </span>
    <span class="artefact-seal" title="Keyless SHA-256 checksum over the rendered HTML body (excluding the hash sentinel) — NOT a cryptographic signature. Any post-generation edit invalidates this digest, but a keyless hash does not prevent someone re-hashing modified content and does not attest authorship or authority. In production this would be counter-signed by a named 2LoD attester.">
      SHA-256 <code class="mono">{{{{ARTEFACT_HASH_PLACEHOLDER}}}}</code>
      · <span class="generated-by">generated-by: risk-as-code-agent::{artefact_label} pipeline</span>
    </span>
    <a href="https://github.com/Jiten76/risk-as-code-agent" target="_blank" rel="noopener" style="color:var(--interactive)">github.com/Jiten76/risk-as-code-agent</a>
  </footer>

  <!-- v2.0a step 4: lineage modal. Lives at body root, shown on click of any .lineage-link element. -->
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

  <!-- v2.0a step 5: verb confirm modal. Opened by clicking any .verb-btn. -->
  <div id="verb-modal" class="verb-modal" data-open="false" role="dialog" aria-modal="true" aria-labelledby="verb-modal-title">
    <form id="verb-form" class="verb-dialog" onsubmit="return false;">
      <h3 id="verb-modal-title" class="verb-dialog-title">Confirm verb</h3>
      <div id="verb-context" class="verb-field-hint" style="margin-bottom:var(--s-3); color:var(--text-muted)"></div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-actor">Named human (actor)</label>
        <input id="verb-actor" type="text" placeholder="e.g., D. Patel" autocomplete="off" />
        <div id="verb-actor-hint" class="verb-field-hint">Per A8 — name a person, not a team handle (e.g. D. Patel).</div>
      </div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-justification">Justification (≥12 words)</label>
        <textarea id="verb-justification" placeholder="Risk-specific justification referencing the signal value, threshold, compensating-control gap, and treatment path being accepted or gated..."></textarea>
        <div id="verb-justification-hint" class="verb-field-hint" data-state="error">0 / 12 words · need 12 more</div>
      </div>
      <div class="verb-field">
        <label class="verb-field-label" for="verb-expiry">Expiry (required for gate / accept / require_eval / restrict_scope)</label>
        <input id="verb-expiry" type="date" />
        <div class="verb-field-hint">Per A8 — actions without expiry become shelfware.</div>
      </div>
      <div class="verb-dialog-actions">
        <button id="verb-cancel-btn" type="button" class="verb-dialog-cancel">Cancel (ESC)</button>
        <button id="verb-confirm-btn" type="button" class="verb-dialog-confirm" disabled>Confirm</button>
      </div>
    </form>
  </div>

  <script>{script}</script>
</body>
</html>"""

    # 5. Compute artefact hash + inject (A11)
    digest = _hash_artefact(pre_hash_html)
    return pre_hash_html.replace("{{ARTEFACT_HASH_PLACEHOLDER}}", digest)


def render_v2_report(
    report: Dict[str, Any],
    history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Convenience: build projection from pipeline output then render.

    Calls render_v2_from_projection internally. Use write_v2_report() for
    the drift-free file flow (writes projection JSON then renders from it).
    """
    if history is None:
        history = generate_history(_scenario_map_from_report(report))
    projection = make_projection(report, history)
    return render_v2_from_projection(projection)


def write_v2_report(
    report: Dict[str, Any],
    output_path: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """Drift-free generation: build projection → write JSON → load JSON → render.

    Per the Claude review on alpha1: writing the projection then reading
    it back BEFORE rendering proves the architectural contract — the same
    JSON that ships as evidence is exactly the input the renderer consumed.

    Returns a dict with both written paths.
    """
    if history is None:
        history = generate_history(_scenario_map_from_report(report))
    projection = make_projection(report, history)

    # Resolve output paths
    period = projection["meta"]["period"]
    os.makedirs("outputs/v2_0a", exist_ok=True)
    if output_path is None:
        output_path = f"outputs/v2_0a/{period}_v2_0a_alpha2.html"
    projection_path = f"outputs/v2_0a/{period}_projection.json"

    # 1. Write projection JSON — this is the engine's only output
    Path(projection_path).write_text(
        json.dumps(projection, indent=2, default=str, sort_keys=True),
        encoding="utf-8",
    )

    # 2. Read it back — proves the round-trip contract; if this drops a
    #    field the renderer needs, we know immediately rather than via
    #    silent drift between JSON-on-disk and HTML
    loaded_projection = json.loads(Path(projection_path).read_text(encoding="utf-8"))

    # 3. Render HTML from the LOADED projection (not the in-memory one)
    html_str = render_v2_from_projection(loaded_projection)

    # 4. Write HTML
    Path(output_path).write_text(html_str, encoding="utf-8")

    return {"html": output_path, "projection": projection_path}
