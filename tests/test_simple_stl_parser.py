import os
import sys
import numpy as np

# Ensure project root on sys.path for direct test invocation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adaptivecad.simple_stl import load_stl


def test_load_stl():
    path = os.path.join(os.path.dirname(__file__), "..", "test_cube.stl")
    verts, faces = load_stl(path)
    assert verts.shape[1] == 3
    assert faces.shape[1] == 3
    # cube should have 8 unique vertices
    assert len(verts) == 8
    # and 12 triangles
    assert len(faces) == 12
    # ensure indices are within range
    assert np.all(faces < len(verts))
