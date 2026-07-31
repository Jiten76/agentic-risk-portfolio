"""
read_page (atg) — r43: THE READ IS FOLDED HOME.

Operator directive 2026-07-25 ("we have 13 links/pages... what a mess"):
13 pages fold to 5 destinations. This spoke's read duplicated devices the
workbench already renders (the counted lineage hero is the catch-flow; the signal hero is the trail); nothing unique remained to carry, so the
read becomes a REDIRECT STUB and old links keep working. The pre-fold page is
frozen at docs/archive/read_pre_r43.html (nothing deleted); full template
history lives in git.

Build:  python3 -c "import sys; sys.path.insert(0,'.'); from utils.read_page import write_read_page; write_read_page()"
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_STUB = '<!DOCTYPE html>\n<!-- redirect-stub · r43: the read folded into the workbench -->\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta http-equiv="refresh" content="0; url=index.html">\n<title>agent-trace-gov · the read → folded into the workbench</title>\n<style>\nbody { background: #14110D; color: #E8DFD3; font-family: ui-monospace, Menlo, monospace; padding: 48px 32px; line-height: 1.6; }\na { color: #C9A26B; }\n.ribbon { font-size: 11.5px; color: rgba(20,17,13,.92); background: #C9A26B; padding: 6px 22px; margin: -48px -32px 40px; }\n</style>\n</head>\n<body>\n<div class="ribbon">A demonstrator on <b>synthetic</b> telemetry — every number traces to its source.</div>\n<p>The read&#39;s pictures already live <b>inside the workbench</b> — the lineage graph IS the catch picture, counted from traces. One page fewer to be lost on.</p>\n<p><a href="index.html">continue to the workbench &#8599;</a> · <a href="archive/read_pre_r43.html">the pre-fold page, frozen &#8599;</a></p>\n</body>\n</html>\n'


def write_read_page(projection_path: str | None = None, output_path: str | None = None) -> str:
    out = Path(output_path) if output_path else _ROOT / "docs" / "read.html"
    out.write_text(_STUB, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print("wrote:", write_read_page())
