"""
Backward-compatibility shims for the original function-based API.

These wrappers allow existing scripts that use the old ``pandasdv`` API to
continue working without modification.  They delegate to the original
``core.py`` and ``io_utils.py`` implementations, which are kept untouched.

Migration guide
---------------
The old global-state API is still functional but is now deprecated.
New code should use :class:`~pandasdv.validator.SurveyValidator` directly::

    # Old (still works):
    from pandasdv import initial_setup, SR, MULTI
    df = initial_setup("survey.sav")
    SR(Rout='QFILTER', QVAR='Q1', RNG=[1, 2, 3])

    # New (recommended):
    from pandasdv import SurveyValidator
    from pandasdv.io import load_data
    df = load_data("survey.sav")
    validator = SurveyValidator(df)
    result = validator.sr("Q1", valid_values=[1, 2, 3])
    print(result.summary())

.. warning::
   The old API relies on a global ``df`` variable in ``io_utils`` and
   redirects ``sys.stdout`` during validation.  It is retained for backward
   compatibility only and will not receive new features.
"""

from __future__ import annotations

# Re-export original implementations unchanged.
# core.py and io_utils.py are left untouched so existing scripts keep working.
from .core import (  # noqa: F401
    FLT_LIST,
    GRID,
    MULTI,
    NULL_CHECK,
    OETEXT,
    RANK_CHECK,
    SR,
    lst_no,
)
from .io_utils import (  # noqa: F401
    initial_setup,
    output_setup,
)
