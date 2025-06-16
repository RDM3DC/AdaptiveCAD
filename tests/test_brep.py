from adaptivecad.linalg import Vec3
from adaptivecad.geom import EulerBRep


def test_euler_tetrahedron():
    br = EulerBRep()
    v0, _ = br.mvfs(Vec3(0.0, 0.0, 0.0))
    v1, _ = br.mev(v0, Vec3(1.0, 0.0, 0.0))
    v2, _ = br.mev(v1, Vec3(0.0, 1.0, 0.0))
    br.mef([v0, v1, v2])  # base
    v3, _ = br.mev(v2, Vec3(0.0, 0.0, 1.0))
    br.mef([v0, v1, v3])
    br.mef([v1, v2, v3])
    br.mef([v2, v0, v3])

    assert len(br.solid.vertices) == 4
    assert len(br.solid.faces) == 5
    assert len(br.solid.edges) == 15
