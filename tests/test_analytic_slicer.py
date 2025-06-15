import importlib
import pytest


@pytest.fixture
def occ_installed():
    try:
        import OCC.Core  # noqa: F401
        return True
    except Exception:
        return False


def test_slice_requires_occ(occ_installed):
    if occ_installed:
        pytest.skip("OCC present; this test checks missing dependency")
    from adaptivecad import analytic_slicer
    with pytest.raises(ImportError):
        analytic_slicer.slice_brep_for_layer(None, 0.0)
