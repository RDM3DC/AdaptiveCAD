from adaptivecad.ndbox import NDBox

def test_ndbox_4d():
    b = NDBox(center=[0,0,0,0], size=[2,4,6,8])
    assert b.ndim == 4
    assert b.volume() == 2*4*6*8
    mn, mx = b.bounds()
    assert all(mn == [-1, -2, -3, -4])
    assert b.contains([0,0,0,0])
    assert not b.contains([10,10,10,10])
