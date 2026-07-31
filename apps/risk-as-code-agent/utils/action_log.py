"""
utils.action_log — SHIM onto the shared portfolio_core.action_log.

Extracted to portfolio_core (port spec §15.D/E) — the hash-chained attestation
log is now genuinely shared across the portfolio, not copy-pasted. This shim
preserves the original import surface (`from utils.action_log import …`) and
points the shared log at THIS project's file + verb vocabulary, so behavior is
identical to the pre-extraction module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Bootstrap: make the sibling portfolio_core package importable (no install).
#    ui-system is the hub package at <repo>/packages/ui-system.
_PC_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages", "ui-system"))
if _PC_PARENT not in sys.path:
    sys.path.insert(0, _PC_PARENT)

from portfolio_core import action_log as _core  # noqa: E402
# Re-export the full public surface so existing imports keep working.
from portfolio_core.action_log import (  # noqa: E402,F401
    SCHEMA_VERSION, VERBS, ROLE_TIERS, JUSTIFICATION_MIN_WORDS,
    validate_entry, read_log, verify_chain, make_entry, append_entry,
    action_log_summary,
)

# ── Configure the shared log for risk-as-code-agent (finance domain).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_core.configure(
    log_file=_PROJECT_ROOT / "data" / "action_log.jsonl",
    project_root=_PROJECT_ROOT,
    # finance verb set = the portfolio_core default; named-human + ≥12-word +
    # expiry rules are shared and unchanged.
)
