#!/usr/bin/env python3
"""
AMA to G-code test script

This script creates a test AMA file and then converts it to G-code to verify
the G-code generator functionality.
"""

import os
import json
import zipfile
import tempfile
from adaptivecad.io.gcode_generator import ama_to_gcode, SimpleMilling

def create_test_ama(file_path):
    """Create a simple test AMA file."""
    print(f"Creating test AMA file at {file_path}")
    
    # Create parts directory if it doesn't exist
    parts_dir = os.path.join(os.path.dirname(file_path), "test_parts")
    if not os.path.exists(parts_dir):
        os.makedirs(parts_dir)
    
    # Create test manifest
    manifest_data = {
        "version": "1.0",
        "author": "AMA Test Script",
        "parts": [
            {"name": "test_cube", "material": "PLA"}
        ]
    }
    
    # Create dummy part data
    brep_data = b"Dummy BREP data for test_cube"
    part_metadata = {
        "material": "PLA", 
        "dimensions": {"x": 20, "y": 20, "z": 10},
        "toolpath": "simple_milling"
    }
    
    # Write to temporary files first
    manifest_path = os.path.join(parts_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)
    
    brep_path = os.path.join(parts_dir, "test_cube.brep")
    with open(brep_path, "wb") as f:
        f.write(brep_data)
    
    meta_path = os.path.join(parts_dir, "test_cube.json")
    with open(meta_path, "w") as f:
        json.dump(part_metadata, f, indent=2)
    
    # Create AMA archive (ZIP)
    with zipfile.ZipFile(file_path, "w") as zf:
        zf.write(manifest_path, "manifest.json")
        zf.write(brep_path, "parts/test_cube.brep")
        zf.write(meta_path, "parts/test_cube.json")
    
    # Clean up temporary files
    os.remove(manifest_path)
    os.remove(brep_path)
    os.remove(meta_path)
    os.rmdir(parts_dir)
    
    print("Test AMA file created successfully")
    return True

def main():
    """Create a test AMA file and convert it to G-code."""
    # Create a temporary AMA file
    with tempfile.NamedTemporaryFile(suffix=".ama", delete=False) as tmp_file:
        ama_path = tmp_file.name
    
    try:
        # Create the test AMA file
        if not create_test_ama(ama_path):
            print("Failed to create test AMA file")
            return False
        
        # Generate G-code filename
        gcode_path = ama_path.replace(".ama", ".gcode")
        
        # Create milling strategy
        strategy = SimpleMilling(
            safe_height=15.0,
            cut_depth=2.0,
            feed_rate=200.0,
            tool_diameter=6.0
        )
        
        # Convert to G-code
        print(f"Converting {ama_path} to G-code...")
        output_path = ama_to_gcode(ama_path, gcode_path, strategy)
        
        # Print G-code content
        print("\nGenerated G-code:")
        with open(output_path, "r") as f:
            gcode_content = f.read()
            print(gcode_content)
        
        print(f"\nG-code saved to {output_path}")
        
        # Keep files for inspection
        print(f"\nTest files created: {ama_path} and {gcode_path}")
        print("Please manually delete these files when done testing.")
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        # Clean up files in case of error
        if os.path.exists(ama_path):
            os.remove(ama_path)
        return False

if __name__ == "__main__":
    main()
