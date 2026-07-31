"""
board_page (rac) — the Board / Risk-Committee brief as ONE surface, in the
platform's read grammar.

Round-23 external ask (cold GROK: "there is no Board surface"), round-24
(GROK: Board verbs, not risk rows), round-24.5 (user: the brief must SPEAK
the design system — one-viewport chapter accordion, glass panels, the warm
background, keys 1/2/3 — same grammar as the reads and the tour).

Three chapters, one attention device each:
  01 THE NUMBER      — the residual P95 hero + the challenge tiles
  02 THE RESOLUTIONS — five asks in Board verbs + the evidence docket
  03 POSTURE & PATH  — regime share bars + perimeter + the one move to real

ZERO-DRIFT CONTRACT: the page embeds the sealed projection and hydrates every
number client-side (render-from-data, same as index/read/classic/validation).
The only authored strings are chrome and the verbatim disclosure ribbon.
Gated by board_sha256 freshness in qa/conservation_report.json, C29.1 (shipped
inline JS parses) and verify_bundle B10 (numeric-leaf equality across all rac
views). Print expands every chapter (a pre-read cannot arrive folded).

Build:  python3 -c "import sys; sys.path.insert(0,'.'); from utils.board_page import write_board_page; write_board_page()"
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
<title>risk-as-code-agent · __PERIOD__ · board risk brief</title>
<style>
:root{
  --bg:#14110D; --text:#E8DFD3; --dim:rgba(232,223,211,.62); --faint:rgba(232,223,211,.36);
  --line:rgba(214,196,162,.14); --line-hi:rgba(214,196,162,.32);
  --amber:#C9A26B; --red:#C84A4A; --green:#6BAF7A;
  --serif:'Iowan Old Style','Palatino Nova',Palatino,'Book Antiqua',Georgia,serif;
  --mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--serif);line-height:1.5}
body::before{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(1000px 640px at 82% -12%,rgba(201,162,107,.11),transparent 62%),
             radial-gradient(760px 540px at -8% 112%,rgba(107,175,122,.05),transparent 60%)}
.ribbon{font-family:var(--mono);font-size:11.5px;color:rgba(20,17,13,.92);background:var(--amber);padding:6px 22px}
.masthead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;max-width:1060px;margin:0 auto;padding:12px 32px 0;
  font-family:var(--mono);font-size:12px;color:var(--faint)}
.masthead b{color:var(--dim);font-weight:500}
.masthead a{color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:3px 12px}
.masthead a:hover{color:var(--amber)}
.kbd-note{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
@media (min-width:720px){
  body{height:100vh;overflow:hidden;display:flex;flex-direction:column}
  .stage{flex:1;min-height:0;display:flex;flex-direction:column;max-width:1060px;width:100%;margin:0 auto;padding:0 32px 8px}
  .act{display:flex;flex-direction:column;min-height:0;border:1px solid var(--line);border-radius:14px;margin:4px 0;
    background:rgba(20,17,13,.55);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
  .act.open{flex:1;background:rgba(43,37,31,.78);border-color:var(--line-hi);
    box-shadow:0 18px 60px rgba(0,0,0,.45),inset 0 1px 0 rgba(232,223,211,.07)}
  .act-body{display:none;min-height:0;overflow:auto;padding:4px 22px 14px;scrollbar-gutter:stable}
  .act.open .act-body{display:flex;flex-direction:column;flex:1}
  .act.open .act-body::before,.act.open .act-body::after{content:'';flex:1 0 0;min-height:0}
}
@media (max-width:719.9px){
  .stage{max-width:1060px;margin:0 auto;padding:0 16px}
  .act{border:1px solid var(--line);border-radius:14px;margin:6px 0;background:rgba(27,23,20,.42)}
  .act-body{display:none;padding:6px 16px 20px}
  .act.open .act-body{display:block}
}
.act-head{display:flex;align-items:baseline;gap:16px;width:100%;background:none;border:0;font:inherit;
  color:var(--faint);cursor:pointer;padding:12px 22px;text-align:left}
.act-head .n{font-family:var(--mono);font-size:11px}
.act-head .t{font-family:var(--mono);font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}
.act.open .act-head .t,.act.open .act-head .n{color:var(--amber)}
.act-head .teaser{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.act.open .act-head .teaser{visibility:hidden}
.lede{font-size:clamp(16px,1.6vw,20px);margin:2px 0 12px;color:var(--text)}
.lede i{color:var(--amber)}
.hero{display:flex;gap:26px;align-items:baseline;flex-wrap:wrap;margin:2px 0}
.hero .big{font-family:var(--mono);font-size:clamp(34px,4.6vw,54px);color:var(--text)}
.hero .ctx{font-size:13.5px;color:var(--dim);max-width:42ch}
.hero .ctx b{color:var(--text);font-weight:500}
.row{display:flex;gap:22px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;color:var(--dim);margin-top:10px}
.row b{color:var(--text);font-weight:500}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:14px}
.tile{padding:12px 14px;border:1px solid var(--line);border-radius:10px}
.tile .v{font-family:var(--mono);font-size:19px;font-weight:600;color:var(--amber)}
.tile .k{font-size:12px;color:var(--faint);margin-top:3px;line-height:1.45}
/* r58 (operator-approved punch grammar): each ask is a strike card — verb rail,
   one decidable sentence, one evidence line, THE number where it burns. */
.reso{display:grid;grid-template-columns:96px 1fr auto;gap:18px;align-items:center;padding:15px 18px;margin:9px 0;border:1px solid var(--line);
  border-left:3px solid var(--amber);border-radius:10px;background:rgba(20,17,13,.35)}
.reso .verb{font-family:var(--mono);font-size:12px;font-weight:700;letter-spacing:.14em;color:var(--amber);text-transform:uppercase}
.reso.note-tone .verb{color:var(--red)}
.reso .what{font-size:16px;font-weight:600;line-height:1.4;color:var(--text)}
.reso .evd{display:block;font-size:13px;font-weight:400;color:var(--dim);margin-top:3px;line-height:1.5}
.reso .evd a{color:var(--amber);text-decoration:none}
.reso .evd a:hover{text-decoration:underline}
.reso .num{font-family:var(--mono);font-weight:700;font-size:21px;white-space:nowrap;text-align:right;color:var(--text)}
.reso .num.red{color:var(--red)}
.reso .numlbl{display:block;font-family:var(--mono);font-size:10px;font-weight:400;color:var(--faint,rgba(232,223,211,.4));letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.reso .body a{color:var(--amber)}
.seqrow{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:14px;padding:13px 18px;
  border:1px solid var(--line);border-radius:10px;background:rgba(201,162,107,.06)}
.seqrow .q{font-size:14.5px;flex:1;min-width:240px;color:var(--text)}
.seqrow a{display:inline-block;text-decoration:none;border-radius:9px;font-size:14px;font-weight:650;
  padding:10px 16px;background:var(--amber);color:#171310;white-space:nowrap}
@media(max-width:700px){.reso{grid-template-columns:1fr;gap:8px}.reso .num{text-align:left}}
.dk{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;padding:9px 13px;margin:6px 0;
  border:1px solid var(--line);border-left:3px solid var(--red);border-radius:10px;background:rgba(20,17,13,.35)}
.dk .pid{font-family:var(--mono);color:var(--text);white-space:nowrap}
.dk .who{flex:1 1 260px;font-size:12.5px;color:var(--dim);line-height:1.5}
.dk .who b{color:var(--text);font-weight:500}
.dk .usd{font-family:var(--mono);font-size:11.5px;white-space:nowrap}
.dk .usd a{color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
.dk .usd a:hover{color:var(--amber);border-color:var(--line-hi)}
.cap{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:8px;line-height:1.5}
.regbars{margin-top:6px}
.regrow{display:grid;grid-template-columns:170px 1fr 130px;gap:10px;align-items:center;margin:9px 0;
  font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.regrow .nm{color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rtrack{height:13px;border-radius:99px;background:rgba(214,196,162,.10);overflow:hidden}
.rfill{height:100%;border-radius:99px;background:var(--amber);opacity:.72}
.regrow .val{text-align:right;color:var(--text)}
.regnote{font-family:var(--mono);font-size:10.5px;color:var(--faint);margin:-4px 0 6px;grid-column:1/-1}
.real{border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin-top:12px;font-size:13.5px;color:var(--dim);background:rgba(20,17,13,.35)}
.real b{color:var(--text);font-weight:500}
.real a{color:var(--amber)}
.doorsrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.doorsrow a{font-family:var(--mono);font-size:11.5px;color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 14px}
.doorsrow a:hover{color:var(--amber);border-color:var(--line-hi)}
.nextrow{display:flex;justify-content:flex-end;padding:8px 2px 2px}
.next{background:rgba(201,162,107,.16);border:1px solid var(--amber);border-radius:9px;color:var(--amber);
  font-family:var(--mono);font-size:13px;font-weight:600;padding:8px 20px;cursor:pointer}
@keyframes nudge{0%,100%{box-shadow:0 0 0 0 rgba(201,162,107,0)}50%{box-shadow:0 0 0 7px rgba(201,162,107,.12)}}
@media (prefers-reduced-motion:no-preference){.next{animation:nudge 2.4s ease-in-out infinite}}
@media (max-width:719.9px){.regrow{grid-template-columns:110px 1fr 100px}}
@media print{
  :root{--bg:#fff;--text:#111;--dim:#333;--faint:#777;--line:#ccc;--line-hi:#aaa;--amber:#8a6a34;--red:#a33;--green:#2a6}
  body{height:auto;overflow:visible;display:block}
  body::before{display:none}
  .ribbon{background:#eee;color:#333;border-bottom:1px solid #ccc}
  .masthead a,.kbd-note,.nextrow{display:none}
  .stage{display:block;max-width:none;padding:0}
  .act,.act.open{display:block;border:0;background:none;box-shadow:none;backdrop-filter:none}
  .act-body,.act.open .act-body{display:block !important;overflow:visible;padding:2px 0 14px}
  .act-head{padding:10px 0 2px;color:#8a6a34}
  .act-head .teaser{display:none}
}
</style>
</head>
<body>
<div class="ribbon">__DISCLOSURE__</div>
<div class="masthead">
  <span><b>risk-as-code-agent</b> · <span data-s="period"></span> · board risk brief</span>
  <span class="kbd-note">1 / 2 / 3 switch chapters · print expands all</span>
  <span>
    <a class="wb-link" href="index.html#role=leadership">the workbench ↪</a>
    <a href="validation.html">validation package ↪</a>
    <a href="index.html#role=leadership">the workbench ↪</a>
  </span>
</div>

<main class="stage">
  <section class="act open" id="act-1">
    <button class="act-head" type="button" data-act="1" aria-expanded="true" aria-controls="act-1-body">
      <span class="n">01</span><span class="t">the resolutions</span><span class="teaser" data-s="teaser-2">five asks, in board verbs</span></button>
    <div class="act-body" id="act-1-body">
      <div class="lede">A board votes in verbs. Five asks — <i>the number is their evidence, not the headline.</i>
        <span style="display:block;margin-top:4px;font-size:13.5px;color:var(--dim)">Every figure below re-derives from the sealed projection; challenging any of them re-runs the engine with the same seed.</span></div>
      <div data-s="resolutions"></div>
      <div class="row" style="margin-top:12px"><span>on the table this week — <b data-s="docket-usd"></b> of residual P95 rides on the <span data-s="docket-n"></span> docket items below (the evidence the five asks rest on, not additional votes) ·
        2LoD cannot force them; the levers are table-it, formal challenge, decline-to-countersign, escalate.</span></div>
      <div data-s="docket"></div>
      <div class="cap" data-s="a8line"></div>
      <div class="nextrow"><button class="next" data-goto="2">the number behind the asks ▸</button></div>
    </div>
  </section>

  <section class="act" id="act-2">
    <button class="act-head" type="button" data-act="2" aria-expanded="false" aria-controls="act-2-body">
      <span class="n">02</span><span class="t">the number</span><span class="teaser" data-s="teaser-1">the stress number, challenged</span></button>
    <div class="act-body" id="act-2-body">
      <div class="lede">The number the <span data-s="reso-count">five</span> resolutions rest on, and <i>what it takes to believe it</i> — every figure
        renders from the same sealed projection the workbench runs on; challenging any of them re-runs with the same seed.</div>
      <div class="hero">
        <span class="big" data-s="p95"></span>
        <span class="ctx">residual P95 — what a <b>bad year</b> costs after the controls we credit,
          under the stated, challengeable judgments. A <b>stress number</b> the model produces —
          not a capital figure.</span>
      </div>
      <div class="row" data-s="numrow"></div>
      <div class="tiles" data-s="challenge"></div>
      <div class="cap">If the board challenges it: every tile is one changed judgment on the same seeded engine —
        the tornado and the challenged-judgment log in the validation package show all twelve, one at a time.</div>
      <div class="nextrow"><button class="next" data-goto="3">posture &amp; path ▸</button></div>
    </div>
  </section>

  <section class="act" id="act-3">
    <button class="act-head" type="button" data-act="3" aria-expanded="false" aria-controls="act-3-body">
      <span class="n">03</span><span class="t">posture &amp; path</span><span class="teaser" data-s="teaser-3">regimes, perimeter, the one move</span></button>
    <div class="act-body" id="act-3-body">
      <div class="lede">Where the number sits <i>regulatorily</i> — and the one move that makes all of this real.</div>
      <div class="regbars" data-s="regs"></div>
      <div class="cap" data-s="perimeter"></div>
      <div class="real" data-s="real"></div>
      <div class="cap" data-s="foot"></div>
      <div class="cap">Org dynamics (names, committees, stall reasons) are illustrative — deliberately typical of a
        global fintech. The perimeter determination is reserved to Legal/Compliance; this brief only flags.</div>
      <div class="doorsrow">
        <a href="index.html#role=leadership">drill into the workbench ↪</a>
        <a href="validation.html#contract">the productionization contract ↪</a>
        <a href="index.html#role=leadership">the workbench ↪</a>
      </div>
    </div>
  </section>
</main>

<script id="projection-source" type="application/json">__PROJECTION__</script>
<script>
(function () {
  var P = JSON.parse(document.getElementById('projection-source').textContent);
  function $(id) { return document.querySelector('[data-s="' + id + '"]'); }
  function esc(s) { var d = document.createElement('i'); d.textContent = String(s == null ? '' : s); return d.innerHTML; }
  function M(v) { return '$' + ((v || 0) / 1e6).toFixed(1) + 'M'; }
  $('period').textContent = (P.meta || {}).period || '';

  var irp = ((P.inherent_residual || {}).portfolio) || {};
  var res = irp.residual || {}, inh = irp.inherent || {};
  var cut = inh.p95 ? Math.round((1 - res.p95 / inh.p95) * 100) : 0;
  $('p95').textContent = M(res.p95);
  $('teaser-1').textContent = M(res.p95) + ' residual P95 — stress, not capital';
  // round-27 (external P0, GROK: "silent movement is not honest movement"):
  // WHY the number moved, in one leaf-backed line — the engine deltas are the
  // point, not drift. Composed from the levers' own values.
  var _lv27 = {}; ((P.sensitivity || {}).levers || []).forEach(function (l) { _lv27[l.id] = l; });
  var _recal = (((P.exposure || {}).portfolio_total || {}).recalibration) || {};
  $('numrow').innerHTML =
      '<span>expected year (P50) <b>' + M(res.p50) + '</b></span>'
    + '<span>extreme year (P99) <b>' + M(res.p99) + '</b></span>'
    + '<span>before controls (inherent P95) <b>' + M(inh.p95) + '</b></span>'
    + '<span>controls buy a <b>' + cut + '% cut</b> — tested below, not asserted</span>'
    + '<span style="flex-basis:100%">why this number moved: at the prior seal (' + (_recal.prior_seal || 'E5')
    + ') the residual P95 was <b>' + M(_recal.prior_residual_p95) + '</b> against <b>'
    + M(_recal.prior_inherent_p95) + '</b> inherent; the r29 re-anchor moved the WHOLE distribution — not the '
    + 'controls credit — to <b>' + M(res.p95) + '</b> residual against <b>' + M(inh.p95) + '</b> inherent: '
    + 'every severity median re-cited to reference data (IBM CODB · Uptime · ITIC), dependency stacking '
    + 'capped, and the aggregate now hard-gated to a revenue-fraction band (C33) — future recalibrations '
    + 'move within the band or fail the build. The engine terms stay priced as levers below '
    + '(shared-dependency layer off: <b>' + M((_lv27.dep_layer_off || {}).residual_p95) + '</b> · '
    + 'load-dependent contagion β=0: <b>' + M((_lv27.beta_zero || {}).residual_p95) + '</b>) — '
    + 'deltas are priced risk and cited calibration, never drift</span>';

  var sens = P.sensitivity || {};
  var levers = {}; (sens.levers || []).forEach(function (l) { levers[l.id] = l; });
  var jb = levers.joint_bad_year || {}, co = levers.cascade_off || {};
  var maxSingle = 0;
  (sens.levers || []).forEach(function (l) {
    if (String(l.id).indexOf('joint') !== 0) maxSingle = Math.max(maxSingle, Math.abs(l.delta_p95_pct || 0));
  });
  var sw = ((sens.sev_shock_sweep || {}).points || []).slice(-1)[0] || {};
  var dlB = P.dependency_layer || {};
  var oneB = dlB.one_thing || {};
  $('challenge').innerHTML =
      '<div class="tile"><div class="v">±' + maxSingle.toFixed(0) + '%</div><div class="k">the most any SINGLE challenged judgment moves the number</div></div>'
    + '<div class="tile"><div class="v">−' + M(oneB.delta_p95_usd) + '</div><div class="k">the concentration question, priced: remove the <b>' + esc(oneB.name || '') + '</b> dependency and P95 falls this far (E1 shared-dependency layer)</div></div>'
    + '<div class="tile"><div class="v">' + M(sw.residual_p95) + '</div><div class="k">if severities co-move (σ sweep, +' + (sw.delta_p95_pct || 0) + '%) — tail correlation priced, not assumed away</div></div>'
    + '<div class="tile"><div class="v">' + M(jb.residual_p95) + '</div><div class="k">a joint bad year (+' + (jb.delta_p95_pct || 0) + '%) — frequencies up AND controls down together</div></div>'
    + '<div class="tile"><div class="v">' + M(co.residual_p95) + '</div><div class="k">if the cascade graph is wrong and failures are independent (' + (co.delta_p95_pct || 0) + '%)</div></div>';

  var REG = { occ_12cfr30_app_d: 'OCC 12 CFR 30 App D', eu_dora_ict: 'EU DORA (ICT)', nydfs_500: 'NYDFS Part 500',
              pci_dss_v4: 'PCI-DSS v4', sec_8k_item_1_05: 'SEC 8-K Item 1.05', uk_fca_opres: 'UK FCA Op-Res',
              gdpr_art_33: 'GDPR Art. 33', eu_ai_act_high_risk: 'EU AI Act (high-risk)',
              finra_4370: 'FINRA 4370 (BCP)', sea_17a4: 'SEA 17a-4 (records)', reg_sci: 'Reg SCI (style)' };

  // round-24 (GROK board review P0): a Board votes in verbs — endorse /
  // approve / require / note — not on pattern ids. Every number inside a
  // resolution hydrates from the projection (levers, derived leaves, the
  // internal-audit register); the verbs are chrome.
  var teamRouted = (((P.ia || {}).derived) || {}).treatments_team_routed;
  var nFind = (((P.meta || {}).counts) || {}).findings_total || 0;
  var effDown = levers.eff_down || {};
  var freqUp = levers.freq_up || {};
  var pastDue = (((P.internal_audit || {}).issues) || []).filter(function (i) {
    return /PAST DUE/.test(String(i.status || '')) && i.repeat_finding;
  })[0] || {};
  var _RESO_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
  var _resoCount = 0;
  // r58 (operator-approved): each ask is a strike — verb · one decidable
  // sentence · one evidence line with its link · THE number, labelled.
  function reso(verb, what, evd, num, numlbl, tone) {
    _resoCount += 1;
    return '<div class="reso' + (tone === 'note' ? ' note-tone' : '') + '">'
      + '<span class="verb">' + verb + '</span>'
      + '<span><span class="what">' + what + '</span><span class="evd">' + evd + '</span></span>'
      + '<span class="num' + (tone ? ' red' : '') + '">' + num + '<span class="numlbl">' + numlbl + '</span></span>'
      + '</div>';
  }
  var nPlanes = ((P.dependency_layer || {}).nodes || []).length;
  $('resolutions').innerHTML =
      reso('ENDORSE', 'The residual methodology as the reporting basis.',
        'Seeded, correlated Monte-Carlo; every judgment logged and challengeable · <a href="validation.html">validation package</a>',
        '±' + maxSingle.toFixed(0) + '%', 'max single-judgment move', '')
    + reso('APPROVE', 'The productionization roadmap — return to the Risk Committee with the live-input residual.',
        'Re-fitting the frequency judgment alone moves the number ' + (freqUp.delta_p95_pct > 0 ? '+' : '')
        + (freqUp.delta_p95_pct || 0) + '% · <a href="validation.html#contract">contract, validation §7</a>',
        M(freqUp.residual_p95), 'if frequency re-fits high', '')
    + reso('REQUIRE', 'A formal 2LoD challenge on control effectiveness — the biggest lever in the model.',
        'Credits are self-assessed with a haircut until live control testing lands · <a href="index.html#role=leadership&node=attack">the lever, priced ↪</a>',
        M(effDown.residual_p95), 'if effectiveness −20 pts', 'red')
    + reso('REQUIRE', 'An architectural-isolation review of the shared-dependency concentration.',
        'The ' + esc(oneB.name || '') + ' alone carries ' + M(oneB.delta_p95_usd) + ' of the tail · <a href="index.html#role=leadership&node=stake">per-node prices ↪</a>',
        M(dlB.layer_contribution_usd), 'rides the ' + (_RESO_WORDS[nPlanes] || nPlanes) + ' shared planes', 'red')
    + reso('NOTE', 'The past-due repeat audit issue — and the accountability gap behind every treatment.',
        esc(pastDue.issue_id || '—') + ', Audit Committee visibility · the ask: a named owner on each treatment',
        (teamRouted == null ? '—' : teamRouted) + ' of ' + nFind, 'treatments routed to team handles', 'note')
    // r51: NOT a sixth resolution (the count stays five) — the sequencing pull
    // into the decision surface where asks 03 and 04 become one choice.
    + '<div class="seqrow"><span class="q">Asks 03 · 04 are one sequencing decision — harden the controls or isolate the dependencies first.</span>'
    + '<a href="index.html#role=leadership&node=strategy">See both priced, with owners →</a></div>';

  // the work behind the asks — round-25: this list is CONSUMED from
  // ia.derived.docket_items (the one selection both surfaces share; the
  // workbench docket reads the same list unscoped — gated by C27.5). Each
  // row carries the full committee depth: residual $, named accountable,
  // committee, triggered regimes, the waiting 2LoD verb, and the political
  // reality — no workbench jump required to run the meeting.
  var regsFor = {};
  var mats = P.materiality || {};
  Object.keys(mats).forEach(function (rid) {
    var blk = mats[rid] || {};
    var caveat = /ILLUSTRATIVE|contractual/.test(blk.applicability || '');
    ((blk.triggered_patterns || blk.conditional_patterns) || []).forEach(function (pid) {
      (regsFor[pid] = regsFor[pid] || []).push((REG[rid] || rid).split(' ')[0] + (caveat ? '†' : ''));
    });
  });
  var findingBy = {};
  Object.keys(P.domains || {}).forEach(function (did) {
    ((P.domains[did] || {}).findings || []).forEach(function (f) { findingBy[f.pattern_id + '|' + did] = f; });
  });
  var diItems = ((((P.ia || {}).derived) || {}).docket_items) || [];
  var top3 = diItems.map(function (it) {
    var f = findingBy[it.pattern_id + '|' + it.domain] || {};
    var o = f.org_context || {};
    var tr = f.treatment || {};
    // the A8 verb this row is waiting on — same affordance rule as the
    // workbench docket (from the treatment state, never invented)
    var verb = 'dispo';
    if (tr.status === 'blocked') verb = 'escalate';
    else if (tr.status === 'planned') verb = 'gate';
    else if (tr.status === 'accepted') verb = 'accept (re-affirm)';
    else if ((f.time_in_state_days || 0) > 90) verb = 'escalate (stalled)';
    return { pid: it.pattern_id, name: f.pattern_name || '', usd: it.residual_p95,
             exec: o.accountable_exec || (tr.owner_handle || '—'),
             route: String(o.decision_route || '—').split('—')[0].trim(),
             stall: String(o.stall_reason || '').split('—')[0].trim(),
             cost: String(o.political_cost || ''),
             verb: verb, regs: regsFor[it.pattern_id] || [] };
  });
  var dkUsd = (((P.ia || {}).derived) || {}).docket_at_stake_usd;
  $('docket-usd').textContent = M(dkUsd);
  $('docket-n').textContent = String(top3.length);
  $('teaser-2').textContent = 'five asks · ' + M(dkUsd) + ' on the table';
  $('docket').innerHTML = top3.map(function (c, i) {
    return '<div class="dk"><span class="pid">' + (i + 1) + ' · ' + esc(c.pid) + '</span>'
      + '<span class="who"><b>' + esc(c.name) + '</b> · ' + M(c.usd) + ' residual P95'
      + (c.regs.length ? ' · ' + esc(c.regs.join(' · ')) : '')
      + ' · <span style="color:var(--amber)">waiting on: ' + esc(c.verb) + '</span><br>'
      + esc(c.exec) + ' · decided at ' + esc(c.route)
      + (c.stall ? '<details style="margin-top:3px"><summary style="cursor:pointer;color:var(--faint);font-size:12px">why it stalls ▸</summary>'
        + '<span style="color:var(--faint)">stalled: ' + esc(c.stall)
        + (c.cost ? ' · escalation cost: ' + esc(c.cost.split('.')[0]) : '') + '</span></details>' : '')
      + '</span>' 
      + '<span class="usd"><a href="index.html#role=leadership&node=docket">drill in ↪</a></span></div>';
  }).join('');
  $('reso-count').textContent = _RESO_WORDS[_resoCount] || String(_resoCount);
  $('a8line').innerHTML = 'This list IS the workbench docket — one selection, made in the sealed projection '
    + '(top-3 red findings by per-pattern residual P95), consumed by both surfaces and gated so they cannot diverge. '
    + 'Per-row dollars are per-pattern residual P95 — not additive; the portfolio number is the one at the top. '
    + 'The NOTE resolution surfaces the single highest-governance past-due item by design — production would carry '
    + 'the full prioritized register. † style-mapping or contractual, not a binding statute.';

  var rows = ((P.regulation_residual || {}).by_regulation || []).slice(0, 4);
  $('regs').innerHTML = rows.map(function (r) {
    var caveat = /ILLUSTRATIVE|contractual/.test(r.applicability || '');
    var w = Math.min(100, r.share_of_portfolio_p95_pct || 0);
    return '<div class="regrow">'
      + '<span class="nm">' + esc(REG[r.reg_id] || r.reg_id) + (caveat ? '†' : '') + '</span>'
      + '<div class="rtrack"><div class="rfill" style="width:' + w + '%"></div></div>'
      + '<span class="val">' + M(r.residual_p95) + ' · ' + (r.share_of_portfolio_p95_pct || 0) + '%</span>'
      + '</div>'
      + '<div class="regnote">applies? ' + esc(String(r.applicability || 'binding').split('—')[0].trim()) + '</div>';
  }).join('');
  var pp = ((P.regulation_residual || {}).perimeter_profiles) || {};
  var defProf = (pp.profiles || []).filter(function (x) { return x.profile_id === pp.default; })[0] || {};
  $('perimeter').innerHTML = '† style-mapping or contractual regime, not a binding statute for this archetype. '
    + 'Under the default charter (<b style="color:var(--text)">' + esc(pp.default || '') + '</b>), ' + M(defProf.in_perimeter_residual_p95)
    + ' of the residual P95 sits in perimeter — the workbench perimeter selector re-maps under other charters, indicatively.';

  $('real').innerHTML =
      '<b>One move:</b> connect real data. The synthetic findings feed, trace store and incident stream are swapped '
    + 'for the firm’s own; the engine, the projections, and every gate on this page run <b>unchanged</b>. '
    + 'Acceptance is mechanical: the same audits, conservation probes and numeric baseline re-run green on real inputs. '
    + 'The full contract — what changes, what cannot — is in the <a href="validation.html#contract">validation package</a>.';

  $('foot').textContent = 'as-of ' + ((P.meta || {}).as_of || '') + ' · every number on this page renders from the sealed '
    + ((P.meta || {}).period || '') + ' projection (render-from-data; zero-drift gates C26-C29, B10) · seeded Monte-Carlo, re-runnable.';

  // chapter accordion — the platform read grammar (keys 1/2/3, #act=N, aria)
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
  var m = location.hash.match(/act=(\d)/); if (m) openAct(m[1]);
  window.addEventListener('hashchange', function () {
    var m2 = location.hash.match(/act=(\d)/); if (m2) openAct(m2[1]);
  });
})();
</script>
</body>
</html>
"""


def write_board_page(projection_path: str | None = None, output_path: str | None = None) -> str:
    # canonical sealed projection, never glob-last (round-15 footgun class)
    proj_file = Path(projection_path) if projection_path else (
        _ROOT / "outputs" / "v2_0a" / "2026-Q3_projection.json")
    proj_text = proj_file.read_text(encoding="utf-8")
    meta = json.loads(proj_text).get("meta", {})
    html = (_TEMPLATE
            .replace("__PROJECTION__", proj_text.replace("</", "<\\/"))
            .replace("__DISCLOSURE__", _DISCLOSURE)
            .replace("__PERIOD__", str(meta.get("period", ""))))
    out = Path(output_path) if output_path else _ROOT / "docs" / "board.html"
    out.write_text(html, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print("wrote:", write_board_page())
