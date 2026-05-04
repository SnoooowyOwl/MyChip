"""Compatibility imports for the split autogen modules.

New code should import from `rv32_emit.py` and `accelerator_api.py` directly.
"""

from __future__ import annotations

try:
    from .accelerator_api import *  # noqa: F401,F403
    from .rv32_emit import *  # noqa: F401,F403
except ImportError:  # Allows direct imports from the autogen directory.
    from accelerator_api import *  # type: ignore # noqa: F401,F403
    from rv32_emit import *  # type: ignore # noqa: F401,F403
