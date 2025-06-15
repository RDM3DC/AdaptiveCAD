import unittest
import os
import json
import zipfile
from adaptivecad.io.ama_reader import read_ama, AMAFile, AMAPart

class TestAMAReader(unittest.TestCase):

    def setUp(self):
        """Create a dummy AMA file for testing."""
        self.test_ama_file_path = "test_reader.ama"
        self.part1_name = "cube_part"
        self.part2_name = "sphere_part"

        if not os.path.exists("test_parts_dir"):
            os.makedirs("test_parts_dir")

        self.manifest_data = {
            "version": "1.0",
            "author": "TestAMAReader",
            "parts": [
                {"name": self.part1_name, "material": "PLA"},
                {"name": self.part2_name, "material": "ABS"}
            ]
        }
        self.part1_brep_data = b"Dummy BREP data for cube_part"
        self.part1_metadata = {"color": "red", "size": "10x10x10"}
        self.part2_brep_data = b"Dummy BREP data for sphere_part"
        self.part2_metadata = {"radius": 5, "smoothness": "high"}

        with zipfile.ZipFile(self.test_ama_file_path, 'w') as zf:
            # Write manifest
            zf.writestr('manifest.json', json.dumps(self.manifest_data))
            
            # Write part 1 files
            zf.writestr(f'parts/{self.part1_name}.brep', self.part1_brep_data)
            zf.writestr(f'parts/{self.part1_name}.json', json.dumps(self.part1_metadata))

            # Write part 2 files
            zf.writestr(f'parts/{self.part2_name}.brep', self.part2_brep_data)
            zf.writestr(f'parts/{self.part2_name}.json', json.dumps(self.part2_metadata))

    def tearDown(self):
        """Clean up the dummy AMA file and directory."""
        if os.path.exists(self.test_ama_file_path):
            os.remove(self.test_ama_file_path)
        if os.path.exists("test_parts_dir"):
            # Clean up any files inside before removing dir if needed, though not strictly necessary for this test
            for root, dirs, files in os.walk("test_parts_dir", topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir("test_parts_dir")

    def test_read_valid_ama_file(self):
        """Test reading a well-formed AMA file."""
        ama_file_content = read_ama(self.test_ama_file_path)
        self.assertIsNotNone(ama_file_content)
        self.assertIsInstance(ama_file_content, AMAFile)
        
        # Check manifest
        self.assertEqual(ama_file_content.manifest["version"], "1.0")
        self.assertEqual(ama_file_content.manifest["author"], "TestAMAReader")
        self.assertEqual(len(ama_file_content.manifest["parts"]), 2)

        # Check parts
        self.assertEqual(len(ama_file_content.parts), 2)
        
        part1 = next((p for p in ama_file_content.parts if p.name == self.part1_name), None)
        self.assertIsNotNone(part1)
        self.assertIsInstance(part1, AMAPart)
        self.assertEqual(part1.name, self.part1_name)
        self.assertEqual(part1.brep_data, self.part1_brep_data)
        self.assertEqual(part1.metadata, self.part1_metadata)

        part2 = next((p for p in ama_file_content.parts if p.name == self.part2_name), None)
        self.assertIsNotNone(part2)
        self.assertIsInstance(part2, AMAPart)
        self.assertEqual(part2.name, self.part2_name)
        self.assertEqual(part2.brep_data, self.part2_brep_data)
        self.assertEqual(part2.metadata, self.part2_metadata)

    def test_read_missing_manifest(self):
        """Test reading an AMA file with a missing manifest.json."""
        with zipfile.ZipFile("missing_manifest.ama", 'w') as zf:
            zf.writestr("parts/somepart.brep", b"data")
        
        ama_file_content = read_ama("missing_manifest.ama")
        self.assertIsNone(ama_file_content)
        os.remove("missing_manifest.ama")

    def test_read_corrupted_zip(self):
        """Test reading a corrupted AMA (ZIP) file."""
        with open("corrupted.ama", "wb") as f:
            f.write(b"This is not a zip file")
        ama_file_content = read_ama("corrupted.ama")
        self.assertIsNone(ama_file_content)
        os.remove("corrupted.ama")

    def test_read_missing_part_brep(self):
        """Test reading an AMA where a part's BREP file is missing."""
        with zipfile.ZipFile("missing_brep.ama", 'w') as zf:
            manifest = {"version": "1.0", "parts": [{"name": "no_brep_part"}]}
            zf.writestr('manifest.json', json.dumps(manifest))
            zf.writestr('parts/no_brep_part.json', json.dumps({"info": "meta only"}))
        
        ama_file_content = read_ama("missing_brep.ama")
        self.assertIsNotNone(ama_file_content)
        self.assertEqual(len(ama_file_content.parts), 1)
        part = ama_file_content.parts[0]
        self.assertEqual(part.name, "no_brep_part")
        self.assertIsNone(part.brep_data)
        self.assertEqual(part.metadata, {"info": "meta only"})
        os.remove("missing_brep.ama")

    def test_read_missing_part_metadata(self):
        """Test reading an AMA where a part's metadata JSON is missing."""
        with zipfile.ZipFile("missing_meta.ama", 'w') as zf:
            manifest = {"version": "1.0", "parts": [{"name": "no_meta_part"}]}
            zf.writestr('manifest.json', json.dumps(manifest))
            zf.writestr('parts/no_meta_part.brep', b"brep here")

        ama_file_content = read_ama("missing_meta.ama")
        self.assertIsNotNone(ama_file_content)
        self.assertEqual(len(ama_file_content.parts), 1)
        part = ama_file_content.parts[0]
        self.assertEqual(part.name, "no_meta_part")
        self.assertEqual(part.brep_data, b"brep here")
        self.assertEqual(part.metadata, {})
        os.remove("missing_meta.ama")

    def test_read_empty_parts_list_in_manifest(self):
        """Test reading an AMA with an empty 'parts' list in manifest."""
        with zipfile.ZipFile("empty_parts.ama", 'w') as zf:
            manifest = {"version": "1.0", "parts": []}
            zf.writestr('manifest.json', json.dumps(manifest))
        
        ama_file_content = read_ama("empty_parts.ama")
        self.assertIsNotNone(ama_file_content)
        self.assertEqual(len(ama_file_content.parts), 0)
        self.assertEqual(ama_file_content.manifest["parts"], [])
        os.remove("empty_parts.ama")

    def test_read_no_parts_key_in_manifest(self):
        """Test reading an AMA where 'parts' key is missing from manifest."""
        with zipfile.ZipFile("no_parts_key.ama", 'w') as zf:
            manifest = {"version": "1.0", "description": "No parts array"}
            zf.writestr('manifest.json', json.dumps(manifest))
        
        ama_file_content = read_ama("no_parts_key.ama")
        self.assertIsNotNone(ama_file_content) # Should still parse manifest
        self.assertEqual(len(ama_file_content.parts), 0) # No parts should be found
        self.assertNotIn("parts", ama_file_content.manifest)
        os.remove("no_parts_key.ama")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
