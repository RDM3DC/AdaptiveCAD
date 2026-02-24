import numpy as np

from adaptivecad.aacore.sdf import KIND_BOX, KIND_SPHERE, Prim, Scene


def mat_equals(a, b, eps=1e-6):
    return np.max(np.abs(a - b)) < eps


def test_set_transform_translation_only():
    p = Prim(KIND_SPHERE, [1.0])
    p.set_transform(pos=[2.0, -1.5, 0.75])
    M = p.xform.M
    assert mat_equals(M[:3, 3], np.array([2.0, -1.5, 0.75], dtype=np.float32))


def test_set_transform_rotation_scale():
    p = Prim(KIND_BOX, [1.0, 2.0, 3.0])
    p.set_transform(pos=[0, 0, 0], euler=[45, 0, 0], scale=[2, 3, 4])
    M = p.xform.M
    # With composition S @ Rz @ Ry @ Rx the basis columns are scaled then rotated.
    # Rotation about X mixes the original Y/Z scaled axes:
    # Expected magnitudes: X=2, Y=sqrt((3*cos)^2 + (4*sin)^2), Z=sqrt((3*sin)^2 + (4*cos)^2)
    import math

    angle = math.radians(45)
    sx = np.linalg.norm(M[:3, 0])
    sy = np.linalg.norm(M[:3, 1])
    sz = np.linalg.norm(M[:3, 2])
    exp_sy = math.sqrt((3 * math.cos(angle)) ** 2 + (4 * math.sin(angle)) ** 2)
    exp_sz = math.sqrt((3 * math.sin(angle)) ** 2 + (4 * math.cos(angle)) ** 2)
    assert abs(sx - 2) < 1e-5
    assert abs(sy - exp_sy) < 1e-5
    assert abs(sz - exp_sz) < 1e-5
    # Translation stays zero
    assert mat_equals(M[:3, 3], np.array([0, 0, 0], dtype=np.float32))


def test_scene_gpu_pack_updates_after_transform():
    sc = Scene()
    p = Prim(KIND_SPHERE, [0.5])
    sc.add(p)
    before = sc.to_gpu_structs()["xform"][0].copy()
    p.set_transform(pos=[1, 2, 3], euler=[10, 20, 30], scale=[1.1, 0.9, 2.0])
    after = sc.to_gpu_structs()["xform"][0]
    # Matrices should differ
    assert not mat_equals(before, after)
    # Check translation encoded (reshape with order='F' to match GLSL column-major packing)
    A = after.reshape(4, 4, order="F")
    assert np.allclose(A[:3, 3], [1, 2, 3], atol=1e-5)


def test_multiple_prims_packing_order():
    sc = Scene()
    p1 = Prim(KIND_SPHERE, [0.5])
    p2 = Prim(KIND_BOX, [1, 1, 1])
    sc.add(p1)
    sc.add(p2)
    p1.set_transform(pos=[0.5, 0, 0])
    p2.set_transform(pos=[-0.5, 0, 0])
    pack = sc.to_gpu_structs()
    # Reshape with order='F' to match GLSL column-major packing
    x1 = pack["xform"][0].reshape(4, 4, order="F")
    x2 = pack["xform"][1].reshape(4, 4, order="F")
    assert np.allclose(x1[:3, 3], [0.5, 0, 0], atol=1e-6)
    assert np.allclose(x2[:3, 3], [-0.5, 0, 0], atol=1e-6)
