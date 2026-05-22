"""Lint/diff finding types + result envelope."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass
class Finding:
    rule: str
    severity: Severity
    file: str
    location: str = ""
    message: str = ""
    suggestion: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["suggestion"] is None:
            del d["suggestion"]
        return d


@dataclass
class LintResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def infos(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary": {
                "files": self.files_scanned,
                "errors": self.errors,
                "warnings": self.warnings,
                "info": self.infos,
            },
        }

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0
