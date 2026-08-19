"""
Structured validation result returned by every SurveyValidator method.

Usage::

    result = validator.sr("Q1", valid_values=[1, 2, 3])
    print(result.summary())
    print(result.error_count)
    print(result.errors)        # pd.DataFrame of error rows
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ValidationResult:
    """Structured validation result of a single validation check.

    Attributes
    ----------
    rule_name : str
        Name of the rule that produced this result (e.g. "SR", "MULTI").
    question : str or list[str]
        Question variable(s) that were checked.
    passed : bool
        True when no errors were found.
    error_count : int
        Number of error records detected.
    checked_records : int
        Total number of records evaluated (after routing filter applied).
    errors : pd.DataFrame
        One row per error.  Columns vary by rule but always include
        ``record_id``, ``question``, ``rule``, ``error_type``.
    metadata : dict
        Arbitrary extra information (valid_values, max_rank, etc.).
    """

    rule_name: str
    question: str | list[str]
    passed: bool
    error_count: int
    checked_records: int
    errors: pd.DataFrame = field(default_factory=pd.DataFrame)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        q = self.question if isinstance(self.question, str) else self.question[0]
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.rule_name} | {q} | "
            f"errors={self.error_count} / checked={self.checked_records}"
        )

    def __repr__(self) -> str:
        return self.summary()


# ---------------------------------------------------------------------------
# Helpers used by rules.py and validator.py to build ValidationResult objects
# ---------------------------------------------------------------------------

def _make_error_row(
    record_id: Any,
    question: str,
    rule: str,
    error_type: str,
    actual: Any = None,
    expected: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a single error row dict for assembly into an errors DataFrame."""
    row: dict[str, Any] = {
        "record_id": record_id,
        "question": question,
        "rule": rule,
        "error_type": error_type,
        "actual": actual,
        "expected": expected,
    }
    row.update(extra)
    return row


def build_result(
    rule_name: str,
    question: str | list[str],
    error_rows: list[dict[str, Any]],
    checked_records: int,
    metadata: dict[str, Any] | None = None,
) -> ValidationResult:
    """Construct a :class:`ValidationResult` from a list of error-row dicts."""
    errors_df = pd.DataFrame(error_rows) if error_rows else pd.DataFrame(
        columns=["record_id", "question", "rule", "error_type", "actual", "expected"]
    )
    return ValidationResult(
        rule_name=rule_name,
        question=question,
        passed=len(error_rows) == 0,
        error_count=len(error_rows),
        checked_records=checked_records,
        errors=errors_df,
        metadata=metadata or {},
    )
