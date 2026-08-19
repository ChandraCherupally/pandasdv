"""
IO layer for pandasdv.

Provides a single ``load_data`` entry-point that dispatches to the
appropriate reader based on file extension.

Supported formats
-----------------
- ``.sav`` / ``.zsav`` — SPSS via ``pd.read_spss`` (requires ``pyreadstat``)
- ``.csv`` / ``.tsv`` — delimited text via ``pd.read_csv``
- ``.xlsx`` / ``.xls`` / ``.xlsm`` — Excel via ``pd.read_excel``

Example
-------
::

    from pandasdv.io import load_data

    df = load_data("survey.sav")
    df = load_data("survey.csv")
    df = load_data("survey.xlsx", sheet_name="Data")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SPSS_EXTS = {".sav", ".zsav"}
_CSV_EXTS = {".csv", ".tsv"}
_EXCEL_EXTS = {".xlsx", ".xls", ".xlsm"}


def load_data(
    path: str | Path,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Load survey data from a file into a :class:`pandas.DataFrame`.

    Parameters
    ----------
    path : str or Path
        Path to the data file.
    columns : list[str], optional
        Subset of columns to load (supported for CSV via ``usecols``).
        Not supported for SPSS; all columns are loaded.
    **kwargs
        Extra keyword arguments forwarded to the underlying reader
        (``pd.read_spss``, ``pd.read_csv``, or ``pd.read_excel``).

    Returns
    -------
    pd.DataFrame

    Raises
    ------
    ValueError
        If the file extension is not recognised.
    FileNotFoundError
        If the file does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    ext = p.suffix.lower()

    if ext in _SPSS_EXTS:
        return _load_spss(p, **kwargs)
    if ext in _CSV_EXTS:
        return _load_csv(p, columns=columns, **kwargs)
    if ext in _EXCEL_EXTS:
        return _load_excel(p, columns=columns, **kwargs)

    raise ValueError(
        f"Unsupported file extension '{ext}'. "
        f"Supported: {sorted(_SPSS_EXTS | _CSV_EXTS | _EXCEL_EXTS)}"
    )


# ---------------------------------------------------------------------------
# Private readers
# ---------------------------------------------------------------------------

def _load_spss(path: Path, **kwargs: Any) -> pd.DataFrame:
    """Load an SPSS .sav file.

    Uses ``pd.read_spss`` with ``convert_categoricals=False`` to preserve
    numeric codes, matching the original pandasdv behaviour.

    The first (ID) column is cast to ``int`` where possible, also
    matching the original ``initial_setup`` behaviour.
    """
    kwargs.setdefault("convert_categoricals", False)
    df = pd.read_spss(str(path), **kwargs)
    # Cast ID column to int when it contains whole numbers (original behaviour)
    id_col = df.columns[0]
    try:
        df[id_col] = df[id_col].astype(int)
    except (ValueError, TypeError):
        pass
    return df


def _load_csv(
    path: Path,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Load a CSV or TSV file."""
    if columns is not None:
        kwargs.setdefault("usecols", columns)
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    kwargs.setdefault("sep", sep)
    return pd.read_csv(path, **kwargs)


def _load_excel(
    path: Path,
    columns: list[str] | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Load an Excel file."""
    if columns is not None:
        kwargs.setdefault("usecols", columns)
    return pd.read_excel(path, **kwargs)
