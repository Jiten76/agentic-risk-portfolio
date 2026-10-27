"""
LLM client for agent-trace-gov.
Generates risk narratives and SOC 2 evidence text.
Mock mode runs fully offline.

Mode and API key are read from os.environ at call time (not module
import time) so a UI radio that sets os.environ at runtime propagates
without needing a process restart.
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional

MODEL = "claude-sonnet-4-20250514"
_logger = logging.getLogger("agent_trace_gov.gov_llm")


def _llm_mode() -> str:
    return os.getenv("LLM_MODE", "mock").lower()


def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


def last_llm_error() -> Optional[str]:
    """Surface the last LLM-call error for UI display (never leaks into narrative)."""
    return os.environ.get("_TRACE_LAST_LLM_ERROR") or None


def _record_llm_error(err: Exception) -> None:
    """Log + stash a short sanitised summary. Never returned to the narrative."""
    _logger.warning("LLM call failed; falling back to mock: %s", err)
    short = type(err).__name__
    msg = str(err).splitlines()[0] if str(err) else ""
    if msg:
        os.environ["_TRACE_LAST_LLM_ERROR"] = f"{short}: {msg[:120]}"
    else:
        os.environ["_TRACE_LAST_LLM_ERROR"] = short


def _mock_risk_narrative(
    risk_event_name: str,
    severity: str,
    framework: str,
    occurrence_count: int,
    affected_agents: List[str],
    affected_workflows: List[str],
) -> str:
    agents_str = ", ".join(affected_agents[:3])
    return (
        f"{risk_event_name} was observed {occurrence_count} time(s) across "
        f"{len(affected_workflows)} workflow(s), involving agents: {agents_str}. "
        f"Severity: {severity.upper()}. Framework reference: {framework}. "
        f"Recommend immediate review of affected agent scopes and data handling policies."
    )


def generate_risk_narrative(
    risk_event_id: str,
    risk_event_name: str,
    severity: str,
    framework: str,
    occurrence_count: int,
    affected_agents: List[str],
    affected_workflows: List[str],
) -> str:
    if _llm_mode() == "mock" or not _api_key():
        return _mock_risk_narrative(
            risk_event_name, severity, framework,
            occurrence_count, affected_agents, affected_workflows,
        ) + " [MOCK MODE]"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_api_key())
        prompt = f"""You are a compliance analyst writing an evidence narrative for a governance report.

Risk Event: {risk_event_id} — {risk_event_name}
Severity: {severity}
Framework: {framework}
Occurrences: {occurrence_count}
Affected Agents: {', '.join(affected_agents)}
Affected Workflows: {', '.join(affected_workflows)}

Write a 3-4 sentence evidence narrative that:
1. Describes what the risk event indicates about the agent system's behavior
2. References the specific framework control that applies
3. States the potential impact if unaddressed
4. Recommends a specific remediation action

Tone: audit-ready, factual, no bullet points."""

        msg = client.messages.create(
            model=MODEL, max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        _record_llm_error(e)
        # Silent fallback. Errors live in logs + UI surface, never in narrative.
        return _mock_risk_narrative(
            risk_event_name, severity, framework,
            occurrence_count, affected_agents, affected_workflows,
        )


def generate_soc2_evidence(
    total_workflows: int,
    risk_events: List[Dict],
    pii_flows: int,
    external_flows: int,
) -> Dict[str, Any]:
    """Map governance findings to SOC 2 Trust Service Criteria."""

    critical = sum(1 for e in risk_events if e.get("severity") == "critical")
    high      = sum(1 for e in risk_events if e.get("severity") == "high")

    criteria = {
        "CC6.1": {
            "name": "Logical and Physical Access Controls",
            "status": "finding" if any(e["risk_event_id"] == "RE-04" for e in risk_events) else "satisfied",
            "notes": f"Agent scope violations detected: {sum(1 for e in risk_events if e['risk_event_id'] == 'RE-04')} occurrences"
                     if any(e["risk_event_id"] == "RE-04" for e in risk_events)
                     else "No unauthorized scope expansions detected.",
        },
        "CC6.6": {
            "name": "Logical Access Security — External Transmissions",
            "status": "finding" if any(e["risk_event_id"] == "RE-03" for e in risk_events) else "satisfied",
            "notes": f"Unauthorized external data flows: {sum(1 for e in risk_events if e['risk_event_id'] == 'RE-03')} occurrences"
                     if any(e["risk_event_id"] == "RE-03" for e in risk_events)
                     else f"All {external_flows} external flows authorized.",
        },
        "CC9.2": {
            "name": "Risk Assessment — Vendor and Business Partner Management",
            "status": "satisfied",
            "notes": f"{external_flows} external agent API calls logged and traceable.",
        },
        "P3.1": {
            "name": "Privacy — Collection and Use of Personal Information",
            "status": "finding" if any(e["risk_event_id"] in ("RE-01","RE-02") for e in risk_events) else "satisfied",
            "notes": f"PII flows: {pii_flows}. "
                     + (f"Consent gaps: {sum(1 for e in risk_events if e['risk_event_id'] == 'RE-02')} occurrences."
                        if any(e["risk_event_id"] == "RE-02" for e in risk_events)
                        else "All PII flows have consent records."),
        },
        "P6.1": {
            "name": "Privacy — Disclosure and Notification",
            # keyed to RE-03 (unauthorized EXTERNAL flow) — the actual disclosure
            # event — not RE-01 (internal PII in output, which is P3.1 collection/use).
            "status": "finding" if any(e["risk_event_id"] == "RE-03" for e in risk_events) else "satisfied",
            "notes": f"Unauthorized external disclosures of data: {sum(1 for e in risk_events if e['risk_event_id'] == 'RE-03')} occurrences."
                     if any(e["risk_event_id"] == "RE-03" for e in risk_events)
                     else "No unauthorized external disclosures detected.",
        },
    }

    findings_count = sum(1 for c in criteria.values() if c["status"] == "finding")
    return {
        "assessment_scope": f"{total_workflows} agent workflows",
        "criteria_assessed": len(criteria),
        "findings": findings_count,
        "satisfied": len(criteria) - findings_count,
        "criteria_detail": criteria,
    }
