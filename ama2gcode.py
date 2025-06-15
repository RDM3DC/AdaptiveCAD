#!/usr/bin/env python3
"""
AMA to G-code converter utility

This script converts an AMA (Adaptive Manufacturing Archive) file to G-code for CNC machining.

Usage:
    ama2gcode.py input.ama [output.gcode] [--strategy=simple] [--safe-height=10]
                [--cut-depth=1] [--feed-rate=100] [--tool-diameter=3]

Options:
    input.ama           Input AMA file path
    output.gcode        Output G-code file path (default is input filename with .gcode extension)
    --strategy          Milling strategy: 'simple' (default)
    --safe-height       Safe height for rapid movements in mm (default: 10.0)
    --cut-depth         Depth of cut in mm (default: 1.0)
    --feed-rate         Feed rate in mm/min (default: 100.0)
    --tool-diameter     Tool diameter in mm (default: 3.0)
"""

import os
import sys
import argparse
from adaptivecad.io import ama_to_gcode, SimpleMilling

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert AMA file to G-code')
    parser.add_argument('input', help='Input AMA file path')
    parser.add_argument('output', nargs='?', default=None, help='Output G-code file path (default: input filename with .gcode extension)')
    parser.add_argument('--strategy', default='simple', choices=['simple'], help='Milling strategy')
    parser.add_argument('--safe-height', type=float, default=10.0, help='Safe height for rapid movements in mm')
    parser.add_argument('--cut-depth', type=float, default=1.0, help='Depth of cut in mm')
    parser.add_argument('--feed-rate', type=float, default=100.0, help='Feed rate in mm/min')
    parser.add_argument('--tool-diameter', type=float, default=3.0, help='Tool diameter in mm')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.isfile(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Determine output file path if not specified
    output_path = args.output
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        output_path = os.path.join(os.path.dirname(args.input), f"{base_name}.gcode")
    
    # Create strategy based on arguments
    if args.strategy == 'simple':
        strategy = SimpleMilling(
            safe_height=args.safe_height,
            cut_depth=args.cut_depth,
            feed_rate=args.feed_rate,
            tool_diameter=args.tool_diameter
        )
    else:
        # This should not happen due to choices in argparse
        print(f"Error: Unknown strategy '{args.strategy}'.", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Generate G-code
        output_file = ama_to_gcode(args.input, output_path, strategy)
        print(f"Successfully generated G-code: {output_file}")
        sys.exit(0)
    except Exception as e:
        print(f"Error generating G-code: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
