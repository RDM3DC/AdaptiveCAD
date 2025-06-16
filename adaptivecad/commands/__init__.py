"""Convenience exports for command classes used in the GUI playground."""

from ..command_defs import (
    BaseCmd,
    Feature,
    DOCUMENT,
    rebuild_scene,
    NewBoxCmd,
    ExportAmaCmd,
    RevolveCmd,
    ExportStlCmd,
    ExportGCodeCmd,
    ExportGCodeDirectCmd,
    MoveCmd,
    UnionCmd,
    CutCmd,
    ScaleCmd,
    NewNDBoxCmd,
    NewNDFieldCmd,
    NewBezierCmd,
    NewBSplineCmd,
    NewBallCmd,
    NewTorusCmd,
    NewConeCmd,
    _require_command_modules,
)

try:
    from .pi_square_cmd import PiSquareCmd
    from .draped_sheet_cmd import DrapedSheetCmd
except Exception:  # optional OCC deps may be missing
    PiSquareCmd = None
    DrapedSheetCmd = None

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
    "_require_command_modules",
]

if PiSquareCmd is not None:
    __all__.append("PiSquareCmd")
if DrapedSheetCmd is not None:
    __all__.append("DrapedSheetCmd")
