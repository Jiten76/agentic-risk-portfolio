"""
LLM client wrapper — supports Anthropic Claude (production) and mock mode (demo/CI).
Set ANTHROPIC_API_KEY in .env for real LLM calls.
Set LLM_MODE=mock to run without an API key.
"""

import logging
import os
import json
from typing import Optional


MODEL = "claude-sonnet-4-20250514"
_logger = logging.getLogger("risk_as_code_agent.llm_client")


def _llm_mode() -> str:
    # Read at call time, not at import time, so a UI radio that sets
    # os.environ propagates without a process restart. Default to mock
    # for portfolio demos where running with no key should be honest.
    return os.getenv("LLM_MODE", "mock").lower()


def _api_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


def last_llm_error() -> Optional[str]:
    """Surface the last LLM-call error for UI display (never leaks into narrative)."""
    return os.environ.get("_RISK_LAST_LLM_ERROR") or None


def _record_llm_error(err: Exception) -> None:
    """Log the error and stash a short, sanitised summary for UI surfacing.
    Never returns the message; never appends to narrative output."""
    _logger.warning("LLM call failed; falling back to mock: %s", err)
    # Strip request_id / payload internals — leave just the class + a short message.
    short = type(err).__name__
    msg = str(err).splitlines()[0] if str(err) else ""
    if msg:
        # Trim aggressively so even if a UI prints this, no token / request_id is exposed.
        msg = msg[:120]
        os.environ["_RISK_LAST_LLM_ERROR"] = f"{short}: {msg}"
    else:
        os.environ["_RISK_LAST_LLM_ERROR"] = short


def _fmt_signal_in_narrative(name: str, value) -> str:
    """Smart-round signal value for narrative text — matches the rendering rule
    in utils/html_report.py so the narrative stays consistent with chip display.
    No spurious precision (62.157 days → 62)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    n = name.lower()
    if "count" in n:
        return str(int(round(v)))
    if n.endswith(("_days", "_minutes", "_ms", "_seconds")):
        return str(int(round(v)))
    if n.endswith(("_pct", "_rate")) or "rate" in n or "pct" in n:
        return f"{v:.1f}"
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"


def _mock_evidence_summary(domain: str, pattern_id: str, pattern_name: str, signals: dict) -> str:
    red_signals = [
        k for k, v in signals.items()
        if isinstance(v, dict) and v.get("rag") in ("red", "amber")
    ]
    if not red_signals:
        return (
            f"Domain '{domain}' shows no material findings for {pattern_name} ({pattern_id}). "
            f"All monitored signals are within approved thresholds. No evidence items required."
        )
    parts = []
    for k in red_signals[:3]:
        sig = signals[k]
        val_str = _fmt_signal_in_narrative(k, sig.get("value"))
        parts.append(f"{k}={val_str} ({sig.get('rag', '').upper()})")
    signal_list = ", ".join(parts)
    return (
        f"Domain '{domain}' has elevated readings on {pattern_name} ({pattern_id}). "
        f"Signals of concern: {signal_list}. "
        f"Recommend 2LoD review of control effectiveness and owner attestation within 5 business days."
    )


def _mock_executive_summary(domain: str, findings: list) -> str:
    if not findings:
        return f"Domain '{domain}': No material risk findings. All patterns within appetite."
    top = findings[0]
    return (
        f"Domain '{domain}' presents {len(findings)} risk pattern(s) requiring attention. "
        f"Highest priority: {top.get('pattern_name', 'Unknown')} — {top.get('signal_summary', '')}."
    )


def generate_evidence_summary(
    domain: str,
    pattern_id: str,
    pattern_name: str,
    pattern_description: str,
    signals_exceeded: dict,
    appetite_statement: str,
) -> str:
    """Generate a natural-language evidence summary for a risk pattern finding."""

    if _llm_mode() == "mock" or not _api_key():
        return _mock_evidence_summary(domain, pattern_id, pattern_name, signals_exceeded)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_api_key())

        prompt = f"""You are a second-line-of-defense technology risk analyst writing an evidence summary for an audit-ready risk report.

Domain: {domain}
Risk Pattern: {pattern_id} — {pattern_name}
Description: {pattern_description}
Risk Appetite: {appetite_statement}

Breached or elevated signals (metric: observed value):
{json.dumps(signals_exceeded, indent=2)}

Write a concise (3-5 sentence) evidence summary that:
1. States what the signals indicate about control effectiveness
2. Names the specific signals driving the finding
3. States the residual risk relative to appetite
4. Recommends a specific 2LoD action (review, escalate, accept, remediate)

Tone: professional, factual, audit-ready. No bullet points. Plain prose only."""

        message = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except Exception as e:
        # Log + surface to UI; never leak into narrative.
        _record_llm_error(e)
        return _mock_evidence_summary(domain, pattern_id, pattern_name, signals_exceeded)


def generate_executive_summary(domain: str, findings: list, domain_tier: int) -> str:
    """Generate a board-ready executive summary for a domain."""

    if _llm_mode() == "mock" or not _api_key():
        return _mock_executive_summary(domain, findings)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_api_key())

        findings_text = json.dumps(findings, indent=2) if findings else "No findings."

        prompt = f"""You are a Chief Risk Officer writing a board-level technology risk summary.

Domain: {domain} (Tier {domain_tier} — {"customer-facing critical" if domain_tier == 1 else "platform/infrastructure"})
Risk Findings:
{findings_text}

Write a 2-3 sentence executive summary suitable for a board risk report that:
1. States the overall risk posture of this domain (green/amber/red)
2. Names the top 1-2 concerns without technical jargon
3. States what action is being taken or recommended

Tone: Board-level. No technical acronyms. Quantify where possible."""

        message = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except Exception as e:
        _record_llm_error(e)
        return _mock_executive_summary(domain, findings)


def generate_attestation_statement(
    domain: str,
    period: str,
    total_patterns: int,
    findings_count: int,
    open_items: list,
) -> str:
    """Generate a formal attestation statement for the one-pager."""

    if _llm_mode() == "mock" or not _api_key():
        status = "requires attention" if findings_count > 0 else "is within risk appetite"
        return (
            f"Based on the risk signals evaluated for the period {period}, "
            f"domain '{domain}' {status} across {total_patterns} monitored risk patterns. "
            f"{findings_count} pattern(s) have findings requiring remediation or acceptance. "
            f"This attestation is generated by the Risk-as-Code Agent Framework and is pending owner sign-off."
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_api_key())

        prompt = f"""Write a formal risk attestation statement for an internal audit document.

Domain: {domain}
Assessment Period: {period}
Patterns Assessed: {total_patterns}
Findings Requiring Action: {findings_count}
Open Items: {json.dumps(open_items)}

The statement should:
- Be 2-3 sentences
- Reference the evidence-based methodology
- State the attestation scope and any caveats
- Be suitable for inclusion in a board risk pack

Do not include signatures or dates — those are added separately."""

        message = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except Exception as e:
        _record_llm_error(e)
        # Identical mock fallback shape — never leak the exception into the report.
        status = "requires attention" if findings_count > 0 else "is within risk appetite"
        return (
            f"Based on telemetry-backed evidence collected for the period {period}, "
            f"domain '{domain}' {status} across {total_patterns} monitored risk patterns. "
            f"{findings_count} pattern(s) have findings requiring remediation or acceptance. "
            f"This attestation is generated by the Risk-as-Code Agent Framework and is pending owner sign-off."
        )
