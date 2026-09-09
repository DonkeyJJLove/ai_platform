"""Read-only parser for historical LION RUN text.

Historical RUN prose is DATA. This adapter never executes it and never
interprets an authority declaration as a grant.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

CLASSES = frozenset({"LOSSLESS_TRANSLATION", "LOSSY_BUT_SAFE", "AMBIGUOUS", "UNREPRESENTABLE"})
_RUN = re.compile(r"^\s*RUN(?:=|\s+)([A-Za-z0-9_.:/-]+)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^\s*--([A-Za-z0-9_.-]+)=\s*(.*)$", re.MULTILINE)
_PHASE = re.compile(r"^\s*(?:PHASE(?:_|\s+)|--phase-|phase-)\d+", re.MULTILINE | re.IGNORECASE)
_THEN = re.compile(r"(?:^|[_\s])THEN(?:[_\s]|$)", re.IGNORECASE)


class LegacyRunError(ValueError):
    pass


@dataclass(frozen=True)
class LegacyRunResult:
    classification: str
    run_id: str
    fields: tuple[tuple[str, str], ...]
    reasons: tuple[str, ...]

    def validate(self) -> "LegacyRunResult":
        if self.classification not in CLASSES:
            raise LegacyRunError("invalid legacy classification")
        if self.classification != "UNREPRESENTABLE" and not self.run_id:
            raise LegacyRunError("representable legacy RUN requires run_id")
        return self


class LegacyRunAdapter:
    """Extracts bounded syntax from historical RUN material without effects."""
    KNOWN_FIELDS = frozenset({
        "repository", "baseline", "baseline-head", "baseline-tree", "expected-head", "expected-tree",
        "mode", "objective", "scope", "authority", "require", "prohibit", "on-pass", "on-fail",
        "on-unknown", "falsifiers", "next-step", "project", "mission", "parent-mission", "continuation-of",
    })

    def parse(self, text: str) -> LegacyRunResult:
        if type(text) is not str:
            raise LegacyRunError("historical RUN source must be text")
        match = _RUN.search(text)
        if match is None:
            return LegacyRunResult("UNREPRESENTABLE", "", (), ("RUN identity not found",)).validate()
        run_id = match.group(1)
        fields = tuple((name.lower(), value.strip()) for name, value in _FIELD.findall(text))
        reasons: list[str] = []
        if len([name for name, _ in fields if name == "mode"]) > 1:
            reasons.append("duplicate MODE")
        if _PHASE.search(text):
            reasons.append("numbered PHASE ordering requires dependency reconstruction")
        if any(name == "mode" and _THEN.search(value) for name, value in fields):
            reasons.append("MODE encodes procedural THEN sequence")
        if any(name == "authority" for name, _ in fields):
            reasons.append("authority field is ambiguous between requirement and grant")
        unknown = sorted({name for name, _ in fields if name not in self.KNOWN_FIELDS})
        if unknown:
            reasons.append("unknown legacy fields: " + ",".join(unknown))
        if reasons:
            classification = "AMBIGUOUS"
        else:
            classification = "LOSSY_BUT_SAFE"
            if not fields:
                reasons.append("RUN identity extracted; semantic contract absent")
        return LegacyRunResult(classification, run_id, fields, tuple(reasons)).validate()

    def semantic_candidate(self, text: str) -> dict[str, object]:
        result = self.parse(text)
        if result.classification in {"AMBIGUOUS", "UNREPRESENTABLE"}:
            raise LegacyRunError("legacy RUN cannot be promoted to canonical process")
        return {"legacy_run_id": result.run_id, "classification": result.classification, "fields": dict(result.fields), "authority_effect": "NONE", "execution_effect": "NONE"}
