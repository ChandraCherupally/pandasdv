"""
Tests for ValidationReport — QC report generation and export.

Covers:
- Initialization with valid/invalid inputs
- Property / metric calculations (total_rules, passed_rules, failed_rules, total_errors, total_checked_records, passed)
- summary() DataFrame generation
- to_csv() export (with errors, without errors, parent directory creation)
- to_excel() export (Summary sheet, rule error sheets, name sanitization, duplicates)
- to_txt() export (human-readable formatting)
- to_markdown() export (clean tabular formatting)
- Integration workflow: ChunkProcessor -> ValidationReport -> Exports
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from pandasdv import (
    ChunkProcessor,
    SurveyValidator,
    ValidationReport,
    ValidationResult,
)
from pandasdv.results import build_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_results() -> list[ValidationResult]:
    """Return a mix of passed and failed ValidationResult objects."""
    # 1. Passed SR
    r1 = build_result(
        rule_name="SR",
        question="Q1",
        error_rows=[],
        checked_records=100,
    )
    # 2. Failed MULTI
    r2 = build_result(
        rule_name="MULTI",
        question=["Q2_1", "Q2_2", "Q2_3"],
        error_rows=[
            {
                "record_id": 101,
                "question": "Q2_1",
                "rule": "MULTI",
                "error_type": "nothing_selected",
                "actual": {"Q2_1": 0, "Q2_2": 0, "Q2_3": 0},
                "expected": "at least one == 1",
            },
            {
                "record_id": 105,
                "question": "Q2_1",
                "rule": "MULTI",
                "error_type": "exclusive_violation",
                "actual": {"Q2_1": 1, "Q2_2": 0, "Q2_3": 1},
                "expected": "exclusive check",
            },
        ],
        checked_records=100,
    )
    # 3. Passed GRID
    r3 = build_result(
        rule_name="GRID",
        question=["Q5_1", "Q5_2"],
        error_rows=[],
        checked_records=80,
    )
    # 4. Failed RANK_CHECK
    r4 = build_result(
        rule_name="RANK_CHECK",
        question=["Q10_r1", "Q10_r2"],
        error_rows=[
            {
                "record_id": 102,
                "question": "Q10_r1",
                "rule": "RANK_CHECK",
                "error_type": "duplicate_rank",
                "actual": "rank 1 twice",
                "expected": "unique ranks",
            }
        ],
        checked_records=80,
    )
    return [r1, r2, r3, r4]


@pytest.fixture
def all_passed_results() -> list[ValidationResult]:
    r1 = build_result("SR", "Q1", [], 50)
    r2 = build_result("MULTI", ["Q2_1", "Q2_2"], [], 50)
    return [r1, r2]


# ===========================================================================
# 1. Initialization
# ===========================================================================

class TestValidationReportInit:
    def test_init_valid_list(self, sample_results: list[ValidationResult]):
        report = ValidationReport(sample_results)
        assert len(report.results) == 4

    def test_init_empty_list(self):
        report = ValidationReport([])
        assert report.total_rules == 0
        assert report.passed is True

    def test_init_invalid_type_raises(self):
        with pytest.raises(TypeError, match="iterable"):
            ValidationReport(123)  # type: ignore

        with pytest.raises(TypeError, match="iterable"):
            ValidationReport("not a list")  # type: ignore

    def test_init_invalid_item_raises(self):
        with pytest.raises(TypeError, match="ValidationResult"):
            ValidationReport([build_result("SR", "Q1", [], 10), "invalid_item"])  # type: ignore


# ===========================================================================
# 2. Properties and Summary DataFrame
# ===========================================================================

class TestValidationReportMetrics:
    def test_metrics_calculation(self, sample_results: list[ValidationResult]):
        report = ValidationReport(sample_results)
        assert report.total_rules == 4
        assert report.passed_rules == 2
        assert report.failed_rules == 2
        assert report.total_errors == 3  # 2 in MULTI + 1 in RANK_CHECK
        assert report.total_checked_records == 360  # 100 + 100 + 80 + 80
        assert report.passed is False

    def test_all_passed_metrics(self, all_passed_results: list[ValidationResult]):
        report = ValidationReport(all_passed_results)
        assert report.passed_rules == 2
        assert report.failed_rules == 0
        assert report.total_errors == 0
        assert report.passed is True

    def test_summary_dataframe_structure(self, sample_results: list[ValidationResult]):
        report = ValidationReport(sample_results)
        summary_df = report.summary()

        assert isinstance(summary_df, pd.DataFrame)
        assert list(summary_df.columns) == [
            "rule",
            "question",
            "status",
            "error_count",
            "checked_records",
        ]
        assert len(summary_df) == 4
        assert summary_df.iloc[0]["status"] == "PASS"
        assert summary_df.iloc[1]["status"] == "FAIL"
        assert summary_df.iloc[1]["error_count"] == 2

    def test_summary_empty_results(self):
        report = ValidationReport([])
        summary_df = report.summary()
        assert isinstance(summary_df, pd.DataFrame)
        assert summary_df.empty
        assert "status" in summary_df.columns


# ===========================================================================
# 3. CSV Export
# ===========================================================================

class TestCSVExport:
    def test_to_csv_with_errors(self, sample_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "errors.csv"
        report = ValidationReport(sample_results)
        ret_path = report.to_csv(out_file)

        assert ret_path == out_file
        assert out_file.exists()

        df_errors = pd.read_csv(out_file)
        assert len(df_errors) == 3  # 2 + 1 errors
        assert set(df_errors["rule"].unique()) == {"MULTI", "RANK_CHECK"}
        assert "record_id" in df_errors.columns
        assert "error_type" in df_errors.columns

    def test_to_csv_no_errors(self, all_passed_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "no_errors.csv"
        report = ValidationReport(all_passed_results)
        report.to_csv(out_file)

        assert out_file.exists()
        df_errors = pd.read_csv(out_file)
        assert df_errors.empty
        assert "record_id" in df_errors.columns

    def test_to_csv_creates_subdirectories(self, sample_results: list[ValidationResult], tmp_path: Path):
        nested_file = tmp_path / "nested" / "reports" / "errors.csv"
        report = ValidationReport(sample_results)
        report.to_csv(nested_file)
        assert nested_file.exists()


# ===========================================================================
# 4. Excel Export
# ===========================================================================

class TestExcelExport:
    def test_to_excel_structure(self, sample_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "qc_report.xlsx"
        report = ValidationReport(sample_results)
        ret_path = report.to_excel(out_file)

        assert ret_path == out_file
        assert out_file.exists()

        excel_file = pd.ExcelFile(out_file)
        # Sheet 1: Summary, plus sheets for failed rules
        assert "Summary" in excel_file.sheet_names
        assert len(excel_file.sheet_names) == 3  # Summary, MULTI_Q2_1, RANK_CHECK_Q10_r1

        df_summary = excel_file.parse("Summary")
        assert not df_summary.empty

    def test_to_excel_no_errors(self, all_passed_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "passed_qc.xlsx"
        report = ValidationReport(all_passed_results)
        report.to_excel(out_file)

        excel_file = pd.ExcelFile(out_file)
        assert excel_file.sheet_names == ["Summary"]

    def test_to_excel_sheet_name_sanitization_and_duplicates(self, tmp_path: Path):
        # Create results with invalid excel chars and long question names that collide
        long_q_name = "Q_very_long_question_name_exceeding_the_standard_excel_limit_12345"
        r1 = build_result("SR", f"{long_q_name}_A", [{"record_id": 1, "question": "Q", "rule": "SR", "error_type": "bad"}], 10)
        r2 = build_result("SR", f"{long_q_name}_B", [{"record_id": 2, "question": "Q", "rule": "SR", "error_type": "bad"}], 10)
        r3 = build_result("SR", "Q[1]:bad/char?*", [{"record_id": 3, "question": "Q", "rule": "SR", "error_type": "bad"}], 10)

        out_file = tmp_path / "sanitized_qc.xlsx"
        report = ValidationReport([r1, r2, r3])
        report.to_excel(out_file)

        excel_file = pd.ExcelFile(out_file)
        sheet_names = excel_file.sheet_names
        assert "Summary" in sheet_names
        # Ensure all sheet names <= 31 chars and unique
        for name in sheet_names:
            assert len(name) <= 31
            assert not any(c in name for c in r":\/?*[]")
        assert len(set(sheet_names)) == len(sheet_names)


# ===========================================================================
# 5. TXT and Markdown Export
# ===========================================================================

class TestTxtAndMarkdownExport:
    def test_to_txt(self, sample_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "qc_report.txt"
        report = ValidationReport(sample_results)
        ret_path = report.to_txt(out_file)

        assert ret_path == out_file
        assert out_file.exists()

        content = out_file.read_text(encoding="utf-8")
        assert "PANDASDV SURVEY QC REPORT" in content
        assert "Overall Status:        FAIL" in content
        assert "Total Errors:          3" in content
        assert "[FAIL] MULTI | Q2_1" in content
        assert "[PASS] SR | Q1" in content

    def test_to_markdown(self, sample_results: list[ValidationResult], tmp_path: Path):
        out_file = tmp_path / "qc_report.md"
        report = ValidationReport(sample_results)
        ret_path = report.to_markdown(out_file)

        assert ret_path == out_file
        assert out_file.exists()

        content = out_file.read_text(encoding="utf-8")
        assert "# Survey QC Validation Report" in content
        assert "| **Total Rules Evaluated** | 4 |" in content
        assert "| MULTI | Q2_1..Q2_3 | FAIL | 2 | 100 |" in content


# ===========================================================================
# 6. ChunkProcessor -> ValidationReport Integration
# ===========================================================================

class TestChunkProcessorIntegration:
    def test_chunk_processing_to_report(self, tmp_path: Path):
        # Create synthetic CSV with 15 rows
        csv_file = tmp_path / "survey_batch.csv"
        csv_file.write_text(
            "RespID,Q1,Q2_1,Q2_2\n"
            "1,1,1,0\n"
            "2,2,0,1\n"
            "3,99,0,0\n"  # Q1 invalid code, Q2 nothing selected
            "4,1,1,0\n"
            "5,2,0,1\n"
            "6,1,1,0\n"
            "7,2,0,1\n"
            "8,1,1,0\n"
            "9,2,0,1\n"
            "10,1,1,0\n"
            "11,2,0,1\n"
            "12,1,1,0\n"
            "13,2,0,1\n"
            "14,1,1,0\n"
            "15,2,0,1\n"
        )

        processor = ChunkProcessor(chunk_size=5)
        rules = [
            {"name": "SR", "params": {"question": "Q1", "valid_values": [1, 2]}},
            {"name": "MULTI", "params": {"questions": ["Q2_1", "Q2_2"]}},
        ]
        results = processor.process_csv(csv_file, rules=rules)

        report = ValidationReport(results)

        assert report.total_rules == 2
        assert report.failed_rules == 2
        assert report.total_errors == 2
        assert report.total_checked_records == 30  # 15 for Q1 + 15 for Q2

        # Export all formats
        csv_path = report.to_csv(tmp_path / "reports" / "batch_errors.csv")
        xlsx_path = report.to_excel(tmp_path / "reports" / "batch_report.xlsx")
        txt_path = report.to_txt(tmp_path / "reports" / "batch_summary.txt")
        md_path = report.to_markdown(tmp_path / "reports" / "batch_summary.md")

        assert csv_path.exists()
        assert xlsx_path.exists()
        assert txt_path.exists()
        assert md_path.exists()

        df_err = pd.read_csv(csv_path)
        assert len(df_err) == 2
        assert set(df_err["record_id"].unique()) == {3}
