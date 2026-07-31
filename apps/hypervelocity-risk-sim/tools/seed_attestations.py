"""
Seed ILLUSTRATIVE attestation entries into the hypervelocity log.

An empty chain verifies "intact 0/0" — which an examiner reads as a misleading
assurance indicator (empty ≠ operating control). These 2 entries exercise the full
record — named human + role tier + verb + ≥12-word justification + expiry + SHA-256
hash chain — so the attestation capability is DEMONSTRATED, not merely asserted.

They are demonstrator decisions on synthetic scenarios, explicitly flagged
ILLUSTRATIVE in every justification — NOT real risk acceptances. Timestamps are
fixed so the committed log (and the projection seal over it) stays reproducible.

Run once:  PYTHONPATH=apps/hypervelocity-risk-sim python3 apps/hypervelocity-risk-sim/tools/seed_attestations.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_SPOKE = Path(__file__).resolve().parent.parent
for _p in (str(_SPOKE), str(_SPOKE.parent.parent / "packages" / "ui-system")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils.projection import _HV_LOG  # noqa: E402

_ENTRIES = [
    dict(actor_name="D. Patel", actor_handle="@dpatel", actor_role="SRE · demonstrator",
         actor_role_tier="1LoD", verb="escalate", target_type="scenario", target_id="HV-01",
         target_name="Consumer-Lag Cascade",
         justification=("ILLUSTRATIVE demonstrator attestation: escalate the consumer-lag SLO violation "
                        "to the payments on-call for signal-based triage and immediate evidence capture."),
         linked_findings=["HV-01"], expiry="2027-06-01", timestamp="2026-06-01T09:05:00Z"),
    dict(actor_name="M. Okonkwo", actor_handle="@mokonkwo", actor_role="Audit · demonstrator",
         actor_role_tier="3LoD", verb="certify", target_type="run", target_id="hv-2026-06",
         target_name="hypervelocity run 2026-06",
         justification=("ILLUSTRATIVE demonstrator attestation: certify that this seeded run reproduces "
                        "byte-for-byte and that the response-time gap is labelled operator-calibrated illustration."),
         linked_findings=["HV-01", "HV-02", "HV-03"], timestamp="2026-06-01T09:06:00Z"),
]


def main() -> int:
    log = _HV_LOG.log_file
    if log.exists():
        log.unlink()   # idempotent — rebuild the illustrative chain from scratch
    for e in _ENTRIES:
        _HV_LOG.append_entry(_HV_LOG.make_entry(**e))
    n = len(_HV_LOG.read_log())
    print(f"seeded {n} ILLUSTRATIVE attestations → {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
