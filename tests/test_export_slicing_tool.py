import pytest


@pytest.fixture
def occ_installed():
    try:
        import OCC.Core  # noqa: F401
        return True
    except Exception:
        return False


def test_export_slices_requires_occ(occ_installed, tmp_path):
    if occ_installed:
        pytest.skip("OCC present; this test checks missing dependency")

    from adaptivecad.slice_export import export_slices_from_ama

    with pytest.raises(ImportError):
        export_slices_from_ama("dummy.ama", [0.0], tmp_path)
