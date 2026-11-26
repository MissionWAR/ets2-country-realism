"""Strict frozen Pydantic v2 diagnostic and report models for offline SCS validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ValidationSeverity = Literal["error", "warning"]
ValidationMode = Literal["workshop", "local_zip"]
PackageProfile = Literal["core", "promods", "combo"]


class ValidationIssue(BaseModel):
    """Single SCS Workshop or ETS2 1.62 realism validation finding."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    code: str
    severity: ValidationSeverity
    path: str | None = None
    detail: str


class ValidationReport(BaseModel):
    """Structured offline validation outcome (warnings fail hard per D-09)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target: str
    mode: ValidationMode
    ok: bool
    error_count: int
    warning_count: int
    issues: list[ValidationIssue] = Field(default_factory=list)


class ValidationCollector:
    """Deduplicated accumulator that converts any error or warning into a hard failure."""

    def __init__(self) -> None:
        self._items: list[ValidationIssue] = []
        self._keys: set[tuple[str, ValidationSeverity, str | None, str]] = set()

    @property
    def items(self) -> list[ValidationIssue]:
        return list(self._items)

    def add(
        self,
        code: str,
        severity: ValidationSeverity,
        path: str | None,
        detail: str,
    ) -> None:
        """Record a deduplicated validation issue in insertion order."""
        key = (code, severity, path, detail)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(
            ValidationIssue(
                code=code,
                severity=severity,
                path=path,
                detail=detail,
            )
        )

    def error(self, code: str, path: str | None, detail: str) -> None:
        """Record a hard validation error."""
        self.add(code, "error", path, detail)

    def warning(self, code: str, path: str | None, detail: str) -> None:
        """Record a validation warning (treated as hard failure in ``ValidationReport.ok``)."""
        self.add(code, "warning", path, detail)

    def build_report(self, target: Path | str, mode: ValidationMode) -> ValidationReport:
        """Finalize an immutable ``ValidationReport`` where ``ok`` requires zero issues."""
        error_count = sum(1 for item in self._items if item.severity == "error")
        warning_count = sum(1 for item in self._items if item.severity == "warning")
        return ValidationReport(
            target=str(target),
            mode=mode,
            ok=len(self._items) == 0,
            error_count=error_count,
            warning_count=warning_count,
            issues=list(self._items),
        )
