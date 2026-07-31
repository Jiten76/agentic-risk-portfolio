"""
a2a-cards — signed agent identity / interop cards for the portfolio's agents.

Graduates the last "declared roadmap contract" into a working demonstrator: every
agent the platform knows about gets a CARD — a canonical-JSON identity document
(who the agent is, which spoke runs it, what it is AUTHORIZED to do) signed with
Ed25519. The verifier proves the signatures, runs a tamper test, and — the
substance — RECONCILES cards against reality: every agent observed in the atg
trace stream and every agent in rac's AI-gov inventory must be carded, and each
card's tool_scope must equal the authorization source (atg AGENT_SCOPE) byte for
byte, so cards cannot drift from the scopes the RE-04 classifier enforces.

HONEST SCOPE, on the record:
  - The signing key is a COMMITTED TEST KEY derived from a fixed seed and printed
    in this file — deliberately, so the whole build is deterministic/reproducible
    (RFC 8032 Ed25519 signatures are deterministic). It proves the MECHANISM
    (issue → sign → verify → reconcile), not key custody. Production would issue
    from an HSM/KMS-held key with rotation and a revocation list.
  - Cards are issued from declared/config data (illustrative), not a live
    registration flow.

Deterministic: fixed key, fixed clock, uuid5 ids, sorted-key canonical JSON →
byte-reproducible dist/ (same discipline as the seals and OSCAL exports).

Run:  python3 packages/a2a-cards/build_cards.py   (needs `cryptography`)
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # pragma: no cover
    sys.exit("`cryptography` required: pip install cryptography")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
NS = uuid.UUID("7c2f4a19-88de-4b6e-9a55-3d2f10c4e901")   # fixed → deterministic uuids
TS = "2026-07-01T00:00:00Z"                              # fixed clock → reproducible
EXPIRES = "2027-07-01T00:00:00Z"
SCHEMA_VERSION = "1.0"

# DISCLOSED TEST KEY — deterministic by design (see module docstring).
_KEY_SEED = hashlib.sha256(b"a2a-cards-demonstrator-test-key-DISCLOSED").digest()
_PRIV = Ed25519PrivateKey.from_private_bytes(_KEY_SEED)
KEY_ID = "a2a-demo-2026-07"
PUB_HEX = _PRIV.public_key().public_bytes_raw().hex()


def uid(key: str) -> str:
    return str(uuid.uuid5(NS, key))


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign(body: dict) -> dict:
    sig = _PRIV.sign(canonical(body).encode("utf-8"))
    return {"alg": "Ed25519", "key_id": KEY_ID, "sig_hex": sig.hex(),
            "signed_payload": "canonical JSON of `card` (sorted keys, compact separators, ascii)"}


def _atg_agents():
    sys.path.insert(0, str(REPO / "apps" / "agent-trace-gov"))
    from data.agent_simulator import AGENTS, AGENT_SCOPE  # noqa: E402
    for a in AGENTS:
        yield {
            "agent_id": a["id"],
            "display_name": a["name"],
            "agent_type": a["type"],
            "spoke": "agent-trace-gov",
            "runtime": "simulated multi-agent workflow (seeded)",
            "tool_scope": list(AGENT_SCOPE.get(a["id"], [])),
            "scope_source": "data/agent_simulator.py::AGENT_SCOPE — the same authorization context the RE-04 classifier enforces",
        }


def _rac_agents():
    globs = sorted((REPO / "apps" / "risk-as-code-agent" / "outputs" / "v2_0a").glob("*_projection.json"))
    if not globs:
        return
    proj = json.loads(globs[-1].read_text())
    for a in (proj.get("ai_gov", {}) or {}).get("agents", []) or []:
        yield {
            "agent_id": a.get("id") or a.get("agent_id"),
            "display_name": a.get("name", ""),
            "agent_type": "inventory",
            "spoke": "risk-as-code-agent",
            "runtime": a.get("framework", ""),
            "tool_scope": list(a.get("scope") or a.get("scopes") or []),
            "scope_source": "rac projection ai_gov.agents inventory (declared, illustrative)",
            "hitl_required": bool(a.get("hitl_required")),
        }


def build() -> list[Path]:
    DIST.mkdir(exist_ok=True)
    cards_dir = DIST / "cards"
    cards_dir.mkdir(exist_ok=True)
    written = []
    for src in (*_atg_agents(), *_rac_agents()):
        if not src.get("agent_id"):
            continue
        body = {
            "schema_version": SCHEMA_VERSION,
            "card_id": uid(f"card:{src['agent_id']}"),
            **src,
            "issuer": "agentic-risk-portfolio demonstrator CA (test key — see build_cards.py disclosure)",
            "key_id": KEY_ID,
            "issued_at": TS,
            "expires": EXPIRES,
            "source_status": "illustrative",
        }
        card = {"card": body, "signature": sign(body)}
        p = cards_dir / f"{src['agent_id']}.card.json"
        p.write_text(json.dumps(card, indent=2, sort_keys=False) + "\n")
        written.append(p)
    (DIST / "issuer.json").write_text(json.dumps({
        "key_id": KEY_ID, "alg": "Ed25519", "public_key_hex": PUB_HEX,
        "disclosure": ("TEST issuer for a reproducible demonstrator: the private key is "
                       "derived from a fixed, published seed. Proves the mechanism, not "
                       "key custody — production issues from HSM/KMS with rotation + "
                       "revocation."),
        "issued_at": TS,
    }, indent=2) + "\n")
    return written


def main() -> int:
    written = build()
    print(f"wrote {len(written)} agent cards → dist/cards/ (+ dist/issuer.json, key {KEY_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
