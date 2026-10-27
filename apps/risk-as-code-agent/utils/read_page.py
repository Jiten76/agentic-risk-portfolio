"""
read_page — r43: THE READ IS FOLDED HOME.

The story-first read page is now the workbench's CLOSING CHAPTER (ia node
`story` on every role path — its flow picture + narrated walker live in
utils/v2_html_report.renderStoryFlow; the number/docket screens it duplicated
were already workbench panels). Operator directive 2026-07-25: "we have 13
links/pages... what a mess" → 13 pages fold to 5 destinations.

This module now writes a REDIRECT STUB so old links and bookmarks keep
working. The pre-fold page is frozen at docs/archive/read_pre_r43.html
(nothing deleted); the full template history lives in git.

Build:  python3 -c "import sys; sys.path.insert(0,'.'); from utils.read_page import write_read_page; write_read_page()"
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_STUB = """<!DOCTYPE html>
<!-- redirect-stub · r43: the read folded into the workbench closing chapter -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url=index.html#role=basic&node=story">
<title>risk-as-code-agent · the read → folded into the workbench</title>
<style>
body { background: #14110D; color: #E8DFD3; font-family: ui-monospace, Menlo, monospace; padding: 48px 32px; line-height: 1.6; }
a { color: #C9A26B; }
.ribbon { font-size: 11.5px; color: rgba(20,17,13,.92); background: #C9A26B; padding: 6px 22px; margin: -48px -32px 40px; }
</style>
</head>
<body>
<div class="ribbon">A demonstrator on <b>synthetic</b> telemetry. Firm-specific dollar figures are illustrative; the risk logic and every threshold&#39;s public source are real, and each number traces to it.</div>
<p>The read now lives <b>inside the workbench</b> as its closing chapter — one page fewer to be lost on.</p>
<p><a href="index.html#role=basic&node=story">continue to the workbench &#8599;</a> · <a href="archive/read_pre_r43.html">the pre-fold page, frozen &#8599;</a></p>
</body>
</html>
"""


def write_read_page(projection_path: str | None = None, output_path: str | None = None) -> str:
    out = Path(output_path) if output_path else _ROOT / "docs" / "read.html"
    out.write_text(_STUB, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print("wrote:", write_read_page())
