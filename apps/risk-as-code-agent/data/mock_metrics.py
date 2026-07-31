"""
Synthetic telemetry generator for risk-as-code-agent.
Produces realistic Prometheus-style metrics for a fintech microservices environment.
No proprietary data — all shapes are based on public SRE/DORA literature.
"""

import os
import random
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any


# v2.0a-alpha2 added RISK_RNG_SEED but nothing ever set it — so every register
# build rolled unseeded dice while the dashboards claimed seed-reproducibility
# (round-12: three rebuilds minutes apart produced 27, 25, then 26 findings;
# caught by verify_bundle's OSCAL↔projection reconciliation). Determinism is
# now the DEFAULT; set RISK_RNG_SEED=unseeded to opt back into noise, or to
# any other value to explore alternate seeded worlds.
_RNG_SEED = os.environ.get("RISK_RNG_SEED", "2026-Q3-baseline")
_UNSEEDED = _RNG_SEED.lower() in ("", "unseeded", "none")
_RNG = random if _UNSEEDED else random.Random(_RNG_SEED)


def reset_rng() -> None:
    """Re-seed the stream. Called at the top of every assessment run so the
    determinism contract is per-RUN, not per-process-start — two consecutive
    runs in one process produce identical registers (audit-gated, C25)."""
    global _RNG
    if not _UNSEEDED:
        _RNG = random.Random(_RNG_SEED)


def _jitter(base: float, pct: float = 0.15) -> float:
    return base * (1 + _RNG.uniform(-pct, pct))


def generate_domain_snapshot(domain_id: str, scenario: str = "normal") -> Dict[str, Any]:
    """
    Generate a point-in-time telemetry snapshot for a domain.
    
    Scenarios:
      normal    — healthy baseline, all green
      degraded  — amber on 2-3 signals, one domain under stress
      incident  — red on multiple signals, active issue
      post_patch — elevated change failure rate, settling
    """

    scenarios = {
        "normal": {
            "change_failure_rate": _jitter(3.0),
            "deployment_frequency": _jitter(8.0),
            "rollback_rate": _jitter(1.5),
            "lead_time_for_changes": _jitter(45.0),
            "error_rate_p99": _jitter(0.08),
            "mttr_minutes": _jitter(18.0),
            "availability_pct": _jitter(99.97, 0.01),
            "incident_count": int(_jitter(2.0)),
            "policy_violation_count": int(_jitter(0.5)),
            "drift_detected_count": 0,
            "iac_scan_failures": int(_jitter(1.0)),
            "admission_webhook_denials": int(_jitter(3.0)),
            "critical_vuln_count": 0,
            "vuln_aging_days_p90": _jitter(4.0),
            "vuln_aging_kev_days": _jitter(3.0),
            "kev_listed_open_count": 0,
            "sast_findings_open": int(_jitter(2.0)),
            "orphaned_account_count": 0,
            "privileged_access_exceptions": int(_jitter(1.0)),
            "access_review_overdue": 0,
            "mfa_coverage_pct": 100.0,
            "dlp_alert_count": 0,
            "pii_scan_findings": 0,
            "vendor_sla_breach_count": 0,
            "tprm_overdue_reviews": int(_jitter(1.0)),
            "alert_coverage_pct": _jitter(97.0, 0.02),
            "mean_time_to_detect": _jitter(4.0),
            "emergency_change_rate": _jitter(1.5),
            "change_without_ticket_count": 0,
            "cpu_saturation_pct": _jitter(52.0),
            "memory_saturation_pct": _jitter(61.0),
            "latency_p99_ms": _jitter(145.0),
            "repeat_incident_rate": _jitter(4.0),
            "rto_breach_count": 0,
            "postmortem_overdue": 0,
            "runbook_coverage_pct": _jitter(94.0, 0.02),
            "prompt_injection_detected_count": 0,
            "tool_invocation_rejected_count": int(_jitter(2.0)),
            "mcp_tool_mutation_count": 0,
            "agent_session_anomaly_score": _jitter(0.05),
            "unauthorized_tool_access_attempts": 0,
        },
        "degraded": {
            "change_failure_rate": _jitter(18.0),
            "deployment_frequency": _jitter(12.0),
            "rollback_rate": _jitter(9.0),
            "lead_time_for_changes": _jitter(120.0),
            "error_rate_p99": _jitter(0.45),
            "mttr_minutes": _jitter(95.0),
            "availability_pct": _jitter(99.6, 0.02),
            "incident_count": int(_jitter(6.0)),
            "policy_violation_count": int(_jitter(8.0)),
            "drift_detected_count": int(_jitter(4.0)),
            "iac_scan_failures": int(_jitter(5.0)),
            "admission_webhook_denials": int(_jitter(12.0)),
            "critical_vuln_count": int(_jitter(2.0)),
            "vuln_aging_days_p90": _jitter(22.0),
            "vuln_aging_kev_days": _jitter(11.5, 0.05),
            "kev_listed_open_count": int(_jitter(2.0)),
            "sast_findings_open": int(_jitter(8.0)),
            "orphaned_account_count": int(_jitter(3.0)),
            "privileged_access_exceptions": int(_jitter(4.0)),
            "access_review_overdue": int(_jitter(2.0)),
            "mfa_coverage_pct": _jitter(97.5, 0.01),
            "dlp_alert_count": int(_jitter(1.5)),
            "pii_scan_findings": 0,
            "vendor_sla_breach_count": int(_jitter(1.5)),
            "tprm_overdue_reviews": int(_jitter(4.0)),
            "alert_coverage_pct": _jitter(87.0, 0.03),
            "mean_time_to_detect": _jitter(12.0),
            "emergency_change_rate": _jitter(7.0),
            "change_without_ticket_count": int(_jitter(1.5)),
            "cpu_saturation_pct": _jitter(78.0),
            "memory_saturation_pct": _jitter(82.0),
            "latency_p99_ms": _jitter(420.0),
            "repeat_incident_rate": _jitter(14.0),
            "rto_breach_count": int(_jitter(0.5)),
            "postmortem_overdue": int(_jitter(1.5)),
            "runbook_coverage_pct": _jitter(84.0, 0.03),
            "prompt_injection_detected_count": int(_jitter(8.0)),
            "tool_invocation_rejected_count": int(_jitter(12.0)),
            "mcp_tool_mutation_count": int(_jitter(2.0)),
            "agent_session_anomaly_score": _jitter(0.35),
            "unauthorized_tool_access_attempts": int(_jitter(4.0)),
        },
        "incident": {
            "change_failure_rate": _jitter(28.0),
            "deployment_frequency": _jitter(3.0),
            "rollback_rate": _jitter(22.0),
            "lead_time_for_changes": _jitter(240.0),
            "error_rate_p99": _jitter(3.2),
            "mttr_minutes": _jitter(185.0),
            "availability_pct": _jitter(98.8, 0.05),
            "incident_count": int(_jitter(12.0)),
            "policy_violation_count": int(_jitter(22.0)),
            "drift_detected_count": int(_jitter(11.0)),
            "iac_scan_failures": int(_jitter(14.0)),
            "admission_webhook_denials": int(_jitter(35.0)),
            "critical_vuln_count": int(_jitter(8.0)),
            "vuln_aging_days_p90": _jitter(55.0),
            "vuln_aging_kev_days": _jitter(19.0, 0.05),
            "kev_listed_open_count": int(_jitter(6.0)),
            "sast_findings_open": int(_jitter(18.0)),
            "orphaned_account_count": int(_jitter(12.0)),
            "privileged_access_exceptions": int(_jitter(9.0)),
            "access_review_overdue": int(_jitter(7.0)),
            "mfa_coverage_pct": _jitter(93.0, 0.02),
            "dlp_alert_count": int(_jitter(6.0)),
            "pii_scan_findings": int(_jitter(2.0)),
            "vendor_sla_breach_count": int(_jitter(4.0)),
            "tprm_overdue_reviews": int(_jitter(9.0)),
            "alert_coverage_pct": _jitter(72.0, 0.04),
            "mean_time_to_detect": _jitter(28.0),
            "emergency_change_rate": _jitter(18.0),
            "change_without_ticket_count": int(_jitter(6.0)),
            "cpu_saturation_pct": _jitter(92.0),
            "memory_saturation_pct": _jitter(94.0),
            "latency_p99_ms": _jitter(1200.0),
            "repeat_incident_rate": _jitter(28.0),
            "rto_breach_count": int(_jitter(3.0)),
            "postmortem_overdue": int(_jitter(5.0)),
            "runbook_coverage_pct": _jitter(68.0, 0.04),
            "prompt_injection_detected_count": int(_jitter(25.0)),
            "tool_invocation_rejected_count": int(_jitter(38.0)),
            "mcp_tool_mutation_count": int(_jitter(6.0)),
            "agent_session_anomaly_score": _jitter(0.72),
            "unauthorized_tool_access_attempts": int(_jitter(14.0)),
        },
    }

    base = scenarios.get(scenario, scenarios["normal"])
    return {
        "domain_id": domain_id,
        "snapshot_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scenario": scenario,
        "metrics": {k: round(v, 3) for k, v in base.items()},
    }


def generate_multi_domain_snapshot(scenario_map: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Generate snapshots across all domains.
    scenario_map: {domain_id: scenario} — defaults to all normal
    """
    domains = ["trading", "payments", "custody", "identity", "platform"]
    scenario_map = scenario_map or {d: "normal" for d in domains}

    snapshots = {}
    for domain in domains:
        scenario = scenario_map.get(domain, "normal")
        snapshots[domain] = generate_domain_snapshot(domain, scenario)

    return {
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "synthetic-telemetry-v1",
        "domains": snapshots,
    }


def get_demo_scenario() -> Dict[str, Any]:
    """
    Pre-baked demo scenario: trading degraded, payments in incident,
    everything else normal. Good for demos and README screenshots.
    """
    return generate_multi_domain_snapshot({
        "trading": "degraded",
        "payments": "incident",
        "custody": "normal",
        "identity": "normal",
        "platform": "degraded",
    })


if __name__ == "__main__":
    snapshot = get_demo_scenario()
    print(json.dumps(snapshot, indent=2))
