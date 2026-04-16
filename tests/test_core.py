# tests/test_core.py

import pandas as pd
from pandasdv.core import (
    lst_no
)

# 🔹 TEST: lst_no (simple function)
def test_lst_no_range():
    assert lst_no(1, 3) == [1, 2, 3]


def test_lst_no_single():
    assert lst_no(5) == [5]


