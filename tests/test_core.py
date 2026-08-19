"""
Tests for the original function-based API (backward compatibility).

These tests preserve the existing test behaviour using ``monkeypatch`` to
inject a test DataFrame into the global ``io_utils.df`` used by ``core.py``.

New code should use the class-based SurveyValidator API instead — see
``test_validator.py``.
"""

import pandas as pd
import pytest

from pandasdv.core import (
    FLT_LIST,
    SR,
    lst_no,
)


# ===========================================================================
# lst_no helper
# ===========================================================================

def test_lst_no_range():
    assert lst_no(1, 3) == [1, 2, 3]


def test_lst_no_single():
    assert lst_no(5) == [5]


# ===========================================================================
# FLT_LIST (original global-state API)
# ===========================================================================

def test_flt_list_basic(monkeypatch, capsys):
    df = pd.DataFrame({
        "ID": [1, 2, 3],
        "Q1": [1, None, 3]
    })

    # Inject test DataFrame into the global used by core.py
    monkeypatch.setattr("pandasdv.io_utils.df", df)

    cond = df["Q1"].isna()
    FLT_LIST(COND=cond, LIST=["ID", "Q1"])

    captured = capsys.readouterr()
    assert "Number of cases listed: 1" in captured.out


def test_flt_list_no_matches(monkeypatch, capsys):
    df = pd.DataFrame({"ID": [1, 2], "Q1": [1, 2]})
    monkeypatch.setattr("pandasdv.io_utils.df", df)

    FLT_LIST(COND=df["Q1"].isna(), LIST=["ID", "Q1"])

    captured = capsys.readouterr()
    assert "Number of cases listed: 0" in captured.out


# ===========================================================================
# SR (original global-state API)
# ===========================================================================

def test_sr_runs(monkeypatch, capsys):
    df = pd.DataFrame({
        "ID": [1, 2, 3],
        "Q1": [1, 99, None]
    })
    monkeypatch.setattr("pandasdv.io_utils.df", df)

    SR(QVAR="Q1", RNG=[1, 2, 3])

    captured = capsys.readouterr()
    assert "Q1:" in captured.out


def test_sr_valid_no_errors_output(monkeypatch, capsys):
    df = pd.DataFrame({"ID": [1, 2], "Q1": [1, 2]})
    monkeypatch.setattr("pandasdv.io_utils.df", df)

    SR(QVAR="Q1", RNG=[1, 2])

    captured = capsys.readouterr()
    # No records should be listed
    assert "Number of cases listed: 0" in captured.out


# ===========================================================================
# Package-level import sanity check
# ===========================================================================

def test_new_api_importable():
    """Confirm new class-based API is importable from the top-level package."""
    from pandasdv import SurveyValidator, ValidationResult, ChunkProcessor, ValidationReport, load_data  # noqa: F401
    assert SurveyValidator is not None
    assert ValidationResult is not None
    assert ChunkProcessor is not None
    assert ValidationReport is not None
    assert load_data is not None


def test_legacy_api_importable():
    """Confirm all original functions remain importable."""
    from pandasdv import (  # noqa: F401
        SR, MULTI, GRID, RANK_CHECK, OETEXT, NULL_CHECK, FLT_LIST, lst_no
    )