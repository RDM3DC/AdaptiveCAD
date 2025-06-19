import os
from adaptivecad.slicer3d import slice_model_to_gcode, PrinterSettings

# Dummy model for test (replace with a real OCC TopoDS_Shape in real use)
class DummyModel:
    pass

model = DummyModel()
output_path = os.path.abspath("test_gcode_output.gcode")
settings = PrinterSettings()

print(f"[TEST] Running slice_model_to_gcode with output_path: {output_path}")
result = slice_model_to_gcode(model, output_path, settings=settings, show_progress=True)
print(f"[TEST] Result: {result}")
print(f"[TEST] File exists: {os.path.exists(output_path)}")
