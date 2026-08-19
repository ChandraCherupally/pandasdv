"""
ChunkProcessor — validates large CSV datasets without loading the entire file.

Design
------
The processor reads a CSV file in fixed-size chunks using
``pandas.read_csv(..., chunksize=N)``.  For each chunk it creates a fresh
:class:`~pandasdv.validator.SurveyValidator`, runs the requested rules, and
collects only the error rows.  The chunk is then released from memory.

At the end, per-rule error DataFrames from all chunks are concatenated and
wrapped in :class:`~pandasdv.results.ValidationResult` objects.

Cross-chunk checks
------------------
Some validations cannot be done independently per-chunk:

- **Duplicate respondent IDs**: a record-ID seen in chunk 1 might be
  duplicated in chunk 5.  The processor tracks a ``Counter`` of seen IDs
  across chunks using O(unique IDs) memory rather than storing entire records.

Chunk-local checks (safe to do per-chunk without aggregation):
- SR, MULTI, GRID, RANK_CHECK, OETEXT, NULL_CHECK routing errors

Full-dataset checks (performed by loading entire file, currently none):
- None required in this version.

SPSS limitation
---------------
``pandas.read_spss`` and ``pyreadstat.read_sav`` do not support true
streaming chunk reads in the same way as ``pd.read_csv``.
``pyreadstat.read_file_in_chunks`` *does* exist (confirmed in v1.3.1) but
requires the caller to manage a reader context that is tightly coupled to
pyreadstat's internal row-group model.

To keep the implementation simple and correct, SPSS files are loaded in full
and then processed in a single pass.  CSV is the recommended format for
large datasets with chunk processing.

Rule definition format
----------------------
Rules are plain dicts::

    rules = [
        {
            "name": "SR",
            "params": {
                "question": "Q1",
                "valid_values": [1, 2, 3],
                "routing_column": "QFILTER",
            }
        },
        {
            "name": "MULTI",
            "params": {
                "questions": ["Q2_1", "Q2_2"],
                "exclusive": ["Q2_99"],
            }
        },
    ]

Supported ``name`` values: ``"SR"``, ``"MULTI"``, ``"GRID"``,
``"RANK_CHECK"``, ``"OETEXT"``, ``"NULL_CHECK"``.

Example
-------
::

    from pandasdv import ChunkProcessor

    processor = ChunkProcessor(chunk_size=50_000)
    results = processor.process_csv("large_survey.csv", rules=rules)

    for r in results:
        print(r.summary())
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .results import ValidationResult, build_result
from .validator import SurveyValidator

# ---------------------------------------------------------------------------
# Supported rule names → SurveyValidator method mapping
# ---------------------------------------------------------------------------

_RULE_METHOD: dict[str, str] = {
    "SR": "sr",
    "MULTI": "multi",
    "GRID": "grid",
    "RANK_CHECK": "rank_check",
    "OETEXT": "oe_text",
    "NULL_CHECK": "null_check",
}


class ChunkProcessor:
    """Process large CSV files chunk-by-chunk without loading all data at once.

    Parameters
    ----------
    chunk_size : int
        Number of rows per chunk.  Defaults to 50 000.

    Examples
    --------
    ::

        processor = ChunkProcessor(chunk_size=10_000)
        results = processor.process_csv(
            "survey.csv",
            rules=[
                {"name": "SR", "params": {"question": "Q1", "valid_values": [1, 2]}},
            ],
        )
        for r in results:
            print(r.summary())
    """

    def __init__(self, chunk_size: int = 50_000) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        self.chunk_size = chunk_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_csv(
        self,
        file_path: str | Path,
        rules: list[dict[str, Any]],
        id_col: str | None = None,
        **csv_kwargs: Any,
    ) -> list[ValidationResult]:
        """Validate a CSV file using chunk-based processing.

        Parameters
        ----------
        file_path : str or Path
            Path to the CSV file.
        rules : list[dict]
            Rule definitions.  Each dict has ``"name"`` and ``"params"`` keys.
        id_col : str, optional
            Respondent-ID column name.  Defaults to the first column.
        **csv_kwargs
            Extra keyword arguments forwarded to ``pandas.read_csv``.

        Returns
        -------
        list[ValidationResult]
            One result per rule, with errors aggregated across all chunks.
        """
        self._validate_rules(rules)
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Accumulators — keyed by rule index to preserve ordering
        error_rows_by_rule: dict[int, list[dict[str, Any]]] = {i: [] for i in range(len(rules))}
        checked_by_rule: dict[int, int] = {i: 0 for i in range(len(rules))}
        id_counter: Counter[Any] = Counter()

        # Determine id_col from first chunk header if not supplied
        resolved_id_col: str | None = id_col

        chunks = pd.read_csv(file_path, chunksize=self.chunk_size, **csv_kwargs)
        for chunk in chunks:
            if resolved_id_col is None:
                resolved_id_col = chunk.columns[0]

            # Cross-chunk: count IDs
            id_counter.update(chunk[resolved_id_col].tolist())

            validator = SurveyValidator(chunk, id_col=resolved_id_col)
            for i, rule in enumerate(rules):
                result = self._run_rule(validator, rule)
                error_rows_by_rule[i].extend(result.errors.to_dict("records"))
                checked_by_rule[i] += result.checked_records

        # Detect cross-chunk duplicate IDs
        duplicate_ids = {rid for rid, count in id_counter.items() if count > 1}

        # Build aggregated results
        aggregated: list[ValidationResult] = []
        for i, rule in enumerate(rules):
            rule_name = rule["name"]
            params = rule.get("params", {})
            question = params.get("question") or params.get("questions", "unknown")
            result = build_result(
                rule_name=rule_name,
                question=question,
                error_rows=error_rows_by_rule[i],
                checked_records=checked_by_rule[i],
                metadata={"params": params, "chunk_size": self.chunk_size},
            )
            aggregated.append(result)

        # Append duplicate-ID result if any found
        if duplicate_ids:
            dup_errors = [
                {
                    "record_id": rid,
                    "question": resolved_id_col or "ID",
                    "rule": "DUPLICATE_ID",
                    "error_type": "duplicate_id",
                    "actual": rid,
                    "expected": "unique",
                }
                for rid in sorted(duplicate_ids, key=str)
            ]
            aggregated.append(
                build_result(
                    rule_name="DUPLICATE_ID",
                    question=resolved_id_col or "ID",
                    error_rows=dup_errors,
                    checked_records=sum(id_counter.values()),
                    metadata={"duplicate_count": len(duplicate_ids)},
                )
            )

        return aggregated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_rules(rules: list[dict[str, Any]]) -> None:
        if not rules:
            raise ValueError("rules list must not be empty.")
        for rule in rules:
            name = rule.get("name")
            if name not in _RULE_METHOD:
                raise ValueError(
                    f"Unknown rule name '{name}'. "
                    f"Valid names: {sorted(_RULE_METHOD)}"
                )

    @staticmethod
    def _run_rule(
        validator: SurveyValidator,
        rule: dict[str, Any],
    ) -> ValidationResult:
        """Dispatch a rule dict to the appropriate SurveyValidator method."""
        method_name = _RULE_METHOD[rule["name"]]
        method = getattr(validator, method_name)
        params = rule.get("params", {})
        return method(**params)
