"""Command definitions for AdaptiveCAD."""
from __future__ import annotations

# Re-export everything from the main command_defs module
from ..command_defs import *

# Also export from submodules
from .slice_to_gcode import SliceToGCodeCmd

# Define DOCUMENT as a global list to store features or objects
DOCUMENT = []

__all__ = [
    "SliceToGCodeCmd",
]
