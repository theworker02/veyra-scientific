"""Veyra Scientific — a computational laboratory for Cursor."""

from veyra.core import VERSION, Check, Metric, VeyraResult, render_instrument
from veyra.verify import assert_scientific

__version__ = VERSION
__all__ = [
    "Check",
    "Metric",
    "VeyraResult",
    "assert_scientific",
    "render_instrument",
    "__version__",
]
