#!/usr/bin/env python3
"""Extract and save STL model from JSON output."""

import json
import base64
import os

with open('model_output.json', 'r') as f:
    data = json.load(f)

stl_b64 = data['stl_data']
stl_bytes = base64.b64decode(stl_b64)
filename = data['filename']
filepath = os.path.join('.', filename)

with open(filepath, 'wb') as f:
    f.write(stl_bytes)

size = len(stl_bytes)
print(f"✓ Model built: {filename}")
print(f"✓ File size: {size:,} bytes ({size/1024:.1f} KB)")
print(f"\nMetrics:")
print(f"  Phase energy: {data['phase_energy']:.6f}")
print(f"  Coupling energy: {data['coupling_energy']:.6f}")
print(f"  Total energy: {data['total_energy']:.6f}")
print(f"  Coherence: {data['coherence']:.6f}")
print(f"  Grid size: 32×32")
print(f"  Steps: 100")
print(f"  Phase space: wrapped")
print(f"\nFile saved to: {filepath}")
