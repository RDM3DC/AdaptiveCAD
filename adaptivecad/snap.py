import numpy as np

class SnapManager:
    def __init__(self, tol_px=12):
        self.strategies = []
        self.tol_px = tol_px  # screen-space tolerance (pixels)
        self.enabled = True   # master snap toggle

    def register(self, strategy, priority=0):
        self.strategies.append((priority, strategy))
        self.strategies.sort(reverse=True)

    def snap(self, world_pt, view):
        if not self.enabled:
            return None, None
        best, best_dist, best_label = None, float('inf'), None
        for _, strat in self.strategies:
            result = strat(world_pt, view)
            if result is not None:
                pt, label = result
                d = np.linalg.norm(view.world_to_screen(pt) - view.world_to_screen(world_pt))
                if d < self.tol_px and d < best_dist:
                    best, best_dist, best_label = pt, d, label
        return (best, best_label) if best is not None else (None, None)

    def toggle(self):
        self.enabled = not self.enabled
