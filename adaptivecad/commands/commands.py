from adaptivecad.import_conformal import import_mesh_shape, conform_bspline_surface
from OCC.Core.GeomConvert import geomconvert_SurfaceToBSplineSurface
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from PySide6.QtWidgets import QFileDialog, QInputDialog
import time, os
from adaptivecad.command_defs import BaseCmd, DOCUMENT, rebuild_scene

class ImportConformalCmd(BaseCmd):
    """Import an STL/STEP file, fit B‑spline faces, and πₐ‑conform them."""

    title = "Import πₐ"

    def run(self, mw):
        self.activate()
    def activate(self):
        # --- 1. Pick a file --------------------------------------------------
        filename, _ = QFileDialog.getOpenFileName(
            None, "Select mesh to import", "", "Mesh (*.stl *.step *.stp)"
        )
        if not filename:
            return

        # --- 2. Ask for κ ----------------------------------------------------
        kappa, ok = QInputDialog.getDouble(
            None, "πₐ curvature κ",
            "Enter κ (0.1 = very warped … 1.0 = gentle):", 1.0, 0.01, 10.0, 2
        )
        if not ok:
            return

        # --- 3. Run pipeline -------------------------------------------------
        self.import_and_conform(filename, kappa)

    def import_and_conform(self, path: str, kappa: float) -> None:
        tic = time.perf_counter()
        shape = import_mesh_shape(path)
        load_s = time.perf_counter() - tic
        # Convert every face to a B‑spline surface
        bspline_faces = []
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        from OCC.Core.BRep import BRep_Tool
        while exp.More():
            face = exp.Current()
            bsurf = geomconvert_SurfaceToBSplineSurface(
                BRep_Tool.Surface(face)
            )
            bspline_faces.append(bsurf)
            exp.Next()
        fit_s = time.perf_counter() - tic - load_s
        # πₐ‑conform each surface
        for i, bs in enumerate(bspline_faces, 1):
            conform_bspline_surface(bs, kappa)
            print(f"[πₐ] Conformed face {i}/{len(bspline_faces)}")
        wrap_s = time.perf_counter() - tic - load_s - fit_s
        # Re‑build into a compound shape for display
        builder, comp = TopoDS_Builder(), TopoDS_Compound()
        builder.MakeCompound(comp)
        for bs in bspline_faces:
            builder.Add(comp, BRepBuilderAPI_MakeFace(bs).Face())
        DOCUMENT.add_shape(comp)
        rebuild_scene()
        total = time.perf_counter() - tic
        print(
            f"Imported '{os.path.basename(path)}' "
            f"(load {load_s:.2f}s, fit {fit_s:.2f}s, πₐ {wrap_s:.2f}s, total {total:.2f}s)"
        )
