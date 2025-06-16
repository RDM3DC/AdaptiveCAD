from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..linalg import Vec3


@dataclass
class Vertex:
    """A vertex in the B-rep."""

    pos: Vec3


@dataclass
class Edge:
    """An edge connecting two vertices."""

    v1: Vertex
    v2: Vertex
    faces: List["Face"] = field(default_factory=list)


@dataclass
class Face:
    """A face bounded by a loop of edges."""

    edges: List[Edge] = field(default_factory=list)


@dataclass
class Solid:
    """Collection of faces, edges and vertices."""

    vertices: List[Vertex] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    faces: List[Face] = field(default_factory=list)


class EulerBRep:
    """Simple B-rep built using Euler operators."""

    def __init__(self) -> None:
        self.solid = Solid()

    def mvfs(self, pos: Vec3) -> tuple[Vertex, Face]:
        """Make vertex, face and solid."""
        v = Vertex(pos)
        f = Face()
        self.solid.vertices.append(v)
        self.solid.faces.append(f)
        return v, f

    def mev(self, start: Vertex, pos: Vec3) -> tuple[Vertex, Edge]:
        """Make an edge and new vertex from ``start``."""
        v = Vertex(pos)
        e = Edge(start, v)
        self.solid.vertices.append(v)
        self.solid.edges.append(e)
        return v, e

    def mef(self, vertices: List[Vertex]) -> Face:
        """Make a face from a sequence of vertices."""
        if len(vertices) < 3:
            raise ValueError("Face requires at least three vertices")
        edges = []
        for i in range(len(vertices)):
            e = Edge(vertices[i], vertices[(i + 1) % len(vertices)])
            edges.append(e)
            self.solid.edges.append(e)
        f = Face(edges)
        for e in edges:
            e.faces.append(f)
        self.solid.faces.append(f)
        return f
