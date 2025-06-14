"""Computational geometry stubs."""


class AABB:
    def __init__(self, min_pt, max_pt):
        self.min = min_pt
        self.max = max_pt

    def contains(self, p):
        return (
            self.min.x <= p.x <= self.max.x and
            self.min.y <= p.y <= self.max.y and
            self.min.z <= p.z <= self.max.z
        )
