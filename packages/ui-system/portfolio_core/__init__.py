"""
portfolio_core — the shared, genuinely-reusable layer across the three
cybersecurity-risk portfolio projects (risk-as-code-agent, agent-trace-gov,
hypervelocity-risk-sim).

Per the agent-trace-gov v2 port spec §14.D / §15.D-F: this package is the
NON-copy-paste extraction of the 100%-generic foundation. Each project imports
it; make_projection stays per-domain in each project. Extracting it (rather
than copying) is what makes the portfolio's "reusable foundation" claim TRUE
rather than asserted.

Extraction order (port spec §15.E):
  1. action_log + provenance  ← THIS milestone (Stage 0, step 1)
  2. presentation (render-from-data + CSS/JS)   ← step 2
  3. audit harness (parameterized)              ← step 3

No pip install required — consuming projects add this package's parent dir to
sys.path via a 3-line bootstrap (portfolio-core is a sibling of each project
under /Users/jitendranjoshi/code/).
"""
from __future__ import annotations

__version__ = "0.1.0"

from . import action_log, provenance  # noqa: F401

__all__ = ["action_log", "provenance", "__version__"]
