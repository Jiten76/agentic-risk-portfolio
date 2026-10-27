"""
validation_page (rac) — the Model Validation Package as ONE surface.

Round-17 external ask (cold examiner + hiring-manager personas): "the package a
model-validation function would request" — composed ENTIRELY from the sealed
projection. Nothing here is new analysis: it is the engine spec, sampling error,
sensitivity tornado, σ-sweep, and challenged-judgment log that already ship in
the workbench, re-sequenced as the dossier an examiner reads first.

ZERO-DRIFT CONTRACT: the page embeds the sealed projection and hydrates every
number client-side (render-from-data, same as index/read/classic). The only
authored strings are chrome and the verbatim disclosure ribbon. Gated by
validation_sha256 freshness in qa/conservation_report.json and by verify_bundle
B10 (numeric-leaf equality across all rac views).

Build:  python3 -c "import sys; sys.path.insert(0,'.'); from utils.validation_page import write_validation_page; write_validation_page()"
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_DISCLOSURE = ("A demonstrator on <b>synthetic</b> telemetry. Firm-specific dollar figures are "
               "illustrative; the risk logic and every threshold's public source are real, and "
               "each number traces to it.")

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>risk-as-code-agent · __PERIOD__ · model validation package</title>
<style>
:root {
  --bg: #14110D; --text: #E8DFD3; --muted: rgba(232,223,211,.62); --faint: rgba(232,223,211,.36);
  --line: rgba(214,196,162,.16); --amber: #C9A26B; --red: #C84A4A; --green: #6BAF7A;
  --serif: 'Iowan Old Style', 'Palatino Nova', Palatino, 'Book Antiqua', Georgia, serif;
  --mono: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--serif); line-height: 1.6; }
body::before { content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(900px 600px at 85% -10%, rgba(201,162,107,.10), transparent 60%); }
.ribbon { font-family: var(--mono); font-size: 11.5px; color: rgba(20,17,13,.92); background: var(--amber); padding: 7px 22px; }
.shell { max-width: 880px; margin: 0 auto; padding: 26px 30px 70px; }
.masthead { display: flex; justify-content: space-between; align-items: baseline; gap: 14px; flex-wrap: wrap;
  font-family: var(--mono); font-size: 12.5px; color: var(--faint); padding-bottom: 18px; border-bottom: 1px solid var(--line); }
.masthead b { color: var(--muted); font-weight: 500; }
.masthead a { color: var(--muted); text-decoration: none; border: 1px solid var(--line); border-radius: 999px; padding: 3px 12px; }
.masthead a:hover { color: var(--amber); }
h1 { font-size: clamp(22px, 2.4vw, 30px); font-weight: 400; margin: 26px 0 6px; }
h2 { font-family: var(--mono); font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: var(--amber);
  margin: 34px 0 10px; padding-top: 16px; border-top: 1px solid var(--line); }
p.lede { color: var(--muted); max-width: 62ch; }
table { border-collapse: collapse; width: 100%; font-family: var(--mono); font-size: 12px; margin: 8px 0; }
th { text-align: left; color: var(--faint); font-weight: 500; padding: 5px 10px 5px 0; border-bottom: 1px solid var(--line); }
td { padding: 5px 10px 5px 0; border-bottom: 1px solid rgba(214,196,162,.07); color: var(--muted); vertical-align: top; }
td.n { color: var(--text); white-space: nowrap; }
.note { font-family: var(--mono); font-size: 11px; color: var(--faint); line-height: 1.55; margin: 6px 0 0; max-width: 76ch; }
.judg { border-left: 2px solid var(--line); padding: 8px 0 8px 16px; margin: 12px 0; }
.judg .q { color: var(--text); }
.judg .m { font-family: var(--mono); font-size: 11.5px; color: var(--muted); margin-top: 4px; }
.judg .c { font-family: var(--mono); font-size: 11.5px; color: var(--amber); margin-top: 4px; }
.openitem { border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; margin: 10px 0; font-size: 14.5px; color: var(--muted); background: rgba(20,17,13,.35); }
.openitem b { color: var(--text); font-weight: 500; }
/* mobile: tables scroll inside themselves; nowrap cells release (round-18
   sweep catch: the dossier shipped 743px wide at a 390px viewport) */
@media (max-width: 640px) {
  table { display: block; overflow-x: auto; }
  td.n { white-space: normal; }
  .masthead { gap: 8px; }
}
/* round-24.5 (user): the dossier speaks the platform read grammar — one-viewport
   chapter accordion, glass panels, keys 1/2/3 — same shell as the reads/tour. */
.masthead { max-width: 1060px; margin: 0 auto; padding: 12px 32px 0; border-bottom: 0; }
@media (min-width: 720px) {
  body { height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
  .stage { flex: 1; min-height: 0; display: flex; flex-direction: column; max-width: 1060px; width: 100%; margin: 0 auto; padding: 0 32px 8px; }
  .act { display: flex; flex-direction: column; min-height: 0; border: 1px solid var(--line); border-radius: 14px; margin: 4px 0;
    background: rgba(20,17,13,.55); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
  .act.open { flex: 1; background: rgba(43,37,31,.78); border-color: rgba(214,196,162,.32);
    box-shadow: 0 18px 60px rgba(0,0,0,.45), inset 0 1px 0 rgba(232,223,211,.07); }
  .act-body { display: none; min-height: 0; overflow: auto; padding: 4px 22px 16px; scrollbar-gutter: stable; }
  .act.open .act-body { display: block; flex: 1; }
}
@media (max-width: 719.9px) {
  .stage { max-width: 1060px; margin: 0 auto; padding: 0 16px; }
  .act { border: 1px solid var(--line); border-radius: 14px; margin: 6px 0; background: rgba(27,23,20,.42); }
  .act-body { display: none; padding: 6px 16px 20px; }
  .act.open .act-body { display: block; }
}
.act-head { display: flex; align-items: baseline; gap: 16px; width: 100%; background: none; border: 0; font: inherit;
  color: var(--faint); cursor: pointer; padding: 12px 22px; text-align: left; }
.act-head .n { font-family: var(--mono); font-size: 11px; }
.act-head .t { font-family: var(--mono); font-size: 12px; letter-spacing: .2em; text-transform: uppercase; color: var(--muted); }
.act.open .act-head .t, .act.open .act-head .n { color: var(--amber); }
.act-head .teaser { margin-left: auto; font-family: var(--mono); font-size: 12px; color: var(--faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.act.open .act-head .teaser { visibility: hidden; }
.nextrow { display: flex; justify-content: flex-end; padding: 8px 2px 2px; }
.next { background: rgba(201,162,107,.16); border: 1px solid var(--amber); border-radius: 9px; color: var(--amber);
  font-family: var(--mono); font-size: 13px; font-weight: 600; padding: 8px 20px; cursor: pointer; }
@keyframes nudge { 0%,100% { box-shadow: 0 0 0 0 rgba(201,162,107,0); } 50% { box-shadow: 0 0 0 7px rgba(201,162,107,.12); } }
@media (prefers-reduced-motion: no-preference) { .next { animation: nudge 2.4s ease-in-out infinite; } }
.kbd-note { font-family: var(--mono); font-size: 10.5px; color: var(--faint); }
h2 { border-top: 0; padding-top: 8px; }
@media print {
  :root { --bg: #fff; --text: #111; --muted: #333; --faint: #777; --line: #ccc; --amber: #8a6a34; --red: #a33; --green: #2a6; }
  body { height: auto; overflow: visible; display: block; }
  body::before { display: none; }
  .ribbon { background: #eee; color: #333; border-bottom: 1px solid #ccc; }
  .masthead a, .kbd-note, .nextrow { display: none; }
  .stage { display: block; max-width: none; padding: 0; }
  .act, .act.open { display: block; border: 0; background: none; box-shadow: none; backdrop-filter: none; }
  .act-body, .act.open .act-body { display: block !important; overflow: visible; padding: 2px 0 12px; }
  .act-head { padding: 10px 0 2px; }
  .act-head .teaser { display: none; }
}
</style>
</head>
<body>
<div class="ribbon">__DISCLOSURE__</div>
<div class="masthead">
  <span><b>risk-as-code-agent</b> / model validation package · <span data-s="period"></span></span>
  <span class="kbd-note">1 / 2 / 3 switch chapters · print expands all</span>
  <span style="display:flex; gap:10px"><a class="wb-link" href="index.html#role=audit">workbench ↗</a><a href="board.html">board brief ↪</a><a href="journey.html">the journey ↪</a></span>
</div>

<main class="stage">
  <section class="act open" id="act-1">
    <button class="act-head" type="button" data-act="1" aria-expanded="true" aria-controls="act-1-body">
      <span class="n">01</span><span class="t">the engine &amp; its error bars</span><span class="teaser">seeded correlated MC · its own CIs</span></button>
    <div class="act-body" id="act-1-body">
      <h1>The package a model-validation function asks for first</h1>
      <p class="lede">Every number below hydrates from the same sealed projection as the workbench —
      this page re-sequences the engine specification, its own error bars, the sensitivity apparatus,
      and the challenged-judgment log into one dossier. Nothing here is new analysis; everything here
      is challengeable, and the challenges are pre-priced.</p>
      <h2>1 · Engine specification</h2>
      <div data-s="engine"></div>
      <h2>2 · Sampling error — the model's own error bars</h2>
      <div data-s="sampling"></div>
      <div class="nextrow"><button class="next" data-goto="2">what moves the number ▸</button></div>
    </div>
  </section>

  <section class="act" id="act-2">
    <button class="act-head" type="button" data-act="2" aria-expanded="false" aria-controls="act-2-body">
      <span class="n">02</span><span class="t">what moves the number</span><span class="teaser">12 levers · σ-sweep · the judgment log</span></button>
    <div class="act-body" id="act-2-body">
      <h2>3 · Sensitivity — what moves the number, priced</h2>
      <div data-s="levers"></div>
      <h2>4 · Severity co-movement — the σ-sweep</h2>
      <div data-s="sweep"></div>
      <h2>5 · Challenged-judgment log — who set what, and the 2LoD challenge each invites</h2>
      <div data-s="judgments"></div>
      <div class="nextrow"><button class="next" data-goto="3">limits &amp; the contract ▸</button></div>
    </div>
  </section>

  <section class="act" id="act-3">
    <button class="act-head" type="button" data-act="3" aria-expanded="false" aria-controls="act-3-body">
      <span class="n">03</span><span class="t">limits &amp; the contract</span><span class="teaser">3 open items · one move to real</span></button>
    <div class="act-body" id="act-3-body">
      <h2>6 · Known limits and the open validation items</h2>
      <div data-s="limits"></div>
      <h2 id="contract">7 · The productionization contract — one move to real</h2>
      <div data-s="contract"></div>
    </div>
  </section>
</main>
<script id="projection-source" type="application/json">__PROJECTION__</script>
<script>
(function () {
  var P = JSON.parse(document.getElementById('projection-source').textContent);
  function $(id) { return document.querySelector('[data-s="' + id + '"]'); }
  function esc(s) { var d = document.createElement('i'); d.textContent = String(s == null ? '' : s); return d.innerHTML; }
  function M(v) { return '$' + (v / 1e6).toFixed(1) + 'M'; }
  $('period').textContent = (P.meta || {}).period || '';

  var exp = (P.exposure || {}).portfolio_total || {};
  var cm = exp.correlation_model || {};
  var cf = (cm.independence_counterfactual || {});
  var sens = P.sensitivity || {};
  var base = sens.baseline || {};
  $('engine').innerHTML = '<table><tbody>'
    + '<tr><th>form</th><td>' + esc(cm.type || 'Poisson frequency × lognormal severity') + ' · ' + esc(cm.generations) + '-generation cascade on the declared edges</td></tr>'
    + '<tr><th>trials · seed</th><td class="n">' + esc(base.trials) + ' · seed ' + esc(base.seed) + ' (byte-reproducible)</td></tr>'
    + '<tr><th>residual</th><td class="n">P50 ' + M(exp.p50_usd) + ' · P95 ' + M(exp.p95_usd) + ' · P99 ' + M(exp.p99_usd) + '</td></tr>'
    + '<tr><th>inherent</th><td class="n">P95 ' + M(exp.inherent_p95_usd) + '</td></tr>'
    + '<tr><th>independence counterfactual</th><td class="n">P95 ' + M(cf.residual_p95 || 0) + ' — the correlated-tail delta is explicit and re-runnable (cascade=False)</td></tr>'
    + '<tr><th>cascade induction</th><td>' + esc(JSON.stringify(cm.strength_to_probability || {})) + ' — operator_calibrated, disclosed</td></tr>'
    + '</tbody></table>'
    + '<div class="note">' + esc(cm.note || '') + '</div>'
    + '<div class="note">' + esc(exp.methodology_note || '') + '</div>';

  var se = exp.sampling_error || {};
  var ci95 = se.residual_p95_ci95 || [], ci99 = se.residual_p99_ci95 || [];
  $('sampling').innerHTML = '<table><tbody>'
    + (ci95.length ? '<tr><th>P95 · 95% CI</th><td class="n">' + M(ci95[0]) + ' – ' + M(ci95[1]) + '</td></tr>' : '')
    + (ci99.length ? '<tr><th>P99 · 95% CI</th><td class="n">' + M(ci99[0]) + ' – ' + M(ci99[1]) + '</td></tr>' : '')
    + '</tbody></table><div class="note">' + esc(se.note || '') + '</div>';

  var levers = sens.levers || [];
  var rows = levers.map(function (l) {
    return '<tr><td>' + esc(l.label) + '</td><td class="n">' + M(l.residual_p95) + '</td>'
      + '<td class="n" style="color:' + (l.delta_p95_pct >= 0 ? 'var(--red)' : 'var(--green)') + '">'
      + (l.delta_p95_pct >= 0 ? '+' : '') + esc(l.delta_p95_pct) + '%</td></tr>';
  }).join('');
  $('levers').innerHTML = '<table><thead><tr><th>challenged judgment</th><th>residual P95</th><th>Δ vs headline</th></tr></thead>'
    + '<tbody>' + rows + '</tbody></table>'
    + '<div class="note">' + esc(sens.method_note || '') + '</div>';

  var sw = (sens.sev_shock_sweep || {});
  var pts = sw.points || [];
  $('sweep').innerHTML = '<table><thead><tr><th>σ</th><th>residual P95</th><th>Δ</th></tr></thead><tbody>'
    + pts.map(function (q) { return '<tr><td class="n">' + esc(q.sigma) + '</td><td class="n">' + M(q.residual_p95) + '</td><td class="n">+' + esc(q.delta_p95_pct) + '%</td></tr>'; }).join('')
    + '</tbody></table><div class="note">' + esc(sw.note || '') + '</div>';

  var jl = sens.judgment_log || [];
  $('judgments').innerHTML = jl.map(function (j) {
    return '<div class="judg">'
      + '<div class="q">' + esc(j.judgment || j.id || '') + '</div>'
      + '<div class="m">' + esc(j.basis || '') + '</div>'
      + (j.challenge ? '<div class="c">2LoD challenge: ' + esc(j.challenge) + '</div>' : '')
      + (j.answers_with ? '<div class="m">answered by: ' + esc(j.answers_with) + '</div>' : '')
      + '</div>';
  }).join('');

  // limits: quote the projection's own disclosure strings; the three open items
  // are the recorded examiner asks (chrome — they name gaps, they mint nothing).
  $('limits').innerHTML =
    '<div class="note" style="font-size:12px">' + esc(((P.inherent_residual || {}).calibration_basis_note) || (sens.source_note || '')) + '</div>'
    + '<div class="openitem"><b>Open item 1 — loss-history fit.</b> Frequencies and severity anchors are operator judgment calibrated to public events, not fitted to internal loss history. Production replaces the inputs and re-runs the same engine.</div>'
    + '<div class="openitem"><b>Open item 2 — live control testing.</b> Control-evidence rows carry the CCT schema (method · date · result · credited-vs-self-assessed) populated illustratively; effectiveness credits await live test results.</div>'
    + '<div class="openitem"><b>Open item 3 — perimeter binding.</b> The regulation view re-maps under a declared charter (see the workbench perimeter selector), indicatively — the determination is reserved to Legal/Compliance.</div>'
    + (function () {
        var rc = (((P.exposure || {}).portfolio_total || {}).recalibration) || {};
        if (!rc.prior_residual_p95) return '';
        return '<div class="openitem"><b>On headline movement.</b> The residual P95 has moved across review rounds while '
          + 'the inputs remain operator judgment — it was <b>' + M(rc.prior_residual_p95) + '</b> at the prior seal ('
          + esc(rc.prior_seal || '') + '). Two standing answers, both machinery: <b>' + esc((rc.band_gate || '').split(':')[0] || 'C33')
          + '</b> now hard-gates the aggregate to a revenue-fraction band (' + esc(rc.band_gate || '')
          + ') — recalibrations move within it or fail the build; and every superseded headline must wear a transition '
          + 'marker in shipped prose (verify_bundle B6.2). The moves are recalibration under the productionization '
          + 'contract, not fitted-history drift — and the contract above is the exit from the volatility itself.</div>';
      })();

  // round-23 (cold GROK P1): the "one move to real" as an explicit CONTRACT,
  // not a footnote — what swaps, what cannot change, and how acceptance is
  // decided mechanically. Chrome text: it names the machinery, mints no number.
  // round-24 (GROK P1): each step carries the SENSITIVITY lever that already
  // prices its impact — honest bounds from the tornado, not invented ΔP95
  // forecasts — and the named acceptance gate that decides it landed.
  var _lv = {}; ((P.sensitivity || {}).levers || []).forEach(function (l) { _lv[l.id] = l; });
  var _fu = _lv.freq_up || {}, _ed = _lv.eff_down || {};
  var _pp = ((P.regulation_residual || {}).perimeter_profiles) || {};
  var _dp = (_pp.profiles || []).filter(function (x) { return x.profile_id === _pp.default; })[0] || {};
  $('contract').innerHTML =
    '<div class="openitem"><b>Step 1 — fit frequencies & severities to internal loss history.</b> Replaces the operator '
    + 'judgments of open item 1. The tornado already bounds what this can move: the frequency lever alone is '
    + (_fu.delta_p95_pct > 0 ? '+' : '') + (_fu.delta_p95_pct || 0) + '% (' + M(_fu.residual_p95) + ' at ×1.5). '
    + '<i>Acceptance gate:</i> numeric baseline re-cut in the same change; C1/C18 reconciliation and B11 green on the fitted feed.</div>'
    + '<div class="openitem"><b>Step 2 — wire live control testing (CCT).</b> Replaces the self-assessed-with-haircut credits '
    + 'of open item 2. The effectiveness lever prices the stake: −20 pts is +' + (_ed.delta_p95_pct || 0) + '% ('
    + M(_ed.residual_p95) + '). <i>Acceptance gate:</i> C22 control-evidence rows carry real method/date/result; '
    + 'C24 coverage≠effectiveness class stays green.</div>'
    + '<div class="openitem"><b>Step 3 — bind the prudential perimeter.</b> Legal/Compliance declares the charter; the '
    + 'selector\'s indicative re-mapping (default profile holds ' + M(_dp.in_perimeter_residual_p95) + ' in perimeter) '
    + 'becomes a determination. <i>Acceptance gate:</i> C28 perimeter gates re-run against the declared charter; '
    + 'the reservation note is replaced by the determination record.</div>'
    + '<div class="openitem"><b>What cannot change (the machinery).</b> The seeded Monte-Carlo engine, the sealed-projection '
    + 'contract, render-from-data, and every gate — conservation probes, the C-series audits, the interaction matrix, '
    + 'the cross-build numeric baseline — run UNCHANGED on real inputs. A production deployment that edits the machinery '
    + 'to fit its data has failed this contract, not satisfied it. No demo-to-prod judgment call — the gates ARE the '
    + 'acceptance test.</div>';
  // chapter accordion — the platform read grammar (keys 1/2/3, #act=N, aria);
  // #contract deep links (the board brief points here) open chapter 3.
  function openAct(n) {
    [1, 2, 3].forEach(function (i) {
      var on = i === Number(n);
      document.getElementById('act-' + i).classList.toggle('open', on);
      var hd = document.querySelector('#act-' + i + ' .act-head');
      if (hd) hd.setAttribute('aria-expanded', String(on));
    });
  }
  document.querySelectorAll('.act-head').forEach(function (h) {
    h.addEventListener('click', function () { openAct(h.dataset.act); });
  });
  document.querySelectorAll('.next').forEach(function (b) {
    b.addEventListener('click', function () { openAct(b.dataset.goto); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.target && e.target.matches && e.target.matches('input, textarea, select')) return;
    if (e.key >= '1' && e.key <= '3') openAct(e.key);
  });
  function route() {
    var m = location.hash.match(/act=(\d)/);
    if (m) openAct(m[1]);
    else if (location.hash === '#contract') openAct(3);
  }
  route();
  window.addEventListener('hashchange', route);
})();
</script>
</body>
</html>
"""


def write_validation_page(projection_path: str | None = None, output_path: str | None = None) -> str:
    # canonical sealed projection, never glob-last (round-15 footgun class)
    proj_file = Path(projection_path) if projection_path else (
        _ROOT / "outputs" / "v2_0a" / "2026-Q3_projection.json")
    proj_text = proj_file.read_text(encoding="utf-8")
    meta = json.loads(proj_text).get("meta", {})
    html = (_TEMPLATE
            .replace("__PROJECTION__", proj_text.replace("</", "<\\/"))
            .replace("__DISCLOSURE__", _DISCLOSURE)
            .replace("__PERIOD__", str(meta.get("period", ""))))
    out = Path(output_path) if output_path else _ROOT / "docs" / "validation.html"
    out.write_text(html, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print("wrote:", write_validation_page())
