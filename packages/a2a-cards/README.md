# a2a-cards — signed agent identity / interop cards

Every agent the platform knows about gets a **card**: a canonical-JSON identity
document (who the agent is, which spoke runs it, what it is *authorized* to do)
signed with **Ed25519**. The verifier proves the mechanism, then reconciles the
cards against reality.

```
python3 packages/a2a-cards/build_cards.py    # 10 cards → dist/cards/ + dist/issuer.json
python3 packages/a2a-cards/verify_cards.py   # 10/10
```

## What makes it substance, not ceremony

- **Tamper gate** — the verifier *adds a scope* to a signed card (a privilege-
  escalation attempt) and asserts the signature breaks. Signature checking that
  can't fail is theater; this one is proven non-vacuous on every run.
- **No scope drift** — each atg card's `tool_scope` must equal
  `agent_simulator.AGENT_SCOPE` byte-for-byte: the *same* authorization context
  the RE-04 (scope-exceeded) classifier enforces. Cards cannot quietly diverge
  from the source of authority.
- **Trace reconciliation** — every `agent_id` observed in the seeded atg trace
  stream (seed 42, same run the dashboard shows) must carry a card; uncarded
  observed agents are listed, never hidden — the same ungoverned-agent class
  atg's RE-04 flags.
- **Deterministic** — fixed clock, uuid5 ids, RFC 8032 Ed25519 (deterministic
  signatures) → `dist/` is byte-reproducible, same discipline as the dashboards'
  seals and the OSCAL exports.

## Honest scope

The signing key is a **committed test key** derived from a published seed —
deliberately, so the whole build reproduces byte-for-byte. It demonstrates the
mechanism (issue → sign → verify → reconcile), **not key custody**. Production
issues from an HSM/KMS-held key with rotation and a revocation list, and cards
come from a registration flow rather than declared config. All cards carry
`source_status: illustrative`.
