# kri-taxonomy — the hub's shared risk vocabulary

The platform speaks **one** canonical risk vocabulary; each spoke keeps its own
reviewed, fact-checked taxonomy and **maps onto it** — the spokes are never rewritten.

## Files
- **`kri-catalog.yaml`** — the canonical KRI catalog: 5 domain families
  (**AS** Agent Security · **DP** Data Protection & Privacy · **PL** Platform & Infra ·
  **DR** Delivery & Reliability · **GV** Governance & Assurance), 22 KRIs, each with a
  description and standards-accurate framework alignment.
- **`crosswalk.yaml`** — maps every spoke pattern → canonical KRI(s)
  (`primary` + optional `also`). Today: `risk-as-code-agent` RP-01..13 and
  `agent-trace-gov` RE-01..08.
- **`validate.py`** — substance gate. Asserts real coverage against the spokes' *actual*
  taxonomies (no orphan pattern, no phantom mapping, all targets real, ids unique +
  framework-cited). `python3 packages/kri-taxonomy/validate.py` → **9/9**.
- **`risk-patterns.yaml`** — the original May-2 agent-security draft (RP-01..12). It seeded
  the AS/PL families; retained as provenance. The canonical catalog supersedes it.

## Why a crosswalk, not a rewrite
The two spokes were reviewed by six independent lenses and fact-checked end-to-end; their
taxonomies carry that assurance. A canonical catalog + crosswalk lets the hub present one
vocabulary (and drive shared services like OSCAL export) **without** disturbing reviewed
work — the standard "canonical catalog + per-domain mapping" pattern (cf. OSCAL control
mappings). A new spoke conforms by adding its own crosswalk block; unused KRIs (e.g.
`PL-01`) are headroom for the next domain.
