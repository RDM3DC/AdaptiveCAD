#!/usr/bin/env python
import argparse
import os
import sys

# Add the project root to the Python path to allow importing adaptivecad
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from adaptivecad.gcode_generator import generate_gcode_from_ama_file

def main():
    parser = argparse.ArgumentParser(description="Convert AMA files to G-code.")
    parser.add_argument("ama_file", help="Path to the input AMA file (.ama)")
    parser.add_argument("-o", "--output", help="Path to the output G-code file (.gcode). Defaults to input filename with .gcode extension.")
    parser.add_argument("-td", "--tool_diameter", type=float, default=6.0, help="Diameter of the milling tool in mm (default: 6.0)")

    args = parser.parse_args()

    if not os.path.exists(args.ama_file):
        print(f"Error: Input AMA file not found: {args.ama_file}")
        sys.exit(1)

    if not args.ama_file.lower().endswith(".ama"):
        print(f"Warning: Input file '{args.ama_file}' does not have an .ama extension.")

    output_gcode_path = args.output
    if not output_gcode_path:
        base, _ = os.path.splitext(args.ama_file)
        output_gcode_path = base + ".gcode"
    
    print(f"Converting {args.ama_file} to G-code...")
    print(f"Tool diameter: {args.tool_diameter} mm")

    gcode_program = generate_gcode_from_ama_file(args.ama_file, output_gcode_path, args.tool_diameter)

    if gcode_program:
        print(f"G-code successfully generated and saved to {output_gcode_path}")
    else:
        print(f"Failed to generate G-code from {args.ama_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()
