import unittest
import os
import json
import zipfile
import tempfile
from adaptivecad.gcode_generator import generate_gcode_from_ama_file, generate_gcode_from_ama_data
from adaptivecad.io.ama_reader import AMAFile, AMAPart

class TestGCodeGenerator(unittest.TestCase):

    def setUp(self):
        """Set up for G-code generator tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_ama_file_path = os.path.join(self.temp_dir, "test_gcode.ama")
        self.part_name = "test_part_for_gcode"

        manifest_data = {
            "version": "1.0",
            "author": "TestGCodeGenerator",
            "parts": [
                {"name": self.part_name, "material": "Aluminum"}
            ]
        }
        part_brep_data = b"Simulated BREP data for G-code test part"
        part_metadata = {"process": "milling", "tolerance": "0.01mm"}

        with zipfile.ZipFile(self.test_ama_file_path, 'w') as zf:
            zf.writestr('manifest.json', json.dumps(manifest_data))
            zf.writestr(f'parts/{self.part_name}.brep', part_brep_data)
            zf.writestr(f'parts/{self.part_name}.json', json.dumps(part_metadata))

    def tearDown(self):
        """Clean up temporary files and directory."""
        if os.path.exists(self.test_ama_file_path):
            os.remove(self.test_ama_file_path)
        # Clean up other files in temp_dir if any were created by tests
        for item in os.listdir(self.temp_dir):
            item_path = os.path.join(self.temp_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
        os.rmdir(self.temp_dir)

    def test_generate_gcode_from_valid_ama_file(self):
        """Test G-code generation from a valid AMA file."""
        output_gcode_path = os.path.join(self.temp_dir, "output.gcode")
        gcode = generate_gcode_from_ama_file(self.test_ama_file_path, output_gcode_path)
        
        self.assertIsNotNone(gcode)
        self.assertTrue(os.path.exists(output_gcode_path))
        self.assertIn(f"; G-code generated for {self.part_name}", gcode)
        self.assertIn("G21       ; Set units to mm", gcode)
        self.assertIn("G28       ; Home all axes", gcode)
        self.assertIn("G0 Z15.000", gcode) # Example command

        with open(output_gcode_path, 'r') as f:
            file_content = f.read()
        self.assertEqual(gcode, file_content)

    def test_generate_gcode_from_ama_data(self):
        """Test G-code generation directly from AMAFile object."""
        manifest = {"version": "1.0", "parts": [{"name": "data_part"}]}
        part = AMAPart(name="data_part", brep_data=b"brep", metadata={})
        ama_data = AMAFile(manifest=manifest, parts=[part])

        gcode = generate_gcode_from_ama_data(ama_data, tool_diameter=3.0)
        self.assertIsNotNone(gcode)
        self.assertIn("; G-code generated for data_part", gcode)
        self.assertIn("; Tool diameter: 3.0mm", gcode)

    def test_generate_gcode_no_parts(self):
        """Test G-code generation when AMA file has no parts."""
        empty_ama_path = os.path.join(self.temp_dir, "empty.ama")
        manifest_data = {"version": "1.0", "author": "TestEmpty", "parts": []}
        with zipfile.ZipFile(empty_ama_path, 'w') as zf:
            zf.writestr('manifest.json', json.dumps(manifest_data))
        
        gcode = generate_gcode_from_ama_file(empty_ama_path)
        self.assertIsNotNone(gcode)
        self.assertIn("; No parts found in AMA file to process.", gcode)

    def test_generate_gcode_nonexistent_ama_file(self):
        """Test G-code generation with a non-existent AMA file path."""
        gcode = generate_gcode_from_ama_file("nonexistent.ama")
        self.assertIsNone(gcode) # Expecting None as the file can't be read

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
