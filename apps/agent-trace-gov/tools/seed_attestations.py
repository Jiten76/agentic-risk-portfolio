"""
Seed illustrative demonstrator attestations into data/attestation_log.jsonl.

Idempotent — only seeds when the log is empty. The attestations are ILLUSTRATIVE
governance decisions (disclosed as such), but the SHA-256 hash chain over them is
REAL and verified live in-browser. Mirrors risk-as-code-agent's seeded action_log
so the ATTEST surface ships with a populated, genesis→head-verifiable chain rather
than an empty log that renders a green "intact" badge over nothing (the examiner's
"assurance over nothing" finding). Timestamps are fixed → reproducible projection.

Run: .venv/bin/python3 tools/seed_attestations.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.projection import _ATG_LOG, make_projection  # noqa: E402
from graph.governance_graph import run_governance_analysis_full  # noqa: E402


def main() -> int:
    existing = _ATG_LOG.read_log()
    if existing:
        print(f"attestation_log already has {len(existing)} entries — not re-seeding.")
        return 0

    # real, deterministic firing findings to link the attestations to
    p = make_projection(run_governance_analysis_full(16, seed=42),
                        as_of="2026-06-01T09:00:00Z", run_seed=42)
    by_re = {}
    for d in p["domains"].values():
        for f in d["findings"]:
            by_re.setdefault(f["risk_event_id"], f)

    def pick(re_id):
        f = by_re.get(re_id) or next(iter(by_re.values()))
        return f["finding_id"], f["risk_event_id"] + " · " + f["name"]

    ext_id, ext_name = pick("RE-03")
    scope_id, scope_name = pick("RE-04")

    seeds = [
        dict(actor_name="D. Patel", actor_handle="@dpatel",
             actor_role="Director, AI Platform (1LoD)", actor_role_tier="1LoD",
             verb="escalate", target_type="finding", target_id=ext_id, target_name=ext_name,
             justification=("Escalating the unauthorized external data flow to 2LoD: the KYC agent egressed "
                            "PII to a third-party endpoint with no lawful-basis record in the trace."),
             linked_findings=[ext_id], review_cadence_days=7, timestamp="2026-06-22T14:05:00Z"),
        dict(actor_name="S. Khoury", actor_handle="@skhoury",
             actor_role="Director, Technology Risk (2LoD)", actor_role_tier="2LoD",
             verb="gate", target_type="finding", target_id=scope_id, target_name=scope_name,
             justification=("Production gate on the scope-exceeded agent pending a human-oversight control and "
                            "updated logging; lift only after 2LoD re-review of the delegated path."),
             linked_findings=[scope_id], expiry="2026-07-20", review_cadence_days=14,
             timestamp="2026-06-23T09:40:00Z"),
        dict(actor_name="M. Okonkwo", actor_handle="@mokonkwo",
             actor_role="VP Engineering / Audit liaison (3LoD)", actor_role_tier="3LoD",
             verb="certify", target_type="workflow", target_id="governance-pass",
             target_name="Governance pass · " + p["meta"]["period"],
             justification=("Certifying that this governance pass reviewed every traced workflow, that fired "
                            "framework triggers were routed to Legal for materiality determination, and the "
                            "attestation chain verifies genesis-to-head."),
             linked_findings=[ext_id, scope_id], review_cadence_days=30, timestamp="2026-06-24T16:20:00Z"),
    ]

    for s in seeds:
        entry = _ATG_LOG.make_entry(**s)
        _ATG_LOG.append_entry(entry)

    written = _ATG_LOG.read_log()
    from portfolio_core.action_log import verify_chain
    res = verify_chain(written)
    print(f"seeded {len(seeds)} illustrative attestations → {_ATG_LOG._require_log_file()}")
    print(f"chain valid: {res['valid']} ({len(written)} entries, genesis→head)")
    return 0 if res["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
