"""
Hypervelocity fintech event generator.
Simulates realistic cascade failures, Kafka lag storms, velocity surgees.
Based on public SRE/chaos engineering literature — no proprietary patterns.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Tuple, Optional


DOMAINS = ["trading", "payments", "custody", "identity", "platform"]

# Deterministic-clock anchor. None → live wall clock; run_scenario(seed=...) pins it
# to a fixed instant so a seeded run is byte-reproducible (matches the platform's
# reproducibility discipline — cf. the other spokes' injectable clock).
_BASE_TIME: Optional[datetime] = None

EVENT_TYPES = [
    "kafka_lag_storm", "deployment_cascade", "velocity_surge", "identity_outage",
    "db_connection_exhaustion", "memory_leak_cascade", "cert_expiry",
    "dependency_timeout", "traffic_spike", "config_drift_cascade",
]


def _ts(offset: float = 0) -> str:
    base = _BASE_TIME if _BASE_TIME is not None else datetime.now(timezone.utc)
    return (base + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def generate_kafka_lag_storm(duration_seconds: int = 600) -> List[Dict[str, Any]]:
    """
    Kafka consumer-lag storm — DRIVER-BASED: the lag is not drawn, it EMERGES.

    Root cause = a consumer-rate degradation (a slow partition / rebalance). The
    visible lag is the INTEGRAL of the producer−consumer rate deficit, so the
    causal arrow points the right way: drive the consumer down, and the backlog
    emerges rather than being hand-drawn. Downstream error-rate and latency are
    derived from the backlog. Continuous by construction — no exp→plateau discontinuity.

    Honest scope of "simulated": the DRIVER trajectory (the consumer-degradation
    curve) is an OPERATOR-CALIBRATED deterministic function of time plus ±1-2%
    jitter — NOT a stochastic process. So this is a reproducible seeded *replay of
    one calibrated incident shape*, not a sampled distribution (contrast rac's
    exposure, which is a genuine 20k-trial Monte-Carlo). The spoke presents no
    percentiles/means-across-trials, so it never dresses this single realization
    as sampled.

    SCALE (round-8 depth pass, v2): calibrated to a GLOBAL-fintech platform whose
    CUMULATIVE Kafka pipeline moves 10B+ events/day across apps/APIs/K8s, with
    backlog peaks in the tens of millions on the largest apps. payment-events here
    is one of the largest single slices: ~96k msg/s sustained over 768 partitions,
    3 regions, baseline in-flight backlog ~19k msgs (~0.2s of flow). The storm is
    a REBALANCE STALL — a rebalance parks ~92% of consumer capacity for ~2.5
    minutes (the classic stuck-generation shape), so the backlog integrates to
    ~13M messages before a 1.5× catch-up drains it. Magnitudes are operator-
    calibrated to global-platform scale references, NOT measured from any real
    system; shapes and physics are unchanged.
    """
    events = []
    producer_base = 96_000.0         # msgs/s — payment-events: a top slice of a 10B+/day cumulative pipeline
    lag = 19_200.0                   # baseline in-flight backlog (~0.2s of flow at base rate)
    LAG_FLOOR = 19_200.0
    # error/latency scale with backlog / LAG_SLO. Set ABOVE the emergent peak (~13M)
    # so the two derived signals VARY across the storm instead of pinning flat at the
    # min() ceilings (the "every red the same shape" tell the red-team caught).
    LAG_SLO = 15_000_000.0
    t, prev_t = 0, 0
    while t < duration_seconds:
        dt = t - prev_t
        # DRIVER: consumer rate — healthy → rebalance stall → catch-up.
        if t < 40:
            consumer_factor = 1.0
        elif t < 190:
            ramp = min(1.0, (t - 40) / 25.0)          # the rebalance parks consumers fast
            consumer_factor = 1.0 - 0.92 * ramp       # down to ~8% (a ~88k msg/s deficit)
        elif t < 560:
            consumer_factor = 1.5                      # catch-up: scaled-out group drains the backlog
        else:
            consumer_factor = 1.0
        producer_rate = producer_base + random.uniform(-950, 950)
        consumer_rate = producer_base * consumer_factor + random.uniform(-950, 950)
        # SYMPTOM: lag = ∫ (producer − consumer) dt — the backlog integrates the deficit
        lag = max(LAG_FLOOR, lag + (producer_rate - consumer_rate) * dt)
        error_rate = min(15.0, (lag / LAG_SLO) * 12 + random.uniform(0, 0.4))
        latency = min(2000, 150 + (lag / LAG_SLO) * 1800 + random.uniform(-30, 60))
        events.append({
            "timestamp":             _ts(t),
            "t_seconds":             t,
            "event_type":            "kafka_lag_storm",
            "source_topic":          "payment-events",
            "consumer_group":        "payment-processor-v2",
            "partitions":            768,
            "regions":               "us-east-1 · eu-west-1 · ap-southeast-1",
            "lag_messages":          int(lag),
            "lag_seconds_of_flow":   round(lag / producer_base, 2),
            "producer_rate_mps":     round(producer_rate, 1),
            "consumer_rate_mps":     round(consumer_rate, 1),
            "downstream_error_rate": round(error_rate, 2),
            "downstream_latency_ms": int(latency),
            "alert_triggered":       lag > 400_000,
            "slo_violation":            lag > 850_000,
            "domain_affected":       "payments",
        })
        prev_t = t
        t += random.randint(5, 15)
    return events


def generate_deployment_cascade(n_services: int = 6) -> List[Dict[str, Any]]:
    """
    Bad-deployment cascade — DRIVER-BASED. The deployed service (svc 0) carries the
    HIGHEST error (the bad release itself); downstream impact DECAYS with dependency
    distance. svc 0's error trips its breaker → a rollback is triggered. A real
    recovery tail (rollback → error decay across the drain / redeploy / cache-warm
    window) follows, and MTTR is measured from violation onset to error-normalized —
    NOT time-to-full-cascade.
    """
    events = []
    services = ["order-router", "execution-engine", "payment-gateway",
                "balance-service", "auth-service", "api-gateway"][:n_services]
    REQ_RATE = 38_000      # requests/s per service — global edge aggregate (round-8 scale calibration; operator-calibrated to public-engineering-blog ranges, not measured)
    ROLLBACK_THRESHOLD = 15.0
    t = 0

    events.append({
        "timestamp": _ts(t), "t_seconds": t, "event_type": "deployment_start",
        "service": services[0], "version": "v2.4.1", "deployment_type": "rolling",
        "change_ticket": "CHG-2025-0401", "error_rate_before": 0.1, "error_rate_after": None,
    })
    t += 30

    violation_onset = None
    base_error = 24.0      # svc-0 — the bad release; highest error at the source
    for i, svc in enumerate(services):
        # DRIVER: error is highest at the deployed service and DECAYS downstream
        error = max(0.2, base_error * (0.72 ** i) + random.uniform(-1.0, 1.0))
        circuit_open = error > ROLLBACK_THRESHOLD
        step_dt = random.randint(15, 40)
        if circuit_open and violation_onset is None:
            violation_onset = t
        events.append({
            "timestamp": _ts(t), "t_seconds": t, "event_type": "cascade_failure",
            "service": svc, "trigger": "bad_deployment" if i == 0 else "upstream_failure",
            "error_rate_pct": round(error, 1),
            "circuit_breaker": "open" if circuit_open else "closed",
            # volume basis: an OPEN breaker sheds ~all traffic for its open window
            "requests_dropped": int(REQ_RATE * step_dt) if circuit_open else 0,
            "rollback_triggered": (i == 0 and circuit_open),   # svc-0 error ~24 > 15 → fires
            "change_failure": True,
            "domain": DOMAINS[i % len(DOMAINS)],
        })
        t += step_dt

    # rollback decision + redeploy the prior artifact
    t += random.randint(30, 60)
    events.append({
        "timestamp": _ts(t), "t_seconds": t, "event_type": "rollback_start",
        "service": services[0], "rollback_to": "v2.4.0", "trigger": "error_rate > threshold",
    })
    # RECOVERY tail: error decays over the drain / redeploy / circuit-reset /
    # cache-warm window. Each step is 3–8 MINUTES (t is in seconds) — a 6-service
    # rollback normalizes in ~15–35 min, not the ~4 min a seconds-scale step gave.
    err = base_error
    for _ in range(4):
        t += random.randint(180, 480)       # 3–8 min per recovery step
        err = max(0.12, err * 0.4)
        events.append({
            "timestamp": _ts(t), "t_seconds": t, "event_type": "recovery",
            "service": services[0], "error_rate_pct": round(err, 2),
            "circuit_breaker": "half_open" if err > 1 else "closed",
        })
    violation_onset = violation_onset if violation_onset is not None else 30
    events.append({
        "timestamp": _ts(t), "t_seconds": t, "event_type": "rollback_complete",
        "service": services[0], "rollback_to": "v2.4.0",
        "mttr_minutes": round((t - violation_onset) / 60.0, 1),   # violation → normalized
        "error_rate_after": 0.12, "post_incident": "required",
    })
    return events


def generate_velocity_surge(duration_seconds: int = 180) -> List[Dict[str, Any]]:
    """
    Simulates a transaction velocity surge:
    - Transaction rate spikes 10x normal
    - Fraud detection triggers, blocks legitimate traffic
    - Elevated-velocity signal is routed to an AML review queue for human
      disposition (a fraud-control signal, NOT a BSA/AML determination)
    """
    events = []
    t = 0
    normal_tps = 9_200     # global payments baseline tps (round-8 scale calibration — operator-calibrated, not measured)
    while t < duration_seconds:
        if t < 30:
            tps = normal_tps + random.uniform(-400, 400)
        elif t < 90:
            # Spike
            tps = normal_tps * (1 + (t - 30) / 10) + random.uniform(-1000, 2000)
        elif t < 120:
            tps = normal_tps * 8 + random.uniform(-2000, 2000)
        else:
            # fraud-block + shed drains the surge back UNDER the surge line (3x) within
            # the window — so the recovery phase is real, not just a past-peak label.
            tps = max(normal_tps, tps * 0.82)

        surge = tps > normal_tps * 3
        aml_flag = tps > normal_tps * 5
        events.append({
            "timestamp":          _ts(t),
            "t_seconds":          t,
            "event_type":         "velocity_surge" if surge else "normal_traffic",
            "transactions_per_sec": int(tps),
            "normal_baseline_tps":  normal_tps,
            "surge_ratio":         round(tps / normal_tps, 2),
            "fraud_score_avg":      round(min(0.98, 0.12 + (tps / normal_tps) * 0.08), 3),
            "transactions_blocked": int(tps * 0.15) if surge else 0,
            "aml_review_routed":    aml_flag,
            "compliance_escalation": aml_flag,
            "domain":               "payments",
        })
        t += random.randint(5, 20)
    return events


def generate_identity_outage(duration_seconds: int = 600) -> List[Dict[str, Any]]:
    """
    E2 — the identity-plane lockout (the scenario the other three cannot tell):
    - The customer auth/session plane degrades then fails: customers locked out
      of accounts and funds in real time (Auth0 2021-04-20 class; the 2021-01
      brokerage login failures under volume).
    - The RECURSION: workforce SSO shares the failed plane — responders are
      locked out of their own tooling WITH the customers (Meta 2021-10-04
      class). Detection is near-instant; ACCESS is the bottleneck.
    - Break-glass fallback restores tool access, then the plane recovers into
      a re-auth surge (every locked-out session returns at once).
    """
    events = []
    t = 0
    base_attempts = 5_200      # customer auth attempts/s (platform archetype)
    locked_out = 0
    while t < duration_seconds:
        if t < 60:
            success = 99.4 + random.uniform(0, 0.4)
            attempts = base_attempts + random.uniform(-250, 250)
            tools = True
        elif t < 140:
            # degradation — token issuance failing under a bad dependency
            k = (t - 60) / 80.0
            success = 99.0 - k * 55 + random.uniform(-3, 3)
            attempts = base_attempts * (1 + k * 0.6)          # retry pressure
            tools = t < 120                                    # SSO follows the plane down
        elif t < 320:
            # full outage — customers AND responders locked out
            success = max(2.0, 12.0 - (t - 140) / 30 + random.uniform(-2, 2))
            attempts = base_attempts * 1.9 + random.uniform(-400, 400)
            tools = False
        elif t < 430:
            # break-glass path restores tool access first; plane limps back
            k = (t - 320) / 110.0
            success = 15 + k * 75 + random.uniform(-4, 4)
            attempts = base_attempts * (1.9 - k * 0.5)
            tools = t >= 390
        else:
            # recovery — re-auth surge as locked-out sessions return
            success = 99.0 + random.uniform(0, 0.6)
            attempts = base_attempts * 1.5 * max(1.0, (600 - t) / 170)
            tools = True
        fail_pct = max(0.0, 100.0 - success)
        if success < 90:
            locked_out += int(attempts * (fail_pct / 100.0) * 4)   # ~4s of failed attempts per tick
        events.append({
            "timestamp":                _ts(t),
            "t_seconds":                t,
            "event_type":               "identity_outage" if success < 90 else "normal_auth",
            "auth_success_rate":        round(success, 1),
            "auth_failure_rate_pct":    round(fail_pct, 1),
            "auth_attempts_per_sec":    int(attempts),
            "customers_locked_out":     locked_out,
            "responder_tools_reachable": tools,
            "responder_lockout":        0 if tools else 1,
            "support_queue_depth":      int(locked_out * 0.012),
            "session_reauth_surge":     t >= 430,
            "domain":                   "identity",
        })
        t += random.randint(5, 20)
    return events


def run_scenario(scenario: str, seed: Optional[int] = None) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    Run a named scenario. Returns (events, summary).

    seed: when provided, the run is byte-reproducible — the RNG is seeded and the
    timestamp clock is anchored to a fixed instant. Default None keeps the live,
    stochastic behaviour (each run is a fresh instance of the failure shape).
    """
    global _BASE_TIME
    if seed is not None:
        random.seed(seed)
        _BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
    else:
        _BASE_TIME = None

    if scenario == "kafka_lag_storm":
        events = generate_kafka_lag_storm(600)
        peak_lag = max(e.get("lag_messages", 0) for e in events)
        slo_violations = sum(1 for e in events if e.get("slo_violation"))
        summary = {
            "scenario":      "Kafka Lag Storm",
            "duration_s":    events[-1]["t_seconds"] if events else 0,
            "peak_lag_msgs": peak_lag,
            "slo_violations":  slo_violations,
            "peak_error_rate": max(e.get("downstream_error_rate", 0) for e in events),
            "peak_latency_ms": max(e.get("downstream_latency_ms", 0) for e in events),
            "risk_patterns":  ["RP-02 Availability", "RP-11 Capacity", "RP-08 Observability"],
        }

    elif scenario == "deployment_cascade":
        events = generate_deployment_cascade(6)
        mttr = next((e.get("mttr_minutes", 0) for e in events if e.get("event_type") == "rollback_complete"), 0)
        summary = {
            "scenario":        "Deployment Cascade Failure",
            "services_hit":    6,
            "mttr_minutes":    mttr,
            "change_failure":  True,
            "rollback":        True,
            "risk_patterns":   ["RP-01 Deployment", "RP-02 Availability", "RP-09 Change Management"],
        }

    elif scenario == "velocity_surge":
        events = generate_velocity_surge(240)   # long enough for the surge to drain under breach
        peak_ratio = max(e.get("surge_ratio", 1) for e in events)
        blocked = sum(e.get("transactions_blocked", 0) for e in events)
        summary = {
            "scenario":           "Transaction-Velocity Surge / Fraud-Control Response",
            "duration_s":         events[-1]["t_seconds"] if events else 0,
            "peak_surge_ratio":  peak_ratio,
            "total_blocked_txns": blocked,
            "aml_review_routed":  True,
            "risk_patterns":      ["RP-02 Availability", "RP-06 Data & Privacy", "RP-03 Policy"],
        }

    elif scenario == "identity_outage":
        events = generate_identity_outage(600)
        min_success = min(e.get("auth_success_rate", 100) for e in events)
        peak_locked = max(e.get("customers_locked_out", 0) for e in events)
        dark = [e["t_seconds"] for e in events if not e.get("responder_tools_reachable", True)]
        summary = {
            "scenario":              "Identity-Plane Lockout",
            "duration_s":            events[-1]["t_seconds"] if events else 0,
            "min_auth_success_pct":  min_success,
            "peak_locked_out":       peak_locked,
            "responder_dark_min":    round((max(dark) - min(dark)) / 60) if dark else 0,
            "support_queue_peak":    max(e.get("support_queue_depth", 0) for e in events),
            "risk_patterns":         ["RP-05 Access & Identity", "RP-02 Availability", "RP-12 Incident & Recovery"],
        }

    else:
        events = []
        summary = {"scenario": scenario, "error": "unknown scenario"}

    return events, summary


def compare_response_strategies(events: List[Dict], scenario: str) -> Dict[str, Any]:
    """
    Compare traditional checklist vs Risk-as-Code response to an event stream.
    Returns side-by-side comparison metrics.
    """
    event_count = len(events)

    # Response-regime constants are operator_calibrated ILLUSTRATION (labelled per value
    # in the projection). They model a COMPETENT-manual baseline vs instrumented+automated
    # — a believable few-fold gap, NOT a strawman: manual assembles audit-ready evidence in
    # 1-2h (not 8), misses ~10% during a storm (not 40%), and the automated regime is
    # imperfect too (small non-zero false-positives / missed).
    if scenario == "kafka_lag_storm":
        return {
            "traditional": {
                "name":               "Traditional — Manual Checklist",
                "detection_time_min": 12,
                "escalation_time_min": 22,
                "evidence_ready_min": 90,
                "false_positives":    3,
                "missed_events":      round(event_count * 0.10),
                "human_effort_hours": 4.0,
                "audit_trail":        "Manual notes + log pulls",
                "slo_response":       "After SLO violation, manual confirm",
            },
            "risk_as_code": {
                "name":               "Risk-as-Code — Automated",
                "detection_time_min": 2,
                "escalation_time_min": 5,
                "evidence_ready_min": 10,
                "false_positives":    1,
                "missed_events":      round(event_count * 0.015),
                "human_effort_hours": 0.75,
                "audit_trail":        "Full telemetry trace, timestamped",
                "slo_response":       "Automated alert at threshold crossing",
            },
        }
    elif scenario == "deployment_cascade":
        return {
            "traditional": {
                "name":               "Traditional — Manual Checklist",
                "detection_time_min": 10,
                "escalation_time_min": 20,
                "evidence_ready_min": 100,
                "false_positives":    2,
                "missed_events":      round(event_count * 0.10),
                "human_effort_hours": 4.5,
                "audit_trail":        "Post-incident ticket + manual timeline",
                "rollback_trigger":   "Manual decision at T+18min",
            },
            "risk_as_code": {
                "name":               "Risk-as-Code — Automated",
                "detection_time_min": 2,
                "escalation_time_min": 4,
                "evidence_ready_min": 12,
                "false_positives":    1,
                "missed_events":      round(event_count * 0.015),
                "human_effort_hours": 1.0,
                "audit_trail":        "Change failure auto-logged, RP-01 triggered",
                "rollback_trigger":   "Automated at error_rate > threshold",
            },
        }
    elif scenario == "velocity_surge":
        # Full symmetric metric set — the fraud/AML-routing scenario is the most
        # compliance-sensitive, so escalation (the review-queue clock) matters most.
        return {
            "traditional": {
                "name":               "Traditional — Manual Checklist",
                "detection_time_min": 12,
                "escalation_time_min": 20,
                "evidence_ready_min": 85,
                "false_positives":    4,
                "missed_events":      round(event_count * 0.10),
                "human_effort_hours": 4.0,
                "audit_trail":        "Manual notes + review-queue entry",
                "aml_routing":        "Manual review-queue entry, after the fact",
            },
            "risk_as_code": {
                "name":               "Risk-as-Code — Automated",
                "detection_time_min": 2,
                "escalation_time_min": 5,
                "evidence_ready_min": 10,
                "false_positives":    1,
                "missed_events":      round(event_count * 0.015),
                "human_effort_hours": 0.7,
                "audit_trail":        "Full telemetry trace, timestamped",
                "aml_routing":        "Auto-routed to AML review queue with evidence pack",
            },
        }
    elif scenario == "identity_outage":
        # E2 — the INVERTED gap: detection is near-parity (an auth-failure spike
        # is unmissable in both regimes). The differentiator is ACCESS — the
        # traditional regime's responders are locked out with the customers
        # (workforce SSO shares the failed plane, Meta 2021-10-04 class); the
        # instrumented regime has break-glass identities pre-provisioned,
        # exercised quarterly, and logged.
        return {
            "traditional": {
                "name":               "Traditional — Manual Checklist",
                "detection_time_min": 3,
                "escalation_time_min": 25,
                "evidence_ready_min": 120,
                "tool_access_recovery_min": 42,
                "false_positives":    2,
                "missed_events":      round(event_count * 0.08),
                "human_effort_hours": 5.0,
                "audit_trail":        "Reconstructed after access restored; the lockout window is a gap in its own evidence",
                "access_note":        "Responders locked out with the customers — war room assembles on personal phones",
            },
            "risk_as_code": {
                "name":               "Risk-as-Code — Automated",
                "detection_time_min": 2,
                "escalation_time_min": 6,
                "evidence_ready_min": 12,
                "tool_access_recovery_min": 6,
                "false_positives":    1,
                "missed_events":      round(event_count * 0.015),
                "human_effort_hours": 1.2,
                "audit_trail":        "Out-of-band telemetry keeps recording through the lockout; break-glass use itself is logged",
                "access_note":        "Break-glass identities pre-provisioned + exercised quarterly; out-of-band evidence path",
            },
        }
    else:
        return {
            "traditional": {"name": "Traditional", "detection_time_min": 20,
                            "evidence_ready_min": 420, "human_effort_hours": 7.0},
            "risk_as_code": {"name": "Risk-as-Code", "detection_time_min": 2,
                             "evidence_ready_min": 5, "human_effort_hours": 0.5},
        }


if __name__ == "__main__":
    for scenario in ["kafka_lag_storm", "deployment_cascade", "velocity_surge", "identity_outage"]:
        events, summary = run_scenario(scenario)
        print(f"\n{summary['scenario']}: {len(events)} events")
        print(f"  Risk patterns: {summary.get('risk_patterns', [])}")
