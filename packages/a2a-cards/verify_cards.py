"""
a2a-cards verifier — proves the cards, then reconciles them against reality.

Gates (same substance discipline as the other validators — a green run means the
BEHAVIOUR holds, not that files exist):
  C1  cards present for issuance sources (atg simulator agents + rac inventory)
  C2  every card schema-complete (identity, scope, issuer, expiry, signature)
  C3  every Ed25519 signature verifies against the published issuer key
  C4  TAMPER test — mutate one scope entry, signature must FAIL (proves C3 isn't
      vacuously passing)
  C5  expiry sanity (expires > issued_at)
  C6  NO SCOPE DRIFT — each atg card's tool_scope equals AGENT_SCOPE byte-for-byte
      (cards cannot diverge from the authorization source the RE-04 classifier
      enforces)
  C7  TRACE RECONCILIATION — every agent_id observed in the seeded atg trace
      stream (seed 42, same as the dashboard) carries a valid card; uncarded
      observed agents are listed, not hidden
  C8  rac AI-gov inventory agents all carded
  C9  determinism — rebuild is byte-identical (fixed key/clock/uuids)

Run:  python3 packages/a2a-cards/verify_cards.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
sys.path.insert(0, str(HERE))
import build_cards  # noqa: E402

from cryptography.exceptions import InvalidSignature  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: E402

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
results: list[bool] = []


def check(cid: str, ok: bool, msg: str) -> None:
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {cid} · {msg}")


def main() -> int:
    print("a2a-cards verification")
    print("=" * 58)
    build_cards.build()
    issuer = json.loads((DIST / "issuer.json").read_text())
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer["public_key_hex"]))
    cards = {p.stem.replace(".card", ""): json.loads(p.read_text())
             for p in sorted((DIST / "cards").glob("*.card.json"))}

    print("\nC1 · issuance coverage")
    sys.path.insert(0, str(REPO / "apps" / "agent-trace-gov"))
    from data.agent_simulator import AGENTS, AGENT_SCOPE, generate_workflow_batch  # noqa: E402
    check("C1.1 a card exists for every atg simulator agent",
          all(a["id"] in cards for a in AGENTS), f"{len(cards)} cards · {len(AGENTS)} atg agents")

    print("\nC2 · schema completeness")
    REQ = ("schema_version", "card_id", "agent_id", "display_name", "spoke",
           "tool_scope", "scope_source", "issuer", "key_id", "issued_at", "expires", "source_status")
    incomplete = [aid for aid, c in cards.items() if any(k not in c["card"] for k in REQ)]
    check("C2.1 every card carries the full identity/scope/issuer schema",
          not incomplete, "complete" if not incomplete else str(incomplete[:3]))
    check("C2.2 every card is labeled illustrative (honest issuance source)",
          all(c["card"]["source_status"] == "illustrative" for c in cards.values()), "labeled")

    print("\nC3 · signatures")
    bad_sig = []
    for aid, c in cards.items():
        try:
            pub.verify(bytes.fromhex(c["signature"]["sig_hex"]),
                       build_cards.canonical(c["card"]).encode("utf-8"))
        except InvalidSignature:
            bad_sig.append(aid)
    check("C3.1 every Ed25519 signature verifies against the published issuer key",
          not bad_sig, f"{len(cards)}/{len(cards)} verify" if not bad_sig else str(bad_sig))

    print("\nC4 · tamper detection (the gate that proves C3 isn't vacuous)")
    victim = dict(next(iter(cards.values()))["card"])
    victim["tool_scope"] = list(victim["tool_scope"]) + ["data_write"]  # privilege escalation attempt
    try:
        pub.verify(bytes.fromhex(next(iter(cards.values()))["signature"]["sig_hex"]),
                   build_cards.canonical(victim).encode("utf-8"))
        tampered_caught = False
    except InvalidSignature:
        tampered_caught = True
    check("C4.1 adding a scope to a signed card breaks its signature", tampered_caught,
          "escalation attempt rejected" if tampered_caught else "TAMPER NOT DETECTED")

    print("\nC5 · expiry")
    check("C5.1 expires > issued_at on every card",
          all(c["card"]["expires"] > c["card"]["issued_at"] for c in cards.values()), "sane")

    print("\nC6 · no scope drift vs the RE-04 authorization source")
    drift = [a["id"] for a in AGENTS
             if cards.get(a["id"]) and cards[a["id"]]["card"]["tool_scope"] != AGENT_SCOPE.get(a["id"], [])]
    check("C6.1 every atg card's tool_scope == AGENT_SCOPE (byte-for-byte)",
          not drift, "no drift" if not drift else f"DRIFT: {drift}")

    print("\nC7 · trace reconciliation (cards vs observed reality, seed 42)")
    observed = set()
    for wf in generate_workflow_batch(16, seed=42):
        for tr in wf.get("traces", wf if isinstance(wf, list) else []):
            if isinstance(tr, dict) and tr.get("agent_id"):
                observed.add(tr["agent_id"])
    if not observed:  # tolerate alternate batch shape
        for wf in generate_workflow_batch(16, seed=42):
            if isinstance(wf, dict):
                for v in wf.values():
                    if isinstance(v, list):
                        observed |= {t.get("agent_id") for t in v if isinstance(t, dict) and t.get("agent_id")}
    uncarded = sorted(a for a in observed if a not in cards)
    check("C7.1 every trace-observed agent carries a card (uncarded = listed, not hidden)",
          not uncarded, f"{len(observed)} observed, all carded" if not uncarded
          else f"{len(observed)} observed · UNCARDED: {uncarded} (matches atg's ungoverned-agent class)")

    print("\nC8 · rac AI-gov inventory coverage")
    globs = sorted((REPO / "apps" / "risk-as-code-agent" / "outputs" / "v2_0a").glob("*_projection.json"))
    inv = [a.get("id") for a in json.loads(globs[-1].read_text()).get("ai_gov", {}).get("agents", []) if a.get("id")]
    missing_inv = [a for a in inv if a not in cards]
    check("C8.1 every rac inventory agent is carded", not missing_inv,
          f"{len(inv)} inventory agents, all carded" if not missing_inv else str(missing_inv))

    print("\nC9 · determinism")
    before = {p.name: p.read_text() for p in (DIST / "cards").glob("*.card.json")}
    build_cards.build()
    after = {p.name: p.read_text() for p in (DIST / "cards").glob("*.card.json")}
    check("C9.1 rebuild is byte-identical (fixed key/clock/uuids)", before == after, "byte-stable")

    print("\n" + "=" * 58)
    failed = results.count(False)
    print(f"Summary: {results.count(True)} PASS · {failed} FAIL · {len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
