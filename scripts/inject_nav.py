#!/usr/bin/env python3
"""inject_nav — ONE navigation drawer on EVERY human-facing page.

Operator (r42): "we need navigation window on the left for each of these
links connected for an easy map. Without it I am completely lost."

One component, injected post-build into every page (idempotent via marker
comments), so the map cannot drift per-page:
  - fixed left drawer, closed by default (zero layout impact on any page),
    opened by an always-visible MAP tab on the left edge; state persists
  - the full site map with a you-are-here highlight (pathname match)
  - absolute /apps/... hrefs for the served monorepo; inside the review
    bundle the SAME bytes resolve their own links at runtime (data-pb flat
    paths) so shipped pages stay byte-identical to the audited files
  - classics are frozen archives and are NEVER injected

Run from repo root:  python3 scripts/inject_nav.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# r43: 13 pages fold to 5 destinations — reads/tour are redirect stubs
# (no nav; they bounce immediately), classics/protos live in archive/.
PAGES = [
    "PORTFOLIO_INDEX.html",
    "apps/risk-as-code-agent/docs/index.html",
    "apps/risk-as-code-agent/docs/journey.html",
    "apps/risk-as-code-agent/docs/board.html",
    "apps/risk-as-code-agent/docs/validation.html",
    "apps/agent-trace-gov/docs/index.html",
    "apps/hypervelocity-risk-sim/docs/index.html",
]

MARK_A = "<!-- portfolio-nav -->"
MARK_B = "<!-- /portfolio-nav -->"

NAV = MARK_A + r"""
<style>
#pnav-tab{position:fixed;left:0;top:50%;transform:translateY(-50%);z-index:9998;writing-mode:vertical-rl;
  text-orientation:mixed;font:600 10px ui-monospace,monospace;letter-spacing:.22em;color:rgba(232,223,211,.75);
  background:rgba(24,20,16,.92);border:1px solid rgba(214,196,162,.3);border-left:none;border-radius:0 8px 8px 0;
  padding:14px 5px;cursor:pointer;user-select:none}
#pnav-tab:hover{color:#C9A26B;border-color:#C9A26B}
#pnav{position:fixed;left:0;top:0;bottom:0;width:216px;z-index:9999;transform:translateX(-100%);
  transition:transform .22s ease;background:rgba(20,17,13,.97);border-right:1px solid rgba(214,196,162,.25);
  font-family:ui-monospace,monospace;overflow-y:auto;padding:14px 0 20px;
  box-shadow:8px 0 40px rgba(0,0,0,.5)}
#pnav.open{transform:translateX(0)}
#pnav .pn-x{position:absolute;top:8px;right:12px;color:rgba(232,223,211,.4);cursor:pointer;font-size:13px}
#pnav .pn-x:hover{color:#C9A26B}
#pnav .pn-t{font-size:10px;letter-spacing:.2em;color:#C9A26B;padding:8px 16px 4px;text-transform:uppercase}
#pnav .pn-g{font-size:9.5px;letter-spacing:.16em;color:rgba(232,223,211,.38);padding:12px 16px 3px;text-transform:uppercase}
#pnav a{display:block;padding:5px 16px 5px 22px;font-size:11.5px;color:rgba(232,223,211,.68);text-decoration:none;line-height:1.4}
#pnav a:hover{color:#E8DFD3;background:rgba(201,162,107,.08)}
#pnav a.here{color:#C9A26B;border-left:2px solid #C9A26B;padding-left:20px;background:rgba(201,162,107,.10)}
#pnav a small{color:rgba(232,223,211,.35);font-size:9.5px}
#pnav a.annex{padding-left:30px;font-size:10.5px;color:rgba(232,223,211,.5)}
#pnav .pn-f{margin-top:14px;padding:10px 16px 0;border-top:1px solid rgba(214,196,162,.14);
  font-size:9px;color:rgba(232,223,211,.32);line-height:1.5}
@media print{#pnav,#pnav-tab{display:none}}
</style>
<div id="pnav-tab" title="the site map">M A P</div>
<nav id="pnav" aria-label="Portfolio map">
  <span class="pn-x" title="close">✕</span>
  <div class="pn-t">The map</div>
  <div class="pn-g">Start here</div>
  <a href="@@ROOT@@PORTFOLIO_INDEX.html" data-pn="PORTFOLIO_INDEX.html" data-pb="landing.html">⌂ front door <small>· doors + the guided tour</small></a>
  <div class="pn-g">risk-as-code · priced engine</div>
  <a href="@@ROOT@@apps/risk-as-code-agent/docs/journey.html" data-pn="apps/risk-as-code-agent/docs/journey.html" data-pb="rac/journey.html">▶ the journey <small>· one money path, played</small></a>
  <a href="@@ROOT@@apps/risk-as-code-agent/docs/index.html" data-pn="apps/risk-as-code-agent/docs/index.html" data-pb="rac/index.html">workbench <small>· price it, challenge it, sign it</small></a>
  <a class="annex" href="@@ROOT@@apps/risk-as-code-agent/docs/board.html" data-pn="apps/risk-as-code-agent/docs/board.html" data-pb="rac/board.html">⎙ board brief <small>· print annex</small></a>
  <a class="annex" href="@@ROOT@@apps/risk-as-code-agent/docs/validation.html" data-pn="apps/risk-as-code-agent/docs/validation.html" data-pb="rac/validation.html">⎙ validation <small>· examiner annex</small></a>
  <div class="pn-g">agent-trace-gov · agent governance</div>
  <a href="@@ROOT@@apps/agent-trace-gov/docs/index.html" data-pn="apps/agent-trace-gov/docs/index.html" data-pb="atg/index.html">workbench <small>· traces → verdict-free findings</small></a>
  <div class="pn-g">hypervelocity · incident observatory</div>
  <a href="@@ROOT@@apps/hypervelocity-risk-sim/docs/index.html" data-pn="apps/hypervelocity-risk-sim/docs/index.html" data-pb="hv/index.html">observatory <small>· four failure shapes, animated</small></a>
  <div class="pn-f">The highlighted line is where you are. ⎙ pages are printable briefs.</div>
</nav>
<script>
(function () {
  'use strict';
  var nav = document.getElementById('pnav'), tab = document.getElementById('pnav-tab');
  if (!nav || !tab) return;
  var KEY = 'portfolio_nav_open';
  function setOpen(on) {
    nav.classList.toggle('open', on);
    tab.style.display = on ? 'none' : '';
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
  }
  tab.addEventListener('click', function () { setOpen(true); });
  nav.querySelector('.pn-x').addEventListener('click', function () { setOpen(false); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && nav.classList.contains('open')) setOpen(false);
  });
  try { if (localStorage.getItem(KEY) === '1') setOpen(true); } catch (e) {}
  var path = location.pathname;
  var dIdx = path.indexOf('/dashboards/');
  if (dIdx >= 0) {
    // review-bundle flat layout: resolve links at RUNTIME so the shipped
    // page stays byte-identical to the audited repo file (B9 hash equality)
    var sub = path.slice(dIdx + 12);
    var up = sub.indexOf('/') >= 0 ? '../' : '';
    nav.querySelectorAll('a[data-pb]').forEach(function (a) {
      a.setAttribute('href', up + a.getAttribute('data-pb'));
      if (sub === a.getAttribute('data-pb')) a.classList.add('here');
    });
  } else {
    nav.querySelectorAll('a[data-pn]').forEach(function (a) {
      var pn = a.getAttribute('data-pn');
      if (path.slice(-pn.length) === pn
          || (pn === 'PORTFOLIO_INDEX.html' && /(^|\/)(index\.html)?$/.test(path) && path.indexOf('apps') < 0 && path.indexOf('docs') < 0)) {
        a.classList.add('here');
      }
    });
  }
})();
</script>
""" + MARK_B


def inject(page: Path, rel: str) -> str:
    # r84: hrefs are DEPTH-RELATIVE per page (../ per directory level) — a
    # root-absolute "/apps/..." works only when the site is mounted at the
    # domain root and 404s under a subpath (GitHub Pages project sites).
    prefix = "../" * rel.count("/")
    nav_html = NAV.replace("@@ROOT@@", prefix)
    html = page.read_text()
    if MARK_A in html:
        pre = html.split(MARK_A)[0]
        post = html.split(MARK_B)[-1]
        # r56b: injection adds NAV + "\n" before </body>; the strip must remove
        # that SAME newline or every inject cycle accretes one byte — enough
        # cycles and the shipped page no longer byte-matches its sealed build
        # (caught by the export's body-hash seal recompute, V2).
        html = pre + post.lstrip("\n")
    if "</body>" not in html:
        return "SKIP (no </body>)"
    html = html.replace("</body>", nav_html + "\n</body>", 1)
    page.write_text(html)
    return "injected"


def main() -> None:
    for rel in PAGES:
        p = ROOT / rel
        if not p.exists():
            print(f"  MISSING  {rel}")
            continue
        print(f"  {inject(p, rel):9s} {rel}")


if __name__ == "__main__":
    main()
