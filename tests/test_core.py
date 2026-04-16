import pandas as pd

from pandasdv.core import (
    lst_no,
    FLT_LIST,
    SR  
)

# 🔹 TEST: lst_no
def test_lst_no_range():
    assert lst_no(1, 3) == [1, 2, 3]

def test_lst_no_single():
    assert lst_no(5) == [5]


# 🔹 TEST: FLT_LIST (basic)
def test_flt_list_basic(monkeypatch, capsys):
    df = pd.DataFrame({
        "ID": [1, 2, 3],
        "Q1": [1, None, 3]
    })

    # Mock global df
    monkeypatch.setattr("pandasdv.io_utils.df", df)

    cond = df["Q1"].isna()

    FLT_LIST(COND=cond, LIST=["ID", "Q1"])

    captured = capsys.readouterr()

    assert "Number of cases listed: 1" in captured.out

def test_sr_runs(monkeypatch, capsys):
    from pandasdv.core import SR

    df = pd.DataFrame({
        "ID": [1, 2, 3],
        "Q1": [1, 99, None]
    })

    monkeypatch.setattr("pandasdv.io_utils.df", df)

    SR(QVAR="Q1", RNG=[1,2,3])

    captured = capsys.readouterr()

    assert "Q1:" in captured.out    