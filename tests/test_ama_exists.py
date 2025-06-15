# tests/test_ama_exists.py
import pytest
from pathlib import Path
import importlib

# Skip test if OCC is not available
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("OCC") is None, 
    reason="OCC library not available in this environment"
)

def test_write_ama(tmp_path):
    # Only import these if the test is not skipped
    from adaptivecad.io.ama_writer import write_ama
    from adaptivecad.commands import Feature
    try:
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    except ImportError:
        pytest.skip("OCC.Core.BRepPrimAPI not available")

    # Create a simple box feature
    # Ensure the Feature class can be instantiated this way for testing
    # If Feature requires a specific structure for params or shape, adjust accordingly
    box_shape = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    box_feature = Feature(name="Box", params={"l":10,"w":10,"h":10}, shape=box_shape)
    
    document = [box_feature]
    
    ama_file_path = tmp_path / "test_box.ama"
    
    # Call the writer
    result_path = write_ama(document, ama_file_path)
    
    assert result_path.exists(), "AMA file was not created"
    assert result_path == ama_file_path, "Returned path does not match input path"

    # Optional: Add more assertions, e.g., check zip contents
    import zipfile
    with zipfile.ZipFile(result_path, 'r') as zf:
        file_list = zf.namelist()
        assert "meta/manifest.json" in file_list
        assert "model/graph.json" in file_list
        assert "geom/s000.brep" in file_list
