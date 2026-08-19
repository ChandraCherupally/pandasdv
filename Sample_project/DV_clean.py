"""
Sample survey data validation script using pandasdv (v0.2+ class-based API).

Dataset: Consumer Brand Preference Survey (SPSS .sav / CSV)
"""

from pathlib import Path
import pandas as pd
from pandasdv import SurveyValidator, ValidationReport, load_data, lst_no

# 1. Resolve dataset path relative to this script
DATA_DIR = Path(__file__).resolve().parent
#SAV_PATH = DATA_DIR / "Consumer_Brand_Preference_Data_50.sav"
CSV_PATH = DATA_DIR / "Consumer_Brand_Preference_Data_50.csv"

# Load SPSS .sav if present, else fallback to CSV
input_file = CSV_PATH
print(f"Loading data from: {input_file.name}")
df = load_data(input_file)

# 2. Instantiate SurveyValidator
validator = SurveyValidator(df, id_col="RespID")
print(f"Total respondents loaded: {len(df)}\n")

results = []

def report(title: str, res):
    """Helper to display validation results cleanly."""
    print(f"--- {title} ---")
    print(res.summary())
    if not res.passed:
        print(f"  -> Error count: {res.error_count}")
        print(res.errors[["record_id", "question", "error_type", "actual", "expected"]].to_string(index=False))
    print()
    results.append(res)


# -----------------------------------------------------------------------------
# RespID Checks: Valid ID & Duplicates
# -----------------------------------------------------------------------------
res_respid_valid = validator.custom_check(
    condition=(df["RespID"].isna()) | (df["RespID"] <= 0),
    question="RespID",
    rule_name="ID_CHECK",
    error_type="invalid_or_missing_id",
    expected="RespID > 0",
)
report("RespID: Valid ID Check", res_respid_valid)

res_respid_dup = validator.custom_check(
    condition=df["RespID"].duplicated(keep=False),
    question="RespID",
    rule_name="ID_CHECK",
    error_type="duplicate_id",
    expected="unique RespID",
)
report("RespID: Duplicate ID Check", res_respid_dup)


# -----------------------------------------------------------------------------
# Q1: Single Response (Ask-all, Gender: 1=Male, 2=Female)
# -----------------------------------------------------------------------------
res_q1 = validator.sr(
    question="Q1",
    valid_values=[1, 2]
)
report("Q1: Gender (SR)", res_q1)


# -----------------------------------------------------------------------------
# Q2: Age validation logic
# -----------------------------------------------------------------------------
condition_filter1 = (df["Q1"] == 1) & (~df["Q2"].isin(lst_no(18, 100)))
condition_filter2 = (df["Q1"] == 2) & (~df["Q2"].isin(lst_no(18, 80)))
condition_filter3 = df["Q2"].isna()

res_q2 = validator.custom_check(
    condition=condition_filter1 | condition_filter2 | condition_filter3,
    question="Q2",
    rule_name="LOGIC_CHECK",
    error_type="invalid_age_for_gender",
    expected="Male: 18-100, Female: 18-80",
    display_columns=["Q1", "Q2"],
)
report("Q2: Age Logic Check", res_q2)


# -----------------------------------------------------------------------------
# Q3: Single Response (Ask-all, Code: 1, 2)
# -----------------------------------------------------------------------------
res_q3 = validator.sr(question="Q3", valid_values=[1, 2])
report("Q3 (SR)", res_q3)


# -----------------------------------------------------------------------------
# Q4: Single Response (Codes 1 to 4 + 97)
# -----------------------------------------------------------------------------
res_q4 = validator.sr(question="Q4", valid_values=lst_no(1, 4) + [97])
report("Q4 (SR)", res_q4)


# -----------------------------------------------------------------------------
# Q5: Multiple Response with Exclusive (Q5_1 to Q5_6, Exclusive: Q5_7)
# -----------------------------------------------------------------------------
q5_vars = [f"Q5_{i}" for i in lst_no(1, 6)]
res_q5 = validator.multi(questions=q5_vars, exclusive=["Q5_7"])
report("Q5 (MULTI with Exclusive)", res_q5)


# -----------------------------------------------------------------------------
# Q6: Conditional Multiple Response (Asked if any Q5_1..Q5_6 == 1)
# -----------------------------------------------------------------------------
df["QFILTER"] = 0
df.loc[df[q5_vars].eq(1).any(axis=1), "QFILTER"] = 1

q6_vars = [f"Q6_{i}" for i in lst_no(1, 6)]
res_q6 = validator.multi(
    questions=q6_vars,
    exclusive=["Q6_7"],
    routing_column="QFILTER"
)
report("Q6 (Conditional MULTI)", res_q6)


# -----------------------------------------------------------------------------
# Q7: Looped Single Response (Q7_1..Q7_6 asked if corresponding Q6_i == 1)
# -----------------------------------------------------------------------------
for i in lst_no(1, 6):
    df["QFILTER"] = 0
    df.loc[df[f"Q6_{i}"] == 1, "QFILTER"] = 1
    res_q7 = validator.sr(
        question=f"Q7_{i}",
        valid_values=lst_no(1, 6),
        routing_column="QFILTER"
    )
    report(f"Q7_{i} (Looped SR)", res_q7)


# -----------------------------------------------------------------------------
# Q8: Multiple Response (Q8_1..Q8_9 + Q8_98, Exclusive: Q8_97)
# -----------------------------------------------------------------------------
q8_vars = [f"Q8_{i}" for i in lst_no(1, 9)] + ["Q8_98"]
res_q8 = validator.multi(questions=q8_vars, exclusive=["Q8_97"])
report("Q8 (MULTI)", res_q8)


# -----------------------------------------------------------------------------
# Q8_oth: Open-Ended Text (Asked if Q8_97 == 1)
# -----------------------------------------------------------------------------
df["QFILTER"] = 0
df.loc[df["Q8_97"] == 1, "QFILTER"] = 1
res_q8_oth = validator.oe_text(
    questions="Q8_oth",
    routing_column="QFILTER"
)
report("Q8_oth (Conditional OE Text)", res_q8_oth)


# -----------------------------------------------------------------------------
# Q9: Grid Question (Q9_1..Q9_5 with rating scale 1 to 5)
# -----------------------------------------------------------------------------
df["QFILTER"] = 0
df.loc[df[[f"Q8_{i}" for i in lst_no(1, 9)] + ["Q8_97"]].eq(1).any(axis=1), "QFILTER"] = 1

q9_vars = [f"Q9_{i}" for i in lst_no(1, 5)]
res_q9 = validator.grid(
    questions=q9_vars,
    valid_codes=[1, 2, 3, 4, 5],
    routing_column="QFILTER"
)
report("Q9 (Grid Rating 1-5)", res_q9)


# -----------------------------------------------------------------------------
# Q10: Conditional Single Response (Asked if Q4 between 1 and 4)
# -----------------------------------------------------------------------------
df["QFILTER"] = 0
df.loc[df["Q4"].between(1, 4), "QFILTER"] = 1
res_q10 = validator.sr(
    question="Q10",
    valid_values=lst_no(1, 5),
    routing_column="QFILTER"
)
report("Q10 (Conditional SR)", res_q10)


# -----------------------------------------------------------------------------
# Q11: Multiple Response (Q11_1..Q11_7, Exclusive: Q11_97)
# -----------------------------------------------------------------------------
q11_vars = [f"Q11_{i}" for i in lst_no(1, 7)]
res_q11 = validator.multi(questions=q11_vars, exclusive=["Q11_97"])
report("Q11 (MULTI)", res_q11)


# -----------------------------------------------------------------------------
# Q12: Single Response (Ask-all, Codes 1 to 5)
# -----------------------------------------------------------------------------
res_q12 = validator.sr(question="Q12", valid_values=lst_no(1, 5))
report("Q12 (SR)", res_q12)


# -----------------------------------------------------------------------------
# Q13: Multiple Response (Q13_1..Q13_8)
# -----------------------------------------------------------------------------
q13_vars = [f"Q13_{i}" for i in lst_no(1, 8)]
res_q13 = validator.multi(questions=q13_vars)
report("Q13 (MULTI)", res_q13)


# -----------------------------------------------------------------------------
# Q13_oth: Open-Ended Text (Asked if Q13_8 == 1)
# -----------------------------------------------------------------------------
df["QFILTER"] = 0
df.loc[df["Q13_8"] == 1, "QFILTER"] = 1
res_q13_oth = validator.oe_text(
    questions="Q13_oth",
    routing_column="QFILTER"
)
report("Q13_oth (Conditional OE Text)", res_q13_oth)


# -----------------------------------------------------------------------------
# Q14_text: Open-Ended Text (Ask-all)
# -----------------------------------------------------------------------------
res_q14 = validator.oe_text(questions="Q14_text")
report("Q14_text (Ask-all OE Text)", res_q14)


# -----------------------------------------------------------------------------
# Final QC Summary & Deliverable Generation via ValidationReport
# -----------------------------------------------------------------------------
qc_report = ValidationReport(results)

print("=" * 60)
print(f"QC VALIDATION SUMMARY: {qc_report.total_rules} rules evaluated")
print(f"Passed: {qc_report.passed_rules} | Failed: {qc_report.failed_rules} | Total Errors: {qc_report.total_errors}")
print("=" * 60)

# Export QC deliverables
output_dir = DATA_DIR / "outputs"
output_dir.mkdir(parents=True, exist_ok=True)

def safe_export(export_func, file_path, name):
    try:
        return export_func(file_path)
    except PermissionError:
        fallback = file_path.with_name(f"{file_path.stem}_latest{file_path.suffix}")
        print(f"[Notice] '{file_path.name}' is open in another program. Exporting to: '{fallback.name}'")
        return export_func(fallback)

xlsx_path = safe_export(qc_report.to_excel, output_dir / "survey_qc_report.xlsx", "Excel")
csv_path = safe_export(qc_report.to_csv, output_dir / "survey_qc_errors.csv", "CSV")
txt_path = safe_export(qc_report.to_txt, output_dir / "survey_qc_report.txt", "TXT")

print(f"\nGenerated QC Deliverables:")
print(f"  - Excel: {xlsx_path}")
print(f"  - CSV:   {csv_path}")
print(f"  - TXT:   {txt_path}")

