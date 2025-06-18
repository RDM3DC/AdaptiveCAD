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
    LoftCmd,
    SweepAlongPathCmd,
    ShellCmd,
    IntersectCmd,
    _require_command_modules,
)

try:
    from .pi_square_cmd import PiSquareCmd
    from .draped_sheet_cmd import DrapedSheetCmd
    from .import_conformal import ImportConformalCmd
except Exception:  # optional OCC deps may be missing
    PiSquareCmd = None
    DrapedSheetCmd = None
    # Do not assign ImportConformalCmd = None; let import fail if missing

try:
    from .cosmic_curve_cmds import (
        BizarreCurveCmd,
        CosmicSplineCmd,
        NDFieldExplorerCmd,
    )
except Exception:
    BizarreCurveCmd = None
    CosmicSplineCmd = None
    NDFieldExplorerCmd = None

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

if BizarreCurveCmd is not None:
    __all__.append("BizarreCurveCmd")
if CosmicSplineCmd is not None:
    __all__.append("CosmicSplineCmd")
if NDFieldExplorerCmd is not None:
    __all__.append("NDFieldExplorerCmd")
