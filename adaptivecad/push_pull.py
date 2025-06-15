from __future__ import annotations
from typing import TYPE_CHECKING

from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape
from OCC.Core.gp import gp_Vec, gp_Dir
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder

from adaptivecad.commands import BaseCmd, Feature, DOCUMENT, rebuild_scene

if TYPE_CHECKING:
    from adaptivecad.gui.playground import MainWindow # To avoid circular import

class PushPullFeatureCmd(BaseCmd):
    title = "Push-Pull Face"

    def __init__(self):
        super().__init__()
        self.selected_face: TopoDS_Face | None = None
        self.original_shape: TopoDS_Shape | None = None
        self.original_feature_index: int | None = None
        self.preview_shape: TopoDS_Shape | None = None
        self.is_planar_face: bool = False
        self.face_normal_or_axis: gp_Dir | None = None
        self.current_offset_distance: float = 0.0

    def pick_face(self, mw: 'MainWindow', shape: TopoDS_Shape, face: TopoDS_Face):
        """Called when a face is picked in Push-Pull mode."""
        self.selected_face = face
        self.original_shape = shape # The shape the face belongs to

        # Find the original feature in DOCUMENT
        for i, feat in enumerate(DOCUMENT):
            if feat.shape.IsSame(self.original_shape):
                self.original_feature_index = i
                break
        
        if self.original_feature_index is None:
            print("Error: Could not find original shape in document for Push-Pull.")
            mw.exit_push_pull_mode() # Or some other error handling
            return

        # Determine face type and direction
        adaptor = BRepAdaptor_Surface(self.selected_face, True)
        surface_type = adaptor.GetType()

        if surface_type == GeomAbs_Plane:
            self.is_planar_face = True
            plane = adaptor.Plane()
            self.face_normal_or_axis = plane.Axis().Direction()
            print(f"Push-Pull: Picked planar face. Normal: {self.face_normal_or_axis.X()},{self.face_normal_or_axis.Y()},{self.face_normal_or_axis.Z()}")
        elif surface_type == GeomAbs_Cylinder:
            self.is_planar_face = False # It's a cylindrical face, offset will change radius
            cylinder = adaptor.Cylinder()
            self.face_normal_or_axis = cylinder.Axis().Direction() # Axis of the cylinder
            print(f"Push-Pull: Picked cylindrical face. Axis: {self.face_normal_or_axis.X()},{self.face_normal_or_axis.Y()},{self.face_normal_or_axis.Z()}")
        else:
            print(f"Push-Pull: Selected face type ({surface_type}) not supported for Push-Pull.")
            mw.exit_push_pull_mode()
            return
        
        mw.win.statusBar().showMessage("Push-Pull: Drag mouse to offset face, Enter to commit, Esc to cancel.")

    def update_preview(self, mw: 'MainWindow', offset_distance: float):
        if not self.selected_face or not self.original_shape or self.face_normal_or_axis is None:
            return

        self.current_offset_distance = offset_distance
        # print(f"Push-Pull: Updating preview with offset {offset_distance}")

        # Remove previous preview if any
        if self.preview_shape and mw.view._display.Context.IsDisplayed(self.preview_shape):
            mw.view._display.Context.Remove(self.preview_shape, False) # Don't update immediately
        self.preview_shape = None

        try:
            if self.is_planar_face:
                # For planar faces, BRepOffsetAPI_MakeOffsetShape might be complex for a simple push-pull.
                # A simpler approach for a single face is to make a prism (extrusion).
                # The direction vector for MakePrism needs to be scaled by the offset distance.
                offset_vector = gp_Vec(self.face_normal_or_axis.XYZ()) * offset_distance
                # Create a prism from the selected face
                # Note: This creates a new solid from the face. We then need to Boolean it.
                extruded_tool = BRepPrimAPI_MakePrism(self.selected_face, offset_vector).Shape()
            else: # Cylindrical face - attempt to offset (effectively changing radius)
                # This is more complex. BRepOffsetAPI_MakeOffsetShape is the way.
                # A positive offset should expand, negative should shrink.
                # The offset is applied to the whole shape, but we are interested in the effect on the face.
                # This is a simplification; true radial offset of just one cylinder face is tricky.
                # For now, let's assume we are offsetting the entire original shape and see the result.
                # This will likely offset ALL faces of the original_shape.
                # A more targeted approach would be needed for robust cylindrical push-pull.
                
                # Create an offset shape of the *original_shape* containing the face
                # This is not ideal as it offsets the whole shape. 
                # A true push-pull on a cylinder face would involve reconstructing the cylinder or using advanced modeling.
                # For MVP, let's try BRepOffsetAPI_MakeOffsetShape on the face itself, which might create a shell/solid.
                offset_op = BRepOffsetAPI_MakeOffsetShape(self.selected_face, offset_distance, 1.0e-5) # Small tolerance
                offset_op.Build()
                if offset_op.IsDone():
                    extruded_tool = offset_op.Shape()
                else:
                    print("Push-Pull: Failed to create offset shape for cylindrical face.")
                    return

            # Perform Boolean operation with the original shape
            # We need to decide if it's a FUSE (pulling out) or CUT (pushing in)
            # This depends on the sign of offset_distance and potentially the face normal relative to material.
            # For simplicity: positive offset_distance = FUSE, negative = CUT
            # This logic might need to be refined based on face orientation.
            if offset_distance > 0:
                final_preview = BRepAlgoAPI_Fuse(self.original_shape, extruded_tool).Shape()
            elif offset_distance < 0:
                # For cut, the extruded_tool might need to be sufficiently large or positioned correctly.
                # If extruded_tool is made from the face and extruded inwards, it should work.
                final_preview = BRepAlgoAPI_Cut(self.original_shape, extruded_tool).Shape()
            else: # No offset
                final_preview = self.original_shape
            
            self.preview_shape = final_preview

            # Display the preview shape (ghosted)
            if self.preview_shape:
                mw.view._display.DisplayShape(self.preview_shape, color="BLUE", transparency=0.7, update=True)
                # Hide the original shape temporarily if it's a separate object in the viewer
                # This depends on how shapes are managed. If DOCUMENT is rebuilt, this is handled.
                # For now, we assume the preview replaces the visual of the original.

        except Exception as e:
            print(f"Error during Push-Pull preview: {e}")
            if self.preview_shape and mw.view._display.Context.IsDisplayed(self.preview_shape):
                 mw.view._display.Context.Remove(self.preview_shape, True)
            self.preview_shape = None

    def commit(self, mw: 'MainWindow'):
        if not self.preview_shape or self.original_feature_index is None or self.current_offset_distance == 0:
            print("Push-Pull: Commit called but no valid preview or no offset.")
            # Restore original display if needed
            if self.preview_shape and mw.view._display.Context.IsDisplayed(self.preview_shape):
                mw.view._display.Context.Remove(self.preview_shape, False)
            if self.original_shape:
                 mw.view._display.DisplayShape(self.original_shape, update=True) # Re-display original
            mw.exit_push_pull_mode()
            return

        print(f"Push-Pull: Committing offset {self.current_offset_distance}")
        
        # Create a new Feature for the PushPull operation
        # The parameters should ideally reference the target face ID and original feature ID
        # For now, we store the delta and the type of operation.
        new_feature_name = f"PushPull_{DOCUMENT[self.original_feature_index].name}"
        params = {
            "original_feature_id": DOCUMENT[self.original_feature_index].name, # Or a unique ID
            # "target_face_index": # Need a way to identify the face robustly
            "offset_distance": self.current_offset_distance,
            "is_planar": self.is_planar_face
        }
        
        # The new shape is the preview_shape
        new_feature = Feature(name=new_feature_name, params=params, shape=self.preview_shape)

        # Replace the original feature or add a new one?
        # For true parametric history, this PushPull should be a new feature that takes the old one as input.
        # Let's add it as a new feature that modifies the previous one.
        # This means the DOCUMENT list will grow. The AMA export needs to handle this graph.
        
        # Option 1: Replace (simpler for now, but loses original parametric step)
        # DOCUMENT[self.original_feature_index] = new_feature
        
        # Option 2: Add as a new feature (better for history)
        DOCUMENT.append(new_feature)
        # If we add, the original shape should probably be hidden or removed from direct display
        # if it's not part of the new shape's construction history in the viewer.
        # rebuild_scene will handle displaying the latest features.

        # Clean up the preview display (it will be redrawn by rebuild_scene)
        if mw.view._display.Context.IsDisplayed(self.preview_shape):
            mw.view._display.Context.Remove(self.preview_shape, False) # Don't update display yet
        
        # If the original shape was displayed as a separate AIS_InteractiveObject, remove it.
        # This depends on how rebuild_scene works. If it erases all and redraws from DOCUMENT, it's fine.
        # ais_original = mw.view._display.Context.GetDetectedAIS() # This is not reliable here.
        # Need a map from TopoDS_Shape to AIS_InteractiveObject if managing them individually.
        # For now, rely on rebuild_scene to clear and draw the new state of DOCUMENT.

        rebuild_scene(mw.view._display)
        mw.win.statusBar().showMessage(f"Push-Pull committed: {self.current_offset_distance} mm", 3000)
        mw.exit_push_pull_mode()

    def cancel(self, mw: 'MainWindow'):
        print("Push-Pull: Cancelled.")
        if self.preview_shape and mw.view._display.Context.IsDisplayed(self.preview_shape):
            mw.view._display.Context.Remove(self.preview_shape, False)
        
        # Ensure the original shape is visible if it was hidden or replaced by preview
        # This is best handled by simply rebuilding the scene to the state before PP started.
        # However, if DOCUMENT was modified, this won't work directly.
        # For now, if original_shape exists, ensure it's displayed.
        # This logic is tricky if the original shape itself was a preview from another command.
        # The robust way is to not modify DOCUMENT until commit.
        if self.original_shape and not mw.view._display.Context.IsDisplayed(self.original_shape):
             # This might re-add it if rebuild_scene is not called. Best to let rebuild_scene handle it.
             pass 

        rebuild_scene(mw.view._display) # Re-render the document as it was before PP attempt
        mw.exit_push_pull_mode()

    def run(self, mw: 'MainWindow') -> None:
        # This command is not run like others (e.g. from toolbar).
        # It's activated by a mode change in the MainWindow.
        # MainWindow will call pick_face, update_preview, commit, or cancel.
        print("PushPullFeatureCmd.run() called - this command is mode-based.")
        pass

# Helper to get face from AIS_InteractiveObject if needed
# def get_face_from_ais_object(ais_object) -> TopoDS_Face | None:
#     if hasattr(ais_object, "Shape") and isinstance(ais_object.Shape(), TopoDS_Face):
#         return ais_object.Shape()
#     # More complex logic might be needed if shapes are nested
#     return None
