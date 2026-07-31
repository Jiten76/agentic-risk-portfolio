# oscal-bindings — machine-readable compliance export

Turns the hub's KRI catalog + crosswalk into **OSCAL 1.1.2** — NIST's machine-readable
control language — so the platform's risk vocabulary and coverage are consumable by GRC
tooling, not just human dashboards.

## Output (`dist/`)
- **`kri-catalog.oscal.json`** — the canonical KRI catalog as an OSCAL **catalog**:
  5 families → groups, 22 KRIs → controls, each with framework `props` and a `statement` part.
- **`spokes.component-definition.oscal.json`** — each spoke as an OSCAL **component**, with
  `control-implementations` declaring which catalog controls (KRIs) it assesses — derived
  from `crosswalk.yaml`, so it stays true to the reviewed spoke taxonomies.

## Properties
- **Deterministic** — UUIDs are `uuid5(namespace, key)` and the timestamp is fixed, so the
  emitted OSCAL is byte-reproducible (same discipline as the dashboards' artefact seal).
- **Verified** — `validate.py` checks OSCAL structural conformance (required metadata,
  `oscal-version`, unique control ids, framework props), cross-reference integrity (every
  component control-id resolves to a catalog control), and reproducibility. **8/8.**

## Build
```bash
python3 packages/oscal-bindings/build_oscal.py     # → dist/*.oscal.json
python3 packages/oscal-bindings/validate.py        # 8/8
```

A new spoke appears here automatically once it has a `crosswalk.yaml` block — no code change.
