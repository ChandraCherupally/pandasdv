# 🧾 pandasdv — Pandas Data Validator for Survey Datasets

`pandasdv` is a lightweight Python library designed to **validate survey and structured datasets** (e.g., SPSS `.sav` files) with `pandas`.  
It provides ready-to-use validation functions for common survey question types such as **Single Response**, **Multiple Response**, **Grid**, **Ranking**, and **Open-Ended** checks.

---

## 🚀 Features

- ✅ Easy integration with `pandas`
- 📊 Supports validation of `.sav` files directly
- 🧠 Ready-to-use functions for survey logic validation:
  - `SR` — Single Response Validation
  - `MULTI` — Multiple Response Validation
  - `GRID` — Grid & Conditional Validation
  - `RANK_CHECK` — Rank Order Validation
  - `OETEXT` — Open-ended Text Validation
  - `NULL_CHECK` — Null or Blank Check
- 🧾 Automatic output logging to text file
- 🪄 Simple, readable validation results

---

## 📦 Installation

```bash
pip install pandasdv
```

*(Make sure you have `pandas` and `numpy` installed.)*

---

## 🧰 Basic Usage

```python
from pandasdv import initial_setup, SR, MULTI, GRID, RANK_CHECK, OETEXT, NULL_CHECK, FLT_LIST, lst_no
## OR use below syntax
## from pandasdv import *

# Load SPSS file (.sav)
df = initial_setup("survey_data.sav")

# Validate a single-response question
SR(Rout='QFILTER', QVAR='Q1', RNG=[1, 2, 3, 4], LIST=['Q1'])
## OR Use below syntax
## SR(Rout='QFILTER', QVAR='Q1', RNG=lst_no(1,4), LIST=['Q1'])

# Validate a multi-response question
MULTI(Rout='QFILTER', QVAR=['Q2_1', 'Q2_2', 'Q2_3'], QEX=['Q2_99'])
```

---

## 🧾 Core Functions

### `initial_setup(input_file)`
Reads `.sav` file and sets pandas display options.

### `output_setup(out_file='python_output.txt')`
Writes validation output to a text file and prints to console.

### `FLT_LIST(COND, LIST)`
Filters cases based on a logical condition and lists specified variables.

---

## 🧪 Validation Functions

- `SR` — Single Response Validation
- `MULTI` — Multiple Response Validation
- `GRID` — Grid Validation
- `RANK_CHECK` — Rank Order Validation
- `OETEXT` — Open-ended Text Validation
- `NULL_CHECK` — Null or Blank Validation

---

## 🧭 Example Workflow

```python
from pandasdv import *

df = initial_setup("Consumer_Brand_Preference_Data_50.sav")

# Unique ID check
FLT_LIST(COND=df['RespID'].isna() | (df['RespID'] <= 0), LIST=['RespID'])
FLT_LIST(COND=df['RespID'].duplicated(keep=False), LIST=['RespID'])

# SR validation
SR(Rout='QFILTER', QVAR='Q1', RNG=[1, 2])

# Conditional SR
df['QFILTER'] = 0
df.loc[df['Q30'].between(2,5), 'QFILTER'] = 1
SR(Rout='QFILTER', QVAR='Q30a', RNG=lst_no(1,16)+[97], LIST=['Q30a','Q30'])

# Multi Response
MULTI(QVAR=['Q5_1', 'Q5_2', 'Q5_3'], QEX=['Q5_7'])

# Grid
GRID(QVAR=['Q56_1', 'Q56_2'], COD=[1,2,3,4,5])

# Rank check
RANK_CHECK(
    Rout='QFILTER',
    QVAR=[f'Q180_Orderr{i}' for i in range(1, 6)],
    MINR=1,
    MAXR=3
)

# OE Text
OETEXT(Rout='QFILTER', QVAR='Q8_oth', LIST=['Q8_97'])

# Output results
output_setup('validation_results.txt')
```

---

## 🛠️ Notes

- Always set base filters (`Rout`) before validation for conditional questions.
- Use `lst_no(min, max)` to avoid manually writing long code lists.
- `FLT_LIST` is useful for quick debugging of any custom conditions.
- The first column in the dataset is assumed to be the respondent ID.
- Refer below github repository for sample files and and synatx files
- https://github.com/ChandraCherupally/pandasdv
---


## 🧑‍💻 Contributing

1. Fork the repository
2. Create a new branch (feature/my-feature)
3. Commit your changes
4. Open a Pull Request

## 🙌 Acknowledgements

- Built on top of pandas
- Inspired by real-world survey data quality validation workflows.

