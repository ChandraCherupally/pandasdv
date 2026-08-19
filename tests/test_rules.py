"""
Tests for pandasdv.rules — pure validation logic functions.

All tests use synthetic DataFrames; no files are read.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pandasdv.rules import (
    filter_list,
    validate_grid,
    validate_multi,
    validate_null_check,
    validate_oetext,
    validate_rank,
    validate_sr,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ID = "RespID"


def make_df(**cols: list) -> pd.DataFrame:
    """Build a test DataFrame with a RespID column plus named columns."""
    n = max(len(v) for v in cols.values())
    data = {ID: list(range(1, n + 1))}
    data.update(cols)
    return pd.DataFrame(data)


# ===========================================================================
# SR
# ===========================================================================

class TestSR:
    def test_valid_data_no_errors(self):
        df = make_df(Q1=[1, 2, 3], FILTER=[1, 1, 1])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3], routing_col="FILTER")
        assert errors == []

    def test_invalid_code_detected(self):
        df = make_df(Q1=[1, 99, 3], FILTER=[1, 1, 1])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3], routing_col="FILTER")
        assert len(errors) == 1
        assert errors[0]["record_id"] == 2
        assert errors[0]["error_type"] == "invalid_code"

    def test_missing_value_detected(self):
        df = make_df(Q1=[1, None, 3], FILTER=[1, 1, 1])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3], routing_col="FILTER")
        assert len(errors) == 1
        assert errors[0]["error_type"] == "missing_or_invalid"

    def test_populated_when_routed_out(self):
        df = make_df(Q1=[None, 2, None], FILTER=[0, 1, 0])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3], routing_col="FILTER")
        assert errors == []  # row 2 is valid (routed-in, valid code)

    def test_routed_out_should_be_blank(self):
        df = make_df(Q1=[5, 2, None], FILTER=[0, 1, 0])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3], routing_col="FILTER")
        assert len(errors) == 1
        assert errors[0]["error_type"] == "populated_when_filtered_out"

    def test_ask_all_no_routing(self):
        df = make_df(Q1=[1, 2, 3])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3])
        assert errors == []

    def test_ask_all_invalid(self):
        df = make_df(Q1=[1, 99, 3])
        errors = validate_sr(df, ID, "Q1", [1, 2, 3])
        assert len(errors) == 1


# ===========================================================================
# MULTI
# ===========================================================================

class TestMULTI:
    def test_valid_multi_no_errors(self):
        df = make_df(Q1=[1, 0, 1], Q2=[0, 1, 0], FILTER=[1, 1, 1])
        errors = validate_multi(df, ID, ["Q1", "Q2"], routing_col="FILTER")
        assert errors == []

    def test_nothing_selected(self):
        df = make_df(Q1=[0, 1], Q2=[0, 0], FILTER=[1, 1])
        errors = validate_multi(df, ID, ["Q1", "Q2"], routing_col="FILTER")
        assert any(e["error_type"] == "nothing_selected" for e in errors)

    def test_invalid_punch(self):
        df = make_df(Q1=[1, 5], Q2=[0, 0], FILTER=[1, 1])
        errors = validate_multi(df, ID, ["Q1", "Q2"], routing_col="FILTER")
        assert any(e["error_type"] == "invalid_punch" for e in errors)

    def test_exclusive_violation(self):
        # Both Q1 (regular) and Q_ex (exclusive) selected
        df = make_df(Q1=[1, 0], Q_ex=[1, 1], FILTER=[1, 1])
        errors = validate_multi(df, ID, ["Q1"], exclusive=["Q_ex"], routing_col="FILTER")
        assert any(e["error_type"] == "exclusive_violation" for e in errors)

    def test_populated_when_filtered_out(self):
        df = make_df(Q1=[1, 0], Q2=[0, 0], FILTER=[0, 1])
        errors = validate_multi(df, ID, ["Q1", "Q2"], routing_col="FILTER")
        # row 1 routed out but Q1=1 (not NaN) → error
        assert any(e["error_type"] == "populated_when_filtered_out" for e in errors)

    def test_all_null_routed_out_no_error(self):
        df = make_df(Q1=[None, 1], Q2=[None, 0], FILTER=[0, 1])
        errors = validate_multi(df, ID, ["Q1", "Q2"], routing_col="FILTER")
        assert errors == []


# ===========================================================================
# GRID
# ===========================================================================

class TestGRID:
    def test_valid_grid_no_errors(self):
        df = make_df(G1=[1, 2], G2=[3, 4], FILTER=[1, 1])
        errors = validate_grid(df, ID, ["G1", "G2"], [1, 2, 3, 4, 5], routing_col="FILTER")
        assert errors == []

    def test_invalid_code(self):
        df = make_df(G1=[1, 9], G2=[3, 4], FILTER=[1, 1])
        errors = validate_grid(df, ID, ["G1", "G2"], [1, 2, 3, 4, 5], routing_col="FILTER")
        assert any(e["error_type"] == "invalid_code" for e in errors)

    def test_filter_off_populated(self):
        df = make_df(G1=[3, 2], G2=[None, 4], FILTER=[0, 1])
        errors = validate_grid(df, ID, ["G1", "G2"], [1, 2, 3, 4, 5], routing_col="FILTER")
        # row 1 routed out but G1=3 → error
        assert any(e["error_type"] == "populated_when_filtered_out" for e in errors)

    def test_paired_mode_valid(self):
        df = make_df(G1=[1, None], G2=[2, 3], D1=[1, 0], D2=[1, 1], FILTER=[1, 1])
        errors = validate_grid(df, ID, ["G1", "G2"], [1, 2, 3],
                               routing_col="FILTER", paired_cols=["D1", "D2"])
        assert errors == []

    def test_paired_mode_sub_routed_out_populated(self):
        # D1=0 (sub-filter off) but G1=1 (populated) → error
        df = make_df(G1=[1, None], D1=[0, 0], FILTER=[1, 1])
        errors = validate_grid(df, ID, ["G1"], [1, 2, 3],
                               routing_col="FILTER", paired_cols=["D1"])
        assert any(e["error_type"] == "populated_when_sub_filtered_out" for e in errors)


# ===========================================================================
# RANK_CHECK
# ===========================================================================

class TestRANKCHECK:
    def test_valid_rank(self):
        df = make_df(R1=[1, 2], R2=[2, 1], R3=[3, 3], FILTER=[1, 1])
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, routing_col="FILTER")
        assert errors == []

    def test_invalid_punch_out_of_range(self):
        df = make_df(R1=[1, 99], R2=[2, 2], R3=[3, 3], FILTER=[1, 1])
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, routing_col="FILTER")
        assert any(e["error_type"] == "invalid_punch" for e in errors)

    def test_duplicate_rank(self):
        # Both R1 and R2 have rank 1
        df = make_df(R1=[1, 1], R2=[1, 2], R3=[3, 3], FILTER=[1, 1])
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, routing_col="FILTER")
        assert any(e["error_type"] == "duplicate_rank" for e in errors)

    def test_filter_off_no_values(self):
        df = make_df(R1=[None, 1], R2=[None, 2], R3=[None, 3], FILTER=[0, 1])
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, routing_col="FILTER")
        assert errors == []

    def test_filter_off_populated(self):
        df = make_df(R1=[1, 1], R2=[2, 2], R3=[3, 3], FILTER=[0, 1])
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, routing_col="FILTER")
        assert any(e["error_type"] == "populated_when_filtered_out" for e in errors)

    def test_min_rank_below_threshold(self):
        df = make_df(R1=[1, None], R2=[None, None], R3=[None, None], FILTER=[1, 1])
        # min_rank=2 means max used rank must be >= 2; row 1 has max=1 → error
        errors = validate_rank(df, ID, ["R1", "R2", "R3"], max_rank=3, min_rank=2, routing_col="FILTER")
        assert any(e["error_type"] == "below_minimum_rank" for e in errors)


# ===========================================================================
# OETEXT
# ===========================================================================

class TestOETEXT:
    def test_valid_text(self):
        df = make_df(OE=["hello", "world"], FILTER=[1, 1])
        errors = validate_oetext(df, ID, ["OE"], routing_col="FILTER")
        assert errors == []

    def test_missing_text_routed_in(self):
        df = make_df(OE=["hello", ""], FILTER=[1, 1])
        errors = validate_oetext(df, ID, ["OE"], routing_col="FILTER")
        assert len(errors) == 1
        assert errors[0]["error_type"] == "missing_response"

    def test_populated_when_filtered_out(self):
        df = make_df(OE=["hi", ""], FILTER=[0, 1])
        errors = validate_oetext(df, ID, ["OE"], routing_col="FILTER")
        assert any(e["error_type"] == "populated_when_filtered_out" for e in errors)

    def test_ask_all_no_filter(self):
        df = make_df(OE=["", "world"])
        errors = validate_oetext(df, ID, ["OE"])
        assert len(errors) == 1


# ===========================================================================
# NULL_CHECK
# ===========================================================================

class TestNULLCHECK:
    def test_all_null_no_errors(self):
        df = make_df(Q1=[None, None])
        errors = validate_null_check(df, ID, ["Q1"])
        assert errors == []

    def test_populated_numeric_detected(self):
        df = make_df(Q1=[None, 5.0])
        errors = validate_null_check(df, ID, ["Q1"])
        assert len(errors) == 1
        assert errors[0]["error_type"] == "unexpected_value"

    def test_blank_string_ok(self):
        df = make_df(Q1=["", ""])
        errors = validate_null_check(df, ID, ["Q1"])
        assert errors == []

    def test_non_blank_string_detected(self):
        df = make_df(Q1=["", "some text"])
        errors = validate_null_check(df, ID, ["Q1"])
        assert len(errors) == 1


# ===========================================================================
# FILTER_LIST
# ===========================================================================

class TestFilterList:
    def test_returns_filtered_rows(self):
        df = make_df(Q1=[1, None, 3])
        result = filter_list(df, df["Q1"].isna(), ["RespID", "Q1"])
        assert len(result) == 1
        assert result.iloc[0]["RespID"] == 2

    def test_no_match_returns_empty(self):
        df = make_df(Q1=[1, 2, 3])
        result = filter_list(df, df["Q1"].isna())
        assert result.empty
