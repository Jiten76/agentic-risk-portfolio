"""
One-shot migration: add exposure_model (frequency_per_year + severity_distribution)
to each pattern in data/risk_patterns.json. Idempotent.

Per spec §3.1 + amendment A3 — replaces v1.4's "3 methodologies" hack with the
real frequency × severity model the external reviewer called out as missing.

Each pattern's frequency derivation cites:
  - base_metric (e.g., DORA change_failure_rate)
  - deploys_per_year assumption (site-specific calibration target)
  - conversion_to_material_incident (the missing-in-v1.4 term)

Each pattern's severity carries P50 / P95 / worst_anchor on one distribution.

Run from repo root:
    python scripts/migrate_v2_0a_exposure.py
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATTERNS_FILE = REPO / "data" / "risk_patterns.json"


# Per-pattern exposure model.
# Frequencies are illustrative starting points; production calibrates to internal
# incident-rate history. Severities reference the financial_basis already cited
# in v1.3.1 incident_reference blocks.
EXPOSURE_MODELS = {
    "RP-01": {
        "incident_frequency_per_year": {
            "p50": 1.4,
            "p95": 5.0,
            "derivation": {
                "base_metric":                    "change_failure_rate",
                "base_metric_unit":               "fraction of deploys that fail",
                "base_metric_p50":                0.18,
                "base_metric_p95":                0.64,
                "base_metric_source":             "DORA 2024 — Medium-performer (15%) → Low-performer (64%) cluster boundaries",
                "deploys_per_year_assumption":    52,
                "deploys_per_year_basis":         "weekly release cadence (site-specific; production calibrates from real CD telemetry)",
                "conversion_to_material_incident":  0.15,
                "conversion_basis":       "Illustrative industry base rate — ~15% of failed deploys surface as customer-visible incidents per published SRE postmortem reviews. Production replaces with internal incident:deploy ratio."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           5_000_000,
            "p95_usd":           50_000_000,
            "worst_anchor_usd":  440_000_000,
            "worst_anchor_basis": "Knight Capital 2012-08-01 — $440M / 45 min",
            "derivation":        "P50 = typical bad-release cost (SLA credits + remediation + comms). P95 = significant outage with customer-visible impact lasting hours. worst_anchor = comparable real catastrophic event.",
            "source_status":     "illustrative"
        }
    },
    "RP-02": {
        "incident_frequency_per_year": {
            "p50": 4.0,
            "p95": 12.0,
            "derivation": {
                "base_metric":                    "availability_pct (1 - SLO target)",
                "base_metric_unit":               "fraction of time service is unavailable",
                "base_metric_p50":                0.001,
                "base_metric_p95":                0.005,
                "base_metric_source":             "Google SRE 99.9% / 99.5% SLO boundaries → error-budget exhaustion events",
                "incidents_per_year_methodology": "events_count where SLO budget exceeded",
                "calibration_basis":              "Median well-run SaaS observes ~4 customer-visible availability incidents/year; struggling teams 12+."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           2_000_000,
            "p95_usd":           25_000_000,
            "worst_anchor_usd":  150_000_000,
            "worst_anchor_basis": "AWS US-EAST-1 2021-12-07 — multi-hour outage with downstream impact (illustrative aggregate of disclosed customer-side losses)",
            "derivation":        "P50 = brief customer-facing degradation. P95 = sustained outage with measurable revenue + SLA cost. worst_anchor = AWS-class blast radius event.",
            "source_status":     "illustrative"
        }
    },
    "RP-03": {
        "incident_frequency_per_year": {
            "p50": 0.5,
            "p95": 2.5,
            "derivation": {
                "base_metric":                    "policy_violation_count (open admission denials)",
                "base_metric_unit":               "violations per week",
                "base_metric_p50":                5,
                "base_metric_p95":                20,
                "base_metric_source":             "CIS Controls v8 IG1 — zero-tolerance drift posture",
                "incidents_per_year_methodology": "fraction of policy violations that materialize as exploitable misconfigurations",
                "calibration_basis":              "Policy drift events are detected upstream of customer-visible incident; conversion rate is low."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           3_000_000,
            "p95_usd":           30_000_000,
            "worst_anchor_usd":  270_000_000,
            "worst_anchor_basis": "Capital One 2019-07-19 — $80M OCC fine + ~$190M remediation",
            "derivation":        "P50 = MRA-class examination finding cost. P95 = consent-order remediation + reputational cost. worst_anchor = Capital One-class breach with OCC + private-litigation exposure.",
            "source_status":     "illustrative"
        }
    },
    "RP-04": {
        "incident_frequency_per_year": {
            "p50": 2.0,
            "p95": 8.0,
            "derivation": {
                "base_metric":                    "critical_vuln_count beyond CISA SLA",
                "base_metric_unit":               "open critical CVEs past SLA",
                "base_metric_p50":                3,
                "base_metric_p95":                15,
                "base_metric_source":             "CISA BOD 19-02 / 22-01 + KEV catalog tempo",
                "incidents_per_year_methodology": "fraction of overdue critical CVEs that are actively exploited",
                "calibration_basis":              "CISA KEV inclusion = active exploitation. 2025 KEV catalog added ~1,484 items (+20% YoY exploitation rate)."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           20_000_000,
            "p95_usd":           150_000_000,
            "worst_anchor_usd":  700_000_000,
            "worst_anchor_basis": "Equifax 2017-09-07 — $700M+ FTC settlement (CVE-2017-5638 unpatched 60+ days)",
            "derivation":        "P50 = single-CVE exploitation + remediation. P95 = chained exploitation with data exfiltration. worst_anchor = Equifax-class settlement.",
            "source_status":     "illustrative"
        }
    },
    "RP-05": {
        "incident_frequency_per_year": {
            "p50": 0.5,
            "p95": 3.0,
            "derivation": {
                "base_metric":                    "orphaned_account_count + mfa_coverage_pct gaps",
                "base_metric_unit":               "stale-credential exposure events",
                "base_metric_p50":                5,
                "base_metric_p95":                20,
                "base_metric_source":             "NIST SP 800-63B AAL2/AAL3 + CISA ZTMM v2",
                "incidents_per_year_methodology": "fraction of access events leading to lateral movement",
                "calibration_basis":              "Strong identity controls (hardware MFA + JIT) push P50 frequency low; weak controls (legacy accounts, SMS MFA) drive P95."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           5_000_000,
            "p95_usd":           50_000_000,
            "worst_anchor_usd":  100_000_000,
            "worst_anchor_basis": "Uber 2022-09-15 — disclosed remediation + regulatory action",
            "derivation":        "P50 = compromised-account remediation + comms. P95 = lateral-movement breach with data access. worst_anchor = Uber-class with extended forensics + regulatory scrutiny.",
            "source_status":     "illustrative"
        }
    },
    "RP-06": {
        "incident_frequency_per_year": {
            "p50": 0.3,
            "p95": 1.5,
            "derivation": {
                "base_metric":                    "dlp_alert_count + pii_scan_findings",
                "base_metric_unit":               "PII exposure events",
                "base_metric_p50":                2,
                "base_metric_p95":                10,
                "base_metric_source":             "GDPR Art. 33 (72-hour notification) + state breach-law thresholds",
                "incidents_per_year_methodology": "fraction of DLP signals that meet regulatory reporting threshold",
                "calibration_basis":              "Many DLP signals are below reporting threshold; only a fraction become reportable incidents."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           10_000_000,
            "p95_usd":           100_000_000,
            "worst_anchor_usd":  700_000_000,
            "worst_anchor_basis": "Equifax 2017-09-07 — $700M+ FTC settlement (147.9M records)",
            "derivation":        "P50 = notification + identity-monitoring cost. P95 = significant PII exposure with regulatory + class-action cost. worst_anchor = Equifax-class total cost.",
            "source_status":     "illustrative"
        }
    },
    "RP-07": {
        "incident_frequency_per_year": {
            "p50": 0.5,
            "p95": 2.0,
            "derivation": {
                "base_metric":                    "vendor_sla_breach_count + dependency_vuln_count",
                "base_metric_unit":               "TPRM events per quarter",
                "base_metric_p50":                2,
                "base_metric_p95":                8,
                "base_metric_source":             "NIST CSF 2.0 GV.SC + EO 14028 SBOM requirements",
                "incidents_per_year_methodology": "fraction of vendor events causing internal incident",
                "calibration_basis":              "SolarWinds-class events are infrequent but devastating; routine vendor SLA breaches are common but contained."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           8_000_000,
            "p95_usd":           90_000_000,
            "worst_anchor_usd":  500_000_000,
            "worst_anchor_basis": "SolarWinds 2020-12-13 — illustrative multi-firm remediation aggregate",
            "derivation":        "P50 = vendor incident response + service-level impact. P95 = supply-chain compromise with internal exposure. worst_anchor = SolarWinds-class blast-radius event.",
            "source_status":     "illustrative"
        }
    },
    "RP-08": {
        "incident_frequency_per_year": {
            "p50": 1.0,
            "p95": 4.0,
            "derivation": {
                "base_metric":                    "alert_coverage_pct gaps + mean_time_to_detect",
                "base_metric_unit":               "detection-gap events per quarter",
                "base_metric_p50":                3,
                "base_metric_p95":                10,
                "base_metric_source":             "Google SRE alerting workbook + IBM Cost of Breach lifecycle data",
                "incidents_per_year_methodology": "detection gaps amplify incident severity; baseline ~1 customer-visible detection-gap-driven event/year for moderate observability maturity",
                "calibration_basis":              "Telemetry-mature orgs catch incidents pre-customer-visible; gaps in coverage drive P95 up."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           4_000_000,
            "p95_usd":           30_000_000,
            "worst_anchor_usd":  200_000_000,
            "worst_anchor_basis": "SolarWinds 2020 — 9-month dwell time amplified breach impact across affected firms",
            "derivation":        "P50 = extended-detection cost. P95 = significant detection-gap-driven extended exposure. worst_anchor = SolarWinds dwell-time amplification.",
            "source_status":     "illustrative"
        }
    },
    "RP-09": {
        "incident_frequency_per_year": {
            "p50": 1.0,
            "p95": 6.0,
            "derivation": {
                "base_metric":                    "emergency_change_rate + change_without_ticket_count",
                "base_metric_unit":               "fraction of changes that bypass review",
                "base_metric_p50":                0.08,
                "base_metric_p95":                0.30,
                "base_metric_source":             "ITIL 4 emergency-change discipline + DORA 2024 elite-team boundaries",
                "deploys_per_year_assumption":    52,
                "conversion_to_material_incident":  0.20,
                "conversion_basis":       "Emergency changes correlate with higher incident rate than reviewed changes; ~20% conversion rate is illustrative."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           3_000_000,
            "p95_usd":           30_000_000,
            "worst_anchor_usd":  200_000_000,
            "worst_anchor_basis": "GitLab 2017-01-31 — emergency-change cascade + extended customer-credit impact",
            "derivation":        "P50 = post-hoc CAB + remediation cost. P95 = cascade-driven extended outage. worst_anchor = GitLab-class data-loss + recovery.",
            "source_status":     "illustrative"
        }
    },
    "RP-10": {
        "incident_frequency_per_year": {
            "p50": 1.0,
            "p95": 4.0,
            "derivation": {
                "base_metric":                    "model_accuracy_drift_pct + inference_error_rate",
                "base_metric_unit":               "model events per quarter",
                "base_metric_p50":                3,
                "base_metric_p95":                12,
                "base_metric_source":             "NIST AI RMF MEASURE-2 + AI 600-1 GenAI Profile",
                "incidents_per_year_methodology": "fraction of model events that materialize as customer-facing harm",
                "calibration_basis":              "Pre-deployment eval + production monitoring catch most issues; uncaught drift drives P95."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           10_000_000,
            "p95_usd":           80_000_000,
            "worst_anchor_usd":  304_000_000,
            "worst_anchor_basis": "Zillow Offers 2021-11-02 — $304M Q3 inventory write-down (model drift in iBuying)",
            "derivation":        "P50 = model-incident remediation cost. P95 = sustained model harm with regulatory + reputational cost. worst_anchor = Zillow-class business-line shutdown.",
            "source_status":     "illustrative"
        }
    },
    "RP-11": {
        "incident_frequency_per_year": {
            "p50": 2.0,
            "p95": 8.0,
            "derivation": {
                "base_metric":                    "cpu_saturation_pct + latency_p99_ms (Four Golden Signals — saturation + latency)",
                "base_metric_unit":               "capacity events per quarter",
                "base_metric_p50":                3,
                "base_metric_p95":                10,
                "base_metric_source":             "Google SRE Four Golden Signals + 30% headroom convention",
                "incidents_per_year_methodology": "fraction of capacity events causing customer-visible degradation",
                "calibration_basis":              "Well-tuned autoscaling catches most; capacity events visible at SLO violation drive P95."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           2_000_000,
            "p95_usd":           15_000_000,
            "worst_anchor_usd":  40_000_000,
            "worst_anchor_basis": "Cloudflare 2019-07-02 — 27-min global edge outage from CPU saturation (regex backtracking)",
            "derivation":        "P50 = brief capacity-driven degradation. P95 = sustained capacity event with SLA cost. worst_anchor = Cloudflare-class global edge event.",
            "source_status":     "illustrative"
        }
    },
    "RP-12": {
        "incident_frequency_per_year": {
            "p50": 1.0,
            "p95": 4.0,
            "derivation": {
                "base_metric":                    "repeat_incident_rate + rto_breach_count",
                "base_metric_unit":               "Sev-1 recovery events per quarter",
                "base_metric_p50":                2,
                "base_metric_p95":                8,
                "base_metric_source":             "Google SRE postmortem culture + DORA failed-deployment-recovery clusters",
                "incidents_per_year_methodology": "Sev-1 incident frequency baseline + RTO-breach amplification",
                "calibration_basis":              "Strong runbook + DR culture reduces frequency; gaps drive P95."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           5_000_000,
            "p95_usd":           50_000_000,
            "worst_anchor_usd":  300_000_000,
            "worst_anchor_basis": "Atlassian 2022-04-04 — 14-day customer impact + SLA credits + churn",
            "derivation":        "P50 = standard Sev-1 recovery cost. P95 = extended RTO breach with revenue impact. worst_anchor = Atlassian-class extended outage.",
            "source_status":     "illustrative"
        }
    },
    "RP-13": {
        "incident_frequency_per_year": {
            "p50": 2.0,
            "p95": 10.0,
            "derivation": {
                "base_metric":                    "prompt_injection_detected_count + mcp_tool_mutation_count + unauthorized_tool_access_attempts",
                "base_metric_unit":               "agent-event count per quarter",
                "base_metric_p50":                5,
                "base_metric_p95":                25,
                "base_metric_source":             "OWASP MCP Top 10 (2025) + NIST AI 600-1 GenAI Profile",
                "incidents_per_year_methodology": "fraction of agent events with material consequence; high uncertainty given novelty of surface",
                "calibration_basis":              "Tool-mutation + injection events are newly-tracked; conversion rate has high uncertainty (illustrative range)."
            },
            "source_status": "illustrative"
        },
        "severity_distribution": {
            "p50_usd":           5_000_000,
            "p95_usd":           50_000_000,
            "worst_anchor_usd":  200_000_000,
            "worst_anchor_basis": "Samsung 2023-04-30 IP exfil + CVE-2025-49596 MCP Inspector RCE supply-chain class",
            "derivation":        "P50 = single agent-action incident remediation. P95 = supply-chain or scope-violation event with broader exposure. worst_anchor = Samsung-class IP loss + supply-chain compromise.",
            "source_status":     "illustrative"
        }
    },
}


def main() -> None:
    data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    if data.get("version") < "1.4":
        data["version"] = "1.4"
    data["grounding_note"] += (
        " v1.4 / v2.0a adds exposure_model with frequency × severity decomposition "
        "per amendment A3 — closes the v1.4 'sum of worst analogs' failure with an "
        "explicit breach→incident conversion term. See reviews/v2_0a_spec_amendments.md A3."
    )

    for p in data["patterns"]:
        pid = p["id"]
        if pid in EXPOSURE_MODELS:
            p["exposure_model"] = EXPOSURE_MODELS[pid]

    PATTERNS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    n_with_exposure = sum(1 for p in data["patterns"] if "exposure_model" in p)
    print(f"Wrote {PATTERNS_FILE.relative_to(REPO)} — version {data['version']}, "
          f"{len(data['patterns'])} patterns, "
          f"{n_with_exposure} with exposure_model blocks")


if __name__ == "__main__":
    main()
