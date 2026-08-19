"""
Tests for ChunkProcessor — large CSV chunk-based processing.

Covers:
- Single-chunk CSV (small file)
- Multi-chunk CSV (file processed in multiple passes)
- Error aggregation across chunks
- Cross-chunk duplicate ID detection
- Empty rules raises ValueError
- Unknown rule name raises ValueError
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pandasdv import ChunkProcessor


ID = "RespID"


def write_csv(path: Path, n_rows: int, q1_valid: bool = True) -> None:
    """Write a simple CSV with n_rows rows for testing."""
    with open(path, "w", newline="") as f:
        f.write("RespID,Q1,Q2_1,Q2_2\n")
        for i in range(1, n_rows + 1):
            q1 = 1 if q1_valid else (1 if i % 2 == 0 else 99)
            q2_1 = 1 if i % 3 != 0 else 0
            q2_2 = 0 if i % 3 != 0 else 1
            f.write(f"{i},{q1},{q2_1},{q2_2}\n")


# ---------------------------------------------------------------------------
# Basic rules fixture
# ---------------------------------------------------------------------------

SR_RULE = {"name": "SR", "params": {"question": "Q1", "valid_values": [1, 2]}}
MULTI_RULE = {"name": "MULTI", "params": {"questions": ["Q2_1", "Q2_2"]}}


# ===========================================================================
# Initialization
# ===========================================================================

class TestChunkProcessorInit:
    def test_default_chunk_size(self):
        p = ChunkProcessor()
        assert p.chunk_size == 50_000

    def test_custom_chunk_size(self):
        p = ChunkProcessor(chunk_size=100)
        assert p.chunk_size == 100

    def test_zero_chunk_size_raises(self):
        with pytest.raises(ValueError, match="positive"):
            ChunkProcessor(chunk_size=0)


# ===========================================================================
# process_csv — basic
# ===========================================================================

class TestProcessCSV:
    def test_single_chunk_valid(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, n_rows=10, q1_valid=True)
        proc = ChunkProcessor(chunk_size=100)
        results = proc.process_csv(csv_path, rules=[SR_RULE])
        assert len(results) >= 1
        sr_result = results[0]
        assert sr_result.rule_name == "SR"
        assert sr_result.passed

    def test_single_chunk_with_errors(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, n_rows=10, q1_valid=False)
        proc = ChunkProcessor(chunk_size=100)
        results = proc.process_csv(csv_path, rules=[SR_RULE])
        sr_result = results[0]
        assert not sr_result.passed
        assert sr_result.error_count > 0

    def test_multi_chunk_error_aggregation(self, tmp_path: Path):
        """Errors from multiple chunks must be combined correctly."""
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, n_rows=20, q1_valid=False)
        # chunk_size=5 means 4 chunks for 20 rows
        proc = ChunkProcessor(chunk_size=5)
        results_small = proc.process_csv(csv_path, rules=[SR_RULE])

        # Also process as single chunk
        proc_large = ChunkProcessor(chunk_size=1000)
        results_large = proc_large.process_csv(csv_path, rules=[SR_RULE])

        # Both should detect the same total number of errors
        assert results_small[0].error_count == results_large[0].error_count

    def test_multiple_rules(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, n_rows=6)
        proc = ChunkProcessor(chunk_size=100)
        results = proc.process_csv(csv_path, rules=[SR_RULE, MULTI_RULE])
        assert len(results) >= 2

    def test_file_not_found_raises(self, tmp_path: Path):
        proc = ChunkProcessor()
        with pytest.raises(FileNotFoundError):
            proc.process_csv(tmp_path / "nonexistent.csv", rules=[SR_RULE])

    def test_empty_rules_raises(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, 5)
        proc = ChunkProcessor()
        with pytest.raises(ValueError, match="rules"):
            proc.process_csv(csv_path, rules=[])

    def test_unknown_rule_raises(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, 5)
        proc = ChunkProcessor()
        with pytest.raises(ValueError, match="Unknown"):
            proc.process_csv(csv_path, rules=[{"name": "BOGUS", "params": {}}])


# ===========================================================================
# Cross-chunk duplicate ID detection
# ===========================================================================

class TestCrossChunkDuplicates:
    def test_no_duplicates_no_extra_result(self, tmp_path: Path):
        csv_path = tmp_path / "data.csv"
        write_csv(csv_path, n_rows=10)
        proc = ChunkProcessor(chunk_size=3)
        results = proc.process_csv(csv_path, rules=[SR_RULE])
        rule_names = [r.rule_name for r in results]
        assert "DUPLICATE_ID" not in rule_names

    def test_within_chunk_duplicate_detected(self, tmp_path: Path):
        csv_path = tmp_path / "dupes.csv"
        # Two rows with the same ID in the same chunk
        csv_path.write_text("RespID,Q1\n1,1\n1,2\n3,1\n")
        proc = ChunkProcessor(chunk_size=100)
        results = proc.process_csv(csv_path, rules=[SR_RULE])
        rule_names = [r.rule_name for r in results]
        assert "DUPLICATE_ID" in rule_names
        dup_result = next(r for r in results if r.rule_name == "DUPLICATE_ID")
        assert dup_result.error_count == 1  # one unique ID (1) is duplicated

    def test_cross_chunk_duplicate_detected(self, tmp_path: Path):
        csv_path = tmp_path / "cross_dupes.csv"
        # ID=1 appears in chunk 1 (rows 1-2) and chunk 2 (rows 3-4)
        csv_path.write_text("RespID,Q1\n1,1\n2,1\n1,2\n4,1\n")
        proc = ChunkProcessor(chunk_size=2)  # 2 rows per chunk
        results = proc.process_csv(csv_path, rules=[SR_RULE])
        rule_names = [r.rule_name for r in results]
        assert "DUPLICATE_ID" in rule_names
