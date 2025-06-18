"""Convenience exports for command classes used in the GUI playground."""

import importlib.util
import sys
import os

# Load command_defs.py module directly to avoid package naming conflict
command_defs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'command_defs.py')
spec = importlib.util.spec_from_file_location("command_defs_module", command_defs_path)
command_defs = importlib.util.module_from_spec(spec)
sys.modules['command_defs_module'] = command_defs
spec.loader.exec_module(command_defs)

# Import all the symbols we need from the module
BaseCmd = command_defs.BaseCmd
Feature = command_defs.Feature
DOCUMENT = command_defs.DOCUMENT
rebuild_scene = command_defs.rebuild_scene
NewBoxCmd = command_defs.NewBoxCmd
ExportAmaCmd = command_defs.ExportAmaCmd
RevolveCmd = command_defs.RevolveCmd
ExportStlCmd = command_defs.ExportStlCmd
ExportGCodeCmd = command_defs.ExportGCodeCmd
ExportGCodeDirectCmd = command_defs.ExportGCodeDirectCmd
MoveCmd = command_defs.MoveCmd
UnionCmd = command_defs.UnionCmd
CutCmd = command_defs.CutCmd
ScaleCmd = command_defs.ScaleCmd
NewNDBoxCmd = command_defs.NewNDBoxCmd
NewNDFieldCmd = command_defs.NewNDFieldCmd
NewBezierCmd = command_defs.NewBezierCmd
NewBSplineCmd = command_defs.NewBSplineCmd
NewBallCmd = command_defs.NewBallCmd
NewTorusCmd = command_defs.NewTorusCmd
NewConeCmd = command_defs.NewConeCmd
LoftCmd = command_defs.LoftCmd
SweepAlongPathCmd = command_defs.SweepAlongPathCmd
ShellCmd = command_defs.ShellCmd
IntersectCmd = command_defs.IntersectCmd
_require_command_modules = command_defs._require_command_modules

try:
    from .pi_square_cmd import PiSquareCmd
    from .draped_sheet_cmd import DrapedSheetCmd
    from .import_conformal import ImportConformalCmd
except Exception:  # optional OCC deps may be missing
    PiSquareCmd = None
    DrapedSheetCmd = None
    # Do not assign ImportConformalCmd = None; let import fail if missing

__all__ = [
    "BaseCmd",
    "Feature",
    "DOCUMENT",
    "rebuild_scene",
    "NewBoxCmd",
    "ExportAmaCmd",
    "ExportStlCmd",
    "ExportGCodeCmd",
    "ExportGCodeDirectCmd",
    "RevolveCmd",
    "MoveCmd",
    "ScaleCmd",
    "UnionCmd",
    "CutCmd",
    "NewNDBoxCmd",
    "NewNDFieldCmd",
    "NewBezierCmd",
    "NewBSplineCmd",
    "NewBallCmd",
    "NewTorusCmd",
    "NewConeCmd",
    "LoftCmd",
    "SweepAlongPathCmd",
    "ShellCmd",
    "IntersectCmd",
    "_require_command_modules",
]

if PiSquareCmd is not None:
    __all__.append("PiSquareCmd")
if DrapedSheetCmd is not None:
    __all__.append("DrapedSheetCmd")
__all__.append("ImportConformalCmd")
