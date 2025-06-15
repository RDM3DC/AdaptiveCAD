import json
import zipfile
import os

class AMAPart:
    def __init__(self, name, brep_data, metadata):
        self.name = name
        self.brep_data = brep_data
        self.metadata = metadata

    def __repr__(self):
        return f"AMAPart(name='{self.name}', metadata={self.metadata})"

class AMAFile:
    def __init__(self, manifest, parts):
        self.manifest = manifest
        self.parts = parts # List of AMAPart objects

    def __repr__(self):
        return f"AMAFile(manifest={self.manifest}, parts_count={len(self.parts)})"

def read_ama(file_path):
    """
    Reads an AMA (Adaptive Manufacturing Archive) file.

    An AMA file is a ZIP archive containing:
    - manifest.json: Metadata about the archive and a list of parts.
    - parts/<part_name>.brep: The BRep geometry of the part.
    - parts/<part_name>.json: Metadata for the part.

    Args:
        file_path (str): The path to the AMA file.

    Returns:
        AMAFile: An object representing the parsed AMA file,
                 or None if the file is invalid.
    """
    parts = []
    manifest = None

    try:
        with zipfile.ZipFile(file_path, 'r') as ama_zip:
            if 'manifest.json' not in ama_zip.namelist():
                print(f"Error: 'manifest.json' not found in {file_path}")
                return None
            
            with ama_zip.open('manifest.json') as mf_file:
                manifest_data = json.load(mf_file)
            
            manifest = manifest_data # Store the raw manifest dict

            if 'parts' not in manifest_data:
                print(f"Error: 'parts' key not found in manifest.json of {file_path}")
                return AMAFile(manifest, []) # Return with manifest but no parts if parts list is missing

            for part_entry in manifest_data.get('parts', []):
                part_name = part_entry.get('name')
                if not part_name:
                    print(f"Warning: Part entry in manifest is missing a name. Skipping.")
                    continue

                brep_file_name = f"parts/{part_name}.brep"
                meta_file_name = f"parts/{part_name}.json"

                brep_data = None
                part_metadata = {}

                if brep_file_name in ama_zip.namelist():
                    with ama_zip.open(brep_file_name) as bf:
                        brep_data = bf.read()
                else:
                    print(f"Warning: BREP file '{brep_file_name}' not found for part '{part_name}'.")
                
                if meta_file_name in ama_zip.namelist():
                    with ama_zip.open(meta_file_name) as pf_meta:
                        part_metadata = json.load(pf_meta)
                else:
                    print(f"Warning: Metadata file '{meta_file_name}' not found for part '{part_name}'.")
                
                parts.append(AMAPart(name=part_name, brep_data=brep_data, metadata=part_metadata))
        
        return AMAFile(manifest=manifest, parts=parts)

    except FileNotFoundError:
        print(f"Error: AMA file not found at {file_path}")
        return None
    except zipfile.BadZipFile:
        print(f"Error: Invalid or corrupted AMA (ZIP) file: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON in AMA file {file_path}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None

if __name__ == '__main__':
    # Example usage:
    # Create a dummy AMA file for testing
    if not os.path.exists('parts'):
        os.makedirs('parts')

    dummy_manifest = {
        "version": "1.0",
        "author": "Test Script",
        "parts": [
            {"name": "part1", "material": "PLA"},
            {"name": "part2", "material": "ABS"}
        ]
    }
    with open('manifest.json', 'w') as f:
        json.dump(dummy_manifest, f, indent=4)
    
    with open('parts/part1.brep', 'wb') as f:
        f.write(b"This is dummy BREP data for part1.")
    
    dummy_part1_meta = {"material": "PLA", "process": "FDM"}
    with open('parts/part1.json', 'w') as f:
        json.dump(dummy_part1_meta, f, indent=4)

    with open('parts/part2.brep', 'wb') as f:
        f.write(b"This is dummy BREP data for part2.")
    
    dummy_part2_meta = {"material": "ABS", "process": "SLA"}
    with open('parts/part2.json', 'w') as f:
        json.dump(dummy_part2_meta, f, indent=4)

    with zipfile.ZipFile('test.ama', 'w') as zf:
        zf.write('manifest.json')
        zf.write('parts/part1.brep', 'parts/part1.brep')
        zf.write('parts/part1.json', 'parts/part1.json')
        zf.write('parts/part2.brep', 'parts/part2.brep')
        zf.write('parts/part2.json', 'parts/part2.json')

    # Test reading the dummy AMA file
    ama_content = read_ama('test.ama')
    if ama_content:
        print("Successfully read AMA file.")
        print(f"Manifest: {ama_content.manifest}")
        for part in ama_content.parts:
            print(f"Part: {part.name}, Metadata: {part.metadata}, BREP length: {len(part.brep_data) if part.brep_data else 0}")
    else:
        print("Failed to read AMA file.")

    # Clean up dummy files
    os.remove('manifest.json')
    os.remove('parts/part1.brep')
    os.remove('parts/part1.json')
    os.remove('parts/part2.brep')
    os.remove('parts/part2.json')
    os.rmdir('parts')
    os.remove('test.ama')
