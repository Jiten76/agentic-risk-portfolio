"""
oscal-bindings — emit machine-readable OSCAL from the hub's KRI catalog + crosswalk.

Produces two OSCAL 1.1.2 documents:
  dist/kri-catalog.oscal.json          — the canonical KRI catalog AS an OSCAL catalog
                                         (families → groups, KRIs → controls).
  dist/spokes.component-definition.oscal.json
                                       — each spoke as an OSCAL component, declaring which
                                         catalog controls (KRIs) it assesses, via crosswalk.

Deterministic: UUIDs are uuid5(namespace, key) and the timestamp is fixed, so the output is
byte-reproducible (same discipline as the dashboards' artefact seal). No external deps but PyYAML.

Run:  python3 packages/oscal-bindings/build_oscal.py
"""
from __future__ import annotations
import json
import sys
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

HERE = Path(__file__).resolve().parent
KRI = HERE.parent / "kri-taxonomy"
DIST = HERE / "dist"
NS = uuid.UUID("1b671a64-40d5-491e-99b0-da01ff1f3341")   # fixed namespace → deterministic uuids
TS = "2026-07-01T00:00:00Z"                              # fixed → reproducible
OSCAL_VERSION = "1.1.2"


def uid(key: str) -> str:
    return str(uuid.uuid5(NS, key))


def _meta(title: str) -> dict:
    return {"title": title, "last-modified": TS, "version": "1.0", "oscal-version": OSCAL_VERSION}


def build_catalog(catalog_yaml: dict) -> dict:
    groups = []
    for fam_key, fam in catalog_yaml["families"].items():
        controls = []
        for kri in fam["kris"]:
            props = [{"name": "framework", "value": fw} for fw in kri.get("frameworks", [])]
            # Jurisdiction mapping strategy (round-9): US regulators speak
            # NYDFS 500 / FFIEC / NIST CSF 2.0; EU-Global speaks ISO 27001:2022
            # Annex A plus the cloud pair 27017 (cloud controls, CLD extensions)
            # and 27018 (PII in public cloud). Judgment mappings; approximate
            # hooks carry caveat props; a scheme is omitted where it has nothing
            # real to say rather than padded.
            SCHEMES = [("iso_27001_2022", "iso-27001-2022", "mapping-global"),
                       ("iso_27017", "iso-27017", "mapping-global"),
                       ("iso_27018", "iso-27018", "mapping-global"),
                       ("nydfs_500", "nydfs-500", "mapping-us"),
                       ("ffiec_booklets", "ffiec-it-booklet", "mapping-us"),
                       ("nist_csf_2", "nist-csf-2.0", "mapping-us")]
            for ykey, pname, pclass in SCHEMES:
                for code in kri.get(ykey, []):
                    props.append({"name": pname, "value": code, "class": pclass})
            if kri.get("iso_note"):
                props.append({"name": "iso-27001-2022-note", "value": kri["iso_note"], "class": "mapping-caveat"})
            controls.append({
                "id": kri["id"].lower(),
                "title": kri["name"],
                "props": props,
                "parts": [{"id": kri["id"].lower() + "_stmt", "name": "statement",
                           "prose": kri.get("description", "")}],
            })
        groups.append({"id": fam_key.lower(), "title": fam["name"], "controls": controls})
    return {"catalog": {
        "uuid": uid("catalog"),
        "metadata": _meta("Agentic Risk Portfolio — Canonical KRI Catalog"),
        "groups": groups,
    }}


def build_component_definition(crosswalk: dict) -> dict:
    components = []
    for spoke, cfg in crosswalk["spokes"].items():
        # canonical KRI -> the spoke patterns that map to it (primary or also)
        kri_to_patterns: dict = {}
        for m in cfg["map"]:
            for tgt in [m["primary"], *m.get("also", [])]:
                kri_to_patterns.setdefault(tgt, []).append(m["from"])
        reqs = []
        for kri_id in sorted(kri_to_patterns):
            pats = ", ".join(sorted(kri_to_patterns[kri_id]))
            reqs.append({
                "uuid": uid(f"ir:{spoke}:{kri_id}"),
                "control-id": kri_id.lower(),
                "description": f"Assessed by {spoke} via pattern(s) {pats}.",
            })
        components.append({
            "uuid": uid(f"component:{spoke}"),
            "type": "software",
            "title": spoke,
            "description": f"Portfolio spoke '{spoke}' — assesses {len(reqs)} canonical KRIs.",
            "control-implementations": [{
                "uuid": uid(f"ci:{spoke}"),
                "source": "kri-catalog.oscal.json",
                "description": f"Canonical KRIs assessed by {spoke}.",
                "implemented-requirements": reqs,
            }],
        })
    return {"component-definition": {
        "uuid": uid("component-definition"),
        "metadata": _meta("Agentic Risk Portfolio — Spoke Component Definition"),
        "components": components,
    }}


# ── assessment-plan + assessment-results — OSCAL end-to-end from real findings ────
# Round-9 build (user ask: "graduate OSCAL to end-to-end"). The rac projection's
# findings become an OSCAL 1.1.2 assessment-results document: each finding targets
# its canonical KRI control (via the crosswalk), carries an observation (the
# exceeded signals), and an associated risk whose status/remediation/deadline come
# from the treatment plan. A minimal assessment-plan scopes the reviewed controls.
# HONEST SIMPLIFICATION, on the record: a demonstrator has no System Security Plan,
# so the plan's required import-ssp points at a same-document remark instead of an
# SSP — stated in remarks, gated in validate.py, not hidden.

RAC_OUT = HERE.parent.parent / "apps" / "risk-as-code-agent" / "outputs" / "v2_0a"
ATG_OUT = HERE.parent.parent / "apps" / "agent-trace-gov" / "outputs"

_RISK_STATUS = {  # treatment.status → OSCAL risk status vocabulary
    "accepted": "deviation-approved",
    "in_progress": "remediating",
    "blocked": "open",
    "planned": "open",
}


def _load_rac_projection() -> dict:
    globs = sorted(RAC_OUT.glob("*_projection.json"))
    if not globs:
        sys.exit(f"no rac projection under {RAC_OUT} — build the rac dashboard first")
    return json.loads(globs[-1].read_text())


def _load_atg_projection() -> dict:
    globs = sorted(ATG_OUT.glob("*_atg_projection.json"))
    if not globs:
        sys.exit(f"no atg projection under {ATG_OUT} — build the agent-trace-gov dashboard first")
    return json.loads(globs[-1].read_text())


def _require_kri(crosswalk: dict, spoke_key: str, pid: str, fid: str) -> str:
    """Map a spoke's pattern id → its canonical KRI, RAISING if unmapped.

    No silent default: an unmapped pattern must fail the build loudly, not
    collapse onto a governance control (the old ``gv-01`` fallback) and pass
    review unnoticed.
    """
    m = {e["from"]: e["primary"].lower() for e in crosswalk["spokes"][spoke_key]["map"]}
    if pid not in m:
        sys.exit(f"OSCAL: {spoke_key} finding {fid!r} has pattern {pid!r} not mapped in "
                 f"crosswalk.yaml — refusing to default silently. Add the mapping.")
    return m[pid]


def _not_satisfied(rag: str) -> bool:
    return rag not in ("green", "satisfied", "clear")


def build_assessment_plan(crosswalk: dict) -> dict:
    rac_map = crosswalk["spokes"]["risk-as-code-agent"]["map"]
    atg_map = crosswalk["spokes"]["agent-trace-gov"]["map"]
    kris = sorted({m["primary"].lower() for m in rac_map}
                  | {m["primary"].lower() for m in atg_map})
    return {"assessment-plan": {
        "uuid": uid("assessment-plan"),
        "metadata": _meta("Agentic Risk Portfolio — Assessment Plan (2026-Q3, seeded demonstrator)"),
        "import-ssp": {
            "href": "#demonstrator-no-ssp",
            "remarks": ("This demonstrator has no System Security Plan; the import-ssp "
                        "requirement is satisfied structurally and disclosed here rather "
                        "than pointed at a fabricated SSP. Production would reference the "
                        "platform SSP."),
        },
        "reviewed-controls": {"control-selections": [{
            "description": ("Canonical KRIs assessed by risk-as-code-agent and agent-trace-gov "
                            "(via crosswalk primaries)."),
            "include-controls": [{"control-id": k} for k in kris],
        }]},
        "assessment-subjects": [{
            "type": "component",
            "include-subjects": [
                {"subject-uuid": uid("component:risk-as-code-agent"), "type": "component"},
                {"subject-uuid": uid("component:agent-trace-gov"), "type": "component"},
            ],
        }],
    }}


def _rac_assessment(crosswalk: dict, proj: dict) -> tuple[list, list, list]:
    observations, findings, risks = [], [], []
    for did, dom in sorted(proj.get("domains", {}).items()):
        for f in dom.get("findings", []):
            fid = f["finding_id"]
            pid = f["pattern_id"]
            kri = _require_kri(crosswalk, "risk-as-code-agent", pid, fid)
            rag = f.get("overall_rag", "amber")
            tr = f.get("treatment", {}) or {}
            sig_names = sorted((f.get("signals_exceeded") or {}).keys())
            obs_uuid = uid(f"obs:{fid}")
            risk_uuid = uid(f"risk:{fid}")
            observations.append({
                "uuid": obs_uuid,
                "title": f"{pid} signals exceeded in {did}",
                "description": (f"Signals over threshold: {', '.join(sig_names) or 'see projection'} "
                                f"(seeded demonstrator telemetry; provenance per-signal in the projection)."),
                "methods": ["TEST"],
                "collected": TS,
            })
            risks.append({
                "uuid": risk_uuid,
                "title": f"{pid} · {f.get('pattern_name', '')} ({did})",
                "description": (f.get("org_context", {}) or {}).get("stall_reason",
                                f"{pid} firing in {did}."),
                "statement": f"RAG {rag}; treatment {tr.get('plan', '?')} ({tr.get('status', '?')}).",
                "props": [{"name": "rag", "value": rag},
                          {"name": "pattern-id", "value": pid}],
                "status": _RISK_STATUS.get(tr.get("status", ""), "open"),
                "deadline": (tr.get("eta") or TS[:10]) + "T00:00:00Z",
                "remediations": [{
                    "uuid": uid(f"rem:{fid}"),
                    "lifecycle": "planned",
                    "title": f"{tr.get('plan', 'mitigate')} — {tr.get('owner_team', '')}",
                    "description": (f"Treatment {tr.get('plan', '?')} owned by {tr.get('owner_team', '?')} "
                                    f"({tr.get('owner_handle', '')}, illustrative team handle), "
                                    f"ticket {tr.get('ticket', '—')}, ETA {tr.get('eta', '—')}."),
                }],
            })
            findings.append({
                "uuid": uid(f"finding:{fid}"),
                "title": f"{pid} in {did}",
                "description": f.get("pattern_name", pid),
                "target": {
                    "type": "objective-id",
                    "target-id": kri + "_stmt",
                    "status": {"state": "not-satisfied" if _not_satisfied(rag) else "satisfied"},
                },
                "related-observations": [{"observation-uuid": obs_uuid}],
                "related-risks": [{"risk-uuid": risk_uuid}],
            })
    return observations, findings, risks


def _atg_assessment(crosswalk: dict, proj: dict) -> tuple[list, list, list]:
    """agent-trace-gov findings → OSCAL. Its treatment is populated at Stage 4
    from real attestations, so it is absent (disclosed) here; the risk stays open
    with a Stage-4 remediation stub — degraded gracefully, never fabricated."""
    observations, findings, risks = [], [], []
    for did, dom in sorted(proj.get("domains", {}).items()):
        for f in dom.get("findings", []):
            fid = f["finding_id"]
            pid = f["risk_event_id"]
            kri = _require_kri(crosswalk, "agent-trace-gov", pid, fid)
            rag = f.get("overall_rag", "amber")
            name = f.get("name", pid)
            agents = f.get("affected_agents") or []
            occ = f.get("occurrence_count", "?")
            tr_absent = (f.get("treatment") or {}).get("value") is None
            obs_uuid = uid(f"obs:{fid}")
            risk_uuid = uid(f"risk:{fid}")
            observations.append({
                "uuid": obs_uuid,
                "title": f"{pid} detected in agent traces ({did})",
                "description": (f"{name}: {occ} occurrence(s) across {len(agents)} agent(s) "
                                f"(seeded agent-trace telemetry; per-signal provenance in the projection)."),
                "methods": ["TEST"],
                "collected": TS,
            })
            risks.append({
                "uuid": risk_uuid,
                "title": f"{pid} · {name} ({did})",
                "description": f"{name} derived from agent execution traces in {did}.",
                "statement": (f"RAG {rag}; treatment absent (populated at Stage 4 from attestations)."
                              if tr_absent else f"RAG {rag}."),
                "props": [{"name": "rag", "value": rag},
                          {"name": "risk-event-id", "value": pid}],
                "status": "open",
                "deadline": TS[:10] + "T00:00:00Z",
                "remediations": [{
                    "uuid": uid(f"rem:{fid}"),
                    "lifecycle": "planned",
                    "title": "treatment pending — Stage 4 attestation",
                    "description": ("agent-trace-gov emits detection + framework mapping; the "
                                    "treatment/owner is populated at Stage 4 from real attestation "
                                    "entries and is absent (disclosed) in this demonstrator run."),
                }],
            })
            findings.append({
                "uuid": uid(f"finding:{fid}"),
                "title": f"{pid} in {did}",
                "description": name,
                "target": {
                    "type": "objective-id",
                    "target-id": kri + "_stmt",
                    "status": {"state": "not-satisfied" if _not_satisfied(rag) else "satisfied"},
                },
                "related-observations": [{"observation-uuid": obs_uuid}],
                "related-risks": [{"risk-uuid": risk_uuid}],
            })
    return observations, findings, risks


def build_assessment_results(crosswalk: dict, rac_proj: dict, atg_proj: dict) -> dict:
    r_obs, r_find, r_risk = _rac_assessment(crosswalk, rac_proj)
    a_obs, a_find, a_risk = _atg_assessment(crosswalk, atg_proj)
    return {"assessment-results": {
        "uuid": uid("assessment-results"),
        "metadata": _meta("Agentic Risk Portfolio — Assessment Results (2026-Q3, seeded demonstrator)"),
        "import-ap": {"href": "assessment-plan.oscal.json"},
        "results": [{
            "uuid": uid("result:2026-Q3"),
            "title": "2026-Q3 seeded assessment run (rac + agent-trace-gov, seed-reproducible)",
            "description": ("Automated risk-pattern + agent-trace assessment over seeded telemetry. "
                            "All input data is synthetic and disclosed as such; findings/risks mirror "
                            "the dashboard projections at the mapping level."),
            "start": TS,
            "reviewed-controls": {"control-selections": [{
                "description": "Same control scope as the assessment plan.",
                # control-selections REQUIRES include-all or include-controls;
                # description alone is invalid OSCAL (trestle-validated).
                "include-all": {},
            }]},
            "observations": r_obs + a_obs,
            "risks": r_risk + a_risk,
            "findings": r_find + a_find,
        }],
    }}


def main() -> int:
    catalog_yaml = yaml.safe_load((KRI / "kri-catalog.yaml").read_text())
    crosswalk = yaml.safe_load((KRI / "crosswalk.yaml").read_text())
    DIST.mkdir(exist_ok=True)

    cat = build_catalog(catalog_yaml)
    comp = build_component_definition(crosswalk)
    rac_proj = _load_rac_projection()
    atg_proj = _load_atg_projection()
    ap = build_assessment_plan(crosswalk)
    ar = build_assessment_results(crosswalk, rac_proj, atg_proj)
    (DIST / "kri-catalog.oscal.json").write_text(json.dumps(cat, indent=2, sort_keys=False) + "\n")
    (DIST / "spokes.component-definition.oscal.json").write_text(json.dumps(comp, indent=2, sort_keys=False) + "\n")
    (DIST / "assessment-plan.oscal.json").write_text(json.dumps(ap, indent=2, sort_keys=False) + "\n")
    (DIST / "findings.assessment-results.oscal.json").write_text(json.dumps(ar, indent=2, sort_keys=False) + "\n")

    n_ctrl = sum(len(g["controls"]) for g in cat["catalog"]["groups"])
    n_comp = len(comp["component-definition"]["components"])
    n_find = len(ar["assessment-results"]["results"][0]["findings"])
    print(f"wrote dist/kri-catalog.oscal.json               ({n_ctrl} controls, {len(cat['catalog']['groups'])} groups, ISO-mapped)")
    print(f"wrote dist/spokes.component-definition.oscal.json ({n_comp} components)")
    print(f"wrote dist/assessment-plan.oscal.json             (rac + atg scope)")
    print(f"wrote dist/findings.assessment-results.oscal.json ({n_find} findings, {n_find} risks, {n_find} observations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
