import numpy as np
from adaptivecad.linalg import VecN


def test_vecn_basic_ops():
    a = VecN([1.0, 2.0, 3.0, 4.0])
    b = VecN([4.0, 3.0, 2.0, 1.0])
    c = a + b
    assert np.allclose(c.coords, np.array([5.0, 5.0, 5.0, 5.0]))
    assert np.isclose(a.dot(b), 20.0)
    assert np.isclose(a.norm(), np.sqrt(30.0))
    assert np.isclose(a.dist(b), np.linalg.norm(a.coords - b.coords))
    assert a.dim() == 4


def test_vecn_iter_len_repr():
    v = VecN([1, 2, 3])
    assert list(v) == [1.0, 2.0, 3.0]
    assert len(v) == 3
    assert repr(v) == "VecN([1.0, 2.0, 3.0])"
