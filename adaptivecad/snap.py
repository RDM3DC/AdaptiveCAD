import numpy as np

class SnapManager:
    def __init__(self, tol_px=12):
        self.strategies = []
        self.strategy_enabled = {}
        self.tol_px = tol_px  # screen-space tolerance (pixels)
        self.enabled = True   # master snap toggle

    def set_tolerance(self, pixels):
        """Set the snap tolerance in pixels."""
        self.tol_px = pixels

    def register(self, strategy, priority=0):
        self.strategies.append((priority, strategy))
        self.strategies.sort(key=lambda x: x[0], reverse=True)
        self.strategy_enabled[strategy.__name__] = True

    def enable_strategy(self, name: str, enabled: bool = True) -> None:
        if name in self.strategy_enabled:
            self.strategy_enabled[name] = enabled

    def toggle_strategy(self, name: str) -> bool:
        if name in self.strategy_enabled:
            self.strategy_enabled[name] = not self.strategy_enabled[name]
            return self.strategy_enabled[name]
        return False

    def is_enabled(self, name: str) -> bool:
        return self.strategy_enabled.get(name, False)

    def _screen_coords(self, view, pt):
        """Project a 3‑D point to screen coordinates using the viewer."""
        try:
            if hasattr(pt, "X"):
                x, y, z = float(pt.X()), float(pt.Y()), float(pt.Z())
            else:
                x, y, z = float(pt[0]), float(pt[1]), float(pt[2])
            if (
                hasattr(view, "_display")
                and hasattr(view._display, "View")
                and hasattr(view._display.View, "Project")
            ):
                return np.array(view._display.View.Project(x, y, z))
        except Exception:
            pass
        return np.array([x, y])

    def snap(self, world_pt, view):
        if not self.enabled:
            return None, None
        best, best_dist, best_label = None, float("inf"), None
        for _, strat in self.strategies:
            if not self.strategy_enabled.get(strat.__name__, True):
                continue
            result = strat(world_pt, view)
            if result is not None:
                pt, label = result
                d = np.linalg.norm(
                    self._screen_coords(view, pt) - self._screen_coords(view, world_pt)
                )
                if d < self.tol_px and d < best_dist:
                    best, best_dist, best_label = pt, d, label
        return (best, best_label) if best is not None else (None, None)

    def toggle(self):
        self.enabled = not self.enabled
