from adaptivecad.ndfield import NDField

def test_ndfield_4d():
    fld = NDField(grid_shape=[2,2,2,2], values=range(16))
    assert fld.ndim == 4
    assert fld.value_at([1,1,1,1]) == 15
