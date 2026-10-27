"""
portfolio_core.provenance — shared per-value provenance helpers.

EXTRACTED from risk-as-code-agent/utils/projection.py. Per A2, every numeric
value that reaches the screen carries a provenance block; the renderer's
lineage modal reads it. The source_status is a quad-state (port spec §14.A):

  - real_query_real_data        · value from a real query against real firm data (telemetry)
  - real_query_synthesized_data · value from a real query against synthesized data
  - published_standard          · value cited from an external published standard / regulation
  - illustrative                · value fully synthesized

agent-trace-gov adds a 5th tier `derived`/`absent` for engine-shaped-but-not-
counted fields (port spec §14.A.2) — see derived_provenance() / absent_provenance().

These are pure functions; make_projection stays per-domain and calls them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── injectable clock ──────────────────────────────────────────────────────────
# By default every provenance stamp is wall-clock now(); a reproducible run
# (golden-file test, examiner re-derivation, the artefact seal) sets a single
# `as_of` so the whole projection stamps ONE deterministic time instead of N
# independent now() calls. Unset → now() (risk-as-code-agent unaffected).
_AS_OF: Optional[str] = None


def set_as_of(iso_timestamp: Optional[str]) -> None:
    """Pin every subsequent provenance stamp to a fixed time (or None → now())."""
    global _AS_OF
    _AS_OF = iso_timestamp


def _stamp() -> str:
    if _AS_OF is not None:
        return _AS_OF
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def illustrative_provenance(
    *,
    source_system: str = "mock_metrics",
    source_query: str = "synthesized",
    computation: str = "",
    assumptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Tri-state provenance per A2 — for values hand-set as illustrative."""
    return {
        "source_status": "illustrative",
        "source_system": source_system,
        "source_query": source_query,
        "source_timestamp": _stamp(),
        "computation": computation,
        "assumptions": list(assumptions or []),
    }


def counted_provenance(
    *,
    source_system: str,
    source_query: str,
    computation: str = "",
    assumptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """`real_query_synthesized_data` — a value COUNTED by a real query/operation
    over synthesized (but real-shaped) data. Distinct from `illustrative`
    (fully made up): a count of real traces is real counting, and mislabeling it
    `illustrative` is a lineage lie (the inverse v1.4 sin — a real number wearing
    a 'fabricated' tag). Use this for every counted/aggregated value."""
    return {
        "source_status": "real_query_synthesized_data",
        "source_system": source_system,
        "source_query": source_query,
        "source_timestamp": _stamp(),
        "computation": computation,
        "assumptions": list(assumptions or []),
    }


def provenance_for_threshold(threshold_source: str, threshold_source_url: str) -> Dict[str, Any]:
    """Provenance for threshold values — cited to a published external standard.

    `published_standard` is reserved for external-standard citations (DORA /
    CISA / NIST / GDPR); `real_query_real_data` is reserved exclusively for
    wired firm telemetry (port spec §14.A).
    """
    return {
        "source_status": "published_standard",
        "source_system": "published_standard",
        "source_query": threshold_source_url,
        "source_timestamp": "1900-01-01T00:00:00Z",  # threshold is static; date is N/A
        "computation": "Threshold derived from published industry standard or regulation.",
        "assumptions": [threshold_source] if threshold_source else [],
    }


def derived_provenance(
    *,
    computation: str,
    source_system: str = "adapter",
    assumptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """5th tier (port spec §14.A.2): value DERIVED at adapter time from real
    fields (e.g. first_detected = min(timestamp)), not directly observed. The
    computation string must state exactly how it was derived — it is honest
    about being a derivation, not a measurement."""
    return {
        "source_status": "derived",
        "source_system": source_system,
        "source_query": "derived_at_adapter",
        "source_timestamp": _stamp(),
        "computation": computation,
        "assumptions": list(assumptions or []),
    }


def absent_provenance(reason: str) -> Dict[str, Any]:
    """5th tier (port spec §14.A.2): the value is NOT instrumented / not in the
    source. The field renders as 'not instrumented', never as 0 or an estimate."""
    return {
        "source_status": "absent",
        "source_system": "none",
        "source_query": "not_instrumented",
        "source_timestamp": "1900-01-01T00:00:00Z",
        "computation": "Value not present in the source; rendered as absent, never estimated.",
        "assumptions": [reason] if reason else [],
    }


def value_with_provenance(value: Any, provenance: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap any value with provenance. Per A2, every numeric value on screen
    must carry this shape. Thin renderers click-through to the modal."""
    return {"value": value, "provenance": provenance}
