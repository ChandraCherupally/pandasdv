"""
Tests for SurveyValidator — class-based API.

Verifies that:
- SurveyValidator accepts a DataFrame (no global state needed)
- Each method returns a ValidationResult with correct fields
- Empty DataFrame raises ValueError
- Missing columns raise ValueError
- result.summary() returns a string
- result.errors is a pd.DataFrame
"""

from __future__ import annotations

import pandas as pd
import pytest

from pandasdv import SurveyValidator, ValidationResult


ID = "RespID"


def make_df(**cols: list) -> pd.DataFrame:
    n = max(len(v) for v in cols.values())
    data = {ID: list(range(1, n + 1))}
    data.update(cols)
    return pd.DataFrame(data)


# ===========================================================================
# Initialization
# ===========================================================================

class TestInit:
    def test_accepts_valid_df(self):
        df = make_df(Q1=[1, 2])
        v = SurveyValidator(df)
        assert v.id_col == ID

    def test_empty_df_raises(self):
        with pytest.raises(ValueError, match="empty"):
            SurveyValidator(pd.DataFrame())

    def test_custom_id_col(self):
        df = pd.DataFrame({"CID": [1, 2], "Q1": [1, 2]})
        v = SurveyValidator(df, id_col="CID")
        assert v.id_col == "CID"

    def test_invalid_id_col_raises(self):
        df = make_df(Q1=[1, 2])
        with pytest.raises(ValueError, match="id_col"):
            SurveyValidator(df, id_col="NonExistent")

    def test_df_not_mutated(self):
        df = make_df(Q1=[1, 2, 3])
        original_cols = list(df.columns)
        v = SurveyValidator(df)
        v.sr("Q1", valid_values=[1, 2, 3])
        assert list(df.columns) == original_cols


# ===========================================================================
# ValidationResult structure
# ===========================================================================

class TestValidationResultStructure:
    def test_result_is_ValidationResult(self):
        df = make_df(Q1=[1, 2])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert isinstance(result, ValidationResult)

    def test_result_has_passed_true(self):
        df = make_df(Q1=[1, 2])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert result.passed is True

    def test_result_has_passed_false(self):
        df = make_df(Q1=[1, 99])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert result.passed is False

    def test_error_count_correct(self):
        df = make_df(Q1=[1, 99, None])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert result.error_count == 2

    def test_errors_is_dataframe(self):
        df = make_df(Q1=[1, 99])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert isinstance(result.errors, pd.DataFrame)

    def test_errors_empty_on_pass(self):
        df = make_df(Q1=[1, 2])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert result.errors.empty

    def test_summary_returns_string(self):
        df = make_df(Q1=[1, 99])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        s = result.summary()
        assert isinstance(s, str)
        assert "SR" in s
        assert "FAIL" in s

    def test_summary_pass(self):
        df = make_df(Q1=[1, 2])
        result = SurveyValidator(df).sr("Q1", valid_values=[1, 2])
        assert "PASS" in result.summary()


# ===========================================================================
# SR
# ===========================================================================

class TestValidatorSR:
    def test_sr_valid(self):
        df = make_df(Q1=[1, 2, 3])
        result = SurveyValidator(df).sr("Q1", [1, 2, 3])
        assert result.passed

    def test_sr_missing_column_raises(self):
        df = make_df(Q1=[1, 2])
        with pytest.raises(ValueError, match="Column"):
            SurveyValidator(df).sr("Q99", [1, 2])

    def test_sr_routing(self):
        df = make_df(Q1=[None, 2, None], FILTER=[0, 1, 0])
        result = SurveyValidator(df).sr("Q1", [1, 2], routing_column="FILTER")
        assert result.passed
        assert result.checked_records == 1

    def test_sr_routing_error(self):
        df = make_df(Q1=[5, 2, None], FILTER=[0, 1, 0])
        result = SurveyValidator(df).sr("Q1", [1, 2], routing_column="FILTER")
        assert not result.passed
        assert result.error_count == 1


# ===========================================================================
# MULTI
# ===========================================================================

class TestValidatorMULTI:
    def test_multi_valid(self):
        df = make_df(Q1=[1, 0], Q2=[0, 1])
        result = SurveyValidator(df).multi(["Q1", "Q2"])
        assert result.passed

    def test_multi_nothing_selected(self):
        df = make_df(Q1=[0], Q2=[0])
        result = SurveyValidator(df).multi(["Q1", "Q2"])
        assert not result.passed

    def test_multi_exclusive(self):
        df = make_df(Q1=[1], Q_ex=[1])
        result = SurveyValidator(df).multi(["Q1"], exclusive=["Q_ex"])
        assert not result.passed


# ===========================================================================
# GRID
# ===========================================================================

class TestValidatorGRID:
    def test_grid_valid(self):
        df = make_df(G1=[1, 2], G2=[3, 5])
        result = SurveyValidator(df).grid(["G1", "G2"], [1, 2, 3, 4, 5])
        assert result.passed

    def test_grid_invalid_code(self):
        df = make_df(G1=[1, 9], G2=[3, 5])
        result = SurveyValidator(df).grid(["G1", "G2"], [1, 2, 3, 4, 5])
        assert not result.passed

    def test_grid_paired_mismatch_length_raises(self):
        df = make_df(G1=[1], G2=[2], D1=[1])
        with pytest.raises(ValueError, match="same length"):
            SurveyValidator(df).grid(["G1", "G2"], [1, 2], paired_cols=["D1"])


# ===========================================================================
# RANK_CHECK
# ===========================================================================

class TestValidatorRANK:
    def test_rank_valid(self):
        df = make_df(R1=[1, 2], R2=[2, 1], R3=[3, 3])
        result = SurveyValidator(df).rank_check(["R1", "R2", "R3"], max_rank=3)
        assert result.passed

    def test_rank_duplicate(self):
        df = make_df(R1=[1, 1], R2=[1, 2], R3=[3, 3])
        result = SurveyValidator(df).rank_check(["R1", "R2", "R3"], max_rank=3)
        assert not result.passed


# ===========================================================================
# OETEXT
# ===========================================================================

class TestValidatorOETEXT:
    def test_oetext_valid(self):
        df = make_df(OE=["hello", "world"])
        result = SurveyValidator(df).oe_text("OE")
        assert result.passed

    def test_oetext_missing(self):
        df = make_df(OE=["hello", ""])
        result = SurveyValidator(df).oe_text("OE")
        assert not result.passed

    def test_oetext_list_input(self):
        df = make_df(OE1=["a", "b"], OE2=["c", ""])
        result = SurveyValidator(df).oe_text(["OE1", "OE2"])
        assert not result.passed


# ===========================================================================
# NULL_CHECK
# ===========================================================================

class TestValidatorNULLCHECK:
    def test_null_check_all_null_passes(self):
        df = make_df(Q1=[None, None])
        result = SurveyValidator(df).null_check("Q1")
        assert result.passed

    def test_null_check_populated_fails(self):
        df = make_df(Q1=[None, 5.0])
        result = SurveyValidator(df).null_check("Q1")
        assert not result.passed
        assert result.error_count == 1


# ===========================================================================
# FILTER_LIST
# ===========================================================================

class TestValidatorFilterList:
    def test_filter_list_returns_df(self):
        df = make_df(Q1=[1, None, 3])
        v = SurveyValidator(df)
        result = v.filter_list(df["Q1"].isna(), ["RespID", "Q1"])
        assert len(result) == 1

    def test_filter_list_no_match(self):
        df = make_df(Q1=[1, 2])
        v = SurveyValidator(df)
        result = v.filter_list(df["Q1"].isna())
        assert result.empty


# ===========================================================================
# CUSTOM_CHECK
# ===========================================================================

class TestValidatorCustomCheck:
    def test_custom_check_pass(self):
        df = make_df(Q1=[1, 2], Age=[25, 30])
        v = SurveyValidator(df)
        result = v.custom_check(
            condition=df["Age"] < 18,
            question="Age",
            rule_name="AGE_CHECK",
            error_type="underage",
            expected="Age >= 18",
        )
        assert result.passed
        assert result.error_count == 0

    def test_custom_check_fail(self):
        df = make_df(Q1=[1, 2], Age=[15, 30])
        v = SurveyValidator(df)
        result = v.custom_check(
            condition=df["Age"] < 18,
            question="Age",
            rule_name="AGE_CHECK",
            error_type="underage",
            expected="Age >= 18",
            display_columns=["Q1", "Age"],
        )
        assert not result.passed
        assert result.error_count == 1
        assert result.errors.iloc[0]["record_id"] == 1
        assert result.errors.iloc[0]["error_type"] == "underage"

