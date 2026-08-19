"""
pandasdv — Survey Data Validator for Pandas.

Recommended (new) API::

    from pandasdv import SurveyValidator
    from pandasdv.io import load_data
    from pandasdv import ChunkProcessor

Legacy (backward-compatible) API::

    from pandasdv import initial_setup, SR, MULTI, GRID, RANK_CHECK
    from pandasdv import OETEXT, NULL_CHECK, FLT_LIST, lst_no, output_setup
"""

# ---------------------------------------------------------------------------
# New class-based public API
# ---------------------------------------------------------------------------
from .validator import SurveyValidator
from .results import ValidationResult, build_result
from .processor import ChunkProcessor
from .report import ValidationReport
from .io import load_data

# ---------------------------------------------------------------------------
# Backward-compatible function-based API (re-exported from compat.py)
# ---------------------------------------------------------------------------
from .compat import (  # noqa: F401
    FLT_LIST,
    GRID,
    MULTI,
    NULL_CHECK,
    OETEXT,
    RANK_CHECK,
    SR,
    initial_setup,
    lst_no,
    output_setup,
)

__version__ = "0.2.0"
__author__ = "Naveen Chandra Cherupally"

__all__ = [
    # New API
    "SurveyValidator",
    "ValidationResult",
    "ChunkProcessor",
    "ValidationReport",
    "load_data",
    # Legacy API
    "SR",
    "MULTI",
    "GRID",
    "RANK_CHECK",
    "OETEXT",
    "NULL_CHECK",
    "FLT_LIST",
    "initial_setup",
    "output_setup",
    "lst_no",
]
