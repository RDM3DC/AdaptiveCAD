import pytest
from adaptivecad.cam import adaptive_clearing_5axis

def test_adaptive_clearing_not_implemented():
    with pytest.raises(NotImplementedError):
        adaptive_clearing_5axis(None)
