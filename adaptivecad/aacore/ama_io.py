"""Convenience re-exports for AMA read/write.

The canonical implementations live in :mod:`adaptivecad.io`; this module
provides the ``adaptivecad.aacore.ama_io`` import path that several
parts of the codebase expect.
"""

from adaptivecad.io import read_ama, write_ama

__all__ = ["read_ama", "write_ama"]
