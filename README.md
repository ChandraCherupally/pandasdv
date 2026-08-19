# 🧾 pandasdv — Survey Data Validation Library for Pandas

[![PyPI version](https://img.shields.io/pypi/v/pandasdv.svg)](https://pypi.org/project/pandasdv/)
[![Python versions](https://img.shields.io/pypi/pyversions/pandasdv.svg)](https://pypi.org/project/pandasdv/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`pandasdv` is a survey data validation library designed for Python and `pandas`, inspired by real-world **Market Research** and **SPSS Quality Control (QC)** workflows.

It transforms repetitive questionnaire validation checks into structured, testable, and memory-conscious operations with first-class support for single response, multi-select batteries, grids/matrices, ranking sequences, open-ended text, and large dataset chunk processing.

---

## 📌 Table of Contents

- [Why pandasdv?](#-why-pandasdv)
- [Architecture & Design Principles](#-architecture--design-principles)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Survey Validation Rule Types](#-survey-validation-rule-types)
  - [Single Response (SR)](#1-single-response-sr)
  - [Multiple Response (MULTI)](#2-multiple-response-multi)
  - [Grid / Matrix (GRID)](#3-grid--matrix-grid)
  - [Rank Order (RANK_CHECK)](#4-rank-order-rank_check)
  - [Open-Ended Text (OETEXT)](#5-open-ended-text-oetext)
  - [Null / Blank Checks (NULL_CHECK)](#6-null--blank-checks-null_check)
  - [Ad-hoc Filtering (filter_list)](#7-ad-hoc-filtering-filter_list)
- [ValidationResult Structure](#-validationresult-structure)
- [QC Report Generation](#-qc-report-generation)
- [Large Dataset & Chunk Processing](#-large-dataset--chunk-processing)
- [IO Layer & SPSS/SAV Support](#-io-layer--spsssav-support)
- [Memory Optimization Guidelines](#-memory-optimization-guidelines)
- [Migration Guide from Legacy API](#-migration-guide-from-legacy-api)
- [Limitations](#-limitations)
- [Testing & Verification](#-testing--verification)
- [Contributing & License](#-contributing--license)

---

## 💡 Why pandasdv?

In Market Research and survey analytics, data cleaning teams perform standard quality assurance tasks on raw questionnaire datasets (often delivered as SPSS `.sav` or delimited `.csv` files). These QC checks verify routing logic, validate code ranges, identify punch anomalies, and flag exclusive option conflicts.

Traditionally, analysts wrote ad-hoc scripts or relied on manual syntax files that mixed validation logic, logging, and state mutation. 

`pandasdv` provides:
1. **Class-Based SurveyValidator**: No global DataFrames, no hidden state.
2. **Pure, Non-Mutating Validation Logic**: Does not modify input data or inject temporary columns.
3. **Structured Validation Results**: Every rule returns a `ValidationResult` object with error counts, passing flags, and a clean error DataFrame.
4. **Large Dataset Chunk Processing**: Stream huge CSV datasets without loading the entire file into memory, including cross-chunk duplicate ID tracking.
5. **SPSS (.sav) Compatibility**: Native preservation of categorical numeric codes (`convert_categoricals=False`).
6. **Full Backward Compatibility**: Legacy function-based scripts remain supported via compatibility shims.

---

## 🏗️ Architecture & Design Principles

`pandasdv` follows **SOLID** and **KISS** software design principles:

- **Single Responsibility Principle (SRP)**:
  - `pandasdv.io`: File loading and format dispatch.
  - `pandasdv.rules`: Pure, stateless survey validation algorithms.
  - `pandasdv.validator`: Object-oriented interface for in-memory DataFrames.
  - `pandasdv.results`: Structured dataclass representations of QC outputs.
  - `pandasdv.processor`: Batch and chunk streaming pipeline for large files.
- **Open/Closed Principle (OCP)**: New validation rules can be added as pure functions in `rules.py` and exposed via `SurveyValidator` without touching unrelated logic.
- **Dependency Inversion Principle (DIP)**: Core validation rules operate on standard pandas structures and return structured dictionaries, decoupling logic from I/O or terminal printing.
- **Don't Repeat Yourself (DRY)**: Centralized routing masks and consistent error record formatting.

```
                     ┌──────────────────────┐
                     │ Raw Survey Data File │
                     │   (.sav, .csv, etc.) │
                     └──────────┬───────────┘
                                │
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
          ┌───────────────┐           ┌────────────────┐
          │  load_data()  │           │ ChunkProcessor │
          └───────┬───────┘           └───────┬────────┘
                  │                           │ (processes in chunks)
                  ▼                           ▼
          ┌────────────────────────────────────────────┐
          │               SurveyValidator              │
          │  .sr()  .multi()  .grid()  .rank_check()   │
          └─────────────────────┬──────────────────────┘
                                │
                                ▼
          ┌────────────────────────────────────────────┐
          │              ValidationResult              │
          │  - passed: bool                            │
          │  - error_count: int                        │
          │  - errors: pd.DataFrame                    │
          │  - summary(): str                          │
          └────────────────────────────────────────────┘
```

---

## 📦 Installation

Install `pandasdv` from PyPI:

```bash
pip install pandasdv
```

Or install with development test tools:

```bash
pip install "pandasdv[dev]"
```

**Requirements:**
- Python `>= 3.8`
- `pandas >= 2.0.0`
- `numpy >= 1.24.0`
- `pyreadstat >= 1.3.0` (for SPSS `.sav` files)

---

## 🚀 Quick Start

```python
import pandas as pd
from pandasdv import SurveyValidator, load_data

# 1. Load survey dataset (.sav, .csv, or .xlsx)
df = load_data("survey_data.sav")

# 2. Instantiate validator (defaults to the first column as Respondent ID)
validator = SurveyValidator(df, id_col="RespID")

# 3. Validate Single Response question (Ask-all: Q1 must be 1 or 2)
res_q1 = validator.sr(
    question="Q1",
    valid_values=[1, 2]
)
print(res_q1.summary())
# Output: [PASS] SR | Q1 | errors=0 / checked=500

# 4. Validate Conditional Question (Q30a only asked if QFILTER == 1)
df["QFILTER"] = 0
df.loc[df["Q30"].between(2, 5), "QFILTER"] = 1

res_q30a = validator.sr(
    question="Q30a",
    valid_values=list(range(1, 17)) + [97],
    routing_column="QFILTER"
)

if not res_q30a.passed:
    print(f"Errors detected: {res_q30a.error_count}")
    print(res_q30a.errors[["record_id", "question", "error_type", "actual", "expected"]])
```

---

## 🧪 Survey Validation Rule Types

### 1. Single Response (`SR`)
Validates single-choice categorical questions.
- **Routed-in (`routing_column == 1`)**: Must not be missing/null and value must exist in `valid_values`.
- **Routed-out (`routing_column != 1`)**: Must be null/blank.

```python
result = validator.sr(
    question="Q1",
    valid_values=[1, 2, 3, 4],
    routing_column="QFILTER"  # Optional: omit for ask-all questions
)
```

### 2. Multiple Response (`MULTI`)
Validates multiple-select question batteries coded as binary indicator variables (0 = Not Selected, 1 = Selected).
- Detects **Nothing Selected** (all zeros when routed in).
- Detects **Invalid Punches** (values other than 0 or 1).
- Detects **Exclusive Option Violations** (e.g., respondent selected "Option 1" AND "None of the above").
- Detects **Filter-OFF Violations** (values populated when routed out).

```python
result = validator.multi(
    questions=["Q5_1", "Q5_2", "Q5_3", "Q5_4"],
    exclusive=["Q5_99"],       # Exclusive option ("None of these")
    routing_column="QFILTER"    # Optional
)
```

### 3. Grid / Matrix (`GRID`)
Validates rating grids or matrix question blocks across multiple attributes.
- **Simple Mode**: Checks all columns in `questions` against `valid_codes`.
- **Paired Mode (`paired_cols`)**: Supports per-row conditional routing where each grid row has its own display filter variable.

```python
# Simple grid
result = validator.grid(
    questions=["Q56_1", "Q56_2", "Q56_3"],
    valid_codes=[1, 2, 3, 4, 5],
    routing_column="QFILTER"
)

# Paired grid with row-level filtering
result = validator.grid(
    questions=["QBrand_1", "QBrand_2", "QBrand_3"],
    paired_cols=["QAware_1", "QAware_2", "QAware_3"],
    valid_codes=[1, 2, 3, 4, 5],
    routing_column="QFILTER"
)
```

### 4. Rank Order (`RANK_CHECK`)
Validates ranking questions across assigned rank positions.
- Checks that assigned ranks fall between `1` and `max_rank`.
- Detects duplicate rank assignments (e.g., respondent gave rank 1 to two items).
- Supports optional `min_rank` thresholds when respondents are required to rank at least a subset of items.
- Detects values when the filter is OFF.

```python
result = validator.rank_check(
    questions=["Q180_Order1", "Q180_Order2", "Q180_Order3", "Q180_Order4"],
    max_rank=3,
    min_rank=1,
    routing_column="QFILTER"
)
```

### 5. Open-Ended Text (`OETEXT`)
Validates required verbatim responses and text fields.
- When routed in: Confirms response is populated and not an empty string.
- When routed out: Confirms response is blank.

```python
result = validator.oe_text(
    questions=["Q8_other_specify"],
    routing_column="QFILTER"
)
```

### 6. Null / Blank Checks (`NULL_CHECK`)
Ensures designated columns are completely blank or null.
- Numeric columns: asserts all values are `NaN`/`None`.
- Text/object columns: asserts all values are `NaN` or empty strings `""`.

```python
result = validator.null_check(
    questions=["Unused_Column_1", "Unused_Column_2"]
)
```

### 7. Ad-hoc Filtering (`filter_list`)
Allows custom condition checks and returns a filtered DataFrame (pure replacement for legacy `FLT_LIST`).

```python
# Check for invalid respondent IDs (negative or NaN)
bad_ids = validator.filter_list(
    condition=(df["RespID"].isna()) | (df["RespID"] <= 0),
    columns=["RespID"]
)

# Check for duplicate respondent IDs
dup_ids = validator.filter_list(
    condition=df["RespID"].duplicated(keep=False),
    columns=["RespID"]
)
```

---

## 📊 ValidationResult Structure

Every validation method returns a structured `ValidationResult` dataclass:

```python
@dataclass
class ValidationResult:
    rule_name: str          # e.g., "SR", "MULTI", "GRID"
    question: str | list    # Question variable(s) checked
    passed: bool            # True if zero errors found
    error_count: int        # Number of offending records
    checked_records: int    # Number of records evaluated in scope
    errors: pd.DataFrame    # Tabular error details
    metadata: dict          # Rule configuration metadata
```

### Accessing Error Details
The `.errors` DataFrame provides standardized columns across all rules:

| Column | Description |
|---|---|
| `record_id` | Identifier of the respondent |
| `question` | Question column name |
| `rule` | Rule name (`SR`, `MULTI`, etc.) |
| `error_type` | Diagnostic type (`invalid_code`, `nothing_selected`, etc.) |
| `actual` | Actual value or response vector |
| `expected` | Expected criteria |

```python
result = validator.sr("Q1", valid_values=[1, 2])

print(result.passed)        # False
print(result.error_count)   # 3
print(result.errors.head())
```

---

## 📊 QC Report Generation

The `ValidationReport` class aggregates multiple `ValidationResult` objects to generate structured QC deliverables across Excel, CSV, Text, and Markdown formats.

### In-Memory Validation Workflow

```python
from pandasdv import SurveyValidator, ValidationReport, load_data

df = load_data("survey.sav")
validator = SurveyValidator(df)

results = [
    validator.sr("Q1", valid_values=[1, 2, 3]),
    validator.multi(["Q2_1", "Q2_2"], exclusive=["Q2_99"]),
    validator.grid(["Q5_1", "Q5_2"], valid_codes=[1, 2, 3, 4, 5]),
]

report = ValidationReport(results)

# 1. Inspect summary DataFrame
print(report.summary())

# 2. Export QC deliverables
report.to_excel("reports/survey_qc_report.xlsx")
report.to_csv("reports/survey_qc_errors.csv")
report.to_txt("reports/survey_qc_report.txt")
report.to_markdown("reports/survey_qc_report.md")
```

### Large CSV Batch Workflow

```python
from pandasdv import ChunkProcessor, ValidationReport

processor = ChunkProcessor(chunk_size=50_000)

rules = [
    {"name": "SR", "params": {"question": "Q1", "valid_values": [1, 2, 3]}},
    {"name": "MULTI", "params": {"questions": ["Q2_1", "Q2_2"], "exclusive": ["Q2_99"]}},
]

results = processor.process_csv("large_survey.csv", rules=rules)

report = ValidationReport(results)
report.to_excel("survey_qc_report.xlsx")
report.to_csv("survey_qc_errors.csv")
report.to_txt("survey_qc_report.txt")
```

### Description of Generated Report Files

| Generated File | Content Description |
|---|---|
| `survey_qc_report.xlsx` | Multi-sheet Excel workbook. Sheet 1 (`Summary`) includes KPI overview metrics and rule-level pass/fail summary. Subsequent sheets contain detailed error rows for each failed rule. |
| `survey_qc_errors.csv` | Consolidated CSV containing all detailed error records from failed rules (includes `record_id`, `question`, `rule`, `error_type`, `actual`, and `expected`). |
| `survey_qc_report.txt` | Human-readable plain text summary suitable for console logging or automated status emails. |
| `survey_qc_report.md` | Clean Markdown document with tabular metric breakdowns and status badges. |

> [!NOTE]
> Report export currently aggregates existing `ValidationResult.errors` DataFrames in memory to assemble the final output files. For extreme error volumes (millions of erroneous rows), consider addressing data quality issues upstream or filtering error outputs.

---

## ⚡ Large Dataset & Chunk Processing

For multi-gigabyte survey exports, reading the entire file into memory is often unnecessary and can cause Out-Of-Memory (OOM) errors.

`pandasdv.ChunkProcessor` streams CSV files in batches, runs validation rules sequentially per chunk, releases the chunk from memory, and aggregates the final results.

### Cross-Chunk Duplicate Detection
While question validations are chunk-local, respondent ID uniqueness requires global tracking. `ChunkProcessor` maintains an in-memory `Counter` of respondent IDs across all chunks with $O(\text{unique IDs})$ memory complexity without holding full records in RAM.

```python
from pandasdv import ChunkProcessor

processor = ChunkProcessor(chunk_size=50_000)

rules = [
    {
        "name": "SR",
        "params": {
            "question": "Q1",
            "valid_values": [1, 2, 3, 4]
        }
    },
    {
        "name": "MULTI",
        "params": {
            "questions": ["Q2_1", "Q2_2", "Q2_3"],
            "exclusive": ["Q2_99"]
        }
    }
]

# Process in stream mode
results = processor.process_csv("large_survey_data.csv", rules=rules)

for r in results:
    print(r.summary())
    if not r.passed:
        print(f"  -> Found {r.error_count} errors in {r.rule_name}")
```

---

## 💾 IO Layer & SPSS/SAV Support

The `load_data()` utility provides unified loading for `.sav`, `.zsav`, `.csv`, `.tsv`, and `.xlsx` files:

```python
from pandasdv.io import load_data

# SPSS SAV file (preserves numeric codes, casts ID to int)
df_sav = load_data("data.sav")

# CSV file with selective column loading for memory efficiency
df_csv = load_data("data.csv", columns=["RespID", "Q1", "Q2_1", "Q2_2"])

# Excel file
df_excel = load_data("data.xlsx", sheet_name="SurveyData")
```

---

## 🧠 Memory Optimization Guidelines

When validating high-volume survey datasets:
1. **Use Selective Columns in CSV**: Specify `columns=[...]` in `load_data()` to avoid loading unused columns.
2. **Use ChunkProcessor for CSV**: For CSV datasets with millions of rows, use `ChunkProcessor` with a `chunk_size` suited to your available memory (typically 25,000–100,000 rows).
3. **No Unnecessary Copies**: `SurveyValidator` does not duplicate your DataFrame during validation.

---

## 🔄 Migration Guide from Legacy API

The legacy function-based API (which relied on global `df` state and terminal output redirection) is fully preserved for backward compatibility. 

### Before (Legacy v0.1.x API)
```python
from pandasdv import initial_setup, SR, MULTI, output_setup

# Deprecated: Relies on global module-level df and stdout redirection
df = initial_setup("survey.sav")
SR(Rout='QFILTER', QVAR='Q1', RNG=[1, 2, 3])
MULTI(QVAR=['Q2_1', 'Q2_2'], QEX=['Q2_99'])
output_setup("report.txt")
```

### After (Recommended v0.2.x API)
```python
from pandasdv import SurveyValidator, load_data

df = load_data("survey.sav")
validator = SurveyValidator(df)

res_sr = validator.sr("Q1", valid_values=[1, 2, 3])
res_multi = validator.multi(["Q2_1", "Q2_2"], exclusive=["Q2_99"])

print(res_sr.summary())
print(res_multi.summary())
```

---

## ⚠️ Limitations

1. **SPSS Chunk Streaming**: Standard `pd.read_spss()` loads the entire file into memory before returning a DataFrame. While `pyreadstat` provides lower-level block readers, chunk streaming is officially recommended and optimized for `.csv` files.
2. **First Column ID Default**: If `id_col` is not specified, `SurveyValidator` defaults to using `df.columns[0]` as the respondent identifier column.

---

## 🧪 Testing & Verification

Run the comprehensive test suite with `pytest`:

```bash
uv run pytest tests/ -v
```

The test suite covers:
- Single response validation (valid codes, missing values, routing in/out checks)
- Multiple response validation (nothing selected, invalid punches, exclusive conflicts)
- Matrix/grid validation (simple & paired sub-routing modes)
- Ranking validation (range bounds, duplicate ranks, minimum rank constraints)
- Open-ended text & blank checks
- Chunk processing and cross-chunk duplicate respondent ID detection
- Backward-compatibility wrappers and import integrity

---

## 🤝 Contributing & License

Contributions are welcome! Please submit issues or pull requests to the [GitHub Repository](https://github.com/ChandraCherupally/pandasdv).

This project is licensed under the **MIT License**.
