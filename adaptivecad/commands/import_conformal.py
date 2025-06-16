from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.GeomConvert import geomconvert_SurfaceToBSplineSurface
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TColgp import TColgp_Array2OfPnt
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

from adaptivecad.command_defs import BaseCmd, DOCUMENT, Feature, rebuild_scene
from adaptivecad.geom import pi_a_over_pi


def import_mesh_shape(file_path: str) -> TopoDS_Shape:
    """Load a STEP or STL file into a TopoDS_Shape."""
    if file_path.lower().endswith(".stl"):
        reader = StlAPI_Reader()
        shape = TopoDS_Shape()
        success = reader.Read(shape, file_path)
        if not success:
            raise RuntimeError(f"Failed to load STL: {file_path}")
        return shape
    elif file_path.lower().endswith((".step", ".stp")):
        reader = STEPControl_Reader()
        status = reader.ReadFile(file_path)
        if status != 1:
            raise RuntimeError(f"Failed to load STEP: {file_path}")
        reader.TransferRoots()
        return reader.OneShape()
    else:
        raise ValueError("Unsupported file format (only STL and STEP supported)")


def extract_bspline_faces(shape: TopoDS_Shape):
    """Return BSpline surfaces for all faces of ``shape``."""
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    faces = []
    while explorer.More():
        face = explorer.Current()
        # Ensure triangulation for the surface data
        mesher = BRepMesh_IncrementalMesh(face, 0.1)
        mesher.Perform()
        surf = BRep_Tool.Surface(face)
        bs = geomconvert_SurfaceToBSplineSurface(surf)
        faces.append(bs)
        explorer.Next()
    return faces


def conform_bspline_surface(bspline, kappa: float):
    """Scale BSpline control points using ``pi_a_over_pi``."""
    poles = bspline.Poles()
    u_count = poles.RowLength()
    v_count = poles.ColLength()
    new_poles = TColgp_Array2OfPnt(1, u_count, 1, v_count)

    for i in range(1, u_count + 1):
        for j in range(1, v_count + 1):
            pt = poles.Value(i, j)
            r = (pt.X() ** 2 + pt.Y() ** 2 + pt.Z() ** 2) ** 0.5
            scale = pi_a_over_pi(r, kappa)
            new_poles.SetValue(i, j, pt.Scaled(scale))

    bspline.SetPoles(new_poles)
    return bspline


class ImportConformalCmd(BaseCmd):
    """Import a CAD file and conform its surfaces using the \pi_a metric."""

    title = "Import Conformal"

    def run(self, mw) -> None:  # pragma: no cover - GUI integration
        from PySide6.QtWidgets import QFileDialog, QInputDialog

        path, _ = QFileDialog.getOpenFileName(
            mw.win, "Import STL or STEP", filter="CAD files (*.stl *.step *.stp)"
        )
        if not path:
            return

        kappa, ok = QInputDialog.getDouble(mw.win, "Conformal Import", "kappa:", 1.0)
        if not ok:
            return

        shape = import_mesh_shape(path)
        for bs in extract_bspline_faces(shape):
            conform_bspline_surface(bs, kappa)
            face = BRepBuilderAPI_MakeFace(bs, 1e-6).Face()
            DOCUMENT.append(Feature("Imported", {"file": path}, face))

        rebuild_scene(mw.view._display)
        mw.win.statusBar().showMessage(f"Imported: {path}")
