"""
Tests for pandasdv.io — load_data() entry-point.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pandas as pd
import pytest

from pandasdv.io import load_data


# ---------------------------------------------------------------------------
# CSV tests (no external file needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.csv"
    p.write_text("ID,Q1,Q2\n1,1,2\n2,2,3\n3,3,1\n")
    return p


class TestLoadCSV:
    def test_loads_csv(self, csv_file: Path):
        df = load_data(csv_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "Q1" in df.columns

    def test_column_subset(self, csv_file: Path):
        df = load_data(csv_file, columns=["ID", "Q1"])
        assert list(df.columns) == ["ID", "Q1"]

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_data(tmp_path / "nonexistent.csv")

    def test_unsupported_extension_raises(self, tmp_path: Path):
        p = tmp_path / "data.parquet"
        p.write_bytes(b"fake")
        with pytest.raises(ValueError, match="Unsupported"):
            load_data(p)

    def test_loads_string_path(self, csv_file: Path):
        df = load_data(str(csv_file))
        assert len(df) == 3


# ---------------------------------------------------------------------------
# SPSS tests (skipped when pyreadstat not available or file absent)
# ---------------------------------------------------------------------------

SAMPLE_SAV = Path(__file__).parent.parent / "Sample_project" / "Consumer_Brand_Preference_Data_50.sav"


@pytest.mark.skipif(not SAMPLE_SAV.exists(), reason="Sample .sav file not present")
class TestLoadSPSS:
    def test_loads_sav(self):
        df = load_data(SAMPLE_SAV)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_first_col_is_int(self):
        df = load_data(SAMPLE_SAV)
        id_col = df.columns[0]
        assert pd.api.types.is_integer_dtype(df[id_col])
