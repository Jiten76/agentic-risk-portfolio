"""journey signal generator — Stage 1a of reviews/journey_spine_port_spec.md.

Deterministic seeded telemetry for J-SIM-001 · Instant Transfer. Structure
from the operator's production 2LoD practice; all names, values, and dates
SEEDED — nothing here is measured, and every surface that shows these numbers
says so via the chip grammar (SEEDED · {n}pts · {cadence} · gen:journey_signal_gen@seed42).

Two resolutions per signal:
  - base series: 90d at 1h cadence (2,160 pts) — the observation window
  - incident overlay: SIM-0531 window at 1m cadence (150 pts) — the walk

THE incident (the journey's narrative anchor): SIM-0531, 2026-05-31
09:40–11:40 ET — event-bus consumer lag builds, ledger-writer p99 degrades,
retry amplification (the RP-14→RP-11 physics the engine already prices),
self-recovery with zero customer-visible failures: the self-concealing loop.
Peak values are never typed anywhere — projection and gates RECOMPUTE them
from this generator (audit C36.3)."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

SEED = 42
GEN_ID = "journey_signal_gen@seed42"
WINDOW = {"start": "2026-03-15", "end": "2026-06-13", "days": 90}
BASE_CADENCE = "1h"
BASE_PTS = 2160  # 90d × 24h — cardinality stated, reference-artifact style
INCIDENT = {
    "id": "SIM-0531",
    "date": "2026-05-31",
    "start_et": "09:40",
    "end_et": "11:40",
    "overlay_cadence": "1m",
    "overlay_pts": 150,  # 09:30–12:00 ET at 1m
}
# hour index of incident start within the 90d window (2026-05-31 = day 77)
_INCIDENT_HOUR = 77 * 24 + 13  # ~09:40 ET expressed in window hours (UTC-ish, seeded world)

# signal id → (baseline, daily_amplitude, noise_sd, incident_mult, unit)
# incident_mult > 1 ⇒ the signal participates in SIM-0531.
_SPECS: Dict[str, tuple] = {
    "sim.rps_edge":                (420.0, 120.0, 18.0, 1.0,  "rps"),
    "sim.p99_edge":                (95.0,  12.0,  6.0,  1.6,  "ms"),
    "sim.p99_transfer_api":        (210.0, 25.0,  12.0, 2.2,  "ms"),
    "sim.error_rate_transfer_api": (0.20,  0.05,  0.04, 3.0,  "%"),
    "sim.p99_risk_score":          (140.0, 15.0,  8.0,  1.3,  "ms"),
    "sim.decision_conf_p5":        (0.83,  0.02,  0.015, 1.0, "score"),
    "sim.auth_failure_rate":       (0.9,   0.2,   0.12, 1.0,  "%"),
    "sim.p99_identity":            (120.0, 14.0,  7.0,  1.2,  "ms"),
    "sim.p99_ledger_write":        (180.0, 20.0,  10.0, 5.2,  "ms"),
    "sim.write_retry_rate":        (0.6,   0.15,  0.1,  6.0,  "%"),
    "sim.consumer_lag_p95":        (820.0, 180.0, 90.0, 11.0, "msgs"),
    "sim.publish_p99":             (24.0,  4.0,   2.0,  2.8,  "ms"),
    "sim.p99_settle":              (310.0, 35.0,  16.0, 1.8,  "ms"),
    "sim.settle_queue_depth":      (140.0, 40.0,  22.0, 3.4,  "items"),
    "sim.rail_ack_latency":        (940.0, 110.0, 55.0, 1.0,  "ms"),
    "sim.notify_send_rate":        (380.0, 95.0,  30.0, 1.0,  "per_min"),
    "sim.recon_break_count":       (2.0,   1.0,   0.8,  1.0,  "count"),
}


def _series(sig: str) -> List[float]:
    base, amp, sd, mult, _unit = _SPECS[sig]
    rng = random.Random(f"{SEED}:{sig}")
    out = []
    for h in range(BASE_PTS):
        diurnal = amp * max(0.0, math.sin((h % 24) / 24.0 * math.pi))
        v = base + diurnal + rng.gauss(0.0, sd)
        # SIM-0531: a 2h ramp-and-recover envelope on participating signals
        if mult > 1.0 and 0 <= h - _INCIDENT_HOUR < 3:
            phase = (h - _INCIDENT_HOUR)  # 0,1,2 → build, peak, drain
            envelope = (0.55, 1.0, 0.35)[phase]
            v = base + (base * (mult - 1.0)) * envelope + rng.gauss(0.0, sd)
        out.append(max(0.0, v))
    return out


def _overlay(sig: str) -> List[float]:
    """Minute-resolution incident window (09:30–12:00 ET) — the walkable shape."""
    base, _amp, sd, mult, _unit = _SPECS[sig]
    rng = random.Random(f"{SEED}:{sig}:overlay")
    out = []
    for m in range(INCIDENT["overlay_pts"]):
        t = m / INCIDENT["overlay_pts"]
        if mult > 1.0:
            # sigmoid build to peak at ~t=0.45, exponential drain after
            build = 1.0 / (1.0 + math.exp(-(t - 0.28) * 22))
            drain = math.exp(-max(0.0, t - 0.55) * 6.5)
            envelope = build * drain
            v = base + (base * (mult - 1.0)) * envelope + rng.gauss(0.0, sd * 0.6)
        else:
            v = base + rng.gauss(0.0, sd * 0.6)
        out.append(max(0.0, v))
    return out


def signal_stats() -> Dict[str, Dict[str, Any]]:
    """Per-signal stats + chip metadata — everything a surface may quote.
    Peaks are COMPUTED here; typing one anywhere else is a C36.3 failure."""
    out: Dict[str, Dict[str, Any]] = {}
    for sig, (base, _a, _sd, mult, unit) in _SPECS.items():
        s = _series(sig)
        srt = sorted(s)
        ov = _overlay(sig)
        out[sig] = {
            "unit": unit,
            "baseline": round(base, 1),
            "mean": round(sum(s) / len(s), 1),
            "p95": round(srt[int(len(srt) * 0.95)], 1),
            "max": round(max(s), 1),
            "incident_participant": mult > 1.0,
            "incident_peak": round(max(ov), 1) if mult > 1.0 else None,
            "incident_peak_over_baseline": round(max(ov) / base, 1) if mult > 1.0 else None,
            "chip": {"realness": "SEEDED", "pts": BASE_PTS, "cadence": BASE_CADENCE, "gen": GEN_ID},
            "overlay_chip": {"realness": "SEEDED", "pts": INCIDENT["overlay_pts"],
                             "cadence": INCIDENT["overlay_cadence"], "gen": GEN_ID},
        }
    return out


def aggregator_payload() -> Dict[str, Any]:
    """Stage 4 — the journey aggregator contract: the MINIMAL journey state the
    consumer needs, emitted by the generator side. The reference artifact
    asserts 'verbatim · unmodified'; here the claim is GATED — C38.2 recomputes
    this payload's canonical hash and fails the build if the consumer embedded
    anything else."""
    st = signal_stats()
    return {
        "journey": "J-SIM-001",
        "window": WINDOW,
        "incident": {
            "id": INCIDENT["id"], "date": INCIDENT["date"],
            "window_et": f"{INCIDENT['start_et']}–{INCIDENT['end_et']}",
            "peaks": {sig: s["incident_peak"] for sig, s in sorted(st.items())
                      if s["incident_participant"]},
        },
        "generated_by": GEN_ID,
    }


def base_series(sig: str, downsample: int = 8) -> List[float]:
    """The 90d hourly series, MAX-POOLED per bucket for the trend chart —
    a strided downsample dropped the incident hours entirely (the chart's one
    job is the spike; r39 operator catch). Max-pooling keeps every peak."""
    s = _series(sig)
    return [round(max(s[i:i + downsample]), 1) for i in range(0, len(s), downsample)]


def overlay_series(sig: str, downsample: int = 1) -> List[float]:
    """The incident-window series for rendering (stage 1b sparklines)."""
    s = _overlay(sig)
    return [round(v, 1) for v in s[::downsample]]
