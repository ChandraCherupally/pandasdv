"""
Pure validation logic for survey data quality checks.

Each function accepts a DataFrame and returns a list of error-row dicts.
No printing, no global state, no DataFrame mutation.

All functions accept ``id_col`` (the respondent-ID column name).  When
``routing_col`` is supplied, only rows where ``df[routing_col] == 1`` are
treated as "routed in" (asked).  Rows where ``routing_col != 1`` are
"routed out" and checked for unexpected population.

When ``routing_col`` is None every row is treated as routed-in (ask-all).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .results import _make_error_row

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RULE_SR = "SR"
_RULE_MULTI = "MULTI"
_RULE_GRID = "GRID"
_RULE_RANK = "RANK_CHECK"
_RULE_OETEXT = "OETEXT"
_RULE_NULL = "NULL_CHECK"


def _routing_masks(
    df: pd.DataFrame, routing_col: str | None
) -> tuple[pd.Series, pd.Series]:
    """Return (routed_in_mask, routed_out_mask) boolean Series.

    When *routing_col* is None every row is considered routed-in.
    """
    if routing_col is None or routing_col not in df.columns:
        routed_in = pd.Series(True, index=df.index)
        routed_out = pd.Series(False, index=df.index)
    else:
        routed_in = df[routing_col] == 1
        routed_out = df[routing_col] != 1
    return routed_in, routed_out


# ---------------------------------------------------------------------------
# SR — Single Response
# ---------------------------------------------------------------------------

def validate_sr(
    df: pd.DataFrame,
    id_col: str,
    question: str,
    valid_values: list[Any],
    routing_col: str | None = None,
) -> list[dict[str, Any]]:
    """Validate a single-response question.

    Checks:
    - Routed-in rows: value must be in *valid_values* (missing = error)
    - Routed-out rows: value must be null/blank (populated = error)
    """
    errors: list[dict[str, Any]] = []
    routed_in, routed_out = _routing_masks(df, routing_col)

    # Routed-in: missing or invalid code
    mask_bad_in = routed_in & (df[question].isna() | ~df[question].isin(valid_values))
    for _, row in df[mask_bad_in].iterrows():
        actual = row[question]
        errors.append(_make_error_row(
            record_id=row[id_col],
            question=question,
            rule=_RULE_SR,
            error_type="missing_or_invalid" if pd.isna(actual) else "invalid_code",
            actual=actual,
            expected=f"one of {valid_values}",
        ))

    # Routed-out: value populated when it should be blank
    mask_bad_out = routed_out & df[question].notna()
    for _, row in df[mask_bad_out].iterrows():
        errors.append(_make_error_row(
            record_id=row[id_col],
            question=question,
            rule=_RULE_SR,
            error_type="populated_when_filtered_out",
            actual=row[question],
            expected=None,
        ))

    return errors


# ---------------------------------------------------------------------------
# MULTI — Multiple Response
# ---------------------------------------------------------------------------

def validate_multi(
    df: pd.DataFrame,
    id_col: str,
    questions: list[str],
    exclusive: list[str] | None = None,
    routing_col: str | None = None,
) -> list[dict[str, Any]]:
    """Validate a multiple-response question battery.

    Checks (routed-in rows):
    - Nothing selected (all variables are 0 or not 1)
    - Invalid punches (values other than 0 or 1)
    - Exclusive code selected together with other codes

    Checks (routed-out rows):
    - Any variable is not null
    """
    errors: list[dict[str, Any]] = []
    exclusive = exclusive or []
    all_vars = questions + exclusive
    n_vars = len(all_vars)

    routed_in, routed_out = _routing_masks(df, routing_col)

    in_df = df[routed_in]
    out_df = df[routed_out]

    # --- Routed-in checks ---------------------------------------------------

    count_selected = in_df[all_vars].eq(1).sum(axis=1)
    count_valid_punches = in_df[all_vars].isin([0, 1]).sum(axis=1)

    # Nothing selected
    nothing_selected = count_selected == 0
    for _, row in in_df[nothing_selected].iterrows():
        errors.append(_make_error_row(
            record_id=row[id_col],
            question=questions[0],
            rule=_RULE_MULTI,
            error_type="nothing_selected",
            actual={v: row[v] for v in all_vars},
            expected="at least one variable == 1",
        ))

    # Invalid punches (any value not 0 or 1)
    invalid_punches = count_valid_punches != n_vars
    for _, row in in_df[invalid_punches].iterrows():
        bad = {v: row[v] for v in all_vars if row[v] not in (0, 1) and not pd.isna(row[v])}
        errors.append(_make_error_row(
            record_id=row[id_col],
            question=questions[0],
            rule=_RULE_MULTI,
            error_type="invalid_punch",
            actual=bad,
            expected="values must be 0 or 1",
        ))

    # Exclusive code violations
    if exclusive:
        count_exclusive = in_df[exclusive].eq(1).sum(axis=1)
        # Exclusive selected AND something else selected, OR multiple exclusive selected
        exclusive_violation = ((count_selected > 1) & (count_exclusive == 1)) | (count_exclusive > 1)
        for _, row in in_df[exclusive_violation].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=questions[0],
                rule=_RULE_MULTI,
                error_type="exclusive_violation",
                actual={v: row[v] for v in all_vars},
                expected=f"exclusive var(s) {exclusive} must not be selected with others",
            ))

    # --- Routed-out check ---------------------------------------------------
    if not out_df.empty:
        populated_out = out_df[all_vars].isna().sum(axis=1) != n_vars
        for _, row in out_df[populated_out].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=questions[0],
                rule=_RULE_MULTI,
                error_type="populated_when_filtered_out",
                actual={v: row[v] for v in all_vars if not pd.isna(row[v])},
                expected=None,
            ))

    return errors


# ---------------------------------------------------------------------------
# GRID — Grid / Matrix Question
# ---------------------------------------------------------------------------

def validate_grid(
    df: pd.DataFrame,
    id_col: str,
    questions: list[str],
    valid_codes: list[Any],
    routing_col: str | None = None,
    paired_cols: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate a grid / matrix question.

    Two modes:

    1. **Simple** (``paired_cols`` is None): every question in *questions*
       must contain a value in *valid_codes* when routed-in; must be null
       when routed-out.

    2. **Paired** (``paired_cols`` provided): each element of *questions*
       has its own sub-routing column in *paired_cols*.  Within the
       outer routing filter, the sub-routing column determines whether that
       specific grid row is asked.

    Preserves the exact semantics of the original ``GRID`` function.
    """
    errors: list[dict[str, Any]] = []
    routed_in, routed_out = _routing_masks(df, routing_col)

    in_df = df[routed_in]
    out_df = df[routed_out]

    if not paired_cols:
        # --- Simple mode ---
        for q in questions:
            # Invalid code (routed-in)
            bad_in = in_df[q].isna() | ~in_df[q].isin(valid_codes)
            for _, row in in_df[bad_in].iterrows():
                errors.append(_make_error_row(
                    record_id=row[id_col],
                    question=q,
                    rule=_RULE_GRID,
                    error_type="invalid_code",
                    actual=row[q],
                    expected=f"one of {valid_codes}",
                ))

            # Populated when routed-out
            bad_out = out_df[q].notna()
            for _, row in out_df[bad_out].iterrows():
                errors.append(_make_error_row(
                    record_id=row[id_col],
                    question=q,
                    rule=_RULE_GRID,
                    error_type="populated_when_filtered_out",
                    actual=row[q],
                    expected=None,
                ))

    else:
        # --- Paired mode: per-column sub-routing ---
        for q, d_col in zip(questions, paired_cols):
            # Within routed-in rows, sub-filter determines ask/not-ask
            sub_in = in_df[d_col] == 1
            sub_out = in_df[d_col] != 1

            # Sub-routed in: must have valid code
            bad_code = (in_df[sub_in][q].isna()) | (~in_df[sub_in][q].isin(valid_codes))
            for _, row in in_df[sub_in][bad_code].iterrows():
                errors.append(_make_error_row(
                    record_id=row[id_col],
                    question=q,
                    rule=_RULE_GRID,
                    error_type="invalid_code",
                    actual=row[q],
                    expected=f"one of {valid_codes}",
                    paired_col=d_col,
                ))

            # Sub-routed out: must be null
            populated_sub_out = in_df[sub_out][q].notna()
            for _, row in in_df[sub_out][populated_sub_out].iterrows():
                errors.append(_make_error_row(
                    record_id=row[id_col],
                    question=q,
                    rule=_RULE_GRID,
                    error_type="populated_when_sub_filtered_out",
                    actual=row[q],
                    expected=None,
                    paired_col=d_col,
                ))

            # Outer routed-out: must be null
            bad_out = out_df[q].notna()
            for _, row in out_df[bad_out].iterrows():
                errors.append(_make_error_row(
                    record_id=row[id_col],
                    question=q,
                    rule=_RULE_GRID,
                    error_type="populated_when_filtered_out",
                    actual=row[q],
                    expected=None,
                    paired_col=d_col,
                ))

    return errors


# ---------------------------------------------------------------------------
# RANK_CHECK — Rank Order
# ---------------------------------------------------------------------------

def validate_rank(
    df: pd.DataFrame,
    id_col: str,
    questions: list[str],
    max_rank: int,
    min_rank: int | None = None,
    routing_col: str | None = None,
) -> list[dict[str, Any]]:
    """Validate a rank-order question.

    Checks (routed-in rows):
    - Invalid punches: ranks outside [1, max_rank] or wrong number used
    - Minimum rank: highest rank used < min_rank (only when min_rank set)
    - Duplicate ranks: the same rank value appears more than once

    Checks (routed-out rows):
    - Any variable is not null

    NOTE: The "invalid punch" logic with ``min_rank`` uses the same
    semantics as the original RANK_CHECK: when ``min_rank`` is given, the
    respondent may use fewer ranks (at least 1 up to max_rank), so the
    check is based on the count of valid ranks used rather than requiring
    exactly ``max_rank`` filled slots.
    """
    errors: list[dict[str, Any]] = []
    n_vars = len(questions)
    routed_in, routed_out = _routing_masks(df, routing_col)

    in_df = df[routed_in].copy()
    out_df = df[routed_out]

    valid_mask = (in_df[questions] >= 1) & (in_df[questions] <= max_rank)
    q_count = valid_mask.sum(axis=1)

    if min_rank is not None:
        q_maxr = in_df[questions].max(axis=1)

        # Minimum rank check: highest rank used < min_rank
        min_rank_fail = q_maxr < min_rank
        for _, row in in_df[min_rank_fail].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=questions[0],
                rule=_RULE_RANK,
                error_type="below_minimum_rank",
                actual=int(q_maxr[row.name]) if not pd.isna(q_maxr[row.name]) else None,
                expected=f">= {min_rank}",
            ))

        # Invalid punches (with min_rank): number of valid-range slots used
        # must equal q_count, and no unexpected non-null values outside range
        invalid_punch = (
            (in_df[questions].isna().sum(axis=1) != (n_vars - q_count))
            | (q_count == 0)
        )
    else:
        # Invalid punches (fixed ranks): must have exactly max_rank valid ranks,
        # rest must be null
        invalid_punch = (
            (q_count != max_rank)
            | (in_df[questions].isna().sum(axis=1) != (n_vars - max_rank))
        )

    for _, row in in_df[invalid_punch].iterrows():
        errors.append(_make_error_row(
            record_id=row[id_col],
            question=questions[0],
            rule=_RULE_RANK,
            error_type="invalid_punch",
            actual={q: row[q] for q in questions},
            expected=f"ranks 1–{max_rank}, exactly {max_rank if min_rank is None else 'up to ' + str(max_rank)} used",
        ))

    # Duplicate ranks
    for rank_val in range(1, max_rank + 1):
        rank_count = (in_df[questions] == rank_val).sum(axis=1)
        if min_rank is not None:
            dup_mask = (rank_val <= q_count) & (rank_count != 1)
        else:
            dup_mask = rank_count != 1
        for _, row in in_df[dup_mask].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=questions[0],
                rule=_RULE_RANK,
                error_type="duplicate_rank",
                actual=f"rank {rank_val} appears {int(rank_count[row.name])} time(s)",
                expected=f"rank {rank_val} appears exactly once",
            ))

    # Routed-out: must all be null
    if not out_df.empty:
        populated_out = out_df[questions].isna().sum(axis=1) != n_vars
        for _, row in out_df[populated_out].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=questions[0],
                rule=_RULE_RANK,
                error_type="populated_when_filtered_out",
                actual={q: row[q] for q in questions if not pd.isna(row[q])},
                expected=None,
            ))

    return errors


# ---------------------------------------------------------------------------
# OETEXT — Open-Ended Text
# ---------------------------------------------------------------------------

def validate_oetext(
    df: pd.DataFrame,
    id_col: str,
    questions: list[str],
    routing_col: str | None = None,
) -> list[dict[str, Any]]:
    """Validate open-ended text questions.

    Checks:
    - Routed-in rows: value must not be empty string or null
    - Routed-out rows: value must be empty string (the original behaviour
      treats '' as the expected blank state)
    """
    errors: list[dict[str, Any]] = []
    routed_in, routed_out = _routing_masks(df, routing_col)

    in_df = df[routed_in]
    out_df = df[routed_out]

    for q in questions:
        # Routed-in: empty string = error (matches original: df[i] == '')
        bad_in = in_df[q].eq("")
        for _, row in in_df[bad_in].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=q,
                rule=_RULE_OETEXT,
                error_type="missing_response",
                actual="",
                expected="non-empty text",
            ))

        # Routed-out: non-empty value = error
        bad_out = out_df[q].ne("") & out_df[q].notna()
        for _, row in out_df[bad_out].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=q,
                rule=_RULE_OETEXT,
                error_type="populated_when_filtered_out",
                actual=row[q],
                expected="empty string",
            ))

    return errors


# ---------------------------------------------------------------------------
# NULL_CHECK — Null / Blank Detection
# ---------------------------------------------------------------------------

def validate_null_check(
    df: pd.DataFrame,
    id_col: str,
    questions: list[str],
) -> list[dict[str, Any]]:
    """Identify populated (non-null / non-blank) values where null is expected.

    For numeric columns: reports any non-null value.
    For string/object columns: reports any non-empty-string value.

    This mirrors the original NULL_CHECK behaviour exactly.
    """
    errors: list[dict[str, Any]] = []

    for q in questions:
        # Treat string/object columns the same way: blank string ("") is OK.
        # pandas >=3.0 uses `str` dtype; earlier versions use `object`.
        if df[q].dtype == object or pd.api.types.is_string_dtype(df[q]):
            bad = df[q].ne("") & df[q].notna()
        else:
            bad = df[q].notna()

        for _, row in df[bad].iterrows():
            errors.append(_make_error_row(
                record_id=row[id_col],
                question=q,
                rule=_RULE_NULL,
                error_type="unexpected_value",
                actual=row[q],
                expected="null or blank",
            ))

    return errors


# ---------------------------------------------------------------------------
# FILTER_LIST — ad-hoc filtered listing
# ---------------------------------------------------------------------------

def filter_list(
    df: pd.DataFrame,
    condition: pd.Series,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Return filtered rows of *df* matching *condition*.

    Equivalent to the original ``FLT_LIST`` but returns a DataFrame instead
    of printing.  The caller decides how to display or log the result.
    """
    cols = columns if columns is not None else df.columns.tolist()
    filtered = df.loc[condition, cols].reset_index(drop=True)
    return filtered
