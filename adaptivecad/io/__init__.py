"""IO utilities for AdaptiveCAD."""

from .ama_reader import read_ama, AMAFile, AMAPart
from .gcode_generator import ama_to_gcode, GCodeGenerator, SimpleMilling

# AMA writing relies on pythonocc-core. Import if available.
try:
    from .ama_writer import write_ama
except Exception:  # OCC not installed or missing deps
    write_ama = None
