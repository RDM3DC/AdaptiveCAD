from OCC.Core.gp import gp_Pnt
from OCC.Core.AIS import AIS_Point, AIS_Shape
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Display.OCCViewer import Viewer3d

class SnapStrategy:
    def __init__(self, viewer_display):
        self.viewer_display = viewer_display
        self.is_active = False

    def snap(self, x, y) -> gp_Pnt | None:
        # Base snap method, to be overridden by subclasses
        return None

    def activate(self):
        self.is_active = True

    def deactivate(self):
        self.is_active = False

    def toggle(self):
        self.is_active = not self.is_active
        return self.is_active

class GridStrategy(SnapStrategy):
    def __init__(self, viewer_display, grid_step=10.0, snap_increment_divisor=10):
        super().__init__(viewer_display)
        self.grid_step = grid_step  # e.g., 10.0 mm
        self.snap_increment = grid_step / snap_increment_divisor # e.g., 1.0 mm
        self.name = "GridSnap"

    def snap(self, x_screen, y_screen) -> gp_Pnt | None:
        if not self.is_active:
            return None

        # Convert screen coordinates to 3D point on the XY plane (for now)
        # This needs to be more sophisticated to handle view projection correctly
        # and snap to the dynamic grid plane.
        # For MVP, let's assume snapping on XY plane view from Z axis.
        pnt_3d_world = self.viewer_display.View.ConvertToGrid(x_screen, y_screen)
        
        # Snap to the snap_increment
        snapped_x = round(pnt_3d_world.X() / self.snap_increment) * self.snap_increment
        snapped_y = round(pnt_3d_world.Y() / self.snap_increment) * self.snap_increment
        snapped_z = round(pnt_3d_world.Z() / self.snap_increment) * self.snap_increment # Or keep Z as is, depending on grid plane

        # For now, assume grid is on XY plane, so Z is 0 or based on active sketch plane
        # Let's simplify and snap Z as well, or keep it from the converted point
        # For a true dynamic grid, this Z would be on the grid plane.
        snapped_pnt = gp_Pnt(snapped_x, snapped_y, pnt_3d_world.Z()) 
        # print(f"GridSnap: Screen ({x_screen},{y_screen}) -> World ({pnt_3d_world.X():.2f},{pnt_3d_world.Y():.2f},{pnt_3d_world.Z():.2f}) -> Snapped ({snapped_x:.2f},{snapped_y:.2f},{snapped_pnt.Z():.2f})")
        return snapped_pnt

    def set_grid_step(self, step):
        self.grid_step = step
        self.snap_increment = step / 10 # As per blueprint

class SnapManager:
    def __init__(self, viewer_display):
        self.viewer_display = viewer_display
        self.strategies: list[SnapStrategy] = []
        self.snap_tolerance_pixels = 8 # As per blueprint
        self._current_snap_marker: list[AIS_Shape] | None = None

    def add_strategy(self, strategy: SnapStrategy):
        self.strategies.append(strategy)

    def get_strategy(self, name: str) -> SnapStrategy | None:
        for s in self.strategies:
            if hasattr(s, 'name') and s.name == name:
                return s
        return None

    def on_mouse_move(self, x_screen, y_screen):
        snapped_point = None
        active_strategy = None

        for strategy in self.strategies:
            if strategy.is_active:
                # print(f"Trying strategy: {strategy.name if hasattr(strategy, 'name') else strategy.__class__.__name__}")
                current_snap = strategy.snap(x_screen, y_screen)
                if current_snap:
                    snapped_point = current_snap
                    active_strategy = strategy
                    break # First active strategy that snaps wins

        if self._current_snap_marker:
            for marker in self._current_snap_marker:
                self.viewer_display.Context.Remove(marker, True)
            self._current_snap_marker = None

        if snapped_point:
            # print(f"SnapManager: Snapped to {snapped_point.X():.2f}, {snapped_point.Y():.2f}, {snapped_point.Z():.2f} using {active_strategy.name if hasattr(active_strategy, 'name') else active_strategy.__class__.__name__}")
            self._current_snap_marker = create_crosshair_at_point(snapped_point)
            for marker in self._current_snap_marker:
                self.viewer_display.Context.Display(marker, True)
        
        return snapped_point

    def toggle_grid_snap(self) -> bool:
        grid_strategy = self.get_strategy("GridSnap")
        if grid_strategy:
            is_now_active = grid_strategy.toggle()
            print(f"Grid Snap {'activated' if is_now_active else 'deactivated'}")
            if not is_now_active and self._current_snap_marker: # Clear marker if grid snap deactivated
                for marker in self._current_snap_marker:
                    self.viewer_display.Context.Remove(marker, True)
                self._current_snap_marker = None
            return is_now_active
        return False

    def update_grid_parameters_from_zoom(self, view_magnification):
        # Dynamic Grid Rules: 10x decade scale
        # This is a simplified logic. A more robust way would be to get the
        # actual visible extent in world coordinates.
        grid_strategy = self.get_strategy("GridSnap")
        if not grid_strategy or not isinstance(grid_strategy, GridStrategy):
            return

        # Example logic:
        if view_magnification > 500: # Zoomed in a lot
            new_step = 0.1
        elif view_magnification > 100:
            new_step = 1.0
        elif view_magnification > 20:
            new_step = 10.0
        else: # Zoomed out
            new_step = 100.0
        
        if grid_strategy.grid_step != new_step:
            grid_strategy.set_grid_step(new_step)
            # print(f"Grid step updated to: {new_step} mm due to zoom: {view_magnification}")

            # TODO: Re-display the grid if it's visually represented
            # self.viewer_display.View.Grid().SetXStep(new_step)
            # self.viewer_display.View.Grid().SetYStep(new_step)
            # self.viewer_display.View.Update() # or similar to refresh grid visuals
            pass


def create_crosshair_at_point(point: gp_Pnt, size: float = 2.0) -> list[AIS_Shape]:
    """Create a simple two-line crosshair at ``point``."""
    half = size / 2.0
    edge_x = BRepBuilderAPI_MakeEdge(
        gp_Pnt(point.X() - half, point.Y(), point.Z()),
        gp_Pnt(point.X() + half, point.Y(), point.Z()),
    ).Edge()
    edge_y = BRepBuilderAPI_MakeEdge(
        gp_Pnt(point.X(), point.Y() - half, point.Z()),
        gp_Pnt(point.X(), point.Y() + half, point.Z()),
    ).Edge()
    return [AIS_Shape(edge_x), AIS_Shape(edge_y)]



