"""
portfolio_core.action_log — shared hash-chained attestation log.

EXTRACTED from risk-as-code-agent/utils/action_log.py (the FIXED subsystem,
post-commit 822d819). Shared across the portfolio per port spec §14.D/§15.H.

INSTANCE-SCOPED config (adversarial-review fix): config (log path + verb
vocabulary) lives on an `ActionLog` INSTANCE, not module globals — so two
domains in one process can each hold their own without stomping each other
(the SRE re-audit caught the prior module-singleton design cross-contaminating
verb sets + log paths). Module-level functions delegate to a default instance
for backward-compatibility (risk-as-code-agent configures the default); a second
domain (agent-trace-gov) creates ActionLog(...) and never touches the default.

The hash chain, verify_chain(), and named-human + ≥12-word + expiry rules are
identical and shared. _hash_entry is SHA-256 over canonical JSON of the entry
minus this_action_hash (json.dumps(sort_keys=True, default=str)) — the in-browser
verifyChain() canonicalJson() byte-matches this.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "1.0"
ROLE_TIERS = ("1LoD", "2LoD", "3LoD")
_DEFAULT_VERBS = ("gate", "accept", "escalate", "dispo", "require_eval", "restrict_scope")
_DEFAULT_VERBS_NEEDING_EXPIRY = ("gate", "accept", "require_eval", "restrict_scope")
_DEFAULT_MIN_WORDS = 12


def _canon_numbers(obj: Any) -> Any:
    """Coerce numbers into the single canonical form the in-browser verifier can
    byte-match. Python json writes ``25.0`` / ``1e-07`` and full-precision big
    ints; JS ``String()`` writes ``25`` / ``1e-7`` and loses precision past 2^53
    — so floats and oversized ints are NOT allowed in the hashed domain. Integral
    floats → int; non-integral floats → str; ints past 2^53 → str. Applied before
    signing so the stored entry == the hashed entry == the JS-recomputable entry."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return int(obj) if obj.is_integer() else str(obj)
    if isinstance(obj, int) and abs(obj) > 9007199254740991:
        return str(obj)
    if isinstance(obj, dict):
        return {k: _canon_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_canon_numbers(v) for v in obj]
    return obj


def _hash_entry(entry: Dict[str, Any]) -> str:
    """SHA-256 of canonical JSON of an entry (excluding this_action_hash).
    Static — chain integrity is config-independent. The in-browser
    verifyChain() canonicalJson() byte-matches this (numbers closed to the
    canonical domain by _canon_numbers at sign time)."""
    e = {k: v for k, v in entry.items() if k != "this_action_hash"}
    canonical = json.dumps(e, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _word_count(s: str) -> int:
    return len([w for w in (s or "").split() if w.strip()])


def verify_chain(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Walk the chain: verify each entry's CONTENT hash (this_action_hash ==
    _hash_entry(entry)) AND the previous_action_hash LINK. Static (no config).

    The content check mirrors the in-browser verifyChain() (which is link + content),
    so the server-side chain_status cannot report 'intact' over a content-tampered
    entry that the browser would flag as BROKEN (closes the verifier asymmetry)."""
    prev_hash = "GENESIS"
    for i, entry in enumerate(entries):
        if "_error" in entry:
            return {"valid": False, "broken_at_index": i, "reason": entry["_error"]}
        actual = entry.get("previous_action_hash")
        if actual != prev_hash:
            return {
                "valid": False, "broken_at_index": i,
                "expected_prev": prev_hash, "actual_prev": actual,
                "reason": "previous_action_hash does not match the previous entry's this_action_hash",
            }
        if entry.get("this_action_hash") != _hash_entry(entry):
            return {
                "valid": False, "broken_at_index": i,
                "reason": "this_action_hash does not match the recomputed content hash (entry tampered)",
            }
        prev_hash = entry.get("this_action_hash", "")
    return {"valid": True, "broken_at_index": None}


class ActionLog:
    """An attestation log bound to one project's file + verb vocabulary.
    Each portfolio project holds its own instance — no shared mutable global,
    so two domains in one process cannot cross-contaminate (verbs / log path)."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        project_root: Optional[Path] = None,
        verbs: Tuple[str, ...] = _DEFAULT_VERBS,
        verbs_needing_expiry: Tuple[str, ...] = _DEFAULT_VERBS_NEEDING_EXPIRY,
        justification_min_words: int = _DEFAULT_MIN_WORDS,
    ) -> None:
        self.schema_version = SCHEMA_VERSION
        self.role_tiers = ROLE_TIERS
        self.configure(
            log_file=log_file, project_root=project_root, verbs=verbs,
            verbs_needing_expiry=verbs_needing_expiry,
            justification_min_words=justification_min_words,
        )

    def configure(
        self, *, log_file: Optional[Path] = None, project_root: Optional[Path] = None,
        verbs: Optional[Tuple[str, ...]] = None,
        verbs_needing_expiry: Optional[Tuple[str, ...]] = None,
        justification_min_words: Optional[int] = None,
    ) -> "ActionLog":
        if log_file is not None:
            self.log_file = Path(log_file)
            self.project_root = Path(project_root) if project_root else self.log_file.resolve().parent.parent
        elif not hasattr(self, "log_file"):
            self.log_file = None
            self.project_root = Path(project_root) if project_root else None
        if verbs is not None:
            self.verbs = tuple(verbs)
        elif not hasattr(self, "verbs"):
            self.verbs = _DEFAULT_VERBS
        if verbs_needing_expiry is not None:
            self.verbs_needing_expiry = tuple(verbs_needing_expiry)
        elif not hasattr(self, "verbs_needing_expiry"):
            self.verbs_needing_expiry = _DEFAULT_VERBS_NEEDING_EXPIRY
        if justification_min_words is not None:
            self.justification_min_words = int(justification_min_words)
        elif not hasattr(self, "justification_min_words"):
            self.justification_min_words = _DEFAULT_MIN_WORDS
        return self

    def _require_log_file(self) -> Path:
        if self.log_file is None:
            raise RuntimeError(
                "ActionLog not configured — set log_file (each project points it "
                "at its own data/*.jsonl)."
            )
        return self.log_file

    def validate_entry(self, entry: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        required = (
            "actor_name", "actor_handle", "actor_role", "actor_role_tier",
            "verb", "target_type", "target_id", "target_name",
            "timestamp", "justification", "linked_findings",
        )
        for key in required:
            if not entry.get(key):
                errors.append(f"missing required field: {key}")
        if entry.get("verb") and entry["verb"] not in self.verbs:
            errors.append(f"verb must be one of {self.verbs}; got {entry['verb']}")
        if entry.get("actor_role_tier") and entry["actor_role_tier"] not in self.role_tiers:
            errors.append(f"actor_role_tier must be one of {self.role_tiers}")
        just = entry.get("justification", "")
        if just and _word_count(just) < self.justification_min_words:
            errors.append(
                f"justification must be ≥{self.justification_min_words} words "
                f"(got {_word_count(just)}); per amendment A8")
        if entry.get("verb") in self.verbs_needing_expiry and not entry.get("expiry"):
            errors.append(f"verb '{entry.get('verb')}' requires expiry date")
        return errors

    def read_log(self) -> List[Dict[str, Any]]:
        log_file = self._require_log_file()
        if not log_file.exists():
            return []
        out: List[Dict[str, Any]] = []
        with log_file.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as e:
                    out.append({"_error": f"JSON parse failed at line {line_no}: {e}", "_raw": line})
        return out

    def make_entry(
        self, *, actor_name: str, actor_handle: str, actor_role: str, actor_role_tier: str,
        verb: str, target_type: str, target_id: str, target_name: str, justification: str,
        linked_findings: List[str], expiry: Optional[str] = None,
        review_cadence_days: Optional[int] = None, dissenting_voice: Optional[str] = None,
        thresholds_at_time: Optional[Dict[str, Any]] = None,
        previous_action_hash: str = "GENESIS", timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        base = {
            "schema_version": self.schema_version,
            "actor_name": actor_name, "actor_handle": actor_handle,
            "actor_role": actor_role, "actor_role_tier": actor_role_tier,
            "verb": verb, "target_type": target_type, "target_id": target_id,
            "target_name": target_name, "timestamp": timestamp,
            "justification": justification, "justification_min_words": self.justification_min_words,
            "expiry": expiry, "review_cadence_days": review_cadence_days,
            "dissenting_voice": dissenting_voice, "linked_findings": linked_findings,
            "thresholds_at_time": thresholds_at_time or {},
            "previous_action_hash": previous_action_hash,
        }
        base = _canon_numbers(base)
        base["this_action_hash"] = _hash_entry(base)
        return base

    def append_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        log_file = self._require_log_file()
        existing = self.read_log()
        last_hash = "GENESIS"
        if existing:
            last = existing[-1]
            if "_error" not in last:
                last_hash = last.get("this_action_hash", "GENESIS")
        if entry.get("previous_action_hash") != last_hash:
            entry["previous_action_hash"] = last_hash
        entry = _canon_numbers(entry)
        entry["this_action_hash"] = _hash_entry(entry)
        errors = self.validate_entry(entry)
        if errors:
            raise ValueError(f"action_log validation failed: {errors}")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def action_log_summary(self) -> Dict[str, Any]:
        log_file = self._require_log_file()
        entries = self.read_log()
        chain = verify_chain(entries)
        recent = entries[-5:] if entries else []
        try:
            rel_path = str(log_file.relative_to(self.project_root)) if self.project_root else str(log_file)
        except ValueError:
            rel_path = str(log_file)
        return {
            "schema_version": self.schema_version,
            "path": rel_path,
            "total_entries": len(entries),
            "chain_status": "intact" if chain["valid"] else "BROKEN",
            "chain_detail": chain,
            "recent_entries": recent,
            "verbs_supported": list(self.verbs),
            # The renderer's verb modal reads this to know which verbs require an
            # expiry; without it the client falls back to a generic default that
            # may not match this domain's vocabulary. Expose it per-instance.
            "verbs_needing_expiry": list(self.verbs_needing_expiry),
            "role_tiers": list(self.role_tiers),
            "justification_min_words": self.justification_min_words,
        }


# ── Default instance + module-level delegation (backward-compat) ───────────────
# risk-as-code-agent's shim calls module-level configure() + imports the
# functions; those operate on this default instance. agent-trace-gov builds its
# OWN ActionLog(...) and never touches the default — no cross-domain stomp.
_default = ActionLog()
# Module-level VERBS etc. reflect the default (finance) vocabulary at import; a
# second domain reads its own instance's .verbs, not these.
VERBS = _default.verbs
JUSTIFICATION_MIN_WORDS = _default.justification_min_words


def configure(**kwargs) -> None:
    _default.configure(**kwargs)


def validate_entry(entry):       return _default.validate_entry(entry)
def read_log():                  return _default.read_log()
def make_entry(**kwargs):        return _default.make_entry(**kwargs)
def append_entry(entry):         return _default.append_entry(entry)
def action_log_summary():        return _default.action_log_summary()
