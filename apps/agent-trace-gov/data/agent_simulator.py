"""
Synthetic multi-agent workflow simulator.
Generates realistic agent action traces for a fintech agentic system.
Covers: data flows, PII handling, consent checks, external calls, delegations.
No proprietary data — all patterns based on public agentic system literature.
"""

import hashlib
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

# When a run is seeded, traces stamp from a fixed base clock instead of now(), so
# the projection is reproducible (examiner re-derivation, golden-file, the seal).
_BASE_TIME: Optional[datetime] = None


# ── PII patterns for detection simulation ────────────────────────────────────

PII_SAMPLES = {
    "email":  ["user@example.com", "client@finance.io", "test@demo.net"],
    "phone":  ["555-123-4567", "+1-800-555-0199"],
    "ssn":    ["***-**-1234"],          # already masked in output
    "account": ["ACCT-****-7890"],
    "name":   ["John Smith", "Jane Doe", "Alex Johnson"],
}

CLEAN_PAYLOADS = [
    "{'action': 'get_balance', 'account_id': 'ACC-789'}",
    "{'query': 'risk_score', 'entity': 'TXN-001-2025'}",
    "{'report_type': 'quarterly', 'domain': 'payments'}",
    "{'signal': 'latency_p99', 'service': 'order-router'}",
    "{'decision': 'approve', 'confidence': 0.94}",
    "{'tool': 'risk_calculator', 'input': {'amount': 5000, 'currency': 'USD'}}",
]

PII_PAYLOADS = [
    "{'user': 'John Smith', 'email': 'john.smith@example.com', 'action': 'kyc_check'}",
    "{'customer': 'Jane Doe', 'ssn_last4': '1234', 'query': 'credit_check'}",
    "{'contact': '555-123-4567', 'account': 'ACCT-****-7890', 'status': 'active'}",
]

AGENTS = [
    {"id": "agent-orchestrator",  "name": "Orchestrator Agent",    "type": "orchestrator"},
    {"id": "agent-risk-analyzer", "name": "Risk Analysis Agent",   "type": "specialist"},
    {"id": "agent-data-fetcher",  "name": "Data Fetch Agent",      "type": "tool"},
    {"id": "agent-kyc-validator", "name": "KYC Validation Agent",  "type": "specialist"},
    {"id": "agent-report-writer", "name": "Report Writer Agent",   "type": "specialist"},
    {"id": "agent-decision",      "name": "Decision Agent",        "type": "decision"},
    {"id": "agent-notifier",      "name": "Notification Agent",    "type": "tool"},
]

# Authorized action-type scope per agent — the authorization context a real system
# attaches to a span. The classifier DERIVES RE-04 (scope exceeded) by comparing a
# trace's action_type against this; nothing is pre-labelled. A report-writer that
# makes an external_api_call or tool_execution is out of scope; a kyc-validator
# calling a KYC provider is IN scope (its data-governance issues are RE-01/RE-03).
AGENT_SCOPE = {
    "agent-orchestrator":  ["agent_delegation", "human_handoff"],
    "agent-risk-analyzer": ["data_read", "model_inference", "agent_delegation", "human_handoff"],
    "agent-data-fetcher":  ["data_read", "agent_delegation"],
    "agent-kyc-validator": ["data_read", "model_inference", "data_write", "external_api_call", "agent_delegation"],
    "agent-report-writer": ["data_read", "data_write", "model_inference", "agent_delegation", "human_handoff"],
    "agent-decision":      ["data_read", "model_inference", "decision", "agent_delegation", "human_handoff"],
    "agent-notifier":      ["notify", "human_handoff"],
}

TOOLS = [
    "risk_calculator", "balance_lookup", "kyc_api",
    "credit_bureau_api", "internal_ledger", "report_generator",
    "alert_dispatcher", "audit_logger",
    # r56: an effectful tool — its execution MOVES FUNDS. No agent's scope
    # includes tool_execution against it; reaching it is the franchise-class
    # unauthorized-action shape the consequence-driven severity model tops.
    "payment_disbursement",
]

EXTERNAL_ENDPOINTS = [
    "kyc-provider.external.io",
    "credit-bureau.external.io",
    "fraud-detection.external.io",
    "regulatory-reporting.gov.io",
    "customer-comms-gateway.external.io",
]


def _ts(offset_seconds: int = 0) -> str:
    base = _BASE_TIME if _BASE_TIME is not None else datetime.now(timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")


def _contains_pii(payload: str) -> Dict[str, Any]:
    """Simulate PII detection scan."""
    pii_found = {}
    for pii_type, samples in PII_SAMPLES.items():
        for sample in samples:
            if sample.lower() in payload.lower():
                pii_found[pii_type] = True
    return pii_found


def generate_agent_trace(
    workflow_id: str,
    scenario: str = "clean",
) -> List[Dict[str, Any]]:
    """
    Generate a sequence of agent action trace records for a workflow.

    Scenarios:
      clean             — normal workflow, no risk events
      pii_leak          — agent passes PII to external endpoint
      scope_exceed      — agent calls tool outside its authorized scope
      consent_gap       — data processed without consent record
      loop              — agents delegating to each other in a loop
      low_conf          — decision agent firing below confidence threshold
      payment_tool_grab — notifier executes the funds-movement tool, out of scope (r56)
      retail_comms      — customer comms sent externally, out of scope, no human gate (r56)
      ledger_amend      — record-store write with broken lineage (r56)
    """
    actions = []
    t = 0

    # Each step is (agent, action_type, target, payload, signals). `signals` carries
    # only RAW FACTS about what happened (consent flag, decision confidence) — NEVER
    # a risk-event label. The risk_classifier node DERIVES RE-xx from these signals +
    # action_type + target + pii-scan + agent scope. This is a trace stream, not an
    # answer key.
    if scenario == "clean":
        steps = [
            ("agent-orchestrator",  "agent_delegation", "agent-risk-analyzer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-risk-analyzer", "data_read",        "internal_ledger",     random.choice(CLEAN_PAYLOADS), None),
            ("agent-risk-analyzer", "model_inference",  "risk_model_v2",       random.choice(CLEAN_PAYLOADS), None),
            ("agent-risk-analyzer", "agent_delegation", "agent-report-writer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "data_write",       "report_store",        random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "human_handoff",    "risk_reviewer",       random.choice(CLEAN_PAYLOADS), None),
        ]

    elif scenario == "pii_leak":  # PII egressed to an external endpoint → RE-01 + RE-03
        steps = [
            ("agent-orchestrator",  "agent_delegation",  "agent-kyc-validator", random.choice(CLEAN_PAYLOADS), None),
            ("agent-kyc-validator", "data_read",         "customer_db",         random.choice(PII_PAYLOADS),   None),
            ("agent-kyc-validator", "external_api_call", "kyc-provider.external.io", random.choice(PII_PAYLOADS), None),
            ("agent-kyc-validator", "data_write",        "kyc_results",         random.choice(PII_PAYLOADS),   None),
            ("agent-orchestrator",  "human_handoff",     "compliance_team",     random.choice(CLEAN_PAYLOADS), None),
        ]

    elif scenario == "scope_exceed":  # report-writer does tool_execution + external call → out of scope
        steps = [
            ("agent-orchestrator",   "agent_delegation", "agent-report-writer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer",  "data_read",        "internal_ledger",     random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer",  "tool_execution",   "credit_bureau_api",   random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer",  "external_api_call","credit-bureau.external.io", random.choice(CLEAN_PAYLOADS), None),
            ("agent-orchestrator",   "human_handoff",    "security_team",       random.choice(CLEAN_PAYLOADS), None),
        ]

    elif scenario == "consent_gap":  # PII written to a consent-requiring sink with no consent record
        steps = [
            ("agent-orchestrator",  "agent_delegation", "agent-kyc-validator", random.choice(CLEAN_PAYLOADS), None),
            ("agent-kyc-validator", "data_read",        "customer_db",         random.choice(PII_PAYLOADS),   None),
            ("agent-kyc-validator", "model_inference",  "kyc_model",           random.choice(PII_PAYLOADS),   None),
            ("agent-kyc-validator", "data_write",       "kyc_results",         random.choice(PII_PAYLOADS),   {"consent_verified": False}),
        ]

    elif scenario == "loop":  # a delegation edge repeats within the workflow → RE-08
        steps = [
            ("agent-orchestrator",  "agent_delegation", "agent-risk-analyzer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-risk-analyzer", "agent_delegation", "agent-data-fetcher",  random.choice(CLEAN_PAYLOADS), None),
            ("agent-data-fetcher",  "agent_delegation", "agent-risk-analyzer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-risk-analyzer", "agent_delegation", "agent-data-fetcher",  random.choice(CLEAN_PAYLOADS), None),
            ("agent-data-fetcher",  "agent_delegation", "agent-risk-analyzer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-orchestrator",  "human_handoff",    "on_call_engineer",    "Loop detected — escalating", None),
        ]

    elif scenario == "low_conf":  # automated decision below the confidence floor → RE-05
        steps = [
            ("agent-orchestrator",  "agent_delegation", "agent-decision",      random.choice(CLEAN_PAYLOADS), None),
            ("agent-decision",      "data_read",        "risk_signals_db",     random.choice(CLEAN_PAYLOADS), None),
            ("agent-decision",      "model_inference",  "decision_model_v1",   random.choice(CLEAN_PAYLOADS), None),
            ("agent-decision",      "decision",         "approve_transaction", "decision=approve", {"confidence": 0.41}),
            ("agent-orchestrator",  "human_handoff",    "risk_reviewer",       "Low confidence — routed to human", None),
        ]

    # r56 · the finance/conduct shapes — what makes the register read as a
    # financial institution's agent estate, not a privacy linter.
    elif scenario == "payment_tool_grab":  # notifier reaches the FUNDS tool → RE-04, effectful
        steps = [
            ("agent-orchestrator", "agent_delegation", "agent-notifier",      random.choice(CLEAN_PAYLOADS), None),
            ("agent-notifier",     "tool_execution",   "payment_disbursement", "{'tool': 'payment_disbursement', 'input': {'amount': 1250, 'currency': 'USD'}}", None),
            ("agent-orchestrator", "human_handoff",    "security_team",       "Out-of-scope tool execution — escalating", None),
        ]

    elif scenario == "retail_comms":  # comms sent to customers, out of scope, gate skipped → RE-04 + RE-03
        steps = [
            ("agent-orchestrator",  "agent_delegation",  "agent-report-writer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "model_inference",   "comms_draft_model",   random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "agent_delegation",  "agent-notifier",      random.choice(CLEAN_PAYLOADS), None),
            # the send happens BEFORE any human gate — that ordering is the finding
            ("agent-notifier",      "external_api_call", "customer-comms-gateway.external.io", random.choice(CLEAN_PAYLOADS), None),
            ("agent-orchestrator",  "human_handoff",     "compliance_team",     "Post-hoc review — comms already sent", None),
        ]

    elif scenario == "ledger_amend":  # record-store write with broken lineage → RE-06
        steps = [
            ("agent-orchestrator",  "agent_delegation", "agent-report-writer", random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "data_read",        "internal_ledger",     random.choice(CLEAN_PAYLOADS), None),
            ("agent-report-writer", "data_write",       "internal_ledger",     random.choice(CLEAN_PAYLOADS), {"lineage_complete": False}),
            ("agent-report-writer", "human_handoff",    "risk_reviewer",       "Ledger write flagged — lineage incomplete", None),
        ]

    else:
        steps = []

    for i, (agent_id, action_type, target, payload, signals) in enumerate(steps):
        t += random.randint(50, 400)
        signals = signals or {}
        pii_found = _contains_pii(payload)

        action = {
            "trace_id":     str(uuid.uuid4())[:8],
            "workflow_id":  workflow_id,
            "span_id":      f"span-{i+1:03d}",
            "timestamp":    _ts(t),
            "agent_id":     agent_id,
            "agent_name":   next((a["name"] for a in AGENTS if a["id"] == agent_id), agent_id),
            "action_type":  action_type,
            "target":       target,
            "payload_preview": payload[:120],
            "pii_detected": pii_found,
            "pii_redacted": bool(pii_found) and action_type in ("external_api_call", "data_write"),
            # RAW signals the classifier derives risk events from — NO labels here
            "consent_verified": signals.get("consent_verified", True),
            "confidence":   signals.get("confidence"),          # set only for `decision`
            "lineage_complete": signals.get("lineage_complete", True),  # write provenance intact?
            "agent_scope":  AGENT_SCOPE.get(agent_id, []),      # authorization context
            "duration_ms":  random.randint(8, 850),
            "status":       "completed",
            "data_lineage": {
                "source": agent_id,
                "destination": target,
                "data_classification": "PII" if pii_found else "internal",
            },
        }
        actions.append(action)

    return actions


def generate_workflow_batch(n: int = 10, seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Generate a batch of workflows with mixed scenarios.

    When ``seed`` is given the batch is fully deterministic — seeded RNG, a fixed
    base clock, and hash-derived workflow IDs (not uuid4) — so the same (n, seed)
    always reproduces the same projection. An examiner can re-derive any finding;
    a golden-file test can pin the artefact seal.
    """
    global _BASE_TIME
    if seed is not None:
        random.seed(seed)
        _BASE_TIME = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    # r56: the rotation carries the finance/conduct shapes alongside the data-
    # governance ones — the register must read as a financial institution's
    # agent estate. Changing this list is a scenario EPOCH (findings re-key).
    scenarios = ["clean", "clean", "clean", "pii_leak", "scope_exceed",
                 "consent_gap", "loop", "low_conf", "payment_tool_grab",
                 "retail_comms", "ledger_amend", "clean", "pii_leak"]
    workflows = []
    for i in range(n):
        if seed is not None:
            wf_id = "WF-" + hashlib.md5(f"{seed}-{i}".encode()).hexdigest()[:6].upper()
        else:
            wf_id = f"WF-{str(uuid.uuid4())[:6].upper()}"
        scenario = scenarios[i % len(scenarios)]
        traces = generate_agent_trace(wf_id, scenario)
        # risk events are DERIVED downstream by the classifier, not pre-tagged here
        risk_count = sum(len(a.get("risk_events", [])) for a in traces)
        workflows.append({
            "workflow_id":    wf_id,
            "scenario":       scenario,
            "started_at":     traces[0]["timestamp"] if traces else _ts(),
            "action_count":   len(traces),
            "risk_event_count": risk_count,
            "has_pii":        any(a["pii_detected"] for a in traces),
            "status":         "completed",
            "traces":         traces,
        })
    return workflows


if __name__ == "__main__":
    import json
    batch = generate_workflow_batch(5)
    for wf in batch:
        print(f"{wf['workflow_id']} [{wf['scenario']:15}] "
              f"actions={wf['action_count']} "
              f"risk_events={wf['risk_event_count']} "
              f"pii={wf['has_pii']}")
