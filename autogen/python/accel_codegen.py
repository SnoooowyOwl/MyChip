"""Compatibility imports for the manual Python assembly modules.

New code should import from `autogen.python.rv32_emit` and
`autogen.python.accelerator_api` directly.
"""

from __future__ import annotations

try:
    from .accelerator_api import *  # noqa: F401,F403
    from .rv32_emit import *  # noqa: F401,F403
except ImportError:  # Allows direct imports from the autogen directory.
    from accelerator_api import *  # type: ignore # noqa: F401,F403
    from rv32_emit import *  # type: ignore # noqa: F401,F403
