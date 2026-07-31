"""
journey_page (rac) — Stage 1b of reviews/journey_spine_port_spec.md: the
journey surface. The page that must "land from the moment you pull it."

THE STORYBOARD (locked diagnosis, spec §1 — the reference grammar):
  first paint  — a BUSINESS OBJECT: breadcrumb › journey · id · criticality ·
                 window · services · POSTURE ("no findings · no verdicts"),
                 the journey SLO, and the path itself — before any model talk
  01 THE PATH  — five stages, ten services, and the four-hop chain per service
                 (signal+chip → risk IDs+$ → owner → controls) with the caveat
                 IN THE CELL, expandable without leaving the page
  02 SIM-0531  — the dated seeded incident: four steps with derived peaks,
                 do-not-overclaim lines, and the seeded sparklines
  03 SO WHAT   — audience modes that RE-ARGUE (Engineering / 2LoD / Audit /
                 Board get different rows, not different filters)

ZERO-DRIFT: embeds the sealed projection; every number hydrates client-side
from journey_spine (peaks recompute via C36.3). Incident sparklines ride a
separate #journey-overlays island generated from the same seeded generator.
Structure from the operator's production 2LoD practice; all names, values,
and dates seeded.

Build: python3 -c "import sys; sys.path.insert(0,'.'); from utils.journey_page import write_journey_page; write_journey_page()"
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_DISCLOSURE = ("<b>2LoD independent observation — no findings, no verdicts.</b> A demonstrator "
               "on <b>synthetic</b> telemetry: structure from the operator's production 2LoD "
               "practice; all names, values, and dates seeded — the chip on every signal says so.")

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>risk-as-code-agent · __PERIOD__ · the journey</title>
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
.masthead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;max-width:1120px;margin:0 auto;padding:10px 32px 0;
  font-family:var(--mono);font-size:12px;color:var(--faint)}
.masthead b{color:var(--dim);font-weight:500}
.masthead a{color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:3px 12px}
.masthead a:hover{color:var(--amber)}
.kbd-note{font-family:var(--mono);font-size:10.5px;color:var(--faint)}
/* ── the business-object hero (always visible, before any chapter) ── */
.jhero{max-width:1120px;margin:0 auto;padding:8px 32px 2px}
.crumb{font-family:var(--mono);font-size:11.5px;color:var(--faint)}
.crumb b{color:var(--dim);font-weight:500}
.crumb .sep{margin:0 6px;color:var(--faint)}
.jtitle{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-top:4px}
.jtitle .nm{font-size:clamp(21px,2.6vw,30px)}
.jtitle .jid{font-family:var(--mono);font-size:12px;color:var(--amber);border:1px solid var(--line-hi);border-radius:999px;padding:2px 10px}
.jtitle .meta{font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.posture{font-family:var(--mono);font-size:11.5px;color:var(--dim);margin-top:5px}
.posture b{color:var(--amber);font-weight:500}
.jstats{display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;color:var(--dim);margin-top:8px}
.jstats b{color:var(--text);font-weight:600;font-size:15px}
.jstats .ok{color:var(--green)}
/* ── THE STAGE: the money path as a living flow-graph (stage 5) ── */
.jplayer{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 4px;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.jplay{background:rgba(201,162,107,.16);border:1px solid var(--amber);border-radius:8px;color:var(--amber);font:600 12px var(--mono);padding:5px 14px;cursor:pointer}
.jscrub{flex:1 1 220px;accent-color:#C9A26B}
.jspd button{background:none;border:1px solid var(--line);border-radius:6px;color:var(--dim);font:600 10.5px var(--mono);padding:3px 8px;cursor:pointer;margin-left:4px}
.jspd button.on{color:var(--amber);border-color:var(--amber)}
.jclk{min-width:120px;text-align:right;color:var(--text)}
.jphases{display:flex;gap:8px;font-size:10px;color:var(--faint)}
.jphases b{color:var(--red);font-weight:600}
.jkpis{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0 6px}
.jkpi{border:1px solid var(--line);border-radius:9px;padding:6px 12px;min-width:118px}
.jkpi .v{font-family:var(--mono);font-size:17px;font-weight:600;color:var(--text)}
.jkpi.watch .v{color:var(--amber)} .jkpi.crit .v{color:var(--red)}
.jkpi .l{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-top:2px}
.jstage{position:relative;height:clamp(380px,52vh,560px);border:1px solid rgba(214,196,162,.16);border-radius:12px;
  background:radial-gradient(900px 420px at 50% -30%,rgba(201,162,107,.07),transparent 65%),#0f0c09;overflow:hidden;
  box-shadow:0 8px 32px rgba(0,0,0,.6),inset 0 1px 0 rgba(232,223,211,.05)}
.jstage canvas{position:absolute;inset:0}
.jnode{position:absolute;transform:translate(-50%,-50%);min-width:96px;max-width:130px;border:1px solid var(--line-hi);
  border-radius:9px;background:rgba(24,20,16,.92);padding:5px 8px;cursor:pointer;z-index:2;text-align:center}
.jnode:hover{border-color:var(--amber)}
.jnode.sel{border-color:var(--amber);box-shadow:0 0 0 1px var(--amber)}
.jnode.ext{border-style:dashed;opacity:.85}
.jnode .nm{font-family:var(--mono);font-size:10.5px;font-weight:600;color:var(--text);white-space:nowrap}
.jnode .lv{font-family:var(--mono);font-size:9.5px;color:var(--dim);margin-top:1px;white-space:nowrap}
.jnode.watch .lv{color:var(--amber)} .jnode.crit .lv{color:var(--red)}
.jnode .dot{position:absolute;top:-4px;right:-4px;width:8px;height:8px;border-radius:50%;background:var(--green);opacity:.85}
.jnode.watch .dot{background:var(--amber)} .jnode.crit .dot{background:var(--red);animation:jpulse 1.2s ease-in-out infinite}
@keyframes jpulse{0%,100%{box-shadow:0 0 0 0 rgba(200,74,74,.5)}50%{box-shadow:0 0 0 6px rgba(200,74,74,0)}}
.jstagelbl{position:absolute;top:6px;transform:translateX(-50%);font-family:var(--mono);font-size:9.5px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--faint);z-index:1}
.jcap{font-family:var(--mono);font-size:10px;color:var(--faint);margin-top:5px}
/* the chain CARD (click a node) */
.jcard{border:1px solid var(--line-hi);border-radius:12px;background:rgba(24,20,16,.6);padding:12px 16px}
.jcard .jchead{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;font-family:var(--mono);font-size:12.5px;margin-bottom:6px}
.jcard .jchead .id{color:var(--amber);font-weight:600;font-size:14px}
.svcpick{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.svcpick button{background:none;border:1px solid var(--line);border-radius:999px;color:var(--dim);font:11px var(--mono);padding:3px 11px;cursor:pointer}
.svcpick button.on{color:var(--amber);border-color:var(--amber)}
.trend{margin-top:10px}
.trend canvas{width:100%;height:110px;display:block;border:1px solid var(--line);border-radius:8px;background:rgba(16,13,10,.5)}
.stepcard.live{border-color:var(--amber);box-shadow:0 0 0 1px rgba(201,162,107,.5)}
.stepcard{cursor:pointer}
/* the walk lives ON the player + the canvas */
.zhead{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--amber);margin-bottom:7px}
.zhead [data-s]{color:var(--dim);letter-spacing:0;text-transform:none}
.jwalk{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
.pills{display:inline-flex;gap:6px;flex-wrap:wrap}
.pill{font-family:var(--mono);font-size:10.5px;color:var(--dim);border:1px solid var(--line);border-radius:999px;
  padding:3px 11px;cursor:pointer;white-space:nowrap}
.pill b{color:var(--text);font-weight:600}
.pill.live{color:var(--amber);border-color:var(--amber);box-shadow:0 0 0 1px rgba(201,162,107,.35)}
.pill.p4.live{color:var(--green);border-color:var(--green);box-shadow:0 0 0 1px rgba(107,175,122,.3)}
/* the narrator strip — FIXED at the stage floor, never over the graph */
.jcallout{position:absolute;z-index:4;left:8px;right:8px;bottom:8px;border:1px solid rgba(224,145,58,.45);
  border-radius:8px;background:rgba(16,13,10,.94);padding:5px 8px;pointer-events:none;display:none;
  align-items:center;gap:10px;font-family:var(--mono);font-size:11px;color:rgba(232,223,211,.72)}
.jcallout .cl-body{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.jcallout .jwbtn{pointer-events:auto;flex:none;background:rgba(201,162,107,.16);border:1px solid #C9A26B;border-radius:7px;
  color:#C9A26B;font:600 12px var(--mono);padding:3px 11px;cursor:pointer}
.jcallout .jwbtn:hover{background:rgba(201,162,107,.32)}
.jcallout .cl-t{color:#E0913A;font-weight:600}
.jcallout .cl-v{color:rgba(232,223,211,.95)}
.jcallout .cl-n{font-family:var(--serif);font-style:italic}
.jcallout .cl-d{color:var(--faint);font-size:10px}
/* the chain as a floating card next to the clicked node */
.jchaincard{position:absolute;z-index:5;width:min(340px,44%);max-height:calc(100% - 46px);overflow-y:auto;
  border:1px solid var(--line-hi);border-radius:11px;
  background:rgba(24,20,16,.97);padding:10px 13px;display:none;box-shadow:0 18px 50px rgba(0,0,0,.5)}
.jchaincard.on{display:block}
.jchaincard .x{position:absolute;top:6px;right:10px;cursor:pointer;color:var(--faint);font-family:var(--mono)}
.jchaincard .jchead{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;font-family:var(--mono);font-size:11.5px;margin-bottom:4px}
.jchaincard .jchead .id{color:var(--amber);font-weight:600;font-size:13px}
.jchaincard .hop{margin:6px 0 2px}
.jchaincard .sigrow,.jchaincard .risklnk{font-size:10.5px}
.jchaincard .intent{display:none}
/* audiences: tiles + bars, not memos */
.atiles{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 10px}
.atile{border:1px solid var(--line);border-radius:10px;padding:9px 14px;min-width:140px}
.atile .v{font-family:var(--mono);font-size:20px;font-weight:600;color:var(--amber)}
.atile .v small{font-size:11px;color:var(--faint);font-weight:400}
.atile .k{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-top:3px}
.abar{display:grid;grid-template-columns:190px 1fr 90px;gap:10px;align-items:center;margin:6px 0;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
.abar .nm{color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.abar .tr{height:11px;border-radius:99px;background:rgba(214,196,162,.10);overflow:hidden}
.abar .fl{height:100%;border-radius:99px;background:var(--amber);opacity:.75}
.abar .fl.red{background:var(--red)}
.abar .vv{text-align:right;color:var(--text)}
.apills{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.apill{font-family:var(--mono);font-size:10.5px;color:var(--green);border:1px solid rgba(107,175,122,.5);border-radius:999px;padding:2px 10px}
.apill.warn{color:var(--amber);border-color:rgba(201,162,107,.5)}
.aline{font-size:12.5px;color:var(--dim);margin:6px 0}
.aline b{color:var(--text)} .aline a{color:var(--amber)}
/* the journey SCROLLS — the stage is the marquee, the chapters flow below it
   (the one-viewport lock belongs to the board brief, not here) */
.stage{max-width:1120px;margin:0 auto;padding:0 32px 40px}
.act{border:1px solid var(--line);border-radius:14px;margin:8px 0;
  background:rgba(20,17,13,.55);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
.act.open{background:rgba(43,37,31,.78);border-color:var(--line-hi);
  box-shadow:0 18px 60px rgba(0,0,0,.45),inset 0 1px 0 rgba(232,223,211,.07)}
.act-body{display:none;padding:6px 22px 18px}
.act.open .act-body{display:block}
@media (max-width:719.9px){.stage{padding:0 16px 32px}.act-body{padding:6px 16px 16px}}
.act-head{display:flex;align-items:baseline;gap:16px;width:100%;background:none;border:0;font:inherit;
  color:var(--faint);cursor:pointer;padding:11px 22px;text-align:left}
.act-head .n{font-family:var(--mono);font-size:11px}
.act-head .t{font-family:var(--mono);font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--dim)}
.act.open .act-head .t,.act.open .act-head .n{color:var(--amber)}
.act-head .teaser{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.act.open .act-head .teaser{visibility:hidden}
.lede{font-size:clamp(15px,1.5vw,18px);margin:2px 0 10px;color:var(--text)}
.lede i{color:var(--amber)}
/* chapter 1 — service chain rows */
.svcrow{border:1px solid var(--line);border-radius:10px;margin:7px 0;background:rgba(20,17,13,.35)}
.svcrow.inc{border-left:3px solid var(--red)}
.svchead{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;width:100%;background:none;border:0;font:inherit;
  color:var(--dim);cursor:pointer;padding:9px 14px;text-align:left;font-family:var(--mono);font-size:12px}
.svchead .id{color:var(--text);font-weight:600}
.svchead .lyr{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}
.svchead .own{color:var(--faint)}
.svchead .pats{margin-left:auto;color:var(--amber);font-size:11px}
.svcbody{display:none;padding:2px 16px 12px;border-top:1px solid var(--line)}
.svcrow.open .svcbody{display:block}
.hop{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--amber);margin:9px 0 3px}
.sigrow{display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;font-family:var(--mono);font-size:11.5px;color:var(--dim);margin:4px 0;padding-left:2px}
.sigrow .sid{color:var(--text)}
.sigrow .chip{font-size:10px;color:rgba(20,17,13,.9);background:var(--green);border-radius:4px;padding:1px 6px;opacity:.85}
.sigrow .intent{flex-basis:100%;font-size:11px;color:var(--faint);font-family:var(--serif);font-style:italic}
.risklnk{display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;font-family:var(--mono);font-size:11.5px;color:var(--dim);margin:4px 0}
.risklnk .pid{color:var(--text)}
.risklnk .usd{color:var(--amber)}
.cvt{font-size:10.5px;color:var(--faint);font-style:italic;font-family:var(--serif)}
.nonclaim{border:1px dashed rgba(200,74,74,.45);border-radius:8px;padding:7px 11px;margin-top:8px;
  font-family:var(--mono);font-size:11px;color:var(--dim)}
/* chapter 2 — incident walk */
.inchdr{display:flex;gap:16px;align-items:baseline;flex-wrap:wrap;font-family:var(--mono);font-size:12.5px;color:var(--dim)}
.inchdr .iid{color:var(--red);font-weight:600}
.inchdr b{color:var(--text)}
.stepcard{border:1px solid var(--line);border-left:3px solid var(--red);border-radius:10px;padding:10px 14px;margin:8px 0;background:rgba(20,17,13,.35)}
.stepcard .sh{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;font-family:var(--mono);font-size:12px}
.stepcard .sh .sn{color:var(--red);font-weight:600}
.stepcard .sh .peak{margin-left:auto;color:var(--amber)}
.stepcard .tx{font-size:13px;color:var(--dim);margin-top:4px;line-height:1.55}
.stepcard .tx b{color:var(--text);font-weight:500}
.stepcard .noclaim{font-family:var(--mono);font-size:10.5px;color:var(--faint);margin-top:5px}
.spark{margin-top:6px}
.spark svg{width:100%;height:44px;display:block}
.spark .pl{fill:none;stroke:var(--red);stroke-width:1.4;opacity:.85}
.spark .base{stroke:var(--faint);stroke-width:.6;stroke-dasharray:3 4}
.spark .cap2{font-family:var(--mono);font-size:10px;color:var(--faint)}
.sowhat{border:1px solid var(--line-hi);border-radius:10px;padding:10px 14px;margin-top:10px;font-size:13.5px;color:var(--dim)}
.sowhat b{color:var(--text);font-weight:500}
/* chapter 3 — audiences */
.audbar{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 10px}
.audbtn{font-family:var(--mono);font-size:11.5px;color:var(--dim);background:none;border:1px solid var(--line);border-radius:999px;padding:5px 14px;cursor:pointer}
.audbtn.on{color:var(--amber);border-color:var(--amber)}
.audrow{display:flex;gap:14px;align-items:baseline;padding:9px 13px;margin:6px 0;border:1px solid var(--line);border-radius:10px;background:rgba(20,17,13,.35)}
.audrow .lbl{font-family:var(--mono);font-size:11px;color:var(--amber);flex:0 0 88px}
.audrow .bd{font-size:13px;color:var(--dim);line-height:1.55}
.audrow .bd b{color:var(--text);font-weight:500}
.audrow .bd a{color:var(--amber)}
.cap{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:8px;line-height:1.5}
@media print{
  :root{--bg:#fff;--text:#111;--dim:#333;--faint:#777;--line:#ccc;--line-hi:#aaa;--amber:#8a6a34;--red:#a33;--green:#2a6}
  body{height:auto;overflow:visible;display:block}
  body::before{display:none}
  .ribbon{background:#eee;color:#333;border-bottom:1px solid #ccc}
  .masthead a,.kbd-note{display:none}
  .stage{display:block;max-width:none;padding:0}
  .act,.act.open{display:block;border:0;background:none;box-shadow:none;backdrop-filter:none}
  .act-body,.act.open .act-body{display:block !important;overflow:visible;padding:2px 0 14px}
  .svcbody{display:block !important}
  .act-head{padding:10px 0 2px;color:#8a6a34}
  .act-head .teaser{display:none}
}
</style>
</head>
<body>
<div class="ribbon">__DISCLOSURE__</div>
<div class="masthead">
  <span><b>risk-as-code-agent</b> · <span data-s="period"></span> · the journey</span>
  <span class="kbd-note">▶ play the incident · click a node for its chain · click a step to jump · print expands all</span>
  <span>
    <a href="index.html#role=leadership">the workbench ↪</a>
    <a href="board.html">board brief ↪</a>
    <a href="index.html">workbench ↪</a>
  </span>
</div>

<div class="jhero">
  <div class="crumb" data-s="crumb"></div>
  <div class="jtitle">
    <span class="nm" data-s="jname"></span>
    <span class="jid" data-s="jid"></span>
    <span class="meta" data-s="jmeta"></span>
  </div>
  <div class="posture" data-s="posture"></div>
  <div class="jstats" data-s="jstats"></div>
  <div data-s="path">
    <div class="jplayer">
      <button class="jplay" data-j="play">▶ play the incident</button>
      <span data-s="jphaselbl" class="jphases"></span>
      <input type="range" class="jscrub" data-j="scrub" min="0" max="0" value="0" aria-label="Scrub the incident window">
      <span class="jspd"><button data-spd="1" class="on">1×</button><button data-spd="4">4×</button></span>
      <span class="jclk" data-s="jclk"></span>
    </div>
    <div class="jkpis" data-s="jkpis"></div>
    <div class="jstage" data-s="jstage"><canvas data-j="cv"></canvas>
      <div class="jcallout" data-j="calloutwrap"><button class="jwbtn" data-j="beat-prev" type="button" aria-label="previous beat">◂</button><span class="cl-body" data-j="callout"></span><button class="jwbtn" data-j="beat-next" type="button" aria-label="next beat">▸</button></div>
      <div class="jchaincard" data-s="svcchains"></div>
    </div>
    <div class="jcap">lanes = the five stages, money flows left → right (arrows on every hop) · particles = transfers ·
      ↺ red dashed arc = the retry loop feeding the queue it waits on · ⟳ ring + halo = backlog depth at the bus ·
      ECG on the ledger→bus edge = consumer lag · heat spreading right = the cascade · dashed node = external, ACK-only ·
      severity = multiple of the seeded baseline · click any node for its risk chain · ◂ ▸ walk the beats</div>
    <div class="jwalk">
      <span class="zhead" style="margin:0">THE INCIDENT · <span data-s="incid-t2"></span></span>
      <span class="pills" data-s="steps"></span>
      <span data-s="inchdr" style="display:none"></span>
    </div>
    <div class="sowhat" data-s="incso" style="margin-top:8px"></div>
    <div class="trend" data-s="trend"><canvas data-j="trendcv"></canvas><div class="jcap" data-s="trendcap"></div></div>
    <div class="cap" data-s="inccap"></div>
    <div class="cap" data-s="chaincap"></div>
    <span data-s="svcpick" style="display:none"></span><span data-s="selname" style="display:none"></span>
  </div>
  <div class="posture" data-s="aggline" style="margin-top:4px"></div>
</div>

<main class="stage">
  <section class="act open" id="act-1">
    <button class="act-head" type="button" data-act="1" aria-expanded="true" aria-controls="act-1-body">
      <span class="n">01</span><span class="t">so what · per audience</span><span class="teaser" data-s="teaser-3"></span></button>
    <div class="act-body" id="act-1-body">
      <div class="lede">The same journey, argued four ways — <i>tiles and bars, not memos</i>; each audience gets its own read.</div>
      <div class="audbar" data-s="audbar"></div>
      <div data-s="audrows"></div>
      <div class="cap" data-s="audcap"></div>
    </div>
  </section>
</main>

<script type="application/json" id="projection-source">__PROJECTION__</script>
<script type="application/json" id="journey-overlays">__OVERLAYS__</script>
<script>
(function () {
  'use strict';
  var P = JSON.parse(document.getElementById('projection-source').textContent);
  var OV = JSON.parse(document.getElementById('journey-overlays').textContent);
  var J = P.journey_spine || {};
  var esc = function (s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };
  var $ = function (k) { return document.querySelector('[data-s="' + k + '"]'); };
  var M = function (v) { return v == null ? '—' : '$' + (v / 1e6).toFixed(1) + 'M'; };
  var chip = function (c) { return c ? c.realness + ' · ' + c.pts.toLocaleString() + 'pts · ' + c.cadence + ' · gen:' + c.gen : ''; };
  var UNITS = {msgs: ' msgs', ms: ' ms', '%': '%', rps: ' rps', per_min: '/min', count: '', items: ' items', score: ''};
  var fmtV = function (v, unit) {
    if (v == null) return '—';
    var n = +v;
    var s = n >= 1000 ? Math.round(n).toLocaleString() : (n >= 100 ? Math.round(n) : n.toFixed(1));
    return s + (UNITS[unit] != null ? UNITS[unit] : (unit ? ' ' + unit : ''));
  };

  $('period').textContent = (P.meta || {}).period || '';
  var jn = J.journey || {};
  $('crumb').innerHTML = (jn.breadcrumb || []).map(function (b, i) {
    return (i ? '<span class="sep">›</span>' : '') + (i === (jn.breadcrumb.length - 1) ? '<b>' + esc(b) + '</b>' : esc(b));
  }).join('');
  $('jname').textContent = jn.name || '';
  $('jid').textContent = jn.id || '';
  var w = J.window || {};
  $('jmeta').textContent = (jn.criticality || '') + ' · ' + (J.services || []).length + ' services · '
    + (w.days || 0) + 'd ' + (w.start || '') + ' → ' + (w.end || '');
  $('posture').innerHTML = '<b>' + esc(jn.posture || '') + '</b> — ' + esc(jn.sor_note || '');
  var slo = J.slo_derived || {};
  $('jstats').innerHTML =
      '<span>end-to-end p95 <b>' + Math.round(slo.end_to_end_p95_ms || 0).toLocaleString() + 'ms</b> vs <b>' + Math.round(slo.target_ms || 0).toLocaleString() + 'ms</b> target '
      + (slo.within_target ? '<span class="ok">within</span>' : '<span style="color:var(--red)">outside</span>') + '</span>'
    + '<span>availability <b>' + esc(slo.availability_observed_pct) + '%</b> vs ' + esc(slo.availability_target_pct) + '% target</span>'
    + '<span>signals <b>' + (J.signal_catalog || []).length + '</b> · ' + esc(((J.generator || {}).base_pts || 0).toLocaleString()) + 'pts each · SEEDED</span>'
    + '<span>residual on the path: see <a href="index.html#role=leadership" style="color:var(--amber)">the workbench</a></span>';

  var agg = J.aggregator || {};
  $('aggline').innerHTML = agg.consumed_sha256
    ? esc(agg.file || '') + ' · <b>verbatim · unmodified</b> — sha256 ' + esc(String(agg.consumed_sha256).slice(0, 12))
      + '… (' + esc(agg.claim || '') + ')'
    : '';
  var inc = J.incident || {};
  var svcById = {}; (J.services || []).forEach(function (s) { svcById[s.id] = s; });

  // ═══ THE STAGE — the money path as a living flow-graph (stage 5) ═══
  var PH = OV.__phases || {n: 150, build_end: 30, peak: 45, drain_start: 85, clock_origin_et: '09:30', cadence_min: 1};
  var BASE = OV.__baselines || {};
  var N = PH.n || 150;
  var LAYOUT = {
    'edge-gateway':      {x: 7,  y: 30}, 'transfer-api':      {x: 13, y: 57},
    'risk-scorer':       {x: 26, y: 27}, 'identity-verifier': {x: 28, y: 82},
    'ledger-writer':     {x: 39.5, y: 54}, 'event-bus':         {x: 57, y: 54},
    'settlement-engine': {x: 66, y: 28}, 'rails-partner':     {x: 76, y: 47},
    'notify-svc':        {x: 86, y: 68}, 'recon-batch':       {x: 92, y: 33}
  };
  // the shapes the layout must SAY: fan-out (api → both checks), the
  // convergence bottleneck (checks → ledger), the cycle (ledger ⇄ bus),
  // the explosion (bus → three consumers). Sizes say it too:
  var NODE_SCALE = {'ledger-writer': 1.1, 'event-bus': 1.22, 'rails-partner': 0.82, 'notify-svc': 0.88, 'recon-batch': 0.88};
  var STAGES_X = {initiate: 8, 'risk-check': 27, ledger: 47, rails: 68, settle: 88};
  var EDGES = [
    ['edge-gateway', 'transfer-api', null, 'flow', -10],
    ['transfer-api', 'risk-scorer', null, 'flow', -7],
    ['transfer-api', 'identity-verifier', null, 'flow', 7],
    ['risk-scorer', 'ledger-writer', null, 'flow', -7],
    ['identity-verifier', 'ledger-writer', null, 'flow', 7],
    ['ledger-writer', 'event-bus', 'sim.consumer_lag_p95', 'flow', -40],
    ['event-bus', 'settlement-engine', null, 'flow', -18],
    ['settlement-engine', 'rails-partner', null, 'ext', -12],
    ['event-bus', 'notify-svc', null, 'flow', 30],
    ['event-bus', 'recon-batch', null, 'flow', -58],
    ['ledger-writer', 'event-bus', 'sim.write_retry_rate', 'retry', 58]
  ];
  var SIGSVC = {};
  (J.services || []).forEach(function (s) { (s.signal_rows || []).forEach(function (r) {
    if (!(s.id in SIGSVC) || r.incident_participant) SIGSVC[s.id] = SIGSVC[s.id] || [];
    SIGSVC[s.id].push(r);
  }); });
  var stage = document.querySelector('[data-s="jstage"]');
  // stage column labels + node divs

  // canvas-drawn nodes (the reference treatment): circles + glow + labels,
  // no HTML boxes. Live values render per frame; clicks hit-test the canvas.
  var STAGECOL = {initiate: '#b8ae9c', 'risk-check': '#a88fd0', ledger: '#E0913A',
                  rails: '#C9A26B', settle: '#6BAF7A'};
  var NODE_LIVE = {};  // id -> {vTxt, sev}

  var sev = function (sig, v) {
    var b = BASE[sig] || 1; var m = v / b;
    return m >= 3 ? 'crit' : m >= 1.5 ? 'watch' : 'ok';
  };
  var at = function (sig, i) { var s = OV[sig]; return s ? (s[Math.max(0, Math.min(s.length - 1, i))] || 0) : (BASE[sig] || 0); };
  var svcSig = function (id) {
    var rows = (svcById[id] || {}).signal_rows || [];
    var part = rows.filter(function (r) { return r.incident_participant && OV[r.id]; })[0];
    return part || rows[0] || null;
  };

  // KPI tiles
  var KPIS = [
    {sig: 'sim.consumer_lag_p95', lbl: 'consumer lag', unit: 'msgs'},
    {sig: 'sim.p99_ledger_write', lbl: 'ledger p99', unit: 'ms'},
    {sig: 'sim.write_retry_rate', lbl: 'write retries', unit: '%'},
    {sig: 'sim.p99_transfer_api', lbl: 'transfer p99', unit: 'ms'}
  ];
  $('jkpis').innerHTML = KPIS.map(function (k, i) {
    return '<div class="jkpi" data-kpi="' + i + '"><div class="v">—</div><div class="l">' + esc(k.lbl) + '</div></div>';
  }).join('');
  var kpiEls = [].slice.call(document.querySelectorAll('.jkpi'));
  $('jphaselbl').innerHTML = 'phases: build → <b>peak</b> → drain (derived from the seeded series)';

  // canvas engine
  var cv = document.querySelector('[data-j="cv"]'), g = cv.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var pts = {}, parts = [], idx = 0, playing = false, spd = 1, animT = 0, narrSeat = null, curLag = 0;
  function centers() {
    var sr = stage.getBoundingClientRect();
    cv.width = sr.width * dpr; cv.height = sr.height * dpr;
    cv.style.width = sr.width + 'px'; cv.style.height = sr.height + 'px';
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    var R = Math.max(26, Math.min(sr.width, sr.height) / 15);
    (J.services || []).forEach(function (s) {
      var pos = LAYOUT[s.id] || {x: 50, y: 50};
      var Rn = R * (NODE_SCALE[s.id] || 1);
      pts[s.id] = {x: pos.x / 100 * sr.width, y: pos.y / 100 * sr.height,
                   w: Rn * 2, h: Rn * 2, r: Rn, col: STAGECOL[s.stage] || '#C9A26B',
                   ext: s.layer === 'external'};
    });
  }
  function rga(hex, a) {
    var r = parseInt(hex.slice(1, 3), 16), gg = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + gg + ',' + b + ',' + a + ')';
  }
  // click + hover hit-testing on the canvas
  function hitNode(ev) {
    var sr = stage.getBoundingClientRect();
    var mx = ev.clientX - sr.left, my = ev.clientY - sr.top, best = null, bd = 1e9;
    Object.keys(pts).forEach(function (id) {
      var n = pts[id], d = Math.hypot(mx - n.x, my - n.y);
      if (d < n.r * 1.5 && d < bd) { bd = d; best = id; }
    });
    return best;
  }
  cv.addEventListener('click', function (ev) { var id = hitNode(ev); if (id) selectSvc(id); });
  cv.addEventListener('mousemove', function (ev) { cv.style.cursor = hitNode(ev) ? 'pointer' : 'default'; });
  function bd(a, b) { var dx = b.x - a.x, dy = b.y - a.y, hw = a.w / 2 + 3, hh = a.h / 2 + 3, sx = dx ? hw / Math.abs(dx) : 1e9, sy = dy ? hh / Math.abs(dy) : 1e9, s = Math.min(sx, sy); return {x: a.x + dx * s, y: a.y + dy * s}; }
  function cpOf(a, b, l) { var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1; return {x: mx + (-dy / len) * l, y: my + (dx / len) * l}; }
  function geom(e) { var a = pts[e[0]], b = pts[e[1]]; if (!a || !b) return null; var a2 = bd(a, b), b2 = bd(b, a); return {a: a2, b: b2, cp: cpOf(a2, b2, e[4] !== undefined ? e[4] : (e[3] === 'retry' ? 56 : -18))}; }
  function bez(a, cp, b, t) { var mt = 1 - t; return {x: mt * mt * a.x + 2 * mt * t * cp.x + t * t * b.x, y: mt * mt * a.y + 2 * mt * t * cp.y + t * t * b.y}; }
  function seed() {
    parts = [];
    EDGES.forEach(function (e, ei) {
      if (e[3] === 'retry') return;
      for (var i = 0; i < 8; i++) parts.push({e: ei, t: Math.random(), spd: 0.10 + Math.random() * 0.08});
    });
  }
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  var SEVCOL = {ok: '#6BAF7A', watch: '#E0913A', crit: '#C84A4A'};
  function draw() {
    g.clearRect(0, 0, cv.width, cv.height);
    var srW = stage.clientWidth, srH = stage.clientHeight;
    // stage LANES — the left→right pipeline is architecture, not a header row
    var laneOrder = ['initiate', 'risk-check', 'ledger', 'rails', 'settle'];
    var laneB = [0, 17.5, 37, 57.5, 78, 100];
    (J.stages || []).forEach(function (st) {
      var si = laneOrder.indexOf(st.id); if (si < 0) return;
      var x0 = laneB[si] / 100 * srW, x1 = laneB[si + 1] / 100 * srW;
      var lcol = STAGECOL[st.id] || '#C9A26B';
      if (si % 2 === 1) { g.fillStyle = 'rgba(232,223,211,.028)'; g.fillRect(x0, 0, x1 - x0, srH); }
      if (si > 0) { g.strokeStyle = 'rgba(232,223,211,.07)'; g.lineWidth = 1;
        g.beginPath(); g.moveTo(x0, 30); g.lineTo(x0, srH - 34); g.stroke(); }
      g.textAlign = 'center'; g.font = '600 10.5px ui-monospace, monospace';
      g.fillStyle = rga(lcol, 0.9);
      g.fillText((si + 1) + ' · ' + st.name.toUpperCase(), (x0 + x1) / 2, 17);
      g.strokeStyle = rga(lcol, 0.55); g.lineWidth = 2;
      g.beginPath(); g.moveTo((x0 + x1) / 2 - 26, 24); g.lineTo((x0 + x1) / 2 + 26, 24); g.stroke();
      if (si < 4) {
        g.fillStyle = 'rgba(232,223,211,.45)'; g.font = '11px ui-monospace, monospace';
        g.fillText('▸', x1, 18);
      }
    });
    var i = Math.floor(idx);
    var lag = at('sim.consumer_lag_p95', i), lagN = Math.min(1, lag / ((BASE['sim.consumer_lag_p95'] || 1) * 11));
    curLag = lagN;
    var retry = at('sim.write_retry_rate', i), retryN = Math.min(1, retry / ((BASE['sim.write_retry_rate'] || 1) * 6));
    // the narrator's seat node wears a soft amber ring
    if (narrSeat && pts[narrSeat] && narrSeat !== selected) {
      var np = pts[narrSeat];
      g.strokeStyle = 'rgba(224,145,58,' + (0.4 + Math.sin(animT * 2.6) * 0.18) + ')';
      g.lineWidth = 1.4;
      g.beginPath(); g.arc(np.x, np.y, 40, 0, 7); g.stroke();
    }
    // orbit ring on the selected node — the chain is anchored HERE
    if (selected && pts[selected]) {
      var sp = pts[selected];
      g.strokeStyle = 'rgba(201,162,107,.8)'; g.lineWidth = 1.2; g.setLineDash([3, 5]);
      g.beginPath(); g.arc(sp.x, sp.y, 44 + Math.sin(animT * 2.2) * 3, 0, 7); g.stroke(); g.setLineDash([]);
    }
    // the backlog is a LOOP at the bus — rotating orbit ring + live depth + halo
    var eb = pts['event-bus'];
    if (eb) {
      if (lagN > 0.06) {
        var rad = eb.r * (1.6 + lagN * 2.6);
        var grd = g.createRadialGradient(eb.x, eb.y, eb.r * 0.35, eb.x, eb.y, rad);
        grd.addColorStop(0, 'rgba(200,74,74,' + (0.12 + lagN * 0.3) + ')'); grd.addColorStop(1, 'rgba(0,0,0,0)');
        g.fillStyle = grd; g.beginPath(); g.arc(eb.x, eb.y, rad, 0, 7); g.fill();
      }
      if (lagN > 0.45) {
        for (var sw = 0; sw < 3; sw++) {
          var ph2 = (animT * 0.5 + sw / 3) % 1;
          g.strokeStyle = 'rgba(200,74,74,' + ((1 - ph2) * 0.34 * lagN) + ')';
          g.lineWidth = 1.6;
          g.beginPath(); g.arc(eb.x, eb.y, eb.r * (1.2 + ph2 * 3.4), 0, 7); g.stroke();
        }
      }
      var orbR = eb.r * 1.45 + lagN * 7;
      g.strokeStyle = 'rgba(200,74,74,' + (0.18 + lagN * 0.62) + ')';
      g.lineWidth = 1.2 + lagN * 2.2;
      g.setLineDash([4, 6]); g.lineDashOffset = -animT * 34;
      g.beginPath(); g.arc(eb.x, eb.y, orbR, 0, 7); g.stroke();
      g.setLineDash([]); g.lineDashOffset = 0;
      g.textAlign = 'center'; g.font = '600 9.5px ui-monospace, monospace';
      g.fillStyle = 'rgba(200,74,74,' + Math.min(1, 0.45 + lagN * 0.55) + ')';
      g.fillText('⟳ backlog ' + fmtV(lag, 'msgs'), eb.x, eb.y + orbR + 13);
    }
    // edges
    EDGES.forEach(function (e) {
      var G = geom(e); if (!G) return;
      if (e[3] === 'retry') {
        // the retry loop is TOPOLOGY — visible at baseline, loud when it feeds itself
        g.strokeStyle = 'rgba(200,74,74,' + (0.16 + retryN * 0.66) + ')';
        g.lineWidth = 1.2 + retryN * 5;
        g.setLineDash([6, 5]); g.lineDashOffset = -animT * 26;
        g.beginPath(); g.moveTo(G.b.x, G.b.y); g.quadraticCurveTo(G.cp.x, G.cp.y, G.a.x, G.a.y); g.stroke();
        g.setLineDash([]); g.lineDashOffset = 0;
        var pmR = bez(G.b, G.cp, G.a, 0.5), pmR2 = bez(G.b, G.cp, G.a, 0.56);
        var angR = Math.atan2(pmR2.y - pmR.y, pmR2.x - pmR.x);
        g.save(); g.translate(pmR.x, pmR.y); g.rotate(angR);
        g.fillStyle = 'rgba(200,74,74,' + (0.45 + retryN * 0.55) + ')';
        g.beginPath(); g.moveTo(6, 0); g.lineTo(-4, -4); g.lineTo(-4, 4); g.closePath(); g.fill(); g.restore();
        g.textAlign = 'center'; g.font = '600 9.5px ui-monospace, monospace';
        g.fillStyle = 'rgba(200,74,74,' + Math.min(1, 0.5 + retryN * 0.5) + ')';
        g.fillText('↺ retries ' + fmtV(retry, '%'), pmR.x, pmR.y + 16);
        return;
      }
      // cascade heat spreads RIGHT of the bus as the backlog deepens
      var heat = (e[0] === 'ledger-writer' && e[1] === 'event-bus') ? lagN
        : (e[0] === 'event-bus' && e[1] === 'settlement-engine') ? Math.max(0, lagN - 0.18) * 0.95
        : (e[0] === 'settlement-engine') ? Math.max(0, lagN - 0.32) * 0.85
        : (e[0] === 'event-bus') ? Math.max(0, lagN - 0.25) * 0.6
        : 0;
      var heatCol = 'rgba(' + Math.round(232 - heat * 32) + ',' + Math.round(223 - heat * 149) + ',' + Math.round(211 - heat * 137) + ',' + (0.4 + heat * 0.35) + ')';
      if (e[3] === 'ext') {
        g.strokeStyle = 'rgba(232,223,211,.22)';
      } else if (heat > 0.05) {
        g.strokeStyle = heatCol;
      } else {
        var ca = (pts[e[0]] || {}).col || '#C9A26B', cb2 = (pts[e[1]] || {}).col || '#C9A26B';
        var grad = g.createLinearGradient(G.a.x, G.a.y, G.b.x, G.b.y);
        grad.addColorStop(0, rga(ca, 0.42)); grad.addColorStop(1, rga(cb2, 0.42));
        g.strokeStyle = grad;
      }
      var trunkW = (e[0] === 'ledger-writer' || e[1] === 'ledger-writer' || e[0] === 'event-bus' || e[1] === 'event-bus') ? 0.7 : 0;
      g.lineWidth = (e[3] === 'ext' ? 1.2 : 2 + trunkW) + heat * 2.2;
      if (e[3] === 'ext') g.setLineDash([4, 5]);
      g.beginPath(); g.moveTo(G.a.x, G.a.y); g.quadraticCurveTo(G.cp.x, G.cp.y, G.b.x, G.b.y); g.stroke(); g.setLineDash([]);
      // direction arrow at the crest — money flows left → right, visibly
      var pm = bez(G.a, G.cp, G.b, 0.55), pm2 = bez(G.a, G.cp, G.b, 0.6);
      var ang = Math.atan2(pm2.y - pm.y, pm2.x - pm.x);
      g.save(); g.translate(pm.x, pm.y); g.rotate(ang);
      g.fillStyle = heat > 0.05 ? heatCol : 'rgba(232,223,211,.55)';
      g.beginPath(); g.moveTo(5.5, 0); g.lineTo(-3.5, -3.6); g.lineTo(-3.5, 3.6); g.closePath(); g.fill();
      g.restore();
    });
    // ECG on the ledger→bus edge — consumer lag window
    var ecgE = EDGES[5], G2 = geom(ecgE);
    if (G2) {
      var WIN = 26, s0 = Math.max(0, i - WIN), sf = OV['sim.consumer_lag_p95'] || [];
      var mx = Math.max.apply(null, sf.concat([1]));
      g.beginPath(); var started = false;
      for (var k = s0; k <= i; k++) {
        var tt = (k - s0) / Math.max(1, i - s0);
        var pB = bez(G2.a, G2.cp, G2.b, tt);
        var dx2 = G2.b.x - G2.a.x, dy2 = G2.b.y - G2.a.y, dl = Math.hypot(dx2, dy2) || 1;
        var disp = ((sf[k] || 0) / mx - 0.25) * 24;
        var wx = pB.x + (-dy2 / dl) * disp, wy = pB.y + (dx2 / dl) * disp;
        started ? g.lineTo(wx, wy) : (g.moveTo(wx, wy), started = true);
      }
      var inten = Math.min(1, lag / mx);
      g.strokeStyle = 'rgba(' + Math.round(107 + inten * 93) + ',' + Math.round(175 - inten * 101) + ',' + Math.round(122 - inten * 48) + ',.85)';
      g.lineWidth = 2.2; g.stroke();
    }
    // particles — the transfers; slow through congestion
    parts.forEach(function (pp) {
      var e = EDGES[pp.e], G3 = geom(e); if (!G3) return;
      var slow = (e[0] === 'ledger-writer' || e[1] === 'event-bus' || e[0] === 'event-bus') ? (1 - lagN * 0.7) : 1;
      if (!reduced) pp.t += pp.spd * 0.016 * slow * (playing ? spd : 0.35);
      if (pp.t > 1) pp.t = 0;
      var col = e[3] === 'ext' ? '#7a7264' : '#E8DFD3';
      for (var tl = 3; tl >= 0; tl--) {
        var tt2 = Math.max(0, pp.t - tl * 0.012);
        var pos = bez(G3.a, G3.cp, G3.b, tt2);
        g.fillStyle = rga(col, tl === 0 ? 0.9 : 0.22 - tl * 0.05);
        g.beginPath(); g.arc(pos.x, pos.y, tl === 0 ? 2.2 : 1.6, 0, 7); g.fill();
      }
    });
    // retry particles (looping back) when amplification is live
    if (retryN > 0.08) {
      var G4 = geom(EDGES[10]);
      if (G4) for (var rp = 0; rp < Math.ceil(retryN * 6); rp++) {
        var tR = ((animT * 0.35 * spd) + rp / 6) % 1;
        for (var tl2 = 2; tl2 >= 0; tl2--) {
          var posR = bez(G4.b, G4.cp, G4.a, Math.max(0, tR - tl2 * 0.02));
          g.fillStyle = rga('#C84A4A', tl2 === 0 ? 0.95 : 0.25);
          g.beginPath(); g.arc(posR.x, posR.y, tl2 === 0 ? 2.4 : 1.7, 0, 7); g.fill();
        }
      }
    }
    drawNodes();
    if (walkSpot) {
      g.fillStyle = 'rgba(15,12,9,.52)';
      if (walkSpot[0] > 0) g.fillRect(0, 30, walkSpot[0], srH - 64);
      if (walkSpot[1] < srW) g.fillRect(walkSpot[1], 30, srW - walkSpot[1], srH - 64);
      g.strokeStyle = 'rgba(201,162,107,.42)'; g.lineWidth = 1;
      g.beginPath(); g.roundRect(walkSpot[0] + 2, 32, walkSpot[1] - walkSpot[0] - 4, srH - 68, 12); g.stroke();
    }
  }
  function updateHud() {
    var i = Math.floor(idx);
    KPIS.forEach(function (k, n) {
      var v = at(k.sig, i);
      var el = kpiEls[n]; if (!el) return;
      el.className = 'jkpi ' + ({ok: '', watch: 'watch', crit: 'crit'}[sev(k.sig, v)] || '');
      el.querySelector('.v').textContent = fmtV(v, k.unit.trim());
    });
    (J.services || []).forEach(function (s) {
      var r = svcSig(s.id); if (!r) return;
      var v = OV[r.id] ? at(r.id, i) : r.p95;
      NODE_LIVE[s.id] = {vTxt: fmtV(v, r.unit), sev: OV[r.id] ? sev(r.id, v) : 'ok'};
    });
    var mins = (PH.cadence_min || 1) * i;
    var h0 = parseInt((PH.clock_origin_et || '09:30').slice(0, 2), 10), m0 = parseInt((PH.clock_origin_et || '09:30').slice(3), 10);
    var tot = h0 * 60 + m0 + mins;
    $('jclk').textContent = inc.date + ' · ' + String(Math.floor(tot / 60)).padStart(2, '0') + ':' + String(tot % 60).padStart(2, '0') + ' ET';
    var phase = i < PH.build_end ? 0 : i < PH.drain_start ? 1 : 2;
    var liveStep = phase === 0 ? 0 : phase === 1 ? (at('sim.write_retry_rate', i) / (BASE['sim.write_retry_rate'] || 1) >= 3 ? 2 : 1) : 3;
    document.querySelectorAll('.pill').forEach(function (c, ci) { c.classList.toggle('live', ci === liveStep); });
    // the narrator strip at the stage floor; the seat node wears the ring
    var st = (inc.narrative_steps || [])[liveStep];
    var co = document.querySelector('[data-j="callout"]');
    if (st && co) {
      narrSeat = {0: 'event-bus', 1: 'ledger-writer', 2: 'ledger-writer', 3: 'event-bus'}[liveStep];
      var vLine = liveStep === 3 ? 'draining → ~' + fmtV(BASE[st.signal], 'msgs')
        : fmtV(at(st.signal, i), (st.unit || '').trim()) + ' now · peak ' + fmtV(st.derived_peak, (st.unit || '').trim());
      co.innerHTML = '<span class="cl-t">STEP ' + st.step + ' · ' + esc(st.label.toUpperCase()) + '</span>'
        + ' <span class="cl-v">@ ' + esc(narrSeat) + ' — ' + vLine + '</span>'
        + ' · <span class="cl-n">' + esc(st.text) + '</span>'
        + ' · <span class="cl-d">DO NOT OVERCLAIM: ' + esc(st.do_not_overclaim) + '</span>';
      co.title = st.text + ' — DO NOT OVERCLAIM: ' + st.do_not_overclaim;
      var coWrap = document.querySelector('[data-j="calloutwrap"]');
      if (coWrap) coWrap.style.display = 'flex';
    }
    scrub.value = i;
  }
  var scrub = document.querySelector('[data-j="scrub"]');
  scrub.max = N - 1;
  scrub.addEventListener('input', function () { idx = +scrub.value; playing = false; walkSpot = null; beatIdx = -1; playBtn.textContent = '▶ play the incident'; updateHud(); });
  var playBtn = document.querySelector('[data-j="play"]');
  playBtn.addEventListener('click', function () {
    playing = !playing;
    walkSpot = null; beatIdx = -1;
    if (playing && idx >= N - 2) idx = 0;
    playBtn.textContent = playing ? '❚❚ pause' : '▶ play the incident';
  });
  // ── the narrated walk: ◂ ▸ steps the incident's beats, spotlighting the seat ──
  var BEATS = [
    {i: 3, seat: 'event-bus', lbl: 'BASELINE',
     txt: 'all signals at their seeded baseline — the path clears steadily before the storm',
     dno: 'baseline is seeded, not measured'},
    {i: Math.max(6, Math.round(PH.build_end * 0.6)), ns: 0},
    {i: Math.max(8, Math.round((PH.build_end + PH.peak) / 2)), ns: 1},
    {i: PH.peak, ns: 2},
    {i: Math.min(N - 4, Math.round(PH.drain_start + (N - PH.drain_start) * 0.35)), ns: 3}
  ];
  var beatIdx = -1, walkSpot = null;
  var BEAT_SEAT = {0: 'event-bus', 1: 'ledger-writer', 2: 'ledger-writer', 3: 'event-bus'};
  function gotoBeat(bi) {
    beatIdx = (bi + BEATS.length) % BEATS.length;
    var b = BEATS[beatIdx];
    playing = false; playBtn.textContent = '▶ play the incident';
    idx = b.i; updateHud();
    var seat = b.seat || BEAT_SEAT[b.ns];
    var sp2 = pts[seat], srW2 = stage.clientWidth;
    walkSpot = sp2 ? [Math.max(0, sp2.x - srW2 * 0.175), Math.min(srW2, sp2.x + srW2 * 0.175)] : null;
    if (b.lbl) {
      var co2 = document.querySelector('[data-j="callout"]');
      co2.innerHTML = '<span class="cl-t">STEP 0 · ' + b.lbl + '</span>'
        + ' <span class="cl-v">@ ' + esc(seat) + '</span>'
        + ' · <span class="cl-n">' + esc(b.txt) + '</span>'
        + ' · <span class="cl-d">DO NOT OVERCLAIM: ' + esc(b.dno) + '</span>';
    }
  }
  document.querySelector('[data-j="beat-prev"]').addEventListener('click', function () {
    gotoBeat(beatIdx <= 0 ? BEATS.length - 1 : beatIdx - 1);
  });
  document.querySelector('[data-j="beat-next"]').addEventListener('click', function () {
    gotoBeat(beatIdx + 1);
  });
  document.querySelectorAll('.jspd button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.jspd button').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on'); spd = +b.getAttribute('data-spd');
    });
  });
  // time-based scheduler with an interval fallback: rAF is SUSPENDED on
  // hidden documents (embedded panes, background tabs) — the player must
  // still advance there, and dt-scaling keeps real browsers smooth.
  var lastT = performance.now(), rafAlive = false;
  function stepFrame(now) {
    var dt = Math.min(220, now - lastT); lastT = now;
    if (playing) {
      idx += 0.0132 * spd * dt;
      if (idx >= N - 1) { idx = N - 1; playing = false; playBtn.textContent = '▶ replay'; }
      updateHud();
    }
    animT += dt / 1000;
    draw();
  }
  function drawNodes() {
    (J.services || []).forEach(function (s) {
      var n = pts[s.id]; if (!n) return;
      var live = NODE_LIVE[s.id] || {};
      var sevc = SEVCOL[live.sev || 'ok'];
      // pulsing severity glow behind risk-bearing nodes (the reference device)
      if (live.sev && live.sev !== 'ok') {
        var pulse = 0.10 + Math.sin(animT * 2.2 + n.x * 0.008) * 0.05;
        var gg2 = g.createRadialGradient(n.x, n.y, n.r * 0.3, n.x, n.y, n.r * 2.4);
        gg2.addColorStop(0, rga(sevc, pulse * (live.sev === 'crit' ? 2.2 : 1.4)));
        gg2.addColorStop(1, 'rgba(0,0,0,0)');
        g.fillStyle = gg2; g.beginPath(); g.arc(n.x, n.y, n.r * 2.4, 0, 7); g.fill();
      }
      var rr = n.r + (s.id === 'event-bus' ? curLag * n.r * 0.16 * (1 + Math.sin(animT * 3) * 0.35) : 0);
      g.beginPath(); g.arc(n.x, n.y, rr, 0, 7);
      g.fillStyle = rga(n.col, selected === s.id ? 0.2 : 0.09); g.fill();
      g.strokeStyle = rga(n.col, selected === s.id ? 0.9 : n.ext ? 0.25 : 0.5);
      g.lineWidth = selected === s.id ? 2 : 1.4;
      if (n.ext) g.setLineDash([3, 3]);
      g.stroke(); g.setLineDash([]);
      g.textAlign = 'center'; g.shadowColor = 'rgba(0,0,0,.9)'; g.shadowBlur = 5;
      var fs = Math.max(9, n.r * 0.34);
      g.fillStyle = selected === s.id ? '#fff' : n.col;
      g.font = '700 ' + fs + 'px ui-monospace, monospace';
      g.fillText(s.id, n.x, n.y - 3);
      g.fillStyle = live.sev && live.sev !== 'ok' ? sevc : 'rgba(232,223,211,.62)';
      g.font = '600 ' + Math.max(8, n.r * 0.3) + 'px ui-monospace, monospace';
      g.fillText(live.vTxt || '', n.x, n.y + fs * 0.85);
      g.shadowBlur = 0;
    });
  }
  function loop(now) { rafAlive = true; stepFrame(now || performance.now()); requestAnimationFrame(loop); }
  setInterval(function () { if (!rafAlive) stepFrame(performance.now()); rafAlive = false; }, 250);
  window.addEventListener('resize', centers);

  // ── 01 · the chain as a CARD (click a node or a chip) ──
  var selected = inc.seat_service || 'event-bus';
  function chainCard(s) {
    return '<div class="jchead"><span class="id">' + esc(s.id) + '</span>'
      + '<span class="lyr">' + esc(s.layer) + ' · ' + esc(s.stage) + '</span>'
      + '<span class="own">' + esc(s.owner) + '</span>'
      + ((inc.participants || []).indexOf(s.id) >= 0 ? '<span style="color:var(--red)">⚠ ' + esc(inc.id) + ' participant</span>' : '') + '</div>'
      + '<div class="hop">observed signal</div>'
      + (s.signal_rows || []).map(function (r) {
          return '<div class="sigrow"><span class="sid">' + esc(r.id) + '</span>'
            + '<span>mean ' + fmtV(r.mean, r.unit) + ' · p95 ' + fmtV(r.p95, r.unit) + ' · max ' + fmtV(r.max, r.unit) + '</span>'
            + '<span class="chip">' + esc(chip(r.chip)) + '</span>'
            + (r.incident_participant ? '<span style="color:var(--red)">' + esc(inc.id) + ' peak ' + fmtV(r.incident_peak, r.unit) + ' (' + esc(r.incident_peak_over_baseline) + '×)</span>' : '')
            + '<span class="intent">' + esc(r.query_intent) + '</span></div>';
        }).join('')
      + '<div class="hop">risk patterns on this service</div>'
      + (s.risk_links || []).map(function (l) {
          return '<div class="risklnk"><span class="pid">' + esc(l.pattern_id) + '</span>'
            + '<span class="usd">' + M(l.residual_p95_usd) + ' residual P95</span>'
            + '<span>controls: ' + (l.controls_linked || []).map(esc).join(' · ') + '</span>'
            + '<span class="cvt">' + esc(l.controls_caveat) + '</span></div>';
        }).join('')
      + '<div class="hop">owner</div>'
      + '<div class="sigrow"><span class="sid">' + esc(s.owner) + '</span><span class="cvt">' + esc(s.owner_caveat) + '</span></div>'
      + (s.non_claim ? '<div class="nonclaim">NON-CLAIM · ' + esc(s.non_claim) + '</div>' : '');
  }
  function selectSvc(id) {
    var card = document.querySelector('.jchaincard');
    if (selected === id && card.classList.contains('on')) {
      card.classList.remove('on'); selected = null;
      return;
    }
    selected = id;
    var s = svcById[id]; if (!s) return;
    card.innerHTML = '<span class="x" data-j="cardx">✕</span>' + chainCard(s);
    card.classList.add('on');
    var pt = pts[id], sr = stage.getBoundingClientRect();
    if (pt) {
      var cw = Math.min(340, sr.width * 0.44);
      var lx = pt.x + 64; if (lx + cw > sr.width - 6) lx = pt.x - cw - 64;
      var ctop = Math.max(6, Math.min(sr.height - 210, pt.y - 60));
      card.style.left = Math.max(6, lx) + 'px';
      card.style.top = ctop + 'px';
      card.style.maxHeight = Math.max(150, sr.height - ctop - 44) + 'px';
    }
    card.querySelector('[data-j="cardx"]').addEventListener('click', function () {
      card.classList.remove('on'); selected = null;
    });
  }
  $('chaincap').textContent = (J.chain_caveats || {}).patterns + ' · ' + (J.port_tag || '');

  // ── the incident walk (docked under the canvas) ──
  $('incid-t2').textContent = inc.id || '';
  $('inchdr').innerHTML = '<b>' + esc(inc.name) + '</b> · ' + esc(inc.date) + ' ' + esc(inc.window_et)
    + ' ET · seat: <b>' + esc(inc.seat_service) + '</b> — steps light up as the player runs; click one to jump';
  var spark = function (sig) {
    var ser = OV[sig]; if (!ser || !ser.length) return '';
    var mx = Math.max.apply(null, ser), mn = Math.min.apply(null, ser);
    var pts = ser.map(function (v, i) {
      return (i / (ser.length - 1) * 300).toFixed(1) + ',' + (40 - ((v - mn) / (mx - mn || 1)) * 36).toFixed(1);
    }).join(' ');
    return '<div class="spark"><svg viewBox="0 0 300 44" preserveAspectRatio="none">'
      + '<line class="base" x1="0" y1="40" x2="300" y2="40"></line>'
      + '<polyline class="pl" points="' + pts + '"></polyline></svg>'
      + '<div class="cap2">' + esc(sig) + ' · ' + esc(chip((OV.__chips || {})[sig])) + '</div></div>';
  };
  $('steps').innerHTML = (inc.narrative_steps || []).map(function (st) {
    var vLine = st.step === 4
      ? '→ ~' + fmtV(BASE[st.signal], 'msgs')
      : fmtV(st.derived_peak, (st.unit || '').trim()) + ' · ' + st.derived_peak_over_baseline + '×';
    return '<span class="pill' + (st.step === 4 ? ' p4' : '') + '" data-step="' + st.step + '" title="'
      + esc(st.text + ' DO NOT OVERCLAIM · ' + st.do_not_overclaim) + '">'
      + '<b>' + st.step + '</b> ' + esc(st.label.toLowerCase()) + ' · ' + esc(vLine) + '</span>';
  }).join('');
  $('incso').innerHTML = '<b>So what:</b> ' + esc(inc.so_what);
  var hv = inc.hv_cross_reference || {};
  $('inccap').textContent = 'war-room view: the hypervelocity observatory — kafka_lag (' + (hv.kafka_lag || '')
    + ') · identity_outage (' + (hv.identity_outage || '') + '). Peaks derive from ' + ((J.generator || {}).id || '') + '; typing one is a build failure (C36.3).';

  // ── 03 · audiences that re-argue ──
  var topPat = (J.services || []).reduce(function (acc, s) {
    (s.risk_links || []).forEach(function (l) { if (!acc[l.pattern_id]) acc[l.pattern_id] = l.residual_p95_usd; });
    return acc;
  }, {});
  var patRows = Object.keys(topPat).map(function (k) { return [k, topPat[k]]; })
    .sort(function (a, b) { return (b[1] || 0) - (a[1] || 0); }).slice(0, 3);
  var depOnPath = {}; (J.services || []).forEach(function (s) { (s.dependency_nodes || []).forEach(function (d) { depOnPath[d] = 1; }); });
  var depRows = ((P.dependency_layer || {}).nodes || []).filter(function (n) { return depOnPath[n.id]; }).slice(0, 3);
  var ledgerSvc = (J.services || []).filter(function (s) { return s.stage === inc.stage; });
  var stepPeaks = (inc.narrative_steps || []).slice(0, 3);
  var statTile = function (v, unit, k) {
    return '<div class="atile"><div class="v">' + v + '<small>' + esc(unit) + '</small></div><div class="k">' + esc(k) + '</div></div>';
  };
  var hbar = function (nm, val, mx, txt, red) {
    var pct = Math.max(3, Math.round(val / (mx || 1) * 100));
    return '<div class="abar"><span class="nm">' + esc(nm) + '</span><span class="tr"><span class="fl' + (red ? ' red' : '') + '" style="width:' + pct + '%"></span></span><span class="vv">' + esc(txt) + '</span></div>';
  };
  var depMax = Math.max.apply(null, depRows.map(function (n) { return n.delta_p95_usd || 0; }).concat([1]));
  var patMax = Math.max.apply(null, patRows.map(function (r) { return r[1] || 0; }).concat([1]));
  var AUD = {
    eng: {label: 'Engineering', html:
      '<div class="atiles">' + stepPeaks.map(function (st) {
        return statTile(st.derived_peak >= 100 ? Math.round(st.derived_peak).toLocaleString() : st.derived_peak, st.unit + ' · ' + st.derived_peak_over_baseline + '×', st.label);
      }).join('') + '</div>'
      + '<div class="apills"><span class="apill warn">journey SLO: seeded</span><span class="apill warn">per-signal thresholds: NOT DEFINED — that absence is the finding</span><span class="apill">β lever on the <a href="validation.html" style="color:inherit">validation package</a></span></div>'
      + '<div class="aline"><b>Confirm:</b> does this shape — build → peak → silent drain — match how your estate degrades? One click, no new work.</div>'},
    risk: {label: '2LoD Risk', html:
      '<div class="aline">Shared-dependency concentration ON this path (same sealed tornado):</div>'
      + depRows.map(function (n) { return hbar(n.name || n.id, n.delta_p95_usd || 0, depMax, M(n.delta_p95_usd), true); }).join('')
      + '<div class="aline" style="margin-top:8px">Largest residual on the path (same sealed MC as the headline):</div>'
      + patRows.map(function (r) { return hbar(r[0], r[1] || 0, patMax, M(r[1])); }).join('')
      + '<div class="aline">Decisions stay on the <a href="board.html">board brief</a> — this surface is observation-only: <b>no findings, no verdicts</b>.</div>'},
    audit: {label: 'Audit', html:
      '<div class="abar"><span class="nm">four-hop chains complete</span><span class="tr"><span class="fl" style="width:100%"></span></span><span class="vv">' + (J.services || []).length + ' / ' + (J.services || []).length + '</span></div>'
      + '<div class="apills"><span class="apill">C36.3 · peaks recompute</span><span class="apill">C36.4 · chains + caveats</span><span class="apill">C38.2 · passthrough proven</span><span class="apill">C9 · chips derive</span></div>'
      + '<div class="aline">' + esc(J.port_tag || '') + ' Every governance action stays A8-gated and hash-chained — the journey adds the operational join, not a second system of record.</div>'},
    board: {label: 'Board', html:
      '<div class="atiles">'
      + statTile(Math.round(slo.end_to_end_p95_ms || 0).toLocaleString(), 'ms vs ' + Math.round(slo.target_ms || 0).toLocaleString(), 'end-to-end p95 · within target')
      + statTile(slo.availability_observed_pct, '% vs ' + slo.availability_target_pct + '%', 'availability')
      + statTile('1', ' hour', 'the riskiest hour was invisible to level alerts') + '</div>'
      + '<div class="aline">Customers can move money — and ' + esc(inc.id) + ' is why the concentration resolution matters, in the shape of one journey. The five asks live on the <a href="board.html">board brief</a>; nothing here requests a vote.</div>'}
  };
  var audKeys = ['eng', 'risk', 'audit', 'board'];
  $('teaser-3').textContent = audKeys.length + ' audiences · tiles and bars, not memos';
  $('audbar').innerHTML = audKeys.map(function (k, i) {
    return '<button class="audbtn' + (i === 0 ? ' on' : '') + '" data-aud="' + k + '">' + esc(AUD[k].label) + '</button>';
  }).join('');
  var renderAud = function (k) { $('audrows').innerHTML = AUD[k].html; };
  renderAud('eng');
  document.querySelectorAll('.audbtn').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.audbtn').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on'); renderAud(b.getAttribute('data-aud'));
    });
  });
  $('audcap').textContent = 'Every tile and bar hydrates from the same sealed projection — different arguments, one world.';

  // chapter accordion + keys
  var openAct = function (n) {
    document.querySelectorAll('.act').forEach(function (a, i) {
      var on = (i + 1) === n;
      a.classList.toggle('open', on);
      a.querySelector('.act-head').setAttribute('aria-expanded', on ? 'true' : 'false');
      if (on && a.scrollIntoView) a.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
  };
  document.querySelectorAll('.act-head').forEach(function (h) {
    h.addEventListener('click', function () { openAct(parseInt(h.getAttribute('data-act'), 10)); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === '1' && !e.metaKey && !e.ctrlKey && !e.altKey) openAct(1);
  });
  // ── the 90d trend: the spike must be VISIBLE (stage 5) ──
  (function () {
    var tr = OV.__trend || {}; var s = tr.series || []; if (!s.length) return;
    var tcv = document.querySelector('[data-j="trendcv"]'); if (!tcv) return;
    var tg = tcv.getContext('2d');
    var W = tcv.clientWidth || 900, H = 110;
    tcv.width = W * dpr; tcv.height = H * dpr; tg.setTransform(dpr, 0, 0, dpr, 0, 0);
    var mx = Math.max.apply(null, s), mn = Math.min.apply(null, s);
    // the incident day sits at day 77 of 90 — shade its slice of the window
    var x0 = (77 / 90) * W, x1 = (77.5 / 90) * W;
    tg.fillStyle = 'rgba(200,74,74,.13)'; tg.fillRect(x0, 0, Math.max(3, x1 - x0), H);
    tg.beginPath();
    s.forEach(function (v, i) {
      var x = i / (s.length - 1) * W, y = H - 8 - ((v - mn) / (mx - mn || 1)) * (H - 22);
      i ? tg.lineTo(x, y) : tg.moveTo(x, y);
    });
    tg.strokeStyle = 'rgba(201,162,107,.85)'; tg.lineWidth = 1.3; tg.stroke();
    tg.lineTo(W, H); tg.lineTo(0, H); tg.closePath();
    var ag = tg.createLinearGradient(0, 0, 0, H);
    ag.addColorStop(0, 'rgba(201,162,107,.18)'); ag.addColorStop(1, 'rgba(201,162,107,0)');
    tg.fillStyle = ag; tg.fill();
    tg.font = '600 9px ui-monospace, monospace'; tg.fillStyle = 'rgba(200,74,74,.95)'; tg.textAlign = 'center';
    tg.fillText('▲ ' + inc.id, Math.min(W - 40, x0 + 2), 12);
    var ch2 = ((OV.__chips || {})['sim.consumer_lag_p95'] || {});
    $('trendcap').textContent = tr.sig + ' — the full ' + ((tr.window || {}).days || 90) + 'd window at ' + (tr.cadence || '8h')
      + ' (' + s.length + 'pts, downsampled from SEEDED 1h) — one spike, one journey-threatening hour, invisible to level alerts before it. '
      + 'Peak ' + Math.round(mx).toLocaleString() + ' msgs — the tower is the incident; everything else is the diurnal rhythm.';
  })();
  // step cards drive the player
  document.querySelectorAll('.pill').forEach(function (c, ci) {
    c.addEventListener('click', function () {
      idx = [Math.max(0, PH.build_end - 8), PH.peak, Math.min(PH.peak + 6, N - 1), Math.min(PH.drain_start + 10, N - 1)][ci] || 0;
      playing = false; playBtn.textContent = '▶ play the incident'; updateHud();
    });
  });
  // ── boot the stage ──
  centers(); seed(); idx = PH.peak || 45; selected = null; updateHud(); loop();

  // read-grammar hash router: #act=N deep-links a chapter (same contract as board/read)
  var applyHash = function () {
    var m = /act=(\d)/.exec(location.hash || '');
    if (m) openAct(parseInt(m[1], 10));
  };
  window.addEventListener('hashchange', applyHash);
  applyHash();
})();
</script>
</body>
</html>
"""


def write_journey_page(projection_path: str | None = None, output_path: str | None = None) -> str:
    proj_file = Path(projection_path) if projection_path else (
        sorted((_ROOT / "outputs" / "v2_0a").glob("*_projection.json"))[-1])
    projection = json.loads(proj_file.read_text())
    period = (projection.get("meta") or {}).get("period", "")

    # incident-window overlays for the sparklines — same seeded generator,
    # separate island (the shared projection's leaf multiset stays untouched)
    from utils.journey_signals import (overlay_series, base_series, signal_stats,
                                       INCIDENT, GEN_ID, _SPECS)
    js = projection.get("journey_spine") or {}
    stats = signal_stats()
    # stage 5: EVERY incident-participant signal rides the player, full minute
    # resolution — the observatory needs the real shapes, not summaries
    participants = sorted(s for s, v in stats.items() if v.get("incident_participant"))
    overlays = {sig: overlay_series(sig, downsample=1) for sig in participants}
    overlays["__chips"] = {sig: {"realness": "SEEDED",
                                 "pts": len(overlays[sig]),
                                 "cadence": INCIDENT["overlay_cadence"],
                                 "gen": GEN_ID} for sig in participants}
    overlays["__baselines"] = {sig: _SPECS[sig][0] for sig in _SPECS}
    # derived phase boundaries from the star signal (never typed): build ends
    # when lag first crosses half its peak; drain starts when it falls back
    star = overlays.get("sim.consumer_lag_p95") or []
    if star:
        peak_i = max(range(len(star)), key=lambda i: star[i])
        half = star[peak_i] / 2.0
        build_end = next((i for i in range(len(star)) if star[i] >= half), 0)
        drain_start = next((i for i in range(peak_i, len(star)) if star[i] < half), len(star) - 1)
        overlays["__phases"] = {"build_end": build_end, "peak": peak_i,
                                "drain_start": drain_start, "n": len(star),
                                "start_et": INCIDENT["start_et"], "cadence_min": 1,
                                "clock_origin_et": "09:30"}
    # the 90d trend for the star signal — the spike must be VISIBLE, not stated
    overlays["__trend"] = {"sig": "sim.consumer_lag_p95",
                           "series": base_series("sim.consumer_lag_p95", downsample=8),
                           "cadence": "8h", "window": dict(js.get("window") or {})}

    html = (_TEMPLATE
            .replace("__PERIOD__", period)
            .replace("__DISCLOSURE__", _DISCLOSURE)
            .replace("__PROJECTION__", json.dumps(projection).replace("</", "<\\/"))
            .replace("__OVERLAYS__", json.dumps(overlays).replace("</", "<\\/")))
    out = Path(output_path) if output_path else (_ROOT / "docs" / "journey.html")
    out.write_text(html)
    print(f"wrote: {out}")
    return str(out)
