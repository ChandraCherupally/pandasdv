"""
SurveyValidator — the main class-based API for pandasdv.

Usage::

    import pandas as pd
    from pandasdv import SurveyValidator

    df = pd.read_csv("survey.csv")
    validator = SurveyValidator(df)

    result = validator.sr("Q1", valid_values=[1, 2, 3])
    print(result.summary())
    print(result.errors)
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .results import ValidationResult, build_result
from .rules import (
    filter_list,
    validate_grid,
    validate_multi,
    validate_null_check,
    validate_oetext,
    validate_rank,
    validate_sr,
)


class SurveyValidator:
    """Validates survey data against common questionnaire rules.

    Parameters
    ----------
    df : pd.DataFrame
        The survey dataset.  Must not be empty.
    id_col : str, optional
        Name of the respondent-ID column.  Defaults to the first column.

    Examples
    --------
    >>> validator = SurveyValidator(df)
    >>> result = validator.sr("Q1", valid_values=[1, 2, 3])
    >>> print(result.summary())
    """

    def __init__(self, df: pd.DataFrame, id_col: str | None = None) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty — nothing to validate.")
        self._df = df
        self._id_col: str = id_col if id_col is not None else df.columns[0]
        if self._id_col not in df.columns:
            raise ValueError(f"id_col '{self._id_col}' not found in DataFrame columns.")

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def df(self) -> pd.DataFrame:
        """The underlying DataFrame (read-only reference)."""
        return self._df

    @property
    def id_col(self) -> str:
        """Name of the respondent-ID column."""
        return self._id_col

    # ------------------------------------------------------------------
    # Validation methods
    # ------------------------------------------------------------------

    def sr(
        self,
        question: str,
        valid_values: list[Any],
        routing_column: str | None = None,
        display_columns: list[str] | None = None,
    ) -> ValidationResult:
        """Validate a **single-response** question.

        Parameters
        ----------
        question : str
            Column name of the question variable.
        valid_values : list
            Allowed response codes (e.g. ``[1, 2, 3, 97]``).
        routing_column : str, optional
            Name of a pre-built 0/1 filter column.  When ``None`` (default)
            every row is treated as routed-in (ask-all question).
        display_columns : list[str], optional
            Not used for validation logic; stored in ``metadata`` so callers
            can reference them when formatting output.

        Returns
        -------
        ValidationResult
        """
        self._require_columns([question], routing_column)
        checked = self._checked_count(routing_column)

        errors = validate_sr(
            df=self._df,
            id_col=self._id_col,
            question=question,
            valid_values=valid_values,
            routing_col=routing_column,
        )
        return build_result(
            rule_name="SR",
            question=question,
            error_rows=errors,
            checked_records=checked,
            metadata={
                "valid_values": valid_values,
                "routing_column": routing_column,
                "display_columns": display_columns,
            },
        )

    def multi(
        self,
        questions: list[str],
        exclusive: list[str] | None = None,
        routing_column: str | None = None,
        display_columns: list[str] | None = None,
    ) -> ValidationResult:
        """Validate a **multiple-response** question battery.

        Parameters
        ----------
        questions : list[str]
            Column names of the main response variables (0/1 coded).
        exclusive : list[str], optional
            Column name(s) of exclusive-option variables (e.g. "None of above").
        routing_column : str, optional
            Pre-built 0/1 filter column.
        display_columns : list[str], optional
            Stored in metadata for formatting.

        Returns
        -------
        ValidationResult
        """
        exclusive = exclusive or []
        self._require_columns(questions + exclusive, routing_column)
        checked = self._checked_count(routing_column)

        errors = validate_multi(
            df=self._df,
            id_col=self._id_col,
            questions=questions,
            exclusive=exclusive,
            routing_col=routing_column,
        )
        return build_result(
            rule_name="MULTI",
            question=questions,
            error_rows=errors,
            checked_records=checked,
            metadata={
                "exclusive": exclusive,
                "routing_column": routing_column,
                "display_columns": display_columns,
            },
        )

    def grid(
        self,
        questions: list[str],
        valid_codes: list[Any],
        routing_column: str | None = None,
        paired_cols: list[str] | None = None,
        display_columns: list[str] | None = None,
    ) -> ValidationResult:
        """Validate a **grid / matrix** question.

        Parameters
        ----------
        questions : list[str]
            Grid row column names.
        valid_codes : list
            Allowed response codes for each grid cell.
        routing_column : str, optional
            Outer 0/1 filter column.
        paired_cols : list[str], optional
            Per-row sub-routing columns (same length as *questions*).
            When provided, uses paired mode — each row has its own ask/not-ask
            control variable.
        display_columns : list[str], optional
            Stored in metadata.

        Returns
        -------
        ValidationResult
        """
        all_cols = questions + (paired_cols or [])
        self._require_columns(all_cols, routing_column)
        if paired_cols and len(paired_cols) != len(questions):
            raise ValueError("paired_cols must be the same length as questions.")
        checked = self._checked_count(routing_column)

        errors = validate_grid(
            df=self._df,
            id_col=self._id_col,
            questions=questions,
            valid_codes=valid_codes,
            routing_col=routing_column,
            paired_cols=paired_cols,
        )
        return build_result(
            rule_name="GRID",
            question=questions,
            error_rows=errors,
            checked_records=checked,
            metadata={
                "valid_codes": valid_codes,
                "paired_cols": paired_cols,
                "routing_column": routing_column,
                "display_columns": display_columns,
            },
        )

    def rank_check(
        self,
        questions: list[str],
        max_rank: int,
        min_rank: int | None = None,
        routing_column: str | None = None,
    ) -> ValidationResult:
        """Validate a **rank-order** question.

        Parameters
        ----------
        questions : list[str]
            One column per rank slot (e.g. ``["Q10_r1", "Q10_r2", "Q10_r3"]``).
        max_rank : int
            Highest rank value allowed (e.g. 3 means ranks 1, 2, 3).
        min_rank : int, optional
            When set, respondents may use fewer ranks but at least this many.
        routing_column : str, optional
            Pre-built 0/1 filter column.

        Returns
        -------
        ValidationResult
        """
        self._require_columns(questions, routing_column)
        checked = self._checked_count(routing_column)

        errors = validate_rank(
            df=self._df,
            id_col=self._id_col,
            questions=questions,
            max_rank=max_rank,
            min_rank=min_rank,
            routing_col=routing_column,
        )
        return build_result(
            rule_name="RANK_CHECK",
            question=questions,
            error_rows=errors,
            checked_records=checked,
            metadata={
                "max_rank": max_rank,
                "min_rank": min_rank,
                "routing_column": routing_column,
            },
        )

    def oe_text(
        self,
        questions: list[str] | str,
        routing_column: str | None = None,
        display_columns: list[str] | None = None,
    ) -> ValidationResult:
        """Validate **open-ended text** questions.

        Parameters
        ----------
        questions : str or list[str]
            Column name(s) of text response variables.
        routing_column : str, optional
            Pre-built 0/1 filter column.
        display_columns : list[str], optional
            Stored in metadata.

        Returns
        -------
        ValidationResult
        """
        if isinstance(questions, str):
            questions = [questions]
        self._require_columns(questions, routing_column)
        checked = self._checked_count(routing_column)

        errors = validate_oetext(
            df=self._df,
            id_col=self._id_col,
            questions=questions,
            routing_col=routing_column,
        )
        return build_result(
            rule_name="OETEXT",
            question=questions,
            error_rows=errors,
            checked_records=checked,
            metadata={
                "routing_column": routing_column,
                "display_columns": display_columns,
            },
        )

    def null_check(
        self,
        questions: list[str] | str,
    ) -> ValidationResult:
        """Check for non-null / non-blank values in columns expected to be empty.

        Parameters
        ----------
        questions : str or list[str]
            Column name(s) to inspect.

        Returns
        -------
        ValidationResult
        """
        if isinstance(questions, str):
            questions = [questions]
        self._require_columns(questions)
        checked = len(self._df)

        errors = validate_null_check(
            df=self._df,
            id_col=self._id_col,
            questions=questions,
        )
        return build_result(
            rule_name="NULL_CHECK",
            question=questions,
            error_rows=errors,
            checked_records=checked,
        )

    def custom_check(
        self,
        condition: pd.Series,
        question: str | list[str] = "CUSTOM",
        rule_name: str = "LOGIC_CHECK",
        error_type: str = "condition_failed",
        expected: Any = None,
        display_columns: list[str] | None = None,
    ) -> ValidationResult:
        """Evaluate a custom boolean error condition and return a :class:`ValidationResult`.

        Parameters
        ----------
        condition : pd.Series of bool
            Boolean mask where ``True`` marks an error record.
        question : str or list[str], default "CUSTOM"
            Identifier or question name for the check.
        rule_name : str, default "LOGIC_CHECK"
            Name of the rule category.
        error_type : str, default "condition_failed"
            Diagnostic error label.
        expected : Any, optional
            Human-readable description of expected criteria.
        display_columns : list[str], optional
            Columns to capture in the actual value diagnostic payload.

        Returns
        -------
        ValidationResult
        """
        error_rows: list[dict[str, Any]] = []
        bad_df = self._df[condition]

        q_name = question if isinstance(question, str) else question[0]
        cols = display_columns or ([question] if isinstance(question, str) and question in self._df.columns else [])

        for _, row in bad_df.iterrows():
            if cols:
                actual = row[cols[0]] if len(cols) == 1 else {c: row[c] for c in cols if c in row}
            else:
                actual = row[q_name] if q_name in row else None

            error_rows.append({
                "record_id": row[self._id_col],
                "question": q_name,
                "rule": rule_name,
                "error_type": error_type,
                "actual": actual,
                "expected": expected,
            })

        return build_result(
            rule_name=rule_name,
            question=question,
            error_rows=error_rows,
            checked_records=len(self._df),
            metadata={
                "display_columns": display_columns,
                "expected": expected,
            },
        )

    def filter_list(
        self,
        condition: pd.Series,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return rows matching *condition*, analogous to the original ``FLT_LIST``.

        Parameters
        ----------
        condition : pd.Series of bool
            Boolean mask aligned to :attr:`df`.
        columns : list[str], optional
            Subset of columns to include in the result.  Defaults to all.

        Returns
        -------
        pd.DataFrame
            Filtered rows, reset index.
        """
        return filter_list(self._df, condition, columns)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_columns(
        self,
        columns: list[str],
        routing_col: str | None = None,
    ) -> None:
        missing = [c for c in columns if c not in self._df.columns]
        if routing_col and routing_col not in self._df.columns:
            missing.append(routing_col)
        if missing:
            raise ValueError(f"Column(s) not found in DataFrame: {missing}")

    def _checked_count(self, routing_col: str | None) -> int:
        if routing_col and routing_col in self._df.columns:
            return int((self._df[routing_col] == 1).sum())
        return len(self._df)
