"""
ValidationReport — aggregates multiple ValidationResult objects for QC reporting.

Supports export to:
- CSV (consolidated detailed errors)
- Excel / XLSX (Summary sheet + per-rule error sheets)
- TXT (human-readable QC summary)
- Markdown (tabular Markdown QC summary)

Usage::

    from pandasdv import SurveyValidator, ValidationReport

    validator = SurveyValidator(df)
    results = [
        validator.sr("Q1", valid_values=[1, 2]),
        validator.multi(["Q2_1", "Q2_2"], exclusive=["Q2_99"]),
    ]

    report = ValidationReport(results)
    print(report.summary())

    report.to_csv("survey_qc_errors.csv")
    report.to_excel("survey_qc_report.xlsx")
    report.to_txt("survey_qc_report.txt")
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd

from .results import ValidationResult


class ValidationReport:
    """Consolidates multiple :class:`ValidationResult` objects into a QC report.

    Parameters
    ----------
    results : iterable of ValidationResult
        List or sequence of validation result instances.

    Raises
    ------
    TypeError
        If *results* is not iterable or contains items that are not
        :class:`ValidationResult`.
    """

    def __init__(self, results: Iterable[ValidationResult]) -> None:
        if not isinstance(results, Iterable) or isinstance(results, (str, bytes)):
            raise TypeError("results must be an iterable of ValidationResult objects.")

        validated_results: list[ValidationResult] = []
        for i, item in enumerate(results):
            if not isinstance(item, ValidationResult):
                raise TypeError(
                    f"Item at index {i} is {type(item).__name__}, expected ValidationResult."
                )
            validated_results.append(item)

        self._results = validated_results

    # ------------------------------------------------------------------
    # Properties / KPI metrics
    # ------------------------------------------------------------------

    @property
    def results(self) -> list[ValidationResult]:
        """List of underlying :class:`ValidationResult` instances."""
        return self._results

    @property
    def total_rules(self) -> int:
        """Total number of validation rules evaluated."""
        return len(self._results)

    @property
    def passed_rules(self) -> int:
        """Number of validation rules that passed with 0 errors."""
        return sum(1 for r in self._results if r.passed)

    @property
    def failed_rules(self) -> int:
        """Number of validation rules that failed."""
        return sum(1 for r in self._results if not r.passed)

    @property
    def total_errors(self) -> int:
        """Sum of all error records across all evaluated rules."""
        return sum(r.error_count for r in self._results)

    @property
    def total_checked_records(self) -> int:
        """Sum of all checked records across all evaluated rules."""
        return sum(r.checked_records for r in self._results)

    @property
    def passed(self) -> bool:
        """True if all evaluated validation rules passed with zero errors."""
        if not self._results:
            return True
        return all(r.passed for r in self._results)

    # ------------------------------------------------------------------
    # Summary DataFrame
    # ------------------------------------------------------------------

    def summary(self) -> pd.DataFrame:
        """Return a structured overview DataFrame of all evaluated rules.

        Returns
        -------
        pd.DataFrame
            Columns: ``['rule', 'question', 'status', 'error_count', 'checked_records']``
        """
        rows: list[dict[str, Any]] = []
        for r in self._results:
            if isinstance(r.question, list):
                q_str = f"{r.question[0]}..{r.question[-1]}" if len(r.question) > 1 else str(r.question[0])
            else:
                q_str = str(r.question)

            rows.append({
                "rule": r.rule_name,
                "question": q_str,
                "status": "PASS" if r.passed else "FAIL",
                "error_count": r.error_count,
                "checked_records": r.checked_records,
            })

        if not rows:
            return pd.DataFrame(
                columns=["rule", "question", "status", "error_count", "checked_records"]
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Export methods
    # ------------------------------------------------------------------

    def to_csv(self, file_path: str | Path, **kwargs: Any) -> Path:
        """Export all detailed error records from failed rules to a single CSV.

        Parameters
        ----------
        file_path : str or Path
            Target CSV file path. Parent directories are created automatically.
        **kwargs
            Additional keyword arguments forwarded to ``pandas.DataFrame.to_csv``.

        Returns
        -------
        pathlib.Path
            The resolved target file path.
        """
        path = Path(file_path)
        self._ensure_parent_dir(path)

        error_dfs = [r.errors for r in self._results if not r.passed and not r.errors.empty]

        if error_dfs:
            combined = pd.concat(error_dfs, ignore_index=True)
        else:
            combined = pd.DataFrame(
                columns=["record_id", "question", "rule", "error_type", "actual", "expected"]
            )

        kwargs.setdefault("index", False)
        combined.to_csv(path, **kwargs)
        return path

    def to_excel(self, file_path: str | Path, **kwargs: Any) -> Path:
        """Export a multi-sheet Excel QC workbook.

        - **Sheet 1 (`Summary`)**: Overall QC statistics table and rule summaries.
        - **Subsequent Sheets**: Detailed error tables for failed rules.

        Sheet names are sanitized to 31 characters with invalid Excel characters removed.

        Parameters
        ----------
        file_path : str or Path
            Target Excel (.xlsx) file path. Parent directories are created automatically.
        **kwargs
            Additional keyword arguments forwarded to ``pandas.ExcelWriter``.

        Returns
        -------
        pathlib.Path
            The resolved target file path.
        """
        path = Path(file_path)
        self._ensure_parent_dir(path)

        summary_df = self.summary()
        overview_data = {
            "Metric": [
                "Overall Status",
                "Total Rules Evaluated",
                "Passed Rules",
                "Failed Rules",
                "Total Errors Detected",
                "Total Checked Records",
            ],
            "Value": [
                "PASS" if self.passed else "FAIL",
                self.total_rules,
                self.passed_rules,
                self.failed_rules,
                self.total_errors,
                self.total_checked_records,
            ],
        }
        overview_df = pd.DataFrame(overview_data)

        seen_sheet_names: set[str] = set()

        with pd.ExcelWriter(path, engine="openpyxl", **kwargs) as writer:
            # Sheet 1: Summary overview + rule table
            overview_df.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
            summary_df.to_excel(
                writer,
                sheet_name="Summary",
                index=False,
                startrow=len(overview_df) + 2,
            )
            seen_sheet_names.add("Summary")

            # Subsequent sheets: one per failed rule with errors
            for r in self._results:
                if not r.passed and not r.errors.empty:
                    q_raw = r.question[0] if isinstance(r.question, list) else r.question
                    base_name = f"{r.rule_name}_{q_raw}"
                    sheet_name = self._sanitize_sheet_name(base_name, seen_sheet_names)
                    seen_sheet_names.add(sheet_name)
                    r.errors.to_excel(writer, sheet_name=sheet_name, index=False)

        return path

    def to_txt(self, file_path: str | Path) -> Path:
        """Export a clean, human-readable summary text file.

        Parameters
        ----------
        file_path : str or Path
            Target TXT file path. Parent directories are created automatically.

        Returns
        -------
        pathlib.Path
            The resolved target file path.
        """
        path = Path(file_path)
        self._ensure_parent_dir(path)

        status_str = "PASS" if self.passed else "FAIL"
        lines = [
            "PANDASDV SURVEY QC REPORT",
            "=========================",
            "",
            f"Overall Status:        {status_str}",
            f"Total Rules Evaluated: {self.total_rules}",
            f"Passed Rules:          {self.passed_rules}",
            f"Failed Rules:          {self.failed_rules}",
            f"Total Errors:          {self.total_errors}",
            f"Total Checked Records: {self.total_checked_records:,}",
            "",
            "VALIDATION SUMMARY",
            "------------------",
        ]

        if not self._results:
            lines.append("No validation rules evaluated.")
        else:
            for r in self._results:
                lines.append(r.summary())

        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def to_markdown(self, file_path: str | Path) -> Path:
        """Export a clean Markdown QC summary document.

        Parameters
        ----------
        file_path : str or Path
            Target Markdown (.md) file path. Parent directories are created automatically.

        Returns
        -------
        pathlib.Path
            The resolved target file path.
        """
        path = Path(file_path)
        self._ensure_parent_dir(path)

        status_badge = "✅ **PASS**" if self.passed else "❌ **FAIL**"
        lines = [
            "# Survey QC Validation Report",
            "",
            f"**Overall Status**: {status_badge}",
            "",
            "## Summary Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| **Total Rules Evaluated** | {self.total_rules} |",
            f"| **Passed Rules** | {self.passed_rules} |",
            f"| **Failed Rules** | {self.failed_rules} |",
            f"| **Total Errors** | {self.total_errors} |",
            f"| **Total Checked Records** | {self.total_checked_records:,} |",
            "",
            "## Rule-by-Rule Breakdown",
            "",
        ]

        summary_df = self.summary()
        if summary_df.empty:
            lines.append("_No rules evaluated._")
        else:
            lines.append("| Rule | Question | Status | Error Count | Checked Records |")
            lines.append("|---|---|---|---|---|")
            for _, row in summary_df.iterrows():
                lines.append(
                    f"| {row['rule']} | {row['question']} | {row['status']} | {row['error_count']} | {row['checked_records']} |"
                )

        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_parent_dir(path: Path) -> None:
        """Create parent directories if they don't exist and path is not in cwd."""
        if path.parent and not path.parent.exists() and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_sheet_name(name: str, existing_names: set[str]) -> str:
        """Sanitize sheet name for Excel compatibility (max 31 chars, no invalid chars)."""
        # Remove invalid Excel characters: : \ / ? * [ ]
        clean = re.sub(r"[:\\/?*\[\]]", "_", name)
        clean = clean.strip() or "Sheet"
        # Truncate to 31 chars max
        base = clean[:31]

        candidate = base
        counter = 1
        while candidate.lower() in {e.lower() for e in existing_names}:
            suffix = f"_{counter}"
            candidate = f"{base[:31 - len(suffix)]}{suffix}"
            counter += 1

        return candidate
